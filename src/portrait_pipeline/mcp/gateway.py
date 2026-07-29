from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import re
import secrets
import signal
import sys
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ..constants import ExitCode
from ..util import atomic_json_write, is_sha256, project_root, relative_safe_path, sha256_file
from .adapter import AdapterError, PortraitMcpService


UPLOAD_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")
JOB_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp", "image/tiff"}
DEFAULT_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_GATEWAY_BODY_BYTES = 40 * 1024 * 1024


class GatewayConflict(AdapterError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(ExitCode.INPUT_SCHEMA_INVALID, message, retryable=False, stage="GATEWAY_IDEMPOTENCY", details=details)


class PortraitGateway:
    """Narrow authenticated REST gateway for the remote Comfy Cloud route.

    The gateway deliberately exposes no raw ComfyUI endpoint and accepts only
    the registered full-power workflow through the validated job contract.
    """

    def __init__(self, root: str | Path | None = None, *, service: PortraitMcpService | None = None):
        self.root = project_root(root)
        self.service = service or PortraitMcpService(self.root, remote=True)
        self.max_upload_bytes = self._bounded_int("PORTRAIT_MAX_UPLOAD_BYTES", DEFAULT_MAX_UPLOAD_BYTES, 1, DEFAULT_MAX_UPLOAD_BYTES)
        self.max_active_jobs = self._bounded_int("PORTRAIT_MAX_ACTIVE_JOBS", 1, 1, 8)
        self.max_requests_per_minute = self._bounded_int("PORTRAIT_MAX_REQUESTS_PER_MINUTE", 120, 1, 600)
        self._last_request = time.monotonic()
        self._rate_lock = threading.Lock()
        self._rate_window_start = time.monotonic()
        self._rate_counts: dict[str, int] = {}

    @staticmethod
    def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
        try:
            value = int(os.environ.get(name, default))
        except (TypeError, ValueError):
            value = default
        return max(minimum, min(maximum, value))

    def touch(self) -> None:
        self._last_request = time.monotonic()

    def rate_limit(self, handler: BaseHTTPRequestHandler) -> None:
        client = str(handler.client_address[0] if handler.client_address else "unknown")
        now = time.monotonic()
        with self._rate_lock:
            if now - self._rate_window_start >= 60:
                self._rate_window_start = now
                self._rate_counts.clear()
            count = self._rate_counts.get(client, 0) + 1
            self._rate_counts[client] = count
        if count > self.max_requests_per_minute:
            raise AdapterError(ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED, "gateway rate limit exceeded", retryable=True, stage="RATE_LIMITING")

    @staticmethod
    def _token(handler: BaseHTTPRequestHandler) -> str | None:
        value = handler.headers.get("Authorization", "")
        scheme, separator, token = value.partition(" ")
        return token.strip() if separator and scheme.casefold() == "bearer" and token.strip() else None

    def authenticate(self, handler: BaseHTTPRequestHandler) -> None:
        self.service.authenticate(self._token(handler))

    @staticmethod
    def _required_header(handler: BaseHTTPRequestHandler, name: str) -> str:
        value = handler.headers.get(name)
        if not value or len(value) > 128 or any(ord(char) < 33 or ord(char) > 126 for char in value):
            raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, f"{name} header is required and must be printable ASCII")
        return value

    def _content_length(self, handler: BaseHTTPRequestHandler, *, maximum: int) -> int:
        try:
            value = int(handler.headers.get("Content-Length", "-1"))
        except (TypeError, ValueError) as exc:
            raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "Content-Length must be an integer") from exc
        if value < 0 or value > maximum:
            raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "request body is missing or exceeds the configured limit")
        return value

    def _json_body(self, handler: BaseHTTPRequestHandler, *, maximum: int = MAX_GATEWAY_BODY_BYTES) -> dict[str, Any]:
        length = self._content_length(handler, maximum=maximum)
        if length == 0:
            raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "JSON request body is required")
        try:
            payload = json.loads(handler.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "request body is not valid UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "request body must be a JSON object")
        return payload

    def _safe_job_id(self, value: Any) -> str:
        if not isinstance(value, str) or not JOB_ID_PATTERN.fullmatch(value):
            raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "job_id does not satisfy the job contract", stage="JOB_ACCEPTED")
        return value

    def _safe_upload_id(self, value: Any) -> str:
        if not isinstance(value, str) or not UPLOAD_ID_PATTERN.fullmatch(value):
            raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "upload_id is invalid")
        return value

    def _upload_root(self, job_id: str) -> Path:
        path = relative_safe_path(self.root / "jobs", job_id) / "uploads"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _upload_metadata_path(self, job_id: str, upload_id: str) -> Path:
        return relative_safe_path(self._upload_root(job_id), f"{upload_id}.json")

    def _read_upload(self, job_id: str, upload_id: str) -> dict[str, Any]:
        path = self._upload_metadata_path(job_id, upload_id)
        if not path.is_file():
            raise AdapterError(ExitCode.SOURCE_INVALID, "upload id does not exist")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AdapterError(ExitCode.SOURCE_INVALID, "upload metadata is unreadable") from exc
        if not isinstance(data, dict) or data.get("upload_id") != upload_id or data.get("job_id") != job_id:
            raise AdapterError(ExitCode.SOURCE_INVALID, "upload metadata is invalid")
        return data

    def _find_idempotent_upload(self, job_id: str, key: str) -> dict[str, Any] | None:
        upload_root = self._upload_root(job_id)
        for path in sorted(upload_root.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict) and data.get("idempotency_key") == key:
                return data
        return None

    def create_upload(self, handler: BaseHTTPRequestHandler, body: dict[str, Any]) -> dict[str, Any]:
        key = self._required_header(handler, "Idempotency-Key")
        job_id = self._safe_job_id(body.get("job_id"))
        filename = body.get("filename")
        if not isinstance(filename, str) or not filename or Path(filename).name != filename or filename in {".", ".."}:
            raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "filename must be a simple filename")
        mime_type = str(body.get("mime_type") or mimetypes.types_map.get(Path(filename).suffix.casefold(), ""))
        if mime_type not in ALLOWED_MIME_TYPES:
            raise AdapterError(ExitCode.SOURCE_INVALID, "upload MIME type is not an allowed image type")
        try:
            size_bytes = int(body.get("size_bytes"))
        except (TypeError, ValueError) as exc:
            raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "size_bytes must be an integer") from exc
        if size_bytes <= 0 or size_bytes > self.max_upload_bytes:
            raise AdapterError(ExitCode.SOURCE_INVALID, "upload size exceeds the configured limit")
        digest = body.get("sha256")
        if not is_sha256(digest):
            raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "sha256 must be a lowercase SHA-256")
        existing = self._find_idempotent_upload(job_id, key)
        if existing is not None:
            comparable = {name: existing.get(name) for name in ("filename", "mime_type", "size_bytes", "sha256")}
            requested = {"filename": filename, "mime_type": mime_type, "size_bytes": size_bytes, "sha256": digest}
            if comparable != requested:
                raise GatewayConflict("Idempotency-Key was reused with different upload metadata")
            return existing
        upload_id = f"upload-{secrets.token_hex(16)}"
        record = {
            "schema_version": "1.0.0",
            "upload_id": upload_id,
            "job_id": job_id,
            "idempotency_key": key,
            "filename": filename,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "sha256": digest,
            "state": "CREATED",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": "gateway_metadata_only_until_put",
        }
        atomic_json_write(self._upload_metadata_path(job_id, upload_id), record)
        return record

    def put_upload(self, handler: BaseHTTPRequestHandler, upload_id: str) -> dict[str, Any]:
        upload_id = self._safe_upload_id(upload_id)
        job_id = self._safe_job_id(handler.headers.get("X-Portrait-Job-Id"))
        record = self._read_upload(job_id, upload_id)
        if record.get("state") == "UPLOADED":
            return record
        expected_size = int(record["size_bytes"])
        length = self._content_length(handler, maximum=self.max_upload_bytes)
        if length != expected_size:
            raise AdapterError(ExitCode.SOURCE_INVALID, "upload byte count does not match metadata")
        content_type = handler.headers.get("Content-Type", "").split(";", 1)[0].strip().casefold()
        if content_type and content_type not in ALLOWED_MIME_TYPES:
            raise AdapterError(ExitCode.SOURCE_INVALID, "upload MIME type is not allowed")
        payload = handler.rfile.read(length)
        actual = hashlib.sha256(payload).hexdigest()
        supplied = handler.headers.get("Content-SHA256")
        if supplied and supplied != actual:
            raise AdapterError(ExitCode.SOURCE_INVALID, "Content-SHA256 does not match upload bytes")
        if actual != record.get("sha256"):
            raise AdapterError(ExitCode.MODEL_CHECKSUM_MISMATCH, "source upload checksum mismatch")
        result = self.service.call(
            "portrait_upload_source",
            {
                "job_id": job_id,
                "filename": record["filename"],
                "max_bytes": self.max_upload_bytes,
                "source_bytes_base64": base64.b64encode(payload).decode("ascii"),
            },
            auth_token=self._token(handler),
        )
        record.update({"state": "UPLOADED", "source_result": result, "uploaded_at": datetime.now(timezone.utc).isoformat()})
        atomic_json_write(self._upload_metadata_path(job_id, upload_id), record)
        return record

    def _active_job_count(self) -> int:
        jobs_root = self.root / "jobs"
        if not jobs_root.is_dir():
            return 0
        count = 0
        for path in jobs_root.glob("*/status.json"):
            try:
                state = json.loads(path.read_text(encoding="utf-8")).get("state")
            except (OSError, json.JSONDecodeError):
                continue
            if state in {"SUBMITTED", "RUNNING"}:
                count += 1
        return count

    def submit_job(self, handler: BaseHTTPRequestHandler, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        key = self._required_header(handler, "Idempotency-Key")
        job = body.get("job")
        if not isinstance(job, dict):
            raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "job object is required", stage="JOB_ACCEPTED")
        job = dict(job)
        job_id = self._safe_job_id(job.get("job_id"))
        if job.get("execution_profile") != "agent_full_power_gpu":
            raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "remote gateway accepts only agent_full_power_gpu jobs")
        upload_id = self._safe_upload_id(body.get("source_upload_id"))
        upload = self._read_upload(job_id, upload_id)
        if upload.get("state") != "UPLOADED":
            raise AdapterError(ExitCode.SOURCE_INVALID, "source upload is not complete")
        job["source_image_path"] = f"jobs/{job_id}/{upload['source_result']['relative_path']}"
        job_root = relative_safe_path(self.root / "jobs", job_id)
        existing_status = job_root / "status.json"
        if self._active_job_count() >= self.max_active_jobs and not (existing_status.is_file() and json.loads(existing_status.read_text(encoding="utf-8")).get("state") in {"COMPLETED", "FAILED", "CANCELED", "BLOCKED", "NEEDS_REVIEW"}):
            raise AdapterError(ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED, "maximum active GPU job limit has been reached", retryable=True, stage="JOB_ACCEPTED")
        result = self.service.call("portrait_submit_job", {"job": job}, auth_token=self._token(handler))
        gateway_record = {"idempotency_key": key, "job_id": job_id, "source_upload_id": upload_id, "job_hash": hashlib.sha256(json.dumps(job, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(), "submitted_at": datetime.now(timezone.utc).isoformat()}
        atomic_json_write(job_root / "gateway_submission.json", gateway_record)
        return 202, result

    def route(self, handler: BaseHTTPRequestHandler, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any, str | None]:
        self.touch()
        self.rate_limit(handler)
        self.authenticate(handler)
        parsed = urllib.parse.urlsplit(path)
        parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
        if len(parts) < 2 or parts[:1] != ["v1"]:
            raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "unknown gateway route")
        if method == "POST" and parts[1:] == ["uploads"]:
            return 201, self.create_upload(handler, body or {}), None
        if method == "PUT" and len(parts) == 3 and parts[1] == "uploads":
            return 200, self.put_upload(handler, parts[2]), None
        if method == "GET" and len(parts) == 3 and parts[1] == "uploads":
            job_id = self._safe_job_id(handler.headers.get("X-Portrait-Job-Id"))
            return 200, self._read_upload(job_id, self._safe_upload_id(parts[2])), None
        if method == "POST" and parts[1:] == ["jobs"]:
            status, result = self.submit_job(handler, body or {})
            return status, result, None
        if len(parts) >= 3 and parts[1] == "jobs":
            job_id = self._safe_job_id(parts[2])
            if method == "GET" and len(parts) == 3:
                return 200, self.service.call("portrait_job_status", {"job_id": job_id}, auth_token=self._token(handler)), None
            if method == "POST" and len(parts) == 4 and parts[3] == "cancel":
                return 200, self.service.call("portrait_cancel_job", {"job_id": job_id, **(body or {})}, auth_token=self._token(handler)), None
            if method == "GET" and len(parts) == 4 and parts[3] == "outputs":
                return 200, self.service.call("portrait_fetch_outputs", {"job_id": job_id}, auth_token=self._token(handler)), None
            if method == "GET" and len(parts) == 5 and parts[3] == "outputs":
                artifact_id = parts[4]
                descriptors = self.service.call("portrait_fetch_outputs", {"job_id": job_id}, auth_token=self._token(handler)).get("artifacts", [])
                descriptor = next((item for item in descriptors if item.get("artifact_id") == artifact_id), None)
                if descriptor is None:
                    raise AdapterError(ExitCode.SOURCE_INVALID, "requested output artifact is unavailable")
                job_root = relative_safe_path(self.root / "jobs", job_id)
                artifact = relative_safe_path(job_root, descriptor["relative_path"])
                if not artifact.is_file() or sha256_file(artifact) != descriptor.get("sha256"):
                    raise AdapterError(ExitCode.INTEGRATION_BLOCKED, "output checksum verification failed")
                return 200, artifact.read_bytes(), descriptor.get("mime_type", "application/octet-stream")
        if method == "GET" and parts[1:] == ["health"]:
            return 200, self.service.call("portrait_health", {}, auth_token=self._token(handler)), None
        if method == "GET" and parts[1:] == ["capabilities"]:
            return 200, self.service.call("portrait_capabilities", {}, auth_token=self._token(handler)), None
        raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "unknown gateway route")


