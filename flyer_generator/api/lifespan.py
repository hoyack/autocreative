"""FastAPI lifespan — builds engine + arq pool per uvicorn worker process."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI

from flyer_generator.api.config import AppSettings
from flyer_generator.api.db import build_engine, build_sessionmaker


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build engine + sessionmaker + arq Redis pool; stash on app.state."""
    settings = AppSettings()
    engine = build_engine(settings)
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = build_sessionmaker(engine)
    app.state.arq_pool = await create_pool(
        RedisSettings.from_dsn(settings.redis_url)
    )
    try:
        yield
    finally:
        await app.state.arq_pool.aclose()
        await engine.dispose()
