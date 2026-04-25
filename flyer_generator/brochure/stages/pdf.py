"""PDF assembly for the brochure — 2-page consumer-printer-friendly PDF.

Takes the two rasterized sheet PNGs (outside + inside, each rendered at the
bleed canvas) and assembles them into a 2-page PDF whose page size is the
TRIM dimensions (11 × 8.5 in letter landscape = 792 × 612 pt), not the bleed
canvas. The bleed-canvas PNG is drawn with a -BLEED_PX offset so the bleed
clips off the page edges and only the trim content is visible. This produces
a PDF that prints correctly on a standard letter sheet without the printer
scaling/padding to fit the 0.125" bleed margins (which caused black bars and
visible stretching pre-260425-nwj).

Crop marks are intentionally omitted — they belong to the bleed area which
is no longer part of the PDF page. If a print-shop variant ever lands, it
would re-emit the bleed canvas + crop marks behind a new request flag.

Depends on `reportlab` (pure-Python PDF toolkit) for drawing + page assembly.
"""

from __future__ import annotations

import io

from reportlab.lib.colors import black
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from flyer_generator.brochure.stages.layout import (
    BLEED_CANVAS_HEIGHT,
    BLEED_CANVAS_WIDTH,
    BLEED_PX,
    TRIM_HEIGHT_PX,
    TRIM_WIDTH_PX,
)
from flyer_generator.errors import RasterizationError


class BrochurePDFError(RasterizationError):
    """Raised when PDF assembly fails."""


# 300dpi pixel -> PostScript-point conversion factor (RM-01, plan 24.2-01).
# ReportLab interprets the ``Canvas(buf, pagesize=(w, h))`` tuple as points
# (1 pt = 1/72 in). Multiply pixel dims by this factor to get the correct
# point-space pagesize, then call ``canvas.scale(PT_PER_PX, PT_PER_PX)`` so
# user-space remains in 300dpi pixels — drawImage and crop-mark coordinates
# stay in pixel units (no cascading edits).
PT_PER_PX: float = 72.0 / 300.0  # 0.24

_CROP_LEN = 36
_CROP_STROKE = 3


def _draw_crop_marks(canvas: Canvas, page_h: int) -> None:
    """Draw 4 L-shaped crop marks at each trim corner, in the bleed area.

    reportlab's coordinate system puts origin at bottom-left, so we invert y.
    """
    canvas.setStrokeColor(black)
    canvas.setLineWidth(_CROP_STROKE)

    trim_left_x = BLEED_PX
    trim_right_x = BLEED_PX + TRIM_WIDTH_PX
    # Invert for reportlab: y_pdf = page_h - y_pixel
    trim_top_y = page_h - BLEED_PX
    trim_bottom_y = page_h - (BLEED_PX + TRIM_HEIGHT_PX)

    corners = [
        # (corner_x, corner_y, h_extend_sign, v_extend_sign)
        (trim_left_x, trim_top_y, -1, +1),     # top-left: lines go left + up
        (trim_right_x, trim_top_y, +1, +1),    # top-right
        (trim_left_x, trim_bottom_y, -1, -1),  # bottom-left
        (trim_right_x, trim_bottom_y, +1, -1), # bottom-right
    ]
    for cx, cy, hx, vy in corners:
        # Horizontal tick extending outward into the bleed
        canvas.line(cx, cy, cx + hx * _CROP_LEN, cy)
        # Vertical tick extending outward into the bleed
        canvas.line(cx, cy, cx, cy + vy * _CROP_LEN)


def assemble_brochure_pdf(
    outside_png_bytes: bytes,
    inside_png_bytes: bytes,
) -> bytes:
    """Build a 2-page PDF: page 1 = outside sheet, page 2 = inside sheet.

    Page size is the TRIM dimensions (11 × 8.5 in = 792 × 612 pt) so the PDF
    prints correctly on a standard letter sheet. The bleed-canvas PNG
    (3376 × 2626 px) is drawn at a ``-BLEED_PX`` offset on both axes so the
    bleed area extends past the visible page boundary and clips off; only
    the trim portion of the PNG (the central TRIM_WIDTH × TRIM_HEIGHT region)
    appears on the page.

    Caller still rasterizes at the bleed canvas dimensions (no upstream
    contract change) — the trim/bleed split is a PDF-assembly concern.
    """
    if not outside_png_bytes:
        raise BrochurePDFError("outside_png_bytes must be non-empty")
    if not inside_png_bytes:
        raise BrochurePDFError("inside_png_bytes must be non-empty")

    # Page is sized to the TRIM (consumer-printer-friendly).
    page_w = TRIM_WIDTH_PX   # 3300 px = 11 in
    page_h = TRIM_HEIGHT_PX  # 2550 px = 8.5 in
    page_w_pt = page_w * PT_PER_PX  # 792 pt
    page_h_pt = page_h * PT_PER_PX  # 612 pt

    buf = io.BytesIO()
    try:
        canvas = Canvas(buf, pagesize=(page_w_pt, page_h_pt))
        # User-space stays in 300dpi pixels; pagesize is in points.
        canvas.scale(PT_PER_PX, PT_PER_PX)
        # --- Page 1: outside sheet ---
        # Draw at (-BLEED_PX, -BLEED_PX) so the bleed area extends past the
        # page edges; only the trim portion (BLEED_PX..BLEED_PX+TRIM in the
        # source PNG) is visible on the page.
        canvas.drawImage(
            ImageReader(io.BytesIO(outside_png_bytes)),
            -BLEED_PX, -BLEED_PX,
            width=BLEED_CANVAS_WIDTH, height=BLEED_CANVAS_HEIGHT,
            preserveAspectRatio=False,
        )
        canvas.showPage()
        # --- Page 2: inside sheet ---
        # showPage() resets the CTM, so re-apply the user-space scale.
        canvas.scale(PT_PER_PX, PT_PER_PX)
        canvas.drawImage(
            ImageReader(io.BytesIO(inside_png_bytes)),
            -BLEED_PX, -BLEED_PX,
            width=BLEED_CANVAS_WIDTH, height=BLEED_CANVAS_HEIGHT,
            preserveAspectRatio=False,
        )
        canvas.showPage()
        canvas.save()
    except Exception as exc:
        raise BrochurePDFError(f"PDF assembly failed: {exc}") from exc

    return buf.getvalue()
