"""Brochure route tests (API-07)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from flyer_generator.api.models import BrochureRecord, JobKind, JobRecord, JobStatus, RenderRecord


def _minimal_brochure_content() -> dict:
    """Construct a minimal BrochureContent dict.

    Fields verified against flyer_generator/brochure/schema_renderer/content_model.py:
      - BrochureContent requires: title: str, org: str, sections: list[ContentSection]
        (min_length=1), and uses ConfigDict(extra="forbid") so unknown keys
        (`cta`, `body` on a section, etc.) are rejected.
      - ContentSection requires: heading: str, and uses body_paragraphs: list[str]
        (NOT `body: str`). Also extra="forbid".

    Executor: if BrochureContent gains a required field later, grep
    `flyer_generator/brochure/schema_renderer/content_model.py` for
    `class BrochureContent` and update this helper.
    """
    return {
        "title": "Sample Brochure",
        "subtitle": "Built via API",
        "org": "Test Co",
        "sections": [
            {"heading": "Intro", "body_paragraphs": ["Hello world."], "bullets": []},
        ],
    }


@pytest.mark.asyncio
async def test_post_brochure_returns_202(client, fake_arq_pool, sessionmaker_fx) -> None:
    body = {
        "content": _minimal_brochure_content(),
        "template": "editorial_classic",
        "generate_images": False,
    }
    r = await client.post("/api/v1/brochures", json=body)
    assert r.status_code == 202, r.text

    job_id = r.json()["job_id"]
    assert len(fake_arq_pool.calls) == 1
    fn, _, kwargs = fake_arq_pool.calls[0]
    assert fn == "task_generate_brochure"
    assert kwargs["job_id"] == job_id
    assert kwargs["payload"]["template"] == "editorial_classic"

    async with sessionmaker_fx() as s:
        job = (await s.execute(select(JobRecord).where(JobRecord.id == job_id))).scalar_one()
        assert job.kind == JobKind.BROCHURE
        assert job.status == JobStatus.QUEUED


@pytest.mark.asyncio
async def test_post_brochure_rejects_missing_content(client) -> None:
    r = await client.post("/api/v1/brochures", json={"template": "editorial_classic"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_brochure_rejects_bad_slug(client) -> None:
    body = {
        "content": _minimal_brochure_content(),
        "template": "editorial_classic",
        "brand_kit_slug": "BAD_UPPER",
    }
    r = await client.post("/api/v1/brochures", json=body)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_brochure_defaults_generate_images_true(client, fake_arq_pool) -> None:
    body = {"content": _minimal_brochure_content(), "template": "editorial_classic"}
    r = await client.post("/api/v1/brochures", json=body)
    assert r.status_code == 202
    _, _, kwargs = fake_arq_pool.calls[0]
    assert kwargs["payload"]["generate_images"] is True


@pytest.mark.asyncio
async def test_post_brochure_rejects_extra_fields(client) -> None:
    body = {
        "content": _minimal_brochure_content(),
        "template": "editorial_classic",
        "rogue_field": "x",
    }
    r = await client.post("/api/v1/brochures", json=body)
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/brochures/{brochure_id} — detail route (Plan 21-07 Task 1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_brochure_detail_returns_404_when_missing(client) -> None:
    """Missing brochure id (valid 26-char ULID shape) returns 404."""
    # 26-char ULID-shaped string with no matching row.
    resp = await client.get("/api/v1/brochures/01TESTTESTTESTTESTTESTTEST")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_brochure_detail_returns_3_render_urls(client, sessionmaker_fx) -> None:
    """Seed a BrochureRecord + 3 RenderRecords and verify the detail fuse."""
    async with sessionmaker_fx() as s:
        front = RenderRecord(kind="brochure_front", file_path="/tmp/front.png")
        back = RenderRecord(kind="brochure_back", file_path="/tmp/back.png")
        pdf = RenderRecord(kind="brochure_pdf", file_path="/tmp/print.pdf")
        s.add_all([front, back, pdf])
        await s.flush()
        brochure_id = "01BROCBROCBROCBROCBROCBROC"
        brochure = BrochureRecord(
            id=brochure_id,
            title="t",
            template="editorial_classic",
            brand_kit_slug=None,
            content_payload={},
            render_front_id=front.id,
            render_back_id=back.id,
            render_pdf_id=pdf.id,
        )
        s.add(brochure)
        await s.commit()
        # Capture the render ids before leaving the session context.
        front_id, back_id, pdf_id = front.id, back.id, pdf.id

    resp = await client.get(f"/api/v1/brochures/{brochure_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == brochure_id
    assert body["template"] == "editorial_classic"
    assert body["front_render_url"] == f"/api/v1/renders/{front_id}/image"
    assert body["back_render_url"] == f"/api/v1/renders/{back_id}/image"
    assert body["pdf_render_url"] == f"/api/v1/renders/{pdf_id}/image"


@pytest.mark.asyncio
async def test_get_brochure_detail_short_id_422(client) -> None:
    """A brochure_id shorter than 26 chars fails PathParam validation (422)."""
    resp = await client.get("/api/v1/brochures/tooshort")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Plan 21-12 WR-03 regression: enqueue failure must flip JobRecord to FAILED
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_brochure_enqueue_failure_marks_job_failed(
    fake_arq_pool, sessionmaker_fx, app, monkeypatch
) -> None:
    """WR-03 regression: if arq enqueue_job raises, the JobRecord must be
    flipped to FAILED with error_detail before the 5xx propagates. Otherwise
    the row sits in QUEUED forever and the dashboard shows a ghost job.

    Uses a dedicated client with ``raise_app_exceptions=False`` so the 5xx
    surfaces as a normal response instead of propagating through the ASGI
    transport — this mirrors how a real HTTP client would observe the error.
    """
    from httpx import ASGITransport, AsyncClient

    # Force enqueue_job to raise — simulates Redis down / arq pool misconfig.
    async def boom(*_a, **_kw):
        raise RuntimeError("redis unreachable")

    monkeypatch.setattr(fake_arq_pool, "enqueue_job", boom)

    body = {
        "content": _minimal_brochure_content(),
        "template": "editorial_classic",
        "generate_images": False,
    }

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/v1/brochures", json=body)
    assert r.status_code >= 500, r.text

    # Exactly one JobRecord exists and it is FAILED with a typed error_detail.
    async with sessionmaker_fx() as s:
        rows = (
            await s.execute(select(JobRecord).where(JobRecord.kind == JobKind.BROCHURE))
        ).scalars().all()
        assert len(rows) == 1, f"Expected 1 brochure JobRecord, got {len(rows)}"
        row = rows[0]
        assert row.status == JobStatus.FAILED, (
            f"Expected FAILED, got {row.status}. WR-03: enqueue failure "
            "left a stale QUEUED row."
        )
        assert row.error_detail is not None
        assert row.error_detail.get("reason") == "enqueue_failed"
