from __future__ import annotations

import importlib.util
import json
import math
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

try:
    import torch
    from PIL import Image
except ImportError:  # Keep graph/installer CI lightweight when image runtimes are absent.
    torch = None
    Image = None

from scripts import apply_variant, build_workflows, configure_workspace, download_models, install_workflows, validate_workflows


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
        self.assertEqual({item["nodes"] for item in result["workflows"]}, {78, 21, 43, 52})

    def test_every_node_stays_visible_inside_expanded_canvas_groups(self) -> None:
        for workflow_id in build_workflows.BUILDERS:
            path = WORKFLOW_DIR / f"{workflow_id}.json"
            ui = json.loads(path.read_text())
            self.assertTrue(ui["groups"], path.name)
            self.assertTrue(all(group["flags"] == {"collapsed": False} for group in ui["groups"]))
            self.assertNotIn("definitions", ui, path.name)

    def test_exact_prompts_and_only_focused_custom_nodes(self) -> None:
        source = json.loads((WORKFLOW_DIR / "hoi4_portrait_source.api.json").read_text())
        text = json.loads((WORKFLOW_DIR / "hoi4_portrait_text_to_image.api.json").read_text())
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
        self.assertEqual(sum(node["class_type"] == "ComfySwitchNode" for node in source.values()), 1)
        self.assertEqual(sum(node["class_type"] == "Hoi4BackgroundReplace" for node in source.values()), 1)

    def test_current_comfyui_widget_contract_is_not_shifted(self) -> None:
        for workflow_id in build_workflows.BUILDERS:
            ui = json.loads((WORKFLOW_DIR / f"{workflow_id}.json").read_text())
            for sampler in (node for node in ui["nodes"] if node["type"] == "KSampler"):
                self.assertEqual([item["name"] for item in sampler["inputs"]], ["model", "positive", "negative", "latent_image"])
                self.assertEqual(sampler["widgets_values"], [sampler["widgets_values"][0], "fixed", 4, 1.0, "euler", "simple", 1.0])
            for crop in (node for node in ui["nodes"] if node["type"] == "AdaptivePortraitCrop"):
                self.assertEqual([item["name"] for item in crop["inputs"]], ["image", "face_bboxes", "subject_mask"])
                face_bboxes = next(item for item in crop["inputs"] if item["name"] == "face_bboxes")
                self.assertEqual(face_bboxes["widget"], {"name": "face_bboxes"})
                self.assertEqual(crop["widgets_values"], [{"x": 0, "y": 0, "width": 512, "height": 512}, 0, 0, 512, 512, True, False, 0.0, 0.0, 1.0, 1.0, 0.9, True, 512, 683])
            for saver in (node for node in ui["nodes"] if node["type"] == "SaveImage"):
                filename_prefix = next(item for item in saver["inputs"] if item["name"] == "filename_prefix")
                self.assertEqual(filename_prefix["widget"], {"name": "filename_prefix"})
                self.assertIsNotNone(filename_prefix["link"])

    def test_adonis_prompts_are_source_neutral(self) -> None:
        prompts = f"{build_workflows.ADONIS_BASE_COMBINED_PROMPT} {build_workflows.ADONIS_POST_COMBINED_PROMPT}".casefold()
        for source_specific_term in ("cellphone", "camera raw", "high iso", "male portrait"):
            self.assertNotIn(source_specific_term, prompts)
        for preservation_term in ("monochrome", "sepia", "historical character", "only where present"):
            self.assertIn(preservation_term, prompts)

    def test_source_comparison_and_outputs_are_exact(self) -> None:
        ui = json.loads((WORKFLOW_DIR / "hoi4_portrait_source.json").read_text())
        api = json.loads((WORKFLOW_DIR / "hoi4_portrait_source.api.json").read_text())
        previews = [
            node for node in ui["nodes"]
            if node["type"] == "PreviewImage"
            and node.get("properties", {}).get("hoi4_group") == "06 Compare portraits"
        ]
        self.assertEqual(len(previews), 5)
        self.assertTrue(all(node["size"] == [600, 810] for node in previews))
        titles = {node["title"] for node in previews}
        self.assertTrue({"Prepared portrait", "Restored portrait"}.issubset(titles))
        self.assertEqual(sum(title.startswith("Portrait ") for title in titles), 3)
        self.assertTrue(all("full resolution" in title for title in titles if title.startswith("Portrait ")))
        stage_groups = {
            group["title"]: group["bounding"]
            for group in ui["groups"]
            if group["title"] in {"03 Restore details", "04 Create three portraits", "05 Save portraits"}
        }
        self.assertEqual({bounding[1] for bounding in stage_groups.values()}, {40})
        self.assertEqual({bounding[3] for bounding in stage_groups.values()}, {1520})
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

    def test_final_previews_use_full_resolution_masters(self) -> None:
        expected_titles = {
            "hoi4_portrait_source": {"Portrait 1 — full resolution", "Portrait 2 — full resolution", "Portrait 3 — full resolution"},
            "hoi4_portrait_text_to_image": {"Full-resolution portrait"},
            "hoi4_portrait_batch": {"Full-resolution portrait"},
            "hoi4_portrait_processing_only": {"Full-resolution portrait"},
        }
        for workflow_id, titles in expected_titles.items():
            ui = json.loads((WORKFLOW_DIR / f"{workflow_id}.json").read_text())
            nodes = {node["id"]: node for node in ui["nodes"]}
            links = {link[0]: link for link in ui["links"]}
            previews = [node for node in ui["nodes"] if node["type"] == "PreviewImage" and node["title"] in titles]
            self.assertEqual({node["title"] for node in previews}, titles)
            for preview in previews:
                source_id = links[preview["inputs"][0]["link"]][1]
                source = nodes[source_id]
                self.assertEqual(source["type"], "ImageScale")
                self.assertEqual(source["widgets_values"][1:3], [1024, 1365])

    def test_adonis_defaults_match_the_upstream_base_post_graph(self) -> None:
        api = json.loads((WORKFLOW_DIR / "hoi4_portrait_processing_only.api.json").read_text())
        ui = json.loads((WORKFLOW_DIR / "hoi4_portrait_processing_only.json").read_text())
        scale = next(node for node in api.values() if node["class_type"] == "ImageScaleToTotalPixelsX")
        self.assertEqual([scale["inputs"][key] for key in ("megapixels", "multiple_of", "resize_mode", "upscale_method")], [1.7, 16, "crop", "lanczos"])
        options = next(node for node in api.values() if node["class_type"] == "SharkOptions_Beta")
        self.assertEqual([options["inputs"][key] for key in ("noise_type_init", "s_noise_init", "denoise_alt", "channelwise_cfg")], ["laplacian", 1.0, 1.0, False])
        samplers = [node for node in api.values() if node["class_type"] == "ClownsharKSampler_Beta"]
        self.assertEqual(len(samplers), 2)
        base = next(node for node in samplers if "Base" in node["_meta"]["title"])
        post = next(node for node in samplers if "Post" in node["_meta"]["title"])
        self.assertEqual([base["inputs"][key] for key in ("eta", "sampler_name", "scheduler", "steps_to_run", "cfg", "denoise", "sampler_mode", "bongmath")], [0.8, "exponential/res_2s", "simple", -1, 1.0, 1.0, "standard", True])
        self.assertEqual([post["inputs"][key] for key in ("eta", "sampler_name", "scheduler", "steps_to_run", "cfg", "denoise", "sampler_mode", "bongmath")], [0.5, "exponential/res_2s", "simple", -1, 1.0, 1.0, "standard", True])
        self.assertEqual(base["inputs"]["steps"], post["inputs"]["steps"])
        self.assertEqual(base["inputs"]["seed"], post["inputs"]["seed"])
        self.assertEqual(base["inputs"]["latent_image"], post["inputs"]["latent_image"])
        post_refs = [api[post["inputs"][name][0]] for name in ("positive", "negative")]
        self.assertTrue(all(node["class_type"] == "ReferenceLatent" for node in post_refs))
        self.assertTrue(all(node["inputs"]["latent"][0] == next(node_id for node_id, node in api.items() if node is base) for node in post_refs))
        switch = next(node for node in api.values() if node["class_type"] == "ComfySwitchNode")
        self.assertIs(switch["inputs"]["switch"], True)
        self.assertEqual(api[switch["inputs"]["on_false"][0]]["class_type"], "ImageScale")
        cached = api[switch["inputs"]["on_true"][0]]
        self.assertEqual(cached["class_type"], "Hoi4RestorationCache")
        self.assertEqual(api[cached["inputs"]["image"][0]]["class_type"], "VAEDecode")
        self.assertEqual(sum(node["class_type"] == "VAEDecode" for node in api.values()), 1)
        adonis_ui_samplers = [node for node in ui["nodes"] if node["type"] == "ClownsharKSampler_Beta"]
        self.assertEqual(len(adonis_ui_samplers), 2)
        self.assertTrue(all(node["widgets_values"][8] == "fixed" for node in adonis_ui_samplers))
        shared_seed = next(node for node in ui["nodes"] if node["title"] == "Shared Adonis seed")
        self.assertEqual(shared_seed["widgets_values"], [42])

    def test_batch_has_one_sampler_and_all_three_output_types(self) -> None:
        api = json.loads((WORKFLOW_DIR / "hoi4_portrait_batch.api.json").read_text())
        ui = json.loads((WORKFLOW_DIR / "hoi4_portrait_batch.json").read_text())
        self.assertEqual(sum(node["class_type"] == "Hoi4BatchInput" for node in api.values()), 1)
        self.assertEqual(sum(node["class_type"] == "KSampler" for node in api.values()), 1)
        self.assertEqual(sum(node["class_type"] == "SaveImage" for node in api.values()), 2)
        self.assertEqual(sum(node["class_type"] == "Hoi4SaveDDS" for node in api.values()), 1)
        filename_node_id, filename_node = next(
            (node_id, node) for node_id, node in api.items()
            if node["class_type"] == "Hoi4OutputFilename"
        )
        self.assertEqual(api[filename_node["inputs"]["source_filename"][0]]["class_type"], "Hoi4BatchInput")
        prefixes = [node["inputs"]["filename_prefix"] for node in api.values() if node["class_type"] in {"SaveImage", "Hoi4SaveDDS"}]
        self.assertEqual({tuple(prefix) for prefix in prefixes}, {(filename_node_id, 0), (filename_node_id, 1), (filename_node_id, 2)})
        for node in api.values():
            if node["class_type"] not in {"SaveImage", "Hoi4SaveDDS"}:
                continue
            source = api[node["inputs"]["images"][0]]
            self.assertEqual(source["class_type"], "ImageScale")
        self.assertEqual([group["title"] for group in ui["groups"]], ["00 Setup", "01 Prepare portraits", "02 Models", "03 Restore details", "04 Create portraits", "05 Save portraits"])
        previews = [node for node in ui["nodes"] if node["type"] == "PreviewImage"]
        self.assertEqual([node["pos"] for node in previews], [[5360, 740], [6000, 740], [6640, 740]])
        self.assertTrue(all(node["color"] == build_workflows.COLORS["sample"][0] for node in previews))
        create_group, save_group = ui["groups"][-2:]
        self.assertEqual(save_group["bounding"][0] - (create_group["bounding"][0] + create_group["bounding"][2]), 80)

    def test_every_workflow_uses_input_aware_output_names(self) -> None:
        expected_sources = {
            "hoi4_portrait_source": "Hoi4LoadImage",
            "hoi4_portrait_batch": "Hoi4BatchInput",
            "hoi4_portrait_processing_only": "Hoi4LoadImage",
        }
        for workflow_id in build_workflows.BUILDERS:
            api = json.loads((WORKFLOW_DIR / f"{workflow_id}.api.json").read_text())
            filename_nodes = {
                node_id: node for node_id, node in api.items()
                if node["class_type"] == "Hoi4OutputFilename"
            }
            self.assertEqual(len(filename_nodes), 3 if workflow_id == "hoi4_portrait_source" else 1)
            for node in filename_nodes.values():
                source_filename = node["inputs"]["source_filename"]
                if workflow_id == "hoi4_portrait_text_to_image":
                    self.assertEqual(source_filename, "text_to_image.png")
                else:
                    self.assertEqual(source_filename[1], 2)
                    self.assertEqual(api[source_filename[0]]["class_type"], expected_sources[workflow_id])
            for saver in (node for node in api.values() if node["class_type"] in {"SaveImage", "Hoi4SaveDDS"}):
                prefix = saver["inputs"]["filename_prefix"]
                self.assertIn(prefix[0], filename_nodes)


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
            self.assertTrue((comfy_root / "output/hoi4_portraits/156x210/dds").is_dir())

    @unittest.skipIf(sys.platform == "win32", "directory symlinks require elevated Windows privileges")
    def test_runpod_workspace_uses_runtime_input_and_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            comfy_root = self._comfy_root(directory)
            runtime_root = root / "hoi4-portrait-runpod"
            old_input = comfy_root / "input/hoi4_portraits_batch"
            old_input.mkdir(parents=True)
            (old_input / "existing.jpg").write_bytes(b"existing")
            old_output = comfy_root / "output/hoi4_portraits/156x210/dds"
            old_output.mkdir(parents=True)
            (old_output / "existing.dds").write_bytes(b"existing")
            self.assertEqual(configure_workspace.main(["--comfyui-root", str(comfy_root), "--runtime-root", str(runtime_root)]), 0)
            self.assertTrue((comfy_root / "input/hoi4_portraits_batch").is_symlink())
            self.assertTrue((comfy_root / "output/hoi4_portraits").is_symlink())
            self.assertEqual((runtime_root / "input/existing.jpg").read_bytes(), b"existing")
            self.assertEqual((runtime_root / "output/156x210/dds/existing.dds").read_bytes(), b"existing")

    def test_every_variant_install_keeps_all_nine_loras(self) -> None:
        manifest = json.loads((ROOT / "models.json").read_text())
        expected = {
            "hoi4_portrait_flux2_klein_9b_lora_000001750.safetensors",
            "hoi4_portrait_flux2_klein_9b_lora_000002000.safetensors",
            "hoi4_portrait_flux2_klein_9b_lora_000002250.safetensors",
            "hoi4_portrait_flux2_klein_9b_lora_000002500.safetensors",
            "hoi4_portrait_flux2_klein_9b_lora_000002750.safetensors",
            "hoi4_portrait_flux2_klein_9b_lora_000003000.safetensors",
            "adonis_base.safetensors",
            "adonis_refine.safetensors",
            "adonis_post.safetensors",
        }
        for variant in ("full", "fp8", "gguf"):
            entries = download_models._selected_model_entries(
                manifest, set(), {variant}, {"Q5_K_M"}
            )
            installed_loras = {entry["filename"] for entry in entries if entry["directory"] == "loras"}
            self.assertEqual(installed_loras, expected, variant)
            self.assertTrue(
                all(
                    entry["variant"] == "shared"
                    for entry in entries
                    if entry["directory"] == "loras"
                )
            )

    def test_runpod_and_windows_script_defaults_are_fp8(self) -> None:
        runpod = (ROOT / "scripts/install_runpod.sh").read_text()
        windows = (ROOT / "scripts/install_windows.ps1").read_text()
        self.assertIn("VARIANTS=(fp8)", runpod)
        self.assertIn('[string]$Variant = "fp8"', windows)

    def test_windows_wizard_offers_official_comfyui_and_amd_rocm_install(self) -> None:
        wizard = (ROOT / "packaging/windows/main.go").read_text()
        starter = (ROOT / "scripts/start_windows.ps1").read_text()
        self.assertIn("Install ComfyUI automatically now?", wizard)
        self.assertIn("Install ComfyUI with ROCm automatically now?", wizard)
        self.assertIn("ComfyUI_windows_portable_amd.7z", wizard)
        self.assertIn("ComfyUI_windows_portable_nvidia.7z", wizard)
        self.assertIn("amdWindowsROCmSupported", wizard)
        self.assertIn("run_amd_gpu.bat", starter)

    def test_three_ireland_batch_examples_are_bundled(self) -> None:
        self.assertEqual(
            {path.name for path in (ROOT / "examples/batch_input").iterdir() if path.is_file()},
            {"portrait_eamon_de_valera.jpg", "portrait_sean_lemass_1932.png", "portrait_w_t_cosgrave.jpg"},
        )

    def test_every_diffusion_variant_uses_distilled_klein_9b_weights(self) -> None:
        manifest = json.loads((ROOT / "models.json").read_text())
        diffusion_models = [
            entry for entry in manifest["models"]
            if entry["directory"] == "diffusion_models"
        ]
        self.assertEqual({entry["variant"] for entry in diffusion_models}, {"full", "fp8", "gguf"})
        self.assertTrue(all("distilled" in entry["name"].casefold() for entry in diffusion_models))
        self.assertNotIn("klein-base", json.dumps(diffusion_models).casefold())
        self.assertEqual(
            {entry["source"] for entry in diffusion_models if entry["variant"] == "full"},
            {"black-forest-labs/FLUX.2-klein-9B"},
        )
        self.assertEqual(
            {entry["source"] for entry in diffusion_models if entry["variant"] == "fp8"},
            {"black-forest-labs/FLUX.2-klein-9b-fp8"},
        )
        self.assertEqual(
            {entry["source"] for entry in diffusion_models if entry["variant"] == "gguf"},
            {"drends/FLUX.2-klein-9B-GGUF"},
        )

    def test_model_downloader_retries_hugging_face_rate_limits(self) -> None:
        entry = {"filename": "model.safetensors"}
        sleeps: list[int] = []
        with mock.patch.object(
            download_models,
            "_download",
            side_effect=[RuntimeError("HTTP status client error (429 Too Many Requests)"), "downloaded"],
        ) as downloader:
            result = download_models._download_with_retries(
                entry,
                Path("model.safetensors"),
                verify_only=False,
                sleep_fn=sleeps.append,
            )
        self.assertEqual(result, "downloaded")
        self.assertEqual(sleeps, [15])
        self.assertEqual(downloader.call_count, 2)

    def test_model_downloader_does_not_retry_integrity_errors(self) -> None:
        entry = {"filename": "model.safetensors"}
        with mock.patch.object(
            download_models,
            "_download",
            side_effect=RuntimeError("downloaded file failed integrity validation"),
        ) as downloader:
            with self.assertRaisesRegex(RuntimeError, "integrity"):
                download_models._download_with_retries(
                    entry,
                    Path("model.safetensors"),
                    verify_only=False,
                    sleep_fn=lambda _: self.fail("non-network errors must not sleep"),
                )
        self.assertEqual(downloader.call_count, 1)

    def test_model_downloader_serializes_each_source_repository(self) -> None:
        jobs = [
            ({"source": "repo/adonis", "url": "https://example.invalid/a", "filename": "base"}, Path("base")),
            ({"source": "repo/other", "url": "https://example.invalid/b", "filename": "other"}, Path("other")),
            ({"source": "repo/adonis", "url": "https://example.invalid/c", "filename": "post"}, Path("post")),
        ]
        groups = download_models._group_jobs_by_source(jobs)
        self.assertEqual([[entry["filename"] for entry, _ in group] for group in groups], [["base", "post"], ["other"]])

    def test_model_downloader_falls_back_to_https_when_xet_is_rate_limited(self) -> None:
        entry = {
            "filename": "model.safetensors",
            "url": "https://huggingface.co/example/model/resolve/revision/model.safetensors",
            "revision": "revision",
            "source": "example/model",
            "size_bytes": download_models.XET_MIN_SIZE_BYTES,
            "sha256": "unused",
            "requires_huggingface_auth": False,
        }
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / entry["filename"]
            with mock.patch.object(download_models, "_download_from_hub", side_effect=RuntimeError("429 Too Many Requests")), mock.patch.object(download_models, "_download_via_http") as https_download:
                self.assertEqual(download_models._download(entry, destination, verify_only=False), "downloaded")
            https_download.assert_called_once()

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
            source = json.loads((target / "hoi4_portrait_source.json").read_text())
            loader = next(node for node in source["nodes"] if node["type"] == "UNETLoader")
            self.assertEqual(loader["widgets_values"][0], "flux-2-klein-9b-fp8.safetensors")
            gguf = json.loads((target / "hoi4_portrait_source_gguf.json").read_text())
            gguf_loader = next(node for node in gguf["nodes"] if node["type"] == "UnetLoaderGGUF")
            self.assertEqual(gguf_loader["widgets_values"][0], "flux-2-klein-9b-Q5_K_M.gguf")
            self.assertEqual(personal.read_bytes(), before)


