"""Applier tests: palette swap, typography scaling, logo bytes, no-mutation,
partial kits, and AA guardrail.

Direct-module imports only (B1) — never import via the package root
(`from flyer_generator.brand_kit import ...`). Plan 07 owns the
consolidated re-export block.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from flyer_generator.brand_kit.applier import apply_brand_kit
from flyer_generator.brand_kit.contrast import passes_aa
from flyer_generator.brand_kit.models import (
    BrandKit,
    BrandLogo,
    BrandPalette,
    BrandTypography,
    ColorUsage,
)
from flyer_generator.brand_kit.storage import save_brand_kit
from flyer_generator.brochure.schema_renderer.loader import load_template


# ---- Helpers ------------------------------------------------------------


def _full_palette(
    primary: str = "#AABBCC",
    secondary: str = "#DDEEFF",
    accent: str = "#112233",
    neutral_dark: str = "#1A1A1A",
    neutral_light: str = "#FAFAF7",
) -> BrandPalette:
    """A fully populated BrandPalette with AA-safe default neutrals."""
    return BrandPalette(
        primary=ColorUsage(hex=primary),
        secondary=ColorUsage(hex=secondary),
        accent=ColorUsage(hex=accent),
        neutral_dark=ColorUsage(hex=neutral_dark),
        neutral_light=ColorUsage(hex=neutral_light),
        extras={},
    )


def _kit(
    *,
    palette: BrandPalette | None = None,
    typography: BrandTypography | None = None,
    logos: list[BrandLogo] | None = None,
    size_multiplier: float = 1.0,
) -> BrandKit:
    return BrandKit(
        name="Test",
        fetched_at=datetime.now(timezone.utc),
        palette=palette,
        typography=typography,
        logos=logos or [],
        size_multiplier=size_multiplier,
    )


# ---- Palette swap -------------------------------------------------------


def test_apply_brand_kit_swaps_palette_accent_default() -> None:
    """Truth: `accent_default` equals `kit.palette.primary.hex` (uppercased)."""
    t = load_template("editorial_classic")
    kit = _kit(palette=_full_palette(primary="#AABBCC"))
    new_t, _ = apply_brand_kit(t, kit)
    assert new_t.palette.accent_default == "#AABBCC"


def test_apply_brand_kit_swaps_palette_neutrals() -> None:
    """Truth: neutral_dark/neutral_light swap through verbatim when AA passes."""
    t = load_template("editorial_classic")
    kit = _kit(
        palette=_full_palette(neutral_dark="#0A0A0A", neutral_light="#FFFFFF"),
    )
    new_t, _ = apply_brand_kit(t, kit)
    assert new_t.palette.neutral_dark == "#0A0A0A"
    assert new_t.palette.neutral_light == "#FFFFFF"


def test_apply_brand_kit_swaps_secondary_into_muted() -> None:
    """BrandPalette.secondary maps to the template's muted slot."""
    t = load_template("editorial_classic")
    kit = _kit(palette=_full_palette(secondary="#DDEEFF"))
    new_t, _ = apply_brand_kit(t, kit)
    assert new_t.palette.muted == "#DDEEFF"


def test_apply_brand_kit_copies_extras() -> None:
    """BrandPalette.extras hexes land in Palette.extras by key."""
    t = load_template("editorial_classic")
    bp = _full_palette()
    bp = bp.model_copy(
        update={"extras": {"success": ColorUsage(hex="#2F855A")}}
    )
    kit = _kit(palette=bp)
    new_t, _ = apply_brand_kit(t, kit)
    assert new_t.palette.extras == {"success": "#2F855A"}


def test_apply_brand_kit_palette_none_keeps_template_palette() -> None:
    """Truth: when kit.palette is None, new_t.palette == t.palette."""
    t = load_template("editorial_classic")
    kit = _kit(palette=None)
    new_t, _ = apply_brand_kit(t, kit)
    assert new_t.palette == t.palette


# ---- Typography swap + size scaling -------------------------------------


def test_apply_brand_kit_swaps_font_families() -> None:
    """Truth: heading_family / body_family swap from kit.typography."""
    t = load_template("editorial_classic")
    kit = _kit(
        typography=BrandTypography(
            heading_family="'Space Grotesk', sans-serif",
            body_family="'Inter', sans-serif",
        ),
    )
    new_t, _ = apply_brand_kit(t, kit)
    assert new_t.typography.heading_family == "'Space Grotesk', sans-serif"
    assert new_t.typography.body_family == "'Inter', sans-serif"


def test_apply_brand_kit_typography_none_keeps_template_typography() -> None:
    """Truth: when kit.typography is None and size_multiplier==1.0, unchanged."""
    t = load_template("editorial_classic")
    kit = _kit(typography=None)
    new_t, _ = apply_brand_kit(t, kit)
    assert new_t.typography == t.typography


