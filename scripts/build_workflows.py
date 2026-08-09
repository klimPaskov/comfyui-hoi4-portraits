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

def _build_setup_note() -> str:
    catalog = json.loads((ROOT / "models.json").read_text())
    downloads = []
    for model in catalog["models"]:
        variant = f" [{model['variant']}]" if model.get("variant") not in {None, "shared"} else ""
        downloads.extend((f"⬇️ {model['filename']}{variant}", model["url"]))
    return "\n".join(
        (
            "📦 FILES + DOWNLOADS",
            "The installer can place these for you. If you install them by hand, use these folders:",
            "",
            "📂 ComfyUI/models/",
            "├── 🧠 diffusion_models/ — choose one FLUX.2 file",
            "├── 💬 text_encoders/ — Qwen3-8B-Q8_0.gguf",
            "├── 🎨 vae/ — flux2-vae.safetensors",
            "├── 🧩 loras/ — HOI4 style + Adonis Base + Adonis Refine",
            "├── 🔎 upscale_models/ — RealESRGAN_x2plus.pth",
            "├── ✂️ background_removal/ — birefnet.safetensors",
            "└── 🙂 detection/ — MediaPipe + YuNet fallback",
            "",
            "Direct downloads:",
            *downloads,
        )
    )


SETUP_NOTE = _build_setup_note()

PREP_NOTE = (
    "🙂 Start with a clear portrait. The crop follows the face and leaves room for hats. "
    "Use the manual crop controls only when the automatic crop misses."
)

RESTORE_NOTE = (
    "✨ This cleans up blur, colour damage, and missing facial detail before styling. "
    "Leave the red switch on for old or low-quality photos; turn it off for a clean modern image."
)

STYLE_NOTE = (
    f"🎨 Keep the prompt as: {STYLE_PROMPT}\n"
    "Add only a few identity or clothing details if you need them. Change the seed for a different portrait."
)

TEXT_STYLE_NOTE = (
    "🎨 Describe the person and clothing in one short sentence. The defaults are a good starting point: "
    "4 steps, CFG 1, guidance 1, Euler, simple."
)

BATCH_NOTE = (
    "🖼️ Put PNG, JPG, JPEG, or WebP files in input/hoi4_portraits_batch/ and queue once. "
    "Each photo runs on its own and keeps the same settings."
)

