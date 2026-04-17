"""Integration tests for FlyerGenerator pipeline with mocked stages."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from flyer_generator.config import Settings
from flyer_generator.errors import MaxAttemptsExceededError
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
# Fixtures
# ---------------------------------------------------------------------------


def _mock_settings(max_bg_attempts: int = 3) -> Settings:
    return Settings(
        anthropic_api_key=SecretStr("test-key"),
        comfycloud_api_key=SecretStr("test-key"),
        max_bg_attempts=max_bg_attempts,
    )


def _sample_event() -> EventInput:
    return EventInput(
        title="Neighborhood Clean-Up Day",
        date="Saturday, May 2, 2026",
        time="9:00 AM - 12:00 PM",
        location_name="Riverside Park Pavilion",
        location_address="123 Park Rd, San Antonio, TX 78205",
        fees="FREE",
        org="Friends of Riverside Park",
        style_concept="community outdoor event, park setting",
        style_preset="photorealistic",
    )


def _sample_comfy_job() -> ComfyJob:
    return ComfyJob(
        prompt_id="test-prompt-123",
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


def _sample_verdict_rejected(
    reasons: list[str] | None = None,
    hint: str = "add more light",
) -> VisionVerdict:
    return VisionVerdict(
        approved=False,
        confidence=0.3,
        rejection_reasons=reasons or ["too dark"],
        refinement_hint=hint,
        raw_response="{}",
    )


def _sample_resolved_layout() -> ResolvedLayout:
    return ResolvedLayout(
        title=ZoneCoord(x=540, y=320, anchor="middle"),
        details=ZoneCoord(x=540, y=1600, anchor="middle"),
        fee_badge=ZoneCoord(x=900, y=320, anchor="end"),
        org_credit=ZoneCoord(x=540, y=1600, anchor="middle"),
    )


def _sample_background(comfy_job: ComfyJob | None = None) -> GeneratedBackground:
    return GeneratedBackground(
        image_bytes=b"fake-upscaled-png",
        source_dimensions=(832, 1472),
        final_dimensions=(1080, 1920),
        comfy_job=comfy_job or _sample_comfy_job(),
    )


# ---------------------------------------------------------------------------
# Helper: Build generator with mocked stages
# ---------------------------------------------------------------------------


def _build_generator_with_mocks(
    settings: Settings | None = None,
    vision_returns: list[VisionVerdict] | None = None,
) -> FlyerGenerator:
    """Create a FlyerGenerator with all stages replaced by mocks."""
    settings = settings or _mock_settings()
    comfy_job = _sample_comfy_job()

    gen = FlyerGenerator(
        settings=settings,
        presets=MagicMock(),
        http_client=MagicMock(),
    )

    # Mock prompt builder
    mock_workflow = MagicMock()
    mock_workflow.positive_prompt = "test positive prompt"
    mock_workflow.negative_prompt = "test negative prompt"
    mock_workflow.seed = 42
    gen._prompt_builder = MagicMock()
    gen._prompt_builder.build = MagicMock(return_value=mock_workflow)

    # Mock comfy client (async)
    gen._comfy_client = MagicMock()
    gen._comfy_client.generate = AsyncMock(return_value=(comfy_job, b"fake-png"))

    # Mock preprocessor
    gen._preprocessor = MagicMock()
    gen._preprocessor.upscale = MagicMock(return_value=_sample_background(comfy_job))

    # Mock vision evaluator (async)
    if vision_returns is None:
        vision_returns = [_sample_verdict_approved()]
    gen._vision = MagicMock()
    gen._vision.evaluate = AsyncMock(side_effect=list(vision_returns))

    # Mock layout resolver
    gen._layout = MagicMock()
    gen._layout.resolve = MagicMock(return_value=_sample_resolved_layout())

    # Mock composer
    gen._composer = MagicMock()
    gen._composer.compose = MagicMock(return_value="<svg>test</svg>")

    # Mock rasterizer
    gen._rasterizer = MagicMock()
    gen._rasterizer.rasterize = MagicMock(return_value=b"fake-png-output")

    return gen


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGenerateFirstAttemptSuccess:
    async def test_generate_first_attempt_success(self) -> None:
        gen = _build_generator_with_mocks()
        event = _sample_event()

        result = await gen.generate(event)

        assert isinstance(result, FlyerOutput)
        assert result.attempts_used == 1
        assert result.png_bytes == b"fake-png-output"
        assert result.dimensions == (1080, 1920)
        assert result.event_title == event.title
        assert len(result.trace_id) == 32
        assert result.final_vision_verdict.approved is True

        # Verify stages were called once
        gen._prompt_builder.build.assert_called_once()
        gen._comfy_client.generate.assert_called_once()
        gen._preprocessor.upscale.assert_called_once()
        gen._vision.evaluate.assert_called_once()
        gen._layout.resolve.assert_called_once()
        gen._composer.compose.assert_called_once()
        gen._rasterizer.rasterize.assert_called_once()


class TestGenerateRetryOnRejection:
    async def test_generate_retry_on_rejection(self) -> None:
        gen = _build_generator_with_mocks(
            vision_returns=[
                _sample_verdict_rejected(reasons=["too dark"], hint="add more light"),
                _sample_verdict_approved(),
            ],
        )
        event = _sample_event()

        result = await gen.generate(event)

        assert result.attempts_used == 2
        assert result.final_vision_verdict.approved is True

        # Prompt builder called twice
        assert gen._prompt_builder.build.call_count == 2

        # Second call should include refinement_hint
        second_call_args = gen._prompt_builder.build.call_args_list[1]
        assert second_call_args[0][2] == "add more light"  # refinement_hint


class TestGenerateMaxAttemptsExceeded:
    async def test_generate_max_attempts_exceeded(self) -> None:
        settings = _mock_settings(max_bg_attempts=3)
        gen = _build_generator_with_mocks(
            settings=settings,
            vision_returns=[
                _sample_verdict_rejected(reasons=["too dark"]),
                _sample_verdict_rejected(reasons=["too cluttered"]),
                _sample_verdict_rejected(reasons=["wrong mood"]),
            ],
        )
        event = _sample_event()

        with pytest.raises(MaxAttemptsExceededError, match="Rejection history"):
            await gen.generate(event)

        # All 3 attempts exhausted
        assert gen._prompt_builder.build.call_count == 3
        assert gen._vision.evaluate.call_count == 3


class TestTraceId:
    async def test_generate_trace_id_is_uuid4_hex(self) -> None:
        gen = _build_generator_with_mocks()
        event = _sample_event()

        result = await gen.generate(event)

        # UUID4 hex is exactly 32 hex characters
        assert len(result.trace_id) == 32
        int(result.trace_id, 16)  # Should not raise -- valid hex


class TestDefaultConstruction:
    def test_generate_default_presets(self) -> None:
        settings = _mock_settings()
        # Should not raise when presets is None (uses build_default_registry)
        gen = FlyerGenerator(settings=settings, http_client=MagicMock())
        assert gen._prompt_builder is not None

    def test_generate_default_http_client(self) -> None:
        settings = _mock_settings()
        # Should not raise when http_client is None (creates its own)
        gen = FlyerGenerator(settings=settings)
        assert gen._owns_http is True
        assert gen._comfy_client is not None