class _GatewayHandler(BaseHTTPRequestHandler):
    application: PortraitGateway

    def _write(self, status: int, payload: Any, content_type: str | None = None) -> None:
        if isinstance(payload, bytes):
            body = payload
            mime = content_type or "application/octet-stream"
        else:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            mime = content_type or "application/json"
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def _status_for_error(exc: AdapterError) -> int:
        if exc.code == ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED:
            return 401 if exc.stage == "AUTHENTICATING_REMOTE_CALL" else 429
        if exc.code in {ExitCode.SOURCE_INVALID, ExitCode.MODEL_CHECKSUM_MISMATCH}:
            return 422
        return 400

    def _handle(self, method: str, *, body: dict[str, Any] | None = None) -> None:
        try:
            status, payload, content_type = self.application.route(self, method, self.path, body)
            self._write(status, payload, content_type)
        except AdapterError as exc:
            self._write(self._status_for_error(exc), exc.as_error())
        except (OSError, ValueError, KeyError, TypeError) as exc:
            error = AdapterError(ExitCode.INTERNAL_ERROR, "gateway operation failed", details={"error_type": type(exc).__name__})
            self._write(500, error.as_error())

    def do_GET(self):  # noqa: N802
        self._handle("GET")

    def do_POST(self):  # noqa: N802
        try:
            length = self.application._content_length(self, maximum=MAX_GATEWAY_BODY_BYTES)
            if length == 0:
                body: dict[str, Any] = {}
            else:
                decoded = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(decoded, dict):
                    raise AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "request body must be a JSON object")
                body = decoded
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._write(400, AdapterError(ExitCode.INPUT_SCHEMA_INVALID, "request body is not valid UTF-8 JSON").as_error())
            return
        except AdapterError as exc:
            self._write(self._status_for_error(exc), exc.as_error())
            return
        self._handle("POST", body=body)

    def do_PUT(self):  # noqa: N802
        self._handle("PUT")

    def log_message(self, format: str, *args: Any) -> None:
        return


