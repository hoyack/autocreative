"""Social post renderer -- PostTemplate + copy + BrandKit -> PNG bytes.

Thin wrapper: reuses brochure schema_renderer SVG primitives + CairoSVG
rasterization. Per 19-PATTERNS.md line 370: "build a one-panel PostTemplate,
call the schema renderer, rasterize via CairoSVG, apply the Pillow crop."
Here we emit the SVG inline (1 panel is simpler than the brochure's 6-panel
loop).

Public surface:
  - ``render_post(template, copy, brand_kit, *, hero_image_bytes=None) -> bytes``
  - ``_apply_brand_kit_to_post_template(template, kit) -> PostTemplate``

Safety guardrails (STRIDE mitigations, 19-06 threat model):
  - T-19-06-01: every user-supplied content string is XML-escaped before it
    lands in an SVG ``<text>`` node.
  - T-19-06-02: ``w * h > 50_000_000`` raises ``SocialError`` before CairoSVG
    allocates any pixels.
"""

from __future__ import annotations

import base64
from xml.sax.saxutils import escape as xml_escape

import structlog

from flyer_generator.brand_kit.models import BrandKit
from flyer_generator.brochure.schema_renderer.schema_model import (
    Palette,
    Typography,
)
from flyer_generator.errors import SocialError
from flyer_generator.social.models import PostCopy
from flyer_generator.social.schemas.schema_model import PostTemplate

# Per 19-PATTERNS.md §PNG safety cap (50 MP). Matches brand_kit/audit.py and
# social/crop.py so every image entry point enforces the same cap.
_MAX_IMAGE_MP = 50_000_000

# Brochure Typography has several integer *_size fields. When a brand kit
# carries a size_multiplier we scale each of them; the TextSlot's own
# ``font_size`` is scaled separately because PostTemplate carries per-slot
# sizes (Typography acts as a default).
_TYPOGRAPHY_SIZE_FIELDS: tuple[str, ...] = (
    "cover_title_size",
    "cover_subtitle_size",
    "heading_size",
    "body_size",
    "body_line_height",
    "bullet_size",
    "bullet_line_height",
)

_logger = structlog.get_logger(__name__)


# --------------------------------------------------------------------------- #
# Brand-kit application
# --------------------------------------------------------------------------- #


def _normalize_font_stack(stack: str) -> str:
    """Mirror :func:`flyer_generator.brand_kit.applier._normalize_font_stack`.

    CSS font stacks commonly ship as ``"Open Sans", sans-serif``; inside a
    double-quoted SVG ``font-family="..."`` attribute those embedded double
    quotes break the XML. Single quotes are equivalent for CSS/SVG font
    family values.
    """
    return stack.replace('"', "'")


