from __future__ import annotations

import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .constants import PROFILE_LIMITS, STYLE_LORA_PATH, STYLE_LORA_SHA256
from .experiments import build_matrix
from .preflight import collect_preflight
from .util import atomic_json_write, project_root, sanitize_public_paths, sha256_file
from .workflow_validation import validate_all_workflows


BENCHMARK_SCHEMA_VERSION = "1.0.0"
BENCHMARK_REPORT_VERSION = "runtime-capability-2026-07-26.1"
LOCAL_PROFILES = {"human_local_nvidia_16gb", "agent_local_nvidia_16gb"}
REMOTE_PROFILES = {"human_full_power_gpu", "agent_full_power_gpu"}


def _profile_applies(entry: dict[str, Any], profile: str) -> bool:
    profiles = entry.get("profiles")
    return not profiles or profile in profiles or "all" in profiles


def _model_budget(root: Path, profile: str) -> dict[str, Any]:
    lock_path = root / "dependencies" / "models.lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8")) if lock_path.is_file() else {}
    entries = [entry for entry in lock.get("models", []) if entry.get("mandatory") and _profile_applies(entry, profile)]
    artifacts: list[dict[str, Any]] = []
    expected_bytes = 0
    for entry in entries:
        if isinstance(entry.get("shard_size_bytes"), dict):
            size_bytes = sum(int(value) for value in entry["shard_size_bytes"].values())
        else:
            size_bytes = int(entry.get("size_bytes") or 0)
        expected_bytes += size_bytes
        artifacts.append({
            "name": entry.get("name"),
            "filename": entry.get("filename"),
            "size_bytes": size_bytes,
            "revision": entry.get("revision"),
            "sha256": entry.get("sha256") if isinstance(entry.get("sha256"), str) else None,
            "shard_sha256": entry.get("shard_sha256") if isinstance(entry.get("shard_sha256"), dict) else None,
            "source_url": entry.get("source_url"),
        })

    immutable_entry: dict[str, Any] | None = None
    immutable_entries = lock.get("project_owned_immutable_files", [])
    for entry in immutable_entries:
        if entry.get("path") == STYLE_LORA_PATH:
            immutable_entry = entry
            break
    style_path = root / STYLE_LORA_PATH
    actual_style_sha = sha256_file(style_path) if style_path.is_file() else None
    if immutable_entry is not None and immutable_entry.get("size_bytes") is not None:
        immutable_size = int(immutable_entry["size_bytes"])
        expected_bytes += immutable_size
        artifacts.append({
            "name": "immutable_style_lora",
            "filename": STYLE_LORA_PATH,
            "size_bytes": immutable_size,
            "repository": immutable_entry.get("repository"),
            "revision": immutable_entry.get("revision"),
            "sha256": STYLE_LORA_SHA256,
            "actual_sha256": actual_style_sha,
            "source_url": immutable_entry.get("source_url"),
            "source_visibility": immutable_entry.get("source_visibility"),
        })
    return {
        "lock_path": str(lock_path),
        "profile": profile,
        "artifacts": artifacts,
        "expected_model_bytes": expected_bytes,
        "style_lora_present": style_path.is_file(),
        "style_lora_sha256": actual_style_sha,
    }


def _physical_memory_bytes(report: dict[str, Any]) -> int | None:
    raw = report.get("hardware", {}).get("memory", {}).get("memsize_bytes")
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _gate_statuses(report: dict[str, Any]) -> dict[str, str]:
    return {str(gate.get("name")): str(gate.get("status")) for gate in report.get("gates", [])}


def _structural_measurement(root: Path, profile: str) -> dict[str, Any]:
    try:
        reports = validate_all_workflows(root)
    except Exception as exc:  # evidence generation must not hide a validation failure
        return {"status": "FAIL", "error_type": type(exc).__name__}
    selected = next((item for item in reports if item.get("workflow_id") == profile), None)
    if selected is None:
        return {"status": "FAIL", "reason": "profile workflow was not returned by validator"}
    return {
        "status": "PASS" if selected.get("structural_status") == "PASS" else "FAIL",
        "workflow_id": profile,
        "structural_status": selected.get("structural_status"),
        "runtime_status": "NOT_MEASURED",
        "issues": selected.get("issues", []),
    }


