from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..constants import (
    AUTOPROMPTER_PATH,
    GROUP_LABELS,
    HOI4_OPERATIVE_BACKGROUND_RUNTIME_PATH,
    HOI4_OPERATIVE_BACKGROUND_SHA256,
    HOI4_SCIENTIST_BACKGROUND_RUNTIME_PATH,
    HOI4_SCIENTIST_BACKGROUND_SHA256,
    PROFILE_LIMITS,
    RANDOM_PORTRAIT_PROMPT_PATH,
    WORKFLOW_VERSION,
    ExecutionProfile,
)
from ..prompt import autoprompter_instruction, autoprompter_instruction_sha256
from ..util import atomic_json_write, canonical_hash, project_root, sha256_file
from .model import GraphSpec, Link, NodeSpec


CORE_NODES = {
    "UNETLoader",
    "LoraLoaderModelOnly",
    "CLIPLoader",
    "VAELoader",
    "VAEEncode",
    "EmptySD3LatentImage",
    "KSampler",
    "VAEDecode",
    "UpscaleModelLoader",
    "ImageUpscaleWithModel",
    "SaveImage",
}
QWEN_PREPARATION_CORE_NODES = {
    "CFGNorm",
    "FluxKontextImageScale",
    "ModelSamplingAuraFlow",
    "TextEncodeQwenImageEditPlus",
}
RANDOM_PROMPT_CORE_NODES = {
    "UNETLoader",
    "LoraLoaderModelOnly",
    "CLIPLoader",
    "CLIPTextEncode",
    "VAELoader",
    "EmptySD3LatentImage",
    "KSampler",
    "VAEDecode",
    "PreviewImage",
    "SaveImage",
}
PREVIEW_NODE = "PreviewImage"
KREA_NODES = {"Krea2EditModelPatch", "Krea2EditGroundedEncode"}
PROJECT_NODES = {
    "HOI4JobInput",
    "HOI4JobSource",
    "HOI4SourceGuard",
    "HOI4SubjectSelect",
    "HOI4HeadShouldersCrop",
    "HOI4ConservativePrep",
    "HOI4ForegroundMask",
    "HOI4MaskAndBackgroundGuard",
    "HOI4KreaModelLoadBarrier",
    "HOI4PromptInput",
    "HOI4AutopromptClient",
    "HOI4EvidenceExport",
}
QWEN_PREPARATION_PROJECT_NODES = {"HOI4RestorationPrompt"}
HUMAN_ONLY_PROJECT_NODES = {"HOI4HumanControls", "HOI4BundledBackground"}
FORBIDDEN_CLASS_TOKENS = ("faceswap", "face_swap", "ipadapterface", "replacer", "subjectreplacement")
UI_ONLY_NODE_CLASSES = {"Note"}
RANDOM_PROMPT_WORKFLOWS = {
    "hoi4_portraits_no_input_local_nvidia_16gb": {
        "route": "local_nvidia",
        "canvas_width": 832,
        "canvas_height": 1120,
        "human_workflow": True,
    },
    "hoi4_portraits_no_input_full_power_gpu": {
        "route": "runpod",
        "canvas_width": 1196,
        "canvas_height": 1610,
        "human_workflow": True,
    },
    "hoi4_portraits_agent_no_input_local_nvidia_16gb": {
        "route": "local_nvidia",
        "canvas_width": 832,
        "canvas_height": 1120,
        "human_workflow": False,
    },
    "hoi4_portraits_agent_no_input_full_power_gpu": {
        "route": "runpod",
        "canvas_width": 1196,
        "canvas_height": 1610,
        "human_workflow": False,
    },
}
RANDOM_PROMPT_GROUPS = [
    "01 Portrait idea",
    "02 Krea 2 model",
    "03 HOI4 style",
    "04 Generate portrait",
    "05 Preview and save",
]
PREP_WORKFLOW_ID = "hoi4_portraits_prepare_portrait_for_hoi4"
PREP_QWEN_WORKFLOW_ID = "hoi4_portraits_prepare_portrait_qwen"
PREP_BASIC_WORKFLOW_ID = "hoi4_portraits_prepare_portrait_basic"
PREP_WORKFLOW_IDS = {PREP_WORKFLOW_ID, PREP_QWEN_WORKFLOW_ID, PREP_BASIC_WORKFLOW_ID}
PREP_KREA_GROUPS = [
    "01 Choose image",
    "02 Crop portrait",
    "03 Restoration settings",
    "04 Restore with Krea",
    "05 Preview and save",
]
PREP_QWEN_GROUPS = [
    "01 Choose image",
    "02 Crop portrait",
    "03 Restoration settings",
    "04 Restore with Qwen",
    "05 Refine portrait",
    "06 Preview and save",
]
PREP_BASIC_GROUPS = [
    "01 Choose image",
    "02 Crop portrait",
    "03 Enhance portrait",
    "04 Preview and save",
]
LOW_MEMORY_PROFILE_IDS = {
    "hoi4_portraits_local_nvidia_16gb",
    "hoi4_portraits_agent_local_nvidia_16gb",
}
FULL_POWER_PROFILE_IDS = {
    "hoi4_portraits_full_power_gpu",
    "hoi4_portraits_agent_full_power_gpu",
}

# The UI workflow is deliberately laid out as a compact two-row rectangular
# stage board.  The larger input and preview panels are placed beside the
# stage that produces each image, so a human can follow the portrait without
# hunting across the canvas.  These values are presentation metadata only;
# they do not change the execution graph or any locked control.
GROUP_LAYOUT = {
    "00 Portrait setup": (40, 40, 870, 900),
    "01 Choose subject": (940, 40, 500, 900),
    "02 Crop portrait": (1470, 40, 440, 900),
    "03 Prepare portrait": (1940, 40, 440, 980),
    "04 Choose background": (2410, 40, 1550, 900),
    "05 Portrait description": (300, 1020, 500, 720),
    "06 Krea 2 portrait edit": (840, 1020, 900, 780),
    "07 HOI4 portrait style": (1780, 1020, 340, 720),
    "08 Generate portrait": (2160, 1020, 340, 720),
    "09 Preview and save": (2540, 1020, 1080, 720),
}
FULL_POWER_GROUP_LAYOUT = {
    "00 Portrait setup": (40, 40, 870, 900),
    "01 Choose subject": (940, 40, 500, 900),
    "02 Crop portrait": (1470, 40, 440, 900),
    "03 Prepare portrait": (1940, 40, 2200, 980),
    "04 Choose background": (4170, 40, 1550, 900),
    "05 Portrait description": (300, 1050, 500, 720),
    "06 Krea 2 portrait edit": (840, 1050, 1300, 780),
    "07 HOI4 portrait style": (2180, 1050, 340, 720),
    "08 Generate portrait": (2560, 1050, 340, 720),
    "09 Preview and save": (2940, 1050, 2300, 720),
}

GROUP_COLORS = {
    "00 Portrait setup": "#355070",
    "01 Choose subject": "#3a7ca5",
    "02 Crop portrait": "#2a9d8f",
    "03 Prepare portrait": "#588157",
    "04 Choose background": "#527fa3",
    "05 Portrait description": "#8064a2",
    "06 Krea 2 portrait edit": "#6d597a",
    "07 HOI4 portrait style": "#b56576",
    "08 Generate portrait": "#c17817",
    "09 Preview and save": "#457b9d",
}

NODE_COLORS = {
    "00 Portrait setup": ("#1d2f45", "#294866"),
    "01 Choose subject": ("#1f4862", "#2c6d90"),
    "02 Crop portrait": ("#164f49", "#217a70"),
    "03 Prepare portrait": ("#294a2b", "#3d6b40"),
    "04 Choose background": ("#294b61", "#3b6f8d"),
    "05 Portrait description": ("#46375a", "#654c80"),
    "06 Krea 2 portrait edit": ("#40344a", "#5b4a69"),
    "07 HOI4 portrait style": ("#663442", "#914b5e"),
    "08 Generate portrait": ("#66400c", "#945e12"),
    "09 Preview and save": ("#23465b", "#306985"),
}

RANDOM_PROMPT_GROUP_LAYOUT = {
    "01 Portrait idea": (40, 40, 540, 740),
    "02 Krea 2 model": (620, 40, 640, 740),
    "03 HOI4 style": (1300, 40, 340, 740),
    "04 Generate portrait": (40, 790, 980, 520),
    "05 Preview and save": (1060, 790, 1040, 620),
}
RANDOM_PROMPT_GROUP_COLORS = {
    "01 Portrait idea": "#8064a2",
    "02 Krea 2 model": "#6d597a",
    "03 HOI4 style": "#b56576",
    "04 Generate portrait": "#c17817",
    "05 Preview and save": "#457b9d",
}
RANDOM_PROMPT_NODE_COLORS = {
    "01 Portrait idea": ("#46375a", "#654c80"),
    "02 Krea 2 model": ("#40344a", "#5b4a69"),
    "03 HOI4 style": ("#663442", "#914b5e"),
    "04 Generate portrait": ("#66400c", "#945e12"),
    "05 Preview and save": ("#23465b", "#306985"),
}
PREP_GROUP_LAYOUT = {
    "01 Choose image": (40, 40, 760, 520),
    "02 Crop portrait": (840, 40, 760, 520),
    "03 Enhance portrait": (40, 600, 1080, 600),
    "04 Preview and save": (1160, 600, 900, 600),
}
PREP_KREA_GROUP_LAYOUT = {
    "01 Choose image": (40, 40, 760, 560),
    "02 Crop portrait": (840, 40, 760, 560),
    "03 Restoration settings": (1640, 40, 760, 560),
    "04 Restore with Krea": (40, 640, 2680, 940),
    "05 Preview and save": (2760, 640, 1040, 940),
}
PREP_QWEN_GROUP_LAYOUT = {
    "01 Choose image": (40, 40, 760, 560),
    "02 Crop portrait": (840, 40, 760, 560),
    "03 Restoration settings": (1640, 40, 760, 560),
    "04 Restore with Qwen": (40, 640, 2000, 940),
    "05 Refine portrait": (2080, 640, 760, 940),
    "06 Preview and save": (2880, 640, 1040, 940),
}
PREP_GROUP_COLORS = {
    "01 Choose image": "#355070",
    "02 Crop portrait": "#2a9d8f",
    "03 Enhance portrait": "#8064a2",
    "04 Preview and save": "#457b9d",
}
PREP_KREA_GROUP_COLORS = {
    "01 Choose image": "#355070",
    "02 Crop portrait": "#2a9d8f",
    "03 Restoration settings": "#8064a2",
    "04 Restore with Krea": "#6d597a",
    "05 Preview and save": "#457b9d",
}
PREP_QWEN_GROUP_COLORS = {
    "01 Choose image": "#355070",
    "02 Crop portrait": "#2a9d8f",
    "03 Restoration settings": "#8064a2",
    "04 Restore with Qwen": "#6d597a",
    "05 Refine portrait": "#588157",
    "06 Preview and save": "#457b9d",
}
PREP_NODE_COLORS = {
    "01 Choose image": ("#1d2f45", "#294866"),
    "02 Crop portrait": ("#164f49", "#217a70"),
    "03 Enhance portrait": ("#46375a", "#654c80"),
    "04 Preview and save": ("#23465b", "#306985"),
}
PREP_KREA_NODE_COLORS = {
    "01 Choose image": ("#1d2f45", "#294866"),
    "02 Crop portrait": ("#164f49", "#217a70"),
    "03 Restoration settings": ("#46375a", "#654c80"),
    "04 Restore with Krea": ("#40344a", "#5b4a69"),
    "05 Preview and save": ("#23465b", "#306985"),
}
PREP_QWEN_NODE_COLORS = {
    "01 Choose image": ("#1d2f45", "#294866"),
    "02 Crop portrait": ("#164f49", "#217a70"),
    "03 Restoration settings": ("#46375a", "#654c80"),
    "04 Restore with Qwen": ("#40344a", "#5b4a69"),
    "05 Refine portrait": ("#294a2b", "#3d6b40"),
    "06 Preview and save": ("#23465b", "#306985"),
}


def _node(
    node_id: int,
    class_type: str,
    group: str,
    title: str,
    *,
    inputs: dict[str, Any] | None = None,
    input_types: dict[str, str] | None = None,
    outputs: list[str] | None = None,
    output_types: list[str] | None = None,
    pos: tuple[int, int] = (0, 0),
    size: tuple[int, int] = (260, 120),
    widgets: list[Any] | None = None,
    locked: list[str] | None = None,
) -> NodeSpec:
    return NodeSpec(
        node_id=node_id,
        class_type=class_type,
        group=group,
        title=title,
        inputs=inputs or {},
        input_types=input_types or {},
        outputs=outputs or [],
        output_types=output_types or [],
        pos=pos,
        size=size,
        widgets=widgets or [],
        locked=locked or [],
    )


