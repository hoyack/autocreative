"""Shared pytest fixtures for the Phase 20 API test suite."""

from __future__ import annotations

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from flyer_generator.api.models import Base


@pytest_asyncio.fixture
async def sessionmaker_fx():
    """An in-memory SQLite async sessionmaker.

    Uses :class:`StaticPool` + ``check_same_thread=False`` so multiple
    coroutine calls share the same underlying connection (required for
    ``:memory:`` — each new connection is a fresh empty DB).
    ``expire_on_commit=False`` mirrors the production setting so objects
    remain usable after commit.
    """
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(eng, expire_on_commit=False)
    try:
        yield sm
    finally:
        await eng.dispose()
