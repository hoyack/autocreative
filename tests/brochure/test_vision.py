"""Tests for brochure cover vision evaluation.

Mocks the Anthropic SDK via the existing test pattern (monkeypatch on AsyncAnthropic)
and verifies that:
- BROCHURE_COVER_SYSTEM_PROMPT is used (no 9-zone grid instruction)
- The concept string is forwarded to the user message
- Zones are dropped from the verdict (brochure has no zones)
- Approval without zones is accepted (unlike flyer mode)
- Confidence gate still fires below threshold
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from flyer_generator.brochure.stages.vision import (
    BROCHURE_COVER_SYSTEM_PROMPT,
    BrochureCoverVisionEvaluator,
)
from flyer_generator.config import Settings


def _settings() -> Settings:
    return Settings(
        anthropic_api_key=SecretStr("sk-test"),
        comfycloud_api_key=SecretStr("test"),
        vision_provider="anthropic",
        vision_confidence_threshold=0.6,
    )


def _fake_anthropic_response(body: dict) -> SimpleNamespace:
    return SimpleNamespace(content=[SimpleNamespace(text=json.dumps(body))])


def _install_mock_anthropic(monkeypatch: pytest.MonkeyPatch, response_body: dict):
    """Patch AsyncAnthropic so its messages.create returns a canned response."""
    mock_client = SimpleNamespace(
        messages=SimpleNamespace(
            create=AsyncMock(return_value=_fake_anthropic_response(response_body))
        )
    )

    def _factory(*args, **kwargs):
        return mock_client

    monkeypatch.setattr(
        "flyer_generator.stages.vision.AsyncAnthropic", _factory
    )
    return mock_client


@pytest.mark.asyncio
async def test_approves_without_zones(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {
        "approved": True,
        "confidence": 0.85,
        "rejection_reasons": [],
        "refinement_hint": "",
        "text_color": "white",
        "mood_tags": ["professional", "warm"],
    }
    _install_mock_anthropic(monkeypatch, body)

    evaluator = BrochureCoverVisionEvaluator(_settings())
    verdict = await evaluator.evaluate(
        image_bytes=b"\x89PNG\x00test",
        concept="modern conference stage",
        style_preset="photorealistic",
    )
    assert verdict.approved is True
    assert verdict.confidence == 0.85
    assert verdict.zones is None  # brochure always has zones=None
    assert verdict.text_color == "white"


@pytest.mark.asyncio
async def test_low_confidence_triggers_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {
        "approved": True,
        "confidence": 0.4,  # below 0.6 threshold
        "rejection_reasons": [],
        "refinement_hint": "",
        "text_color": "white",
        "mood_tags": [],
    }
    _install_mock_anthropic(monkeypatch, body)

    evaluator = BrochureCoverVisionEvaluator(_settings())
    verdict = await evaluator.evaluate(
        image_bytes=b"x", concept="c"
    )
    assert verdict.approved is False
    assert any("low confidence" in r.lower() for r in verdict.rejection_reasons)


@pytest.mark.asyncio
async def test_uses_brochure_cover_system_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {
        "approved": True,
        "confidence": 0.9,
        "rejection_reasons": [],
        "refinement_hint": "",
        "text_color": "dark",
        "mood_tags": [],
    }
    mock_client = _install_mock_anthropic(monkeypatch, body)

    evaluator = BrochureCoverVisionEvaluator(_settings())
    await evaluator.evaluate(image_bytes=b"x", concept="c", style_preset="anime")

    # The system prompt passed to Anthropic must be the brochure one, not the flyer one.
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["system"] == BROCHURE_COVER_SYSTEM_PROMPT
    # Sanity: brochure prompt must NOT contain the flyer 9-zone grid instruction.
    assert "3x3 grid" not in BROCHURE_COVER_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_concept_and_preset_appear_in_user_text(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {
        "approved": True,
        "confidence": 0.8,
        "rejection_reasons": [],
        "refinement_hint": "",
        "text_color": "white",
        "mood_tags": [],
    }
    mock_client = _install_mock_anthropic(monkeypatch, body)

    evaluator = BrochureCoverVisionEvaluator(_settings())
    await evaluator.evaluate(
        image_bytes=b"x",
        concept="rolling vineyards at sunset",
        style_preset="photorealistic",
    )

    call_kwargs = mock_client.messages.create.call_args.kwargs
    # Find the text block in the user message content list
    user_content = call_kwargs["messages"][0]["content"]
    text_blocks = [c["text"] for c in user_content if c.get("type") == "text"]
    joined = "\n".join(text_blocks)
    assert "rolling vineyards at sunset" in joined
    assert "photorealistic" in joined


@pytest.mark.asyncio
async def test_zones_returned_by_model_are_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    # Even if the model returns a zones field, brochure mode drops it.
    body = {
        "approved": True,
        "confidence": 0.95,
        "rejection_reasons": [],
        "refinement_hint": "",
        "zones": {
            "title": "TOP_CENTER",
            "details": "BOTTOM_CENTER",
            "fee_badge": "TOP_RIGHT",
            "org_credit": "BOTTOM_CENTER",
        },
        "text_color": "white",
        "mood_tags": [],
    }
    _install_mock_anthropic(monkeypatch, body)

    evaluator = BrochureCoverVisionEvaluator(_settings())
    verdict = await evaluator.evaluate(image_bytes=b"x", concept="c")
    assert verdict.zones is None
