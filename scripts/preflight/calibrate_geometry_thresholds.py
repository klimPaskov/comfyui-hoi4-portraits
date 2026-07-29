#!/usr/bin/env python3
"""Measure pinned geometry, pose, expression, and asymmetry evidence.

This command measures invariance of the pinned YuNet face crop plus MediaPipe
Face Landmarker on private, rights-cleared fixture images and deterministic
preprocessing variants.  It is evidence only: it never edits
``config/identity_thresholds`` and cannot authorize a production candidate.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageEnhance

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from portrait_pipeline.constants import ExitCode  # noqa: E402
from portrait_pipeline.util import atomic_json_write, project_root, sha256_file  # noqa: E402


REGION_INDICES = {
    "eyes": [33, 133, 159, 145, 362, 263, 386, 374],
    "nose": [1, 2, 4, 5, 6, 98, 327, 168],
    "mouth": [61, 291, 13, 14, 78, 308],
    "jaw": [10, 152, 234, 454, 172, 397],
}
ASYMMETRY_PAIRS = [(33, 263), (133, 362), (61, 291), (70, 300), (234, 454), (172, 397)]


def _quantile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    weight = position - lower
    return float(ordered[lower] * (1.0 - weight) + ordered[upper] * weight)


def _jpeg_variant(image: Image.Image, quality: int) -> Any:
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    encoded = io.BytesIO()
    image.save(encoded, format="JPEG", quality=quality, optimize=False)
    decoded = np.frombuffer(encoded.getvalue(), dtype=np.uint8)
    return cv2.imdecode(decoded, cv2.IMREAD_COLOR)


def _variants(image: Any) -> list[Any]:
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    height, width = image.shape[:2]
    smaller = cv2.resize(image, (max(64, int(width * 0.72)), max(64, int(height * 0.72))), interpolation=cv2.INTER_AREA)
    resized = cv2.resize(smaller, (width, height), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    darker = cv2.cvtColor(__import__("numpy").asarray(ImageEnhance.Brightness(pil).enhance(0.82)), cv2.COLOR_RGB2BGR)
    jpeg = _jpeg_variant(pil, 62)
    return [resized, gray, darker, jpeg]


def _fixture_paths(root: Path, fixture_dir: Path) -> list[Path]:
    paths = sorted(fixture_dir.glob("loc_*.jpg"))
    legacy = root / "fixtures/private/loc_dag_1518_portrait.jpg"
    if legacy.is_file():
        paths.append(legacy)
    return paths


def _manifest_summary(root: Path, fixture_dir: Path, paths: list[Path]) -> dict[str, Any]:
    manifest_path = fixture_dir / "manifest.json"
    relative = str(manifest_path.relative_to(root))
    if not manifest_path.is_file():
        return {"status": "BLOCKED_MISSING", "path": relative, "sha256": None, "declared_count": 0, "observed_count": len(paths)}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        declared = {str(item["fixture_id"]) for item in manifest.get("fixtures", []) if isinstance(item, dict) and item.get("fixture_id")}
    except (OSError, json.JSONDecodeError, TypeError, KeyError):
        return {"status": "BLOCKED_INVALID", "path": relative, "sha256": sha256_file(manifest_path), "declared_count": 0, "observed_count": len(paths)}
    observed = {path.stem for path in paths}
    return {
        "status": "PASS" if declared == observed else "BLOCKED_INCOMPLETE",
        "path": relative,
        "sha256": sha256_file(manifest_path),
        "declared_count": len(declared),
        "observed_count": len(observed),
        "missing_fixture_ids": sorted(observed - declared),
        "extra_fixture_ids": sorted(declared - observed),
    }


def _landmarker(root: Path) -> tuple[Any, dict[str, Any]]:
    import mediapipe as mp  # type: ignore

    lock = json.loads((root / "dependencies" / "preprocessing_lock.json").read_text(encoding="utf-8"))
    entries = {item.get("name"): item for item in lock.get("dependencies", []) if isinstance(item, dict)}
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
    return mp.tasks.vision.FaceLandmarker.create_from_options(options), {
        "name": "MediaPipe Face Landmarker",
        "revision": entry.get("source_revision"),
        "sha256": entry.get("artifact_sha256"),
    }


def _face_crop_detector(root: Path) -> tuple[Any, dict[str, Any]]:
    import cv2  # type: ignore

    lock = json.loads((root / "dependencies" / "preprocessing_lock.json").read_text(encoding="utf-8"))
    entries = {item.get("name"): item for item in lock.get("dependencies", []) if isinstance(item, dict)}
    entry = entries["YuNet"]
    model_path = root / str(entry["destination_path"])
    if not model_path.is_file():
        raise FileNotFoundError("pinned YuNet face detector is missing")
    return cv2.FaceDetectorYN.create(str(model_path), "", (320, 320), 0.6, 0.3, 5000), {
        "name": "YuNet",
        "revision": entry.get("source_revision"),
        "sha256": entry.get("artifact_sha256"),
    }


def _single_face_crop(detector: Any, image: Any) -> Any:
    """Make the landmarker input deterministic for portrait-scale fixtures.

    MediaPipe is intentionally run on a YuNet-selected crop for every source
    and variant.  This preserves the exactly-one-face rule while avoiding a
    full-canvas detector failure on small or low-contrast archive scans.  The
    crop policy is fixed and recorded in the aggregate report; no bbox is
    emitted.
    """
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    rgb = np.ascontiguousarray(image, dtype=np.uint8)
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("expected an RGB image")
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    height, width = bgr.shape[:2]
    detector.setInputSize((int(width), int(height)))
    _, faces = detector.detect(bgr)
    count = 0 if faces is None else len(faces)
    if count != 1:
        raise ValueError(f"YuNet expected exactly one face, found {count}")
    x, y, face_width, face_height = [float(value) for value in faces[0][:4]]
    margin = 0.65 * max(face_width, face_height)
    left = max(0, int(math.floor(x - margin)))
    top = max(0, int(math.floor(y - margin)))
    right = min(width, int(math.ceil(x + face_width + margin)))
    bottom = min(height, int(math.ceil(y + face_height + margin)))
    crop = rgb[top:bottom, left:right]
    if crop.size == 0 or crop.shape[0] < 32 or crop.shape[1] < 32:
        raise ValueError("YuNet face crop is too small")
    return np.ascontiguousarray(crop, dtype=np.uint8)


def _detect(landmarker: Any, image: Any) -> tuple[Any, dict[str, float], Any]:
    import mediapipe as mp  # type: ignore
    import numpy as np  # type: ignore

    array = np.ascontiguousarray(image, dtype=np.uint8)
    result = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=array))
    faces = getattr(result, "face_landmarks", None) or []
    if len(faces) != 1:
        raise ValueError(f"expected exactly one face, found {len(faces)}")
    points = np.asarray([[float(point.x), float(point.y), float(point.z)] for point in faces[0]], dtype=np.float64)
    left, top = points[:, :2].min(axis=0)
    right, bottom = points[:, :2].max(axis=0)
    width = max(1e-9, float(right - left))
    height = max(1e-9, float(bottom - top))
    normalized = points.copy()
    normalized[:, 0] = (normalized[:, 0] - left) / width
    normalized[:, 1] = (normalized[:, 1] - top) / height
    blendshapes: dict[str, float] = {}
    blendshape_sets = getattr(result, "face_blendshapes", None) or []
    if blendshape_sets:
        for category in blendshape_sets[0]:
            name = getattr(category, "category_name", None)
            if isinstance(name, str):
                blendshapes[name] = float(getattr(category, "score", 0.0))
    matrices = getattr(result, "facial_transformation_matrixes", None) or []
    matrix = np.asarray(matrices[0], dtype=np.float64) if matrices else None
    return normalized, blendshapes, matrix


def _euler(matrix: Any) -> tuple[float, float, float] | None:
    if matrix is None or getattr(matrix, "shape", ())[:2] != (4, 4):
        return None
    rotation = matrix[:3, :3]
    yaw = math.degrees(math.atan2(float(rotation[0, 2]), float(rotation[2, 2])))
    pitch = math.degrees(math.atan2(float(-rotation[1, 2]), math.hypot(float(rotation[1, 0]), float(rotation[1, 1]))))
    roll = math.degrees(math.atan2(float(rotation[1, 0]), float(rotation[1, 1])))
    return yaw, pitch, roll


def _asymmetry(points: Any) -> float:
    import numpy as np  # type: ignore

    center = (points[10, :2] + points[152, :2]) / 2.0
    values = []
    for left_index, right_index in ASYMMETRY_PAIRS:
        values.append(abs(float(np.linalg.norm(points[left_index, :2] - center)) - float(np.linalg.norm(points[right_index, :2] - center))))
    return float(np.mean(values))


def _signals(source: tuple[Any, dict[str, float], Any], variant: tuple[Any, dict[str, float], Any]) -> dict[str, Any]:
    import numpy as np  # type: ignore

    source_points, source_blendshapes, source_matrix = source
    variant_points, variant_blendshapes, variant_matrix = variant
    if source_points.shape != variant_points.shape or source_points.shape[0] < 400:
        raise ValueError("landmark topology is incomplete or changed")
    per_point = np.linalg.norm(variant_points[:, :2] - source_points[:, :2], axis=1)
    region_errors = {name: float(per_point[indices].mean()) for name, indices in REGION_INDICES.items()}
    source_pose = _euler(source_matrix)
    variant_pose = _euler(variant_matrix)
    pose_delta = None
    if source_pose is not None and variant_pose is not None:
        pose_delta = tuple(abs(variant_pose[index] - source_pose[index]) for index in range(3))
    common = sorted(set(source_blendshapes) & set(variant_blendshapes))
    expression_distance = None
    if common:
        expression_distance = float(np.linalg.norm(np.asarray([variant_blendshapes[name] - source_blendshapes[name] for name in common], dtype=np.float64)) / math.sqrt(len(common)))
    return {
        "landmark_normalized_error": float(per_point.mean()),
        "region_errors": region_errors,
        "pose_delta_yaw_degrees": pose_delta[0] if pose_delta else None,
        "pose_delta_pitch_degrees": pose_delta[1] if pose_delta else None,
        "pose_delta_roll_degrees": pose_delta[2] if pose_delta else None,
        "expression_distance": expression_distance,
        "asymmetry_change": abs(_asymmetry(variant_points) - _asymmetry(source_points)),
        "expression_feature_count": len(common),
    }


def _distribution(values: list[float]) -> dict[str, Any]:
    return {
        "count": len(values),
        "p95": _quantile(values, 0.95),
        "p99": _quantile(values, 0.99),
        "maximum": max(values) if values else None,
    }


def calibrate(root: Path, fixture_dir: Path) -> dict[str, Any]:
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    paths = _fixture_paths(root, fixture_dir)
    manifest = _manifest_summary(root, fixture_dir, paths)
    landmarker, landmarker_model = _landmarker(root)
    detector, detector_model = _face_crop_detector(root)
    accepted = 0
    rejected: list[dict[str, Any]] = []
    measurements: list[dict[str, Any]] = []
    try:
        for path in paths:
            try:
                with Image.open(path) as opened:
                    image = opened.convert("RGB")
                source = np.asarray(image, dtype=np.uint8)
                source_features = _detect(landmarker, _single_face_crop(detector, source))
                accepted += 1
                bgr = cv2.cvtColor(source, cv2.COLOR_RGB2BGR)
                for variant_index, variant in enumerate(_variants(bgr)):
                    variant_rgb = cv2.cvtColor(variant, cv2.COLOR_BGR2RGB)
                    variant_crop = _single_face_crop(detector, variant_rgb)
                    measured = _signals(source_features, _detect(landmarker, variant_crop))
                    measured["fixture_id"] = path.stem
                    measured["variant_index"] = variant_index
                    measurements.append(measured)
            except Exception as exc:
                rejected.append({"fixture_id": path.stem, "reason": f"{type(exc).__name__}:{exc}"})
    finally:
        landmarker.close()

    scalar_names = [
        "landmark_normalized_error",
        "pose_delta_yaw_degrees",
        "pose_delta_pitch_degrees",
        "pose_delta_roll_degrees",
        "expression_distance",
        "asymmetry_change",
    ]
    scalar_distributions = {
        name: _distribution([float(item[name]) for item in measurements if isinstance(item.get(name), (int, float))])
        for name in scalar_names
    }
    region_distributions = {
        name: _distribution([float(item["region_errors"][name]) for item in measurements if isinstance(item.get("region_errors"), dict) and isinstance(item["region_errors"].get(name), (int, float))])
        for name in REGION_INDICES
    }
    blockers = [
        "these measurements cover preprocessing invariance only; source-specific generated-candidate acceptance is still required",
        "hairline, facial-hair, accessory, foreground-mask, and HOI4-style thresholds require separate labeled evidence",
        "the tracked production threshold file remains unchanged and fail-closed",
    ]
    if manifest["status"] != "PASS":
        blockers.append("the private calibration fixture manifest does not enumerate exactly the observed fixture set")
    if not measurements:
        blockers.append("no geometry measurement completed")
    elif accepted < 20 or len(measurements) < 100:
        blockers.append(f"geometry calibration is currently small-sample evidence ({accepted} accepted fixtures, {len(measurements)} measurements); it is not sufficient for production approval")
    return {
        "schema_version": "1.0.0",
        "calibration_id": "loc-daguerreotype-geometry-2026-07-29",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "GEOMETRY_EVIDENCE_MEASURED_PRODUCTION_BLOCKED" if measurements and manifest["status"] == "PASS" else "BLOCKED_GEOMETRY_CALIBRATION_INCOMPLETE",
        "source_class": "public_domain_primary_archive",
        "rights_policy": "private_local_calibration_only; no source portrait or landmark vector is written to Git",
        "model": {
            "landmarker": landmarker_model,
            "face_crop_detector": detector_model,
        },
        "fixture_set": {
            "fixture_count": len(paths),
            "accepted_single_face_count": accepted,
            "rejected_count": len(rejected),
            "rejected": rejected,
            "variant_policy": ["resize_round_trip", "grayscale", "brightness_0.82", "jpeg_quality_62"],
            "landmarker_input_policy": "pinned_yunet_single_face_crop; bbox margin is 0.65x the larger face dimension; no bbox is emitted",
        },
        "fixture_manifest": manifest,
        "measurement_count": len(measurements),
        "scalar_distributions": scalar_distributions,
        "region_distributions": region_distributions,
        "proposed_operating_point": {
            "basis": "observed_p99_preprocessing_invariance; not an approval",
            "landmark_max_normalized_error": scalar_distributions["landmark_normalized_error"]["p99"],
            "region_limits": {name: values["p99"] for name, values in region_distributions.items()},
            "pose_limits": {name: scalar_distributions[f"pose_delta_{name}_degrees"]["p99"] for name in ("yaw", "pitch", "roll")},
            "expression_max_distance": scalar_distributions["expression_distance"]["p99"],
            "asymmetry_max_change": scalar_distributions["asymmetry_change"]["p99"],
            "approved": False,
        },
        "blocked_reasons": blockers,
        "policy": "This report is aggregate calibration evidence only. It cannot authorize a threshold record, candidate, PNG, DDS, or mod integration output.",
    }


def render_markdown(report: dict[str, Any]) -> str:
    scalar = report["scalar_distributions"]
    proposed = report["proposed_operating_point"]
    lines = [
        "# Geometry calibration evidence",
        "",
        f"- Status: **{report['status']}**",
        f"- Calibration ID: `{report['calibration_id']}`",
        "- Source collection: [Library of Congress Daguerreotypes Collection](https://www.loc.gov/collections/daguerreotypes/about-this-collection/)",
        "",
        "This is preprocessing-invariance evidence using a pinned YuNet-selected face crop before MediaPipe landmarking. It does not modify the tracked threshold file and cannot authorize a portrait, PNG, DDS, or mod integration output.",
        "",
        f"- Fixtures: `{report['fixture_set']['fixture_count']}`; exactly-one-face: `{report['fixture_set']['accepted_single_face_count']}`",
        f"- Measurements: `{report['measurement_count']}`; private manifest: `{report['fixture_manifest']['status']}`",
        "",
        "| Signal | Count | P95 | P99 | Maximum |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, values in scalar.items():
        lines.append(f"| `{name}` | {values['count']} | {values['p95']} | {values['p99']} | {values['maximum']} |")
    lines.extend(["", "## Proposed operating point (not approved)", "", f"- Basis: `{proposed['basis']}`", f"- Landmark limit: `{proposed['landmark_max_normalized_error']}`", f"- Region limits: `{json.dumps(proposed['region_limits'], sort_keys=True)}`", f"- Pose limits: `{json.dumps(proposed['pose_limits'], sort_keys=True)}`", f"- Expression limit: `{proposed['expression_max_distance']}`", f"- Asymmetry limit: `{proposed['asymmetry_max_change']}`", "- Approved: **False**", "", "## Blockers", ""])
    lines.extend(f"- {reason}" for reason in report["blocked_reasons"])
    lines.extend(["", "Source images and biometric-derived landmarks remain private under the ignored fixture/job roots.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure pinned geometry evidence without approving thresholds.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--fixture-dir", type=Path, default=Path("fixtures/private/loc_calibration_2026-07-29"))
    parser.add_argument("--output", type=Path, default=Path(".runtime/reports/geometry_calibration.json"))
    parser.add_argument("--markdown-output", type=Path, default=Path(".runtime/reports/geometry_calibration.md"))
    parser.add_argument("--private-output", type=Path, default=Path("jobs/geometry-calibration-2026-07-29/evidence/geometry_calibration.json"))
    args = parser.parse_args()
    root = project_root(args.root)
    fixture_dir = args.fixture_dir if args.fixture_dir.is_absolute() else root / args.fixture_dir
    report = calibrate(root, fixture_dir)
    output = args.output if args.output.is_absolute() else root / args.output
    markdown = args.markdown_output if args.markdown_output.is_absolute() else root / args.markdown_output
    private = args.private_output if args.private_output.is_absolute() else root / args.private_output
    atomic_json_write(output, report)
    markdown.parent.mkdir(parents=True, exist_ok=True)
    markdown.write_text(render_markdown(report), encoding="utf-8")
    private.parent.mkdir(parents=True, exist_ok=True)
    atomic_json_write(private, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return int(ExitCode.AUDIT_UNCERTAIN)


if __name__ == "__main__":
    raise SystemExit(main())