def build_graph(profile: str, root: str | Path | None = None) -> GraphSpec:
    root_path = project_root(root)
    if profile not in PROFILE_LIMITS:
        raise ValueError(f"unknown execution profile: {profile}")
    limits = PROFILE_LIMITS[profile]
    is_human = bool(limits["autoprompter"])
    full_power = profile in FULL_POWER_PROFILE_IDS
    width = int(limits["canvas_width"])
    height = int(limits["canvas_height"])
    group = {label: label for label in GROUP_LABELS}
    instruction = autoprompter_instruction(root_path) if is_human else None
    nodes: list[NodeSpec] = []

    nodes.append(_node(
        1, "HOI4JobInput", group["00 Portrait setup"], "Choose portrait settings",
        inputs={"execution_profile": profile, "job_contract_path": "jobs/<job_id>/input.json", "candidate_count": int(limits["candidate_max"]), "retry_limit": int(limits["retry_max"]), "seed_policy": "derived"},
        input_types={"execution_profile": "STRING", "job_contract_path": "STRING", "candidate_count": "INT", "retry_limit": "INT", "seed_policy": "COMBO"},
        outputs=["job"], output_types=["HOI4_JOB"], pos=(40, 80), widgets=[profile, "jobs/<job_id>/input.json", int(limits["candidate_max"]), int(limits["retry_max"]), "derived"], locked=["execution_profile", "candidate_count", "retry_limit", "seed_policy"],
    ))
    job_node_id = 24 if is_human else 1
    if is_human:
        nodes.append(_node(
            24, "HOI4HumanControls", group["00 Portrait setup"], "Choose input portrait and options",
            inputs={"job": Link(1), "source_image_path": "<from_job_contract>", "subject_selector_mode": "automatic", "face_index": 0, "bbox_left": 0, "bbox_top": 0, "bbox_right": 0, "bbox_bottom": 0, "crop_override_left": 0, "crop_override_top": 0, "crop_override_right": 0, "crop_override_bottom": 0, "approved_background_registry_id": "<from_job_contract>", "background_choice": "Keep current background", "seed_mode": "derived", "fixed_seed": 0, "candidate_count": int(limits["candidate_max"]), "output_job_id": "<job_id_from_contract>"},
            input_types={"job": "HOI4_JOB", "source_image_path": "STRING", "subject_selector_mode": "COMBO", "face_index": "INT", "bbox_left": "INT", "bbox_top": "INT", "bbox_right": "INT", "bbox_bottom": "INT", "crop_override_left": "INT", "crop_override_top": "INT", "crop_override_right": "INT", "crop_override_bottom": "INT", "approved_background_registry_id": "STRING", "background_choice": "COMBO", "seed_mode": "COMBO", "fixed_seed": "INT", "candidate_count": "INT", "output_job_id": "STRING"},
            outputs=["job", "control_meta"], output_types=["HOI4_JOB", "HOI4_META"], pos=(360, 80),
            widgets=["<from_job_contract>", "automatic", 0, 0, 0, 0, 0, 0, 0, 0, "<from_job_contract>", "Keep current background", "derived", 0, int(limits["candidate_max"]), "<job_id_from_contract>"],
        ))
    control_inputs = {"control_meta": Link(24, 1)} if is_human else {}
    control_input_types = {"control_meta": "HOI4_META"} if is_human else {}
    nodes.append(_node(
        2, "HOI4JobSource", group["00 Portrait setup"], "Load input portrait",
        inputs={"job": Link(job_node_id)}, input_types={"job": "HOI4_JOB"}, outputs=["image", "source_meta"], output_types=["IMAGE", "HOI4_META"], pos=(40, 300),
    ))
    nodes.append(_node(
        3, "HOI4SourceGuard", group["00 Portrait setup"], "Check input portrait",
        inputs={"job": Link(job_node_id), "image": Link(2, 0)}, input_types={"job": "HOI4_JOB", "image": "IMAGE"}, outputs=["image", "source_meta"], output_types=["IMAGE", "HOI4_META"], pos=(40, 510),
    ))
    nodes.append(_node(
        4, "HOI4SubjectSelect", group["01 Choose subject"], "Select the subject",
        inputs={"job": Link(job_node_id), "image": Link(3, 0)}, input_types={"job": "HOI4_JOB", "image": "IMAGE"}, outputs=["image", "selection_meta"], output_types=["IMAGE", "HOI4_META"], pos=(360, 80),
    ))
    nodes.append(_node(
        5, "HOI4HeadShouldersCrop", group["02 Crop portrait"], "Crop the portrait",
        inputs={"job": Link(job_node_id), "image": Link(4, 0), "selection_meta": Link(4, 1), **control_inputs}, input_types={"job": "HOI4_JOB", "image": "IMAGE", "selection_meta": "HOI4_META", **control_input_types}, outputs=["image", "crop_meta"], output_types=["IMAGE", "HOI4_META"], pos=(360, 300),
    ))
    if full_power:
        nodes.extend([
            _node(
                40, "HOI4RestorationPrompt", group["03 Prepare portrait"], "Choose portrait restoration",
                inputs={
                    "restoration_mode": "Restore and colorize when needed",
                    "custom_instructions": "",
                },
                input_types={"restoration_mode": "COMBO", "custom_instructions": "STRING"},
                outputs=["restoration_instructions"], output_types=["STRING"],
                widgets=["Restore and colorize when needed", ""],
            ),
            _node(
                41, "VAEEncode", group["03 Prepare portrait"], "Encode portrait for restoration",
                inputs={
                    "pixels": Link(5, 0),
                    "vae": Link(12),
                },
                input_types={"pixels": "IMAGE", "vae": "VAE"},
                outputs=["latent"], output_types=["LATENT"],
            ),
            _node(
                42, "Krea2EditModelPatch", group["03 Prepare portrait"], "Apply restoration reference",
                inputs={
                    "model": Link(11),
                    "source_latent": Link(41),
                    "vae": Link(12),
                    "source_image": Link(5, 0),
                    "fit_mode": "fit",
                    "ref_boost": 1.0,
                },
                input_types={
                    "model": "MODEL",
                    "source_latent": "LATENT",
                    "vae": "VAE",
                    "source_image": "IMAGE",
                    "fit_mode": "COMBO",
                    "ref_boost": "FLOAT",
                },
                outputs=["model"], output_types=["MODEL"],
                widgets=["fit", 1.0], locked=["fit_mode", "ref_boost"],
            ),
            _node(
                43, "Krea2EditGroundedEncode", group["03 Prepare portrait"], "Describe the restoration",
                inputs={"clip": Link(15), "prompt": Link(40), "image": Link(5, 0), "grounding_px": 768},
                input_types={"clip": "CLIP", "prompt": "STRING", "image": "IMAGE", "grounding_px": "INT"},
                outputs=["conditioning"], output_types=["CONDITIONING"],
                widgets=[768], locked=["grounding_px"],
            ),
            _node(
                44, "Krea2EditGroundedEncode", group["03 Prepare portrait"], "Use a neutral restoration negative",
                inputs={"clip": Link(15), "prompt": "", "image": Link(5, 0), "grounding_px": 768},
                input_types={"clip": "CLIP", "prompt": "STRING", "image": "IMAGE", "grounding_px": "INT"},
                outputs=["conditioning"], output_types=["CONDITIONING"],
                widgets=["", 768], locked=["prompt", "grounding_px"],
            ),
            _node(
                45, "EmptySD3LatentImage", group["03 Prepare portrait"], "Set restored portrait size",
                inputs={"width": width, "height": height, "batch_size": 1},
                input_types={"width": "INT", "height": "INT", "batch_size": "INT"},
                outputs=["latent"], output_types=["LATENT"],
                widgets=[width, height, 1], locked=["width", "height", "batch_size"],
            ),
            _node(
                46, "KSampler", group["03 Prepare portrait"], "Restore portrait with Krea",
                inputs={
                    "model": Link(42),
                    "positive": Link(43),
                    "negative": Link(44),
                    "latent_image": Link(45),
                    "seed": 0,
                    "steps": 8,
                    "cfg": 1.0,
                    "sampler_name": "euler",
                    "scheduler": "simple",
                    "denoise": 1.0,
                },
                input_types={
                    "model": "MODEL",
                    "positive": "CONDITIONING",
                    "negative": "CONDITIONING",
                    "latent_image": "LATENT",
                    "seed": "INT",
                    "steps": "INT",
                    "cfg": "FLOAT",
                    "sampler_name": "COMBO",
                    "scheduler": "COMBO",
                    "denoise": "FLOAT",
                },
                outputs=["latent"], output_types=["LATENT"],
                widgets=[0, 8, 1.0, "euler", "simple", 1.0],
                locked=["steps", "cfg", "sampler_name", "scheduler", "denoise"],
            ),
            _node(
                47, "VAEDecode", group["03 Prepare portrait"], "Build restored portrait",
                inputs={"samples": Link(46), "vae": Link(12)},
                input_types={"samples": "LATENT", "vae": "VAE"},
                outputs=["image"], output_types=["IMAGE"],
            ),
        ])
        enhanced_image_link = Link(47)
        preparation_engine = "Krea 2 Turbo restoration"
    else:
        nodes.extend([
            _node(
                36, "UpscaleModelLoader", group["03 Prepare portrait"], "Load AI portrait enhancer",
                inputs={"model_name": "RealESRGAN_x2plus.pth"},
                input_types={"model_name": "COMBO"},
                outputs=["upscale_model"], output_types=["UPSCALE_MODEL"],
                widgets=["RealESRGAN_x2plus.pth"], locked=["model_name"],
            ),
            _node(
                39, "ImageUpscaleWithModel", group["03 Prepare portrait"], "Enhance portrait with AI",
                inputs={"upscale_model": Link(36, 0), "image": Link(5, 0)},
                input_types={"upscale_model": "UPSCALE_MODEL", "image": "IMAGE"},
                outputs=["enhanced_image"], output_types=["IMAGE"],
            ),
        ])
        enhanced_image_link = Link(39)
        preparation_engine = "RealESRGAN x2"
    nodes.append(_node(
        6, "HOI4ConservativePrep", group["03 Prepare portrait"], "Prepare the portrait",
        inputs={
            "job": Link(job_node_id),
            "image": Link(5, 0),
            "crop_meta": Link(5, 1),
            "enhanced_image": enhanced_image_link,
            "preparation_engine": preparation_engine,
            **control_inputs,
        },
        input_types={
            "job": "HOI4_JOB",
            "image": "IMAGE",
            "crop_meta": "HOI4_META",
            "enhanced_image": "IMAGE",
            "preparation_engine": "COMBO",
            **control_input_types,
        },
        outputs=["image", "reference_meta"], output_types=["IMAGE", "HOI4_META"], pos=(360, 520),
        widgets=[preparation_engine], locked=["preparation_engine"],
    ))
    nodes.append(_node(
        7, "HOI4ForegroundMask", group["04 Choose background"], "Separate person from background",
        inputs={"job": Link(job_node_id), "image": Link(6, 0), "reference_meta": Link(6, 1), "mask_model": "BiRefNet"}, input_types={"job": "HOI4_JOB", "image": "IMAGE", "reference_meta": "HOI4_META", "mask_model": "STRING"}, outputs=["image", "mask", "mask_meta"], output_types=["IMAGE", "MASK", "HOI4_META"], pos=(680, 40), widgets=["BiRefNet"], locked=["mask_model"],
    ))
    if is_human:
        nodes.append(_node(
            34, "HOI4BundledBackground", group["04 Choose background"], "HOI4 scientist portrait background",
            inputs={
                "asset_path": HOI4_SCIENTIST_BACKGROUND_RUNTIME_PATH,
                "asset_sha256": HOI4_SCIENTIST_BACKGROUND_SHA256,
            },
            input_types={"asset_path": "STRING", "asset_sha256": "STRING"},
            outputs=["image", "background_details"], output_types=["IMAGE", "HOI4_META"],
            widgets=[HOI4_SCIENTIST_BACKGROUND_RUNTIME_PATH, HOI4_SCIENTIST_BACKGROUND_SHA256],
            locked=["asset_path", "asset_sha256"],
        ))
        nodes.append(_node(
            37, "HOI4BundledBackground", group["04 Choose background"], "HOI4 operative portrait background",
            inputs={
                "asset_path": HOI4_OPERATIVE_BACKGROUND_RUNTIME_PATH,
                "asset_sha256": HOI4_OPERATIVE_BACKGROUND_SHA256,
            },
            input_types={"asset_path": "STRING", "asset_sha256": "STRING"},
            outputs=["image", "background_details"], output_types=["IMAGE", "HOI4_META"],
            widgets=[HOI4_OPERATIVE_BACKGROUND_RUNTIME_PATH, HOI4_OPERATIVE_BACKGROUND_SHA256],
            locked=["asset_path", "asset_sha256"],
        ))
    background_choice_inputs = {
        "control_meta": Link(24, 1),
        "scientist_background": Link(34, 0),
        "scientist_background_meta": Link(34, 1),
        "operative_background": Link(37, 0),
        "operative_background_meta": Link(37, 1),
    } if is_human else {}
    background_choice_input_types = {
        "control_meta": "HOI4_META",
        "scientist_background": "IMAGE",
        "scientist_background_meta": "HOI4_META",
        "operative_background": "IMAGE",
        "operative_background_meta": "HOI4_META",
    } if is_human else {}
    nodes.append(_node(
        8, "HOI4MaskAndBackgroundGuard", group["04 Choose background"], "Choose portrait background",
        inputs={"job": Link(job_node_id), "image": Link(7, 0), "mask": Link(7, 1), "mask_meta": Link(7, 2), **background_choice_inputs},
        input_types={"job": "HOI4_JOB", "image": "IMAGE", "mask": "MASK", "mask_meta": "HOI4_META", **background_choice_input_types},
        outputs=["image", "composite", "mask", "background_meta"], output_types=["IMAGE", "IMAGE", "MASK", "HOI4_META"], pos=(680, 270),
    ))

    if is_human:
        nodes.append(_node(
            9, "HOI4AutopromptClient", group["05 Portrait description"], "Choose automatic or manual description",
            inputs={"job": Link(job_node_id), "image": Link(8, 0), "background_meta": Link(8, 3), "control_meta": Link(24, 1), "description_mode": "Create automatically", "manual_description": "", "instruction_text": instruction, "instruction_path": AUTOPROMPTER_PATH, "model_id": limits["prompt_model"], "prompt_source": "autoprompter"},
            input_types={"job": "HOI4_JOB", "image": "IMAGE", "background_meta": "HOI4_META", "control_meta": "HOI4_META", "description_mode": "COMBO", "manual_description": "STRING", "instruction_text": "STRING", "instruction_path": "STRING", "model_id": "STRING", "prompt_source": "COMBO"},
            outputs=["prompt", "prompt_meta"], output_types=["STRING", "HOI4_META"], pos=(680, 340), size=(460, 520), widgets=["Create automatically", "", instruction, AUTOPROMPTER_PATH, limits["prompt_model"], "autoprompter"], locked=["instruction_text", "instruction_path", "model_id", "prompt_source"],
        ))
    else:
        nodes.append(_node(
            9, "HOI4PromptInput", group["05 Portrait description"], "Use portrait description",
            inputs={"job": Link(job_node_id), "background_meta": Link(8, 3), "prompt_source": "job_contract"}, input_types={"job": "HOI4_JOB", "background_meta": "HOI4_META", "prompt_source": "COMBO"}, outputs=["prompt", "prompt_meta"], output_types=["STRING", "HOI4_META"], pos=(680, 540), widgets=["job_contract"], locked=["prompt_source"],
        ))

    nodes.append(_node(
        10, "UNETLoader", group["06 Krea 2 portrait edit"], "Load Krea 2 Turbo",
        inputs={"unet_name": "krea2_turbo_fp8_scaled.safetensors", "weight_dtype": "default"}, input_types={"unet_name": "COMBO", "weight_dtype": "COMBO"}, outputs=["model"], output_types=["MODEL"], pos=(1000, 80), widgets=["krea2_turbo_fp8_scaled.safetensors", "default"], locked=["unet_name", "weight_dtype"],
    ))
    nodes.append(_node(
        11, "LoraLoaderModelOnly", group["06 Krea 2 portrait edit"], "Preserve identity",
        inputs={"model": Link(10), "lora_name": "krea2_identity_edit_v1_2.safetensors", "strength_model": 1.0}, input_types={"model": "MODEL", "lora_name": "COMBO", "strength_model": "FLOAT"}, outputs=["model"], output_types=["MODEL"], pos=(1000, 260), widgets=["krea2_identity_edit_v1_2.safetensors", 1.0], locked=["lora_name", "strength_model"],
    ))
    nodes.append(_node(
        12, "VAELoader", group["06 Krea 2 portrait edit"], "Prepare image decoder",
        inputs={"vae_name": "qwen_image_vae.safetensors"}, input_types={"vae_name": "COMBO"}, outputs=["vae"], output_types=["VAE"], pos=(1000, 450), widgets=["qwen_image_vae.safetensors"], locked=["vae_name"],
    ))
    nodes.append(_node(
        13, "VAEEncode", group["06 Krea 2 portrait edit"], "Encode reference image",
        inputs={"pixels": Link(8, 1), "vae": Link(12)}, input_types={"pixels": "IMAGE", "vae": "VAE"}, outputs=["latent"], output_types=["LATENT"], pos=(1000, 610),
    ))
    nodes.append(_node(
        14, "Krea2EditModelPatch", group["06 Krea 2 portrait edit"], "Apply identity reference",
        inputs={"model": Link(11), "source_latent": Link(13), "vae": Link(12), "source_image": Link(8, 1), "fit_mode": "fit", "ref_boost": 1.0}, input_types={"model": "MODEL", "source_latent": "LATENT", "vae": "VAE", "source_image": "IMAGE", "fit_mode": "COMBO", "ref_boost": "FLOAT"}, outputs=["model"], output_types=["MODEL"], pos=(1320, 200), widgets=["fit", 1.0], locked=["fit_mode", "ref_boost"],
    ))
    nodes.append(_node(
        15, "CLIPLoader", group["06 Krea 2 portrait edit"], "Read portrait description",
        inputs={"clip_name": "qwen3vl_4b_fp8_scaled.safetensors", "type": "krea2"}, input_types={"clip_name": "COMBO", "type": "COMBO"}, outputs=["clip"], output_types=["CLIP"], pos=(1320, 430), widgets=["qwen3vl_4b_fp8_scaled.safetensors", "krea2"], locked=["clip_name", "type"],
    ))
    nodes.append(_node(
        16, "Krea2EditGroundedEncode", group["06 Krea 2 portrait edit"], "Connect portrait description",
        inputs={"clip": Link(15), "prompt": Link(9, 0), "image": Link(8, 1), "grounding_px": 768}, input_types={"clip": "CLIP", "prompt": "STRING", "image": "IMAGE", "grounding_px": "INT"}, outputs=["conditioning"], output_types=["CONDITIONING"], pos=(1640, 80), widgets=[768], locked=["grounding_px"],
    ))
    nodes.append(_node(
        17, "Krea2EditGroundedEncode", group["06 Krea 2 portrait edit"], "Keep background empty",
        inputs={"clip": Link(15), "prompt": "", "image": Link(8, 1), "grounding_px": 768}, input_types={"clip": "CLIP", "prompt": "STRING", "image": "IMAGE", "grounding_px": "INT"}, outputs=["conditioning"], output_types=["CONDITIONING"], pos=(1640, 290), widgets=["", 768], locked=["prompt", "grounding_px"],
    ))
    nodes.append(_node(
        18, "LoraLoaderModelOnly", group["07 HOI4 portrait style"], "Apply HOI4 portrait style",
        inputs={"model": Link(14), "lora_name": "hoi4_portrait_new_style_lora.safetensors", "strength_model": 0.80}, input_types={"model": "MODEL", "lora_name": "COMBO", "strength_model": "FLOAT"}, outputs=["model"], output_types=["MODEL"], pos=(1960, 200), widgets=["hoi4_portrait_new_style_lora.safetensors", 0.80], locked=["lora_name"],
    ))
    nodes.append(_node(
        29, "HOI4KreaModelLoadBarrier", group["08 Generate portrait"], "Prepare generation",
        inputs={"model": Link(18), "positive": Link(16), "negative": Link(17)}, input_types={"model": "MODEL", "positive": "CONDITIONING", "negative": "CONDITIONING"}, outputs=["model", "positive", "negative"], output_types=["MODEL", "CONDITIONING", "CONDITIONING"], pos=(1320, 620),
    ))
    nodes.append(_node(
        19, "EmptySD3LatentImage", group["08 Generate portrait"], "Set portrait size",
        inputs={"width": width, "height": height, "batch_size": 1}, input_types={"width": "INT", "height": "INT", "batch_size": "INT"}, outputs=["latent"], output_types=["LATENT"], pos=(1960, 430), widgets=[width, height, 1], locked=["width", "height", "batch_size"],
    ))
    nodes.append(_node(
        20, "KSampler", group["08 Generate portrait"], "Generate portrait",
        inputs={"model": Link(29, 0), "positive": Link(29, 1), "negative": Link(29, 2), "latent_image": Link(19), "seed": 0, "steps": 8, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}, input_types={"model": "MODEL", "positive": "CONDITIONING", "negative": "CONDITIONING", "latent_image": "LATENT", "seed": "INT", "steps": "INT", "cfg": "FLOAT", "sampler_name": "COMBO", "scheduler": "COMBO", "denoise": "FLOAT"}, outputs=["latent"], output_types=["LATENT"], pos=(2280, 120), widgets=[0, 8, 1.0, "euler", "simple", 1.0], locked=["steps", "cfg", "sampler_name", "scheduler", "denoise"],
    ))
    nodes.append(_node(
        21, "VAEDecode", group["09 Preview and save"], "Build portrait image",
        inputs={"samples": Link(20), "vae": Link(12)}, input_types={"samples": "LATENT", "vae": "VAE"}, outputs=["image"], output_types=["IMAGE"], pos=(2600, 120),
    ))
    nodes.append(_node(
        22, "HOI4EvidenceExport", group["09 Preview and save"], "Prepare portrait for saving",
        inputs={"job": Link(job_node_id), "source_master": Link(3, 0), "processed_reference": Link(6, 0), "approved_background": Link(8, 1), "candidate": Link(21), "mask": Link(8, 2), "prompt": Link(9, 0), "candidate_index": 0}, input_types={"job": "HOI4_JOB", "source_master": "IMAGE", "processed_reference": "IMAGE", "approved_background": "IMAGE", "candidate": "IMAGE", "mask": "MASK", "prompt": "STRING", "candidate_index": "INT"}, outputs=["image", "evidence_meta"], output_types=["IMAGE", "HOI4_META"], pos=(2920, 120), widgets=[0], locked=["candidate_index"],
    ))
    nodes.append(_node(
        23, "SaveImage", group["09 Preview and save"], "Save portrait PNG",
        inputs={"images": Link(22, 0), "filename_prefix": "evidence/candidates"}, input_types={"images": "IMAGE", "filename_prefix": "STRING"}, outputs=[], output_types=[], pos=(3240, 120), widgets=["evidence/candidates"], locked=["filename_prefix"],
    ))

    if is_human:
        # Human workflows expose the key image checkpoints in the UI.  These
        # nodes are read-only inspection surfaces; the agent graphs remain
        # unchanged and receive their prompt exclusively from the job contract.
        nodes.extend([
            _node(
                25, PREVIEW_NODE, group["02 Crop portrait"], "Cropped portrait",
                inputs={"images": Link(5, 0)}, input_types={"images": "IMAGE"}, outputs=["images"], output_types=["IMAGE"], pos=(4080, 300),
            ),
            _node(
                26, PREVIEW_NODE, group["03 Prepare portrait"], "Prepared portrait",
                inputs={"images": Link(6, 0)}, input_types={"images": "IMAGE"}, outputs=["images"], output_types=["IMAGE"], pos=(4080, 500),
            ),
            _node(
                27, PREVIEW_NODE, group["04 Choose background"], "Background preview",
                inputs={"images": Link(8, 1)}, input_types={"images": "IMAGE"}, outputs=["images"], output_types=["IMAGE"], pos=(4390, 500),
            ),
            _node(
                28, PREVIEW_NODE, group["09 Preview and save"], "Saved portrait preview",
                inputs={"images": Link(22, 0)}, input_types={"images": "IMAGE"}, outputs=["images"], output_types=["IMAGE"], pos=(4690, 300),
            ),
            _node(
                30, PREVIEW_NODE, group["01 Choose subject"], "Input portrait preview",
                inputs={"images": Link(3, 0)}, input_types={"images": "IMAGE"}, outputs=["images"], output_types=["IMAGE"], pos=(870, 280),
            ),
            _node(
                35, PREVIEW_NODE, group["04 Choose background"], "Scientist background preview",
                inputs={"images": Link(34, 0)}, input_types={"images": "IMAGE"}, outputs=["images"], output_types=["IMAGE"],
            ),
            _node(
                38, PREVIEW_NODE, group["04 Choose background"], "Operative background preview",
                inputs={"images": Link(37, 0)}, input_types={"images": "IMAGE"}, outputs=["images"], output_types=["IMAGE"],
            ),
        ])
        if full_power:
            nodes.append(_node(
                54, PREVIEW_NODE, group["03 Prepare portrait"], "Krea restoration preview",
                inputs={"images": Link(47, 0)}, input_types={"images": "IMAGE"},
                outputs=["images"], output_types=["IMAGE"],
            ))

    if profile in LOW_MEMORY_PROFILE_IDS:
        # These are deliberately UI-only notes.  They make the lower-memory
        # choices discoverable without putting an unverified GGUF loader into
        # the executable API graph.
        nodes.extend([
            _node(
                31, "Note", group["06 Krea 2 portrait edit"], "Lower-memory model options",
                widgets=["The included model is active. You can connect a compatible 12 GB or 8 GB Krea 2 GGUF model here after installing it."],
            ),
            _node(
                32, "Note", group["06 Krea 2 portrait edit"], "Use a 12 GB GGUF model",
                widgets=["This node is not connected. Install a compatible Krea 2 GGUF model, then connect its loader here."],
            ),
            _node(
                33, "Note", group["06 Krea 2 portrait edit"], "Use an 8 GB GGUF model",
                widgets=["This node is not connected. Install a compatible Krea 2 GGUF model, then connect its loader here."],
            ),
        ])

    _apply_visual_layout(nodes, is_human=is_human, full_power=full_power)

    metadata = {
        "schema_version": "1.0.0",
        "graph_spec_version": WORKFLOW_VERSION,
        "workflow_id": profile,
        "execution_profile": profile,
        "route": limits["route"],
        "human_workflow": is_human,
        "autoprompter": is_human,
        "autoprompter_instruction_path": AUTOPROMPTER_PATH if is_human else None,
        "autoprompter_instruction_sha256": autoprompter_instruction_sha256(root_path) if is_human else None,
        "prompt_source": "automatic_or_manual" if is_human else "job_contract",
        "prompt_model": limits["prompt_model"],
        "controlnet_policy": "not_included; no approved live-compatible ControlNet experiment demonstrated a benefit over the Krea identity reference, mask, and approved-background route",
        "remote_authentication": "authenticated_runpod_gateway" if limits["route"] == "runpod" else "loopback_only",
        "identity_policy": "identity_edit_only; replacement_routes_are_not_in_the_graph",
        "work_canvas": {"width": width, "height": height, "pixels": width * height},
        "final_canvas": {"width": 156, "height": 210},
        "required_groups": GROUP_LABELS,
        "locked_controls": {node.title: node.locked for node in nodes if node.locked},
        "required_core_nodes": sorted(
            (CORE_NODES - {"UpscaleModelLoader", "ImageUpscaleWithModel"} if full_power else CORE_NODES)
            | ({PREVIEW_NODE} if is_human else set())
        ),
        "required_preparation_nodes": (
            sorted({"EmptySD3LatentImage", "KSampler", "Krea2EditGroundedEncode", "Krea2EditModelPatch", "VAEDecode", "VAEEncode", "HOI4ConservativePrep", "HOI4RestorationPrompt"})
            if full_power
            else ["UpscaleModelLoader", "ImageUpscaleWithModel", "HOI4ConservativePrep"]
        ),
        "preparation_model": (
            "krea2_turbo_fp8_scaled.safetensors"
            if full_power
            else "RealESRGAN_x2plus.pth"
        ),
        "preparation_engine": "krea2_edit_restoration" if full_power else "realesrgan_x2",
        "colorization": full_power,
        "preview_nodes": [node.title for node in nodes if node.class_type == PREVIEW_NODE],
        "final_preview_save_pair": {
            "preview_node_id": 28 if is_human else None,
            "save_node_id": 23,
            "shared_source_node_id": 22,
            "shared_source_slot": 0,
            "policy": "human_final_preview_and_save_consume_the_same_evidence_export_image" if is_human else "agent_save_only",
        },
        "required_krea_nodes": sorted(KREA_NODES),
        "required_project_nodes": sorted(
            (
                PROJECT_NODES
                | (QWEN_PREPARATION_PROJECT_NODES if full_power else set())
                | (HUMAN_ONLY_PROJECT_NODES if is_human else set())
            )
            & {node.class_type for node in nodes}
        ),
        "candidate_budget": {"max": int(limits["candidate_max"]), "retry_max": int(limits["retry_max"])},
        "finalization_policy": "controller_only_after_independent_audit_all_pass; no DDS node is present in the workflow",
        "low_memory_placeholder_nodes": [
            {"node_id": node.node_id, "title": node.title, "connected": False, "ui_only": True}
            for node in nodes if node.class_type == "Note"
        ],
    }
    graph = GraphSpec(profile, profile, nodes, GROUP_LABELS, metadata)
    validate_graph(graph)
    return graph


