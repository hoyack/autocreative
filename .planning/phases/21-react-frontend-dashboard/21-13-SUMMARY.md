---
phase: 21-react-frontend-dashboard
plan: 13
subsystem: api
tags: [backend, gap-closure, brand-kits, pagination, enqueue-compensation, tdd, wr-02, wr-03, in-03]

# Dependency graph
requires:
  - phase: 21-react-frontend-dashboard
    plan: 05
    provides: list_brand_kits + create_brand_kit_fetch (the two functions this plan patches)
  - phase: 21-react-frontend-dashboard
    review: 21-REVIEW.md
    provides: WR-02 (list_brand_kits FS-fuse over-counts) + WR-03 (orphan QUEUED job on enqueue failure, brand-kits half) + IN-03 (FS-fuse items appended without sort)
provides:
  - "flyer_generator/api/routes/brand_kits.py::list_brand_kits — full-DB-slug dedup + page-invariant total + merged scraped_at desc sort (WR-02 + IN-03)"
  - "flyer_generator/api/routes/brand_kits.py::create_brand_kit_fetch — try/except compensating transition to FAILED on arq enqueue failure with typed error_detail (WR-03)"
  - "tests/api/test_brand_kits_routes.py — 2 new regression tests pinning the fixes"
affects: [21-14-final-verification]

# Tech tracking
tech-stack:
  added: []  # No new dependencies — pure logic fix
  patterns:
    - "Full-column dedup set for FS-fuse: compute set(select(Column.slug)) once at the top of the handler; dedup the FS side against that full set, not the paginated page slice. Stable across pages."
    - "Enqueue-failure compensation (mirror of Plan 21-12 Task 2): on exception from arq_pool.enqueue_job, open a FRESH session via request.app.state.sessionmaker() (request-scoped session may be inconsistent post-raise), set JobRecord.status = FAILED, write typed error_detail {reason, type} — NEVER the stringified exception (leak vector), then re-raise."
    - "Mixed naive/aware datetime sort normalization: SQLite strips tzinfo on DateTime(timezone=True) columns but Pydantic/FS-loaded datetimes are aware. Sort key must coerce naive datetimes to UTC before comparison."

key-files:
  created: []
  modified:
    - "flyer_generator/api/routes/brand_kits.py — rewrote list_brand_kits (WR-02 + IN-03), wrapped create_brand_kit_fetch enqueue in try/except (WR-03)"
    - "tests/api/test_brand_kits_routes.py — appended 2 regression tests: test_list_brand_kits_pagination_no_duplicates_across_pages (WR-02), test_post_brand_kit_fetch_enqueue_failure_marks_job_failed (WR-03); + `timedelta` added to datetime import"

key-decisions:
  - "[Rule 1 - Bug] Fixed a latent naive/aware datetime TypeError in the new sort step. SQLite returns naive datetimes from DateTime(timezone=True) columns, while FS-loaded BrandKit.fetched_at is tz-aware. Merging and sorting the two crashed in pytest. Added a ``_as_utc`` lambda that normalizes naive datetimes to UTC before comparison. Zero-risk narrow fix; does not alter ordering (all current callsites write UTC)."
  - "Plan-checker W2 hygiene applied: the RED pagination test uses the existing ``app`` fixture's ``app.state.settings.brand_kits_dir = tmp_path`` pattern (idiomatic for this module — see test_get_list_empty) rather than adding AppSettings.model_copy + dependency_overrides. Dropped all ``build_app``, ``ASGITransport``, ``AsyncClient``, ``create_async_engine``, ``async_sessionmaker``, ``StaticPool``, ``get_settings`` imports that the plan's sample test brought in (they were unused after switching to the idiomatic pattern)."
  - "Rewrote the RED Task 2 assertion from ``r.status_code >= 500`` to ``pytest.raises(RuntimeError)``. Reason: httpx.ASGITransport defaults to ``raise_app_exceptions=True`` — an unhandled exception in a FastAPI route surfaces to the test client as a raised Python exception rather than becoming a 5xx response. The fix path is identical (route must re-raise after compensating transition) but the test contract must match what ASGITransport actually delivers. In production Starlette's ServerErrorMiddleware renders the 5xx for real clients."
  - "Kept a single global ``merged.sort`` rather than a hybrid SQL LIMIT+OFFSET + FS tail merge. Per 21-CONTEXT.md, v1 scale is \"a few dozen kits on a single-user private instance\" — the enumerate-then-slice approach is correct and the simpler code wins. Revisit when >1000 kits lands (no phase currently plans it)."
  - "IN-03 companion fix landed in the same GREEN commit as WR-02 because it's the natural result of the merged-then-sorted algorithm — FS-only entries now interleave by recency rather than tailing unconditionally. No separate test was added; the WR-02 test's total-count + unique-union assertions already fail if the algorithm regresses."

