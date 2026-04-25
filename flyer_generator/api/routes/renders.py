"""Render artifact streaming route (API-11).

SECURITY: ``GET /api/v1/renders/{id}/image`` is the only attacker-reachable
file-read endpoint in Phase 20.  T-1 (HIGH) path traversal is mitigated by:

  1. DB lookup — the client supplies only the ``RenderRecord`` primary key,
     never a filename.
  2. Resolved-path containment check — the resolved file MUST live inside
     one of the four configured artifact roots (flyer / brochure / brand-kits
     / social-campaigns). Any failure returns 404 — never a filesystem hint.
  3. Extension whitelist — only PNG / PDF / JPG are mapped to media types.

Returning 404 (not 403) on containment failure is deliberate: we do not leak
whether a render id exists-but-outside-the-allowed-roots vs. is-genuinely-
missing. See analog: :func:`flyer_generator.brand_kit.storage._validate_containment`.
"""

from __future__ import annotations

import os
from datetime import datetime as _dt
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from flyer_generator.api.config import AppSettings
from flyer_generator.api.db import get_session
from flyer_generator.api.deps import get_settings
from flyer_generator.api.models import RenderRecord
from flyer_generator.api.models.brochure import BrochureRecord
from flyer_generator.api.models.flyer import FlyerRecord
from flyer_generator.api.models.postcard import PostcardRecord
from flyer_generator.api.models.poster import PosterRecord
from flyer_generator.api.models.social import PostRecord
from flyer_generator.api.schemas.renders import PaginatedRenders, RenderSummary

_log = structlog.get_logger(__name__)

router = APIRouter(tags=["renders"])

