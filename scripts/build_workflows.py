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

BASE_MODEL = "flux-2-klein-base-9b-fp8.safetensors"
TEXT_ENCODER = "qwen_3_8b_fp8mixed.safetensors"
VAE_MODEL = "flux2-vae.safetensors"
STYLE_LORA = "hoi4_portrait_flux2_klein9b_lora_000002250.safetensors"
RESTORATION_LOKR = "adonis_base.safetensors"
DX_CONSISTENCY_LORA = "Flux2-Klein-9B-consistency-V2.safetensors"
LCS_CONSISTENCY_LORA = "f2k_9B_lcs_consist_20260415.safetensors"
SAMEFACE_LORA = "Flux2Klein9BSameFaceR64.safetensors"
REFCONTROL_LINEART_LORA = "flux2_klein_9b_refcontrol_lineart.safetensors"
PULID_MODEL = "pulid_flux2_klein_v2.safetensors"
STYLE_LORA_STRENGTH = 1.0
SOURCE_STYLE_DENOISE = 1.0
DEFAULT_STEPS = 6
DEFAULT_CFG = 1.0
DEFAULT_GUIDANCE = 1.0
CANVAS_WIDTH = 1024
CANVAS_HEIGHT = 1365
GAME_WIDTH = 156
GAME_HEIGHT = 210
WORKFLOW_SCHEMA_VERSION = "2.6.1"
SOURCE_CANDIDATE_COUNT = 3
SOURCE_STYLE_SEEDS = (42, 43, 44)
SOURCE_CANDIDATE_SAMPLING = (("euler", 6), ("res_2s", 4), ("res_2m", 8))
IDENTITY_LOCK_PRESET = "MID_LOCK"
IDENTITY_HARD_DOUBLE = "0-7:mid_img=0.55"
IDENTITY_HARD_SINGLE = (
    "0:mid_img=0.22; 1:mid_img=0.24; 3:mid_img=0.28; 4:mid_img=0.22; "
    "6:mid_img=0.26; 7:mid_img=0.27; 8:mid_img=0.25; 10:mid_img=0.27; 13:mid_img=0.27"
)
ESRGAN_MODEL = "RealESRGAN_x2plus.pth"
BACKGROUND_MODEL = "birefnet.safetensors"
FACE_DETECTION_MODEL = "mediapipe_face_fp32.safetensors"
YUNET_MODEL = "face_detection_yunet_2023mar.onnx"

MODEL_URLS = {
    BASE_MODEL: "https://huggingface.co/black-forest-labs/FLUX.2-klein-base-9B-fp8/resolve/9ecf2143d71542449960c5584340269c6d401449/flux-2-klein-base-9b-fp8.safetensors",
    TEXT_ENCODER: "https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/23fbc8aa8b621f29f2249cd1bd9c47e5d0eebd83/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors",
    VAE_MODEL: "https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/23fbc8aa8b621f29f2249cd1bd9c47e5d0eebd83/split_files/vae/flux2-vae.safetensors",
    STYLE_LORA: "https://huggingface.co/Hoops-McCann/hoi4-portraits-flux2-klein-9b-lora/resolve/4902bba7fd76337dabc4a6273d3f6edb3dafc2f5/hoi4_portrait_flux2_klein9b_lora_000002250.safetensors",
    RESTORATION_LOKR: "https://huggingface.co/n8te0/adonis_flux2klein/resolve/515ecf66717d14309a055811b3d478cdfa59bbda/adonis_base.safetensors",
    DX_CONSISTENCY_LORA: "https://huggingface.co/dx8152/Flux2-Klein-9B-Consistency/resolve/8df0c7338cf68cfcd89ca7e461fe679905634607/Flux2-Klein-9B-consistency-V2.safetensors",
    LCS_CONSISTENCY_LORA: "https://huggingface.co/lrzjason/Consistance_Edit_Lora/resolve/825b73f9952186f807acb44f05dec4ec5044f394/f2k_9B_lcs_consist_20260415.safetensors",
    SAMEFACE_LORA: "https://huggingface.co/rphmeier/Flux2Klein9B-SameFaceLora/resolve/94ee6271f4d37fbcd6689b6469341aba6170d0b9/Flux2Klein9BSameFaceR64.safetensors",
    REFCONTROL_LINEART_LORA: "https://huggingface.co/thedeoxen/refcontrol-FLUX.2-klein-9B-reference-lineart-lora/resolve/140f26de5b6006f6d455ecee417be774a1c054e8/flux2_klein_9b_refcontrol_lineart.safetensors",
    PULID_MODEL: "https://huggingface.co/Fayens/Pulid-Flux2/resolve/550167db98d7169bfc83f9aa8225bd0da70f2d6b/pulid_flux2_klein_v2.safetensors",
    ESRGAN_MODEL: "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
    BACKGROUND_MODEL: "https://huggingface.co/Comfy-Org/BiRefNet/resolve/8fdc9d315889de96cc0c6269eeecd333e2727889/background_removal/birefnet.safetensors",
    FACE_DETECTION_MODEL: "https://huggingface.co/Comfy-Org/mediapipe/resolve/b98d050e8bf406f14f063bdba697e5b5391bbbf5/detection/mediapipe_face_fp32.safetensors",
    YUNET_MODEL: "https://media.githubusercontent.com/media/opencv/opencv_zoo/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
}

