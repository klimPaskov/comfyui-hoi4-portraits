from __future__ import annotations

import json
import os
import struct
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .constants import ExitCode, FINAL_HEIGHT, FINAL_WIDTH
from .contracts import validate_audit
from .util import sha256_file


DDS_HEADER_SIZE = 128
DDS_FILE_SIZE = DDS_HEADER_SIZE + FINAL_WIDTH * FINAL_HEIGHT * 4
DDSD_CAPS = 0x00000001
DDSD_HEIGHT = 0x00000002
DDSD_WIDTH = 0x00000004
DDSD_PITCH = 0x00000008
DDSD_PIXELFORMAT = 0x00001000
DDPF_ALPHAPIXELS = 0x00000001
DDPF_RGB = 0x00000040
DDSCAPS_TEXTURE = 0x00001000


class DdsValidationError(RuntimeError):
    exit_code = ExitCode.DDS_VALIDATION_FAILED


@dataclass(frozen=True)
class DdsHeader:
    width: int
    height: int
    pitch: int
    mipmap_count: int
    pixel_format_flags: int
    fourcc: int
    rgb_bit_count: int
    red_mask: int
    green_mask: int
    blue_mask: int
    alpha_mask: int
    caps: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "pitch": self.pitch,
            "mipmap_count": self.mipmap_count,
            "pixel_format_flags": self.pixel_format_flags,
            "fourcc": f"0x{self.fourcc:08x}",
            "rgb_bit_count": self.rgb_bit_count,
            "red_mask": f"0x{self.red_mask:08x}",
            "green_mask": f"0x{self.green_mask:08x}",
            "blue_mask": f"0x{self.blue_mask:08x}",
            "alpha_mask": f"0x{self.alpha_mask:08x}",
            "caps": f"0x{self.caps:08x}",
        }


