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
