---
phase: 18-brand-kit-system
plan: 03
subsystem: brand_kit
tags: [brand-kit, contrast, wcag, color-science]
dependency_graph:
  requires:
    - flyer_generator/brochure/models.py::validate_hex_color
    - wcag-contrast-ratio>=0.9
    - coloraide>=8,<9
    - pydantic>=2.13.1
  provides:
    - flyer_generator/brand_kit/contrast.py (wcag_ratio, passes_aa, passes_aaa,
      classify_level, remediate, ensure_aa, _hex_to_floats)
    - flyer_generator/brand_kit/contrast.py::ContrastPair
    - flyer_generator/brand_kit/contrast.py::ContrastReport
  affects:
    - Plan 05 applier (consumes remediate + passes_aa for derived-palette validation)
    - Plan 06 audit (consumes ContrastReport + ensure_aa for per-region validation)
    - Plan 07 smoke test (asserts overall_aa_pass on final render)
tech_stack:
  added:
    - wcag-contrast-ratio (ratio math; pinned 0.9, API stable since 2015)
    - coloraide 8.x (OKLCH traversal for hue-preserving lightness search)
  patterns:
    - Pure-function module (analog flyer_generator/brochure/schema_renderer/text_fit.py)
    - Pydantic v2 model_config = ConfigDict(extra="forbid") + @field_validator
    - Input validation at trust boundary via validate_hex_color
key_files:
  created:
    - flyer_generator/brand_kit/contrast.py
    - tests/brand_kit/test_contrast.py
  modified: []
decisions:
  - Direct library rgb call isolated to a single site (_wcag.rgb inside
    wcag_ratio) -- grep-enforced to prevent future int-tuple leaks.
  - ContrastPair normalizes hex input to uppercase #RRGGBB for stable
    JSON serialization.
  - Remediation strategy is strictly ordered pass -> opposite neutral ->
    other neutral (fallback) -> OKLCH lightness nudge -> FAIL note.
  - OKLCH binary search is bounded to 12 iterations (~0.02 precision) and
    walks the search window BACK toward the original lightness once a
    passing midpoint is found, minimizing perturbation.
  - remediate() never raises; FAIL is returned as a note so callers can
    log-and-continue or escalate to BrandKitContrastError at their
    discretion.
  - Package-root flyer_generator/brand_kit/__init__.py intentionally NOT
    created (B1 rule; Plan 07 owns consolidation).
metrics:
  duration: "5m44s"
  completed: "2026-04-21T00:18:37Z"
  tasks: 2
  files: 2
  tests_added: 26
  tests_passing: 691
---

# Phase 18 Plan 03: Contrast Module Summary

WCAG 2.1 contrast validation + auto-remediation as a pure-function module,
with JSON-round-trippable `ContrastPair`/`ContrastReport` Pydantic models.

## API Exports

Eight callables + two models in
`flyer_generator.brand_kit.contrast` (DIRECT-MODULE imports only):

| Export | Kind | Purpose |
|--------|------|---------|
| `wcag_ratio(fg_hex, bg_hex)` | fn | WCAG 2.1 contrast ratio (1.0-21.0) |
| `passes_aa(fg_hex, bg_hex, *, large_text=False)` | fn | True iff ratio >= 4.5 body / 3.0 large |
| `passes_aaa(fg_hex, bg_hex, *, large_text=False)` | fn | True iff ratio >= 7.0 body / 4.5 large |
| `classify_level(fg_hex, bg_hex, *, large_text=False)` | fn | Literal "AAA"/"AA"/"FAIL" |
| `remediate(fg_hex, bg_hex, *, neutrals, large_text=False)` | fn | `(new_fg, note)` with strategy label |
| `ensure_aa(fg_hex, bg_hex, *, palette_neutrals, large_text=False)` | fn | `(final_fg, note_or_None)` wrapper |
| `_hex_to_floats(hex_color)` | private fn | `#RRGGBB` -> (r, g, b) floats 0.0-1.0 |
| `ContrastPair` | Pydantic model | `{fg, bg, ratio, level, remediation?, panel?, content_key?}` |
| `ContrastReport` | Pydantic model | `{pairs: list[ContrastPair]}` + `overall_aa_pass`, `fails()` |

## Hex-to-Floats Pitfall Mitigation

