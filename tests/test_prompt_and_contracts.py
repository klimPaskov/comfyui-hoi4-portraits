from __future__ import annotations

import unittest

from portrait_pipeline.constants import ExitCode
from portrait_pipeline.contracts import validate_schema
from portrait_pipeline.prompt import validate_prompt
from portrait_pipeline.util import project_root


class PromptAndContractTests(unittest.TestCase):
    def test_exact_trigger_and_valid_description(self):
        result = validate_prompt("hoi4_portrait, a middle-aged person with short hair, glasses, and a neutral expression")
        self.assertTrue(result.passed, result.as_dict())

    def test_prohibited_terms_are_rejected_without_rewrite(self):
        result = validate_prompt("hoi4_portrait, a man in a studio with dramatic lighting")
        self.assertFalse(result.passed)
        self.assertIsNone(result.normalized_prompt)
        self.assertIn("AUTOPROMPT_PROHIBITED_CONTENT", result.failure_codes)

    def test_name_leak_is_rejected(self):
        result = validate_prompt("hoi4_portrait, John Example with a neutral expression", record_name="John Example")
        self.assertFalse(result.passed)
        self.assertIn("AUTOPROMPT_NAME_LEAK", result.failure_codes)

    def test_input_schema_has_strict_profile_enum(self):
        root = project_root()
        valid = {
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
        }
        self.assertEqual(validate_schema(valid, root / "schemas/portrait_job_input.schema.json"), [])
        invalid = dict(valid)
        invalid["execution_profile"] = "unsupported"
        self.assertTrue(validate_schema(invalid, root / "schemas/portrait_job_input.schema.json"))


if __name__ == "__main__":
    unittest.main()