# Metrics
duration: ~7min
completed: 2026-04-23

# WR closure evidence
review-closures:
  - "WR-02: grep ``all_db_slugs`` returns 3 matches (was 0); grep ``db_slugs = {r.slug for r in rows}`` returns 0 matches (was 1); grep ``merged.sort`` returns 1 match (new)"
  - "WR-03 (brand-kits half): grep ``except Exception`` inside create_brand_kit_fetch returns 1 match (new); grep ``\"enqueue_failed\"`` returns 1 match (new); grep ``str(exc)`` returns 0 matches (no leak)"
  - "IN-03: grep ``merged.sort(key=lambda s: _as_utc(s.scraped_at), reverse=True)`` returns 1 match — FS-only entries now sorted globally by scraped_at desc"

requirements-completed: [FE-04]
---

# Phase 21 Plan 13: Gap Closure (WR-02 + WR-03 brand-kits half + IN-03) Summary

**Closed two data-integrity warnings in `flyer_generator/api/routes/brand_kits.py` via 2 RED/GREEN TDD pairs (4 commits). `list_brand_kits` now dedups the FS fuse against the full DB slug set (stable total across pages, no duplicate slugs, merged-and-sorted by scraped_at desc). `create_brand_kit_fetch` now wraps arq `enqueue_job` in try/except, flipping the just-committed JobRecord to FAILED with typed `error_detail` ({reason, type}) before re-raising — no more orphan QUEUED rows on Redis/arq failure, no infrastructure-leaking exception strings.**

## Performance

- **Duration:** ~7 min (start 20:37:50 UTC → finish via 4 commits)
- **Tasks:** 2 (both TDD — 2 RED + 2 GREEN = 4 commits total)
- **Files modified:** 2 (route + route test file)
- **Files created:** 0
- **Test delta:** +2 backend tests (17 → 19 in `tests/api/test_brand_kits_routes.py`). Full `tests/api/` suite: 174 passed, 0 failed, 1 pre-existing warning.

## Accomplishments

### WR-02 — pagination dedup + stable total (Task 1)

- **Rewrote `list_brand_kits`:** now computes `all_db_slugs = set(select(BrandKitRecord.slug))` (a single cheap indexed-column scan) before the FS enumeration, so the filesystem fuse dedups against the FULL set of DB slugs — not just the current page's slice. This closes two defects at once:
  1. A slug present in the DB on page N is no longer misreported as "FS-only" on page N-1.
  2. `total = db_total + fs_only_count` is now page-invariant because `fs_only_count` is computed ONCE over the whole filesystem before slicing.
