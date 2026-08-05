#!/usr/bin/env python3
"""Verify that a running ComfyUI exposes every node and sampler we use."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request


REQUIRED_NODE_TYPES = {
    "AdaptivePortraitCrop",
    "CLIPLoader",
    "CLIPTextEncode",
    "ComfySwitchNode",
    "CropByBBoxes",
    "EmptyFlux2LatentImage",
    "Flux2PortraitSampler",
    "ImageCompositeMasked",
    "ImageScale",
    "ImageScaleToMaxDimension",
    "ImageUpscaleWithModel",
    "LoadBackgroundRemovalModel",
    "LoadImage",
    "LoadMediaPipeFaceLandmarker",
    "LoraLoaderModelOnly",
    "MediaPipeFaceLandmarker",
    "PreviewImage",
    "PrimitiveBoundingBox",
    "ReferenceLatent",
    "RemoveBackground",
    "SaveImage",
    "UNETLoader",
    "UpscaleModelLoader",
    "VAEDecode",
    "VAEEncode",
    "VAELoader",
}
REQUIRED_SAMPLERS = {"euler", "res_2s", "res_2m"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8188")
    args = parser.parse_args()
    endpoint = args.url.rstrip("/") + "/object_info"
    try:
        with urllib.request.urlopen(endpoint, timeout=30) as response:
            object_info = json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not read the ComfyUI node registry at {endpoint}: {exc}")

    missing_nodes = sorted(REQUIRED_NODE_TYPES - set(object_info))
    sampler_info = object_info.get("KSamplerSelect", {}).get("input", {}).get("required", {}).get("sampler_name")
    sampler_options: set[str] = set()
    if isinstance(sampler_info, list) and len(sampler_info) > 1 and isinstance(sampler_info[1], dict):
        sampler_options = set(sampler_info[1].get("options", []))
    missing_samplers = sorted(REQUIRED_SAMPLERS - sampler_options)

    if missing_nodes or missing_samplers:
        if missing_nodes:
            print("Missing workflow nodes: " + ", ".join(missing_nodes))
        if missing_samplers:
            print("Missing samplers: " + ", ".join(missing_samplers))
        print("ComfyUI must be restarted after running install_runpod.sh.")
        return 1
    print("Validated the live ComfyUI registry: all workflow nodes and samplers are available.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
