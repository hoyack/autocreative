"""Tests for flyer_generator.brochure.stages.layout panel geometry.

Asserts: correct panel count/order, rects are ints, trim panels tile the trim
canvas exactly (no overlap, no gap), safe zones are 75 px inset on all sides,
fold lines are at thirds in trim-space, crop marks are in bleed (never inside
trim), determinism, and a forbidden-imports guard preventing anyone from
leaking heavy deps into this pure-math module.
"""

from __future__ import annotations

import inspect
import re

import pytest

from flyer_generator.brochure.models import (
    PanelRect,
    ResolvedBrochureLayout,
)
from flyer_generator.brochure.stages import layout as layout_mod
from flyer_generator.brochure.stages.layout import (
    BLEED_CANVAS_HEIGHT,
    BLEED_CANVAS_WIDTH,
    BLEED_PX,
    DPI,
    LETTER_LANDSCAPE_INCHES,
    PANEL_WIDTH_PX,
    SAFE_PX,
    TRIM_HEIGHT_PX,
    TRIM_WIDTH_PX,
    compute_panel_layout,
)


# ---------- Constants sanity ----------


def test_constants_match_letter_landscape_at_300_dpi() -> None:
    assert LETTER_LANDSCAPE_INCHES == (11.0, 8.5)
    assert DPI == 300
    assert TRIM_WIDTH_PX == 3300
    assert TRIM_HEIGHT_PX == 2550


def test_bleed_canvas_is_trim_plus_2_bleed_per_side() -> None:
    assert BLEED_PX == 38
    assert BLEED_CANVAS_WIDTH == TRIM_WIDTH_PX + 2 * BLEED_PX
    assert BLEED_CANVAS_HEIGHT == TRIM_HEIGHT_PX + 2 * BLEED_PX


def test_panel_width_and_safe_inset() -> None:
    assert PANEL_WIDTH_PX == 1100
    assert SAFE_PX == 75


# ---------- compute_panel_layout structure ----------


def test_compute_panel_layout_returns_resolved_layout() -> None:
    layout = compute_panel_layout()
    assert isinstance(layout, ResolvedBrochureLayout)


def test_layout_has_three_panels_per_sheet_in_correct_order() -> None:
    layout = compute_panel_layout()
    outside_names = [p.name for p in layout.outside_panels]
    outside_indices = [p.index for p in layout.outside_panels]
    inside_names = [p.name for p in layout.inside_panels]
    inside_indices = [p.index for p in layout.inside_panels]

    assert outside_names == ["back_cover", "front_cover", "tuck_flap"]
    assert outside_indices == [6, 1, 2]
    assert inside_names == ["inner_left", "inner_center", "inner_right"]
    assert inside_indices == [3, 4, 5]


def test_layout_panels_have_correct_sheet_labels() -> None:
    layout = compute_panel_layout()
    assert all(p.sheet == "outside" for p in layout.outside_panels)
    assert all(p.sheet == "inside" for p in layout.inside_panels)


# ---------- Trim tiling ----------


def _panel_area(p: PanelRect) -> int:
    _, _, w, h = p.trim_rect
    return w * h


def test_trim_rects_tile_the_trim_canvas_no_overlap_no_gap() -> None:
    layout = compute_panel_layout()
    for sheet_panels in (layout.outside_panels, layout.inside_panels):
        total_area = sum(_panel_area(p) for p in sheet_panels)
        assert total_area == TRIM_WIDTH_PX * TRIM_HEIGHT_PX

        # Check contiguous x-placement: each panel's right edge == next panel's left edge.
        sorted_panels = sorted(sheet_panels, key=lambda p: p.trim_rect[0])
        for a, b in zip(sorted_panels, sorted_panels[1:]):
            a_right = a.trim_rect[0] + a.trim_rect[2]
            b_left = b.trim_rect[0]
            assert a_right == b_left, f"gap/overlap between {a.name} and {b.name}"


def test_trim_rects_start_at_bleed_offset() -> None:
    layout = compute_panel_layout()
    for sheet_panels in (layout.outside_panels, layout.inside_panels):
        leftmost = min(sheet_panels, key=lambda p: p.trim_rect[0])
        assert leftmost.trim_rect[0] == BLEED_PX
        assert leftmost.trim_rect[1] == BLEED_PX


