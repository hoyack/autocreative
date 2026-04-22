---
phase: 20-fastapi-sqlalchemy-backend
plan: 10
subsystem: api

tags: [fastapi, brochure, social, post, campaign, arq, pydantic, http-202, json-encoder]

# Dependency graph
requires:
  - phase: 20-fastapi-sqlalchemy-backend
    provides:
      - "Plan 20-05 schemas (BrochureCreateRequest, PostCreateRequest, CampaignCreateRequest, JobCreated)"
      - "Plan 20-06 app factory + router barrel + lifespan + get_session"
      - "Plan 20-07 task names (task_generate_brochure, task_generate_post, task_generate_campaign)"
      - "Plan 20-04 ORM models (JobRecord, JobKind, JobStatus)"
provides:
  - "POST /api/v1/brochures (API-07): 202 + {job_id} + JobKind.BROCHURE row + arq enqueue"
  - "POST /api/v1/social/posts (API-08): 202 + {job_id} + JobKind.SOCIAL_POST row + arq enqueue"
  - "POST /api/v1/social/campaigns (API-09): 202 + {job_id} + JobKind.SOCIAL_CAMPAIGN row + arq enqueue"
  - "Hardened RequestValidationError handler (jsonable_encoder around exc.errors())"
  - "14 new pytest cases covering happy + 11 negative paths across 3 endpoints"
affects: [20-12, future-react-client]

# Tech tracking
tech-stack:
  added: []  # all dependencies (fastapi, sqlalchemy, ulid) inherited from earlier plans
  patterns:
    - "Plan 20-09 idiom: validate body -> commit JobRecord -> arq_pool.enqueue_job (post-commit) -> return JobCreated"
    - "Worker-task contract: enqueue with kwargs={job_id, payload}, payload = body.model_dump(mode='json')"
    - "RequestValidationError handler routes exc.errors() through jsonable_encoder so field_validator ValueError objects survive JSON serialization"

key-files:
  created:
    - "tests/api/test_brochure_routes.py"
    - "tests/api/test_social_routes.py"
  modified:
    - "flyer_generator/api/routes/brochures.py"
    - "flyer_generator/api/routes/social.py"
    - "flyer_generator/api/errors.py"

key-decisions:
  - "Both new route modules follow Plan 20-09 flyer template verbatim — three identical handlers differ only in JobKind enum value and arq task-name string."
  - "_minimal_brochure_content() helper omits cta key and uses body_paragraphs (not body) — verified against ContentSection / BrochureContent v2 forbid-extras schema."
  - "Patched RequestValidationError handler with jsonable_encoder (Rule 3 deviation) to unblock all 422 tests — pre-existing latent bug from Plan 20-06 first triggered by brand_kit_slug field_validator ValueError."

patterns-established:
  - "Three-line route body: ulid + JobRecord(...) + commit + enqueue. Identical across flyer/brochure/post/campaign."
  - "Negative-test matrix per endpoint: bad enum / bad slug / oversized list / extra fields / missing required."

requirements-completed: [API-07, API-08, API-09]

# Metrics
duration: ~30min
completed: 2026-04-22
---

# Phase 20 Plan 10: Brochure + Social Routes Summary

**Three POST endpoints (`/brochures`, `/social/posts`, `/social/campaigns`) wired to arq tasks via `JobRecord` + `arq_pool.enqueue_job`, plus a JSON-encoder fix for the 422 validation handler.**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-04-22T22:36:00Z (approx)
- **Completed:** 2026-04-22T23:06:06Z
- **Tasks:** 2
- **Files modified:** 5 (2 routes, 1 error handler, 2 test files)

## Accomplishments
- POST /api/v1/brochures (API-07) returns 202 + `{job_id}`, enqueues `task_generate_brochure`, persists JobKind.BROCHURE row.
- POST /api/v1/social/posts (API-08) returns 202 + `{job_id}`, enqueues `task_generate_post`, persists JobKind.SOCIAL_POST row.
- POST /api/v1/social/campaigns (API-09) returns 202 + `{job_id}`, enqueues `task_generate_campaign`, persists JobKind.SOCIAL_CAMPAIGN row.
- 14 new pytest cases (5 brochure + 9 social): happy paths + every documented negative path (unknown platform, unknown intent, bad slug, empty topic, empty/oversized platforms list, extra fields, missing content).
- Fixed latent RequestValidationError JSON-serialization bug — Pydantic v2 embeds raw `ValueError` objects in `ctx.error`; we now route through FastAPI's `jsonable_encoder`.

## Task Commits

Each task was committed atomically on the worktree branch (`worktree-agent-ae8dc574`):

1. **Task 1: Implement routes/brochures.py + routes/social.py** — `d13509c` (feat)
2. **Deviation Rule 3 fix: errors.py JSON-serialization** — `28e397e` (fix)
3. **Task 2: Add brochure + social route tests** — `b47da0b` (test)

_Equivalent commits on master (cross-contaminated cwd): `7571f5d`, `458f4e1`, `82a09b6`._

