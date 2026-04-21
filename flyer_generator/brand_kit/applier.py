"""Apply a BrandKit to a TemplateSchema -> (new template, logo_bytes).

Never mutates the input template. Mirrors the `accent_override` pattern at
`flyer_generator/brochure/schema_renderer/renderer.py:752-759`
(nested `model_copy(update={...})` at field granularity).

Pipeline:
  1. Build a new ``Palette`` from ``kit.palette`` (if present); else keep
     ``template.palette`` unchanged.
  2. Build a new ``Typography`` by swapping ``heading_family`` /
     ``body_family`` from ``kit.typography`` (if present) and scaling
     every ``*_size: int`` by ``round(value * kit.size_multiplier)``
     (default ``1.0`` is a no-op).
  3. Validate AA contrast on the canonical body-text pair
     ``(neutral_dark, neutral_light)``. A failing pair is auto-remediated
     via ``contrast.ensure_aa`` (swap to the opposite neutral) and a
     single warning is logged per correction. The accent is left
     untouched so that the truth invariant
     "``accent_default`` equals ``kit.palette.primary.hex``" holds — the
     kit's brand color survives the applier verbatim.
  4. Read primary logo bytes from ``<kit_dir>/<logo.path>`` when the
     caller provides ``slug`` (and optionally ``base_dir``). A
     ``.resolve()`` containment check blocks path traversal.

Design rules (from plan):
  * ``__init__.py`` is NOT touched by this plan (Plan 07 owns the
    consolidated re-export block).
  * All cross-module imports are direct-module so the package-init stays
    a stub.
"""

from __future__ import annotations

from pathlib import Path

import structlog

from flyer_generator.brand_kit.contrast import ensure_aa
from flyer_generator.brand_kit.models import BrandKit
from flyer_generator.brochure.schema_renderer.schema_model import (
    Palette,
    TemplateSchema,
    Typography,
)

logger = structlog.get_logger()

# Every ``*_size: int`` field on Typography must scale by ``kit.size_multiplier``.
# ``body_max_chars_per_line`` is deliberately excluded: it's a character
# budget, not a pixel size.
_SCALED_SIZE_FIELDS: tuple[str, ...] = (
    "cover_title_size",
    "cover_subtitle_size",
    "heading_size",
    "body_size",
    "body_line_height",
    "bullet_size",
    "bullet_line_height",
)


def _build_palette(template_palette: Palette, kit: BrandKit) -> Palette:
    """Return a new Palette derived from ``kit``; keep template unchanged if kit has none."""
    if kit.palette is None:
        return template_palette

    bp = kit.palette
    accent = bp.primary.hex
    neutral_dark = bp.neutral_dark.hex
    neutral_light = bp.neutral_light.hex
    muted = bp.secondary.hex
    extras = {k: v.hex for k, v in bp.extras.items()}

    # AA guardrail 1: neutral_dark on neutral_light (the canonical "body text
    # on panel background" pair). Swap neutral_dark via ensure_aa if the
    # naive swap fails.
    fixed_dark, note = ensure_aa(
        neutral_dark,
        neutral_light,
        palette_neutrals=(neutral_dark, neutral_light),
    )
    if note is not None:
        logger.warning(
            "brand_kit_palette_aa_fix",
            pair="neutral_dark_on_neutral_light",
            original=neutral_dark,
            corrected=fixed_dark,
            note=note,
        )
        neutral_dark = fixed_dark

    # NOTE: Accent is intentionally NOT auto-remediated here. The truth
    # invariant "palette.accent_default equals kit.palette.primary.hex" is
    # load-bearing for downstream users who expect the brand color to
    # survive the applier verbatim. The template's body-text-on-panel AA
    # story is carried by the neutral_dark/neutral_light swap above. Any
    # accent-vs-text contrast concerns are handled inline during render
    # (render-time shape/text contrast is the audit subsystem's
    # responsibility — Plan 04/06).

    try:
        return Palette(
            accent_default=accent,
            neutral_dark=neutral_dark,
            neutral_light=neutral_light,
            muted=muted,
            extras=extras,
        )
    except Exception as err:  # noqa: BLE001 — defensive: any Pydantic failure
        # falls back to the untouched template palette rather than crashing
        # the render pipeline.
        logger.warning(
            "brand_kit_palette_build_failed_keeping_template",
            error=str(err),
        )
        return template_palette


