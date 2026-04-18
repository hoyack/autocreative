"""Tests for stage 8 — mechanical output lint."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from flyer_generator.brochure.generative.lint import (
    _panel_is_empty,
    _text_bounding_boxes,
    check_crop_marks_in_svg,
    check_empty_quadrants,
    check_text_clipping,
    check_xml_validity,
    lint_brochure,
)
from flyer_generator.brochure.stages.layout import (
    BLEED_CANVAS_HEIGHT,
    BLEED_CANVAS_WIDTH,
    compute_panel_layout,
)


# ---------- XML validity ----------


def test_xml_validity_passes_on_well_formed() -> None:
    out = check_xml_validity("<svg><g/></svg>", "<svg><text>x</text></svg>")
    assert out == {"outside_svg_valid": True, "inside_svg_valid": True}


def test_xml_validity_reports_malformed() -> None:
    out = check_xml_validity("<svg>oops", "<svg/>")
    assert out["outside_svg_valid"] != True  # falsy — either False or error string
    assert out["inside_svg_valid"] is True


# ---------- Crop marks presence ----------


def test_crop_marks_detected_when_present() -> None:
    svg = '<svg><g id="crop-marks"><line/></g></svg>'
    out = check_crop_marks_in_svg(svg, svg)
    assert out == {"outside_crop_marks_present": True, "inside_crop_marks_present": True}


def test_crop_marks_missing_flags_false() -> None:
    out = check_crop_marks_in_svg("<svg/>", "<svg/>")
    assert out == {"outside_crop_marks_present": False, "inside_crop_marks_present": False}


# ---------- Panel emptiness (unit) ----------


def test_panel_is_empty_true_for_uniform_pixels() -> None:
    pixels = [(255, 255, 255)] * 400
    assert _panel_is_empty(pixels) is True


def test_panel_is_empty_false_for_mixed_pixels() -> None:
    pixels = [(0, 0, 0), (255, 255, 255)] * 200
    assert _panel_is_empty(pixels) is False


# ---------- Empty-quadrant check end-to-end ----------


def _solid_png(w: int, h: int, color: tuple[int, int, int]) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


def test_empty_quadrants_flags_blank_sheet() -> None:
    layout = compute_panel_layout()
    blank = _solid_png(BLEED_CANVAS_WIDTH, BLEED_CANVAS_HEIGHT, (255, 255, 255))
    report = check_empty_quadrants(blank, blank, layout, outside_svg="", inside_svg="")
    # All 6 panels on a uniform-white sheet must flag empty
    empty_flags = [v for k, v in report.items() if k.startswith("panel_") and k.endswith("_empty")]
    assert all(flag is True for flag in empty_flags)
    assert len(empty_flags) == 6


def test_empty_quadrants_skipped_when_svg_has_images() -> None:
    """Rich content (lots of shapes + an <image>) → empty flag stays False."""
    layout = compute_panel_layout()
    blank = _solid_png(BLEED_CANVAS_WIDTH, BLEED_CANVAS_HEIGHT, (255, 255, 255))
    rich_svg = '<svg><image href="x"/><path/><path/><path/></svg>'
    report = check_empty_quadrants(blank, blank, layout, outside_svg=rich_svg, inside_svg=rich_svg)
    empty_flags = [v for k, v in report.items() if k.startswith("panel_") and k.endswith("_empty")]
    assert all(flag is False for flag in empty_flags)


def test_empty_quadrants_handles_bad_png() -> None:
    """Non-PNG bytes → error string in the report; doesn't raise."""
    layout = compute_panel_layout()
    report = check_empty_quadrants(b"garbage", b"garbage", layout)
    assert "empty_quadrant_check_error" in report


# ---------- Text bounding boxes ----------


def test_text_bounding_boxes_parses_well_formed_text() -> None:
    svg = '<svg><text x="100" y="200" font-size="40">Hello</text></svg>'
    bboxes = _text_bounding_boxes(svg)
    assert len(bboxes) == 1
    x0, y0, x1, y1 = bboxes[0]
    assert x0 == 100
    assert y0 == 200 - 40
    # Width for "Hello" = 0.55 * 40 * 5 = 110
    assert x1 == 100 + 110


def test_text_bounding_boxes_skips_empty_text() -> None:
    svg = '<svg><text x="0" y="0" font-size="20">   </text></svg>'
    assert _text_bounding_boxes(svg) == []


# ---------- Text clipping ----------


def test_text_clipping_all_false_on_empty_svg() -> None:
    layout = compute_panel_layout()
    out = check_text_clipping("<svg/>", "<svg/>", layout)
    assert all(v is False for v in out.values())


def test_text_clipping_flags_overflowing_text() -> None:
    layout = compute_panel_layout()
    # Grab an inner panel's safe rect and construct text that starts inside
    # but is so long it extends past the safe rect's right edge.
    panel = layout.inside_panels[0]
    sx, sy, sw, sh = panel.safe_rect
    # Text starts near the right edge with huge font-size → definitely clips.
    inside_svg = (
        f'<svg><text x="{sx + sw - 20}" y="{sy + 50}" font-size="200">'
        f'overflowing-text-that-will-never-fit</text></svg>'
    )
    out = check_text_clipping("<svg/>", inside_svg, layout)
    key = f"panel_{panel.name}_text_clip"
    assert out[key] is True


# ---------- lint_brochure orchestrator ----------


def test_lint_brochure_merges_all_checks() -> None:
    layout = compute_panel_layout()
    blank = _solid_png(BLEED_CANVAS_WIDTH, BLEED_CANVAS_HEIGHT, (255, 255, 255))
    report = lint_brochure(
        outside_svg='<svg><g id="crop-marks"/></svg>',
        inside_svg='<svg><g id="crop-marks"/></svg>',
        front_png_bytes=blank,
        back_png_bytes=blank,
        layout=layout,
    )
    # Every category contributes
    assert "outside_svg_valid" in report
    assert "outside_crop_marks_present" in report
    assert any(k.endswith("_empty") for k in report)
    assert any(k.endswith("_text_clip") for k in report)
    assert "_summary" in report
    assert "/" in report["_summary"]


def test_lint_brochure_summary_reflects_failures() -> None:
    """An all-empty sheet → summary shows fewer-than-all passing."""
    layout = compute_panel_layout()
    blank = _solid_png(BLEED_CANVAS_WIDTH, BLEED_CANVAS_HEIGHT, (255, 255, 255))
    report = lint_brochure(
        outside_svg="<svg/>",
        inside_svg="<svg/>",
        front_png_bytes=blank,
        back_png_bytes=blank,
        layout=layout,
    )
    # Crop marks missing + all 6 panels empty → failures present
    summary = report["_summary"]
    passed, total = summary.split(" ")[0].split("/")
    assert int(passed) < int(total)
