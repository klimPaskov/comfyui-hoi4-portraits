from __future__ import annotations

import numpy as np
import torch
import torch.nn.functional as functional
from scipy import ndimage

import cv2
import folder_paths


ASPECT = 26 / 35
YUNET_MODEL = "face_detection_yunet_2023mar.onnx"


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
    head_top = max(0.0, y1 - 0.88 * face_height)
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
    if count and fx2 > fx1 and fy2 > fy1:
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
    # Zoom primarily removes torso below the face. The protected head/headwear
    # bounds remain hard constraints and are never weakened by this control.
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
                "zoom": (
                    "FLOAT",
                    {
                        "default": 0.90,
                        "min": 0.0,
                        "max": 1.0,
                        "step": 0.05,
                        "tooltip": "Higher values frame the face more closely while preserving the complete head, headwear, and a safety margin.",
                    },
                ),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("portrait",)
    FUNCTION = "crop"
    CATEGORY = "image/transform"
    DESCRIPTION = "Adaptive head-and-shoulders crop with protected hair and headwear."

    def crop(self, image, face_bboxes, subject_mask, zoom):
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
            box = _frame_box(width, height, face, mask.detach().float().cpu().numpy(), zoom)
            left, top, right, bottom = box
            crop = frame[top:bottom, left:right, :].permute(2, 0, 1).unsqueeze(0)
            resized = functional.interpolate(crop, size=(1120, 832), mode="bicubic", align_corners=False, antialias=True)
            outputs.append(resized.squeeze(0).permute(1, 2, 0))
        return (torch.stack(outputs).clamp(0, 1),)


NODE_CLASS_MAPPINGS = {"AdaptivePortraitCrop": AdaptivePortraitCrop}
NODE_DISPLAY_NAME_MAPPINGS = {"AdaptivePortraitCrop": "Adaptive Portrait Crop"}
