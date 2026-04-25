"""Pydantic schema for poster template JSON documents.

A poster template JSON declares the visual structure of a print-sized poster
canvas (5400×7200 to 8100×12000 depending on size preset). The Canvas
dimensions in the template JSON are the **template's design canvas**
(typically 5400×7200 = 18×24 at 300 DPI); the worker overrides the
rasterized output dimensions per request via
``FlyerGenerator(canvas_dimensions=...)`` (see Phase 24 D-XX and the locked
size-to-dim mapping in 24-CONTEXT.md).

This model is intentionally strict (extra="forbid") so malformed templates
fail loud at load time, not at render time.

Primitives (GradientStop, SolidFill, LinearGradientFill, RadialGradientFill,
TextureSlotFill, Fill, Stroke, ShapeElement, TextElement, BulletsElement,
LogoPlaceholder, ImagePlaceholder, DividerElement, PanelElement, PanelSchema)
are copied verbatim from
``flyer_generator.flyer.schema_renderer.schema_model`` to avoid a
cross-package dependency from poster -> flyer at the module boundary. The
shared ``validate_hex_color`` helper IS imported from
``flyer_generator.brochure.models`` (acceptable cross-package utility import
per 22-PATTERNS line 151).

Differences vs. the flyer schema:
- ``subtype_compat`` field is dropped (posters have no event/info split).
- :class:`Canvas` defaults to (5400, 7200) — 18×24 portrait at 300 DPI.
- :class:`Typography` defaults are bumped ~3× for print reading distance.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from flyer_generator.brochure.models import validate_hex_color

# Poster is single-canvas like the flyer.
_PanelName = Literal["hero"]

# Retain flyer-relevant text roles. Posters share the same role vocabulary;
# only the typography defaults differ (print-distance reading scale).
_TextRole = Literal[
    "cover_title",
    "cover_subtitle",
    "section_heading",
    "body",
    "lead_paragraph",
    "bullet",
    "quote",
    "cta_heading",
    "cta_body",
    "org_name",
    "contact_name",
    "contact_phone",
    "contact_email",
    "contact_url",
    "contact_address",
    "tagline",
    "static",
]

_BulletStyle = Literal["disc", "dash", "square", "accent_block", "numbered"]

_ShapeKind = Literal[
    "rect",
    "rounded_rect",
    "circle",
    "ellipse",
    "polygon",
    "ribbon",
    "triangle",
    "wave",
    "line",
]

_Align = Literal["left", "center", "right", "justify"]
_VAlign = Literal["top", "middle", "bottom"]


class GradientStop(BaseModel):
    """One color stop in a linear or radial gradient."""

    model_config = ConfigDict(extra="forbid")

    offset: float = Field(ge=0.0, le=1.0)
    color: str
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("color")
    @classmethod
    def _validate_color(cls, v: str) -> str:
        return validate_hex_color(v)


class SolidFill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["solid"] = "solid"
    color: str
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("color")
    @classmethod
    def _validate_color(cls, v: str) -> str:
        return validate_hex_color(v)


class LinearGradientFill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["linear_gradient"] = "linear_gradient"
    stops: list[GradientStop] = Field(min_length=2, max_length=6)
    angle: float = Field(
        default=0.0,
        description="Degrees, 0 = top-to-bottom, 90 = left-to-right, clockwise.",
    )


class RadialGradientFill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["radial_gradient"] = "radial_gradient"
    stops: list[GradientStop] = Field(min_length=2, max_length=6)
    center: tuple[float, float] = (0.5, 0.5)  # relative 0..1
    radius: float = Field(default=0.75, ge=0.1, le=2.0)


class TextureSlotFill(BaseModel):
    """Reserved for Phase 4 — fill a shape with a ComfyUI-generated texture."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["texture_slot"] = "texture_slot"
    slot: str
    fallback: SolidFill | LinearGradientFill | RadialGradientFill


Fill = Annotated[
    Union[SolidFill, LinearGradientFill, RadialGradientFill, TextureSlotFill],
    Field(discriminator="type"),
]


