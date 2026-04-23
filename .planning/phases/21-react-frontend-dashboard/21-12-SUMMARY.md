---
phase: 21-react-frontend-dashboard
plan: 12
subsystem: api
tags: [backend, brochures, gap-closure, wr-01, wr-03, tdd, compensating-transition, threat-mitigation]

# Dependency graph
requires:
  - phase: 21-react-frontend-dashboard
    plan: 07
    provides: Brochure POST route + worker + BrochureRecord parallel-id pattern. This plan fixes a silent bug in the worker (wrong payload key) and a data-integrity gap in the route (stale QUEUED on enqueue failure).
provides:
  - "flyer_generator/api/tasks/brochure.py — MODIFIED. Worker now reads payload['workflow'] (matches BrochureCreateRequest.workflow field name) instead of payload['workflow_name'], so user-supplied workflow overrides actually take effect (WR-01)."
  - "flyer_generator/api/routes/brochures.py — MODIFIED. create_brochure wraps enqueue_job in try/except; on failure opens a fresh session from request.app.state.sessionmaker and flips the just-committed JobRecord to FAILED with error_detail={'reason': 'enqueue_failed', 'type': <ExcName>} before re-raising (WR-03 brochures half)."
  - "tests/api/test_worker_tasks.py — +1 regression test (test_brochure_task_honors_user_supplied_workflow) pinning the WR-01 behavior."
  - "tests/api/test_brochure_routes.py — +1 regression test (test_post_brochure_enqueue_failure_marks_job_failed) pinning the WR-03 compensating transition."
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Compensating-transition pattern for route-layer async-queue enqueue failures: wrap arq.enqueue_job in try/except, open a fresh session from request.app.state.sessionmaker (NOT the dependency-injected request-scoped session — it may be dirty/closed after the first commit), flip the just-created JobRecord to FAILED with a MINIMAL typed error_detail, then re-raise. First consumer of the pattern in the brochures route; WR-03 brand-kits half remains open for a sibling plan."
    - "error_detail minimization (T-21-12-03 mitigation): write only {'reason': <machine_token>, 'type': type(exc).__name__}. Never str(exc) — may leak Redis connection strings, file paths, or stack frames into the DB column that surfaces in GET /api/v1/jobs."
    - "ASGITransport(raise_app_exceptions=False) for route-layer regression tests that assert on 5xx response codes: the default transport re-raises application exceptions through the AsyncClient, which is the right default for most FastAPI tests but prevents asserting response.status_code >= 500 when the route intentionally re-raises after cleanup. Pattern: spin up a dedicated client with the flag flipped just for this test; keep the shared `client` fixture at the default for everything else."

key-files:
  created: []
  modified:
    - "flyer_generator/api/tasks/brochure.py (1-line fix: payload.get('workflow_name', ...) -> payload.get('workflow', ...) + updated comment)"
    - "flyer_generator/api/routes/brochures.py (+try/except block around enqueue_job + compensating sessionmaker fresh-session transition + 4-field error_detail write + re-raise)"
    - "tests/api/test_worker_tasks.py (+68 lines: 1 new test + WR-01 regression section header)"
    - "tests/api/test_brochure_routes.py (+51 lines: 1 new test + WR-03 regression section header)"

key-decisions:
  - "Use request.app.state.sessionmaker() for the compensating transition, NOT the DI-provided session. The first commit on the request session may leave the transaction in a state where a follow-up update inside the same session doesn't reliably land (depends on sessionmaker config, isolation, and how far past commit the exception fires). A fresh session is a 2-line pattern with zero coupling to the outer request lifecycle — it either commits or it doesn't."
  - "Build error_detail from {type(exc).__name__, 'enqueue_failed'} only. NEVER str(exc). The reviewer called this out specifically as T-21-12-03 in the threat register; str(RuntimeError('redis://prod-secret:6379')) would put the secret into the DB column that GET /api/v1/jobs returns over the network. The minimal typed-name payload gives the dashboard enough to render a useful error badge without exfiltrating anything."
  - "Use ASGITransport(raise_app_exceptions=False) in the Task-2 RED test. Default transport re-raises, which would make `assert r.status_code >= 500` unreachable even after the GREEN fix (the route still re-raises by design — the compensating transition is a cleanup step, not a swallow). The alternative (wrap client.post in pytest.raises) conflates the HTTP-layer contract with the exception-handler-layer contract; this approach cleanly separates them."
  - "Keep the existing `client` fixture untouched. The WR-03 test instantiates its own transport + AsyncClient locally rather than parameterizing the shared fixture; avoids perturbing the 8 other brochure-route tests that rely on the default raise-on-5xx behavior for cleaner assertions."

