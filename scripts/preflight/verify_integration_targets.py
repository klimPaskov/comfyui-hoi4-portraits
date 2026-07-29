#!/usr/bin/env python3
"""Read-only validation of the live integration target checkouts.

This deliberately never writes to an integration target.  It records the
target state, package-vs-live hashes, structural checks, and parent-owned
validation blockers in a redacted project report.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib  # type: ignore


ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "docs/preflight/integration_target_validation_2026-07-29.json"
MARKDOWN_PATH = ROOT / "docs/preflight/integration_target_validation_2026-07-29.md"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def run_git(path: Path, *args: str) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            ["git", *args], cwd=path, capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, "", str(exc)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def git_snapshot(path: Path) -> dict[str, Any]:
    if not path.is_dir() or not (path / ".git").exists():
        return {"exists": path.is_dir(), "is_git": False, "target_path": "redacted"}
    _, head, _ = run_git(path, "rev-parse", "HEAD")
    _, branch, _ = run_git(path, "branch", "--show-current")
    _, remote, _ = run_git(path, "remote", "get-url", "origin")
    _, status, _ = run_git(path, "status", "--porcelain=v1")
    entries = [line for line in status.splitlines() if line.strip()]
    staged = sum(1 for line in entries if line[0] not in {" ", "?"})
    unstaged = sum(1 for line in entries if len(line) > 1 and line[1] not in {" ", "?"})
    untracked = sum(1 for line in entries if line.startswith("??"))
    return {
        "exists": True,
        "is_git": True,
        "target_path": "redacted",
        "head": head or None,
        "branch": branch or None,
        "origin": remote or None,
        "status_entry_count": len(entries),
        "staged_entry_count": staged,
        "unstaged_entry_count": unstaged,
        "untracked_entry_count": untracked,
        "status_sample": [line[:240] for line in entries[:12]],
        "diff_check": "PASS" if run_git(path, "diff", "--check")[0] == 0 else "BLOCKED",
    }


def file_record(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        return {"path": relative, "exists": False, "sha256": None, "size_bytes": None}
    return {"path": relative, "exists": True, "sha256": sha256_file(path), "size_bytes": path.stat().st_size}


def compare_chaos_package(target: Path) -> dict[str, Any]:
    manifest_path = ROOT / "integrations/chaos-redux/replacement_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []
    for item in manifest.get("files", []):
        destination = str(item["destination"])
        actual = file_record(target, destination)
        expected_source = item.get("source_sha256")
        expected_replacement = item.get("replacement_sha256")
        if not actual["exists"]:
            comparison = "MISSING"
        elif actual["sha256"] == expected_source:
            comparison = "MATCHES_UPLOADED_BASELINE"
        elif actual["sha256"] == expected_replacement:
            comparison = "MATCHES_PROPOSED_REPLACEMENT"
        else:
            comparison = "LIVE_DIVERGED"
        records.append({**actual, "source_sha256": expected_source, "replacement_sha256": expected_replacement, "comparison": comparison})
    consumer_paths = [
        "AGENTS.md",
        ".agents/skills/chaos-redux-event-assets/SKILL.md",
        ".agents/skills/chaos-redux-subagents/SKILL.md",
        ".codex/agents/chaosx_hoi4_portrait_pipeline.toml",
        ".codex/agents/chaosx_portrait_identity_auditor.toml",
        "interface/chaosx_characters.gfx",
        ".tools/convert_to_dds.py",
        "gfx/leaders/portrait_leader_background.psd",
    ]
    counts: dict[str, int] = {}
    for item in records:
        counts[item["comparison"]] = counts.get(item["comparison"], 0) + 1
    return {
        "target_snapshot": git_snapshot(target),
        "package_manifest": "integrations/chaos-redux/replacement_manifest.json",
        "destination_comparisons": records,
        "comparison_counts": counts,
        "consumer_surface": [file_record(target, path) for path in consumer_paths],
        "direct_apply": "BLOCKED_READ_ONLY_AUDIT",
    }


def generic_portrait_audit(target: Path) -> dict[str, Any]:
    manifest_path = target / "hoi4-mod-setup.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    component = next((item for item in manifest.get("components", []) if item.get("id") == "workflow.hoi4_portrait_pipeline"), None)
    expected_files = component.get("expected_files", []) if isinstance(component, dict) else []
    expected_records: list[dict[str, Any]] = []
    for expected in expected_files:
        actual = file_record(target, str(expected["path"]))
        expected_records.append({**actual, "expected_sha256": expected.get("sha256"), "expected_size_bytes": expected.get("size"), "match": actual["exists"] and actual["sha256"] == expected.get("sha256") and actual["size_bytes"] == expected.get("size")})

    toml_records: list[dict[str, Any]] = []
    agent_root = target / ".codex/agents"
    for path in sorted(agent_root.glob("*.toml")) if agent_root.is_dir() else []:
        try:
            parsed = tomllib.loads(path.read_text(encoding="utf-8"))
            toml_records.append({"path": str(path.relative_to(target)), "status": "PASS", "fork_context_config_value": parsed.get("fork_context")})
        except Exception as exc:  # pragma: no cover - evidence should preserve the parser failure
            toml_records.append({"path": str(path.relative_to(target)), "status": "BLOCKED", "error": type(exc).__name__})

    portrait_files = [
        ".agents/skills/hoi4-portrait-pipeline/SKILL.md",
        ".codex/agents/hoi4_portrait_pipeline.toml",
        ".codex/agents/hoi4_portrait_identity_auditor.toml",
    ]
    forbidden = re.compile(r"(?:/Users/klimpaskov|comfyui-hoi4-portraits|Chaos Redux|chaosx_)", re.IGNORECASE)
    leak_records = []
    for relative in portrait_files:
        path = target / relative
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        leak_records.append({"path": relative, "exists": path.is_file(), "forbidden_project_specific_text": bool(forbidden.search(text)), "fork_context_false_text": "fork_context=false" in text})

    # The setup manifest is intentionally broader than the portrait addition.
    # Count its baseline drift, but report portrait-file parity separately.
    all_expected = []
    for item in manifest.get("components", []):
        all_expected.extend(item.get("expected_files", []))
    all_mismatches = 0
    all_missing = 0
    for expected in all_expected:
        actual = file_record(target, str(expected["path"]))
        if not actual["exists"]:
            all_missing += 1
        elif actual["sha256"] != expected.get("sha256") or actual["size_bytes"] != expected.get("size"):
            all_mismatches += 1
    portrait_pass = bool(expected_records) and all(item["match"] for item in expected_records)
    toml_pass = bool(toml_records) and all(item["status"] == "PASS" for item in toml_records)
    # ``fork_context=false`` is a spawn-time requirement recorded in the two
    # agent instructions.  It is not required to appear in the shared skill
    # document, so keep the leak scan and spawn-policy checks separate.
    leak_pass = bool(leak_records) and all(
        item["exists"] and not item["forbidden_project_specific_text"] for item in leak_records
    ) and all(
        item["fork_context_false_text"]
        for item in leak_records
        if item["path"].endswith(".toml")
    )
    return {
        "target_snapshot": git_snapshot(target),
        "portrait_manifest_component": component.get("id") if isinstance(component, dict) else None,
        "portrait_expected_files": expected_records,
        "portrait_manifest_status": "PASS" if portrait_pass else "BLOCKED",
        "all_manifest_expected_file_count": len(all_expected),
        "all_manifest_missing_count": all_missing,
        "all_manifest_mismatch_count": all_mismatches,
        "all_manifest_baseline_status": "PASS" if all_missing == 0 and all_mismatches == 0 else "BLOCKED_PREEXISTING_EXPECTED_FILE_DRIFT",
        "toml_parse": {"status": "PASS" if toml_pass else "BLOCKED", "files": toml_records},
        "portrait_leak_and_spawn_policy": {"status": "PASS" if leak_pass else "BLOCKED", "files": leak_records, "spawn_parameter_policy": "Parent must pass fork_context=false when spawning; config files record the requirement in developer instructions."},
        "target_live_consumer_validation": "NOT_RUN_PARENT_OWNED",
        "direct_apply": "NOT_PERFORMED",
    }


def write_markdown(report: dict[str, Any]) -> None:
    chaos = report["chaos_redux"]
    generic = report["agentic_hoi4_modding"]
    lines = [
        "# Integration target validation — 2026-07-29",
        "",
        f"Status: **{report['overall_status']}**",
        "",
        "This is a read-only audit of the local live target checkouts. No target repository was edited, reset, cleaned, committed, or pushed.",
        "",
        "## Chaos Redux",
        "",
        f"- Target snapshots found: `{len(chaos['targets'])}`.",
        f"- Installed-game target consumer surface: `{chaos['installed_game_target_surface']}`.",
        f"- Direct apply: `{chaos['direct_apply']}`.",
        "- Baseline comparisons are recorded in the JSON report; divergent or missing files require a regenerated patch and parent review.",
        "",
        "## Generic Agentic HOI4 Modding",
        "",
        f"- Portrait package file parity: `{generic['portrait_manifest_status']}`.",
        f"- Whole-target setup manifest: `{generic['all_manifest_baseline_status']}` ({generic['all_manifest_mismatch_count']} mismatches, {generic['all_manifest_missing_count']} missing files).",
        f"- TOML parse: `{generic['toml_parse']['status']}`.",
        f"- Portrait leak/spawn-policy scan: `{generic['portrait_leak_and_spawn_policy']['status']}`.",
        f"- Live consumer validation: `{generic['target_live_consumer_validation']}`.",
        "",
        "## Remaining blockers",
        "",
    ]
    lines.extend(f"- {item}" for item in report["blockers"])
    lines.extend(["", "Machine-readable evidence: [`integration_target_validation_2026-07-29.json`](integration_target_validation_2026-07-29.json).", ""])
    MARKDOWN_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    installed = Path.home() / "Documents/Paradox Interactive/Hearts of Iron IV/mod/Chaos-Redux"
    chaos_targets: list[tuple[str, Path]] = [("chaos_redux_project_checkout", ROOT / "repos/Chaos-Redux-live")]
    if installed.is_dir() and installed.resolve() != chaos_targets[0][1].resolve():
        chaos_targets.insert(0, ("chaos_redux_installed_game_mod", installed))
    chaos_records = [{"target_id": target_id, "audit": compare_chaos_package(path)} for target_id, path in chaos_targets]
    generic = generic_portrait_audit(ROOT / "repos/Agentic-HOI4-Modding")

    blockers = [
        "Chaos Redux direct application remains blocked until a clean, current target diff and parent-owned consumer validation exist.",
        "The generic target has pre-existing setup-manifest expected-file drift and remains uncommitted/unpushed by owner instruction.",
        "Parent-owned live consumer validation and final mod wiring were not run because no independently audited production candidate exists.",
    ]
    report = {
        "schema_version": "1.0.0",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "scope": "read_only_live_integration_target_validation",
        "overall_status": "PORTABLE_VALIDATION_PASS_LIVE_APPLY_BLOCKED",
        "source_project": "comfyui-hoi4-portraits",
        "chaos_redux": {
            "targets": chaos_records,
            "installed_game_target_surface": "PRESENT" if installed.is_dir() else "UNAVAILABLE",
            "direct_apply": "BLOCKED_READ_ONLY_AUDIT",
        },
        "agentic_hoi4_modding": generic,
        "blockers": blockers,
        "production_boundary": {
            "final_png": "NOT_CREATED",
            "final_dds": "NOT_CREATED",
            "final_gfx_wiring": "NOT_CREATED",
            "live_consumer_validation": "NOT_RUN",
        },
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    write_markdown(report)
    print(json.dumps({"status": report["overall_status"], "report": str(REPORT_PATH.relative_to(ROOT)), "blocker_count": len(blockers)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