_ALLOWED_EXT_MIME = {
    ".png": "image/png",
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def _is_within(candidate: Path, root: Path) -> bool:
    """True iff ``candidate`` (resolved, must exist) is inside ``root`` (resolved).

    ``strict=True`` on the candidate forces the file to exist AND follows
    symlinks, so any symlink-to-outside-root is rejected.  ``is_relative_to``
    (py >= 3.9) is the canonical containment check — it correctly handles
    trailing separators where ``str.startswith`` would not.
    """
    try:
        resolved = candidate.resolve(strict=True)
    except (FileNotFoundError, OSError):
        return False
    try:
        # Root may not exist on disk during tests — resolve without strict
        # so we can still compare against a configured-but-empty directory.
        root_resolved = root.resolve(strict=True) if root.exists() else root.resolve()
    except OSError:
        return False
    return resolved.is_relative_to(root_resolved)


@router.get(
    "/renders/{render_id}/image",
    summary="Stream a render artifact (PNG / PDF / JPG)",
)
async def get_render_image(
    render_id: str = PathParam(..., min_length=26, max_length=26),
    session: AsyncSession = Depends(get_session),
    settings: AppSettings = Depends(get_settings),
) -> FileResponse:
    """Stream a render artifact to the client.

    Returns 404 on ANY of the following (never distinguishing which):

    - ``render_id`` not present in the ``renders`` table
    - ``file_path`` missing on disk
    - resolved ``file_path`` outside every configured artifact root (T-1)
    - ``file_path`` suffix not in the allowed extension whitelist
    """
    record = await session.get(RenderRecord, render_id)
    if record is None:
        raise HTTPException(status_code=404, detail="render not found")

    candidate = Path(record.file_path)
    allowed_roots = [
        Path(settings.artifact_root_flyer),
        Path(settings.artifact_root_brochure),
        Path(settings.brand_kits_dir),
        Path(settings.social_campaigns_dir),
    ]

    # T-1 containment: resolved file must live inside exactly one allowed root.
    if not any(_is_within(candidate, root) for root in allowed_roots):
        # Deliberately 404 (not 403) — don't leak filesystem shape.
        raise HTTPException(status_code=404, detail="render not found")

    media_type = _ALLOWED_EXT_MIME.get(candidate.suffix.lower())
    if media_type is None:
        # Unknown extension -> reject rather than serve octet-stream.
        raise HTTPException(status_code=404, detail="render not found")

    return FileResponse(
        path=candidate,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{candidate.name}"'},
    )


# --- GET /api/v1/renders (list, Plan 21-11 Task 1) --------------------------
#
# Mirror of ``routes/jobs.py::list_jobs`` / ``routes/brand_kits.py::list_brand_kits``.
# Paginated list sorted by ``created_at`` DESC with two optional filters:
#   - ``kind``: exact match against ``RenderRecord.kind`` (indexed column).
#   - ``since``: datetime lower-bound on ``RenderRecord.created_at``.
#
# File bytes are NOT inlined — callers build the download URL as
# ``/api/v1/renders/{id}/image`` which flows through the streaming route
# above (preserving all T-1 path-containment defenses).


@router.get(
    "/renders",
    response_model=PaginatedRenders,
    summary="List rendered artifacts (newest first; filter by kind / since)",
)
async def list_renders(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    kind: str | None = Query(default=None, max_length=40),
    since: _dt | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> PaginatedRenders:
    """Return paginated render summaries sorted by ``created_at`` DESC.

    Per 21-RESEARCH.md Open Q2 + 21-PATTERNS.md "Backend addition:
    list_renders" — this endpoint is a cheap metadata list; clients fetch
    the bytes via :func:`get_render_image` using the id. T-5 DoS is
    mitigated by the ``le=200`` cap on ``limit``.
    """
    stmt = select(RenderRecord).order_by(RenderRecord.created_at.desc())
    count_stmt = select(func.count()).select_from(RenderRecord)
    if kind is not None:
        stmt = stmt.where(RenderRecord.kind == kind)
        count_stmt = count_stmt.where(RenderRecord.kind == kind)
    if since is not None:
        stmt = stmt.where(RenderRecord.created_at >= since)
        count_stmt = count_stmt.where(RenderRecord.created_at >= since)

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (
        (await session.execute(stmt.limit(limit).offset(offset))).scalars().all()
    )
    items = [
        RenderSummary(
            id=r.id,
            kind=r.kind,
            comfy_job_id=r.comfy_job_id,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return PaginatedRenders(items=items, total=total, limit=limit, offset=offset)


# --- DELETE /api/v1/renders/{render_id} (Plan 24.2-02 RM-02) ---------------
#
# Cascade choice (locked in 24.2-CONTEXT.md): null FK columns on every parent
# table that may reference this render — do NOT hard-block the delete. The
# parent rows stay; the missing render surfaces in detail routes as a null URL.
#
# Critical: SQLite does NOT enable ``PRAGMA foreign_keys=ON`` in this codebase
# (see ``flyer_generator/api/db.py`` — neither ``build_engine`` nor any
# ``listens_for("connect")`` event toggles it). Therefore the schema-level
# ``ondelete="SET NULL"`` declared on every parent ForeignKey does NOT fire
# automatically on SQLite. We must issue explicit UPDATE statements before
# the DELETE so behavior is identical on Postgres (where it would fire) and
# SQLite (where it would silently no-op).

# Tuple of (model, [render-FK-columns]) used by the delete handler. Adding a
# new parent table that references RenderRecord requires adding it here.
_RENDER_PARENT_FK_COLS: tuple[tuple[type, tuple[str, ...]], ...] = (
    (PostcardRecord, ("render_front_id", "render_back_id", "render_pdf_id")),
    (BrochureRecord, ("render_front_id", "render_back_id", "render_pdf_id")),
    (PosterRecord, ("render_id",)),
    (FlyerRecord, ("render_id",)),
    (PostRecord, ("render_id",)),
)


@router.delete(
    "/renders/{render_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary=(
        "Delete a render artifact (DB row + on-disk file). "
        "Idempotent path: re-delete returns 404."
    ),
)
async def delete_render(
    render_id: str = PathParam(..., min_length=26, max_length=26),
    session: AsyncSession = Depends(get_session),
    settings: AppSettings = Depends(get_settings),
) -> None:
    """Delete a render row + best-effort unlink the on-disk artifact.

    Returns:
        - 204 No Content on success (row deleted; file unlinked if present)
        - 404 Not Found if ``render_id`` is unknown OR was already deleted

    The on-disk file is unlinked ONLY when its resolved path lives inside one
    of the configured artifact roots — same containment guard as
    :func:`get_render_image` (T-1 defense-in-depth). If the file is missing,
    outside the allowed roots, or unwriteable, the row is still deleted and
    a structured warning is logged (user intent: purge-from-gallery).
    """
    record = await session.get(RenderRecord, render_id)
    if record is None:
        raise HTTPException(status_code=404, detail="render not found")

    # 1) Null every FK column on every parent table that may reference this
    #    render. SQLite needs this explicit UPDATE because PRAGMA foreign_keys
    #    is off; on Postgres the schema-level ``ondelete="SET NULL"`` would
    #    fire automatically. Writing it explicitly makes behavior DB-agnostic.
    for model, columns in _RENDER_PARENT_FK_COLS:
        for col_name in columns:
            col = getattr(model, col_name)
            await session.execute(
                update(model).where(col == render_id).values({col_name: None})
            )

    # 2) Capture file_path BEFORE deleting the row — once detached, accessing
    #    ORM attributes is undefined behavior under expire_on_commit=False.
    file_path = Path(record.file_path)

    # 3) Delete the DB row. Commit happens in get_session on successful exit.
    await session.delete(record)

    # 4) Best-effort filesystem unlink with the same containment guard as
    #    get_render_image. If the file lives outside every allowed root
    #    (or is missing, or is unwriteable) we LOG and STILL return 204.
    allowed_roots = [
        Path(settings.artifact_root_flyer),
        Path(settings.artifact_root_brochure),
        Path(settings.brand_kits_dir),
        Path(settings.social_campaigns_dir),
    ]
    if any(_is_within(file_path, root) for root in allowed_roots):
        try:
            os.unlink(file_path)
        except FileNotFoundError:
            _log.warning(
                "render_delete_file_missing",
                render_id=render_id,
                file_path=str(file_path),
            )
        except OSError as exc:
            _log.warning(
                "render_delete_unlink_failed",
                render_id=render_id,
                file_path=str(file_path),
                error=str(exc),
            )
    else:
        _log.warning(
            "render_delete_path_outside_roots",
            render_id=render_id,
            file_path=str(file_path),
        )
    # FastAPI emits 204 No Content automatically — do not return anything.
