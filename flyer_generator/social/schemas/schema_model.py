"""PostTemplate Pydantic schema for Phase 19 social posts.

A social post template is a single-panel (vs brochure's six-panel) document
describing canvas dimensions, optional image slot, shape overlays (e.g. a
darkening scrim band), text slots with role-driven styling, and an optional
logo placeholder.

Design tenets (19-PATTERNS.md line 583):

* **Reuse, do not duplicate:** ``Canvas``, ``Palette``, ``Typography``,
  ``ShapeElement``, and ``LogoPlaceholder`` come from the brochure renderer.
  Those types are already battle-tested by the brochure pipeline and ship with
  hex-color validation, discriminated fills, and strict ``extra="forbid"``
  semantics.
* **Brand-kit-first:** ``palette`` and ``typography`` default to ``None`` so
  that per-client brand kits (SOC-02, SOC-05) are injected at render time by
  Plan 06's ``_apply_brand_kit_to_post_template``. Authoring literal palette
  or typography values in template JSON breaks the brand-kit model.
* **Semantic color/font references:** ``TextSlot.color_role`` and
  ``TextSlot.font_role`` are resolved to the applied brand kit at render time
  rather than baked into the JSON.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from flyer_generator.brochure.schema_renderer.schema_model import (
    Canvas,
    LogoPlaceholder,
    Palette,
    ShapeElement,
    Typography,
)
from flyer_generator.social.models import Intent, Platform

_AspectString = Literal["1:1", "4:5", "1.91:1", "16:9", "9:16"]

_TextRole = Literal[
    "title",
    "body",
    "cta",
    "caption_overlay",
    "hashtag_strip",
    "org_mark",
]
_ColorRole = Literal["primary", "neutral_dark", "neutral_light", "accent"]
_FontRole = Literal["heading", "body"]
_FontWeight = Literal["normal", "medium", "semibold", "bold"]


class ImageSlot(BaseModel):
    """Rectangle carrying a generated or user-supplied image."""

    model_config = ConfigDict(extra="forbid")

    bbox: tuple[float, float, float, float]
    aspect: _AspectString
    slot_name: str = "hero"


class TextSlot(BaseModel):
    """A text region bound to a content_key with role-driven styling.

    ``color_role`` and ``font_role`` are resolved to the applied brand kit at
    render time; they must not be hex literals or font-family strings.
    """

    model_config = ConfigDict(extra="forbid")

    bbox: tuple[float, float, float, float]
    role: _TextRole
    content_key: str
    max_chars: int = Field(gt=0)
    color_role: _ColorRole
    font_role: _FontRole
    font_size: int = Field(gt=0)
    font_weight: _FontWeight = "normal"
    align: Literal["left", "center", "right"] = "left"
    valign: Literal["top", "middle", "bottom"] = "top"
    uppercase: bool = False


class PostTemplate(BaseModel):
    """Top-level social post template. Loaded from JSON under ``schemas/``.

    Invariants enforced at validation time:

    * ``name`` matches ``^[a-z][a-z0-9_-]*(__[a-z][a-z0-9-]*)?$`` (filename
      stem).
    * ``palette`` and ``typography`` default to ``None`` so the brand kit
      drives color + typography at render time (see 19-PATTERNS.md, SOC-02 /
      SOC-05).
    * ``image_slot`` may be ``None`` for pure-text posts
      (e.g. ``twitter__announcement``).
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"]
    name: str = Field(pattern=r"^[a-z][a-z0-9_-]*(__[a-z][a-z0-9-]*)?$")
    platform: Platform
    intent: Intent
    description: str
    canvas: Canvas
    palette: Palette | None = None
    typography: Typography | None = None
    text_budgets: dict[str, int] = Field(default_factory=dict)
    image_slot: ImageSlot | None = None
    shapes: list[ShapeElement] = Field(default_factory=list)
    text_slots: list[TextSlot] = Field(default_factory=list)
    logo_slot: LogoPlaceholder | None = None
