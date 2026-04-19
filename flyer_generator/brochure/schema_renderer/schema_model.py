"""Pydantic schema for template JSON documents.

A template JSON declares the visual structure of a brochure: which shapes,
text regions, and placeholders populate each of the six panels, what palette
and typography defaults apply, and how text regions map to content keys.

This model is intentionally strict (extra="forbid") so malformed templates
fail loud at load time, not at render time.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from flyer_generator.brochure.models import validate_hex_color

_PanelName = Literal[
    "front_cover",
    "back_cover",
    "tuck_flap",
    "inner_left",
    "inner_center",
    "inner_right",
]

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
    radius: float = Field(default=0.75, ge=0.1, le=2.0)  # relative to shape half-diagonal


class TextureSlotFill(BaseModel):
    """Reserved for Phase 4 — fill a shape with a ComfyUI-generated texture."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["texture_slot"] = "texture_slot"
    slot: str  # e.g. "texture_1"
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
    rotation: float = 0.0  # degrees, around shape center
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    bleed: Literal[False, True, "left", "right", "top", "bottom", "all"] = False
    z: int = 0  # z-order within panel; higher renders later (on top)


class TextElement(BaseModel):
    """A text region with a hard character budget."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["text"] = "text"
    bbox: tuple[float, float, float, float]  # x, y, w, h
    role: _TextRole
    content_key: str | None = None
    # If content_key omitted for role == 'static', `static_text` must be set.
    static_text: str | None = None
    section_index: int | None = None  # for per-section roles (body, section_heading)
    max_chars: int | None = None
    wrap: bool = True
    align: _Align = "left"
    valign: _VAlign = "top"
    color: str | None = None
    font_family: str | None = None  # overrides template.typography
    font_size: int | None = None
    line_height: int | None = None
    weight: Literal["normal", "medium", "semibold", "bold"] = "normal"
    letter_spacing: float = 0.0
    uppercase: bool = False
    italic: bool = False
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    z: int = 10  # text is above shapes by default

    @field_validator("color")
    @classmethod
    def _validate_color(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return validate_hex_color(v)


class BulletsElement(BaseModel):
    """Render a bulleted list from content (sections[i].bullets or back_panel.bullets)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["bullets"] = "bullets"
    bbox: tuple[float, float, float, float]
    content_key: str  # e.g. "sections[0].bullets" or "back_panel.bullets"
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
    fallback_style: Literal["monogram_circle", "monogram_square", "initials_plain"] = "monogram_circle"
    fallback_color: str | None = None  # defaults to palette.accent_default
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
    slot: str = "hero"  # hero, spot_1, spot_2, spot_3
    fallback_fill: Fill | None = None  # defaults to a muted gradient when None
    mask: Literal["none", "rounded", "circle"] = "none"
    corner_radius: float = 0.0
    caption_below: str | None = None
    show_placeholder_label: bool = True  # render "[hero image]" text when no image supplied
    z: int = 5


class DividerElement(BaseModel):
    """Rule line."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["divider"] = "divider"
    orientation: Literal["horizontal", "vertical"] = "horizontal"
    position: tuple[float, float, float, float]  # x, y, end_x, end_y
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
    background: Fill | None = None  # optional full-panel background fill
    elements: list[PanelElement] = Field(default_factory=list)


class Canvas(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: int = Field(ge=100)
    height: int = Field(ge=100)


class Palette(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accent_default: str
    neutral_dark: str = "#111827"
    neutral_light: str = "#F7F7F5"
    muted: str = "#E5E7EB"
    extras: dict[str, str] = Field(default_factory=dict)

    @field_validator("accent_default", "neutral_dark", "neutral_light", "muted")
    @classmethod
    def _validate_color(cls, v: str) -> str:
        return validate_hex_color(v)

    @field_validator("extras")
    @classmethod
    def _validate_extras(cls, v: dict[str, str]) -> dict[str, str]:
        for key, color in v.items():
            validate_hex_color(color)
        return v


class Typography(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heading_family: str = "'Inter', 'Helvetica Neue', sans-serif"
    body_family: str = "'Inter', 'Helvetica Neue', sans-serif"
    cover_title_size: int = 112
    cover_subtitle_size: int = 48
    heading_size: int = 64
    body_size: int = 34
    body_line_height: int = 46
    body_max_chars_per_line: int = 32
    bullet_size: int = 32
    bullet_line_height: int = 44


class TemplateSchema(BaseModel):
    """The top-level template schema. Loaded from JSON under schemas/."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"]
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    description: str
    tone_keywords: list[str] = Field(default_factory=list)
    canvas: Canvas
    palette: Palette
    typography: Typography = Field(default_factory=Typography)
    panels: dict[_PanelName, PanelSchema]

    @field_validator("panels")
    @classmethod
    def _validate_panels_complete(
        cls, v: dict[str, PanelSchema]
    ) -> dict[str, PanelSchema]:
        required = {
            "front_cover",
            "back_cover",
            "tuck_flap",
            "inner_left",
            "inner_center",
            "inner_right",
        }
        missing = required - set(v.keys())
        if missing:
            msg = f"template missing panels: {sorted(missing)}"
            raise ValueError(msg)
        return v
