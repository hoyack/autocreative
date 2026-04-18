"""Named layout templates for brochure v2 composition.

Each template declares typography scale, gradient opacity, accent placement
defaults, and a per-panel shape mix (shapes resolved in phase 12 by the
composer). LLM layout-selection picks a template by name.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from flyer_generator.brochure.generative.models import LayoutTemplateName


@dataclass(frozen=True)
class LayoutTemplate:
    """Declarative layout template. Read by composer v2 (phase 12)."""

    name: LayoutTemplateName
    description: str
    tone_keywords: tuple[str, ...]  # hints the LLM uses to match templates to content tone

    # Typography
    heading_font_family: str
    body_font_family: str
    cover_title_font_size: int
    heading_font_size: int
    body_font_size: int
    body_line_height: int
    body_max_chars_per_line: int

    # Gradients on non-cover panels
    gradient_opacity_top: float
    gradient_opacity_bottom: float

    # Shape recipe per panel.
    # Each list element is a string "shape_name(param=value, ...)" resolved in phase 12.
    # An empty list means "solid gradient only".
    shape_mix: dict[str, tuple[str, ...]]

    # Default accent placement + cover treatment (LLM may override via LayoutChoice).
    default_accent_placement: Literal["top_rule", "side_band", "corner_block"]
    default_cover_treatment: Literal["image_full", "image_half_shapes", "shapes_only"]


# ----------------------------- The six templates -----------------------------

EDITORIAL = LayoutTemplate(
    name="editorial",
    description="Professional services, B2B, conservative. Serif body, thin accent rules, minimal shapes.",
    tone_keywords=("professional", "authoritative", "corporate", "b2b", "law", "finance", "consulting"),
    heading_font_family="'Playfair Display', 'Times New Roman', serif",
    body_font_family="'Source Serif Pro', 'Georgia', serif",
    cover_title_font_size=104,
    heading_font_size=64,
    body_font_size=36,
    body_line_height=46,
    body_max_chars_per_line=30,
    gradient_opacity_top=0.12,
    gradient_opacity_bottom=0.04,
    shape_mix={
        "cover": (),
        "back_cover": ("accent_bar(placement=top, thickness=4)",),
        "tuck_flap": ("accent_bar(placement=top, thickness=2)",),
        "inner_left": ("accent_bar(placement=top, thickness=4)",),
        "inner_center": ("accent_bar(placement=top, thickness=4)",),
        "inner_right": ("accent_bar(placement=top, thickness=4)",),
    },
    default_accent_placement="top_rule",
    default_cover_treatment="image_full",
)

MINIMALIST = LayoutTemplate(
    name="minimalist",
    description="Tech, SaaS, design studios. Sans-serif, single accent block per inner panel, lots of whitespace.",
    tone_keywords=("tech", "saas", "minimal", "clean", "modern", "startup", "software", "design"),
    heading_font_family="'Inter', 'Helvetica Neue', sans-serif",
    body_font_family="'Inter', 'Helvetica Neue', sans-serif",
    cover_title_font_size=112,
    heading_font_size=72,
    body_font_size=32,
    body_line_height=46,
    body_max_chars_per_line=32,
    gradient_opacity_top=0.05,
    gradient_opacity_bottom=0.02,
    shape_mix={
        "cover": (),
        "back_cover": ("corner_wedge(corner=bottom-right, size=180, pattern=solid)",),
        "tuck_flap": (),
        "inner_left": ("rotated_block(angle=0, width=90, height=6, fill=accent)",),
        "inner_center": ("rotated_block(angle=0, width=90, height=6, fill=accent)",),
        "inner_right": ("rotated_block(angle=0, width=90, height=6, fill=accent)",),
    },
    default_accent_placement="corner_block",
    default_cover_treatment="image_full",
)

PLAYFUL = LayoutTemplate(
    name="playful",
    description="Events, kids, food, casual. Circles off-page, rotated tags, dot-grid accents.",
    tone_keywords=("playful", "fun", "kids", "family", "event", "food", "casual", "celebration", "festival"),
    heading_font_family="'Fredoka', 'Avenir Next', sans-serif",
    body_font_family="'Avenir Next', 'Avenir', sans-serif",
    cover_title_font_size=130,
    heading_font_size=80,
    body_font_size=38,
    body_line_height=50,
    body_max_chars_per_line=28,
    gradient_opacity_top=0.22,
    gradient_opacity_bottom=0.08,
    shape_mix={
        "cover": (),
        "back_cover": ("dot_grid(density=sparse)", "rotated_block(angle=-8, width=300, height=80)"),
        "tuck_flap": ("circle_offpage(size=260, offset_direction=bottom-right)",),
        "inner_left": ("circle_offpage(size=220, offset_direction=top-left)", "dot_grid(density=sparse)"),
        "inner_center": ("rotated_block(angle=6, width=340, height=100)",),
        "inner_right": ("circle_offpage(size=240, offset_direction=bottom-right)", "dot_grid(density=sparse)"),
    },
    default_accent_placement="corner_block",
    default_cover_treatment="image_half_shapes",
)

GALLERY_STRIP = LayoutTemplate(
    name="gallery_strip",
    description="Portfolios, retail, image-heavy. Horizontal image band per panel, minimal text below.",
    tone_keywords=("portfolio", "retail", "gallery", "photography", "visual", "showcase", "catalog"),
    heading_font_family="'Inter', 'Helvetica Neue', sans-serif",
    body_font_family="'Inter', 'Helvetica Neue', sans-serif",
    cover_title_font_size=96,
    heading_font_size=56,
    body_font_size=34,
    body_line_height=44,
    body_max_chars_per_line=34,
    gradient_opacity_top=0.08,
    gradient_opacity_bottom=0.03,
    shape_mix={
        "cover": (),
        "back_cover": ("accent_bar(placement=side, thickness=8)",),
        "tuck_flap": ("accent_bar(placement=side, thickness=4)",),
        "inner_left": ("accent_bar(placement=side, thickness=8)",),
        "inner_center": ("accent_bar(placement=side, thickness=8)",),
        "inner_right": ("accent_bar(placement=side, thickness=8)",),
    },
    default_accent_placement="side_band",
    default_cover_treatment="image_full",
)

QUOTE_DRIVEN = LayoutTemplate(
    name="quote_driven",
    description="Non-profits, manifestos, mission-driven. Large pull-quotes in ovals; corner wedges.",
    tone_keywords=("nonprofit", "mission", "manifesto", "cause", "advocacy", "community", "movement"),
    heading_font_family="'Playfair Display', 'Georgia', serif",
    body_font_family="'Source Serif Pro', 'Georgia', serif",
    cover_title_font_size=96,
    heading_font_size=48,
    body_font_size=40,
    body_line_height=54,
    body_max_chars_per_line=26,
    gradient_opacity_top=0.18,
    gradient_opacity_bottom=0.06,
    shape_mix={
        "cover": (),
        "back_cover": ("corner_wedge(corner=top-left, size=220, pattern=striped)",),
        "tuck_flap": ("pullquote_frame(shape=oval, text=brief)",),
        "inner_left": ("pullquote_frame(shape=oval)", "corner_wedge(corner=bottom-right, size=140, pattern=solid)"),
        "inner_center": ("pullquote_frame(shape=asym_block)",),
        "inner_right": ("pullquote_frame(shape=oval)", "corner_wedge(corner=top-right, size=140, pattern=dotted)"),
    },
    default_accent_placement="corner_block",
    default_cover_treatment="image_half_shapes",
)

SPOTLIGHT = LayoutTemplate(
    name="spotlight",
    description="Single-product or single-event focus. Oversized hero spanning cover + tuck flap; minimal inner text.",
    tone_keywords=("product", "launch", "spotlight", "single", "focus", "hero", "event"),
    heading_font_family="'Inter', 'Helvetica Neue', sans-serif",
    body_font_family="'Inter', 'Helvetica Neue', sans-serif",
    cover_title_font_size=140,
    heading_font_size=56,
    body_font_size=34,
    body_line_height=46,
    body_max_chars_per_line=30,
    gradient_opacity_top=0.10,
    gradient_opacity_bottom=0.03,
    shape_mix={
        "cover": (),
        "back_cover": ("accent_bar(placement=diagonal, thickness=6)",),
        "tuck_flap": (),
        "inner_left": ("rotated_block(angle=0, width=120, height=8, fill=accent)",),
        "inner_center": ("rotated_block(angle=0, width=120, height=8, fill=accent)",),
        "inner_right": ("rotated_block(angle=0, width=120, height=8, fill=accent)",),
    },
    default_accent_placement="top_rule",
    default_cover_treatment="image_full",
)


TEMPLATE_REGISTRY: dict[str, LayoutTemplate] = {
    t.name: t
    for t in (EDITORIAL, MINIMALIST, PLAYFUL, GALLERY_STRIP, QUOTE_DRIVEN, SPOTLIGHT)
}


def get_template(name: str) -> LayoutTemplate:
    """Return the LayoutTemplate with the given name.

    Raises KeyError if name is not in the registry.
    """
    return TEMPLATE_REGISTRY[name]


def all_templates() -> tuple[LayoutTemplate, ...]:
    """All registered templates in registry order."""
    return tuple(TEMPLATE_REGISTRY.values())


__all__ = [
    "EDITORIAL",
    "GALLERY_STRIP",
    "LayoutTemplate",
    "MINIMALIST",
    "PLAYFUL",
    "QUOTE_DRIVEN",
    "SPOTLIGHT",
    "TEMPLATE_REGISTRY",
    "all_templates",
    "get_template",
]
