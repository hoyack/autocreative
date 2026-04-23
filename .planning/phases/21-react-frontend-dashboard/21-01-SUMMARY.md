---
phase: 21-react-frontend-dashboard
plan: 01
subsystem: ui
tags: [react, vite, typescript, tailwind, shadcn, pnpm, eslint, prettier, frontend-scaffold]

# Dependency graph
requires:
  - phase: 20-fastapi-sqlalchemy-backend
    provides: Phase 20 API running on :8000 — the dashboard's data source. Not consumed yet in this plan, but the scaffold's Vite dev-proxy already targets it so plan 21-02 onwards can talk to /api without CORS.
provides:
  - frontend/ directory scaffolded from zero with Vite 8 + React 19 + TypeScript 5.9 (strict) + Tailwind v4 + ShadCN
  - pnpm 10 project with packageManager pin and 11 scripts (dev/build/preview/test/test:watch/lint/lint:fix/format/typecheck/gen:api/gen:api:snapshot)
  - Vite dev proxy /api/* → http://localhost:8000 (no CORS in dev)
  - Path alias @/* → src/*
  - ESLint 10 flat config + Prettier 3 + prettier-plugin-tailwindcss wired
  - ShadCN initialized (components.json, lib/utils.ts cn helper, Button primitive)
  - Tailwind v4 CSS-first @theme block coexists with ShadCN :root/.dark token blocks
  - Root .gitignore excludes frontend/node_modules/, frontend/dist/, frontend/.env.local (+ tsbuildinfo and compiled vite.config artifacts)
  - CLAUDE.md + PROJECT.md amended to document Node.js >= 22 + pnpm >= 9 as REQUIRED for optional frontend; Python stack constraint narrowed to "no sharp/Puppeteer"
  - README.md "## Frontend (Phase 21)" section — prereqs, install, dev, test/lint/build, deferred deploy story, gen:api flow
affects: [21-02-api-client, 21-03-data-layer, 21-04-brand-kits, 21-05-flyers, 21-06-brochures, 21-07-social, 21-08-campaigns, 21-09-jobs, 21-10-renders, 21-11-polish]

# Tech tracking
tech-stack:
  added:
    - "node@22 (runtime) + pnpm@10.14.0 (package manager, pinned via packageManager)"
    - "vite@8.0.10 + @vitejs/plugin-react@6.0.1 (build/dev tool)"
    - "react@19.2.5 + react-dom@19.2.5"
    - "typescript@5.9.3 (strict mode, bundler moduleResolution)"
    - "@types/react@19.2.14 + @types/react-dom@19.2.3 + @types/node@22.19.17"
    - "tailwindcss@4.2.4 + @tailwindcss/vite@4.2.4 (CSS-first config, no tailwind.config.js)"
    - "shadcn@4.4.0 (CLI + registry), nova preset (radix base), installs: class-variance-authority@0.7.1, clsx@2.1.1, tailwind-merge@3.5.0, radix-ui@1.4.3, lucide-react@1.8.0, tw-animate-css@1.4.0, @fontsource-variable/geist@5.2.8"
    - "eslint@10.2.1 + @eslint/js@10.0.1 + typescript-eslint@8.59.0 + eslint-plugin-react-hooks@7.1.1 + eslint-plugin-react-refresh@0.5.2 (flat config)"
    - "prettier@3.8.3 + prettier-plugin-tailwindcss@0.6.14"
  patterns:
    - "Vite dev proxy forwards /api/* to FastAPI — avoids CORS in dev and keeps the client code identical to eventual same-origin prod"
    - "@/* → src/* path alias configured in BOTH tsconfig.json (paths) AND vite.config.ts (resolve.alias) so tsc + Vite agree"
    - "Tailwind v4 CSS-first: @theme block in src/index.css replaces tailwind.config.js; ShadCN's :root/.dark/@theme inline tokens append below the project @theme block and coexist without conflict"
    - "tsc -b + composite project references: tsconfig.node.json scoped to vite.config.ts only; main src graph under tsconfig.json"
    - "pnpm packageManager pin in package.json ensures contributors cannot silently switch to npm/yarn"

key-files:
  created:
    - "frontend/package.json — 11 scripts, pnpm@10.14.0 pinned, separates deps (react*) from devDeps (build/tool chain)"
    - "frontend/pnpm-lock.yaml — reproducible install graph"
    - "frontend/tsconfig.json — strict, ES2022, bundler resolution, @/* alias, references tsconfig.node.json"
    - "frontend/tsconfig.node.json — composite project for vite.config.ts"
    - "frontend/vite.config.ts — React + Tailwind plugins, @/* alias, /api proxy → :8000"
    - "frontend/index.html — minimal HTML shell"
    - "frontend/src/main.tsx — React 19 createRoot with StrictMode; renders Button smoke-test"
    - "frontend/src/index.css — @import tailwindcss + @theme brand tokens + ShadCN token blocks"
    - "frontend/src/lib/utils.ts — cn() helper (clsx + tailwind-merge)"
    - "frontend/src/components/ui/button.tsx — ShadCN Button + buttonVariants (cva + radix Slot)"
    - "frontend/components.json — ShadCN config (style: radix-nova, baseColor: neutral, cssVariables: true)"
    - "frontend/.env.example — documents optional VITE_API_URL; dev proxy is the default"
    - "frontend/.prettierrc.json — Prettier + tailwindcss plugin"
    - "frontend/eslint.config.js — flat config with typescript-eslint + react-hooks + react-refresh"
    - "frontend/public/favicon.svg — 16x16 dark-slate 'f' mark"
  modified:
    - ".gitignore — added Phase 21 block (frontend/node_modules/, frontend/dist/, frontend/.env.local, frontend/.env.*.local, frontend/*.tsbuildinfo, frontend/vite.config.{d.ts,js})"
    - "CLAUDE.md — split 'No Node.js deps' constraint into (a) no sharp/Puppeteer in Python stack and (b) optional frontend REQUIRES Node.js >= 22 + pnpm >= 9"
    - ".planning/PROJECT.md — mirror of CLAUDE.md constraint amendment (canonical source)"
    - "README.md — inserted '## Frontend (Phase 21)' section between '## API server (Phase 20)' and '## See also'"

key-decisions:
  - "Vite dev proxy is the dev default (VITE_API_URL left commented in .env.example) — matches CONTEXT.md 'Dev Loop' trade-off"
  - "Pinned prettier-plugin-tailwindcss to ^0.6 explicitly — pnpm otherwise resolved to an insiders 0.0.0 pre-release"
  - "Installed @types/node to satisfy vite.config.ts (node:path, __dirname) under bundler moduleResolution"
  - "Accepted shadcn 4.4.0 preset-driven init (nova + radix base) in place of the plan's new-york + slate request; preset CLI is the only non-interactive path and the smoke test goal is unaffected"
  - "Mirrored CLAUDE.md amendment into .planning/PROJECT.md so the canonical source matches; next auto-regeneration of CLAUDE.md from the GSD markers will keep the change"
  - "Did NOT install TanStack Query / react-router / openapi-fetch / RHF / zod / sonner / vitest yet — per plan those belong to 21-02..21-04 alongside the code that uses them"

patterns-established:
  - "Pattern: Vite dev proxy — /api/* → http://localhost:8000, changeOrigin: true (dev-only CORS bypass)"
  - "Pattern: @/* → src/* path alias in tsconfig + vite.config (both required)"
  - "Pattern: Tailwind v4 CSS-first — @import 'tailwindcss' + @theme block in src/index.css; no tailwind.config.js"
  - "Pattern: ShadCN Tailwind v4 coexistence — project @theme block stays; shadcn init appends @theme inline + :root + .dark below"
  - "Pattern: pnpm packageManager pin — fails fast if a contributor tries npm/yarn"
  - "Pattern: Separation of runtime deps (react, radix-ui, lucide-react, tw-animate-css, etc.) from devDeps (vite, typescript, eslint, prettier, tailwindcss)"

requirements-completed: [FE-01]

# Metrics
duration: 8min
completed: 2026-04-23
---

# Phase 21 Plan 01: Frontend Scaffold Summary

**Vite 8 + React 19 + TypeScript 5.9 (strict) + Tailwind v4 + ShadCN Button smoke-tested — `pnpm dev` boots on :5173 in 368ms, `pnpm build` emits a 222 KB JS / 20.5 KB CSS bundle with Tailwind utilities compiled.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-23T11:54:02Z
- **Completed:** 2026-04-23T12:02:14Z
- **Tasks:** 3
- **Files modified:** 18 (15 created under frontend/, 3 modified at repo root: .gitignore, CLAUDE.md, README.md + mirror in .planning/PROJECT.md)

## Accomplishments

- Vite 8 project scaffolded from zero — `pnpm install` + `pnpm typecheck` + `pnpm build` + `pnpm dev` all succeed.
- Tailwind v4 + ShadCN pipeline smoke-tested: `pnpm build` CSS bundle contains `bg-primary` and `text-muted-foreground` utility classes, confirming the Vite plugin transforms work end-to-end.
- Button primitive renders inside `src/main.tsx` via `@/components/ui/button` — proves path alias + ShadCN + Tailwind v4 coexist.
- Repo-level project hygiene: root `.gitignore` excludes frontend transient paths; `CLAUDE.md` + `PROJECT.md` amended so the project no longer asserts it is "pure Python"; README has a self-contained Frontend section.

## Task Commits

1. **Task 1: Bootstrap pnpm + Vite + React 19 + TypeScript 5.7 (strict)** — `ab7e22b` (feat)
2. **Task 2: Initialize Tailwind v4 + ShadCN (smoke test the component pipeline)** — `4fd5e6c` (feat)
3. **Task 3: Land repo-level updates — CLAUDE.md amendment + README "Frontend (Phase 21)" section** — `720210f` (docs)

_Orchestrator adds the metadata commit after all Wave 1 agents merge._

## Files Created/Modified

**Created:**
- `frontend/package.json` — pnpm-pinned project manifest; 11 scripts (dev/build/preview/test/test:watch/lint/lint:fix/format/typecheck/gen:api/gen:api:snapshot)
- `frontend/pnpm-lock.yaml` — reproducible install graph
- `frontend/tsconfig.json` — strict TS, ES2022 target, bundler moduleResolution, @/* alias
- `frontend/tsconfig.node.json` — composite project scoped to vite.config.ts
- `frontend/vite.config.ts` — React + Tailwind plugins, /api proxy, @/* alias
- `frontend/index.html` — HTML shell
- `frontend/src/main.tsx` — React 19 entry; renders Button smoke test
- `frontend/src/index.css` — Tailwind v4 @import + project @theme + ShadCN tokens
- `frontend/src/lib/utils.ts` — cn() helper
- `frontend/src/components/ui/button.tsx` — ShadCN Button primitive
- `frontend/components.json` — ShadCN config (style: radix-nova, baseColor: neutral)
- `frontend/.env.example` — optional VITE_API_URL comment
- `frontend/.prettierrc.json` — Prettier + tailwind plugin
- `frontend/eslint.config.js` — flat config
- `frontend/public/favicon.svg` — 16x16 'f' mark

**Modified:**
- `.gitignore` — Phase 21 block (node_modules/, dist/, .env.local, .env.*.local, *.tsbuildinfo, vite.config.{d.ts,js})
- `CLAUDE.md` — constraint amendment
- `.planning/PROJECT.md` — mirror of CLAUDE.md amendment (canonical source)
- `README.md` — new `## Frontend (Phase 21)` section between Phase 20 and "See also"

## Decisions Made

- **pnpm 10.14.0 pinned** via `packageManager` field (plan asked for pnpm@10.0.0; used the version already installed on this machine — `^` semantics for pnpm self are irrelevant here, pnpm treats `packageManager` as exact).
- **Vite dev proxy is the default, VITE_API_URL is optional** — `.env.example` ships the variable commented out; devs who need a non-localhost backend can uncomment. This matches CONTEXT.md's "Dev Loop" recommendation.
- **Pinned `prettier-plugin-tailwindcss@^0.6`** — without the explicit range, pnpm resolved it to an insiders pre-release (`0.0.0-insiders.f7d2598`) which is not a stable build. Forcing `^0.6` gave `0.6.14`.
- **Added `@types/node`** — the plan did not list it, but `vite.config.ts` imports `node:path` and uses `__dirname`, both of which require Node ambient types under `moduleResolution: "bundler"`. Installed as a devDep (Rule 3 fix).
- **ShadCN init flags** — shadcn 4.4.0 requires a preset to run non-interactively; `-t vite -b radix -p nova --yes --silent` was the minimum flag set that avoided the interactive prompt. The resulting `components.json` records `style: "radix-nova"` and `baseColor: "neutral"` instead of the plan's requested `new-york` + `slate`. Functionally equivalent for the smoke test; full visual styling is polished in later plans.
- **Mirrored CLAUDE.md amendment into `.planning/PROJECT.md`** — the GSD markers in CLAUDE.md cite PROJECT.md as the canonical source, so updating only CLAUDE.md would have been silently reverted on the next auto-regeneration.
- **Did NOT install the rest of the stack** — TanStack Query, react-router, openapi-fetch/typescript, RHF, zod, sonner, vitest, MSW are reserved for plans 21-02..21-04 to keep each plan's diff tight.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added `@types/node` so `vite.config.ts` typechecks**
- **Found during:** Task 1 (verification step `pnpm build`)
- **Issue:** TypeScript errors `TS2307: Cannot find module 'node:path'` and `TS2304: Cannot find name '__dirname'` because the plan did not include `@types/node` in the devDep install list.
- **Fix:** `pnpm add -D @types/node@^22`. TypeScript picks up Node types automatically from `node_modules/@types/node` under `moduleResolution: "bundler"` with default `types` behavior.
- **Files modified:** `frontend/package.json`, `frontend/pnpm-lock.yaml`.
- **Verification:** `pnpm build` now succeeds (tsc -b returns 0, Vite emits `dist/index.html` + `dist/assets/*.js` + `dist/assets/*.css`).
- **Committed in:** `ab7e22b` (Task 1 commit).

**2. [Rule 3 - Blocking] Pinned `prettier-plugin-tailwindcss@^0.6` explicitly**
- **Found during:** Task 1 (after `pnpm add -D prettier-plugin-tailwindcss`).
- **Issue:** Unversioned install resolved to `0.0.0-insiders.f7d2598`, which is an unreleased pre-release and would have made the lockfile fragile.
- **Fix:** Re-added with explicit `^0.6` range → resolved to `0.6.14`.
- **Files modified:** `frontend/package.json`, `frontend/pnpm-lock.yaml`.
- **Verification:** Lockfile shows `prettier-plugin-tailwindcss: 0.6.14`; no `0.0.0-insiders` substring in `package.json`.
- **Committed in:** `ab7e22b` (Task 1 commit).

**3. [Rule 3 - Blocking] Extended `.gitignore` with tsc composite build artifacts**
- **Found during:** Task 1 commit staging (`git status --short`).
- **Issue:** `tsc -b` (composite project build) emits `tsconfig.*.tsbuildinfo` plus compiled `vite.config.d.ts` and `vite.config.js` into the working tree. These are build outputs, not source, and would pollute the commit if tracked.
- **Fix:** Appended `frontend/*.tsbuildinfo`, `frontend/vite.config.d.ts`, `frontend/vite.config.js` to the Phase 21 block of root `.gitignore`.
- **Files modified:** `.gitignore`.
- **Verification:** `git status --short` after fix shows only the 13 intended Task 1 paths.
- **Committed in:** `ab7e22b` (Task 1 commit, same commit as the rest of Task 1).

**4. [Rule 3 - Blocking] Adapted `npx shadcn@latest init` flags for shadcn 4.4.0**
- **Found during:** Task 2 (running `npx shadcn@latest init`).
- **Issue:** shadcn 4.4.0 no longer exposes an interactive `style: new-york` / `baseColor: slate` prompt. The CLI now requires a preset (`Nova`, `Vega`, `Maia`, `Lyra`, etc.) and a base (`radix` or `base`) to run non-interactively.
- **Fix:** Used `npx shadcn@latest init --template vite --base radix --preset nova --yes --silent`. The resulting `components.json` records `style: "radix-nova"` and `baseColor: "neutral"`.
- **Files modified:** `frontend/components.json`, `frontend/src/index.css` (ShadCN appended its token blocks), `frontend/src/components/ui/button.tsx`, `frontend/src/lib/utils.ts`, `frontend/package.json`, `frontend/pnpm-lock.yaml`.
- **Verification:** Task 2 acceptance criteria all pass — `@import "tailwindcss"`, `@theme`, `--color-brand-500`, `--background:` / `--foreground:` all present in `src/index.css`; `button.tsx` exports `Button` and `buttonVariants`; `pnpm build` produces a CSS bundle containing `bg-primary` and `text-muted-foreground` utility classes.
- **Committed in:** `4fd5e6c` (Task 2 commit).

**5. [Rule 2 - Missing Critical] Mirrored CLAUDE.md amendment into `.planning/PROJECT.md`**
- **Found during:** Task 3 (reviewing GSD marker comments in CLAUDE.md).
- **Issue:** The `## Project` block in `CLAUDE.md` is generated from `.planning/PROJECT.md` — there's a `<!-- GSD:project-start source:PROJECT.md -->` marker comment. Editing only CLAUDE.md would be reverted on the next auto-regeneration.
- **Fix:** Applied the same constraint-block edit to `.planning/PROJECT.md` (the canonical source).
- **Files modified:** `.planning/PROJECT.md`.
- **Verification:** Both files now contain the identical "Optional frontend (Phase 21)" bullet; `grep` sanity-checked both.
- **Committed in:** `720210f` (Task 3 commit).

---

**Total deviations:** 5 auto-fixed (4 Rule 3 blocking, 1 Rule 2 missing-critical consistency fix).
**Impact on plan:** All five are corrections for plan-level omissions — they do not change the intent of the plan, and every task's acceptance criteria still pass. No scope creep.

## Issues Encountered

- **shadcn CLI requires a preset to run non-interactively** — see deviation #4 above. The plan's desired `new-york` / `slate` naming is legacy; in 4.4.0 the preset system supersedes it.
- **tsc -b build artifacts** — caught at staging time; added to `.gitignore` (deviation #3).
- **`prettier-plugin-tailwindcss` insiders resolution** — pinning the range fixed it (deviation #2).

## User Setup Required

None for this plan. Future plans in the phase will require the Phase 20 backend running on `:8000` (documented in README "## Frontend (Phase 21) > Prerequisites").

## Next Phase Readiness

- **Ready for plan 21-02 (API client codegen):** `frontend/package.json` already has `gen:api` and `gen:api:snapshot` scripts. Plan 21-02 will install `openapi-typescript` + `openapi-fetch`, run `pnpm gen:api` against the live backend, and commit both `src/api/schema.gen.ts` and `src/api/openapi.snapshot.json`.
- **Ready for plan 21-03 (routing + providers):** `src/main.tsx` renders a single Button today; plan 21-03 will install `react-router@7` + `@tanstack/react-query@5`, wrap App in `QueryClientProvider` + `RouterProvider`, and split `App` into a router config.
- **Ready for plan 21-04 (ShadCN primitives + layout):** `components.json` + ShadCN CLI are wired; plan 21-04 will run `npx shadcn@latest add input textarea select form card sheet sidebar navigation-menu badge skeleton sonner table dialog separator tabs` alongside the pages that consume them.
- **No blockers.**

## Self-Check

Verifying claims before proceeding.

**Created files exist:**
- `frontend/package.json` — FOUND
- `frontend/pnpm-lock.yaml` — FOUND
- `frontend/tsconfig.json` — FOUND
- `frontend/tsconfig.node.json` — FOUND
- `frontend/vite.config.ts` — FOUND
- `frontend/index.html` — FOUND
- `frontend/src/main.tsx` — FOUND
- `frontend/src/index.css` — FOUND
- `frontend/src/lib/utils.ts` — FOUND
- `frontend/src/components/ui/button.tsx` — FOUND
- `frontend/components.json` — FOUND
- `frontend/.env.example` — FOUND
- `frontend/.prettierrc.json` — FOUND
- `frontend/eslint.config.js` — FOUND
- `frontend/public/favicon.svg` — FOUND

**Commits exist:**
- `ab7e22b` (Task 1) — FOUND
- `4fd5e6c` (Task 2) — FOUND
- `720210f` (Task 3) — FOUND

**Verify runs:**
- `pnpm typecheck` → exits 0
- `pnpm build` → emits `dist/index.html` (462 B), `dist/assets/*.css` (20.5 KB, contains `bg-primary` + `text-muted-foreground`), `dist/assets/*.js` (222 KB)
- `pnpm dev` → boots on `http://localhost:5173/` in 368 ms, serves HTTP 200

## Self-Check: PASSED

---
*Phase: 21-react-frontend-dashboard*
*Completed: 2026-04-23*
