#!/usr/bin/env python3
"""Render readable, high-resolution workflow layout screenshots from editor JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "workflows" / "hoi4_portrait_flux2_klein_9b_source.json"
OUT = ROOT / "docs" / "assets" / "workflows"
PREVIEW_ASSETS = {
    35: ROOT / "comfyui" / "input" / "screenshot_stage_processed.png",
    55: ROOT / "comfyui" / "input" / "screenshot_stage_styled.png",
    75: ROOT / "comfyui" / "input" / "screenshot_stage_final.png",
    95: ROOT / "comfyui" / "input" / "screenshot_stage_styled.png",
}


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def _mix(value: str, amount: float) -> tuple[int, int, int]:
    base = _rgb(value)
    return tuple(round(channel * amount + 18 * (1 - amount)) for channel in base)


def _short(value: Any, limit: int = 28) -> str:
    text = str(value).replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def render(
    workflow: dict[str, Any],
    filename: str,
    *,
    focus_group: str | None = None,
    scale: float = 0.55,
) -> None:
    groups = workflow["groups"]
    nodes = {node["id"]: node for node in workflow["nodes"]}
    selected = next((group for group in groups if group["title"] == focus_group), None)
    if selected:
        gx, gy, gw, gh = selected["bounding"]
        bounds = (gx - 30, gy - 30, gx + gw + 30, gy + gh + 30)
    else:
        bounds = (0, 0, max(group["bounding"][0] + group["bounding"][2] for group in groups) + 60,
                  max(group["bounding"][1] + group["bounding"][3] for group in groups) + 60)
    left, top, right, bottom = bounds
    width = max(1, round((right - left) * scale))
    height = max(1, round((bottom - top) * scale))
    image = Image.new("RGB", (width, height), (12, 14, 18))
    draw = ImageDraw.Draw(image)

    def point(x: float, y: float) -> tuple[int, int]:
        return round((x - left) * scale), round((y - top) * scale)

    title_font = _font(max(14, round(28 * scale)))
    group_font = _font(max(12, round(24 * scale)))
    node_font = _font(max(10, round(20 * scale)))
    small_font = _font(max(8, round(16 * scale)))

    for group in groups:
        gx, gy, gw, gh = group["bounding"]
        if gx + gw < left or gx > right or gy + gh < top or gy > bottom:
            continue
        x0, y0 = point(gx, gy)
        x1, y1 = point(gx + gw, gy + gh)
        color = _rgb(group["color"])
        draw.rounded_rectangle((x0, y0, x1, y1), radius=max(4, round(16 * scale)), fill=_mix(group["color"], 0.32), outline=color, width=max(1, round(3 * scale)))
        draw.text((x0 + round(14 * scale), y0 + round(8 * scale)), group["title"], fill=(235, 240, 248), font=group_font)

    visible_ids = {
        node_id
        for node_id, node in nodes.items()
        if node["pos"][0] + node["size"][0] >= left and node["pos"][0] <= right
        and node["pos"][1] + node["size"][1] >= top and node["pos"][1] <= bottom
    }
    for link in workflow.get("links", []):
        _, source_id, _, destination_id, _, link_type = link
        if source_id not in visible_ids or destination_id not in visible_ids:
            continue
        source = nodes[source_id]
        destination = nodes[destination_id]
        sx, sy = source["pos"]
        sw, sh = source["size"]
        dx, dy = destination["pos"]
        _, dh = destination["size"]
        start = point(sx + sw, sy + sh / 2)
        end = point(dx, dy + dh / 2)
        color = {"IMAGE": (105, 170, 231), "MASK": (216, 151, 80), "MODEL": (232, 206, 92)}.get(link_type, (153, 160, 176))
        draw.line((start, end), fill=color, width=max(1, round(2 * scale)), joint="curve")

    for node_id in sorted(visible_ids):
        node = nodes[node_id]
        x, y = node["pos"]
        w, h = node["size"]
        x0, y0 = point(x, y)
        x1, y1 = point(x + w, y + h)
        group = next((item for item in groups if item["title"] == node["properties"].get("hoi4_group")), None)
        color = node.get("color") or (group["color"] if group else "#64748b")
        background = node.get("bgcolor") or color
        draw.rounded_rectangle((x0, y0, x1, y1), radius=max(3, round(10 * scale)), fill=_mix(background, 0.74), outline=_rgb(color), width=max(1, round(3 * scale)))
        draw.text((x0 + round(9 * scale), y0 + round(7 * scale)), _short(node.get("title", node["type"]), 38), fill=(250, 250, 252), font=node_font)
        draw.text((x0 + round(9 * scale), y0 + round(30 * scale)), f"#{node_id}  {node['type']}", fill=(196, 210, 226), font=small_font)
        if node["type"] == "PreviewImage":
            preview_top = y0 + round(58 * scale)
            draw.rectangle((x0 + round(10 * scale), preview_top, x1 - round(10 * scale), y1 - round(10 * scale)), fill=(28, 34, 44), outline=(175, 185, 198), width=max(1, round(2 * scale)))
            preview_path = PREVIEW_ASSETS.get(node_id)
            if preview_path and preview_path.is_file():
                inner = (x0 + round(12 * scale), preview_top + round(2 * scale), x1 - round(12 * scale), y1 - round(12 * scale))
                preview = Image.open(preview_path).convert("RGB")
                preview = ImageOps.fit(preview, (max(1, inner[2] - inner[0]), max(1, inner[3] - inner[1])), method=Image.Resampling.LANCZOS)
                image.paste(preview, (inner[0], inner[1]))
            else:
                draw.text((x0 + round(18 * scale), preview_top + round(14 * scale)), "preview after queue", fill=(160, 174, 190), font=small_font)
        elif node.get("widgets_values"):
            value = _short(node["widgets_values"][0], 42)
            draw.text((x0 + round(9 * scale), y1 - round(25 * scale)), value, fill=(218, 225, 236), font=small_font)

    if focus_group is None:
        draw.text((round(22 * scale), round(12 * scale)), "HOI4 portrait source workflow · three candidates · background toggle applies to all", fill=(239, 244, 250), font=title_font)
    else:
        draw.text((round(22 * scale), round(12 * scale)), f"HOI4 portrait workflow · {focus_group}", fill=(239, 244, 250), font=title_font)
    OUT.mkdir(parents=True, exist_ok=True)
    image.save(OUT / filename, optimize=True)


def main() -> None:
    workflow = json.loads(SOURCE.read_text(encoding="utf-8"))
    render(workflow, "source-workflow-overview.png", scale=0.55)
    render(workflow, "step-1-source-processing.png", focus_group="01 Source and ESRGAN", scale=0.9)
    render(workflow, "step-2-model-setup.png", focus_group="02 FLUX.2 Klein 9B models", scale=1.0)
    render(workflow, "step-3-flux-restoration.png", focus_group="03 Optional FLUX.2 restoration", scale=0.8)
    render(workflow, "step-4-lora-styling.png", focus_group="04 HOI4 LoRA styling", scale=0.65)
    render(workflow, "step-5-background-replacement.png", focus_group="05 Optional background - after generation", scale=0.7)
    render(workflow, "step-6-preview-and-save.png", focus_group="06 Preview and save", scale=0.7)


if __name__ == "__main__":
    main()
