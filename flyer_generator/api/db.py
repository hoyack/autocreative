"""SQLAlchemy 2.0 async engine + sessionmaker + FastAPI dependency.

Builds the engine from :class:`AppSettings.database_url`.  The FastAPI
``lifespan`` (Plan 20-06) calls :func:`build_engine` once per process and
stashes the :class:`async_sessionmaker` on ``app.state.sessionmaker``.  The
:func:`get_session` dependency reads that sessionmaker from
``request.app.state`` and yields a session that commits on successful exit
and rolls back on exception.
"""

from __future__ import annotations

from typing import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from flyer_generator.api.config import AppSettings


def build_engine(settings: AppSettings) -> AsyncEngine:
    """Build an AsyncEngine honoring SQLite and Postgres idioms.

    - SQLite: ``NullPool`` + ``check_same_thread=False`` (Pitfall 1, 2).
    - Postgres: default pooling, no connect_args override.
    """
    kwargs: dict = {"echo": False, "future": True}
    if settings.database_url.startswith("sqlite"):
        from sqlalchemy.pool import NullPool

        kwargs["poolclass"] = NullPool
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_async_engine(settings.database_url, **kwargs)


def build_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build an async_sessionmaker with ``expire_on_commit=False`` (Pitfall 3)."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency — yield an AsyncSession from ``app.state.sessionmaker``.

    Commits on successful exit, rolls back on exception, always closes.
    Route handlers should NOT call ``await session.commit()`` manually.
    """
    sessionmaker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with sessionmaker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()
