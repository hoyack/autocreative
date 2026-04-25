"""Schema -> SVG renderer for postcards.

Walks a PostcardTemplateSchema + PostcardContent pair and emits two SVG
strings (front_svg, back_svg). Each SVG is sized to the template canvas
(e.g. 1200x1800 portrait, 1800x1200 landscape) and is rasterized
independently by the standard ``Rasterizer``. Page 1 of the print PDF ==
front, page 2 == back; addresses go in the back panel.

Reuses shape primitives (render_shape, render_fill) and text-fit helpers
from the brochure schema_renderer because those are pure utility
functions free of brochure-specific layout concerns. The element-level
text / bullets / divider / image_placeholder / logo_placeholder helpers
are copied (with minimal adaptation for the simpler postcard topology)
to keep the postcard package self-contained at the rendering boundary.

Postcard topology vs. brochure
-------------------------------
A postcard is a 2-sided card with no panel layout, no fold lines, and no
bleed math. Each panel ("front" / "back") IS the entire canvas, so the
renderer skips the brochure's ``compute_panel_layout`` + per-panel
``<g transform="translate(...)">`` wrapping and emits one SVG per panel
with a (0, 0) -> (W, H) coordinate system.

Trust boundary: every interpolated user string passes through
``xml_escape`` before insertion into ``<text>`` content. Threat T-23-09
(SVG injection via headline / body / address_block) is mitigated here.
"""

from __future__ import annotations

from xml.sax.saxutils import escape as xml_escape

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
from flyer_generator.postcard.schema_renderer.content_model import PostcardContent
from flyer_generator.postcard.schema_renderer.schema_model import (
    BulletsElement,
    DividerElement,
    ImagePlaceholder,
    LogoPlaceholder,
    PanelSchema,
    PostcardTemplateSchema,
    ShapeElement,
    TextElement,
)

# --------------------------------------------------------------------------- #
# Role -> typography-field maps (verbatim from brochure renderer; postcard
# Typography has the same field set so the maps are reusable as-is).
# --------------------------------------------------------------------------- #

_ROLE_FONT_SIZE: dict[str, str] = {
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

_ROLE_LINE_HEIGHT: dict[str, float] = {
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


# --------------------------------------------------------------------------- #
# Element-level helpers (text, bullets, divider, image, logo)
# --------------------------------------------------------------------------- #


def _resolve_font(
    el: TextElement | BulletsElement,
    schema: PostcardTemplateSchema,
) -> tuple[str, int, int]:
    """Return ``(font_family, font_size, line_height)`` for a text-like element.

    Mirrors the brochure renderer's resolution order: explicit element
    override > role-default > Typography fallback.
    """
    # Font family
    if getattr(el, "font_family", None):
        family = el.font_family  # type: ignore[assignment]
    elif (
        hasattr(el, "role")
        and el.role
        in ("cover_title", "section_heading", "cta_heading", "org_name", "quote")
    ):
        family = schema.typography.heading_family
    else:
        family = schema.typography.body_family

    # Size
    if getattr(el, "font_size", None):
        size = el.font_size  # type: ignore[assignment]
    elif hasattr(el, "role"):
        size = getattr(
            schema.typography, _ROLE_FONT_SIZE.get(el.role, "body_size")
        )
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


def _resolve_text_content(el: TextElement, content: PostcardContent) -> str:
    """Resolve the runtime text for a TextElement.

    ``role == "static"`` or absent ``content_key`` -> ``static_text`` (or "").
    Otherwise look up ``content.resolve_key`` and stringify the result.
    """
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
    content: PostcardContent,
    schema: PostcardTemplateSchema,
) -> str:
    """Render a TextElement to an SVG ``<text>`` tag with one ``<tspan>`` per line.

    All interpolated user strings are XML-escaped via ``xml_escape``.
    """
    text = _resolve_text_content(el, content)
    if not text:
        return ""
    if el.uppercase:
        text = text.upper()
    if el.max_chars and len(text) > el.max_chars:
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
    weight = {
        "normal": "400",
        "medium": "500",
        "semibold": "600",
        "bold": "700",
    }[el.weight]
    font_style = "italic" if el.italic else "normal"

    # Horizontal alignment
    anchor = {
        "left": "start",
        "center": "middle",
        "right": "end",
        "justify": "start",
    }[el.align]
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
    else:  # bottom
        y_start = y + h - (len(fitted.lines) - 1) * lh

    tspans: list[str] = []
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
    content: PostcardContent,
    schema: PostcardTemplateSchema,
) -> str:
    """Render a BulletsElement. Postcard schema currently has no bulleted
    content keys, but the helper is kept available so future templates can
    emit bullets without a renderer change.
    """
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

    cursor_y = y + size
    parts: list[str] = []
    for idx, item in enumerate(items):
        lines = wrap_text(item, cpl)
        if not lines:
            continue
        marker_cy = cursor_y - size * 0.3
        if el.bullet_style == "disc":
            marker = (
                f'<circle cx="{x + size * 0.35}" cy="{marker_cy}" '
                f'r="{size * 0.18}" fill="{bullet_color}"/>'
            )
        elif el.bullet_style == "square":
            marker = (
                f'<rect x="{x + size * 0.1}" y="{marker_cy - size * 0.2}" '
                f'width="{size * 0.4}" height="{size * 0.4}" '
                f'fill="{bullet_color}"/>'
            )
        elif el.bullet_style == "accent_block":
            marker = (
                f'<rect x="{x}" y="{cursor_y - size * 0.9}" '
                f'width="{size * 0.12}" '
                f'height="{lh * len(lines) - 6}" '
                f'fill="{bullet_color}"/>'
            )
        elif el.bullet_style == "numbered":
            marker = (
                f'<text x="{x}" y="{cursor_y}" font-family="{family}" '
                f'font-size="{size}" fill="{bullet_color}" '
                f'font-weight="600">{idx + 1}.</text>'
            )
        else:  # dash
            marker = (
                f'<line x1="{x + size * 0.1}" y1="{marker_cy}" '
                f'x2="{x + size * 0.7}" y2="{marker_cy}" '
                f'stroke="{bullet_color}" stroke-width="{size * 0.12}"/>'
            )
        parts.append(marker)
        for i, line in enumerate(lines):
            safe = xml_escape(line)
            parts.append(
                f'<text x="{x + indent}" y="{cursor_y + i * lh}" '
                f'font-family="{family}" font-size="{size}" '
                f'fill="{text_color}">{safe}</text>'
            )
        cursor_y += lh * len(lines) + el.item_spacing
        if cursor_y > y + h:
            break
    return "".join(parts)


