#!/usr/bin/env python3
"""Fail-closed bootstrap entrypoint.

This command is intentionally safe to run on a clean machine. It records the
preflight first and refuses all downloads or installs while any hard gate is
unresolved. The current project state is expected to stop at that boundary.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from portrait_pipeline.constants import ExitCode  # noqa: E402
from portrait_pipeline.comfy_client import ComfyTransportError, LoopbackComfyClient  # noqa: E402
from portrait_pipeline.graph_spec.builder import build_workflow_artifacts  # noqa: E402
from portrait_pipeline.preflight import PROFILE_RUNTIME_LOCKS, collect_preflight, render_markdown  # noqa: E402
from portrait_pipeline.util import atomic_json_write, relative_safe_path, sanitize_public_paths, sha256_file  # noqa: E402
from portrait_pipeline.workflow_validation import validate_all_workflows  # noqa: E402


def _capability_report(profile: str, preflight: dict[str, Any], actions: list[dict[str, Any]]) -> dict[str, Any]:
    required_workflows = (
        "workflows/human/local_mac_16gb/human_local_mac_16gb.json",
        "workflows/human/local_nvidia_16gb/human_local_nvidia_16gb.json",
        "workflows/agent/local_mac_16gb/agent_local_mac_16gb.json",
        "workflows/agent/local_nvidia_16gb/agent_local_nvidia_16gb.json",
    )
    return {"schema_version": "1.0.0", "profile": profile, "created_at": datetime.now(timezone.utc).isoformat(), "status": preflight["status"], "installation_permitted": preflight["installation_permitted"], "preflight": preflight, "actions": actions, "workflow_validation": validate_all_workflows(ROOT) if all((ROOT / path).is_file() for path in required_workflows) else []}


def _run(command: list[str], cwd: Path = ROOT) -> dict[str, Any]:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False, timeout=900)
    return {"command": command, "returncode": result.returncode, "stdout": result.stdout[-2000:], "stderr": result.stderr[-2000:]}


def _write_bootstrap_log(run_id: str, profile: str, actions: list[dict[str, Any]], status: str) -> Path:
    path = ROOT / "logs" / "bootstrap" / f"{run_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({"run_id": run_id, "profile": profile, "status": status, "recorded_at": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False) + "\n")
        for action in actions:
            handle.write(json.dumps(action, ensure_ascii=False) + "\n")
    return path


def _qualification_install_decision(preflight: dict[str, Any], *, owner_authorized: bool) -> tuple[bool, list[str]]:
    """Decide whether missing installable inputs may be provisioned.

    A normal restore remains strictly fail-closed.  The explicit private
    qualification mode exists because a clean machine necessarily fails the
    runtime/model/node gates before those components can be installed.  It
    does not waive production gates: background, source-rights, calibration,
    live compatibility, remote-auth, and final-audit gates remain blockers.
    """

    if not owner_authorized:
        return False, ["private qualification installation requires explicit owner authorization"]
    hard_refusals: list[str] = []
    for gate in preflight.get("gates", []):
        if not isinstance(gate, dict):
            continue
        name = str(gate.get("name", ""))
        status = str(gate.get("status", ""))
        evidence = gate.get("evidence", {})
        if name == "planning_package_checksums" and status != "PASS":
            hard_refusals.append("planning package checksum verification is not PASS")
        if name == "immutable_style_lora" and status != "PASS":
            hard_refusals.append("immutable style LoRA verification is not PASS")
        if name == "license_and_rights_review" and status not in {"PASS", "APPROVED", "RESOLVED"}:
            # The command explicitly authorizes a private qualification copy,
            # but never converts the unresolved review into production
            # clearance.  The action is recorded below and reports stay
            # BLOCKED until the owner resolves scope and terms.
            continue
        if name in {"model_artifact_preflight", "preprocessing_and_audit_dependencies"}:
            checks = evidence.get("checks", []) if isinstance(evidence, dict) else []
            if any(isinstance(item, dict) and str(item.get("status", "")).startswith("BLOCKED_CHECKSUM") for item in checks):
                hard_refusals.append(f"{name} reports a checksum mismatch")
            if any(isinstance(item, dict) and item.get("status") == "BLOCKED_UNSUPPORTED_FORMAT" for item in checks):
                hard_refusals.append(f"{name} reports an unsupported artifact format")
        if name == "custom_node_preflight" and status == "BLOCKED":
            packages = evidence.get("packages", []) if isinstance(evidence, dict) else []
            if any(isinstance(item, dict) and item.get("status") == "BLOCKED_CHECKSUM_MISMATCH" for item in packages):
                hard_refusals.append("custom-node preflight reports a checksum mismatch")
    return not hard_refusals, hard_refusals


class BootstrapError(RuntimeError):
    def __init__(self, code: ExitCode, message: str):
        super().__init__(message)
        self.code = code


def _run_checked(command: list[str], cwd: Path = ROOT) -> dict[str, Any]:
    try:
        result = _run(command, cwd)
    except (OSError, subprocess.SubprocessError) as exc:
        raise BootstrapError(ExitCode.DEPENDENCY_MISSING, f"command failed to start: {command[0]}") from exc
    if result["returncode"] != 0:
        raise BootstrapError(ExitCode.DEPENDENCY_MISSING, f"command failed: {command[0]}")
    return result


def _git_checkout(url: str, destination: Path, revision: str, actions: list[dict[str, Any]]) -> None:
    if not destination.exists():
        actions.append(_run_checked(["git", "clone", url, str(destination)], ROOT))
    elif not (destination / ".git").exists():
        raise BootstrapError(ExitCode.NODE_MISSING, f"refusing to use a non-Git checkout at {destination}")
    actions.append(_run_checked(["git", "fetch", "--tags", "--force", "origin", revision], destination))
    actions.append(_run_checked(["git", "checkout", "--detach", revision], destination))
    actual = _run_checked(["git", "rev-parse", "HEAD"], destination)["stdout"].strip()
    if actual != revision:
        raise BootstrapError(ExitCode.NODE_MISSING, f"checkout revision mismatch at {destination}")


def _python_executable(venv: Path) -> Path:
    candidate = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not candidate.is_file():
        raise BootstrapError(ExitCode.DEPENDENCY_MISSING, "pinned Python environment was not created")
    return candidate


def _install_python_environment(lock: dict[str, Any], runtime_lock: dict[str, Any], actions: list[dict[str, Any]], profile: str) -> Path:
    uv = shutil.which("uv")
    if not uv:
        raise BootstrapError(ExitCode.DEPENDENCY_MISSING, "uv is required for the pinned Python environment")
    venv = ROOT / ".venv"
    if not venv.exists():
        actions.append(_run_checked([uv, "venv", str(venv), "--python", os.environ.get("PORTRAIT_PYTHON", "3.12")], ROOT))
    python = _python_executable(venv)
    profile_for_lock = {
        "local_mac_16gb": "agent_local_mac_16gb",
        "local_nvidia_16gb": "agent_local_nvidia_16gb",
        "full_power_gpu": "human_full_power_gpu",
    }.get(profile, profile)
    profile_lock_id = PROFILE_RUNTIME_LOCKS.get(profile_for_lock)
    profile_lock = runtime_lock.get("profile_locks", {}).get(profile_lock_id, {}) if profile_lock_id else {}
    profile_lock_path = ROOT / str(profile_lock.get("path", ""))
    if not profile_lock_id or not profile_lock_path.is_file() or profile_lock.get("status") != "RESOLVED" or sha256_file(profile_lock_path) != profile_lock.get("sha256"):
        raise BootstrapError(ExitCode.DEPENDENCY_MISSING, f"resolved runtime profile lock is unavailable for {profile}")
    actions.append({"action": "runtime_profile_lock_verified", "profile": profile, "path": str(profile_lock_path.relative_to(ROOT)), "sha256": sha256_file(profile_lock_path)})
    profile_result = _run_checked([uv, "pip", "install", "--python", str(python), "--require-hashes", "-r", str(profile_lock_path)], ROOT)
    actions.append({"action": "runtime_profile_installed", "profile": profile, "result": profile_result})
    project_lock = runtime_lock.get("project_lock", {})
    project_lock_path = ROOT / str(project_lock.get("path", ""))
    if project_lock.get("status") != "RESOLVED" or not project_lock_path.is_file() or sha256_file(project_lock_path) != project_lock.get("sha256"):
        raise BootstrapError(ExitCode.DEPENDENCY_MISSING, "resolved project dependency lock is unavailable")
    actions.append({"action": "project_dependency_lock_verified", "path": str(project_lock_path.relative_to(ROOT)), "sha256": sha256_file(project_lock_path)})
    actions.append(_run_checked([uv, "pip", "install", "--python", str(python), "--require-hashes", "-r", str(project_lock_path)], ROOT))
    actions.append(_run_checked([uv, "pip", "install", "--python", str(python), "--no-deps", "-e", str(ROOT)], ROOT))
    return python


def _artifact_url(entry: dict[str, Any], filename: str) -> str:
    source_url = str(entry.get("source_url", ""))
    if "/tree/" in source_url:
        source_path = str(entry.get("source_relative_path", filename))
        source_url = source_url.replace("/tree/", "/resolve/", 1).rstrip("/") + "/" + urllib.parse.quote(source_path, safe="/")
    return source_url


def _download_verified(url: str, destination: Path, expected_size: int | None, expected_sha256: str, actions: list[dict[str, Any]]) -> None:
    if destination.is_file():
        actual_size = destination.stat().st_size
        actual_sha = sha256_file(destination)
        if actual_size == expected_size and actual_sha == expected_sha256:
            actions.append({"action": "model_cache_hit", "path": str(destination.relative_to(ROOT)), "size_bytes": actual_size, "sha256": actual_sha})
            return
        raise BootstrapError(ExitCode.MODEL_CHECKSUM_MISMATCH, f"locked model checksum mismatch: {destination.relative_to(ROOT)}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {os.environ['HF_TOKEN']}"} if os.environ.get("HF_TOKEN") else {})
    temporary: Path | None = None
    try:
        with urllib.request.urlopen(request, timeout=120) as response, tempfile.NamedTemporaryFile("wb", dir=destination.parent, prefix=f".{destination.name}.", suffix=".download", delete=False) as handle:
            temporary = Path(handle.name)
            size = 0
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                handle.write(chunk)
        actual_sha = sha256_file(temporary)
        if (expected_size is not None and size != expected_size) or actual_sha != expected_sha256:
            raise BootstrapError(ExitCode.MODEL_CHECKSUM_MISMATCH, f"downloaded model checksum or size mismatch: {destination.relative_to(ROOT)}")
        os.replace(temporary, destination)
        temporary = None
        actions.append({"action": "model_restored", "path": str(destination.relative_to(ROOT)), "url": url, "size_bytes": size, "sha256": actual_sha})
    except urllib.error.HTTPError as exc:
        raise BootstrapError(ExitCode.DEPENDENCY_MISSING, f"official model source returned HTTP {exc.code}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise BootstrapError(ExitCode.DEPENDENCY_MISSING, "official model source was unavailable") from exc
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _restore_models(model_lock: dict[str, Any], profile: str, actions: list[dict[str, Any]]) -> None:
    workflow_profiles = {
        "local_mac_16gb": {"human_local_mac_16gb", "agent_local_mac_16gb"},
        "local_nvidia_16gb": {"human_local_nvidia_16gb", "agent_local_nvidia_16gb"},
        "full_power_gpu": {"human_full_power_gpu"},
        "agent_full_power_gpu": {"agent_full_power_gpu"},
    }[profile]
    for entry in model_lock.get("models", []):
        if not entry.get("mandatory") or not workflow_profiles.intersection(entry.get("profiles", [])):
            continue
        destination_root = ROOT / str(entry.get("destination_folder", "models"))
        shard_hashes = entry.get("shard_sha256")
        if isinstance(shard_hashes, dict):
            shard_sizes = entry.get("shard_size_bytes", {})
            for filename, expected_sha in sorted(shard_hashes.items()):
                _download_verified(_artifact_url(entry, filename), destination_root / filename, shard_sizes.get(filename), str(expected_sha), actions)
        else:
            filename = str(entry.get("filename", ""))
            if not filename or not entry.get("sha256"):
                raise BootstrapError(ExitCode.DEPENDENCY_MISSING, f"model lock entry is incomplete: {entry.get('name')}")
            _download_verified(_artifact_url(entry, filename), destination_root / filename, entry.get("size_bytes"), str(entry["sha256"]), actions)
        runtime_files = entry.get("runtime_files")
        if isinstance(runtime_files, list):
            for runtime_file in runtime_files:
                if not isinstance(runtime_file, dict):
                    raise BootstrapError(ExitCode.DEPENDENCY_MISSING, f"runtime metadata entry is invalid: {entry.get('name')}")
                filename = runtime_file.get("filename")
                source_relative_path = runtime_file.get("source_relative_path")
                source_url = runtime_file.get("source_url")
                expected_size = runtime_file.get("size_bytes")
                expected_hash = runtime_file.get("sha256")
                if not isinstance(filename, str) or not isinstance(source_relative_path, str) or not isinstance(source_url, str) or not source_url.startswith("https://") or not isinstance(expected_size, int) or not isinstance(expected_hash, str):
                    raise BootstrapError(ExitCode.DEPENDENCY_MISSING, f"runtime metadata lock entry is incomplete: {entry.get('name')}")
                runtime_entry = {"source_url": source_url, "source_relative_path": source_relative_path}
                _download_verified(_artifact_url(runtime_entry, filename), destination_root / filename, expected_size, expected_hash, actions)


def _restore_preprocessing_models(preprocessing_lock: dict[str, Any], actions: list[dict[str, Any]]) -> None:
    """Restore mandatory preprocessing artifacts from their exact primary URLs."""

    for entry in preprocessing_lock.get("dependencies", []):
        if not entry.get("mandatory"):
            continue
        destination_value = entry.get("destination_path")
        artifact_url = entry.get("artifact_url")
        artifact_size = entry.get("artifact_size_bytes")
        artifact_hash = entry.get("artifact_sha256")
        if not isinstance(destination_value, str) or not isinstance(artifact_url, str) or not artifact_url.startswith("https://") or not isinstance(artifact_size, int) or not isinstance(artifact_hash, str):
            raise BootstrapError(ExitCode.DEPENDENCY_MISSING, f"preprocessing lock entry is incomplete: {entry.get('name')}")
        destination = relative_safe_path(ROOT, destination_value)
        _download_verified(artifact_url, destination, artifact_size, artifact_hash, actions)


def _restore_preprocessing_source_artifacts(preprocessing_lock: dict[str, Any], actions: list[dict[str, Any]]) -> None:
    """Restore pinned local model-code files required by trusted remote code."""

    for entry in preprocessing_lock.get("dependencies", []):
        if not entry.get("mandatory"):
            continue
        source_artifacts = entry.get("source_artifacts")
        if not isinstance(source_artifacts, dict) or not source_artifacts.get("runtime_required"):
            continue
        source_files = source_artifacts.get("files")
        if not isinstance(source_files, list) or not source_files:
            raise BootstrapError(ExitCode.DEPENDENCY_MISSING, f"preprocessing source-artifact lock entry is incomplete: {entry.get('name')}")
        for source_file in source_files:
            if not isinstance(source_file, dict):
                raise BootstrapError(ExitCode.DEPENDENCY_MISSING, f"preprocessing source-artifact entry is invalid: {entry.get('name')}")
            destination_value = source_file.get("destination_path")
            artifact_url = source_file.get("artifact_url")
            artifact_size = source_file.get("size_bytes")
            artifact_hash = source_file.get("sha256")
            filename = source_file.get("filename")
            if not isinstance(destination_value, str) or not isinstance(filename, str) or not isinstance(artifact_url, str) or not artifact_url.startswith("https://") or not isinstance(artifact_size, int) or not isinstance(artifact_hash, str):
                raise BootstrapError(ExitCode.DEPENDENCY_MISSING, f"preprocessing source-artifact lock entry is incomplete: {entry.get('name')}")
            destination = relative_safe_path(ROOT, destination_value)
            if destination.name != filename or destination.suffix.casefold() not in {".py", ".json"}:
                raise BootstrapError(ExitCode.DEPENDENCY_MISSING, f"preprocessing source-artifact format is unsupported: {entry.get('name')}")
            try:
                destination.relative_to((ROOT / "models" / "preprocessing").resolve())
            except ValueError as exc:
                raise BootstrapError(ExitCode.DEPENDENCY_MISSING, f"preprocessing source-artifact path escapes the controlled model root: {entry.get('name')}") from exc
            _download_verified(artifact_url, destination, artifact_size, artifact_hash, actions)


def _write_extra_model_paths(comfy_root: Path, actions: list[dict[str, Any]]) -> None:
    # The project-owned style LoRA is immutable and must be loaded from its
    # original read-only path.  Keep downloaded model artifacts under
    # models/loras, while adding the immutable project directory to the same
    # ComfyUI search category without copying or rewriting the file.
    config = """hoi4_portrait:\n  base_path: {root}\n  diffusion_models: models/diffusion_models\n  unet: models/diffusion_models\n  text_encoders: models/text_encoders\n  vae: models/vae\n  loras: |\n    models/loras\n    loras\n  autoprompter: models/autoprompter\n  is_default: true\n""".format(root=ROOT)
    path = comfy_root / "extra_model_paths.yaml"
    if path.is_file() and path.read_text(encoding="utf-8") != config:
        raise BootstrapError(ExitCode.WORKFLOW_INVALID, f"existing ComfyUI extra model path config differs: {path}")
    if not path.is_file():
        path.write_text(config, encoding="utf-8")
    actions.append({"action": "extra_model_paths_verified", "path": str(path.relative_to(ROOT))})


def _terminate_process(process: subprocess.Popen[Any] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=15)


def _start_preprocessing_service(python: Path, actions: list[dict[str, Any]]) -> tuple[subprocess.Popen[Any], dict[str, str]]:
    port = int(os.environ.get("PORTRAIT_PREPROCESSING_PORT", "8790"))
    if not 1024 <= port <= 65535:
        raise BootstrapError(ExitCode.INPUT_SCHEMA_INVALID, "PORTRAIT_PREPROCESSING_PORT is outside the bounded range")
    log_path = ROOT / "logs" / "bootstrap" / "preprocessing-service.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["HOI4_SUBJECT_SERVICE_LOOPBACK"] = f"http://127.0.0.1:{port}/v1/subject"
    environment["HOI4_MASK_SERVICE_LOOPBACK"] = f"http://127.0.0.1:{port}/v1/mask"
    with log_path.open("ab") as log_handle:
        process = subprocess.Popen([str(python), "-m", "portrait_pipeline.preprocessing_service", "--root", str(ROOT), "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=environment, stdout=log_handle, stderr=subprocess.STDOUT)
    actions.append({"action": "preprocessing_service_started", "pid": process.pid, "binding": f"http://127.0.0.1:{port}", "subject_endpoint": environment["HOI4_SUBJECT_SERVICE_LOOPBACK"], "mask_endpoint": environment["HOI4_MASK_SERVICE_LOOPBACK"]})
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise BootstrapError(ExitCode.DEPENDENCY_MISSING, "preprocessing sidecar exited before health readiness")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as response:
                health = json.loads(response.read().decode("utf-8"))
            if isinstance(health, dict) and health.get("status") == "PASS":
                actions.append({"action": "preprocessing_service_health", "status": "PASS", "binding": f"http://127.0.0.1:{port}", "checks": health.get("checks", [])})
                return process, environment
            raise BootstrapError(ExitCode.DEPENDENCY_MISSING, "preprocessing sidecar health is BLOCKED")
        except BootstrapError:
            _terminate_process(process)
            raise
        except (OSError, urllib.error.URLError, UnicodeDecodeError, json.JSONDecodeError):
            time.sleep(1)
    _terminate_process(process)
    raise BootstrapError(ExitCode.DEPENDENCY_MISSING, "preprocessing sidecar health check timed out")


def restore_from_lock(profile: str) -> list[dict[str, Any]]:
    """Restore pinned components after preflight has passed.

    The function is not called in the current blocked environment. Every
    external operation is explicit, non-interactive, revision-pinned, and
    followed by an import/checksum gate.
    """
    actions: list[dict[str, Any]] = []
    comfy_root = ROOT / "comfyui"
    dependency_lock = json.loads((ROOT / "dependencies" / "dependencies.lock.json").read_text(encoding="utf-8"))
    comfy = next(item for item in dependency_lock["dependencies"] if item["name"] == "ComfyUI")
    _git_checkout(str(comfy["official_source"]), comfy_root, str(comfy["version_or_commit"]), actions)
    custom_root = comfy_root / "custom_nodes" / "comfyui-krea2edit"
    krea = next(item for item in dependency_lock["dependencies"] if item["name"] == "comfyui-krea2edit")
    _git_checkout(str(krea["official_source"]), custom_root, str(krea["version_or_commit"]), actions)
    manager = next(item for item in dependency_lock["dependencies"] if item["name"] == "ComfyUI-Manager")
    _git_checkout(str(manager["official_source"]), comfy_root / "custom_nodes" / "ComfyUI-Manager", str(manager["version_or_commit"]), actions)
    project_nodes = comfy_root / "custom_nodes" / "hoi4_portrait_nodes"
    if project_nodes.exists() and project_nodes.is_symlink():
        project_nodes.unlink()
    elif project_nodes.exists():
        raise BootstrapError(ExitCode.NODE_MISSING, f"refusing to overwrite existing custom node path: {project_nodes}")
    project_nodes.symlink_to(ROOT / "src" / "comfyui_hoi4_portrait_nodes", target_is_directory=True)
    actions.append({"action": "project_nodes_symlink", "path": str(project_nodes), "target": str(project_nodes.resolve())})
    runtime_lock = json.loads((ROOT / "dependencies" / "runtime_requirements_lock.json").read_text(encoding="utf-8"))
    python = _install_python_environment(dependency_lock, runtime_lock, actions, profile)
    _restore_models(json.loads((ROOT / "dependencies" / "models.lock.json").read_text(encoding="utf-8")), profile, actions)
    preprocessing_lock = json.loads((ROOT / "dependencies" / "preprocessing_lock.json").read_text(encoding="utf-8"))
    _restore_preprocessing_models(preprocessing_lock, actions)
    _restore_preprocessing_source_artifacts(preprocessing_lock, actions)
    lora_path = ROOT / "loras" / "hoi4_portrait_new_style_lora.safetensors"
    if not lora_path.is_file() or sha256_file(lora_path) != "2ad94552d151d2dedf151cf7356cdd3ea07677607ff289fc0ac61534b34dead1":
        raise BootstrapError(ExitCode.MODEL_CHECKSUM_MISMATCH, "immutable style LoRA is missing or changed")
    actions.append({"action": "immutable_style_lora_verified", "path": str(lora_path.relative_to(ROOT)), "sha256": sha256_file(lora_path)})
    if profile in {"local_mac_16gb", "local_nvidia_16gb"}:
        sidecar_profile = "human_local_nvidia_16gb" if profile == "local_nvidia_16gb" else "human_local_mac_16gb"
        sidecar_check = _run_checked([str(python), "-m", "portrait_pipeline.autoprompter_service", "--root", str(ROOT), "--profile", sidecar_profile, "--check-only"], ROOT)
        actions.append({"action": "autoprompter_runtime_lock_verified", "status": "PASS", "result": sidecar_check})
    _write_extra_model_paths(comfy_root, actions)
    try:
        build_workflow_artifacts(ROOT)
    except (KeyError, ValueError) as exc:
        raise BootstrapError(ExitCode.WORKFLOW_INVALID, "workflow generation failed against the locked graph contract") from exc
    actions.append({"action": "workflows_built", "status": "PASS"})
    workflow_reports = validate_all_workflows(ROOT)
    if any(report["structural_status"] != "PASS" for report in workflow_reports):
        raise BootstrapError(ExitCode.WORKFLOW_INVALID, "workflow structural validation failed after restore")
    actions.append({"action": "workflows_validated", "status": "PASS", "count": len(workflow_reports)})
    preprocessing_process, comfy_environment = _start_preprocessing_service(python, actions)
    try:
        log_path = ROOT / "logs" / "bootstrap" / "comfyui-smoke.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("ab") as log_handle:
            process = subprocess.Popen([str(python), "main.py", "--listen", "127.0.0.1", "--port", "8188"], cwd=comfy_root, env=comfy_environment, stdout=log_handle, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 120
                while time.monotonic() < deadline:
                    try:
                        client = LoopbackComfyClient(timeout=5.0)
                        client.health()
                        client.inventory()
                        actions.append({"action": "loopback_comfyui_smoke", "status": "PASS", "pid": process.pid, "binding": "http://127.0.0.1:8188"})
                        break
                    except ComfyTransportError:
                        if process.poll() is not None:
                            raise BootstrapError(ExitCode.WORKFLOW_INVALID, "ComfyUI exited before loopback smoke test completed")
                        time.sleep(1)
                else:
                    raise BootstrapError(ExitCode.WORKFLOW_INVALID, "ComfyUI loopback smoke test timed out")
            finally:
                _terminate_process(process)
    finally:
        _terminate_process(preprocessing_process)
    return actions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-closed HOI4 portrait bootstrap.")
    parser.add_argument("--profile", required=True, choices=["local_mac_16gb", "local_nvidia_16gb", "full_power_gpu", "agent_full_power_gpu"])
    parser.add_argument("--restore-from-lock", action="store_true")
    parser.add_argument(
        "--private-qualification-install",
        action="store_true",
        help=(
            "provision missing pinned runtime, node, and model inputs for a private qualification run; "
            "requires --owner-authorized-private-install and never waives production gates"
        ),
    )
    parser.add_argument(
        "--owner-authorized-private-install",
        action="store_true",
        help="record the user's explicit authorization for private Krea/model qualification copies",
    )
    args = parser.parse_args(argv)
    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    profile_name = args.profile
    if profile_name == "full_power_gpu":
        preflight_profile = "human_full_power_gpu"
    elif profile_name == "agent_full_power_gpu":
        preflight_profile = "agent_full_power_gpu"
    elif profile_name == "local_nvidia_16gb":
        preflight_profile = "agent_local_nvidia_16gb"
    else:
        preflight_profile = "agent_local_mac_16gb"
    preflight = collect_preflight(ROOT, profile=preflight_profile)
    actions: list[dict[str, Any]] = []
    qualification_allowed, qualification_refusals = _qualification_install_decision(
        preflight,
        owner_authorized=args.owner_authorized_private_install,
    )
    qualification_mode = args.private_qualification_install and qualification_allowed
    if args.private_qualification_install and not qualification_allowed:
        actions.append({"action": "qualification_installation", "status": "BLOCKED", "reasons": qualification_refusals})
    if preflight["status"] != "PASS" and not qualification_mode:
        actions.append({"action": "installation", "status": "SKIPPED_HARD_PREFLIGHT_BLOCK", "reason": " and ".join(preflight["blockers"])})
        report = _capability_report(args.profile, preflight, actions)
        output_dir = ROOT / "docs" / "capabilities"
        output_dir.mkdir(parents=True, exist_ok=True)
        public_report = sanitize_public_paths(report, ROOT)
        public_preflight = sanitize_public_paths(preflight, ROOT)
        atomic_json_write(output_dir / f"{args.profile}.json", public_report)
        (output_dir / f"{args.profile}.md").write_text(render_markdown(public_preflight), encoding="utf-8")
        _write_bootstrap_log(run_id, args.profile, actions, preflight["status"])
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return int(preflight["recommended_exit_code"])
    if not args.restore_from_lock:
        print("preflight passed but --restore-from-lock is required; no install performed", file=sys.stderr)
        _write_bootstrap_log(run_id, args.profile, [{"action": "installation", "status": "SKIPPED_RESTORE_FLAG_REQUIRED"}], "BLOCKED")
        return int(ExitCode.DEPENDENCY_MISSING)
    if profile_name in {"full_power_gpu", "agent_full_power_gpu"}:
        actions.append({"action": "cloud_bootstrap", "status": "BLOCKED_NOT_CONNECTED", "reason": "Full-power profiles execute in Comfy Cloud; local bootstrap does not download Cloud models or expose a remote runtime."})
        report = _capability_report(args.profile, preflight, actions)
        output_dir = ROOT / "docs" / "capabilities"
        output_dir.mkdir(parents=True, exist_ok=True)
        atomic_json_write(output_dir / f"{args.profile}.json", sanitize_public_paths(report, ROOT))
        (output_dir / f"{args.profile}.md").write_text(render_markdown(sanitize_public_paths(preflight, ROOT)), encoding="utf-8")
        _write_bootstrap_log(run_id, args.profile, actions, "BLOCKED")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return int(ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED)
    try:
        qualification_action = {
            "action": "qualification_installation",
            "status": "AUTHORIZED_PRIVATE_ONLY",
            "scope": "pinned local/private qualification artifacts; no production or redistribution clearance",
            "owner_authorized": True,
            "remaining_production_blockers": preflight["blockers"],
        }
        restore_actions = restore_from_lock(args.profile)
        actions = ([qualification_action] if qualification_mode else []) + restore_actions
    except BootstrapError as exc:
        actions.append({"action": "installation", "status": "FAILED", "error_code": int(exc.code), "error": str(exc)})
        return_code = int(exc.code)
    except (OSError, RuntimeError, KeyError, subprocess.SubprocessError) as exc:
        actions.append({"action": "installation", "status": "FAILED", "error_code": int(ExitCode.DEPENDENCY_MISSING), "error": str(exc)})
        return_code = int(ExitCode.DEPENDENCY_MISSING)
    else:
        return_code = 0
    report = _capability_report(args.profile, preflight, actions)
    output_dir = ROOT / "docs" / "capabilities"
    output_dir.mkdir(parents=True, exist_ok=True)
    public_report = sanitize_public_paths(report, ROOT)
    public_preflight = sanitize_public_paths(preflight, ROOT)
    atomic_json_write(output_dir / f"{args.profile}.json", public_report)
    (output_dir / f"{args.profile}.md").write_text(render_markdown(public_preflight), encoding="utf-8")
    _write_bootstrap_log(run_id, args.profile, actions, "PASS" if return_code == 0 else "FAILED")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
