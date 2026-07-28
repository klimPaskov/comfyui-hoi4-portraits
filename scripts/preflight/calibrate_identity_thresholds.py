#!/usr/bin/env python3
"""Measure the pinned face-embedding calibration distribution.

This command is deliberately not a threshold approver.  It computes a
private calibration distribution from legally usable fixture images and emits
only aggregate evidence.  The production threshold file is not modified:
landmark, pose, expression, accessory, mask, and style calibration still have
to be supplied before a threshold record can become approved.
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
    darker = cv2.cvtColor(np.asarray(ImageEnhance.Brightness(pil).enhance(0.82)), cv2.COLOR_RGB2BGR)
    jpeg = _jpeg_variant(pil, 62)
    return [resized, gray, darker, jpeg]


def _load_backend(root: Path) -> tuple[Any, Any, dict[str, Any]]:
    import cv2  # type: ignore

    lock = json.loads((root / "dependencies" / "preprocessing_lock.json").read_text(encoding="utf-8"))
    entries = {item.get("name"): item for item in lock.get("dependencies", []) if isinstance(item, dict)}
    yunet_entry = entries["YuNet"]
    sface_entry = entries["SFace"]
    yunet_path = root / str(yunet_entry["destination_path"])
    sface_path = root / str(sface_entry["destination_path"])
    if not yunet_path.is_file() or not sface_path.is_file():
        raise FileNotFoundError("pinned YuNet or SFace artifact is missing")
    detector = cv2.FaceDetectorYN.create(str(yunet_path), "", (320, 320), 0.6, 0.3, 5000)
    recognizer = cv2.FaceRecognizerSF.create(str(sface_path), "")
    model_summary = {
        "detector": {"name": "YuNet", "revision": yunet_entry.get("source_revision"), "sha256": yunet_entry.get("artifact_sha256")},
        "recognizer": {"name": "SFace", "revision": sface_entry.get("source_revision"), "sha256": sface_entry.get("artifact_sha256")},
    }
    return detector, recognizer, model_summary


def _feature(detector: Any, recognizer: Any, image: Any) -> tuple[Any | None, int]:
    detector.setInputSize((int(image.shape[1]), int(image.shape[0])))
    _, faces = detector.detect(image)
    count = 0 if faces is None else len(faces)
    if count != 1:
        return None, count
    aligned = recognizer.alignCrop(image, faces[0])
    return recognizer.feature(aligned), count


def _fixture_paths(root: Path, fixture_dir: Path) -> list[Path]:
    paths = sorted(fixture_dir.glob("loc_*.jpg"))
    legacy = root / "fixtures/private/loc_dag_1518_portrait.jpg"
    if legacy.is_file():
        paths.append(legacy)
    return paths


def _fixture_manifest(root: Path, fixture_dir: Path, fixture_paths: list[Path]) -> dict[str, Any]:
    manifest_path = fixture_dir / "manifest.json"
    relative_path = str(manifest_path.relative_to(root))
    if not manifest_path.is_file():
        return {
            "status": "BLOCKED_MISSING",
            "path": relative_path,
            "sha256": None,
            "declared_count": 0,
            "observed_count": len(fixture_paths),
            "missing_fixture_ids": [path.stem for path in fixture_paths],
            "extra_fixture_ids": [],
        }
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        declared_ids = {str(item["fixture_id"]) for item in manifest.get("fixtures", []) if isinstance(item, dict) and item.get("fixture_id")}
    except (OSError, json.JSONDecodeError, TypeError, KeyError):
        return {
            "status": "BLOCKED_INVALID",
            "path": relative_path,
            "sha256": sha256_file(manifest_path),
            "declared_count": 0,
            "observed_count": len(fixture_paths),
            "missing_fixture_ids": [path.stem for path in fixture_paths],
            "extra_fixture_ids": [],
        }
    observed_ids = {path.stem for path in fixture_paths}
    missing = sorted(observed_ids - declared_ids)
    extra = sorted(declared_ids - observed_ids)
    return {
        "status": "PASS" if not missing and not extra else "BLOCKED_INCOMPLETE",
        "path": relative_path,
        "sha256": sha256_file(manifest_path),
        "declared_count": len(declared_ids),
        "observed_count": len(observed_ids),
        "missing_fixture_ids": missing,
        "extra_fixture_ids": extra,
    }


def calibrate(root: Path, fixture_dir: Path, *, min_negative_pairs: int) -> dict[str, Any]:
    import cv2  # type: ignore

    detector, recognizer, models = _load_backend(root)
    fixture_paths = _fixture_paths(root, fixture_dir)
    manifest = _fixture_manifest(root, fixture_dir, fixture_paths)
    accepted: list[tuple[str, Any, Image.Image]] = []
    rejected: list[dict[str, Any]] = []
    for path in fixture_paths:
        try:
            with Image.open(path) as opened:
                image = opened.convert("RGB")
            bgr = cv2.cvtColor(__import__("numpy").asarray(image), cv2.COLOR_RGB2BGR)
            feature, face_count = _feature(detector, recognizer, bgr)
            if feature is None:
                rejected.append({"fixture_id": path.stem, "reason": "expected exactly one face", "face_count": face_count})
                continue
            accepted.append((path.stem, feature, image))
        except Exception as exc:
            rejected.append({"fixture_id": path.stem, "reason": f"decode_or_model_error:{type(exc).__name__}"})

    positive: list[float] = []
    positive_variant_count = 0
    for fixture_id, original_feature, image in accepted:
        bgr_variants = _variants(cv2.cvtColor(__import__("numpy").asarray(image), cv2.COLOR_RGB2BGR))
        for variant in bgr_variants:
            variant_feature, face_count = _feature(detector, recognizer, variant)
            if variant_feature is not None:
                positive.append(float(recognizer.match(original_feature, variant_feature, cv2.FaceRecognizerSF_FR_COSINE)))
                positive_variant_count += 1

    negative: list[float] = []
    for index, (_, left, _) in enumerate(accepted):
        for _, right, _ in accepted[index + 1 :]:
            negative.append(float(recognizer.match(left, right, cv2.FaceRecognizerSF_FR_COSINE)))

    positive_p05 = _quantile(positive, 0.05)
    negative_p999 = _quantile(negative, 0.999)
    candidate = max(negative) if negative else None
    target_met = candidate is not None and positive_p05 is not None and candidate <= positive_p05
    blockers: list[str] = []
    if len(negative) < min_negative_pairs:
        blockers.append(f"different-person pair count {len(negative)} is below the required {min_negative_pairs}")
    if not accepted:
        blockers.append("no fixture produced exactly one detectable face")
    if not positive:
        blockers.append("no same-person variant score was measured")
    if not target_met:
        blockers.append("the observed FAR/FRR operating point is not simultaneously demonstrated")
    if manifest["status"] != "PASS":
        blockers.append("the private calibration fixture manifest does not enumerate exactly the observed fixture set")
    blockers.extend([
        "landmark, pose, expression, hair/accessory, mask, and style thresholds require separate calibrated evidence",
        "the tracked production threshold file remains unchanged and fail-closed",
    ])
    return {
        "schema_version": "1.0.0",
        "calibration_id": "loc-daguerreotype-face-embedding-2026-07-29",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "BLOCKED_FACE_CALIBRATION_INCOMPLETE" if blockers else "PASS_FACE_CALIBRATION_PARTIAL",
        "source_class": "public_domain_primary_archive",
        "rights_policy": "private_local_calibration_only; no source portrait or biometric vector is written to Git",
        "models": models,
        "fixture_set": {
            "fixture_count": len(fixture_paths),
            "accepted_single_face_count": len(accepted),
            "rejected_count": len(rejected),
            "rejected": rejected,
            "variant_policy": ["resize_round_trip", "grayscale", "brightness_0.82", "jpeg_quality_62"],
        },
        "fixture_manifest": manifest,
        "positive_same_person": {
            "score_count": len(positive),
            "minimum": min(positive) if positive else None,
            "p05": positive_p05,
            "median": _quantile(positive, 0.50),
            "maximum": max(positive) if positive else None,
        },
        "negative_different_person": {
            "pair_count": len(negative),
            "required_pair_count": min_negative_pairs,
            "maximum": max(negative) if negative else None,
            "p999": negative_p999,
            "median": _quantile(negative, 0.50),
        },
        "operating_point": {
            "target_false_accept_rate_max": 0.001,
            "target_false_reject_rate_max": 0.05,
            "candidate_minimum_similarity": candidate,
            "observed_positive_p05": positive_p05,
            "target_simultaneously_demonstrated": target_met and len(negative) >= min_negative_pairs,
            "approved": False,
        },
        "blocked_reasons": blockers,
        "policy": "This report measures calibration evidence only. It cannot authorize a production threshold, candidate, PNG, DDS, or mod integration output.",
    }


def render_markdown(report: dict[str, Any]) -> str:
    fixture = report["fixture_set"]
    positive = report["positive_same_person"]
    negative = report["negative_different_person"]
    operating = report["operating_point"]
    lines = [
        "# Identity calibration evidence",
        "",
        f"- Status: **{report['status']}**",
        f"- Calibration ID: `{report['calibration_id']}`",
        f"- Source class: `{report['source_class']}`",
        "- Source collection: [Library of Congress Daguerreotypes Collection](https://www.loc.gov/collections/daguerreotypes/about-this-collection/)",
        "",
        "This is an aggregate calibration measurement. It does not modify the tracked threshold file and cannot authorize a portrait, PNG, DDS, or mod integration output.",
        "",
        "## Measured set",
        "",
        f"- Fixture images: `{fixture['fixture_count']}`",
        f"- Exactly-one-face fixtures: `{fixture['accepted_single_face_count']}`",
        f"- Rejected fixtures: `{fixture['rejected_count']}`",
        f"- Private manifest: `{report['fixture_manifest']['status']}` ({report['fixture_manifest']['declared_count']} declared / {report['fixture_manifest']['observed_count']} observed)",
        f"- Same-person variant scores: `{positive['score_count']}`",
        f"- Different-person pairs: `{negative['pair_count']}` / `{negative['required_pair_count']}` required",
        "",
        "## Observed SFace distribution",
        "",
        "| Distribution | Minimum | P05/P99.9 | Median | Maximum |",
        "| --- | ---: | ---: | ---: | ---: |",
        f"| Same-person variants | {positive['minimum']} | {positive['p05']} | {positive['median']} | {positive['maximum']} |",
        f"| Different-person pairs | — | {negative['p999']} | {negative['median']} | {negative['maximum']} |",
        "",
        f"Candidate operating point: `{operating['candidate_minimum_similarity']}`; simultaneous target demonstrated: **{operating['target_simultaneously_demonstrated']}**.",
        "",
        "## Blockers",
        "",
    ]
    lines.extend(f"- {reason}" for reason in report["blocked_reasons"])
    lines.extend([
        "",
        "The production threshold record remains `config/identity_thresholds.json` with `fail_closed: true` and null acceptance values.",
        "",
        "Source images and biometric vectors remain private under the ignored fixture/job roots.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure pinned face-embedding calibration evidence without approving thresholds.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--fixture-dir", type=Path, default=Path("fixtures/private/loc_calibration_2026-07-29"))
    parser.add_argument("--output", type=Path, default=Path("docs/preflight/identity_calibration_2026-07-29.json"))
    parser.add_argument("--markdown-output", type=Path, default=Path("docs/preflight/identity_calibration_2026-07-29.md"))
    parser.add_argument("--private-output", type=Path, default=Path("jobs/identity-calibration-2026-07-29/evidence/face_embedding_calibration.json"))
    parser.add_argument("--min-negative-pairs", type=int, default=1000)
    args = parser.parse_args()
    root = project_root(args.root)
    fixture_dir = args.fixture_dir if args.fixture_dir.is_absolute() else root / args.fixture_dir
    report = calibrate(root, fixture_dir, min_negative_pairs=max(1, args.min_negative_pairs))
    output = args.output if args.output.is_absolute() else root / args.output
    private_output = args.private_output if args.private_output.is_absolute() else root / args.private_output
    atomic_json_write(output, report)
    markdown_output = args.markdown_output if args.markdown_output.is_absolute() else root / args.markdown_output
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(render_markdown(report), encoding="utf-8")
    private_output.parent.mkdir(parents=True, exist_ok=True)
    atomic_json_write(private_output, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "PASS_FACE_CALIBRATION_PARTIAL" else int(ExitCode.AUDIT_UNCERTAIN)


if __name__ == "__main__":
    raise SystemExit(main())
