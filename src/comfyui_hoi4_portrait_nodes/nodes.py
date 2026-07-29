from __future__ import annotations

import json
import base64
import binascii
import hashlib
import io
import os
import random
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from portrait_pipeline.constants import (
    ExitCode,
    HOI4_OPERATIVE_BACKGROUND_REGISTRY_ID,
    HOI4_OPERATIVE_BACKGROUND_RUNTIME_PATH,
    HOI4_OPERATIVE_BACKGROUND_SHA256,
    HOI4_SCIENTIST_BACKGROUND_REGISTRY_ID,
    HOI4_SCIENTIST_BACKGROUND_RUNTIME_PATH,
    HOI4_SCIENTIST_BACKGROUND_SHA256,
    RANDOM_PORTRAIT_PROMPT_PATH,
)
from portrait_pipeline.contracts import validate_job, validate_schema
from portrait_pipeline.prompt import validate_prompt
from portrait_pipeline.constants import PROFILE_LIMITS
from portrait_pipeline.util import atomic_json_write, project_root, relative_safe_path, sha256_file

try:  # ComfyUI supplies torch/Pillow in its runtime.
    import torch  # type: ignore
except Exception:  # pragma: no cover - import-only path on a clean preflight host
    torch = None

try:
    from PIL import Image, ImageEnhance, ImageOps  # type: ignore
except Exception:  # pragma: no cover - import-only path on a clean preflight host
    Image = None
    ImageEnhance = None
    ImageOps = None


def _raise(code: ExitCode, message: str) -> None:
    raise RuntimeError(f"{code.name} ({int(code)}): {message}")


def _manual_generation_prompt(value: str, *, field_name: str) -> str:
    prompt = " ".join(str(value).replace("\r", " ").replace("\n", " ").split())
    if not prompt:
        _raise(ExitCode.INPUT_SCHEMA_INVALID, f"{field_name} requires a portrait description")
    if len(prompt) > 1200:
        _raise(ExitCode.INPUT_SCHEMA_INVALID, f"{field_name} exceeds 1200 characters")
    return prompt if prompt.casefold().startswith("hoi4_portrait,") else f"hoi4_portrait, {prompt}"


def _project_from_job(job: dict[str, Any]) -> Path:
    root = job.get("_project_root") or os.environ.get("HOI4_PORTRAIT_PROJECT_ROOT")
    if not root:
        _raise(ExitCode.INTERNAL_ERROR, "job does not identify an allowed project root")
    return project_root(root)


def _standalone_project_root() -> Path:
    """Find the project used by simple workflows that do not use a job file."""

    candidates: list[Path] = []
    environment_root = os.environ.get("HOI4_PORTRAIT_PROJECT_ROOT")
    if environment_root:
        candidates.append(Path(environment_root))
    marker = Path(__file__).resolve().parent / ".hoi4_project_root"
    try:
        marker_value = marker.read_text(encoding="utf-8").strip()
    except OSError:
        marker_value = ""
    if marker_value:
        candidates.append(Path(marker_value))
    candidates.append(Path(__file__).resolve().parents[2])
    for candidate in candidates:
        try:
            return project_root(candidate)
        except (FileNotFoundError, ValueError):
            continue
    _raise(ExitCode.INTERNAL_ERROR, "the HOI4 portrait project folder could not be found")


def _job_path(path_value: str, root: Path) -> Path:
    if "<" in path_value or ">" in path_value:
        _raise(ExitCode.INPUT_SCHEMA_INVALID, "workflow job contract path is still a placeholder")
    return relative_safe_path(root, path_value)


def _pil_to_comfy(image: Any) -> Any:
    if torch is None:
        _raise(ExitCode.DEPENDENCY_MISSING, "PyTorch is required inside ComfyUI")
    if Image is None:
        _raise(ExitCode.DEPENDENCY_MISSING, "Pillow is required inside ComfyUI")
    rgb = image.convert("RGB")
    # ComfyUI image tensors are [batch, height, width, channels] float32 RGB.
    values = torch.frombuffer(bytearray(rgb.tobytes()), dtype=torch.uint8).reshape(rgb.height, rgb.width, 3)
    return values.float().div(255.0).unsqueeze(0)


def _comfy_to_pil(image: Any) -> Any:
    if Image is None:
        _raise(ExitCode.DEPENDENCY_MISSING, "Pillow is required inside ComfyUI")
    if hasattr(image, "detach"):
        image = image.detach().cpu().clamp(0, 1)
        if image.ndim == 4:
            image = image[0]
        array = (image.mul(255).byte().numpy())
        return Image.fromarray(array, mode="RGB")
    return image


def _job_root(job: dict[str, Any]) -> Path:
    root = _project_from_job(job)
    job_id = str(job.get("job_id", ""))
    if not job_id or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for char in job_id):
        _raise(ExitCode.INPUT_SCHEMA_INVALID, "job id is invalid")
    return relative_safe_path(root / "jobs", job_id)


def _pixel_digest(image: Any) -> str:
    digest = hashlib.sha256()
    digest.update(f"{image.width}x{image.height}:{image.mode}".encode("ascii"))
    digest.update(image.tobytes())
    return digest.hexdigest()


def _write_image(path: Path, image: Any, *, format_name: str = "PNG") -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
            image.save(handle, format=format_name, optimize=False)
            temporary = Path(handle.name)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return {"path": str(path), "relative_path": str(path), "sha256": sha256_file(path), "width": image.width, "height": image.height, "mode": image.mode, "pixel_sha256": _pixel_digest(image)}


def _read_project_job(job: dict[str, Any]) -> tuple[Path, Path]:
    root = _project_from_job(job)
    job_root = _job_root(job)
    return root, job_root


def _source_format_allowed(fmt: str | None) -> bool:
    return fmt in {"PNG", "JPEG", "WEBP", "TIFF"}


def _preprocessing_entry(root: Path, name: str) -> dict[str, Any]:
    lock_path = root / "dependencies" / "preprocessing_lock.json"
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _raise(ExitCode.DEPENDENCY_MISSING, f"preprocessing lock is unavailable: {type(exc).__name__}")
    entries = [entry for entry in lock.get("dependencies", []) if entry.get("name") == name]
    entry = entries[0] if entries else {}
    if (
        not entries
        or lock.get("status") not in {"PINNED_ARTIFACTS_NOT_INSTALLED", "RESOLVED"}
        or not isinstance(entry.get("artifact_sha256"), str)
        or len(entry["artifact_sha256"]) != 64
        or not isinstance(entry.get("artifact_url"), str)
        or not entry["artifact_url"].startswith("https://")
        or not isinstance(entry.get("destination_path"), str)
    ):
        _raise(ExitCode.DEPENDENCY_MISSING, f"{name} preprocessing artifact is not locked and verified")
    try:
        destination = relative_safe_path(root, entry["destination_path"])
    except (KeyError, ValueError) as exc:
        _raise(ExitCode.DEPENDENCY_MISSING, f"{name} preprocessing destination is invalid: {type(exc).__name__}")
    expected_size = entry.get("artifact_size_bytes")
    expected_format = entry.get("artifact_format")
    supported_formats = {".bin": "pytorch_bin", ".onnx": "onnx", ".safetensors": "safetensors", ".task": "mediapipe_task"}
    if not destination.is_file():
        _raise(ExitCode.DEPENDENCY_MISSING, f"{name} preprocessing artifact is not installed")
    if destination.suffix.casefold() not in supported_formats or supported_formats[destination.suffix.casefold()] != expected_format:
        _raise(ExitCode.DEPENDENCY_MISSING, f"{name} preprocessing artifact format is unsupported")
    if not isinstance(expected_size, int) or destination.stat().st_size != expected_size:
        _raise(ExitCode.MODEL_CHECKSUM_MISMATCH, f"{name} preprocessing artifact size does not match the lock")
    if sha256_file(destination) != entry["artifact_sha256"]:
        _raise(ExitCode.MODEL_CHECKSUM_MISMATCH, f"{name} preprocessing artifact checksum does not match the lock")
    return entry


