---
phase: 24-poster-primitive
plan: 05
subsystem: frontend
tags: [react, react-hook-form, zod, openapi-typescript, msw, vitest, react-testing-library, page-routing, dashboard-nav]

# Dependency graph
requires:
  - phase: 24-poster-primitive-03
    provides: PosterCreateRequest schema visible on /api/v1/posters in OpenAPI
  - phase: 24-poster-primitive-04
    provides: POST /api/v1/posters route + JobKind.POSTER + RenderKind poster_final
  - phase: 21-09 (frontend baseline)
    provides: openapi-fetch client, RHF + zod + ShadCN Select pattern, JobStatusCard, msw test infra
provides:
  - PosterCreateRequestBody type alias on the typed client
  - /posters/new editorial creator route + sidebar nav entry
  - /posters/:id status route (JobStatusCard wrapper, single-artifact)
  - poster KIND filter on Jobs page + statusPathFor("poster", id) -> /posters/{id}
  - poster_final KIND filter on Renders gallery
  - 5 vitest+RTL tests covering field render, header composition, submit button, default size, end-to-end POST body capture
affects:
  - 26  # adversarial sweep — FE surface for posters now exists for E2E coverage

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "In-process OpenAPI snapshot regen: build_app().openapi() -> JSON file -> pnpm gen:api:snapshot. Avoids the stale-uvicorn trap (per 23-05 SUMMARY) — guarantees the snapshot reflects the current source tree, not a long-running dev server."
    - "Locked-set Select pattern: SIZES + TEMPLATES + PRESETS as `as const` tuples, surfaced via z.enum + ShadCN Select. SelectTrigger keyed by data-testid for stable test selectors across CSS-in-JS internals."
    - "Single-artifact status page: thin wrapper around <JobStatusCard /> (no detail-page fetch, no figure grid) — appropriate when the primitive ships a single PNG and JobStatusCard already renders result_ref inline."
    - "Empty-string -> null normalization in mutationFn for every Optional[str] field, matching backend Pydantic Optional[str] = None semantics."

key-files:
  created:
    - frontend/src/pages/posters/new.tsx
    - frontend/src/pages/posters/status.tsx
    - frontend/src/pages/posters/new.test.tsx
  modified:
    - frontend/src/api/openapi.snapshot.json
    - frontend/src/api/schema.gen.ts
    - frontend/src/api/client.ts
    - frontend/src/components/DashboardLayout.tsx
    - frontend/src/routes.tsx
    - frontend/src/pages/jobs/list.tsx
    - frontend/src/pages/renders/gallery.tsx

key-decisions:
  - "Status page is single-artifact: no detail-page GET, no figure grid — JobStatusCard already renders result_ref as a PNG when succeeded. This matches the locked CONTEXT.md decision and 24-04 SUMMARY (no GET /posters/{id} route exists)."
  - "Insertion ordering follows JobKind enum order: nav entry between postcard and social_post; route registration between postcard pair and social pair; KINDS arrays in jobs+renders both insert poster between postcard and social_post."
  - "The existing brochure/postcard pattern uses headline-and-Body Input/Textarea pairs; poster substitutes Body for Subheading + CTA + Image hint to match PosterCreateRequest's slimmer shape (no body field at the schema layer)."
  - "Default size '18x24' chosen (smallest of 3) — matches the most common print-shop intake and gives the lowest-cost first render attempt."

patterns-established:
  - "Locked-set Select with data-testid trigger: a stable convention for any future primitive that ships fixed enums (e.g., invitation sizes, brochure trim sizes). Tests assert the trigger via getByTestId rather than getByLabelText (Radix-aria internals can shift)."
  - "Status page family pattern: thin (JobStatusCard only) for single-artifact primitives, fat (manual figure grid + detail GET) for multi-artifact primitives — locked by the primitive's render count, not by the FE author's preference."

requirements-completed: [PO-04]

# Metrics
duration: ~12min
completed: 2026-04-25
---

# Phase 24 Plan 05: Poster FE Creator + Status Wiring Summary

