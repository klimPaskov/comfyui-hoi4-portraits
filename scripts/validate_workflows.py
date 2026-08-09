#!/usr/bin/env python3
"""Validate the four compact editor and API workflows."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

try:
    from . import build_workflows
except ImportError:
    import build_workflows


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_IDS = tuple(build_workflows.BUILDERS)
ALLOWED_NODES = {
    "Note",
    "LoadImage",
    "PreviewImage",
    "SaveImage",
    "Hoi4ModelStack",
    "Hoi4SourcePrep",
    "Hoi4PortraitSampler",
    "Hoi4AdonisRestoration",
    "Hoi4FinalOutput",
    "Hoi4BatchInput",
    "Hoi4SaveDDS",
}


def _non_person_prompt_terms(prompt: str) -> list[str]:
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


def _overlap(a: list[float], b: list[float], padding: float = 0) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (
        ax + aw + padding <= bx
        or bx + bw + padding <= ax
        or ay + ah + padding <= by
        or by + bh + padding <= ay
    )


def _ui_errors(path: Path, ui: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    nodes = ui.get("nodes", [])
    links = ui.get("links", [])
    groups = ui.get("groups", [])
    if not nodes or not groups:
        return [f"{path}: nodes and groups must be non-empty"]
    by_id = {node.get("id"): node for node in nodes}
    if len(by_id) != len(nodes) or None in by_id:
        errors.append(f"{path}: UI node ids are missing or duplicated")
    link_ids: set[int] = set()
    for link in links:
        if not isinstance(link, list) or len(link) != 6:
            errors.append(f"{path}: malformed link {link!r}")
            continue
        link_id, source_id, source_slot, target_id, target_slot, link_type = link
        if link_id in link_ids:
            errors.append(f"{path}: duplicate link id {link_id}")
        link_ids.add(link_id)
        source = by_id.get(source_id)
        target = by_id.get(target_id)
        if source is None or target is None:
            errors.append(f"{path}: link {link_id} has a missing endpoint")
            continue
        try:
            if source["outputs"][source_slot]["type"] != link_type:
                errors.append(f"{path}: link {link_id} source type mismatch")
            if target["inputs"][target_slot]["type"] != link_type:
                errors.append(f"{path}: link {link_id} target type mismatch")
        except (IndexError, KeyError, TypeError):
            errors.append(f"{path}: link {link_id} has an invalid slot")
    for node in nodes:
        if node.get("type") not in ALLOWED_NODES:
            errors.append(f"{path}: unapproved node {node.get('type')!r}")
        if node.get("mode") != 0:
            errors.append(f"{path}: node {node.get('id')} is disabled or bypassed")
        for item in node.get("inputs", []):
            if item.get("link") is not None and item["link"] not in link_ids:
                errors.append(f"{path}: node {node.get('id')} references a missing input link")
        for item in node.get("outputs", []):
            if any(link_id not in link_ids for link_id in item.get("links") or []):
                errors.append(f"{path}: node {node.get('id')} references a missing output link")

    group_bounds = {group["title"]: group["bounding"] for group in groups}
    for index, group in enumerate(groups):
        for other in groups[index + 1 :]:
            if _overlap(group["bounding"], other["bounding"]):
                errors.append(f"{path}: groups overlap: {group['title']} / {other['title']}")
    for node in nodes:
        group_name = node.get("properties", {}).get("hoi4_group")
        bounds = group_bounds.get(group_name)
        if bounds is None:
            errors.append(f"{path}: node {node.get('id')} is not assigned to a group")
            continue
        nx, ny = node["pos"]
        nw, nh = node["size"]
        gx, gy, gw, gh = bounds
        if nx < gx + 20 or ny < gy + 20 or nx + nw > gx + gw - 20 or ny + nh > gy + gh - 20:
            errors.append(f"{path}: node {node.get('id')} extends outside {group_name}")
    for index, node in enumerate(nodes):
        box = [*node["pos"], *node["size"]]
        for other in nodes[index + 1 :]:
            other_box = [*other["pos"], *other["size"]]
            if _overlap(box, other_box, 20):
                errors.append(f"{path}: nodes {node['id']} and {other['id']} overlap or lack a 20px gutter")
    return errors


def _api_errors(path: Path, api: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not api:
        return [f"{path}: API graph is empty"]
    for node_id, node in api.items():
        if not node_id.isdigit() or node.get("class_type") not in ALLOWED_NODES - {"Note"}:
            errors.append(f"{path}: invalid API node {node_id}: {node.get('class_type')!r}")
        for value in node.get("inputs", {}).values():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and value[0] not in api:
                errors.append(f"{path}: node {node_id} references missing node {value[0]}")
    return errors


def _policy_errors(path: Path, ui: dict[str, Any], api: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    workflow_id = ui.get("extra", {}).get("workflow_id")
    is_source = workflow_id == WORKFLOW_IDS[0]
    is_text = workflow_id == WORKFLOW_IDS[1]
    is_processing = workflow_id == WORKFLOW_IDS[2]
    is_batch = workflow_id == WORKFLOW_IDS[3]
    if ui.get("extra", {}).get("base_model") != build_workflows.BASE_MODEL or "klein-base" in json.dumps(ui).casefold():
        errors.append(f"{path}: only distilled FLUX.2 Klein is allowed")
    if ui.get("extra", {}).get("master_size") != [1024, 1365] or ui.get("extra", {}).get("game_size") != [156, 210]:
        errors.append(f"{path}: master/game dimensions are wrong")
    if ui.get("extra", {}).get("dds") != {"compression": "DXT5", "mipmaps": False}:
        errors.append(f"{path}: DDS policy must be DXT5 with no mipmaps")

    counts: dict[str, int] = {}
    for node in api.values():
        counts[node["class_type"]] = counts.get(node["class_type"], 0) + 1
    expected_samplers = 3 if is_source else 0 if is_processing else 1
    if counts.get("Hoi4PortraitSampler", 0) != expected_samplers:
        errors.append(f"{path}: expected {expected_samplers} sampler card(s)")
    expected_restorers = 0 if is_text else 1
    if counts.get("Hoi4AdonisRestoration", 0) != expected_restorers:
        errors.append(f"{path}: expected {expected_restorers} Adonis card(s)")
    if counts.get("Hoi4ModelStack", 0) != 1 or counts.get("Hoi4FinalOutput", 0) != (3 if is_source else 1):
        errors.append(f"{path}: model/final logical card count is incorrect")
    if is_batch and counts.get("Hoi4BatchInput", 0) != 1:
        errors.append(f"{path}: batch workflow needs one list-output input card")
    if is_source and counts.get("PreviewImage", 0) != 6:
        errors.append(f"{path}: source workflow needs source preview plus the five-card comparison row")

    for node in api.values():
        class_type = node["class_type"]
        inputs = node.get("inputs", {})
        if class_type == "Hoi4ModelStack":
            exact = {
                "diffusion_model": build_workflows.BASE_MODEL,
                "text_encoder": build_workflows.TEXT_ENCODER,
                "vae_name": build_workflows.VAE_MODEL,
                "style_lora": build_workflows.STYLE_LORA,
                "adonis_base": build_workflows.ADONIS_BASE,
                "adonis_refine": build_workflows.ADONIS_REFINE,
            }
            for key, expected in exact.items():
                if inputs.get(key) != expected:
                    errors.append(f"{path}: model stack {key} must be {expected}")
            if is_processing and inputs.get("style_strength") != 0.0:
                errors.append(f"{path}: processing-only must bypass the style LoRA")
            if is_text and inputs.get("load_restoration") is not False:
                errors.append(f"{path}: text-to-image must not load Adonis LoRAs")
            if not is_text and inputs.get("load_restoration") is not True:
                errors.append(f"{path}: source processing must load Adonis Base + Refine")
        elif class_type == "Hoi4PortraitSampler":
            exact = {"steps": 4, "cfg": 1.0, "guidance": 1.0, "sampling_algorithm": "euler", "scheduler": "simple", "denoise": 1.0}
            for key, expected in exact.items():
                if inputs.get(key) != expected:
                    errors.append(f"{path}: sampler {key} must default to {expected!r}")
            expected_prompt = build_workflows.TEXT_PROMPT if is_text else build_workflows.STYLE_PROMPT
            expected_mode = "text_to_image" if is_text else "source_reference"
            if inputs.get("prompt") != expected_prompt or inputs.get("mode") != expected_mode:
                errors.append(f"{path}: sampler mode or exact prompt changed")
            if not is_text and "reference_image" not in inputs:
                errors.append(f"{path}: source sampler is missing its reference image")
        elif class_type == "Hoi4AdonisRestoration":
            exact = {
                "enabled": True, "prompt": build_workflows.RESTORATION_PROMPT, "megapixels": 1.7,
                "multiple_of": 16, "resize_mode": "crop", "upscale_method": "lanczos", "eta": 0.8,
                "sampling_algorithm": "exponential/res_2s", "scheduler": "simple", "total_steps": 9,
                "base_steps_to_run": 5, "cfg": 1.0, "denoise": 1.0, "base_sampling_mode": "standard",
                "refine_sampling_mode": "resample", "noise_type": "gaussian", "initial_noise_scale": 1.0,
                "alternate_denoise": 1.0, "channelwise_cfg": False, "bongmath": True,
            }
            for key, expected in exact.items():
                if inputs.get(key) != expected:
                    errors.append(f"{path}: Adonis {key} must be {expected!r}")
        elif class_type == "Hoi4FinalOutput":
            if [inputs.get("master_width"), inputs.get("master_height"), inputs.get("game_width"), inputs.get("game_height")] != [1024, 1365, 156, 210]:
                errors.append(f"{path}: final output sizes changed")
        elif class_type == "Hoi4SaveDDS":
            if inputs.get("compression") != "dxt5" or not str(inputs.get("filename_prefix", "")).startswith("156x210/dds/"):
                errors.append(f"{path}: DDS output is not game-ready")

    if any(node["class_type"] in {"ImageScale", "ImageScaleBy", "ImageUpscaleWithModel", "UNETLoader", "UnetLoaderGGUF"} for node in api.values()):
        errors.append(f"{path}: graph contains redundant low-level loader/upscale nodes")
    if is_processing and ui.get("extra", {}).get("style_lora") is not None:
        errors.append(f"{path}: processing-only metadata advertises a style LoRA")
    if not is_processing and ui.get("extra", {}).get("style_lora") != build_workflows.STYLE_LORA:
        errors.append(f"{path}: step-2500 style LoRA metadata is missing")
    return errors


def validate_all(root: Path = ROOT) -> dict[str, Any]:
    workflow_dir = root / "workflows"
    errors: list[str] = []
    details: list[dict[str, Any]] = []
    actual_ui = {path.stem for path in workflow_dir.glob("*.json") if not path.name.endswith(".api.json") and path.name != "manifest.json"}
    if actual_ui != set(WORKFLOW_IDS):
        errors.append(f"{workflow_dir}: expected exactly four editor workflows, found {sorted(actual_ui)}")
    for workflow_id in WORKFLOW_IDS:
        ui_path = workflow_dir / f"{workflow_id}.json"
        api_path = workflow_dir / f"{workflow_id}.api.json"
        if not ui_path.is_file() or not api_path.is_file():
            errors.append(f"{workflow_id}: editor/API pair is incomplete")
            continue
        ui = json.loads(ui_path.read_text(encoding="utf-8"))
        api = json.loads(api_path.read_text(encoding="utf-8"))
        errors.extend(_ui_errors(ui_path, ui))
        errors.extend(_api_errors(api_path, api))
        errors.extend(_policy_errors(ui_path, ui, api))
        details.append({"id": workflow_id, "nodes": len(ui["nodes"]), "links": len(ui["links"])})
    return {"status": "PASS" if not errors else "FAIL", "errors": errors, "workflows": details}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    result = validate_all(args.root.resolve())
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
