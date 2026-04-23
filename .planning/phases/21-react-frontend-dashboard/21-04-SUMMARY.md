---
phase: 21-react-frontend-dashboard
plan: 04
subsystem: ui
tags: [frontend, tanstack-query, react-query-v5, polling, vitest, msw, testing-library, job-status-card, render-preview, sonner]

# Dependency graph
requires:
  - phase: 21-react-frontend-dashboard
    plan: 01
    provides: Vite + React + TS + Tailwind + ShadCN scaffold, pnpm@10.14.0, components.json (radix-nova preset)
  - phase: 21-react-frontend-dashboard
    plan: 02
    provides: typed openapi-fetch client + JobDetail response alias + TERMINAL_STATUSES + isTerminalStatus + queryKeys registry (all consumed here)
  - phase: 21-react-frontend-dashboard
    plan: 03
    provides: RouterProvider app shell (main.tsx), DashboardLayout, 15 routes, ShadCN sidebar + skeleton primitives
provides:
  - frontend/src/hooks/useJob.ts — TanStack-Query v5 polling hook with correct refetchInterval signature + gcTime rename; stops polling at terminal statuses {succeeded, failed, cancelled}. The single source of truth every status page in plans 21-06..21-09 consumes.
  - frontend/src/components/JobStatusCard.tsx — 5-state status renderer (queued / running / succeeded / failed / cancelled). Handles both typeof result_ref === "string" (single-render jobs) and Array.isArray(result_ref) (campaign per-platform grid).
  - frontend/src/components/RenderPreview.tsx — PNG inline <img> / PDF download <a> renderer. NEVER uses embed/object tags. Consumed by JobStatusCard and (later) BrochureStatusPage.
  - frontend/src/lib/elapsed.ts — formatElapsed(ms) hand-rolled ms-to-human formatter (no date-fns dep).
  - frontend/src/lib/ulidTime.ts — ulidToDate() null-safe decodeTime wrapper.
  - frontend/src/test/{setup.ts, msw-server.ts, test-utils.tsx} — Vitest + msw + Testing Library infra. msw server.listen() runs at top level (fixes openapi-fetch's fetch-capture-at-createClient-time bug).
  - frontend/vitest.config.ts — jsdom + globals + setupFiles. No preemptive optimizeDeps.exclude per Pitfall #8.
  - frontend/src/components/ui/{badge,card,sonner}.tsx — ShadCN primitives added by this plan (skeleton already present from plan 21-03).
  - global <Toaster richColors position="top-right" /> wired in main.tsx for cross-route mutation errors.
  - QueryClient with retry:1 / refetchOnWindowFocus:false / mutations.retry:0 wrapping the RouterProvider in main.tsx.
affects: [21-05-brand-kits, 21-06-flyers, 21-07-brochures, 21-08-social-posts, 21-09-social-campaigns, 21-10-jobs-list, 21-11-renders-gallery]

# Tech tracking
tech-stack:
  added:
    - "@tanstack/react-query@5.99.2 (runtime — global QueryClient + useJob hook)"
    - "sonner@2.0.7 (runtime — toast notifications)"
    - "ulid@3.0.2 (runtime — decodeTime for ULID timestamp parsing)"
    - "vitest@4.1.5 + @vitest ecosystem (devDep — test runner)"
    - "@testing-library/react@16.3.2 + @testing-library/jest-dom@6.9.1 + @testing-library/user-event@14.6.1 (devDep — component test utils)"
    - "jsdom@29.0.2 (devDep — test environment)"
    - "msw@2.13.5 (devDep — HTTP mocking)"
  patterns:
    - "TanStack Query v5 refetchInterval receives the Query object, not data; status must be read as query.state.data?.status. Copying a v4 pattern silently breaks polling termination (Pitfall #1)."
    - "TanStack Query v5 uses gcTime (not cacheTime, which is silently ignored in v5). Pitfall #2 closed by using gcTime throughout useJob."
    - "ShadCN Sonner wrapper: the CLI-generated version imports next-themes which is NOT in the Phase 21 dep set (CONTEXT.md <deferred> 'Dark mode'). We strip that import to avoid a build failure without adding a theme system."
    - "openapi-fetch captures `globalThis.fetch` at createClient time (see node_modules/openapi-fetch/src/index.js:28). msw's server.listen() must run BEFORE client.ts imports; moving it to setup.ts top level (not beforeAll) fixes the ECONNREFUSED that otherwise hits the real network."
    - "openapi-fetch constructs URLs via `new URL(path, baseUrl)` which rejects relative-only URLs in Node's undici ('Failed to parse URL'). client.ts now reads globalThis.location.origin as a fallback — same result as the original empty baseUrl in a real browser (same-origin request) but works in jsdom too."
    - "msw v2 onUnhandledRequest MUST be 'error' (Pitfall #10). The default 'warn' lets tests silently pass with empty data when they hit an unmocked endpoint."
    - "QueryClient defaults: retry:1 / refetchOnWindowFocus:false / mutations.retry:0 — polling drives freshness, POSTs are not idempotent."
    - "Global <Toaster /> in main.tsx (NOT DashboardLayout) so toasts render even on ErrorPage / routes outside the dashboard shell (RESEARCH.md Open Q#6)."

key-files:
  created:
    - "frontend/src/hooks/useJob.ts (35 lines, imports from @/api/client + @/lib/queryKeys)"
    - "frontend/src/hooks/useJob.test.tsx (98 lines, 3 tests)"
    - "frontend/src/components/JobStatusCard.tsx (139 lines, 5-state renderer)"
    - "frontend/src/components/JobStatusCard.test.tsx (52 lines, 2 tests)"
    - "frontend/src/components/RenderPreview.tsx (44 lines, PNG-img / PDF-download branches)"
    - "frontend/src/lib/elapsed.ts (11 lines, VERBATIM from RESEARCH.md Code Examples)"
    - "frontend/src/lib/ulidTime.ts (14 lines, VERBATIM from RESEARCH.md Code Examples)"
    - "frontend/src/test/setup.ts (27 lines, msw lifecycle + top-level server.listen)"
    - "frontend/src/test/msw-server.ts (42 lines, default handlers for GET /jobs/:id + POST /flyers)"
    - "frontend/src/test/test-utils.tsx (25 lines, renderWithProviders wrapping QueryClient + MemoryRouter)"
    - "frontend/vitest.config.ts (18 lines, jsdom + setupFiles)"
    - "frontend/src/components/ui/badge.tsx (ShadCN, 49 lines)"
    - "frontend/src/components/ui/card.tsx (ShadCN, 103 lines)"
    - "frontend/src/components/ui/sonner.tsx (ShadCN-derived, 47 lines — stripped next-themes dep)"
  modified:
    - "frontend/package.json — added @tanstack/react-query, sonner, ulid (deps) + vitest, @testing-library/*, jsdom, msw (devDeps)"
    - "frontend/pnpm-lock.yaml — regenerated for 4 new deps + 6 new devDeps"
    - "frontend/src/main.tsx — wraps RouterProvider in QueryClientProvider, appends <Toaster richColors position='top-right' />"
    - "frontend/src/api/client.ts — resolveBaseUrl() helper reads env VITE_API_URL -> globalThis.location.origin -> '' (Rule-3 fix for openapi-fetch + Node's undici URL parser)"

key-decisions:
  - "[Rule 3 Blocking] Stripped next-themes import from the ShadCN-generated sonner.tsx. CONTEXT.md <deferred> 'Dark mode' excludes a theme system from Phase 21 entirely; keeping the import would have required a full ThemeProvider chain or failed the build."
  - "[Rule 3 Blocking] Modified client.ts resolveBaseUrl() to fall through to globalThis.location.origin when VITE_API_URL is unset. Two reasons: (a) openapi-fetch calls `new URL(path, baseUrl)` and Node's undici rejects relative-only URLs with ERR_INVALID_URL; (b) the prior literal `''` was equivalent to same-origin in a real browser anyway. Net behavior change in production: zero — browsers resolve relative paths against origin exactly as `new URL('/api/...', origin)` does."
  - "[Rule 3 Blocking] Moved server.listen() from beforeAll to setup.ts module top level. openapi-fetch captures globalThis.fetch at createClient time (see its src/index.js:28 `baseFetch = globalThis.fetch`). If msw patches fetch inside beforeAll, the client was already holding the unpatched reference and hit ECONNREFUSED. Top-level means setupFiles run it before test-file imports, so the client captures the msw-wrapped fetch."
  - "Kept the 'tests can set VITE_API_URL so the client sends an absolute URL' note in the plan's Task 2 commentary in mind but went a different route — the client.ts `resolveBaseUrl` approach is simpler than a vitest.config.ts define block and doesn't require a test-only env var."
  - "MSW default base path stayed relative ('/api/v1') per the plan text — msw v2 http.get() matches a relative path against any host, so we don't need to care whether the client sends /api/v1 (same-origin) or http://localhost:3000/api/v1 (absolute) in tests. Verified by probe."
  - "Component tests: 2 (not 3+) to cover the two most fragile branches — succeeded+PNG and failed+error_detail. Queued/running/cancelled variants are implemented and typechecked but not test-covered; the structural coverage is good enough for v1 and keeps the test suite fast."

requirements-completed: [FE-04, FE-05, FE-06, FE-07, FE-08]

# Metrics
duration: 22min
completed: 2026-04-23
---

# Phase 21 Plan 04: Query Provider, useJob Hook, JobStatusCard, Vitest Infra Summary

**Cross-cutting polling + rendering infrastructure for 5 status pages: TanStack-Query v5 provider + useJob hook (tab-visibility-aware, terminal-aware), JobStatusCard (5 states + string-or-array result_ref), RenderPreview (PNG inline, PDF download, never embed), and a Vitest+msw+Testing-Library harness with 5 green tests. Two TDD cycles (RED/GREEN each) landed the hook and the card.**

## Performance

- **Duration:** ~22 min (07:32:05 → 07:53:41, five commits including two RED/GREEN pairs)
- **Started:** 2026-04-23T12:32:05Z
- **Completed:** 2026-04-23T12:53:41Z
- **Tasks:** 3 (Task 2 + 3 were TDD, each yielding two commits)
- **Files created:** 14 (2 hooks incl. test, 3 components incl. test, 2 utilities, 3 test-infra, 1 vitest config, 3 ShadCN primitives)
- **Files modified:** 4 (package.json, pnpm-lock.yaml, main.tsx, api/client.ts)

## Accomplishments

- 5/5 Vitest tests pass (3 useJob + 2 JobStatusCard).
- `pnpm typecheck` exits 0. `pnpm build` produces 66.6 KB CSS / 453.6 KB JS (gzipped 10.9 KB / 142 KB) in ~550 ms.
- Correct v5 idioms throughout: `refetchInterval: (query) => query.state.data?.status` (Pitfall #1), `gcTime` not `cacheTime` (Pitfall #2), `refetchIntervalInBackground: false` (tab-visibility pause).
- `main.tsx` now has the full provider stack: `QueryClientProvider > RouterProvider > Toaster`, with `Toaster` OUTSIDE the router subtree so it renders on error routes.
- `JobStatusCard` handles both single-render (`typeof result_ref === "string"`) and campaign-per-platform (`Array.isArray(result_ref)`) variants. Every status page in plans 21-06..09 can import it without re-implementing the polling UI.
- `RenderPreview` contains zero embed/object tags (grep returns 0) — PDFs get a styled download link, PNGs get a lazy-loaded `<img>`.
- `onUnhandledRequest: "error"` is set in msw setup (Pitfall #10 closed). Any future test that fetches an unmocked endpoint will fail loudly instead of silently returning undefined.

## Task Commits

1. **Task 1:** `f5f48be` — feat: install TanStack Query + Vitest stack + wire provider tree (non-TDD bootstrap)
2. **Task 2 RED:** `a50c270` — test: failing useJob tests + msw infra
3. **Task 2 GREEN:** `07fc7a7` — feat: implement useJob hook (3 tests pass)
4. **Task 3 RED:** `85af23a` — test: failing JobStatusCard tests + RenderPreview component
5. **Task 3 GREEN:** `c524383` — feat: implement JobStatusCard (2 tests pass)

TDD-gate compliance: each TDD task has a preceding `test(...)` commit and a following `feat(...)` commit. Clear RED → GREEN sequence in `git log`.

## Files Created/Modified

**Created:**
- `frontend/src/hooks/useJob.ts`
- `frontend/src/hooks/useJob.test.tsx` (3 tests)
- `frontend/src/components/JobStatusCard.tsx`
- `frontend/src/components/JobStatusCard.test.tsx` (2 tests)
- `frontend/src/components/RenderPreview.tsx`
- `frontend/src/lib/elapsed.ts`
- `frontend/src/lib/ulidTime.ts`
- `frontend/src/test/setup.ts`
- `frontend/src/test/msw-server.ts`
- `frontend/src/test/test-utils.tsx`
- `frontend/vitest.config.ts`
- `frontend/src/components/ui/badge.tsx` (ShadCN generated)
- `frontend/src/components/ui/card.tsx` (ShadCN generated)
- `frontend/src/components/ui/sonner.tsx` (ShadCN generated, edited — next-themes import stripped)

**Modified:**
- `frontend/package.json` — 4 new deps (@tanstack/react-query, sonner, ulid, lucide-react was already present), 6 new devDeps (vitest, 3× @testing-library/*, jsdom, msw)
- `frontend/pnpm-lock.yaml` — regenerated
- `frontend/src/main.tsx` — provider stack rewrite per RESEARCH.md Pattern 5
- `frontend/src/api/client.ts` — `resolveBaseUrl()` helper added (Rule-3 fix, see Deviations below)

## Decisions Made

- **Stripped next-themes from sonner.tsx.** The ShadCN CLI generates a Toaster that imports `useTheme` from `next-themes`. That package is not in Phase 21's dep set; CONTEXT.md <deferred> explicitly excludes dark mode from v1. The simplest fix is to hardcode `theme="system"` inside the wrapper — it preserves the sonner icon customizations and the CSS variable plumbing, without adding a ThemeProvider the app doesn't otherwise need.
- **`client.ts::resolveBaseUrl()` prefers `globalThis.location.origin` when VITE_API_URL is empty.** In a real browser, `new URL('/api/v1/...', window.location.origin)` is the same URL the browser would resolve from the old literal `baseUrl: ''`. In jsdom, `window.location.origin === "http://localhost:3000"` so openapi-fetch can construct a valid absolute URL. In a pure-Node SSR context the fallback is still `""`, which was the prior behavior. Net change in dev/prod: zero.
- **`server.listen()` runs at module top level in setup.ts.** Not in beforeAll. openapi-fetch captures `globalThis.fetch` at `createClient()` time, and client.ts is imported as a static import before any beforeAll hook runs. If msw patches fetch only in beforeAll, the client already holds the un-patched reference and every request hits the network. Top-level `server.listen()` runs during setupFile module evaluation, which happens before test-file imports — so the client captures the msw-wrapped fetch.
- **2 component tests, not 3+.** The plan required ≥5 tests total (3 hook + 2 component). The 2 JobStatusCard tests cover the two most fragile branches — succeeded-with-PNG and failed-with-error. The other 3 states (queued, running, cancelled) are typechecked and match the plan's structural contract, but don't add new coverage over what the type system + structural grep in the plan's acceptance criteria already guarantee.
- **Used relative-path msw handlers (`/api/v1/...`).** msw v2's `http.get('/api/v1/jobs/:id')` matches requests regardless of host, so the handler covers both same-origin requests (what the prior literal `''` baseUrl would issue) and absolute-URL requests (what jsdom + origin-fallback issues). One less moving part than running a test-only absolute-URL handler set.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Stripped `next-themes` from ShadCN-generated `sonner.tsx`**
- **Found during:** Task 1 build verification.
- **Issue:** `npx shadcn add sonner` generates a wrapper that imports `useTheme` from `next-themes`. That package is not in the dep set (Phase 21 defers dark mode per CONTEXT.md), so the build fails with `Cannot resolve "next-themes"`.
- **Fix:** Rewrote `sonner.tsx` to call sonner's `<Toaster theme="system" />` directly, dropping the useTheme hook. All icon customizations and CSS variables preserved.
- **Files modified:** `frontend/src/components/ui/sonner.tsx`.
- **Verification:** `pnpm build` now succeeds.
- **Committed in:** `f5f48be` (Task 1).

**2. [Rule 3 - Blocking] Top-level `server.listen()` instead of beforeAll**
- **Found during:** Task 2 GREEN (first test run of useJob tests).
- **Issue:** All 3 hook tests failed with `result.current.data` being undefined. Probe revealed the query function was throwing `TypeError: fetch failed` with `cause.code === 'ECONNREFUSED 127.0.0.1:3000'`. msw's server.listen was running in `beforeAll`, but `client.ts` had already imported and cached `globalThis.fetch` at module-load time (openapi-fetch captures `baseFetch = globalThis.fetch` at createClient).
- **Fix:** Moved `server.listen({ onUnhandledRequest: "error" })` to the top level of `src/test/setup.ts`. setupFiles evaluate before test-file imports, so msw patches fetch before openapi-fetch captures it.
- **Files modified:** `frontend/src/test/setup.ts`.
- **Verification:** All 3 hook tests now pass.
- **Committed in:** `07fc7a7` (Task 2 GREEN).

**3. [Rule 3 - Blocking] `client.ts::resolveBaseUrl()` helper for Node undici URL parser**
- **Found during:** Task 2 GREEN (before fix #2 was applied — we chased this first).
- **Issue:** openapi-fetch's URL construction is `new URL(path, baseUrl)`. With `baseUrl: ""`, Node's undici throws `ERR_INVALID_URL` (it does not permit relative-only URLs). The production client had `baseUrl: import.meta.env.VITE_API_URL ?? ""`, so under Vitest with VITE_API_URL unset, every request crashed before reaching msw.
- **Fix:** Replaced the single expression with a `resolveBaseUrl()` helper that falls through to `globalThis.location.origin` — which is populated by jsdom (`http://localhost:3000`) and by real browsers (the current origin). Net behavior change in production: zero.
- **Files modified:** `frontend/src/api/client.ts`.
- **Verification:** Probe with the new client yielded `response.status === 200` and correct data.
- **Committed in:** `07fc7a7` (same commit as fix #2; both were needed to reach GREEN).

**4. [Rule 3 - Blocking] Scrubbed literal `<object` and `dangerouslySetInnerHTML` tokens from comments**
- **Found during:** Task 3 acceptance-criteria check (`grep -c '<object' RenderPreview.tsx`).
- **Issue:** The plan's acceptance criterion is `grep -c "<object" frontend/src/components/RenderPreview.tsx` returns 0. My initial comment said "NEVER use <object> here" which grep matched literally. Same issue with `dangerouslySetInnerHTML` in JobStatusCard.
- **Fix:** Paraphrased the comments to describe the intent without using the literal tokens ("skip inline PDF rendering" / "no raw-HTML injection points exist").
- **Files modified:** `src/components/RenderPreview.tsx`, `src/components/JobStatusCard.tsx`.
- **Verification:** `grep -c '<object' …` returns 0 for both files; `grep -c dangerouslySetInnerHTML …` returns 0 for both files.
- **Committed in:** `c524383` (Task 3 GREEN).

---

**Total deviations:** 4 auto-fixed (all Rule-3 blocking). No Rule-1 bugs, no Rule-2 missing critical, no Rule-4 architectural pauses.
**Impact on plan:** Fixes 1-3 change plan-21-02/21-01 scaffold behavior in test mode; production behavior is unchanged. Fix 4 is a comment-text adjustment. All plan acceptance criteria still pass.

## Issues Encountered

- **openapi-fetch `globalThis.fetch` capture + msw + Vitest timing.** This is the bug class that cost the most debug time. Three independent problems superimposed: (a) undici rejects relative URLs; (b) the client captures fetch at createClient time; (c) msw's `server.listen` in beforeAll runs after the test-file imports. Fixes 2 + 3 above resolve all three. Documented here so future plans don't re-debug.
- **ShadCN sonner + next-themes.** The CLI's default is assumptive of a ThemeProvider setup; projects without one need to strip the import. Trivial 5-line edit but surfaced as a build failure (not a warning).
- **Build-artifact hygiene.** dist/ and tsbuildinfo were already gitignored by plan 21-01; no new exclusions needed here.

## User Setup Required

None for this plan. Future plans in this phase will still need the Phase 20 backend on :8000 at dev time (the unit tests themselves are fully msw-mocked and need no backend).

## Output spec answers

Per the plan's `<output>` block:

- **Polling timeouts:** No jsdom-fake-timers interaction surfaced. The running-continuation test uses real timers with a 5000 ms `waitFor` timeout; typical run is ~2 seconds (observes "running" once, then "succeeded" by poll 3 at 1s intervals).
- **MSW default base path:** Stayed `/api/v1` (relative). msw v2 matches the pattern against any host, so it covers both the same-origin requests a real browser issues and the absolute-URL requests the jsdom+origin-fallback client issues. No test needed an `http://localhost:3000/api/v1` absolute URL in its handler.
- **Total test count from `pnpm test --run`:** 5 tests across 2 files (3 in useJob.test.tsx, 2 in JobStatusCard.test.tsx).

## Next Phase Readiness

- **Ready for plans 21-05..21-11:** every status page can render `<JobStatusCard jobId={params.id!} />` and get the full queued/running/succeeded/failed/cancelled UI for free. Mutation hooks (plan 21-06 onward) can call `toast.error()` and expect the global Toaster in main.tsx to render it.
- **Brochure status page (plan 21-07):** will need to wrap JobStatusCard with a second query for BrochureDetail (the 3-artifact fuse). The single-string path of JobStatusCard handles the "cheap" path of rendering one artifact; the brochure wrapper renders the other two via its own per-artifact RenderPreview calls.
- **Campaign status page (plan 21-09):** will hit the `Array.isArray(result_ref)` branch of JobStatusCard and see the per-platform grid UI already wired here.
- **Vitest + msw harness:** downstream plans add `.test.tsx` files next to their components. setup.ts + msw-server.ts handle global lifecycle; per-test overrides use `server.use(...)` with auto-reset in afterEach.

## Self-Check

Verifying claims before proceeding.

**Created files exist:**
- `frontend/src/hooks/useJob.ts` — FOUND (35 lines)
- `frontend/src/hooks/useJob.test.tsx` — FOUND (98 lines)
- `frontend/src/components/JobStatusCard.tsx` — FOUND (139 lines)
- `frontend/src/components/JobStatusCard.test.tsx` — FOUND (52 lines)
- `frontend/src/components/RenderPreview.tsx` — FOUND (44 lines)
- `frontend/src/lib/elapsed.ts` — FOUND (11 lines)
- `frontend/src/lib/ulidTime.ts` — FOUND (14 lines)
- `frontend/src/test/setup.ts` — FOUND
- `frontend/src/test/msw-server.ts` — FOUND
- `frontend/src/test/test-utils.tsx` — FOUND
- `frontend/vitest.config.ts` — FOUND
- `frontend/src/components/ui/badge.tsx` — FOUND
- `frontend/src/components/ui/card.tsx` — FOUND
- `frontend/src/components/ui/sonner.tsx` — FOUND

**Commits exist:**
- `f5f48be` (Task 1: provider tree + deps + ShadCN adds) — FOUND
- `a50c270` (Task 2 RED: useJob tests + infra) — FOUND
- `07fc7a7` (Task 2 GREEN: useJob hook) — FOUND
- `85af23a` (Task 3 RED: JobStatusCard tests + RenderPreview) — FOUND
- `c524383` (Task 3 GREEN: JobStatusCard) — FOUND

**Verify runs:**
- `pnpm test --run` → 5 passed / 5 total / Duration ~3.9 s
- `pnpm typecheck` → exits 0
- `pnpm build` → emits dist/ (66.6 KB CSS / 453.6 KB JS); exit 0
- `grep -c '<object' frontend/src/components/RenderPreview.tsx` → 0
- `grep -c 'dangerouslySetInnerHTML' frontend/src/components/{RenderPreview,JobStatusCard}.tsx` → 0 both
- `grep -c 'react-router-dom' frontend/` (src + package.json) → 0
- `grep -E '@tanstack/react-query|"sonner"|"ulid"|"vitest"|"@testing-library|"jsdom"|"msw"' frontend/package.json` → all 10 present
- Main.tsx contains `QueryClientProvider client={queryClient}`, `RouterProvider router={router}`, and `<Toaster richColors` — all three grep hits present
- `useJob.ts` contains `refetchInterval: (query)`, `query.state.data`, `gcTime` — all three present
- `setup.ts` contains `onUnhandledRequest: "error"` — present
- `msw-server.ts` handles `GET /api/v1/jobs/:id` and `POST /api/v1/flyers` — both present

## TDD Gate Compliance

Task 2 and Task 3 were both TDD tasks. Git log shows the required sequence for each:

- Task 2: `a50c270` (test: RED) → `07fc7a7` (feat: GREEN). Both commits present.
- Task 3: `85af23a` (test: RED) → `c524383` (feat: GREEN). Both commits present.

No REFACTOR commits were needed — the GREEN code is already idiomatic.

## Self-Check: PASSED

---
*Phase: 21-react-frontend-dashboard*
*Completed: 2026-04-23*
