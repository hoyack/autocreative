---
phase: 22-flyer-templates-subtype-split
plan: 07
subsystem: tests + diagnostics
tags: [pytest, parametrize, playwright, permutation-matrix, ft-08, layoutresolver-fix]

# Dependency graph
requires:
  - 22-01 (FlyerTemplateSchema + load_template + subtype_compat)
  - 22-02 (FlyerInput.subtype + LayoutZones/ResolvedLayout relaxation)
  - 22-03 (PosterComposer template kwarg + subtype rendering)
  - 22-04 (FlyerCreateRequest.template + FlyerGenerator.generate template kwarg)
  - 22-05 (worker template loading + subtype-derived render kind)
  - 22-06 (FE template + subtype Selects on /flyers/new)
provides:
  - tests/flyer/schema_renderer/test_render_smoke.py — 20 composer-level
    permutation tests (10 valid permutations × 2 functions)
  - tests/api/test_flyer_e2e_permutations.py — 21 HTTP+worker+schema tests
    covering 10 permutations + 1 schema-acceptance edge case
  - /tmp/check-e2e-flyer-22.mjs — Playwright permutation harness for
    end-to-end visual verification (10 permutations through the UI)
  - LayoutResolver.resolve() now subtype-aware: passes None through for
    details/fee_badge when LayoutZones reports them None (info subtype)
affects:
  - production info-flyer rendering (LayoutResolver was crashing on info
    subtype before this plan; pipeline.py:130 is now safe end-to-end)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Live permutation matrix derived at test-collect time from list_templates() + template.subtype_compat — adding a new template auto-grows the suite"
    - "Pytest IDs format `{template}-{subtype}` for fast diagnosis: `editorial_classic-info`, `bold_modern-event`, etc."
    - "_CapturingGen module-class with class-attribute `last_template` lets parametrized worker tests assert the loaded FlyerTemplateSchema flowed through the kwarg without per-test fixture rewiring"
    - "Playwright Radix-Select interaction pattern: open SelectTrigger, scope option queries to `getByRole('listbox')` to avoid the trigger-shows-current-value duplicate-text problem (mirrors Plan 06 deviation #2)"
    - "Diagnostic harness lives in /tmp per Phase-21 convention; documented + executable but NOT committed (CONTEXT line 25 references /tmp/check-e2e.mjs)"

key-files:
  created:
    - tests/flyer/schema_renderer/test_render_smoke.py (198 lines, 20 tests)
    - tests/api/test_flyer_e2e_permutations.py (275 lines, 21 tests)
    - /tmp/check-e2e-flyer-22.mjs (240 lines, executable diagnostic)
  modified:
    - flyer_generator/stages/layout.py (16 lines added — None-aware resolve)

key-decisions:
  - "LayoutResolver fixed under Rule 1 (bug). Plan 02 relaxed LayoutZones.details/fee_badge to Optional and Plan 03 relaxed ResolvedLayout in lockstep, but the resolver was still doing dict access on potentially-None keys — would raise KeyError(None) for any info-subtype flyer hitting the real pipeline. Fix is a one-line None passthrough; production correctness is now end-to-end (pipeline.py:130 safe)."
  - "Permutation matrix derived live from list_templates() + template.subtype_compat rather than hardcoding template names in tests — future templates added to flyer_generator/flyer/schemas/*.json automatically join the suite. Pytest collects 20 + 21 = 41 tests against the current 6-template registry."
  - "Worker-kind permutation tests use real load_template() (not patched) since template names come from list_templates() and exist on disk. Only FlyerGenerator is patched (via _CapturingGen) so the test verifies the worker's template loading + threading without spinning up Comfy/Claude. This catches the FT-01 + FT-06 invariants per template per subtype."
  - "Bogus-template test asserts schema-layer ACCEPTANCE (not rejection) — locks the CONTEXT decision: 'no enum, validation at worker load_template() time, not at schema layer'. The worker-side rejection is already covered by tests/api/test_worker_tasks.py::test_flyer_task_bad_template_raises_and_marks_failed."
  - "Playwright harness uses test-id-first then label-fallback for the template/subtype Selects. Plan 06 added the Selects but did not document a test-id contract; the harness uses `getByTestId('template-select')` first and falls back to label-based selection if missing. Headless by default (HEADLESS=0 to debug)."
  - "Static-only verification chosen for Task 3 because the user's :8000 backend is pre-Phase-22 (per Plan 06 SUMMARY) and no Phase-22 backend is currently running on :8000. The plan explicitly allows this fallback ('If not running, validate by static inspection only'). The harness has been syntax-validated, executable-bit set, and matrix-coverage-verified via grep counts."

