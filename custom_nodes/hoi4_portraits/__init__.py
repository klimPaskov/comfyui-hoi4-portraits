from __future__ import annotations

from fnmatch import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

import numpy as np
import torch
import torch.nn.functional as functional
from scipy import ndimage

import cv2
import folder_paths
from PIL import Image, ImageOps, PngImagePlugin


ASPECT = 1024 / 1365
YUNET_MODEL = "face_detection_yunet_2023mar.onnx"
WEB_DIRECTORY = "./web"


def _safe_output_name(source_filename: str, suffix: str = "") -> str:
    """Build one filesystem-safe output name from an input image."""

    basename = str(source_filename).replace("\\", "/").rsplit("/", 1)[-1]
    stem = Path(basename).stem.strip() or "portrait"
    safe_stem = re.sub(r'[\x00-\x1f<>:"/\\|?*]', "_", stem)
    safe_suffix = re.sub(r'[\x00-\x1f<>:"/\\|?*]', "_", str(suffix).strip())
    return f"{safe_stem}{safe_suffix}"


def _output_filename_prefixes(source_filename: str, suffix: str = "") -> tuple[str, str, str, str, str]:
    """Build safe output paths while preserving the input image stem."""

    output_name = _safe_output_name(source_filename, suffix)
    return (
        f"hoi4_portraits/1024x1365/{output_name}",
        f"hoi4_portraits/156x210/{output_name}",
        f"hoi4_portraits/156x210/dds/{output_name}",
        f"hoi4_portraits/1024x1365/processed/{output_name}",
        f"hoi4_portraits/1024x1365/restored/{output_name}",
    )


def _safe_output_prefix(filename_prefix: str) -> tuple[Path, str]:
    """Resolve a safe output prefix, including the installer-managed portrait link."""

    output_dir = Path(folder_paths.get_output_directory())
    prefix = Path(str(filename_prefix))
    if prefix.is_absolute() or not prefix.name or ".." in prefix.parts:
        raise ValueError("Portrait filename_prefix must stay inside the configured output folder.")
    target_folder = output_dir / prefix.parent
    if prefix.parts and prefix.parts[0] == "hoi4_portraits":
        allowed_root = (output_dir / "hoi4_portraits").resolve(strict=False)
    else:
        allowed_root = output_dir.resolve(strict=False)
    resolved_target = target_folder.resolve(strict=False)
    try:
        if os.path.commonpath((str(allowed_root), str(resolved_target))) != str(allowed_root):
            raise ValueError("Portrait filename_prefix resolves outside the configured output folder.")
    except ValueError as exc:
        raise ValueError("Portrait filename_prefix resolves outside the configured output folder.") from exc
    target_folder.mkdir(parents=True, exist_ok=True)
    return target_folder, prefix.name


def _safe_input_file(source_filename: str) -> Path:
    """Resolve an input file, including the installer-managed batch link."""

    input_dir = Path(folder_paths.get_input_directory())
    relative = Path(str(source_filename))
    if relative.is_absolute() or not relative.name or ".." in relative.parts:
        raise ValueError("Portrait source filename must stay inside the configured input folder.")
    if relative.parts and relative.parts[0] == "hoi4_portraits_batch":
        allowed_root = (input_dir / "hoi4_portraits_batch").resolve(strict=False)
    else:
        allowed_root = input_dir.resolve(strict=False)
    source_path = (input_dir / relative).resolve(strict=False)
    try:
        if os.path.commonpath((str(allowed_root), str(source_path))) != str(allowed_root):
            raise ValueError("Portrait source filename resolves outside the configured input folder.")
    except ValueError as exc:
        raise ValueError("Portrait source filename resolves outside the configured input folder.") from exc
    if not source_path.is_file():
        raise ValueError(f"Portrait source file does not exist: {source_filename!r}")
    return source_path


def _next_output_counter(target_folder: Path, filename: str, extension: str) -> int:
    pattern = re.compile(rf"^{re.escape(filename)}_(\d{{5}}){re.escape(extension)}$", re.IGNORECASE)
    counters = [int(match.group(1)) for path in target_folder.iterdir() if (match := pattern.match(path.name))]
    return max(counters, default=0) + 1