OUTPUT_NOTE = (
    "💾 The DDS is the game portrait: 156×210, A8R8G8B8, no mipmaps. "
    "Move it to your mod's gfx/leaders/TAG/ folder and reference it from the portrait sprite."
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
        self._group_node_colors: dict[str, str] = {}
        self._node_id = 0
        self._link_id = 0

    def group(self, title: str, color: str, node_color: str) -> None:
        if title in self._group_titles:
            raise ValueError(f"duplicate group title: {title}")
        self._group_titles.add(title)
        self._group_node_colors[title] = node_color
        self.groups.append(
            {
                "id": len(self.groups) + 1,
                "title": title,
                "bounding": [0, 0, 0, 0],
                "color": color,
                "font_size": 28,
                "flags": {"collapsed": False},
                "properties": {"hoi4_node_color": node_color},
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
        color: str | None = None,
    ) -> Ref:
        if group not in self._group_titles:
            raise ValueError(f"unknown visible group: {group}")
        self._node_id += 1
        node_id = self._node_id
        node_color = "switch" if color == "switch" else self._group_node_colors[group]
        foreground, background = COLORS[node_color]
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
            "dds": {"format": "A8R8G8B8", "mipmaps": False},
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
        "UNETLoader", "FLUX.2 Klein 9B", pos, (440, 130), group,
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
        "MediaPipeFaceLandmarker", "Find the face", pos, (500, 300), group,
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
        "AdaptivePortraitCrop", "Crop portrait to 512×683", pos, (480, 420), group,
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
    normalized = _image_scale(g, "Resize prepared portrait to 1024×1365", 1024, 1365, (x + 540, 920), group)
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
        "ImageScaleToTotalPixelsX", "Resize for restoration — 1.7 MP", pos, (400, 240), group,
        [("image", "IMAGE", False), ("megapixels", "FLOAT", True), ("multiple_of", "INT", True),
         ("resize_mode", "COMBO", True), ("upscale_method", "COMBO", True)],
        [("image", "IMAGE"), ("width", "INT"), ("height", "INT")],
        values, dict(zip(("megapixels", "multiple_of", "resize_mode", "upscale_method"), values)), "restore",
    )


def _clip_encode(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "CLIPTextEncode", "Restoration prompt", pos, (440, 260), group,
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
        "EmptyFlux2LatentImage", "Restoration latent", pos, (360, 180), group,
        [("width", "INT", True), ("height", "INT", True), ("batch_size", "INT", True)], [("LATENT", "LATENT")],
        values, dict(zip(("width", "height", "batch_size"), values)), "restore",
    )


def _shark_options(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    values = ["laplacian", 1.0, 1.0, False]
    return g.node(
        "SharkOptions_Beta", "Restoration sampler settings", pos, (400, 180), group,
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
    base = _adonis_sampler(g, "Restore details — Base pass (steps 1–5)", (x + 1360, 100), group, refine=False)
    refine = _adonis_sampler(g, "Restore details — Refine pass", (x + 1940, 100), group, refine=True)
    decoded = _vae_decode(g, (x + 1940, 1280), group)
    enabled = _switch(g, "Use restored portrait", True, (x + 2320, 1280), group)

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


def _model_pipeline(g: Graph, group: str, *, x: int, y: int = 100, style: bool, adonis: bool, background: bool) -> dict[str, Ref]:
    unet = _unet(g, (x, y), group)
    clip = _clip(g, (x, y + 220), group)
    vae = _vae(g, (x, y + 440), group)
    result: dict[str, Ref] = {"unet": unet, "clip": clip, "vae": vae}
    if style:
        style_lora = _lora(g, "HOI4 portrait style LoRA", STYLE_LORA, (x + 500, y), group)
        g.connect(unet, 0, style_lora, "model")
        result["style"] = style_lora
    if adonis:
        base = _lora(g, "Adonis Base LoRA", ADONIS_BASE, (x + 500, y + 220), group)
        refine = _lora(g, "Adonis Refine LoRA", ADONIS_REFINE, (x + 500, y + 440), group)
        g.connect(unet, 0, base, "model")
        g.connect(unet, 0, refine, "model")
        result.update({"adonis_base": base, "adonis_refine": refine})
    if background:
        result["background_model"] = _background_model(g, (x, y + 620), group)
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


def _image_batch(g: Graph, title: str, first: Ref, second: Ref, pos: tuple[int, int], group: str) -> Ref:
    node = g.node(
        "ImageBatch", title, pos, (360, 100), group,
        [("image1", "IMAGE", False), ("image2", "IMAGE", False)], [("IMAGE", "IMAGE")], [], {},
    )
    g.connect(first, 0, node, "image1")
    g.connect(second, 0, node, "image2")
    return node


def _image_from_batch(g: Graph, title: str, image: Ref, index: int, pos: tuple[int, int], group: str) -> Ref:
    node = g.node(
        "ImageFromBatch", title, pos, (360, 140), group,
        [("image", "IMAGE", False), ("batch_index", "INT", True), ("length", "INT", True)],
        [("IMAGE", "IMAGE")], [index, 1], {"batch_index": index, "length": 1},
    )
    g.connect(image, 0, node, "image")
    return node


def _save_image(g: Graph, title: str, prefix: str, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "SaveImage", title, pos, (420, 150), group,
        [("images", "IMAGE", False), ("filename_prefix", "STRING", True)], [("IMAGE", "IMAGE")],
        [prefix], {"filename_prefix": prefix}, "output",
    )


def _save_dds(g: Graph, title: str, prefix: str, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "Hoi4SaveDDS", title, pos, (420, 190), group,
        [("images", "IMAGE", False), ("filename_prefix", "STRING", True), ("format", "COMBO", True)], [("images", "IMAGE")],
        [prefix, "argb8888"], {"filename_prefix": prefix, "format": "argb8888"}, "output",
    )


def _batch_input(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    values = ["hoi4_portraits_batch", "*.png;*.jpg;*.jpeg;*.webp"]
    return g.node(
        "Hoi4BatchInput", "Batch portrait folder", pos, (700, 260), group,
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
    g = Graph("hoi4_portrait_flux2_klein_9b_source", "HOI4 Portrait — source reference, three portraits")
    g.group("00 Setup", "#334155", "note")
    g.group("01 Prepare portrait", "#365b41", "source")
    g.group("02 Models", "#365b73", "model")
    g.group("03 Restore details", "#765b35", "restore")
    g.group("04 Create three portraits", "#654572", "sample")
    g.group("05 Save portraits", "#3d596f", "output")
    g.group("06 Compare portraits", "#334c61", "output")

    _note(g, "📦 Files and downloads", SETUP_NOTE, (80, 100), (1320, 1100), "00 Setup")

    source = _load_image(g, "Choose a source portrait", "source_portrait.jpg", (1560, 100), (600, 620), "01 Prepare portrait")
    source_preview = _preview(g, "Source portrait", (1560, 800), "01 Prepare portrait")
    g.connect(source, 0, source_preview, "images")
    esrgan = _source_pipeline(g, source, "01 Prepare portrait", x=2240)
    _note(g, "🙂 Cropping tip", PREP_NOTE, (2240, 1160), (1020, 180), "01 Prepare portrait")

    model = _model_pipeline(g, "02 Models", x=1560, y=1800, style=True, adonis=True, background=True)
    restored, _ = _adonis_pipeline(g, esrgan, model, "03 Restore details", x=3420)
    _note(g, "✨ When to restore", RESTORE_NOTE, (3420, 920), (440, 180), "03 Restore details")

    portraits: list[Ref] = []
    for index, (seed, y) in enumerate(((42, 100), (43, 960), (44, 1820)), start=1):
        sampler = _style_sampler(g, f"Portrait {index}", (6940, y), "04 Create three portraits", mode="source_reference", prompt=STYLE_PROMPT, seed=seed)
        _wire_style(g, model, sampler, restored)
        portraits.append(sampler)

    _note(g, "🎨 Prompt tip", STYLE_NOTE, (7740, 100), (600, 180), "04 Create three portraits")
    first_pair = _image_batch(g, "Join portraits 1 and 2", portraits[0], portraits[1], (7740, 360), "04 Create three portraits")
    all_portraits = _image_batch(g, "Add portrait 3", first_pair, portraits[2], (7740, 520), "04 Create three portraits")
    background = _load_image(g, "Choose a replacement background", "hoi4_leader_portrait_background.png", (7740, 700), (600, 560), "04 Create three portraits")
    replace = _background_replace(g, "Use replacement background", (7740, 1340), "04 Create three portraits")
    g.connect(all_portraits, 0, replace, "image")
    g.connect(model["background_model"], 0, replace, "bg_removal_model")
    g.connect(background, 0, replace, "background")

    finals: list[Ref] = []
    masters: list[Ref] = []
    for index, y in enumerate((760, 1020, 1280), start=1):
        portrait = _image_from_batch(g, f"Take portrait {index}", replace, index - 1, (8420, 100 + (index - 1) * 220), "04 Create three portraits")
        master = _image_scale(g, f"Portrait {index} master — 1024×1365", 1024, 1365, (8420, y), "04 Create three portraits")
        game = _image_scale(g, f"Portrait {index} game — 156×210", 156, 210, (8900, y), "04 Create three portraits")
        g.connect(portrait, 0, master, "image")
        g.connect(master, 0, game, "image")
        masters.append(master)
        finals.append(game)

    for index, (master, game) in enumerate(zip(masters, finals), start=1):
        oy = 100 + (index - 1) * 480
        save_master = _save_image(g, f"Save portrait {index} master PNG", f"1024x1365/portrait_{index}", (9460, oy), "05 Save portraits")
        save_game = _save_image(g, f"Save portrait {index} game PNG", f"156x210/portrait_{index}", (9960, oy), "05 Save portraits")
        save_dds = _save_dds(g, f"Save portrait {index} DDS", f"156x210/dds/portrait_{index}", (9960, oy + 200), "05 Save portraits")
        g.connect(master, 0, save_master, "images")
        g.connect(game, 0, save_game, "images")
        g.connect(game, 0, save_dds, "images")
    _note(g, "💾 Using the DDS", OUTPUT_NOTE, (9460, 1680), (920, 180), "05 Save portraits")

    comparison = [
        ("Prepared portrait", esrgan),
        ("Restored portrait", restored),
        ("Portrait 1 — 156×210", finals[0]),
        ("Portrait 2 — 156×210", finals[1]),
        ("Portrait 3 — 156×210", finals[2]),
    ]
    for index, (title, ref) in enumerate(comparison):
        preview = _preview(g, title, (3420 + index * 680, 1700), "06 Compare portraits")
        g.connect(ref, 0, preview, "images")
    return g.serialize(style_lora=STYLE_LORA)


def build_text() -> tuple[dict[str, Any], dict[str, Any]]:
    g = Graph("hoi4_portrait_flux2_klein_9b_text_to_image", "HOI4 Portrait — text to image")
    g.group("00 Setup", "#334155", "note")
    g.group("01 Models", "#365b73", "model")
    g.group("02 Create portrait", "#654572", "sample")
    g.group("03 Finish and save", "#3d596f", "output")
    _note(g, "📦 Files and downloads", SETUP_NOTE, (80, 100), (1320, 1100), "00 Setup")
    model = _model_pipeline(g, "01 Models", x=1560, style=True, adonis=False, background=True)
    sampler = _style_sampler(g, "Create portrait from text", (2720, 100), "02 Create portrait", mode="text_to_image", prompt=TEXT_PROMPT, seed=42)
    _note(g, "🎨 Writing the prompt", TEXT_STYLE_NOTE, (2720, 960), (720, 180), "02 Create portrait")
    _wire_style(g, model, sampler, None)

    replace = _background_replace(g, "Use replacement background", (3600, 100), "03 Finish and save")
    master = _image_scale(g, "Master portrait — 1024×1365", 1024, 1365, (3600, 440), "03 Finish and save")
    game = _image_scale(g, "Game portrait — 156×210", 156, 210, (3600, 700), "03 Finish and save")
    background = _load_image(g, "Choose a replacement background", "hoi4_leader_portrait_background.png", (4180, 100), (600, 560), "03 Finish and save")
    g.connect(sampler, 0, replace, "image")
    g.connect(model["background_model"], 0, replace, "bg_removal_model")
    g.connect(background, 0, replace, "background")
    g.connect(replace, 0, master, "image")
    g.connect(master, 0, game, "image")
    save_master = _save_image(g, "Save master PNG", "1024x1365/text_to_image", (3600, 960), "03 Finish and save")
    save_game = _save_image(g, "Save game PNG", "156x210/text_to_image", (3600, 1200), "03 Finish and save")
    save_dds = _save_dds(g, "Save game DDS", "156x210/dds/text_to_image", (3600, 1440), "03 Finish and save")
    preview = _preview(g, "Game portrait", (4180, 740), "03 Finish and save")
    _note(g, "💾 Using the DDS", OUTPUT_NOTE, (4180, 1620), (600, 180), "03 Finish and save")
    g.connect(master, 0, save_master, "images")
    g.connect(game, 0, save_game, "images")
    g.connect(game, 0, save_dds, "images")
    g.connect(game, 0, preview, "images")
    return g.serialize(style_lora=STYLE_LORA)


def build_processing() -> tuple[dict[str, Any], dict[str, Any]]:
    g = Graph("hoi4_portrait_processing_only", "HOI4 Portrait — processing and restoration only")
    g.group("00 Setup", "#334155", "note")
    g.group("01 Prepare portrait", "#365b41", "source")
    g.group("02 Models", "#365b73", "model")
    g.group("03 Restore details", "#765b35", "restore")
    g.group("04 Finish and save", "#3d596f", "output")
    _note(g, "📦 Files and downloads", SETUP_NOTE, (80, 100), (1320, 1100), "00 Setup")
    _note(g, "🙂 Cropping tip", PREP_NOTE, (1560, 100), (680, 180), "01 Prepare portrait")
    source = _load_image(g, "Choose a source portrait", "source_portrait.jpg", (1560, 340), (680, 620), "01 Prepare portrait")
    esrgan = _source_pipeline(g, source, "01 Prepare portrait", x=2320)
    model = _model_pipeline(g, "02 Models", x=1560, y=1320, style=False, adonis=True, background=False)
    restored, _ = _adonis_pipeline(g, esrgan, model, "03 Restore details", x=3500)
    _note(g, "✨ When to restore", RESTORE_NOTE, (3500, 920), (440, 180), "03 Restore details")
    master = _image_scale(g, "Restored master — 1024×1365", 1024, 1365, (6340, 100), "04 Finish and save")
    game = _image_scale(g, "Game portrait — 156×210", 156, 210, (6820, 100), "04 Finish and save")
    g.connect(restored, 0, master, "image")
    g.connect(master, 0, game, "image")
    save_master = _save_image(g, "Save restored master PNG", "1024x1365/processing_only", (7300, 100), "04 Finish and save")
    save_game = _save_image(g, "Save game PNG", "156x210/processing_only", (7300, 340), "04 Finish and save")
    save_dds = _save_dds(g, "Save game DDS", "156x210/dds/processing_only", (7300, 580), "04 Finish and save")
    _note(g, "💾 Using the DDS", OUTPUT_NOTE, (7300, 840), (420, 180), "04 Finish and save")
    g.connect(master, 0, save_master, "images")
    g.connect(game, 0, save_game, "images")
    g.connect(game, 0, save_dds, "images")
    for index, (title, ref) in enumerate((("Prepared portrait", esrgan), ("Restored portrait", restored), ("Game portrait", game))):
        preview = _preview(g, title, (6340 + index * 680, 1120), "04 Finish and save")
        g.connect(ref, 0, preview, "images")
    return g.serialize(style_lora=None)


def build_batch() -> tuple[dict[str, Any], dict[str, Any]]:
    g = Graph("hoi4_portrait_batch", "HOI4 Portrait — batch input and output")
    g.group("00 Setup", "#334155", "note")
    g.group("01 Prepare portraits", "#365b41", "source")
    g.group("02 Models", "#365b73", "model")
    g.group("03 Restore details", "#765b35", "restore")
    g.group("04 Create and save", "#654572", "sample")
    _note(g, "📦 Files and downloads", SETUP_NOTE, (80, 100), (1320, 1100), "00 Setup")
    _note(g, "🖼️ Batch folder", BATCH_NOTE, (1560, 100), (700, 180), "01 Prepare portraits")
    batch = _batch_input(g, (1560, 480), "01 Prepare portraits")
    esrgan = _source_pipeline(g, batch, "01 Prepare portraits", x=2340)
    model = _model_pipeline(g, "02 Models", x=1560, y=1320, style=True, adonis=True, background=False)
    restored, _ = _adonis_pipeline(g, esrgan, model, "03 Restore details", x=3540)
    _note(g, "✨ When to restore", RESTORE_NOTE, (3540, 920), (440, 180), "03 Restore details")
    sampler = _style_sampler(g, "Create each portrait", (6380, 100), "04 Create and save", mode="source_reference", prompt=STYLE_PROMPT, seed=42)
    _note(g, "🎨 Prompt tip", STYLE_NOTE, (6380, 960), (720, 180), "04 Create and save")
    _wire_style(g, model, sampler, restored)
    master = _image_scale(g, "Master portrait — 1024×1365", 1024, 1365, (7180, 100), "04 Create and save")
    game = _image_scale(g, "Game portrait — 156×210", 156, 210, (7660, 100), "04 Create and save")
    g.connect(sampler, 0, master, "image")
    g.connect(master, 0, game, "image")
    save_master = _save_image(g, "Save every master PNG", "1024x1365/batch", (7180, 360), "04 Create and save")
    save_game = _save_image(g, "Save every game PNG", "156x210/batch", (7660, 360), "04 Create and save")
    save_dds = _save_dds(g, "Save every game DDS", "156x210/dds/batch", (7660, 600), "04 Create and save")
    _note(g, "💾 Using the DDS", OUTPUT_NOTE, (7660, 860), (600, 180), "04 Create and save")
    g.connect(master, 0, save_master, "images")
    g.connect(game, 0, save_game, "images")
    g.connect(game, 0, save_dds, "images")
    for index, (title, ref) in enumerate((("Prepared portrait", esrgan), ("Restored portrait", restored), ("Game portrait", game))):
        preview = _preview(g, title, (6380 + index * 680, 1220), "04 Create and save")
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
