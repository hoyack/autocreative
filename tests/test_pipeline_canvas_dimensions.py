"""Tests for FlyerGenerator.canvas_dimensions kwarg (Phase 24-02 — PO-02).

`FlyerGenerator.__init__` accepts an optional ``canvas_dimensions: tuple[int, int]``
keyword. When None (default), the pipeline falls back to (1080, 1920) — preserving
byte-identical behavior for the existing flyer worker which calls
``FlyerGenerator(settings=..., http_client=...)`` with no canvas_dimensions kwarg.

When supplied (e.g. (5400, 7200) for 18×24" posters at 300 DPI), the entire stage
chain — preprocessor upscale, composer canvas math, rasterizer output dims, and
FlyerOutput.dimensions — operates at the injected size.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from flyer_generator.config import Settings
from flyer_generator.models import (
    ComfyJob,
    EventInput,
    FlyerOutput,
    GeneratedBackground,
    LayoutZones,
    ResolvedLayout,
    VisionVerdict,
)
from flyer_generator.pipeline import FlyerGenerator
from flyer_generator.zones import ZoneCoord


# ---------------------------------------------------------------------------
# Fixtures (mirror tests/test_pipeline.py shapes)
# ---------------------------------------------------------------------------


def _mock_settings() -> Settings:
    return Settings(
        anthropic_api_key=SecretStr("test-key"),
        comfycloud_api_key=SecretStr("test-key"),
        max_bg_attempts=3,
    )


def _sample_event() -> EventInput:
    return EventInput(
        title="Poster Day",
        date="Saturday, May 2, 2026",
        time="9:00 AM",
        location_name="Town Plaza",
        location_address="100 Main St, Springfield",
        fees="FREE",
        org="Civic League",
        style_concept="bold poster, festival art",
        style_preset="photorealistic",
    )


def _sample_comfy_job() -> ComfyJob:
    return ComfyJob(
        prompt_id="test-prompt-canvas",
        submitted_at=datetime.now(timezone.utc),
        positive_prompt="test positive prompt",
        negative_prompt="test negative prompt",
        seed=42,
        attempt_number=1,
    )


def _sample_verdict_approved() -> VisionVerdict:
    return VisionVerdict(
        approved=True,
        confidence=0.9,
        zones=LayoutZones(
            title="TOP_CENTER",
            details="BOTTOM_CENTER",
            fee_badge="TOP_RIGHT",
            org_credit="BOTTOM_CENTER",
        ),
        text_color="white",
        raw_response="{}",
    )


def _sample_resolved_layout() -> ResolvedLayout:
    return ResolvedLayout(
        title=ZoneCoord(x=540, y=320, anchor="middle"),
        details=ZoneCoord(x=540, y=1600, anchor="middle"),
        fee_badge=ZoneCoord(x=900, y=320, anchor="end"),
        org_credit=ZoneCoord(x=540, y=1600, anchor="middle"),
    )


def _sample_background(comfy_job: ComfyJob, dims: tuple[int, int]) -> GeneratedBackground:
    return GeneratedBackground(
        image_bytes=b"fake-upscaled-png",
        source_dimensions=(832, 1472),
        final_dimensions=dims,
        comfy_job=comfy_job,
    )


def _build_generator(
    canvas_dimensions: tuple[int, int] | None = None,
    *,
    mock_stages: bool = True,
) -> FlyerGenerator:
    """Construct a FlyerGenerator. When ``mock_stages`` is True, replace all
    runtime stages with mocks so generate(...) works end-to-end without
    network or rasterization. Stage instances themselves (set in __init__)
    are preserved for assertions about constructor wiring.
    """
    settings = _mock_settings()

    # Construct via canvas_dimensions kwarg. When None we use default constructor.
    if canvas_dimensions is None:
        gen = FlyerGenerator(
            settings=settings,
            presets=MagicMock(),
            http_client=MagicMock(),
        )
    else:
        gen = FlyerGenerator(
            settings=settings,
            presets=MagicMock(),
            http_client=MagicMock(),
            canvas_dimensions=canvas_dimensions,
        )

    if not mock_stages:
        return gen

    # Mock prompt builder
    mock_workflow = MagicMock()
    mock_workflow.positive_prompt = "test positive prompt"
    mock_workflow.negative_prompt = "test negative prompt"
    mock_workflow.seed = 42
    gen._prompt_builder = MagicMock()
    gen._prompt_builder.build = MagicMock(return_value=mock_workflow)

    # Mock comfy client (async)
    comfy_job = _sample_comfy_job()
    gen._comfy_client = MagicMock()
    gen._comfy_client.generate = AsyncMock(return_value=(comfy_job, b"fake-png"))

    # Mock preprocessor — pretend it produces an upscaled background.
    # Preserve the real instance for inspection (kept as gen._preprocessor)
    # but swap its upscale() with a mock.
    fake_dims = canvas_dimensions or (1080, 1920)
    gen._preprocessor.upscale = MagicMock(  # type: ignore[method-assign]
        return_value=_sample_background(comfy_job, fake_dims),
    )

    # Mock vision (async)
    gen._vision = MagicMock()
    gen._vision.evaluate = AsyncMock(return_value=_sample_verdict_approved())

    # Mock layout
    gen._layout = MagicMock()
    gen._layout.resolve = MagicMock(return_value=_sample_resolved_layout())

    # Mock composer — preserve instance for inspection, swap compose()
    gen._composer.compose = MagicMock(return_value="<svg>test</svg>")  # type: ignore[method-assign]

    # Mock rasterizer — preserve instance for inspection, swap rasterize()
    gen._rasterizer.rasterize = MagicMock(return_value=b"fake-png-output")  # type: ignore[method-assign]

    return gen


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestConstructorAcceptsCanvasDimensions:
    def test_constructor_signature_has_canvas_dimensions(self) -> None:
        sig = inspect.signature(FlyerGenerator.__init__)
        assert "canvas_dimensions" in sig.parameters
        # Default must be None for back-compat.
        assert sig.parameters["canvas_dimensions"].default is None
        # Must be keyword-only.
        assert (
            sig.parameters["canvas_dimensions"].kind
            == inspect.Parameter.KEYWORD_ONLY
        )


class TestDefaultCanvasDimensionsBackCompat:
    """No-arg call site (existing flyer worker) keeps (1080, 1920) behavior."""

    def test_default_canvas_dimensions_back_compat(self) -> None:
        gen = _build_generator(canvas_dimensions=None, mock_stages=False)
        assert gen._canvas_dimensions == (1080, 1920)

    def test_default_threading_to_stages(self) -> None:
        gen = _build_generator(canvas_dimensions=None, mock_stages=False)
        assert gen._preprocessor._final_dimensions == (1080, 1920)
        assert gen._composer._canvas_width == 1080
        assert gen._rasterizer._width == 1080
        assert gen._rasterizer._height == 1920


class TestPosterCanvasDimensions:
    """Each of the 3 locked poster sizes threads correctly to all stages."""

    @pytest.mark.parametrize(
        "dims",
        [
            pytest.param((5400, 7200), id="18x24"),
            pytest.param((7200, 10800), id="24x36"),
            pytest.param((8100, 12000), id="27x40"),
        ],
    )
    def test_canvas_dimensions_threads_to_preprocessor_and_composer_and_rasterizer(
        self, dims: tuple[int, int]
    ) -> None:
        gen = _build_generator(canvas_dimensions=dims, mock_stages=False)
        assert gen._canvas_dimensions == dims
        assert gen._preprocessor._final_dimensions == dims
        assert gen._composer._canvas_width == dims[0]
        assert gen._rasterizer._width == dims[0]
        assert gen._rasterizer._height == dims[1]


class TestFlyerOutputDimensionsReflectsCanvas:
    """FlyerOutput.dimensions equals the constructor kwarg, not a hardcoded literal."""

    async def test_default_output_dimensions_1080x1920(self) -> None:
        gen = _build_generator(canvas_dimensions=None)
        result = await gen.generate(_sample_event())
        assert isinstance(result, FlyerOutput)
        assert result.dimensions == (1080, 1920)

    @pytest.mark.parametrize(
        "dims",
        [
            pytest.param((5400, 7200), id="18x24"),
            pytest.param((7200, 10800), id="24x36"),
            pytest.param((8100, 12000), id="27x40"),
        ],
    )
    async def test_poster_output_dimensions_reflects_canvas_dimensions(
        self, dims: tuple[int, int]
    ) -> None:
        gen = _build_generator(canvas_dimensions=dims)
        result = await gen.generate(_sample_event())
        assert isinstance(result, FlyerOutput)
        assert result.dimensions == dims
