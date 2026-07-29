from __future__ import annotations

import argparse
import base64
import binascii
import io
import json
import mimetypes
import os
import re
import secrets
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from ..constants import ExitCode
from ..controller import JobController
from ..comfy_client import ComfyCloudClient, ComfyTransportError, LoopbackComfyClient
from ..constants import DEPENDENCY_LOCK_VERSION, PROFILE_LIMITS, WORKFLOW_VERSION
from ..preflight import collect_preflight
from ..util import atomic_json_write, canonical_hash, project_root, relative_safe_path, sha256_file
from ..workflow_validation import validate_workflow_file


TOOL_NAMES = (
    "portrait_health",
    "portrait_capabilities",
    "portrait_inventory",
    "portrait_validate_workflow",
    "portrait_import_workflow",
    "portrait_upload_source",
    "portrait_submit_job",
    "portrait_job_status",
    "portrait_watch_job",
    "portrait_cancel_job",
    "portrait_fetch_outputs",
    "portrait_history",
    "portrait_free_memory",
)


class AdapterError(RuntimeError):
    def __init__(self, code: ExitCode, message: str, *, stage: str = "ADAPTER", retryable: bool | None = None, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.stage = stage
        self.retryable = retryable if retryable is not None else code in {ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED, ExitCode.OUT_OF_MEMORY, ExitCode.GENERATION_FAILED}
        self.details = details or {}

    def as_error(self) -> dict[str, Any]:
        return {
            "ok": False,
            "error": {
                "code": self.code.name,
                "message": str(self),
                "retryable": self.retryable,
                "stage": self.stage,
                "details": {"exit_code": int(self.code), **self.details},
            },
        }


class PortraitMcpService:
    def __init__(self, root: str | Path | None = None, *, remote: bool = False):
        self.root = project_root(root)
        self.remote = remote
        self.controller = JobController(self.root)
        self.registered_dir = self.root / "evidence" / "registered_workflows"
        self._worker_lock = threading.Lock()
        self._workers: dict[str, threading.Thread] = {}

    def _check_remote_auth(self, token: str | None) -> None:
        if not self.remote:
            return
        expected = os.environ.get("PORTRAIT_GATEWAY_TOKEN")
        if not expected or not token or not secrets.compare_digest(token, expected):
            raise AdapterError(ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED, "remote adapter authentication failed", retryable=False, stage="AUTHENTICATING_REMOTE_CALL")

    def authenticate(self, token: str | None) -> None:
        """Authorize a gateway request without performing a ComfyUI call."""

        self._check_remote_auth(token)

    @staticmethod
    def _profile(params: dict[str, Any]) -> str | None:
        profile = params.get("profile")
        if profile is not None and profile not in PROFILE_LIMITS:
            raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, f"unknown execution profile: {profile}")
        return profile

    @staticmethod
    def _queue_depth(payload: Any) -> int | None:
        if not isinstance(payload, dict):
            return None
        running = payload.get("queue_running", [])
        pending = payload.get("queue_pending", [])
        return len(running) + len(pending) if isinstance(running, list) and isinstance(pending, list) else None

    def _runtime_probe(self, profile: str | None = None) -> dict[str, Any]:
        cloud_profile = profile in {"human_full_power_gpu", "agent_full_power_gpu"}
        try:
            client = ComfyCloudClient(timeout=3.0) if cloud_profile else LoopbackComfyClient(timeout=3.0)
        except ComfyTransportError as exc:
            return {"status": "BLOCKED", "error_code": exc.code.name, "message": str(exc), "binding": "https://cloud.comfy.org" if cloud_profile else "http://127.0.0.1:8188"}
        try:
            stats = client.health()
            inventory = client.inventory()
            queue = client.queue()
        except ComfyTransportError as exc:
            return {"status": "BLOCKED", "error_code": exc.code.name, "message": str(exc), "binding": "https://cloud.comfy.org" if cloud_profile else "http://127.0.0.1:8188"}
        return {"status": "PASS", "binding": "https://cloud.comfy.org" if cloud_profile else "http://127.0.0.1:8188", "system_stats": stats.payload, "queue": queue.payload, "object_info": inventory.payload, "queue_depth": self._queue_depth(queue.payload), "transport": "comfy_cloud_api" if cloud_profile else "loopback"}

    def _workflow_path(self, workflow_id: str, api: bool = True) -> Path:
        paths = {
            "human_local_mac_16gb": "workflows/human/local_mac_16gb/human_local_mac_16gb.api.json",
            "human_local_nvidia_16gb": "workflows/human/local_nvidia_16gb/human_local_nvidia_16gb.api.json",
            "human_full_power_gpu": "workflows/human/full_power_gpu/human_full_power_gpu.api.json",
            "agent_local_mac_16gb": "workflows/agent/local_mac_16gb/agent_local_mac_16gb.api.json",
            "agent_local_nvidia_16gb": "workflows/agent/local_nvidia_16gb/agent_local_nvidia_16gb.api.json",
            "agent_full_power_gpu": "workflows/agent/full_power_gpu/agent_full_power_gpu.api.json",
        }
        if workflow_id not in paths:
            raise AdapterError(ExitCode.WORKFLOW_INVALID, f"unknown workflow id: {workflow_id}")
        return self.root / paths[workflow_id]

    def call(self, name: str, params: dict[str, Any] | None = None, *, auth_token: str | None = None) -> dict[str, Any]:
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "tool params must be a JSON object", stage="ADAPTER")
        self._check_remote_auth(auth_token)
        method: Callable[[dict[str, Any]], dict[str, Any]] | None = getattr(self, f"_{name}", None)
        if name not in TOOL_NAMES or method is None:
            raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, f"unsupported project-owned tool: {name}")
        try:
            return method(params)
        except AdapterError:
            raise
        except Exception as exc:
            raise AdapterError(ExitCode.INTERNAL_ERROR, f"adapter operation failed: {type(exc).__name__}: {exc}") from exc

    def _portrait_health(self, params: dict[str, Any]) -> dict[str, Any]:
        profile = self._profile(params)
        report = collect_preflight(self.root, profile=profile)
        runtime = self._runtime_probe(profile)
        status = "PASS" if report["status"] == "PASS" and runtime["status"] == "PASS" else "BLOCKED"
        return {"status": status, "adapter": "project_owned", "remote": self.remote, "raw_comfyui_exposed": False, "comfyui_binding": "http://127.0.0.1:8188", "comfyui": runtime, "blockers": report["blockers"] + ([] if runtime["status"] == "PASS" else ["loopback ComfyUI health is unavailable"]), "workflow_version": WORKFLOW_VERSION, "dependency_lock_version": DEPENDENCY_LOCK_VERSION, "profile": report.get("profile"), "queue_depth": runtime.get("queue_depth")}

    def _portrait_capabilities(self, params: dict[str, Any]) -> dict[str, Any]:
        profile = self._profile(params)
        report = collect_preflight(self.root, profile=profile)
        runtime = self._runtime_probe(profile)
        node_classes = sorted(runtime.get("object_info", {})) if isinstance(runtime.get("object_info"), dict) else []
        return {"profiles": list(PROFILE_LIMITS), "local_comfyui_binding": "http://127.0.0.1:8188", "cloud_binding": "https://cloud.comfy.org", "raw_comfyui_public": False, "remote_transport": "authenticated_comfy_cloud_api_or_project_gateway", "first_party_local_mcp_parity": False, "available_routes": ["/api/object_info", "/api/upload/image", "/api/prompt", "/api/job/{prompt_id}/status", "/api/view"], "runtime": runtime, "node_classes": node_classes, "hardware": report.get("hardware"), "gates": {gate["name"]: gate["status"] for gate in report["gates"]}, "unresolved_limitations": report["blockers"] + ([] if runtime["status"] == "PASS" else ["selected ComfyUI route health is unavailable"])}

    def _portrait_inventory(self, params: dict[str, Any]) -> dict[str, Any]:
        model_lock = json.loads((self.root / "dependencies" / "models.lock.json").read_text(encoding="utf-8"))
        node_dir = self.root / "src" / "comfyui_hoi4_portrait_nodes"
        lock = json.loads((self.root / "dependencies" / "custom_nodes.lock.json").read_text(encoding="utf-8"))
        model_files = []
        if (self.root / "models").is_dir():
            for path in sorted((self.root / "models").rglob("*")):
                if path.is_file():
                    model_files.append({"relative_path": str(path.relative_to(self.root)), "size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
        project_classes: dict[str, str] = {}
        try:
            from comfyui_hoi4_portrait_nodes import NODE_CLASS_MAPPINGS
            for name, node_class in NODE_CLASS_MAPPINGS.items():
                project_classes[name] = canonical_hash(node_class.INPUT_TYPES())
        except Exception:
            project_classes = {}
        report = collect_preflight(self.root, profile=self._profile(params))
        registry = json.loads((self.root / "config" / "background_registry.json").read_text(encoding="utf-8")) if (self.root / "config" / "background_registry.json").is_file() else {}
        thresholds = json.loads((self.root / "config" / "identity_thresholds.json").read_text(encoding="utf-8")) if (self.root / "config" / "identity_thresholds.json").is_file() else {}
        return {"status": report["status"], "custom_nodes": lock.get("custom_nodes", []), "project_node_classes": project_classes, "locked_models": model_lock["models"], "installed_model_files": model_files, "background_registry": {"status": registry.get("registry_status"), "entries": registry.get("backgrounds", [])}, "threshold_registry": {"status": thresholds.get("status"), "thresholds_id": thresholds.get("thresholds_id")}, "missing_dependencies": report["blockers"]}

    def _portrait_validate_workflow(self, params: dict[str, Any]) -> dict[str, Any]:
        workflow_id = str(params.get("workflow_id", ""))
        path = self._workflow_path(workflow_id)
        if not path.is_file():
            raise AdapterError(ExitCode.WORKFLOW_INVALID, f"workflow artifact missing: {workflow_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        nodes = data.get("_meta", {})
        ui_path = path.with_name(path.name.replace(".api.json", ".json"))
        structural = validate_workflow_file(workflow_id, ui_path, path, self.root)
        nodes = data.get("_meta", {})
        report = collect_preflight(self.root, profile=workflow_id)
        return {"workflow_id": workflow_id, "json_sha256": sha256_file(path), "ui_sha256": sha256_file(ui_path), "graph_spec_version": nodes.get("graph_spec_version"), "autoprompter": nodes.get("autoprompter"), "prompt_source": nodes.get("prompt_source"), "structural_valid": structural["structural_status"] == "PASS", "structural_issues": structural["issues"], "runtime_status": report["status"], "blockers": report["blockers"]}

    def _portrait_import_workflow(self, params: dict[str, Any]) -> dict[str, Any]:
        workflow_id = str(params.get("workflow_id", ""))
        path = self._workflow_path(workflow_id)
        ui_path = path.with_name(path.name.replace(".api.json", ".json"))
        structural = validate_workflow_file(workflow_id, ui_path, path, self.root)
        if structural["structural_status"] != "PASS":
            raise AdapterError(ExitCode.WORKFLOW_INVALID, "workflow failed structural validation", stage="WORKFLOW_VALIDATED", details={"issues": structural["issues"]})
        expected = str(params.get("sha256", ""))
        actual = sha256_file(path)
        if not expected:
            raise AdapterError(ExitCode.MODEL_CHECKSUM_MISMATCH, "API workflow SHA-256 is required", stage="WORKFLOW_VALIDATED")
        if expected != actual:
            raise AdapterError(ExitCode.MODEL_CHECKSUM_MISMATCH, "workflow checksum mismatch", stage="WORKFLOW_VALIDATED", details={"expected_sha256": expected, "actual_sha256": actual})
        record = {"workflow_id": workflow_id, "path": str(path.relative_to(self.root)), "sha256": actual, "registered_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}
        atomic_json_write(self.registered_dir / f"{workflow_id}.json", record)
        return record

    def _portrait_upload_source(self, params: dict[str, Any]) -> dict[str, Any]:
        job_id = str(params.get("job_id", ""))
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,63}", job_id):
            raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "job_id does not satisfy the job contract", stage="JOB_ACCEPTED")
        try:
            max_bytes = min(max(1, int(params.get("max_bytes", 25 * 1024 * 1024))), 25 * 1024 * 1024)
        except (TypeError, ValueError) as exc:
            raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "max_bytes must be an integer") from exc
        source: Path | None = None
        source_bytes: bytes | None = None
        if params.get("source_bytes_base64") is not None:
            encoded = params.get("source_bytes_base64")
            if not isinstance(encoded, str):
                raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "source_bytes_base64 must be a string")
            if len(encoded) > (max_bytes * 4 // 3) + 4:
                raise AdapterError(ExitCode.SOURCE_INVALID, "source upload exceeds the configured size limit")
            try:
                source_bytes = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise AdapterError(ExitCode.SOURCE_INVALID, "source upload is not valid base64") from exc
            if not source_bytes:
                raise AdapterError(ExitCode.SOURCE_INVALID, "source upload is empty")
            if len(source_bytes) > max_bytes:
                raise AdapterError(ExitCode.SOURCE_INVALID, "source upload exceeds the configured size limit", details={"size_bytes": len(source_bytes), "max_bytes": max_bytes})
            source_name = str(params.get("filename", "source.png"))
            if not source_name or Path(source_name).name != source_name or source_name in {".", ".."}:
                raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "source filename must be a simple filename")
        else:
            source = Path(str(params.get("source_path", ""))).expanduser().resolve()
            if not source.is_file():
                raise AdapterError(ExitCode.SOURCE_INVALID, "source path does not exist")
            if source.stat().st_size > max_bytes:
                raise AdapterError(ExitCode.SOURCE_INVALID, "source upload exceeds the configured size limit", details={"size_bytes": source.stat().st_size, "max_bytes": max_bytes})
            source_name = source.name
        source_format = None
        try:
            from PIL import Image  # type: ignore
        except ImportError as exc:
            raise AdapterError(ExitCode.DEPENDENCY_MISSING, "Pillow is required for safe source upload validation") from exc
        try:
            if source_bytes is not None:
                probe = io.BytesIO(source_bytes)
                image_context = Image.open(probe)
            else:
                image_context = Image.open(source)
            with image_context as image:
                image.verify()
                source_format = image.format
        except Exception as exc:
            raise AdapterError(ExitCode.SOURCE_INVALID, f"source is not a supported, decodable image: {type(exc).__name__}") from exc
        if source_format not in {"PNG", "JPEG", "WEBP", "TIFF"}:
            raise AdapterError(ExitCode.SOURCE_INVALID, f"unsupported source image format: {source_format}")
        job_root = relative_safe_path(self.root / "jobs", job_id)
        target = relative_safe_path(job_root, f"source/original/{source_name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("wb", dir=target.parent, delete=False) as tmp:
            if source_bytes is not None:
                tmp.write(source_bytes)
            else:
                with source.open("rb") as handle:
                    while chunk := handle.read(1024 * 1024):
                        tmp.write(chunk)
            temporary = Path(tmp.name)
        incoming_sha = sha256_file(temporary)
        try:
            if target.is_file():
                existing_sha = sha256_file(target)
                if existing_sha != incoming_sha:
                    raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "source upload conflicts with existing bytes for this job and filename", stage="JOB_ACCEPTED")
                temporary.unlink()
            else:
                os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()
        return {"job_id": job_id, "relative_path": str(target.relative_to(job_root)), "size_bytes": target.stat().st_size, "mime_type": mimetypes.types_map.get(Path(source_name).suffix.casefold(), "application/octet-stream"), "format": source_format, "sha256": incoming_sha}

    def _portrait_submit_job(self, params: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(params.get("job"), dict):
            raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "job object is required", stage="JOB_ACCEPTED")
        result = self.controller.submit(dict(params["job"]))
        job_id = str(result.output.get("job_id", result.job_root.name))
        status = result.output.get("status", "SUBMITTED")
        if status == "SUBMITTED":
            with self._worker_lock:
                worker = self._workers.get(job_id)
                if worker is None or not worker.is_alive():
                    worker = threading.Thread(target=self._run_worker, args=(job_id,), name=f"portrait-job-{job_id}", daemon=True)
                    self._workers[job_id] = worker
                    worker.start()
        return {"job_id": job_id, "status": status, "job_root": str(result.job_root.relative_to(self.root)), "output": result.output}

    def _run_worker(self, job_id: str) -> None:
        try:
            self.controller.run(job_id)
        finally:
            with self._worker_lock:
                self._workers.pop(job_id, None)

    def _portrait_job_status(self, params: dict[str, Any]) -> dict[str, Any]:
        return self.controller.status(self._required_job_id(params))

    def _portrait_watch_job(self, params: dict[str, Any]) -> dict[str, Any]:
        job_id = self._required_job_id(params)
        try:
            timeout = max(0.0, min(30.0, float(params.get("timeout_seconds", 0.0))))
        except (TypeError, ValueError) as exc:
            raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "timeout_seconds must be a number") from exc
        deadline = time.monotonic() + timeout
        status = self.controller.status(job_id)
        while timeout > 0 and time.monotonic() < deadline and status.get("state") not in {"COMPLETED", "FAILED", "CANCELED", "BLOCKED", "NEEDS_REVIEW"}:
            time.sleep(min(0.25, max(0.01, deadline - time.monotonic())))
            status = self.controller.status(job_id)
        return status

    def _portrait_cancel_job(self, params: dict[str, Any]) -> dict[str, Any]:
        job_id = self._required_job_id(params)
        reason = str(params.get("reason", "caller requested cancellation"))
        try:
            return self.controller.cancel(job_id, reason=reason, caller=str(params.get("caller", "adapter")))
        except ValueError as exc:
            raise AdapterError(ExitCode.SOURCE_INVALID, str(exc), stage="JOB_ACCEPTED") from exc

    def _portrait_fetch_outputs(self, params: dict[str, Any]) -> dict[str, Any]:
        job_id = self._required_job_id(params)
        job_root = relative_safe_path(self.root / "jobs", job_id)
        output_path = job_root / "output.json"
        if not output_path.is_file():
            raise AdapterError(ExitCode.SOURCE_INVALID, "job output is unavailable")
        output = json.loads(output_path.read_text(encoding="utf-8"))
        if output.get("status") != "SUCCEEDED":
            raise AdapterError(ExitCode.INTEGRATION_BLOCKED, "outputs are not available until the job succeeds")
        checksum_names = {"final_png": "png", "final_dds": "dds"}
        artifacts = []
        for key, value in (("final_png", output.get("final_png")), ("final_dds", output.get("final_dds"))):
            if not value:
                continue
            try:
                artifact = relative_safe_path(job_root, value)
            except ValueError as exc:
                raise AdapterError(ExitCode.INTEGRATION_BLOCKED, "output manifest path escapes the job root") from exc
            expected = output.get("final_checksums", {}).get(checksum_names[key])
            actual = sha256_file(artifact) if artifact.is_file() else None
            if not artifact.is_file() or actual != expected:
                raise AdapterError(ExitCode.INTEGRATION_BLOCKED, "output checksum verification failed", details={"artifact_id": key, "expected_sha256": expected, "actual_sha256": actual})
            artifacts.append({"artifact_id": key, "relative_path": str(artifact.relative_to(job_root)), "mime_type": "image/png" if key == "final_png" else "image/vnd-ms.dds", "size_bytes": artifact.stat().st_size, "sha256": actual})
        return {"job_id": job_id, "artifacts": artifacts}

    def _portrait_history(self, params: dict[str, Any]) -> dict[str, Any]:
        jobs: list[dict[str, Any]] = []
        if (self.root / "jobs").is_dir():
            for status_path in sorted((self.root / "jobs").glob("*/status.json")):
                try:
                    jobs.append(json.loads(status_path.read_text(encoding="utf-8")))
                except json.JSONDecodeError:
                    continue
        try:
            limit = max(1, min(100, int(params.get("limit", 25))))
        except (TypeError, ValueError) as exc:
            raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "history limit must be an integer") from exc
        return {"jobs": jobs[-limit:], "count": len(jobs)}

    @staticmethod
    def _required_job_id(params: dict[str, Any]) -> str:
        job_id = params.get("job_id")
        if not isinstance(job_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,63}", job_id):
            raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "job_id does not satisfy the job contract", stage="JOB_ACCEPTED")
        return job_id

    def _portrait_free_memory(self, params: dict[str, Any]) -> dict[str, Any]:
        client = LoopbackComfyClient(timeout=30.0)
        before = self._runtime_probe()
        if before["status"] != "PASS":
            raise AdapterError(ExitCode.DEPENDENCY_MISSING, "ComfyUI free-memory route is unavailable", stage="FREEING_MEMORY", details=before)
        try:
            response = client.free_memory()
        except ComfyTransportError as exc:
            raise AdapterError(exc.code, str(exc), stage="FREEING_MEMORY") from exc
        after = self._runtime_probe()
        return {"status": "PASS" if response.status == 200 else "BLOCKED", "binding": "loopback-only", "before": before, "free_response": response.payload, "after": after}


