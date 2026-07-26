from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def main() -> int:
    token = os.environ.get("PORTRAIT_GATEWAY_TOKEN")
    if not token:
        return 60
    preprocessing_port = os.environ.get("PORTRAIT_PREPROCESSING_PORT", "8790")
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{preprocessing_port}/health", timeout=5) as response:
            preprocessing = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return 20
    if not isinstance(preprocessing, dict) or preprocessing.get("status") != "PASS":
        return 20
    host = os.environ.get("PORTRAIT_GATEWAY_HOST_CHECK", "127.0.0.1")
    port = os.environ.get("PORTRAIT_GATEWAY_PORT", "8765")
    for route in ("/v1/health", "/v1/capabilities"):
        request = urllib.request.Request(f"http://{host}:{port}{route}", headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError):
            return 60
        if not isinstance(payload, dict):
            return 70
        result = payload.get("result", payload)
        if not isinstance(result, dict) or result.get("status") != "PASS":
            return 20
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
