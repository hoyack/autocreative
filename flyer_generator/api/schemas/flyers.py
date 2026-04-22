"""POST /api/v1/flyers request schema — wraps EventInput."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from flyer_generator.models import EventInput

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class FlyerCreateRequest(BaseModel):
    """Body of POST /api/v1/flyers.

    Re-uses EventInput verbatim (no field-by-field redefinition). Adds API-layer
    options: optional brand-kit slug, optional accent override, optional max
    background retry cap.
    """

    model_config = ConfigDict(extra="forbid")

    event: EventInput
    preset: str = Field(min_length=1, max_length=64)
    brand_kit_slug: str | None = Field(default=None, max_length=64)
    accent: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    max_bg_attempts: int | None = Field(default=None, ge=1, le=10)

    @field_validator("brand_kit_slug")
    @classmethod
    def _validate_slug(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not _SLUG_RE.match(v):
            raise ValueError("brand_kit_slug must match ^[a-z0-9][a-z0-9-]*$")
        return v
