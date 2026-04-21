"""Per checker B1: direct-module imports only."""

from __future__ import annotations

import json

import pytest

from flyer_generator.brand_kit.models import BrandVoice
from flyer_generator.errors import BrandVoiceViolationError
from flyer_generator.social.models import PostBrief
from flyer_generator.social.platforms.linkedin import RULES as LI_RULES
from flyer_generator.social.schemas.loader import load_post_template
from flyer_generator.social.voice import (
    _build_system_prompt,
    _build_user_prompt,
    format_voice_directive,
    generate_social_copy,
)


class _FakeTextClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def complete(self, *, system: str, user: str, response_format: str) -> str:
        self.calls.append({"system": system, "user": user, "response_format": response_format})
        return self._responses.pop(0)

    async def aclose(self) -> None: ...


def _clean_json() -> str:
    return json.dumps(
        {
            "copy.title": "Typed validation wins",
            "copy.body": "Every engineer has shipped a runtime error that a type check would have caught.",
            "copy.cta": "Read more",
            "copy.hashtags": ["#python", "#pydantic", "#devops", "#typedcode"],
        }
    )


def _banned_json() -> str:
    return json.dumps(
        {
            "copy.title": "Leveraging synergy at scale",
            "copy.body": "We synergize our runtime validations.",
            "copy.cta": "Learn more",
            "copy.hashtags": ["#python"],
        }
    )


def test_format_voice_directive_none_is_empty_string() -> None:
    assert format_voice_directive(None) == ""


def test_format_voice_directive_includes_all_fields() -> None:
    voice = BrandVoice(
        tone="warm and direct",
        example_phrases=["we ship", "built for humans"],
        banned_words=["synergy"],
    )
    out = format_voice_directive(voice)
    assert "VOICE DIRECTIVE" in out
    assert "warm and direct" in out
    assert "we ship" in out
    assert "synergy" in out


def test_build_user_prompt_includes_link_policy_for_instagram() -> None:
    from flyer_generator.social.platforms.instagram import RULES as IG_RULES
    brief = PostBrief(topic="t", intent="value-prop", platform="instagram")
    tpl = load_post_template("instagram__value-prop")
    out = _build_user_prompt(brief, IG_RULES, tpl)
    assert "LINK POLICY" in out
    assert "strips URLs" in out


def test_build_system_prompt_injects_voice_when_provided() -> None:
    voice = BrandVoice(tone="bold", banned_words=["hype"])
    sys = _build_system_prompt(voice)
    assert "VOICE DIRECTIVE" in sys
    assert "bold" in sys


def test_build_system_prompt_no_voice_when_none() -> None:
    sys = _build_system_prompt(None)
    assert "VOICE DIRECTIVE" not in sys


@pytest.mark.asyncio
async def test_generate_social_copy_happy_path() -> None:
    brief = PostBrief(topic="typed validation", intent="value-prop", platform="linkedin")
    tpl = load_post_template("linkedin__value-prop")
    client = _FakeTextClient([_clean_json()])
    result = await generate_social_copy(
        brief, LI_RULES, tpl, brand_voice=None, text_client=client
    )
    assert result.title == "Typed validation wins"
    assert len(result.hashtags) == 4
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_generate_social_copy_retries_on_banned_then_succeeds() -> None:
    voice = BrandVoice(tone="direct", banned_words=["synergy"])
    brief = PostBrief(topic="t", intent="value-prop", platform="linkedin")
    tpl = load_post_template("linkedin__value-prop")
    client = _FakeTextClient([_banned_json(), _clean_json()])
    result = await generate_social_copy(
        brief, LI_RULES, tpl, brand_voice=voice, text_client=client
    )
    assert result.title == "Typed validation wins"  # came from clean response
    assert len(client.calls) == 2
    assert "banned words" in client.calls[1]["user"]


@pytest.mark.asyncio
async def test_generate_social_copy_raises_after_retry() -> None:
    voice = BrandVoice(tone="direct", banned_words=["synergy"])
    brief = PostBrief(topic="t", intent="value-prop", platform="linkedin")
    tpl = load_post_template("linkedin__value-prop")
    client = _FakeTextClient([_banned_json(), _banned_json()])
    with pytest.raises(BrandVoiceViolationError) as exc:
        await generate_social_copy(
            brief, LI_RULES, tpl, brand_voice=voice, text_client=client
        )
    assert "synergy" in exc.value.banned_matches


@pytest.mark.asyncio
async def test_generate_social_copy_hard_caps_hashtags() -> None:
    from flyer_generator.social.platforms.instagram import RULES as IG_RULES
    brief = PostBrief(topic="t", intent="value-prop", platform="instagram")
    tpl = load_post_template("instagram__value-prop")
    # LLM returns 35 hashtags — over IG hard cap of 30
    excess = json.dumps(
        {
            "copy.title": "t",
            "copy.body": "b",
            "copy.cta": "c",
            "copy.hashtags": [f"#tag{i}" for i in range(35)],
        }
    )
    client = _FakeTextClient([excess])
    result = await generate_social_copy(
        brief, IG_RULES, tpl, brand_voice=None, text_client=client
    )
    assert len(result.hashtags) == 30  # hard-capped
