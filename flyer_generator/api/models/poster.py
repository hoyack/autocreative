"""PosterRecord — one generated poster (single PNG artifact, larger canvas).

Per PO-XX (Phase 24): id == JobRecord.id (parallel-id pattern from 21-07,
mirrored by postcards 23-02). The route handler computes the ULID, writes
JobRecord first, then the worker writes ``PosterRecord(id=job_id, ...)``.
NO ``default=new_ulid`` on ``id`` so the parallel-id contract cannot be
silently violated by an auto-default (T-24-11 mitigation).

Posters differ from postcards in two ways:
- Single ``render_id`` (not 3) — single PNG output, no front/back/pdf split.
- ``size`` column — stores the locked literal ("18x24" / "24x36" / "27x40")
  for FE display + audit; canvas-dim mapping lives in the worker.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flyer_generator.api.models.base import Base, utcnow
from flyer_generator.api.models.render import RenderRecord


class PosterRecord(Base):
    __tablename__ = "posters"

    # Parallel-id (PO-XX): id == JobRecord.id, supplied by the route handler at
    # enqueue time. NO ``default=new_ulid`` — the worker MUST set ``id`` from
    # the ``job_id`` task kwarg explicitly (otherwise the FE's
    # ``GET /posters/{job_id}`` lookup breaks).
    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    template: Mapped[str] = mapped_column(String(64), nullable=False)
    # Stored as the size literal (e.g. "18x24") for FE display + audit. The
    # canvas-dim mapping (300 DPI) lives in the worker, not here.
    size: Mapped[str] = mapped_column(String(8), nullable=False)
    brand_kit_slug: Mapped[str | None] = mapped_column(
        ForeignKey("brand_kits.slug", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # PosterCreateRequest.model_dump(mode="json") — preserves headline,
    # subheading, cta_text, image_hint, style_preset, etc. for audit/debug.
    content_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # Single PNG render — no front/back/pdf split.
    render_id: Mapped[str | None] = mapped_column(
        ForeignKey("renders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    render: Mapped[RenderRecord | None] = relationship(
        "RenderRecord", foreign_keys=[render_id], lazy="joined"
    )
