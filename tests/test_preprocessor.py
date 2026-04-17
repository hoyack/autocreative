"""Tests for ImagePreprocessor upscale logic."""

from __future__ import annotations

import io
from datetime import datetime, timezone

import pytest
from PIL import Image

from flyer_generator.models import ComfyJob, GeneratedBackground
from flyer_generator.stages.preprocessor import ImagePreprocessor


def _make_test_png(width: int, height: int) -> bytes:
    """Create a minimal test PNG in memory."""
    img = Image.new("RGB", (width, height), color=(128, 64, 32))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture()
def mock_comfy_job() -> ComfyJob:
    return ComfyJob(
        prompt_id="test-123",
        submitted_at=datetime.now(timezone.utc),
        positive_prompt="test positive",
        negative_prompt="test negative",
        seed=42,
        attempt_number=1,
    )


@pytest.fixture()
def preprocessor() -> ImagePreprocessor:
    return ImagePreprocessor()


class TestUpscaleDimensions:
    def test_produces_correct_dimensions(
        self, preprocessor: ImagePreprocessor, mock_comfy_job: ComfyJob
    ) -> None:
        raw = _make_test_png(832, 1472)
        result = preprocessor.upscale(raw, mock_comfy_job)
        img = Image.open(io.BytesIO(result.image_bytes))
        assert img.size == (1080, 1920)

    def test_records_source_dimensions(
        self, preprocessor: ImagePreprocessor, mock_comfy_job: ComfyJob
    ) -> None:
        raw = _make_test_png(832, 1472)
        result = preprocessor.upscale(raw, mock_comfy_job)
        assert result.source_dimensions == (832, 1472)

    def test_records_final_dimensions(
        self, preprocessor: ImagePreprocessor, mock_comfy_job: ComfyJob
    ) -> None:
        raw = _make_test_png(832, 1472)
        result = preprocessor.upscale(raw, mock_comfy_job)
        assert result.final_dimensions == (1080, 1920)


class TestUpscaleReturnType:
    def test_returns_generated_background(
        self, preprocessor: ImagePreprocessor, mock_comfy_job: ComfyJob
    ) -> None:
        raw = _make_test_png(832, 1472)
        result = preprocessor.upscale(raw, mock_comfy_job)
        assert isinstance(result, GeneratedBackground)

    def test_all_fields_populated(
        self, preprocessor: ImagePreprocessor, mock_comfy_job: ComfyJob
    ) -> None:
        raw = _make_test_png(832, 1472)
        result = preprocessor.upscale(raw, mock_comfy_job)
        assert result.image_bytes
        assert result.source_dimensions
        assert result.final_dimensions
        assert result.comfy_job == mock_comfy_job


class TestUpscaleOutputFormat:
    def test_output_is_valid_png(
        self, preprocessor: ImagePreprocessor, mock_comfy_job: ComfyJob
    ) -> None:
        raw = _make_test_png(832, 1472)
        result = preprocessor.upscale(raw, mock_comfy_job)
        # Verify output can be opened as a valid PNG
        img = Image.open(io.BytesIO(result.image_bytes))
        assert img.format == "PNG"


class TestUpscaleNonStandardSource:
    def test_handles_arbitrary_source_dimensions(
        self, preprocessor: ImagePreprocessor, mock_comfy_job: ComfyJob
    ) -> None:
        """Verify it handles non-standard source dimensions, recording actual size."""
        raw = _make_test_png(640, 480)
        result = preprocessor.upscale(raw, mock_comfy_job)
        assert result.source_dimensions == (640, 480)
        assert result.final_dimensions == (1080, 1920)
        # Output should still be 1080x1920
        img = Image.open(io.BytesIO(result.image_bytes))
        assert img.size == (1080, 1920)
