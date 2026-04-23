---
phase: 21-react-frontend-dashboard
plan: 07
subsystem: api+ui
tags: [backend, frontend, brochures, parallel-id, 3-artifacts, rhf, zod, tanstack-query, job-polling, fe-06]

# Dependency graph
requires:
  - phase: 20-fastapi-sqlalchemy-backend
    provides: FastAPI app + BrochureRecord ORM + existing POST /brochures route + task_generate_brochure worker. This plan EXTENDS brochures.py with a detail route and flips the worker's result_ref contract.
  - phase: 21-react-frontend-dashboard
    plan: 02
    provides: openapi-fetch client + BrochureCreateRequestBody alias + queryKeys.brochure(id) registry entry
  - phase: 21-react-frontend-dashboard
    plan: 03
    provides: React Router v7 shell with stub pages at frontend/src/pages/brochures/{new,status}.tsx (REPLACED here) and the 2 routes already wired
  - phase: 21-react-frontend-dashboard
    plan: 04
    provides: <JobStatusCard/> + useJob hook + <RenderPreview/> (PNG inline / PDF Download) + Vitest/MSW harness + <Toaster/> in main.tsx
  - phase: 21-react-frontend-dashboard
    plan: 05
    provides: renderWithProviders with <Toaster/> + matchMedia polyfill + noValidate idiom
  - phase: 21-react-frontend-dashboard
    plan: 06
    provides: form-page template (.strict() schema + RHF + zodResolver + useMutation + navigate pattern)
  - phase: 21-react-frontend-dashboard
    plan: 08
    provides: ShadCN Textarea primitive (reused here) — textarea already present from social-post form
provides:
  - "flyer_generator/api/tasks/brochure.py — MODIFIED. BrochureRecord(id=job_id) (parallel-id pattern) + result_ref = brochure.id (no longer r_front.id). Mirrors campaign-side JobRecord.id == CampaignRecord.id precedent."
  - "flyer_generator/api/schemas/brochures.py — BrochureDetail schema (extra=forbid) with front/back/pdf render_url fields."
  - "flyer_generator/api/routes/brochures.py — new GET /api/v1/brochures/{brochure_id} route. 404 on miss; 422 on short id via PathParam(min_length=26, max_length=26) guard."
  - "tests/api/test_brochure_routes.py — 3 new tests (8 total). 404 when missing, 3-URL happy path with seeded renders, 422 on short id."
  - "tests/api/test_worker_tasks.py — updated the existing brochure-task test to assert the new parallel-id contract (render_id == jid; job.result_ref == jid; brochures[0].id == jid)."
  - "frontend/src/api/openapi.snapshot.json — regenerated via build_app().openapi(); includes /api/v1/brochures/{brochure_id} GET + BrochureDetail component."
  - "frontend/src/api/schema.gen.ts — regenerated."
  - "frontend/src/components/ui/switch.tsx — new ShadCN Switch primitive."
  - "frontend/src/pages/brochures/new.tsx — REPLACED stub. RHF + zodResolver + .strict() BrochureFormSchema (contentJson + template + brand_kit_slug + workflow + style_preset + generate_images Switch). mutationFn JSON.parses textarea into body.content; POST /api/v1/brochures; toast + navigate to /brochures/:job_id."
  - "frontend/src/pages/brochures/status.tsx — REPLACED stub. <JobStatusCard/> polls the job; on succeeded, second useQuery fetches /brochures/{id} and renders 3 <RenderPreview/> entries (front PNG, back PNG, print PDF)."
  - "frontend/src/pages/brochures/new.test.tsx — 2 new tests (22 total across the suite). Malformed JSON rejection + valid submit sends parsed body.content."
affects: []

