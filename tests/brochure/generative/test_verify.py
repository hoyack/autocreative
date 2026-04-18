"""Tests for stage 7 — verification (rubric scoring)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from flyer_generator.brochure.generative.models import (
    BrochureOutline,
    SectionSpec,
    VerificationVerdict,
)
from flyer_generator.brochure.generative.verify import (
    BrochureVerificationError,
    verify_brochure,
    verify_with_text_critique,
)
from flyer_generator.config import Settings
from flyer_generator.models import VisionVerdict


def _settings() -> Settings:
    return Settings(
        anthropic_api_key=SecretStr("sk-test"),
        comfycloud_api_key=SecretStr("t"),
    )


def _outline() -> BrochureOutline:
    return BrochureOutline(
        sections=[
            SectionSpec(heading="Hero", body_brief="x", image_hint=None, panel_role="cover"),
            SectionSpec(heading="Details", body_brief="y", image_hint=None, panel_role="feature"),
        ],
        tone="warm",
        cta_intent="book",
        suggested_preset="photorealistic",
        suggested_accent="#2E8B57",
    )


def _visiver(approved: bool, confidence: float, hint: str = "") -> VisionVerdict:
    return VisionVerdict(
        approved=approved,
        confidence=confidence,
        zones=None,
        rejection_reasons=[] if approved else ["generic"],
        refinement_hint=hint,
        text_color="white",
        mood_tags=[],
        raw_response="{}",
    )


# ---------- verify_brochure (vision-based) ----------


@pytest.mark.asyncio
async def test_verify_brochure_high_score_no_weakest_stage() -> None:
    evaluator = AsyncMock()
    evaluator.evaluate_cover = AsyncMock(return_value=_visiver(approved=True, confidence=0.85))

    verdict = await verify_brochure(
        outside_png_bytes=b"png-outside",
        inside_png_bytes=b"png-inside",
        original_prompt="a brochure",
        outline=_outline(),
        settings=_settings(),
        vision_evaluator=evaluator,
    )
    assert isinstance(verdict, VerificationVerdict)
    assert verdict.score == 85
    assert verdict.weakest_stage is None


@pytest.mark.asyncio
async def test_verify_brochure_low_score_flags_weakest_stage() -> None:
    evaluator = AsyncMock()
    evaluator.evaluate_cover = AsyncMock(
        return_value=_visiver(approved=True, confidence=0.5, hint="more balance")
    )

    verdict = await verify_brochure(
        outside_png_bytes=b"png",
        inside_png_bytes=b"png",
        original_prompt="a brochure",
        outline=_outline(),
        settings=_settings(),
        vision_evaluator=evaluator,
    )
    assert verdict.score == 50
    # Low + approved → compose
    assert verdict.weakest_stage == "compose"
    # Two-sheet merge prefixes critiques by sheet label
    assert "more balance" in verdict.critique
    assert "[outside]" in verdict.critique and "[inside]" in verdict.critique


@pytest.mark.asyncio
async def test_verify_brochure_rejected_flags_text_stage() -> None:
    evaluator = AsyncMock()
    evaluator.evaluate_cover = AsyncMock(
        return_value=_visiver(approved=False, confidence=0.4)
    )

    verdict = await verify_brochure(
        outside_png_bytes=b"png",
        inside_png_bytes=b"png",
        original_prompt="a brochure",
        outline=_outline(),
        settings=_settings(),
        vision_evaluator=evaluator,
    )
    assert verdict.score == 40
    assert verdict.weakest_stage == "text"


@pytest.mark.asyncio
async def test_verify_brochure_uses_rubric_json_when_present() -> None:
    """When raw_response contains a rubric JSON, parsed dims override uniform confidence."""
    rubric = json.dumps(
        {
            "dimension_scores": {
                "content_fit": 92,
                "visual_balance": 60,
                "text_legibility": 88,
                "layout_coherence": 75,
                "print_readiness": 70,
            },
            "critique": "visual balance is off on the tuck flap",
            "weakest_stage": "layout",
        }
    )
    verdict_in = VisionVerdict(
        approved=True,
        confidence=0.5,  # would give uniform 50 — proves rubric wins
        zones=None,
        rejection_reasons=[],
        refinement_hint="",
        text_color="white",
        mood_tags=[],
        raw_response=rubric,
    )
    evaluator = AsyncMock()
    evaluator.evaluate_cover = AsyncMock(return_value=verdict_in)

    verdict = await verify_brochure(
        outside_png_bytes=b"png",
        inside_png_bytes=b"png",
        original_prompt="a brochure",
        outline=_outline(),
        settings=_settings(),
        vision_evaluator=evaluator,
    )
    # (92+60+88+75+70)/5 = 77
    assert verdict.score == 77
    assert verdict.dimension_scores["content_fit"] == 92
    assert verdict.dimension_scores["visual_balance"] == 60
    # Dimensions must be heterogeneous — that's the whole point
    assert len(set(verdict.dimension_scores.values())) > 1
    assert verdict.weakest_stage == "layout"
    assert "visual balance" in verdict.critique


@pytest.mark.asyncio
async def test_verify_brochure_falls_back_when_rubric_malformed() -> None:
    """Malformed raw_response → fall back to confidence-based uniform dims."""
    verdict_in = VisionVerdict(
        approved=True,
        confidence=0.8,
        zones=None,
        rejection_reasons=[],
        refinement_hint="looks good",
        text_color="white",
        mood_tags=[],
        raw_response="not json at all",
    )
    evaluator = AsyncMock()
    evaluator.evaluate_cover = AsyncMock(return_value=verdict_in)

    verdict = await verify_brochure(
        outside_png_bytes=b"png",
        inside_png_bytes=b"png",
        original_prompt="p",
        outline=_outline(),
        settings=_settings(),
        vision_evaluator=evaluator,
    )
    assert verdict.score == 80
    # Uniform dims — fallback path signature
    assert len(set(verdict.dimension_scores.values())) == 1


@pytest.mark.asyncio
async def test_verify_brochure_iteration_field_set() -> None:
    evaluator = AsyncMock()
    evaluator.evaluate_cover = AsyncMock(return_value=_visiver(approved=True, confidence=0.9))

    verdict = await verify_brochure(
        outside_png_bytes=b"png",
        inside_png_bytes=b"png",
        original_prompt="a brochure",
        outline=_outline(),
        settings=_settings(),
        vision_evaluator=evaluator,
        iteration=2,
    )
    assert verdict.iteration == 2


# ---------- verify_brochure (two-sheet averaging) ----------


@pytest.mark.asyncio
async def test_verify_brochure_averages_two_sheets_when_inside_provided() -> None:
    """Outside rubric=80-mean, inside rubric=60-mean → merged score=70 (average)."""
    outside_rubric = json.dumps(
        {
            "dimension_scores": {
                "content_fit": 90,
                "visual_balance": 70,
                "text_legibility": 80,
                "layout_coherence": 80,
                "print_readiness": 80,
            },
            "critique": "outside looks great",
            "weakest_stage": None,
        }
    )
    inside_rubric = json.dumps(
        {
            "dimension_scores": {
                "content_fit": 60,
                "visual_balance": 40,
                "text_legibility": 70,
                "layout_coherence": 70,
                "print_readiness": 60,
            },
            "critique": "inside is off",
            "weakest_stage": "layout",
        }
    )

    def _mk(raw: str) -> VisionVerdict:
        return VisionVerdict(
            approved=True,
            confidence=0.9,
            zones=None,
            rejection_reasons=[],
            refinement_hint="",
            text_color="white",
            mood_tags=[],
            raw_response=raw,
        )

    evaluator = AsyncMock()
    evaluator.evaluate_cover = AsyncMock(side_effect=[_mk(outside_rubric), _mk(inside_rubric)])

    verdict = await verify_brochure(
        outside_png_bytes=b"outside",
        inside_png_bytes=b"inside",
        original_prompt="p",
        outline=_outline(),
        settings=_settings(),
        vision_evaluator=evaluator,
    )
    # outside mean = 80, inside mean = 60, merged dims average per-key:
    # (90+60)/2=75, (70+40)/2=55, (80+70)/2=75, (80+70)/2=75, (80+60)/2=70
    # mean = (75+55+75+75+70)/5 = 70
    assert verdict.score == 70
    assert verdict.dimension_scores["visual_balance"] == 55
    # Inside had lower mean (60 < 80) → weakest_stage follows inside
    assert verdict.weakest_stage == "layout"
    assert "outside" in verdict.critique.lower()
    assert "inside" in verdict.critique.lower()
    # Both sheets were evaluated
    assert evaluator.evaluate_cover.await_count == 2


@pytest.mark.asyncio
async def test_verify_brochure_skips_inside_when_flag_false() -> None:
    """verify_inside_sheet=False → only one vision call."""
    evaluator = AsyncMock()
    evaluator.evaluate_cover = AsyncMock(return_value=_visiver(approved=True, confidence=0.8))

    verdict = await verify_brochure(
        outside_png_bytes=b"o",
        inside_png_bytes=b"i",
        original_prompt="p",
        outline=_outline(),
        settings=_settings(),
        vision_evaluator=evaluator,
        verify_inside_sheet=False,
    )
    assert verdict.score == 80
    assert evaluator.evaluate_cover.await_count == 1


@pytest.mark.asyncio
async def test_verify_brochure_skips_inside_when_bytes_empty() -> None:
    """Empty inside bytes → only outside scored."""
    evaluator = AsyncMock()
    evaluator.evaluate_cover = AsyncMock(return_value=_visiver(approved=True, confidence=0.75))

    verdict = await verify_brochure(
        outside_png_bytes=b"o",
        inside_png_bytes=b"",
        original_prompt="p",
        outline=_outline(),
        settings=_settings(),
        vision_evaluator=evaluator,
    )
    assert verdict.score == 75
    assert evaluator.evaluate_cover.await_count == 1


# ---------- verify_with_text_critique (text-only alternative) ----------


@pytest.mark.asyncio
async def test_verify_text_critique_happy_path() -> None:
    text_client = AsyncMock()
    text_client.complete = AsyncMock(
        return_value=json.dumps(
            {
                "dimension_scores": {
                    "content_fit": 80,
                    "visual_balance": 70,
                    "text_legibility": 75,
                    "layout_coherence": 85,
                    "print_readiness": 90,
                },
                "critique": "solid overall",
                "weakest_stage": None,
            }
        )
    )

    verdict = await verify_with_text_critique(
        outside_png_bytes=b"png",
        inside_png_bytes=b"png",
        original_prompt="prompt",
        outline=_outline(),
        text_client=text_client,
    )
    # 80+70+75+85+90 = 400, mean 80
    assert verdict.score == 80
    assert verdict.weakest_stage is None


@pytest.mark.asyncio
async def test_verify_text_critique_raises_on_malformed_json() -> None:
    text_client = AsyncMock()
    text_client.complete = AsyncMock(return_value="not json")

    with pytest.raises(BrochureVerificationError):
        await verify_with_text_critique(
            outside_png_bytes=b"png",
            inside_png_bytes=b"png",
            original_prompt="prompt",
            outline=_outline(),
            text_client=text_client,
        )
