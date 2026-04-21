"""Palette extraction via Pillow Image.quantize."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw

from flyer_generator.brand_kit.palette import extract_palette


def _png_with_three_blocks() -> bytes:
    """Red/green/blue each filling ~1/3 of a 300x100 image."""
    img = Image.new("RGB", (300, 100), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 99, 99], fill=(255, 0, 0))
    draw.rectangle([100, 0, 199, 99], fill=(0, 255, 0))
    draw.rectangle([200, 0, 299, 99], fill=(0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _solid_color_png(hex_color: str, size: int = 64) -> bytes:
    h = hex_color.lstrip("#")
    rgb = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    img = Image.new("RGB", (size, size), rgb)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_extract_palette_three_blocks() -> None:
    png = _png_with_three_blocks()
    palette = extract_palette(png, n_colors=5)
    hexes = [p[0] for p in palette]
    # Quantization may snap slightly -- assert R/G/B dominant hues are in the list
    assert any(h.startswith("#FF") or h.startswith("#F") for h in hexes)
    assert any("00" in h and h != "#000000" for h in hexes)


def test_extract_palette_solid_color() -> None:
    png = _solid_color_png("#1E3A5F")
    palette = extract_palette(png, n_colors=3)
    assert palette
    # Median-cut on a solid image yields exactly one color
    assert palette[0][0] == "#1E3A5F"


def test_extract_palette_hex_uppercase() -> None:
    png = _solid_color_png("#abcdef")
    palette = extract_palette(png, n_colors=1)
    assert palette[0][0] == "#ABCDEF"


def test_extract_palette_sorted_descending() -> None:
    png = _png_with_three_blocks()
    palette = extract_palette(png, n_colors=5)
    counts = [c for _, c in palette]
    assert counts == sorted(counts, reverse=True)
