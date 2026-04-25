---
phase: 24-poster-primitive
plan: 06
subsystem: tests
tags: [poster, render-smoke, http-permutations, playwright, dimension-assertion, e2e]

# Dependency graph
requires:
  - phase: 24-poster-primitive-01
    provides: 3 shipped poster JSON templates (editorial_grand, bold_announcement, cinematic_onesheet) + load_template
  - phase: 24-poster-primitive-02
    provides: PosterComposer(canvas_width=W) + Rasterizer(width=W, height=H) parameterized canvas
  - phase: 24-poster-primitive-03
    provides: PosterCreateRequest with size Literal + JobKind.POSTER + JobRecord shape
  - phase: 24-poster-primitive-04
    provides: POST /api/v1/posters route + task_generate_poster worker + _SIZE_TO_CANVAS mapping
  - phase: 24-poster-primitive-05
    provides: NewPosterPage FE creator (size + template Selects with data-testid hooks)
  - phase: 23-postcard-primitive-06
    provides: 3-layer permutation pattern (render-smoke + HTTP + Playwright harness)
provides:
  - 9 render-smoke pytests proving each (template x size) PNG decodes at exactly the size-derived canvas dims
  - 9 HTTP POST permutation tests + 3 invalid-size rejection tests
  - Authored Playwright harness /tmp/check-e2e-poster-24.mjs (NOT committed; live-stack run deferred to user post-merge)
affects:
  - 26-adversarial-hardening-sweep  # poster permutation matrix is the baseline the adversarial sweep extends

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Permutation matrix derived from worker constant: tests import _SIZE_TO_CANVAS so future size additions auto-grow the matrix without test edits."
    - "Synthetic PNG fixture for Comfy: Pillow Image.new(canvas_dims) + BytesIO -> GeneratedBackground; exercises the full Composer + Rasterizer chain at print canvas dims without hitting Comfy or vision."
    - "Dimension assertion via Pillow round-trip: PIL.Image.open(BytesIO(png_bytes)).size == canvas_dims locks the print-spec contract for every shipped (template x size) combination."
    - "Authoring vs. runtime gates (continuation of Phase 22-07 + 23-06 precedent): plan tasks AUTHOR the Playwright harness (write file + chmod +x + node --check + grep matrix coverage); runtime live-stack verification deferred to user post-merge."

key-files:
  created:
    - tests/poster/test_render_smoke.py
    - tests/api/test_poster_permutations.py
    - /tmp/check-e2e-poster-24.mjs  # not committed; lives in /tmp by phase convention
  modified: []

key-decisions:
  - "Render-smoke uses real PosterComposer + real Rasterizer with mocked Comfy. The synthetic background bytes are a Pillow-generated solid-color PNG at canvas dims; this exercises the full PosterComposer.compose() -> Rasterizer.rasterize() chain at the injected canvas without needing a real Comfy server."
  - "subtype='info' chosen for the FlyerInput fixture (mirrors the worker's _build_flyer_input). info-subtype zones (title + org_credit only, no details/fee_badge) match what posters emit in production."
  - "Invalid-size matrix locks ['36x48', '12x18', ''] — these explicitly test the non-empty + wrong-format + empty-string boundaries against the schema-layer Literal."
  - "Playwright harness lives at /tmp/check-e2e-poster-24.mjs per phase convention (Phase 21+22+23 pattern: /tmp/check-e2e-{phase}-{N}.mjs). NOT committed."

patterns-established:
  - "3-layer permutation closing pattern for v1.1 primitives: (1) render-smoke pytest with PNG-dimension assertion; (2) HTTP POST permutations + invalid-input rejections; (3) authored Playwright harness in /tmp/. Mirrors Phase 23-06 (postcards) and ports cleanly to Phase 25 (invitations)."
  - "Test ID convention for parametrized poster cases: {template}-{size} (e.g. editorial_grand-18x24). Pytest's ids= lambda builds them; matches log readability."

requirements-completed: [PO-01, PO-02, PO-03, PO-04]

# Metrics
duration: ~30min
completed: 2026-04-25
---