def build_dds_header(width: int, height: int) -> bytes:
    flags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PITCH | DDSD_PIXELFORMAT
    values = [
        124,
        flags,
        height,
        width,
        width * 4,
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
    if len(values) != 31:
        raise DdsValidationError("internal DDS header has the wrong number of DWORDs")
    return b"DDS " + struct.pack("<31I", *values)


def parse_dds_header(data: bytes) -> DdsHeader:
    if len(data) < DDS_HEADER_SIZE or data[:4] != b"DDS ":
        raise DdsValidationError("DDS magic or header is invalid")
    values = struct.unpack("<31I", data[4:128])
    if values[0] != 124 or values[18] != 32:
        raise DdsValidationError("unexpected DDS header sizes")
    return DdsHeader(
        width=values[3], height=values[2], pitch=values[4], mipmap_count=values[6],
        pixel_format_flags=values[19], fourcc=values[20], rgb_bit_count=values[21],
        red_mask=values[22], green_mask=values[23], blue_mask=values[24], alpha_mask=values[25], caps=values[26],
    )


def rgba_to_bgra_bytes(image: Any) -> bytes:
    from PIL import Image as PillowImage  # type: ignore

    r, g, b, a = image.convert("RGBA").split()
    return PillowImage.merge("RGBA", (b, g, r, a)).tobytes()


def bgra_to_rgba_bytes(pixel_data: bytes, width: int, height: int) -> bytes:
    expected = width * height * 4
    if len(pixel_data) != expected:
        raise DdsValidationError(f"pixel payload size {len(pixel_data)} != {expected}")
    output = bytearray(expected)
    for index in range(0, expected, 4):
        b, g, r, a = pixel_data[index:index + 4]
        output[index:index + 4] = bytes((r, g, b, a))
    return bytes(output)


def decode_dds(path: str | Path) -> tuple[DdsHeader, bytes]:
    payload = Path(path).read_bytes()
    header = parse_dds_header(payload)
    if header.width != FINAL_WIDTH or header.height != FINAL_HEIGHT:
        raise DdsValidationError(f"DDS dimensions must be {FINAL_WIDTH}x{FINAL_HEIGHT}")
    if header.pitch != FINAL_WIDTH * 4 or header.mipmap_count != 0 or header.fourcc != 0:
        raise DdsValidationError("DDS pitch, mipmap, or FourCC violates the locked project precedent")
    if header.pixel_format_flags != DDPF_RGB | DDPF_ALPHAPIXELS or header.rgb_bit_count != 32:
        raise DdsValidationError("DDS pixel format flags violate the locked project precedent")
    if (header.red_mask, header.green_mask, header.blue_mask, header.alpha_mask) != (0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000):
        raise DdsValidationError("DDS channel masks violate the locked BGRA contract")
    if header.caps != DDSCAPS_TEXTURE:
        raise DdsValidationError("DDS caps violate the locked texture contract")
    pixel_data = payload[DDS_HEADER_SIZE:]
    if len(payload) != DDS_FILE_SIZE:
        raise DdsValidationError(f"DDS file size must be {DDS_FILE_SIZE}, got {len(payload)}")
    return header, bgra_to_rgba_bytes(pixel_data, header.width, header.height)


def _require_audit_pass(audit_path: str | Path, root: str | Path | None = None) -> dict[str, Any]:
    audit = json.loads(Path(audit_path).read_text(encoding="utf-8"))
    issues = validate_audit(audit, root)
    if issues:
        raise DdsValidationError("audit contract invalid: " + "; ".join(f"{issue.path}: {issue.message}" for issue in issues))
    if audit.get("verdict") != "PASS" or any(value != "PASS" for value in audit.get("hard_gates", {}).values()):
        raise DdsValidationError("DDS promotion requires an independent PASS for every hard gate")
    return audit


def convert_png_to_dds(input_path: str | Path, output_path: str | Path, audit_path: str | Path, root: str | Path | None = None) -> dict[str, Any]:
    _require_audit_pass(audit_path, root)
    try:
        from PIL import Image, ImageChops  # type: ignore
    except ImportError as exc:
        raise DdsValidationError(f"Pillow is required for PNG/DDS conversion: {exc}") from exc

    source = Path(input_path)
    destination = Path(output_path)
    if not source.is_file():
        raise DdsValidationError(f"final PNG does not exist: {source}")
    with Image.open(source) as opened:
        image = opened.convert("RGBA")
        if image.size != (FINAL_WIDTH, FINAL_HEIGHT):
            raise DdsValidationError(f"final PNG must be {FINAL_WIDTH}x{FINAL_HEIGHT}, got {image.size}")
        alpha = image.getchannel("A")
        if alpha.getextrema() != (255, 255):
            raise DdsValidationError("final PNG contains unintended transparency")
        if image.getbbox() is None:
            raise DdsValidationError("final PNG is empty")
        pixels = rgba_to_bgra_bytes(image)
        header = build_dds_header(FINAL_WIDTH, FINAL_HEIGHT)

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=destination.parent, delete=False) as tmp:
        tmp.write(header + pixels)
        temporary = Path(tmp.name)
    try:
        decoded_header, decoded_pixels = decode_dds(temporary)
        expected_rgba = image.tobytes()
        if decoded_pixels != expected_rgba:
            diff = ImageChops.difference(Image.frombytes("RGBA", image.size, decoded_pixels), image)
            raise DdsValidationError(f"DDS round-trip pixel mismatch; diff bbox={diff.getbbox()}")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {
        "status": "PASS",
        "input_png": str(source),
        "output_dds": str(destination),
        "width": FINAL_WIDTH,
        "height": FINAL_HEIGHT,
        "size_bytes": destination.stat().st_size,
        "sha256": sha256_file(destination),
        "header": decoded_header.as_dict(),
        "pixel_round_trip": "PASS",
        "independent_decoder": "SKIPPED_NO_SECOND_LIBRARY",
        "audit_path": str(audit_path),
    }