def _apply_brand_kit_to_post_template(
    template: PostTemplate, kit: BrandKit | None
) -> PostTemplate:
    """Return a new ``PostTemplate`` with palette + typography swapped from ``kit``.

    Never mutates the input template -- uses ``model_copy(update={...})`` per
    the 19-PATTERNS.md "Immutable model transform" guidance (mirrors
    ``flyer_generator.brand_kit.applier.apply_brand_kit`` semantics).

    Args:
        template: PostTemplate whose ``palette`` and ``typography`` may be
            ``None`` (Plan 05 templates ship them as null so the brand kit
            drives color + typography at render time).
        kit: BrandKit to apply. If ``None``, the function requires that the
            template already carries non-null palette + typography, otherwise
            it raises :class:`SocialError`.

    Returns:
        A new PostTemplate with:
          * ``palette``: derived from ``kit.palette`` (primary->accent_default,
            neutral_dark/light carried verbatim, secondary->muted).
          * ``typography``: derived from ``kit.typography`` with font stacks
            normalized for SVG attribute embedding; size fields scaled by
            ``kit.size_multiplier``.
          * ``text_slots``: each ``font_size`` scaled by
            ``kit.size_multiplier``.

    Raises:
        SocialError: ``kit is None`` while the template carries no
            palette/typography (Plan 05 shipped state).
    """
    if kit is None:
        if template.palette is None or template.typography is None:
            raise SocialError(
                "brand_kit is required because template has null palette or typography",
                template_name=template.name,
            )
        return template

    # --- Palette ---------------------------------------------------------- #
    # Fall-through hierarchy:
    #   1. kit.palette present  -> build Palette from kit (brand-kit wins).
    #   2. kit.palette missing  -> keep template.palette if non-null.
    #   3. both missing         -> minimal safe Palette so _build_svg can run.
    if kit.palette is not None:
        new_palette_obj = Palette(
            accent_default=kit.palette.primary.hex,
            neutral_dark=kit.palette.neutral_dark.hex,
            neutral_light=kit.palette.neutral_light.hex,
            muted=kit.palette.secondary.hex,
            extras={k: v.hex for k, v in kit.palette.extras.items()},
        )
    elif template.palette is not None:
        new_palette_obj = template.palette
    else:
        new_palette_obj = Palette(accent_default="#1E3A5F")

    # --- Typography ------------------------------------------------------- #
    base_typography = template.typography or Typography()
    typ_updates: dict[str, object] = {}

    if kit.typography is not None:
        if kit.typography.heading_family:
            typ_updates["heading_family"] = _normalize_font_stack(
                kit.typography.heading_family
            )
        if kit.typography.body_family:
            typ_updates["body_family"] = _normalize_font_stack(
                kit.typography.body_family
            )

    multiplier = kit.size_multiplier if kit.size_multiplier else 1.0
    if abs(multiplier - 1.0) > 1e-9:
        for field in _TYPOGRAPHY_SIZE_FIELDS:
            orig = getattr(base_typography, field)
            typ_updates[field] = max(1, round(orig * multiplier))

    new_typography = (
        base_typography.model_copy(update=typ_updates)
        if typ_updates
        else base_typography
    )

    # --- Text slots: scale font_size by multiplier ------------------------ #
    if abs(multiplier - 1.0) > 1e-9:
        new_text_slots = [
            ts.model_copy(
                update={"font_size": max(1, int(round(ts.font_size * multiplier)))}
            )
            for ts in template.text_slots
        ]
    else:
        new_text_slots = list(template.text_slots)

    return template.model_copy(
        update={
            "palette": new_palette_obj,
            "typography": new_typography,
            "text_slots": new_text_slots,
        }
    )


# --------------------------------------------------------------------------- #
# SVG composition
# --------------------------------------------------------------------------- #


def _resolve_palette_color(role: str, palette: Palette) -> str:
    """Map a ``color_role`` on a TextSlot to a hex string from the palette."""
    mapping = {
        "primary": palette.accent_default,
        "accent": palette.accent_default,
        "neutral_dark": palette.neutral_dark,
        "neutral_light": palette.neutral_light,
    }
    return mapping.get(role, palette.neutral_dark)


def _resolve_font_family(role: str, typography: Typography) -> str:
    return typography.heading_family if role == "heading" else typography.body_family


def _fit_font_size(
    text: str,
    max_width: float,
    base_font_size: int,
    *,
    min_ratio: float = 0.65,
    avg_char_width_coefficient: float = 0.55,
) -> int:
    """Shrink font_size so ``text`` fits inside ``max_width`` at the rendered scale.

    Heuristic: estimates pixel width as ``len(text) * font_size *
    avg_char_width_coefficient`` (0.55 is a standard sans-serif average
    advance). If the estimate overshoots ``max_width``, scales the font down
    proportionally with a 5% safety margin. Never shrinks below
    ``base_font_size * min_ratio`` (legibility floor).

    Args:
        text: Rendered title/cta string (post xml_escape / uppercase).
        max_width: Slot bbox width in SVG units.
        base_font_size: Template-declared font_size.
        min_ratio: Minimum allowed ratio of the base size.
        avg_char_width_coefficient: Width/size ratio for the expected font.

    Returns:
        Integer font_size to render. Always <= base_font_size.
    """
    if not text or max_width <= 0 or base_font_size <= 0:
        return base_font_size
    estimated_width = len(text) * base_font_size * avg_char_width_coefficient
    if estimated_width <= max_width:
        return base_font_size
    scale = (max_width / estimated_width) * 0.95
    floor = base_font_size * min_ratio
    new_size = max(floor, base_font_size * scale)
    return int(round(new_size))


