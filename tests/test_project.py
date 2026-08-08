from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import apply_variant, build_workflows, install_workflows, validate_workflows


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / "workflows"


class WorkflowTests(unittest.TestCase):
    def test_committed_workflows_match_deterministic_builder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_workflows.build_all(root)
            for path in WORKFLOW_DIR.glob("*.json"):
                generated = root / "workflows" / path.name
                self.assertTrue(generated.exists(), path.name)
                self.assertEqual(generated.read_bytes(), path.read_bytes(), path.name)

    def test_structural_and_layout_validation_passes(self) -> None:
        result = validate_workflows.validate_all(ROOT)
        self.assertEqual(result["status"], "PASS", result["errors"])
        self.assertEqual(
            {item["workflow_id"] for item in result["workflows"]},
            {
                "hoi4_portrait_flux2_klein_9b_source",
                "hoi4_portrait_flux2_klein_9b_text_to_image",
                "hoi4_portrait_processing_only",
                "hoi4_portrait_batch",
            },
        )

    def test_distilled_model_and_sampler_defaults(self) -> None:
        self.assertEqual(build_workflows.BASE_MODEL, "flux-2-klein-9b.safetensors")
        self.assertNotIn("base", build_workflows.BASE_MODEL.casefold())
        self.assertEqual(build_workflows.STYLE_LORA_CHECKPOINTS, (build_workflows.STYLE_LORA,))
        self.assertEqual(build_workflows.DEFAULT_STEPS, 4)
        self.assertEqual(build_workflows.DEFAULT_CFG, 1.0)
        self.assertEqual(build_workflows.DEFAULT_GUIDANCE, 1.0)
        self.assertEqual(build_workflows.SOURCE_STYLE_DENOISE, 1.0)

    def test_each_sampler_is_merged_and_advanced(self) -> None:
        expected = {
            "hoi4_portrait_flux2_klein_9b_source.api.json": 5,
            "hoi4_portrait_flux2_klein_9b_text_to_image.api.json": 1,
            "hoi4_portrait_processing_only.api.json": 2,
            "hoi4_portrait_batch.api.json": 3,
        }
        for filename, count in expected.items():
            api = json.loads((WORKFLOW_DIR / filename).read_text())
            samplers = [node for node in api.values() if node["class_type"] == "Hoi4PortraitSampler"]
            self.assertEqual(len(samplers), count, filename)
            for node in samplers:
                inputs = node["inputs"]
                self.assertEqual(inputs["steps"], 4)
                self.assertEqual(inputs["cfg"], 1.0)
                self.assertEqual(inputs["guidance"], 1.0)
                self.assertEqual(inputs["sampling_algorithm"], "euler")
                self.assertEqual(inputs["scheduler"], "simple")
                self.assertEqual(inputs["denoise"], 1.0)

    def test_source_has_crop_preview_restoration_previews_and_three_candidates(self) -> None:
        api = json.loads((WORKFLOW_DIR / "hoi4_portrait_flux2_klein_9b_source.api.json").read_text())
        self.assertEqual(api["10"]["class_type"], "PreviewImage")
        self.assertEqual(api["10"]["inputs"]["images"], ["8", 0])
        # The Adonis Base and Post previews now read the direct decode output
        # (the redundant normalize-to-canvas node was removed).
        self.assertEqual(api["35"]["inputs"]["images"], ["31", 0])
        self.assertEqual(api["415"]["inputs"]["images"], ["411", 0])
        for sampler_id in ("50", "70", "90"):
            self.assertEqual(api[sampler_id]["class_type"], "Hoi4PortraitSampler")
        dds = [node for node in api.values() if node["class_type"] == "Hoi4SaveDDS"]
        self.assertEqual(len(dds), 3)

    def test_processing_has_dedicated_crop_esrgan_preview(self) -> None:
        api = json.loads((WORKFLOW_DIR / "hoi4_portrait_processing_only.api.json").read_text())
        self.assertEqual(api["10"]["class_type"], "PreviewImage")
        self.assertEqual(api["10"]["inputs"]["images"], ["8", 0])
        # The comparison row shows ESRGAN, the restoration pass, and the final.
        self.assertEqual(api["600"]["class_type"], "PreviewImage")
        self.assertEqual(api["600"]["inputs"]["images"], ["8", 0])
        self.assertEqual(api["601"]["inputs"]["images"], ["32", 0])
        self.assertEqual(api["602"]["inputs"]["images"], ["75", 0])
        self.assertEqual(api["74"]["class_type"], "Hoi4SaveDDS")

    def test_comparison_row_is_close_and_large(self) -> None:
        ui = json.loads((WORKFLOW_DIR / "hoi4_portrait_flux2_klein_9b_source.json").read_text())
        previews = [node for node in ui["nodes"] if node["type"] == "PreviewImage" and node["title"].startswith("Final portrait candidate")]
        self.assertEqual(len(previews), 3)
        self.assertTrue(all(node["size"][0] >= 500 and node["size"][1] >= 650 for node in previews))
        # All three finals sit on the same comparison row, close together.
        self.assertEqual({node["pos"][1] for node in previews}, {previews[0]["pos"][1]})
        gaps = [previews[index + 1]["pos"][0] - previews[index]["pos"][0] for index in range(2)]
        self.assertTrue(all(0 < gap <= 900 for gap in gaps), gaps)
        for index, node in enumerate(ui["nodes"]):
            ax, ay = node["pos"]
            aw, ah = node["size"]
            for other in ui["nodes"][index + 1 :]:
                bx, by = other["pos"]
                bw, bh = other["size"]
                self.assertTrue(ax + aw + 16 <= bx or bx + bw + 16 <= ax or ay + ah + 16 <= by or by + bh + 16 <= ay, (node["id"], other["id"]))

    def test_notes_explain_models_sampling_restoration_and_prompts(self) -> None:
        ui = json.loads((WORKFLOW_DIR / "hoi4_portrait_flux2_klein_9b_source.json").read_text())
        notes = [node for node in ui["nodes"] if node["type"] == "Note"]
        self.assertGreaterEqual(len(notes), 3)
        text = "\n".join(str(node["widgets_values"][0]) for node in notes)
        self.assertIn("diffusion_models", text)
        self.assertIn("CFG", text)
        self.assertIn("make this portrait hoi4_portrait style", text)
        self.assertIn("adonis_base.safetensors", text)
        # Notes must not leak into the API graph.
        api = json.loads((WORKFLOW_DIR / "hoi4_portrait_flux2_klein_9b_source.api.json").read_text())
        self.assertNotIn("Note", {node["class_type"] for node in api.values()})

    def test_batch_has_one_style_sampler_and_output_folders(self) -> None:
        api = json.loads((WORKFLOW_DIR / "hoi4_portrait_batch.api.json").read_text())
        self.assertIn("Hoi4BatchInput", {node["class_type"] for node in api.values()})
        style_lora = [node for node in api.values() if node["class_type"] == "LoraLoaderModelOnly" and str(node["inputs"].get("lora_name", "")).startswith("hoi4_portrait")]
        self.assertEqual(len(style_lora), 1)
        prefixes = [str(node["inputs"].get("filename_prefix", "")) for node in api.values() if node["class_type"] in {"SaveImage", "Hoi4SaveDDS"}]
        self.assertTrue(any(prefix.startswith("1024x1365/") for prefix in prefixes))
        self.assertTrue(any(prefix.startswith("156x210/") for prefix in prefixes))
        self.assertTrue(any(prefix.startswith("156x210/dds/") for prefix in prefixes))

    def test_crop_node_exposes_zoom_and_headwear_switch(self) -> None:
        api = json.loads((WORKFLOW_DIR / "hoi4_portrait_processing_only.api.json").read_text())
        crop = next(node for node in api.values() if node["class_type"] == "AdaptivePortraitCrop")
        self.assertEqual(crop["inputs"]["zoom"], 0.90)
        self.assertTrue(crop["inputs"]["preserve_headwear"])


