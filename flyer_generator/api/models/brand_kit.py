"""BrandKitRecord — DB metadata for a .brand-kits/<slug>/ directory."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from flyer_generator.api.models.base import Base, utcnow


class BrandKitRecord(Base):
    """DB reflection of ``.brand-kits/<slug>/brand.json``.

    Actual kit files (palette JSON, logos, screenshots) remain on disk.
    This row indexes by slug and caches the scraped payload as JSON so the
    ``GET /brand-kits`` list endpoint can return summaries without reading
    every ``brand.json`` from disk.
    """

    __tablename__ = "brand_kits"

    slug: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    # Full BrandKit.model_dump(mode="json") payload; canonical source is disk,
    # this column is a cache for list/detail routes.
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
