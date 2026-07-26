from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .experiments import build_matrix
from .preflight import collect_preflight
from .util import atomic_json_write, project_root


COMPARISON_SCHEMA_VERSION = "1.0.0"


def build_comparison_report(root: str | Path | None = None) -> dict[str, Any]:
    root_path = project_root(root)
    preflight = collect_preflight(root_path)
    gate_statuses = {gate["name"]: gate["status"] for gate in preflight["gates"]}
    return {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "comparison_id": "identity-style-comparison-2026-07-26.1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "BLOCKED_NO_REAL_CANDIDATES",
        "reason": "No comparison sheet or candidate ranking is produced without a legally usable source fixture, live runtime, calibrated thresholds, and independent audit evidence.",
        "matrix_id": build_matrix()["matrix_id"],
        "selection_policy": {
            "identity_first": True,
            "selection_order": build_matrix()["selection_order"],
            "face_swap_permitted": False,
            "style_ranking_before_identity": False,
        },
        "candidate_counts": {"observed": 0, "required_for_matrix": "profile_budgeted"},
        "comparison_artifacts": [],
        "metrics": {
            "identity_pass_rate": None,
            "geometry_pass_rate": None,
            "expression_pass_rate": None,
            "accessory_pass_rate": None,
            "mask_pass_rate": None,
            "style_pass_rate_among_identity_pass": None,
            "median_runtime_seconds": None,
            "tail_runtime_seconds": None,
            "peak_memory_bytes": None,
            "repeated_seed_variance": None,
        },
        "preflight": {
            "status": preflight["status"],
            "gate_statuses": gate_statuses,
            "blockers": preflight["blockers"],
        },
        "claims": {
            "identity_winner": None,
            "style_winner": None,
            "comparison_sheet": "NOT_CREATED",
            "final_png": "NOT_CREATED",
            "final_dds": "NOT_CREATED",
        },
    }


def render_comparison_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Identity and Style Comparison",
        "",
        f"- Status: **{report['status']}**",
        f"- Reason: {report['reason']}",
        f"- Matrix: `{report['matrix_id']}`",
        "",
        "No candidate comparison was generated. The absence of a sheet is intentional while the hard gates are blocked.",
        "",
        "## Required selection order",
        "",
        " → ".join(report["selection_policy"]["selection_order"]),
        "",
        "## Blockers",
        "",
    ]
    lines.extend(f"- {item}" for item in report["preflight"]["blockers"])
    lines.extend(["", "## Metrics", "", "All values remain `null` until real candidates and independent audits exist.", ""])
    return "\n".join(lines)


def write_comparison_report(root: str | Path | None = None) -> dict[str, Any]:
    root_path = project_root(root)
    report = build_comparison_report(root_path)
    output_dir = root_path / "docs" / "comparisons"
    output_dir.mkdir(parents=True, exist_ok=True)
    atomic_json_write(output_dir / "identity_style_comparison.json", report)
    (output_dir / "identity_style_comparison.md").write_text(render_comparison_markdown(report), encoding="utf-8")
    return report


def main(root: str | Path | None = None) -> int:
    report = write_comparison_report(root)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
