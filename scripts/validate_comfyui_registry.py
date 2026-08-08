#!/usr/bin/env python3
"""Verify that a running ComfyUI exposes every node and sampler we use.

The required node set is derived from the installed workflows in
``user/default/workflows/hoi4_portraits``, so it automatically covers the
full, fp8, and GGUF variants (``UnetLoaderGGUF`` is only required when a GGUF
workflow copy was installed).  Frontend-only ``Note`` cards are ignored.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Nodes every workflow depends on that are never serialized in the API graph
# (the API graph skips them, but the editor still needs them).
ALWAYS_REQUIRED = {
    "AdaptivePortraitCrop",
    "Hoi4BatchInput",
    "Hoi4PortraitSampler",
    "Hoi4SaveDDS",
    "PortraitIdentityMask",
}

FRONTEND_ONLY = {"Note"}


def _workflow_node_types(comfy_root: Path) -> set[str]:
    required: set[str] = set(ALWAYS_REQUIRED)
    workflow_dir = comfy_root / "user" / "default" / "workflows" / "hoi4_portraits"
    if not workflow_dir.is_dir():
        return required
    for path in workflow_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if path.name.endswith(".api.json"):
            nodes = data.values()
            for node in nodes:
                if isinstance(node, dict) and "class_type" in node:
                    required.add(str(node["class_type"]))
        else:
            for node in data.get("nodes", []):
                class_type = str(node.get("type", ""))
                if class_type not in FRONTEND_ONLY:
                    required.add(class_type)
    return required


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8188")
    parser.add_argument("--comfyui-root", type=Path, default=None)
    args = parser.parse_args()

    comfy_root = args.comfyui_root or ROOT / "comfyui"
    required_nodes = _workflow_node_types(comfy_root.resolve())
    endpoint = args.url.rstrip("/") + "/object_info"
    try:
        with urllib.request.urlopen(endpoint, timeout=30) as response:
            object_info = json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not read the ComfyUI node registry at {endpoint}: {exc}")

    missing_nodes = sorted(required_nodes - set(object_info))
    sampler_info = object_info.get("KSamplerSelect", {}).get("input", {}).get("required", {}).get("sampler_name")
    sampler_options: set[str] = set()
    if isinstance(sampler_info, list) and len(sampler_info) > 1 and isinstance(sampler_info[1], dict):
        sampler_options = set(sampler_info[1].get("options", []))
    missing_samplers = sorted({"euler"} - sampler_options)
    scheduler_info = object_info.get("KSamplerSelect", {}).get("input", {}).get("required", {}).get("scheduler")
    scheduler_options: set[str] = set()
    if isinstance(scheduler_info, list) and len(scheduler_info) > 1 and isinstance(scheduler_info[1], dict):
        scheduler_options = set(scheduler_info[1].get("options", []))
    missing_schedulers = sorted({"simple"} - scheduler_options)

    if missing_nodes or missing_samplers or missing_schedulers:
        if missing_nodes:
            print("Missing workflow nodes: " + ", ".join(missing_nodes))
        if missing_samplers:
            print("Missing samplers: " + ", ".join(missing_samplers))
        if missing_schedulers:
            print("Missing schedulers: " + ", ".join(missing_schedulers))
        print("ComfyUI must be restarted after running the installer.")
        return 1
    print("Validated the live ComfyUI registry: all workflow nodes and samplers are available.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
