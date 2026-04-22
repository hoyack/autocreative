---
phase: 20-fastapi-sqlalchemy-backend
plan: 09
subsystem: api

tags: [fastapi, sqlalchemy, arq, pydantic-v2, ulid, flyer, route]

# Dependency graph
requires:
  - phase: 20-fastapi-sqlalchemy-backend
    provides: "FastAPI app factory (20-06), FlyerRecord + JobRecord ORM (20-03), FlyerCreateRequest + JobCreated schemas (20-05), task_generate_flyer arq task (20-07), test fixtures + FakeArqPool (20-06)"
provides:
  - "POST /api/v1/flyers endpoint returning 202 + {job_id}"
  - "Load-bearing commit-before-enqueue idiom (template for 20-10 brochure/social routes)"
  - "8 flyer route tests covering happy path + 7 negative validation branches"
  - "Repaired RequestValidationError handler (JSON-encodes ctx.error ValueErrors)"
affects: [20-10-brochures-social-routes, 20-11-jobs-renders-routes, 20-12-release-smoke]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "commit-before-enqueue: session.commit() BEFORE arq_pool.enqueue_job so worker never sees a job_id whose JobRecord row is not yet visible"
    - "body.model_dump(mode=\"json\") reused as BOTH the JobRecord.input_payload column AND the arq payload — round-trippable via EventInput.model_validate(payload['event'])"
    - "route enqueues by task NAME (string), never imports the task function — preserves arq decoupling"
    - "fastapi.encoders.jsonable_encoder over exc.errors() to handle Pydantic v2 custom-validator ctx.error ValueError objects"

key-files:
  created:
    - "tests/api/test_flyer_routes.py"
  modified:
    - "flyer_generator/api/routes/flyers.py"
    - "flyer_generator/api/errors.py"

key-decisions:
  - "Keep explicit ``await session.commit()`` inside the route despite the ``get_session`` dep also committing on successful exit — the explicit commit is load-bearing for the commit-before-enqueue invariant; the dep's final commit is a harmless no-op"
  - "Fix errors.py RequestValidationError handler with jsonable_encoder rather than pydantic-specific kwargs (include_context=False) because FastAPI's RequestValidationError.errors() does not forward kwargs to underlying pydantic"
  - "Bundle the errors.py fix as its own fix() commit rather than fold into the test commit, so the auto-fix is traceable and reversible independently of the test file"

patterns-established:
  - "Per-route atomic flow: build ULID → insert JobRecord(QUEUED) → commit → enqueue task by name with {job_id, payload} → return 202 + {job_id}"
  - "Test fixtures assert on fake_arq_pool.calls[i] = (func_name, args, kwargs) tuple to verify both the task name string and the payload shape"

requirements-completed: [API-06]

# Metrics
duration: 7min
completed: 2026-04-22
---

# Phase 20 Plan 09: Flyer Route Summary

**POST /api/v1/flyers async endpoint with commit-before-enqueue discipline, 8 route tests, and a JSON-encoding fix for Pydantic v2 custom-validator error bodies.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-04-22T22:58:00Z
- **Completed:** 2026-04-22T23:05:42Z
- **Tasks:** 2 (both `type="auto"`)
- **Files modified:** 3 (1 route, 1 test, 1 handler fix)

## Accomplishments

- `POST /api/v1/flyers` populated — validates `FlyerCreateRequest` (wrapping `EventInput`), inserts `JobRecord(kind=FLYER, status=QUEUED)`, commits, then enqueues `task_generate_flyer` with `{job_id, payload}` via `request.app.state.arq_pool.enqueue_job`. Returns 202 + `JobCreated{job_id}` (26-char ULID).
- 8 flyer route tests green (happy path + 7 negative validations: bad accent hex, bad event color_accent, missing event, bad brand_kit_slug, extra fields, max_bg_attempts 0, max_bg_attempts 11) plus JobRecord commit verification and brand_kit_slug payload round-trip.
- Surfaced + repaired a latent bug in `flyer_generator/api/errors.py` RequestValidationError handler: Pydantic v2's `ctx.error` field carries raw `ValueError` instances that starlette's default JSON encoder rejects. Wired `fastapi.encoders.jsonable_encoder` through the handler. All 12 existing error-mapping tests still pass; all 114 API tests green.

## Task Commits

1. **Task 1: Implement `flyer_generator/api/routes/flyers.py`** — `adc6a63` (feat)
2. **Task 2: `tests/api/test_flyer_routes.py`** — `ab41c2c` (test)
3. **Rule 1 auto-fix: RequestValidationError JSON encoding** — `bda4cf9` (fix)

## Files Created/Modified

