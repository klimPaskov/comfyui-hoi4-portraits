#!/usr/bin/env python3
"""Build a deterministic, model-free workflow release ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "dist"
FIXED_ZIP_TIME = (2026, 8, 2, 0, 0, 0)
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
INCLUDED_TREES = {"backgrounds", "docs", "loras", "prompts", "scripts", "tests", "workflows"}
IGNORED_PARTS = {"__pycache__", ".DS_Store"}
MODEL_SUFFIXES = {".bin", ".ckpt", ".gguf", ".onnx", ".pt", ".pth", ".safetensors"}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
    if len(list((ROOT / "workflows").glob("*.json"))) != 7:
        raise RuntimeError("expected three editor graphs, three API graphs, and one manifest")
    return files


def _build_zip(path: Path, files: list[Path], version: str) -> dict[str, str]:
    checksums: dict[str, str] = {}
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in files:
            relative = source.relative_to(ROOT).as_posix()
            data = source.read_bytes()
            checksums[relative] = _sha256(data)
            info = zipfile.ZipInfo(relative, FIXED_ZIP_TIME)
            info.create_system = 3
            mode = 0o755 if source.suffix in {".py", ".sh"} else 0o644
            info.external_attr = (mode & 0xFFFF) << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        manifest = json.dumps(
            {
                "schema_version": "2.2.0",
                "version": version,
                "models_bundled": False,
                "custom_nodes_bundled": False,
                "files": checksums,
            },
            indent=2,
            sort_keys=True,
        ).encode() + b"\n"
        info = zipfile.ZipInfo("RELEASE_MANIFEST.json", FIXED_ZIP_TIME)
        info.create_system = 3
        info.external_attr = (0o644 & 0xFFFF) << 16
        archive.writestr(info, manifest, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return checksums


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    args = parser.parse_args(argv)
    version = args.version.strip()
    if not version or not all(character.isalnum() or character in "._-" for character in version):
        parser.error("version contains unsupported characters")
    DIST.mkdir(exist_ok=True)
    zip_path = DIST / f"HOI4-Portrait-Workflows-{version}.zip"
    checksums = _build_zip(zip_path, _selected_files(), version)
    digest = _sha256(zip_path.read_bytes())
    sums_path = DIST / "SHA256SUMS.txt"
    sums_path.write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "PASS",
                "version": version,
                "file_count": len(checksums),
                "artifacts": [
                    {"path": str(zip_path), "size_bytes": zip_path.stat().st_size, "sha256": digest},
                    {"path": str(sums_path), "size_bytes": sums_path.stat().st_size},
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
