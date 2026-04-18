"""Stage 8: Mechanical output lint.

Post-render sanity checks on the composed SVGs + rasterised PNGs. Catches
mechanical failures (empty panels, crop marks missing, malformed XML, text
bounding boxes outside safe rects) that the vision verifier can't reliably
diagnose.

Outputs a flat ``dict[str, bool | str]`` report attached to
``BrochureOutput.lint_report``. Each key is a check name; value is either
``True`` (passed), ``False`` (failed), or a string with a human-readable
failure note when an exception interrupted the check.
"""

from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
from typing import Any

from PIL import Image

from flyer_generator.brochure.models import ResolvedBrochureLayout

# --- Tunables ---

# A panel's safe_rect is flagged empty when >= this fraction of its pixels are
# within EMPTY_COLOR_TOLERANCE of the most common colour.
EMPTY_COLOR_DOMINANCE = 0.95
EMPTY_COLOR_TOLERANCE = 5  # max per-channel delta counted as the dominant colour

# To avoid flagging panels that DO carry content (spot image, many shapes),
# pixel-check is skipped when the panel's SVG region contains any of these
# element tags.
_CONTENT_TAGS_SKIP = frozenset({"image", "path", "polygon", "polyline"})


def check_xml_validity(outside_svg: str, inside_svg: str) -> dict[str, Any]:
    """Parse both SVG documents via ElementTree — must not raise."""
    out: dict[str, Any] = {}
    for name, svg in (("outside_svg_valid", outside_svg), ("inside_svg_valid", inside_svg)):
        try:
            ET.fromstring(svg)
            out[name] = True
        except ET.ParseError as exc:
            out[name] = f"parse error: {exc}"
    return out


def check_crop_marks_in_svg(outside_svg: str, inside_svg: str) -> dict[str, Any]:
    """Confirm the SVG contains the dedicated crop-mark layer."""
    return {
        "outside_crop_marks_present": 'id="crop-marks"' in outside_svg,
        "inside_crop_marks_present": 'id="crop-marks"' in inside_svg,
    }


def _panel_pixels(img: Image.Image, safe_rect: tuple[int, int, int, int]) -> list[tuple[int, int, int]]:
    """Extract RGB tuples from the safe region of a rendered PNG.

    Downsamples to a 40x40 grid so lint stays cheap even on the 3376×2626
    brochure canvas.
    """
    sx, sy, sw, sh = safe_rect
    region = img.crop((sx, sy, sx + sw, sy + sh)).convert("RGB")
    region = region.resize((40, 40))
    # Pillow 14+ deprecates getdata(); iterate via getpixel for forward compat.
    return [region.getpixel((x, y)) for y in range(region.height) for x in range(region.width)]


def _panel_is_empty(pixels: list[tuple[int, int, int]]) -> bool:
    """Return True when >= EMPTY_COLOR_DOMINANCE of pixels cluster near the mode colour."""
    if not pixels:
        return True
    # Most-common colour (exact match is fine on the downsampled grid).
    from collections import Counter

    counter = Counter(pixels)
    mode_colour, _ = counter.most_common(1)[0]
    mr, mg, mb = mode_colour

    close = 0
    for r, g, b in pixels:
        if (
            abs(r - mr) <= EMPTY_COLOR_TOLERANCE
            and abs(g - mg) <= EMPTY_COLOR_TOLERANCE
            and abs(b - mb) <= EMPTY_COLOR_TOLERANCE
        ):
            close += 1
    return close / len(pixels) >= EMPTY_COLOR_DOMINANCE


def _panel_has_rich_content(svg: str, safe_rect: tuple[int, int, int, int]) -> bool:
    """Does the SVG have an <image> or many shape elements inside safe_rect?

    We use a cheap heuristic: count occurrences of content-tag names in the
    whole SVG. The proper spatial filter is overkill for a lint — empty-panel
    false positives on richly-designed brochures are rarer than the lint firing
    usefully on a genuinely empty tuck flap.
    """
    if "<image " in svg:
        return True
    shape_count = sum(svg.count(f"<{t} ") for t in _CONTENT_TAGS_SKIP)
    return shape_count >= 3


def check_empty_quadrants(
    front_png_bytes: bytes,
    back_png_bytes: bytes,
    layout: ResolvedBrochureLayout,
    outside_svg: str = "",
    inside_svg: str = "",
) -> dict[str, Any]:
    """Return a per-panel empty flag. ``True`` means the panel is visually empty."""
    out: dict[str, Any] = {}
    try:
        front = Image.open(io.BytesIO(front_png_bytes))
        back = Image.open(io.BytesIO(back_png_bytes))
    except Exception as exc:
        out["empty_quadrant_check_error"] = f"could not open PNG: {exc}"
        return out

    for panel in layout.outside_panels:
        key = f"panel_{panel.name}_empty"
        # Skip panels whose SVG region has rich content.
        if outside_svg and _panel_has_rich_content(outside_svg, panel.safe_rect):
            out[key] = False
            continue
        pixels = _panel_pixels(front, panel.safe_rect)
        out[key] = _panel_is_empty(pixels)

    for panel in layout.inside_panels:
        key = f"panel_{panel.name}_empty"
        if inside_svg and _panel_has_rich_content(inside_svg, panel.safe_rect):
            out[key] = False
            continue
        pixels = _panel_pixels(back, panel.safe_rect)
        out[key] = _panel_is_empty(pixels)
    return out