# ---------- Safe zone inset ----------


def test_safe_rects_are_properly_inset_on_all_four_sides() -> None:
    layout = compute_panel_layout()
    for p in layout.outside_panels + layout.inside_panels:
        tx, ty, tw, th = p.trim_rect
        sx, sy, sw, sh = p.safe_rect
        assert sx == tx + SAFE_PX, f"{p.name}: left safe inset"
        assert sy == ty + SAFE_PX, f"{p.name}: top safe inset"
        assert sx + sw == tx + tw - SAFE_PX, f"{p.name}: right safe inset"
        assert sy + sh == ty + th - SAFE_PX, f"{p.name}: bottom safe inset"


# ---------- Bleed rect extensions ----------


def test_bleed_rect_extends_to_canvas_on_sheet_edge_sides() -> None:
    layout = compute_panel_layout()
    for sheet_panels in (layout.outside_panels, layout.inside_panels):
        # Leftmost panel: bleed_rect.x == 0
        leftmost = min(sheet_panels, key=lambda p: p.trim_rect[0])
        assert leftmost.bleed_rect[0] == 0
        # Rightmost panel: bleed_rect.x + bleed_rect.w == BLEED_CANVAS_WIDTH
        rightmost = max(sheet_panels, key=lambda p: p.trim_rect[0])
        rx, _, rw, _ = rightmost.bleed_rect
        assert rx + rw == BLEED_CANVAS_WIDTH
        # All panels: bleed extends top/bottom to full canvas height
        for p in sheet_panels:
            _, by, _, bh = p.bleed_rect
            assert by == 0
            assert bh == BLEED_CANVAS_HEIGHT


# ---------- Fold lines ----------


def test_fold_lines_are_at_panel_boundaries_inside_trim() -> None:
    layout = compute_panel_layout()
    for fold_lines in (layout.fold_lines_outside, layout.fold_lines_inside):
        assert fold_lines == [BLEED_PX + PANEL_WIDTH_PX, BLEED_PX + 2 * PANEL_WIDTH_PX]
        # Fold lines must be strictly inside the trim x-range.
        for x in fold_lines:
            assert BLEED_PX < x < BLEED_PX + TRIM_WIDTH_PX


# ---------- Crop marks ----------


def test_eight_crop_marks_total() -> None:
    layout = compute_panel_layout()
    assert len(layout.crop_marks) == 8


def test_crop_marks_are_in_bleed_never_inside_trim() -> None:
    layout = compute_panel_layout()
    trim_left = BLEED_PX
    trim_right = BLEED_PX + TRIM_WIDTH_PX
    trim_top = BLEED_PX
    trim_bottom = BLEED_PX + TRIM_HEIGHT_PX

    for x, y in layout.crop_marks:
        in_trim_x = trim_left <= x < trim_right
        in_trim_y = trim_top <= y < trim_bottom
        # A crop mark is "inside trim" only if BOTH axes are inside.
        assert not (in_trim_x and in_trim_y), f"crop mark ({x}, {y}) is inside trim area"
        # And must be within the bleed canvas.
        assert 0 <= x <= BLEED_CANVAS_WIDTH
        assert 0 <= y <= BLEED_CANVAS_HEIGHT


# ---------- Determinism ----------


def test_compute_panel_layout_is_deterministic() -> None:
    a = compute_panel_layout()
    b = compute_panel_layout()
    assert a == b


# ---------- PanelRect bounds ----------


def test_panel_rect_rejects_index_out_of_range() -> None:
    with pytest.raises(ValueError):
        PanelRect(
            name="back_cover",
            index=7,  # type: ignore[arg-type]
            sheet="outside",
            bleed_rect=(0, 0, 10, 10),
            trim_rect=(0, 0, 10, 10),
            safe_rect=(0, 0, 10, 10),
        )


# ---------- Forbidden imports guard ----------


def test_layout_module_does_not_import_heavy_deps() -> None:
    source = inspect.getsource(layout_mod)
    forbidden = ("anthropic", "httpx", "reportlab", "cairosvg", "resvg_py", "PIL")
    for name in forbidden:
        pattern = rf"\bimport\s+{re.escape(name)}\b|\bfrom\s+{re.escape(name)}\b"
        assert not re.search(pattern, source), (
            f"layout module must not import '{name}' — pure math only"
        )
