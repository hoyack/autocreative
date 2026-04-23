# Phase 21: React Frontend Dashboard - Research

**Researched:** 2026-04-22
**Domain:** React 19 SPA + Vite 8 + Tailwind v4 + ShadCN/ui + TanStack Query v5 + React Router v7 + typed API client (openapi-typescript + openapi-fetch) + react-hook-form + zod + Vitest, consuming the Phase 20 FastAPI backend
**Confidence:** HIGH

## Summary

Phase 21 adds an optional `frontend/` SPA to the project that consumes the Phase 20 HTTP API. Every architectural decision (framework, router, data layer, forms, tests, package manager) was already locked by the inline 8-question survey captured in `21-CONTEXT.md`. This research document is therefore prescriptive: it pins the 2026-current package versions, supplies the concrete code patterns the planner will turn into task actions, and surfaces the small number of gotchas that bite executors of this exact stack.

The trickiest pieces (in priority order):

1. The TanStack Query v5 `refetchInterval` callback signature changed in v5 - it now receives the `Query` object, not `data`. Documenting the correct pattern up front prevents an entire class of "polling never stops" bugs.
2. ShadCN/ui supports Tailwind v4 - but only via `npx shadcn@latest init`, not the older `shadcn-ui` package name. Using the wrong CLI silently produces a v3 setup.
3. The Phase 20 API has exact, locked request/response shapes that the frontend MUST mirror. Pulling them from the running backend via `openapi-typescript` is the source of truth - hand-typing them risks drift.
4. Vite v8 + Vite dev-server proxy is the right way to forward `/api/v1/*` to `http://localhost:8000` without CORS plumbing in dev. (Phase 20 already permits `http://localhost:5173` in CORS, so the proxy is convenience, not necessity.)

**Primary recommendation:** Scaffold `frontend/` with Vite 8 + React 19 + TypeScript 6 + Tailwind v4 + `pnpm`. Run `npx shadcn@latest init` to bring in ShadCN/ui. Generate `src/api/schema.gen.ts` from `http://localhost:8000/openapi.json` with `openapi-typescript@^7`. Use `openapi-fetch@^0.17` as the runtime client. Wrap the app in `QueryClientProvider` at the root. Use `createBrowserRouter` (data-router mode) with a single `<DashboardLayout>` route that contains an `<Outlet>` and the sidebar. Build a single `useJob(jobId)` hook that owns the polling rule. Use `react-hook-form` + `zod` (via `@hookform/resolvers/zod`) for every form, colocated per page. Write tests with Vitest + Testing Library + `msw@^2` for HTTP mocking.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| URL routing + history | Browser / Client (React Router v7) | - | SPA -- no SSR; routing is pure client concern |
| Server state cache | Browser / Client (TanStack Query) | API / Backend | Cache lives in QueryClient; backend owns truth |
| Form state + validation | Browser / Client (RHF + zod) | API / Backend | Client validation is UX; backend re-validates via Pydantic |
| Async job polling | Browser / Client (TanStack Query refetchInterval) | API / Backend | Polling is client-driven; server returns current state |
| Asset display (PNG/PDF) | Browser / Client (`<img>` / download `<a>`) | API / Backend (FileResponse) | Client embeds; server streams |
| API contract types | Browser / Client (codegen from OpenAPI) | API / Backend (OpenAPI schema source) | Types generated client-side, schema authored server-side |
| Mutation submission | Browser / Client (TanStack Query useMutation) | API / Backend (POST handlers) | Client orchestrates submit + cache invalidate; server enqueues |
| Auth | None (single-user, private network - inherited from Phase 20) | - | No auth in scope; documented in README |

## User Constraints (from CONTEXT.md)

### Locked Decisions

These are LOCKED by the 8-question architectural survey already captured in `21-CONTEXT.md`. Do NOT re-examine in plans:

- **Framework:** React 19 + TypeScript 5.x (strict mode). Note: `npm view typescript version` returns `6.0.3` as of 2026-04 -- the planner may target either `^5` (CONTEXT.md text) or `^6` (latest stable). Recommend `^5.7` for now since CONTEXT explicitly says "5.x" and TS 6 is too fresh to bet a new project on; revisit at next major.
- **Build tool:** Vite 7+ -- but `npm view vite version` returns `8.0.9` as of 2026-04-20. Vite 8 is the current stable. Plans should target `vite@^8` (still satisfies "7+").
- **Component lib:** ShadCN/ui (copy-paste, no npm dep on a UI lib). Use the `shadcn` CLI (NOT the old `shadcn-ui` package name).
- **CSS:** Tailwind CSS v4 with the `@tailwindcss/vite` Vite plugin and CSS-first config (no `tailwind.config.js`; use `@theme` blocks in CSS).
- **Data layer:** TanStack Query v5. Polling rule: `refetchInterval` returns `1000` while `status in {queued, running}`, returns `false` when terminal. `refetchIntervalInBackground: false`.
- **Routing:** React Router v7 in data-router mode (`createBrowserRouter` + `RouterProvider`).
- **API client:** `openapi-typescript` for codegen, `openapi-fetch` for runtime. Configured `client` with `baseUrl: import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1"`.
- **Forms:** `react-hook-form` + `zod` + `@hookform/resolvers/zod`. ShadCN `Form` component for layout.
- **Layout:** `frontend/` sibling of `flyer_generator/`. Standard Vite layout (`src/api/`, `src/components/ui/`, `src/components/`, `src/pages/`, `src/routes.tsx`, `src/lib/`, `tests/`, `public/`). `frontend/.env.local` gitignored. `frontend/node_modules/` and `frontend/dist/` added to root `.gitignore`.
- **Package manager:** pnpm >= 9 (latest is 10.33.1 as of 2026-04-21, fine to use pnpm 10). `frontend/package.json` declares `"packageManager": "pnpm@10.x"`.
- **Testing:** Vitest + @testing-library/react + @testing-library/jest-dom + jsdom. NO Playwright. Target: >= 30 frontend tests. No coverage gate.
- **Auth:** NONE (inherited from Phase 20 single-user / private-network trust).
- **Job polling UX:** All status pages use a single `<JobStatusCard jobId={...}/>` component. PNG via `<img>`, PDF via download link.

### Claude's Discretion

These are the planner's call:

- Exact ShadCN component set (initial recommendation: button, input, textarea, select, form, card, sheet, sidebar, navigation-menu, badge, skeleton, sonner (toast), table, dialog, separator, tabs).
- Whether to abstract the polling rule into `useJob(jobId)` hook -- recommend YES (5 status pages will share it).
- Whether to ship a global `<Toaster />` for mutation errors -- recommend YES (sonner via ShadCN).
- Whether to extend Tailwind theme to mirror brand-kit palette dynamically -- recommend NO for v1 (palette displayed per-card, not as global theme).
- Whether to use ShadCN `Sidebar` vs hand-rolled flex layout -- recommend ShadCN `Sidebar` (free responsive collapse, persistent state).
- Whether `/` is a redirect or a "Recent jobs" widget -- recommend redirect to `/brand-kits` (most likely first action).
- ESLint/Prettier scope -- recommend Vite scaffold defaults + `eslint-plugin-react-hooks` + Prettier with `prettier-plugin-tailwindcss` (auto-sort class names).

### Deferred Ideas (OUT OF SCOPE)

Do NOT plan tasks for any of these:

