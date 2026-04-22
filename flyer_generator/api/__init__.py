"""Phase 20 HTTP API — wraps existing generators.

Running:
    uv run uvicorn flyer_generator.api:app --reload

The module-level ``app`` is safe for uvicorn ``--workers N`` because the
engine and arq pool are built in :func:`lifespan` (per-process), not here.
"""

from __future__ import annotations

from fastapi import FastAPI

from flyer_generator.api.config import AppSettings
from flyer_generator.api.errors import register_exception_handlers
from flyer_generator.api.lifespan import lifespan
from flyer_generator.api.middleware import install_middleware
from flyer_generator.api.routes import ROUTERS


def build_app() -> FastAPI:
    """FastAPI app factory. Call once at import time; lifespan does per-process setup."""
    settings = AppSettings()
    app = FastAPI(
        title="flyer-generator API",
        version="0.1.0",
        description=(
            "Phase 20 — async HTTP surface wrapping the flyer / brochure / "
            "brand_kit / social generators. Single-user v1 (no auth)."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    install_middleware(app, settings)
    register_exception_handlers(app)
    for router in ROUTERS:
        app.include_router(router, prefix="/api/v1")

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict[str, str]:
        """Liveness check — does NOT touch the DB or Redis."""
        return {"status": "ok"}

    return app


app = build_app()

__all__ = ["AppSettings", "app", "build_app"]
