#!/usr/bin/env python3
"""Install the project into an existing ComfyUI checkout.

This command never downloads or replaces ComfyUI itself. It installs the
revision-pinned Krea Edit node pack, copies the project-owned node pack,
materializes checksum-locked models under the project root, adds a bounded
extra-model-path block, and copies the selected workflows into ComfyUI's user
workflow directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from portrait_pipeline.constants import (  # noqa: E402
    HOI4_OPERATIVE_BACKGROUND_RUNTIME_PATH,
    HOI4_OPERATIVE_BACKGROUND_SHA256,
    HOI4_LEADER_BACKGROUND_RUNTIME_PATH,
    HOI4_LEADER_BACKGROUND_SHA256,
    HOI4_SCIENTIST_BACKGROUND_RUNTIME_PATH,
    HOI4_SCIENTIST_BACKGROUND_SHA256,
    ExitCode,
)
from portrait_pipeline.util import atomic_json_write, sha256_file  # noqa: E402
from scripts.install_support import (  # noqa: E402
    InstallError,
    _download_verified,
    _restore_models,
    _restore_preprocessing_models,
    _restore_preprocessing_source_artifacts,
    _restore_project_owned_files,
)

CONFIG_BEGIN = "# BEGIN HOI4 PORTRAIT WORKFLOWS"
CONFIG_END = "# END HOI4 PORTRAIT WORKFLOWS"


def _run(command: list[str], cwd: Path) -> dict[str, Any]:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False, timeout=900)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()[-1000:]
        raise InstallError(ExitCode.DEPENDENCY_MISSING, f"command failed: {command[0]}: {detail}")
    return {"command": command, "returncode": 0, "stdout": result.stdout.strip()[-1000:]}


def _checkout_krea_nodes(comfy_root: Path, actions: list[dict[str, Any]]) -> None:
    lock = json.loads((ROOT / "dependencies" / "custom_nodes.lock.json").read_text(encoding="utf-8"))
    entry = next(item for item in lock["custom_nodes"] if item["name"] == "comfyui-krea2edit")
    destination = comfy_root / "custom_nodes" / "comfyui-krea2edit"
    if destination.exists() and not (destination / ".git").is_dir():
        raise InstallError(ExitCode.NODE_MISSING, f"refusing to replace non-Git node directory: {destination}")
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        actions.append(_run(["git", "clone", entry["repository"], str(destination)], comfy_root))
    actions.append(_run(["git", "fetch", "--tags", "--force", "origin", entry["revision"]], destination))
    actions.append(_run(["git", "checkout", "--detach", entry["revision"]], destination))
    actual = _run(["git", "rev-parse", "HEAD"], destination)["stdout"]
    if actual != entry["revision"]:
        raise InstallError(ExitCode.NODE_MISSING, "Krea Edit node revision does not match the lock")
    actions.append({"action": "krea_edit_nodes_verified", "path": str(destination), "revision": actual})


def _install_hoi4_backgrounds(
    actions: list[dict[str, Any]],
) -> None:
    assets = (
        (
            "scientist",
            HOI4_SCIENTIST_BACKGROUND_RUNTIME_PATH,
            HOI4_SCIENTIST_BACKGROUND_SHA256,
        ),
        (
            "operative",
            HOI4_OPERATIVE_BACKGROUND_RUNTIME_PATH,
            HOI4_OPERATIVE_BACKGROUND_SHA256,
        ),
        (
            "leader",
            HOI4_LEADER_BACKGROUND_RUNTIME_PATH,
            HOI4_LEADER_BACKGROUND_SHA256,
        ),
    )
    for name, runtime_path, expected_sha256 in assets:
        destination = ROOT / runtime_path
        if destination.is_file():
            actual = sha256_file(destination)
            if actual != expected_sha256:
                raise InstallError(ExitCode.MODEL_CHECKSUM_MISMATCH, f"local HOI4 {name} background checksum mismatch")
            actions.append({
                "action": f"hoi4_{name}_background_verified",
                "path": str(destination),
                "sha256": actual,
            })
            continue
        raise InstallError(
            ExitCode.BACKGROUND_UNRESOLVED,
            f"required HOI4 background is missing from the repository: {runtime_path}",
        )


def _source_files() -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    node_source = ROOT / "src" / "comfyui_hoi4_portrait_nodes"
    for source in sorted(node_source.rglob("*")):
        if source.is_file() and "__pycache__" not in source.parts and source.suffix != ".pyc":
            pairs.append((source, source.relative_to(node_source)))
    pipeline_source = ROOT / "src" / "portrait_pipeline"
    for source in sorted(pipeline_source.rglob("*")):
        if source.is_file() and "__pycache__" not in source.parts and source.suffix != ".pyc":
            pairs.append((source, Path("portrait_pipeline") / source.relative_to(pipeline_source)))
    return pairs


def _tree_fingerprint(root: Path, relative_paths: list[Path]) -> str | None:
    if not root.is_dir() or any(not (root / relative).is_file() for relative in relative_paths):
        return None
    digest = hashlib.sha256()
    for relative in sorted(relative_paths):
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256_file(root / relative)))
    return digest.hexdigest()


def _copy_project_nodes(comfy_root: Path, actions: list[dict[str, Any]]) -> None:
    destination = comfy_root / "custom_nodes" / "hoi4_portrait_nodes"
    pairs = _source_files()
    relative_paths = [relative for _, relative in pairs]
    source_digest = hashlib.sha256()
    for source, relative in sorted(pairs, key=lambda item: item[1].as_posix()):
        source_digest.update(relative.as_posix().encode("utf-8"))
        source_digest.update(b"\0")
        source_digest.update(bytes.fromhex(sha256_file(source)))
    expected = source_digest.hexdigest()
    if destination.exists():
        actual = _tree_fingerprint(destination, relative_paths)
        if actual != expected:
            raise InstallError(
                ExitCode.NODE_MISSING,
                f"existing project node directory differs; back it up or remove it explicitly: {destination}",
            )
        (destination / ".hoi4_project_root").write_text(str(ROOT) + "\n", encoding="utf-8")
        actions.append({"action": "project_nodes_verified", "path": str(destination), "sha256": actual})
        return
    for source, relative in pairs:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    actual = _tree_fingerprint(destination, relative_paths)
    if actual != expected:
        raise InstallError(ExitCode.NODE_MISSING, "copied project node pack failed checksum verification")
    (destination / ".hoi4_project_root").write_text(str(ROOT) + "\n", encoding="utf-8")
    actions.append({"action": "project_nodes_installed", "path": str(destination), "sha256": actual})


def _extra_model_block() -> str:
    root_json = json.dumps(str(ROOT))
    return (
        f"{CONFIG_BEGIN}\n"
        "hoi4_portrait:\n"
        f"  base_path: {root_json}\n"
        "  diffusion_models: models/diffusion_models\n"
        "  unet: models/diffusion_models\n"
        "  text_encoders: models/text_encoders\n"
        "  vae: models/vae\n"
        "  upscale_models: models/upscale_models\n"
        "  loras: |\n"
        "    models/loras\n"
        "    loras\n"
        "  autoprompter: models/autoprompter\n"
        "  is_default: true\n"
        f"{CONFIG_END}\n"
    )


def _merge_extra_model_paths(comfy_root: Path, actions: list[dict[str, Any]]) -> None:
    path = comfy_root / "extra_model_paths.yaml"
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    block = _extra_model_block()
    if CONFIG_BEGIN in existing or CONFIG_END in existing:
        if CONFIG_BEGIN not in existing or CONFIG_END not in existing:
            raise InstallError(ExitCode.WORKFLOW_INVALID, "existing HOI4 extra-model-path marker block is malformed")
        start = existing.index(CONFIG_BEGIN)
        end = existing.index(CONFIG_END, start) + len(CONFIG_END)
        current = existing[start:end].rstrip() + "\n"
        if current != block:
            raise InstallError(
                ExitCode.WORKFLOW_INVALID,
                "existing HOI4 extra-model-path block differs; remove only that marked block and rerun",
            )
        actions.append({"action": "extra_model_paths_verified", "path": str(path)})
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    separator = "" if not existing or existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
    path.write_text(existing + separator + block, encoding="utf-8")
    actions.append({"action": "extra_model_paths_installed", "path": str(path)})


def _copy_workflows(
    comfy_root: Path,
    actions: list[dict[str, Any]],
    workflow_ids: set[str] | None = None,
) -> None:
    destination = comfy_root / "user" / "default" / "workflows" / "hoi4_portraits"
    destination.mkdir(parents=True, exist_ok=True)
    count = 0
    for source in sorted((ROOT / "workflows").glob("**/*.json")):
        if source.name.endswith(".api.json"):
            continue
        if workflow_ids is None and source.stem == "hoi4_portraits_prepare_portrait_qwen":
            continue
        if workflow_ids is not None and source.stem not in workflow_ids:
            continue
        target = destination / source.name
        if target.is_file() and sha256_file(target) != sha256_file(source):
            raise InstallError(ExitCode.WORKFLOW_INVALID, f"existing workflow differs: {target}")
        if not target.is_file():
            shutil.copy2(source, target)
        count += 1
    actions.append({"action": "ui_workflows_installed", "path": str(destination), "count": count})


def _copy_example_input(comfy_root: Path, actions: list[dict[str, Any]]) -> None:
    source = ROOT / "docs" / "assets" / "examples" / "preparation_01_before.jpg"
    destination = comfy_root / "input" / "hoi4_preparation_example.jpg"
    if not source.is_file():
        raise InstallError(ExitCode.SOURCE_INVALID, "the portrait preparation example image is missing")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and sha256_file(destination) != sha256_file(source):
        raise InstallError(ExitCode.SOURCE_INVALID, f"existing example image differs: {destination}")
    if not destination.is_file():
        shutil.copy2(source, destination)
    actions.append({"action": "example_input_installed", "path": str(destination)})


def _install_autoprompter_runtime(
    profile: str,
    actions: list[dict[str, Any]],
    workflow_ids: set[str] | None = None,
) -> None:
    if (
        profile != "hoi4_portraits_local_nvidia_16gb"
        or os.name != "nt"
        or (workflow_ids is not None and "hoi4_portraits_local_nvidia_16gb" not in workflow_ids)
    ):
        return
    lock = json.loads((ROOT / "dependencies" / "autoprompter_runtime.lock.json").read_text(encoding="utf-8"))
    artifact = lock["artifacts"]["windows_x64"]
    archive = ROOT / ".runtime" / "downloads" / artifact["filename"]
    _download_verified(
        artifact["url"],
        archive,
        artifact["size_bytes"],
        artifact["sha256"],
        actions,
    )
    destination = ROOT / artifact["install_directory"]
    executable = ROOT / artifact["install_path"]
    if executable.is_file():
        if (
            executable.stat().st_size != artifact["extracted_binary_size_bytes"]
            or sha256_file(executable) != artifact["extracted_binary_sha256"]
        ):
            raise InstallError(ExitCode.MODEL_CHECKSUM_MISMATCH, "installed autoprompter runtime checksum mismatch")
    else:
        destination.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as package:
            for member in package.infolist():
                target = (destination / member.filename).resolve()
                try:
                    target.relative_to(destination.resolve())
                except ValueError as exc:
                    raise InstallError(ExitCode.DEPENDENCY_MISSING, "autoprompter runtime archive contains an unsafe path") from exc
            package.extractall(destination)
        if (
            not executable.is_file()
            or executable.stat().st_size != artifact["extracted_binary_size_bytes"]
            or sha256_file(executable) != artifact["extracted_binary_sha256"]
        ):
            raise InstallError(ExitCode.MODEL_CHECKSUM_MISMATCH, "extracted autoprompter runtime checksum mismatch")
    actions.append({
        "action": "autoprompter_runtime_verified",
        "path": str(executable),
        "sha256": sha256_file(executable),
    })


def install(
    comfy_root: Path,
    profile: str,
    workflow_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    if not comfy_root.is_dir() or not (comfy_root / "main.py").is_file():
        raise InstallError(ExitCode.WORKFLOW_INVALID, "existing ComfyUI root must contain main.py")
    if profile not in {"hoi4_portraits_local_nvidia_16gb", "hoi4_portraits_full_power_gpu"}:
        raise InstallError(ExitCode.INPUT_SCHEMA_INVALID, "existing-runtime install supports local NVIDIA or full-power GPU profiles")
    actions: list[dict[str, Any]] = [{
        "action": "existing_comfyui_verified",
        "path": str(comfy_root),
        "main_sha256": sha256_file(comfy_root / "main.py"),
        "comfyui_downloaded": False,
    }]
    identity_workflows = {
        "hoi4_portraits_local_nvidia_16gb",
        "hoi4_portraits_full_power_gpu",
        "hoi4_portraits_agent_local_nvidia_16gb",
        "hoi4_portraits_agent_full_power_gpu",
    }
    krea_edit_workflows = identity_workflows | {"hoi4_portraits_prepare_portrait_for_hoi4"}
    if workflow_ids is None or workflow_ids.intersection(krea_edit_workflows):
        _checkout_krea_nodes(comfy_root, actions)
    _copy_project_nodes(comfy_root, actions)
    model_lock = json.loads((ROOT / "dependencies" / "models.lock.json").read_text(encoding="utf-8"))
    generation_workflows = identity_workflows | {
        "hoi4_portraits_no_input_local_nvidia_16gb",
        "hoi4_portraits_no_input_full_power_gpu",
        "hoi4_portraits_agent_no_input_local_nvidia_16gb",
        "hoi4_portraits_agent_no_input_full_power_gpu",
    }
    if workflow_ids is None or workflow_ids.intersection(generation_workflows):
        _restore_project_owned_files(model_lock, actions)
    _restore_models(model_lock, profile, actions, workflow_ids)
    preprocessing_lock = json.loads((ROOT / "dependencies" / "preprocessing_lock.json").read_text(encoding="utf-8"))
    _restore_preprocessing_models(preprocessing_lock, actions)
    _restore_preprocessing_source_artifacts(preprocessing_lock, actions)
    _install_autoprompter_runtime(profile, actions, workflow_ids)
    _merge_extra_model_paths(comfy_root, actions)
    _install_hoi4_backgrounds(actions)
    if workflow_ids is None or workflow_ids.intersection({"hoi4_portraits_prepare_portrait_for_hoi4", "hoi4_portraits_prepare_portrait_qwen", "hoi4_portraits_prepare_portrait_basic"}):
        _copy_example_input(comfy_root, actions)
    _copy_workflows(comfy_root, actions, workflow_ids)
    return actions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install HOI4 portrait workflows into an existing ComfyUI checkout.")
    parser.add_argument("--comfyui-root", required=True, type=Path)
    parser.add_argument("--profile", required=True, choices=["hoi4_portraits_local_nvidia_16gb", "hoi4_portraits_full_power_gpu"])
    parser.add_argument(
        "--workflow",
        action="append",
        choices=[
            "hoi4_portraits_local_nvidia_16gb",
            "hoi4_portraits_full_power_gpu",
            "hoi4_portraits_agent_local_nvidia_16gb",
            "hoi4_portraits_agent_full_power_gpu",
            "hoi4_portraits_no_input_local_nvidia_16gb",
            "hoi4_portraits_no_input_full_power_gpu",
            "hoi4_portraits_agent_no_input_local_nvidia_16gb",
            "hoi4_portraits_agent_no_input_full_power_gpu",
            "hoi4_portraits_prepare_portrait_for_hoi4",
            "hoi4_portraits_prepare_portrait_qwen",
            "hoi4_portraits_prepare_portrait_basic",
        ],
        help="copy only the named UI workflow; repeat to install more than one",
    )
    args = parser.parse_args(argv)
    try:
        actions = install(
            args.comfyui_root.expanduser().resolve(),
            args.profile,
            set(args.workflow) if args.workflow else None,
        )
    except InstallError as exc:
        print(json.dumps({"status": "BLOCKED", "exit_code": int(exc.code), "error": str(exc)}, indent=2), file=sys.stderr)
        return int(exc.code)
    receipt = {
        "schema_version": "1.0.0",
        "status": "PASS_SETUP_ONLY",
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "profile": args.profile,
        "workflows": sorted(args.workflow) if args.workflow else "all",
        "comfyui_root": str(args.comfyui_root.expanduser().resolve()),
        "actions": actions,
        "next_step": "Restart ComfyUI, open the installed workflow, and try one portrait.",
    }
    receipt_path = ROOT / ".runtime" / "existing_comfyui_install_receipt.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_json_write(receipt_path, receipt)
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
