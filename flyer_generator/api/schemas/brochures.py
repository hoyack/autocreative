"""POST /api/v1/brochures request schema — wraps BrochureContent."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from flyer_generator.brochure.schema_renderer.content_model import BrochureContent

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class BrochureCreateRequest(BaseModel):
    """Body of POST /api/v1/brochures."""

    model_config = ConfigDict(extra="forbid")

    content: BrochureContent
    template: str = Field(min_length=1, max_length=64)
    brand_kit_slug: str | None = Field(default=None, max_length=64)
    generate_images: bool = True
    workflow: str = "turbo_landscape"
    style_preset: str = "photorealistic"

    @field_validator("brand_kit_slug")
    @classmethod
    def _validate_slug(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not _SLUG_RE.match(v):
            raise ValueError("brand_kit_slug must match ^[a-z0-9][a-z0-9-]*$")
        return v
