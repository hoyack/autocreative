"""Pydantic v2 data contracts for the brochure generator.

Mirrors the patterns used by flyer_generator.models (BaseModel + ConfigDict +
Field + field_validator). Hex color validation regex is re-declared locally per
decision D-05-09 (do not import private symbols from the flyer module).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, field_validator

from flyer_generator.models import VisionVerdict

if TYPE_CHECKING:
    from flyer_generator.brochure.generative.models import VerificationVerdict

PanelName = Literal[
    "back_cover",
    "front_cover",
    "tuck_flap",
    "inner_left",
    "inner_center",
    "inner_right",
]
SheetName = Literal["outside", "inside"]

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
    verification: "VerificationVerdict | None" = None
    lint_report: dict[str, Any] | None = None
    trace_id: str = ""

    def save(self, directory: Path) -> None:
        """Write front PNG, back PNG, and print PDF into the given directory."""
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "brochure_front.png").write_bytes(self.front_png_bytes)
        (directory / "brochure_back.png").write_bytes(self.back_png_bytes)
        (directory / "brochure_print.pdf").write_bytes(self.pdf_bytes)


class PanelRect(BaseModel):
    """Geometry for a single tri-fold panel on the bleed canvas.

    All coordinates are integer pixels in bleed-canvas space (origin top-left).
    trim_rect is the visible printed area; safe_rect is the text-safe inset;
    bleed_rect extends outward to the canvas edge on sheet-edge sides.
    """

    model_config = ConfigDict(extra="forbid")

    name: PanelName
    index: int = Field(ge=1, le=6)
    sheet: SheetName
    bleed_rect: tuple[int, int, int, int]  # (x, y, w, h)
    trim_rect: tuple[int, int, int, int]
    safe_rect: tuple[int, int, int, int]


class ResolvedBrochureLayout(BaseModel):
    """Full panel-level geometry for a tri-fold brochure.

    Contains three panels per sheet (outside + inside), fold-line x-coordinates
    for each sheet, and eight crop-mark anchor points (four per sheet) positioned
    in the bleed area just outside each trim corner.
    """

    model_config = ConfigDict(extra="forbid")

    outside_panels: list[PanelRect] = Field(min_length=3, max_length=3)
    inside_panels: list[PanelRect] = Field(min_length=3, max_length=3)
    fold_lines_outside: list[int] = Field(min_length=2, max_length=2)
    fold_lines_inside: list[int] = Field(min_length=2, max_length=2)
    crop_marks: list[tuple[int, int]] = Field(min_length=8, max_length=8)


# Deferred resolution of the `VerificationVerdict` forward-reference on
# BrochureOutput. Imported here (module end) to avoid a circular import at
# top-of-file — `generative.models` pulls `validate_hex_color` from this module.
from flyer_generator.brochure.generative.models import (  # noqa: E402
    VerificationVerdict as _VerificationVerdict,
)

BrochureOutput.model_rebuild(_types_namespace={"VerificationVerdict": _VerificationVerdict})