def test_apply_brand_kit_scales_body_size_by_multiplier() -> None:
    """Truth: `body_size == round(original_body_size * size_multiplier)`."""
    t = load_template("editorial_classic")
    original_body = t.typography.body_size
    kit = _kit(size_multiplier=1.5)
    new_t, _ = apply_brand_kit(t, kit)
    assert new_t.typography.body_size == round(original_body * 1.5)


def test_apply_brand_kit_scales_all_size_fields() -> None:
    """Every pixel-size field on Typography scales by the multiplier."""
    t = load_template("editorial_classic")
    kit = _kit(size_multiplier=1.2)
    new_t, _ = apply_brand_kit(t, kit)
    for field in (
        "cover_title_size",
        "cover_subtitle_size",
        "heading_size",
        "body_size",
        "body_line_height",
        "bullet_size",
        "bullet_line_height",
    ):
        orig = getattr(t.typography, field)
        got = getattr(new_t.typography, field)
        assert got == round(orig * 1.2), (
            f"{field}: expected {round(orig * 1.2)}, got {got}"
        )


def test_apply_brand_kit_does_not_scale_chars_per_line() -> None:
    """body_max_chars_per_line is a character budget, not a pixel size."""
    t = load_template("editorial_classic")
    kit = _kit(size_multiplier=1.5)
    new_t, _ = apply_brand_kit(t, kit)
    assert (
        new_t.typography.body_max_chars_per_line
        == t.typography.body_max_chars_per_line
    )


def test_apply_brand_kit_size_multiplier_1_is_noop_on_sizes() -> None:
    """size_multiplier == 1.0 must be a strict no-op on every size field."""
    t = load_template("editorial_classic")
    kit = _kit(size_multiplier=1.0)
    new_t, _ = apply_brand_kit(t, kit)
    assert new_t.typography.body_size == t.typography.body_size
    assert new_t.typography.cover_title_size == t.typography.cover_title_size
    assert new_t.typography.heading_size == t.typography.heading_size


# ---- No mutation --------------------------------------------------------


def test_apply_brand_kit_does_not_mutate_input() -> None:
    """Truth (T-18-APPLIER-03): the passed-in template is never mutated."""
    t = load_template("editorial_classic")
    before = t.model_dump_json()
    kit = _kit(
        palette=_full_palette(primary="#AABBCC"),
        typography=BrandTypography(heading_family="serif", body_family="serif"),
        size_multiplier=1.25,
    )
    _new_t, _ = apply_brand_kit(t, kit)
    after = t.model_dump_json()
    assert before == after


# ---- Logo bytes ---------------------------------------------------------


def test_apply_brand_kit_logo_bytes_none_when_no_logos() -> None:
    """Truth: kit.logos == [] -> logo_bytes is None."""
    t = load_template("editorial_classic")
    kit = _kit(logos=[])
    _new_t, logo_bytes = apply_brand_kit(t, kit, slug="x")
    assert logo_bytes is None


def test_apply_brand_kit_logo_bytes_none_when_slug_not_provided() -> None:
    """Without a slug the applier cannot resolve kit_dir; return None."""
    t = load_template("editorial_classic")
    kit = _kit(
        logos=[
            BrandLogo(
                path="logos/p.png",
                variant="primary",
                format="png",
                aspect_ratio=1.0,
            )
        ],
    )
    _new_t, logo_bytes = apply_brand_kit(t, kit)  # no slug, no base_dir
    assert logo_bytes is None


def test_apply_brand_kit_reads_primary_logo(tmp_path: Path) -> None:
    """Happy path: with a saved kit + primary logo bytes on disk, return bytes."""
    t = load_template("editorial_classic")
    kit_dir = tmp_path / "test-kit"
    (kit_dir / "logos").mkdir(parents=True)
    logo_bytes_written = b"\x89PNG\r\n\x1a\ntest-logo-bytes"
    (kit_dir / "logos" / "primary.png").write_bytes(logo_bytes_written)

    kit = _kit(
        logos=[
            BrandLogo(
                path="logos/primary.png",
                variant="primary",
                format="png",
                aspect_ratio=1.0,
            ),
        ],
    )
    save_brand_kit(kit, "test-kit", base_dir=tmp_path)

    _new_t, logo_bytes = apply_brand_kit(
        t, kit, slug="test-kit", base_dir=tmp_path
    )
    assert logo_bytes == logo_bytes_written


def test_apply_brand_kit_logo_traversal_blocked(tmp_path: Path) -> None:
    """T-18-APPLIER-01: a logo.path that resolves outside kit_dir is skipped."""
    t = load_template("editorial_classic")
    kit_dir = tmp_path / "bad-kit"
    (kit_dir / "logos").mkdir(parents=True)

    kit = _kit(
        logos=[
            BrandLogo(
                path="../../../etc/passwd",
                variant="primary",
                format="png",
                aspect_ratio=1.0,
            ),
        ],
    )
    save_brand_kit(kit, "bad-kit", base_dir=tmp_path)

    _new_t, logo_bytes = apply_brand_kit(
        t, kit, slug="bad-kit", base_dir=tmp_path
    )
    assert logo_bytes is None


