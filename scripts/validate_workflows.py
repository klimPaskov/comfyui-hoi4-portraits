#!/usr/bin/env python3
"""Validate the four expanded, fully visible editor and API workflows."""

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
    "LoadImage",
    "PreviewImage",
    "SaveImage",
    "UNETLoader",
    "UnetLoaderGGUF",
    "ClipLoaderGGUF",
    "VAELoader",
    "LoraLoaderModelOnly",
    "LoadMediaPipeFaceLandmarker",
    "MediaPipeFaceLandmarker",
    "LoadBackgroundRemovalModel",
    "RemoveBackground",
    "AdaptivePortraitCrop",
    "UpscaleModelLoader",
    "ImageUpscaleWithModel",
    "ImageScale",
    "ImageScaleToTotalPixelsX",
    "CLIPTextEncode",
    "ConditioningZeroOut",
    "VAEEncode",
    "ReferenceLatent",
    "EmptyFlux2LatentImage",
    "SharkOptions_Beta",
    "PrimitiveInt",
    "ClownsharKSampler_Beta",
    "VAEDecode",
    "FluxGuidance",
    "KSampler",
    "ComfySwitchNode",
    "Hoi4SetupGuide",
    "Hoi4BackgroundReplace",
    "ImageBatch",
    "ImageFromBatch",
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
    groups = ui.get("groups")
    if not nodes:
        return [f"{path}: nodes must be non-empty"]
    if not isinstance(groups, list) or not groups:
        errors.append(f"{path}: visible canvas groups must be present")
    if "definitions" in ui:
        errors.append(f"{path}: subgraphs/definitions are not allowed; the whole workflow must stay visible")
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

    group_bounds: dict[str, list[float]] = {}
    for index, group in enumerate(groups or []):
        title = group.get("title")
        bounds = group.get("bounding")
        if not isinstance(title, str) or not isinstance(bounds, list) or len(bounds) != 4:
            errors.append(f"{path}: malformed visible group {group!r}")
            continue
        if group.get("flags", {}).get("collapsed") is not False:
            errors.append(f"{path}: group {title!r} must be explicitly expanded")
        group_bounds[title] = bounds
        for other in (groups or [])[index + 1 :]:
            other_bounds = other.get("bounding", [])
            if len(other_bounds) == 4 and _overlap(bounds, other_bounds, 80):
                errors.append(f"{path}: visible groups overlap or lack an 80px gutter: {title} / {other.get('title')}")
    members_by_group: dict[str, list[dict[str, Any]]] = {title: [] for title in group_bounds}
    for node in nodes:
        group_name = node.get("properties", {}).get("hoi4_group")
        bounds = group_bounds.get(group_name)
        if bounds is None:
            errors.append(f"{path}: node {node.get('id')} is not assigned to a visible group")
            continue
        members_by_group[group_name].append(node)
        nx, ny = node["pos"]
        nw, nh = node["size"]
        if nx % 20 or ny % 20:
            errors.append(f"{path}: node {node.get('id')} is off the symmetric 20px layout grid")
        gx, gy, gw, gh = bounds
        if nx < gx + 20 or ny < gy + 20 or nx + nw > gx + gw - 20 or ny + nh > gy + gh - 20:
            errors.append(f"{path}: node {node.get('id')} extends outside {group_name}")

    for title, members in members_by_group.items():
        if not members:
            errors.append(f"{path}: visible group {title!r} is empty")
            continue
        left = min(node["pos"][0] for node in members)
        top = min(node["pos"][1] for node in members)
        right = max(node["pos"][0] + node["size"][0] for node in members)
        bottom = max(node["pos"][1] + node["size"][1] for node in members)
        expected = [left - 40, top - 60, right - left + 80, bottom - top + 100]
        if group_bounds[title] != expected:
            errors.append(f"{path}: group {title!r} is not tightly fitted with symmetric gutters")

    for index, node in enumerate(nodes):
        box = [*node["pos"], *node["size"]]
        for other in nodes[index + 1 :]:
            other_box = [*other["pos"], *other["size"]]
            if _overlap(box, other_box, 40):
                errors.append(f"{path}: nodes {node['id']} and {other['id']} overlap or lack a 40px gutter")
    return errors


