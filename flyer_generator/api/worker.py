"""arq worker entrypoint: ``uv run arq flyer_generator.api.worker.WorkerSettings``.

Worker is a SEPARATE OS process from uvicorn — builds its own engine +
sessionmaker + httpx.AsyncClient in ``on_startup(ctx)`` (RESEARCH.md Pitfall
5: worker can't access ``app.state``).
"""

from __future__ import annotations

import httpx
import structlog
from arq.connections import RedisSettings

from flyer_generator.api.config import AppSettings
from flyer_generator.api.db import build_engine, build_sessionmaker
from flyer_generator.api.tasks import ALL_TASKS

logger = structlog.get_logger()


async def on_startup(ctx: dict) -> None:
    """Build per-worker engine + sessionmaker + shared httpx client."""
    settings = AppSettings()
    ctx["settings"] = settings
    ctx["engine"] = build_engine(settings)
    ctx["sessionmaker"] = build_sessionmaker(ctx["engine"])
    ctx["http_client"] = httpx.AsyncClient(follow_redirects=True, timeout=300.0)
    logger.info(
        "arq_worker_started",
        database=settings.database_url.split("://")[0],
    )


async def on_shutdown(ctx: dict) -> None:
    """Close the shared client + dispose the engine."""
    client: httpx.AsyncClient | None = ctx.get("http_client")
    if client is not None:
        await client.aclose()
    engine = ctx.get("engine")
    if engine is not None:
        await engine.dispose()
    logger.info("arq_worker_stopped")


class WorkerSettings:
    """arq worker configuration.

    ``max_tries=1`` is deliberate (RESEARCH.md Pitfall 4): ``llm_retry.py``
    already owns per-call retry + model-chain fallback. Re-running the whole
    task on failure would double-charge ComfyCloud.
    """

    functions = ALL_TASKS
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = RedisSettings.from_dsn(str(AppSettings().redis_url))
    max_jobs = 4
    job_timeout = 600  # 10 min — deep ComfyCloud queue headroom
    keep_result = 3600  # hold results in Redis 1 h for polling grace
    max_tries = 1  # Pitfall 4 — do NOT retry on exception