`wcag-contrast-ratio.rgb()` REQUIRES float triples in 0.0-1.0. Passing int
triples 0-255 silently produces nonsense ratios (pitfall 2 in RESEARCH.md).

The module mitigates via:

1. A single `_hex_to_floats()` helper that validates the hex string via
   `validate_hex_color` (regex-enforced `#RRGGBB`) and divides each channel
   by 255.0.
2. Every library ratio call is routed through the `wcag_ratio()` wrapper,
   which calls `_hex_to_floats()` on both inputs.
3. A grep-enforced acceptance criterion in the plan ensures exactly one
   match of the internal library rgb pattern in the whole file.

This isolation means no future caller can accidentally pass ints.

## OKLCH Binary-Search Convergence

When both neutrals fail, `_oklch_lightness_search` preserves hue + chroma
and binary-searches the lightness axis of the OKLCH representation:

1. Measure bg's OKLAB lightness.
2. If bg is "dark" (lightness < 0.5), walk fg toward 1.0 (lighter).
   Otherwise walk toward 0.0 (darker).
3. For each midpoint, re-convert to sRGB, compute the ratio, and:
   * If the ratio meets target: record as `best`, then walk the search
     window BACK toward the original lightness (minimal perturbation).
   * If not: walk further from the original.
4. Bounded to 12 iterations (~`2^-12` = ~0.00024 lightness precision).

Return `None` if no lightness in `[0.0, 1.0]` meets the target -- e.g. a
saturated mid-chroma hue with a same-lightness background where no
hue-preserving nudge helps. Caller (`remediate`) falls through to the FAIL
note in that case.

## Direct-Module Import Strategy (B1)

Per checker iteration 1 (B1), this plan must NOT write to
`flyer_generator/brand_kit/__init__.py`. The package root stays a stub
(or absent, per current wave-1 worktree state) until Plan 07 consolidates
re-exports.

Every test uses direct-module imports:
```python
from flyer_generator.brand_kit.contrast import (
    ContrastPair, ContrastReport, _hex_to_floats, classify_level,
    ensure_aa, passes_aa, passes_aaa, remediate, wcag_ratio,
)
```

`grep -c '^from flyer_generator.brand_kit import' tests/brand_kit/test_contrast.py`
returns `0` (verified).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] passes_aaa counter-example test used wrong hex**
- **Found during:** Task 2 pre-write ratio check
- **Issue:** Plan's draft test asserted `passes_aaa("#555555", "#FFFFFF") is False`, but the empirical ratio for `#555555` on white is `7.455` via `wcag-contrast-ratio 0.9`, which meets the 7.0 AAA body threshold. The assertion would have failed.
- **Fix:** Substituted `#666666` (empirical ratio `5.742`), which clearly fails AAA body (< 7.0) while still passing AA body (>= 4.5).
- **Files modified:** `tests/brand_kit/test_contrast.py`
- **Commit:** `5ed639c`

**2. [Rule 1 - Bug] Dark-bg remediation test fg already passed AA**
- **Found during:** Task 2 pre-write ratio check
- **Issue:** Plan's draft `test_remediate_swaps_to_opposite_neutral_for_dark_bg` used `fg="#808080"` on `bg="#111111"`. The empirical ratio is `4.781`, which already passes AA body (>= 4.5) -- so `remediate()` would return `("#808080", "pass")` unchanged, and the assertion `"neutral_light" in note or "OKLCH" in note` would fail because `note == "pass"`.
- **Fix:** Substituted `fg="#555555"` (empirical ratio `2.533` on `#111111`, clearly fails AA), so remediation actually fires and swaps to the light neutral.
- **Files modified:** `tests/brand_kit/test_contrast.py`
- **Commit:** `5ed639c`

**3. [Rule 3 - Blocker] Missing runtime dependencies**
- **Found during:** Task 1 environment check
- **Issue:** Neither `wcag-contrast-ratio` nor `coloraide` was installed in the project venv. `python -c "import wcag_contrast_ratio"` raised `ModuleNotFoundError`. These deps are slated for pyproject.toml in Plan 01 / Plan 04 but this plan (Wave 1, parallel with Plan 01) needs them at runtime.
- **Fix:** Installed both packages into the existing `.venv` site-packages: `wcag-contrast-ratio==0.9`, `coloraide==8.8.1`, `typing-extensions==4.15.0`. No `pyproject.toml` edit is made by this plan -- dependency-declaration ownership stays with the dedicated plan.
- **Files modified:** none in repo (venv-only install)
- **Commit:** none (install is an environment-setup step)

