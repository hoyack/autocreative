"""WCAG contrast validation + auto-remediation.

Thin wrapper around `wcag-contrast-ratio` (for ratio math) and
`coloraide` (for OKLCH lightness adjustments) that produces
JSON-round-trippable `ContrastPair` / `ContrastReport` Pydantic models.

Remediation strategy (in order):
  1. If pair already passes AA -> return unchanged.
  2. Try the OPPOSITE neutral (dark <-> light from the kit palette).
  3. Binary-search OKLCH lightness of the original fg, preserving hue.
  4. If nothing passes -> return original fg + FAIL note (caller decides
     whether to escalate to BrandKitContrastError or log-and-continue).

Ratio thresholds (WCAG 2.1):
  * AA   -- body text >= 4.5, large text (>= 24pt or 18.66pt bold) >= 3.0
  * AAA  -- body text >= 7.0, large text >= 4.5

Key pitfall mitigation:
  The underlying `wcag-contrast-ratio` library's core function REQUIRES
  float triples 0.0-1.0, NOT int 0-255. Every call is routed through
  `_hex_to_floats()` + `wcag_ratio()`. No direct library rgb calls exist
  outside the `wcag_ratio` helper -- this is enforced by a grep acceptance
  check in the plan (the internal library call is isolated to one site).
"""

from __future__ import annotations

from typing import Literal

import wcag_contrast_ratio as _wcag
from coloraide import Color
from pydantic import BaseModel, ConfigDict, Field, field_validator

from flyer_generator.brochure.models import validate_hex_color

Level = Literal["AAA", "AA", "FAIL"]

_AA_BODY = 4.5
_AA_LARGE = 3.0
_AAA_BODY = 7.0
_AAA_LARGE = 4.5


# ---- Hex <-> wcag-contrast-ratio plumbing -------------------------------


def _hex_to_floats(hex_color: str) -> tuple[float, float, float]:
    """Normalize + convert #RRGGBB to (r, g, b) floats in 0.0-1.0.

    `wcag-contrast-ratio` REQUIRES floats in 0.0-1.0; ints 0-255 silently
    produce nonsense ratios (Pitfall 2 in RESEARCH.md).
    """
    normalized = validate_hex_color(hex_color)  # raises ValueError if invalid
    h = normalized.lstrip("#")
    return (
        int(h[0:2], 16) / 255.0,
        int(h[2:4], 16) / 255.0,
        int(h[4:6], 16) / 255.0,
    )


def wcag_ratio(fg_hex: str, bg_hex: str) -> float:
    """Return the WCAG 2.1 contrast ratio (1.0 - 21.0, symmetric)."""
    return _wcag.rgb(_hex_to_floats(fg_hex), _hex_to_floats(bg_hex))


def passes_aa(fg_hex: str, bg_hex: str, *, large_text: bool = False) -> bool:
    """True when the pair meets WCAG 2.1 AA (4.5 body / 3.0 large)."""
    threshold = _AA_LARGE if large_text else _AA_BODY
    return wcag_ratio(fg_hex, bg_hex) >= threshold


def passes_aaa(fg_hex: str, bg_hex: str, *, large_text: bool = False) -> bool:
    """True when the pair meets WCAG 2.1 AAA (7.0 body / 4.5 large)."""
    threshold = _AAA_LARGE if large_text else _AAA_BODY
    return wcag_ratio(fg_hex, bg_hex) >= threshold


def classify_level(fg_hex: str, bg_hex: str, *, large_text: bool = False) -> Level:
    """Classify a pair as AAA / AA / FAIL per WCAG 2.1 thresholds."""
    r = wcag_ratio(fg_hex, bg_hex)
    aaa_threshold = _AAA_LARGE if large_text else _AAA_BODY
    aa_threshold = _AA_LARGE if large_text else _AA_BODY
    if r >= aaa_threshold:
        return "AAA"
    if r >= aa_threshold:
        return "AA"
    return "FAIL"


# ---- Remediation --------------------------------------------------------


def _normalize_oklch_output(color: Color) -> str:
    """Convert coloraide output back to uppercased #RRGGBB.

    coloraide's `to_string(hex=True)` returns lowercase `#rrggbb`; we route
    it through `validate_hex_color` which checks the regex (case-insensitive)
    and then we uppercase to match the repo-wide convention used by
    schema_renderer's `Palette.validate_hex_color` callers.
    """
    raw = color.convert("srgb").fit().to_string(hex=True)  # e.g. "#1e3a5f"
    return validate_hex_color(raw).upper()


