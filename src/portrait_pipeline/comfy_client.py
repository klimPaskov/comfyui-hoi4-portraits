from __future__ import annotations

import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .constants import ExitCode


class ComfyTransportError(RuntimeError):
    def __init__(self, code: ExitCode, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ComfyResponse:
    status: int
    payload: Any


class _JsonHttpClient:
    def __init__(self, base_url: str, *, headers: dict[str, str] | None = None, timeout: float = 30.0, transport_error_code: ExitCode = ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED, http_error_code: ExitCode = ExitCode.GENERATION_FAILED):
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout
        self.transport_error_code = transport_error_code
        self.http_error_code = http_error_code

    def request(self, method: str, path: str, body: Any | None = None, *, timeout: float | None = None) -> ComfyResponse:
        url = self.base_url + "/" + path.lstrip("/")
        payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {"Accept": "application/json", **self.headers}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=payload, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout or self.timeout) as response:
                data = response.read()
                try:
                    decoded = json.loads(data.decode("utf-8")) if data else None
                except json.JSONDecodeError:
                    decoded = {"raw_length": len(data)}
                return ComfyResponse(response.status, decoded)
        except urllib.error.HTTPError as exc:
            raise ComfyTransportError(self.http_error_code, f"HTTP {exc.code} from protected runtime") from exc
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise ComfyTransportError(self.transport_error_code, f"runtime transport unavailable: {exc}") from exc