# Tech tracking
tech-stack:
  added:
    - "ShadCN Switch primitive (radix-nova registry; first use in phase 21)"
  patterns:
    - "Parallel-id pattern extension: BrochureRecord(id=job_id) in task_generate_brochure — the second polymorphic-link in the repo (CampaignRecord was the first). When a detail fuse needs a single string result_ref that points to >1 artifact, reuse the job_id as the parent row's primary key. Net change: one fewer column, one fewer query."
    - "JSON-paste textarea fallback for nested request schemas: instead of useFieldArray for BrochureContent.sections[].body_paragraphs[].bullets[], ship a Textarea validated by zod .refine(JSON.parse). Cheap to test, forwards the raw object to the server where Pydantic handles validation with extra=forbid."
    - "Field-strip on submit: the form stores `contentJson` (a string) but the server expects `content` (a parsed object). The mutationFn destructures contentJson off (`const { contentJson, ...rest } = values`) so the server never sees the extra field (extra=forbid on BrochureCreateRequest would 422 it otherwise)."
    - "userEvent.type DSL escape: `{` is a modifier token in @testing-library/user-event's `type()` keystroke parser, so literal `{` in a test input must be doubled (`{{`). Surfaced as 'Expected repeat modifier or release modifier' when typing malformed JSON literals."
    - "Conditional detail fetch via useQuery.enabled: the BrochureDetail row doesn't exist until the worker commits (task tail), so the second query is gated on `job?.status === 'succeeded'`. Avoids a 404 race while the job is still running."

key-files:
  created:
    - "frontend/src/pages/brochures/new.test.tsx (63 lines, 2 tests)"
    - "frontend/src/components/ui/switch.tsx (ShadCN, 31 lines)"
  modified:
    - "flyer_generator/api/tasks/brochure.py (+id=job_id + result_ref=brochure.id + updated docstring and log field)"
    - "flyer_generator/api/schemas/brochures.py (+BrochureDetail schema, +datetime import)"
    - "flyer_generator/api/routes/brochures.py (+get_brochure_detail route, +HTTPException/Path/BrochureDetail imports, +BrochureRecord import)"
    - "tests/api/test_brochure_routes.py (+3 detail tests, +BrochureRecord/RenderRecord imports)"
    - "tests/api/test_worker_tasks.py (updated brochure task test to verify parallel-id contract)"
    - "frontend/src/api/openapi.snapshot.json (regenerated)"
    - "frontend/src/api/schema.gen.ts (regenerated)"
    - "frontend/src/pages/brochures/new.tsx (stub → 245-line form)"
    - "frontend/src/pages/brochures/status.tsx (stub → 100-line status page)"

key-decisions:
  - "[Rule 1 - Bug] userEvent.type interprets `{` as a modifier token. The invalid-JSON test originally typed `{not valid` which aborted parsing with 'Expected repeat modifier or release modifier'. Fixed by doubling (`{{not valid`) — literal `{` followed by `not valid`. The test now actually validates the zod refine path."
  - "[Rule 1 - Bug] TS2352 in new.test.tsx: after declaring `let captured: Record<string, unknown> | null = null`, TS narrowed the type to `null` by the time we asserted fields. Re-widened through `as unknown as { ... }` so the property-access assertions type-check. Runtime behavior unchanged — the msw handler overwrites the value before the assertions run."
  - "Used build_app().openapi() to regen the OpenAPI snapshot instead of booting uvicorn + curling /openapi.json (same choice as plan 21-10 + 21-11). No network, no port dance, deterministic output."
  - "Kept the existing brochure worker test fixture (the one with mocked BrochureContent + load_template + render_schema_brochure + Rasterizer + assemble_brochure_pdf) instead of adding a new parallel-id-specific test. The update was already a one-character-level change to the assertion set — no duplicated mock scaffolding needed."
  - "Added `noValidate` to the <form> element (matches plans 21-05/06/08). Keeps zod as the single validation path in case a future field uses type='url' / type='email'. Not strictly required for this page — no HTML5-validated input types used — but infrastructure-consistency is the right default."
  - "Did NOT surface the BrochureContent nested editor (sections[].body_paragraphs[].bullets[]) in v1. RESEARCH.md line 348 recommended JSON-paste as an acceptable fallback; a polish plan can decompose it via useFieldArray when UX feedback demands it."
  - "Strip `contentJson` from the POST body. The zod schema has `contentJson` (a string); the server expects `content` (a parsed object). The mutationFn destructures `contentJson` off before spreading `rest` + injecting `content`. This matters specifically because BrochureCreateRequest has extra='forbid' — leaking contentJson would produce a 422 in production."
  - "Detail fetch is gated on job.status === 'succeeded'. The BrochureRecord row is written at the tail of task_generate_brochure, so fetching /brochures/{id} before the worker commits would 404 and then retry via TanStack Query's cache — noisy. The gate avoids that transient state entirely."