class _RequestHandler(BaseHTTPRequestHandler):
    service: PortraitMcpService
    max_body_bytes = 40 * 1024 * 1024

    def do_POST(self):  # noqa: N802
        body: Any = None
        try:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except (TypeError, ValueError) as exc:
                raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "Content-Length must be an integer") from exc
            if length <= 0 or length > self.max_body_bytes:
                raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "request body is missing or exceeds the adapter limit")
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(body, dict):
                raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "JSON-RPC request must be an object")
            token = self.headers.get("Authorization", "").removeprefix("Bearer ") or None
            result = self.service.call(body.get("method", ""), body.get("params", {}), auth_token=token)
            payload = {"jsonrpc": "2.0", "id": body.get("id"), "result": result}
            code = 200
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            error = AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "request body is not valid UTF-8 JSON")
            payload = {"jsonrpc": "2.0", "id": None, "result": error.as_error()}
            code = 400
        except AdapterError as exc:
            request_id = body.get("id") if isinstance(body, dict) else None
            payload = {"jsonrpc": "2.0", "id": request_id, "result": exc.as_error()}
            code = 403 if exc.code == ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED else 400
        except Exception as exc:
            payload = {"jsonrpc": "2.0", "id": None, "result": AdapterError(ExitCode.INTERNAL_ERROR, "adapter operation failed").as_error()}
            code = 500
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:
        return


