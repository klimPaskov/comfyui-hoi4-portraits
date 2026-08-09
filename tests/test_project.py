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
        self.assertEqual({item["nodes"] for item in result["workflows"]}, {29, 10, 13, 14})

    def test_every_node_stays_visible_without_collapsible_groups(self) -> None:
        for workflow_id in build_workflows.BUILDERS:
            path = WORKFLOW_DIR / f"{workflow_id}.json"
            ui = json.loads(path.read_text())
            self.assertEqual(ui["groups"], [], path.name)
            self.assertNotIn("definitions", ui, path.name)

    def test_exact_prompts_and_compact_logical_cards(self) -> None:
        source = json.loads((WORKFLOW_DIR / "hoi4_portrait_flux2_klein_9b_source.api.json").read_text())
        text = json.loads((WORKFLOW_DIR / "hoi4_portrait_flux2_klein_9b_text_to_image.api.json").read_text())
        source_samplers = [node for node in source.values() if node["class_type"] == "Hoi4PortraitSampler"]
        self.assertEqual(len(source_samplers), 3)
        self.assertEqual({node["inputs"]["prompt"] for node in source_samplers}, {build_workflows.STYLE_PROMPT})
        self.assertEqual({node["inputs"]["noise_seed"] for node in source_samplers}, {42, 43, 44})
        text_sampler = next(node for node in text.values() if node["class_type"] == "Hoi4PortraitSampler")
        self.assertEqual(text_sampler["inputs"]["prompt"], build_workflows.TEXT_PROMPT)
        for sampler in source_samplers + [text_sampler]:
            self.assertEqual(
                [sampler["inputs"][name] for name in ("steps", "cfg", "guidance", "sampling_algorithm", "scheduler")],
                [4, 1.0, 1.0, "euler", "simple"],
            )
        self.assertEqual(sum(node["class_type"] == "Hoi4ModelStack" for node in source.values()), 1)
        self.assertFalse(any(node["class_type"] in {"UNETLoader", "UnetLoaderGGUF", "ImageUpscaleWithModel"} for node in source.values()))

    def test_source_comparison_and_outputs_are_exact(self) -> None:
        ui = json.loads((WORKFLOW_DIR / "hoi4_portrait_flux2_klein_9b_source.json").read_text())
        api = json.loads((WORKFLOW_DIR / "hoi4_portrait_flux2_klein_9b_source.api.json").read_text())
        previews = [node for node in ui["nodes"] if node["type"] == "PreviewImage"]
        self.assertEqual(len(previews), 6)
        self.assertTrue(all(node["size"] == [600, 810] for node in previews))
        titles = {node["title"] for node in previews}
        self.assertTrue({"Source preview", "RealESRGAN prepared crop", "Adonis Base → Refine restored"}.issubset(titles))
        self.assertEqual(sum(title.startswith("Final candidate") for title in titles), 3)
        finals = [node for node in api.values() if node["class_type"] == "Hoi4FinalOutput"]
        self.assertEqual(len(finals), 3)
        for node in finals:
            self.assertEqual(
                [node["inputs"][key] for key in ("master_width", "master_height", "game_width", "game_height")],
                [1024, 1365, 156, 210],
            )
        dds = [node for node in api.values() if node["class_type"] == "Hoi4SaveDDS"]
        self.assertEqual(len(dds), 3)
        self.assertTrue(all(node["inputs"]["compression"] == "dxt5" for node in dds))

    def test_adonis_defaults_match_the_upstream_base_refine_graph(self) -> None:
        api = json.loads((WORKFLOW_DIR / "hoi4_portrait_processing_only.api.json").read_text())
        restore = next(node for node in api.values() if node["class_type"] == "Hoi4AdonisRestoration")
        expected = {
            "prompt": build_workflows.RESTORATION_PROMPT,
            "megapixels": 1.7,
            "multiple_of": 16,
            "resize_mode": "crop",
            "upscale_method": "lanczos",
            "eta": 0.8,
            "sampling_algorithm": "exponential/res_2s",
            "scheduler": "simple",
            "total_steps": 9,
            "base_steps_to_run": 5,
            "base_sampling_mode": "standard",
            "refine_sampling_mode": "resample",
            "noise_type": "gaussian",
            "channelwise_cfg": False,
            "bongmath": True,
        }
        for key, value in expected.items():
            self.assertEqual(restore["inputs"][key], value, key)

    def test_batch_has_one_sampler_and_all_three_output_types(self) -> None:
        api = json.loads((WORKFLOW_DIR / "hoi4_portrait_batch.api.json").read_text())
        self.assertEqual(sum(node["class_type"] == "Hoi4BatchInput" for node in api.values()), 1)
        self.assertEqual(sum(node["class_type"] == "Hoi4PortraitSampler" for node in api.values()), 1)
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
            self.assertTrue((comfy_root / "input/source_portrait.jpg").is_file())
            self.assertTrue((comfy_root / "input/hoi4_leader_portrait_background.png").is_file())
            self.assertTrue((comfy_root / "input/hoi4_portraits_batch").is_dir())
            self.assertTrue((comfy_root / "output/156x210/dds").is_dir())

    def test_variant_selector_patches_the_model_stack_and_preserves_personal_files(self) -> None:
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
            stack = next(node for node in source["nodes"] if node["type"] == "Hoi4ModelStack")
            self.assertEqual(stack["widgets_values"][0], "flux-2-klein-9b-fp8.safetensors")
            gguf = json.loads((target / "hoi4_portrait_flux2_klein_9b_source_gguf.json").read_text())
            gguf_stack = next(node for node in gguf["nodes"] if node["type"] == "Hoi4ModelStack")
            self.assertEqual(gguf_stack["widgets_values"][0], "flux-2-klein-9b-Q5_K_M.gguf")
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

    def test_center_crop_and_final_output_never_stretch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            module = self._load_module(Path(directory))
            image = torch.linspace(0, 1, 300).view(1, 1, 300, 1).repeat(1, 100, 1, 3)
            master, game = module.Hoi4FinalOutput().finish(image, False, "birefnet.safetensors", 1024, 1365, 156, 210)
            self.assertEqual(tuple(master.shape), (1, 1365, 1024, 3))
            self.assertEqual(tuple(game.shape), (1, 210, 156, 3))
            self.assertGreater(float(game.std()), 0.05)

    def test_dds_is_dxt5_156x210_with_no_mipmap_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module = self._load_module(root)
            image = torch.rand((1, 210, 156, 3), dtype=torch.float32)
            module.Hoi4SaveDDS().save(image, "156x210/dds/test", "dxt5")
            dds = next((root / "output/156x210/dds").glob("*.dds"))
            data = dds.read_bytes()
            self.assertEqual(data[:4], b"DDS ")
            self.assertEqual(data[84:88], b"DXT5")
            self.assertEqual(int.from_bytes(data[12:16], "little"), 210)
            self.assertEqual(int.from_bytes(data[16:20], "little"), 156)
            self.assertEqual(int.from_bytes(data[28:32], "little"), 0)

    def test_batch_input_returns_list_items_for_one_by_one_execution(self) -> None:
        source = (ROOT / "custom_nodes/hoi4_portraits/__init__.py").read_text()
        self.assertIn("OUTPUT_IS_LIST = (True, True, True)", source)
        self.assertIn('"Hoi4ModelStack": Hoi4ModelStack', source)
        self.assertIn('"Hoi4FinalOutput": Hoi4FinalOutput', source)


if __name__ == "__main__":
    unittest.main()
