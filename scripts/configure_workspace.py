#!/usr/bin/env python3
"""Connect ComfyUI's portrait folders to the selected input and output workspace."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path


def _verify_merge(source: Path, destination: Path) -> None:
    if not destination.exists():
        return
    if source.is_dir() and destination.is_dir():
        for child in source.iterdir():
            _verify_merge(child, destination / child.name)
        return
    if source.is_file() and destination.is_file() and source.read_bytes() == destination.read_bytes():
        return
    raise RuntimeError(f"Cannot merge different files at {destination}")


def _merge(source: Path, destination: Path) -> None:
    if not destination.exists():
        shutil.move(str(source), str(destination))
        return
    if source.is_dir():
        for child in list(source.iterdir()):
            _merge(child, destination / child.name)
        source.rmdir()
        return
    source.unlink()


def _link_directory(link: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    link.parent.mkdir(parents=True, exist_ok=True)
    link_path = link.absolute()
    destination_path = destination.absolute()
    if link_path == destination_path:
        return
    if link_path in destination_path.parents or destination_path in link_path.parents:
        raise RuntimeError(f"Linked folder and selected folder cannot contain each other: {link} and {destination}")
    if link.exists() and os.path.samefile(link, destination):
        return
    attributes = getattr(os.lstat(link), "st_file_attributes", 0) if link.exists() else 0
    is_junction = bool(getattr(link, "is_junction", lambda: False)()) or bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0) and not link.is_symlink())
    if link.is_symlink() or is_junction:
        if link.resolve() == destination.resolve():
            return
        if is_junction:
            link.rmdir()
        else:
            link.unlink()
    elif link.exists():
        if not link.is_dir():
            raise RuntimeError(f"Expected a directory at {link}")
        _verify_merge(link, destination)
        _merge(link, destination)
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(destination)], check=True, capture_output=True, text=True)
    else:
        link.symlink_to(destination, target_is_directory=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comfyui-root", required=True, type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    comfy_root = args.comfyui_root.expanduser().resolve()
    runtime_root = args.runtime_root.expanduser().resolve() if args.runtime_root else None
    if not (comfy_root / "main.py").is_file():
        parser.error("--comfyui-root must point to a ComfyUI checkout containing main.py")
    if runtime_root is None and (args.input_dir is None or args.output_dir is None):
        parser.error("provide --runtime-root or both --input-dir and --output-dir")
    input_dir = args.input_dir.expanduser().resolve() if args.input_dir else runtime_root / "input"
    output_dir = args.output_dir.expanduser().resolve() if args.output_dir else runtime_root / "output"
    for relative in ("1024x1365", "1024x1365/processed", "1024x1365/restored", "156x210", "156x210/dds"):
        (output_dir / relative).mkdir(parents=True, exist_ok=True)
    _link_directory(comfy_root / "input" / "hoi4_portraits_batch", input_dir)
    _link_directory(comfy_root / "output" / "hoi4_portraits", output_dir)
    print(json.dumps({"status": "PASS", "batch_input": str(input_dir), "portrait_output": str(output_dir)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
