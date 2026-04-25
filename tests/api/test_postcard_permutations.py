"""HTTP permutation coverage for POST /api/v1/postcards (PC-01 + PC-03).

Exercises all 4 permutations: 2 templates x {with-address, without-address}.

Two test layers:
    1. POST /api/v1/postcards permutations (4 cases) -- asserts 202 +
       JobCreated, JobRecord shape, and arq enqueue call wiring.
    2. GET /api/v1/postcards/{id} permutations (2 cases per template) --
       asserts the 3-render-URL fuse for a pre-seeded PostcardRecord.

Uses the conftest fixtures already established for the Phase 23-04
route tests (`client`, `sessionmaker_fx`, `fake_arq_pool`, `app`).
"""

from __future__ import annotations

import ulid
from sqlalchemy import select

from flyer_generator.api.models import (
    JobKind,
    JobRecord,
    JobStatus,
    PostcardRecord,
    RenderRecord,
)

_TEMPLATES = ["classic_portrait", "modern_landscape"]
_ADDRESS_FLAGS = [False, True]


def _body(template: str, with_address: bool) -> dict:
    b: dict = {
        "headline": "Save the Date",
        "body": "Body copy goes here.",
        "image_hint": None,
        "brand_kit_slug": None,
        "template": template,
        "address_block": None,
    }
    if with_address:
        b["address_block"] = {
            "recipient_name": "Jane Doe",
            "street": "123 Main St",
            "city_state_zip": "Springfield, IL 62701",
        }
    return b


# ---------------------------------------------------------------------------
# POST /api/v1/postcards -- 4 permutations (2 templates x address-flag)
# ---------------------------------------------------------------------------


import pytest


@pytest.mark.parametrize("template", _TEMPLATES)
@pytest.mark.parametrize("with_address", _ADDRESS_FLAGS)
async def test_post_postcard_permutation_returns_202(
    client,
    sessionmaker_fx,
    fake_arq_pool,
    template: str,
    with_address: bool,
) -> None:
    body = _body(template, with_address)
    response = await client.post("/api/v1/postcards", json=body)
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]
    assert len(job_id) == 26  # ULID

    async with sessionmaker_fx() as s:
        row = (
            await s.execute(select(JobRecord).where(JobRecord.id == job_id))
        ).scalar_one()
        assert row.kind == JobKind.POSTCARD
        assert row.status == JobStatus.QUEUED
        assert row.input_payload["template"] == template
        assert row.input_payload["address_block"] == body["address_block"]

    # arq was called exactly once for this permutation, with the right task name.
    assert len(fake_arq_pool.calls) == 1
    fn, _, kwargs = fake_arq_pool.calls[0]
    assert fn == "task_generate_postcard"
    assert kwargs["job_id"] == job_id
    assert kwargs["payload"]["template"] == template


# ---------------------------------------------------------------------------
# GET /api/v1/postcards/{id} -- 2 permutations (one per template)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("template", _TEMPLATES)
async def test_get_postcard_detail_with_3_renders_returns_3_urls(
    client,
    sessionmaker_fx,
    template: str,
) -> None:
    postcard_id = str(ulid.ULID())
    async with sessionmaker_fx() as s:
        r_front = RenderRecord(kind="postcard_front", file_path="/tmp/fake/front.png")
        r_back = RenderRecord(kind="postcard_back", file_path="/tmp/fake/back.png")
        r_pdf = RenderRecord(kind="postcard_pdf", file_path="/tmp/fake/print.pdf")
        s.add_all([r_front, r_back, r_pdf])
        await s.flush()
        postcard = PostcardRecord(
            id=postcard_id,
            template=template,
            brand_kit_slug=None,
            content_payload={"template": template},
            render_front_id=r_front.id,
            render_back_id=r_back.id,
            render_pdf_id=r_pdf.id,
        )
        s.add(postcard)
        await s.commit()
        front_id, back_id, pdf_id = r_front.id, r_back.id, r_pdf.id

    response = await client.get(f"/api/v1/postcards/{postcard_id}")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["id"] == postcard_id
    assert data["template"] == template
    assert data["front_render_url"] == f"/api/v1/renders/{front_id}/image"
    assert data["back_render_url"] == f"/api/v1/renders/{back_id}/image"
    assert data["pdf_render_url"] == f"/api/v1/renders/{pdf_id}/image"


@pytest.mark.parametrize("template", _TEMPLATES)
async def test_get_postcard_detail_null_renders_returns_null_urls(
    client,
    sessionmaker_fx,
    template: str,
) -> None:
    """Per-template null-render-id coverage: when render_*_id columns are
    NULL the corresponding URLs in the response must also be null. Locks
    in the 3-URL fuse's None-passthrough branch for both shipped templates.
    """
    postcard_id = str(ulid.ULID())
    async with sessionmaker_fx() as s:
        postcard = PostcardRecord(
            id=postcard_id,
            template=template,
            brand_kit_slug=None,
            content_payload={"template": template},
            render_front_id=None,
            render_back_id=None,
            render_pdf_id=None,
        )
        s.add(postcard)
        await s.commit()

    response = await client.get(f"/api/v1/postcards/{postcard_id}")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["front_render_url"] is None
    assert data["back_render_url"] is None
    assert data["pdf_render_url"] is None
