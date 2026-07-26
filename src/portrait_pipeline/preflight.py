from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import ExitCode, PROFILE_LIMITS, STYLE_LORA_PATH, STYLE_LORA_SHA256
from .util import atomic_json_write, is_sha256, project_root, relative_safe_path, sha256_file, tree_sha256

SUPPORTED_MODEL_SUFFIXES = {".safetensors", ".gguf"}


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


def _profile_applies(entry: dict[str, Any], profile: str | None) -> bool:
    if profile is None:
        return True
    profiles = entry.get("profiles")
    return not profiles or profile in profiles or "all" in profiles


def _model_artifact_preflight(root: Path, model_root: Path, entries: list[dict[str, Any]], profile: str | None) -> dict[str, Any]:
    """Verify every scoped model at its locked path, size, and SHA-256.

    A directory-level existence check is not enough: it could accept an
    unrelated or unsupported model.  Sharded entries are checked file by
    file, and any extra model artifact is treated as an unlocked input.
    """

    scoped = [entry for entry in entries if entry.get("mandatory") and _profile_applies(entry, profile)]
    expected_paths: set[Path] = set()
    checks: list[dict[str, Any]] = []
    all_pass = True
    for entry in scoped:
        destination = root / str(entry.get("destination_folder", "models"))
        shard_hashes = entry.get("shard_sha256")
        if isinstance(shard_hashes, dict):
            shard_sizes = entry.get("shard_size_bytes", {})
            for filename, expected_hash in sorted(shard_hashes.items()):
                path = destination / filename
                expected_paths.add(path.resolve())
                format_ok = Path(filename).suffix.casefold() in SUPPORTED_MODEL_SUFFIXES
                actual_hash = sha256_file(path) if path.is_file() else None
                actual_size = path.stat().st_size if path.is_file() else None
                size_ok = filename not in shard_sizes or actual_size == shard_sizes[filename]
                hash_ok = is_sha256(expected_hash) and actual_hash == expected_hash
                item_ok = path.is_file() and format_ok and size_ok and hash_ok
                all_pass &= item_ok
                checks.append({"name": entry.get("name"), "path": str(path.relative_to(root)), "format": Path(filename).suffix.casefold() or None, "format_supported": format_ok, "present": path.is_file(), "size_bytes": actual_size, "expected_size_bytes": shard_sizes.get(filename), "sha256": actual_hash, "expected_sha256": expected_hash, "status": "PASS" if item_ok else "BLOCKED"})
            continue
        filename = entry.get("filename")
        expected_hash = entry.get("sha256")
        if not isinstance(filename, str) or not filename or not is_sha256(expected_hash):
            all_pass = False
            checks.append({"name": entry.get("name"), "status": "BLOCKED", "reason": "locked filename or SHA-256 is missing"})
            continue
        format_ok = Path(filename).suffix.casefold() in SUPPORTED_MODEL_SUFFIXES
        path = destination / filename
        expected_paths.add(path.resolve())
        actual_hash = sha256_file(path) if path.is_file() else None
        actual_size = path.stat().st_size if path.is_file() else None
        expected_size = entry.get("size_bytes")
        size_ok = expected_size is None or actual_size == expected_size
        item_ok = path.is_file() and format_ok and size_ok and actual_hash == expected_hash
        all_pass &= item_ok
        checks.append({"name": entry.get("name"), "path": str(path.relative_to(root)), "format": Path(filename).suffix.casefold() or None, "format_supported": format_ok, "present": path.is_file(), "size_bytes": actual_size, "expected_size_bytes": expected_size, "sha256": actual_hash, "expected_sha256": expected_hash, "status": "PASS" if item_ok else "BLOCKED"})

    unexpected: list[str] = []
    if model_root.is_dir():
        for path in model_root.rglob("*"):
            if path.is_file() and path.resolve() not in expected_paths:
                unexpected.append(str(path.relative_to(root)))
    if unexpected:
        all_pass = False
    return {"status": "PASS" if all_pass and bool(scoped) else "BLOCKED", "profile": profile, "checks": checks, "unexpected_files": sorted(unexpected), "scoped_mandatory_models": [entry.get("name") for entry in scoped]}


