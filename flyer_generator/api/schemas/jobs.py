"""Request/response schemas for job creation + detail."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from flyer_generator.api.models.job import JobKind, JobStatus


class JobCreated(BaseModel):
    """Response body for every async-job-starting endpoint (202 Accepted)."""

    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=26, max_length=26, description="ULID job id")


class ResultLink(BaseModel):
    """One entry in a campaign's `result_ref` list."""

    model_config = ConfigDict(extra="forbid")

    platform: str
    url: str  # absolute API path, e.g. "/api/v1/renders/<ulid>/image"


class JobDetail(BaseModel):
    """GET /api/v1/jobs/{id} response."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: JobKind
    status: JobStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_detail: dict | None = None
    # Single-render jobs: a string URL path.
    # Campaigns: a list of {platform, url} entries.
    # Queued / running: None.
    result_ref: str | list[ResultLink] | None = None
    created_at: datetime


class PaginatedJobs(BaseModel):
    """Response for ``GET /api/v1/jobs?limit=&offset=&kind=&status=``.

    Mirrors :class:`PaginatedBrandKits`. Items reuse the existing
    :class:`JobDetail` schema so clients can share a single row type between
    the list view and the single-job poll.

    Per Plan 21-10 + 21-RESEARCH.md Open Q1 (cheap path): campaigns whose
    detail route would fuse a ``list[ResultLink]`` instead have
    ``result_ref=None`` in the list view — callers fetch the full fuse from
    ``GET /api/v1/jobs/{id}``.
    """

    model_config = ConfigDict(extra="forbid")

    items: list[JobDetail]
    total: int
    limit: int
    offset: int
