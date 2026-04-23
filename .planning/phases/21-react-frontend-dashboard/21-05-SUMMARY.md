---
phase: 21-react-frontend-dashboard
plan: 05
subsystem: ui
tags: [frontend, brand-kits, backend-route, path-traversal, rhf, zod, tanstack-query, shadcn, file-streaming]

# Dependency graph
requires:
  - phase: 20-fastapi-sqlalchemy-backend
    provides: FastAPI app + brand-kits routes (list + detail + fetch). This plan EXTENDS that package with the logo-stream route.
  - phase: 21-react-frontend-dashboard
    plan: 01
    provides: Vite + React + TS + Tailwind + ShadCN scaffold; pnpm + components.json
  - phase: 21-react-frontend-dashboard
    plan: 02
    provides: openapi-fetch client + openapi.snapshot.json + queryKeys registry (BrandKitDetail / BrandKitSummary / brandKits / brandKit)
  - phase: 21-react-frontend-dashboard
    plan: 03
    provides: React Router v7 shell with stub pages at frontend/src/pages/brand-kits/{list,new,detail}.tsx and the 3 routes already wired
  - phase: 21-react-frontend-dashboard
    plan: 04
    provides: Vitest + MSW + Testing Library harness; <Toaster/> wired in main.tsx; queryClient in main.tsx
provides:
  - flyer_generator/api/routes/brand_kits.py -- new GET /api/v1/brand-kits/{slug}/logos/{filename} route + _LOGO_EXT_MIME whitelist + _logo_is_within containment guard (T-1 HIGH mitigation copied from routes/renders.py::_is_within).
  - tests/api/test_brand_kits_routes.py -- 4 new tests (PNG happy path, SVG happy path, URL-encoded traversal 404, missing-file 404). 17 total in this file, 13 prior still pass.
  - frontend/src/api/openapi.snapshot.json -- re-captured (27,038 bytes, up from 25,758); new logo path present.
  - frontend/src/api/schema.gen.ts -- regenerated from the new snapshot.
  - frontend/src/components/PaletteSwatches.tsx -- 5-role palette renderer (inline backgroundColor styles; no dangerouslySetInnerHTML).
  - frontend/src/components/LogoGallery.tsx -- img grid consuming /api/v1/brand-kits/{slug}/logos/{filename}; strips "logos/" prefix from BrandLogo.path; encodeURIComponent on filename.
  - frontend/src/components/BrandKitCard.tsx -- react-router <Link> Card tile.
  - frontend/src/components/ui/{dialog,form,label}.tsx -- new ShadCN primitives (form fetched from new-york style URL because the radix-nova registry returns an empty stub for form).
  - frontend/src/pages/brand-kits/list.tsx -- REPLACED stub. useQuery + <BrandKitCard> grid + Previous/Next pager + empty-state.
  - frontend/src/pages/brand-kits/detail.tsx -- REPLACED stub. useQuery + composed PaletteSwatches + typography + LogoGallery + voice; "Use in flyer/brochure/post" cross-links.
  - frontend/src/pages/brand-kits/new.tsx -- REPLACED stub. RHF + zodResolver + .strict() BrandKitFetchSchema (url + slug); POST /brand-kits/fetch; invalidate + toast + navigate.
  - frontend/src/pages/brand-kits/list.test.tsx -- 2 tests (empty-state + populated).
  - frontend/src/pages/brand-kits/new.test.tsx -- 2 tests (invalid URL + valid submit).
  - frontend/src/test/test-utils.tsx -- EXTENDED: mounts <Toaster /> alongside MemoryRouter so mutation-driven toasts surface in the DOM for findByText assertions.
  - frontend/src/test/setup.ts -- EXTENDED: polyfills window.matchMedia so sonner's Toaster doesn't crash under jsdom.
  - frontend/package.json + pnpm-lock.yaml -- added react-hook-form@^7.73.1, zod@^4.3.6, @hookform/resolvers@^5.2.2 (via shadcn add pulling them as peer deps).
affects: [21-06-flyers, 21-07-brochures, 21-08-social-posts, 21-09-social-campaigns, 21-10-jobs-list, 21-11-renders-gallery]

