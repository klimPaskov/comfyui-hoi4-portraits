from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .audit import audit_is_pass, load_audits
from .constants import (
    DEPENDENCY_LOCK_VERSION,
    ExitCode,
    JobStatus,
    STAGES,
    WORKFLOW_VERSION,
)
from .contracts import ValidationIssue, build_blocked_output, validate_job
from .dds import convert_png_to_dds
from .preflight import collect_preflight
from .selection import select_identity_first
from .util import atomic_json_write, canonical_hash, project_root, relative_safe_path, sha256_file


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

    def _write_state(self, job_root: Path, state: str, *, stage: str, blockers: list[str] | None = None, warnings: list[str] | None = None, exit_code: int | None = None) -> None:
        atomic_json_write(job_root / "status.json", {
            "schema_version": "1.0.0",
            "job_id": job_root.name,
            "state": state,
            "stage": stage,
            "stage_index": STAGES.index(stage) if stage in STAGES else None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "attempt": 0,
            "progress": 0.0 if state != "COMPLETED" else 1.0,
            "warnings": warnings or [],
            "blockers": blockers or [],
            "terminal_exit_code": exit_code,
        })

    def _write_output(self, job_root: Path, output: dict[str, Any]) -> JobResult:
        atomic_json_write(job_root / "output.json", output)
        return JobResult(output, job_root)

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
        return JobResult({"status": "SUBMITTED", "job_id": job_id, "input_hash": semantic_hash}, job_root)

    def _preflight_blocker(self, job: dict[str, Any]) -> tuple[ExitCode, list[str]] | None:
        report = collect_preflight(self.root)
        blockers = list(report["blockers"])
        if not blockers:
            return None
        if any("background" in item.casefold() for item in blockers):
            return ExitCode.BACKGROUND_UNRESOLVED, blockers
        if job.get("execution_profile") == "agent_remote_runpod" and any("RunPod" in item or "remote" in item.casefold() for item in blockers):
            return ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED, blockers
        return ExitCode.DEPENDENCY_MISSING, blockers

    def run(self, job_id: str) -> JobResult:
        job_root = self._job_root(job_id)
        input_path = job_root / "input.json"
        if not input_path.is_file():
            output = build_blocked_output({"job_id": job_id}, ExitCode.SOURCE_INVALID, "job input is missing", root=self.root)
            job_root.mkdir(parents=True, exist_ok=True)
            self._write_state(job_root, "BLOCKED", stage="JOB_ACCEPTED", blockers=["job input is missing"], exit_code=int(ExitCode.SOURCE_INVALID))
            return self._write_output(job_root, output)
        job = json.loads(input_path.read_text(encoding="utf-8"))
        blocker = self._preflight_blocker(job)
        if blocker:
            code, blockers = blocker
            output = build_blocked_output(job, code, blockers[0], blockers=blockers, root=self.root)
            self._write_state(job_root, "BLOCKED", stage="JOB_ACCEPTED", blockers=blockers, exit_code=int(code))
            return self._write_output(job_root, output)
        # A successful preflight still does not bypass the runtime experiment,
        # independent audit, or candidate-selection gates. Generation is
        # intentionally delegated to the authenticated Comfy adapter.
        output = build_blocked_output(job, ExitCode.GENERATION_FAILED, "ComfyUI execution was not invoked by this controller instance", blockers=["authenticated ComfyUI route required"], root=self.root)
        self._write_state(job_root, "FAILED", stage="WORKFLOW_VALIDATED", blockers=output["blockers"], exit_code=int(ExitCode.GENERATION_FAILED))
        return self._write_output(job_root, output)

    def promote(self, job_id: str, audit_paths: list[str | Path]) -> JobResult:
        job_root = self._job_root(job_id)
        job = json.loads((job_root / "input.json").read_text(encoding="utf-8"))
        audits = load_audits(audit_paths, self.root)
        selected, selection_report = select_identity_first(audits)
        atomic_json_write(job_root / "audit" / "selection.json", selection_report)
        if selected is None:
            code = ExitCode.AUDIT_UNCERTAIN if any(audit.get("verdict") == "UNCERTAIN" for audit in audits) else ExitCode.IDENTITY_NO_PASSING_CANDIDATE
            output = build_blocked_output(job, code, "no independently audited PASS candidate exists", blockers=["DDS and mod integration remain prohibited"], root=self.root)
            self._write_state(job_root, "NEEDS_REVIEW", stage="CANDIDATE_SELECTED", blockers=output["blockers"], exit_code=int(code))
            return self._write_output(job_root, output)
        candidate = Path(selected["evidence"]["candidate"])
        if not candidate.is_absolute():
            candidate = job_root / candidate
        final_png = job_root / "final" / f"{job['final_output_stem']}.png"
        final_dds = job_root / "final" / f"{job['final_output_stem']}.dds"
        # The audited candidate is still not promoted here unless a separate
        # final-PNG processor has created an exact 156x210 opaque PNG.
        if not final_png.is_file():
            output = build_blocked_output(job, ExitCode.DDS_VALIDATION_FAILED, "audited candidate has no validated final 156x210 PNG", blockers=["final PNG processing is required before DDS conversion"], root=self.root)
            self._write_state(job_root, "BLOCKED", stage="PNG_VALIDATED", blockers=output["blockers"], exit_code=int(ExitCode.DDS_VALIDATION_FAILED))
            return self._write_output(job_root, output)
        audit_path = next(Path(path) for path in audit_paths if json.loads(Path(path).read_text(encoding="utf-8")).get("candidate_id") == selected.get("candidate_id"))
        try:
            dds_report = convert_png_to_dds(final_png, final_dds, audit_path, self.root)
        except Exception as exc:
            output = build_blocked_output(job, ExitCode.DDS_VALIDATION_FAILED, str(exc), blockers=["DDS validator rejected finalization"], root=self.root)
            self._write_state(job_root, "FAILED", stage="DDS_VALIDATED", blockers=output["blockers"], exit_code=int(ExitCode.DDS_VALIDATION_FAILED))
            return self._write_output(job_root, output)
        output = build_blocked_output(job, ExitCode.SUCCESS, "")
        output.update({"status": JobStatus.SUCCEEDED.value, "error_code": None, "error_message": None, "selected_candidate": selected["candidate_id"], "final_png": str(final_png.relative_to(job_root)), "final_dds": str(final_dds.relative_to(job_root)), "final_checksums": {"png": sha256_file(final_png), "dds": dds_report["sha256"]}, "audits": {"identity": selected, "style": selected, "mask": selected, "provenance": selected}, "manifest_path": "manifest.json", "comparison_sheet_path": selected["evidence"].get("native_comparison"), "blockers": [], "warnings": []})
        atomic_json_write(job_root / "manifest.json", {"job_id": job_id, "selected_candidate": selected, "dds": dds_report, "workflow_version": WORKFLOW_VERSION, "dependency_lock_version": DEPENDENCY_LOCK_VERSION})
        self._write_state(job_root, "COMPLETED", stage="COMPLETED", exit_code=0)
        return self._write_output(job_root, output)

    def status(self, job_id: str) -> dict[str, Any]:
        job_root = self._job_root(job_id)
        status_path = job_root / "status.json"
        if status_path.is_file():
            return json.loads(status_path.read_text(encoding="utf-8"))
        return {"job_id": job_id, "state": "UNKNOWN", "stage": "JOB_ACCEPTED", "blockers": ["job not found"]}


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

