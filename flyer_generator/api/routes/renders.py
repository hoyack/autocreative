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

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from flyer_generator.api.config import AppSettings
from flyer_generator.api.db import get_session
from flyer_generator.api.deps import get_settings
from flyer_generator.api.models import RenderRecord

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
