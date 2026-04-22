"""Job polling route (API-10).

``GET /api/v1/jobs/{id}`` is the polling target for every async endpoint.
It returns a stable :class:`JobDetail` shape that clients consume in a loop
until ``status`` transitions to ``succeeded`` / ``failed`` / ``cancelled``.

For single-artifact jobs (flyer, brochure, single social post), ``result_ref``
is a string URL path like ``/api/v1/renders/<ulid>/image``.  For campaign
jobs, ``result_ref`` is a list of :class:`ResultLink` entries fused from
``CampaignRecord.posts`` → each ``PostRecord.render``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from flyer_generator.api.db import get_session
from flyer_generator.api.models import (
    CampaignRecord,
    JobKind,
    JobRecord,
    JobStatus,
    PostRecord,
)
from flyer_generator.api.schemas.jobs import JobDetail, ResultLink

router = APIRouter(tags=["jobs"])


@router.get(
    "/jobs/{job_id}",
    response_model=JobDetail,
    summary="Poll a job's status + result reference",
)
async def get_job(
    job_id: str = PathParam(..., min_length=26, max_length=26),
    session: AsyncSession = Depends(get_session),
) -> JobDetail:
    """Return the current status of a job plus a stable result reference.

    - Single-artifact jobs (flyer, single post, brochure): ``result_ref`` is
      a string URL path like ``/api/v1/renders/<ulid>/image``.
    - Campaign jobs: ``result_ref`` is a list of :class:`ResultLink`
      (``platform``, ``url``) fused from ``CampaignRecord.posts`` +
      each ``PostRecord.render``.
    - Not-yet-succeeded jobs: ``result_ref`` is ``None``.
    """
    job = await session.get(JobRecord, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    result_ref: str | list[ResultLink] | None = None

    if job.kind == JobKind.SOCIAL_CAMPAIGN and job.status == JobStatus.SUCCEEDED:
        # Fuse campaign posts + renders -> list of ResultLink.
        # JobRecord.id is reused as CampaignRecord.id by task_generate_campaign
        # (Plan 20-07), so no FK / lookup table is needed.
        campaign = (
            await session.execute(
                select(CampaignRecord)
                .where(CampaignRecord.id == job.id)
                .options(
                    selectinload(CampaignRecord.posts).selectinload(PostRecord.render)
                )
            )
        ).scalar_one_or_none()
        if campaign is not None:
            links: list[ResultLink] = []
            for post in campaign.posts:
                if post.render_id is not None:
                    links.append(
                        ResultLink(
                            platform=post.platform,
                            url=f"/api/v1/renders/{post.render_id}/image",
                        )
                    )
            result_ref = links if links else None
    elif job.result_ref is not None:
        # Single render — expose as URL path (not bare id).
        result_ref = f"/api/v1/renders/{job.result_ref}/image"

    return JobDetail(
        id=job.id,
        kind=job.kind,
        status=job.status,
        started_at=job.started_at,
        completed_at=job.completed_at,
        error_detail=job.error_detail,
        result_ref=result_ref,
        created_at=job.created_at,
    )
