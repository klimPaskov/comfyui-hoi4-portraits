"""Read-only, independent candidate audit implementation.

The auditor computes the measurable image/provenance signals available in the
private job root and returns UNCERTAIN whenever a calibrated model or threshold
is unavailable.  It never ranks candidates or edits candidate files.
"""

from __future__ import annotations

import json
import math
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
    region_limits = thresholds.get("landmarks", {}).get("region_limits")
    if not isinstance(region_limits, dict):
        issues.append("threshold landmarks.region_limits is missing")
    else:
        for region in ("eyes", "nose", "mouth", "jaw"):
            if region_limits.get(region) is None:
                issues.append(f"threshold landmarks.region_limits.{region} is null")
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


def _landmark_signals(root: Path, source: Path, candidate: Path) -> tuple[dict[str, Any], str | None]:
    """Recompute geometry, pose, and expression signals with the pinned MediaPipe model."""

    try:
        import mediapipe as mp  # type: ignore
        import numpy as np  # type: ignore
    except ImportError as exc:
        return {"landmark_backend": "mediapipe", "landmark_status": "UNCERTAIN", "error_type": type(exc).__name__}, "MediaPipe is unavailable for the independent landmark audit"
    try:
        lock = json.loads((root / "dependencies" / "preprocessing_lock.json").read_text(encoding="utf-8"))
        entries = {item.get("name"): item for item in lock.get("dependencies", [])}
        entry = entries["MediaPipe Face Landmarker"]
        model_path = root / str(entry["destination_path"])
        if not model_path.is_file():
            raise FileNotFoundError("pinned MediaPipe Face Landmarker is missing")
        options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
            num_faces=2,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
        )
        with mp.tasks.vision.FaceLandmarker.create_from_options(options) as landmarker:
            def detect(path: Path) -> tuple[Any, dict[str, float], Any]:
                image = _read_image(path).convert("RGB")
                array = np.ascontiguousarray(np.asarray(image, dtype=np.uint8))
                result = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=array))
                faces = getattr(result, "face_landmarks", None) or []
                blendshape_sets = getattr(result, "face_blendshapes", None) or []
                matrices = getattr(result, "facial_transformation_matrixes", None) or []
                if len(faces) != 1:
                    raise ValueError(f"MediaPipe expected exactly one face, found {len(faces)}")
                points = np.asarray([[float(point.x), float(point.y), float(point.z)] for point in faces[0]], dtype=np.float64)
                left, top = points[:, :2].min(axis=0)
                right, bottom = points[:, :2].max(axis=0)
                width = max(1e-9, float(right - left))
                height = max(1e-9, float(bottom - top))
                normalized = points.copy()
                normalized[:, 0] = (normalized[:, 0] - left) / width
                normalized[:, 1] = (normalized[:, 1] - top) / height
                blendshapes: dict[str, float] = {}
                if blendshape_sets:
                    for category in blendshape_sets[0]:
                        name = getattr(category, "category_name", None)
                        if isinstance(name, str):
                            blendshapes[name] = float(getattr(category, "score", 0.0))
                matrix = np.asarray(matrices[0], dtype=np.float64) if matrices else None
                return normalized, blendshapes, matrix

            source_points, source_blendshapes, source_matrix = detect(source)
            candidate_points, candidate_blendshapes, candidate_matrix = detect(candidate)

        if source_points.shape != candidate_points.shape or source_points.shape[0] < 400:
            raise ValueError("MediaPipe landmark topology is incomplete or changed")
        delta = candidate_points[:, :2] - source_points[:, :2]
        per_point = np.linalg.norm(delta, axis=1)
        region_indices = {
            "eyes": [33, 133, 159, 145, 362, 263, 386, 374],
            "nose": [1, 2, 4, 5, 6, 98, 327, 168],
            "mouth": [61, 291, 13, 14, 78, 308],
            "jaw": [10, 152, 234, 454, 172, 397],
        }
        region_errors = {name: float(per_point[indices].mean()) for name, indices in region_indices.items()}

        def _euler(matrix: Any) -> tuple[float, float, float] | None:
            if matrix is None or getattr(matrix, "shape", ())[:2] != (4, 4):
                return None
            rotation = matrix[:3, :3]
            yaw = math.degrees(math.atan2(float(rotation[0, 2]), float(rotation[2, 2])))
            pitch = math.degrees(math.atan2(float(-rotation[1, 2]), math.hypot(float(rotation[1, 0]), float(rotation[1, 1]))))
            roll = math.degrees(math.atan2(float(rotation[1, 0]), float(rotation[1, 1])))
            return yaw, pitch, roll

        source_pose = _euler(source_matrix)
        candidate_pose = _euler(candidate_matrix)
        pose_delta = None
        if source_pose is not None and candidate_pose is not None:
            pose_delta = tuple(abs(candidate_pose[index] - source_pose[index]) for index in range(3))

        common_expression_names = sorted(set(source_blendshapes) & set(candidate_blendshapes))
        expression_distance = None
        if common_expression_names:
            expression_distance = float(np.linalg.norm(np.asarray([candidate_blendshapes[name] - source_blendshapes[name] for name in common_expression_names], dtype=np.float64)) / math.sqrt(len(common_expression_names)))

        asymmetry_pairs = [(33, 263), (133, 362), (61, 291), (70, 300), (234, 454), (172, 397)]
        def _asymmetry(points: Any) -> float:
            center = (points[10, :2] + points[152, :2]) / 2.0
            values = []
            for left_index, right_index in asymmetry_pairs:
                values.append(abs(float(np.linalg.norm(points[left_index, :2] - center)) - float(np.linalg.norm(points[right_index, :2] - center))))
            return float(np.mean(values))

        source_asymmetry = _asymmetry(source_points)
        candidate_asymmetry = _asymmetry(candidate_points)
        return {
            "landmark_backend": "mediapipe_face_landmarker",
            "landmark_status": "PASS",
            "landmark_count": int(source_points.shape[0]),
            "landmark_normalized_error": float(per_point.mean()),
            "landmark_region_errors": json.dumps(region_errors, separators=(",", ":")),
            "pose_delta_yaw_degrees": pose_delta[0] if pose_delta is not None else None,
            "pose_delta_pitch_degrees": pose_delta[1] if pose_delta is not None else None,
            "pose_delta_roll_degrees": pose_delta[2] if pose_delta is not None else None,
            "expression_distance": expression_distance,
            "asymmetry_change": abs(candidate_asymmetry - source_asymmetry),
            "source_asymmetry": source_asymmetry,
            "candidate_asymmetry": candidate_asymmetry,
            "expression_feature_count": len(common_expression_names),
            "landmark_model_revision": entry.get("source_revision"),
            "landmark_model_sha256": entry.get("artifact_sha256"),
        }, None
    except Exception as exc:
        return {"landmark_backend": "mediapipe_face_landmarker", "landmark_status": "UNCERTAIN", "error_type": type(exc).__name__}, f"landmark/pose/expression audit failed closed: {type(exc).__name__}"


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
    source_mask_path = private_root / "evidence" / "mask" / "foreground.png"
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
                gates["facial_proportions"] = "PASS"
            if candidate_image.getchannel("A").getextrema() != (255, 255):
                gates["foreground_integrity"] = "FAIL"
                reasons.append("candidate contains transparency")
            else:
                gates["foreground_integrity"] = "PASS"
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
    if files_present:
        landmark_metrics, landmark_issue = _landmark_signals(project, paths["source_master"], paths["candidate"])
        metrics.update(landmark_metrics)
        if landmark_issue:
            reasons.append(landmark_issue)
        elif not threshold_issues:
            landmark_error = landmark_metrics.get("landmark_normalized_error")
            landmark_limit = thresholds.get("landmarks", {}).get("max_normalized_error")
            if isinstance(landmark_error, (int, float)) and isinstance(landmark_limit, (int, float)):
                gates["landmarks"] = "PASS" if landmark_error <= landmark_limit else "FAIL"
                if gates["landmarks"] == "FAIL":
                    reasons.append("landmark normalized error is above the calibrated threshold")
            region_limits = thresholds.get("landmarks", {}).get("region_limits", {})
            region_errors_value = landmark_metrics.get("landmark_region_errors", "{}")
            try:
                region_errors = json.loads(region_errors_value) if isinstance(region_errors_value, str) else {}
            except json.JSONDecodeError:
                region_errors = {}
            if isinstance(region_limits, dict) and isinstance(region_errors, dict) and all(isinstance(region_errors.get(name), (int, float)) and isinstance(region_limits.get(name), (int, float)) and region_errors[name] <= region_limits[name] for name in ("eyes", "nose", "mouth", "jaw")):
                gates["facial_proportions"] = "PASS"
            elif isinstance(region_errors, dict) and any(isinstance(region_errors.get(name), (int, float)) and isinstance(region_limits.get(name), (int, float)) and region_errors[name] > region_limits[name] for name in ("eyes", "nose", "mouth", "jaw")):
                gates["facial_proportions"] = "FAIL"
                reasons.append("one or more calibrated facial-proportion regions exceed their limits")
            pose_values = [("yaw", "pose_delta_yaw_degrees", "max_yaw_delta_degrees"), ("pitch", "pose_delta_pitch_degrees", "max_pitch_delta_degrees"), ("roll", "pose_delta_roll_degrees", "max_roll_delta_degrees")]
            if all(isinstance(landmark_metrics.get(metric), (int, float)) and isinstance(thresholds.get("pose", {}).get(limit), (int, float)) for _, metric, limit in pose_values):
                pose_pass = all(landmark_metrics[metric] <= thresholds["pose"][limit] for _, metric, limit in pose_values)
                gates["head_direction"] = "PASS" if pose_pass else "FAIL"
                if not pose_pass:
                    reasons.append("head-direction delta exceeds a calibrated pose limit")
            expression_distance = landmark_metrics.get("expression_distance")
            expression_limit = thresholds.get("expression", {}).get("max_distance")
            if isinstance(expression_distance, (int, float)) and isinstance(expression_limit, (int, float)):
                gates["expression"] = "PASS" if expression_distance <= expression_limit else "FAIL"
                if gates["expression"] == "FAIL":
                    reasons.append("expression blendshape distance is above the calibrated threshold")
            asymmetry_change = landmark_metrics.get("asymmetry_change")
            asymmetry_limit = thresholds.get("asymmetry", {}).get("max_change")
            if isinstance(asymmetry_change, (int, float)) and isinstance(asymmetry_limit, (int, float)):
                gates["asymmetry"] = "PASS" if asymmetry_change <= asymmetry_limit else "FAIL"
                if gates["asymmetry"] == "FAIL":
                    reasons.append("facial asymmetry change is above the calibrated threshold")
    if files_present and not thresholds.get("hair_and_accessories", {}).get("required_attribute_agreement"):
        reasons.append("hairline, facial-hair, and accessory agreement requires a qualified visual audit")
    if files_present and not thresholds.get("style", {}).get("minimum_score"):
        reasons.append("style audit requires a calibrated HOI4 reference set and qualified visual classifier")
    if source_mask_path.is_file() and paths["mask_comparison"].is_file():
        try:
            import numpy as np  # type: ignore

            from_mask = np.asarray(_read_image(source_mask_path).convert("L"), dtype=np.uint8) >= 128
            candidate_mask = np.asarray(_read_image(paths["mask_comparison"]).convert("L"), dtype=np.uint8) >= 128
            if from_mask.shape != candidate_mask.shape:
                reasons.append("source and candidate foreground masks have different dimensions")
            else:
                union = int(np.logical_or(from_mask, candidate_mask).sum())
                mismatch = int(np.logical_xor(from_mask, candidate_mask).sum())
                leakage = float(mismatch / max(1, union))
                metrics["mask_union_pixels"] = union
                metrics["mask_mismatch_pixels"] = mismatch
                metrics["mask_boundary_leakage_ratio"] = leakage
                if not threshold_issues and isinstance(thresholds.get("mask", {}).get("maximum_boundary_leakage_ratio"), (int, float)):
                    gates["mask_boundary"] = "PASS" if leakage <= thresholds["mask"]["maximum_boundary_leakage_ratio"] else "FAIL"
                    if gates["mask_boundary"] == "FAIL":
                        reasons.append("foreground mask mismatch exceeds the calibrated boundary-leakage ratio")
        except Exception as exc:
            reasons.append(f"mask-boundary audit failed closed: {type(exc).__name__}")
    else:
        reasons.append("source and candidate foreground masks are not both available for independent mask audit")
    component_evidence_path = private_root / "evidence" / "mask" / "foreground.json"
    required_components = {"person_alpha", "hard_interior", "face", "hair_hat_boundary", "accessory_attention", "background", "boundary_ring"}
    if component_evidence_path.is_file():
        try:
            component_record = json.loads(component_evidence_path.read_text(encoding="utf-8"))
            component_records = component_record.get("component_masks") if isinstance(component_record, dict) else None
            contract = component_record.get("mask_contract") if isinstance(component_record, dict) else None
            component_verified = isinstance(component_records, dict) and required_components.issubset(component_records) and isinstance(contract, dict) and contract.get("status") == "PASS_STRUCTURAL_COMPONENTS"
            if component_verified:
                for component_name in sorted(required_components):
                    record = component_records[component_name]
                    if not isinstance(record, dict) or not isinstance(record.get("path"), str) or not isinstance(record.get("sha256"), str):
                        component_verified = False
                        break
                    component_path = relative_safe_path(private_root, record["path"])
                    if not component_path.is_file() or sha256_file(component_path) != record["sha256"]:
                        component_verified = False
                        break
            metrics["mask_component_contract_verified"] = component_verified
            metrics["mask_component_count"] = len(component_records) if isinstance(component_records, dict) else 0
            metrics["mask_alternative_comparison_status"] = str(contract.get("alternative_matting_comparison", {}).get("status", "UNKNOWN")) if isinstance(contract, dict) and isinstance(contract.get("alternative_matting_comparison"), dict) else "UNKNOWN"
            if not component_verified:
                reasons.append("component-mask contract or one of its private evidence checksums is incomplete")
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            metrics["mask_component_contract_verified"] = False
            metrics["mask_component_count"] = 0
            metrics["mask_alternative_comparison_status"] = "UNKNOWN"
            reasons.append(f"component-mask audit evidence could not be verified: {type(exc).__name__}")
    else:
        metrics["mask_component_contract_verified"] = False
        metrics["mask_component_count"] = 0
        metrics["mask_alternative_comparison_status"] = "MISSING"
        reasons.append("complete component-mask audit evidence is missing")
    if files_present and paths["manifest"].is_file():
        metrics["provenance_verified"] = True
        gates["provenance"] = "PASS"
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
