"""Tests for stage 4 — imagery orchestration."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from flyer_generator.brochure.generative.imagery import (
    GeneratedImagery,
    generate_imagery,
)
from flyer_generator.brochure.generative.models import (
    BrochureOutline,
    LayoutChoice,
    SectionSpec,
)
from flyer_generator.config import Settings
from flyer_generator.errors import MaxAttemptsExceededError
from flyer_generator.models import ComfyJob, VisionVerdict
from tests.brochure.fixtures.sample_brochures import FULL_BROCHURE


def _settings() -> Settings:
    return Settings(
        anthropic_api_key=SecretStr("sk-test"),
        comfycloud_api_key=SecretStr("t"),
        max_bg_attempts=3,
    )


def _outline_with_hints(*, n_hints: int) -> BrochureOutline:
    sections = [
        SectionSpec(heading="Cover", body_brief="hero", image_hint=None, panel_role="cover"),
        SectionSpec(heading="A", body_brief="x", image_hint="image a" if n_hints >= 1 else None, panel_role="feature"),
        SectionSpec(heading="B", body_brief="x", image_hint="image b" if n_hints >= 2 else None, panel_role="feature"),
        SectionSpec(heading="C", body_brief="x", image_hint="image c" if n_hints >= 3 else None, panel_role="detail"),
        SectionSpec(heading="D", body_brief="x", image_hint="image d" if n_hints >= 4 else None, panel_role="cta"),
    ]
    return BrochureOutline(
        sections=sections,
        tone="warm",
        cta_intent="visit us",
        suggested_preset="photorealistic",
        suggested_accent="#F59E0B",
    )


def _layout_choice(cover_treatment: str = "image_full") -> LayoutChoice:
    return LayoutChoice(
        template="editorial",
        shape_density="medium",
        accent_placement="top_rule",
        cover_treatment=cover_treatment,  # type: ignore[arg-type]
    )


def _approved_verdict() -> VisionVerdict:
    return VisionVerdict(
        approved=True,
        confidence=0.9,
        zones=None,
        rejection_reasons=[],
        refinement_hint="",
        text_color="white",
        mood_tags=[],
        raw_response="{}",
    )


def _rejected_verdict(hint: str = "more sky") -> VisionVerdict:
    return VisionVerdict(
        approved=False,
        confidence=0.3,
        zones=None,
        rejection_reasons=["too busy"],
        refinement_hint=hint,
        text_color="white",
        mood_tags=[],
        raw_response="{}",
    )


def _comfy_mock(n_calls: int) -> AsyncMock:
    """ComfyClient.generate returns (ComfyJob, bytes)."""
    job = ComfyJob(
        prompt_id="p",
        submitted_at=datetime(2026, 4, 18),
        positive_prompt="p",
        negative_prompt="n",
        seed=1,
        attempt_number=1,
    )
    m = AsyncMock()
    m.generate = AsyncMock(return_value=(job, b"\x89PNG-fake"))
    return m


# ---------- Happy path ----------


@pytest.mark.asyncio
async def test_generate_imagery_produces_hero_on_first_approval() -> None:
    comfy = _comfy_mock(n_calls=1)
    cover_vision = AsyncMock()
    cover_vision.evaluate = AsyncMock(return_value=_approved_verdict())

    result = await generate_imagery(
        brochure=FULL_BROCHURE,
        outline=_outline_with_hints(n_hints=0),
        layout_choice=_layout_choice(),
        settings=_settings(),
        comfy_client=comfy,
        cover_vision=cover_vision,
    )
    assert isinstance(result, GeneratedImagery)
    assert result.hero_png_bytes is not None
    assert result.hero_attempts_used == 1
    assert result.spot_images == {}


@pytest.mark.asyncio
async def test_generate_imagery_with_two_spot_hints() -> None:
    comfy = _comfy_mock(n_calls=3)
    cover_vision = AsyncMock()
    cover_vision.evaluate = AsyncMock(return_value=_approved_verdict())

    result = await generate_imagery(
        brochure=FULL_BROCHURE,
        outline=_outline_with_hints(n_hints=2),
        layout_choice=_layout_choice(),
        settings=_settings(),
        comfy_client=comfy,
        cover_vision=cover_vision,
    )
    assert result.hero_png_bytes is not None
    assert len(result.spot_images) == 2
    # 1 hero call + 2 spot calls = 3 generate() calls
    assert comfy.generate.await_count == 3


@pytest.mark.asyncio
async def test_generate_imagery_caps_spot_images_at_three() -> None:
    comfy = _comfy_mock(n_calls=4)
    cover_vision = AsyncMock()
    cover_vision.evaluate = AsyncMock(return_value=_approved_verdict())

    # Outline with 4 hints; only first 3 should produce spots
    result = await generate_imagery(
        brochure=FULL_BROCHURE,
        outline=_outline_with_hints(n_hints=4),
        layout_choice=_layout_choice(),
        settings=_settings(),
        comfy_client=comfy,
        cover_vision=cover_vision,
    )
    assert len(result.spot_images) == 3


# ---------- Shapes-only cover ----------


@pytest.mark.asyncio
async def test_shapes_only_cover_skips_hero_generation() -> None:
    comfy = _comfy_mock(n_calls=0)
    cover_vision = AsyncMock()

    result = await generate_imagery(
        brochure=FULL_BROCHURE,
        outline=_outline_with_hints(n_hints=0),
        layout_choice=_layout_choice(cover_treatment="shapes_only"),
        settings=_settings(),
        comfy_client=comfy,
        cover_vision=cover_vision,
    )
    assert result.hero_png_bytes is None
    assert result.hero_attempts_used == 0
    # No cover vision call
    assert cover_vision.evaluate.await_count == 0


# ---------- Hero regen loop ----------


@pytest.mark.asyncio
async def test_generate_imagery_retries_on_vision_rejection() -> None:
    comfy = _comfy_mock(n_calls=2)
    cover_vision = AsyncMock()
    cover_vision.evaluate = AsyncMock(
        side_effect=[_rejected_verdict("more sky"), _approved_verdict()]
    )

    result = await generate_imagery(
        brochure=FULL_BROCHURE,
        outline=_outline_with_hints(n_hints=0),
        layout_choice=_layout_choice(),
        settings=_settings(),
        comfy_client=comfy,
        cover_vision=cover_vision,
    )
    assert result.hero_attempts_used == 2


@pytest.mark.asyncio
async def test_generate_imagery_raises_after_max_attempts() -> None:
    settings = _settings()
    settings.max_bg_attempts = 2
    comfy = _comfy_mock(n_calls=2)
    cover_vision = AsyncMock()
    cover_vision.evaluate = AsyncMock(
        side_effect=[_rejected_verdict(), _rejected_verdict()]
    )

    with pytest.raises(MaxAttemptsExceededError):
        await generate_imagery(
            brochure=FULL_BROCHURE,
            outline=_outline_with_hints(n_hints=0),
            layout_choice=_layout_choice(),
            settings=settings,
            comfy_client=comfy,
            cover_vision=cover_vision,
        )
