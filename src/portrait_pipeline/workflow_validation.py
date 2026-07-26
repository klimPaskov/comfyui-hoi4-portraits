from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .constants import GROUP_LABELS
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
    if titles != GROUP_LABELS:
        issues.append(f"groups are not the exact required order: {titles!r}")
    metadata = api.get("_meta", {})
    if metadata.get("workflow_id") != workflow_id:
        issues.append("workflow id metadata mismatch")
    if workflow_id.startswith("human_"):
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
    if any(_contains_value(ui, token) for token in ("faceswap", "face_swap", "subject_replacement")):
        issues.append("workflow contains a prohibited identity-replacement route")
    required = set(metadata.get("required_core_nodes", [])) | set(metadata.get("required_krea_nodes", [])) | set(metadata.get("required_project_nodes", []))
    present = {str(node.get("type")) for node in ui_nodes} | {str(node.get("class_type")) for node in api_nodes.values()}
    missing = sorted(required - present)
    if missing:
        issues.append(f"required node classes missing: {missing}")
    if not any(node.get("type") == "HOI4EvidenceExport" for node in ui_nodes):
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
        "human_local_mac_16gb": ("workflows/human/local_mac_16gb/human_local_mac_16gb.json", "workflows/human/local_mac_16gb/human_local_mac_16gb.api.json"),
        "human_full_power_gpu": ("workflows/human/full_power_gpu/human_full_power_gpu.json", "workflows/human/full_power_gpu/human_full_power_gpu.api.json"),
        "agent_local_mac_16gb": ("workflows/agent/local_mac_16gb/agent_local_mac_16gb.json", "workflows/agent/local_mac_16gb/agent_local_mac_16gb.api.json"),
        "agent_remote_runpod": ("workflows/agent/remote_runpod/agent_remote_runpod.json", "workflows/agent/remote_runpod/agent_remote_runpod.api.json"),
    }
    return [validate_workflow_file(workflow_id, root_path / ui, root_path / api, root_path) for workflow_id, (ui, api) in specs.items()]

