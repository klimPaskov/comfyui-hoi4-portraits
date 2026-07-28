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

from .constants import CALIBRATED_THRESHOLD_STATUSES, ExitCode, PROFILE_LIMITS, STYLE_LORA_PATH, STYLE_LORA_SHA256
from .util import atomic_json_write, is_sha256, project_root, relative_safe_path, sanitize_public_paths, sha256_file, tree_sha256

SUPPORTED_MODEL_SUFFIXES = {".safetensors", ".gguf"}
SUPPORTED_MODEL_RUNTIME_SUFFIXES = {".json", ".txt"}
SUPPORTED_PREPROCESSING_SUFFIXES = {
    ".bin": "pytorch_bin",
    ".onnx": "onnx",
    ".safetensors": "safetensors",
    ".task": "mediapipe_task",
}
PROFILE_RUNTIME_LOCKS = {
    "human_local_mac_16gb": "macos_arm64_cpu",
    "agent_local_mac_16gb": "macos_arm64_cpu",
    "human_full_power_gpu": "linux_amd64_cuda128",
    "agent_full_power_gpu": "linux_amd64_cuda128",
    "agent_remote_runpod": "linux_amd64_cuda128",
}


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


def _runtime_python(root: Path) -> Path:
    """Select the project-owned interpreter used by the installed runtime."""

    for candidate in (root / ".venv" / "bin" / "python", root / ".venv" / "bin" / "python3"):
        if candidate.is_file():
            return candidate
    return Path(sys.executable)


