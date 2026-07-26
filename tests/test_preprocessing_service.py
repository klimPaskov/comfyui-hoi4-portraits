from __future__ import annotations

import base64
import io
import json
import threading
import unittest
import urllib.request
from pathlib import Path

from PIL import Image

from portrait_pipeline.preprocessing_service import PreprocessingBlocked, PreprocessingService, create_server
from portrait_pipeline.util import project_root


class PreprocessingServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = project_root()

    def test_health_is_blocked_until_exact_artifacts_and_runtime_exist(self):
        report = PreprocessingService(self.root).health()
        self.assertEqual(report["status"], "BLOCKED")
        self.assertTrue(report["blockers"])

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
