from __future__ import annotations

import json
import os
import secrets
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .audit import audit_is_promotion_pass, load_audits
from .constants import (
    CALIBRATED_THRESHOLD_STATUSES,
    DEPENDENCY_LOCK_VERSION,
    ExitCode,
    JobStatus,
    STAGES,
    WORKFLOW_VERSION,
)
from .contracts import ValidationIssue, build_blocked_output, validate_job
from .dds import DdsValidationError, convert_png_to_dds
from .comfy_client import ComfyTransportError, LoopbackComfyClient
from .preflight import collect_preflight
from .selection import select_identity_first
from .finalize import FinalizationError, finalize_candidate_png
from .util import atomic_json_write, canonical_hash, project_root, relative_safe_path, sha256_file
from .workflow_validation import validate_workflow_file


LOCAL_PROFILE_IDS = frozenset({
    "local_nvidia_16gb",
    "agent_local_nvidia_16gb",
})
LOCAL_GENERATION_UNAVAILABLE = "LOCAL_GENERATION_UNAVAILABLE"


@dataclass
class JobResult:
    output: dict[str, Any]
    job_root: Path


class JobController:
    """Controller for the 17-stage contract, with fail-closed promotion."""

    def __init__(self, root: str | Path | None = None):
        self.root = project_root(root)
        self.jobs_root = self.root / "jobs"

    def _job_root(self, job_id: str) -> Path:
        return relative_safe_path(self.jobs_root, job_id)

    def _write_state(self, job_root: Path, state: str, *, stage: str, blockers: list[str] | None = None, warnings: list[str] | None = None, exit_code: int | None = None, attempt: int = 0, progress: float | None = None, prompt_id: str | None = None) -> None:
        atomic_json_write(job_root / "status.json", {
            "schema_version": "1.0.0",
            "job_id": job_root.name,
            "state": state,
            "stage": stage,
            "stage_index": STAGES.index(stage) if stage in STAGES else None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "attempt": attempt,
            "progress": (1.0 if state == "COMPLETED" else 0.0) if progress is None else progress,
            "prompt_id": prompt_id,
            "warnings": warnings or [],
            "blockers": blockers or [],
            "terminal_exit_code": exit_code,
        })

    def _write_output(self, job_root: Path, output: dict[str, Any]) -> JobResult:
        atomic_json_write(job_root / "output.json", output)
        return JobResult(output, job_root)

    def _record_local_generation_unavailable(
        self,
        job: dict[str, Any],
        job_root: Path,
        output: dict[str, Any],
        *,
        stage: str,
    ) -> None:
        """Persist the local failure boundary without queueing remotely."""

        if str(job.get("execution_profile")) not in LOCAL_PROFILE_IDS:
            return
        evidence_paths = ["docs/capability_reports/local_krea_infeasible.md"]
        evidence_paths.extend(
            sorted(
                str(path.relative_to(self.root))
                for pattern in ("local_canary_*.json", "gpu_canary_*.json", "cpu_canary_*.json")
                for path in (self.root / "docs" / "preflight").glob(pattern)
                if path.is_file()
            )
        )
        marker = {
            "schema_version": "1.0.0",
            "status": LOCAL_GENERATION_UNAVAILABLE,
            "job_id": job.get("job_id"),
            "execution_profile": job.get("execution_profile"),
            "stage": stage,
            "exit_code": output.get("exit_code"),
            "reason": output.get("error_message"),
            "blockers": [str(item) for item in output.get("blockers", [])],
            "evidence": evidence_paths,
            "remote_submission": "NOT_QUEUED_BY_LOCAL_ROUTE",
            "policy": "Remote generation requires a separate authenticated submission.",
        }
        atomic_json_write(job_root / "local_generation_unavailable.json", marker)
        output["error_code"] = LOCAL_GENERATION_UNAVAILABLE
        output["error_message"] = f"{LOCAL_GENERATION_UNAVAILABLE}: {output.get('error_message', '')}"
        output["warnings"] = list(dict.fromkeys([LOCAL_GENERATION_UNAVAILABLE, *output.get("warnings", [])]))

    def submit(self, job: dict[str, Any]) -> JobResult:
        issues = validate_job(job, self.root)
        job_id = str(job.get("job_id", "invalid-job"))
        if not job_id or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for char in job_id) or len(job_id) < 3:
            output = build_blocked_output(job, ExitCode.INPUT_SCHEMA_INVALID, "job id does not satisfy the contract", root=self.root)
            return self._write_output(self.root / "jobs" / "invalid-job", output)
        job_root = self._job_root(job_id)
        semantic_hash = canonical_hash(job)
        if job_root.exists():
            existing = job_root / "input.json"
            if existing.is_file():
                old_hash = canonical_hash(json.loads(existing.read_text(encoding="utf-8")))
                if old_hash != semantic_hash:
                    output = build_blocked_output(job, ExitCode.INPUT_SCHEMA_INVALID, "JOB_ID_CONFLICT: existing job input differs", root=self.root)
                    output["error_code"] = "JOB_ID_CONFLICT"
                    return self._write_output(job_root, output)
                if (job_root / "output.json").is_file():
                    return JobResult(json.loads((job_root / "output.json").read_text(encoding="utf-8")), job_root)
        else:
            job_root.parent.mkdir(parents=True, exist_ok=True)
            temporary = Path(tempfile.mkdtemp(prefix=f".{job_id}.", dir=job_root.parent))
            try:
                os.replace(temporary, job_root)
            except FileExistsError:
                shutil.rmtree(temporary, ignore_errors=True)
        (job_root / "evidence").mkdir(exist_ok=True)
        (job_root / "candidates").mkdir(exist_ok=True)
        (job_root / "audit").mkdir(exist_ok=True)
        atomic_json_write(job_root / "input.json", job)
        atomic_json_write(job_root / "submission.json", {"input_hash": semantic_hash, "submitted_at": datetime.now(timezone.utc).isoformat(), "workflow_version": WORKFLOW_VERSION})
        self._write_state(job_root, "SUBMITTED", stage="JOB_ACCEPTED")
        if issues:
            code = _issue_exit_code(issues)
            output = build_blocked_output(job, code, "; ".join(f"{issue.path}: {issue.message}" for issue in issues), blockers=[issue.message for issue in issues], root=self.root)
            self._write_state(job_root, "BLOCKED", stage="JOB_ACCEPTED", blockers=output["blockers"], exit_code=int(code))
            return self._write_output(job_root, output)
        preflight_blocker = self._preflight_blocker(job)
        if preflight_blocker:
            code, blockers = preflight_blocker
            output = build_blocked_output(job, code, blockers[0], blockers=blockers, root=self.root)
            self._record_local_generation_unavailable(job, job_root, output, stage="JOB_ACCEPTED")
            self._write_state(job_root, "BLOCKED", stage="JOB_ACCEPTED", blockers=blockers, warnings=output.get("warnings"), exit_code=int(code))
            return self._write_output(job_root, output)
        return JobResult({"status": "SUBMITTED", "job_id": job_id, "input_hash": semantic_hash}, job_root)

    def _preflight_blocker(self, job: dict[str, Any]) -> tuple[ExitCode, list[str]] | None:
        report = collect_preflight(self.root, profile=str(job.get("execution_profile")))
        blockers = list(report["blockers"])
        if not blockers:
            return None
        if any("background" in item.casefold() for item in blockers):
            return ExitCode.BACKGROUND_UNRESOLVED, blockers
        if job.get("execution_profile") in {"full_power_gpu", "agent_full_power_gpu"} and any("RunPod" in item or "remote" in item.casefold() for item in blockers):
            return ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED, blockers
        return ExitCode.DEPENDENCY_MISSING, blockers

    def _workflow_api_path(self, workflow_id: str) -> Path:
        paths = {
            "local_nvidia_16gb": self.root / "workflows/human/local_nvidia_16gb/local_nvidia_16gb.api.json",
            "full_power_gpu": self.root / "workflows/human/full_power_gpu/full_power_gpu.api.json",
            "agent_local_nvidia_16gb": self.root / "workflows/agent/local_nvidia_16gb/agent_local_nvidia_16gb.api.json",
            "agent_full_power_gpu": self.root / "workflows/agent/full_power_gpu/agent_full_power_gpu.api.json",
        }
        try:
            return paths[workflow_id]
        except KeyError as exc:
            raise RuntimeError(f"unknown workflow profile: {workflow_id}") from exc

    def _derived_seed(self, job: dict[str, Any], candidate_index: int) -> int:
        source_path = job.get("source_image_path")
        source_sha = "0" * 64
        if isinstance(source_path, str):
            try:
                path = relative_safe_path(self.root, source_path)
                if path.is_file():
                    source_sha = sha256_file(path)
            except ValueError:
                pass
        prompt_hash = canonical_hash(job.get("prompt", ""))
        seed_material = f"{source_sha}:{prompt_hash}:{candidate_index}:{WORKFLOW_VERSION}:hoi4-portrait-seed-v1"
        return int(canonical_hash(seed_material)[:16], 16) & ((1 << 63) - 1)

    def _candidate_seed(self, job: dict[str, Any], candidate_index: int) -> int:
        mode = job["seed_policy"]["mode"]
        if mode == "derived":
            return self._derived_seed(job, candidate_index)
        if mode == "fixed":
            return int(job["seed_policy"]["seed"])
        if mode == "random_recorded":
            # The contract requires a fresh, auditable random seed per
            # candidate.  The generation evidence records the returned value.
            return secrets.randbits(63)
        raise ValueError(f"unsupported seed policy: {mode}")

    def _api_workflow_for_candidate(self, job: dict[str, Any], candidate_index: int, *, seed: int | None = None) -> dict[str, Any]:
        import copy

        workflow = json.loads(self._workflow_api_path(str(job["execution_profile"])).read_text(encoding="utf-8"))
        metadata = workflow.pop("_meta", {})
        workflow = copy.deepcopy(workflow)
        node_one = workflow.get("1")
        if not isinstance(node_one, dict):
            raise RuntimeError("workflow API JSON has no job input node")
        node_one.setdefault("inputs", {})["job_contract_path"] = f"jobs/{job['job_id']}/input.json"
        node_one["inputs"]["candidate_count"] = int(job["candidate_count"])
        node_one["inputs"]["retry_limit"] = int(job["retry_limit"])
        node_one["inputs"]["seed_policy"] = job["seed_policy"]["mode"]
        human_controls = workflow.get("24")
        if isinstance(human_controls, dict):
            controls = human_controls.setdefault("inputs", {})
            controls["source_image_path"] = str(job["source_image_path"])
            selector = job.get("subject_selector")
            if isinstance(selector, dict) and selector.get("mode") == "bbox":
                bbox = [int(value) for value in selector["bbox_xyxy"]]
                controls.update({"subject_selector_mode": "bbox", "bbox_left": bbox[0], "bbox_top": bbox[1], "bbox_right": bbox[2], "bbox_bottom": bbox[3]})
            elif isinstance(selector, dict) and selector.get("mode") == "face_index":
                controls.update({"subject_selector_mode": "face_index", "face_index": int(selector["face_index"])})
            else:
                controls["subject_selector_mode"] = "automatic"
            controls["approved_background_registry_id"] = str(job["approved_background"]["registry_id"])
            controls["seed_mode"] = str(job["seed_policy"]["mode"])
            controls["fixed_seed"] = int(job["seed_policy"].get("seed") or 0)
            controls["candidate_count"] = int(job["candidate_count"])
            controls["output_job_id"] = str(job["job_id"])
        sampler = workflow.get("20")
        if isinstance(sampler, dict):
            sampler.setdefault("inputs", {})["seed"] = self._candidate_seed(job, candidate_index) if seed is None else int(seed)
        export = workflow.get("22")
        if isinstance(export, dict):
            export.setdefault("inputs", {})["candidate_index"] = candidate_index
        return workflow

    def _candidate_evidence_paths(self, job_root: Path, candidate_id: str) -> list[Path]:
        paths = [
            job_root / "evidence/source/master.png",
            job_root / "evidence/reference/processed.png",
            job_root / "evidence/background/approved_composite.png",
            job_root / f"candidates/{candidate_id}.png",
        ]
        return [path for path in paths if path.is_file()]

    @staticmethod
    def _cancel_requested(job_root: Path) -> bool:
        return (job_root / "cancel.json").is_file()

    def _run_comfy_candidates(self, job: dict[str, Any], job_root: Path) -> tuple[list[str], list[int]]:
        workflow_id = str(job["execution_profile"])
        api_path = self._workflow_api_path(workflow_id)
        ui_path = api_path.with_name(api_path.name.replace(".api.json", ".json"))
        validation = validate_workflow_file(workflow_id, ui_path, api_path, self.root)
        if validation["structural_status"] != "PASS":
            raise ComfyTransportError(ExitCode.WORKFLOW_INVALID, "; ".join(validation["issues"]))
        # Local installs and RunPod Pods both keep raw ComfyUI on loopback.
        # Remote callers reach the authenticated project gateway; the
        # controller itself always talks to the colocated loopback server.
        client = LoopbackComfyClient()
        client.health()
        candidate_paths: list[str] = []
        seeds: list[int] = []
        count = int(job["candidate_count"])
        for candidate_index in range(count):
            if self._cancel_requested(job_root):
                raise ComfyTransportError(ExitCode.CANCELED, "job cancellation was requested")
            seed = self._candidate_seed(job, candidate_index)
            seeds.append(seed)
            self._write_state(job_root, "RUNNING", stage="WORKFLOW_VALIDATED", attempt=1, progress=candidate_index / max(1, count))
            prompt_id = client.submit(self._api_workflow_for_candidate(job, candidate_index, seed=seed), f"hoi4-portrait-{job['job_id']}")
            self._write_state(job_root, "RUNNING", stage="CANDIDATES_GENERATED", attempt=1, progress=candidate_index / max(1, count), prompt_id=prompt_id)
            history = client.wait_for_history(prompt_id)
            if self._cancel_requested(job_root):
                raise ComfyTransportError(ExitCode.CANCELED, "job cancellation was requested")
            status = history.get("status", {}) if isinstance(history, dict) else {}
            if isinstance(status, dict) and status.get("status_str") == "error":
                raise ComfyTransportError(ExitCode.GENERATION_FAILED, "ComfyUI reported a workflow execution error")
            candidate_id = f"candidate-{candidate_index:03d}"
            candidate = job_root / f"candidates/{candidate_id}.png"
            if not candidate.is_file():
                raise ComfyTransportError(ExitCode.GENERATION_FAILED, f"evidence export did not create {candidate_id}")
            candidate_paths.append(str(candidate.relative_to(job_root)))
            atomic_json_write(job_root / "evidence" / "generation" / f"{candidate_id}.json", {"candidate_id": candidate_id, "candidate_index": candidate_index, "seed": seed, "prompt_id": prompt_id, "history_status": status, "candidate_sha256": sha256_file(candidate)})
        return candidate_paths, seeds

    def run(self, job_id: str) -> JobResult:
        job_root = self._job_root(job_id)
        input_path = job_root / "input.json"
        if not input_path.is_file():
            output = build_blocked_output({"job_id": job_id}, ExitCode.SOURCE_INVALID, "job input is missing", root=self.root)
            job_root.mkdir(parents=True, exist_ok=True)
            self._write_state(job_root, "BLOCKED", stage="JOB_ACCEPTED", blockers=["job input is missing"], exit_code=int(ExitCode.SOURCE_INVALID))
            return self._write_output(job_root, output)
        job = json.loads(input_path.read_text(encoding="utf-8"))
        if self._cancel_requested(job_root):
            output = build_blocked_output(job, ExitCode.CANCELED, "job cancellation was requested", blockers=["caller canceled the job before generation"], root=self.root)
            self._write_state(job_root, "CANCELED", stage="JOB_ACCEPTED", blockers=output["blockers"], exit_code=int(ExitCode.CANCELED))
            return self._write_output(job_root, output)
        blocker = self._preflight_blocker(job)
        if blocker:
            code, blockers = blocker
            output = build_blocked_output(job, code, blockers[0], blockers=blockers, root=self.root)
            self._record_local_generation_unavailable(job, job_root, output, stage="JOB_ACCEPTED")
            self._write_state(job_root, "BLOCKED", stage="JOB_ACCEPTED", blockers=blockers, warnings=output.get("warnings"), exit_code=int(code))
            return self._write_output(job_root, output)
        try:
            candidate_paths, seeds = self._run_comfy_candidates(job, job_root)
        except ComfyTransportError as exc:
            output = build_blocked_output(job, exc.code, str(exc), blockers=[str(exc)], root=self.root)
            if exc.code in {ExitCode.OUT_OF_MEMORY, ExitCode.DEPENDENCY_MISSING, ExitCode.GENERATION_FAILED}:
                self._record_local_generation_unavailable(job, job_root, output, stage="CANDIDATES_GENERATED")
            state = "CANCELED" if exc.code == ExitCode.CANCELED else "FAILED"
            self._write_state(job_root, state, stage="CANDIDATES_GENERATED", blockers=output["blockers"], warnings=output.get("warnings"), exit_code=int(exc.code))
            return self._write_output(job_root, output)
        except (OSError, RuntimeError, ValueError) as exc:
            output = build_blocked_output(job, ExitCode.GENERATION_FAILED, f"generation orchestration failed: {type(exc).__name__}", blockers=["authenticated ComfyUI route failed"], root=self.root)
            self._record_local_generation_unavailable(job, job_root, output, stage="CANDIDATES_GENERATED")
            self._write_state(job_root, "FAILED", stage="CANDIDATES_GENERATED", blockers=output["blockers"], warnings=output.get("warnings"), exit_code=int(ExitCode.GENERATION_FAILED))
            return self._write_output(job_root, output)
        if self._cancel_requested(job_root):
            output = build_blocked_output(job, ExitCode.CANCELED, "job cancellation was requested", blockers=["caller canceled the job after candidate generation"], root=self.root)
            self._write_state(job_root, "CANCELED", stage="CANDIDATES_GENERATED", blockers=output["blockers"], exit_code=int(ExitCode.CANCELED))
            return self._write_output(job_root, output)
        output = build_blocked_output(job, ExitCode.AUDIT_UNCERTAIN, "candidates generated; independent audit and identity-first selection are required", blockers=["independent all-PASS audit is required before finalization"], root=self.root)
        output.update({"status": JobStatus.NEEDS_REVIEW.value, "candidate_paths": candidate_paths, "seeds": seeds})
        self._write_state(job_root, "NEEDS_REVIEW", stage="CANDIDATES_GENERATED", blockers=output["blockers"], exit_code=int(ExitCode.AUDIT_UNCERTAIN), attempt=1, progress=1.0)
        return self._write_output(job_root, output)

    def promote(self, job_id: str, audit_paths: list[str | Path]) -> JobResult:
        job_root = self._job_root(job_id)
        try:
            job = json.loads((job_root / "input.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            output = build_blocked_output({"job_id": job_id}, ExitCode.AUDIT_UNCERTAIN, "job input is unavailable for audit promotion", blockers=["independent audit cannot be associated with a missing job"], root=self.root)
            self._write_state(job_root, "NEEDS_REVIEW", stage="CANDIDATE_SELECTED", blockers=output["blockers"], exit_code=int(ExitCode.AUDIT_UNCERTAIN))
            return self._write_output(job_root, output)
        safe_audit_paths: list[Path] = []
        try:
            for raw_path in audit_paths:
                safe_path = relative_safe_path(job_root, raw_path)
                if not safe_path.is_file():
                    raise ValueError(f"audit file is missing: {raw_path}")
                safe_audit_paths.append(safe_path)
            audits = load_audits(safe_audit_paths, self.root)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            output = build_blocked_output(job, ExitCode.AUDIT_UNCERTAIN, "audit evidence is invalid or outside the job root", blockers=[f"independent audit could not be loaded: {type(exc).__name__}"], root=self.root)
            self._write_state(job_root, "NEEDS_REVIEW", stage="CANDIDATE_SELECTED", blockers=output["blockers"], exit_code=int(ExitCode.AUDIT_UNCERTAIN))
            return self._write_output(job_root, output)
        selected, selection_report = select_identity_first(audits)
        audit_blockers: list[str] = []
        thresholds_path = self.root / "config" / "identity_thresholds.json"
        thresholds = json.loads(thresholds_path.read_text(encoding="utf-8")) if thresholds_path.is_file() else {}
        threshold_id = thresholds.get("thresholds_id")
        thresholds_ready = thresholds.get("status") in CALIBRATED_THRESHOLD_STATUSES and thresholds.get("fail_closed") is True and threshold_id not in {None, "UNSET_BLOCK_EXECUTION"}
        for audit in audits:
            if audit.get("job_id") != job_id:
                audit_blockers.append(f"audit {audit.get('candidate_id')} belongs to a different job")
            if not isinstance(audit.get("candidate_id"), str) or not audit.get("candidate_id", "").startswith("candidate-"):
                audit_blockers.append("audit candidate id is invalid")
            if not audit_is_promotion_pass(audit):
                continue
            if not thresholds_ready or audit.get("thresholds_id") != threshold_id:
                audit_blockers.append(f"candidate {audit.get('candidate_id')} uses an unapproved identity-threshold registry")
            for field, value in audit.get("evidence", {}).items():
                try:
                    evidence_path = relative_safe_path(job_root, value)
                except (TypeError, ValueError):
                    audit_blockers.append(f"candidate {audit.get('candidate_id')} evidence path escapes the job root: {field}")
                    continue
                if not evidence_path.is_file():
                    audit_blockers.append(f"candidate {audit.get('candidate_id')} evidence is missing: {field}")
        if audit_blockers:
            selected = None
            selection_report["hard_blockers"] = audit_blockers
        atomic_json_write(job_root / "audit" / "selection.json", selection_report)
        if selected is None:
            code = ExitCode.AUDIT_UNCERTAIN if audit_blockers or any(audit.get("verdict") == "UNCERTAIN" for audit in audits) else ExitCode.IDENTITY_NO_PASSING_CANDIDATE
            output = build_blocked_output(job, code, "no independently audited PASS candidate exists", blockers=["DDS and mod integration remain prohibited"], root=self.root)
            self._write_state(job_root, "NEEDS_REVIEW", stage="CANDIDATE_SELECTED", blockers=output["blockers"], exit_code=int(code))
            return self._write_output(job_root, output)
        try:
            candidate = relative_safe_path(job_root, selected["evidence"]["candidate"])
            final_png = relative_safe_path(job_root, job["final_png_path"])
            final_dds = relative_safe_path(job_root, job["final_dds_path"])
        except (KeyError, ValueError) as exc:
            output = build_blocked_output(job, ExitCode.INPUT_SCHEMA_INVALID, "candidate or final output path is outside the job root", blockers=["final output paths must be project-relative"], root=self.root)
            self._write_state(job_root, "BLOCKED", stage="CANDIDATE_SELECTED", blockers=output["blockers"], exit_code=int(ExitCode.INPUT_SCHEMA_INVALID))
            return self._write_output(job_root, output)
        if not candidate.is_file():
            output = build_blocked_output(job, ExitCode.IDENTITY_NO_PASSING_CANDIDATE, "audited candidate file is missing", blockers=["candidate evidence is incomplete"], root=self.root)
            self._write_state(job_root, "BLOCKED", stage="CANDIDATE_SELECTED", blockers=output["blockers"], exit_code=int(ExitCode.IDENTITY_NO_PASSING_CANDIDATE))
            return self._write_output(job_root, output)
        audit_path = next(path for path, audit in zip(safe_audit_paths, audits) if audit.get("candidate_id") == selected.get("candidate_id"))
        try:
            evidence_images = [(label, evidence_path) for label, value in (("source", selected["evidence"].get("source_master")), ("processed", selected["evidence"].get("processed_reference")), ("candidate", selected["evidence"].get("candidate"))) if isinstance(value, str) and (evidence_path := relative_safe_path(job_root, value)).is_file()]
            final_report = finalize_candidate_png(candidate, final_png, selected, root=self.root, comparison_dir=job_root / "comparisons", evidence_images=evidence_images)
            dds_report = convert_png_to_dds(final_png, final_dds, audit_path, self.root)
        except (DdsValidationError, FinalizationError, OSError, ValueError) as exc:
            output = build_blocked_output(job, ExitCode.DDS_VALIDATION_FAILED, f"finalization failed: {type(exc).__name__}", blockers=[str(exc)], root=self.root)
            self._write_state(job_root, "FAILED", stage="PNG_VALIDATED", blockers=output["blockers"], exit_code=int(ExitCode.DDS_VALIDATION_FAILED))
            return self._write_output(job_root, output)
        output = build_blocked_output(job, ExitCode.SUCCESS, "")
        output.update({"status": JobStatus.SUCCEEDED.value, "error_code": None, "error_message": None, "selected_candidate": selected["candidate_id"], "final_png": str(final_png.relative_to(job_root)), "final_dds": str(final_dds.relative_to(job_root)), "final_checksums": {"png": sha256_file(final_png), "dds": dds_report["sha256"]}, "audits": {"identity": selected, "style": selected, "mask": selected, "provenance": selected}, "manifest_path": "manifest.json", "comparison_sheet_path": final_report["comparisons"][0]["path"] if final_report.get("comparisons") else None, "blockers": [], "warnings": []})
        atomic_json_write(job_root / "manifest.json", {"job_id": job_id, "selected_candidate": selected, "finalization": final_report, "dds": dds_report, "workflow_version": WORKFLOW_VERSION, "dependency_lock_version": DEPENDENCY_LOCK_VERSION})
        self._write_state(job_root, "COMPLETED", stage="COMPLETED", exit_code=0)
        return self._write_output(job_root, output)

    def status(self, job_id: str) -> dict[str, Any]:
        job_root = self._job_root(job_id)
        status_path = job_root / "status.json"
        if status_path.is_file():
            return json.loads(status_path.read_text(encoding="utf-8"))
        return {"job_id": job_id, "state": "UNKNOWN", "stage": "JOB_ACCEPTED", "blockers": ["job not found"]}

    def cancel(self, job_id: str, *, reason: str = "caller requested cancellation", caller: str | None = None) -> dict[str, Any]:
        job_root = self._job_root(job_id)
        status = self.status(job_id)
        if status.get("state") == "UNKNOWN":
            raise ValueError("job not found")
        if status.get("state") in {"COMPLETED", "FAILED", "CANCELED", "BLOCKED", "NEEDS_REVIEW"}:
            return status
        atomic_json_write(job_root / "cancel.json", {"job_id": job_id, "reason": reason, "caller": caller, "requested_at": datetime.now(timezone.utc).isoformat()})
        try:
            LoopbackComfyClient().cancel()
            interrupt = "PASS"
        except ComfyTransportError as exc:
            interrupt = {"status": "UNAVAILABLE", "code": exc.code.name}
        if status.get("state") not in {"COMPLETED", "FAILED", "CANCELED"}:
            self._write_state(job_root, "CANCELED", stage=str(status.get("stage", "JOB_ACCEPTED")), blockers=[reason], exit_code=int(ExitCode.CANCELED))
        status = self.status(job_id)
        status["cancel_interrupt"] = interrupt
        status["cancel_reason"] = reason
        status["cancel_caller"] = caller
        atomic_json_write(job_root / "status.json", status)
        return status


def _issue_exit_code(issues: list[ValidationIssue]) -> ExitCode:
    priorities = [
        ExitCode.BACKGROUND_UNRESOLVED,
        ExitCode.PROVENANCE_MISSING,
        ExitCode.SOURCE_INVALID,
        ExitCode.INPUT_SCHEMA_INVALID,
    ]
    issue_codes = {issue.code for issue in issues}
    for code in priorities:
        if code in issue_codes:
            return code
    return issues[0].code if issues else ExitCode.INPUT_SCHEMA_INVALID
