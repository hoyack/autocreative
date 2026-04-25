"""PDF assembly for the brochure — 2-page print-ready PDF with crop marks.

Takes the two rasterized sheet PNGs (outside + inside) and assembles them into
a single 2-page PDF sized to the bleed canvas at 300 DPI. Crop marks are drawn
onto the bleed area at each trim corner.

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

    Design canvas is the bleed canvas (3376 x 2626 px at 300 DPI). Page size
    is the bleed canvas converted to PostScript points via ``PT_PER_PX``
    (72pt/in / 300px/in = 0.24); after ``canvas.scale(PT_PER_PX, PT_PER_PX)``
    the user-space coordinate system is 300dpi pixels, so all subsequent
    ``drawImage`` and crop-mark calls use pixel units. The PNG is placed to
    fill the entire bleed canvas — caller is responsible for having
    pre-rasterized at the bleed-canvas dimensions.
    """
    if not outside_png_bytes:
        raise BrochurePDFError("outside_png_bytes must be non-empty")
    if not inside_png_bytes:
        raise BrochurePDFError("inside_png_bytes must be non-empty")

    page_w = BLEED_CANVAS_WIDTH
    page_h = BLEED_CANVAS_HEIGHT
    page_w_pt = page_w * PT_PER_PX
    page_h_pt = page_h * PT_PER_PX

    buf = io.BytesIO()
    try:
        canvas = Canvas(buf, pagesize=(page_w_pt, page_h_pt))
        # User-space stays in 300dpi pixels; pagesize is in points.
        canvas.scale(PT_PER_PX, PT_PER_PX)
        # --- Page 1: outside sheet ---
        canvas.drawImage(
            ImageReader(io.BytesIO(outside_png_bytes)),
            0, 0,
            width=page_w, height=page_h,
            preserveAspectRatio=False,
        )
        _draw_crop_marks(canvas, page_h)
        canvas.showPage()
        # --- Page 2: inside sheet ---
        # showPage() resets the CTM, so re-apply the user-space scale.
        canvas.scale(PT_PER_PX, PT_PER_PX)
        canvas.drawImage(
            ImageReader(io.BytesIO(inside_png_bytes)),
            0, 0,
            width=page_w, height=page_h,
            preserveAspectRatio=False,
        )
        _draw_crop_marks(canvas, page_h)
        canvas.showPage()
        canvas.save()
    except Exception as exc:
        raise BrochurePDFError(f"PDF assembly failed: {exc}") from exc

    return buf.getvalue()