def build_random_prompt_graph(workflow_id: str, root: str | Path | None = None) -> GraphSpec:
    """Build a standalone text-to-image portrait workflow with no source image."""

    root_path = project_root(root)
    if workflow_id not in RANDOM_PROMPT_WORKFLOWS:
        raise ValueError(f"unknown random prompt workflow: {workflow_id}")
    settings = RANDOM_PROMPT_WORKFLOWS[workflow_id]
    is_human = bool(settings["human_workflow"])
    width = int(settings["canvas_width"])
    height = int(settings["canvas_height"])
    instruction_path = root_path / RANDOM_PORTRAIT_PROMPT_PATH
    instruction = instruction_path.read_text(encoding="utf-8")
    groups = RANDOM_PROMPT_GROUPS
    prompt_node = (
        _node(
            1, "HOI4RandomPortraitPrompt", groups[0], "Choose random or write your own prompt",
            inputs={
                "prompt_mode": "Create a random portrait",
                "manual_prompt": "",
                "character_brief": "",
                "country_influence": "random",
                "role": "random",
                "presentation": "random",
                "age": "random",
                "expression": "random",
                "seed": 0,
                "instruction_text": instruction,
                "instruction_path": RANDOM_PORTRAIT_PROMPT_PATH,
            },
            input_types={
                "prompt_mode": "COMBO",
                "manual_prompt": "STRING",
                "character_brief": "STRING",
                "country_influence": "COMBO",
                "role": "COMBO",
                "presentation": "COMBO",
                "age": "COMBO",
                "expression": "COMBO",
                "seed": "INT",
                "instruction_text": "STRING",
                "instruction_path": "STRING",
            },
            outputs=["prompt", "prompt_details", "seed"], output_types=["STRING", "HOI4_META", "INT"],
            pos=(80, 100), size=(500, 680),
            widgets=["Create a random portrait", "", "", "random", "random", "random", "random", "random", 0, instruction, RANDOM_PORTRAIT_PROMPT_PATH],
            locked=["instruction_text", "instruction_path"],
        )
        if is_human
        else _node(
            1, "HOI4PromptJobInput", groups[0], "Load portrait description",
            inputs={
                "execution_profile": workflow_id,
                "job_contract_path": "jobs/<job_id>/input.json",
                "candidate_count": 2 if "local" in workflow_id else 6,
                "retry_limit": 2,
                "seed_policy": "derived",
            },
            input_types={
                "execution_profile": "STRING",
                "job_contract_path": "STRING",
                "candidate_count": "INT",
                "retry_limit": "INT",
                "seed_policy": "COMBO",
            },
            outputs=["job", "prompt", "prompt_details", "seed"],
            output_types=["HOI4_JOB", "STRING", "HOI4_META", "INT"],
            pos=(80, 100), size=(460, 300),
            widgets=[workflow_id, "jobs/<job_id>/input.json", 2 if "local" in workflow_id else 6, 2, "derived"],
            locked=["execution_profile", "candidate_count", "retry_limit", "seed_policy"],
        )
    )
    nodes = [
        prompt_node,
        _node(
            2, "UNETLoader", groups[1], "Load Krea 2 Turbo",
            inputs={"unet_name": "krea2_turbo_fp8_scaled.safetensors", "weight_dtype": "default"},
            input_types={"unet_name": "COMBO", "weight_dtype": "COMBO"},
            outputs=["model"], output_types=["MODEL"], pos=(660, 100), size=(280, 150),
            widgets=["krea2_turbo_fp8_scaled.safetensors", "default"], locked=["unet_name", "weight_dtype"],
        ),
        _node(
            3, "CLIPLoader", groups[1], "Load portrait text encoder",
            inputs={"clip_name": "qwen3vl_4b_fp8_scaled.safetensors", "type": "krea2"},
            input_types={"clip_name": "COMBO", "type": "COMBO"},
            outputs=["clip"], output_types=["CLIP"], pos=(660, 300), size=(280, 150),
            widgets=["qwen3vl_4b_fp8_scaled.safetensors", "krea2"], locked=["clip_name", "type"],
        ),
        _node(
            4, "VAELoader", groups[1], "Load image decoder",
            inputs={"vae_name": "qwen_image_vae.safetensors"}, input_types={"vae_name": "COMBO"},
            outputs=["vae"], output_types=["VAE"], pos=(660, 500), size=(280, 140),
            widgets=["qwen_image_vae.safetensors"], locked=["vae_name"],
        ),
        _node(
            5, "LoraLoaderModelOnly", groups[2], "Apply HOI4 portrait style",
            inputs={"model": Link(2), "lora_name": "hoi4_portrait_new_style_lora.safetensors", "strength_model": 0.80},
            input_types={"model": "MODEL", "lora_name": "COMBO", "strength_model": "FLOAT"},
            outputs=["model"], output_types=["MODEL"], pos=(1340, 220), size=(260, 180),
            widgets=["hoi4_portrait_new_style_lora.safetensors", 0.80], locked=["lora_name"],
        ),
        _node(
            6, "CLIPTextEncode", groups[1], "Turn the portrait idea into conditioning",
            inputs={"text": Link(1, 0 if is_human else 1), "clip": Link(3)}, input_types={"text": "STRING", "clip": "CLIP"},
            outputs=["conditioning"], output_types=["CONDITIONING"], pos=(960, 100), size=(260, 180),
        ),
        _node(
            7, "CLIPTextEncode", groups[1], "Use an empty negative prompt",
            inputs={"text": "", "clip": Link(3)}, input_types={"text": "STRING", "clip": "CLIP"},
            outputs=["conditioning"], output_types=["CONDITIONING"], pos=(960, 360), size=(260, 180),
            widgets=[""], locked=["text"],
        ),
        _node(
            8, "EmptySD3LatentImage", groups[3], "Set portrait size",
            inputs={"width": width, "height": height, "batch_size": 1},
            input_types={"width": "INT", "height": "INT", "batch_size": "INT"},
            outputs=["latent"], output_types=["LATENT"], pos=(80, 860), size=(280, 160),
            widgets=[width, height, 1], locked=["width", "height", "batch_size"],
        ),
        _node(
            9, "HOI4KreaModelLoadBarrier", groups[3], "Prepare generation",
            inputs={"model": Link(5), "positive": Link(6), "negative": Link(7)},
            input_types={"model": "MODEL", "positive": "CONDITIONING", "negative": "CONDITIONING"},
            outputs=["model", "positive", "negative"], output_types=["MODEL", "CONDITIONING", "CONDITIONING"],
            pos=(400, 860), size=(260, 140),
        ),
        _node(
            10, "KSampler", groups[3], "Generate a new portrait",
            inputs={
                "model": Link(9, 0), "positive": Link(9, 1), "negative": Link(9, 2), "latent_image": Link(8),
                "seed": Link(1, 2 if is_human else 3), "steps": 8, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0,
            },
            input_types={
                "model": "MODEL", "positive": "CONDITIONING", "negative": "CONDITIONING", "latent_image": "LATENT",
                "seed": "INT", "steps": "INT", "cfg": "FLOAT", "sampler_name": "COMBO", "scheduler": "COMBO", "denoise": "FLOAT",
            },
            outputs=["latent"], output_types=["LATENT"], pos=(700, 850), size=(280, 220),
            widgets=[8, 1.0, "euler", "simple", 1.0],
            locked=["steps", "cfg", "sampler_name", "scheduler", "denoise"],
        ),
        _node(
            11, "VAEDecode", groups[4], "Build portrait image",
            inputs={"samples": Link(10), "vae": Link(4)}, input_types={"samples": "LATENT", "vae": "VAE"},
            outputs=["image"], output_types=["IMAGE"], pos=(1100, 850), size=(260, 140),
        ),
        _node(
            12, PREVIEW_NODE, groups[4], "Portrait preview",
            inputs={"images": Link(11)}, input_types={"images": "IMAGE"},
            outputs=["images"], output_types=["IMAGE"], pos=(1390, 850), size=(380, 500),
        ),
        _node(
            13, "SaveImage", groups[4], "Save portrait PNG",
            inputs={"images": Link(11), "filename_prefix": "hoi4_portraits/random"},
            input_types={"images": "IMAGE", "filename_prefix": "STRING"},
            pos=(1800, 850), size=(260, 180), widgets=["hoi4_portraits/random"], locked=["filename_prefix"],
        ),
    ]
    if not is_human:
        nodes = [node for node in nodes if node.class_type != PREVIEW_NODE]
    metadata = {
        "schema_version": "1.0.0",
        "graph_spec_version": WORKFLOW_VERSION,
        "workflow_id": workflow_id,
        "profile": workflow_id,
        "execution_profile": workflow_id,
        "workflow_kind": "random_text_to_image",
        "route": settings["route"],
        "human_workflow": is_human,
        "autoprompter": is_human,
        "autoprompter_kind": "deterministic_text_only" if is_human else None,
        "autoprompter_instruction_path": RANDOM_PORTRAIT_PROMPT_PATH if is_human else None,
        "autoprompter_instruction_sha256": sha256_file(instruction_path) if is_human else None,
        "prompt_source": "random_builder_or_manual" if is_human else "job_contract",
        "prompt_model": None,
        "source_image_required": False,
        "vision_model_required": False,
        "controlnet_policy": "not_used",
        "identity_policy": "fictional_portraits_only",
        "remote_authentication": "authenticated_runpod_gateway" if settings["route"] == "runpod" else "loopback_only",
        "work_canvas": {"width": width, "height": height, "pixels": width * height},
        "final_canvas": {"width": 156, "height": 210},
        "required_groups": groups,
        "locked_controls": {node.title: node.locked for node in nodes if node.locked},
        "required_core_nodes": sorted(RANDOM_PROMPT_CORE_NODES if is_human else RANDOM_PROMPT_CORE_NODES - {PREVIEW_NODE}),
        "required_krea_nodes": [],
        "required_project_nodes": [
            "HOI4KreaModelLoadBarrier",
            "HOI4RandomPortraitPrompt" if is_human else "HOI4PromptJobInput",
        ],
        "preview_nodes": ["Portrait preview"] if is_human else [],
        "final_preview_save_pair": {
            "preview_node_id": 12 if is_human else None,
            "save_node_id": 13,
            "shared_source_node_id": 11,
            "shared_source_slot": 0,
            "policy": "preview_and_save_consume_the_same_decoded_image" if is_human else "agent_save_only",
        },
        "low_memory_placeholder_nodes": [],
    }
    graph = GraphSpec(workflow_id, workflow_id, nodes, groups, metadata)
    validate_graph(graph)
    return graph


