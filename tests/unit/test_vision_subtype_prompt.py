"""Vision subtype-aware prompt tests (Phase 22 FT-05).

Validates that:
- VISION_SYSTEM_PROMPT_EVENT / VISION_SYSTEM_PROMPT_INFO constants are exported.
- VISION_SYSTEM_PROMPT (legacy name) is an alias for the event prompt.
- Prompt bodies contain the subtype-appropriate zone schema hints.
- VisionEvaluator.evaluate() selects the right prompt + user-text per subtype.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from flyer_generator.config import Settings
from flyer_generator.models import (
    ComfyJob,
    FlyerInput,
    GeneratedBackground,
    LayoutZones,
    VisionVerdict,
)
from flyer_generator.stages.vision import (
    VISION_SYSTEM_PROMPT,
    VISION_SYSTEM_PROMPT_EVENT,
    VISION_SYSTEM_PROMPT_INFO,
    VisionEvaluator,
)


def _settings() -> Settings:
    return Settings(anthropic_api_key="test", comfycloud_api_key="test")


def _bg() -> GeneratedBackground:
    return GeneratedBackground(
        image_bytes=b"\x89PNG\r\n\x1a\n" + b"\x00" * 100,
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


def _event_flyer() -> FlyerInput:
    return FlyerInput(
        title="Gala",
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


def _info_flyer() -> FlyerInput:
    return FlyerInput(
        title="Notice",
        subtype="info",
        description="Road closure",
        call_to_action="Plan alternate route",
        org="City",
        style_concept="civic",
        style_preset="photorealistic",
    )


class TestPromptConstants:
    def test_event_prompt_imports(self) -> None:
        assert VISION_SYSTEM_PROMPT_EVENT is not None
        assert isinstance(VISION_SYSTEM_PROMPT_EVENT, str)

    def test_info_prompt_imports(self) -> None:
        assert VISION_SYSTEM_PROMPT_INFO is not None
        assert isinstance(VISION_SYSTEM_PROMPT_INFO, str)

    def test_backcompat_alias(self) -> None:
        assert VISION_SYSTEM_PROMPT is VISION_SYSTEM_PROMPT_EVENT

    def test_info_prompt_content(self) -> None:
        assert "TITLE" in VISION_SYSTEM_PROMPT_INFO
        assert "DESCRIPTION" in VISION_SYSTEM_PROMPT_INFO
        assert "ORG_CREDIT" in VISION_SYSTEM_PROMPT_INFO
        assert "FEE_BADGE" not in VISION_SYSTEM_PROMPT_INFO
        assert "DETAILS" not in VISION_SYSTEM_PROMPT_INFO
        # zones.details and zones.fee_badge must be documented as null.
        assert "null" in VISION_SYSTEM_PROMPT_INFO

    def test_event_prompt_content(self) -> None:
        for key in ("TITLE", "DETAILS", "FEE_BADGE", "ORG_CREDIT"):
            assert key in VISION_SYSTEM_PROMPT_EVENT


class TestEvaluateBranching:
    @pytest.mark.asyncio
    async def test_event_flyer_uses_event_prompt(self) -> None:
        ev = VisionEvaluator(settings=_settings())
        fake_verdict = VisionVerdict(
            approved=True,
            confidence=0.9,
            zones=LayoutZones(
                title="TOP_CENTER",
                details="BOTTOM_CENTER",
                fee_badge="TOP_RIGHT",
                org_credit="BOTTOM_CENTER",
            ),
            text_color="white",
            raw_response="{}",
        )
        with patch.object(
            ev, "_call_backend", new_callable=AsyncMock, return_value=fake_verdict
        ) as mock:
            await ev.evaluate(_bg(), _event_flyer())
            kwargs = mock.call_args.kwargs
            assert kwargs["system_prompt"] is VISION_SYSTEM_PROMPT_EVENT
            assert "Date:" in kwargs["user_text"]
            assert "Fees:" in kwargs["user_text"]
            assert "Venue:" in kwargs["user_text"]

    @pytest.mark.asyncio
    async def test_info_flyer_uses_info_prompt(self) -> None:
        ev = VisionEvaluator(settings=_settings())
        fake_verdict = VisionVerdict(
            approved=True,
            confidence=0.9,
            zones=LayoutZones(
                title="TOP_CENTER",
                details=None,
                fee_badge=None,
                org_credit="BOTTOM_CENTER",
            ),
            text_color="white",
            raw_response="{}",
        )
        with patch.object(
            ev, "_call_backend", new_callable=AsyncMock, return_value=fake_verdict
        ) as mock:
            await ev.evaluate(_bg(), _info_flyer())
            kwargs = mock.call_args.kwargs
            assert kwargs["system_prompt"] is VISION_SYSTEM_PROMPT_INFO
            assert "Headline:" in kwargs["user_text"]
            assert "Description:" in kwargs["user_text"]
            assert "Call to action:" in kwargs["user_text"]
            assert "Date:" not in kwargs["user_text"]
            assert "Fees:" not in kwargs["user_text"]
