#!/usr/bin/env python3
"""Build the public ComfyUI workflows from one deterministic graph source.

The generated ``*.json`` files are editor/save format; the matching
``*.api.json`` files are ready for ``/prompt`` or the Comfy Cloud workflow API.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / "workflows"

BASE_MODEL = "flux-2-klein-9b.safetensors"
FP8_MODEL = "flux-2-klein-9b-fp8.safetensors"
GGUF_MODEL = "flux-2-klein-9b-Q5_K_M.gguf"
TEXT_ENCODER = "qwen_3_8b_fp8mixed.safetensors"
VAE_MODEL = "flux2-vae.safetensors"
STYLE_LORA = "hoi4_portrait_flux2_klein_9b_lora_000002500.safetensors"
STYLE_LORA_CHECKPOINTS = (STYLE_LORA,)
RESTORATION_LOKR = "adonis_base.safetensors"
RESTORATION_POST_LOKR = "adonis_post.safetensors"
STYLE_LORA_STRENGTH = 1.0
SOURCE_STYLE_DENOISE = 1.0
DEFAULT_STEPS = 4
DEFAULT_CFG = 1.0
DEFAULT_GUIDANCE = 1.0
CANVAS_WIDTH = 1024
CANVAS_HEIGHT = 1365
GAME_WIDTH = 156
GAME_HEIGHT = 210
WORKFLOW_SCHEMA_VERSION = "3.0.0"
# Keep a visible breathing space between cards in the editor.  ComfyUI can
# render widget-heavy nodes taller than the compact dimensions stored in a
# workflow, so the editor layout uses a larger guard than the JSON validator's
# old 24 px minimum.
UI_LAYOUT_PADDING = 150
GROUP_LAYOUT_GAP = 140
# Preview cards are deliberately larger than the default ComfyUI card.  The
# editor uses the serialized node size as the initial render size; keeping the
# same dimensions in every stage makes the three candidate lanes line up
# instead of looking like a staircase of different cards.
STAGE_PREVIEW_SIZE = (560, 700)
FINAL_PREVIEW_SIZE = (620, 760)
# Source and ESRGAN cards are deliberately smaller than the candidate cards so
# the whole preparation stage stays compact; they still render clearly.
SOURCE_PREVIEW_SIZE = (440, 540)
# The game-size previews are upscaled purely for display so the 156x210
# portrait can be compared clearly.  The saved PNG/DDS stay at exact 156x210.
PREVIEW_BOOST_WIDTH = 624
PREVIEW_BOOST_HEIGHT = 840
SOURCE_CANDIDATE_COUNT = 3
SOURCE_STYLE_SEEDS = (42, 43, 44)
SOURCE_CANDIDATE_SAMPLING = (("euler", DEFAULT_STEPS),) * SOURCE_CANDIDATE_COUNT
# The preview card is taller than the sampler controls.  Leave a full card and
# a safety gutter between candidate lanes so ComfyUI's widget auto-sizing
# cannot make one lane touch the next one.
SOURCE_CANDIDATE_ROW_GAP = 1500
ESRGAN_MODEL = "RealESRGAN_x2plus.pth"
BACKGROUND_MODEL = "birefnet.safetensors"
FACE_DETECTION_MODEL = "mediapipe_face_fp32.safetensors"
YUNET_MODEL = "face_detection_yunet_2023mar.onnx"

MODEL_URLS = {
    BASE_MODEL: "https://huggingface.co/black-forest-labs/FLUX.2-klein-9B/resolve/92196c8e11f7b6cf2b7493e037d8c5345c559216/flux-2-klein-9b.safetensors",
    FP8_MODEL: "https://huggingface.co/black-forest-labs/FLUX.2-klein-9b-fp8/resolve/902d9d510b51533e07729f19211414a3648b77d2/flux-2-klein-9b-fp8.safetensors",
    GGUF_MODEL: "https://huggingface.co/drends/FLUX.2-klein-9B-GGUF/resolve/9d468c2918205cc55ebd7a09802dc64c225fb2a6/flux-2-klein-9b-Q5_K_M.gguf",
    TEXT_ENCODER: "https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/23fbc8aa8b621f29f2249cd1bd9c47e5d0eebd83/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors",
    VAE_MODEL: "https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/23fbc8aa8b621f29f2249cd1bd9c47e5d0eebd83/split_files/vae/flux2-vae.safetensors",
    RESTORATION_LOKR: "https://huggingface.co/n8te0/adonis_flux2klein/resolve/515ecf66717d14309a055811b3d478cdfa59bbda/adonis_base.safetensors",
    RESTORATION_POST_LOKR: "https://huggingface.co/n8te0/adonis_flux2klein/resolve/515ecf66717d14309a055811b3d478cdfa59bbda/adonis_post.safetensors",
    ESRGAN_MODEL: "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
    BACKGROUND_MODEL: "https://huggingface.co/Comfy-Org/BiRefNet/resolve/8fdc9d315889de96cc0c6269eeecd333e2727889/background_removal/birefnet.safetensors",
    FACE_DETECTION_MODEL: "https://huggingface.co/Comfy-Org/mediapipe/resolve/b98d050e8bf406f14f063bdba697e5b5391bbbf5/detection/mediapipe_face_fp32.safetensors",
    YUNET_MODEL: "https://media.githubusercontent.com/media/opencv/opencv_zoo/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
}
for checkpoint in STYLE_LORA_CHECKPOINTS:
    MODEL_URLS[checkpoint] = (
        "https://huggingface.co/Hoops-McCann/hoi4-portraits-flux2-klein-9b-lora/"
        f"resolve/001ab9fe6a795124432287125fb28c2b99b74f57/{checkpoint}"
    )

RESTORATION_PROMPT = (
    "uhdmanscale, fully reconstruct this entire image from cellphone quality to professional high resolution color raw quality. "
    "Remove halftone dot pattern. Apply descreen filter. Eliminate periodic grid noise. Eliminate repeating noise patterns and artifacts, "
    "remove uniform diagonal line texture patterns. Reconstruct low resolution high ISO noise areas with high resolution low ISO noise textures. "
    "Apply full detail reconstruction to all areas: background, environment, surfaces, objects, clothing, and foreground elements — render everything sharp, textured, and high fidelity. "
    "Subject identity is locked: preserve exact facial geometry and body geometry, eye shape and color, nose and mouth shape, and expression. "
    "On skin areas, remove color blotch artifacts, normalize tone uniformity, preserve natural pore and texture detail. "
    "On hair and body hair areas, separate smeared color artifacts, restore strand separation and texture. "
    "Outside the subject's face, freely reconstruct all texture and sharpness with no restrictions. "
    "Deblur and focus correction pass. Infer and reconstruct underlying detail from soft source: sharpen edge definition, recover eye detail, lip definition, and skin texture from motion blur. "
    "Output as professional high resolution color camera RAW image."
)
RESTORATION_BASE_PROMPT = RESTORATION_PROMPT + (
    " fully reconstruct this entire image from cellphone quality to professional high resolution color raw quality."
)
RESTORATION_POST_PROMPT = RESTORATION_PROMPT + (
    " clean natural skin, hair and body texture, no jpeg artifacts, no checkerboard pattern, male portrait."
)
RESTORATION_NEGATIVE = ""
STYLE_PROMPT = "make this portrait hoi4_portrait style"
STYLE_NEGATIVE = ""
TEXT_PROMPT = (
    "hoi4_portrait style, an Irish middle-aged man with neatly combed dark hair, "
    "wearing a plain civilian jacket."
)

SETUP_GUIDE_NOTE = (
    "📦 HOI4 PORTRAIT WORKFLOW — MODEL SETUP\n"
    "\n"
    "The bundled installer places every file below for you. If you install "
    "manually, the workflow looks for these exact filenames:\n"
    "\n"
    "🖼️  FLUX.2 Klein 9B\n"
    "    ComfyUI/models/diffusion_models/\n"
    "    ├── flux-2-klein-9b.safetensors        · full BF16, 18.2 GB (24+ GB VRAM)\n"
    "    ├── flux-2-klein-9b-fp8.safetensors    · FP8, 9.4 GB (16–20 GB VRAM)\n"
    "    └── flux-2-klein-9b-Q5_K_M.gguf        · GGUF, 7.0 GB (8–16 GB VRAM)\n"
    "\n"
    "🧠  Qwen 3 8B text encoder\n"
    "    ComfyUI/models/text_encoders/qwen_3_8b_fp8mixed.safetensors\n"
    "\n"
    "🎨  FLUX.2 VAE\n"
    "    ComfyUI/models/vae/flux2-vae.safetensors\n"
    "\n"
    "🎭  HOI4 style LoRA — step 2500 (the tuned checkpoint)\n"
    "    ComfyUI/models/loras/hoi4_portrait_flux2_klein_9b_lora_000002500.safetensors\n"
    "\n"
    "✨  Adonis restoration LoKrs (optional pass)\n"
    "    ComfyUI/models/loras/adonis_base.safetensors\n"
    "    ComfyUI/models/loras/adonis_post.safetensors\n"
    "\n"
    "🔍  Support models\n"
    "    ComfyUI/models/upscale_models/RealESRGAN_x2plus.pth\n"
    "    ComfyUI/models/background_removal/birefnet.safetensors\n"
    "    ComfyUI/models/detection/face_detection_yunet_2023mar.onnx\n"
    "\n"
    "The GGUF and FP8 files are smaller variants of the same model; "
    "pick the one that fits your VRAM (the installer suggests one for you)."
)

SAMPLING_NOTE = (
    "🎛️  SAMPLER CONTROLS — WHAT THEY DO\n"
    "\n"
    "Every generation node is one advanced sampler card. The tuned defaults "
    "for this workflow are: CFG 1.0, guidance 1.0, 4 steps, Euler sampler, "
    "simple scheduler, denoise 1.0.\n"
    "\n"
    "• Steps — how many denoising passes run. More steps = more detail but "
    "slower generation. The style LoRA is trained for 4 steps; going much "
    "higher mostly slows things down.\n"
    "• CFG — how strongly the model follows your prompt. Higher values apply "
    "the HOI4 style more sharply (try 2–3 if you want a stronger look).\n"
    "• Guidance — FLUX.2's own prompt-following scale. Klein works best at "
    "low values (default 1.0).\n"
    "• Seed — the random source. Change it (or hit randomize) for a different "
    "portrait from the same prompt.\n"
    "• Sampling algorithm — the sampler itself. Euler is the tuned default; "
    "advanced users can switch (e.g. euler_ancestral, dpmpp_2m).\n"
    "• Scheduler — how denoise strength is scheduled across steps. Simple is "
    "the FLUX.2 default.\n"
    "\n"
    "Sampling is LIVE: watch the portrait being constructed in the preview "
    "cards while it runs."
)

RESTORATION_NOTE = (
    "✨ WHY THE RESTORATION PASS IS WORTH KEEPING\n"
    "\n"
    "Old photos are often blurry, grainy, or sepia. RealESRGAN upscales them "
    "first, then the optional Adonis pass (Base → Post) rebuilds skin, hair "
    "and eye detail and restores natural colour.\n"
    "\n"
    "The benefit: the HOI4 style LoRA no longer has to guess colours or "
    "invent facial details — it can focus purely on the painted HOI4 look, "
    "which gives cleaner, more consistent portraits.\n"
    "\n"
    "The red toggle is ON by default. Turn it OFF if you prefer the direct "
    "ESRGAN result (for example a very clean modern photo that needs no "
    "repair)."
)

PROMPTING_NOTE = (
    "✍️  WHAT TO PROMPT\n"
    "\n"
    "Keep the default prompt exactly as-is:\n"
    "    make this portrait hoi4_portrait style\n"
    "\n"
    "That short phrase already triggers the trained HOI4 look. You can safely "
    "append a short description when the model needs help:\n"
    "\n"
    "• Ethnicity or skin colour — if the skin tone comes out wrong.\n"
    "• Civilian / military / clerical clothing — if it helps the outfit.\n"
    "• Age, hair, or facial hair — if the portrait drifts.\n"
    "\n"
    "Example:\n"
    "    make this portrait hoi4_portrait style, a middle-aged Irish man "
    "with dark hair, wearing a military uniform\n"
    "\n"
    "Don't describe the game, background, lighting, or rendering — the LoRA "
    "handles those."
)

BATCH_NOTE = (
    "🖼️  BATCH MODE\n"
    "\n"
    "Drop any number of source photos into:\n"
    "    ComfyUI/input/hoi4_portraits_batch/\n"
    "\n"
    "then queue once. Every image is processed one by one through the same "
    "crop, ESRGAN, optional restoration, and the single HOI4 sampler. Results "
    "are saved to:\n"
    "\n"
    "    ComfyUI/output/1024x1365/     · full-res masters\n"
    "    ComfyUI/output/156x210/       · game-size PNGs\n"
    "    ComfyUI/output/156x210/dds/   · HOI4-ready DDS files\n"
    "\n"
    "The DDS files are 156x210 DXT5 with no mipmaps — drop them straight "
    "into your mod's gfx/portraits folder."
)


@dataclass(frozen=True)
class Link:
    node_id: int
    slot: int = 0


@dataclass
class Node:
    node_id: int
    class_type: str
    title: str
    group: str
    pos: tuple[int, int]
    size: tuple[int, int]
    inputs: dict[str, Any]
    input_types: dict[str, str]
    outputs: list[str]
    output_types: list[str]
    widgets: list[Any] = field(default_factory=list)
    models: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class Group:
    title: str
    bounding: tuple[int, int, int, int]
    color: str


@dataclass
class Graph:
    workflow_id: str
    description: str
    kind: str
    nodes: list[Node]
    groups: list[Group]
    metadata: dict[str, Any]


def _model(name: str, directory: str) -> list[dict[str, str]]:
    return [{"name": name, "url": MODEL_URLS[name], "directory": directory}]


def _note(
    node_id: int,
    title: str,
    text: str,
    group: str,
    pos: tuple[int, int],
    *,
    size: tuple[int, int] = (760, 520),
) -> Node:
    """Create a frontend-only explanatory Note card.

    The ComfyUI editor renders ``Note`` nodes client-side, so they never enter
    the API graph and are skipped by ``_api_json``.
    """
    return _node(
        node_id,
        "Note",
        title,
        group,
        pos,
        size=size,
        widgets=[text],
    )


def _node(
    node_id: int,
    class_type: str,
    title: str,
    group: str,
    pos: tuple[int, int],
    *,
    size: tuple[int, int] = (300, 100),
    inputs: dict[str, Any] | None = None,
    input_types: dict[str, str] | None = None,
    outputs: list[str] | None = None,
    output_types: list[str] | None = None,
    widgets: list[Any] | None = None,
    models: list[dict[str, str]] | None = None,
) -> Node:
    return Node(
        node_id=node_id,
        class_type=class_type,
        title=title,
        group=group,
        pos=pos,
        size=size,
        inputs=inputs or {},
        input_types=input_types or {},
        outputs=outputs or [],
        output_types=output_types or [],
        widgets=widgets or [],
        models=models or [],
    )


def _model_nodes(*, include_lora: bool = True, include_restoration_lokr: bool = True) -> list[Node]:
    group = "02 FLUX.2 Klein 9B models"
    nodes = [
        _node(
            1,
            "UNETLoader",
            "Load FLUX.2 Klein 9B",
            group,
            (1120, 120),
            inputs={"unet_name": BASE_MODEL, "weight_dtype": "default"},
            input_types={"unet_name": "COMBO", "weight_dtype": "COMBO"},
            outputs=["MODEL"],
            output_types=["MODEL"],
            widgets=[BASE_MODEL, "default"],
            models=_model(BASE_MODEL, "diffusion_models"),
        ),
        _node(
            2,
            "CLIPLoader",
            "Load Qwen 3 8B text encoder",
            group,
            (1120, 280),
            inputs={"clip_name": TEXT_ENCODER, "type": "flux2", "device": "default"},
            input_types={"clip_name": "COMBO", "type": "COMBO", "device": "COMBO"},
            outputs=["CLIP"],
            output_types=["CLIP"],
            widgets=[TEXT_ENCODER, "flux2", "default"],
            models=_model(TEXT_ENCODER, "text_encoders"),
        ),
        _node(
            3,
            "VAELoader",
            "Load FLUX.2 VAE",
            group,
            (1120, 460),
            inputs={"vae_name": VAE_MODEL},
            input_types={"vae_name": "COMBO"},
            outputs=["VAE"],
            output_types=["VAE"],
            widgets=[VAE_MODEL],
            models=_model(VAE_MODEL, "vae"),
        ),
    ]
    if include_lora:
        nodes.append(
            _node(
                4,
                "LoraLoaderModelOnly",
                "Apply HOI4 LoRA — strength editable here",
                group,
                (1120, 640),
                size=(300, 130),
                inputs={"model": Link(1), "lora_name": STYLE_LORA, "strength_model": STYLE_LORA_STRENGTH},
                input_types={"model": "MODEL", "lora_name": "COMBO", "strength_model": "FLOAT"},
                outputs=["MODEL"],
                output_types=["MODEL"],
                widgets=[STYLE_LORA, STYLE_LORA_STRENGTH],
                models=_model(STYLE_LORA, "loras"),
            )
        )
    if include_restoration_lokr:
        nodes.append(
            _node(
                191,
                "LoraLoaderModelOnly",
                "Apply Adonis restoration LoKr — strength editable here",
                group,
                (1120, 820 if include_lora else 640),
                size=(300, 130),
                inputs={"model": Link(1), "lora_name": RESTORATION_LOKR, "strength_model": 1.0},
                input_types={"model": "MODEL", "lora_name": "COMBO", "strength_model": "FLOAT"},
                outputs=["MODEL"],
                output_types=["MODEL"],
                widgets=[RESTORATION_LOKR, 1.0],
                models=_model(RESTORATION_LOKR, "loras"),
            )
        )
        nodes.append(
            _node(
                192,
                "LoraLoaderModelOnly",
                "Load Adonis Post restoration LoKr",
                group,
                (1120, 1030 if include_lora else 850),
                size=(300, 130),
                inputs={"model": Link(1), "lora_name": RESTORATION_POST_LOKR, "strength_model": 1.0},
                input_types={"model": "MODEL", "lora_name": "COMBO", "strength_model": "FLOAT"},
                outputs=["MODEL"],
                output_types=["MODEL"],
                widgets=[RESTORATION_POST_LOKR, 1.0],
                models=_model(RESTORATION_POST_LOKR, "loras"),
            )
        )
    return nodes


def _source_nodes(*, include_processed_preview: bool = True) -> list[Node]:
    group = "01 Source and ESRGAN"
    nodes = [
        _node(
            5,
            "LoadImage",
            "Load source portrait — upload or pick your photo here",
            group,
            (100, 120),
            size=(460, 420),
            inputs={"image": "source_portrait.jpg"},
            input_types={"image": "COMBO"},
            outputs=["IMAGE", "MASK"],
            output_types=["IMAGE", "MASK"],
            widgets=["source_portrait.jpg", "image"],
        ),
        _node(
            9,
            "ImageScaleToMaxDimension",
            "Normalize source for face detection",
            group,
            (520, 120),
            size=(360, 120),
            inputs={"image": Link(5), "upscale_method": "lanczos", "largest_size": 1024},
            input_types={"image": "IMAGE", "upscale_method": "COMBO", "largest_size": "INT"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=["lanczos", 1024],
        ),
        _node(
            12,
            "LoadMediaPipeFaceLandmarker",
            "Load MediaPipe face detector",
            group,
            (100, 500),
            inputs={"model_name": FACE_DETECTION_MODEL},
            input_types={"model_name": "COMBO"},
            outputs=["FACE_DETECTION_MODEL"],
            output_types=["FACE_DETECTION_MODEL"],
            widgets=[FACE_DETECTION_MODEL],
            models=_model(FACE_DETECTION_MODEL, "detection"),
        ),
        _node(
            13,
            "MediaPipeFaceLandmarker",
            "Find the portrait subject",
            group,
            (520, 350),
            size=(360, 220),
            inputs={
                "face_detection_model": Link(12),
                "image": Link(9),
                "detector_variant": "both",
                "num_faces": 1,
                "min_confidence": 0.3,
                "missing_frame_fallback": "empty",
            },
            input_types={
                "face_detection_model": "FACE_DETECTION_MODEL",
                "image": "IMAGE",
                "detector_variant": "COMBO",
                "num_faces": "INT",
                "min_confidence": "FLOAT",
                "missing_frame_fallback": "COMBO",
            },
            outputs=["face_landmarks", "bboxes"],
            output_types=["FACE_LANDMARKS", "BOUNDING_BOX"],
            widgets=["both", 1, 0.3, "empty"],
        ),
        _node(
            11,
            "AdaptivePortraitCrop",
            "Face zoom 0.90 — preserve headwear: true",
            group,
            (520, 650),
            size=(360, 230),
            inputs={
                "image": Link(9),
                "face_bboxes": Link(13, 1),
                "subject_mask": Link(156),
                "zoom": 0.90,
                "preserve_headwear": True,
            },
            input_types={
                "image": "IMAGE",
                "face_bboxes": "BOUNDING_BOX",
                "subject_mask": "MASK",
                "zoom": "FLOAT",
                "preserve_headwear": "BOOLEAN",
            },
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=[0.90, True],
            models=_model(YUNET_MODEL, "detection"),
        ),
        _node(
            155,
            "LoadBackgroundRemovalModel",
            "Load subject silhouette model",
            group,
            (100, 680),
            size=(320, 100),
            inputs={"bg_removal_name": BACKGROUND_MODEL},
            input_types={"bg_removal_name": "COMBO"},
            outputs=["BACKGROUND_REMOVAL"],
            output_types=["BACKGROUND_REMOVAL"],
            widgets=[BACKGROUND_MODEL],
            models=_model(BACKGROUND_MODEL, "background_removal"),
        ),
        _node(
            156,
            "RemoveBackground",
            "Measure the complete head and headwear silhouette",
            group,
            (100, 840),
            size=(320, 100),
            inputs={"bg_removal_model": Link(155), "image": Link(9)},
            input_types={"bg_removal_model": "BACKGROUND_REMOVAL", "image": "IMAGE"},
            outputs=["MASK"],
            output_types=["MASK"],
        ),
        _node(
            15,
            "PrimitiveBoundingBox",
            "Manual crop box for difficult sources",
            group,
            (100, 1020),
            size=(320, 190),
            inputs={"x": 128, "y": 0, "width": 768, "height": 1024},
            input_types={"x": "INT", "y": "INT", "width": "INT", "height": "INT"},
            outputs=["BOUNDING_BOX"],
            output_types=["BOUNDING_BOX"],
            widgets=[128, 0, 768, 1024],
        ),
        _node(
            16,
            "CropByBBoxes",
            "Apply manual head-and-shoulders crop",
            group,
            (520, 960),
            size=(360, 180),
            inputs={
                "image": Link(9),
                "bboxes": Link(15),
                "output_width": CANVAS_WIDTH,
                "output_height": CANVAS_HEIGHT,
                "padding": 0,
                "keep_aspect": "stretch",
            },
            input_types={
                "image": "IMAGE",
                "bboxes": "BOUNDING_BOX",
                "output_width": "INT",
                "output_height": "INT",
                "padding": "INT",
                "keep_aspect": "COMBO",
            },
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=[CANVAS_WIDTH, CANVAS_HEIGHT, 0, "stretch"],
        ),
        _node(
            18,
            "ComfySwitchNode",
            "Manual crop override — off uses automatic crop",
            group,
            (520, 1200),
            size=(360, 150),
            inputs={"switch": False, "on_false": Link(11), "on_true": Link(16)},
            input_types={"switch": "BOOLEAN", "on_false": "IMAGE", "on_true": "IMAGE"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=[False],
        ),
        _node(
            17,
            "ComfySwitchNode",
            "Toggle face processing (on: face crop; off: keep full composition)",
            group,
            (520, 1430),
            size=(360, 100),
            inputs={"switch": True, "on_false": Link(9), "on_true": Link(18)},
            input_types={"switch": "BOOLEAN", "on_false": "IMAGE", "on_true": "IMAGE"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=[True],
        ),
        _node(
            6,
            "UpscaleModelLoader",
            "Load RealESRGAN x2",
            group,
            (100, 1410),
            inputs={"model_name": ESRGAN_MODEL},
            input_types={"model_name": "COMBO"},
            outputs=["UPSCALE_MODEL"],
            output_types=["UPSCALE_MODEL"],
            widgets=[ESRGAN_MODEL],
            models=_model(ESRGAN_MODEL, "upscale_models"),
        ),
        _node(
            7,
            "ImageUpscaleWithModel",
            "Restore and upscale with ESRGAN",
            group,
            (520, 1600),
            size=(360, 80),
            inputs={"upscale_model": Link(6), "image": Link(17)},
            input_types={"upscale_model": "UPSCALE_MODEL", "image": "IMAGE"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
        ),
        _node(
            8,
            "ImageScale",
            f"Fit portrait to the {CANVAS_WIDTH} x {CANVAS_HEIGHT} work canvas",
            group,
            (520, 1740),
            size=(360, 150),
            inputs={"image": Link(7), "upscale_method": "lanczos", "width": CANVAS_WIDTH, "height": CANVAS_HEIGHT, "crop": "center"},
            input_types={"image": "IMAGE", "upscale_method": "COMBO", "width": "INT", "height": "INT", "crop": "COMBO"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=["lanczos", CANVAS_WIDTH, CANVAS_HEIGHT, "center"],
        ),
    ]
    if include_processed_preview:
        nodes.append(
            _node(
                10,
                "PreviewImage",
                "Preview crop + ESRGAN only — before FLUX restoration",
                group,
                (1180, 1500),
                size=SOURCE_PREVIEW_SIZE,
                inputs={"images": Link(8)},
                input_types={"images": "IMAGE"},
                outputs=["IMAGE"],
                output_types=["IMAGE"],
            )
        )
        nodes.append(
            _node(
                501,
                "PreviewImage",
                "Preview original source",
                group,
                (1180, 120),
                size=SOURCE_PREVIEW_SIZE,
                inputs={"images": Link(5)},
                input_types={"images": "IMAGE"},
                outputs=["IMAGE"],
                output_types=["IMAGE"],
            )
        )
        nodes.append(
            _node(
                502,
                "PreviewImage",
                "Preview ESRGAN upscale",
                group,
                (1180, 810),
                size=SOURCE_PREVIEW_SIZE,
                inputs={"images": Link(7)},
                input_types={"images": "IMAGE"},
                outputs=["IMAGE"],
                output_types=["IMAGE"],
            )
        )
    return nodes


def _sampling_nodes(
    *,
    sampler_id: int,
    group: str,
    x: int,
    y: int,
    model: Link,
    positive: Link,
    negative: Link,
    latent: Link,
    seed: int,
    seed_mode: str,
    sampler_name: str,
    steps: int,
    denoise: float,
    title_prefix: str,
) -> list[Node]:
    # One advanced card keeps the graph readable while still exposing the
    # underlying ComfyUI sampler, scheduler and partial-step controls.
    return [
        _node(
            sampler_id,
            "Hoi4PortraitSampler",
            f"{title_prefix} — sampler and generation controls",
            group,
            (x + 1000, y + 150),
            size=(520, 420),
            inputs={
                "model": model,
                "positive": positive,
                "negative": negative,
                "latent_image": latent,
                "noise_seed": seed,
                "steps": steps,
                "cfg": DEFAULT_CFG,
                "guidance": DEFAULT_GUIDANCE,
                "sampling_algorithm": sampler_name,
                "scheduler": "simple",
                "denoise": denoise,
                "add_noise": "enable",
                "start_at_step": 0,
                "end_at_step": 10000,
                "force_full_denoise": True,
            },
            input_types={
                "model": "MODEL",
                "positive": "CONDITIONING",
                "negative": "CONDITIONING",
                "latent_image": "LATENT",
                "noise_seed": "INT",
                "steps": "INT",
                "cfg": "FLOAT",
                "guidance": "FLOAT",
                "sampling_algorithm": "COMBO",
                "scheduler": "COMBO",
                "denoise": "FLOAT",
                "add_noise": "COMBO",
                "start_at_step": "INT",
                "end_at_step": "INT",
                "force_full_denoise": "BOOLEAN",
            },
            outputs=["samples"],
            output_types=["LATENT"],
            widgets=[seed, steps, DEFAULT_CFG, DEFAULT_GUIDANCE, sampler_name, "simple", denoise, "enable", 0, 10000, True],
        ),
    ]


def _edit_stage(
    *,
    id_start: int,
    group: str,
    x: int,
    image: Link,
    model: Link,
    prompt: str,
    negative: str,
    seed: int,
    title_prefix: str,
    denoise: float = 1.0,
    seed_mode: str = "fixed",
    y: int = 120,
    prompt_node_title: str | None = None,
    sampler_name: str = "euler",
    steps: int = DEFAULT_STEPS,
    double_reference: bool = False,
    reference_images: tuple[Link, Link] | None = None,
    start_from_empty: bool = False,
) -> tuple[list[Node], Link]:
    i = id_start
    if double_reference and reference_images is not None:
        raise ValueError("double_reference and reference_images are mutually exclusive")
    nodes: list[Node] = [
        _node(
            i,
            "CLIPTextEncode",
            prompt_node_title or f"{title_prefix} instructions",
            group,
            (x, y),
            size=(430, 280),
            inputs={"clip": Link(2), "text": prompt},
            input_types={"clip": "CLIP", "text": "STRING"},
            outputs=["CONDITIONING"],
            output_types=["CONDITIONING"],
            widgets=[prompt],
        ),
        _node(
            i + 1,
            "CLIPTextEncode",
            f"{title_prefix} negative",
            group,
            (x, y + 330),
            size=(430, 200),
            inputs={"clip": Link(2), "text": negative},
            input_types={"clip": "CLIP", "text": "STRING"},
            outputs=["CONDITIONING"],
            output_types=["CONDITIONING"],
            widgets=[negative],
        ),
        _node(
            i + 2,
            "EmptyFlux2LatentImage" if start_from_empty else "VAEEncode",
            f"Create {title_prefix.lower()} edit latent" if start_from_empty else f"Encode {title_prefix.lower()} reference",
            group,
            (x + 500, y),
            size=(300, 120),
            inputs=(
                {"width": CANVAS_WIDTH, "height": CANVAS_HEIGHT, "batch_size": 1}
                if start_from_empty
                else {"pixels": image, "vae": Link(3)}
            ),
            input_types=(
                {"width": "INT", "height": "INT", "batch_size": "INT"}
                if start_from_empty
                else {"pixels": "IMAGE", "vae": "VAE"}
            ),
            outputs=["LATENT"],
            output_types=["LATENT"],
            widgets=[CANVAS_WIDTH, CANVAS_HEIGHT, 1] if start_from_empty else [],
        ),
        _node(
            i + 3,
            "Flux2KleinMultiReferenceLatent" if (double_reference or reference_images) else "ReferenceLatent",
            (
                "Attach two identity references to positive conditioning"
                if reference_images
                else "Attach source twice to positive conditioning"
                if double_reference
                else "Attach reference to positive conditioning"
            ),
            group,
            (x + 500, y + 190),
            size=(300, 120),
            inputs=(
                {"conditioning": Link(i), "latent_1": Link(i + 5), "latent_2": Link(i + 6)}
                if reference_images
                else
                {"conditioning": Link(i), "latent_1": Link(i + 2), "latent_2": Link(i + 2)}
                if double_reference
                else {"conditioning": Link(i), "latent": Link(i + 2)}
            ),
            input_types=(
                {"conditioning": "CONDITIONING", "latent_1": "LATENT", "latent_2": "LATENT"}
                if (double_reference or reference_images)
                else {"conditioning": "CONDITIONING", "latent": "LATENT"}
            ),
            outputs=["CONDITIONING"],
            output_types=["CONDITIONING"],
        ),
        _node(
            i + 4,
            "Flux2KleinMultiReferenceLatent" if (double_reference or reference_images) else "ReferenceLatent",
            (
                "Attach two identity references to negative conditioning"
                if reference_images
                else "Attach source twice to negative conditioning"
                if double_reference
                else "Attach reference to negative conditioning"
            ),
            group,
            (x + 500, y + 380),
            size=(300, 120),
            inputs=(
                {"conditioning": Link(i + 1), "latent_1": Link(i + 5), "latent_2": Link(i + 6)}
                if reference_images
                else
                {"conditioning": Link(i + 1), "latent_1": Link(i + 2), "latent_2": Link(i + 2)}
                if double_reference
                else {"conditioning": Link(i + 1), "latent": Link(i + 2)}
            ),
            input_types=(
                {"conditioning": "CONDITIONING", "latent_1": "LATENT", "latent_2": "LATENT"}
                if (double_reference or reference_images)
                else {"conditioning": "CONDITIONING", "latent": "LATENT"}
            ),
            outputs=["CONDITIONING"],
            output_types=["CONDITIONING"],
        ),
        _node(
            i + 11,
            "VAEDecode",
            f"Decode {title_prefix.lower()} result",
            group,
            (x + 1430, y + 500),
            size=(300, 120),
            inputs={"samples": Link(i + 10), "vae": Link(3)},
            input_types={"samples": "LATENT", "vae": "VAE"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
        ),
        _node(
            i + 15,
            "PreviewImage",
            f"Preview {title_prefix.lower()} result (live while sampling)",
            group,
            (x + 1430, y + 680),
            size=(560, 680),
            inputs={"images": Link(i + 11)},
            input_types={"images": "IMAGE"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
        ),
    ]
    nodes.extend(
        _sampling_nodes(
            sampler_id=i + 10,
            group=group,
            x=x,
            y=y,
            model=model,
            positive=Link(i + 3),
            negative=Link(i + 4),
            latent=Link(i + 2),
            seed=seed,
            seed_mode=seed_mode,
            sampler_name=sampler_name,
            steps=steps,
            denoise=denoise,
            title_prefix=title_prefix,
        )
    )
    if reference_images:
        nodes.extend(
            [
                _node(
                    i + 5,
                    "VAEEncode",
                    f"Encode {title_prefix.lower()} original-crop reference",
                    group,
                    (x + 500, y + 670),
                    size=(300, 120),
                    inputs={"pixels": reference_images[0], "vae": Link(3)},
                    input_types={"pixels": "IMAGE", "vae": "VAE"},
                    outputs=["LATENT"],
                    output_types=["LATENT"],
                ),
                _node(
                    i + 6,
                    "VAEEncode",
                    f"Encode {title_prefix.lower()} selected-processed reference",
                    group,
                    (x + 900, y + 670),
                    size=(300, 120),
                    inputs={"pixels": reference_images[1], "vae": Link(3)},
                    input_types={"pixels": "IMAGE", "vae": "VAE"},
                    outputs=["LATENT"],
                    output_types=["LATENT"],
                ),
            ]
        )
    return nodes, Link(i + 11)


def _text_stage(*, group: str, x: int) -> tuple[list[Node], Link]:
    nodes = [
        _node(
            20,
            "CLIPTextEncode",
            "Describe only the person",
            group,
            (x, 120),
            size=(450, 300),
            inputs={"clip": Link(2), "text": TEXT_PROMPT},
            input_types={"clip": "CLIP", "text": "STRING"},
            outputs=["CONDITIONING"],
            output_types=["CONDITIONING"],
            widgets=[TEXT_PROMPT],
        ),
        _node(
            21,
            "CLIPTextEncode",
            "Negative prompt",
            group,
            (x, 500),
            size=(450, 190),
            inputs={"clip": Link(2), "text": STYLE_NEGATIVE},
            input_types={"clip": "CLIP", "text": "STRING"},
            outputs=["CONDITIONING"],
            output_types=["CONDITIONING"],
            widgets=[STYLE_NEGATIVE],
        ),
        _node(
            22,
            "EmptyFlux2LatentImage",
            f"Set {CANVAS_WIDTH} x {CANVAS_HEIGHT} portrait canvas",
            group,
            (x + 520, 120),
            inputs={"width": CANVAS_WIDTH, "height": CANVAS_HEIGHT, "batch_size": 1},
            input_types={"width": "INT", "height": "INT", "batch_size": "INT"},
            outputs=["LATENT"],
            output_types=["LATENT"],
            widgets=[CANVAS_WIDTH, CANVAS_HEIGHT, 1],
        ),
        _node(
            28,
            "VAEDecode",
            "Decode final styled portrait",
            group,
            (x + 1430, 500),
            size=(300, 120),
            inputs={"samples": Link(27), "vae": Link(3)},
            input_types={"samples": "LATENT", "vae": "VAE"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
        ),
        _node(
            29,
            "PreviewImage",
            "Preview generated portrait (live while sampling)",
            group,
            (x + 1430, 680),
            size=(560, 680),
            inputs={"images": Link(28)},
            input_types={"images": "IMAGE"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
        ),
    ]
    nodes.extend(
        _sampling_nodes(
            sampler_id=27,
            group=group,
            x=x,
            y=120,
            model=Link(4),
            positive=Link(20),
            negative=Link(21),
            latent=Link(22),
            seed=42,
            seed_mode="fixed",
            sampler_name="euler",
            steps=DEFAULT_STEPS,
            denoise=1.0,
            title_prefix="HOI4 portrait",
        )
    )
    return nodes, Link(28)


def _background_and_outputs(*, final_image: Link, x: int = 5200) -> list[Node]:
    background_group = "05 Optional background - after generation"
    output_group = "06 Preview and save"
    nodes = [
        _node(
            60,
            "LoadImage",
            "Load replacement background",
            background_group,
            (x, 120),
            size=(340, 300),
            inputs={"image": "hoi4_leader_portrait_background.png"},
            input_types={"image": "COMBO"},
            outputs=["IMAGE", "MASK"],
            output_types=["IMAGE", "MASK"],
            widgets=["hoi4_leader_portrait_background.png", "image"],
        ),
        _node(
            61,
            "ImageScale",
            "Fit background to final master canvas",
            background_group,
            (x, 500),
            size=(340, 150),
            inputs={"image": Link(60), "upscale_method": "lanczos", "width": CANVAS_WIDTH, "height": CANVAS_HEIGHT, "crop": "center"},
            input_types={"image": "IMAGE", "upscale_method": "COMBO", "width": "INT", "height": "INT", "crop": "COMBO"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=["lanczos", CANVAS_WIDTH, CANVAS_HEIGHT, "center"],
        ),
        _node(
            62,
            "LoadBackgroundRemovalModel",
            "Load BiRefNet foreground model",
            background_group,
            (x + 420, 120),
            inputs={"bg_removal_name": BACKGROUND_MODEL},
            input_types={"bg_removal_name": "COMBO"},
            outputs=["BACKGROUND_REMOVAL"],
            output_types=["BACKGROUND_REMOVAL"],
            widgets=[BACKGROUND_MODEL],
            models=_model(BACKGROUND_MODEL, "background_removal"),
        ),
        _node(
            63,
            "RemoveBackground",
            "Mask the final styled portrait",
            background_group,
            (x + 420, 300),
            inputs={"bg_removal_model": Link(62), "image": final_image},
            input_types={"bg_removal_model": "BACKGROUND_REMOVAL", "image": "IMAGE"},
            outputs=["MASK"],
            output_types=["MASK"],
        ),
        _node(
            65,
            "ImageCompositeMasked",
            "Composite only after the styled portrait exists",
            background_group,
            (x + 800, 250),
            size=(360, 180),
            inputs={"destination": Link(61), "source": final_image, "x": 0, "y": 0, "resize_source": True, "mask": Link(63)},
            input_types={"destination": "IMAGE", "source": "IMAGE", "x": "INT", "y": "INT", "resize_source": "BOOLEAN", "mask": "MASK"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=[0, 0, True],
        ),
        _node(
            66,
            "ComfySwitchNode",
            "Toggle replacement background (off by default)",
            background_group,
            (x + 800, 520),
            size=(360, 130),
            inputs={"switch": False, "on_false": final_image, "on_true": Link(65)},
            input_types={"switch": "BOOLEAN", "on_false": "IMAGE", "on_true": "IMAGE"},
            outputs=["output"],
            output_types=["IMAGE"],
            widgets=[False],
        ),
        _node(
            71,
            "SaveImage",
            f"Save {CANVAS_WIDTH} x {CANVAS_HEIGHT} master PNG",
            output_group,
            (x + 1880, 120),
            inputs={"images": Link(66), "filename_prefix": "1024x1365/portrait"},
            input_types={"images": "IMAGE", "filename_prefix": "STRING"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=["1024x1365/portrait"],
        ),
        _node(
            72,
            "ImageScale",
            "Resize to HOI4 156 x 210",
            output_group,
            (x + 1880, 320),
            size=(340, 150),
            inputs={"image": Link(66), "upscale_method": "lanczos", "width": GAME_WIDTH, "height": GAME_HEIGHT, "crop": "center"},
            input_types={"image": "IMAGE", "upscale_method": "COMBO", "width": "INT", "height": "INT", "crop": "COMBO"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=["lanczos", GAME_WIDTH, GAME_HEIGHT, "center"],
        ),
        _node(
            73,
            "SaveImage",
            "Save game-size portrait PNG",
            output_group,
            (x + 1880, 540),
            inputs={"images": Link(72), "filename_prefix": "156x210/portrait"},
            input_types={"images": "IMAGE", "filename_prefix": "STRING"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=["156x210/portrait"],
        ),
        _node(
            74,
            "Hoi4SaveDDS",
            "Save HOI4-ready 156 x 210 DDS",
            output_group,
            (x + 1880, 760),
            size=(360, 150),
            inputs={"images": Link(72), "filename_prefix": "156x210/dds/portrait"},
            input_types={"images": "IMAGE", "filename_prefix": "STRING"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=["156x210/dds/portrait"],
        ),
        _node(
            75,
            "ImageScale",
            "Enlarge game preview for clarity (does not change saved files)",
            output_group,
            (x + 1380, 320),
            size=(340, 150),
            inputs={
                "image": Link(72),
                "upscale_method": "lanczos",
                "width": PREVIEW_BOOST_WIDTH,
                "height": PREVIEW_BOOST_HEIGHT,
                "crop": "disabled",
            },
            input_types={"image": "IMAGE", "upscale_method": "COMBO", "width": "INT", "height": "INT", "crop": "COMBO"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=["lanczos", PREVIEW_BOOST_WIDTH, PREVIEW_BOOST_HEIGHT, "disabled"],
        ),
    ]
    return nodes, Link(75)


def _background_and_outputs_multi(
    *,
    final_images: list[Link],
    x: int = 5600,
    id_start: int = 120,
) -> list[Node]:
    """Fan one background/removal setup into one optional output branch per final."""
    background_group = "05 Optional background - after generation"
    output_group = "06 Preview and save"
    nodes = [
        _node(
            id_start - 1,
            "PrimitiveBoolean",
            "Toggle replacement background for all three candidates (off by default)",
            background_group,
            (x, 680),
            size=(340, 100),
            inputs={"value": False},
            input_types={"value": "BOOLEAN"},
            outputs=["BOOLEAN"],
            output_types=["BOOLEAN"],
            widgets=[False],
        ),
        _node(
            id_start,
            "LoadImage",
            "Load one replacement background for all candidates",
            background_group,
            (x, 120),
            size=(340, 300),
            inputs={"image": "hoi4_leader_portrait_background.png"},
            input_types={"image": "COMBO"},
            outputs=["IMAGE", "MASK"],
            output_types=["IMAGE", "MASK"],
            widgets=["hoi4_leader_portrait_background.png", "image"],
        ),
        _node(
            id_start + 1,
            "ImageScale",
            "Fit one background to the final master canvas",
            background_group,
            (x, 500),
            size=(340, 150),
            inputs={
                "image": Link(id_start),
                "upscale_method": "lanczos",
                "width": CANVAS_WIDTH,
                "height": CANVAS_HEIGHT,
                "crop": "center",
            },
            input_types={"image": "IMAGE", "upscale_method": "COMBO", "width": "INT", "height": "INT", "crop": "COMBO"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=["lanczos", CANVAS_WIDTH, CANVAS_HEIGHT, "center"],
        ),
        _node(
            id_start + 2,
            "LoadBackgroundRemovalModel",
            "Load one BiRefNet model for all candidates",
            background_group,
            (x + 420, 120),
            inputs={"bg_removal_name": BACKGROUND_MODEL},
            input_types={"bg_removal_name": "COMBO"},
            outputs=["BACKGROUND_REMOVAL"],
            output_types=["BACKGROUND_REMOVAL"],
            widgets=[BACKGROUND_MODEL],
            models=_model(BACKGROUND_MODEL, "background_removal"),
        ),
    ]
    for index, final_image in enumerate(final_images, start=1):
        branch = id_start + 3 + (index - 1) * 10
        # Match the LoRA candidate lane spacing exactly.  Keeping each
        # candidate's background/output card on the same repeated row makes
        # the whole right-hand half of the canvas visually symmetrical.
        row_y = 1050 + (index - 1) * SOURCE_CANDIDATE_ROW_GAP
        label = f"candidate {index}"
        prefix = f"hoi4_portraits/candidate_{index}"
        nodes.extend(
            [
                _node(
                    branch,
                    "RemoveBackground",
                    f"Mask {label} final portrait",
                    background_group,
                    (x + 420, row_y),
                    inputs={"bg_removal_model": Link(id_start + 2), "image": final_image},
                    input_types={"bg_removal_model": "BACKGROUND_REMOVAL", "image": "IMAGE"},
                    outputs=["MASK"],
                    output_types=["MASK"],
                ),
                _node(
                    branch + 1,
                    "ImageCompositeMasked",
                    f"Composite {label} after final styling",
                    background_group,
                    (x + 800, row_y),
                    size=(360, 180),
                    inputs={
                        "destination": Link(id_start + 1),
                        "source": final_image,
                        "x": 0,
                        "y": 0,
                        "resize_source": True,
                        "mask": Link(branch),
                    },
                    input_types={"destination": "IMAGE", "source": "IMAGE", "x": "INT", "y": "INT", "resize_source": "BOOLEAN", "mask": "MASK"},
                    outputs=["IMAGE"],
                    output_types=["IMAGE"],
                    widgets=[0, 0, True],
                ),
                _node(
                    branch + 2,
                    "ComfySwitchNode",
                    f"Toggle background for {label} (off by default)",
                    background_group,
                    (x + 800, row_y + 240),
                    size=(360, 130),
                    inputs={"switch": Link(id_start - 1), "on_false": final_image, "on_true": Link(branch + 1)},
                    input_types={"switch": "BOOLEAN", "on_false": "IMAGE", "on_true": "IMAGE"},
                    outputs=["output"],
                    output_types=["IMAGE"],
                    widgets=[],
                ),
                _node(
                    branch + 4,
                    "SaveImage",
                    f"Save {label} {CANVAS_WIDTH} x {CANVAS_HEIGHT} master PNG",
                    output_group,
                    (x + 1880, row_y),
                    inputs={"images": Link(branch + 2), "filename_prefix": f"1024x1365/candidate_{index}"},
                    input_types={"images": "IMAGE", "filename_prefix": "STRING"},
                    outputs=["IMAGE"],
                    output_types=["IMAGE"],
                    widgets=[f"1024x1365/candidate_{index}"],
                ),
                _node(
                    branch + 5,
                    "ImageScale",
                    f"Resize {label} to HOI4 156 x 210",
                    output_group,
                    (x + 1880, row_y + 200),
                    size=(340, 150),
                    inputs={"image": Link(branch + 2), "upscale_method": "lanczos", "width": GAME_WIDTH, "height": GAME_HEIGHT, "crop": "center"},
                    input_types={"image": "IMAGE", "upscale_method": "COMBO", "width": "INT", "height": "INT", "crop": "COMBO"},
                    outputs=["IMAGE"],
                    output_types=["IMAGE"],
                    widgets=["lanczos", GAME_WIDTH, GAME_HEIGHT, "center"],
                ),
                _node(
                    branch + 6,
                    "SaveImage",
                    f"Save {label} game-size PNG",
                    output_group,
                    (x + 1880, row_y + 420),
                    inputs={"images": Link(branch + 5), "filename_prefix": f"156x210/candidate_{index}"},
                    input_types={"images": "IMAGE", "filename_prefix": "STRING"},
                    outputs=["IMAGE"],
                    output_types=["IMAGE"],
                    widgets=[f"156x210/candidate_{index}"],
                ),
                _node(
                    branch + 9,
                    "ImageScale",
                    f"Enlarge {label} game preview for clarity (does not change saved files)",
                    output_group,
                    (x + 2420, row_y),
                    size=(340, 150),
                    inputs={
                        "image": Link(branch + 5),
                        "upscale_method": "lanczos",
                        "width": PREVIEW_BOOST_WIDTH,
                        "height": PREVIEW_BOOST_HEIGHT,
                        "crop": "disabled",
                    },
                    input_types={"image": "IMAGE", "upscale_method": "COMBO", "width": "INT", "height": "INT", "crop": "COMBO"},
                    outputs=["IMAGE"],
                    output_types=["IMAGE"],
                    widgets=["lanczos", PREVIEW_BOOST_WIDTH, PREVIEW_BOOST_HEIGHT, "disabled"],
                ),
                _node(
                    branch + 8,
                    "Hoi4SaveDDS",
                    f"Save {label} HOI4-ready DDS",
                    output_group,
                    (x + 1880, row_y + 650),
                    size=(360, 150),
                    inputs={"images": Link(branch + 5), "filename_prefix": f"156x210/dds/candidate_{index}"},
                    input_types={"images": "IMAGE", "filename_prefix": "STRING"},
                    outputs=["IMAGE"],
                    output_types=["IMAGE"],
                    widgets=[f"156x210/dds/candidate_{index}"],
                ),
            ]
        )
    preview_links = [Link(id_start + 3 + (index - 1) * 10 + 9) for index in range(1, len(final_images) + 1)]
    return nodes, preview_links


def _processing_outputs(*, processed_image: Link) -> list[Node]:
    output_group = "04 Processed portrait output"
    nodes = [
        _node(
            71,
            "SaveImage",
            f"Save {CANVAS_WIDTH} x {CANVAS_HEIGHT} processed PNG",
            output_group,
            (4500, 120),
            inputs={"images": processed_image, "filename_prefix": "1024x1365/processed"},
            input_types={"images": "IMAGE", "filename_prefix": "STRING"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=["1024x1365/processed"],
        ),
        _node(
            72,
            "ImageScale",
            "Resize to HOI4 156 x 210",
            output_group,
            (4500, 320),
            size=(340, 150),
            inputs={"image": processed_image, "upscale_method": "lanczos", "width": GAME_WIDTH, "height": GAME_HEIGHT, "crop": "center"},
            input_types={"image": "IMAGE", "upscale_method": "COMBO", "width": "INT", "height": "INT", "crop": "COMBO"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=["lanczos", GAME_WIDTH, GAME_HEIGHT, "center"],
        ),
        _node(
            73,
            "SaveImage",
            "Save processed game-size PNG",
            output_group,
            (4500, 540),
            inputs={"images": Link(72), "filename_prefix": "156x210/processed"},
            input_types={"images": "IMAGE", "filename_prefix": "STRING"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=["156x210/processed"],
        ),
        _node(
            74,
            "Hoi4SaveDDS",
            "Save processed HOI4-ready DDS",
            output_group,
            (4500, 760),
            size=(360, 150),
            inputs={"images": Link(72), "filename_prefix": "156x210/dds/processed"},
            input_types={"images": "IMAGE", "filename_prefix": "STRING"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=["156x210/dds/processed"],
        ),
        _node(
            75,
            "ImageScale",
            "Enlarge processed preview for clarity (does not change saved files)",
            output_group,
            (3900, 120),
            size=(340, 150),
            inputs={
                "image": Link(72),
                "upscale_method": "lanczos",
                "width": PREVIEW_BOOST_WIDTH,
                "height": PREVIEW_BOOST_HEIGHT,
                "crop": "disabled",
            },
            input_types={"image": "IMAGE", "upscale_method": "COMBO", "width": "INT", "height": "INT", "crop": "COMBO"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=["lanczos", PREVIEW_BOOST_WIDTH, PREVIEW_BOOST_HEIGHT, "disabled"],
        ),
    ]
    return nodes, Link(75)


def _groups(
    *,
    has_source: bool,
    has_restoration: bool,
    candidate_count: int = 1,
    background_x: int | None = None,
) -> list[Group]:
    groups: list[Group] = [Group("00 Welcome & setup", (40, 40, 840, 980), "#6b7280")]
    if has_source:
        groups.append(Group("01 Source and ESRGAN", (980, 40, 1180, 2200), "#557a46"))
    groups.append(Group("02 FLUX.2 Klein 9B models", (2300, 40, 430, 1100), "#3f789e"))
    if has_restoration:
        groups.append(Group("03 Optional FLUX.2 restoration", (2830, 40, 2100, 1100), "#8b6f47"))
        style_height = 6200 if candidate_count > 1 else 3600
        groups.append(Group("04 HOI4 LoRA styling", (5200, 40, 3600, style_height), "#7a568e"))
    else:
        groups.append(Group("04 HOI4 LoRA styling", (2830, 40, 2200, 3600), "#7a568e"))
    if background_x is None:
        background_x = 9400 if has_restoration else 5600
    output_height = 3040 if candidate_count > 1 else 1120
    groups.append(Group("05 Optional background - after generation", (background_x - 80, 40, 1300, output_height), "#8d5b5b"))
    groups.append(Group("06 Preview and save", (background_x + 1300, 40, 1200, output_height), "#596b82"))
    return groups


def _processing_groups() -> list[Group]:
    return [
        Group("00 Welcome & setup", (40, 40, 860, 2600), "#6b7280"),
        Group("01 Source and ESRGAN", (980, 40, 1180, 2200), "#557a46"),
        Group("02 FLUX.2 Klein 9B models", (2300, 40, 430, 1100), "#3f789e"),
        Group("03 Optional FLUX.2 restoration", (2830, 40, 2100, 1100), "#8b6f47"),
        Group("04 Processed portrait output", (5200, 40, 2200, 1800), "#596b82"),
    ]


def _adonis_restoration_stages(*, image: Link, seed: int = 17) -> tuple[list[Node], Link]:
    """Build the Adonis Base -> Adonis Post sequence from the model guide."""

    base_nodes, base_output = _edit_stage(
        id_start=20,
        group="03 Optional FLUX.2 restoration",
        x=1540,
        image=image,
        model=Link(191),
        prompt=RESTORATION_BASE_PROMPT,
        negative=RESTORATION_NEGATIVE,
        seed=seed,
        title_prefix="Adonis Base restoration",
        seed_mode="fixed",
    )
    post_nodes, post_output = _edit_stage(
        id_start=400,
        group="03 Optional FLUX.2 restoration",
        x=3300,
        image=base_output,
        model=Link(192),
        prompt=RESTORATION_POST_PROMPT,
        negative=RESTORATION_NEGATIVE,
        seed=seed,
        title_prefix="Adonis Post restoration",
        seed_mode="fixed",
    )
    base_preview = next(node for node in base_nodes if node.node_id == 35)
    base_preview.title = "Preview Adonis Base restoration"
    post_preview = next(node for node in post_nodes if node.node_id == 415)
    post_preview.title = "Preview Adonis Post restoration"
    return base_nodes + post_nodes, post_output


def _comparison_row(
    *,
    group: str,
    x: int,
    y: int,
    esrgan: Link | None,
    restored: Link | None,
    finals: list[Link],
    final_label: str = "candidate {index}",
) -> list[Node]:
    """A close comparison row: [ESRGAN] [restoration] [final 1] [final 2] [final 3].

    The row sits below the generation cards so the source processing, the
    optional restoration, and every final game-size result can be compared in
    one glance.  The final previews show the upscaled-for-display game images
    (the saved PNG/DDS stay exactly 156x210).
    """
    nodes: list[Node] = []
    node_id = 600
    gap = 60
    if esrgan is not None:
        nodes.append(
            _node(
                node_id,
                "PreviewImage",
                "Preview ESRGAN restored source (before LoRA)",
                group,
                (x, y),
                size=FINAL_PREVIEW_SIZE,
                inputs={"images": esrgan},
                input_types={"images": "IMAGE"},
                outputs=["IMAGE"],
                output_types=["IMAGE"],
            )
        )
        node_id += 1
        x += FINAL_PREVIEW_SIZE[0] + gap
    if restored is not None:
        nodes.append(
            _node(
                node_id,
                "PreviewImage",
                "Preview FLUX.2 restoration pass (Adonis)",
                group,
                (x, y),
                size=FINAL_PREVIEW_SIZE,
                inputs={"images": restored},
                input_types={"images": "IMAGE"},
                outputs=["IMAGE"],
                output_types=["IMAGE"],
            )
        )
        node_id += 1
        x += FINAL_PREVIEW_SIZE[0] + 180
    for index, final in enumerate(finals, start=1):
        nodes.append(
            _node(
                node_id,
                "PreviewImage",
                f"Final portrait {final_label.format(index=index)} — 156 x 210 (game size)",
                group,
                (x, y),
                size=FINAL_PREVIEW_SIZE,
                inputs={"images": final},
                input_types={"images": "IMAGE"},
                outputs=["IMAGE"],
                output_types=["IMAGE"],
            )
        )
        node_id += 1
        x += FINAL_PREVIEW_SIZE[0] + gap
    return nodes


def _beginner_notes(*, with_restoration: bool) -> list[Node]:
    """The beginner guide column plus the section note for restoration."""
    nodes = [
        _note(
            800,
            "📦 Setup guide — models and ComfyUI folders",
            SETUP_GUIDE_NOTE,
            "00 Welcome & setup",
            (100, 100),
            size=(860, 940),
        ),
        _note(
            801,
            "🎛️ Sampler controls — what steps and CFG do",
            SAMPLING_NOTE,
            "00 Welcome & setup",
            (100, 1140),
            size=(860, 660),
        ),
        _note(
            802,
            "✍️ Prompting guide",
            PROMPTING_NOTE,
            "00 Welcome & setup",
            (100, 1900),
            size=(860, 560),
        ),
    ]
    if with_restoration:
        nodes.append(
            _note(
                803,
                "✨ Why the restoration pass is worth keeping",
                RESTORATION_NOTE,
                "03 Optional FLUX.2 restoration",
                (5200, 120),
                size=(840, 520),
            )
        )
    return nodes


def build_source() -> Graph:
    # Show the crop + ESRGAN result before the optional FLUX pass.  This is
    # intentionally present in the source workflow as well as the processing
    # workflow, so a user can verify the input framing before any generation.
    nodes = _source_nodes(include_processed_preview=True) + _model_nodes() + _beginner_notes(with_restoration=True)
    restoration_nodes, restored = _adonis_restoration_stages(image=Link(8))
    nodes.extend(restoration_nodes)
    nodes.append(
        _node(
            32,
            "ComfySwitchNode",
            "Toggle FLUX restoration (on: ESRGAN then FLUX; off: keep ESRGAN output)",
            "03 Optional FLUX.2 restoration",
            (2450, 880),
            size=(360, 150),
            inputs={"switch": True, "on_false": Link(8), "on_true": restored},
            input_types={"switch": "BOOLEAN", "on_false": "IMAGE", "on_true": "IMAGE"},
            outputs=["output"],
            output_types=["IMAGE"],
            widgets=[True],
        )
    )
    styled_images: list[Link] = []
    if len(SOURCE_STYLE_SEEDS) != len(SOURCE_CANDIDATE_SAMPLING):
        raise ValueError("source seeds and sampling presets must have the same length")
    for index, (seed, (sampler_name, steps)) in enumerate(
        zip(SOURCE_STYLE_SEEDS, SOURCE_CANDIDATE_SAMPLING), start=1
    ):
        style_nodes, styled = _edit_stage(
            id_start=40 + (index - 1) * 20,
            group="04 HOI4 LoRA styling",
            x=3840,
            y=100 + (index - 1) * SOURCE_CANDIDATE_ROW_GAP,
            image=Link(32),
            model=Link(4),
            prompt=STYLE_PROMPT,
            negative=STYLE_NEGATIVE,
            seed=seed,
            title_prefix=f"Candidate {index} identity LoRA",
            denoise=SOURCE_STYLE_DENOISE,
            prompt_node_title=f"Editable candidate {index} prompt — edits affect only candidate {index}",
            sampler_name=sampler_name,
            steps=steps,
        )
        nodes.extend(style_nodes)
        styled_images.append(styled)
    output_nodes, preview_links = _background_and_outputs_multi(
        final_images=styled_images, x=6400, id_start=120
    )
    nodes.extend(output_nodes)
    # Portrait comparison row: ESRGAN source, restoration pass, then the three
    # game-size finals side by side for a clear head-to-head.
    nodes.extend(
        _comparison_row(
            group="04 HOI4 LoRA styling",
            x=5840,
            y=5400,
            esrgan=Link(8),
            restored=Link(32),
            finals=preview_links,
        )
    )
    groups = _groups(
        has_source=True,
        has_restoration=True,
        candidate_count=SOURCE_CANDIDATE_COUNT,
        background_x=6400,
    )
    return Graph(
        workflow_id="hoi4_portrait_flux2_klein_9b_source",
        description="Source portrait workflow: RealESRGAN first, optional Adonis Base and Post restoration, then three independent HOI4 LoRA portrait candidates from the processed source reference.",
        kind="image_to_image",
        nodes=nodes,
        groups=groups,
        metadata={
            "restoration_order": ["RealESRGAN_x2plus", "optional_adonis_base", "optional_adonis_post"],
            "flux_restoration_default": True,
            "face_processing_default": True,
            "face_processing_bypass": "whole_composition_center_crop_then_esrgan",
            "candidate_count": SOURCE_CANDIDATE_COUNT,
            "candidate_seed_count": SOURCE_CANDIDATE_COUNT,
            "background_candidate_count": SOURCE_CANDIDATE_COUNT,
            "source_crop": "toggleable_adaptive_head_and_shoulders_zoom_0.90_adjustable_headwear_before_esrgan",
            "pose_preservation": "encoded_source_latent_is_sampler_start",
            "identity_preservation": "source_reference",
            "generation_start": "encoded_processed_source",
            "background_order": "after_final_lora_styled_decode",
            "comparison_row": ["esrgan", "flux_restoration", "final_1", "final_2", "final_3"],
        },
    )


def build_processing() -> Graph:
    nodes = _source_nodes(include_processed_preview=True) + _model_nodes(include_lora=False) + _beginner_notes(with_restoration=True)
    processing_preview = next(node for node in nodes if node.node_id == 10)
    processing_preview.title = "Preview crop + ESRGAN only — before FLUX restoration"
    restoration_nodes, restored = _adonis_restoration_stages(image=Link(8))
    nodes.extend(restoration_nodes)
    nodes.append(
        _node(
            32,
            "ComfySwitchNode",
            "Toggle FLUX restoration (on: ESRGAN then FLUX; off: keep ESRGAN output)",
            "03 Optional FLUX.2 restoration",
            (2450, 880),
            size=(360, 150),
            inputs={"switch": True, "on_false": Link(8), "on_true": restored},
            input_types={"switch": "BOOLEAN", "on_false": "IMAGE", "on_true": "IMAGE"},
            outputs=["output"],
            output_types=["IMAGE"],
            widgets=[True],
        )
    )
    output_nodes, processed_preview = _processing_outputs(processed_image=Link(32))
    nodes.extend(output_nodes)
    nodes.extend(
        _comparison_row(
            group="04 Processed portrait output",
            x=5300,
            y=1000,
            esrgan=Link(8),
            restored=Link(32),
            finals=[processed_preview],
            final_label="processed",
        )
    )
    return Graph(
        workflow_id="hoi4_portrait_processing_only",
        description="Source processing workflow: adjustable crop, RealESRGAN, optional Adonis Base and Post restoration, and processed portrait outputs without LoRA styling.",
        kind="image_processing",
        nodes=nodes,
        groups=_processing_groups(),
        metadata={
            "style_lora": None,
            "restoration_order": ["RealESRGAN_x2plus", "optional_adonis_base", "optional_adonis_post"],
            "flux_restoration_default": True,
            "face_processing_default": True,
            "face_processing_bypass": "whole_composition_center_crop_then_esrgan",
            "source_crop": "toggleable_adaptive_head_and_shoulders_zoom_0.90_adjustable_headwear_before_esrgan",
            "background_order": "not_applicable_processing_only",
            "processing_preview": "crop_and_esrgan_before_flux_restoration",
            "comparison_row": ["esrgan", "flux_restoration", "processed_final"],
        },
    )


def build_text_to_image() -> Graph:
    nodes = _model_nodes(include_restoration_lokr=False) + _beginner_notes(with_restoration=False)
    text_nodes, styled = _text_stage(group="04 HOI4 LoRA styling", x=1540)
    nodes.extend(text_nodes)
    output_nodes, final_preview = _background_and_outputs(final_image=styled, x=4000)
    nodes.extend(output_nodes)
    nodes.extend(
        _comparison_row(
            group="04 HOI4 LoRA styling",
            x=3300,
            y=900,
            esrgan=None,
            restored=None,
            finals=[final_preview],
            final_label="generated",
        )
    )
    groups = [group for group in _groups(has_source=False, has_restoration=False) if group.title != "01 Source and ESRGAN"]
    return Graph(
        workflow_id="hoi4_portrait_flux2_klein_9b_text_to_image",
        description="Text-to-image HOI4 leader workflow using FLUX.2 Klein 9B and the project LoRA, with optional background replacement only after generation.",
        kind="text_to_image",
        nodes=nodes,
        groups=groups,
        metadata={
            "restoration_order": [],
            "flux_restoration_default": False,
            "background_order": "after_final_lora_styled_decode",
            "comparison_row": ["final_generated"],
        },
    )


def build_batch() -> Graph:
    """Process every image in input/hoi4_portraits_batch with one sampler."""

    nodes = _source_nodes(include_processed_preview=True) + _model_nodes() + _beginner_notes(with_restoration=True)
    batch_input = next(node for node in nodes if node.node_id == 5)
    batch_input.class_type = "Hoi4BatchInput"
    batch_input.title = "Load all portraits from input/hoi4_portraits_batch"
    batch_input.size = (440, 180)
    batch_input.inputs = {"input_folder": "hoi4_portraits_batch", "file_pattern": "*.png;*.jpg;*.jpeg;*.webp"}
    batch_input.input_types = {"input_folder": "STRING", "file_pattern": "STRING"}
    batch_input.outputs = ["images", "masks", "filenames"]
    batch_input.output_types = ["IMAGE", "MASK", "STRING"]
    batch_input.widgets = ["hoi4_portraits_batch", "*.png;*.jpg;*.jpeg;*.webp"]

    restoration_nodes, restored = _adonis_restoration_stages(image=Link(8))
    nodes.extend(restoration_nodes)
    nodes.append(
        _node(
            32,
            "ComfySwitchNode",
            "Toggle FLUX restoration (on: Adonis Base then Post; off: ESRGAN only)",
            "03 Optional FLUX.2 restoration",
            (2450, 880),
            size=(360, 150),
            inputs={"switch": True, "on_false": Link(8), "on_true": restored},
            input_types={"switch": "BOOLEAN", "on_false": "IMAGE", "on_true": "IMAGE"},
            outputs=["output"],
            output_types=["IMAGE"],
            widgets=[True],
        )
    )
    style_nodes, styled = _edit_stage(
        id_start=40,
        group="04 HOI4 LoRA styling",
        x=5200,
        image=Link(32),
        model=Link(4),
        prompt=STYLE_PROMPT,
        negative=STYLE_NEGATIVE,
        seed=42,
        title_prefix="Batch HOI4 LoRA",
        denoise=SOURCE_STYLE_DENOISE,
        prompt_node_title="Editable batch prompt — applies independently to each input image",
        sampler_name="euler",
        steps=DEFAULT_STEPS,
    )
    nodes.extend(style_nodes)
    output_nodes, final_preview = _background_and_outputs(final_image=styled, x=7000)
    nodes.extend(output_nodes)
    nodes.append(_note(805, "🖼️ Batch mode", BATCH_NOTE, "00 Welcome & setup", (100, 2560), size=(860, 600)))
    nodes.extend(
        _comparison_row(
            group="04 HOI4 LoRA styling",
            x=6800,
            y=900,
            esrgan=Link(8),
            restored=Link(32),
            finals=[final_preview],
            final_label="batch",
        )
    )
    return Graph(
        workflow_id="hoi4_portrait_batch",
        description="Batch portrait workflow: load a folder of source images, process each image, run one shared FLUX.2 Klein 9B sampler, and save PNG plus HOI4-ready DDS outputs.",
        kind="batch_image_to_image",
        nodes=nodes,
        groups=_groups(has_source=True, has_restoration=True, candidate_count=1, background_x=7000),
        metadata={
            "restoration_order": ["RealESRGAN_x2plus", "optional_adonis_base", "optional_adonis_post"],
            "flux_restoration_default": True,
            "batch_input_folder": "input/hoi4_portraits_batch",
            "batch_sampler_count": 1,
            "output_folders": ["output/1024x1365", "output/156x210", "output/156x210/dds"],
            "background_order": "after_final_lora_styled_decode",
            "comparison_row": ["esrgan", "flux_restoration", "batch_final"],
        },
    )


def _api_json(graph: Graph) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for node in graph.nodes:
        if node.class_type == "Note":
            # Notes are frontend-only cards; they are not ComfyUI node classes.
            continue
        inputs: dict[str, Any] = {}
        for name, value in node.inputs.items():
            inputs[name] = [str(value.node_id), value.slot] if isinstance(value, Link) else value
        data[str(node.node_id)] = {"class_type": node.class_type, "inputs": inputs, "_meta": {"title": node.title}}
    return data


def _layout_positions(graph: Graph) -> dict[int, list[int]]:
    """Pack each visual group into aligned columns without moving branches sideways.

    Nodes are authored with semantic columns.  This pass normalizes small
    column offsets (for example, 4,040 vs. 4,050) and gives every column the
    same horizontal clearance.  Within a column, cards are stacked in reading
    order with the same vertical clearance.  It never resolves a collision by
    moving a node into a different column, which keeps repeated candidates
    visually symmetrical.
    """

    positions = {node.node_id: [node.pos[0], node.pos[1]] for node in graph.nodes}
    horizontal_gap = UI_LAYOUT_PADDING + 20
    lane_tolerance = 120
    for group in graph.groups:
        grouped = [node for node in graph.nodes if node.group == group.title]
        if len(grouped) < 2:
            continue

        lanes: list[list[Node]] = []
        lane_centers: list[float] = []
        for node in sorted(grouped, key=lambda item: (item.pos[0], item.pos[1], item.node_id)):
            for index, center in enumerate(lane_centers):
                if abs(node.pos[0] - center) <= lane_tolerance:
                    lanes[index].append(node)
                    lane_centers[index] = sum(item.pos[0] for item in lanes[index]) / len(lanes[index])
                    break
            else:
                lanes.append([node])
                lane_centers.append(float(node.pos[0]))

        lane_x = min(node.pos[0] for node in grouped)
        for lane in lanes:
            lane_width = max(node.size[0] for node in lane)
            for node in lane:
                positions[node.node_id][0] = lane_x
            lane_y = None
            for node in sorted(lane, key=lambda item: (item.pos[1], item.node_id)):
                desired_y = node.pos[1]
                if lane_y is not None:
                    desired_y = max(desired_y, lane_y)
                positions[node.node_id][1] = desired_y
                lane_y = desired_y + node.size[1] + UI_LAYOUT_PADDING
            lane_x += lane_width + horizontal_gap

    # Pack the colored frames from left to right after the internal lanes have
    # been normalized.  The hand-authored graph used to rely on guessed frame
    # widths; a larger PreviewImage could therefore push into the next frame
    # even when the node rectangles themselves were technically disjoint.
    # Recomputing the frame origins from the actual node extents gives every
    # stage the same 40 px inner margin and one explicit inter-frame gutter.
    frame_cursor = 40
    for group in graph.groups:
        grouped = [node for node in graph.nodes if node.group == group.title]
        if not grouped:
            continue
        left = min(positions[node.node_id][0] for node in grouped)
        right = max(positions[node.node_id][0] + node.size[0] for node in grouped)
        shift = frame_cursor + 40 - left
        for node in grouped:
            positions[node.node_id][0] += shift
        frame_cursor += (right - left) + 80 + GROUP_LAYOUT_GAP
    return positions


def _ui_json(graph: Graph) -> dict[str, Any]:
    viewport = {"scale": 0.45, "offset": [120, 120]}

    node_by_id = {node.node_id: node for node in graph.nodes}
    layout_positions = _layout_positions(graph)
    link_id = 1
    links: list[list[Any]] = []
    target_links: dict[tuple[int, str], int] = {}
    output_links: dict[tuple[int, int], list[int]] = {}
    for node in graph.nodes:
        for input_name, value in node.inputs.items():
            if not isinstance(value, Link):
                continue
            source = node_by_id[value.node_id]
            connection_type = source.output_types[value.slot]
            links.append([link_id, value.node_id, value.slot, node.node_id, list(node.inputs).index(input_name), connection_type])
            target_links[(node.node_id, input_name)] = link_id
            output_links.setdefault((value.node_id, value.slot), []).append(link_id)
            link_id += 1

    tightened_groups: list[Group] = []
    for group in graph.groups:
        grouped_nodes = [node for node in graph.nodes if node.group == group.title]
        if not grouped_nodes:
            tightened_groups.append(group)
            continue
        group_x = min(layout_positions[node.node_id][0] for node in grouped_nodes) - 40
        group_y = min(layout_positions[node.node_id][1] for node in grouped_nodes) - 40
        right = max(layout_positions[node.node_id][0] + node.size[0] for node in grouped_nodes) + 40
        bottom = max(layout_positions[node.node_id][1] + node.size[1] for node in grouped_nodes) + 40
        tightened_groups.append(
            Group(group.title, (group_x, group_y, right - group_x, bottom - group_y), group.color)
        )

    colors = {group.title: group.color for group in tightened_groups}
    ui_nodes: list[dict[str, Any]] = []
    for order, node in enumerate(graph.nodes):
        inputs = []
        for name in node.inputs:
            item: dict[str, Any] = {"name": name, "type": node.input_types[name], "link": target_links.get((node.node_id, name))}
            if not isinstance(node.inputs[name], Link):
                item["widget"] = {"name": name}
            inputs.append(item)
        outputs = []
        for slot, name in enumerate(node.outputs):
            outgoing = output_links.get((node.node_id, slot))
            outputs.append({"name": name, "type": node.output_types[slot], "links": outgoing or None})
        properties: dict[str, Any] = {
            "Node name for S&R": node.class_type,
            "hoi4_group": node.group,
        }
        if node.models:
            properties["models"] = node.models
        is_feature_toggle = (
            node.title.startswith("Toggle FLUX restoration")
            or node.title.startswith("Toggle replacement background")
            or node.title.startswith("Toggle face processing")
        )
        node_color = "#b91c1c" if is_feature_toggle else colors.get(node.group, "#3f789e")
        node_background = "#7f1d1d" if is_feature_toggle else colors.get(node.group, "#3f789e")
        ui_nodes.append(
            {
                "id": node.node_id,
                "type": node.class_type,
                "title": node.title,
                "pos": layout_positions[node.node_id],
                "size": list(node.size),
                "color": node_color,
                "bgcolor": node_background,
                "flags": {},
                "order": order,
                "mode": 0,
                "inputs": inputs,
                "outputs": outputs,
                "properties": properties,
                "widgets_values": node.widgets,
            }
        )
    flat_ui = {
        "last_node_id": max(node.node_id for node in graph.nodes),
        "last_link_id": link_id - 1,
        "nodes": ui_nodes,
        "links": links,
        "groups": [
            {"title": group.title, "bounding": list(group.bounding), "color": group.color, "font_size": 24, "flags": {}}
            for group in tightened_groups
        ],
        "config": {},
        "extra": {
            "ds": viewport,
            "workflow_id": graph.workflow_id,
            "description": graph.description,
            "workflow_kind": graph.kind,
            "project": "comfyui-hoi4-portraits",
            "graph_version": WORKFLOW_SCHEMA_VERSION,
            "base_model": BASE_MODEL,
            "style_lora": STYLE_LORA,
            "master_size": [CANVAS_WIDTH, CANVAS_HEIGHT],
            "game_size": [GAME_WIDTH, GAME_HEIGHT],
            "game_resize_policy": "lanczos_center_crop",
            "core_nodes_only": not any(
                node.class_type in {"AdaptivePortraitCrop", "PortraitIdentityMask"} for node in graph.nodes
            ),
            "comfy_cloud_ready": True,
            **graph.metadata,
        },
        "version": 0.4,
    }
    # Keep every workflow stage visible on the main canvas. Colored groups are
    # organizational frames only; native subgraphs can be mistaken for missing
    # node packs by some hosted ComfyUI builds.
    flat_ui["extra"]["editor_layout"] = "flat_grouped_canvas"
    return flat_ui


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_all(root: Path = ROOT) -> list[dict[str, Any]]:
    workflow_dir = root / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    graphs = [build_source(), build_text_to_image(), build_processing(), build_batch()]
    for stale in workflow_dir.glob("*.json"):
        stale.unlink()
    manifest_items: list[dict[str, Any]] = []
    for graph in graphs:
        ui_path = workflow_dir / f"{graph.workflow_id}.json"
        api_path = workflow_dir / f"{graph.workflow_id}.api.json"
        _write_json(ui_path, _ui_json(graph))
        _write_json(api_path, _api_json(graph))
        manifest_items.append(
            {
                "workflow_id": graph.workflow_id,
                "description": graph.description,
                "workflow_json": ui_path.relative_to(root).as_posix(),
                "api_json": api_path.relative_to(root).as_posix(),
                "node_count": len(graph.nodes),
                "core_nodes_only": not any(
                    node.class_type in {"AdaptivePortraitCrop", "PortraitIdentityMask"}
                    for node in graph.nodes
                ),
            }
        )
    manifest = {
        "schema_version": WORKFLOW_SCHEMA_VERSION,
        "base_model": BASE_MODEL,
        "model_variants": {"full": BASE_MODEL, "fp8": FP8_MODEL, "gguf": GGUF_MODEL},
        "text_encoder": TEXT_ENCODER,
        "vae": VAE_MODEL,
        "style_lora": STYLE_LORA,
        "master_size": [CANVAS_WIDTH, CANVAS_HEIGHT],
        "game_size": [GAME_WIDTH, GAME_HEIGHT],
        "workflows": manifest_items,
    }
    _write_json(workflow_dir / "manifest.json", manifest)
    return manifest_items


def main() -> int:
    items = build_all()
    print(json.dumps({"status": "PASS", "workflows": items}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
