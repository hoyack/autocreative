"""Flyer route tests (API-06)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from flyer_generator.api.models import JobKind, JobRecord, JobStatus


def _valid_event(**overrides) -> dict:
    data = {
        "title": "Test Event",
        "date": "2026-05-01",
        "time": "7pm",
        "location_name": "Hall",
        "location_address": "1 Main St",
        "fees": "free",
        "org": "Club",
        "url": None,
        "style_concept": "summer party vibes",
        "style_preset": "photorealistic",
        "color_accent": "#F59E0B",
    }
    data.update(overrides)
    return data


@pytest.mark.asyncio
async def test_post_flyer_returns_202(client, fake_arq_pool, sessionmaker_fx) -> None:
    body = {
        "event": _valid_event(),
        "template": "editorial_classic",
        "preset": "photorealistic",
    }
    r = await client.post("/api/v1/flyers", json=body)
    assert r.status_code == 202, r.text

    job_id = r.json()["job_id"]
    assert len(job_id) == 26

    # arq received one enqueue
    assert len(fake_arq_pool.calls) == 1
    func_name, _, kwargs = fake_arq_pool.calls[0]
    assert func_name == "task_generate_flyer"
    assert kwargs["job_id"] == job_id
    assert kwargs["payload"]["preset"] == "photorealistic"
    assert kwargs["payload"]["template"] == "editorial_classic"
    assert kwargs["payload"]["event"]["title"] == "Test Event"

    # JobRecord committed with status=queued
    async with sessionmaker_fx() as s:
        job = (
            await s.execute(select(JobRecord).where(JobRecord.id == job_id))
        ).scalar_one()
        assert job.status == JobStatus.QUEUED
        assert job.kind == JobKind.FLYER
        assert job.input_payload["preset"] == "photorealistic"
        assert job.input_payload["template"] == "editorial_classic"


@pytest.mark.asyncio
async def test_post_flyer_rejects_bad_accent(client) -> None:
    body = {
        "event": _valid_event(),
        "template": "editorial_classic",
        "preset": "photorealistic",
        "accent": "not-a-hex",
    }
    r = await client.post("/api/v1/flyers", json=body)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_flyer_rejects_bad_event_color_accent(client) -> None:
    # color_accent inside FlyerInput must match ^#[0-9A-Fa-f]{6}$
    body = {
        "event": _valid_event(color_accent="orange"),
        "template": "editorial_classic",
        "preset": "photorealistic",
    }
    r = await client.post("/api/v1/flyers", json=body)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_flyer_rejects_missing_event(client) -> None:
    r = await client.post(
        "/api/v1/flyers",
        json={"template": "editorial_classic", "preset": "photorealistic"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_flyer_rejects_missing_template(client) -> None:
    """Phase 22 FT-01: template is required."""
    body = {
        "event": _valid_event(),
        "preset": "photorealistic",
    }
    r = await client.post("/api/v1/flyers", json=body)
    assert r.status_code == 422
    assert "template" in r.text


@pytest.mark.asyncio
async def test_post_flyer_rejects_empty_template(client) -> None:
    """Phase 22 FT-01: template must be non-empty (min_length=1)."""
    body = {
        "event": _valid_event(),
        "template": "",
        "preset": "photorealistic",
    }
    r = await client.post("/api/v1/flyers", json=body)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_flyer_rejects_bad_slug(client) -> None:
    body = {
        "event": _valid_event(),
        "template": "editorial_classic",
        "preset": "photorealistic",
        "brand_kit_slug": "BAD_UPPER",
    }
    r = await client.post("/api/v1/flyers", json=body)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_flyer_carries_brand_kit_slug_into_payload(
    client, fake_arq_pool
) -> None:
    body = {
        "event": _valid_event(),
        "template": "editorial_classic",
        "preset": "photorealistic",
        "brand_kit_slug": "shrubnet",
    }
    r = await client.post("/api/v1/flyers", json=body)
    assert r.status_code == 202

    _, _, kwargs = fake_arq_pool.calls[0]
    assert kwargs["payload"]["brand_kit_slug"] == "shrubnet"
    assert kwargs["payload"]["template"] == "editorial_classic"


@pytest.mark.asyncio
async def test_post_flyer_rejects_extra_fields(client) -> None:
    body = {
        "event": _valid_event(),
        "template": "editorial_classic",
        "preset": "photorealistic",
        "unexpected_field": "should_fail",
    }
    r = await client.post("/api/v1/flyers", json=body)
    assert r.status_code == 422  # extra="forbid" on FlyerCreateRequest


@pytest.mark.asyncio
async def test_post_flyer_max_bg_attempts_bounds(client) -> None:
    # < 1 rejected
    body = {
        "event": _valid_event(),
        "template": "editorial_classic",
        "preset": "ph",
        "max_bg_attempts": 0,
    }
    r = await client.post("/api/v1/flyers", json=body)
    assert r.status_code == 422
    # > 10 rejected
    body = {
        "event": _valid_event(),
        "template": "editorial_classic",
        "preset": "ph",
        "max_bg_attempts": 11,
    }
    r = await client.post("/api/v1/flyers", json=body)
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Phase 22 FT-01 + FT-06 — info-subtype + template wiring through the route
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_flyer_info_subtype_returns_202(
    client, fake_arq_pool
) -> None:
    """Info-subtype event (no date/time/venue/fees) is accepted with template."""
    body = {
        "event": {
            "title": "Public Notice",
            "subtype": "info",
            "description": "Road closure on Main St this weekend.",
            "org": "City Public Works",
            "style_concept": "civic",
            "style_preset": "photorealistic",
        },
        "template": "editorial_classic",
        "preset": "photorealistic",
    }
    r = await client.post("/api/v1/flyers", json=body)
    assert r.status_code == 202, r.text
    _, _, kwargs = fake_arq_pool.calls[0]
    assert kwargs["payload"]["event"]["subtype"] == "info"
    assert kwargs["payload"]["template"] == "editorial_classic"
