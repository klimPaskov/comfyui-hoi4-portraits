"""Read-only, independent candidate audit implementation.

The auditor computes the measurable image/provenance signals available in the
private job root and returns UNCERTAIN whenever a calibrated model or threshold
is unavailable.  It never ranks candidates or edits candidate files.
"""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any, Iterable

from .audit import make_audit_record, write_audit
from .constants import CALIBRATED_THRESHOLD_STATUSES, HARD_AUDIT_GATES
from .util import is_sha256, project_root, relative_safe_path, sha256_file


def _load_thresholds(root: Path) -> tuple[dict[str, Any], list[str]]:
    path = root / "config" / "identity_thresholds.json"
    if not path.is_file():
        return {}, ["calibrated identity thresholds file is missing"]
    try:
        thresholds = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [f"thresholds are unreadable: {type(exc).__name__}"]
    issues: list[str] = []
    if thresholds.get("status") not in CALIBRATED_THRESHOLD_STATUSES or str(thresholds.get("thresholds_id", "")).startswith("UNSET"):
        issues.append("thresholds are not approved")
    required_values = (
        ("face_embedding", "minimum_similarity"),
        ("landmarks", "max_normalized_error"),
        ("pose", "max_yaw_delta_degrees"),
        ("pose", "max_pitch_delta_degrees"),
        ("pose", "max_roll_delta_degrees"),
        ("expression", "max_distance"),
        ("asymmetry", "max_change"),
        ("hair_and_accessories", "required_attribute_agreement"),
        ("mask", "maximum_boundary_leakage_ratio"),
        ("style", "minimum_score"),
    )
    for section, key in required_values:
        if thresholds.get(section, {}).get(key) is None:
            issues.append(f"threshold {section}.{key} is null")
    return thresholds, issues


def _read_image(path: Path) -> Any:
    from PIL import Image  # type: ignore

    with Image.open(path) as image:
        return image.convert("RGBA")


def _face_signals(root: Path, source: Path, candidate: Path) -> tuple[dict[str, Any], str | None]:
    """Compute SFace/YuNet signals when the pinned OpenCV models are usable."""

    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError as exc:
        return {"backend": "opencv", "status": "UNCERTAIN", "error_type": type(exc).__name__}, "OpenCV is unavailable for independent face audit"
    lock_path = root / "dependencies" / "preprocessing_lock.json"
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        entries = {item.get("name"): item for item in lock.get("dependencies", [])}
        yunet = root / str(entries["YuNet"]["destination_path"])
        sface = root / str(entries["SFace"]["destination_path"])
        if not yunet.is_file() or not sface.is_file():
            raise FileNotFoundError("pinned YuNet or SFace model is missing")
        source_image = cv2.cvtColor(np.asarray(_read_image(source)), cv2.COLOR_RGBA2BGR)
        candidate_image = cv2.cvtColor(np.asarray(_read_image(candidate)), cv2.COLOR_RGBA2BGR)
        detector = cv2.FaceDetectorYN.create(str(yunet), "", (320, 320), 0.6, 0.3, 5000)

        def detect(image: Any) -> Any:
            detector.setInputSize((int(image.shape[1]), int(image.shape[0])))
            _, faces = detector.detect(image)
            return faces if faces is not None else []

        source_faces = detect(source_image)
        candidate_faces = detect(candidate_image)
        metrics: dict[str, Any] = {"backend": "opencv_yunet_sface", "source_face_count": int(len(source_faces)), "candidate_face_count": int(len(candidate_faces))}
        if len(source_faces) != 1 or len(candidate_faces) != 1:
            return metrics, "independent face association requires exactly one source and one candidate face"
        recognizer = cv2.FaceRecognizerSF.create(str(sface), "")
        source_aligned = recognizer.alignCrop(source_image, source_faces[0])
        candidate_aligned = recognizer.alignCrop(candidate_image, candidate_faces[0])
        source_feature = recognizer.feature(source_aligned)
        candidate_feature = recognizer.feature(candidate_aligned)
        similarity = float(recognizer.match(source_feature, candidate_feature, cv2.FaceRecognizerSF_FR_COSINE))
        metrics.update({"face_embedding_similarity": similarity, "source_face_box": json.dumps([float(value) for value in source_faces[0][:4]], separators=(",", ":")), "candidate_face_box": json.dumps([float(value) for value in candidate_faces[0][:4]], separators=(",", ":"))})
        return metrics, None
    except Exception as exc:  # model/API differences are an audit uncertainty, never a pass
        return {"backend": "opencv_yunet_sface", "status": "UNCERTAIN", "error_type": type(exc).__name__}, f"face audit backend failed closed: {type(exc).__name__}"


def _path_evidence(root: Path, paths: dict[str, Path]) -> tuple[dict[str, str], bool, list[str]]:
    evidence: dict[str, str] = {}
    issues: list[str] = []
    for name, path in paths.items():
        if not path.is_file():
            issues.append(f"missing evidence file: {name}")
            evidence[name] = str(path)
            continue
        try:
            evidence[name] = str(path.relative_to(root))
        except ValueError:
            issues.append(f"evidence path is outside the private root: {name}")
            evidence[name] = str(path)
    return evidence, not issues, issues


