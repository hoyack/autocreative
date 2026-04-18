"""End-to-end integration test for generate_brochure_from_prompt.

All external dependencies (LLM text, Comfy, vision) are mocked via the injected
text_client + module-level monkeypatches so the pipeline runs offline and fast.
"""

from __future__ import annotations

import io
import json
from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from PIL import Image
from pydantic import SecretStr

from flyer_generator.brochure import BrochureOutput, generate_brochure_from_prompt
from flyer_generator.brochure.stages.layout import (
    BLEED_CANVAS_HEIGHT,
    BLEED_CANVAS_WIDTH,
)
from flyer_generator.config import Settings
from flyer_generator.models import ComfyJob, VisionVerdict


def _settings() -> Settings:
    return Settings(
        anthropic_api_key=SecretStr("sk-test"),
        comfycloud_api_key=SecretStr("t"),
        max_bg_attempts=2,
        vision_confidence_threshold=0.6,
    )


def _text_client_for_pipeline() -> AsyncMock:
    """Mock text client that returns different JSON depending on the prompt content."""
    outline_json = json.dumps(
        {
            "sections": [
                {"heading": "Welcome", "body_brief": "hero", "image_hint": None, "panel_role": "cover"},
                {"heading": "Classes", "body_brief": "list formats", "image_hint": "yoga mats", "panel_role": "feature"},
                {"heading": "Memberships", "body_brief": "pricing tiers", "image_hint": None, "panel_role": "detail"},
                {"heading": "Visit", "body_brief": "address + hours", "image_hint": None, "panel_role": "cta"},
            ],
            "tone": "calm, welcoming",
            "cta_intent": "book a first class",
            "suggested_preset": "photorealistic",
            "suggested_accent": "#7BB661",
        }
    )
    layout_json = json.dumps(
        {
            "template": "editorial",
            "shape_density": "medium",
            "accent_placement": "top_rule",
            "cover_treatment": "image_full",
        }
    )
    body_text = "Generated section body suitable for a brochure panel."

    client = AsyncMock()

    async def _complete(*, system: str, user: str, response_format: str = "text") -> str:
        # Route by system-prompt fingerprint (cheap but reliable).
        if "brochure copywriter" in system:
            return outline_json
        if "layout template" in system or "brand designer picking" in system:
            return layout_json
        # Everything else (text + fit) returns body text.
        return body_text

    client.complete = AsyncMock(side_effect=_complete)
    return client


def _hero_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1472, 832), (120, 140, 180)).save(buf, "PNG")
    return buf.getvalue()


def _install_comfy_and_vision_mocks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch ComfyClient.generate and BrochureCoverVisionEvaluator.evaluate."""
    hero = _hero_png()
    job = ComfyJob(
        prompt_id="p",
        submitted_at=datetime(2026, 4, 18),
        positive_prompt="p",
        negative_prompt="n",
        seed=1,
        attempt_number=1,
    )

    async def fake_generate(self, workflow, attempt):
        return job, hero

    monkeypatch.setattr(
        "flyer_generator.stages.comfy_client.ComfyClient.generate",
        fake_generate,
    )

    approved = VisionVerdict(
        approved=True,
        confidence=0.9,
        zones=None,
        rejection_reasons=[],
        refinement_hint="",
        text_color="white",
        mood_tags=[],
        raw_response="{}",
    )

    async def fake_cover_evaluate(self, image_bytes, concept, style_preset=""):
        return approved

    monkeypatch.setattr(
        "flyer_generator.brochure.stages.vision.BrochureCoverVisionEvaluator.evaluate",
        fake_cover_evaluate,
    )

    # Also patch the verify stage's vision evaluator to return a high-confidence verdict.
    async def fake_evaluate_cover(self, image_bytes, concept, style_preset=""):
        return approved

    monkeypatch.setattr(
        "flyer_generator.stages.vision.VisionEvaluator.evaluate_cover",
        fake_evaluate_cover,
    )


# -------------------------------- Tests --------------------------------


@pytest.mark.asyncio
async def test_generate_from_prompt_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_comfy_and_vision_mocks(monkeypatch)

    result = await generate_brochure_from_prompt(
        prompt="a tri-fold brochure for a neighborhood yoga studio for new moms",
        settings=_settings(),
        text_client=_text_client_for_pipeline(),
        verify_threshold=70,
        max_verify_iterations=1,
    )

    assert isinstance(result, BrochureOutput)
    assert len(result.front_png_bytes) > 0
    assert len(result.back_png_bytes) > 0
    assert result.pdf_bytes.startswith(b"%PDF-")
    assert result.dimensions == (BLEED_CANVAS_WIDTH, BLEED_CANVAS_HEIGHT)
    assert result.trace_id  # non-empty
    # verify_threshold was 70 → verification must be attached to the output
    assert result.verification is not None
    assert 0 <= result.verification.score <= 100
    # Mechanical lint runs unconditionally; report must be attached
    assert result.lint_report is not None
    assert "_summary" in result.lint_report


@pytest.mark.asyncio
async def test_generate_from_prompt_skips_verify_when_threshold_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_comfy_and_vision_mocks(monkeypatch)

    result = await generate_brochure_from_prompt(
        prompt="a brochure",
        settings=_settings(),
        text_client=_text_client_for_pipeline(),
        verify_threshold=0,
        max_verify_iterations=1,
    )
    # Pipeline still returns a BrochureOutput; verification just skipped.
    assert result.pdf_bytes.startswith(b"%PDF-")


@pytest.mark.asyncio
async def test_generate_from_prompt_accepts_user_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_comfy_and_vision_mocks(monkeypatch)

    # User overrides preset + accent; outline returns different values but generate_outline echoes overrides.
    result = await generate_brochure_from_prompt(
        prompt="a brochure",
        settings=_settings(),
        text_client=_text_client_for_pipeline(),
        style_preset="anime",
        color_accent="#FF0000",
        verify_threshold=0,
        max_verify_iterations=1,
    )
    # Overrides are echoed in the outline; downstream composition uses those values.
    # We don't easily introspect them from BrochureOutput, but the run should not error.
    assert isinstance(result, BrochureOutput)


@pytest.mark.asyncio
async def test_generate_from_prompt_produces_renderable_svg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sanity: generated PNGs should be valid image bytes openable by Pillow."""
    _install_comfy_and_vision_mocks(monkeypatch)

    result = await generate_brochure_from_prompt(
        prompt="a brochure",
        settings=_settings(),
        text_client=_text_client_for_pipeline(),
        verify_threshold=0,
        max_verify_iterations=1,
    )

    front_img = Image.open(io.BytesIO(result.front_png_bytes))
    back_img = Image.open(io.BytesIO(result.back_png_bytes))
    assert front_img.size == (BLEED_CANVAS_WIDTH, BLEED_CANVAS_HEIGHT)
    assert back_img.size == (BLEED_CANVAS_WIDTH, BLEED_CANVAS_HEIGHT)
