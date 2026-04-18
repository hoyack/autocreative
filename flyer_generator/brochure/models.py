"""Pydantic v2 data contracts for the brochure generator.

Mirrors the patterns used by flyer_generator.models (BaseModel + ConfigDict +
Field + field_validator). Hex color validation regex is re-declared locally per
decision D-05-09 (do not import private symbols from the flyer module).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from flyer_generator.models import VisionVerdict

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def validate_hex_color(v: str) -> str:
    """Raise ValueError if v is not a 6-digit hex color like '#F59E0B'."""
    if not _HEX_COLOR_RE.match(v):
        msg = f"color_accent must be a 6-digit hex color (e.g. #F59E0B), got {v!r}"
        raise ValueError(msg)
    return v


class ContactBlock(BaseModel):
    """Optional contact block used on the back cover panel."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    phone: str | None = None
    email: str | None = None
    url: str | None = None
    address: str | None = None


class BrochureSection(BaseModel):
    """One content section rendered into an inner panel or the tuck flap."""

    model_config = ConfigDict(extra="forbid")

    heading: str
    body: str
    icon_hint: str | None = None


class BrochureBackPanel(BaseModel):
    """Back-cover panel content. Template selected by `kind`."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["cta", "bio", "map_stub", "contact"]
    content: str


class BrochureInput(BaseModel):
    """Structured brochure data — the brochure pipeline's primary input."""

    model_config = ConfigDict(extra="forbid")

    title: str
    subtitle: str | None = None
    hero_concept: str
    style_preset: str
    color_accent: str = "#F59E0B"
    org: str
    contact: ContactBlock | None = None
    sections: list[BrochureSection] = Field(min_length=2, max_length=5)
    back_panel: BrochureBackPanel | None = None

    @field_validator("color_accent")
    @classmethod
    def _validate_color_accent(cls, v: str) -> str:
        return validate_hex_color(v)


class BrochureOutput(BaseModel):
    """Final brochure output with metadata.

    Phase 5 leaves the byte fields as empty-allowed placeholders so the model is
    importable before phases 7/8 populate them. Dimensions default to the trim
    canvas (3300x2550); the PDF is sized to the bleed canvas (3375x2625) but
    that's an implementation detail of phase 8.
    """

    model_config = ConfigDict(extra="forbid")

    front_png_bytes: bytes = b""
    back_png_bytes: bytes = b""
    pdf_bytes: bytes = b""
    dimensions: tuple[int, int] = (3300, 2550)
    attempts_used: int = 0
    hero_vision_verdict: VisionVerdict | None = None
    trace_id: str = ""

    def save(self, directory: Path) -> None:
        """Write front PNG, back PNG, and print PDF into the given directory."""
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "brochure_front.png").write_bytes(self.front_png_bytes)
        (directory / "brochure_back.png").write_bytes(self.back_png_bytes)
        (directory / "brochure_print.pdf").write_bytes(self.pdf_bytes)
