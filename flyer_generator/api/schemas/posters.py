"""POST /api/v1/posters request schema.

Phase 24 PO-01 (poster primitive). Mirrors the postcard schema shape but
swaps ``address_block`` + ``body`` for poster-specific fields:

- ``size: Literal["18x24", "24x36", "27x40"]`` — locked enum (T-24-07)
- ``style_preset`` — flyer-style preset name
- ``subheading`` / ``cta_text`` — optional secondary copy
- single-canvas (no recipient block — posters are not direct mail)

Locked size mapping (300 DPI portrait, see CONTEXT D-XX):
  "18x24" → 5400×7200, "24x36" → 7200×10800, "27x40" → 8100×12000.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# Locked size literals per CONTEXT D-XX. Exactly 3 values — adding more
# (ANSI/ISO sizes) is deferred per CONTEXT.deferred. Anything outside this
# set returns 422 from the Pydantic layer (T-24-07 mitigation).
PosterSize = Literal["18x24", "24x36", "27x40"]


class PosterCreateRequest(BaseModel):
    """Body of POST /api/v1/posters (PO-01)."""

    model_config = ConfigDict(extra="forbid")

    headline: str = Field(min_length=1, max_length=120)
    subheading: str | None = Field(default=None, max_length=200)
    cta_text: str | None = Field(default=None, max_length=120)
    image_hint: str | None = Field(default=None, max_length=500)
    brand_kit_slug: str | None = Field(default=None, max_length=64)
    style_preset: str = Field(min_length=1, max_length=64)
    template: str = Field(min_length=1, max_length=64)
    size: PosterSize

    @field_validator("brand_kit_slug")
    @classmethod
    def _validate_slug(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not _SLUG_RE.match(v):
            raise ValueError("brand_kit_slug must match ^[a-z0-9][a-z0-9-]*$")
        return v