RESTORATION_PROMPT = (
    "uhdmanscale, restore this historical head-and-shoulders portrait conservatively. Repair scratches, fading, compression, blur, and lost fine detail. "
    "Preserve the person's exact identity, facial geometry, expression, hairstyle, clothing, pose, camera angle, and crop. "
    "Keep period-authentic texture. For monochrome or sepia material, restore plausible natural color. Do not stylize."
)
RESTORATION_NEGATIVE = ""
STYLE_PROMPT = (
    "hoi4_portrait, maintain the exact identity, facing direction, and expression of the person, "
    "including every object they are holding or wearing."
)
STYLE_NEGATIVE = ""
TEXT_PROMPT = (
    "hoi4_portrait, an Irish middle-aged man with neatly combed dark hair, "
    "wearing a plain civilian jacket."
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


@dataclass(frozen=True)
class IdentityComparison:
    key: str
    label: str
    method: str


IDENTITY_COMPARISONS = (
    IdentityComparison("native", "Native two-reference baseline", "native"),
    IdentityComparison("feature_mid", "Feature transfer — MID_LOCK", "feature_mid"),
    IdentityComparison("feature_hard", "Feature transfer — HARD_LOCK", "feature_hard"),
    IdentityComparison("dx_consistency", "DX consistency LoRA V2", "dx_consistency"),
    IdentityComparison("lcs_consistency", "LCS consistency LoRA", "lcs_consistency"),
    IdentityComparison("sameface", "SameFace LoRA", "sameface"),
    IdentityComparison("refcontrol_lineart", "RefControl lineart", "refcontrol_lineart"),
    IdentityComparison("pulid", "PuLID Flux2 v2", "pulid"),
    IdentityComparison("composite", "Klein edit composite", "composite"),
)


def _model(name: str, directory: str) -> list[dict[str, str]]:
    return [{"name": name, "url": MODEL_URLS[name], "directory": directory}]


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
            "Load FLUX.2 Klein 9B base",
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
    return nodes


def _source_nodes(*, include_processed_preview: bool = True) -> list[Node]:
    group = "01 Source and ESRGAN"
    nodes = [
        _node(
            5,
            "LoadImage",
            "Load source portrait",
            group,
            (100, 120),
            size=(360, 310),
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
            (520, 300),
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
            (520, 580),
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
            (100, 760),
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
            (100, 920),
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
            (100, 1080),
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
            (520, 850),
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
            (520, 1120),
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
            (520, 1320),
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
            (100, 1480),
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
            (520, 1460),
            size=(267, 46),
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
            (520, 1600),
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
                "Confirm head-and-shoulders processing before FLUX",
                group,
                (100, 1620),
                size=(360, 430),
                inputs={"images": Link(8)},
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
    control_id = 1000 + sampler_id * 10
    control_x = x + 850
    option_x = x + 1140
    sample_x = x + 1430
    return [
        _node(
            control_id,
            "FluxGuidance",
            f"{title_prefix} guidance",
            group,
            (control_x, y),
            size=(260, 100),
            inputs={"conditioning": positive, "guidance": DEFAULT_GUIDANCE},
            input_types={"conditioning": "CONDITIONING", "guidance": "FLOAT"},
            outputs=["CONDITIONING"],
            output_types=["CONDITIONING"],
            widgets=[DEFAULT_GUIDANCE],
        ),
        _node(
            control_id + 1,
            "CFGGuider",
            f"{title_prefix} CFG",
            group,
            (control_x, y + 140),
            size=(260, 160),
            inputs={"model": model, "positive": Link(control_id), "negative": negative, "cfg": DEFAULT_CFG},
            input_types={"model": "MODEL", "positive": "CONDITIONING", "negative": "CONDITIONING", "cfg": "FLOAT"},
            outputs=["GUIDER"],
            output_types=["GUIDER"],
            widgets=[DEFAULT_CFG],
        ),
        _node(
            control_id + 2,
            "RandomNoise",
            f"{title_prefix} seed",
            group,
            (option_x, y),
            size=(260, 100),
            inputs={"noise_seed": seed},
            input_types={"noise_seed": "INT"},
            outputs=["NOISE"],
            output_types=["NOISE"],
            widgets=[seed, seed_mode],
        ),
        _node(
            control_id + 3,
            "KSamplerSelect",
            f"{title_prefix} sampler",
            group,
            (option_x, y + 140),
            size=(260, 100),
            inputs={"sampler_name": sampler_name},
            input_types={"sampler_name": "COMBO"},
            outputs=["SAMPLER"],
            output_types=["SAMPLER"],
            widgets=[sampler_name],
        ),
        _node(
            control_id + 4,
            "Flux2Scheduler",
            f"{title_prefix} steps and resolution",
            group,
            (option_x, y + 280),
            size=(260, 150),
            inputs={"steps": steps, "width": CANVAS_WIDTH, "height": CANVAS_HEIGHT},
            input_types={"steps": "INT", "width": "INT", "height": "INT"},
            outputs=["SIGMAS"],
            output_types=["SIGMAS"],
            widgets=[steps, CANVAS_WIDTH, CANVAS_HEIGHT],
        ),
        _node(
            control_id + 5,
            "SplitSigmasDenoise",
            f"{title_prefix} denoise",
            group,
            (option_x, y + 470),
            size=(260, 100),
            inputs={"sigmas": Link(control_id + 4), "denoise": denoise},
            input_types={"sigmas": "SIGMAS", "denoise": "FLOAT"},
            outputs=["high_sigmas", "low_sigmas"],
            output_types=["SIGMAS", "SIGMAS"],
            widgets=[denoise],
        ),
        _node(
            sampler_id,
            "SamplerCustomAdvanced",
            f"Sample {title_prefix.lower()}",
            group,
            (sample_x, y + 80),
            size=(300, 170),
            inputs={
                "noise": Link(control_id + 2),
                "guider": Link(control_id + 1),
                "sampler": Link(control_id + 3),
                "sigmas": Link(control_id + 5, 1),
                "latent_image": latent,
            },
            input_types={"noise": "NOISE", "guider": "GUIDER", "sampler": "SAMPLER", "sigmas": "SIGMAS", "latent_image": "LATENT"},
            outputs=["output", "denoised_output"],
            output_types=["LATENT", "LATENT"],
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
    seed_mode: str = "randomize",
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
            size=(430, 250),
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
            size=(430, 180),
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
            (x + 500, y + 200),
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
            (x + 500, y + 400),
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
            (x + 1430, y + 290),
            inputs={"samples": Link(i + 10), "vae": Link(3)},
            input_types={"samples": "LATENT", "vae": "VAE"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
        ),
        _node(
            i + 14,
            "ImageScale",
            f"Normalize {title_prefix.lower()} to exact {CANVAS_WIDTH} x {CANVAS_HEIGHT}",
            group,
            (x + 1430, y + 430),
            size=(340, 150),
            inputs={
                "image": Link(i + 11),
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
            i + 15,
            "PreviewImage",
            f"Preview {title_prefix.lower()} result",
            group,
            (x + 1430, y + 620),
            size=(300, 220),
            inputs={"images": Link(i + 14)},
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
                    (x + 500, y + 600),
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
                    (x + 900, y + 600),
                    inputs={"pixels": reference_images[1], "vae": Link(3)},
                    input_types={"pixels": "IMAGE", "vae": "VAE"},
                    outputs=["LATENT"],
                    output_types=["LATENT"],
                ),
            ]
        )
    return nodes, Link(i + 14)


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
            (x + 1430, 410),
            inputs={"samples": Link(27), "vae": Link(3)},
            input_types={"samples": "LATENT", "vae": "VAE"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
        ),
        _node(
            30,
            "ImageScale",
            f"Normalize final portrait to exact {CANVAS_WIDTH} x {CANVAS_HEIGHT}",
            group,
            (x + 1430, 550),
            size=(340, 150),
            inputs={"image": Link(28), "upscale_method": "lanczos", "width": CANVAS_WIDTH, "height": CANVAS_HEIGHT, "crop": "center"},
            input_types={"image": "IMAGE", "upscale_method": "COMBO", "width": "INT", "height": "INT", "crop": "COMBO"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=["lanczos", CANVAS_WIDTH, CANVAS_HEIGHT, "center"],
        ),
        _node(
            29,
            "PreviewImage",
            "Preview generated portrait before background replacement",
            group,
            (x + 1430, 740),
            size=(300, 220),
            inputs={"images": Link(30)},
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
            seed_mode="randomize",
            sampler_name="euler",
            steps=DEFAULT_STEPS,
            denoise=1.0,
            title_prefix="HOI4 portrait",
        )
    )
    return nodes, Link(30)


def _background_and_outputs(*, final_image: Link, x: int = 5200) -> list[Node]:
    background_group = "05 Optional background - after generation"
    output_group = "06 Preview and save"
    return [
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
            70,
            "PreviewImage",
            "Preview final portrait",
            output_group,
            (x + 1380, 120),
            size=(420, 420),
            inputs={"images": Link(66)},
            input_types={"images": "IMAGE"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
        ),
        _node(
            71,
            "SaveImage",
            f"Save {CANVAS_WIDTH} x {CANVAS_HEIGHT} master PNG",
            output_group,
            (x + 1880, 120),
            inputs={"images": Link(66), "filename_prefix": "hoi4_portraits/master"},
            input_types={"images": "IMAGE", "filename_prefix": "STRING"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=["hoi4_portraits/master"],
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
            inputs={"images": Link(72), "filename_prefix": "hoi4_portraits/portrait_156x210"},
            input_types={"images": "IMAGE", "filename_prefix": "STRING"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=["hoi4_portraits/portrait_156x210"],
        ),
    ]


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
        row_y = 760 + (index - 1) * 760
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
                    (x + 800, row_y - 50),
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
                    (x + 800, row_y + 220),
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
                    inputs={"images": Link(branch + 2), "filename_prefix": f"{prefix}_master"},
                    input_types={"images": "IMAGE", "filename_prefix": "STRING"},
                    outputs=["IMAGE"],
                    output_types=["IMAGE"],
                    widgets=[f"{prefix}_master"],
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
                    inputs={"images": Link(branch + 5), "filename_prefix": f"{prefix}_portrait_156x210"},
                    input_types={"images": "IMAGE", "filename_prefix": "STRING"},
                    outputs=["IMAGE"],
                    output_types=["IMAGE"],
                    widgets=[f"{prefix}_portrait_156x210"],
                ),
            ]
        )
    return nodes


def _processing_outputs(*, processed_image: Link) -> list[Node]:
    output_group = "04 Processed portrait output"
    return [
        _node(
            70,
            "PreviewImage",
            "Preview processed portrait",
            output_group,
            (3500, 120),
            size=(420, 420),
            inputs={"images": processed_image},
            input_types={"images": "IMAGE"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
        ),
        _node(
            71,
            "SaveImage",
            f"Save {CANVAS_WIDTH} x {CANVAS_HEIGHT} processed PNG",
            output_group,
            (4000, 120),
            inputs={"images": processed_image, "filename_prefix": "hoi4_portraits/processed_master"},
            input_types={"images": "IMAGE", "filename_prefix": "STRING"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=["hoi4_portraits/processed_master"],
        ),
        _node(
            72,
            "ImageScale",
            "Resize to HOI4 156 x 210",
            output_group,
            (4000, 320),
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
            (4000, 540),
            inputs={"images": Link(72), "filename_prefix": "hoi4_portraits/processed_156x210"},
            input_types={"images": "IMAGE", "filename_prefix": "STRING"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=["hoi4_portraits/processed_156x210"],
        ),
    ]


def _groups(*, has_source: bool, has_restoration: bool, candidate_count: int = 1) -> list[Group]:
    groups: list[Group] = []
    if has_source:
        groups.append(Group("01 Source and ESRGAN", (40, 40, 930, 2150), "#557a46"))
    groups.append(Group("02 FLUX.2 Klein 9B models", (1040, 40, 430, 980), "#3f789e"))
    if has_restoration:
        groups.append(Group("03 Optional FLUX.2 restoration", (1500, 40, 1800, 980), "#8b6f47"))
        style_height = 2700 if candidate_count > 1 else 980
        groups.append(Group("04 HOI4 LoRA styling", (3400, 40, 1800, style_height), "#7a568e"))
    else:
        groups.append(Group("04 HOI4 LoRA styling", (1500, 40, 1800, 980), "#7a568e"))
    background_x = 5650 if has_restoration else 3600
    output_height = 3040 if candidate_count > 1 else 720
    groups.append(Group("05 Optional background - after generation", (background_x - 80, 40, 1300, output_height), "#8d5b5b"))
    groups.append(Group("06 Preview and save", (background_x + 1300, 40, 1100, output_height), "#596b82"))
    return groups


def _processing_groups() -> list[Group]:
    return [
        Group("01 Source and ESRGAN", (40, 40, 930, 2150), "#557a46"),
        Group("02 FLUX.2 Klein 9B models", (1040, 40, 430, 980), "#3f789e"),
        Group("03 Optional FLUX.2 restoration", (1500, 40, 1800, 980), "#8b6f47"),
        Group("04 Processed portrait output", (3400, 40, 1100, 720), "#596b82"),
    ]


def _feature_transfer_node(*, preset: str, with_mask: bool) -> list[Node]:
    effective_preset = "custom" if with_mask else preset
    similarity_floor = 0.04 if preset == "HARD_LOCK" else 0.2
    softmax_temperature = 0.025 if preset == "HARD_LOCK" else 0.07
    inputs: dict[str, Any] = {
        "model": Link(4),
        "preset": effective_preset,
        "enabled": True,
        "reference_index": 0,
        "reference_indices": "all",
        "similarity_floor": similarity_floor,
        "softmax_temperature": softmax_temperature,
        "mask_threshold": 0.35 if with_mask else 1.0,
        "double_blocks": IDENTITY_HARD_DOUBLE,
        "single_blocks": IDENTITY_HARD_SINGLE,
        "debug": False,
        "mask_behavior": "focus_only",
    }
    input_types = {
        "model": "MODEL",
        "preset": "COMBO",
        "enabled": "BOOLEAN",
        "reference_index": "INT",
        "reference_indices": "STRING",
        "similarity_floor": "FLOAT",
        "softmax_temperature": "FLOAT",
        "mask_threshold": "FLOAT",
        "double_blocks": "STRING",
        "single_blocks": "STRING",
        "debug": "BOOLEAN",
        "mask_behavior": "COMBO",
    }
    nodes: list[Node] = []
    if with_mask:
        nodes.append(
            _node(
                192,
                "PortraitIdentityMask",
                "Face-and-head mask for reference feature transfer",
                "02 FLUX.2 Klein 9B models",
                (1100, 1480),
                size=(340, 120),
                inputs={"image": Link(18)},
                input_types={"image": "IMAGE"},
                outputs=["identity_mask"],
                output_types=["MASK"],
            )
        )
        inputs.update({"subject_mask_1": Link(192), "subject_mask_2": Link(192)})
        input_types.update({"subject_mask_1": "MASK", "subject_mask_2": "MASK"})
    nodes.insert(
        0,
        _node(
            190,
            "IdentityFeatureTransferFinal",
            f"Source identity feature transfer — {preset}",
            "02 FLUX.2 Klein 9B models",
            (1100, 1000),
            size=(340, 430),
            inputs=inputs,
            input_types=input_types,
            outputs=["MODEL"],
            output_types=["MODEL"],
            widgets=[
                effective_preset,
                True,
                0,
                "all",
                similarity_floor,
                softmax_temperature,
                0.35 if with_mask else 1.0,
                IDENTITY_HARD_DOUBLE,
                IDENTITY_HARD_SINGLE,
                False,
                "focus_only",
            ],
        ),
    )
    return nodes


def _identity_comparison_setup(
    method: str,
) -> tuple[list[Node], Link, tuple[Link, Link] | None, bool, str]:
    if method == "source":
        return [], Link(4), None, False, STYLE_PROMPT
    if method == "native":
        return [], Link(4), (Link(18), Link(32)), False, STYLE_PROMPT
    if method in {"feature_mid", "feature_hard"}:
        preset = "MID_LOCK" if method == "feature_mid" else "HARD_LOCK"
        return _feature_transfer_node(preset=preset, with_mask=True), Link(190), (Link(18), Link(32)), False, STYLE_PROMPT
    consistency = {
        "dx_consistency": (DX_CONSISTENCY_LORA, 0.4, "DX consistency LoRA V2"),
        "lcs_consistency": (LCS_CONSISTENCY_LORA, 0.5, "LCS consistency LoRA"),
        "sameface": (SAMEFACE_LORA, 1.0, "SameFace identity LoRA"),
        "refcontrol_lineart": (REFCONTROL_LINEART_LORA, 0.8, "RefControl lineart LoRA"),
    }
    if method in consistency:
        filename, strength, title = consistency[method]
        nodes = [
            _node(
                190,
                "LoraLoaderModelOnly",
                f"Apply {title} — strength editable here",
                "02 FLUX.2 Klein 9B models",
                (1100, 1000),
                size=(340, 130),
                inputs={"model": Link(4), "lora_name": filename, "strength_model": strength},
                input_types={"model": "MODEL", "lora_name": "COMBO", "strength_model": "FLOAT"},
                outputs=["MODEL"],
                output_types=["MODEL"],
                widgets=[filename, strength],
                models=_model(filename, "loras"),
            )
        ]
        references = (Link(18), Link(32))
        prompt = STYLE_PROMPT
        if method == "refcontrol_lineart":
            nodes.append(
                _node(
                    192,
                    "Canny",
                    "Create first RefControl lineart reference",
                    "02 FLUX.2 Klein 9B models",
                    (1100, 1180),
                    size=(340, 150),
                    inputs={"image": Link(18), "low_threshold": 0.4, "high_threshold": 0.8},
                    input_types={"image": "IMAGE", "low_threshold": "FLOAT", "high_threshold": "FLOAT"},
                    outputs=["IMAGE"],
                    output_types=["IMAGE"],
                    widgets=[0.4, 0.8],
                )
            )
            references = (Link(192), Link(32))
            prompt = STYLE_PROMPT.replace("hoi4_portrait,", "hoi4_portrait, refcontrol,", 1)
        return nodes, Link(190), references, False, prompt
    if method == "pulid":
        nodes = [
            _node(
                190,
                "PuLIDModelLoader",
                "Load PuLID Flux2 Klein v2",
                "02 FLUX.2 Klein 9B models",
                (1100, 1000),
                size=(340, 120),
                inputs={"pulid_file": PULID_MODEL},
                input_types={"pulid_file": "COMBO"},
                outputs=["PULID_MODEL"],
                output_types=["PULID_MODEL"],
                widgets=[PULID_MODEL],
                models=_model(PULID_MODEL, "pulid"),
            ),
            _node(
                192,
                "PuLIDEVACLIPLoader",
                "Load PuLID EVA-CLIP",
                "02 FLUX.2 Klein 9B models",
                (1100, 1170),
                size=(340, 100),
                outputs=["EVA_CLIP"],
                output_types=["EVA_CLIP"],
            ),
            _node(
                193,
                "PuLIDInsightFaceLoader",
                "Load PuLID InsightFace on CUDA",
                "02 FLUX.2 Klein 9B models",
                (1100, 1320),
                size=(340, 110),
                inputs={"provider": "CUDA"},
                input_types={"provider": "COMBO"},
                outputs=["INSIGHTFACE"],
                output_types=["INSIGHTFACE"],
                widgets=["CUDA"],
            ),
            _node(
                194,
                "ApplyPuLIDFlux2",
                "Apply PuLID identity — strength editable here",
                "02 FLUX.2 Klein 9B models",
                (1100, 1480),
                size=(340, 330),
                inputs={
                    "model": Link(4),
                    "pulid_model": Link(190),
                    "strength": 1.4,
                    "eva_clip": Link(192),
                    "face_analysis": Link(193),
                    "image": Link(18),
                    "face_index": 0,
                    "debug_mode": False,
                },
                input_types={
                    "model": "MODEL",
                    "pulid_model": "PULID_MODEL",
                    "strength": "FLOAT",
                    "eva_clip": "EVA_CLIP",
                    "face_analysis": "INSIGHTFACE",
                    "image": "IMAGE",
                    "face_index": "INT",
                    "debug_mode": "BOOLEAN",
                },
                outputs=["MODEL"],
                output_types=["MODEL"],
                widgets=[1.4, 0, False],
            ),
        ]
        return nodes, Link(194), (Link(18), Link(32)), False, STYLE_PROMPT
    if method == "composite":
        return [], Link(4), (Link(18), Link(32)), False, STYLE_PROMPT
    raise ValueError(f"unsupported identity comparison method: {method}")


def _klein_composite_node(*, node_id: int, generated: Link, y: int, candidate: int) -> Node:
    return _node(
        node_id,
        "KleinEditComposite",
        f"Composite candidate {candidate} identity details",
        "04 HOI4 LoRA styling",
        (5235, y),
        size=(340, 620),
        inputs={
            "generated_image": generated,
            "original_image": Link(18),
            "delta_e_threshold": -1.0,
            "flow_quality": "medium",
            "use_occlusion": False,
            "occlusion_threshold": -1.0,
            "noise_removal_pct": 0.3,
            "close_radius_pct": 0.5,
            "fill_holes": False,
            "fill_borders": True,
            "max_islands": 0,
            "grow_mask_pct": 0.0,
            "feather_pct": 2.0,
            "color_match_blend": 0.0,
            "poisson_blend_edges": False,
        },
        input_types={
            "generated_image": "IMAGE",
            "original_image": "IMAGE",
            "delta_e_threshold": "FLOAT",
            "flow_quality": "COMBO",
            "use_occlusion": "BOOLEAN",
            "occlusion_threshold": "FLOAT",
            "noise_removal_pct": "FLOAT",
            "close_radius_pct": "FLOAT",
            "fill_holes": "BOOLEAN",
            "fill_borders": "BOOLEAN",
            "max_islands": "INT",
            "grow_mask_pct": "FLOAT",
            "feather_pct": "FLOAT",
            "color_match_blend": "FLOAT",
            "poisson_blend_edges": "BOOLEAN",
        },
        outputs=["IMAGE", "MASK", "STRING", "IMAGE"],
        output_types=["IMAGE", "MASK", "STRING", "IMAGE"],
        widgets=[-1.0, "medium", False, -1.0, 0.3, 0.5, False, True, 0, 0.0, 2.0, 0.0, False],
    )


def build_source(*, comparison: IdentityComparison | None = None) -> Graph:
    method = comparison.method if comparison else "source"
    nodes = _source_nodes(include_processed_preview=False) + _model_nodes()
    identity_nodes, style_model, reference_images, double_reference, style_prompt = _identity_comparison_setup(method)
    nodes.extend(identity_nodes)
    restoration_nodes, restored = _edit_stage(
        id_start=20,
        group="03 Optional FLUX.2 restoration",
        x=1540,
        image=Link(8),
        model=Link(191),
        prompt=RESTORATION_PROMPT,
        negative=RESTORATION_NEGATIVE,
        seed=17,
        title_prefix="Conservative restoration",
        seed_mode="fixed",
    )
    nodes.extend(restoration_nodes)
    nodes.append(
        _node(
            32,
            "ComfySwitchNode",
            "Toggle FLUX restoration (on: ESRGAN then FLUX; off: keep ESRGAN output)",
            "03 Optional FLUX.2 restoration",
            (2040, 680),
            size=(330, 150),
            inputs={"switch": True, "on_false": Link(8), "on_true": restored},
            input_types={"switch": "BOOLEAN", "on_false": "IMAGE", "on_true": "IMAGE"},
            outputs=["output"],
            output_types=["IMAGE"],
            widgets=[True],
        )
    )
    restoration_preview = next(node for node in nodes if node.node_id == 35)
    restoration_preview.title = "Preview selected processed portrait"
    restoration_preview.inputs["images"] = Link(32)
    styled_images: list[Link] = []
    if len(SOURCE_STYLE_SEEDS) != len(SOURCE_CANDIDATE_SAMPLING):
        raise ValueError("source seeds and sampling presets must have the same length")
    for index, (seed, (sampler_name, steps)) in enumerate(
        zip(SOURCE_STYLE_SEEDS, SOURCE_CANDIDATE_SAMPLING), start=1
    ):
        style_nodes, styled = _edit_stage(
            id_start=40 + (index - 1) * 20,
            group="04 HOI4 LoRA styling",
            x=3440,
            y=80 + (index - 1) * 900,
            image=Link(32),
            model=style_model,
            prompt=style_prompt,
            negative=STYLE_NEGATIVE,
            seed=seed,
            title_prefix=f"Candidate {index} identity LoRA",
            denoise=SOURCE_STYLE_DENOISE,
            prompt_node_title=f"Editable candidate {index} prompt — edits affect only candidate {index}",
            sampler_name=sampler_name,
            steps=steps,
            double_reference=double_reference,
            reference_images=reference_images,
            start_from_empty=comparison is not None,
        )
        if method == "composite":
            composite_id = 200 + (index - 1) * 10
            composite = _klein_composite_node(
                node_id=composite_id,
                generated=styled,
                y=100 + (index - 1) * 900,
                candidate=index,
            )
            style_nodes.append(composite)
            preview = next(node for node in style_nodes if node.node_id == 55 + (index - 1) * 20)
            preview.title = f"Preview composited candidate {index}"
            preview.inputs["images"] = Link(composite_id)
            styled = Link(composite_id)
        nodes.extend(style_nodes)
        styled_images.append(styled)
    background_x = 5700 if method == "composite" else 5600
    nodes.extend(_background_and_outputs_multi(final_images=styled_images, x=background_x, id_start=120))
    workflow_id = (
        f"hoi4_portrait_flux2_klein_9b_source_identity_test_{comparison.key}"
        if comparison
        else "hoi4_portrait_flux2_klein_9b_source"
    )
    identity_label = comparison.label if comparison else "Direct source reference"
    groups = _groups(has_source=True, has_restoration=True, candidate_count=SOURCE_CANDIDATE_COUNT)
    if method == "composite":
        groups = [
            Group(group.title, (5670, *group.bounding[1:]), group.color)
            if group.title == "05 Optional background - after generation"
            else group
            for group in groups
        ]
    return Graph(
        workflow_id=workflow_id,
        description=(
            f"Source portrait workflow using {identity_label}: RealESRGAN first, optional FLUX.2 Klein 9B restoration once, then three independent HOI4 LoRA portrait candidates."
            if comparison
            else "Source portrait workflow: RealESRGAN first, optional FLUX.2 Klein 9B restoration once, then three independent HOI4 LoRA portrait candidates from the processed source reference."
        ),
        kind="image_to_image",
        nodes=nodes,
        groups=groups,
        metadata={
            "restoration_order": ["RealESRGAN_x2plus", "optional_flux2_klein_9b"],
            "flux_restoration_default": True,
            "face_processing_default": True,
            "face_processing_bypass": "whole_composition_center_crop_then_esrgan",
            "candidate_count": SOURCE_CANDIDATE_COUNT,
            "candidate_seed_count": SOURCE_CANDIDATE_COUNT,
            "background_candidate_count": SOURCE_CANDIDATE_COUNT,
            "source_crop": "toggleable_adaptive_head_and_shoulders_zoom_0.90_adjustable_headwear_before_esrgan",
            "pose_preservation": "encoded_source_latent_is_sampler_start",
            "identity_preservation": method,
            "identity_comparison": comparison is not None,
            "identity_comparison_label": identity_label,
            "generation_start": "empty_edit_latent" if comparison else "encoded_processed_source",
            "background_order": "after_final_lora_styled_decode",
        },
    )


def build_processing() -> Graph:
    nodes = _source_nodes() + _model_nodes(include_lora=False)
    restoration_nodes, restored = _edit_stage(
        id_start=20,
        group="03 Optional FLUX.2 restoration",
        x=1540,
        image=Link(8),
        model=Link(191),
        prompt=RESTORATION_PROMPT,
        negative=RESTORATION_NEGATIVE,
        seed=17,
        title_prefix="Conservative restoration",
        seed_mode="fixed",
    )
    nodes.extend(restoration_nodes)
    nodes.append(
        _node(
            32,
            "ComfySwitchNode",
            "Toggle FLUX restoration (on: ESRGAN then FLUX; off: keep ESRGAN output)",
            "03 Optional FLUX.2 restoration",
            (2040, 680),
            size=(330, 150),
            inputs={"switch": True, "on_false": Link(8), "on_true": restored},
            input_types={"switch": "BOOLEAN", "on_false": "IMAGE", "on_true": "IMAGE"},
            outputs=["output"],
            output_types=["IMAGE"],
            widgets=[True],
        )
    )
    restoration_preview = next(node for node in nodes if node.node_id == 35)
    restoration_preview.title = "Preview selected processed portrait"
    restoration_preview.inputs["images"] = Link(32)
    nodes.extend(_processing_outputs(processed_image=Link(32)))
    return Graph(
        workflow_id="hoi4_portrait_processing_only",
        description="Source processing workflow: adjustable crop, RealESRGAN, optional FLUX.2 Klein 9B restoration, and processed portrait outputs without LoRA styling.",
        kind="image_processing",
        nodes=nodes,
        groups=_processing_groups(),
        metadata={
            "style_lora": None,
            "restoration_order": ["RealESRGAN_x2plus", "optional_flux2_klein_9b"],
            "flux_restoration_default": True,
            "face_processing_default": True,
            "face_processing_bypass": "whole_composition_center_crop_then_esrgan",
            "source_crop": "toggleable_adaptive_head_and_shoulders_zoom_0.90_adjustable_headwear_before_esrgan",
            "background_order": "not_applicable_processing_only",
        },
    )


def build_text_to_image() -> Graph:
    nodes = _model_nodes(include_restoration_lokr=False)
    text_nodes, styled = _text_stage(group="04 HOI4 LoRA styling", x=1540)
    nodes.extend(text_nodes)
    nodes.extend(_background_and_outputs(final_image=styled, x=3600))
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
        },
    )


def _api_json(graph: Graph) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for node in graph.nodes:
        inputs: dict[str, Any] = {}
        for name, value in node.inputs.items():
            inputs[name] = [str(value.node_id), value.slot] if isinstance(value, Link) else value
        data[str(node.node_id)] = {"class_type": node.class_type, "inputs": inputs, "_meta": {"title": node.title}}
    return data


def _ui_json(graph: Graph) -> dict[str, Any]:
    viewport = {"scale": 0.45, "offset": [120, 120]}

    node_by_id = {node.node_id: node for node in graph.nodes}
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
        group_x, group_y, _, _ = group.bounding
        right = max(node.pos[0] + node.size[0] for node in grouped_nodes) + 40
        bottom = max(node.pos[1] + node.size[1] for node in grouped_nodes) + 40
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
                "pos": list(node.pos),
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
    graphs = [
        build_source(),
        build_text_to_image(),
        build_processing(),
        *(build_source(comparison=comparison) for comparison in IDENTITY_COMPARISONS),
    ]
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
