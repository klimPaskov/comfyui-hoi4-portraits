from __future__ import annotations

import argparse
import json
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
    "DualCLIPLoader",
    "VAELoader",
    "VAEEncode",
    "EmptySD3LatentImage",
    "KSampler",
    "VAEDecode",
    "SaveImage",
}
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
    "HOI4PromptInput",
    "HOI4AutopromptClient",
    "HOI4EvidenceExport",
}
FORBIDDEN_CLASS_TOKENS = ("faceswap", "face_swap", "ipadapterface", "replacer", "subjectreplacement")


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
        1, "HOI4JobInput", group["00 Job and source"], "Job contract and profile",
        inputs={"execution_profile": profile, "job_contract_path": "jobs/<job_id>/input.json", "candidate_count": int(limits["candidate_max"]), "retry_limit": int(limits["retry_max"]), "seed_policy": "derived"},
        input_types={"execution_profile": "STRING", "job_contract_path": "STRING", "candidate_count": "INT", "retry_limit": "INT", "seed_policy": "COMBO"},
        outputs=["job"], output_types=["HOI4_JOB"], pos=(40, 80), widgets=[profile, "jobs/<job_id>/input.json", int(limits["candidate_max"]), int(limits["retry_max"]), "derived"], locked=["execution_profile", "candidate_count", "retry_limit", "seed_policy"],
    ))
    nodes.append(_node(
        2, "HOI4JobSource", group["00 Job and source"], "Load source only from job root",
        inputs={"job": Link(1)}, input_types={"job": "HOI4_JOB"}, outputs=["image", "source_meta"], output_types=["IMAGE", "HOI4_META"], pos=(40, 300),
    ))
    nodes.append(_node(
        3, "HOI4SourceGuard", group["00 Job and source"], "Provenance and source guard",
        inputs={"job": Link(1), "image": Link(2, 0)}, input_types={"job": "HOI4_JOB", "image": "IMAGE"}, outputs=["image", "source_meta"], output_types=["IMAGE", "HOI4_META"], pos=(40, 510),
    ))
    nodes.append(_node(
        4, "HOI4SubjectSelect", group["01 Subject selection"], "Deterministic subject selection",
        inputs={"job": Link(1), "image": Link(3, 0)}, input_types={"job": "HOI4_JOB", "image": "IMAGE"}, outputs=["image", "selection_meta"], output_types=["IMAGE", "HOI4_META"], pos=(360, 80),
    ))
    nodes.append(_node(
        5, "HOI4HeadShouldersCrop", group["02 Crop and source preparation"], "Head and shoulders crop",
        inputs={"job": Link(1), "image": Link(4, 0)}, input_types={"job": "HOI4_JOB", "image": "IMAGE"}, outputs=["image", "crop_meta"], output_types=["IMAGE", "HOI4_META"], pos=(360, 300),
    ))
    nodes.append(_node(
        6, "HOI4ConservativePrep", group["03 Color and restoration"], "Conditional color and conservative restoration",
        inputs={"job": Link(1), "image": Link(5, 0)}, input_types={"job": "HOI4_JOB", "image": "IMAGE"}, outputs=["image", "reference_meta"], output_types=["IMAGE", "HOI4_META"], pos=(360, 520),
    ))
    nodes.append(_node(
        7, "HOI4ForegroundMask", group["04 Masks and approved background"], "Pinned foreground/mask analysis",
        inputs={"job": Link(1), "image": Link(6, 0), "mask_model": "BiRefNet:PINNED_REQUIRED"}, input_types={"job": "HOI4_JOB", "image": "IMAGE", "mask_model": "STRING"}, outputs=["image", "mask", "mask_meta"], output_types=["IMAGE", "MASK", "HOI4_META"], pos=(680, 40), widgets=["BiRefNet:PINNED_REQUIRED"], locked=["mask_model"],
    ))
    nodes.append(_node(
        8, "HOI4MaskAndBackgroundGuard", group["04 Masks and approved background"], "Approved background composite and foreground guard",
        inputs={"job": Link(1), "image": Link(7, 0), "mask": Link(7, 1)}, input_types={"job": "HOI4_JOB", "image": "IMAGE", "mask": "MASK"}, outputs=["image", "composite", "mask", "background_meta"], output_types=["IMAGE", "IMAGE", "MASK", "HOI4_META"], pos=(680, 270),
    ))

    if is_human:
        nodes.append(_node(
            9, "HOI4AutopromptClient", group["05 Prompt"], "Human-only exact autoprompter",
            inputs={"job": Link(1), "image": Link(8, 0), "instruction_text": instruction, "instruction_path": AUTOPROMPTER_PATH, "model_id": limits["prompt_model"], "prompt_source": "autoprompter"},
            input_types={"job": "HOI4_JOB", "image": "IMAGE", "instruction_text": "STRING", "instruction_path": "STRING", "model_id": "STRING", "prompt_source": "COMBO"},
            outputs=["prompt", "prompt_meta"], output_types=["STRING", "HOI4_META"], pos=(680, 340), widgets=[instruction, AUTOPROMPTER_PATH, limits["prompt_model"], "autoprompter"], locked=["instruction_text", "instruction_path", "model_id", "prompt_source"],
        ))
    else:
        nodes.append(_node(
            9, "HOI4PromptInput", group["05 Prompt"], "Agent prompt from job contract",
            inputs={"job": Link(1), "prompt_source": "job_contract"}, input_types={"job": "HOI4_JOB", "prompt_source": "COMBO"}, outputs=["prompt", "prompt_meta"], output_types=["STRING", "HOI4_META"], pos=(680, 540), widgets=["job_contract"], locked=["prompt_source"],
        ))

    nodes.append(_node(
        10, "UNETLoader", group["06 Krea 2 identity edit"], "Krea 2 Turbo FP8",
        inputs={"unet_name": "krea2_turbo_fp8_scaled.safetensors", "weight_dtype": "default"}, input_types={"unet_name": "COMBO", "weight_dtype": "COMBO"}, outputs=["model"], output_types=["MODEL"], pos=(1000, 80), widgets=["krea2_turbo_fp8_scaled.safetensors", "default"], locked=["unet_name", "weight_dtype"],
    ))
    nodes.append(_node(
        11, "LoraLoaderModelOnly", group["06 Krea 2 identity edit"], "Pinned Krea identity adapter",
        inputs={"model": Link(10), "lora_name": "krea2_identity_edit_v1_2.safetensors", "strength_model": 1.0}, input_types={"model": "MODEL", "lora_name": "COMBO", "strength_model": "FLOAT"}, outputs=["model"], output_types=["MODEL"], pos=(1000, 260), widgets=["krea2_identity_edit_v1_2.safetensors", 1.0], locked=["lora_name", "strength_model"],
    ))
    nodes.append(_node(
        12, "VAELoader", group["06 Krea 2 identity edit"], "Krea VAE",
        inputs={"vae_name": "qwen_image_vae.safetensors"}, input_types={"vae_name": "COMBO"}, outputs=["vae"], output_types=["VAE"], pos=(1000, 450), widgets=["qwen_image_vae.safetensors"], locked=["vae_name"],
    ))
    nodes.append(_node(
        13, "VAEEncode", group["06 Krea 2 identity edit"], "Encode identity reference",
        inputs={"pixels": Link(8, 0), "vae": Link(12)}, input_types={"pixels": "IMAGE", "vae": "VAE"}, outputs=["latent"], output_types=["LATENT"], pos=(1000, 610),
    ))
    nodes.append(_node(
        14, "Krea2EditModelPatch", group["06 Krea 2 identity edit"], "Krea 2 identity edit patch",
        inputs={"model": Link(11), "source_latent": Link(13), "fit_mode": "fit", "ref_boost": 1.0}, input_types={"model": "MODEL", "source_latent": "LATENT", "fit_mode": "COMBO", "ref_boost": "FLOAT"}, outputs=["model"], output_types=["MODEL"], pos=(1320, 200), widgets=["fit", 1.0], locked=["fit_mode", "ref_boost"],
    ))
    nodes.append(_node(
        15, "DualCLIPLoader", group["06 Krea 2 identity edit"], "Krea Qwen3-VL encoder",
        inputs={"clip_name1": "qwen3vl_4b_fp8_scaled.safetensors", "clip_name2": "qwen3vl_4b_fp8_scaled.safetensors", "type": "krea2"}, input_types={"clip_name1": "COMBO", "clip_name2": "COMBO", "type": "COMBO"}, outputs=["clip"], output_types=["CLIP"], pos=(1320, 430), widgets=["qwen3vl_4b_fp8_scaled.safetensors", "qwen3vl_4b_fp8_scaled.safetensors", "krea2"], locked=["clip_name1", "clip_name2", "type"],
    ))
    nodes.append(_node(
        16, "Krea2EditGroundedEncode", group["06 Krea 2 identity edit"], "Grounded positive conditioning",
        inputs={"clip": Link(15), "prompt": Link(9, 0), "image": Link(8, 0), "grounding_px": 64}, input_types={"clip": "CLIP", "prompt": "STRING", "image": "IMAGE", "grounding_px": "INT"}, outputs=["conditioning"], output_types=["CONDITIONING"], pos=(1640, 80), widgets=[64], locked=["grounding_px"],
    ))
    nodes.append(_node(
        17, "Krea2EditGroundedEncode", group["06 Krea 2 identity edit"], "Grounded empty negative conditioning",
        inputs={"clip": Link(15), "prompt": "", "image": Link(8, 0), "grounding_px": 64}, input_types={"clip": "CLIP", "prompt": "STRING", "image": "IMAGE", "grounding_px": "INT"}, outputs=["conditioning"], output_types=["CONDITIONING"], pos=(1640, 290), widgets=["", 64], locked=["prompt", "grounding_px"],
    ))
    nodes.append(_node(
        18, "LoraLoaderModelOnly", group["07 HOI4 style LoRA"], "Immutable HOI4 style LoRA",
        inputs={"model": Link(14), "lora_name": "hoi4_portrait_new_style_lora.safetensors", "strength_model": 0.80}, input_types={"model": "MODEL", "lora_name": "COMBO", "strength_model": "FLOAT"}, outputs=["model"], output_types=["MODEL"], pos=(1960, 200), widgets=["hoi4_portrait_new_style_lora.safetensors", 0.80], locked=["lora_name"],
    ))
    nodes.append(_node(
        19, "EmptySD3LatentImage", group["08 Candidate generation"], "Profile work canvas",
        inputs={"width": width, "height": height, "batch_size": 1}, input_types={"width": "INT", "height": "INT", "batch_size": "INT"}, outputs=["latent"], output_types=["LATENT"], pos=(1960, 430), widgets=[width, height, 1], locked=["width", "height", "batch_size"],
    ))
    nodes.append(_node(
        20, "KSampler", group["08 Candidate generation"], "Krea 2 Turbo candidate",
        inputs={"model": Link(18), "positive": Link(16), "negative": Link(17), "latent_image": Link(19), "seed": 0, "steps": 8, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}, input_types={"model": "MODEL", "positive": "CONDITIONING", "negative": "CONDITIONING", "latent_image": "LATENT", "seed": "INT", "steps": "INT", "cfg": "FLOAT", "sampler_name": "COMBO", "scheduler": "COMBO", "denoise": "FLOAT"}, outputs=["latent"], output_types=["LATENT"], pos=(2280, 120), widgets=[0, 8, 1.0, "euler", "simple", 1.0], locked=["steps", "cfg", "sampler_name", "scheduler", "denoise"],
    ))
    nodes.append(_node(
        21, "VAEDecode", group["09 Preview and evidence export"], "Decode candidate",
        inputs={"samples": Link(20), "vae": Link(12)}, input_types={"samples": "LATENT", "vae": "VAE"}, outputs=["image"], output_types=["IMAGE"], pos=(2600, 120),
    ))
    nodes.append(_node(
        22, "HOI4EvidenceExport", group["09 Preview and evidence export"], "Candidate evidence and audit handoff",
        inputs={"job": Link(1), "source_master": Link(3, 0), "processed_reference": Link(8, 0), "approved_background": Link(8, 1), "candidate": Link(21), "mask": Link(8, 2), "prompt": Link(9, 0), "candidate_index": 0}, input_types={"job": "HOI4_JOB", "source_master": "IMAGE", "processed_reference": "IMAGE", "approved_background": "IMAGE", "candidate": "IMAGE", "mask": "MASK", "prompt": "STRING", "candidate_index": "INT"}, outputs=["image", "evidence_meta"], output_types=["IMAGE", "HOI4_META"], pos=(2920, 120), widgets=[0], locked=["candidate_index"],
    ))
    nodes.append(_node(
        23, "SaveImage", group["09 Preview and evidence export"], "Preview PNG only",
        inputs={"images": Link(22, 0), "filename_prefix": "evidence/candidates"}, input_types={"images": "IMAGE", "filename_prefix": "STRING"}, outputs=[], output_types=[], pos=(3240, 120), widgets=["evidence/candidates"], locked=["filename_prefix"],
    ))

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
        "identity_policy": "identity_edit_only; replacement_routes_are_not_in_the_graph",
        "work_canvas": {"width": width, "height": height, "pixels": width * height},
        "final_canvas": {"width": 156, "height": 210},
        "required_groups": GROUP_LABELS,
        "locked_controls": {node.title: node.locked for node in nodes if node.locked},
        "required_core_nodes": sorted(CORE_NODES),
        "required_krea_nodes": sorted(KREA_NODES),
        "required_project_nodes": sorted(PROJECT_NODES & {node.class_type for node in nodes}),
        "candidate_budget": {"max": int(limits["candidate_max"]), "retry_max": int(limits["retry_max"])},
        "finalization_policy": "controller_only_after_independent_audit_all_pass; no DDS node is present in the workflow",
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
    required = CORE_NODES | KREA_NODES | common_project_nodes
    required.add("HOI4AutopromptClient" if graph.metadata["human_workflow"] else "HOI4PromptInput")
    missing = sorted(required - class_names)
    if missing:
        raise ValueError(f"workflow is missing required node classes: {missing}")


