"""Brand-kit filesystem I/O.

Resolves `FLYER_BRAND_KITS_DIR` (default `.brand-kits/` relative to CWD),
writes each kit under `<base_dir>/<slug>/brand.json`, and enforces a
safe slug regex + path-traversal containment check.

The `BrandKit` Pydantic model is imported lazily inside functions to
avoid a module-load cycle with `flyer_generator/brand_kit/models.py`
(which is created in Plan 02 and runs in the same wave as this module).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

from flyer_generator.config import Settings
from flyer_generator.errors import BrandKitError, BrandKitNotFoundError

if TYPE_CHECKING:  # pragma: no cover
    from flyer_generator.brand_kit.models import BrandKit

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_ALLOW_SYSTEM_ENV = "FLYER_BRAND_KITS_ALLOW_SYSTEM"


def _base_dir(base_dir: Path | None = None) -> Path:
    """Resolve the brand-kit root directory.

    Precedence: explicit `base_dir` > `Settings().brand_kits_dir` (which
    reads `FLYER_BRAND_KITS_DIR` via pydantic-settings).
    """
    if base_dir is not None:
        return base_dir
    return Settings().brand_kits_dir


def _validate_slug(slug: str) -> None:
    if not _SLUG_RE.match(slug):
        raise BrandKitError(
            f"invalid slug {slug!r}: must match ^[a-z0-9][a-z0-9-]*$",
            slug=slug,
        )


def _validate_containment(kit_dir: Path, base: Path) -> None:
    """Guard against path traversal + unsafe system paths.

    Either the resolved kit_dir must be inside CWD or inside Path.home(),
    OR the env var FLYER_BRAND_KITS_ALLOW_SYSTEM=1 must be set explicitly.
    """
    if os.environ.get(_ALLOW_SYSTEM_ENV) == "1":
        return
    resolved = kit_dir.resolve()
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
    raise BrandKitError(
        "resolved brand-kit path is outside CWD and HOME; "
        f"set {_ALLOW_SYSTEM_ENV}=1 to override",
        resolved=str(resolved),
        base=str(base),
    )


def resolve_kit_dir(slug: str, *, base_dir: Path | None = None) -> Path:
    """Return `<base>/<slug>` after slug + containment validation.

    Containment enforcement applies only when `base_dir` is resolved from
    `Settings` (i.e. env var `FLYER_BRAND_KITS_DIR` or the default). When
    a caller passes `base_dir=` explicitly, they have asserted trust in
    that path (tests pass `tmp_path`; library callers construct their
    own Path). The threat model (T-18-CONFIG-01) specifically targets
    env-driven paths; explicit keyword args are out of scope.
    """
    _validate_slug(slug)
    if base_dir is None:
        base = _base_dir(None)
        kit_dir = base / slug
        _validate_containment(kit_dir, base)
    else:
        base = base_dir
        kit_dir = base / slug
    return kit_dir


def save_brand_kit(
    kit: "BrandKit",
    slug: str,
    *,
    base_dir: Path | None = None,
) -> Path:
    """Write `brand.json` under `<base>/<slug>/`. Returns the kit dir.

    The kit dir and its `logos/` and `source/` subdirs are created if
    missing. Logo and source artifact bytes are expected to be written
    separately by the scraper — this function only persists `brand.json`.
    """
    kit_dir = resolve_kit_dir(slug, base_dir=base_dir)
    kit_dir.mkdir(parents=True, exist_ok=True)
    (kit_dir / "logos").mkdir(parents=True, exist_ok=True)
    (kit_dir / "source").mkdir(parents=True, exist_ok=True)
    (kit_dir / "brand.json").write_text(kit.model_dump_json(indent=2), encoding="utf-8")
    return kit_dir


def load_brand_kit(
    slug_or_path: str,
    *,
    base_dir: Path | None = None,
) -> "BrandKit":
    """Load a brand kit by slug (under base_dir) or explicit path to brand.json.

    Raises:
        BrandKitNotFoundError: no matching kit found (subclass of
            ``BrandKitError``, so existing ``except BrandKitError`` callers
            continue to match).
        pydantic.ValidationError: brand.json does not match BrandKit.
        BrandKitError: slug failed validation.
    """
    # Lazy import to break a module-load cycle with models.py (same wave).
    from flyer_generator.brand_kit.models import BrandKit  # noqa: PLC0415

    if slug_or_path.endswith(".json"):
        path = Path(slug_or_path)
    else:
        kit_dir = resolve_kit_dir(slug_or_path, base_dir=base_dir)
        path = kit_dir / "brand.json"
    if not path.is_file():
        available = list_brand_kits(base_dir=base_dir)
        raise BrandKitNotFoundError(
            f"brand kit not found: {path}. Available slugs: {available}",
            slug=slug_or_path,
            expected_path=str(path),
            available=available,
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    return BrandKit.model_validate(raw)


def list_brand_kits(*, base_dir: Path | None = None) -> list[str]:
    """Return sorted list of slugs under the configured base dir."""
    base = _base_dir(base_dir)
    if not base.exists():
        return []
    return sorted(
        p.parent.name
        for p in base.glob("*/brand.json")
        if _SLUG_RE.match(p.parent.name)
    )