def build_preparation_graph(
    root: str | Path | None = None,
    workflow_id: str = PREP_WORKFLOW_ID,
) -> GraphSpec:
    """Build one of the standalone input-photo preparation workflows."""

    project_root(root)
    if workflow_id not in PREP_WORKFLOW_IDS:
        raise ValueError(f"unknown portrait preparation workflow: {workflow_id}")
    krea_enhanced = workflow_id == PREP_WORKFLOW_ID
    qwen_enhanced = workflow_id == PREP_QWEN_WORKFLOW_ID
    ai_enhanced = krea_enhanced or qwen_enhanced
    groups = PREP_KREA_GROUPS if krea_enhanced else PREP_QWEN_GROUPS if qwen_enhanced else PREP_BASIC_GROUPS
    nodes: list[NodeSpec] = [
        _node(
            1, "LoadImage", groups[0], "Choose portrait photo",
            inputs={"image": "hoi4_preparation_example.jpg"}, input_types={"image": "COMBO"},
            outputs=["image", "mask"], output_types=["IMAGE", "MASK"],
            pos=(80, 100), size=(300, 180), widgets=["hoi4_preparation_example.jpg", "image"],
        ),
        _node(
            2, PREVIEW_NODE, groups[0], "Input image preview",
            inputs={"images": Link(1, 0)}, input_types={"images": "IMAGE"},
            outputs=["images"], output_types=["IMAGE"],
            pos=(400, 80), size=(360, 420),
        ),
        _node(
            3, "HOI4PortraitCrop", groups[1], "Crop to head and shoulders",
            inputs={"image": Link(1, 0), "face_index": 0, "framing": "Normal head and shoulders"},
            input_types={"image": "IMAGE", "face_index": "INT", "framing": "COMBO"},
            outputs=["cropped_portrait", "crop_details"], output_types=["IMAGE", "HOI4_META"],
            pos=(880, 100), size=(320, 180),
            widgets=[0, "Normal head and shoulders"],
        ),
        _node(
            4, PREVIEW_NODE, groups[1], "Head-and-shoulders preview",
            inputs={"images": Link(3, 0)}, input_types={"images": "IMAGE"},
            outputs=["images"], output_types=["IMAGE"],
            pos=(1220, 80), size=(340, 420),
        ),
    ]
    if krea_enhanced:
        nodes.extend([
            _node(
                5, "HOI4RestorationPrompt", groups[2], "Choose portrait restoration",
                inputs={
                    "restoration_mode": "Restore and colorize when needed",
                    "custom_instructions": "",
                },
                input_types={"restoration_mode": "COMBO", "custom_instructions": "STRING"},
                outputs=["restoration_instructions"], output_types=["STRING"],
                pos=(1680, 100), size=(680, 460),
                widgets=["Restore and colorize when needed", ""],
            ),
            _node(
                6, "UNETLoader", groups[3], "Load Krea 2 Turbo",
                inputs={"unet_name": "krea2_turbo_fp8_scaled.safetensors", "weight_dtype": "default"},
                input_types={"unet_name": "COMBO", "weight_dtype": "COMBO"},
                outputs=["model"], output_types=["MODEL"],
                pos=(80, 700), size=(300, 140),
                widgets=["krea2_turbo_fp8_scaled.safetensors", "default"],
                locked=["unet_name", "weight_dtype"],
            ),
            _node(
                7, "LoraLoaderModelOnly", groups[3], "Preserve identity",
                inputs={"model": Link(6), "lora_name": "krea2_identity_edit_v1_2.safetensors", "strength_model": 1.0},
                input_types={"model": "MODEL", "lora_name": "COMBO", "strength_model": "FLOAT"},
                outputs=["model"], output_types=["MODEL"],
                pos=(420, 700), size=(300, 140),
                widgets=["krea2_identity_edit_v1_2.safetensors", 1.0],
                locked=["lora_name", "strength_model"],
            ),
            _node(
                8, "VAELoader", groups[3], "Load image decoder",
                inputs={"vae_name": "qwen_image_vae.safetensors"},
                input_types={"vae_name": "COMBO"},
                outputs=["vae"], output_types=["VAE"],
                pos=(420, 880), size=(300, 140),
                widgets=["qwen_image_vae.safetensors"], locked=["vae_name"],
            ),
            _node(
                9, "VAEEncode", groups[3], "Encode portrait reference",
                inputs={"pixels": Link(3), "vae": Link(8)},
                input_types={"pixels": "IMAGE", "vae": "VAE"},
                outputs=["latent"], output_types=["LATENT"],
                pos=(760, 700), size=(320, 140),
            ),
            _node(
                10, "Krea2EditModelPatch", groups[3], "Apply restoration reference",
                inputs={
                    "model": Link(7),
                    "source_latent": Link(9),
                    "vae": Link(8),
                    "source_image": Link(3),
                    "fit_mode": "fit",
                    "ref_boost": 1.0,
                },
                input_types={
                    "model": "MODEL",
                    "source_latent": "LATENT",
                    "vae": "VAE",
                    "source_image": "IMAGE",
                    "fit_mode": "COMBO",
                    "ref_boost": "FLOAT",
                },
                outputs=["model"], output_types=["MODEL"],
                pos=(1120, 700), size=(340, 180),
                widgets=["fit", 1.0], locked=["fit_mode", "ref_boost"],
            ),
            _node(
                11, "CLIPLoader", groups[3], "Load Krea image understanding",
                inputs={"clip_name": "qwen3vl_4b_fp8_scaled.safetensors", "type": "krea2"},
                input_types={"clip_name": "COMBO", "type": "COMBO"},
                outputs=["clip"], output_types=["CLIP"],
                pos=(760, 880), size=(320, 140),
                widgets=["qwen3vl_4b_fp8_scaled.safetensors", "krea2"],
                locked=["clip_name", "type"],
            ),
            _node(
                12, "Krea2EditGroundedEncode", groups[3], "Describe the restoration",
                inputs={"clip": Link(11), "prompt": Link(5), "image": Link(3), "grounding_px": 768},
                input_types={"clip": "CLIP", "prompt": "STRING", "image": "IMAGE", "grounding_px": "INT"},
                outputs=["conditioning"], output_types=["CONDITIONING"],
                pos=(1120, 920), size=(340, 180),
                widgets=[768], locked=["grounding_px"],
            ),
            _node(
                13, "Krea2EditGroundedEncode", groups[3], "Use a neutral negative prompt",
                inputs={"clip": Link(11), "prompt": "", "image": Link(3), "grounding_px": 768},
                input_types={"clip": "CLIP", "prompt": "STRING", "image": "IMAGE", "grounding_px": "INT"},
                outputs=["conditioning"], output_types=["CONDITIONING"],
                pos=(1120, 1140), size=(340, 180),
                widgets=["", 768], locked=["prompt", "grounding_px"],
            ),
            _node(
                14, "EmptySD3LatentImage", groups[3], "Set prepared portrait size",
                inputs={"width": 832, "height": 1120, "batch_size": 1},
                input_types={"width": "INT", "height": "INT", "batch_size": "INT"},
                outputs=["latent"], output_types=["LATENT"],
                pos=(1500, 700), size=(320, 150),
                widgets=[832, 1120, 1], locked=["width", "height", "batch_size"],
            ),
            _node(
                15, "KSampler", groups[3], "Restore portrait with Krea",
                inputs={
                    "model": Link(10),
                    "positive": Link(12),
                    "negative": Link(13),
                    "latent_image": Link(14),
                    "seed": 0,
                    "steps": 8,
                    "cfg": 1.0,
                    "sampler_name": "euler",
                    "scheduler": "simple",
                    "denoise": 1.0,
                },
                input_types={
                    "model": "MODEL",
                    "positive": "CONDITIONING",
                    "negative": "CONDITIONING",
                    "latent_image": "LATENT",
                    "seed": "INT",
                    "steps": "INT",
                    "cfg": "FLOAT",
                    "sampler_name": "COMBO",
                    "scheduler": "COMBO",
                    "denoise": "FLOAT",
                },
                outputs=["latent"], output_types=["LATENT"],
                pos=(1500, 900), size=(340, 220),
                widgets=[0, 8, 1.0, "euler", "simple", 1.0],
                locked=["steps", "cfg", "sampler_name", "scheduler", "denoise"],
            ),
            _node(
                16, "VAEDecode", groups[3], "Build restored portrait",
                inputs={"samples": Link(15), "vae": Link(8)},
                input_types={"samples": "LATENT", "vae": "VAE"},
                outputs=["image"], output_types=["IMAGE"],
                pos=(1880, 700), size=(320, 140),
            ),
            _node(
                17, "HOI4FinishPreparedPortrait", groups[3], "Fit restored portrait for HOI4",
                inputs={"image": Link(16), "contrast": 1.0, "sharpness": 1.0},
                input_types={"image": "IMAGE", "contrast": "FLOAT", "sharpness": "FLOAT"},
                outputs=["prepared_portrait"], output_types=["IMAGE"],
                pos=(1880, 880), size=(320, 150),
                widgets=[1.0, 1.0],
            ),
            _node(
                18, PREVIEW_NODE, groups[3], "Krea restoration preview",
                inputs={"images": Link(17)}, input_types={"images": "IMAGE"},
                outputs=["images"], output_types=["IMAGE"],
                pos=(2240, 700), size=(440, 820),
            ),
            _node(
                19, PREVIEW_NODE, groups[4], "Prepared portrait preview",
                inputs={"images": Link(17)}, input_types={"images": "IMAGE"},
                outputs=["images"], output_types=["IMAGE"],
                pos=(2800, 700), size=(500, 650),
            ),
            _node(
                20, "SaveImage", groups[4], "Save prepared portrait",
                inputs={"images": Link(17), "filename_prefix": "hoi4_portraits/prepared_krea"},
                input_types={"images": "IMAGE", "filename_prefix": "STRING"},
                pos=(3340, 700), size=(400, 180),
                widgets=["hoi4_portraits/prepared_krea"], locked=["filename_prefix"],
            ),
        ])
        preview_nodes = [
            "Input image preview",
            "Head-and-shoulders preview",
            "Krea restoration preview",
            "Prepared portrait preview",
        ]
        required_core_nodes = sorted({
            "CLIPLoader",
            "EmptySD3LatentImage",
            "KSampler",
            "LoadImage",
            "LoraLoaderModelOnly",
            "PreviewImage",
            "SaveImage",
            "UNETLoader",
            "VAEDecode",
            "VAEEncode",
            "VAELoader",
        })
        final_preview_id, save_id, final_source_id = 19, 20, 17
    elif qwen_enhanced:
        nodes.extend([
            _node(
                5, "HOI4RestorationPrompt", groups[2], "Choose portrait restoration",
                inputs={
                    "restoration_mode": "Restore and colorize when needed",
                    "custom_instructions": "",
                },
                input_types={"restoration_mode": "COMBO", "custom_instructions": "STRING"},
                outputs=["restoration_instructions"], output_types=["STRING"],
                pos=(1680, 100), size=(680, 460),
                widgets=["Restore and colorize when needed", ""],
            ),
            _node(
                6, "FluxKontextImageScale", groups[3], "Scale portrait for Qwen",
                inputs={"image": Link(3)}, input_types={"image": "IMAGE"},
                outputs=["scaled_portrait"], output_types=["IMAGE"],
                pos=(80, 700), size=(320, 140),
            ),
            _node(
                7, "UNETLoader", groups[3], "Load Qwen portrait restorer",
                inputs={
                    "unet_name": "qwen_image_edit_2511_fp8mixed.safetensors",
                    "weight_dtype": "default",
                },
                input_types={"unet_name": "COMBO", "weight_dtype": "COMBO"},
                outputs=["model"], output_types=["MODEL"],
                pos=(440, 700), size=(300, 140),
                widgets=["qwen_image_edit_2511_fp8mixed.safetensors", "default"],
                locked=["unet_name", "weight_dtype"],
            ),
            _node(
                8, "CLIPLoader", groups[3], "Load Qwen image understanding",
                inputs={
                    "clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors",
                    "type": "qwen_image",
                    "device": "default",
                },
                input_types={"clip_name": "COMBO", "type": "COMBO", "device": "COMBO"},
                outputs=["clip"], output_types=["CLIP"],
                pos=(440, 870), size=(300, 140),
                widgets=["qwen_2.5_vl_7b_fp8_scaled.safetensors", "qwen_image", "default"],
                locked=["clip_name", "type", "device"],
            ),
            _node(
                9, "VAELoader", groups[3], "Load Qwen image decoder",
                inputs={"vae_name": "qwen_image_vae.safetensors"},
                input_types={"vae_name": "COMBO"},
                outputs=["vae"], output_types=["VAE"],
                pos=(440, 1040), size=(300, 140),
                widgets=["qwen_image_vae.safetensors"], locked=["vae_name"],
            ),
            _node(
                10, "TextEncodeQwenImageEditPlus", groups[3], "Describe the restoration",
                inputs={
                    "clip": Link(8),
                    "prompt": Link(5),
                    "vae": Link(9),
                    "image1": Link(6),
                },
                input_types={"clip": "CLIP", "prompt": "STRING", "vae": "VAE", "image1": "IMAGE"},
                outputs=["conditioning"], output_types=["CONDITIONING"],
                pos=(780, 700), size=(360, 220),
            ),
            _node(
                11, "TextEncodeQwenImageEditPlus", groups[3], "Use a neutral negative prompt",
                inputs={
                    "clip": Link(8),
                    "prompt": "",
                    "vae": Link(9),
                    "image1": Link(6),
                },
                input_types={"clip": "CLIP", "prompt": "STRING", "vae": "VAE", "image1": "IMAGE"},
                outputs=["conditioning"], output_types=["CONDITIONING"],
                pos=(780, 960), size=(360, 200),
                widgets=[""], locked=["prompt"],
            ),
            _node(
                12, "VAEEncode", groups[3], "Encode portrait for restoration",
                inputs={"pixels": Link(6), "vae": Link(9)},
                input_types={"pixels": "IMAGE", "vae": "VAE"},
                outputs=["latent"], output_types=["LATENT"],
                pos=(780, 1200), size=(360, 140),
            ),
            _node(
                13, "ModelSamplingAuraFlow", groups[3], "Set Qwen image sampling",
                inputs={"model": Link(7), "shift": 3.1},
                input_types={"model": "MODEL", "shift": "FLOAT"},
                outputs=["model"], output_types=["MODEL"],
                pos=(1180, 700), size=(340, 130),
                widgets=[3.1], locked=["shift"],
            ),
            _node(
                14, "CFGNorm", groups[3], "Keep restoration balanced",
                inputs={"model": Link(13), "strength": 1.0, "pre_cfg": False},
                input_types={"model": "MODEL", "strength": "FLOAT", "pre_cfg": "BOOLEAN"},
                outputs=["model"], output_types=["MODEL"],
                pos=(1180, 870), size=(340, 130),
                widgets=[1.0, False], locked=["strength", "pre_cfg"],
            ),
            _node(
                15, "KSampler", groups[3], "Restore portrait with Qwen",
                inputs={
                    "model": Link(14),
                    "positive": Link(10),
                    "negative": Link(11),
                    "latent_image": Link(12),
                    "seed": 0,
                    "steps": 40,
                    "cfg": 4.0,
                    "sampler_name": "euler",
                    "scheduler": "simple",
                    "denoise": 1.0,
                },
                input_types={
                    "model": "MODEL",
                    "positive": "CONDITIONING",
                    "negative": "CONDITIONING",
                    "latent_image": "LATENT",
                    "seed": "INT",
                    "steps": "INT",
                    "cfg": "FLOAT",
                    "sampler_name": "COMBO",
                    "scheduler": "COMBO",
                    "denoise": "FLOAT",
                },
                outputs=["latent"], output_types=["LATENT"],
                pos=(1180, 1040), size=(340, 220),
                widgets=[0, 40, 4.0, "euler", "simple", 1.0],
                locked=["steps", "cfg", "sampler_name", "scheduler", "denoise"],
            ),
            _node(
                16, "VAEDecode", groups[3], "Build restored portrait",
                inputs={"samples": Link(15), "vae": Link(9)},
                input_types={"samples": "LATENT", "vae": "VAE"},
                outputs=["image"], output_types=["IMAGE"],
                pos=(1560, 700), size=(440, 140),
            ),
            _node(
                17, PREVIEW_NODE, groups[3], "Qwen restoration preview",
                inputs={"images": Link(16)}, input_types={"images": "IMAGE"},
                outputs=["images"], output_types=["IMAGE"],
                pos=(1560, 880), size=(440, 620),
            ),
            _node(
                18, "UpscaleModelLoader", groups[4], "Load final portrait refiner",
                inputs={"model_name": "RealESRGAN_x2plus.pth"},
                input_types={"model_name": "COMBO"},
                outputs=["upscale_model"], output_types=["UPSCALE_MODEL"],
                pos=(2120, 700), size=(320, 140),
                widgets=["RealESRGAN_x2plus.pth"], locked=["model_name"],
            ),
            _node(
                19, "ImageUpscaleWithModel", groups[4], "Refine and enlarge portrait",
                inputs={"upscale_model": Link(18), "image": Link(16)},
                input_types={"upscale_model": "UPSCALE_MODEL", "image": "IMAGE"},
                outputs=["enhanced_image"], output_types=["IMAGE"],
                pos=(2120, 880), size=(320, 140),
            ),
            _node(
                20, "HOI4FinishPreparedPortrait", groups[4], "Fit restored portrait for HOI4",
                inputs={"image": Link(19), "contrast": 1.0, "sharpness": 1.0},
                input_types={"image": "IMAGE", "contrast": "FLOAT", "sharpness": "FLOAT"},
                outputs=["prepared_portrait"], output_types=["IMAGE"],
                pos=(2120, 1060), size=(320, 140),
                widgets=[1.0, 1.0],
            ),
            _node(
                21, PREVIEW_NODE, groups[4], "Refined portrait preview",
                inputs={"images": Link(19)}, input_types={"images": "IMAGE"},
                outputs=["images"], output_types=["IMAGE"],
                pos=(2120, 1240), size=(680, 340),
            ),
            _node(
                22, PREVIEW_NODE, groups[5], "Prepared portrait preview",
                inputs={"images": Link(20)}, input_types={"images": "IMAGE"},
                outputs=["images"], output_types=["IMAGE"],
                pos=(2920, 700), size=(500, 650),
            ),
            _node(
                23, "SaveImage", groups[5], "Save prepared portrait",
                inputs={"images": Link(20), "filename_prefix": "hoi4_portraits/prepared_qwen"},
                input_types={"images": "IMAGE", "filename_prefix": "STRING"},
                pos=(3460, 700), size=(400, 180),
                widgets=["hoi4_portraits/prepared_qwen"], locked=["filename_prefix"],
            ),
        ])
        preview_nodes = [
            "Input image preview",
            "Head-and-shoulders preview",
            "Qwen restoration preview",
            "Refined portrait preview",
            "Prepared portrait preview",
        ]
        required_core_nodes = sorted({
            "CFGNorm",
            "CLIPLoader",
            "FluxKontextImageScale",
            "ImageUpscaleWithModel",
            "KSampler",
            "LoadImage",
            "ModelSamplingAuraFlow",
            "PreviewImage",
            "SaveImage",
            "TextEncodeQwenImageEditPlus",
            "UNETLoader",
            "UpscaleModelLoader",
            "VAEDecode",
            "VAEEncode",
            "VAELoader",
        })
        final_preview_id, save_id, final_source_id = 22, 23, 20
    else:
        nodes.extend([
            _node(
                5, "HOI4FinishPreparedPortrait", groups[2], "Apply basic image adjustments",
                inputs={"image": Link(3, 0), "contrast": 1.04, "sharpness": 1.08},
                input_types={"image": "IMAGE", "contrast": "FLOAT", "sharpness": "FLOAT"},
                outputs=["prepared_portrait"], output_types=["IMAGE"],
                pos=(160, 680), size=(340, 160),
                widgets=[1.04, 1.08],
            ),
            _node(
                6, PREVIEW_NODE, groups[3], "Prepared portrait preview",
                inputs={"images": Link(5, 0)}, input_types={"images": "IMAGE"},
                outputs=["images"], output_types=["IMAGE"],
                pos=(1200, 640), size=(430, 500),
            ),
            _node(
                7, "SaveImage", groups[3], "Save prepared portrait",
                inputs={"images": Link(5, 0), "filename_prefix": "hoi4_portraits/prepared_basic"},
                input_types={"images": "IMAGE", "filename_prefix": "STRING"},
                pos=(1660, 640), size=(340, 180),
                widgets=["hoi4_portraits/prepared_basic"], locked=["filename_prefix"],
            ),
        ])
        preview_nodes = ["Input image preview", "Head-and-shoulders preview", "Prepared portrait preview"]
        required_core_nodes = ["LoadImage", "PreviewImage", "SaveImage"]
        final_preview_id, save_id, final_source_id = 6, 7, 5
    metadata = {
        "schema_version": "1.0.0",
        "graph_spec_version": WORKFLOW_VERSION,
        "workflow_id": workflow_id,
        "profile": workflow_id,
        "execution_profile": workflow_id,
        "workflow_kind": "portrait_preparation",
        "enhancement_mode": "krea2_edit" if krea_enhanced else "qwen_image_edit" if qwen_enhanced else "basic",
        "default_preparation_workflow": krea_enhanced,
        "upscale_model": "RealESRGAN_x2plus.pth" if qwen_enhanced else None,
        "restoration_model": (
            "krea2_turbo_fp8_scaled.safetensors"
            if krea_enhanced
            else "qwen_image_edit_2511_fp8mixed.safetensors"
            if qwen_enhanced
            else None
        ),
        "restoration_text_encoder": (
            "qwen3vl_4b_fp8_scaled.safetensors"
            if krea_enhanced
            else "qwen_2.5_vl_7b_fp8_scaled.safetensors"
            if qwen_enhanced
            else None
        ),
        "colorization": ai_enhanced,
        "route": "full_power_gpu" if ai_enhanced else "local_or_runpod",
        "human_workflow": True,
        "autoprompter": False,
        "autoprompter_instruction_path": None,
        "autoprompter_instruction_sha256": None,
        "prompt_source": "none",
        "prompt_model": None,
        "source_image_required": True,
        "vision_model_required": ai_enhanced,
        "required_groups": groups,
        "required_core_nodes": required_core_nodes,
        "required_project_nodes": [
            "HOI4FinishPreparedPortrait",
            "HOI4PortraitCrop",
            *(["HOI4RestorationPrompt"] if ai_enhanced else []),
        ],
        "required_krea_nodes": sorted(KREA_NODES) if krea_enhanced else [],
        "preview_nodes": preview_nodes,
        "final_preview_save_pair": {
            "preview_node_id": final_preview_id,
            "save_node_id": save_id,
            "shared_source_node_id": final_source_id,
            "shared_source_slot": 0,
            "policy": "preview_and_save_use_the_same_prepared_portrait",
        },
        "low_memory_placeholder_nodes": [],
    }
    graph = GraphSpec(workflow_id, workflow_id, nodes, groups, metadata)
    validate_graph(graph)
    return graph


