"""JobRecord — polymorphic row tracking any async creative generation."""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum as SAEnum, String
from sqlalchemy.orm import Mapped, mapped_column

from flyer_generator.api.models.base import Base, utcnow


class JobKind(str, enum.Enum):
    BRAND_KIT = "brand_kit"
    FLYER = "flyer"
    BROCHURE = "brochure"
    POSTCARD = "postcard"
    SOCIAL_POST = "social_post"
    SOCIAL_CAMPAIGN = "social_campaign"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobRecord(Base):
    """Polymorphic async-job tracking row.

    ``id`` is a ULID supplied by the route handler at enqueue time so the 202
    response can echo it synchronously.  ``result_ref`` points at a
    ``RenderRecord.id`` for single-artifact jobs or is NULL for campaigns
    (whose renders are reached via ``CampaignRecord.posts``).
    """

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    kind: Mapped[JobKind] = mapped_column(SAEnum(JobKind, name="jobkind"), index=True, nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, name="jobstatus"), index=True, default=JobStatus.QUEUED, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result_ref: Mapped[str | None] = mapped_column(String(26), nullable=True, index=True)
    input_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
