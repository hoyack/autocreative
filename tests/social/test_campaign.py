"""Per checker B1: direct-module imports only."""

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
from flyer_generator.errors import CampaignError
from flyer_generator.social.campaign import generate_campaign
from flyer_generator.social.models import Campaign


def _make_kit() -> BrandKit:
    return BrandKit(
        name="Test Brand",
        fetched_at=datetime(2026, 4, 21, tzinfo=timezone.utc),
        palette=BrandPalette(
            primary=ColorUsage(hex="#1E3A5F"),
            secondary=ColorUsage(hex="#C4A269"),
            accent=ColorUsage(hex="#E8F1F2"),
            neutral_dark=ColorUsage(hex="#1A1A1A"),
            neutral_light=ColorUsage(hex="#FAFAF7"),
        ),
        typography=BrandTypography(heading_family="sans", body_family="sans"),
        voice=BrandVoice(tone="direct", banned_words=[]),
    )


def _make_png(w: int, h: int) -> bytes:
    img = Image.new("RGB", (w, h), (64, 128, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


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


def _canned_copy() -> str:
    return json.dumps(
        {
            "copy.title": "T",
            "copy.body": "Short body.",
            "copy.cta": "C",
            "copy.hashtags": ["#a"],
        }
    )


@pytest.mark.asyncio
async def test_generate_campaign_shares_hero_across_platforms() -> None:
    kit = _make_kit()
    text = _FakeTextClient(_canned_copy())
    comfy = _FakeComfy(_make_png(1024, 1024))
    campaign = await generate_campaign(
        kit,
        topic="typed validation",
        platforms=["linkedin", "twitter", "instagram"],
        intent="value-prop",
        text_client=text,
        comfy_client=comfy,
        audit=False,
    )
    assert isinstance(campaign, Campaign)
    assert comfy.calls == 1, (
        "campaign should generate ONE shared hero, not one per platform"
    )
    assert text.calls >= 3, (
        "copy should be generated per-platform (at least one call each)"
    )
    assert len(campaign.posts) == 3


@pytest.mark.asyncio
async def test_generate_campaign_empty_platforms_raises() -> None:
    kit = _make_kit()
    with pytest.raises(CampaignError):
        await generate_campaign(kit, topic="t", platforms=[], intent="value-prop")


@pytest.mark.asyncio
async def test_generate_campaign_with_story_uses_portrait_workflow() -> None:
    kit = _make_kit()
    text = _FakeTextClient(_canned_copy())
    comfy = _FakeComfy(_make_png(832, 1472))
    campaign = await generate_campaign(
        kit,
        topic="t",
        platforms=["instagram", "linkedin"],
        intent="value-prop",
        include_story=True,
        text_client=text,
        comfy_client=comfy,
    )
    assert comfy.calls == 1
    assert campaign.campaign_id  # ULID
    # campaign_id is 26 chars Base32
    assert len(campaign.campaign_id) == 26
