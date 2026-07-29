from __future__ import annotations

import base64
import io
import json
import threading
import unittest
import urllib.request
from pathlib import Path

from PIL import Image

from portrait_pipeline.preprocessing_service import LockedArtifact, PreprocessingBlocked, PreprocessingService, create_server
from portrait_pipeline.util import project_root


class PreprocessingServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = project_root()

    def test_health_passes_after_exact_artifacts_and_runtime_install(self):
        report = PreprocessingService(self.root).health()
        self.assertEqual(report["status"], "PASS")
        self.assertFalse(report["blockers"])

    def test_mask_returns_complete_structural_component_contract(self):
        import cv2
        import numpy as np

        service = PreprocessingService(self.root)
        image_buffer = io.BytesIO()
        Image.new("RGB", (16, 16), (120, 120, 120)).save(image_buffer, format="PNG")
        revisions = {
            "BiRefNet": "birefnet-revision",
            "YuNet": "yunet-revision",
            "MediaPipe Face Landmarker": "landmarker-revision",
        }

        def fake_verify(name, **_kwargs):
            return LockedArtifact(entry={"source_revision": revisions[name], "artifact_sha256": "a" * 64}, path=self.root / "README.md")

        service._verify_artifact = fake_verify
        service._segment = lambda _image: np.full((16, 16), 0.9, dtype=np.float32)
        service._load_yunet = lambda: (object(), cv2)
        service._load_landmarker = lambda: (object(), object())
        service._detect_yunet = lambda *_args: [{"detector_index": 0, "bbox_xyxy": [4, 4, 12, 12], "confidence": 0.99, "landmarks": []}]
        service._detect_mediapipe = lambda *_args: [{"landmark_index": 0, "bbox_xyxy": [4.0, 4.0, 12.0, 12.0], "landmarks": [{"x": 4.0, "y": 4.0}, {"x": 12.0, "y": 4.0}, {"x": 12.0, "y": 12.0}, {"x": 4.0, "y": 12.0}]}]
        payload = {
            "job_id": "component-contract-001",
            "model": {"name": "BiRefNet", "source_revision": revisions["BiRefNet"], "artifact_sha256": "a" * 64},
            "image_png_base64": base64.b64encode(image_buffer.getvalue()).decode("ascii"),
        }
        response = service.handle("/v1/mask", payload)
        self.assertEqual(response["status"], "PASS")
        self.assertEqual(response["mask_contract"]["status"], "PASS_STRUCTURAL_COMPONENTS")
        self.assertEqual(set(response["component_masks"]), {"person_alpha", "hard_interior", "face", "hair_hat_boundary", "accessory_attention", "background", "boundary_ring"})
        for descriptor in response["component_masks"].values():
            with Image.open(io.BytesIO(base64.b64decode(descriptor["png_base64"]))) as component:
                self.assertEqual(component.size, (16, 16))

    def test_endpoint_rejects_invalid_job_before_model_use(self):
        service = PreprocessingService(self.root)
        response = service.handle("/v1/mask", {"job_id": "<placeholder>", "model": {}})
        self.assertEqual(response["status"], "BLOCKED")
        self.assertEqual(response["error_code"], "INPUT_SCHEMA_INVALID")

    def test_missing_model_cannot_return_a_false_pass(self):
        image_buffer = io.BytesIO()
        Image.new("RGB", (2, 2), (1, 2, 3)).save(image_buffer, format="PNG")
        payload = {
            "job_id": "service-test-001",
            "model": {"name": "BiRefNet", "source_revision": "x", "artifact_sha256": "x"},
            "image_png_base64": base64.b64encode(image_buffer.getvalue()).decode("ascii"),
        }
        response = PreprocessingService(self.root).handle("/v1/mask", payload)
        self.assertEqual(response["status"], "BLOCKED")
        self.assertNotEqual(response.get("status"), "PASS")

    def test_non_loopback_bind_is_rejected(self):
        with self.assertRaises(PreprocessingBlocked) as context:
            create_server(self.root, host="0.0.0.0")
        self.assertEqual(context.exception.code.name, "REMOTE_AUTH_OR_TRANSPORT_FAILED")

    def test_loopback_health_endpoint_does_not_expose_request_data(self):
        server = create_server(self.root, port=0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/health", timeout=5) as response:
                body = json.loads(response.read().decode("utf-8"))
            self.assertIn(body["status"], {"PASS", "BLOCKED"})
            self.assertNotIn("image_png_base64", json.dumps(body))
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)
            server.service.close()


if __name__ == "__main__":
    unittest.main()