def _background_preflight(root: Path, registry_path: Path, registry: dict[str, Any]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for item in registry.get("backgrounds", []):
        runtime_value = item.get("runtime_path") or item.get("path")
        actual_hash = None
        path_error = None
        if runtime_value:
            try:
                path = relative_safe_path(root, str(runtime_value))
                if path.is_file():
                    actual_hash = sha256_file(path)
                else:
                    path_error = "runtime background file is missing"
            except ValueError as exc:
                path_error = str(exc)
        else:
            path = None
            path_error = "runtime path is missing"
        expected_hash = item.get("sha256")
        item_ok = item.get("status") == "APPROVED" and is_sha256(expected_hash) and actual_hash == expected_hash and path_error is None
        entries.append({"registry_id": item.get("registry_id"), "status": item.get("status"), "path": runtime_value, "expected_sha256": expected_hash, "actual_sha256": actual_hash, "path_error": path_error, "status_check": "PASS" if item_ok else "BLOCKED"})
    candidate_path = root / "docs" / "preflight" / "background_candidates.json"
    candidate_status = None
    if candidate_path.is_file():
        try:
            candidate_status = json.loads(candidate_path.read_text(encoding="utf-8")).get("candidates", [])
        except json.JSONDecodeError:
            candidate_status = "INVALID_JSON"
    return {"status": "PASS" if registry.get("registry_status") == "RESOLVED" and any(item["status_check"] == "PASS" for item in entries) else "BLOCKED", "registry_path": str(registry_path), "registry_status": registry.get("registry_status"), "entries": entries, "candidate_evidence_path": str(candidate_path), "candidate_evidence": candidate_status}


def _custom_node_preflight(root: Path) -> dict[str, Any]:
    lock_path = root / "dependencies" / "custom_nodes.lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8")) if lock_path.is_file() else {}
    comfy_root = root / "comfyui"
    checks: list[dict[str, Any]] = []
    for entry in lock.get("custom_nodes", []):
        if entry.get("name") == "hoi4_portrait_project_nodes":
            source_root = root / "src" / "comfyui_hoi4_portrait_nodes"
            present = (source_root / "__init__.py").is_file()
            expected_classes = set(entry.get("classes", []))
            expected_source_checksum = entry.get("source_tree_checksum")
            actual_source_checksum = tree_sha256(source_root) if present else None
            source_match = is_sha256(expected_source_checksum) and actual_source_checksum == expected_source_checksum
            try:
                import importlib

                module = importlib.import_module("comfyui_hoi4_portrait_nodes")
                actual_classes = set(getattr(module, "NODE_CLASS_MAPPINGS", {}))
                class_match = expected_classes <= actual_classes
            except Exception as exc:
                actual_classes = []
                class_match = False
                checks.append({"name": entry.get("name"), "status": "BLOCKED", "reason": f"import failed: {type(exc).__name__}"})
                continue
            checks.append({"name": entry.get("name"), "present": present, "expected_classes": sorted(expected_classes), "actual_classes": sorted(actual_classes), "expected_source_tree_checksum": expected_source_checksum, "actual_source_tree_checksum": actual_source_checksum, "source_checksum_match": source_match, "status": "PASS" if present and class_match and source_match else "BLOCKED"})
        else:
            checkout = comfy_root / "custom_nodes" / str(entry.get("name"))
            present = checkout.is_dir()
            expected_revision = str(entry.get("revision", ""))
            actual_revision = None
            revision_match = False
            signature_files: list[str] = []
            signature_text = ""
            if present:
                try:
                    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=checkout, capture_output=True, text=True, timeout=15, check=False)
                    actual_revision = result.stdout.strip() if result.returncode == 0 else None
                except (OSError, subprocess.SubprocessError):
                    actual_revision = None
                revision_match = actual_revision == expected_revision
                for source_file in sorted(checkout.rglob("*.py")):
                    try:
                        signature_text += source_file.read_text(encoding="utf-8") + "\n"
                        signature_files.append(str(source_file.relative_to(checkout)))
                    except (OSError, UnicodeDecodeError):
                        continue
            expected_classes = set(entry.get("classes", []))
            class_matches = {name: (name in signature_text) for name in expected_classes}
            signature_match = bool(expected_classes) and all(class_matches.values())
            checks.append({"name": entry.get("name"), "revision": expected_revision, "actual_revision": actual_revision, "revision_match": revision_match, "path": str(checkout), "present": present, "signature_files": signature_files, "expected_classes": sorted(expected_classes), "class_matches": class_matches, "signature_match": signature_match, "status": "PASS" if present and revision_match and (signature_match if expected_classes else True) else "BLOCKED"})
    status = "PASS" if checks and all(item.get("status") == "PASS" for item in checks) else "BLOCKED"
    return {"status": status, "lock_path": str(lock_path), "checks": checks}