- Authentication (magic link / OAuth / JWT / sessions)
- Multi-tenancy / Organization picker
- Playwright e2e tests
- Server-side rendering
- Mobile-responsive design beyond Tailwind defaults
- Dark mode toggle
- i18n / translations
- Accessibility audit beyond ShadCN/Radix defaults
- Inline PDF preview (PDFs are download-only)
- Theme builder / global brand-kit palette injection
- WebSocket / SSE job streaming (polling only for v1)
- Optimistic mutation rollback
- CDN deployment / mounting `dist/` on FastAPI
- Shared zod schemas published as a package
- Image upload to brand-kit (URL-scrape only, mirroring Phase 20)
- Frontend CI

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FE-01 | React + Vite + TypeScript + ShadCN + Tailwind project under `frontend/`; `pnpm dev` boots; `pnpm build` emits production bundle | Standard Stack + Vite 8 scaffold recipe + ShadCN init |
| FE-02 | Typed API client generated from Phase 20's OpenAPI schema living at `frontend/src/api/`; dev proxy to `http://localhost:8000/api/v1` | API Client Codegen section + Vite proxy snippet |
| FE-03 | Dashboard shell with sidebar nav (Brand Kits / Flyers / Brochures / Social / Campaigns / Jobs / Renders) using ShadCN `Sheet` + `NavigationMenu` | React Router v7 nested-layouts section + ShadCN Sidebar pattern |
| FE-04 | Brand Kits page -- list + detail (palette swatches + typography + logo gallery) + "Add" modal that POSTs to `/brand-kits/fetch` and tails the job | API surface tables + useJob hook + RHF+zod form pattern |
| FE-05 | Flyer creator -- typed form matching `EventInput`, preset/brand-kit pickers, submit -> job polling -> PNG preview + download | EventInput shape table + RHF+zod form recipe + status-page pattern |
| FE-06 | Brochure creator -- content JSON editor (schema-driven form), template picker, preset picker, brand-kit picker, submit -> job polling -> front/back PNG + PDF preview | BrochureContent shape table + useFieldArray for nested sections + status-page pattern |
| FE-07 | Social post creator -- platform/intent/topic/CTA/image_hint inputs + brand-kit + style preset, submit -> job polling -> copy + image + validation report + audit report | PostCreateRequest shape + Post payload shape + status-page pattern |
| FE-08 | Campaign creator -- topic/platforms multi-select/intent/brand-kit/style preset, submit -> job polling -> per-platform result grid (shared source hero) | CampaignCreateRequest shape + JobDetail.result_ref campaign-list-of-{platform,url} pattern |
| FE-09 | Jobs page -- global list of every job with status + kind filter, click-through to originating creative, row-level status polling via `/jobs/{id}` | NOTE: Phase 20 does NOT expose `GET /jobs` (list); see Open Questions Q1 |
| FE-10 | Renders gallery -- grid of all renders, download button, inline preview (PNG inline, PDF via object tag), filter by kind + date | NOTE: Phase 20 does NOT expose `GET /renders` (list); see Open Questions Q2 |

## Project Constraints (from CLAUDE.md)

CLAUDE.md currently lists `**No Node.js deps:** No sharp, no Puppeteer -- pure Python stack` as a project constraint. Phase 21 evolves that constraint:

> Node.js + pnpm are required for the optional `frontend/` dashboard. The Python API + CLI remain the source of truth and are usable without the dashboard. The frontend is a separate, optional surface that depends on the backend running locally.

The first plan should append a CLAUDE.md amendment block documenting this evolution, so future research agents do not interpret CLAUDE.md as forbidding the new `frontend/` directory.

Other CLAUDE.md directives that still apply:

- **Pydantic v2 for all data contracts** -- the frontend mirrors these via zod schemas hand-written from generated TS types. The TS types ARE the v2 source of truth.
- **GSD workflow enforcement** -- all `frontend/` work goes through GSD plans/tasks like the rest of the codebase.
- **No emojis in files unless requested.**
- **Use absolute paths in tool calls.**

## Standard Stack

All versions verified against npm registry on 2026-04-22 via `npm view <pkg> version` [VERIFIED: npm registry].

### Core Runtime

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react | ^19.2.5 | UI library | Locked. R19 brings Actions, native form handling, useOptimistic, ref-as-prop. |
| react-dom | ^19.2.5 | DOM renderer | Pair with react. |
| typescript | ^5.7 (or ^6.0 once stable in your editor) | Type system | CONTEXT.md says "5.x". TS 6.0.3 published but very fresh; recommend `^5.7` for the lockfile. |
| vite | ^8.0 | Build + dev server | Vite 8 is current stable as of 2026-03-12; 8.0.9 published 2026-04-20. Replaces "Vite 7+" (still satisfies). |
| @vitejs/plugin-react | ^6.0 | React fast refresh + JSX | Pair with vite 8. |
| @types/react | ^19.2 | TS types for react | Required. |
| @types/react-dom | ^19.2 | TS types for react-dom | Required. |

### Styling

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| tailwindcss | ^4.2 | Utility CSS | Locked. v4 is CSS-first; no `tailwind.config.js`. 4.2.4 published 2026-04-21. |
| @tailwindcss/vite | ^4.2 | Vite plugin for Tailwind v4 | Mandatory for Tailwind v4 + Vite (replaces the old PostCSS dance). |

### Components

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| shadcn (CLI) | ^4.4 | Component generator (copy-paste) | Use `npx shadcn@latest init`. NOT a runtime dep -- it scaffolds files into `src/components/ui/`. |

