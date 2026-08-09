from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

import torch

from scripts import apply_variant, build_workflows, install_workflows, validate_workflows


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / "workflows"


class WorkflowTests(unittest.TestCase):
    def test_committed_workflows_match_the_clean_builder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_workflows.build_all(root)
            generated = root / "workflows"
            for path in WORKFLOW_DIR.glob("*.json"):
                self.assertEqual((generated / path.name).read_bytes(), path.read_bytes(), path.name)

    def test_structural_layout_and_policy_validation_pass(self) -> None:
        result = validate_workflows.validate_all(ROOT)
        self.assertEqual(result["status"], "PASS", "\n".join(result["errors"]))
        self.assertEqual({item["nodes"] for item in result["workflows"]}, {70, 20, 37, 46})

    def test_every_node_stays_visible_inside_expanded_canvas_groups(self) -> None:
        for workflow_id in build_workflows.BUILDERS:
            path = WORKFLOW_DIR / f"{workflow_id}.json"
            ui = json.loads(path.read_text())
            self.assertTrue(ui["groups"], path.name)
            self.assertTrue(all(group["flags"] == {"collapsed": False} for group in ui["groups"]))
            self.assertNotIn("definitions", ui, path.name)

    def test_exact_prompts_and_only_focused_custom_nodes(self) -> None:
        source = json.loads((WORKFLOW_DIR / "hoi4_portrait_flux2_klein_9b_source.api.json").read_text())
        text = json.loads((WORKFLOW_DIR / "hoi4_portrait_flux2_klein_9b_text_to_image.api.json").read_text())
        source_samplers = [node for node in source.values() if node["class_type"] == "KSampler"]
        self.assertEqual(len(source_samplers), 3)
        self.assertEqual({node["inputs"]["seed"] for node in source_samplers}, {42, 43, 44})
        text_sampler = next(node for node in text.values() if node["class_type"] == "KSampler")
        for sampler in source_samplers + [text_sampler]:
            self.assertEqual(
                [sampler["inputs"][name] for name in ("steps", "cfg", "sampler_name", "scheduler", "denoise")],
                [4, 1.0, "euler", "simple", 1.0],
            )
        source_prompts = [node for node in source.values() if node["class_type"] == "CLIPTextEncode" and node["_meta"]["title"] == "Portrait prompt"]
        text_prompt = next(node for node in text.values() if node["class_type"] == "CLIPTextEncode" and node["_meta"]["title"] == "Portrait prompt")
        self.assertEqual({node["inputs"]["text"] for node in source_prompts}, {build_workflows.STYLE_PROMPT})
        self.assertEqual(text_prompt["inputs"]["text"], build_workflows.TEXT_PROMPT)
        self.assertTrue(all(node["inputs"]["guidance"] == 1.0 for node in source.values() if node["class_type"] == "FluxGuidance"))
        forbidden = {"Hoi4ModelStack", "Hoi4SourcePrep", "Hoi4AdonisRestoration", "Hoi4FinalOutput"}
        self.assertFalse(any(node["class_type"] in forbidden for node in source.values()))
        for required in ("UNETLoader", "ClipLoaderGGUF", "VAELoader", "ImageUpscaleWithModel"):
            self.assertEqual(sum(node["class_type"] == required for node in source.values()), 1, required)
        self.assertEqual(sum(node["class_type"] == "LoraLoaderModelOnly" for node in source.values()), 3)
        self.assertEqual(sum(node["class_type"] == "Hoi4BackgroundReplace" for node in source.values()), 1)

    def test_source_comparison_and_outputs_are_exact(self) -> None:
        ui = json.loads((WORKFLOW_DIR / "hoi4_portrait_flux2_klein_9b_source.json").read_text())
        api = json.loads((WORKFLOW_DIR / "hoi4_portrait_flux2_klein_9b_source.api.json").read_text())
        previews = [node for node in ui["nodes"] if node["type"] == "PreviewImage"]
        self.assertEqual(len(previews), 5)
        self.assertTrue(all(node["size"] == [600, 810] for node in previews))
        titles = {node["title"] for node in previews}
        self.assertTrue({"Prepared portrait", "Restored portrait"}.issubset(titles))
        self.assertEqual(sum(title.startswith("Portrait ") for title in titles), 3)
        masters = [node for node in api.values() if node["class_type"] == "ImageScale" and "master" in node["_meta"]["title"]]
        games = [node for node in api.values() if node["class_type"] == "ImageScale" and "game" in node["_meta"]["title"]]
        self.assertEqual(len(masters), 3)
        self.assertEqual(len(games), 3)
        self.assertTrue(all([node["inputs"]["width"], node["inputs"]["height"], node["inputs"]["crop"]] == [1024, 1365, "center"] for node in masters))
        self.assertTrue(all([node["inputs"]["width"], node["inputs"]["height"], node["inputs"]["crop"]] == [156, 210, "center"] for node in games))
        dds = [node for node in api.values() if node["class_type"] == "Hoi4SaveDDS"]
        self.assertEqual(len(dds), 3)
        self.assertTrue(all(node["inputs"]["format"] == "argb8888" for node in dds))
        background_id, background = next((node_id, node) for node_id, node in api.items() if node["class_type"] == "Hoi4BackgroundReplace")
        self.assertEqual(api[background["inputs"]["image"][0]]["class_type"], "ImageBatch")
        extracts = [node for node in api.values() if node["class_type"] == "ImageFromBatch"]
        self.assertEqual(len(extracts), 3)
        self.assertTrue(all(node["inputs"]["image"][0] == background_id for node in extracts))

    def test_adonis_defaults_match_the_upstream_base_refine_graph(self) -> None:
        api = json.loads((WORKFLOW_DIR / "hoi4_portrait_processing_only.api.json").read_text())
        scale = next(node for node in api.values() if node["class_type"] == "ImageScaleToTotalPixelsX")
        self.assertEqual([scale["inputs"][key] for key in ("megapixels", "multiple_of", "resize_mode", "upscale_method")], [1.7, 16, "crop", "lanczos"])
        options = next(node for node in api.values() if node["class_type"] == "SharkOptions_Beta")
        self.assertEqual([options["inputs"][key] for key in ("noise_type_init", "s_noise_init", "denoise_alt", "channelwise_cfg")], ["laplacian", 1.0, 1.0, False])
        samplers = [node for node in api.values() if node["class_type"] == "ClownsharKSampler_Beta"]
        self.assertEqual(len(samplers), 2)
        base = next(node for node in samplers if "Base" in node["_meta"]["title"])
        refine = next(node for node in samplers if "Refine" in node["_meta"]["title"])
        self.assertEqual([base["inputs"][key] for key in ("eta", "sampler_name", "scheduler", "steps_to_run", "cfg", "denoise", "sampler_mode", "bongmath")], [0.8, "exponential/res_2s", "simple", 5, 1.0, 1.0, "standard", True])
        self.assertEqual([refine["inputs"][key] for key in ("eta", "sampler_name", "scheduler", "steps_to_run", "cfg", "denoise", "sampler_mode", "bongmath")], [0.8, "exponential/res_2s", "simple", -1, 1.0, 1.0, "resample", True])
        self.assertNotIn("positive", refine["inputs"])
        self.assertNotIn("negative", refine["inputs"])

    def test_batch_has_one_sampler_and_all_three_output_types(self) -> None:
        api = json.loads((WORKFLOW_DIR / "hoi4_portrait_batch.api.json").read_text())
        self.assertEqual(sum(node["class_type"] == "Hoi4BatchInput" for node in api.values()), 1)
        self.assertEqual(sum(node["class_type"] == "KSampler" for node in api.values()), 1)
        prefixes = [node["inputs"].get("filename_prefix", "") for node in api.values()]
        self.assertTrue(any(str(prefix).startswith("1024x1365/") for prefix in prefixes))
        self.assertTrue(any(str(prefix).startswith("156x210/") for prefix in prefixes))
        self.assertTrue(any(str(prefix).startswith("156x210/dds/") for prefix in prefixes))


