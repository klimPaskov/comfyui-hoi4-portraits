"""Run the pinned local preprocessing route on one private qualification fixture.

The raw subject response (including landmarks) and the returned matte remain
under the ignored job root.  The checked-in report contains only model
identity, status, dimensions, checksums, and bounded summary measurements.
This script never invokes ComfyUI/Krea generation and cannot approve a
production source, background, threshold set, DDS, or integration.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image

from portrait_pipeline.util import atomic_json_write, project_root, relative_safe_path, sha256_file


def _post(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"preprocessing endpoint failed: {type(exc).__name__}") from exc
    if not isinstance(body, dict):
        raise RuntimeError("preprocessing endpoint returned a non-object")
    return body


def _summary_model(body: dict[str, Any]) -> dict[str, Any] | None:
    model = body.get("model")
    return model if isinstance(model, dict) else None


def qualify(root: Path, fixture_path: Path, *, endpoint: str, fixture_id: str, job_id: str) -> dict[str, Any]:
    if not endpoint.startswith(("http://127.0.0.1:", "http://localhost:")):
        raise RuntimeError("preprocessing endpoint must remain loopback-only")
    source_path = fixture_path.resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    try:
        source_relative = str(source_path.relative_to(root))
    except ValueError as exc:
        raise RuntimeError("fixture must remain under the project root") from exc

    with Image.open(source_path) as source:
        source_rgb = source.convert("RGB")
        source_size = source_rgb.size
        encoded = io.BytesIO()
        source_rgb.save(encoded, format="PNG", optimize=False)
    image_b64 = base64.b64encode(encoded.getvalue()).decode("ascii")
    job_root = relative_safe_path(root / "jobs", job_id)
    evidence_root = job_root / "evidence"
    evidence_root.mkdir(parents=True, exist_ok=True)
    source_copy = evidence_root / "source_master.png"
    source_rgb.save(source_copy, format="PNG", optimize=False)

    subject_model = {
        "name": "YuNet",
        "source_revision": "47534e27c9851bb1128ccc0102f1145e27f23f98",
        "artifact_sha256": "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    }
    mask_model = {
        "name": "BiRefNet",
        "source_revision": "25cb9309bacf3dde954e4584594e16e142c51de5",
        "artifact_sha256": "9ab37426bf4de0567af6b5d21b16151357149139362e6e8992021b8ce356a154",
    }
    base_payload = {"job_id": job_id, "image_png_base64": image_b64}

    subject_started = time.monotonic()
    subject = _post(endpoint.rstrip("/") + "/v1/subject", {**base_payload, "model": subject_model})
    subject_seconds = round(time.monotonic() - subject_started, 3)
    atomic_json_write(evidence_root / "subject_inventory.json", subject)

    mask_started = time.monotonic()
    mask = _post(endpoint.rstrip("/") + "/v1/mask", {**base_payload, "model": mask_model})
    mask_seconds = round(time.monotonic() - mask_started, 3)
    raw_mask = mask.get("mask_png_base64")
    if isinstance(raw_mask, str) and raw_mask:
        mask_path = evidence_root / "foreground_mask.png"
        mask_path.write_bytes(base64.b64decode(raw_mask, validate=True))
        mask_evidence = {"path": str(mask_path.relative_to(root)), "sha256": sha256_file(mask_path)}
    else:
        mask_evidence = {"path": None, "sha256": None}

    selected = subject.get("selected") if isinstance(subject.get("selected"), dict) else {}
    subjects = subject.get("subjects") if isinstance(subject.get("subjects"), list) else []
    subject_pass = subject.get("status") == "PASS" and subject.get("analysis_status") == "PASS" and len(subjects) == 1
    mask_pass = mask.get("status") == "PASS" and mask.get("analysis_status") == "PASS" and bool(mask_evidence["path"])
    report = {
        "schema_version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS_PREPROCESSING_ONLY" if subject_pass and mask_pass else "BLOCKED_PREPROCESSING",
        "fixture_id": fixture_id,
        "fixture_path": source_relative,
        "source_sha256": sha256_file(source_path),
        "source_dimensions": list(source_size),
        "private_job_root": str(job_root.relative_to(root)),
        "raw_biometric_evidence": "retained only under the ignored private job root",
        "subject": {
            "status": subject.get("status"),
            "analysis_status": subject.get("analysis_status"),
            "model": _summary_model(subject),
            "association_model": subject.get("association_model"),
            "landmark_model": subject.get("landmark_model"),
            "subject_count": len(subjects),
            "selected_bbox_xyxy": selected.get("bbox_xyxy"),
            "selected_confidence": selected.get("confidence"),
            "runtime_seconds": subject_seconds,
            "error_code": subject.get("error_code"),
            "error": subject.get("error"),
        },
        "mask": {
            "status": mask.get("status"),
            "analysis_status": mask.get("analysis_status"),
            "model": _summary_model(mask),
            "stats": mask.get("mask_stats"),
            "inference": mask.get("inference"),
            "runtime_seconds": mask_seconds,
            "evidence": mask_evidence,
            "error_code": mask.get("error_code"),
            "error": mask.get("error"),
        },
        "production_policy": {
            "krea_generation_attempted": False,
            "approved_background_changed": False,
            "identity_thresholds_changed": False,
            "dds_or_mod_integration_created": False,
            "independent_production_audit": "not_run",
        },
    }
    atomic_json_write(root / "docs" / "preflight" / "source_fixture_execution.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Qualify a private source fixture through the pinned preprocessing sidecar.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--fixture", type=Path, default=Path("fixtures/private/loc_dag_1518_portrait.jpg"))
    parser.add_argument("--fixture-id", default="loc_dag_1518_portrait")
    parser.add_argument("--job-id", default="fixture-loc-1518")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8790")
    args = parser.parse_args()
    root = project_root(args.root)
    fixture = args.fixture if args.fixture.is_absolute() else root / args.fixture
    report = qualify(root, fixture, endpoint=args.endpoint, fixture_id=args.fixture_id, job_id=args.job_id)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "PASS_PREPROCESSING_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
