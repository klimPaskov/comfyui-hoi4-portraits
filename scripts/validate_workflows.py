#!/usr/bin/env python3
"""Validate the public HOI4 workflow graphs and their editor layout."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE_MODEL = "flux-2-klein-9b.safetensors"
STYLE_LORA = "hoi4_portrait_flux2_klein_9b_lora_000002500.safetensors"
DEFAULT_STEPS = 4
DEFAULT_CFG = 1.0
DEFAULT_GUIDANCE = 1.0
CANVAS_WIDTH = 1024
CANVAS_HEIGHT = 1365
GAME_WIDTH = 156
GAME_HEIGHT = 210
LAYOUT_NODE_PADDING = 16
GROUP_NODE_PADDING = 24

ALLOWED_NODES = {
    "AdaptivePortraitCrop",
    "ComfySwitchNode",
    "CropByBBoxes",
    "Hoi4BatchInput",
    "Hoi4PortraitSampler",
    "Hoi4SaveDDS",
    "ImageCompositeMasked",
    "ImageScale",
    "ImageScaleToMaxDimension",
    "ImageUpscaleWithModel",
    "LoadBackgroundRemovalModel",
    "LoadImage",
    "LoadMediaPipeFaceLandmarker",
    "LoraLoaderModelOnly",
    "MediaPipeFaceLandmarker",
    "Note",
    "PreviewImage",
    "PrimitiveBoolean",
    "PrimitiveBoundingBox",
    "RemoveBackground",
    "SaveImage",
    "UNETLoader",
    "UpscaleModelLoader",
    "VAEDecode",
    "VAEEncode",
    "VAELoader",
    "CLIPLoader",
    "CLIPTextEncode",
    "EmptyFlux2LatentImage",
    "ReferenceLatent",
    "ComfySwitchNode",
}


def _non_person_prompt_terms(prompt: str) -> list[str]:
    """Keep the public helper used by the project's documentation tests."""

    forbidden = {
        "hearts of iron": r"\bhearts of iron\b",
        "grand-strategy": r"\bgrand-strategy\b",
        "background": r"\bbackground\b",
        "palette": r"\bpalette\b",
        "lighting": r"\blighting\b",
        "preserve": r"\bpreserv(?:e|ation)\b",
        "do not": r"\bdo not\b",
    }
    return sorted(label for label, pattern in forbidden.items() if re.search(pattern, prompt.casefold()))


def _overlap(a: list[float], b: list[float], *, padding: float = 0) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (
        ax + aw + padding <= bx
        or bx + bw + padding <= ax
        or ay + ah + padding <= by
        or by + bh + padding <= ay
    )


def _ancestors(api: dict[str, Any], node_id: str) -> set[str]:
    found: set[str] = set()
    pending = [node_id]
    while pending:
        current = pending.pop()
        for value in api.get(current, {}).get("inputs", {}).values():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and value[0] not in found:
                found.add(value[0])
                pending.append(value[0])
    return found


