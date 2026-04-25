---
phase: 24-poster-primitive
plan: 04
subsystem: api
tags: [poster, worker, route, arq, fastapi, parallel-id, compensating-enqueue, tdd, canvas-dimensions]

# Dependency graph
requires:
  - phase: 24-poster-primitive-01
    provides: load_template + 3 shipped JSON templates (editorial_grand / bold_announcement / cinematic_onesheet)
  - phase: 24-poster-primitive-02
    provides: FlyerGenerator(canvas_dimensions=(W, H)) injectable canvas
  - phase: 24-poster-primitive-03
    provides: PosterCreateRequest + PosterRecord + JobKind.POSTER + alembic f24t01
  - phase: 23-postcard-primitive
    provides: parallel-id ORM contract, compensating-enqueue pattern, BLOCKER-2 module-scope import pattern
provides:
  - task_generate_poster (arq worker) registered in ALL_TASKS
  - POST /api/v1/posters route registered in ROUTERS with compensating-enqueue
  - _size_to_canvas_dimensions defense-in-depth gate past Pydantic Literal
  - _validate_template_slug T-24-08 path-traversal mitigation
  - End-to-end HTTP -> worker -> single-PNG-artifact flow at injected canvas dims
affects:
  - 24-05  # frontend creator at /posters/new + status wrapper around JobStatusCard
  - 24-06  # FE Jobs/Renders filter entries for poster + poster_final
  - 26     # adversarial sweep covers POST /api/v1/posters with the rest of the catalog

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Worker pipeline-reuse: task_generate_poster instantiates FlyerGenerator(canvas_dimensions=size_to_dim(size)) and threads the existing flyer pipeline (Comfy + vision + composer + rasterizer) at print-canvas dims — no fork."
    - "BLOCKER-2 module-scope imports of load_template + FlyerGenerator (mirrors postcard worker), enabling direct-invocation tests to patch via patch('flyer_generator.api.tasks.poster.X')."
    - "Defense-in-depth size validation: _size_to_canvas_dimensions raises ValueError on unknown size literals (T-24-14), independent of the schema-layer Pydantic Literal['18x24','24x36','27x40']."
    - "Compensating-enqueue with strict greppable guard: route file body has zero 'str(exc)' occurrences — error_detail is exactly {reason, type} (T-24-12)."
    - "_build_flyer_input maps poster payload to FlyerInput with subtype='info' (locked decision; posters are announcement-shaped, not date-anchored)."

key-files:
  created:
    - flyer_generator/api/tasks/poster.py
    - flyer_generator/api/routes/posters.py
    - tests/api/test_worker_poster_tasks.py
    - tests/api/test_poster_routes.py
  modified:
    - flyer_generator/api/tasks/__init__.py
    - flyer_generator/api/routes/__init__.py

key-decisions:
  - "Single RenderRecord(kind='poster_final') — posters ship a single PNG, no front/back/pdf split (already established in 24-03)."
  - "Worker reuses artifact_root_flyer settings field rather than introducing a new env var; output is namespaced under <artifact_root_flyer>/posters/<job_id>.png so it never collides with flyer outputs at <artifact_root_flyer>/<job_id>.png."
  - "task_generate_poster slot in ALL_TASKS is between task_generate_postcard and task_generate_post (matches JobKind enum ordering POSTCARD -> POSTER -> SOCIAL_POST)."
  - "posters.router slot in ROUTERS is between postcards.router and social.router (matches the same JobKind ordering)."
  - "_build_flyer_input uses subtype='info' which triggers the Phase 22 vision prompt branch naming TITLE + DESCRIPTION + ORG_CREDIT zones — appropriate for a poster, where DETAILS / FEE_BADGE zones would be empty."
  - "No GET /api/v1/posters/{id} detail route — locked decision in 24-CONTEXT.md. Status page (24-05) uses existing JobStatusCard which reads JobRecord.result_ref via GET /api/v1/jobs/{id} and renders the resulting /api/v1/renders/{render_id}/image URL."

patterns-established:
  - "Worker pipeline-reuse pattern for v1.1 primitives: instantiate FlyerGenerator with the right canvas_dimensions, map request fields onto FlyerInput, run the existing pipeline. No new generator code needed — just a translator and a canvas-dim mapping."
  - "Defense-in-depth size mapping: every size-literal-driven primitive should have both a schema-layer Literal AND a worker-layer mapping function that raises ValueError on unknown values, ensuring the JobRecord transitions to FAILED with a typed error_detail rather than corrupting downstream math."