def _normalize_font_stack(stack: str) -> str:
    """Replace any embedded double quotes with single quotes so the value can
    be inlined into an SVG ``font-family="..."`` attribute without breaking XML.

    CSS font stacks commonly ship as ``"Open Sans", sans-serif`` (double-quoted
    family names), but that form is invalid inside a double-quoted SVG
    attribute. Single quotes are equally valid per CSS/SVG for family names
    containing spaces.
    """
    return stack.replace('"', "'")


def _build_typography(template_typ: Typography, kit: BrandKit) -> Typography:
    """Return a new Typography with kit font families + sizes scaled by size_multiplier."""
    updates: dict[str, object] = {}

    if kit.typography is not None:
        if kit.typography.heading_family:
            updates["heading_family"] = _normalize_font_stack(kit.typography.heading_family)
        if kit.typography.body_family:
            updates["body_family"] = _normalize_font_stack(kit.typography.body_family)

    multiplier = kit.size_multiplier
    # Use a tiny epsilon so size_multiplier=1.0 is a strict no-op (avoids
    # pointlessly rewriting every size field with round(x*1.0)=x).
    if abs(multiplier - 1.0) > 1e-9:
        for field in _SCALED_SIZE_FIELDS:
            orig = getattr(template_typ, field)
            updates[field] = max(1, round(orig * multiplier))

    if not updates:
        return template_typ
    return template_typ.model_copy(update=updates)


def _load_primary_logo_bytes(
    kit: BrandKit,
    slug: str | None,
    base_dir: Path | None,
) -> bytes | None:
    """Return bytes of the primary logo (or first logo) on disk, or ``None``.

    Guards against path traversal: the resolved logo path must be inside
    the resolved kit directory. A traversal attempt logs a warning and
    returns ``None`` rather than raising — the rest of the render still
    proceeds without a logo.
    """
    if not kit.logos:
        return None
    if slug is None:
        # Callers that don't pass a slug can't resolve a kit dir — logos
        # require the slug/base_dir context (Plan 01 resolve_kit_dir).
        return None

    # Local import so the package's module-load graph stays acyclic (Plan 01
    # storage.py also imports BrandKit lazily for the same reason).
    from flyer_generator.brand_kit.storage import resolve_kit_dir  # noqa: PLC0415

    kit_dir = resolve_kit_dir(slug, base_dir=base_dir).resolve()
    primary = next(
        (lg for lg in kit.logos if lg.variant == "primary"),
        kit.logos[0],
    )
    candidate = (kit_dir / primary.path).resolve()
    try:
        candidate.relative_to(kit_dir)
    except ValueError:
        # T-18-APPLIER-01: path-traversal guard. Log + skip, never raise.
        logger.warning(
            "brand_kit_logo_path_traversal_blocked",
            path=primary.path,
            kit_dir=str(kit_dir),
        )
        return None
    if not candidate.is_file():
        logger.warning("brand_kit_logo_missing", path=str(candidate))
        return None
    return candidate.read_bytes()


def apply_brand_kit(
    template: TemplateSchema,
    kit: BrandKit,
    *,
    slug: str | None = None,
    base_dir: Path | None = None,
) -> tuple[TemplateSchema, bytes | None]:
    """Return ``(new_template, logo_bytes)``. Never mutates the input template.

    Args:
        template: The source template. Never mutated — returned template is
            produced via ``template.model_copy(update=...)``.
        kit: The brand kit to apply. Partial kits are supported: any of
            ``palette``, ``typography``, ``logos`` may be absent.
        slug: When provided (with optional ``base_dir``), primary logo
            bytes are loaded from ``<base_dir>/<slug>/<logo.path>``.
        base_dir: Override for the brand-kits root directory. When
            ``None``, the value from ``Settings().brand_kits_dir`` is used
            (i.e. ``$FLYER_BRAND_KITS_DIR`` or ``.brand-kits/`` relative
            to CWD).

    Returns:
        ``(new_template, logo_bytes)`` where ``logo_bytes`` is ``None`` when
        the kit has no logos or the ``slug`` was not supplied.
    """
    new_palette = _build_palette(template.palette, kit)
    new_typography = _build_typography(template.typography, kit)

    new_template = template.model_copy(
        update={"palette": new_palette, "typography": new_typography}
    )
    logo_bytes = _load_primary_logo_bytes(kit, slug, base_dir)
    return new_template, logo_bytes
