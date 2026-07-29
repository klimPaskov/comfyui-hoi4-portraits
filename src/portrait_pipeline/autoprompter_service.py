"""Loopback-only staged Qwen3-VL autoprompter service.

The service is deliberately a narrow adapter around the pinned official
llama.cpp ``llama-server`` binary.  It does not expose a filesystem tool, does
not forward background metadata, and never changes the exact instruction.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import io
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .prompt import autoprompter_instruction, validate_prompt
from .util import atomic_json_write, project_root, relative_safe_path, sha256_file


class AutoprompterServiceError(RuntimeError):
    def __init__(self, message: str, *, attempts: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.attempts = attempts or []


# The retry ladder changes decoding only.  The exact instruction and the
# processed image are reused byte-for-byte on every attempt, as required by
# the autoprompter contract.  Keep this small and deterministic so a failed
# high-risk claim cannot turn into an unbounded VLM loop.
AUTOPROMPTER_RETRY_PROFILES: tuple[dict[str, float | int], ...] = (
    {"temperature": 0.0, "seed": 0},
    {"temperature": 0.1, "seed": 17},
    {"temperature": 0.2, "seed": 29},
)


def _read_lock(root: Path) -> dict[str, Any]:
    path = root / "dependencies" / "autoprompter_runtime.lock.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AutoprompterServiceError(f"autoprompter runtime lock is unreadable: {type(exc).__name__}") from exc


def _verify_file(root: Path, relative: str, expected_sha256: str, expected_size: int | None = None) -> Path:
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise AutoprompterServiceError(f"locked autoprompter path escapes project root: {relative}") from exc
    if not path.is_file():
        raise AutoprompterServiceError(f"locked autoprompter artifact is missing: {relative}")
    if expected_size is not None and path.stat().st_size != expected_size:
        raise AutoprompterServiceError(f"locked autoprompter artifact size mismatch: {relative}")
    actual = sha256_file(path)
    if actual != expected_sha256:
        raise AutoprompterServiceError(f"locked autoprompter artifact checksum mismatch: {relative}")
    return path


def _resolve_local_runtime(root: Path) -> tuple[dict[str, Any], Path, Path, Path]:
    lock = _read_lock(root)
    artifact = lock.get("artifacts", {}).get("windows_x64", {})
    binary = root / str(artifact.get("install_path", ""))
    if not binary.is_file():
        raise AutoprompterServiceError(f"pinned llama-server binary is missing: {binary}")
    if binary.stat().st_size != int(artifact.get("extracted_binary_size_bytes", -1)) or sha256_file(binary) != artifact.get("extracted_binary_sha256"):
        raise AutoprompterServiceError("pinned llama-server binary checksum or size mismatch")
    model_cfg = lock.get("local_profile", {})
    model = _verify_file(root, str(model_cfg.get("model_path")), str(model_cfg.get("model_sha256")), int(model_cfg.get("model_size_bytes", -1)))
    mmproj = _verify_file(root, str(model_cfg.get("mmproj_path")), str(model_cfg.get("mmproj_sha256")), int(model_cfg.get("mmproj_size_bytes", -1)))
    instruction_path = root / "prompts" / "autoprompter_instruction.txt"
    if not instruction_path.is_file():
        raise AutoprompterServiceError("exact autoprompter instruction is missing")
    return lock, binary, model, mmproj


def _resolve_full_power_runtime(root: Path) -> tuple[dict[str, Any], Path]:
    lock = _read_lock(root)
    profile = lock.get("full_power_profile", {})
    if not isinstance(profile, dict) or profile.get("status") != "PINNED_TRANSFORMERS_FORMAT_EXECUTION_UNVERIFIED":
        raise AutoprompterServiceError("full-power Transformers runtime is not pinned")
    model_root_value = profile.get("model_root")
    if not isinstance(model_root_value, str):
        raise AutoprompterServiceError("full-power model root is missing from the runtime lock")
    model_root = (root / model_root_value).resolve()
    try:
        model_root.relative_to(root.resolve())
    except ValueError as exc:
        raise AutoprompterServiceError("full-power model root escapes the project root") from exc
    try:
        models_lock = json.loads((root / "dependencies" / "models.lock.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AutoprompterServiceError("full-power model lock is unreadable") from exc
    entry = next((item for item in models_lock.get("models", []) if item.get("name") == profile.get("model_lock_entry")), None)
    if not isinstance(entry, dict) or entry.get("revision") != profile.get("model_revision"):
        raise AutoprompterServiceError("full-power model lock entry or revision does not match the autoprompter lock")
    shard_sizes = entry.get("shard_size_bytes", {})
    for filename, expected_hash in sorted((entry.get("shard_sha256") or {}).items()):
        _verify_file(root, f"{model_root_value}/{filename}", str(expected_hash), int(shard_sizes.get(filename, -1)))
    for runtime_file in entry.get("runtime_files", []):
        if not isinstance(runtime_file, dict):
            raise AutoprompterServiceError("full-power runtime metadata entry is invalid")
        _verify_file(root, f"{model_root_value}/{runtime_file.get('filename', '')}", str(runtime_file.get("sha256", "")), int(runtime_file.get("size_bytes", -1)))
    return lock, model_root


def _post_json(url: str, payload: dict[str, Any], timeout: float = 10.0) -> dict[str, Any]:
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=encoded, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise AutoprompterServiceError(f"llama-server request failed: {type(exc).__name__}") from exc
    if not isinstance(value, dict):
        raise AutoprompterServiceError("llama-server returned a non-object response")
    return value


class _Handler(BaseHTTPRequestHandler):
    service: "AutoprompterService"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        # Request bodies contain private portraits and prompts; never log them.
        sys.stderr.write("autoprompter: " + format % args + "\n")

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send(200, self.service.health())
            return
        if self.path == "/v1/models":
            self._send(200, {"object": "list", "data": [{"id": self.service.model_id, "object": "model", "owned_by": "Qwen"}]})
            return
        self._send(404, {"error": {"message": "route not found"}})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/chat/completions":
            self._send(404, {"error": {"message": "route not found"}})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 16 * 1024 * 1024:
                raise AutoprompterServiceError("request body is missing or exceeds the bounded limit")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise AutoprompterServiceError("request body must be an object")
            result = self.service.complete(payload)
        except (AutoprompterServiceError, ValueError, json.JSONDecodeError) as exc:
            error = {"message": str(exc), "type": type(exc).__name__}
            attempts = getattr(exc, "attempts", None)
            if isinstance(attempts, list) and attempts:
                error["attempts"] = attempts
            self._send(400, {"error": error})
            return
        self._send(200, result)


class AutoprompterService:
    def __init__(self, root: str | Path | None = None, *, profile: str = "local_nvidia_16gb", host: str = "127.0.0.1", port: int = 8099, upstream_port: int = 8100):
        if host not in {"127.0.0.1", "localhost"}:
            raise AutoprompterServiceError("autoprompter may bind only to loopback")
        if profile not in {"local_nvidia_16gb", "full_power_gpu"}:
            raise AutoprompterServiceError("autoprompter profile is not a human workflow profile")
        self.root = project_root(root)
        self.profile = profile
        self.host = host
        self.port = port
        self.upstream_port = upstream_port
        self.child: subprocess.Popen[bytes] | None = None
        self._model: Any = None
        self._processor: Any = None
        if profile == "local_nvidia_16gb":
            self.lock, self.binary, self.model, self.mmproj = _resolve_local_runtime(self.root)
            self.model_id = "Qwen/Qwen3-VL-4B-Instruct-GGUF"
        else:
            self.lock, self.model = _resolve_full_power_runtime(self.root)
            self.model_root = self.model
            self.binary = None
            self.mmproj = None
            self.model_id = "Qwen/Qwen3-VL-8B-Instruct"
        self.instruction = autoprompter_instruction(self.root)

    def start_upstream(self) -> None:
        if self.profile == "full_power_gpu":
            try:
                import torch  # type: ignore
                from transformers import AutoProcessor, Qwen3VLForConditionalGeneration  # type: ignore
            except Exception as exc:
                raise AutoprompterServiceError(f"full-power Transformers runtime is unavailable: {type(exc).__name__}") from exc
            if not torch.cuda.is_available():
                raise AutoprompterServiceError("full_power_gpu autoprompter requires CUDA; the current host has no CUDA device")
            try:
                self._processor = AutoProcessor.from_pretrained(str(self.model_root), local_files_only=True)
                self._model = Qwen3VLForConditionalGeneration.from_pretrained(
                    str(self.model_root),
                    local_files_only=True,
                    torch_dtype=torch.bfloat16,
                    device_map="auto",
                )
            except Exception as exc:
                self._model = None
                self._processor = None
                raise AutoprompterServiceError(f"full-power Qwen3-VL model load failed: {type(exc).__name__}") from exc
            return
        command = [
            str(self.binary),
            "--model", str(self.model),
            "--mmproj", str(self.mmproj),
            "--host", "127.0.0.1",
            "--port", str(self.upstream_port),
            "--ctx-size", str(self.lock["local_profile"]["context_size"]),
            "--n-predict", str(self.lock["local_profile"]["max_tokens"]),
            "--parallel", str(self.lock["local_profile"]["parallel_requests"]),
            "--temp", str(self.lock["local_profile"]["temperature"]),
            "--reasoning", "off",
            "--no-webui",
            "--offline",
        ]
        environment = os.environ.copy()
        environment.pop("HF_TOKEN", None)
        self.child = subprocess.Popen(command, cwd=self.root, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if self.child.poll() is not None:
                raise AutoprompterServiceError("llama-server exited before health readiness")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.upstream_port}/health", timeout=2) as response:
                    if response.status == 200:
                        return
            except OSError:
                time.sleep(0.5)
        raise AutoprompterServiceError("llama-server health readiness timed out")

    def health(self) -> dict[str, Any]:
        if self.profile == "full_power_gpu":
            ready = self._model is not None and self._processor is not None
            return {"status": "PASS", "binding": f"http://{self.host}:{self.port}", "upstream": "transformers_loaded" if ready else "transformers_staged_idle", "profile": self.profile, "model_id": self.model_id, "instruction_sha256": __import__("hashlib").sha256(self.instruction.encode("utf-8")).hexdigest()}
        upstream = False
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.upstream_port}/health", timeout=2) as response:
                upstream = response.status == 200
        except OSError:
            upstream = False
        return {"status": "PASS" if upstream else "BLOCKED", "binding": f"http://{self.host}:{self.port}", "upstream": upstream, "profile": self.profile, "model_id": self.model_id, "instruction_sha256": __import__("hashlib").sha256(self.instruction.encode("utf-8")).hexdigest()}

    def _record_attempts(self, job_id: Any, attempts: list[dict[str, Any]]) -> None:
        """Persist private retry metadata without storing the model's prompt text."""

        if not isinstance(job_id, str) or not job_id or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for char in job_id):
            return
        try:
            job_root = relative_safe_path(self.root / "jobs", job_id)
        except ValueError:
            return
        atomic_json_write(
            job_root / "evidence" / "prompt" / "autoprompter_attempts.json",
            {
                "schema_version": "1.0.0",
                "instruction_sha256": __import__("hashlib").sha256(self.instruction.encode("utf-8")).hexdigest(),
                "attempts": attempts,
            },
        )

    def _complete_full_power(self, image_value: str, *, temperature: float, seed: int) -> str:
        if self._model is None or self._processor is None:
            raise AutoprompterServiceError("full-power Transformers model is not ready")
        try:
            import torch  # type: ignore
            from PIL import Image  # type: ignore

            image = Image.open(io.BytesIO(base64.b64decode(image_value, validate=True))).convert("RGB")
            messages = [{"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": self.instruction}]}]
            try:
                inputs = self._processor.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors="pt", return_dict=True, enable_thinking=False)
            except TypeError:
                inputs = self._processor.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors="pt", return_dict=True)
            device = next(self._model.parameters()).device
            inputs = {key: value.to(device) if hasattr(value, "to") else value for key, value in inputs.items()}
            torch.manual_seed(seed)
            generation_kwargs: dict[str, Any] = {
                "max_new_tokens": int(self.lock["local_profile"]["max_tokens"]),
            }
            if temperature > 0.0:
                generation_kwargs.update({"do_sample": True, "temperature": temperature})
            else:
                generation_kwargs["do_sample"] = False
            with torch.inference_mode():
                generated = self._model.generate(**inputs, **generation_kwargs)
            input_ids = inputs.get("input_ids")
            if input_ids is not None:
                generated = [output[len(input_row):] for input_row, output in zip(input_ids, generated)]
            return self._processor.batch_decode(generated, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]
        except AutoprompterServiceError:
            raise
        except Exception as exc:
            raise AutoprompterServiceError(f"full-power Qwen3-VL generation failed: {type(exc).__name__}") from exc

    def _release_full_power(self) -> None:
        if self.profile != "full_power_gpu":
            return
        self._model = None
        self._processor = None
        try:
            import torch  # type: ignore

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    def complete(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("model_id") != self.model_id:
            raise AutoprompterServiceError("model_id does not match the pinned local profile")
        if payload.get("instruction") != self.instruction:
            raise AutoprompterServiceError("instruction does not exactly match prompts/autoprompter_instruction.txt")
        image_value = payload.get("image_png_base64")
        if not isinstance(image_value, str) or not image_value:
            raise AutoprompterServiceError("processed image is required")
        try:
            decoded = base64.b64decode(image_value, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise AutoprompterServiceError("processed image is not valid base64") from exc
        if not decoded.startswith(b"\x89PNG\r\n\x1a\n"):
            raise AutoprompterServiceError("autoprompter accepts PNG input only")
        if self.profile == "full_power_gpu" and (self._model is None or self._processor is None):
            self.start_upstream()
        attempts: list[dict[str, Any]] = []
        for attempt_index, retry_profile in enumerate(AUTOPROMPTER_RETRY_PROFILES, start=1):
            temperature = float(retry_profile["temperature"])
            seed = int(retry_profile["seed"])
            if self.profile == "full_power_gpu":
                try:
                    prompt = self._complete_full_power(image_value, temperature=temperature, seed=seed)
                except Exception:
                    self._release_full_power()
                    raise
            else:
                upstream_payload = {
                    "model": self.model_id,
                    "messages": [{"role": "user", "content": [
                        {"type": "text", "text": self.instruction},
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + image_value}},
                    ]}],
                    "max_tokens": int(self.lock["local_profile"]["max_tokens"]),
                    "temperature": temperature,
                    "seed": seed,
                    "stream": False,
                }
                response = _post_json(f"http://127.0.0.1:{self.upstream_port}/v1/chat/completions", upstream_payload, timeout=180)
                try:
                    prompt = response["choices"][0]["message"]["content"]
                except (KeyError, IndexError, TypeError) as exc:
                    raise AutoprompterServiceError("llama-server response has no assistant content") from exc
                if not isinstance(prompt, str):
                    raise AutoprompterServiceError("llama-server assistant content is not text")
            validation = validate_prompt(prompt, allowed_claims=payload.get("allowed_claims"))
            attempt_record = {
                "attempt": attempt_index,
                "temperature": temperature,
                "seed": seed,
                "status": "PASS" if validation.passed else "REJECTED",
                "failure_codes": list(validation.failure_codes),
                "findings": list(validation.findings),
                "claims": {key: list(value) for key, value in validation.claims.items()},
            }
            attempts.append(attempt_record)
            if validation.passed:
                self._record_attempts(payload.get("job_id"), attempts)
                self._release_full_power()
                return {"prompt": validation.normalized_prompt, "model": self.model_id, "validator": validation.as_dict(), "attempts": attempts}
        final = attempts[-1] if attempts else {"failure_codes": ["AUTOPROMPT_EMPTY"]}
        self._record_attempts(payload.get("job_id"), attempts)
        self._release_full_power()
        raise AutoprompterServiceError("autoprompt failed validation after bounded retries: " + ",".join(final.get("failure_codes", [])), attempts=attempts)

    def stop(self) -> None:
        if self.profile == "full_power_gpu":
            self._release_full_power()
            return
        if self.child is None or self.child.poll() is not None:
            return
        self.child.terminate()
        try:
            self.child.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.child.kill()
            self.child.wait(timeout=20)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the loopback-only staged Qwen3-VL autoprompter.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--profile", default="local_nvidia_16gb")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument("--upstream-port", type=int, default=8100)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        service = AutoprompterService(args.root, profile=args.profile, host=args.host, port=args.port, upstream_port=args.upstream_port)
        if args.check_only:
            print(json.dumps({"status": "PASS", "profile": service.profile, "model_id": service.model_id, "binary": str(service.binary) if service.binary else None, "model": str(service.model), "mmproj": str(service.mmproj) if service.mmproj else None}, indent=2))
            return 0
        # The full-power VLM shares the GPU with portrait generation. Keep it
        # staged on disk until a workflow request actually needs an automatic
        # prompt, then release it immediately after the bounded prompt pass.
        if service.profile != "full_power_gpu":
            service.start_upstream()
        server = ThreadingHTTPServer((args.host, args.port), _Handler)
        _Handler.service = service
        for signal_name in (signal.SIGINT, signal.SIGTERM):
            signal.signal(signal_name, lambda _signum, _frame: threading.Thread(target=server.shutdown, daemon=True).start())
        upstream = "transformers_staged_idle" if service.profile == "full_power_gpu" else f"http://127.0.0.1:{args.upstream_port}"
        print(json.dumps({"status": "PASS", "binding": f"http://{args.host}:{args.port}", "upstream": upstream}), flush=True)
        try:
            server.serve_forever()
        finally:
            server.server_close()
            service.stop()
        return 0
    except AutoprompterServiceError as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}), file=sys.stderr)
        return 20


if __name__ == "__main__":
    raise SystemExit(main())
