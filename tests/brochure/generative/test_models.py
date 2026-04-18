"""Tests for generative-pipeline Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from flyer_generator.brochure.generative.models import (
    BrochureOutline,
    BrochurePrompt,
    LayoutChoice,
    SectionSpec,
    SectionText,
    VerificationVerdict,
)


# ---------- BrochurePrompt ----------


def test_brochure_prompt_minimal() -> None:
    p = BrochurePrompt(prompt="A brochure for an event")
    assert p.target_length == "medium"
    assert p.color_accent is None


def test_brochure_prompt_rejects_invalid_accent() -> None:
    with pytest.raises(ValidationError, match="color_accent"):
        BrochurePrompt(prompt="x", color_accent="red")


def test_brochure_prompt_accepts_valid_accent() -> None:
    p = BrochurePrompt(prompt="x", color_accent="#7BB661")
    assert p.color_accent == "#7BB661"


@pytest.mark.parametrize("length", ["short", "medium", "long"])
def test_target_length_literals(length: str) -> None:
    p = BrochurePrompt(prompt="x", target_length=length)  # type: ignore[arg-type]
    assert p.target_length == length


def test_brochure_prompt_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden|extra fields"):
        BrochurePrompt(prompt="x", unexpected="boom")


# ---------- BrochureOutline ----------


def _valid_outline_kwargs() -> dict:
    return {
        "sections": [
            SectionSpec(heading="Hero", body_brief="establish the offer", image_hint=None, panel_role="cover"),
            SectionSpec(heading="Details", body_brief="what it includes", image_hint="product shot", panel_role="feature"),
        ],
        "tone": "warm and authoritative",
        "cta_intent": "visit example.com to book",
        "suggested_preset": "photorealistic",
        "suggested_accent": "#2E8B57",
    }


def test_brochure_outline_valid() -> None:
    outline = BrochureOutline(**_valid_outline_kwargs())
    assert len(outline.sections) == 2
    assert outline.tone == "warm and authoritative"


def test_brochure_outline_rejects_bad_accent() -> None:
    kwargs = _valid_outline_kwargs()
    kwargs["suggested_accent"] = "green"
    with pytest.raises(ValidationError):
        BrochureOutline(**kwargs)


def test_brochure_outline_section_count_bounds() -> None:
    kwargs = _valid_outline_kwargs()
    kwargs["sections"] = [SectionSpec(heading="only", body_brief="x", image_hint=None, panel_role="cover")]
    with pytest.raises(ValidationError):
        BrochureOutline(**kwargs)


# ---------- SectionSpec + SectionText ----------


def test_section_spec_panel_roles() -> None:
    for role in ("cover", "feature", "detail", "cta"):
        s = SectionSpec(heading="x", body_brief="y", image_hint=None, panel_role=role)  # type: ignore[arg-type]
        assert s.panel_role == role


def test_section_spec_rejects_invalid_role() -> None:
    with pytest.raises(ValidationError):
        SectionSpec(heading="x", body_brief="y", image_hint=None, panel_role="other")  # type: ignore[arg-type]


def test_section_text_roundtrips() -> None:
    t = SectionText(heading="Hello", body="World", image_hint="map")
    assert t.model_dump()["image_hint"] == "map"


# ---------- LayoutChoice ----------


@pytest.mark.parametrize(
    "template",
    ["editorial", "minimalist", "playful", "gallery_strip", "quote_driven", "spotlight"],
)
def test_layout_choice_accepts_all_six_templates(template: str) -> None:
    lc = LayoutChoice(
        template=template,  # type: ignore[arg-type]
        shape_density="medium",
        accent_placement="top_rule",
        cover_treatment="image_full",
    )
    assert lc.template == template


def test_layout_choice_rejects_unknown_template() -> None:
    with pytest.raises(ValidationError):
        LayoutChoice(
            template="futuristic",  # type: ignore[arg-type]
            shape_density="medium",
            accent_placement="top_rule",
            cover_treatment="image_full",
        )


# ---------- VerificationVerdict ----------


def test_verification_verdict_score_bounds() -> None:
    v = VerificationVerdict(score=75, dimension_scores={"a": 80}, critique="good")
    assert v.score == 75


def test_verification_verdict_rejects_out_of_range_score() -> None:
    with pytest.raises(ValidationError):
        VerificationVerdict(score=150, dimension_scores={"a": 80}, critique="x")
