#!/usr/bin/env python3
"""Build four fully visible HOI4 ComfyUI workflows deterministically."""

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
    "Only the purple style sampler combines controls. Model loading, source processing, Adonis Base, Adonis Refine, decoding, and output sizing stay visible as separate nodes. "
    "ComfyUI's live latent callback shows both style and restoration construction while they run."
)

PROMPT_NOTE = (
    "✍️ PROMPTING + RESTORATION\n\n"
    f"Keep the source prompt exactly:\n{STYLE_PROMPT}\n\n"
    "Only append short facts when necessary: ethnicity or skin colour, age/hair, and civilian/military/clerical clothing. "
    "Do not re-describe the game style.\n\n"
    "RealESRGAN prepares the crop. The expanded Adonis Base → Refine graph restores colour and facial detail first, so the style LoRA does not have to guess them. "
    "Disable the visible restoration switch only for a clean modern photograph."
)

BATCH_NOTE = (
    "🖼️ BATCH — ONE PORTRAIT AT A TIME\n\n"
    "Drop PNG/JPG/JPEG/WebP files into ComfyUI/input/hoi4_portraits_batch/ and queue once. "
    "The list output makes ComfyUI execute this one-sampler graph once per source.\n\n"
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
    "switch": ("#b84949", "#702f2f"),
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
        self.groups: list[dict[str, Any]] = []
        self._group_titles: set[str] = set()
        self._node_id = 0
        self._link_id = 0

    def group(self, title: str, color: str) -> None:
        if title in self._group_titles:
            raise ValueError(f"duplicate group title: {title}")
        self._group_titles.add(title)
        self.groups.append(
            {
                "id": len(self.groups) + 1,
                "title": title,
                "bounding": [0, 0, 0, 0],
                "color": color,
                "font_size": 28,
                "flags": {"collapsed": False},
            }
        )

    def node(
        self,
        class_type: str,
        title: str,
        pos: tuple[int, int],
        size: tuple[int, int],
        group: str,
        inputs: list[tuple[str, str, bool]],
        outputs: list[tuple[str, str]],
        widgets: list[Any],
        api_inputs: dict[str, Any],
        color: str = "output",
    ) -> Ref:
        if group not in self._group_titles:
            raise ValueError(f"unknown visible group: {group}")
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
                "properties": {"Node name for S&R": class_type, "hoi4_group": group},
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
        if source_node["outputs"][source_slot]["links"] is None:
            source_node["outputs"][source_slot]["links"] = []
        source_node["outputs"][source_slot]["links"].append(link_id)
        self.api[str(target.node_id)]["inputs"][target_input] = [str(source.node_id), source_slot]

    def _fit_groups(self) -> None:
        """Wrap every visible group tightly around its nodes with equal gutters."""

        for group in self.groups:
            members = [
                node for node in self.nodes
                if node.get("properties", {}).get("hoi4_group") == group["title"]
            ]
            if not members:
                raise ValueError(f"visible group has no nodes: {group['title']}")
            left = min(node["pos"][0] for node in members)
            top = min(node["pos"][1] for node in members)
            right = max(node["pos"][0] + node["size"][0] for node in members)
            bottom = max(node["pos"][1] + node["size"][1] for node in members)
            # The extra 20px above the nodes leaves room for the group title.
            group["bounding"] = [left - 40, top - 60, right - left + 80, bottom - top + 100]

    def serialize(self, *, style_lora: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
        self._fit_groups()
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
        return (
            {
                "id": self.workflow_id,
                "revision": 0,
                "last_node_id": self._node_id,
                "last_link_id": self._link_id,
                "nodes": self.nodes,
                "links": self.links,
                "groups": self.groups,
                "config": {},
                "extra": extra,
                "version": 0.4,
            },
            self.api,
        )


def _note(g: Graph, title: str, text: str, pos: tuple[int, int], size: tuple[int, int], group: str) -> Ref:
    return g.node("Note", title, pos, size, group, [], [], [text], {}, "note")


def _load_image(g: Graph, title: str, filename: str, pos: tuple[int, int], size: tuple[int, int], group: str) -> Ref:
    return g.node(
        "LoadImage", title, pos, size, group,
        [("image", "COMBO", True)], [("IMAGE", "IMAGE"), ("MASK", "MASK")],
        [filename, "image"], {"image": filename}, "source",
    )


def _preview(g: Graph, title: str, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "PreviewImage", title, pos, (600, 810), group,
        [("images", "IMAGE", False)], [("IMAGE", "IMAGE")], [], {}, "output",
    )


def _unet(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "UNETLoader", "Load distilled FLUX.2 Klein 9B — full / FP8 / GGUF installer target", pos, (440, 130), group,
        [("unet_name", "COMBO", True), ("weight_dtype", "COMBO", True)], [("MODEL", "MODEL")],
        [BASE_MODEL, "default"], {"unet_name": BASE_MODEL, "weight_dtype": "default"}, "model",
    )


def _clip(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    values = [TEXT_ENCODER, "flux2", "default"]
    return g.node(
        "ClipLoaderGGUF", "Load Qwen3 8B Q8 text encoder", pos, (440, 150), group,
        [("clip_name", "COMBO", True), ("type", "COMBO", True), ("device", "COMBO", True)], [("CLIP", "CLIP")],
        values, dict(zip(("clip_name", "type", "device"), values)), "model",
    )


def _vae(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "VAELoader", "Load FLUX.2 VAE", pos, (440, 100), group,
        [("vae_name", "COMBO", True)], [("VAE", "VAE")], [VAE_MODEL], {"vae_name": VAE_MODEL}, "model",
    )


def _lora(g: Graph, title: str, filename: str, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "LoraLoaderModelOnly", title, pos, (500, 140), group,
        [("model", "MODEL", False), ("lora_name", "COMBO", True), ("strength_model", "FLOAT", True)], [("MODEL", "MODEL")],
        [filename, 1.0], {"lora_name": filename, "strength_model": 1.0}, "model",
    )


def _face_loader(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "LoadMediaPipeFaceLandmarker", "Load face detector", pos, (400, 100), group,
        [("model_name", "COMBO", True)], [("FACE_DETECTION_MODEL", "FACE_DETECTION_MODEL")],
        [FACE_MODEL], {"model_name": FACE_MODEL}, "source",
    )


def _face_detect(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    values = ["both", 1, 0.35, "empty"]
    return g.node(
        "MediaPipeFaceLandmarker", "Detect portrait face — bounding box stays visible", pos, (500, 300), group,
        [("face_detection_model", "FACE_DETECTION_MODEL", False), ("image", "IMAGE", False),
         ("detector_variant", "COMBO", True), ("num_faces", "INT", True),
         ("min_confidence", "FLOAT", True), ("missing_frame_fallback", "COMBO", True)],
        [("face_landmarks", "FACE_LANDMARKS"), ("bboxes", "BOUNDING_BOX")],
        values, dict(zip(("detector_variant", "num_faces", "min_confidence", "missing_frame_fallback"), values)), "source",
    )


def _background_model(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "LoadBackgroundRemovalModel", "Load BiRefNet mask model", pos, (440, 100), group,
        [("bg_removal_name", "COMBO", True)], [("bg_model", "BACKGROUND_REMOVAL")],
        [BACKGROUND_MODEL], {"bg_removal_name": BACKGROUND_MODEL}, "model",
    )


def _remove_background(g: Graph, title: str, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "RemoveBackground", title, pos, (360, 100), group,
        [("bg_removal_model", "BACKGROUND_REMOVAL", False), ("image", "IMAGE", False)], [("mask", "MASK")],
        [], {}, "source",
    )


def _adaptive_crop(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    names = (
        "face_processing", "use_manual_crop", "manual_x", "manual_y", "manual_width",
        "manual_height", "zoom", "preserve_headwear", "output_width", "output_height",
    )
    values = [True, False, 0.0, 0.0, 1.0, 1.0, 0.9, True, 512, 683]
    return g.node(
        "AdaptivePortraitCrop", "Portrait crop — automatic / centered / manual, 512×683 before 2× ESRGAN", pos, (480, 420), group,
        [("image", "IMAGE", False), ("face_bboxes", "BOUNDING_BOX", False), ("subject_mask", "MASK", False),
         ("face_processing", "BOOLEAN", True), ("use_manual_crop", "BOOLEAN", True),
         ("manual_x", "FLOAT", True), ("manual_y", "FLOAT", True),
         ("manual_width", "FLOAT", True), ("manual_height", "FLOAT", True),
         ("zoom", "FLOAT", True), ("preserve_headwear", "BOOLEAN", True),
         ("output_width", "INT", True), ("output_height", "INT", True)],
        [("portrait", "IMAGE")], values, dict(zip(names, values)), "source",
    )


def _upscale_loader(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "UpscaleModelLoader", "Load RealESRGAN ×2", pos, (400, 100), group,
        [("model_name", "COMBO", True)], [("UPSCALE_MODEL", "UPSCALE_MODEL")],
        [ESRGAN_MODEL], {"model_name": ESRGAN_MODEL}, "source",
    )


def _upscale(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "ImageUpscaleWithModel", "Run RealESRGAN ×2", pos, (360, 100), group,
        [("upscale_model", "UPSCALE_MODEL", False), ("image", "IMAGE", False)], [("IMAGE", "IMAGE")],
        [], {}, "source",
    )


def _image_scale(g: Graph, title: str, width: int, height: int, pos: tuple[int, int], group: str) -> Ref:
    values = ["lanczos", width, height, "center"]
    return g.node(
        "ImageScale", title, pos, (400, 180), group,
        [("image", "IMAGE", False), ("upscale_method", "COMBO", True), ("width", "INT", True),
         ("height", "INT", True), ("crop", "COMBO", True)], [("IMAGE", "IMAGE")],
        values, dict(zip(("upscale_method", "width", "height", "crop"), values)), "output",
    )


def _source_pipeline(g: Graph, source: Ref, group: str, *, x: int = 1600) -> Ref:
    face_loader = _face_loader(g, (x, 100), group)
    detector = _face_detect(g, (x, 260), group)
    mask_loader = _background_model(g, (x, 640), group)
    mask = _remove_background(g, "Generate subject silhouette for crop", (x, 800), group)
    crop = _adaptive_crop(g, (x + 540, 100), group)
    upscale_loader = _upscale_loader(g, (x + 540, 600), group)
    upscale = _upscale(g, (x + 540, 760), group)
    normalized = _image_scale(g, "Normalize RealESRGAN result to 1024×1365", 1024, 1365, (x + 540, 920), group)
    g.connect(face_loader, 0, detector, "face_detection_model")
    g.connect(source, 0, detector, "image")
    g.connect(mask_loader, 0, mask, "bg_removal_model")
    g.connect(source, 0, mask, "image")
    g.connect(source, 0, crop, "image")
    g.connect(detector, 1, crop, "face_bboxes")
    g.connect(mask, 0, crop, "subject_mask")
    g.connect(upscale_loader, 0, upscale, "upscale_model")
    g.connect(crop, 0, upscale, "image")
    g.connect(upscale, 0, normalized, "image")
    return normalized


def _scale_total(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    values = [1.7, 16, "crop", "lanczos"]
    return g.node(
        "ImageScaleToTotalPixelsX", "Adonis pre-process — exact 1.7 MP, multiple of 16, crop, Lanczos", pos, (400, 240), group,
        [("image", "IMAGE", False), ("megapixels", "FLOAT", True), ("multiple_of", "INT", True),
         ("resize_mode", "COMBO", True), ("upscale_method", "COMBO", True)],
        [("image", "IMAGE"), ("width", "INT"), ("height", "INT")],
        values, dict(zip(("megapixels", "multiple_of", "resize_mode", "upscale_method"), values)), "restore",
    )


def _clip_encode(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "CLIPTextEncode", "Adonis positive prompt — uhdmanscale", pos, (440, 260), group,
        [("clip", "CLIP", False), ("text", "STRING", True)], [("CONDITIONING", "CONDITIONING")],
        [RESTORATION_PROMPT], {"text": RESTORATION_PROMPT}, "restore",
    )


def _zero_conditioning(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "ConditioningZeroOut", "Zero negative conditioning", pos, (320, 80), group,
        [("conditioning", "CONDITIONING", False)], [("CONDITIONING", "CONDITIONING")], [], {}, "restore",
    )


def _vae_encode(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "VAEEncode", "Encode restored reference latent", pos, (300, 100), group,
        [("pixels", "IMAGE", False), ("vae", "VAE", False)], [("LATENT", "LATENT")], [], {}, "restore",
    )


def _reference(g: Graph, title: str, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "ReferenceLatent", title, pos, (320, 100), group,
        [("conditioning", "CONDITIONING", False), ("latent", "LATENT", False)], [("CONDITIONING", "CONDITIONING")],
        [], {}, "restore",
    )


def _empty_latent(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    values = [1024, 1024, 1]
    return g.node(
        "EmptyFlux2LatentImage", "Empty FLUX.2 latent — dimensions come from 1.7 MP pre-process", pos, (360, 180), group,
        [("width", "INT", True), ("height", "INT", True), ("batch_size", "INT", True)], [("LATENT", "LATENT")],
        values, dict(zip(("width", "height", "batch_size"), values)), "restore",
    )


def _shark_options(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    values = ["laplacian", 1.0, 1.0, False]
    return g.node(
        "SharkOptions_Beta", "Adonis RES4LYF options — exact upstream", pos, (400, 180), group,
        [("noise_type_init", "COMBO", True), ("s_noise_init", "FLOAT", True),
         ("denoise_alt", "FLOAT", True), ("channelwise_cfg", "BOOLEAN", True)], [("options", "OPTIONS")],
        values, dict(zip(("noise_type_init", "s_noise_init", "denoise_alt", "channelwise_cfg"), values)), "restore",
    )


def _primitive_int(g: Graph, title: str, value: int, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "PrimitiveInt", title, pos, (300, 100), group,
        [("value", "INT", True)], [("INT", "INT")], [value], {"value": value}, "restore",
    )


def _adonis_sampler(g: Graph, title: str, pos: tuple[int, int], group: str, *, refine: bool) -> Ref:
    values = [0.8, "exponential/res_2s", "simple", 9, -1 if refine else 5, 1.0, 1.0, 42, "fixed", "resample" if refine else "standard", True]
    names = ("eta", "sampler_name", "scheduler", "steps", "steps_to_run", "cfg", "denoise", "seed", "control_after_generate", "sampler_mode", "bongmath")
    return g.node(
        "ClownsharKSampler_Beta", title, pos, (500, 1100), group,
        [("model", "MODEL", False), ("positive", "CONDITIONING", False), ("negative", "CONDITIONING", False),
         ("latent_image", "LATENT", False), ("options", "OPTIONS", False),
         ("eta", "FLOAT", True), ("sampler_name", "COMBO", True), ("scheduler", "COMBO", True),
         ("steps", "INT", True), ("steps_to_run", "INT", True), ("cfg", "FLOAT", True),
         ("denoise", "FLOAT", True), ("seed", "INT", True), ("control_after_generate", "COMBO", True),
         ("sampler_mode", "COMBO", True), ("bongmath", "BOOLEAN", True)],
        [("output", "LATENT"), ("denoised", "LATENT"), ("options", "OPTIONS")],
        values, dict(zip(names, values)), "restore",
    )


def _vae_decode(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "VAEDecode", "Decode Adonis Refine output", pos, (300, 100), group,
        [("samples", "LATENT", False), ("vae", "VAE", False)], [("IMAGE", "IMAGE")], [], {}, "restore",
    )


def _switch(g: Graph, title: str, enabled: bool, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "ComfySwitchNode", title, pos, (360, 160), group,
        [("switch", "BOOLEAN", True), ("on_false", "IMAGE", False), ("on_true", "IMAGE", False)], [("IMAGE", "IMAGE")],
        [enabled], {"switch": enabled}, "switch",
    )


def _adonis_pipeline(g: Graph, image: Ref, model: dict[str, Ref], group: str, *, x: int = 4000) -> tuple[Ref, Ref]:
    scale = _scale_total(g, (x, 100), group)
    prompt = _clip_encode(g, (x, 420), group)
    negative = _zero_conditioning(g, (x, 760), group)
    encoded = _vae_encode(g, (x + 480, 100), group)
    positive_ref = _reference(g, "Positive reference latent", (x + 480, 280), group)
    negative_ref = _reference(g, "Negative reference latent", (x + 480, 460), group)
    empty = _empty_latent(g, (x + 480, 640), group)
    options = _shark_options(g, (x + 880, 100), group)
    seed = _primitive_int(g, "Shared Adonis seed", 42, (x + 880, 360), group)
    steps = _primitive_int(g, "Total Adonis steps", 9, (x + 880, 540), group)
    base = _adonis_sampler(g, "Adonis Base — live RES4LYF sampler (first 5 of 9 steps)", (x + 1360, 100), group, refine=False)
    refine = _adonis_sampler(g, "Adonis Refine — live RES4LYF sampler (remaining steps)", (x + 1940, 100), group, refine=True)
    decoded = _vae_decode(g, (x + 1940, 1280), group)
    enabled = _switch(g, "Use Adonis restoration", True, (x + 2320, 1280), group)

    g.connect(image, 0, scale, "image")
    g.connect(model["clip"], 0, prompt, "clip")
    g.connect(prompt, 0, negative, "conditioning")
    g.connect(scale, 0, encoded, "pixels")
    g.connect(model["vae"], 0, encoded, "vae")
    g.connect(prompt, 0, positive_ref, "conditioning")
    g.connect(encoded, 0, positive_ref, "latent")
    g.connect(negative, 0, negative_ref, "conditioning")
    g.connect(encoded, 0, negative_ref, "latent")
    g.connect(scale, 1, empty, "width")
    g.connect(scale, 2, empty, "height")

    g.connect(model["adonis_base"], 0, base, "model")
    g.connect(positive_ref, 0, base, "positive")
    g.connect(negative_ref, 0, base, "negative")
    g.connect(empty, 0, base, "latent_image")
    g.connect(options, 0, base, "options")
    g.connect(steps, 0, base, "steps")
    g.connect(seed, 0, base, "seed")

    g.connect(model["adonis_refine"], 0, refine, "model")
    g.connect(base, 0, refine, "latent_image")
    g.connect(steps, 0, refine, "steps")
    g.connect(seed, 0, refine, "seed")
    g.connect(refine, 0, decoded, "samples")
    g.connect(model["vae"], 0, decoded, "vae")
    g.connect(image, 0, enabled, "on_false")
    g.connect(decoded, 0, enabled, "on_true")
    return enabled, scale


def _model_pipeline(g: Graph, group: str, *, x: int, style: bool, adonis: bool, background: bool) -> dict[str, Ref]:
    unet = _unet(g, (x, 100), group)
    clip = _clip(g, (x, 320), group)
    vae = _vae(g, (x, 540), group)
    result: dict[str, Ref] = {"unet": unet, "clip": clip, "vae": vae}
    if style:
        style_lora = _lora(g, "Load HOI4 style LoRA — step 2500 only", STYLE_LORA, (x + 500, 100), group)
        g.connect(unet, 0, style_lora, "model")
        result["style"] = style_lora
    if adonis:
        base = _lora(g, "Load Adonis Base LoRA", ADONIS_BASE, (x + 500, 320), group)
        refine = _lora(g, "Load Adonis Refine LoRA", ADONIS_REFINE, (x + 500, 540), group)
        g.connect(unet, 0, base, "model")
        g.connect(unet, 0, refine, "model")
        result.update({"adonis_base": base, "adonis_refine": refine})
    if background:
        result["background_model"] = _background_model(g, (x, 720), group)
    return result


def _style_sampler(g: Graph, title: str, pos: tuple[int, int], group: str, *, mode: str, prompt: str, seed: int) -> Ref:
    names = [
        ("mode", "COMBO"), ("prompt", "STRING"), ("negative_prompt", "STRING"), ("width", "INT"),
        ("height", "INT"), ("noise_seed", "INT"), ("steps", "INT"), ("cfg", "FLOAT"),
        ("guidance", "FLOAT"), ("sampling_algorithm", "COMBO"), ("scheduler", "COMBO"),
        ("denoise", "FLOAT"), ("add_noise", "COMBO"), ("start_at_step", "INT"),
        ("end_at_step", "INT"), ("force_full_denoise", "BOOLEAN"),
    ]
    values = [mode, prompt, "", 1024, 1365, seed, 4, 1.0, 1.0, "euler", "simple", 1.0, "enable", 0, 10000, True]
    return g.node(
        "Hoi4PortraitSampler", title, pos, (720, 780), group,
        [("model", "MODEL", False), ("clip", "CLIP", False), ("vae", "VAE", False)]
        + [(name, type_name, True) for name, type_name in names]
        + [("reference_image", "IMAGE", False)],
        [("portrait", "IMAGE")], values, dict(zip((name for name, _ in names), values)), "sample",
    )


def _background_replace(g: Graph, title: str, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "Hoi4BackgroundReplace", title, pos, (500, 260), group,
        [("image", "IMAGE", False), ("bg_removal_model", "BACKGROUND_REMOVAL", False),
         ("use_background", "BOOLEAN", True), ("background", "IMAGE", False)],
        [("image", "IMAGE")], [False], {"use_background": False}, "switch",
    )


def _save_image(g: Graph, title: str, prefix: str, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "SaveImage", title, pos, (420, 150), group,
        [("images", "IMAGE", False), ("filename_prefix", "STRING", True)], [("IMAGE", "IMAGE")],
        [prefix], {"filename_prefix": prefix}, "output",
    )


def _save_dds(g: Graph, title: str, prefix: str, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "Hoi4SaveDDS", title, pos, (420, 190), group,
        [("images", "IMAGE", False), ("filename_prefix", "STRING", True), ("compression", "COMBO", True)], [("images", "IMAGE")],
        [prefix, "dxt5"], {"filename_prefix": prefix, "compression": "dxt5"}, "output",
    )


def _batch_input(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    values = ["hoi4_portraits_batch", "*.png;*.jpg;*.jpeg;*.webp"]
    return g.node(
        "Hoi4BatchInput", "Batch input folder — list output runs one portrait at a time", pos, (700, 260), group,
        [("input_folder", "STRING", True), ("file_pattern", "STRING", True)],
        [("images", "IMAGE"), ("masks", "MASK"), ("filenames", "STRING")], values,
        {"input_folder": values[0], "file_pattern": values[1]}, "source",
    )


def _wire_style(g: Graph, model: dict[str, Ref], sampler: Ref, reference: Ref | None) -> None:
    g.connect(model["style"], 0, sampler, "model")
    g.connect(model["clip"], 0, sampler, "clip")
    g.connect(model["vae"], 0, sampler, "vae")
    if reference is not None:
        g.connect(reference, 0, sampler, "reference_image")


def build_source() -> tuple[dict[str, Any], dict[str, Any]]:
    g = Graph("hoi4_portrait_flux2_klein_9b_source", "HOI4 Portrait — source reference, three candidates")
    g.group("00 Welcome & setup", "#334155")
    g.group("01 Source processing — every node visible", "#365b41")
    g.group("02 Separate model loaders", "#365b73")
    g.group("03 Adonis Base → Refine — expanded upstream graph", "#765b35")
    g.group("04 Three live style candidates", "#654572")
    g.group("05 Automatic outputs", "#3d596f")
    g.group("06 Portrait comparison", "#334c61")

    _note(g, "📦 Setup — models, variants, and folders", SETUP_NOTE, (80, 100), (720, 760), "00 Welcome & setup")
    _note(g, "🎛️ Beginner + advanced sampler guide", SAMPLER_NOTE, (80, 940), (720, 700), "00 Welcome & setup")
    _note(g, "✍️ Exact prompt and why restoration helps", PROMPT_NOTE, (80, 1720), (720, 780), "00 Welcome & setup")

    source = _load_image(g, "Load source portrait — upload or choose here", "source_portrait.jpg", (960, 100), (600, 620), "01 Source processing — every node visible")
    source_preview = _preview(g, "Source preview", (960, 800), "01 Source processing — every node visible")
    g.connect(source, 0, source_preview, "images")
    esrgan = _source_pipeline(g, source, "01 Source processing — every node visible", x=1640)
    background = _load_image(g, "Optional replacement background", "hoi4_leader_portrait_background.png", (1640, 1180), (600, 560), "01 Source processing — every node visible")

    model = _model_pipeline(g, "02 Separate model loaders", x=2820, style=True, adonis=True, background=True)
    restored, _ = _adonis_pipeline(g, esrgan, model, "03 Adonis Base → Refine — expanded upstream graph", x=3980)

    finals: list[Ref] = []
    for index, (seed, y) in enumerate(((42, 100), (43, 960), (44, 1820)), start=1):
        sampler = _style_sampler(g, f"Candidate {index} — advanced live style sampler", (6820, y), "04 Three live style candidates", mode="source_reference", prompt=STYLE_PROMPT, seed=seed)
        replace = _background_replace(g, f"Candidate {index} — optional background replacement", (7620, y), "04 Three live style candidates")
        master = _image_scale(g, f"Candidate {index} master — centered 1024×1365 crop", 1024, 1365, (7620, y + 340), "04 Three live style candidates")
        game = _image_scale(g, f"Candidate {index} game — centered 156×210 crop", 156, 210, (7620, y + 600), "04 Three live style candidates")
        _wire_style(g, model, sampler, restored)
        g.connect(sampler, 0, replace, "image")
        g.connect(model["background_model"], 0, replace, "bg_removal_model")
        g.connect(background, 0, replace, "background")
        g.connect(replace, 0, master, "image")
        g.connect(master, 0, game, "image")
        finals.append(game)

        oy = 100 + (index - 1) * 480
        save_master = _save_image(g, f"Save candidate {index} master PNG", f"1024x1365/candidate_{index}", (8280, oy), "05 Automatic outputs")
        save_game = _save_image(g, f"Save candidate {index} game PNG", f"156x210/candidate_{index}", (8780, oy), "05 Automatic outputs")
        save_dds = _save_dds(g, f"Save candidate {index} DDS — DXT5, no mipmaps", f"156x210/dds/candidate_{index}", (8780, oy + 200), "05 Automatic outputs")
        g.connect(master, 0, save_master, "images")
        g.connect(game, 0, save_game, "images")
        g.connect(game, 0, save_dds, "images")

    comparison = [
        ("RealESRGAN prepared crop", esrgan),
        ("Adonis Base → Refine restored", restored),
        ("Final candidate 1 — 156×210", finals[0]),
        ("Final candidate 2 — 156×210", finals[1]),
        ("Final candidate 3 — 156×210", finals[2]),
    ]
    for index, (title, ref) in enumerate(comparison):
        preview = _preview(g, title, (2820 + index * 680, 1640), "06 Portrait comparison")
        g.connect(ref, 0, preview, "images")
    return g.serialize(style_lora=STYLE_LORA)


def build_text() -> tuple[dict[str, Any], dict[str, Any]]:
    g = Graph("hoi4_portrait_flux2_klein_9b_text_to_image", "HOI4 Portrait — text to image")
    g.group("00 Notes", "#334155")
    g.group("01 Separate model loaders", "#365b73")
    g.group("02 One advanced live sampler", "#654572")
    g.group("03 Visible background, sizing, saves, preview", "#3d596f")
    _note(g, "📦 Setup", SETUP_NOTE, (80, 100), (720, 800), "00 Notes")
    _note(g, "🎛️ Sampler guide", SAMPLER_NOTE, (80, 980), (720, 760), "00 Notes")
    model = _model_pipeline(g, "01 Separate model loaders", x=960, style=True, adonis=False, background=True)
    sampler = _style_sampler(g, "Text-to-image — advanced live sampler", (2120, 100), "02 One advanced live sampler", mode="text_to_image", prompt=TEXT_PROMPT, seed=42)
    _wire_style(g, model, sampler, None)

    replace = _background_replace(g, "Optional background replacement", (3000, 100), "03 Visible background, sizing, saves, preview")
    master = _image_scale(g, "Master — centered 1024×1365 crop", 1024, 1365, (3000, 440), "03 Visible background, sizing, saves, preview")
    game = _image_scale(g, "Game — centered 156×210 crop", 156, 210, (3000, 700), "03 Visible background, sizing, saves, preview")
    background = _load_image(g, "Optional replacement background", "hoi4_leader_portrait_background.png", (3580, 100), (600, 560), "03 Visible background, sizing, saves, preview")
    g.connect(sampler, 0, replace, "image")
    g.connect(model["background_model"], 0, replace, "bg_removal_model")
    g.connect(background, 0, replace, "background")
    g.connect(replace, 0, master, "image")
    g.connect(master, 0, game, "image")
    save_master = _save_image(g, "Save master PNG", "1024x1365/text_to_image", (3000, 960), "03 Visible background, sizing, saves, preview")
    save_game = _save_image(g, "Save game PNG", "156x210/text_to_image", (3000, 1200), "03 Visible background, sizing, saves, preview")
    save_dds = _save_dds(g, "Save game DDS — DXT5, no mipmaps", "156x210/dds/text_to_image", (3000, 1440), "03 Visible background, sizing, saves, preview")
    preview = _preview(g, "Final 156×210 portrait", (3580, 740), "03 Visible background, sizing, saves, preview")
    g.connect(master, 0, save_master, "images")
    g.connect(game, 0, save_game, "images")
    g.connect(game, 0, save_dds, "images")
    g.connect(game, 0, preview, "images")
    return g.serialize(style_lora=STYLE_LORA)


def build_processing() -> tuple[dict[str, Any], dict[str, Any]]:
    g = Graph("hoi4_portrait_processing_only", "HOI4 Portrait — processing and restoration only")
    g.group("00 Notes", "#334155")
    g.group("01 Source processing — every node visible", "#365b41")
    g.group("02 Separate model loaders", "#365b73")
    g.group("03 Adonis Base → Refine — expanded upstream graph", "#765b35")
    g.group("04 Visible sizing, saves, comparison", "#3d596f")
    _note(g, "📦 Setup", SETUP_NOTE, (80, 100), (720, 900), "00 Notes")
    _note(g, "✨ Processing-only guide", PROMPT_NOTE, (80, 1080), (720, 900), "00 Notes")
    source = _load_image(g, "Load source portrait", "source_portrait.jpg", (960, 340), (680, 620), "01 Source processing — every node visible")
    esrgan = _source_pipeline(g, source, "01 Source processing — every node visible", x=1720)
    model = _model_pipeline(g, "02 Separate model loaders", x=2900, style=False, adonis=True, background=False)
    restored, _ = _adonis_pipeline(g, esrgan, model, "03 Adonis Base → Refine — expanded upstream graph", x=4060)
    master = _image_scale(g, "Restored master — centered 1024×1365 crop", 1024, 1365, (6900, 100), "04 Visible sizing, saves, comparison")
    game = _image_scale(g, "Restored game — centered 156×210 crop", 156, 210, (7380, 100), "04 Visible sizing, saves, comparison")
    g.connect(restored, 0, master, "image")
    g.connect(master, 0, game, "image")
    save_master = _save_image(g, "Save restored master PNG", "1024x1365/processing_only", (7860, 100), "04 Visible sizing, saves, comparison")
    save_game = _save_image(g, "Save restored game PNG", "156x210/processing_only", (7860, 340), "04 Visible sizing, saves, comparison")
    save_dds = _save_dds(g, "Save restored game DDS", "156x210/dds/processing_only", (7860, 580), "04 Visible sizing, saves, comparison")
    g.connect(master, 0, save_master, "images")
    g.connect(game, 0, save_game, "images")
    g.connect(game, 0, save_dds, "images")
    for index, (title, ref) in enumerate((("RealESRGAN", esrgan), ("Adonis Base → Refine", restored), ("Final 156×210", game))):
        preview = _preview(g, title, (6900 + index * 680, 860), "04 Visible sizing, saves, comparison")
        g.connect(ref, 0, preview, "images")
    return g.serialize(style_lora=None)


def build_batch() -> tuple[dict[str, Any], dict[str, Any]]:
    g = Graph("hoi4_portrait_batch", "HOI4 Portrait — batch input and output")
    g.group("00 Batch guide", "#334155")
    g.group("01 One-at-a-time source processing", "#365b41")
    g.group("02 Separate model loaders", "#365b73")
    g.group("03 Adonis Base → Refine — expanded upstream graph", "#765b35")
    g.group("04 One live sampler + visible outputs", "#654572")
    _note(g, "🖼️ Batch input and output", BATCH_NOTE, (80, 100), (720, 920), "00 Batch guide")
    _note(g, "🎛️ Sampler guide", SAMPLER_NOTE, (80, 1100), (720, 900), "00 Batch guide")
    batch = _batch_input(g, (960, 480), "01 One-at-a-time source processing")
    esrgan = _source_pipeline(g, batch, "01 One-at-a-time source processing", x=1740)
    model = _model_pipeline(g, "02 Separate model loaders", x=2920, style=True, adonis=True, background=False)
    restored, _ = _adonis_pipeline(g, esrgan, model, "03 Adonis Base → Refine — expanded upstream graph", x=4080)
    sampler = _style_sampler(g, "Batch portrait — one advanced live sampler", (6920, 100), "04 One live sampler + visible outputs", mode="source_reference", prompt=STYLE_PROMPT, seed=42)
    _wire_style(g, model, sampler, restored)
    master = _image_scale(g, "Batch master — centered 1024×1365 crop", 1024, 1365, (7720, 100), "04 One live sampler + visible outputs")
    game = _image_scale(g, "Batch game — centered 156×210 crop", 156, 210, (8200, 100), "04 One live sampler + visible outputs")
    g.connect(sampler, 0, master, "image")
    g.connect(master, 0, game, "image")
    save_master = _save_image(g, "Save every master PNG", "1024x1365/batch", (7720, 360), "04 One live sampler + visible outputs")
    save_game = _save_image(g, "Save every game PNG", "156x210/batch", (8200, 360), "04 One live sampler + visible outputs")
    save_dds = _save_dds(g, "Save every game DDS", "156x210/dds/batch", (8200, 600), "04 One live sampler + visible outputs")
    g.connect(master, 0, save_master, "images")
    g.connect(game, 0, save_game, "images")
    g.connect(game, 0, save_dds, "images")
    for index, (title, ref) in enumerate((("RealESRGAN", esrgan), ("Adonis restored", restored), ("Final 156×210", game))):
        preview = _preview(g, title, (6920 + index * 680, 960), "04 One live sampler + visible outputs")
        g.connect(ref, 0, preview, "images")
    return g.serialize(style_lora=STYLE_LORA)


BUILDERS = {
    "hoi4_portrait_flux2_klein_9b_source": build_source,
    "hoi4_portrait_flux2_klein_9b_text_to_image": build_text,
    "hoi4_portrait_processing_only": build_processing,
    "hoi4_portrait_batch": build_batch,
}


def build_all(root: Path = ROOT) -> list[Path]:
    output = root / "workflows"
    output.mkdir(parents=True, exist_ok=True)
    for stale in output.glob("*.json"):
        stale.unlink()
    written: list[Path] = []
    manifest = {"schema_version": SCHEMA_VERSION, "default_workflows": len(BUILDERS), "workflows": []}
    for workflow_id, builder in BUILDERS.items():
        ui, api = builder()
        ui_path = output / f"{workflow_id}.json"
        api_path = output / f"{workflow_id}.api.json"
        ui_path.write_text(json.dumps(ui, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        api_path.write_text(json.dumps(api, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.extend((ui_path, api_path))
        manifest["workflows"].append(
            {
                "id": workflow_id,
                "title": ui["extra"]["title"],
                "workflow": ui_path.name,
                "api_workflow": api_path.name,
                "nodes": len(ui["nodes"]),
            }
        )
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    written.append(manifest_path)
    return written


def main() -> int:
    for path in build_all():
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