# Tech tracking
tech-stack:
  added:
    - "react-hook-form@7.73.1 (runtime -- form state + validation)"
    - "zod@4.3.6 (runtime -- schema mirrors of Pydantic request shapes)"
    - "@hookform/resolvers@5.2.2 (runtime -- bridges zod <-> RHF)"
    - "ShadCN dialog + form + label primitives (form pulled from new-york URL, see deviation)"
  patterns:
    - "RHF + zod + ShadCN Form: use `.strict()` to mirror Pydantic's extra=\"forbid\"; use zodResolver(schema) as resolver; FormField renders Controller; FormMessage pulls error.message from fieldState."
    - "File-streaming containment guard: _logo_is_within is a 1:1 copy of routes/renders.py::_is_within. Every new file-streaming route MUST copy this pattern (or share a helper once we have three). 404 on every failure mode -- never 403, never 500, never leak filesystem shape."
    - "SVG whitelist for logos: renders.py excludes SVG (rendered creative output is rasterized); brand-kit logos commonly ARE SVG, so the new whitelist adds .svg -> image/svg+xml."
    - "BrandLogo.path is kit-relative (e.g. \"logos/primary.png\"); LogoGallery strips the \"logos/\" prefix before constructing /api/v1/brand-kits/{slug}/logos/{filename}."
    - "Form-level noValidate disables browser-native type=\"url\" validation so RHF's zod resolver is the ONLY validation path. Without this, jsdom and real browsers block submit before RHF fires, and tests see an untouched form."
    - "Test harness: Toaster lives INSIDE QueryClientProvider (outside MemoryRouter) in renderWithProviders so toasts are captured for findByText; matchMedia polyfill covers jsdom's missing implementation."

key-files:
  created:
    - "flyer_generator/api/routes/brand_kits.py -- MODIFIED (new imports + _LOGO_EXT_MIME + _logo_is_within + get_brand_kit_logo)"
    - "tests/api/test_brand_kits_routes.py -- MODIFIED (+4 tests)"
    - "frontend/src/components/PaletteSwatches.tsx (67 lines)"
    - "frontend/src/components/LogoGallery.tsx (54 lines)"
    - "frontend/src/components/BrandKitCard.tsx (43 lines)"
    - "frontend/src/components/ui/dialog.tsx (ShadCN generated)"
    - "frontend/src/components/ui/form.tsx (ShadCN generated, from new-york URL)"
    - "frontend/src/components/ui/label.tsx (ShadCN generated, from new-york URL)"
    - "frontend/src/pages/brand-kits/list.tsx -- REWRITTEN (86 lines, was 9-line stub)"
    - "frontend/src/pages/brand-kits/detail.tsx -- REWRITTEN (166 lines, was 9-line stub)"
    - "frontend/src/pages/brand-kits/new.tsx -- REWRITTEN (130 lines, was 9-line stub)"
    - "frontend/src/pages/brand-kits/list.test.tsx (58 lines, 2 tests)"
    - "frontend/src/pages/brand-kits/new.test.tsx (69 lines, 2 tests)"
  modified:
    - "frontend/src/api/openapi.snapshot.json -- regenerated from running backend (27,038 bytes; added /brand-kits/{slug}/logos/{filename} path)"
    - "frontend/src/api/schema.gen.ts -- regenerated from new snapshot"
    - "frontend/src/test/test-utils.tsx -- mount <Toaster /> alongside MemoryRouter"
    - "frontend/src/test/setup.ts -- window.matchMedia polyfill for jsdom"
    - "frontend/package.json + pnpm-lock.yaml -- react-hook-form + zod + @hookform/resolvers"

