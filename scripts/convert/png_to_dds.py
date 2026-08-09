#!/usr/bin/env python3
"""Convert a 156 x 210 PNG to a vanilla-style HOI4 portrait DDS file.

This is a convenience converter for files produced outside ComfyUI. The
workflows themselves already save the DDS via the Hoi4SaveDDS node, which uses
the same A8R8G8B8, no-mipmap profile.
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
    parser.add_argument("--dxt5", action="store_true", help="Use legacy DXT5 instead of vanilla portrait A8R8G8B8")
    args = parser.parse_args(argv)

    image = Image.open(args.png).convert("RGBA")
    if image.size != (WIDTH, HEIGHT):
        parser.error(f"input must be {WIDTH}x{HEIGHT}; got {image.size[0]}x{image.size[1]}")
    output = args.output or args.png.with_suffix(".dds")
    if args.dxt5:
        image.save(output, format="DDS", pixel_format="DXT5")
    else:
        image.save(output, format="DDS")
    print(f"Wrote {output} ({output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
