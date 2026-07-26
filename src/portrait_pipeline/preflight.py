from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import ExitCode, STYLE_LORA_PATH, STYLE_LORA_SHA256
from .util import atomic_json_write, project_root, sha256_file


def _command(*args: str) -> dict[str, Any]:
    try:
        completed = subprocess.run(args, capture_output=True, text=True, timeout=15, check=False)
        return {
            "command": list(args),
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
    except (OSError, subprocess.SubprocessError) as exc:
        return {"command": list(args), "returncode": None, "stdout": "", "stderr": str(exc)}


def _command_text(*args: str) -> str | None:
    result = _command(*args)
    if result["returncode"] == 0 and result["stdout"]:
        return result["stdout"]
    return None


def _tool_version(command: str, *args: str) -> dict[str, Any]:
    path = shutil.which(command)
    result: dict[str, Any] = {"command": command, "path": path, "present": path is not None}
    if path is not None:
        result["probe"] = _command(path, *args)
    return result


def _memory_snapshot() -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    if platform.system() == "Darwin":
        for key, args in (
            ("memsize_bytes", ("sysctl", "-n", "hw.memsize")),
            ("cpu_count", ("sysctl", "-n", "hw.ncpu")),
            ("arm64", ("sysctl", "-n", "hw.optional.arm64")),
        ):
            value = _command_text(*args)
            snapshot[key] = value
        snapshot["swap"] = _command("/usr/sbin/sysctl", "vm.swapusage")
        snapshot["vm_stat"] = _command("/usr/bin/vm_stat")
    else:
        snapshot["platform"] = platform.platform()
    return snapshot


def _repo_snapshot(path: Path) -> dict[str, Any]:
    if not path.is_dir():
        return {"path": str(path), "exists": False}
    # Use explicit subprocess calls because the helper intentionally only takes argv.
    def git(*args: str) -> dict[str, Any]:
        try:
            result = subprocess.run(["git", *args], cwd=path, capture_output=True, text=True, timeout=15, check=False)
            return {"returncode": result.returncode, "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}
        except (OSError, subprocess.SubprocessError) as exc:
            return {"returncode": None, "stdout": "", "stderr": str(exc)}

    return {
        "path": str(path),
        "exists": True,
        "is_git": (path / ".git").exists(),
        "status": git("status", "--short", "--branch"),
        "head": git("rev-parse", "HEAD"),
        "remote": git("remote", "-v"),
    }


def _planning_checksum_check(root: Path) -> dict[str, Any]:
    checksum_file = root / "checksums.sha256"
    results: list[dict[str, Any]] = []
    if not checksum_file.is_file():
        return {"status": "BLOCKED", "results": [], "reason": "checksums.sha256 missing"}
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        expected, relative = line.split(maxsplit=1)
        candidate = root / relative
        actual = sha256_file(candidate) if candidate.is_file() else None
        results.append({"path": relative, "expected": expected, "actual": actual, "match": actual == expected})
    return {"status": "PASS" if all(item["match"] for item in results) else "BLOCKED", "results": results}


def _env_presence() -> dict[str, bool]:
    names = (
        "RUNPOD_API_KEY",
        "RUNPOD_ENDPOINT_ID",
        "HF_TOKEN",
        "GITHUB_TOKEN",
        "PORTRAIT_GATEWAY_TOKEN",
    )
    return {name: bool(os.environ.get(name)) for name in names}


def collect_preflight(root: str | Path | None = None) -> dict[str, Any]:
    root_path = project_root(root)
    live_chaos = Path("/Users/klimpaskov/Documents/Paradox Interactive/Hearts of Iron IV/mod/Chaos-Redux")
    generic_candidates = [
        Path("/Users/klimpaskov/Documents/Projects/agentic-hoi4-modding"),
        Path("/Users/klimpaskov/Documents/Projects/agentic-hoi4"),
        root_path / "integrations" / "agentic-hoi4-modding",
    ]
    style_path = root_path / STYLE_LORA_PATH
    background_registry = root_path / "config" / "background_registry.json"
    registry = json.loads(background_registry.read_text(encoding="utf-8")) if background_registry.is_file() else {}
    background_resolved = registry.get("registry_status") == "RESOLVED" and any(
        item.get("status") == "APPROVED" and item.get("sha256") for item in registry.get("backgrounds", [])
    )
    model_root = root_path / "models"
    comfy_path = shutil.which("comfy") or shutil.which("comfy-cli")
    try:
        import torch  # type: ignore

        torch_probe: dict[str, Any] = {
            "installed": True,
            "version": getattr(torch, "__version__", None),
            "mps_available": bool(getattr(getattr(torch, "backends", None), "mps", None) and torch.backends.mps.is_available()),
        }
    except Exception as exc:  # missing optional dependency is a reportable gate, not a crash
        torch_probe = {"installed": False, "error_type": type(exc).__name__, "error": str(exc)}

    blockers: list[str] = []
    gates: list[dict[str, Any]] = []

    hardware = {
        "platform": platform.platform(),
        "python": sys.version,
        "machine": platform.machine(),
        "processor": platform.processor(),
        "memory": _memory_snapshot(),
        "sw_vers": _command("sw_vers"),
        "disk": _command("df", "-h", str(root_path)),
    }
    gates.append({
        "name": "hardware_detection",
        "status": "PASS" if hardware["memory"].get("memsize_bytes") == "17179869184" and platform.system() == "Darwin" else "UNVERIFIED",
        "evidence": hardware,
    })
    python_floor_ok = sys.version_info >= (3, 10)
    gates.append({
        "name": "local_runtime_capability",
        "status": "PASS" if python_floor_ok and torch_probe.get("installed") and torch_probe.get("mps_available") else "BLOCKED",
        "evidence": {"python_version": platform.python_version(), "python_floor": ">=3.10", "python_floor_ok": python_floor_ok, "torch": torch_probe, "comfy_cli": comfy_path},
    })
    if gates[-1]["status"] == "BLOCKED":
        blockers.append("PyTorch/MPS and ComfyUI are not installed or MPS capability is not verified; local execution cannot be claimed.")

    lora_present = style_path.is_file()
    lora_actual = sha256_file(style_path) if lora_present else None
    lora_status = "PASS" if lora_actual == STYLE_LORA_SHA256 else "BLOCKED"
    gates.append({
        "name": "immutable_style_lora",
        "status": lora_status,
        "evidence": {"path": str(style_path), "present": lora_present, "expected_sha256": STYLE_LORA_SHA256, "actual_sha256": lora_actual, "immutable": True},
    })
    if lora_status != "PASS":
        blockers.append("The required immutable style LoRA is missing or its checksum does not match.")

    background_status = "PASS" if background_resolved else "BLOCKED"
    gates.append({
        "name": "approved_source_background",
        "status": background_status,
        "evidence": {"registry_path": str(background_registry), "registry": registry},
    })
    if background_status != "PASS":
        blockers.append("The approved HOI4 portrait background registry is unresolved; generation and DDS promotion are blocked.")

    fixture_files = [str(path.relative_to(root_path)) for path in (root_path / "fixtures").rglob("*") if path.is_file()] if (root_path / "fixtures").is_dir() else []
    source_fixture_status = "PASS" if fixture_files else "BLOCKED"
    gates.append({"name": "source_fixture_and_provenance", "status": source_fixture_status, "evidence": {"fixture_files": fixture_files, "manifest_template": str(root_path / "tests/fixture_manifest.template.json")}})
    if source_fixture_status != "PASS":
        blockers.append("No legally usable source portrait fixture and complete provenance record is present for calibration or route execution.")

    planning_checksums = _planning_checksum_check(root_path)
    gates.append({"name": "planning_package_checksums", **planning_checksums})
    if planning_checksums["status"] != "PASS":
        blockers.append("One or more planning package checksums do not match.")

    model_entries = json.loads((root_path / "dependencies" / "models.lock.json").read_text(encoding="utf-8")).get("models", [])
    local_model_files = [str(path.relative_to(root_path)) for path in model_root.rglob("*") if path.is_file()] if model_root.is_dir() else []
    model_status = "PASS" if local_model_files and all(entry.get("sha256") or entry.get("shard_sha256") for entry in model_entries if entry.get("mandatory")) else "BLOCKED"
    gates.append({"name": "model_artifact_preflight", "status": model_status, "evidence": {"local_files": local_model_files, "locked_models": len(model_entries), "unsupported_or_unverified": [entry["name"] for entry in model_entries if entry.get("sha256") is None and entry.get("shard_sha256") is None]}})
    if model_status != "PASS":
        blockers.append("Required Krea/Qwen model artifacts are not installed and live ComfyUI compatibility has not been verified.")

    runtime_lock_path = root_path / "dependencies" / "runtime_requirements_lock.json"
    runtime_lock = json.loads(runtime_lock_path.read_text(encoding="utf-8")) if runtime_lock_path.is_file() else {}
    runtime_unresolved = [item.get("name") for item in runtime_lock.get("requirements", []) if item.get("mandatory") and (item.get("sha256") is None or str(item.get("version", "")).startswith("UNRESOLVED"))]
    runtime_lock_status = "PASS" if runtime_lock.get("status") == "RESOLVED" and not runtime_unresolved else "BLOCKED"
    gates.append({"name": "comfyui_runtime_dependency_lock", "status": runtime_lock_status, "evidence": {"path": str(runtime_lock_path), "unresolved": runtime_unresolved}})
    if runtime_lock_status != "PASS":
        blockers.append("The pinned ComfyUI runtime dependency lock still contains unresolved platform versions or artifact checksums.")

    env_presence = _env_presence()
    gates.append({"name": "remote_topology_auth", "status": "PASS" if env_presence["RUNPOD_API_KEY"] and env_presence["RUNPOD_ENDPOINT_ID"] else "BLOCKED", "evidence": {"credential_presence": env_presence, "raw_comfyui_binding": "not configured"}})
    if gates[-1]["status"] == "BLOCKED":
        blockers.append("RunPod endpoint credentials are absent; remote submission/acceptance cannot run.")

    generic_existing = [str(path) for path in generic_candidates if path.is_dir() and path != root_path / "integrations" / "agentic-hoi4-modding"]
    repo_gate = {
        "name": "repository_preflight",
        "status": "PASS" if live_chaos.is_dir() else "BLOCKED",
        "evidence": {"chaos_redux": _repo_snapshot(live_chaos), "generic_candidates": generic_existing, "generic_target_status": "UNAVAILABLE" if not generic_existing else "FOUND"},
    }
    gates.append(repo_gate)
    if not live_chaos.is_dir():
        blockers.append("The live Chaos Redux target repository is unavailable.")
    if not generic_existing:
        blockers.append("No live generic agentic HOI4 target repository was found; only the planning proposal is available.")

    threshold_path = root_path / "config" / "identity_thresholds.json"
    thresholds = json.loads(threshold_path.read_text(encoding="utf-8")) if threshold_path.is_file() else {}
    threshold_status = "PASS" if thresholds.get("thresholds_id") not in {None, "UNSET_BLOCK_EXECUTION"} and thresholds.get("approved_by") and thresholds.get("fail_closed") is True else "BLOCKED"
    gates.append({"name": "calibrated_identity_thresholds", "status": threshold_status, "evidence": {"path": str(threshold_path), "present": threshold_path.is_file(), "thresholds_id": thresholds.get("thresholds_id"), "approved_by": thresholds.get("approved_by")}})
    if threshold_status != "PASS":
        blockers.append("Identity/style thresholds are still calibration placeholders; no production candidate may be accepted.")

    gates.append({"name": "krea_live_compatibility", "status": "BLOCKED", "evidence": {"reason": "ComfyUI and the pinned Krea custom node are not installed; node signatures and a live Turbo execution are unverified."}})
    blockers.append("Krea 2 Turbo compatibility, identity-edit behavior, and the immutable style LoRA matrix have not been measured in the pinned runtime.")

    preprocessing_lock_path = root_path / "dependencies" / "preprocessing_lock.json"
    preprocessing_lock = json.loads(preprocessing_lock_path.read_text(encoding="utf-8")) if preprocessing_lock_path.is_file() else {}
    preprocessing_missing = [entry.get("name") for entry in preprocessing_lock.get("dependencies", []) if entry.get("mandatory") and not entry.get("artifact_sha256")]
    preprocessing_status = "PASS" if not preprocessing_missing else "BLOCKED"
    gates.append({"name": "preprocessing_and_audit_dependencies", "status": preprocessing_status, "evidence": {"path": str(preprocessing_lock_path), "missing_checksums": preprocessing_missing}})
    if preprocessing_status != "PASS":
        blockers.append("Pinned preprocessing/audit model artifacts have no verified checksums; masking, face analysis, and independent audit cannot run.")

    license_review = json.loads((root_path / "dependencies" / "license_review.json").read_text(encoding="utf-8"))
    gates.append({"name": "license_and_rights_review", "status": license_review.get("status", "BLOCKED"), "evidence": license_review})
    blockers.append("License/rights review is not fully approved for Krea redistribution or the unresolved background.")

    return {
        "schema_version": "1.0.0",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(root_path),
        "hardware": hardware,
        "gates": gates,
        "blockers": list(dict.fromkeys(blockers)),
        "status": "PASS" if not blockers else "BLOCKED",
        "recommended_exit_code": int(ExitCode.BACKGROUND_UNRESOLVED if background_status != "PASS" else ExitCode.DEPENDENCY_MISSING),
        "installation_permitted": False if blockers else True,
        "policy": "No model, node, or runtime installation is authorized while a hard preflight blocker remains.",
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Initial Preflight Report",
        "",
        f"- Collected: `{report['collected_at']}`",
        f"- Status: **{report['status']}**",
        f"- Installation permitted: **{report['installation_permitted']}**",
        f"- Recommended exit code: `{report['recommended_exit_code']}`",
        "",
        "## Gates",
        "",
        "| Gate | Status | Evidence summary |",
        "| --- | --- | --- |",
    ]
    for gate in report["gates"]:
        summary = json.dumps(gate.get("evidence", {}), ensure_ascii=False, sort_keys=True)
        lines.append(f"| `{gate['name']}` | **{gate['status']}** | `{summary[:500]}` |")
    lines.extend(["", "## Blockers", ""])
    lines.extend(f"- {item}" for item in report["blockers"])
    lines.extend(["", "## Installation decision", "", report["policy"], ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run fail-closed hardware, topology, dependency, license, background, LoRA, and repository preflights.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--markdown-out", type=Path, default=None)
    args = parser.parse_args(argv)
    root = project_root(args.root)
    report = collect_preflight(root)
    json_out = args.json_out or root / "docs" / "preflight" / "initial_preflight.json"
    markdown_out = args.markdown_out or root / "docs" / "preflight" / "initial_preflight.md"
    atomic_json_write(json_out, report)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else int(report["recommended_exit_code"])
