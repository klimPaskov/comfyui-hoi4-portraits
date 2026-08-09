from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as functional
from scipy import ndimage

import cv2
import folder_paths
from PIL import Image, ImageOps


ASPECT = 1024 / 1365
YUNET_MODEL = "face_detection_yunet_2023mar.onnx"


def _resize_center_crop(image: torch.Tensor, width: int, height: int) -> torch.Tensor:
    """Lanczos-equivalent resize followed by a centered crop, never stretch."""

    if image.ndim != 4:
        raise ValueError("Expected a ComfyUI IMAGE tensor in BHWC format.")
    source_height, source_width = int(image.shape[1]), int(image.shape[2])
    scale = max(width / source_width, height / source_height)
    resized_width = max(width, round(source_width * scale))
    resized_height = max(height, round(source_height * scale))
    nchw = image.movedim(-1, 1)
    resized = functional.interpolate(
        nchw,
        size=(resized_height, resized_width),
        mode="bicubic",
        align_corners=False,
        antialias=True,
    ).movedim(1, -1)
    left = max(0, (resized_width - width) // 2)
    top = max(0, (resized_height - height) // 2)
    return resized[:, top : top + height, left : left + width, :].clamp(0, 1)


def _face_score(face: dict, width: int, height: int) -> float:
    face_center_x = float(face["x"]) + float(face["width"]) / 2
    face_center_y = float(face["y"]) + float(face["height"]) / 2
    distance = np.hypot((face_center_x - width / 2) / width, (face_center_y - height * 0.42) / height)
    area = np.sqrt(max(0.0, float(face["width"]) * float(face["height"])) / (width * height))
    return float(face.get("score", 0.0)) + 2.8 * area - 0.38 * distance


def _yunet_faces(frame: torch.Tensor) -> list[dict]:
    rgb = frame.detach().mul(255).add(0.5).clamp(0, 255).to(torch.uint8).cpu().numpy()
    height, width = rgb.shape[:2]
    # The workflow normalizes large sources before face detection. YuNet is much
    # more dependable on blurred and archival faces when its own fallback pass
    # sees a slightly larger raster, so upscale internally and map the result
    # back to the workflow image coordinates.
    scale = max(1.0, 1400.0 / max(width, height))
    work_width = max(1, round(width * scale))
    work_height = max(1, round(height * scale))
    work_rgb = (
        cv2.resize(rgb, (work_width, work_height), interpolation=cv2.INTER_LANCZOS4)
        if scale > 1.0
        else rgb
    )
    model_path = folder_paths.get_full_path_or_raise("detection", YUNET_MODEL)
    detector = cv2.FaceDetectorYN.create(model_path, "", (work_width, work_height), 0.25, 0.3, 5000)
    variants = [
        cv2.cvtColor(work_rgb, cv2.COLOR_RGB2BGR),
        cv2.cvtColor(
            cv2.equalizeHist(cv2.cvtColor(work_rgb, cv2.COLOR_RGB2GRAY)),
            cv2.COLOR_GRAY2BGR,
        ),
    ]
    faces: list[dict] = []
    for variant in variants:
        detector.setInputSize((work_width, work_height))
        _, detections = detector.detect(variant)
        if detections is None:
            continue
        for detection in detections:
            x, y, face_width, face_height = (float(value) / scale for value in detection[:4])
            if face_width < 8 or face_height < 8:
                continue
            faces.append(
                {
                    "x": x,
                    "y": y,
                    "width": face_width,
                    "height": face_height,
                    "score": float(detection[-1]),
                }
            )
    return faces


def _select_face(frame: torch.Tensor, provided: list[dict]) -> dict:
    height, width = int(frame.shape[0]), int(frame.shape[1])
    reliable = [face for face in provided if float(face.get("score", 0.0)) >= 0.45]
    if reliable:
        return max(reliable, key=lambda face: _face_score(face, width, height))
    fallback = _yunet_faces(frame)
    if fallback:
        return max(fallback, key=lambda face: _face_score(face, width, height))
    usable = [face for face in provided if float(face.get("score", 0.0)) >= 0.20]
    if usable:
        return max(usable, key=lambda face: _face_score(face, width, height))
    raise RuntimeError("No portrait subject was detected. Use the manual crop branch for this source.")


def _frame_box(
    width: int,
    height: int,
    face: dict,
    mask: np.ndarray,
    zoom: float,
    preserve_headwear: bool,
) -> tuple[int, int, int, int]:
    x1 = float(face["x"])
    y1 = float(face["y"])
    x2 = x1 + float(face["width"])
    y2 = y1 + float(face["height"])
    face_width = x2 - x1
    face_height = y2 - y1
    if face_width <= 0 or face_height <= 0:
        raise RuntimeError("The detected face box is invalid.")

    center_x = (x1 + x2) / 2
    head_top = max(0.0, y1 - (0.88 if preserve_headwear else 0.52) * face_height)
    head_left = max(0.0, x1 - 0.42 * face_height)
    head_right = min(float(width), x2 + 0.42 * face_height)

    mask_height, mask_width = mask.shape
    scale_x = mask_width / width
    scale_y = mask_height / height
    binary = mask >= 0.31
    labels, count = ndimage.label(binary)
    fx1 = max(0, round(x1 * scale_x))
    fy1 = max(0, round(y1 * scale_y))
    fx2 = min(mask_width, round(x2 * scale_x))
    fy2 = min(mask_height, round(y2 * scale_y))
    if preserve_headwear and count and fx2 > fx1 and fy2 > fy1:
        face_labels = labels[fy1:fy2, fx1:fx2]
        values, frequencies = np.unique(face_labels[face_labels > 0], return_counts=True)
        if len(values):
            component = labels == int(values[int(np.argmax(frequencies))])
            rx1 = max(0, round((center_x - 1.08 * face_height) * scale_x))
            rx2 = min(mask_width, round((center_x + 1.08 * face_height) * scale_x))
            ry1 = max(0, round((y1 - 1.35 * face_height) * scale_y))
            ry2 = min(mask_height, round((y1 + 0.48 * face_height) * scale_y))
            ys, xs = np.where(component[ry1:ry2, rx1:rx2])
            if len(xs) >= 24:
                silhouette_top = (ry1 + int(ys.min())) / scale_y
                silhouette_left = (rx1 + int(xs.min())) / scale_x
                silhouette_right = (rx1 + int(xs.max()) + 1) / scale_x
                # A reliable subject silhouette gives us the real top of hair
                # or headwear. Use it directly with a small visible margin;
                # the larger face-box allowance above remains the fallback
                # only when the silhouette cannot be trusted.
                head_top = max(0.0, silhouette_top - 0.08 * face_height)
                head_left = min(head_left, max(0.0, silhouette_left - 0.08 * face_height))
                head_right = max(head_right, min(float(width), silhouette_right + 0.08 * face_height))

    zoom = min(1.0, max(0.0, float(zoom)))
    # Zoom primarily removes torso below the face. When headwear preservation
    # is enabled, its silhouette remains a hard constraint. Otherwise the crop
    # uses ordinary face/head geometry and may cut oversized hats.
    body_below_face = 1.00 - 0.85 * zoom
    base_height = 3.40 - 1.45 * zoom
    desired_bottom = min(float(height), y2 + body_below_face * face_height)
    crop_height = max(
        base_height * face_height,
        desired_bottom - head_top,
        (head_right - head_left) / ASPECT,
    )
    crop_height = min(crop_height, float(height), width / ASPECT)
    crop_width = crop_height * ASPECT

    minimum_center = head_right - crop_width / 2
    maximum_center = head_left + crop_width / 2
    horizontal_center = (
        min(max(center_x, minimum_center), maximum_center)
        if minimum_center <= maximum_center
        else center_x
    )
    left = min(max(0.0, horizontal_center - crop_width / 2), width - crop_width)
    minimum_top = max(0.0, desired_bottom - crop_height)
    maximum_top = min(head_top, height - crop_height)
    top = max(
        0.0,
        maximum_top
        if maximum_top >= minimum_top
        else min(head_top, height - crop_height),
    )
    return round(left), round(top), round(left + crop_width), round(top + crop_height)


class AdaptivePortraitCrop:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "face_bboxes": ("BOUNDING_BOX",),
                "subject_mask": ("MASK",),
                "face_processing": (
                    "BOOLEAN",
                    {"default": True, "label_on": "use detected face", "label_off": "use centered crop"},
                ),
                "use_manual_crop": ("BOOLEAN", {"default": False}),
                "manual_x": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01, "advanced": True}),
                "manual_y": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01, "advanced": True}),
                "manual_width": ("FLOAT", {"default": 1.0, "min": 0.05, "max": 1.0, "step": 0.01, "advanced": True}),
                "manual_height": ("FLOAT", {"default": 1.0, "min": 0.05, "max": 1.0, "step": 0.01, "advanced": True}),
                "zoom": (
                    "FLOAT",
                    {
                        "default": 0.90,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.05,
                        "tooltip": "Higher values frame the face more closely while preserving the head and a safety margin.",
                    },
                ),
                "preserve_headwear": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label_on": "preserve hat/headwear",
                        "label_off": "ignore hat/headwear",
                        "tooltip": "When enabled, the subject silhouette protects the complete hat or headwear. Disable it for a normal face-led crop that may cut oversized headwear.",
                    },
                ),
                "output_width": (
                    "INT",
                    {
                        "default": 1024,
                        "min": 64,
                        "max": 8192,
                        "step": 1,
                        "tooltip": "Crop width before RealESRGAN. The public workflows use 512 for a true 2× preparation pass.",
                    },
                ),
                "output_height": (
                    "INT",
                    {
                        "default": 1365,
                        "min": 64,
                        "max": 8192,
                        "step": 1,
                        "tooltip": "Crop height before RealESRGAN. The public workflows use 683 for a true 2× preparation pass.",
                    },
                ),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("portrait",)
    FUNCTION = "crop"
    CATEGORY = "image/transform"
    DESCRIPTION = "Adaptive head-and-shoulders crop with optional headwear preservation."

    def crop(
        self,
        image,
        face_bboxes,
        subject_mask,
        face_processing=True,
        use_manual_crop=False,
        manual_x=0.0,
        manual_y=0.0,
        manual_width=1.0,
        manual_height=1.0,
        zoom=0.9,
        preserve_headwear=True,
        output_width=1024,
        output_height=1365,
    ):
        if bool(use_manual_crop):
            height, width = int(image.shape[1]), int(image.shape[2])
            left = min(width - 1, max(0, round(float(manual_x) * width)))
            top = min(height - 1, max(0, round(float(manual_y) * height)))
            right = min(width, max(left + 1, round((float(manual_x) + float(manual_width)) * width)))
            bottom = min(height, max(top + 1, round((float(manual_y) + float(manual_height)) * height)))
            return (_resize_center_crop(image[:, top:bottom, left:right, :], int(output_width), int(output_height)),)
        if not bool(face_processing):
            return (_resize_center_crop(image, int(output_width), int(output_height)),)
        if not isinstance(face_bboxes, list):
            face_bboxes = [[face_bboxes]]
        elif face_bboxes and isinstance(face_bboxes[0], dict):
            face_bboxes = [face_bboxes]
        outputs = []
        for index in range(image.shape[0]):
            boxes = face_bboxes[min(index, len(face_bboxes) - 1)] if face_bboxes else []
            frame = image[index]
            height, width = int(frame.shape[0]), int(frame.shape[1])
            face = _select_face(frame, boxes)
            mask_index = min(index, subject_mask.shape[0] - 1) if subject_mask.ndim == 3 else None
            mask = subject_mask[mask_index] if mask_index is not None else subject_mask
            box = _frame_box(
                width,
                height,
                face,
                mask.detach().float().cpu().numpy(),
                zoom,
                bool(preserve_headwear),
            )
            left, top, right, bottom = box
            crop = frame[top:bottom, left:right, :].permute(2, 0, 1).unsqueeze(0)
            resized = functional.interpolate(
                crop,
                size=(int(output_height), int(output_width)),
                mode="bicubic",
                align_corners=False,
                antialias=True,
            )
            outputs.append(resized.squeeze(0).permute(1, 2, 0))
        return (torch.stack(outputs).clamp(0, 1),)


