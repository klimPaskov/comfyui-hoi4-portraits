from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from portrait_pipeline.audit import independent_audit_blocked
from portrait_pipeline.dds import DdsValidationError, convert_png_to_dds
from portrait_pipeline.graph_spec.builder import build_workflow_artifacts
from portrait_pipeline.workflow_validation import validate_all_workflows
from portrait_pipeline.util import project_root


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
            self.assertEqual(data["_meta"]["prompt_source"], "job_contract")

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
