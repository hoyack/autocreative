"""Direct-invocation tests for ``task_generate_brochure`` (Plan 24.1-02 / PLF-02).

Worker-layer assertions for the **real bug surface**: the brochure worker
must invoke ``ComfyClient.generate`` when the request payload sets
``generate_images: true`` AND ``content.hero_concept`` is provided. Patches
``flyer_generator.stages.comfy_client.ComfyClient.generate`` directly via
``unittest.mock.patch.object`` so a regression in the worker→image_gate→
ComfyClient call chain surfaces here, not in the higher-level
``generate_template_images`` mock used by older tests.

Mirrors the pattern in ``tests/api/test_worker_postcard_tasks.py``: hand-rolls
a ``ctx`` dict, patches the rendering collaborators (``load_template`` /
``render_schema_brochure`` / ``Rasterizer`` / ``assemble_brochure_pdf``), seeds
a JobRecord, and awaits the real task function.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from flyer_generator.api.models import (
    JobKind,
    JobRecord,
    JobStatus,
)
from flyer_generator.models import ComfyJob
from flyer_generator.stages.comfy_client import ComfyClient


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _png_bytes() -> bytes:
    """Tiny PNG so ComfyClient.generate's stub return matches the real bytes shape."""
    import io

    from PIL import Image

    img = Image.new("RGB", (4, 4), color=(8, 8, 8))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _payload(*, generate_images: bool, hero_concept: str | None = "spring meadow") -> dict:
    """Brochure payload with optional hero_concept."""
    return {
        "template": "editorial_classic",
        "content": {
            "title": "PLF-02 Title",
            "subtitle": "PLF-02 Subtitle",
            "tagline": "Spring Update",
            "org": "PLF-02 Org",
            "hero_concept": hero_concept,
            "sections": [
                {"heading": "Section A", "lead_paragraph": "Lead A."},
                {"heading": "Section B", "lead_paragraph": "Lead B."},
                {"heading": "Section C", "lead_paragraph": "Lead C."},
            ],
        },
        "generate_images": generate_images,
        "workflow": "turbo_landscape",
        "style_preset": "photorealistic",
    }


async def _seed_job(sessionmaker, job_id: str) -> None:
    async with sessionmaker() as s:
        s.add(
            JobRecord(
                id=job_id,
                kind=JobKind.BROCHURE,
                status=JobStatus.QUEUED,
                input_payload={},
            )
        )
        await s.commit()


def _build_ctx(sessionmaker, tmp_path):
    from flyer_generator.api.config import AppSettings

    settings = AppSettings()
    settings.artifact_root_brochure = tmp_path
    return {"sessionmaker": sessionmaker, "settings": settings, "http_client": None}


def _fake_comfy_return(workflow_obj):
    """Build (ComfyJob, png_bytes) for ComfyClient.generate stubs."""
    job = ComfyJob(
        prompt_id="fake-id",
        submitted_at=datetime.now(timezone.utc),
        positive_prompt=getattr(workflow_obj, "positive_prompt", "p"),
        negative_prompt=getattr(workflow_obj, "negative_prompt", "n"),
        seed=getattr(workflow_obj, "seed", 0),
        attempt_number=1,
    )
    return (job, _png_bytes())