def validate_graph(graph: GraphSpec) -> None:
    ids = [node.node_id for node in graph.nodes]
    if len(ids) != len(set(ids)):
        raise ValueError("workflow node ids are not unique")
    if graph.groups != graph.metadata.get("required_groups"):
        raise ValueError("workflow group order does not match its declared layout")
    class_names = {node.class_type for node in graph.nodes}
    if any(token in node.class_type.casefold() for node in graph.nodes for token in FORBIDDEN_CLASS_TOKENS):
        raise ValueError("workflow contains a forbidden face-swap/replacement class")
    if graph.metadata.get("workflow_kind") == "random_text_to_image":
        random_prompt_nodes = [node for node in graph.nodes if node.class_type == "HOI4RandomPortraitPrompt"]
        agent_prompt_nodes = [node for node in graph.nodes if node.class_type == "HOI4PromptJobInput"]
        if graph.metadata["human_workflow"]:
            if len(random_prompt_nodes) != 1 or agent_prompt_nodes:
                raise ValueError("human random portrait workflow must contain exactly one text-only prompt builder")
        elif len(agent_prompt_nodes) != 1 or random_prompt_nodes:
            raise ValueError("agent random portrait workflow must contain exactly one job-contract prompt input")
        prohibited = KREA_NODES | {"LoadImage", "HOI4JobSource", "HOI4AutopromptClient"}
        if any(node.class_type in prohibited for node in graph.nodes):
            raise ValueError("random portrait workflow contains an image-input or identity-edit route")
        prompt_class = "HOI4RandomPortraitPrompt" if graph.metadata["human_workflow"] else "HOI4PromptJobInput"
        required_core = RANDOM_PROMPT_CORE_NODES if graph.metadata["human_workflow"] else RANDOM_PROMPT_CORE_NODES - {PREVIEW_NODE}
        required = required_core | {"HOI4KreaModelLoadBarrier", prompt_class}
        missing = sorted(required - class_names)
        if missing:
            raise ValueError(f"random portrait workflow is missing required node classes: {missing}")
    elif graph.metadata.get("workflow_kind") == "portrait_preparation":
        required = {
            "LoadImage",
            "PreviewImage",
            "SaveImage",
            "HOI4PortraitCrop",
            "HOI4FinishPreparedPortrait",
        }
        if graph.metadata.get("enhancement_mode") == "krea2_edit":
            required |= (
                KREA_NODES
                | {
                    "CLIPLoader",
                    "EmptySD3LatentImage",
                    "KSampler",
                    "LoraLoaderModelOnly",
                    "UNETLoader",
                    "VAEDecode",
                    "VAEEncode",
                    "VAELoader",
                    "HOI4RestorationPrompt",
                }
            )
        elif graph.metadata.get("enhancement_mode") == "qwen_image_edit":
            required |= (
                QWEN_PREPARATION_CORE_NODES
                | {
                    "CLIPLoader",
                    "ImageUpscaleWithModel",
                    "KSampler",
                    "UNETLoader",
                    "UpscaleModelLoader",
                    "VAEDecode",
                    "VAEEncode",
                    "VAELoader",
                    "HOI4RestorationPrompt",
                }
            )
        elif graph.metadata.get("enhancement_mode") == "basic":
            if (
                {"UpscaleModelLoader", "ImageUpscaleWithModel", "HOI4RestorationPrompt"}
                | QWEN_PREPARATION_CORE_NODES
            ) & class_names:
                raise ValueError("basic portrait preparation workflow may not load an enhancement model")
        else:
            raise ValueError("portrait preparation workflow has an unknown enhancement mode")
        missing = sorted(required - class_names)
        if missing:
            raise ValueError(f"portrait preparation workflow is missing required node classes: {missing}")
        if any(node.class_type == "HOI4AutopromptClient" for node in graph.nodes):
            raise ValueError("portrait preparation workflow may not contain the portrait autoprompter")
        if graph.metadata.get("enhancement_mode") != "krea2_edit" and any(node.class_type in KREA_NODES for node in graph.nodes):
            raise ValueError("non-Krea portrait preparation workflow contains Krea Edit nodes")
    elif graph.metadata["human_workflow"]:
        autoprompter_nodes = [node for node in graph.nodes if node.class_type == "HOI4AutopromptClient"]
        if len(autoprompter_nodes) != 1:
            raise ValueError("human workflow must contain exactly one autoprompter node")
        if autoprompter_nodes[0].inputs.get("instruction_text") != graph.metadata.get("_instruction_text", autoprompter_nodes[0].inputs.get("instruction_text")):
            # This branch intentionally only checks presence; the value itself
            # is compared to the prompt file by build_workflow_artifacts.
            if not autoprompter_nodes[0].inputs.get("instruction_text"):
                raise ValueError("human workflow autoprompter instruction is empty")
    else:
        if any(node.class_type == "HOI4AutopromptClient" or "VLM" in node.class_type for node in graph.nodes):
            raise ValueError("agent workflow may not contain an autoprompter or VLM client")
        if graph.metadata["prompt_source"] != "job_contract":
            raise ValueError("agent workflow prompt source must be the job contract")
    if graph.metadata.get("workflow_kind") not in {"random_text_to_image", "portrait_preparation"}:
        common_project_nodes = PROJECT_NODES - {"HOI4PromptInput", "HOI4AutopromptClient"}
        if graph.metadata.get("preparation_engine") in {"qwen_image_edit_2511", "krea2_edit_restoration"}:
            common_project_nodes |= QWEN_PREPARATION_PROJECT_NODES
        if not graph.metadata["human_workflow"]:
            common_project_nodes -= HUMAN_ONLY_PROJECT_NODES
        required_core = (
            CORE_NODES - {"UpscaleModelLoader", "ImageUpscaleWithModel"}
            if graph.metadata.get("preparation_engine") == "krea2_edit_restoration"
            else CORE_NODES
        )
        required = required_core | KREA_NODES | common_project_nodes
        if graph.metadata.get("preparation_engine") == "qwen_image_edit_2511":
            required |= QWEN_PREPARATION_CORE_NODES
        if graph.metadata["human_workflow"]:
            required.add(PREVIEW_NODE)
        required.add("HOI4AutopromptClient" if graph.metadata["human_workflow"] else "HOI4PromptInput")
        if graph.metadata["human_workflow"]:
            required |= HUMAN_ONLY_PROJECT_NODES
        missing = sorted(required - class_names)
        if missing:
            raise ValueError(f"workflow is missing required node classes: {missing}")
    for index, left in enumerate(graph.nodes):
        left_right = left.pos[0] + left.size[0]
        left_bottom = left.pos[1] + left.size[1]
        for right in graph.nodes[index + 1:]:
            if left_right <= right.pos[0] or right.pos[0] + right.size[0] <= left.pos[0]:
                continue
            if left_bottom <= right.pos[1] or right.pos[1] + right.size[1] <= left.pos[1]:
                continue
            raise ValueError(f"workflow nodes overlap: {left.node_id} ({left.title}) and {right.node_id} ({right.title})")


