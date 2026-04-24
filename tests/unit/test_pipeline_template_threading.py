"""FlyerGenerator.generate template-kwarg threading tests (Phase 22 FT-03)."""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from flyer_generator import FlyerGenerator
from flyer_generator.config import Settings
from flyer_generator.flyer.schema_renderer.loader import load_template
from flyer_generator.models import (
    ComfyJob,
    FlyerInput,
    GeneratedBackground,
    LayoutZones,
    VisionVerdict,
)


def _settings() -> Settings:
    return Settings(anthropic_api_key="t", comfycloud_api_key="t")


def _event_flyer() -> FlyerInput:
    return FlyerInput(
        title="T",
        subtype="event",
        date="2026-05-01",
        time="7pm",
        location_name="Hall",
        location_address="1 Main",
        fees="Free",
        org="Acme",
        style_concept="c",
        style_preset="photorealistic",
    )


def _bg() -> GeneratedBackground:
    return GeneratedBackground(
        image_bytes=b"\x89PNG" + b"\x00" * 100,
        source_dimensions=(832, 1472),
        final_dimensions=(1080, 1920),
        comfy_job=ComfyJob(
            prompt_id="x",
            submitted_at=datetime.now(timezone.utc),
            positive_prompt="",
            negative_prompt="",
            seed=0,
            attempt_number=1,
        ),
    )


def _verdict_approved() -> VisionVerdict:
    return VisionVerdict(
        approved=True,
        confidence=0.9,
        text_color="white",
        raw_response="{}",
        zones=LayoutZones(
            title="TOP_CENTER",
            details="BOTTOM_CENTER",
            fee_badge="TOP_RIGHT",
            org_credit="BOTTOM_CENTER",
        ),
    )


def _verdict_rejected() -> VisionVerdict:
    return VisionVerdict(
        approved=False,
        confidence=0.2,
        text_color="white",
        rejection_reasons=["bad bg"],
        refinement_hint="brighter image please",
        raw_response="{}",
    )


class TestPipelineSignature:
    """The generate() method must expose `template` as keyword-only with default None."""

    def test_generate_has_keyword_only_template_param(self):
        sig = inspect.signature(FlyerGenerator.generate)
        params = sig.parameters
        assert "template" in params
        assert params["template"].kind == inspect.Parameter.KEYWORD_ONLY
        assert params["template"].default is None


class TestTemplateThreading:
    """generate() must forward `template=` to composer.compose on every attempt."""

    @pytest.mark.asyncio
    async def test_template_threaded_to_composer(self):
        """When template is provided, composer.compose receives it."""
        tpl = load_template("editorial_classic")
        http_client = httpx.AsyncClient()
        try:
            gen = FlyerGenerator(settings=_settings(), http_client=http_client)
            with patch.object(
                gen._comfy_client, "generate", new_callable=AsyncMock
            ) as m_comfy, patch.object(
                gen._preprocessor, "upscale"
            ) as m_pre, patch.object(
                gen._vision, "evaluate", new_callable=AsyncMock
            ) as m_vision, patch.object(
                gen._composer, "compose"
            ) as m_compose, patch.object(
                gen._rasterizer, "rasterize"
            ) as m_rast:
                m_comfy.return_value = (
                    _bg().comfy_job,
                    b"\x89PNG" + b"\x00" * 100,
                )
                m_pre.return_value = _bg()
                m_vision.return_value = _verdict_approved()
                m_compose.return_value = "<svg></svg>"
                m_rast.return_value = b"\x89PNG" + b"\x00" * 200

                await gen.generate(_event_flyer(), template=tpl)

                kwargs = m_compose.call_args.kwargs
                assert kwargs.get("template") is tpl
        finally:
            await http_client.aclose()

    @pytest.mark.asyncio
    async def test_no_template_passes_none_to_composer(self):
        """Back-compat: no template kwarg -> composer.compose called with template=None."""
        http_client = httpx.AsyncClient()
        try:
            gen = FlyerGenerator(settings=_settings(), http_client=http_client)
            with patch.object(
                gen._comfy_client, "generate", new_callable=AsyncMock
            ) as m_comfy, patch.object(
                gen._preprocessor, "upscale"
            ) as m_pre, patch.object(
                gen._vision, "evaluate", new_callable=AsyncMock
            ) as m_vision, patch.object(
                gen._composer, "compose"
            ) as m_compose, patch.object(
                gen._rasterizer, "rasterize"
            ) as m_rast:
                m_comfy.return_value = (
                    _bg().comfy_job,
                    b"\x89PNG" + b"\x00" * 100,
                )
                m_pre.return_value = _bg()
                m_vision.return_value = _verdict_approved()
                m_compose.return_value = "<svg></svg>"
                m_rast.return_value = b"\x89PNG" + b"\x00" * 200

                await gen.generate(_event_flyer())

                kwargs = m_compose.call_args.kwargs
                assert kwargs.get("template") is None
        finally:
            await http_client.aclose()

    @pytest.mark.asyncio
    async def test_template_passed_on_every_attempt_in_retry_loop(self):
        """If vision rejects N-1 times then approves, composer (called once on
        approval) must receive template= on that final compose."""
        tpl = load_template("editorial_classic")
        # Bump max_bg_attempts so we can exercise rejection retries.
        settings = _settings()
        settings.max_bg_attempts = 3
        http_client = httpx.AsyncClient()
        try:
            gen = FlyerGenerator(settings=settings, http_client=http_client)
            # Two rejections then an approval — the composer is called only
            # on approval, but the test confirms that after multiple loops
            # the template still threads through correctly.
            with patch.object(
                gen._comfy_client, "generate", new_callable=AsyncMock
            ) as m_comfy, patch.object(
                gen._preprocessor, "upscale"
            ) as m_pre, patch.object(
                gen._vision, "evaluate", new_callable=AsyncMock
            ) as m_vision, patch.object(
                gen._composer, "compose"
            ) as m_compose, patch.object(
                gen._rasterizer, "rasterize"
            ) as m_rast:
                m_comfy.return_value = (
                    _bg().comfy_job,
                    b"\x89PNG" + b"\x00" * 100,
                )
                m_pre.return_value = _bg()
                m_vision.side_effect = [
                    _verdict_rejected(),
                    _verdict_rejected(),
                    _verdict_approved(),
                ]
                m_compose.return_value = "<svg></svg>"
                m_rast.return_value = b"\x89PNG" + b"\x00" * 200

                await gen.generate(_event_flyer(), template=tpl)

                # Composer is called exactly once (only on approval).
                assert m_compose.call_count == 1
                kwargs = m_compose.call_args.kwargs
                assert kwargs.get("template") is tpl
                # Vision was called all 3 times.
                assert m_vision.call_count == 3
        finally:
            await http_client.aclose()
