"""Schema → SVG renderer.

Walks a TemplateSchema + BrochureContent pair and emits two SVG strings
(outside sheet, inside sheet), sized to the bleed canvas used by the rest
of the brochure pipeline (3376×2626).

Element coordinates in a template are *panel-local*: (0,0) is the top-left
of that panel's **trim** rect, and a panel is 1100×2550 pixels wide. The
renderer wraps each panel's elements in a `<g transform="translate(tx, ty)">`
so shape authors don't need to know absolute sheet coordinates.

`bleed` on a shape extends the rect outward toward the panel's bleed edges
(dynamically derived from `compute_panel_layout()`).
"""

from __future__ import annotations

import base64
from typing import Iterable
from xml.sax.saxutils import escape as xml_escape

from flyer_generator.brochure.models import PanelRect
from flyer_generator.brochure.schema_renderer.content_model import BrochureContent
from flyer_generator.brochure.schema_renderer.schema_model import (
    BulletsElement,
    DividerElement,
    ImagePlaceholder,
    LogoPlaceholder,
    PanelSchema,
    ShapeElement,
    TemplateSchema,
    TextElement,
)
from flyer_generator.brochure.schema_renderer.shapes import (
    _fill_opacity,
    render_fill,
    render_shape,
)
from flyer_generator.brochure.schema_renderer.text_fit import (
    chars_per_line,
    fit_to_bbox,
    wrap_text,
)
from flyer_generator.brochure.stages.layout import (
    BLEED_CANVAS_HEIGHT,
    BLEED_CANVAS_WIDTH,
    compute_panel_layout,
)

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

_PANEL_TRIM_W = 1100
_PANEL_TRIM_H = 2550

_ROLE_FONT_SIZE = {
    "cover_title": "cover_title_size",
    "cover_subtitle": "cover_subtitle_size",
    "section_heading": "heading_size",
    "lead_paragraph": "body_size",
    "body": "body_size",
    "quote": "heading_size",
    "bullet": "bullet_size",
    "cta_heading": "heading_size",
    "cta_body": "body_size",
    "org_name": "heading_size",
    "contact_name": "body_size",
    "contact_phone": "body_size",
    "contact_email": "body_size",
    "contact_url": "body_size",
    "contact_address": "body_size",
    "tagline": "cover_subtitle_size",
    "static": "body_size",
}

_ROLE_LINE_HEIGHT = {
    "cover_title": 1.05,
    "cover_subtitle": 1.25,
    "section_heading": 1.1,
    "lead_paragraph": 1.28,
    "body": 1.28,
    "quote": 1.2,
    "bullet": 1.35,
    "cta_heading": 1.1,
    "cta_body": 1.28,
    "org_name": 1.1,
    "contact_name": 1.28,
    "contact_phone": 1.28,
    "contact_email": 1.28,
    "contact_url": 1.28,
    "contact_address": 1.28,
    "tagline": 1.2,
    "static": 1.28,
}


def panel_bleed_margins(p: PanelRect) -> dict[str, int]:
    tx, ty, tw, th = p.trim_rect
    bx, by, bw, bh = p.bleed_rect
    return {
        "left": tx - bx,
        "top": ty - by,
        "right": (bx + bw) - (tx + tw),
        "bottom": (by + bh) - (ty + th),
    }


def _apply_panel_bleed(
    rect: tuple[float, float, float, float],
    bleed,
    margins: dict[str, int],
) -> tuple[float, float, float, float]:
    """Extend a panel-local rect into that panel's bleed margin."""
    if not bleed:
        return rect
    x, y, w, h = rect
    sides = (
        ("left", "top", "right", "bottom")
        if bleed in (True, "all")
        else (bleed,)
    )
    if "left" in sides:
        w += x + margins["left"]  # new width grows left by margin + any existing inset
        x = -margins["left"]
    if "top" in sides:
        h += y + margins["top"]
        y = -margins["top"]
    if "right" in sides:
        w = (_PANEL_TRIM_W + margins["right"]) - x
    if "bottom" in sides:
        h = (_PANEL_TRIM_H + margins["bottom"]) - y
    return (x, y, w, h)


