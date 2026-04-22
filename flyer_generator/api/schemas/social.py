"""Request schemas for social routes. PostBrief is reused verbatim — no wrapper."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from flyer_generator.social.models import Intent, Platform  # Literal aliases

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class PostCreateRequest(BaseModel):
    """Body of POST /api/v1/social/posts.

    Mirrors PostBrief fields but ADDS brand_kit_slug + style_preset at the
    API boundary so the task can resolve the kit + pick a Comfy workflow.
    """

    model_config = ConfigDict(extra="forbid")

    brand_kit_slug: str = Field(min_length=1, max_length=64)
    platform: Platform
    intent: Intent
    topic: str = Field(min_length=1, max_length=400)
    cta: str | None = Field(default=None, max_length=200)
    image_hint: str | None = Field(default=None, max_length=400)
    style_preset: str | None = Field(default=None, max_length=64)

    @field_validator("brand_kit_slug")
    @classmethod
    def _validate_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError("brand_kit_slug must match ^[a-z0-9][a-z0-9-]*$")
        return v


class CampaignCreateRequest(BaseModel):
    """Body of POST /api/v1/social/campaigns."""

    model_config = ConfigDict(extra="forbid")

    brand_kit_slug: str = Field(min_length=1, max_length=64)
    platforms: list[Platform] = Field(min_length=1, max_length=10)
    intent: Intent
    topic: str = Field(min_length=1, max_length=400)
    cta: str | None = Field(default=None, max_length=200)
    style_preset: str | None = Field(default=None, max_length=64)

    @field_validator("brand_kit_slug")
    @classmethod
    def _validate_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError("brand_kit_slug must match ^[a-z0-9][a-z0-9-]*$")
        return v
