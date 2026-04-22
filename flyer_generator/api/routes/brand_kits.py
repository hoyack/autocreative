"""Brand-kit routes (API-05).

Endpoints:
    POST /api/v1/brand-kits/fetch   -> enqueue task_fetch_brand_kit (202)
    GET  /api/v1/brand-kits          -> paginated list (DB + .brand-kits/ fuse)
    GET  /api/v1/brand-kits/{slug}   -> detail (404 via BrandKitNotFoundError)
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import ulid
from fastapi import APIRouter, Depends, Path as PathParam, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from flyer_generator.api.config import AppSettings
from flyer_generator.api.db import get_session
from flyer_generator.api.deps import get_settings
from flyer_generator.api.models import BrandKitRecord, JobKind, JobRecord, JobStatus
from flyer_generator.api.schemas.brand_kits import (
    BrandKitDetail,
    BrandKitFetchRequest,
    BrandKitSummary,
    PaginatedBrandKits,
)
from flyer_generator.api.schemas.jobs import JobCreated
from flyer_generator.brand_kit import load_brand_kit
from flyer_generator.brand_kit.models import BrandKit

router = APIRouter(tags=["brand-kits"])

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@router.post(
    "/brand-kits/fetch",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobCreated,
    summary="Enqueue a brand-kit scrape from a URL",
)
async def create_brand_kit_fetch(
    body: BrandKitFetchRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> JobCreated:
    """Enqueue a scrape. Body validation (URL + slug regex) happens in the schema.

    SSRF protection is inherited from ``flyer_generator/brand_kit/scraper.py``
    which runs inside ``task_fetch_brand_kit``. This route DOES NOT bypass it —
    it only forwards ``url`` + ``slug``.
    """
    job_id = str(ulid.ULID())
    session.add(
        JobRecord(
            id=job_id,
            kind=JobKind.BRAND_KIT,
            status=JobStatus.QUEUED,
            input_payload={"url": str(body.url), "slug": body.slug},
        )
    )
    # Commit the JobRecord before enqueue so the worker can read it.
    # (get_session also commits on exit, but we need the row visible to the
    # worker the moment enqueue_job returns.)
    await session.commit()

    await request.app.state.arq_pool.enqueue_job(
        "task_fetch_brand_kit",
        job_id=job_id,
        payload={"url": str(body.url), "slug": body.slug},
    )
    return JobCreated(job_id=job_id)


@router.get(
    "/brand-kits",
    response_model=PaginatedBrandKits,
    summary="List brand kits (DB + filesystem fuse)",
)
async def list_brand_kits(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    settings: AppSettings = Depends(get_settings),
) -> PaginatedBrandKits:
    """Return DB rows unioned with filesystem-only kits (lazy fuse — no INSERT).

    RESEARCH.md Open Question Q3 recommendation: synthesize ``BrandKitSummary``
    entries in-memory for slugs present on disk but not yet in the DB. This is
    safe for v1 where at most a few dozen kits exist.  A real "import to DB"
    step is a later phase.
    """
    # 1. DB side — count + page
    total_q = await session.execute(select(func.count()).select_from(BrandKitRecord))
    db_total = total_q.scalar_one()

    rows = (
        (
            await session.execute(
                select(BrandKitRecord)
                .order_by(BrandKitRecord.scraped_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    db_slugs = {r.slug for r in rows}

    items: list[BrandKitSummary] = [
        BrandKitSummary(
            slug=r.slug,
            name=r.name,
            source_url=r.source_url,
            scraped_at=r.scraped_at,
        )
        for r in rows
    ]

    # 2. Filesystem fuse — extend ``items`` (and ``total``) with disk-only
    #    slugs that are NOT already represented in the DB. For v1 this is
    #    best-effort: we don't paginate across the filesystem, we only top
    #    up the current page.
    base_dir = Path(settings.brand_kits_dir)
    fs_only_count = 0
    if base_dir.exists():
        for child in sorted(base_dir.iterdir()):
            if not child.is_dir():
                continue
            slug = child.name
            if not _SLUG_RE.match(slug):
                continue
            if slug in db_slugs:
                continue
            brand_json = child / "brand.json"
            if not brand_json.is_file():
                continue
            try:
                kit = BrandKit.model_validate_json(
                    brand_json.read_text(encoding="utf-8")
                )
            except Exception:
                # Corrupt brand.json — skip silently for list endpoint.
                continue
            fs_only_count += 1
            items.append(
                BrandKitSummary(
                    slug=slug,
                    name=kit.name,
                    source_url=kit.source_url,
                    scraped_at=kit.fetched_at,
                )
            )

    return PaginatedBrandKits(
        items=items,
        total=db_total + fs_only_count,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/brand-kits/{slug}",
    response_model=BrandKitDetail,
    summary="Brand-kit detail (palette + typography + logos + voice)",
)
async def get_brand_kit(
    slug: str = PathParam(..., pattern=r"^[a-z0-9][a-z0-9-]*$", max_length=64),
    session: AsyncSession = Depends(get_session),
    settings: AppSettings = Depends(get_settings),
) -> BrandKitDetail:
    """Load a single brand kit.

    Resolution order:
      1. DB row (fast path — preferred).
      2. Filesystem via ``load_brand_kit(slug, base_dir=...)``.
      3. Missing -> ``load_brand_kit`` raises ``BrandKitNotFoundError``
         which the exception-handler bank maps to HTTP 404.
    """
    # Try DB first.
    row = (
        await session.execute(
            select(BrandKitRecord).where(BrandKitRecord.slug == slug)
        )
    ).scalar_one_or_none()

    if row is not None:
        # Re-materialize the BrandKit payload from the JSON column.
        kit: BrandKit | None = (
            BrandKit.model_validate(row.payload) if row.payload else None
        )
        if kit is None:
            # Degraded row — fall through to filesystem load.
            kit = load_brand_kit(slug, base_dir=Path(settings.brand_kits_dir))
        return BrandKitDetail(
            slug=slug,
            record_created_at=row.created_at,
            brand_kit=kit,
        )

    # DB miss — try filesystem; raises BrandKitNotFoundError on miss.
    kit = load_brand_kit(slug, base_dir=Path(settings.brand_kits_dir))
    # Kit loaded from disk only — no DB row exists yet; synthesize a timestamp.
    return BrandKitDetail(
        slug=slug,
        record_created_at=datetime.now(timezone.utc),
        brand_kit=kit,
    )