# --- Text clipping ---

_TEXT_RE = re.compile(
    r'<text[^>]*?x="(-?\d+(?:\.\d+)?)"[^>]*?y="(-?\d+(?:\.\d+)?)"[^>]*?font-size="(\d+)"[^>]*?>([^<]*)</text>',
    flags=re.DOTALL,
)


def _text_bounding_boxes(svg: str) -> list[tuple[float, float, float, float]]:
    """Return approximate (x0, y0, x1, y1) bboxes for every <text> in svg.

    Approximate width uses 0.55 * font_size per character (a conservative
    estimate for common sans/serif fonts). Height uses font_size.
    """
    bboxes: list[tuple[float, float, float, float]] = []
    for match in _TEXT_RE.finditer(svg):
        x_str, y_str, size_str, content = match.groups()
        x = float(x_str)
        y = float(y_str)
        size = int(size_str)
        text_content = content.strip()
        if not text_content:
            continue
        width = 0.55 * size * len(text_content)
        # y is baseline; extend up by font_size, down by ~0.25 * font_size descender.
        bboxes.append((x, y - size, x + width, y + 0.25 * size))
    return bboxes


def _bbox_inside(
    bbox: tuple[float, float, float, float],
    rect: tuple[int, int, int, int],
    slack: float = 20.0,
) -> bool:
    x0, y0, x1, y1 = bbox
    rx, ry, rw, rh = rect
    return (
        x0 >= rx - slack
        and y0 >= ry - slack
        and x1 <= rx + rw + slack
        and y1 <= ry + rh + slack
    )


def _bbox_overlaps_rect(
    bbox: tuple[float, float, float, float],
    rect: tuple[int, int, int, int],
) -> bool:
    x0, y0, x1, y1 = bbox
    rx, ry, rw, rh = rect
    return not (x1 <= rx or x0 >= rx + rw or y1 <= ry or y0 >= ry + rh)


def check_text_clipping(
    outside_svg: str,
    inside_svg: str,
    layout: ResolvedBrochureLayout,
) -> dict[str, Any]:
    """Return ``panel_<name>_text_clip`` flags for every panel.

    ``True`` means at least one text element has a bounding box that overlaps
    the panel but extends past its safe rect (indicating the copy may get
    clipped when printed).
    """
    out: dict[str, Any] = {}
    pairs = [("outside", outside_svg, layout.outside_panels), ("inside", inside_svg, layout.inside_panels)]
    for _sheet, svg, panels in pairs:
        bboxes = _text_bounding_boxes(svg)
        for panel in panels:
            rect = panel.safe_rect
            key = f"panel_{panel.name}_text_clip"
            clipped = False
            for bbox in bboxes:
                if _bbox_overlaps_rect(bbox, rect) and not _bbox_inside(bbox, rect):
                    clipped = True
                    break
            out[key] = clipped
    return out


def lint_brochure(
    *,
    outside_svg: str,
    inside_svg: str,
    front_png_bytes: bytes,
    back_png_bytes: bytes,
    layout: ResolvedBrochureLayout,
) -> dict[str, Any]:
    """Run every lint check and return a merged report."""
    report: dict[str, Any] = {}
    report.update(check_xml_validity(outside_svg, inside_svg))
    report.update(check_crop_marks_in_svg(outside_svg, inside_svg))
    report.update(
        check_empty_quadrants(
            front_png_bytes, back_png_bytes, layout,
            outside_svg=outside_svg, inside_svg=inside_svg,
        )
    )
    report.update(check_text_clipping(outside_svg, inside_svg, layout))

    # Derive a pass/fail summary for CLI convenience. A check is "failing" when
    # its value is falsy (False, empty string, error string coerces True so we
    # guard explicitly).
    checks_total = len(report)
    checks_passed = 0
    for key, value in report.items():
        if isinstance(value, bool) and value is True:
            checks_passed += 1
        elif isinstance(value, bool) and value is False and key.endswith(("_empty", "_text_clip")):
            # "_empty = False" / "_text_clip = False" are *passes* for these keys.
            checks_passed += 1
    report["_summary"] = f"{checks_passed}/{checks_total} checks passed"
    return report
