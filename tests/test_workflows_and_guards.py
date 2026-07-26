from __future__ import annotations

import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from portrait_pipeline.audit import independent_audit_blocked
from portrait_pipeline.dds import DdsValidationError, convert_png_to_dds
from portrait_pipeline.graph_spec.builder import build_workflow_artifacts
from portrait_pipeline.mcp.adapter import AdapterError, PortraitMcpService
from portrait_pipeline.preflight import _model_artifact_preflight, collect_preflight
from portrait_pipeline.workflow_validation import validate_all_workflows
from portrait_pipeline.util import project_root
from comfyui_hoi4_portrait_nodes import NODE_CLASS_MAPPINGS


class WorkflowAndGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = project_root()
        build_workflow_artifacts(cls.root)

    def test_four_workflows_are_structurally_valid(self):
        reports = validate_all_workflows(self.root)
        self.assertEqual(len(reports), 4)
        for report in reports:
            self.assertEqual(report["structural_status"], "PASS", report)

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
        self.assertEqual(review["status"], "BLOCKED_PINNED_CORE_SCHEMA_UNVERIFIED")
        self.assertEqual(next(item["status"] for item in review["findings"] if item["id"] == "pinned_core_loader_type"), "BLOCKED")
        for path in self.root.joinpath("workflows").glob("**/*.api.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            patch_inputs = data["14"]["inputs"]
            self.assertEqual(patch_inputs["vae"], ["12", 0])
            self.assertEqual(patch_inputs["source_image"], ["8", 1])
            self.assertEqual(data["16"]["inputs"]["grounding_px"], 768)
            self.assertEqual(data["17"]["inputs"]["grounding_px"], 768)

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
        self.assertEqual(next(g["status"] for g in remote["gates"] if g["name"] == "remote_topology_auth"), "BLOCKED")

    def test_remote_adapter_errors_use_authenticated_machine_contract(self):
        service = PortraitMcpService(self.root, remote=True)
        with self.assertRaises(AdapterError) as context:
            service.call("portrait_health")
        error = context.exception.as_error()
        self.assertFalse(error["ok"])
        self.assertEqual(error["error"]["code"], "REMOTE_AUTH_OR_TRANSPORT_FAILED")
        self.assertIn("retryable", error["error"])
        self.assertIn("stage", error["error"])

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

    def test_dds_round_trip_uses_locked_header_contract(self):
        from PIL import Image  # type: ignore

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            png_path = root / "candidate.png"
            dds_path = root / "candidate.dds"
            Image.new("RGBA", (156, 210), (12, 34, 56, 255)).save(png_path, format="PNG")
            audit = independent_audit_blocked("fixture-002", "candidate-001")
            audit["thresholds_id"] = "test-calibrated"
            audit["verdict"] = "PASS"
            audit["hard_gates"] = {key: "PASS" for key in audit["hard_gates"]}
            audit_path = root / "audit-pass.json"
            audit_path.write_text(json.dumps(audit), encoding="utf-8")
            report = convert_png_to_dds(png_path, dds_path, audit_path, self.root)
            self.assertEqual(report["size_bytes"], 131168)
            self.assertEqual(report["header"]["fourcc"], "0x00000000")
            self.assertEqual(report["pixel_round_trip"], "PASS")


if __name__ == "__main__":
    unittest.main()
