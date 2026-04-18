"""Integration tests for BrochureGenerator with mocked Comfy + vision.

Verifies: regen loop on vision rejection, MaxAttemptsExceededError on exhaustion, happy-path produces BrochureOutput with non-empty PNGs + PDF + trace_id.
"""

from __future__ import annotations

import io
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from PIL import Image
from pydantic import SecretStr

from flyer_generator.brochure.models import BrochureOutput
from flyer_generator.brochure.pipeline import BrochureGenerator
from flyer_generator.brochure.stages.layout import (
    BLEED_CANVAS_HEIGHT,
    BLEED_CANVAS_WIDTH,
)
from flyer_generator.config import Settings
from flyer_generator.errors import MaxAttemptsExceededError
from flyer_generator.models import ComfyJob, VisionVerdict
from tests.brochure.fixtures.sample_brochures import FULL_BROCHURE


def _hero_png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1472, 832), (180, 140, 100)).save(buf, "PNG")
    return buf.getvalue()


def _settings() -> Settings:
    return Settings(
        anthropic_api_key=SecretStr("sk-test"),
        comfycloud_api_key=SecretStr("test"),
        max_bg_attempts=3,
        vision_confidence_threshold=0.6,
    )


def _fake_comfy_job() -> ComfyJob:
    from datetime import datetime

    return ComfyJob(
        prompt_id="test-prompt-id",
        submitted_at=datetime(2026, 4, 18),
        positive_prompt="p",
        negative_prompt="n",
        seed=42,
        attempt_number=1,
    )


def _approved_verdict() -> VisionVerdict:
    return VisionVerdict(
        approved=True,
        confidence=0.9,
        rejection_reasons=[],
        refinement_hint="",
        zones=None,
        text_color="white",
        mood_tags=["professional"],
        raw_response="{}",
    )


def _rejected_verdict(hint: str = "more clean sky") -> VisionVerdict:
    return VisionVerdict(
        approved=False,
        confidence=0.3,
        rejection_reasons=["too busy"],
        refinement_hint=hint,
        zones=None,
        text_color="white",
        mood_tags=[],
        raw_response="{}",
    )


def _install_mocks(
    gen: BrochureGenerator,
    *,
    verdicts: list[VisionVerdict],
) -> None:
    """Replace comfy_client and vision stages with mocks that return canned responses."""
    hero = _hero_png_bytes()
    job = _fake_comfy_job()
    gen._comfy_client.generate = AsyncMock(return_value=(job, hero))
    gen._vision.evaluate = AsyncMock(side_effect=verdicts)


@pytest.mark.asyncio
async def test_generate_produces_brochure_output_on_first_approval() -> None:
    gen = BrochureGenerator(_settings(), http_client=SimpleNamespace())  # type: ignore[arg-type]
    _install_mocks(gen, verdicts=[_approved_verdict()])

    result = await gen.generate(FULL_BROCHURE)

    assert isinstance(result, BrochureOutput)
    assert result.attempts_used == 1
    assert len(result.front_png_bytes) > 0
    assert len(result.back_png_bytes) > 0
    assert result.pdf_bytes.startswith(b"%PDF-")
    assert result.dimensions == (BLEED_CANVAS_WIDTH, BLEED_CANVAS_HEIGHT)
    assert result.trace_id
    assert result.hero_vision_verdict.approved is True


@pytest.mark.asyncio
async def test_regen_loop_retries_on_rejection_then_approves() -> None:
    gen = BrochureGenerator(_settings(), http_client=SimpleNamespace())  # type: ignore[arg-type]
    _install_mocks(
        gen,
        verdicts=[_rejected_verdict("more sky"), _approved_verdict()],
    )

    result = await gen.generate(FULL_BROCHURE)
    assert result.attempts_used == 2
    # Vision called twice.
    assert gen._vision.evaluate.await_count == 2


@pytest.mark.asyncio
async def test_max_attempts_exceeded_raises() -> None:
    settings = _settings()
    settings.max_bg_attempts = 2
    gen = BrochureGenerator(settings, http_client=SimpleNamespace())  # type: ignore[arg-type]
    _install_mocks(
        gen,
        verdicts=[_rejected_verdict("sky"), _rejected_verdict("brighter")],
    )

    with pytest.raises(MaxAttemptsExceededError):
        await gen.generate(FULL_BROCHURE)


@pytest.mark.asyncio
async def test_save_writes_three_files(tmp_path) -> None:
    gen = BrochureGenerator(_settings(), http_client=SimpleNamespace())  # type: ignore[arg-type]
    _install_mocks(gen, verdicts=[_approved_verdict()])

    result = await gen.generate(FULL_BROCHURE)
    target = tmp_path / "out"
    result.save(target)

    assert (target / "brochure_front.png").exists()
    assert (target / "brochure_back.png").exists()
    assert (target / "brochure_print.pdf").exists()
    assert (target / "brochure_print.pdf").read_bytes().startswith(b"%PDF-")
