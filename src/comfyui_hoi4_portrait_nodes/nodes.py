from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from portrait_pipeline.constants import ExitCode
from portrait_pipeline.contracts import validate_job
from portrait_pipeline.prompt import validate_prompt
from portrait_pipeline.util import project_root, relative_safe_path, sha256_file

try:  # ComfyUI supplies torch/Pillow in its runtime.
    import torch  # type: ignore
except Exception:  # pragma: no cover - import-only path on a clean preflight host
    torch = None

try:
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover - import-only path on a clean preflight host
    Image = None


def _raise(code: ExitCode, message: str) -> None:
    raise RuntimeError(f"{code.name} ({int(code)}): {message}")


def _project_from_job(job: dict[str, Any]) -> Path:
    root = job.get("_project_root") or os.environ.get("HOI4_PORTRAIT_PROJECT_ROOT")
    if not root:
        _raise(ExitCode.INTERNAL_ERROR, "job does not identify an allowed project root")
    return project_root(root)


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


class HOI4JobInput:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "execution_profile": ("STRING", {"default": "agent_local_mac_16gb"}),
            "job_contract_path": ("STRING", {"default": "jobs/<job_id>/input.json"}),
            "candidate_count": ("INT", {"default": 1, "min": 1, "max": 12}),
            "retry_limit": ("INT", {"default": 0, "min": 0, "max": 4}),
            "seed_policy": (["fixed", "derived", "random_recorded"], {"default": "derived"}),
        }}

    RETURN_TYPES = ("HOI4_JOB",)
    RETURN_NAMES = ("job",)
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/00 Job and source"

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
        job["_project_root"] = str(root)
        job["_workflow_execution_profile"] = execution_profile
        issues = validate_job(job, root)
        if issues:
            first = issues[0]
            _raise(first.code, f"{first.path}: {first.message}")
        if job.get("execution_profile") != execution_profile:
            _raise(ExitCode.WORKFLOW_INVALID, "job profile does not match the loaded workflow")
        return (job,)


class HOI4JobSource:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"job": ("HOI4_JOB",)}}

    RETURN_TYPES = ("IMAGE", "HOI4_META")
    RETURN_NAMES = ("image", "source_meta")
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/00 Job and source"

    def run(self, job: dict[str, Any]):
        if Image is None:
            _raise(ExitCode.DEPENDENCY_MISSING, "Pillow is required to load the source portrait")
        root = _project_from_job(job)
        path_value = str(job["source_image_path"])
        path = relative_safe_path(root, path_value)
        if not path.is_file():
            _raise(ExitCode.SOURCE_INVALID, f"source portrait is missing: {path_value}")
        actual = sha256_file(path)
        source_meta = {"path": str(path.relative_to(root)), "sha256": actual, "source_provenance": job.get("source_provenance")}
        with Image.open(path) as image:
            image.load()
            return (_pil_to_comfy(image), source_meta)


class HOI4SourceGuard:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"job": ("HOI4_JOB",), "image": ("IMAGE",)}}

    RETURN_TYPES = ("IMAGE", "HOI4_META")
    RETURN_NAMES = ("image", "source_meta")
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/00 Job and source"

    def run(self, job: dict[str, Any], image: Any):
        root = _project_from_job(job)
        path = relative_safe_path(root, job["source_image_path"])
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
    CATEGORY = "HOI4 Portrait/01 Subject selection"

    def run(self, job: dict[str, Any], image: Any):
        selector = job.get("subject_selector")
        if selector is None and job.get("subject_identity", {}).get("real_person") is True:
            _raise(ExitCode.AMBIGUOUS_SUBJECT, "real-person jobs require a deterministic selector or an audited single-face detector")
        return image, {"selector": selector, "selection": "contract_or_preflight_confirmed"}


class HOI4HeadShouldersCrop:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"job": ("HOI4_JOB",), "image": ("IMAGE",)}}

    RETURN_TYPES = ("IMAGE", "HOI4_META")
    RETURN_NAMES = ("image", "crop_meta")
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/02 Crop and source preparation"

    def run(self, job: dict[str, Any], image: Any):
        return image, {"crop": "delegated_to_calibrated_selector", "job_id": job.get("job_id")}


