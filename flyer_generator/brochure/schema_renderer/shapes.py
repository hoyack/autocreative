"""Shape primitive → SVG renderer.

Each function accepts a ShapeElement (pydantic model) plus a panel bounding
box and emits a string of SVG markup. Gradients are emitted as <defs> with
unique ids so the caller can accumulate them separately from shape bodies
if desired, but for simplicity we inline defs + shape in one string.
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flyer_generator.brochure.schema_renderer.schema_model import (
        Fill,
        ShapeElement,
        Stroke,
    )

# Default tile size for texture_slot fills (Phase 4 stretch). A texture image
# is wrapped in a <pattern> and repeats every TEXTURE_TILE_PX pixels across the
# shape fill. Larger = fewer visible seams for "atmospheric" textures; smaller
# = more visible repeat for "grain / weave" textures.
TEXTURE_TILE_PX = 512


# --------------------------------------------------------------------------- #
# Gradient / fill helpers
# --------------------------------------------------------------------------- #


def _gradient_id(kind: str, salt: str) -> str:
    """Produce a stable-ish id that won't collide across panels."""
    return f"grad-{kind}-{salt}"


def _linear_gradient_defs(grad_id: str, stops, angle: float) -> str:
    """Emit a <linearGradient> under <defs>.

    angle 0 = top→bottom, 90 = left→right (clockwise).
    """
    # Convert angle to x1,y1,x2,y2 in object-bounding-box space.
    import math

    # angle=0 → (0,0)-(0,1) ; angle=90 → (0,0)-(1,0)
    rad = math.radians(angle)
    cx, cy = 0.5, 0.5
    dx = math.sin(rad) / 2
    dy = -math.cos(rad) / 2
    x1, y1 = cx - dx, cy - dy
    x2, y2 = cx + dx, cy + dy
    stop_xml = "".join(
        f'<stop offset="{s.offset * 100:.2f}%" stop-color="{s.color}" stop-opacity="{s.opacity:.4f}"/>'
        for s in stops
    )
    return (
        f'<linearGradient id="{grad_id}" '
        f'x1="{x1:.4f}" y1="{y1:.4f}" x2="{x2:.4f}" y2="{y2:.4f}">'
        f"{stop_xml}</linearGradient>"
    )


def _radial_gradient_defs(grad_id: str, stops, center, radius: float) -> str:
    cx, cy = center
    stop_xml = "".join(
        f'<stop offset="{s.offset * 100:.2f}%" stop-color="{s.color}" stop-opacity="{s.opacity:.4f}"/>'
        for s in stops
    )
    return (
        f'<radialGradient id="{grad_id}" '
        f'cx="{cx:.4f}" cy="{cy:.4f}" r="{radius:.4f}" fx="{cx:.4f}" fy="{cy:.4f}">'
        f"{stop_xml}</radialGradient>"
    )


def _texture_pattern_defs(pattern_id: str, image_bytes: bytes) -> str:
    """Emit a <pattern> that tiles `image_bytes` at TEXTURE_TILE_PX over a shape fill."""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    href = f"data:image/png;base64,{b64}"
    return (
        f'<defs><pattern id="{pattern_id}" patternUnits="userSpaceOnUse" '
        f'width="{TEXTURE_TILE_PX}" height="{TEXTURE_TILE_PX}">'
        f'<image href="{href}" x="0" y="0" '
        f'width="{TEXTURE_TILE_PX}" height="{TEXTURE_TILE_PX}" '
        f'preserveAspectRatio="xMidYMid slice"/></pattern></defs>'
    )


