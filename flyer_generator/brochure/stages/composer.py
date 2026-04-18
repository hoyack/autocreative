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
from xml.sax.saxutils import escape

from flyer_generator.brochure.models import (
    BrochureInput,
    BrochureSection,
    PanelRect,
    ResolvedBrochureLayout,
)
from flyer_generator.errors import CompositionError

_FONT_TITLE = "'Arial Black', Arial, sans-serif"
_FONT_BODY = "Arial, sans-serif"

_HEADING_FONT_SIZE = 64
_BODY_FONT_SIZE = 36
_BODY_LINE_HEIGHT = 44
_BODY_MAX_CHARS_PER_LINE = 28

_TITLE_FONT_SIZE = 110
_SUBTITLE_FONT_SIZE = 48

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


def _render_cover_text(panel: PanelRect, title: str, subtitle: str | None) -> str:
    """Title + optional subtitle overlaid on the cover panel safe area."""
    sx, sy, sw, sh = panel.safe_rect
    cx = sx + sw // 2
    title_y = sy + sh // 3  # upper third
    title = title.upper()
    parts = [
        f'<text x="{cx}" y="{title_y}" text-anchor="middle" '
        f'font-family="{_FONT_TITLE}" font-size="{_TITLE_FONT_SIZE}" '
        f'fill="#FFFFFF" stroke="#000000" stroke-width="3" paint-order="stroke">'
        f"{escape(title)}</text>"
    ]
    if subtitle:
        sub_y = title_y + _TITLE_FONT_SIZE + 16
        parts.append(
            f'<text x="{cx}" y="{sub_y}" text-anchor="middle" '
            f'font-family="{_FONT_BODY}" font-size="{_SUBTITLE_FONT_SIZE}" '
            f'fill="#FFFFFF" stroke="#000000" stroke-width="2" paint-order="stroke">'
            f"{escape(subtitle)}</text>"
        )
    return "".join(parts)


def _render_section_text(panel: PanelRect, section: BrochureSection, accent_hex: str) -> str:
    """Heading + wrapped body text for an inner panel."""
    sx, sy, sw, _ = panel.safe_rect
    y = sy + _HEADING_FONT_SIZE
    parts = [
        f'<text x="{sx}" y="{y}" '
        f'font-family="{_FONT_TITLE}" font-size="{_HEADING_FONT_SIZE}" '
        f'fill="{accent_hex}">{escape(section.heading)}</text>'
    ]
    y += 24  # gap after heading
    for kind, text in _parse_body(section.body):
        if kind == "bullet":
            lines = _wrap(text, _BODY_MAX_CHARS_PER_LINE - 2)
            for i, line in enumerate(lines):
                y += _BODY_LINE_HEIGHT
                prefix = "• " if i == 0 else "  "
                parts.append(
                    f'<text x="{sx}" y="{y}" '
                    f'font-family="{_FONT_BODY}" font-size="{_BODY_FONT_SIZE}" '
                    f'fill="#333333">{escape(prefix + line)}</text>'
                )
        else:
            lines = _wrap(text, _BODY_MAX_CHARS_PER_LINE)
            for line in lines:
                y += _BODY_LINE_HEIGHT
                parts.append(
                    f'<text x="{sx}" y="{y}" '
                    f'font-family="{_FONT_BODY}" font-size="{_BODY_FONT_SIZE}" '
                    f'fill="#333333">{escape(line)}</text>'
                )
            y += 12  # paragraph gap
    return "".join(parts)


