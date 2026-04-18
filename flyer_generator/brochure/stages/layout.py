"""Pure-function tri-fold brochure panel geometry.

No I/O, no logging, no external deps beyond Pydantic (via the models module).
All measurements derived from the four named constants at module top.
"""

from __future__ import annotations

import math

from flyer_generator.brochure.models import (
    PanelRect,
    ResolvedBrochureLayout,
)

# --- Named constants (source of truth; D-05-12) ---

LETTER_LANDSCAPE_INCHES: tuple[float, float] = (11.0, 8.5)  # (width, height)
BLEED_INCHES: float = 0.125
SAFE_INCHES: float = 0.25
DPI: int = 300

# --- Derived pixel dimensions ---

TRIM_WIDTH_PX: int = int(LETTER_LANDSCAPE_INCHES[0] * DPI)   # 3300
TRIM_HEIGHT_PX: int = int(LETTER_LANDSCAPE_INCHES[1] * DPI)  # 2550

# Bleed is ceil-rounded to the next integer pixel so the bleed canvas is always
# at least as large as the nominal 0.125" margin on every side (conservative for
# print — slight overprint is safer than under).
BLEED_PX: int = int(math.ceil(BLEED_INCHES * DPI))  # 38

BLEED_CANVAS_WIDTH: int = TRIM_WIDTH_PX + 2 * BLEED_PX    # 3376
BLEED_CANVAS_HEIGHT: int = TRIM_HEIGHT_PX + 2 * BLEED_PX  # 2626

SAFE_PX: int = int(SAFE_INCHES * DPI)  # 75

PANEL_WIDTH_PX: int = TRIM_WIDTH_PX // 3  # 1100 (equal-width panels; D-05-13)

# Crop marks sit this many pixels outside each trim corner, in the bleed area.
CROP_MARK_INSET_PX: int = 10


# --- Helpers ---

def _build_panel(
    *,
    name: str,
    index: int,
    sheet: str,
    trim_x: int,
) -> PanelRect:
    """Build a PanelRect for a given panel position on a sheet.

    `trim_x` is the panel's x-origin within the trim area (0, 1100, or 2200).
    `trim_y` is always 0 because all panels span the full sheet height.
    Bleed extensions are added only on sheet-edge sides (first and last panels).
    """
    trim_rect = (
        BLEED_PX + trim_x,
        BLEED_PX,
        PANEL_WIDTH_PX,
        TRIM_HEIGHT_PX,
    )

    # Bleed_rect extends to sheet edges where the panel touches them.
    left_touches_edge = trim_x == 0
    right_touches_edge = trim_x == 2 * PANEL_WIDTH_PX

    bleed_x = 0 if left_touches_edge else trim_rect[0]
    bleed_w = (trim_rect[0] - bleed_x) + trim_rect[2]
    if right_touches_edge:
        bleed_w += BLEED_PX
    # Top/bottom always touch the sheet edge for panels (tri-fold spans full
    # sheet height), so y extends all the way from 0 to canvas height.
    bleed_rect = (bleed_x, 0, bleed_w, BLEED_CANVAS_HEIGHT)

    safe_rect = (
        trim_rect[0] + SAFE_PX,
        trim_rect[1] + SAFE_PX,
        PANEL_WIDTH_PX - 2 * SAFE_PX,
        TRIM_HEIGHT_PX - 2 * SAFE_PX,
    )

    return PanelRect(
        name=name,  # type: ignore[arg-type]
        index=index,
        sheet=sheet,  # type: ignore[arg-type]
        bleed_rect=bleed_rect,
        trim_rect=trim_rect,
        safe_rect=safe_rect,
    )


def _crop_marks_for_sheet() -> list[tuple[int, int]]:
    """Four crop-mark anchor points per sheet, placed in the bleed area just
    outside each trim corner.
    """
    trim_left = BLEED_PX
    trim_top = BLEED_PX
    trim_right = BLEED_PX + TRIM_WIDTH_PX
    trim_bottom = BLEED_PX + TRIM_HEIGHT_PX
    d = CROP_MARK_INSET_PX
    return [
        (trim_left - d, trim_top - d),        # top-left
        (trim_right + d, trim_top - d),       # top-right
        (trim_left - d, trim_bottom + d),     # bottom-left
        (trim_right + d, trim_bottom + d),    # bottom-right
    ]


def compute_panel_layout() -> ResolvedBrochureLayout:
    """Compute full panel geometry for a US Letter landscape tri-fold brochure.

    Deterministic: takes no arguments; all dimensions come from module constants.
    Returns three outside panels, three inside panels, two fold lines per sheet,
    and eight crop-mark anchor points (four per sheet).

    Panel order (D-05-14):
      outside: back_cover (6), front_cover (1), tuck_flap (2)  (left→right)
      inside:  inner_left (3), inner_center (4), inner_right (5)  (left→right)
    """
    outside_panels = [
        _build_panel(name="back_cover", index=6, sheet="outside", trim_x=0),
        _build_panel(name="front_cover", index=1, sheet="outside", trim_x=PANEL_WIDTH_PX),
        _build_panel(name="tuck_flap", index=2, sheet="outside", trim_x=2 * PANEL_WIDTH_PX),
    ]
    inside_panels = [
        _build_panel(name="inner_left", index=3, sheet="inside", trim_x=0),
        _build_panel(name="inner_center", index=4, sheet="inside", trim_x=PANEL_WIDTH_PX),
        _build_panel(name="inner_right", index=5, sheet="inside", trim_x=2 * PANEL_WIDTH_PX),
    ]

    # Fold lines sit at the panel boundaries in trim space, translated into the
    # bleed canvas coordinate system.
    fold_positions = [BLEED_PX + PANEL_WIDTH_PX, BLEED_PX + 2 * PANEL_WIDTH_PX]

    # Four corner crop marks per sheet → 8 total.
    crop_marks = _crop_marks_for_sheet() + _crop_marks_for_sheet()

    return ResolvedBrochureLayout(
        outside_panels=outside_panels,
        inside_panels=inside_panels,
        fold_lines_outside=fold_positions,
        fold_lines_inside=fold_positions,
        crop_marks=crop_marks,
    )