def _blocked_status(profile: str, preflight: dict[str, Any]) -> tuple[str, str]:
    statuses = _gate_statuses(preflight)
    if profile in LOCAL_PROFILES and statuses.get("local_runtime_capability") != "PASS":
        return "BLOCKED_RUNTIME_UNAVAILABLE", "The target local runtime is not installed or its accelerator capability is not verified."
    if profile in REMOTE_PROFILES:
        remote_status = statuses.get("remote_topology_auth")
        if remote_status != "PASS":
            return "BLOCKED_REMOTE_AUTH", "RunPod gateway authentication and remote acceptance are unavailable."
    if preflight.get("status") != "PASS":
        return "BLOCKED_PREFLIGHT", "One or more mandatory preflight gates remain blocked."
    return "BLOCKED_RUNTIME_UNAVAILABLE", "No live ComfyUI health, load, and generation measurements were recorded."


def _live_schema_measurements(root: Path, profile: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Use the pinned live probe for schema/load evidence without claiming execution."""

    path = root / ".runtime" / "reports" / "live_comfy_compatibility.json"
    try:
        probe = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        probe = {}
    live_status = probe.get("status")
    workflow = next((item for item in probe.get("workflows", []) if item.get("workflow_id") == profile), {})
    schema_pass = live_status == "PASS_SCHEMA_ONLY_EXECUTION_BLOCKED" and workflow.get("status") == "PASS"
    runtime_health = {
        "status": "PASS_SCHEMA_ONLY" if schema_pass else "NOT_MEASURED",
        "binding": probe.get("server", {}).get("base_url", "http://127.0.0.1:8188"),
        "raw_comfy_binding": probe.get("server", {}).get("raw_comfy_binding", "loopback_only"),
        "reason": "Live health and /object_info schema evidence exists; no source-specific generation claim is made.",
        "evidence_path": ".runtime/reports/live_comfy_compatibility.json",
    }
    workflow_load = {
        "status": "PASS_SCHEMA_ONLY" if schema_pass else "NOT_MEASURED",
        "workflow_id": profile,
        "reason": "Live node-registry/load-shape validation passed; this is not a model-loading or eight-step execution result." if schema_pass else "Live schema evidence is unavailable for this profile.",
        "evidence_path": ".runtime/reports/live_comfy_compatibility.json",
    }
    return runtime_health, workflow_load


def _local_execution_evidence(root: Path, profile: str) -> dict[str, Any]:
    """Return runtime evidence only when a target-host benchmark is present."""

    return {"status": "NOT_RECORDED", "candidate_count": 0}


def build_benchmark_report(root: str | Path | None, profile: str) -> dict[str, Any]:
    root_path = project_root(root)
    if profile not in PROFILE_LIMITS:
        raise ValueError(f"unknown execution profile: {profile}")
    preflight = collect_preflight(root_path, profile=profile)
    status, status_reason = _blocked_status(profile, preflight)
    budget = _model_budget(root_path, profile)
    physical_memory = _physical_memory_bytes(preflight)
    expected_bytes = budget["expected_model_bytes"]
    ratio = expected_bytes / physical_memory if physical_memory else None
    if physical_memory and expected_bytes > physical_memory:
        capacity_assessment = "MODEL_BYTES_EXCEED_PHYSICAL_MEMORY_RISK_ONLY"
    elif physical_memory:
        capacity_assessment = "MODEL_BYTES_WITHIN_PHYSICAL_MEMORY_NOT_EXECUTION_PROOF"
    else:
        capacity_assessment = "PHYSICAL_MEMORY_UNAVAILABLE"
    structural = _structural_measurement(root_path, profile)
    gate_statuses = _gate_statuses(preflight)
    runtime_health, workflow_load = _live_schema_measurements(root_path, profile)
    execution_evidence = _local_execution_evidence(root_path, profile)
    if execution_evidence.get("status") == "PASS_EXECUTION_ONLY":
        status = "BLOCKED_PRODUCTION_GATES_CPU_FALLBACK"
        status_reason = "A private CPU fallback candidate was produced, but local production acceptance remains blocked by accelerator, memory, calibration, and audit gates."
        runtime_health["execution_evidence"] = execution_evidence
        workflow_load["execution_evidence"] = execution_evidence
    if profile in {"human_local_nvidia_16gb", "agent_local_nvidia_16gb"}:
        runtime_health["target_profile_accelerator"] = "CUDA"
        runtime_health["target_profile_accelerator_status"] = gate_statuses.get("local_runtime_capability")
    elif profile in REMOTE_PROFILES:
        runtime_health["target_profile_accelerator"] = "RunPod NVIDIA GPU"
        runtime_health["target_profile_accelerator_status"] = gate_statuses.get("remote_topology_auth")
    preprocessing_ready = gate_statuses.get("approved_source_background") == "PASS" and gate_statuses.get("source_fixture_and_provenance") == "PASS"
    dry_validation_job = ({"status": "PASS_PREPROCESSING_ONLY_PRODUCTION_GATES_BLOCKED", "reason": "The source fixture, approved background, and deterministic preprocessing route are evidenced; calibrated identity/style thresholds and independent audit still block promotion."} if preprocessing_ready else {"status": "BLOCKED_NO_APPROVED_FIXTURE_OR_BACKGROUND", "reason": "The live schema probe and private preprocessing qualification passed, but no production-authorized source fixture and approved background are available."})
    required_follow_up = [
        "run the target profile inside its target accelerator environment without mutation",
        "verify RunPod gateway authentication, custom-node parity, model availability, and source upload behavior",
        "complete live source-specific model loading and the eight-step Turbo execution",
        "verify all model revisions, formats, sizes, and SHA-256 values in the target environment",
        "run the target profile with independent identity/style/mask/provenance audit",
        "record peak host memory, peak VRAM, runtime, thermal, cancellation, and repeatability evidence",
    ]
    if not preprocessing_ready:
        required_follow_up.insert(4, "provide an approved source fixture, background, and rights record")
    return {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "report_version": BENCHMARK_REPORT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "status": status,
        "status_reason": status_reason,
        "hardware": {
            "platform": platform.platform(),
            "python": sys.version,
            "machine": platform.machine(),
            "preflight_snapshot": preflight.get("hardware", {}),
        },
        "preflight": {
            "status": preflight.get("status"),
            "recommended_exit_code": preflight.get("recommended_exit_code"),
            "gate_statuses": gate_statuses,
            "blockers": preflight.get("blockers", []),
        },
        "resource_model": {
            "expected_model_bytes": expected_bytes,
            "physical_memory_bytes": physical_memory,
            "expected_model_to_physical_memory_ratio": ratio,
            "capacity_assessment": capacity_assessment,
            "peak_memory_bytes": None,
            "peak_vram_bytes": None,
            "measurement_note": "File-size arithmetic is not a measured execution or OOM result; offload, allocator overhead, activations, and runtime staging remain unmeasured.",
            "locked_artifacts": budget["artifacts"],
        },
        "measurements": {
            "workflow_structure": structural,
            "runtime_health": runtime_health,
            "workflow_load": workflow_load,
            "dry_validation_job": dry_validation_job,
            "generation": ({"status": "PASS_EXECUTION_ONLY_PRODUCTION_BLOCKED", "candidate_count": 1, "candidate_path": execution_evidence.get("candidate_path"), "candidate_sha256": execution_evidence.get("candidate_sha256"), "reason": "A checksum-recorded CPU fallback candidate exists, but it is quarantined from production promotion."} if execution_evidence.get("status") == "PASS_EXECUTION_ONLY" else {"status": "BLOCKED_NOT_ATTEMPTED", "candidate_count": 0, "reason": "Portrait generation was not attempted while source, background, threshold, and audit gates remained blocked."}),
            "thermal": {"status": "NOT_MEASURED", "samples": [], "swap_observed": execution_evidence.get("status") == "PASS_EXECUTION_ONLY", "reason": "Thermal samples were not captured for this run; CPU fallback evidence records swap behavior separately."},
            "quality": ({"status": "UNCERTAIN_AUDIT", "candidate_count": 1, "identity_pass_rate": None, "style_pass_rate_among_identity_pass": None, "audit_verdict": execution_evidence.get("audit_verdict"), "face_embedding_similarity": execution_evidence.get("face_embedding_similarity")} if execution_evidence.get("status") == "PASS_EXECUTION_ONLY" else {"status": "NOT_MEASURED", "candidate_count": 0, "identity_pass_rate": None, "style_pass_rate_among_identity_pass": None}),
            "failure_recovery": {"status": "NOT_MEASURED", "cancellation": "NOT_MEASURED", "oom_recovery": "NOT_MEASURED", "restart_repeatability": "NOT_MEASURED"},
        },
        "required_follow_up": required_follow_up,
        "claims": {
            "local_generation": ("EXECUTION_ONLY_CPU_FALLBACK_PRODUCTION_NOT_CLAIMED" if execution_evidence.get("status") == "PASS_EXECUTION_ONLY" else "NOT_CLAIMED") if profile in LOCAL_PROFILES else "NOT_APPLICABLE",
            "remote_generation": "NOT_CLAIMED" if profile in REMOTE_PROFILES else "NOT_APPLICABLE",
            "local_preprocessing_and_validation": "STRUCTURE_ONLY",
            "final_png": "NOT_CREATED",
            "final_dds": "NOT_CREATED",
        },
        "provenance": {
            "matrix_id": build_matrix()["matrix_id"],
            "selection_order": build_matrix()["selection_order"],
            "style_lora_sha256": STYLE_LORA_SHA256,
            "style_lora_observed_sha256": budget["style_lora_sha256"],
            "execution_evidence": execution_evidence,
        },
    }


def render_benchmark_markdown(report: dict[str, Any]) -> str:
    resource = report["resource_model"]
    measurements = report["measurements"]
    lines = [
        f"# Benchmark Report: `{report['profile']}`",
        "",
        f"- Status: **{report['status']}**",
        f"- Reason: {report['status_reason']}",
        f"- Expected locked model bytes: `{resource['expected_model_bytes']}`",
        f"- Physical memory bytes: `{resource['physical_memory_bytes']}`",
        f"- Capacity assessment: **{resource['capacity_assessment']}**",
        "",
        "This report contains no production acceptance claim. Any CPU diagnostic execution evidence is explicitly quarantined from promotion. File-size arithmetic is a risk indicator, not an infeasibility measurement.",
        "",
        "## Gate status",
        "",
        "| Gate | Status |",
        "| --- | --- |",
    ]
    lines.extend(f"| `{name}` | **{status}** |" for name, status in sorted(report["preflight"]["gate_statuses"].items()))
    lines.extend(["", "## Measurements", "", "| Measurement | Status |", "| --- | --- |"])
    for name, value in measurements.items():
        lines.append(f"| `{name}` | **{value.get('status', 'SEE_JSON')}** |")
    lines.extend(["", "## Blockers", ""])
    lines.extend(f"- {item}" for item in report["preflight"]["blockers"])
    lines.extend(["", "## Required follow-up", ""])
    lines.extend(f"- {item}" for item in report["required_follow_up"])
    return "\n".join(lines) + "\n"


def write_benchmark_reports(root: str | Path | None = None, profiles: Iterable[str] | None = None) -> list[dict[str, Any]]:
    root_path = project_root(root)
    selected = tuple(profiles) if profiles is not None else tuple(PROFILE_LIMITS)
    output_dir = root_path / ".runtime" / "reports" / "benchmarks"
    output_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    for profile in selected:
        report = build_benchmark_report(root_path, profile)
        atomic_json_write(output_dir / f"{profile}.json", sanitize_public_paths(report, root_path))
        (output_dir / f"{profile}.md").write_text(render_benchmark_markdown(report), encoding="utf-8")
        reports.append(report)
    return reports


def main(root: str | Path | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Record fail-closed runtime capability and benchmark evidence.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--profile", choices=tuple(PROFILE_LIMITS), action="append")
    parser.add_argument("--strict", action="store_true", help="return the first profile's recommended exit code when a report is blocked")
    args = parser.parse_args() if root is None else argparse.Namespace(root=root, profile=None, strict=False)
    reports = write_benchmark_reports(args.root, args.profile)
    print(json.dumps(reports, indent=2, ensure_ascii=False))
    if args.strict:
        blocked = next((report for report in reports if report["status"] != "PASS"), None)
        return int(blocked["preflight"]["recommended_exit_code"] if blocked else 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
