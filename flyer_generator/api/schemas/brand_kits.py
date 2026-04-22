"""Request/response schemas for brand-kit routes."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator

from flyer_generator.brand_kit.models import BrandKit

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class BrandKitFetchRequest(BaseModel):
    """Body of POST /api/v1/brand-kits/fetch."""

    model_config = ConfigDict(extra="forbid")

    url: AnyHttpUrl
    slug: str = Field(min_length=1, max_length=64)

    @field_validator("slug")
    @classmethod
    def _validate_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError("slug must match ^[a-z0-9][a-z0-9-]*$")
        return v


class BrandKitSummary(BaseModel):
    """Entry in GET /api/v1/brand-kits list."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    name: str | None = None
    source_url: str | None = None
    scraped_at: datetime


class PaginatedBrandKits(BaseModel):
    """Response for GET /api/v1/brand-kits?limit=&offset=."""

    model_config = ConfigDict(extra="forbid")

    items: list[BrandKitSummary]
    total: int
    limit: int
    offset: int


class BrandKitDetail(BaseModel):
    """Response for GET /api/v1/brand-kits/{slug}.

    Wraps the existing :class:`BrandKit` Pydantic model (which already has all
    palette / typography / logos / voice fields). Exposed as-is — no reshape.
    """

    model_config = ConfigDict(extra="forbid")

    slug: str
    record_created_at: datetime
    # Nested brand kit payload (may include logo file paths, palette JSON, etc.)
    brand_kit: BrandKit
