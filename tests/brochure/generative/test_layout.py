"""Tests for stage 3 — layout selection, and for the template registry."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from flyer_generator.brochure.generative.layout import choose_layout
from flyer_generator.brochure.generative.models import (
    BrochureOutline,
    SectionSpec,
)
from flyer_generator.brochure.templates import (
    TEMPLATE_REGISTRY,
    all_templates,
    get_template,
)
from flyer_generator.errors import VisionResponseParseError


def _outline() -> BrochureOutline:
    return BrochureOutline(
        sections=[
            SectionSpec(heading="Hero", body_brief="x", image_hint=None, panel_role="cover"),
            SectionSpec(heading="More", body_brief="y", image_hint=None, panel_role="feature"),
        ],
        tone="professional",
        cta_intent="book a call",
        suggested_preset="photorealistic",
        suggested_accent="#2E8B57",
    )


# ---------- Registry ----------


def test_registry_has_six_templates() -> None:
    assert len(TEMPLATE_REGISTRY) == 6
    assert set(TEMPLATE_REGISTRY.keys()) == {
        "editorial",
        "minimalist",
        "playful",
        "gallery_strip",
        "quote_driven",
        "spotlight",
    }


def test_all_templates_preserves_registry_order() -> None:
    names = [t.name for t in all_templates()]
    assert names == list(TEMPLATE_REGISTRY.keys())


def test_get_template_returns_correct_instance() -> None:
    t = get_template("playful")
    assert t.name == "playful"
    assert "fun" in t.tone_keywords


def test_get_template_raises_on_unknown_name() -> None:
    with pytest.raises(KeyError):
        get_template("nonexistent")


def test_each_template_has_required_panels_in_shape_mix() -> None:
    required = {"cover", "back_cover", "tuck_flap", "inner_left", "inner_center", "inner_right"}
    for t in all_templates():
        assert set(t.shape_mix.keys()) == required, f"{t.name} missing panels"


def test_each_template_font_sizes_are_positive_ints() -> None:
    for t in all_templates():
        assert t.cover_title_font_size > 0
        assert t.heading_font_size > 0
        assert t.body_font_size > 0
        assert t.body_line_height > t.body_font_size


# ---------- choose_layout ----------


def _valid_choice_json(template: str = "editorial") -> str:
    return json.dumps(
        {
            "template": template,
            "shape_density": "medium",
            "accent_placement": "top_rule",
            "cover_treatment": "image_full",
        }
    )


def _mock_client(response: str) -> AsyncMock:
    client = AsyncMock()
    client.complete = AsyncMock(return_value=response)
    return client


@pytest.mark.asyncio
async def test_choose_layout_returns_valid_choice() -> None:
    client = _mock_client(_valid_choice_json("playful"))
    choice = await choose_layout(_outline(), client)
    assert choice.template == "playful"
    assert choice.shape_density == "medium"


@pytest.mark.asyncio
async def test_choose_layout_falls_back_on_parse_error() -> None:
    client = AsyncMock()
    client.complete = AsyncMock(side_effect=VisionResponseParseError("no json"))
    choice = await choose_layout(_outline(), client)
    # Fallback is editorial + medium + top_rule + image_full
    assert choice.template == "editorial"
    assert choice.shape_density == "medium"


@pytest.mark.asyncio
async def test_choose_layout_falls_back_on_invalid_template_name() -> None:
    client = _mock_client(
        json.dumps(
            {
                "template": "futuristic",  # not a valid template
                "shape_density": "medium",
                "accent_placement": "top_rule",
                "cover_treatment": "image_full",
            }
        )
    )
    choice = await choose_layout(_outline(), client)
    assert choice.template == "editorial"  # fallback


@pytest.mark.asyncio
async def test_choose_layout_falls_back_on_missing_keys() -> None:
    client = _mock_client(json.dumps({"template": "editorial"}))  # missing keys
    choice = await choose_layout(_outline(), client)
    assert choice.template == "editorial"


@pytest.mark.asyncio
async def test_choose_layout_prompt_includes_all_six_templates() -> None:
    client = _mock_client(_valid_choice_json())
    await choose_layout(_outline(), client)
    user_prompt = client.complete.await_args.kwargs["user"]
    for name in ("editorial", "minimalist", "playful", "gallery_strip", "quote_driven", "spotlight"):
        assert name in user_prompt


@pytest.mark.asyncio
async def test_choose_layout_accepts_all_six_template_choices() -> None:
    for name in ("editorial", "minimalist", "playful", "gallery_strip", "quote_driven", "spotlight"):
        client = _mock_client(_valid_choice_json(name))
        choice = await choose_layout(_outline(), client)
        assert choice.template == name
