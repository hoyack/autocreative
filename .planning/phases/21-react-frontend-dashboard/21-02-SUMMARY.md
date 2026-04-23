---
phase: 21-react-frontend-dashboard
plan: 02
subsystem: ui
tags: [frontend, api-client, openapi, codegen, tanstack-query, typescript]

# Dependency graph
requires:
  - phase: 20-fastapi-sqlalchemy-backend
    provides: Live /openapi.json served on :8000 for the initial snapshot; the committed snapshot is what every future gen:api:snapshot run consumes, so the backend is only needed once per schema change.
  - phase: 21-react-frontend-dashboard
    plan: 01
    provides: frontend/ scaffold (Vite 8 + React 19 + TS 5.9), pnpm@10.14.0 packageManager pin, gen:api / gen:api:snapshot scripts already declared in package.json, Vite dev proxy /api/* -> http://localhost:8000
provides:
  - frontend/src/api/openapi.snapshot.json -- committed 25,758-byte copy of /openapi.json (10 paths, 29 named schemas, OpenAPI 3.1.0)
  - frontend/src/api/schema.gen.ts -- 1087-line generated TS types covering all 6 Phase 20 route groups (brand-kits, flyers, brochures, social/posts, social/campaigns, jobs, renders). Zero `any`.
  - frontend/src/api/client.ts -- configured openapi-fetch client + 5 request-body aliases, 4 response aliases, ApiErrorBody, TERMINAL_STATUSES / TerminalStatus / isTerminalStatus type guard (72 lines, zero `any`).
  - frontend/src/lib/queryKeys.ts -- TanStack Query key registry for job, jobs, brandKits, brandKit, renders, brochure (38 lines, pure TypeScript).
  - frontend/src/vite-env.d.ts -- Vite ambient types (enables `import.meta.env.VITE_API_URL`).
affects: [21-03-data-layer, 21-04-brand-kits, 21-05-flyers, 21-06-brochures, 21-07-social, 21-08-campaigns, 21-09-jobs, 21-10-renders, 21-11-polish]

# Tech tracking
tech-stack:
  added:
    - "openapi-fetch@0.17.0 (runtime HTTP client, ~5 KB, typed via `paths` generic)"
    - "openapi-typescript@7.13.0 (devDep, CLI: `openapi-typescript <input> -o <output>`)"
  patterns:
    - "Committed OpenAPI snapshot pattern: `pnpm gen:api:snapshot` regenerates types from the checked-in JSON, so codegen is reproducible offline / in CI."
    - "FastAPI mounts routers with `prefix=\"/api/v1\"` (flyer_generator/api/__init__.py:39) so every path key in /openapi.json is absolute (`/api/v1/flyers`). openapi-fetch calls therefore use absolute paths that match the generated `paths` interface exactly; baseUrl defaults to empty so the browser sends same-origin requests and Vite's dev proxy forwards /api/* to :8000."
    - "Hand-written ApiErrorBody shadows the FastAPI custom error envelope (`{detail, error_type, trace_id}` from flyer_generator/api/errors.py). FastAPI's default OpenAPI does NOT declare this shape -- only the validation-error schema is emitted -- so consumers type errors via the hand-written interface."
    - "TanStack Query keys declared as `as const` tuple factories with optional-filter second element; `queryKeys.jobs({ kind: 'flyer' })` produces a stable hashable tuple, and `invalidateQueries({ queryKey: ['jobs'] })` matches the prefix."

key-files:
  created:
    - "frontend/src/api/openapi.snapshot.json (25,758 bytes, 10 paths, 29 schemas, single-line JSON)"
    - "frontend/src/api/schema.gen.ts (1087 lines, auto-generated, zero any)"
    - "frontend/src/api/client.ts (72 lines, typed openapi-fetch wrapper)"
    - "frontend/src/lib/queryKeys.ts (38 lines, TanStack Query key registry)"
    - "frontend/src/vite-env.d.ts (1 line, `/// <reference types=\"vite/client\" />`) -- needed so import.meta.env is typed"
  modified:
    - "frontend/package.json -- added `openapi-fetch@^0.17.0` (deps) and `openapi-typescript@^7.13.0` (devDeps)"
    - "frontend/pnpm-lock.yaml -- lockfile updated"

key-decisions:
  - "[Rule 1 - Bug] Used empty baseUrl (not the plan's literal \"/api/v1\") because FastAPI bakes the /api/v1 prefix into every path key in /openapi.json. The plan's client.ts sample would have produced type errors at every `paths[\"/flyers\"]` index access. Fix: baseUrl defaults to '' so the browser issues same-origin /api/v1/... requests (Vite proxy handles forwarding) and path-key indices match schema.gen.ts exactly."
  - "[Rule 3 - Blocking] Added frontend/src/vite-env.d.ts so `import.meta.env.VITE_API_URL` typechecks. Without it tsc reports TS2339 `Property 'env' does not exist on type 'ImportMeta'`."
  - "Hand-wrote ApiErrorBody rather than deriving it from schema.gen.ts because FastAPI does NOT emit the custom `{detail, error_type, trace_id}` shape in /openapi.json. Only HTTPValidationError is emitted, and that is the 422-response shape, not the generic 4xx/5xx envelope."
  - "Kept the plan's 10 path aliases verbatim in intent but rewrote every key with the absolute `/api/v1/...` prefix. Downstream plans must use absolute paths in `client.POST('/api/v1/flyers', ...)` too."

requirements-completed: [FE-02]

# Metrics
duration: 6min
completed: 2026-04-23
---

# Phase 21 Plan 02: API Client + TanStack Query Key Registry Summary

**Typed API layer every downstream plan imports: committed OpenAPI snapshot + 1087-line schema.gen.ts (zero `any`) + 72-line openapi-fetch client with 10 named aliases + 6-entry TanStack Query key registry. `pnpm gen:api:snapshot` regenerates types offline from the committed snapshot.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-04-23T12:08:48Z
- **Completed:** 2026-04-23T12:14:30Z
- **Tasks:** 3
- **Files created:** 5 (openapi.snapshot.json, schema.gen.ts, client.ts, queryKeys.ts, vite-env.d.ts)
- **Files modified:** 2 (package.json, pnpm-lock.yaml)

## Accomplishments

- Installed `openapi-fetch@0.17.0` (runtime) and `openapi-typescript@7.13.0` (devDep). Both are the latest stable majors.
- Booted the Phase 20 backend (`uvicorn flyer_generator.api:app` on :8000), snapshotted `/openapi.json` into `frontend/src/api/openapi.snapshot.json`, verified all six route groups + 29 schemas are present, then stopped the backend. The snapshot is committed so future runs of `pnpm gen:api:snapshot` regenerate types offline.
- Generated `frontend/src/api/schema.gen.ts` (1087 lines, 34 KB). Contains `export interface paths` and `export interface components`; every Phase 20 route is covered; zero `any` in the file.
- Wrote `frontend/src/api/client.ts` (72 lines). Exports `client`, `Schemas`, 5 request-body aliases, 4 response aliases, `ApiErrorBody`, `TERMINAL_STATUSES`, `TerminalStatus`, `isTerminalStatus`. baseUrl defaults to `""` so Vite's dev proxy (and eventual same-origin production mount) handle routing; the path keys match the absolute `/api/v1/...` shape emitted by FastAPI.
- Wrote `frontend/src/lib/queryKeys.ts` (38 lines). Registry covers `job`, `jobs`, `brandKits`, `brandKit`, `renders`, `brochure` -- every key every Phase 21 plan (21-04..21-11) will reference.
- `pnpm typecheck` passes against all three new files plus the pre-existing scaffold.

## Task Commits

1. **Task 1: Install openapi-* libs + snapshot /openapi.json + generate schema.gen.ts** -- `41ceb80` (feat)
2. **Task 2: Write client.ts with typed aliases** -- `9a12dbf` (feat)
3. **Task 3: Create queryKeys.ts TanStack Query registry** -- `83f4c2c` (feat)

_Orchestrator adds the metadata commit after all Wave 2 agents merge._

## Files Created/Modified

**Created:**
- `frontend/src/api/openapi.snapshot.json` -- committed OpenAPI 3.1.0 snapshot (25,758 bytes; 10 paths; 29 named schemas)
- `frontend/src/api/schema.gen.ts` -- 1087-line auto-generated TS types; `export interface paths` + `export interface components`; zero `any`
- `frontend/src/api/client.ts` -- 72-line typed openapi-fetch client + 10 named aliases + error envelope + status-literal guard
- `frontend/src/lib/queryKeys.ts` -- 38-line pure-TS TanStack Query key registry
- `frontend/src/vite-env.d.ts` -- ambient `/// <reference types="vite/client" />` so `import.meta.env` is typed

**Modified:**
- `frontend/package.json` -- added `openapi-fetch: ^0.17.0` to `dependencies` and `openapi-typescript: ^7.13.0` to `devDependencies`
- `frontend/pnpm-lock.yaml` -- regenerated lockfile (net +17/-17 lines around the two new packages)

## Decisions Made

- **baseUrl defaults to `""`, not `/api/v1`.** FastAPI bakes the `prefix="/api/v1"` mount into every path key emitted by `/openapi.json`, so the generated `paths` interface is keyed by `/api/v1/flyers` (absolute). The plan's example code used `paths["/flyers"]` and `baseUrl: "/api/v1"`, which would have produced TS2339 errors on every alias. The correct pattern: keep `baseUrl` empty so openapi-fetch calls look like `client.POST("/api/v1/flyers", ...)` (the same string the browser sends same-origin, which Vite's dev proxy already forwards to `:8000`). `VITE_API_URL` can still override when pointing at a non-default backend, but the default is empty -- no absolute URL is baked into the bundle.
- **Absolute path keys on every alias.** All 10 type aliases in `client.ts` index the generated `paths` with the absolute `/api/v1/...` key. This matches the generated types exactly and keeps downstream `client.POST(...)` call sites using the same string. Any Phase 20 schema change surfaces as a single-alias TS error in `client.ts`, not as silent drift across the phase.
- **Hand-wrote `ApiErrorBody`.** FastAPI's default OpenAPI only emits `HTTPValidationError` for the 422-response. The project's custom `{detail, error_type, trace_id}` envelope from `flyer_generator/api/errors.py` is NOT declared in `/openapi.json`, so `openapi-typescript` cannot surface it. The hand-written interface is the single source of truth for error parsing in downstream mutation hooks.
- **`vite-env.d.ts` is a one-liner.** The plan-21-01 scaffold did not create it, so `import.meta.env.VITE_API_URL` errored. A single `/// <reference types="vite/client" />` file is the Vite-standard fix (matches what `pnpm create vite` emits).
- **Did NOT install TanStack Query / react-router / RHF / zod here.** The plan limits Wave 2 to codegen + client + key registry. Those libraries arrive in plan 21-03 alongside the code that uses them.

## Routes in the Snapshot NOT Aliased in client.ts

Per the plan's output spec, these routes appear in `openapi.snapshot.json` / `schema.gen.ts` but do NOT yet have named aliases in `client.ts`. Downstream plans that need them must either add aliases to `client.ts` or index `paths[...]` ad-hoc:

| Path | Method | Reason not aliased |
|------|--------|---------------------|
| `/api/v1/brand-kits/fetch` | POST | Enqueues a scrape job. Returns 202 JobCreated. Alias exists for the request body (`BrandKitFetchRequestBody`) but not for the response because JobCreated is already aliased via the flyer POST. |
| `/api/v1/renders/{render_id}/image` | GET | Returns an image (binary content). openapi-fetch's `data` return is typed per the 200 response content block, but the plan does not declare a named response alias because the image will be referenced via URL, not fetched through the client. |
| `/healthz` | GET | Liveness check -- not part of Phase 21 UX. |

**List endpoints NOT in Phase 20 yet.** The queryKeys registry declares `jobs` (list) and `renders` (list) factories, but Phase 20 only ships singular `GET /api/v1/jobs/{job_id}` and `GET /api/v1/renders/{render_id}/image`. Plans 21-10 (jobs list page) and 21-11 (renders gallery) will need to add `GET /api/v1/jobs` and `GET /api/v1/renders` to Phase 20 first; 21-02 cannot alias what does not exist. The query-key factories are wired up-front so these plans can consume them without registry edits.

## Schema.gen.ts Oddities

- **`components["schemas"]["JobStatus"]`** is emitted as a string-literal union (`"queued" | "running" | "succeeded" | "failed" | "cancelled"`) rather than a named enum. This is the correct openapi-typescript behavior for Pydantic v2 StrEnum types and matches the runtime value shape.
- **`JobDetail.result_ref`** is typed `string | components["schemas"]["ResultLink"][] | null` -- the three variants (single-artifact, campaign, not-yet-succeeded) per the FastAPI docstring. Downstream plans that render the field must narrow with `Array.isArray(result_ref)` (campaign case) / `typeof result_ref === "string"` (single-artifact) / `result_ref == null` (pre-success).
- **`HTTPValidationError`** is declared but is only the 422-response shape. The generic error envelope with `error_type` / `trace_id` is NOT in the generated types -- it's covered by the hand-written `ApiErrorBody` interface in `client.ts`.
- **No `servers` array in the snapshot.** That would let openapi-typescript scope the paths; without it, every `paths[...]` key carries the full `/api/v1/...` prefix. This drove the baseUrl decision above.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] baseUrl + path-key shape mismatch in the plan's sample client.ts**
- **Found during:** Task 2 (writing `frontend/src/api/client.ts`).
- **Issue:** The plan specified `baseUrl: import.meta.env.VITE_API_URL ?? "/api/v1"` and path keys like `paths["/flyers"]["post"]...`. But FastAPI mounts routers with `prefix="/api/v1"`, so `/openapi.json` emits keys like `/api/v1/flyers` -- not `/flyers`. `paths["/flyers"]` therefore has no type, and every alias would fail with TS2339.
- **Fix:** Dropped the `/api/v1` from `baseUrl` (`baseUrl: import.meta.env.VITE_API_URL ?? ""`) and rewrote all 10 alias keys with the absolute `/api/v1/...` prefix. The browser still sends `/api/v1/...` same-origin, Vite's dev proxy still forwards `/api/*` to `:8000`, and a same-origin production mount (deferred future phase) would work with no client change.
- **Files modified:** `frontend/src/api/client.ts`.
- **Verification:** `pnpm typecheck` passes (zero errors, zero `any`). Running `grep "paths\\[\"/api/v1/\"" src/api/client.ts` shows 10 aliases (5 requests + 4 responses + 1 `Schemas = paths`).
- **Committed in:** `9a12dbf` (Task 2 commit).

**2. [Rule 3 - Blocking] Missing `vite-env.d.ts` blocks `import.meta.env` typecheck**
- **Found during:** Task 2 (first `pnpm typecheck` after writing client.ts).
- **Issue:** `tsc --noEmit` reported `src/api/client.ts(18,24): error TS2339: Property 'env' does not exist on type 'ImportMeta'.` The plan-21-01 scaffold did NOT create `src/vite-env.d.ts`, which Vite's scaffold normally emits (it contains `/// <reference types="vite/client" />` to pull in Vite's ambient augmentations for `ImportMeta`).
- **Fix:** Created `frontend/src/vite-env.d.ts` with the single reference directive. `tsconfig.json`'s default `types` behavior then picks up `vite/client` automatically.
- **Files modified:** `frontend/src/vite-env.d.ts` (created).
- **Verification:** `pnpm typecheck` exits 0.
- **Committed in:** `9a12dbf` (Task 2 commit, same commit as the client.ts that needed it).

---

**Total deviations:** 2 auto-fixed (1 Rule 1 bug in the plan's sample code, 1 Rule 3 fix for a plan-21-01 scaffold omission).
**Impact on plan:** Intent is preserved -- 10+ named aliases, reproducible codegen, key registry. The path-key shape is the only substantive behavior change from the plan's sample code, and it's required for the types to be correct at all.

## Issues Encountered

- **Backend not running at worktree start.** Task 1 requires the Phase 20 server on :8000 for the snapshot. Started `uvicorn flyer_generator.api:app` via the repo root's pre-existing `.venv/bin/uvicorn`, waited for `/healthz` to return 200, snapshotted `/openapi.json`, then killed the server. No `uv` binary was available on this machine, so `make serve` / `uv run` could not be used directly -- the project `.venv` already has `uvicorn` installed, so invoking it directly was the cleanest path.
- **FastAPI `api/v1` prefix shape** (deviation #1 above). This is a one-time correction; every downstream plan now calls `client.POST("/api/v1/flyers", ...)` which matches both the generated types AND the dev-proxy route.
- **Missing `vite-env.d.ts`** (deviation #2 above). One-liner fix.

## User Setup Required

None for this plan. Future plans in the phase will still require the Phase 20 backend running on :8000 at runtime (the generated types are static, but live API calls need the backend).

## Next Phase Readiness

- **Ready for plan 21-03 (routing + providers):** `frontend/src/api/client.ts` exports a configured `client` that the TanStack Query mutation/query hooks in plan 21-03 can consume. `frontend/src/lib/queryKeys.ts` is the single registry every hook references.
- **Ready for plan 21-04 (job polling hook + JobStatusCard):** `JobDetail`, `TERMINAL_STATUSES`, `isTerminalStatus`, and `queryKeys.job(id)` are all in place. The hook is a ~30-line wrapper over `useQuery` that the plan will add.
- **Ready for plan 21-05..21-09 (feature pages):** Each plan imports the relevant `*RequestBody` alias for its form, the matching list / detail response alias for its read paths, and `queryKeys.*` for invalidation.
- **Flagged for 21-10 / 21-11:** Phase 20 does NOT yet ship `GET /api/v1/jobs` (list) or `GET /api/v1/renders` (list). Both plans must add the route to Phase 20 first, re-snapshot, re-run `pnpm gen:api:snapshot`, and only then type-alias the new list responses in `client.ts`.

## Self-Check

Verifying claims before proceeding.

**Created files exist:**
- `frontend/src/api/openapi.snapshot.json` -- FOUND (25,758 bytes)
- `frontend/src/api/schema.gen.ts` -- FOUND (34,026 bytes, 1087 lines)
- `frontend/src/api/client.ts` -- FOUND (72 lines)
- `frontend/src/lib/queryKeys.ts` -- FOUND (38 lines)
- `frontend/src/vite-env.d.ts` -- FOUND (1 line)

**Commits exist:**
- `41ceb80` (Task 1: snapshot + codegen) -- FOUND
- `9a12dbf` (Task 2: client.ts + vite-env.d.ts) -- FOUND
- `83f4c2c` (Task 3: queryKeys.ts) -- FOUND

**Verify runs:**
- `pnpm gen:api:snapshot` -> exits 0, regenerates schema.gen.ts in ~110 ms
- `pnpm typecheck` -> exits 0 (zero errors, zero `any` in new files)
- `grep "export interface paths" src/api/schema.gen.ts` -> 1 match
- `grep "createClient<paths>" src/api/client.ts` -> 1 match
- `grep "export const queryKeys" src/lib/queryKeys.ts` -> 1 match

## Self-Check: PASSED

---
*Phase: 21-react-frontend-dashboard*
*Completed: 2026-04-23*