def _render_shape_panel_local(
    el: ShapeElement,
    margins: dict[str, int],
    salt: str,
    textures: dict[str, bytes] | None = None,
) -> str:
    """Render a shape element using panel-local coords + panel bleed margins."""
    # Clone with adjusted rect if bleed
    if el.rect is not None and el.bleed:
        new_rect = _apply_panel_bleed(el.rect, el.bleed, margins)
        effective = el.model_copy(update={"rect": new_rect, "bleed": False})
    else:
        effective = el
    # Use shapes.render_shape with a canvas_rect covering panel + margins
    canvas = (
        -margins["left"],
        -margins["top"],
        _PANEL_TRIM_W + margins["left"] + margins["right"],
        _PANEL_TRIM_H + margins["top"] + margins["bottom"],
    )
    return render_shape(effective, canvas, salt, textures)


# --------------------------------------------------------------------------- #
# Text rendering
# --------------------------------------------------------------------------- #


def _typography_field(schema: TemplateSchema, name: str) -> int | str | None:
    return getattr(schema.typography, name, None)


def _resolve_font(el: TextElement | BulletsElement, schema: TemplateSchema) -> tuple[str, int, int]:
    """Return (font_family, font_size, line_height) for a text-like element."""
    # Font family
    if getattr(el, "font_family", None):
        family = el.font_family  # type: ignore[assignment]
    elif hasattr(el, "role") and el.role in ("cover_title", "section_heading", "cta_heading", "org_name", "quote"):
        family = schema.typography.heading_family
    else:
        family = schema.typography.body_family

    # Size
    if getattr(el, "font_size", None):
        size = el.font_size  # type: ignore[assignment]
    elif hasattr(el, "role"):
        size = getattr(schema.typography, _ROLE_FONT_SIZE.get(el.role, "body_size"))
    else:
        size = schema.typography.bullet_size

    # Line height
    if getattr(el, "line_height", None):
        lh = el.line_height  # type: ignore[assignment]
    elif hasattr(el, "role"):
        lh = int(size * _ROLE_LINE_HEIGHT.get(el.role, 1.3))
    else:
        lh = schema.typography.bullet_line_height

    return family, int(size), int(lh)


def _resolve_text_content(el: TextElement, content: BrochureContent) -> str:
    if el.role == "static" or el.content_key is None:
        return el.static_text or ""
    raw = content.resolve_key(el.content_key, el.section_index)
    if raw is None:
        return ""
    if isinstance(raw, list):
        return ", ".join(str(item) for item in raw)
    return str(raw)


def _render_text_element(
    el: TextElement,
    content: BrochureContent,
    schema: TemplateSchema,
) -> str:
    text = _resolve_text_content(el, content)
    if not text:
        return ""
    if el.uppercase:
        text = text.upper()
    if el.max_chars and len(text) > el.max_chars:
        # Truncate politely on word boundary
        truncated = text[: el.max_chars].rsplit(" ", 1)[0]
        text = truncated + "…"

    family, size, lh = _resolve_font(el, schema)
    fitted = fit_to_bbox(
        text,
        el.bbox,
        font_size=size,
        line_height=lh,
        font_family=family,
    )
    x, y, w, h = el.bbox
    color = el.color or schema.palette.neutral_dark
    weight = {"normal": "400", "medium": "500", "semibold": "600", "bold": "700"}[el.weight]
    font_style = "italic" if el.italic else "normal"

    # Horizontal alignment
    anchor = {"left": "start", "center": "middle", "right": "end", "justify": "start"}[el.align]
    if el.align == "center":
        tx = x + w / 2
    elif el.align == "right":
        tx = x + w
    else:
        tx = x

    # Vertical alignment
    if el.valign == "top":
        y_start = y + size
    elif el.valign == "middle":
        y_start = y + h / 2 - (len(fitted.lines) * lh) / 2 + size
    else:
        y_start = y + h - (len(fitted.lines) - 1) * lh

    tspans = []
    for i, line in enumerate(fitted.lines):
        dy = lh if i > 0 else 0
        safe = xml_escape(line)
        tspans.append(f'<tspan x="{tx}" dy="{dy}">{safe}</tspan>')

    letter_sp = (
        f' letter-spacing="{el.letter_spacing}"' if el.letter_spacing else ""
    )
    return (
        f'<text x="{tx}" y="{y_start}" text-anchor="{anchor}" '
        f'font-family="{family}" font-size="{size}" font-weight="{weight}" '
        f'font-style="{font_style}" fill="{color}"{letter_sp}>'
        f'{"".join(tspans)}</text>'
    )


