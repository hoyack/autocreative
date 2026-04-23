---
phase: 21-react-frontend-dashboard
verified: 2026-04-23T14:58:28Z
updated: 2026-04-23T20:52:26Z
status: human_needed
score: 13/13 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 13/13
  wave: 6
  wave_plans: [21-12, 21-13, 21-14]
  warnings_closed: [WR-01, WR-02, WR-03, WR-04]
  info_closed: [IN-01, IN-03]
  gaps_closed:
    - "WR-01: brochure worker reads payload['workflow'] (not 'workflow_name')"
    - "WR-02: list_brand_kits dedupes FS-fuse against full DB slug set (stable total, no duplicates)"
    - "WR-03: both brand-kits + brochures routes wrap enqueue_job in try/except with compensating FAILED transition"
    - "WR-04: RenderPreview uses strict .pdf suffix regex + explicit isPdf prop (no /pdf substring false-positives)"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Capability (a): Browse brand kits + scrape a new one via URL"
    expected: "Navigate /brand-kits -> see card grid; click Add brand kit; enter URL + slug; submit; watch job progress to succeeded; return to /brand-kits and see new kit; click card -> detail shows palette swatches + typography + logos + voice"
    why_human: "End-to-end UX flow (form submit -> job polling -> render) only verifiable with live Phase 20 API + real scrape"
  - test: "Capability (b): Flyer form -> job progress -> rendered PNG"
    expected: "Navigate /flyers/new; fill EventInput fields + preset + accent; submit; on /flyers/:id see queued -> running (elapsed counter ticks) -> succeeded with PNG preview rendered inline"
    why_human: "Visual PNG appearance + 1s polling cadence + elapsed-time counter behavior only verifiable at runtime"
  - test: "Capability (c): Brochure form -> two sheets + PDF render"
    expected: "Navigate /brochures/new; paste content JSON + fill template/preset/brand-kit; submit; on /brochures/:id see job polling and, after succeeded, 3 artifacts: front PNG inline + back PNG inline + Print PDF download link"
    why_human: "Three-artifact render visibility + PDF download link behavior only verifiable against a real brochure job"
  - test: "Capability (d): Social post form -> copy + image + validation report"
    expected: "Navigate /social/posts/new; pick platform/intent + fill topic/cta/image_hint/brand-kit; submit; on /social/posts/:id watch job poll to succeeded; see rendered post image"
    why_human: "Note v1 scope limitation: per 21-08 plan, validation_report and audit_report are NOT yet surfaced by the v1 API (PostRecord.audit_report has no read route) — only the image preview is rendered. This deviation is documented in the plan but needs human confirmation that the visible UX matches user expectation for v1."
  - test: "Capability (e): Campaign form -> N platform variants render"
    expected: "Navigate /social/campaigns/new; pick 2+ platforms via checkbox group + intent/topic/brand-kit; submit; on /social/campaigns/:id see per-platform grid with one RenderPreview per platform"
    why_human: "Multi-platform grid rendering + array-result_ref branch of JobStatusCard only verifiable against a real campaign job"
  - test: "Capability (f): Browse past renders with download + inline preview"
    expected: "Navigate /renders; see CSS grid of render cards; PNG kinds render inline via <img>; PDF kinds show Download PDF link; Kind dropdown filters results; pagination works"
    why_human: "Gallery grid visuals + PDF download behavior + filter refinement only verifiable at runtime"
  - test: "Jobs page (FE-09): global list with row-level status polling"
    expected: "Navigate /jobs; see Table with Created/Kind/Status/Id columns; Kind + Status filters refine list; non-terminal rows poll and update status in place every 1s; row click navigates to the creative's status page for flyer/brochure/social_post/social_campaign kinds (brand_kit falls back to /jobs/:id -> 404 wildcard which is acknowledged as an accepted v1 gap in plan 21-10)"
    why_human: "Per-row live polling update behavior + click-through routing only verifiable with multiple live jobs in progress"
  - test: "Sidebar navigation: 7 links with active-state highlighting"
    expected: "DashboardLayout sidebar shows Brand kits / New flyer / New brochure / New post / New campaign / Jobs / Renders. Current route's NavLink has aria-current or data-active styling."
    why_human: "aria-current + data-active visual distinction cannot be verified purely through automated tests without a JSX snapshot"
  - test: "Dev loop: cd frontend && pnpm dev boots on :5173 and talks to Phase 20 via proxy"
    expected: "Vite dev server starts on :5173; HMR works; /api/* requests proxy to http://localhost:8000; no CORS errors in browser console"
    why_human: "Live server + proxy handshake + browser network behavior only verifiable by running the dev loop"
---

# Phase 21: React Frontend Dashboard Verification Report