def _api_value(value: Any) -> Any:
    if isinstance(value, Link):
        return [str(value.node_id), value.slot]
    return value


def _apply_visual_layout(nodes: list[NodeSpec], *, is_human: bool, full_power: bool) -> None:
    """Place nodes and image checkpoints on the compact two-row stage board."""

    positions = (
        {
            1: (80, 100), 24: (460, 100), 2: (80, 340), 3: (80, 560),
            4: (980, 100), 30: (980, 320),
            5: (1510, 100), 25: (1510, 320),
            40: (1980, 100), 41: (1980, 280),
            42: (2520, 100), 43: (2520, 260), 44: (2520, 420),
            52: (2520, 600), 53: (2520, 760),
            45: (2860, 100), 46: (2860, 340), 47: (2860, 580),
            48: (3260, 100), 49: (3260, 260), 50: (3260, 420),
            51: (3260, 680), 6: (3260, 840),
            54: (3700, 100), 26: (3700, 520),
            7: (4210, 100), 8: (4210, 320), 27: (4570, 300),
            34: (4930, 100), 35: (4930, 320), 37: (5290, 100), 38: (5290, 320),
            9: (340, 1110),
            10: (880, 1110), 11: (880, 1270), 12: (880, 1430), 13: (880, 1590),
            14: (1180, 1110), 15: (1180, 1270), 16: (1480, 1430), 17: (1480, 1590),
            18: (2220, 1220),
            19: (2600, 1110), 20: (2600, 1300), 29: (2600, 1530),
            21: (2980, 1110), 22: (3320, 1110), 23: (3320, 1320), 28: (3680, 1110),
        }
        if full_power
        else {
            1: (80, 100), 24: (460, 100), 2: (80, 340), 3: (80, 560),
            4: (980, 100), 30: (980, 320),
            5: (1510, 100), 25: (1510, 320),
            36: (1980, 100), 39: (1980, 260), 6: (1980, 420), 26: (1980, 600),
            7: (2450, 100), 8: (2450, 320), 27: (2810, 300),
            34: (3170, 100), 35: (3170, 320), 37: (3530, 100), 38: (3530, 320),
            9: (340, 1080),
            10: (880, 1080), 11: (880, 1240), 12: (880, 1400), 13: (880, 1560),
            14: (1160, 1080), 15: (1160, 1240), 16: (1160, 1400), 17: (1160, 1560),
            18: (1820, 1220),
            19: (2200, 1080), 20: (2200, 1260), 29: (2200, 1490),
            21: (2580, 1080), 22: (2900, 1080), 23: (2900, 1290), 28: (3220, 1080),
            31: (1460, 1080), 32: (1460, 1240), 33: (1460, 1410),
        }
    )
    sizes = {
        1: (350, 190), 24: (400, 720), 2: (350, 150), 3: (350, 150),
        4: (360, 160), 30: (400, 500),
        5: (360, 160), 25: (400, 500),
        36: (360, 140), 39: (360, 140), 6: (360, 160), 26: (400, 400),
        40: (500, 140), 41: (500, 600),
        42: (300, 130), 43: (300, 130), 44: (300, 130),
        45: (360, 200), 46: (360, 200), 47: (360, 140),
        48: (360, 130), 49: (360, 130), 50: (360, 220), 51: (360, 140),
        52: (300, 130), 53: (300, 140), 54: (400, 400),
        7: (320, 160), 8: (320, 260), 27: (340, 500),
        34: (340, 160), 35: (340, 500), 37: (340, 160), 38: (340, 500),
        9: (440, 600 if is_human else 230),
        10: (260, 130), 11: (260, 130), 12: (260, 130), 13: (260, 130),
        14: (260, 130), 15: (260, 130), 16: (260, 130), 17: (260, 130),
        18: (260, 170), 19: (260, 150), 20: (260, 180), 29: (260, 130),
        21: (300, 140), 22: (300, 170), 23: (300, 140), 28: (400, 540),
        31: (250, 120), 32: (250, 140), 33: (250, 140),
    }
    if full_power:
        sizes[26] = (400, 470)
    for node in nodes:
        if node.node_id in positions:
            node.pos = positions[node.node_id]
        if node.node_id in sizes:
            node.size = sizes[node.node_id]


