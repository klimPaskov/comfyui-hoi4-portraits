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
    ".gitignore",
    "LICENSE",
    "README.md",
    "SETUP_WITH_CODING_AGENT.md",
    "pyproject.toml",
    "config/background_registry.template.json",
    "config/identity_thresholds.template.json",
    "docs/runpod.md",
    "docs/contracts-and-safety.md",
    "docs/getting-started.md",
    "docs/licensing-and-public-repository.md",
    "docs/testing-and-evidence.md",
    "docs/workflows.md",
    "loras/HUGGINGFACE_MODEL_CARD.md",
    "loras/README.md",
    "scripts/__init__.py",
    "scripts/audit_candidate.py",
    "scripts/bootstrap/__init__.py",
    "scripts/bootstrap/bootstrap.py",
    "scripts/install_into_existing_comfyui.py",
    "scripts/install_runpod.sh",
    "scripts/install_windows.ps1",
    "scripts/start_runpod.sh",
    "scripts/start_windows.ps1",
    "scripts/produce_visual_audit.py",
}
INCLUDED_TREES = {
    "dependencies",
    "docs/examples",
    "prompts",
    "schemas",
    "scripts/preflight",
    "src",
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
            if not (relative.parts[:2] == ("docs", "assets") and path.suffix.casefold() in {".png", ".jpg", ".jpeg"}):
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
    files = _selected_files()
    zip_path = DIST / f"HOI4-Portrait-Workflows-{version}.zip"
    _write_zip(zip_path, files, version)
    windows_path = _build_windows(zip_path, version)
    artifacts = [zip_path, windows_path]
    sums_path = DIST / "SHA256SUMS.txt"
    sums_payload = "".join(f"{_sha256(path)}  {path.name}\n" for path in artifacts).encode("utf-8")
    sums_path.write_bytes(sums_payload)
    if b"\r" in sums_path.read_bytes():
        raise RuntimeError("release checksum file must use portable LF line endings")
    print(json.dumps({
        "status": "PASS",
        "version": version,
        "comfyui_bundled": False,
        "models_bundled": False,
        "file_count": len(files),
        "artifacts": [{"path": str(path), "size_bytes": path.stat().st_size, "sha256": _sha256(path)} for path in artifacts],
        "checksums": str(sums_path),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
