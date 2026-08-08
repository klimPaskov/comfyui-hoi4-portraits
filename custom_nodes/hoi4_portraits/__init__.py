from __future__ import annotations

import glob
import os
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as functional
from scipy import ndimage

import cv2
import folder_paths
from PIL import Image, ImageOps


ASPECT = 1024 / 1365
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
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("portrait",)
    FUNCTION = "crop"
    CATEGORY = "image/transform"
    DESCRIPTION = "Adaptive head-and-shoulders crop with optional headwear preservation."

    def crop(self, image, face_bboxes, subject_mask, zoom, preserve_headwear=True):
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
            resized = functional.interpolate(crop, size=(1365, 1024), mode="bicubic", align_corners=False, antialias=True)
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
    """One advanced sampler card for the portrait graph.

    The node intentionally wraps ComfyUI's own ``common_ksampler`` rather than
    implementing a second sampler.  This keeps sampler behaviour identical to
    the core node while putting the controls that users actually tune beside
    one another.  ``common_ksampler`` also installs ComfyUI's normal latent
    preview callback, so the editor shows construction previews while the
    sampling pass is running.

    The ``sampling_algorithm`` combo exposes the sampler itself (``euler`` is
    the FLUX.2 default) and ``scheduler`` exposes the step schedule (``simple``
    is the FLUX.2 default).  Advanced users can switch to any ComfyUI sampler
    or scheduler; the workflow defaults stay at the project's tuned settings.
    """

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
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                "latent_image": ("LATENT",),
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
            }
        }

    RETURN_TYPES = ("LATENT",)
    RETURN_NAMES = ("samples",)
    FUNCTION = "sample"
    CATEGORY = "HOI4 portraits/sampling"
    DESCRIPTION = (
        "Advanced FLUX.2 Klein sampler. Guidance, CFG, seed, steps, sampler, "
        "scheduler, denoise, and partial-step controls live on one node. "
        "Uses ComfyUI's live latent preview callback."
    )

    def sample(
        self,
        model,
        positive,
        negative,
        latent_image,
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
    ):
        # Imports are local so the node pack can be imported by the release
        # validator without requiring a running ComfyUI process.
        import node_helpers
        import nodes

        guided_positive = node_helpers.conditioning_set_values(
            positive, {"guidance": float(guidance)}
        )
        return nodes.common_ksampler(
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
        )


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
        max_width = max(image.width for image in images)
        max_height = max(image.height for image in images)
        tensors: list[torch.Tensor] = []
        masks: list[torch.Tensor] = []
        for image in images:
            canvas = Image.new("RGB", (max_width, max_height), (0, 0, 0))
            fitted = ImageOps.contain(image, (max_width, max_height), Image.Resampling.LANCZOS)
            canvas.paste(fitted, ((max_width - fitted.width) // 2, (max_height - fitted.height) // 2))
            array = np.asarray(canvas, dtype=np.float32) / 255.0
            tensors.append(torch.from_numpy(array))
            masks.append(torch.zeros((64, 64), dtype=torch.float32))
        return (
            torch.stack(tensors).clamp(0, 1),
            torch.stack(masks),
            "\n".join(path.name for path in paths),
        )


class Hoi4SaveDDS:
    """Save a 156x210 portrait as a HOI4-compatible DDS.

    Hearts of Iron IV reads 156x210 portrait textures in the classic DXT5
    (BC3) block-compressed DDS format with no mipmaps.  That is the format the
    in-game engine expects and the one the community tools (paint.net DXT5,
    Kadaif BC3, GIMP DXT5) produce, so dropping the output straight into a
    ``gfx/portraits`` folder will not crash the game.  Pillow writes the
    standard DDS header with the ``DXT5`` FOURCC and a single top-level
    mipmap, which keeps the file small (about 32 KB) and immediately usable.

    ``compression`` lets advanced users pick the classic uncompressed ARGB8
    profile instead (larger files, zero loss), which the engine also accepts.
    Keeping this in a node means the workflow emits the game asset in
    addition to the review PNG instead of relying on a second conversion tool.
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
                "compression": (
                    ["dxt5", "uncompressed"],
                    {
                        "tooltip": "DXT5 (BC3) is the HOI4 standard, ~32 KB, no mipmaps. 'uncompressed' writes ARGB8 which also works but is ~3x larger.",
                    },
                ),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "save"
    CATEGORY = "HOI4 portraits/output"
    DESCRIPTION = "Save 156x210 DXT5 (BC3) DDS files with no mipmaps for HOI4."

    def save(self, images, filename_prefix, compression="dxt5"):
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
            image = Image.fromarray(array[:, :, :3], mode="RGB")
            target = output_dir / prefix.parent / f"{prefix.name}_{index:03d}.dds"
            target.parent.mkdir(parents=True, exist_ok=True)
            if compression == "dxt5":
                image.save(target, format="DDS", pixel_format="DXT5")
            else:
                image.save(target, format="DDS")
            saved.append(target)
        return (images,)


NODE_CLASS_MAPPINGS = {
    "AdaptivePortraitCrop": AdaptivePortraitCrop,
    "PortraitIdentityMask": PortraitIdentityMask,
    "Hoi4PortraitSampler": Hoi4PortraitSampler,
    "Hoi4BatchInput": Hoi4BatchInput,
    "Hoi4SaveDDS": Hoi4SaveDDS,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AdaptivePortraitCrop": "Adaptive Portrait Crop",
    "PortraitIdentityMask": "Portrait Identity Mask",
    "Hoi4PortraitSampler": "HOI4 Portrait Sampler (advanced)",
    "Hoi4BatchInput": "HOI4 Batch Input Folder",
    "Hoi4SaveDDS": "HOI4 Save DDS (156x210)",
}
