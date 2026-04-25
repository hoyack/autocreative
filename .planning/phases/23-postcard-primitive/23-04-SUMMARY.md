---
phase: 23-postcard-primitive
plan: 04
subsystem: arq-worker + http-routes
tags: [arq, fastapi, sqlalchemy, parallel-id, compensating-enqueue, blocker-2-mirror, t-23-01-mitigation, tdd, pc-01, pc-02, pc-04, pc-06]

# Dependency graph
requires:
  - phase: 23-postcard-primitive
    plan: 01
    provides: load_template + PostcardTemplateSchema (loader + JSON template registry)
  - phase: 23-postcard-primitive
    plan: 02
    provides: PostcardCreateRequest + PostcardDetail + AddressBlock + PostcardRecord + JobKind.POSTCARD + alembic f23t01
  - phase: 23-postcard-primitive
    plan: 03
    provides: render_postcard + PostcardContent + PostcardAddressBlock + assemble_postcard_pdf + PostcardPDFError
provides:
  - flyer_generator.api.tasks.postcard.task_generate_postcard (PC-04 worker; PC-06 emits 3 render kinds)
  - flyer_generator.api.tasks.postcard._validate_template_slug (T-23-01 path-traversal guard)
  - flyer_generator.api.tasks.postcard._content_from_payload (api-schema -> renderer-content translator)
  - flyer_generator.api.routes.postcards.create_postcard (PC-01 POST + PC-02 compensating-enqueue)
  - flyer_generator.api.routes.postcards.get_postcard_detail (PC-01 GET, 3-URL fuse, parallel-id)
  - task_generate_postcard registered in ALL_TASKS (worker boot picks up via WorkerSettings.functions)
  - postcards.router registered in ROUTERS (build_app() mounts it under /api/v1)
affects:
  - 23-05 (frontend): can now call POST /api/v1/postcards + GET /api/v1/postcards/{id}; OpenAPI snapshot regeneration unblocked.
  - 23-06 (frontend creator + status pages): nav route /postcards/new and status route /postcards/:id can wire to live endpoints.

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "BLOCKER-2 module-scope imports (load_template + render_postcard + Rasterizer + assemble_postcard_pdf) so direct-invocation tests can patch via patch('flyer_generator.api.tasks.postcard.X')"
    - "T-23-01 path-traversal guard mirrors Phase 22 T-22-10: refuse '.json' / '/' / '\\\\' BEFORE load_template's file-path branch"
    - "Parallel-id pattern (PostcardRecord.id := job_id) mirrors Phase 21-07 brochure parallel-id; the route generates the ULID, the worker assigns it"
    - "Compensating-enqueue (Phase 21-12 WR-03 mirror): on arq.enqueue_job exception, flip JobRecord -> FAILED with error_detail = {'reason': 'enqueue_failed', 'type': type(exc).__name__} using a fresh sessionmaker — NEVER stringifies the exception"
    - "asyncio.to_thread wrapping for 3 sync collaborators (render_postcard, Rasterizer.rasterize, assemble_postcard_pdf) keeps the arq event loop responsive"
    - "Artifact namespace reuse: <artifact_root_brochure>/postcards/<job_id>/ (no new env var; CONTEXT.md Claude's discretion)"
    - "Route 26-char PathParam guard (min_length=26, max_length=26) for postcard_id matches the brochure pattern"
    - "Route returns 404 'postcard not found' for missing ids; PathParam-rejected malformed ids surface as 422 first (T-16 disposition: trust the ULID guard)"

key-files:
  created:
    - flyer_generator/api/tasks/postcard.py  (~190 lines — task_generate_postcard + _validate_template_slug + _content_from_payload + module-scope BLOCKER-2 imports)
    - flyer_generator/api/routes/postcards.py  (~125 lines — create_postcard + get_postcard_detail with compensating-enqueue try/except)
    - tests/api/test_worker_postcard_tasks.py  (~553 lines — 18 tests covering all 14 plan must_haves)
    - tests/api/test_postcard_routes.py  (~292 lines — 13 tests covering all 15 plan must_haves)
  modified:
    - flyer_generator/api/tasks/__init__.py  (added postcard import + ALL_TASKS entry + __all__ entry)
    - flyer_generator/api/routes/__init__.py  (added postcards import + ROUTERS entry + __all__ entry)

