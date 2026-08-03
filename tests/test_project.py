from __future__ import annotations

import contextlib
import hashlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path

from scripts import build_workflows, install_workflows, validate_workflows
from scripts.release import build_release_artifacts

ROOT = Path(__file__).resolve().parents[1]


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
        self.assertEqual(len(result["workflows"]), 3)

    def test_manifest_hashes_match_files(self) -> None:
        manifest = json.loads((ROOT / "workflows" / "manifest.json").read_text())
        self.assertEqual(manifest["schema_version"], "2.3.0")
        for item in manifest["workflows"]:
            for path_key, digest_key in (("workflow_json", "sha256"), ("api_json", "api_sha256")):
                data = (ROOT / item[path_key]).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), item[digest_key])

    def test_editor_model_urls_are_revision_pinned(self) -> None:
        for workflow in (ROOT / "workflows").glob("*.json"):
            self.assertNotIn("/resolve/main/", workflow.read_text(encoding="utf-8"), workflow.name)

    def test_autoprompter_output_contract_is_person_only(self) -> None:
        instruction = (ROOT / "prompts" / "autoprompter_instruction.txt").read_text(encoding="utf-8").casefold()
        self.assertIn("describe only broad", instruction)
        self.assertNotIn("workflow", instruction)
        self.assertNotIn("comfyui", instruction)
        for forbidden in (
            "transform the supplied",
            "grand-strategy portrait",
            "hand-painted 1930s",
            "background description",
        ):
            self.assertNotIn(forbidden, instruction)
        self.assertIn("monochrome or sepia sources, do not invent colors", instruction)

    def test_selected_lora_and_sampling_defaults(self) -> None:
        self.assertEqual(build_workflows.STYLE_LORA_STRENGTH, 0.75)
        self.assertEqual(build_workflows.DEFAULT_STEPS, 8)
        for workflow in (ROOT / "workflows").glob("*.api.json"):
            api = json.loads(workflow.read_text(encoding="utf-8"))
            loras = [node for node in api.values() if node["class_type"] == "LoraLoaderModelOnly"]
            if workflow.name.endswith("processing_only.api.json"):
                self.assertEqual(loras, [], workflow.name)
            else:
                self.assertEqual(len(loras), 1, workflow.name)
                self.assertEqual(loras[0]["inputs"]["strength_model"], 0.75, workflow.name)
            schedules = [node for node in api.values() if node["class_type"] == "Flux2Scheduler"]
            self.assertTrue(schedules, workflow.name)
            self.assertTrue(all(node["inputs"]["steps"] == 8 for node in schedules), workflow.name)
            if workflow.name.endswith("source.api.json"):
                self.assertIs(api["32"]["inputs"]["switch"], False)

    def test_source_graphs_crop_before_esrgan_and_preserve_source_latent(self) -> None:
        for name, path in (
            ("source", ROOT / "workflows" / "hoi4_portrait_flux2_klein_9b_source.api.json"),
            ("processing", ROOT / "workflows" / "hoi4_portrait_processing_only.api.json"),
        ):
            api = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(api["11"]["class_type"], "ImageCropV2")
            self.assertEqual(api["11"]["inputs"]["image"], ["5", 0])
            self.assertEqual(api["11"]["inputs"]["crop_region"], ["9", 0])
            self.assertEqual(api["7"]["inputs"]["image"], ["11", 0])
            self.assertNotIn("EmptyFlux2LatentImage", {node["class_type"] for node in api.values()})
            if name == "source":
                self.assertEqual(api["50"]["inputs"]["latent_image"], ["42", 0])
            else:
                self.assertNotIn("4", api)
                self.assertEqual(api["30"]["inputs"]["latent_image"], ["22", 0])

    def test_person_prompt_policy_allows_hairstyle_but_rejects_style(self) -> None:
        self.assertEqual(validate_workflows._non_person_prompt_terms("a different hairstyle"), [])
        self.assertEqual(validate_workflows._non_person_prompt_terms("use a painted style"), ["style"])


class InstallerAndModelTests(unittest.TestCase):
    def test_installer_copies_three_workflows_without_custom_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            comfy_root = Path(directory)
            (comfy_root / "main.py").touch()
            with contextlib.redirect_stdout(io.StringIO()):
                result = install_workflows.main(["--comfyui-root", str(comfy_root)])
            self.assertEqual(result, 0)
            installed = list((comfy_root / "user/default/workflows/hoi4_portraits").glob("*.json"))
            self.assertEqual(len(installed), 3)
            self.assertTrue((comfy_root / "input/source_portrait.jpg").is_file())
            self.assertFalse((comfy_root / "custom_nodes").exists())

    def test_model_manifest_is_pinned_and_unique(self) -> None:
        data = json.loads((ROOT / "models.json").read_text())
        self.assertEqual(data["schema_version"], "2.0.0")
        models = data["models"]
        self.assertEqual(len(models), 6)
        filenames = [entry["filename"] for entry in models]
        self.assertEqual(len(filenames), len(set(filenames)))
        for entry in models:
            self.assertRegex(entry["revision"], r"^[0-9a-f]{40}$")
            self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(entry["size_bytes"], 0)
            self.assertTrue(entry["url"].startswith("https://"))

    def test_release_package_selection_excludes_model_weights(self) -> None:
        selected = build_release_artifacts._selected_files()
        forbidden = build_release_artifacts.MODEL_SUFFIXES
        self.assertFalse(any(path.suffix.casefold() in forbidden for path in selected))

    def test_windows_release_extractor_sources_are_current(self) -> None:
        source = ROOT / "packaging" / "windows" / "main.go"
        self.assertTrue((ROOT / "packaging" / "windows" / "go.mod").is_file())
        contents = source.read_text(encoding="utf-8")
        self.assertIn('"docs", "local-install.md"', contents)
        self.assertIn("it installs no custom nodes", contents)
        self.assertNotIn("setup-with-coding-agent.md", contents)


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

    def test_readme_contains_new_gallery_and_autoprompter_descriptions(self) -> None:
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
        self.assertEqual(readme.count("Autoprompter description:"), 6)
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

    def test_readme_gallery_uses_the_requested_older_boards(self) -> None:
        expected = {
            "source-processing-01.jpg": "9f6c3f8c4de1",
            "source-processing-02.jpg": "b4a09d4407f6",
            "source-processing-03.jpg": "077dfb9c9579",
            "source-processing-restoration-off-01.jpg": "8c1ea1da97e4",
            "source-processing-restoration-off-02.jpg": "c7e62859880b",
            "source-processing-restoration-off-03.jpg": "5e6b1e1ea456",
        }
        for filename, prefix in expected.items():
            digest = hashlib.sha256((ROOT / "docs/assets/test-runs" / filename).read_bytes()).hexdigest()
            self.assertTrue(digest.startswith(prefix), filename)

    def test_readme_contains_source_workflow_visual_walkthrough(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        screenshots = (
            "source-workflow-overview.png",
            "step-1-source-processing.png",
            "step-2-model-setup.png",
            "step-3-flux-restoration.png",
            "step-4-lora-styling.png",
            "step-5-background-replacement.png",
            "step-6-preview-and-save.png",
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
            ROOT / "docs" / "autoprompter-examples.md",
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
