"""Shared state-transition helpers for every arq task.

Every task commits three hops to JobRecord:
 1. queued -> running   (enter)
 2. running -> succeeded (exit OK, with result_ref)
 3. running -> failed   (exit error, with error_detail)

Each hop uses its own ``async with sessionmaker()`` block so the commit is
durable even if the worker process is SIGTERM'd between hops.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import update

from flyer_generator.api.models import JobRecord, JobStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def mark_running(sessionmaker, job_id: str) -> None:
    """Transition ``queued -> running`` and stamp ``started_at``."""
    async with sessionmaker() as s:
        await s.execute(
            update(JobRecord)
            .where(JobRecord.id == job_id)
            .values(status=JobStatus.RUNNING, started_at=_now())
        )
        await s.commit()


async def mark_succeeded(sessionmaker, job_id: str, *, result_ref: Any | None) -> None:
    """Transition ``running -> succeeded``.

    ``result_ref`` is either a string (single render id) or ``None`` (campaigns
    leave it NULL; the route fuses per-post render URLs from
    ``CampaignRecord.posts`` at GET time).
    """
    async with sessionmaker() as s:
        await s.execute(
            update(JobRecord)
            .where(JobRecord.id == job_id)
            .values(
                status=JobStatus.SUCCEEDED,
                completed_at=_now(),
                result_ref=result_ref if isinstance(result_ref, str) else None,
            )
        )
        await s.commit()


async def mark_failed(sessionmaker, job_id: str, exc: Exception) -> None:
    """Transition ``running -> failed``.

    Writes only ``{type, message}`` — never the raw ``exc.context`` bag (T-5
    mitigation: ``context`` kwargs may contain SecretStr values, SSRF reasons,
    or private file paths which must not reach the DB column).
    """
    async with sessionmaker() as s:
        await s.execute(
            update(JobRecord)
            .where(JobRecord.id == job_id)
            .values(
                status=JobStatus.FAILED,
                completed_at=_now(),
                error_detail={
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            )
        )
        await s.commit()