requirements-completed: [FE-06]

# Metrics
duration: ~8min
completed: 2026-04-23
---

# Phase 21 Plan 12: Gap Closure — WR-01 + WR-03 Brochures Half Summary

**One-liner:** Close two REVIEW warnings in the brochure subsystem: fix the one-line payload-key bug that was silently dropping every user-supplied `workflow` override (WR-01), and add a try/except compensating transition around `enqueue_job` so Redis/arq failures flip the already-committed JobRecord from QUEUED to FAILED with a typed error_detail before the 5xx surfaces (WR-03 brochures half). Four TDD commits (RED/GREEN x 2). +2 regression tests; 174 backend tests pass (was 172).

## Performance

- **Duration:** ~8 min
- **Tasks:** 2 (both TDD — 2 RED + 2 GREEN = 4 commits)
- **Files created:** 0
- **Files modified:** 4 (2 source + 2 test)

## Accomplishments

- **WR-01 closed.** `flyer_generator/api/tasks/brochure.py:78` now reads `payload.get("workflow", "turbo_landscape")` — matching the actual key produced by `BrochureCreateRequest.model_dump(mode="json")`. Old `payload["workflow_name"]` read is grep-provably gone (`grep -rn 'payload.get("workflow_name"' flyer_generator/api/tasks/` → 0 matches). User-supplied workflow overrides (e.g. `{"workflow": "foo_portrait"}`) now reach `generate_template_images` as `workflow_name="foo_portrait"`.
- **WR-03 brochures half closed.** `flyer_generator/api/routes/brochures.py::create_brochure` now wraps `arq_pool.enqueue_job` in try/except. On failure, a fresh session from `request.app.state.sessionmaker()` flips the just-committed JobRecord from QUEUED to FAILED with `error_detail={"reason": "enqueue_failed", "type": type(exc).__name__}` — deliberately excluding `str(exc)` per T-21-12-03 disposition — then re-raises so FastAPI's existing handlers still surface a 5xx to the client. The dashboard `/jobs` list will no longer show ghost QUEUED rows for failed enqueues.
- **Brand-kits half of WR-03 left open.** The plan frontmatter scopes this work to "brochures half". `flyer_generator/api/routes/brand_kits.py::create_brand_kit_fetch` has the same stale-QUEUED issue and will need the same compensating-transition pattern in a sibling plan (or a later wave of 21-12 if the orchestrator decides to bundle).
- **+2 regression tests, 100% green.** `tests/api/test_worker_tasks.py::test_brochure_task_honors_user_supplied_workflow` pins the WR-01 behavior; `tests/api/test_brochure_routes.py::test_post_brochure_enqueue_failure_marks_job_failed` pins the WR-03 compensating transition. Both RED tests were verified to fail on the pre-fix code before the GREEN fix was applied.
- **Full backend suite stays green.** `.venv/bin/pytest tests/api/ -q` → 174 passed, 1 warning (pre-existing `copy` field-shadow warning in `social/models.py` — not in scope).

## Task Commits

1. `8cbaec4` — test(21-12): RED — brochure worker must honor user-supplied workflow (WR-01).
2. `00d82dd` — fix(21-12): brochure worker reads payload['workflow'] (WR-01).
3. `045c712` — test(21-12): RED — brochure enqueue failure must flip JobRecord to FAILED (WR-03).
4. `fc63f67` — fix(21-12): compensate brochure enqueue failure with JobRecord -> FAILED (WR-03).

TDD gate compliance: both tasks have `test(...)` (RED) → `fix(...)` (GREEN) pairs in the git log in the required order. No REFACTOR commits needed; GREEN code is idiomatic on first pass.

## Files Created/Modified

**Backend source (modified):**
- `flyer_generator/api/tasks/brochure.py` — 1-line payload-key fix + updated 3-line comment block to reflect the translation contract (schema key `workflow` → callee kwarg `workflow_name`).
- `flyer_generator/api/routes/brochures.py` — added try/except wrapper around `enqueue_job`, fresh-session compensating transition, `error_detail` write with `{reason, type}`, re-raise.