def render_fill(
    fill: "Fill | None",
    salt: str,
    textures: dict[str, bytes] | None = None,
) -> tuple[str, str]:
    """Return (defs_fragment, fill_attr_value).

    Examples:
        ('', '#F7F7F5')                   # solid
        ('<defs>…</defs>', 'url(#grad-…)')  # gradient
        ('<defs>…</defs>', 'url(#tex-…)')   # texture_slot (tiled pattern)

    When `textures` contains a key matching a `texture_slot` fill's slot, the
    fill resolves to a tiled <pattern> referencing that image. Otherwise the
    texture_slot falls through to its `fallback` field.
    """
    if fill is None:
        return "", "none"

    kind = fill.type
    if kind == "solid":
        # Embed opacity into a separate attr; caller applies via element attr.
        return "", fill.color  # type: ignore[union-attr]

    if kind == "linear_gradient":
        gid = _gradient_id("lin", salt)
        defs = f"<defs>{_linear_gradient_defs(gid, fill.stops, fill.angle)}</defs>"  # type: ignore[union-attr]
        return defs, f"url(#{gid})"

    if kind == "radial_gradient":
        gid = _gradient_id("rad", salt)
        defs = f"<defs>{_radial_gradient_defs(gid, fill.stops, fill.center, fill.radius)}</defs>"  # type: ignore[union-attr]
        return defs, f"url(#{gid})"

    if kind == "texture_slot":
        slot = fill.slot  # type: ignore[union-attr]
        if textures is not None and slot in textures:
            pid = f"tex-{slot}-{salt}"
            return _texture_pattern_defs(pid, textures[slot]), f"url(#{pid})"
        # Fall through to fallback fill
        return render_fill(fill.fallback, salt, textures)  # type: ignore[union-attr]

    return "", "none"


def _fill_opacity(fill: "Fill | None") -> float:
    if fill is None:
        return 1.0
    if fill.type == "solid":
        return fill.opacity  # type: ignore[union-attr]
    return 1.0  # gradient stops carry their own opacity


def _stroke_attrs(stroke: "Stroke | None") -> str:
    if stroke is None:
        return 'stroke="none"'
    parts = [
        f'stroke="{stroke.color}"',
        f'stroke-width="{stroke.width}"',
        f'stroke-opacity="{stroke.opacity:.4f}"',
    ]
    if stroke.dash:
        parts.append(f'stroke-dasharray="{" ".join(str(d) for d in stroke.dash)}"')
    return " ".join(parts)


# --------------------------------------------------------------------------- #
# Bleed adjustment
# --------------------------------------------------------------------------- #


