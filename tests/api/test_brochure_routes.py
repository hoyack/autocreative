"""Brochure route tests (API-07)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from flyer_generator.api.models import JobKind, JobRecord, JobStatus


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
