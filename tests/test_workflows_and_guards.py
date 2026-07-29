from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from portrait_pipeline.audit import audit_is_promotion_pass, independent_audit_blocked
from portrait_pipeline.constants import CALIBRATED_THRESHOLD_STATUSES, ExitCode
from portrait_pipeline.controller import JobController, LOCAL_GENERATION_UNAVAILABLE
from portrait_pipeline.contracts import build_blocked_output, validate_schema
from portrait_pipeline.dds import DdsValidationError, convert_png_to_dds
from portrait_pipeline.graph_spec.builder import build_workflow_artifacts
from portrait_pipeline.mcp.adapter import AdapterError, PortraitMcpService
from portrait_pipeline.preflight import _model_artifact_preflight, _preprocessing_artifact_preflight, collect_preflight
from portrait_pipeline.workflow_validation import validate_all_workflows
from portrait_pipeline.util import project_root, sanitize_public_paths
from comfyui_hoi4_portrait_nodes import NODE_CLASS_MAPPINGS


class WorkflowAndGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = project_root()
        build_workflow_artifacts(cls.root)

    def test_required_and_local_nvidia_workflows_are_structurally_valid(self):
        reports = validate_all_workflows(self.root)
        self.assertEqual(len(reports), 5)
        for report in reports:
            self.assertEqual(report["structural_status"], "PASS", report)

    def test_workflow_manifest_uses_current_live_probe_timestamp(self):
        manifest = json.loads((self.root / "manifests/workflow_manifest.json").read_text(encoding="utf-8"))
        probe = json.loads((self.root / "docs/preflight/live_comfy_compatibility.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["generated_at"], probe["checked_at"])

    def test_local_nvidia_agent_is_routable_through_controller_and_adapter(self):
        controller_path = JobController(self.root)._workflow_api_path("agent_full_power_gpu")
        adapter_path = PortraitMcpService(self.root)._workflow_path("agent_full_power_gpu")
        self.assertEqual(controller_path, adapter_path)
        self.assertTrue(controller_path.is_file())

    def test_local_generation_unavailable_is_explicit_and_never_remote(self):
        controller = JobController(self.root)
        job = {"job_id": "local-unavailable-001", "execution_profile": "human_local_mac_16gb"}
        output = build_blocked_output(job, ExitCode.DEPENDENCY_MISSING, "measured local memory blocker", blockers=["MPS canary blocked"], root=self.root)
        with tempfile.TemporaryDirectory() as directory:
            job_root = Path(directory) / "job"
            job_root.mkdir()
            controller._record_local_generation_unavailable(job, job_root, output, stage="JOB_ACCEPTED")
            marker = json.loads((job_root / "local_generation_unavailable.json").read_text(encoding="utf-8"))
            self.assertEqual(marker["status"], LOCAL_GENERATION_UNAVAILABLE)
            self.assertEqual(marker["remote_submission"], "NOT_QUEUED_BY_LOCAL_ROUTE")
            self.assertEqual(output["error_code"], LOCAL_GENERATION_UNAVAILABLE)
            self.assertIn(LOCAL_GENERATION_UNAVAILABLE, output["warnings"])
            self.assertEqual(validate_schema(output, self.root / "schemas/portrait_job_output.schema.json"), [])

            remote_job = {"job_id": "remote-unavailable-001", "execution_profile": "agent_remote_runpod"}
            remote_output = build_blocked_output(remote_job, ExitCode.DEPENDENCY_MISSING, "remote blocker", blockers=["remote auth"], root=self.root)
            remote_root = Path(directory) / "remote"
            remote_root.mkdir()
            controller._record_local_generation_unavailable(remote_job, remote_root, remote_output, stage="JOB_ACCEPTED")
            self.assertFalse((remote_root / "local_generation_unavailable.json").exists())
            self.assertEqual(remote_output["error_code"], ExitCode.DEPENDENCY_MISSING.name)

    def test_human_workflows_keep_exact_instruction(self):
        instruction = (self.root / "prompts/autoprompter_instruction.txt").read_text(encoding="utf-8")
        for path in (self.root / "workflows/human").glob("**/*.api.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            ui_path = path.with_name(path.name.replace(".api.json", ".json"))
            values = [node.get("widgets_values", []) for node in json.loads(ui_path.read_text(encoding="utf-8")).get("nodes", []) if node.get("type") == "HOI4AutopromptClient"]
            self.assertEqual(values[0][0], instruction)
            self.assertEqual(data["_meta"]["autoprompter"], True)

    def test_agent_workflows_have_no_autoprompter(self):
        for path in (self.root / "workflows/agent").glob("**/*.api.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("HOI4AutopromptClient", json.dumps(data))
            self.assertNotIn("HOI4HumanControls", json.dumps(data))
            self.assertEqual(data["_meta"]["prompt_source"], "job_contract")

    def test_human_final_preview_shares_the_saved_image_source(self):
        for path in (self.root / "workflows/human").glob("**/*.api.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["23"]["inputs"]["images"], ["22", 0])
            self.assertEqual(data["28"]["inputs"]["images"], ["22", 0])
            pair = data["_meta"]["final_preview_save_pair"]
            self.assertEqual(pair["preview_node_id"], 28)
            self.assertEqual(pair["save_node_id"], 23)
            self.assertEqual(pair["shared_source_node_id"], 22)
        for path in (self.root / "workflows/agent").glob("**/*.api.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIsNone(data["_meta"]["final_preview_save_pair"]["preview_node_id"])

    def test_public_evidence_redacts_host_local_paths(self):
        sanitized = sanitize_public_paths({"root": str(self.root), "external": "/Users/example/private/source.png"}, self.root)
        self.assertEqual(sanitized["root"], "<project-root>")
        self.assertEqual(sanitized["external"], "<local-path>")

    def test_human_workflows_expose_controls_and_project_node_signatures_match(self):
        for path in (self.root / "workflows/human").glob("**/*.api.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("HOI4HumanControls", json.dumps(data))
            self.assertIn("HOI4HumanControls", data["_meta"]["required_project_nodes"])
        for path in self.root.joinpath("workflows").glob("**/*.api.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            for node in (value for key, value in data.items() if not key.startswith("_")):
                class_type = node.get("class_type")
                if class_type not in NODE_CLASS_MAPPINGS:
                    continue
                declared = set()
                input_types = NODE_CLASS_MAPPINGS[class_type].INPUT_TYPES()
                for section in ("required", "optional"):
                    declared.update(input_types.get(section, {}))
                self.assertTrue(set(node.get("inputs", {})) <= declared, (path, class_type, node.get("inputs"), declared))

    def test_krea_graph_matches_primary_fit_contract_and_records_schema_blocker(self):
        review = json.loads((self.root / "docs/preflight/krea_compatibility_review.json").read_text(encoding="utf-8"))
        self.assertEqual(review["status"], "QUALIFIED_CPU_FALLBACK_MPS_BLOCKED")
        self.assertEqual(next(item["status"] for item in review["findings"] if item["id"] == "pinned_core_loader_type"), "PASS")
        for path in self.root.joinpath("workflows").glob("**/*.api.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            patch_inputs = data["14"]["inputs"]
            self.assertEqual(patch_inputs["vae"], ["12", 0])
            self.assertEqual(patch_inputs["source_image"], ["8", 1])
            self.assertEqual(data["16"]["inputs"]["grounding_px"], 768)
            self.assertEqual(data["17"]["inputs"]["grounding_px"], 768)
            if data["_meta"]["human_workflow"]:
                self.assertEqual(data["9"]["inputs"]["image"], ["8", 0])
            self.assertEqual(data["29"]["class_type"], "HOI4KreaModelLoadBarrier")
            self.assertEqual(data["20"]["inputs"]["model"], ["29", 0])
            self.assertEqual(data["20"]["inputs"]["positive"], ["29", 1])
            self.assertEqual(data["20"]["inputs"]["negative"], ["29", 2])

    def test_job_input_validates_public_contract_before_private_runtime_context(self):
        background = json.loads((self.root / "config/background_registry.json").read_text(encoding="utf-8"))["backgrounds"][0]
        job = {
            "schema_version": "1.0.0",
            "job_id": "input-context-001",
            "execution_profile": "human_local_mac_16gb",
            "source_image_path": "README.md",
            "source_provenance": {"source_class": "user_provided", "attribution": "unit-test", "rights_notes": "unit-test"},
            "subject_identity": {"record_name": "unit_test_subject", "identity_classification": "approved_fictional_subject", "real_person": False},
            "subject_selector": None,
            "prompt": "hoi4_portrait, a person with a neutral expression",
            "intended_hoi4_role": "country_leader",
            "final_output_stem": "input_context_subject",
            "approved_background": {"registry_id": background["registry_id"], "path": background["runtime_path"], "sha256": background["sha256"]},
            "seed_policy": {"mode": "derived"},
            "candidate_count": 1,
            "retry_limit": 0,
            "identity_thresholds_id": "UNSET_BLOCK_EXECUTION",
            "style_thresholds_id": "UNSET_BLOCK_EXECUTION",
            "final_png_path": "jobs/input-context-001/final/input_context_subject.png",
            "final_dds_path": "jobs/input-context-001/final/input_context_subject.dds",
        }
        contract_dir = self.root / "jobs" / "input-context-001"
        contract_dir.mkdir(parents=True, exist_ok=True)
        contract_path = contract_dir / "input.json"
        contract_path.write_text(json.dumps(job), encoding="utf-8")
        try:
            with mock.patch.dict(os.environ, {"HOI4_PORTRAIT_PROJECT_ROOT": str(self.root)}):
                (validated,) = NODE_CLASS_MAPPINGS["HOI4JobInput"]().run(
                    "human_local_mac_16gb",
                    "jobs/input-context-001/input.json",
                    1,
                    0,
                    "derived",
                )
            self.assertEqual(validated["job_id"], "input-context-001")
            self.assertEqual(validated["_workflow_execution_profile"], "human_local_mac_16gb")
            self.assertEqual(validated["_project_root"], str(self.root))
        finally:
            contract_path.unlink(missing_ok=True)
            contract_dir.rmdir()

    def test_model_preflight_rejects_mismatch_and_unlocked_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model_root = root / "models"
            model_root.mkdir()
            model_path = model_root / "sample.safetensors"
            model_path.write_bytes(b"locked")
            import hashlib

            digest = hashlib.sha256(b"locked").hexdigest()
            entry = {"name": "sample", "mandatory": True, "profiles": ["agent_local_mac_16gb"], "destination_folder": "models", "filename": "sample.safetensors", "size_bytes": 6, "sha256": digest}
            self.assertEqual(_model_artifact_preflight(root, model_root, [entry], "agent_local_mac_16gb")["status"], "PASS")
            model_path.write_bytes(b"changed")
            self.assertEqual(_model_artifact_preflight(root, model_root, [entry], "agent_local_mac_16gb")["status"], "BLOCKED")
            model_path.write_bytes(b"locked")
            (model_root / "unlocked.bin").write_bytes(b"extra")
            self.assertEqual(_model_artifact_preflight(root, model_root, [entry], "agent_local_mac_16gb")["status"], "BLOCKED")
            unsupported = dict(entry, filename="sample.bin")
            model_path.rename(model_root / "sample.bin")
            self.assertEqual(_model_artifact_preflight(root, model_root, [unsupported], "agent_local_mac_16gb")["status"], "BLOCKED")

    def test_preprocessing_lock_is_complete_and_installed_artifacts_pass(self):
        lock = json.loads((self.root / "dependencies/preprocessing_lock.json").read_text(encoding="utf-8"))
        report = _preprocessing_artifact_preflight(self.root, lock)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["missing_checksums"], [])
        self.assertEqual(report["mandatory_count"], 5)
        self.assertEqual(report["source_artifact_count"], 3)
        self.assertEqual(report["source_verification_status"], "PASS")
        self.assertEqual(report["source_verification_issues"], [])
        self.assertTrue(all(item["status"] == "PASS" for item in report["checks"]), report)

    def test_human_face_index_selects_the_indexed_audited_subject(self):
        from types import SimpleNamespace
        import comfyui_hoi4_portrait_nodes.nodes as node_module

        with tempfile.TemporaryDirectory() as directory:
            job_root = Path(directory)
            inventory_path = job_root / "evidence" / "subject_inventory.json"
            inventory_path.parent.mkdir(parents=True)
            inventory_path.write_text(json.dumps({
                "analysis_status": "PASS",
                "subjects": [
                    {"bbox_xyxy": [10, 10, 40, 40]},
                    {"bbox_xyxy": [30, 20, 80, 90]},
                ],
                "selected": {"bbox_xyxy": [10, 10, 40, 40]},
            }), encoding="utf-8")
            fake_image = SimpleNamespace(shape=(1, 120, 100, 3))
            with mock.patch.object(node_module, "_job_root", return_value=job_root), mock.patch.object(node_module, "sha256_file", return_value="a" * 64):
                _, meta = NODE_CLASS_MAPPINGS["HOI4SubjectSelect"]().run({"job_id": "fixture-001", "subject_selector": {"mode": "face_index", "face_index": 1}}, fake_image)
            self.assertEqual(meta["selection"], "audited_face_index")
            self.assertEqual(meta["bbox_xyxy"], [30, 20, 80, 90])

    def test_foreground_mask_default_is_the_locked_model_name(self):
        mask_inputs = NODE_CLASS_MAPPINGS["HOI4ForegroundMask"].INPUT_TYPES()["required"]["mask_model"]
        self.assertEqual(mask_inputs[1]["default"], "BiRefNet")

    def test_profile_preflight_does_not_make_missing_remote_auth_a_local_blocker(self):
        local = collect_preflight(self.root, profile="agent_local_mac_16gb")
        remote = collect_preflight(self.root, profile="agent_remote_runpod")
        self.assertEqual(next(g["status"] for g in local["gates"] if g["name"] == "remote_topology_auth"), "NOT_APPLICABLE")
        self.assertEqual(next(g["status"] for g in remote["gates"] if g["name"] == "remote_topology_auth"), "DEFERRED_OUT_OF_SCOPE")

    def test_calibrated_threshold_status_gate_is_consistent(self):
        self.assertEqual(CALIBRATED_THRESHOLD_STATUSES, frozenset({"APPROVED", "RESOLVED"}))
        self.assertNotIn("BLOCKED_UNTIL_CALIBRATION", CALIBRATED_THRESHOLD_STATUSES)

    def test_identity_calibration_evidence_is_recorded_but_stays_fail_closed(self):
        evidence_path = self.root / "docs/preflight/identity_calibration_2026-07-29.json"
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        self.assertEqual(evidence["status"], "BLOCKED_FACE_CALIBRATION_INCOMPLETE")
        self.assertGreaterEqual(evidence["fixture_set"]["accepted_single_face_count"], 1)
        self.assertGreaterEqual(evidence["positive_same_person"]["score_count"], 1)
        self.assertEqual(evidence["fixture_manifest"]["status"], "PASS")
        self.assertEqual(evidence["fixture_manifest"]["declared_count"], evidence["fixture_manifest"]["observed_count"])
        self.assertFalse(evidence["operating_point"]["approved"])
        thresholds = json.loads((self.root / "config/identity_thresholds.json").read_text(encoding="utf-8"))
        self.assertEqual(thresholds["status"], "BLOCKED_UNTIL_CALIBRATION")
        self.assertTrue(thresholds["fail_closed"])

    def test_geometry_calibration_evidence_is_measured_but_not_approved(self):
        evidence = json.loads((self.root / "docs/preflight/geometry_calibration_2026-07-29.json").read_text(encoding="utf-8"))
        self.assertEqual(evidence["status"], "GEOMETRY_EVIDENCE_MEASURED_PRODUCTION_BLOCKED")
        self.assertGreaterEqual(evidence["fixture_set"]["accepted_single_face_count"], 20)
        self.assertGreater(evidence["measurement_count"], 0)
        self.assertGreaterEqual(evidence["measurement_count"], 100)
        self.assertEqual(evidence["model"]["face_crop_detector"]["name"], "YuNet")
        self.assertIn("landmarker_input_policy", evidence["fixture_set"])
        self.assertFalse(evidence["proposed_operating_point"]["approved"])

    def test_independent_auditor_uses_the_calibrated_face_crop_policy(self):
        from portrait_pipeline.independent_auditor import _landmark_signals

        candidate = self.root / "jobs/local-agent-loc-cpu-full-08-01/candidates/candidate-000.png"
        source = self.root / "jobs/local-agent-loc-cpu-full-08-01/evidence/source/master.png"
        if not source.is_file() or not candidate.is_file():
            self.skipTest("private diagnostic candidate evidence is unavailable")
        metrics, issue = _landmark_signals(self.root, source, candidate)
        self.assertIsNone(issue, metrics)
        self.assertEqual(metrics["landmark_status"], "PASS")
        self.assertIn("pinned_yunet_single_face_crop", metrics["landmark_input_policy"])
        self.assertEqual(len(metrics["landmark_model_sha256"]), 64)
        self.assertEqual(len(metrics["landmark_face_detector_sha256"]), 64)

    def test_visual_audit_evidence_is_hash_bound_and_fail_closed(self):
        from portrait_pipeline.visual_audit import evaluate_visual_audit

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.png"
            candidate = root / "candidate.png"
            source.write_bytes(b"source")
            candidate.write_bytes(b"candidate")
            metrics, gates, reasons = evaluate_visual_audit(
                private_root=root,
                source_path=source,
                candidate_path=candidate,
                producer_process_id="producer-1",
                thresholds={"status": "BLOCKED_UNTIL_CALIBRATION", "style": {"reference_set_id": "UNSET_BLOCK_EXECUTION"}},
                threshold_issues=["thresholds are not approved"],
            )
            self.assertEqual(metrics["visual_audit_status"], "UNCERTAIN")
            self.assertEqual(set(gates.values()), {"UNCERTAIN"})
            self.assertIn("private visual audit evidence is missing", reasons)

    def test_visual_audit_pass_maps_only_after_approved_threshold_and_hash_checks(self):
        from datetime import datetime, timezone
        from portrait_pipeline.util import sha256_file
        from portrait_pipeline.visual_audit import evaluate_visual_audit

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.png"
            candidate = root / "candidate.png"
            source.write_bytes(b"source")
            candidate.write_bytes(b"candidate")
            evidence_path = root / "evidence/audit/visual_audit.json"
            evidence_path.parent.mkdir(parents=True)
            evidence_path.write_text(json.dumps({
                "schema_version": "1.0.0",
                "status": "PASS",
                "auditor": {"process_id": "auditor-2", "independent_from_producer": True, "reviewed_at": datetime.now(timezone.utc).isoformat()},
                "model": {"name": "test-visual-rubric", "revision": "test-revision", "artifact_sha256": "a" * 64},
                "reference_set": {"id": "country-leader-style-v1", "role": "country_leader", "manifest_sha256": "b" * 64, "sample_count": 4},
                "source_sha256": sha256_file(source),
                "candidate_sha256": sha256_file(candidate),
                "scores": {"hairline": 0.91, "facial_hair": 0.88, "accessories": 0.93, "style": 0.86},
                "human_readable_evidence": {
                    "hairline": "Hairline silhouette and parting agree with the source.",
                    "facial_hair": "Facial-hair presence and boundaries agree with the source.",
                    "accessories": "No source-visible accessory is removed or invented.",
                    "style": "The candidate matches the approved role-specific HOI4 painted reference set.",
                },
            }), encoding="utf-8")
            metrics, gates, reasons = evaluate_visual_audit(
                private_root=root,
                source_path=source,
                candidate_path=candidate,
                producer_process_id="producer-1",
                thresholds={
                    "status": "APPROVED",
                    "thresholds_id": "calibrated-test",
                    "hair_and_accessories": {"required_attribute_agreement": 0.8},
                    "style": {"minimum_score": 0.8, "reference_set_id": "country-leader-style-v1"},
                },
                threshold_issues=[],
            )
            self.assertEqual(gates, {"hairline": "PASS", "facial_hair": "PASS", "accessories": "PASS", "style": "PASS"})
            self.assertEqual(metrics["visual_audit_reference_set_id"], "country-leader-style-v1")
            self.assertIn("Hairline silhouette", metrics["visual_audit_human_readable_evidence"])
            self.assertEqual(reasons, [])

    def test_visual_audit_producer_hashes_approved_reference_set_and_validates_model_response(self):
        from datetime import datetime, timezone
        from PIL import Image
        from portrait_pipeline.util import sha256_file
        from portrait_pipeline.visual_audit_service import VisualAuditProducer

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.png"
            candidate = root / "candidate.png"
            reference = root / "references/ref.png"
            reference.parent.mkdir(parents=True)
            Image.new("RGB", (64, 64), (20, 40, 60)).save(source)
            Image.new("RGB", (64, 64), (60, 40, 20)).save(candidate)
            Image.new("RGB", (72, 96), (30, 50, 70)).save(reference)
            manifest = root / "references/manifest.json"
            manifest.write_text(json.dumps({
                "schema_version": "1.0.0",
                "reference_set_id": "fixture-country-leader-style-v1",
                "revision": "fixture-revision",
                "role": "country_leader",
                "status": "APPROVED_PRIVATE",
                "source_class": "synthetic",
                "rights_notes": "Synthetic test-only reference.",
                "approved_by": ["test"],
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "images": [{"reference_id": "ref-1", "path": "references/ref.png", "sha256": sha256_file(reference), "width": 72, "height": 96}],
            }), encoding="utf-8")
            output = root / "evidence/audit/visual_audit.json"
            response = {"choices": [{"message": {"content": json.dumps({
                "status": "PASS",
                "scores": {"hairline": 0.9, "facial_hair": 0.9, "accessories": 0.9, "style": 0.9},
                "human_readable_evidence": {name: "visible fixture evidence" for name in ("hairline", "facial_hair", "accessories", "style")},
            })}}]}
            with mock.patch("portrait_pipeline.visual_audit_service.VisualAuditProducer.start"), mock.patch("portrait_pipeline.visual_audit_service.VisualAuditProducer.stop"), mock.patch("portrait_pipeline.visual_audit_service._post_json", return_value=response) as post:
                producer = VisualAuditProducer(root=self.root, auditor_process_id="visual-auditor-2", port=8191)
                record = producer.produce(private_root=root, source_path=source, candidate_path=candidate, reference_manifest=manifest, producer_process_id="producer-1", output_path=output)
            self.assertEqual(record["status"], "PASS")
            self.assertEqual(record["reference_set"]["sample_count"], 1)
            self.assertEqual(record["source_sha256"], sha256_file(source))
            self.assertEqual(record["candidate_sha256"], sha256_file(candidate))
            self.assertTrue(output.is_file())
            self.assertEqual(post.call_count, 1)
            content = post.call_args.args[1]["messages"][0]["content"]
            self.assertEqual(len(content), 4)
            self.assertIn("SOURCE", content[0]["text"])

    def test_full_power_visual_audit_route_fails_closed_without_cuda(self):
        from portrait_pipeline.visual_audit_service import VisualAuditProducer, VisualAuditServiceError

        lock = {
            "status": "PINNED_LOCAL_LOOPBACK_PRODUCER_EXECUTION_UNVERIFIED",
            "full_power": {"transformers_version": "5.14.1", "max_tokens": 512},
        }
        descriptor = {
            "name": "Qwen3-VL-8B-Instruct-BF16-shards",
            "revision": "test-revision",
            "artifact_sha256": "a" * 64,
            "root": self.root / "models/autoprompter",
            "loader": "transformers.Qwen3VLForConditionalGeneration",
            "processor": "transformers.AutoProcessor",
            "torch_dtype": "bfloat16",
            "device_requirement": "CUDA",
        }
        with mock.patch("portrait_pipeline.visual_audit_service._load_full_power_runtime_lock", return_value=(lock, self.root / "prompts/visual_audit_rubric.txt", self.root / "models/autoprompter", descriptor)), mock.patch("torch.cuda.is_available", return_value=False):
            producer = VisualAuditProducer(root=self.root, runtime_profile="full_power_gpu", auditor_process_id="visual-auditor-2")
            with self.assertRaises(VisualAuditServiceError):
                producer.start()

    def test_acceptance_schema_gate_includes_visual_audit_contracts(self):
        from portrait_pipeline.acceptance import _schema_gate

        result = _schema_gate(self.root)
        self.assertEqual(result["status"], "PASS")
        schemas = {item["schema"] for item in result["checked"]}
        self.assertIn("schemas/visual_audit_evidence.schema.json", schemas)
        self.assertIn("schemas/visual_reference_set.schema.json", schemas)

    def test_identity_style_matrix_execution_is_explicitly_fail_closed(self):
        from portrait_pipeline.constants import PROFILE_LIMITS
        from portrait_pipeline.experiments import build_execution_report, build_matrix

        report = build_execution_report(self.root)
        self.assertEqual(report["status"], "BLOCKED_PREREQUISITES")
        self.assertEqual(report["execution_status"], "NOT_RUN_FAIL_CLOSED")
        self.assertEqual(report["queued_jobs"], 0)
        self.assertEqual(report["candidate_count"], 0)
        self.assertEqual(report["selection_status"], "NOT_RUN")
        matrix = build_matrix()
        self.assertEqual(set(matrix["profiles"]), set(PROFILE_LIMITS))
        self.assertEqual(matrix["profiles"]["agent_full_power_gpu"]["canvas"], [1196, 1610])

    def test_production_graph_model_scope_matches_the_model_lock(self):
        lock = json.loads((self.root / "dependencies/models.lock.json").read_text(encoding="utf-8"))
        fp8 = next(model for model in lock["models"] if model["name"] == "krea2_turbo_fp8_scaled.safetensors")
        self.assertTrue(fp8["mandatory"])
        for profile in ("human_local_mac_16gb", "human_full_power_gpu", "agent_local_mac_16gb", "agent_full_power_gpu", "agent_remote_runpod"):
            self.assertIn(profile, fp8["profiles"], profile)

    def test_profile_runtime_locks_are_checksum_verified_but_live_runtime_stays_separate(self):
        for profile in ("human_local_mac_16gb", "human_full_power_gpu", "agent_local_mac_16gb", "agent_full_power_gpu", "agent_remote_runpod"):
            report = collect_preflight(self.root, profile=profile)
            gate = next(gate for gate in report["gates"] if gate["name"] == "comfyui_runtime_dependency_lock")
            self.assertEqual(gate["status"], "PASS", gate)
            self.assertEqual(gate["evidence"]["mode"], "profile_locks")
            self.assertEqual(gate["evidence"]["project_lock"]["status"], "PASS", gate)

    def test_benchmark_and_comparison_reports_never_claim_generation_without_evidence(self):
        from portrait_pipeline.benchmarks import build_benchmark_report
        from portrait_pipeline.comparisons import build_comparison_report

        benchmark = build_benchmark_report(self.root, "agent_local_mac_16gb")
        self.assertNotEqual(benchmark["status"], "PASS")
        self.assertEqual(benchmark["claims"]["final_png"], "NOT_CREATED")
        self.assertEqual(benchmark["measurements"]["generation"]["status"], "PASS_EXECUTION_ONLY_PRODUCTION_BLOCKED")
        self.assertEqual(benchmark["measurements"]["generation"]["candidate_count"], 1)
        comparison = build_comparison_report(self.root)
        self.assertIn(comparison["status"], {"BLOCKED_NO_REAL_CANDIDATES", "BLOCKED_DIAGNOSTIC_CANDIDATES_NOT_PRODUCTION_AUTHORIZED"})
        self.assertGreaterEqual(comparison["candidate_counts"]["observed"], 0)
        self.assertIsNone(comparison["claims"]["identity_winner"])

    def test_runpod_surface_is_fail_closed_and_keeps_raw_comfy_loopback(self):
        image_lock = json.loads((self.root / "deploy/runpod/image_lock.json").read_text(encoding="utf-8"))
        dockerfile = (self.root / "deploy/runpod/Dockerfile").read_text(encoding="utf-8")
        gateway = (self.root / "src/portrait_pipeline/mcp/gateway.py").read_text(encoding="utf-8")
        self.assertFalse(image_lock["build_permitted"])
        self.assertTrue(image_lock["base_image"]["reference"].startswith("nvidia/cuda:"))
        self.assertIn("127.0.0.1", dockerfile)
        self.assertIn("IMAGE_LOCK_STATUS", dockerfile)
        self.assertIn("COPY . /opt/portrait-project/", dockerfile)
        self.assertIn("project_requirements.lock.txt", (self.root / "deploy/runpod/install_runtime.sh").read_text(encoding="utf-8"))
        for route in ("/v1/uploads", "/v1/jobs", "/v1/capabilities"):
            self.assertIn(route, (self.root / "deploy/runpod/README.md").read_text(encoding="utf-8"))
        self.assertIn("agent_remote_runpod", gateway)
        self.assertIn("arbitrary ComfyUI workflow submission", (self.root / "deploy/runpod/README.md").read_text(encoding="utf-8"))

    def test_remote_adapter_errors_use_authenticated_machine_contract(self):
        service = PortraitMcpService(self.root, remote=True)
        with self.assertRaises(AdapterError) as context:
            service.call("portrait_health")
        error = context.exception.as_error()
        self.assertFalse(error["ok"])
        self.assertEqual(error["error"]["code"], "REMOTE_AUTH_OR_TRANSPORT_FAILED")
        self.assertIn("retryable", error["error"])
        self.assertIn("stage", error["error"])

    def test_rest_gateway_auth_upload_and_idempotency(self):
        import hashlib
        import io
        import threading
        import urllib.error
        import urllib.request
        from http.server import ThreadingHTTPServer
        from PIL import Image

        from portrait_pipeline.mcp.gateway import PortraitGateway, _GatewayHandler

        with tempfile.TemporaryDirectory() as directory, mock.patch.dict("os.environ", {"PORTRAIT_GATEWAY_TOKEN": "unit-token"}):
            root = Path(directory)
            (root / "schemas").symlink_to(self.root / "schemas", target_is_directory=True)
            service = PortraitMcpService(root, remote=True)
            application = PortraitGateway(root, service=service)
            _GatewayHandler.application = application
            server = ThreadingHTTPServer(("127.0.0.1", 0), _GatewayHandler)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                image_buffer = io.BytesIO()
                Image.new("RGBA", (2, 2), (1, 2, 3, 255)).save(image_buffer, format="PNG")
                image_bytes = image_buffer.getvalue()
                digest = hashlib.sha256(image_bytes).hexdigest()

                with self.assertRaises(urllib.error.HTTPError) as unauthorized:
                    urllib.request.urlopen(urllib.request.Request(base + "/v1/health"), timeout=5)
                self.assertEqual(unauthorized.exception.code, 401)

                headers = {"Authorization": "Bearer unit-token", "Content-Type": "application/json", "Idempotency-Key": "upload-key-001"}
                metadata = {"job_id": "gateway-test-001", "filename": "source.png", "mime_type": "image/png", "size_bytes": len(image_bytes), "sha256": digest}
                request = urllib.request.Request(base + "/v1/uploads", data=json.dumps(metadata).encode("utf-8"), headers=headers, method="POST")
                with urllib.request.urlopen(request, timeout=5) as response:
                    upload = json.loads(response.read().decode("utf-8"))
                    self.assertEqual(response.status, 201)
                upload_id = upload["upload_id"]
                put_headers = {"Authorization": "Bearer unit-token", "X-Portrait-Job-Id": "gateway-test-001", "Content-Type": "image/png", "Content-SHA256": digest}
                request = urllib.request.Request(base + f"/v1/uploads/{upload_id}", data=image_bytes, headers=put_headers, method="PUT")
                with urllib.request.urlopen(request, timeout=5) as response:
                    uploaded = json.loads(response.read().decode("utf-8"))
                self.assertEqual(uploaded["state"], "UPLOADED")
                request = urllib.request.Request(base + "/v1/uploads", data=json.dumps(metadata).encode("utf-8"), headers=headers, method="POST")
                with urllib.request.urlopen(request, timeout=5) as response:
                    repeated = json.loads(response.read().decode("utf-8"))
                self.assertEqual(repeated["upload_id"], upload_id)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=5)

    def test_adapter_rejects_non_object_stdio_requests_without_crashing(self):
        import io
        from contextlib import redirect_stdout
        from portrait_pipeline.mcp.adapter import serve_stdio

        stream = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO("[1,2,3]\n")), redirect_stdout(stream):
            self.assertEqual(serve_stdio(PortraitMcpService(self.root)), 0)
        response = json.loads(stream.getvalue())
        self.assertEqual(response["result"]["error"]["code"], "INPUT_SCHEMA_INVALID")

    def test_dds_promotion_is_blocked_without_audit_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit_path = root / "audit.json"
            audit_path.write_text(json.dumps(independent_audit_blocked("fixture-001", "candidate-000")), encoding="utf-8")
            with self.assertRaises(DdsValidationError):
                convert_png_to_dds(root / "missing.png", root / "final.dds", audit_path, self.root)

    def test_promotion_predicate_rejects_forged_pass_without_production_proof(self):
        audit = independent_audit_blocked("fixture-guard", "candidate-guard")
        audit["verdict"] = "PASS"
        audit["hard_gates"] = {key: "PASS" for key in audit["hard_gates"]}
        self.assertFalse(audit_is_promotion_pass(audit))

    def test_dds_round_trip_uses_locked_header_contract(self):
        from PIL import Image  # type: ignore

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            png_path = root / "candidate.png"
            dds_path = root / "candidate.dds"
            Image.new("RGBA", (156, 210), (12, 34, 56, 255)).save(png_path, format="PNG")
            audit = independent_audit_blocked("fixture-002", "candidate-001")
            audit["thresholds_id"] = "synthetic-acceptance-only"
            audit["verdict"] = "PASS"
            audit["hard_gates"] = {key: "PASS" for key in audit["hard_gates"]}
            audit["metrics"]["audit_mode"] = "synthetic_test"
            audit_path = root / "audit-pass.json"
            audit_path.write_text(json.dumps(audit), encoding="utf-8")
            report = convert_png_to_dds(png_path, dds_path, audit_path, self.root, allow_synthetic_test=True)
            self.assertEqual(report["size_bytes"], 131168)
            self.assertEqual(report["header"]["fourcc"], "0x00000000")
            self.assertEqual(report["pixel_round_trip"], "PASS")
            self.assertEqual(report["independent_decoder"], "PASS_PROJECT_SECOND_DECODER")


if __name__ == "__main__":
    unittest.main()