class PortraitIdentityMask:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"image": ("IMAGE",)}}

    RETURN_TYPES = ("MASK",)
    RETURN_NAMES = ("identity_mask",)
    FUNCTION = "mask"
    CATEGORY = "masking"
    DESCRIPTION = "Soft face-and-head mask for FLUX.2 reference-feature transfer."

    def mask(self, image):
        masks = []
        for frame in image:
            height, width = int(frame.shape[0]), int(frame.shape[1])
            faces = _yunet_faces(frame)
            if faces:
                face = max(faces, key=lambda item: _face_score(item, width, height))
                x = float(face["x"])
                y = float(face["y"])
                face_width = float(face["width"])
                face_height = float(face["height"])
                center = (
                    round(x + face_width * 0.5),
                    round(y + face_height * 0.34),
                )
                axes = (
                    max(1, round(face_width * 1.02)),
                    max(1, round(face_height * 1.22)),
                )
            else:
                # The source has already been framed as a portrait. This
                # conservative fallback covers the head without selecting the
                # lower torso when the archival face is too degraded for YuNet.
                center = (round(width * 0.5), round(height * 0.34))
                axes = (round(width * 0.31), round(height * 0.29))
            mask = np.zeros((height, width), dtype=np.float32)
            cv2.ellipse(mask, center, axes, 0, 0, 360, 1.0, thickness=-1)
            blur = max(5, round(min(width, height) * 0.045))
            if blur % 2 == 0:
                blur += 1
            mask = cv2.GaussianBlur(mask, (blur, blur), 0)
            masks.append(torch.from_numpy(mask))
        return (torch.stack(masks).clamp(0, 1),)