ShadCN itself pulls in (as runtime peers when components are installed):
- `class-variance-authority`, `clsx`, `tailwind-merge` (utility primitives)
- `@radix-ui/react-*` packages (accessible primitives, one per component)
- `lucide-react` (icons; ShadCN's default icon set)

### Data Layer

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| @tanstack/react-query | ^5.99 | Server state cache + polling | Locked. v5 is current; 5.99.2 published 2026-04-19. |
| react-router | ^7.14 | Routing in data-router mode | Locked. v7 unifies the previous `react-router-dom` package -- in v7 the `react-router` package is sufficient. (`react-router-dom` still exists as a re-export shim.) |

### Forms

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react-hook-form | ^7.73 | Form state | Locked. |
| zod | ^4.3 | Schema validation | NOTE: zod v4.3 is current; v3 is also still maintained. ShadCN docs and `@hookform/resolvers/zod` both work with v4. |
| @hookform/resolvers | ^5.2 | RHF -> zod adapter | Locked pattern. Imports specifically `@hookform/resolvers/zod`. |

### API Client

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| openapi-typescript | ^7.13 | OpenAPI -> TS types codegen | Locked. Run as a dev-time script, not a runtime dep. |
| openapi-fetch | ^0.17 | Typed fetch wrapper | Locked. ~5KB, no React magic, plays well with TanStack Query. |

### Utilities

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| ulid | ^3.0 | Decode ULID timestamps | Decode `JobRecord.id` (26-char ULID) to display "created X ago". |
| sonner | ^2.0 | Toast notifications | ShadCN's recommended toast since v2. Add via `npx shadcn@latest add sonner`. |
| lucide-react | latest | Icon set | ShadCN default. |

**Skip these (NOT recommended for v1):**

- `date-fns` -- 13KB just to display "X minutes ago" elapsed time. Hand-roll a 5-line `formatElapsed(ms): string` helper in `src/lib/elapsed.ts`. Reach for date-fns only if a second date-formatting need surfaces.
- `axios` -- `openapi-fetch` already wraps `fetch`. Don't add a second HTTP layer.
- `swr` -- TanStack Query is the locked choice; don't introduce a parallel cache.

### Dev / Testing

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| vitest | ^4.1 | Test runner | Native to Vite, fastest setup. 4.1.5 published 2026-04. |
| @testing-library/react | ^16.3 | Component testing | Standard. |
| @testing-library/jest-dom | ^6.9 | Custom matchers (toBeInTheDocument, etc.) | Standard. |
| @testing-library/user-event | ^14.6 | Realistic user interaction | Required for form tests. |
| jsdom | ^29.0 | DOM impl for tests | Vitest's recommended DOM. |
| msw | ^2.13 | HTTP mocking (Mock Service Worker) | RECOMMENDED over manual fetch mocks. v2 has a Node-side request handler API that works inside Vitest without browser plumbing. |

### Linting

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| eslint | ^10.2 | Linter | ESLint 10 is current (10.2.1 as of 2026-04). |
| @eslint/js | ^10.0 | ESLint flat-config core rules | Required for ESLint 9+ flat config. |
| eslint-plugin-react-hooks | ^7.1 | React hooks rules | Required for any React project. |
| eslint-plugin-react-refresh | ^0.5 | Vite HMR safety check | Vite scaffold default. |
| typescript-eslint | ^9 (or whatever's current) | TS-aware lint rules | Standard. |
| prettier | ^3.8 | Formatter | Standard. |
| prettier-plugin-tailwindcss | latest | Auto-sort Tailwind classes | Recommended QoL. |

**Skip:**

- `eslint-plugin-tailwindcss` -- v3.18.3 is the latest, but Tailwind v4 support is a known gap. The Prettier plugin handles class sorting; the ESLint plugin's "valid class name" check is the v3-era feature you'd want, and it isn't reliable on v4 yet [VERIFIED: project listed in CONTEXT.md `Claude's Discretion`; `eslint-plugin-tailwindcss@3.18.3` last published, no v4-compatible release as of 2026-04].

### Installation

```bash
# Inside frontend/ after `pnpm init`
pnpm add react@^19 react-dom@^19
pnpm add -D typescript@^5.7 @types/react@^19 @types/react-dom@^19
pnpm add -D vite@^8 @vitejs/plugin-react@^6
pnpm add -D tailwindcss@^4 @tailwindcss/vite@^4
pnpm add @tanstack/react-query@^5 react-router@^7
pnpm add react-hook-form@^7 zod@^4 @hookform/resolvers@^5
pnpm add openapi-fetch@^0.17
pnpm add -D openapi-typescript@^7
pnpm add ulid@^3 sonner@^2 lucide-react@latest
pnpm add -D vitest@^4 @testing-library/react@^16 @testing-library/jest-dom@^6 @testing-library/user-event@^14 jsdom@^29 msw@^2
pnpm add -D eslint@^10 @eslint/js@^10 eslint-plugin-react-hooks@^7 eslint-plugin-react-refresh@^0.5 typescript-eslint
pnpm add -D prettier@^3 prettier-plugin-tailwindcss
```

ShadCN is added separately via its CLI, which writes files into `src/components/ui/`:

```bash
npx shadcn@latest init
# Then for each component:
npx shadcn@latest add button input textarea select form card sheet sidebar navigation-menu badge skeleton sonner table dialog separator tabs
```

The CLI prompts you for: style (default `new-york`), base color (recommend `slate`), CSS file path (`src/index.css`), and the `@/` import alias (`@/components`, `@/lib/utils`).

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| TanStack Query | SWR, RTK Query | Locked. TanStack Query has the most flexible polling + invalidation API and the best TS story. |
| openapi-fetch | axios + manual types | Hand-typing the API is fragile and the team has already locked codegen. |
| openapi-fetch | openapi-typescript-fetch | Less maintained; openapi-fetch is the official sibling of openapi-typescript. |
| zod | yup, valibot | RHF resolver works for all three; zod is the most ubiquitous and integrates with ShadCN docs. |
| msw | jest-fetch-mock / manual stubs | msw mocks at the network layer (more realistic), works with openapi-fetch as-is, scales to 50+ tests. |
| sonner | react-hot-toast | sonner is what ShadCN ships with as of 2026; one less dep. |
| Playwright | Cypress | Out of scope for Phase 21. |

## API Surface (Source of Truth)

The frontend consumes Phase 20's API. **All routes are mounted under the `/api/v1` prefix.** Errors return `{detail, error_type, trace_id}`.

### Endpoint Catalog

| Method | Path | Request body | Response (success) | Status | Notes |
|--------|------|--------------|--------------------|--------|-------|
| GET | `/healthz` | - | `{status: "ok"}` | 200 | Liveness; no DB touch |
| POST | `/api/v1/brand-kits/fetch` | `BrandKitFetchRequest` | `JobCreated` | 202 | Enqueues scrape; SSRF rejection inherited from Phase 18 scraper |
| GET | `/api/v1/brand-kits` | (query: `limit`, `offset`) | `PaginatedBrandKits` | 200 | Fuses DB rows with `.brand-kits/*/` filesystem |
| GET | `/api/v1/brand-kits/{slug}` | - | `BrandKitDetail` | 200 / 404 | 404 via `BrandKitNotFoundError` |
| POST | `/api/v1/flyers` | `FlyerCreateRequest` | `JobCreated` | 202 | Wraps `FlyerGenerator.generate` |
| POST | `/api/v1/brochures` | `BrochureCreateRequest` | `JobCreated` | 202 | Wraps `render_schema_brochure` + `generate_template_images` |
| POST | `/api/v1/social/posts` | `PostCreateRequest` | `JobCreated` | 202 | Wraps `generate_post` |
| POST | `/api/v1/social/campaigns` | `CampaignCreateRequest` | `JobCreated` | 202 | Wraps `generate_campaign` |
| GET | `/api/v1/jobs/{job_id}` | - | `JobDetail` | 200 / 404 | Polling target. ULID id (26 chars). |
| GET | `/api/v1/renders/{render_id}/image` | - | (binary stream) | 200 / 404 | `Content-Disposition: inline`. PNG/PDF/JPG only. |

**Phase 20 does NOT currently expose:**

- `GET /api/v1/jobs` (list of all jobs). Required by FE-09. See Open Questions Q1.
- `GET /api/v1/renders` (list of all renders). Required by FE-10. See Open Questions Q2.

### Request/Response Shapes

**`BrandKitFetchRequest`** ([VERIFIED: `flyer_generator/api/schemas/brand_kits.py`])
```ts
{
  url: string,           // AnyHttpUrl
  slug: string           // ^[a-z0-9][a-z0-9-]*$, max 64
}
```

**`PaginatedBrandKits`**
```ts
{
  items: Array<{ slug: string; name: string | null; source_url: string | null; scraped_at: string /* ISO datetime */ }>,
  total: number,
  limit: number,
  offset: number
}
```

**`BrandKitDetail`**
```ts
{
  slug: string,
  record_created_at: string,    // ISO datetime
  brand_kit: BrandKit            // Full Phase 18 BrandKit Pydantic model: palette, typography, logos, voice, photo_hints
}
```

The `BrandKit` shape is large; pull it from generated types rather than hand-redefining. Logos contain file paths -- to render them in the UI, plans need a `GET /api/v1/brand-kits/{slug}/logos/{filename}` route OR the logos must be served via the existing `/renders/{id}/image` route. Phase 20 currently does NOT serve logo files. See Open Questions Q3.

**`FlyerCreateRequest`** ([VERIFIED: `flyer_generator/api/schemas/flyers.py`])
```ts
{
  event: EventInput,             // see flyer_generator/models.py
  preset: string,                // 1..64 chars
  brand_kit_slug?: string,       // ^[a-z0-9][a-z0-9-]*$, max 64
  accent?: string,               // ^#[0-9A-Fa-f]{6}$
  max_bg_attempts?: number       // 1..10
}

