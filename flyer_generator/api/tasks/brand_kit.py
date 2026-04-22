"""arq task wrapping :func:`fetch_brand_kit`. Writes :class:`BrandKitRecord` on success."""

from __future__ import annotations

from pathlib import Path

import structlog

from flyer_generator.api.models import BrandKitRecord
from flyer_generator.api.tasks._state import mark_failed, mark_running, mark_succeeded
from flyer_generator.brand_kit import fetch_brand_kit

logger = structlog.get_logger()


async def task_fetch_brand_kit(ctx: dict, *, job_id: str, payload: dict) -> str | None:
    """Scrape a brand kit from a URL.

    ``payload`` expects ``{"url": str, "slug": str}``.
    Returns ``None`` — brand kits aren't stored as ``RenderRecord`` rows.
    The downstream polling client reaches the kit by slug via
    ``GET /api/v1/brand-kits/{slug}``.
    """
    sessionmaker = ctx["sessionmaker"]
    settings = ctx["settings"]
    http_client = ctx["http_client"]

    log = logger.bind(job_id=job_id, kind="brand_kit")
    log.info("task_start")
    await mark_running(sessionmaker, job_id)

    try:
        url = payload["url"]
        slug = payload["slug"]

        kit = await fetch_brand_kit(
            url=url,
            slug=slug,
            http_client=http_client,
            base_dir=Path(settings.brand_kits_dir),
        )

        async with sessionmaker() as s:
            # Upsert: overwrite if slug already exists (re-scrape replaces metadata).
            await s.merge(
                BrandKitRecord(
                    slug=slug,
                    source_url=str(url),
                    name=kit.name,
                    scraped_at=kit.fetched_at,
                    payload=kit.model_dump(mode="json"),
                )
            )
            await s.commit()

        await mark_succeeded(sessionmaker, job_id, result_ref=None)
        log.info("task_succeeded", slug=slug)
        return None

    except Exception as exc:
        log.exception("task_failed")
        await mark_failed(sessionmaker, job_id, exc)
        raise  # arq sees the exception, job_timeout / max_tries=1 prevents retry
