"""Brand kit subsystem (Phase 18).

Public API -- every name is re-exported here for ergonomic imports.
Direct-module imports (`from flyer_generator.brand_kit.models import BrandKit`)
remain supported and are used inside the test suite to avoid same-wave
__init__.py write conflicts during phase execution (see Plans 01-06).

Categories:
    Data models:      BrandKit, BrandPalette, BrandTypography, BrandLogo,
                      BrandVoice, BrandPhotoHints, ColorUsage
    Contrast:         ContrastPair, ContrastReport, wcag_ratio, passes_aa,
                      passes_aaa, classify_level, remediate, ensure_aa
    Audit:            AuditIssue, AuditReport, audit_render,
                      iterate_audit_loop, remediate_contrast,
                      remediate_density
    Storage:          save_brand_kit, load_brand_kit, list_brand_kits,
                      resolve_kit_dir
    Scraper:          fetch_brand_kit
    Applier:          apply_brand_kit

Owned by Plan 18-07 (see .planning/phases/18-brand-kit-system/18-07-PLAN.md).
"""

from __future__ import annotations

from flyer_generator.brand_kit.applier import apply_brand_kit
from flyer_generator.brand_kit.audit import (
    AuditIssue,
    AuditReport,
    audit_render,
    iterate_audit_loop,
    remediate_contrast,
    remediate_density,
)
from flyer_generator.brand_kit.contrast import (
    ContrastPair,
    ContrastReport,
    classify_level,
    ensure_aa,
    passes_aa,
    passes_aaa,
    remediate,
    wcag_ratio,
)
from flyer_generator.brand_kit.models import (
    BrandKit,
    BrandLogo,
    BrandPalette,
    BrandPhotoHints,
    BrandTypography,
    BrandVoice,
    ColorUsage,
)
from flyer_generator.brand_kit.scraper import fetch_brand_kit
from flyer_generator.brand_kit.storage import (
    list_brand_kits,
    load_brand_kit,
    resolve_kit_dir,
    save_brand_kit,
)

__all__ = sorted(
    [
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
    ]
)