def _oklch_lightness_search(
    fg_hex: str,
    bg_hex: str,
    *,
    target: float,
    iterations: int = 12,
) -> str | None:
    """Binary-search OKLCH lightness of `fg_hex` until `wcag_ratio >= target`.

    Preserves hue + chroma. Returns the passing hex (minimal perturbation
    from the original), or None if no lightness in [0.0, 1.0] satisfies
    the target.

    Strategy:
      * Measure the bg's OKLAB lightness. If bg is dark, push fg toward 1.0
        (lighter). If bg is light, push fg toward 0.0 (darker).
      * After finding a passing midpoint, walk the search window BACK
        toward the original lightness so the result is the minimal nudge.
    """
    original = Color(fg_hex).convert("oklch")
    orig_l = float(original["lightness"])

    bg_l = float(Color(bg_hex).convert("oklab")["lightness"])
    # If bg is "dark", push fg lighter (toward 1.0); else push darker (toward 0.0).
    if bg_l < 0.5:
        lo, hi = orig_l, 1.0
    else:
        lo, hi = 0.0, orig_l

    best: str | None = None

    for _ in range(iterations):
        mid = (lo + hi) / 2.0
        c = Color(fg_hex).convert("oklch")
        c["lightness"] = mid
        trial = _normalize_oklch_output(c)
        if wcag_ratio(trial, bg_hex) >= target:
            best = trial
            # Walk BACK toward original (minimal perturbation)
            if bg_l < 0.5:
                hi = mid
            else:
                lo = mid
        else:
            if bg_l < 0.5:
                lo = mid
            else:
                hi = mid
    return best


def remediate(
    fg_hex: str,
    bg_hex: str,
    *,
    neutrals: tuple[str, str],
    large_text: bool = False,
) -> tuple[str, str]:
    """Return (remediated_fg, note).

    `neutrals = (dark_hex, light_hex)` -- typically from the kit palette.

    Strategy:
      1. If already passing -> `(fg_hex, "pass")`.
      2. Opposite neutral (farther from bg's OKLAB lightness).
      3. Other neutral (fallback).
      4. OKLCH lightness binary-search, preserving hue.
      5. Nothing worked -> `(fg_hex, "FAIL: no AA-compliant fg found")`.
    """
    if passes_aa(fg_hex, bg_hex, large_text=large_text):
        return fg_hex, "pass"

    dark, light = neutrals
    bg_lightness = float(Color(bg_hex).convert("oklab")["lightness"])
    # Pick the neutral farther from bg (dark bg -> light fg; light bg -> dark fg)
    candidate = dark if bg_lightness > 0.5 else light
    if passes_aa(candidate, bg_hex, large_text=large_text):
        label = "neutral_dark" if candidate == dark else "neutral_light"
        return validate_hex_color(candidate), f"swapped to {label}"

    # Try the other neutral just in case
    other = light if candidate == dark else dark
    if passes_aa(other, bg_hex, large_text=large_text):
        label = "neutral_light" if other == light else "neutral_dark"
        return validate_hex_color(other), f"swapped to {label} (fallback)"

    # OKLCH lightness nudge on the original fg, preserving hue
    target = _AA_LARGE if large_text else _AA_BODY
    nudged = _oklch_lightness_search(fg_hex, bg_hex, target=target)
    if nudged is not None:
        return nudged, f"OKLCH lightness nudge to {nudged}"

    return fg_hex, "FAIL: no AA-compliant fg found"


def ensure_aa(
    fg_hex: str,
    bg_hex: str,
    *,
    palette_neutrals: tuple[str, str],
    large_text: bool = False,
) -> tuple[str, str | None]:
    """Ergonomic wrapper.

    Returns `(final_fg, remediation_note_or_None)`:
      * `(fg_hex, None)` when already passing.
      * `(new_fg, note)` when remediated successfully.
      * `(fg_hex, "FAIL: ...")` when nothing passes.
    """
    result, note = remediate(
        fg_hex, bg_hex, neutrals=palette_neutrals, large_text=large_text
    )
    if note == "pass":
        return result, None
    return result, note


# ---- Models (round-trip to JSON via AuditReport) ------------------------


class ContrastPair(BaseModel):
    """One fg/bg pair with its ratio, level, and optional remediation note."""

    model_config = ConfigDict(extra="forbid")

    fg: str
    bg: str
    ratio: float = Field(ge=1.0, le=21.0)
    level: Level
    remediation: str | None = None

    # Optional location context so the audit report can point back to the region
    panel: str | None = None
    content_key: str | None = None

    @field_validator("fg", "bg")
    @classmethod
    def _validate_hex(cls, v: str) -> str:
        # validate_hex_color raises on malformed input; uppercase for
        # consistent serialization (schema_renderer's hex fields also
        # normalize to uppercase via the same helper at call sites).
        return validate_hex_color(v).upper()


class ContrastReport(BaseModel):
    """Aggregate of every ContrastPair evaluated in a render."""

    model_config = ConfigDict(extra="forbid")

    pairs: list[ContrastPair] = Field(default_factory=list)

    @property
    def overall_aa_pass(self) -> bool:
        """True iff every pair is AA or AAA (no FAILs)."""
        return all(p.level in ("AA", "AAA") for p in self.pairs)

    def fails(self) -> list[ContrastPair]:
        """Return every pair whose level is FAIL."""
        return [p for p in self.pairs if p.level == "FAIL"]
