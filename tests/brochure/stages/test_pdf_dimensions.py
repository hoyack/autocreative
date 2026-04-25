"""Mediabox dimension contract for the brochure print PDF (RM-01, plan 24.2-01).

ReportLab interprets the ``Canvas(buf, pagesize=(w, h))`` tuple as PostScript
points (1pt = 1/72in). The brochure assembler historically passed 300dpi pixel
values directly, yielding a mediabox of 3376 x 2626 pt = 46.89 x 36.47 in
(should be 11.25 x 8.75 in — letter-landscape + 0.125in bleed each edge).

The fix: scale the pagesize tuple by ``PT_PER_PX = 72.0 / 300.0`` and call
``canvas.scale(PT_PER_PX, PT_PER_PX)`` so user-space stays in 300dpi pixel units
(drawImage and crop-mark coordinates unchanged).

These tests assert the points-correct contract by decoding the produced PDF
with ``pypdf`` and checking ``mediabox.width / 72`` reports inches.
"""

from __future__ import annotations

import io

from PIL import Image
from pypdf import PdfReader

from flyer_generator.brochure.stages.layout import (
    BLEED_CANVAS_HEIGHT,
    BLEED_CANVAS_WIDTH,
)
from flyer_generator.brochure.stages.pdf import assemble_brochure_pdf

# 300dpi pixel -> PostScript-point conversion factor.
# Mirrored from flyer_generator/brochure/stages/pdf.py::PT_PER_PX so the test
# encodes the dimensional contract independently of the production constant.
PT_PER_PX: float = 72.0 / 300.0  # 0.24


def _fake_sheet_png(color: tuple[int, int, int] = (200, 200, 255)) -> bytes:
    """Generate a valid PNG at the bleed canvas size (3376 x 2626 px)."""
    buf = io.BytesIO()
    Image.new("RGB", (BLEED_CANVAS_WIDTH, BLEED_CANVAS_HEIGHT), color).save(buf, "PNG")
    return buf.getvalue()


def test_brochure_pdf_mediabox_is_in_points_not_pixels() -> None:
    """Mediabox width is BLEED_CANVAS_WIDTH * 72/300 (= 810.24 pt), NOT 3376 px.

    Anti-regression: the bug expressed itself as ``float(box.width) == 3376.0``
    (pixels treated as points). After the fix the value should be ~810.24.
    """
    outside = _fake_sheet_png((240, 240, 255))
    inside = _fake_sheet_png((255, 240, 240))
    pdf_bytes = assemble_brochure_pdf(outside, inside)

    reader = PdfReader(io.BytesIO(pdf_bytes))
    page = reader.pages[0]
    expected_width_pt = BLEED_CANVAS_WIDTH * PT_PER_PX  # 810.24
    expected_height_pt = BLEED_CANVAS_HEIGHT * PT_PER_PX  # 630.24

    assert abs(float(page.mediabox.width) - expected_width_pt) < 0.01, (
        f"mediabox.width should be {expected_width_pt:.4f} pt, "
        f"got {float(page.mediabox.width):.4f} (likely the pixel-as-point bug)"
    )
    assert abs(float(page.mediabox.height) - expected_height_pt) < 0.01, (
        f"mediabox.height should be {expected_height_pt:.4f} pt, "
        f"got {float(page.mediabox.height):.4f}"
    )
    # Strong anti-regression: explicitly NOT the pixel value.
    assert float(page.mediabox.width) != float(BLEED_CANVAS_WIDTH), (
        "mediabox.width still equals the pixel value — the PT_PER_PX scale was "
        "not applied"
    )


def test_brochure_pdf_mediabox_in_inches() -> None:
    """11.25in x 8.75in = letter landscape (11x8.5) + 0.125in bleed each edge.

    Letter-landscape trim is 11.0 x 8.5 in; bleed adds 0.125in on every side
    (BLEED_INCHES in layout.py). 11.0 + 2*0.125 = 11.25, 8.5 + 2*0.125 = 8.75.
    """
    pdf_bytes = assemble_brochure_pdf(_fake_sheet_png(), _fake_sheet_png())
    reader = PdfReader(io.BytesIO(pdf_bytes))
    page = reader.pages[0]

    width_in = float(page.mediabox.width) / 72.0
    height_in = float(page.mediabox.height) / 72.0

    assert abs(width_in - 11.253333) < 0.01, (
        f"mediabox width in inches should be ~11.25 (letter landscape + bleed), "
        f"got {width_in:.4f}"
    )
    assert abs(height_in - 8.753333) < 0.01, (
        f"mediabox height in inches should be ~8.75 (letter landscape + bleed), "
        f"got {height_in:.4f}"
    )


def test_brochure_both_pages_same_mediabox() -> None:
    """Pages 1 (outside) and 2 (inside) must share identical mediabox dims."""
    pdf_bytes = assemble_brochure_pdf(_fake_sheet_png(), _fake_sheet_png())
    reader = PdfReader(io.BytesIO(pdf_bytes))

    assert len(reader.pages) == 2
    p1, p2 = reader.pages
    assert float(p1.mediabox.width) == float(p2.mediabox.width)
    assert float(p1.mediabox.height) == float(p2.mediabox.height)
