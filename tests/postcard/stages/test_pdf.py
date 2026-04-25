"""Tests for postcard PDF assembly (assemble_postcard_pdf + PostcardPDFError)."""

from __future__ import annotations

import io

import pytest
from PIL import Image
from pypdf import PdfReader


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _png_bytes(w: int, h: int, color: tuple[int, int, int] = (200, 200, 255)) -> bytes:
    """Generate a valid PNG of dims (w, h) at the requested color."""
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Test 1: importability
# ---------------------------------------------------------------------------


def test_imports_assemble_postcard_pdf_and_error() -> None:
    """from flyer_generator.postcard.stages.pdf import assemble_postcard_pdf, PostcardPDFError."""
    from flyer_generator.postcard.stages.pdf import (  # noqa: F401
        PostcardPDFError,
        assemble_postcard_pdf,
    )


# ---------------------------------------------------------------------------
# Test 2: PostcardPDFError is a RasterizationError subclass
# ---------------------------------------------------------------------------


def test_postcard_pdf_error_is_rasterization_error_subclass() -> None:
    from flyer_generator.errors import RasterizationError
    from flyer_generator.postcard.stages.pdf import PostcardPDFError

    assert issubclass(PostcardPDFError, RasterizationError)


# ---------------------------------------------------------------------------
# Tests 3-4: empty input rejection
# ---------------------------------------------------------------------------


def test_empty_front_png_raises_with_field_name_in_message() -> None:
    from flyer_generator.postcard.stages.pdf import (
        PostcardPDFError,
        assemble_postcard_pdf,
    )

    valid = _png_bytes(1200, 1800)
    with pytest.raises(PostcardPDFError, match="front_png_bytes"):
        assemble_postcard_pdf(b"", valid, 1200, 1800)


def test_empty_back_png_raises_with_field_name_in_message() -> None:
    from flyer_generator.postcard.stages.pdf import (
        PostcardPDFError,
        assemble_postcard_pdf,
    )

    valid = _png_bytes(1200, 1800)
    with pytest.raises(PostcardPDFError, match="back_png_bytes"):
        assemble_postcard_pdf(valid, b"", 1200, 1800)


# ---------------------------------------------------------------------------
# Test 5: PDF magic + non-trivial size (portrait)
# ---------------------------------------------------------------------------


def test_returns_pdf_bytes_with_magic_header_portrait() -> None:
    from flyer_generator.postcard.stages.pdf import assemble_postcard_pdf

    front = _png_bytes(1200, 1800, (240, 240, 255))
    back = _png_bytes(1200, 1800, (255, 240, 240))
    pdf = assemble_postcard_pdf(front, back, 1200, 1800)
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1000


# ---------------------------------------------------------------------------
# Test 6: 2-page PDF
# ---------------------------------------------------------------------------


def test_pdf_has_exactly_two_pages() -> None:
    from flyer_generator.postcard.stages.pdf import assemble_postcard_pdf

    front = _png_bytes(1200, 1800)
    back = _png_bytes(1200, 1800)
    pdf = assemble_postcard_pdf(front, back, 1200, 1800)
    reader = PdfReader(io.BytesIO(pdf))
    assert len(reader.pages) == 2


# ---------------------------------------------------------------------------
# Tests 7-8: page dimensions match input — portrait
# ---------------------------------------------------------------------------


def test_portrait_page_one_dimensions_match_input() -> None:
    """Mediabox is the input pixel dims scaled by 72/300 (RM-01: points, not pixels).

    1200 px * 72/300 = 288 pt = 4 in. 1800 px * 72/300 = 432 pt = 6 in.
    """
    from flyer_generator.postcard.stages.pdf import assemble_postcard_pdf

    front = _png_bytes(1200, 1800)
    back = _png_bytes(1200, 1800)
    pdf = assemble_postcard_pdf(front, back, 1200, 1800)
    reader = PdfReader(io.BytesIO(pdf))
    page1 = reader.pages[0]
    assert abs(float(page1.mediabox.width) - 1200 * 72.0 / 300.0) < 0.01
    assert abs(float(page1.mediabox.height) - 1800 * 72.0 / 300.0) < 0.01