key-decisions:
  - "[Rule 2 - Missing Critical] Copied _logo_is_within from routes/renders.py::_is_within rather than importing. The helper is 18 lines; sharing it would have meant a mid-plan refactor to an api/_paths.py module that doesn't exist yet. The plan explicitly permitted both approaches. If a THIRD file-streaming route lands (unlikely this phase), extraction becomes a separate chore."
  - "[Rule 3 - Blocking] Added noValidate to the scrape form. Browser-native type=\"url\" validation blocks submit before RHF's onSubmit fires, so the zodResolver never runs on invalid URLs and the form message field stays empty. The plan's sample code used type=\"url\" without noValidate; noValidate is the minimum-change fix that preserves the nice HTML5 hint while handing validation off to zod."
  - "[Rule 3 - Blocking] Polyfilled window.matchMedia in src/test/setup.ts. sonner's <Toaster /> reads matchMedia at mount to detect prefers-color-scheme; jsdom does not implement it. Polyfill is a vi.fn() no-op MediaQueryList. Alternative was to skip mounting Toaster in test-utils, but then valid-submit tests could not findByText the success toast."
  - "[Rule 3 - Blocking] Mounted <Toaster /> inside renderWithProviders. Plan-21-04 committed Toaster to main.tsx only; tests rendering a page in isolation had no Toaster, so toast.success from the mutation success handler never surfaced. Matches main.tsx positioning (outside MemoryRouter, inside QueryClientProvider)."
  - "[Rule 3 - Blocking] Fetched ShadCN form from the new-york style URL. The radix-nova registry (our project's configured style) returns an effectively empty form.json (name + type only, no content). Running `shadcn add form` silently completes without creating the file. Fetched via explicit URL `https://ui.shadcn.com/r/styles/new-york/form.json` which includes the real Controller + useFormContext-based component + peer deps (@hookform/resolvers, zod, react-hook-form). The generated form.tsx works unchanged with radix-nova."
  - "[Rule 1 - Bug] PaletteSwatches type cast: the generated BrandPalette includes both named roles AND an extras index map; direct `as Record<string, ColorUsage>` failed TS's overlap check (extras value shape differs). Solved with `as unknown as Record<...>` narrowing and a slightly looser ColorUsage type (`usage_hint?: string | null`). Runtime unchanged."
  - "Used `app.state.settings.brand_kits_dir = tmp_path` in the 4 new backend tests rather than adding a dedicated fixture. The plan mentioned a `brand_kits_dir` fixture from 20-08 but no such fixture exists in tests/api/conftest.py -- existing brand-kits tests use the override-in-test pattern, so the new tests match that style."
  - "Removed `type=\"url\"` requirement? No -- kept `type=\"url\"` on the input (it still gives native URL keyboard hint on mobile + nice icon) and added `noValidate` on the form. This keeps the nice UX affordance while routing validation through zod exclusively."

requirements-completed: [FE-04]

# Metrics
duration: ~35min
completed: 2026-04-23
---

# Phase 21 Plan 05: Brand Kits (Pages + Logo Route) Summary

**Brand Kits page ships end-to-end: `/brand-kits` paginated card grid + `/brand-kits/:slug` palette/typography/logos/voice detail + `/brand-kits/new` RHF+zod scrape form + new backend route `GET /api/v1/brand-kits/{slug}/logos/{filename}` with T-1 HIGH path-traversal mitigation. Backend: 4 new tests (17 total), FE: 4 new tests (9 total), zero new `dangerouslySetInnerHTML`.**

## Performance

- **Duration:** ~35 min (08:00 → 08:20 UTC, including schema regen + shadcn registry debugging)
- **Tasks:** 3 (Task 1 + Task 3 were TDD -- 4 task commits + 2 RED test commits = 6 total commits)
- **Files created:** 8 (3 components, 3 ShadCN primitives, 2 test files)
- **Files modified:** 9 (backend route, backend test file, 3 stub-to-real pages, OpenAPI snapshot, schema.gen.ts, 2 test-harness files, package.json)

## Accomplishments