- `flyer_generator/api/routes/flyers.py` (modified) — replaced Plan 20-06 empty-stub `APIRouter` with the populated `create_flyer` handler. 48 lines net added. Imports `ulid`, `JobKind`/`JobRecord`/`JobStatus`, `FlyerCreateRequest`, `JobCreated`.
- `tests/api/test_flyer_routes.py` (created) — 134 lines, 8 async tests, `_valid_event(**overrides)` helper. Asserts on `fake_arq_pool.calls` tuple and re-queries `JobRecord` through `sessionmaker_fx` to prove commit durability.
- `flyer_generator/api/errors.py` (modified) — 1 import + 4 lines changed in `_pydantic_validation` handler: `exc.errors()` → `jsonable_encoder(exc.errors())`. Rule 1 auto-fix; see Deviations.

## Decisions Made

- **Explicit commit in route + dep commit = redundant but safe.** The `get_session` dep in `flyer_generator/api/db.py` commits on successful exit, but the route body must already have committed BEFORE calling `enqueue_job`. The plan explicitly flags this ("deliberate; the dep's own commit on dep exit is still correct but redundant"). Kept exactly as specified in the plan.
- **`jsonable_encoder` vs `include_context=False`** for the RequestValidationError fix: FastAPI's `RequestValidationError.errors()` signature is `(self) -> Sequence[Any]` — it does NOT forward kwargs to Pydantic. Using `jsonable_encoder` is the version-stable fix that also handles any other future non-serializable ctx payloads (e.g., arbitrary Python objects from third-party validators).
- **Bundle Rule 1 fix as a separate `fix()` commit** rather than amend into Task 2 — keeps the auto-fix traceable and reversible independently. Three commits total (feat, test, fix).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] RequestValidationError handler cannot serialize Pydantic v2 `ctx.error` ValueErrors**
- **Found during:** Task 2 (first test run — `test_post_flyer_rejects_bad_event_color_accent` hit 500 instead of 422)
- **Issue:** Pydantic v2's `ValidationError.errors()` emits entries with `ctx={"error": ValueError(...)}` whenever a custom `@field_validator` raises `ValueError`. Starlette's default JSON encoder cannot serialize raw `ValueError` instances, so the 422 response never escapes the handler — it re-raises as a 500 `TypeError: Object of type ValueError is not JSON serializable`.
- **Fix:** Added `from fastapi.encoders import jsonable_encoder` and wrapped `exc.errors()` → `jsonable_encoder(exc.errors())` in the `_pydantic_validation` handler in `flyer_generator/api/errors.py`.
- **Files modified:** `flyer_generator/api/errors.py` (1 import + 4 lines)
- **Verification:** All 8 new flyer route tests pass, including the two that exercise `EventInput.color_accent` custom-validator. All 12 existing `tests/api/test_error_mapping.py` tests still pass. All 114 tests in `tests/api/` green.
- **Committed in:** `bda4cf9` (separate `fix()` commit, not folded into Task 2)

**Why this was in-scope:** Plan 20-09's must-have #2 explicitly requires "Invalid `EventInput` (e.g. bad hex accent) returns 422 via RequestValidationError handler" — the bug *directly* prevented meeting this must-have. The fix is isolated, non-architectural (no new dep, no schema change, no behavior change in the success path), and fully unit-tested by Plan 20-09's new test suite.

---

**Total deviations:** 1 auto-fixed (1 × Rule 1 — bug)
**Impact on plan:** Auto-fix was required to satisfy must-have #2. No scope creep. The fix benefits every future `@field_validator`-emitting route (brochure, social, jobs) and is the last blocker for 422 correctness across the API.

## Issues Encountered

None beyond the Rule 1 auto-fix above.

## User Setup Required

None — internal route, no external-service config.

## Next Phase Readiness

- **Plan 20-10 (brochure/social routes)** can copy `flyer_generator/api/routes/flyers.py` verbatim as the commit-before-enqueue template.
- **Plan 20-11 (jobs/renders routes)** can rely on the `jsonable_encoder`-fixed handler for 422 responses to path-param validation failures.
- **Plan 20-12 (release smoke)** should smoke-test the `POST /api/v1/flyers` happy path end-to-end once arq Redis is wired.

## Self-Check: PASSED

**Files verified:**
- FOUND: `flyer_generator/api/routes/flyers.py`
- FOUND: `tests/api/test_flyer_routes.py`
- FOUND: `flyer_generator/api/errors.py` (modified)

**Commits verified:**
- FOUND: `adc6a63` (feat: Task 1)
- FOUND: `ab41c2c` (test: Task 2)
- FOUND: `bda4cf9` (fix: Rule 1)

**Tests verified:**
- `tests/api/test_flyer_routes.py`: 8/8 pass
- `tests/api/test_error_mapping.py`: 12/12 pass (regression)
- `tests/api/` full suite: 114/114 pass

---
*Phase: 20-fastapi-sqlalchemy-backend*
*Plan: 09*
*Completed: 2026-04-22*
