#!/usr/bin/env python3
"""Convert a 156 x 210 PNG to an HOI4-ready DXT5 (BC3) DDS file.

This is a convenience converter for files produced outside ComfyUI. The
workflows themselves already save the DDS via the Hoi4SaveDDS node, which uses
the same DXT5, no-mipmap profile.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

WIDTH = 156
HEIGHT = 210


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("png", type=Path, help="Input 156x210 PNG")
    parser.add_argument("--output", type=Path, default=None, help="Output .dds path (default: same name with .dds)")
    parser.add_argument("--uncompressed", action="store_true", help="Write uncompressed ARGB8 instead of DXT5")
    args = parser.parse_args(argv)

    image = Image.open(args.png).convert("RGB")
    if image.size != (WIDTH, HEIGHT):
        parser.error(f"input must be {WIDTH}x{HEIGHT}; got {image.size[0]}x{image.size[1]}")
    output = args.output or args.png.with_suffix(".dds")
    if args.uncompressed:
        image.save(output, format="DDS")
    else:
        image.save(output, format="DDS", pixel_format="DXT5")
    print(f"Wrote {output} ({output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
