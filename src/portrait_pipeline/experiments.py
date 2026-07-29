from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .constants import ExecutionProfile
from .preflight import collect_preflight
from .util import atomic_json_write, canonical_hash, project_root


EXPERIMENT_AXES = {
    "identity_adapter": ["absent", "full_v1_2", "r128", "r64"],
    "style_lora": ["absent", "low", "medium", "high"],
    "adapter_order": ["identity_then_style", "style_then_identity"],
    "pass_structure": ["single_pass", "two_pass"],
    "first_pass_reference": ["processed_source", "approved_composite"],
    "mask_route": ["no_generation_mask", "person_mask", "face_protection_or_subject_mask"],
    "ref_boost": ["lower", "baseline", "higher"],
    "grounding_px": [512, 768, 1024],
    "steps": [8, 10, 12],
    "cfg": [1.0],
    "sampler": ["euler_simple", "qualified_alternative"],
    "style_pass_denoise": [0.10, 0.20, 0.30],
    "working_resolution": ["local_mac_canvas", "full_power_canvas"],
}


def build_matrix() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "matrix_id": "krea2_identity_style_factorial_v1",
        "selection_order": ["identity_gates", "geometry_gates", "accessories", "mask", "style", "runtime", "reproducibility"],
        "staged_design": True,
        "axes": EXPERIMENT_AXES,
        "profiles": {
            ExecutionProfile.HUMAN_LOCAL_MAC_16GB.value: {"candidate_budget": 2, "retry_limit": 2, "canvas": [832, 1120]},
            ExecutionProfile.HUMAN_FULL_POWER_GPU.value: {"candidate_budget": 6, "retry_limit": 2, "canvas": [1196, 1610]},
            ExecutionProfile.AGENT_LOCAL_MAC_16GB.value: {"candidate_budget": 2, "retry_limit": 2, "canvas": [832, 1120]},
            ExecutionProfile.AGENT_FULL_POWER_GPU.value: {"candidate_budget": 6, "retry_limit": 2, "canvas": [1196, 1610]},
            ExecutionProfile.AGENT_REMOTE_RUNPOD.value: {"candidate_budget": 6, "retry_limit": 2, "canvas": [1196, 1610]},
        },
        "status": "PLANNED_BLOCKED_UNTIL_APPROVED_FIXTURE_BACKGROUND_THRESHOLDS",
        "execution_status": "NOT_RUN",
        "required_eight_step_turbo_status": "NOT_RUN",
        "required_prerequisites": [
            "production-authorized source fixture with immutable provenance",
            "approved HOI4 background registry entry",
            "approved calibrated identity/style thresholds",
            "live model-loading and source-specific execution evidence",
        ],
        "selection_policy": {
            "identity_first": True,
            "style_ranking_before_identity": False,
            "face_swap_permitted": False,
        },
        "hard_rule": "eliminate identity failures before style ranking; no face swapping; no final output from an un-audited route",
    }


def build_execution_report(root: str | Path | None = None) -> dict[str, Any]:
    """Record a fail-closed matrix attempt without queuing generation."""

    root_path = project_root(root)
    matrix = build_matrix()
    profile_reports: dict[str, Any] = {}
    blockers: list[str] = []
    for profile in matrix["profiles"]:
        preflight = collect_preflight(root_path, profile=profile)
        statuses = {str(gate.get("name")): str(gate.get("status")) for gate in preflight.get("gates", [])}
        blocked_gates = [name for name, status in statuses.items() if status not in {"PASS", "APPROVED", "NOT_APPLICABLE", "DEFERRED_OUT_OF_SCOPE"}]
        profile_blockers = [str(item) for item in preflight.get("blockers", [])]
        profile_reports[profile] = {
            "status": "PASS" if preflight.get("status") == "PASS" else "BLOCKED",
            "preflight_status": preflight.get("status"),
            "blocked_gates": blocked_gates,
            "blockers": profile_blockers,
        }
        for item in profile_blockers:
            if item not in blockers:
                blockers.append(item)
    return {
        "schema_version": "1.0.0",
        "execution_id": "krea2-identity-style-factorial-v1-2026-07-29",
        "matrix_id": matrix["matrix_id"],
        "matrix_design_sha256": canonical_hash(matrix),
        "status": "PASS_READY_TO_RUN" if not blockers else "BLOCKED_PREREQUISITES",
        "execution_status": "READY_TO_RUN" if not blockers else "NOT_RUN_FAIL_CLOSED",
        "required_eight_step_turbo_status": "READY_TO_RUN" if not blockers else "NOT_RUN_PRODUCTION_BLOCKED",
        "profiles": profile_reports,
        "queued_jobs": 0,
        "candidate_count": 0,
        "selection_status": "NOT_RUN",
        "blocked_reasons": blockers,
        "selection_policy": matrix["selection_policy"],
        "policy": "No matrix candidate is queued until every mandatory preflight and independent-audit prerequisite passes. This report is not a generation result.",
    }


def write_execution_report(root: str | Path | None = None) -> dict[str, Any]:
    root_path = project_root(root)
    report = build_execution_report(root_path)
    atomic_json_write(root_path / "docs" / "preflight" / "identity_style_matrix_execution_2026-07-29.json", report)
    return report


def main(root: str | Path | None = None) -> int:
    root_path = project_root(root)
    output = root_path / "experiments" / "identity_style_matrix.json"
    matrix = build_matrix()
    execution = write_execution_report(root_path)
    matrix["execution_status"] = execution["execution_status"]
    matrix["required_eight_step_turbo_status"] = execution["required_eight_step_turbo_status"]
    atomic_json_write(output, matrix)
    print(json.dumps({"matrix": matrix, "execution": execution}, indent=2))
    return 0
