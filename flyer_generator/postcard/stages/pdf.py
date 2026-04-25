"""PDF assembly for postcards — 2-page print-ready PDF.

Page 1 = front PNG; Page 2 = back PNG. Page dimensions are passed in by
the caller (typically derived from PostcardTemplateSchema.canvas) so a
1200x1800 portrait card and an 1800x1200 landscape card share this
single function.

No crop marks: postcards are typically printed at exact USPS dimensions
(4x6 / 6x4) without bleed, and mailing carriers do not require trim
guides. Brochures, by contrast, ship with a bleed canvas + crop marks
via ``flyer_generator/brochure/stages/pdf.py::assemble_brochure_pdf``.

Depends on ``reportlab`` (pure-Python PDF toolkit, already pinned by
Phase 8).
"""

from __future__ import annotations

import io

from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from flyer_generator.errors import RasterizationError

# 300dpi pixel -> PostScript-point conversion factor (RM-01, plan 24.2-01).
# ReportLab interprets the ``Canvas(buf, pagesize=(w, h))`` tuple as points
# (1 pt = 1/72 in). Scale pixel dims by this factor for the pagesize tuple,
# then call ``canvas.scale(PT_PER_PX, PT_PER_PX)`` so user-space stays in
# 300dpi pixels — drawImage calls keep their pixel coordinates unchanged.
PT_PER_PX: float = 72.0 / 300.0  # 0.24


class PostcardPDFError(RasterizationError):
    """Raised when postcard PDF assembly fails.

    Subclasses ``RasterizationError`` so callers handling either rasterizer
    or PDF assembly failure with a single ``except RasterizationError``
    catch continue to work unchanged. The worker plan (23-04) will
    surface this type to ``JobRecord.error_detail`` (T-23-11 mitigation).
    """


def assemble_postcard_pdf(
    front_png_bytes: bytes,
    back_png_bytes: bytes,
    page_width: int,
    page_height: int,
) -> bytes:
    """Build a 2-page PDF: page 1 = front, page 2 = back.

    Page size is supplied by the caller (typically
    ``template.canvas.width`` / ``template.canvas.height``). Each PNG is
    drawn full-bleed to the page rect with
    ``preserveAspectRatio=False``; the caller is responsible for having
    rasterized at exactly ``page_width x page_height`` (verified by
    ``Rasterizer.rasterize``'s dimension check).

    Parameters
    ----------
    front_png_bytes:
        Rasterized front-panel PNG. Must be non-empty.
    back_png_bytes:
        Rasterized back-panel PNG. Must be non-empty.
    page_width, page_height:
        Page dimensions in 300dpi pixel units. Page size is computed in
        PostScript points (1pt = 1/72in) by scaling pixel dims by
        ``PT_PER_PX`` (= 72/300 = 0.24); after
        ``canvas.scale(PT_PER_PX, PT_PER_PX)`` the user-space remains
        300dpi pixels so the caller's ``drawImage(..., width=page_width,
        height=page_height)`` call still spans the full page.

    Returns
    -------
    bytes
        PDF file bytes (starts with ``b"%PDF-"``).

    Raises
    ------
    PostcardPDFError
        If either input is empty, page dimensions are non-positive, or
        reportlab raises during canvas assembly (corrupt PNG, etc.).
    """
    if not front_png_bytes:
        raise PostcardPDFError("front_png_bytes must be non-empty")
    if not back_png_bytes:
        raise PostcardPDFError("back_png_bytes must be non-empty")
    if page_width <= 0 or page_height <= 0:
        raise PostcardPDFError(
            f"page dimensions must be positive (got "
            f"{page_width}x{page_height})"
        )

    page_w_pt = page_width * PT_PER_PX
    page_h_pt = page_height * PT_PER_PX

    buf = io.BytesIO()
    try:
        canvas = Canvas(buf, pagesize=(page_w_pt, page_h_pt))
        # User-space stays in 300dpi pixels; pagesize is in points.
        canvas.scale(PT_PER_PX, PT_PER_PX)
        # --- Page 1: front ---
        canvas.drawImage(
            ImageReader(io.BytesIO(front_png_bytes)),
            0,
            0,
            width=page_width,
            height=page_height,
            preserveAspectRatio=False,
        )
        canvas.showPage()
        # --- Page 2: back ---
        # showPage() resets the CTM, so re-apply the user-space scale.
        canvas.scale(PT_PER_PX, PT_PER_PX)
        canvas.drawImage(
            ImageReader(io.BytesIO(back_png_bytes)),
            0,
            0,
            width=page_width,
            height=page_height,
            preserveAspectRatio=False,
        )
        canvas.showPage()
        canvas.save()
    except Exception as exc:
        raise PostcardPDFError(f"PDF assembly failed: {exc}") from exc

    return buf.getvalue()
