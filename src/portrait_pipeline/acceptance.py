from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import ExitCode
from .audit import independent_audit_blocked
from .benchmarks import write_benchmark_reports
from .comparisons import write_comparison_report
from .contracts import build_blocked_output
from .dds import DdsValidationError, convert_png_to_dds
from .experiments import build_matrix, write_execution_report
from .graph_spec.builder import build_workflow_artifacts
from .preflight import collect_preflight
from .prompt import autoprompter_instruction_sha256, validate_prompt
from .util import project_root, sanitize_public_paths, scan_text_for_secrets, sha256_file
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
            convert_png_to_dds(png_path, temp_root / "blocked.dds", blocked_audit_path, root, allow_synthetic_test=True)
        except DdsValidationError:
            negative_passed = True
        passing = independent_audit_blocked("acceptance", "candidate-000")
        passing["thresholds_id"] = "synthetic-acceptance-only"
        passing["verdict"] = "PASS"
        passing["hard_gates"] = {name: "PASS" for name in passing["hard_gates"]}
        passing["metrics"].update({"audit_mode": "synthetic_test"})
        pass_audit_path.write_text(json.dumps(passing), encoding="utf-8")
        try:
            positive = convert_png_to_dds(png_path, dds_path, pass_audit_path, root, allow_synthetic_test=True)
            positive_passed = positive.get("pixel_round_trip") == "PASS" and positive.get("size_bytes") == 131168
        except DdsValidationError as exc:
            positive = {"error": type(exc).__name__}
            positive_passed = False
    return {"status": "PASS" if negative_passed and positive_passed else "FAIL", "negative_gate": "PASS" if negative_passed else "FAIL", "positive_round_trip": "PASS" if positive_passed else "FAIL", "evidence": "synthetic-only; production DDS remains prohibited until a real independent all-PASS audit exists"}


