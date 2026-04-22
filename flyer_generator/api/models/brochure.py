"""BrochureRecord — one generated brochure (front PNG + back PNG + print PDF)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flyer_generator.api.models.base import Base, new_ulid, utcnow
from flyer_generator.api.models.render import RenderRecord


class BrochureRecord(Base):
    __tablename__ = "brochures"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_ulid)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    template: Mapped[str] = mapped_column(String(64), nullable=False)
    brand_kit_slug: Mapped[str | None] = mapped_column(
        ForeignKey("brand_kits.slug", ondelete="SET NULL"), nullable=True, index=True
    )
    # BrochureContent.model_dump(mode="json") plus workflow/style_preset knobs.
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