**Wires the poster primitive into the Phase-21 React dashboard: regenerated OpenAPI snapshot surfacing POST /api/v1/posters, typed PosterCreateRequestBody alias, editorial /posters/new creator with size + template + preset Selects, thin /posters/:id status page wrapping JobStatusCard, and KINDS extensions on the Jobs + Renders filter pages — closes PO-04 with 5 vitest+RTL tests.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-04-25 (post 24-04 merge)
- **Completed:** 2026-04-25
- **Tasks:** 2 / 2 complete
- **Commits:** 2 (Task 1 + Task 2)
- **Files created:** 3 (new.tsx, status.tsx, new.test.tsx)
- **Files modified:** 7 (snapshot, schema.gen, client, layout, routes, jobs/list, renders/gallery)
- **Tests added:** 5 (new poster-page tests)
- **Full FE suite:** 43 passed, 0 failed (38 baseline + 5 new)

## Accomplishments

- **PO-04 closed (FE surface):** Navigating to `/posters/new` shows the editorial creator form with editorial PageHeader (`09 / THE BIG ONE`), 3 size options (18x24 / 24x36 / 27x40), 3 templates (editorial_grand / bold_announcement / cinematic_onesheet), and 6 style presets. Submission POSTs to `/api/v1/posters` with empty-string optionals normalized to null. On success the page navigates to `/posters/{job_id}` which shows the JobStatusCard polling until the rendered PNG lands.
- **OpenAPI snapshot regenerated in-process:** `build_app().openapi()` -> `frontend/src/api/openapi.snapshot.json` -> `pnpm gen:api:snapshot` -> `schema.gen.ts`. Snapshot now contains `/api/v1/posters` (POST + tag) and `PosterCreateRequest` schema; `PosterCreateRequestBody` type alias derived from it.
- **Status page is intentionally thin:** wraps `<JobStatusCard jobId={id} title="Poster" />` with a manual editorial header (back-link + 09 / Job kicker + h1) — no `GET /posters/{id}` fetch, no figure grid (locked CONTEXT.md decision; posters ship a single PNG).
- **Sidebar nav extended to 10 entries:** New poster slot between New postcard and New post, matching JobKind enum ordering.
- **Routes registered:** `/posters/new` (NewPosterPage) and `/posters/:id` (PosterStatusPage) between the postcard pair and the social pair in `routes.tsx`.
- **Jobs + Renders filters extended:** `KINDS` arrays in `jobs/list.tsx` and `renders/gallery.tsx` include `poster` and `poster_final` respectively; `statusPathFor("poster", id)` routes to `/posters/{id}`.
- **5 vitest+RTL tests pass.** Full FE suite: 43 passed, 0 failed (no regressions vs the 38-test post-23-05 baseline).
- **Production build succeeds** (`pnpm build` -> `dist/index-*.js` 646 kB / 192 kB gzip; pre-existing chunk-size warning unchanged).

## Task Commits

1. **Task 1** — `7459e83` (feat): regenerate OpenAPI + add `PosterCreateRequestBody` alias + nav entry + 2 routes + write `new.tsx` and `status.tsx`. Verified by `pnpm typecheck` clean and the 7-line strict grep panel matching all expected substrings.
2. **Task 2** — `535f603` (feat): extend `jobs/list.tsx::KINDS` and `statusPathFor`, extend `renders/gallery.tsx::KINDS`, write `new.test.tsx` with 5 cases. Verified by `pnpm test --run src/pages/posters/` (5/5), full suite (43/43), `pnpm typecheck` clean, `pnpm build` clean.

This plan declared `type: execute` (not TDD), so a single feat commit per task was the appropriate atomic unit.

## Files Created/Modified

### Created

- **`frontend/src/pages/posters/new.tsx`** (~290 lines) — RHF + zod creator form:
  - Editorial PageHeader (`number="09"`, `kicker="The Big One"`, locked CONTEXT.md decision).
  - Form fields: headline (Input, required) + subheading (Input, optional) + cta_text (Input, optional) + image_hint (Textarea, optional) + brand_kit_slug (Input, optional, slug regex) + size Select + template Select + style_preset Select + Submit.
  - Locked-set Selects: SIZES = `["18x24", "24x36", "27x40"]`, TEMPLATES = `["editorial_grand", "bold_announcement", "cinematic_onesheet"]`, PRESETS = the 6-entry flyer preset list.
  - Each Select trigger keyed by data-testid (`size-select`, `template-select`, `preset-select`) for stable test selectors.
  - mutationFn normalizes empty-string optional fields to null before POST; on success invalidates jobs query, toasts `Poster enqueued (...)` and navigates to `/posters/{job_id}`.
  - `.strict()` schema mirrors backend Pydantic `extra="forbid"`.