def _render_bullets_element(
    el: BulletsElement,
    content: BrochureContent,
    schema: TemplateSchema,
) -> str:
    raw = content.resolve_key(el.content_key, el.section_index)
    if not raw or not isinstance(raw, list):
        return ""
    items = [str(i) for i in raw][: el.max_items]
    if not items:
        return ""

    family, size, lh = _resolve_font(el, schema)
    x, y, w, h = el.bbox
    text_color = el.text_color or schema.palette.neutral_dark
    bullet_color = el.bullet_color or schema.palette.accent_default

    indent = size * 1.2  # space for bullet marker
    cpl = chars_per_line(w - indent, size, family)
    cpl = min(cpl, el.max_chars_per_item)

    cursor_y = y + size  # first baseline
    parts: list[str] = []
    for idx, item in enumerate(items):
        # Wrap
        lines = wrap_text(item, cpl)
        if not lines:
            continue
        # Bullet marker
        marker_cy = cursor_y - size * 0.3
        if el.bullet_style == "disc":
            marker = (
                f'<circle cx="{x + size * 0.35}" cy="{marker_cy}" r="{size * 0.18}" '
                f'fill="{bullet_color}"/>'
            )
        elif el.bullet_style == "square":
            marker = (
                f'<rect x="{x + size * 0.1}" y="{marker_cy - size * 0.2}" '
                f'width="{size * 0.4}" height="{size * 0.4}" fill="{bullet_color}"/>'
            )
        elif el.bullet_style == "accent_block":
            marker = (
                f'<rect x="{x}" y="{cursor_y - size * 0.9}" '
                f'width="{size * 0.12}" height="{lh * len(lines) - 6}" fill="{bullet_color}"/>'
            )
        elif el.bullet_style == "numbered":
            marker = (
                f'<text x="{x}" y="{cursor_y}" font-family="{family}" '
                f'font-size="{size}" fill="{bullet_color}" font-weight="600">{idx + 1}.</text>'
            )
        else:  # dash
            marker = (
                f'<line x1="{x + size * 0.1}" y1="{marker_cy}" '
                f'x2="{x + size * 0.7}" y2="{marker_cy}" '
                f'stroke="{bullet_color}" stroke-width="{size * 0.12}"/>'
            )
        parts.append(marker)
        # Lines
        for i, line in enumerate(lines):
            safe = xml_escape(line)
            parts.append(
                f'<text x="{x + indent}" y="{cursor_y + i * lh}" '
                f'font-family="{family}" font-size="{size}" fill="{text_color}">{safe}</text>'
            )
        cursor_y += lh * len(lines) + el.item_spacing
        # Overflow guard
        if cursor_y > y + h:
            break
    return "".join(parts)


