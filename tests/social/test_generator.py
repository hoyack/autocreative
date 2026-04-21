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


class _FakeComfyClient:
    def __init__(self, png_bytes: bytes) -> None:
        self._png = png_bytes
        self.calls = 0

    async def generate_image(self, *, workflow_name: str, prompt: str, brand_kit) -> bytes:
        self.calls += 1
        return self._png


def _make_kit() -> BrandKit:
    return BrandKit(
        name="Test",
        fetched_at=datetime(2026, 4, 21, tzinfo=timezone.utc),
        palette=BrandPalette(
            primary=ColorUsage(hex="#1E3A5F"),
            secondary=ColorUsage(hex="#C4A269"),
            accent=ColorUsage(hex="#E8F1F2"),
            neutral_dark=ColorUsage(hex="#1A1A1A"),
            neutral_light=ColorUsage(hex="#FAFAF7"),
        ),
        typography=BrandTypography(
            heading_family="'Test', sans-serif",
            body_family="'Test', sans-serif",
        ),
        voice=BrandVoice(tone="direct", banned_words=[]),
    )


def _make_png(w: int = 512, h: int = 512) -> bytes:
    img = Image.new("RGB", (w, h), (64, 128, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _canned_copy() -> str:
    return json.dumps(
        {
            "copy.title": "Ship it",
            "copy.body": "Typed validation wins.",
            "copy.cta": "Read more",
            "copy.hashtags": ["#python", "#pydantic"],
        }
    )


@pytest.mark.asyncio
async def test_generate_post_linkedin_value_prop_e2e_mocked() -> None:
    brief = PostBrief(
        topic="Typed validation",
        intent="value-prop",
        platform="linkedin",
    )
    kit = _make_kit()
    text_client = _FakeTextClient(_canned_copy())
    comfy_client = _FakeComfyClient(_make_png())
    post = await generate_post(
        brief,
        kit,
        settings=None,
        text_client=text_client,
        comfy_client=comfy_client,
        audit=False,
    )
    assert post.platform == "linkedin"
    assert post.intent == "value-prop"
    assert post.copy.title == "Ship it"
    assert post.image_bytes is not None
    assert text_client.calls == 1
    assert comfy_client.calls == 1


@pytest.mark.asyncio
async def test_generate_post_twitter_announcement_text_only_skips_comfy() -> None:
    brief = PostBrief(
        topic="Launching today",
        intent="announcement",
        platform="twitter",
    )
    kit = _make_kit()
    text_client = _FakeTextClient(_canned_copy())
    comfy_client = _FakeComfyClient(_make_png())
    post = await generate_post(
        brief,
        kit,
        settings=None,
        text_client=text_client,
        comfy_client=comfy_client,
        audit=False,
    )
    assert post.platform == "twitter"
    assert post.image_bytes is None, "text-only should NOT render an image"
    assert comfy_client.calls == 0, "text-only should NOT call ComfyCloud"


@pytest.mark.asyncio
async def test_generate_post_produces_validation_report() -> None:
    brief = PostBrief(topic="T", intent="value-prop", platform="linkedin")
    kit = _make_kit()
    text_client = _FakeTextClient(_canned_copy())
    comfy_client = _FakeComfyClient(_make_png())
    post = await generate_post(
        brief, kit, text_client=text_client, comfy_client=comfy_client
    )
    assert post.validation_report.platform == "linkedin"
    # With valid short body + 2 hashtags + proper aspect, should be clean
    # (acceptance: no hard errors — warn is acceptable)
    assert post.validation_report.passed is True
