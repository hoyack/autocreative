"""Tests for stage 1 — outline generation."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from flyer_generator.brochure.generative.models import BrochurePrompt
from flyer_generator.brochure.generative.outline import (
    BrochureOutlineError,
    generate_outline,
)


def _valid_outline_json() -> str:
    return json.dumps(
        {
            "sections": [
                {"heading": "Welcome", "body_brief": "introduce the studio", "image_hint": None, "panel_role": "cover"},
                {"heading": "Classes", "body_brief": "list class formats", "image_hint": "yoga mats neatly stacked", "panel_role": "feature"},
                {"heading": "Visit", "body_brief": "address + hours", "image_hint": None, "panel_role": "cta"},
            ],
            "tone": "calm, welcoming",
            "cta_intent": "visit for a first-class trial",
            "suggested_preset": "photorealistic",
            "suggested_accent": "#7BB661",
        }
    )


def _mock_text_client(response: str) -> AsyncMock:
    client = AsyncMock()
    client.complete = AsyncMock(return_value=response)
    return client


@pytest.mark.asyncio
async def test_generate_outline_happy_path() -> None:
    client = _mock_text_client(_valid_outline_json())
    prompt = BrochurePrompt(prompt="yoga studio for new moms")

    outline = await generate_outline(prompt, client)
    assert len(outline.sections) == 3
    assert outline.tone == "calm, welcoming"
    assert outline.suggested_accent == "#7BB661"
    # Exactly one cover
    cover = [s for s in outline.sections if s.panel_role == "cover"]
    assert len(cover) == 1


@pytest.mark.asyncio
async def test_generate_outline_echoes_user_overrides() -> None:
    # LLM returns one preset/accent; prompt locks a different one — prompt wins.
    client = _mock_text_client(_valid_outline_json())
    prompt = BrochurePrompt(
        prompt="yoga",
        style_preset="watercolor",
        color_accent="#FFAA00",
    )
    outline = await generate_outline(prompt, client)
    assert outline.suggested_preset == "watercolor"
    assert outline.suggested_accent == "#FFAA00"


@pytest.mark.asyncio
async def test_generate_outline_rejects_zero_covers() -> None:
    bad = json.dumps(
        {
            "sections": [
                {"heading": "A", "body_brief": "x", "image_hint": None, "panel_role": "feature"},
                {"heading": "B", "body_brief": "y", "image_hint": None, "panel_role": "detail"},
            ],
            "tone": "t",
            "cta_intent": "c",
            "suggested_preset": "photorealistic",
            "suggested_accent": "#112233",
        }
    )
    client = _mock_text_client(bad)
    with pytest.raises(BrochureOutlineError, match="cover"):
        await generate_outline(BrochurePrompt(prompt="x"), client)


@pytest.mark.asyncio
async def test_generate_outline_rejects_too_many_image_hints() -> None:
    bad = json.dumps(
        {
            "sections": [
                {"heading": "A", "body_brief": "x", "image_hint": "a", "panel_role": "cover"},
                {"heading": "B", "body_brief": "y", "image_hint": "b", "panel_role": "feature"},
                {"heading": "C", "body_brief": "z", "image_hint": "c", "panel_role": "feature"},
                {"heading": "D", "body_brief": "w", "image_hint": "d", "panel_role": "cta"},  # 4 hints
            ],
            "tone": "t",
            "cta_intent": "c",
            "suggested_preset": "photorealistic",
            "suggested_accent": "#112233",
        }
    )
    client = _mock_text_client(bad)
    with pytest.raises(BrochureOutlineError, match="image_hints"):
        await generate_outline(BrochurePrompt(prompt="x"), client)


@pytest.mark.asyncio
async def test_generate_outline_rejects_invalid_json() -> None:
    from flyer_generator.errors import VisionResponseParseError

    client = AsyncMock()
    client.complete = AsyncMock(side_effect=VisionResponseParseError("not json"))
    with pytest.raises(BrochureOutlineError):
        await generate_outline(BrochurePrompt(prompt="x"), client)


@pytest.mark.asyncio
async def test_generate_outline_passes_response_format_json() -> None:
    client = _mock_text_client(_valid_outline_json())
    await generate_outline(BrochurePrompt(prompt="x"), client)
    assert client.complete.call_args.kwargs["response_format"] == "json"


@pytest.mark.asyncio
async def test_generate_outline_parses_cover_image_concept() -> None:
    """Cover section carries through the dedicated image concept."""
    payload = json.dumps(
        {
            "sections": [
                {
                    "heading": "Welcome",
                    "body_brief": "introduce the studio",
                    "image_hint": None,
                    "panel_role": "cover",
                    "cover_image_concept": "sunlit yoga studio with plants and a folded mat",
                },
                {
                    "heading": "Classes",
                    "body_brief": "list class formats",
                    "image_hint": None,
                    "panel_role": "feature",
                },
            ],
            "tone": "calm",
            "cta_intent": "come try a class",
            "suggested_preset": "photorealistic",
            "suggested_accent": "#7BB661",
        }
    )
    outline = await generate_outline(BrochurePrompt(prompt="x"), _mock_text_client(payload))
    cover = next(s for s in outline.sections if s.panel_role == "cover")
    assert cover.cover_image_concept == "sunlit yoga studio with plants and a folded mat"
    # Non-cover section: field absent in JSON → defaults to None
    non_cover = next(s for s in outline.sections if s.panel_role != "cover")
    assert non_cover.cover_image_concept is None


@pytest.mark.asyncio
async def test_generate_outline_omits_cover_image_concept_gracefully() -> None:
    """Missing cover_image_concept is tolerated (defaults to None)."""
    # Use existing _valid_outline_json which doesn't include the new field.
    outline = await generate_outline(
        BrochurePrompt(prompt="x"), _mock_text_client(_valid_outline_json())
    )
    cover = next(s for s in outline.sections if s.panel_role == "cover")
    assert cover.cover_image_concept is None


def test_assemble_brochure_input_prefers_cover_image_concept() -> None:
    """_assemble_brochure_input picks cover_image_concept over body_brief."""
    from flyer_generator.brochure.generative.models import (
        BrochureOutline,
        SectionSpec,
        SectionText,
    )
    from flyer_generator.brochure.generative.pipeline import _assemble_brochure_input

    outline = BrochureOutline(
        sections=[
            SectionSpec(
                heading="Welcome",
                body_brief="copywriter-direction-that-should-not-be-used",
                image_hint=None,
                panel_role="cover",
                cover_image_concept="backlit studio with sheer curtains and soft dawn light",
            ),
            SectionSpec(
                heading="Classes",
                body_brief="list class formats",
                image_hint=None,
                panel_role="feature",
            ),
        ],
        tone="calm",
        cta_intent="visit us",
        suggested_preset="photorealistic",
        suggested_accent="#7BB661",
    )
    texts = [
        SectionText(heading="Welcome", body="hello"),
        SectionText(heading="Classes", body="classes body"),
    ]
    prompt = BrochurePrompt(prompt="yoga for moms")
    brochure_input = _assemble_brochure_input(prompt, outline, texts)
    assert brochure_input.hero_concept == "backlit studio with sheer curtains and soft dawn light"


def test_assemble_brochure_input_falls_back_to_body_brief_when_concept_missing() -> None:
    """With cover_image_concept=None, hero_concept uses body_brief as before."""
    from flyer_generator.brochure.generative.models import (
        BrochureOutline,
        SectionSpec,
        SectionText,
    )
    from flyer_generator.brochure.generative.pipeline import _assemble_brochure_input

    outline = BrochureOutline(
        sections=[
            SectionSpec(
                heading="Welcome",
                body_brief="introduce the studio",
                image_hint=None,
                panel_role="cover",
            ),
            SectionSpec(
                heading="Classes",
                body_brief="list",
                image_hint=None,
                panel_role="feature",
            ),
        ],
        tone="calm",
        cta_intent="visit",
        suggested_preset="photorealistic",
        suggested_accent="#7BB661",
    )
    texts = [
        SectionText(heading="Welcome", body="hello"),
        SectionText(heading="Classes", body="c"),
    ]
    brochure_input = _assemble_brochure_input(BrochurePrompt(prompt="p"), outline, texts)
    assert brochure_input.hero_concept == "introduce the studio"