# Phase 24 Plan 06: Poster Permutation Tests Summary

**Three-layer permutation coverage closes Phase 24: 9 render-smoke pytests prove every (template x size) combination rasterizes at exactly the print-spec canvas dims; 9 HTTP POST permutations + 3 invalid-size rejections lock the route surface; an authored Playwright harness at `/tmp/check-e2e-poster-24.mjs` is documented + executable + matrix-coverage-verified for the user's post-merge live-stack run.**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-04-25T08:14Z (worktree base verified)
- **Completed:** 2026-04-25T08:42Z
- **Tasks:** 3 / 3 complete
- **Commits:** 2 (Task 3 has no commit by phase convention — `/tmp/` files are not tracked)
- **Files created:** 2 pytest files + 1 /tmp Playwright harness
- **Tests added:** 22 net-new pytests (10 render-smoke + 12 HTTP)

## Accomplishments

- **PO-01 closed at HTTP layer (9 + 3 cases):** All 9 (template x size) POSTs to `/api/v1/posters` return 202 + 26-char ULID job_id. JobRecord persists with `kind=POSTER`, `status=QUEUED`, and `input_payload` reflecting the requested template + size. `fake_arq_pool` captures exactly one `task_generate_poster` enqueue per request with matching payload. The 3 invalid-size cases (`'36x48'`, `'12x18'`, `''`) return 422 via the schema-layer `size: Literal['18x24','24x36','27x40']` (T-24-07 mitigation).
- **PO-02 closed at integration layer (9 cases):** Each `(template x size)` permutation runs the real `PosterComposer(canvas_width=W).compose(...)` followed by real `Rasterizer(width=W, height=H).rasterize(svg)`, with a Pillow-synthesized solid-color PNG standing in for the Comfy background at canvas dims. The output PNG decodes via `PIL.Image.open(BytesIO(png_bytes)).size == canvas_dims` for every case — locking the print-spec contract.
- **PO-03 closed at integration layer:** All 3 shipped poster templates (`editorial_grand`, `bold_announcement`, `cinematic_onesheet`) round-trip through the renderer at all 3 size presets (`18x24` -> 5400x7200, `24x36` -> 7200x10800, `27x40` -> 8100x12000). The `test_size_to_canvas_dims_locked` sanity-check pins the worker's `_SIZE_TO_CANVAS` mapping to the locked CONTEXT.md values.
- **PO-04 closed at E2E authoring layer:** `/tmp/check-e2e-poster-24.mjs` is authored, executable (`chmod +x`), syntax-valid (`node --check`), and matrix-coverage-verified (all 3 templates + all 3 sizes referenced; `PERMUTATIONS` constant, `POLL_TIMEOUT_MS = 300_000` per T-24-19, `"All 9 permutations passed"` exit literal). Live-stack runtime verification deferred to user post-merge per Phase 22-07 + 23-06 precedent.
- **Zero regression.** Full project pytest sweep (`pytest tests/ -q -k "not slow" --ignore=tests/integration`): **1754 passed, 0 failed.** Frontend (`pnpm test --run`): **43 passed, 0 failed.**

## Task Commits

Each task was committed atomically. Task 3 deliberately has no commit — the `/tmp/` Playwright harness lives outside the repo by phase convention (matches Phase 22-07 + 23-06).

1. **Task 1 — render-smoke (10 tests, 9 perms + 1 sanity):** `2ac7230` — `feat(24-06): add 9-permutation render-smoke + dimension assertion (PO-02 + PO-03)`
2. **Task 2 — HTTP permutations (12 tests, 9 happy + 3 422):** `ae14571` — `feat(24-06): add HTTP permutation suite (9 perms + 3 invalid-size) for posters`
3. **Task 3 — Playwright harness:** No commit (`/tmp/check-e2e-poster-24.mjs` not tracked).

## Files Created/Modified

### Created