**Backend tests (modified):**
- `tests/api/test_worker_tasks.py` — added WR-01 regression section + `test_brochure_task_honors_user_supplied_workflow` (68 lines added). Patches `generate_template_images`, `load_template`, `render_schema_brochure`, `Rasterizer`, `assemble_brochure_pdf` so the only thing under test is the payload-key translation.
- `tests/api/test_brochure_routes.py` — added WR-03 regression section + `test_post_brochure_enqueue_failure_marks_job_failed` (51 lines added). Uses `ASGITransport(raise_app_exceptions=False)` so the 5xx response can be asserted directly instead of propagating through the transport.

## Decisions Made

See the `key-decisions` list in the frontmatter above. Summarized:

- Fresh session via `request.app.state.sessionmaker()` rather than reusing the DI-scoped `session` — avoids relying on the outer request transaction being in a clean post-commit state.
- `error_detail` contains ONLY `{reason, type}` — no `str(exc)` — per T-21-12-03 (information-disclosure mitigation).
- `ASGITransport(raise_app_exceptions=False)` only in the WR-03 test; existing shared `client` fixture left untouched for the other 8 brochure-route tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] ASGITransport default re-raises application exceptions**
- **Found during:** Task 2 RED (running the specified `r = await client.post(...); assert r.status_code >= 500` against the pre-fix code).
- **Issue:** The plan's sample test uses the shared `client` fixture from `tests/api/conftest.py` with `r = await client.post(...)` followed by `assert r.status_code >= 500`. The shared fixture uses `ASGITransport(app=app)` which defaults to `raise_app_exceptions=True`, so any uncaught exception in a route handler propagates through `client.post(...)` as a Python exception — `r` never gets assigned. The test would need either a `pytest.raises` wrapper (conflates transport-layer and response-layer contracts) or a dedicated transport with `raise_app_exceptions=False` (cleanly separates them).
- **Fix:** Switched the test signature from `(client, fake_arq_pool, sessionmaker_fx, monkeypatch)` to `(fake_arq_pool, sessionmaker_fx, app, monkeypatch)` and instantiated a local `ASGITransport(app=app, raise_app_exceptions=False) + AsyncClient(...)` inside the test body. The other 8 brochure-route tests keep using the shared `client` fixture unchanged.
- **Files modified:** `tests/api/test_brochure_routes.py` (locally scoped to the one new test).
- **Verification:** RED test fails with the expected assertion (`Expected FAILED, got JobStatus.QUEUED`) rather than bubbling a raw `RuntimeError`; GREEN test passes with the compensating transition in place.
- **Committed in:** `045c712` (RED) and `fc63f67` (GREEN).

---

**Total deviations:** 1 auto-fixed (Rule 3 blocking: test-harness plumbing). No Rule 1 bugs, no Rule 2 missing-critical, no Rule 4 architectural.

## Threat Flags

None. No new trust boundaries, no new endpoints, no schema changes. Both fixes close existing gaps identified in 21-REVIEW.md with threat-register dispositions already assigned (T-21-12-01 Tampering mitigated via the payload-key fix; T-21-12-02 self-inflicted DoS mitigated via the compensating transition; T-21-12-03 information disclosure mitigated by minimizing `error_detail`).

## Issues Encountered

