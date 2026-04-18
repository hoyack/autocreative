"""Tests for stage 5 — fit optimization."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from flyer_generator.brochure.generative.fit import (
    estimate_body_capacity,
    needs_rewrite,
    optimize_fit,
)
from flyer_generator.brochure.generative.models import SectionText
from flyer_generator.brochure.templates import EDITORIAL, MINIMALIST, PLAYFUL


# ---------- Capacity estimation ----------


def test_estimate_capacity_is_positive_for_all_templates() -> None:
    for t in (EDITORIAL, MINIMALIST, PLAYFUL):
        cap = estimate_body_capacity(t)
        assert cap > 500  # Every template should permit a real paragraph


def test_estimate_capacity_scales_with_body_font() -> None:
    # MINIMALIST has smaller body font than PLAYFUL → more capacity per panel
    assert estimate_body_capacity(MINIMALIST) > estimate_body_capacity(PLAYFUL)


# ---------- needs_rewrite ----------


def test_needs_rewrite_flags_overflow() -> None:
    long_body = "x" * 4000  # way over any template's capacity
    needs, target = needs_rewrite(long_body, EDITORIAL, "medium")
    assert needs is True
    assert target < 4000


def test_needs_rewrite_allows_short_when_target_is_short() -> None:
    short_body = "x" * 60
    needs, _ = needs_rewrite(short_body, EDITORIAL, "short")
    # Short target should not flag underflow
    assert needs is False


def test_needs_rewrite_flags_underflow_for_medium() -> None:
    # 20 chars when target is medium (~60% of capacity) → severe underflow
    needs, _ = needs_rewrite("x" * 20, EDITORIAL, "medium")
    assert needs is True


def test_needs_rewrite_passes_when_in_range() -> None:
    # Pick a body size near mid-capacity for medium
    cap = estimate_body_capacity(EDITORIAL)
    midrange = "x" * (cap // 2)
    needs, _ = needs_rewrite(midrange, EDITORIAL, "medium")
    assert needs is False


# ---------- optimize_fit ----------


def _mock_text_client(sequential_replies: list[str]) -> AsyncMock:
    client = AsyncMock()
    client.complete = AsyncMock(side_effect=sequential_replies)
    return client


@pytest.mark.asyncio
async def test_optimize_fit_leaves_fitting_sections_unchanged() -> None:
    cap = estimate_body_capacity(EDITORIAL)
    body = "x" * (cap // 2)  # mid-range, no rewrite needed
    client = AsyncMock()
    client.complete = AsyncMock()  # should not be called

    original = [SectionText(heading="A", body=body, image_hint=None)]
    result = await optimize_fit(original, EDITORIAL, client, target_length="medium")
    assert result[0].body == body
    assert client.complete.await_count == 0


@pytest.mark.asyncio
async def test_optimize_fit_rewrites_overflowing_sections() -> None:
    client = _mock_text_client(["tightened body"])
    overflow = SectionText(heading="Too long", body="x" * 5000, image_hint=None)

    result = await optimize_fit([overflow], EDITORIAL, client, target_length="medium")
    assert result[0].body == "tightened body"
    assert result[0].heading == "Too long"  # heading preserved
    assert client.complete.await_count == 1


@pytest.mark.asyncio
async def test_optimize_fit_preserves_image_hint() -> None:
    client = _mock_text_client(["revised"])
    section = SectionText(heading="H", body="x" * 5000, image_hint="a map")
    result = await optimize_fit([section], EDITORIAL, client, target_length="medium")
    assert result[0].image_hint == "a map"


@pytest.mark.asyncio
async def test_optimize_fit_runs_rewrites_in_parallel() -> None:
    client = _mock_text_client(["a", "b", "c"])
    sections = [
        SectionText(heading=f"H{i}", body="x" * 5000, image_hint=None) for i in range(3)
    ]
    result = await optimize_fit(sections, EDITORIAL, client, target_length="medium")
    assert [s.body for s in result] == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_optimize_fit_single_rewrite_per_section() -> None:
    """Rewrite is called at most once per section (no inner loop)."""
    client = _mock_text_client(["still_wrong"])  # rewrite output still huge
    section = SectionText(heading="H", body="x" * 5000, image_hint=None)
    result = await optimize_fit([section], EDITORIAL, client, target_length="medium")
    assert result[0].body == "still_wrong"  # accepted even if still off
    assert client.complete.await_count == 1  # exactly one call