def _comfy_cloud_gate(root: Path) -> dict[str, Any]:
    """Record the Cloud route without mistaking credentials for acceptance."""

    base_url = os.environ.get("COMFY_CLOUD_BASE_URL", "https://cloud.comfy.org")
    key_present = bool(os.environ.get("COMFY_CLOUD_API_KEY") or os.environ.get("COMFY_API_KEY"))
    workflows = ["human_full_power_gpu", "agent_full_power_gpu"]
    probe_paths = sorted((root / "docs" / "preflight").glob("comfy_cloud_ui_probe_*.json"))
    probe_path = probe_paths[-1] if probe_paths else None
    probe: dict[str, Any] = {}
    if probe_path is not None:
        try:
            loaded = json.loads(probe_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                probe = loaded
        except (OSError, json.JSONDecodeError):
            probe = {}
    status = str(probe.get("status")) if probe.get("status") else ("BLOCKED_LIVE_CAPABILITY_NOT_VERIFIED" if key_present else "BLOCKED_NOT_CONNECTED")
    workflow_import = probe.get("workflow_import", "NOT_RUN")
    node_parity = "BLOCKED" if status == "BLOCKED_CLOUD_NODE_MODEL_PARITY" else "NOT_RUN"
    model_availability = "BLOCKED" if status == "BLOCKED_CLOUD_NODE_MODEL_PARITY" else "NOT_RUN"
    source_bridge = probe.get("source_upload", "NOT_RUN")
    return {
        "status": status,
        "provider": "comfy_cloud",
        "base_url": base_url,
        "base_url_https": base_url.startswith("https://"),
        "api_key_present": key_present,
        "profiles": workflows,
        "workflow_import": workflow_import,
        "node_parity": node_parity,
        "model_availability": model_availability,
        "source_upload_and_job_contract_bridge": source_bridge,
        "live_execution": "NOT_RUN",
        "ui_probe_path": str(probe_path.relative_to(root)) if probe_path is not None else None,
        "ui_probe_authentication": probe.get("authentication") if probe else None,
        "acceptance_policy": "Cloud credentials never promote a workflow. Import, node/model parity, source/job-contract delivery, output checksums, and independent all-gates audit must pass first.",
    }


def _schema_gate(root: Path) -> dict[str, Any]:
    schema_files = {
        "benchmark": (root / "schemas/portrait_benchmark_report.schema.json", sorted((root / "docs/benchmarks").glob("*.json"))),
        "comparison": (root / "schemas/portrait_comparison_report.schema.json", [root / "docs/comparisons/identity_style_comparison.json"]),
    }
    schema_fixtures = {
        "audit": (
            root / "schemas/portrait_audit.schema.json",
            [("in-memory:blocked-audit", independent_audit_blocked("schema-fixture", "candidate-000"))],
        ),
        "job_input": (
            root / "schemas/portrait_job_input.schema.json",
            [
                (
                    "in-memory:valid-job-input",
                    {
                        "schema_version": "1.0.0",
                        "job_id": "fixture-001",
                        "execution_profile": "agent_local_mac_16gb",
                        "source_image_path": "fixtures/source.png",
                        "source_provenance": {"source_class": "user_provided", "attribution": "user", "rights_notes": "authorized"},
                        "subject_identity": {"record_name": "Example", "identity_classification": "approved_fictional_subject", "real_person": False},
                        "prompt": "hoi4_portrait, a person with a neutral expression",
                        "intended_hoi4_role": "country_leader",
                        "final_output_stem": "fixture_portrait",
                        "approved_background": {"registry_id": "background-1", "path": "backgrounds/bg.png", "sha256": "a" * 64},
                        "seed_policy": {"mode": "derived"},
                        "candidate_count": 1,
                        "retry_limit": 0,
                        "identity_thresholds_id": "calibrated-1",
                        "style_thresholds_id": "calibrated-style-1",
                        "final_png_path": "final/fixture.png",
                        "final_dds_path": "final/fixture.dds",
                    },
                )
            ],
        ),
        "job_output": (
            root / "schemas/portrait_job_output.schema.json",
            [
                (
                    "in-memory:blocked-job-output",
                    build_blocked_output(None, ExitCode.BACKGROUND_UNRESOLVED, "schema fixture", root=root),
                )
            ],
        ),
        "visual_audit_evidence": (
            root / "schemas/visual_audit_evidence.schema.json",
            [
                (
                    "in-memory:valid-visual-audit-evidence",
                    {
                        "schema_version": "1.0.0",
                        "status": "PASS",
                        "auditor": {
                            "process_id": "visual-auditor-fixture",
                            "independent_from_producer": True,
                            "reviewed_at": datetime.now(timezone.utc).isoformat(),
                        },
                        "model": {
                            "name": "fixture-visual-rubric",
                            "revision": "fixture-revision",
                            "artifact_sha256": "a" * 64,
                        },
                        "reference_set": {
                            "id": "fixture-country-leader-style-v1",
                            "role": "country_leader",
                            "manifest_sha256": "b" * 64,
                            "sample_count": 1,
                        },
                        "source_sha256": "c" * 64,
                        "candidate_sha256": "d" * 64,
                        "scores": {
                            "hairline": 1.0,
                            "facial_hair": 1.0,
                            "accessories": 1.0,
                            "style": 1.0,
                        },
                        "human_readable_evidence": {
                            "hairline": "fixture hairline agrees",
                            "facial_hair": "fixture facial hair agrees",
                            "accessories": "fixture accessories agree",
                            "style": "fixture style agrees with the approved reference set",
                        },
                    },
                )
            ],
        ),
        "visual_reference_set": (
            root / "schemas/visual_reference_set.schema.json",
            [
                (
                    "in-memory:valid-visual-reference-set",
                    {
                        "schema_version": "1.0.0",
                        "reference_set_id": "fixture-country-leader-style-v1",
                        "revision": "fixture-revision",
                        "role": "country_leader",
                        "status": "APPROVED_PRIVATE",
                        "source_class": "synthetic",
                        "rights_notes": "Synthetic acceptance fixture only.",
                        "approved_by": ["acceptance-fixture"],
                        "reviewed_at": datetime.now(timezone.utc).isoformat(),
                        "images": [{
                            "reference_id": "fixture-reference-1",
                            "path": "private/reference.png",
                            "sha256": "a" * 64,
                            "width": 156,
                            "height": 210,
                        }],
                    },
                )
            ],
        ),
    }
    try:
        from jsonschema import Draft202012Validator  # type: ignore
    except ImportError as exc:
        return {"status": "BLOCKED", "reason": f"normative JSON Schema validator is unavailable: {type(exc).__name__}", "checked": []}
    checked: list[dict[str, Any]] = []
    all_cases = {
        **{name: (schema_path, [(str(path.relative_to(root)), None) for path in reports]) for name, (schema_path, reports) in schema_files.items()},
        **{name: (schema_path, [(label, payload) for label, payload in fixtures]) for name, (schema_path, fixtures) in schema_fixtures.items()},
    }
    for name, (schema_path, cases) in all_cases.items():
        try:
            validator = Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            return {"status": "BLOCKED", "reason": f"{name} schema is unreadable: {type(exc).__name__}", "checked": checked}
        for report_label, inline_payload in cases:
            try:
                if inline_payload is None:
                    payload = json.loads((root / report_label).read_text(encoding="utf-8"))
                else:
                    payload = inline_payload
                errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
            except (OSError, json.JSONDecodeError) as exc:
                errors = [f"report unreadable: {type(exc).__name__}"]
            checked.append({"schema": str(schema_path.relative_to(root)), "report": report_label, "status": "PASS" if not errors else "FAIL", "error": str(errors[0]) if errors else None})
    return {"status": "PASS" if checked and all(item["status"] == "PASS" for item in checked) else "BLOCKED", "checked": checked}


def run_acceptance(root: str | Path | None = None) -> dict[str, Any]:
    root_path = project_root(root)
    workflow_manifest = build_workflow_artifacts(root_path)
    preflight = collect_preflight(root_path)
    workflows = validate_all_workflows(root_path)
    benchmark_reports = write_benchmark_reports(root_path)
    benchmark_gate = {
        "status": "PASS" if benchmark_reports and all(report["status"] == "PASS" for report in benchmark_reports) else "BLOCKED",
        "reports": [
            {
                "profile": report["profile"],
                "status": report["status"],
                "json_path": f"docs/benchmarks/{report['profile']}.json",
                "markdown_path": f"docs/benchmarks/{report['profile']}.md",
                "expected_model_bytes": report["resource_model"]["expected_model_bytes"],
                "peak_memory_bytes": report["resource_model"]["peak_memory_bytes"],
                "peak_vram_bytes": report["resource_model"]["peak_vram_bytes"],
            }
            for report in benchmark_reports
        ],
        "policy": "A blocked report is evidence of an unmeasured or unavailable gate, never a successful benchmark claim.",
    }
    comparison_report = write_comparison_report(root_path)
    comparison_gate = {
        "status": comparison_report["status"],
        "json_path": "docs/comparisons/identity_style_comparison.json",
        "markdown_path": "docs/comparisons/identity_style_comparison.md",
        "candidate_count": comparison_report["candidate_counts"]["observed"],
        "reason": comparison_report["reason"],
    }
    schema_gate = _schema_gate(root_path)
    prompt_gate = _prompt_gate()
    lora = root_path / "loras" / "hoi4_portrait_new_style_lora.safetensors"
    lora_gate = {"status": "PASS" if lora.is_file() and sha256_file(lora) == "2ad94552d151d2dedf151cf7356cdd3ea07677607ff289fc0ac61534b34dead1" else "FAIL", "sha256": sha256_file(lora) if lora.is_file() else None}
    matrix = build_matrix()
    matrix_execution = write_execution_report(root_path)
    experiments = {
        "status": matrix["status"],
        "matrix_id": matrix["matrix_id"],
        "matrix_path": "experiments/identity_style_matrix.json",
        "matrix_written": (root_path / "experiments" / "identity_style_matrix.json").is_file(),
        "execution_status": matrix_execution["execution_status"],
        "required_eight_step_turbo_status": matrix_execution["required_eight_step_turbo_status"],
        "execution_report_path": "docs/preflight/identity_style_matrix_execution_2026-07-29.json",
        "queued_jobs": matrix_execution["queued_jobs"],
        "candidate_count": matrix_execution["candidate_count"],
        "blocked_reasons": matrix_execution["blocked_reasons"],
        "selection_policy": matrix["selection_policy"],
        "reason": "The matrix execution report is fail-closed: no candidate was queued because mandatory preflight and independent-audit prerequisites remain unresolved.",
    }
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
    comfy_cloud = _comfy_cloud_gate(root_path)
    report = {
        "schema_version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "overall_status": "BLOCKED" if preflight["status"] != "PASS" or any(item["structural_status"] != "PASS" for item in workflows) or dds_guard["status"] != "PASS" or integration["status"] != "PASS" or benchmark_gate["status"] != "PASS" or comparison_gate["status"] != "PASS" or comfy_cloud["status"] != "PASS" or schema_gate["status"] != "PASS" else "PASS",
        "recommended_exit_code": preflight["recommended_exit_code"] if preflight["status"] != "PASS" else (int(ExitCode.AUDIT_UNCERTAIN) if comparison_gate["status"] != "PASS" else 0),
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
            "autoprompter_runtime": next((gate for gate in preflight["gates"] if gate["name"] == "autoprompter_runtime"), None),
            "visual_audit_runtime": next((gate for gate in preflight["gates"] if gate["name"] == "visual_audit_runtime"), None),
            "preprocessing_and_audit_dependencies": next((gate for gate in preflight["gates"] if gate["name"] == "preprocessing_and_audit_dependencies"), None),
            "calibrated_identity_thresholds": next((gate for gate in preflight["gates"] if gate["name"] == "calibrated_identity_thresholds"), None),
            "repository_preflight": next((gate for gate in preflight["gates"] if gate["name"] == "repository_preflight"), None),
            "licenses_and_rights": next((gate for gate in preflight["gates"] if gate["name"] == "license_and_rights_review"), None),
            "workflow_structure": workflows,
            "autoprompter_validator": prompt_gate,
            "dds_gate": dds_guard,
            "identity_style_experiments": experiments,
            "benchmark_reports": benchmark_gate,
            "identity_style_comparison": comparison_gate,
            "comfy_cloud_execution": comfy_cloud,
            "schema_validation": schema_gate,
            "integration_packages": integration,
            "secret_scan": _secret_scan(root_path),
        },
        "preflight_blockers": preflight["blockers"],
        "workflow_manifest": workflow_manifest,
        "runtime_claims": {"local_mac_execution": "CPU_FALLBACK_CANDIDATE_PRODUCED_PRODUCTION_GATES_BLOCKED", "comfy_cloud_execution": "NOT_CLAIMED", "final_png": "NOT_CREATED", "final_dds": "NOT_CREATED", "mod_wiring": "PARENT_AGENT_ONLY"},
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
    additional: list[str] = []
    for name, value in report["gates"].items():
        if not isinstance(value, dict) or value.get("status") in {"PASS", "NOT_APPLICABLE"}:
            continue
        if name in {"package_checksums", "hardware_detection", "hardware_runtime", "remote_topology_auth", "approved_background", "source_fixture_and_provenance", "dependencies_and_models", "custom_node_preflight", "runtime_dependency_lock", "krea_live_compatibility", "autoprompter_runtime", "preprocessing_and_audit_dependencies", "calibrated_identity_thresholds", "repository_preflight", "licenses_and_rights"}:
            continue
        if name == "benchmark_reports":
            detail = ", ".join(f"{item['profile']}={item['status']}" for item in value.get("reports", []))
        else:
            detail = str(value.get("reason") or value.get("image_lock_status") or value.get("status"))
        additional.append(f"`{name}`: {detail}")
    if additional:
        lines.extend(["", "## Additional blocked or skipped surfaces", ""])
        lines.extend(f"- {item}" for item in additional)
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
    public_report = sanitize_public_paths(report, root_path)
    (output_dir / "acceptance_report.json").write_text(json.dumps(public_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "acceptance_report.md").write_text(render_report(report), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return int(report["recommended_exit_code"])