def audit_candidate(
    *,
    job_root: str | Path,
    candidate_id: str,
    source_master: str | Path,
    processed_reference: str | Path,
    candidate: str | Path,
    mask: str | Path,
    manifest: str | Path,
    producer_process_id: str,
    root: str | Path | None = None,
    auditor_process_id: str | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    project = project_root(root)
    private_root = Path(job_root).resolve()
    paths = {
        "source_master": Path(source_master).resolve(),
        "processed_reference": Path(processed_reference).resolve(),
        "candidate": Path(candidate).resolve(),
        "native_comparison": private_root / "comparisons" / f"{candidate_id}_native.png",
        "enlarged_comparison": private_root / "comparisons" / f"{candidate_id}_4x.png",
        "mask_comparison": Path(mask).resolve(),
        "manifest": Path(manifest).resolve(),
    }
    evidence, files_present, path_issues = _path_evidence(private_root, paths)
    thresholds, threshold_issues = _load_thresholds(project)
    reasons = path_issues + threshold_issues
    metrics: dict[str, Any] = {
        "audit_mode": "production",
        "output_authority": "read_only",
        "candidate_selection_access": False,
        "independent_recompute": False,
        "evidence_verified": files_present,
        "thresholds_verified": not threshold_issues,
        "source_fixture_verified": files_present,
        "provenance_verified": False,
        "gate_recompute_count": 0,
        "producer_process_id": producer_process_id,
        "auditor_process_id": auditor_process_id or f"auditor-{os.getpid()}",
    }
    gates = {name: "UNCERTAIN" for name in HARD_AUDIT_GATES}

    if files_present:
        try:
            image_records = {}
            for name, path in paths.items():
                image_records[f"{name}_sha256"] = sha256_file(path)
            metrics.update(image_records)
            source_image = _read_image(paths["source_master"])
            candidate_image = _read_image(paths["candidate"])
            mask_image = _read_image(paths["mask_comparison"])
            metrics.update({"source_dimensions": f"{source_image.width}x{source_image.height}", "candidate_dimensions": f"{candidate_image.width}x{candidate_image.height}", "mask_dimensions": f"{mask_image.width}x{mask_image.height}", "candidate_alpha_opaque": candidate_image.getchannel("A").getextrema() == (255, 255)})
            if candidate_image.width * 35 != candidate_image.height * 26:
                gates["facial_proportions"] = "FAIL"
                reasons.append("candidate canvas is not the locked 26:35 portrait ratio")
            else:
                gates["facial_proportions"] = "UNCERTAIN"
            if candidate_image.getchannel("A").getextrema() != (255, 255):
                gates["foreground_integrity"] = "FAIL"
                reasons.append("candidate contains transparency")
        except Exception as exc:
            reasons.append(f"image evidence could not be decoded: {type(exc).__name__}")
    if files_present:
        face_metrics, face_issue = _face_signals(project, paths["source_master"], paths["candidate"])
        metrics.update(face_metrics)
        if face_issue:
            reasons.append(face_issue)
        elif not threshold_issues:
            similarity = face_metrics.get("face_embedding_similarity")
            minimum = thresholds.get("face_embedding", {}).get("minimum_similarity")
            if isinstance(similarity, (int, float)) and isinstance(minimum, (int, float)):
                gates["face_embedding"] = "PASS" if similarity >= minimum else "FAIL"
                if gates["face_embedding"] == "FAIL":
                    reasons.append("face embedding similarity is below the calibrated threshold")
    if files_present and not threshold_issues:
        # The remaining gates require the locked landmark/expression/accessory/
        # style reference implementations.  They are intentionally not
        # approximated from pixel heuristics.
        reasons.append("landmark, pose, expression, hair/accessory, mask-boundary, and style auditors are not qualified")
    if files_present and paths["manifest"].is_file():
        metrics["provenance_verified"] = True
        gates["provenance"] = "PASS" if not threshold_issues else "UNCERTAIN"
    verdict = "FAIL" if any(value == "FAIL" for value in gates.values()) else ("PASS" if all(value == "PASS" for value in gates.values()) and not reasons else "UNCERTAIN")
    metrics["independent_recompute"] = verdict in {"PASS", "FAIL"} and metrics["auditor_process_id"] != producer_process_id
    metrics["gate_recompute_count"] = sum(value != "UNCERTAIN" for value in gates.values())
    audit = make_audit_record(job_id=private_root.name, candidate_id=candidate_id, evidence=evidence, verdict=verdict, gates=gates, metrics=metrics, reasons=reasons, producer_process_id=producer_process_id, auditor_process_id=auditor_process_id, thresholds_id=str(thresholds.get("thresholds_id", "UNSET_BLOCK_EXECUTION")))
    if output_path is not None:
        write_audit(output_path, audit, project)
    return audit


def audit_candidates_randomized(candidates: Iterable[dict[str, Any]], *, job_root: str | Path, producer_process_id: str, root: str | Path | None = None, order_output: str | Path | None = None) -> list[dict[str, Any]]:
    """Audit candidates in randomized order without exposing producer ranking."""

    shuffled = list(candidates)
    secrets.SystemRandom().shuffle(shuffled)
    if order_output is not None:
        path = Path(order_output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"schema_version": "1.0.0", "candidate_order": [item.get("candidate_id") for item in shuffled], "producer_preferred_candidate_received": False, "candidate_selection_access": False}, indent=2) + "\n", encoding="utf-8")
    return [audit_candidate(producer_process_id=producer_process_id, root=root, job_root=job_root, **item) for item in shuffled]