// EventInput:
{
  title: string,                 // max 120
  date: string,                  // max 120 (free-form)
  time: string,                  // max 120
  location_name: string,         // max 120
  location_address: string,      // max 120
  fees: string,                  // max 120
  org: string,                   // max 120
  url: string | null,
  style_concept: string,         // max 120
  style_preset: string,          // max 120 (NOTE: also passed at top level as `preset`)
  color_accent: string           // ^#[0-9A-Fa-f]{6}$, default "#F59E0B"
}
```

NOTE: `EventInput.style_preset` and `FlyerCreateRequest.preset` are duplicated by design. The frontend form should accept ONE preset selection and copy it into both fields when submitting.

**`BrochureCreateRequest`** ([VERIFIED: `flyer_generator/api/schemas/brochures.py`])
```ts
{
  content: BrochureContent,      // see flyer_generator/brochure/schema_renderer/content_model.py
  template: string,              // 1..64 chars (e.g. "editorial_classic")
  brand_kit_slug?: string,
  generate_images: boolean,      // default true
  workflow: string,              // default "turbo_landscape"
  style_preset: string           // default "photorealistic"
}
```

`BrochureContent` is a large nested model with `sections[]` (each containing `heading`, `body_paragraphs[]`, `bullets[]`, `lead_paragraph`, `quote`), `back_panel`, `contact`, optional `brief`. **This is the single most complex form in the phase.** Use react-hook-form's `useFieldArray` for the sections. Plans should consider a "JSON paste" fallback (textarea that the user can paste a `BrochureContent` JSON into) for v1 instead of building a fully-decomposed nested form on day one. CONTEXT.md spec language ("schema-driven form") is satisfied by either approach.

**`PostCreateRequest`** ([VERIFIED: `flyer_generator/api/schemas/social.py`])
```ts
{
  brand_kit_slug: string,                                       // required, 1..64
  platform: "linkedin" | "twitter" | "instagram" | "facebook",
  intent: "announcement" | "value-prop" | "testimonial",
  topic: string,                                                // 1..400
  cta?: string,                                                 // max 200
  image_hint?: string,                                          // max 400
  style_preset?: string                                         // max 64
}
```

**`CampaignCreateRequest`** ([VERIFIED: `flyer_generator/api/schemas/social.py`])
```ts
{
  brand_kit_slug: string,
  platforms: Array<"linkedin" | "twitter" | "instagram" | "facebook">,  // 1..10 (multi-select)
  intent: "announcement" | "value-prop" | "testimonial",
  topic: string,
  cta?: string,
  style_preset?: string
}
```

**`JobCreated`** (response body for every `POST` enqueue route, status 202)
```ts
{ job_id: string }   // 26-char ULID
```

**`JobDetail`** (response body for `GET /api/v1/jobs/{id}`)
```ts
{
  id: string,                   // ULID, 26 chars
  kind: "brand_kit" | "flyer" | "brochure" | "social_post" | "social_campaign",
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled",
  started_at: string | null,    // ISO datetime
  completed_at: string | null,  // ISO datetime
  error_detail: object | null,  // arbitrary diagnostic dict
  result_ref: string | Array<{ platform: string; url: string }> | null,
  created_at: string            // ISO datetime
}
```

For **single-artifact jobs** (flyer / brochure / single post), `result_ref` is a string like `"/api/v1/renders/01J9ABCDEFGHJKMNPQRSTVWXYZ/image"`. The frontend embeds this directly in `<img src={...}>`.

For **campaigns**, `result_ref` is `[{platform: "linkedin", url: "/api/v1/renders/..."}, ...]`. The frontend renders a per-platform grid.

For **queued / running** jobs, `result_ref` is `null`.

For **brochure jobs**, `result_ref` is currently a single string URL. The brochure generates THREE artifacts (front PNG, back PNG, PDF), but `JobRecord.result_ref` is a `String(26)` column holding ONE render id. See Open Questions Q4.

### Error Body Shape ([VERIFIED: `flyer_generator/api/errors.py`])

Every error response (4xx, 5xx) has this shape:

```ts
{
  detail: string | object,    // string for domain errors; object (Pydantic v2 errors list) for 422
  error_type: string,         // class name, e.g. "BrandKitNotFoundError"
  trace_id: string            // correlation id, may be empty string
}
```

Special case: `LLMRateLimitError` returns 503 with a `Retry-After` header. The frontend should respect it on retry attempts.

### Status -> HTTP mapping (for typed catches)

| Server-side error class | HTTP | When |
|------------------------|------|------|
| `BrandKitNotFoundError` | 404 | `GET /brand-kits/{slug}` for missing kit |
| `BrandKitError`, `SocialError`, `FlyerGeneratorError` | 400 | Domain-level validation issues |
| `BrandVoiceViolationError` | 422 | Generated copy contains banned words |
| `RequestValidationError` (Pydantic) | 422 | Body shape wrong; `detail` is a list |
| `LLMRateLimitError` | 503 + `Retry-After` | LLM 429s upstream |
| `LLMAPIError` (and `VisionAPIError` alias) | 502 | Upstream LLM down |
| `ComfyError` | 502 | Upstream ComfyCloud failure |
| Unmapped | 500 | Bug; trace_id is the diagnostic handle |

### CORS

Phase 20 reads `FLYER_CORS_ORIGINS` and defaults to `http://localhost:5173`. Vite's default dev port is `5173`. **No CORS config change is needed to run the dashboard against a default backend.** If a developer runs Vite on a different port, they must set `FLYER_CORS_ORIGINS` accordingly.

## Architecture Patterns

### System Architecture Diagram

```
                                  Browser
+--------------------------------------------------------------------+
|                                                                    |
|   React Router v7 (createBrowserRouter)                            |
|   |                                                                |
|   |---- DashboardLayout ----+--- /brand-kits  ---> BrandKitsList   |
|   |    (Sidebar + Outlet)   +--- /brand-kits/new -> ScrapeForm     |
|   |                         +--- /brand-kits/:slug -> KitDetail    |
|   |                         +--- /flyers/new -----> FlyerForm ---+ |
|   |                         +--- /flyers/:id -----> JobStatusCard  |
|   |                         +--- /brochures/new --> BrochureForm   |
|   |                         +--- /brochures/:id --> JobStatusCard  |
|   |                         +--- /social/posts/new -> PostForm     |
|   |                         +--- /social/posts/:id -> JobStatusCard|
|   |                         +--- /social/campaigns/new -> CampForm |
|   |                         +--- /social/campaigns/:id -> Campaign |
|   |                         |                            ResultGrid|
|   |                         +--- /jobs ----------> JobsList        |
|   |                         +--- /renders -------> RenderGallery   |
|   v                                                                |
|   +------------ TanStack Query QueryClientProvider --------------+ |
|   |                                                              | |
|   |  useQuery / useMutation -> openapi-fetch client              | |
|   |  - useJob(id): refetchInterval = 1000 while non-terminal     | |
|   |  - on mutation success -> queryClient.invalidateQueries(...) | |
|   |                                                              | |
|   +--------------------------------------------------------------+ |
|                                                                    |
|   <Toaster /> (sonner) for global mutation errors                  |
|                                                                    |
+--------------------------------------------------------------------+
                       |  fetch (typed via openapi-fetch)
                       |  Vite dev proxy strips /api/v1 -> http://localhost:8000/api/v1
                       v
+--------------------------------------------------------------------+
|                  Phase 20 FastAPI (port 8000)                      |
|   /api/v1/{brand-kits, flyers, brochures, social, jobs, renders}   |
|   /healthz  /docs  /openapi.json                                   |
+--------------------------------------------------------------------+
                       |  enqueue
                       v
+--------------------------------------------------------------------+
|              arq Worker (Redis on port 6379)                       |
|   tasks: fetch_brand_kit, generate_flyer, render_schema_brochure,  |
|          generate_post, generate_campaign                          |
+--------------------------------------------------------------------+
```

### Recommended Project Structure

```
frontend/
  package.json
  pnpm-lock.yaml
  pnpm-workspace.yaml         # NOT needed (single package)
  tsconfig.json
  tsconfig.node.json
  vite.config.ts
  eslint.config.js            # flat config
  .prettierrc.json
  index.html
  .env.example
  .env.local                  # gitignored
  public/
    favicon.svg
  src/
    main.tsx                  # createRoot + RouterProvider + QueryClientProvider + Toaster
    routes.tsx                # createBrowserRouter config
    index.css                 # @import "tailwindcss"; + @theme blocks
    api/
      client.ts               # createClient<paths>({...}) export
      schema.gen.ts           # generated by openapi-typescript (CHECKED IN)
      openapi.snapshot.json   # snapshot of upstream openapi.json (CHECKED IN, regen via script)
    components/
      ui/                     # ShadCN copy-pasted primitives (button.tsx, input.tsx, ...)
      DashboardLayout.tsx     # Sidebar + Outlet
      JobStatusCard.tsx       # owns useJob hook + status badges
      RenderPreview.tsx       # <img> for PNG, <a download> for PDF
      PaletteSwatches.tsx     # for brand-kit detail
      LogoGallery.tsx
      BrandKitCard.tsx
      ValidationReportPanel.tsx
      AuditReportPanel.tsx
    pages/
      brand-kits/
        list.tsx
        new.tsx               # POST /brand-kits/fetch + redirect to status
        detail.tsx            # GET /brand-kits/:slug
      flyers/
        new.tsx               # form + POST /flyers
        status.tsx            # JobStatusCard for /flyers/:id
      brochures/
        new.tsx
        status.tsx
      social/
        posts/
          new.tsx
          status.tsx
        campaigns/
          new.tsx
          status.tsx
      jobs/
        list.tsx              # FE-09 (depends on Open Question Q1)
      renders/
        gallery.tsx           # FE-10 (depends on Open Question Q2)
    hooks/
      useJob.ts               # the polling hook
      useBrandKits.ts         # list + detail wrappers
      useEnqueueFlyer.ts      # useMutation wrapper for POST /flyers
      ...
    lib/
      utils.ts                # cn() helper (ShadCN convention)
      elapsed.ts              # ms -> "Xs / Xm Xs / Xh Xm" formatter
      ulidTime.ts             # decode ULID timestamp -> Date
      queryKeys.ts            # central query-key registry
    test/
      setup.ts                # Vitest setup, msw server, jest-dom
      handlers.ts             # msw request handlers
      test-utils.tsx          # renderWithProviders helper
  tests/                      # OR co-locate as *.test.tsx next to components
```

### Pattern 1: Vite + React 19 + Tailwind v4 Scaffold

`vite.config.ts`:

```ts
// Source: https://ui.shadcn.com/docs/installation/vite + https://tailwindcss.com/docs/installation/using-vite
import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Forward /api/v1/* to the FastAPI backend so we don't need CORS in dev
      // and the same code works in dev + prod (where dist/ is mounted on FastAPI).
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
```

`src/index.css` (Tailwind v4 CSS-first config):