- **Merged + globally sorted by `scraped_at` desc (IN-03 companion):** the previous code emitted DB rows first (order_by scraped_at desc), then appended FS-only summaries in `sorted(base_dir.iterdir())` (alphabetic) order — FS-only entries always tailed the page regardless of recency. The new algorithm builds `merged = db_summaries + fs_only_summaries`, sorts globally, and slices for the page. FS-only entries now appear in the correct recency position.
- **Datetime normalization in the sort key:** SQLite returns naive datetimes from `DateTime(timezone=True)` columns; `BrandKit.fetched_at` (loaded from disk JSON) is tz-aware. Sorting the merged list crashed with `TypeError: can't compare offset-naive and offset-aware datetimes`. Added a narrow `_as_utc` helper that coerces naive datetimes to UTC before comparison. All current write sites store UTC, so this does not alter ordering — it only unblocks comparison.
- **Regression test** `test_list_brand_kits_pagination_no_duplicates_across_pages`: seeds 3 DB rows + 1 FS-only kit, paginates `limit=2`, asserts `total=4` on both pages, asserts union of slugs across pages has exactly 4 unique values, and asserts the FS-only slug appears exactly once across both pages. This test previously failed with "fs-only appeared 2 times (want 1)" on the buggy code.

### WR-03 (brand-kits half) — enqueue-failure compensation (Task 2)

- **Wrapped `enqueue_job` in try/except** inside `create_brand_kit_fetch`. On any exception from the arq pool, opens a fresh `app.state.sessionmaker()` session (request-scoped `session` may already be inconsistent after the raise), looks up the JobRecord by id, sets `status = FAILED`, and writes **typed** `error_detail = {"reason": "enqueue_failed", "type": type(exc).__name__}`. The exception is then re-raised so Starlette's ServerErrorMiddleware renders the 5xx for real clients.
- **T-21-13-04 info-disclosure guardrail:** the code deliberately does NOT stringify the exception into `error_detail`. Exception messages from arq/Redis can include the Redis URL / connection-string fragments / stack frames that leak infrastructure shape. Only the fixed reason string + exception class name are persisted.
- **Regression test** `test_post_brand_kit_fetch_enqueue_failure_marks_job_failed`: monkeypatches `fake_arq_pool.enqueue_job` to raise `RuntimeError("redis unreachable")`, asserts the RuntimeError propagates to the test client (httpx `ASGITransport` default `raise_app_exceptions=True`), then asserts the JobRecord is FAILED with `error_detail.reason == "enqueue_failed"` and that the literal `"redis"` does NOT leak into `error_detail`.

## Task Commits

1. **Task 1 RED:** `429a72d` — `test(21-13): add failing pagination regression for list_brand_kits (WR-02 RED)`.
2. **Task 1 GREEN:** `8a52f2a` — `fix(21-13): stable pagination total + dedup against full DB slug set in list_brand_kits (WR-02)`.
3. **Task 2 RED:** `e348934` — `test(21-13): add failing regression for brand-kit enqueue failure compensation (WR-03 RED)`.
4. **Task 2 GREEN:** `2b1421c` — `fix(21-13): compensate brand-kit enqueue failure with JobRecord -> FAILED (WR-03)`.

TDD gate compliance: both tasks have `test(...)` (RED) → `fix(...)` (GREEN) pairs in the git log. No REFACTOR commits were required; the GREEN code is already idiomatic and matches the existing brochure-route pattern (Plan 21-12 Task 2).

## Files Modified

- **`flyer_generator/api/routes/brand_kits.py`** — two functions touched:
  - `list_brand_kits` (WR-02 + IN-03): full rewrite of the dedup + pagination algorithm.
  - `create_brand_kit_fetch` (WR-03): try/except wrap around `arq_pool.enqueue_job`, fresh-session compensating transition, typed `error_detail`, re-raise.
- **`tests/api/test_brand_kits_routes.py`** — two regression tests appended; `datetime` import extended with `timedelta`.

## Decisions Made

See `key-decisions` in frontmatter. The highlights:

- **Rule 1 fix — naive/aware datetime TypeError in sort** — found during Task 1 GREEN first run. Narrow lambda-scoped normalization to UTC. No ordering change.
- **Plan-checker W2 hygiene** — used the existing `app.state.settings.brand_kits_dir = tmp_path` idiom rather than dependency overrides + model_copy; dropped all the unused imports the plan's sample brought in.
- **RED assertion rewrite for Task 2** — `pytest.raises(RuntimeError)` instead of `r.status_code >= 500` because `ASGITransport(raise_app_exceptions=True)` is the default; unhandled exceptions surface as Python raises to the test caller, not as 5xx responses. Production path is unchanged — Starlette still renders 5xx to real HTTP clients via `ServerErrorMiddleware`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Mixed naive/aware datetime TypeError in merged sort**
- **Found during:** Task 1 GREEN (first test run).
- **Issue:** SQLite returns naive datetimes from `DateTime(timezone=True)` columns; `BrandKit.fetched_at` (from disk JSON) is tz-aware. `merged.sort(key=lambda s: s.scraped_at, reverse=True)` crashed with `TypeError: can't compare offset-naive and offset-aware datetimes`.
- **Fix:** Added an inline `_as_utc` lambda that coerces naive datetimes to UTC (`dt.replace(tzinfo=timezone.utc)`) before comparison. Used as the `key=` callable.
- **Files modified:** `flyer_generator/api/routes/brand_kits.py` (GREEN commit).
- **Verification:** `pytest tests/api/test_brand_kits_routes.py -x -q` → 18 passed (Task 1) / 19 passed (Task 2).
- **Committed in:** `8a52f2a` (Task 1 GREEN).

**2. [Rule 3 - Blocking] RED test assertion shape mismatch with ASGITransport**
- **Found during:** Task 2 RED (first test run after writing the sample from the plan).
- **Issue:** The plan's sample RED test asserted `r.status_code >= 500`, but `httpx.AsyncClient(transport=ASGITransport(app=app))` uses `raise_app_exceptions=True` by default, so an unhandled exception in the route surfaces to the test caller as a Python raise — not a 5xx response. This is orthogonal to the actual bug (route is missing compensation); the test contract was just incorrect.
- **Fix:** Changed the assertion to `with pytest.raises(RuntimeError, match="redis unreachable"): ...`. Production behavior is unchanged — real HTTP clients still see a 5xx via Starlette's `ServerErrorMiddleware`.
- **Files modified:** `tests/api/test_brand_kits_routes.py` (RED commit).
- **Verification:** RED test now fails with the intended message "Expected FAILED, got JobStatus.QUEUED" (stale QUEUED row), proving the bug AND the test contract.
- **Committed in:** `e348934` (Task 2 RED).

**3. [Rule 3 - Blocking] `str(exc)` grep match in code comment**
- **Found during:** Task 2 GREEN post-commit grep verification.
- **Issue:** The plan's orchestrator `<success_criteria>` includes `! grep 'str(exc)' flyer_generator/api/routes/brand_kits.py` (zero matches). My initial GREEN commit had a comment "never write `str(exc)`..." which triggered 1 grep match, tripping the success criterion even though no actual code wrote `str(exc)`.
- **Fix:** Rephrased the comment to "never the stringified exception message" — same semantic guardrail, zero literal `str(exc)` occurrences.
- **Files modified:** `flyer_generator/api/routes/brand_kits.py` (folded into the Task 2 GREEN commit).
- **Verification:** `grep -c "str(exc)" flyer_generator/api/routes/brand_kits.py` → 0.
- **Committed in:** `2b1421c` (Task 2 GREEN).

**Total deviations:** 3 auto-fixed (1 Rule 1 bug, 2 Rule 3 blocking). No Rule 2 missing-critical, no Rule 4 architectural. All acceptance criteria still met.

## Issues Encountered

- **SQLite tz-aware column returns naive datetimes** — deviation #1. Well-documented SQLAlchemy + SQLite quirk; the fix is narrow and future-proof.
- **ASGITransport raise_app_exceptions=True** — deviation #2. Subtle test-harness behavior that the sample RED test didn't account for. Fix is a single-line assertion swap; production path is unaffected.
- **Orchestrator success criterion via grep** — deviation #3. Grep-based acceptance is line-sensitive; comments need to avoid the literal token. Straightforward to work around.

