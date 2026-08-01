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
        for item in manifest["workflows"]:
            for path_key, digest_key in (("workflow_json", "sha256"), ("api_json", "api_sha256")):
                data = (ROOT / item[path_key]).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), item[digest_key])

    def test_editor_model_urls_are_revision_pinned(self) -> None:
        for workflow in (ROOT / "workflows").glob("*.json"):
            self.assertNotIn("/resolve/main/", workflow.read_text(encoding="utf-8"), workflow.name)


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


if __name__ == "__main__":
    unittest.main()
