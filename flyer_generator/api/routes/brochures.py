"""Brochure routes (API-07 + Plan 21-07 Task 1)."""

from __future__ import annotations

import ulid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi import Path as PathParam
from sqlalchemy.ext.asyncio import AsyncSession

from flyer_generator.api.db import get_session
from flyer_generator.api.models import BrochureRecord, JobKind, JobRecord, JobStatus
from flyer_generator.api.schemas.brochures import BrochureCreateRequest, BrochureDetail
from flyer_generator.api.schemas.jobs import JobCreated

router = APIRouter(tags=["brochures"])


@router.post(
    "/brochures",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobCreated,
    summary="Enqueue a brochure generation (3 artifacts: front PNG + back PNG + PDF)",
)
async def create_brochure(
    body: BrochureCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> JobCreated:
    job_id = str(ulid.ULID())
    payload = body.model_dump(mode="json")

    session.add(
        JobRecord(
            id=job_id,
            kind=JobKind.BROCHURE,
            status=JobStatus.QUEUED,
            input_payload=payload,
        )
    )
    await session.commit()

    await request.app.state.arq_pool.enqueue_job(
        "task_generate_brochure",
        job_id=job_id,
        payload=payload,
    )
    return JobCreated(job_id=job_id)


@router.get(
    "/brochures/{brochure_id}",
    response_model=BrochureDetail,
    summary="Brochure detail (front PNG + back PNG + print PDF)",
)
async def get_brochure_detail(
    brochure_id: str = PathParam(..., min_length=26, max_length=26),
    session: AsyncSession = Depends(get_session),
) -> BrochureDetail:
    """Return the 3 render URLs for a brochure.

    Per Plan 21-07 Task 1 parallel-id pattern: ``brochure_id`` == ``job_id``,
    so the FE can navigate from /jobs/{id} (or directly from a brochure-task
    ``result_ref``) to this route without an extra lookup.

    Returns 404 when no ``BrochureRecord`` with the given id exists. No
    distinction is made between "no such id" and "id is malformed beyond
    the 26-char PathParam guard" — both surface as the same 404 to avoid
    leaking DB presence signals (T-16 disposition: trust the ULID guard,
    don't leak existence).
    """
    record = await session.get(BrochureRecord, brochure_id)
    if record is None:
        raise HTTPException(status_code=404, detail="brochure not found")
    return BrochureDetail(
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
