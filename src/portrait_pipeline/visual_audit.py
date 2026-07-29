"""Fail-closed consumption of private visual-audit evidence.

The visual classifier or fixed VLM rubric runs outside the producer and writes
only this private, hash-bound evidence record.  This module never creates a
visual score and never approves a threshold registry; it verifies the evidence
and maps it to hard gates only after the production threshold record is already
approved.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import validate_schema
from .util import is_sha256, relative_safe_path, sha256_file


VISUAL_AUDIT_RELATIVE_PATH = "evidence/audit/visual_audit.json"
VISUAL_AUDIT_GATES = ("hairline", "facial_hair", "accessories", "style")


def _blocked_metrics(path: Path) -> dict[str, Any]:
    return {
        "visual_audit_status": "UNCERTAIN",
        "visual_audit_path": str(path),
    }


def evaluate_visual_audit(
    *,
    private_root: str | Path,
    source_path: str | Path,
    candidate_path: str | Path,
    producer_process_id: str,
    thresholds: dict[str, Any],
    threshold_issues: list[str],
) -> tuple[dict[str, Any], dict[str, str], list[str]]:
    """Verify and compare private visual evidence without creating approval."""

    root = Path(private_root).resolve()
    source = Path(source_path).resolve()
    candidate = Path(candidate_path).resolve()
    evidence_path = relative_safe_path(root, VISUAL_AUDIT_RELATIVE_PATH)
    metrics = _blocked_metrics(evidence_path)
    gates = {name: "UNCERTAIN" for name in VISUAL_AUDIT_GATES}
    reasons: list[str] = []

    if not evidence_path.is_file():
        reasons.append("private visual audit evidence is missing")
        return metrics, gates, reasons
    try:
        record = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        reasons.append(f"private visual audit evidence is unreadable: {type(exc).__name__}")
        return metrics, gates, reasons

    issues = validate_schema(record, Path(__file__).resolve().parents[2] / "schemas/visual_audit_evidence.schema.json")
    if issues:
        reasons.append("private visual audit evidence does not satisfy its schema")
        metrics["visual_audit_schema_issues"] = json.dumps([issue.as_dict() for issue in issues], sort_keys=True, separators=(",", ":"))
        return metrics, gates, reasons

    try:
        source.relative_to(root)
        candidate.relative_to(root)
    except ValueError:
        reasons.append("visual audit source or candidate is outside the private job root")
        return metrics, gates, reasons
    if not source.is_file() or not candidate.is_file():
        reasons.append("visual audit source or candidate file is missing")
        return metrics, gates, reasons

    auditor = record["auditor"]
    model = record["model"]
    reference_set = record["reference_set"]
    scores = record["scores"]
    metrics.update({
        "visual_audit_status": record["status"],
        "visual_audit_process_id": auditor["process_id"],
        "visual_audit_model_name": model["name"],
        "visual_audit_model_revision": model["revision"],
        "visual_audit_model_sha256": model["artifact_sha256"],
        "visual_audit_reference_set_id": reference_set["id"],
        "visual_audit_reference_set_sha256": reference_set["manifest_sha256"],
        "visual_audit_source_sha256": record["source_sha256"],
        "visual_audit_candidate_sha256": record["candidate_sha256"],
        "visual_audit_scores": json.dumps(scores, sort_keys=True, separators=(",", ":")),
    })

    if not auditor["independent_from_producer"] or auditor["process_id"] == producer_process_id:
        reasons.append("visual audit process is not independent from the producer")
    if sha256_file(source) != record["source_sha256"]:
        reasons.append("visual audit source checksum does not match the immutable source evidence")
    if sha256_file(candidate) != record["candidate_sha256"]:
        reasons.append("visual audit candidate checksum does not match the candidate evidence")
    if not is_sha256(model["artifact_sha256"]) or not is_sha256(reference_set["manifest_sha256"]):
        reasons.append("visual audit model or reference-set checksum is not a valid SHA-256")

    expected_reference_set = thresholds.get("style", {}).get("reference_set_id")
    if isinstance(expected_reference_set, str) and expected_reference_set.startswith("UNSET"):
        reasons.append("visual audit reference-set comparison is withheld until a calibrated role-specific reference set is approved")
    elif reference_set["id"] != expected_reference_set:
        reasons.append("visual audit reference set does not match the calibrated threshold registry")

    if threshold_issues:
        reasons.append("visual audit gate comparison is withheld until all calibrated thresholds are approved")
    if reasons:
        return metrics, gates, reasons

    if record["status"] == "UNCERTAIN":
        reasons.append("visual classifier returned UNCERTAIN")
        return metrics, gates, reasons

    attribute_limit = thresholds["hair_and_accessories"]["required_attribute_agreement"]
    style_limit = thresholds["style"]["minimum_score"]
    if record["status"] == "FAIL":
        gates = {name: "FAIL" for name in VISUAL_AUDIT_GATES}
        reasons.append("visual classifier returned FAIL")
        return metrics, gates, reasons

    for name in ("hairline", "facial_hair", "accessories"):
        gates[name] = "PASS" if scores[name] >= attribute_limit else "FAIL"
        if gates[name] == "FAIL":
            reasons.append(f"visual audit score for {name} is below the calibrated attribute threshold")
    gates["style"] = "PASS" if scores["style"] >= style_limit else "FAIL"
    if gates["style"] == "FAIL":
        reasons.append("visual audit style score is below the calibrated HOI4 style threshold")
    return metrics, gates, reasons