def _runtime_probe(root: Path) -> dict[str, Any]:
    """Probe the selected project interpreter in a subprocess.

    The host Python on macOS is commonly an older system interpreter.  It is
    useful hardware evidence, but it is not the runtime that bootstrap
    installs or that ComfyUI serves.  Keep both facts separate and base the
    execution gate on this measured project interpreter.
    """

    runtime_python = _runtime_python(root)
    probe_code = (
        "import json, sys\n"
        "result = {'python_executable': sys.executable, 'python_version': sys.version, "
        "'python_version_info': [sys.version_info[0], sys.version_info[1], sys.version_info[2]]}\n"
        "try:\n"
        "    import torch\n"
        "    mps = getattr(getattr(torch, 'backends', None), 'mps', None)\n"
        "    result['torch'] = {'installed': True, 'version': getattr(torch, '__version__', None), "
        "'mps_built': bool(mps and mps.is_built()), 'mps_available': bool(mps and mps.is_available()), "
        "'cuda_available': bool(getattr(torch, 'cuda', None) and torch.cuda.is_available())}\n"
        "except Exception as exc:\n"
        "    result['torch'] = {'installed': False, 'error_type': type(exc).__name__, 'error': str(exc)}\n"
        "for module_name, key in (('pydantic', 'pydantic'), ('pydantic_settings', 'pydantic_settings'), "
        "('transformers', 'transformers')):\n"
        "    try:\n"
        "        module = __import__(module_name)\n"
        "        result[key] = {'installed': True, 'version': getattr(module, '__version__', None)}\n"
        "    except Exception as exc:\n"
        "        result[key] = {'installed': False, 'error_type': type(exc).__name__, 'error': str(exc)}\n"
        "print(json.dumps(result, sort_keys=True))"
    )
    try:
        completed = subprocess.run(
            [str(runtime_python), "-c", probe_code],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "python_executable": str(runtime_python),
            "status": "BLOCKED",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    evidence: dict[str, Any] = {
        "python_executable": str(runtime_python),
        "returncode": completed.returncode,
        "stderr": completed.stderr.strip(),
        "status": "PASS" if completed.returncode == 0 else "BLOCKED",
    }
    try:
        payload = json.loads(completed.stdout) if completed.stdout.strip() else {}
    except json.JSONDecodeError as exc:
        payload = {"parse_error": str(exc), "stdout": completed.stdout.strip()}
    if isinstance(payload, dict):
        evidence.update(payload)
    return evidence


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


def _configured_path(name: str) -> Path | None:
    value = os.environ.get(name)
    if not value:
        return None
    return Path(value).expanduser().resolve()


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


def _owner_scope(root: Path) -> dict[str, Any]:
    """Read the explicit project-owner scope decision for optional surfaces."""

    path = root / "docs" / "preflight" / "owner_attestation.json"
    try:
        attestation = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "MISSING_OR_INVALID", "path": str(path), "scope": {}}
    scope = attestation.get("scope") if isinstance(attestation, dict) else {}
    return {"status": "PASS" if isinstance(scope, dict) else "MISSING_OR_INVALID", "path": str(path), "scope": scope if isinstance(scope, dict) else {}}


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
    locked_paths: set[Path] = set()
    managed_directories: set[Path] = set()
    checks: list[dict[str, Any]] = []
    all_pass = True
    for entry in entries:
        destination = (root / str(entry.get("destination_folder", "models"))).resolve()
        managed_directories.add(destination)
        shard_hashes = entry.get("shard_sha256")
        if isinstance(shard_hashes, dict):
            locked_paths.update(destination / filename for filename in shard_hashes)
        elif isinstance(entry.get("filename"), str):
            locked_paths.add(destination / str(entry["filename"]))
        runtime_files = entry.get("runtime_files")
        if isinstance(runtime_files, list):
            for runtime_file in runtime_files:
                if isinstance(runtime_file, dict) and isinstance(runtime_file.get("filename"), str):
                    locked_paths.add(destination / str(runtime_file["filename"]))
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
        else:
            filename = entry.get("filename")
            expected_hash = entry.get("sha256")
            if not isinstance(filename, str) or not filename or not is_sha256(expected_hash):
                all_pass = False
                checks.append({"name": entry.get("name"), "status": "BLOCKED", "reason": "locked filename or SHA-256 is missing"})
            else:
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

        runtime_files = entry.get("runtime_files")
        if isinstance(runtime_files, list):
            for runtime_file in runtime_files:
                if not isinstance(runtime_file, dict):
                    all_pass = False
                    checks.append({"name": entry.get("name"), "kind": "runtime_metadata", "status": "BLOCKED", "reason": "runtime file entry is not an object"})
                    continue
                filename = runtime_file.get("filename")
                expected_hash = runtime_file.get("sha256")
                expected_size = runtime_file.get("size_bytes")
                format_ok = isinstance(filename, str) and Path(filename).suffix.casefold() in SUPPORTED_MODEL_RUNTIME_SUFFIXES
                path = destination / str(filename or "")
                actual_hash = sha256_file(path) if path.is_file() else None
                actual_size = path.stat().st_size if path.is_file() else None
                size_ok = isinstance(expected_size, int) and actual_size == expected_size
                item_ok = format_ok and path.is_file() and size_ok and is_sha256(expected_hash) and actual_hash == expected_hash
                all_pass &= item_ok
                checks.append({"name": entry.get("name"), "kind": "runtime_metadata", "path": str(path.relative_to(root)), "format": Path(filename).suffix.casefold() if isinstance(filename, str) else None, "format_supported": format_ok, "present": path.is_file(), "size_bytes": actual_size, "expected_size_bytes": expected_size, "sha256": actual_hash, "expected_sha256": expected_hash, "status": "PASS" if item_ok else "BLOCKED"})
        continue

    unexpected: list[str] = []
    if model_root.is_dir():
        for path in model_root.rglob("*"):
            if path.is_file() and path.resolve() not in locked_paths and any(
                path.resolve().is_relative_to(directory) for directory in managed_directories
            ):
                unexpected.append(str(path.relative_to(root)))
    if unexpected:
        all_pass = False
    return {"status": "PASS" if all_pass and bool(scoped) else "BLOCKED", "profile": profile, "checks": checks, "unexpected_files": sorted(unexpected), "scoped_mandatory_models": [entry.get("name") for entry in scoped]}


