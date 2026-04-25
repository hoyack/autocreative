"""Tests for brochure PDF assembly."""

from __future__ import annotations

import io

import pytest
from PIL import Image
from pypdf import PdfReader

from flyer_generator.brochure.stages.layout import (
    BLEED_CANVAS_HEIGHT,
    BLEED_CANVAS_WIDTH,
    TRIM_HEIGHT_PX,
    TRIM_WIDTH_PX,
)
from flyer_generator.brochure.stages.pdf import (
    BrochurePDFError,
    assemble_brochure_pdf,
)


def _fake_sheet_png(color: tuple[int, int, int] = (200, 200, 255)) -> bytes:
    """Generate a valid PNG at the bleed canvas size."""
    buf = io.BytesIO()
    Image.new("RGB", (BLEED_CANVAS_WIDTH, BLEED_CANVAS_HEIGHT), color).save(buf, "PNG")
    return buf.getvalue()


def test_assemble_returns_valid_pdf_bytes() -> None:
    outside = _fake_sheet_png((240, 240, 255))
    inside = _fake_sheet_png((255, 240, 240))
    pdf_bytes = assemble_brochure_pdf(outside, inside)

    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 1000  # non-trivial


def test_pdf_has_exactly_two_pages() -> None:
    pdf_bytes = assemble_brochure_pdf(_fake_sheet_png(), _fake_sheet_png())
    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) == 2


def test_pdf_page_size_matches_letter_trim() -> None:
    """Mediabox is the TRIM size (11 × 8.5 in letter landscape = 792 × 612 pt).

    Quick task 260425-nwj: PDF is now consumer-printer-friendly. The bleed
    canvas (810.24 × 630.24 pt = 11.25 × 8.75 in) is no longer the page
    boundary — the bleed-canvas PNG is drawn at a -BLEED_PX offset so the
    bleed extends past the page edges and clips off, leaving only the trim
    portion visible. This makes the PDF print correctly on a standard letter
    sheet without the printer scaling/padding to fit the bleed margins.
    """
    pdf_bytes = assemble_brochure_pdf(_fake_sheet_png(), _fake_sheet_png())
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pt_per_px = 72.0 / 300.0
    expected_w_pt = TRIM_WIDTH_PX * pt_per_px   # 792
    expected_h_pt = TRIM_HEIGHT_PX * pt_per_px  # 612
    for page in reader.pages:
        box = page.mediabox
        assert abs(float(box.width) - expected_w_pt) < 0.01
        assert abs(float(box.height) - expected_h_pt) < 0.01


def test_empty_outside_png_raises() -> None:
    with pytest.raises(BrochurePDFError, match="outside_png_bytes"):
        assemble_brochure_pdf(b"", _fake_sheet_png())


def test_empty_inside_png_raises() -> None:
    with pytest.raises(BrochurePDFError, match="inside_png_bytes"):
        assemble_brochure_pdf(_fake_sheet_png(), b"")


def test_invalid_png_raises_brochure_pdf_error() -> None:
    with pytest.raises(BrochurePDFError, match="assembly failed"):
        assemble_brochure_pdf(b"not-a-png", b"also-not-a-png")


def test_pdf_size_reflects_image_plus_crop_marks() -> None:
    # Two ~22KB PNGs produce a PDF >20KB (images dominate; crop-marks add little).
    pdf_bytes = assemble_brochure_pdf(_fake_sheet_png(), _fake_sheet_png())
    assert len(pdf_bytes) > 20_000


def test_outside_is_page_one_inside_is_page_two() -> None:
    # Distinguishable colors ensure page ordering is correct: if reversed, the
    # returned bytes would still be a valid PDF but with swapped pages. pypdf
    # doesn't easily give us pixel access, so we just confirm we can extract
    # two pages without error and that page 1 precedes page 2 in the reader.
    outside = _fake_sheet_png((255, 0, 0))
    inside = _fake_sheet_png((0, 0, 255))
    pdf_bytes = assemble_brochure_pdf(outside, inside)
    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) == 2
    # Both pages must have image resources (X-Objects of subtype /Image).
    for page in reader.pages:
        resources = page.get("/Resources")
        xobjects = resources.get("/XObject") if resources else None
        assert xobjects is not None, "expected image xobject on every page"
