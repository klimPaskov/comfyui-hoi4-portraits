#!/usr/bin/env python3
"""Convert a 156 x 210 PNG to HOI4-compatible uncompressed BGRA DDS."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import tempfile
from pathlib import Path

WIDTH = 156
HEIGHT = 210
DDSD_CAPS = 0x1
DDSD_HEIGHT = 0x2
DDSD_WIDTH = 0x4
DDSD_PITCH = 0x8
DDSD_PIXELFORMAT = 0x1000
DDPF_ALPHAPIXELS = 0x1
DDPF_RGB = 0x40
DDSCAPS_TEXTURE = 0x1000


def _header() -> bytes:
    values = [
        124,
        DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PITCH | DDSD_PIXELFORMAT,
        HEIGHT,
        WIDTH,
        WIDTH * 4,
        0,
        0,
        *([0] * 11),
        32,
        DDPF_RGB | DDPF_ALPHAPIXELS,
        0,
        32,
        0x00FF0000,
        0x0000FF00,
        0x000000FF,
        0xFF000000,
        DDSCAPS_TEXTURE,
        0,
        0,
        0,
        0,
    ]
    return b"DDS " + struct.pack("<31I", *values)


def convert(source: Path, destination: Path) -> dict[str, object]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required: python -m pip install 'Pillow>=10'") from exc
    if not source.is_file():
        raise RuntimeError(f"input PNG does not exist: {source}")
    with Image.open(source) as opened:
        image = opened.convert("RGBA")
        if image.size != (WIDTH, HEIGHT):
            raise RuntimeError(f"input must be {WIDTH} x {HEIGHT}, got {image.width} x {image.height}")
        red, green, blue, alpha = image.split()
        pixels = Image.merge("RGBA", (blue, green, red, alpha)).tobytes()
    payload = _header() + pixels
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
        temporary.write(payload)
        temporary_path = Path(temporary.name)
    temporary_path.replace(destination)
    return {
        "status": "PASS",
        "input": str(source),
        "output": str(destination),
        "width": WIDTH,
        "height": HEIGHT,
        "format": "uncompressed 32-bit BGRA DDS",
        "size_bytes": destination.stat().st_size,
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = convert(args.input, args.output)
    except (OSError, RuntimeError) as exc:
        parser.exit(1, f"error: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
