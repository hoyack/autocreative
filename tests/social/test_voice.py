"""Per Phase 18 checker B1: imports use direct-module paths so this file
never imports from the package-root __init__.py (which does not yet exist
for flyer_generator.social)."""

from __future__ import annotations

import json

import pytest

from flyer_generator.brand_kit.models import BrandVoice
from flyer_generator.brochure.schema_renderer import load_template
from flyer_generator.brochure.schema_renderer.text_gen import (
    _assemble_system_prompt,
    _enforce_banned_words,
    generate_content_from_prompt,
)
from flyer_generator.errors import BrandKitError, BrandVoiceViolationError, FlyerGeneratorError


def test_brand_voice_violation_error_is_brand_kit_error_subclass() -> None:
    err = BrandVoiceViolationError("x")
    assert isinstance(err, BrandKitError)
    assert isinstance(err, FlyerGeneratorError)


def test_brand_voice_violation_error_populates_context_fields() -> None:
    err = BrandVoiceViolationError(
        "banned word used",
        banned_matches=["ai", "ml"],
        keys=["copy.body", "copy.title"],
    )
    assert err.banned_matches == ["ai", "ml"]
    assert err.keys == ["copy.body", "copy.title"]


def test_brand_voice_violation_error_defaults_empty_lists() -> None:
    err = BrandVoiceViolationError("msg")
    assert err.banned_matches == []
    assert err.keys == []


# --------------------------------------------------------------------------- #
# _assemble_system_prompt + _enforce_banned_words unit tests
# --------------------------------------------------------------------------- #


def test_assemble_system_prompt_none_returns_base_unchanged() -> None:
    base = "SYSTEM BASE"
    assert _assemble_system_prompt(None, base) == base


def test_assemble_system_prompt_includes_voice_directive() -> None:
    voice = BrandVoice(
        tone="warm and direct",
        example_phrases=["we ship", "built for humans"],
        banned_words=["synergy"],
    )
    out = _assemble_system_prompt(voice, "SYSTEM BASE")
    assert "VOICE DIRECTIVE" in out
    assert "warm and direct" in out
    assert "we ship" in out
    assert "synergy" in out
    assert out.endswith("SYSTEM BASE")


def test_enforce_banned_words_case_insensitive_word_boundary() -> None:
    # "AI" in "AI-powered" matches on word boundary; "AI" in "retain" does NOT
    assert _enforce_banned_words("AI-powered by AI", ["ai"]) == ["AI", "AI"]
    assert _enforce_banned_words("retain details", ["ai"]) == []


def test_enforce_banned_words_empty_banned_is_noop() -> None:
    # Fast-path: empty list returns [] with no regex compile
    assert _enforce_banned_words("any text with synergy", []) == []


# --------------------------------------------------------------------------- #
# generate_content_from_prompt voice-wiring integration tests
# --------------------------------------------------------------------------- #


class _FakeTextClient:
    """Minimal TextClient stand-in: queues canned responses and records calls."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def complete(
        self, *, system: str, user: str, response_format: str
    ) -> str:
        self.calls.append(
            {"system": system, "user": user, "response_format": response_format}
        )
        return self._responses.pop(0)

    async def aclose(self) -> None:  # pragma: no cover - noop
        return None


def _minimal_llm_json(body_text: str) -> dict:
    """Build a minimal LLM JSON response matching BrochureContent shape.

    `body_text` is placed in sections[0].body_paragraphs[0] so tests can
    thread banned words into a deterministic leaf key ("sections[0]...").
    """
    return {
        "title": "Short Title",
        "subtitle": "Sub",
        "tagline": "Tag",
        "org": "Acme",
        "hero_concept": "warm photograph",
        "color_accent": "#111111",
        "contact": {},
        "sections": [
            {
                "heading": "One",
                "lead_paragraph": "Intro.",
                "body_paragraphs": [body_text],
                "bullets": ["a", "b", "c"],
                "image_concept": "scene",
            },
            {
                "heading": "Two",
                "lead_paragraph": "Middle.",
                "body_paragraphs": ["Clean copy."],
                "bullets": ["x", "y", "z"],
                "image_concept": "scene",
            },
            {
                "heading": "Three",
                "lead_paragraph": "End.",
                "body_paragraphs": ["Final."],
                "bullets": ["p", "q", "r"],
                "image_concept": "scene",
            },
        ],
        "back_panel": {"kind": "cta", "heading": "Ready", "body": "Go"},
    }


async def test_system_prompt_omits_voice_directive_when_brand_voice_none() -> None:
    template = load_template("hero_image_dominant")
    client = _FakeTextClient([json.dumps(_minimal_llm_json("clean copy"))])
    await generate_content_from_prompt(
        template, "describe business", text_client=client
    )
    assert client.calls, "expected at least one LLM call"
    assert "VOICE DIRECTIVE" not in client.calls[0]["system"]


async def test_system_prompt_injects_voice_directive_when_brand_voice_supplied() -> None:
    template = load_template("hero_image_dominant")
    voice = BrandVoice(
        tone="warm and direct",
        example_phrases=["we ship", "built for humans"],
        banned_words=["synergy"],
    )
    client = _FakeTextClient([json.dumps(_minimal_llm_json("clean copy"))])
    await generate_content_from_prompt(
        template, "describe business", text_client=client, brand_voice=voice
    )
    system = client.calls[0]["system"]
    assert "VOICE DIRECTIVE" in system
    assert "warm and direct" in system
    assert "we ship" in system
    assert "synergy" in system


async def test_voice_retry_on_banned_word_then_clean() -> None:
    template = load_template("hero_image_dominant")
    voice = BrandVoice(
        tone="warm", example_phrases=[], banned_words=["synergy"]
    )
    dirty = _minimal_llm_json("we are leveraging synergy across teams")
    clean = _minimal_llm_json("we are teaming up across groups")
    client = _FakeTextClient([json.dumps(dirty), json.dumps(clean)])

    await generate_content_from_prompt(
        template, "describe business", text_client=client, brand_voice=voice
    )
    # One original + one retry
    assert len(client.calls) == 2
    retry_user = client.calls[1]["user"]
    assert "banned words" in retry_user


async def test_voice_raises_after_retry_still_banned() -> None:
    template = load_template("hero_image_dominant")
    voice = BrandVoice(
        tone="warm", example_phrases=[], banned_words=["synergy"]
    )
    dirty = _minimal_llm_json("leveraging synergy everywhere")
    client = _FakeTextClient([json.dumps(dirty), json.dumps(dirty)])

    with pytest.raises(BrandVoiceViolationError) as excinfo:
        await generate_content_from_prompt(
            template, "describe business", text_client=client, brand_voice=voice
        )
    assert excinfo.value.banned_matches == ["synergy"]
    # Key path should point at the leaf that held the banned word
    assert any("body_paragraphs" in k for k in excinfo.value.keys)
