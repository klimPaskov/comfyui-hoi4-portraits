#!/usr/bin/env python3
"""Build four fully visible HOI4 ComfyUI workflows deterministically."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / "workflows"
SCHEMA_VERSION = "1.0.0"

BASE_MODEL = "flux-2-klein-9b.safetensors"
TEXT_ENCODER = "Qwen3-8B-Q8_0.gguf"
VAE_MODEL = "flux2-vae.safetensors"
STYLE_LORA = "hoi4_portrait_flux2_klein_9b_lora_000002500.safetensors"
ADONIS_BASE = "adonis_base.safetensors"
ADONIS_REFINE = "adonis_refine.safetensors"
ADONIS_POST = "adonis_post.safetensors"
ADONIS_REVISION = "515ecf66717d14309a055811b3d478cdfa59bbda"
ADONIS_WORKFLOW = "adonis_post_workflows/Adonis_Base_Post_gguf.json"
ESRGAN_MODEL = "RealESRGAN_x2plus.pth"
BACKGROUND_MODEL = "birefnet.safetensors"
FACE_MODEL = "mediapipe_face_fp32.safetensors"

STYLE_PROMPT = "make this portrait hoi4_portrait style"
TEXT_PROMPT = (
    "hoi4_portrait style, an Irish middle-aged man with neatly combed dark hair, "
    "wearing a plain civilian jacket."
)
ADONIS_FIXED_PROMPT = (
    "Remove compression artifacts, halftone patterns, periodic grid noise, scratches, dust, scanning artifacts, sensor noise, and other defects only where present. "
    "Reconstruct missing fine detail across the background, environment, surfaces, objects, clothing, and foreground while keeping texture natural and avoiding oversharpening.\n\n"
    "Preserve the subject exactly: keep facial and body geometry, eye shape, nose and mouth shape, expression, pose, apparent age, distinctive features, composition, crop, and perspective unchanged.\n\n"
    "Restore natural skin, hair, fabric, and material texture without plastic smoothing or invented features. Recover strand separation, edge definition, and fine surface detail conservatively where the source is soft or damaged.\n\n"
    "Preserve the source's intended colour treatment and historical character. Keep monochrome or sepia images monochrome or sepia unless colourisation is explicitly requested; for colour images, correct unwanted casts without inventing colours.\n\n"
    "Output a clean, faithful, high-resolution archival restoration."
)
ADONIS_BASE_PROMPT = "faithfully restore and reconstruct this entire image from its current source quality to clean high-resolution archival quality."
ADONIS_POST_PROMPT = "refine natural skin, hair, clothing, objects, and background detail; remove remaining artifacts without altering identity, composition, expression, or the source's intended colour treatment."
ADONIS_BASE_COMBINED_PROMPT = f"{ADONIS_BASE_PROMPT} {ADONIS_FIXED_PROMPT}"
ADONIS_POST_COMBINED_PROMPT = f"{ADONIS_POST_PROMPT} {ADONIS_FIXED_PROMPT}"

SETUP_GUIDE_SIZE = (620, 1440)

COLORS = {
    "note": ("#6b4c36", "#3f2f24"),
    "source": ("#446a4d", "#304c38"),
    "model": ("#385d7a", "#29465c"),
    "restore": ("#80613d", "#5d472e"),
    "sample": ("#705080", "#523b60"),
    "output": ("#47647a", "#344b5c"),
    "switch": ("#b84949", "#702f2f"),
}

# The right half follows the user's hand-arranged source workflow, snapped to a consistent grid and regularized into aligned columns and portrait lanes.
SOURCE_LAYOUT = {
    34: ((4640, 1240), (260, 80)),
    35: ((4160, 800), None),
    36: ((4640, 1360), None),
    37: ((5200, 100), None),
    38: ((5200, 480), None),
    39: ((5200, 720), None),
    40: ((5200, 860), None),
    41: ((5200, 1000), None),
    42: ((5200, 1140), None),
    43: ((5760, 100), (560, 420)),
    44: ((6360, 100), None),
    45: ((5760, 600), (560, 420)),
    46: ((6360, 600), None),
    47: ((5760, 1100), (560, 420)),
    48: ((6360, 1100), None),
    49: ((6720, 100), None),
    50: ((6720, 240), None),
    51: ((6720, 400), None),
    52: ((6720, 1000), None),
    53: ((7360, 100), None),
    54: ((7360, 740), None),
    55: ((7800, 740), None),
    56: ((7360, 320), None),
    57: ((7360, 1000), None),
    58: ((7800, 1000), None),
    59: ((7360, 540), None),
    60: ((7360, 1260), None),
    61: ((7800, 1260), None),
    62: ((8360, 100), None),
    63: ((8360, 300), None),
    64: ((8820, 100), None),
    65: ((8820, 300), (420, 180)),
    66: ((8360, 620), None),
    67: ((8360, 820), None),
    68: ((8820, 620), None),
    69: ((8820, 820), (420, 180)),
    70: ((8360, 1140), None),
    71: ((8360, 1340), None),
    72: ((8820, 1140), None),
    73: ((8820, 1340), (420, 180)),
    74: ((2800, 1720), None),
    75: ((3440, 1720), None),
    76: ((4080, 1720), None),
    77: ((4720, 1720), None),
    78: ((5360, 1720), None),
}

BATCH_LAYOUT = {
    34: ((4160, 800), None),
    35: ((4640, 1380), None),
    36: ((5200, 100), None),
    37: ((5200, 480), None),
    38: ((5760, 100), None),
    39: ((5760, 280), None),
    40: ((6160, 100), None),
    41: ((6160, 280), None),
    42: ((6520, 100), (520, 500)),
    43: ((7080, 100), None),
    44: ((7540, 100), None),
    45: ((8000, 100), None),
    46: ((7540, 360), None),
    47: ((8000, 360), None),
    48: ((8000, 600), None),
    49: ((7540, 600), None),
    50: ((5360, 740), None),
    51: ((6000, 740), None),
    52: ((6640, 740), None),
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
        self._input_specs: dict[int, list[tuple[str, str, bool]]] = {}
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
        self._input_specs[node_id] = list(inputs)
        ui_inputs = [
            {"name": name, "type": type_name, "link": None}
            for name, type_name, is_widget in inputs
            if not is_widget
        ]
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

    def connect(
        self,
        source: Ref,
        source_slot: int,
        target: Ref,
        target_input: str,
        *,
        api_target_input: str | None = None,
    ) -> None:
        source_node = self.nodes[source.node_id - 1]
        target_node = self.nodes[target.node_id - 1]
        if not any(item["name"] == target_input for item in target_node["inputs"]):
            specs = self._input_specs[target.node_id]
            spec_index = next(index for index, item in enumerate(specs) if item[0] == target_input)
            name, type_name, is_widget = specs[spec_index]
            if not is_widget:
                raise ValueError(f"missing non-widget input socket: {target_input}")
            included_names = {item["name"] for item in target_node["inputs"]}
            insertion_index = sum(1 for item in specs[:spec_index] if not item[2] or item[0] in included_names)
            target_node["inputs"].insert(
                insertion_index,
                {"name": name, "type": type_name, "link": None, "widget": {"name": name}},
            )
            for link in self.links:
                if link[3] == target.node_id and link[4] >= insertion_index:
                    link[4] += 1
        target_slot = next(index for index, item in enumerate(target_node["inputs"]) if item["name"] == target_input)
        self._link_id += 1
        link_id = self._link_id
        link_type = source_node["outputs"][source_slot]["type"]
        self.links.append([link_id, source.node_id, source_slot, target.node_id, target_slot, link_type])
        target_node["inputs"][target_slot]["link"] = link_id
        if source_node["outputs"][source_slot]["links"] is None:
            source_node["outputs"][source_slot]["links"] = []
        source_node["outputs"][source_slot]["links"].append(link_id)
        self.api[str(target.node_id)]["inputs"][api_target_input or target_input] = [str(source.node_id), source_slot]

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

    def apply_layout(self, layout: dict[int, tuple[tuple[int, int], tuple[int, int] | None]]) -> None:
        """Apply a reviewed editor layout without changing graph semantics."""

        for node_id, (position, size) in layout.items():
            node = self.nodes[node_id - 1]
            if node["id"] != node_id:
                raise ValueError(f"layout node id mismatch: {node_id}")
            node["pos"] = list(position)
            if size is not None:
                node["size"] = list(size)

    def serialize(self, *, style_lora: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
        self._fit_groups()
        uses_adonis = any(
            node.get("type") == "LoraLoaderModelOnly" and ADONIS_POST in node.get("widgets_values", [])
            for node in self.nodes
        )
        extra = {
            "workflow_id": self.workflow_id,
            "title": self.title,
            "schema_version": SCHEMA_VERSION,
            "base_model": BASE_MODEL,
            "style_lora": style_lora,
            "master_size": [1024, 1365],
            "game_size": [156, 210],
            "dds": {"format": "A8R8G8B8", "mipmaps": False},
            "adonis": {
                "source": "n8te0/adonis_flux2klein",
                "revision": ADONIS_REVISION,
                "workflow": ADONIS_WORKFLOW,
                "passes": ["adonis_base.safetensors", "adonis_post.safetensors"],
            } if uses_adonis else None,
            "frontendVersion": "1.45.19",
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


def _setup_guide(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "Hoi4SetupGuide", "📂 Setup and downloads", pos, SETUP_GUIDE_SIZE, group,
        [], [], [], {}, "note",
    )


def _load_image(
    g: Graph,
    title: str,
    filename: str,
    pos: tuple[int, int],
    size: tuple[int, int],
    group: str,
    *,
    keep_filename: bool = False,
) -> Ref:
    class_type = "Hoi4LoadImage" if keep_filename else "LoadImage"
    outputs = [("IMAGE", "IMAGE"), ("MASK", "MASK")]
    if keep_filename:
        outputs.append(("filename", "STRING"))
    return g.node(
        class_type, title, pos, size, group,
        [("image", "COMBO", True)], outputs,
        [filename, "image"], {"image": filename}, "source",
    )


def _preview(g: Graph, title: str, pos: tuple[int, int], group: str, color: str | None = "output") -> Ref:
    return g.node(
        "PreviewImage", title, pos, (600, 810), group,
        [("images", "IMAGE", False)], [("IMAGE", "IMAGE")], [], {}, color,
    )


def _unet(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "UNETLoader", "FLUX.2 Klein 9B", pos, (400, 130), group,
        [("unet_name", "COMBO", True), ("weight_dtype", "COMBO", True)], [("MODEL", "MODEL")],
        [BASE_MODEL, "default"], {"unet_name": BASE_MODEL, "weight_dtype": "default"}, "model",
    )


def _clip(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    values = [TEXT_ENCODER, "flux2", "default"]
    return g.node(
        "ClipLoaderGGUF", "Load Qwen3 8B Q8 text encoder", pos, (400, 160), group,
        [("clip_name", "COMBO", True), ("type", "COMBO", True), ("device", "COMBO", True)], [("CLIP", "CLIP")],
        values, dict(zip(("clip_name", "type", "device"), values)), "model",
    )


def _vae(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "VAELoader", "Load FLUX.2 VAE", pos, (400, 100), group,
        [("vae_name", "COMBO", True)], [("VAE", "VAE")], [VAE_MODEL], {"vae_name": VAE_MODEL}, "model",
    )


def _lora(g: Graph, title: str, filename: str, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "LoraLoaderModelOnly", title, pos, (400, 140), group,
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
        "LoadBackgroundRemovalModel", "Load BiRefNet mask model", pos, (400, 100), group,
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
    bounding_box_widgets = [{"x": 0, "y": 0, "width": 512, "height": 512}, 0, 0, 512, 512]
    return g.node(
        "AdaptivePortraitCrop", "Crop portrait to 512×683", pos, (480, 420), group,
        [("image", "IMAGE", False), ("face_bboxes", "BOUNDING_BOX", True), ("subject_mask", "MASK", False),
         ("face_processing", "BOOLEAN", True), ("use_manual_crop", "BOOLEAN", True),
         ("manual_x", "FLOAT", True), ("manual_y", "FLOAT", True),
         ("manual_width", "FLOAT", True), ("manual_height", "FLOAT", True),
         ("zoom", "FLOAT", True), ("preserve_headwear", "BOOLEAN", True),
         ("output_width", "INT", True), ("output_height", "INT", True)],
        [("portrait", "IMAGE")], bounding_box_widgets + values, dict(zip(names, values)), "source",
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
    detector = _face_detect(g, (x, 240), group)
    mask_loader = _background_model(g, (x, 580), group)
    mask = _remove_background(g, "Generate subject silhouette for crop", (x, 720), group)
    crop = _adaptive_crop(g, (x + 540, 100), group)
    upscale_loader = _upscale_loader(g, (x + 540, 560), group)
    upscale = _upscale(g, (x + 540, 700), group)
    normalized = _image_scale(g, "Resize prepared portrait to 1024×1365", 1024, 1365, (x + 540, 840), group)
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


def _clip_encode(g: Graph, title: str, prompt: str, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "CLIPTextEncode", title, pos, (440, 260), group,
        [("clip", "CLIP", False), ("text", "STRING", True)], [("CONDITIONING", "CONDITIONING")],
        [prompt], {"text": prompt}, "restore",
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


def _adonis_sampler(g: Graph, title: str, pos: tuple[int, int], group: str, *, post: bool) -> Ref:
    values = [0.5 if post else 0.8, "exponential/res_2s", "simple", 8 if post else 9, -1, 1.0, 1.0, 42, "fixed", "standard", True]
    names = ("eta", "sampler_name", "scheduler", "steps", "steps_to_run", "cfg", "denoise", "seed", "control_after_generate", "sampler_mode", "bongmath")
    api_values = dict(zip(names, values))
    api_values.pop("control_after_generate")
    return g.node(
        "ClownsharKSampler_Beta", title, pos, (400, 1100), group,
        [("model", "MODEL", False), ("positive", "CONDITIONING", False), ("negative", "CONDITIONING", False),
         ("latent_image", "LATENT", False), ("options", "OPTIONS", False),
         ("eta", "FLOAT", True), ("sampler_name", "COMBO", True), ("scheduler", "COMBO", True),
         ("steps", "INT", True), ("steps_to_run", "INT", True), ("cfg", "FLOAT", True),
         ("denoise", "FLOAT", True), ("seed", "INT", True), ("control_after_generate", "COMBO", True),
         ("sampler_mode", "COMBO", True), ("bongmath", "BOOLEAN", True)],
        [("output", "LATENT"), ("denoised", "LATENT"), ("options", "OPTIONS")],
        values, api_values, "restore",
    )


def _vae_decode(
    g: Graph,
    pos: tuple[int, int],
    group: str,
    title: str = "Decode restored portrait",
    size: tuple[int, int] = (300, 100),
) -> Ref:
    return g.node(
        "VAEDecode", title, pos, size, group,
        [("samples", "LATENT", False), ("vae", "VAE", False)], [("IMAGE", "IMAGE")], [], {}, "restore",
    )


def _switch(g: Graph, title: str, enabled: bool, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "ComfySwitchNode", title, pos, (360, 160), group,
        [("switch", "BOOLEAN", True), ("on_false", "IMAGE", False), ("on_true", "IMAGE", False)],
        [("IMAGE", "IMAGE")], [enabled], {"switch": enabled}, "switch",
    )


def _restoration_cache(g: Graph, image: Ref, source_filename: tuple[Ref, int], pos: tuple[int, int], group: str) -> Ref:
    cache = g.node(
        "Hoi4RestorationCache", "Reuse restored portrait", pos, (440, 140), group,
        [("image", "IMAGE", False), ("source_filename", "STRING", False)], [("IMAGE", "IMAGE")], [], {}, "restore",
    )
    g.connect(image, 0, cache, "image")
    g.connect(source_filename[0], source_filename[1], cache, "source_filename")
    return cache


def _adonis_pipeline(
    g: Graph,
    image: Ref,
    model: dict[str, Ref],
    group: str,
    *,
    x: int = 4000,
    source_filename: tuple[Ref, int] | None = None,
) -> tuple[Ref, Ref]:
    scale = _scale_total(g, (x, 100), group)
    base_prompt = _clip_encode(g, "Adonis Base prompt", ADONIS_BASE_COMBINED_PROMPT, (x, 380), group)
    base_negative = _zero_conditioning(g, (x, 680), group)
    encoded = _vae_encode(g, (x, 800), group)
    empty = _empty_latent(g, (x, 940), group)

    base_positive_ref = _reference(g, "Base positive reference", (x + 480, 100), group)
    base_negative_ref = _reference(g, "Base negative reference", (x + 480, 240), group)
    options = _shark_options(g, (x + 480, 380), group)
    seed = _primitive_int(g, "Shared Adonis seed", 42, (x + 480, 600), group)
    steps = _primitive_int(g, "Steps per Adonis model", 9, (x + 480, 740), group)
    base = _adonis_sampler(g, "Restore details — Adonis Base", (x + 920, 100), group, post=False)

    post_prompt = _clip_encode(g, "Adonis Post prompt", ADONIS_POST_COMBINED_PROMPT, (x + 1360, 100), group)
    post_negative = _zero_conditioning(g, (x + 1360, 400), group)
    post_positive_ref = _reference(g, "Post positive reference", (x + 1360, 520), group)
    post_negative_ref = _reference(g, "Post negative reference", (x + 1360, 660), group)
    post = _adonis_sampler(g, "Finish details — Adonis Post", (x + 1840, 100), group, post=True)
    decoded = _vae_decode(g, (x + 1840, 1240), group, size=(260, 100))
    restored = _restoration_cache(g, decoded, source_filename, (x + 1360, 800), group) if source_filename else decoded
    enabled = _switch(g, "Use Adonis restoration", True, (x + 1840, 1380), group)

    g.connect(image, 0, scale, "image")
    g.connect(model["clip"], 0, base_prompt, "clip")
    g.connect(base_prompt, 0, base_negative, "conditioning")
    g.connect(scale, 0, encoded, "pixels")
    g.connect(model["vae"], 0, encoded, "vae")
    g.connect(base_prompt, 0, base_positive_ref, "conditioning")
    g.connect(encoded, 0, base_positive_ref, "latent")
    g.connect(base_negative, 0, base_negative_ref, "conditioning")
    g.connect(encoded, 0, base_negative_ref, "latent")
    g.connect(scale, 1, empty, "width")
    g.connect(scale, 2, empty, "height")

    g.connect(model["adonis_base"], 0, base, "model")
    g.connect(base_positive_ref, 0, base, "positive")
    g.connect(base_negative_ref, 0, base, "negative")
    g.connect(empty, 0, base, "latent_image")
    g.connect(options, 0, base, "options", api_target_input="options_group.options0")
    g.connect(steps, 0, base, "steps")
    g.connect(seed, 0, base, "seed")

    g.connect(model["clip"], 0, post_prompt, "clip")
    g.connect(post_prompt, 0, post_negative, "conditioning")
    g.connect(post_prompt, 0, post_positive_ref, "conditioning")
    g.connect(base, 0, post_positive_ref, "latent")
    g.connect(post_negative, 0, post_negative_ref, "conditioning")
    g.connect(base, 0, post_negative_ref, "latent")

    g.connect(model["adonis_post"], 0, post, "model")
    g.connect(post_positive_ref, 0, post, "positive")
    g.connect(post_negative_ref, 0, post, "negative")
    g.connect(empty, 0, post, "latent_image")
    g.connect(options, 0, post, "options", api_target_input="options_group.options0")
    g.connect(steps, 0, post, "steps")
    g.connect(seed, 0, post, "seed")
    g.connect(post, 0, decoded, "samples")
    g.connect(model["vae"], 0, decoded, "vae")
    g.connect(image, 0, enabled, "on_false")
    g.connect(restored, 0, enabled, "on_true")
    return enabled, scale


def _model_pipeline(g: Graph, group: str, *, x: int, y: int = 100, style: bool, adonis: bool, background: bool) -> dict[str, Ref]:
    if adonis:
        unet = _unet(g, (x, y), group)
        clip = _clip(g, (x, y + 180), group)
        vae = _vae(g, (x + 460, y + 180), group)
    else:
        unet = _unet(g, (x, y), group)
        clip = _clip(g, (x, y + 220), group)
        vae = _vae(g, (x, y + 440), group)
    result: dict[str, Ref] = {"unet": unet, "clip": clip, "vae": vae}
    if style:
        style_lora = _lora(g, "HOI4 portrait style LoRA", STYLE_LORA, (x + 460, y), group)
        g.connect(unet, 0, style_lora, "model")
        result["style"] = style_lora
    if adonis:
        base_column = 920 if style else 460
        post_column = 1380 if style else 920
        base = _lora(g, "Adonis Base LoRA", ADONIS_BASE, (x + base_column, y), group)
        post = _lora(g, "Adonis Post LoRA", ADONIS_POST, (x + post_column, y), group)
        g.connect(unet, 0, base, "model")
        g.connect(unet, 0, post, "model")
        result.update({"adonis_base": base, "adonis_post": post})
    if background:
        position = (x + 920, y + 180) if adonis else (x, y + 620)
        result["background_model"] = _background_model(g, position, group)
    return result


def _style_text_encode(g: Graph, title: str, text: str, pos: tuple[int, int], size: tuple[int, int], group: str) -> Ref:
    return g.node(
        "CLIPTextEncode", title, pos, size, group,
        [("clip", "CLIP", False), ("text", "STRING", True)], [("CONDITIONING", "CONDITIONING")],
        [text], {"text": text},
    )


def _flux_guidance(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    return g.node(
        "FluxGuidance", "Prompt guidance — 1", pos, (360, 100), group,
        [("conditioning", "CONDITIONING", False), ("guidance", "FLOAT", True)],
        [("CONDITIONING", "CONDITIONING")], [1.0], {"guidance": 1.0},
    )


def _portrait_latent(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    values = [1024, 1365, 1]
    return g.node(
        "EmptyFlux2LatentImage", "Empty 1024×1365 portrait latent", pos, (360, 180), group,
        [("width", "INT", True), ("height", "INT", True), ("batch_size", "INT", True)],
        [("LATENT", "LATENT")], values, dict(zip(("width", "height", "batch_size"), values)),
    )


def _style_inputs(
    g: Graph,
    model: dict[str, Ref],
    group: str,
    *,
    x: int,
    y: int,
    prompt: str,
    reference: Ref | None,
) -> tuple[Ref, Ref, Ref]:
    positive = _style_text_encode(g, "Portrait prompt", prompt, (x, y), (520, 300), group)
    negative = _style_text_encode(g, "Negative prompt", "", (x, y + 380), (520, 180), group)
    guidance = _flux_guidance(g, (x + 560, y), group)
    g.connect(model["clip"], 0, positive, "clip")
    g.connect(model["clip"], 0, negative, "clip")
    g.connect(positive, 0, guidance, "conditioning")

    if reference is None:
        latent = _portrait_latent(g, (x + 560, y + 180), group)
        return guidance, negative, latent

    latent = g.node(
        "VAEEncode", "Encode portrait reference", (x + 560, y + 180), (300, 100), group,
        [("pixels", "IMAGE", False), ("vae", "VAE", False)], [("LATENT", "LATENT")], [], {},
    )
    positive_ref = _reference(g, "Positive portrait reference", (x + 960, y), group)
    negative_ref = _reference(g, "Negative portrait reference", (x + 960, y + 180), group)
    g.connect(reference, 0, latent, "pixels")
    g.connect(model["vae"], 0, latent, "vae")
    g.connect(guidance, 0, positive_ref, "conditioning")
    g.connect(latent, 0, positive_ref, "latent")
    g.connect(negative, 0, negative_ref, "conditioning")
    g.connect(latent, 0, negative_ref, "latent")
    return positive_ref, negative_ref, latent


def _ksampler(
    g: Graph,
    title: str,
    model: dict[str, Ref],
    positive: Ref,
    negative: Ref,
    latent: Ref,
    seed: int,
    pos: tuple[int, int],
    group: str,
) -> Ref:
    values = [seed, "fixed", 4, 1.0, "euler", "simple", 1.0]
    sampler = g.node(
        "KSampler", title, pos, (560, 500), group,
        [("model", "MODEL", False), ("seed", "INT", True), ("steps", "INT", True),
         ("cfg", "FLOAT", True), ("sampler_name", "COMBO", True), ("scheduler", "COMBO", True),
         ("positive", "CONDITIONING", False), ("negative", "CONDITIONING", False),
         ("latent_image", "LATENT", False), ("denoise", "FLOAT", True)],
        [("LATENT", "LATENT")], values,
        {
            "seed": seed,
            "steps": 4,
            "cfg": 1.0,
            "sampler_name": "euler",
            "scheduler": "simple",
            "denoise": 1.0,
        },
    )
    g.connect(model["style"], 0, sampler, "model")
    g.connect(positive, 0, sampler, "positive")
    g.connect(negative, 0, sampler, "negative")
    g.connect(latent, 0, sampler, "latent_image")
    return sampler


def _decode_style(g: Graph, model: dict[str, Ref], samples: Ref, pos: tuple[int, int], group: str) -> Ref:
    decoded = _vae_decode(g, pos, group, "Decode portrait")
    g.connect(samples, 0, decoded, "samples")
    g.connect(model["vae"], 0, decoded, "vae")
    return decoded


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


def _output_filenames(
    g: Graph,
    title: str,
    source_filename: str,
    suffix: str,
    pos: tuple[int, int],
    group: str,
    filename_source: tuple[Ref, int] | None,
    size: tuple[int, int] = (420, 160),
) -> Ref:
    node = g.node(
        "Hoi4OutputFilename", title, pos, size, group,
        [("source_filename", "STRING", True), ("suffix", "STRING", True)],
        [("master_png", "STRING"), ("game_png", "STRING"), ("game_dds", "STRING")],
        [source_filename, suffix], {"source_filename": source_filename, "suffix": suffix}, "output",
    )
    if filename_source is not None:
        g.connect(filename_source[0], filename_source[1], node, "source_filename")
    return node


def _save_image(
    g: Graph,
    title: str,
    prefix: str,
    pos: tuple[int, int],
    group: str,
    prefix_source: tuple[Ref, int] | None = None,
) -> Ref:
    node = g.node(
        "SaveImage", title, pos, (420, 150), group,
        [("images", "IMAGE", False), ("filename_prefix", "STRING", True)], [("IMAGE", "IMAGE")],
        [prefix], {"filename_prefix": prefix}, "output",
    )
    if prefix_source is not None:
        g.connect(prefix_source[0], prefix_source[1], node, "filename_prefix")
    return node


def _save_dds(
    g: Graph,
    title: str,
    prefix: str,
    pos: tuple[int, int],
    group: str,
    prefix_source: tuple[Ref, int] | None = None,
) -> Ref:
    node = g.node(
        "Hoi4SaveDDS", title, pos, (420, 190), group,
        [("images", "IMAGE", False), ("filename_prefix", "STRING", True), ("format", "COMBO", True)], [("images", "IMAGE")],
        [prefix, "argb8888"], {"filename_prefix": prefix, "format": "argb8888"}, "output",
    )
    if prefix_source is not None:
        g.connect(prefix_source[0], prefix_source[1], node, "filename_prefix")
    return node


def _batch_input(g: Graph, pos: tuple[int, int], group: str) -> Ref:
    values = ["hoi4_portraits_batch", "*.png;*.jpg;*.jpeg;*.webp"]
    return g.node(
        "Hoi4BatchInput", "Batch portrait folder", pos, (680, 260), group,
        [("input_folder", "STRING", True), ("file_pattern", "STRING", True)],
        [("images", "IMAGE"), ("masks", "MASK"), ("filenames", "STRING")], values,
        {"input_folder": values[0], "file_pattern": values[1]}, "source",
    )


def build_source() -> tuple[dict[str, Any], dict[str, Any]]:
    g = Graph("hoi4_portrait_source", "HOI4 Portrait — source reference, three portraits")
    g.group("00 Setup", "#4b3327", "note")
    g.group("01 Prepare portrait", "#365b41", "source")
    g.group("02 Models", "#365b73", "model")
    g.group("03 Restore details", "#765b35", "restore")
    g.group("04 Create three portraits", "#654572", "sample")
    g.group("05 Save portraits", "#3d596f", "output")
    g.group("06 Compare portraits", "#334c61", "output")

    _setup_guide(g, (80, 100), "00 Setup")

    source = _load_image(
        g, "Choose a source portrait", "source_portrait.jpg", (860, 100), (680, 620),
        "01 Prepare portrait", keep_filename=True,
    )
    esrgan = _source_pipeline(g, source, "01 Prepare portrait", x=1620)

    model = _model_pipeline(g, "02 Models", x=860, y=1200, style=True, adonis=True, background=True)
    restored, _ = _adonis_pipeline(g, esrgan, model, "03 Restore details", x=2800, source_filename=(source, 2))

    positive, negative, latent = _style_inputs(
        g, model, "04 Create three portraits", x=5200, y=100, prompt=STYLE_PROMPT, reference=restored,
    )
    portraits: list[Ref] = []
    for index, (seed, y) in enumerate(((42, 100), (43, 680), (44, 1260)), start=1):
        sampler = _ksampler(
            g, f"Portrait {index} sampling", model, positive, negative, latent, seed,
            (6520, y), "04 Create three portraits",
        )
        portraits.append(_decode_style(g, model, sampler, (7120, y), "04 Create three portraits"))

    first_pair = _image_batch(g, "Join portraits 1 and 2", portraits[0], portraits[1], (7460, 100), "04 Create three portraits")
    all_portraits = _image_batch(g, "Add portrait 3", first_pair, portraits[2], (7460, 260), "04 Create three portraits")
    background = _load_image(g, "Choose a replacement background", "hoi4_leader_portrait_background.png", (7460, 440), (600, 560), "04 Create three portraits")
    replace = _background_replace(g, "Use replacement background", (7460, 1080), "04 Create three portraits")
    g.connect(all_portraits, 0, replace, "image")
    g.connect(model["background_model"], 0, replace, "bg_removal_model")
    g.connect(background, 0, replace, "background")

    finals: list[Ref] = []
    masters: list[Ref] = []
    for index, y in enumerate((760, 1020, 1280), start=1):
        portrait = _image_from_batch(g, f"Take portrait {index}", replace, index - 1, (8100, 100 + (index - 1) * 220), "04 Create three portraits")
        master = _image_scale(g, f"Portrait {index} master — 1024×1365", 1024, 1365, (8100, y), "04 Create three portraits")
        game = _image_scale(g, f"Portrait {index} game — 156×210", 156, 210, (8540, y), "04 Create three portraits")
        g.connect(portrait, 0, master, "image")
        g.connect(master, 0, game, "image")
        masters.append(master)
        finals.append(game)

    for index, (master, game) in enumerate(zip(masters, finals), start=1):
        oy = 100 + (index - 1) * 480
        names = _output_filenames(
            g, f"Keep source name — portrait {index}", "source_portrait.jpg", f"_{index}",
            (9100, oy), "05 Save portraits", (source, 2),
        )
        save_master = _save_image(
            g, f"Save portrait {index} master PNG", f"hoi4_portraits/1024x1365/source_portrait_{index}",
            (9100, oy + 200), "05 Save portraits", (names, 0),
        )
        save_game = _save_image(
            g, f"Save portrait {index} game PNG", f"hoi4_portraits/156x210/source_portrait_{index}",
            (9560, oy), "05 Save portraits", (names, 1),
        )
        save_dds = _save_dds(
            g, f"Save portrait {index} DDS", f"hoi4_portraits/156x210/dds/source_portrait_{index}",
            (9560, oy + 200), "05 Save portraits", (names, 2),
        )
        g.connect(master, 0, save_master, "images")
        g.connect(game, 0, save_game, "images")
        g.connect(game, 0, save_dds, "images")
    comparison = [
        ("Prepared portrait", esrgan),
        ("Restored portrait", restored),
        ("Portrait 1 — full resolution", masters[0]),
        ("Portrait 2 — full resolution", masters[1]),
        ("Portrait 3 — full resolution", masters[2]),
    ]
    for index, (title, ref) in enumerate(comparison):
        preview = _preview(g, title, (2800 + index * 640, 1940), "06 Compare portraits")
        g.connect(ref, 0, preview, "images")
    g.apply_layout(SOURCE_LAYOUT)
    return g.serialize(style_lora=STYLE_LORA)


def build_text() -> tuple[dict[str, Any], dict[str, Any]]:
    g = Graph("hoi4_portrait_text_to_image", "HOI4 Portrait — text to image")
    g.group("00 Setup", "#4b3327", "note")
    g.group("01 Models", "#365b73", "model")
    g.group("02 Create portrait", "#654572", "sample")
    g.group("03 Finish and save", "#3d596f", "output")
    _setup_guide(g, (80, 100), "00 Setup")
    model = _model_pipeline(g, "01 Models", x=860, style=True, adonis=False, background=True)
    positive, negative, latent = _style_inputs(
        g, model, "02 Create portrait", x=1880, y=100, prompt=TEXT_PROMPT, reference=None,
    )
    sampler = _ksampler(g, "Portrait sampling", model, positive, negative, latent, 42, (2840, 100), "02 Create portrait")
    portrait = _decode_style(g, model, sampler, (3440, 100), "02 Create portrait")
    names = _output_filenames(
        g, "Name generated portrait files", "text_to_image.png", "", (3440, 280),
        "02 Create portrait", None, (300, 160),
    )

    replace = _background_replace(g, "Use replacement background", (3900, 100), "03 Finish and save")
    master = _image_scale(g, "Master portrait — 1024×1365", 1024, 1365, (3900, 440), "03 Finish and save")
    game = _image_scale(g, "Game portrait — 156×210", 156, 210, (3900, 700), "03 Finish and save")
    background = _load_image(g, "Choose a replacement background", "hoi4_leader_portrait_background.png", (4440, 100), (600, 560), "03 Finish and save")
    g.connect(portrait, 0, replace, "image")
    g.connect(model["background_model"], 0, replace, "bg_removal_model")
    g.connect(background, 0, replace, "background")
    g.connect(replace, 0, master, "image")
    g.connect(master, 0, game, "image")
    save_master = _save_image(g, "Save master PNG", "hoi4_portraits/1024x1365/text_to_image", (3900, 960), "03 Finish and save", (names, 0))
    save_game = _save_image(g, "Save game PNG", "hoi4_portraits/156x210/text_to_image", (3900, 1200), "03 Finish and save", (names, 1))
    save_dds = _save_dds(g, "Save game DDS", "hoi4_portraits/156x210/dds/text_to_image", (3900, 1440), "03 Finish and save", (names, 2))
    preview = _preview(g, "Full-resolution portrait", (4440, 740), "03 Finish and save")
    g.connect(master, 0, save_master, "images")
    g.connect(game, 0, save_game, "images")
    g.connect(game, 0, save_dds, "images")
    g.connect(master, 0, preview, "images")
    return g.serialize(style_lora=STYLE_LORA)


def build_processing() -> tuple[dict[str, Any], dict[str, Any]]:
    g = Graph("hoi4_portrait_processing_only", "HOI4 Portrait — processing and restoration only")
    g.group("00 Setup", "#4b3327", "note")
    g.group("01 Prepare portrait", "#365b41", "source")
    g.group("02 Models", "#365b73", "model")
    g.group("03 Restore details", "#765b35", "restore")
    g.group("04 Finish and save", "#3d596f", "output")
    _setup_guide(g, (80, 100), "00 Setup")
    source = _load_image(
        g, "Choose a source portrait", "source_portrait.jpg", (860, 100), (680, 620),
        "01 Prepare portrait", keep_filename=True,
    )
    esrgan = _source_pipeline(g, source, "01 Prepare portrait", x=1620)
    model = _model_pipeline(g, "02 Models", x=860, y=1200, style=False, adonis=True, background=False)
    restored, _ = _adonis_pipeline(g, esrgan, model, "03 Restore details", x=2800, source_filename=(source, 2))
    master = _image_scale(g, "Restored master — 1024×1365", 1024, 1365, (5200, 100), "04 Finish and save")
    game = _image_scale(g, "Game portrait — 156×210", 156, 210, (5640, 100), "04 Finish and save")
    g.connect(restored, 0, master, "image")
    g.connect(master, 0, game, "image")
    names = _output_filenames(
        g, "Keep source image name", "source_portrait.jpg", "", (5620, 340),
        "04 Finish and save", (source, 2),
    )
    save_master = _save_image(g, "Save restored master PNG", "hoi4_portraits/1024x1365/source_portrait", (6080, 100), "04 Finish and save", (names, 0))
    save_game = _save_image(g, "Save game PNG", "hoi4_portraits/156x210/source_portrait", (6080, 340), "04 Finish and save", (names, 1))
    save_dds = _save_dds(g, "Save game DDS", "hoi4_portraits/156x210/dds/source_portrait", (6080, 580), "04 Finish and save", (names, 2))
    g.connect(master, 0, save_master, "images")
    g.connect(game, 0, save_game, "images")
    g.connect(game, 0, save_dds, "images")
    for index, (title, ref) in enumerate((("Prepared portrait", esrgan), ("Restored portrait", restored), ("Full-resolution portrait", master))):
        preview = _preview(g, title, (5200 + index * 640, 880), "04 Finish and save")
        g.connect(ref, 0, preview, "images")
    return g.serialize(style_lora=None)


def build_batch() -> tuple[dict[str, Any], dict[str, Any]]:
    g = Graph("hoi4_portrait_batch", "HOI4 Portrait — batch input and output")
    g.group("00 Setup", "#4b3327", "note")
    g.group("01 Prepare portraits", "#365b41", "source")
    g.group("02 Models", "#365b73", "model")
    g.group("03 Restore details", "#765b35", "restore")
    g.group("04 Create portraits", "#654572", "sample")
    g.group("05 Save portraits", "#3d596f", "output")
    _setup_guide(g, (80, 100), "00 Setup")
    batch = _batch_input(g, (860, 100), "01 Prepare portraits")
    esrgan = _source_pipeline(g, batch, "01 Prepare portraits", x=1620)
    model = _model_pipeline(g, "02 Models", x=860, y=1200, style=True, adonis=True, background=False)
    restored, _ = _adonis_pipeline(g, esrgan, model, "03 Restore details", x=2800, source_filename=(batch, 2))
    positive, negative, latent = _style_inputs(
        g, model, "04 Create portraits", x=5200, y=100, prompt=STYLE_PROMPT, reference=restored,
    )
    sampler = _ksampler(g, "Portrait sampling", model, positive, negative, latent, 42, (6520, 100), "04 Create portraits")
    portrait = _decode_style(g, model, sampler, (7120, 100), "04 Create portraits")
    master = _image_scale(g, "Master portrait — 1024×1365", 1024, 1365, (7460, 100), "05 Save portraits")
    game = _image_scale(g, "Game portrait — 156×210", 156, 210, (7900, 100), "05 Save portraits")
    g.connect(portrait, 0, master, "image")
    g.connect(master, 0, game, "image")
    save_master = _save_image(g, "Save every master PNG", "hoi4_portraits/1024x1365/batch", (7460, 360), "05 Save portraits")
    save_game = _save_image(g, "Save every game PNG", "hoi4_portraits/156x210/batch", (7920, 360), "05 Save portraits")
    save_dds = _save_dds(g, "Save every game DDS", "hoi4_portraits/156x210/dds/batch", (7920, 600), "05 Save portraits")
    names = _output_filenames(
        g, "Keep each source image name", "portrait.png", "", (7460, 600),
        "05 Save portraits", (batch, 2),
    )
    g.connect(names, 0, save_master, "filename_prefix")
    g.connect(names, 1, save_game, "filename_prefix")
    g.connect(names, 2, save_dds, "filename_prefix")
    g.connect(master, 0, save_master, "images")
    g.connect(game, 0, save_game, "images")
    g.connect(game, 0, save_dds, "images")
    for index, (title, ref) in enumerate((("Prepared portrait", esrgan), ("Restored portrait", restored), ("Full-resolution portrait", master))):
        preview = _preview(g, title, (6520 + index * 640, 900), "04 Create portraits", None)
        g.connect(ref, 0, preview, "images")
    g.apply_layout(BATCH_LAYOUT)
    return g.serialize(style_lora=STYLE_LORA)


BUILDERS = {
    "hoi4_portrait_source": build_source,
    "hoi4_portrait_text_to_image": build_text,
    "hoi4_portrait_batch": build_batch,
    "hoi4_portrait_processing_only": build_processing,
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
