"""Poster routes (Phase 24-04 PO-01).

POST /api/v1/posters enqueues a job that produces a single PNG at
size-derived canvas dimensions (300 DPI portrait). Compensating-enqueue
try/except mirrors Phase 21-12 + Phase 23-04: ``error_detail`` is exactly
``{"reason", "type"}`` — NEVER stringifies the exception (which would leak
Redis URIs / stack frames into the JSON column).

NO GET /api/v1/posters/{id} — single-artifact poster status reads
``result_ref`` directly via the existing ``JobStatusCard`` (CONTEXT.md
locked decision). The render is fetched via the existing
``GET /api/v1/renders/{id}/image`` route.
"""

from __future__ import annotations

import ulid
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from flyer_generator.api.db import get_session
from flyer_generator.api.models import JobKind, JobRecord, JobStatus
from flyer_generator.api.schemas.jobs import JobCreated
from flyer_generator.api.schemas.posters import PosterCreateRequest

router = APIRouter(tags=["posters"])


@router.post(
    "/posters",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobCreated,
    summary="Enqueue a poster generation (single PNG at print canvas dims)",
)
async def create_poster(
    body: PosterCreateRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> JobCreated:
    job_id = str(ulid.ULID())
    payload = body.model_dump(mode="json")

    session.add(
        JobRecord(
            id=job_id,
            kind=JobKind.POSTER,
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
    # the DB column. NEVER stringifies the exception (T-24-12).
    try:
        await request.app.state.arq_pool.enqueue_job(
            "task_generate_poster",
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