def _validate_ui(path: Path, ui: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    nodes = ui.get("nodes")
    links = ui.get("links")
    groups = ui.get("groups")
    if not isinstance(nodes, list) or not nodes:
        return [f"{path}: nodes must be a non-empty list"]
    if not isinstance(links, list):
        errors.append(f"{path}: links must be a list")
    if not isinstance(groups, list) or not groups:
        errors.append(f"{path}: groups must be a non-empty list")
    if ui.get("definitions"):
        errors.append(f"{path}: workflow stages must remain visible on the main canvas")

    by_id = {node.get("id"): node for node in nodes}
    if len(by_id) != len(nodes) or None in by_id:
        errors.append(f"{path}: node ids must be present and unique")

    link_by_id: dict[int, list[Any]] = {}
    for link in links or []:
        if not isinstance(link, list) or len(link) != 6:
            errors.append(f"{path}: malformed link {link!r}")
            continue
        link_id, source_id, source_slot, target_id, target_slot, link_type = link
        if link_id in link_by_id:
            errors.append(f"{path}: duplicate link id {link_id}")
        link_by_id[link_id] = link
        source = by_id.get(source_id)
        target = by_id.get(target_id)
        if source is None or target is None:
            errors.append(f"{path}: link {link_id} has a missing endpoint")
            continue
        outputs = source.get("outputs", [])
        inputs = target.get("inputs", [])
        if not isinstance(source_slot, int) or not 0 <= source_slot < len(outputs):
            errors.append(f"{path}: link {link_id} has an invalid source slot")
        elif outputs[source_slot].get("type") != link_type:
            errors.append(f"{path}: link {link_id} source type mismatch")
        if not isinstance(target_slot, int) or not 0 <= target_slot < len(inputs):
            errors.append(f"{path}: link {link_id} has an invalid target slot")
        elif inputs[target_slot].get("type") not in {link_type, "IMAGE", "COMFY_MATCHTYPE_V3"}:
            errors.append(f"{path}: link {link_id} target type mismatch")

    for node in nodes:
        class_type = str(node.get("type", ""))
        if class_type not in ALLOWED_NODES:
            errors.append(f"{path}: unapproved node {class_type!r}")
        if "krea" in class_type.casefold() or "identity" in class_type.casefold() or "pulid" in class_type.casefold():
            errors.append(f"{path}: obsolete identity/Krea node {class_type!r}")
        if node.get("mode") != 0:
            errors.append(f"{path}: node {node.get('id')} is unexpectedly bypassed")
        for input_item in node.get("inputs", []):
            if input_item.get("link") is not None and input_item["link"] not in link_by_id:
                errors.append(f"{path}: node {node.get('id')} references a missing input link")
        for output in node.get("outputs", []):
            for output_link in output.get("links") or []:
                if output_link not in link_by_id:
                    errors.append(f"{path}: node {node.get('id')} references a missing output link")

    group_bounds = {group.get("title"): group.get("bounding") for group in groups or []}
    for index, group in enumerate(groups or []):
        bounds = group.get("bounding")
        if not (isinstance(bounds, list) and len(bounds) == 4):
            errors.append(f"{path}: group {group.get('title')} has invalid bounds")
            continue
        for other in (groups or [])[index + 1 :]:
            other_bounds = other.get("bounding")
            if isinstance(other_bounds, list) and len(other_bounds) == 4 and _overlap(bounds, other_bounds):
                errors.append(f"{path}: groups overlap: {group.get('title')} and {other.get('title')}")

    for node in nodes:
        group_name = node.get("properties", {}).get("hoi4_group")
        bounds = group_bounds.get(group_name)
        if bounds is None:
            errors.append(f"{path}: node {node.get('id')} has no valid group")
            continue
        nx, ny = node.get("pos", [0, 0])
        nw, nh = node.get("size", [0, 0])
        gx, gy, gw, gh = bounds
        if nx < gx + GROUP_NODE_PADDING or ny < gy + GROUP_NODE_PADDING or nx + nw > gx + gw - GROUP_NODE_PADDING or ny + nh > gy + gh - GROUP_NODE_PADDING:
            errors.append(f"{path}: node {node.get('id')} extends outside group {group_name}")

    for index, node in enumerate(nodes):
        a = [*node.get("pos", [0, 0]), *node.get("size", [0, 0])]
        for other in nodes[index + 1 :]:
            b = [*other.get("pos", [0, 0]), *other.get("size", [0, 0])]
            if _overlap(a, b, padding=LAYOUT_NODE_PADDING):
                errors.append(f"{path}: nodes overlap or have insufficient gutter: {node.get('id')} and {other.get('id')}")
    return errors


def _validate_api(path: Path, api: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not api:
        return [f"{path}: API graph is empty"]
    for node_id, node in api.items():
        if not node_id.isdigit() or not isinstance(node, dict):
            errors.append(f"{path}: invalid API node key {node_id!r}")
            continue
        class_type = str(node.get("class_type", ""))
        if class_type not in ALLOWED_NODES:
            errors.append(f"{path}: API graph uses unapproved node {class_type!r}")
        for value in node.get("inputs", {}).values():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and value[0] not in api:
                errors.append(f"{path}: node {node_id} references missing node {value[0]}")
    if not any(node.get("class_type") in {"SaveImage", "Hoi4SaveDDS"} for node in api.values()):
        errors.append(f"{path}: graph has no output node")
    return errors


def _validate_policy(path: Path, ui: dict[str, Any], api: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    extra = ui.get("extra", {})
    workflow_id = str(extra.get("workflow_id", ""))
    is_processing = workflow_id == "hoi4_portrait_processing_only"
    is_text = workflow_id.endswith("text_to_image")
    is_batch = workflow_id == "hoi4_portrait_batch"
    if extra.get("base_model") != BASE_MODEL or BASE_MODEL in {"flux-2-klein-base-9b-fp8.safetensors", "flux-2-klein-base-9b.safetensors"}:
        errors.append(f"{path}: only the distilled FLUX.2 Klein 9B model is allowed")
    if "base" in str(extra.get("base_model", "")).casefold():
        errors.append(f"{path}: base FLUX model was selected")
    if is_processing and extra.get("style_lora") is not None:
        errors.append(f"{path}: processing workflow must not advertise a style LoRA")
    if not is_processing and extra.get("style_lora") != STYLE_LORA:
        errors.append(f"{path}: workflow must use the 2500-step LoRA")
    if extra.get("master_size") != [CANVAS_WIDTH, CANVAS_HEIGHT] or extra.get("game_size") != [GAME_WIDTH, GAME_HEIGHT]:
        errors.append(f"{path}: output dimensions are incorrect")
    for node_id, node in api.items():
        if node.get("class_type") == "LoraLoaderModelOnly" and str(node.get("inputs", {}).get("lora_name", "")).startswith("hoi4_portrait"):
            if node.get("inputs", {}).get("lora_name") != STYLE_LORA or node.get("inputs", {}).get("strength_model") != 1.0:
                errors.append(f"{path}: style LoRA must be 2500 at strength 1.00")
    restoration_loaders = [node for node in api.values() if node.get("class_type") == "LoraLoaderModelOnly" and node.get("inputs", {}).get("lora_name") in {"adonis_base.safetensors", "adonis_post.safetensors"}]
    if is_text and restoration_loaders:
        errors.append(f"{path}: text-to-image must not load Adonis")
    if not is_text and not is_processing and not is_batch and len(restoration_loaders) != 2:
        errors.append(f"{path}: source workflow must load Adonis Base and Post")
    if is_processing or is_batch:
        if len(restoration_loaders) != 2:
            errors.append(f"{path}: restoration workflow must load Adonis Base and Post")

    samplers = [node for node in api.values() if node.get("class_type") == "Hoi4PortraitSampler"]
    expected_count = 1 if is_text else 2 if is_processing else 3 if is_batch else 5
    if len(samplers) != expected_count:
        errors.append(f"{path}: expected {expected_count} merged sampler cards, found {len(samplers)}")
    for sampler in samplers:
        inputs = sampler.get("inputs", {})
        for name, expected in (("steps", DEFAULT_STEPS), ("cfg", DEFAULT_CFG), ("guidance", DEFAULT_GUIDANCE), ("sampling_algorithm", "euler"), ("scheduler", "simple"), ("denoise", 1.0)):
            if inputs.get(name) != expected:
                errors.append(f"{path}: sampler {name} must default to {expected!r}")
    if is_batch and extra.get("batch_sampler_count") != 1:
        errors.append(f"{path}: batch metadata must advertise one sampler")
    if not is_processing and not is_batch and not is_text:
        prompt = str(api.get("40", {}).get("inputs", {}).get("text", ""))
        if prompt != "make this portrait hoi4_portrait style":
            errors.append(f"{path}: source prompt is not the exact editable default")
    if is_text and api.get("20", {}).get("inputs", {}).get("text") != "hoi4_portrait, an Irish middle-aged man with neatly combed dark hair, wearing a plain civilian jacket.":
        errors.append(f"{path}: text-to-image prompt is not the documented example")
    if any(node.get("class_type") == "ImageScale" and node.get("inputs", {}).get("crop") == "stretch" for node in api.values()):
        errors.append(f"{path}: output scaling must not stretch")
    output_prefixes = [str(node.get("inputs", {}).get("filename_prefix", "")) for node in api.values() if node.get("class_type") in {"SaveImage", "Hoi4SaveDDS"}]
    for folder in ("1024x1365/", "156x210/", "156x210/dds/"):
        if not any(prefix.startswith(folder) for prefix in output_prefixes):
            errors.append(f"{path}: missing output folder {folder}")
    if not any(node.get("class_type") == "Hoi4SaveDDS" for node in api.values()):
        errors.append(f"{path}: missing HOI4 DDS output node")
    needs_processing_preview = not is_text
    if needs_processing_preview and not any(node.get("class_type") == "PreviewImage" and "crop + ESRGAN" in str(node.get("_meta", {}).get("title", "")) for node in api.values()):
        errors.append(f"{path}: missing crop + ESRGAN preview")
    for node in api.values():
        if node.get("class_type") == "ComfySwitchNode" and "restoration" in str(node.get("_meta", {}).get("title", "")).casefold():
            if node.get("inputs", {}).get("switch") is not True:
                errors.append(f"{path}: restoration toggle must be enabled by default")
    if is_batch and not any(node.get("class_type") == "Hoi4BatchInput" for node in api.values()):
        errors.append(f"{path}: batch graph needs the folder input node")
    return errors


def validate_all(root: Path = ROOT) -> dict[str, Any]:
    workflow_dir = root / "workflows"
    errors: list[str] = []
    try:
        manifest = json.loads((workflow_dir / "manifest.json").read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "FAIL", "errors": [f"{workflow_dir / 'manifest.json'}: {exc}"], "workflows": []}
    items = manifest.get("workflows", [])
    expected_ids = {
        "hoi4_portrait_flux2_klein_9b_source",
        "hoi4_portrait_flux2_klein_9b_text_to_image",
        "hoi4_portrait_processing_only",
        "hoi4_portrait_batch",
    }
    if {item.get("workflow_id") for item in items} != expected_ids:
        errors.append(f"{workflow_dir / 'manifest.json'}: exactly four default workflows are required")
    reports: list[dict[str, Any]] = []
    for item in items:
        ui_path = root / item["workflow_json"]
        api_path = root / item["api_json"]
        try:
            ui = json.loads(ui_path.read_text(encoding="utf-8"))
            api = json.loads(api_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{item.get('workflow_id')}: {exc}")
            continue
        workflow_errors = _validate_ui(ui_path, ui) + _validate_api(api_path, api) + _validate_policy(ui_path, ui, api)
        errors.extend(workflow_errors)
        reports.append({"workflow_id": item["workflow_id"], "node_count": len(ui.get("nodes", [])), "link_count": len(ui.get("links", [])), "status": "PASS" if not workflow_errors else "FAIL", "errors": workflow_errors})
    return {"status": "PASS" if not errors else "FAIL", "errors": errors, "workflows": reports}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    result = validate_all(args.root.resolve())
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