- **Backend route shipped** -- `GET /api/v1/brand-kits/{slug}/logos/{filename}` returns the logo bytes with correct Content-Type (PNG/JPG/JPEG/SVG) and inline Content-Disposition, or 404 on every failure mode. T-1 HIGH mitigation (path traversal) closed via _logo_is_within + _LOGO_EXT_MIME whitelist. SVG added to the whitelist because brand-kit logos are commonly SVG (renders.py whitelist intentionally excludes SVG because rendered creative output is always rasterized).
- **4 new backend tests** -- PNG happy path, SVG happy path, URL-encoded traversal attempt (`..%2Fbrand.json` returns 404), missing-file 404. 13 pre-existing brand-kits route tests still pass.
- **OpenAPI snapshot regenerated** -- booted the backend on port 8765 (avoiding the project's default 8000 in case of conflicts in CI), curled `/openapi.json`, ran `pnpm gen:api:snapshot`. New path present in both files.
- **3 reusable components** -- PaletteSwatches (5 roles + extras dict), LogoGallery (img grid consuming the new route), BrandKitCard (react-router Link wrapper around Card). None uses `dangerouslySetInnerHTML` (grep verified).
- **3 stub pages replaced** -- list/detail/new; Ctrl+F `stub — plan 21-05 replaces` returns 0 matches after this plan.
- **4 new frontend tests** -- 2 for list (empty state + populated), 2 for new (invalid URL + valid submit). Total Vitest: 9/9 (5 prior + 4 new).
- **Typecheck + build pass** -- `pnpm typecheck` returns 0; `pnpm build` emits 69.66 KB CSS / 573.84 KB JS in ~570 ms.

## Task Commits

1. **Task 1 RED:** `d83794d` -- test: add failing logo-route tests (4 tests, all fail against stub).
2. **Task 1 GREEN:** `596cab0` -- feat: add GET /brand-kits/{slug}/logos/{filename} route.
3. **Task 1 chore:** `ba9965d` -- chore: regenerate OpenAPI snapshot + schema.gen.ts.
4. **Task 2:** `136ea5e` -- feat: PaletteSwatches + LogoGallery + BrandKitCard + ShadCN dialog/form/label.
5. **Task 3 RED:** `33aca66` -- test: failing brand-kit page tests (4 tests, all fail against stubs).
6. **Task 3 GREEN:** `243da07` -- feat: replace brand-kit stubs with real list/detail/new pages (all 4 tests pass).

TDD gate compliance: Task 1 and Task 3 each have `test(...)` (RED) -> `feat(...)` (GREEN) pairs in the git log. Task 2 is non-TDD (no test was required in the plan for components). No REFACTOR commits were needed.

## Files Created/Modified

**Backend (modified):**
- `flyer_generator/api/routes/brand_kits.py` -- appended `_LOGO_EXT_MIME`, `_logo_is_within`, `get_brand_kit_logo` after `get_brand_kit`.
- `tests/api/test_brand_kits_routes.py` -- appended 4 tests under a new `GET /brand-kits/{slug}/logos/{filename}` section.

**Frontend (created):**
- `frontend/src/components/PaletteSwatches.tsx`
- `frontend/src/components/LogoGallery.tsx`
- `frontend/src/components/BrandKitCard.tsx`
- `frontend/src/components/ui/dialog.tsx` (ShadCN)
- `frontend/src/components/ui/form.tsx` (ShadCN, from new-york URL)
- `frontend/src/components/ui/label.tsx` (ShadCN, from new-york URL)
- `frontend/src/pages/brand-kits/list.test.tsx`
- `frontend/src/pages/brand-kits/new.test.tsx`

**Frontend (modified):**
- `frontend/src/api/openapi.snapshot.json` (regenerated)
- `frontend/src/api/schema.gen.ts` (regenerated)
- `frontend/src/pages/brand-kits/list.tsx` (stub -> real)
- `frontend/src/pages/brand-kits/detail.tsx` (stub -> real)
- `frontend/src/pages/brand-kits/new.tsx` (stub -> real)
- `frontend/src/test/test-utils.tsx` (added <Toaster />)
- `frontend/src/test/setup.ts` (matchMedia polyfill)
- `frontend/package.json` (+3 runtime deps)
- `frontend/pnpm-lock.yaml` (regenerated)

## Decisions Made

- **`app.state.settings.brand_kits_dir = tmp_path` for the 4 new backend tests.** The plan mentioned a `brand_kits_dir` fixture "already in conftest.py from Plan 20-08", but no such fixture exists in `tests/api/conftest.py`. Rather than add one, I matched the existing pattern already used by `test_get_list_empty` / `test_get_list_returns_db_rows` / `test_get_detail_falls_back_to_filesystem` (attribute-set on the app's settings bundle). This keeps the test file internally consistent.
- **Copied (not imported) `_is_within`.** The plan explicitly permitted both approaches. Importing from `routes/renders.py` would pin a module-to-module dependency for an 18-line helper; a future third file-streaming route should extract to `api/_paths.py` when that need actually materializes.
- **SVG in logo whitelist.** `_LOGO_EXT_MIME` is NOT the same as `renders.py::_ALLOWED_EXT_MIME`. Logos are commonly SVG (brand marks); rendered creative output is not (always rasterized PNG/PDF/JPG). A deliberate divergence, documented in the inline comment.
- **ShadCN form from new-york URL.** The radix-nova style registry returns an effectively empty form.json (just `$schema` + `name` + `type`). `shadcn add form` silently no-ops. I fetched the real form from `https://ui.shadcn.com/r/styles/new-york/form.json` which has the full implementation + peer deps. The result works unchanged with radix-nova tokens because the form.tsx uses only ShadCN-agnostic classes (text-destructive, text-sm, etc.).
- **Kept `type="url"` on the Input + added `noValidate` on the form.** The `type="url"` attribute still provides mobile keyboard affordance; `noValidate` disables the browser's blocking validation so RHF's zod resolver is the single validation path. This fix was discovered during Task 3 test debugging -- without it, the "rejects an invalid URL" test fails with `aria-invalid="false"` because the browser's native validation intercepts the submit event before RHF fires.
- **Polyfilled matchMedia in setup.ts.** Shared across the whole Vitest suite. Safer than patching each test because sonner's Toaster can surface in any test that imports a component using `toast.*`. A no-op MediaQueryList returning `matches: false` is correct for a jsdom environment (no OS color-scheme preference to detect).
- **2 tests per page (not 3+).** The plan required exactly 4 frontend tests (2 form + 2 list). No deviation. Error-state branches of detail.tsx are typechecked and structurally correct but not under test — their coverage can be added in a polish plan.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] ShadCN form from radix-nova returns a stub**
- **Found during:** Task 2 (running `shadcn@latest add form`).
- **Issue:** `shadcn add form --yes` succeeded but created no file; the CLI queries the radix-nova registry at `https://ui.shadcn.com/r/styles/radix-nova/form.json` which returns `{ name: "form", type: "registry:ui" }` — no content. The shadcn@4.4.0 CLI silently no-ops on an empty registry item.
- **Fix:** Fetched the form from the new-york style URL: `pnpm dlx shadcn@latest add "https://ui.shadcn.com/r/styles/new-york/form.json" --yes --overwrite`. Created `src/components/ui/{form,label}.tsx` and pulled the required peer deps (@hookform/resolvers@^5.2.2, zod@^4.3.6, react-hook-form@^7.73.1).
- **Files modified:** `frontend/src/components/ui/form.tsx`, `frontend/src/components/ui/label.tsx`, `frontend/package.json`, `frontend/pnpm-lock.yaml`.
- **Verification:** `pnpm typecheck` passes; the form imports from `react-hook-form` + `@hookform/resolvers/zod` compile.
- **Committed in:** `136ea5e` (Task 2 commit).

**2. [Rule 3 - Blocking] jsdom missing window.matchMedia**
- **Found during:** Task 3 GREEN (first run of the new.test.tsx suite).
- **Issue:** Every test rendering a page through renderWithProviders (now with Toaster) crashed with `TypeError: window.matchMedia is not a function`. sonner's Toaster (v2.0.7) reads matchMedia at mount for prefers-color-scheme detection; jsdom does not implement it.
- **Fix:** Polyfilled in `src/test/setup.ts` with `vi.fn()` returning a no-op MediaQueryList (matches: false). Setup files run before any test-file import, so every test has matchMedia available.
- **Files modified:** `frontend/src/test/setup.ts`.
- **Verification:** All 9 Vitest tests pass; no matchMedia-related failures.
- **Committed in:** `243da07` (Task 3 commit).

**3. [Rule 3 - Blocking] renderWithProviders missing Toaster**
- **Found during:** Task 3 GREEN (valid-submit test; couldn't find "Scrape enqueued" in the DOM).
- **Issue:** Plan 21-04 committed `<Toaster />` only to `main.tsx`. Tests render pages through `renderWithProviders` in isolation — no Toaster means `toast.success(...)` calls never surface as DOM nodes, so `await screen.findByText(/scrape enqueued/i)` times out.
- **Fix:** Added `<Toaster />` to the renderWithProviders wrapper, outside MemoryRouter but inside QueryClientProvider (matches main.tsx position).
- **Files modified:** `frontend/src/test/test-utils.tsx`.
- **Verification:** `submits + posts to /brand-kits/fetch on valid input` test passes; finds "Scrape enqueued" from the success toast.
- **Committed in:** `243da07` (Task 3 commit).

**4. [Rule 3 - Blocking] Browser-native type="url" validation intercepts submit**
- **Found during:** Task 3 GREEN (invalid-URL test; aria-invalid="false" in the DOM dump).
- **Issue:** The `<input type="url" />` element has built-in HTML5 validation. In jsdom (and in real browsers), clicking the submit button on an invalid URL blocks the submit event before React-Hook-Form's onSubmit handler runs — so the zodResolver never validates and FormMessage stays empty.
- **Fix:** Added `noValidate` to the `<form>` element. Keeps the `type="url"` mobile-keyboard affordance but disables browser-native blocking. zod's resolver is now the single validation path.
- **Files modified:** `frontend/src/pages/brand-kits/new.tsx`.
- **Verification:** `rejects an invalid URL` test passes; finds "Invalid URL" from the FormMessage component.
- **Committed in:** `243da07` (Task 3 commit).

**5. [Rule 1 - Bug] PaletteSwatches TS type-overlap error**
- **Found during:** Task 2 typecheck.
- **Issue:** `as Record<string, ColorUsage>` on the generated BrandPalette failed: the `extras` index map has a different value shape from the named-role fields, so TS rejects the direct cast. `ColorUsage.usage_hint` is declared as `string | null | undefined` whereas my Record literal said `string | null`.
- **Fix:** Two-step cast `as unknown as Record<...>` plus loosened `usage_hint?: string | null` (question mark allows undefined). Runtime behavior unchanged.
- **Files modified:** `frontend/src/components/PaletteSwatches.tsx`.
- **Verification:** `pnpm typecheck` returns 0.
- **Committed in:** `136ea5e` (Task 2 commit).

---

**Total deviations:** 5 auto-fixed (4 Rule 3 blocking, 1 Rule 1 bug). No Rule 2 missing-critical, no Rule 4 architectural. All acceptance criteria still met.

## Issues Encountered

- **shadcn form registry mismatch** (deviation #1). The radix-nova registry is incomplete; fetching from new-york URL is the escape hatch.
- **jsdom + sonner + RHF interaction** (deviations #2, #3, #4). Three separate symptoms, all discovered during Task 3 GREEN test debug. Each fix is a well-scoped one-liner; all three are documented in inline comments so future status-page tests (21-06..09) don't re-debug.
- **TS type inference on index-signature types** (deviation #5). One-line fix; inline comment explains why.
- **No backend startup command** (minor). The existing `make serve` uses the project's default port 8000; I used port 8765 via direct uvicorn to avoid interference with any long-running dev server. `pnpm gen:api:snapshot` (the primary codegen path) reads from the committed snapshot so this is a one-time dev-time action.

## Output spec answers

Per the plan's `<output>` block:

- **Whether the snapshot regen step needed manual touch-ups:** NO. `openapi-typescript 7.13.0` ran cleanly against the new snapshot and emitted a schema.gen.ts with `BrandKitDetail.brand_kit` correctly typed as `components["schemas"]["BrandKit"]` (not `unknown`). The components.BrandPalette + .BrandLogo types are correctly surfaced; the only TS correction needed was in PaletteSwatches' internal dynamic-access cast (deviation #5).
- **Container shortcuts in tests:** msw handlers use relative URLs (`/api/v1/brand-kits/fetch`, `/api/v1/brand-kits`) rather than absolute. This is consistent with plan-21-04's `msw-server.ts` and works because msw v2's `http.get(path)` matches regardless of host. No absolute URL was required.
- **Backend test count delta:** +4 (13 -> 17 tests in `tests/api/test_brand_kits_routes.py`).
- **Frontend test count delta:** +4 (5 -> 9 tests across the whole Vitest suite; 4 new tests in 2 new files under `src/pages/brand-kits/`).

## Next Phase Readiness

- **Ready for plans 21-06 through 21-09 (status pages):** the new logo-stream route + regenerated schema + ShadCN Form/Input/Dialog primitives + RHF/zod/@hookform/resolvers are all now landed. Form-page plans can copy this plan's `new.tsx` pattern verbatim (replace the zod schema and the POST path) and its test pattern (userEvent + msw handler).
- **Ready for plan 21-10 (jobs list):** this plan's list.tsx pattern (useQuery + limit/offset + queryKeys registry + Previous/Next pager + empty-state + skeleton) is a reusable template for any paginated list.
- **Ready for plan 21-11 (renders gallery):** LogoGallery's "construct URL from a relative path" idiom applies to render artifacts too (though renders use the render-id route rather than a filename, so the URL construction differs).
- **Toaster-in-test-utils:** every future mutation test gets free toast assertions via `await screen.findByText(/toast text/i)`.
- **matchMedia polyfill:** future UI tests using any ShadCN + radix primitives that probe color-scheme (Dialog, Tooltip, etc.) are now pre-immunized.
- **noValidate idiom:** form-page plans (21-06..09) should set noValidate on their `<form>` elements to keep zod as the single validation path (same reasoning applies to type="email", type="number", etc.).

## Known Stubs

None from this plan. The 3 stub pages from plan 21-03 (`list.tsx`, `new.tsx`, `detail.tsx`) are all replaced with real implementations.

## Self-Check

**Backend files exist + tests pass:**
- `flyer_generator/api/routes/brand_kits.py` — FOUND (new _LOGO_EXT_MIME + _logo_is_within + get_brand_kit_logo appended).
- `tests/api/test_brand_kits_routes.py` — FOUND (4 new tests).
- `pytest tests/api/test_brand_kits_routes.py -x -q` → 17 passed, 1 warning, 1.09s.
- `pytest tests/api/test_brand_kits_routes.py -k "logo" -x -q` → 4 passed, 13 deselected, 0.21s.

**Frontend files exist:**
- `frontend/src/api/openapi.snapshot.json` — FOUND (27,038 bytes; contains `logos/{filename}`).
- `frontend/src/api/schema.gen.ts` — FOUND (contains the new path).
- `frontend/src/components/PaletteSwatches.tsx` — FOUND.
- `frontend/src/components/LogoGallery.tsx` — FOUND.
- `frontend/src/components/BrandKitCard.tsx` — FOUND.
- `frontend/src/components/ui/dialog.tsx` — FOUND.
- `frontend/src/components/ui/form.tsx` — FOUND.
- `frontend/src/components/ui/label.tsx` — FOUND.
- `frontend/src/pages/brand-kits/list.tsx` — REWRITTEN (no "stub" substring; imports BrandKitCard, Button, Skeleton, useQuery, Link).
- `frontend/src/pages/brand-kits/detail.tsx` — REWRITTEN (imports PaletteSwatches, LogoGallery, Separator; renders Palette + Typography + Logos + Voice CardTitles).
- `frontend/src/pages/brand-kits/new.tsx` — REWRITTEN (uses zodResolver(BrandKitFetchSchema), .strict(), POSTs to /brand-kits/fetch, navigates to /jobs/:id).
- `frontend/src/pages/brand-kits/list.test.tsx` — FOUND (2 tests).
- `frontend/src/pages/brand-kits/new.test.tsx` — FOUND (2 tests).
- `frontend/src/test/test-utils.tsx` — MODIFIED (Toaster present).
- `frontend/src/test/setup.ts` — MODIFIED (matchMedia polyfill present).

**Commits exist:**
- `d83794d` (Task 1 RED) — FOUND.
- `596cab0` (Task 1 GREEN) — FOUND.
- `ba9965d` (Task 1 chore schema regen) — FOUND.
- `136ea5e` (Task 2 components + ShadCN primitives) — FOUND.
- `33aca66` (Task 3 RED) — FOUND.
- `243da07` (Task 3 GREEN) — FOUND.

**Verify runs:**
- `pnpm typecheck` → exits 0.
- `pnpm test --run` → 9 passed / 4 files / Duration 4.11s.
- `pnpm build` → dist/ (69.66 KB CSS / 573.84 KB JS); exits 0.
- `grep -c "dangerouslySetInnerHTML" frontend/src/**/*.tsx` → 0 (no matches anywhere in the tree).
- `grep -c "stub" frontend/src/pages/brand-kits/list.tsx` → 0.
- `grep -c "<BrandKitCard" frontend/src/pages/brand-kits/list.tsx` → 1.
- `grep -c "PaletteSwatches\|LogoGallery" frontend/src/pages/brand-kits/detail.tsx` → 4.
- `grep -c "zodResolver(BrandKitFetchSchema)" frontend/src/pages/brand-kits/new.tsx` → 1.
- `grep -c ".strict()" frontend/src/pages/brand-kits/new.tsx` → 1 (ignoring comments).
- Logo URL idiom: `grep -c "/api/v1/brand-kits/\${slug}/logos/\${encodeURIComponent" frontend/src/components/LogoGallery.tsx` → 1.

## TDD Gate Compliance

Task 1 and Task 3 were both TDD tasks. Git log shows the required sequence:

- Task 1: `d83794d` (test: RED) → `596cab0` (feat: GREEN). Both present.
- Task 3: `33aca66` (test: RED) → `243da07` (feat: GREEN). Both present.

No REFACTOR commits were needed; GREEN code is already idiomatic.

## Self-Check: PASSED

---
*Phase: 21-react-frontend-dashboard*
*Completed: 2026-04-23*
