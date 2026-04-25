"""Mediabox dimension contract for the brochure print PDF.

The PDF page size is derived from the source PNG dimensions at 300 dpi
(``PT_PER_PX = 72.0 / 300.0``), so the image fills the page 1:1 — never
stretched. If the renderer emits 1080×1920 portrait panels the PDF is
3.6×6.4 in. If it emits 3376×2626 landscape sheets the PDF is 11.25×8.75 in.

Bug history:
  - RM-01 (260425, fixed): pagesize tuple was passed as pixels, treated by
    reportlab as points → 46.89 in mediabox.
  - 260425-nwj v1: pagesize was the bleed canvas (11.25 × 8.75) which
    doesn't match consumer letter paper.
  - 260425-nwj v2 (this contract): pagesize was forced to letter trim
    (11 × 8.5) which stretched the 1080×1920 portrait PNG into landscape,
    producing visible vertical squash. Now the page tracks the PNG.
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


def _fake_sheet_png(
    color: tuple[int, int, int] = (200, 200, 255),
    size: tuple[int, int] = (BLEED_CANVAS_WIDTH, BLEED_CANVAS_HEIGHT),
) -> bytes:
    """Generate a valid PNG at the requested ``size`` (default = bleed canvas)."""
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def test_brochure_pdf_mediabox_matches_png_at_300dpi() -> None:
    """Mediabox = (PNG_W * 72/300, PNG_H * 72/300). 1:1 mapping at 300dpi.

    Anti-regression: page size must NOT be a hardcoded constant — it must
    follow the source PNG. Use a non-default PNG size (1080x1920 portrait,
    matching what the schema renderer actually produces today) and verify
    the PDF page is 1080*0.24 × 1920*0.24 = 259.2 × 460.8 pt.
    """
    portrait = _fake_sheet_png(size=(1080, 1920))
    pdf_bytes = assemble_brochure_pdf(portrait, portrait)

    reader = PdfReader(io.BytesIO(pdf_bytes))
    page = reader.pages[0]
    expected_w_pt = 1080 * PT_PER_PX  # 259.2
    expected_h_pt = 1920 * PT_PER_PX  # 460.8

    assert abs(float(page.mediabox.width) - expected_w_pt) < 0.01, (
        f"PDF page width should track PNG width (1080*0.24 = {expected_w_pt:.2f}), "
        f"got {float(page.mediabox.width):.2f}"
    )
    assert abs(float(page.mediabox.height) - expected_h_pt) < 0.01, (
        f"PDF page height should track PNG height (1920*0.24 = {expected_h_pt:.2f}), "
        f"got {float(page.mediabox.height):.2f}"
    )
    # Anti-regression: the PNG aspect ratio must be preserved on the PDF page.
    png_aspect = 1080 / 1920
    pdf_aspect = float(page.mediabox.width) / float(page.mediabox.height)
    assert abs(pdf_aspect - png_aspect) < 0.001, (
        f"PDF page aspect ({pdf_aspect:.4f}) must match PNG aspect ({png_aspect:.4f}); "
        f"otherwise the image is stretched (the symptom that motivated 260425-nwj v2)"
    )


def test_brochure_pdf_mediabox_tracks_bleed_canvas_when_renderer_emits_one() -> None:
    """If the renderer ever emits a bleed-canvas PNG (3376×2626), the PDF
    becomes 810.24 × 630.24 pt = 11.25 × 8.75 in — same 1:1 contract,
    different PNG dims.
    """
    bleed = _fake_sheet_png()  # default = bleed canvas size
    pdf_bytes = assemble_brochure_pdf(bleed, bleed)
    page = PdfReader(io.BytesIO(pdf_bytes)).pages[0]

    width_in = float(page.mediabox.width) / 72.0
    height_in = float(page.mediabox.height) / 72.0

    assert abs(width_in - 11.253333) < 0.01
    assert abs(height_in - 8.753333) < 0.01


def test_brochure_pdf_rejects_mismatched_png_dimensions() -> None:
    """Both pages of the PDF must share dimensions; refuse mismatched input."""
    import pytest

    from flyer_generator.brochure.stages.pdf import BrochurePDFError

    portrait = _fake_sheet_png(size=(1080, 1920))
    landscape = _fake_sheet_png(size=(3376, 2626))
    with pytest.raises(BrochurePDFError, match="must share dimensions"):
        assemble_brochure_pdf(portrait, landscape)


def test_brochure_both_pages_same_mediabox() -> None:
    """Pages 1 (outside) and 2 (inside) must share identical mediabox dims."""
    pdf_bytes = assemble_brochure_pdf(_fake_sheet_png(), _fake_sheet_png())
    reader = PdfReader(io.BytesIO(pdf_bytes))

    assert len(reader.pages) == 2
    p1, p2 = reader.pages
    assert float(p1.mediabox.width) == float(p2.mediabox.width)
    assert float(p1.mediabox.height) == float(p2.mediabox.height)
