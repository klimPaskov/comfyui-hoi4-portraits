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
        self.assertEqual(len(reports), 11)
        for report in reports:
            self.assertEqual(report["structural_status"], "PASS", report)

    def test_workflow_manifest_is_structural_and_fail_closed(self):
        manifest = json.loads((self.root / "docs/reference/workflow_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "UNVALIDATED")
        self.assertIn(
            manifest["runtime_status"],
            {"STRUCTURAL_ONLY_RUNTIME_BLOCKED", "LIVE_SCHEMA_LOADABLE_EXECUTION_BLOCKED"},
        )
        self.assertEqual(len(manifest["workflows"]), 11)
        self.assertTrue(all(item["validation_status"] == "UNVALIDATED" for item in manifest["workflows"]))

    def test_local_nvidia_agent_is_routable_through_controller_and_adapter(self):
        controller_path = JobController(self.root)._workflow_api_path("hoi4_portraits_agent_local_nvidia_16gb")
        adapter_path = PortraitMcpService(self.root)._workflow_path("hoi4_portraits_agent_local_nvidia_16gb")
        self.assertEqual(controller_path, adapter_path)
        self.assertTrue(controller_path.is_file())

    def test_local_generation_unavailable_is_explicit_and_never_remote(self):
        controller = JobController(self.root)
        job = {"job_id": "local-unavailable-001", "execution_profile": "hoi4_portraits_local_nvidia_16gb"}
        output = build_blocked_output(job, ExitCode.DEPENDENCY_MISSING, "measured local memory blocker", blockers=["local runtime canary blocked"], root=self.root)
        with tempfile.TemporaryDirectory() as directory:
            job_root = Path(directory) / "job"
            job_root.mkdir()
            controller._record_local_generation_unavailable(job, job_root, output, stage="JOB_ACCEPTED")
            marker = json.loads((job_root / "local_generation_unavailable.json").read_text(encoding="utf-8"))
            self.assertEqual(marker["status"], LOCAL_GENERATION_UNAVAILABLE)
            self.assertEqual(marker["remote_submission"], "NOT_QUEUED_BY_LOCAL_ROUTE")
            self.assertEqual(output["error_code"], LOCAL_GENERATION_UNAVAILABLE)
            self.assertIn(LOCAL_GENERATION_UNAVAILABLE, output["warnings"])
            self.assertEqual(validate_schema(output, self.root / "docs/schemas/portrait_job_output.schema.json"), [])

            remote_job = {"job_id": "remote-unavailable-001", "execution_profile": "hoi4_portraits_agent_full_power_gpu"}
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
            if data["_meta"].get("workflow_kind") in {"random_text_to_image", "portrait_preparation"}:
                continue
            ui_path = path.with_name(path.name.replace(".api.json", ".json"))
            values = [node.get("widgets_values", []) for node in json.loads(ui_path.read_text(encoding="utf-8")).get("nodes", []) if node.get("type") == "HOI4AutopromptClient"]
            self.assertEqual(values[0][0], "Create automatically")
            self.assertEqual(values[0][2], instruction)
            self.assertEqual(data["9"]["inputs"]["description_mode"], "Create automatically")
            self.assertEqual(data["9"]["inputs"]["manual_description"], "")
            self.assertEqual(data["_meta"]["autoprompter"], True)

    def test_human_autoprompter_can_be_switched_to_an_unrestricted_manual_description(self):
        instruction = (self.root / "prompts/autoprompter_instruction.txt").read_text(encoding="utf-8")
        job = {
            "job_id": "manual-description-test",
            "execution_profile": "hoi4_portraits_local_nvidia_16gb",
            "_project_root": str(self.root),
            "subject_identity": {},
            "allowed_autoprompt_claims": {},
        }
        with mock.patch("comfyui_hoi4_portrait_nodes.nodes.atomic_json_write"):
            prompt, metadata = NODE_CLASS_MAPPINGS["HOI4AutopromptClient"]().run(
                job,
                None,
                {},
                {},
                "Use my description",
                "British officer with a period banner behind him",
                instruction,
                "prompts/autoprompter_instruction.txt",
                "Qwen/Qwen3-VL-4B-Instruct-GGUF",
                "autoprompter",
            )
        self.assertEqual(
            prompt,
            "hoi4_portrait, British officer with a period banner behind him",
        )
        self.assertEqual(metadata["source"], "human_manual_override")

    def test_prompt_instructions_do_not_steer_symbol_or_flag_usage(self):
        for relative in (
            "prompts/autoprompter_instruction.txt",
            "prompts/random_portrait_instruction.txt",
        ):
            text = (self.root / relative).read_text(encoding="utf-8").casefold()
            self.assertNotIn("flag", text)
            self.assertNotIn("symbol", text)

    def test_agent_workflows_have_no_autoprompter(self):
        for path in (self.root / "workflows/agent").glob("**/*.api.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("HOI4AutopromptClient", json.dumps(data))
            self.assertNotIn("HOI4HumanControls", json.dumps(data))
            self.assertEqual(data["_meta"]["prompt_source"], "job_contract")

    def test_human_final_preview_shares_the_saved_image_source(self):
        for path in (self.root / "workflows/human").glob("**/*.api.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            pair = data["_meta"]["final_preview_save_pair"]
            if data["_meta"].get("workflow_kind") == "portrait_preparation":
                preview_id = str(pair["preview_node_id"])
                save_id = str(pair["save_node_id"])
                source = [str(pair["shared_source_node_id"]), 0]
                self.assertEqual(data[preview_id]["inputs"]["images"], source)
                self.assertEqual(data[save_id]["inputs"]["images"], source)
            elif data["_meta"].get("workflow_kind") == "random_text_to_image":
                self.assertEqual(data["12"]["inputs"]["images"], ["11", 0])
                self.assertEqual(data["13"]["inputs"]["images"], ["11", 0])
                self.assertEqual(pair["preview_node_id"], 12)
                self.assertEqual(pair["save_node_id"], 13)
                self.assertEqual(pair["shared_source_node_id"], 11)
            else:
                self.assertEqual(data["23"]["inputs"]["images"], ["22", 0])
                self.assertEqual(data["28"]["inputs"]["images"], ["22", 0])
                self.assertEqual(pair["preview_node_id"], 28)
                self.assertEqual(pair["save_node_id"], 23)
                self.assertEqual(pair["shared_source_node_id"], 22)
        for path in (self.root / "workflows/agent").glob("**/*.api.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIsNone(data["_meta"]["final_preview_save_pair"]["preview_node_id"])

    def test_workflow_titles_are_user_facing_and_human_previews_are_large(self):
        forbidden_title_terms = ("human-only", "exact", "candidate")
        for path in self.root.joinpath("workflows").glob("**/*.json"):
            if path.name.endswith(".api.json"):
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            titles = [str(node.get("title", "")) for node in data.get("nodes", [])]
            for title in titles:
                self.assertFalse(any(term in title.casefold() for term in forbidden_title_terms), (path, title))
        for path in self.root.joinpath("workflows/human").glob("**/*.json"):
            if path.name.endswith(".api.json"):
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            api = json.loads(path.with_suffix(".api.json").read_text(encoding="utf-8"))
            previews = {node["id"]: node for node in data["nodes"] if node.get("type") == "PreviewImage"}
            if api["_meta"].get("workflow_kind") == "portrait_preparation":
                expected = (
                    {2, 4, 18, 19}
                    if api["_meta"]["enhancement_mode"] == "krea2_edit"
                    else {2, 4, 17, 21, 22}
                    if api["_meta"]["enhancement_mode"] == "qwen_image_edit"
                    else {2, 4, 6}
                )
                self.assertEqual(set(previews), expected)
                self.assertTrue(all(node["size"][0] >= 340 and node["size"][1] >= 340 for node in previews.values()))
                continue
            if api["_meta"].get("workflow_kind") == "random_text_to_image":
                self.assertEqual(set(previews), {12})
                self.assertGreaterEqual(previews[12]["size"][0], 300)
                self.assertGreaterEqual(previews[12]["size"][1], 300)
                continue
            expected = {25, 26, 27, 28, 30, 35, 38}
            if api["_meta"].get("preparation_engine") == "krea2_edit_restoration":
                expected.add(54)
            self.assertEqual(set(previews), expected)
            self.assertTrue(all(node["size"][0] >= 300 and node["size"][1] >= 300 for node in previews.values()))
            self.assertEqual(api["30"]["inputs"]["images"], ["3", 0])
            for node_id in (25, 26, 27, 30, 35, 38):
                self.assertGreaterEqual(previews[node_id]["size"][0], 340)
                self.assertGreaterEqual(previews[node_id]["size"][1], 400)
            self.assertGreaterEqual(previews[28]["size"][0], 400)
            self.assertGreaterEqual(previews[28]["size"][1], 500)

    def test_workflow_layout_uses_aligned_symmetric_columns(self):
        for path in self.root.joinpath("workflows").glob("**/*.json"):
            if path.name.endswith(".api.json"):
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            nodes = {node["id"]: node for node in data["nodes"]}
            if data.get("extra", {}).get("workflow_kind") in {"random_text_to_image", "portrait_preparation"}:
                continue
            self.assertEqual(nodes[5]["size"], nodes[6]["size"], path)
            self.assertEqual(nodes[10]["size"], nodes[14]["size"], path)
            self.assertEqual(nodes[11]["size"], nodes[15]["size"], path)
            self.assertEqual(nodes[12]["size"], nodes[16]["size"], path)
            self.assertEqual(nodes[13]["size"], nodes[17]["size"], path)
            self.assertEqual(nodes[10]["pos"][1], nodes[14]["pos"][1], path)
            self.assertEqual(nodes[11]["pos"][1], nodes[15]["pos"][1], path)
            self.assertEqual(nodes[12]["pos"][1], nodes[16]["pos"][1], path)
            self.assertEqual(nodes[13]["pos"][1], nodes[17]["pos"][1], path)

    def test_public_evidence_redacts_host_local_paths(self):
        sanitized = sanitize_public_paths({"root": str(self.root), "external": "/Users/example/private/source.png"}, self.root)
        self.assertEqual(sanitized["root"], "<project-root>")
        self.assertEqual(sanitized["external"], "<local-path>")

    def test_human_workflows_expose_controls_and_project_node_signatures_match(self):
        for path in (self.root / "workflows/human").glob("**/*.api.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data["_meta"].get("workflow_kind") == "portrait_preparation":
                self.assertIn("HOI4PortraitCrop", json.dumps(data))
                self.assertNotIn("DDColor_Colorize", json.dumps(data))
                if data["_meta"]["enhancement_mode"] == "qwen_image_edit":
                    self.assertIn("UpscaleModelLoader", json.dumps(data))
                    self.assertIn("ImageUpscaleWithModel", json.dumps(data))
                    self.assertIn("TextEncodeQwenImageEditPlus", json.dumps(data))
                elif data["_meta"]["enhancement_mode"] == "krea2_edit":
                    self.assertIn("Krea2EditModelPatch", json.dumps(data))
                    self.assertIn("Krea2EditGroundedEncode", json.dumps(data))
                self.assertNotIn("HOI4HumanControls", json.dumps(data))
                continue
            if data["_meta"].get("workflow_kind") == "random_text_to_image":
                self.assertIn("HOI4RandomPortraitPrompt", json.dumps(data))
                self.assertNotIn("HOI4HumanControls", json.dumps(data))
                continue
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

    def test_human_source_workflows_offer_the_local_hoi4_backgrounds(self):
        expected_scientist_sha = "552ce50cd0f04327ebcc7dd20ac8be24141641451ef46595e3c0f4327153139e"
        expected_operative_sha = "b3ad16dae595837fc94376d6d27bf9d3d06776ca984695e107197ff74d66dd0d"
        self.assertFalse((self.root / "backgrounds/bundled/scientist_laboratory_cc0.jpg").exists())
        registry = json.loads((self.root / "config/background_registry.json").read_text(encoding="utf-8"))
        scientist = next(
            item
            for item in registry["backgrounds"]
            if item["registry_id"] == "hoi4_scientist_portrait_background"
        )
        self.assertEqual(scientist["sha256"], expected_scientist_sha)
        self.assertEqual(scientist["source_path"], "tools/art/scientists_BG.png")
        self.assertEqual(scientist["runtime_path"], "backgrounds/local/hoi4_scientists_BG.png")
        self.assertEqual(scientist["redistribution_rule"], "local_copy_only")
        self.assertEqual(scientist["status"], "APPROVED_LOCAL_COPY_REQUIRED")
        operative = next(
            item
            for item in registry["backgrounds"]
            if item["registry_id"] == "hoi4_operative_portrait_background"
        )
        self.assertEqual(operative["sha256"], expected_operative_sha)
        self.assertEqual(operative["source_path"], "tools/art/portrait_operative_background.png")
        self.assertEqual(operative["runtime_path"], "backgrounds/local/hoi4_operative_background.png")
        self.assertEqual(operative["redistribution_rule"], "local_copy_only")
        self.assertEqual(operative["status"], "APPROVED_LOCAL_COPY_REQUIRED")

        for path in (
            self.root / "workflows/human/local_nvidia_16gb/hoi4_portraits_local_nvidia_16gb.api.json",
            self.root / "workflows/human/full_power_gpu/hoi4_portraits_full_power_gpu.api.json",
        ):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["24"]["inputs"]["background_choice"], "Keep current background")
            self.assertEqual(data["34"]["class_type"], "HOI4BundledBackground")
            self.assertEqual(data["34"]["inputs"]["asset_sha256"], expected_scientist_sha)
            self.assertEqual(data["37"]["class_type"], "HOI4BundledBackground")
            self.assertEqual(data["37"]["inputs"]["asset_sha256"], expected_operative_sha)
            self.assertEqual(data["8"]["inputs"]["scientist_background"], ["34", 0])
            self.assertEqual(data["8"]["inputs"]["scientist_background_meta"], ["34", 1])
            self.assertEqual(data["8"]["inputs"]["operative_background"], ["37", 0])
            self.assertEqual(data["8"]["inputs"]["operative_background_meta"], ["37", 1])
            self.assertEqual(data["35"]["inputs"]["images"], ["34", 0])
            self.assertEqual(data["38"]["inputs"]["images"], ["37", 0])

    def test_every_source_workflow_includes_automatic_portrait_preparation(self):
        paths = (
            self.root / "workflows/human/local_nvidia_16gb/hoi4_portraits_local_nvidia_16gb.api.json",
            self.root / "workflows/human/full_power_gpu/hoi4_portraits_full_power_gpu.api.json",
            self.root / "workflows/agent/local_nvidia_16gb/hoi4_portraits_agent_local_nvidia_16gb.api.json",
            self.root / "workflows/agent/full_power_gpu/hoi4_portraits_agent_full_power_gpu.api.json",
        )
        for path in paths:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data["_meta"]["preparation_engine"] == "krea2_edit_restoration":
                self.assertEqual(data["42"]["class_type"], "Krea2EditModelPatch")
                self.assertEqual(data["42"]["inputs"]["source_image"], ["5", 0])
                self.assertEqual(data["43"]["class_type"], "Krea2EditGroundedEncode")
                self.assertEqual(data["46"]["class_type"], "KSampler")
                self.assertEqual(data["47"]["class_type"], "VAEDecode")
                self.assertEqual(data["6"]["inputs"]["enhanced_image"], ["47", 0])
                self.assertTrue(data["_meta"]["colorization"])
                self.assertNotIn("qwen_image_edit_2511_fp8mixed.safetensors", json.dumps(data))
            else:
                self.assertEqual(data["36"]["class_type"], "UpscaleModelLoader")
                self.assertEqual(data["36"]["inputs"]["model_name"], "RealESRGAN_x2plus.pth")
                self.assertEqual(data["39"]["class_type"], "ImageUpscaleWithModel")
                self.assertEqual(data["39"]["inputs"]["image"], ["5", 0])
                self.assertEqual(data["39"]["inputs"]["upscale_model"], ["36", 0])
                self.assertEqual(data["6"]["inputs"]["enhanced_image"], ["39", 0])
                self.assertFalse(data["_meta"]["colorization"])

    def test_random_prompt_builder_is_text_only_and_repeatable(self):
        from comfyui_hoi4_portrait_nodes import NODE_CLASS_MAPPINGS

        instruction = (self.root / "prompts/random_portrait_instruction.txt").read_text(encoding="utf-8")
        node = NODE_CLASS_MAPPINGS["HOI4RandomPortraitPrompt"]()
        arguments = {
            "prompt_mode": "Create a random portrait",
            "manual_prompt": "",
            "character_brief": "random British officers with round glasses",
            "country_influence": "random",
            "role": "random",
            "presentation": "random",
            "age": "random",
            "expression": "random",
            "seed": 42,
            "instruction_text": instruction,
            "instruction_path": "prompts/random_portrait_instruction.txt",
        }
        with mock.patch.dict("os.environ", {"HOI4_PORTRAIT_PROJECT_ROOT": str(self.root)}):
            first = node.run(**arguments)
            second = node.run(**arguments)
        self.assertEqual(first, second)
        self.assertTrue(first[0].startswith("hoi4_portrait,"))
        self.assertIn("round glasses", first[0])
        self.assertIn("British officers", first[0])
        self.assertNotIn(first[1]["selected"]["country_influence"] + " visual influence", first[0])
        self.assertNotIn(first[1]["selected"]["role"], first[0])
        self.assertNotIn("no flag", first[0].casefold())
        self.assertNotIn("no symbol", first[0].casefold())
        self.assertFalse(first[1]["used_image"])
        self.assertFalse(first[1]["used_language_model"])

        manual_arguments = {
            **arguments,
            "prompt_mode": "Use my prompt",
            "manual_prompt": "British officers assembled for a wartime portrait",
        }
        with mock.patch.dict("os.environ", {"HOI4_PORTRAIT_PROJECT_ROOT": str(self.root)}):
            manual = node.run(**manual_arguments)
        self.assertEqual(
            manual[0],
            "hoi4_portrait, British officers assembled for a wartime portrait",
        )
        self.assertEqual(manual[1]["source"], "human_manual_prompt")

    def test_qwen_restoration_prompt_preserves_identity_and_allows_color_control(self):
        node = NODE_CLASS_MAPPINGS["HOI4RestorationPrompt"]()
        color_prompt = node.run("Restore and colorize when needed", "")[0]
        monochrome_prompt = node.run("Restore without changing color", "")[0]
        custom_prompt = node.run("Use my instructions", "Repair the torn corner only.")[0]
        for prompt in (color_prompt, monochrome_prompt, custom_prompt):
            self.assertIn("Preserve the subject's identity", prompt)
            self.assertIn("not an illustration", prompt)
        self.assertIn("colorize", color_prompt)
        self.assertIn("preserving the source image's existing", monochrome_prompt)
        self.assertTrue(custom_prompt.startswith("Repair the torn corner only."))

    def test_agent_prompt_workflow_loads_a_job_contract_without_a_source_image(self):
        job_id = "agent-prompt-test-001"
        contract_dir = self.root / "jobs" / job_id
        contract_dir.mkdir(parents=True, exist_ok=True)
        contract_path = contract_dir / "input.json"
        contract_path.write_text(json.dumps({
            "schema_version": "1.0.0",
            "job_id": job_id,
            "execution_profile": "hoi4_portraits_agent_no_input_local_nvidia_16gb",
            "prompt": "hoi4_portrait, a fictional civilian with short hair and a neutral expression",
            "seed_policy": {"mode": "derived"},
            "candidate_count": 1,
            "retry_limit": 0,
            "final_output_stem": "agent_prompt_test_001",
        }), encoding="utf-8")
        try:
            with mock.patch.dict(os.environ, {"HOI4_PORTRAIT_PROJECT_ROOT": str(self.root)}):
                job, prompt, details, seed = NODE_CLASS_MAPPINGS["HOI4PromptJobInput"]().run(
                    "hoi4_portraits_agent_no_input_local_nvidia_16gb",
                    f"jobs/{job_id}/input.json",
                    2,
                    2,
                    "derived",
                )
            self.assertEqual(job["job_id"], job_id)
            self.assertTrue(prompt.startswith("hoi4_portrait,"))
            self.assertFalse(details["source_image_required"])
            self.assertIsInstance(seed, int)
        finally:
            contract_path.unlink(missing_ok=True)
            contract_dir.rmdir()

    def test_portrait_preparation_workflow_stops_before_generation(self):
        path = self.root / "workflows/human/prepare_portrait/hoi4_portraits_prepare_portrait_for_hoi4.api.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        classes = {node["class_type"] for key, node in data.items() if not key.startswith("_")}
        self.assertTrue({
            "LoadImage", "HOI4PortraitCrop", "HOI4RestorationPrompt", "Krea2EditModelPatch",
            "Krea2EditGroundedEncode", "HOI4FinishPreparedPortrait",
            "PreviewImage", "SaveImage",
        } <= classes)
        self.assertNotIn("HOI4AutopromptClient", classes)
        self.assertEqual(data["6"]["inputs"]["unet_name"], "krea2_turbo_fp8_scaled.safetensors")
        self.assertEqual(data["10"]["inputs"]["source_image"], ["3", 0])
        self.assertEqual(data["19"]["inputs"]["images"], ["17", 0])
        self.assertEqual(data["20"]["inputs"]["images"], ["17", 0])
        self.assertTrue(data["_meta"]["colorization"])
        self.assertEqual(data["_meta"]["enhancement_mode"], "krea2_edit")

        qwen_path = self.root / "workflows/human/prepare_portrait_qwen/hoi4_portraits_prepare_portrait_qwen.api.json"
        qwen = json.loads(qwen_path.read_text(encoding="utf-8"))
        qwen_classes = {node["class_type"] for key, node in qwen.items() if not key.startswith("_")}
        self.assertTrue({
            "TextEncodeQwenImageEditPlus", "UpscaleModelLoader", "ImageUpscaleWithModel",
        } <= qwen_classes)
        self.assertEqual(qwen["7"]["inputs"]["unet_name"], "qwen_image_edit_2511_fp8mixed.safetensors")
        self.assertEqual(qwen["_meta"]["enhancement_mode"], "qwen_image_edit")
        self.assertFalse(qwen["_meta"]["default_preparation_workflow"])

        basic_path = self.root / "workflows/human/prepare_portrait_basic/hoi4_portraits_prepare_portrait_basic.api.json"
        basic = json.loads(basic_path.read_text(encoding="utf-8"))
        basic_classes = {node["class_type"] for key, node in basic.items() if not key.startswith("_")}
        self.assertTrue({"LoadImage", "HOI4PortraitCrop", "HOI4FinishPreparedPortrait", "PreviewImage", "SaveImage"} <= basic_classes)
        self.assertFalse({"UpscaleModelLoader", "ImageUpscaleWithModel", "DDColor_Colorize"} & basic_classes)
        self.assertEqual(basic["_meta"]["enhancement_mode"], "basic")

    def test_portrait_crop_is_tight_and_never_boxes_the_default_examples(self):
        import numpy as np
        import torch
        from PIL import Image

        crop_node = NODE_CLASS_MAPPINGS["HOI4PortraitCrop"]()
        for path in sorted((self.root / "docs/assets/examples").glob("preparation_*_before.*")):
            image = Image.open(path).convert("RGB")
            tensor = torch.from_numpy(np.asarray(image).astype(np.float32) / 255.0).unsqueeze(0)
            _cropped, details = crop_node.run(tensor, 0, "Normal head and shoulders")
            self.assertEqual(details["padding"], {"left": 0, "top": 0, "right": 0, "bottom": 0}, path)
            face_left, face_top, face_width, face_height = details["face_box_xywh"]
            crop_left, crop_top, crop_right, crop_bottom = details["crop_box_xyxy"]
            crop_height = crop_bottom - crop_top
            self.assertGreaterEqual(face_height / crop_height, 0.40, path)
            self.assertLessEqual(crop_left, face_left, path)
            self.assertLessEqual(crop_top, face_top, path)
            self.assertGreaterEqual(crop_right, face_left + face_width, path)
            self.assertGreaterEqual(crop_bottom, face_top + face_height, path)
            expected_headroom = min(face_top, round(face_height * 0.50))
            self.assertGreaterEqual(details["headroom_pixels"], expected_headroom - 1, path)

    def test_krea_graph_matches_primary_fit_contract(self):
        for path in self.root.joinpath("workflows").glob("**/*.api.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            if data["_meta"].get("workflow_kind") == "portrait_preparation":
                if data["_meta"].get("enhancement_mode") == "krea2_edit":
                    self.assertIn("Krea2EditModelPatch", json.dumps(data))
                    patch = data["10"]["inputs"]
                    self.assertEqual(patch["fit_mode"], "fit")
                    self.assertEqual(patch["vae"], ["8", 0])
                    self.assertEqual(patch["source_image"], ["3", 0])
                elif data["_meta"].get("enhancement_mode") == "qwen_image_edit":
                    self.assertNotIn("Krea2EditModelPatch", json.dumps(data))
                    self.assertIn("TextEncodeQwenImageEditPlus", json.dumps(data))
                    self.assertIn("KSampler", json.dumps(data))
                else:
                    self.assertNotIn("Krea2EditModelPatch", json.dumps(data))
                    self.assertNotIn("KSampler", json.dumps(data))
                continue
            if data["_meta"].get("workflow_kind") == "random_text_to_image":
                self.assertNotIn("Krea2EditModelPatch", json.dumps(data))
                self.assertNotIn("Krea2EditGroundedEncode", json.dumps(data))
                self.assertEqual(data["6"]["class_type"], "CLIPTextEncode")
                self.assertEqual(data["10"]["inputs"]["model"], ["9", 0])
                continue
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
        registry_path = self.root / "config/background_registry.json"
        original_registry = registry_path.read_text(encoding="utf-8")
        background = {
            "registry_id": "unit-test-background",
            "runtime_path": "README.md",
            "sha256": "0" * 64,
            "status": "APPROVED",
        }
        registry_path.write_text(
            json.dumps({"schema_version": "1.0.0", "registry_status": "RESOLVED", "backgrounds": [background]}),
            encoding="utf-8",
        )
        job = {
            "schema_version": "1.0.0",
            "job_id": "input-context-001",
            "execution_profile": "hoi4_portraits_local_nvidia_16gb",
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
                    "hoi4_portraits_local_nvidia_16gb",
                    "jobs/input-context-001/input.json",
                    1,
                    0,
                    "derived",
                )
            self.assertEqual(validated["job_id"], "input-context-001")
            self.assertEqual(validated["_workflow_execution_profile"], "hoi4_portraits_local_nvidia_16gb")
            self.assertEqual(validated["_project_root"], str(self.root))
        finally:
            contract_path.unlink(missing_ok=True)
            contract_dir.rmdir()
            registry_path.write_text(original_registry, encoding="utf-8")

    def test_model_preflight_rejects_mismatch_and_unlocked_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model_root = root / "models"
            model_root.mkdir()
            model_path = model_root / "sample.safetensors"
            model_path.write_bytes(b"locked")
            import hashlib

            digest = hashlib.sha256(b"locked").hexdigest()
            entry = {"name": "sample", "mandatory": True, "profiles": ["hoi4_portraits_agent_local_nvidia_16gb"], "destination_folder": "models", "filename": "sample.safetensors", "size_bytes": 6, "sha256": digest}
            self.assertEqual(_model_artifact_preflight(root, model_root, [entry], "hoi4_portraits_agent_local_nvidia_16gb")["status"], "PASS")
            model_path.write_bytes(b"changed")
            self.assertEqual(_model_artifact_preflight(root, model_root, [entry], "hoi4_portraits_agent_local_nvidia_16gb")["status"], "BLOCKED")
            model_path.write_bytes(b"locked")
            (model_root / "unlocked.bin").write_bytes(b"extra")
            self.assertEqual(_model_artifact_preflight(root, model_root, [entry], "hoi4_portraits_agent_local_nvidia_16gb")["status"], "BLOCKED")
            unsupported = dict(entry, filename="sample.bin")
            model_path.rename(model_root / "sample.bin")
            self.assertEqual(_model_artifact_preflight(root, model_root, [unsupported], "hoi4_portraits_agent_local_nvidia_16gb")["status"], "BLOCKED")

    def test_preprocessing_lock_is_complete_and_installed_artifacts_pass(self):
        lock = json.loads((self.root / "dependencies/preprocessing_lock.json").read_text(encoding="utf-8"))
        report = _preprocessing_artifact_preflight(self.root, lock)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["missing_checksums"], [])
        self.assertEqual(report["mandatory_count"], 4)
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
        local = collect_preflight(self.root, profile="hoi4_portraits_agent_local_nvidia_16gb")
        remote = collect_preflight(self.root, profile="hoi4_portraits_agent_full_power_gpu")
        self.assertEqual(next(g["status"] for g in local["gates"] if g["name"] == "remote_topology_auth"), "NOT_APPLICABLE")
        self.assertEqual(next(g["status"] for g in remote["gates"] if g["name"] == "remote_topology_auth"), "BLOCKED")

    def test_calibrated_threshold_status_gate_is_consistent(self):
        self.assertEqual(CALIBRATED_THRESHOLD_STATUSES, frozenset({"APPROVED", "RESOLVED"}))
        self.assertNotIn("BLOCKED_UNTIL_CALIBRATION", CALIBRATED_THRESHOLD_STATUSES)

    def test_identity_calibration_evidence_is_recorded_but_stays_fail_closed(self):
        thresholds = json.loads((self.root / "config/identity_thresholds.json").read_text(encoding="utf-8"))
        self.assertEqual(thresholds["status"], "BLOCKED_UNTIL_CALIBRATION")
        self.assertTrue(thresholds["fail_closed"])
        self.assertIsNone(thresholds["face_embedding"]["minimum_similarity"])
        self.assertIsNone(thresholds["landmarks"]["max_normalized_error"])

    def test_geometry_thresholds_remain_unapproved(self):
        thresholds = json.loads((self.root / "config/identity_thresholds.json").read_text(encoding="utf-8"))
        self.assertIsNone(thresholds["pose"]["max_yaw_delta_degrees"])
        self.assertIsNone(thresholds["expression"]["max_distance"])
        self.assertIsNone(thresholds["asymmetry"]["max_change"])

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
            runtime_lock = {
                "model": {"name": "fixture-visual-auditor", "revision": "fixture-revision", "sha256": "a" * 64},
                "runtime": {
                    "port": 8191,
                    "context_size": 8192,
                    "max_tokens": 512,
                    "parallel_requests": 1,
                    "temperature": 0.0,
                },
            }
            runtime_tuple = (
                runtime_lock,
                self.root / "prompts/visual_audit_rubric.txt",
                source,
                source,
                candidate,
            )
            with mock.patch("portrait_pipeline.visual_audit_service._load_runtime_lock", return_value=runtime_tuple), mock.patch("portrait_pipeline.visual_audit_service.VisualAuditProducer.start"), mock.patch("portrait_pipeline.visual_audit_service.VisualAuditProducer.stop"), mock.patch("portrait_pipeline.visual_audit_service._post_json", return_value=response) as post:
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
            producer = VisualAuditProducer(root=self.root, runtime_profile="hoi4_portraits_full_power_gpu", auditor_process_id="visual-auditor-2")
            with self.assertRaises(VisualAuditServiceError):
                producer.start()

    def test_acceptance_schema_gate_includes_visual_audit_contracts(self):
        from portrait_pipeline.acceptance import _schema_gate

        result = _schema_gate(self.root)
        self.assertEqual(result["status"], "PASS")
        schemas = {item["schema"] for item in result["checked"]}
        self.assertIn("docs/schemas/visual_audit_evidence.schema.json", schemas)
        self.assertIn("docs/schemas/visual_reference_set.schema.json", schemas)

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
        self.assertEqual(matrix["profiles"]["hoi4_portraits_agent_full_power_gpu"]["canvas"], [1196, 1610])

    def test_production_graph_model_scope_matches_the_model_lock(self):
        lock = json.loads((self.root / "dependencies/models.lock.json").read_text(encoding="utf-8"))
        fp8 = next(model for model in lock["models"] if model["name"] == "krea2_turbo_fp8_scaled.safetensors")
        self.assertTrue(fp8["mandatory"])
        for profile in ("hoi4_portraits_local_nvidia_16gb", "hoi4_portraits_full_power_gpu", "hoi4_portraits_agent_local_nvidia_16gb", "hoi4_portraits_agent_full_power_gpu"):
            self.assertIn(profile, fp8["profiles"], profile)
        enhancer = next(model for model in lock["models"] if model["name"] == "RealESRGAN_x2plus.pth")
        self.assertTrue(enhancer["mandatory"])
        self.assertEqual(enhancer["revision"], "64ad194ddaf9c4d8c4b0d1b98cac6d89d3ea0d11")
        self.assertEqual(enhancer["size_bytes"], 67061725)
        self.assertEqual(enhancer["sha256"], "49fafd45f8fd7aa8d31ab2a22d14d91b536c34494a5cfe31eb5d89c2fa266abb")
        self.assertEqual(enhancer["destination_folder"], "models/upscale_models")
        qwen_edit = next(model for model in lock["models"] if model["name"] == "qwen_image_edit_2511_fp8mixed.safetensors")
        self.assertEqual(qwen_edit["repository"], "Comfy-Org/Qwen-Image-Edit_ComfyUI")
        self.assertEqual(qwen_edit["revision"], "e9e85de74a8f48c1e3e2656617626348675a2f21")
        self.assertEqual(qwen_edit["size_bytes"], 20533762817)
        self.assertEqual(qwen_edit["sha256"], "c9fdc158e46d3b61ef75f21ae866ca2fe808bf4a53643120d1c1e87c19280a4e")
        self.assertEqual(qwen_edit["destination_folder"], "models/diffusion_models")
        self.assertEqual(
            set(qwen_edit["profiles"]),
            {
                "hoi4_portraits_prepare_portrait_qwen",
            },
        )
        qwen_encoder = next(model for model in lock["models"] if model["name"] == "qwen_2.5_vl_7b_fp8_scaled.safetensors")
        self.assertEqual(qwen_encoder["revision"], "46839d338df81ce625d5fae27d7e370314c0fbc9")
        self.assertEqual(qwen_encoder["sha256"], "cb5636d852a0ea6a9075ab1bef496c0db7aef13c02350571e388aea959c5c0b4")
        style = next(item for item in lock["project_owned_immutable_files"] if item["name"] == "hoi4_portrait_new_style_lora.safetensors")
        self.assertEqual(style["repository"], "Hoops-McCann/hoi4-portrait-new-style-lora")
        self.assertEqual(style["revision"], "2eb855d3176908af4329640c8d966a1b26fc3d6b")
        self.assertIn(style["revision"], style["source_url"])
        self.assertEqual(style["source_visibility"], "public")
        self.assertFalse(style["requires_authentication"])
        self.assertEqual(style["size_bytes"], 228587816)
        self.assertEqual(style["sha256"], "2ad94552d151d2dedf151cf7356cdd3ea07677607ff289fc0ac61534b34dead1")

    def test_installer_selects_qwen_only_for_the_optional_restoration_workflow(self):
        from scripts.install_support import _restore_models

        lock = json.loads((self.root / "dependencies/models.lock.json").read_text(encoding="utf-8"))
        selected: list[str] = []

        def record(_url, destination, _size, _sha256, _actions):
            selected.append(Path(destination).name)

        with mock.patch("scripts.install_support._download_verified", side_effect=record):
            _restore_models(
                lock,
                "hoi4_portraits_full_power_gpu",
                [],
                {
                    "hoi4_portraits_full_power_gpu",
                    "hoi4_portraits_agent_full_power_gpu",
                    "hoi4_portraits_prepare_portrait_for_hoi4",
                },
            )
        self.assertNotIn("qwen_image_edit_2511_fp8mixed.safetensors", selected)
        self.assertNotIn("qwen_2.5_vl_7b_fp8_scaled.safetensors", selected)
        self.assertIn("krea2_turbo_fp8_scaled.safetensors", selected)

        selected.clear()
        with mock.patch("scripts.install_support._download_verified", side_effect=record):
            _restore_models(
                lock,
                "hoi4_portraits_full_power_gpu",
                [],
                {"hoi4_portraits_prepare_portrait_qwen"},
            )
        self.assertIn("qwen_image_edit_2511_fp8mixed.safetensors", selected)
        self.assertIn("qwen_2.5_vl_7b_fp8_scaled.safetensors", selected)

        selected.clear()
        with mock.patch("scripts.install_support._download_verified", side_effect=record):
            _restore_models(
                lock,
                "hoi4_portraits_local_nvidia_16gb",
                [],
                {
                    "hoi4_portraits_local_nvidia_16gb",
                    "hoi4_portraits_agent_local_nvidia_16gb",
                },
            )
        self.assertNotIn("qwen_image_edit_2511_fp8mixed.safetensors", selected)
        self.assertNotIn("qwen_2.5_vl_7b_fp8_scaled.safetensors", selected)
        self.assertIn("RealESRGAN_x2plus.pth", selected)

    def test_existing_comfyui_installer_is_non_destructive_and_packages_agent_setup(self):
        from scripts.install_into_existing_comfyui import _copy_example_input, _copy_project_nodes, _copy_workflows, _merge_extra_model_paths

        with tempfile.TemporaryDirectory() as directory:
            comfy_root = Path(directory)
            (comfy_root / "main.py").write_text("# existing ComfyUI fixture\n", encoding="utf-8")
            actions = []
            _copy_project_nodes(comfy_root, actions)
            _merge_extra_model_paths(comfy_root, actions)
            _copy_workflows(comfy_root, actions)
            installed_nodes = comfy_root / "custom_nodes" / "hoi4_portrait_nodes"
            self.assertTrue((installed_nodes / "__init__.py").is_file())
            self.assertTrue((installed_nodes / "portrait_pipeline" / "constants.py").is_file())
            installed_workflows = list((comfy_root / "user/default/workflows/hoi4_portraits").glob("*.json"))
            self.assertEqual(len(installed_workflows), 10)
            _copy_example_input(comfy_root, actions)
            self.assertTrue((comfy_root / "input/hoi4_preparation_example.jpg").is_file())
            _copy_workflows(comfy_root, actions, {"hoi4_portraits_full_power_gpu"})
            installed_workflows = list((comfy_root / "user/default/workflows/hoi4_portraits").glob("*.json"))
            self.assertEqual(len(installed_workflows), 10)
            self.assertIn("hoi4_portraits_full_power_gpu", {path.stem for path in installed_workflows})
            config = (comfy_root / "extra_model_paths.yaml").read_text(encoding="utf-8")
            self.assertEqual(config.count("# BEGIN HOI4 PORTRAIT WORKFLOWS"), 1)
            _merge_extra_model_paths(comfy_root, actions)
            self.assertEqual((comfy_root / "extra_model_paths.yaml").read_text(encoding="utf-8"), config)
            self.assertTrue((self.root / "docs/setup-with-coding-agent.md").is_file())
            prompt = (self.root / "prompts/install_into_existing_comfyui_agent_prompt.md").read_text(encoding="utf-8")
            self.assertIn("Do not replace or reinstall ComfyUI", prompt)
            self.assertIn("scripts/install_windows.ps1", prompt)
            self.assertIn("scripts/install_runpod.sh", prompt)

    def test_runpod_setup_installs_every_workflow_without_installing_comfyui(self):
        installer = (self.root / "scripts/install_runpod.sh").read_text(encoding="utf-8")
        workflow_ids = {
            path.stem
            for path in (self.root / "workflows").glob("**/*.json")
            if not path.name.endswith(".api.json") and path.stem != "hoi4_portraits_prepare_portrait_qwen"
        }
        for workflow_id in workflow_ids:
            self.assertIn(f"--workflow {workflow_id}", installer)
        optional = (self.root / "scripts/install_runpod_qwen.sh").read_text(encoding="utf-8")
        self.assertIn("--workflow hoi4_portraits_prepare_portrait_qwen", optional)
        self.assertNotIn("--workflow hoi4_portraits_prepare_portrait_qwen", installer)
        self.assertIn("existing ComfyUI", (self.root / "README.md").read_text(encoding="utf-8"))
        self.assertNotIn("install or replace ComfyUI", installer)

    def test_release_package_is_user_facing_and_runtime_complete(self):
        from scripts.release.build_release_artifacts import FORBIDDEN_SUFFIXES, _selected_files

        relative = {path.relative_to(self.root).as_posix() for path in _selected_files()}
        self.assertIn("docs/setup-with-coding-agent.md", relative)
        self.assertIn("prompts/install_into_existing_comfyui_agent_prompt.md", relative)
        self.assertIn("scripts/install_support.py", relative)
        self.assertNotIn("scripts/bootstrap/bootstrap.py", relative)
        self.assertNotIn("scripts/preflight/verify_live_comfy_compatibility.py", relative)
        self.assertNotIn("src/portrait_pipeline/acceptance.py", relative)
        self.assertNotIn("src/portrait_pipeline/audit.py", relative)
        self.assertIn("workflows/human/local_nvidia_16gb/hoi4_portraits_local_nvidia_16gb.json", relative)
        self.assertIn("workflows/agent/local_nvidia_16gb/hoi4_portraits_agent_local_nvidia_16gb.json", relative)
        self.assertIn("workflows/human/no_input_local_nvidia_16gb/hoi4_portraits_no_input_local_nvidia_16gb.json", relative)
        self.assertIn("workflows/agent/no_input_local_nvidia_16gb/hoi4_portraits_agent_no_input_local_nvidia_16gb.json", relative)
        self.assertIn("docs/schemas/portrait_prompt_job_input.schema.json", relative)
        self.assertIn("workflows/human/prepare_portrait/hoi4_portraits_prepare_portrait_for_hoi4.json", relative)
        self.assertIn("workflows/human/prepare_portrait_basic/hoi4_portraits_prepare_portrait_basic.json", relative)
        self.assertTrue(any(path.startswith("docs/assets/") for path in relative))
        self.assertFalse(
            any(
                Path(path).suffix.casefold() in FORBIDDEN_SUFFIXES
                and not path.startswith("docs/assets/")
                for path in relative
            )
        )
        self.assertFalse(any(path.startswith("backgrounds/local/") for path in relative))
        self.assertFalse(any(path.startswith("backgrounds/bundled/") for path in relative))
        self.assertFalse(any(".egg-info/" in path for path in relative))
        self.assertNotIn("prompts/implementation_goal_prompt.md", relative)

    def test_profile_runtime_locks_are_checksum_verified_but_live_runtime_stays_separate(self):
        for profile in ("hoi4_portraits_local_nvidia_16gb", "hoi4_portraits_full_power_gpu", "hoi4_portraits_agent_local_nvidia_16gb", "hoi4_portraits_agent_full_power_gpu"):
            report = collect_preflight(self.root, profile=profile)
            gate = next(gate for gate in report["gates"] if gate["name"] == "comfyui_runtime_dependency_lock")
            self.assertEqual(gate["status"], "PASS", gate)
            self.assertEqual(gate["evidence"]["mode"], "profile_locks")
            self.assertEqual(gate["evidence"]["project_lock"]["status"], "PASS", gate)

    def test_benchmark_and_comparison_reports_never_claim_generation_without_evidence(self):
        from portrait_pipeline.benchmarks import build_benchmark_report
        from portrait_pipeline.comparisons import build_comparison_report

        benchmark = build_benchmark_report(self.root, "hoi4_portraits_agent_local_nvidia_16gb")
        self.assertNotEqual(benchmark["status"], "PASS")
        self.assertEqual(benchmark["claims"]["final_png"], "NOT_CREATED")
        self.assertEqual(benchmark["measurements"]["generation"]["status"], "BLOCKED_NOT_ATTEMPTED")
        self.assertEqual(benchmark["measurements"]["generation"]["candidate_count"], 0)
        comparison = build_comparison_report(self.root)
        self.assertIn(comparison["status"], {"BLOCKED_NO_REAL_CANDIDATES", "BLOCKED_DIAGNOSTIC_CANDIDATES_NOT_PRODUCTION_AUTHORIZED"})
        self.assertGreaterEqual(comparison["candidate_counts"]["observed"], 0)
        self.assertIsNone(comparison["claims"]["identity_winner"])

    def test_remote_surface_is_authenticated_and_fail_closed(self):
        from portrait_pipeline.comfy_client import AuthenticatedRemoteGatewayClient, ComfyTransportError

        with self.assertRaises(ComfyTransportError) as context:
            AuthenticatedRemoteGatewayClient("https://example.invalid", "")
        self.assertEqual(context.exception.code, ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED)

        gateway = (self.root / "src/portrait_pipeline/mcp/gateway.py").read_text(encoding="utf-8")
        self.assertIn("hoi4_portraits_agent_full_power_gpu", gateway)
        self.assertFalse((self.root / "deploy/runpod").exists())
        self.assertTrue((self.root / "workflows/agent/full_power_gpu").exists())

    def test_local_memory_profiles_expose_only_unqualified_switch_placeholders(self):
        from portrait_pipeline.graph_spec.builder import UI_ONLY_NODE_CLASSES

        for path in self.root.joinpath("workflows").glob("**/*.json"):
            if path.name.endswith(".api.json"):
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            profile = data.get("extra", {}).get("hoi4_portrait", {}).get("profile")
            if profile not in {"hoi4_portraits_local_nvidia_16gb", "hoi4_portraits_agent_local_nvidia_16gb"}:
                continue
            notes = {node["id"]: node for node in data["nodes"] if node.get("type") in UI_ONLY_NODE_CLASSES}
            self.assertEqual(set(notes), {31, 32, 33}, path)
            note_text = " ".join(str(node.get("widgets_values", [""])[0]) for node in notes.values())
            self.assertIn("12 GB", note_text)
            self.assertIn("8 GB", note_text)
            api = json.loads(path.with_name(path.name.replace(".json", ".api.json")).read_text(encoding="utf-8"))
            self.assertNotIn("Note", {node.get("class_type") for node in api.values() if isinstance(node, dict)})
            self.assertEqual(len(api["_meta"]["low_memory_placeholder_nodes"]), 3)

    def test_runpod_profiles_use_remote_auth_and_controlnet_is_not_included(self):
        for path in self.root.joinpath("workflows").glob("**/*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            meta = data.get("extra", {}).get("hoi4_portrait", {})
            if meta.get("profile") in {"hoi4_portraits_full_power_gpu", "hoi4_portraits_agent_full_power_gpu"}:
                self.assertEqual(meta["route"], "runpod")
                self.assertEqual(meta["remote_authentication"], "x_api_key_runpod")
            for node in data.get("nodes", []):
                text = json.dumps(node).casefold()
                self.assertNotIn("controlnet", text, (path, node))

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
            (root / "docs").mkdir()
            (root / "docs/schemas").symlink_to(self.root / "docs/schemas", target_is_directory=True)
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