def _render_image_placeholder(
    el: ImagePlaceholder,
    content: PostcardContent,
    schema: PostcardTemplateSchema,
    salt: str,
) -> str:
    """Render an image_placeholder using its ``fallback_fill`` (or the
    default accent->neutral_light gradient) plus an optional placeholder
    label. The postcard renderer in this plan does NOT accept actual image
    bytes — slot content embedding is a worker concern (Phase 23-04).
    """
    del content  # placeholder-only path; content not needed for fallback
    x, y, w, h = el.bbox

    if el.fallback_fill is None:
        from flyer_generator.postcard.schema_renderer.schema_model import (
            GradientStop,
            LinearGradientFill,
        )

        fallback = LinearGradientFill(
            stops=[
                GradientStop(
                    offset=0.0,
                    color=schema.palette.accent_default,
                    opacity=0.22,
                ),
                GradientStop(
                    offset=1.0,
                    color=schema.palette.neutral_light,
                    opacity=0.9,
                ),
            ],
            angle=135,
        )
    else:
        fallback = el.fallback_fill

    defs, fill_val = render_fill(fallback, f"img-{el.slot}-{salt}", None)
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
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
            f'rx="{rx}" ry="{rx}" '
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
            f'text-anchor="middle" '
            f'font-family="{schema.typography.body_family}" '
            f'font-size="{size}" fill="{schema.palette.neutral_dark}" '
            f'opacity="0.55">{xml_escape(label_text)}</text>'
        )

    return defs + body + label