def test_portrait_page_two_dimensions_match_input() -> None:
    """Page 2 mediabox is also 72/300-scaled (RM-01: points, not pixels)."""
    from flyer_generator.postcard.stages.pdf import assemble_postcard_pdf

    front = _png_bytes(1200, 1800)
    back = _png_bytes(1200, 1800)
    pdf = assemble_postcard_pdf(front, back, 1200, 1800)
    reader = PdfReader(io.BytesIO(pdf))
    page2 = reader.pages[1]
    assert abs(float(page2.mediabox.width) - 1200 * 72.0 / 300.0) < 0.01
    assert abs(float(page2.mediabox.height) - 1800 * 72.0 / 300.0) < 0.01


# ---------------------------------------------------------------------------
# Test 9: landscape dimensions
# ---------------------------------------------------------------------------


def test_landscape_dimensions_round_trip() -> None:
    """Landscape 1800x1200 px → 432 x 288 pt = 6 x 4 in (RM-01)."""
    from flyer_generator.postcard.stages.pdf import assemble_postcard_pdf

    front = _png_bytes(1800, 1200)
    back = _png_bytes(1800, 1200)
    pdf = assemble_postcard_pdf(front, back, 1800, 1200)
    reader = PdfReader(io.BytesIO(pdf))
    assert len(reader.pages) == 2
    for page in reader.pages:
        assert abs(float(page.mediabox.width) - 1800 * 72.0 / 300.0) < 0.01
        assert abs(float(page.mediabox.height) - 1200 * 72.0 / 300.0) < 0.01


# ---------------------------------------------------------------------------
# Test 10: deterministic-enough size
# ---------------------------------------------------------------------------


def test_two_assemblies_produce_similar_size_output() -> None:
    """reportlab embeds a timestamp; sizes should still match within ~200 bytes."""
    from flyer_generator.postcard.stages.pdf import assemble_postcard_pdf

    front = _png_bytes(1200, 1800, (10, 20, 30))
    back = _png_bytes(1200, 1800, (40, 50, 60))
    out1 = assemble_postcard_pdf(front, back, 1200, 1800)
    out2 = assemble_postcard_pdf(front, back, 1200, 1800)
    assert abs(len(out1) - len(out2)) < 200


# ---------------------------------------------------------------------------
# Bonus tests: corrupt PNG, bad page dims, page-ordering smoke
# ---------------------------------------------------------------------------


def test_corrupt_png_raises_postcard_pdf_error() -> None:
    from flyer_generator.postcard.stages.pdf import (
        PostcardPDFError,
        assemble_postcard_pdf,
    )

    with pytest.raises(PostcardPDFError, match="assembly failed"):
        assemble_postcard_pdf(b"not-a-png", b"also-not-a-png", 1200, 1800)


def test_zero_page_dim_raises() -> None:
    from flyer_generator.postcard.stages.pdf import (
        PostcardPDFError,
        assemble_postcard_pdf,
    )

    front = _png_bytes(1200, 1800)
    back = _png_bytes(1200, 1800)
    with pytest.raises(PostcardPDFError, match="page dimensions"):
        assemble_postcard_pdf(front, back, 0, 1800)
    with pytest.raises(PostcardPDFError, match="page dimensions"):
        assemble_postcard_pdf(front, back, 1200, 0)


def test_each_page_has_image_xobject_resource() -> None:
    """Both pages must have an /Image XObject (the PNG was embedded)."""
    from flyer_generator.postcard.stages.pdf import assemble_postcard_pdf

    front = _png_bytes(1200, 1800, (255, 0, 0))
    back = _png_bytes(1200, 1800, (0, 0, 255))
    pdf = assemble_postcard_pdf(front, back, 1200, 1800)
    reader = PdfReader(io.BytesIO(pdf))
    for page in reader.pages:
        resources = page.get("/Resources")
        xobjects = resources.get("/XObject") if resources else None
        assert xobjects is not None, "expected image xobject on every page"
