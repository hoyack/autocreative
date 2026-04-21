"""Test BrandKit, BrandPalette, BrandTypography, BrandLogo, BrandVoice,
BrandPhotoHints, ColorUsage: round-trip, partial kits, validation.

Per checker B1: imports use direct-module paths
(`from flyer_generator.brand_kit.models import ...`) so this plan
never writes to the package-root `__init__.py` (which is a docstring-
only stub until Plan 07)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from flyer_generator.brand_kit.models import (
    BrandKit,
    BrandLogo,
    BrandPalette,
    BrandPhotoHints,
    BrandTypography,
    BrandVoice,
    ColorUsage,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_FILE = REPO_ROOT / ".brand-kit-template.json"


def _minimal_kit() -> BrandKit:
    return BrandKit(
        name="Test",
        source_url=None,
        fetched_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
        palette=None,
        typography=None,
        logos=[],
        voice=None,
        photography=None,
        source_artifacts=[],
        size_multiplier=1.0,
    )


def _full_palette() -> BrandPalette:
    return BrandPalette(
        primary=ColorUsage(hex="#1E3A5F", usage_hint="primary CTA"),
        secondary=ColorUsage(hex="#C4A269", usage_hint="supporting accent"),
        accent=ColorUsage(hex="#E8F1F2"),
        neutral_dark=ColorUsage(hex="#1A1A1A"),
        neutral_light=ColorUsage(hex="#FAFAF7"),
        extras={"success": ColorUsage(hex="#2F855A")},
    )


# ---- ColorUsage ---------------------------------------------------------


def test_color_usage_valid() -> None:
    c = ColorUsage(hex="#1E3A5F", usage_hint="primary")
    assert c.hex == "#1E3A5F"
    assert c.usage_hint == "primary"


def test_color_usage_normalizes_uppercase() -> None:
    c = ColorUsage(hex="#1e3a5f")
    assert c.hex == "#1E3A5F"


def test_color_usage_rejects_missing_hash() -> None:
    with pytest.raises(ValidationError):
        ColorUsage(hex="1e3a5f")


def test_color_usage_rejects_wrong_length() -> None:
    with pytest.raises(ValidationError):
        ColorUsage(hex="#1E3A")


def test_color_usage_rejects_non_hex_chars() -> None:
    with pytest.raises(ValidationError):
        ColorUsage(hex="#GGGGGG")


# ---- BrandPalette -------------------------------------------------------


def test_brand_palette_roundtrip() -> None:
    p = _full_palette()
    dumped = p.model_dump_json()
    loaded = BrandPalette.model_validate_json(dumped)
    assert loaded.model_dump() == p.model_dump()


def test_brand_palette_extras_allows_multiple() -> None:
    p = BrandPalette(
        primary=ColorUsage(hex="#000000"),
        secondary=ColorUsage(hex="#111111"),
        accent=ColorUsage(hex="#222222"),
        neutral_dark=ColorUsage(hex="#333333"),
        neutral_light=ColorUsage(hex="#FFFFFF"),
        extras={
            "success": ColorUsage(hex="#2F855A"),
            "danger": ColorUsage(hex="#C53030"),
        },
    )
    assert "success" in p.extras
    assert "danger" in p.extras


def test_brand_palette_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        BrandPalette(
            primary=ColorUsage(hex="#000000"),
            secondary=ColorUsage(hex="#111111"),
            accent=ColorUsage(hex="#222222"),
            neutral_dark=ColorUsage(hex="#333333"),
            neutral_light=ColorUsage(hex="#FFFFFF"),
            tertiary=ColorUsage(hex="#444444"),  # type: ignore[call-arg]
        )


# ---- BrandTypography ----------------------------------------------------


def test_brand_typography_valid() -> None:
    t = BrandTypography(
        heading_family="'Playfair Display', serif",
        body_family="Georgia, serif",
        size_scale={"hero": 120, "body": 34, "caption": 22},
        font_sources=["https://fonts.example.com/p.woff2"],
    )
    assert t.size_scale["hero"] == 120


def test_brand_typography_rejects_non_int_size() -> None:
    with pytest.raises(ValidationError):
        BrandTypography(
            heading_family="serif",
            body_family="serif",
            size_scale={"body": "big"},  # type: ignore[dict-item]
        )


# ---- BrandLogo ----------------------------------------------------------


def test_brand_logo_valid() -> None:
    lg = BrandLogo(path="logos/primary.png", variant="primary", format="png", aspect_ratio=2.5)
    assert lg.variant == "primary"


def test_brand_logo_rejects_bad_variant() -> None:
    with pytest.raises(ValidationError):
        BrandLogo(
            path="logos/x.png",
            variant="unknown_variant",  # type: ignore[arg-type]
            format="png",
            aspect_ratio=1.0,
        )


def test_brand_logo_rejects_bad_format() -> None:
    with pytest.raises(ValidationError):
        BrandLogo(
            path="logos/x.webp",
            variant="primary",
            format="webp",  # type: ignore[arg-type]
            aspect_ratio=1.0,
        )


def test_brand_logo_rejects_zero_aspect_ratio() -> None:
    with pytest.raises(ValidationError):
        BrandLogo(path="logos/x.png", variant="primary", format="png", aspect_ratio=0.0)


# ---- BrandVoice / BrandPhotoHints --------------------------------------


def test_brand_voice_valid() -> None:
    v = BrandVoice(tone="warm", example_phrases=["A", "B"], banned_words=["synergy"])
    assert v.tone == "warm"


def test_brand_photo_hints_all_optional() -> None:
    p = BrandPhotoHints()
    assert p.preferred_style_preset is None
    assert p.color_grade_notes is None


# ---- BrandKit ------------------------------------------------------------


def test_brand_kit_minimal_validates() -> None:
    k = _minimal_kit()
    assert k.palette is None
    assert k.typography is None
    assert k.logos == []


def test_brand_kit_full_roundtrip() -> None:
    k = BrandKit(
        name="Full",
        source_url="https://example.com",
        fetched_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
        palette=_full_palette(),
        typography=BrandTypography(
            heading_family="serif",
            body_family="serif",
            size_scale={"body": 34},
        ),
        logos=[BrandLogo(path="logos/p.png", variant="primary", format="png", aspect_ratio=2.5)],
        voice=BrandVoice(tone="warm"),
        photography=BrandPhotoHints(preferred_style_preset="photorealistic"),
        source_artifacts=["source/screenshot.png"],
        size_multiplier=1.15,
    )
    dumped = k.model_dump_json()
    loaded = BrandKit.model_validate_json(dumped)
    assert loaded.model_dump() == k.model_dump()


def test_brand_kit_from_template_file() -> None:
    """The repo-tracked .brand-kit-template.json MUST parse as a BrandKit.

    In isolated parallel-wave worktrees where Plan 01's template artifact
    has not yet merged, the file may be absent. We skip cleanly with a
    diagnostic message rather than hard-failing — once Plan 01's branch
    merges into the shared trunk the file lands at repo root and this
    test runs for real.
    """
    if not TEMPLATE_FILE.is_file():
        pytest.skip(
            f"{TEMPLATE_FILE.name} not present in this worktree "
            "(Plan 01 creates it in parallel wave)"
        )
    raw = json.loads(TEMPLATE_FILE.read_text(encoding="utf-8"))
    k = BrandKit.model_validate(raw)
    assert k.name == "Example Brand"
    assert k.palette is not None
    assert k.palette.primary.hex == "#1E3A5F"
    assert k.typography is not None
    assert "hero" in k.typography.size_scale


def test_brand_kit_size_multiplier_bounds() -> None:
    # zero → fails (gt=0.0)
    with pytest.raises(ValidationError):
        BrandKit(
            name="X",
            fetched_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
            size_multiplier=0.0,
        )
    # above 3.0 → fails (le=3.0)
    with pytest.raises(ValidationError):
        BrandKit(
            name="X",
            fetched_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
            size_multiplier=3.01,
        )
    # at the boundary 3.0 → OK
    ok = BrandKit(
        name="X",
        fetched_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
        size_multiplier=3.0,
    )
    assert ok.size_multiplier == 3.0


def test_brand_kit_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        BrandKit(
            name="X",
            fetched_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
            secret_field=42,  # type: ignore[call-arg]
        )