def _post_loopback_json(endpoint: str, payload: dict[str, Any], *, timeout: float = 120.0, service_label: str = "preprocessing service") -> dict[str, Any]:
    if not endpoint:
        _raise(ExitCode.DEPENDENCY_MISSING, "preprocessing service is not configured")
    if not (endpoint.startswith("http://127.0.0.1:") or endpoint.startswith("http://localhost:")):
        _raise(ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED, "preprocessing service must be bound to loopback")
    request = urllib.request.Request(endpoint, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Keep the failure fail-closed but preserve the service identity and a
        # bounded structured error for diagnosis.  The old message called all
        # loopback failures a preprocessing error, which obscured autoprompt
        # validation failures from users and auditors.
        try:
            body = json.loads(exc.read().decode("utf-8"))
            detail = body.get("error", {}).get("message") if isinstance(body, dict) and isinstance(body.get("error"), dict) else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            detail = None
        suffix = f": {detail}" if isinstance(detail, str) and detail else ""
        _raise(ExitCode.DEPENDENCY_MISSING, f"loopback {service_label} returned HTTP {exc.code}{suffix}")
    except (OSError, urllib.error.URLError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        _raise(ExitCode.DEPENDENCY_MISSING, f"loopback {service_label} unavailable: {type(exc).__name__}")
    if not isinstance(body, dict):
        _raise(ExitCode.GENERATION_FAILED, "loopback preprocessing service returned a non-object response")
    if body.get("status") == "BLOCKED":
        try:
            code = ExitCode(int(body.get("exit_code")))
        except (TypeError, ValueError):
            code = ExitCode.GENERATION_FAILED
        _raise(code, str(body.get("error") or body.get("error_code") or "loopback preprocessing service blocked the operation"))
    if body.get("status") not in {None, "PASS"}:
        _raise(ExitCode.GENERATION_FAILED, f"loopback preprocessing service returned status {body.get('status')!r}")
    return body


def _post_autoprompt_staged(root: Path, endpoint: str, payload: dict[str, Any], profile: str) -> dict[str, Any]:
    """Use an existing loopback sidecar or launch one for this single request.

    The owned sidecar is terminated before this node returns so the controller
    can proceed to Krea loading without retaining the VLM process.
    """

    parsed = urlsplit(endpoint)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        _raise(ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED, "autoprompter is not bound to loopback")
    base = f"http://{parsed.netloc}"
    owned: subprocess.Popen[Any] | None = None
    try:
        try:
            with urllib.request.urlopen(base + "/health", timeout=2) as response:
                health = json.loads(response.read().decode("utf-8"))
            if not isinstance(health, dict) or health.get("status") != "PASS" or health.get("model_id") != payload.get("model_id"):
                raise OSError("autoprompter health is not PASS")
        except (OSError, urllib.error.URLError, json.JSONDecodeError):
            runtime_python = root / ".venv" / "bin" / "python"
            if not runtime_python.is_file():
                runtime_python = Path(sys.executable)
            port = int(parsed.port or 8099)
            owned = subprocess.Popen([str(runtime_python), "-m", "portrait_pipeline.autoprompter_service", "--root", str(root), "--profile", profile, "--port", str(port), "--upstream-port", str(port + 1)], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                if owned.poll() is not None:
                    _raise(ExitCode.DEPENDENCY_MISSING, "staged autoprompter sidecar exited before readiness")
                try:
                    with urllib.request.urlopen(base + "/health", timeout=2) as response:
                        health = json.loads(response.read().decode("utf-8"))
                    if isinstance(health, dict) and health.get("status") == "PASS" and health.get("model_id") == payload.get("model_id"):
                        break
                except (OSError, urllib.error.URLError, json.JSONDecodeError):
                    time.sleep(0.5)
            else:
                _raise(ExitCode.DEPENDENCY_MISSING, "staged autoprompter sidecar health timed out")
        return _post_loopback_json(endpoint, payload, timeout=180.0, service_label="autoprompter service")
    finally:
        if owned is not None and owned.poll() is None:
            owned.terminate()
            try:
                owned.wait(timeout=20)
            except subprocess.TimeoutExpired:
                owned.kill()
                owned.wait(timeout=20)


def _write_subject_inventory(job: dict[str, Any], image: Any) -> dict[str, Any]:
    root = _project_from_job(job)
    entry = _preprocessing_entry(root, "YuNet")
    endpoint = os.environ.get("HOI4_SUBJECT_SERVICE_LOOPBACK", "")
    source = _comfy_to_pil(image).convert("RGB")
    encoded = io.BytesIO()
    source.save(encoded, format="PNG", optimize=False)
    response = _post_loopback_json(endpoint, {"job_id": job.get("job_id"), "model": {"name": "YuNet", "source_revision": entry.get("source_revision"), "artifact_sha256": entry.get("artifact_sha256")}, "image_png_base64": base64.b64encode(encoded.getvalue()).decode("ascii")}, service_label="subject preprocessing service")
    response_model = response.get("model")
    if not isinstance(response_model, dict) or response_model.get("name") != "YuNet" or response_model.get("source_revision") != entry.get("source_revision") or response_model.get("artifact_sha256") != entry.get("artifact_sha256"):
        _raise(ExitCode.MODEL_CHECKSUM_MISMATCH, "subject service model identity does not match the preprocessing lock")
    if response.get("analysis_status") != "PASS":
        _raise(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "subject service did not return an auditable PASS analysis")
    subjects = response.get("subjects")
    selected = response.get("selected")
    if not isinstance(subjects, list) or not subjects:
        _raise(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "subject service returned no auditable subjects")
    for subject in subjects:
        if not isinstance(subject, dict) or not isinstance(subject.get("person_association"), dict) or not isinstance(subject.get("landmarks"), dict):
            _raise(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "subject service returned a subject without person association and landmarks")
    if not isinstance(selected, dict):
        if len(subjects) != 1:
            _raise(ExitCode.AMBIGUOUS_SUBJECT, "subject service returned multiple plausible subjects without a deterministic selection")
        selected = subjects[0]
    bbox = selected.get("bbox_xyxy")
    if not isinstance(bbox, list) or len(bbox) != 4 or not all(isinstance(value, int) and value >= 0 for value in bbox):
        _raise(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "subject service selected an invalid bounding box")
    left, top, right, bottom = bbox
    if right <= left or bottom <= top or left >= source.width or top >= source.height:
        _raise(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "subject service selected a box outside the source")
    inventory = {"schema_version": "1.0.0", "analysis_status": "PASS", "model": {"name": "YuNet", "source_revision": entry.get("source_revision"), "artifact_sha256": entry.get("artifact_sha256")}, "subjects": subjects, "selected": {**selected, "bbox_xyxy": [left, top, min(right, source.width), min(bottom, source.height)]}}
    atomic_json_write(_job_root(job) / "evidence" / "subject_inventory.json", inventory)
    return inventory


class HOI4JobInput:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "execution_profile": ("STRING", {"default": "hoi4_portraits_agent_local_nvidia_16gb"}),
            "job_contract_path": ("STRING", {"default": "jobs/<job_id>/input.json"}),
            "candidate_count": ("INT", {"default": 1, "min": 1, "max": 12}),
            "retry_limit": ("INT", {"default": 0, "min": 0, "max": 4}),
            "seed_policy": (["fixed", "derived", "random_recorded"], {"default": "derived"}),
        }}

    RETURN_TYPES = ("HOI4_JOB",)
    RETURN_NAMES = ("job",)
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/00 Portrait setup"

    def run(self, execution_profile: str, job_contract_path: str, candidate_count: int, retry_limit: int, seed_policy: str):
        # The actual JSON is loaded here so the graph cannot silently accept a
        # UI prompt or background override. The controller replaces the
        # <job_id> token before queueing.
        root = project_root(os.environ.get("HOI4_PORTRAIT_PROJECT_ROOT", Path.cwd()))
        path = _job_path(job_contract_path, root)
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            _raise(ExitCode.SOURCE_INVALID, f"job contract missing: {job_contract_path}")
        except json.JSONDecodeError as exc:
            _raise(ExitCode.INPUT_SCHEMA_INVALID, f"job contract is not valid JSON: {exc}")
        issues = validate_job(job, root)
        if issues:
            first = issues[0]
            _raise(first.code, f"{first.path}: {first.message}")
        if job.get("execution_profile") != execution_profile:
            _raise(ExitCode.WORKFLOW_INVALID, "job profile does not match the loaded workflow")
        # Internal runtime context is deliberately added only after strict
        # contract validation. The public job schema has additionalProperties
        # disabled, so validating the context-enriched object would reject the
        # node's own private fields before any workflow stage can run.
        job["_project_root"] = str(root)
        job["_workflow_execution_profile"] = execution_profile
        return (job,)


class HOI4PromptJobInput:
    """Load an agent prompt-only job without requiring a source portrait."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "execution_profile": ("STRING", {"default": "hoi4_portraits_agent_no_input_local_nvidia_16gb"}),
            "job_contract_path": ("STRING", {"default": "jobs/<job_id>/input.json"}),
            "candidate_count": ("INT", {"default": 1, "min": 1, "max": 12}),
            "retry_limit": ("INT", {"default": 0, "min": 0, "max": 4}),
            "seed_policy": (["fixed", "derived", "random_recorded"], {"default": "derived"}),
        }}

    RETURN_TYPES = ("HOI4_JOB", "STRING", "HOI4_META", "INT")
    RETURN_NAMES = ("job", "prompt", "prompt_meta", "seed")
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/01 Portrait idea"

    def run(self, execution_profile: str, job_contract_path: str, candidate_count: int, retry_limit: int, seed_policy: str):
        root = project_root(os.environ.get("HOI4_PORTRAIT_PROJECT_ROOT", Path.cwd()))
        path = _job_path(job_contract_path, root)
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            _raise(ExitCode.SOURCE_INVALID, f"job contract missing: {job_contract_path}")
        except json.JSONDecodeError as exc:
            _raise(ExitCode.INPUT_SCHEMA_INVALID, f"job contract is not valid JSON: {exc}")
        issues = validate_schema(job, root / "docs" / "schemas" / "portrait_prompt_job_input.schema.json")
        if issues:
            first = issues[0]
            _raise(first.code, f"{first.path}: {first.message}")
        if job.get("execution_profile") != execution_profile:
            _raise(ExitCode.WORKFLOW_INVALID, "job profile does not match the loaded workflow")
        if int(job.get("candidate_count", 0)) > candidate_count:
            _raise(ExitCode.INPUT_SCHEMA_INVALID, "job candidate count exceeds the loaded workflow limit")
        if int(job.get("retry_limit", 0)) > retry_limit:
            _raise(ExitCode.INPUT_SCHEMA_INVALID, "job retry limit exceeds the loaded workflow limit")
        configured_seed_mode = job.get("seed_policy", {}).get("mode")
        if configured_seed_mode != seed_policy:
            _raise(ExitCode.WORKFLOW_INVALID, "job seed policy does not match the loaded workflow")
        configured_seed = job.get("seed_policy", {}).get("seed")
        if configured_seed_mode in {"fixed", "random_recorded"}:
            if not isinstance(configured_seed, int) or isinstance(configured_seed, bool) or configured_seed < 0:
                _raise(ExitCode.INPUT_SCHEMA_INVALID, f"{configured_seed_mode} seed policy requires a recorded non-negative seed")
            resolved_seed = configured_seed
        else:
            material = f"{job.get('job_id')}:{job.get('prompt')}".encode("utf-8")
            resolved_seed = int.from_bytes(hashlib.sha256(material).digest()[:8], "big")
        subject = job.get("subject_identity")
        record_name = subject.get("record_name") if isinstance(subject, dict) else None
        result = validate_prompt(
            prompt=str(job.get("prompt", "")),
            record_name=record_name,
            allowed_claims=job.get("allowed_autoprompt_claims"),
        )
        if not result.passed:
            _raise(ExitCode.INPUT_SCHEMA_INVALID, "; ".join(result.failure_codes + result.findings))
        job["_project_root"] = str(root)
        job["_workflow_execution_profile"] = execution_profile
        return job, result.normalized_prompt, {
            "source": "job_contract",
            "validator": result.as_dict(),
            "source_image_required": False,
            "seed": resolved_seed,
        }, resolved_seed


class HOI4HumanControls:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "job": ("HOI4_JOB",),
            "source_image_path": ("STRING", {"default": "<from_job_contract>"}),
            "subject_selector_mode": (["automatic", "face_index", "bbox"], {"default": "automatic"}),
            "face_index": ("INT", {"default": 0, "min": 0, "max": 63}),
            "bbox_left": ("INT", {"default": 0, "min": 0}),
            "bbox_top": ("INT", {"default": 0, "min": 0}),
            "bbox_right": ("INT", {"default": 0, "min": 0}),
            "bbox_bottom": ("INT", {"default": 0, "min": 0}),
            "crop_override_left": ("INT", {"default": 0, "min": 0}),
            "crop_override_top": ("INT", {"default": 0, "min": 0}),
            "crop_override_right": ("INT", {"default": 0, "min": 0}),
            "crop_override_bottom": ("INT", {"default": 0, "min": 0}),
            "approved_background_registry_id": ("STRING", {"default": "<from_job_contract>"}),
            "background_choice": (["Keep current background", "Scientist laboratory", "Operative background"], {"default": "Keep current background"}),
            "seed_mode": (["fixed", "derived", "random_recorded"], {"default": "derived"}),
            "fixed_seed": ("INT", {"default": 0, "min": 0}),
            "candidate_count": ("INT", {"default": 1, "min": 1, "max": 6}),
            "output_job_id": ("STRING", {"default": "<job_id_from_contract>"}),
        }, "optional": {}}

    RETURN_TYPES = ("HOI4_JOB", "HOI4_META")
    RETURN_NAMES = ("job", "control_meta")
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/00 Portrait setup"

    def run(self, job: dict[str, Any], source_image_path: str, subject_selector_mode: str, face_index: int, bbox_left: int, bbox_top: int, bbox_right: int, bbox_bottom: int, crop_override_left: int, crop_override_top: int, crop_override_right: int, crop_override_bottom: int, approved_background_registry_id: str, background_choice: str, seed_mode: str, fixed_seed: int, candidate_count: int, output_job_id: str):
        root = _project_from_job(job)
        if output_job_id not in {"", "<job_id_from_contract>", str(job.get("job_id"))}:
            _raise(ExitCode.WORKFLOW_INVALID, "human control output_job_id cannot change the validated job root")
        updated = json.loads(json.dumps(job))
        resolved_source = source_image_path if source_image_path not in {"", "<from_job_contract>"} else updated.get("source_image_path")
        if not isinstance(resolved_source, str) or Path(resolved_source).is_absolute():
            _raise(ExitCode.SOURCE_INVALID, "human source control must be a project-relative path")
        try:
            source_path = relative_safe_path(root, resolved_source)
        except ValueError:
            _raise(ExitCode.SOURCE_INVALID, "human source control escapes the project root")
        if not source_path.is_file():
            _raise(ExitCode.SOURCE_INVALID, "human source control points to a missing image")
        updated["source_image_path"] = resolved_source
        if subject_selector_mode == "automatic":
            # Retain an explicit selector already present in the validated job;
            # otherwise the subject node will require an audited inventory.
            pass
        elif subject_selector_mode == "face_index":
            updated["subject_selector"] = {"mode": "face_index", "face_index": int(face_index)}
        elif subject_selector_mode == "bbox":
            bbox = [int(bbox_left), int(bbox_top), int(bbox_right), int(bbox_bottom)]
            if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
                _raise(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "human bbox control is empty")
            updated["subject_selector"] = {"mode": "bbox", "bbox_xyxy": bbox}
        else:
            _raise(ExitCode.INPUT_SCHEMA_INVALID, "unknown human subject-selector mode")
        if candidate_count < 1 or candidate_count > int(PROFILE_LIMITS[str(job.get("execution_profile"))]["candidate_max"]):
            _raise(ExitCode.INPUT_SCHEMA_INVALID, "human candidate count exceeds the locked profile ceiling")
        updated["candidate_count"] = int(candidate_count)
        if seed_mode == "fixed":
            updated["seed_policy"] = {"mode": "fixed", "seed": int(fixed_seed)}
        elif seed_mode in {"derived", "random_recorded"}:
            updated["seed_policy"] = {"mode": seed_mode}
        else:
            _raise(ExitCode.INPUT_SCHEMA_INVALID, "unknown human seed mode")
        if background_choice not in {"Keep current background", "Scientist laboratory", "Operative background"}:
            _raise(ExitCode.INPUT_SCHEMA_INVALID, "unknown portrait background choice")
        if approved_background_registry_id not in {"", "<from_job_contract>"}:
            registry_path = root / "config" / "background_registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.is_file() else {}
            matches = [
                item
                for item in registry.get("backgrounds", [])
                if item.get("registry_id") == approved_background_registry_id
                and item.get("status") in {"APPROVED", "APPROVED_LOCAL_COPY_REQUIRED"}
            ]
            if not matches:
                _raise(ExitCode.BACKGROUND_UNRESOLVED, "human background control does not identify an approved registry entry")
            entry = matches[0]
            updated["approved_background"] = {"registry_id": entry["registry_id"], "path": entry.get("runtime_path") or entry.get("path"), "sha256": entry.get("sha256")}
        # The control node is allowed to change only the documented human
        # controls. Revalidate the resulting contract before it reaches any
        # producer node.
        hidden = {key: updated.pop(key) for key in tuple(updated) if key.startswith("_")}
        issues = validate_job(updated, root)
        updated.update(hidden)
        if issues:
            first = issues[0]
            _raise(first.code, f"{first.path}: {first.message}")
        crop_override = [int(crop_override_left), int(crop_override_top), int(crop_override_right), int(crop_override_bottom)]
        if not (crop_override[0] == crop_override[1] == crop_override[2] == crop_override[3] == 0):
            if crop_override[2] <= crop_override[0] or crop_override[3] <= crop_override[1] or crop_override[2] - crop_override[0] <= 0:
                _raise(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "human crop override is empty")
        control_meta = {"source": resolved_source, "subject_selector_mode": subject_selector_mode, "crop_override_xyxy": crop_override if any(crop_override) else None, "approved_background_registry_id": updated.get("approved_background", {}).get("registry_id"), "background_choice": background_choice, "seed_mode": seed_mode, "candidate_count": int(candidate_count), "output_job_id": updated.get("job_id")}
        return updated, control_meta


class HOI4JobSource:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"job": ("HOI4_JOB",)}}

    RETURN_TYPES = ("IMAGE", "HOI4_META")
    RETURN_NAMES = ("image", "source_meta")
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/00 Portrait setup"

    def run(self, job: dict[str, Any]):
        if Image is None:
            _raise(ExitCode.DEPENDENCY_MISSING, "Pillow is required to load the source portrait")
        root, job_root = _read_project_job(job)
        path_value = str(job["source_image_path"])
        try:
            path = relative_safe_path(root, path_value)
        except ValueError:
            _raise(ExitCode.SOURCE_INVALID, "source portrait path escapes the project root")
        if not path.is_file():
            _raise(ExitCode.SOURCE_INVALID, f"source portrait is missing: {path_value}")
        actual = sha256_file(path)
        original_target = relative_safe_path(job_root, f"source/original/{path.name}")
        original_target.parent.mkdir(parents=True, exist_ok=True)
        if original_target.is_file() and sha256_file(original_target) != actual:
            _raise(ExitCode.SOURCE_INVALID, "immutable source snapshot conflicts with the current source bytes")
        if not original_target.is_file():
            with tempfile.NamedTemporaryFile("wb", dir=original_target.parent, prefix=f".{original_target.name}.", suffix=".tmp", delete=False) as target_handle:
                temporary = Path(target_handle.name)
                with path.open("rb") as source_handle:
                    while chunk := source_handle.read(1024 * 1024):
                        target_handle.write(chunk)
            try:
                os.replace(temporary, original_target)
            finally:
                if temporary.exists():
                    temporary.unlink()
            if not original_target.is_file() or sha256_file(original_target) != actual:
                _raise(ExitCode.SOURCE_INVALID, "immutable source snapshot checksum verification failed")
        try:
            with Image.open(path) as opened:
                fmt = opened.format
                width, height = opened.size
                if not _source_format_allowed(fmt):
                    _raise(ExitCode.SOURCE_INVALID, f"unsupported source image format: {fmt}")
                if width <= 0 or height <= 0 or width * height > 50_000_000:
                    _raise(ExitCode.SOURCE_INVALID, "source image dimensions are unsafe")
                orientation = opened.getexif().get(274, 1)
                image = ImageOps.exif_transpose(opened).convert("RGB") if ImageOps is not None else opened.convert("RGB")
                image.load()
        except Exception as exc:
            if isinstance(exc, RuntimeError):
                raise
            _raise(ExitCode.SOURCE_INVALID, f"source image decode failed: {type(exc).__name__}")
        decoded_target = relative_safe_path(job_root, "source/decoded/master.png")
        decoded_record = _write_image(decoded_target, image)
        source_meta = {"path": str(path.relative_to(root)), "original_path": str(original_target.relative_to(job_root)), "decoded_master": str(decoded_target.relative_to(job_root)), "sha256": actual, "size_bytes": path.stat().st_size, "format": fmt, "original_dimensions": [width, height], "orientation_tag": orientation, "orientation_transform": "EXIF transpose" if orientation not in {None, 1} else "identity", "decoded_pixel_sha256": decoded_record["pixel_sha256"], "source_provenance": job.get("source_provenance")}
        atomic_json_write(job_root / "evidence" / "source_intake.json", source_meta)
        return (_pil_to_comfy(image), source_meta)


class HOI4SourceGuard:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"job": ("HOI4_JOB",), "image": ("IMAGE",)}}

    RETURN_TYPES = ("IMAGE", "HOI4_META")
    RETURN_NAMES = ("image", "source_meta")
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/00 Portrait setup"

    def run(self, job: dict[str, Any], image: Any):
        root = _project_from_job(job)
        try:
            path = relative_safe_path(root, job["source_image_path"])
        except ValueError:
            _raise(ExitCode.SOURCE_INVALID, "source path escapes the project root")
        if not path.is_file():
            _raise(ExitCode.SOURCE_INVALID, "source disappeared during execution")
        provenance = job.get("source_provenance", {})
        if not provenance.get("attribution") or not provenance.get("rights_notes"):
            _raise(ExitCode.PROVENANCE_MISSING, "source attribution and rights notes are required")
        return image, {"source_sha256": sha256_file(path), "provenance": provenance}


class HOI4SubjectSelect:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"job": ("HOI4_JOB",), "image": ("IMAGE",)}}

    RETURN_TYPES = ("IMAGE", "HOI4_META")
    RETURN_NAMES = ("image", "selection_meta")
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/01 Choose subject"

    def run(self, job: dict[str, Any], image: Any):
        selector = job.get("subject_selector")
        if selector is None:
            inventory_path = _job_root(job) / "evidence" / "subject_inventory.json"
            if not inventory_path.is_file():
                _write_subject_inventory(job, image)
            selector = {"mode": "subject_hint", "subject_hint": "service_selected_subject"}
        if not isinstance(selector, dict) or selector.get("mode") not in {"bbox", "face_index", "subject_hint"}:
            _raise(ExitCode.INPUT_SCHEMA_INVALID, "subject selector is invalid")
        if selector.get("mode") == "bbox":
            bbox = selector.get("bbox_xyxy")
            if not isinstance(bbox, list) or len(bbox) != 4 or not all(isinstance(value, int) and value >= 0 for value in bbox):
                _raise(ExitCode.INPUT_SCHEMA_INVALID, "bbox selector must contain four non-negative integers")
            left, top, right, bottom = bbox
            if right <= left or bottom <= top or left >= int(image.shape[2]) or top >= int(image.shape[1]):
                _raise(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "subject bbox is outside the decoded source")
            right = min(right, int(image.shape[2]))
            bottom = min(bottom, int(image.shape[1]))
            if right - left < 8 or bottom - top < 8:
                _raise(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "subject bbox is too small for an auditable portrait")
            inventory_path = _job_root(job) / "evidence" / "subject_inventory.json"
            if not inventory_path.is_file():
                _write_subject_inventory(job, image)
            try:
                inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                _raise(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, f"subject inventory is invalid: {exc}")
            if inventory.get("analysis_status") != "PASS" or not isinstance(inventory.get("subjects"), list):
                _raise(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "bbox selection requires an auditable subject inventory")

            def iou(candidate: list[int]) -> float:
                c_left, c_top, c_right, c_bottom = candidate
                inter_left, inter_top = max(left, c_left), max(top, c_top)
                inter_right, inter_bottom = min(right, c_right), min(bottom, c_bottom)
                intersection = max(0, inter_right - inter_left) * max(0, inter_bottom - inter_top)
                union = (right - left) * (bottom - top) + max(0, c_right - c_left) * max(0, c_bottom - c_top) - intersection
                return intersection / union if union else 0.0

            matches = []
            for subject in inventory["subjects"]:
                candidate = subject.get("bbox_xyxy") if isinstance(subject, dict) else None
                if isinstance(candidate, list) and len(candidate) == 4 and all(isinstance(value, int) and not isinstance(value, bool) for value in candidate):
                    overlap = iou(candidate)
                    if overlap >= 0.5:
                        matches.append((overlap, subject))
            if not matches:
                _raise(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "contract bbox does not overlap an auditable YuNet/person-associated subject")
            matches.sort(key=lambda item: (-item[0], item[1].get("subject_index", 0)))
            if len(matches) > 1 and matches[0][0] == matches[1][0]:
                _raise(ExitCode.AMBIGUOUS_SUBJECT, "contract bbox overlaps multiple equally plausible audited subjects")
            selected = matches[0][1]
            audited_bbox = selected["bbox_xyxy"]
            return image, {"selector": selector, "selection": "audited_contract_bbox", "bbox_xyxy": audited_bbox, "requested_bbox_xyxy": [left, top, right, bottom], "inventory_path": str(inventory_path.relative_to(_job_root(job))), "inventory_sha256": sha256_file(inventory_path), "face_analysis": inventory.get("analysis_status", "unverified"), "selected_subject_index": selected.get("subject_index")}
        inventory_path = _job_root(job) / "evidence" / "subject_inventory.json"
        if not inventory_path.is_file():
            _write_subject_inventory(job, image)
        try:
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            _raise(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, f"subject inventory is invalid: {exc}")
        if inventory.get("analysis_status") != "PASS":
            _raise(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "subject inventory is not an auditable PASS result")
        subjects = inventory.get("subjects")
        if not isinstance(subjects, list) or not subjects:
            _raise(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "subject inventory has no auditable proposals")
        if selector.get("mode") == "face_index":
            face_index = selector.get("face_index")
            if not isinstance(face_index, int) or isinstance(face_index, bool) or face_index < 0:
                _raise(ExitCode.INPUT_SCHEMA_INVALID, "face_index must be a non-negative integer")
            if face_index >= len(subjects):
                _raise(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "face_index is outside the auditable subject inventory")
            selected = subjects[face_index]
            selection_label = "audited_face_index"
        else:
            selected = inventory.get("selected")
            selection_label = "audited_inventory"
        if not isinstance(selected, dict) or not isinstance(selected.get("bbox_xyxy"), list):
            _raise(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "subject inventory has no selected auditable face")
        bbox = selected["bbox_xyxy"]
        if len(bbox) != 4 or not all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in bbox):
            _raise(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "subject inventory selected an invalid bbox")
        left, top, right, bottom = bbox
        if right <= left or bottom <= top or left >= int(image.shape[2]) or top >= int(image.shape[1]):
            _raise(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "subject inventory selected a bbox outside the decoded source")
        right = min(right, int(image.shape[2]))
        bottom = min(bottom, int(image.shape[1]))
        if right - left < 8 or bottom - top < 8:
            _raise(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "subject inventory selected a bbox too small for an auditable portrait")
        return image, {"selector": selector, "selection": selection_label, "bbox_xyxy": [left, top, right, bottom], "inventory_path": str(inventory_path.relative_to(_job_root(job))), "inventory_sha256": sha256_file(inventory_path), "face_analysis": inventory.get("analysis_status", "unverified"), "selected_subject_index": selector.get("face_index") if selector.get("mode") == "face_index" else None}


class HOI4HeadShouldersCrop:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"job": ("HOI4_JOB",), "image": ("IMAGE",), "selection_meta": ("HOI4_META",)}, "optional": {"control_meta": ("HOI4_META",)}}

    RETURN_TYPES = ("IMAGE", "HOI4_META")
    RETURN_NAMES = ("image", "crop_meta")
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/02 Crop portrait"

    def run(self, job: dict[str, Any], image: Any, selection_meta: dict[str, Any], control_meta: dict[str, Any] | None = None):
        if Image is None or ImageOps is None:
            _raise(ExitCode.DEPENDENCY_MISSING, "Pillow is required for exact crop generation")
        source = _comfy_to_pil(image)
        bbox = selection_meta.get("bbox_xyxy") if isinstance(selection_meta, dict) else None
        if not isinstance(bbox, list) or len(bbox) != 4:
            _raise(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "subject selection has no usable bbox")
        left, top, right, bottom = [int(value) for value in bbox]
        if not (0 <= left < right <= source.width and 0 <= top < bottom <= source.height):
            _raise(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "subject bbox is outside the decoded master")
        explicit = control_meta.get("crop_override_xyxy") if isinstance(control_meta, dict) and control_meta.get("crop_override_xyxy") else selection_meta.get("crop_xyxy") if isinstance(selection_meta, dict) else None
        if isinstance(explicit, list) and len(explicit) == 4:
            crop_left, crop_top, crop_right, crop_bottom = [int(value) for value in explicit]
            derived_crop = False
        else:
            face_width = right - left
            face_height = bottom - top
            target_height = max(96, int(round(face_height * 2.35)))
            maximum_height = min(source.height, int(source.width * 35 / 26))
            target_height = min(target_height, maximum_height)
            target_width = int(round(target_height * 26 / 35))
            center_x = (left + right) / 2.0
            center_y = (top + bottom) / 2.0
            crop_left = int(round(center_x - target_width / 2.0))
            crop_top = int(round(center_y - target_height * 0.30))
            crop_left = min(max(0, crop_left), source.width - target_width)
            crop_top = min(max(0, crop_top), source.height - target_height)
            crop_right = crop_left + target_width
            crop_bottom = crop_top + target_height
            derived_crop = True
        if crop_right <= crop_left or crop_bottom <= crop_top:
            _raise(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "calculated crop is empty")
        crop_width = crop_right - crop_left
        crop_height = crop_bottom - crop_top
        if crop_width * 35 != crop_height * 26:
            # Correct only the derived/explicit canvas dimensions; do not
            # silently alter the selected face or invent a new pose.
            crop_height = int(round(crop_width * 35 / 26))
            crop_bottom = crop_top + crop_height
        source_left = max(0, crop_left)
        source_top = max(0, crop_top)
        source_right = min(source.width, crop_right)
        source_bottom = min(source.height, crop_bottom)
        if source_right <= source_left or source_bottom <= source_top:
            _raise(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "crop does not intersect the source")
        if derived_crop:
            canvas = source.crop((crop_left, crop_top, crop_right, crop_bottom)).convert("RGB")
            padding = {"left": 0, "top": 0, "right": 0, "bottom": 0}
        else:
            canvas = Image.new("RGB", (crop_width, crop_height), (0, 0, 0))
            patch = source.crop((source_left, source_top, source_right, source_bottom))
            canvas.paste(patch, (source_left - crop_left, source_top - crop_top))
            padding = {"left": max(0, -crop_left), "top": max(0, -crop_top), "right": max(0, crop_right - source.width), "bottom": max(0, crop_bottom - source.height)}
        profile = str(job.get("execution_profile", ""))
        limits = PROFILE_LIMITS.get(profile)
        if limits:
            maximum_output = (int(limits["canvas_width"]), int(limits["canvas_height"]))
            if canvas.width > maximum_output[0] or canvas.height > maximum_output[1]:
                canvas = ImageOps.fit(canvas, maximum_output, method=Image.Resampling.LANCZOS)
        meta = {"job_id": job.get("job_id"), "crop_xyxy": [crop_left, crop_top, crop_right, crop_bottom], "source_intersection_xyxy": [source_left, source_top, source_right, source_bottom], "padding": padding, "aspect_ratio": "26:35", "selected_bbox_xyxy": [left, top, right, bottom], "output_size": [canvas.width, canvas.height], "pixel_sha256": _pixel_digest(canvas), "source_pixel_preserved_inside_intersection": True}
        decoded = _pil_to_comfy(canvas)
        job_root = _job_root(job)
        meta["evidence_path"] = str((job_root / "evidence" / "reference" / "crop.png").relative_to(job_root))
        _write_image(job_root / "evidence" / "reference" / "crop.png", canvas)
        atomic_json_write(job_root / "evidence" / "crop.json", meta)
        return decoded, meta


class HOI4ConservativePrep:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "job": ("HOI4_JOB",),
                "image": ("IMAGE",),
                "crop_meta": ("HOI4_META",),
                "enhanced_image": ("IMAGE",),
            },
            "optional": {
                "control_meta": ("HOI4_META",),
                "preparation_engine": (
                    [
                        "RealESRGAN x2",
                        "Qwen Image Edit 2511 and RealESRGAN x2",
                    ],
                ),
            },
        }

    RETURN_TYPES = ("IMAGE", "HOI4_META")
    RETURN_NAMES = ("image", "reference_meta")
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/03 Prepare portrait"

    def run(
        self,
        job: dict[str, Any],
        image: Any,
        crop_meta: dict[str, Any],
        enhanced_image: Any,
        control_meta: dict[str, Any] | None = None,
        preparation_engine: str = "RealESRGAN x2",
    ):
        if Image is None:
            _raise(ExitCode.DEPENDENCY_MISSING, "Pillow is required for source preparation")
        source = _comfy_to_pil(image).convert("RGB")
        enhanced = _comfy_to_pil(enhanced_image).convert("RGB")
        profile = str(job.get("execution_profile", ""))
        limits = PROFILE_LIMITS.get(profile)
        if not limits:
            _raise(ExitCode.WORKFLOW_INVALID, "job execution profile is unknown")
        supported_engines = {
            "RealESRGAN x2",
            "Qwen Image Edit 2511 and RealESRGAN x2",
        }
        if preparation_engine not in supported_engines:
            _raise(ExitCode.WORKFLOW_INVALID, "portrait preparation engine is not supported")
        target = (int(limits["canvas_width"]), int(limits["canvas_height"]))
        if enhanced.size != target:
            prepared = enhanced.resize(target, Image.Resampling.LANCZOS)
            resize_operation = "LANCZOS_TO_PROFILE_CANVAS"
        else:
            prepared = enhanced
            resize_operation = "IDENTITY_SIZE"
        qwen_restoration = preparation_engine.startswith("Qwen Image Edit 2511")
        meta = {
            "crop_meta": crop_meta,
            "restoration": {
                "status": "AI_RESTORATION_AND_UPSCALE_APPLIED" if qwen_restoration else "AI_UPSCALE_APPLIED",
                "model": preparation_engine,
                "operations": (
                    ["Qwen-Image-Edit-2511 FP8 mixed", "Real-ESRGAN_x2plus", resize_operation]
                    if qwen_restoration
                    else ["Real-ESRGAN_x2plus", resize_operation]
                ),
            },
            "colorization": {
                "status": "AI_RESTORATION_ENABLED" if qwen_restoration else "NOT_USED",
                "source_color_preserved": not qwen_restoration,
            },
            "source_size": {"width": source.width, "height": source.height},
            "work_canvas": {"width": prepared.width, "height": prepared.height},
            "pixel_sha256": _pixel_digest(prepared),
        }
        job_root = _job_root(job)
        _write_image(job_root / "evidence" / "reference" / "processed.png", prepared)
        atomic_json_write(job_root / "evidence" / "reference" / "processed.json", meta)
        return _pil_to_comfy(prepared), meta


class HOI4RestorationPrompt:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "restoration_mode": (
                    [
                        "Restore and colorize when needed",
                        "Restore without changing color",
                        "Use my instructions",
                    ],
                ),
                "custom_instructions": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "dynamicPrompts": False,
                    },
                ),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("restoration_instructions",)
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/03 Prepare portrait"

    _PRESERVATION_RULES = (
        "Preserve the subject's identity, facial geometry, expression, pose, hairstyle, "
        "clothing, insignia, accessories, framing, and background. Do not add, remove, "
        "replace, or redesign any person, object, uniform feature, medal, symbol, or "
        "background element. Keep the person's age and appearance unchanged. Produce a "
        "clean high-resolution photographic restoration, not an illustration."
    )

    def run(self, restoration_mode: str, custom_instructions: str):
        if restoration_mode == "Restore and colorize when needed":
            task = (
                "Restore this historical portrait photograph at high fidelity. Remove blur, "
                "fading, scratches, compression artifacts, halftone patterns, dust, and noise. "
                "Reconstruct natural facial detail and fabric texture. If the source is monochrome "
                "or sepia, colorize it with restrained, historically plausible natural colors. "
                "If it already contains color, preserve and correct the existing palette."
            )
        elif restoration_mode == "Restore without changing color":
            task = (
                "Restore this historical portrait photograph at high fidelity. Remove blur, "
                "fading, scratches, compression artifacts, halftone patterns, dust, and noise. "
                "Reconstruct natural facial detail and fabric texture while preserving the "
                "source image's existing monochrome, sepia, or color treatment."
            )
        elif restoration_mode == "Use my instructions":
            task = " ".join(str(custom_instructions).replace("\r", " ").replace("\n", " ").split())
            if not task:
                _raise(ExitCode.INPUT_SCHEMA_INVALID, "custom restoration instructions are empty")
        else:
            _raise(ExitCode.INPUT_SCHEMA_INVALID, "restoration mode is not supported")
        return (f"{task} {self._PRESERVATION_RULES}",)


class HOI4PortraitCrop:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "face_index": ("INT", {"default": 0, "min": 0, "max": 20, "step": 1}),
                "framing": (["Normal head and shoulders", "Wider shoulders", "Tighter portrait"],),
            }
        }

    RETURN_TYPES = ("IMAGE", "HOI4_META")
    RETURN_NAMES = ("cropped_portrait", "crop_details")
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/02 Crop portrait"

    def run(self, image: Any, face_index: int, framing: str):
        if Image is None or ImageOps is None:
            _raise(ExitCode.DEPENDENCY_MISSING, "Pillow is required to crop the portrait")
        try:
            import cv2  # type: ignore
            import numpy as np  # type: ignore
        except (ImportError, ModuleNotFoundError):
            _raise(ExitCode.DEPENDENCY_MISSING, "OpenCV is required to find the face")
        root = _standalone_project_root()
        entry = _preprocessing_entry(root, "YuNet")
        model_path = relative_safe_path(root, str(entry["destination_path"]))
        source = _comfy_to_pil(image).convert("RGB")
        rgb = np.asarray(source)
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        detector = cv2.FaceDetectorYN.create(
            str(model_path),
            "",
            (source.width, source.height),
            score_threshold=0.45,
            nms_threshold=0.3,
            top_k=5000,
        )
        _, detections = detector.detect(bgr)
        if detections is None or len(detections) == 0:
            _raise(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "no usable face was found in the image")
        faces = sorted(
            detections.tolist(),
            key=lambda row: (-(float(row[2]) * float(row[3])), float(row[0]), float(row[1])),
        )
        if face_index >= len(faces):
            _raise(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, f"face {face_index} was not found; detected {len(faces)} face(s)")
        x, y, face_width, face_height = [float(value) for value in faces[face_index][:4]]
        height_multiplier = {
            "Tighter portrait": 2.0,
            "Normal head and shoulders": 2.35,
            "Wider shoulders": 3.0,
        }.get(framing)
        if height_multiplier is None:
            _raise(ExitCode.INPUT_SCHEMA_INVALID, "portrait framing choice is invalid")
        crop_height = max(96, int(round(face_height * height_multiplier)))
        maximum_height = min(source.height, int(source.width * 35 / 26))
        crop_height = min(crop_height, maximum_height)
        crop_width = int(round(crop_height * 26 / 35))
        center_x = x + face_width / 2.0
        face_center_y = y + face_height / 2.0
        crop_left = int(round(center_x - crop_width / 2.0))
        crop_top = int(round(face_center_y - crop_height * 0.28))
        crop_left = min(max(0, crop_left), source.width - crop_width)
        crop_top = min(max(0, crop_top), source.height - crop_height)
        crop_right = crop_left + crop_width
        crop_bottom = crop_top + crop_height
        prepared = source.crop((crop_left, crop_top, crop_right, crop_bottom))
        if prepared.width > 832 or prepared.height > 1120:
            prepared = ImageOps.fit(prepared, (832, 1120), method=Image.Resampling.LANCZOS)
        details = {
            "detected_faces": len(faces),
            "selected_face": int(face_index),
            "framing": framing,
            "face_box_xywh": [round(x), round(y), round(face_width), round(face_height)],
            "crop_box_xyxy": [crop_left, crop_top, crop_right, crop_bottom],
            "output_size": [prepared.width, prepared.height],
            "padding": {"left": 0, "top": 0, "right": 0, "bottom": 0},
        }
        return _pil_to_comfy(prepared), details


class HOI4FinishPreparedPortrait:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "contrast": ("FLOAT", {"default": 1.04, "min": 0.8, "max": 1.3, "step": 0.01}),
                "sharpness": ("FLOAT", {"default": 1.08, "min": 0.8, "max": 1.5, "step": 0.01}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("prepared_portrait",)
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/03 Enhance portrait"

    def run(self, image: Any, contrast: float, sharpness: float):
        if ImageEnhance is None or ImageOps is None:
            _raise(ExitCode.DEPENDENCY_MISSING, "Pillow is required to finish the portrait")
        source = _comfy_to_pil(image).convert("RGB")
        finished = ImageEnhance.Contrast(source).enhance(float(contrast))
        finished = ImageEnhance.Sharpness(finished).enhance(float(sharpness))
        finished = ImageOps.fit(finished, (832, 1120), method=Image.Resampling.LANCZOS)
        return (_pil_to_comfy(finished),)


class HOI4ForegroundMask:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"job": ("HOI4_JOB",), "image": ("IMAGE",), "reference_meta": ("HOI4_META",), "mask_model": ("STRING", {"default": "BiRefNet"})}}

    RETURN_TYPES = ("IMAGE", "MASK", "HOI4_META")
    RETURN_NAMES = ("image", "mask", "mask_meta")
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/04 Choose background"

    def run(self, job: dict[str, Any], image: Any, reference_meta: dict[str, Any], mask_model: str):
        if mask_model != "BiRefNet":
            _raise(ExitCode.WORKFLOW_INVALID, "foreground mask model is not the locked BiRefNet route")
        if torch is None or Image is None:
            _raise(ExitCode.DEPENDENCY_MISSING, "PyTorch and Pillow are required for the pinned foreground mask route")
        root = _project_from_job(job)
        entry = _preprocessing_entry(root, "BiRefNet")
        source = _comfy_to_pil(image).convert("RGB")
        image_bytes = io.BytesIO()
        source.save(image_bytes, format="PNG", optimize=False)
        response = _post_loopback_json(os.environ.get("HOI4_MASK_SERVICE_LOOPBACK", ""), {"job_id": job.get("job_id"), "model": {"name": "BiRefNet", "source_revision": entry.get("source_revision"), "artifact_sha256": entry.get("artifact_sha256")}, "image_png_base64": base64.b64encode(image_bytes.getvalue()).decode("ascii")}, service_label="mask preprocessing service")
        model = response.get("model")
        if not isinstance(model, dict) or model.get("name") != "BiRefNet" or model.get("source_revision") != entry.get("source_revision") or model.get("artifact_sha256") != entry.get("artifact_sha256"):
            _raise(ExitCode.MODEL_CHECKSUM_MISMATCH, "mask service model identity does not match the preprocessing lock")
        encoded_mask = response.get("mask_png_base64")
        if not isinstance(encoded_mask, str):
            _raise(ExitCode.MASK_AUDIT_FAILED, "mask service returned no PNG mask")
        try:
            mask_bytes = base64.b64decode(encoded_mask, validate=True)
            with Image.open(io.BytesIO(mask_bytes)) as opened:
                mask_image = opened.convert("L")
                mask_image.load()
        except (binascii.Error, ValueError, OSError) as exc:
            _raise(ExitCode.MASK_AUDIT_FAILED, f"mask service returned an undecodable mask: {type(exc).__name__}")
        if mask_image.size != source.size:
            _raise(ExitCode.MASK_AUDIT_FAILED, "mask service dimensions do not match the processed reference")
        mask_values = torch.frombuffer(bytearray(mask_image.tobytes()), dtype=torch.uint8).reshape(mask_image.height, mask_image.width).float().div(255.0).unsqueeze(0).to(device=image.device, dtype=image.dtype)
        component_payload = response.get("component_masks")
        contract = response.get("mask_contract")
        required_components = {"person_alpha", "hard_interior", "face", "hair_hat_boundary", "accessory_attention", "background", "boundary_ring"}
        if not isinstance(component_payload, dict) or not required_components.issubset(component_payload) or not isinstance(contract, dict) or contract.get("status") != "PASS_STRUCTURAL_COMPONENTS":
            _raise(ExitCode.MASK_AUDIT_FAILED, "mask service did not return the complete component-mask contract")
        component_records: dict[str, Any] = {}
        for component_name in sorted(required_components):
            descriptor = component_payload.get(component_name)
            if not isinstance(descriptor, dict) or not isinstance(descriptor.get("png_base64"), str):
                _raise(ExitCode.MASK_AUDIT_FAILED, f"mask service returned no encoded {component_name} component")
            try:
                component_bytes = base64.b64decode(descriptor["png_base64"], validate=True)
                with Image.open(io.BytesIO(component_bytes)) as opened:
                    component_image = opened.convert("L")
                    component_image.load()
            except (binascii.Error, ValueError, OSError) as exc:
                _raise(ExitCode.MASK_AUDIT_FAILED, f"mask service returned an undecodable {component_name} component: {type(exc).__name__}")
            if component_image.size != source.size:
                _raise(ExitCode.MASK_AUDIT_FAILED, f"mask service {component_name} dimensions do not match the processed reference")
            component_path = _job_root(job) / "evidence" / "mask" / "components" / f"{component_name}.png"
            written = _write_image(component_path, component_image)
            relative_component_path = str(component_path.relative_to(_job_root(job)))
            component_records[component_name] = {"path": relative_component_path, "sha256": written["sha256"], "pixel_sha256": written["pixel_sha256"], "width": component_image.width, "height": component_image.height, "mode": component_image.mode, "binary": bool(descriptor.get("binary")), "semantics": descriptor.get("semantics")}
        mask_record = {"model": model, "analysis_status": "PASS", "mask_path": "evidence/mask/foreground.png", "mask_sha256": _pixel_digest(mask_image), "reference_meta": reference_meta, "mask_contract": contract, "component_masks": component_records, "component_comparison_status": contract.get("alternative_matting_comparison", {}).get("status") if isinstance(contract.get("alternative_matting_comparison"), dict) else "UNKNOWN"}
        _write_image(_job_root(job) / "evidence" / "mask" / "foreground.png", mask_image)
        atomic_json_write(_job_root(job) / "evidence" / "mask" / "foreground.json", mask_record)
        return image, mask_values, mask_record


class HOI4BundledBackground:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "asset_path": ("STRING", {"default": HOI4_SCIENTIST_BACKGROUND_RUNTIME_PATH}),
            "asset_sha256": ("STRING", {"default": HOI4_SCIENTIST_BACKGROUND_SHA256}),
        }}

    RETURN_TYPES = ("IMAGE", "HOI4_META")
    RETURN_NAMES = ("image", "background_details")
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/04 Background"

    def run(self, asset_path: str, asset_sha256: str):
        supported_assets = {
            HOI4_SCIENTIST_BACKGROUND_RUNTIME_PATH: {
                "registry_id": HOI4_SCIENTIST_BACKGROUND_REGISTRY_ID,
                "sha256": HOI4_SCIENTIST_BACKGROUND_SHA256,
                "name": "scientist",
            },
            HOI4_OPERATIVE_BACKGROUND_RUNTIME_PATH: {
                "registry_id": HOI4_OPERATIVE_BACKGROUND_REGISTRY_ID,
                "sha256": HOI4_OPERATIVE_BACKGROUND_SHA256,
                "name": "operative",
            },
        }
        selected = supported_assets.get(asset_path)
        if selected is None:
            _raise(ExitCode.BACKGROUND_UNRESOLVED, "unsupported HOI4 portrait background path")
        if asset_sha256 != selected["sha256"]:
            _raise(ExitCode.MODEL_CHECKSUM_MISMATCH, f"{selected['name']} background checksum setting is incorrect")
        root = project_root(os.environ.get("HOI4_PORTRAIT_PROJECT_ROOT", Path.cwd()))
        path = relative_safe_path(root, asset_path)
        if Image is None:
            _raise(ExitCode.DEPENDENCY_MISSING, "Pillow is required to load an HOI4 portrait background")
        if not path.is_file():
            placeholder = Image.new("RGB", (312, 420), (12, 18, 24))
            return _pil_to_comfy(placeholder), {
                "registry_id": selected["registry_id"],
                "asset_path": asset_path,
                "asset_sha256": asset_sha256,
                "available": False,
                "pixel_sha256": _pixel_digest(placeholder),
            }
        if sha256_file(path) != asset_sha256:
            _raise(ExitCode.MODEL_CHECKSUM_MISMATCH, f"the copied HOI4 {selected['name']} background has changed")
        with Image.open(path) as opened:
            image = opened.convert("RGB")
            image.load()
        return _pil_to_comfy(image), {
            "registry_id": selected["registry_id"],
            "asset_path": asset_path,
            "asset_sha256": asset_sha256,
            "available": True,
            "pixel_sha256": _pixel_digest(image),
        }


class HOI4MaskAndBackgroundGuard:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"job": ("HOI4_JOB",), "image": ("IMAGE",), "mask": ("MASK",), "mask_meta": ("HOI4_META",)},
            "optional": {
                "control_meta": ("HOI4_META",),
                "scientist_background": ("IMAGE",),
                "scientist_background_meta": ("HOI4_META",),
                "operative_background": ("IMAGE",),
                "operative_background_meta": ("HOI4_META",),
            },
        }

    RETURN_TYPES = ("IMAGE", "IMAGE", "MASK", "HOI4_META")
    RETURN_NAMES = ("image", "composite", "mask", "background_meta")
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/04 Choose background"

    def run(
        self,
        job: dict[str, Any],
        image: Any,
        mask: Any,
        mask_meta: dict[str, Any],
        control_meta: dict[str, Any] | None = None,
        scientist_background: Any = None,
        scientist_background_meta: dict[str, Any] | None = None,
        operative_background: Any = None,
        operative_background_meta: dict[str, Any] | None = None,
    ):
        root = _project_from_job(job)
        required_components = {"person_alpha", "hard_interior", "face", "hair_hat_boundary", "accessory_attention", "background", "boundary_ring"}
        component_records = mask_meta.get("component_masks") if isinstance(mask_meta, dict) else None
        if not isinstance(component_records, dict) or not required_components.issubset(component_records) or not isinstance(mask_meta.get("mask_contract"), dict) or mask_meta.get("mask_contract", {}).get("status") != "PASS_STRUCTURAL_COMPONENTS":
            _raise(ExitCode.MASK_AUDIT_FAILED, "complete component-mask evidence is required before background compositing")
        for component_name in required_components:
            record = component_records.get(component_name)
            if not isinstance(record, dict) or not isinstance(record.get("path"), str) or not isinstance(record.get("sha256"), str):
                _raise(ExitCode.MASK_AUDIT_FAILED, f"component-mask evidence record is incomplete: {component_name}")
            try:
                component_path = relative_safe_path(_job_root(job), record["path"])
            except ValueError:
                _raise(ExitCode.MASK_AUDIT_FAILED, f"component-mask evidence path escapes the job root: {component_name}")
            if not component_path.is_file() or sha256_file(component_path) != record["sha256"]:
                _raise(ExitCode.MASK_AUDIT_FAILED, f"component-mask evidence checksum failed: {component_name}")
        background_choice = control_meta.get("background_choice") if isinstance(control_meta, dict) else None
        if background_choice == "Keep current background":
            guard_meta = {
                "background_choice": "Keep current background",
                "background_registry_id": None,
                "background_sha256": None,
                "mask_meta": mask_meta,
            }
            atomic_json_write(_job_root(job) / "evidence" / "background_composite.json", guard_meta)
            return image, image, mask, guard_meta

        registry_path = root / "config" / "background_registry.json"
        if not registry_path.is_file():
            _raise(ExitCode.BACKGROUND_UNRESOLVED, "background registry is missing")
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        requested = job.get("approved_background", {})
        selected_local_background: tuple[str, Any, dict[str, Any] | None] | None = None
        if background_choice in {"Scientist laboratory", "Operative background"}:
            selected_registry_id = (
                HOI4_SCIENTIST_BACKGROUND_REGISTRY_ID
                if background_choice == "Scientist laboratory"
                else HOI4_OPERATIVE_BACKGROUND_REGISTRY_ID
            )
            local_matches = [
                item for item in registry.get("backgrounds", [])
                if item.get("registry_id") == selected_registry_id
            ]
            if not local_matches:
                _raise(ExitCode.BACKGROUND_UNRESOLVED, f"{background_choice.casefold()} is not registered")
            entry = local_matches[0]
            requested = {
                "registry_id": entry.get("registry_id"),
                "path": entry.get("runtime_path"),
                "sha256": entry.get("sha256"),
            }
            selected_local_background = (
                "scientist" if background_choice == "Scientist laboratory" else "operative",
                scientist_background if background_choice == "Scientist laboratory" else operative_background,
                scientist_background_meta if background_choice == "Scientist laboratory" else operative_background_meta,
            )
        matches = [item for item in registry.get("backgrounds", []) if item.get("registry_id") == requested.get("registry_id")]
        if not matches or matches[0].get("status") != "APPROVED_LOCAL_COPY_REQUIRED" or matches[0].get("sha256") != requested.get("sha256"):
            _raise(ExitCode.BACKGROUND_UNRESOLVED, "requested background does not match an approved registry entry")
        if torch is None or Image is None:
            _raise(ExitCode.DEPENDENCY_MISSING, "PyTorch and Pillow are required for the background composite")
        background_value = matches[0].get("runtime_path")
        if not background_value:
            _raise(ExitCode.BACKGROUND_UNRESOLVED, "approved background has no runtime path")
        if requested.get("path") != background_value:
            _raise(ExitCode.BACKGROUND_UNRESOLVED, "requested background path does not match the approved registry")
        background_path = relative_safe_path(root, background_value)
        if not background_path.is_file() or sha256_file(background_path) != requested.get("sha256"):
            _raise(ExitCode.BACKGROUND_UNRESOLVED, "approved background file is missing or checksum mismatched")
        with Image.open(background_path) as background_image:
            original_background = background_image.convert("RGB")
            original_background.load()
        if selected_local_background is not None:
            background_name, node_background, node_background_meta = selected_local_background
            if node_background is None or not isinstance(node_background_meta, dict):
                _raise(ExitCode.BACKGROUND_UNRESOLVED, f"{background_name} background node is not connected")
            if (
                node_background_meta.get("available") is not True
                or node_background_meta.get("registry_id") != requested["registry_id"]
                or node_background_meta.get("asset_sha256") != requested["sha256"]
                or _pixel_digest(_comfy_to_pil(node_background).convert("RGB")) != node_background_meta.get("pixel_sha256")
            ):
                _raise(ExitCode.MODEL_CHECKSUM_MISMATCH, f"the HOI4 {background_name} background is unavailable or changed")
        background_image = original_background.resize((image.shape[2], image.shape[1]))
        background = _pil_to_comfy(background_image).to(device=image.device, dtype=image.dtype)
        working_mask = mask
        if not hasattr(working_mask, "isfinite"):
            _raise(ExitCode.MASK_AUDIT_FAILED, "foreground mask tensor is unavailable")
        if not bool(torch.isfinite(working_mask).all().item()):
            _raise(ExitCode.MASK_AUDIT_FAILED, "foreground mask contains non-finite values")
        if working_mask.ndim == 3:
            working_mask = working_mask.unsqueeze(-1)
        working_mask = working_mask.to(device=image.device, dtype=image.dtype).clamp(0, 1)
        if working_mask.shape[0] != image.shape[0] or working_mask.shape[1] != image.shape[1] or working_mask.shape[2] != image.shape[2]:
            _raise(ExitCode.MASK_AUDIT_FAILED, "foreground mask dimensions do not match the processed reference")
        composite = image * working_mask + background * (1.0 - working_mask)
        interior = working_mask >= 0.999
        interior_pixels = int(interior[..., 0].sum().item()) if interior.ndim == 4 else int(interior.sum().item())
        if interior_pixels:
            difference = (image - composite).abs()
            interior_difference = difference.masked_select(interior.expand_as(difference))
            max_difference = float(interior_difference.max().item()) if interior_difference.numel() else 0.0
            if max_difference != 0.0:
                _raise(ExitCode.MASK_AUDIT_FAILED, "composite changed an eroded foreground interior pixel")
        else:
            _raise(ExitCode.MASK_AUDIT_FAILED, "foreground mask has no hard interior")
        guard_meta = {"background_choice": background_choice or "Approved job background", "background_registry_id": requested["registry_id"], "background_sha256": requested["sha256"], "mask_semantics": "foreground_alpha; independently_audited", "foreground_integrity_required": True, "mask_meta": mask_meta, "hard_interior_pixels": interior_pixels, "interior_max_difference": 0.0, "boundary_blend_only": True}
        atomic_json_write(_job_root(job) / "evidence" / "background_composite.json", guard_meta)
        return image, composite, mask, guard_meta


class HOI4PromptInput:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"job": ("HOI4_JOB",), "background_meta": ("HOI4_META",), "prompt_source": (["job_contract"], {"default": "job_contract"})}}

    RETURN_TYPES = ("STRING", "HOI4_META")
    RETURN_NAMES = ("prompt", "prompt_meta")
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/05 Portrait description"

    def run(self, job: dict[str, Any], background_meta: dict[str, Any], prompt_source: str):
        if prompt_source != "job_contract":
            _raise(ExitCode.WORKFLOW_INVALID, "agent prompt must come from the job contract")
        result = validate_prompt(prompt=str(job.get("prompt", "")), record_name=job.get("subject_identity", {}).get("record_name"), allowed_claims=job.get("allowed_autoprompt_claims"))
        if not result.passed:
            _raise(ExitCode.INPUT_SCHEMA_INVALID, "; ".join(result.failure_codes + result.findings))
        return result.normalized_prompt, {"source": "job_contract", "validator": result.as_dict(), "background_meta": background_meta}


class HOI4RandomPortraitPrompt:
    """Build a reproducible fictional leader prompt without an image or LLM."""

    COUNTRIES = (
        "Central European",
        "Northern European",
        "Mediterranean",
        "Eastern European",
        "East Asian",
        "South Asian",
        "Middle Eastern",
        "North American",
        "Latin American",
    )
    ROLES = (
        "civilian head of government",
        "career army commander",
        "naval commander",
        "air force commander",
        "diplomat",
        "intelligence director",
        "industrial organizer",
        "scientist and administrator",
    )
    PRESENTATIONS = ("masculine", "feminine", "androgynous")
    AGES = ("young adult", "middle-aged", "older adult")
    EXPRESSIONS = (
        "calm and resolute",
        "stern and focused",
        "reserved and thoughtful",
        "confident with a restrained smile",
        "weary but determined",
    )
    CLOTHING = (
        "tailored 1940s civilian suit",
        "period service uniform",
        "formal diplomatic dress",
        "practical wartime administration attire",
        "period overcoat over formal clothing",
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "prompt_mode": (["Create a random portrait", "Use my prompt"], {"default": "Create a random portrait"}),
            "manual_prompt": ("STRING", {"multiline": True, "default": ""}),
            "character_brief": ("STRING", {"multiline": True, "default": ""}),
            "country_influence": (["random", *cls.COUNTRIES], {"default": "random"}),
            "role": (["random", *cls.ROLES], {"default": "random"}),
            "presentation": (["random", *cls.PRESENTATIONS], {"default": "random"}),
            "age": (["random", *cls.AGES], {"default": "random"}),
            "expression": (["random", *cls.EXPRESSIONS], {"default": "random"}),
            "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
            "instruction_text": ("STRING", {"multiline": True, "default": ""}),
            "instruction_path": ("STRING", {"default": RANDOM_PORTRAIT_PROMPT_PATH}),
        }}

    RETURN_TYPES = ("STRING", "HOI4_META", "INT")
    RETURN_NAMES = ("prompt", "prompt_details", "seed")
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/01 Portrait idea"

    @staticmethod
    def _choose(value: str, values: tuple[str, ...], rng: random.Random) -> str:
        if value == "random":
            return rng.choice(values)
        if value not in values:
            _raise(ExitCode.INPUT_SCHEMA_INVALID, f"unsupported random portrait option: {value}")
        return value

    def run(
        self,
        prompt_mode: str,
        manual_prompt: str,
        character_brief: str,
        country_influence: str,
        role: str,
        presentation: str,
        age: str,
        expression: str,
        seed: int,
        instruction_text: str,
        instruction_path: str,
    ):
        root = project_root(os.environ.get("HOI4_PORTRAIT_PROJECT_ROOT", Path.cwd()))
        exact_path = relative_safe_path(root, instruction_path)
        try:
            exact_instruction = exact_path.read_text(encoding="utf-8")
        except OSError as exc:
            _raise(ExitCode.DEPENDENCY_MISSING, f"random portrait instruction is unavailable: {type(exc).__name__}")
        if instruction_path != RANDOM_PORTRAIT_PROMPT_PATH or instruction_text != exact_instruction:
            _raise(ExitCode.WORKFLOW_INVALID, "random portrait instruction does not match the project file")

        if prompt_mode not in {"Create a random portrait", "Use my prompt"}:
            _raise(ExitCode.INPUT_SCHEMA_INVALID, "unknown portrait prompt mode")
        if prompt_mode == "Use my prompt":
            prompt = _manual_generation_prompt(manual_prompt, field_name="manual prompt mode")
            return prompt, {
                "source": "human_manual_prompt",
                "seed": int(seed),
                "instruction_path": instruction_path,
                "instruction_sha256": sha256_file(exact_path),
                "selected": {},
                "used_image": False,
                "used_language_model": False,
            }, int(seed)

        brief = " ".join(str(character_brief).replace("\r", " ").replace("\n", " ").split())
        if len(brief) > 500:
            _raise(ExitCode.INPUT_SCHEMA_INVALID, "character brief exceeds 500 characters")
        forbidden = ("http://", "https://", "<script", "faceswap", "face swap", "deepfake")
        if any(token in brief.casefold() for token in forbidden):
            _raise(ExitCode.INPUT_SCHEMA_INVALID, "character brief contains an unsupported instruction")

        rng = random.Random(int(seed))
        selected = {
            "country_influence": self._choose(country_influence, self.COUNTRIES, rng),
            "role": self._choose(role, self.ROLES, rng),
            "presentation": self._choose(presentation, self.PRESENTATIONS, rng),
            "age": self._choose(age, self.AGES, rng),
            "expression": self._choose(expression, self.EXPRESSIONS, rng),
            "clothing": rng.choice(self.CLOTHING),
        }

        # The free-form brief is authoritative. Random country and role values
        # are omitted when a brief is present so requests such as "random
        # British officers" cannot be contradicted by an unrelated random
        # country or civilian role. Explicit dropdown choices are still used.
        details_parts = [brief.rstrip(" .")] if brief else ["fictional original adult leader"]
        if not brief or country_influence != "random":
            details_parts.append(selected["country_influence"] + " visual influence")
        if not brief or role != "random":
            details_parts.append(selected["role"])
        details_parts.extend((
            selected["presentation"] + " presentation",
            selected["age"],
            selected["expression"] + " expression",
            selected["clothing"],
        ))
        details = ", ".join(details_parts)
        prompt = (
            "hoi4_portrait, "
            + details
            + ", chest-up formal portrait, 1936-1948 period, "
              "painterly grand-strategy game portrait, restrained historical color palette, "
              "clear facial features"
        )
        return prompt, {
            "source": "deterministic_text_only_autoprompter",
            "seed": int(seed),
            "instruction_path": instruction_path,
            "instruction_sha256": sha256_file(exact_path),
            "selected": selected,
            "used_image": False,
            "used_language_model": False,
        }, int(seed)


class HOI4AutopromptClient:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "job": ("HOI4_JOB",),
            "image": ("IMAGE",),
            "background_meta": ("HOI4_META",),
            "control_meta": ("HOI4_META",),
            "description_mode": (["Create automatically", "Use my description"], {"default": "Create automatically"}),
            "manual_description": ("STRING", {"multiline": True, "default": ""}),
            "instruction_text": ("STRING", {"multiline": True, "default": ""}),
            "instruction_path": ("STRING", {"default": "prompts/autoprompter_instruction.txt"}),
            "model_id": ("STRING", {"default": "Qwen/Qwen3-VL-4B-Instruct-GGUF"}),
            "prompt_source": (["autoprompter"], {"default": "autoprompter"}),
        }}

    RETURN_TYPES = ("STRING", "HOI4_META")
    RETURN_NAMES = ("prompt", "prompt_meta")
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/05 Portrait description"

    def run(self, job: dict[str, Any], image: Any, background_meta: dict[str, Any], control_meta: dict[str, Any], description_mode: str, manual_description: str, instruction_text: str, instruction_path: str, model_id: str, prompt_source: str):
        if prompt_source != "autoprompter":
            _raise(ExitCode.WORKFLOW_INVALID, "human autoprompter source is locked")
        if description_mode not in {"Create automatically", "Use my description"}:
            _raise(ExitCode.INPUT_SCHEMA_INVALID, "unknown portrait description mode")
        expected_model = "Qwen/Qwen3-VL-4B-Instruct-GGUF" if job.get("execution_profile") == "hoi4_portraits_local_nvidia_16gb" else "Qwen/Qwen3-VL-8B-Instruct"
        if model_id != expected_model:
            _raise(ExitCode.WORKFLOW_INVALID, f"autoprompter model does not match profile; expected {expected_model}")
        root = _project_from_job(job)
        exact_path = relative_safe_path(root, instruction_path)
        exact_instruction = exact_path.read_text(encoding="utf-8")
        if instruction_text != exact_instruction:
            _raise(ExitCode.WORKFLOW_INVALID, "autoprompter instruction does not exactly match the project file")
        if description_mode == "Use my description":
            prompt = _manual_generation_prompt(manual_description, field_name="manual description mode")
            validator = {
                "passed": True,
                "normalized_prompt": prompt,
                "failure_codes": [],
                "findings": [],
                "claims": {},
            }
            attempts = [{"attempt": 1, "status": "PASS", "source": "human_manual_override"}]
            atomic_json_write(_job_root(job) / "evidence" / "prompt" / "autoprompter_attempts.json", {"schema_version": "1.0.0", "instruction_sha256": sha256_file(exact_path), "attempts": attempts})
            return prompt, {"source": "human_manual_override", "instruction_sha256": sha256_file(exact_path), "validator": validator, "attempts": attempts, "background_meta": background_meta}
        endpoint = os.environ.get("HOI4_AUTOPROMPTER_LOOPBACK", "http://127.0.0.1:8099/v1/chat/completions")
        if not endpoint.startswith("http://127.0.0.1:") and not endpoint.startswith("http://localhost:"):
            _raise(ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED, "autoprompter is not bound to loopback")
        image_bytes = io.BytesIO()
        _comfy_to_pil(image).save(image_bytes, format="PNG", optimize=False)
        encoded = json.dumps({"instruction": exact_instruction, "job_id": job.get("job_id"), "model_id": model_id, "image_png_base64": base64.b64encode(image_bytes.getvalue()).decode("ascii"), "background_meta": background_meta, "allowed_claims": job.get("allowed_autoprompt_claims", {})}, ensure_ascii=False).encode("utf-8")
        try:
            payload = _post_autoprompt_staged(root, endpoint, json.loads(encoded.decode("utf-8")), str(job.get("execution_profile")))
        except RuntimeError:
            raise
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            _raise(ExitCode.DEPENDENCY_MISSING, f"loopback autoprompter sidecar unavailable: {type(exc).__name__}")
        prompt = str(payload.get("prompt", ""))
        result = validate_prompt(prompt, record_name=job.get("subject_identity", {}).get("record_name"), allowed_claims=job.get("allowed_autoprompt_claims"))
        if not result.passed:
            _raise(ExitCode.INPUT_SCHEMA_INVALID, "; ".join(result.failure_codes + result.findings))
        attempts = payload.get("attempts", [])
        if not isinstance(attempts, list):
            _raise(ExitCode.DEPENDENCY_MISSING, "autoprompter returned an invalid attempt record")
        atomic_json_write(_job_root(job) / "evidence" / "prompt" / "autoprompter_attempts.json", {"schema_version": "1.0.0", "instruction_sha256": sha256_file(exact_path), "attempts": attempts})
        return result.normalized_prompt, {"source": "autoprompter", "instruction_sha256": sha256_file(exact_path), "validator": result.as_dict(), "attempts": attempts}


class HOI4KreaModelLoadBarrier:
    """Release completed text-encoder/runtime models before Krea sampling.

    The Krea model patcher is passed through unchanged.  The barrier exists
    only to make the required staged load order explicit: both grounded
    conditioning branches must finish before ComfyUI is allowed to load the
    diffusion model for sampling.  It does not change tensors, weights,
    prompts, seeds, or model selection.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("MODEL",),
            "positive": ("CONDITIONING",),
            "negative": ("CONDITIONING",),
        }}

    RETURN_TYPES = ("MODEL", "CONDITIONING", "CONDITIONING")
    RETURN_NAMES = ("model", "positive", "negative")
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/06 Krea 2 portrait edit"

    def run(self, model: Any, positive: Any, negative: Any):
        try:
            import gc
            import comfy.model_management as model_management  # type: ignore
        except Exception as exc:
            _raise(ExitCode.DEPENDENCY_MISSING, f"ComfyUI model-release API is unavailable: {type(exc).__name__}")
        # The model patcher is still an execution value here; KSampler has not
        # loaded it yet.  Release every device-aware ComfyUI model record so
        # the completed Qwen encoder is not retained while KSampler loads the
        # Krea diffusion model.  Calling free_memory(..., device=None) is not
        # equivalent when --disable-smart-memory is enabled in the pinned
        # ComfyUI revision: that combination leaves the per-device unload
        # budget at zero.  unload_all_models() is the supported path and still
        # preserves the Krea patcher returned by this node as an execution
        # value; it does not mutate model files, weights, prompts, or seeds.
        model_management.unload_all_models()
        gc.collect()
        return model, positive, negative


