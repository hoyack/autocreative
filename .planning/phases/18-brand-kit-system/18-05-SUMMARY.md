---
phase: 18-brand-kit-system
plan: 05
subsystem: brand-kit
tags: [brand-kit, applier, template-transform, contrast-validation, pydantic, immutable]

# Dependency graph
requires:
  - phase: 18-01
    provides: resolve_kit_dir (storage path resolver)
  - phase: 18-02
    provides: BrandKit, BrandPalette, BrandTypography, BrandLogo, ColorUsage (data contracts)
  - phase: 18-03
    provides: ensure_aa, passes_aa, wcag_ratio (AA contrast guardrail)
provides:
  - apply_brand_kit(template, kit, *, slug, base_dir) -> (TemplateSchema, bytes | None)
  - Immutable template transform via nested model_copy(update={...})
  - 7-field typography size scaling by kit.size_multiplier
  - Inline AA guardrail on neutral_dark/neutral_light pair with auto-remediation
  - Path-traversal-safe primary-logo byte loading
affects: [18-06, 18-07]

# Tech tracking
tech-stack:
  added: []  # no new deps — applier is pure stdlib + pydantic + structlog (existing)
  patterns:
    - "Nested model_copy(update={...}) at field granularity — mirrors renderer.py:752-759 accent_override"
    - "resolve().relative_to(kit_dir) path-traversal containment check for disk reads"
    - "Epsilon guard (abs(m-1.0) > 1e-9) for strict no-op on size_multiplier=1.0"
    - "structlog warning-per-correction for AA auto-remediations"

key-files:
  created:
    - flyer_generator/brand_kit/applier.py (219 lines)
    - tests/brand_kit/test_applier.py (22 tests, 425 lines)
  modified: []  # __init__.py intentionally NOT touched (B1)

key-decisions:
  - "Accent left verbatim through AA guardrail — truth invariant 'accent_default == kit.palette.primary.hex' is load-bearing; accent-vs-text contrast is audit subsystem's (Plan 04/06) responsibility, not the applier's."
  - "Logo loading requires explicit `slug` argument; without it, return None (no way to resolve kit_dir without the slug)."
  - "Fall back to kit.logos[0] when no variant='primary' exists (SVG marks / mono-only kits still produce usable logo bytes)."
  - "Direct-module imports throughout tests (B1 honored) — Plan 07 will assemble the consolidated public API."

patterns-established:
  - "Pattern 1: Pydantic immutable transforms — always return via model_copy(update=...), never mutate in place. Verified by before/after model_dump_json() equality test."
  - "Pattern 2: Partial-kit tolerance — every optional field on BrandKit (palette, typography, logos) has a 'None/empty -> keep template default' path so scrapers can write partial kits without breaking downstream renders."
  - "Pattern 3: Pixel-size vs character-budget split — *_size fields scale with size_multiplier; body_max_chars_per_line does NOT (it's a count, not a size)."

requirements-completed: [HANDOFF-BK-APPLIER]

# Metrics
duration: ~25min
completed: 2026-04-20
---

# Phase 18 Plan 05: Applier Summary

**Immutable `apply_brand_kit(template, kit) -> (new_template, logo_bytes)` with 7-field typography scaling, inline AA guardrail on body-text neutrals, and path-traversal-safe primary-logo read.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-04-20T19:28:00Z
- **Completed:** 2026-04-20T19:53:00Z
- **Tasks:** 2
- **Files created:** 2 (1 source, 1 test)

## Accomplishments

- `apply_brand_kit(template, kit, *, slug, base_dir)` ships as the single entry point for Plan 07's CLI integration.
- Nested `model_copy(update=...)` at palette + typography field granularity mirrors the existing `renderer.py:752-759` `accent_override` pattern (no new transform idiom introduced).
- Seven `*_size` Typography fields scale by `kit.size_multiplier`: `cover_title_size`, `cover_subtitle_size`, `heading_size`, `body_size`, `body_line_height`, `bullet_size`, `bullet_line_height`. `body_max_chars_per_line` is explicitly NOT scaled.
- Inline AA guardrail on the canonical body-on-panel pair `(neutral_dark, neutral_light)` via `contrast.ensure_aa`; one `logger.warning` per correction so every swap is auditable.
- Primary-logo byte loader is path-traversal-safe (T-18-APPLIER-01): `.resolve()` + `relative_to(kit_dir)` blocks `../../../etc/passwd`-style paths and skip-with-warning for missing files.
- 22 direct-module tests pass; full suite (749 tests) passes — no regressions.

## Task Commits

1. **Task 1: Implement `flyer_generator/brand_kit/applier.py`** — `7011343` (feat)
2. **Task 2: Author `tests/brand_kit/test_applier.py`** — `d903217` (test)

## Files Created

- `flyer_generator/brand_kit/applier.py` — `apply_brand_kit` + three private helpers (`_build_palette`, `_build_typography`, `_load_primary_logo_bytes`). 219 lines. No `__init__.py` re-export (B1).
- `tests/brand_kit/test_applier.py` — 22 tests covering palette swap (5), typography (6), no-mutation (1), logo bytes (7), AA guardrail (2), and `.brand-kit-template.json` integration (1). 425 lines. 0 package-root imports (B1).

## AA Guardrail Pairs Validated

Per the `<output>` section of the plan, the applier validates exactly **one** pair inline:

| Pair | Text size | Threshold | Remediation on fail |
|------|-----------|-----------|---------------------|
| `neutral_dark` on `neutral_light` | body (4.5) | AA | `ensure_aa` → opposite neutral or OKLCH lightness nudge |