class LoopbackComfyClient(_JsonHttpClient):
    """Internal client; raw ComfyUI is always constrained to loopback."""

    def __init__(self, base_url: str = "http://127.0.0.1:8188", **kwargs: Any):
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("raw ComfyUI client must use an HTTP loopback URL")
        super().__init__(base_url, transport_error_code=ExitCode.DEPENDENCY_MISSING, http_error_code=ExitCode.GENERATION_FAILED, **kwargs)

    def health(self) -> ComfyResponse:
        return self.request("GET", "/system_stats")

    def inventory(self) -> ComfyResponse:
        return self.request("GET", "/object_info")

    def queue(self) -> ComfyResponse:
        return self.request("GET", "/queue")

    def history(self, prompt_id: str | None = None) -> ComfyResponse:
        return self.request("GET", f"/history/{urllib.parse.quote(prompt_id)}" if prompt_id else "/history")

    def submit(self, api_workflow: dict[str, Any], client_id: str) -> str:
        response = self.request("POST", "/prompt", {"prompt": api_workflow, "client_id": client_id})
        if response.status != 200 or not isinstance(response.payload, dict) or not response.payload.get("prompt_id"):
            raise ComfyTransportError(ExitCode.GENERATION_FAILED, "ComfyUI did not return a prompt id")
        return str(response.payload["prompt_id"])

    def cancel(self) -> ComfyResponse:
        return self.request("POST", "/interrupt", {})

    def free_memory(self) -> ComfyResponse:
        return self.request("POST", "/free", {"unload_models": True, "free_memory": True})

    def wait_for_history(self, prompt_id: str, *, timeout: float = 3600, interval: float = 2.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            history = self.history(prompt_id).payload
            if isinstance(history, dict) and prompt_id in history:
                return history[prompt_id]
            time.sleep(min(interval, max(0.1, deadline - time.monotonic())))
        raise ComfyTransportError(ExitCode.GENERATION_FAILED, "ComfyUI history poll timed out")


class AuthenticatedRemoteGatewayClient(_JsonHttpClient):
    """Remote client for the project gateway, never a direct public ComfyUI client."""

    def __init__(self, base_url: str, token: str, **kwargs: Any):
        if not token:
            raise ComfyTransportError(ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED, "remote gateway token is missing")
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme != "https" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ComfyTransportError(ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED, "remote gateway must use HTTPS")
        super().__init__(base_url, headers={"Authorization": f"Bearer {token}", "X-Portrait-Client": "hoi4-portrait-pipeline/1"}, transport_error_code=ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED, http_error_code=ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED, **kwargs)

    def call_tool(self, name: str, params: dict[str, Any]) -> ComfyResponse:
        return self.request("POST", "/mcp", {"jsonrpc": "2.0", "id": secrets.token_hex(8), "method": name, "params": params})


class ComfyCloudClient(_JsonHttpClient):
    """Authenticated Comfy Cloud API client for the full-power profiles.

    Cloud is intentionally not treated as a raw ComfyUI endpoint.  Every
    request carries the Cloud API key, the base URL must be HTTPS, and the
    client uses the documented ``/api`` surface.  A missing subscription,
    missing key, or unavailable Cloud capability is surfaced as a remote
    transport blocker instead of falling back to an unauthenticated route.
    """

    def __init__(self, base_url: str | None = None, api_key: str | None = None, **kwargs: Any):
        selected_base = base_url or os.environ.get("COMFY_CLOUD_BASE_URL", "https://cloud.comfy.org")
        selected_key = api_key if api_key is not None else (os.environ.get("COMFY_CLOUD_API_KEY") or os.environ.get("COMFY_API_KEY", ""))
        if not selected_key:
            raise ComfyTransportError(ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED, "Comfy Cloud API key is missing")
        parsed = urllib.parse.urlparse(selected_base)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ComfyTransportError(ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED, "Comfy Cloud API must use an HTTPS base URL")
        super().__init__(
            selected_base,
            headers={"X-API-Key": selected_key, "X-Portrait-Client": "hoi4-portrait-pipeline/1"},
            transport_error_code=ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED,
            http_error_code=ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED,
            **kwargs,
        )

    def health(self) -> ComfyResponse:
        # Cloud documents object_info as the authenticated capability probe;
        # unlike local ComfyUI, no unauthenticated /system_stats assumption is
        # made here.
        return self.request("GET", "/api/object_info")

    def inventory(self) -> ComfyResponse:
        return self.request("GET", "/api/object_info")

    def queue(self) -> ComfyResponse:
        return self.request("GET", "/api/queue")

    def submit(self, api_workflow: dict[str, Any], client_id: str) -> str:
        response = self.request("POST", "/api/prompt", {"prompt": api_workflow})
        if not isinstance(response.payload, dict) or not response.payload.get("prompt_id"):
            raise ComfyTransportError(ExitCode.GENERATION_FAILED, "Comfy Cloud did not return a prompt id")
        return str(response.payload["prompt_id"])

    def job_status(self, prompt_id: str) -> ComfyResponse:
        safe_id = urllib.parse.quote(prompt_id, safe="")
        return self.request("GET", f"/api/job/{safe_id}/status")

    def history(self, prompt_id: str | None = None) -> ComfyResponse:
        if prompt_id:
            safe_id = urllib.parse.quote(prompt_id, safe="")
            return self.request("GET", f"/api/history/{safe_id}")
        return self.request("GET", "/api/history")

    def cancel_job(self, prompt_id: str) -> ComfyResponse:
        safe_id = urllib.parse.quote(prompt_id, safe="")
        return self.request("POST", f"/api/job/{safe_id}/cancel", {})

    def wait_for_history(self, prompt_id: str, *, timeout: float = 3600, interval: float = 2.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status_payload = self.job_status(prompt_id).payload
            status = status_payload.get("status") if isinstance(status_payload, dict) else None
            if status == "completed":
                history = self.history(prompt_id).payload
                if isinstance(history, dict):
                    return history
                return {"status": {"status_str": "success"}, "cloud_status": status, "outputs": history}
            if status in {"failed", "cancelled"}:
                return {"status": {"status_str": "error", "cloud_status": status}, "cloud_status": status}
            time.sleep(min(interval, max(0.1, deadline - time.monotonic())))
        raise ComfyTransportError(ExitCode.GENERATION_FAILED, "Comfy Cloud job status poll timed out")

    def upload_image(self, path: str | Any, *, input_type: str = "input") -> dict[str, Any]:
        """Upload an image using the documented multipart Cloud endpoint."""

        image_path = Path(path)
        if not image_path.is_file():
            raise ComfyTransportError(ExitCode.SOURCE_INVALID, "Cloud upload source image is missing")
        payload = image_path.read_bytes()
        boundary = f"----hoi4portrait{secrets.token_hex(12)}"
        parts: list[bytes] = []
        for name, value in (("type", input_type), ("overwrite", "true")):
            parts.extend([
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                str(value).encode(),
                b"\r\n",
            ])
        parts.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="image"; filename="{image_path.name}"\r\n'.encode(),
            b"Content-Type: application/octet-stream\r\n\r\n",
            payload,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ])
        request = urllib.request.Request(
            self.base_url + "/api/upload/image",
            data=b"".join(parts),
            headers={"Accept": "application/json", **self.headers, "Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = response.read()
                result = json.loads(data.decode("utf-8")) if data else {}
        except urllib.error.HTTPError as exc:
            raise ComfyTransportError(ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED, f"HTTP {exc.code} from Comfy Cloud upload") from exc
        except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
            raise ComfyTransportError(ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED, f"Comfy Cloud upload failed: {type(exc).__name__}") from exc
        if not isinstance(result, dict) or not result.get("name"):
            raise ComfyTransportError(ExitCode.SOURCE_INVALID, "Comfy Cloud upload did not return an image reference")
        return result
