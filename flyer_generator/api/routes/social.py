"""Social routes (API-08 + API-09)."""

from __future__ import annotations

import ulid
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from flyer_generator.api.db import get_session
from flyer_generator.api.models import JobKind, JobRecord, JobStatus
from flyer_generator.api.schemas.jobs import JobCreated
from flyer_generator.api.schemas.social import CampaignCreateRequest, PostCreateRequest

router = APIRouter(tags=["social"])


@router.post(
    "/social/posts",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobCreated,
    summary="Enqueue a single-platform social post generation",
)
async def create_social_post(
    body: PostCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> JobCreated:
    job_id = str(ulid.ULID())
    payload = body.model_dump(mode="json")

    session.add(
        JobRecord(
            id=job_id,
            kind=JobKind.SOCIAL_POST,
            status=JobStatus.QUEUED,
            input_payload=payload,
        )
    )
    await session.commit()

    await request.app.state.arq_pool.enqueue_job(
        "task_generate_post",
        job_id=job_id,
        payload=payload,
    )
    return JobCreated(job_id=job_id)


@router.post(
    "/social/campaigns",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobCreated,
    summary="Enqueue a multi-platform social campaign (shared hero)",
)
async def create_social_campaign(
    body: CampaignCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> JobCreated:
    job_id = str(ulid.ULID())
    payload = body.model_dump(mode="json")

    session.add(
        JobRecord(
            id=job_id,
            kind=JobKind.SOCIAL_CAMPAIGN,
            status=JobStatus.QUEUED,
            input_payload=payload,
        )
    )
    await session.commit()

    await request.app.state.arq_pool.enqueue_job(
        "task_generate_campaign",
        job_id=job_id,
        payload=payload,
    )
    return JobCreated(job_id=job_id)
