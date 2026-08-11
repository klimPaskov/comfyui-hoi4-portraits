#!/usr/bin/env python3
"""Switch the installed HOI4 workflows to a model variant.

The repository keeps one canonical set of four workflows that load the full
FLUX.2 Klein 9B safetensors.  This helper rewrites the *installed* copies in
``user/default/workflows/hoi4_portraits`` so they load the variant that
matches the user's VRAM:

* ``full`` — ``flux-2-klein-9b.safetensors`` (BF16, more than 20 GB VRAM)
* ``fp8``  — ``flux-2-klein-9b-fp8.safetensors`` (16-20 GB VRAM)
* ``gguf`` — a GGUF quantization loaded by ``UnetLoaderGGUF`` (8-16 GB VRAM)

Each workflow keeps its diffusion-model loader visible. This helper rewrites
that node between ``UNETLoader`` and ``UnetLoaderGGUF`` in installed copies.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FULL_MODEL = "flux-2-klein-9b.safetensors"
FP8_MODEL = "flux-2-klein-9b-fp8.safetensors"
GGUF_QUANTS = ("Q4_K_M", "Q5_K_M", "Q6_K", "Q8_0")
LOADER_CLASSES = {"UNETLoader", "UnetLoaderGGUF"}
WORKFLOW_IDS = (
    "hoi4_portrait_source",
    "hoi4_portrait_text_to_image",
    "hoi4_portrait_batch",
    "hoi4_portrait_processing_only",
)


def _gguf_filename(quant: str) -> str:
    manifest = json.loads((ROOT / "models.json").read_text(encoding="utf-8"))
    for entry in manifest["models"]:
        if entry.get("variant") == "gguf" and entry.get("quant") == quant:
            return str(entry["filename"])
    raise ValueError(f"unsupported GGUF quantization {quant!r}")


def _patch_ui(path: Path, model_name: str, loader_class: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    for node in data.get("nodes", []):
        if node.get("type") not in LOADER_CLASSES:
            continue
        node["type"] = loader_class
        node.setdefault("properties", {})["Node name for S&R"] = loader_class
        if loader_class == "UnetLoaderGGUF":
            node["widgets_values"] = [model_name]
            node["inputs"] = [
                item for item in node.get("inputs", []) if item.get("name") != "weight_dtype"
            ]
            for item in node["inputs"]:
                if item.get("name") == "unet_name":
                    item["widget"] = {"name": "unet_name"}
        else:
            node["widgets_values"] = [model_name, "default"]
            inputs = [item for item in node.get("inputs", []) if item.get("name") != "weight_dtype"]
            for item in inputs:
                if item.get("name") == "unet_name":
                    item["widget"] = {"name": "unet_name"}
            inputs.append(
                {
                    "name": "weight_dtype",
                    "type": "COMBO",
                    "widget": {"name": "weight_dtype"},
                    "link": None,
                }
            )
            node["inputs"] = inputs
    data.setdefault("extra", {})["base_model"] = model_name
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _patch_api(path: Path, model_name: str, loader_class: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    for node in data.values():
        if not isinstance(node, dict) or node.get("class_type") not in LOADER_CLASSES:
            continue
        node["class_type"] = loader_class
        node["inputs"] = {k: v for k, v in node.get("inputs", {}).items() if k != "weight_dtype"}
        node["inputs"]["unet_name"] = model_name
        if loader_class == "UNETLoader":
            node["inputs"]["weight_dtype"] = "default"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _variant_model(variant: str, quant: str) -> tuple[str, str]:
    if variant == "full":
        return FULL_MODEL, "UNETLoader"
    if variant == "fp8":
        return FP8_MODEL, "UNETLoader"
    return _gguf_filename(quant), "UnetLoaderGGUF"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comfyui-root", required=True, type=Path)
    parser.add_argument(
        "--variant",
        action="append",
        choices=["full", "fp8", "gguf"],
        default=[],
        help="Model variant(s) to prepare. The first is applied to the four main workflows; the rest are emitted as ready-made copies. Defaults to full.",
    )
    parser.add_argument(
        "--gguf-quants",
        default="Q5_K_M",
        help="Comma-separated GGUF quantizations to prepare. The first is used for the gguf workflow.",
    )
    args = parser.parse_args(argv)

    comfy_root = args.comfyui_root.expanduser().resolve()
    workflow_dir = comfy_root / "user" / "default" / "workflows" / "hoi4_portraits"
    if not workflow_dir.is_dir():
        parser.error(f"installed workflow folder not found: {workflow_dir}. Run install_workflows.py first.")

    variants = args.variant or ["full"]
    quants = [item.strip() for item in args.gguf_quants.split(",") if item.strip()] or ["Q5_K_M"]
    primary = variants[0]
    primary_quant = quants[0] if primary == "gguf" else None
    model_name, loader_class = _variant_model(primary, primary_quant or "Q5_K_M")

    canonical_paths = []
    for workflow_id in WORKFLOW_IDS:
        ui_path = workflow_dir / f"{workflow_id}.json"
        if not ui_path.is_file():
            parser.error(f"installed workflow file not found: {ui_path}")
        canonical_paths.append(ui_path)
        api_path = workflow_dir / f"{workflow_id}.api.json"
        if api_path.is_file():
            canonical_paths.append(api_path)

    patched = []
    for path in canonical_paths:
        if path.name.endswith(".api.json"):
            _patch_api(path, model_name, loader_class)
        else:
            _patch_ui(path, model_name, loader_class)
        patched.append(path.name)

    copies = []
    for variant in variants[1:]:
        quant = quants[0] if variant == "gguf" else None
        copy_model, copy_loader = _variant_model(variant, quant or "Q5_K_M")
        for path in canonical_paths:
            suffix = ".api.json" if path.name.endswith(".api.json") else ".json"
            base = path.name[: -len(suffix)]
            target = path.with_name(f"{base}_{variant}{suffix}")
            target.write_bytes(path.read_bytes())
            if suffix == ".api.json":
                _patch_api(target, copy_model, copy_loader)
            else:
                _patch_ui(target, copy_model, copy_loader)
            copies.append(target.name)

    print(
        json.dumps(
            {
                "status": "PASS",
                "variant": primary,
                "model": model_name,
                "loader": loader_class,
                "patched": patched,
                "copies": copies,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