class Hoi4PortraitSampler:
    """Generate a distilled FLUX.2 portrait from a prompt or source image."""

    @classmethod
    def INPUT_TYPES(cls):
        try:
            from comfy.samplers import KSampler

            samplers = list(KSampler.SAMPLERS)
            schedulers = list(KSampler.SCHEDULERS)
        except Exception:
            samplers = ["euler"]
            schedulers = ["simple"]
        if "euler" not in samplers:
            samplers.insert(0, "euler")
        if "simple" not in schedulers:
            schedulers.insert(0, "simple")
        return {
            "required": {
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "vae": ("VAE",),
                "mode": (["source_reference", "text_to_image"], {"default": "source_reference"}),
                "prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "dynamicPrompts": True,
                        "default": "make this portrait hoi4_portrait style",
                        "tooltip": "Keep this exact trigger phrase; append only short identity or clothing details when needed.",
                    },
                ),
                "negative_prompt": ("STRING", {"multiline": True, "default": ""}),
                "width": ("INT", {"default": 1024, "min": 16, "max": 16384, "step": 16}),
                "height": ("INT", {"default": 1365, "min": 16, "max": 16384, "step": 1}),
                "noise_seed": (
                    "INT",
                    {
                        "default": 42,
                        "min": 0,
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "control_after_generate": True,
                        "tooltip": "Random source for the initial noise. Change it (or let 'randomize' pick one) to get a different portrait from the same prompt.",
                    },
                ),
                "steps": (
                    "INT",
                    {
                        "default": 4,
                        "min": 1,
                        "max": 10000,
                        "tooltip": "How many denoising steps the sampler runs. More steps = more refined detail but slower. The project default of 4 is tuned for the HOI4 style LoRA.",
                    },
                ),
                "cfg": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.0,
                        "max": 100.0,
                        "step": 0.1,
                        "round": 0.01,
                        "tooltip": "How strongly the model follows the prompt. Higher values apply the HOI4 style more sharply; the tuned default for this workflow is 1.0.",
                    },
                ),
                "guidance": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.0,
                        "max": 100.0,
                        "step": 0.1,
                        "round": 0.01,
                        "tooltip": "FLUX.2 guidance scale. Like CFG it controls prompt adherence; FLUX.2 Klein works best at low values (default 1.0).",
                    },
                ),
                "sampling_algorithm": (
                    samplers,
                    {
                        "tooltip": "The sampling algorithm (sampler) itself. 'euler' is the tuned default; switch to 'euler_ancestral', 'dpmpp_2m' or any installed sampler for experiments.",
                    },
                ),
                "scheduler": (
                    schedulers,
                    {
                        "tooltip": "How the denoise strength is scheduled across the steps. 'simple' is the tuned FLUX.2 default; 'karras' or 'sgm_uniform' change the schedule.",
                    },
                ),
                "denoise": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.01,
                        "round": 0.01,
                        "tooltip": "Fraction of the noise removed. 1.0 means a full generation from the reference latent; lower values keep more of the source structure.",
                    },
                ),
                "add_noise": (
                    ["enable", "disable"],
                    {
                        "tooltip": "Whether new noise is added before sampling. Keep 'enable'; 'disable' is only for img2img refinement at low denoise.",
                    },
                ),
                "start_at_step": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 10000,
                        "advanced": True,
                        "tooltip": "Advanced: first step of sampling to run. Leave at 0.",
                    },
                ),
                "end_at_step": (
                    "INT",
                    {
                        "default": 10000,
                        "min": 0,
                        "max": 10000,
                        "advanced": True,
                        "tooltip": "Advanced: last step of sampling to run. Leave at 10000 to run the full range.",
                    },
                ),
                "force_full_denoise": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "advanced": True,
                        "tooltip": "Advanced: force the sampler to denoise the final step fully. Keep enabled.",
                    },
                ),
            },
            "optional": {"reference_image": ("IMAGE",)},
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("portrait",)
    FUNCTION = "sample"
    CATEGORY = "HOI4 portraits/sampling"
    DESCRIPTION = (
        "FLUX.2 Klein portrait generator with prompt, source-reference/text mode, guidance, CFG, "
        "seed, steps, sampler, scheduler, and denoise controls."
    )

    def sample(
        self,
        model,
        clip,
        vae,
        mode,
        prompt,
        negative_prompt,
        width,
        height,
        noise_seed,
        steps,
        cfg,
        guidance,
        sampling_algorithm,
        scheduler,
        denoise,
        add_noise="enable",
        start_at_step=0,
        end_at_step=10000,
        force_full_denoise=True,
        reference_image=None,
    ):
        # Imports are local so the node pack can be imported by the release
        # validator without requiring a running ComfyUI process.
        import node_helpers
        import nodes

        positive = nodes.CLIPTextEncode().encode(clip, str(prompt))[0]
        negative = nodes.CLIPTextEncode().encode(clip, str(negative_prompt))[0]
        if mode == "source_reference":
            if reference_image is None:
                raise ValueError("source_reference mode requires a reference_image connection.")
            latent_image = nodes.VAEEncode().encode(vae, reference_image)[0]
            reference_node = _registered_node("ReferenceLatent")
            positive = _node_output_values(reference_node.execute(positive, latent_image))[0]
            negative = _node_output_values(reference_node.execute(negative, latent_image))[0]
        else:
            empty_node = _registered_node("EmptyFlux2LatentImage")
            latent_image = _node_output_values(
                empty_node.execute(int(width), int(height), 1)
            )[0]

        guided_positive = node_helpers.conditioning_set_values(positive, {"guidance": float(guidance)})
        samples = nodes.common_ksampler(
            model,
            int(noise_seed),
            int(steps),
            float(cfg),
            sampling_algorithm,
            scheduler,
            guided_positive,
            negative,
            latent_image,
            denoise=float(denoise),
            disable_noise=add_noise == "disable",
            start_step=int(start_at_step),
            last_step=int(end_at_step),
            force_full_denoise=bool(force_full_denoise),
        )[0]
        return nodes.VAEDecode().decode(vae, samples)


