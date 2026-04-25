"""Postcard route tests (Phase 23-04 PC-01 + PC-02).

Mirrors tests/api/test_brochure_routes.py: httpx.AsyncClient + ASGITransport
with the test-app fixture from conftest (stubbed arq_pool +
in-memory SQLite + sessionmaker).

Coverage:
  POST /api/v1/postcards happy + validation cases (missing template /
  missing headline / missing body / empty template / extra unknown key /
  with-address-block); compensating-enqueue WR-03 mirror (RuntimeError
  -> JobRecord FAILED with ``{"reason": "enqueue_failed", "type": ...}``,
  no ``str(exc)`` leak).

  GET /api/v1/postcards/{id} 404 + happy + null-render-id + malformed-id
  422.

  Router-registration smoke (postcards.router in ROUTERS).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from flyer_generator.api.models import (
    JobKind,
    JobRecord,
    JobStatus,
    PostcardRecord,
    RenderRecord,
)


def _post_body(with_address: bool = False) -> dict:
    body: dict = {
        "headline": "Hello Mailbox",
        "body": "This is the back of the postcard.",
        "template": "classic_portrait",
    }
    if with_address:
        body["address_block"] = {
            "recipient_name": "Jane Doe",
            "street": "123 Main St",
            "city_state_zip": "Springfield, IL 62701",
        }
    return body


# ---------------------------------------------------------------------------
# POST /api/v1/postcards — happy + state contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_postcard_returns_202(
    client, fake_arq_pool, sessionmaker_fx
) -> None:
    body = _post_body()
    r = await client.post("/api/v1/postcards", json=body)
    assert r.status_code == 202, r.text

    job_id = r.json()["job_id"]
    assert len(job_id) == 26  # ULID

    assert len(fake_arq_pool.calls) == 1
    fn, _, kwargs = fake_arq_pool.calls[0]
    assert fn == "task_generate_postcard"
    assert kwargs["job_id"] == job_id
    assert kwargs["payload"]["template"] == "classic_portrait"
    assert kwargs["payload"]["headline"] == "Hello Mailbox"

    async with sessionmaker_fx() as s:
        job = (
            await s.execute(select(JobRecord).where(JobRecord.id == job_id))
        ).scalar_one()
        assert job.kind == JobKind.POSTCARD
        assert job.status == JobStatus.QUEUED
        assert job.input_payload["template"] == "classic_portrait"
        assert job.input_payload["headline"] == "Hello Mailbox"


@pytest.mark.asyncio
async def test_post_postcard_with_address_block_round_trips(
    client, fake_arq_pool, sessionmaker_fx
) -> None:
    body = _post_body(with_address=True)
    r = await client.post("/api/v1/postcards", json=body)
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]

    async with sessionmaker_fx() as s:
        job = (
            await s.execute(select(JobRecord).where(JobRecord.id == job_id))
        ).scalar_one()
        ab = job.input_payload["address_block"]
        assert ab["recipient_name"] == "Jane Doe"
        assert ab["street"] == "123 Main St"
        assert ab["city_state_zip"] == "Springfield, IL 62701"


# ---------------------------------------------------------------------------
# POST validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_postcard_rejects_missing_template(client) -> None:
    body = {
        "headline": "x",
        "body": "y",
    }
    r = await client.post("/api/v1/postcards", json=body)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_postcard_rejects_missing_headline(client) -> None:
    body = {
        "body": "y",
        "template": "classic_portrait",
    }
    r = await client.post("/api/v1/postcards", json=body)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_postcard_rejects_missing_body(client) -> None:
    body = {
        "headline": "x",
        "template": "classic_portrait",
    }
    r = await client.post("/api/v1/postcards", json=body)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_postcard_rejects_empty_template(client) -> None:
    body = {
        "headline": "x",
        "body": "y",
        "template": "",
    }
    r = await client.post("/api/v1/postcards", json=body)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_postcard_rejects_extra_field(client) -> None:
    body = _post_body()
    body["rogue_field"] = "x"
    r = await client.post("/api/v1/postcards", json=body)
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Compensating-enqueue WR-03 mirror
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_postcard_enqueue_failure_marks_job_failed(
    fake_arq_pool, sessionmaker_fx, app, monkeypatch
) -> None:
    """Compensating-enqueue: arq raise -> JobRecord FAILED with typed error_detail.

    error_detail must be exactly {"reason": "enqueue_failed", "type": ...}
    with NO str(exc) leak (no Redis URI, no stack frames). Mirrors Phase
    21-12 WR-03 contract for brochures.
    """
    from httpx import ASGITransport, AsyncClient

    async def boom(*_a, **_kw):
        raise RuntimeError("redis unreachable secret://internal")

    monkeypatch.setattr(fake_arq_pool, "enqueue_job", boom)

    body = _post_body()
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/v1/postcards", json=body)

    assert r.status_code >= 500, r.text

    async with sessionmaker_fx() as s:
        rows = (
            await s.execute(select(JobRecord).where(JobRecord.kind == JobKind.POSTCARD))
        ).scalars().all()
        assert len(rows) == 1
        row = rows[0]
        assert row.status == JobStatus.FAILED
        assert row.error_detail == {
            "reason": "enqueue_failed",
            "type": "RuntimeError",
        }
        # Defense-in-depth: the secret string MUST NOT appear anywhere in
        # error_detail (no message field, no stack, no str(exc)).
        assert "redis unreachable" not in str(row.error_detail)
        assert "secret://internal" not in str(row.error_detail)


# ---------------------------------------------------------------------------
# GET /api/v1/postcards/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_postcard_detail_returns_404_when_missing(client) -> None:
    """Missing postcard id (valid 26-char ULID shape) returns 404."""
    resp = await client.get("/api/v1/postcards/01TESTTESTTESTTESTTESTTEST")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "postcard not found"


@pytest.mark.asyncio
async def test_get_postcard_detail_returns_3_render_urls(
    client, sessionmaker_fx
) -> None:
    """Seed a PostcardRecord + 3 RenderRecords; verify the detail fuse."""
    async with sessionmaker_fx() as s:
        front = RenderRecord(kind="postcard_front", file_path="/tmp/front.png")
        back = RenderRecord(kind="postcard_back", file_path="/tmp/back.png")
        pdf = RenderRecord(kind="postcard_pdf", file_path="/tmp/print.pdf")
        s.add_all([front, back, pdf])
        await s.flush()
        postcard_id = "01POSTPOSTPOSTPOSTPOSTPOST"
        postcard = PostcardRecord(
            id=postcard_id,
            template="classic_portrait",
            brand_kit_slug=None,
            content_payload={"headline": "x", "body": "y"},
            render_front_id=front.id,
            render_back_id=back.id,
            render_pdf_id=pdf.id,
        )
        s.add(postcard)
        await s.commit()
        front_id, back_id, pdf_id = front.id, back.id, pdf.id

    resp = await client.get(f"/api/v1/postcards/{postcard_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == postcard_id
    assert body["template"] == "classic_portrait"
    assert body["brand_kit_slug"] is None
    assert body["front_render_url"] == f"/api/v1/renders/{front_id}/image"
    assert body["back_render_url"] == f"/api/v1/renders/{back_id}/image"
    assert body["pdf_render_url"] == f"/api/v1/renders/{pdf_id}/image"


@pytest.mark.asyncio
async def test_get_postcard_detail_null_render_ids(
    client, sessionmaker_fx
) -> None:
    """When render_*_id columns are None the corresponding URLs are null."""
    async with sessionmaker_fx() as s:
        postcard_id = "01POSTPOSTNULLPOSTPOSTNULL"
        postcard = PostcardRecord(
            id=postcard_id,
            template="classic_portrait",
            brand_kit_slug=None,
            content_payload={},
            render_front_id=None,
            render_back_id=None,
            render_pdf_id=None,
        )
        s.add(postcard)
        await s.commit()

    resp = await client.get(f"/api/v1/postcards/{postcard_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["front_render_url"] is None
    assert body["back_render_url"] is None
    assert body["pdf_render_url"] is None


@pytest.mark.asyncio
async def test_get_postcard_detail_short_id_422(client) -> None:
    """A postcard_id shorter than 26 chars fails PathParam validation (422)."""
    resp = await client.get("/api/v1/postcards/tooshort")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Router registration smoke
# ---------------------------------------------------------------------------


def test_router_registered_in_routers_barrel() -> None:
    from flyer_generator.api.routes import ROUTERS, postcards

    assert postcards.router in ROUTERS
