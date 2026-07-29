"""Pinned local visual-rubric producer for the independent auditor.

This module is deliberately separate from the ComfyUI producer and the human
autoprompter. It loads only checksum-verified local artifacts, binds every
input image to its private job root, sends the fixed rubric to a loopback-only
llama.cpp process, and writes a schema-validated evidence record. It never
selects candidates, edits images, or approves thresholds.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import validate_schema
from .util import atomic_json_write, project_root, relative_safe_path, sha256_file


VISUAL_AUDIT_LOCK_PATH = "dependencies/visual_audit_runtime.lock.json"
VISUAL_REFERENCE_SCHEMA_PATH = "schemas/visual_reference_set.schema.json"
VISUAL_EVIDENCE_SCHEMA_PATH = "schemas/visual_audit_evidence.schema.json"


class VisualAuditServiceError(RuntimeError):
    """Raised when visual-audit production cannot be verified safely."""


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VisualAuditServiceError(f"{label} is unreadable: {type(exc).__name__}") from exc
    if not isinstance(value, dict):
        raise VisualAuditServiceError(f"{label} must contain a JSON object")
    return value


def _verify_locked_file(root: Path, relative_path: str, expected_sha256: str, expected_size: int | None, label: str) -> Path:
    path = relative_safe_path(root, relative_path)
    if not path.is_file():
        raise VisualAuditServiceError(f"locked {label} is missing: {relative_path}")
    if expected_size is not None and path.stat().st_size != expected_size:
        raise VisualAuditServiceError(f"locked {label} size mismatch: {relative_path}")
    if sha256_file(path) != expected_sha256:
        raise VisualAuditServiceError(f"locked {label} checksum mismatch: {relative_path}")
    return path


def _load_runtime_lock(root: Path) -> tuple[dict[str, Any], Path, Path, Path, Path]:
    lock = _read_json(root / VISUAL_AUDIT_LOCK_PATH, "visual-audit runtime lock")
    if lock.get("status") != "PINNED_LOCAL_LOOPBACK_PRODUCER_EXECUTION_UNVERIFIED":
        raise VisualAuditServiceError("visual-audit runtime lock is not in the pinned local state")
    rubric = lock.get("rubric")
    runtime = lock.get("runtime")
    model = lock.get("model")
    if not all(isinstance(item, dict) for item in (rubric, runtime, model)):
        raise VisualAuditServiceError("visual-audit runtime lock sections are incomplete")
    rubric_path = _verify_locked_file(root, str(rubric["path"]), str(rubric["sha256"]), int(rubric["size_bytes"]), "visual rubric")
    binary_path = _verify_locked_file(root, str(runtime["binary_path"]), str(runtime["binary_sha256"]), None, "llama-server")
    model_path = _verify_locked_file(root, str(model["path"]), str(model["sha256"]), None, "visual-audit model")
    mmproj_path = _verify_locked_file(root, str(model["mmproj_path"]), str(model["mmproj_sha256"]), None, "visual-audit vision projector")

    models_lock = _read_json(root / "dependencies/models.lock.json", "model lock")
    model_entry = next((item for item in models_lock.get("models", []) if isinstance(item, dict) and item.get("name") == model["name"]), None)
    if not isinstance(model_entry, dict):
        raise VisualAuditServiceError("visual-audit model is absent from the model lock")
    if model_entry.get("revision") != model.get("revision") or model_entry.get("sha256") != model.get("sha256") or model_entry.get("size_bytes") != model_path.stat().st_size:
        raise VisualAuditServiceError("visual-audit model does not match its pinned model-lock entry")
    return lock, rubric_path, binary_path, model_path, mmproj_path


def load_reference_set(private_root: str | Path, manifest_path: str | Path, *, schema_root: str | Path | None = None) -> dict[str, Any]:
    """Load and checksum-verify an approved private reference-set manifest."""

    root = Path(private_root).resolve()
    manifest = Path(manifest_path).resolve()
    try:
        manifest.relative_to(root)
    except ValueError as exc:
        raise VisualAuditServiceError("reference-set manifest is outside the private job root") from exc
    if not manifest.is_file():
        raise VisualAuditServiceError("approved visual reference-set manifest is missing")
    value = _read_json(manifest, "visual reference-set manifest")
    contract_root = project_root(schema_root) if schema_root is not None else project_root()
    issues = validate_schema(value, contract_root / VISUAL_REFERENCE_SCHEMA_PATH)
    if issues:
        raise VisualAuditServiceError("visual reference-set manifest does not satisfy its schema")
    reference_ids: set[str] = set()
    images: list[Path] = []
    for item in value["images"]:
        reference_id = item["reference_id"]
        if reference_id in reference_ids:
            raise VisualAuditServiceError("visual reference-set manifest contains duplicate reference ids")
        reference_ids.add(reference_id)
        image_path = relative_safe_path(root, item["path"])
        if not image_path.is_file():
            raise VisualAuditServiceError(f"approved visual reference image is missing: {item['path']}")
        if sha256_file(image_path) != item["sha256"]:
            raise VisualAuditServiceError(f"approved visual reference checksum mismatch: {item['path']}")
        try:
            from PIL import Image  # type: ignore

            with Image.open(image_path) as image:
                width, height = image.size
        except Exception as exc:
            raise VisualAuditServiceError(f"approved visual reference cannot be decoded: {type(exc).__name__}") from exc
        if (width, height) != (item["width"], item["height"]):
            raise VisualAuditServiceError(f"approved visual reference dimensions mismatch: {item['path']}")
        images.append(image_path)
    return {
        "id": value["reference_set_id"],
        "revision": value["revision"],
        "role": value["role"],
        "manifest_sha256": sha256_file(manifest),
        "sample_count": len(images),
        "images": images,
    }


def _image_data_url(path: Path, *, max_dimension: int = 768) -> str:
    try:
        from PIL import Image  # type: ignore

        with Image.open(path) as source:
            image = source.convert("RGB")
            image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            image.save(buffer, format="PNG", optimize=False)
    except Exception as exc:
        raise VisualAuditServiceError(f"visual-audit image encoding failed: {type(exc).__name__}") from exc
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return "data:image/png;base64," + encoded


def _post_json(url: str, payload: dict[str, Any], timeout: float = 180.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise VisualAuditServiceError(f"visual-audit llama-server request failed: {type(exc).__name__}") from exc
    if not isinstance(value, dict):
        raise VisualAuditServiceError("visual-audit llama-server returned a non-object response")
    return value


def _parse_model_response(response: dict[str, Any]) -> dict[str, Any]:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise VisualAuditServiceError("visual-audit model response has no assistant content") from exc
    if not isinstance(content, str):
        raise VisualAuditServiceError("visual-audit model response content is not text")
    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        raise VisualAuditServiceError("visual-audit model response is not strict JSON") from exc
    if not isinstance(value, dict) or set(value) != {"status", "scores", "human_readable_evidence"}:
        raise VisualAuditServiceError("visual-audit model response does not match the fixed response contract")
    if value["status"] not in {"PASS", "FAIL", "UNCERTAIN"}:
        raise VisualAuditServiceError("visual-audit model returned an invalid status")
    expected_names = {"hairline", "facial_hair", "accessories", "style"}
    if not isinstance(value["scores"], dict) or set(value["scores"]) != expected_names:
        raise VisualAuditServiceError("visual-audit model scores are incomplete or contain unexpected fields")
    if not isinstance(value["human_readable_evidence"], dict) or set(value["human_readable_evidence"]) != expected_names:
        raise VisualAuditServiceError("visual-audit human-readable evidence is incomplete or contains unexpected fields")
    for name in sorted(expected_names):
        score = value["scores"][name]
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0.0 <= float(score) <= 1.0:
            raise VisualAuditServiceError(f"visual-audit score is outside [0,1]: {name}")
        explanation = value["human_readable_evidence"][name]
        if not isinstance(explanation, str) or not explanation.strip() or len(explanation) > 2000:
            raise VisualAuditServiceError(f"visual-audit explanation is invalid: {name}")
    return {
        "status": value["status"],
        "scores": {name: float(value["scores"][name]) for name in sorted(expected_names)},
        "human_readable_evidence": {name: value["human_readable_evidence"][name].strip() for name in sorted(expected_names)},
    }


class VisualAuditProducer:
    """One-shot local producer for a separate visual-audit process."""

    def __init__(self, root: str | Path | None = None, *, port: int | None = None, auditor_process_id: str | None = None):
        self.root = project_root(root)
        self.lock, self.rubric_path, self.binary_path, self.model_path, self.mmproj_path_text = _load_runtime_lock(self.root)
        self.model = self.lock["model"]
        self.runtime = self.lock["runtime"]
        self.port = int(port if port is not None else self.runtime["port"])
        self.auditor_process_id = auditor_process_id or f"visual-auditor-{os.getpid()}"
        self.child: subprocess.Popen[bytes] | None = None

    @property
    def mmproj_path(self) -> Path:
        return Path(self.mmproj_path_text)

    def start(self) -> None:
        command = [
            str(self.binary_path),
            "--model", str(self.model_path),
            "--mmproj", str(self.mmproj_path),
            "--host", "127.0.0.1",
            "--port", str(self.port),
            "--ctx-size", str(self.runtime["context_size"]),
            "--n-predict", str(self.runtime["max_tokens"]),
            "--parallel", str(self.runtime["parallel_requests"]),
            "--temp", str(self.runtime["temperature"]),
            "--reasoning", "off",
            "--no-webui",
            "--offline",
        ]
        self.child = subprocess.Popen(command, cwd=self.root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 180.0
        while time.monotonic() < deadline:
            if self.child.poll() is not None:
                raise VisualAuditServiceError("visual-audit llama-server exited before health readiness")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/health", timeout=2.0) as response:
                    if response.status == 200:
                        return
            except OSError:
                time.sleep(0.5)
        raise VisualAuditServiceError("visual-audit llama-server health readiness timed out")

    def stop(self) -> None:
        if self.child is None or self.child.poll() is not None:
            return
        self.child.terminate()
        try:
            self.child.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.child.kill()
            self.child.wait(timeout=20)

    def produce(
        self,
        *,
        private_root: str | Path,
        source_path: str | Path,
        candidate_path: str | Path,
        reference_manifest: str | Path,
        producer_process_id: str,
        output_path: str | Path | None = None,
    ) -> dict[str, Any]:
        job_root = Path(private_root).resolve()
        source = relative_safe_path(job_root, source_path)
        candidate = relative_safe_path(job_root, candidate_path)
        if not source.is_file() or not candidate.is_file():
            raise VisualAuditServiceError("visual-audit source or candidate is missing")
        if self.auditor_process_id == producer_process_id:
            raise VisualAuditServiceError("visual-audit process id must differ from producer process id")
        reference = load_reference_set(job_root, reference_manifest, schema_root=self.root)
        source_sha256 = sha256_file(source)
        candidate_sha256 = sha256_file(candidate)
        content = [{"type": "text", "text": self.rubric_path.read_text(encoding="utf-8")}, {"type": "image_url", "image_url": {"url": _image_data_url(source)}}]
        content.append({"type": "image_url", "image_url": {"url": _image_data_url(candidate)}})
        content.extend({"type": "image_url", "image_url": {"url": _image_data_url(path)}} for path in reference["images"])
        payload = {
            "model": self.model["name"],
            "messages": [{"role": "user", "content": content}],
            "max_tokens": int(self.runtime["max_tokens"]),
            "temperature": float(self.runtime["temperature"]),
            "seed": 0,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        self.start()
        try:
            model_response = _parse_model_response(_post_json(f"http://127.0.0.1:{self.port}/v1/chat/completions", payload))
        finally:
            self.stop()
        record = {
            "schema_version": "1.0.0",
            "status": model_response["status"],
            "auditor": {
                "process_id": self.auditor_process_id,
                "independent_from_producer": True,
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
            },
            "model": {
                "name": self.model["name"],
                "revision": self.model["revision"],
                "artifact_sha256": self.model["sha256"],
            },
            "reference_set": {
                "id": reference["id"],
                "role": reference["role"],
                "manifest_sha256": reference["manifest_sha256"],
                "sample_count": reference["sample_count"],
            },
            "source_sha256": source_sha256,
            "candidate_sha256": candidate_sha256,
            "scores": model_response["scores"],
            "human_readable_evidence": model_response["human_readable_evidence"],
            "notes": f"fixed_rubric_sha256={sha256_file(self.rubric_path)}; reference_set_revision={reference['revision']}",
        }
        issues = validate_schema(record, self.root / VISUAL_EVIDENCE_SCHEMA_PATH)
        if issues:
            raise VisualAuditServiceError("produced visual-audit evidence failed its schema")
        destination = relative_safe_path(job_root, output_path or "evidence/audit/visual_audit.json")
        atomic_json_write(destination, record)
        return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Produce private, hash-bound visual-audit evidence using the pinned local rubric runtime.")
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--reference-manifest", type=Path, required=True)
    parser.add_argument("--producer-process-id", required=True)
    parser.add_argument("--auditor-process-id", default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args(argv)
    try:
        producer = VisualAuditProducer(port=args.port, auditor_process_id=args.auditor_process_id)
        record = producer.produce(private_root=args.private_root, source_path=args.source, candidate_path=args.candidate, reference_manifest=args.reference_manifest, producer_process_id=args.producer_process_id, output_path=args.output)
    except VisualAuditServiceError as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}), file=sys.stderr)
        return 20
    print(json.dumps(record, indent=2, ensure_ascii=False))
    return 0 if record["status"] in {"PASS", "FAIL"} else 43


if __name__ == "__main__":
    raise SystemExit(main())
