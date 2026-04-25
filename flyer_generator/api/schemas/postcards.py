"""POST /api/v1/postcards request schema + GET /api/v1/postcards/{id} response.

Phase 23 PC-01 + PC-03 (postcard primitive). Mirrors brochures.py shape but
flattens the request body — postcards do not wrap content in a sub-model
because the structure is small enough to live at the top level.
"""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class AddressBlock(BaseModel):
    """Optional recipient address rendered on the back panel.

    Per PC-03: a typographically precise block (recipient + street + single-line
    city/state/zip). All three fields are required when the block is supplied;
    the block itself is optional on the request.
    """

    model_config = ConfigDict(extra="forbid")

    recipient_name: str = Field(min_length=1, max_length=120)
    street: str = Field(min_length=1, max_length=120)
    city_state_zip: str = Field(min_length=1, max_length=120)


class PostcardCreateRequest(BaseModel):
    """Body of POST /api/v1/postcards (PC-01)."""

    model_config = ConfigDict(extra="forbid")

    headline: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=2000)
    image_hint: str | None = Field(default=None, max_length=500)
    brand_kit_slug: str | None = Field(default=None, max_length=64)
    template: str = Field(min_length=1, max_length=64)
    address_block: AddressBlock | None = None

    @field_validator("brand_kit_slug")
    @classmethod
    def _validate_slug(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not _SLUG_RE.match(v):
            raise ValueError("brand_kit_slug must match ^[a-z0-9][a-z0-9-]*$")
        return v


class PostcardDetail(BaseModel):
    """Response for GET /api/v1/postcards/{id} — all 3 artifacts.

    Mirrors BrochureDetail (Phase 21-07). The parallel-id pattern (PC-02)
    means id == job_id, so the FE can navigate from /jobs/{id} to
    /postcards/{id} without an extra lookup.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    template: str
    brand_kit_slug: str | None = None
    front_render_url: str | None = None  # /api/v1/renders/{id}/image
    back_render_url: str | None = None
    pdf_render_url: str | None = None
    created_at: datetime