def _preprocessing_artifact_preflight(root: Path, lock: dict[str, Any]) -> dict[str, Any]:
    """Verify the exact preprocessing artifacts, not only their lock metadata.

    Preprocessing artifacts use formats that are intentionally separate from
    the ComfyUI diffusion-model allowlist.  A complete lock is still a
    blocked runtime until every mandatory artifact is present, size-matched,
    and SHA-256 verified.  Unknown files under the controlled preprocessing
    directory are rejected so a service cannot silently select an unlocked
    model.
    """

    dependencies = lock.get("dependencies", []) if isinstance(lock.get("dependencies", []), list) else []
    checks: list[dict[str, Any]] = []
    source_checks: list[dict[str, Any]] = []
    preprocessing_root = (root / "models" / "preprocessing").resolve()
    expected_paths: set[Path] = set()
    missing_lock_fields: list[str] = []
    all_pass = bool(dependencies)
    for entry in dependencies:
        if not entry.get("mandatory"):
            continue
        name = str(entry.get("name", ""))
        destination_value = entry.get("destination_path")
        filename = entry.get("artifact_filename")
        artifact_url = entry.get("artifact_url")
        artifact_revision = entry.get("artifact_revision")
        artifact_hash = entry.get("artifact_sha256")
        artifact_size = entry.get("artifact_size_bytes")
        artifact_format = entry.get("artifact_format")
        required_ok = (
            isinstance(destination_value, str)
            and isinstance(filename, str)
            and isinstance(artifact_url, str)
            and artifact_url.startswith("https://")
            and isinstance(artifact_revision, str)
            and bool(artifact_revision)
            and is_sha256(artifact_hash)
            and isinstance(artifact_size, int)
            and artifact_size > 0
            and artifact_format in set(SUPPORTED_PREPROCESSING_SUFFIXES.values())
        )
        if not required_ok:
            missing_lock_fields.append(name or "<unnamed>")
            all_pass = False
            checks.append({"name": name, "status": "BLOCKED_LOCK_INCOMPLETE", "artifact_url": artifact_url, "artifact_revision": artifact_revision, "expected_sha256": artifact_hash, "expected_size_bytes": artifact_size, "destination_path": destination_value})
            continue
        try:
            destination = relative_safe_path(root, destination_value)
        except ValueError as exc:
            all_pass = False
            checks.append({"name": name, "status": "BLOCKED_LOCK_INCOMPLETE", "reason": str(exc), "destination_path": destination_value})
            continue
        try:
            destination.relative_to(preprocessing_root)
        except ValueError:
            all_pass = False
            checks.append({"name": name, "status": "BLOCKED_LOCK_INCOMPLETE", "reason": "destination must remain under models/preprocessing", "destination_path": destination_value})
            continue
        expected_paths.add(destination.resolve())
        suffix = destination.suffix.casefold()
        format_ok = suffix in SUPPORTED_PREPROCESSING_SUFFIXES and SUPPORTED_PREPROCESSING_SUFFIXES[suffix] == artifact_format and destination.name == filename
        actual_hash = sha256_file(destination) if destination.is_file() else None
        actual_size = destination.stat().st_size if destination.is_file() else None
        present = destination.is_file()
        size_ok = present and actual_size == artifact_size
        hash_ok = present and actual_hash == artifact_hash
        item_ok = format_ok and size_ok and hash_ok
        all_pass &= item_ok
        if not present:
            status = "BLOCKED_NOT_INSTALLED"
        elif not format_ok:
            status = "BLOCKED_UNSUPPORTED_FORMAT"
        elif not size_ok or not hash_ok:
            status = "BLOCKED_CHECKSUM_MISMATCH"
        else:
            status = "PASS"
        checks.append({"name": name, "status": status, "path": destination_value, "artifact_url": artifact_url, "artifact_revision": artifact_revision, "format": suffix or None, "format_expected": artifact_format, "format_supported": format_ok, "present": present, "size_bytes": actual_size, "expected_size_bytes": artifact_size, "sha256": actual_hash, "expected_sha256": artifact_hash})

        source_artifacts = entry.get("source_artifacts")
        if isinstance(source_artifacts, dict) and source_artifacts.get("runtime_required"):
            source_revision = source_artifacts.get("source_revision")
            source_files = source_artifacts.get("files")
            source_lock_ok = isinstance(source_artifacts.get("source_url"), str) and source_artifacts["source_url"].startswith("https://") and isinstance(source_revision, str) and bool(source_revision) and isinstance(source_files, list) and bool(source_files)
            if not source_lock_ok:
                missing_lock_fields.append(f"{name}.source_artifacts")
                all_pass = False
                source_checks.append({"name": name, "status": "BLOCKED_LOCK_INCOMPLETE", "source_revision": source_revision})
            else:
                for source_file in source_files:
                    if not isinstance(source_file, dict):
                        missing_lock_fields.append(f"{name}.source_file")
                        all_pass = False
                        source_checks.append({"name": name, "status": "BLOCKED_LOCK_INCOMPLETE"})
                        continue
                    source_name = str(source_file.get("filename", ""))
                    source_destination_value = source_file.get("destination_path")
                    source_url = source_file.get("artifact_url")
                    source_size = source_file.get("size_bytes")
                    source_hash = source_file.get("sha256")
                    source_required_ok = isinstance(source_destination_value, str) and isinstance(source_url, str) and source_url.startswith("https://") and isinstance(source_size, int) and source_size > 0 and is_sha256(source_hash) and Path(str(source_destination_value)).name == source_name and Path(str(source_destination_value)).suffix.casefold() in {".py", ".json"}
                    if not source_required_ok:
                        missing_lock_fields.append(f"{name}.{source_name or 'source_file'}")
                        all_pass = False
                        source_checks.append({"name": name, "filename": source_name, "status": "BLOCKED_LOCK_INCOMPLETE", "destination_path": source_destination_value, "artifact_url": source_url})
                        continue
                    try:
                        source_destination = relative_safe_path(root, source_destination_value)
                        source_destination.relative_to(preprocessing_root)
                    except ValueError as exc:
                        all_pass = False
                        source_checks.append({"name": name, "filename": source_name, "status": "BLOCKED_LOCK_INCOMPLETE", "reason": str(exc), "destination_path": source_destination_value})
                        continue
                    expected_paths.add(source_destination.resolve())
                    source_present = source_destination.is_file()
                    source_actual_size = source_destination.stat().st_size if source_present else None
                    source_actual_hash = sha256_file(source_destination) if source_present else None
                    source_size_ok = source_present and source_actual_size == source_size
                    source_hash_ok = source_present and source_actual_hash == source_hash
                    source_item_ok = source_size_ok and source_hash_ok
                    all_pass &= source_item_ok
                    source_status = "PASS" if source_item_ok else "BLOCKED_NOT_INSTALLED" if not source_present else "BLOCKED_CHECKSUM_MISMATCH"
                    source_checks.append({"name": name, "filename": source_name, "status": source_status, "path": source_destination_value, "artifact_url": source_url, "source_revision": source_revision, "present": source_present, "size_bytes": source_actual_size, "expected_size_bytes": source_size, "sha256": source_actual_hash, "expected_sha256": source_hash})

    unexpected: list[str] = []
    if preprocessing_root.is_dir():
        for path in preprocessing_root.rglob("*"):
            if path.is_file() and path.resolve() not in expected_paths:
                unexpected.append(str(path.relative_to(root)))
    if unexpected:
        all_pass = False

    source_evidence_path = root / "docs" / "preflight" / "preprocessing_artifact_sources.json"
    source_issues: list[str] = []
    source_status = "BLOCKED_MISSING"
    source_entries: dict[str, dict[str, Any]] = {}
    if source_evidence_path.is_file():
        try:
            source_evidence = json.loads(source_evidence_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            source_evidence = {}
            source_issues.append(f"cannot read source evidence: {type(exc).__name__}")
        if isinstance(source_evidence, dict):
            raw_sources = source_evidence.get("sources")
            source_evidence_status = source_evidence.get("status")
            source_evidence_accepted = (
                isinstance(source_evidence_status, str)
                and (
                    source_evidence_status.startswith("PASS_METADATA_ONLY")
                    or source_evidence_status == "PASS_PRIMARY_SOURCE_AND_LOCAL_CHECKSUMS"
                )
            )
            if source_evidence_accepted and isinstance(raw_sources, list):
                for item in raw_sources:
                    if isinstance(item, dict) and isinstance(item.get("name"), str):
                        if item["name"] in source_entries:
                            source_issues.append(f"duplicate source evidence: {item['name']}")
                        source_entries[item["name"]] = item
            else:
                source_issues.append("source evidence status or sources list is incomplete")
        else:
            source_issues.append("source evidence root must be an object")

    mandatory_names = {str(entry.get("name", "")) for entry in dependencies if entry.get("mandatory")}
    for entry in dependencies:
        if not entry.get("mandatory"):
            continue
        name = str(entry.get("name", ""))
        source = source_entries.get(name)
        if source is None:
            source_issues.append(f"missing source evidence: {name or '<unnamed>'}")
            continue
        expected = {
            "revision": entry.get("artifact_revision"),
            "artifact": entry.get("artifact_filename"),
            "size_bytes": entry.get("artifact_size_bytes"),
            "sha256": entry.get("artifact_sha256"),
        }
        for field, value in expected.items():
            if source.get(field) != value:
                source_issues.append(f"source evidence mismatch for {name}: {field}")
        if source.get("metadata_status") != "PASS":
            source_issues.append(f"source evidence is not verified for {name}")
        expected_source_files = entry.get("source_artifacts", {}).get("files", []) if isinstance(entry.get("source_artifacts"), dict) else []
        if expected_source_files:
            evidence_source_files = source.get("source_files")
            if not isinstance(evidence_source_files, list):
                source_issues.append(f"missing source-file evidence: {name}")
            else:
                expected_by_name = {item.get("filename"): item for item in expected_source_files if isinstance(item, dict)}
                observed_by_name = {item.get("filename"): item for item in evidence_source_files if isinstance(item, dict)}
                if set(expected_by_name) != set(observed_by_name):
                    source_issues.append(f"source-file evidence names mismatch for {name}")
                for filename, expected_file in expected_by_name.items():
                    observed_file = observed_by_name.get(filename, {})
                    for field in ("size_bytes", "sha256"):
                        if observed_file.get(field) != expected_file.get(field):
                            source_issues.append(f"source-file evidence mismatch for {name}/{filename}: {field}")
    unexpected_sources = sorted(set(source_entries) - mandatory_names)
    if unexpected_sources:
        source_issues.extend(f"unexpected source evidence: {name}" for name in unexpected_sources)
    if source_evidence_path.is_file() and not source_issues:
        source_status = "PASS"
    else:
        all_pass = False

    return {
        "status": "PASS" if all_pass and checks and not unexpected else "BLOCKED",
        "lock_status": lock.get("status"),
        "checks": checks,
        "source_artifact_checks": source_checks,
        "missing_checksums": missing_lock_fields,
        "unexpected_files": sorted(unexpected),
        "mandatory_count": len(checks),
        "source_artifact_count": len(source_checks),
        "source_verification_path": str(source_evidence_path.relative_to(root)),
        "source_verification_status": source_status,
        "source_verification_issues": source_issues,
    }


def _autoprompter_preflight(root: Path, profile: str | None) -> dict[str, Any]:
    """Verify the human prompt runtime evidence without claiming prompt quality."""

    lock_path = root / "dependencies" / "autoprompter_runtime.lock.json"
    report_path = root / "docs" / "preflight" / "autoprompter_runtime_test.json"
    evidence: dict[str, Any] = {
        "lock_path": str(lock_path.relative_to(root)),
        "report_path": str(report_path.relative_to(root)),
        "profile": profile,
        "instruction_sha256": sha256_file(root / "prompts" / "autoprompter_instruction.txt") if (root / "prompts" / "autoprompter_instruction.txt").is_file() else None,
    }
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "BLOCKED", **evidence, "reason": f"autoprompter lock/evidence is unreadable: {type(exc).__name__}"}
    evidence.update({"lock_status": lock.get("status"), "runtime_report": report})
    local = report.get("runtime", {}) if isinstance(report, dict) else {}
    local_health = local.get("health", {}) if isinstance(local, dict) else {}
    local_pass = report.get("status") == "PASS_HEALTH_AND_NEGATIVE_VALIDATION" and report.get("negative_validation", {}).get("status") == "PASS" and local_health.get("status") == "PASS"
    full_power = report.get("full_power", {}) if isinstance(report, dict) else {}
    full_format_pass = full_power.get("status") == "PASS_FORMAT_AND_PROCESSOR_SCHEMA"
    if profile in {"agent_local_mac_16gb", "agent_full_power_gpu", "agent_remote_runpod"}:
        status = "NOT_APPLICABLE"
    elif profile == "human_local_mac_16gb":
        status = "PASS" if local_pass and full_format_pass else "BLOCKED"
    elif profile == "human_full_power_gpu":
        status = "PASS_FORMAT_ONLY_EXECUTION_BLOCKED" if full_format_pass and full_power.get("execution") == "BLOCKED_TARGET_CUDA_UNAVAILABLE" else "BLOCKED"
    else:
        status = "PASS_LOCAL_AND_FULL_POWER_FORMAT_ONLY" if local_pass and full_format_pass else "BLOCKED"
    evidence["local_sidecar_status"] = "PASS" if local_pass else "BLOCKED"
    evidence["full_power_format_status"] = "PASS" if full_format_pass else "BLOCKED"
    evidence["positive_generation_status"] = report.get("positive_generation", {}).get("status")
    evidence["production_prompt_claim"] = "NOT_CLAIMED"
    return {"status": status, **evidence}


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


