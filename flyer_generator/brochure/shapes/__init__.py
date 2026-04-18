"""Parameterized SVG shape library for brochure v2 composition.

Six shape functions, each returning an SVG fragment string. Input is always:
- `panel_rect`: the PanelRect being decorated (bleed/trim/safe available)
- `accent_hex`: primary accent color
- `seed`: deterministic seed for position jitter
- plus shape-specific kwargs

A recipe parser accepts strings like "accent_bar(placement=top, thickness=4)" and returns (name, kwargs). The composer uses `render_shape(recipe, panel_rect, accent_hex, seed)` which parses + dispatches.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Callable
from xml.sax.saxutils import escape

from flyer_generator.brochure.models import PanelRect

# Deterministic pseudo-random: use hash of (panel_name + seed + salt) modulo N.


def _det_int(panel_name: str, seed: int, salt: str, mod: int) -> int:
    h = hashlib.sha256(f"{panel_name}:{seed}:{salt}".encode()).hexdigest()
    return int(h[:8], 16) % mod


# ------------------------------- Shape functions -------------------------------


def circle_offpage(
    panel_rect: PanelRect,
    accent_hex: str,
    seed: int = 0,
    *,
    size: int = 240,
    offset_direction: str = "top-left",
    text: str | None = None,
) -> str:
    """Large circle partially clipped by the panel edge."""
    _, _, w, h = panel_rect.bleed_rect
    bx, by, _, _ = panel_rect.bleed_rect

    # Center depends on offset direction. Protrude more when only the horizontal
    # edge is crossed (the circle is a natural "peek" in from the side without
    # clashing with text). Protrude less on top/bottom so the visible cap stays
    # small and doesn't land in the heading zone.
    protrude_side = int(size * 0.40)  # when hitting left/right only
    protrude_vert = int(size * 0.25)  # when hitting top/bottom
    cx, cy = bx + w // 2, by + h // 2
    if "left" in offset_direction:
        cx = bx - protrude_side + size // 2
    if "right" in offset_direction:
        cx = bx + w + protrude_side - size // 2
    if "top" in offset_direction:
        cy = by - protrude_vert + size // 2
    if "bottom" in offset_direction:
        cy = by + h + protrude_vert - size // 2

    # Clip to the panel bleed rect so partial circle reads clean.
    clip_id = f"clip-{panel_rect.sheet}-{panel_rect.name}-circle-{seed}"
    parts = [
        f'<clipPath id="{clip_id}">'
        f'<rect x="{bx}" y="{by}" width="{w}" height="{h}"/>'
        f"</clipPath>",
        f'<g clip-path="url(#{clip_id})">'
        f'<circle cx="{cx}" cy="{cy}" r="{size // 2}" fill="{accent_hex}" fill-opacity="0.85"/>'
        f"</g>",
    ]
    if text:
        parts.append(
            f'<text x="{cx}" y="{cy}" text-anchor="middle" dominant-baseline="middle" '
            f'font-family="Arial, sans-serif" font-size="28" fill="#FFFFFF">'
            f"{escape(text)}</text>"
        )
    return "".join(parts)


def rotated_block(
    panel_rect: PanelRect,
    accent_hex: str,
    seed: int = 0,
    *,
    angle: int = 0,
    width: int = 120,
    height: int = 8,
    fill: str = "accent",
    text: str | None = None,
) -> str:
    """Rectangle rotated by `angle` degrees.

    For thin accent bars (height <= 20) anchors near the top of the safe zone just above the heading.
    For bigger decorative blocks (height > 20) anchors in the bottom third of the safe zone so it doesn't overlap headings or body text.
    """
    sx, sy, sw, sh = panel_rect.safe_rect
    jx = _det_int(panel_rect.name, seed, "rot-x", 30)
    if height <= 20:
        # Thin accent line — sits just above the heading.
        y = sy - 16
    else:
        # Larger block — anchor in the bottom third, away from heading + body.
        jy = _det_int(panel_rect.name, seed, "rot-y", 40)
        y = sy + int(sh * 0.66) + jy
    x = sx + jx
    fill_color = accent_hex if fill == "accent" else fill
    group_open = (
        f'<g transform="rotate({angle} {x + width // 2} {y + height // 2})">'
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" fill="{fill_color}"/>'
    )
    group_body = ""
    if text:
        text_y = y + height + 10 if height < 40 else y + height // 2 + 10
        group_body = (
            f'<text x="{x}" y="{text_y}" font-family="Arial, sans-serif" '
            f'font-size="24" fill="{fill_color}">{escape(text)}</text>'
        )
    return group_open + group_body + "</g>"


def accent_bar(
    panel_rect: PanelRect,
    accent_hex: str,
    seed: int = 0,
    *,
    placement: str = "top",
    thickness: int = 4,
) -> str:
    """Solid accent bar. placement: top | side | diagonal."""
    tx, ty, tw, th = panel_rect.trim_rect
    if placement == "top":
        return (
            f'<rect x="{tx}" y="{ty + 30}" width="{tw}" height="{thickness}" '
            f'fill="{accent_hex}"/>'
        )
    if placement == "side":
        return (
            f'<rect x="{tx}" y="{ty}" width="{thickness}" height="{th}" '
            f'fill="{accent_hex}"/>'
        )
    if placement == "diagonal":
        # Diagonal thin stripe from top-left to bottom-right of trim rect.
        return (
            f'<line x1="{tx}" y1="{ty}" x2="{tx + tw}" y2="{ty + th}" '
            f'stroke="{accent_hex}" stroke-width="{thickness}" stroke-opacity="0.4"/>'
        )
    # Fallback: top
    return (
        f'<rect x="{tx}" y="{ty + 30}" width="{tw}" height="{thickness}" '
        f'fill="{accent_hex}"/>'
    )


def dot_grid(
    panel_rect: PanelRect,
    accent_hex: str,
    seed: int = 0,
    *,
    density: str = "medium",
    color: str | None = None,
) -> str:
    """Regular dot pattern filling the panel's bleed rect."""
    spacing_map = {"sparse": 48, "medium": 32, "dense": 20}
    spacing = spacing_map.get(density, 32)
    dot_color = color or accent_hex
    bx, by, bw, bh = panel_rect.bleed_rect
    pattern_id = f"dots-{panel_rect.sheet}-{panel_rect.name}-{seed}"
    return (
        f'<defs><pattern id="{pattern_id}" x="0" y="0" '
        f'width="{spacing}" height="{spacing}" patternUnits="userSpaceOnUse">'
        f'<circle cx="{spacing // 2}" cy="{spacing // 2}" r="2" '
        f'fill="{dot_color}" fill-opacity="0.35"/>'
        f"</pattern></defs>"
        f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" fill="url(#{pattern_id})"/>'
    )


def pullquote_frame(
    panel_rect: PanelRect,
    accent_hex: str,
    seed: int = 0,
    *,
    shape: str = "oval",
    text: str | None = None,
) -> str:
    """Text container: ellipse ('oval') or asymmetric rounded rect ('asym_block')."""
    sx, sy, sw, sh = panel_rect.safe_rect
    cx = sx + sw // 2
    cy = sy + sh // 2
    frame_w = int(sw * 0.9)
    frame_h = int(sh * 0.45)

    if shape == "oval":
        frame = (
            f'<ellipse cx="{cx}" cy="{cy}" rx="{frame_w // 2}" ry="{frame_h // 2}" '
            f'fill="none" stroke="{accent_hex}" stroke-width="4"/>'
        )
    else:  # asym_block
        frame = (
            f'<rect x="{cx - frame_w // 2}" y="{cy - frame_h // 2}" '
            f'width="{frame_w}" height="{frame_h}" rx="40" ry="40" '
            f'fill="none" stroke="{accent_hex}" stroke-width="4"/>'
        )

    if not text:
        return frame

    # Simple centered text label inside the frame.
    return (
        frame
        + f'<text x="{cx}" y="{cy}" text-anchor="middle" dominant-baseline="middle" '
        f'font-family="Georgia, serif" font-size="34" font-style="italic" '
        f'fill="{accent_hex}">{escape(text)}</text>'
    )


def corner_wedge(
    panel_rect: PanelRect,
    accent_hex: str,
    seed: int = 0,
    *,
    corner: str = "bottom-right",
    size: int = 180,
    pattern: str = "solid",
) -> str:
    """Triangular wedge filling a panel corner."""
    bx, by, bw, bh = panel_rect.bleed_rect
    corners = {
        "top-left": f"{bx},{by} {bx + size},{by} {bx},{by + size}",
        "top-right": f"{bx + bw},{by} {bx + bw - size},{by} {bx + bw},{by + size}",
        "bottom-left": f"{bx},{by + bh} {bx + size},{by + bh} {bx},{by + bh - size}",
        "bottom-right": f"{bx + bw},{by + bh} {bx + bw - size},{by + bh} {bx + bw},{by + bh - size}",
    }
    points = corners.get(corner, corners["bottom-right"])

    if pattern == "solid":
        return f'<polygon points="{points}" fill="{accent_hex}" fill-opacity="0.75"/>'
    if pattern == "striped":
        return (
            f'<polygon points="{points}" fill="{accent_hex}" fill-opacity="0.25"/>'
            + _striped_overlay(points, accent_hex, panel_rect, seed)
        )
    if pattern == "dotted":
        # Dot cluster in the corner.
        return f'<polygon points="{points}" fill="{accent_hex}" fill-opacity="0.15"/>'
    return f'<polygon points="{points}" fill="{accent_hex}"/>'


def _striped_overlay(
    polygon_points: str, accent_hex: str, panel_rect: PanelRect, seed: int
) -> str:
    """Diagonal stripes inside a polygon via a clipPath."""
    bx, by, bw, bh = panel_rect.bleed_rect
    clip_id = f"stripe-{panel_rect.sheet}-{panel_rect.name}-{seed}"
    lines = []
    for i in range(0, bw + bh, 40):
        lines.append(
            f'<line x1="{bx + i}" y1="{by}" x2="{bx + i - bh}" y2="{by + bh}" '
            f'stroke="{accent_hex}" stroke-width="3" stroke-opacity="0.55"/>'
        )
    return (
        f'<clipPath id="{clip_id}"><polygon points="{polygon_points}"/></clipPath>'
        f'<g clip-path="url(#{clip_id})">{"".join(lines)}</g>'
    )


# ------------------------------- Recipe parser -------------------------------

# Registry name → callable
SHAPE_FUNCTIONS: dict[str, Callable[..., str]] = {
    "circle_offpage": circle_offpage,
    "rotated_block": rotated_block,
    "accent_bar": accent_bar,
    "dot_grid": dot_grid,
    "pullquote_frame": pullquote_frame,
    "corner_wedge": corner_wedge,
}


_RECIPE_RE = re.compile(r"^(?P<name>\w+)\((?P<args>.*)\)$")


def parse_shape_recipe(recipe: str) -> tuple[str, dict[str, object]]:
    """Parse a recipe string like 'accent_bar(placement=top, thickness=4)'.

    Returns (shape_name, kwargs_dict). Values are ints when they parse as int,
    else strings (stripped of surrounding quotes if present).
    """
    m = _RECIPE_RE.match(recipe.strip())
    if not m:
        raise ValueError(f"Invalid shape recipe: {recipe!r}")
    name = m.group("name")
    args_str = m.group("args").strip()
    kwargs: dict[str, object] = {}
    if args_str:
        # Split on top-level commas (no nested parens for v1 shapes).
        for part in args_str.split(","):
            if "=" not in part:
                raise ValueError(f"Invalid shape arg {part!r} in recipe {recipe!r}")
            k, v = part.split("=", 1)
            k = k.strip()
            v = v.strip().strip("'\"")
            # Coerce to int if numeric.
            try:
                kwargs[k] = int(v)
            except ValueError:
                kwargs[k] = v
    return name, kwargs


def render_shape(
    recipe: str,
    panel_rect: PanelRect,
    accent_hex: str,
    seed: int = 0,
    *,
    text: str | None = None,
) -> str:
    """Parse recipe and dispatch to the right shape function. Returns SVG fragment.

    If the parsed kwargs reference text=brief, the caller-provided `text` is substituted; otherwise text is left to whatever the recipe specified.
    """
    name, kwargs = parse_shape_recipe(recipe)
    if kwargs.get("text") == "brief" and text is not None:
        kwargs["text"] = text
    fn = SHAPE_FUNCTIONS.get(name)
    if fn is None:
        return f"<!-- unknown shape: {escape(name)} -->"
    return fn(panel_rect, accent_hex, seed=seed, **kwargs)


__all__ = [
    "SHAPE_FUNCTIONS",
    "accent_bar",
    "circle_offpage",
    "corner_wedge",
    "dot_grid",
    "parse_shape_recipe",
    "pullquote_frame",
    "render_shape",
    "rotated_block",
]