key-decisions:
  - "Reused artifact_root_brochure rather than introducing a new artifact_root_postcard env var (CONTEXT.md Claude's discretion). The /postcards/<job_id>/ subdir namespace prevents collision with brochure outputs and avoids a settings sprawl when both creative primitives share the same printable-PDF + pair-of-PNGs disk shape."
  - "_content_from_payload() lives in the worker (not in api.schemas.postcards) so the schema_renderer package never imports api/. The mapping is explicit + 1:1 on the 4 rendering-relevant fields (headline / body / image_hint / address_block); brand_kit_slug + template are handled outside the renderer payload."
  - "Compensating-enqueue rewrites NEVER ``str(exc)``: the file body has zero occurrences of the literal substring. Even the docstring + comment language uses 'stringifies the exception' so a future grep guard against accidental str(exc) leakage stays clean."
  - "Routes use a fresh ``sessionmaker()`` block on the compensating-enqueue path (NOT the request-scoped session) because the request session may be in a dirty state after the route's prior commit succeeded but the enqueue failed. Mirrors Phase 21-12 WR-03 verbatim."
  - "Worker module-scope imports: 4 BLOCKER-2 patchable names + 2 PostcardContent / PostcardAddressBlock helpers. The PostcardContent imports are also module-scope (rather than inside _content_from_payload) so the same patching mechanism is available for tests that want to stub the content-validation step."
  - "PR-tests assert NO secret-string leak in error_detail after enqueue failure: not just the typed-shape contract but also that the original exception message ('redis unreachable secret://internal') does not appear anywhere in str(error_detail). Defense-in-depth against accidental future regressions where a maintainer might add a 'message' or 'detail' field that re-introduces the leak."

requirements-completed: [PC-01, PC-02, PC-04, PC-06]

# Metrics
duration: ~12min
tasks: 2
files_created: 4
files_modified: 2
tests_added: 31
tests_total_local: 31  # 18 worker + 13 routes
tests_total_subsystem: 286  # full tests/api/ green
completed: 2026-04-23
---

# Phase 23 Plan 04: Postcard Worker + Routes Summary

**End-to-end wiring for the postcard pipeline: ``task_generate_postcard`` arq worker (BLOCKER-2 module-scope imports + T-23-01 path-traversal guard + parallel-id) + ``POST /api/v1/postcards`` (compensating-enqueue) + ``GET /api/v1/postcards/{id}`` (3-URL fuse). After this plan, a single HTTP request enqueues a job that produces 3 artifacts (front PNG, back PNG, print PDF) and 1 ``PostcardRecord`` discoverable via the parallel-id GET route.**

## Performance

- **Duration:** ~12 minutes
- **Tasks:** 2 (both autonomous, both TDD)
- **Files created:** 4 (2 code + 2 test)
- **Files modified:** 2 (tasks barrel + routes barrel)
- **Tests added:** 31 (18 worker + 13 routes)
- **Subsystem-wide tests:** 286 across full ``tests/api/`` (no regressions vs. 23-03 baseline of 255 — added exactly 31 new)

## Accomplishments

### Task 1 — task_generate_postcard worker (RED `b2ba45f`, GREEN `50430f8`)

