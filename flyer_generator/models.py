"""Pydantic v2 data contracts for all cross-stage data."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from flyer_generator.zones import ZoneCoord, ZoneName

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class WorkflowConfig(BaseModel):
    """Metadata + node graph for a ComfyUI workflow."""

    name: str
    description: str = ""
    latent_dimensions: tuple[int, int]
    injection_points: dict[str, str]  # role -> node_id
    workflow: dict  # raw ComfyUI node graph (meta stripped)


class FlyerInput(BaseModel):
    """Structured flyer input — event-or-info.

    All event-specific fields (date, time, location_*, fees) are optional;
    `subtype` drives which are expected at the worker/vision/composer layer.
    Vision prompt, composer, and template resolver branch on `subtype` to
    avoid rendering empty event fields for info flyers.
    """

    title: str = Field(max_length=120)
    subtype: Literal["event", "info"] = "event"
    # Event-only — optional at the model layer; worker/vision prompt validate
    # presence when subtype == "event".
    date: str | None = Field(default=None, max_length=120)
    time: str | None = Field(default=None, max_length=120)
    location_name: str | None = Field(default=None, max_length=120)
    location_address: str | None = Field(default=None, max_length=120)
    fees: str | None = Field(default=None, max_length=120)
    # Info-only
    description: str | None = Field(default=None, max_length=600)
    call_to_action: str | None = Field(default=None, max_length=120)
    # Shared
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


# Backward-compat alias. Deprecated — use FlyerInput in new code.
# Kept through at least Phase 23 so external callers aren't broken mid-milestone.
EventInput = FlyerInput


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
    """Zone assignments from vision evaluation.

    For event-subtype flyers, `details` and `fee_badge` are populated.
    For info-subtype flyers, both are None (vision prompt omits those
    zones; composer skips their rendering).
    """

    title: ZoneName
    details: ZoneName | None = None
    fee_badge: ZoneName | None = None
    org_credit: ZoneName = "BOTTOM_CENTER"


class VisionVerdict(BaseModel):
    """Vision evaluation result.

    Zones are flyer-specific: the flyer pipeline requires them when approved
    (enforced by VisionEvaluator in flyer mode). For other domains (e.g.
    brochure cover evaluation), zones may be None even when approved — the
    caller is responsible for domain-specific validity.
    """

    approved: bool
    confidence: float = Field(ge=0.0, le=1.0)
    rejection_reasons: list[str] = Field(default_factory=list)
    refinement_hint: str = ""
    zones: LayoutZones | None = None
    text_color: Literal["white", "dark"] = "white"
    mood_tags: list[str] = Field(default_factory=list)
    raw_response: str = Field(max_length=4000)


class ResolvedLayout(BaseModel):
    """Pixel-resolved zone coordinates for SVG composition.

    `details` and `fee_badge` are None for info-subtype flyers; the composer
    (Plan 03) performs None checks before rendering those blocks.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    title: ZoneCoord
    details: ZoneCoord | None = None
    fee_badge: ZoneCoord | None = None
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
