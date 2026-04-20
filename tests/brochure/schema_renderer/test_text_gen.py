"""Tests for Phase 2 — LLM-driven text budgeting."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from flyer_generator.brochure.schema_renderer import (
    BrochureContent,
    TextBudget,
    collect_text_budgets,
    generate_content_from_prompt,
    load_template,
)
from flyer_generator.brochure.schema_renderer.text_gen import (
    _apply_budgets,
    _infer_bullets_per_key,
    _truncate_at_word_boundary,
)


# --------------------------------------------------------------------------- #
# collect_text_budgets
# --------------------------------------------------------------------------- #


def test_collect_text_budgets_covers_title_and_sections() -> None:
    t = load_template("hero_image_dominant")
    budgets = collect_text_budgets(t)
    keys = {b.content_key for b in budgets}
    assert "title" in keys
    # hero_image_dominant references sections[0..2]
    assert any(k.startswith("sections[") for k in keys)


def test_collect_text_budgets_returns_unique_content_keys() -> None:
    t = load_template("editorial_classic")
    budgets = collect_text_budgets(t)
    seen = [b.content_key for b in budgets]
    assert len(seen) == len(set(seen))


def test_collect_text_budgets_marks_bullets_as_list() -> None:
    t = load_template("hero_image_dominant")
    budgets = collect_text_budgets(t)
    bullet_budgets = [b for b in budgets if b.is_list]
    assert bullet_budgets, "expected at least one bullets element"
    for b in bullet_budgets:
        assert b.role == "bullet"


def test_collect_text_budgets_respects_max_chars_override() -> None:
    """A TextElement with max_chars=10 should cap the budget to at most 10."""
    from flyer_generator.brochure.schema_renderer.schema_model import (
        Canvas,
        Palette,
        PanelSchema,
        TemplateSchema,
        TextElement,
    )

    tight = TextElement(
        bbox=(0.0, 0.0, 1000.0, 200.0),
        role="cover_title",
        content_key="title",
        max_chars=10,
    )
    tmpl = TemplateSchema(
        schema_version="1",
        name="test_tight",
        description="t",
        canvas=Canvas(width=1100, height=2550),
        palette=Palette(accent_default="#111111"),
        panels={
            p: PanelSchema(elements=[tight] if p == "front_cover" else [])
            for p in (
                "front_cover",
                "back_cover",
                "tuck_flap",
                "inner_left",
                "inner_center",
                "inner_right",
            )
        },
    )
    budgets = collect_text_budgets(tmpl)
    title = next(b for b in budgets if b.content_key == "title")
    # Slack is 0.92 → max_chars=10 floored + slack means 9 or 10
    assert title.max_chars <= 10


# --------------------------------------------------------------------------- #
# Budget enforcement
# --------------------------------------------------------------------------- #


def test_truncate_at_word_boundary_backs_off_to_space() -> None:
    out = _truncate_at_word_boundary("The quick brown fox jumps", 15)
    assert len(out) <= 15
    assert out.endswith("…") or not out.endswith(" ")
    # Should prefer a word boundary, not mid-word
    assert "quic" not in out or "quick" in out


def test_truncate_leaves_short_text_unchanged() -> None:
    assert _truncate_at_word_boundary("short", 50) == "short"


def test_apply_budgets_truncates_overflowing_title() -> None:
    budgets = [
        TextBudget(
            content_key="title", role="cover_title", max_chars=10, is_list=False
        )
    ]
    data = {"title": "This is way too long for a cover title"}
    corrected, overflow = _apply_budgets(data, budgets, bullets_per_key={})
    assert "title" in overflow
    assert len(corrected["title"]) <= 10


def test_apply_budgets_clips_bullets_list_and_per_item() -> None:
    budgets = [
        TextBudget(
            content_key="sections[0].bullets",
            role="bullet",
            max_chars=40,  # total across ~4 items → ~10 chars each
            is_list=True,
        )
    ]
    data = {
        "sections": [
            {
                "bullets": [
                    "this bullet is also excessively long",
                    "another far too long bullet that wont fit",
                    "one more item blown way past",
                    "short one",
                    "this should be dropped",
                    "this too",
                ]
            }
        ]
    }
    corrected, overflow = _apply_budgets(
        data, budgets, bullets_per_key={"sections[0].bullets": 4}
    )
    bullets = corrected["sections"][0]["bullets"]
    # Truncated to first 4 items
    assert len(bullets) == 4
    # Each item respects per_item = 40 // 4 = 10
    for item in bullets:
        assert len(item) <= 10
    assert "sections[0].bullets" in overflow


def test_apply_budgets_leaves_fitting_fields_alone() -> None:
    budgets = [
        TextBudget("title", "cover_title", 50, False),
        TextBudget("subtitle", "cover_subtitle", 80, False),
    ]
    data = {"title": "Short Title", "subtitle": "A perfectly reasonable subtitle."}
    corrected, overflow = _apply_budgets(data, budgets, bullets_per_key={})
    assert overflow == []
    assert corrected["title"] == "Short Title"


def test_infer_bullets_per_key_matches_template() -> None:
    t = load_template("hero_image_dominant")
    mapping = _infer_bullets_per_key(t)
    # hero_image_dominant.inner_center bullets has max_items=6
    assert mapping.get("sections[1].bullets") == 6


# --------------------------------------------------------------------------- #
# generate_content_from_prompt (mocked LLM)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_generate_content_from_prompt_happy_path() -> None:
    t = load_template("hero_image_dominant")

    llm_json = {
        "title": "Protect",
        "subtitle": "Estate planning for families",
        "tagline": "Flat fees. Clear advice.",
        "org": "Harbor Vale",
        "hero_concept": "warm golden-hour family on a porch",
        "color_accent": "#1E3A5F",
        "contact": {
            "name": "Ellen Vale",
            "phone": "(415) 555-0100",
            "email": "hi@hv.com",
            "url": "hv.com",
            "address": "225 Bush St, SF",
        },
        "sections": [
            {
                "heading": "Why Plan",
                "lead_paragraph": "Families need plans.",
                "body_paragraphs": [],
                "bullets": ["Name guardians", "Skip probate", "Protect home"],
                "image_concept": "family at a table",
            },
            {
                "heading": "Our Services",
                "lead_paragraph": "Everything you need.",
                "body_paragraphs": [],
                "bullets": ["Living trust", "Pour-over will", "POA"],
                "image_concept": "signed papers",
            },
            {
                "heading": "Our Process",
                "lead_paragraph": "Two visits, done.",
                "body_paragraphs": [],
                "bullets": ["Intake", "Review", "Sign"],
                "image_concept": "office meeting",
            },
        ],
        "back_panel": {
            "kind": "cta",
            "heading": "Ready?",
            "body": "Call us.",
            "bullets": ["Call", "Email", "Visit"],
            "cta_label": "Book now",
            "footer_note": "Offer ends soon.",
        },
    }

    mock_client = AsyncMock()
    mock_client.complete = AsyncMock(return_value=json.dumps(llm_json))

    result = await generate_content_from_prompt(
        t,
        "a boutique estate-planning law firm",
        text_client=mock_client,
    )
    assert isinstance(result, BrochureContent)
    assert result.title.startswith("Protect")
    assert len(result.sections) >= 1
    assert result.contact is not None
    assert result.contact.phone is not None
    # Single LLM call on happy path (no overflow retry)
    assert mock_client.complete.await_count == 1


@pytest.mark.asyncio
async def test_generate_content_retries_on_overflow() -> None:
    t = load_template("hero_image_dominant")

    # First response has a comically long title; second response is tighter.
    overflow_json = {
        "title": "A" * 500,
        "org": "Acme",
        "hero_concept": "x",
        "color_accent": "#111111",
        "contact": {},
        "sections": [{"heading": "H", "bullets": []}],
        "back_panel": {"kind": "cta"},
    }
    good_json = dict(overflow_json, title="Short Title")

    mock_client = AsyncMock()
    mock_client.complete = AsyncMock(
        side_effect=[json.dumps(overflow_json), json.dumps(good_json)]
    )
    await generate_content_from_prompt(t, "x", text_client=mock_client)
    assert mock_client.complete.await_count == 2


@pytest.mark.asyncio
async def test_generate_content_falls_back_to_truncation_when_retry_fails() -> None:
    t = load_template("hero_image_dominant")

    overflow_json = {
        "title": "A" * 500,
        "org": "Acme",
        "hero_concept": "x",
        "color_accent": "#111111",
        "contact": {},
        "sections": [{"heading": "H", "bullets": []}],
        "back_panel": {"kind": "cta"},
    }

    mock_client = AsyncMock()
    # Both calls return the same overflowing JSON
    mock_client.complete = AsyncMock(return_value=json.dumps(overflow_json))

    result = await generate_content_from_prompt(t, "x", text_client=mock_client)
    # Title got truncated even after retry also failed
    # hero_image_dominant title max is bounded by font_size=128 × box width;
    # whatever the exact number is, 500 chars is far over.
    assert len(result.title) < 500


@pytest.mark.asyncio
async def test_generate_content_fills_defaults_for_missing_fields() -> None:
    t = load_template("hero_image_dominant")
    # Minimal LLM response missing most fields
    minimal_json = {"title": "T", "org": "O"}

    mock_client = AsyncMock()
    mock_client.complete = AsyncMock(return_value=json.dumps(minimal_json))

    result = await generate_content_from_prompt(t, "x", text_client=mock_client)
    # BrochureContent requires ≥1 section — defaults fill in
    assert len(result.sections) >= 1
    assert result.title == "T"
    assert result.org == "O"


# --------------------------------------------------------------------------- #
# BrochureBrief + supplied contact passthrough
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_brief_is_embedded_in_llm_prompt() -> None:
    """Intake facts must show up in the user prompt verbatim."""
    from flyer_generator.brochure.schema_renderer import BrochureBrief, Testimonial

    t = load_template("hero_image_dominant")
    brief = BrochureBrief(
        target_audience="solo developers shipping side projects",
        offerings=["Async workers", "Retry-safe pipelines", "Structured logging"],
        differentiators=["Zero cold starts", "Sub-5ms p99"],
        testimonials=[
            Testimonial(quote="saved us 3 weeks", attribution="— Jane, CTO"),
        ],
        awards=["YC S25 Best Infra"],
        key_stats=["99.99% uptime", "500 customers"],
        founded_year=2024,
        hours="24/7 on-call",
        primary_cta="Start free tier",
        secondary_cta="Read docs",
    )

    captured = {}

    async def capture(system, user, response_format):
        captured["user"] = user
        return json.dumps({"title": "T", "org": "O"})

    mock_client = AsyncMock()
    mock_client.complete = AsyncMock(side_effect=capture)

    await generate_content_from_prompt(
        t, "infra for async workloads", brief=brief, text_client=mock_client
    )

    user = captured["user"]
    assert "INTAKE BRIEF" in user
    assert "Async workers" in user
    assert "Zero cold starts" in user
    assert "YC S25 Best Infra" in user
    assert "Start free tier" in user
    assert "24/7 on-call" in user


@pytest.mark.asyncio
async def test_brief_is_attached_to_returned_content() -> None:
    """Brief passed in should round-trip into BrochureContent.brief."""
    from flyer_generator.brochure.schema_renderer import BrochureBrief

    t = load_template("hero_image_dominant")
    brief = BrochureBrief(value_proposition="infra for async workloads")

    mock_client = AsyncMock()
    mock_client.complete = AsyncMock(return_value=json.dumps({"title": "T", "org": "O"}))

    result = await generate_content_from_prompt(
        t, "x", brief=brief, text_client=mock_client
    )
    assert result.brief is not None
    assert result.brief.value_proposition == "infra for async workloads"


@pytest.mark.asyncio
async def test_supplied_contact_overrides_llm_contact_values() -> None:
    """Caller-supplied contact fields win over the LLM's choices."""
    from flyer_generator.brochure.models import ContactBlock

    t = load_template("hero_image_dominant")
    # LLM invents a phone number we don't want
    llm_json = {
        "title": "T",
        "org": "O",
        "contact": {"phone": "(555) 000-0000", "email": "bot@example.com"},
    }
    mock_client = AsyncMock()
    mock_client.complete = AsyncMock(return_value=json.dumps(llm_json))

    supplied = ContactBlock(phone="(415) 867-5309", address="1 Real Street")
    result = await generate_content_from_prompt(
        t, "x", contact=supplied, text_client=mock_client
    )
    # Real phone & address win; LLM's email stays (we didn't supply it)
    assert result.contact.phone == "(415) 867-5309"
    assert result.contact.address == "1 Real Street"
    assert result.contact.email == "bot@example.com"


@pytest.mark.asyncio
async def test_contact_block_is_embedded_in_prompt() -> None:
    """Supplied contact fields must appear in the user prompt so the LLM sees them."""
    from flyer_generator.brochure.models import ContactBlock

    t = load_template("hero_image_dominant")
    supplied = ContactBlock(
        phone="(415) 867-5309",
        email="hello@example.com",
        address="118 Broadway Suite 221, San Antonio, TX 78205",
    )

    captured = {}

    async def capture(system, user, response_format):
        captured["user"] = user
        return json.dumps({"title": "T", "org": "O"})

    mock_client = AsyncMock()
    mock_client.complete = AsyncMock(side_effect=capture)

    await generate_content_from_prompt(
        t, "x", contact=supplied, text_client=mock_client
    )
    user = captured["user"]
    assert "CONTACT" in user
    assert "(415) 867-5309" in user
    assert "118 Broadway Suite 221" in user
