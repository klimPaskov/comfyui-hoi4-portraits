from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .constants import GROUP_LABELS, RANDOM_PORTRAIT_PROMPT_PATH
from .prompt import autoprompter_instruction
from .util import project_root, scan_text_for_secrets, sha256_file


def _contains_value(value: Any, needle: str) -> bool:
    if isinstance(value, str):
        return needle in value
    if isinstance(value, dict):
        return any(_contains_value(key, needle) or _contains_value(item, needle) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_value(item, needle) for item in value)
    return False


def validate_workflow_file(workflow_id: str, ui_path: str | Path, api_path: str | Path, root: str | Path | None = None) -> dict[str, Any]:
    root_path = project_root(root)
    ui = json.loads(Path(ui_path).read_text(encoding="utf-8"))
    api = json.loads(Path(api_path).read_text(encoding="utf-8"))
    issues: list[str] = []
    ui_nodes = ui.get("nodes", [])
    api_nodes = {str(key): value for key, value in api.items() if not str(key).startswith("_")}
    ids = [node.get("id") for node in ui_nodes]
    if len(ids) != len(set(ids)):
        issues.append("UI node ids are not unique")
    titles = [group.get("title") for group in ui.get("groups", [])]
    metadata = api.get("_meta", {})
    required_groups = metadata.get("required_groups", GROUP_LABELS)
    if titles != required_groups:
        issues.append(f"groups do not match the workflow layout: {titles!r}")
    if metadata.get("workflow_id") != workflow_id:
        issues.append("workflow id metadata mismatch")
    workflow_kind = metadata.get("workflow_kind")
    if workflow_kind == "random_text_to_image":
        autoprompt_nodes = [node for node in ui_nodes if node.get("type") == "HOI4RandomPortraitPrompt"]
        agent_prompt_nodes = [node for node in ui_nodes if node.get("type") == "HOI4PromptJobInput"]
        if metadata.get("human_workflow"):
            if len(autoprompt_nodes) != 1 or agent_prompt_nodes:
                issues.append("human random portrait workflow must contain one text-only prompt builder")
        elif len(agent_prompt_nodes) != 1 or autoprompt_nodes:
            issues.append("agent random portrait workflow must contain one job-contract prompt input")
        if autoprompt_nodes:
            instruction_path = root_path / RANDOM_PORTRAIT_PROMPT_PATH
            instruction = instruction_path.read_text(encoding="utf-8")
            values = autoprompt_nodes[0].get("widgets_values", [])
            if len(values) < 9 or values[7] != instruction or values[8] != RANDOM_PORTRAIT_PROMPT_PATH:
                issues.append("random portrait instruction does not match the project file")
            if metadata.get("autoprompter_instruction_sha256") != sha256_file(instruction_path):
                issues.append("random portrait instruction checksum mismatch")
        prohibited = {"LoadImage", "HOI4JobSource", "HOI4AutopromptClient", "Krea2EditModelPatch", "Krea2EditGroundedEncode"}
        if any(node.get("type") in prohibited for node in ui_nodes):
            issues.append("random portrait workflow contains an image-input or identity-edit node")
        if metadata.get("vision_model_required") is not False:
            issues.append("random portrait workflow does not declare vision-free prompting")
    elif workflow_kind == "portrait_preparation":
        required_preparation_nodes = {
            "LoadImage",
            "HOI4PortraitCrop",
            "DDColor_Colorize",
            "HOI4UseColorWhenNeeded",
            "HOI4FinishPreparedPortrait",
            "PreviewImage",
            "SaveImage",
        }
        present_types = {node.get("type") for node in ui_nodes}
        missing_preparation = sorted(required_preparation_nodes - present_types)
        if missing_preparation:
            issues.append(f"portrait preparation nodes are missing: {missing_preparation}")
        if any(node.get("type") in {"HOI4AutopromptClient", "Krea2EditModelPatch", "KSampler"} for node in ui_nodes):
            issues.append("portrait preparation workflow continues into portrait generation")
    elif metadata.get("human_workflow"):
        autoprompt_nodes = [node for node in ui_nodes if node.get("type") == "HOI4AutopromptClient"]
        if len(autoprompt_nodes) != 1:
            issues.append("human workflow must contain exactly one autoprompter node")
        else:
            instruction = autoprompter_instruction(root_path)
            values = autoprompt_nodes[0].get("widgets_values", [])
            if not values or values[0] != instruction:
                issues.append("human workflow instruction does not exactly match the approved instruction file")
            if metadata.get("autoprompter_instruction_sha256") != sha256_file(root_path / "prompts/autoprompter_instruction.txt"):
                issues.append("human workflow instruction checksum mismatch")
    else:
        if any(node.get("type") == "HOI4AutopromptClient" for node in ui_nodes):
            issues.append("agent workflow contains an autoprompter node")
        if metadata.get("prompt_source") != "job_contract":
            issues.append("agent workflow prompt source is not job_contract")
        if any(_contains_value(node, "Qwen3-VL-4B-Instruct-GGUF") or _contains_value(node, "Qwen3-VL-8B-Instruct") for node in ui_nodes):
            issues.append("agent workflow contains an autoprompter model reference")
    if workflow_kind not in {"random_text_to_image", "portrait_preparation"}:
        present_types = {node.get("type") for node in ui_nodes}
        if not {"DDColor_Colorize", "HOI4ConservativePrep"} <= present_types:
            issues.append("source workflow does not include automatic portrait preparation")
    if any(_contains_value(ui, token) for token in ("faceswap", "face_swap", "subject_replacement")):
        issues.append("workflow contains a prohibited identity-replacement route")
    if metadata.get("workflow_kind") != "controlnet_composition" and any(_contains_value(node, token) for node in ui_nodes for token in ("ControlNet", "controlnet")):
        issues.append("workflow contains an unapproved ControlNet route")
    required = set(metadata.get("required_core_nodes", [])) | set(metadata.get("required_krea_nodes", [])) | set(metadata.get("required_project_nodes", []))
    present = {str(node.get("type")) for node in ui_nodes} | {str(node.get("class_type")) for node in api_nodes.values()}
    missing = sorted(required - present)
    if missing:
        issues.append(f"required node classes missing: {missing}")
    if workflow_kind not in {"random_text_to_image", "portrait_preparation"} and not any(node.get("type") == "HOI4EvidenceExport" for node in ui_nodes):
        issues.append("evidence export is not connected")
    return {
        "workflow_id": workflow_id,
        "ui_path": str(Path(ui_path).relative_to(root_path)),
        "api_path": str(Path(api_path).relative_to(root_path)),
        "ui_sha256": sha256_file(ui_path),
        "api_sha256": sha256_file(api_path),
        "structural_status": "PASS" if not issues else "FAIL",
        "runtime_status": "BLOCKED_UNVERIFIED",
        "issues": issues,
        "node_count": len(ui_nodes),
        "group_count": len(titles),
        "api_node_count": len(api_nodes),
    }


