"""Tests for the generate_single_image helper added by Phase 19 Plan 07 Task 0.

Per checker B1: direct-module imports only.
"""

from __future__ import annotations

import httpx
import pytest

from flyer_generator.brochure.schema_renderer.image_gate import (
    generate_single_image,
)
from flyer_generator.config import Settings
from flyer_generator.models import ComfyJob
from flyer_generator.stages.comfy_client import ComfyClient


@pytest.mark.asyncio
async def test_generate_single_image_returns_png_bytes(monkeypatch) -> None:
    """generate_single_image returns bytes from ComfyClient.generate (mocked)."""
    fake_png = b"\x89PNG\r\n\x1a\nFAKE"

    async def _fake_generate(self, workflow, attempt=1):
        from datetime import datetime, timezone
        job = ComfyJob(
            prompt_id="fake-id",
            submitted_at=datetime.now(timezone.utc),
            positive_prompt=workflow.positive_prompt,
            negative_prompt=workflow.negative_prompt,
            seed=workflow.seed,
            attempt_number=attempt,
        )
        return (job, fake_png)

    monkeypatch.setattr(ComfyClient, "generate", _fake_generate)

    async with httpx.AsyncClient() as http:
        result = await generate_single_image(
            workflow_name="ernie_landscape",
            prompt="a dramatic golden-hour sunset over a rocky coast",
            settings=Settings(),
            http_client=http,
        )
    assert result == fake_png


@pytest.mark.asyncio
async def test_generate_single_image_uses_correct_comfy_client_init(monkeypatch) -> None:
    """B-05 regression: helper must call ComfyClient(settings, http_client) — NOT ComfyClient(settings=settings) alone."""
    captured: dict = {}

    original_init = ComfyClient.__init__

    def _capturing_init(self, settings, http_client):
        captured["settings"] = settings
        captured["http_client"] = http_client
        original_init(self, settings, http_client)

    async def _fake_generate(self, workflow, attempt=1):
        from datetime import datetime, timezone
        job = ComfyJob(
            prompt_id="x",
            submitted_at=datetime.now(timezone.utc),
            positive_prompt=workflow.positive_prompt,
            negative_prompt=workflow.negative_prompt,
            seed=workflow.seed,
            attempt_number=attempt,
        )
        return (job, b"png-bytes")

    monkeypatch.setattr(ComfyClient, "__init__", _capturing_init)
    monkeypatch.setattr(ComfyClient, "generate", _fake_generate)

    async with httpx.AsyncClient() as http:
        await generate_single_image(
            workflow_name="ernie_landscape",
            prompt="test",
            settings=Settings(),
            http_client=http,
        )
    assert "settings" in captured
    assert captured["http_client"] is not None
