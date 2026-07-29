from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from portrait_pipeline.constants import ExitCode
from portrait_pipeline.contracts import validate_schema
from portrait_pipeline.autoprompter_service import AUTOPROMPTER_RETRY_PROFILES, AutoprompterService, AutoprompterServiceError
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

    def test_explicit_uniform_claims_can_be_authorized_without_allowing_nationality(self):
        result = validate_prompt(
            "hoi4_portrait, a military officer wearing a uniform with insignia",
            allowed_claims={
                "roles": ["officer"],
                "medals_or_insignia": ["insignia"],
                "organization_or_branch": ["uniform", "military"],
                "jewelry": ["jewelry"],
            },
        )
        self.assertTrue(result.passed, result.as_dict())
        nationality = validate_prompt(
            "hoi4_portrait, an American military officer",
            allowed_claims={"roles": ["officer"], "organization_or_branch": ["military"]},
        )
        self.assertFalse(nationality.passed)
        self.assertIn("AUTOPROMPT_UNVERIFIED_CLAIM", nationality.failure_codes)

    def test_input_schema_has_strict_profile_enum(self):
        root = project_root()
        valid = {
            "schema_version": "1.0.0",
            "job_id": "fixture-001",
            "execution_profile": "hoi4_portraits_agent_local_nvidia_16gb",
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
            "allowed_autoprompt_claims": {
                "roles": ["officer"],
                "organization_or_branch": ["uniform"],
            },
        }
        self.assertEqual(validate_schema(valid, root / "docs/schemas/portrait_job_input.schema.json"), [])
        invalid = dict(valid)
        invalid["execution_profile"] = "unsupported"
        self.assertTrue(validate_schema(invalid, root / "docs/schemas/portrait_job_input.schema.json"))

    def test_prompt_job_schema_requires_an_agent_prompt_profile_without_a_source_image(self):
        root = project_root()
        valid = {
            "schema_version": "1.0.0",
            "job_id": "prompt-job-001",
            "execution_profile": "hoi4_portraits_agent_no_input_local_nvidia_16gb",
            "prompt": "hoi4_portrait, a fictional civilian leader with short hair and a neutral expression",
            "seed_policy": {"mode": "derived"},
            "candidate_count": 1,
            "retry_limit": 0,
            "final_output_stem": "fictional_leader_001",
        }
        schema = root / "docs/schemas/portrait_prompt_job_input.schema.json"
        self.assertEqual(validate_schema(valid, schema), [])
        invalid = dict(valid)
        invalid["execution_profile"] = "hoi4_portraits_no_input_local_nvidia_16gb"
        self.assertTrue(validate_schema(invalid, schema))

    def test_autoprompter_retries_decoding_only_and_records_bounded_attempts(self):
        instruction = (project_root() / "prompts/autoprompter_instruction.txt").read_text(encoding="utf-8")
        service = object.__new__(AutoprompterService)
        service.root = Path(tempfile.mkdtemp(prefix="hoi4-autoprompt-test-"))
        service.profile = "hoi4_portraits_local_nvidia_16gb"
        service.model_id = "Qwen/Qwen3-VL-4B-Instruct-GGUF"
        service.instruction = instruction
        service.upstream_port = 1
        service.lock = {"local_profile": {"max_tokens": 256}}
        png_value = base64.b64encode(b"\x89PNG\r\n\x1a\nunit-test").decode("ascii")
        responses = [
            {"choices": [{"message": {"content": "hoi4_portrait, an American officer with a neutral expression"}}]},
            {"choices": [{"message": {"content": "hoi4_portrait, a person with short hair and a neutral expression"}}]},
        ]
        try:
            with mock.patch("portrait_pipeline.autoprompter_service._post_json", side_effect=responses) as post:
                result = service.complete({"job_id": "retry-test-001", "model_id": service.model_id, "instruction": instruction, "image_png_base64": png_value})
            self.assertEqual(result["prompt"], "hoi4_portrait, a person with short hair and a neutral expression")
            self.assertEqual(len(result["attempts"]), 2)
            self.assertEqual(result["attempts"][0]["status"], "REJECTED")
            self.assertEqual(result["attempts"][1]["status"], "PASS")
            self.assertEqual([call.kwargs["timeout"] for call in post.call_args_list], [180, 180])
            payloads = [call.args[1] for call in post.call_args_list]
            self.assertEqual([payload["messages"] for payload in payloads], [payloads[0]["messages"]] * 2)
            self.assertEqual([payload["messages"][0]["content"][1]["image_url"]["url"] for payload in payloads], ["data:image/png;base64," + png_value] * 2)
            self.assertEqual([(payload["temperature"], payload["seed"]) for payload in payloads], [(0.0, 0), (0.1, 17)])
            attempt_path = service.root / "jobs/retry-test-001/evidence/prompt/autoprompter_attempts.json"
            self.assertTrue(attempt_path.is_file())
            self.assertEqual(len(__import__("json").loads(attempt_path.read_text(encoding="utf-8"))["attempts"]), 2)
        finally:
            import shutil

            shutil.rmtree(service.root)

    def test_autoprompter_rejects_after_exactly_three_attempts(self):
        instruction = (project_root() / "prompts/autoprompter_instruction.txt").read_text(encoding="utf-8")
        service = object.__new__(AutoprompterService)
        service.root = Path(tempfile.mkdtemp(prefix="hoi4-autoprompt-test-"))
        service.profile = "hoi4_portraits_local_nvidia_16gb"
        service.model_id = "Qwen/Qwen3-VL-4B-Instruct-GGUF"
        service.instruction = instruction
        service.upstream_port = 1
        service.lock = {"local_profile": {"max_tokens": 256}}
        png_value = base64.b64encode(b"\x89PNG\r\n\x1a\nunit-test").decode("ascii")
        response = {"choices": [{"message": {"content": "hoi4_portrait, an American officer with a neutral expression"}}]}
        try:
            with mock.patch("portrait_pipeline.autoprompter_service._post_json", return_value=response) as post:
                with self.assertRaises(AutoprompterServiceError) as context:
                    service.complete({"job_id": "retry-test-002", "model_id": service.model_id, "instruction": instruction, "image_png_base64": png_value})
            self.assertEqual(len(context.exception.attempts), len(AUTOPROMPTER_RETRY_PROFILES))
            self.assertEqual(post.call_count, len(AUTOPROMPTER_RETRY_PROFILES))
            self.assertTrue(all(item["status"] == "REJECTED" for item in context.exception.attempts))
        finally:
            import shutil

            shutil.rmtree(service.root)


if __name__ == "__main__":
    unittest.main()