- Implemented ``flyer_generator/api/tasks/postcard.py`` with:
  - **BLOCKER-2 module-scope imports** (4 patchable names): ``load_template``, ``render_postcard``, ``Rasterizer``, ``assemble_postcard_pdf`` — all importable at module top-level so ``patch("flyer_generator.api.tasks.postcard.X")`` works in direct-invocation tests. Also imports ``PostcardContent`` + ``PostcardAddressBlock`` at module scope.
  - **T-23-01 path-traversal guard** (``_validate_template_slug``): refuses ``.json`` suffix + ``/`` + ``\\`` BEFORE ``load_template`` activates its file-path branch. Mirrors Phase 22 T-22-10 (flyer worker) verbatim.
  - **``_content_from_payload`` translator**: maps 1:1 between the request body (4 rendering-relevant fields) and ``PostcardContent`` so the schema_renderer package keeps zero dependencies on ``api/``.
  - **Parallel-id pattern**: ``PostcardRecord(id=job_id, ...)`` so ``JobRecord.id == PostcardRecord.id``. Returns ``postcard.id`` as ``result_ref``; the ``mark_succeeded`` helper stamps it into ``JobRecord.result_ref``.
  - **3 RenderRecords** (``postcard_front``, ``postcard_back``, ``postcard_pdf``) written under ``<artifact_root_brochure>/postcards/<job_id>/``. Reusing ``artifact_root_brochure`` rather than introducing a new env var (CONTEXT.md Claude's discretion); the ``/postcards/`` subdir namespaces the path so it never collides with brochure outputs.
  - **asyncio.to_thread** wrapping for 3 sync collaborators (``render_postcard``, ``rasterize``, ``assemble_postcard_pdf``) to keep the arq event loop responsive.
- Registered ``task_generate_postcard`` in ``ALL_TASKS`` (between ``task_generate_brochure`` and ``task_generate_post``) so ``WorkerSettings.functions = ALL_TASKS`` automatically picks it up at worker boot. Verified empirically:
  ```text
  WorkerSettings.functions = [
      'task_fetch_brand_kit', 'task_generate_flyer',
      'task_generate_brochure', 'task_generate_postcard',  # new
      'task_generate_post', 'task_generate_campaign',
  ]
  ```

### Task 2 — POST + GET routes (RED `dc6452b`, GREEN `60370f2`)

- Implemented ``flyer_generator/api/routes/postcards.py`` with:
  - **POST /api/v1/postcards**: validates body via ``PostcardCreateRequest``, generates a server-side ULID, persists ``JobRecord(id=ulid, kind=POSTCARD, status=QUEUED, input_payload=body)``, then calls ``arq_pool.enqueue_job("task_generate_postcard", job_id=..., payload=...)``. Returns 202 + ``JobCreated{job_id}``.
  - **Compensating-enqueue** (Phase 21-12 WR-03 mirror): wraps the ``enqueue_job`` call in ``try/except``; on any exception, opens a fresh ``sessionmaker()`` block, flips the ``JobRecord`` row to ``FAILED`` with ``error_detail = {"reason": "enqueue_failed", "type": type(exc).__name__}``, then re-raises. **Never** stringifies the exception — file body contains zero occurrences of ``str(exc)``.
  - **GET /api/v1/postcards/{postcard_id}**: 26-char ``PathParam`` guard (``min_length=26, max_length=26``); returns 404 ``"postcard not found"`` when no row matches; otherwise returns ``PostcardDetail`` with ``front_render_url`` / ``back_render_url`` / ``pdf_render_url`` (each ``/api/v1/renders/{id}/image`` or ``None`` when the corresponding ``render_*_id`` is ``NULL``). Mirrors ``get_brochure_detail`` shape verbatim.
- Registered ``postcards.router`` in ``ROUTERS`` (between ``brochures.router`` and ``social.router``) so ``build_app()`` picks it up automatically.

## Task Commits

Each task followed the TDD RED -> GREEN gate with explicit commits:

1. **Task 1 RED:** `b2ba45f` — `test(23-04): add failing tests for task_generate_postcard worker`
   (18 tests; all fail with ``ModuleNotFoundError: No module named 'flyer_generator.api.tasks.postcard'``)
2. **Task 1 GREEN:** `50430f8` — `feat(23-04): add task_generate_postcard worker (PC-01/PC-02/PC-04/PC-06)`
   (18/18 worker tests pass; 38/38 worker-tests-combined pass — no regressions in tests/api/test_worker_tasks.py)
3. **Task 2 RED:** `dc6452b` — `test(23-04): add failing tests for postcard routes (POST + GET)`
   (13 tests; all fail at the POST endpoint with HTTP 404 — route not registered)
4. **Task 2 GREEN:** `60370f2` — `feat(23-04): add postcard routes (POST + GET) with compensating-enqueue`
   (13/13 route tests pass; 286/286 full ``tests/api/`` pass — no regressions)

Plan metadata commit (this SUMMARY.md) will follow.

## Files Created

### Production code
- ``flyer_generator/api/tasks/postcard.py`` (~190 lines)
- ``flyer_generator/api/routes/postcards.py`` (~125 lines)

### Tests
- ``tests/api/test_worker_postcard_tasks.py`` (~553 lines, 18 tests)
- ``tests/api/test_postcard_routes.py`` (~292 lines, 13 tests)

### Files Modified
- ``flyer_generator/api/tasks/__init__.py`` — import + ALL_TASKS entry + __all__ entry for ``task_generate_postcard``
- ``flyer_generator/api/routes/__init__.py`` — import + ROUTERS entry + __all__ entry for ``postcards``

## Verification Run Log

```bash
# Task 1 GREEN gate — worker tests
$ .venv/bin/pytest tests/api/test_worker_postcard_tasks.py -v
# -> 18 passed in 1.01s

# Task 1 + 22-05 worker regression check (no flyer-worker breakage)
$ .venv/bin/pytest tests/api/test_worker_tasks.py tests/api/test_worker_postcard_tasks.py -v
# -> 38 passed in 2.18s

# Task 2 GREEN gate — route tests
$ .venv/bin/pytest tests/api/test_postcard_routes.py -v
# -> 13 passed in 0.73s

# Plan-spec verification — both registrations
$ .venv/bin/python -c "
from flyer_generator.api.tasks import ALL_TASKS, task_generate_postcard
from flyer_generator.api.routes import postcards, ROUTERS
assert task_generate_postcard in ALL_TASKS
assert postcards.router in ROUTERS
print('OK')
"
# -> OK

# Worker-side smoke (WorkerSettings.functions includes the new task)
$ .venv/bin/python -c "
from flyer_generator.api.worker import WorkerSettings
from flyer_generator.api.tasks.postcard import task_generate_postcard
assert task_generate_postcard in WorkerSettings.functions
print('OK')
"
# -> OK

# Full tests/api/ regression sweep
$ .venv/bin/pytest tests/api/ -q
# -> 286 passed, 1 warning in 12.69s   (no regressions vs. 23-03 baseline of 255)
```

## Acceptance Criteria — All Pass

### Task 1 — Worker

- [x] `flyer_generator/api/tasks/postcard.py` exists
- [x] `from flyer_generator.postcard.schema_renderer.loader import load_template` (1 line — module-scope BLOCKER-2)
- [x] `from flyer_generator.postcard.stages.pdf import assemble_postcard_pdf` (1 line)
- [x] `from flyer_generator.stages.rasterizer import Rasterizer` (1 line)
- [x] `def _validate_template_slug` (1 occurrence — T-23-01 guard)
- [x] `bare slug` substring (1 occurrence — error message body)
- [x] `id=job_id` (3 occurrences — parallel-id assignment + 2 documentation comments)
- [x] `kind="postcard_front"|kind="postcard_back"|kind="postcard_pdf"` (3 occurrences — one per RenderRecord)
- [x] `asyncio.to_thread` (3 occurrences — render + rasterize + PDF assembly)
- [x] `task_generate_postcard` references in barrel (3 occurrences — import + ALL_TASKS + __all__)
- [x] All 18 worker tests pass

### Task 2 — Routes

- [x] `flyer_generator/api/routes/postcards.py` exists
- [x] `@router.post` (1 occurrence — POST /postcards)
- [x] `@router.get` (1 occurrence — GET /postcards/{postcard_id})
- [x] `JobKind.POSTCARD` (1 occurrence — JobRecord persistence)
- [x] `task_generate_postcard` (1 occurrence — enqueue_job call)
- [x] `"reason": "enqueue_failed"` (1 occurrence — typed error_detail)
- [x] `type(exc).__name__` (1 occurrence — typed error_detail)
- [x] **`str(exc)` count: 0** (file has zero occurrences of the literal substring — defense-in-depth against future leak regressions)
- [x] `front_render_url|back_render_url|pdf_render_url` (3 init lines + verified 3 conditional branches via Test 12 + Test 13)
- [x] `session.get(PostcardRecord` (1 occurrence — detail lookup)
- [x] `min_length=26, max_length=26` (1 occurrence — PathParam ULID guard)
- [x] `postcards` references in routes barrel (3 occurrences — import + ROUTERS + __all__)
- [x] All 13 route tests pass

## Decisions Made

- **Re-used `artifact_root_brochure` for postcards:** The `/postcards/<job_id>/` subdir namespaces the path so it never collides with brochure outputs; saves a settings-sprawl issue while both creative primitives share the same disk shape (PNG pair + PDF). CONTEXT.md explicitly permits Claude's discretion here.
- **`_content_from_payload` lives in the worker, not in api.schemas:** Keeps the schema_renderer package free of `api/` dependencies. The mapping is 1:1 on the 4 rendering-relevant fields; `template` and `brand_kit_slug` are handled outside the renderer payload.
- **Compensating-enqueue uses fresh sessionmaker(), not the request-scoped session:** Mirrors Phase 21-12 WR-03 — the request session may be dirty after the prior commit succeeded but enqueue failed. A fresh session is the only safe way to commit the FAILED transition.
- **Module-scope imports include PostcardContent + PostcardAddressBlock:** The 2 helpers are only used inside `_content_from_payload`, so module-local imports would also work. Keeping them at module scope mirrors the 4 BLOCKER-2 patchable names and makes the module a single, easily-greppable import block.
- **Defense-in-depth on enqueue-leak test:** Test 10 asserts both the typed-shape contract `error_detail == {"reason": "enqueue_failed", "type": "RuntimeError"}` AND that the original exception message (`"redis unreachable secret://internal"`) does not appear anywhere in `str(error_detail)`. Catches future regressions where a maintainer might add a `"message"` or `"detail"` field that re-introduces the leak.
- **Doc-comment language hygiene:** Re-worded both `str(exc)` references in the route file's docstring + comment to use "stringifies the exception" wording. The file body now has zero occurrences of the literal `str(exc)` substring, so a CI grep guard against accidental leak stays clean. Behavior is unchanged; only documentation language tightened.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Documentation hygiene] Removed `str(exc)` literal substring from docstring + comment**

- **Found during:** Task 2 GREEN acceptance-criteria grep.
- **Issue:** Plan acceptance criterion explicitly forbids `str(exc)` substring anywhere in the route file. My initial implementation correctly did NOT use `str(exc)` in the compensating-enqueue logic, but the docstring + comment used the literal phrase ``NEVER ``str(exc)``` to document the prohibition. A strict grep matched those two lines.
- **Fix:** Reworded both occurrences to "stringifies the exception" / "stringify the exception". Behavior unchanged; the file body now has zero `str(exc)` occurrences so a CI grep guard against accidental leak stays clean.
- **Files affected:** `flyer_generator/api/routes/postcards.py` (docstring line 6 + inline comment line 71).
- **Committed in:** `60370f2` (Task 2 GREEN — fold-in before commit).

**Total deviations:** 1 — documentation language tightening to satisfy strict grep criterion. No code-side deviations; no scope creep.

## Issues Encountered

None — both tasks went RED -> GREEN on first GREEN attempt. The route file's docstring `str(exc)` references were caught during the post-implementation acceptance-grep sweep (before the GREEN commit) so the final commit shows clean output for all 11 acceptance grep checks.

## Threat Flags

None — the trust-boundary mitigations documented in the plan's `<threat_model>` are all satisfied:

- **T-23-12 (Information disclosure: compensating-enqueue leaks redis URI / stack via str(exc)):** Mitigated. `error_detail` is exactly `{"reason": "enqueue_failed", "type": type(exc).__name__}` — the file body contains zero occurrences of `str(exc)`. Test 10 asserts both the typed-shape contract AND the absence of the secret message in `str(error_detail)`.
- **T-23-13 (Tampering: payload['template'] = "../etc/passwd" reads arbitrary file via load_template):** Mitigated. `_validate_template_slug` rejects `.json` suffix + `/` + `\\` BEFORE `load_template`. 4 parametrized worker tests verify rejection (`../etc/passwd`, `foo.json`, `subdir/template`, `subdir\\template`); 1 happy-slug test verifies bare slugs pass.
- **T-23-14 (DoS: worker crashes mid-render leaving orphan files / DB rows):** Mitigated. All RenderRecord + PostcardRecord writes happen inside a single `async with sessionmaker()` block; on exception SQLAlchemy rolls back uncommitted rows. Test 7 (`test_task_generate_postcard_render_failure_rolls_back`) verifies that `render_postcard` raising `RuntimeError` results in 0 RenderRecords + 0 PostcardRecords committed. Files-on-disk before crash are orphaned but harmless (artifact root namespaced by job_id).
- **T-23-15 (Tampering: concurrent POSTs with same client-supplied id):** N/A — client cannot influence job_id; route generates `str(ulid.ULID())` server-side.
- **T-23-16 (Information disclosure: GET /postcards/{id} leaks DB-presence signal):** Accepted — same disposition as Phase 21-07 brochure detail (T-16). Trust the 26-char ULID guard, return 404 for both not-found and malformed-but-passes-PathParam ids.

No new threat surface introduced beyond the registered items.

## Known Stubs

None — every artifact this plan claims to provide is wired and tested:

- **task_generate_postcard worker:** Wired into ALL_TASKS, picked up by WorkerSettings.functions. The Comfy hero-generation step is intentionally omitted (CONTEXT.md decision: postcard front uses `image_placeholder` fallback fill until a future plan adds Comfy); the renderer's fallback fill handles this path gracefully. Plan 23-03's renderer was explicit about this stub being a deliberate choice for the worker-plan tier.
- **POST + GET routes:** Both wired into ROUTERS, mounted at `/api/v1/postcards`. End-to-end: POST returns 202 + ULID; GET returns 200 + 3 URLs (or 404 / 422).
- **Compensating-enqueue:** End-to-end coverage including the secret-string leak guard test.
- **Parallel-id:** End-to-end — Test 10 asserts `PostcardRecord.id == job_id`; route + worker share the same ULID.

The image-generation path being a stub is documented in the plan's `<context>` notes: *"No image-generation pipeline yet for postcards — the front panel uses an image_placeholder element which renders a fallback fill. Hero generation is future work (out of scope per CONTEXT.md ... and the locked decision list does NOT mention Comfy hero gen for postcards)."* This is an intentional architectural decision, not an unfinished surface.

## User Setup Required

None — no external service configuration required. The arq worker picks up the new task automatically via `WorkerSettings.functions = ALL_TASKS`. Existing `redis://` and `database_url` settings cover the new endpoint.

## Next Phase Readiness

- **Plan 23-05 / 23-06 (frontend):** Both endpoints are live and OpenAPI-discoverable. The frontend can:
  1. Regenerate the OpenAPI snapshot to pick up `PostcardCreateRequest` + `PostcardDetail` + `JobCreated` schemas.
  2. Wire `frontend/src/pages/postcards/new.tsx` to `POST /api/v1/postcards`.
  3. Wire `frontend/src/pages/postcards/status.tsx` to `GET /api/v1/postcards/{id}` (3-artifact figure grid: `front_render_url` / `back_render_url` / `pdf_render_url`).
  4. Add `postcard` to `frontend/src/pages/jobs/list.tsx::KINDS` + `statusPathFor`.
  5. Add 3 new render kinds (`postcard_front`, `postcard_back`, `postcard_pdf`) to `frontend/src/pages/renders/gallery.tsx::KINDS`.
- **Future Comfy hero generation for postcards:** When postcards gain Comfy hero generation (deferred), the worker's structure already accommodates it — insert a `generate_template_images`-equivalent call between `_validate_template_slug` and `render_postcard`, then thread the resulting bytes into the renderer (currently the renderer's `image_placeholder` always renders fallback fill).

