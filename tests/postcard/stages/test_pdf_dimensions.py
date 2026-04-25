"""Mediabox dimension contract for the postcard print PDF (RM-01, plan 24.2-01).

ReportLab interprets ``Canvas(buf, pagesize=(w, h))`` as PostScript points
(1pt = 1/72in). The postcard assembler historically passed 300dpi pixel values
directly, yielding a 1200x1800 portrait mediabox of 1200x1800 pt = 16.67x25 in
(should be 4 x 6 in). The original docstring even codified the bug as a feature
("passing pixel values here gives us a 1:1 pixel-to-point page so the caller
does not need DPI math") — that is precisely the bug.

These tests assert the points-correct contract via ``pypdf`` decoding.
"""

from __future__ import annotations

import io

from PIL import Image
from pypdf import PdfReader

from flyer_generator.postcard.stages.pdf import assemble_postcard_pdf

# 300dpi pixel -> PostScript-point conversion factor (mirror of the production
# constant in flyer_generator/postcard/stages/pdf.py::PT_PER_PX).
PT_PER_PX: float = 72.0 / 300.0  # 0.24


def _png_bytes(w: int, h: int, color: tuple[int, int, int] = (200, 200, 255)) -> bytes:
    """Generate a valid PNG of dims (w, h) at the requested color."""
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


def test_postcard_portrait_mediabox_is_4x6_inches() -> None:
    """Portrait template is 1200x1800 px @ 300dpi → 4x6 in mediabox."""
    front = _png_bytes(1200, 1800, (240, 240, 255))
    back = _png_bytes(1200, 1800, (255, 240, 240))
    pdf = assemble_postcard_pdf(front, back, 1200, 1800)

    reader = PdfReader(io.BytesIO(pdf))
    page = reader.pages[0]

    width_in = float(page.mediabox.width) / 72.0
    height_in = float(page.mediabox.height) / 72.0

    assert abs(width_in - 4.0) < 0.01, (
        f"portrait mediabox width should be 4.0 in, got {width_in:.4f}"
    )
    assert abs(height_in - 6.0) < 0.01, (
        f"portrait mediabox height should be 6.0 in, got {height_in:.4f}"
    )


def test_postcard_landscape_mediabox_is_6x4_inches() -> None:
    """Landscape template is 1800x1200 px @ 300dpi → 6x4 in mediabox."""
    front = _png_bytes(1800, 1200, (240, 240, 255))
    back = _png_bytes(1800, 1200, (255, 240, 240))
    pdf = assemble_postcard_pdf(front, back, 1800, 1200)

    reader = PdfReader(io.BytesIO(pdf))
    for page in reader.pages:
        width_in = float(page.mediabox.width) / 72.0
        height_in = float(page.mediabox.height) / 72.0
        assert abs(width_in - 6.0) < 0.01, (
            f"landscape mediabox width should be 6.0 in, got {width_in:.4f}"
        )
        assert abs(height_in - 4.0) < 0.01, (
            f"landscape mediabox height should be 4.0 in, got {height_in:.4f}"
        )


def test_postcard_mediabox_dims_in_points_not_pixels() -> None:
    """Explicit anti-regression: mediabox.width is 288 pt, not 1200.

    1200 px * (72/300) = 288 pt = 4 in. If the bug returns, mediabox.width
    will equal 1200.0 (pixels treated as points).
    """
    front = _png_bytes(1200, 1800)
    back = _png_bytes(1200, 1800)
    pdf = assemble_postcard_pdf(front, back, 1200, 1800)

    reader = PdfReader(io.BytesIO(pdf))
    page = reader.pages[0]

    expected_width_pt = 1200 * PT_PER_PX  # 288.0
    expected_height_pt = 1800 * PT_PER_PX  # 432.0

    assert abs(float(page.mediabox.width) - expected_width_pt) < 0.01, (
        f"mediabox.width should be {expected_width_pt:.4f} pt, "
        f"got {float(page.mediabox.width):.4f}"
    )
    assert abs(float(page.mediabox.height) - expected_height_pt) < 0.01, (
        f"mediabox.height should be {expected_height_pt:.4f} pt, "
        f"got {float(page.mediabox.height):.4f}"
    )
    # Strong anti-regression: NOT the pixel value.
    assert float(page.mediabox.width) != 1200.0, (
        "mediabox.width still equals 1200.0 px — PT_PER_PX scale was not applied"
    )
    assert float(page.mediabox.height) != 1800.0, (
        "mediabox.height still equals 1800.0 px — PT_PER_PX scale was not applied"
    )
