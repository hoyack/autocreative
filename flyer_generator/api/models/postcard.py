"""PostcardRecord — one generated postcard (front PNG + back PNG + print PDF).

Per PC-02 (Phase 23): id == JobRecord.id (parallel-id pattern from 21-07).
The route handler computes the ULID, writes JobRecord first, then the worker
writes ``PostcardRecord(id=job_id, ...)``. NO ``default=new_ulid`` on ``id``
so the parallel-id contract cannot be silently violated by an auto-default.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flyer_generator.api.models.base import Base, utcnow
from flyer_generator.api.models.render import RenderRecord


class PostcardRecord(Base):
    __tablename__ = "postcards"

    # Parallel-id (PC-02): id == JobRecord.id, supplied by the route handler at
    # enqueue time. NO ``default=new_ulid`` — the worker MUST set ``id`` from
    # the ``job_id`` task kwarg explicitly (otherwise the FE's
    # ``GET /postcards/{job_id}`` lookup breaks).
    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    template: Mapped[str] = mapped_column(String(64), nullable=False)
    brand_kit_slug: Mapped[str | None] = mapped_column(
        ForeignKey("brand_kits.slug", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # PostcardCreateRequest.model_dump(mode="json") — preserves headline, body,
    # image_hint, address_block, etc. for audit/debug.
    content_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    render_front_id: Mapped[str | None] = mapped_column(
        ForeignKey("renders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    render_back_id: Mapped[str | None] = mapped_column(
        ForeignKey("renders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    render_pdf_id: Mapped[str | None] = mapped_column(
        ForeignKey("renders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    render_front: Mapped[RenderRecord | None] = relationship(
        "RenderRecord", foreign_keys=[render_front_id], lazy="joined"
    )
    render_back: Mapped[RenderRecord | None] = relationship(
        "RenderRecord", foreign_keys=[render_back_id], lazy="joined"
    )
    render_pdf: Mapped[RenderRecord | None] = relationship(
        "RenderRecord", foreign_keys=[render_pdf_id], lazy="joined"
    )