class InstallerTests(unittest.TestCase):
    def _comfy_root(self, directory: str) -> Path:
        root = Path(directory) / "ComfyUI"
        (root / "user/default/workflows").mkdir(parents=True)
        (root / "main.py").write_text("# test\n")
        return root

    def test_installer_overwrites_stale_graphs_with_exactly_four_workflows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            comfy_root = self._comfy_root(directory)
            target = comfy_root / "user/default/workflows/hoi4_portraits"
            target.mkdir(parents=True)
            (target / "identity_test_bad.json").write_text("{}")
            self.assertEqual(install_workflows.main(["--comfyui-root", str(comfy_root)]), 0)
            installed = sorted(target.glob("*.json"))
            self.assertEqual([path.stem for path in installed], sorted(build_workflows.BUILDERS))
            self.assertFalse((target / "identity_test_bad.json").exists())
            self.assertTrue((comfy_root / "custom_nodes/hoi4_portraits/__init__.py").is_file())
            self.assertTrue((comfy_root / "custom_nodes/hoi4_portraits/web/setup_guide.js").is_file())
            self.assertTrue((comfy_root / "input/source_portrait.jpg").is_file())
            self.assertTrue((comfy_root / "input/hoi4_leader_portrait_background.png").is_file())
            self.assertTrue((comfy_root / "input/hoi4_portraits_batch").is_dir())
            self.assertTrue((comfy_root / "output/156x210/dds").is_dir())

    def test_variant_selector_patches_visible_model_loader_and_preserves_personal_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            comfy_root = self._comfy_root(directory)
            self.assertEqual(install_workflows.main(["--comfyui-root", str(comfy_root)]), 0)
            target = comfy_root / "user/default/workflows/hoi4_portraits"
            personal = target / "personal_workflow.json"
            personal.write_text('{"nodes": [{"type": "Note", "widgets_values": ["mine"]}]}')
            before = personal.read_bytes()
            result = apply_variant.main(
                ["--comfyui-root", str(comfy_root), "--variant", "fp8", "--variant", "gguf", "--gguf-quants", "Q5_K_M"]
            )
            self.assertEqual(result, 0)
            source = json.loads((target / "hoi4_portrait_flux2_klein_9b_source.json").read_text())
            loader = next(node for node in source["nodes"] if node["type"] == "UNETLoader")
            self.assertEqual(loader["widgets_values"][0], "flux-2-klein-9b-fp8.safetensors")
            gguf = json.loads((target / "hoi4_portrait_flux2_klein_9b_source_gguf.json").read_text())
            gguf_loader = next(node for node in gguf["nodes"] if node["type"] == "UnetLoaderGGUF")
            self.assertEqual(gguf_loader["widgets_values"][0], "flux-2-klein-9b-Q5_K_M.gguf")
            self.assertEqual(personal.read_bytes(), before)


