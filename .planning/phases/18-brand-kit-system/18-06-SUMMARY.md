---
phase: 18-brand-kit-system
plan: 06
subsystem: brand-kit
tags: [brand-kit, audit, whitespace, contrast, density, iteration-loop, remediation]

# Dependency graph
requires:
  - phase: 18-01
    provides: BrandKitAuditError (errors.py augmented with cycles/remaining_issues kwargs)
  - phase: 18-03
    provides: ContrastPair, ContrastReport, wcag_ratio, classify_level (AA math)
  - phase: 18-05
    provides: apply_brand_kit (used by remediate_contrast for opposite-neutral swap)
  - existing
    provides: TemplateSchema, PanelSchema, TextElement, BulletsElement, BrochureContent, chars_per_line
provides:
  - audit_render(content, template, rendered_png, *, side, cycle) -> AuditReport
  - iterate_audit_loop(...) with default-composite remediate (kit + regenerate_fn)
  - remediate_contrast(content, template, audit, *, kit) -> (content, template)
  - remediate_density(content, template, audit, *, regenerate_fn) -> (content, template)
  - AuditReport, AuditIssue Pydantic models (JSON-round-trip for future persistence)
affects: [18-07, 18-08]

# Tech tracking
tech-stack:
  added: []  # no new deps — audit is pure PIL + pydantic + structlog + stdlib
  patterns:
    - "Panel-order-indexed sheet cropping: _OUTSIDE_ORDER = (back_cover, tuck_flap, front_cover); _INSIDE_ORDER = (inner_left, inner_center, inner_right)"
    - "Downsampled whitespace histogram (1/15 per dim, ~225x pixel reduction) for O(panel_area/225) bg-tolerance match"
    - "tobytes() pixel iteration (Pillow 14 forward-compat) instead of deprecated getdata()"
    - "Default-composite remediate factory (_make_default_remediate) returns None when caller supplied no kit AND no regenerate_fn"
    - "Threat guard: reject PNGs > 50 MP with BrandKitAuditError before Image.open (T-18-AUDIT-01)"
    - "Soft-fail per-element contrast: log+continue inside audit_render so one malformed color doesn't nuke the whole report"

key-files:
  created:
    - flyer_generator/brand_kit/audit.py (655 lines)
    - tests/brand_kit/test_audit.py (20 tests, 445 lines)
  modified: []  # __init__.py intentionally NOT touched (B1)

key-decisions:
  - "Remediation scope locked to contrast-swap + text_gen regen per CONTEXT.md §'Audit loop remediation scope'. Edit-in-place LLM rewrites are explicitly deferred to a later phase."
  - "Arg-order regression guard: test_remediate_contrast_swaps_failing_text asserts a CONCRETE palette change (new_template.palette.accent_default != t.palette.accent_default) so a future refactor that flips apply_brand_kit(template, kit) to apply_brand_kit(kit, template) fails pytest immediately, not silently."
  - "Whitespace threshold = 0.85 (panels above this ratio get a 'warn' issue); density-low threshold = 0.50 (content_keys below this get an 'info' issue). Both are tunable constants at module top; calibrated to match RESEARCH.md Pattern 6."
  - "tuck_flap is exempt from the whitespace WARN — it's typically a narrow full-bleed accent panel in all 13 templates and would always trip the threshold."
  - "remediate_density builds tighter_budgets from the current resolved length: target = max(24, round(len(resolved) * 1.25)). This targets ~80% fill of the new budget without knowing the original template budget — the target is a character count, not a budget expansion."
  - "iterate_audit_loop composes remediate_contrast + remediate_density into a single default callback when the caller passes kit + regenerate_fn (SC-6). Passing an explicit remediate always wins."
  - "Direct-module imports ONLY throughout audit + test files (B1). Plan 07 owns the consolidated __init__ re-export block."
  - "BulletsElement font_size sourced from template.typography.bullet_size via getattr-with-fallback (W16). The 32 fallback is only hit on synthetic test fixtures — all real templates populate typography.bullet_size."