def _render_logo_placeholder(
    el: LogoPlaceholder,
    content: BrochureContent,
    schema: TemplateSchema,
) -> str:
    """Render a monogram (Phase 1 fallback). Phase 6 will support real logos."""
    x, y, w, h = el.bbox
    bg_color = el.fallback_color or schema.palette.accent_default
    # Monogram: take the first letter of each word in org, up to 2 letters
    org = content.org.strip() or "•"
    words = [w for w in org.split() if w]
    initials = "".join(w[0] for w in words[:2]).upper() or "•"

    cx = x + w / 2
    cy = y + h / 2
    # Use ~0.55 of the smallest dimension as radius (for circle) / rect side
    radius = min(w, h) / 2

    if el.fallback_style == "monogram_square":
        shape = (
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{w * 0.1}" ry="{w * 0.1}" '
            f'fill="{bg_color}"/>'
        )
    elif el.fallback_style == "initials_plain":
        shape = ""
    else:  # monogram_circle
        shape = f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="{bg_color}"/>'

    letter_color = (
        schema.palette.neutral_light if el.fallback_style != "initials_plain" else schema.palette.accent_default
    )
    letter_size = int(min(w, h) * 0.5)
    letter_family = schema.typography.heading_family
    baseline_shift = letter_size * 0.35
    text = (
        f'<text x="{cx}" y="{cy + baseline_shift}" text-anchor="middle" '
        f'font-family="{letter_family}" font-size="{letter_size}" '
        f'font-weight="700" fill="{letter_color}">{xml_escape(initials)}</text>'
    )
    return shape + text


def _embed_image(
    el: ImagePlaceholder,
    image_bytes: bytes,
    salt: str,
) -> str:
    """Embed `image_bytes` as base64 PNG inside the placeholder's bbox.

    Uses preserveAspectRatio="xMidYMid slice" so the image always fills the
    bbox (cropping the overflowing side), and applies a clipPath when the
    placeholder requests a rounded or circle mask.
    """
    x, y, w, h = el.bbox
    b64 = base64.b64encode(image_bytes).decode("ascii")
    href = f"data:image/png;base64,{b64}"
    image_tag = (
        f'<image x="{x}" y="{y}" width="{w}" height="{h}" '
        f'preserveAspectRatio="xMidYMid slice" href="{href}"'
    )

    if el.mask == "circle":
        r = min(w, h) / 2
        cx = x + w / 2
        cy = y + h / 2
        clip_id = f"img-clip-{salt}"
        clip = (
            f'<defs><clipPath id="{clip_id}">'
            f'<circle cx="{cx}" cy="{cy}" r="{r}"/>'
            f"</clipPath></defs>"
        )
        return f'{clip}{image_tag} clip-path="url(#{clip_id})"/>'

    if el.mask == "rounded":
        rx = el.corner_radius if el.corner_radius else 40
        clip_id = f"img-clip-{salt}"
        clip = (
            f'<defs><clipPath id="{clip_id}">'
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
            f'rx="{rx}" ry="{rx}"/>'
            f"</clipPath></defs>"
        )
        return f'{clip}{image_tag} clip-path="url(#{clip_id})"/>'

    # mask == "none"
    return f"{image_tag}/>"


def _render_image_placeholder(
    el: ImagePlaceholder,
    content: BrochureContent,
    schema: TemplateSchema,
    images: dict[str, bytes] | None = None,
    salt: str = "img",
    textures: dict[str, bytes] | None = None,
) -> str:
    """Render an image_placeholder.

    When `images` contains this element's slot, embed the PNG bytes as a
    base64 data URL with the appropriate clip path. Otherwise render the
    fallback fill — Phase 1 behavior — so design-only renders still work.
    `textures` is passed through in case a fallback_fill is a texture_slot.
    """
    if images is not None and el.slot in images:
        return _embed_image(el, images[el.slot], salt)

    x, y, w, h = el.bbox
    # Derive default fallback fill if not set: light gradient from accent muted to neutral_light
    if el.fallback_fill is None:
        from flyer_generator.brochure.schema_renderer.schema_model import (
            GradientStop,
            LinearGradientFill,
        )

        fallback = LinearGradientFill(
            stops=[
                GradientStop(
                    offset=0.0, color=schema.palette.accent_default, opacity=0.22
                ),
                GradientStop(
                    offset=1.0, color=schema.palette.neutral_light, opacity=0.9
                ),
            ],
            angle=135,
        )
    else:
        fallback = el.fallback_fill

    defs, fill_val = render_fill(fallback, f"img-{el.slot}-{int(x)}", textures)
    opacity = _fill_opacity(fallback)

    if el.mask == "circle":
        r = min(w, h) / 2
        cx = x + w / 2
        cy = y + h / 2
        body = (
            f'<circle cx="{cx}" cy="{cy}" r="{r}" '
            f'fill="{fill_val}" fill-opacity="{opacity:.4f}"/>'
        )
    elif el.mask == "rounded":
        rx = el.corner_radius if el.corner_radius else 40
        body = (
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" ry="{rx}" '
            f'fill="{fill_val}" fill-opacity="{opacity:.4f}"/>'
        )
    else:
        body = (
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
            f'fill="{fill_val}" fill-opacity="{opacity:.4f}"/>'
        )

    label = ""
    if el.show_placeholder_label:
        label_text = f"[ {el.slot} ]"
        size = 40
        label = (
            f'<text x="{x + w / 2}" y="{y + h / 2 + size / 3}" '
            f'text-anchor="middle" font-family="{schema.typography.body_family}" '
            f'font-size="{size}" fill="{schema.palette.neutral_dark}" '
            f'opacity="0.55">{xml_escape(label_text)}</text>'
        )

    return defs + body + label


