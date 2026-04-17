"""Tests for flyer_generator.stages.rasterizer -- SVG to PNG conversion."""

import io

import pytest
from PIL import Image

from flyer_generator.errors import RasterizationError
from flyer_generator.stages.rasterizer import Rasterizer

# Minimal valid SVG at the target canvas dimensions.
_VALID_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920">'
    '<rect width="1080" height="1920" fill="blue"/>'
    "</svg>"
)


class TestRasterizer:
    """Verify Rasterizer.rasterize() produces correct PNG output."""

    def setup_method(self) -> None:
        self.rasterizer = Rasterizer()

    def test_rasterize_valid_svg_returns_bytes(self) -> None:
        """Valid SVG produces non-empty bytes output."""
        result = self.rasterizer.rasterize(_VALID_SVG)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_rasterize_produces_valid_png(self) -> None:
        """Output starts with PNG magic bytes."""
        result = self.rasterizer.rasterize(_VALID_SVG)
        assert result[:4] == b"\x89PNG"

    def test_rasterize_dimensions_1080x1920(self) -> None:
        """Output image is exactly 1080x1920 pixels."""
        result = self.rasterizer.rasterize(_VALID_SVG)
        img = Image.open(io.BytesIO(result))
        assert img.size == (1080, 1920)

    def test_rasterize_invalid_svg_raises_rasterization_error(self) -> None:
        """Garbage input raises RasterizationError."""
        with pytest.raises(RasterizationError, match="rasterization failed"):
            self.rasterizer.rasterize("not svg at all")

    def test_rasterize_empty_string_raises_rasterization_error(self) -> None:
        """Empty string raises RasterizationError."""
        with pytest.raises(RasterizationError):
            self.rasterizer.rasterize("")

    def test_rasterize_malformed_xml_raises_rasterization_error(self) -> None:
        """Malformed XML raises RasterizationError."""
        with pytest.raises(RasterizationError):
            self.rasterizer.rasterize("<svg><unclosed")

    def test_rasterize_error_wraps_original_exception(self) -> None:
        """RasterizationError preserves the original cause via __cause__."""
        with pytest.raises(RasterizationError) as exc_info:
            self.rasterizer.rasterize("not svg")
        assert exc_info.value.__cause__ is not None
