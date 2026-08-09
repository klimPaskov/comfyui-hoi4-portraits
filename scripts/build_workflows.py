#!/usr/bin/env python3
"""Build the four compact, public HOI4 ComfyUI workflows deterministically."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / "workflows"
SCHEMA_VERSION = "3.1.0"

BASE_MODEL = "flux-2-klein-9b.safetensors"
TEXT_ENCODER = "Qwen3-8B-Q8_0.gguf"
VAE_MODEL = "flux2-vae.safetensors"
STYLE_LORA = "hoi4_portrait_flux2_klein_9b_lora_000002500.safetensors"
ADONIS_BASE = "adonis_base.safetensors"
ADONIS_REFINE = "adonis_refine.safetensors"
ESRGAN_MODEL = "RealESRGAN_x2plus.pth"
BACKGROUND_MODEL = "birefnet.safetensors"
FACE_MODEL = "mediapipe_face_fp32.safetensors"

STYLE_PROMPT = "make this portrait hoi4_portrait style"
TEXT_PROMPT = (
    "hoi4_portrait style, an Irish middle-aged man with neatly combed dark hair, "
    "wearing a plain civilian jacket."
)
RESTORATION_PROMPT = (
    "uhdmanscale, fully reconstruct this entire image from cellphone quality to professional high resolution color raw quality.\n\n"
    "Remove halftone dot pattern. Apply descreen filter. Eliminate periodic grid noise. Eliminate repeating noise patterns and artifacts, "
    "remove uniform diagonal line texture patterns. Reconstruct low resolution high ISO noise areas with high resolution low ISO noise textures.\n\n"
    "Apply full detail reconstruction to all areas: background, environment, surfaces, objects, clothing, and foreground elements — render everything sharp, textured, and high fidelity.\n\n"
    "Subject identity is locked: preserve exact facial geometry and body geometry, eye shape and color, nose and mouth shape, and expression.\n\n"
    "On skin areas, remove color blotch artifacts, normalize tone uniformity, preserve natural pore and texture detail.\n\n"
    "On hair and body hair areas, separate smeared color artifacts, restore strand separation and texture. Outside the subject's face, freely reconstruct all texture and sharpness with no restrictions.\n\n"
    "Deblur and focus correction pass. Infer and reconstruct underlying detail from soft source: sharpen edge definition, recover eye detail, lip definition, and skin texture from motion blur.\n\n"
    "Output as professional high resolution color camera RAW image."
)

SETUP_NOTE = (
    "📦 MODELS + FOLDERS\n\n"
    "The installer places every file automatically. Manual locations:\n\n"
    "ComfyUI/models/\n"
    "├── diffusion_models/\n"
    "│   └── flux-2-klein-9b.safetensors (distilled; never Base)\n"
    "├── text_encoders/\n"
    "│   └── Qwen3-8B-Q8_0.gguf\n"
    "├── vae/\n"
    "│   └── flux2-vae.safetensors\n"
    "├── loras/\n"
    "│   ├── hoi4_portrait_flux2_klein_9b_lora_000002500.safetensors\n"
    "│   ├── adonis_base.safetensors\n"
    "│   └── adonis_refine.safetensors\n"
    "├── upscale_models/RealESRGAN_x2plus.pth\n"
    "├── background_removal/birefnet.safetensors\n"
    "└── detection/mediapipe_face_fp32.safetensors\n\n"
    "Model links and exact pinned revisions are in models.json. The installer selects full, FP8, or GGUF for your VRAM."
)

SAMPLER_NOTE = (
    "🎛️ SAMPLER — TUNED DEFAULTS\n\n"
    "4 steps · CFG 1 · guidance 1 · Euler · simple · denoise 1\n\n"
    "Steps control denoising detail and time. CFG controls how sharply the prompt — here, the HOI4 style trigger — is followed. "
    "Seed changes the result. Guidance is FLUX.2 prompt strength. Sampler and scheduler are independent controls: Euler is the algorithm; simple is the schedule.\n\n"
    "The purple sampler is deliberately one advanced card. ComfyUI's live latent callback shows the portrait being constructed while it runs."
)

PROMPT_NOTE = (
    "✍️ PROMPTING + RESTORATION\n\n"
    f"Keep the source prompt exactly:\n{STYLE_PROMPT}\n\n"
    "Only append short facts when necessary: ethnicity or skin colour, age/hair, and civilian/military/clerical clothing. "
    "Do not re-describe the game style.\n\n"
    "RealESRGAN prepares the crop. Adonis Base → Refine can restore colour and facial detail first, so the style LoRA does not have to guess them. "
    "Bypass Adonis only for a clean modern photograph."
)

BATCH_NOTE = (
    "🖼️ BATCH — ONE PORTRAIT AT A TIME\n\n"
    "Drop PNG/JPG/JPEG/WebP files into ComfyUI/input/hoi4_portraits_batch/ and queue once. "
    "The list output makes ComfyUI execute this single-sampler graph once per source.\n\n"
    "Automatic outputs:\n"
    "output/1024x1365/\n"
    "output/156x210/\n"
    "output/156x210/dds/\n\n"
    "DDS is DXT5/BC3, 156×210, one top level, no mipmaps."
)

COLORS = {
    "note": ("#475569", "#334155"),
    "source": ("#446a4d", "#304c38"),
    "model": ("#385d7a", "#29465c"),
    "restore": ("#80613d", "#5d472e"),
    "sample": ("#705080", "#523b60"),
    "output": ("#47647a", "#344b5c"),
}


@dataclass(frozen=True)
class Ref:
    node_id: int


class Graph:
    def __init__(self, workflow_id: str, title: str) -> None:
        self.workflow_id = workflow_id
        self.title = title
        self.nodes: list[dict[str, Any]] = []
        self.api: dict[str, dict[str, Any]] = {}
        self.links: list[list[Any]] = []
        self.stages: set[str] = set()
        self._node_id = 0
        self._link_id = 0

    def stage(self, title: str) -> None:
        """Register a logical stage without creating a collapsible canvas group."""
        self.stages.add(title)

    def node(
        self,
        class_type: str,
        title: str,
        pos: tuple[int, int],
        size: tuple[int, int],
        stage: str,
        inputs: list[tuple[str, str, bool]],
        outputs: list[tuple[str, str]],
        widgets: list[Any],
        api_inputs: dict[str, Any],
        color: str = "output",
    ) -> Ref:
        if stage not in self.stages:
            raise ValueError(f"unknown visible stage: {stage}")
        self._node_id += 1
        node_id = self._node_id
        foreground, background = COLORS[color]
        ui_inputs = []
        for name, type_name, is_widget in inputs:
            item: dict[str, Any] = {"name": name, "type": type_name, "link": None}
            if is_widget:
                item["widget"] = {"name": name}
            ui_inputs.append(item)
        ui_outputs = [{"name": name, "type": type_name, "links": None} for name, type_name in outputs]
        self.nodes.append(
            {
                "id": node_id,
                "type": class_type,
                "title": title,
                "pos": list(pos),
                "size": list(size),
                "color": foreground,
                "bgcolor": background,
                "flags": {},
                "order": len(self.nodes),
                "mode": 0,
                "inputs": ui_inputs,
                "outputs": ui_outputs,
                "properties": {"Node name for S&R": class_type, "hoi4_stage": stage},
                "widgets_values": widgets,
            }
        )
        if class_type != "Note":
            self.api[str(node_id)] = {"inputs": dict(api_inputs), "class_type": class_type, "_meta": {"title": title}}
        return Ref(node_id)

    def connect(self, source: Ref, source_slot: int, target: Ref, target_input: str) -> None:
        source_node = self.nodes[source.node_id - 1]
        target_node = self.nodes[target.node_id - 1]
        target_slot = next(index for index, item in enumerate(target_node["inputs"]) if item["name"] == target_input)
        self._link_id += 1
        link_id = self._link_id
        link_type = source_node["outputs"][source_slot]["type"]
        self.links.append([link_id, source.node_id, source_slot, target.node_id, target_slot, link_type])
        target_node["inputs"][target_slot]["link"] = link_id
        source_links = source_node["outputs"][source_slot]["links"]
        if source_links is None:
            source_node["outputs"][source_slot]["links"] = []
        source_node["outputs"][source_slot]["links"].append(link_id)
        self.api[str(target.node_id)]["inputs"][target_input] = [str(source.node_id), source_slot]

    def serialize(self, *, style_lora: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
        extra = {
            "workflow_id": self.workflow_id,
            "title": self.title,
            "schema_version": SCHEMA_VERSION,
            "base_model": BASE_MODEL,
            "style_lora": style_lora,
            "master_size": [1024, 1365],
            "game_size": [156, 210],
            "dds": {"compression": "DXT5", "mipmaps": False},
            "frontendVersion": "1.24.2",
            "ds": {"scale": 0.72, "offset": [0, 0]},
        }
        ui = {
            "id": self.workflow_id,
            "revision": 0,
            "last_node_id": self._node_id,
            "last_link_id": self._link_id,
            "nodes": self.nodes,
            "links": self.links,
            # Keep every node visible on the main canvas. ComfyUI canvas groups can
            # be collapsed, so this project deliberately serializes none of them.
            "groups": [],
            "config": {},
            "extra": extra,
            "version": 0.4,
        }
        return ui, self.api


def _note(graph: Graph, title: str, text: str, pos: tuple[int, int], size: tuple[int, int], stage: str) -> Ref:
    return graph.node("Note", title, pos, size, stage, [], [], [text], {}, "note")


def _load_image(graph: Graph, title: str, filename: str, pos: tuple[int, int], size: tuple[int, int], stage: str) -> Ref:
    return graph.node(
        "LoadImage", title, pos, size, stage,
        [("image", "COMBO", True)], [("IMAGE", "IMAGE"), ("MASK", "MASK")],
        [filename, "image"], {"image": filename}, "source",
    )


def _preview(graph: Graph, title: str, pos: tuple[int, int], size: tuple[int, int], stage: str) -> Ref:
    return graph.node("PreviewImage", title, pos, size, stage, [("images", "IMAGE", False)], [("IMAGE", "IMAGE")], [], {}, "output")


def _model_stack(graph: Graph, pos: tuple[int, int], stage: str, *, style_strength: float, restoration: bool) -> Ref:
    values = [BASE_MODEL, TEXT_ENCODER, VAE_MODEL, STYLE_LORA, style_strength, restoration, ADONIS_BASE, ADONIS_REFINE, "default", "default"]
    names = [
        ("diffusion_model", "STRING"), ("text_encoder", "STRING"), ("vae_name", "STRING"),
        ("style_lora", "STRING"), ("style_strength", "FLOAT"), ("load_restoration", "BOOLEAN"),
        ("adonis_base", "STRING"), ("adonis_refine", "STRING"), ("weight_dtype", "COMBO"),
        ("text_encoder_device", "COMBO"),
    ]
    return graph.node(
        "Hoi4ModelStack", "Distilled FLUX.2 Klein stack — full / FP8 / GGUF", pos, (820, 720), stage,
        [(name, type_name, True) for name, type_name in names],
        [("style_model", "MODEL"), ("adonis_base_model", "MODEL"), ("adonis_refine_model", "MODEL"), ("clip", "CLIP"), ("vae", "VAE")],
        values, dict(zip((name for name, _ in names), values)), "model",
    )


def _source_prep(graph: Graph, pos: tuple[int, int], stage: str) -> Ref:
    widgets = [True, 0.90, True, False, 0.0, 0.0, 1.0, 1.0, FACE_MODEL, BACKGROUND_MODEL, ESRGAN_MODEL]
    widget_names = [
        ("face_processing", "BOOLEAN"), ("face_zoom", "FLOAT"), ("preserve_headwear", "BOOLEAN"),
        ("use_manual_crop", "BOOLEAN"), ("manual_x", "FLOAT"), ("manual_y", "FLOAT"),
        ("manual_width", "FLOAT"), ("manual_height", "FLOAT"), ("face_model", "STRING"),
        ("subject_model", "STRING"), ("upscale_model", "STRING"),
    ]
    return graph.node(
        "Hoi4SourcePrep", "Source prep — face/manual crop + headwear + RealESRGAN", pos, (680, 760), stage,
        [("image", "IMAGE", False)] + [(name, type_name, True) for name, type_name in widget_names],
        [("source", "IMAGE"), ("crop", "IMAGE"), ("esrgan", "IMAGE")], widgets,
        dict(zip((name for name, _ in widget_names), widgets)), "source",
    )


def _restorer(graph: Graph, pos: tuple[int, int], stage: str, *, enabled: bool = True) -> Ref:
    widget_names = [
        ("enabled", "BOOLEAN"), ("prompt", "STRING"), ("noise_seed", "INT"), ("megapixels", "FLOAT"),
        ("multiple_of", "INT"), ("resize_mode", "COMBO"), ("upscale_method", "COMBO"), ("eta", "FLOAT"),
        ("sampling_algorithm", "STRING"), ("scheduler", "STRING"), ("total_steps", "INT"),
        ("base_steps_to_run", "INT"), ("cfg", "FLOAT"), ("denoise", "FLOAT"),
        ("base_sampling_mode", "COMBO"), ("refine_sampling_mode", "COMBO"), ("noise_type", "STRING"),
        ("initial_noise_scale", "FLOAT"), ("alternate_denoise", "FLOAT"), ("channelwise_cfg", "BOOLEAN"),
        ("bongmath", "BOOLEAN"),
    ]
    values = [enabled, RESTORATION_PROMPT, 42, 1.7, 16, "crop", "lanczos", 0.8, "exponential/res_2s", "simple", 9, 5, 1.0, 1.0, "standard", "resample", "gaussian", 1.0, 1.0, False, True]
    return graph.node(
        "Hoi4AdonisRestoration", "Adonis Base → Refine — exact upstream topology + live controls", pos, (860, 1120), stage,
        [("base_model", "MODEL", False), ("refine_model", "MODEL", False), ("clip", "CLIP", False), ("vae", "VAE", False), ("image", "IMAGE", False)]
        + [(name, type_name, True) for name, type_name in widget_names],
        [("restored", "IMAGE"), ("preprocessed", "IMAGE")], values,
        dict(zip((name for name, _ in widget_names), values)), "restore",
    )


def _sampler(graph: Graph, title: str, pos: tuple[int, int], stage: str, *, mode: str, prompt: str, seed: int) -> Ref:
    widget_names = [
        ("mode", "COMBO"), ("prompt", "STRING"), ("negative_prompt", "STRING"), ("width", "INT"),
        ("height", "INT"), ("noise_seed", "INT"), ("steps", "INT"), ("cfg", "FLOAT"),
        ("guidance", "FLOAT"), ("sampling_algorithm", "COMBO"), ("scheduler", "COMBO"),
        ("denoise", "FLOAT"), ("add_noise", "COMBO"), ("start_at_step", "INT"),
        ("end_at_step", "INT"), ("force_full_denoise", "BOOLEAN"),
    ]
    values = [mode, prompt, "", 1024, 1365, seed, 4, 1.0, 1.0, "euler", "simple", 1.0, "enable", 0, 10000, True]
    return graph.node(
        "Hoi4PortraitSampler", title, pos, (720, 740), stage,
        [("model", "MODEL", False), ("clip", "CLIP", False), ("vae", "VAE", False)]
        + [(name, type_name, True) for name, type_name in widget_names]
        + [("reference_image", "IMAGE", False)],
        [("portrait", "IMAGE")], values, dict(zip((name for name, _ in widget_names), values)), "sample",
    )


def _final_output(graph: Graph, title: str, pos: tuple[int, int], stage: str) -> Ref:
    names = [
        ("use_background", "BOOLEAN"), ("background_model", "STRING"), ("master_width", "INT"),
        ("master_height", "INT"), ("game_width", "INT"), ("game_height", "INT"),
    ]
    values = [False, BACKGROUND_MODEL, 1024, 1365, 156, 210]
    return graph.node(
        "Hoi4FinalOutput", title, pos, (600, 500), stage,
        [("image", "IMAGE", False)] + [(name, type_name, True) for name, type_name in names] + [("background", "IMAGE", False)],
        [("master_1024x1365", "IMAGE"), ("game_156x210", "IMAGE")], values,
        dict(zip((name for name, _ in names), values)), "output",
    )


def _save_image(graph: Graph, title: str, prefix: str, pos: tuple[int, int], stage: str) -> Ref:
    return graph.node(
        "SaveImage", title, pos, (420, 150), stage,
        [("images", "IMAGE", False), ("filename_prefix", "STRING", True)], [("IMAGE", "IMAGE")],
        [prefix], {"filename_prefix": prefix}, "output",
    )


def _save_dds(graph: Graph, title: str, prefix: str, pos: tuple[int, int], stage: str) -> Ref:
    return graph.node(
        "Hoi4SaveDDS", title, pos, (420, 190), stage,
        [("images", "IMAGE", False), ("filename_prefix", "STRING", True), ("compression", "COMBO", True)], [("images", "IMAGE")],
        [prefix, "dxt5"], {"filename_prefix": prefix, "compression": "dxt5"}, "output",
    )


def _batch_input(graph: Graph, pos: tuple[int, int], stage: str) -> Ref:
    values = ["hoi4_portraits_batch", "*.png;*.jpg;*.jpeg;*.webp"]
    return graph.node(
        "Hoi4BatchInput", "Batch input folder — list output runs one file at a time", pos, (700, 260), stage,
        [("input_folder", "STRING", True), ("file_pattern", "STRING", True)],
        [("images", "IMAGE"), ("masks", "MASK"), ("filenames", "STRING")], values,
        {"input_folder": values[0], "file_pattern": values[1]}, "source",
    )


def _wire_models(graph: Graph, stack: Ref, restorer: Ref) -> None:
    graph.connect(stack, 1, restorer, "base_model")
    graph.connect(stack, 2, restorer, "refine_model")
    graph.connect(stack, 3, restorer, "clip")
    graph.connect(stack, 4, restorer, "vae")


def _wire_sampler_models(graph: Graph, stack: Ref, sampler: Ref) -> None:
    graph.connect(stack, 0, sampler, "model")
    graph.connect(stack, 3, sampler, "clip")
    graph.connect(stack, 4, sampler, "vae")


def _wire_outputs(graph: Graph, image: Ref, final: Ref, background: Ref | None) -> None:
    graph.connect(image, 0, final, "image")
    if background is not None:
        graph.connect(background, 0, final, "background")


def build_source() -> tuple[dict[str, Any], dict[str, Any]]:
    graph = Graph("hoi4_portrait_flux2_klein_9b_source", "HOI4 Portrait — source reference, three candidates")
    for stage in (
        "00 Welcome & setup",
        "01 Source + RealESRGAN",
        "02 Models + Adonis",
        "03 Three live HOI4 candidates",
        "04 Automatic outputs",
        "05 Compare: ESRGAN · Adonis · final 1 · final 2 · final 3",
    ):
        graph.stage(stage)

    _note(graph, "📦 Setup — models, variants, and folders", SETUP_NOTE, (80, 100), (720, 760), "00 Welcome & setup")
    _note(graph, "🎛️ Beginner + advanced sampler guide", SAMPLER_NOTE, (80, 940), (720, 700), "00 Welcome & setup")
    _note(graph, "✍️ Exact prompt and why restoration helps", PROMPT_NOTE, (80, 1720), (720, 780), "00 Welcome & setup")

    source = _load_image(graph, "Load source portrait — upload or choose here", "source_portrait.jpg", (920, 100), (700, 620), "01 Source + RealESRGAN")
    source_preview = _preview(graph, "Source preview", (960, 790), (600, 810), "01 Source + RealESRGAN")
    prep = _source_prep(graph, (920, 1650), "01 Source + RealESRGAN")
    graph.connect(source, 0, source_preview, "images")
    graph.connect(source, 0, prep, "image")

    stack = _model_stack(graph, (1760, 100), "02 Models + Adonis", style_strength=1.0, restoration=True)
    restore = _restorer(graph, (1740, 920), "02 Models + Adonis")
    _wire_models(graph, stack, restore)
    graph.connect(prep, 2, restore, "image")

    background = _load_image(graph, "Optional replacement background (toggle is inside each final card)", "hoi4_leader_portrait_background.png", (2740, 100), (620, 560), "03 Three live HOI4 candidates")
    finals: list[Ref] = []
    for index, (seed, y) in enumerate(((42, 100), (43, 930), (44, 1760)), start=1):
        sampler = _sampler(graph, f"Candidate {index} — one advanced live sampler card", (3420, y), "03 Three live HOI4 candidates", mode="source_reference", prompt=STYLE_PROMPT, seed=seed)
        final = _final_output(graph, f"Candidate {index} — background + centered master/game crops", (4190, y + 80), "03 Three live HOI4 candidates")
        _wire_sampler_models(graph, stack, sampler)
        graph.connect(restore, 0, sampler, "reference_image")
        _wire_outputs(graph, sampler, final, background)
        finals.append(final)

        oy = 100 + (index - 1) * 820
        master = _save_image(graph, f"Save candidate {index} master PNG", f"1024x1365/candidate_{index}", (5020, oy), "04 Automatic outputs")
        game = _save_image(graph, f"Save candidate {index} game PNG", f"156x210/candidate_{index}", (5480, oy), "04 Automatic outputs")
        dds = _save_dds(graph, f"Save candidate {index} game DDS — DXT5, no mipmaps", f"156x210/dds/candidate_{index}", (5480, oy + 230), "04 Automatic outputs")
        graph.connect(final, 0, master, "images")
        graph.connect(final, 1, game, "images")
        graph.connect(final, 1, dds, "images")

    comparison = [
        ("RealESRGAN prepared crop", prep, 2),
        ("Adonis Base → Refine restored", restore, 0),
        ("Final candidate 1 — 156×210", finals[0], 1),
        ("Final candidate 2 — 156×210", finals[1], 1),
        ("Final candidate 3 — 156×210", finals[2], 1),
    ]
    for index, (title, ref, slot) in enumerate(comparison):
        preview = _preview(graph, title, (930 + index * 660, 2870), (600, 810), "05 Compare: ESRGAN · Adonis · final 1 · final 2 · final 3")
        graph.connect(ref, slot, preview, "images")
    return graph.serialize(style_lora=STYLE_LORA)


def build_text() -> tuple[dict[str, Any], dict[str, Any]]:
    graph = Graph("hoi4_portrait_flux2_klein_9b_text_to_image", "HOI4 Portrait — text to image")
    for stage in ("00 Notes", "01 Model + one live sampler", "02 Final output"):
        graph.stage(stage)
    _note(graph, "📦 Setup", SETUP_NOTE, (80, 100), (700, 800), "00 Notes")
    _note(graph, "🎛️ Sampler guide", SAMPLER_NOTE, (80, 980), (700, 760), "00 Notes")
    stack = _model_stack(graph, (920, 100), "01 Model + one live sampler", style_strength=1.0, restoration=False)
    sampler = _sampler(graph, "Text-to-image — one advanced live sampler", (1800, 100), "01 Model + one live sampler", mode="text_to_image", prompt=TEXT_PROMPT, seed=42)
    _wire_sampler_models(graph, stack, sampler)
    background = _load_image(graph, "Optional replacement background", "hoi4_leader_portrait_background.png", (2720, 100), (620, 560), "02 Final output")
    final = _final_output(graph, "Centered 1024×1365 master + 156×210 game crop", (3420, 100), "02 Final output")
    _wire_outputs(graph, sampler, final, background)
    master = _save_image(graph, "Save master PNG", "1024x1365/text_to_image", (2720, 760), "02 Final output")
    game = _save_image(graph, "Save game PNG", "156x210/text_to_image", (3180, 760), "02 Final output")
    dds = _save_dds(graph, "Save game DDS — DXT5, no mipmaps", "156x210/dds/text_to_image", (3640, 760), "02 Final output")
    preview = _preview(graph, "Final 156×210 portrait", (2880, 1050), (600, 810), "02 Final output")
    graph.connect(final, 0, master, "images")
    graph.connect(final, 1, game, "images")
    graph.connect(final, 1, dds, "images")
    graph.connect(final, 1, preview, "images")
    return graph.serialize(style_lora=STYLE_LORA)


def build_processing() -> tuple[dict[str, Any], dict[str, Any]]:
    graph = Graph("hoi4_portrait_processing_only", "HOI4 Portrait — processing and restoration only")
    for stage in ("00 Notes", "01 Source + processing", "02 Exact Adonis restoration", "03 Outputs + comparison"):
        graph.stage(stage)
    _note(graph, "📦 Setup", SETUP_NOTE, (80, 100), (700, 900), "00 Notes")
    _note(graph, "✨ Processing-only guide", PROMPT_NOTE, (80, 1080), (700, 900), "00 Notes")
    source = _load_image(graph, "Load source portrait", "source_portrait.jpg", (920, 100), (680, 620), "01 Source + processing")
    prep = _source_prep(graph, (1650, 100), "01 Source + processing")
    graph.connect(source, 0, prep, "image")
    stack = _model_stack(graph, (2480, 100), "02 Exact Adonis restoration", style_strength=0.0, restoration=True)
    restore = _restorer(graph, (3340, 100), "02 Exact Adonis restoration")
    _wire_models(graph, stack, restore)
    graph.connect(prep, 2, restore, "image")
    final = _final_output(graph, "Centered master + game crop (no style LoRA)", (4320, 100), "03 Outputs + comparison")
    graph.connect(restore, 0, final, "image")
    master = _save_image(graph, "Save restored master PNG", "1024x1365/processing_only", (4960, 100), "03 Outputs + comparison")
    game = _save_image(graph, "Save restored game PNG", "156x210/processing_only", (5420, 100), "03 Outputs + comparison")
    dds = _save_dds(graph, "Save restored game DDS", "156x210/dds/processing_only", (5880, 100), "03 Outputs + comparison")
    graph.connect(final, 0, master, "images")
    graph.connect(final, 1, game, "images")
    graph.connect(final, 1, dds, "images")
    for index, (title, ref, slot) in enumerate((("RealESRGAN", prep, 2), ("Adonis Base → Refine", restore, 0), ("Final 156×210", final, 1))):
        preview = _preview(graph, title, (4320 + index * 660, 760), (600, 810), "03 Outputs + comparison")
        graph.connect(ref, slot, preview, "images")
    return graph.serialize(style_lora=None)


def build_batch() -> tuple[dict[str, Any], dict[str, Any]]:
    graph = Graph("hoi4_portrait_batch", "HOI4 Portrait — batch input and output")
    for stage in ("00 Batch guide", "01 One-at-a-time source prep", "02 Models + exact Adonis", "03 One live sampler + outputs"):
        graph.stage(stage)
    _note(graph, "🖼️ Batch input and output", BATCH_NOTE, (80, 100), (700, 920), "00 Batch guide")
    _note(graph, "🎛️ Sampler guide", SAMPLER_NOTE, (80, 1100), (700, 900), "00 Batch guide")
    batch = _batch_input(graph, (920, 100), "01 One-at-a-time source prep")
    prep = _source_prep(graph, (1660, 100), "01 One-at-a-time source prep")
    graph.connect(batch, 0, prep, "image")
    stack = _model_stack(graph, (2460, 100), "02 Models + exact Adonis", style_strength=1.0, restoration=True)
    restore = _restorer(graph, (3320, 100), "02 Models + exact Adonis")
    _wire_models(graph, stack, restore)
    graph.connect(prep, 2, restore, "image")
    sampler = _sampler(graph, "Batch portrait — exactly one advanced live sampler", (4340, 100), "03 One live sampler + outputs", mode="source_reference", prompt=STYLE_PROMPT, seed=42)
    _wire_sampler_models(graph, stack, sampler)
    graph.connect(restore, 0, sampler, "reference_image")
    final = _final_output(graph, "Centered master + game crop", (5100, 100), "03 One live sampler + outputs")
    graph.connect(sampler, 0, final, "image")
    master = _save_image(graph, "Save every master PNG", "1024x1365/batch", (5740, 100), "03 One live sampler + outputs")
    game = _save_image(graph, "Save every game PNG", "156x210/batch", (5740, 310), "03 One live sampler + outputs")
    dds = _save_dds(graph, "Save every game DDS", "156x210/dds/batch", (5740, 520), "03 One live sampler + outputs")
    graph.connect(final, 0, master, "images")
    graph.connect(final, 1, game, "images")
    graph.connect(final, 1, dds, "images")
    for index, (title, ref, slot) in enumerate((("RealESRGAN", prep, 2), ("Adonis restored", restore, 0), ("Final 156×210", final, 1))):
        preview = _preview(graph, title, (4340 + index * 660, 920), (600, 810), "03 One live sampler + outputs")
        graph.connect(ref, slot, preview, "images")
    return graph.serialize(style_lora=STYLE_LORA)


BUILDERS = {
    "hoi4_portrait_flux2_klein_9b_source": build_source,
    "hoi4_portrait_flux2_klein_9b_text_to_image": build_text,
    "hoi4_portrait_processing_only": build_processing,
    "hoi4_portrait_batch": build_batch,
}


def build_all(root: Path = ROOT) -> list[Path]:
    workflow_dir = root / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    manifest_entries = []
    for workflow_id, builder in BUILDERS.items():
        ui, api = builder()
        ui_path = workflow_dir / f"{workflow_id}.json"
        api_path = workflow_dir / f"{workflow_id}.api.json"
        ui_path.write_text(json.dumps(ui, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        api_path.write_text(json.dumps(api, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.extend((ui_path, api_path))
        manifest_entries.append(
            {
                "id": workflow_id,
                "title": ui["extra"]["title"],
                "workflow": ui_path.name,
                "api_workflow": api_path.name,
                "nodes": len(ui["nodes"]),
            }
        )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "default_workflows": len(BUILDERS),
        "workflows": manifest_entries,
    }
    manifest_path = workflow_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    written.append(manifest_path)
    return written


def main() -> int:
    for path in build_all():
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