- **`frontend/src/pages/posters/status.tsx`** (~50 lines) — single-artifact status:
  - Manual editorial header block (back-link to `/posters/new` + `09 / Job · {id-truncated}` kicker + `h1` "Poster job").
  - Body: `<JobStatusCard jobId={id} title="Poster" />` only — no detail GET, no figure grid (locked decision).
- **`frontend/src/pages/posters/new.test.tsx`** (~95 lines) — 5 tests:
  1. Renders headline + size + template fields (asserts via `getByLabelText` for headline, `getByTestId` for the two Selects).
  2. Renders the editorial header pieces ("09" + /the big one/i + "New poster" h1).
  3. Renders the "Generate poster" submit button.
  4. Defaults size Select to "18x24" (asserts trigger text without opening the dropdown).
  5. End-to-end POST capture via msw — types headline, clicks submit, awaits success toast, asserts captured body has `headline = "Friday Night Show"`, `template = "editorial_grand"`, `size = "18x24"`, `style_preset = "photorealistic"`, and every empty-string optional (`subheading`, `cta_text`, `image_hint`, `brand_kit_slug`) normalized to `null`.

### Modified

- **`frontend/src/api/openapi.snapshot.json`** — regenerated from `build_app().openapi()`. Now contains `/api/v1/posters` POST + `PosterCreateRequest` schema (alongside the rest of the API).
- **`frontend/src/api/schema.gen.ts`** — regenerated by `pnpm gen:api:snapshot`. Adds the `PosterCreateRequest` schema component, the `paths["/api/v1/posters"]["post"]` operation, and the `create_poster_api_v1_posters_post` operation entry.
- **`frontend/src/api/client.ts`** — adds `export type PosterCreateRequestBody` between `PostcardDetail` and `PostCreateRequestBody`. Drives the form's typed `body` cast in `mutationFn`.
- **`frontend/src/components/DashboardLayout.tsx`** — `NAV` array gains `{ to: "/posters/new", label: "New poster" }` between the postcard entry and the social-posts entry. Now 10 entries total.
- **`frontend/src/routes.tsx`** — imports `NewPosterPage` + `PosterStatusPage` and registers `posters/new` + `posters/:id` between the postcard pair and the social-post pair.
- **`frontend/src/pages/jobs/list.tsx`** — `KINDS` adds `"poster"` between `postcard` and `social_post`; `statusPathFor` adds `case "poster": return /posters/${id}`.
- **`frontend/src/pages/renders/gallery.tsx`** — `KINDS` adds `"poster_final"` after `postcard_pdf` and before `social_post_image`; comment block updated to mention Phase 24 PO-04.

## Diffs (key sections)

### `client.ts` — typed alias

```ts
export type PosterCreateRequestBody =
  paths["/api/v1/posters"]["post"]["requestBody"]["content"]["application/json"];
```

### `new.tsx` — locked-set Selects + form schema

```ts
const SIZES = ["18x24", "24x36", "27x40"] as const;
const TEMPLATES = [
  "editorial_grand",
  "bold_announcement",
  "cinematic_onesheet",
] as const;

const PosterFormSchema = z
  .object({
    headline: z.string().min(1, "headline is required").max(120),
    subheading: z.string().max(200).optional(),
    cta_text: z.string().max(120).optional(),
    image_hint: z.string().max(500).optional(),
    brand_kit_slug: z
      .string()
      .regex(SLUG, "lowercase letters, digits, dashes")
      .max(64)
      .optional()
      .or(z.literal("")),
    style_preset: z.string().min(1).max(64),
    template: z.enum(TEMPLATES),
    size: z.enum(SIZES),
  })
  .strict();
```

### `new.tsx` — empty-string -> null normalization in mutationFn

```ts
const body: PosterCreateRequestBody = {
  headline: values.headline,
  subheading: values.subheading?.trim() ? values.subheading : null,
  cta_text: values.cta_text?.trim() ? values.cta_text : null,
  image_hint: values.image_hint?.trim() ? values.image_hint : null,
  brand_kit_slug: values.brand_kit_slug?.trim()
    ? values.brand_kit_slug
    : null,
  style_preset: values.style_preset,
  template: values.template,
  size: values.size,
};
```

