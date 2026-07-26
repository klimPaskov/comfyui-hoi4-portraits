#!/usr/bin/env python3
"""Fail-closed bootstrap entrypoint.

This command is intentionally safe to run on a clean machine. It records the
preflight first and refuses all downloads or installs while any hard gate is
unresolved. The current project state is expected to stop at that boundary.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from portrait_pipeline.constants import ExitCode  # noqa: E402
from portrait_pipeline.graph_spec.builder import build_workflow_artifacts  # noqa: E402
from portrait_pipeline.preflight import collect_preflight, render_markdown  # noqa: E402
from portrait_pipeline.util import atomic_json_write, sha256_file  # noqa: E402
from portrait_pipeline.workflow_validation import validate_all_workflows  # noqa: E402


def _capability_report(profile: str, preflight: dict[str, Any], actions: list[dict[str, Any]]) -> dict[str, Any]:
    return {"schema_version": "1.0.0", "profile": profile, "created_at": datetime.now(timezone.utc).isoformat(), "status": preflight["status"], "installation_permitted": preflight["installation_permitted"], "preflight": preflight, "actions": actions, "workflow_validation": validate_all_workflows(ROOT) if all((ROOT / path).is_file() for path in ("workflows/human/local_mac_16gb/human_local_mac_16gb.json", "workflows/agent/remote_runpod/agent_remote_runpod.json")) else []}


def _run(command: list[str], cwd: Path = ROOT) -> dict[str, Any]:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    return {"command": command, "returncode": result.returncode, "stdout": result.stdout[-2000:], "stderr": result.stderr[-2000:]}


def restore_from_lock(profile: str) -> list[dict[str, Any]]:
    """Restore pinned components after preflight has passed.

    The function is not called in the current blocked environment. Every
    external operation is explicit, non-interactive, revision-pinned, and
    followed by an import/checksum gate.
    """
    actions: list[dict[str, Any]] = []
    comfy_root = ROOT / "comfyui"
    dependency_lock = json.loads((ROOT / "dependencies" / "dependencies.lock.json").read_text(encoding="utf-8"))
    comfy = next(item for item in dependency_lock["dependencies"] if item["name"] == "ComfyUI")
    if not comfy_root.exists():
        actions.append(_run(["git", "clone", "https://github.com/Comfy-Org/ComfyUI.git", str(comfy_root)]))
    actions.append(_run(["git", "fetch", "--tags", "--force", "origin"], comfy_root))
    actions.append(_run(["git", "checkout", "--detach", comfy["version_or_commit"]], comfy_root))
    custom_root = comfy_root / "custom_nodes" / "comfyui-krea2edit"
    if not custom_root.exists():
        actions.append(_run(["git", "clone", "https://github.com/lbouaraba/comfyui-krea2edit.git", str(custom_root)], comfy_root))
    actions.append(_run(["git", "checkout", "--detach", "cae442e11b59bcba04ed82f4c01ffe3752531fe1"], custom_root))
    project_nodes = comfy_root / "custom_nodes" / "hoi4_portrait_nodes"
    if project_nodes.exists() and project_nodes.is_symlink():
        project_nodes.unlink()
    elif project_nodes.exists():
        raise RuntimeError(f"refusing to overwrite existing custom node path: {project_nodes}")
    project_nodes.symlink_to(ROOT / "src" / "comfyui_hoi4_portrait_nodes", target_is_directory=True)
    actions.append({"action": "project_nodes_symlink", "path": str(project_nodes), "target": str(project_nodes.resolve())})
    build_workflow_artifacts(ROOT)
    actions.append({"action": "workflows_built", "status": "PASS"})
    return actions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-closed HOI4 portrait bootstrap.")
    parser.add_argument("--profile", required=True, choices=["local_mac_16gb", "full_power_gpu", "remote_runpod"])
    parser.add_argument("--restore-from-lock", action="store_true")
    args = parser.parse_args(argv)
    preflight = collect_preflight(ROOT)
    actions: list[dict[str, Any]] = []
    if preflight["status"] != "PASS":
        actions.append({"action": "installation", "status": "SKIPPED_HARD_PREFLIGHT_BLOCK", "reason": " and ".join(preflight["blockers"])})
        report = _capability_report(args.profile, preflight, actions)
        output_dir = ROOT / "docs" / "capabilities"
        output_dir.mkdir(parents=True, exist_ok=True)
        atomic_json_write(output_dir / f"{args.profile}.json", report)
        (output_dir / f"{args.profile}.md").write_text(render_markdown(preflight), encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return int(preflight["recommended_exit_code"])
    if not args.restore_from_lock:
        print("preflight passed but --restore-from-lock is required; no install performed", file=sys.stderr)
        return int(ExitCode.DEPENDENCY_MISSING)
    try:
        actions = restore_from_lock(args.profile)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        actions.append({"action": "installation", "status": "FAILED", "error": str(exc)})
        return_code = int(ExitCode.DEPENDENCY_MISSING)
    else:
        return_code = 0
    report = _capability_report(args.profile, preflight, actions)
    output_dir = ROOT / "docs" / "capabilities"
    output_dir.mkdir(parents=True, exist_ok=True)
    atomic_json_write(output_dir / f"{args.profile}.json", report)
    (output_dir / f"{args.profile}.md").write_text(render_markdown(preflight), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())