def _render_divider(el: DividerElement) -> str:
    x1, y1, x2, y2 = el.position
    dash = ""
    if el.dash:
        dash = f' stroke-dasharray="{" ".join(str(d) for d in el.dash)}"'
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{el.color}" stroke-width="{el.thickness}" '
        f'stroke-opacity="{el.opacity:.4f}"{dash}/>'
    )


# --------------------------------------------------------------------------- #
# Panel + sheet assembly
# --------------------------------------------------------------------------- #


def _render_panel(
    panel: PanelSchema,
    panel_rect: PanelRect,
    content: BrochureContent,
    schema: TemplateSchema,
    images: dict[str, bytes] | None = None,
    textures: dict[str, bytes] | None = None,
) -> str:
    tx, ty, tw, th = panel_rect.trim_rect
    margins = panel_bleed_margins(panel_rect)

    # Sort elements by z-order (lowest first → bottom)
    elements = sorted(panel.elements, key=lambda e: getattr(e, "z", 0))

    parts: list[str] = []

    # Optional full-panel background fill — drawn in bleed rect
    if panel.background is not None:
        defs, fill_val = render_fill(
            panel.background, f"bg-{panel_rect.name}", textures
        )
        opacity = _fill_opacity(panel.background)
        bg_rect = (
            -margins["left"],
            -margins["top"],
            tw + margins["left"] + margins["right"],
            th + margins["top"] + margins["bottom"],
        )
        bx, by, bw, bh = bg_rect
        parts.append(defs)
        parts.append(
            f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" '
            f'fill="{fill_val}" fill-opacity="{opacity:.4f}"/>'
        )

    # Draw each element
    salt_counter = 0
    for el in elements:
        salt = f"{panel_rect.name}-{salt_counter}"
        salt_counter += 1
        if isinstance(el, ShapeElement):
            parts.append(_render_shape_panel_local(el, margins, salt, textures))
        elif isinstance(el, TextElement):
            parts.append(_render_text_element(el, content, schema))
        elif isinstance(el, BulletsElement):
            parts.append(_render_bullets_element(el, content, schema))
        elif isinstance(el, LogoPlaceholder):
            parts.append(_render_logo_placeholder(el, content, schema))
        elif isinstance(el, ImagePlaceholder):
            parts.append(
                _render_image_placeholder(el, content, schema, images, salt, textures)
            )
        elif isinstance(el, DividerElement):
            parts.append(_render_divider(el))

    return (
        f'<g transform="translate({tx}, {ty})">' + "".join(parts) + "</g>"
    )


def _render_crop_marks(layout) -> str:
    """Crop marks on outside + inside sheets. 72px length, 6px stroke."""
    length = 72
    stroke = 6
    color = "#000000"
    parts = [f'<g id="crop-marks" stroke="{color}" stroke-width="{stroke}">']
    for mx, my in layout.crop_marks:
        # horizontal tick
        parts.append(
            f'<line x1="{mx - length}" y1="{my}" x2="{mx + length}" y2="{my}"/>'
        )
        # vertical tick
        parts.append(
            f'<line x1="{mx}" y1="{my - length}" x2="{mx}" y2="{my + length}"/>'
        )
    parts.append("</g>")
    return "".join(parts)