class Stroke(BaseModel):
    model_config = ConfigDict(extra="forbid")

    color: str
    width: float = Field(ge=0.0)
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    dash: list[float] | None = None

    @field_validator("color")
    @classmethod
    def _validate_color(cls, v: str) -> str:
        return validate_hex_color(v)


class ShapeElement(BaseModel):
    """A geometric primitive: rectangle, circle, polygon, ribbon, etc.

    Positioning:
      - `rect` = [x, y, w, h] for rect-based kinds (rect, rounded_rect, ellipse).
      - `points` = list of [x, y] for polygon / triangle.
      - `path_params` for kind-specific knobs (corner_radius, wave_amplitude, etc.).
      - When bleed=True, the renderer extends the shape to the nearest canvas
        edge(s) after panel placement.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["shape"] = "shape"
    kind: _ShapeKind
    rect: tuple[float, float, float, float] | None = None
    points: list[tuple[float, float]] | None = None
    path_params: dict = Field(default_factory=dict)
    fill: Fill | None = None
    stroke: Stroke | None = None
    rotation: float = 0.0
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    bleed: Literal[False, True, "left", "right", "top", "bottom", "all"] = False
    z: int = 0


class TextElement(BaseModel):
    """A text region with a hard character budget."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["text"] = "text"
    bbox: tuple[float, float, float, float]
    role: _TextRole
    content_key: str | None = None
    static_text: str | None = None
    section_index: int | None = None
    max_chars: int | None = None
    wrap: bool = True
    align: _Align = "left"
    valign: _VAlign = "top"
    color: str | None = None
    font_family: str | None = None
    font_size: int | None = None
    line_height: int | None = None
    weight: Literal["normal", "medium", "semibold", "bold"] = "normal"
    letter_spacing: float = 0.0
    uppercase: bool = False
    italic: bool = False
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    z: int = 10

    @field_validator("color")
    @classmethod
    def _validate_color(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return validate_hex_color(v)


class BulletsElement(BaseModel):
    """Render a bulleted list from content."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["bullets"] = "bullets"
    bbox: tuple[float, float, float, float]
    content_key: str
    section_index: int | None = None
    max_items: int = 6
    max_chars_per_item: int = 80
    bullet_style: _BulletStyle = "disc"
    bullet_color: str | None = None
    text_color: str | None = None
    font_family: str | None = None
    font_size: int | None = None
    line_height: int | None = None
    item_spacing: int = 6
    z: int = 10

    @field_validator("bullet_color", "text_color")
    @classmethod
    def _validate_color(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return validate_hex_color(v)


class LogoPlaceholder(BaseModel):
    """Slot for a user-supplied logo image. Fallback renders a monogram."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["logo_placeholder"] = "logo_placeholder"
    bbox: tuple[float, float, float, float]
    align: _Align = "center"
    valign: _VAlign = "middle"
    fallback_style: Literal["monogram_circle", "monogram_square", "initials_plain"] = (
        "monogram_circle"
    )
    fallback_color: str | None = None
    z: int = 20

    @field_validator("fallback_color")
    @classmethod
    def _validate_color(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return validate_hex_color(v)


class ImagePlaceholder(BaseModel):
    """Slot for a generated or supplied image. Phase 1 renders fallback only."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["image_placeholder"] = "image_placeholder"
    bbox: tuple[float, float, float, float]
    slot: str = "hero"
    fallback_fill: Fill | None = None
    mask: Literal["none", "rounded", "circle"] = "none"
    corner_radius: float = 0.0
    caption_below: str | None = None
    show_placeholder_label: bool = True
    z: int = 5


class DividerElement(BaseModel):
    """Rule line."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["divider"] = "divider"
    orientation: Literal["horizontal", "vertical"] = "horizontal"
    position: tuple[float, float, float, float]
    thickness: float = 2.0
    color: str
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    dash: list[float] | None = None
    z: int = 8

    @field_validator("color")
    @classmethod
    def _validate_color(cls, v: str) -> str:
        return validate_hex_color(v)


PanelElement = Annotated[
    Union[
        ShapeElement,
        TextElement,
        BulletsElement,
        LogoPlaceholder,
        ImagePlaceholder,
        DividerElement,
    ],
    Field(discriminator="type"),
]


class PanelSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = None
    background: Fill | None = None
    elements: list[PanelElement] = Field(default_factory=list)


class Canvas(BaseModel):
    """Poster canvas defaults to 5400x7200 (18×24 portrait at 300 DPI).

    The composer treats this as the template's design canvas; the worker
    re-canvases to the requested size preset (24×36 → 7200×10800,
    27×40 → 8100×12000) at render time per locked decision in 24-CONTEXT.md.
    """

    model_config = ConfigDict(extra="forbid")

    width: int = Field(default=5400, gt=0)
    height: int = Field(default=7200, gt=0)


class Palette(BaseModel):
    """Poster palette — same shape as flyer (scrim_opacity_top/bottom knobs).

    Defaults are reused so existing palette utilities apply unchanged.
    """

    model_config = ConfigDict(extra="forbid")

    accent_default: str
    neutral_dark: str = "#1A1A1A"
    neutral_light: str = "#FAFAF7"
    muted: str = "#E8E6E1"
    scrim_opacity_top: float = Field(default=0.75, ge=0.0, le=1.0)
    scrim_opacity_bottom: float = Field(default=0.85, ge=0.0, le=1.0)
    extras: dict[str, str] = Field(default_factory=dict)

    @field_validator("accent_default", "neutral_dark", "neutral_light", "muted")
    @classmethod
    def _validate_color(cls, v: str) -> str:
        return validate_hex_color(v)

    @field_validator("extras")
    @classmethod
    def _validate_extras(cls, v: dict[str, str]) -> dict[str, str]:
        for _key, color in v.items():
            validate_hex_color(color)
        return v


class Typography(BaseModel):
    """Poster typography defaults — sized for print-distance reading.

    Sized for 18+ inch reading distance at 300 DPI; cover_title_size=300 vs
    flyer's 82 reflects the ~3.65× linear scale and ensures headlines remain
    readable from across a room when printed at 18×24 minimum. Subtitle and
    body sizes scale similarly. Templates may override these per design
    intent (editorial_grand uses 360pt for an extra-large serif title;
    bold_announcement uses 420pt for a display sans).
    """

    model_config = ConfigDict(extra="forbid")

    heading_family: str = "'Arial Black', 'Helvetica Neue', Arial, sans-serif"
    body_family: str = "'Arial', sans-serif"
    cover_title_size: int = Field(default=300, gt=0)  # ~3.65× flyer's 82
    cover_subtitle_size: int = Field(default=180, gt=0)
    heading_size: int = Field(default=220, gt=0)
    body_size: int = Field(default=120, gt=0)
    body_line_height: int = Field(default=160, gt=0)
    body_max_chars_per_line: int = Field(default=32, gt=0)
    bullet_size: int = Field(default=120, gt=0)
    bullet_line_height: int = Field(default=160, gt=0)


class PosterTemplateSchema(BaseModel):
    """Top-level poster template schema. Loaded from JSON under ``schemas/``.

    Notable differences from :class:`FlyerTemplateSchema`:

    - No ``subtype_compat`` field — posters have no event/info split.
    - Canvas defaults to (5400, 7200) — 18×24 portrait at 300 DPI.
    - Typography defaults are print-scaled (~3× the flyer pixel sizes).
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"]
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    description: str
    tone_keywords: list[str] = Field(default_factory=list)
    canvas: Canvas = Field(default_factory=Canvas)
    palette: Palette
    typography: Typography = Field(default_factory=Typography)
    panels: dict[_PanelName, PanelSchema]

    @field_validator("panels")
    @classmethod
    def _validate_panels_complete(
        cls, v: dict[str, PanelSchema]
    ) -> dict[str, PanelSchema]:
        required = {"hero"}  # poster = single-canvas
        missing = required - set(v.keys())
        if missing:
            msg = f"template missing panels: {sorted(missing)}"
            raise ValueError(msg)
        return v