def _node_output_values(value: Any) -> tuple[Any, ...]:
    """Normalize V1 tuples/dicts and V3 ``NodeOutput`` values.

    The upstream Adonis graph mixes classic ComfyUI nodes with the V3
    RES4LYF sampler. This adapter is shared by the focused custom nodes that
    invoke registered ComfyUI operations while keeping the public workflow
    topology expanded and inspectable.
    """

    if hasattr(value, "result"):
        result = value.result
        return tuple(result or ())
    if isinstance(value, dict) and "result" in value:
        return tuple(value["result"])
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    return (value,)


def _registered_node(class_type: str):
    import nodes

    node_class = nodes.NODE_CLASS_MAPPINGS.get(class_type)
    if node_class is None:
        raise RuntimeError(
            f"Required Adonis node {class_type!r} is unavailable. "
            "Run the bundled installer, restart ComfyUI, and queue again."
        )
    return node_class


class Hoi4BackgroundReplace:
    """One focused operation: optionally replace the generated background."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "bg_removal_model": ("BACKGROUND_REMOVAL",),
                "use_background": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "label_on": "use supplied background",
                        "label_off": "keep generated background",
                    },
                ),
            },
            "optional": {"background": ("IMAGE",)},
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "replace"
    CATEGORY = "HOI4 portraits/output"
    DESCRIPTION = "Optional BiRefNet subject mask and background composite."

    def replace(self, image, bg_removal_model, use_background, background=None):
        if not bool(use_background):
            return (image,)
        if background is None:
            raise ValueError("Background replacement is enabled but no background image is connected.")
        mask = _node_output_values(
            _registered_node("RemoveBackground").execute(bg_removal_model, image)
        )[0]
        if mask.ndim == 2:
            mask = mask.unsqueeze(0)
        height, width = int(image.shape[1]), int(image.shape[2])
        mask = functional.interpolate(
            mask.unsqueeze(1).float(),
            size=(height, width),
            mode="bilinear",
            align_corners=False,
        ).movedim(1, -1).clamp(0, 1)
        backdrop = _resize_center_crop(background, width, height)
        if backdrop.shape[0] == 1 and image.shape[0] > 1:
            backdrop = backdrop.repeat(image.shape[0], 1, 1, 1)
        return ((image * mask + backdrop[: image.shape[0]] * (1.0 - mask)).clamp(0, 1),)


class Hoi4BatchInput:
    """Load all compatible images in an input subfolder as one image batch."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_folder": ("STRING", {"default": "hoi4_portraits_batch"}),
                "file_pattern": ("STRING", {"default": "*.png;*.jpg;*.jpeg;*.webp"}),
            }
        }

    RETURN_TYPES = ("IMAGE", "MASK", "STRING")
    RETURN_NAMES = ("images", "masks", "filenames")
    OUTPUT_IS_LIST = (True, True, True)
    FUNCTION = "load_batch"
    CATEGORY = "HOI4 portraits/input"
    DESCRIPTION = "Load every image in input/hoi4_portraits_batch for one shared workflow run."

    def load_batch(self, input_folder, file_pattern):
        root = Path(folder_paths.get_input_directory()) / input_folder
        patterns = [item.strip() for item in str(file_pattern).split(";") if item.strip()]
        paths: list[Path] = []
        for pattern in patterns or ["*"]:
            paths.extend(Path(path) for path in glob.glob(str(root / pattern)))
        paths = sorted({path.resolve() for path in paths if path.is_file()})
        if not paths:
            raise RuntimeError(f"No input images found in {root} matching {file_pattern!r}.")

        images: list[Image.Image] = []
        for path in paths:
            with Image.open(path) as source:
                images.append(ImageOps.exif_transpose(source).convert("RGB"))
        tensors: list[torch.Tensor] = []
        masks: list[torch.Tensor] = []
        for image in images:
            array = np.asarray(image, dtype=np.float32) / 255.0
            tensors.append(torch.from_numpy(array).unsqueeze(0))
            masks.append(torch.zeros((1, 64, 64), dtype=torch.float32))
        return (
            [tensor.clamp(0, 1) for tensor in tensors],
            masks,
            [path.name for path in paths],
        )