class InstallerTests(unittest.TestCase):
    def test_installer_copies_four_workflows_and_custom_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            comfy_root = Path(directory) / "ComfyUI"
            (comfy_root / "user/default/workflows").mkdir(parents=True)
            (comfy_root / "main.py").write_text("# test")
            result = install_workflows.main(["--comfyui-root", str(comfy_root)])
            self.assertEqual(result, 0)
            installed = list((comfy_root / "user/default/workflows/hoi4_portraits").glob("*.json"))
            self.assertEqual(len(installed), 8)
            self.assertTrue((comfy_root / "custom_nodes/hoi4_portraits/__init__.py").is_file())

    def test_apply_variant_switches_and_copies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            comfy_root = Path(directory) / "ComfyUI"
            (comfy_root / "user/default/workflows").mkdir(parents=True)
            (comfy_root / "main.py").write_text("# test")
            self.assertEqual(install_workflows.main(["--comfyui-root", str(comfy_root)]), 0)
            self.assertEqual(
                apply_variant.main(
                    [
                        "--comfyui-root",
                        str(comfy_root),
                        "--variant",
                        "fp8",
                        "--variant",
                        "gguf",
                        "--gguf-quants",
                        "Q5_K_M",
                    ]
                ),
                0,
            )
            source = json.loads(
                (comfy_root / "user/default/workflows/hoi4_portraits/hoi4_portrait_flux2_klein_9b_source.json").read_text()
            )
            loader = next(node for node in source["nodes"] if node["type"] in {"UNETLoader", "UnetLoaderGGUF"})
            self.assertEqual(loader["type"], "UNETLoader")
            self.assertEqual(loader["widgets_values"][0], "flux-2-klein-9b-fp8.safetensors")
            gguf_copy = json.loads(
                (comfy_root / "user/default/workflows/hoi4_portraits/hoi4_portrait_flux2_klein_9b_source_gguf.json").read_text()
            )
            gguf_loader = next(node for node in gguf_copy["nodes"] if node["type"] in {"UNETLoader", "UnetLoaderGGUF"})
            self.assertEqual(gguf_loader["type"], "UnetLoaderGGUF")
            self.assertEqual(gguf_loader["widgets_values"][0], "flux-2-klein-9b-Q5_K_M.gguf")


class DocumentationTests(unittest.TestCase):
    def test_readme_has_four_default_workflows_and_setup_links(self) -> None:
        readme = (ROOT / "README.md").read_text()
        for workflow in (
            "hoi4_portrait_flux2_klein_9b_source.json",
            "hoi4_portrait_flux2_klein_9b_text_to_image.json",
            "hoi4_portrait_processing_only.json",
            "hoi4_portrait_batch.json",
        ):
            self.assertIn(workflow, readme)
        self.assertIn("FLUX.2-klein-9B", readme)
        self.assertIn("read-only Hugging Face token", readme)
        self.assertIn("156x210/dds", readme)


if __name__ == "__main__":
    unittest.main()
