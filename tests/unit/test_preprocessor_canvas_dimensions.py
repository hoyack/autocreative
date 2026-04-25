"""Tests for ImagePreprocessor's parameterized final_dimensions kwarg.

Phase 24-02: ImagePreprocessor must accept an optional `final_dimensions`
constructor kwarg so the poster pipeline can upscale to larger canvases
(5400×7200, 7200×10800, 8100×12000) while the existing flyer pipeline
keeps the (1080, 1920) default.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

import pytest
from PIL import Image

from flyer_generator.models import ComfyJob
from flyer_generator.stages.preprocessor import ImagePreprocessor


def _make_test_png(width: int, height: int) -> bytes:
    img = Image.new("RGB", (width, height), color=(128, 64, 32))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture()
def mock_comfy_job() -> ComfyJob:
    return ComfyJob(
        prompt_id="test-canvas-dims",
        submitted_at=datetime.now(timezone.utc),
        positive_prompt="test positive",
        negative_prompt="test negative",
        seed=42,
        attempt_number=1,
    )


class TestDefaultConstructor:
    def test_default_constructor_final_dimensions_1080x1920(self) -> None:
        """No-arg constructor preserves Phase 1 behavior — back-compat."""
        pp = ImagePreprocessor()
        assert pp._final_dimensions == (1080, 1920)

    def test_default_constructor_upscales_to_1080x1920(
        self, mock_comfy_job: ComfyJob
    ) -> None:
        pp = ImagePreprocessor()
        raw = _make_test_png(832, 1472)
        result = pp.upscale(raw, mock_comfy_job)
        assert result.final_dimensions == (1080, 1920)
        img = Image.open(io.BytesIO(result.image_bytes))
        assert img.size == (1080, 1920)


class TestPosterDimensions:
    """Verify each of the 3 locked poster sizes (300 DPI) upscales correctly."""

    def test_18x24_5400x7200(self, mock_comfy_job: ComfyJob) -> None:
        pp = ImagePreprocessor(final_dimensions=(5400, 7200))
        assert pp._final_dimensions == (5400, 7200)
        raw = _make_test_png(832, 1472)
        result = pp.upscale(raw, mock_comfy_job)
        assert result.final_dimensions == (5400, 7200)
        img = Image.open(io.BytesIO(result.image_bytes))
        assert img.size == (5400, 7200)

    def test_24x36_7200x10800(self, mock_comfy_job: ComfyJob) -> None:
        pp = ImagePreprocessor(final_dimensions=(7200, 10800))
        assert pp._final_dimensions == (7200, 10800)
        raw = _make_test_png(832, 1472)
        result = pp.upscale(raw, mock_comfy_job)
        assert result.final_dimensions == (7200, 10800)
        img = Image.open(io.BytesIO(result.image_bytes))
        assert img.size == (7200, 10800)

    def test_27x40_8100x12000(self, mock_comfy_job: ComfyJob) -> None:
        pp = ImagePreprocessor(final_dimensions=(8100, 12000))
        assert pp._final_dimensions == (8100, 12000)
        raw = _make_test_png(832, 1472)
        result = pp.upscale(raw, mock_comfy_job)
        assert result.final_dimensions == (8100, 12000)
        img = Image.open(io.BytesIO(result.image_bytes))
        assert img.size == (8100, 12000)
