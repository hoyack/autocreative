"""PDF assembly for the brochure — 2-page PDF that matches the source PNG aspect.

Takes the two rasterized sheet PNGs (outside + inside) and assembles them
into a 2-page PDF whose **page size is derived from the actual PNG
dimensions at 300 dpi**, so the image is never stretched. If the schema
renderer emits 1080×1920 PNGs the PDF is 3.6×6.4 in. If it emits
3376×2626 sheets the PDF is 11.25×8.75 in. The PDF reflects whatever the
renderer produced — 1:1, no aspect-ratio distortion.

This replaces the prior bleed-canvas / fixed-letter-trim assumption (which
stretched a 1080×1920 PNG into an 11×8.5 landscape page, producing the
visible vertical squash + black-bar artifacts the user flagged at
260425-nwj). Bleed/crop-marks belong to the renderer if it chooses a
bleed-canvas output; the PDF assembler is now agnostic.

Depends on `reportlab` (pure-Python PDF toolkit) for drawing + page assembly.
"""

from __future__ import annotations

import io

from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

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

def _png_size(png_bytes: bytes) -> tuple[int, int]:
    """Return ``(width_px, height_px)`` of a PNG byte stream."""
    with Image.open(io.BytesIO(png_bytes)) as img:
        return img.size


def _flatten_to_white(png_bytes: bytes) -> bytes:
    """If the PNG has alpha, composite onto a white background.

    The schema renderer can emit RGBA PNGs whose top/bottom bands are fully
    transparent (alpha=0). Without flattening, those transparent regions
    print as either black bars (some viewers/printers) or unpredictable
    paper-color (others). Compositing onto white guarantees consistent
    output on every printer. PNGs without alpha are returned unchanged.
    """
    with Image.open(io.BytesIO(png_bytes)) as img:
        if img.mode != "RGBA" and not (img.mode == "P" and "transparency" in img.info):
            return png_bytes
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[3])
        out = io.BytesIO()
        bg.save(out, "PNG")
        return out.getvalue()


def assemble_brochure_pdf(
    outside_png_bytes: bytes,
    inside_png_bytes: bytes,
) -> bytes:
    """Build a 2-page PDF: page 1 = outside sheet, page 2 = inside sheet.

    Page dimensions are derived from the source PNGs at 300 dpi. Both PNGs
    must share dimensions; that shared (W, H) becomes the PDF page size in
    PostScript points (W * 72/300, H * 72/300). The PNG fills the page
    1:1 — no offset, no bleed clipping, no aspect-ratio distortion.

    The PDF reflects whatever the renderer produced: a 1080×1920 portrait
    panel becomes a 3.6×6.4 in PDF, a 3376×2626 bleed sheet becomes an
    11.25×8.75 in PDF. If the renderer changes its output dimensions,
    the PDF tracks automatically.
    """
    if not outside_png_bytes:
        raise BrochurePDFError("outside_png_bytes must be non-empty")
    if not inside_png_bytes:
        raise BrochurePDFError("inside_png_bytes must be non-empty")

    try:
        outside_size = _png_size(outside_png_bytes)
        inside_size = _png_size(inside_png_bytes)
    except Exception as exc:
        raise BrochurePDFError(f"PDF assembly failed: {exc}") from exc

    if outside_size != inside_size:
        raise BrochurePDFError(
            f"outside and inside PNGs must share dimensions; got "
            f"outside={outside_size} inside={inside_size}"
        )

    # Flatten any alpha channel onto white so transparent canvas regions
    # print clean instead of as black bars.
    outside_png_bytes = _flatten_to_white(outside_png_bytes)
    inside_png_bytes = _flatten_to_white(inside_png_bytes)

    page_w_px, page_h_px = outside_size
    page_w_pt = page_w_px * PT_PER_PX
    page_h_pt = page_h_px * PT_PER_PX

    buf = io.BytesIO()
    try:
        canvas = Canvas(buf, pagesize=(page_w_pt, page_h_pt))
        # User-space stays in 300dpi pixels; pagesize is in points.
        canvas.scale(PT_PER_PX, PT_PER_PX)
        # --- Page 1: outside sheet ---
        canvas.drawImage(
            ImageReader(io.BytesIO(outside_png_bytes)),
            0, 0,
            width=page_w_px, height=page_h_px,
            preserveAspectRatio=False,
        )
        canvas.showPage()
        # --- Page 2: inside sheet ---
        # showPage() resets the CTM, so re-apply the user-space scale.
        canvas.scale(PT_PER_PX, PT_PER_PX)
        canvas.drawImage(
            ImageReader(io.BytesIO(inside_png_bytes)),
            0, 0,
            width=page_w_px, height=page_h_px,
            preserveAspectRatio=False,
        )
        canvas.showPage()
        canvas.save()
    except Exception as exc:
        raise BrochurePDFError(f"PDF assembly failed: {exc}") from exc

    return buf.getvalue()