def _single_list_value(value: Any, default: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return value[0] if value else default
    return value


def _batch_output_subfolder(batch_name: Any, save_without_batch_folder: Any) -> str:
    """Reserve the next batch folder, or validate a user-supplied folder name."""

    if bool(_single_list_value(save_without_batch_folder, False)):
        return ""
    custom = str(_single_list_value(batch_name, "")).strip()
    if custom:
        if (
            custom in {".", ".."}
            or Path(custom).name != custom
            or "/" in custom
            or "\\" in custom
            or re.search(r'[\x00-\x1f<>:"|?*]', custom)
        ):
            raise ValueError("Batch name must be one valid folder name.")
        _safe_output_prefix(f"hoi4_portraits/1024x1365/{custom}/portrait")
        return custom

    master_root, _ = _safe_output_prefix("hoi4_portraits/1024x1365/portrait")
    numbers = [
        int(match.group(1))
        for path in master_root.iterdir()
        if path.is_dir() and (match := re.fullmatch(r"batch_(\d+)", path.name, re.IGNORECASE))
    ]
    number = max(numbers, default=0) + 1
    while True:
        folder = master_root / f"batch_{number}"
        try:
            folder.mkdir()
            return folder.name
        except FileExistsError:
            number += 1


def _tensor_to_pil(tensor: torch.Tensor) -> Image.Image:
    array = (tensor.detach().cpu().numpy().clip(0, 1) * 255.0 + 0.5).astype(np.uint8)
    if array.ndim != 3 or array.shape[2] not in (3, 4):
        raise ValueError(f"Portrait output expects RGB or RGBA images; received shape {array.shape}.")
    return Image.fromarray(array)


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


class Hoi4SetupGuide:
    """Frontend-only download and folder guide shown at the start of a workflow."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {}}

    RETURN_TYPES = ()
    FUNCTION = "show"
    CATEGORY = "HOI4 portraits/setup"
    DESCRIPTION = "Clickable model downloads and their ComfyUI folder locations."

    def show(self):
        return ()


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


class Hoi4LoadImage:
    """Core image upload with the selected filename exposed downstream."""

    @classmethod
    def INPUT_TYPES(cls):
        return _registered_node("LoadImage").INPUT_TYPES()

    RETURN_TYPES = ("IMAGE", "MASK", "STRING")
    RETURN_NAMES = ("image", "mask", "filename")
    FUNCTION = "load_image"
    CATEGORY = "HOI4 portraits/input"
    DESCRIPTION = "Upload a portrait and pass its filename to the automatic savers."

    @classmethod
    def IS_CHANGED(cls, image):
        return _registered_node("LoadImage").IS_CHANGED(image)

    @classmethod
    def VALIDATE_INPUTS(cls, image):
        return _registered_node("LoadImage").VALIDATE_INPUTS(image)

    def load_image(self, image):
        loaded_image, mask = _registered_node("LoadImage")().load_image(image)
        return (loaded_image, mask, str(image))


class Hoi4BatchInput:
    """Load compatible images as list items for one-by-one workflow execution."""

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
    DESCRIPTION = "Rescan input/hoi4_portraits_batch on every queue and process each matching image once."

    @classmethod
    def IS_CHANGED(cls, input_folder, file_pattern):
        # A folder is external mutable state. Never reuse a cached list: every
        # queue must see additions/removals and must reach the automatic savers.
        return float("nan")

    def load_batch(self, input_folder, file_pattern):
        input_root = Path(folder_paths.get_input_directory()).resolve()
        relative_folder = Path(str(input_folder))
        if relative_folder.is_absolute() or ".." in relative_folder.parts:
            raise ValueError("Batch input folder must stay inside the ComfyUI input folder.")
        root = (input_root / relative_folder).resolve()
        if not root.is_dir():
            raise RuntimeError(f"Batch input folder does not exist: {root}")
        patterns = [item.strip() for item in str(file_pattern).split(";") if item.strip()]
        folded_patterns = [pattern.casefold() for pattern in patterns or ["*"]]
        paths = sorted(
            {
                resolved
                for path in root.iterdir()
                if path.is_file()
                and any(fnmatch(path.name.casefold(), pattern) for pattern in folded_patterns)
                and root in (resolved := path.resolve()).parents
            },
            key=lambda path: (path.name.casefold(), path.name),
        )
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
            masks.append(torch.zeros((1, image.height, image.width), dtype=torch.float32))
        return (
            [tensor.clamp(0, 1) for tensor in tensors],
            masks,
            [(relative_folder / path.name).as_posix() for path in paths],
        )


class Hoi4OutputFilename:
    """Keep the source image stem across final, processed, and restored saves."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "source_filename": ("STRING", {"default": "portrait.png"}),
                "suffix": ("STRING", {"default": ""}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("master_png", "game_png", "game_dds", "processed_png", "restored_png")
    FUNCTION = "build"
    CATEGORY = "HOI4 portraits/output"
    DESCRIPTION = "Preserve the input image name in every automatic output."

    def build(self, source_filename, suffix=""):
        return _output_filename_prefixes(source_filename, suffix)


class Hoi4BatchOutputFilename:
    """Choose one numbered batch folder and build every source-aware output path."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "source_filenames": ("STRING", {"forceInput": True}),
                "batch_name": ("STRING", {"default": ""}),
                "save_without_batch_folder": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("master_png", "game_png", "game_dds", "processed_png", "restored_png")
    OUTPUT_IS_LIST = (True, True, True, True, True)
    INPUT_IS_LIST = True
    FUNCTION = "build"
    CATEGORY = "HOI4 portraits/output"
    DESCRIPTION = "Set a batch name, or leave it blank to use batch_1, batch_2, and so on."

    @classmethod
    def IS_CHANGED(cls, source_filenames, batch_name, save_without_batch_folder):
        # A blank name creates the next numbered batch directory on every queue.
        return float("nan")

    def build(self, source_filenames, batch_name, save_without_batch_folder):
        sources = [str(item) for item in source_filenames]
        if not sources:
            raise ValueError("Batch output needs at least one source filename.")
        subfolder = _batch_output_subfolder(batch_name, save_without_batch_folder)
        master_root = "hoi4_portraits/1024x1365"
        game_root = "hoi4_portraits/156x210"
        dds_root = "hoi4_portraits/156x210/dds"
        if subfolder:
            master_root = f"{master_root}/{subfolder}"
            game_root = f"{game_root}/{subfolder}"
            dds_root = f"{game_root}/dds"
        masters: list[str] = []
        games: list[str] = []
        dds: list[str] = []
        processed: list[str] = []
        restored: list[str] = []
        for source in sources:
            output_name = _safe_output_name(source)
            masters.append(f"{master_root}/{output_name}")
            games.append(f"{game_root}/{output_name}")
            dds.append(f"{dds_root}/{output_name}")
            processed.append(f"{master_root}/processed/{output_name}")
            restored.append(f"{master_root}/restored/{output_name}")
        return masters, games, dds, processed, restored


class Hoi4RestorationCache:
    """Reuse a completed Adonis image without evaluating its lazy input again."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE", {"lazy": True}),
                "source_filename": ("STRING", {"forceInput": True}),
            },
            "hidden": {"prompt": "PROMPT", "unique_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "reuse"
    CATEGORY = "HOI4 portraits/restoration"
    DESCRIPTION = "Reuse the completed fixed-seed Adonis restoration for an unchanged source and unchanged settings."

    @staticmethod
    def _ancestor_signature(prompt, node_id):
        nodes = prompt if isinstance(prompt, dict) else {}
        active: set[str] = set()

        def visit(current_id):
            key = str(current_id)
            if key in active:
                return {"cycle": key}
            node = nodes.get(key, {})
            active.add(key)
            inputs = {}
            for name, value in sorted(node.get("inputs", {}).items()):
                if isinstance(value, list) and len(value) == 2 and str(value[0]) in nodes:
                    inputs[name] = {"node": visit(value[0]), "slot": value[1]}
                else:
                    inputs[name] = value
            active.remove(key)
            return {"class_type": node.get("class_type"), "inputs": inputs}

        cache_node = nodes.get(str(node_id), {})
        image_link = cache_node.get("inputs", {}).get("image")
        return visit(image_link[0]) if isinstance(image_link, list) and len(image_link) == 2 else {}

    @classmethod
    def _cache_path(cls, source_filename, prompt, unique_id):
        digest = hashlib.sha256()
        signature = cls._ancestor_signature(prompt, unique_id)
        digest.update(json.dumps({"schema": 1, "graph": signature}, sort_keys=True, separators=(",", ":"), default=str).encode())
        source_name = str(source_filename)
        digest.update(source_name.encode(errors="replace"))
        try:
            source_path = Path(folder_paths.get_annotated_filepath(source_name))
        except (OSError, ValueError):
            source_path = _safe_input_file(source_name)
        try:
            with source_path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
        except (OSError, ValueError):
            pass
        cache_root = Path(folder_paths.get_temp_directory()) / "hoi4_portraits" / "restoration_cache"
        return cache_root / f"{digest.hexdigest()}.npy"

    @staticmethod
    def _valid(path: Path) -> bool:
        try:
            array = np.load(path, mmap_mode="r", allow_pickle=False)
            return array.ndim == 4 and array.shape[-1] in (3, 4)
        except (OSError, ValueError):
            path.unlink(missing_ok=True)
            return False

    def check_lazy_status(self, image, source_filename, prompt=None, unique_id=None):
        path = self._cache_path(source_filename, prompt, unique_id)
        if self._valid(path):
            return []
        return ["image"] if image is None else []

    def reuse(self, image, source_filename, prompt=None, unique_id=None):
        path = self._cache_path(source_filename, prompt, unique_id)
        if image is None:
            array = np.load(path, allow_pickle=False)
            return (torch.from_numpy(np.array(array, copy=True)).clamp(0, 1),)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        with temporary.open("wb") as target:
            np.save(target, image.detach().cpu().numpy(), allow_pickle=False)
        temporary.replace(path)
        return (image,)


class Hoi4SavePNG:
    """Automatically save PNG portraits through the configured output workspace."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "filename_prefix": ("STRING", {"default": "hoi4_portraits/1024x1365/hoi4_portrait"}),
            },
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "HOI4 portraits/output"
    DESCRIPTION = "Automatically save PNG portraits in the configured portrait output folder."

    def save(self, images, filename_prefix, prompt=None, extra_pnginfo=None):
        target_folder, filename = _safe_output_prefix(filename_prefix)
        counter = _next_output_counter(target_folder, filename, ".png")
        metadata = PngImagePlugin.PngInfo()
        if prompt is not None:
            metadata.add_text("prompt", json.dumps(prompt))
        if extra_pnginfo:
            for key, value in extra_pnginfo.items():
                metadata.add_text(str(key), json.dumps(value))
        for index, tensor in enumerate(images):
            target = target_folder / f"{filename}_{counter + index:05d}.png"
            _tensor_to_pil(tensor).save(target, format="PNG", pnginfo=metadata, compress_level=4)
        return (images,)


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
                        "default": "hoi4_portraits/156x210/dds/hoi4_portrait",
                        "tooltip": "Output subfolder and filename prefix inside ComfyUI's output folder.",
                    },
                ),
                "format": (
                    ["argb8888", "dxt5"],
                    {
                        "tooltip": "Creates a HOI4-ready 156x210 DDS portrait.",
                    },
                ),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "HOI4 portraits/output"
    DESCRIPTION = "Save HOI4-ready 156x210 DDS portraits."

    def save(self, images, filename_prefix, format="argb8888"):
        if format not in {"argb8888", "dxt5"}:
            raise ValueError(f"Unsupported DDS format: {format!r}")
        prepared: list[Image.Image] = []
        for tensor in images:
            array = np.asarray(_tensor_to_pil(tensor))
            if array.ndim != 3 or array.shape[0] != 210 or array.shape[1] != 156:
                raise ValueError(
                    f"HOI4 DDS output must be 156x210; received {array.shape[1]}x{array.shape[0]}."
                )
            rgb = array[:, :, :3]
            alpha = np.full((array.shape[0], array.shape[1], 1), 255, dtype=np.uint8)
            prepared.append(Image.fromarray(np.concatenate((rgb, alpha), axis=2)))
        if not prepared:
            return (images,)
        target_folder, filename = _safe_output_prefix(filename_prefix)
        counter = _next_output_counter(target_folder, filename, ".dds")
        for index, image in enumerate(prepared):
            target = target_folder / f"{filename}_{counter + index:05d}.dds"
            if format == "dxt5":
                image.save(target, format="DDS", pixel_format="DXT5")
            else:
                image.save(target, format="DDS")
        return (images,)


NODE_CLASS_MAPPINGS = {
    "AdaptivePortraitCrop": AdaptivePortraitCrop,
    "PortraitIdentityMask": PortraitIdentityMask,
    "Hoi4SetupGuide": Hoi4SetupGuide,
    "Hoi4BackgroundReplace": Hoi4BackgroundReplace,
    "Hoi4LoadImage": Hoi4LoadImage,
    "Hoi4BatchInput": Hoi4BatchInput,
    "Hoi4OutputFilename": Hoi4OutputFilename,
    "Hoi4BatchOutputFilename": Hoi4BatchOutputFilename,
    "Hoi4RestorationCache": Hoi4RestorationCache,
    "Hoi4SavePNG": Hoi4SavePNG,
    "Hoi4SaveDDS": Hoi4SaveDDS,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AdaptivePortraitCrop": "Adaptive Portrait Crop",
    "PortraitIdentityMask": "Portrait Identity Mask",
    "Hoi4SetupGuide": "📂 Setup and downloads",
    "Hoi4BackgroundReplace": "HOI4 Optional Background Replacement",
    "Hoi4LoadImage": "HOI4 Portrait Upload",
    "Hoi4BatchInput": "HOI4 Batch Input Folder",
    "Hoi4OutputFilename": "Keep Input Filename",
    "Hoi4BatchOutputFilename": "Batch Output Folders",
    "Hoi4RestorationCache": "Reuse Restored Portrait",
    "Hoi4SavePNG": "Save Portrait PNG",
    "Hoi4SaveDDS": "HOI4 Save DDS Portrait (156x210)",
}