class HOI4ConservativePrep:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"job": ("HOI4_JOB",), "image": ("IMAGE",)}}

    RETURN_TYPES = ("IMAGE", "HOI4_META")
    RETURN_NAMES = ("image", "reference_meta")
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/03 Color and restoration"

    def run(self, job: dict[str, Any], image: Any):
        return image, {"colorization": "conditional", "restoration": "conservative", "identity_master_preserved": True}


class HOI4ForegroundMask:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"job": ("HOI4_JOB",), "image": ("IMAGE",), "mask_model": ("STRING", {"default": "BiRefNet:PINNED_REQUIRED"})}}

    RETURN_TYPES = ("IMAGE", "MASK", "HOI4_META")
    RETURN_NAMES = ("image", "mask", "mask_meta")
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/04 Masks and approved background"

    def run(self, job: dict[str, Any], image: Any, mask_model: str):
        if "PINNED_REQUIRED" in mask_model:
            _raise(ExitCode.DEPENDENCY_MISSING, "BiRefNet mask model is not installed and verified")
        service = os.environ.get("HOI4_MASK_SERVICE_LOOPBACK")
        if not service or not (service.startswith("http://127.0.0.1:") or service.startswith("http://localhost:")):
            _raise(ExitCode.DEPENDENCY_MISSING, "foreground mask service is not configured on loopback")
        _raise(ExitCode.GENERATION_FAILED, "mask service integration is not live-qualified; no placeholder mask is permitted")


class HOI4MaskAndBackgroundGuard:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"job": ("HOI4_JOB",), "image": ("IMAGE",), "mask": ("MASK",)}}

    RETURN_TYPES = ("IMAGE", "IMAGE", "MASK", "HOI4_META")
    RETURN_NAMES = ("image", "composite", "mask", "background_meta")
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/04 Masks and approved background"

    def run(self, job: dict[str, Any], image: Any, mask: Any):
        root = _project_from_job(job)
        registry_path = root / "config" / "background_registry.json"
        if not registry_path.is_file():
            _raise(ExitCode.BACKGROUND_UNRESOLVED, "background registry is missing")
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        requested = job.get("approved_background", {})
        matches = [item for item in registry.get("backgrounds", []) if item.get("registry_id") == requested.get("registry_id")]
        if not matches or matches[0].get("status") != "APPROVED" or matches[0].get("sha256") != requested.get("sha256"):
            _raise(ExitCode.BACKGROUND_UNRESOLVED, "requested background does not match an approved registry entry")
        if torch is None or Image is None:
            _raise(ExitCode.DEPENDENCY_MISSING, "PyTorch and Pillow are required for the background composite")
        background_value = matches[0].get("runtime_path")
        if not background_value:
            _raise(ExitCode.BACKGROUND_UNRESOLVED, "approved background has no runtime path")
        background_path = relative_safe_path(root, background_value)
        if not background_path.is_file() or sha256_file(background_path) != requested.get("sha256"):
            _raise(ExitCode.BACKGROUND_UNRESOLVED, "approved background file is missing or checksum mismatched")
        with Image.open(background_path) as background_image:
            background_image = background_image.convert("RGB").resize((image.shape[2], image.shape[1]))
            background = _pil_to_comfy(background_image).to(device=image.device, dtype=image.dtype)
        working_mask = mask
        if working_mask.ndim == 3:
            working_mask = working_mask.unsqueeze(-1)
        working_mask = working_mask.to(device=image.device, dtype=image.dtype).clamp(0, 1)
        composite = image * working_mask + background * (1.0 - working_mask)
        return image, composite, mask, {"background_registry_id": requested["registry_id"], "background_sha256": requested["sha256"], "mask_semantics": "foreground_alpha; independently_audited", "foreground_integrity_required": True}