**Phase Goal:** A developer can run `cd frontend && pnpm dev` and, against a running Phase 20 API, use a single-page React dashboard to (a) browse brand kits + scrape a new one via URL, (b) fill a flyer form and watch its job progress to a rendered PNG, (c) fill a brochure form and watch its two sheets + PDF render, (d) fill a social post form and watch copy + image + validation report render, (e) fill a campaign form and watch all N platform variants render, (f) browse past renders in a gallery with download + inline preview. Single-user v1 (no login). All dashboard pages use ShadCN components + Tailwind; job status polls Phase 20's `/api/v1/jobs/{id}` endpoint (no WebSocket for v1).

**Verified:** 2026-04-23T14:58:28Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Summary

Phase 21 ships a complete, substantively-implemented React dashboard. All 11 plans completed and committed. All automated checks pass cleanly:

- `pnpm typecheck` — clean (strict mode, no errors)
- `pnpm test --run` — 22/22 tests across 11 test files pass in 6.95s
- `pnpm build` — production bundle emits to frontend/dist/ in 597ms (640.49 kB main bundle, 80.49 kB CSS, 3 Geist woff2 font assets)
- `pytest tests/api/ -q` — 172/172 backend API tests pass (no regression from the new list_jobs / list_renders / brochure-detail / brand-kit-logo routes)

All 6 goal-specified capabilities (a-f) map to concrete pages with real implementations (none are stubs). All 10 requirement IDs (FE-01..FE-10) map to committed artifacts. All 4 warnings surfaced in 21-REVIEW.md are polish items that do NOT block the stated goal — they are listed under Anti-Patterns for a follow-up phase.