### `status.tsx` — thin wrapper

```tsx
export function PosterStatusPage() {
  const { id = "" } = useParams<{ id: string }>();
  return (
    <div className="mx-auto max-w-screen-xl px-10 pt-14 pb-24 md:px-14">
      {/* back-link + 09 / Job kicker + h1 Poster job */}
      <div className="mt-10">
        <JobStatusCard jobId={id} title="Poster" />
      </div>
    </div>
  );
}
```

### `jobs/list.tsx` — KINDS + statusPathFor

```ts
const KINDS = [
  "brand_kit",
  "flyer",
  "brochure",
  "postcard",
  "poster",
  "social_post",
  "social_campaign",
] as const;

function statusPathFor(kind: string, id: string): string {
  switch (kind) {
    // ...existing cases...
    case "poster":
      return `/posters/${id}`;
    // ...rest...
  }
}
```

### `renders/gallery.tsx` — KINDS

```ts
const KINDS = [
  "flyer_event_final",
  "flyer_info_final",
  "brochure_front",
  "brochure_back",
  "brochure_pdf",
  "postcard_front",
  "postcard_back",
  "postcard_pdf",
  "poster_final",
  "social_post_image",
  "brand_kit_logo",
] as const;
```

## Test Counts

| Suite                                                       | Pass | Failed | Notes |
| ----------------------------------------------------------- | ---: | -----: | ----- |
| New: `frontend/src/pages/posters/new.test.tsx`              |    5 |      0 | 1 field render + 1 header composition + 1 submit button + 1 default size + 1 e2e POST capture |
| Existing: full vitest suite                                 |   43 |      0 | 38 post-23-05 baseline + 5 new = 43 (no regressions) |

## Threat Mitigations Implemented

| Threat ID | Mitigation                                                                               | Verified by                                                                |
| --------- | ---------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| T-24-16 (XSS) | Every form value renders as React JSX text (no `dangerouslySetInnerHTML`); submission via typed openapi-fetch POST body — no string interpolation into HTML. | Code review — no `dangerouslySetInnerHTML` anywhere in `new.tsx` or `status.tsx`. |
| T-24-17 (Tampering) | `accept` disposition: backend Pydantic `Literal["18x24","24x36","27x40"]` is authoritative; the FE `z.enum(SIZES)` is a UX nicety. | 24-03 + 24-04 SUMMARY (backend tests). FE-side: client-side enum present, but treated as defense-in-depth only. |
| T-24-18 (Information disclosure) | `accept` disposition: single-user v1; URL-leaks-job-id is the same disposition as Phase 23-05 T-23-18. | N/A (architectural, single-user). |

## Verification Results

| Check | Result |
|-------|--------|
| `grep -c "/api/v1/posters" frontend/src/api/schema.gen.ts` | 2 (path key + tag/operation) |
| `grep -n "export type PosterCreateRequestBody" frontend/src/api/client.ts` | 1 line |
| `grep -n '/posters/new", label: "New poster"' frontend/src/components/DashboardLayout.tsx` | 1 line |
| `grep -n 'path: "posters/new"' frontend/src/routes.tsx` | 1 line |
| `grep -n 'path: "posters/:id"' frontend/src/routes.tsx` | 1 line |
| `grep -n 'export function NewPosterPage' frontend/src/pages/posters/new.tsx` | 1 line |
| `grep -n 'export function PosterStatusPage' frontend/src/pages/posters/status.tsx` | 1 line |
| `grep -n 'kicker="The Big One"' frontend/src/pages/posters/new.tsx` | 1 line |
| `grep -n 'number="09"' frontend/src/pages/posters/new.tsx` | 1 line |
| `grep -c '"poster"' frontend/src/pages/jobs/list.tsx` | 2 (KINDS array entry + case label) |
| `grep -c 'case "poster":' frontend/src/pages/jobs/list.tsx` | 1 line |
| `grep -c '"poster_final"' frontend/src/pages/renders/gallery.tsx` | 1 line |
| `pnpm test --run` (full FE suite) | 43 passed, 0 failed |
| `pnpm typecheck` | no errors |
| `pnpm build` | success (560 ms) |

## Decisions Made

None beyond what was locked in `24-05-PLAN.md` and `24-CONTEXT.md`. Plan executed as written:

