#!/usr/bin/env python3
"""Build the public ComfyUI workflows from one deterministic graph source.

Only built-in ComfyUI nodes are used.  The generated ``*.json`` files are
editor/save format; the matching ``*.api.json`` files are ready for
``/prompt`` or the Comfy Cloud workflow API.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / "workflows"

BASE_MODEL = "flux-2-klein-base-9b-fp8.safetensors"
TEXT_ENCODER = "qwen_3_8b_fp8mixed.safetensors"
VAE_MODEL = "flux2-vae.safetensors"
STYLE_LORA = "hoi4_portraits_flux2_klein_9b_lora_000002500.safetensors"
ESRGAN_MODEL = "RealESRGAN_x2plus.pth"
BACKGROUND_MODEL = "birefnet.safetensors"

MODEL_URLS = {
    BASE_MODEL: "https://huggingface.co/black-forest-labs/FLUX.2-klein-base-9B-fp8/resolve/9ecf2143d71542449960c5584340269c6d401449/flux-2-klein-base-9b-fp8.safetensors",
    TEXT_ENCODER: "https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/23fbc8aa8b621f29f2249cd1bd9c47e5d0eebd83/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors",
    VAE_MODEL: "https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/23fbc8aa8b621f29f2249cd1bd9c47e5d0eebd83/split_files/vae/flux2-vae.safetensors",
    STYLE_LORA: "https://huggingface.co/Hoops-McCann/hoi4-portraits-flux2-klein-9b-lora/resolve/567bdd03a4a93f7506453780285323fa10ed48aa/hoi4_portraits_flux2_klein_9b_lora_000002500.safetensors",
    ESRGAN_MODEL: "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
    BACKGROUND_MODEL: "https://huggingface.co/Comfy-Org/BiRefNet/resolve/8fdc9d315889de96cc0c6269eeecd333e2727889/background_removal/birefnet.safetensors",
}

RESTORATION_PROMPT = (
    "Restore this historical head-and-shoulders portrait conservatively. Repair scratches, fading, compression, and lost fine detail. "
    "Preserve the person's exact identity, facial geometry, expression, hairstyle, clothing, pose, camera angle, and crop. "
    "Keep period-authentic texture. Colorize monochrome or sepia material only when the colors can remain plausible. Do not stylize."
)
RESTORATION_NEGATIVE = (
    "changed identity, changed face, altered expression, different hairstyle, different clothing, modern accessories, beauty retouching, "
    "plastic skin, painterly style, fantasy details, text, watermark"
)
STYLE_PROMPT = (
    "hoi4_portrait, transform the supplied person into a polished Hearts of Iron IV leader portrait. Preserve exact identity, facial "
    "geometry, expression, hairstyle, visible clothing, pose, camera angle, and crop. Use a hand-painted 1930s-1940s grand-strategy "
    "portrait finish, restrained brushwork, realistic skin, crisp eyes, soft directional studio light, muted historical colors, and a "
    "formal head-and-shoulders composition. Do not invent medals, insignia, hats, glasses, facial hair, or accessories."
)
STYLE_NEGATIVE = (
    "changed identity, face swap, different person, deformed face, asymmetrical eyes, extra limbs, invented insignia, invented medals, "
    "modern clothing, anime, cartoon, 3d render, glossy plastic skin, text, watermark"
)
TEXT_PROMPT = (
    "hoi4_portrait, a stern middle-aged 1940s army officer in a plain dark service uniform, direct gaze, closed mouth, neatly combed hair, "
    "formal head-and-shoulders composition, hand-painted grand-strategy portrait, restrained brushwork, realistic skin, crisp eyes, soft "
    "directional studio light, muted olive and brown historical palette, no visible text."
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


def _model_nodes() -> list[Node]:
    group = "02 FLUX.2 Klein 9B models"
    return [
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
        _node(
            4,
            "LoraLoaderModelOnly",
            "Apply the HOI4 FLUX.2 Klein 9B LoRA",
            group,
            (1120, 620),
            inputs={"model": Link(1), "lora_name": STYLE_LORA, "strength_model": 1.0},
            input_types={"model": "MODEL", "lora_name": "COMBO", "strength_model": "FLOAT"},
            outputs=["MODEL"],
            output_types=["MODEL"],
            widgets=[STYLE_LORA, 1.0],
            models=_model(STYLE_LORA, "loras"),
        ),
    ]


def _source_nodes() -> list[Node]:
    group = "01 Source and ESRGAN"
    return [
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
            6,
            "UpscaleModelLoader",
            "Load RealESRGAN x2",
            group,
            (520, 120),
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
            (520, 300),
            inputs={"upscale_model": Link(6), "image": Link(5)},
            input_types={"upscale_model": "UPSCALE_MODEL", "image": "IMAGE"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
        ),
        _node(
            8,
            "ImageScale",
            "Fit portrait to the 832 x 1120 work canvas",
            group,
            (520, 480),
            size=(360, 150),
            inputs={"image": Link(7), "upscale_method": "lanczos", "width": 832, "height": 1120, "crop": "center"},
            input_types={"image": "IMAGE", "upscale_method": "COMBO", "width": "INT", "height": "INT", "crop": "COMBO"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=["lanczos", 832, 1120, "center"],
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
) -> tuple[list[Node], Link]:
    i = id_start
    nodes = [
        _node(
            i,
            "CLIPTextEncode",
            f"{title_prefix} instructions",
            group,
            (x, 120),
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
            (x, 430),
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
            (x + 500, 120),
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
            (x + 500, 300),
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
            (x + 500, 480),
            inputs={"conditioning": Link(i + 1), "latent": Link(i + 2)},
            input_types={"conditioning": "CONDITIONING", "latent": "LATENT"},
            outputs=["CONDITIONING"],
            output_types=["CONDITIONING"],
        ),
        _node(
            i + 5,
            "EmptyFlux2LatentImage",
            "Set 832 x 1120 generation canvas",
            group,
            (x + 500, 660),
            inputs={"width": 832, "height": 1120, "batch_size": 1},
            input_types={"width": "INT", "height": "INT", "batch_size": "INT"},
            outputs=["LATENT"],
            output_types=["LATENT"],
            widgets=[832, 1120, 1],
        ),
        _node(
            i + 6,
            "CFGGuider",
            f"Guide {title_prefix.lower()} pass",
            group,
            (x + 900, 120),
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
            (x + 900, 300),
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
            (x + 900, 480),
            inputs={"sampler_name": "euler"},
            input_types={"sampler_name": "COMBO"},
            outputs=["SAMPLER"],
            output_types=["SAMPLER"],
            widgets=["euler"],
        ),
        _node(
            i + 9,
            "Flux2Scheduler",
            "FLUX.2 schedule - 20 steps",
            group,
            (x + 900, 660),
            inputs={"steps": 20, "width": 832, "height": 1120},
            input_types={"steps": "INT", "width": "INT", "height": "INT"},
            outputs=["SIGMAS"],
            output_types=["SIGMAS"],
            widgets=[20, 832, 1120],
        ),
        _node(
            i + 10,
            "SamplerCustomAdvanced",
            f"Run {title_prefix.lower()} pass",
            group,
            (x + 1280, 260),
            size=(300, 150),
            inputs={
                "noise": Link(i + 7),
                "guider": Link(i + 6),
                "sampler": Link(i + 8),
                "sigmas": Link(i + 9),
                "latent_image": Link(i + 5),
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
            (x + 1280, 500),
            inputs={"samples": Link(i + 10), "vae": Link(3)},
            input_types={"samples": "LATENT", "vae": "VAE"},
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
            "Write the leader portrait prompt",
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
            (x + 520, 480),
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
            (x + 900, 120),
            inputs={"sampler_name": "euler"},
            input_types={"sampler_name": "COMBO"},
            outputs=["SAMPLER"],
            output_types=["SAMPLER"],
            widgets=["euler"],
        ),
        _node(
            26,
            "Flux2Scheduler",
            "FLUX.2 schedule - 20 steps",
            group,
            (x + 900, 300),
            inputs={"steps": 20, "width": 832, "height": 1120},
            input_types={"steps": "INT", "width": "INT", "height": "INT"},
            outputs=["SIGMAS"],
            output_types=["SIGMAS"],
            widgets=[20, 832, 1120],
        ),
        _node(
            27,
            "SamplerCustomAdvanced",
            "Generate the HOI4 portrait",
            group,
            (x + 900, 500),
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
            (x + 1280, 500),
            inputs={"samples": Link(27), "vae": Link(3)},
            input_types={"samples": "LATENT", "vae": "VAE"},
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
            (x + 1320, 120),
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
            (x + 1820, 120),
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
            (x + 1820, 320),
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
            (x + 1820, 540),
            inputs={"images": Link(72), "filename_prefix": "hoi4_portraits/portrait_156x210"},
            input_types={"images": "IMAGE", "filename_prefix": "STRING"},
            outputs=["IMAGE"],
            output_types=["IMAGE"],
            widgets=["hoi4_portraits/portrait_156x210"],
        ),
    ]


def _groups(*, has_source: bool, has_restoration: bool) -> list[Group]:
    groups: list[Group] = []
    if has_source:
        groups.append(Group("01 Source and ESRGAN", (40, 40, 930, 720), "#557a46"))
    groups.append(Group("02 FLUX.2 Klein 9B models", (1040, 40, 390, 760), "#3f789e"))
    if has_restoration:
        groups.append(Group("03 Optional FLUX.2 restoration", (1500, 40, 1700, 860), "#8b6f47"))
        groups.append(Group("04 HOI4 LoRA styling", (3280, 40, 1700, 860), "#7a568e"))
    else:
        groups.append(Group("04 HOI4 LoRA styling", (1500, 40, 1700, 860), "#7a568e"))
    background_x = 5200 if has_restoration else 3420
    groups.append(Group("05 Optional background - after generation", (background_x - 80, 40, 1260, 720), "#8d5b5b"))
    groups.append(Group("06 Preview and save", (background_x + 1240, 40, 960, 720), "#596b82"))
    return groups


def build_full_power() -> Graph:
    nodes = _source_nodes() + _model_nodes()
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
            "Toggle FLUX restoration (on: ESRGAN then FLUX; off: ESRGAN only)",
            "03 Optional FLUX.2 restoration",
            (2820, 680),
            size=(330, 150),
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
        x=3320,
        image=Link(32),
        model=Link(4),
        prompt=STYLE_PROMPT,
        negative=STYLE_NEGATIVE,
        seed=42,
        title_prefix="HOI4 LoRA styling",
    )
    nodes.extend(style_nodes)
    nodes.extend(_background_and_outputs(final_image=styled, x=5200))
    return Graph(
        workflow_id="hoi4_portrait_flux2_klein_9b_full_power",
        description="Source portrait workflow: RealESRGAN first, optional FLUX.2 Klein 9B restoration second, HOI4 LoRA styling, then optional background replacement.",
        kind="image_to_image_full_power",
        nodes=nodes,
        groups=_groups(has_source=True, has_restoration=True),
        metadata={
            "restoration_order": ["RealESRGAN_x2plus", "optional_flux2_klein_9b"],
            "flux_restoration_default": True,
            "background_order": "after_final_lora_styled_decode",
        },
    )


def build_esrgan_only() -> Graph:
    nodes = _source_nodes() + _model_nodes()
    style_nodes, styled = _edit_stage(
        id_start=40,
        group="04 HOI4 LoRA styling",
        x=1540,
        image=Link(8),
        model=Link(4),
        prompt=STYLE_PROMPT,
        negative=STYLE_NEGATIVE,
        seed=42,
        title_prefix="HOI4 LoRA styling",
    )
    nodes.extend(style_nodes)
    nodes.extend(_background_and_outputs(final_image=styled, x=3420))
    return Graph(
        workflow_id="hoi4_portrait_flux2_klein_9b_esrgan_only",
        description="Source portrait workflow: RealESRGAN preparation, FLUX.2 Klein 9B HOI4 LoRA styling, then optional background replacement.",
        kind="image_to_image_esrgan_only",
        nodes=nodes,
        groups=_groups(has_source=True, has_restoration=False),
        metadata={
            "restoration_order": ["RealESRGAN_x2plus"],
            "flux_restoration_default": False,
            "background_order": "after_final_lora_styled_decode",
        },
    )


def build_text_to_image() -> Graph:
    nodes = _model_nodes()
    text_nodes, styled = _text_stage(group="04 HOI4 LoRA styling", x=1540)
    nodes.extend(text_nodes)
    nodes.extend(_background_and_outputs(final_image=styled, x=3420))
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
        properties: dict[str, Any] = {
            "Node name for S&R": node.class_type,
            "cnr_id": "comfy-core",
            "ver": "0.8.2",
            "hoi4_group": node.group,
        }
        if node.models:
            properties["models"] = node.models
        ui_nodes.append(
            {
                "id": node.node_id,
                "type": node.class_type,
                "title": node.title,
                "pos": list(node.pos),
                "size": list(node.size),
                "color": colors.get(node.group, "#3f789e"),
                "bgcolor": colors.get(node.group, "#3f789e"),
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
            "ds": {"scale": 0.45, "offset": [120, 120]},
            "workflow_id": graph.workflow_id,
            "description": graph.description,
            "workflow_kind": graph.kind,
            "project": "comfyui-hoi4-portraits",
            "graph_version": "2.0.0",
            "base_model": BASE_MODEL,
            "style_lora": STYLE_LORA,
            "core_nodes_only": True,
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
    graphs = [build_full_power(), build_esrgan_only(), build_text_to_image()]
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
                "core_nodes_only": True,
            }
        )
    manifest = {
        "schema_version": "2.0.0",
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