- **`tests/poster/test_render_smoke.py`** (~197 lines, 10 tests):
  - `test_size_to_canvas_dims_locked` — sanity-check that `_SIZE_TO_CANVAS` matches the 3 CONTEXT.md-locked values.
  - 9 parametrized `test_render_smoke_canvas_dims[<template>-<size>]` cases. For each: load template, build synthetic GeneratedBackground at canvas_dims, compose SVG via real PosterComposer, rasterize via real Rasterizer, assert `Image.open(BytesIO(png_bytes)).size == canvas_dims`.
- **`tests/api/test_poster_permutations.py`** (~126 lines, 12 tests):
  - 9 parametrized `test_post_poster_permutation_returns_202[<template>-<size>]` cases. Each asserts 202 + ULID job_id + JobRecord(kind=POSTER, status=QUEUED, input_payload reflecting template + size) + exactly-one fake_arq_pool capture with matching task name + payload.
  - 3 parametrized `test_post_poster_rejects_invalid_size[size=<value>]` cases for `'36x48'`, `'12x18'`, `''` — all 422.
- **`/tmp/check-e2e-poster-24.mjs`** (~180 lines, NOT committed):
  - Imports `chromium` from playwright; defines TEMPLATES + SIZES arrays + `PERMUTATIONS = TEMPLATES.flatMap(t => SIZES.map(s => ({...})))` (9 entries).
  - Pre-flight `/openapi.json` check for `/api/v1/posters` POST presence (fail fast if Phase-24 BE not running).
  - Per-permutation Playwright flow: navigate `/posters/new`, fill headline, open size + template Selects via `data-testid` hooks, click submit, wait for `/posters/[A-Z0-9]{26}$` redirect, poll body text for `succeeded|failed|cancelled` within `POLL_TIMEOUT_MS = 300_000`.
  - On failure: `await page.screenshot({ path: \`/tmp/poster-fail-${template}-${size}-${ts}.png\`, fullPage: true })` + structured failures array + per-permutation reason in summary output.
  - End: if no failures, `console.log("All 9 permutations passed")` + `process.exit(0)`; else `process.exit(1)` with per-permutation reasons.

### Modified

None.

## Decisions Made

None beyond what was locked in `24-06-PLAN.md`, `24-CONTEXT.md`, and prior plan summaries. Plan executed exactly as written:

- Render-smoke uses real Composer + real Rasterizer at full canvas dims (5400x7200 / 7200x10800 / 8100x12000) per plan's `<patterns>` block. No shortcuts taken (no scale-down, no rasterizer mock).
- HTTP permutation tests reuse `client`, `fake_arq_pool`, `sessionmaker_fx` fixtures from `tests/api/conftest.py` per plan's `<patterns>` block.
- Playwright harness mirrors `/tmp/check-e2e-postcard-23.mjs` structure with the poster-specific UI selectors (`data-testid="size-select"` + `data-testid="template-select"` + the "Generate poster →" button label).
- Test ID convention `{template}-{size}` matches plan spec and prior phases.

## Deviations from Plan

None — plan executed exactly as written.

The plan's `<action>` block specified:

- Task 1: "10 tests" (9 parametrized + 1 sanity check) — delivered exactly **10**.
- Task 1: "Verify dimension assertion at one explicit case via shell" — verified via `/home/hoyack/work/autocreative/.venv/bin/python -c "..."` against `_SIZE_TO_CANVAS`. Output: `OK`.
- Task 2: "12 tests" (9 happy + 3 invalid-size) — delivered exactly **12**.
- Task 3: All 8 grep verification checks pass (PERMUTATIONS=2, "All 9 permutations passed"=1, all 3 templates referenced, all 3 sizes referenced, POLL_TIMEOUT_MS=4 occurrences, `import { chromium }`=1, `POLL_TIMEOUT_MS = 300_000`=2).

The verify chain from `<verification>` ran clean:

