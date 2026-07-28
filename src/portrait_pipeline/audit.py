from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .constants import HARD_AUDIT_GATES
from .contracts import validate_audit
from .util import atomic_json_write, canonical_hash, sha256_file


def audit_is_promotion_pass(audit: dict[str, Any], *, allow_synthetic_test: bool = False) -> bool:
    """Return true only for an auditor record that can authorize promotion.

    A verdict and a set of PASS labels are not enough: the producer must not be
    able to self-approve, and the auditor must prove that it independently
    recomputed every hard gate from verified evidence and calibrated thresholds.
    The explicit synthetic escape hatch is used only by the in-process DDS
    round-trip test; the production CLI and controller never enable it.
    """

    if audit.get("verdict") != "PASS":
        return False
    if audit.get("auditor", {}).get("independent_from_producer") is not True:
        return False
    if any(audit.get("hard_gates", {}).get(name) != "PASS" for name in HARD_AUDIT_GATES):
        return False
    metrics = audit.get("metrics", {})
    if not isinstance(metrics, dict):
        return False
    thresholds_id = str(audit.get("thresholds_id", ""))
    if allow_synthetic_test and metrics.get("audit_mode") == "synthetic_test" and thresholds_id == "synthetic-acceptance-only":
        return True
    required = {
        "audit_mode": "production",
        "output_authority": "read_only",
        "candidate_selection_access": False,
        "independent_recompute": True,
        "evidence_verified": True,
        "thresholds_verified": True,
        "source_fixture_verified": True,
        "provenance_verified": True,
        "gate_recompute_count": len(HARD_AUDIT_GATES),
    }
    if any(metrics.get(key) != value for key, value in required.items()):
        return False
    if not thresholds_id or thresholds_id.startswith("UNSET") or thresholds_id.startswith("synthetic"):
        return False
    auditor = audit.get("auditor", {})
    auditor_process_id = auditor.get("process_id")
    producer_process_id = metrics.get("producer_process_id")
    if not isinstance(auditor_process_id, str) or not auditor_process_id:
        return False
    if not isinstance(producer_process_id, str) or not producer_process_id or producer_process_id == auditor_process_id:
        return False
    if metrics.get("auditor_process_id") != auditor_process_id:
        return False
    return True


def audit_is_pass(audit: dict[str, Any]) -> bool:
    """Compatibility alias for the production promotion predicate."""

    return audit_is_promotion_pass(audit)


def audit_is_uncertain_or_failed(audit: dict[str, Any]) -> bool:
    return not audit_is_pass(audit)


def make_audit_record(
    *,
    job_id: str,
    candidate_id: str,
    evidence: dict[str, str],
    verdict: str = "UNCERTAIN",
    gates: dict[str, str] | None = None,
    metrics: dict[str, Any] | None = None,
    reasons: list[str] | None = None,
    auditor_id: str = "portrait_identity_auditor",
    producer_process_id: str = "producer-unknown",
    auditor_process_id: str | None = None,
    thresholds_id: str = "UNSET_BLOCK_EXECUTION",
) -> dict[str, Any]:
    gate_values = {name: "UNCERTAIN" for name in HARD_AUDIT_GATES}
    if gates:
        gate_values.update(gates)
    actual_auditor_process_id = auditor_process_id or f"auditor-{os.getpid()}"
    base_metrics = {
        "audit_mode": "blocked",
        "output_authority": "read_only",
        "candidate_selection_access": False,
        "independent_recompute": False,
        "evidence_verified": False,
        "thresholds_verified": False,
        "source_fixture_verified": False,
        "provenance_verified": False,
        "gate_recompute_count": 0,
        "producer_process_id": producer_process_id,
        "auditor_process_id": actual_auditor_process_id,
    }
    base_metrics.update(metrics or {})
    audit = {
        "schema_version": "1.0.0",
        "job_id": job_id,
        "candidate_id": candidate_id,
        "auditor": {
            "auditor_id": auditor_id,
            "process_id": actual_auditor_process_id,
            "independent_from_producer": actual_auditor_process_id != producer_process_id,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        },
        "thresholds_id": thresholds_id,
        "metrics": base_metrics,
        "hard_gates": gate_values,
        "rejection_reasons": reasons or [],
        "verdict": verdict,
        "evidence": {
            "source_master": evidence.get("source_master", "evidence/source/master.png"),
            "processed_reference": evidence.get("processed_reference", "evidence/reference/processed.png"),
            "candidate": evidence.get("candidate", f"candidates/{candidate_id}.png"),
            "native_comparison": evidence.get("native_comparison", f"comparisons/{candidate_id}_native.png"),
            "enlarged_comparison": evidence.get("enlarged_comparison", f"comparisons/{candidate_id}_4x.png"),
            "mask_comparison": evidence.get("mask_comparison", f"audit/{candidate_id}_mask.png"),
            "manifest": evidence.get("manifest", "manifest.json"),
        },
    }
    return audit


def validate_audit_record(audit: dict[str, Any], root: str | Path | None = None) -> None:
    issues = validate_audit(audit, root)
    if issues:
        raise ValueError("invalid audit: " + "; ".join(f"{issue.path}: {issue.message}" for issue in issues))


def write_audit(path: str | Path, audit: dict[str, Any], root: str | Path | None = None) -> None:
    validate_audit_record(audit, root)
    atomic_json_write(path, audit)


def load_audits(paths: Iterable[str | Path], root: str | Path | None = None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        audit = json.loads(Path(path).read_text(encoding="utf-8"))
        validate_audit_record(audit, root)
        records.append(audit)
    return records


def independent_audit_blocked(job_id: str, candidate_id: str, evidence_root: str = "evidence") -> dict[str, Any]:
    evidence = {
        "source_master": f"{evidence_root}/source/master.png",
        "processed_reference": f"{evidence_root}/reference/processed.png",
        "candidate": f"candidates/{candidate_id}.png",
        "native_comparison": f"comparisons/{candidate_id}_native.png",
        "enlarged_comparison": f"comparisons/{candidate_id}_4x.png",
        "mask_comparison": f"audit/{candidate_id}_mask.png",
        "manifest": "manifest.json",
    }
    return make_audit_record(
        job_id=job_id,
        candidate_id=candidate_id,
        evidence=evidence,
        verdict="UNCERTAIN",
        reasons=["runtime, calibration thresholds, and candidate evidence are unavailable"],
        auditor_id="portrait_identity_auditor",
        producer_process_id=f"blocked-producer-{job_id}",
        auditor_process_id=f"blocked-auditor-{job_id}",
    )


def audit_digest(audit: dict[str, Any]) -> str:
    return canonical_hash(audit)
