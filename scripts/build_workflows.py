#!/usr/bin/env python3
"""Build the public ComfyUI workflows from one deterministic graph source.

The generated ``*.json`` files are editor/save format; the matching
``*.api.json`` files are ready for ``/prompt`` or the Comfy Cloud workflow API.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / "workflows"
SOURCE_LAYOUT_PATH = ROOT / "scripts" / "layouts" / "hoi4_portrait_flux2_klein_9b_source.json"

BASE_MODEL = "flux-2-klein-base-9b-fp8.safetensors"
TEXT_ENCODER = "qwen_3_8b_fp8mixed.safetensors"
VAE_MODEL = "flux2-vae.safetensors"
STYLE_LORA = "hoi4_portraits_flux2_klein_9b_lora_000002500.safetensors"
STYLE_LORA_STRENGTH = 1.0
DEFAULT_STEPS = 8
WORKFLOW_SCHEMA_VERSION = "2.4.1"
SOURCE_CANDIDATE_COUNT = 3
SOURCE_STYLE_SEEDS = (42, 43, 44)
ESRGAN_MODEL = "RealESRGAN_x2plus.pth"
BACKGROUND_MODEL = "birefnet.safetensors"
FACE_DETECTION_MODEL = "mediapipe_face_fp32.safetensors"
YUNET_MODEL = "face_detection_yunet_2023mar.onnx"

MODEL_URLS = {
    BASE_MODEL: "https://huggingface.co/black-forest-labs/FLUX.2-klein-base-9B-fp8/resolve/9ecf2143d71542449960c5584340269c6d401449/flux-2-klein-base-9b-fp8.safetensors",
    TEXT_ENCODER: "https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/23fbc8aa8b621f29f2249cd1bd9c47e5d0eebd83/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors",
    VAE_MODEL: "https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/23fbc8aa8b621f29f2249cd1bd9c47e5d0eebd83/split_files/vae/flux2-vae.safetensors",
    STYLE_LORA: "https://huggingface.co/Hoops-McCann/hoi4-portraits-flux2-klein-9b-lora/resolve/567bdd03a4a93f7506453780285323fa10ed48aa/hoi4_portraits_flux2_klein_9b_lora_000002500.safetensors",
    ESRGAN_MODEL: "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
    BACKGROUND_MODEL: "https://huggingface.co/Comfy-Org/BiRefNet/resolve/8fdc9d315889de96cc0c6269eeecd333e2727889/background_removal/birefnet.safetensors",
    FACE_DETECTION_MODEL: "https://huggingface.co/Comfy-Org/mediapipe/resolve/b98d050e8bf406f14f063bdba697e5b5391bbbf5/detection/mediapipe_face_fp32.safetensors",
    YUNET_MODEL: "https://media.githubusercontent.com/media/opencv/opencv_zoo/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
}

RESTORATION_PROMPT = (
    "Restore this historical head-and-shoulders portrait conservatively. Repair scratches, fading, compression, and lost fine detail. "
    "Preserve the person's exact identity, facial geometry, expression, hairstyle, clothing, pose, camera angle, and crop. "
    "Keep period-authentic texture. Colorize monochrome or sepia material only when the colors can remain plausible. Do not stylize."
)
RESTORATION_NEGATIVE = ""
STYLE_PROMPT = "hoi4_portrait, maintain the identity, facing direction, and expression of the person in the portrait, including any objects they are holding or wearing."
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


def _model_nodes(*, include_lora: bool = True) -> list[Node]:
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
                "Apply the HOI4 FLUX.2 Klein 9B LoRA",
                group,
                (1120, 620),
                inputs={"model": Link(1), "lora_name": STYLE_LORA, "strength_model": STYLE_LORA_STRENGTH},
                input_types={"model": "MODEL", "lora_name": "COMBO", "strength_model": "FLOAT"},
                outputs=["MODEL"],
                output_types=["MODEL"],
                widgets=[STYLE_LORA, STYLE_LORA_STRENGTH],
                models=_model(STYLE_LORA, "loras"),
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
            "Face zoom 0.90 — full head and headwear protected",
            group,
            (520, 580),
            size=(360, 190),
            inputs={
                "image": Link(9),
                "face_bboxes": Link(13, 1),
                "subject_mask": Link(156),
                "zoom": 0.90,
            },
            input_types={
                "image": "IMAGE",
                "face_bboxes": "BOUNDING_BOX",
                "subject_mask": "MASK",
                "zoom": "FLOAT",
            },
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=[0.90],
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
                "output_width": 832,
                "output_height": 1120,
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
            widgets=[832, 1120, 0, "stretch"],
        ),
        _node(
            17,
            "PrimitiveBoolean",
            "Use manual crop for difficult sources",
            group,
            (100, 1330),
            size=(320, 90),
            inputs={"value": False},
            input_types={"value": "BOOLEAN"},
            outputs=["BOOLEAN"],
            output_types=["BOOLEAN"],
            widgets=[False],
        ),
        _node(
            18,
            "ComfySwitchNode",
            "Choose automatic or manual crop",
            group,
            (520, 1120),
            size=(360, 130),
            inputs={"switch": Link(17), "on_false": Link(11), "on_true": Link(16)},
            input_types={"switch": "BOOLEAN", "on_false": "IMAGE", "on_true": "IMAGE"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
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
            inputs={"upscale_model": Link(6), "image": Link(18)},
            input_types={"upscale_model": "UPSCALE_MODEL", "image": "IMAGE"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
        ),
        _node(
            8,
            "ImageScale",
            "Fit portrait to the 832 x 1120 work canvas",
            group,
            (520, 1600),
            size=(360, 150),
            inputs={"image": Link(7), "upscale_method": "lanczos", "width": 832, "height": 1120, "crop": "center"},
            input_types={"image": "IMAGE", "upscale_method": "COMBO", "width": "INT", "height": "INT", "crop": "COMBO"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=["lanczos", 832, 1120, "center"],
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
    y: int = 120,
    prompt_node_title: str | None = None,
) -> tuple[list[Node], Link]:
    i = id_start
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
            "VAEEncode",
            f"Encode {title_prefix.lower()} reference",
            group,
            (x + 500, y),
            inputs={"pixels": image, "vae": Link(3)},
            input_types={"pixels": "IMAGE", "vae": "VAE"},
            outputs=["LATENT"],
            output_types=["LATENT"],
        ),
        _node(
            i + 3,
            "ReferenceLatent",
            "Attach reference to positive conditioning",
            group,
            (x + 500, y + 200),
            inputs={"conditioning": Link(i), "latent": Link(i + 2)},
            input_types={"conditioning": "CONDITIONING", "latent": "LATENT"},
            outputs=["CONDITIONING"],
            output_types=["CONDITIONING"],
        ),
        _node(
            i + 4,
            "ReferenceLatent",
            "Attach reference to negative conditioning",
            group,
            (x + 500, y + 400),
            inputs={"conditioning": Link(i + 1), "latent": Link(i + 2)},
            input_types={"conditioning": "CONDITIONING", "latent": "LATENT"},
            outputs=["CONDITIONING"],
            output_types=["CONDITIONING"],
        ),
        _node(
            i + 6,
            "CFGGuider",
            f"Guide {title_prefix.lower()} pass",
            group,
            (x + 900, y),
            inputs={"model": model, "positive": Link(i + 3), "negative": Link(i + 4), "cfg": 5.0},
            input_types={"model": "MODEL", "positive": "CONDITIONING", "negative": "CONDITIONING", "cfg": "FLOAT"},
            outputs=["GUIDER"],
            output_types=["GUIDER"],
            widgets=[5.0],
        ),
        _node(
            i + 7,
            "RandomNoise",
            f"{title_prefix} seed",
            group,
            (x + 900, y + 200),
            inputs={"noise_seed": seed},
            input_types={"noise_seed": "INT"},
            outputs=["NOISE"],
            output_types=["NOISE"],
            widgets=[seed, "randomize"],
        ),
        _node(
            i + 8,
            "KSamplerSelect",
            "Use Euler sampler",
            group,
            (x + 900, y + 400),
            inputs={"sampler_name": "euler"},
            input_types={"sampler_name": "COMBO"},
            outputs=["SAMPLER"],
            output_types=["SAMPLER"],
            widgets=["euler"],
        ),
        _node(
            i + 9,
            "Flux2Scheduler",
            f"FLUX.2 schedule - {DEFAULT_STEPS} steps",
            group,
            (x + 900, y + 580),
            inputs={"steps": DEFAULT_STEPS, "width": 832, "height": 1120},
            input_types={"steps": "INT", "width": "INT", "height": "INT"},
            outputs=["SIGMAS"],
            output_types=["SIGMAS"],
            widgets=[DEFAULT_STEPS, 832, 1120],
        ),
        _node(
            i + 5,
            "SplitSigmasDenoise",
            "Denoise 1.00 (editable)",
            group,
            (x + 900, y + 720),
            inputs={"sigmas": Link(i + 9), "denoise": 1.0},
            input_types={"sigmas": "SIGMAS", "denoise": "FLOAT"},
            outputs=["high_sigmas", "low_sigmas"],
            output_types=["SIGMAS", "SIGMAS"],
            widgets=[1.0],
        ),
        _node(
            i + 10,
            "SamplerCustomAdvanced",
            f"Run {title_prefix.lower()} pass",
            group,
            (x + 1320, y + 140),
            size=(300, 150),
            inputs={
                "noise": Link(i + 7),
                "guider": Link(i + 6),
                "sampler": Link(i + 8),
                "sigmas": Link(i + 5),
                "latent_image": Link(i + 2),
            },
            input_types={"noise": "NOISE", "guider": "GUIDER", "sampler": "SAMPLER", "sigmas": "SIGMAS", "latent_image": "LATENT"},
            outputs=["output", "denoised_output"],
            output_types=["LATENT", "LATENT"],
        ),
        _node(
            i + 11,
            "VAEDecode",
            f"Decode {title_prefix.lower()} result",
            group,
            (x + 1320, y + 380),
            inputs={"samples": Link(i + 10), "vae": Link(3)},
            input_types={"samples": "LATENT", "vae": "VAE"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
        ),
        _node(
            i + 15,
            "PreviewImage",
            f"Preview {title_prefix.lower()} result",
            group,
            (x + 1320, y + 560),
            size=(300, 220),
            inputs={"images": Link(i + 11)},
            input_types={"images": "IMAGE"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
        ),
    ]
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
            "Set 832 x 1120 portrait canvas",
            group,
            (x + 520, 120),
            inputs={"width": 832, "height": 1120, "batch_size": 1},
            input_types={"width": "INT", "height": "INT", "batch_size": "INT"},
            outputs=["LATENT"],
            output_types=["LATENT"],
            widgets=[832, 1120, 1],
        ),
        _node(
            23,
            "CFGGuider",
            "Guide the HOI4 LoRA generation",
            group,
            (x + 520, 300),
            inputs={"model": Link(4), "positive": Link(20), "negative": Link(21), "cfg": 5.0},
            input_types={"model": "MODEL", "positive": "CONDITIONING", "negative": "CONDITIONING", "cfg": "FLOAT"},
            outputs=["GUIDER"],
            output_types=["GUIDER"],
            widgets=[5.0],
        ),
        _node(
            24,
            "RandomNoise",
            "Portrait seed",
            group,
            (x + 520, 520),
            inputs={"noise_seed": 42},
            input_types={"noise_seed": "INT"},
            outputs=["NOISE"],
            output_types=["NOISE"],
            widgets=[42, "randomize"],
        ),
        _node(
            25,
            "KSamplerSelect",
            "Use Euler sampler",
            group,
            (x + 900, 140),
            inputs={"sampler_name": "euler"},
            input_types={"sampler_name": "COMBO"},
            outputs=["SAMPLER"],
            output_types=["SAMPLER"],
            widgets=["euler"],
        ),
        _node(
            26,
            "Flux2Scheduler",
            f"FLUX.2 schedule - {DEFAULT_STEPS} steps",
            group,
            (x + 900, 340),
            inputs={"steps": DEFAULT_STEPS, "width": 832, "height": 1120},
            input_types={"steps": "INT", "width": "INT", "height": "INT"},
            outputs=["SIGMAS"],
            output_types=["SIGMAS"],
            widgets=[DEFAULT_STEPS, 832, 1120],
        ),
        _node(
            27,
            "SamplerCustomAdvanced",
            "Generate the HOI4 portrait",
            group,
            (x + 900, 540),
            size=(320, 150),
            inputs={"noise": Link(24), "guider": Link(23), "sampler": Link(25), "sigmas": Link(26), "latent_image": Link(22)},
            input_types={"noise": "NOISE", "guider": "GUIDER", "sampler": "SAMPLER", "sigmas": "SIGMAS", "latent_image": "LATENT"},
            outputs=["output", "denoised_output"],
            output_types=["LATENT", "LATENT"],
        ),
        _node(
            28,
            "VAEDecode",
            "Decode final styled portrait",
            group,
            (x + 1320, 540),
            inputs={"samples": Link(27), "vae": Link(3)},
            input_types={"samples": "LATENT", "vae": "VAE"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
        ),
        _node(
            29,
            "PreviewImage",
            "Preview generated portrait before background replacement",
            group,
            (x + 1320, 700),
            size=(300, 220),
            inputs={"images": Link(28)},
            input_types={"images": "IMAGE"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
        ),
    ]
    return nodes, Link(28)


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
            inputs={"image": Link(60), "upscale_method": "lanczos", "width": 832, "height": 1120, "crop": "center"},
            input_types={"image": "IMAGE", "upscale_method": "COMBO", "width": "INT", "height": "INT", "crop": "COMBO"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=["lanczos", 832, 1120, "center"],
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
            "Save 832 x 1120 master PNG",
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
            inputs={"image": Link(66), "upscale_method": "lanczos", "width": 156, "height": 210, "crop": "center"},
            input_types={"image": "IMAGE", "upscale_method": "COMBO", "width": "INT", "height": "INT", "crop": "COMBO"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=["lanczos", 156, 210, "center"],
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
                "width": 832,
                "height": 1120,
                "crop": "center",
            },
            input_types={"image": "IMAGE", "upscale_method": "COMBO", "width": "INT", "height": "INT", "crop": "COMBO"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=["lanczos", 832, 1120, "center"],
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
                    f"Save {label} 832 x 1120 master PNG",
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
                    inputs={"image": Link(branch + 2), "upscale_method": "lanczos", "width": 156, "height": 210, "crop": "center"},
                    input_types={"image": "IMAGE", "upscale_method": "COMBO", "width": "INT", "height": "INT", "crop": "COMBO"},
                    outputs=["IMAGE"],
                    output_types=["IMAGE"],
                    widgets=["lanczos", 156, 210, "center"],
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
            "Save 832 x 1120 processed PNG",
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
            inputs={"image": processed_image, "upscale_method": "lanczos", "width": 156, "height": 210, "crop": "center"},
            input_types={"image": "IMAGE", "upscale_method": "COMBO", "width": "INT", "height": "INT", "crop": "COMBO"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=["lanczos", 156, 210, "center"],
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
    groups.append(Group("02 FLUX.2 Klein 9B models", (1040, 40, 430, 800), "#3f789e"))
    if has_restoration:
        groups.append(Group("03 Optional FLUX.2 restoration", (1500, 40, 1800, 980), "#8b6f47"))
        style_height = 2700 if candidate_count > 1 else 980
        groups.append(Group("04 HOI4 LoRA styling", (3400, 40, 1800, style_height), "#7a568e"))
    else:
        groups.append(Group("04 HOI4 LoRA styling", (1500, 40, 1800, 980), "#7a568e"))
    background_x = 5600 if has_restoration else 3600
    output_height = 3040 if candidate_count > 1 else 720
    groups.append(Group("05 Optional background - after generation", (background_x - 80, 40, 1300, output_height), "#8d5b5b"))
    groups.append(Group("06 Preview and save", (background_x + 1300, 40, 1100, output_height), "#596b82"))
    return groups


def _processing_groups() -> list[Group]:
    return [
        Group("01 Source and ESRGAN", (40, 40, 930, 2150), "#557a46"),
        Group("02 FLUX.2 Klein 9B models", (1040, 40, 430, 800), "#3f789e"),
        Group("03 Optional FLUX.2 restoration", (1500, 40, 1800, 980), "#8b6f47"),
        Group("04 Processed portrait output", (3340, 40, 1100, 720), "#596b82"),
    ]


def build_source() -> Graph:
    nodes = _source_nodes(include_processed_preview=False) + _model_nodes()
    restoration_nodes, restored = _edit_stage(
        id_start=20,
        group="03 Optional FLUX.2 restoration",
        x=1540,
        image=Link(8),
        model=Link(1),
        prompt=RESTORATION_PROMPT,
        negative=RESTORATION_NEGATIVE,
        seed=17,
        title_prefix="Conservative restoration",
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
            inputs={"switch": False, "on_false": Link(8), "on_true": restored},
            input_types={"switch": "BOOLEAN", "on_false": "IMAGE", "on_true": "IMAGE"},
            outputs=["output"],
            output_types=["IMAGE"],
            widgets=[False],
        )
    )
    restoration_preview = next(node for node in nodes if node.node_id == 35)
    restoration_preview.title = "Preview selected processed portrait"
    restoration_preview.inputs["images"] = Link(32)
    styled_images: list[Link] = []
    for index, seed in enumerate(SOURCE_STYLE_SEEDS, start=1):
        style_nodes, styled = _edit_stage(
            id_start=40 + (index - 1) * 20,
            group="04 HOI4 LoRA styling",
            x=3440,
            y=80 + (index - 1) * 900,
            image=Link(32),
            model=Link(4),
            prompt=STYLE_PROMPT,
            negative=STYLE_NEGATIVE,
            seed=seed,
            title_prefix=f"Candidate {index} identity LoRA",
            prompt_node_title=f"Editable candidate {index} prompt — edits affect only candidate {index}",
        )
        nodes.extend(style_nodes)
        styled_images.append(styled)
    nodes.extend(_background_and_outputs_multi(final_images=styled_images, x=5600, id_start=120))
    return Graph(
        workflow_id="hoi4_portrait_flux2_klein_9b_source",
        description="Source portrait workflow: RealESRGAN first, optional FLUX.2 Klein 9B restoration once, then three independent HOI4 LoRA portrait candidates with optional background replacement on every candidate.",
        kind="image_to_image",
        nodes=nodes,
        groups=_groups(has_source=True, has_restoration=True, candidate_count=SOURCE_CANDIDATE_COUNT),
        metadata={
            "restoration_order": ["RealESRGAN_x2plus", "optional_flux2_klein_9b"],
            "flux_restoration_default": False,
            "candidate_count": SOURCE_CANDIDATE_COUNT,
            "candidate_seed_count": SOURCE_CANDIDATE_COUNT,
            "background_candidate_count": SOURCE_CANDIDATE_COUNT,
            "source_crop": "adaptive_head_and_shoulders_zoom_0.90_before_esrgan",
            "pose_preservation": "encoded_source_latent_is_sampler_start",
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
        model=Link(1),
        prompt=RESTORATION_PROMPT,
        negative=RESTORATION_NEGATIVE,
        seed=17,
        title_prefix="Conservative restoration",
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
            inputs={"switch": False, "on_false": Link(8), "on_true": restored},
            input_types={"switch": "BOOLEAN", "on_false": "IMAGE", "on_true": "IMAGE"},
            outputs=["output"],
            output_types=["IMAGE"],
            widgets=[False],
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
            "flux_restoration_default": False,
            "source_crop": "adaptive_head_and_shoulders_zoom_0.90_before_esrgan",
            "background_order": "not_applicable_processing_only",
        },
    )


def build_text_to_image() -> Graph:
    nodes = _model_nodes()
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
    if graph.workflow_id == "hoi4_portrait_flux2_klein_9b_source":
        layout = json.loads(SOURCE_LAYOUT_PATH.read_text(encoding="utf-8"))
        geometry = layout["nodes"]
        for node in graph.nodes:
            if node.node_id in {5, 6, 7, 8, 9, 11, 12, 13, 14}:
                continue
            saved = geometry.get(str(node.node_id))
            if saved:
                node.pos = tuple(saved["pos"])
                node.size = tuple(saved["size"])
        viewport = layout["viewport"]

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

    colors = {group.title: group.color for group in graph.groups}
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
        is_adaptive_crop = node.class_type == "AdaptivePortraitCrop"
        properties: dict[str, Any] = {
            "Node name for S&R": node.class_type,
            "cnr_id": "adaptive-portrait-crop" if is_adaptive_crop else "comfy-core",
            "ver": "0.8.2",
            "hoi4_group": node.group,
        }
        if node.models:
            properties["models"] = node.models
        is_feature_toggle = node.title.startswith("Toggle FLUX restoration") or node.title.startswith(
            "Toggle replacement background"
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
    return {
        "last_node_id": max(node.node_id for node in graph.nodes),
        "last_link_id": link_id - 1,
        "nodes": ui_nodes,
        "links": links,
        "groups": [
            {"title": group.title, "bounding": list(group.bounding), "color": group.color, "font_size": 24, "flags": {}}
            for group in graph.groups
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
            "core_nodes_only": not any(node.class_type == "AdaptivePortraitCrop" for node in graph.nodes),
            "comfy_cloud_ready": True,
            **graph.metadata,
        },
        "version": 0.4,
    }


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_all(root: Path = ROOT) -> list[dict[str, Any]]:
    workflow_dir = root / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    graphs = [build_source(), build_processing(), build_text_to_image()]
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
                "sha256": hashlib.sha256(ui_path.read_bytes()).hexdigest(),
                "api_sha256": hashlib.sha256(api_path.read_bytes()).hexdigest(),
                "node_count": len(graph.nodes),
                "core_nodes_only": not any(node.class_type == "AdaptivePortraitCrop" for node in graph.nodes),
            }
        )
    manifest = {
        "schema_version": WORKFLOW_SCHEMA_VERSION,
        "base_model": BASE_MODEL,
        "text_encoder": TEXT_ENCODER,
        "vae": VAE_MODEL,
        "style_lora": STYLE_LORA,
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