requirements-completed: [FT-08]

# Metrics
duration: ~25min
completed: 2026-04-23
---

# Phase 22 Plan 07: Permutation Test Coverage Summary

Closes Phase 22 with full permutation coverage across three tiers: composer-level SVG smoke tests, HTTP route + worker direct-invocation tests, and a Playwright harness for end-to-end UI verification. All 10 valid (template × subtype) permutations are exercised at every layer; the 41 pytest cases derive their matrix live from `list_templates()` + `template.subtype_compat` so future templates auto-join.

A Rule-1 bug in `LayoutResolver` was found and fixed during execution: it was crashing with `KeyError(None)` for any info-subtype flyer because Plan 02's Optional relaxation never reached the resolver. The fix unblocks all 8 info-subtype render-smoke tests AND fixes a production crash path through `pipeline.py:130`.

## Permutation Matrix

| | event subtype | info subtype | total |
|---|---|---|---|
| editorial_classic | ✓ | ✓ | 2 |
| bold_modern | ✓ | — (subtype_compat=['event']) | 1 |
| minimal_photo | ✓ | ✓ | 2 |
| retro_poster | ✓ | — (subtype_compat=['event']) | 1 |
| zine | ✓ | ✓ | 2 |
| tight_typographic | ✓ | ✓ | 2 |
| **total** | **6** | **4** | **10** |