## TDD Gate Compliance

Both Task 1 and Task 2 were tagged `tdd="true"`. RED -> GREEN gates satisfied with explicit commits visible in `git log`:

- **Task 1 RED:** `b2ba45f` `test(23-04): add failing tests for task_generate_postcard worker` (18 tests; all fail with `ModuleNotFoundError`)
- **Task 1 GREEN:** `50430f8` `feat(23-04): add task_generate_postcard worker (PC-01/PC-02/PC-04/PC-06)` (18/18 worker tests pass; 38/38 across worker tests pass; no regressions)
- **Task 2 RED:** `dc6452b` `test(23-04): add failing tests for postcard routes (POST + GET)` (13 tests; all fail at POST with HTTP 404 — route not registered)
- **Task 2 GREEN:** `60370f2` `feat(23-04): add postcard routes (POST + GET) with compensating-enqueue` (13/13 route tests pass; 286/286 full tests/api/ pass — no regressions)

No REFACTOR commits needed — both GREEN passes were minimal-correct on first try, with one in-place documentation-language tightening during Task 2 GREEN (committed alongside the GREEN work, not as a separate commit).

## Self-Check: PASSED

Verified each created/modified file exists and each commit hash is reachable:

- `flyer_generator/api/tasks/postcard.py` FOUND (created)
- `flyer_generator/api/tasks/__init__.py` FOUND (modified — ALL_TASKS + __all__)
- `flyer_generator/api/routes/postcards.py` FOUND (created)
- `flyer_generator/api/routes/__init__.py` FOUND (modified — ROUTERS + __all__)
- `tests/api/test_worker_postcard_tasks.py` FOUND (created — 18 tests)
- `tests/api/test_postcard_routes.py` FOUND (created — 13 tests)
- Commit `b2ba45f` (Task 1 RED) FOUND
- Commit `50430f8` (Task 1 GREEN) FOUND
- Commit `dc6452b` (Task 2 RED) FOUND
- Commit `60370f2` (Task 2 GREEN) FOUND

31 tests across 2 new test files green; 286 tests/api/ tests green (no regressions vs. 23-03 baseline of 255 — added exactly 31 new). Plan-level holistic registration smoke `task_generate_postcard in ALL_TASKS and postcards.router in ROUTERS and task_generate_postcard in WorkerSettings.functions` returns OK.

---

*Phase: 23-postcard-primitive*
*Completed: 2026-04-23*