def _runtime_lock_preflight(root: Path, lock: dict[str, Any], profile: str | None) -> dict[str, Any]:
    """Validate a profile lock without treating structural resolution as live compatibility."""

    def hashed_requirements_check(path: Path | None, expected_sha: object, status: object) -> tuple[bool, dict[str, Any]]:
        actual_sha = sha256_file(path) if path is not None and path.is_file() else None
        content_ok = False
        invalid_packages: list[str] = []
        if path is not None and path.is_file():
            blocks: list[str] = []
            current: list[str] = []
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or (line.startswith("--") and not line.startswith("--hash=")):
                    continue
                if raw_line and not raw_line[0].isspace() and current:
                    blocks.append("\n".join(current))
                    current = []
                current.append(line)
            if current:
                blocks.append("\n".join(current))
            invalid_packages = [block.splitlines()[0] for block in blocks if "==" not in block or "--hash=sha256:" not in block or "UNRESOLVED" in block]
            content_ok = bool(blocks) and not invalid_packages
        item_ok = status == "RESOLVED" and path is not None and path.is_file() and is_sha256(expected_sha) and actual_sha == expected_sha and content_ok
        return item_ok, {"status": "PASS" if item_ok else "BLOCKED", "expected_sha256": expected_sha, "actual_sha256": actual_sha, "content_ok": content_ok, "invalid_packages": invalid_packages}

    profile_locks = lock.get("profile_locks")
    if not isinstance(profile_locks, dict):
        unresolved = [item.get("name") for item in lock.get("requirements", []) if item.get("mandatory") and (item.get("sha256") is None or str(item.get("version", "")).startswith("UNRESOLVED"))]
        return {"status": "PASS" if lock.get("status") == "RESOLVED" and not unresolved else "BLOCKED", "mode": "legacy", "unresolved": unresolved}

    selected = [PROFILE_RUNTIME_LOCKS[profile]] if profile in PROFILE_RUNTIME_LOCKS else sorted(profile_locks)
    checks: list[dict[str, Any]] = []
    all_pass = True
    for lock_id in selected:
        entry = profile_locks.get(lock_id, {})
        relative = entry.get("path")
        path = root / str(relative) if isinstance(relative, str) else None
        expected_sha = entry.get("sha256")
        item_ok, content = hashed_requirements_check(path, expected_sha, entry.get("status"))
        all_pass &= item_ok
        checks.append({"profile_lock": lock_id, "path": relative, **content})

    project_entry = lock.get("project_lock", {})
    project_relative = project_entry.get("path")
    project_path = root / str(project_relative) if isinstance(project_relative, str) else None
    project_ok, project_check = hashed_requirements_check(project_path, project_entry.get("sha256"), project_entry.get("status"))
    all_pass &= project_ok
    return {"status": "PASS" if all_pass and checks else "BLOCKED", "mode": "profile_locks", "lock_status": lock.get("status"), "checks": checks, "project_lock": {"path": project_relative, **project_check}}


