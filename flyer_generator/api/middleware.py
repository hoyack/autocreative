"""CORS + correlation-id middleware wiring."""

from __future__ import annotations

from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from flyer_generator.api.config import AppSettings


def install_middleware(app: FastAPI, settings: AppSettings) -> None:
    """Wire request-correlation-id + CORS. Order matters: correlation-id FIRST."""
    # CorrelationIdMiddleware echoes/generates X-Request-ID and populates
    # the `asgi_correlation_id.correlation_id` contextvar. structlog's
    # merge_contextvars processor surfaces it as trace_id in every log line.
    #
    # validator=None accepts arbitrary client-supplied IDs (ULIDs, opaque
    # trace IDs from an upstream gateway, etc.). The library's default
    # validator only accepts UUID4 strings and silently overwrites non-UUID
    # IDs, which breaks the must_haves truth "X-Request-ID header is echoed
    # on every response". Phase 20 uses ULIDs for job_id and downstream
    # observability tooling should be able to thread its own trace IDs.
    app.add_middleware(
        CorrelationIdMiddleware, header_name="X-Request-ID", validator=None
    )

    # CORS — origins from FLYER_CORS_ORIGINS env (default
    # ["http://localhost:5173"], never "*" per Pitfall 7 when credentials=True).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
