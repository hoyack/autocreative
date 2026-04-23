"""Render summary — lightweight read-only shape for list endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RenderSummary(BaseModel):
    """Metadata row for GET /renders/{id} (no file bytes here)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str
    comfy_job_id: str | None = None
    created_at: datetime


class PaginatedRenders(BaseModel):
    """Response for ``GET /api/v1/renders?limit=&offset=&kind=&since=``.

    Mirrors :class:`PaginatedBrandKits` / :class:`PaginatedJobs`. Items reuse
    :class:`RenderSummary` — file bytes are NOT inlined; clients build the
    download URL as ``/api/v1/renders/{id}/image`` via the existing
    :func:`flyer_generator.api.routes.renders.get_render_image` route.
    """

    model_config = ConfigDict(extra="forbid")

    items: list[RenderSummary]
    total: int
    limit: int
    offset: int
