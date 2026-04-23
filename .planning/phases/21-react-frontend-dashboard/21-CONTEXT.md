# Phase 21: React Frontend Dashboard — Context

**Gathered:** 2026-04-22
**Status:** Ready for planning
**Source:** Inline AskUserQuestion (8 architectural decisions) + ROADMAP.md Phase 21 stub + HANDOFF.md §7

<domain>
## Phase Boundary

Phase 21 delivers a single-page React dashboard that consumes the Phase 20 HTTP API. The dashboard is the primary non-CLI interface to all four creative subsystems (flyer / brochure / brand_kit / social).

- **In scope:** React + Vite + ShadCN + Tailwind SPA under `frontend/`. 7 dashboard pages (Brand Kits / Flyers / Brochures / Social posts / Campaigns / Jobs / Renders) with creators, list views, job-polling status streams, render gallery. Typed API client generated from Phase 20's OpenAPI schema. Vitest + Testing Library unit/component tests.
- **Out of scope:** Auth/login (Phase 20 is single-user, private-network trust), multi-tenancy, Playwright e2e, server-side rendering, mobile-responsive design beyond what Tailwind defaults give us, dark mode toggle, i18n, accessibility audit beyond ShadCN defaults.
- **Reuses (no reimplementation):** Phase 20 OpenAPI schema (consumed via codegen), Phase 20 routes (no new server work).
- **Hard dependency:** Phase 20 must be running locally (`make serve`) for the dashboard to function — Phase 21 plans must include the dev-loop boot story.

</domain>

<decisions>
## Implementation Decisions

