"""Smoke tests for Phase 20 async SQLAlchemy plumbing."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from flyer_generator.api.config import AppSettings
from flyer_generator.api.db import build_engine, build_sessionmaker
from flyer_generator.api.models import Base, JobKind, JobRecord, JobStatus


@pytest_asyncio.fixture
async def in_memory_sessionmaker():
    """In-memory SQLite engine shared across coroutines via StaticPool."""
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(eng, expire_on_commit=False)
    yield sm
    await eng.dispose()


@pytest.mark.asyncio
async def test_build_engine_is_async_and_sqlite_uses_nullpool() -> None:
    settings = AppSettings()
    # Force the SQLite branch regardless of environment:
    settings.database_url = "sqlite+aiosqlite:///:memory:"
    engine = build_engine(settings)
    assert type(engine.pool).__name__ == "NullPool"
    await engine.dispose()


@pytest.mark.asyncio
async def test_sessionmaker_round_trips_jobrecord(in_memory_sessionmaker) -> None:
    async with in_memory_sessionmaker() as session:
        job = JobRecord(
            id="01HTESTDBSESSION00000000001",
            kind=JobKind.FLYER,
            status=JobStatus.QUEUED,
            input_payload={"smoke": True},
        )
        session.add(job)
        await session.commit()

    async with in_memory_sessionmaker() as session:
        result = await session.execute(
            select(JobRecord).where(JobRecord.id == "01HTESTDBSESSION00000000001")
        )
        row = result.scalar_one()
        assert row.kind == JobKind.FLYER
        assert row.status == JobStatus.QUEUED
        assert row.input_payload == {"smoke": True}


@pytest.mark.asyncio
async def test_session_rollback_on_error(in_memory_sessionmaker) -> None:
    # Insert, then attempt duplicate PK — expect IntegrityError, row should
    # not persist twice.
    async with in_memory_sessionmaker() as session:
        session.add(
            JobRecord(
                id="01HDUPTEST00000000000000001",
                kind=JobKind.FLYER,
                input_payload={},
            )
        )
        await session.commit()

    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        async with in_memory_sessionmaker() as session:
            session.add(
                JobRecord(
                    id="01HDUPTEST00000000000000001",
                    kind=JobKind.FLYER,
                    input_payload={},
                )
            )
            await session.commit()