patterns-established:
  - "Pattern 1: Structured-verdict audit — every rendered sheet produces a JSON-round-trippable AuditReport. Future phases can persist reports for analytics without reshaping the data."
  - "Pattern 2: Composable remediate closures — the audit module exports concrete remediation primitives (remediate_contrast, remediate_density) plus an orchestrator that composes them. Callers can override with a custom remediate or opt into the default by passing kit + regenerate_fn."
  - "Pattern 3: Shape-stacking deferred — _panel_bg_hex uses the panel's background SolidFill as a first-pass approximation. True per-text-region bg (walking shape z-order + opacity) is flagged in RESEARCH.md as Phase 19 work."

requirements-completed: [HANDOFF-BK-AUDIT]

# Metrics
duration: ~30min
completed: 2026-04-20
---

# Phase 18 Plan 06: Post-Render Audit + Iterate Loop Summary

**Post-render `audit_render` produces a structured `AuditReport` (whitespace per panel, contrast pairs per text region, density per content_key, severity-tagged issues). `iterate_audit_loop` re-renders up to 3 cycles with bounded remediation (opposite-neutral contrast swap + tighter-budget text_gen regen — no edit-in-place). Both W10 remediation closures are exported as first-class primitives and auto-composed into the loop's default callback when the caller supplies `kit` + `regenerate_fn`.**

## Performance

- **Duration:** ~30 min
- **Tasks:** 2
- **Files created:** 2 (1 source, 1 test)
- **Lines added:** 1100 (655 impl + 445 tests)
- **Tests:** 20 new (all pass), 795 full suite (no regressions)

## Accomplishments

- `audit_render(content, template, rendered_png_bytes, *, side, cycle) -> AuditReport` ships with three audit dimensions and one severity-tagged issue stream.
- Whitespace: panel-order-indexed crop (`back_cover/tuck_flap/front_cover` outside; `inner_left/inner_center/inner_right` inside), downsampled 15× per dimension for O(~225× fewer pixels) bg-tolerance match, `Image.tobytes()` iteration (Pillow 14 forward-compat).
- Contrast: walks every `TextElement` + `BulletsElement` in the template, builds a `ContrastPair` per (text color, panel bg), classifies via `wcag_ratio` + `classify_level`, flags FAILs as `severity="error"` issues.
- Density: resolves each non-static `content_key` via `BrochureContent.resolve_key`, computes a character budget via `chars_per_line × max_lines`, flags `< 50%` fills as `severity="info"` issues.
- `AuditReport.is_clean` returns True when no contrast FAIL and no WARN/ERROR issues — info-severity density flags do NOT block the clean verdict.
- `iterate_audit_loop` runs up to `max_cycles=3`, short-circuits on `is_clean`, and composes `remediate_contrast` + `remediate_density` into a default callback when the caller passes `kit` + `regenerate_fn` (SC-6 satisfied).
- `strict=True` raises `BrandKitAuditError(cycles=N, remaining_issues=[...])` on exhaustion; `strict=False` returns the last report unchanged.
- **W10a** `remediate_contrast`: swaps the kit's `primary` to its `neutral_dark` and re-applies via `apply_brand_kit(template, swapped_kit)`. The applier's existing inline AA guard on neutral_dark/neutral_light then picks the opposite neutral for every body-text pair.
- **W10b** `remediate_density`: computes `tighter_budgets[key] = max(24, round(len(resolved) * 1.25))` for each under-filled key and invokes the caller's `regenerate_fn`. The audit module itself does NOT call any LLM — Plan 07's integration wires `regenerate_fn` via `text_gen.generate_content_from_prompt` with reduced char budgets.
- **Threat guard (T-18-AUDIT-01):** PNGs exceeding 50 MP are rejected with `BrandKitAuditError("rendered PNG exceeds 50 MP cap", cycles, width, height)` before Pillow decodes them (DoS mitigation for untrusted bytes).
- **W16:** `_collect_text_elements` sources BulletsElement font_size from `template.typography.bullet_size` via `getattr(..., "bullet_size", 32)`; the 32 fallback is unreachable in production (all 13 templates populate the field).
- Arg-order regression guard: `test_remediate_contrast_swaps_failing_text` asserts a concrete palette change (`new_template.palette.accent_default != t.palette.accent_default`) so a future refactor that flips `apply_brand_kit(template, kit)` to `apply_brand_kit(kit, template)` fails pytest immediately, not silently.
- 20 direct-module tests pass; full suite (795 tests) passes — no regressions.