def _render_logo_placeholder(
    el: LogoPlaceholder,
    content: PostcardContent,
    schema: PostcardTemplateSchema,
    salt: str,
) -> str:
    """Render a monogram fallback for a LogoPlaceholder.

    The postcard renderer does not consume real logo bytes (no logo argument
    on render_postcard); the worker layer can compose a logo on top of the
    rasterized PNG if needed in a future phase. PostcardContent has no
    ``org`` field, so the monogram falls back to a single bullet glyph "•".
    """
    del content, salt
    x, y, w, h = el.bbox
    bg_color = el.fallback_color or schema.palette.accent_default
    initials = "•"

    cx = x + w / 2
    cy = y + h / 2
    radius = min(w, h) / 2

    if el.fallback_style == "monogram_square":
        shape = (
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
            f'rx="{w * 0.1}" ry="{w * 0.1}" '
            f'fill="{bg_color}"/>'
        )
    elif el.fallback_style == "initials_plain":
        shape = ""
    else:  # monogram_circle
        shape = (
            f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="{bg_color}"/>'
        )

    letter_color = (
        schema.palette.neutral_light
        if el.fallback_style != "initials_plain"
        else schema.palette.accent_default
    )
    letter_size = int(min(w, h) * 0.5)
    letter_family = schema.typography.heading_family
    baseline_shift = letter_size * 0.35
    text = (
        f'<text x="{cx}" y="{cy + baseline_shift}" text-anchor="middle" '
        f'font-family="{letter_family}" font-size="{letter_size}" '
        f'font-weight="700" fill="{letter_color}">'
        f"{xml_escape(initials)}</text>"
    )
    return shape + text


def _render_divider(el: DividerElement) -> str:
    """Render a DividerElement as an SVG ``<line>``."""
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
# Per-panel canvas + top-level render_postcard
# --------------------------------------------------------------------------- #


def _render_canvas(
    name: str,
    panel: PanelSchema,
    template: PostcardTemplateSchema,
    content: PostcardContent,
) -> str:
    """Render a single panel ("front" or "back") to a complete SVG document.

    The panel IS the canvas — coordinates are absolute (no
    ``<g transform="translate(...)">`` wrapper, no bleed math).
    """
    W = template.canvas.width
    H = template.canvas.height

    parts: list[str] = []

    # Optional full-canvas background fill
    if panel.background is not None:
        defs, fill_val = render_fill(panel.background, f"bg-{name}", None)
        opacity = _fill_opacity(panel.background)
        parts.append(defs)
        parts.append(
            f'<rect x="0" y="0" width="{W}" height="{H}" '
            f'fill="{fill_val}" fill-opacity="{opacity:.4f}"/>'
        )

    # Sort elements by z (lowest first -> bottom)
    elements = sorted(panel.elements, key=lambda e: getattr(e, "z", 0))

    salt_counter = 0
    for el in elements:
        salt = f"{name}-{salt_counter}"
        salt_counter += 1
        if isinstance(el, ShapeElement):
            parts.append(render_shape(el, (0, 0, W, H), salt, None))
        elif isinstance(el, TextElement):
            parts.append(_render_text_element(el, content, template))
        elif isinstance(el, BulletsElement):
            parts.append(_render_bullets_element(el, content, template))
        elif isinstance(el, ImagePlaceholder):
            parts.append(_render_image_placeholder(el, content, template, salt))
        elif isinstance(el, LogoPlaceholder):
            parts.append(_render_logo_placeholder(el, content, template, salt))
        elif isinstance(el, DividerElement):
            parts.append(_render_divider(el))

    body = "".join(parts)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
        f'<rect width="{W}" height="{H}" fill="white"/>'
        f"{body}"
        "</svg>"
    )


def render_postcard(
    template: PostcardTemplateSchema,
    content: PostcardContent,
) -> tuple[str, str]:
    """Render ``(front_svg, back_svg)`` from a template + content pair.

    No bleed math, no fold lines: a postcard's front IS the full canvas
    and the back IS the full canvas. Page 1 of the print PDF is the front,
    page 2 is the back. The shape primitives (``render_shape``,
    ``render_fill``) and text-fit helpers are imported from the brochure
    schema_renderer because they are pure utility functions free of any
    brochure-specific coordinate math.

    Parameters
    ----------
    template:
        A loaded ``PostcardTemplateSchema`` (e.g. from ``load_template``).
        Must declare both "front" and "back" panels (validated at template
        load time by ``PostcardTemplateSchema._validate_panels_complete``).
    content:
        The runtime content payload. ``address_block`` may be None — in
        that case any address-block TextElements in the back panel render
        as empty text rather than raising.

    Returns
    -------
    tuple[str, str]
        ``(front_svg, back_svg)`` — two complete SVG documents, each sized
        to ``template.canvas.width`` x ``template.canvas.height``.
    """
    front_panel = template.panels["front"]
    back_panel = template.panels["back"]

    front_svg = _render_canvas("front", front_panel, template, content)
    back_svg = _render_canvas("back", back_panel, template, content)
    return front_svg, back_svg
