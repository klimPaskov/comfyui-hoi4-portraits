from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import tempfile
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from ..constants import ExitCode
from ..controller import JobController
from ..preflight import collect_preflight
from ..util import atomic_json_write, project_root, relative_safe_path, sha256_file


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
    def __init__(self, code: ExitCode, message: str):
        super().__init__(message)
        self.code = code


class PortraitMcpService:
    def __init__(self, root: str | Path | None = None, *, remote: bool = False):
        self.root = project_root(root)
        self.remote = remote
        self.controller = JobController(self.root)
        self.registered_dir = self.root / "evidence" / "registered_workflows"

    def _check_remote_auth(self, token: str | None) -> None:
        if not self.remote:
            return
        expected = os.environ.get("PORTRAIT_GATEWAY_TOKEN")
        if not expected or not token or not secrets.compare_digest(token, expected):
            raise AdapterError(ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED, "remote adapter authentication failed")

    def _workflow_path(self, workflow_id: str, api: bool = True) -> Path:
        paths = {
            "human_local_mac_16gb": "workflows/human/local_mac_16gb/human_local_mac_16gb.api.json",
            "human_full_power_gpu": "workflows/human/full_power_gpu/human_full_power_gpu.api.json",
            "agent_local_mac_16gb": "workflows/agent/local_mac_16gb/agent_local_mac_16gb.api.json",
            "agent_remote_runpod": "workflows/agent/remote_runpod/agent_remote_runpod.api.json",
        }
        if workflow_id not in paths:
            raise AdapterError(ExitCode.WORKFLOW_INVALID, f"unknown workflow id: {workflow_id}")
        return self.root / paths[workflow_id]

    def call(self, name: str, params: dict[str, Any] | None = None, *, auth_token: str | None = None) -> dict[str, Any]:
        params = params or {}
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
        report = collect_preflight(self.root)
        return {"status": report["status"], "adapter": "project_owned", "remote": self.remote, "raw_comfyui_exposed": False, "blockers": report["blockers"], "workflow_version": "graph-spec-1.0.0"}

    def _portrait_capabilities(self, params: dict[str, Any]) -> dict[str, Any]:
        report = collect_preflight(self.root)
        return {"profiles": ["human_local_mac_16gb", "human_full_power_gpu", "agent_local_mac_16gb", "agent_remote_runpod"], "local_comfyui_binding": "http://127.0.0.1:8188", "remote_transport": "authenticated_gateway_only", "first_party_local_mcp_parity": False, "gates": {gate["name"]: gate["status"] for gate in report["gates"]}}

    def _portrait_inventory(self, params: dict[str, Any]) -> dict[str, Any]:
        model_lock = json.loads((self.root / "dependencies" / "models.lock.json").read_text(encoding="utf-8"))
        node_dir = self.root / "src" / "comfyui_hoi4_portrait_nodes"
        return {"project_nodes": sorted(path.stem for path in node_dir.glob("*.py")), "locked_models": [item["name"] for item in model_lock["models"]], "installed_model_files": [str(path.relative_to(self.root)) for path in (self.root / "models").rglob("*") if path.is_file()] if (self.root / "models").is_dir() else [], "status": "BLOCKED" if not (self.root / "models").is_dir() else "UNVERIFIED"}

    def _portrait_validate_workflow(self, params: dict[str, Any]) -> dict[str, Any]:
        workflow_id = str(params.get("workflow_id", ""))
        path = self._workflow_path(workflow_id)
        if not path.is_file():
            raise AdapterError(ExitCode.WORKFLOW_INVALID, f"workflow artifact missing: {workflow_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        nodes = data.get("_meta", {})
        report = collect_preflight(self.root)
        return {"workflow_id": workflow_id, "json_sha256": sha256_file(path), "graph_spec_version": nodes.get("graph_spec_version"), "autoprompter": nodes.get("autoprompter"), "prompt_source": nodes.get("prompt_source"), "structural_valid": bool(nodes.get("required_groups")), "runtime_status": report["status"], "blockers": report["blockers"]}

    def _portrait_import_workflow(self, params: dict[str, Any]) -> dict[str, Any]:
        workflow_id = str(params.get("workflow_id", ""))
        path = self._workflow_path(workflow_id)
        expected = str(params.get("sha256", ""))
        actual = sha256_file(path)
        if expected and expected != actual:
            raise AdapterError(ExitCode.MODEL_CHECKSUM_MISMATCH, "workflow checksum mismatch")
        record = {"workflow_id": workflow_id, "path": str(path.relative_to(self.root)), "sha256": actual, "registered_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}
        atomic_json_write(self.registered_dir / f"{workflow_id}.json", record)
        return record

    def _portrait_upload_source(self, params: dict[str, Any]) -> dict[str, Any]:
        job_id = str(params.get("job_id", ""))
        source = Path(str(params.get("source_path", ""))).expanduser().resolve()
        if not source.is_file():
            raise AdapterError(ExitCode.SOURCE_INVALID, "source path does not exist")
        job_root = relative_safe_path(self.root / "jobs", job_id)
        target = relative_safe_path(job_root, f"source/original/{source.name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("wb", dir=target.parent, delete=False) as tmp:
            tmp.write(source.read_bytes())
            temporary = Path(tmp.name)
        os.replace(temporary, target)
        return {"job_id": job_id, "relative_path": str(target.relative_to(job_root)), "size_bytes": target.stat().st_size, "sha256": sha256_file(target)}

    def _portrait_submit_job(self, params: dict[str, Any]) -> dict[str, Any]:
        result = self.controller.submit(dict(params["job"]))
        return {"job_id": result.output.get("job_id", result.job_root.name), "status": result.output.get("status", "SUBMITTED"), "job_root": str(result.job_root.relative_to(self.root)), "output": result.output}

    def _portrait_job_status(self, params: dict[str, Any]) -> dict[str, Any]:
        return self.controller.status(str(params["job_id"]))

    def _portrait_watch_job(self, params: dict[str, Any]) -> dict[str, Any]:
        return self.controller.status(str(params["job_id"]))

    def _portrait_cancel_job(self, params: dict[str, Any]) -> dict[str, Any]:
        job_id = str(params["job_id"])
        job_root = relative_safe_path(self.root / "jobs", job_id)
        status = self.controller.status(job_id)
        status.update({"state": "CANCELED", "terminal_exit_code": int(ExitCode.CANCELED), "cancel_reason": str(params.get("reason", "caller requested cancellation"))})
        atomic_json_write(job_root / "status.json", status)
        return status

    def _portrait_fetch_outputs(self, params: dict[str, Any]) -> dict[str, Any]:
        job_id = str(params["job_id"])
        job_root = relative_safe_path(self.root / "jobs", job_id)
        output_path = job_root / "output.json"
        if not output_path.is_file():
            raise AdapterError(ExitCode.SOURCE_INVALID, "job output is unavailable")
        output = json.loads(output_path.read_text(encoding="utf-8"))
        if output.get("status") != "SUCCEEDED":
            raise AdapterError(ExitCode.INTEGRATION_BLOCKED, "outputs are not available until the job succeeds")
        checksum_names = {"final_png": "png", "final_dds": "dds"}
        return {"job_id": job_id, "artifacts": [{"artifact_id": key, "relative_path": value, "sha256": output.get("final_checksums", {}).get(checksum_names[key])} for key, value in (("final_png", output.get("final_png")), ("final_dds", output.get("final_dds"))) if value]}

    def _portrait_history(self, params: dict[str, Any]) -> dict[str, Any]:
        jobs: list[dict[str, Any]] = []
        if (self.root / "jobs").is_dir():
            for status_path in sorted((self.root / "jobs").glob("*/status.json")):
                try:
                    jobs.append(json.loads(status_path.read_text(encoding="utf-8")))
                except json.JSONDecodeError:
                    continue
        limit = max(1, min(100, int(params.get("limit", 25))))
        return {"jobs": jobs[-limit:], "count": len(jobs)}

    def _portrait_free_memory(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"status": "UNVERIFIED", "binding": "loopback-only", "message": "ComfyUI memory-free operation requires a live health-checked runtime"}


class _RequestHandler(BaseHTTPRequestHandler):
    service: PortraitMcpService

    def do_POST(self):  # noqa: N802
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            token = self.headers.get("Authorization", "").removeprefix("Bearer ") or None
            result = self.service.call(body.get("method", ""), body.get("params", {}), auth_token=token)
            payload = {"jsonrpc": "2.0", "id": body.get("id"), "result": result}
            code = 200
        except AdapterError as exc:
            payload = {"jsonrpc": "2.0", "id": body.get("id") if "body" in locals() else None, "error": {"code": int(exc.code), "message": str(exc)}}
            code = 403 if exc.code == ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED else 400
        except Exception as exc:
            payload = {"jsonrpc": "2.0", "id": None, "error": {"code": int(ExitCode.INTERNAL_ERROR), "message": f"{type(exc).__name__}: {exc}"}}
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
        request: dict[str, Any] = {}
        try:
            request = json.loads(line)
            result = service.call(request.get("method", ""), request.get("params", {}))
            response = {"jsonrpc": "2.0", "id": request.get("id"), "result": result}
        except AdapterError as exc:
            response = {"jsonrpc": "2.0", "id": request.get("id") if "request" in locals() else None, "error": {"code": int(exc.code), "message": str(exc)}}
        except Exception as exc:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": int(ExitCode.INTERNAL_ERROR), "message": f"{type(exc).__name__}: {exc}"}}
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