```css
/* Source: https://tailwindcss.com/docs/upgrade-guide#tailwind-v4 */
@import "tailwindcss";

/* CSS-first theme config -- replaces tailwind.config.js */
@theme {
  --color-brand-50:  oklch(98% 0.02 250);
  --color-brand-500: oklch(60% 0.18 250);
  --color-brand-900: oklch(28% 0.10 250);
  --font-sans: "Inter", ui-sans-serif, system-ui, sans-serif;
}

/* ShadCN's :root tokens get appended below by `npx shadcn@latest init` */
```

`tsconfig.json` (strict + path aliases):

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": false,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

`package.json` scripts block:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest",
    "lint": "eslint .",
    "lint:fix": "eslint . --fix",
    "format": "prettier -w .",
    "typecheck": "tsc --noEmit",
    "gen:api": "openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.gen.ts",
    "gen:api:snapshot": "openapi-typescript src/api/openapi.snapshot.json -o src/api/schema.gen.ts"
  }
}
```

The two `gen:api` variants give the executor a choice:
- `gen:api` -- requires the backend running; fetches live `/openapi.json`
- `gen:api:snapshot` -- regen from a checked-in snapshot file (so codegen works offline / in CI)

A workflow that scales: run `gen:api` whenever you change Phase 20 routes, then commit BOTH `schema.gen.ts` AND `openapi.snapshot.json` (regenerate the snapshot via `curl http://localhost:8000/openapi.json -o frontend/src/api/openapi.snapshot.json`).

### Pattern 2: openapi-fetch Typed Client

`src/api/client.ts`:

```ts
// Source: https://openapi-ts.dev/openapi-fetch/
import createClient from "openapi-fetch";
import type { paths } from "./schema.gen";

export const client = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_URL ?? "/api/v1",
});

// Helpful type extractors -- use these in component code instead of
// re-deriving the deep nested type each time.
export type Schemas = paths;

export type FlyerCreateRequestBody =
  paths["/flyers"]["post"]["requestBody"]["content"]["application/json"];

export type JobDetail =
  paths["/jobs/{job_id}"]["get"]["responses"][200]["content"]["application/json"];

export type BrandKitDetail =
  paths["/brand-kits/{slug}"]["get"]["responses"][200]["content"]["application/json"];
```

A typical mutation:

```ts
// Source: https://openapi-ts.dev/openapi-fetch/api
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { client } from "@/api/client";
import { toast } from "sonner";

export function useEnqueueFlyer() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return useMutation({
    mutationFn: async (body: FlyerCreateRequestBody) => {
      const { data, error, response } = await client.POST("/flyers", { body });
      if (error) {
        // openapi-fetch returns the parsed error body when error_type is in the response.
        throw new Error(
          (error as { detail?: string })?.detail ?? `HTTP ${response.status}`,
        );
      }
      return data!;  // { job_id }
    },
    onSuccess: ({ job_id }) => {
      // Invalidate the jobs list so it picks up the new entry on next mount.
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      navigate(`/flyers/${job_id}`);
    },
    onError: (err) => toast.error(err.message),
  });
}
```

### Pattern 3: TanStack Query v5 `useJob` Polling Hook

This is the hook every status page calls. The `refetchInterval` callback signature in v5 receives the `Query` object (not data); accessing data is `query.state.data`.

```ts
// Source: https://tanstack.com/query/v5/docs/framework/react/guides/migrating-to-v5
//   "refetchInterval callback function only gets query passed"
// AND   query.state.data is the un-transformed cached value
import { useQuery } from "@tanstack/react-query";
import { client, type JobDetail } from "@/api/client";

const TERMINAL = new Set(["succeeded", "failed", "cancelled"]);

export function useJob(jobId: string) {
  return useQuery<JobDetail>({
    queryKey: ["job", jobId],
    queryFn: async () => {
      const { data, error } = await client.GET("/jobs/{job_id}", {
        params: { path: { job_id: jobId } },
      });
      if (error || !data) throw new Error("failed to fetch job");
      return data;
    },
    // v5: receives the Query object, NOT data.
    // Return a number (ms) to keep polling; return false to stop.
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status && TERMINAL.has(status)) return false;
      return 1000;
    },
    refetchIntervalInBackground: false,  // pause polling when tab is hidden
    // v5: do NOT use `cacheTime` (renamed to `gcTime`).
    gcTime: 5 * 60 * 1000,
    staleTime: 0,                         // always fetch fresh on remount
  });
}
```

A consuming component:

```tsx
import { useParams } from "react-router";
import { useJob } from "@/hooks/useJob";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { RenderPreview } from "@/components/RenderPreview";

export function FlyerStatusPage() {
  const { id } = useParams<{ id: string }>();
  const { data: job, isPending, error } = useJob(id!);

  if (isPending) return <Skeleton className="h-96 w-full" />;
  if (error) return <div className="text-destructive">Failed to load job: {error.message}</div>;
  if (!job) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Badge variant={job.status === "failed" ? "destructive" : "default"}>
          {job.status}
        </Badge>
        <span className="text-sm text-muted-foreground">{job.kind}</span>
      </div>
      {job.status === "succeeded" && typeof job.result_ref === "string" && (
        <RenderPreview url={job.result_ref} />
      )}
      {job.status === "failed" && job.error_detail && (
        <pre className="rounded bg-muted p-4 text-xs">
          {JSON.stringify(job.error_detail, null, 2)}
        </pre>
      )}
    </div>
  );
}
```

### Pattern 4: react-hook-form + zod + ShadCN Form

Per-form colocation (recommended over a centralized schemas dir for v1):

```tsx
// src/pages/flyers/new.tsx
// Source: https://ui.shadcn.com/docs/components/form
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useEnqueueFlyer } from "@/hooks/useEnqueueFlyer";

const HEX = /^#[0-9A-Fa-f]{6}$/;
const SLUG = /^[a-z0-9][a-z0-9-]*$/;

const FlyerFormSchema = z.object({
  event: z.object({
    title: z.string().min(1).max(120),
    date: z.string().min(1).max(120),
    time: z.string().min(1).max(120),
    location_name: z.string().min(1).max(120),
    location_address: z.string().min(1).max(120),
    fees: z.string().max(120),
    org: z.string().max(120),
    url: z.string().url().nullable().optional(),
    style_concept: z.string().max(120),
    style_preset: z.string().max(120),
    color_accent: z.string().regex(HEX).default("#F59E0B"),
  }),
  preset: z.string().min(1).max(64),
  brand_kit_slug: z.string().regex(SLUG).max(64).optional(),
  accent: z.string().regex(HEX).optional(),
  max_bg_attempts: z.number().int().min(1).max(10).optional(),
});

type FlyerFormValues = z.infer<typeof FlyerFormSchema>;

export function NewFlyerPage() {
  const enqueue = useEnqueueFlyer();
  const form = useForm<FlyerFormValues>({
    resolver: zodResolver(FlyerFormSchema),
    defaultValues: { preset: "photorealistic", event: { color_accent: "#F59E0B" } as any },
  });

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit((values) => enqueue.mutate(values))}
        className="space-y-4 max-w-xl"
      >
        <FormField
          control={form.control}
          name="event.title"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Title</FormLabel>
              <FormControl><Input {...field} /></FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        {/* ... other fields ... */}
        <Button type="submit" disabled={enqueue.isPending}>
          {enqueue.isPending ? "Submitting..." : "Generate flyer"}
        </Button>
      </form>
    </Form>
  );
}
```

For the brochure form's nested `sections[].body_paragraphs[]`, use `useFieldArray`:

```tsx
// In a brochure form -- pattern only
import { useFieldArray } from "react-hook-form";
const { fields, append, remove } = useFieldArray({ control: form.control, name: "content.sections" });
// Inside each section, a NESTED useFieldArray for body_paragraphs[]:
//   const paragraphs = useFieldArray({ control: form.control, name: `content.sections.${i}.body_paragraphs` });
```

### Pattern 5: React Router v7 Data-Router with Nested Layout