@unittest.skipIf(torch is None or Image is None, "requires Torch and Pillow")
class CustomNodeTests(unittest.TestCase):
    @staticmethod
    def _load_module(root: Path):
        fake = types.ModuleType("folder_paths")
        fake.get_input_directory = lambda: str(root / "input")
        fake.get_output_directory = lambda: str(root / "output")
        fake.get_temp_directory = lambda: str(root / "temp")
        fake.get_annotated_filepath = lambda name: str(root / "input" / str(name))

        def save_path(prefix, output_dir, width, height):
            prefix_path = Path(prefix)
            folder = Path(output_dir) / prefix_path.parent
            counter = 1
            while (folder / f"{prefix_path.name}_{counter:05d}.dds").exists():
                counter += 1
            return str(folder), prefix_path.name, counter, "", str(prefix_path.parent)

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

    def test_output_paths_keep_the_input_image_stem(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            module = self._load_module(Path(directory))
            self.assertEqual(
                module._output_filename_prefixes("uploads/My General.Portrait.JPG", "_2"),
                (
                    "hoi4_portraits/1024x1365/My General.Portrait_2",
                    "hoi4_portraits/156x210/My General.Portrait_2",
                    "hoi4_portraits/156x210/dds/My General.Portrait_2",
                ),
            )

    def test_restoration_cache_skips_lazy_adonis_input_for_an_unchanged_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "input").mkdir()
            (root / "input/source.png").write_bytes(b"source-v1")
            module = self._load_module(root)
            prompt = {
                "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "setting": 42}},
                "7": {"class_type": "ClownsharKSampler_Beta", "inputs": {"seed": 42}},
                "9": {"class_type": "Hoi4RestorationCache", "inputs": {"image": ["8", 0], "source_filename": ["1", 2]}},
            }
            cache = module.Hoi4RestorationCache()
            self.assertEqual(cache.check_lazy_status(None, "source.png", prompt, "9"), ["image"])
            image = torch.rand((1, 64, 48, 3), dtype=torch.float32)
            saved = cache.reuse(image, "source.png", prompt, "9")[0]
            self.assertIs(saved, image)
            self.assertEqual(cache.check_lazy_status(None, "source.png", prompt, "9"), [])
            loaded = cache.reuse(None, "source.png", prompt, "9")[0]
            self.assertTrue(torch.equal(loaded, image))
            changed_prompt = json.loads(json.dumps(prompt))
            changed_prompt["7"]["inputs"]["seed"] = 43
            self.assertEqual(cache.check_lazy_status(None, "source.png", changed_prompt, "9"), ["image"])

    def test_dds_matches_vanilla_argb8888_portrait_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module = self._load_module(root)
            self.assertIs(module.Hoi4SaveDDS.OUTPUT_NODE, True)
            image = torch.rand((1, 210, 156, 3), dtype=torch.float32)
            module.Hoi4SaveDDS().save(image, "hoi4_portraits/156x210/dds/test", "argb8888")
            dds = next((root / "output/hoi4_portraits/156x210/dds").glob("*.dds"))
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

    def test_dds_output_node_saves_every_batch_item_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module = self._load_module(root)
            images = torch.rand((3, 210, 156, 3), dtype=torch.float32)
            saver = module.Hoi4SaveDDS()
            saver.save(images, "hoi4_portraits/156x210/dds/batch_test", "argb8888")
            saver.save(images[:1], "hoi4_portraits/156x210/dds/batch_test", "argb8888")
            files = sorted((root / "output/hoi4_portraits/156x210/dds").glob("batch_test_*.dds"))
            self.assertEqual([path.name for path in files], [
                "batch_test_00001.dds",
                "batch_test_00002.dds",
                "batch_test_00003.dds",
                "batch_test_00004.dds",
            ])
            self.assertTrue(all(path.read_bytes()[:4] == b"DDS " for path in files))

    def test_batch_input_loads_every_matching_file_in_stable_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            batch = root / "input/hoi4_portraits_batch"
            batch.mkdir(parents=True)
            Image.new("RGB", (18, 24), (255, 0, 0)).save(batch / "b.JPG")
            Image.new("RGB", (20, 30), (0, 255, 0)).save(batch / "A.png")
            Image.new("RGB", (22, 28), (0, 0, 255)).save(batch / "c.webp")
            (batch / "ignore.txt").write_text("not an image")
            module = self._load_module(root)
            self.assertTrue(math.isnan(module.Hoi4BatchInput.IS_CHANGED("hoi4_portraits_batch", "*.png")))
            images, masks, names = module.Hoi4BatchInput().load_batch(
                "hoi4_portraits_batch", "*.png;*.jpg;*.jpeg;*.webp"
            )
            self.assertEqual(names, [
                "hoi4_portraits_batch/A.png",
                "hoi4_portraits_batch/b.JPG",
                "hoi4_portraits_batch/c.webp",
            ])
            self.assertEqual([tuple(image.shape) for image in images], [
                (1, 30, 20, 3),
                (1, 24, 18, 3),
                (1, 28, 22, 3),
            ])
            self.assertEqual([tuple(mask.shape) for mask in masks], [
                (1, 30, 20),
                (1, 24, 18),
                (1, 28, 22),
            ])
            with self.assertRaises(ValueError):
                module.Hoi4BatchInput().load_batch("../outside", "*.png")

    def test_batch_input_returns_list_items_for_one_by_one_execution(self) -> None:
        source = (ROOT / "custom_nodes/hoi4_portraits/__init__.py").read_text()
        self.assertIn("OUTPUT_IS_LIST = (True, True, True)", source)
        self.assertNotIn('"Hoi4ModelStack": Hoi4ModelStack', source)
        self.assertNotIn('"Hoi4FinalOutput": Hoi4FinalOutput', source)
        self.assertNotIn("Hoi4PortraitSampler", source)
        self.assertIn('"Hoi4SetupGuide": Hoi4SetupGuide', source)
        self.assertIn('"Hoi4BackgroundReplace": Hoi4BackgroundReplace', source)
        self.assertIn('"Hoi4RestorationCache": Hoi4RestorationCache', source)


if __name__ == "__main__":
    unittest.main()