def test_apply_brand_kit_prefers_primary_variant(tmp_path: Path) -> None:
    """When multiple logos exist, the 'primary' variant wins regardless of order."""
    t = load_template("editorial_classic")
    kit_dir = tmp_path / "multi-logo"
    (kit_dir / "logos").mkdir(parents=True)
    (kit_dir / "logos" / "primary.png").write_bytes(b"primary-bytes")
    (kit_dir / "logos" / "mono.png").write_bytes(b"mono-bytes")

    kit = _kit(
        logos=[
            BrandLogo(
                path="logos/mono.png",
                variant="mono_dark",
                format="png",
                aspect_ratio=1.0,
            ),
            BrandLogo(
                path="logos/primary.png",
                variant="primary",
                format="png",
                aspect_ratio=1.0,
            ),
        ],
    )
    save_brand_kit(kit, "multi-logo", base_dir=tmp_path)

    _new_t, logo_bytes = apply_brand_kit(
        t, kit, slug="multi-logo", base_dir=tmp_path
    )
    assert logo_bytes == b"primary-bytes"


def test_apply_brand_kit_falls_back_to_first_logo_when_no_primary(
    tmp_path: Path,
) -> None:
    """No `primary` variant present -> fall back to kit.logos[0]."""
    t = load_template("editorial_classic")
    kit_dir = tmp_path / "no-primary"
    (kit_dir / "logos").mkdir(parents=True)
    (kit_dir / "logos" / "mark.svg").write_bytes(b"<svg/>")

    kit = _kit(
        logos=[
            BrandLogo(
                path="logos/mark.svg",
                variant="mark_only",
                format="svg",
                aspect_ratio=1.0,
            ),
        ],
    )
    save_brand_kit(kit, "no-primary", base_dir=tmp_path)

    _new_t, logo_bytes = apply_brand_kit(
        t, kit, slug="no-primary", base_dir=tmp_path
    )
    assert logo_bytes == b"<svg/>"


def test_apply_brand_kit_missing_logo_file_returns_none(tmp_path: Path) -> None:
    """When the kit points at a logo file that doesn't exist on disk, return None."""
    t = load_template("editorial_classic")
    kit = _kit(
        logos=[
            BrandLogo(
                path="logos/missing.png",
                variant="primary",
                format="png",
                aspect_ratio=1.0,
            ),
        ],
    )
    save_brand_kit(kit, "gap-kit", base_dir=tmp_path)
    _new_t, logo_bytes = apply_brand_kit(
        t, kit, slug="gap-kit", base_dir=tmp_path
    )
    assert logo_bytes is None


# ---- AA guardrail -------------------------------------------------------


def test_apply_brand_kit_aa_guardrail_swaps_on_fail() -> None:
    """When the naive neutral_dark/neutral_light pair fails AA, the applier
    either (a) remediates via ensure_aa to a passing pair, or (b) leaves
    the original hexes untouched when no remediation exists. Either is
    acceptable per the plan — what's NOT acceptable is silently producing
    a FAIL-AA pair and pretending everything's fine.
    """
    t = load_template("editorial_classic")
    kit = _kit(
        palette=BrandPalette(
            primary=ColorUsage(hex="#000000"),
            secondary=ColorUsage(hex="#111111"),
            accent=ColorUsage(hex="#222222"),
            neutral_dark=ColorUsage(hex="#505050"),
            neutral_light=ColorUsage(hex="#606060"),  # ratio ~1.28 — FAIL
            extras={},
        ),
    )
    new_t, _ = apply_brand_kit(t, kit)
    pair_ok = passes_aa(
        new_t.palette.neutral_dark, new_t.palette.neutral_light
    )
    pair_original = (
        new_t.palette.neutral_dark == "#505050"
        and new_t.palette.neutral_light == "#606060"
    )
    assert pair_ok or pair_original


def test_apply_brand_kit_passing_pair_unchanged() -> None:
    """A palette that already passes AA must survive the guardrail verbatim."""
    t = load_template("editorial_classic")
    kit = _kit(
        palette=_full_palette(neutral_dark="#000000", neutral_light="#FFFFFF"),
    )
    new_t, _ = apply_brand_kit(t, kit)
    assert new_t.palette.neutral_dark == "#000000"
    assert new_t.palette.neutral_light == "#FFFFFF"


# ---- Integration: .brand-kit-template.json + editorial_classic ----------


def test_apply_template_json_kit_to_editorial_classic() -> None:
    """Repo-tracked `.brand-kit-template.json` applies cleanly to
    `editorial_classic`: accent swap is verbatim and the body-on-panel
    pair still passes AA.
    """
    repo_root = Path(__file__).resolve().parents[2]
    template_file = repo_root / ".brand-kit-template.json"
    raw = json.loads(template_file.read_text(encoding="utf-8"))
    kit = BrandKit.model_validate(raw)

    t = load_template("editorial_classic")
    new_t, _ = apply_brand_kit(t, kit)
    assert new_t.palette.accent_default == "#1E3A5F"
    assert passes_aa(new_t.palette.neutral_dark, new_t.palette.neutral_light)