## Task Commits

1. **Task 2 (RED): Author `tests/brand_kit/test_audit.py`** — `0044f94` (test)
2. **Task 1 (GREEN): Implement `flyer_generator/brand_kit/audit.py`** — `b5571cf` (feat)

TDD gate order: the failing test file was committed first (RED), then the implementation (GREEN). No REFACTOR commit was needed — the single fix applied during GREEN (`tobytes()` in place of deprecated `getdata()`) was bundled into the GREEN commit since it was author-time polish, not post-GREEN cleanup.

## Audit Thresholds (tunable module constants)

| Constant | Value | Meaning |
|----------|-------|---------|
| `_WHITESPACE_THRESHOLD` | `0.85` | Panels (except tuck_flap) above this ratio get a `warn` issue |
| `_DENSITY_LOW_THRESHOLD` | `0.50` | content_keys below this fill fraction get an `info` issue |
| `_TOLERANCE` | `12` (0-255) | Per-channel distance-from-bg for "near-bg pixel" classification |
| `_MAX_IMAGE_MP` | `50_000_000` | OOM guard: reject PNGs larger than 50 megapixels |

## Panel-Order Assumptions (sheet cropping)

The audit crops a rendered sheet into thirds (left/middle/right) based on a fixed panel order per side:

| Side | Left third | Middle third | Right third |
|------|-----------|--------------|-------------|
| `outside` | `back_cover` | `tuck_flap` | `front_cover` |
| `inside` | `inner_left` | `inner_center` | `inner_right` |

This assumes the renderer composes sheets in that panel order, which matches the current `render_schema_brochure` sheet-builder output. If a future renderer change reshuffles panel order within a sheet, the `_OUTSIDE_ORDER`/`_INSIDE_ORDER` constants at the top of `audit.py` are the single point of adjustment.

## Remediation Closure Composition

`iterate_audit_loop` accepts either an explicit `remediate` callback, or `kit` + `regenerate_fn` kwargs. When both are omitted and no explicit remediate is passed, the loop runs detect-only (render → audit → return).

```text
remediate argument       | kit | regenerate_fn | loop behavior
-------------------------+-----+---------------+-----------------------------------------
explicit callback        |  *  |       *       | Uses the explicit callback verbatim
None                     | yes |      yes      | Composes remediate_contrast + remediate_density
None                     | yes |      no       | Contrast-only remediation (density detected but not fixed)
None                     | no  |      yes      | Density-only remediation (contrast detected but not fixed)
None                     | no  |      no       | Detect-only; break after first non-clean cycle
```

The default composite, when fired, runs remediate_contrast first (it's deterministic and cheap — one `apply_brand_kit` call with a mutated kit), then remediate_density (one LLM round-trip via the caller's `regenerate_fn`). Neither is invoked when the relevant issue category is absent from the audit report.

## B1 / B3 Compliance

