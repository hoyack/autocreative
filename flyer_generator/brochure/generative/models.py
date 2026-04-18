"""Pydantic models for the generative brochure pipeline (stages 1-5 of v2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from flyer_generator.brochure.models import validate_hex_color

PanelRole = Literal["cover", "feature", "detail", "cta"]
TargetLength = Literal["short", "medium", "long"]
CoverTreatment = Literal["image_full", "image_half_shapes", "shapes_only"]
ShapeDensity = Literal["sparse", "medium", "dense"]
AccentPlacement = Literal["top_rule", "side_band", "corner_block"]
LayoutTemplateName = Literal[
    "editorial",
    "minimalist",
    "playful",
    "gallery_strip",
    "quote_driven",
    "spotlight",
]


class BrochurePrompt(BaseModel):
    """User-facing input for prompt-driven generation."""

    model_config = ConfigDict(extra="forbid")

    prompt: str
    style_preset: str | None = None
    audience: str | None = None
    color_accent: str | None = None
    target_length: TargetLength = "medium"

    @field_validator("color_accent")
    @classmethod
    def _validate_accent(cls, v: str | None) -> str | None:
        return validate_hex_color(v) if v is not None else None


class SectionSpec(BaseModel):
    """Outline-level section description produced by stage 1 (outline)."""

    model_config = ConfigDict(extra="forbid")

    heading: str
    body_brief: str = Field(description="one-sentence direction for stage 2")
    image_hint: str | None = None
    panel_role: PanelRole
    cover_image_concept: str | None = Field(
        default=None,
        description=(
            "Cover-section only: concrete visual concept for the hero image "
            "(what to render, not how to describe it in copy). Ignored on "
            "non-cover sections."
        ),
    )


class BrochureOutline(BaseModel):
    """Stage 1 output: the shape of the brochure before text is written."""

    model_config = ConfigDict(extra="forbid")

    sections: list[SectionSpec] = Field(min_length=2, max_length=5)
    tone: str
    cta_intent: str
    suggested_preset: str
    suggested_accent: str

    @field_validator("suggested_accent")
    @classmethod
    def _validate_suggested_accent(cls, v: str) -> str:
        return validate_hex_color(v)


class SectionText(BaseModel):
    """Stage 2 output: final prose for one section."""

    model_config = ConfigDict(extra="forbid")

    heading: str
    body: str
    image_hint: str | None = None


class LayoutChoice(BaseModel):
    """Stage 3 output: template + parameters that drive composition."""

    model_config = ConfigDict(extra="forbid")

    template: LayoutTemplateName
    shape_density: ShapeDensity
    accent_placement: AccentPlacement
    cover_treatment: CoverTreatment


class VerificationVerdict(BaseModel):
    """Stage 7 output: holistic 5-dimension rubric score + optional regen hint."""

    model_config = ConfigDict(extra="forbid")

    score: int = Field(ge=0, le=100)
    dimension_scores: dict[str, int]
    critique: str
    weakest_stage: Literal["outline", "text", "layout", "imagery", "compose"] | None = None
    iteration: int = 1
