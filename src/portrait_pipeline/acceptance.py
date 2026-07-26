from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import ExitCode
from .audit import independent_audit_blocked
from .dds import DdsValidationError, convert_png_to_dds
from .experiments import build_matrix
from .graph_spec.builder import build_workflow_artifacts
from .preflight import collect_preflight
from .prompt import autoprompter_instruction_sha256, validate_prompt
from .util import project_root, scan_text_for_secrets, sha256_file
from .workflow_validation import validate_all_workflows


def _prompt_gate() -> dict[str, Any]:
    cases = [
        ("valid", "hoi4_portrait, a middle-aged man with an oval face, short hair, glasses, and a neutral expression", True),
        ("wrong_trigger", "hoi4, a middle-aged man", False),
        ("heading", "Prompt: hoi4_portrait, a man", False),
        ("quoted", '"hoi4_portrait, a man"', False),
        ("paragraph", "hoi4_portrait, a man\nwith glasses", False),
        ("name_leak", "hoi4_portrait, John Example with short hair", False),
        ("background", "hoi4_portrait, a man in a studio background", False),
        ("lighting", "hoi4_portrait, a man with dramatic lighting", False),
        ("style", "hoi4_portrait, an oil painting of a man", False),
        ("nationality", "hoi4_portrait, a German man", False),
        ("medal", "hoi4_portrait, a man with a medal", False),
    ]
    results = []
    for name, prompt, expected in cases:
        result = validate_prompt(prompt, record_name="John Example")
        results.append({"name": name, "passed": result.passed, "expected": expected, "match": result.passed == expected, "result": result.as_dict()})
    return {"status": "PASS" if all(item["match"] for item in results) else "FAIL", "cases": results}


def _secret_scan(root: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    try:
        import subprocess

        tracked = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=False).stdout.decode().split("\0")
    except OSError:
        tracked = []
    for relative in tracked:
        if not relative or relative.endswith((".safetensors", ".gguf", ".png", ".dds")):
            continue
        path = root / relative
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for label in scan_text_for_secrets(text):
                findings.append({"path": relative, "label": label})
    return {"status": "PASS" if not findings else "FAIL", "findings": findings}


def _dds_gate(root: Path) -> dict[str, Any]:
    """Exercise both the negative audit gate and the locked DDS round trip.

    This is a synthetic converter test only. It never creates a production
    portrait and cannot substitute for an independent audit of a real job.
    """

    try:
        from PIL import Image  # type: ignore
    except ImportError as exc:
        return {"status": "BLOCKED", "negative_gate": "NOT_RUN", "positive_round_trip": "NOT_RUN", "reason": f"Pillow unavailable: {type(exc).__name__}"}
    with tempfile.TemporaryDirectory(prefix="hoi4-dds-acceptance-") as directory:
        temp_root = Path(directory)
        png_path = temp_root / "candidate.png"
        blocked_audit_path = temp_root / "blocked-audit.json"
        pass_audit_path = temp_root / "pass-audit.json"
        dds_path = temp_root / "candidate.dds"
        Image.new("RGBA", (156, 210), (17, 29, 43, 255)).save(png_path, format="PNG", optimize=False)
        blocked = independent_audit_blocked("acceptance", "candidate-000")
        blocked_audit_path.write_text(json.dumps(blocked), encoding="utf-8")
        negative_passed = False
        try:
            convert_png_to_dds(png_path, temp_root / "blocked.dds", blocked_audit_path, root)
        except DdsValidationError:
            negative_passed = True
        passing = independent_audit_blocked("acceptance", "candidate-000")
        passing["thresholds_id"] = "synthetic-acceptance-only"
        passing["verdict"] = "PASS"
        passing["hard_gates"] = {name: "PASS" for name in passing["hard_gates"]}
        pass_audit_path.write_text(json.dumps(passing), encoding="utf-8")
        try:
            positive = convert_png_to_dds(png_path, dds_path, pass_audit_path, root)
            positive_passed = positive.get("pixel_round_trip") == "PASS" and positive.get("size_bytes") == 131168
        except DdsValidationError as exc:
            positive = {"error": type(exc).__name__}
            positive_passed = False
    return {"status": "PASS" if negative_passed and positive_passed else "FAIL", "negative_gate": "PASS" if negative_passed else "FAIL", "positive_round_trip": "PASS" if positive_passed else "FAIL", "evidence": "synthetic-only; production DDS remains prohibited until a real independent all-PASS audit exists"}