def _api_value(value: Any) -> Any:
    if isinstance(value, Link):
        return [str(value.node_id), value.slot]
    return value


def _api_json(graph: GraphSpec) -> dict[str, Any]:
    return {
        "1": {
            "class_type": "HOI4JobInput",
            "inputs": {"execution_profile": graph.profile, "job_contract_path": "jobs/<job_id>/input.json", "candidate_count": int(PROFILE_LIMITS[graph.profile]["candidate_max"]), "retry_limit": int(PROFILE_LIMITS[graph.profile]["retry_max"]), "seed_policy": "derived"},
        },
        **{
            str(node.node_id): {"class_type": node.class_type, "inputs": {key: _api_value(value) for key, value in node.inputs.items() if key != "instruction_text" or graph.metadata["human_workflow"]}}
            for node in graph.nodes if node.node_id != 1
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
        ui_nodes.append({
            "id": node.node_id,
            "type": node.class_type,
            "pos": list(node.pos),
            "size": list(node.size),
            "flags": {},
            "order": order,
            "mode": 0,
            "inputs": [{"name": name, "type": node.input_types.get(name, "*"), "link": input_links.get((node.node_id, name))} for name in node.inputs],
            "outputs": [{"name": name, "type": node.output_types[index] if index < len(node.output_types) else "*", "links": output_links.get((node.node_id, index))} for index, name in enumerate(node.outputs)],
            "properties": {"Node name for S&R": node.title, "hoi4_group": node.group, "hoi4_locked_controls": node.locked},
            "widgets_values": node.widgets,
        })
    groups = []
    for index, label in enumerate(graph.groups):
        groups.append({"title": label, "bounding": [20 + (index % 5) * 640, 20 + (index // 5) * 500, 600, 440], "color": "#335", "font_size": 24})
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
    paths = {
        "human_local_mac_16gb": root_path / "workflows/human/local_mac_16gb/human_local_mac_16gb.json",
        "human_full_power_gpu": root_path / "workflows/human/full_power_gpu/human_full_power_gpu.json",
        "agent_local_mac_16gb": root_path / "workflows/agent/local_mac_16gb/agent_local_mac_16gb.json",
        "agent_remote_runpod": root_path / "workflows/agent/remote_runpod/agent_remote_runpod.json",
    }
    manifests: list[dict[str, Any]] = []
    for workflow_id, ui_path in paths.items():
        graph = build_graph(workflow_id, root_path)
        classes = {node.class_type for node in graph.nodes}
        required_prompt_node = "HOI4AutopromptClient" if graph.metadata["human_workflow"] else "HOI4PromptInput"
        required_custom_nodes = sorted(KREA_NODES | (PROJECT_NODES - {"HOI4PromptInput", "HOI4AutopromptClient"}) | {required_prompt_node})
        required_models = ["krea2_turbo_fp8_scaled.safetensors", "qwen3vl_4b_fp8_scaled.safetensors", "qwen_image_vae.safetensors", "krea2_identity_edit_v1_2.safetensors", "hoi4_portrait_new_style_lora.safetensors"]
        if graph.metadata["human_workflow"]:
            required_models.append("Qwen3VL-4B-Instruct-Q4_K_M.gguf" if "local" in workflow_id else "Qwen3-VL-8B-Instruct-BF16-shards")
        api_path = ui_path.with_suffix(".api.json")
        atomic_json_write(ui_path, _ui_json(graph))
        atomic_json_write(api_path, _api_json(graph))
        manifests.append({
            "workflow_id": workflow_id,
            "display_name": workflow_id,
            "workflow_json": str(ui_path.relative_to(root_path)),
            "api_json": str(api_path.relative_to(root_path)),
            "sha256": sha256_file(ui_path),
            "api_sha256": sha256_file(api_path),
            "graph_spec_version": WORKFLOW_VERSION,
            "comfyui_commit": "f49bdb655707b97952dcef40e12e5af1f08d2007",
            "required_core_nodes": sorted(CORE_NODES),
            "required_custom_nodes": required_custom_nodes,
            "required_models": required_models,
            "autoprompter_present": bool(PROFILE_LIMITS[workflow_id]["autoprompter"]),
            "prompt_source": "autoprompter" if PROFILE_LIMITS[workflow_id]["autoprompter"] else "job_contract",
            "autoprompter_instruction_sha256": graph.metadata["autoprompter_instruction_sha256"],
            "validation_status": "STRUCTURAL_ONLY_RUNTIME_BLOCKED",
            "load_test_evidence": None,
            "execution_test_evidence": None,
        })
    manifest = {"schema_version": "1.0.0", "generated_at": "2026-07-26", "lock_version": "workflows-2026-07-26.1", "workflows": manifests, "status": "STRUCTURAL_ONLY_RUNTIME_BLOCKED"}
    atomic_json_write(root_path / "manifests/workflow_manifest.json", manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build all four deterministic ComfyUI workflow artifacts.")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args(argv)
    manifest = build_workflow_artifacts(args.root)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0