- **ASGITransport default** (deviation #1). One-off plumbing fix scoped to the new test; no production-code impact.
- **Plan's `test(...)` vs `fix(...)` commit convention.** The plan-supplied GREEN commit message uses `fix(...)` rather than `feat(...)` — this matches the plan's sample commit message verbatim and is the semantically correct type for both warnings (bug fix, not new feature). No deviation.
- **No other issues.** Both RED tests failed cleanly on the expected assertions; both GREEN fixes made them pass on the first try; full backend suite remained green throughout.

## User Setup Required

None. All tests + fixes are self-contained; no env vars, no new dependencies, no DB migrations.

## Output spec answers

Per the plan's `<output>` block:

- **WR-01 evidence (grep-verifiable absence of old bug):** `grep -rn 'payload.get("workflow_name"' flyer_generator/api/tasks/` → 0 matches. `grep -n 'payload.get("workflow",' flyer_generator/api/tasks/brochure.py` → 1 match at line 79 (the fix).
- **WR-03 evidence (grep-verifiable presence of compensating transition):** `grep -n "except Exception" flyer_generator/api/routes/brochures.py` → 1 match at line 52. `grep -n '"enqueue_failed"' flyer_generator/api/routes/brochures.py` → 2 matches (line 55 in the comment + line 63 in the `error_detail` literal). `grep -n "str(exc)" flyer_generator/api/routes/brochures.py` → 0 matches (T-21-12-03 disposition honored).
- **Regression test names (for traceability):**
  - WR-01: `tests/api/test_worker_tasks.py::test_brochure_task_honors_user_supplied_workflow`
  - WR-03: `tests/api/test_brochure_routes.py::test_post_brochure_enqueue_failure_marks_job_failed`
- **Files touched (4 total, matches plan):**
  - `flyer_generator/api/tasks/brochure.py` (fix)
  - `flyer_generator/api/routes/brochures.py` (fix)
  - `tests/api/test_worker_tasks.py` (regression test)
  - `tests/api/test_brochure_routes.py` (regression test)

## Next Phase Readiness

- **Compensating-transition pattern now documented** (see `tech-stack.patterns` above). A sibling plan closing the WR-03 brand-kits half can copy the 3-step idiom verbatim: fresh session via `request.app.state.sessionmaker()`, flip JobRecord to FAILED with minimal typed `error_detail`, re-raise.
- **ASGITransport(raise_app_exceptions=False) idiom documented** for future route-layer tests that need to assert on 5xx response codes without conflating transport-layer and response-layer contracts. Useful template when the tested route re-raises by design (e.g. after cleanup, after logging, after publishing a metric).

## Known Stubs

None introduced by this plan. Neither WR-01 nor WR-03 creates any new surface area; both are targeted fixes to existing code paths.

## Self-Check

**Files exist + modifications confirmed:**
- `flyer_generator/api/tasks/brochure.py` — MODIFIED (line 79: `workflow_name=payload.get("workflow", "turbo_landscape")`).
- `flyer_generator/api/routes/brochures.py` — MODIFIED (line 52: `except Exception as exc:`; line 63: `"reason": "enqueue_failed",`).
- `tests/api/test_worker_tasks.py` — MODIFIED (+1 test: `test_brochure_task_honors_user_supplied_workflow`).
- `tests/api/test_brochure_routes.py` — MODIFIED (+1 test: `test_post_brochure_enqueue_failure_marks_job_failed`).
- `.planning/phases/21-react-frontend-dashboard/21-12-SUMMARY.md` — CREATED (this file).

**Commits exist:**
- `8cbaec4` (Task 1 RED) — FOUND.
- `00d82dd` (Task 1 GREEN) — FOUND.
- `045c712` (Task 2 RED) — FOUND.
- `fc63f67` (Task 2 GREEN) — FOUND.

**Verify runs:**
- `.venv/bin/pytest tests/api/test_brochure_routes.py tests/api/test_worker_tasks.py -x -q` → 18 passed.
- `.venv/bin/pytest tests/api/test_worker_tasks.py::test_brochure_task_honors_user_supplied_workflow tests/api/test_brochure_routes.py::test_post_brochure_enqueue_failure_marks_job_failed -x -q` → 2 passed.
- `.venv/bin/pytest tests/api/ -q` → 174 passed, 1 warning (was 172 → +2 new tests).
- `! grep -rn 'payload.get("workflow_name"' flyer_generator/api/tasks/` → exit 0 (zero matches, `!` inverts).
- `grep -n "except Exception" flyer_generator/api/routes/brochures.py` → 1 match (line 52).
- `grep -n '"enqueue_failed"' flyer_generator/api/routes/brochures.py` → 2 matches (line 55 comment, line 63 dict key).
- `grep -n "str(exc)" flyer_generator/api/routes/brochures.py` → 0 matches.

## TDD Gate Compliance

Both tasks were TDD. Git log shows each has a `test(...)` (RED) commit before its `fix(...)` (GREEN) commit, in the required Task-1-then-Task-2 order:

- Task 1: `8cbaec4` (test RED) → `00d82dd` (fix GREEN). Present.
- Task 2: `045c712` (test RED) → `fc63f67` (fix GREEN). Present.

No REFACTOR commits. GREEN code is idiomatic on first pass; no cleanup needed.

## Self-Check: PASSED

---
*Phase: 21-react-frontend-dashboard*
*Completed: 2026-04-23*
