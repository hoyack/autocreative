"""BrochureComposer — SVG composition for tri-fold brochure sheets.

Produces two SVG documents (outside + inside) sized to the bleed canvas.
For each of the six panels:
  - Front cover (outside center): embeds the hero image as base64 PNG
  - All other panels: render an accent-tinted linear gradient fill
  - Overlays panel-specific text (heading + body) within the panel safe zone

Fold lines and crop marks render on dedicated <g> layers that can be toggled
off for the final print pass.

Output is two SVG strings; pixel rasterisation is the rasterizer's job (phase 7
reuses flyer_generator.stages.rasterizer.Rasterizer unchanged).
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from xml.sax.saxutils import escape

from flyer_generator.brochure.generative.models import LayoutChoice
from flyer_generator.brochure.models import (
    BrochureBackPanel,
    BrochureInput,
    BrochureSection,
    PanelRect,
    ResolvedBrochureLayout,
)
from flyer_generator.brochure.shapes import render_shape
from flyer_generator.brochure.stages.fonts import build_font_face_defs
from flyer_generator.brochure.templates import EDITORIAL, LayoutTemplate, get_template
from flyer_generator.errors import CompositionError

# --- Fallback typography (used when no template is supplied — keeps v1 tests green) ---

_FONT_TITLE = "'Arial Black', Arial, sans-serif"
_FONT_BODY = "Arial, sans-serif"

_HEADING_FONT_SIZE = 64
_BODY_FONT_SIZE = 36
_BODY_LINE_HEIGHT = 44
_BODY_MAX_CHARS_PER_LINE = 28

_TITLE_FONT_SIZE = 110
_SUBTITLE_FONT_SIZE = 48


@dataclass(frozen=True)
class _Typography:
    """Packaged typography values — template-aware, falls back to module constants."""

    title_font: str
    body_font: str
    cover_title_size: int
    heading_size: int
    body_size: int
    body_line_height: int
    body_max_chars: int


def _typography(template: LayoutTemplate | None) -> _Typography:
    if template is None:
        return _Typography(
            title_font=_FONT_TITLE,
            body_font=_FONT_BODY,
            cover_title_size=_TITLE_FONT_SIZE,
            heading_size=_HEADING_FONT_SIZE,
            body_size=_BODY_FONT_SIZE,
            body_line_height=_BODY_LINE_HEIGHT,
            body_max_chars=_BODY_MAX_CHARS_PER_LINE,
        )
    return _Typography(
        title_font=template.heading_font_family,
        body_font=template.body_font_family,
        cover_title_size=template.cover_title_font_size,
        heading_size=template.heading_font_size,
        body_size=template.body_font_size,
        body_line_height=template.body_line_height,
        body_max_chars=template.body_max_chars_per_line,
    )


def _fit_title_font_size(title: str, base_size: int = _TITLE_FONT_SIZE) -> int:
    """Auto-shrink the cover title font when the string is long.

    Base fits ~14 characters across the cover panel safe zone (~950px).
    Longer titles scale down linearly to a minimum of 62px.
    """
    n = max(1, len(title))
    if n <= 14:
        return base_size
    scaled = int(base_size * 14 / n)
    return max(62, min(base_size, scaled))

# --- Back-panel kind → human-readable heading (fixes v1 "CTA" leak) ---

_BACK_PANEL_HEADINGS: dict[str, str] = {
    "cta": "Visit Us",
    "bio": "About",
    "map_stub": "Find Us",
    "contact": "Contact",
}

_FOLD_LINE_COLOR = "#FF00FF"  # magenta, visible guide color; on a non-printing layer
_CROP_MARK_COLOR = "#000000"
_CROP_MARK_LENGTH = 36
_CROP_MARK_STROKE = 3


def _wrap(text: str, max_chars: int) -> list[str]:
    """Simple word-wrap: never break a word, respect max_chars per line."""
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        if len(current) + 1 + len(word) <= max_chars:
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _parse_body(body: str) -> list[tuple[str, str]]:
    """Return a list of (kind, text) tuples. kind is 'bullet' or 'para'.

    Lines starting with '- ' become bullets; other lines become paragraphs.
    Adjacent paragraph lines are joined with a space.
    """
    items: list[tuple[str, str]] = []
    current_para: list[str] = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            if current_para:
                items.append(("para", " ".join(current_para)))
                current_para = []
            continue
        if line.startswith("- "):
            if current_para:
                items.append(("para", " ".join(current_para)))
                current_para = []
            items.append(("bullet", line[2:].strip()))
        else:
            current_para.append(line)
    if current_para:
        items.append(("para", " ".join(current_para)))
    if not items:
        items.append(("para", body.strip()))
    return items


def _render_panel_gradient(panel: PanelRect, accent_hex: str) -> str:
    """Accent-tinted vertical linear gradient, keyed by panel name for unique IDs."""
    x, y, w, h = panel.bleed_rect
    grad_id = f"grad-{panel.sheet}-{panel.name}"
    return (
        f'<defs><linearGradient id="{grad_id}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{accent_hex}" stop-opacity="0.18"/>'
        f'<stop offset="100%" stop-color="{accent_hex}" stop-opacity="0.06"/>'
        f"</linearGradient></defs>"
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#{grad_id})"/>'
    )


def _render_hero_image(panel: PanelRect, hero_png_bytes: bytes) -> str:
    """Embed hero PNG base64 on the front-cover panel at the bleed rect extent."""
    if not hero_png_bytes:
        raise CompositionError("hero_png_bytes must be non-empty for front cover")
    b64 = base64.b64encode(hero_png_bytes).decode()
    x, y, w, h = panel.bleed_rect
    return (
        f'<image x="{x}" y="{y}" width="{w}" height="{h}" '
        f'preserveAspectRatio="xMidYMid slice" '
        f'href="data:image/png;base64,{b64}"/>'
    )


def _render_placeholder_cover(
    panel: PanelRect,
    title: str,
    subtitle: str | None,
    accent_hex: str,
    typ: _Typography,
) -> str:
    """Cover treatment when no hero image is available.

    Renders:
      - Accent-tinted gradient across the full panel (same as other panels)
      - A dominant accent bar near the top for visual anchor
      - Title rendered in dark/accent colour (NOT white) so it's visible against
        the pale gradient — white-on-white was the silent failure from the
        shapes_only + placeholder hero path
      - Subtitle in a muted colour below the title
    """
    sx, sy, sw, sh = panel.safe_rect
    x, y, w, h = panel.bleed_rect
    cx = sx + sw // 2
    title_y = sy + sh // 3
    title_display = title.upper()
    title_size = _fit_title_font_size(title_display, base_size=typ.cover_title_size)

    # Use the same panel-gradient id pattern so multiple panels don't collide.
    grad_id = f"grad-{panel.sheet}-{panel.name}-cover"
    parts = [
        f'<defs><linearGradient id="{grad_id}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{accent_hex}" stop-opacity="0.22"/>'
        f'<stop offset="100%" stop-color="{accent_hex}" stop-opacity="0.08"/>'
        f"</linearGradient></defs>"
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#{grad_id})"/>',
        # Anchor bar above the title
        f'<rect x="{cx - 120}" y="{title_y - title_size - 40}" width="240" height="8" fill="{accent_hex}"/>',
        # Title (accent colour, no drop shadow — high-contrast against pale gradient)
        f'<text x="{cx}" y="{title_y}" text-anchor="middle" '
        f'font-family="{typ.title_font}" '
        f'font-size="{title_size}" '
        f'fill="{accent_hex}">'
        f"{escape(title_display)}</text>",
    ]
    if subtitle:
        sub_y = title_y + title_size + 16
        parts.append(
            f'<text x="{cx}" y="{sub_y}" text-anchor="middle" '
            f'font-family="{typ.body_font}" font-size="{_SUBTITLE_FONT_SIZE}" '
            f'fill="#333333">{escape(subtitle)}</text>'
        )
    return "".join(parts)


def _render_cover_text(
    panel: PanelRect,
    title: str,
    subtitle: str | None,
    typ: _Typography,
) -> str:
    """Title + optional subtitle overlaid on the cover panel safe area.

    Uses a soft drop shadow (via SVG filter) instead of the hard outline stroke
    so type reads naturally against any hero image.
    """
    sx, sy, sw, sh = panel.safe_rect
    cx = sx + sw // 2
    title_y = sy + sh // 3  # upper third
    title = title.upper()
    filter_id = f"cover-shadow-{panel.sheet}"
    title_size = _fit_title_font_size(title, base_size=typ.cover_title_size)
    parts = [
        f'<defs><filter id="{filter_id}" x="-10%" y="-30%" width="120%" height="160%">'
        f'<feGaussianBlur in="SourceAlpha" stdDeviation="3"/>'
        f'<feOffset dx="0" dy="4"/>'
        f'<feComponentTransfer><feFuncA type="linear" slope="0.75"/></feComponentTransfer>'
        f'<feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>'
        f"</filter></defs>",
        f'<text x="{cx}" y="{title_y}" text-anchor="middle" '
        f'font-family="{typ.title_font}" '
        f'font-size="{title_size}" '
        f'fill="#FFFFFF" filter="url(#{filter_id})">'
        f"{escape(title)}</text>",
    ]
    if subtitle:
        sub_y = title_y + typ.cover_title_size + 16
        parts.append(
            f'<text x="{cx}" y="{sub_y}" text-anchor="middle" '
            f'font-family="{typ.body_font}" font-size="{_SUBTITLE_FONT_SIZE}" '
            f'fill="#FFFFFF" filter="url(#{filter_id})">'
            f"{escape(subtitle)}</text>"
        )
    return "".join(parts)


def _fit_heading_font_size(heading: str, panel_safe_width: int, base_size: int) -> int:
    """Shrink heading size until estimated width fits the panel's safe width.

    Uses ~0.55 * size per character as a width estimate (common for modern
    sans/serif fonts). Floor is 60% of the base to avoid unreadable text.
    """
    n = max(1, len(heading))
    floor = max(int(base_size * 0.6), 24)
    size = base_size
    while size > floor and 0.55 * size * n > panel_safe_width:
        size -= 2
    return size


def _render_section_text(
    panel: PanelRect,
    section: BrochureSection,
    accent_hex: str,
    typ: _Typography,
) -> str:
    """Heading + accent rule + wrapped body text for an inner panel."""
    sx, sy, sw, _ = panel.safe_rect
    heading_size = _fit_heading_font_size(section.heading, sw, typ.heading_size)
    y = sy + heading_size
    parts = [
        f'<text x="{sx}" y="{y}" '
        f'font-family="{typ.title_font}" font-size="{heading_size}" '
        f'fill="{accent_hex}">{escape(section.heading)}</text>',
        f'<rect x="{sx}" y="{y + 12}" width="{min(sw, 220)}" height="3" fill="{accent_hex}"/>',
    ]
    y += 24 + 16
    for kind, text in _parse_body(section.body):
        if kind == "bullet":
            lines = _wrap(text, typ.body_max_chars - 2)
            for i, line in enumerate(lines):
                y += typ.body_line_height
                prefix = "• " if i == 0 else "  "
                parts.append(
                    f'<text x="{sx}" y="{y}" '
                    f'font-family="{typ.body_font}" font-size="{typ.body_size}" '
                    f'fill="#333333">{escape(prefix + line)}</text>'
                )
        else:
            lines = _wrap(text, typ.body_max_chars)
            for line in lines:
                y += typ.body_line_height
                parts.append(
                    f'<text x="{sx}" y="{y}" '
                    f'font-family="{typ.body_font}" font-size="{typ.body_size}" '
                    f'fill="#333333">{escape(line)}</text>'
                )
            y += 12
    return "".join(parts)


def _render_back_panel_text(
    panel: PanelRect,
    brochure: BrochureInput,
    typ: _Typography,
) -> str:
    """Back-cover panel content: back_panel if provided, else org + contact block."""
    sx, sy, sw, _sh = panel.safe_rect
    parts: list[str] = []
    y = sy + typ.heading_size
    if brochure.back_panel is not None:
        heading_text = _BACK_PANEL_HEADINGS.get(brochure.back_panel.kind, "Details")
        parts.append(
            f'<text x="{sx}" y="{y}" '
            f'font-family="{typ.title_font}" font-size="{typ.heading_size}" '
            f'fill="{brochure.color_accent}">'
            f"{escape(heading_text)}</text>"
        )
        parts.append(
            f'<rect x="{sx}" y="{y + 12}" width="{min(sw, 220)}" height="3" '
            f'fill="{brochure.color_accent}"/>'
        )
        y += typ.heading_size + 16
        for line in _wrap(brochure.back_panel.content, typ.body_max_chars):
            y += typ.body_line_height
            parts.append(
                f'<text x="{sx}" y="{y}" '
                f'font-family="{typ.body_font}" font-size="{typ.body_size}" '
                f'fill="#333333">{escape(line)}</text>'
            )
        return "".join(parts)

    # Fallback: org + contact
    parts.append(
        f'<text x="{sx}" y="{y}" '
        f'font-family="{typ.title_font}" font-size="{typ.heading_size}" '
        f'fill="{brochure.color_accent}">{escape(brochure.org)}</text>'
    )
    parts.append(
        f'<rect x="{sx}" y="{y + 12}" width="{min(sw, 220)}" height="3" '
        f'fill="{brochure.color_accent}"/>'
    )
    y += 16
    if brochure.contact is not None:
        for attr in ("name", "phone", "email", "url", "address"):
            value = getattr(brochure.contact, attr)
            if value:
                y += typ.body_line_height
                parts.append(
                    f'<text x="{sx}" y="{y}" '
                    f'font-family="{typ.body_font}" font-size="{typ.body_size}" '
                    f'fill="#333333">{escape(value)}</text>'
                )
    return "".join(parts)


def _render_tuck_flap_tagline(
    panel: PanelRect,
    org_name: str,
    accent_hex: str,
    typ: _Typography,
) -> str:
    """Org name only (no tagline body) for panels that have no assigned section.

    Used when the brochure has fewer than 4 content sections (tuck flap) or
    when inner_center would otherwise ship empty (N=2 case). Renders a single
    centred strap with an accent rule. No wrapped body line — previous
    iterations accidentally duplicated the org name as a multi-line tagline
    which overflowed narrow panels with long input strings.
    """
    sx, sy, sw, sh = panel.safe_rect
    if not org_name:
        return ""
    # Hard cap on how much text we'll try to render — tuck flap is ~4cm wide.
    org = org_name.strip()[:32]
    if not org:
        return ""
    cx = sx + sw // 2
    center_y = sy + sh // 2
    strap_size = max(typ.body_size + 4, typ.heading_size // 2)
    # Detect if the org text is too wide for the panel's safe width. Assume
    # ~0.55 * font_size per char; if estimated width exceeds safe width, shrink.
    est_width = 0.55 * strap_size * len(org)
    if est_width > sw - 40:
        # Cap at a size that actually fits
        strap_size = max(int((sw - 40) / (0.55 * len(org))), typ.body_size)
    return "".join([
        f'<text x="{cx}" y="{center_y}" text-anchor="middle" '
        f'font-family="{typ.title_font}" font-size="{strap_size}" '
        f'fill="{accent_hex}">{escape(org.upper())}</text>',
        f'<rect x="{cx - 40}" y="{center_y + strap_size // 3}" '
        f'width="80" height="3" fill="{accent_hex}"/>',
    ])


def _render_fold_lines(fold_x_coords: list[int], canvas_h: int) -> str:
    """Fold-line guides — magenta dashed lines on a non-printing layer."""
    parts = []
    for x in fold_x_coords:
        parts.append(
            f'<line x1="{x}" y1="0" x2="{x}" y2="{canvas_h}" '
            f'stroke="{_FOLD_LINE_COLOR}" stroke-width="1" stroke-dasharray="8 8"/>'
        )
    return "".join(parts)


def _render_crop_marks(anchors: list[tuple[int, int]]) -> str:
    """L-shaped crop marks at each anchor in the bleed area."""
    length = _CROP_MARK_LENGTH
    parts = []
    for x, y in anchors:
        parts.extend(
            [
                f'<line x1="{x}" y1="{y}" x2="{x + length}" y2="{y}" '
                f'stroke="{_CROP_MARK_COLOR}" stroke-width="{_CROP_MARK_STROKE}"/>',
                f'<line x1="{x}" y1="{y}" x2="{x}" y2="{y + length}" '
                f'stroke="{_CROP_MARK_COLOR}" stroke-width="{_CROP_MARK_STROKE}"/>',
            ]
        )
    return "".join(parts)


def _sheet_svg(
    *,
    canvas_w: int,
    canvas_h: int,
    panel_content: str,
    fold_lines: list[int],
    crop_mark_anchors: list[tuple[int, int]],
    render_guides: bool = False,
    font_defs: str = "",
) -> str:
    """Assemble a full-sheet SVG document with ordered layers.

    Order (back to front): font-face defs (when supplied), white background,
    panel_content, fold-line guides (only when render_guides=True — fixes v1
    print bug), crop marks.
    """
    header = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{canvas_w}" height="{canvas_h}" '
        f'viewBox="0 0 {canvas_w} {canvas_h}">'
        f"{font_defs}"
    )
    fold_layer = ""
    if render_guides:
        fold_layer = (
            f'<g id="fold-lines" data-print="false">'
            f"{_render_fold_lines(fold_lines, canvas_h)}"
            f"</g>"
        )
    body = (
        f'<rect width="{canvas_w}" height="{canvas_h}" fill="#FFFFFF"/>'
        f"{panel_content}"
        f"{fold_layer}"
        f'<g id="crop-marks" data-print="true">'
        f"{_render_crop_marks(crop_mark_anchors)}"
        f"</g>"
    )
    return header + body + "</svg>"


def _resolve_shapes_for_panel(
    panel: PanelRect,
    recipes: tuple[str, ...],
    accent_hex: str,
    seed: int,
    density: str,
    section_heading: str | None = None,
) -> str:
    """Render all shape recipes declared for a panel, scaled by shape_density."""
    if not recipes:
        return ""
    if density == "sparse":
        recipes_to_render = recipes[:1]  # keep only the first recipe
    elif density == "dense":
        recipes_to_render = recipes + recipes[:1]  # duplicate first for more density
    else:
        recipes_to_render = recipes
    parts = []
    for i, recipe in enumerate(recipes_to_render):
        parts.append(render_shape(recipe, panel, accent_hex, seed=seed + i, text=section_heading))
    return "".join(parts)


def _spot_preserve_aspect_ratio(png_bytes: bytes) -> str:
    """Pick a crop anchor for a spot image based on its aspect ratio.

    Portrait-oriented images (h/w > 1.2) use ``xMidYMin slice`` so the top
    of the image (usually the subject) is kept when cropped to the panel's
    landscape slot. Landscape and near-square stay with center crop.
    """
    try:
        import io

        from PIL import Image

        with Image.open(io.BytesIO(png_bytes)) as im:
            w, h = im.size
        if w == 0:
            return "xMidYMid slice"
        if h / w > 1.2:
            return "xMidYMin slice"
        return "xMidYMid slice"
    except Exception:
        # If we can't parse the image (non-PNG, truncated bytes), keep center crop.
        return "xMidYMid slice"


def _render_spot_image(panel: PanelRect, png_bytes: bytes) -> str:
    """Embed a spot image in the top 40% of the panel's safe zone.

    Returns the <image> fragment. Caller is responsible for narrowing the text
    region so body doesn't overlap the image.
    """
    if not png_bytes:
        return ""
    b64 = base64.b64encode(png_bytes).decode()
    sx, sy, sw, sh = panel.safe_rect
    img_h = int(sh * 0.40)
    par = _spot_preserve_aspect_ratio(png_bytes)
    return (
        f'<image x="{sx}" y="{sy}" width="{sw}" height="{img_h}" '
        f'preserveAspectRatio="{par}" '
        f'href="data:image/png;base64,{b64}"/>'
    )


def _render_section_text_below_image(
    panel: PanelRect,
    section: BrochureSection,
    accent_hex: str,
    image_h: int,
    typ: _Typography,
) -> str:
    """Like _render_section_text but starts below a spot image occupying top image_h pixels."""
    sx, sy, sw, _ = panel.safe_rect
    heading_size = _fit_heading_font_size(section.heading, sw, typ.heading_size)
    text_top = sy + image_h + 16
    y = text_top + heading_size
    parts = [
        f'<text x="{sx}" y="{y}" '
        f'font-family="{typ.title_font}" font-size="{heading_size}" '
        f'fill="{accent_hex}">{escape(section.heading)}</text>',
        f'<rect x="{sx}" y="{y + 12}" width="{min(sw, 220)}" height="3" fill="{accent_hex}"/>',
    ]
    y += 24 + 16
    for kind, text in _parse_body(section.body):
        if kind == "bullet":
            lines = _wrap(text, typ.body_max_chars - 2)
            for i, line in enumerate(lines):
                y += typ.body_line_height
                prefix = "• " if i == 0 else "  "
                parts.append(
                    f'<text x="{sx}" y="{y}" '
                    f'font-family="{typ.body_font}" font-size="{typ.body_size}" '
                    f'fill="#333333">{escape(prefix + line)}</text>'
                )
        else:
            lines = _wrap(text, typ.body_max_chars)
            for line in lines:
                y += typ.body_line_height
                parts.append(
                    f'<text x="{sx}" y="{y}" '
                    f'font-family="{typ.body_font}" font-size="{typ.body_size}" '
                    f'fill="#333333">{escape(line)}</text>'
                )
            y += 12
    return "".join(parts)


def compose_brochure_svgs(
    brochure: BrochureInput,
    layout: ResolvedBrochureLayout,
    hero_png_bytes: bytes,
    layout_choice: LayoutChoice | None = None,
    template: LayoutTemplate | None = None,
    spot_images: dict[str, bytes] | None = None,
    *,
    render_guides: bool = False,
    hero_is_placeholder: bool = False,
) -> tuple[str, str]:
    """Return (outside_sheet_svg, inside_sheet_svg) as strings.

    Panel-to-content assignment (per brochure-plan.md §3):
      outside: [back_cover(6), front_cover(1), tuck_flap(2)]
        back_cover -> brochure.back_panel or org/contact fallback
        front_cover -> hero image + title/subtitle
        tuck_flap -> sections[0] compressed (heading + truncated body)
      inside: [inner_left(3), inner_center(4), inner_right(5)]
        inner_left/center/right -> sections[1], sections[2], sections[3] when present
        overflow sections[4] renders as a compact list at the bottom of inner_right
    """
    # Canvas size is the bleed canvas; derive from the first panel's bleed rect top-left being (0,0)
    # and any panel's bleed_rect (they all span full height already).
    any_panel = layout.outside_panels[0]
    canvas_w = max(p.bleed_rect[0] + p.bleed_rect[2] for p in layout.outside_panels)
    canvas_h = any_panel.bleed_rect[3]

    shape_density = layout_choice.shape_density if layout_choice is not None else "medium"
    seed_base = hash(brochure.title) & 0xFFFF
    typ = _typography(template)
    font_defs = build_font_face_defs(template) if template is not None else ""

    # --- OUTSIDE SHEET ---
    outside_parts: list[str] = []
    # Gradient on back cover and tuck flap only (front cover gets the hero image).
    for panel in layout.outside_panels:
        if panel.name == "front_cover":
            if hero_is_placeholder:
                # No real hero → render gradient + shapes + high-contrast title.
                # The previous behavior rendered white-on-white text over a 1×1
                # transparent PNG, making the cover panel silently blank.
                outside_parts.append(
                    _render_placeholder_cover(
                        panel, brochure.title, brochure.subtitle,
                        brochure.color_accent, typ,
                    )
                )
                if template is not None:
                    outside_parts.append(
                        _resolve_shapes_for_panel(
                            panel,
                            template.shape_mix.get("front_cover", ())
                            or template.shape_mix.get("cover", ()),
                            brochure.color_accent, seed_base + 2, shape_density,
                        )
                    )
            else:
                outside_parts.append(_render_hero_image(panel, hero_png_bytes))
                outside_parts.append(
                    _render_cover_text(panel, brochure.title, brochure.subtitle, typ)
                )
        elif panel.name == "back_cover":
            outside_parts.append(_render_panel_gradient(panel, brochure.color_accent))
            if template is not None:
                outside_parts.append(
                    _resolve_shapes_for_panel(
                        panel, template.shape_mix.get(panel.name, ()),
                        brochure.color_accent, seed_base, shape_density,
                    )
                )
            outside_parts.append(_render_back_panel_text(panel, brochure, typ))
        elif panel.name == "tuck_flap":
            outside_parts.append(_render_panel_gradient(panel, brochure.color_accent))
            # Tuck flap shows the FOURTH section (index 3) when present, so it doesn't
            # duplicate an inner panel. When N < 4, tuck flap is gradient + shapes only
            # (handled below — skip text).
            tuck_section = (
                brochure.sections[3] if len(brochure.sections) >= 4 else None
            )
            # When we do have a tuck section, keep it compact (2 sentences max).
            compressed: BrochureSection | None = None
            if tuck_section is not None:
                body_first = tuck_section.body.split(". ")
                compressed_body = ". ".join(body_first[:2]).strip().rstrip(".") + "."
                compressed = BrochureSection(
                    heading=tuck_section.heading,
                    body=compressed_body,
                    icon_hint=tuck_section.icon_hint,
                )
            tuck_spot = (
                spot_images.get(tuck_section.heading)
                if (tuck_section is not None and spot_images)
                else None
            )
            if template is not None:
                outside_parts.append(
                    _resolve_shapes_for_panel(
                        panel, template.shape_mix.get(panel.name, ()),
                        brochure.color_accent, seed_base + 1, shape_density,
                        section_heading=compressed.heading if compressed else None,
                    )
                )
            if compressed is not None and tuck_spot is not None:
                outside_parts.append(_render_spot_image(panel, tuck_spot))
                image_h = int(panel.safe_rect[3] * 0.40)
                outside_parts.append(
                    _render_section_text_below_image(
                        panel, compressed, brochure.color_accent, image_h, typ
                    )
                )
            elif compressed is not None:
                outside_parts.append(
                    _render_section_text(panel, compressed, brochure.color_accent, typ)
                )
            else:
                # N<4 case: no section to land here. Fill with org name + tagline
                # so the closed brochure has content on every panel.
                outside_parts.append(
                    _render_tuck_flap_tagline(
                        panel, brochure.org, brochure.color_accent, typ
                    )
                )

    outside_svg = _sheet_svg(
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        panel_content="".join(outside_parts),
        fold_lines=layout.fold_lines_outside,
        crop_mark_anchors=layout.crop_marks[:4],
        render_guides=render_guides,
        font_defs=font_defs,
    )

    # --- INSIDE SHEET ---
    inside_parts: list[str] = []
    # Inner-first section assignment:
    #   N=2: sections[0..1] → inner_left, inner_right (inner_center stays empty for breathing room)
    #   N=3: sections[0..2] → inner_left, inner_center, inner_right (tuck flap already shows sections[0] too — OK, it's the same section)
    #   N>=4: sections[0..2] → inner panels, sections[3+] → tuck flap + overflow handled above
    inside_sections: list[BrochureSection | None]
    n = len(brochure.sections)
    if n == 2:
        inside_sections = [brochure.sections[0], None, brochure.sections[1]]
    else:
        # n >= 3: fill all three inner panels with the first three sections.
        inside_sections = [
            brochure.sections[0] if n >= 1 else None,
            brochure.sections[1] if n >= 2 else None,
            brochure.sections[2] if n >= 3 else None,
        ]

    for idx, (panel, section) in enumerate(zip(layout.inside_panels, inside_sections)):
        inside_parts.append(_render_panel_gradient(panel, brochure.color_accent))

        # Spot image lookup by heading match.
        spot_bytes = None
        if spot_images and section is not None and section.heading in spot_images:
            spot_bytes = spot_images[section.heading]

        if template is not None:
            inside_parts.append(
                _resolve_shapes_for_panel(
                    panel, template.shape_mix.get(panel.name, ()),
                    brochure.color_accent, seed_base + 10 + idx, shape_density,
                    section_heading=section.heading if section else None,
                )
            )

        if spot_bytes is not None:
            # Render image top, text below (using image_h = 40% of safe_rect height).
            inside_parts.append(_render_spot_image(panel, spot_bytes))
            if section is not None:
                image_h = int(panel.safe_rect[3] * 0.40)
                inside_parts.append(
                    _render_section_text_below_image(
                        panel, section, brochure.color_accent, image_h, typ
                    )
                )
        elif section is not None:
            inside_parts.append(
                _render_section_text(panel, section, brochure.color_accent, typ)
            )
        else:
            # N=2 case: inner_center has no section. Fill with org name + tagline
            # so no inner panel ships blank. Mirror the tuck-flap tagline pattern.
            inside_parts.append(
                _render_tuck_flap_tagline(
                    panel, brochure.org, brochure.color_accent, typ
                )
            )

    # Overflow section[4] → bottom of rightmost inner panel as a compact list.
    # With the new inner-first assignment: sections[0..2] fill inner panels,
    # sections[3] goes to tuck flap, sections[4] overflows here.
    if len(brochure.sections) >= 5:
        right_panel = layout.inside_panels[-1]
        overflow = brochure.sections[4]
        sx, sy, sw, sh = right_panel.safe_rect
        overflow_heading_size = max(typ.heading_size // 2, typ.body_size + 8)
        y = sy + sh - (typ.body_line_height * 4)
        inside_parts.append(
            f'<text x="{sx}" y="{y}" '
            f'font-family="{typ.title_font}" font-size="{overflow_heading_size}" '
            f'fill="{brochure.color_accent}">{escape(overflow.heading)}</text>'
        )
        for line in _wrap(overflow.body, typ.body_max_chars)[:3]:
            y += typ.body_line_height
            inside_parts.append(
                f'<text x="{sx}" y="{y}" '
                f'font-family="{typ.body_font}" font-size="{typ.body_size - 6}" '
                f'fill="#555555">{escape(line)}</text>'
            )

    inside_svg = _sheet_svg(
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        panel_content="".join(inside_parts),
        fold_lines=layout.fold_lines_inside,
        crop_mark_anchors=layout.crop_marks[4:],
        render_guides=render_guides,
        font_defs=font_defs,
    )

    return outside_svg, inside_svg