requirements-completed: [PO-01, PO-02, PO-04]

# Metrics
duration: 9min
completed: 2026-04-25
---

# Phase 24 Plan 04: Poster Worker + Route Summary

**`task_generate_poster` (arq worker) + `POST /api/v1/posters` route wire the poster primitive end-to-end: a single HTTP request flows from the FE client through to a single PNG artifact persisted on disk + indexed in DB, at print canvas dims (5400×7200 / 7200×10800 / 8100×12000) via the existing flyer pipeline.**

## Performance

- **Duration:** ~9 min (4 commits including 2 TDD RED/GREEN gate pairs)
- **Started:** 2026-04-25T07:57:47Z
- **Completed:** 2026-04-25T08:06:16Z
- **Tasks:** 2 / 2 complete
- **Commits:** 4 (Task 1 RED+GREEN, Task 2 RED+GREEN)
- **Files created:** 4 source/test
- **Files modified:** 2 barrels
- **Tests added:** 41 (26 worker + 15 route)
- **Full tests/api/ regression:** 374 passed, 0 failed (333 baseline + 41 = 374)

## Accomplishments

- **PO-01 closed (POST surface):** `POST /api/v1/posters` accepts a `PosterCreateRequest` body, persists a `JobRecord(kind=POSTER, status=QUEUED)`, enqueues `task_generate_poster` via arq, and returns 202 + `JobCreated{job_id}`. Compensating-enqueue flips the JobRecord to FAILED with typed error_detail on arq failure.
- **PO-02 closed (pipeline reuse):** The worker calls `FlyerGenerator(canvas_dimensions=size_to_dim(size))` with the locked 3-value mapping (300 DPI portrait): `"18x24"` → `(5400, 7200)`, `"24x36"` → `(7200, 10800)`, `"27x40"` → `(8100, 12000)`. The entire flyer pipeline (Comfy + vision + composer + rasterizer + FlyerOutput) operates at the injected canvas — no forked renderer.
- **PO-04 partial (worker side):** Worker writes 1 `RenderRecord(kind="poster_final")` + 1 `PosterRecord(id=job_id, ...)` (parallel-id contract) + flips `JobRecord` to SUCCEEDED with `result_ref = render.id`. Jobs/Renders filter routes for `poster` / `poster_final` will land in 24-05/06.
- **Threat mitigations honored:** T-24-08 (path-traversal slug guard before `load_template`), T-24-12 (compensating-enqueue with zero `str(exc)` substrings + secret-leak test), T-24-13 (single async-with sessionmaker block ensures rollback on render failure — verified by `test_task_render_failure_rolls_back`), T-24-14 (defense-in-depth `_size_to_canvas_dimensions` past the Pydantic Literal).
- **Zero regression.** Full `tests/api/` suite: 374 passed, 0 failed (vs 333 baseline post-24-03 + 41 from this plan).

## Task Commits

Each task was committed atomically per the TDD cycle:

1. **Task 1 RED — Failing worker tests** — `2f01587` (test): 26 direct-invocation tests covering BLOCKER-2 module imports, T-24-08 path-traversal guard, _size_to_canvas_dimensions for the 3 locked sizes, parallel-id contract, single `RenderRecord(kind="poster_final")` emission, canvas_dimensions threading, compensating rollback on render failure, and ALL_TASKS registration.
2. **Task 1 GREEN — `task_generate_poster` worker** — `7403f38` (feat): Worker + module-scope imports + `_size_to_canvas_dimensions` + `_validate_template_slug` + `_build_flyer_input` + ALL_TASKS registration. All 26 worker tests pass; full worker suite (64 tests across flyer + postcard + poster) green.
3. **Task 2 RED — Failing route tests** — `903e74a` (test): 15 route tests covering POST happy paths for the 3 locked sizes, 422 validation (invalid size, missing required fields, extra='forbid'), compensating-enqueue with typed error_detail, secret-leak defense-in-depth, ROUTERS registration, and the strict greppable `str(exc)` guard.
4. **Task 2 GREEN — `POST /api/v1/posters` route** — `6ff6a3f` (feat): Route + ROUTERS registration. All 15 route tests pass; full `tests/api/` suite (374 tests) green.

REFACTOR gate: not needed — both GREEN implementations were minimal and clean on first pass; the worker mirrored the postcard worker structurally and the route mirrored the postcard route minus the GET detail surface.

## Files Created/Modified

### Created