The plan's `<action>` scaffold also included a second pair (`accent on neutral_light`, large-text 3.0), but the `must_haves.truths` explicitly require that `template.palette.accent_default` in the returned template equals `kit.palette.primary.hex` verbatim. Those two requirements are contradictory: silently remediating accent would break the truth invariant that downstream users depend on. The truth wins — accent flows through verbatim, and accent-vs-text contrast concerns are handled by the render-time audit subsystem (Plans 04 / 06).

## Decisions Made

1. **Accent guardrail removed** — see Deviations §1 below. Truth invariant "accent_default equals kit.palette.primary.hex" beats the scaffold's over-eager remediation.
2. **`slug is None` short-circuit for logo loading** — without a slug there's no way to resolve `kit_dir`, so return `None` rather than raise. Tests assert this path.
3. **First-logo fallback when no `variant='primary'`** — SVG mark-only kits still produce usable bytes via `next(... kit.logos[0])`.
4. **Epsilon guard for `size_multiplier=1.0`** — `abs(m - 1.0) > 1e-9` means the typography pass is a strict no-op and doesn't pointlessly rewrite every size field.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Spec Reconciliation] Removed accent AA guardrail to honor truth invariant**
- **Found during:** Task 1 (inline `<verify>` script execution)
- **Issue:** The plan's `<action>` scaffold included a second AA guardrail that remediates `accent` when `accent_on_neutral_light` fails the large-text 3.0 threshold. Running the plan's own inline-verify script with `primary="#AABBCC"` triggered remediation (ratio 1.88 < 3.0), swapping accent to `#1A1A1A`. That immediately contradicted the scaffold's `assert new_t.palette.accent_default == '#AABBCC'` line AND the `must_haves.truths` invariant "`accent_default` equals `kit.palette.primary.hex` (uppercased)".
- **Fix:** Removed the accent-on-neutral-light guardrail from `_build_palette`. Kept the `neutral_dark_on_neutral_light` guardrail — which is the only pair the truth invariants actually describe. Replaced the guardrail block with a documented NOTE explaining the split of responsibilities (accent-vs-text is Plan 04/06's audit concern, not the applier's).
- **Files modified:** `flyer_generator/brand_kit/applier.py` (removed 17-line block, added 8-line rationale comment; also dropped the `passes_aa` import that the removed block used).
- **Verification:** Inline-verify script from plan passes. All 22 test_applier.py tests pass, including `test_apply_brand_kit_swaps_palette_accent_default` which asserts the truth invariant directly.
- **Committed in:** 7011343 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — internal-spec contradiction).
**Impact on plan:** No scope change; the remaining guardrail is exactly the pair described in `must_haves.truths`, and the integration test against `.brand-kit-template.json` still produces an AA-passing template.

## Issues Encountered

None. The conflict between the `<action>` scaffold and `must_haves.truths` was resolved in favor of the truth invariants (which the inline verify script also enforced). No blockers, no checkpoints, no authentication gates.

## B1 / B2 Compliance

- **B1 (__init__.py stays a stub):** `git diff flyer_generator/brand_kit/__init__.py` vs. base `8c646d4` — empty diff. Tests use zero `from flyer_generator.brand_kit import ...` (package-root) lines; all imports are direct-module (`from flyer_generator.brand_kit.applier import apply_brand_kit`, etc.).
- **B2 (depends_on includes 18-01):** `applier.py` imports `resolve_kit_dir` from `flyer_generator.brand_kit.storage` (Plan 01). The import is lazy (inside `_load_primary_logo_bytes`) to keep the module-load graph acyclic — same pattern storage.py uses for its lazy BrandKit import.

## User Setup Required

None. This plan adds a pure Python function + tests. No env vars, no external services, no CLI changes (Plan 07 wires the CLI).

## Next Phase Readiness

- **Plan 06 (Audit) can consume:** The `(TemplateSchema, bytes | None)` tuple returned by `apply_brand_kit` is exactly what `render_schema_brochure(template=..., logo_bytes=...)` expects as input — Plan 06's audit loop can call apply → render → audit without any adapter.
- **Plan 07 (CLI integration) can consume:** `apply_brand_kit(tmpl, kit)` — same contract as the CONTEXT.md locked signature. Plan 07 will also add `apply_brand_kit` to `__init__.py`'s consolidated re-export block.
- **No blockers.** All 749 tests (incl. 22 new) pass.

## Self-Check: PASSED

- [x] `flyer_generator/brand_kit/applier.py` exists.
- [x] `grep -q "def apply_brand_kit"` — present.
- [x] `grep -q "template.model_copy(update="` — present.
- [x] `grep -q "_SCALED_SIZE_FIELDS"` — present.
- [x] `grep -q "ensure_aa"` — present.
- [x] `grep -q "resolve_kit_dir"` — present.
- [x] Path-traversal guard via `relative_to(kit_dir)` — present.
- [x] `flyer_generator/brand_kit/__init__.py` UNCHANGED — verified via `git diff`.
- [x] `pytest tests/brand_kit/test_applier.py` — 22/22 passing.
- [x] `pytest tests/` full suite — 749/749 passing (no regressions).
- [x] Direct-module import smoke: `from flyer_generator.brand_kit.applier import apply_brand_kit` — ok.
- [x] Task commit `7011343` — present in `git log`.
- [x] Task commit `d903217` — present in `git log`.

---
*Phase: 18-brand-kit-system*
*Completed: 2026-04-20*
