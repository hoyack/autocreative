"""Social-campaign filesystem I/O.

Clones the shape of ``flyer_generator/brand_kit/storage.py`` and adds a
``campaign_id`` nesting layer: artifacts land at
``<base_dir>/<slug>/<campaign_id>/<template_name>/post.json``.

Both the slug and the campaign_id are validated against a strict regex before
any filesystem access. ``_validate_containment`` mirrors the brand-kit guard
but also accepts the explicit ``base_dir`` argument as a valid root so
``tmp_path`` usage in tests round-trips cleanly.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

from flyer_generator.config import Settings
from flyer_generator.errors import SocialError

if TYPE_CHECKING:  # pragma: no cover
    from flyer_generator.social.models import Campaign, Post

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
# ULID shape: 26 uppercase base32 chars. We accept the full [0-9A-Z] range
# (rather than strict Crockford which excludes I/L/O/U) because downstream
# test fixtures use the looser form and the regex's job here is path-
# traversal defense: any char outside ``[0-9A-Z]`` is rejected.
_ULID_RE = re.compile(r"^[0-9A-Z]{26}$")
_ALLOW_SYSTEM_ENV = "FLYER_SOCIAL_CAMPAIGNS_ALLOW_SYSTEM"


def _base_dir(base_dir: Path | None = None) -> Path:
    """Resolve the social-campaigns root directory.

    Precedence: explicit ``base_dir`` > ``Settings().social_campaigns_dir``
    (which reads ``FLYER_SOCIAL_CAMPAIGNS_DIR`` via pydantic-settings).
    """
    if base_dir is not None:
        return base_dir
    return Settings().social_campaigns_dir


def _validate_slug(slug: str, *, field: str = "slug") -> None:
    if not _SLUG_RE.match(slug):
        raise SocialError(
            f"invalid {field} {slug!r}: must match ^[a-z0-9][a-z0-9-]*$",
            slug=slug,
        )


def _validate_campaign_id(campaign_id: str) -> None:
    """Accept either a ULID (26 Crockford-base32 chars) or a generic slug.

    Using both accommodates test fixtures that prefer short IDs while still
    rejecting path-traversal input (``../evil``) at the regex boundary.
    """
    if _ULID_RE.match(campaign_id):
        return
    if _SLUG_RE.match(campaign_id):
        return
    raise SocialError(
        f"invalid campaign_id {campaign_id!r}: must be ULID or slug",
        campaign_id=campaign_id,
    )


def _validate_containment(target: Path, base: Path) -> None:
    """Guard against path traversal + unsafe system paths.

    Either the resolved ``target`` must be inside the explicit ``base``, the
    CWD, or ``Path.home()``, OR ``FLYER_SOCIAL_CAMPAIGNS_ALLOW_SYSTEM=1`` must
    be set explicitly. Accepting ``base`` covers the ``tmp_path`` test case
    where pytest's tmp dir may be outside both CWD and HOME.
    """
    if os.environ.get(_ALLOW_SYSTEM_ENV) == "1":
        return
    resolved = target.resolve()
    cwd = Path.cwd().resolve()
    home = Path.home().resolve()
    try:
        resolved.relative_to(cwd)
        return
    except ValueError:
        pass
    try:
        resolved.relative_to(home)
        return
    except ValueError:
        pass
    try:
        resolved.relative_to(base.resolve())
        return
    except ValueError:
        pass
    raise SocialError(
        "resolved social-campaign path is outside CWD, HOME, and base; "
        f"set {_ALLOW_SYSTEM_ENV}=1 to override",
        resolved=str(resolved),
        base=str(base),
    )


def resolve_campaign_dir(
    slug: str,
    campaign_id: str,
    *,
    base_dir: Path | None = None,
) -> Path:
    """Return ``<base>/<slug>/<campaign_id>`` after slug + id + containment validation."""
    _validate_slug(slug, field="slug")
    _validate_campaign_id(campaign_id)
    base = _base_dir(base_dir)
    target = base / slug / campaign_id
    _validate_containment(target, base)
    return target


def save_post(
    post: "Post",
    slug: str,
    campaign_id: str,
    template_name: str,
    *,
    base_dir: Path | None = None,
) -> Path:
    """Write ``post.json`` and (optionally) ``image.png`` under the campaign dir.

    Returns the post directory. ``image_bytes`` is excluded from ``post.json``
    so campaign artifacts stay grep-friendly; the bytes live in ``image.png``.
    """
    campaign_dir = resolve_campaign_dir(slug, campaign_id, base_dir=base_dir)
    post_dir = campaign_dir / template_name
    post_dir.mkdir(parents=True, exist_ok=True)

    data = post.model_dump(mode="json", exclude={"image_bytes"})
    (post_dir / "post.json").write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if post.image_bytes is not None:
        (post_dir / "image.png").write_bytes(post.image_bytes)
    return post_dir


def load_post(
    slug: str,
    campaign_id: str,
    template_name: str,
    *,
    base_dir: Path | None = None,
) -> "Post":
    """Reconstruct a :class:`Post` from ``post.json`` (+ ``image.png`` if present)."""
    from flyer_generator.social.models import Post  # noqa: PLC0415 — lazy, break cycle

    post_dir = resolve_campaign_dir(slug, campaign_id, base_dir=base_dir) / template_name
    data = json.loads((post_dir / "post.json").read_text(encoding="utf-8"))
    img_path = post_dir / "image.png"
    if img_path.exists():
        data["image_bytes"] = img_path.read_bytes()
    return Post.model_validate(data)


def save_campaign(
    campaign: "Campaign",
    *,
    base_dir: Path | None = None,
) -> Path:
    """Write ``campaign.json`` at ``<base>/<slug>/<campaign_id>/``."""
    campaign_dir = resolve_campaign_dir(
        campaign.brand_kit_slug,
        campaign.campaign_id,
        base_dir=base_dir,
    )
    campaign_dir.mkdir(parents=True, exist_ok=True)
    (campaign_dir / "campaign.json").write_text(
        campaign.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    return campaign_dir


def load_campaign(
    slug: str,
    campaign_id: str,
    *,
    base_dir: Path | None = None,
) -> "Campaign":
    """Load a :class:`Campaign` from ``campaign.json``."""
    from flyer_generator.social.models import Campaign  # noqa: PLC0415 — lazy, break cycle

    campaign_dir = resolve_campaign_dir(slug, campaign_id, base_dir=base_dir)
    data = json.loads((campaign_dir / "campaign.json").read_text(encoding="utf-8"))
    return Campaign.model_validate(data)


def list_campaigns(slug: str, *, base_dir: Path | None = None) -> list[str]:
    """Return sorted campaign_ids for a given brand-kit slug."""
    _validate_slug(slug)
    base = _base_dir(base_dir)
    slug_dir = base / slug
    if not slug_dir.exists():
        return []
    return sorted(p.name for p in slug_dir.iterdir() if p.is_dir())