class CustomNodeTests(unittest.TestCase):
    @staticmethod
    def _load_module(root: Path):
        fake = types.ModuleType("folder_paths")
        fake.get_input_directory = lambda: str(root / "input")
        fake.get_output_directory = lambda: str(root / "output")

        def save_path(prefix, output_dir, width, height):
            prefix_path = Path(prefix)
            folder = Path(output_dir) / prefix_path.parent
            return str(folder), prefix_path.name, 1, "", str(prefix_path.parent)

        fake.get_save_image_path = save_path
        sys.modules["folder_paths"] = fake
        path = ROOT / "custom_nodes/hoi4_portraits/__init__.py"
        spec = importlib.util.spec_from_file_location("hoi4_nodes_test", path)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        return module

    def test_center_crop_never_stretches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            module = self._load_module(Path(directory))
            image = torch.linspace(0, 1, 300).view(1, 1, 300, 1).repeat(1, 100, 1, 3)
            master = module._resize_center_crop(image, 1024, 1365)
            game = module._resize_center_crop(master, 156, 210)
            self.assertEqual(tuple(master.shape), (1, 1365, 1024, 3))
            self.assertEqual(tuple(game.shape), (1, 210, 156, 3))
            self.assertGreater(float(game.std()), 0.05)

    def test_dds_matches_vanilla_argb8888_portrait_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module = self._load_module(root)
            image = torch.rand((1, 210, 156, 3), dtype=torch.float32)
            module.Hoi4SaveDDS().save(image, "156x210/dds/test", "argb8888")
            dds = next((root / "output/156x210/dds").glob("*.dds"))
            data = dds.read_bytes()
            self.assertEqual(data[:4], b"DDS ")
            self.assertEqual(data[84:88], b"\x00\x00\x00\x00")
            self.assertEqual(int.from_bytes(data[12:16], "little"), 210)
            self.assertEqual(int.from_bytes(data[16:20], "little"), 156)
            self.assertEqual(int.from_bytes(data[28:32], "little"), 0)
            self.assertEqual(int.from_bytes(data[80:84], "little"), 0x41)
            self.assertEqual(int.from_bytes(data[88:92], "little"), 32)
            self.assertEqual(int.from_bytes(data[92:96], "little"), 0x00FF0000)
            self.assertEqual(int.from_bytes(data[96:100], "little"), 0x0000FF00)
            self.assertEqual(int.from_bytes(data[100:104], "little"), 0x000000FF)
            self.assertEqual(int.from_bytes(data[104:108], "little"), 0xFF000000)

    def test_batch_input_returns_list_items_for_one_by_one_execution(self) -> None:
        source = (ROOT / "custom_nodes/hoi4_portraits/__init__.py").read_text()
        self.assertIn("OUTPUT_IS_LIST = (True, True, True)", source)
        self.assertNotIn('"Hoi4ModelStack": Hoi4ModelStack', source)
        self.assertNotIn('"Hoi4FinalOutput": Hoi4FinalOutput', source)
        self.assertNotIn("Hoi4PortraitSampler", source)
        self.assertIn('"Hoi4SetupGuide": Hoi4SetupGuide', source)
        self.assertIn('"Hoi4BackgroundReplace": Hoi4BackgroundReplace', source)


if __name__ == "__main__":
    unittest.main()
