"""Rasterizer -- converts SVG string to PNG bytes via cairosvg."""

import io

import cairosvg
from PIL import Image

from flyer_generator.errors import RasterizationError


class Rasterizer:
    """Convert an SVG document to a 1080x1920 PNG image.

    Uses cairosvg for rasterization with a Pillow dimension sanity check.
    """

    def rasterize(self, svg: str) -> bytes:
        """Rasterize *svg* to PNG bytes at 1080x1920.

        Parameters
        ----------
        svg:
            Complete SVG document as a string.

        Returns
        -------
        PNG image bytes at exactly 1080x1920 pixels.

        Raises
        ------
        RasterizationError
            If cairosvg fails or the output dimensions are wrong.
        """
        try:
            png_bytes: bytes = cairosvg.svg2png(
                bytestring=svg.encode("utf-8"),
                output_width=1080,
                output_height=1920,
            )
        except Exception as exc:
            raise RasterizationError(
                f"cairosvg rasterization failed: {exc}"
            ) from exc

        # Sanity-check dimensions via Pillow.
        try:
            img = Image.open(io.BytesIO(png_bytes))
        except Exception as exc:
            raise RasterizationError(
                f"Failed to open rasterized PNG for dimension check: {exc}"
            ) from exc

        width, height = img.size
        if (width, height) != (1080, 1920):
            raise RasterizationError(
                f"Dimension mismatch: expected 1080x1920, "
                f"got {width}x{height}"
            )

        return png_bytes
