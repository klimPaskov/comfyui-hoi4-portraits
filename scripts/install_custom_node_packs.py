#!/usr/bin/env python3
"""Install the pinned ComfyUI node packs required by every workflow."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class NodePack:
    name: str
    url: str
    revision: str


NODE_PACKS = (
    # Adonis_Workflow.json serializes cnr_id=gguf, ver=2.8.2. This is the
    # exact calcuis loader that provides ClipLoaderGGUF with its device input.
    NodePack(
        "gguf",
        "https://github.com/calcuis/gguf.git",
        "e802c7831507af49eefa40324eb78378eec4f3cf",
    ),
    # The selectable GGUF diffusion-model variant uses city96's loader.
    NodePack(
        "ComfyUI-GGUF",
        "https://github.com/city96/ComfyUI-GGUF.git",
        "6ea2651e7df66d7585f6ffee804b20e92fb38b8a",
    ),
    NodePack(
        "RES4LYF",
        "https://github.com/ClownsharkBatwing/RES4LYF.git",
        "26036f647ca15d3048a193daf99a40cecfc3820d",
    ),
    NodePack(
        "ComfyUi-Scale-Image-to-Total-Pixels-Advanced",
        "https://github.com/BigStationW/ComfyUi-Scale-Image-to-Total-Pixels-Advanced.git",
        "79e831097bb7a76ade3a28359300e62332086c42",
    ),
)


def _run(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def _install_requirements(requirements: Path) -> None:
    has_pip = subprocess.run(
        [sys.executable, "-c", "import pip"],
        capture_output=True,
        text=True,
    ).returncode == 0
    if has_pip:
        _run(sys.executable, "-m", "pip", "install", "-r", str(requirements))
        return
    uv = shutil.which("uv")
    if uv:
        _run(uv, "pip", "install", "--python", sys.executable, "-r", str(requirements))
        return
    raise RuntimeError(
        f"Python dependencies are required by {requirements.parent.name}, but neither pip nor uv is available."
    )


def _download_pinned_archive(destination: Path, pack: NodePack) -> None:
    """Install a GitHub revision without requiring Git on Windows."""

    archive_url = f"{pack.url.removesuffix('.git')}/archive/{pack.revision}.zip"
    with tempfile.TemporaryDirectory(prefix="hoi4-node-pack-") as directory:
        archive_path = Path(directory) / "pack.zip"
        with urllib.request.urlopen(archive_url, timeout=120) as response:
            archive_path.write_bytes(response.read())
        with zipfile.ZipFile(archive_path) as archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            roots = {Path(item.filename).parts[0] for item in members if Path(item.filename).parts}
            if len(roots) != 1:
                raise RuntimeError(f"Unexpected archive layout for {pack.name}")
            root = next(iter(roots))
            destination.mkdir(parents=True)
            for item in members:
                relative = Path(*Path(item.filename).parts[1:])
                if not relative.parts or relative.is_absolute() or ".." in relative.parts:
                    continue
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(item) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
    (destination / ".hoi4_revision").write_text(pack.revision + "\n", encoding="utf-8")


def _install_pack(custom_nodes: Path, pack: NodePack, *, skip_python_dependencies: bool) -> dict[str, str]:
    destination = custom_nodes / pack.name
    if (destination / ".git").is_dir():
        status = subprocess.run(
            ["git", "-C", str(destination), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if status:
            raise RuntimeError(
                f"{destination} has local changes. Preserve or commit them before installing the pinned revision."
            )
        _run("git", "-C", str(destination), "fetch", "--depth", "1", "origin", pack.revision)
    elif (destination / ".hoi4_revision").is_file() and (destination / ".hoi4_revision").read_text(encoding="utf-8").strip() == pack.revision:
        pass
    elif destination.exists():
        raise RuntimeError(
            f"{destination} exists but is not this installer's pinned revision. Move it aside, then rerun the installer."
        )
    elif shutil.which("git") is None:
        _download_pinned_archive(destination, pack)
    else:
        _run("git", "clone", "--filter=blob:none", "--no-checkout", pack.url, str(destination))
        _run("git", "-C", str(destination), "fetch", "--depth", "1", "origin", pack.revision)
    _run("git", "-C", str(destination), "checkout", "--detach", pack.revision)

    requirements = destination / "requirements.txt"
    if requirements.is_file() and not skip_python_dependencies:
        _install_requirements(requirements)
    return {"name": pack.name, "revision": pack.revision, "path": str(destination)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comfyui-root", required=True, type=Path)
    parser.add_argument("--skip-python-dependencies", action="store_true")
    parser.add_argument(
        "--pack",
        action="append",
        choices=[pack.name for pack in NODE_PACKS],
        default=[],
        help="Install only a named pack. Repeat for more than one; omitted installs all required packs.",
    )
    args = parser.parse_args(argv)

    comfy_root = args.comfyui_root.expanduser().resolve()
    if not (comfy_root / "main.py").is_file():
        parser.error("--comfyui-root must point to a ComfyUI checkout containing main.py")
    custom_nodes = comfy_root / "custom_nodes"
    custom_nodes.mkdir(parents=True, exist_ok=True)

    try:
        selected = [pack for pack in NODE_PACKS if not args.pack or pack.name in args.pack]
        installed = [
            _install_pack(
                custom_nodes,
                pack,
                skip_python_dependencies=args.skip_python_dependencies,
            )
            for pack in selected
        ]
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps({"status": "PASS", "node_packs": installed}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