def _render_back_panel_text(panel: PanelRect, brochure: BrochureInput) -> str:
    """Back-cover panel content: back_panel if provided, else org + contact block."""
    sx, sy, sw, _sh = panel.safe_rect
    parts: list[str] = []
    y = sy + _HEADING_FONT_SIZE
    if brochure.back_panel is not None:
        parts.append(
            f'<text x="{sx}" y="{y}" '
            f'font-family="{_FONT_TITLE}" font-size="{_HEADING_FONT_SIZE}" '
            f'fill="{brochure.color_accent}">'
            f"{escape(brochure.back_panel.kind.replace('_', ' ').upper())}</text>"
        )
        y += _HEADING_FONT_SIZE
        for line in _wrap(brochure.back_panel.content, _BODY_MAX_CHARS_PER_LINE):
            y += _BODY_LINE_HEIGHT
            parts.append(
                f'<text x="{sx}" y="{y}" '
                f'font-family="{_FONT_BODY}" font-size="{_BODY_FONT_SIZE}" '
                f'fill="#333333">{escape(line)}</text>'
            )
        return "".join(parts)

    # Fallback: org + contact
    parts.append(
        f'<text x="{sx}" y="{y}" '
        f'font-family="{_FONT_TITLE}" font-size="{_HEADING_FONT_SIZE}" '
        f'fill="{brochure.color_accent}">{escape(brochure.org)}</text>'
    )
    if brochure.contact is not None:
        for attr in ("name", "phone", "email", "url", "address"):
            value = getattr(brochure.contact, attr)
            if value:
                y += _BODY_LINE_HEIGHT
                parts.append(
                    f'<text x="{sx}" y="{y}" '
                    f'font-family="{_FONT_BODY}" font-size="{_BODY_FONT_SIZE}" '
                    f'fill="#333333">{escape(value)}</text>'
                )
    return "".join(parts)


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
) -> str:
    """Assemble a full-sheet SVG document with ordered layers.

    Order (back to front): white background, panel_content, fold-line guides
    (non-printing), crop marks.
    """
    header = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{canvas_w}" height="{canvas_h}" '
        f'viewBox="0 0 {canvas_w} {canvas_h}">'
    )
    body = (
        f'<rect width="{canvas_w}" height="{canvas_h}" fill="#FFFFFF"/>'
        f"{panel_content}"
        f'<g id="fold-lines" data-print="false">'
        f"{_render_fold_lines(fold_lines, canvas_h)}"
        f"</g>"
        f'<g id="crop-marks" data-print="true">'
        f"{_render_crop_marks(crop_mark_anchors)}"
        f"</g>"
    )
    return header + body + "</svg>"


def compose_brochure_svgs(
    brochure: BrochureInput,
    layout: ResolvedBrochureLayout,
    hero_png_bytes: bytes,
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

    # --- OUTSIDE SHEET ---
    outside_parts: list[str] = []
    # Gradient on back cover and tuck flap only (front cover gets the hero image).
    for panel in layout.outside_panels:
        if panel.name == "front_cover":
            outside_parts.append(_render_hero_image(panel, hero_png_bytes))
            outside_parts.append(
                _render_cover_text(panel, brochure.title, brochure.subtitle)
            )
        elif panel.name == "back_cover":
            outside_parts.append(_render_panel_gradient(panel, brochure.color_accent))
            outside_parts.append(_render_back_panel_text(panel, brochure))
        elif panel.name == "tuck_flap":
            outside_parts.append(_render_panel_gradient(panel, brochure.color_accent))
            # Tuck flap carries a compressed version of the first section.
            first_section = brochure.sections[0]
            body_first = first_section.body.split(". ")
            compressed_body = ". ".join(body_first[:2]).strip().rstrip(".") + "."
            compressed = BrochureSection(
                heading=first_section.heading,
                body=compressed_body,
                icon_hint=first_section.icon_hint,
            )
            outside_parts.append(
                _render_section_text(panel, compressed, brochure.color_accent)
            )

    outside_svg = _sheet_svg(
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        panel_content="".join(outside_parts),
        fold_lines=layout.fold_lines_outside,
        crop_mark_anchors=layout.crop_marks[:4],
    )

    # --- INSIDE SHEET ---
    inside_parts: list[str] = []
    # Section assignment: sections[1..3] into inner_left/center/right.
    # If only 2 sections exist (minimum), inner_center and inner_right may be empty.
    inside_sections: list[BrochureSection | None] = []
    for idx in (1, 2, 3):
        inside_sections.append(
            brochure.sections[idx] if idx < len(brochure.sections) else None
        )

    for panel, section in zip(layout.inside_panels, inside_sections):
        inside_parts.append(_render_panel_gradient(panel, brochure.color_accent))
        if section is not None:
            inside_parts.append(
                _render_section_text(panel, section, brochure.color_accent)
            )

    # Overflow section[4] → bottom of rightmost inner panel as a compact list.
    if len(brochure.sections) == 5:
        right_panel = layout.inside_panels[-1]
        overflow = brochure.sections[4]
        sx, sy, sw, sh = right_panel.safe_rect
        y = sy + sh - (_BODY_LINE_HEIGHT * 4)
        inside_parts.append(
            f'<text x="{sx}" y="{y}" '
            f'font-family="{_FONT_TITLE}" font-size="{_HEADING_FONT_SIZE // 2}" '
            f'fill="{brochure.color_accent}">{escape(overflow.heading)}</text>'
        )
        for line in _wrap(overflow.body, _BODY_MAX_CHARS_PER_LINE)[:3]:
            y += _BODY_LINE_HEIGHT
            inside_parts.append(
                f'<text x="{sx}" y="{y}" '
                f'font-family="{_FONT_BODY}" font-size="{_BODY_FONT_SIZE - 6}" '
                f'fill="#555555">{escape(line)}</text>'
            )

    inside_svg = _sheet_svg(
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        panel_content="".join(inside_parts),
        fold_lines=layout.fold_lines_inside,
        crop_mark_anchors=layout.crop_marks[4:],
    )

    return outside_svg, inside_svg