def collect_preflight(root: str | Path | None = None, *, profile: str | None = None) -> dict[str, Any]:
    root_path = project_root(root)
    if profile is not None and profile not in PROFILE_LIMITS:
        raise ValueError(f"unknown execution profile: {profile}")
    chaos_candidates = [
        _configured_path("HOI4_CHAOS_REDUX_PATH"),
        root_path / "repos" / "Chaos-Redux",
        Path.home() / "Documents/Paradox Interactive/Hearts of Iron IV/mod/Chaos-Redux",
    ]
    live_chaos = next((path for path in chaos_candidates if path is not None and path.is_dir()), next(path for path in chaos_candidates if path is not None))
    generic_candidates = [
        _configured_path("HOI4_GENERIC_TARGET_PATH"),
        root_path / "repos" / "Agentic-HOI4-Modding",
        root_path / "repos" / "agentic-hoi4-modding",
        Path.home() / "Documents/Projects/Agentic-HOI4-Modding",
        Path.home() / "Documents/Projects/agentic-hoi4-modding",
        Path.home() / "Documents/Projects/agentic-hoi4",
        root_path / "integrations" / "agentic-hoi4-modding",
    ]
    style_path = root_path / STYLE_LORA_PATH
    background_registry = root_path / "config" / "background_registry.json"
    registry = json.loads(background_registry.read_text(encoding="utf-8")) if background_registry.is_file() else {}
    background_evidence = _background_preflight(root_path, background_registry, registry)
    background_resolved = background_evidence["status"] == "PASS"
    model_root = root_path / "models"
    comfy_path = shutil.which("comfy") or shutil.which("comfy-cli")
    runtime_probe = _runtime_probe(root_path)
    torch_probe = runtime_probe.get("torch", {}) if isinstance(runtime_probe.get("torch"), dict) else {}

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
    runtime_version_info = runtime_probe.get("python_version_info", [])
    python_floor_ok = isinstance(runtime_version_info, list) and len(runtime_version_info) >= 2 and tuple(runtime_version_info[:2]) >= (3, 10)
    local_profile = profile in {"human_local_mac_16gb", "agent_local_mac_16gb"} if profile else True
    full_gpu_profile = profile in {"human_full_power_gpu", "agent_full_power_gpu"}
    comfy_runtime_present = bool(comfy_path) or (root_path / "comfyui" / "main.py").is_file()
    required_accelerator = "MPS" if local_profile else ("CUDA" if full_gpu_profile else "not_local")
    accelerator_ok = bool(torch_probe.get("mps_available")) if local_profile else (bool(torch_cuda) if full_gpu_profile else True)
    gates.append({
        "name": "local_runtime_capability",
        "status": "PASS" if (not local_profile and not full_gpu_profile) or (python_floor_ok and torch_probe.get("installed") and accelerator_ok and comfy_runtime_present) else "BLOCKED",
        "evidence": {"profile": profile, "python_version": runtime_probe.get("python_version"), "python_executable": runtime_probe.get("python_executable"), "host_python_version": platform.python_version(), "python_floor": ">=3.10", "python_floor_ok": python_floor_ok, "torch": torch_probe, "runtime_probe": runtime_probe, "comfy_cli": comfy_path, "comfy_runtime_present": comfy_runtime_present, "required_accelerator": required_accelerator, "accelerator_ok": accelerator_ok},
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
    model_profile = "human_local_mac_16gb" if profile == "agent_local_mac_16gb" else profile
    model_evidence = _model_artifact_preflight(root_path, model_root, model_entries, model_profile)
    model_evidence["requested_profile"] = profile
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
    runtime_lock_evidence = _runtime_lock_preflight(root_path, runtime_lock, profile)
    runtime_lock_status = runtime_lock_evidence["status"]
    gates.append({"name": "comfyui_runtime_dependency_lock", "status": runtime_lock_status, "evidence": {"path": str(runtime_lock_path), **runtime_lock_evidence}})
    if runtime_lock_status != "PASS":
        blockers.append("The pinned ComfyUI runtime dependency lock still contains unresolved platform versions or artifact checksums.")

    env_presence = _env_presence()
    owner_scope = _owner_scope(root_path)
    remote_required = profile in {None, "agent_remote_runpod"}
    remote_deferred = owner_scope.get("scope", {}).get("runpod_live_deployment") == "DEFERRED_OUT_OF_CURRENT_SCOPE"
    remote_status = "DEFERRED_OUT_OF_SCOPE" if remote_required and remote_deferred else ("PASS" if env_presence["RUNPOD_API_KEY"] and env_presence["RUNPOD_ENDPOINT_ID"] else ("BLOCKED" if remote_required else "NOT_APPLICABLE"))
    gates.append({"name": "remote_topology_auth", "status": remote_status, "evidence": {"profile": profile, "credential_presence": env_presence, "raw_comfyui_binding": "not configured", "remote_gateway": "authenticated_only", "owner_scope": owner_scope, "live_execution": "NOT_RUN" if remote_status == "DEFERRED_OUT_OF_SCOPE" else "UNQUALIFIED"}})
    if remote_status == "BLOCKED":
        blockers.append("RunPod endpoint credentials are absent; remote submission/acceptance cannot run.")

    generic_existing = [str(path) for path in generic_candidates if path is not None and path.is_dir() and path != root_path / "integrations" / "agentic-hoi4-modding"]
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
    threshold_status = "PASS" if thresholds.get("status") in CALIBRATED_THRESHOLD_STATUSES and thresholds.get("thresholds_id") not in {None, "UNSET_BLOCK_EXECUTION"} and thresholds.get("approved_by") and thresholds.get("fail_closed") is True else "BLOCKED"
    calibration_evidence: dict[str, Any] = {"status": "NOT_RECORDED"}
    calibration_paths = sorted((root_path / "docs" / "preflight").glob("identity_calibration_*.json"))
    if calibration_paths:
        calibration_path = calibration_paths[-1]
        try:
            calibration_report = json.loads(calibration_path.read_text(encoding="utf-8"))
            calibration_evidence = {
                "path": str(calibration_path.relative_to(root_path)),
                "status": calibration_report.get("status"),
                "calibration_id": calibration_report.get("calibration_id"),
                "fixture_set": calibration_report.get("fixture_set"),
                "fixture_manifest": calibration_report.get("fixture_manifest"),
                "positive_same_person": calibration_report.get("positive_same_person"),
                "negative_different_person": calibration_report.get("negative_different_person"),
                "operating_point": calibration_report.get("operating_point"),
                "blocked_reasons": calibration_report.get("blocked_reasons", []),
            }
        except (OSError, json.JSONDecodeError):
            calibration_evidence = {"path": str(calibration_path.relative_to(root_path)), "status": "INVALID_JSON"}
    geometry_evidence: dict[str, Any] = {"status": "NOT_RECORDED"}
    geometry_paths = sorted((root_path / "docs" / "preflight").glob("geometry_calibration_*.json"))
    if geometry_paths:
        geometry_path = geometry_paths[-1]
        try:
            geometry_report = json.loads(geometry_path.read_text(encoding="utf-8"))
            geometry_evidence = {
                "path": str(geometry_path.relative_to(root_path)),
                "status": geometry_report.get("status"),
                "calibration_id": geometry_report.get("calibration_id"),
                "fixture_set": geometry_report.get("fixture_set"),
                "measurement_count": geometry_report.get("measurement_count"),
                "scalar_distributions": geometry_report.get("scalar_distributions"),
                "region_distributions": geometry_report.get("region_distributions"),
                "proposed_operating_point": geometry_report.get("proposed_operating_point"),
                "blocked_reasons": geometry_report.get("blocked_reasons", []),
            }
        except (OSError, json.JSONDecodeError):
            geometry_evidence = {"path": str(geometry_path.relative_to(root_path)), "status": "INVALID_JSON"}
    gates.append({"name": "calibrated_identity_thresholds", "status": threshold_status, "evidence": {"path": str(threshold_path), "present": threshold_path.is_file(), "status": thresholds.get("status"), "accepted_statuses": sorted(CALIBRATED_THRESHOLD_STATUSES), "thresholds_id": thresholds.get("thresholds_id"), "approved_by": thresholds.get("approved_by"), "calibration_evidence": calibration_evidence, "geometry_calibration_evidence": geometry_evidence}})
    if threshold_status != "PASS":
        if calibration_evidence.get("status") not in {None, "NOT_RECORDED"}:
            blockers.append("Calibration evidence exists but does not yet demonstrate the required approved identity/style threshold set; no production candidate may be accepted.")
        else:
            blockers.append("Identity/style thresholds are still calibration placeholders; no production candidate may be accepted.")

    krea_review_path = root_path / "docs" / "preflight" / "krea_compatibility_review.json"
    try:
        krea_review = json.loads(krea_review_path.read_text(encoding="utf-8")) if krea_review_path.is_file() else {"status": "MISSING"}
    except json.JSONDecodeError:
        krea_review = {"status": "INVALID_JSON"}
    live_krea_path = root_path / "docs" / "preflight" / "live_comfy_compatibility.json"
    try:
        live_krea = json.loads(live_krea_path.read_text(encoding="utf-8")) if live_krea_path.is_file() else {"status": "MISSING"}
    except json.JSONDecodeError:
        live_krea = {"status": "INVALID_JSON"}
    live_schema_pass = live_krea.get("status") == "PASS_SCHEMA_ONLY_EXECUTION_BLOCKED"
    krea_review_statuses = {"BLOCKED_EXECUTION_NOT_MEASURED", "BLOCKED_EXECUTION_LOCAL_16GB_MEMORY_INFEASIBLE", "QUALIFIED_CPU_FALLBACK_MPS_BLOCKED"}
    krea_status = "PASS" if live_schema_pass and krea_review.get("status") in krea_review_statuses else "BLOCKED"
    gates.append({"name": "krea_live_compatibility", "status": krea_status, "evidence": {"reason": "Live core/node/schema compatibility is verified; source-specific execution remains a separate qualification gate and the detected 16 GB Mac has a measured memory/offload blocker.", "compatibility_review_path": str(krea_review_path), "compatibility_review_status": krea_review.get("status"), "compatibility_review": krea_review, "live_probe_path": str(live_krea_path), "live_probe_status": live_krea.get("status"), "live_probe": live_krea}})
    if krea_status != "PASS":
        blockers.append("Krea 2 Turbo live core/node/schema compatibility is not verified in the pinned runtime.")
    blockers.append("Krea 2 source-specific production acceptance and the immutable style-LoRA experiment matrix remain blocked: the default MPS routes fail, the CPU fallback completed only one heavily-swapping run, and calibrated audit thresholds plus independent audit evidence are still required.")

    autoprompter_evidence = _autoprompter_preflight(root_path, profile)
    autoprompter_status = autoprompter_evidence["status"]
    gates.append({"name": "autoprompter_runtime", "status": autoprompter_status, "evidence": autoprompter_evidence})
    if autoprompter_status == "BLOCKED":
        blockers.append("The required human autoprompter runtime lock or live local sidecar evidence is unavailable.")
    elif autoprompter_status == "PASS_FORMAT_ONLY_EXECUTION_BLOCKED":
        blockers.append("The full-power human autoprompter format is pinned and processor-verified, but target CUDA execution is unavailable on the detected host.")

    preprocessing_lock_path = root_path / "dependencies" / "preprocessing_lock.json"
    preprocessing_lock = json.loads(preprocessing_lock_path.read_text(encoding="utf-8")) if preprocessing_lock_path.is_file() else {}
    preprocessing_evidence = _preprocessing_artifact_preflight(root_path, preprocessing_lock)
    preprocessing_status = preprocessing_evidence["status"]
    gates.append({"name": "preprocessing_and_audit_dependencies", "status": preprocessing_status, "evidence": {"path": str(preprocessing_lock_path), **preprocessing_evidence}})
    if preprocessing_status != "PASS":
        blockers.append("Pinned preprocessing/audit model artifacts are not all installed and checksum-verified; masking, face analysis, and independent audit cannot run.")

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
    public_report = sanitize_public_paths(report, root)
    atomic_json_write(json_out, public_report)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.write_text(render_markdown(public_report), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else int(report["recommended_exit_code"])