def run_acceptance(root: str | Path | None = None) -> dict[str, Any]:
    root_path = project_root(root)
    workflow_manifest = build_workflow_artifacts(root_path)
    preflight = collect_preflight(root_path)
    workflows = validate_all_workflows(root_path)
    prompt_gate = _prompt_gate()
    lora = root_path / "loras" / "hoi4_portrait_new_style_lora.safetensors"
    lora_gate = {"status": "PASS" if lora.is_file() and sha256_file(lora) == "2ad94552d151d2dedf151cf7356cdd3ea07677607ff289fc0ac61534b34dead1" else "FAIL", "sha256": sha256_file(lora) if lora.is_file() else None}
    experiments = {"status": "BLOCKED_UNTIL_RUNTIME", "matrix_id": build_matrix()["matrix_id"], "matrix_written": (root_path / "experiments" / "identity_style_matrix.json").is_file()}
    chaos_review_path = root_path / "integrations/chaos-redux/live_review.json"
    generic_review_path = root_path / "integrations/agentic-hoi4-modding/live_review.json"
    chaos_review = json.loads(chaos_review_path.read_text(encoding="utf-8")) if chaos_review_path.is_file() else {}
    generic_review = json.loads(generic_review_path.read_text(encoding="utf-8")) if generic_review_path.is_file() else {}
    chaos_gate = "PASS" if chaos_review.get("status") == "APPLIED_AND_VALIDATED" else "BLOCKED"
    generic_gate = "PASS" if generic_review.get("status") == "APPLIED_AND_VALIDATED" else "BLOCKED"
    integration = {
        "status": "PASS" if chaos_gate == "PASS" and generic_gate == "PASS" else "BLOCKED",
        "chaos_redux_live_review": chaos_gate,
        "chaos_redux_status": chaos_review.get("status"),
        "generic_live_review": generic_gate,
        "generic_status": generic_review.get("status"),
        "direct_application": "NOT_PERFORMED",
    }
    dds_guard = _dds_gate(root_path)
    report = {
        "schema_version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "overall_status": "BLOCKED" if preflight["status"] != "PASS" or any(item["structural_status"] != "PASS" for item in workflows) or dds_guard["status"] != "PASS" or integration["status"] != "PASS" else "PASS",
        "recommended_exit_code": preflight["recommended_exit_code"] if preflight["status"] != "PASS" else 0,
        "gates": {
            "package_checksums": next((gate for gate in preflight["gates"] if gate["name"] == "planning_package_checksums"), None),
            "hardware_detection": next((gate for gate in preflight["gates"] if gate["name"] == "hardware_detection"), None),
            "hardware_runtime": next((gate for gate in preflight["gates"] if gate["name"] == "local_runtime_capability"), None),
            "remote_topology_auth": next((gate for gate in preflight["gates"] if gate["name"] == "remote_topology_auth"), None),
            "immutable_lora": lora_gate,
            "approved_background": next((gate for gate in preflight["gates"] if gate["name"] == "approved_source_background"), None),
            "source_fixture_and_provenance": next((gate for gate in preflight["gates"] if gate["name"] == "source_fixture_and_provenance"), None),
            "dependencies_and_models": next((gate for gate in preflight["gates"] if gate["name"] == "model_artifact_preflight"), None),
            "custom_node_preflight": next((gate for gate in preflight["gates"] if gate["name"] == "custom_node_preflight"), None),
            "runtime_dependency_lock": next((gate for gate in preflight["gates"] if gate["name"] == "comfyui_runtime_dependency_lock"), None),
            "krea_live_compatibility": next((gate for gate in preflight["gates"] if gate["name"] == "krea_live_compatibility"), None),
            "preprocessing_and_audit_dependencies": next((gate for gate in preflight["gates"] if gate["name"] == "preprocessing_and_audit_dependencies"), None),
            "calibrated_identity_thresholds": next((gate for gate in preflight["gates"] if gate["name"] == "calibrated_identity_thresholds"), None),
            "repository_preflight": next((gate for gate in preflight["gates"] if gate["name"] == "repository_preflight"), None),
            "licenses_and_rights": next((gate for gate in preflight["gates"] if gate["name"] == "license_and_rights_review"), None),
            "workflow_structure": workflows,
            "autoprompter_validator": prompt_gate,
            "dds_gate": dds_guard,
            "identity_style_experiments": experiments,
            "integration_packages": integration,
            "secret_scan": _secret_scan(root_path),
        },
        "preflight_blockers": preflight["blockers"],
        "workflow_manifest": workflow_manifest,
        "runtime_claims": {"local_mac_execution": "NOT_CLAIMED", "remote_runpod_execution": "NOT_CLAIMED", "final_png": "NOT_CREATED", "final_dds": "NOT_CREATED", "mod_wiring": "PARENT_AGENT_ONLY"},
        "source_pins": {"autoprompter_instruction_sha256": autoprompter_instruction_sha256(root_path), "style_lora_sha256": lora_gate["sha256"]},
    }
    return report


def render_report(report: dict[str, Any]) -> str:
    lines = [
        "# Acceptance Report",
        "",
        f"- Overall: **{report['overall_status']}**",
        f"- Recommended exit code: `{report['recommended_exit_code']}`",
        "",
        "## Gate summary",
        "",
        "| Gate | Status |",
        "| --- | --- |",
    ]
    for name, value in report["gates"].items():
        if isinstance(value, dict) and "status" in value:
            status = value["status"]
        elif isinstance(value, list):
            status = "PASS" if all(item.get("structural_status") == "PASS" for item in value) else "FAIL"
        else:
            status = "SEE_JSON"
        lines.append(f"| `{name}` | **{status}** |")
    lines.extend(["", "## Blockers", ""])
    lines.extend(f"- {item}" for item in report["preflight_blockers"])
    lines.extend(["", "## Runtime claims", "", "```json", json.dumps(report["runtime_claims"], indent=2), "```", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run structural and fail-closed acceptance checks.")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args(argv)
    root_path = project_root(args.root)
    report = run_acceptance(root_path)
    output_dir = root_path / "docs" / "acceptance"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "acceptance_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "acceptance_report.md").write_text(render_report(report), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return int(report["recommended_exit_code"])