### Module docstring edit

Initial docstring contained the literal pattern `_wcag.rgb(...)` which caused `grep -c "_wcag\.rgb\|wcag_contrast_ratio\.rgb"` to return 2, tripping the "exactly one match" acceptance criterion. Rewrote the docstring to describe the isolation rule without containing the grepped pattern. The substantive content is preserved.

## Known Edge Cases

1. **Mid-gray on mid-gray, neutrals equidistant.** When `fg ~= bg ~= mid` and both neutrals are also close to mid-gray (e.g. `#777` + `#888`), no neutral swap passes AA, and the OKLCH search may also fail (every lightness in [0, 1] may still give ratio < 4.5 because the underlying issue is the bg is at the ratio-indifference point). `remediate()` returns `(fg, "FAIL: no AA-compliant fg found")` -- caller must decide. The test `test_remediate_returns_fail_note_when_no_solution` asserts this behavior tolerantly: either OKLCH found a passing value OR the FAIL note is returned; both are acceptable outcomes.

2. **coloraide hex output casing.** `coloraide.Color.convert('srgb').to_string(hex=True)` emits lowercase `#rrggbb`. The module normalizes via `_normalize_oklch_output()` which runs the output through `validate_hex_color` (regex case-insensitive) and then `.upper()`, so all returned hexes from remediation are uppercase `#RRGGBB` -- matching the repo-wide convention.

3. **ContrastPair hex normalization.** The `@field_validator` on `fg`/`bg` uppercases after validation. Callers passing lowercase hex (e.g. from coloraide output) will get uppercase back from `ContrastPair(...).fg`. The test `test_contrast_pair_hex_normalized` pins this behavior.

4. **Ratio bounds on ContrastPair.** `ratio: float = Field(ge=1.0, le=21.0)`. Real WCAG ratios are bounded `[1.0, 21.0]` by construction, but explicit bounds prevent garbage ratios from flowing into the audit report.

## Verification Status

| Check | Result |
|-------|--------|
| `pytest tests/brand_kit/test_contrast.py -q` | 26 passed in 1.20s |
| `pytest tests/ -q` (full suite, no regressions) | 691 passed in 37.38s |
| `python -c "from flyer_generator.brand_kit.contrast import ..."` | imports succeed |
| `grep -c "def wcag_ratio\|def passes_aa\|def classify_level\|def remediate\|def ensure_aa" flyer_generator/brand_kit/contrast.py` | all funcs present |
| `grep -c "class ContrastPair\|class ContrastReport" flyer_generator/brand_kit/contrast.py` | both models present |
| `grep -c "_wcag\.rgb\|wcag_contrast_ratio\.rgb" flyer_generator/brand_kit/contrast.py` | 1 (single isolated call site) |
| `grep -c "^from flyer_generator.brand_kit import" tests/brand_kit/test_contrast.py` | 0 (B1 compliance) |
| `grep -c "def test_" tests/brand_kit/test_contrast.py` | 26 (>=20 required) |
| `ls flyer_generator/brand_kit/__init__.py` | absent (B1: plan forbids writing it) |

## Commits

| Hash | Message |
|------|---------|
| `aa4dbd9` | feat(18-03): add brand_kit contrast module with WCAG ratio + remediation |
| `5ed639c` | test(18-03): add brand_kit contrast test suite with 26 cases |

## Threat Model Compliance

| Threat | Mitigation | Status |
|--------|------------|--------|
| T-18-CONTRAST-01 Input validation (garbage hex) | `_hex_to_floats` routes every hex through `validate_hex_color`; invalid -> `ValueError` | implemented |
| T-18-CONTRAST-02 Int-tuple leak to `.rgb()` | All calls routed through `wcag_ratio` helper; grep-enforced single site | implemented + enforced |
| T-18-CONTRAST-03 OKLCH search divergence | Loop bounded to 12 iterations; always returns `(str \| None, ...)` without raise | implemented |

## Self-Check: PASSED

- `flyer_generator/brand_kit/contrast.py` — FOUND
- `tests/brand_kit/test_contrast.py` — FOUND
- Commit `aa4dbd9` — FOUND in git log
- Commit `5ed639c` — FOUND in git log
- `flyer_generator/brand_kit/__init__.py` — absent (as mandated by B1)