### Framework Stack (locked in ROADMAP.md)
- **React 19** + **TypeScript 5.x (strict mode)**
- **Vite 7+** as build/dev tool — dev server on port `5173` (matches Phase 20's default `FLYER_CORS_ORIGINS`)
- **ShadCN/ui** for component library (copy-paste components, no npm dep on a UI lib)
- **Tailwind CSS v4** for styling (Tailwind v4 is the current stable; uses CSS-first config)
- **Radix UI** primitives via ShadCN (already a transitive dep)

### Data Fetching + Server State
- **TanStack Query v5** (`@tanstack/react-query@^5`)
- One `QueryClient` provider at app root.
- Polling pattern for `GET /api/v1/jobs/{id}`: `refetchInterval` returns `1000` while `status === "queued" || "running"`, returns `false` (stop) when `status in {"succeeded", "failed", "cancelled"}`. Polling pauses on backgrounded tabs (`refetchIntervalInBackground: false`).
- Mutations for `POST /flyers`, `POST /brochures`, etc. use `useMutation`; on success, navigate to the job-detail page that polls.

### Routing
- **React Router v7** in **data-router mode** (`createBrowserRouter` + `RouterProvider`). Data-router mode pairs cleanly with TanStack Query (loaders can warm the query cache).
- Routes: `/` (dashboard home), `/brand-kits`, `/brand-kits/:slug`, `/brand-kits/new`, `/flyers/new`, `/flyers/:id`, `/brochures/new`, `/brochures/:id`, `/social/posts/new`, `/social/posts/:id`, `/social/campaigns/new`, `/social/campaigns/:id`, `/jobs`, `/jobs/:id`, `/renders` (gallery).

### API Client Codegen
- **openapi-typescript** generates types from Phase 20's `/openapi.json` into `frontend/src/api/schema.gen.ts`.
- **openapi-fetch** is the typed runtime client (~5 KB, no React-specific magic).
- A small `frontend/src/api/client.ts` exports a configured `client` with `baseUrl: import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1"`.
- Codegen recipe: `pnpm gen:api` runs `openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.gen.ts`. Document in README. NOT run in CI; checked-in regen pattern.

### Forms
- **react-hook-form** for all forms (FE-04..FE-08).
- **zod** schemas mirror Phase 20's request shapes (`FlyerCreateRequest`, `BrochureCreateRequest`, etc.). Where possible, derive zod from generated TS types via `zod-to-ts` or hand-write minimal mirrors. Hand-write is fine for v1 — Phase 20 schemas are stable.
- **@hookform/resolvers/zod** integrates the two.
- Form layout: ShadCN `Form`, `Input`, `Textarea`, `Select`, `Switch`, `Button` components. Field validation surfaces inline.

### Directory Layout
- `frontend/` is a sibling of `flyer_generator/` at repo root. NOT a pnpm workspace, NOT a sub-package.
- Standard Vite layout inside:
  - `frontend/src/api/` — generated types + client
  - `frontend/src/components/ui/` — ShadCN copy-pasted primitives
  - `frontend/src/components/` — composite app components
  - `frontend/src/pages/` — top-level route components
  - `frontend/src/routes.tsx` — central router config
  - `frontend/src/lib/` — utilities (cn, formatters, ULID parser, etc.)
  - `frontend/tests/` — Vitest tests
  - `frontend/public/` — static assets
- `frontend/.env.example` documents `VITE_API_URL`. `frontend/.env.local` is gitignored.
- Root `.gitignore` adds `frontend/node_modules/`, `frontend/dist/`, `frontend/.env.local`.

### Package Manager
- **pnpm** (≥ 9). Frontend lockfile lives at `frontend/pnpm-lock.yaml`. `frontend/package.json` declares `"packageManager": "pnpm@9.x"`.
- Project README documents `npm install -g pnpm` as a prereq.

### Testing
- **Vitest** + **@testing-library/react** + **@testing-library/jest-dom** + **jsdom**.
- Component tests live next to components or under `frontend/tests/`.
- **No Playwright / no e2e** in Phase 21 scope. Polling/job-status flows are covered by unit-level fakes (mocked TanStack Query responses).
- Target: ≥ 30 frontend tests green via `pnpm test`. No coverage gate.
- Backend `tests/api/` continues to be the integration boundary.

### Job Polling UX
- Status pages (`/flyers/:id`, `/brochures/:id`, etc.) all use the same `<JobStatusCard jobId={...}/>` component.
- Component owns the TanStack Query `useQuery` for `GET /jobs/{id}` with `refetchInterval` rule above.
- States: `queued` (spinner + "Waiting in queue…"), `running` (spinner + elapsed time), `succeeded` (preview + download link from `result_ref`), `failed` (error_detail.type + error_detail.message), `cancelled` (gray "cancelled" badge).
- Renders preview: PNG → `<img src=resultUrl />`, PDF → `<object data=resultUrl type="application/pdf">` or download link.

### Auth + Tenancy
- **No auth** for Phase 21 — inherited from Phase 20 single-user / private-network trust.
- Single global app state (no user/session context).
- README documents that the app trusts whoever can reach `http://localhost:5173` and `http://localhost:8000`.

### Dev Loop
- Two terminals (or honcho via Phase 20's Procfile):
  - Backend: `make serve` (uvicorn + arq) on `:8000`
  - Frontend: `cd frontend && pnpm dev` on `:5173`
- README "Frontend (Phase 21)" section walks through prereqs, install, dev, build, test.

### Build + Deploy
- `pnpm build` produces a `frontend/dist/` static bundle.
- v1 ships dev-only — no production hosting story (matches Phase 20 deferral).
- A future phase would either:
  - Mount `frontend/dist/` on FastAPI as static files (`StaticFiles(...)`), OR
  - Serve from a separate static host (Vercel / Netlify / Caddy / nginx).
- Phase 21 documents this trade-off in README but does NOT ship either deploy path.

### Claude's Discretion
The planner may decide:

- Exact ShadCN components installed (initially: Button, Input, Textarea, Select, Form, Card, Sheet, Sidebar, NavigationMenu, Badge, Skeleton, Toast — planner can trim/extend per page needs).
- Whether to install `@hookform/resolvers/zod` separately or use react-hook-form's built-in resolver pattern.
- Whether to abstract the polling rule into a custom hook (`useJobPolling(jobId)`) or inline it per page (recommend custom hook — DRY across 5 status pages).
- Whether to ship a global toast bank for mutation errors (recommend yes — ShadCN `Toaster`).
- Tailwind theme tokens — extend to mirror brand-kit palette retrieved at runtime, OR keep static? (recommend static for v1; brand-kit palette display is per-card / per-preview, not a global theme switch.)
- How to render the sidebar (ShadCN `Sidebar` is the obvious choice; alternative is a hand-rolled flex layout).
- Whether to add a "Recent jobs" widget on the dashboard home or keep `/` as a plain redirect to `/brand-kits`.
- ESLint + Prettier config — Vite scaffold's defaults, plus optional `eslint-plugin-tailwindcss`. Planner picks.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 20 (HARD dependency — frontend consumes its API)
- `flyer_generator/api/__init__.py` — app factory + mounted routes
- `flyer_generator/api/routes/*.py` — exact route paths and methods
- `flyer_generator/api/schemas/*.py` — Pydantic request/response shapes (mirrored as zod schemas + TS types)
- `flyer_generator/api/errors.py` — error response body `{detail, error_type, trace_id}` shape
- `flyer_generator/api/models/job.py` — `JobStatus` enum (queued / running / succeeded / failed / cancelled)
- `flyer_generator/api/models/render.py` — `RenderKind` enum
- `README.md` "## API server (Phase 20)" — env vars, boot commands, OpenAPI URL

### OpenAPI source
- Live: `http://localhost:8000/openapi.json` (require running backend during codegen)
- A snapshot is OK to commit at `frontend/src/api/openapi.snapshot.json` for reproducible CI builds; planner's call

### CONTEXT artifacts from Phase 20 (to honor consistent decisions)
- `.planning/phases/20-fastapi-sqlalchemy-backend/20-CONTEXT.md` — Phase 20 architectural decisions
- `.planning/phases/20-fastapi-sqlalchemy-backend/PHASE-SUMMARY.md` — full Phase 20 ledger

### Project conventions
- `CLAUDE.md` — original constraint list. Phase 21 ADDS Node.js to the stack (it was previously a constraint). Document this evolution: "Node.js + pnpm required for the optional `frontend/` dashboard; the Python API + CLI remain the source of truth and are usable without the dashboard."

### Library docs (planner may consult)
- React Router v7 data-router mode docs
- TanStack Query v5 polling docs (`refetchInterval`, `refetchIntervalInBackground`)
- ShadCN/ui CLI docs (`npx shadcn@latest add ...`)
- Tailwind v4 setup with Vite

</canonical_refs>

<specifics>
## Specific Ideas

- Use TanStack Query's `useQuery` for both list reads (`/brand-kits`, `/jobs`) and single reads (`/jobs/{id}` polling). One `queryClient` instance.
- Polling rule lives in a single hook: `useJob(jobId)` returns `{ data, isLoading, isTerminal, isFailed }`.
- Mutations (`useMutation`) for all `POST /…` routes; on success → invalidate the matching list query → navigate to `/{kind}/{returned_id}` polling page.
- The brochure form is the most complex UI: it has a list of `sections[]`, each with `heading`, `body_paragraphs[]`, `bullets[]`. Use react-hook-form's `useFieldArray` for the sections and nested arrays.
- Brand-kit detail page renders palette swatches (CSS divs with hex backgrounds), font samples (CSS @font-face with fetched font URLs is too heavy for v1 — show font NAMES + a "Aa" sample in a system-font fallback), logo gallery (image grid).
- Render gallery (`/renders`) is a CSS-grid of `<RenderCard>` items. Filter by `kind` (flyer / brochure / post) + date range (start with simple `>= last 30 days` chips).
- Render preview pattern: `<img>` for PNG, `<a download href=…>Download</a>` for PDF (skip inline PDF rendering for v1 — `<object>` UX is poor across browsers).
- Use ULID parser to display human-readable timestamps from `JobRecord.id` (ULIDs encode 48-bit timestamp).

</specifics>

<deferred>
## Deferred Ideas

- **Authentication** — magic link, OAuth, JWT, sessions. Phase 21 inherits Phase 20's "no auth, private network" trust model.
- **Multi-tenancy** — no Organization picker, no team management.
- **Playwright e2e tests** — Vitest covers unit. e2e is a future phase.
- **Server-side rendering** — Vite SPA only.
- **Mobile-responsive design** — Tailwind defaults give some flex, but no dedicated mobile layout work.
- **Dark mode** — ShadCN supports it; defer to user demand.
- **i18n / translations** — English only.
- **Accessibility audit** — Radix primitives via ShadCN are accessible by default; no formal axe-core gate in Phase 21.
- **Inline PDF preview** — gallery offers PNG inline; PDFs are download-only.
- **Theme builder** — brand-kit palette is shown per-card, not applied as a global theme.
- **Real-time job streaming** — polling is sufficient; WebSocket/SSE is a future phase if UX demand surfaces.
- **Optimistic mutation rollback** — for v1, mutations are pessimistic (await server). Optimistic patterns can land later.
- **CDN deployment** — `pnpm build` produces `dist/` but Phase 21 does NOT ship a deploy story.
- **Shared zod schemas published as a package** — for v1, hand-write zod mirrors of Pydantic-v2 schemas. A future phase could auto-generate.
- **Image upload to brand-kit** — Phase 20 only supports URL-scrape; Phase 21 mirrors that surface (no file upload).
- **CI for the frontend** — backend already has tests. Frontend CI (`pnpm test`, `pnpm build`) is a polish phase.

</deferred>

---

*Phase: 21-react-frontend-dashboard*
*Context gathered: 2026-04-22 via inline 8-question architectural survey + Phase 20 outputs as canonical refs*
