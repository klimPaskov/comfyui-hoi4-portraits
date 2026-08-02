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
        self.assertEqual(manifest["schema_version"], "2.2.0")
        for item in manifest["workflows"]:
            for path_key, digest_key in (("workflow_json", "sha256"), ("api_json", "api_sha256")):
                data = (ROOT / item[path_key]).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), item[digest_key])

    def test_editor_model_urls_are_revision_pinned(self) -> None:
        for workflow in (ROOT / "workflows").glob("*.json"):
            self.assertNotIn("/resolve/main/", workflow.read_text(encoding="utf-8"), workflow.name)

    def test_autoprompter_output_contract_is_person_only(self) -> None:
        instruction = (ROOT / "prompts" / "autoprompter_instruction.txt").read_text(encoding="utf-8").casefold()
        self.assertIn("the prompt describes only the person", instruction)
        for forbidden in (
            "transform the supplied",
            "grand-strategy portrait",
            "hand-painted 1930s",
            "background description",
        ):
            self.assertNotIn(forbidden, instruction)
        self.assertIn("for monochrome or sepia sources, do not infer skin tone", instruction)
        self.assertIn("do not contradict yourself", instruction)

    def test_selected_lora_and_sampling_defaults(self) -> None:
        self.assertEqual(build_workflows.STYLE_LORA_STRENGTH, 0.7)
        self.assertEqual(build_workflows.DEFAULT_STEPS, 6)
        for workflow in (ROOT / "workflows").glob("*.api.json"):
            api = json.loads(workflow.read_text(encoding="utf-8"))
            lora = next(node for node in api.values() if node["class_type"] == "LoraLoaderModelOnly")
            self.assertEqual(lora["inputs"]["strength_model"], 0.7, workflow.name)
            schedules = [node for node in api.values() if node["class_type"] == "Flux2Scheduler"]
            self.assertTrue(schedules, workflow.name)
            self.assertTrue(all(node["inputs"]["steps"] == 6 for node in schedules), workflow.name)

    def test_source_graphs_crop_before_esrgan_and_preserve_source_latent(self) -> None:
        for name in ("full_power", "esrgan_only"):
            path = ROOT / "workflows" / f"hoi4_portrait_flux2_klein_9b_{name}.api.json"
            api = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(api["11"]["class_type"], "ImageCropV2")
            self.assertEqual(api["11"]["inputs"]["image"], ["5", 0])
            self.assertEqual(api["11"]["inputs"]["crop_region"], ["9", 0])
            self.assertEqual(api["7"]["inputs"]["image"], ["11", 0])
            self.assertNotIn("EmptyFlux2LatentImage", {node["class_type"] for node in api.values()})
            self.assertEqual(api["50"]["inputs"]["latent_image"], ["42", 0])

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


class DocumentationTests(unittest.TestCase):
    LINK = re.compile(r"\[[^]]+\]\(([^)]+)\)")
    CODE_BLOCK = re.compile(r"```(?:text)?\n(.*?)```", re.DOTALL)

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
        table = "\n".join(line for line in section.splitlines() if line.startswith("|"))
        self.assertEqual(table.count("workflows/hoi4_portrait_flux2_klein_9b_"), 3)
        self.assertNotIn("krea", table.casefold())

    def test_readme_contains_new_gallery_and_autoprompter_descriptions(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertEqual(readme.count("docs/assets/test-runs/full-restoration-"), 3)
        self.assertEqual(readme.count("docs/assets/test-runs/esrgan-only-"), 3)
        self.assertIn("docs/assets/test-runs/random-portraits.jpg", readme)
        self.assertIn("docs/assets/test-runs/step-comparison.jpg", readme)
        self.assertEqual(readme.count("Autoprompter description:"), 6)
        for obsolete in (
            "full-restoration-04.jpg",
            "full-restoration-05.jpg",
            "esrgan-only-04.jpg",
            "esrgan-only-05.jpg",
            "settings-matrix.jpg",
        ):
            self.assertFalse((ROOT / "docs" / "assets" / "test-runs" / obsolete).exists(), obsolete)

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
                if "hoi4_portrait," in block:
                    examples.append((document, block.strip()))
        self.assertGreaterEqual(len(examples), 3)
        for document, example in examples:
            self.assertIsNone(forbidden.search(example), f"{document.name}: {example}")


if __name__ == "__main__":
    unittest.main()
