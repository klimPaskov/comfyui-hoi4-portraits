"""Fail-closed local preprocessing sidecar for the ComfyUI nodes.

The sidecar deliberately owns only the CPU/GPU-heavy preprocessing operations
that are not portable inside a ComfyUI graph.  It accepts images only over a
loopback HTTP socket, keeps request bytes in memory, and never downloads a
model or source file on demand.  Every model/code artifact is checked against
``dependencies/preprocessing_lock.json`` immediately before use.

This module is importable on a clean preflight host.  Optional scientific
dependencies are imported only when an endpoint is called, so a missing
runtime reports a structured BLOCKED response instead of turning into a
partially working or silently approximate preprocessing path.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import importlib
import importlib.util
import io
import json
import re
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .constants import ExitCode
from .util import is_sha256, project_root, relative_safe_path, sha256_file


LOOPBACK_HOST = "127.0.0.1"
DEFAULT_PORT = 8790
MAX_REQUEST_BYTES = 64 * 1024 * 1024
MAX_IMAGE_BYTES = 48 * 1024 * 1024
MAX_IMAGE_PIXELS = 24_000_000
JOB_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")
SUPPORTED_FORMATS = {
    ".bin": "pytorch_bin",
    ".onnx": "onnx",
    ".safetensors": "safetensors",
    ".task": "mediapipe_task",
}


class PreprocessingBlocked(RuntimeError):
    """An expected, fail-closed inability to execute a sidecar operation."""

    def __init__(self, code: ExitCode, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}

    def response(self) -> dict[str, Any]:
        return {
            "status": "BLOCKED",
            "exit_code": int(self.code),
            "error_code": self.code.name,
            "error": str(self),
            "details": self.details,
        }


@dataclass(frozen=True)
class LockedArtifact:
    entry: dict[str, Any]
    path: Path


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _as_json_value(value: Any) -> Any:
    """Convert small scientific-library values to JSON without lossy strings."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        return _as_json_value(tolist())
    if isinstance(value, (list, tuple)):
        return [_as_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _as_json_value(item) for key, item in value.items()}
    raise TypeError(f"value is not JSON serializable: {type(value).__name__}")


