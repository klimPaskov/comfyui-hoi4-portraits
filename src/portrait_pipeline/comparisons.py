from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .experiments import build_matrix
from .preflight import collect_preflight
from .util import atomic_json_write, project_root


COMPARISON_SCHEMA_VERSION = "1.0.0"


def _diagnostic_candidates(root: Path) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for path in sorted((root / ".runtime" / "reports").glob("local_*_execution_*.json")):
        try:
            evidence = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(evidence, dict) or not str(evidence.get("status", "")).startswith("QUALIFIED_CPU_FALLBACK"):
            continue
        candidate = evidence.get("candidate")
        if not isinstance(candidate, dict) or not isinstance(candidate.get("sha256"), str):
            continue
        audit = evidence.get("independent_audit") if isinstance(evidence.get("independent_audit"), dict) else {}
        candidates.append({
            "execution_profile": evidence.get("execution_profile"),
            "job_id": evidence.get("job_id"),
            "candidate_id": candidate.get("candidate_id"),
            "path": candidate.get("path"),
            "sha256": candidate.get("sha256"),
            "dimensions": candidate.get("dimensions"),
            "audit_verdict": audit.get("verdict", "UNCERTAIN"),
            "production_eligible": False,
        })
    return candidates


def build_comparison_report(root: str | Path | None = None) -> dict[str, Any]:
    root_path = project_root(root)
    preflight = collect_preflight(root_path)
    gate_statuses = {gate["name"]: gate["status"] for gate in preflight["gates"]}
    diagnostic_candidates = _diagnostic_candidates(root_path)
    has_diagnostic_candidates = bool(diagnostic_candidates)
    return {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "comparison_id": "identity-style-comparison-2026-07-26.1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "BLOCKED_DIAGNOSTIC_CANDIDATES_NOT_PRODUCTION_AUTHORIZED" if has_diagnostic_candidates else "BLOCKED_NO_REAL_CANDIDATES",
        "reason": "Diagnostic candidates were observed, but no comparison ranking or production winner is produced until calibrated thresholds and independent all-PASS audits authorize them." if has_diagnostic_candidates else "No comparison sheet or candidate ranking is produced without a production-authorized source fixture, live generation runtime, calibrated thresholds, and independent audit evidence.",
        "matrix_id": build_matrix()["matrix_id"],
        "selection_policy": {
            "identity_first": True,
            "selection_order": build_matrix()["selection_order"],
            "face_swap_permitted": False,
            "style_ranking_before_identity": False,
        },
        "candidate_counts": {"observed": len(diagnostic_candidates), "eligible_for_selection": 0, "required_for_matrix": "profile_budgeted"},
        "diagnostic_candidates": diagnostic_candidates,
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
        "No production comparison ranking was generated. Diagnostic candidates, when present, remain quarantined while the hard gates are blocked.",
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
    output_dir = root_path / ".runtime" / "reports" / "comparisons"
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
