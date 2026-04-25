"""Postcard routes (Phase 23-04 PC-01 + PC-02).

POST /api/v1/postcards enqueues a job that produces 3 artifacts (front
PNG + back PNG + print PDF). Compensating-enqueue try/except mirrors
Phase 21-12: ``error_detail`` is exactly ``{"reason", "type"}`` —
NEVER stringifies the exception (which can leak Redis URIs / stack
frames into the JSON column).

GET /api/v1/postcards/{postcard_id} returns :class:`PostcardDetail`
with all 3 render URLs. The parallel-id pattern (PC-02) means
``postcard_id == job_id``, so the FE can navigate ``/jobs/{id}``
-> ``/postcards/{id}`` without an extra lookup.
"""

from __future__ import annotations

import ulid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi import Path as PathParam
from sqlalchemy.ext.asyncio import AsyncSession

from flyer_generator.api.db import get_session
from flyer_generator.api.models import (
    JobKind,
    JobRecord,
    JobStatus,
    PostcardRecord,
)
from flyer_generator.api.schemas.jobs import JobCreated
from flyer_generator.api.schemas.postcards import (
    PostcardCreateRequest,
    PostcardDetail,
)

router = APIRouter(tags=["postcards"])


@router.post(
    "/postcards",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobCreated,
    summary=(
        "Enqueue a postcard generation "
        "(3 artifacts: front PNG + back PNG + PDF)"
    ),
)
async def create_postcard(
    body: PostcardCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> JobCreated:
    job_id = str(ulid.ULID())
    payload = body.model_dump(mode="json")

    session.add(
        JobRecord(
            id=job_id,
            kind=JobKind.POSTCARD,
            status=JobStatus.QUEUED,
            input_payload=payload,
        )
    )
    await session.commit()

    # Compensating-enqueue: if arq can't accept the job (Redis down,
    # pool misconfigured, etc.), the QUEUED row above has no worker to
    # advance it — flip it to FAILED before the 5xx propagates so the
    # dashboard reflects reality instead of showing a ghost. The
    # error_detail is deliberately minimal — exactly {"reason", "type"}
    # — to avoid leaking Redis connection strings or stack frames into
    # the DB column. NEVER stringify the exception.
    try:
        await request.app.state.arq_pool.enqueue_job(
            "task_generate_postcard",
            job_id=job_id,
            payload=payload,
        )
    except Exception as exc:
        # Use a fresh session: the request-scoped ``session`` may be in a
        # dirty state depending on the failure path.
        async with request.app.state.sessionmaker() as s2:
            row = await s2.get(JobRecord, job_id)
            if row is not None:
                row.status = JobStatus.FAILED
                row.error_detail = {
                    "reason": "enqueue_failed",
                    "type": type(exc).__name__,
                }
                await s2.commit()
        raise

    return JobCreated(job_id=job_id)


@router.get(
    "/postcards/{postcard_id}",
    response_model=PostcardDetail,
    summary="Postcard detail (front PNG + back PNG + print PDF)",
)
async def get_postcard_detail(
    postcard_id: str = PathParam(..., min_length=26, max_length=26),
    session: AsyncSession = Depends(get_session),
) -> PostcardDetail:
    """Return the 3 render URLs for a postcard.

    Per PC-02 parallel-id: ``postcard_id == job_id``, so the FE can
    navigate from /jobs/{id} (or directly from a postcard-task
    ``result_ref``) to this route without an extra lookup.

    Returns 404 when no ``PostcardRecord`` with the given id exists. No
    distinction is made between "no such id" and "id is malformed beyond
    the 26-char PathParam guard" — both surface as the same 404 (T-16
    disposition: trust the ULID guard, do not leak DB-presence signals).
    """
    record = await session.get(PostcardRecord, postcard_id)
    if record is None:
        raise HTTPException(status_code=404, detail="postcard not found")
    return PostcardDetail(
        id=record.id,
        template=record.template,
        brand_kit_slug=record.brand_kit_slug,
        front_render_url=(
            f"/api/v1/renders/{record.render_front_id}/image"
            if record.render_front_id
            else None
        ),
        back_render_url=(
            f"/api/v1/renders/{record.render_back_id}/image"
            if record.render_back_id
            else None
        ),
        pdf_render_url=(
            f"/api/v1/renders/{record.render_pdf_id}/image"
            if record.render_pdf_id
            else None
        ),
        created_at=record.created_at,
    )
