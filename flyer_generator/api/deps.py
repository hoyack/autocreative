"""FastAPI dependency factories (arq pool, settings)."""

from __future__ import annotations

from fastapi import Request

from flyer_generator.api.config import AppSettings


def get_settings(request: Request) -> AppSettings:
    """Return the AppSettings instance stashed on app.state by lifespan."""
    return request.app.state.settings


def get_arq_pool(request: Request):
    """Return the arq ArqRedis pool stashed on app.state by lifespan."""
    return request.app.state.arq_pool
