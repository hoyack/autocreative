"""FlyerRecord — one generated flyer."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flyer_generator.api.models.base import Base, new_ulid, utcnow
from flyer_generator.api.models.render import RenderRecord


class FlyerRecord(Base):
    __tablename__ = "flyers"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_ulid)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    preset: Mapped[str] = mapped_column(String(64), nullable=False)
    brand_kit_slug: Mapped[str | None] = mapped_column(
        ForeignKey("brand_kits.slug", ondelete="SET NULL"), nullable=True, index=True
    )
    # EventInput.model_dump(mode="json") + {preset, brand_kit_slug, accent, max_bg_attempts}
    event_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    render_id: Mapped[str | None] = mapped_column(
        ForeignKey("renders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    render: Mapped[RenderRecord | None] = relationship("RenderRecord", lazy="joined")