def apply_bleed(
    rect: tuple[float, float, float, float],
    bleed,
    canvas_rect: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    """Extend a shape's rect to the nearest canvas edge per `bleed` policy.

    Templates specify shape rects in canvas-absolute coords; bleed extends the
    rect outward by enough to reach the canvas edge on the requested sides.
    """
    if not bleed:
        return rect

    x, y, w, h = rect
    cx, cy, cw, ch = canvas_rect

    def ext_left():
        nonlocal x, w
        w = w + (x - cx)
        x = cx

    def ext_top():
        nonlocal y, h
        h = h + (y - cy)
        y = cy

    def ext_right():
        nonlocal w
        w = (cx + cw) - x

    def ext_bottom():
        nonlocal h
        h = (cy + ch) - y

    if bleed is True or bleed == "all":
        ext_left()
        ext_top()
        ext_right()
        ext_bottom()
    elif bleed == "left":
        ext_left()
    elif bleed == "right":
        ext_right()
    elif bleed == "top":
        ext_top()
    elif bleed == "bottom":
        ext_bottom()
    return (x, y, w, h)


# --------------------------------------------------------------------------- #
# Shape renderers
# --------------------------------------------------------------------------- #


def _rotate_attr(rotation: float, cx: float, cy: float) -> str:
    if rotation == 0:
        return ""
    return f' transform="rotate({rotation} {cx} {cy})"'


def render_rect(el: "ShapeElement", salt: str, textures: dict[str, bytes] | None = None) -> str:
    assert el.rect is not None, "rect kind requires `rect`"
    x, y, w, h = el.rect
    defs, fill_val = render_fill(el.fill, salt, textures)
    fop = _fill_opacity(el.fill)
    stroke = _stroke_attrs(el.stroke)
    rot = _rotate_attr(el.rotation, x + w / 2, y + h / 2)
    body = (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
        f'fill="{fill_val}" fill-opacity="{fop:.4f}" opacity="{el.opacity:.4f}" '
        f"{stroke}{rot}/>"
    )
    return defs + body


def render_rounded_rect(el: "ShapeElement", salt: str, textures: dict[str, bytes] | None = None) -> str:
    assert el.rect is not None, "rounded_rect kind requires `rect`"
    x, y, w, h = el.rect
    corner = float(el.path_params.get("corner_radius", 24.0))
    defs, fill_val = render_fill(el.fill, salt, textures)
    fop = _fill_opacity(el.fill)
    stroke = _stroke_attrs(el.stroke)
    rot = _rotate_attr(el.rotation, x + w / 2, y + h / 2)
    body = (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{corner}" ry="{corner}" '
        f'fill="{fill_val}" fill-opacity="{fop:.4f}" opacity="{el.opacity:.4f}" '
        f"{stroke}{rot}/>"
    )
    return defs + body


def render_circle(el: "ShapeElement", salt: str, textures: dict[str, bytes] | None = None) -> str:
    assert el.rect is not None, "circle kind requires `rect`"
    x, y, w, h = el.rect
    # Use the smallest of w/h as diameter; center inside rect.
    diameter = min(w, h)
    cx = x + w / 2
    cy = y + h / 2
    r = diameter / 2
    defs, fill_val = render_fill(el.fill, salt, textures)
    fop = _fill_opacity(el.fill)
    stroke = _stroke_attrs(el.stroke)
    body = (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" '
        f'fill="{fill_val}" fill-opacity="{fop:.4f}" opacity="{el.opacity:.4f}" '
        f"{stroke}/>"
    )
    return defs + body


def render_ellipse(el: "ShapeElement", salt: str, textures: dict[str, bytes] | None = None) -> str:
    assert el.rect is not None, "ellipse kind requires `rect`"
    x, y, w, h = el.rect
    cx = x + w / 2
    cy = y + h / 2
    defs, fill_val = render_fill(el.fill, salt, textures)
    fop = _fill_opacity(el.fill)
    stroke = _stroke_attrs(el.stroke)
    rot = _rotate_attr(el.rotation, cx, cy)
    body = (
        f'<ellipse cx="{cx}" cy="{cy}" rx="{w / 2}" ry="{h / 2}" '
        f'fill="{fill_val}" fill-opacity="{fop:.4f}" opacity="{el.opacity:.4f}" '
        f"{stroke}{rot}/>"
    )
    return defs + body


def render_polygon(el: "ShapeElement", salt: str, textures: dict[str, bytes] | None = None) -> str:
    assert el.points is not None and len(el.points) >= 3, "polygon requires >=3 points"
    points_str = " ".join(f"{x},{y}" for x, y in el.points)
    # Compute rough centroid for rotation
    cx = sum(p[0] for p in el.points) / len(el.points)
    cy = sum(p[1] for p in el.points) / len(el.points)
    defs, fill_val = render_fill(el.fill, salt, textures)
    fop = _fill_opacity(el.fill)
    stroke = _stroke_attrs(el.stroke)
    rot = _rotate_attr(el.rotation, cx, cy)
    body = (
        f'<polygon points="{points_str}" '
        f'fill="{fill_val}" fill-opacity="{fop:.4f}" opacity="{el.opacity:.4f}" '
        f"{stroke}{rot}/>"
    )
    return defs + body


def render_ribbon(el: "ShapeElement", salt: str, textures: dict[str, bytes] | None = None) -> str:
    """A parallelogram. `path_params.skew` (pixels to offset top/bottom edges)."""
    assert el.rect is not None, "ribbon kind requires `rect`"
    x, y, w, h = el.rect
    skew = float(el.path_params.get("skew", 80.0))
    pts = [
        (x + skew, y),
        (x + w, y),
        (x + w - skew, y + h),
        (x, y + h),
    ]
    points_str = " ".join(f"{px},{py}" for px, py in pts)
    defs, fill_val = render_fill(el.fill, salt, textures)
    fop = _fill_opacity(el.fill)
    stroke = _stroke_attrs(el.stroke)
    rot = _rotate_attr(el.rotation, x + w / 2, y + h / 2)
    body = (
        f'<polygon points="{points_str}" '
        f'fill="{fill_val}" fill-opacity="{fop:.4f}" opacity="{el.opacity:.4f}" '
        f"{stroke}{rot}/>"
    )
    return defs + body


def render_triangle(el: "ShapeElement", salt: str, textures: dict[str, bytes] | None = None) -> str:
    """Triangle: use `points` (3 points) OR derive from `rect` + `path_params.orient`.

    orient: 'up' (default), 'down', 'left', 'right' — the pointed vertex direction.
    """
    defs_stroke_frag = ""
    if el.points is not None and len(el.points) == 3:
        return render_polygon(el, salt, textures)
    assert el.rect is not None, "triangle requires `rect` if no points"
    x, y, w, h = el.rect
    orient = str(el.path_params.get("orient", "up"))
    if orient == "up":
        pts = [(x + w / 2, y), (x + w, y + h), (x, y + h)]
    elif orient == "down":
        pts = [(x, y), (x + w, y), (x + w / 2, y + h)]
    elif orient == "left":
        pts = [(x + w, y), (x + w, y + h), (x, y + h / 2)]
    elif orient == "right":
        pts = [(x, y), (x + w, y + h / 2), (x, y + h)]
    else:
        pts = [(x + w / 2, y), (x + w, y + h), (x, y + h)]
    points_str = " ".join(f"{px},{py}" for px, py in pts)
    defs, fill_val = render_fill(el.fill, salt, textures)
    fop = _fill_opacity(el.fill)
    stroke = _stroke_attrs(el.stroke)
    body = (
        f'<polygon points="{points_str}" '
        f'fill="{fill_val}" fill-opacity="{fop:.4f}" opacity="{el.opacity:.4f}" '
        f"{stroke}/>"
    )
    return defs + defs_stroke_frag + body


def render_wave(el: "ShapeElement", salt: str, textures: dict[str, bytes] | None = None) -> str:
    """Filled wave band along the x-axis.

    path_params:
      amplitude: vertical wave peak (default h/6)
      frequency: cycles across width (default 2)
    """
    import math

    assert el.rect is not None, "wave kind requires `rect`"
    x, y, w, h = el.rect
    amplitude = float(el.path_params.get("amplitude", h / 6))
    frequency = float(el.path_params.get("frequency", 2.0))
    steps = max(24, int(w / 20))
    # Top edge: sine wave; bottom edge: straight line back
    top_pts = []
    for i in range(steps + 1):
        t = i / steps
        px = x + t * w
        py = y + amplitude * math.sin(2 * math.pi * frequency * t)
        top_pts.append((px, py))
    bot_pts = [(x + w, y + h), (x, y + h)]
    path = "M " + " L ".join(f"{px:.2f},{py:.2f}" for px, py in top_pts + bot_pts) + " Z"
    defs, fill_val = render_fill(el.fill, salt, textures)
    fop = _fill_opacity(el.fill)
    stroke = _stroke_attrs(el.stroke)
    return defs + (
        f'<path d="{path}" '
        f'fill="{fill_val}" fill-opacity="{fop:.4f}" opacity="{el.opacity:.4f}" '
        f"{stroke}/>"
    )


def render_line(el: "ShapeElement", salt: str, textures: dict[str, bytes] | None = None) -> str:
    """A simple line between two points in `points` (first two entries).

    If `rect` provided instead, draws horizontal line across rect's center.
    Ignores fill; uses stroke only.
    """
    if el.points and len(el.points) >= 2:
        (x1, y1), (x2, y2) = el.points[0], el.points[1]
    else:
        assert el.rect is not None
        x, y, w, h = el.rect
        x1, y1 = x, y + h / 2
        x2, y2 = x + w, y + h / 2
    stroke = _stroke_attrs(el.stroke)
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'opacity="{el.opacity:.4f}" {stroke}/>'
    )


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #


_DISPATCH = {
    "rect": render_rect,
    "rounded_rect": render_rounded_rect,
    "circle": render_circle,
    "ellipse": render_ellipse,
    "polygon": render_polygon,
    "ribbon": render_ribbon,
    "triangle": render_triangle,
    "wave": render_wave,
    "line": render_line,
}


def render_shape(
    el: "ShapeElement",
    canvas_rect: tuple[float, float, float, float],
    salt: str,
    textures: dict[str, bytes] | None = None,
) -> str:
    """Render a shape to an SVG fragment, applying bleed if requested."""
    effective = el
    if el.rect is not None and el.bleed:
        new_rect = apply_bleed(el.rect, el.bleed, canvas_rect)
        effective = el.model_copy(update={"rect": new_rect})
    renderer = _DISPATCH.get(el.kind)
    if renderer is None:
        raise ValueError(f"Unknown shape kind: {el.kind}")
    return renderer(effective, salt, textures)
