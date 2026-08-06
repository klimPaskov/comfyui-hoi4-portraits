from __future__ import annotations

import contextlib
import hashlib
import io
import json
import re
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts import build_workflows, install_workflows, validate_workflows
from scripts.release import build_release_artifacts

ROOT = Path(__file__).resolve().parents[1]


def _editor_nodes(ui: dict) -> list[dict]:
    return ui.get("nodes", [])


class WorkflowTests(unittest.TestCase):
    def test_committed_workflows_match_deterministic_builder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            build_workflows.build_all(temporary_root)
            generated = temporary_root / "workflows"
            committed = ROOT / "workflows"
            self.assertEqual(
                sorted(path.name for path in generated.glob("*.json")),
                sorted(path.name for path in committed.glob("*.json")),
            )
            for generated_path in generated.glob("*.json"):
                self.assertEqual(
                    generated_path.read_bytes(),
                    (committed / generated_path.name).read_bytes(),
                    generated_path.name,
                )

    def test_structural_and_layout_validation_passes(self) -> None:
        result = validate_workflows.validate_all(ROOT)
        self.assertEqual(result["status"], "PASS", result["errors"])
        self.assertEqual(len(result["workflows"]), 12)

    def test_manifest_workflow_files_exist(self) -> None:
        manifest = json.loads((ROOT / "workflows" / "manifest.json").read_text())
        self.assertEqual(manifest["schema_version"], "2.6.1")
        for item in manifest["workflows"]:
            self.assertTrue((ROOT / item["workflow_json"]).is_file())
            self.assertTrue((ROOT / item["api_json"]).is_file())

    def test_editor_model_urls_are_revision_pinned(self) -> None:
        for workflow in (ROOT / "workflows").glob("*.json"):
            self.assertNotIn("/resolve/main/", workflow.read_text(encoding="utf-8"), workflow.name)

    def test_identity_runtime_uses_compatible_onnx_dependencies(self) -> None:
        installers = [
            ROOT / "scripts" / "install_pulid_flux2.sh",
            ROOT / "scripts" / "install_windows.ps1",
        ]
        for installer in installers:
            text = installer.read_text(encoding="utf-8")
            self.assertIn("onnx==1.22.0", text, installer.name)
            self.assertIn("ml_dtypes==0.5.4", text, installer.name)
            self.assertNotIn("ml_dtypes==0.3.2", text, installer.name)
            self.assertIn("float4_e2m1fn", text, installer.name)

    def test_selected_lora_and_sampling_defaults(self) -> None:
        self.assertEqual(build_workflows.STYLE_LORA_STRENGTH, 1.0)
        self.assertEqual(build_workflows.SOURCE_STYLE_DENOISE, 1.0)
        self.assertEqual(build_workflows.DEFAULT_STEPS, 6)
        self.assertEqual(build_workflows.DEFAULT_CFG, 1.0)
        self.assertEqual(build_workflows.DEFAULT_GUIDANCE, 1.0)
        for workflow in (ROOT / "workflows").glob("*.api.json"):
            api = json.loads(workflow.read_text(encoding="utf-8"))
            is_source = "_source" in workflow.name
            loras = [
                node
                for node in api.values()
                if node["class_type"] == "LoraLoaderModelOnly"
                and str(node["inputs"].get("lora_name", "")).startswith("hoi4_portrait_flux2_klein9b_lora_")
            ]
            if workflow.name.endswith("processing_only.api.json"):
                self.assertEqual(loras, [], workflow.name)
            else:
                self.assertEqual(len(loras), 1, workflow.name)
                self.assertEqual(loras[0]["inputs"]["strength_model"], 1.0, workflow.name)
                self.assertEqual(
                    loras[0]["inputs"]["lora_name"],
                    "hoi4_portrait_flux2_klein9b_lora_000002250.safetensors",
                    workflow.name,
                )
                self.assertNotIn("19", api, workflow.name)
            portrait_samplers = {
                node_id: node["inputs"]
                for node_id, node in api.items()
                if node["class_type"] == "Flux2PortraitSampler"
            }
            if is_source:
                self.assertEqual(
                    {node_id: inputs["steps"] for node_id, inputs in portrait_samplers.items()},
                    {"30": 6, "50": 6, "70": 4, "90": 8},
                    workflow.name,
                )
                self.assertEqual(
                    {node_id: inputs["sampler_name"] for node_id, inputs in portrait_samplers.items()},
                    {"30": "euler", "50": "euler", "70": "res_2s", "90": "res_2m"},
                    workflow.name,
                )
            elif workflow.name.endswith("text_to_image.api.json"):
                self.assertEqual(set(portrait_samplers), {"27"}, workflow.name)
            else:
                self.assertEqual(set(portrait_samplers), {"30"}, workflow.name)
            self.assertTrue(all(node["cfg"] == 1.0 for node in portrait_samplers.values()), workflow.name)
            self.assertTrue(all(node["guidance"] == 1.0 for node in portrait_samplers.values()), workflow.name)
            self.assertTrue(all(node["denoise"] == 1.0 for node in portrait_samplers.values()), workflow.name)
            self.assertTrue(all(node["width"] == 1024 for node in portrait_samplers.values()), workflow.name)
            self.assertTrue(all(node["height"] == 1365 for node in portrait_samplers.values()), workflow.name)
            if is_source:
                self.assertIs(api["32"]["inputs"]["switch"], True)
                expected_prompt = build_workflows.STYLE_PROMPT
                if "refcontrol_lineart" in workflow.name:
                    expected_prompt = expected_prompt.replace("hoi4_portrait,", "hoi4_portrait, refcontrol,", 1)
                self.assertEqual(api["40"]["inputs"]["text"], expected_prompt)
                for prompt_id, reference_id in (("40", "43"), ("60", "63"), ("80", "83")):
                    self.assertEqual(api[prompt_id]["inputs"]["text"], expected_prompt)
                    self.assertEqual(api[reference_id]["inputs"]["conditioning"], [prompt_id, 0])
                    if workflow.name.endswith("9b_source.api.json"):
                        self.assertEqual(api[reference_id]["class_type"], "ReferenceLatent")
                        self.assertEqual(api[reference_id]["inputs"]["latent"], [str(int(prompt_id) + 2), 0])
                    else:
                        self.assertEqual(api[reference_id]["class_type"], "Flux2KleinMultiReferenceLatent")
                        start = int(prompt_id)
                        self.assertEqual(api[reference_id]["inputs"]["latent_1"], [str(start + 5), 0])
                        self.assertEqual(api[reference_id]["inputs"]["latent_2"], [str(start + 6), 0])
                if workflow.name.endswith("9b_source.api.json"):
                    self.assertNotIn("190", api)
                    self.assertTrue(all(api[node_id]["inputs"]["model"] == ["4", 0] for node_id in ("50", "70", "90")))

    def test_feature_toggle_nodes_are_red_and_use_expected_defaults(self) -> None:
        for workflow in (ROOT / "workflows").glob("*.json"):
            if workflow.name.endswith(".api.json"):
                continue
            ui = json.loads(workflow.read_text(encoding="utf-8"))
            if "nodes" not in ui:
                continue
            toggles = [
                node
                for node in _editor_nodes(ui)
                if node["title"].startswith("Toggle FLUX restoration")
                or node["title"].startswith("Toggle replacement background")
                or node["title"].startswith("Toggle face processing")
            ]
            self.assertTrue(toggles, workflow.name)
            for node in toggles:
                self.assertEqual(node["color"], "#b91c1c", f"{workflow.name}: {node['title']}")
                self.assertEqual(node["bgcolor"], "#7f1d1d", f"{workflow.name}: {node['title']}")
                expected = not node["title"].startswith("Toggle replacement background")
                self.assertIs(node["widgets_values"][0], expected, f"{workflow.name}: {node['title']}")

    def test_restoration_seed_is_fixed_and_candidate_seeds_randomize(self) -> None:
        filenames = ["hoi4_portrait_processing_only.json"] + sorted(
            path.name
            for path in (ROOT / "workflows").glob("hoi4_portrait_flux2_klein_9b_source*.json")
            if not path.name.endswith(".api.json")
        )
        for filename in filenames:
            ui = json.loads((ROOT / "workflows" / filename).read_text(encoding="utf-8"))
            nodes = {node["id"]: node for node in _editor_nodes(ui)}
            self.assertEqual(nodes[30]["widgets_values"][:2], [17, "fixed"], filename)
            if "_source" in filename:
                for node_id in (50, 70, 90):
                    self.assertEqual(nodes[node_id]["widgets_values"][1], "randomize", filename)

    def test_source_graphs_crop_before_esrgan_and_preserve_source_latent(self) -> None:
        sources = sorted((ROOT / "workflows").glob("hoi4_portrait_flux2_klein_9b_source*.api.json"))
        for name, path in [("source", path) for path in sources] + [
            ("processing", ROOT / "workflows" / "hoi4_portrait_processing_only.api.json")
        ]:
            api = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(api["9"]["class_type"], "ImageScaleToMaxDimension")
            self.assertEqual(api["9"]["inputs"]["image"], ["5", 0])
            self.assertEqual(api["13"]["class_type"], "MediaPipeFaceLandmarker")
            self.assertEqual(api["13"]["inputs"]["image"], ["9", 0])
            self.assertEqual(api["13"]["inputs"]["detector_variant"], "both")
            self.assertEqual(api["11"]["class_type"], "AdaptivePortraitCrop")
            self.assertEqual(api["11"]["inputs"]["face_bboxes"], ["13", 1])
            self.assertEqual(api["11"]["inputs"]["subject_mask"], ["156", 0])
            self.assertEqual(api["11"]["inputs"]["zoom"], 0.9)
            self.assertIs(api["11"]["inputs"]["preserve_headwear"], True)
            self.assertEqual(api["156"]["inputs"]["image"], ["9", 0])
            self.assertEqual(api["15"]["class_type"], "PrimitiveBoundingBox")
            self.assertEqual(api["16"]["inputs"]["bboxes"], ["15", 0])
            self.assertEqual(api["17"]["class_type"], "ComfySwitchNode")
            self.assertTrue(api["17"]["inputs"]["switch"])
            self.assertEqual(api["17"]["inputs"]["on_false"], ["9", 0])
            self.assertEqual(api["17"]["inputs"]["on_true"], ["18", 0])
            self.assertFalse(api["18"]["inputs"]["switch"])
            self.assertEqual(api["18"]["inputs"]["on_false"], ["11", 0])
            self.assertEqual(api["18"]["inputs"]["on_true"], ["16", 0])
            self.assertEqual(api["7"]["inputs"]["image"], ["17", 0])
            if "identity_test_" not in path.name:
                self.assertNotIn("EmptyFlux2LatentImage", {node["class_type"] for node in api.values()})
            if name == "source":
                for latent_id, sampler_id in (("42", "50"), ("62", "70"), ("82", "90")):
                    if "identity_test_" in path.name:
                        self.assertEqual(api[latent_id]["class_type"], "EmptyFlux2LatentImage")
                    else:
                        self.assertEqual(api[latent_id]["inputs"]["pixels"], ["32", 0])
                    self.assertEqual(api[sampler_id]["inputs"]["latent_image"], [latent_id, 0])
                self.assertEqual(api["119"]["class_type"], "PrimitiveBoolean")
                self.assertFalse(api["119"]["inputs"]["value"])
                final_ids = ("200", "210", "220") if "identity_test_composite" in path.name else ("54", "74", "94")
                for switch_id, final_id in zip(("125", "135", "145"), final_ids):
                    self.assertEqual(api[switch_id]["inputs"]["switch"], ["119", 0])
                    self.assertEqual(api[switch_id]["inputs"]["on_false"], [final_id, 0])
            else:
                self.assertNotIn("4", api)
                self.assertEqual(api["30"]["inputs"]["latent_image"], ["22", 0])

    def test_adaptive_crop_exposes_optional_headwear_preservation(self) -> None:
        source = (ROOT / "custom_nodes" / "hoi4_portraits" / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('"preserve_headwear": (', source)
        self.assertIn('"default": True', source)
        self.assertIn("if preserve_headwear and count", source)
        self.assertIn("0.88 if preserve_headwear else 0.52", source)

    def test_source_workflow_has_three_final_candidates_and_one_restoration(self) -> None:
        api = json.loads(
            (ROOT / "workflows" / "hoi4_portrait_flux2_klein_9b_source.api.json").read_text(encoding="utf-8")
        )
        self.assertEqual(build_workflows.SOURCE_CANDIDATE_COUNT, 3)
        self.assertEqual([api[node_id]["inputs"]["seed"] for node_id in ("50", "70", "90")], [42, 43, 44])
        self.assertEqual(sum(node["class_type"] == "Flux2PortraitSampler" for node in api.values()), 4)
        self.assertEqual(sum(node["class_type"] == "VAEDecode" for node in api.values()), 4)
        self.assertEqual(sum(node["class_type"] == "RemoveBackground" for node in api.values()), 4)
        self.assertEqual(sum(node["class_type"] == "SaveImage" for node in api.values()), 6)

    def test_master_and_game_output_dimensions(self) -> None:
        for path in (ROOT / "workflows").glob("*.api.json"):
            api = json.loads(path.read_text(encoding="utf-8"))
            master_nodes = [
                node
                for node in api.values()
                if node["class_type"] == "ImageScale"
                and node["inputs"].get("width") == 1024
                and node["inputs"].get("height") == 1365
            ]
            self.assertTrue(master_nodes, path.name)
            game_nodes = [
                node
                for node in api.values()
                if node["class_type"] == "ImageScale"
                and node["inputs"].get("width") == 156
                and node["inputs"].get("height") == 210
            ]
            self.assertTrue(game_nodes, path.name)
            self.assertTrue(all(node["inputs"].get("crop") == "center" for node in game_nodes), path.name)

    def test_identity_comparison_pack_is_complete_and_isolated(self) -> None:
        expected = {
            "native",
            "feature_mid",
            "feature_hard",
            "dx_consistency",
            "lcs_consistency",
            "sameface",
            "refcontrol_lineart",
            "pulid",
            "composite",
        }
        files = {
            path.stem.removesuffix(".api").split("identity_test_", 1)[1]: path
            for path in (ROOT / "workflows").glob("*source_identity_test_*.api.json")
        }
        self.assertEqual(set(files), expected)
        for method, path in files.items():
            api = json.loads(path.read_text(encoding="utf-8"))
            for latent_id, sampler_id in (("42", "50"), ("62", "70"), ("82", "90")):
                self.assertEqual(api[latent_id]["class_type"], "EmptyFlux2LatentImage", method)
                self.assertEqual(api[latent_id]["inputs"], {"width": 1024, "height": 1365, "batch_size": 1}, method)
                self.assertEqual(api[sampler_id]["inputs"]["latent_image"], [latent_id, 0], method)
            if method in {"feature_mid", "feature_hard"}:
                self.assertEqual(api["190"]["class_type"], "IdentityFeatureTransferFinal")
                self.assertEqual(api["190"]["inputs"]["preset"], "custom")
                self.assertEqual(api["192"]["class_type"], "PortraitIdentityMask")
                self.assertEqual(api["190"]["inputs"]["subject_mask_1"], ["192", 0])
                self.assertEqual(api["190"]["inputs"]["subject_mask_2"], ["192", 0])
            if method == "pulid":
                self.assertEqual(api["190"]["class_type"], "PuLIDModelLoader")
                self.assertEqual(api["193"]["inputs"]["provider"], "CUDA")
                self.assertEqual(api["194"]["inputs"]["strength"], 1.4)
                self.assertEqual(api["50"]["inputs"]["model"], ["194", 0])
            if method == "refcontrol_lineart":
                self.assertEqual(api["192"]["class_type"], "Canny")
                self.assertIn("refcontrol", api["40"]["inputs"]["text"])
                self.assertEqual(api["45"]["inputs"]["pixels"], ["192", 0])
                self.assertEqual(api["46"]["inputs"]["pixels"], ["32", 0])
            if method == "composite":
                self.assertEqual([api[node]["class_type"] for node in ("200", "210", "220")], ["KleinEditComposite"] * 3)
                self.assertEqual(api["125"]["inputs"]["on_false"], ["200", 0])

    def test_editor_workflows_are_flat_and_fully_visible(self) -> None:
        for workflow in (ROOT / "workflows").glob("*.json"):
            if workflow.name.endswith(".api.json") or workflow.name == "manifest.json":
                continue
            ui = json.loads(workflow.read_text(encoding="utf-8"))
            self.assertNotIn("definitions", ui, workflow.name)
            self.assertGreater(len(ui["nodes"]), len(ui["groups"]), workflow.name)
            self.assertEqual(ui["extra"]["editor_layout"], "flat_grouped_canvas", workflow.name)

    def test_person_prompt_policy_allows_hairstyle_but_rejects_style(self) -> None:
        self.assertEqual(validate_workflows._non_person_prompt_terms("a different hairstyle"), [])
        self.assertEqual(validate_workflows._non_person_prompt_terms("use a painted style"), ["style"])


class InstallerAndModelTests(unittest.TestCase):
    def test_installer_copies_all_workflows_and_project_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            comfy_root = Path(directory)
            (comfy_root / "main.py").touch()
            legacy_node = comfy_root / "custom_nodes/adaptive_portrait_crop"
            legacy_node.mkdir(parents=True)
            (legacy_node / "__init__.py").write_text("# previous package name\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                result = install_workflows.main(["--comfyui-root", str(comfy_root)])
            self.assertEqual(result, 0)
            installed = list((comfy_root / "user/default/workflows/hoi4_portraits").glob("*.json"))
            self.assertEqual(len(installed), 12)
            self.assertTrue((comfy_root / "input/source_portrait.jpg").is_file())
            self.assertTrue((comfy_root / "custom_nodes/hoi4_portraits/__init__.py").is_file())
            self.assertTrue((comfy_root / "custom_nodes/hoi4_portraits/requirements.txt").is_file())
            self.assertFalse((comfy_root / "custom_nodes/adaptive_portrait_crop").exists())

    def test_model_manifest_is_pinned_and_unique(self) -> None:
        data = json.loads((ROOT / "models.json").read_text())
        self.assertEqual(data["schema_version"], "2.0.0")
        models = data["models"]
        self.assertEqual(len(models), 21)
        self.assertEqual(sum(entry["size_bytes"] for entry in models), 24057010868)
        filenames = [entry["filename"] for entry in models]
        self.assertEqual(len(filenames), len(set(filenames)))
        retrained = [name for name in filenames if name.startswith("hoi4_portrait_flux2_klein9b_lora_")]
        self.assertEqual(
            retrained,
            [
                "hoi4_portrait_flux2_klein9b_lora_000002000.safetensors",
                "hoi4_portrait_flux2_klein9b_lora_000002250.safetensors",
                "hoi4_portrait_flux2_klein9b_lora_000002500.safetensors",
            ],
        )
        self.assertIn("adonis_base.safetensors", filenames)
        for entry in models:
            self.assertRegex(entry["revision"], r"^[0-9a-f]{40}$")
            self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(entry["size_bytes"], 0)
            self.assertTrue(entry["url"].startswith("https://"))

    def test_release_package_selection_excludes_model_weights(self) -> None:
        selected = build_release_artifacts._selected_files()
        forbidden = build_release_artifacts.MODEL_SUFFIXES
        self.assertFalse(any(path.suffix.casefold() in forbidden for path in selected))
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "release.zip"
            count = build_release_artifacts._build_zip(archive_path, selected, "v-test")
            with zipfile.ZipFile(archive_path) as archive:
                manifest = json.loads(archive.read("RELEASE_MANIFEST.json"))
            self.assertEqual(count, len(selected))
            self.assertIsInstance(manifest["files"], list)
            self.assertNotIn("sha256", json.dumps(manifest).casefold())

    def test_runpod_release_contains_only_runtime_files(self) -> None:
        files = build_release_artifacts._runpod_files()
        self.assertTrue(files)
        self.assertFalse(any(path.endswith(".md") for path in files))
        self.assertFalse(any(".api.json" in path for path in files))
        self.assertEqual(
            {path for path in files if path.startswith("scripts/")},
            {f"scripts/{name}" for name in build_release_artifacts.RUNPOD_SCRIPTS},
        )
        manifest = json.loads((ROOT / "workflows" / "manifest.json").read_text(encoding="utf-8"))
        expected_workflows = {"workflows/manifest.json"} | {
            item["workflow_json"] for item in manifest["workflows"]
        }
        self.assertEqual({path for path in files if path.startswith("workflows/")}, expected_workflows)
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "runpod.tar.gz"
            build_release_artifacts._build_runpod_archive(archive_path, files)
            with tarfile.open(archive_path, "r:gz") as archive:
                self.assertEqual(set(archive.getnames()), set(files))

    def test_windows_release_extractor_sources_are_current(self) -> None:
        source = ROOT / "packaging" / "windows" / "main.go"
        self.assertTrue((ROOT / "packaging" / "windows" / "go.mod").is_file())
        contents = source.read_text(encoding="utf-8")
        self.assertIn('"docs", "local-install.md"', contents)
        self.assertIn("hoi4_portraits node pack", contents.casefold())
        self.assertNotIn("setup-with-coding-agent.md", contents)

    def test_sampler_extension_is_pinned_in_installers(self) -> None:
        revision = "e716cd1cb2c5cff90131bf4914b75b75a0489d48"
        shell = (ROOT / "scripts" / "install_res4lyf.sh").read_text(encoding="utf-8")
        runpod = (ROOT / "scripts" / "install_runpod.sh").read_text(encoding="utf-8")
        windows = (ROOT / "scripts" / "install_windows.ps1").read_text(encoding="utf-8")
        self.assertIn("https://github.com/ClownsharkBatwing/RES4LYF.git", shell)
        self.assertIn(revision, shell)
        self.assertIn('getattr(work_device, \\"type\\", str(work_device)) == \\"mps\\"', shell)
        self.assertIn("install_res4lyf.sh", runpod)
        self.assertIn("validate_comfyui_registry.py", (ROOT / "scripts" / "start_runpod.sh").read_text())
        self.assertIn(revision, windows)
        self.assertIn('/workspace/runpod-slim/venv/bin/python', runpod)
        self.assertIn('AdaptivePortraitCrop did not register', runpod)
        self.assertIn('Flux2PortraitSampler did not register', runpod)
        self.assertIn("git -C \"${RES4LYF_DIR}\" grep -q 'res_2s'", runpod)
        self.assertIn("git -C \"${RES4LYF_DIR}\" grep -q 'res_2m'", runpod)
        self.assertNotIn("import custom_nodes.RES4LYF", runpod)
        enhancer = (ROOT / "scripts" / "install_flux2_klein_enhancer.sh").read_text(encoding="utf-8")
        self.assertIn("https://github.com/capitan01R/ComfyUI-Flux2Klein-Enhancer.git", enhancer)
        self.assertIn("6804643bff9a20926106427ff08d5b1bd2e49861", enhancer)
        self.assertIn("install_flux2_klein_enhancer.sh", runpod)
        self.assertIn("install_pulid_flux2.sh", runpod)
        self.assertIn("install_klein_edit_composite.sh", runpod)
        pulid = (ROOT / "scripts" / "install_pulid_flux2.sh").read_text(encoding="utf-8")
        composite = (ROOT / "scripts" / "install_klein_edit_composite.sh").read_text(encoding="utf-8")
        self.assertIn("3a0a3f5f18260fc914f96a8c7f0f23c835e881cd", pulid)
        self.assertIn("1505bc58d38abf5411457804ed4923e83f986eee", composite)


class DocumentationTests(unittest.TestCase):
    LINK = re.compile(r"\[[^]]+\]\(([^)]+)\)")
    CODE_BLOCK = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)

    def test_internal_markdown_links_exist(self) -> None:
        failures: list[str] = []
        markdown_files = [*ROOT.glob("*.md"), *(ROOT / "docs").rglob("*.md"), *(ROOT / "backgrounds").glob("*.md"), *(ROOT / "loras").glob("*.md")]
        for document in markdown_files:
            for target in self.LINK.findall(document.read_text(encoding="utf-8")):
                target = target.strip().strip("<>")
                if "://" in target or target.startswith(("#", "mailto:")):
                    continue
                file_target = target.split("#", 1)[0]
                if file_target and not (document.parent / file_target).resolve().exists():
                    failures.append(f"{document.relative_to(ROOT)} -> {target}")
        self.assertEqual(failures, [])

    def test_readme_default_table_contains_only_current_workflows(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        section = readme.split("## Workflows", 1)[1]
        table_rows = [line for line in section.splitlines() if line.startswith("|")]
        table = "\n".join(table_rows)
        self.assertEqual(len(table_rows), 5)  # header, separator, and three workflow rows
        self.assertIn("workflows/hoi4_portrait_flux2_klein_9b_source.json", table_rows[2])
        self.assertIn("workflows/hoi4_portrait_flux2_klein_9b_text_to_image.json", table_rows[3])
        self.assertIn("workflows/hoi4_portrait_processing_only.json", table_rows[4])
        self.assertEqual(table.count("workflows/"), 3)
        self.assertNotIn("krea", table.casefold())

    def test_readme_contains_current_gallery_and_example_prompts(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for filename in (
            "source-processing-01.jpg",
            "source-processing-02.jpg",
            "source-processing-03.jpg",
        ):
            self.assertEqual(readme.count(f"docs/assets/test-runs/{filename}"), 1)
        self.assertEqual(readme.count("docs/assets/test-runs/source-processing-restoration-off-"), 3)
        self.assertIn("docs/assets/test-runs/random-portraits.jpg", readme)
        self.assertIn("docs/assets/test-runs/step-comparison.jpg", readme)
        self.assertNotIn("docs/assets/test-runs/sampler-comparison.png", readme)
        self.assertNotIn("Prompt used for this example:", readme)
        for obsolete in (
            "full-restoration-01.jpg",
            "full-restoration-02.jpg",
            "full-restoration-03.jpg",
            "full-restoration-04.jpg",
            "full-restoration-05.jpg",
            "settings-matrix.jpg",
        ):
            self.assertFalse((ROOT / "docs" / "assets" / "test-runs" / obsolete).exists(), obsolete)
        for current in (
            "source-processing-01.jpg",
            "source-processing-02.jpg",
            "source-processing-03.jpg",
        ):
            self.assertTrue((ROOT / "docs" / "assets" / "test-runs" / current).is_file(), current)

    def test_readme_gallery_uses_the_requested_color_safe_generations(self) -> None:
        expected = {
            "source-processing-01.jpg": "9f6c3f8c4de1",
            "source-processing-02.jpg": "ebb6e4d72834",
            "source-processing-03.jpg": "4b86bca0ec54",
            "source-processing-restoration-off-01.jpg": "6fdedc7fee71",
            "source-processing-restoration-off-02.jpg": "ad97673a1454",
            "source-processing-restoration-off-03.jpg": "7da73d2632d9",
        }
        for filename, prefix in expected.items():
            digest = hashlib.sha256((ROOT / "docs/assets/test-runs" / filename).read_bytes()).hexdigest()
            self.assertTrue(digest.startswith(prefix), filename)

    def test_readme_contains_source_workflow_visual_walkthrough(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        screenshots = (
            "source-workflow-overview.jpg",
            "step-1-source-processing.jpg",
            "step-2-model-setup.jpg",
            "step-3-flux-restoration.jpg",
            "step-4-lora-styling.jpg",
            "step-5-background-replacement.jpg",
            "step-6-preview-and-save.jpg",
        )
        for screenshot in screenshots:
            asset = ROOT / "docs" / "assets" / "workflows" / screenshot
            self.assertTrue(asset.is_file(), screenshot)
            self.assertIn(f"docs/assets/workflows/{screenshot}", readme)

    def test_user_guides_use_present_state_language(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertTrue(readme.splitlines()[6].startswith("Create identity-preserving Hearts of Iron IV-style"))
        self.assertNotIn("Clean ComfyUI workflows", readme)
        documents = [ROOT / "README.md", *(ROOT / "docs").glob("*.md"), *(ROOT / "loras").glob("*.md")]
        self.assertFalse(any(re.search(r"sha-?256|checksum", path.read_text(encoding="utf-8"), re.IGNORECASE) for path in documents))
        forbidden = re.compile(
            r"\b(earlier project|previously verified|current workflows|newly trained|now use|what changed)\b",
            re.IGNORECASE,
        )
        for document in documents:
            self.assertIsNone(forbidden.search(document.read_text(encoding="utf-8")), document.name)

        cloud_only_terms = re.compile(
            r"\b(core[- ]node|built-in (?:ComfyUI )?nodes?|custom[- ]nodes?)\b",
            re.IGNORECASE,
        )
        general_guides = [ROOT / "README.md", *(ROOT / "docs").glob("*.md")]
        for document in general_guides:
            if document.name != "comfy-cloud.md":
                self.assertIsNone(cloud_only_terms.search(document.read_text(encoding="utf-8")), document.name)

    def test_documented_positive_prompt_examples_are_person_only(self) -> None:
        documents = [
            ROOT / "README.md",
            ROOT / "loras" / "HUGGINGFACE_MODEL_CARD.md",
        ]
        forbidden = re.compile(
            r"\b(hearts of iron|grand-strategy|hand-painted|background|lighting|"
            r"render(?:ing|ed)?|transform(?:ation|ed)?|preserv(?:e|ation)|style)\b",
            re.IGNORECASE,
        )
        examples = []
        for document in documents:
            for block in self.CODE_BLOCK.findall(document.read_text(encoding="utf-8")):
                if block.lstrip().startswith("hoi4_portrait,"):
                    examples.append((document, block.strip()))
        self.assertGreaterEqual(len(examples), 3)
        for document, example in examples:
            self.assertIsNone(forbidden.search(example), f"{document.name}: {example}")
            self.assertIsNone(
                re.search(r"\b(crop|chest up|shoulders up|head-and-shoulders)\b", example, re.IGNORECASE),
                f"{document.name}: prompt must not repeat workflow framing",
            )


if __name__ == "__main__":
    unittest.main()
