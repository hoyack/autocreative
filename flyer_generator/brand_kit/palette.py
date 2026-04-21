"""Dominant color extraction via Pillow's native `Image.quantize`.

No new dependency -- reuses the Pillow install already pinned in
pyproject.toml. Median-cut chooses perceptually distinct colors (the
right heuristic for brand-kit extraction vs. MAXCOVERAGE which biases
toward most-pixels-wins and flattens into a stack of neutrals).
"""

from __future__ import annotations

from io import BytesIO

from PIL import Image


def extract_palette(
    png_bytes: bytes,
    *,
    n_colors: int = 5,
    thumbnail_size: tuple[int, int] = (800, 600),
) -> list[tuple[str, int]]:
    """Return `[(hex, pixel_count), ...]` sorted by count desc.

    Uses median-cut on a thumbnailed copy of the input image. Thumbnail
    keeps the operation under ~100ms even for a 1920x1080 screenshot.
    Every returned hex is uppercase `#RRGGBB`.
    """
    img = Image.open(BytesIO(png_bytes)).convert("RGB")
    img.thumbnail(thumbnail_size)
    quantized = img.quantize(
        colors=n_colors,
        method=Image.Quantize.MEDIANCUT,
        kmeans=0,
    )
    palette_bytes = quantized.getpalette() or []
    counts = quantized.getcolors(maxcolors=n_colors) or []
    counts.sort(key=lambda t: -t[0])
    result: list[tuple[str, int]] = []
    for count, idx in counts:
        r = palette_bytes[idx * 3]
        g = palette_bytes[idx * 3 + 1]
        b = palette_bytes[idx * 3 + 2]
        result.append((f"#{r:02X}{g:02X}{b:02X}", count))
    return result