class HOI4EvidenceExport:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "job": ("HOI4_JOB",),
            "source_master": ("IMAGE",),
            "processed_reference": ("IMAGE",),
            "approved_background": ("IMAGE",),
            "candidate": ("IMAGE",),
            "mask": ("MASK",),
            "prompt": ("STRING",),
            "candidate_index": ("INT", {"default": 0, "min": 0, "max": 11}),
        }}

    RETURN_TYPES = ("IMAGE", "HOI4_META")
    RETURN_NAMES = ("image", "evidence_meta")
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/09 Preview and save"

    def run(self, job: dict[str, Any], source_master: Any, processed_reference: Any, approved_background: Any, candidate: Any, mask: Any, prompt: str, candidate_index: int):
        if not prompt.startswith("hoi4_portrait,"):
            _raise(ExitCode.INPUT_SCHEMA_INVALID, "candidate prompt failed the exact trigger gate")
        if approved_background is None:
            _raise(ExitCode.BACKGROUND_UNRESOLVED, "approved composite is required for evidence")
        if candidate_index < 0:
            _raise(ExitCode.INPUT_SCHEMA_INVALID, "candidate index must be non-negative")
        if Image is None:
            _raise(ExitCode.DEPENDENCY_MISSING, "Pillow is required for evidence export")
        job_root = _job_root(job)
        source_image = _comfy_to_pil(source_master).convert("RGB")
        reference_image = _comfy_to_pil(processed_reference).convert("RGB")
        background_image = _comfy_to_pil(approved_background).convert("RGB")
        candidate_image = _comfy_to_pil(candidate).convert("RGB")
        candidate_id = f"candidate-{int(candidate_index):03d}"
        records = {
            "source_master": _write_image(job_root / "evidence" / "source" / "master.png", source_image),
            "processed_reference": _write_image(job_root / "evidence" / "reference" / "processed.png", reference_image),
            "approved_background": _write_image(job_root / "evidence" / "background" / "approved_composite.png", background_image),
            "candidate": _write_image(job_root / "candidates" / f"{candidate_id}.png", candidate_image),
        }
        if mask is not None:
            mask_tensor = mask.detach().cpu().clamp(0, 1) if hasattr(mask, "detach") else mask
            if hasattr(mask_tensor, "ndim") and mask_tensor.ndim == 3:
                mask_tensor = mask_tensor[0]
            if hasattr(mask_tensor, "mul"):
                mask_pixels = (mask_tensor.mul(255).byte().numpy())
                mask_image = Image.fromarray(mask_pixels, mode="L")
            else:
                mask_image = mask.convert("L") if hasattr(mask, "convert") else None
            if mask_image is not None:
                records["mask"] = _write_image(job_root / "evidence" / "mask" / f"{candidate_id}.png", mask_image)
        prompt_path = job_root / "evidence" / "prompt" / f"{candidate_id}.txt"
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(prompt, encoding="utf-8")
        evidence_meta = {"schema_version": "1.0.0", "job_id": job.get("job_id"), "candidate_id": candidate_id, "candidate_index": int(candidate_index), "records": records, "prompt_path": str(prompt_path.relative_to(job_root)), "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(), "finalization": "controller_and_independent_auditor_only", "exported_at": datetime.now(timezone.utc).isoformat()}
        atomic_json_write(job_root / "evidence" / "candidates" / f"{candidate_id}.json", evidence_meta)
        return candidate, evidence_meta
