"""Poster route tests (Phase 24-04 PO-01).

Mirrors tests/api/test_postcard_routes.py: httpx.AsyncClient + ASGITransport
with the test-app fixture from conftest (stubbed arq_pool + in-memory
SQLite + sessionmaker).

Coverage:
  POST /api/v1/posters happy + validation cases (missing headline /
  missing template / missing style_preset / invalid size / extra
  unknown key); each of the 3 locked sizes; compensating-enqueue
  WR-03 mirror (RuntimeError -> JobRecord FAILED with
  ``{"reason": "enqueue_failed", "type": ...}``, no ``str(exc)`` leak).

  Router-registration smoke (posters.router in ROUTERS).

  Defense-in-depth grep guard (no ``str(exc)`` substring in route file body).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from flyer_generator.api.models import (
    JobKind,
    JobRecord,
    JobStatus,
)


def _post_body(
    *,
    size: str = "18x24",
    template: str = "editorial_grand",
    style_preset: str = "editorial_modernist",
) -> dict:
    return {
        "headline": "Big Show Tonight",
        "subheading": "Doors at 7pm",
        "cta_text": "RSVP today",
        "image_hint": "moody twilight, neon accents",
        "brand_kit_slug": None,
        "style_preset": style_preset,
        "template": template,
        "size": size,
    }


# ---------------------------------------------------------------------------
# POST /api/v1/posters — happy + state contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_poster_returns_202_with_valid_body(
    client, fake_arq_pool, sessionmaker_fx
) -> None:
    body = _post_body(size="18x24")
    r = await client.post("/api/v1/posters", json=body)
    assert r.status_code == 202, r.text

    job_id = r.json()["job_id"]
    assert len(job_id) == 26  # ULID

    async with sessionmaker_fx() as s:
        job = (
            await s.execute(select(JobRecord).where(JobRecord.id == job_id))
        ).scalar_one()
        assert job.status == JobStatus.QUEUED


@pytest.mark.asyncio
async def test_post_poster_persists_job_kind_poster(
    client, sessionmaker_fx
) -> None:
    body = _post_body(size="18x24")
    r = await client.post("/api/v1/posters", json=body)
    assert r.status_code == 202

    job_id = r.json()["job_id"]
    async with sessionmaker_fx() as s:
        job = (
            await s.execute(select(JobRecord).where(JobRecord.id == job_id))
        ).scalar_one()
        assert job.kind == JobKind.POSTER
        assert job.input_payload["size"] == "18x24"
        assert job.input_payload["headline"] == "Big Show Tonight"


@pytest.mark.asyncio
async def test_post_poster_enqueues_task_generate_poster(
    client, fake_arq_pool
) -> None:
    body = _post_body(size="18x24")
    r = await client.post("/api/v1/posters", json=body)
    assert r.status_code == 202

    job_id = r.json()["job_id"]
    assert len(fake_arq_pool.calls) == 1
    fn, _, kwargs = fake_arq_pool.calls[0]
    assert fn == "task_generate_poster"
    assert kwargs["job_id"] == job_id
    assert kwargs["payload"]["template"] == "editorial_grand"
    assert kwargs["payload"]["size"] == "18x24"


@pytest.mark.asyncio
async def test_post_poster_accepts_24x36(client) -> None:
    body = _post_body(size="24x36")
    r = await client.post("/api/v1/posters", json=body)
    assert r.status_code == 202, r.text


@pytest.mark.asyncio
async def test_post_poster_accepts_27x40(client) -> None:
    body = _post_body(size="27x40")
    r = await client.post("/api/v1/posters", json=body)
    assert r.status_code == 202, r.text


# ---------------------------------------------------------------------------
# POST validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_poster_rejects_invalid_size_36x48(client) -> None:
    """T-24-07 mitigation: size Literal rejects unknown sizes at 422."""
    body = _post_body(size="36x48")
    r = await client.post("/api/v1/posters", json=body)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_poster_rejects_missing_headline(client) -> None:
    body = _post_body()
    body.pop("headline")
    r = await client.post("/api/v1/posters", json=body)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_poster_rejects_missing_template(client) -> None:
    body = _post_body()
    body.pop("template")
    r = await client.post("/api/v1/posters", json=body)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_poster_rejects_missing_style_preset(client) -> None:
    body = _post_body()
    body.pop("style_preset")
    r = await client.post("/api/v1/posters", json=body)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_poster_rejects_missing_size(client) -> None:
    body = _post_body()
    body.pop("size")
    r = await client.post("/api/v1/posters", json=body)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_poster_rejects_extra_field(client) -> None:
    """extra='forbid' rejects unknown keys at 422."""
    body = _post_body()
    body["rogue_field"] = "x"
    r = await client.post("/api/v1/posters", json=body)
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Compensating-enqueue WR-03 mirror (T-24-12)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_poster_compensating_enqueue_marks_failed(
    fake_arq_pool, sessionmaker_fx, app, monkeypatch
) -> None:
    """Compensating-enqueue: arq raise -> JobRecord FAILED with typed error_detail.

    error_detail must be exactly {"reason": "enqueue_failed", "type": ...}
    with NO str(exc) leak. Mirrors Phase 21-12 WR-03 / Phase 23-04
    compensating-enqueue contract.
    """
    from httpx import ASGITransport, AsyncClient

    async def boom(*_a, **_kw):
        raise RuntimeError("redis://internal:6379/secret")

    monkeypatch.setattr(fake_arq_pool, "enqueue_job", boom)

    body = _post_body()
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/v1/posters", json=body)

    assert r.status_code >= 500, r.text

    async with sessionmaker_fx() as s:
        rows = (
            await s.execute(
                select(JobRecord).where(JobRecord.kind == JobKind.POSTER)
            )
        ).scalars().all()
        assert len(rows) == 1
        row = rows[0]
        assert row.status == JobStatus.FAILED
        assert row.error_detail == {
            "reason": "enqueue_failed",
            "type": "RuntimeError",
        }


@pytest.mark.asyncio
async def test_post_poster_compensating_enqueue_no_secret_leak(
    fake_arq_pool, sessionmaker_fx, app, monkeypatch
) -> None:
    """Defense-in-depth: the original exception message must NOT appear in
    error_detail under any key — no Redis URI, no stack frames."""
    from httpx import ASGITransport, AsyncClient

    secret = "redis://internal:6379/secret"

    async def boom(*_a, **_kw):
        raise RuntimeError(secret)

    monkeypatch.setattr(fake_arq_pool, "enqueue_job", boom)

    body = _post_body()
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        await c.post("/api/v1/posters", json=body)

    async with sessionmaker_fx() as s:
        rows = (
            await s.execute(
                select(JobRecord).where(JobRecord.kind == JobKind.POSTER)
            )
        ).scalars().all()
        assert len(rows) == 1
        row = rows[0]
        # The secret string must NOT appear anywhere in error_detail
        # (no message field, no stack, no str(exc)).
        assert secret not in str(row.error_detail)
        assert "internal" not in str(row.error_detail)


# ---------------------------------------------------------------------------
# Router registration smoke
# ---------------------------------------------------------------------------


def test_router_registered_in_routers_barrel() -> None:
    from flyer_generator.api.routes import ROUTERS, posters

    assert posters.router in ROUTERS


# ---------------------------------------------------------------------------
# Defense-in-depth grep guard: route file body has zero "str(exc)" substrings
# ---------------------------------------------------------------------------


def test_str_exc_not_in_route_file_body() -> None:
    """T-24-12 strict greppable guard: no `str(exc)` in posters route body.

    The compensating-enqueue path uses {'reason', 'type'} only — never
    stringifies the exception (which can leak Redis URIs / stack frames
    into the JSON column).
    """
    body = Path("flyer_generator/api/routes/posters.py").read_text()
    assert "str(exc)" not in body, (
        "posters route file body must NOT contain `str(exc)` — "
        "T-24-12 compensating-enqueue contract"
    )