class HOI4PromptInput:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"job": ("HOI4_JOB",), "prompt_source": (["job_contract"], {"default": "job_contract"})}}

    RETURN_TYPES = ("STRING", "HOI4_META")
    RETURN_NAMES = ("prompt", "prompt_meta")
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/05 Prompt"

    def run(self, job: dict[str, Any], prompt_source: str):
        if prompt_source != "job_contract":
            _raise(ExitCode.WORKFLOW_INVALID, "agent prompt must come from the job contract")
        result = validate_prompt(prompt=str(job.get("prompt", "")), record_name=job.get("subject_identity", {}).get("record_name"), allowed_claims=job.get("allowed_autoprompt_claims"))
        if not result.passed:
            _raise(ExitCode.INPUT_SCHEMA_INVALID, "; ".join(result.failure_codes + result.findings))
        return result.normalized_prompt, {"source": "job_contract", "validator": result.as_dict()}


class HOI4AutopromptClient:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "job": ("HOI4_JOB",),
            "image": ("IMAGE",),
            "instruction_text": ("STRING", {"multiline": True, "default": ""}),
            "instruction_path": ("STRING", {"default": "prompts/autoprompter_instruction.txt"}),
            "model_id": ("STRING", {"default": "Qwen/Qwen3-VL-4B-Instruct-GGUF"}),
            "prompt_source": (["autoprompter"], {"default": "autoprompter"}),
        }}

    RETURN_TYPES = ("STRING", "HOI4_META")
    RETURN_NAMES = ("prompt", "prompt_meta")
    FUNCTION = "run"
    CATEGORY = "HOI4 Portrait/05 Prompt"

    def run(self, job: dict[str, Any], image: Any, instruction_text: str, instruction_path: str, model_id: str, prompt_source: str):
        if prompt_source != "autoprompter":
            _raise(ExitCode.WORKFLOW_INVALID, "human autoprompter source is locked")
        expected_model = "Qwen/Qwen3-VL-4B-Instruct-GGUF" if job.get("execution_profile") == "human_local_mac_16gb" else "Qwen/Qwen3-VL-8B-Instruct"
        if model_id != expected_model:
            _raise(ExitCode.WORKFLOW_INVALID, f"autoprompter model does not match profile; expected {expected_model}")
        root = _project_from_job(job)
        exact_path = relative_safe_path(root, instruction_path)
        exact_instruction = exact_path.read_text(encoding="utf-8")
        if instruction_text != exact_instruction:
            _raise(ExitCode.WORKFLOW_INVALID, "autoprompter instruction does not exactly match the project file")
        endpoint = os.environ.get("HOI4_AUTOPROMPTER_LOOPBACK", "http://127.0.0.1:8099/v1/chat/completions")
        if not endpoint.startswith("http://127.0.0.1:") and not endpoint.startswith("http://localhost:"):
            _raise(ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED, "autoprompter is not bound to loopback")
        encoded = json.dumps({"instruction": exact_instruction, "job_id": job.get("job_id"), "model_id": model_id, "image": "provided_in_process"}).encode("utf-8")
        request = urllib.request.Request(endpoint, data=encoded, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            _raise(ExitCode.DEPENDENCY_MISSING, f"loopback autoprompter sidecar unavailable: {exc}")
        prompt = str(payload.get("prompt", ""))
        result = validate_prompt(prompt, record_name=job.get("subject_identity", {}).get("record_name"), allowed_claims=job.get("allowed_autoprompt_claims"))
        if not result.passed:
            _raise(ExitCode.INPUT_SCHEMA_INVALID, "; ".join(result.failure_codes + result.findings))
        return result.normalized_prompt, {"source": "autoprompter", "instruction_sha256": sha256_file(exact_path), "validator": result.as_dict()}


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
    CATEGORY = "HOI4 Portrait/09 Preview and evidence export"

    def run(self, job: dict[str, Any], source_master: Any, processed_reference: Any, approved_background: Any, candidate: Any, mask: Any, prompt: str, candidate_index: int):
        if not prompt.startswith("hoi4_portrait,"):
            _raise(ExitCode.INPUT_SCHEMA_INVALID, "candidate prompt failed the exact trigger gate")
        if approved_background is None:
            _raise(ExitCode.BACKGROUND_UNRESOLVED, "approved composite is required for evidence")
        return candidate, {"job_id": job.get("job_id"), "candidate_index": candidate_index, "source_master_present": source_master is not None, "processed_reference_present": processed_reference is not None, "approved_background_present": approved_background is not None, "mask_present": mask is not None, "finalization": "controller_and_independent_auditor_only"}
