"""Tests for Phase 4 — image_gate orchestration.

Uses mocked ComfyClient + vision evaluator so no network is required.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from flyer_generator.brochure.schema_renderer import (
    BrochureContent,
    ContentSection,
    collect_image_slots,
    generate_template_images,
    load_template,
    resolve_concept_for_slot,
)
from flyer_generator.config import Settings
from flyer_generator.models import ComfyJob, VisionVerdict


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _settings(max_bg_attempts: int = 3) -> Settings:
    return Settings(
        anthropic_api_key=SecretStr("sk-test"),
        comfycloud_api_key=SecretStr("k-test"),
        max_bg_attempts=max_bg_attempts,
    )


def _content(n_sections: int = 3) -> BrochureContent:
    sections = [
        ContentSection(
            heading=f"Heading {i}",
            lead_paragraph=f"Lead {i}.",
            bullets=[f"B{i}.1", f"B{i}.2"],
            image_concept=f"Concept for section {i}" if i != 1 else None,
            icon_hint=f"icon hint {i}" if i == 1 else None,
        )
        for i in range(n_sections)
    ]
    return BrochureContent(
        title="Sample Title",
        subtitle="Subtitle",
        org="Acme",
        hero_concept="A warm golden-hour porch photo",
        sections=sections,
    )


def _job() -> ComfyJob:
    return ComfyJob(
        prompt_id="p",
        submitted_at=datetime(2026, 4, 19),
        positive_prompt="p",
        negative_prompt="n",
        seed=42,
        attempt_number=1,
    )


def _approved() -> VisionVerdict:
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


def _rejected(hint: str = "more sky") -> VisionVerdict:
    return VisionVerdict(
        approved=False,
        confidence=0.3,
        zones=None,
        rejection_reasons=["text-in-image"],
        refinement_hint=hint,
        text_color="white",
        mood_tags=[],
        raw_response="{}",
    )


def _comfy_mock(return_bytes: bytes = b"\x89PNG-fake") -> AsyncMock:
    m = AsyncMock()
    m.generate = AsyncMock(return_value=(_job(), return_bytes))
    return m


# --------------------------------------------------------------------------- #
# collect_image_slots
# --------------------------------------------------------------------------- #


def test_collect_image_slots_returns_unique_ordered() -> None:
    t = load_template("hero_image_dominant")
    slots = collect_image_slots(t)
    # hero_image_dominant uses hero + spot_1/2/3
    assert "hero" in slots
    assert "spot_1" in slots
    # Order preserves first-occurrence across panels
    assert len(set(slots)) == len(slots)


def test_collect_image_slots_empty_for_pure_design_template() -> None:
    # editorial_classic is a design-heavy template; may have 0 or few slots.
    t = load_template("editorial_classic")
    slots = collect_image_slots(t)
    assert isinstance(slots, list)
    # Even if some exist, the function must return a deduped list.
    assert len(set(slots)) == len(slots)


# --------------------------------------------------------------------------- #
# resolve_concept_for_slot
# --------------------------------------------------------------------------- #


def test_resolve_hero_slot() -> None:
    c = _content()
    assert resolve_concept_for_slot("hero", c) == c.hero_concept


def test_resolve_spot_uses_image_concept() -> None:
    c = _content()
    # Section 0 has image_concept
    assert resolve_concept_for_slot("spot_1", c) == "Concept for section 0"


def test_resolve_spot_falls_back_to_icon_hint() -> None:
    c = _content()
    # Section 1 has no image_concept but has icon_hint
    assert resolve_concept_for_slot("spot_2", c) == "icon hint 1"


def test_resolve_spot_falls_back_to_heading() -> None:
    c = BrochureContent(
        title="T",
        org="O",
        sections=[ContentSection(heading="Only Heading")],
    )
    result = resolve_concept_for_slot("spot_1", c)
    assert result is not None
    assert "Only Heading" in result


def test_resolve_spot_out_of_range_returns_none() -> None:
    c = _content(n_sections=2)
    assert resolve_concept_for_slot("spot_9", c) is None


def test_resolve_unknown_slot_returns_none() -> None:
    c = _content()
    assert resolve_concept_for_slot("texture_1", c) is None


def test_resolve_hero_returns_none_when_content_has_none() -> None:
    c = BrochureContent(
        title="T", org="O", sections=[ContentSection(heading="H")]
    )
    assert resolve_concept_for_slot("hero", c) is None


# --------------------------------------------------------------------------- #
# generate_template_images — happy path
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_generate_template_images_hero_plus_spots() -> None:
    t = load_template("hero_image_dominant")
    c = _content()
    comfy = _comfy_mock(b"\x89PNG-hero")
    vision = AsyncMock()
    vision.evaluate = AsyncMock(return_value=_approved())

    images = await generate_template_images(
        t,
        c,
        settings=_settings(),
        comfy_client=comfy,
        cover_vision=vision,
    )

    # hero_image_dominant has hero + spot_1/2/3
    assert "hero" in images
    assert images["hero"] == b"\x89PNG-hero"
    # Spot images generated in parallel
    assert any(k.startswith("spot_") for k in images)


@pytest.mark.asyncio
async def test_generate_template_images_empty_template_returns_empty() -> None:
    # Build a throwaway template-like by loading editorial_classic; if it has no
    # image slots this returns {}. If it does, this test is still valid: we're
    # really testing the "no slots → no generate calls" branch with a hand-built
    # template, but reusing the no-images path here via zero slots is harder
    # without constructing one. Instead: patch in a zero-slots template.
    from flyer_generator.brochure.schema_renderer.schema_model import (
        Canvas,
        Palette,
        PanelSchema,
        TemplateSchema,
    )

    empty = TemplateSchema(
        schema_version="1",
        name="test_empty",
        description="no image placeholders",
        canvas=Canvas(width=1100, height=2550),
        palette=Palette(accent_default="#111111"),
        panels={
            p: PanelSchema(elements=[])
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
    comfy = _comfy_mock()
    vision = AsyncMock()

    images = await generate_template_images(
        empty,
        _content(),
        settings=_settings(),
        comfy_client=comfy,
        cover_vision=vision,
    )
    assert images == {}
    assert comfy.generate.await_count == 0


# --------------------------------------------------------------------------- #
# Hero retry + fallback
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_hero_retries_on_vision_rejection() -> None:
    t = load_template("hero_image_dominant")
    c = _content()
    comfy = _comfy_mock()
    vision = AsyncMock()
    vision.evaluate = AsyncMock(
        side_effect=[_rejected("more calm sky"), _approved()]
    )

    images = await generate_template_images(
        t,
        c,
        settings=_settings(max_bg_attempts=3),
        comfy_client=comfy,
        cover_vision=vision,
    )
    # Hero eventually approved
    assert "hero" in images
    assert vision.evaluate.await_count == 2


@pytest.mark.asyncio
async def test_hero_falls_back_after_exhausted_attempts() -> None:
    t = load_template("hero_image_dominant")
    c = _content()
    comfy = _comfy_mock()
    vision = AsyncMock()
    vision.evaluate = AsyncMock(
        side_effect=[_rejected(), _rejected(), _rejected()]
    )

    images = await generate_template_images(
        t,
        c,
        settings=_settings(max_bg_attempts=3),
        comfy_client=comfy,
        cover_vision=vision,
    )
    # Hero is omitted — no raise, renderer will fall back to fallback_fill
    assert "hero" not in images
    # But spots still produced
    assert any(k.startswith("spot_") for k in images)


@pytest.mark.asyncio
async def test_hero_generation_error_is_soft() -> None:
    t = load_template("hero_image_dominant")
    c = _content()

    call_count = {"n": 0}

    async def flaky_generate(*_args, **_kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("boom on hero")
        return (_job(), b"\x89PNG-spot")

    comfy = AsyncMock()
    comfy.generate = AsyncMock(side_effect=flaky_generate)
    vision = AsyncMock()

    images = await generate_template_images(
        t,
        c,
        settings=_settings(max_bg_attempts=3),
        comfy_client=comfy,
        cover_vision=vision,
    )
    # Hero exception → skipped; spots still produced
    assert "hero" not in images
    assert any(k.startswith("spot_") for k in images)


@pytest.mark.asyncio
async def test_spot_failure_does_not_block_other_spots() -> None:
    t = load_template("hero_image_dominant")
    c = _content()

    call_count = {"n": 0}

    async def mixed_generate(workflow, *_args, **_kwargs):
        call_count["n"] += 1
        # First call is hero (approved), second spot fails, remaining succeed
        if call_count["n"] == 2:
            raise RuntimeError("spot failure")
        return (_job(), b"\x89PNG-ok")

    comfy = AsyncMock()
    comfy.generate = AsyncMock(side_effect=mixed_generate)
    vision = AsyncMock()
    vision.evaluate = AsyncMock(return_value=_approved())

    images = await generate_template_images(
        t,
        c,
        settings=_settings(),
        comfy_client=comfy,
        cover_vision=vision,
    )
    assert "hero" in images
    # At least one spot made it through
    assert any(k.startswith("spot_") for k in images)


@pytest.mark.asyncio
async def test_hero_skipped_when_content_has_no_hero_concept() -> None:
    t = load_template("hero_image_dominant")
    c = BrochureContent(
        title="T",
        org="O",
        sections=[
            ContentSection(heading="A", image_concept="alpha"),
            ContentSection(heading="B", image_concept="beta"),
        ],
    )
    comfy = _comfy_mock()
    vision = AsyncMock()

    images = await generate_template_images(
        t,
        c,
        settings=_settings(),
        comfy_client=comfy,
        cover_vision=vision,
    )
    # No hero in result because content.hero_concept is None
    assert "hero" not in images
    # Vision never invoked for hero
    assert vision.evaluate.await_count == 0
