"""Tests for stage 2 — per-section text generation."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from flyer_generator.brochure.generative.models import (
    BrochureOutline,
    SectionSpec,
)
from flyer_generator.brochure.generative.text import generate_section_texts


def _outline() -> BrochureOutline:
    return BrochureOutline(
        sections=[
            SectionSpec(heading="Welcome", body_brief="hero", image_hint=None, panel_role="cover"),
            SectionSpec(heading="Classes", body_brief="list formats", image_hint="yoga mat", panel_role="feature"),
            SectionSpec(heading="Visit", body_brief="address", image_hint=None, panel_role="cta"),
        ],
        tone="calm",
        cta_intent="book a trial",
        suggested_preset="photorealistic",
        suggested_accent="#7BB661",
    )


def _text_client_returning_sequence(bodies: list[str]) -> AsyncMock:
    """Mock that returns bodies[0], bodies[1], ... in order of call."""
    client = AsyncMock()
    client.complete = AsyncMock(side_effect=bodies)
    return client


@pytest.mark.asyncio
async def test_generate_texts_returns_one_per_section() -> None:
    client = _text_client_returning_sequence(
        ["welcome body", "classes body", "visit body"]
    )
    texts = await generate_section_texts(_outline(), client, target_length="medium")

    assert len(texts) == 3
    assert [t.heading for t in texts] == ["Welcome", "Classes", "Visit"]
    # Body text is stripped
    assert texts[0].body == "welcome body"
    # image_hint carried from spec
    assert texts[1].image_hint == "yoga mat"
    assert texts[2].image_hint is None


@pytest.mark.asyncio
async def test_generate_texts_calls_in_parallel() -> None:
    """All sections should be dispatched concurrently (one gather call)."""
    client = _text_client_returning_sequence(["a", "b", "c"])
    await generate_section_texts(_outline(), client)
    assert client.complete.await_count == 3


@pytest.mark.asyncio
async def test_generate_texts_strips_body_whitespace() -> None:
    client = _text_client_returning_sequence(["  padded body  \n\n", "b", "c"])
    texts = await generate_section_texts(_outline(), client)
    assert texts[0].body == "padded body"


@pytest.mark.asyncio
async def test_generate_texts_target_length_drives_prompt() -> None:
    client = _text_client_returning_sequence(["a", "b", "c"])
    await generate_section_texts(_outline(), client, target_length="short")

    # Verify the "short" target shows up in at least one user prompt.
    first_call_user = client.complete.await_args_list[0].kwargs["user"]
    assert "25 words" in first_call_user  # short = 25


@pytest.mark.asyncio
async def test_generate_texts_response_format_is_text_not_json() -> None:
    client = _text_client_returning_sequence(["a", "b", "c"])
    await generate_section_texts(_outline(), client)
    assert client.complete.await_args_list[0].kwargs["response_format"] == "text"
