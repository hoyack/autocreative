"""HTTP permutation coverage for POST /api/v1/posters (PO-01 + PO-04).

Exercises all 9 (template x size) permutations + 3 invalid-size rejection
cases.

Two test layers:

    1. POST /api/v1/posters happy — 9 cases (3 templates x 3 sizes) — each
       asserts:
         - 202 + JobCreated{job_id} with 26-char ULID
         - JobRecord persisted with kind=POSTER, status=QUEUED, and
           input_payload reflecting the requested template + size
         - fake_arq_pool captured exactly one enqueue with task name
           ``"task_generate_poster"`` and matching payload[template] +
           payload[size]

    2. POST /api/v1/posters invalid-size rejections — 3 cases ('36x48',
       '12x18', '') — all return 422 (Pydantic Literal enforcement,
       T-24-07).

Reuses the conftest fixtures established in tests/api/conftest.py
(``client``, ``fake_arq_pool``, ``sessionmaker_fx``) — same fixtures
the postcard permutation suite uses (Phase 23-06).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from flyer_generator.api.models import JobKind, JobRecord, JobStatus

_TEMPLATES = ["editorial_grand", "bold_announcement", "cinematic_onesheet"]
_SIZES = ["18x24", "24x36", "27x40"]
_INVALID_SIZES = ["36x48", "12x18", ""]


def _permutations() -> list[tuple[str, str]]:
    return [(t, s) for t in _TEMPLATES for s in _SIZES]


def _post_body(template: str, size: str) -> dict:
    return {
        "headline": "Phase 24 Test",
        "subheading": "Permutation coverage",
        "cta_text": "Visit example.com",
        "image_hint": "bold poster, festival art",
        "brand_kit_slug": None,
        "style_preset": "photorealistic",
        "template": template,
        "size": size,
    }


# ---------------------------------------------------------------------------
# POST /api/v1/posters — 9 happy permutations (3 templates x 3 sizes)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "template,size",
    _permutations(),
    ids=[f"{t}-{s}" for t, s in _permutations()],
)
async def test_post_poster_permutation_returns_202(
    client,
    fake_arq_pool,
    sessionmaker_fx,
    template: str,
    size: str,
) -> None:
    """All 9 (template x size) POSTs return 202 + correct enqueue + JobRecord."""
    body = _post_body(template, size)
    response = await client.post("/api/v1/posters", json=body)
    assert response.status_code == 202, response.text

    job_id = response.json()["job_id"]
    assert len(job_id) == 26  # ULID

    # JobRecord shape: kind=POSTER + status=QUEUED + input_payload reflects
    # the requested template + size.
    async with sessionmaker_fx() as s:
        row = (
            await s.execute(select(JobRecord).where(JobRecord.id == job_id))
        ).scalar_one()
        assert row.kind == JobKind.POSTER
        assert row.status == JobStatus.QUEUED
        assert row.input_payload["template"] == template
        assert row.input_payload["size"] == size

    # arq pool: exactly one enqueue with task_generate_poster + matching payload.
    assert len(fake_arq_pool.calls) == 1
    fn, _args, kwargs = fake_arq_pool.calls[0]
    assert fn == "task_generate_poster"
    assert kwargs["job_id"] == job_id
    assert kwargs["payload"]["template"] == template
    assert kwargs["payload"]["size"] == size


# ---------------------------------------------------------------------------
# POST /api/v1/posters — 3 invalid-size rejections (T-24-07 mitigation)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "invalid_size",
    _INVALID_SIZES,
    ids=[f"size={v!r}" for v in _INVALID_SIZES],
)
async def test_post_poster_rejects_invalid_size(
    client, invalid_size: str
) -> None:
    """3 invalid-size cases return 422 (Pydantic Literal enforcement).

    T-24-07 mitigation: ``size: Literal['18x24','24x36','27x40']`` rejects
    anything else at the schema layer — the request never reaches the
    worker (where _size_to_canvas_dimensions is the defense-in-depth gate).
    """
    body = {
        "headline": "Phase 24 Test",
        "style_preset": "photorealistic",
        "template": "editorial_grand",
        "size": invalid_size,
    }
    response = await client.post("/api/v1/posters", json=body)
    assert response.status_code == 422, response.text
