#!/usr/bin/env python3
"""Mechanical and layout validation for every public workflow."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STEPS = 6
DEFAULT_CFG = 1.0
DEFAULT_GUIDANCE = 1.0
CANVAS_WIDTH = 1024
CANVAS_HEIGHT = 1365
GAME_WIDTH = 156
GAME_HEIGHT = 210
LAYOUT_NODE_PADDING = 24
GROUP_NODE_PADDING = 24

ALLOWED_CORE_NODES = {
    "AdaptivePortraitCrop",
    "ApplyPuLIDFlux2",
    "Canny",
    "CFGGuider",
    "CLIPLoader",
    "CLIPTextEncode",
    "ComfySwitchNode",
    "CropByBBoxes",
    "EmptyFlux2LatentImage",
    "Flux2Scheduler",
    "FluxGuidance",
    "Flux2KleinMultiReferenceLatent",
    "ImageCompositeMasked",
    "ImageCropV2",
    "ImageScale",
    "ImageScaleToMaxDimension",
    "ImageUpscaleWithModel",
    "IdentityFeatureTransferFinal",
    "KSamplerSelect",
    "KleinEditComposite",
    "LoadBackgroundRemovalModel",
    "LoadImage",
    "LoadMediaPipeFaceLandmarker",
    "LoraLoaderModelOnly",
    "MediaPipeFaceLandmarker",
    "PreviewImage",
    "PortraitIdentityMask",
    "PrimitiveBoolean",
    "PrimitiveBoundingBox",
    "PuLIDEVACLIPLoader",
    "PuLIDInsightFaceLoader",
    "PuLIDModelLoader",
    "RandomNoise",
    "ReferenceLatent",
    "RemoveBackground",
    "SamplerCustomAdvanced",
    "SaveImage",
    "SplitSigmasDenoise",
    "UNETLoader",
    "UpscaleModelLoader",
    "VAEDecode",
    "VAEEncode",
    "VAELoader",
}

FORBIDDEN_PERSON_PROMPT_PATTERNS = {
    "hearts of iron": r"\bhearts of iron\b",
    "grand-strategy": r"\bgrand-strategy\b",
    "hand-painted": r"\bhand-painted\b",
    "style": r"\bstyle\b",
    "background": r"\bbackground\b",
    "palette": r"\bpalette\b",
    "render": r"\brender(?:ing|ed)?\b",
    "lighting": r"\blighting\b",
    "studio light": r"\bstudio light(?:ing)?\b",
    "transform": r"\btransform(?:ation|ed)?\b",
    "preserve": r"\bpreserv(?:e|ation)\b",
    "do not": r"\bdo not\b",
}


def _non_person_prompt_terms(prompt: str) -> list[str]:
    prompt_lower = prompt.casefold()
    return sorted(
        label
        for label, pattern in FORBIDDEN_PERSON_PROMPT_PATTERNS.items()
        if re.search(pattern, prompt_lower)
    )


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
        node = api.get(current, {})
        for value in node.get("inputs", {}).values():
            if not (isinstance(value, list) and len(value) == 2 and isinstance(value[0], str)):
                continue
            source = value[0]
            if source not in found:
                found.add(source)
                pending.append(source)
    return found


def _validate_ui(path: Path, ui: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    nodes = ui.get("nodes")
    links = ui.get("links")
    groups = ui.get("groups")
    if not isinstance(nodes, list) or not nodes:
        return [f"{path}: nodes must be a non-empty list"]
    if not isinstance(links, list):
        return [f"{path}: links must be a list"]
    if not isinstance(groups, list) or not groups:
        return [f"{path}: groups must be a non-empty list"]
    by_id = {node.get("id"): node for node in nodes}
    subgraphs = ui.get("definitions", {}).get("subgraphs", [])
    if subgraphs:
        errors.append(f"{path}: workflow stages must remain visible on the main canvas")
    if len(by_id) != len(nodes) or None in by_id:
        errors.append(f"{path}: node ids must be present and unique")

    link_by_id: dict[int, list[Any]] = {}
    for link in links:
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
        source_outputs = source.get("outputs", [])
        target_inputs = target.get("inputs", [])
        if not 0 <= source_slot < len(source_outputs):
            errors.append(f"{path}: link {link_id} has invalid source slot")
        elif source_outputs[source_slot].get("type") != link_type:
            errors.append(f"{path}: link {link_id} source type mismatch")
        if not 0 <= target_slot < len(target_inputs):
            errors.append(f"{path}: link {link_id} has invalid target slot")
        elif target_inputs[target_slot].get("type") not in {link_type, "COMFY_MATCHTYPE_V3", "IMAGE"}:
            errors.append(f"{path}: link {link_id} target type mismatch")

    for node in nodes:
        class_type = str(node.get("type", ""))
        if class_type not in ALLOWED_CORE_NODES:
            errors.append(f"{path}: non-core or unapproved node {class_type!r}")
        if class_type.casefold().startswith("hoi4") or "krea" in class_type.casefold():
            errors.append(f"{path}: forbidden custom/Krea node {class_type!r}")
        if node.get("mode") != 0:
            errors.append(f"{path}: node {node.get('id')} is unexpectedly bypassed or muted")
        for input_item in node.get("inputs", []):
            target_link = input_item.get("link")
            if target_link is not None and target_link not in link_by_id:
                errors.append(f"{path}: node {node.get('id')} references missing input link {target_link}")
        for output in node.get("outputs", []):
            for output_link in output.get("links") or []:
                if output_link not in link_by_id:
                    errors.append(f"{path}: node {node.get('id')} references missing output link {output_link}")

    # Every node belongs to exactly one non-overlapping visual group.
    group_bounds = {group.get("title"): group.get("bounding") for group in groups}
    for index, group in enumerate(groups):
        bounds = group.get("bounding")
        if not (isinstance(bounds, list) and len(bounds) == 4):
            errors.append(f"{path}: group {group.get('title')} has invalid bounds")
            continue
        for other in groups[index + 1 :]:
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
        if (
            nx < gx + GROUP_NODE_PADDING
            or ny < gy + GROUP_NODE_PADDING
            or nx + nw > gx + gw - GROUP_NODE_PADDING
            or ny + nh > gy + gh - GROUP_NODE_PADDING
        ):
            errors.append(f"{path}: node {node.get('id')} extends outside group {group_name}")

    # Rendered nodes from adjacent groups can still collide even when their
    # group rectangles are separate. Keep one layout-wide safety margin.
    for index, node in enumerate(nodes):
        a = [*node.get("pos", [0, 0]), *node.get("size", [0, 0])]
        for other in nodes[index + 1 :]:
            b = [*other.get("pos", [0, 0]), *other.get("size", [0, 0])]
            if _overlap(a, b, padding=LAYOUT_NODE_PADDING):
                errors.append(f"{path}: nodes overlap or are too close: {node.get('id')} and {other.get('id')}")
    return errors


def _validate_api(path: Path, api: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not api:
        return [f"{path}: API graph is empty"]
    for node_id, node in api.items():
        if not node_id.isdigit() or not isinstance(node, dict):
            errors.append(f"{path}: API graph contains a non-node key {node_id!r}")
            continue
        class_type = str(node.get("class_type", ""))
        if class_type not in ALLOWED_CORE_NODES:
            errors.append(f"{path}: API graph uses non-core or unapproved node {class_type!r}")
        if class_type.casefold().startswith("hoi4") or "krea" in class_type.casefold():
            errors.append(f"{path}: API graph contains forbidden custom/Krea node {class_type!r}")
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            errors.append(f"{path}: node {node_id} inputs must be an object")
            continue
        for name, value in inputs.items():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
                if value[0] not in api:
                    errors.append(f"{path}: node {node_id}.{name} references missing node {value[0]}")
                if not isinstance(value[1], int) or value[1] < 0:
                    errors.append(f"{path}: node {node_id}.{name} has invalid output slot")
    if not any(node.get("class_type") == "SaveImage" for node in api.values()):
        errors.append(f"{path}: graph has no SaveImage output")
    return errors


def _validate_policy(path: Path, ui: dict[str, Any], api: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    extra = ui.get("extra", {})
    workflow_id = str(extra.get("workflow_id", ""))
    is_source = extra.get("workflow_kind") == "image_to_image"
    is_processing = workflow_id.endswith("processing_only")
    is_text_to_image = workflow_id.endswith("text_to_image")
    identity_method = str(extra.get("identity_preservation", ""))
    is_comparison = extra.get("identity_comparison") is True
    if extra.get("base_model") != "flux-2-klein-base-9b-fp8.safetensors":
        errors.append(f"{path}: incorrect FLUX.2 Klein 9B base model")
    if is_processing and extra.get("style_lora") is not None:
        errors.append(f"{path}: processing workflow must not advertise a style LoRA")
    elif not is_processing and extra.get("style_lora") != "hoi4_portrait_flux2_klein9b_lora_000002250.safetensors":
        errors.append(f"{path}: incorrect style LoRA")
    expected_core_only = is_text_to_image
    if extra.get("core_nodes_only") is not expected_core_only or extra.get("comfy_cloud_ready") is not True:
        errors.append(f"{path}: workflow compatibility metadata is incorrect")
    expected_background_order = "not_applicable_processing_only" if is_processing else "after_final_lora_styled_decode"
    if extra.get("background_order") != expected_background_order:
        errors.append(f"{path}: background policy is not final-stage-only")
    if extra.get("master_size") != [CANVAS_WIDTH, CANVAS_HEIGHT]:
        errors.append(f"{path}: master size must be {CANVAS_WIDTH} x {CANVAS_HEIGHT}")
    if extra.get("game_size") != [GAME_WIDTH, GAME_HEIGHT] or extra.get("game_resize_policy") != "lanczos_center_crop":
        errors.append(f"{path}: game-size output must use a centered crop to {GAME_WIDTH} x {GAME_HEIGHT}")

    lora_node = next(
        (
            node_id
            for node_id, node in api.items()
            if node.get("class_type") == "LoraLoaderModelOnly"
            and str(node.get("inputs", {}).get("lora_name", "")).startswith("hoi4_portrait_flux2_klein9b_lora_")
        ),
        None,
    )
    if is_processing:
        if lora_node is not None:
            errors.append(f"{path}: processing workflow must not contain a style LoRA")
    elif lora_node is None or api[lora_node]["inputs"].get("model") != ["1", 0]:
        errors.append(f"{path}: style LoRA is not applied directly to the FLUX.2 base model")
    elif api[lora_node]["inputs"].get("strength_model") != 1.0:
        errors.append(f"{path}: LoRA loader strength must default to 1.00")

    restoration_lokr = {
        node_id: node
        for node_id, node in api.items()
        if node.get("class_type") == "LoraLoaderModelOnly"
        and node.get("inputs", {}).get("lora_name") == "adonis_base.safetensors"
    }
    if is_text_to_image:
        if restoration_lokr:
            errors.append(f"{path}: text-to-image workflow must not load the restoration LoKr")
    elif set(restoration_lokr) != {"191"} or restoration_lokr["191"]["inputs"].get("model") != ["1", 0]:
        errors.append(f"{path}: restoration workflow must load Adonis Base from the FLUX.2 model")

    identity_nodes = {
        node_id: node for node_id, node in api.items() if node.get("class_type") == "IdentityFeatureTransferFinal"
    }
    if is_source and identity_method in {"feature_mid", "feature_hard"}:
        identity = identity_nodes.get("190", {}).get("inputs", {})
        profile = "HARD_LOCK" if identity_method == "feature_hard" else "MID_LOCK"
        expected_preset = "custom" if identity_method in {"feature_mid", "feature_hard"} else "MID_LOCK"
        if set(identity_nodes) != {"190"}:
            errors.append(f"{path}: feature-transfer source must contain one shared identity-lock node")
        elif (
            identity.get("model") != ["4", 0]
            or identity.get("preset") != expected_preset
            or identity.get("enabled") is not True
        ):
            errors.append(f"{path}: source feature transfer is not configured for the {profile} profile")
        if identity_method in {"feature_mid", "feature_hard"}:
            if api.get("192", {}).get("class_type") != "PortraitIdentityMask":
                errors.append(f"{path}: masked feature transfer requires PortraitIdentityMask")
            if identity.get("subject_mask_1") != ["192", 0] or identity.get("subject_mask_2") != ["192", 0]:
                errors.append(f"{path}: both feature-transfer references must use the identity mask")
            expected_floor, expected_temperature = ((0.04, 0.025) if identity_method == "feature_hard" else (0.2, 0.07))
            if identity.get("similarity_floor") != expected_floor or identity.get("softmax_temperature") != expected_temperature:
                errors.append(f"{path}: masked feature-transfer profile values are incorrect")
    elif identity_nodes:
        errors.append(f"{path}: unexpected feature-transfer node for identity method {identity_method!r}")

    expected_sampling = {"30": ("euler", DEFAULT_STEPS)}
    if is_source:
        expected_sampling.update(
            {
                "50": ("euler", 6),
                "70": ("res_2s", 4),
                "90": ("res_2m", 8),
            }
        )
    elif is_text_to_image:
        expected_sampling = {"27": ("euler", DEFAULT_STEPS)}
    sampler_nodes = {
        node_id: node for node_id, node in api.items() if node.get("class_type") == "SamplerCustomAdvanced"
    }
    if set(sampler_nodes) != set(expected_sampling):
        errors.append(f"{path}: advanced sampler nodes do not match the workflow sampling policy")
    for sampler_id, (sampler_name, steps) in expected_sampling.items():
        control_id = 1000 + int(sampler_id) * 10
        guidance = api.get(str(control_id), {})
        guider = api.get(str(control_id + 1), {})
        noise = api.get(str(control_id + 2), {})
        selector = api.get(str(control_id + 3), {})
        scheduler = api.get(str(control_id + 4), {})
        split = api.get(str(control_id + 5), {})
        inputs = sampler_nodes.get(sampler_id, {}).get("inputs", {})
        positive_id = "20" if is_text_to_image else str(int(sampler_id) - 7)
        negative_id = "21" if is_text_to_image else str(int(sampler_id) - 6)
        latent_id = "22" if is_text_to_image else str(int(sampler_id) - 8)
        expected_seed = 42 if is_text_to_image else {"30": 17, "50": 42, "70": 43, "90": 44}[sampler_id]
        if guidance.get("class_type") != "FluxGuidance" or guidance.get("inputs") != {
            "conditioning": [positive_id, 0],
            "guidance": DEFAULT_GUIDANCE,
        }:
            errors.append(f"{path}: sampler {sampler_id} guidance control is incorrect")
        if guider.get("class_type") != "CFGGuider" or guider.get("inputs", {}).get("positive") != [str(control_id), 0]:
            errors.append(f"{path}: sampler {sampler_id} CFG guider is incorrect")
        if guider.get("inputs", {}).get("negative") != [negative_id, 0] or guider.get("inputs", {}).get("cfg") != DEFAULT_CFG:
            errors.append(f"{path}: sampler {sampler_id} CFG or negative conditioning is incorrect")
        if noise.get("class_type") != "RandomNoise" or noise.get("inputs", {}).get("noise_seed") != expected_seed:
            errors.append(f"{path}: sampler {sampler_id} seed control is incorrect")
        if selector.get("class_type") != "KSamplerSelect" or selector.get("inputs", {}).get("sampler_name") != sampler_name:
            errors.append(f"{path}: sampler node {sampler_id} must use {sampler_name}")
        if scheduler.get("class_type") != "Flux2Scheduler" or scheduler.get("inputs") != {
            "steps": steps,
            "width": CANVAS_WIDTH,
            "height": CANVAS_HEIGHT,
        }:
            errors.append(f"{path}: sampler node {sampler_id} must use {steps} FLUX.2 steps at the master resolution")
        if split.get("class_type") != "SplitSigmasDenoise" or split.get("inputs") != {
            "sigmas": [str(control_id + 4), 0],
            "denoise": 1.0,
        }:
            errors.append(f"{path}: sampler node {sampler_id} must default to denoise 1.00")
        expected_sampler_inputs = {
            "noise": [str(control_id + 2), 0],
            "guider": [str(control_id + 1), 0],
            "sampler": [str(control_id + 3), 0],
            "sigmas": [str(control_id + 5), 1],
            "latent_image": [latent_id, 0],
        }
        if inputs != expected_sampler_inputs:
            errors.append(f"{path}: advanced sampler node {sampler_id} is wired incorrectly")
        if sampler_id == "30" and not is_text_to_image and guider.get("inputs", {}).get("model") != ["191", 0]:
            errors.append(f"{path}: restoration guider must use the Adonis LoKr model")
        if is_source and sampler_id in {"50", "70", "90"}:
            expected_model_node = {
                "source": "4",
                "native": "4",
                "composite": "4",
                "pulid": "194",
            }.get(identity_method, "190")
            if guider.get("inputs", {}).get("model") != [expected_model_node, 0]:
                errors.append(f"{path}: source candidate guider {sampler_id} must use model node {expected_model_node}")

    master_scale_ids = {"61", "30"} if is_text_to_image else {"8", "34"}
    if is_source:
        master_scale_ids.update({"54", "74", "94", "121"})
    game_scale_ids = {"128", "138", "148"} if is_source else {"72"}
    for node_id in master_scale_ids:
        scale = api.get(node_id, {})
        scale_inputs = scale.get("inputs", {})
        if (
            scale.get("class_type") != "ImageScale"
            or scale_inputs.get("width") != CANVAS_WIDTH
            or scale_inputs.get("height") != CANVAS_HEIGHT
            or scale_inputs.get("crop") != "center"
        ):
            errors.append(f"{path}: image node {node_id} must normalize to {CANVAS_WIDTH} x {CANVAS_HEIGHT}")
    for node_id in game_scale_ids:
        scale = api.get(node_id, {})
        scale_inputs = scale.get("inputs", {})
        if (
            scale.get("class_type") != "ImageScale"
            or scale_inputs.get("width") != GAME_WIDTH
            or scale_inputs.get("height") != GAME_HEIGHT
            or scale_inputs.get("crop") != "center"
        ):
            errors.append(f"{path}: game node {node_id} must center-crop to {GAME_WIDTH} x {GAME_HEIGHT}")

    if not is_processing:
        person_prompt_node = "20" if is_text_to_image else "40"
        person_prompt = str(api.get(person_prompt_node, {}).get("inputs", {}).get("text", ""))
        if not re.match(r"^hoi4_portrait[,.]", person_prompt):
            errors.append(f"{path}: person prompt must begin with the LoRA trigger")
        present_terms = _non_person_prompt_terms(person_prompt)
        if present_terms:
            errors.append(f"{path}: person prompt contains non-person instructions: {present_terms}")
        if is_source:
            expected = (
                "hoi4_portrait, maintain the exact identity, facing direction, and expression of the person, "
                "including every object they are holding or wearing."
            )
            if identity_method == "refcontrol_lineart":
                expected = expected.replace("hoi4_portrait,", "hoi4_portrait, refcontrol,", 1)
            if person_prompt != expected:
                errors.append(f"{path}: source identity prompt must use the concise editable default")
            for prompt_id, reference_id in (("40", "43"), ("60", "63"), ("80", "83")):
                if api.get(prompt_id, {}).get("inputs", {}).get("text") != expected:
                    errors.append(f"{path}: candidate prompt {prompt_id} must use the concise editable default")
                if api.get(reference_id, {}).get("inputs", {}).get("conditioning") != [prompt_id, 0]:
                    errors.append(f"{path}: candidate prompt {prompt_id} must affect only its own branch")
                reference = api.get(reference_id, {})
                if identity_method == "source":
                    if reference.get("class_type") != "ReferenceLatent":
                        errors.append(f"{path}: primary source candidate {prompt_id} must use one source reference")
                    elif reference.get("inputs", {}).get("latent") != [str(int(prompt_id) + 2), 0]:
                        errors.append(f"{path}: primary source candidate {prompt_id} has the wrong source latent")
                elif reference.get("class_type") != "Flux2KleinMultiReferenceLatent":
                    errors.append(f"{path}: comparison candidate {prompt_id} must use two source references")
                else:
                    start = int(prompt_id)
                    if reference.get("inputs", {}).get("latent_1") != [str(start + 5), 0] or reference.get("inputs", {}).get("latent_2") != [str(start + 6), 0]:
                        errors.append(f"{path}: comparison candidate {prompt_id} must attach two independent references")
                    expected_first = ["192", 0] if identity_method == "refcontrol_lineart" else ["18", 0]
                    if api.get(str(start + 5), {}).get("inputs", {}).get("pixels") != expected_first:
                        errors.append(f"{path}: comparison candidate {prompt_id} has the wrong first identity reference")
                    if api.get(str(start + 6), {}).get("inputs", {}).get("pixels") != ["32", 0]:
                        errors.append(f"{path}: comparison candidate {prompt_id} must use the selected processed reference")

    preview_expectations: dict[str, list[Any]] = {}
    if is_text_to_image:
        preview_expectations["70"] = ["66", 0]
        preview_expectations["29"] = ["30", 0]
    elif is_processing:
        preview_expectations.update({"10": ["8", 0], "35": ["32", 0], "70": ["32", 0]})
    elif is_source:
        preview_expectations["35"] = ["32", 0]
        preview_sources = (("55", "200"), ("75", "210"), ("95", "220")) if identity_method == "composite" else (("55", "54"), ("75", "74"), ("95", "94"))
        for preview_id, decode_id in preview_sources:
            preview_expectations[preview_id] = [decode_id, 0]
    else:
        preview_expectations.update({"10": ["8", 0], "35": ["34", 0], "55": ["54", 0], "70": ["66", 0]})
    for preview_id, expected_image in preview_expectations.items():
        preview = api.get(preview_id, {})
        if preview.get("class_type") != "PreviewImage" or preview.get("inputs", {}).get("images") != expected_image:
            errors.append(f"{path}: required completed-stage preview node {preview_id} is missing or miswired")

    if not is_processing:
        if is_source:
            source_final_ids = ("200", "210", "220") if identity_method == "composite" else ("54", "74", "94")
            background_branches = [
                ("125", "123", "124", source_final_ids[0]),
                ("135", "133", "134", source_final_ids[1]),
                ("145", "143", "144", source_final_ids[2]),
            ]
            if api.get("119", {}).get("class_type") != "PrimitiveBoolean" or api.get("119", {}).get("inputs", {}).get("value") is not False:
                errors.append(f"{path}: source background toggle must be one shared false-by-default PrimitiveBoolean")
            for switch_id, _, _, _ in background_branches:
                if api.get(switch_id, {}).get("inputs", {}).get("switch") != ["119", 0]:
                    errors.append(f"{path}: background switch {switch_id} is not controlled by the shared toggle")
            shared_background = {"120": "LoadImage", "121": "ImageScale", "122": "LoadBackgroundRemovalModel"}
        else:
            background_branches = [("66", "63", "65", "30")]
            shared_background = {"60": "LoadImage", "61": "ImageScale", "62": "LoadBackgroundRemovalModel"}
        background_canvas_id = "121" if is_source else "61"

        if any(api.get(node_id, {}).get("class_type") != class_type for node_id, class_type in shared_background.items()):
            errors.append(f"{path}: shared background setup is incomplete")
        if any(node.get("class_type") == "InvertMask" for node in api.values()):
            errors.append(f"{path}: foreground mask must not be inverted")

        for switch_id, mask_id, composite_id, expected_final_id in background_branches:
            switch = api.get(switch_id, {})
            composite = api.get(composite_id, {})
            mask = api.get(mask_id, {})
            if switch.get("class_type") != "ComfySwitchNode" or composite.get("class_type") != "ImageCompositeMasked" or mask.get("class_type") != "RemoveBackground":
                errors.append(f"{path}: optional final background branch {switch_id} is incomplete")
                continue
            final_link = switch.get("inputs", {}).get("on_false")
            if final_link != [expected_final_id, 0] or final_link[0] not in api:
                errors.append(f"{path}: background branch {switch_id} has an invalid final portrait link")
                continue
            final_node_id = final_link[0]
            if api[final_node_id].get("class_type") not in {"VAEDecode", "ImageScale", "KleinEditComposite"}:
                errors.append(f"{path}: background branch {switch_id} does not start from a decoded final portrait")
            if composite.get("inputs", {}).get("source") != final_link:
                errors.append(f"{path}: composite {composite_id} differs from its final styled portrait")
            expected_mask_link = [mask_id, 0]
            if composite.get("inputs", {}).get("mask") != expected_mask_link:
                errors.append(f"{path}: composite {composite_id} must use its RemoveBackground mask directly")
            if mask.get("inputs", {}).get("image") != final_link:
                errors.append(f"{path}: foreground mask {mask_id} is not derived from the final styled portrait")
            if composite.get("inputs", {}).get("destination") != [background_canvas_id, 0]:
                errors.append(f"{path}: composite {composite_id} does not use the fitted background")
            if lora_node not in _ancestors(api, final_node_id):
                errors.append(f"{path}: final portrait {final_node_id} was not generated with the LoRA model")
            background_ancestors = _ancestors(api, final_node_id)
            background_ids = set(shared_background) | {branch_id for branch in background_branches for branch_id in branch[:3]}
            if background_ids & background_ancestors:
                errors.append(f"{path}: background processing occurs before final portrait generation for {final_node_id}")

    if is_source:
        expected = ["RealESRGAN_x2plus", "optional_flux2_klein_9b"]
        if extra.get("restoration_order") != expected:
            errors.append(f"{path}: source restoration order is wrong")
        if extra.get("flux_restoration_default") is not True:
            errors.append(f"{path}: FLUX restoration must be enabled by default")
        for key in ("candidate_count", "candidate_seed_count", "background_candidate_count"):
            if extra.get(key) != 3:
                errors.append(f"{path}: source metadata {key} must be three")
        switch = api.get("32", {}).get("inputs", {})
        if switch.get("switch") is not True or switch.get("on_false") != ["8", 0] or switch.get("on_true") != ["34", 0]:
            errors.append(f"{path}: FLUX restoration toggle is not enabled or wired correctly")
        if api.get("22", {}).get("inputs", {}).get("pixels") != ["8", 0]:
            errors.append(f"{path}: FLUX restoration does not consume ESRGAN output")
        if not is_comparison and api.get("42", {}).get("inputs", {}).get("pixels") != ["32", 0]:
            errors.append(f"{path}: LoRA styling does not consume the restoration switch output")
        if api.get("30", {}).get("inputs", {}).get("latent_image") != ["22", 0]:
            errors.append(f"{path}: FLUX restoration does not start from the encoded cropped portrait")
        style_branches = (("42", "50"), ("62", "70"), ("82", "90"))
        for latent_id, sampler_id in style_branches:
            latent = api.get(latent_id, {})
            if is_comparison:
                if latent.get("class_type") != "EmptyFlux2LatentImage" or latent.get("inputs") != {"width": CANVAS_WIDTH, "height": CANVAS_HEIGHT, "batch_size": 1}:
                    errors.append(f"{path}: comparison branch {sampler_id} must use a canonical empty edit latent")
            elif latent.get("inputs", {}).get("pixels") != ["32", 0]:
                errors.append(f"{path}: LoRA branch {sampler_id} does not consume the restoration switch output")
            if api.get(sampler_id, {}).get("inputs", {}).get("latent_image") != [latent_id, 0]:
                errors.append(f"{path}: LoRA branch {sampler_id} does not use its selected edit latent")
            expected_model_node = {"source": "4", "native": "4", "composite": "4", "pulid": "194"}.get(identity_method, "190")
            guider_id = str(1000 + int(sampler_id) * 10 + 1)
            if api.get(guider_id, {}).get("inputs", {}).get("model") != [expected_model_node, 0]:
                errors.append(f"{path}: LoRA branch {sampler_id} is not using model node {expected_model_node}")
    elif is_processing:
        expected = ["RealESRGAN_x2plus", "optional_flux2_klein_9b"]
        if extra.get("restoration_order") != expected:
            errors.append(f"{path}: processing restoration order is wrong")
        if extra.get("flux_restoration_default") is not True:
            errors.append(f"{path}: FLUX restoration must be enabled by default")
        switch = api.get("32", {}).get("inputs", {})
        if switch.get("switch") is not True or switch.get("on_false") != ["8", 0] or switch.get("on_true") != ["34", 0]:
            errors.append(f"{path}: processing restoration toggle is not enabled or wired correctly")
        if api.get("22", {}).get("inputs", {}).get("pixels") != ["8", 0]:
            errors.append(f"{path}: FLUX restoration does not consume ESRGAN output")
        if api.get("30", {}).get("inputs", {}).get("latent_image") != ["22", 0]:
            errors.append(f"{path}: FLUX restoration does not start from the encoded cropped portrait")
    elif is_text_to_image:
        if any(node.get("class_type") in {"UpscaleModelLoader", "ImageUpscaleWithModel", "VAEEncode", "ReferenceLatent"} for node in api.values()):
            errors.append(f"{path}: text-to-image workflow contains source/restoration nodes")
    else:
        errors.append(f"{path}: unexpected workflow id {workflow_id!r}")

    if not workflow_id.endswith("text_to_image"):
        if not is_comparison and any(node.get("class_type") == "EmptyFlux2LatentImage" for node in api.values()):
            errors.append(f"{path}: source workflow must not start sampling from an empty latent")
        normalized = api.get("9", {})
        detector = api.get("13", {})
        crop = api.get("11", {})
        silhouette_loader = api.get("155", {})
        silhouette_mask = api.get("156", {})
        manual_box = api.get("15", {})
        manual_crop = api.get("16", {})
        crop_switch = api.get("18", {})
        processing_switch = api.get("17", {})
        if normalized.get("class_type") != "ImageScaleToMaxDimension" or normalized.get("inputs", {}).get("image") != ["5", 0] or normalized.get("inputs", {}).get("largest_size") != 1024:
            errors.append(f"{path}: source must be normalized to 1024 before face detection")
        detector_inputs = detector.get("inputs", {})
        if detector.get("class_type") != "MediaPipeFaceLandmarker" or detector_inputs.get("image") != ["9", 0] or detector_inputs.get("detector_variant") != "both" or detector_inputs.get("num_faces") != 1 or detector_inputs.get("min_confidence") != 0.3:
            errors.append(f"{path}: source must use the tested single-face MediaPipe detection settings")
        crop_inputs = crop.get("inputs", {})
        if (
            crop.get("class_type") != "AdaptivePortraitCrop"
            or crop_inputs.get("image") != ["9", 0]
            or crop_inputs.get("face_bboxes") != ["13", 1]
            or crop_inputs.get("subject_mask") != ["156", 0]
            or crop_inputs.get("zoom") != 0.9
            or crop_inputs.get("preserve_headwear") is not True
        ):
            errors.append(f"{path}: source must use the 0.90 adaptive crop with headwear preservation enabled")
        if silhouette_loader.get("class_type") != "LoadBackgroundRemovalModel" or silhouette_mask.get("inputs", {}).get("image") != ["9", 0] or silhouette_mask.get("inputs", {}).get("bg_removal_model") != ["155", 0]:
            errors.append(f"{path}: source silhouette measurement is missing or miswired")
        if manual_box.get("class_type") != "PrimitiveBoundingBox":
            errors.append(f"{path}: difficult sources require a manual bounding-box override")
        manual_inputs = manual_crop.get("inputs", {})
        if manual_crop.get("class_type") != "CropByBBoxes" or manual_inputs.get("image") != ["9", 0] or manual_inputs.get("bboxes") != ["15", 0] or manual_inputs.get("output_width") != CANVAS_WIDTH or manual_inputs.get("output_height") != CANVAS_HEIGHT:
            errors.append(f"{path}: manual crop override is not connected to the normalized source")
        switch_inputs = crop_switch.get("inputs", {})
        if crop_switch.get("class_type") != "ComfySwitchNode" or switch_inputs.get("switch") is not False or switch_inputs.get("on_false") != ["11", 0] or switch_inputs.get("on_true") != ["16", 0]:
            errors.append(f"{path}: automatic/manual crop switch is wired incorrectly")
        processing_inputs = processing_switch.get("inputs", {})
        if (
            processing_switch.get("class_type") != "ComfySwitchNode"
            or processing_inputs.get("switch") is not True
            or processing_inputs.get("on_false") != ["9", 0]
            or processing_inputs.get("on_true") != ["18", 0]
        ):
            errors.append(f"{path}: face-processing bypass must default on and retain the normalized full composition when disabled")
        if api.get("7", {}).get("inputs", {}).get("image") != ["17", 0]:
            errors.append(f"{path}: ESRGAN must consume the face-processing switch output")
        if extra.get("face_processing_default") is not True or extra.get("face_processing_bypass") != "whole_composition_center_crop_then_esrgan":
            errors.append(f"{path}: face-processing metadata is missing")
        if extra.get("source_crop") != "toggleable_adaptive_head_and_shoulders_zoom_0.90_adjustable_headwear_before_esrgan":
            errors.append(f"{path}: source crop metadata is missing")
        if is_source and extra.get("pose_preservation") != "encoded_source_latent_is_sampler_start":
            errors.append(f"{path}: pose-preservation metadata is missing")
    return errors


def validate_all(root: Path = ROOT) -> dict[str, Any]:
    manifest_path = root / "workflows" / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "FAIL", "errors": [f"{manifest_path}: {exc}"], "workflows": []}
    errors: list[str] = []
    reports: list[dict[str, Any]] = []
    items = manifest.get("workflows", [])
    if len(items) != 3 + 9:
        errors.append(f"{manifest_path}: three primary and nine comparison workflows are required")
    for item in items:
        ui_path = root / item["workflow_json"]
        api_path = root / item["api_json"]
        try:
            ui = json.loads(ui_path.read_text(encoding="utf-8"))
            api = json.loads(api_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{item.get('workflow_id')}: {exc}")
            continue
        workflow_errors = _validate_ui(ui_path, ui) + _validate_api(api_path, api) + _validate_policy(ui_path, ui, api)
        errors.extend(workflow_errors)
        reports.append(
            {
                "workflow_id": item["workflow_id"],
                "node_count": len(ui.get("nodes", [])),
                "link_count": len(ui.get("links", [])),
                "status": "PASS" if not workflow_errors else "FAIL",
                "errors": workflow_errors,
            }
        )
    return {"status": "PASS" if not errors else "FAIL", "errors": errors, "workflows": reports}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    result = validate_all(args.root.resolve())
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