## Files Created/Modified
- `flyer_generator/api/routes/brochures.py` — populated POST /brochures handler (was a stub).
- `flyer_generator/api/routes/social.py` — populated POST /social/posts and POST /social/campaigns handlers (was a stub).
- `flyer_generator/api/errors.py` — wrapped `exc.errors()` with `jsonable_encoder` in the RequestValidationError handler so Pydantic v2 `ctx.error: ValueError` objects no longer crash JSON encoding.
- `tests/api/test_brochure_routes.py` — 5 tests covering 202 + missing-content + bad-slug + default-generate-images + extra-field-rejection. `_minimal_brochure_content()` helper VERIFIED against BrochureContent (`title`, `org`, `sections[body_paragraphs]`).
- `tests/api/test_social_routes.py` — 9 tests covering posts (happy + bad platform/intent/slug + empty topic) and campaigns (happy + empty list + 11-platform overflow + unknown platform in list).

## Decisions Made
- **Inline session.commit() before enqueue.** Despite `get_session` already committing on dep exit, the explicit commit ensures the JobRecord is durable BEFORE the worker can pick the job up. Documented in 20-09-PLAN.md.
- **Helper omits `cta` and uses `body_paragraphs`.** Verified against `flyer_generator/brochure/schema_renderer/content_model.py:99-137`; both `BrochureContent` and `ContentSection` use `extra="forbid"`. WARNING-3 from plan-checker explicitly avoided.
- **Reuse Plan 20-09's idiom verbatim.** Three handlers differ only in JobKind value + arq task name + Pydantic model. No abstraction — duplication keeps each endpoint searchable by string.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed RequestValidationError JSON-serialization bug**
- **Found during:** Task 2 (running `test_post_brochure_rejects_bad_slug`).
- **Issue:** Pydantic v2's `RequestValidationError.errors()` embeds the raw `ValueError` instance under `ctx.error` whenever a `field_validator` raises. The Plan 20-06 handler passed this list straight to `JSONResponse(...)`, which crashed with `TypeError: Object of type ValueError is not JSON serializable` on every 422 path that goes through a custom `field_validator` (i.e. all four `brand_kit_slug` validators in Plan 20-05 schemas). Existing tests didn't catch it because they only exercised domain-error 422s (BrandVoiceViolationError) — never the Pydantic validation path with a custom validator ValueError.
- **Fix:** Imported `fastapi.encoders.jsonable_encoder` and wrapped `exc.errors()`. `jsonable_encoder` falls back to `str(...)` for non-serializable objects, so the ValueError becomes its message string while preserving the rest of the error structure.
- **Files modified:** `flyer_generator/api/errors.py`
- **Verification:** All 14 new tests pass (4 of them exercise the now-fixed code path), and the prior 106 tests in `tests/api/` still pass (120 green total).
- **Committed in:** `28e397e` (worktree) / `458f4e1` (master).
- **Scope note:** Plan instructions said "no touches to other route files," but `errors.py` is the error handler module — not a route — and the fix was strictly necessary for the success criteria "all three route tests pass." Parallel peer Plan 20-09 hit the same bug independently and applied the same fix on their worktree (`bda4cf9 fix(20-09): JSON-encode RequestValidationError ctx.error ValueErrors`); duplicate fix on the eventual merge will be a no-op.

---

**Total deviations:** 1 auto-fixed (Rule 3 blocking).
**Impact on plan:** No scope creep. Fix was the minimum patch required to satisfy the plan's own acceptance criteria. Same fix landed in parallel by Plan 20-09 — confirms the bug was latent in Plan 20-06's handler and not specific to either route.

## Issues Encountered

- **Cross-worktree cwd contamination.** Several `Bash` commands used `cd /home/hoyack/work/autocreative && ...` from inside the worktree. That changed *out* of the worktree into the main checkout, so the original Task 1/Task 2/fix commits landed on `master` instead of the worktree branch. Recovered by cherry-picking `7571f5d 458f4e1 82a09b6` onto the worktree branch (`worktree-agent-ae8dc574`). Worktree branch now contains exactly my 3 commits; master has parallel-peer drift the orchestrator will need to reconcile separately. Future executors: prefer absolute paths in `Bash` calls instead of `cd`.

## User Setup Required

None.

## Next Phase Readiness

- All three creative-surface POST endpoints (brochure, post, campaign) are live alongside the flyer endpoint from Plan 20-09. Plus the brand-kit endpoints from Plan 20-08 and the GET endpoints from Plan 20-11.
- Plan 20-12 (smoke-test + README) can wire these into an end-to-end /healthz -> POST -> poll -> GET render-image flow.

## Self-Check: PASSED

- `flyer_generator/api/routes/brochures.py` — FOUND (populated)
- `flyer_generator/api/routes/social.py` — FOUND (populated)
- `flyer_generator/api/errors.py` — FOUND (modified)
- `tests/api/test_brochure_routes.py` — FOUND (5 tests)
- `tests/api/test_social_routes.py` — FOUND (9 tests)
- Worktree commits `d13509c`, `28e397e`, `b47da0b` — all FOUND in `git log 013bc20..HEAD`
- Test suite: 14/14 plan tests pass, full `tests/api/` 120/120 green.

---
*Phase: 20-fastapi-sqlalchemy-backend*
*Plan: 10*
*Completed: 2026-04-22*
