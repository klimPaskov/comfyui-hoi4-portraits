#!/usr/bin/env python3
"""Build a deterministic, model-free workflow release ZIP."""

from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "dist"
WINDOWS_SOURCE = ROOT / "packaging" / "windows"
RELEASE_SCHEMA_VERSION = "3.1.0"
FIXED_ZIP_TIME = (2026, 8, 4, 0, 0, 0)
ROOT_FILES = {
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "THIRD_PARTY_LICENSES.md",
    "models.json",
    "pyproject.toml",
}
INCLUDED_TREES = {"backgrounds", "custom_nodes", "docs", "loras", "prompts", "scripts", "tests", "workflows"}
IGNORED_PARTS = {"__pycache__", ".DS_Store"}
MODEL_SUFFIXES = {".bin", ".ckpt", ".gguf", ".onnx", ".pt", ".pth", ".safetensors"}
RUNPOD_SCRIPTS = {
    "apply_variant.py",
    "download_models.py",
    "install_runpod.sh",
    "install_custom_node_packs.py",
    "install_workflows.py",
    "requirements-download.txt",
    "start_runpod.sh",
    "validate_comfyui_registry.py",
}


def _selected_files() -> list[Path]:
    selected = {ROOT / name for name in ROOT_FILES}
    for tree in INCLUDED_TREES:
        selected.update(path for path in (ROOT / tree).rglob("*") if path.is_file())
    files: list[Path] = []
    for path in sorted(selected):
        relative = path.relative_to(ROOT)
        if any(part in IGNORED_PARTS for part in relative.parts) or path.suffix == ".pyc":
            continue
        if path.suffix.casefold() in MODEL_SUFFIXES:
            continue
        files.append(path)
    missing = sorted(path.relative_to(ROOT).as_posix() for path in selected if not path.is_file())
    if missing:
        raise RuntimeError(f"release inputs are missing: {', '.join(missing)}")
    manifest = json.loads((ROOT / "workflows" / "manifest.json").read_text(encoding="utf-8"))
    expected_graph_files = 2 * len(manifest.get("workflows", [])) + 1
    if len(list((ROOT / "workflows").glob("*.json"))) != expected_graph_files:
        raise RuntimeError("workflow files do not match the generated manifest")
    return files


def _build_zip(path: Path, files: list[Path], version: str) -> int:
    included_files: list[str] = []
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in files:
            relative = source.relative_to(ROOT).as_posix()
            data = source.read_bytes()
            included_files.append(relative)
            info = zipfile.ZipInfo(relative, FIXED_ZIP_TIME)
            info.create_system = 3
            mode = 0o755 if source.suffix in {".py", ".sh"} else 0o644
            info.external_attr = (mode & 0xFFFF) << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        manifest = json.dumps(
            {
                "schema_version": RELEASE_SCHEMA_VERSION,
                "version": version,
                "models_bundled": False,
                "custom_nodes_bundled": True,
                "files": included_files,
            },
            indent=2,
            sort_keys=True,
        ).encode() + b"\n"
        info = zipfile.ZipInfo("RELEASE_MANIFEST.json", FIXED_ZIP_TIME)
        info.create_system = 3
        info.external_attr = (0o644 & 0xFFFF) << 16
        archive.writestr(info, manifest, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return len(included_files)


def _runpod_files() -> dict[str, Path]:
    files: dict[str, Path] = {
        "models.json": ROOT / "models.json",
        "source_portrait.jpg": ROOT / "docs" / "assets" / "examples" / "source_portrait.jpg",
        "workflows/manifest.json": ROOT / "workflows" / "manifest.json",
    }
    for path in sorted((ROOT / "workflows").glob("*.json")):
        if not path.name.endswith(".api.json") and path.name != "manifest.json":
            files[f"workflows/{path.name}"] = path
    for path in sorted((ROOT / "backgrounds").glob("*.png")):
        files[f"backgrounds/{path.name}"] = path
    custom_node_root = ROOT / "custom_nodes" / "hoi4_portraits"
    for path in sorted(custom_node_root.rglob("*")):
        if path.is_file():
            relative = path.relative_to(custom_node_root).as_posix()
            files[f"custom_nodes/hoi4_portraits/{relative}"] = path
    for name in sorted(RUNPOD_SCRIPTS):
        files[f"scripts/{name}"] = ROOT / "scripts" / name
    missing = [archive_path for archive_path, source in files.items() if not source.is_file()]
    if missing:
        raise RuntimeError(f"RunPod package inputs are missing: {', '.join(missing)}")
    return files


def _build_runpod_archive(path: Path, files: dict[str, Path]) -> None:
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for archive_path, source in sorted(files.items()):
                    data = source.read_bytes()
                    info = tarfile.TarInfo(archive_path)
                    info.size = len(data)
                    info.mtime = 0
                    info.mode = 0o755 if source.suffix in {".py", ".sh"} else 0o644
                    archive.addfile(info, io.BytesIO(data))


def _build_windows(zip_path: Path, version: str) -> Path:
    """Cross-compile the model-free ZIP extractor for Windows x64."""
    payload = WINDOWS_SOURCE / "payload.zip"
    shutil.copy2(zip_path, payload)
    output = DIST / f"HOI4-Portrait-Workflows-{version}-windows-x64.exe"
    environment = os.environ.copy()
    environment.update({"GOOS": "windows", "GOARCH": "amd64", "CGO_ENABLED": "0"})
    try:
        subprocess.run(
            [
                "go",
                "build",
                "-trimpath",
                "-ldflags",
                f"-s -w -X main.version={version}",
                "-o",
                str(output),
                ".",
            ],
            cwd=WINDOWS_SOURCE,
            env=environment,
            check=True,
        )
    finally:
        payload.unlink(missing_ok=True)
    if output.read_bytes()[:2] != b"MZ":
        raise RuntimeError("Windows release is not a PE executable")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    args = parser.parse_args(argv)
    version = args.version.strip()
    if not version or not all(character.isalnum() or character in "._-" for character in version):
        parser.error("version contains unsupported characters")
    DIST.mkdir(exist_ok=True)
    for stale in DIST.iterdir():
        if stale.is_file() and (
            stale.name.startswith("HOI4-Portrait-Workflows-")
            or stale.name.startswith("HOI4-Portrait-RunPod")
        ):
            stale.unlink()
    zip_path = DIST / f"HOI4-Portrait-Workflows-{version}.zip"
    file_count = _build_zip(zip_path, _selected_files(), version)
    windows_path = _build_windows(zip_path, version)
    runpod_path = DIST / "HOI4-Portrait-RunPod.tar.gz"
    _build_runpod_archive(runpod_path, _runpod_files())
    artifacts = [zip_path, windows_path, runpod_path]
    print(
        json.dumps(
            {
                "status": "PASS",
                "version": version,
                "file_count": file_count,
                "artifacts": [
                    {"path": str(path), "size_bytes": path.stat().st_size}
                    for path in artifacts
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