- Editorial PageHeader composition (`09 / The Big One`) verbatim.
- Status page thin (no detail GET, no figure grid) per locked decision.
- Locked-set Select pattern with data-testid triggers (mirrors flyer creator's existing convention).
- KINDS array insertion ordering matches JobKind enum ordering.
- Empty-string -> null normalization in mutationFn for every Optional[str] field.

## Deviations from Plan

None — plan executed exactly as written.

The plan's `<patterns>` block specified test imports from `frontend/src/test/render.tsx` and `frontend/src/test/msw-server.ts`; the actual project ships `frontend/src/test/test-utils.tsx` (renderWithProviders) and `frontend/src/test/msw-server.ts`. The postcard test file (the verbatim source pattern per `<context>`) imports `from "@/test/test-utils"`, so the poster test mirrors that path exactly. This is a documentation-correctness adjustment to match reality, not a deviation in behavior — the helper API used (`renderWithProviders` + `server`) is identical.

## Issues Encountered

One small environmental note: `.venv/bin/python` lives at the main repo root (`/home/hoyack/work/autocreative/.venv`), not inside the worktree. The OpenAPI snapshot regen step used the absolute path to that interpreter from inside the worktree's working directory — the in-process `build_app()` call still executes against the worktree's `flyer_generator/` source tree (same Python module on `sys.path`), so the snapshot reflects worktree code, not main-branch code. Verified by `grep "/api/v1/posters" frontend/src/api/schema.gen.ts` returning 2 hits post-regen.

Frontend `node_modules` was not present in the worktree on agent start; `pnpm install --prefer-offline` filled the cache from the global pnpm store in ~2s.

## TDD Gate Compliance

This plan declared `type: execute` (not `tdd`), so the RED/GREEN gate sequence does not apply. The 5 new tests in `new.test.tsx` were authored in Task 2 alongside the KINDS extensions, which is the correct atomic unit for an `execute` plan: tests + small wiring changes ship together as a single `feat(...)` commit.

## Known Stubs

None. Every form field is wired to a Pydantic schema field (verified by the typed `PosterCreateRequestBody`), every Select has its locked enum surfaced, and the status page reads `result_ref` directly via JobStatusCard without a stubbed-out detail fetch.

## User Setup Required

None — no external service configuration required for this plan. Existing dev-stack Vite proxy (`/api/* -> :8000`) carries over.

## Next Phase Readiness

This plan closes the FE creator + status surface for posters. End-to-end smoke test (manual or Playwright):

1. Run dev stack (`pnpm dev` + worker + API).
2. Navigate to `http://localhost:5173/posters/new`.
3. Type a headline + pick a size (18x24 default).
4. Click "Generate poster →".
5. Page navigates to `/posters/{job_id}`; JobStatusCard polls; once succeeded shows the PNG inline (single artifact).

Phase 24 wave 3 closes here. Plan 24-06 (Playwright permutation harness, mirroring 23-06) is the optional follow-up that turns this manual smoke test into automated coverage of all 9 (3 templates × 3 sizes) permutations.

## Self-Check: PASSED

**Files:**

- FOUND: frontend/src/pages/posters/new.tsx
- FOUND: frontend/src/pages/posters/status.tsx
- FOUND: frontend/src/pages/posters/new.test.tsx
- FOUND: frontend/src/api/openapi.snapshot.json (modified)
- FOUND: frontend/src/api/schema.gen.ts (modified)
- FOUND: frontend/src/api/client.ts (modified)
- FOUND: frontend/src/components/DashboardLayout.tsx (modified)
- FOUND: frontend/src/routes.tsx (modified)
- FOUND: frontend/src/pages/jobs/list.tsx (modified)
- FOUND: frontend/src/pages/renders/gallery.tsx (modified)

**Commits:**

- FOUND: 7459e83 (Task 1 — OpenAPI regen + alias + nav/routes + page scaffolds)
- FOUND: 535f603 (Task 2 — jobs+renders KINDS extensions + 5 vitest+RTL tests)

**Test count:** 5 new tests pass (5/5 in `frontend/src/pages/posters/new.test.tsx`). Full FE suite: 43 passed, 0 failed (38 baseline + 5 new = 43).

---
*Phase: 24-poster-primitive*
*Plan: 05*
*Completed: 2026-04-25*
