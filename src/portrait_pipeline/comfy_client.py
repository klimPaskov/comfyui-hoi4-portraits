from __future__ import annotations

import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
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
