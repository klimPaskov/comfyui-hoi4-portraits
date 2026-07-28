from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .constants import ExecutionProfile
from .util import atomic_json_write, project_root


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
            ExecutionProfile.AGENT_REMOTE_RUNPOD.value: {"candidate_budget": 6, "retry_limit": 2, "canvas": [1196, 1610]},
        },
        "status": "PLANNED_BLOCKED_UNTIL_APPROVED_FIXTURE_BACKGROUND_THRESHOLDS",
        "execution_status": "NOT_RUN",
        "required_eight_step_turbo_status": "NOT_RUN",
        "required_prerequisites": [
            "legally usable source fixture with immutable provenance",
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


def main(root: str | Path | None = None) -> int:
    root_path = project_root(root)
    output = root_path / "experiments" / "identity_style_matrix.json"
    atomic_json_write(output, build_matrix())
    print(json.dumps(build_matrix(), indent=2))
    return 0
