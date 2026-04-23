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
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path as PathParam,
    Query,
    Request,
    status,
)
from fastapi.responses import FileResponse
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

    # WR-03 (Plan 21-13 Task 2) — compensate on enqueue failure so the
    # JobRecord we just committed does NOT orphan in QUEUED with no worker
    # to advance it. Mirrors the brochure creator's pattern (Plan 21-12
    # Task 2) and the threat model T-21-13-03 / T-21-13-04 dispositions:
    #   - Use a FRESH session via app.state.sessionmaker() because the
    #     request-scoped ``session`` is owned by get_session and may already
    #     be in an inconsistent state after the enqueue raised.
    #   - Write ONLY typed fields into error_detail ({reason, type}) — never
    #     the stringified exception message, which may include Redis URLs or
    #     stack frames (T-5 / T-21-13-04 info disclosure).
    #   - Re-raise so the caller still sees the 5xx via Starlette.
    try:
        await request.app.state.arq_pool.enqueue_job(
            "task_fetch_brand_kit",
            job_id=job_id,
            payload={"url": str(body.url), "slug": body.slug},
        )
    except Exception as exc:
        async with request.app.state.sessionmaker() as s2:
            row = await s2.get(JobRecord, job_id)
            if row is not None:
                row.status = JobStatus.FAILED
                row.error_detail = {
                    "reason": "enqueue_failed",
                    "type": type(exc).__name__,
                }
                await s2.commit()
        raise

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
    """Return DB rows unioned with filesystem-only kits.

    WR-02 fix (Plan 21-13 Task 1): the dedup key set is the FULL set of DB
    slugs (cheap single indexed-column SELECT), not just the current page's
    slice. This makes the ``total`` count page-invariant and prevents a slug
    that appears in the DB on page N from being misreported as "FS-only" on
    page N-1 (which previously produced both a duplicate row across pages and
    an inflated ``total``).

    IN-03 companion fix: the merged list (DB rows + FS-only summaries) is
    sorted by ``scraped_at`` descending BEFORE slicing, so FS-only entries no
    longer always tail the page regardless of recency.

    Scale note: v1 datasets are expected to be at most a few dozen kits
    (21-CONTEXT.md — single-user private instance), so full DB + FS
    enumeration on every list call is acceptable. Revisit if a future phase
    sees >1000 kits.
    """
    # 1. Full DB slug set for dedup + full DB count (both cheap — single
    #    indexed column scan). These are page-invariant and MUST be computed
    #    before the FS enumeration so the dedup is correct for every page.
    db_total = (
        await session.execute(select(func.count()).select_from(BrandKitRecord))
    ).scalar_one()
    all_db_slugs: set[str] = set(
        (await session.execute(select(BrandKitRecord.slug))).scalars().all()
    )

    # 2. Enumerate FS-only summaries ONCE (page-invariant). A slug present in
    #    ``all_db_slugs`` is skipped — the DB row is the source of truth and
    #    prevents double-counting.
    base_dir = Path(settings.brand_kits_dir)
    fs_only_summaries: list[BrandKitSummary] = []
    if base_dir.exists():
        for child in sorted(base_dir.iterdir()):
            if not child.is_dir():
                continue
            slug = child.name
            if not _SLUG_RE.match(slug):
                continue
            if slug in all_db_slugs:
                continue  # already in DB — skip (no double count)
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
            fs_only_summaries.append(
                BrandKitSummary(
                    slug=slug,
                    name=kit.name,
                    source_url=kit.source_url,
                    scraped_at=kit.fetched_at,
                )
            )
    fs_only_count = len(fs_only_summaries)

    # 3. Stable total computed BEFORE pagination — invariant across pages.
    total = db_total + fs_only_count

    # 4. Build the DB-side summaries (full unpaginated set, at v1 scale), then
    #    merge with FS-only summaries and sort globally by scraped_at desc so
    #    recency ordering is uniform across sources (IN-03).
    db_rows = (
        (
            await session.execute(
                select(BrandKitRecord).order_by(BrandKitRecord.scraped_at.desc())
            )
        )
        .scalars()
        .all()
    )
    db_summaries: list[BrandKitSummary] = [
        BrandKitSummary(
            slug=r.slug,
            name=r.name,
            source_url=r.source_url,
            scraped_at=r.scraped_at,
        )
        for r in db_rows
    ]

    merged = db_summaries + fs_only_summaries

    def _as_utc(dt: datetime) -> datetime:
        """Normalize naive DB datetimes (SQLite returns them without tzinfo
        even on DateTime(timezone=True)) to UTC so sort comparisons across
        DB-sourced and FS-sourced (tz-aware) datetimes don't TypeError.
        """
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

    merged.sort(key=lambda s: _as_utc(s.scraped_at), reverse=True)
    page = merged[offset : offset + limit]

    return PaginatedBrandKits(
        items=page,
        total=total,
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


# --- GET /brand-kits/{slug}/logos/{filename} (Plan 21-05 Task 1) ------------
#
# T-1 HIGH — path-traversal guard. Mirrors routes/renders.py::_is_within
# (copy rather than import to keep the brand-kits module self-contained; the
# helper is 18 lines and pinning two copies is simpler than refactoring. If
# a third file-streaming route lands later, extract to api/_paths.py).
#
# Whitelist extends renders.py by adding SVG — logos are commonly SVG; the
# renders whitelist excludes SVG because rendered creative output is always
# rasterized PNG / PDF / JPG.

_LOGO_EXT_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
}


