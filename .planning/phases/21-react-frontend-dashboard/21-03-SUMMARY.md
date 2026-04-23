---
phase: 21-react-frontend-dashboard
plan: 03
subsystem: ui
tags: [frontend, routing, react-router-v7, shadcn, sidebar, dashboard-shell, data-router]

# Dependency graph
requires:
  - phase: 21-react-frontend-dashboard
    plan: 01
    provides: Vite 8 + React 19 + TS 5.9 + Tailwind v4 + ShadCN scaffold + @/* alias + components.json (style radix-nova, neutral baseColor)
  - phase: 21-react-frontend-dashboard
    plan: 02
    provides: frontend/src/api/client.ts + schema.gen.ts + queryKeys.ts + vite-env.d.ts (typed API layer — NOT consumed in this plan, imported by pages in 21-05..11)
provides:
  - frontend/src/components/DashboardLayout.tsx — SidebarProvider + 7-link NAV + Outlet shared by every dashboard page
  - frontend/src/routes.tsx — createBrowserRouter with 15 routes (1 index-redirect + 13 feature pages + 1 wildcard 404)
  - frontend/src/pages/Error.tsx — React Router v7 errorElement using useRouteError + isRouteErrorResponse
  - frontend/src/pages/NotFound.tsx — wildcard-route handler rendering pathname as JSX-escaped text
  - 13 stub page files under frontend/src/pages/{brand-kits,flyers,brochures,social/{posts,campaigns},jobs,renders} — each 3-line named export replaced by downstream plans 21-05..11
  - frontend/src/components/ui/{sidebar,sheet,navigation-menu,separator,tooltip,input,skeleton}.tsx — 7 ShadCN primitives (5 requested + 2 transitive)
  - frontend/src/hooks/use-mobile.ts — ShadCN-generated mobile-breakpoint hook (sidebar dep)
  - frontend/src/main.tsx — swapped Button smoke test for RouterProvider (QueryClientProvider / Toaster land in 21-04)
affects: [21-04-query-provider-sonner, 21-05-brand-kits, 21-06-flyers, 21-07-brochures, 21-08-social-posts, 21-09-social-campaigns, 21-10-jobs-list, 21-11-renders-gallery]

# Tech tracking
tech-stack:
  added:
    - "react-router@7.14.2 (data-router mode — createBrowserRouter + RouterProvider; imports from 'react-router' single-context bundle)"
    - "ShadCN sidebar / sheet / navigation-menu / separator / tooltip primitives (via shadcn@latest add)"
    - "Transitive ShadCN adds: input, skeleton (pulled by sidebar's field helpers), use-mobile hook"
  patterns:
    - "React Router v7 single-context: imports from `react-router` NOT `react-router-dom` (Pitfall #5). The `react-router-dom` re-export shim still exists in v7, but mixing the two creates two-context bugs where `useNavigate` silently stops working."
    - "data-router mode + errorElement: one errorElement on the root route catches thrown errors from any child route and renders ErrorPage under a centered layout. NavLink render-prop receives `{ isActive }` from the router; forwarded to ShadCN SidebarMenuButton's `isActive` prop (which sets `data-active={true}` on the underlying button)."
    - "Wildcard `*` child route under the root layout: unmatched paths render NotFoundPage INSIDE the sidebar shell (sidebar still visible, navigation still works) — not a full-page takeover. A separate ErrorPage (not under DashboardLayout) handles render-time thrown errors."
    - "Index redirect: `{ index: true, element: <Navigate to=\"/brand-kits\" replace /> }` — hard-coded target (no user input → no open-redirect surface per T-11)."

key-files:
  created:
    - "frontend/src/components/DashboardLayout.tsx (54 lines, named export)"
    - "frontend/src/pages/Error.tsx (25 lines, named export)"
    - "frontend/src/pages/NotFound.tsx (19 lines, named export)"
    - "frontend/src/routes.tsx (51 lines, named export `router`)"
    - "frontend/src/pages/brand-kits/list.tsx (stub → 21-05: BrandKitsListPage)"
    - "frontend/src/pages/brand-kits/new.tsx (stub → 21-05: ScrapeBrandKitPage)"
    - "frontend/src/pages/brand-kits/detail.tsx (stub → 21-05: BrandKitDetailPage)"
    - "frontend/src/pages/flyers/new.tsx (stub → 21-06: NewFlyerPage)"
    - "frontend/src/pages/flyers/status.tsx (stub → 21-06: FlyerStatusPage)"
    - "frontend/src/pages/brochures/new.tsx (stub → 21-07: NewBrochurePage)"
    - "frontend/src/pages/brochures/status.tsx (stub → 21-07: BrochureStatusPage)"
    - "frontend/src/pages/social/posts/new.tsx (stub → 21-08: NewSocialPostPage)"
    - "frontend/src/pages/social/posts/status.tsx (stub → 21-08: SocialPostStatusPage)"
    - "frontend/src/pages/social/campaigns/new.tsx (stub → 21-09: NewCampaignPage)"
    - "frontend/src/pages/social/campaigns/status.tsx (stub → 21-09: CampaignStatusPage)"
    - "frontend/src/pages/jobs/list.tsx (stub → 21-10: JobsListPage)"
    - "frontend/src/pages/renders/gallery.tsx (stub → 21-11: RenderGalleryPage)"
    - "frontend/src/components/ui/sidebar.tsx (ShadCN, ~700 lines)"
    - "frontend/src/components/ui/sheet.tsx (ShadCN)"
    - "frontend/src/components/ui/navigation-menu.tsx (ShadCN)"
    - "frontend/src/components/ui/separator.tsx (ShadCN)"
    - "frontend/src/components/ui/tooltip.tsx (ShadCN)"
    - "frontend/src/components/ui/input.tsx (ShadCN — transitive from sidebar)"
    - "frontend/src/components/ui/skeleton.tsx (ShadCN — transitive from sidebar)"
    - "frontend/src/hooks/use-mobile.ts (ShadCN — transitive from sidebar)"
  modified:
    - "frontend/package.json — added `react-router: ^7`"
    - "frontend/pnpm-lock.yaml — regenerated for react-router + ShadCN transitive deps"
    - "frontend/src/main.tsx — swapped Button smoke test for RouterProvider (5 lines in, 15 lines out)"

key-decisions:
  - "Used ShadCN SidebarMenuButton's `isActive` boolean prop unchanged. The generated sidebar.tsx (line 492/500/511) accepts `isActive?: boolean` and maps it to `data-active={isActive}` on the underlying <button>. No prop-name remap was needed — the plan's warning about potential prop drift was not triggered in shadcn 4.4.0."
  - "`errorElement` is declared ONCE on the root route (the DashboardLayout element). Any render-time throw from any child route propagates to this handler per React Router v7 error-bubbling. The plan explicitly permitted minor tweaks to handle the error-type union — none were needed. `isRouteErrorResponse` plus `error instanceof Error` plus a string fallback covers the three cases (route throw Response, plain JS Error, everything else)."
  - "Transitive ShadCN adds accepted as-is. `npx shadcn@latest add sidebar sheet navigation-menu separator tooltip --yes` also pulled `input`, `skeleton`, and `use-mobile.ts`. These are sidebar internal deps (input for the search form, skeleton for loading states, use-mobile for responsive collapse). Committing them now prevents later plans from re-running `shadcn add` against the same files and hitting 'skipped 1 file' diffs."
  - "Stubs are 3-line named exports, not empty shells. Each stub file names its replacement plan in a comment and renders 'X (stub — plan 21-NN replaces).' as muted text. This means `pnpm dev` shows meaningful page content immediately, and Ctrl+F 'stub — plan 21-NN' finds every replacement target from any downstream plan."
  - "Dev-server smoke test on port 5177 (not 5173). Another Vite process was already using 5173 in this environment; retried with `--port 5177` to confirm `/`, `/brand-kits`, and unmatched `/nonexistent` all serve HTTP 200 (SPA fallback — client-side NotFound is the correct render for unmatched paths)."

requirements-completed: [FE-03]

# Metrics
duration: 5min
completed: 2026-04-23
---

# Phase 21 Plan 03: Router + Dashboard Shell Summary

**React Router v7 data-router mode + ShadCN sidebar dashboard shell wired end-to-end. 15 routes (1 index-redirect + 13 stub feature pages + 1 wildcard 404) under a single DashboardLayout, `pnpm build` produces a 395 KB JS / 62 KB CSS bundle, and the dev server serves every sidebar NavLink with client-side navigation.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-23T12:18:00Z (approx)
- **Tasks:** 3
- **Files created:** 21 (3 router/layout/error files + 13 stubs + 5 ShadCN primitives direct + additional transitive files under src/components/ui/ and src/hooks/)
- **Files modified:** 3 (package.json, pnpm-lock.yaml, main.tsx)

## Accomplishments

- `react-router@7.14.2` installed from `react-router` NOT `react-router-dom` (single-context invariant — `grep react-router-dom` returns 0 in both `package.json` dependencies and the entire `src/` tree).
- Seven ShadCN primitives in place: `sidebar.tsx`, `sheet.tsx`, `navigation-menu.tsx`, `separator.tsx`, `tooltip.tsx` (plan-requested) plus `input.tsx`, `skeleton.tsx`, and `use-mobile.ts` (transitive, pulled by sidebar). Every later plan can now `npx shadcn add <comp>` additional components without fighting for `components.json`.
- `DashboardLayout` is the root route element — SidebarProvider wraps a 7-link NAV (Brand kits / New flyer / New brochure / New post / New campaign / Jobs / Renders) plus `<Outlet />` for child routes. Active link is highlighted via NavLink's `isActive` → SidebarMenuButton's `data-active={true}`.
- `routes.tsx` exports `router` from `createBrowserRouter(...)` with 15 routes: 1 index `Navigate to="/brand-kits" replace`, 13 feature-page routes, 1 wildcard `*` → NotFoundPage. Root route carries `errorElement: <ErrorPage />` which catches any thrown render error from any descendant.
- `main.tsx` now renders `<RouterProvider router={router}>` inside `<React.StrictMode>` — the Button smoke test is gone, the app is the router.
- 13 stub page files, each a 3-line named export with its replacement plan commented at the top. Ctrl+F `stub — plan 21-NN` finds every replacement target.
- `pnpm typecheck` exits 0, `pnpm build` succeeds (395 KB JS / 62 KB CSS / ~410 ms build time), `pnpm dev` on port 5177 serves `/`, `/brand-kits`, and unmatched paths all at HTTP 200 (SPA fallback → client-side NotFound renders).

## Task Commits

1. **Task 1: Install react-router v7 + ShadCN sidebar primitives** — `24dd950` (feat)
2. **Task 2: Add DashboardLayout + ErrorPage + NotFoundPage** — `a195621` (feat)
3. **Task 3: Wire RouterProvider + 15-route table with stub pages** — `13a8de7` (feat)

_Orchestrator adds the metadata commit after all Wave 2 agents merge._

## Files Created/Modified

**Created:**
- `frontend/src/components/DashboardLayout.tsx` — SidebarProvider + 7-link NAV + Outlet
- `frontend/src/pages/Error.tsx` — errorElement renderer using useRouteError + isRouteErrorResponse
- `frontend/src/pages/NotFound.tsx` — wildcard-route renderer
- `frontend/src/routes.tsx` — createBrowserRouter config (15 routes)
- `frontend/src/pages/brand-kits/{list,new,detail}.tsx` — 3 stubs (→ 21-05)
- `frontend/src/pages/flyers/{new,status}.tsx` — 2 stubs (→ 21-06)
- `frontend/src/pages/brochures/{new,status}.tsx` — 2 stubs (→ 21-07)
- `frontend/src/pages/social/posts/{new,status}.tsx` — 2 stubs (→ 21-08)
- `frontend/src/pages/social/campaigns/{new,status}.tsx` — 2 stubs (→ 21-09)
- `frontend/src/pages/jobs/list.tsx` — 1 stub (→ 21-10)
- `frontend/src/pages/renders/gallery.tsx` — 1 stub (→ 21-11)
- `frontend/src/components/ui/sidebar.tsx` — ShadCN Sidebar (~700 lines)
- `frontend/src/components/ui/sheet.tsx` — ShadCN Sheet
- `frontend/src/components/ui/navigation-menu.tsx` — ShadCN NavigationMenu
- `frontend/src/components/ui/separator.tsx` — ShadCN Separator
- `frontend/src/components/ui/tooltip.tsx` — ShadCN Tooltip
- `frontend/src/components/ui/input.tsx` — ShadCN Input (transitive from sidebar)
- `frontend/src/components/ui/skeleton.tsx` — ShadCN Skeleton (transitive from sidebar)
- `frontend/src/hooks/use-mobile.ts` — ShadCN mobile-breakpoint hook (sidebar dep)

**Modified:**
- `frontend/package.json` — added `react-router: ^7` to dependencies
- `frontend/pnpm-lock.yaml` — regenerated
- `frontend/src/main.tsx` — swapped Button smoke test for `<RouterProvider router={router} />` inside StrictMode

## Decisions Made

- **ShadCN SidebarMenuButton props unchanged.** The generated `sidebar.tsx` (line 492-511) exports `SidebarMenuButton` with the prop `isActive?: boolean` that maps to `data-active={isActive}` on the rendered button. The plan pre-flagged that this prop name might have drifted since RESEARCH.md Pattern 5 was captured — in shadcn@4.4.0 + radix-nova preset, it has NOT drifted. The code uses the plan's verbatim render-prop chain (`<NavLink>{({ isActive }) => <SidebarMenuButton isActive={isActive}>…</SidebarMenuButton>}</NavLink>`) without modification.
- **`errorElement` scope.** Declared on the root route only. React Router v7 bubbles render-time throws from any child up to the nearest `errorElement` — so one handler catches every page. Downstream plans that want route-specific error rendering can add their own `errorElement` per child; Phase 21 does not require this (RESEARCH.md Pattern 5 places a single errorElement at the root).
- **`errorElement` error-type union handled cleanly.** `useRouteError()` returns `unknown` in v7. Narrowed via `isRouteErrorResponse(error)` → route-level 4xx/5xx Response with `.status` / `.statusText` / `.data`, `error instanceof Error` → plain JS throw with `.message`, else fall through to the default title. No custom types required.
- **Transitive ShadCN adds accepted.** `shadcn add sidebar sheet navigation-menu separator tooltip` pulled `input.tsx`, `skeleton.tsx`, and `src/hooks/use-mobile.ts` as sidebar's internal deps. Committed all of them in Task 1 so later plans don't re-trigger the same generation and diff against `--skipped` files.
- **Stubs are meaningful, not empty.** Each stub renders `"<feature> (stub — plan 21-NN replaces)."` in muted text with the plan number embedded. `pnpm dev` shows concrete page content immediately, and downstream plans have a Ctrl+F-findable target marker.
- **No modifications to STATE.md or ROADMAP.md.** Per parallel-executor contract, the orchestrator owns those writes after all Wave 2 agents merge.
- **Did NOT install TanStack Query / Toaster / MSW.** Per the plan, `QueryClientProvider` and `<Toaster />` land in plan 21-04, and MSW is a plan 21-02-or-later test-harness concern. Keeping each plan's diff tight.

## Which ShadCN Component Props Differed from RESEARCH.md Pattern 5

Per the plan's output spec ("Which ShadCN sidebar/sheet/navigation-menu component props differed from RESEARCH.md Pattern 5"):

| Component | Pattern 5 expectation | Actual shadcn@4.4.0 behavior | Result |
|-----------|----------------------|------------------------------|--------|
| `SidebarProvider` | wraps Sidebar + main | matches | no change |
| `Sidebar` | top-level | matches | no change |
| `SidebarHeader` / `SidebarContent` | content slots | match | no change |
| `SidebarMenu` / `SidebarMenuItem` | list wrappers | match | no change |
| `SidebarMenuButton` | accepts `isActive?: boolean` | matches (line 492, 500, 511 of generated sidebar.tsx) | no change |

No prop drift encountered. The plan's verbatim NavLink render-prop → `isActive` → SidebarMenuButton chain works unmodified. The plan's fallback advice (accept `data-active` or `aria-current` if the prop name drifted) was not needed.

## errorElement Tweaks for React Router v7 Error-Type Union

Per the plan's output spec ("any `errorElement` tweaks needed to handle React Router v7's error-type union"):

**None beyond the three standard narrows** — `isRouteErrorResponse(error)` for route-level Response errors, `error instanceof Error` for thrown JS errors, fall-through for everything else. This is the shape the RESEARCH.md pattern already embedded; v7's `useRouteError()` returns `unknown` and the narrows are the idiomatic way to extract a renderable message.

## Deviations from Plan

**None** — plan executed exactly as written.

Rule 1 / Rule 2 / Rule 3 triggers scanned during each task:
- Task 1: no typecheck failures, `react-router` installed verbatim, ShadCN CLI non-interactive run succeeded, transitive adds accepted.
- Task 2: typecheck passes on first run, no prop drift, no errorElement tweaks needed.
- Task 3: typecheck + build pass on first run, dev server confirms route resolution.

The only noteworthy nuance (not a deviation): the dev-server smoke test used port 5177 instead of 5173 because another Vite process was already bound to 5173 in this environment. This is a test-harness concession, not a plan deviation — production routing / build / typecheck all use the plan's configuration.

## Issues Encountered

- **Port 5173 in use during dev-server smoke test.** Retried with `--port 5177`; all three tested paths returned HTTP 200 (SPA fallback is correct — the 404 is rendered client-side by NotFoundPage). No code change, no impact on downstream plans — Vite's default port is still 5173 per the scaffold.
- **`msw` build-script warning from pnpm.** `Ignored build scripts: msw.` — MSW (not installed by this plan; presumably queued for a later test-harness plan) needs `pnpm approve-builds` before it can run its postinstall. Not blocking here because MSW isn't used by plan 21-03 — flagged for whichever plan adds the test harness.

## User Setup Required

None for this plan. Downstream plans at runtime will still need the Phase 20 backend on :8000 (the router itself doesn't make API calls — stubs just render text).

## Next Phase Readiness

- **Ready for plan 21-04 (QueryClientProvider + Toaster):** `main.tsx` is the landing pad. Plan 21-04 wraps `<RouterProvider>` in `<QueryClientProvider client={queryClient}>` and appends `<Toaster />` outside the router tree. No changes to `routes.tsx` or any page component needed.
- **Ready for plans 21-05..21-11 (feature pages):** Every stub page is a named export with a predictable import path (`@/pages/<area>/<name>`). Replacing a stub means rewriting the file in place — `routes.tsx` needs no edits because the imports are stable.
- **Stub inventory (Ctrl+F target for downstream executors):** 13 files, each containing `stub — plan 21-NN replaces` where NN matches the replacement plan.

## Known Stubs

Per Stub-Tracking rule: the 13 feature-page files are intentional stubs. Each renders placeholder muted text and names its replacement plan. These are expected by the phase structure — plans 21-05..21-11 replace them. Documented here so the verifier does not flag them as forgotten work:

| File | Component | Intentional? | Replaced by |
|------|-----------|--------------|-------------|
| `src/pages/brand-kits/list.tsx` | `BrandKitsListPage` | yes | 21-05 |
| `src/pages/brand-kits/new.tsx` | `ScrapeBrandKitPage` | yes | 21-05 |
| `src/pages/brand-kits/detail.tsx` | `BrandKitDetailPage` | yes | 21-05 |
| `src/pages/flyers/new.tsx` | `NewFlyerPage` | yes | 21-06 |
| `src/pages/flyers/status.tsx` | `FlyerStatusPage` | yes | 21-06 |
| `src/pages/brochures/new.tsx` | `NewBrochurePage` | yes | 21-07 |
| `src/pages/brochures/status.tsx` | `BrochureStatusPage` | yes | 21-07 |
| `src/pages/social/posts/new.tsx` | `NewSocialPostPage` | yes | 21-08 |
| `src/pages/social/posts/status.tsx` | `SocialPostStatusPage` | yes | 21-08 |
| `src/pages/social/campaigns/new.tsx` | `NewCampaignPage` | yes | 21-09 |
| `src/pages/social/campaigns/status.tsx` | `CampaignStatusPage` | yes | 21-09 |
| `src/pages/jobs/list.tsx` | `JobsListPage` | yes | 21-10 |
| `src/pages/renders/gallery.tsx` | `RenderGalleryPage` | yes | 21-11 |

These stubs are required by plan design — the router must resolve all 15 routes before downstream plans can run in parallel in Wave 3. Each stub's goal is satisfied: render a placeholder and be replaceable.

## Self-Check

Verifying claims before proceeding.

**Created files exist:**
- `frontend/src/components/DashboardLayout.tsx` — FOUND
- `frontend/src/pages/Error.tsx` — FOUND
- `frontend/src/pages/NotFound.tsx` — FOUND
- `frontend/src/routes.tsx` — FOUND
- `frontend/src/pages/brand-kits/list.tsx` — FOUND
- `frontend/src/pages/brand-kits/new.tsx` — FOUND
- `frontend/src/pages/brand-kits/detail.tsx` — FOUND
- `frontend/src/pages/flyers/new.tsx` — FOUND
- `frontend/src/pages/flyers/status.tsx` — FOUND
- `frontend/src/pages/brochures/new.tsx` — FOUND
- `frontend/src/pages/brochures/status.tsx` — FOUND
- `frontend/src/pages/social/posts/new.tsx` — FOUND
- `frontend/src/pages/social/posts/status.tsx` — FOUND
- `frontend/src/pages/social/campaigns/new.tsx` — FOUND
- `frontend/src/pages/social/campaigns/status.tsx` — FOUND
- `frontend/src/pages/jobs/list.tsx` — FOUND
- `frontend/src/pages/renders/gallery.tsx` — FOUND
- `frontend/src/components/ui/sidebar.tsx` — FOUND
- `frontend/src/components/ui/sheet.tsx` — FOUND
- `frontend/src/components/ui/navigation-menu.tsx` — FOUND
- `frontend/src/components/ui/separator.tsx` — FOUND
- `frontend/src/components/ui/tooltip.tsx` — FOUND

**Commits exist:**
- `24dd950` (Task 1: react-router + ShadCN primitives) — FOUND
- `a195621` (Task 2: DashboardLayout + ErrorPage + NotFoundPage) — FOUND
- `13a8de7` (Task 3: routes.tsx + stub pages + main.tsx) — FOUND

**Verify runs:**
- `pnpm typecheck` → exits 0
- `pnpm build` → emits `dist/index.html` (462 B), `dist/assets/*.css` (61.77 KB), `dist/assets/*.js` (395.14 KB), build ~410 ms
- `pnpm dev --port 5177` → serves `/` → 200, `/brand-kits` → 200, `/nonexistent` → 200 (SPA fallback, client-renders NotFound)
- `grep -c "react-router-dom" frontend/package.json` → 0
- `grep -r "react-router-dom" frontend/src/` → 0 matches

## Self-Check: PASSED

---
*Phase: 21-react-frontend-dashboard*
*Completed: 2026-04-23*
