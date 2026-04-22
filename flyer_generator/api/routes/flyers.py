"""Flyer routes (API-06)."""

from __future__ import annotations

import ulid
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from flyer_generator.api.db import get_session
from flyer_generator.api.models import JobKind, JobRecord, JobStatus
from flyer_generator.api.schemas.flyers import FlyerCreateRequest
from flyer_generator.api.schemas.jobs import JobCreated

router = APIRouter(tags=["flyers"])


@router.post(
    "/flyers",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobCreated,
    summary="Enqueue a flyer generation",
)
async def create_flyer(
    body: FlyerCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> JobCreated:
    """Enqueue a flyer generation.

    Commit order is load-bearing:
      1. INSERT JobRecord, COMMIT.
      2. Then ``arq_pool.enqueue_job(...)`` — if we enqueued first, the worker
         could pick the job up before our row is visible and ``mark_running``
         would fail with a FK-style "no such job" error.
    """
    job_id = str(ulid.ULID())
    payload = body.model_dump(mode="json")

    session.add(
        JobRecord(
            id=job_id,
            kind=JobKind.FLYER,
            status=JobStatus.QUEUED,
            input_payload=payload,
        )
    )
    await session.commit()

    await request.app.state.arq_pool.enqueue_job(
        "task_generate_flyer",
        job_id=job_id,
        payload=payload,
    )
    return JobCreated(job_id=job_id)
