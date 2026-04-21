"""End-to-end integration tests -- mocked LLM + Comfy, real CairoSVG.

Per checker B1: direct-module imports only.
Per 19-RESEARCH.md §Testing Matrix §Performance: total < 5 min across all
tests; each < 15s.
"""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone

import pytest
from PIL import Image

from flyer_generator.brand_kit.models import (
    BrandKit,
    BrandPalette,
    BrandTypography,
    BrandVoice,
    ColorUsage,
)
from flyer_generator.social.campaign import generate_campaign
from flyer_generator.social.generator import generate_post
from flyer_generator.social.models import PostBrief


class _FakeTextClient:
    def __init__(self, response: str) -> None:
        self._response = response
        self.calls = 0

    async def complete(self, *, system: str, user: str, response_format: str) -> str:
        self.calls += 1
        return self._response

    async def aclose(self) -> None: ...


class _FakeComfy:
    def __init__(self, png: bytes) -> None:
        self._png = png
        self.calls = 0

    async def generate_image(
        self, *, workflow_name: str, prompt: str, brand_kit
    ) -> bytes:
        self.calls += 1
        return self._png


def _make_png(w: int, h: int) -> bytes:
    img = Image.new("RGB", (w, h), (64, 128, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _seeded_kit() -> BrandKit:
    return BrandKit(
        name="Thunderstaff",
        fetched_at=datetime(2026, 4, 21, tzinfo=timezone.utc),
        palette=BrandPalette(
            primary=ColorUsage(hex="#1E3A5F"),
            secondary=ColorUsage(hex="#8B7D4B"),
            accent=ColorUsage(hex="#C4A269"),
            neutral_dark=ColorUsage(hex="#1A1A1A"),
            neutral_light=ColorUsage(hex="#FAFAF7"),
        ),
        typography=BrandTypography(
            heading_family="'Playfair Display', serif",
            body_family="'Source Serif Pro', serif",
        ),
        voice=BrandVoice(tone="direct, engineering-led", banned_words=["synergy"]),
    )


def _canned_copy() -> str:
    return json.dumps(
        {
            "copy.title": "Typed Validation Ships Fewer Bugs",
            "copy.body": (
                "We built a Pydantic-backed validation layer. "
                "Zero runtime surprises."
            ),
            "copy.cta": "Read more",
            "copy.hashtags": ["#python", "#pydantic", "#devops", "#typedcode"],
        }
    )


@pytest.mark.asyncio
async def test_generate_post_linkedin_value_prop_end_to_end_mocked() -> None:
    brief = PostBrief(
        topic="Typed validation",
        intent="value-prop",
        platform="linkedin",
    )
    kit = _seeded_kit()
    text = _FakeTextClient(_canned_copy())
    comfy = _FakeComfy(_make_png(1024, 1024))
    post = await generate_post(
        brief, kit, text_client=text, comfy_client=comfy, audit=True
    )
    # Shape
    assert post.platform == "linkedin"
    assert post.intent == "value-prop"
    # Copy
    assert post.copy.title == "Typed Validation Ships Fewer Bugs"
    assert len(post.copy.hashtags) == 4
    # Rendered image dims
    assert post.image_bytes is not None
    img = Image.open(io.BytesIO(post.image_bytes))
    # linkedin__value-prop ships 1200x627
    assert img.size == (1200, 627)
    # Validation
    assert post.validation_report.passed is True
    # Audit ran (audit_summary set by Plan 07)
    assert post.audit_summary != "unknown"


@pytest.mark.asyncio
async def test_generate_campaign_three_platforms_shares_hero_and_regenerates_copy() -> None:
    kit = _seeded_kit()
    text = _FakeTextClient(_canned_copy())
    comfy = _FakeComfy(_make_png(1024, 1024))
    campaign = await generate_campaign(
        kit,
        topic="Typed validation",
        platforms=["linkedin", "twitter", "instagram"],
        intent="value-prop",
        text_client=text,
        comfy_client=comfy,
        audit=False,
    )
    # ONE hero generation
    assert comfy.calls == 1
    # Copy generated once per platform (NOT truncated from shared copy)
    assert text.calls >= 3
    # All three platforms produced posts
    assert len(campaign.posts) == 3
    assert "linkedin__value-prop" in campaign.posts
    assert "twitter__value-prop" in campaign.posts
    assert "instagram__value-prop" in campaign.posts