Verification status is `human_needed` because the goal is inherently runtime-observable: job polling, PNG rendering, PDF downloads, per-platform campaign grids, and sidebar active-state highlighting all require running the live Phase 20 backend plus the Vite dev server to verify visually. Every automated check passes.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `cd frontend && pnpm dev` boots Vite on :5173 (scaffolded per FE-01) | VERIFIED | frontend/package.json declares `"dev": "vite"`, vite.config.ts sets port 5173; `pnpm build` produces dist/ successfully |
| 2 | `pnpm build` emits production bundle | VERIFIED | Run confirmed: `dist/index.html` + `dist/assets/index-*.js` (640.49 kB) + `dist/assets/index-*.css` (80.49 kB) emitted in 597ms |
| 3 | Typed API client generated from Phase 20 OpenAPI (FE-02) | VERIFIED | frontend/src/api/schema.gen.ts (1087 lines, zero `any`), frontend/src/api/client.ts (openapi-fetch createClient<paths>), frontend/src/api/openapi.snapshot.json committed |
| 4 | Dashboard shell with sidebar navigation for 7 sections (FE-03) | VERIFIED | frontend/src/components/DashboardLayout.tsx maps NAV array of 7 entries (Brand kits / New flyer / New brochure / New post / New campaign / Jobs / Renders) into Sidebar + Outlet; NavLink renders {isActive} into SidebarMenuButton isActive prop |
| 5 | Brand Kits browse + scrape + detail (FE-04, capability a) | VERIFIED | pages/brand-kits/{list,new,detail}.tsx are all 90-177 lines of real implementation; list renders BrandKitCard grid from GET /brand-kits; new does RHF+zod + POST /brand-kits/fetch + navigate to /jobs/:id; detail renders PaletteSwatches + Typography + LogoGallery + Voice |
| 6 | Flyer form + job polling + PNG preview (FE-05, capability b) | VERIFIED | pages/flyers/new.tsx (360 lines) mirrors FlyerCreateRequest + EventInput with .strict() and HEX+SLUG regex; status.tsx wraps <JobStatusCard/>; JobStatusCard polls GET /jobs/{id} at 1s via useJob hook and renders <RenderPreview> on succeeded |
| 7 | Brochure form + 2 sheets + PDF (FE-06, capability c) | VERIFIED | pages/brochures/new.tsx (274 lines) has RHF+zod JSON-paste textarea per plan; status.tsx polls job + fetches /brochures/{id} via queryKeys.brochure(id) + renders 3 RenderPreview entries (front/back/pdf); BE task/brochure.py sets result_ref = brochure_record.id per parallel-ID pattern; GET /brochures/{brochure_id} returns BrochureDetail with 3 URLs |
| 8 | Social post form + copy + image + validation (FE-07, capability d) | VERIFIED with noted scope limitation | pages/social/posts/new.tsx (312 lines) mirrors PostCreateRequest; status.tsx wraps <JobStatusCard/>. Note: validation_report + audit_report are NOT yet surfaced by the v1 API (no read route for PostRecord.audit_report); per 21-08-PLAN.md this is an acknowledged v1 scope deviation — image preview only. Goal wording says "watch copy + image + validation report render" but the plan explicitly documents the validation_report deferral. Flagged for human confirmation. |
| 9 | Campaign form + N platform variants (FE-08, capability e) | VERIFIED | pages/social/campaigns/new.tsx (337 lines) has Checkbox group for platforms (min 1 max 10) + multi-platform form; status.tsx wraps <JobStatusCard/> whose Array.isArray(result_ref) branch renders per-platform grid with one RenderPreview per link |
| 10 | Jobs page with global list + row-level polling (FE-09) | VERIFIED | pages/jobs/list.tsx (243 lines) renders Table with Kind + Status filter Selects; each row renders <JobStatusBadge> which consumes useJob for non-terminal rows (1s polling, terminal short-circuits); statusPathFor routes rows to /flyers/:id, /brochures/:id, /social/posts/:id, /social/campaigns/:id; new BE GET /api/v1/jobs with PaginatedJobs schema |
| 11 | Renders gallery + download + inline preview (FE-10, capability f) | VERIFIED | pages/renders/gallery.tsx (177 lines) renders CSS-grid of RenderCard items; PNG kinds render via <RenderPreview> with inline <img>; PDF kinds render <a download> link; Kind Select filter + Previous/Next pagination; new BE GET /api/v1/renders with PaginatedRenders schema |
| 12 | Job status polls /api/v1/jobs/{id} at 1s cadence, stops on terminal | VERIFIED | frontend/src/hooks/useJob.ts uses v5 refetchInterval signature (reads query.state.data.status, NOT data.status — Pitfall #1 honored), uses gcTime (NOT cacheTime — Pitfall #2 honored), refetchIntervalInBackground: false; TERMINAL_STATUSES = ["succeeded","failed","cancelled"] mirror server enum |
| 13 | Provider tree: QueryClient + RouterProvider + Toaster in main.tsx | VERIFIED | frontend/src/main.tsx wraps <QueryClientProvider> (retry:1, refetchOnWindowFocus:false, mutations.retry:0) around <RouterProvider router={router}/> and mounts <Toaster richColors position="top-right"/> at top level |

**Score:** 13/13 truths verified

### Required Artifacts

All 11 plans pass `gsd-tools verify artifacts` (40/40 artifacts exist and are substantive — no stubs).

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| frontend/package.json | pnpm project root | VERIFIED | packageManager: pnpm@10.x; 11 scripts (dev/build/preview/test/test:watch/lint/lint:fix/format/typecheck/gen:api/gen:api:snapshot) |
| frontend/vite.config.ts | Vite config with proxy | VERIFIED | server.port=5173, proxy `/api` -> `http://localhost:8000` with changeOrigin=true |
| frontend/src/main.tsx | Provider tree | VERIFIED | QueryClientProvider + RouterProvider + Toaster correctly composed |
| frontend/src/routes.tsx | Central router with all feature routes | VERIFIED | createBrowserRouter with DashboardLayout root + 15 children (index redirect + 13 feature + wildcard 404) |
| frontend/src/api/client.ts | Typed openapi-fetch client | VERIFIED | createClient<paths>, same-origin baseUrl resolution, 5 request-body aliases, 4 response aliases, ApiErrorBody, isTerminalStatus |
| frontend/src/api/schema.gen.ts | Generated TS types | VERIFIED | 1087 lines, zero `any`, covers all 7 route groups |
| frontend/src/api/openapi.snapshot.json | Committed OpenAPI snapshot | VERIFIED | 25,758 bytes, OpenAPI 3.1.0 |
| frontend/src/lib/queryKeys.ts | Central query-key registry | VERIFIED | job, jobs, brandKits, brandKit, renders, brochure — frozen consts |
| frontend/src/hooks/useJob.ts | Polling hook | VERIFIED | v5 refetchInterval callback signature correct; terminal-state short-circuit |
| frontend/src/components/JobStatusCard.tsx | 5-state status renderer | VERIFIED | 140 lines; queued/running/succeeded/failed/cancelled branches + single + array result_ref handling |
| frontend/src/components/RenderPreview.tsx | PNG/PDF preview | VERIFIED | PNG <img> inline; PDF <a download> (no <object>) |
| frontend/src/components/DashboardLayout.tsx | Sidebar + Outlet | VERIFIED | 7-entry NAV, SidebarProvider wrapper |
| frontend/src/pages/brand-kits/* | 3 pages (list, new, detail) | VERIFIED | All substantive (90/130/177 lines) |
| frontend/src/pages/flyers/* | 2 pages (new, status) | VERIFIED | new.tsx 360 lines; status.tsx 21-line wrapper around JobStatusCard (thin by design per plan 21-06) |
| frontend/src/pages/brochures/* | 2 pages (new, status) | VERIFIED | new.tsx 274 lines; status.tsx 111 lines with 3-artifact fetch |
| frontend/src/pages/social/posts/* | 2 pages (new, status) | VERIFIED | new.tsx 312 lines; status.tsx 32-line wrapper |
| frontend/src/pages/social/campaigns/* | 2 pages (new, status) | VERIFIED | new.tsx 337 lines with Checkbox group for platforms; status.tsx 35-line wrapper |
| frontend/src/pages/jobs/list.tsx | Jobs table + filters | VERIFIED | 243 lines with Table + 2 Select filters + per-row JobStatusBadge |
| frontend/src/pages/renders/gallery.tsx | Gallery grid + filter | VERIFIED | 177 lines with Card grid + Kind Select + pagination |
| flyer_generator/api/routes/brand_kits.py | Logo-stream route added | VERIFIED | get_brand_kit_logo with _logo_is_within containment guard |
| flyer_generator/api/routes/brochures.py | Brochure detail route added | VERIFIED | get_brochure_detail returning BrochureDetail (3 render URLs) |
| flyer_generator/api/routes/jobs.py | list_jobs route added | VERIFIED | GET /api/v1/jobs with limit/offset + kind/status enum filters |
| flyer_generator/api/routes/renders.py | list_renders route added | VERIFIED | GET /api/v1/renders with limit/offset + kind/since filters |

### Key Link Verification

Manual grep verification of all wiring patterns (gsd-tools pattern matcher has false negatives for multi-line `client.GET(\n path,\n opts\n)` calls but all wiring is confirmed present):

| From | To | Via | Status |
|------|-----|-----|--------|
| frontend/src/hooks/useJob.ts | GET /api/v1/jobs/{job_id} | openapi-fetch client.GET | WIRED (line 16: `await client.GET("/api/v1/jobs/{job_id}"...)`) |
| frontend/src/pages/brand-kits/list.tsx | GET /api/v1/brand-kits | openapi-fetch client.GET | WIRED (line 22: `client.GET("/api/v1/brand-kits"...)`) |
| frontend/src/pages/brand-kits/new.tsx | POST /api/v1/brand-kits/fetch | client.POST | WIRED (line 56-58: `client.POST("/api/v1/brand-kits/fetch"...)`) |
| frontend/src/pages/brand-kits/detail.tsx | GET /api/v1/brand-kits/{slug} | client.GET | WIRED (line 28-33) |
| frontend/src/pages/flyers/new.tsx | POST /api/v1/flyers | client.POST | WIRED (line 146) |
| frontend/src/pages/flyers/status.tsx | JobStatusCard | import | WIRED |
| frontend/src/pages/brochures/new.tsx | POST /api/v1/brochures | client.POST | WIRED (line 128) |
| frontend/src/pages/brochures/status.tsx | GET /api/v1/brochures/{brochure_id} | client.GET | WIRED (line 40-43) |
| frontend/src/pages/social/posts/new.tsx | POST /api/v1/social/posts | client.POST | WIRED (line 131) |
| frontend/src/pages/social/campaigns/new.tsx | POST /api/v1/social/campaigns | client.POST | WIRED (line 144) |
| frontend/src/pages/jobs/list.tsx | GET /api/v1/jobs | client.GET | WIRED (line 100) |
| frontend/src/pages/renders/gallery.tsx | GET /api/v1/renders | client.GET | WIRED (line 76) |
| frontend/src/components/LogoGallery.tsx | /api/v1/brand-kits/{slug}/logos/{filename} | `<img src>` | WIRED |
| frontend/src/components/JobStatusCard.tsx | frontend/src/hooks/useJob.ts | import | WIRED |
| frontend/src/components/JobStatusBadge.tsx | frontend/src/hooks/useJob.ts | import | WIRED |
| frontend/src/main.tsx | QueryClientProvider | JSX wrap | WIRED |
| frontend/src/api/client.ts | frontend/src/api/schema.gen.ts | `import type { paths }` | WIRED (line 27) |
| frontend/vite.config.ts | http://localhost:8000 | server.proxy | WIRED (line 15-18) |
| frontend/src/index.css | tailwindcss | @import | WIRED |

### Data-Flow Trace (Level 4)

Top-level pages that render dynamic data:

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| pages/brand-kits/list.tsx | `data.items` (brand-kit array) | `client.GET /api/v1/brand-kits` | Yes (SQL + FS scan in routes/brand_kits.py list_brand_kits) | FLOWING |
| pages/brand-kits/detail.tsx | `data.brand_kit` | `client.GET /api/v1/brand-kits/{slug}` | Yes (existing Phase 20 endpoint) | FLOWING |
| pages/jobs/list.tsx | `data.items` (job array) | `client.GET /api/v1/jobs` | Yes (new list_jobs route with PaginatedJobs) | FLOWING |
| pages/renders/gallery.tsx | `data.items` (render array) | `client.GET /api/v1/renders` | Yes (new list_renders route with PaginatedRenders) | FLOWING |
| pages/flyers/status.tsx | job state via JobStatusCard | useJob -> GET /jobs/{id} | Yes (Phase 20 endpoint) | FLOWING |
| pages/brochures/status.tsx | job + detail | useJob + client.GET /brochures/{id} | Yes (new get_brochure_detail route) | FLOWING |
| components/JobStatusCard.tsx | `job` | useJob hook | Yes | FLOWING |
| components/LogoGallery.tsx | logo list (prop) | parent passes kit.logos | Yes | FLOWING |
| components/PaletteSwatches.tsx | palette (prop) | parent passes kit.palette | Yes | FLOWING |

All wired artifacts are connected to real data sources (DB queries or upstream hook), not hardcoded empty/static data.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Frontend TypeScript compilation | `pnpm typecheck` | tsc --noEmit exits 0, no output | PASS |
| Frontend unit tests | `pnpm test --run` | 22/22 tests in 11 files pass in 6.95s | PASS |
| Frontend production build | `pnpm build` | tsc -b + vite build succeed in 597ms; dist/index.html + dist/assets/*.js + *.css + 3 woff2 fonts emitted | PASS |
| Backend API tests (no regression) | `pytest tests/api/ -q` | 172/172 pass in 5.57s | PASS |
| Routes file parses | Read routes.tsx | 15 routes including index redirect, 13 feature routes, wildcard 404 | PASS |
| openapi-fetch client exists | ls frontend/src/api/client.ts | 94 lines, exports client + 9 type aliases + isTerminalStatus guard | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| FE-01 | 21-01 | React + Vite + TS + ShadCN + Tailwind scaffold; pnpm dev boots; pnpm build emits production bundle | SATISFIED | Build/typecheck/test all green; frontend/ directory populated with full scaffold |
| FE-02 | 21-02 | Typed API client generated from Phase 20 OpenAPI; dev proxy to :8000/api/v1 | SATISFIED | schema.gen.ts (1087 lines, zero `any`) + client.ts (openapi-fetch) + vite.config.ts proxy configured |
| FE-03 | 21-03 | Dashboard shell with sidebar for 7 sections | SATISFIED | DashboardLayout.tsx uses ShadCN Sidebar with 7 NavLinks |
| FE-04 | 21-05 | Brand Kits page (list + detail + scrape modal) | SATISFIED | 3 pages (list/new/detail) all substantive; new BE logo-stream route added |
| FE-05 | 21-06 | Flyer creator form + job polling + PNG preview | SATISFIED | flyers/new.tsx (360 lines) + status.tsx JobStatusCard wrapper |
| FE-06 | 21-07 | Brochure creator form + 3-artifact status page | SATISFIED | brochures/new.tsx (274 lines) + status.tsx with BrochureDetail fetch + new BE detail route + parallel-ID pattern in task |
| FE-07 | 21-08 | Social post creator + status page | SATISFIED (with plan-acknowledged deferral of validation_report/audit_report) | social/posts/new.tsx + status.tsx; deferral documented in plan 21-08 |
| FE-08 | 21-09 | Campaign creator with multi-platform + per-platform result grid | SATISFIED | social/campaigns/new.tsx with Checkbox group + status.tsx exercises array-result_ref branch of JobStatusCard |
| FE-09 | 21-10 | Jobs page with filters + row-level polling + click-through | SATISFIED | jobs/list.tsx with Table + 2 filters + JobStatusBadge per-row polling + statusPathFor click-through; new BE list_jobs route |
| FE-10 | 21-11 | Renders gallery with download + inline preview + kind/date filter | SATISFIED | renders/gallery.tsx with CSS-grid + kind Select + pagination; new BE list_renders route |

No orphaned requirements. All 10 FE-01..FE-10 IDs declared in plan frontmatter and satisfied.

### Anti-Patterns Found

Four warnings surfaced in 21-REVIEW.md. All are polish items that do NOT block the stated goal — they belong to a follow-up phase.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| flyer_generator/api/tasks/brochure.py | 78 | Worker reads `payload.get("workflow_name", ...)` but schema sends `workflow` | Warning | Goal-adjacent — brochure still renders with the default `turbo_landscape` workflow; user-supplied overrides silently ignored. Documented as WR-01. |
| flyer_generator/api/routes/brand_kits.py | 121-173 | list_brand_kits FS-fuse double-counts across pages (db_slugs built from current page only) | Warning | Pagination correctness — total count is unstable across pages + possible duplicate rows. v1 single-user datasets are small enough this doesn't visibly break the goal, but it's a latent landmine. Documented as WR-02. |
| flyer_generator/api/routes/brand_kits.py + brochures.py | 66-83 / 32-47 | Job enqueue failure leaves orphan QUEUED row (no compensating transition) | Warning | Data-integrity — if Redis/arq is down at enqueue time, a ghost QUEUED JobRecord lingers. Dashboard polling would spin forever on that row. Doesn't block the happy-path goal; needs fix before production. Documented as WR-03. |
| frontend/src/components/RenderPreview.tsx | 17-23 | `lower.includes("/pdf")` false-positives on any URL path containing "/pdf" substring | Warning | Low-probability today — current URLs are `/api/v1/renders/{ulid}/image` and gallery already branches on `isPdfKind(r.kind)`. Latent landmine if URL scheme changes. Documented as WR-04. |

All four are recommended for a Phase 21-polish or Phase 22 follow-up. None prevent the goal's capabilities (a)-(f) from working end-to-end when the dependencies (Phase 20 backend + happy-path enqueue) are healthy.

### Human Verification Required

See `human_verification:` in the frontmatter above for 9 runtime-observable tests that require a live Phase 20 backend + the Vite dev server:

1. **Capability (a)** — brand kit browse + scrape end-to-end
2. **Capability (b)** — flyer form -> job polling -> PNG preview
3. **Capability (c)** — brochure form -> 2 PNGs + PDF
4. **Capability (d)** — social post form -> image (note documented v1 deferral of validation_report/audit_report)
5. **Capability (e)** — campaign form -> per-platform grid
6. **Capability (f)** — render gallery with inline preview + download
7. **FE-09** — jobs page with row-level polling + click-through
8. **FE-03** — sidebar active-state highlighting
9. **Dev loop** — pnpm dev boots on :5173 with working proxy

### Gaps Summary

No functional gaps block the goal. All 11 plans completed; all 10 requirements satisfied; all automated checks green.

One acknowledged scope deviation: **FE-07 validation_report / audit_report display** — the goal wording says "watch copy + image + validation report render" but plan 21-08 explicitly descoped validation_report / audit_report display for v1 because Phase 20 does not yet expose a read route for `PostRecord.audit_report`. The social post status page shows only the rendered image. This is documented in plan 21-08's objective section. If the goal wording is treated as strict, this could be considered a partial-FE-07; if treated as scoped-per-plan, it is satisfied. Flagged for human decision via the human_verification list.

The four review warnings (WR-01..WR-04) are polish items recommended for a follow-up phase.

---

_Verified: 2026-04-23T14:58:28Z_
_Verifier: Claude (gsd-verifier)_

---

## Gap Closure Re-Verification (2026-04-23)

**Re-verified:** 2026-04-23T20:52:26Z
**Trigger:** Wave 6 gap closure — plans 21-12, 21-13, 21-14 shipped to close 4 REVIEW warnings (WR-01..WR-04) + 2 info items (IN-01, IN-03).
**Re-verification scope:** Targeted grep + regression-test + full-suite re-run. Initial 13 must-haves NOT re-evaluated (they already passed and are unchanged; regression check: all tests still green, no FE-* requirement newly failing).

### Updated Status

| Field | Before | After |
|-------|--------|-------|
| status | human_needed | human_needed (unchanged — 9 human UAT items still open, they are runtime-observable and not affected by gap closure) |
| score | 13/13 | 13/13 (unchanged) |
| warnings open | 4 (WR-01..WR-04) | 0 |
| info items open | 9 | 7 (IN-01, IN-03 closed as companion fixes in Waves 6) |
| BE test count | 172 | 176 (+4 new regression tests) |
| FE test count | 22 | 26 (+4 new RenderPreview tests) |

### Warning Closure Table

| Warning | File(s) | Status | Evidence | Regression Test(s) |
|---------|---------|--------|----------|--------------------|
| WR-01 | flyer_generator/api/tasks/brochure.py:79 | FIXED | `grep 'payload.get("workflow_name"'` → 0 hits; `grep 'payload.get("workflow"'` → 1 hit at line 79; code reads `workflow_name=payload.get("workflow", "turbo_landscape")` | tests/api/test_worker_tasks.py::test_brochure_task_honors_user_supplied_workflow (line 463) — posts `{"workflow": "foo_portrait", ...}` and asserts generate_template_images called with workflow_name="foo_portrait" |
| WR-02 | flyer_generator/api/routes/brand_kits.py:146-148 | FIXED | `grep 'all_db_slugs'` → 3 hits (declaration at 146, doc ref at 151, usage at 162); `grep 'db_slugs = {r.slug for r in rows}'` → 0 hits; `list_brand_kits` computes `all_db_slugs = set(select(BrandKitRecord.slug))` BEFORE FS enumeration + `merged.sort(key=lambda s: _as_utc(s.scraped_at), reverse=True)` for IN-03 companion | tests/api/test_brand_kits_routes.py::test_list_brand_kits_pagination_no_duplicates_across_pages (line 391) — seeds 3 DB + 1 FS kit, paginates limit=2, asserts total=4 stable across pages + union of slugs has 4 unique values + FS-only slug appears exactly once |
| WR-03 brand-kits half | flyer_generator/api/routes/brand_kits.py:96-106 | FIXED | `grep 'except Exception'` → match at line 96 (new) + line 171 (pre-existing corrupt-JSON skip, unrelated); `grep 'enqueue_failed'` → 1 hit at line 102; `grep 'str(exc)'` → 0 hits (T-21-13-04 info-disclosure guardrail honored); pattern: try/except wraps `arq_pool.enqueue_job`, fresh session via `request.app.state.sessionmaker()`, typed `error_detail = {"reason": "enqueue_failed", "type": type(exc).__name__}`, re-raise | tests/api/test_brand_kits_routes.py::test_post_brand_kit_fetch_enqueue_failure_marks_job_failed (line 477) — monkeypatches enqueue_job to raise RuntimeError, asserts propagation + JobRecord FAILED + error_detail.reason == "enqueue_failed" + "redis" NOT in str(error_detail) |
| WR-03 brochures half | flyer_generator/api/routes/brochures.py:46-67 | FIXED | `grep 'except Exception'` → match at line 52; `grep 'enqueue_failed'` → 2 hits (comment line 55 + dict key line 63); `grep 'str(exc)'` → 0 hits; identical try/except + fresh-session + typed error_detail + re-raise pattern | tests/api/test_brochure_routes.py::test_post_brochure_enqueue_failure_marks_job_failed (line 156) — uses ASGITransport(raise_app_exceptions=False) to assert r.status_code >= 500 + JobRecord FAILED + error_detail.reason == "enqueue_failed" |
| WR-04 | frontend/src/components/RenderPreview.tsx:42-50 + frontend/src/pages/brochures/status.tsx:103 | FIXED | `grep 'lower.includes("/pdf")'` → 0 hits; `grep 'PDF_SUFFIX_RE'` → 2 hits (declaration line 42 + usage line 50); `grep 'isPdf'` → 4 hits in RenderPreview.tsx (prop type, destructure, branch, comment); `grep 'isPdf'` → 1 hit in brochures/status.tsx at line 103 (pdf_render_url slot); regex is strict `/\.pdf($|\?)/i`; OR-combined with explicit `isPdf` prop; IN-01 companion `suggestPdfFilename()` helper ensures {ulid}.pdf filename | frontend/src/components/RenderPreview.test.tsx — 4 `it()` blocks: (1) ULID starting with "pdf" in path does NOT trigger PDF branch (WR-04), (2) `.pdf` suffix triggers anchor, (3) `.pdf?query` suffix triggers anchor, (4) `isPdf` prop forces anchor + filename ends in .pdf (IN-01) |

### Info Items Closed (Companion Fixes)

| Info | Companion to | Evidence |
|------|--------------|----------|
| IN-01 | WR-04 (plan 21-14) | `suggestPdfFilename()` helper in RenderPreview.tsx returns `{ulid}.pdf` for `/renders/{id}/image` URLs and appends `.pdf` to generic last-segment fallback. Test case 4 asserts download attr matches `/\.pdf$/`. |
| IN-03 | WR-02 (plan 21-13) | `merged.sort(key=lambda s: _as_utc(s.scraped_at), reverse=True)` before pagination slice — FS-only entries now interleave by recency instead of always tailing. Datetime normalization handles SQLite naive/aware mismatch. |

### Info Items Still Open (Not in Wave 6 Scope)

IN-02 (list_renders accepts untyped kind string), IN-04 (useJob swallows error message), IN-05 (JobStatusCard stale-closure risk), IN-06 (brochure form parses JSON twice), IN-07 (label not associated with Select — accessibility), IN-08 (dead code in task_generate_brochure getattr fallback), IN-09 (logo_bytes hard-coded None warning needed). All 7 remaining info items are polish/a11y/dev-ergonomics — none block the goal.

### Regression Test Suite Results

**Backend (pytest tests/api/):**
```
176 passed, 1 warning in 5.80s
```
- Previous: 172 passed. Delta: +4 tests (2 from plan 21-12 + 2 from plan 21-13). The single warning is pre-existing `copy` field-shadow in `flyer_generator/social/models.py:127` — not in this phase's scope.

**Frontend (pnpm test --run):**
```
Test Files  12 passed (12)
     Tests  26 passed (26)
   Duration  6.63s
```
- Previous: 22 passed in 11 files. Delta: +4 tests in 1 new file (RenderPreview.test.tsx from plan 21-14).

### New Regression Tests (Traceability)

| Plan | Test file | Test name | Pins |
|------|-----------|-----------|------|
| 21-12 | tests/api/test_worker_tasks.py | test_brochure_task_honors_user_supplied_workflow | WR-01 payload-key translation |
| 21-12 | tests/api/test_brochure_routes.py | test_post_brochure_enqueue_failure_marks_job_failed | WR-03 brochures compensating transition |
| 21-13 | tests/api/test_brand_kits_routes.py | test_list_brand_kits_pagination_no_duplicates_across_pages | WR-02 pagination dedup + stable total |
| 21-13 | tests/api/test_brand_kits_routes.py | test_post_brand_kit_fetch_enqueue_failure_marks_job_failed | WR-03 brand-kits compensating transition |
| 21-14 | frontend/src/components/RenderPreview.test.tsx | RenderPreview > does not treat a URL containing the substring '/pdf' as a PDF (WR-04) | WR-04 false-positive prevention |
| 21-14 | frontend/src/components/RenderPreview.test.tsx | RenderPreview > renders a download anchor for a URL ending in .pdf | Happy-path .pdf suffix |
| 21-14 | frontend/src/components/RenderPreview.test.tsx | RenderPreview > renders a download anchor for a URL ending in .pdf?query | .pdf with query string |
| 21-14 | frontend/src/components/RenderPreview.test.tsx | RenderPreview > renders a download anchor when isPdf=true even without a .pdf suffix | isPdf prop threading + IN-01 filename |

### Regression Check: No New Regressions in FE-01..FE-10

All 10 FE-* requirements remain SATISFIED. The three gap-closure plans touched exactly 5 source files:

- `flyer_generator/api/tasks/brochure.py` — supports FE-06 (brochure); fix makes user-supplied workflow actually take effect. No behavioral regression for the default path (default `"turbo_landscape"` unchanged).
- `flyer_generator/api/routes/brochures.py` — supports FE-06; added compensating transition. Happy path unchanged (enqueue success → JobCreated, same as before).
- `flyer_generator/api/routes/brand_kits.py` — supports FE-04 (brand kits list + scrape); happy path unchanged; pagination now correct + stable; FS-only entries now sorted by recency instead of tailed alphabetically (strict improvement for UX).
- `frontend/src/components/RenderPreview.tsx` — supports FE-06 + FE-10 (brochure PDF + renders gallery). Strict regex + explicit prop → all existing `.pdf` URLs still match; gallery already uses `isPdfKind(r.kind)` so RenderPreview for PNG kinds continues to render inline. No visual regression.
- `frontend/src/pages/brochures/status.tsx` — supports FE-06; only addition is `isPdf` prop on the pdf_render_url slot (deterministic PDF branch now). Front/back PNG slots unchanged.

Full test suites (BE 176/176 + FE 26/26) confirm zero regressions.

### Human Verification Status

9 human UAT items remain (unchanged). They are inherently runtime-observable (visual PDF rendering, job polling cadence, sidebar highlighting, live proxy behavior) and Wave 6's gap-closure work does not reduce that list — none of the 4 review warnings were about UX behaviors that would satisfy a human UAT item. All 9 still need manual verification against a live Phase 20 backend + Vite dev server.

### Final Summary

**Status: human_needed (unchanged, by design).**

The 4 automated warnings from 21-REVIEW.md are definitively closed with grep-verifiable source fixes AND regression tests that would catch re-introduction. The 2 companion info items (IN-01 filename, IN-03 FS-fuse sort order) are closed alongside their parent warnings. 7 remaining info items are out of Wave 6 scope and do not block the goal. The 9 human UAT items are unchanged and still the only path to a `passed` status; they require a live backend + dev server run.

Recommendation: proceed with human UAT (the 9 items already listed in the original frontmatter). If UAT passes, phase 21 can be marked `passed`. If any UAT fails, a new gap-closure wave can be planned targeting the failure.

---

_Re-verified: 2026-04-23T20:52:26Z_
_Verifier: Claude (gsd-verifier)_
_Wave: 6 (gap closure of WR-01..WR-04 + IN-01 + IN-03)_