```tsx
// src/routes.tsx
// Source: https://reactrouter.com/start/data/routing
import { createBrowserRouter, Navigate } from "react-router";
import { DashboardLayout } from "@/components/DashboardLayout";
import { ErrorPage } from "@/pages/Error";
// page imports omitted for brevity

export const router = createBrowserRouter([
  {
    path: "/",
    element: <DashboardLayout />,
    errorElement: <ErrorPage />,
    children: [
      { index: true, element: <Navigate to="/brand-kits" replace /> },

      { path: "brand-kits", element: <BrandKitsListPage /> },
      { path: "brand-kits/new", element: <ScrapeBrandKitPage /> },
      { path: "brand-kits/:slug", element: <BrandKitDetailPage /> },

      { path: "flyers/new", element: <NewFlyerPage /> },
      { path: "flyers/:id", element: <FlyerStatusPage /> },

      { path: "brochures/new", element: <NewBrochurePage /> },
      { path: "brochures/:id", element: <BrochureStatusPage /> },

      { path: "social/posts/new", element: <NewSocialPostPage /> },
      { path: "social/posts/:id", element: <SocialPostStatusPage /> },
      { path: "social/campaigns/new", element: <NewCampaignPage /> },
      { path: "social/campaigns/:id", element: <CampaignStatusPage /> },

      { path: "jobs", element: <JobsListPage /> },
      { path: "renders", element: <RenderGalleryPage /> },
    ],
  },
]);
```

```tsx
// src/components/DashboardLayout.tsx
import { Link, NavLink, Outlet } from "react-router";
import { Sidebar, SidebarContent, SidebarHeader, SidebarMenu, SidebarMenuItem, SidebarMenuButton, SidebarProvider } from "@/components/ui/sidebar";

const NAV = [
  { to: "/brand-kits", label: "Brand kits" },
  { to: "/flyers/new", label: "New flyer" },
  { to: "/brochures/new", label: "New brochure" },
  { to: "/social/posts/new", label: "New post" },
  { to: "/social/campaigns/new", label: "New campaign" },
  { to: "/jobs", label: "Jobs" },
  { to: "/renders", label: "Renders" },
];

export function DashboardLayout() {
  return (
    <SidebarProvider>
      <Sidebar>
        <SidebarHeader>
          <Link to="/" className="font-semibold">flyer-generator</Link>
        </SidebarHeader>
        <SidebarContent>
          <SidebarMenu>
            {NAV.map((item) => (
              <SidebarMenuItem key={item.to}>
                <NavLink to={item.to}>
                  {({ isActive }) => (
                    <SidebarMenuButton isActive={isActive}>{item.label}</SidebarMenuButton>
                  )}
                </NavLink>
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarContent>
      </Sidebar>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </SidebarProvider>
  );
}
```

```tsx
// src/main.tsx
import "./index.css";
import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/sonner";
import { router } from "./routes";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 0,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toaster richColors position="top-right" />
    </QueryClientProvider>
  </React.StrictMode>,
);
```

**Why NOT use React Router loaders for data fetching:** TanStack Query already owns server state. Using both creates a second cache and duplicates fetch logic. The accepted pattern in 2026 is: routes own URL/params, components own data via TanStack Query. Loaders are useful only when you want SSR-style data-prefetching, which the SPA does not need.

### Pattern 6: Vitest + Testing Library + msw

`vitest.config.ts`:

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
```

`src/test/setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./msw-server";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

`src/test/msw-server.ts`:

```ts
import { setupServer } from "msw/node";
import { http, HttpResponse } from "msw";

const BASE = "http://localhost:8000/api/v1";

export const handlers = [
  http.post(`${BASE}/flyers`, async () =>
    HttpResponse.json({ job_id: "01J9ABCDEFGHJKMNPQRSTVWXYZ" }, { status: 202 }),
  ),
  http.get(`${BASE}/jobs/:id`, ({ params }) =>
    HttpResponse.json({
      id: params.id,
      kind: "flyer",
      status: "succeeded",
      started_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      error_detail: null,
      result_ref: "/api/v1/renders/01J9XXX/image",
      created_at: new Date().toISOString(),
    }),
  ),
];

export const server = setupServer(...handlers);
```

`src/test/test-utils.tsx`:

```tsx
import { render, type RenderOptions } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import type { ReactElement, ReactNode } from "react";

export function renderWithProviders(ui: ReactElement, options?: RenderOptions) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
  return render(ui, { wrapper: Wrapper, ...options });
}
```

A representative test:

```tsx
// src/pages/flyers/new.test.tsx
import { describe, it, expect } from "vitest";
import userEvent from "@testing-library/user-event";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import { NewFlyerPage } from "./new";

describe("NewFlyerPage", () => {
  it("requires a title", async () => {
    renderWithProviders(<NewFlyerPage />);
    await userEvent.click(screen.getByRole("button", { name: /generate/i }));
    expect(await screen.findByText(/string must contain at least 1/i)).toBeInTheDocument();
  });
});
```

### Anti-Patterns to Avoid