class Hoi4SaveDDS:
    """Save a 156x210 portrait as a HOI4-compatible DDS.

    Vanilla leader portraits are 156x210, uncompressed A8R8G8B8 textures with
    no mipmaps.  Pillow writes that DDS profile from an RGBA image using the
    same 32-bit masks as the game files: R=0x00ff0000, G=0x0000ff00,
    B=0x000000ff, A=0xff000000.  DXT5 remains available for older mods that
    deliberately use block-compressed portraits, but it is not the default.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "filename_prefix": (
                    "STRING",
                    {
                        "default": "156x210/dds/hoi4_portrait",
                        "tooltip": "Output subfolder and filename prefix inside ComfyUI's output folder. '156x210/dds/...' matches the workflow's game-ready folder.",
                    },
                ),
                "format": (
                    ["argb8888", "dxt5"],
                    {
                        "tooltip": "A8R8G8B8 is the vanilla HOI4 leader-portrait format. Both choices use one 156x210 image with no mipmaps.",
                    },
                ),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "save"
    CATEGORY = "HOI4 portraits/output"
    DESCRIPTION = "Save vanilla-style 156x210 A8R8G8B8 DDS portraits with no mipmaps for HOI4."

    def save(self, images, filename_prefix, format="argb8888"):
        output_dir = Path(folder_paths.get_output_directory())
        prefix = Path(str(filename_prefix))
        if prefix.is_absolute() or ".." in prefix.parts:
            raise ValueError("DDS filename_prefix must stay inside the ComfyUI output folder.")
        saved: list[Path] = []
        for index, tensor in enumerate(images):
            array = (tensor.detach().cpu().numpy().clip(0, 1) * 255.0 + 0.5).astype(np.uint8)
            if array.ndim != 3 or array.shape[0] != 210 or array.shape[1] != 156:
                raise ValueError(
                    f"HOI4 DDS output must be 156x210; received {array.shape[1]}x{array.shape[0]}."
                )
            rgb = array[:, :, :3]
            alpha = np.full((array.shape[0], array.shape[1], 1), 255, dtype=np.uint8)
            image = Image.fromarray(np.concatenate((rgb, alpha), axis=2))
            output_folder, filename, counter, _, _ = folder_paths.get_save_image_path(
                str(prefix), str(output_dir), array.shape[1], array.shape[0]
            )
            target_folder = Path(output_folder)
            target_folder.mkdir(parents=True, exist_ok=True)
            target = target_folder / f"{filename}_{counter + index:05d}.dds"
            if format == "dxt5":
                image.save(target, format="DDS", pixel_format="DXT5")
            else:
                image.save(target, format="DDS")
            saved.append(target)
        return (images,)


NODE_CLASS_MAPPINGS = {
    "AdaptivePortraitCrop": AdaptivePortraitCrop,
    "PortraitIdentityMask": PortraitIdentityMask,
    "Hoi4PortraitSampler": Hoi4PortraitSampler,
    "Hoi4BackgroundReplace": Hoi4BackgroundReplace,
    "Hoi4BatchInput": Hoi4BatchInput,
    "Hoi4SaveDDS": Hoi4SaveDDS,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AdaptivePortraitCrop": "Adaptive Portrait Crop",
    "PortraitIdentityMask": "Portrait Identity Mask",
    "Hoi4PortraitSampler": "HOI4 Portrait Sampler",
    "Hoi4BackgroundReplace": "HOI4 Optional Background Replacement",
    "Hoi4BatchInput": "HOI4 Batch Input Folder",
    "Hoi4SaveDDS": "HOI4 Save DDS Portrait (156x210)",
}