def collect_preflight(root: str | Path | None = None, *, profile: str | None = None) -> dict[str, Any]:
    root_path = project_root(root)
    if profile is not None and profile not in PROFILE_LIMITS:
        raise ValueError(f"unknown execution profile: {profile}")
    live_chaos = Path("/Users/klimpaskov/Documents/Paradox Interactive/Hearts of Iron IV/mod/Chaos-Redux")
    generic_candidates = [
        Path("/Users/klimpaskov/Documents/Projects/agentic-hoi4-modding"),
        Path("/Users/klimpaskov/Documents/Projects/agentic-hoi4"),
        root_path / "integrations" / "agentic-hoi4-modding",
    ]
    style_path = root_path / STYLE_LORA_PATH
    background_registry = root_path / "config" / "background_registry.json"
    registry = json.loads(background_registry.read_text(encoding="utf-8")) if background_registry.is_file() else {}
    background_evidence = _background_preflight(root_path, background_registry, registry)
    background_resolved = background_evidence["status"] == "PASS"
    model_root = root_path / "models"
    comfy_path = shutil.which("comfy") or shutil.which("comfy-cli")
    try:
        import torch  # type: ignore

        torch_probe: dict[str, Any] = {
            "installed": True,
            "version": getattr(torch, "__version__", None),
            "mps_available": bool(getattr(getattr(torch, "backends", None), "mps", None) and torch.backends.mps.is_available()),
            "cuda_available": bool(getattr(torch, "cuda", None) and torch.cuda.is_available()),
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
    torch_cuda = bool(torch_probe.get("cuda_available", False))
    gates.append({
        "name": "hardware_detection",
        "status": "PASS" if hardware["memory"].get("memsize_bytes") == "17179869184" and platform.system() == "Darwin" else "UNVERIFIED",
        "evidence": {**hardware, "available_tools": {name: _tool_version(name, "--version") for name in ("uv", "brew", "docker")}},
    })
    python_floor_ok = sys.version_info >= (3, 10)
    local_profile = profile in {"human_local_mac_16gb", "agent_local_mac_16gb"} if profile else True
    full_gpu_profile = profile == "human_full_power_gpu"
    comfy_runtime_present = bool(comfy_path) or (root_path / "comfyui" / "main.py").is_file()
    required_accelerator = "MPS" if local_profile else ("CUDA" if full_gpu_profile else "not_local")
    accelerator_ok = bool(torch_probe.get("mps_available")) if local_profile else (bool(torch_cuda) if full_gpu_profile else True)
    gates.append({
        "name": "local_runtime_capability",
        "status": "PASS" if (not local_profile and not full_gpu_profile) or (python_floor_ok and torch_probe.get("installed") and accelerator_ok and comfy_runtime_present) else "BLOCKED",
        "evidence": {"profile": profile, "python_version": platform.python_version(), "python_floor": ">=3.10", "python_floor_ok": python_floor_ok, "torch": torch_probe, "comfy_cli": comfy_path, "comfy_runtime_present": comfy_runtime_present, "required_accelerator": required_accelerator, "accelerator_ok": accelerator_ok},
    })
    if gates[-1]["status"] == "BLOCKED" and (profile is None or local_profile or full_gpu_profile):
        blockers.append(f"The required {required_accelerator} runtime, Python floor, PyTorch capability, or ComfyUI installation is not verified; this profile cannot be claimed executable.")

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
        "evidence": background_evidence,
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
    model_evidence = _model_artifact_preflight(root_path, model_root, model_entries, profile)
    model_status = model_evidence["status"]
    gates.append({"name": "model_artifact_preflight", "status": model_status, "evidence": {**model_evidence, "local_files": local_model_files, "locked_models": len(model_entries)}})
    if model_status != "PASS":
        blockers.append("Required Krea/Qwen model artifacts are not installed and live ComfyUI compatibility has not been verified.")

    custom_node_evidence = _custom_node_preflight(root_path)
    gates.append({"name": "custom_node_preflight", "status": custom_node_evidence["status"], "evidence": custom_node_evidence})
    if custom_node_evidence["status"] != "PASS":
        blockers.append("One or more required custom-node checkouts or class inventories are missing; workflow execution is blocked.")

    runtime_lock_path = root_path / "dependencies" / "runtime_requirements_lock.json"
    runtime_lock = json.loads(runtime_lock_path.read_text(encoding="utf-8")) if runtime_lock_path.is_file() else {}
    runtime_unresolved = [item.get("name") for item in runtime_lock.get("requirements", []) if item.get("mandatory") and (item.get("sha256") is None or str(item.get("version", "")).startswith("UNRESOLVED"))]
    runtime_lock_status = "PASS" if runtime_lock.get("status") == "RESOLVED" and not runtime_unresolved else "BLOCKED"
    gates.append({"name": "comfyui_runtime_dependency_lock", "status": runtime_lock_status, "evidence": {"path": str(runtime_lock_path), "unresolved": runtime_unresolved}})
    if runtime_lock_status != "PASS":
        blockers.append("The pinned ComfyUI runtime dependency lock still contains unresolved platform versions or artifact checksums.")

    env_presence = _env_presence()
    remote_required = profile in {None, "agent_remote_runpod"}
    remote_status = "PASS" if env_presence["RUNPOD_API_KEY"] and env_presence["RUNPOD_ENDPOINT_ID"] else ("BLOCKED" if remote_required else "NOT_APPLICABLE")
    gates.append({"name": "remote_topology_auth", "status": remote_status, "evidence": {"profile": profile, "credential_presence": env_presence, "raw_comfyui_binding": "not configured", "remote_gateway": "authenticated_only"}})
    if remote_status == "BLOCKED":
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

    krea_review_path = root_path / "docs" / "preflight" / "krea_compatibility_review.json"
    try:
        krea_review = json.loads(krea_review_path.read_text(encoding="utf-8")) if krea_review_path.is_file() else {"status": "MISSING"}
    except json.JSONDecodeError:
        krea_review = {"status": "INVALID_JSON"}
    gates.append({"name": "krea_live_compatibility", "status": "BLOCKED", "evidence": {"reason": "Krea live compatibility, node import, model loading, graph loading, and an eight-step Turbo execution are unverified.", "compatibility_review_path": str(krea_review_path), "compatibility_review_status": krea_review.get("status"), "compatibility_review": krea_review}})
    blockers.append("Krea 2 Turbo compatibility, identity-edit behavior, and the immutable style LoRA matrix have not been measured in the pinned runtime.")

    preprocessing_lock_path = root_path / "dependencies" / "preprocessing_lock.json"
    preprocessing_lock = json.loads(preprocessing_lock_path.read_text(encoding="utf-8")) if preprocessing_lock_path.is_file() else {}
    preprocessing_missing = [entry.get("name") for entry in preprocessing_lock.get("dependencies", []) if entry.get("mandatory") and not entry.get("artifact_sha256")]
    preprocessing_status = "PASS" if not preprocessing_missing else "BLOCKED"
    gates.append({"name": "preprocessing_and_audit_dependencies", "status": preprocessing_status, "evidence": {"path": str(preprocessing_lock_path), "missing_checksums": preprocessing_missing}})
    if preprocessing_status != "PASS":
        blockers.append("Pinned preprocessing/audit model artifacts have no verified checksums; masking, face analysis, and independent audit cannot run.")

    license_review = json.loads((root_path / "dependencies" / "license_review.json").read_text(encoding="utf-8"))
    license_status = license_review.get("status", "BLOCKED")
    gates.append({"name": "license_and_rights_review", "status": license_status, "evidence": license_review})
    if license_status not in {"PASS", "APPROVED", "RESOLVED"}:
        blockers.append("License/rights review is not fully approved for Krea redistribution or the unresolved background.")

    return {
        "schema_version": "1.0.0",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(root_path),
        "profile": profile,
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