requirements-completed: [FE-06]

# Metrics
duration: ~15min
completed: 2026-04-23
---

# Phase 21 Plan 07: Brochure Creator + 3-Artifact Status Page + Backend Extension Summary

**One-liner:** Backend flips the brochure-task contract to set `BrochureRecord.id = JobRecord.id` (parallel-id, mirrors campaigns) and adds `GET /api/v1/brochures/{id}` returning all 3 render URLs. Frontend replaces the 2 plan-21-03 stubs with a JSON-paste form + a status page that wraps `<JobStatusCard/>` and renders 3 `<RenderPreview/>` entries once the job succeeds. 3 new pytest tests (16 total in the two affected files), 2 new Vitest tests (22 total across the FE suite). Closes FE-06.

## Performance

- **Duration:** ~15 min
- **Tasks:** 2 (both TDD — 2 RED commits + 2 GREEN commits + 1 chore codegen + 1 chore ShadCN = 6 total commits)
- **Files created:** 2 (new.test.tsx + switch.tsx)
- **Files modified:** 9 (3 backend source, 2 backend test, 2 frontend source pages, openapi snapshot, schema.gen.ts)

## Accomplishments

- **Backend route shipped.** `GET /api/v1/brochures/{brochure_id}` returns `BrochureDetail` with front/back/pdf render URLs. 404 when no row matches; 422 when the id is not 26 chars (ULID guard).
- **Brochure worker now uses parallel-id pattern.** `BrochureRecord(id=job_id)` at creation, `result_ref = brochure.id`. `/jobs/{id}` → `/brochures/{result_ref}` resolves directly without an extra JOIN.
- **3 new backend tests.** Covering: 404 miss, 200 happy-path with seeded 3 renders, 422 short id. Existing `test_task_generate_brochure_imports_cleanly_and_writes_records` updated to assert the new contract (`render_id == jid`, `job.result_ref == jid`, `brochures[0].id == jid`) — verifies the parallel-id assignment at both the task return value and the DB state.
- **OpenAPI regenerated without a running server.** `build_app().openapi()` dumps the schema; `openapi-typescript` consumes the snapshot. Both `/api/v1/brochures/{brochure_id}` and `BrochureDetail` component present.
- **Stub pages replaced.** Both `/brochures/new` and `/brochures/:id` now have real implementations. `grep "stub — plan 21-07 replaces"` returns 0 across `frontend/src/pages/brochures/`.
- **2 new FE tests.** Malformed JSON → zod refine error; valid submit posts parsed body.content object to `/api/v1/brochures`.
- **Typecheck + build pass.** `pnpm typecheck` exits 0; `pnpm build` emits 80.49 KB CSS / 640.49 KB JS (up from plan 21-11's 75.52 / 605.65 — the brochure form + Switch primitive add ~35 KB JS).

## Task Commits

1. `c1ec1f7` — test(21-07): RED — backend tests for parallel-id contract + detail route.
2. `d7db6e8` — feat(21-07): GREEN — BrochureDetail schema + GET /brochures/{id} + task parallel-id assignment.
3. `ff627b3` — chore(21-07): regenerate OpenAPI snapshot + schema.gen.ts.
4. `c51f9c6` — chore(21-07): add ShadCN Switch primitive (Task 2 prerequisite).
5. `d864a44` — test(21-07): RED — frontend tests for brochure creator form.
6. `09a22d8` — feat(21-07): GREEN — brochure creator + 3-artifact status page.

TDD gate compliance: Task 1 has `c1ec1f7` (test RED) → `d7db6e8` (feat GREEN); Task 2 has `d864a44` (test RED) → `09a22d8` (feat GREEN). No REFACTOR commits needed.

## Files Created/Modified

**Backend (modified):**
- `flyer_generator/api/tasks/brochure.py` — parallel-id assignment + result_ref update + updated docstring + log field rename.
- `flyer_generator/api/schemas/brochures.py` — appended `BrochureDetail` class + `datetime` import.
- `flyer_generator/api/routes/brochures.py` — appended `get_brochure_detail` route + imports (HTTPException, PathParam, BrochureDetail, BrochureRecord).
- `tests/api/test_brochure_routes.py` — 3 new detail tests + BrochureRecord/RenderRecord imports.
- `tests/api/test_worker_tasks.py` — updated brochure task test to verify parallel-id contract (render_id == jid, job.result_ref == jid, brochures[0].id == jid).

**Frontend (created):**
- `frontend/src/components/ui/switch.tsx` — ShadCN Switch primitive.
- `frontend/src/pages/brochures/new.test.tsx` — 2 tests (malformed JSON + valid submit).

**Frontend (modified):**
- `frontend/src/api/openapi.snapshot.json` — regenerated.
- `frontend/src/api/schema.gen.ts` — regenerated.
- `frontend/src/pages/brochures/new.tsx` — stub → 245 lines (RHF + zod + JSON-paste textarea + 6 fields + submit + toast + navigate).
- `frontend/src/pages/brochures/status.tsx` — stub → 100 lines (JobStatusCard + conditional BrochureDetail fetch + 3 RenderPreview entries).

## Decisions Made

- **Parallel-id pattern over option-1 (adding a separate `brochure.job_id` column).** Plan Q4 offered both approaches; option-2 wins because (a) it matches the existing campaign-side precedent, (b) it avoids a schema migration, (c) the single extra SQLAlchemy kwarg (`id=job_id`) is the only code change in the worker's DB section. No new FK, no new index.
- **Return the URL strings directly from the detail route, NOT just the render IDs.** The FE doesn't need to know the URL construction convention — the server owns it. If the `/renders/{id}/image` URL template ever changes (e.g. CDN prefix, signed URL), only the route code moves; the FE remains stable.
- **Kept the existing brochure worker test (updated assertions) rather than adding a duplicate parallel-id-specific test.** The contract change is observable in exactly three places (return value, JobRecord.result_ref, BrochureRecord.id) and the existing test already covers the BrochureRecord path. Adding assertions is cheaper than reproducing the (fairly complex) mock scaffolding for an independent test.
- **JSON-paste textarea over nested useFieldArray UI.** RESEARCH.md line 348 explicitly endorses the fallback. A useFieldArray impl for `content.sections[].body_paragraphs[].bullets[]` is a ~300-line UI that would dwarf the rest of the form. We keep it trivial and let a polish plan invest in the visual editor when users actually ask for one.
- **Switch primitive pulled fresh from radix-nova registry.** Unlike the `form.tsx` stub issue from plan 21-05, the switch entry in radix-nova is fully populated — no escape-hatch to new-york URL needed.
- **Used `build_app().openapi()` over `curl http://localhost:8000/openapi.json`.** Same rationale as plans 21-10 + 21-11 — no port dance, no network, no lifecycle.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] userEvent.type treats `{` as a modifier token**
- **Found during:** Task 2 GREEN (first test run of new.test.tsx).
- **Issue:** The malformed-JSON test typed `{not valid` into the textarea. userEvent.type parses `{...}` as a keyboard special-key directive (e.g. `{Enter}`). The input aborted with `Expected repeat modifier or release modifier or "}" but found " "`.
- **Fix:** Doubled the opening brace (`{{not valid`). userEvent.type parses `{{` as a literal `{` character, so the textarea receives `{not valid` as intended.
- **Files modified:** `frontend/src/pages/brochures/new.test.tsx`.
- **Verification:** Both tests now pass. Committed in `09a22d8`.