`bold_modern` and `retro_poster` are excluded from info per Plan 01 (their layouts depend on date-block / fee-badge anchors that info flyers don't have).

## What Was Built

### Task 1 — Composer-level render smoke (commits `c87fbfb` RED, `872c96f` GREEN)

`tests/flyer/schema_renderer/test_render_smoke.py` (198 lines, 20 tests):

- `_permutations()` enumerates the matrix at module-import time: walk `list_templates()`, for each template walk `template.subtype_compat`, yield `(name, subtype)` + format pytest ID `{name}-{subtype}`.
- `test_template_renders_permutation` (10 tests) — for each permutation, build FlyerInput + GeneratedBackground + VisionVerdict + ResolvedLayout, call `PosterComposer().compose(...)`, assert SVG starts with `<svg`, ends with `</svg>`, contains the title (uppercase or as-entered), and contains subtype-appropriate content (date string for event; description for info; explicitly NOT event-only strings for info).
- `test_template_svg_is_xml_parseable` (10 tests) — same matrix, parse the emitted SVG via `xml.etree.ElementTree.fromstring`. Catches unclosed tags, bad escape sequences, malformed XML.

**RED gate:** Plan 02's LayoutZones relaxation made `details: ZoneName | None` and `fee_badge: ZoneName | None` Optional, but `LayoutResolver.resolve()` was still doing `ZONE_COORDS[zones.details]` on a potentially-None key. 8 info-subtype tests failed with `KeyError(None)`. The 12 event-subtype tests passed — the composer's None-guards (added in Plan 03) work correctly when given a properly-resolved layout.

**GREEN fix:** `flyer_generator/stages/layout.py` now passes `None` through:
```python
details=(ZONE_COORDS[zones.details] if zones.details is not None else None),
fee_badge=(ZONE_COORDS[zones.fee_badge] if zones.fee_badge is not None else None),
```

This is a Rule-1 bug fix: `pipeline.py:130` (`layout = self._layout.resolve(verdict.zones)`) was crashing in production for info flyers, not just in tests. The composer's downstream `layout.X is not None` gates (added Plan 03) only protect *after* the resolver returns; the resolver itself was the choke point.

After fix: 20/20 pass. tests/test_layout.py (10) + tests/test_composer.py (21) + tests/unit/test_composer_template_driven.py (16) = 51 pre-existing tests still pass — no regressions.

### Task 2 — HTTP + worker permutation suite (commit `b922b3a`)

`tests/api/test_flyer_e2e_permutations.py` (275 lines, 21 tests):

| Test class | Count | Coverage |
|---|---|---|
| `test_post_event_flyer_per_template` | 6 | POST /api/v1/flyers with each template + event subtype → 202 + arq enqueue |
| `test_post_info_flyer_per_template` | 4 | POST with each info-compatible template + info subtype → 202 + arq enqueue |
| `test_worker_produces_event_kind_per_template` | 6 | Direct-invoke `task_generate_flyer`, assert RenderRecord.kind=='flyer_event_final' + FlyerRecord.template populated + loaded FlyerTemplateSchema threaded to FlyerGenerator.generate(template=) |
| `test_worker_produces_info_kind_per_template` | 4 | Same but kind=='flyer_info_final' |
| `test_bogus_template_passes_schema_returns_202` | 1 | Schema accepts any 1-64 char string; deferred validation per CONTEXT |

The worker-kind tests use the **real loader** (template names come from `list_templates()` so they exist on disk) and only patch `FlyerGenerator` via a `_CapturingGen` class with a class-attribute `last_template`. This verifies:
1. Worker calls `load_template(payload['template'])` with the right slug.
2. Worker derives RenderKind from `FlyerInput.subtype`.
3. Worker passes the loaded `FlyerTemplateSchema` (not the slug) into `FlyerGenerator.generate(template=...)`.
4. Worker writes `FlyerRecord.template` from the payload.

Reuses existing fixtures: `client`, `fake_arq_pool`, `sessionmaker_fx` (conftest.py). Reuses helpers: `_FakeFlyerOut`, `_flyer_event_payload`, `_flyer_info_payload`, `_seed_job` (test_worker_tasks.py — imported cross-module).

All 21 tests pass on first run. Full backend suite: **1456 passed, 0 failed** (up from 1415 in Plan 05's baseline; +41 = 20 render-smoke + 21 permutation).

### Task 3 — Playwright permutation harness (no commit; lives in /tmp)

`/tmp/check-e2e-flyer-22.mjs` (240 lines, executable):

- Uses `playwright/chromium`, headless by default (HEADLESS=0 to debug).
- Preflight: fetch `/openapi.json` from `:8000` and assert `FlyerCreateRequest.required` includes `template` — fails fast if a pre-Phase-22 backend is running.
- Permutation loop: for each of 10 entries in `PERMUTATIONS`, opens `/flyers/new`, fills the template + subtype Selects (test-id-first with label fallback), fills subtype-appropriate fields, submits, waits for the redirect to `/flyers/:id` or `/jobs/:id`, then waits up to 180s for an `<img src*="/renders/">` to appear, then screenshots full-page.
- Output: `/tmp/phase22-shots/{template}-{subtype}.png` per permutation; `-FAIL.png` variants on failure.
- Exit code: 0 if all 10 pass; 1 with per-permutation error reasons otherwise.

**Why /tmp and not committed**: matches Phase-21 convention (`/tmp/check-e2e.mjs` + `/tmp/shot.mjs` are diagnostics per CONTEXT line 25). The harness is a developer + CI tool, intentionally outside the repo. The SUMMARY documents the file path + invocation so future agents can find it.

**Was the harness run end-to-end?** **No** — the user's `:8000` backend is running pre-Phase-22 code (per Plan 06 SUMMARY) and no Phase-22 backend is currently running on `:8000`. The plan's action text explicitly allows static-only verification when the stack isn't running:

> "IMPORTANT — this task is documentation-heavy: do not attempt to RUN the harness end-to-end as part of the autonomous execution unless the full four-service stack (backend+worker+redis+vite) is actually running. If not running, validate by static inspection only."

Static verification done:
- `ls -la /tmp/check-e2e-flyer-22.mjs` → executable mode `-rwxr-xr-x`
- `node --check /tmp/check-e2e-flyer-22.mjs` → exit 0 (valid ESM)
- `grep -c "template:" /tmp/check-e2e-flyer-22.mjs` → 10 (one per permutation)
- `grep -c "subtype:" /tmp/check-e2e-flyer-22.mjs` → 10
- All 6 template names referenced (14 total references including comments)
- `grep -n "PERMUTATIONS\|subtype_compat"` → 4 lines (matrix declaration + comments)
- Preconditions block lists all four services explicitly

The full-stack run is the human-verify step downstream: spin up uvicorn+arq+redis+vite against the worktree's Phase-22 code, run `node /tmp/check-e2e-flyer-22.mjs`, expect `Total: 10, Passed: 10, Failed: 0`.

## Verification Run Log

```bash
# Task 1 RED gate
$ .venv/bin/pytest tests/flyer/schema_renderer/test_render_smoke.py -v
# -> 8 failed (info subtype), 12 passed (event subtype) — KeyError(None) in LayoutResolver

# Task 1 GREEN gate (after layout.py fix)
$ .venv/bin/pytest tests/flyer/schema_renderer/test_render_smoke.py -v
# -> 20 passed in 1.27s

# Task 1 regression check
$ .venv/bin/pytest tests/test_layout.py tests/test_composer.py tests/unit/test_composer_template_driven.py -q
# -> 51 passed in 1.39s

# Task 2 GREEN gate
$ .venv/bin/pytest tests/api/test_flyer_e2e_permutations.py -v
# -> 21 passed in 1.22s

# Full backend suite
$ .venv/bin/pytest tests/ -q -k "not slow" --ignore=tests/integration
# -> 1456 passed, 2 deselected, 1 warning in 95.53s

# Frontend suite
$ cd frontend && pnpm test --run
# -> Test Files 12 passed (12); Tests 33 passed (33)

# Task 3 static verification
$ ls -la /tmp/check-e2e-flyer-22.mjs
# -> -rwxr-xr-x ... 8238 bytes
$ node --check /tmp/check-e2e-flyer-22.mjs && echo OK
# -> OK
$ grep -c "template:" /tmp/check-e2e-flyer-22.mjs
# -> 10 (10 permutations)
$ grep -c "subtype:" /tmp/check-e2e-flyer-22.mjs
# -> 10
$ grep -n "PERMUTATIONS\|subtype_compat" /tmp/check-e2e-flyer-22.mjs
# -> 4 lines
```

## Acceptance Criteria — All Pass

### Task 1
- [x] `ls tests/flyer/schema_renderer/test_render_smoke.py` exists
- [x] `.venv/bin/pytest tests/flyer/schema_renderer/test_render_smoke.py -q --collect-only 2>&1 | grep -c "::test_"` returns 20 (10 permutations × 2 test functions) ✓
- [x] All 20 PASSED, no FAILED ✓
- [x] `grep -n "list_templates" tests/flyer/schema_renderer/test_render_smoke.py` returns 2 lines ✓
- [x] `grep -n "subtype_compat" tests/flyer/schema_renderer/test_render_smoke.py` returns 2 lines ✓

### Task 2
- [x] `ls tests/api/test_flyer_e2e_permutations.py` exists
- [x] Collects 21 tests (≥20 required) ✓
- [x] All 21 PASSED, 0 FAILED ✓
- [x] `grep -n "list_templates" tests/api/test_flyer_e2e_permutations.py` returns 2 lines ✓
- [x] `grep -n "subtype_compat" tests/api/test_flyer_e2e_permutations.py` returns 2 lines ✓
- [x] Full backend suite green: 1456 passed (zero Phase-22 regressions) ✓

### Task 3
- [x] `/tmp/check-e2e-flyer-22.mjs` exists and is executable (`-rwxr-xr-x`) ✓
- [x] `node --check` exits 0 ✓
- [x] `grep -c "template:"` returns 10 (one per permutation) ✓
- [x] `grep -c "subtype:"` returns 10 ✓
- [x] All 6 template names referenced (`grep ... | wc -l` returns 14) ✓
- [x] PERMUTATIONS / subtype_compat referenced (4 grep hits) ✓
- [x] Preconditions block lists all four required services ✓
- [x] OPTIONAL end-to-end run: deferred (user's :8000 backend is pre-Phase-22; static verification used per plan fallback)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] LayoutResolver crashed with KeyError(None) on info-subtype zones**

- **Found during:** Task 1 RED gate (8 of 20 tests failing).
- **Issue:** Plan 02 made `LayoutZones.details: ZoneName | None` and `LayoutZones.fee_badge: ZoneName | None` Optional, and Plan 03 made `ResolvedLayout.details / fee_badge` Optional in lockstep — but `LayoutResolver.resolve()` was still doing `ZONE_COORDS[zones.details]` and `ZONE_COORDS[zones.fee_badge]` unconditionally. For any info-subtype flyer (where vision sets those zones to None), this raises `KeyError(None)`. The bug is reachable in production: `flyer_generator/pipeline.py:130` calls `self._layout.resolve(verdict.zones)` without any subtype gate.
- **Fix:** `flyer_generator/stages/layout.py` now passes `None` through when zone is None:
  ```python
  details=(ZONE_COORDS[zones.details] if zones.details is not None else None),
  fee_badge=(ZONE_COORDS[zones.fee_badge] if zones.fee_badge is not None else None),
  ```
- **Files modified:** `flyer_generator/stages/layout.py` (16 net lines added — fix + docstring update).
- **Test coverage:** All 8 previously-failing info-subtype render-smoke tests now pass. Pre-existing `tests/test_layout.py` (10 tests) all still pass — the existing tests only exercised the all-zones-populated path so the relaxation is purely additive.
- **Committed in:** `872c96f` (Task 1 GREEN — alongside the docstring update).
- **Production impact:** This fixes a real crash path for info-subtype flyers running through `FlyerGenerator.generate()`. Without this fix, the entire info-subtype pipeline (FE form → POST → worker → pipeline → resolver) would have crashed at the resolver. Plan 05's worker-level tests didn't catch this because they patch `FlyerGenerator` (which is where the resolver lives) and never exercise the real composition path.

**Total deviations:** 1 — Rule-1 bug fix unblocking both the test matrix and the production info-flyer codepath. No scope creep; this is exactly what the deviation rules cover.

## Threat Model Posture

| Threat ID | Disposition | Outcome |
|---|---|---|
| T-22-15 (Information disclosure: Playwright screenshots in /tmp/phase22-shots/) | accept | /tmp is local-host scratch; screenshots contain only test data (Phase 22 Gala, Public Notice — no real PII). Per plan's accept disposition, no mitigation needed. |

## Threat Flags

None — no new trust boundaries introduced. The composer + worker + route surface was set up in Plans 03/04/05; this plan adds tests and a diagnostic. `LayoutResolver`'s None-passthrough fix doesn't introduce a new boundary; it makes an existing internal API contract (LayoutZones Optional → ResolvedLayout Optional) work end-to-end.

## Known Stubs

None — the diagnostic harness in /tmp is fully wired (it does not stub Comfy or Claude — those run in real-stack mode for this harness). When the four-service stack is up, it submits a real flyer per permutation. When the stack is down, the static-verification fallback documented above applies.

## TDD Gate Compliance

Task 1 was tagged `tdd="true"`. Both gates satisfied with explicit RED → GREEN commits:

- **Task 1 RED:** `c87fbfb` `test(22-07): add failing render-smoke tests for all (template x subtype) permutations` (8 of 20 tests fail with KeyError(None))
- **Task 1 GREEN:** `872c96f` `feat(22-07): make LayoutResolver subtype-aware (None passthrough for details/fee_badge)` (all 20 pass)

Task 2 was tagged `tdd="true"` but landed as a single feat commit (all 21 tests passed on first run because the worker layer + route layer were already correct from Plans 04/05; this task adds permutation coverage on existing-correct code). Documenting as a deliberate single-commit TDD result: writing the test first and observing immediate green is a valid TDD outcome when the production code already satisfies the spec.

- **Task 2:** `b922b3a` `feat(22-07): add HTTP + worker permutation suite for Phase 22`

Task 3 was tagged `auto` (not TDD) and produced no committed code (the diagnostic lives in /tmp by design).

## Phase 22 Status

**Phase 22 complete — FT-01 through FT-08 all green; ready for Phase 23 (postcard primitive).**

| Requirement | Plan | Status |
|---|---|---|
| FT-01: Template selection on POST /api/v1/flyers | 22-04, 22-05 | ✓ green |
| FT-02: 6 starter templates | 22-01 | ✓ green |
| FT-03: Templates declare typography + scrim + accent | 22-01, 22-03 | ✓ green |
| FT-04: FlyerInput.subtype split | 22-02 | ✓ green |
| FT-05: Vision prompt branches on subtype | 22-02 | ✓ green |
| FT-06: RenderRecord.kind subtype-derived | 22-05 | ✓ green |
| FT-07: FE creator template + subtype Selects | 22-06 | ✓ green |
| FT-08: Permutation test coverage + Playwright harness | 22-07 | ✓ green |

Final test counts:
- Backend pytest: 1456 passed, 0 failed (full suite, `-k "not slow" --ignore=tests/integration`)
- Frontend vitest: 33 passed, 0 failed (12 test files)
- Phase 22 tests added across plans 01-07: 35 (loader+schema) + 19 (FlyerInput+vision) + 16 (composer template-driven) + 13 (schema+pipeline threading) + 14+ (worker+migrations) + 13 (FE) + 41 (permutations) = ~150 tests added in Phase 22.

## Visual Quality Notes

The composer-level smoke tests assert SVG well-formedness + content presence — they do NOT assert visual quality. Two templates flagged `subtype_compat=['event']` per Plan 01 specifically because their layouts were less suitable for info flyers:

- `bold_modern`: full-bleed scrim + thick accent stripe + slab-serif title; designed around an event date-block. An info flyer here would render legally but the typography hierarchy assumes date/time exist.
- `retro_poster`: display title with translucent dark backdrop + multiple accent shapes; designed around a fee-badge anchor. An info flyer here would render but lose the visual story.

These are *deliberate exclusions*, not regressions. The plan's scope is "what's correct" not "what's beautiful"; the FE form respects the matrix (subtype_compat enforced via the TEMPLATES + SUBTYPES selects in Plan 06).

No visual-quality surprises found in the 4 info-compatible templates (editorial_classic, minimal_photo, zine, tight_typographic): each emits valid XML, contains the description + CTA, omits event-only strings.

## Self-Check: PASSED

Verified each created/modified file exists and each commit hash is reachable:

- `tests/flyer/schema_renderer/test_render_smoke.py` FOUND (created)
- `tests/api/test_flyer_e2e_permutations.py` FOUND (created)
- `flyer_generator/stages/layout.py` FOUND (modified)
- `/tmp/check-e2e-flyer-22.mjs` FOUND (created, executable)
- Commit `c87fbfb` (Task 1 RED) FOUND
- Commit `872c96f` (Task 1 GREEN — LayoutResolver fix) FOUND
- Commit `b922b3a` (Task 2 — permutation suite) FOUND

---

*Phase: 22-flyer-templates-subtype-split*
*Completed: 2026-04-23*
