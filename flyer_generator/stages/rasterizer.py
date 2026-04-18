"""Rasterizer -- converts SVG string to PNG bytes via cairosvg."""

import io

import cairosvg
from PIL import Image

from flyer_generator.errors import RasterizationError


class Rasterizer:
    """Convert an SVG document to a PNG image at a target pixel size.

    Defaults to 1080x1920 (flyer canvas) for backwards compatibility. Brochure
    callers pass width=3376, height=2626 (US Letter landscape bleed canvas).
    Uses cairosvg for rasterization with a Pillow dimension sanity check.
    """

    def __init__(self, width: int = 1080, height: int = 1920) -> None:
        self._width = width
        self._height = height

    def rasterize(self, svg: str) -> bytes:
        """Rasterize *svg* to PNG bytes at the configured width x height."""
        try:
            png_bytes: bytes = cairosvg.svg2png(
                bytestring=svg.encode("utf-8"),
                output_width=self._width,
                output_height=self._height,
            )
        except Exception as exc:
            raise RasterizationError(
                f"cairosvg rasterization failed: {exc}"
            ) from exc

        try:
            img = Image.open(io.BytesIO(png_bytes))
        except Exception as exc:
            raise RasterizationError(
                f"Failed to open rasterized PNG for dimension check: {exc}"
            ) from exc

        width, height = img.size
        if (width, height) != (self._width, self._height):
            raise RasterizationError(
                f"Dimension mismatch: expected {self._width}x{self._height}, "
                f"got {width}x{height}"
            )

        return png_bytes
