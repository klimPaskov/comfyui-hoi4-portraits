#!/usr/bin/env python3
"""Build a user-facing ZIP and Windows self-extractor."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "dist"
WINDOWS_SOURCE = ROOT / "packaging" / "windows"
FIXED_ZIP_TIME = (2026, 7, 29, 0, 0, 0)
FORBIDDEN_SUFFIXES = {
    ".safetensors", ".gguf", ".ckpt", ".pt", ".pth", ".bin", ".onnx",
    ".jpg", ".jpeg", ".webp", ".dds", ".psd", ".mp4", ".mov",
}
FORBIDDEN_PARTS = {
    ".git", ".venv", "__pycache__", "models", "jobs", "outputs", "evidence",
    "logs", ".runtime", "private", "source",
}
EXCLUDED_FILES = {
    "prompts/implementation_goal_prompt.md",
}
EXPLICIT_FILES = {
    "LICENSE",
    "README.md",
    "docs/setup-with-coding-agent.md",
    "backgrounds/README.md",
    "config/background_registry.json",
    "config/background_registry.template.json",
    "docs/runpod.md",
    "docs/getting-started.md",
    "docs/workflows.md",
    "dependencies/autoprompter_runtime.lock.json",
    "dependencies/custom_nodes.lock.json",
    "dependencies/models.lock.json",
    "dependencies/preprocessing_lock.json",
    "dependencies/runpod_sidecar_requirements.lock.txt",
    "dependencies/licenses/krea2-community-license.source.md",
    "dependencies/licenses/qwen-image-edit-2511.source.md",
    "loras/HUGGINGFACE_MODEL_CARD.md",
    "loras/README.md",
    "prompts/autoprompter_instruction.txt",
    "prompts/install_into_existing_comfyui_agent_prompt.md",
    "prompts/random_portrait_instruction.txt",
    "docs/schemas/portrait_job_input.schema.json",
    "docs/schemas/portrait_prompt_job_input.schema.json",
    "scripts/__init__.py",
    "scripts/install_support.py",
    "scripts/install_into_existing_comfyui.py",
    "scripts/install_runpod.sh",
    "scripts/install_windows.ps1",
    "scripts/start_runpod.sh",
    "scripts/start_windows.ps1",
    "src/comfyui_hoi4_portrait_nodes/__init__.py",
    "src/comfyui_hoi4_portrait_nodes/nodes.py",
    "src/portrait_pipeline/__init__.py",
    "src/portrait_pipeline/autoprompter_service.py",
    "src/portrait_pipeline/constants.py",
    "src/portrait_pipeline/contracts.py",
    "src/portrait_pipeline/preprocessing_service.py",
    "src/portrait_pipeline/prompt.py",
    "src/portrait_pipeline/util.py",
}
INCLUDED_TREES = {
    "docs/assets",
    "docs/examples",
    "workflows",
}


def _selected_files() -> list[Path]:
    selected = {ROOT / relative for relative in EXPLICIT_FILES}
    for tree in INCLUDED_TREES:
        selected.update(path for path in (ROOT / tree).rglob("*") if path.is_file())
    files: list[Path] = []
    for path in sorted(selected):
        if not path.is_file():
            raise RuntimeError(f"release input is missing: {path.relative_to(ROOT)}")
        relative = path.relative_to(ROOT)
        if relative.as_posix() in EXCLUDED_FILES or any(part.endswith(".egg-info") for part in relative.parts):
            continue
        if any(part in FORBIDDEN_PARTS for part in relative.parts):
            continue
        if path.suffix.casefold() in FORBIDDEN_SUFFIXES:
            documentation_image = relative.parts[:2] == ("docs", "assets") and path.suffix.casefold() in {".png", ".jpg", ".jpeg"}
            if not documentation_image:
                raise RuntimeError(f"forbidden release artifact selected: {relative}")
        if path.suffix == ".pyc" or ".DS_Store" in relative.parts:
            continue
        files.append(path)
    if not any(path.relative_to(ROOT).as_posix().startswith("workflows/human/") for path in files):
        raise RuntimeError("human workflows are missing from the release package")
    if not any(path.relative_to(ROOT).as_posix().startswith("workflows/agent/") for path in files):
        raise RuntimeError("agent workflows are missing from the release package")
    return files


def _write_zip(path: Path, files: list[Path], version: str) -> dict[str, str]:
    manifest: dict[str, str] = {}
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in files:
            relative = source.relative_to(ROOT).as_posix()
            data = source.read_bytes()
            manifest[relative] = hashlib.sha256(data).hexdigest()
            info = zipfile.ZipInfo(relative, FIXED_ZIP_TIME)
            info.create_system = 3
            info.external_attr = (0o644 & 0xFFFF) << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        release_manifest = json.dumps({
            "schema_version": "1.0.0",
            "version": version,
            "comfyui_bundled": False,
            "models_bundled": False,
            "private_artifacts_bundled": False,
            "files": manifest,
        }, indent=2, sort_keys=True).encode("utf-8") + b"\n"
        info = zipfile.ZipInfo("RELEASE_MANIFEST.json", FIXED_ZIP_TIME)
        info.create_system = 3
        info.external_attr = (0o644 & 0xFFFF) << 16
        archive.writestr(info, release_manifest, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return manifest


def _run(command: list[str], *, cwd: Path = ROOT, environment: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=cwd, env=environment, check=True)


def _build_windows(zip_path: Path, version: str) -> Path:
    payload = WINDOWS_SOURCE / "payload.zip"
    shutil.copy2(zip_path, payload)
    output = DIST / f"HOI4-Portrait-Workflows-{version}-windows-x64.exe"
    environment = os.environ.copy()
    environment.update({"GOOS": "windows", "GOARCH": "amd64", "CGO_ENABLED": "0"})
    try:
        _run([
            "go", "build", "-trimpath",
            "-ldflags", f"-s -w -X main.version={version}",
            "-o", str(output), ".",
        ], cwd=WINDOWS_SOURCE, environment=environment)
    finally:
        payload.unlink(missing_ok=True)
    if output.read_bytes()[:2] != b"MZ":
        raise RuntimeError("Windows release is not a PE executable")
    return output


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    args = parser.parse_args(argv)
    version = args.version.strip()
    if not version or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for character in version):
        raise SystemExit("version contains unsupported characters")
    DIST.mkdir(parents=True, exist_ok=True)
    for stale in DIST.iterdir():
        if stale.is_file() and (
            stale.name.startswith("HOI4-Portrait-Workflows-")
            or stale.name == "SHA256SUMS.txt"
        ):
            stale.unlink()
    files = _selected_files()
    zip_path = DIST / f"HOI4-Portrait-Workflows-{version}.zip"
    _write_zip(zip_path, files, version)
    windows_path = _build_windows(zip_path, version)
    artifacts = [zip_path, windows_path]
    print(json.dumps({
        "status": "PASS",
        "version": version,
        "comfyui_bundled": False,
        "models_bundled": False,
        "file_count": len(files),
        "artifacts": [{"path": str(path), "size_bytes": path.stat().st_size, "sha256": _sha256(path)} for path in artifacts],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