def _logo_is_within(candidate: Path, root: Path) -> bool:
    """Path-containment guard (T-1 HIGH).

    True iff ``candidate`` (resolved, must exist) is inside ``root`` (resolved).
    ``strict=True`` on the candidate forces the file to exist AND follows
    symlinks, so any symlink-to-outside-root is rejected. ``is_relative_to``
    (py >= 3.9) correctly handles trailing separators where ``str.startswith``
    would not.
    """
    try:
        resolved = candidate.resolve(strict=True)
    except (FileNotFoundError, OSError):
        return False
    try:
        root_resolved = (
            root.resolve(strict=True) if root.exists() else root.resolve()
        )
    except OSError:
        return False
    return resolved.is_relative_to(root_resolved)


@router.get(
    "/brand-kits/{slug}/logos/{filename}",
    summary="Stream a brand-kit logo file (PNG / JPG / SVG)",
    responses={404: {"description": "Logo not found"}},
)
async def get_brand_kit_logo(
    slug: str = PathParam(..., pattern=r"^[a-z0-9][a-z0-9-]*$", max_length=64),
    filename: str = PathParam(..., max_length=128),
    settings: AppSettings = Depends(get_settings),
) -> FileResponse:
    """Serve a logo from ``.brand-kits/<slug>/logos/<filename>``.

    SECURITY (T-1 HIGH — path traversal). Returns 404 on EVERY failure:

    - slug regex mismatch (handled by FastAPI PathParam validation -> 422)
    - extension not in :data:`_LOGO_EXT_MIME`
    - resolved file path outside ``settings.brand_kits_dir``
    - file missing on disk

    We deliberately do NOT distinguish (e.g. 403 vs 404) — any signal leaks
    filesystem shape to attackers. See routes/renders.py for the same posture
    (Phase 20 T-1 mitigation).
    """
    base = Path(settings.brand_kits_dir) / slug / "logos"
    candidate = base / filename
    media_type = _LOGO_EXT_MIME.get(Path(filename).suffix.lower())
    if media_type is None:
        raise HTTPException(status_code=404, detail="logo not found")
    if not _logo_is_within(candidate, Path(settings.brand_kits_dir)):
        raise HTTPException(status_code=404, detail="logo not found")
    return FileResponse(
        path=candidate,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{candidate.name}"'},
    )