def _api_json(graph: GraphSpec) -> dict[str, Any]:
    executable_nodes = [
        node for node in graph.nodes
        if node.class_type not in UI_ONLY_NODE_CLASSES
    ]
    if graph.nodes[0].class_type == "HOI4JobInput":
        return {
            "1": {
                "class_type": "HOI4JobInput",
                "inputs": {
                    "execution_profile": graph.profile,
                    "job_contract_path": "jobs/<job_id>/input.json",
                    "candidate_count": int(PROFILE_LIMITS[graph.profile]["candidate_max"]),
                    "retry_limit": int(PROFILE_LIMITS[graph.profile]["retry_max"]),
                    "seed_policy": "derived",
                },
            },
            **{
                str(node.node_id): {
                    "class_type": node.class_type,
                    "inputs": {
                        key: _api_value(value)
                        for key, value in node.inputs.items()
                        if key != "instruction_text" or graph.metadata["human_workflow"]
                    },
                }
                for node in executable_nodes
                if node.node_id != 1
            },
            "_meta": graph.metadata,
        }
    return {
        **{
            str(node.node_id): {
                "class_type": node.class_type,
                "inputs": {key: _api_value(value) for key, value in node.inputs.items()},
            }
            for node in executable_nodes
        },
        "_meta": graph.metadata,
    }