def _get_content_value(copy: PostCopy, content_key: str) -> str:
    """Resolve ``"copy.title"`` -> ``copy.title``, etc.

    Unknown keys return the empty string; they are dropped silently from the
    rendered SVG so a template author adding a future ``copy.promo_price``
    content_key doesn't crash older renderers.
    """
    parts = content_key.split(".", 1)
    if parts[0] != "copy" or len(parts) != 2:
        return ""
    field = parts[1]
    if field == "title":
        return copy.title or ""
    if field == "body":
        return copy.body
    if field == "cta":
        return copy.cta or ""
    if field == "hashtags":
        return " ".join(copy.hashtags)
    return ""


def _build_svg(
    template: PostTemplate,
    copy: PostCopy,
    hero_image_bytes: bytes | None,
) -> str:
    """Compose the SVG markup. Assumes ``template.palette`` and
    ``template.typography`` are non-``None`` (i.e. ``_apply_brand_kit_to_post_template``
    has run).
    """
    assert template.palette is not None
    assert template.typography is not None
    canvas = template.canvas
    palette = template.palette
    typography = template.typography

    bg_hex = palette.neutral_light

    parts: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{canvas.width}" height="{canvas.height}" '
            f'viewBox="0 0 {canvas.width} {canvas.height}">'
        ),
        f'<rect x="0" y="0" width="{canvas.width}" height="{canvas.height}" fill="{bg_hex}"/>',
    ]

    # Hero image slot. Drawn before shapes so an overlay rect can darken it.
    if template.image_slot is not None and hero_image_bytes is not None:
        x, y, w, h = template.image_slot.bbox
        b64 = base64.b64encode(hero_image_bytes).decode("ascii")
        parts.append(
            f'<image x="{x}" y="{y}" width="{w}" height="{h}" '
            f'preserveAspectRatio="xMidYMid slice" '
            f'xlink:href="data:image/png;base64,{b64}"/>'
        )

    # Shapes (sorted by z). v1 supports only rect shapes: Plan 05's 12 shipped
    # templates use rect exclusively. Non-rect shapes are logged and skipped
    # so a template author accidentally using an unsupported kind does not
    # crash the render. A future plan can widen this by importing the
    # dispatch entry point `render_shape` and passing a canvas_rect.
    from flyer_generator.brochure.schema_renderer.shapes import (  # noqa: PLC0415
        render_rect,
    )

    salt_counter = 0
    for shape in sorted(template.shapes, key=lambda s: getattr(s, "z", 0)):
        kind = getattr(shape, "kind", None)
        if kind != "rect":
            _logger.warning(
                "social_renderer_shape_kind_unsupported_in_v1",
                kind=kind,
                template=template.name,
            )
            continue
        salt_counter += 1
        # render_rect(el, salt, textures=None) -- textures unused in post templates v1.
        parts.append(render_rect(shape, f"post-{salt_counter}"))

    # Text slots. Every copy value passes through xml_escape (T-19-06-01).
    for ts in template.text_slots:
        text = _get_content_value(copy, ts.content_key)
        if not text:
            continue
        if ts.uppercase:
            text = text.upper()
        safe = xml_escape(text)
        color = _resolve_palette_color(ts.color_role, palette)
        family = _resolve_font_family(ts.font_role, typography)

        # Auto-shrink: the Ernie/Qwen backdrop + overlay band often ships a
        # bbox narrower than the declared font_size permits for the chosen
        # title length. Estimate rendered pixel width using a sans-serif
        # average-advance heuristic (0.55 * font_size per char); if it
        # overshoots bbox width, scale font_size down — never below 65% of
        # the declared size (legibility floor).
        effective_font_size = _fit_font_size(
            text, ts.bbox[2], ts.font_size, min_ratio=0.65
        )

        # Anchor x based on align; y is bbox-top + font_size for baseline.
        if ts.align == "center":
            x_pos: float = ts.bbox[0] + ts.bbox[2] / 2
        elif ts.align == "right":
            x_pos = ts.bbox[0] + ts.bbox[2]
        else:
            x_pos = ts.bbox[0]
        y_pos = ts.bbox[1] + effective_font_size

        anchor_map = {"left": "start", "center": "middle", "right": "end"}
        anchor = anchor_map[ts.align]

        weight_map = {
            "normal": "400",
            "medium": "500",
            "semibold": "600",
            "bold": "700",
        }
        weight = weight_map.get(ts.font_weight, "400")
        parts.append(
            f'<text x="{x_pos}" y="{y_pos}" fill="{color}" '
            f'font-family="{family}" font-size="{effective_font_size}" '
            f'font-weight="{weight}" text-anchor="{anchor}">{safe}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Rasterization
# --------------------------------------------------------------------------- #


def _rasterize_svg(svg: str, width: int, height: int) -> bytes:
    """Rasterize SVG markup to PNG bytes via CairoSVG (primary) or resvg_py (fallback).

    ``resvg_py`` is optional; when unavailable we rely exclusively on
    ``cairosvg``. If both are missing we surface the CairoSVG ImportError so
    the caller sees the primary dependency as the root cause.
    """
    try:
        import cairosvg  # noqa: PLC0415

        result = cairosvg.svg2png(
            bytestring=svg.encode("utf-8"),
            output_width=width,
            output_height=height,
        )
        if isinstance(result, (bytes, bytearray)):
            return bytes(result)
        # cairosvg returns None when write_to is supplied; we don't use that
        # code path here, but guard against an unexpected return value.
        raise SocialError("cairosvg.svg2png returned non-bytes result")
    except ImportError:
        try:
            import resvg_py  # noqa: PLC0415
        except ImportError:
            raise  # re-raise the original CairoSVG ImportError
        return resvg_py.svg_to_bytes(  # type: ignore[no-any-return]
            svg_string=svg,
            width=width,
            height=height,
        )


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def render_post(
    template: PostTemplate,
    copy: PostCopy,
    brand_kit: BrandKit | None = None,
    *,
    hero_image_bytes: bytes | None = None,
) -> bytes:
    """Render a PostTemplate + copy + brand_kit to PNG bytes.

    Args:
        template: PostTemplate describing canvas, image_slot, shapes, and
            text_slots.
        copy: PostCopy with title/body/cta/hashtags. User-supplied strings
            are XML-escaped before embedding in the SVG.
        brand_kit: Optional BrandKit. Required when ``template.palette`` is
            ``None`` (the shipped state of every template in Plan 05).
        hero_image_bytes: Optional PNG/JPEG bytes embedded at
            ``template.image_slot.bbox`` via a base64 data URI. Ignored when
            ``template.image_slot`` is ``None``.

    Returns:
        PNG bytes at ``(template.canvas.width, template.canvas.height)``.

    Raises:
        SocialError: canvas exceeds the 50 MP cap (T-19-06-02); or the
            template has a null palette/typography and no brand_kit is
            supplied.
    """
    w, h = template.canvas.width, template.canvas.height
    if w * h > _MAX_IMAGE_MP:
        raise SocialError(
            "canvas exceeds 50 MP cap",
            width=w,
            height=h,
            template=template.name,
        )

    kit_applied = _apply_brand_kit_to_post_template(template, brand_kit)
    svg = _build_svg(kit_applied, copy, hero_image_bytes)
    return _rasterize_svg(svg, w, h)