def serve(root: str | Path | None = None, *, host: str | None = None, port: int | None = None) -> int:
    token = os.environ.get("PORTRAIT_GATEWAY_TOKEN")
    if not token:
        print("PORTRAIT_GATEWAY_TOKEN is required for the REST gateway", file=sys.stderr)
        return int(ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED)
    bind_host = host or os.environ.get("PORTRAIT_GATEWAY_HOST", "0.0.0.0")
    bind_port = port or int(os.environ.get("PORTRAIT_GATEWAY_PORT", "8765"))
    application = PortraitGateway(root)
    _GatewayHandler.application = application
    server = ThreadingHTTPServer((bind_host, bind_port), _GatewayHandler)
    server.daemon_threads = True
    idle_minutes = application._bounded_int("PORTRAIT_IDLE_SHUTDOWN_MINUTES", 0, 0, 24 * 60)

    def idle_watch() -> None:
        if idle_minutes <= 0:
            return
        while True:
            time.sleep(30)
            if time.monotonic() - application._last_request < idle_minutes * 60:
                continue
            if application._active_job_count() == 0:
                os.kill(os.getpid(), signal.SIGTERM)
                return

    if idle_minutes:
        threading.Thread(target=idle_watch, name="portrait-gateway-idle-watch", daemon=True).start()
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run the authenticated project-owned REST gateway.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args(argv)
    return serve(args.root, host=args.host, port=args.port)


if __name__ == "__main__":
    raise SystemExit(main())