class PreprocessingService:
    """In-memory YuNet/MediaPipe/BiRefNet service for a single project root."""

    def __init__(self, root: str | Path, *, device: str = "auto"):
        self.root = project_root(root)
        self.device_request = device
        self.lock_path = self.root / "dependencies" / "preprocessing_lock.json"
        self._model_lock = threading.RLock()
        self._inference_lock = threading.RLock()
        self._birefnet: tuple[Any, Any, Any] | None = None
        self._yunet: tuple[Any, Any] | None = None
        self._landmarker: tuple[Any, Any] | None = None

    def _load_lock(self) -> dict[str, Any]:
        try:
            lock = json.loads(self.lock_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PreprocessingBlocked(ExitCode.DEPENDENCY_MISSING, "preprocessing lock is unavailable", details={"type": type(exc).__name__}) from exc
        if not isinstance(lock, dict) or lock.get("status") not in {"PINNED_ARTIFACTS_NOT_INSTALLED", "RESOLVED"}:
            raise PreprocessingBlocked(ExitCode.DEPENDENCY_MISSING, "preprocessing lock is not in an executable state")
        return lock

    def _entry(self, name: str) -> dict[str, Any]:
        lock = self._load_lock()
        entries = [item for item in lock.get("dependencies", []) if isinstance(item, dict) and item.get("name") == name and item.get("mandatory")]
        if len(entries) != 1:
            raise PreprocessingBlocked(ExitCode.DEPENDENCY_MISSING, f"exactly one mandatory {name} preprocessing lock entry is required")
        return entries[0]

    def _verify_artifact(self, name: str, *, verify_source_code: bool = False) -> LockedArtifact:
        entry = self._entry(name)
        destination_value = entry.get("destination_path")
        filename = entry.get("artifact_filename")
        expected_hash = entry.get("artifact_sha256")
        expected_size = entry.get("artifact_size_bytes")
        expected_format = entry.get("artifact_format")
        if not isinstance(destination_value, str) or not isinstance(filename, str) or not is_sha256(expected_hash) or not isinstance(expected_size, int) or expected_size <= 0:
            raise PreprocessingBlocked(ExitCode.DEPENDENCY_MISSING, f"{name} preprocessing lock entry is incomplete")
        try:
            path = relative_safe_path(self.root, destination_value)
            path.relative_to((self.root / "models" / "preprocessing").resolve())
        except (ValueError, OSError) as exc:
            raise PreprocessingBlocked(ExitCode.DEPENDENCY_MISSING, f"{name} preprocessing path is outside the controlled model root") from exc
        suffix = path.suffix.casefold()
        if path.name != filename or SUPPORTED_FORMATS.get(suffix) != expected_format:
            raise PreprocessingBlocked(ExitCode.DEPENDENCY_MISSING, f"{name} preprocessing artifact format is unsupported")
        if not path.is_file():
            raise PreprocessingBlocked(ExitCode.DEPENDENCY_MISSING, f"{name} preprocessing artifact is not installed")
        actual_size = path.stat().st_size
        actual_hash = sha256_file(path)
        if actual_size != expected_size or actual_hash != expected_hash:
            raise PreprocessingBlocked(
                ExitCode.MODEL_CHECKSUM_MISMATCH,
                f"{name} preprocessing artifact does not match its lock",
                details={"path": destination_value, "actual_size_bytes": actual_size, "expected_size_bytes": expected_size, "actual_sha256": actual_hash, "expected_sha256": expected_hash},
            )
        if verify_source_code:
            source_artifacts = entry.get("source_artifacts")
            source_files = source_artifacts.get("files") if isinstance(source_artifacts, dict) else None
            if not isinstance(source_files, list) or not source_files:
                raise PreprocessingBlocked(ExitCode.DEPENDENCY_MISSING, f"{name} runtime source files are not pinned")
            for source_file in source_files:
                self._verify_source_file(name, source_file)
        return LockedArtifact(entry=entry, path=path)

    def _verify_source_file(self, model_name: str, source_file: Any) -> Path:
        if not isinstance(source_file, dict):
            raise PreprocessingBlocked(ExitCode.DEPENDENCY_MISSING, f"{model_name} source-artifact lock entry is invalid")
        destination_value = source_file.get("destination_path")
        filename = source_file.get("filename")
        expected_size = source_file.get("size_bytes")
        expected_hash = source_file.get("sha256")
        if not isinstance(destination_value, str) or not isinstance(filename, str) or not isinstance(expected_size, int) or not is_sha256(expected_hash):
            raise PreprocessingBlocked(ExitCode.DEPENDENCY_MISSING, f"{model_name} source-artifact lock fields are incomplete")
        try:
            path = relative_safe_path(self.root, destination_value)
            path.relative_to((self.root / "models" / "preprocessing").resolve())
        except (ValueError, OSError) as exc:
            raise PreprocessingBlocked(ExitCode.DEPENDENCY_MISSING, f"{model_name} source artifact escapes the controlled model root") from exc
        if path.name != filename or path.suffix.casefold() not in {".py", ".json"}:
            raise PreprocessingBlocked(ExitCode.DEPENDENCY_MISSING, f"{model_name} source artifact format is unsupported")
        if not path.is_file():
            raise PreprocessingBlocked(ExitCode.DEPENDENCY_MISSING, f"{model_name} source artifact is not installed: {destination_value}")
        actual_size = path.stat().st_size
        actual_hash = sha256_file(path)
        if actual_size != expected_size or actual_hash != expected_hash:
            raise PreprocessingBlocked(ExitCode.MODEL_CHECKSUM_MISMATCH, f"{model_name} source artifact does not match its lock", details={"path": destination_value, "actual_size_bytes": actual_size, "expected_size_bytes": expected_size, "actual_sha256": actual_hash, "expected_sha256": expected_hash})
        return path

    @staticmethod
    def _decode_png(encoded: Any) -> Any:
        if not isinstance(encoded, str) or not encoded:
            raise PreprocessingBlocked(ExitCode.SOURCE_INVALID, "request has no PNG image")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise PreprocessingBlocked(ExitCode.SOURCE_INVALID, "request image is not valid base64") from exc
        if len(raw) > MAX_IMAGE_BYTES:
            raise PreprocessingBlocked(ExitCode.SOURCE_INVALID, "request image exceeds the bounded in-memory size")
        try:
            from PIL import Image

            with Image.open(io.BytesIO(raw)) as opened:
                if opened.format != "PNG":
                    raise PreprocessingBlocked(ExitCode.SOURCE_INVALID, "preprocessing sidecar accepts PNG input only")
                width, height = opened.size
                if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                    raise PreprocessingBlocked(ExitCode.SOURCE_INVALID, "request image exceeds the bounded pixel limit")
                image = opened.convert("RGB")
                image.load()
                return image
        except PreprocessingBlocked:
            raise
        except (ImportError, OSError, ValueError) as exc:
            raise PreprocessingBlocked(ExitCode.DEPENDENCY_MISSING if isinstance(exc, ImportError) else ExitCode.SOURCE_INVALID, "request PNG could not be decoded", details={"type": type(exc).__name__}) from exc

    @staticmethod
    def _validate_request(payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise PreprocessingBlocked(ExitCode.INPUT_SCHEMA_INVALID, "sidecar request must be a JSON object")
        job_id = payload.get("job_id")
        if not isinstance(job_id, str) or not JOB_ID_RE.fullmatch(job_id):
            raise PreprocessingBlocked(ExitCode.INPUT_SCHEMA_INVALID, "sidecar request job_id is invalid")
        model = payload.get("model")
        if not isinstance(model, dict):
            raise PreprocessingBlocked(ExitCode.INPUT_SCHEMA_INVALID, "sidecar request model identity is missing")
        return payload

    @staticmethod
    def _check_model_identity(requested: dict[str, Any], entry: dict[str, Any], name: str) -> None:
        expected = {"name": name, "source_revision": entry.get("source_revision"), "artifact_sha256": entry.get("artifact_sha256")}
        if any(requested.get(key) != value for key, value in expected.items()):
            raise PreprocessingBlocked(ExitCode.MODEL_CHECKSUM_MISMATCH, f"{name} request model identity does not match the lock", details={"expected": expected, "received": requested})

    def _select_device(self, torch: Any) -> Any:
        if self.device_request != "auto":
            try:
                device = torch.device(self.device_request)
            except (RuntimeError, ValueError) as exc:
                raise PreprocessingBlocked(ExitCode.DEPENDENCY_MISSING, f"requested preprocessing device is invalid: {self.device_request}") from exc
            if device.type == "cuda" and not torch.cuda.is_available():
                raise PreprocessingBlocked(ExitCode.DEPENDENCY_MISSING, "requested CUDA preprocessing device is unavailable")
            if device.type == "mps":
                mps = getattr(torch.backends, "mps", None)
                if mps is None or not mps.is_available():
                    raise PreprocessingBlocked(ExitCode.DEPENDENCY_MISSING, "requested MPS preprocessing device is unavailable")
            return device
        if torch.cuda.is_available():
            return torch.device("cuda")
        mps = getattr(torch.backends, "mps", None)
        if mps is not None and mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")

    def _load_birefnet(self) -> tuple[Any, Any, Any]:
        with self._model_lock:
            if self._birefnet is not None:
                return self._birefnet
            artifact = self._verify_artifact("BiRefNet", verify_source_code=True)
            try:
                import torch
                from transformers import AutoModelForImageSegmentation
            except (ImportError, ModuleNotFoundError) as exc:
                raise PreprocessingBlocked(ExitCode.DEPENDENCY_MISSING, "BiRefNet runtime requires torch and transformers", details={"missing": type(exc).__name__}) from exc
            device = self._select_device(torch)
            try:
                model = AutoModelForImageSegmentation.from_pretrained(str(artifact.path.parent), trust_remote_code=True, local_files_only=True)
                model.to(device)
                # The pinned BiRefNet snapshot is stored in half precision.
                # MPS can execute that representation directly, but CPU
                # convolutions are more reliable when the model is promoted
                # to float32.  Keep the conversion explicit so the input
                # tensor and model parameters cannot silently diverge.
                if getattr(device, "type", None) == "cpu":
                    model.float()
                model.eval()
            except (OSError, RuntimeError, ValueError, ImportError) as exc:
                raise PreprocessingBlocked(ExitCode.DEPENDENCY_MISSING, "pinned BiRefNet could not be loaded from local artifacts", details={"type": type(exc).__name__}) from exc
            self._birefnet = (model, torch, device)
            return self._birefnet

    def _segment(self, image: Any) -> Any:
        model, torch, device = self._load_birefnet()
        try:
            from torchvision import transforms
            import numpy as np

            transform = transforms.Compose([
                transforms.Resize((1024, 1024)),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ])
            parameter = next(model.parameters(), None)
            dtype = getattr(parameter, "dtype", None)
            tensor = transform(image).unsqueeze(0).to(device=device, dtype=dtype or torch.float32)
            with self._inference_lock:
                with torch.inference_mode():
                    output = model(tensor)
            if hasattr(output, "logits"):
                output = output.logits
            if isinstance(output, dict):
                tensors = [value for value in output.values() if hasattr(value, "ndim")]
                output = tensors[-1] if tensors else None
            if isinstance(output, (list, tuple)):
                tensors = [value for value in output if hasattr(value, "ndim")]
                output = tensors[-1] if tensors else None
            if output is None or not hasattr(output, "ndim"):
                raise PreprocessingBlocked(ExitCode.MASK_AUDIT_FAILED, "BiRefNet returned no tensor output")
            if output.ndim == 3:
                output = output.unsqueeze(1)
            if output.ndim != 4 or output.shape[0] != 1 or output.shape[1] != 1:
                raise PreprocessingBlocked(ExitCode.MASK_AUDIT_FAILED, "BiRefNet returned an unsupported output shape", details={"shape": list(output.shape)})
            mask = torch.sigmoid(output.float())
            mask = torch.nn.functional.interpolate(mask, size=(image.height, image.width), mode="bilinear", align_corners=False)[0, 0]
            result = mask.detach().to("cpu").numpy().astype(np.float32, copy=False)
            if result.shape != (image.height, image.width) or not bool(np.isfinite(result).all()):
                raise PreprocessingBlocked(ExitCode.MASK_AUDIT_FAILED, "BiRefNet returned a non-finite or mis-sized mask")
            return result.clip(0.0, 1.0)
        except PreprocessingBlocked:
            raise
        except (ImportError, ModuleNotFoundError) as exc:
            raise PreprocessingBlocked(ExitCode.DEPENDENCY_MISSING, "BiRefNet preprocessing runtime dependencies are unavailable", details={"type": type(exc).__name__}) from exc
        except (RuntimeError, ValueError, OSError) as exc:
            raise PreprocessingBlocked(ExitCode.MASK_AUDIT_FAILED, "BiRefNet inference failed", details={"type": type(exc).__name__}) from exc

    def _load_yunet(self) -> tuple[Any, Any]:
        with self._model_lock:
            if self._yunet is not None:
                return self._yunet
            artifact = self._verify_artifact("YuNet")
            try:
                import cv2
            except (ImportError, ModuleNotFoundError) as exc:
                raise PreprocessingBlocked(ExitCode.DEPENDENCY_MISSING, "YuNet runtime requires OpenCV", details={"type": type(exc).__name__}) from exc
            if not hasattr(cv2, "FaceDetectorYN"):
                raise PreprocessingBlocked(ExitCode.DEPENDENCY_MISSING, "installed OpenCV does not expose FaceDetectorYN")
            try:
                detector = cv2.FaceDetectorYN.create(str(artifact.path), "", (320, 320), 0.6, 0.3, 5000)
            except (cv2.error, OSError, ValueError) as exc:
                raise PreprocessingBlocked(ExitCode.DEPENDENCY_MISSING, "pinned YuNet model could not be loaded", details={"type": type(exc).__name__}) from exc
            self._yunet = (detector, cv2)
            return self._yunet

    def _load_landmarker(self) -> tuple[Any, Any]:
        with self._model_lock:
            if self._landmarker is not None:
                return self._landmarker
            artifact = self._verify_artifact("MediaPipe Face Landmarker")
            try:
                import mediapipe as mp
            except (ImportError, ModuleNotFoundError) as exc:
                raise PreprocessingBlocked(ExitCode.DEPENDENCY_MISSING, "MediaPipe Face Landmarker runtime is unavailable", details={"type": type(exc).__name__}) from exc
            try:
                options = mp.tasks.vision.FaceLandmarkerOptions(
                    base_options=mp.tasks.BaseOptions(model_asset_path=str(artifact.path)),
                    running_mode=mp.tasks.vision.RunningMode.IMAGE,
                    num_faces=8,
                    output_face_blendshapes=True,
                    output_facial_transformation_matrixes=True,
                )
                landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(options)
            except (OSError, RuntimeError, ValueError, AttributeError) as exc:
                raise PreprocessingBlocked(ExitCode.DEPENDENCY_MISSING, "pinned MediaPipe Face Landmarker could not be loaded", details={"type": type(exc).__name__}) from exc
            self._landmarker = (landmarker, mp)
            return self._landmarker

    @staticmethod
    def _detect_yunet(image: Any, detector: Any, cv2: Any) -> list[dict[str, Any]]:
        import numpy as np

        rgb = np.asarray(image, dtype=np.uint8)
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        detector.setInputSize((image.width, image.height))
        try:
            _, faces = detector.detect(bgr)
        except cv2.error as exc:
            raise PreprocessingBlocked(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "YuNet face detection failed", details={"type": type(exc).__name__}) from exc
        if faces is None:
            return []
        detections: list[dict[str, Any]] = []
        for index, face in enumerate(faces):
            values = [float(value) for value in face.tolist()]
            x, y, width, height = values[:4]
            left = max(0, min(image.width - 1, int(round(x))))
            top = max(0, min(image.height - 1, int(round(y))))
            right = max(left + 1, min(image.width, int(round(x + width))))
            bottom = max(top + 1, min(image.height, int(round(y + height))))
            landmarks = []
            for point_index in range(5):
                offset = 4 + point_index * 2
                landmarks.append({"x": float(values[offset]), "y": float(values[offset + 1])})
            detections.append({"detector_index": index, "bbox_xyxy": [left, top, right, bottom], "confidence": float(values[-1]), "landmarks": landmarks})
        return detections

    @staticmethod
    def _detect_mediapipe(image: Any, landmarker: Any, mp: Any) -> list[dict[str, Any]]:
        import numpy as np

        rgb = np.ascontiguousarray(np.asarray(image, dtype=np.uint8))
        try:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect(mp_image)
        except (RuntimeError, ValueError, TypeError) as exc:
            raise PreprocessingBlocked(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "MediaPipe face landmark detection failed", details={"type": type(exc).__name__}) from exc
        faces = getattr(result, "face_landmarks", None) or []
        blendshape_sets = getattr(result, "face_blendshapes", None) or []
        matrices = getattr(result, "facial_transformation_matrixes", None) or []
        detections: list[dict[str, Any]] = []
        for index, landmarks in enumerate(faces):
            points = [{"x": float(point.x * image.width), "y": float(point.y * image.height), "z": float(point.z)} for point in landmarks]
            if not points:
                continue
            xs = [point["x"] for point in points]
            ys = [point["y"] for point in points]
            blendshapes = []
            if index < len(blendshape_sets):
                for category in blendshape_sets[index]:
                    blendshapes.append({"name": getattr(category, "category_name", None), "index": getattr(category, "index", None), "score": float(getattr(category, "score", 0.0))})
            matrix = _as_json_value(matrices[index]) if index < len(matrices) else None
            detections.append({"landmark_index": index, "bbox_xyxy": [max(0.0, min(float(image.width), min(xs))), max(0.0, min(float(image.height), min(ys))), max(0.0, min(float(image.width), max(xs))), max(0.0, min(float(image.height), max(ys)))], "landmarks": points, "blendshapes": blendshapes, "facial_transformation_matrix": matrix})
        return detections

    @staticmethod
    def _match_landmarks(detections: list[dict[str, Any]], landmark_faces: list[dict[str, Any]], image: Any) -> list[dict[str, Any]]:
        matched: list[dict[str, Any]] = []
        for detection in detections:
            left, top, right, bottom = detection["bbox_xyxy"]
            center_x = (left + right) / 2.0
            center_y = (top + bottom) / 2.0
            candidates = []
            for landmark_face in landmark_faces:
                l_left, l_top, l_right, l_bottom = landmark_face["bbox_xyxy"]
                expanded_left = l_left - (l_right - l_left) * 0.15
                expanded_top = l_top - (l_bottom - l_top) * 0.15
                expanded_right = l_right + (l_right - l_left) * 0.15
                expanded_bottom = l_bottom + (l_bottom - l_top) * 0.15
                distance = ((center_x - (l_left + l_right) / 2.0) ** 2 + (center_y - (l_top + l_bottom) / 2.0) ** 2) ** 0.5
                scale = max(1.0, (right - left + bottom - top) / 2.0)
                if expanded_left <= center_x <= expanded_right and expanded_top <= center_y <= expanded_bottom:
                    candidates.append((distance / scale, landmark_face))
            if not candidates:
                continue
            candidates.sort(key=lambda item: (item[0], item[1]["landmark_index"]))
            match = candidates[0][1]
            if match["bbox_xyxy"][2] <= match["bbox_xyxy"][0] or match["bbox_xyxy"][3] <= match["bbox_xyxy"][1]:
                continue
            matched.append({**detection, "mediapipe": match})
        return matched

    @staticmethod
    def _foreground_component(mask: Any, face_bbox: list[int], cv2: Any) -> tuple[list[int], float, float]:
        import numpy as np

        left, top, right, bottom = face_bbox
        thresholded = (mask >= 0.5).astype(np.uint8)
        height, width = thresholded.shape
        face_crop = mask[top:bottom, left:right]
        if face_crop.size == 0:
            raise PreprocessingBlocked(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "face box is empty during person association")
        face_coverage = float((face_crop >= 0.5).mean())
        center_x = max(0, min(width - 1, int(round((left + right - 1) / 2.0))))
        center_y = max(0, min(height - 1, int(round((top + bottom - 1) / 2.0))))
        center_score = float(mask[center_y, center_x])
        if face_coverage < 0.55 or center_score < 0.35:
            raise PreprocessingBlocked(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "face detection is not associated with a foreground person mask", details={"face_coverage": face_coverage, "center_score": center_score})
        labels_count, labels, stats, _ = cv2.connectedComponentsWithStats(thresholded, connectivity=8)
        label = int(labels[center_y, center_x])
        if label == 0:
            region = thresholded[top:bottom, left:right]
            candidates = []
            for candidate in range(1, labels_count):
                overlap = int(((labels[top:bottom, left:right] == candidate) & (region == 1)).sum())
                if overlap:
                    candidates.append((overlap, candidate))
            if not candidates:
                raise PreprocessingBlocked(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "foreground mask has no component containing the detected face")
            label = max(candidates)[1]
        x, y, component_width, component_height, _ = [int(value) for value in stats[label]]
        return [x, y, min(width, x + component_width), min(height, y + component_height)], face_coverage, center_score

    @staticmethod
    def _component_masks(mask: Any, face: dict[str, Any], cv2: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        """Derive auditable mask components from one locked person matte.

        BiRefNet is the only semantic matting model in the current lock.  The
        remaining masks are deterministic structural/attention masks derived
        from the selected foreground component and MediaPipe face landmarks;
        they are deliberately not presented as accessory classifiers.
        """

        import numpy as np

        if not hasattr(mask, "shape") or len(mask.shape) != 2:
            raise PreprocessingBlocked(ExitCode.MASK_AUDIT_FAILED, "BiRefNet matte has an unsupported shape")
        height, width = [int(value) for value in mask.shape]
        if height <= 0 or width <= 0 or not bool(np.isfinite(mask).all()):
            raise PreprocessingBlocked(ExitCode.MASK_AUDIT_FAILED, "BiRefNet matte is empty or non-finite")
        binary = (mask >= 0.5).astype(np.uint8)
        face_bbox_value = face.get("bbox_xyxy") if isinstance(face, dict) else None
        if not isinstance(face_bbox_value, list) or len(face_bbox_value) != 4:
            raise PreprocessingBlocked(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "mask analysis has no selected face box")
        left, top, right, bottom = [int(round(float(value))) for value in face_bbox_value]
        left = max(0, min(width - 1, left))
        top = max(0, min(height - 1, top))
        right = max(left + 1, min(width, right))
        bottom = max(top + 1, min(height, bottom))
        face_crop = mask[top:bottom, left:right]
        center_x = max(0, min(width - 1, int(round((left + right - 1) / 2.0))))
        center_y = max(0, min(height - 1, int(round((top + bottom - 1) / 2.0))))
        face_coverage = float((face_crop >= 0.5).mean()) if face_crop.size else 0.0
        center_score = float(mask[center_y, center_x])
        if face_coverage < 0.55 or center_score < 0.35:
            raise PreprocessingBlocked(
                ExitCode.FACE_NOT_FOUND_OR_UNUSABLE,
                "mask analysis cannot associate the selected face with a person component",
                details={"face_coverage": face_coverage, "center_score": center_score},
            )
        labels_count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        label = int(labels[center_y, center_x])
        if label == 0:
            region = binary[top:bottom, left:right]
            overlaps = []
            for candidate in range(1, labels_count):
                overlap = int(((labels[top:bottom, left:right] == candidate) & (region == 1)).sum())
                if overlap:
                    overlaps.append((overlap, candidate))
            if not overlaps:
                raise PreprocessingBlocked(ExitCode.MASK_AUDIT_FAILED, "mask analysis found no foreground component for the selected face")
            label = max(overlaps)[1]
        person = labels == label
        if int(person.sum()) <= 0:
            raise PreprocessingBlocked(ExitCode.MASK_AUDIT_FAILED, "selected person component is empty")
        component_x, component_y, component_width, component_height, _ = [int(value) for value in stats[label]]
        component_bbox = [component_x, component_y, min(width, component_x + component_width), min(height, component_y + component_height)]

        raw_points = face.get("landmarks") if isinstance(face, dict) else None
        points: list[tuple[float, float]] = []
        if isinstance(raw_points, list):
            for point in raw_points:
                if not isinstance(point, dict):
                    continue
                try:
                    x_value = float(point["x"])
                    y_value = float(point["y"])
                except (KeyError, TypeError, ValueError):
                    continue
                if max(width, height) > 1 and 0.0 <= x_value <= 1.0 and 0.0 <= y_value <= 1.0:
                    x_value *= width
                    y_value *= height
                points.append((max(0.0, min(width - 1.0, x_value)), max(0.0, min(height - 1.0, y_value))))
        if len(points) < 3:
            raise PreprocessingBlocked(ExitCode.MASK_AUDIT_FAILED, "MediaPipe did not provide enough landmarks for a face mask")

        def hull_mask(values: list[tuple[float, float]]) -> Any:
            canvas = np.zeros((height, width), dtype=np.uint8)
            if len(values) >= 3:
                polygon = cv2.convexHull(np.rint(np.asarray(values, dtype=np.float32)).astype(np.int32).reshape((-1, 1, 2)))
                cv2.fillConvexPoly(canvas, polygon, 1)
            elif values:
                center = tuple(int(round(value)) for value in values[0])
                cv2.circle(canvas, center, max(2, min(width, height) // 32), 1, -1)
            return canvas.astype(bool)

        face_mask = hull_mask(points)
        if not bool(face_mask.any()):
            raise PreprocessingBlocked(ExitCode.MASK_AUDIT_FAILED, "MediaPipe face landmarks produced an empty face mask")
        face_inside_ratio = float((face_mask & person).sum() / max(1, face_mask.sum()))
        if face_inside_ratio < 0.90:
            raise PreprocessingBlocked(
                ExitCode.MASK_AUDIT_FAILED,
                "selected face is not contained by the person mask",
                details={"face_inside_person_ratio": face_inside_ratio},
            )

        person_uint8 = person.astype(np.uint8)
        erosion_kernel = np.ones((3, 3), dtype=np.uint8)
        eroded = cv2.erode(person_uint8, erosion_kernel, iterations=1).astype(bool)
        boundary_ring = person & ~eroded
        person_alpha = np.asarray(mask, dtype=np.float32).clip(0.0, 1.0) * person.astype(np.float32)
        background = 1.0 - person_alpha

        face_left, face_top, face_right, face_bottom = left, top, right, bottom
        face_width = max(1, face_right - face_left)
        face_height = max(1, face_bottom - face_top)
        head_region = np.zeros((height, width), dtype=np.uint8)
        head_left = max(0, int(round(face_left - 0.85 * face_width)))
        head_top = max(0, int(round(face_top - 1.25 * face_height)))
        head_right = min(width, int(round(face_right + 0.85 * face_width)))
        head_bottom = min(height, int(round(face_bottom + 0.55 * face_height)))
        cv2.rectangle(head_region, (head_left, head_top), (max(head_left, head_right - 1), max(head_top, head_bottom - 1)), 1, -1)
        face_dilated = cv2.dilate(face_mask.astype(np.uint8), np.ones((9, 9), dtype=np.uint8), iterations=1).astype(bool)
        hair_hat_boundary = ((face_dilated & ~face_mask) | (boundary_ring & head_region.astype(bool))) & person & head_region.astype(bool)

        def indexed_points(indices: list[int]) -> list[tuple[float, float]]:
            return [points[index] for index in indices if 0 <= index < len(points)]

        accessory_attention = np.zeros((height, width), dtype=np.uint8).astype(bool)
        for indices in ([33, 133, 159, 145, 362, 263, 386, 374], [61, 291, 0, 17, 13, 14, 78, 308], [127, 356, 234, 454]):
            zone_points = indexed_points(indices)
            zone = hull_mask(zone_points)
            if zone.any():
                accessory_attention |= cv2.dilate(zone.astype(np.uint8), np.ones((11, 11), dtype=np.uint8), iterations=1).astype(bool)
        shoulder_top = min(height - 1, max(face_bottom, int(round(face_bottom + 0.35 * face_height))))
        shoulder_bottom = min(height, max(shoulder_top + 1, int(round(face_bottom + 2.2 * face_height))))
        shoulder_left = max(0, int(round((face_left + face_right) / 2.0 - 1.7 * face_width)))
        shoulder_right = min(width, int(round((face_left + face_right) / 2.0 + 1.7 * face_width)))
        if shoulder_right > shoulder_left and shoulder_bottom > shoulder_top:
            shoulder_mask = np.zeros((height, width), dtype=np.uint8)
            cv2.rectangle(shoulder_mask, (shoulder_left, shoulder_top), (shoulder_right - 1, shoulder_bottom - 1), 1, -1)
            accessory_attention |= shoulder_mask.astype(bool)
        accessory_attention &= person

        arrays = {
            "person_alpha": np.rint(person_alpha * 255.0).astype(np.uint8),
            "hard_interior": (eroded.astype(np.uint8) * 255),
            "face": (face_mask.astype(np.uint8) * 255),
            "hair_hat_boundary": (hair_hat_boundary.astype(np.uint8) * 255),
            "accessory_attention": (accessory_attention.astype(np.uint8) * 255),
            "background": np.rint(background * 255.0).astype(np.uint8),
            "boundary_ring": (boundary_ring.astype(np.uint8) * 255),
        }
        metadata = {
            "schema_version": "1.0.0",
            "status": "PASS_STRUCTURAL_COMPONENTS",
            "selected_face_bbox_xyxy": [left, top, right, bottom],
            "selected_person_component_bbox_xyxy": component_bbox,
            "connected_component_count": max(0, int(labels_count) - 1),
            "face_coverage": face_coverage,
            "face_center_mask_score": center_score,
            "face_inside_person_ratio": face_inside_ratio,
            "hard_mask_threshold": 0.5,
            "erosion": "3x3_one_iteration",
            "semantics": {
                "person_alpha": "continuous BiRefNet matte restricted to selected person component",
                "hard_interior": "eroded binary selected person component",
                "face": "MediaPipe landmark convex hull",
                "hair_hat_boundary": "structural boundary/attention mask; not a semantic hair-or-hat classifier",
                "accessory_attention": "landmark corridor attention mask for glasses, facial hair, jewelry, medals, and insignia; not an accessory classifier",
                "background": "inverse of restricted person alpha",
                "boundary_ring": "selected person component minus one-pixel morphological interior",
            },
            "alternative_matting_comparison": {
                "status": "BLOCKED_UNTIL_APPROVED_ALTERNATIVE",
                "primary_model": "BiRefNet",
                "policy": "component masks do not authorize production promotion until a qualified alternative comparison is recorded",
            },
        }
        return arrays, metadata

    def _subject(self, payload: dict[str, Any]) -> dict[str, Any]:
        entry = self._verify_artifact("YuNet")
        self._check_model_identity(payload["model"], entry.entry, "YuNet")
        image = self._decode_png(payload.get("image_png_base64"))
        detector, cv2 = self._load_yunet()
        landmarker, mp = self._load_landmarker()
        with self._model_lock:
            detections = self._detect_yunet(image, detector, cv2)
            landmark_faces = self._detect_mediapipe(image, landmarker, mp)
        if not detections or not landmark_faces:
            raise PreprocessingBlocked(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "YuNet and MediaPipe found no common face")
        matched = self._match_landmarks(detections, landmark_faces, image)
        if not matched:
            raise PreprocessingBlocked(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "YuNet detections could not be matched to MediaPipe landmarks")
        mask = self._segment(image)
        import numpy as np

        subjects: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for candidate in matched:
            try:
                person_bbox, face_coverage, center_score = self._foreground_component(mask, candidate["bbox_xyxy"], cv2)
            except PreprocessingBlocked as exc:
                rejected.append({"detector_index": candidate["detector_index"], "reason": str(exc), "error_code": exc.code.name, "details": exc.details})
                continue
            mediapipe_face = candidate.pop("mediapipe")
            subjects.append({
                "subject_index": len(subjects),
                "bbox_xyxy": candidate["bbox_xyxy"],
                "confidence": candidate["confidence"],
                "yunet_landmarks": candidate["landmarks"],
                "person_association": {
                    "method": "BiRefNet_foreground_contains_face",
                    "person_bbox_xyxy": person_bbox,
                    "face_mask_coverage": face_coverage,
                    "face_center_mask_score": center_score,
                    "threshold": {"binary_mask": 0.5, "minimum_face_coverage": 0.55, "minimum_center_score": 0.35},
                    "calibration_status": "STRUCTURAL_ASSOCIATION_NOT_IDENTITY_CALIBRATION",
                },
                "landmarks": mediapipe_face,
            })
        if not subjects:
            raise PreprocessingBlocked(ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "no face was associated with a foreground person mask", details={"rejected": rejected})
        response: dict[str, Any] = {
            "status": "PASS",
            "analysis_status": "PASS",
            "model": {"name": "YuNet", "source_revision": entry.entry.get("source_revision"), "artifact_sha256": entry.entry.get("artifact_sha256")},
            "association_model": {"name": "BiRefNet", "source_revision": self._entry("BiRefNet").get("source_revision"), "artifact_sha256": self._entry("BiRefNet").get("artifact_sha256")},
            "landmark_model": {"name": "MediaPipe Face Landmarker", "source_revision": self._entry("MediaPipe Face Landmarker").get("source_revision"), "artifact_sha256": self._entry("MediaPipe Face Landmarker").get("artifact_sha256")},
            "subjects": subjects,
            "rejected_detections": rejected,
            "selection_policy": "selected only when exactly one foreground-associated subject remains; otherwise caller must use face_index or fail closed",
        }
        if len(subjects) == 1:
            response["selected"] = subjects[0]
        return response

    def _mask(self, payload: dict[str, Any]) -> dict[str, Any]:
        artifact = self._verify_artifact("BiRefNet", verify_source_code=True)
        self._check_model_identity(payload["model"], artifact.entry, "BiRefNet")
        image = self._decode_png(payload.get("image_png_base64"))
        mask = self._segment(image)
        yunet_artifact = self._verify_artifact("YuNet")
        landmarker_artifact = self._verify_artifact("MediaPipe Face Landmarker")
        yunet_model, cv2 = self._load_yunet()
        landmarker_model, mp = self._load_landmarker()
        with self._model_lock:
            detections = self._detect_yunet(image, yunet_model, cv2)
            landmark_faces = self._detect_mediapipe(image, landmarker_model, mp)
        matched = self._match_landmarks(detections, landmark_faces, image)
        if len(matched) != 1:
            raise PreprocessingBlocked(ExitCode.AMBIGUOUS_SUBJECT if len(matched) > 1 else ExitCode.FACE_NOT_FOUND_OR_UNUSABLE, "mask analysis requires exactly one matched face", details={"matched_face_count": len(matched)})
        face = matched[0]["mediapipe"]
        components, contract = self._component_masks(mask, face, cv2)
        from PIL import Image

        values = components["person_alpha"]
        mask_image = Image.frombytes("L", (image.width, image.height), values.tobytes())
        output = io.BytesIO()
        mask_image.save(output, format="PNG", optimize=False)
        encoded_components: dict[str, dict[str, Any]] = {}
        for name, component in components.items():
            component_image = Image.frombytes("L", (image.width, image.height), component.tobytes())
            component_output = io.BytesIO()
            component_image.save(component_output, format="PNG", optimize=False)
            encoded_components[name] = {
                "png_base64": base64.b64encode(component_output.getvalue()).decode("ascii"),
                "width": image.width,
                "height": image.height,
                "minimum": int(component.min()),
                "maximum": int(component.max()),
                "mean": float(component.mean()),
                "binary": name not in {"person_alpha", "background"},
                "semantics": contract["semantics"][name],
            }
        return {
            "status": "PASS",
            "analysis_status": "PASS",
            "model": {"name": "BiRefNet", "source_revision": artifact.entry.get("source_revision"), "artifact_sha256": artifact.entry.get("artifact_sha256")},
            "mask_png_base64": base64.b64encode(output.getvalue()).decode("ascii"),
            "mask_stats": {"width": image.width, "height": image.height, "minimum": float(values.min()), "maximum": float(values.max()), "mean": float(values.mean())},
            "component_masks": encoded_components,
            "mask_contract": contract,
            "inference": {"device": str(self._birefnet[2]) if self._birefnet is not None else "unknown", "thresholding": "selected component at 0.5; person alpha remains continuous", "face_model": {"name": "YuNet", "source_revision": yunet_artifact.entry.get("source_revision"), "artifact_sha256": yunet_artifact.entry.get("artifact_sha256")}, "landmark_model": {"name": "MediaPipe Face Landmarker", "source_revision": landmarker_artifact.entry.get("source_revision"), "artifact_sha256": landmarker_artifact.entry.get("artifact_sha256")}},
        }

    def health(self) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        for name, source_code in (("BiRefNet", True), ("YuNet", False), ("MediaPipe Face Landmarker", False)):
            try:
                artifact = self._verify_artifact(name, verify_source_code=source_code)
                checks.append({"name": name, "status": "PASS", "path": str(artifact.path.relative_to(self.root))})
            except PreprocessingBlocked as exc:
                checks.append({"name": name, "status": "BLOCKED", "error_code": exc.code.name, "error": str(exc), "details": exc.details})
        for module in ("torch", "transformers", "torchvision", "cv2", "mediapipe", "numpy"):
            checks.append({"name": f"python:{module}", "status": "PASS" if _module_available(module) else "BLOCKED", "available": _module_available(module)})
        blockers = [item for item in checks if item["status"] != "PASS"]
        return {"status": "PASS" if not blockers else "BLOCKED", "service": "hoi4-preprocessing-loopback", "binding": f"http://{LOOPBACK_HOST}", "checks": checks, "blockers": blockers}

    def handle(self, path: str, payload: Any) -> dict[str, Any]:
        try:
            if path == "/v1/subject":
                request = self._validate_request(payload)
                return self._subject(request)
            if path == "/v1/mask":
                request = self._validate_request(payload)
                return self._mask(request)
            raise PreprocessingBlocked(ExitCode.INPUT_SCHEMA_INVALID, "unknown preprocessing endpoint")
        except PreprocessingBlocked as exc:
            return exc.response()
        except (OSError, RuntimeError, ValueError, TypeError, ImportError) as exc:
            return PreprocessingBlocked(ExitCode.INTERNAL_ERROR, "preprocessing sidecar failed closed on an unexpected error", details={"type": type(exc).__name__}).response()

    def close(self) -> None:
        with self._model_lock:
            if self._landmarker is not None:
                close = getattr(self._landmarker[0], "close", None)
                if callable(close):
                    close()
                self._landmarker = None
            self._yunet = None
            self._birefnet = None


class _PreprocessingHandler(BaseHTTPRequestHandler):
    service: PreprocessingService

    def _write_json(self, status: int, value: dict[str, Any]) -> None:
        body = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib HTTP handler API
        if self.path != "/health":
            self._write_json(int(HTTPStatus.NOT_FOUND), {"status": "BLOCKED", "error_code": "INPUT_SCHEMA_INVALID", "error": "unknown preprocessing endpoint"})
            return
        self._write_json(int(HTTPStatus.OK), self.service.health())

    def do_POST(self) -> None:  # noqa: N802 - stdlib HTTP handler API
        length_value = self.headers.get("Content-Length")
        try:
            length = int(length_value or "-1")
        except ValueError:
            length = -1
        if length < 0 or length > MAX_REQUEST_BYTES:
            self._write_json(int(HTTPStatus.REQUEST_ENTITY_TOO_LARGE), {"status": "BLOCKED", "exit_code": int(ExitCode.INPUT_SCHEMA_INVALID), "error_code": "INPUT_SCHEMA_INVALID", "error": "request body is outside the bounded size"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._write_json(int(HTTPStatus.BAD_REQUEST), PreprocessingBlocked(ExitCode.INPUT_SCHEMA_INVALID, "request body is not valid JSON", details={"type": type(exc).__name__}).response())
            return
        response = self.service.handle(self.path, payload)
        self._write_json(int(HTTPStatus.OK), response)

    def log_message(self, format: str, *args: Any) -> None:
        # Do not write request payloads, query strings, or source identifiers to
        # stdout; the bootstrap log is evidence, not an image-data log.
        return


class _PreprocessingServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], service: PreprocessingService):
        super().__init__(server_address, _PreprocessingHandler)
        self.service = service
        _PreprocessingHandler.service = service


def create_server(root: str | Path, *, host: str = LOOPBACK_HOST, port: int = DEFAULT_PORT, device: str = "auto") -> _PreprocessingServer:
    if host != LOOPBACK_HOST:
        raise PreprocessingBlocked(ExitCode.REMOTE_AUTH_OR_TRANSPORT_FAILED, "preprocessing sidecar must bind to 127.0.0.1")
    if not isinstance(port, int) or (port != 0 and not 1024 <= port <= 65535):
        raise PreprocessingBlocked(ExitCode.INPUT_SCHEMA_INVALID, "preprocessing sidecar port is outside the bounded range")
    return _PreprocessingServer((host, port), PreprocessingService(root, device=device))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the fail-closed HOI4 preprocessing loopback sidecar.")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--host", default=LOOPBACK_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--health-check", action="store_true")
    args = parser.parse_args(argv)
    try:
        service = PreprocessingService(args.root, device=args.device)
        if args.health_check:
            health = service.health()
            print(json.dumps(health, indent=2, ensure_ascii=False))
            return 0 if health["status"] == "PASS" else int(ExitCode.DEPENDENCY_MISSING)
        server = create_server(args.root, host=args.host, port=args.port, device=args.device)
    except PreprocessingBlocked as exc:
        print(json.dumps(exc.response(), indent=2, ensure_ascii=False))
        return int(exc.code)
    except OSError as exc:
        blocked = PreprocessingBlocked(ExitCode.DEPENDENCY_MISSING, "preprocessing sidecar could not initialize", details={"type": type(exc).__name__})
        print(json.dumps(blocked.response(), indent=2, ensure_ascii=False))
        return int(blocked.code)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
        server.service.close()
    return int(ExitCode.SUCCESS)


if __name__ == "__main__":
    raise SystemExit(main())
