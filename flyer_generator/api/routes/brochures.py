"""Brochure routes (API-07)."""

from __future__ import annotations

import ulid
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from flyer_generator.api.db import get_session
from flyer_generator.api.models import JobKind, JobRecord, JobStatus
from flyer_generator.api.schemas.brochures import BrochureCreateRequest
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