def _api_errors(path: Path, api: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not api:
        return [f"{path}: API graph is empty"]
    for node_id, node in api.items():
        if not node_id.isdigit() or node.get("class_type") not in ALLOWED_NODES:
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
    compact_limits = {
        WORKFLOW_IDS[0]: (10000, 2750),
        WORKFLOW_IDS[1]: (5060, 1630),
        WORKFLOW_IDS[2]: (7100, 1700),
        WORKFLOW_IDS[3]: (8420, 1720),
    }
    if ui.get("groups") and workflow_id in compact_limits:
        left = min(group["bounding"][0] for group in ui["groups"])
        top = min(group["bounding"][1] for group in ui["groups"])
        right = max(group["bounding"][0] + group["bounding"][2] for group in ui["groups"])
        bottom = max(group["bounding"][1] + group["bounding"][3] for group in ui["groups"])
        maximum_width, maximum_height = compact_limits[workflow_id]
        if right - left > maximum_width or bottom - top > maximum_height:
            errors.append(
                f"{path}: workflow canvas is no longer compact "
                f"({right - left}×{bottom - top}, maximum {maximum_width}×{maximum_height})"
            )
    if ui.get("extra", {}).get("base_model") != build_workflows.BASE_MODEL or "klein-base" in json.dumps(ui).casefold():
        errors.append(f"{path}: only distilled FLUX.2 Klein is allowed")
    if ui.get("extra", {}).get("master_size") != [1024, 1365] or ui.get("extra", {}).get("game_size") != [156, 210]:
        errors.append(f"{path}: master/game dimensions are wrong")
    if ui.get("extra", {}).get("dds") != {"format": "A8R8G8B8", "mipmaps": False}:
        errors.append(f"{path}: DDS policy must be vanilla-style A8R8G8B8 with no mipmaps")
    expected_adonis_metadata = None if is_text else {
        "source": "n8te0/adonis_flux2klein",
        "revision": build_workflows.ADONIS_REVISION,
        "workflow": build_workflows.ADONIS_WORKFLOW,
        "passes": [build_workflows.ADONIS_BASE, build_workflows.ADONIS_POST],
    }
    if ui.get("extra", {}).get("adonis") != expected_adonis_metadata:
        errors.append(f"{path}: pinned Adonis source metadata changed")

    counts: dict[str, int] = {}
    for node in api.values():
        counts[node["class_type"]] = counts.get(node["class_type"], 0) + 1
    expected_samplers = 3 if is_source else 0 if is_processing else 1
    if counts.get("KSampler", 0) != expected_samplers:
        errors.append(f"{path}: expected {expected_samplers} standard ComfyUI KSampler node(s)")
    forbidden_merged = {
        "Hoi4ModelStack",
        "Hoi4SourcePrep",
        "Hoi4AdonisRestoration",
        "Hoi4FinalOutput",
        "Hoi4PortraitSampler",
    }
    merged = sorted(node_type for node_type in forbidden_merged if counts.get(node_type, 0))
    if merged:
        errors.append(f"{path}: oversized merged nodes are forbidden: {', '.join(merged)}")
    if counts.get("UNETLoader", 0) + counts.get("UnetLoaderGGUF", 0) != 1:
        errors.append(f"{path}: workflow needs one visible diffusion-model loader")
    if counts.get("ClipLoaderGGUF", 0) != 1 or counts.get("VAELoader", 0) != 1:
        errors.append(f"{path}: Qwen Q8 and VAE loaders must remain separately visible")
    expected_loras = 1 if is_text else 2 if is_processing else 3
    if counts.get("LoraLoaderModelOnly", 0) != expected_loras:
        errors.append(f"{path}: expected {expected_loras} separately visible LoRA loaders")
    expected_png_savers = 6 if is_source else 2
    expected_dds_savers = 3 if is_source else 1
    if counts.get("SaveImage", 0) != expected_png_savers:
        errors.append(f"{path}: expected {expected_png_savers} automatic PNG saver(s)")
    if counts.get("Hoi4SaveDDS", 0) != expected_dds_savers:
        errors.append(f"{path}: expected {expected_dds_savers} automatic DDS saver(s)")
    save_prefixes: list[str] = []
    for node in api.values():
        if node.get("class_type") not in {"SaveImage", "Hoi4SaveDDS"}:
            continue
        inputs = node.get("inputs", {})
        prefix = str(inputs.get("filename_prefix", ""))
        save_prefixes.append(prefix)
        image_link = inputs.get("images")
        source = api.get(image_link[0], {}) if isinstance(image_link, list) and image_link else {}
        if source.get("class_type") != "ImageScale":
            errors.append(f"{path}: automatic saver {prefix!r} must receive a sized portrait")
            continue
        source_inputs = source.get("inputs", {})
        expected_size = (1024, 1365) if prefix.startswith("1024x1365/") else (156, 210)
        actual_size = (source_inputs.get("width"), source_inputs.get("height"))
        if actual_size != expected_size:
            errors.append(f"{path}: automatic saver {prefix!r} receives {actual_size}, expected {expected_size}")
    if len(save_prefixes) != len(set(save_prefixes)):
        errors.append(f"{path}: automatic save prefixes must be unique")
    if is_batch and counts.get("Hoi4BatchInput", 0) != 1:
        errors.append(f"{path}: batch workflow needs one list-output input card")
    if is_source:
        source_comparison = [
            node for node in ui.get("nodes", [])
            if node.get("type") == "PreviewImage"
            and node.get("properties", {}).get("hoi4_group") == "06 Compare portraits"
        ]
        if len(source_comparison) != 5:
            errors.append(f"{path}: source workflow needs exactly the five-card comparison row")
    expected_background_controls = 1 if is_source or is_text else 0
    if counts.get("Hoi4BackgroundReplace", 0) != expected_background_controls:
        errors.append(f"{path}: expected {expected_background_controls} shared background true/false control(s)")
    if is_source and (counts.get("ImageBatch", 0) != 2 or counts.get("ImageFromBatch", 0) != 3):
        errors.append(f"{path}: the shared background control must batch and split all three portraits")

    setup_nodes = [
        node for node in ui.get("nodes", [])
        if node.get("properties", {}).get("hoi4_group") == "00 Setup"
    ]
    if len(setup_nodes) != 1 or setup_nodes[0].get("type") != "Hoi4SetupGuide":
        errors.append(f"{path}: the left setup group must contain exactly one setup guide")
    else:
        if setup_nodes[0].get("size") != list(build_workflows.SETUP_GUIDE_SIZE):
            errors.append(f"{path}: setup guide must stay narrow and tall")
        setup_source = (build_workflows.ROOT / "custom_nodes/hoi4_portraits/web/setup_guide.js").read_text()
        catalog = json.loads((build_workflows.ROOT / "models.json").read_text())
        missing_urls = [model["url"] for model in catalog["models"] if model["url"] not in setup_source]
        if missing_urls:
            errors.append(f"{path}: setup guide is missing {len(missing_urls)} clickable model download link(s)")
    if any(node.get("type") == "Note" for node in ui.get("nodes", [])):
        errors.append(f"{path}: workflow notes are forbidden; keep explanations in the setup guide or node titles")

    groups_by_title = {group.get("title"): group for group in ui.get("groups", [])}
    if not is_text:
        prep_title = "01 Prepare portraits" if is_batch else "01 Prepare portrait"
        prep = groups_by_title.get(prep_title, {}).get("bounding")
        models = groups_by_title.get("02 Models", {}).get("bounding")
        if prep and models and models[1] < prep[1] + prep[3] + 80:
            errors.append(f"{path}: model loaders must sit below the green preparation group")

    restore_nodes = [
        node for node in ui.get("nodes", [])
        if node.get("properties", {}).get("hoi4_group") == "03 Restore details"
    ]
    restore_counts: dict[str, int] = {}
    for node in restore_nodes:
        restore_counts[node["type"]] = restore_counts.get(node["type"], 0) + 1
    expected_adonis_nodes = 0 if is_text else 1
    for class_type, multiplier in {
        "ImageScaleToTotalPixelsX": 1,
        "CLIPTextEncode": 2,
        "ConditioningZeroOut": 2,
        "VAEEncode": 1,
        "ReferenceLatent": 4,
        "EmptyFlux2LatentImage": 1,
        "SharkOptions_Beta": 1,
        "ClownsharKSampler_Beta": 2,
        "VAEDecode": 1,
        "ComfySwitchNode": 1,
    }.items():
        if restore_counts.get(class_type, 0) != expected_adonis_nodes * multiplier:
            errors.append(f"{path}: expanded Adonis graph needs {expected_adonis_nodes * multiplier} visible {class_type} node(s)")

    forbidden_public_words = re.compile(r"\b(?:live|advanced|expanded|visible)\b", re.IGNORECASE)
    for node in ui.get("nodes", []):
        public_text = node.get("title", "")
        if forbidden_public_words.search(public_text):
            errors.append(f"{path}: node {node.get('id')} contains meta wording")

        group_name = node.get("properties", {}).get("hoi4_group")
        theme = groups_by_title.get(group_name, {}).get("properties", {}).get("hoi4_node_color")
        expected_theme = "switch" if node.get("type") in {"ComfySwitchNode", "Hoi4BackgroundReplace"} else theme
        if expected_theme in build_workflows.COLORS:
            expected_color, expected_background = build_workflows.COLORS[expected_theme]
            if [node.get("color"), node.get("bgcolor")] != [expected_color, expected_background]:
                errors.append(f"{path}: node {node.get('id')} color does not match {group_name}")

        if node.get("type") != "PreviewImage":
            continue
        width, height = node.get("size", [0, 0])
        expected_preview_size = [600, 810]
        if [width, height] != expected_preview_size:
            errors.append(
                f"{path}: portrait preview {node.get('id')} must be "
                f"{expected_preview_size[0]}×{expected_preview_size[1]}"
            )

    previews_by_group: dict[str, list[dict[str, Any]]] = {}
    for node in ui.get("nodes", []):
        if node.get("type") == "PreviewImage":
            group = node.get("properties", {}).get("hoi4_group", "")
            previews_by_group.setdefault(group, []).append(node)
    for group, previews in previews_by_group.items():
        if len(previews) < 3:
            continue
        ordered = sorted(previews, key=lambda node: node["pos"][0])
        if len({node["pos"][1] for node in ordered}) != 1:
            errors.append(f"{path}: preview comparison in {group!r} must be one symmetric row")
        if any(right["pos"][0] - (left["pos"][0] + left["size"][0]) != 40 for left, right in zip(ordered, ordered[1:])):
            errors.append(f"{path}: preview comparison in {group!r} must use exact 40px gutters")

    candidate_samplers = sorted(
        (
            node for node in ui.get("nodes", [])
            if node.get("properties", {}).get("hoi4_group") == "04 Create three portraits"
            and node.get("type") == "KSampler"
        ),
        key=lambda node: node["pos"][1],
    )
    if candidate_samplers:
        if len({node["pos"][0] for node in candidate_samplers}) != 1:
            errors.append(f"{path}: candidate samplers must share one aligned column")
        if any(lower["pos"][1] - (upper["pos"][1] + upper["size"][1]) != 80 for upper, lower in zip(candidate_samplers, candidate_samplers[1:])):
            errors.append(f"{path}: candidate samplers must use exact 80px vertical gutters")

    for node in api.values():
        class_type = node["class_type"]
        inputs = node.get("inputs", {})
        if class_type in {"UNETLoader", "UnetLoaderGGUF"}:
            if inputs.get("unet_name") != build_workflows.BASE_MODEL:
                errors.append(f"{path}: visible model loader must use {build_workflows.BASE_MODEL}")
        elif class_type == "ClipLoaderGGUF":
            if inputs.get("clip_name") != build_workflows.TEXT_ENCODER or inputs.get("type") != "flux2":
                errors.append(f"{path}: visible text encoder must be Qwen3 Q8 in FLUX.2 mode")
        elif class_type == "VAELoader" and inputs.get("vae_name") != build_workflows.VAE_MODEL:
            errors.append(f"{path}: visible VAE loader changed")
        elif class_type == "LoraLoaderModelOnly":
            filename = inputs.get("lora_name")
            allowed = {build_workflows.STYLE_LORA, build_workflows.ADONIS_BASE, build_workflows.ADONIS_POST}
            if filename not in allowed or inputs.get("strength_model") != 1.0:
                errors.append(f"{path}: unexpected visible LoRA loader {filename!r}")
            if is_processing and filename == build_workflows.STYLE_LORA:
                errors.append(f"{path}: processing-only must not load the style LoRA")
            if is_text and filename in {build_workflows.ADONIS_BASE, build_workflows.ADONIS_POST}:
                errors.append(f"{path}: text-to-image must not load Adonis LoRAs")
        elif class_type == "KSampler":
            exact = {"steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}
            for key, expected in exact.items():
                if inputs.get(key) != expected:
                    errors.append(f"{path}: sampler {key} must default to {expected!r}")
            if any(not isinstance(inputs.get(name), list) for name in ("model", "positive", "negative", "latent_image")):
                errors.append(f"{path}: standard sampler inputs must remain visibly connected")
        elif class_type == "FluxGuidance" and inputs.get("guidance") != 1.0:
            errors.append(f"{path}: FLUX guidance must default to 1.0")
        elif class_type == "ImageScaleToTotalPixelsX":
            exact = {"megapixels": 1.7, "multiple_of": 16, "resize_mode": "crop", "upscale_method": "lanczos"}
            if any(inputs.get(key) != value for key, value in exact.items()):
                errors.append(f"{path}: visible Adonis pre-process settings changed")
        elif class_type == "CLIPTextEncode":
            title = node.get("_meta", {}).get("title", "")
            if title == "Adonis Base prompt" and inputs.get("text") != build_workflows.ADONIS_BASE_COMBINED_PROMPT:
                errors.append(f"{path}: exact Adonis Base prompt changed")
            elif title == "Adonis Post prompt" and inputs.get("text") != build_workflows.ADONIS_POST_COMBINED_PROMPT:
                errors.append(f"{path}: exact Adonis Post prompt changed")
            elif title == "Portrait prompt":
                expected_prompt = build_workflows.TEXT_PROMPT if is_text else build_workflows.STYLE_PROMPT
                if inputs.get("text") != expected_prompt:
                    errors.append(f"{path}: exact portrait prompt changed")
            elif title == "Negative prompt" and inputs.get("text") != "":
                errors.append(f"{path}: negative portrait prompt must stay empty")
        elif class_type == "SharkOptions_Beta":
            exact = {"noise_type_init": "laplacian", "s_noise_init": 1.0, "denoise_alt": 1.0, "channelwise_cfg": False}
            if any(inputs.get(key) != value for key, value in exact.items()):
                errors.append(f"{path}: exact upstream Shark options changed")
        elif class_type == "ClownsharKSampler_Beta":
            title = node.get("_meta", {}).get("title", "")
            post = "Post" in title
            exact = {
                "eta": 0.5 if post else 0.8,
                "sampler_name": "exponential/res_2s",
                "scheduler": "simple",
                "steps_to_run": -1,
                "cfg": 1.0,
                "denoise": 1.0,
                "sampler_mode": "standard",
                "bongmath": True,
            }
            if any(inputs.get(key) != value for key, value in exact.items()):
                errors.append(f"{path}: exact visible Adonis {'Post' if post else 'Base'} sampler settings changed")
            linked = ("model", "positive", "negative", "latent_image", "options_group.options0", "steps", "seed")
            if any(not isinstance(inputs.get(name), list) for name in linked):
                errors.append(f"{path}: Adonis sampler inputs must remain visibly connected")
        elif class_type == "ComfySwitchNode":
            if inputs.get("switch") is not True:
                errors.append(f"{path}: Adonis restoration must default to enabled")
            if any(not isinstance(inputs.get(name), list) for name in ("on_false", "on_true")):
                errors.append(f"{path}: Adonis restoration toggle must connect both image choices")
            else:
                false_source = api.get(inputs["on_false"][0], {})
                true_source = api.get(inputs["on_true"][0], {})
                if false_source.get("class_type") != "ImageScale" or true_source.get("class_type") != "VAEDecode":
                    errors.append(f"{path}: Adonis toggle must choose prepared or fully restored portrait")
        elif class_type == "ImageScale":
            title = node.get("_meta", {}).get("title", "")
            if "1024×1365" in title and [inputs.get("width"), inputs.get("height"), inputs.get("crop")] != [1024, 1365, "center"]:
                errors.append(f"{path}: master output must be a centered 1024×1365 crop")
            if "156×210" in title and [inputs.get("width"), inputs.get("height"), inputs.get("crop")] != [156, 210, "center"]:
                errors.append(f"{path}: game output must be a centered 156×210 crop")
        elif class_type == "Hoi4SaveDDS":
            if inputs.get("format") != "argb8888" or not str(inputs.get("filename_prefix", "")).startswith("156x210/dds/"):
                errors.append(f"{path}: DDS output is not game-ready")

    primitive_values = {
        node.get("_meta", {}).get("title"): node.get("inputs", {}).get("value")
        for node in api.values()
        if node.get("class_type") == "PrimitiveInt"
    }
    if not is_text and primitive_values != {"Shared Adonis seed": 42, "Steps per Adonis model": 9}:
        errors.append(f"{path}: visible shared Adonis seed/step controls changed")
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
