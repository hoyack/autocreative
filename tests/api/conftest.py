"""Shared fixtures for tests/api/* — in-memory SQLite + ASGI transport + stub arq."""

from __future__ import annotations

from typing import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from flyer_generator.api import build_app
from flyer_generator.api.config import AppSettings
from flyer_generator.api.models import Base


class _FakeArqPool:
    """In-process stub for arq's ArqRedis pool.

    Records every enqueue_job call so tests can assert the right task was
    enqueued with the right arguments. Does NOT execute the task — Plan 20-07
    tests call task functions directly.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    async def enqueue_job(self, function_name: str, *args, **kwargs):
        self.calls.append((function_name, args, kwargs))

        class _FakeJob:
            def __init__(self, job_id: str) -> None:
                self.job_id = job_id

        return _FakeJob(kwargs.get("job_id", "fake_job"))

    async def aclose(self) -> None:
        pass


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    """In-memory SQLite engine shared across coroutines via StaticPool."""
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def sessionmaker_fx(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def fake_arq_pool() -> _FakeArqPool:
    return _FakeArqPool()


@pytest_asyncio.fixture
async def app(engine, sessionmaker_fx, fake_arq_pool):
    """FastAPI app with test-local engine + sessionmaker + fake arq pool.

    NOTE: We do NOT run the real lifespan context manager — ASGITransport does
    not trigger lifespan by default, and we want to inject test doubles.
    Instead we manually set app.state to a test-controlled bundle.
    """
    app = build_app()
    app.state.settings = AppSettings()
    app.state.engine = engine
    app.state.sessionmaker = sessionmaker_fx
    app.state.arq_pool = fake_arq_pool
    yield app


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
