#!/usr/bin/env python3
"""Install the workflows and sample inputs into an existing ComfyUI."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and destination.read_bytes() == source.read_bytes():
        return
    shutil.copy2(source, destination)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comfyui-root", required=True, type=Path)
    args = parser.parse_args(argv)
    comfy_root = args.comfyui_root.expanduser().resolve()
    if not (comfy_root / "main.py").is_file():
        parser.error("--comfyui-root must point to a ComfyUI checkout containing main.py")
    manifest = json.loads((ROOT / "workflows" / "manifest.json").read_text(encoding="utf-8"))
    workflow_destination = comfy_root / "user" / "default" / "workflows" / "hoi4_portraits"
    installed = []
    for item in manifest["workflows"]:
        source = ROOT / item["workflow_json"]
        destination = workflow_destination / source.name
        _copy(source, destination)
        installed.append(str(destination))
    for background in sorted((ROOT / "backgrounds").glob("*.png")):
        _copy(background, comfy_root / "input" / background.name)
    sample_source = ROOT / "source_portrait.jpg"
    if not sample_source.is_file():
        sample_source = ROOT / "docs" / "assets" / "examples" / "source_portrait.jpg"
    _copy(sample_source, comfy_root / "input" / "source_portrait.jpg")
    custom_node_source = ROOT / "custom_nodes" / "hoi4_portraits"
    custom_node_destination = comfy_root / "custom_nodes" / "hoi4_portraits"
    legacy_custom_node = comfy_root / "custom_nodes" / "adaptive_portrait_crop"
    if legacy_custom_node.is_dir():
        shutil.rmtree(legacy_custom_node)
    for source in sorted(custom_node_source.iterdir()):
        if source.is_file():
            _copy(source, custom_node_destination / source.name)
    print(
        json.dumps(
            {
                "status": "PASS",
                "workflows": installed,
                "custom_nodes_installed": [str(custom_node_destination)],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
