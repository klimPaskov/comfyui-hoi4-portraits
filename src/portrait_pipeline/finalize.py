from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

from .audit import audit_is_promotion_pass
from .constants import FINAL_HEIGHT, FINAL_WIDTH
from .contracts import validate_audit
from .util import sha256_file


class FinalizationError(RuntimeError):
    exit_code = 50


def _load_pillow():
    try:
        from PIL import Image, ImageOps  # type: ignore
    except ImportError as exc:
        raise FinalizationError(f"Pillow is required for final PNG processing: {exc}") from exc
    return Image, ImageOps


def _require_pass(audit: dict[str, Any], root: str | Path | None = None) -> None:
    issues = validate_audit(audit, root)
    if issues:
        raise FinalizationError("audit contract invalid: " + "; ".join(f"{issue.path}: {issue.message}" for issue in issues))
    if not audit_is_promotion_pass(audit):
        raise FinalizationError("final PNG promotion requires an independent all-PASS audit")


def _opaque(image: Any) -> Any:
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    alpha = image.getchannel("A")
    if alpha.getextrema() != (255, 255):
        raise FinalizationError("final PNG contains transparency")
    return image.convert("RGB")


def create_comparison_sheet(images: Iterable[tuple[str, Any]], output_path: str | Path, *, scale: int = 1) -> dict[str, Any]:
    Image, _ = _load_pillow()
    entries = list(images)
    if not entries:
        raise FinalizationError("comparison sheet requires at least one image")
    prepared = [(label, image.convert("RGB")) for label, image in entries]
    cell_w = max(image.width for _, image in prepared) * scale
    cell_h = max(image.height for _, image in prepared) * scale
    sheet = Image.new("RGB", (cell_w * len(prepared), cell_h), (32, 32, 32))
    for index, (_, image) in enumerate(prepared):
        resized = image.resize((cell_w, cell_h), Image.Resampling.NEAREST if scale > 1 else Image.Resampling.LANCZOS)
        sheet.paste(resized, (index * cell_w, 0))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, format="PNG", optimize=False)
    return {"path": str(output), "sha256": sha256_file(output), "labels": [label for label, _ in prepared], "scale": scale}


def finalize_candidate_png(candidate_path: str | Path, output_path: str | Path, audit: dict[str, Any], *, root: str | Path | None = None, comparison_dir: str | Path | None = None, evidence_images: Iterable[tuple[str, str | Path]] | None = None) -> dict[str, Any]:
    _require_pass(audit, root)
    Image, _ = _load_pillow()
    candidate = Path(candidate_path)
    if not candidate.is_file():
        raise FinalizationError(f"audited candidate is missing: {candidate}")
    with Image.open(candidate) as source:
        image = source.convert("RGBA")
        if image.width * 35 != image.height * 26:
            raise FinalizationError("audited candidate is not the locked 26:35 portrait canvas")
        final = _opaque(image.resize((FINAL_WIDTH, FINAL_HEIGHT), Image.Resampling.LANCZOS))
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("wb", dir=destination.parent, delete=False) as tmp:
            final.save(tmp, format="PNG", optimize=False)
            temporary = Path(tmp.name)
        os.replace(temporary, destination)
    with Image.open(destination) as reopened:
        if reopened.size != (FINAL_WIDTH, FINAL_HEIGHT) or reopened.mode not in {"RGB", "RGBA"}:
            raise FinalizationError("reopened final PNG violates dimensions or mode")
        final_copy = reopened.convert("RGB")
        comparisons: list[dict[str, Any]] = []
        if comparison_dir is not None:
            source_images: list[tuple[str, Any]] = [("candidate", final_copy), ("final", final_copy)]
            for label, path in evidence_images or []:
                with Image.open(path) as evidence_image:
                    source_images.append((label, evidence_image.copy()))
            comparison_dir = Path(comparison_dir)
            comparisons.append(create_comparison_sheet(source_images, comparison_dir / "native.png", scale=1))
            comparisons.append(create_comparison_sheet(source_images, comparison_dir / "enlarged_4x.png", scale=4))
    return {"status": "PASS", "png_path": str(output_path), "png_sha256": sha256_file(output_path), "width": FINAL_WIDTH, "height": FINAL_HEIGHT, "comparisons": comparisons, "audit_candidate_id": audit.get("candidate_id")}
