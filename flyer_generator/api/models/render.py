"""RenderRecord — pointer to a single on-disk artifact (PNG / PDF).

Actual bytes live on disk under ``settings.artifact_root_flyer``,
``settings.artifact_root_brochure``, ``settings.brand_kits_dir``, or
``settings.social_campaigns_dir``.  This row is metadata + path only.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from flyer_generator.api.models.base import Base, new_ulid, utcnow


class RenderRecord(Base):
    __tablename__ = "renders"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_ulid)
    kind: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    # Valid kinds: "flyer_final", "brochure_front", "brochure_back",
    # "brochure_pdf", "social_post_image", "brand_kit_logo"
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    comfy_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vision_verdict: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