- **`flyer_generator/api/tasks/poster.py`** (~210 lines) — `task_generate_poster` arq worker + helpers:
  - Module-scope imports of `load_template` (from `flyer_generator.poster.schema_renderer.loader`) and `FlyerGenerator` (from `flyer_generator`) — BLOCKER-2 patch points.
  - `_SIZE_TO_CANVAS` dict + `_size_to_canvas_dimensions(size)` mapping the 3 locked literals to (W, H).
  - `_validate_template_slug(template_name)` rejecting `.json` / `/` / `\\` (T-24-08).
  - `_build_flyer_input(payload)` translating poster fields to a `FlyerInput(subtype="info", ...)`.
  - Async task body: mark_running -> validate -> load_template -> build flyer_input -> FlyerGenerator(canvas_dimensions=...) -> generate -> save PNG -> 1 RenderRecord + 1 PosterRecord (parallel-id) -> mark_succeeded.
- **`flyer_generator/api/routes/posters.py`** (~80 lines) — POST route only:
  - `create_poster` handler: persists JobRecord(QUEUED) -> compensating-enqueue try/except -> returns 202.
  - On arq exception: fresh sessionmaker -> JobRecord.FAILED with `error_detail = {"reason": "enqueue_failed", "type": type(exc).__name__}` -> re-raise.
  - Zero `str(exc)` substrings in file body (T-24-12 strict guard).
- **`tests/api/test_worker_poster_tasks.py`** (~590 lines) — 26 direct-invocation worker tests using existing `sessionmaker_fx` + `tmp_path` fixtures.
- **`tests/api/test_poster_routes.py`** (~280 lines) — 15 route tests using existing `client` + `fake_arq_pool` + `sessionmaker_fx` fixtures, plus a `test_str_exc_not_in_route_file_body` that reads the route file body and asserts no `str(exc)` substring.

### Modified

- **`flyer_generator/api/tasks/__init__.py`** — added `from flyer_generator.api.tasks.poster import task_generate_poster`, inserted `task_generate_poster` between `task_generate_postcard` and `task_generate_post` in `ALL_TASKS` (matches JobKind enum ordering), and added it to sorted `__all__`.
- **`flyer_generator/api/routes/__init__.py`** — added `posters` to the imports tuple, inserted `posters.router` between `postcards.router` and `social.router` in `ROUTERS`, and added `posters` to sorted `__all__`.

## Diffs (key sections)

### `tasks/poster.py` — module-scope imports (BLOCKER-2)

```python
from flyer_generator import FlyerGenerator
from flyer_generator.api.models import PosterRecord, RenderRecord
from flyer_generator.api.tasks._state import (
    mark_failed, mark_running, mark_succeeded,
)
from flyer_generator.models import FlyerInput
# NOTE: BLOCKER-2 module-scope import — patchable via
# patch("flyer_generator.api.tasks.poster.load_template").
from flyer_generator.poster.schema_renderer.loader import load_template
```

### `tasks/poster.py` — size mapping + canvas threading

```python
_SIZE_TO_CANVAS: dict[str, tuple[int, int]] = {
    "18x24": (5400, 7200),
    "24x36": (7200, 10800),
    "27x40": (8100, 12000),
}

# In task body:
canvas_dimensions = _size_to_canvas_dimensions(size)
gen = FlyerGenerator(
    settings=settings,
    http_client=http_client,
    canvas_dimensions=canvas_dimensions,
)
out = await gen.generate(flyer_input, template=template)
```

### `tasks/poster.py` — parallel-id PosterRecord persist

```python
async with sessionmaker() as s:
    render = RenderRecord(
        kind="poster_final",
        file_path=str(artifact_path.resolve()),
        comfy_job_id=getattr(out, "comfy_job_id", None),
        vision_verdict=(
            out.final_vision_verdict.model_dump(mode="json")
            if getattr(out, "final_vision_verdict", None) is not None
            else None
        ),
    )
    s.add(render)
    await s.flush()  # assign render.id

    poster = PosterRecord(
        id=job_id,                    # parallel-id (no new_ulid default)
        template=template_name,
        size=size,
        brand_kit_slug=payload.get("brand_kit_slug"),
        content_payload=payload,
        render_id=render.id,
    )
    s.add(poster)
    await s.commit()
```

### `routes/posters.py` — compensating-enqueue (T-24-12)