def _render_sheet(
    panels: Iterable[tuple[PanelRect, PanelSchema]],
    layout,
    schema: TemplateSchema,
    content: BrochureContent,
    sheet_name: str,
    images: dict[str, bytes] | None = None,
    textures: dict[str, bytes] | None = None,
) -> str:
    body = "".join(
        _render_panel(panel_schema, panel_rect, content, schema, images, textures)
        for panel_rect, panel_schema in panels
    )
    # Crop marks only for this sheet's corners
    sheet_marks: list[tuple[int, int]] = []
    for p in panels:
        pr = p[0]
        bx, by, bw, bh = pr.bleed_rect
        # Corners: (bx, by), (bx+bw, by), (bx, by+bh), (bx+bw, by+bh)
        # But we only emit outer corners — i.e., for sheet-level crop marks we
        # reuse layout.crop_marks which already contains the 4 sheet corners
        # per outside/inside sheet.
    # Use layout.crop_marks: first 4 are outside, last 4 are inside.
    if sheet_name == "outside":
        marks = layout.crop_marks[:4]
    else:
        marks = layout.crop_marks[4:]
    cp_parts = [f'<g id="crop-marks-{sheet_name}" stroke="#000" stroke-width="6">']
    for mx, my in marks:
        length = 72
        cp_parts.append(
            f'<line x1="{mx - length}" y1="{my}" x2="{mx + length}" y2="{my}"/>'
        )
        cp_parts.append(
            f'<line x1="{mx}" y1="{my - length}" x2="{mx}" y2="{my + length}"/>'
        )
    cp_parts.append("</g>")
    crop = "".join(cp_parts)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{BLEED_CANVAS_WIDTH}" height="{BLEED_CANVAS_HEIGHT}" '
        f'viewBox="0 0 {BLEED_CANVAS_WIDTH} {BLEED_CANVAS_HEIGHT}">'
        f'<rect width="{BLEED_CANVAS_WIDTH}" height="{BLEED_CANVAS_HEIGHT}" fill="white"/>'
        f"{body}"
        f"{crop}"
        f"</svg>"
    )


def render_schema_brochure(
    template: TemplateSchema,
    content: BrochureContent,
    *,
    images: dict[str, bytes] | None = None,
    textures: dict[str, bytes] | None = None,
) -> tuple[str, str]:
    """Render a template + content pair to (outside_svg, inside_svg).

    When `images` is supplied, each `image_placeholder` whose `slot` matches a
    key has the PNG bytes embedded as a base64 data URL with the appropriate
    clip path (rounded / circle / none). Slots missing from the dict fall back
    to the placeholder's `fallback_fill`.

    When `textures` is supplied, any `texture_slot` fill whose slot name matches
    a key is rendered as a tiled `<pattern>` referencing the image bytes; slots
    missing from the dict fall back to the `texture_slot.fallback` fill.
    """
    layout = compute_panel_layout()

    outside_panels = []
    for panel_rect in layout.outside_panels:
        pname = panel_rect.name  # type: ignore[attr-defined]
        schema_panel = template.panels.get(pname)
        if schema_panel is None:
            continue
        outside_panels.append((panel_rect, schema_panel))

    inside_panels = []
    for panel_rect in layout.inside_panels:
        pname = panel_rect.name  # type: ignore[attr-defined]
        schema_panel = template.panels.get(pname)
        if schema_panel is None:
            continue
        inside_panels.append((panel_rect, schema_panel))

    outside_svg = _render_sheet(
        outside_panels, layout, template, content, "outside", images, textures
    )
    inside_svg = _render_sheet(
        inside_panels, layout, template, content, "inside", images, textures
    )
    return outside_svg, inside_svg
