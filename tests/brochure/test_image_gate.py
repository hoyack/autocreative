"""Tests for the generate_single_image helper added by Phase 19 Plan 07 Task 0.

Per checker B1: direct-module imports only.

PLF-02 (Plan 24.1-02 Task 1) adds image_gate-level coverage for the
hero_concept-driven Comfy invocation path. These are function-level
regression tests; the worker-layer (real-bug-surface) assertions live in
``tests/api/test_worker_brochure_tasks.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from flyer_generator.brochure.schema_renderer.content_model import (
    BrochureContent,
    ContentSection,
)
from flyer_generator.brochure.schema_renderer.image_gate import (
    generate_single_image,
    generate_template_images,
)
from flyer_generator.brochure.schema_renderer.loader import load_template
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


# --------------------------------------------------------------------------- #
# PLF-02 — hero_concept gating in generate_template_images
# --------------------------------------------------------------------------- #


def _plf02_content_for_image_gate(*, hero_concept: str | None) -> BrochureContent:
    """Minimal BrochureContent that satisfies BrochureInput's section min_length."""
    return BrochureContent(
        title="PLF-02 Title",
        subtitle="PLF-02 Subtitle",
        org="PLF-02 Org",
        hero_concept=hero_concept,
        sections=[
            ContentSection(heading="Section A", lead_paragraph="Lead A."),
            ContentSection(heading="Section B", lead_paragraph="Lead B."),
            ContentSection(heading="Section C", lead_paragraph="Lead C."),
        ],
    )


def _png_bytes() -> bytes:
    """Tiny in-memory PNG for ComfyClient.generate stub returns."""
    import io

    from PIL import Image

    img = Image.new("RGB", (4, 4), color=(8, 8, 8))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _fake_comfy_job(workflow_obj) -> ComfyJob:
    return ComfyJob(
        prompt_id="fake-id",
        submitted_at=datetime.now(timezone.utc),
        positive_prompt=getattr(workflow_obj, "positive_prompt", "p"),
        negative_prompt=getattr(workflow_obj, "negative_prompt", "n"),
        seed=getattr(workflow_obj, "seed", 0),
        attempt_number=1,
    )


@pytest.mark.asyncio
async def test_generate_template_images_skips_hero_when_hero_concept_missing() -> None:
    """When ``content.hero_concept`` is None, the hero branch never invokes
    ComfyClient.generate and the result dict has no 'hero' key.
    """
    template = load_template("editorial_classic")
    content = _plf02_content_for_image_gate(hero_concept=None)

    fake_client = MagicMock(spec=ComfyClient)
    fake_client.generate = AsyncMock(
        side_effect=AssertionError(
            "ComfyClient.generate must NOT be awaited when hero_concept is None"
        )
    )

    result = await generate_template_images(
        template,
        content,
        comfy_client=fake_client,
        cover_builder=MagicMock(),  # never invoked because hero is skipped
        cover_vision=MagicMock(),
    )

    fake_client.generate.assert_not_awaited()
    assert "hero" not in result


@pytest.mark.asyncio
async def test_generate_template_images_invokes_comfy_when_hero_concept_present() -> None:
    """When ``content.hero_concept`` is set and the cover-vision verdict approves,
    ComfyClient.generate is awaited (at least once) and the result has 'hero'.
    """
    template = load_template("editorial_classic")
    content = _plf02_content_for_image_gate(hero_concept="lush spring garden")

    raw_png = _png_bytes()

    fake_client = MagicMock(spec=ComfyClient)

    async def _fake_generate(workflow, attempt):
        return (_fake_comfy_job(workflow), raw_png)

    fake_client.generate = AsyncMock(side_effect=_fake_generate)

    fake_builder = MagicMock()
    # builder.build returns a stand-in workflow object; the renderer doesn't
    # introspect its fields, only passes it to ComfyClient.generate.
    fake_builder.build.return_value = MagicMock(
        positive_prompt="p", negative_prompt="n", seed=42
    )

    fake_vision = MagicMock()
    fake_verdict = MagicMock(
        approved=True, rejection_reasons=[], refinement_hint=""
    )
    fake_vision.evaluate = AsyncMock(return_value=fake_verdict)

    result = await generate_template_images(
        template,
        content,
        comfy_client=fake_client,
        cover_builder=fake_builder,
        cover_vision=fake_vision,
    )

    assert fake_client.generate.await_count >= 1, (
        "ComfyClient.generate must be awaited when hero_concept is set + vision approves."
    )
    assert "hero" in result
    assert result["hero"] == raw_png
