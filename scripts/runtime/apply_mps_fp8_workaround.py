#!/usr/bin/env python3
"""Apply or verify the reversible local FP8-on-MPS fallback.

This is a local compatibility workaround for the pinned ComfyUI checkout. It
does not change a model file or the immutable project LoRA. Apple MPS cannot
materialize FP8 tensors, so the two affected conversions are performed on CPU
and the supported result is returned to MPS. The backup files are created next
to the two runtime files before a change is made.

The workaround is not an upstream ComfyUI feature. Re-run this script with
``--check`` after a runtime update and with ``--apply`` only after reviewing
the detected files.
"""

from __future__ import annotations

import argparse
import py_compile
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FLOAT_PATH = ROOT / "comfyui" / "comfy" / "float.py"
KITCHEN_PATH = ROOT / ".venv" / "lib" / "python3.12" / "site-packages" / "comfy_kitchen" / "backends" / "eager" / "quantization.py"

FLOAT_MARKER = 'on_mps = value.device.type == "mps"'
KITCHEN_MARKER = 'target_device = x.device'


def status(path: Path, marker: str) -> dict[str, object]:
    exists = path.is_file()
    text = path.read_text(encoding="utf-8") if exists else ""
    return {"path": str(path.relative_to(ROOT)), "exists": exists, "patched": marker in text}


def apply_patch(path: Path, marker: str, replacement: str) -> None:
    if not path.is_file():
        raise SystemExit(f"missing runtime file: {path}")
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    old, new = replacement.split("\n---PATCH-SPLIT---\n", 1)
    if old not in text:
        raise SystemExit(f"expected patch anchor not found: {path}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(f"{path.name}.bak_mps_fp8_{stamp}")
    shutil.copy2(path, backup)
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    py_compile.compile(str(path), doraise=True)
    print(f"patched {path} (backup: {backup})")


FLOAT_REPLACEMENT = '''    if dtype == torch.float8_e4m3fn or dtype == torch.float8_e5m2:
        generator = torch.Generator(device=value.device)
---PATCH-SPLIT---
    if dtype == torch.float8_e4m3fn or dtype == torch.float8_e5m2:
        on_mps = value.device.type == "mps"
        if on_mps:
            value = value.cpu()
        generator = torch.Generator(device=value.device)'''

KITCHEN_REPLACEMENT = '''    dq_tensor = x.to(dtype=output_type) * scale.to(dtype=output_type)
    return dq_tensor
---PATCH-SPLIT---
    target_device = x.device
    if x.device.type == "mps":
        x = x.cpu()
        scale = scale.cpu()
    dq_tensor = x.to(dtype=output_type) * scale.to(dtype=output_type)
    if target_device.type == "mps":
        dq_tensor = dq_tensor.to(target_device)
    return dq_tensor'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="apply the reviewed local patch")
    parser.add_argument("--check", action="store_true", help="verify the patch markers")
    args = parser.parse_args()
    if not args.apply and not args.check:
        parser.error("choose --check or --apply")
    if args.apply:
        apply_patch(FLOAT_PATH, FLOAT_MARKER, FLOAT_REPLACEMENT)
        apply_patch(KITCHEN_PATH, KITCHEN_MARKER, KITCHEN_REPLACEMENT)
    reports = [status(FLOAT_PATH, FLOAT_MARKER), status(KITCHEN_PATH, KITCHEN_MARKER)]
    for report in reports:
        print(report)
    return 0 if all(item["exists"] and item["patched"] for item in reports) else 2


if __name__ == "__main__":
    raise SystemExit(main())