def validate_all_workflows(root: str | Path | None = None) -> list[dict[str, Any]]:
    root_path = project_root(root)
    specs = {
        "hoi4_portraits_local_nvidia_16gb": ("workflows/human/local_nvidia_16gb/hoi4_portraits_local_nvidia_16gb.json", "workflows/human/local_nvidia_16gb/hoi4_portraits_local_nvidia_16gb.api.json"),
        "hoi4_portraits_full_power_gpu": ("workflows/human/full_power_gpu/hoi4_portraits_full_power_gpu.json", "workflows/human/full_power_gpu/hoi4_portraits_full_power_gpu.api.json"),
        "hoi4_portraits_agent_local_nvidia_16gb": ("workflows/agent/local_nvidia_16gb/hoi4_portraits_agent_local_nvidia_16gb.json", "workflows/agent/local_nvidia_16gb/hoi4_portraits_agent_local_nvidia_16gb.api.json"),
        "hoi4_portraits_agent_full_power_gpu": ("workflows/agent/full_power_gpu/hoi4_portraits_agent_full_power_gpu.json", "workflows/agent/full_power_gpu/hoi4_portraits_agent_full_power_gpu.api.json"),
        "hoi4_portraits_no_input_local_nvidia_16gb": ("workflows/human/no_input_local_nvidia_16gb/hoi4_portraits_no_input_local_nvidia_16gb.json", "workflows/human/no_input_local_nvidia_16gb/hoi4_portraits_no_input_local_nvidia_16gb.api.json"),
        "hoi4_portraits_no_input_full_power_gpu": ("workflows/human/no_input_full_power_gpu/hoi4_portraits_no_input_full_power_gpu.json", "workflows/human/no_input_full_power_gpu/hoi4_portraits_no_input_full_power_gpu.api.json"),
        "hoi4_portraits_agent_no_input_local_nvidia_16gb": ("workflows/agent/no_input_local_nvidia_16gb/hoi4_portraits_agent_no_input_local_nvidia_16gb.json", "workflows/agent/no_input_local_nvidia_16gb/hoi4_portraits_agent_no_input_local_nvidia_16gb.api.json"),
        "hoi4_portraits_agent_no_input_full_power_gpu": ("workflows/agent/no_input_full_power_gpu/hoi4_portraits_agent_no_input_full_power_gpu.json", "workflows/agent/no_input_full_power_gpu/hoi4_portraits_agent_no_input_full_power_gpu.api.json"),
        "hoi4_portraits_prepare_portrait_for_hoi4": ("workflows/human/prepare_portrait/hoi4_portraits_prepare_portrait_for_hoi4.json", "workflows/human/prepare_portrait/hoi4_portraits_prepare_portrait_for_hoi4.api.json"),
    }
    return [validate_workflow_file(workflow_id, root_path / ui, root_path / api, root_path) for workflow_id, (ui, api) in specs.items()]