def serve_stdio(service: PortraitMcpService) -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        request: Any = {}
        try:
            if len(line.encode("utf-8")) > _RequestHandler.max_body_bytes:
                raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "request line exceeds the adapter limit")
            request = json.loads(line)
            if not isinstance(request, dict):
                raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "JSON-RPC request must be an object")
            result = service.call(request.get("method", ""), request.get("params", {}))
            response = {"jsonrpc": "2.0", "id": request.get("id"), "result": result}
        except (UnicodeDecodeError, json.JSONDecodeError):
            error = AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "request line is not valid JSON")
            response = {"jsonrpc": "2.0", "id": None, "result": error.as_error()}
        except AdapterError as exc:
            request_id = request.get("id") if isinstance(request, dict) else None
            response = {"jsonrpc": "2.0", "id": request_id, "result": exc.as_error()}
        except Exception as exc:
            response = {"jsonrpc": "2.0", "id": None, "result": AdapterError(ExitCode.INTERNAL_ERROR, "adapter operation failed").as_error()}
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the project-owned portrait adapter.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--stdio", action="store_true", default=False)
    parser.add_argument("--remote-http", action="store_true", default=False)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if args.remote_http and args.host in {"127.0.0.1", "localhost"}:
        # Localhost is valid for a development gateway; a public gateway must
        # explicitly choose a non-loopback bind and provide a token.
        pass
    service = PortraitMcpService(args.root, remote=args.remote_http)
    if args.remote_http:
        if not os.environ.get("PORTRAIT_GATEWAY_TOKEN"):
            print("PORTRAIT_GATEWAY_TOKEN is required for remote HTTP mode", file=sys.stderr)
            return int(ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED)
        _RequestHandler.service = service
        server = ThreadingHTTPServer((args.host, args.port), _RequestHandler)
        server.serve_forever()
        return 0
    return serve_stdio(service)


if __name__ == "__main__":
    raise SystemExit(main())