def _ui_json(graph: GraphSpec) -> dict[str, Any]:
    links: list[list[Any]] = []
    link_id = 1
    input_links: dict[tuple[int, str], int] = {}
    output_links: dict[tuple[int, int], list[int]] = {}
    for node in graph.nodes:
        for input_name, value in node.inputs.items():
            if isinstance(value, Link):
                links.append([link_id, value.node_id, value.slot, node.node_id, list(node.input_types).index(input_name) if input_name in node.input_types else 0, node.input_types.get(input_name, "*" )])
                input_links[(node.node_id, input_name)] = link_id
                output_links.setdefault((value.node_id, value.slot), []).append(link_id)
                link_id += 1
    ui_nodes: list[dict[str, Any]] = []
    workflow_kind = graph.metadata.get("workflow_kind")
    krea_preparation = workflow_kind == "portrait_preparation" and graph.metadata.get("enhancement_mode") == "krea2_edit"
    qwen_preparation = workflow_kind == "portrait_preparation" and graph.metadata.get("enhancement_mode") == "qwen_image_edit"
    full_power_source_workflow = graph.profile in FULL_POWER_PROFILE_IDS
    initial_scale = 0.34 if qwen_preparation else 0.36 if krea_preparation else 0.46 if workflow_kind == "portrait_preparation" else 0.44 if workflow_kind == "random_text_to_image" else 0.28 if full_power_source_workflow else 0.32
    initial_offset = [160, 170] if workflow_kind == "portrait_preparation" else [160, 180] if workflow_kind == "random_text_to_image" else [160, 260]
    palette = PREP_KREA_NODE_COLORS if krea_preparation else PREP_QWEN_NODE_COLORS if qwen_preparation else PREP_NODE_COLORS if workflow_kind == "portrait_preparation" else RANDOM_PROMPT_NODE_COLORS if workflow_kind == "random_text_to_image" else NODE_COLORS
    for order, node in enumerate(graph.nodes):
        node_color, node_bgcolor = palette[node.group]
        if node.class_type == "LoadImage":
            ui_inputs = [
                {"localized_name": "image", "name": "image", "type": "COMBO", "widget": {"name": "image"}, "link": None},
                {"localized_name": "choose file to upload", "name": "upload", "type": "IMAGEUPLOAD", "widget": {"name": "upload"}, "link": None},
            ]
        else:
            ui_inputs = [{"name": name, "type": node.input_types.get(name, "*"), "link": input_links.get((node.node_id, name))} for name in node.inputs]
        ui_nodes.append({
            "id": node.node_id,
            "type": node.class_type,
            "title": node.title,
            "pos": list(node.pos),
            "size": list(node.size),
            "color": node_color,
            "bgcolor": node_bgcolor,
            "flags": {},
            "order": order,
            "mode": 0,
            "inputs": ui_inputs,
            "outputs": [{"name": name, "type": node.output_types[index] if index < len(node.output_types) else "*", "links": output_links.get((node.node_id, index))} for index, name in enumerate(node.outputs)],
            "properties": {"Node name for S&R": node.title, "hoi4_group": node.group, "hoi4_locked_controls": node.locked},
            "widgets_values": node.widgets,
        })
    groups = []
    layout = PREP_KREA_GROUP_LAYOUT if krea_preparation else PREP_QWEN_GROUP_LAYOUT if qwen_preparation else PREP_GROUP_LAYOUT if workflow_kind == "portrait_preparation" else RANDOM_PROMPT_GROUP_LAYOUT if workflow_kind == "random_text_to_image" else FULL_POWER_GROUP_LAYOUT if full_power_source_workflow else GROUP_LAYOUT
    colors = PREP_KREA_GROUP_COLORS if krea_preparation else PREP_QWEN_GROUP_COLORS if qwen_preparation else PREP_GROUP_COLORS if workflow_kind == "portrait_preparation" else RANDOM_PROMPT_GROUP_COLORS if workflow_kind == "random_text_to_image" else GROUP_COLORS
    for label in graph.groups:
        x, y, width, height = layout[label]
        groups.append({"title": label, "bounding": [x, y, width, height], "color": colors[label], "font_size": 24})
    return {
        "last_node_id": max(node.node_id for node in graph.nodes),
        "last_link_id": link_id - 1,
        "nodes": ui_nodes,
        "links": links,
        "groups": groups,
        "config": {},
        "extra": {"ds": {"scale": initial_scale, "offset": initial_offset}, **graph.metadata},
        "version": 0.4,
    }


def build_workflow_artifacts(root: str | Path | None = None) -> dict[str, Any]:
    root_path = project_root(root)
    custom_node_lock_path = root_path / "dependencies" / "custom_nodes.lock.json"
    custom_node_lock = json.loads(custom_node_lock_path.read_text(encoding="utf-8")) if custom_node_lock_path.is_file() else {}
    custom_node_entries = {str(item.get("name")): item for item in custom_node_lock.get("custom_nodes", [])}
    custom_node_by_class = {
        class_name: entry
        for entry in custom_node_entries.values()
        for class_name in entry.get("classes", [])
    }
    paths = {
        "hoi4_portraits_local_nvidia_16gb": root_path / "workflows/human/local_nvidia_16gb/hoi4_portraits_local_nvidia_16gb.json",
        "hoi4_portraits_full_power_gpu": root_path / "workflows/human/full_power_gpu/hoi4_portraits_full_power_gpu.json",
        "hoi4_portraits_agent_local_nvidia_16gb": root_path / "workflows/agent/local_nvidia_16gb/hoi4_portraits_agent_local_nvidia_16gb.json",
        "hoi4_portraits_agent_full_power_gpu": root_path / "workflows/agent/full_power_gpu/hoi4_portraits_agent_full_power_gpu.json",
        "hoi4_portraits_no_input_local_nvidia_16gb": root_path / "workflows/human/no_input_local_nvidia_16gb/hoi4_portraits_no_input_local_nvidia_16gb.json",
        "hoi4_portraits_no_input_full_power_gpu": root_path / "workflows/human/no_input_full_power_gpu/hoi4_portraits_no_input_full_power_gpu.json",
        "hoi4_portraits_agent_no_input_local_nvidia_16gb": root_path / "workflows/agent/no_input_local_nvidia_16gb/hoi4_portraits_agent_no_input_local_nvidia_16gb.json",
        "hoi4_portraits_agent_no_input_full_power_gpu": root_path / "workflows/agent/no_input_full_power_gpu/hoi4_portraits_agent_no_input_full_power_gpu.json",
        PREP_WORKFLOW_ID: root_path / "workflows/human/prepare_portrait/hoi4_portraits_prepare_portrait_for_hoi4.json",
        PREP_QWEN_WORKFLOW_ID: root_path / "workflows/human/prepare_portrait_qwen/hoi4_portraits_prepare_portrait_qwen.json",
        PREP_BASIC_WORKFLOW_ID: root_path / "workflows/human/prepare_portrait_basic/hoi4_portraits_prepare_portrait_basic.json",
    }
    manifests: list[dict[str, Any]] = []
    live_probe_path = root_path / ".runtime" / "reports" / "live_comfy_compatibility.json"
    try:
        live_probe = json.loads(live_probe_path.read_text(encoding="utf-8")) if live_probe_path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        live_probe = {}
    live_workflows = {item.get("workflow_id"): item for item in live_probe.get("workflows", []) if isinstance(item, dict)}
    for workflow_id, ui_path in paths.items():
        graph = build_preparation_graph(root_path, workflow_id) if workflow_id in PREP_WORKFLOW_IDS else build_random_prompt_graph(workflow_id, root_path) if workflow_id in RANDOM_PROMPT_WORKFLOWS else build_graph(workflow_id, root_path)
        if workflow_id in PREP_WORKFLOW_IDS:
            required_custom_nodes = ["HOI4FinishPreparedPortrait", "HOI4PortraitCrop"]
            required_models = ["face_detection_yunet_2023mar.onnx"]
            if workflow_id == PREP_WORKFLOW_ID:
                required_custom_nodes.extend(["HOI4RestorationPrompt", *sorted(KREA_NODES)])
                required_models.extend([
                    "krea2_turbo_fp8_scaled.safetensors",
                    "qwen3vl_4b_fp8_scaled.safetensors",
                    "qwen_image_vae.safetensors",
                    "krea2_identity_edit_v1_2.safetensors",
                ])
            elif workflow_id == PREP_QWEN_WORKFLOW_ID:
                required_custom_nodes.append("HOI4RestorationPrompt")
                required_models.extend([
                    "qwen_image_edit_2511_fp8mixed.safetensors",
                    "qwen_2.5_vl_7b_fp8_scaled.safetensors",
                    "qwen_image_vae.safetensors",
                    "RealESRGAN_x2plus.pth",
                ])
        elif workflow_id in RANDOM_PROMPT_WORKFLOWS:
            required_custom_nodes = [
                "HOI4KreaModelLoadBarrier",
                "HOI4RandomPortraitPrompt" if graph.metadata["human_workflow"] else "HOI4PromptJobInput",
            ]
            required_models = [
                "krea2_turbo_fp8_scaled.safetensors",
                "qwen3vl_4b_fp8_scaled.safetensors",
                "qwen_image_vae.safetensors",
                "hoi4_portrait_new_style_lora.safetensors",
            ]
        else:
            required_prompt_node = "HOI4AutopromptClient" if graph.metadata["human_workflow"] else "HOI4PromptInput"
            required_custom_nodes = sorted(
                KREA_NODES
                | (PROJECT_NODES - {"HOI4PromptInput", "HOI4AutopromptClient"} - (set() if graph.metadata["human_workflow"] else HUMAN_ONLY_PROJECT_NODES))
                | (QWEN_PREPARATION_PROJECT_NODES if graph.metadata.get("preparation_engine") in {"qwen_image_edit_2511", "krea2_edit_restoration"} else set())
                | {required_prompt_node}
                | (HUMAN_ONLY_PROJECT_NODES if graph.metadata["human_workflow"] else set())
            )
            required_models = [
                "krea2_turbo_fp8_scaled.safetensors",
                "qwen3vl_4b_fp8_scaled.safetensors",
                "qwen_image_vae.safetensors",
                "krea2_identity_edit_v1_2.safetensors",
                "hoi4_portrait_new_style_lora.safetensors",
                "RealESRGAN_x2plus.pth",
            ]
            if graph.metadata.get("preparation_engine") == "qwen_image_edit_2511":
                required_models.extend([
                    "qwen_image_edit_2511_fp8mixed.safetensors",
                    "qwen_2.5_vl_7b_fp8_scaled.safetensors",
                ])
        if graph.metadata["human_workflow"] and workflow_id not in RANDOM_PROMPT_WORKFLOWS and workflow_id not in PREP_WORKFLOW_IDS:
            required_models.append("Qwen3VL-4B-Instruct-Q4_K_M.gguf" if "local" in workflow_id else "Qwen3-VL-8B-Instruct-BF16-shards")
        api_path = ui_path.with_suffix(".api.json")
        atomic_json_write(ui_path, _ui_json(graph))
        atomic_json_write(api_path, _api_json(graph))
        required_node_packages = sorted({custom_node_by_class[class_name]["name"] for class_name in required_custom_nodes if class_name in custom_node_by_class})
        required_node_revisions = {name: custom_node_entries[name].get("revision") for name in required_node_packages}
        required_node_checksums = {name: custom_node_entries[name].get("source_tree_checksum") for name in required_node_packages}
        live_workflow = live_workflows.get(workflow_id, {})
        live_schema_pass = (
            live_workflow.get("status") == "PASS"
            and all(bool(value) for value in live_probe.get("schema_checks", {}).values())
        )
        runtime_status = "LIVE_SCHEMA_LOADABLE_EXECUTION_BLOCKED" if live_schema_pass else "STRUCTURAL_ONLY_RUNTIME_BLOCKED"
        execution_evidence = {"path": str(live_probe_path.relative_to(root_path)), **live_probe.get("execution", {})} if live_schema_pass else None
        execution_verified = isinstance(execution_evidence, dict) and execution_evidence.get("status") == "PASS" and execution_evidence.get("attempted") is True
        manifests.append({
            "workflow_id": workflow_id,
            "display_name": workflow_id,
            "workflow_json": str(ui_path.relative_to(root_path)),
            "api_json": str(api_path.relative_to(root_path)),
            "sha256": sha256_file(ui_path),
            "api_sha256": sha256_file(api_path),
            "graph_spec_version": WORKFLOW_VERSION,
            "comfyui_commit": "2a610155821d670a2d8047e654e5fce96b790eb5",
            "required_core_nodes": graph.metadata["required_core_nodes"],
            "required_custom_nodes": required_custom_nodes,
            "required_custom_node_packages": required_node_packages,
            "required_custom_node_revisions": required_node_revisions,
            "required_custom_node_source_checksums": required_node_checksums,
            "required_models": required_models,
            "autoprompter_present": bool(graph.metadata["autoprompter"]),
            "prompt_source": graph.metadata["prompt_source"],
            "preview_nodes": graph.metadata.get("preview_nodes", []),
            "final_preview_save_pair": graph.metadata.get("final_preview_save_pair"),
            "autoprompter_instruction_sha256": graph.metadata["autoprompter_instruction_sha256"],
            # The delivery contract reserves validation for a real acceptance
            # execution. Keep schema/load evidence separate so a live registry
            # check cannot accidentally promote the manifest.
            "validation_status": "VALIDATED" if execution_verified else "UNVALIDATED",
            "runtime_status": runtime_status,
            "load_test_evidence": {"path": str(live_probe_path.relative_to(root_path)), "status": "PASS", "checked_at": live_probe.get("checked_at")} if live_schema_pass else None,
            "execution_test_evidence": execution_evidence,
        })
    manifest_status = "VALIDATED" if manifests and all(item.get("validation_status") == "VALIDATED" for item in manifests) else "UNVALIDATED"
    runtime_status = "LIVE_SCHEMA_LOADABLE_EXECUTION_BLOCKED" if manifests and all(item.get("runtime_status") == "LIVE_SCHEMA_LOADABLE_EXECUTION_BLOCKED" for item in manifests) else "STRUCTURAL_ONLY_RUNTIME_BLOCKED"
    generated_at = live_probe.get("checked_at") if isinstance(live_probe.get("checked_at"), str) else datetime.now(timezone.utc).isoformat()
    manifest = {"schema_version": "1.0.0", "generated_at": generated_at, "lock_version": "workflows-2026-07-29.1", "workflows": manifests, "status": manifest_status, "runtime_status": runtime_status}
    atomic_json_write(root_path / "docs/reference/workflow_manifest.json", manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build all configured deterministic ComfyUI workflow artifacts.")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args(argv)
    manifest = build_workflow_artifacts(args.root)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0
