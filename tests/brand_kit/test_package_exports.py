"""B1 consolidation guard: every Phase 18 public name must be importable
from `flyer_generator.brand_kit` and listed in `__all__`."""

from __future__ import annotations

import flyer_generator.brand_kit as bk

REQUIRED_NAMES = {
    # Data models
    "BrandKit",
    "BrandLogo",
    "BrandPalette",
    "BrandPhotoHints",
    "BrandTypography",
    "BrandVoice",
    "ColorUsage",
    # Contrast
    "ContrastPair",
    "ContrastReport",
    "classify_level",
    "ensure_aa",
    "passes_aa",
    "passes_aaa",
    "remediate",
    "wcag_ratio",
    # Audit
    "AuditIssue",
    "AuditReport",
    "audit_render",
    "iterate_audit_loop",
    "remediate_contrast",
    "remediate_density",
    # Storage
    "list_brand_kits",
    "load_brand_kit",
    "resolve_kit_dir",
    "save_brand_kit",
    # Scraper
    "fetch_brand_kit",
    # Applier
    "apply_brand_kit",
}


def test_all_required_names_importable() -> None:
    missing = [n for n in REQUIRED_NAMES if not hasattr(bk, n)]
    assert not missing, f"Missing exports from flyer_generator.brand_kit: {missing}"


def test_all_required_names_in_dunder_all() -> None:
    missing = [n for n in REQUIRED_NAMES if n not in bk.__all__]
    assert not missing, f"Missing from __all__: {missing}"


def test_dunder_all_is_sorted() -> None:
    assert list(bk.__all__) == sorted(bk.__all__), "__all__ must be sorted alphabetically"


def test_star_import_matches_dunder_all() -> None:
    # Simulate `from flyer_generator.brand_kit import *`
    ns: dict[str, object] = {}
    exec("from flyer_generator.brand_kit import *", ns)
    ns.pop("__builtins__", None)
    starred = set(ns.keys())
    assert starred == set(bk.__all__), (
        f"Star-import differs from __all__: "
        f"extra={starred - set(bk.__all__)}, missing={set(bk.__all__) - starred}"
    )
