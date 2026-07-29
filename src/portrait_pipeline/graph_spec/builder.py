from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..constants import (
    AUTOPROMPTER_PATH,
    GROUP_LABELS,
    PROFILE_LIMITS,
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
HUMAN_ONLY_PROJECT_NODES = {"HOI4HumanControls"}
FORBIDDEN_CLASS_TOKENS = ("faceswap", "face_swap", "ipadapterface", "replacer", "subjectreplacement")
UI_ONLY_NODE_CLASSES = {"Note"}
LOW_MEMORY_PROFILE_IDS = {
    "human_local_nvidia_16gb",
    "agent_local_nvidia_16gb",
}

# The UI workflow is deliberately laid out as a compact two-row rectangular
# stage board.  The larger input and preview panels are placed beside the
# stage that produces each image, so a human can follow the portrait without
# hunting across the canvas.  These values are presentation metadata only;
# they do not change the execution graph or any locked control.
GROUP_LAYOUT = {
    "00 Job and source": (40, 40, 760, 700),
    "01 Subject selection": (840, 40, 500, 700),
    "02 Crop and source preparation": (1380, 40, 440, 700),
    "03 Color and restoration": (1860, 40, 440, 700),
    "04 Masks and approved background": (2340, 40, 700, 700),
    "05 Prompt": (40, 800, 500, 640),
    "06 Krea 2 identity edit": (580, 800, 900, 800),
    "07 HOI4 style LoRA": (1520, 800, 340, 640),
    "08 Portrait generation": (1900, 800, 340, 640),
    "09 Preview and evidence export": (2280, 800, 1080, 760),
}

GROUP_COLORS = {
    "00 Job and source": "#355070",
    "01 Subject selection": "#3a7ca5",
    "02 Crop and source preparation": "#2a9d8f",
    "03 Color and restoration": "#588157",
    "04 Masks and approved background": "#527fa3",
    "05 Prompt": "#8064a2",
    "06 Krea 2 identity edit": "#6d597a",
    "07 HOI4 style LoRA": "#b56576",
    "08 Portrait generation": "#c17817",
    "09 Preview and evidence export": "#457b9d",
}

NODE_COLORS = {
    "00 Job and source": ("#1d2f45", "#294866"),
    "01 Subject selection": ("#1f4862", "#2c6d90"),
    "02 Crop and source preparation": ("#164f49", "#217a70"),
    "03 Color and restoration": ("#294a2b", "#3d6b40"),
    "04 Masks and approved background": ("#294b61", "#3b6f8d"),
    "05 Prompt": ("#46375a", "#654c80"),
    "06 Krea 2 identity edit": ("#40344a", "#5b4a69"),
    "07 HOI4 style LoRA": ("#663442", "#914b5e"),
    "08 Portrait generation": ("#66400c", "#945e12"),
    "09 Preview and evidence export": ("#23465b", "#306985"),
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
        widgets=widgets or [],
        locked=locked or [],
    )


def build_graph(profile: str, root: str | Path | None = None) -> GraphSpec:
    root_path = project_root(root)
    if profile not in PROFILE_LIMITS:
        raise ValueError(f"unknown execution profile: {profile}")
    limits = PROFILE_LIMITS[profile]
    is_human = bool(limits["autoprompter"])
    width = int(limits["canvas_width"])
    height = int(limits["canvas_height"])
    group = {label: label for label in GROUP_LABELS}
    instruction = autoprompter_instruction(root_path) if is_human else None
    nodes: list[NodeSpec] = []

    nodes.append(_node(
        1, "HOI4JobInput", group["00 Job and source"], "Portrait workflow settings",
        inputs={"execution_profile": profile, "job_contract_path": "jobs/<job_id>/input.json", "candidate_count": int(limits["candidate_max"]), "retry_limit": int(limits["retry_max"]), "seed_policy": "derived"},
        input_types={"execution_profile": "STRING", "job_contract_path": "STRING", "candidate_count": "INT", "retry_limit": "INT", "seed_policy": "COMBO"},
        outputs=["job"], output_types=["HOI4_JOB"], pos=(40, 80), widgets=[profile, "jobs/<job_id>/input.json", int(limits["candidate_max"]), int(limits["retry_max"]), "derived"], locked=["execution_profile", "candidate_count", "retry_limit", "seed_policy"],
    ))
    job_node_id = 24 if is_human else 1
    if is_human:
        nodes.append(_node(
            24, "HOI4HumanControls", group["00 Job and source"], "Input portrait & portrait options",
            inputs={"job": Link(1), "source_image_path": "<from_job_contract>", "subject_selector_mode": "automatic", "face_index": 0, "bbox_left": 0, "bbox_top": 0, "bbox_right": 0, "bbox_bottom": 0, "crop_override_left": 0, "crop_override_top": 0, "crop_override_right": 0, "crop_override_bottom": 0, "monochrome_mode": "automatic", "restoration_level": "conservative", "approved_background_registry_id": "<from_job_contract>", "prompt_override": "", "seed_mode": "derived", "fixed_seed": 0, "candidate_count": int(limits["candidate_max"]), "output_job_id": "<job_id_from_contract>"},
            input_types={"job": "HOI4_JOB", "source_image_path": "STRING", "subject_selector_mode": "COMBO", "face_index": "INT", "bbox_left": "INT", "bbox_top": "INT", "bbox_right": "INT", "bbox_bottom": "INT", "crop_override_left": "INT", "crop_override_top": "INT", "crop_override_right": "INT", "crop_override_bottom": "INT", "monochrome_mode": "COMBO", "restoration_level": "COMBO", "approved_background_registry_id": "STRING", "prompt_override": "STRING", "seed_mode": "COMBO", "fixed_seed": "INT", "candidate_count": "INT", "output_job_id": "STRING"},
            outputs=["job", "control_meta"], output_types=["HOI4_JOB", "HOI4_META"], pos=(360, 80),
            widgets=["<from_job_contract>", "automatic", 0, 0, 0, 0, 0, 0, 0, 0, "automatic", "conservative", "<from_job_contract>", "", "derived", 0, int(limits["candidate_max"]), "<job_id_from_contract>"],
        ))
    control_inputs = {"control_meta": Link(24, 1)} if is_human else {}
    control_input_types = {"control_meta": "HOI4_META"} if is_human else {}
    nodes.append(_node(
        2, "HOI4JobSource", group["00 Job and source"], "Load input portrait",
        inputs={"job": Link(job_node_id)}, input_types={"job": "HOI4_JOB"}, outputs=["image", "source_meta"], output_types=["IMAGE", "HOI4_META"], pos=(40, 300),
    ))
    nodes.append(_node(
        3, "HOI4SourceGuard", group["00 Job and source"], "Check input portrait",
        inputs={"job": Link(job_node_id), "image": Link(2, 0)}, input_types={"job": "HOI4_JOB", "image": "IMAGE"}, outputs=["image", "source_meta"], output_types=["IMAGE", "HOI4_META"], pos=(40, 510),
    ))
    nodes.append(_node(
        4, "HOI4SubjectSelect", group["01 Subject selection"], "Select the subject",
        inputs={"job": Link(job_node_id), "image": Link(3, 0)}, input_types={"job": "HOI4_JOB", "image": "IMAGE"}, outputs=["image", "selection_meta"], output_types=["IMAGE", "HOI4_META"], pos=(360, 80),
    ))
    nodes.append(_node(
        5, "HOI4HeadShouldersCrop", group["02 Crop and source preparation"], "Crop the portrait",
        inputs={"job": Link(job_node_id), "image": Link(4, 0), "selection_meta": Link(4, 1), **control_inputs}, input_types={"job": "HOI4_JOB", "image": "IMAGE", "selection_meta": "HOI4_META", **control_input_types}, outputs=["image", "crop_meta"], output_types=["IMAGE", "HOI4_META"], pos=(360, 300),
    ))
    nodes.append(_node(
        6, "HOI4ConservativePrep", group["03 Color and restoration"], "Prepare the portrait",
        inputs={"job": Link(job_node_id), "image": Link(5, 0), "crop_meta": Link(5, 1), **control_inputs}, input_types={"job": "HOI4_JOB", "image": "IMAGE", "crop_meta": "HOI4_META", **control_input_types}, outputs=["image", "reference_meta"], output_types=["IMAGE", "HOI4_META"], pos=(360, 520),
    ))
    nodes.append(_node(
        7, "HOI4ForegroundMask", group["04 Masks and approved background"], "Separate person from background",
        inputs={"job": Link(job_node_id), "image": Link(6, 0), "reference_meta": Link(6, 1), "mask_model": "BiRefNet"}, input_types={"job": "HOI4_JOB", "image": "IMAGE", "reference_meta": "HOI4_META", "mask_model": "STRING"}, outputs=["image", "mask", "mask_meta"], output_types=["IMAGE", "MASK", "HOI4_META"], pos=(680, 40), widgets=["BiRefNet"], locked=["mask_model"],
    ))
    nodes.append(_node(
        8, "HOI4MaskAndBackgroundGuard", group["04 Masks and approved background"], "Add approved background",
        inputs={"job": Link(job_node_id), "image": Link(7, 0), "mask": Link(7, 1), "mask_meta": Link(7, 2)}, input_types={"job": "HOI4_JOB", "image": "IMAGE", "mask": "MASK", "mask_meta": "HOI4_META"}, outputs=["image", "composite", "mask", "background_meta"], output_types=["IMAGE", "IMAGE", "MASK", "HOI4_META"], pos=(680, 270),
    ))

    if is_human:
        nodes.append(_node(
            9, "HOI4AutopromptClient", group["05 Prompt"], "Create portrait description",
            inputs={"job": Link(job_node_id), "image": Link(8, 0), "background_meta": Link(8, 3), "control_meta": Link(24, 1), "instruction_text": instruction, "instruction_path": AUTOPROMPTER_PATH, "model_id": limits["prompt_model"], "prompt_source": "autoprompter"},
            input_types={"job": "HOI4_JOB", "image": "IMAGE", "background_meta": "HOI4_META", "control_meta": "HOI4_META", "instruction_text": "STRING", "instruction_path": "STRING", "model_id": "STRING", "prompt_source": "COMBO"},
            outputs=["prompt", "prompt_meta"], output_types=["STRING", "HOI4_META"], pos=(680, 340), widgets=[instruction, AUTOPROMPTER_PATH, limits["prompt_model"], "autoprompter"], locked=["instruction_text", "instruction_path", "model_id", "prompt_source"],
        ))
    else:
        nodes.append(_node(
            9, "HOI4PromptInput", group["05 Prompt"], "Use portrait description",
            inputs={"job": Link(job_node_id), "background_meta": Link(8, 3), "prompt_source": "job_contract"}, input_types={"job": "HOI4_JOB", "background_meta": "HOI4_META", "prompt_source": "COMBO"}, outputs=["prompt", "prompt_meta"], output_types=["STRING", "HOI4_META"], pos=(680, 540), widgets=["job_contract"], locked=["prompt_source"],
        ))

    nodes.append(_node(
        10, "UNETLoader", group["06 Krea 2 identity edit"], "Load Krea 2 Turbo",
        inputs={"unet_name": "krea2_turbo_fp8_scaled.safetensors", "weight_dtype": "default"}, input_types={"unet_name": "COMBO", "weight_dtype": "COMBO"}, outputs=["model"], output_types=["MODEL"], pos=(1000, 80), widgets=["krea2_turbo_fp8_scaled.safetensors", "default"], locked=["unet_name", "weight_dtype"],
    ))
    nodes.append(_node(
        11, "LoraLoaderModelOnly", group["06 Krea 2 identity edit"], "Preserve identity",
        inputs={"model": Link(10), "lora_name": "krea2_identity_edit_v1_2.safetensors", "strength_model": 1.0}, input_types={"model": "MODEL", "lora_name": "COMBO", "strength_model": "FLOAT"}, outputs=["model"], output_types=["MODEL"], pos=(1000, 260), widgets=["krea2_identity_edit_v1_2.safetensors", 1.0], locked=["lora_name", "strength_model"],
    ))
    nodes.append(_node(
        12, "VAELoader", group["06 Krea 2 identity edit"], "Prepare image decoder",
        inputs={"vae_name": "qwen_image_vae.safetensors"}, input_types={"vae_name": "COMBO"}, outputs=["vae"], output_types=["VAE"], pos=(1000, 450), widgets=["qwen_image_vae.safetensors"], locked=["vae_name"],
    ))
    nodes.append(_node(
        13, "VAEEncode", group["06 Krea 2 identity edit"], "Encode reference image",
        inputs={"pixels": Link(8, 1), "vae": Link(12)}, input_types={"pixels": "IMAGE", "vae": "VAE"}, outputs=["latent"], output_types=["LATENT"], pos=(1000, 610),
    ))
    nodes.append(_node(
        14, "Krea2EditModelPatch", group["06 Krea 2 identity edit"], "Apply identity reference",
        inputs={"model": Link(11), "source_latent": Link(13), "vae": Link(12), "source_image": Link(8, 1), "fit_mode": "fit", "ref_boost": 1.0}, input_types={"model": "MODEL", "source_latent": "LATENT", "vae": "VAE", "source_image": "IMAGE", "fit_mode": "COMBO", "ref_boost": "FLOAT"}, outputs=["model"], output_types=["MODEL"], pos=(1320, 200), widgets=["fit", 1.0], locked=["fit_mode", "ref_boost"],
    ))
    nodes.append(_node(
        15, "CLIPLoader", group["06 Krea 2 identity edit"], "Read portrait description",
        inputs={"clip_name": "qwen3vl_4b_fp8_scaled.safetensors", "type": "krea2"}, input_types={"clip_name": "COMBO", "type": "COMBO"}, outputs=["clip"], output_types=["CLIP"], pos=(1320, 430), widgets=["qwen3vl_4b_fp8_scaled.safetensors", "krea2"], locked=["clip_name", "type"],
    ))
    nodes.append(_node(
        16, "Krea2EditGroundedEncode", group["06 Krea 2 identity edit"], "Connect portrait description",
        inputs={"clip": Link(15), "prompt": Link(9, 0), "image": Link(8, 1), "grounding_px": 768}, input_types={"clip": "CLIP", "prompt": "STRING", "image": "IMAGE", "grounding_px": "INT"}, outputs=["conditioning"], output_types=["CONDITIONING"], pos=(1640, 80), widgets=[768], locked=["grounding_px"],
    ))
    nodes.append(_node(
        17, "Krea2EditGroundedEncode", group["06 Krea 2 identity edit"], "Keep background empty",
        inputs={"clip": Link(15), "prompt": "", "image": Link(8, 1), "grounding_px": 768}, input_types={"clip": "CLIP", "prompt": "STRING", "image": "IMAGE", "grounding_px": "INT"}, outputs=["conditioning"], output_types=["CONDITIONING"], pos=(1640, 290), widgets=["", 768], locked=["prompt", "grounding_px"],
    ))
    nodes.append(_node(
        18, "LoraLoaderModelOnly", group["07 HOI4 style LoRA"], "Apply HOI4 portrait style",
        inputs={"model": Link(14), "lora_name": "hoi4_portrait_new_style_lora.safetensors", "strength_model": 0.80}, input_types={"model": "MODEL", "lora_name": "COMBO", "strength_model": "FLOAT"}, outputs=["model"], output_types=["MODEL"], pos=(1960, 200), widgets=["hoi4_portrait_new_style_lora.safetensors", 0.80], locked=["lora_name"],
    ))
    nodes.append(_node(
        29, "HOI4KreaModelLoadBarrier", group["08 Portrait generation"], "Prepare generation",
        inputs={"model": Link(18), "positive": Link(16), "negative": Link(17)}, input_types={"model": "MODEL", "positive": "CONDITIONING", "negative": "CONDITIONING"}, outputs=["model", "positive", "negative"], output_types=["MODEL", "CONDITIONING", "CONDITIONING"], pos=(1320, 620),
    ))
    nodes.append(_node(
        19, "EmptySD3LatentImage", group["08 Portrait generation"], "Set portrait size",
        inputs={"width": width, "height": height, "batch_size": 1}, input_types={"width": "INT", "height": "INT", "batch_size": "INT"}, outputs=["latent"], output_types=["LATENT"], pos=(1960, 430), widgets=[width, height, 1], locked=["width", "height", "batch_size"],
    ))
    nodes.append(_node(
        20, "KSampler", group["08 Portrait generation"], "Generate portrait",
        inputs={"model": Link(29, 0), "positive": Link(29, 1), "negative": Link(29, 2), "latent_image": Link(19), "seed": 0, "steps": 8, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}, input_types={"model": "MODEL", "positive": "CONDITIONING", "negative": "CONDITIONING", "latent_image": "LATENT", "seed": "INT", "steps": "INT", "cfg": "FLOAT", "sampler_name": "COMBO", "scheduler": "COMBO", "denoise": "FLOAT"}, outputs=["latent"], output_types=["LATENT"], pos=(2280, 120), widgets=[0, 8, 1.0, "euler", "simple", 1.0], locked=["steps", "cfg", "sampler_name", "scheduler", "denoise"],
    ))
    nodes.append(_node(
        21, "VAEDecode", group["09 Preview and evidence export"], "Build portrait image",
        inputs={"samples": Link(20), "vae": Link(12)}, input_types={"samples": "LATENT", "vae": "VAE"}, outputs=["image"], output_types=["IMAGE"], pos=(2600, 120),
    ))
    nodes.append(_node(
        22, "HOI4EvidenceExport", group["09 Preview and evidence export"], "Save portrait evidence",
        inputs={"job": Link(job_node_id), "source_master": Link(3, 0), "processed_reference": Link(6, 0), "approved_background": Link(8, 1), "candidate": Link(21), "mask": Link(8, 2), "prompt": Link(9, 0), "candidate_index": 0}, input_types={"job": "HOI4_JOB", "source_master": "IMAGE", "processed_reference": "IMAGE", "approved_background": "IMAGE", "candidate": "IMAGE", "mask": "MASK", "prompt": "STRING", "candidate_index": "INT"}, outputs=["image", "evidence_meta"], output_types=["IMAGE", "HOI4_META"], pos=(2920, 120), widgets=[0], locked=["candidate_index"],
    ))
    nodes.append(_node(
        23, "SaveImage", group["09 Preview and evidence export"], "Save portrait PNG",
        inputs={"images": Link(22, 0), "filename_prefix": "evidence/candidates"}, input_types={"images": "IMAGE", "filename_prefix": "STRING"}, outputs=[], output_types=[], pos=(3240, 120), widgets=["evidence/candidates"], locked=["filename_prefix"],
    ))

    if is_human:
        # Human workflows expose the key image checkpoints in the UI.  These
        # nodes are read-only inspection surfaces; the agent graphs remain
        # unchanged and receive their prompt exclusively from the job contract.
        nodes.extend([
            _node(
                25, PREVIEW_NODE, group["02 Crop and source preparation"], "Cropped portrait",
                inputs={"images": Link(5, 0)}, input_types={"images": "IMAGE"}, outputs=["images"], output_types=["IMAGE"], pos=(4080, 300),
            ),
            _node(
                26, PREVIEW_NODE, group["03 Color and restoration"], "Prepared portrait",
                inputs={"images": Link(6, 0)}, input_types={"images": "IMAGE"}, outputs=["images"], output_types=["IMAGE"], pos=(4080, 500),
            ),
            _node(
                27, PREVIEW_NODE, group["04 Masks and approved background"], "Background preview",
                inputs={"images": Link(8, 1)}, input_types={"images": "IMAGE"}, outputs=["images"], output_types=["IMAGE"], pos=(4390, 500),
            ),
            _node(
                28, PREVIEW_NODE, group["09 Preview and evidence export"], "Saved portrait preview",
                inputs={"images": Link(22, 0)}, input_types={"images": "IMAGE"}, outputs=["images"], output_types=["IMAGE"], pos=(4690, 300),
            ),
            _node(
                30, PREVIEW_NODE, group["01 Subject selection"], "Input portrait preview",
                inputs={"images": Link(3, 0)}, input_types={"images": "IMAGE"}, outputs=["images"], output_types=["IMAGE"], pos=(870, 280),
            ),
        ])

    if profile in LOW_MEMORY_PROFILE_IDS:
        # These are deliberately UI-only notes.  They make the lower-memory
        # choices discoverable without putting an unverified GGUF loader into
        # the executable API graph.
        nodes.extend([
            _node(
                31, "Note", group["06 Krea 2 identity edit"], "Lower-memory model options",
                widgets=["These options are shown for planning only. The active route remains the pinned Krea 2 Turbo model and identity edit adapter."],
            ),
            _node(
                32, "Note", group["06 Krea 2 identity edit"], "Optional 12 GB model path",
                widgets=["Placeholder only — not connected. Activate only after an official, checksum-locked Krea identity-edit GGUF and loader parity pass on a 12 GB host."],
            ),
            _node(
                33, "Note", group["06 Krea 2 identity edit"], "Optional 8 GB model path",
                widgets=["Placeholder only — not connected. Activate only after an official, checksum-locked Krea identity-edit GGUF and loader parity pass on an 8 GB host."],
            ),
        ])

    _apply_visual_layout(nodes, is_human=is_human)

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
        "prompt_source": "autoprompter" if is_human else "job_contract",
        "prompt_model": limits["prompt_model"],
        "controlnet_policy": "not_included; no approved live-compatible ControlNet experiment demonstrated a benefit over the Krea identity reference, mask, and approved-background route",
        "remote_authentication": "authenticated_runpod_gateway" if limits["route"] == "runpod" else "loopback_only",
        "identity_policy": "identity_edit_only; replacement_routes_are_not_in_the_graph",
        "work_canvas": {"width": width, "height": height, "pixels": width * height},
        "final_canvas": {"width": 156, "height": 210},
        "required_groups": GROUP_LABELS,
        "locked_controls": {node.title: node.locked for node in nodes if node.locked},
        "required_core_nodes": sorted(CORE_NODES | ({PREVIEW_NODE} if is_human else set())),
        "preview_nodes": [node.title for node in nodes if node.class_type == PREVIEW_NODE],
        "final_preview_save_pair": {
            "preview_node_id": 28 if is_human else None,
            "save_node_id": 23,
            "shared_source_node_id": 22,
            "shared_source_slot": 0,
            "policy": "human_final_preview_and_save_consume_the_same_evidence_export_image" if is_human else "agent_save_only",
        },
        "required_krea_nodes": sorted(KREA_NODES),
        "required_project_nodes": sorted((PROJECT_NODES | (HUMAN_ONLY_PROJECT_NODES if is_human else set())) & {node.class_type for node in nodes}),
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


def validate_graph(graph: GraphSpec) -> None:
    ids = [node.node_id for node in graph.nodes]
    if len(ids) != len(set(ids)):
        raise ValueError("workflow node ids are not unique")
    if graph.groups != GROUP_LABELS:
        raise ValueError("workflow group order does not match the delivery contract")
    class_names = {node.class_type for node in graph.nodes}
    if any(token in node.class_type.casefold() for node in graph.nodes for token in FORBIDDEN_CLASS_TOKENS):
        raise ValueError("workflow contains a forbidden face-swap/replacement class")
    if graph.metadata["human_workflow"]:
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
    common_project_nodes = PROJECT_NODES - {"HOI4PromptInput", "HOI4AutopromptClient"}
    if not graph.metadata["human_workflow"]:
        common_project_nodes -= HUMAN_ONLY_PROJECT_NODES
    required = CORE_NODES | KREA_NODES | common_project_nodes
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


def _apply_visual_layout(nodes: list[NodeSpec], *, is_human: bool) -> None:
    """Place nodes and image checkpoints on the compact two-row stage board."""

    positions = {
        1: (70, 100), 24: (440, 100), 2: (70, 300), 3: (70, 500),
        4: (870, 100), 30: (870, 280),
        5: (1420, 100), 25: (1420, 280),
        6: (1900, 100), 26: (1900, 280),
        7: (2380, 100), 8: (2380, 300), 27: (2700, 230),
        9: (70, 900),
        10: (620, 900), 11: (620, 1050), 12: (620, 1200), 13: (620, 1350),
        14: (900, 900), 15: (900, 1050), 16: (900, 1200), 17: (900, 1350),
        18: (1560, 1000),
        19: (1940, 900), 20: (1940, 1080), 29: (1940, 1300),
        21: (2320, 900), 22: (2640, 900), 23: (2640, 1090), 28: (2940, 900),
        31: (1200, 900), 32: (1200, 1050), 33: (1200, 1210),
    }
    sizes = {
        1: (350, 170), 24: (350, 580), 2: (350, 140), 3: (350, 140),
        4: (300, 150), 30: (340, 420),
        5: (320, 150), 25: (340, 420),
        6: (320, 150), 26: (340, 420),
        7: (320, 150), 8: (320, 180), 27: (340, 420),
        9: (440, 520 if is_human else 230),
        10: (260, 130), 11: (260, 130), 12: (260, 130), 13: (260, 130),
        14: (260, 130), 15: (260, 130), 16: (260, 130), 17: (260, 130),
        18: (260, 170), 19: (260, 150), 20: (260, 180), 29: (260, 130),
        21: (300, 140), 22: (300, 170), 23: (300, 140), 28: (400, 480),
        31: (250, 120), 32: (250, 140), 33: (250, 140),
    }
    for node in nodes:
        if node.node_id in positions:
            node.pos = positions[node.node_id]
        if node.node_id in sizes:
            node.size = sizes[node.node_id]


def _api_json(graph: GraphSpec) -> dict[str, Any]:
    executable_nodes = [
        node for node in graph.nodes
        if node.node_id != 1 and node.class_type not in UI_ONLY_NODE_CLASSES
    ]
    return {
        "1": {
            "class_type": "HOI4JobInput",
            "inputs": {"execution_profile": graph.profile, "job_contract_path": "jobs/<job_id>/input.json", "candidate_count": int(PROFILE_LIMITS[graph.profile]["candidate_max"]), "retry_limit": int(PROFILE_LIMITS[graph.profile]["retry_max"]), "seed_policy": "derived"},
        },
        **{
            str(node.node_id): {"class_type": node.class_type, "inputs": {key: _api_value(value) for key, value in node.inputs.items() if key != "instruction_text" or graph.metadata["human_workflow"]}}
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
    for order, node in enumerate(graph.nodes):
        node_color, node_bgcolor = NODE_COLORS[node.group]
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
            "inputs": [{"name": name, "type": node.input_types.get(name, "*"), "link": input_links.get((node.node_id, name))} for name in node.inputs],
            "outputs": [{"name": name, "type": node.output_types[index] if index < len(node.output_types) else "*", "links": output_links.get((node.node_id, index))} for index, name in enumerate(node.outputs)],
            "properties": {"Node name for S&R": node.title, "hoi4_group": node.group, "hoi4_locked_controls": node.locked},
            "widgets_values": node.widgets,
        })
    groups = []
    for label in graph.groups:
        x, y, width, height = GROUP_LAYOUT[label]
        groups.append({"title": label, "bounding": [x, y, width, height], "color": GROUP_COLORS[label], "font_size": 24})
    return {
        "last_node_id": max(node.node_id for node in graph.nodes),
        "last_link_id": link_id - 1,
        "nodes": ui_nodes,
        "links": links,
        "groups": groups,
        "config": {},
        "extra": {"ds": {"scale": 0.7, "offset": [0, 0]}, **graph.metadata},
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
        "human_local_nvidia_16gb": root_path / "workflows/human/local_nvidia_16gb/human_local_nvidia_16gb.json",
        "human_full_power_gpu": root_path / "workflows/human/full_power_gpu/human_full_power_gpu.json",
        "agent_local_nvidia_16gb": root_path / "workflows/agent/local_nvidia_16gb/agent_local_nvidia_16gb.json",
        "agent_full_power_gpu": root_path / "workflows/agent/full_power_gpu/agent_full_power_gpu.json",
    }
    manifests: list[dict[str, Any]] = []
    live_probe_path = root_path / ".runtime" / "reports" / "live_comfy_compatibility.json"
    try:
        live_probe = json.loads(live_probe_path.read_text(encoding="utf-8")) if live_probe_path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        live_probe = {}
    live_workflows = {item.get("workflow_id"): item for item in live_probe.get("workflows", []) if isinstance(item, dict)}
    for workflow_id, ui_path in paths.items():
        graph = build_graph(workflow_id, root_path)
        classes = {node.class_type for node in graph.nodes}
        required_prompt_node = "HOI4AutopromptClient" if graph.metadata["human_workflow"] else "HOI4PromptInput"
        required_custom_nodes = sorted(KREA_NODES | (PROJECT_NODES - {"HOI4PromptInput", "HOI4AutopromptClient"} - (set() if graph.metadata["human_workflow"] else HUMAN_ONLY_PROJECT_NODES)) | {required_prompt_node} | (HUMAN_ONLY_PROJECT_NODES if graph.metadata["human_workflow"] else set()))
        required_models = ["krea2_turbo_fp8_scaled.safetensors", "qwen3vl_4b_fp8_scaled.safetensors", "qwen_image_vae.safetensors", "krea2_identity_edit_v1_2.safetensors", "hoi4_portrait_new_style_lora.safetensors"]
        if graph.metadata["human_workflow"]:
            required_models.append("Qwen3VL-4B-Instruct-Q4_K_M.gguf" if "local" in workflow_id else "Qwen3-VL-8B-Instruct-BF16-shards")
        api_path = ui_path.with_suffix(".api.json")
        atomic_json_write(ui_path, _ui_json(graph))
        atomic_json_write(api_path, _api_json(graph))
        required_node_packages = sorted({custom_node_by_class[class_name]["name"] for class_name in required_custom_nodes if class_name in custom_node_by_class})
        required_node_revisions = {name: custom_node_entries[name].get("revision") for name in required_node_packages}
        required_node_checksums = {name: custom_node_entries[name].get("source_tree_checksum") for name in required_node_packages}
        live_workflow = live_workflows.get(workflow_id, {})
        live_schema_pass = live_workflow.get("status") == "PASS" and live_probe.get("status") == "PASS_SCHEMA_ONLY_EXECUTION_BLOCKED"
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
            "required_core_nodes": sorted(CORE_NODES | ({PREVIEW_NODE} if graph.metadata["human_workflow"] else set())),
            "required_custom_nodes": required_custom_nodes,
            "required_custom_node_packages": required_node_packages,
            "required_custom_node_revisions": required_node_revisions,
            "required_custom_node_source_checksums": required_node_checksums,
            "required_models": required_models,
            "autoprompter_present": bool(PROFILE_LIMITS[workflow_id]["autoprompter"]),
            "prompt_source": "autoprompter" if PROFILE_LIMITS[workflow_id]["autoprompter"] else "job_contract",
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
    manifest = {"schema_version": "1.0.0", "generated_at": generated_at, "lock_version": "workflows-2026-07-26.1", "workflows": manifests, "status": manifest_status, "runtime_status": runtime_status}
    atomic_json_write(root_path / "manifests/workflow_manifest.json", manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build all configured deterministic ComfyUI workflow artifacts.")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args(argv)
    manifest = build_workflow_artifacts(args.root)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0
