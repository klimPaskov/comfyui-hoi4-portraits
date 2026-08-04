#!/usr/bin/env python3
"""Mechanical and layout validation for every public workflow."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STEPS = 8
LAYOUT_NODE_PADDING = 24
GROUP_NODE_PADDING = 24

ALLOWED_CORE_NODES = {
    "AdaptivePortraitCrop",
    "CFGGuider",
    "CLIPLoader",
    "CLIPTextEncode",
    "ComfySwitchNode",
    "CropByBBoxes",
    "EmptyFlux2LatentImage",
    "Flux2Scheduler",
    "ImageCompositeMasked",
    "ImageCropV2",
    "ImageScale",
    "ImageScaleToMaxDimension",
    "ImageUpscaleWithModel",
    "KSamplerSelect",
    "LoadBackgroundRemovalModel",
    "LoadImage",
    "LoadMediaPipeFaceLandmarker",
    "LoraLoaderModelOnly",
    "MediaPipeFaceLandmarker",
    "PreviewImage",
    "PrimitiveBoolean",
    "PrimitiveBoundingBox",
    "PrimitiveFloat",
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
    is_source = workflow_id.endswith("source")
    is_processing = workflow_id.endswith("processing_only")
    is_text_to_image = workflow_id.endswith("text_to_image")
    if extra.get("base_model") != "flux-2-klein-base-9b-fp8.safetensors":
        errors.append(f"{path}: incorrect FLUX.2 Klein 9B base model")
    if is_processing and extra.get("style_lora") is not None:
        errors.append(f"{path}: processing workflow must not advertise a style LoRA")
    elif not is_processing and extra.get("style_lora") != "hoi4_portrait_flux2_klein9b_lora_000001500.safetensors":
        errors.append(f"{path}: incorrect style LoRA")
    expected_core_only = is_text_to_image
    if extra.get("core_nodes_only") is not expected_core_only or extra.get("comfy_cloud_ready") is not True:
        errors.append(f"{path}: workflow compatibility metadata is incorrect")
    expected_background_order = "not_applicable_processing_only" if is_processing else "after_final_lora_styled_decode"
    if extra.get("background_order") != expected_background_order:
        errors.append(f"{path}: background policy is not final-stage-only")

    lora_node = next((node_id for node_id, node in api.items() if node.get("class_type") == "LoraLoaderModelOnly"), None)
    if is_processing:
        if lora_node is not None:
            errors.append(f"{path}: processing workflow must not contain a style LoRA")
    elif lora_node is None or api[lora_node]["inputs"].get("model") != ["1", 0]:
        errors.append(f"{path}: style LoRA is not applied directly to the FLUX.2 base model")
    elif api[lora_node]["inputs"].get("strength_model") != ["19", 0]:
        errors.append(f"{path}: style LoRA must use the visible strength control")
    strength_control = api.get("19", {})
    if not is_processing and (
        strength_control.get("class_type") != "PrimitiveFloat"
        or strength_control.get("inputs", {}).get("value") != 0.7
    ):
        errors.append(f"{path}: visible LoRA strength control must default to 0.70")

    for node_id, node in api.items():
        if node.get("class_type") == "Flux2Scheduler" and node.get("inputs", {}).get("steps") != DEFAULT_STEPS:
            errors.append(
                f"{path}: FLUX.2 scheduler node {node_id} must default to {DEFAULT_STEPS} steps"
            )

    if not is_text_to_image:
        denoise_nodes = {
            node_id: node for node_id, node in api.items() if node.get("class_type") == "SplitSigmasDenoise"
        }
        expected_denoise_count = 4 if is_source else 1
        if len(denoise_nodes) != expected_denoise_count:
            errors.append(f"{path}: expected {expected_denoise_count} editable denoise controls")
        expected_denoise = {"25": 1.0}
        if is_source:
            expected_denoise.update({"45": 1.0, "65": 1.0, "85": 1.0})
        for node_id, node in denoise_nodes.items():
            if node.get("inputs", {}).get("denoise") != expected_denoise.get(node_id):
                errors.append(f"{path}: denoise node {node_id} has the wrong default")
        for node_id, node in api.items():
            if node.get("class_type") != "SamplerCustomAdvanced":
                continue
            sigmas = node.get("inputs", {}).get("sigmas")
            if not (isinstance(sigmas, list) and sigmas[0] in denoise_nodes and sigmas[1] == 1):
                errors.append(
                    f"{path}: image-edit sampler {node_id} must use the low-sigmas output of its denoise control"
                )

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
            if person_prompt != expected:
                errors.append(f"{path}: source identity prompt must use the concise editable default")
            for prompt_id, reference_id in (("40", "43"), ("60", "63"), ("80", "83")):
                if api.get(prompt_id, {}).get("inputs", {}).get("text") != expected:
                    errors.append(f"{path}: candidate prompt {prompt_id} must use the concise editable default")
                if api.get(reference_id, {}).get("inputs", {}).get("conditioning") != [prompt_id, 0]:
                    errors.append(f"{path}: candidate prompt {prompt_id} must affect only its own branch")

    preview_expectations: dict[str, list[Any]] = {}
    if is_text_to_image:
        preview_expectations["70"] = ["66", 0]
        preview_expectations["29"] = ["28", 0]
    elif is_processing:
        preview_expectations.update({"10": ["8", 0], "35": ["32", 0], "70": ["32", 0]})
    elif is_source:
        preview_expectations["35"] = ["32", 0]
        for preview_id, decode_id in (("55", "51"), ("75", "71"), ("95", "91")):
            preview_expectations[preview_id] = [decode_id, 0]
    else:
        preview_expectations.update({"10": ["8", 0], "35": ["31", 0], "55": ["51", 0], "70": ["66", 0]})
    for preview_id, expected_image in preview_expectations.items():
        preview = api.get(preview_id, {})
        if preview.get("class_type") != "PreviewImage" or preview.get("inputs", {}).get("images") != expected_image:
            errors.append(f"{path}: required completed-stage preview node {preview_id} is missing or miswired")

    if not is_processing:
        if is_source:
            background_branches = [
                ("125", "123", "124", "51"),
                ("135", "133", "134", "71"),
                ("145", "143", "144", "91"),
            ]
            if api.get("119", {}).get("class_type") != "PrimitiveBoolean" or api.get("119", {}).get("inputs", {}).get("value") is not False:
                errors.append(f"{path}: source background toggle must be one shared false-by-default PrimitiveBoolean")
            for switch_id, _, _, _ in background_branches:
                if api.get(switch_id, {}).get("inputs", {}).get("switch") != ["119", 0]:
                    errors.append(f"{path}: background switch {switch_id} is not controlled by the shared toggle")
            shared_background = {"120": "LoadImage", "121": "ImageScale", "122": "LoadBackgroundRemovalModel"}
        else:
            background_branches = [("66", "63", "65", "28")]
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
            if api[final_node_id].get("class_type") != "VAEDecode":
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
        if extra.get("flux_restoration_default") is not False:
            errors.append(f"{path}: FLUX restoration must be disabled by default")
        for key in ("candidate_count", "candidate_seed_count", "background_candidate_count"):
            if extra.get(key) != 3:
                errors.append(f"{path}: source metadata {key} must be three")
        switch = api.get("32", {}).get("inputs", {})
        if switch.get("switch") is not False or switch.get("on_false") != ["8", 0] or switch.get("on_true") != ["31", 0]:
            errors.append(f"{path}: FLUX restoration toggle does not keep the direct ESRGAN output")
        if api.get("22", {}).get("inputs", {}).get("pixels") != ["8", 0]:
            errors.append(f"{path}: FLUX restoration does not consume ESRGAN output")
        if api.get("42", {}).get("inputs", {}).get("pixels") != ["32", 0]:
            errors.append(f"{path}: LoRA styling does not consume the restoration switch output")
        if api.get("30", {}).get("inputs", {}).get("latent_image") != ["22", 0]:
            errors.append(f"{path}: FLUX restoration does not start from the encoded cropped portrait")
        style_branches = (("42", "50", "46"), ("62", "70", "66"), ("82", "90", "86"))
        for latent_id, sampler_id, guider_id in style_branches:
            if api.get(latent_id, {}).get("inputs", {}).get("pixels") != ["32", 0]:
                errors.append(f"{path}: LoRA branch {sampler_id} does not consume the restoration switch output")
            if api.get(sampler_id, {}).get("inputs", {}).get("latent_image") != [latent_id, 0]:
                errors.append(f"{path}: LoRA branch {sampler_id} does not start from its encoded restored portrait")
            if api.get(guider_id, {}).get("inputs", {}).get("model") != ["4", 0]:
                errors.append(f"{path}: LoRA branch {sampler_id} is not using the project LoRA model")
    elif is_processing:
        expected = ["RealESRGAN_x2plus", "optional_flux2_klein_9b"]
        if extra.get("restoration_order") != expected:
            errors.append(f"{path}: processing restoration order is wrong")
        if extra.get("flux_restoration_default") is not False:
            errors.append(f"{path}: FLUX restoration must be disabled by default")
        switch = api.get("32", {}).get("inputs", {})
        if switch.get("switch") is not False or switch.get("on_false") != ["8", 0] or switch.get("on_true") != ["31", 0]:
            errors.append(f"{path}: processing restoration toggle does not keep the direct ESRGAN output")
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
        if any(node.get("class_type") == "EmptyFlux2LatentImage" for node in api.values()):
            errors.append(f"{path}: source workflow must not start sampling from an empty latent")
        normalized = api.get("9", {})
        detector = api.get("13", {})
        crop = api.get("11", {})
        silhouette_loader = api.get("155", {})
        silhouette_mask = api.get("156", {})
        manual_box = api.get("15", {})
        manual_crop = api.get("16", {})
        manual_toggle = api.get("17", {})
        crop_switch = api.get("18", {})
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
        ):
            errors.append(f"{path}: source must use the 0.90 adaptive head-and-headwear crop")
        if silhouette_loader.get("class_type") != "LoadBackgroundRemovalModel" or silhouette_mask.get("inputs", {}).get("image") != ["9", 0] or silhouette_mask.get("inputs", {}).get("bg_removal_model") != ["155", 0]:
            errors.append(f"{path}: source silhouette measurement is missing or miswired")
        if manual_box.get("class_type") != "PrimitiveBoundingBox":
            errors.append(f"{path}: difficult sources require a manual bounding-box override")
        manual_inputs = manual_crop.get("inputs", {})
        if manual_crop.get("class_type") != "CropByBBoxes" or manual_inputs.get("image") != ["9", 0] or manual_inputs.get("bboxes") != ["15", 0] or manual_inputs.get("output_width") != 832 or manual_inputs.get("output_height") != 1120:
            errors.append(f"{path}: manual crop override is not connected to the normalized source")
        if manual_toggle.get("class_type") != "PrimitiveBoolean" or manual_toggle.get("inputs", {}).get("value") is not False:
            errors.append(f"{path}: manual crop override must be a one-click toggle that is off by default")
        switch_inputs = crop_switch.get("inputs", {})
        if crop_switch.get("class_type") != "ComfySwitchNode" or switch_inputs.get("switch") != ["17", 0] or switch_inputs.get("on_false") != ["11", 0] or switch_inputs.get("on_true") != ["16", 0]:
            errors.append(f"{path}: automatic/manual crop switch is wired incorrectly")
        if api.get("7", {}).get("inputs", {}).get("image") != ["18", 0]:
            errors.append(f"{path}: ESRGAN must consume the selected head-and-shoulders crop")
        if extra.get("source_crop") != "adaptive_head_and_shoulders_zoom_0.90_before_esrgan":
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
    if len(items) != 3:
        errors.append(f"{manifest_path}: exactly three public workflows are required")
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
