#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from portrait_pipeline.dds import DdsValidationError, convert_png_to_dds  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert an independently audited HOI4 PNG into the locked uncompressed DDS contract.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        report = convert_png_to_dds(args.input, args.output, args.audit, args.root)
    except (DdsValidationError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "BLOCKED", "exit_code": 50, "error": str(exc)}, indent=2), file=sys.stderr)
        return 50
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

