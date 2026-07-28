from __future__ import annotations

from typing import Any, Iterable

from .audit import audit_is_promotion_pass
from .constants import HARD_AUDIT_GATES


def _metric(audit: dict[str, Any], name: str, default: float = float("-inf")) -> float:
    value = audit.get("metrics", {}).get(name, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def select_identity_first(audits: Iterable[dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    records = list(audits)
    rejected: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    for audit in records:
        if audit_is_promotion_pass(audit):
            eligible.append(audit)
        else:
            rejected.append({"candidate_id": audit.get("candidate_id"), "reason": audit.get("rejection_reasons", []), "verdict": audit.get("verdict")})
    eligible.sort(key=lambda item: (
        _metric(item, "worst_identity_margin"),
        _metric(item, "face_embedding_margin"),
        _metric(item, "landmark_margin"),
        _metric(item, "accessory_score"),
        _metric(item, "mask_score"),
        _metric(item, "style_score"),
        _metric(item, "native_readability"),
    ), reverse=True)
    selected = eligible[0] if eligible else None
    report = {
        "selection_policy": [
            "discard every candidate with any FAIL or UNCERTAIN hard gate",
            "rank by worst identity margin first",
            "then embedding and geometry margins",
            "then accessories and mask",
            "then style and final-size readability",
        ],
        "selected_candidate": selected.get("candidate_id") if selected else None,
        "eligible_count": len(eligible),
        "rejected": rejected,
        "identity_first": True,
        "hard_gates": HARD_AUDIT_GATES,
    }
    return selected, report
