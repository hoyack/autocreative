"""Pydantic v2 data contracts for the brand-kit subsystem.

Every model uses `ConfigDict(extra="forbid")` so malformed `brand.json`
files or stale cached kits fail at load time. Optional nested models
(palette, typography, voice, photography) accept `None` so partially
populated scrapes round-trip without falling over.

Hex colors are normalized + validated via `validate_hex_color` (imported
from `flyer_generator.brochure.models`) — the same helper the schema
renderer already uses. The field_validator on `ColorUsage.hex` also
uppercases the hex body so round-tripped kits are stable across loads.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from flyer_generator.brochure.models import validate_hex_color


class ColorUsage(BaseModel):
    """A single color with an optional semantic usage hint."""

    model_config = ConfigDict(extra="forbid")

    hex: str
    usage_hint: str | None = None

    @field_validator("hex")
    @classmethod
    def _validate_hex(cls, v: str) -> str:
        # Validate first (raises ValueError on bad input), then normalize
        # case so stored hexes are stable across reloads.
        validated = validate_hex_color(v)
        return "#" + validated[1:].upper()


class BrandPalette(BaseModel):
    """Extracted brand color palette: five named roles + an extras dict."""

    model_config = ConfigDict(extra="forbid")

    primary: ColorUsage
    secondary: ColorUsage
    accent: ColorUsage
    neutral_dark: ColorUsage
    neutral_light: ColorUsage
    extras: dict[str, ColorUsage] = Field(default_factory=dict)


class BrandTypography(BaseModel):
    """Heading + body font stacks and a generic size scale.

    `size_scale` keys are role tokens (`hero`, `display`, `heading`,
    `subheading`, `body`, `caption`). The applier maps these to the
    template's specific size fields.
    """

    model_config = ConfigDict(extra="forbid")

    heading_family: str
    body_family: str
    size_scale: dict[str, int] = Field(default_factory=dict)
    font_sources: list[str] = Field(default_factory=list)


class BrandLogo(BaseModel):
    """A single logo asset (stored at kit_dir / path)."""

    model_config = ConfigDict(extra="forbid")

    path: str
    variant: Literal["primary", "mono_dark", "mono_light", "mark_only"]
    format: Literal["png", "jpg", "svg"]
    aspect_ratio: float = Field(gt=0.0)


class BrandVoice(BaseModel):
    """Optional brand voice hints (captured now, wired to text_gen later)."""

    model_config = ConfigDict(extra="forbid")

    tone: str
    example_phrases: list[str] = Field(default_factory=list)
    banned_words: list[str] = Field(default_factory=list)


class BrandPhotoHints(BaseModel):
    """Optional photography guidance."""

    model_config = ConfigDict(extra="forbid")

    preferred_style_preset: str | None = None
    color_grade_notes: str | None = None


class BrandKit(BaseModel):
    """Top-level brand kit. Optional nested models allow partial scrapes."""

    model_config = ConfigDict(extra="forbid")

    name: str
    source_url: str | None = None
    fetched_at: datetime
    palette: BrandPalette | None = None
    typography: BrandTypography | None = None
    logos: list[BrandLogo] = Field(default_factory=list)
    voice: BrandVoice | None = None
    photography: BrandPhotoHints | None = None
    source_artifacts: list[str] = Field(default_factory=list)
    size_multiplier: float = Field(default=1.0, gt=0.0, le=3.0)