- **Two HTTP layers:** Don't add axios alongside openapi-fetch. Pick one, and openapi-fetch is locked.
- **Polling without termination:** Forgetting to return `false` from `refetchInterval` = wasted requests forever. Use the `useJob` hook from Pattern 3 -- never inline.
- **React Router loader fetching server data:** Loaders + TanStack Query = duplicated cache. Use loaders only if you ever need SSR-style prefetch (you don't).
- **`useEffect` for fetch:** TanStack Query `useQuery` replaces 95% of fetch-in-useEffect patterns. Reach for useEffect only for non-data side-effects (focus, scroll, subscriptions).
- **Mixing default and named exports for components:** Pick named exports (`export function Foo`); easier refactor + better tree-shaking with Vite.
- **Putting zod schemas in src/schemas/ "just in case":** YAGNI for v1. Colocate per-form. Centralize when a duplicate appears.
- **ShadCN component edits without recording the change:** ShadCN files are owned by the project after copy-paste -- no upgrade path. If you edit one, leave a comment so the next person doesn't re-run `shadcn add` and clobber it.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| TS types from OpenAPI | Hand-write request/response interfaces | `openapi-typescript` codegen | Phase 20 schemas drift; codegen always matches the live API |
| Polling | `setInterval` + `useState` + cleanup | TanStack Query `refetchInterval` | Tab-visibility pause, dedup, cache, error handling all built-in |
| Form state | Controlled `useState` per field | `react-hook-form` | Re-renders only changed fields; integrates with zod for typed validation |
| Form validation | `if (!field) errors.push(...)` | `zod` + `@hookform/resolvers/zod` | Schema doubles as TS type via `z.infer<>`; catches drift early |
| Toast notifications | Custom `<Notification />` system | `sonner` (via ShadCN) | Stacking, timeouts, swipe-to-dismiss, a11y all there |
| HTTP mocking in tests | `vi.spyOn(global, "fetch")` per test | `msw` v2 | Mocks at the network layer; one set of handlers serves dev + tests |
| Routing | `if (location.pathname === "/x")` switches | `react-router` v7 | Nested layouts, outlet, type-safe params, history management |
| Class-name composition | String concat or template literals | `clsx` + `tailwind-merge` (ShadCN's `cn()`) | Handles Tailwind class collisions correctly |
| Component library | Building Buttons, Inputs from scratch | ShadCN/ui | Accessible Radix primitives + Tailwind styling, copy-paste so you OWN them |
| ULID timestamp parsing | Bit-shift the first 10 chars yourself | `ulid` package's `decodeTime()` | Correct base32 + 48-bit math |
| Icons | SVG copy-paste per icon | `lucide-react` | Tree-shaken; ShadCN's default; consistent stroke style |

**Key insight:** The frontend ecosystem in 2026 has battle-tested solutions for every category above. Hand-rolling any of them costs days and produces inferior UX. The ShadCN-style "copy-paste, no UI dep" pattern keeps the dependency surface minimal while still leveraging the ecosystem.

## Pitfalls

The 9 things most likely to bite an executor of this exact stack:

1. **`refetchInterval` callback signature drift (v4 -> v5).** In TanStack Query v4 the callback was `(data, query) => ...`. In v5 it is `(query) => ...` and `data` is reached as `query.state.data`. Code copied from a 2024 blog post will silently never stop polling because `data` is `undefined` and the terminal-status check never matches. Verified in v5 migration docs [VERIFIED: TanStack Query v5 migration guide]. Pattern 3 above is correct for v5.

2. **`cacheTime` -> `gcTime` rename in v5.** The option that controls how long cached data lingers after the last subscriber unmounts was renamed. Using `cacheTime` in v5 silently fails (the option is ignored). Pattern 3 above uses the correct name [VERIFIED: TanStack Query v5 migration guide].

3. **ShadCN CLI name confusion.** The package on npm is `shadcn` (note: `npm view shadcn version` returns 4.4.0). The OLD package was `shadcn-ui`. Running `npx shadcn-ui@latest init` either fails or installs an outdated version. Use `npx shadcn@latest init` [VERIFIED: shadcn/ui Vite docs].

4. **Tailwind v4 has NO `tailwind.config.js`.** Configuration moved into CSS via `@theme`. Plans that copy a v3-era `tailwind.config.ts` from another project will produce a working but mis-configured setup where ShadCN's tokens don't apply. Pattern 1's `index.css` example is the canonical setup [VERIFIED: Tailwind v4 docs + ShadCN v4 docs].

5. **`react-router` v7 unifies but re-export shim still exists.** In v7 you can import everything from `react-router` directly (no more `react-router-dom`). Both packages currently work, but mixing them in one codebase causes "two contexts" bugs where `useNavigate` in one file silently stops working. Pick `react-router` (singular) and use it everywhere. The CONTEXT.md recommendation aligns with this.

6. **Vite dev proxy + `baseUrl` interaction.** If `vite.config.ts` proxies `/api` to `http://localhost:8000`, then the openapi-fetch client's `baseUrl` should be `/api/v1` (relative). If you also set `VITE_API_URL=http://localhost:8000/api/v1` in `.env.local`, that absolute URL bypasses the proxy AND triggers a CORS preflight (which Phase 20 allows from `:5173`, so it works -- but you've gained nothing). Pick one approach. Recommendation: rely on the Vite proxy in dev (relative `baseUrl`), use `VITE_API_URL` only when pointing at a different backend.

7. **ULID character set for path validation.** `JobRecord.id` is a 26-char ULID using Crockford base32 (`0-9A-HJKMNP-TV-Z`). The Phase 20 path param validates only `min_length=26, max_length=26` -- it does NOT regex-check the alphabet. The frontend should still validate before constructing URLs to avoid hitting the server with garbage. The `ulid` npm package's `decodeTime()` will throw on invalid input -- catch it in the route component.

8. **Brochure job has 3 artifacts but `result_ref` is a single string.** `JobRecord.result_ref` is `String(26)` (one render id). The brochure produces front PNG + back PNG + PDF. The Phase 20 task currently picks ONE of these as the `result_ref` (likely the PDF or the front PNG -- needs verification by reading `flyer_generator/api/tasks/brochure.py`). The brochure status page MUST handle the case where it cannot show all three, OR a small Phase 21 task should extend the worker to set `result_ref` to a comma-list / extend `JobDetail` with a structured `artifacts` field. See Open Questions Q4.

9. **Brand-kit logos have no streaming endpoint.** `BrandKit.logos` contains filesystem paths (e.g. `.brand-kits/shrubnet/logos/primary.png`). Phase 20's `/api/v1/renders/{id}/image` only serves rows from `RenderRecord` -- it does NOT serve arbitrary files from `.brand-kits/`. The frontend can show palette + typography from JSON, but cannot render logos without either (a) a new Phase 20 route, or (b) base64-embedding logos in the `BrandKitDetail` response. See Open Questions Q3.

10. **MSW v2 `onUnhandledRequest` defaults to `warn`.** Tests that hit a real but un-mocked endpoint will silently pass with empty data, then fail mysteriously elsewhere. Pattern 6 above sets `onUnhandledRequest: "error"` in `setup.ts` -- keep that strict default.

## Code Examples

The patterns above are the verified, source-cited code examples. Repeating once for the elapsed-time helper since it's referenced in CONTEXT and not in any pattern:

```ts
// src/lib/elapsed.ts
// Hand-rolled ms-to-human formatter. ~5 lines, no date-fns dep.
export function formatElapsed(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ${s % 60}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}
```

```ts
// src/lib/ulidTime.ts
import { decodeTime } from "ulid";
export function ulidToDate(id: string): Date | null {
  try {
    return new Date(decodeTime(id));
  } catch {
    return null;
  }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `tailwind.config.js` + PostCSS dance | Tailwind v4 + `@tailwindcss/vite` + CSS-first `@theme` | Tailwind v4 GA (early 2025) | No JS config file; faster build; smaller install |
| `react-router-dom` | `react-router` (v7 unified) | React Router v7 (late 2024) | One package; merged with Remix |
| `useQuery({...}, { refetchInterval: (data) => ... })` | `useQuery({...}, { refetchInterval: (query) => ... })` | TanStack Query v5 | Callback receives Query object, not data |
| `cacheTime` | `gcTime` | TanStack Query v5 | Renamed for clarity |
| `npx shadcn-ui@latest init` | `npx shadcn@latest init` | shadcn 2.x rename | Old package abandoned |
| Class components | Function components + hooks | React 16.8+ | Universal in 2026 |
| CRA (Create React App) | Vite | Since 2023 | CRA is officially deprecated |
| Jest for Vite projects | Vitest | Vite-era projects | Native Vite, faster |
| ESLint .eslintrc.json | ESLint flat config (`eslint.config.js`) | ESLint 9 (and required in 10) | Locked in 10.x |

**Deprecated / outdated:**

- `create-react-app` -- deprecated. Use `pnpm create vite`.
- `node-fetch` polyfill -- not needed; modern Node has `fetch`.
- `react-router-dom` package -- still works as a re-export shim, but new code should import from `react-router`.
- `shadcn-ui` (old npm name) -- replaced by `shadcn`.
- `tailwind.config.{js,ts}` for v4 projects -- not used; `@theme` in CSS replaces it.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | TypeScript 5.7 is preferable to 6.0.3 for a new project lockfile | Standard Stack | LOW. TS 6 is published but new; either works. CONTEXT.md says "5.x" so 5.7 is the conservative match. |
| A2 | Brochure task currently sets `JobRecord.result_ref` to ONE of {front PNG, back PNG, PDF} -- not all three | Pitfalls #8 | MEDIUM. Need to verify by reading `flyer_generator/api/tasks/brochure.py` -- if it sets all three somehow (e.g. as a list serialized into the column), pitfall #8 dissolves. |
| A3 | `BrandKit.logos` field contains filesystem paths NOT base64-encoded image bytes | Pitfalls #9 + Open Q3 | MEDIUM. Could be base64 in `brand.json`. Need to inspect `flyer_generator/brand_kit/models.py`. If base64, the frontend can render logos directly with no new endpoint. |
| A4 | Phase 20's `JobRecord.id` ULIDs use the standard Crockford base32 alphabet | Pitfalls #7 | LOW. The `ulid` Python package matches the spec. |
| A5 | `eslint-plugin-tailwindcss` v3.18 is incompatible with Tailwind v4 | Standard Stack | LOW-MEDIUM. The plugin is at v3.18.3, no v4 listing yet. The Prettier plugin is the safer bet for v1. If a tailwind-aware ESLint plugin appears with v4 support during Phase 21, plans can revisit. |
| A6 | Vite 8.x is API-compatible with the Vite 7-era ShadCN docs | Architecture | LOW. Vite 8 was a small jump (Node 22 baseline + perf); the plugin API is stable. |

## Open Questions

These are gaps in the Phase 20 backend that affect Phase 21 plans. The planner should resolve them by either (a) adding small backend tasks to Phase 21, (b) downscoping the affected requirement, or (c) deferring the affected feature. **Do NOT re-surface these to the user** -- decide in the plan structure.

1. **FE-09 needs `GET /api/v1/jobs` (list of all jobs) -- not currently exposed.**
   - What we know: `GET /jobs/{id}` exists. `JobRecord` has `kind` + `status` indexes -- DB-friendly for list+filter.
   - What's missing: A list route. Phase 20 closed without it because no consumer existed.
   - Recommended resolution: Add a small Plan 21-N near the end that ships `GET /api/v1/jobs?status=&kind=&limit=&offset=` returning `Paginated<JobDetail>`. Backend code is ~30 lines (mirrors the brand-kits list pattern). Plan it in the same wave that builds the Jobs page (`pages/jobs/list.tsx`).

2. **FE-10 needs `GET /api/v1/renders` (list of all renders) -- not currently exposed.**
   - What we know: `RenderRecord` has `kind` index + `created_at`.
   - What's missing: A list route + per-record summary endpoint.
   - Recommended resolution: Same approach as Q1. Add `GET /api/v1/renders?kind=&since=&limit=&offset=` returning `Paginated<RenderSummary>`. The image stream route already exists.

3. **Brand-kit logos and source artifacts have no public URL.**
   - What we know: `BrandKit.logos` is a list (likely of `BrandLogo` objects with file paths). `RenderRecord` does not track them.
   - What's missing: An endpoint to stream `.brand-kits/<slug>/logos/<filename>`.
   - Recommended resolution: Add a small route `GET /api/v1/brand-kits/{slug}/logos/{filename}` with the same path-traversal mitigation as `/renders/{id}/image`, restricted to `settings.brand_kits_dir`. Plan this alongside FE-04. Alternative (simpler): inline base64-encode logos into the `BrandKitDetail` response. Recommend the route approach because logos can be large and inline base64 bloats the JSON cache.

4. **Brochure jobs return only ONE artifact via `result_ref`.**
   - What we know: `JobRecord.result_ref` is `String(26)` (one render id). Brochures produce 3 artifacts.
   - What's missing: A way to expose all three.
   - Recommended resolution: Two options. (a) Cheap fix: change the brochure task to set `result_ref` to the PDF render id (the most useful single artifact), and have the brochure status page also fetch `RenderRecord`s by querying a NEW route `GET /api/v1/brochures/{id}` that returns `{front_render_id, back_render_id, pdf_render_id}`. (b) More elegant: extend `JobDetail.result_ref` to support a `{kind: "brochure", artifacts: {front, back, pdf}}` variant. Recommend (a) -- a small targeted route is simpler than evolving the polymorphic `result_ref`. Plan in the same wave as the brochure status page.

5. **Where to put zod schemas long-term.** CONTEXT.md says hand-write per-form. Recommendation in this research: keep colocated per-form (`pages/flyers/new.tsx` exports `FlyerFormSchema`). When the same shape is reused across two pages, promote it to `src/lib/schemas.ts`. **The planner should NOT pre-create a `src/schemas/` directory.**

6. **Whether a global `<Toaster />` lives in `main.tsx` or in `DashboardLayout`.** Either works. Recommend `main.tsx` so toasts work even on error-route pages outside the dashboard layout. Pattern 5 above places it in `main.tsx`.

7. **Initial route on `/`.** Plans can either redirect to `/brand-kits` (recommended -- most likely first user action) or render a "recent jobs" widget. Recommend redirect for the v1 ship; widget can come in a polish wave.

8. **Should Vite's `optimizeDeps` exclude `msw`?** msw v2 ships ESM-first; Vite usually handles it correctly. If the test runner reports "module not found" for `msw/node`, add `optimizeDeps: { exclude: ["msw"] }` to `vite.config.ts`. Plan to NOT add it preemptively; only react to a concrete error.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js >= 22 | Vite 8, all frontend tooling | Check at execution time | - | If not installed: install via nvm/fnm/volta. Plan 21-01 should detect and document. |
| pnpm >= 9 | All frontend installs | Check at execution time | - | If not installed: `npm install -g pnpm@10`. Document in README. |
| Backend running on :8000 | API codegen + dev | Conditional | Phase 20 API | For codegen: use `gen:api:snapshot` against checked-in `openapi.snapshot.json`. For dev: `make serve` from repo root. |
| ImageMagick / Cairo / etc. | NOT required by frontend | - | - | Frontend has no native deps; pure JS install. |

**Missing dependencies with fallback:**
- Backend not running during dev -> `gen:api:snapshot` regen path.

**Missing dependencies with no fallback:**
- Node.js / pnpm -- the executor must install them. CLAUDE.md amendment in Plan 21-01 documents this.

## Security Domain

The CONTEXT.md `<deferred>` block excludes auth from this phase. The frontend therefore inherits the exact same posture as Phase 20: trusted private network. ASVS categories apply at minimal level:

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | NO | Out of scope (single-user, trusted network) |
| V3 Session Management | NO | No sessions |
| V4 Access Control | NO | No multi-user |
| V5 Input Validation | YES | zod schemas on every form. NEVER `dangerouslySetInnerHTML`. NEVER `eval`. |
| V6 Cryptography | NO | No crypto in the client |
| V7 Error Handling | YES | Error responses are toasted, not logged to localStorage. Trace IDs are visible to the user (intentional, for support). |
| V8 Data Protection | YES (light) | No PII in localStorage. `.env.local` is gitignored. |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| XSS via user-supplied content rendered in `<img alt>`, `<a href>`, etc. | Tampering | React escapes by default. Don't use `dangerouslySetInnerHTML`. |
| URL-injection from `result_ref` field | Tampering | Validate `result_ref` starts with `/api/v1/renders/` before using as `<img src>`. |
| Open-redirect via `state` from URL params | Spoofing | Don't redirect based on URL params. All navigation is route-driven. |
| Secrets in env (`VITE_API_URL`) leaking into bundle | Information Disclosure | Vite exposes only `VITE_*` prefixed vars by design; document this in `.env.example` and never put secrets there. |
| CSP missing | Tampering | Phase 21 v1 does not deploy. When it does, add `Content-Security-Policy` headers via the static host. Out of scope here. |

The most likely real-world issue: **users will paste arbitrary URLs into the brand-kit scrape form.** The Phase 20 scraper has SSRF mitigations from Phase 18 (private-IP rejection, protocol allow-list, timeout). The frontend should pre-validate that the URL is `http://` or `https://` and present a clear error if the backend rejects it -- but does NOT need to duplicate the SSRF rules. The 422 error comes back as `{detail: "...", error_type: "BrandKitError"}` and is toasted.

## Sources

### Primary (HIGH confidence)

- [Phase 20 OpenAPI source — `flyer_generator/api/`](file:///home/hoyack/work/autocreative/flyer_generator/api/) — exact request/response shapes [VERIFIED: file inspection]
- [Phase 20 PHASE-SUMMARY.md](file:///home/hoyack/work/autocreative/.planning/phases/20-fastapi-sqlalchemy-backend/PHASE-SUMMARY.md) — 8 routes shipped, error mapper, ULID job ids, /healthz, CORS default
- [21-CONTEXT.md](file:///home/hoyack/work/autocreative/.planning/phases/21-react-frontend-dashboard/21-CONTEXT.md) — locked architectural decisions
- [npm registry] `npm view <pkg> version` for every package version listed in Standard Stack — verified 2026-04-22
- [shadcn/ui Vite installation](https://ui.shadcn.com/docs/installation/vite) — current init flow, Tailwind v4 path
- [shadcn/ui Tailwind v4 page](https://ui.shadcn.com/docs/tailwind-v4) — confirms compatibility for new projects
- [TanStack Query v5 migration guide](https://tanstack.com/query/v5/docs/framework/react/guides/migrating-to-v5) — `refetchInterval(query)` signature, `cacheTime -> gcTime`
- [openapi-fetch docs](https://openapi-ts.dev/openapi-fetch/) — `createClient<paths>()` typed-client pattern
- [openapi-fetch API docs](https://openapi-ts.dev/openapi-fetch/api) — request/response error handling
- [React Router v7 routing docs](https://reactrouter.com/start/data/routing) — data-router mode, nested layouts, Outlet
- [Tailwind CSS v4 Vite installation](https://tailwindcss.com/docs/installation/using-vite) — `@tailwindcss/vite` plugin

### Secondary (MEDIUM confidence)

- [Tailwind v4 setup with Vite -- 2026 guide](https://thelinuxcode.com/how-to-set-up-tailwind-css-with-vite-2026-guide-tailwind-v4-plugin-legacy-v3-postcss/) — corroborates plugin pattern
- [Robin Wieruch React Router 7 nested routes](https://www.robinwieruch.de/react-router-nested-routes/) — secondary confirmation of Outlet pattern

### Tertiary (LOW confidence -- pattern verified, exact APIs not freshly checked)

- General React Hook Form + zod resolver pattern -- universal in 2026 ecosystem; trusted from training and matches `@hookform/resolvers/zod` README
- General Vitest + Testing Library + msw setup -- universal pattern; matches Vitest official docs

## Metadata

**Confidence breakdown:**
- API surface (Phase 20 contract): HIGH — read directly from source files
- Locked stack versions: HIGH — verified via `npm view` against npm registry
- Polling code pattern (Pattern 3): HIGH — verified against TanStack Query v5 migration docs
- ShadCN Tailwind v4 setup: HIGH — confirmed in shadcn/ui official docs
- Brochure 3-artifact handling (Pitfall #8 / Open Q4): MEDIUM — assumes current task picks ONE artifact; needs verification of `flyer_generator/api/tasks/brochure.py`
- Logo serving (Pitfall #9 / Open Q3): MEDIUM — assumes file paths in `BrandKit.logos`; needs verification of `BrandKit` model

**Research date:** 2026-04-22
**Valid until:** ~2026-05-22 (30 days for stable libraries; sooner if React 19.x or Vite 8.x ships a major).
