"""Social route tests (API-08 + API-09)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from flyer_generator.api.models import JobKind, JobRecord, JobStatus


# ---------- POST /social/posts ----------


@pytest.mark.asyncio
async def test_post_social_post_returns_202(client, fake_arq_pool, sessionmaker_fx) -> None:
    body = {
        "brand_kit_slug": "shrubnet",
        "platform": "linkedin",
        "intent": "announcement",
        "topic": "New product launch",
    }
    r = await client.post("/api/v1/social/posts", json=body)
    assert r.status_code == 202, r.text

    job_id = r.json()["job_id"]
    assert len(fake_arq_pool.calls) == 1
    fn, _, kwargs = fake_arq_pool.calls[0]
    assert fn == "task_generate_post"
    assert kwargs["payload"]["platform"] == "linkedin"
    assert kwargs["payload"]["topic"] == "New product launch"

    async with sessionmaker_fx() as s:
        job = (await s.execute(select(JobRecord).where(JobRecord.id == job_id))).scalar_one()
        assert job.kind == JobKind.SOCIAL_POST


@pytest.mark.asyncio
async def test_post_social_post_rejects_unknown_platform(client) -> None:
    body = {
        "brand_kit_slug": "shrubnet",
        "platform": "tiktok",  # not a Platform Literal
        "intent": "announcement",
        "topic": "x",
    }
    r = await client.post("/api/v1/social/posts", json=body)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_social_post_rejects_unknown_intent(client) -> None:
    body = {
        "brand_kit_slug": "shrubnet",
        "platform": "linkedin",
        "intent": "rant",  # not an Intent Literal
        "topic": "x",
    }
    r = await client.post("/api/v1/social/posts", json=body)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_social_post_rejects_bad_slug(client) -> None:
    body = {
        "brand_kit_slug": "BAD_SLUG",
        "platform": "linkedin",
        "intent": "announcement",
        "topic": "x",
    }
    r = await client.post("/api/v1/social/posts", json=body)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_social_post_rejects_empty_topic(client) -> None:
    body = {
        "brand_kit_slug": "shrubnet",
        "platform": "linkedin",
        "intent": "announcement",
        "topic": "",
    }
    r = await client.post("/api/v1/social/posts", json=body)
    assert r.status_code == 422


# ---------- POST /social/campaigns ----------


@pytest.mark.asyncio
async def test_post_campaign_returns_202(client, fake_arq_pool, sessionmaker_fx) -> None:
    body = {
        "brand_kit_slug": "shrubnet",
        "platforms": ["linkedin", "twitter", "instagram"],
        "intent": "announcement",
        "topic": "Product launch",
    }
    r = await client.post("/api/v1/social/campaigns", json=body)
    assert r.status_code == 202, r.text

    job_id = r.json()["job_id"]
    assert len(fake_arq_pool.calls) == 1
    fn, _, kwargs = fake_arq_pool.calls[0]
    assert fn == "task_generate_campaign"
    assert kwargs["payload"]["platforms"] == ["linkedin", "twitter", "instagram"]

    async with sessionmaker_fx() as s:
        job = (await s.execute(select(JobRecord).where(JobRecord.id == job_id))).scalar_one()
        assert job.kind == JobKind.SOCIAL_CAMPAIGN


@pytest.mark.asyncio
async def test_post_campaign_rejects_empty_platforms(client) -> None:
    body = {
        "brand_kit_slug": "shrubnet",
        "platforms": [],
        "intent": "announcement",
        "topic": "x",
    }
    r = await client.post("/api/v1/social/campaigns", json=body)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_campaign_rejects_too_many_platforms(client) -> None:
    body = {
        "brand_kit_slug": "shrubnet",
        "platforms": ["linkedin"] * 11,  # exceeds max_length=10
        "intent": "announcement",
        "topic": "x",
    }
    r = await client.post("/api/v1/social/campaigns", json=body)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_campaign_rejects_unknown_platform_in_list(client) -> None:
    body = {
        "brand_kit_slug": "shrubnet",
        "platforms": ["linkedin", "tiktok"],
        "intent": "announcement",
        "topic": "x",
    }
    r = await client.post("/api/v1/social/campaigns", json=body)
    assert r.status_code == 422
