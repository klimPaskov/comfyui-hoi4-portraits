#!/usr/bin/env python3
"""Verify the pinned ComfyUI/Krea graph contract against a live loopback server.

This probe intentionally stops at registry/schema validation.  It does not submit
an identity-edit job: a production execution requires an approved source fixture,
an approved background, calibrated thresholds, and the independent auditor.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from portrait_pipeline.constants import PROFILE_LIMITS  # noqa: E402
from portrait_pipeline.util import atomic_json_write, project_root  # noqa: E402


WORKFLOW_PATHS = {
    "hoi4_portraits_local_nvidia_16gb": "workflows/human/local_nvidia_16gb/hoi4_portraits_local_nvidia_16gb.api.json",
    "hoi4_portraits_full_power_gpu": "workflows/human/full_power_gpu/hoi4_portraits_full_power_gpu.api.json",
    "hoi4_portraits_agent_local_nvidia_16gb": "workflows/agent/local_nvidia_16gb/hoi4_portraits_agent_local_nvidia_16gb.api.json",
    "hoi4_portraits_agent_full_power_gpu": "workflows/agent/full_power_gpu/hoi4_portraits_agent_full_power_gpu.api.json",
    "hoi4_portraits_no_input_local_nvidia_16gb": "workflows/human/no_input_local_nvidia_16gb/hoi4_portraits_no_input_local_nvidia_16gb.api.json",
    "hoi4_portraits_no_input_full_power_gpu": "workflows/human/no_input_full_power_gpu/hoi4_portraits_no_input_full_power_gpu.api.json",
    "hoi4_portraits_agent_no_input_local_nvidia_16gb": "workflows/agent/no_input_local_nvidia_16gb/hoi4_portraits_agent_no_input_local_nvidia_16gb.api.json",
    "hoi4_portraits_agent_no_input_full_power_gpu": "workflows/agent/no_input_full_power_gpu/hoi4_portraits_agent_no_input_full_power_gpu.api.json",
    "hoi4_portraits_prepare_portrait_for_hoi4": "workflows/human/prepare_portrait/hoi4_portraits_prepare_portrait_for_hoi4.api.json",
    "hoi4_portraits_prepare_portrait_basic": "workflows/human/prepare_portrait_basic/hoi4_portraits_prepare_portrait_basic.api.json",
}
FORBIDDEN_TOKENS = ("faceswap", "face_swap", "ipadapterface", "replacer", "subjectreplacement")
REQUIRED_CORE_NODES = {
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
REQUIRED_HUMAN_PREVIEW_NODE = "PreviewImage"
REQUIRED_KREA_NODES = {"Krea2EditModelPatch", "Krea2EditGroundedEncode"}


class LiveProbeError(RuntimeError):
    pass


def _get_json(base: str, path: str) -> dict[str, Any]:
    request = urllib.request.Request(base.rstrip("/") + path, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise LiveProbeError(f"{path}: {type(exc).__name__}: {exc}") from exc
    if not isinstance(payload, dict):
        raise LiveProbeError(f"{path}: response is not a JSON object")
    return payload


def _git_revision(path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=path, capture_output=True, text=True, timeout=15, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _input_contract(spec: dict[str, Any], name: str) -> Any:
    inputs = spec.get("input", {})
    for section in ("required", "optional"):
        values = inputs.get(section, {})
        if name in values:
            return values[name]
    return None


def _combo_choices(contract: Any) -> list[Any] | None:
    if not isinstance(contract, list) or not contract:
        return None
    first = contract[0]
    return first if isinstance(first, list) else None


def _validate_api_workflow(root: Path, workflow_id: str, object_info: dict[str, Any]) -> dict[str, Any]:
    path = root / WORKFLOW_PATHS[workflow_id]
    if not path.is_file():
        return {"workflow_id": workflow_id, "status": "BLOCKED", "issues": [f"missing workflow: {path}"]}
    try:
        workflow = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"workflow_id": workflow_id, "status": "BLOCKED", "issues": [f"invalid workflow: {type(exc).__name__}"]}

    issues: list[str] = []
    checked_nodes: list[dict[str, Any]] = []
    for node_id, node in workflow.items():
        if node_id.startswith("_"):
            continue
        if not isinstance(node, dict):
            issues.append(f"node {node_id} is not an object")
            continue
        class_type = node.get("class_type")
        if not isinstance(class_type, str):
            issues.append(f"node {node_id} has no class_type")
            continue
        if any(token in class_type.casefold() for token in FORBIDDEN_TOKENS):
            issues.append(f"forbidden face replacement class: {class_type}")
        spec = object_info.get(class_type)
        if not isinstance(spec, dict):
            issues.append(f"node {node_id} {class_type} is absent from live /object_info")
            continue
        inputs = node.get("inputs", {})
        declared = set(spec.get("input", {}).get("required", {})) | set(spec.get("input", {}).get("optional", {}))
        unknown = sorted(set(inputs) - declared)
        if unknown:
            issues.append(f"node {node_id} {class_type} has unknown live inputs: {unknown}")
        invalid_choices: list[str] = []
        for name, value in inputs.items():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], (str, int)) and isinstance(value[1], int):
                continue
            choices = _combo_choices(_input_contract(spec, name))
            if choices and value not in choices:
                invalid_choices.append(f"{name}={value!r}")
        if invalid_choices:
            issues.append(f"node {node_id} {class_type} has invalid live choices: {invalid_choices}")
        checked_nodes.append({"node_id": node_id, "class_type": class_type, "status": "PASS" if not unknown and not invalid_choices else "BLOCKED", "live_input_names": sorted(declared), "workflow_input_names": sorted(inputs)})

    metadata = workflow.get("_meta", {})
    expected_human = bool(metadata.get("human_workflow"))
    if metadata.get("human_workflow") is not expected_human:
        issues.append("workflow metadata human_workflow does not match profile")
    workflow_kind = metadata.get("workflow_kind")
    prompt_class = "HOI4RandomPortraitPrompt" if workflow_kind == "random_text_to_image" else "HOI4AutopromptClient"
    if expected_human and workflow_kind != "portrait_preparation" and prompt_class not in {item.get("class_type") for item in checked_nodes}:
        issues.append("human workflow is missing the autoprompter node")
    if expected_human and REQUIRED_HUMAN_PREVIEW_NODE not in {item.get("class_type") for item in checked_nodes}:
        issues.append("human workflow is missing its PreviewImage inspection nodes")
    if not expected_human and any(item.get("class_type") == "HOI4AutopromptClient" for item in checked_nodes):
        issues.append("agent workflow contains an autoprompter node")
    return {"workflow_id": workflow_id, "path": str(path.relative_to(root)), "status": "PASS" if not issues else "BLOCKED", "issues": issues, "checked_nodes": checked_nodes, "prompt_source": metadata.get("prompt_source"), "human_workflow": metadata.get("human_workflow")}


def verify(root: Path, base: str, profile: str | None = None) -> dict[str, Any]:
    checked_at = datetime.now(timezone.utc).isoformat()
    system_stats = _get_json(base, "/system_stats")
    object_info = _get_json(base, "/object_info")
    system = system_stats.get("system", {})
    revision = _git_revision(root / "comfyui")
    expected_revision = "2a610155821d670a2d8047e654e5fce96b790eb5"

    workflow_ids = [profile] if profile else list(WORKFLOW_PATHS)
    identity_graph_required = any(workflow_id not in {
        "hoi4_portraits_no_input_local_nvidia_16gb",
        "hoi4_portraits_no_input_full_power_gpu",
        "hoi4_portraits_agent_no_input_local_nvidia_16gb",
        "hoi4_portraits_agent_no_input_full_power_gpu",
        "hoi4_portraits_prepare_portrait_for_hoi4",
        "hoi4_portraits_prepare_portrait_basic",
    } for workflow_id in workflow_ids)
    required_nodes = sorted(REQUIRED_CORE_NODES | ({*REQUIRED_KREA_NODES} if identity_graph_required else set()) | {REQUIRED_HUMAN_PREVIEW_NODE})
    node_presence = {name: name in object_info for name in required_nodes}
    clip_contract = object_info.get("CLIPLoader", {}).get("input", {}).get("required", {}).get("type", [])
    clip_choices = _combo_choices(clip_contract) or []
    krea_loader_schema = "krea2" in clip_choices
    patch = object_info.get("Krea2EditModelPatch", {})
    grounded = object_info.get("Krea2EditGroundedEncode", {})
    patch_optional = set(patch.get("input", {}).get("optional", {}))
    grounded_optional = set(grounded.get("input", {}).get("optional", {}))
    argv = system.get("argv", [])
    loopback_binding = isinstance(argv, list) and "--listen" in argv and len(argv) > argv.index("--listen") + 1 and argv[argv.index("--listen") + 1] == "127.0.0.1"
    schema_checks = {
        "loopback_binding": loopback_binding,
        "pinned_core_revision": revision == expected_revision,
        "core_nodes_present": all(node_presence[name] for name in sorted(REQUIRED_CORE_NODES)),
        "preview_node_present": node_presence[REQUIRED_HUMAN_PREVIEW_NODE],
        "krea_nodes_present": all(node_presence[name] for name in sorted(REQUIRED_KREA_NODES)) if identity_graph_required else True,
        "cliploader_krea2_choice": krea_loader_schema,
        "krea_patch_fit_contract": ({"model", "source_latent"} <= set(patch.get("input", {}).get("required", {})) and {"vae", "source_image", "fit_mode"} <= patch_optional) if identity_graph_required else True,
        "krea_grounded_encode_contract": ({"clip", "prompt"} <= set(grounded.get("input", {}).get("required", {})) and {"image", "grounding_px"} <= grounded_optional) if identity_graph_required else True,
    }
    workflow_checks = [_validate_api_workflow(root, workflow_id, object_info) for workflow_id in workflow_ids]
    schema_pass = all(schema_checks.values()) and all(item["status"] == "PASS" for item in workflow_checks)

    fixture_present = any((root / "fixtures").rglob("*") if (root / "fixtures").is_dir() else [])
    background_registry = root / "config" / "background_registry.json"
    background_resolved = False
    if background_registry.is_file():
        try:
            registry = json.loads(background_registry.read_text(encoding="utf-8"))
            background_resolved = registry.get("registry_status") in {
                "RESOLVED",
                "RESOLVED_LOCAL_GAME_COPY",
            } and any(
                item.get("status") in {"APPROVED", "APPROVED_LOCAL_COPY_REQUIRED"}
                for item in registry.get("backgrounds", [])
            )
        except json.JSONDecodeError:
            background_resolved = False
    execution = {
        "status": "BLOCKED_NO_APPROVED_SOURCE_FIXTURE_OR_BACKGROUND" if not fixture_present or not background_resolved else "NOT_RUN_CALIBRATION_REQUIRED",
        "attempted": False,
        "fixture_present": fixture_present,
        "background_resolved": background_resolved,
        "eight_step_turbo_execution": "NOT_RUN",
        "model_loading": "NOT_RUN",
        "reason": "A live schema check cannot substitute for a source-specific execution and independent audit.",
    }
    return {
        "schema_version": "1.0.0",
        "checked_at": checked_at,
        "status": "PASS_SCHEMA_ONLY_EXECUTION_BLOCKED" if schema_pass else "BLOCKED_LIVE_SCHEMA",
        "server": {"base_url": base, "raw_comfy_binding": "loopback_only", "system_stats": system_stats},
        "comfyui": {"expected_revision": expected_revision, "actual_revision": revision, "version": system.get("comfyui_version"), "python_version": system.get("python_version"), "pytorch_version": system.get("pytorch_version")},
        "node_presence": node_presence,
        "schema_checks": schema_checks,
        "cliploader_type_choices": clip_choices,
        "workflows": workflow_checks,
        "execution": execution,
        "policy": "Live registry/schema PASS permits the pinned Krea graph to be used for qualification only; production generation remains fail-closed until source, background, calibrated thresholds, and independent audit gates pass.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify live pinned ComfyUI/Krea schema compatibility on loopback.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--base-url", default="http://127.0.0.1:8188")
    parser.add_argument("--profile", choices=tuple(WORKFLOW_PATHS), action="append")
    args = parser.parse_args(argv)
    root = project_root(args.root)
    try:
        report = verify(root, args.base_url, args.profile[0] if args.profile and len(args.profile) == 1 else None)
    except LiveProbeError as exc:
        report = {"schema_version": "1.0.0", "checked_at": datetime.now(timezone.utc).isoformat(), "status": "BLOCKED_LIVE_SCHEMA", "error": str(exc), "policy": "No Krea execution is permitted without live schema evidence."}
    output_path = root / ".runtime" / "reports" / "live_comfy_compatibility.json"
    atomic_json_write(output_path, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("status") == "PASS_SCHEMA_ONLY_EXECUTION_BLOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