## Verification

- `grep -n "all_db_slugs" flyer_generator/api/routes/brand_kits.py` → 3 matches (want ≥1).
- `grep -c "db_slugs = {r.slug for r in rows}" flyer_generator/api/routes/brand_kits.py` → 0 matches (want 0).
- `grep -c "merged.sort" flyer_generator/api/routes/brand_kits.py` → 1 match (want 1).
- `grep -n "except Exception" flyer_generator/api/routes/brand_kits.py` → 2 matches (1 new in create_brand_kit_fetch, 1 pre-existing for corrupt brand.json skip in list_brand_kits).
- `grep -c '"enqueue_failed"' flyer_generator/api/routes/brand_kits.py` → 1 match (want 1).
- `grep -c "str(exc)" flyer_generator/api/routes/brand_kits.py` → 0 matches (want 0).
- `pytest tests/api/test_brand_kits_routes.py -x -q` → 19 passed (17 prior + 2 new).
- `pytest tests/api/ -x -q` → 174 passed, 0 failed, 1 pre-existing unrelated warning.

## Threat Flags

None. The patches are correctness fixes that REMOVE data-integrity holes without adding new surface. The try/except in `create_brand_kit_fetch` narrows the failure mode (no more orphan QUEUED rows); the info-disclosure guardrail (typed `error_detail`, no `str(exc)`) matches the existing `_state.mark_failed` posture (T-5). The pagination fix tightens an existing read-only path.

## Known Stubs

None. Both targets (WR-02 dedup + WR-03 compensation) are shipped end-to-end.

## Next Phase Readiness

- **WR-02 + WR-03 (brand-kits half) + IN-03 closed.** Plan 21-12 is still outstanding for WR-01 + WR-03 (brochures half) + WR-04; plan 21-14 covers final verification.
- **Pattern template established:** the try/except compensation pattern used here is identical to Plan 21-12 Task 2's brochure target. Any future creator route (social posts, campaigns, etc.) that writes a JobRecord before enqueueing should copy this pattern.
- **FS-fuse dedup template:** any future route that unions DB + filesystem entries and paginates should compute the full column set once as a dedup key, never from the paginated slice.

## Self-Check

**Files exist + tests pass:**

- `flyer_generator/api/routes/brand_kits.py` — FOUND. Contains `all_db_slugs`, `merged.sort`, `except Exception as exc:`, `"enqueue_failed"`, no `str(exc)`, no `db_slugs = {r.slug for r in rows}`.
- `tests/api/test_brand_kits_routes.py` — FOUND. 19 tests collected, all passing. New tests: `test_list_brand_kits_pagination_no_duplicates_across_pages`, `test_post_brand_kit_fetch_enqueue_failure_marks_job_failed`.
- `pytest tests/api/test_brand_kits_routes.py -x -q` → 19 passed / 1 warning / ~1.07s.
- `pytest tests/api/ -x -q` → 174 passed / 1 warning / ~4.89s.

**Commits exist:**

- `429a72d` (Task 1 RED) — FOUND.
- `8a52f2a` (Task 1 GREEN) — FOUND.
- `e348934` (Task 2 RED) — FOUND.
- `2b1421c` (Task 2 GREEN) — FOUND.

## TDD Gate Compliance

Both tasks followed the RED → GREEN sequence:

- Task 1: `429a72d` (test — RED failed on `fs-only appeared 2 times (want 1)`) → `8a52f2a` (fix — GREEN passes). Both present.
- Task 2: `e348934` (test — RED failed on `Expected FAILED, got JobStatus.QUEUED`) → `2b1421c` (fix — GREEN passes). Both present.

Neither task needed a REFACTOR commit; GREEN code is idiomatic and matches the brochure precedent.

## Self-Check: PASSED

---
*Phase: 21-react-frontend-dashboard*
*Completed: 2026-04-23*