**2. [Rule 1 - Bug] TS2352 on `captured` re-narrowed to null**
- **Found during:** Task 2 GREEN (pnpm typecheck after first passing test run).
- **Issue:** `let captured: Record<string, unknown> | null = null;` followed by `const body = captured as { ... }` failed TS's overlap check — TS narrows `captured` to `null` via control flow, and `null` does not overlap with `{ template, content }`.
- **Fix:** Cast through `unknown` (`as unknown as { ... }`). Runtime behavior is unchanged; the msw handler mutates `captured` before the assertions read it, so the value is always the posted body at assertion time.
- **Files modified:** `frontend/src/pages/brochures/new.test.tsx`.
- **Verification:** `pnpm typecheck` now exits 0. Committed in `09a22d8`.

---

**Total deviations:** 2 auto-fixed (both Rule 1 bugs in the test file). No Rule 2 missing-critical, no Rule 3 blocking infra, no Rule 4 architectural.

## Issues Encountered

- **userEvent.type DSL modifier escaping** (deviation #1). Not a Phase-21 regression — just the first test in the phase to type literal `{`. Documented in `tech-stack.patterns` so future brochure/social/campaign tests with JSON payloads don't re-hit it.
- **TS control-flow narrowing on let-declared captured values** (deviation #2). Common enough pattern in msw-assertion tests that it's worth the `as unknown as` idiom; avoids refactoring the handler into a promise-returning one.
- **No runtime issues.** The existing matchMedia polyfill + Toaster + MemoryRouter in `test-utils.tsx` covered everything this plan needed.

## User Setup Required

None. Both tests + typecheck + build run fully offline via msw mocks + the committed OpenAPI snapshot.

## Output spec answers

Per the plan's `<output>` block:

- **Did any existing test assert `result_ref == r_front.id`?**
  **No**, strictly speaking. The only brochure-task test (`test_task_generate_brochure_imports_cleanly_and_writes_records` in `tests/api/test_worker_tasks.py`) previously asserted only `render_id is not None`. It did not pin the return value to the front-render id, so the worker change did not invalidate an explicit assertion. The test was still updated to assert the NEW contract (`render_id == jid`) — effectively UP-LEVELLING coverage from "task returns something" to "task returns the parallel-id as designed".
  Count of test updates: **1** (the single direct-invocation brochure task test). No other test in `tests/api/` referenced the task's return value.
- **Did the parallel-id assignment create any constraint conflicts?**
  **No.** `BrochureRecord.id` is `Mapped[str] = mapped_column(String(26), primary_key=True, default=new_ulid)`. Supplying `id=job_id` at construction simply bypasses the `default=new_ulid` callable — SQLAlchemy sees a concrete PK, no conflict with any PK/FK. Explicit id assignment works cleanly with the existing schema; no migration needed.
- **FE test count delta:** **+2** (20 → 22 tests across 11 files). New tests live in `src/pages/brochures/new.test.tsx`. Status-page polling + detail-fetch branches are structurally correct (typechecked, build-validated) but not under test; a polish plan can add them alongside other status-page tests (see plan 21-11's proposed polish list).

## Next Phase Readiness

- **Wave 5 close.** This plan is the last in Phase 21's Wave 5 per the orchestrator's plan table. The brochure 3-artifact UX surfaces the final creative subsystem that had an outstanding gap.
- **Parallel-id pattern documented.** Future plans adding polymorphic detail rows (e.g. a future multi-artifact flyer or a batch campaign view) can cite this plan + the campaign precedent instead of re-deriving the trade-off.
- **Textarea JSON-paste pattern reusable.** If future `*CreateRequest` schemas grow nested arrays (e.g. multi-scene video generator), the same Textarea + zod-refine + JSON.parse + field-strip idiom ships a functional form in one plan.

## Known Stubs

None introduced by this plan. The 2 stub pages from plan 21-03 (`brochures/new.tsx`, `brochures/status.tsx`) are both replaced with real implementations. `grep -r "stub — plan 21-07 replaces" frontend/src/pages/brochures/` returns 0 matches.

## Self-Check

**Backend files exist + tests pass:**
- `flyer_generator/api/tasks/brochure.py` — MODIFIED (grep `id=job_id` → 2 matches counting the kwarg and the doc reference; `result_ref = brochure.id` → 2 matches counting the code + the comment).
- `flyer_generator/api/schemas/brochures.py` — MODIFIED (grep `front_render_url|back_render_url|pdf_render_url` → 3 matches, one per field).
- `flyer_generator/api/routes/brochures.py` — MODIFIED (`get_brochure_detail` defined; `@router.get("/brochures/{brochure_id}"` present at line 50).
- `tests/api/test_brochure_routes.py` — 8 tests total (5 prior + 3 new).
- `tests/api/test_worker_tasks.py` — brochure task assertion updated.
- `.venv/bin/pytest tests/api/test_brochure_routes.py tests/api/test_worker_tasks.py -q` → 16 passed (was 13, +3).
- `.venv/bin/pytest tests/api/ -q` (full) → 172 passed (no regressions).

**Frontend files exist:**
- `frontend/src/api/openapi.snapshot.json` — contains `"/api/v1/brochures/{brochure_id}"` + BrochureDetail schema.
- `frontend/src/api/schema.gen.ts` — regenerated; includes BrochureDetail at line ~641.
- `frontend/src/components/ui/switch.tsx` — FOUND (ShadCN, 31 lines).
- `frontend/src/pages/brochures/new.tsx` — REWRITTEN. `JSON.parse(contentJson)` present (1 match). `.strict()` on BrochureFormSchema (1 match). `noValidate` on the form (1 match).
- `frontend/src/pages/brochures/status.tsx` — REWRITTEN. `client.GET("/api/v1/brochures/{brochure_id}"` (multi-line) present at line 40-42. References `front_render_url`, `back_render_url`, `pdf_render_url` (3 matches).
- `frontend/src/pages/brochures/new.test.tsx` — FOUND (2 tests).

**Commits exist:**
- `c1ec1f7` (Task 1 RED) — FOUND.
- `d7db6e8` (Task 1 GREEN) — FOUND.
- `ff627b3` (chore: schema regen) — FOUND.
- `c51f9c6` (chore: Switch primitive) — FOUND.
- `d864a44` (Task 2 RED) — FOUND.
- `09a22d8` (Task 2 GREEN) — FOUND.

**Verify runs:**
- `pnpm test --run` → 22 passed / 11 files / Duration 6.18s (was 20 / 10, +2).
- `pnpm typecheck` → exits 0.
- `pnpm build` → dist/ (80.49 KB CSS / 640.49 KB JS); exits 0.
- `grep -c "stub — plan 21-07 replaces" frontend/src/pages/brochures/` → 0 (both stub markers removed).
- `grep -c "id=job_id" flyer_generator/api/tasks/brochure.py` → 2.
- `grep -c "result_ref = brochure.id" flyer_generator/api/tasks/brochure.py` → 2.
- `grep -c "get_brochure_detail" flyer_generator/api/routes/brochures.py` → 1.
- `grep -nE "/brochures/\\{brochure_id\\}" flyer_generator/api/routes/brochures.py frontend/src/pages/brochures/status.tsx` → 2 matches (one per file).

## TDD Gate Compliance

Both tasks were TDD. Git log shows each has a `test(...)` (RED) commit before its `feat(...)` (GREEN) commit:

- Task 1: `c1ec1f7` (test RED) → `d7db6e8` (feat GREEN) → `ff627b3` (chore codegen). Present.
- Task 2: `d864a44` (test RED) → `09a22d8` (feat GREEN). Present. (Switch primitive `c51f9c6` is a non-TDD prerequisite, not a gate commit.)

No REFACTOR commits. All GREEN code is idiomatic on first pass.

## Self-Check: PASSED

---
*Phase: 21-react-frontend-dashboard*
*Completed: 2026-04-23*