# ---------------------------------------------------------------------------
# Tests 6 + 7 — worker-layer Comfy invocation gate (PLF-02 real bug surface)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_generate_brochure_invokes_comfy_when_generate_images_true(
    sessionmaker_fx, tmp_path
) -> None:
    """PLF-02 real-bug-surface assertion.

    With ``generate_images: true`` and ``content.hero_concept`` set, the
    brochure worker must reach ``ComfyClient.generate`` (the outbound seam to
    ComfyCloud). Patching at this depth — rather than mocking
    ``generate_template_images`` — proves the worker actually wires Comfy at
    runtime, not just that ``image_gate`` is correct in isolation.
    """
    from flyer_generator.api.tasks.brochure import task_generate_brochure

    jid = "01HPLF02BRO0000000000000001"
    payload = _payload(generate_images=True, hero_concept="spring meadow")
    await _seed_job(sessionmaker_fx, jid)
    ctx = _build_ctx(sessionmaker_fx, tmp_path)

    # The cover-vision evaluator gates the hero loop. Stub it so the first
    # generate() result is approved — otherwise the hero loop retries up to
    # max_bg_attempts and the test becomes timing-sensitive. We patch the
    # vision class on the image_gate module path (the only place it's
    # constructed when cover_vision=None).
    fake_verdict = AsyncMock()  # acts as both stub object and awaitable holder
    fake_verdict_obj = type(
        "Verdict",
        (),
        {"approved": True, "rejection_reasons": [], "refinement_hint": ""},
    )()

    async def _fake_evaluate(self, *, image_bytes, concept, style_preset):
        return fake_verdict_obj

    async def _fake_generate(self, workflow, attempt=1):
        return _fake_comfy_return(workflow)

    fake_generate = AsyncMock(side_effect=_fake_generate)

    with patch.object(ComfyClient, "generate", new=fake_generate), patch(
        "flyer_generator.brochure.stages.vision.BrochureCoverVisionEvaluator.evaluate",
        new=_fake_evaluate,
    ), patch(
        "flyer_generator.api.tasks.brochure.render_schema_brochure",
        return_value=("<svg>outside</svg>", "<svg>inside</svg>"),
    ), patch(
        "flyer_generator.api.tasks.brochure.Rasterizer"
    ) as RastCls, patch(
        "flyer_generator.api.tasks.brochure.assemble_brochure_pdf",
        return_value=b"%PDF-1.4 fake",
    ):
        RastCls.return_value.rasterize.return_value = b"\x89PNG\r\n"
        result_ref = await task_generate_brochure(ctx, job_id=jid, payload=payload)

    assert result_ref == jid
    assert fake_generate.await_count >= 1, (
        "PLF-02 regression: ComfyClient.generate must be awaited at least once "
        "when payload has generate_images=true and content.hero_concept is set. "
        "The worker-image_gate-ComfyClient wiring is broken."
    )

    async with sessionmaker_fx() as s:
        job = (
            await s.execute(select(JobRecord).where(JobRecord.id == jid))
        ).scalar_one()
        assert job.status == JobStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_task_generate_brochure_skips_comfy_when_generate_images_false(
    sessionmaker_fx, tmp_path
) -> None:
    """When ``generate_images: false`` is on the request, the worker must NOT
    invoke ComfyClient.generate — image generation is fully bypassed and the
    renderer falls through to the placeholder fallback fill.
    """
    from flyer_generator.api.tasks.brochure import task_generate_brochure

    jid = "01HPLF02BRO0000000000000002"
    payload = _payload(generate_images=False, hero_concept="spring meadow")
    await _seed_job(sessionmaker_fx, jid)
    ctx = _build_ctx(sessionmaker_fx, tmp_path)

    fake_generate = AsyncMock(
        side_effect=AssertionError(
            "ComfyClient.generate must NOT be awaited when generate_images=False"
        )
    )

    with patch.object(ComfyClient, "generate", new=fake_generate), patch(
        "flyer_generator.api.tasks.brochure.render_schema_brochure",
        return_value=("<svg>outside</svg>", "<svg>inside</svg>"),
    ), patch(
        "flyer_generator.api.tasks.brochure.Rasterizer"
    ) as RastCls, patch(
        "flyer_generator.api.tasks.brochure.assemble_brochure_pdf",
        return_value=b"%PDF-1.4 fake",
    ):
        RastCls.return_value.rasterize.return_value = b"\x89PNG\r\n"
        result_ref = await task_generate_brochure(ctx, job_id=jid, payload=payload)

    assert result_ref == jid
    fake_generate.assert_not_awaited()

    async with sessionmaker_fx() as s:
        job = (
            await s.execute(select(JobRecord).where(JobRecord.id == jid))
        ).scalar_one()
        assert job.status == JobStatus.SUCCEEDED