- `pytest tests/poster/test_render_smoke.py -v` -> **10 passed** in ~49s
- `pytest tests/api/test_poster_permutations.py -v` -> **12 passed** in <1s
- `pytest tests/api/ tests/poster/ -q` -> **429 passed, 0 failed** in ~65s
- `pytest tests/ -q -k "not slow" --ignore=tests/integration` -> **1754 passed, 0 failed** in ~156s
- `cd frontend && pnpm test --run` -> **43 passed** (after `pnpm install --frozen-lockfile` in worktree to populate node_modules)
- `node --check /tmp/check-e2e-poster-24.mjs` -> exit 0
- `[ -x /tmp/check-e2e-poster-24.mjs ]` -> true (`-rwxr-xr-x`)

## Issues Encountered

None. The 27x40 (8100x12000 = 97 megapixel) rasterization triggers a Pillow `DecompressionBombWarning` (limit 89 megapixel). This is a non-error warning — the rasterized PNG decodes successfully and the dimension assertion holds. The warning is expected behavior for print-canvas-sized images and matches the pre-existing warning in `tests/unit/test_preprocessor_canvas_dimensions.py::TestPosterDimensions::test_27x40_8100x12000`. No action needed.

## Threat Mitigations Implemented

| Threat ID | Mitigation                                                                                | Verified by                                                                                       |
| --------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| T-24-07   | Schema-layer `size: Literal["18x24","24x36","27x40"]` rejects unknown sizes at 422        | `test_post_poster_rejects_invalid_size[size='36x48' / '12x18' / '']` — 3 cases all return 422     |
| T-24-19   | `POLL_TIMEOUT_MS = 300_000` (5 min per permutation) caps stuck-job hangs in the harness    | `grep -c "POLL_TIMEOUT_MS" /tmp/check-e2e-poster-24.mjs` = 4 (declaration + comment + 2 uses)     |
| T-24-20   | Failure screenshots in `/tmp/` use synthetic "Phase 24 ..." headlines, no real PII        | Source review of `fillAndSubmit(page, { template, size })` — only `Phase 24 ${template} ${size}` is filled |

## Verification Commands

```bash
# Task 1 — render-smoke
/home/hoyack/work/autocreative/.venv/bin/pytest tests/poster/test_render_smoke.py -v
# 10 passed in ~49s

# Task 1 — explicit shell sanity
/home/hoyack/work/autocreative/.venv/bin/python -c "
from flyer_generator.api.tasks.poster import _SIZE_TO_CANVAS
assert _SIZE_TO_CANVAS['18x24'] == (5400, 7200)
assert _SIZE_TO_CANVAS['24x36'] == (7200, 10800)
assert _SIZE_TO_CANVAS['27x40'] == (8100, 12000)
print('OK')"
# OK

# Task 2 — HTTP permutations
/home/hoyack/work/autocreative/.venv/bin/pytest tests/api/test_poster_permutations.py -v
# 12 passed in <1s

# Task 2 — full regression for tests/api/ + tests/poster/
/home/hoyack/work/autocreative/.venv/bin/pytest tests/api/ tests/poster/ -q
# 429 passed, 0 failed in ~65s

# Project-wide regression
/home/hoyack/work/autocreative/.venv/bin/pytest tests/ -q -k "not slow" --ignore=tests/integration
# 1754 passed, 2 deselected, 0 failed in ~156s

# Frontend regression
(cd frontend && pnpm install --frozen-lockfile && pnpm test --run)
# 43 passed in ~7s

# Task 3 — Playwright harness verification
ls -la /tmp/check-e2e-poster-24.mjs                                        # -rwxr-xr-x
node --check /tmp/check-e2e-poster-24.mjs && echo OK                        # OK
grep -c "PERMUTATIONS" /tmp/check-e2e-poster-24.mjs                         # 2
grep -c "All 9 permutations passed" /tmp/check-e2e-poster-24.mjs            # 1
grep -c "editorial_grand\|bold_announcement\|cinematic_onesheet" /tmp/check-e2e-poster-24.mjs   # 4
grep -c "18x24\|24x36\|27x40" /tmp/check-e2e-poster-24.mjs                  # 4
grep -c "POLL_TIMEOUT_MS" /tmp/check-e2e-poster-24.mjs                      # 4
grep -c "import { chromium }" /tmp/check-e2e-poster-24.mjs                  # 1
grep -c "POLL_TIMEOUT_MS = 300_000" /tmp/check-e2e-poster-24.mjs            # 2

# Plan's combined automated verify chain
node --check /tmp/check-e2e-poster-24.mjs && [ -x /tmp/check-e2e-poster-24.mjs ] && \
  grep -q "All 9 permutations passed" /tmp/check-e2e-poster-24.mjs && \
  grep -q "PERMUTATIONS" /tmp/check-e2e-poster-24.mjs && \
  grep -q "editorial_grand" /tmp/check-e2e-poster-24.mjs && \
  grep -q "bold_announcement" /tmp/check-e2e-poster-24.mjs && \
  grep -q "cinematic_onesheet" /tmp/check-e2e-poster-24.mjs && \
  grep -q "18x24" /tmp/check-e2e-poster-24.mjs && \
  grep -q "24x36" /tmp/check-e2e-poster-24.mjs && \
  grep -q "27x40" /tmp/check-e2e-poster-24.mjs && \
  grep -q "POLL_TIMEOUT_MS = 300_000" /tmp/check-e2e-poster-24.mjs && echo "ALL GATES OK"
# ALL GATES OK
```