```python
try:
    await request.app.state.arq_pool.enqueue_job(
        "task_generate_poster",
        job_id=job_id,
        payload=payload,
    )
except Exception as exc:
    async with request.app.state.sessionmaker() as s2:
        row = await s2.get(JobRecord, job_id)
        if row is not None:
            row.status = JobStatus.FAILED
            row.error_detail = {
                "reason": "enqueue_failed",
                "type": type(exc).__name__,
            }
            await s2.commit()
    raise
```

## Test Counts

| Suite                                                   | Pass | Failed | Notes                                                                                  |
| ------------------------------------------------------- | ---: | -----: | -------------------------------------------------------------------------------------- |
| New: `tests/api/test_worker_poster_tasks.py`            |   26 |      0 | Module imports + size mapping + slug guard + 3 sizes happy + 3 canvas-dim threading + load_template smoke + 3 failure paths + content_payload + artifact path + ALL_TASKS |
| New: `tests/api/test_poster_routes.py`                  |   15 |      0 | 5 happy/3-sizes + 6 422 validation + 2 compensating-enqueue + ROUTERS smoke + str(exc) grep |
| Existing `tests/api/test_worker_postcard_tasks.py`      |   23 |      0 | No regression                                                                          |
| Existing `tests/api/test_postcard_routes.py`            |   12 |      0 | No regression                                                                          |
| Existing `tests/api/test_worker_tasks.py`               |   ~ |      0 | No regression                                                                          |
| **Full `tests/api/`**                                   | **374** | **0** | +41 vs 333 baseline post-24-03                                                       |

## Threat Mitigations Implemented

| Threat ID | Mitigation                                                                                            | Verified by                                                                                                |
| --------- | ----------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| T-24-08   | `_validate_template_slug` rejects `.json` / `/` / `\\` BEFORE `load_template`                         | 4 parametrized worker tests + path-traversal failure test marks JobRecord FAILED                            |
| T-24-12   | `error_detail = {reason, type}`; route file body contains zero `str(exc)` substrings                 | `test_post_poster_compensating_enqueue_marks_failed` + `_no_secret_leak` + `test_str_exc_not_in_route_file_body` |
| T-24-13   | All RenderRecord + PosterRecord writes happen inside a single `async with sessionmaker()` block       | `test_task_render_failure_rolls_back` asserts 0 PosterRecord and 0 RenderRecord rows committed on crash    |
| T-24-14   | Schema-level Literal (24-03) + worker-level `_size_to_canvas_dimensions` defense-in-depth (this plan) | `test_size_to_canvas_dimensions_unknown_raises_ValueError` + `test_task_bogus_size_raises_and_marks_failed` |
| T-24-15   | Client cannot influence job_id; route generates `str(ulid.ULID())` server-side                        | N/A (architectural — verified by code review)                                                              |

## Verification Commands

```bash
.venv/bin/pytest tests/api/test_worker_poster_tasks.py tests/api/test_poster_routes.py -v
# 41 passed

.venv/bin/python -c "from flyer_generator.api.tasks import ALL_TASKS, task_generate_poster; \
  from flyer_generator.api.routes import posters, ROUTERS; \
  assert task_generate_poster in ALL_TASKS; assert posters.router in ROUTERS; print('OK')"
# OK

.venv/bin/python -c "from flyer_generator.api.worker import WorkerSettings; \
  from flyer_generator.api.tasks.poster import task_generate_poster; \
  assert task_generate_poster in WorkerSettings.functions; print('OK')"
# OK

grep -c "task_generate_poster" flyer_generator/api/tasks/__init__.py
# 3 (import + ALL_TASKS + __all__)

grep -c "posters" flyer_generator/api/routes/__init__.py
# 3 (import + ROUTERS + __all__)

grep -c "str(exc)" flyer_generator/api/routes/posters.py
# 0 (T-24-12 grep guard)

grep -cE "_validate_template_slug|bare slug" flyer_generator/api/tasks/poster.py
# 4 (function def + 2 comment refs + error message)

grep -c "canvas_dimensions" flyer_generator/api/tasks/poster.py
# 5 (kwarg threading + value)

.venv/bin/pytest tests/api/ -q
# 374 passed, 0 failed (no regressions)
```

## Decisions Made

None beyond what was locked in `24-04-PLAN.md`, `24-CONTEXT.md`, `24-01-SUMMARY.md`, `24-02-SUMMARY.md`, and `24-03-SUMMARY.md`. Plan executed exactly as written:

- Worker mirrored the postcard worker structurally (BLOCKER-2 module-scope imports, T-XX-XX path-traversal guard, parallel-id assertion, compensating rollback on render failure).
- Route mirrored the postcard route modulo: no GET detail surface, single artifact response (JobCreated only), task name `task_generate_poster`, JobKind.POSTER.
- `_size_to_canvas_dimensions` matched the locked mapping in `24-CONTEXT.md` and `24-04-PLAN.md::<patterns>`.
- `_build_flyer_input` used `subtype="info"` per the locked decision in `24-CONTEXT.md`.

## Deviations from Plan

None — plan executed exactly as written.

The plan's `<action>` block specified:

- Task 1: "≥18 tests" — delivered **26** worker tests (3 module imports + 4 size mapping + 5 slug guard parametrized + 1 slug guard accept + 3 happy 3-sizes + 3 canvas-dim threading parametrized + 1 load_template smoke + 4 failure paths + 1 content_payload + 1 artifact path + 1 ALL_TASKS).
- Task 2: "≥10 tests" — delivered **15** route tests (5 happy/3-sizes + 6 422 validation + 2 compensating-enqueue + 1 ROUTERS smoke + 1 str(exc) grep).
- All 28+ new tests requested by `<verification>` delivered (26 + 15 = **41**).

The TDD gate sequence was followed for both tasks:

- Task 1: RED commit (`2f01587`) — `ModuleNotFoundError` at collection time, confirmed before implementation. GREEN commit (`7403f38`) — 26/26 worker tests pass + 64-test worker suite green.
- Task 2: RED commit (`903e74a`) — 15/15 fail with FileNotFoundError on route module + ROUTERS lookup miss. GREEN commit (`6ff6a3f`) — 15/15 route tests pass + 374-test full tests/api suite green.

## Issues Encountered

None.

## TDD Gate Compliance

The plan declares `type: tdd`. All 4 commit-pair gates exist in order:

- Task 1 RED  (`test(24-04): ...`) → `2f01587`
- Task 1 GREEN (`feat(24-04): ...`) → `7403f38`
- Task 2 RED  (`test(24-04): ...`) → `903e74a`
- Task 2 GREEN (`feat(24-04): ...`) → `6ff6a3f`

No REFACTOR commit was needed — both GREEN implementations were minimal and clean on first pass.

## Known Stubs

None. Every code path is wired and tested. The poster's `_build_flyer_input` translator uses the request's `brand_kit_slug` as a placeholder for `FlyerInput.org` until a future plan surfaces a brand_kit-derived org name (this is documented in the function's docstring and is consistent with the postcard worker's analogous treatment — not a stub).

## User Setup Required

None — no external service configuration required for this plan. Existing settings (`artifact_root_flyer`, `database_url`, `redis_url`, `anthropic_api_key`, `comfycloud_api_key`) carry over.

## Next Phase Readiness

This plan closes the API/worker layer for posters. Plan 24-05 (frontend creator + status page) and 24-06 (Jobs/Renders filter entries) can proceed:

- **24-05 frontend:** `frontend/src/pages/posters/new.tsx` posts to `POST /api/v1/posters` (this plan) and reads `JobStatusCard` (existing). `PosterCreateRequest` schema (24-03) is the FE form contract; size + template Selects enumerate the 3 locked sizes + `list_templates()` (24-01).
- **24-06 Jobs/Renders filters:** `JobKind.POSTER` (24-03) + `RenderRecord.kind = "poster_final"` (this plan) are emitted at the right places in the API; FE filter entries map directly.

No blockers. No deferred items.

## Self-Check: PASSED

**Files:**

- FOUND: flyer_generator/api/tasks/poster.py
- FOUND: flyer_generator/api/routes/posters.py
- FOUND: tests/api/test_worker_poster_tasks.py
- FOUND: tests/api/test_poster_routes.py
- FOUND: flyer_generator/api/tasks/__init__.py (modified)
- FOUND: flyer_generator/api/routes/__init__.py (modified)

**Commits:**

- FOUND: 2f01587 (Task 1 RED — failing worker tests)
- FOUND: 7403f38 (Task 1 GREEN — task_generate_poster + ALL_TASKS)
- FOUND: 903e74a (Task 2 RED — failing route tests)
- FOUND: 6ff6a3f (Task 2 GREEN — POST /api/v1/posters + ROUTERS)

**Test count:** 41 new tests pass (26 worker + 15 route). 374 tests in `tests/api/` pass (no regressions vs 333 post-24-03 baseline + 41 = 374).

---
*Phase: 24-poster-primitive*
*Plan: 04*
*Completed: 2026-04-25*
