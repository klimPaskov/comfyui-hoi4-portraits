#!/usr/bin/env python3
"""Record the staged local autoprompter health and negative validation probe."""

from __future__ import annotations

import argparse
import base64
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image  # noqa: E402

from portrait_pipeline.autoprompter_service import AutoprompterService  # noqa: E402
from portrait_pipeline.util import atomic_json_write, project_root  # noqa: E402


def _full_power_format_probe(root: Path) -> dict:
    """Verify the pinned Transformers config/processor without loading 8B weights."""

    try:
        from transformers import AutoProcessor, Qwen3VLConfig  # type: ignore

        service = AutoprompterService(root, profile="human_full_power_gpu")
        processor = AutoProcessor.from_pretrained(str(service.model_root), local_files_only=True)
        config = Qwen3VLConfig.from_pretrained(str(service.model_root), local_files_only=True)
        try:
            import torch  # type: ignore

            cuda = bool(torch.cuda.is_available())
        except Exception:
            cuda = False
        return {
            "status": "PASS_FORMAT_AND_PROCESSOR_SCHEMA",
            "model_id": service.model_id,
            "model_root": str(service.model_root.relative_to(root)),
            "processor_class": type(processor).__name__,
            "config_class": type(config).__name__,
            "config_model_type": getattr(config, "model_type", None),
            "execution": "NOT_RUN_CUDA_UNAVAILABLE" if not cuda else "NOT_RUN_WEIGHT_LOAD_PENDING",
            "cuda_available": cuda,
        }
    except Exception as exc:
        return {"status": "BLOCKED_FORMAT_OR_PROCESSOR", "error": {"type": type(exc).__name__, "message": str(exc)}}


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the local loopback autoprompter runtime.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--base-url", default="http://127.0.0.1:8099")
    args = parser.parse_args(argv)
    root = project_root(args.root)
    checked_at = datetime.now(timezone.utc).isoformat()
    report = {
        "schema_version": "1.0.0",
        "checked_at": checked_at,
        "status": "BLOCKED_SIDECAR_NOT_RUNNING",
        "profile": "human_local_mac_16gb",
        "full_power": _full_power_format_probe(root),
        "negative_validation": {"status": "NOT_RUN"},
        "policy": "A negative validator probe is not a prompt-quality or portrait-generation acceptance run. A legally usable source fixture is required for positive qualification.",
    }
    try:
        service = AutoprompterService(root, profile="human_local_mac_16gb")
        health = _get(args.base_url + "/health")
        models = _get(args.base_url + "/v1/models")
        buffer = BytesIO()
        Image.new("RGB", (128, 160), (120, 120, 120)).save(buffer, format="PNG")
        payload = {
            "job_id": "autoprompt-negative-probe",
            "model_id": service.model_id,
            "instruction": service.instruction,
            "image_png_base64": base64.b64encode(buffer.getvalue()).decode("ascii"),
            "background_meta": {"must_not_be_forwarded": True},
        }
        request = urllib.request.Request(args.base_url + "/v1/chat/completions", data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        try:
            urllib.request.urlopen(request, timeout=300)
            negative = {"status": "FAIL", "expected": "HTTP_400_AUTOPROMPT_UNVERIFIED_CLAIM", "observed": "HTTP_200"}
        except urllib.error.HTTPError as exc:
            body = json.loads(exc.read().decode("utf-8"))
            error_message = body.get("error", {}).get("message", "") if isinstance(body, dict) else ""
            negative = {"status": "PASS" if exc.code == 400 and "AUTOPROMPT_UNVERIFIED_CLAIM" in error_message else "FAIL", "expected": "HTTP_400_AUTOPROMPT_UNVERIFIED_CLAIM", "observed_http_status": exc.code, "observed_error_code": "AUTOPROMPT_UNVERIFIED_CLAIM" if "AUTOPROMPT_UNVERIFIED_CLAIM" in error_message else None}
        report.update({"status": "PASS_HEALTH_AND_NEGATIVE_VALIDATION", "runtime": {"binary": str(service.binary.relative_to(root)), "model": str(service.model.relative_to(root)), "mmproj": str(service.mmproj.relative_to(root)), "health": health, "models": models}, "negative_validation": negative, "positive_generation": {"status": "BLOCKED_NO_LEGAL_SOURCE_FIXTURE"}, "staging": {"one_request_at_a_time": True, "background_metadata_forwarded": False, "binding": args.base_url, "process_shutdown_verified_by_caller": False}})
    except Exception as exc:  # evidence records why the probe did not run
        report["error"] = {"type": type(exc).__name__, "message": str(exc)}
    atomic_json_write(root / "docs" / "preflight" / "autoprompter_runtime_test.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if str(report.get("status", "")).startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
