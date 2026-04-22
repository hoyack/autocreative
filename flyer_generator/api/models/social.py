"""CampaignRecord + PostRecord — Phase 19 social subsystem DB layer."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from flyer_generator.api.models.base import Base, new_ulid, utcnow
from flyer_generator.api.models.render import RenderRecord


class CampaignRecord(Base):
    """A set of Posts generated from a single topic across multiple platforms."""

    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_ulid)
    topic: Mapped[str] = mapped_column(String(400), nullable=False)
    intent: Mapped[str] = mapped_column(String(40), nullable=False)
    brand_kit_slug: Mapped[str | None] = mapped_column(
        ForeignKey("brand_kits.slug", ondelete="SET NULL"), nullable=True, index=True
    )
    # List[str] of platforms, serialized as JSON for SQLite+Postgres compat.
    platforms: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # Campaign.model_dump(mode="json") summary (per-post details in PostRecord).
    summary_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    posts: Mapped[list["PostRecord"]] = relationship(
        "PostRecord", back_populates="campaign", cascade="all, delete-orphan",
        lazy="selectin",
    )


class PostRecord(Base):
    """A single social post (platform-specific copy + optional image)."""

    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_ulid)
    platform: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    intent: Mapped[str] = mapped_column(String(40), nullable=False)
    topic: Mapped[str] = mapped_column(String(400), nullable=False)
    brand_kit_slug: Mapped[str | None] = mapped_column(
        ForeignKey("brand_kits.slug", ondelete="SET NULL"), nullable=True, index=True
    )
    campaign_id: Mapped[str | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # Post.model_dump(mode="json") — copy, hashtags, validation, audit, etc.
    post_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    render_id: Mapped[str | None] = mapped_column(
        ForeignKey("renders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    campaign: Mapped[CampaignRecord | None] = relationship(
        "CampaignRecord", back_populates="posts", lazy="joined"
    )
    render: Mapped[RenderRecord | None] = relationship(
        "RenderRecord", foreign_keys=[render_id], lazy="joined"
    )