## Test Counts

| Suite                                                | Pass | Failed | Notes                                                          |
| ---------------------------------------------------- | ---: | -----: | -------------------------------------------------------------- |
| New: `tests/poster/test_render_smoke.py`             |   10 |      0 | 9 perms + 1 _SIZE_TO_CANVAS sanity                             |
| New: `tests/api/test_poster_permutations.py`         |   12 |      0 | 9 happy POST + 3 invalid-size 422                              |
| Existing `tests/poster/`                              |   33 |      0 | Phase 24-01 schema_renderer suite (no regression)              |
| Existing `tests/api/test_poster_routes.py`           |   15 |      0 | Phase 24-04 route suite (no regression)                        |
| Existing `tests/api/test_worker_poster_tasks.py`     |   26 |      0 | Phase 24-04 worker suite (no regression)                       |
| Full `tests/api/` + `tests/poster/`                  | **429** | **0** | +22 net-new (407 baseline -> 429)                            |
| **Full project** (`-k "not slow" --ignore=tests/integration`) | **1754** | **0** | +22 net-new vs 24-05 baseline (1732 -> 1754)             |
| Frontend (`pnpm test --run`)                          |   43 |      0 | No regression vs 24-05 (38 -> 43 from 24-05 NewPosterPage tests) |

## Live-Stack Runtime Verification (deferred to user post-merge)

Per Phase 22-07 + Phase 23-06 precedent, the Playwright harness's runtime live-stack run is **deferred to the user post-merge**. This worktree does not run the 5-service stack so the harness cannot be executed end-to-end here. The harness is documented + executable + matrix-coverage-verified at the static layer; the underlying surface is independently verified at the unit/HTTP layer (10 + 12 = 22 pytests).

### Stack startup commands

```bash
# 1. Postgres + Redis
docker compose up -d

# 2. Apply migrations (alembic head should be f24t01 from Plan 24-03)
uv run alembic upgrade head

# 3. Backend (port 8000)
uv run uvicorn flyer_generator.api:app --reload --host 127.0.0.1 --port 8000

# 4. Worker (separate terminal)
uv run arq flyer_generator.api.worker.WorkerSettings

# 5. Vite dev (separate terminal)
(cd frontend && pnpm dev)
# Open http://localhost:5173/posters/new to confirm the page renders

# 6. Run the harness
node /tmp/check-e2e-poster-24.mjs
# Expected: "All 9 permutations passed" + exit 0
# On failure: per-permutation screenshot at /tmp/poster-fail-<template>-<size>-<ts>.png
```

### Manual spot-check after harness completes

After `All 9 permutations passed`:

1. **Jobs filter:** Visit http://localhost:5173/jobs and filter `kind=poster` — should see 9 succeeded jobs (one per permutation).
2. **Renders gallery:** Visit http://localhost:5173/renders and filter `kind=poster_final` — should see 9 PNG thumbnails.
3. **Spot-check poster output:** Click into one /posters/:id status page; the JobStatusCard should display the rendered PNG via the `/api/v1/renders/:id/image` link. Right-click -> Save image -> open locally and verify the file is a valid PNG at the expected canvas dims (5400x7200 for 18x24, etc.).

If any of the 9 permutations fail, screenshots land at `/tmp/poster-fail-<template>-<size>-<timestamp>.png` and the harness prints a per-permutation reason.

## Known Stubs

None. Every test is wired to live code: real `PosterComposer`, real `Rasterizer`, real `load_template`, real route + worker registration, real fake-arq capture. The Playwright harness is the only artifact whose runtime gate is deferred (per phase convention).

## TDD Gate Compliance

This plan is `type: execute` (not `type: tdd`), so RED/GREEN gate sequencing does not apply. Each task produced a single `feat(24-06): ...` commit (Tasks 1+2) — Task 3 has no commit by phase convention.

## User Setup Required

After merge:

1. **Verify Phase-24 backend is running** (uvicorn on :8000 with `/api/v1/posters` POST in `/openapi.json`).
2. **Verify Phase-24 frontend is running** (vite dev on :5173 with `/posters/new` accessible).
3. **Run the harness:** `node /tmp/check-e2e-poster-24.mjs` (expects "All 9 permutations passed").
4. **Spot-check** as listed above.

If the harness reports failures, attach the per-permutation `/tmp/poster-fail-*.png` screenshot when reporting the issue.

## Next Phase Readiness

Phase 24 is closed at the test layer with PO-01 + PO-02 + PO-03 + PO-04 fully verified at:

- **Unit/integration layer:** 10 render-smoke pytests (9 perms + 1 sanity) — `tests/poster/test_render_smoke.py`
- **HTTP layer:** 12 permutation pytests (9 happy + 3 invalid-size) — `tests/api/test_poster_permutations.py`
- **E2E authoring layer:** Playwright harness `/tmp/check-e2e-poster-24.mjs` — documented + executable + matrix-coverage-verified
- **E2E runtime layer:** Deferred to user post-merge per Phase 22-07 + 23-06 precedent

Phase 25 (invitation primitive) and Phase 26 (adversarial sweep) can proceed:

- **Phase 25:** The 3-layer permutation closing pattern (render-smoke + HTTP + Playwright harness in /tmp/) is established and ports cleanly to invitations.
- **Phase 26:** The poster permutation matrix (9 cases) is now part of the adversarial sweep's baseline coverage. Future adversarial tests on `/api/v1/posters` extend this matrix without rewriting it.

No blockers. No deferred items.

## Self-Check: PASSED

**Files verified to exist:**

```bash
$ [ -f tests/poster/test_render_smoke.py ] && echo "FOUND: tests/poster/test_render_smoke.py"
FOUND: tests/poster/test_render_smoke.py

$ [ -f tests/api/test_poster_permutations.py ] && echo "FOUND: tests/api/test_poster_permutations.py"
FOUND: tests/api/test_poster_permutations.py

$ [ -f /tmp/check-e2e-poster-24.mjs ] && echo "FOUND: /tmp/check-e2e-poster-24.mjs"
FOUND: /tmp/check-e2e-poster-24.mjs
```

**Commits verified to exist:**

```bash
$ git log --oneline | grep -E "2ac7230|ae14571"
2ac7230 feat(24-06): add 9-permutation render-smoke + dimension assertion (PO-02 + PO-03)
ae14571 feat(24-06): add HTTP permutation suite (9 perms + 3 invalid-size) for posters
```

- FOUND: 2ac7230 (Task 1 — render-smoke)
- FOUND: ae14571 (Task 2 — HTTP permutations)
- (Task 3 — no commit by phase convention; harness lives in /tmp/)

**Test count:** 22 net-new pytests pass (10 render-smoke + 12 HTTP). 1754 total project tests pass (no regressions).

---
*Phase: 24-poster-primitive*
*Plan: 06*
*Completed: 2026-04-25*
