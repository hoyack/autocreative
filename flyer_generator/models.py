"""Pydantic v2 data contracts for all cross-stage data."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from flyer_generator.zones import ZoneCoord, ZoneName

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class EventInput(BaseModel):
    """Structured event data — the pipeline's primary input."""

    title: str = Field(max_length=120)
    date: str = Field(max_length=120)
    time: str = Field(max_length=120)
    location_name: str = Field(max_length=120)
    location_address: str = Field(max_length=120)
    fees: str = Field(max_length=120)
    org: str = Field(max_length=120)
    url: str | None = None
    style_concept: str = Field(max_length=120)
    style_preset: str = Field(max_length=120)
    color_accent: str = "#F59E0B"

    @field_validator("color_accent")
    @classmethod
    def _validate_hex_color(cls, v: str) -> str:
        if not _HEX_COLOR_RE.match(v):
            msg = f"color_accent must be a 6-digit hex color (e.g. #F59E0B), got {v!r}"
            raise ValueError(msg)
        return v


class ComfyJob(BaseModel):
    """Tracks a single ComfyCloud job submission."""

    prompt_id: str
    submitted_at: datetime
    positive_prompt: str
    negative_prompt: str
    seed: int
    attempt_number: int


class GeneratedBackground(BaseModel):
    """Raw background image from ComfyCloud after upscale."""

    image_bytes: bytes
    source_dimensions: tuple[int, int]
    final_dimensions: tuple[int, int]
    comfy_job: ComfyJob


class LayoutZones(BaseModel):
    """Zone assignments from vision evaluation."""

    title: ZoneName
    details: ZoneName
    fee_badge: ZoneName
    org_credit: ZoneName = "BOTTOM_CENTER"


class VisionVerdict(BaseModel):
    """Claude vision evaluation result."""

    approved: bool
    confidence: float = Field(ge=0.0, le=1.0)
    rejection_reasons: list[str] = Field(default_factory=list)
    refinement_hint: str = ""
    zones: LayoutZones | None = None
    text_color: Literal["white", "dark"] = "white"
    mood_tags: list[str] = Field(default_factory=list)
    raw_response: str = Field(max_length=500)

    @model_validator(mode="after")
    def _zones_required_when_approved(self) -> VisionVerdict:
        if self.approved and self.zones is None:
            msg = "zones must be provided when approved=True"
            raise ValueError(msg)
        return self


class ResolvedLayout(BaseModel):
    """Pixel-resolved zone coordinates for SVG composition."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    title: ZoneCoord
    details: ZoneCoord
    fee_badge: ZoneCoord
    org_credit: ZoneCoord


class FlyerOutput(BaseModel):
    """Final flyer output with metadata."""

    png_bytes: bytes
    dimensions: tuple[int, int]
    file_size_kb: int
    event_title: str
    attempts_used: int
    final_vision_verdict: VisionVerdict
    zones_used: LayoutZones
    trace_id: str

    def save(self, path: Path) -> None:
        """Write the flyer PNG to disk, creating parent directories if needed."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.png_bytes)
