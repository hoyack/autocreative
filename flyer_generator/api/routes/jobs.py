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

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Query
from sqlalchemy import func, select
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
from flyer_generator.api.schemas.jobs import JobDetail, PaginatedJobs, ResultLink

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


# --- GET /api/v1/jobs (list, Plan 21-10 Task 1) -----------------------------
#
# Mirror of ``routes/brand_kits.py::list_brand_kits`` — paginated list with
# limit + offset, plus two optional enum filters (``kind`` + ``status``) that
# map directly onto the existing :data:`JobRecord.kind` / ``status`` indexes.
#
# Per 21-RESEARCH.md Open Question Q1 recommendation (the "cheap path"),
# campaign rows in the list view have ``result_ref=None`` — we deliberately
# skip the per-row ``CampaignRecord.posts`` / ``PostRecord.render`` fuse
# here. Clients that want the full ``list[ResultLink]`` call
# ``GET /api/v1/jobs/{id}`` instead. This keeps list-view queries O(N)
# instead of O(N * posts-per-campaign).


@router.get(
    "/jobs",
    response_model=PaginatedJobs,
    summary="List jobs (newest first; filter by kind / status)",
)
async def list_jobs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    kind: JobKind | None = Query(default=None),
    status: JobStatus | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> PaginatedJobs:
    """Return paginated jobs sorted by ``created_at`` DESC.

    Filters: optional ``kind`` + ``status`` enum constraints. FastAPI coerces
    query strings to the two ``JobKind`` / ``JobStatus`` enums and returns
    422 on any value outside the enum — that's the SQL-smuggling mitigation
    for T-18 in the plan threat model.
    """
    stmt = select(JobRecord).order_by(JobRecord.created_at.desc())
    count_stmt = select(func.count()).select_from(JobRecord)
    if kind is not None:
        stmt = stmt.where(JobRecord.kind == kind)
        count_stmt = count_stmt.where(JobRecord.kind == kind)
    if status is not None:
        stmt = stmt.where(JobRecord.status == status)
        count_stmt = count_stmt.where(JobRecord.status == status)

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (
        (await session.execute(stmt.limit(limit).offset(offset))).scalars().all()
    )

    items: list[JobDetail] = []
    for r in rows:
        # Cheap-path result_ref mapping — see module-level comment above.
        if r.kind == JobKind.SOCIAL_CAMPAIGN:
            # Campaigns: no per-row fuse; clients hit /jobs/{id} for the
            # full ResultLink[].
            row_result_ref: str | list[ResultLink] | None = None
        elif r.result_ref is not None:
            # Single-artifact rows (flyer / brochure / single post): expose
            # the URL path (not the bare render id).
            row_result_ref = f"/api/v1/renders/{r.result_ref}/image"
        else:
            row_result_ref = None

        items.append(
            JobDetail(
                id=r.id,
                kind=r.kind,
                status=r.status,
                started_at=r.started_at,
                completed_at=r.completed_at,
                error_detail=r.error_detail,
                result_ref=row_result_ref,
                created_at=r.created_at,
            )
        )

    return PaginatedJobs(items=items, total=total, limit=limit, offset=offset)