- **B1:** `flyer_generator/brand_kit/__init__.py` is UNCHANGED by this plan — verified by `git diff 962192022..HEAD -- flyer_generator/brand_kit/__init__.py` returning empty. Plan 07 owns the consolidated re-export block; every intra-phase test uses direct-module imports (`from flyer_generator.brand_kit.audit import ...`). Grep confirms zero `from flyer_generator.brand_kit import` lines at the package level in `test_audit.py`.
- **B3:** `BrandKitAuditError` is imported from `flyer_generator.errors` (Plan 01's augmented hierarchy), not from a brand_kit local shim. The `cycles` + `remaining_issues` kwargs added by Plan 01 are used verbatim in the loop's exhaustion raise.

## Known Approximation — Shape-Stacking Deferred (Phase 19)

`_panel_bg_hex` returns the panel's `background` fill color as a first-pass approximation of "effective bg for every text region in this panel". The correct answer requires walking the panel's shape tree by z-order + opacity and computing the alpha-composite bg under each text region's bbox — which is Phase 19 work (flagged in RESEARCH.md as "shape-stacking deferred").

Impact for Phase 18: a text region layered over a non-default shape (e.g. a gold ribbon on top of the #FAFAF7 panel bg) has its contrast computed against the panel bg, not the ribbon. False negatives are possible (text that actually fails AA because of the ribbon is reported as passing). Mitigation: Phase 18's applier (Plan 05) constrains palette swaps to AA-safe neutral_dark/neutral_light pairs, so the most common shape-overlay case (body text on panel bg) is covered. Decorative ribbons with static colors remain a known gap until Phase 19.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Forward-Compatibility] Pillow 14 deprecation of `Image.Image.getdata`**
- **Found during:** Task 1 GREEN — first test run surfaced 45 `DeprecationWarning` lines.
- **Issue:** The plan's reference snippet used `panel_small.getdata()` to iterate per-pixel tuples; Pillow 14 (2027-10-15) removes that method.
- **Fix:** Switched to `panel_small.tobytes()` + byte-triple iteration — forward-compatible, ~identical iteration cost, produces identical whitespace ratios (verified by test_audit_whitespace_empty_sheet / _partial_fill still passing).
- **Files modified:** `flyer_generator/brand_kit/audit.py` (single function: `_panel_whitespace_ratio`)
- **Commit:** folded into GREEN commit `b5571cf` (not a separate refactor commit — applied before first commit to keep the history clean).

**2. [Rule 2 — Correctness] BulletsElement font_size override respected**
- **Found during:** Task 1 GREEN — reviewing `_collect_text_elements` against the editorial_classic schema JSON.
- **Issue:** Several templates (e.g. editorial_classic) set a per-element `font_size` on `BulletsElement` (e.g. `font_size: 28` in the inner_left bullet block). The plan's reference snippet always used `template.typography.bullet_size` for BulletsElement, ignoring the per-element override and producing wrong density math for any template that sizes its bullets per panel.
- **Fix:** `_collect_text_elements` now prefers `el.font_size` when the element supplies one; falls back to `template.typography.bullet_size` when it's None; falls back to the literal 32 only when the Typography model itself lacks the field (synthetic fixtures only).
- **Files modified:** `flyer_generator/brand_kit/audit.py` (single function: `_collect_text_elements`)
- **Commit:** folded into GREEN commit `b5571cf`.

## Self-Check: PASSED

- `flyer_generator/brand_kit/audit.py` — FOUND
- `tests/brand_kit/test_audit.py` — FOUND
- Commit `0044f94` (RED test) — FOUND
- Commit `b5571cf` (GREEN impl) — FOUND
- `flyer_generator/brand_kit/__init__.py` diff vs. base `9621920` — EMPTY (B1 compliance verified)
- `pytest tests/brand_kit/test_audit.py -q` — 20 passed
- `pytest tests/ -q` — 795 passed (no regressions)
- Acceptance greps all return ≥1 (AuditReport, AuditIssue, audit_render, iterate_audit_loop, remediate_contrast, remediate_density, _make_default_remediate, is_clean, W16 bullet_size lookup)
- Tests: 20 total (≥15 required), includes W10a + W10b coverage; zero package-level `from flyer_generator.brand_kit import` lines in test file
