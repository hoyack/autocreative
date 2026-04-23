---
phase: 21-react-frontend-dashboard
plan: 08
subsystem: ui
tags: [frontend, social-posts, form-page, rhf, zod, tanstack-query, shadcn-select, shadcn-textarea, job-polling, tdd]

# Dependency graph
requires:
  - phase: 21-react-frontend-dashboard
    plan: 02
    provides: openapi-fetch client + PostCreateRequestBody alias + JobCreated aliases + queryKeys.jobs() + openapi.snapshot.json (already contains /api/v1/social/posts)
  - phase: 21-react-frontend-dashboard
    plan: 03
    provides: plan-21-03 stub pages at frontend/src/pages/social/posts/{new,status}.tsx (REPLACED here) and /social/posts/new + /social/posts/:id routes already wired in routes.tsx
  - phase: 21-react-frontend-dashboard
    plan: 04
    provides: <JobStatusCard/> + useJob hook + RenderPreview + vitest/msw harness + <Toaster/> position convention
  - phase: 21-react-frontend-dashboard
    plan: 05
    provides: ShadCN Form/Input/Select/Label primitives + RHF + zod + @hookform/resolvers + noValidate idiom + Toaster-in-test-utils pattern + matchMedia polyfill
  - phase: 21-react-frontend-dashboard
    plan: 06
    provides: form-page template + zod v4 default() idiom (seed via useForm defaultValues, not .default() on schema)
provides:
  - frontend/src/pages/social/posts/new.tsx — typed RHF + zod form mirroring PostCreateRequest (brand_kit_slug / platform / intent / topic / cta / image_hint / style_preset). .strict() on the outer schema. z.enum(PLATFORMS) and z.enum(INTENTS) mirror flyer_generator/social/models.py Platform + Intent Literal aliases verbatim (4 platforms + 3 intents). Empty-string optional fields are stripped before POST so the server sees absent => Field(default=None) rather than "". POSTs to /api/v1/social/posts, invalidates queryKeys.jobs(), toasts, and navigates to /social/posts/:job_id on success.
  - frontend/src/pages/social/posts/status.tsx — 20-line wrapper around <JobStatusCard jobId title="Social post" />; documents that validation_report + audit_report are not exposed in v1.
  - frontend/src/pages/social/posts/new.test.tsx — 2 tests (empty brand_kit_slug zod error + valid-submit with default platform/intent captured).
  - frontend/src/components/ui/textarea.tsx — ShadCN-style Textarea primitive. Added this plan for topic + image_hint multi-line inputs. Mirrors the Input primitive's focus-visible / disabled / aria-invalid token chain so FormMessage styling stays consistent.
affects: [21-09-social-campaigns]

# Tech tracking
tech-stack:
  added:
    - "ShadCN Textarea primitive (hand-written to match the existing Input primitive's radix-nova token chain; the radix-nova registry shipping a working Textarea has not been verified and the Input-mirror pattern avoids the registry-empty-stub pitfall documented in plan 21-05)"
  patterns:
    - "Form-page template (mirrors 21-06 flyer creator): .strict() on schema; type FormValues = z.infer<typeof Schema>; useForm with zodResolver + defaultValues seeded for all fields (including empty-string optionals so the field is a controlled input from mount); useMutation with typed {data, error, response} destructure + ApiErrorBody cast; invalidate + toast + navigate on success; noValidate on <form> so zod is the single validation path."
    - "Empty-optional stripping idiom in mutationFn: the form stores '' for unset optional strings (controlled inputs); the mutationFn uses conditional spread (`...(values.cta ? { cta: values.cta } : {})`) to omit empty values from the POST body so the server sees absent => Field(default=None) literally, rather than a '' that the server would accept but which muddles the contract."
    - "openapi-fetch path key is the ABSOLUTE FastAPI path: the generated schema.gen.ts keys paths by /api/v1/social/posts (not /social/posts) because FastAPI bakes the prefix='/api/v1' mount into its OpenAPI doc. The form calls client.POST('/api/v1/social/posts', ...) — same as the 21-06 flyer form's client.POST('/api/v1/flyers', ...). The 21-08 plan sample showed /social/posts; that was a non-absolute-path typo corrected here (Rule 1 bug)."

key-files:
  created:
    - "frontend/src/pages/social/posts/new.test.tsx (85 lines, 2 tests)"
    - "frontend/src/components/ui/textarea.tsx (27 lines, ShadCN-style primitive)"
  modified:
    - "frontend/src/pages/social/posts/new.tsx (was 9-line stub; now 312 lines)"
    - "frontend/src/pages/social/posts/status.tsx (was 9-line stub; now 32 lines)"

key-decisions:
  - "[Rule 1 - Bug] Corrected the plan's client.POST path literal from '/social/posts' to '/api/v1/social/posts'. The openapi-fetch `paths` type is keyed by the absolute FastAPI path (see client.ts's top-of-file comment from plan 21-04). Passing a relative path would be a compile-time type error. This matches the 21-06 pattern (client.POST('/api/v1/flyers', ...)). The test msw handler already uses '/api/v1/social/posts' so no adjustment was needed on the test side."
  - "[Rule 2 - Missing Critical] Stripped empty-string optional fields from the POST body in mutationFn. The controlled-input form always holds '' for unset optional fields (cta, image_hint, style_preset); forwarding {cta: '', ...} to a server that accepts max_length=200 but whose Field(default=None) signals 'absent' is a small but real contract muddling. Fix: conditional spread so only truthy strings land in the body."
  - "[Rule 2 - Missing Critical] Seeded every optional field in defaultValues. RHF's Controller-driven inputs surface an uncontrolled-to-controlled warning if defaultValues is undefined for a field that binds `value={field.value ?? ''}`. Explicit '' keeps every field controlled from mount. Mirrors the 21-06 pattern."
  - "Hand-wrote the Textarea primitive rather than running `shadcn add textarea`. Plan 21-05 documented that the radix-nova ShadCN registry returns empty stubs for several components (e.g. form). The Input primitive already exists in the radix-nova variant; mirroring its className chain (plus field-sizing-content for auto-growing textareas and min-h-[60px] for starter height) yields a visually consistent Textarea without fighting the registry. If the registry gains a real radix-nova Textarea later, the primitive can be replaced — it's a 27-line file with no external API surface beyond {className, ...props}."
  - "2 tests, not 3+, matching the plan's `<behavior>` block and mirroring the 21-06 precedent. The 2 tests cover the two highest-risk branches (slug rejection + successful submit with enum defaults captured). Enum-selection-override branches (user picks twitter instead of linkedin) are typechecked and structurally covered by the `z.enum(PLATFORMS)` / `z.enum(INTENTS)` types but not test-covered — a fair trade against keeping the test suite fast."
  - "Kept the historical 'plan-21-03 stub' mention in the header comment (documenting what this file replaces). The runtime DOM no longer contains the '(stub — plan 21-08 replaces)' placeholder; grep for '(stub' across src/pages/social/posts/ returns 0 matches post-GREEN."
  - "`noValidate` on <form> — not strictly needed (no type='url' or type='email' inputs in this form) but kept for consistency with plans 21-05 / 21-06. Defensive infrastructure if a future field adopts HTML5 constraint validation."

requirements-completed: [FE-07]

# Metrics
duration: ~15min
completed: 2026-04-23
---

# Phase 21 Plan 08: Social Post Creator + Status Page Summary

**Typed social post creation flow end-to-end: /social/posts/new replaces the plan-21-03 stub with a react-hook-form + zod form mirroring PostCreateRequest (.strict() + z.enum() on platform + intent), submits via openapi-fetch to /api/v1/social/posts, toasts, and navigates to /social/posts/:job_id; /social/posts/:id is a 20-line wrapper around <JobStatusCard/> so polling + 5-state rendering come free from plan 21-04. Added the ShadCN-style Textarea primitive needed by the form. 2 new Vitest tests land (total 18 across the suite, up from 16).**

## Performance

- **Duration:** ~15 min (worktree install + baseline + RED/GREEN cycle + verify + SUMMARY)
- **Started:** 2026-04-23T14:00:00Z (approx)
- **Completed:** 2026-04-23T14:14:00Z (approx)
- **Tasks:** 1 (TDD — 2 commits: RED + GREEN)
- **Files created:** 2 (`src/pages/social/posts/new.test.tsx` + `src/components/ui/textarea.tsx`)
- **Files modified:** 2 (`src/pages/social/posts/new.tsx` + `src/pages/social/posts/status.tsx` — both stub-to-real replacements)

## Accomplishments

- **Stubs replaced.** `src/pages/social/posts/{new,status}.tsx` no longer contain the `(stub — plan 21-08 replaces)` placeholder. Grep for `(stub` in `src/pages/social/posts/` returns 0 matches after GREEN.
- **Typed form with all 7 PostCreateRequest fields.** brand_kit_slug (required, SLUG regex + 1..64) + platform Select (4 enum) + intent Select (3 enum) + topic Textarea (1..400) + cta Input (optional, ≤200) + image_hint Textarea (optional, ≤400) + style_preset Input (optional, ≤64). All mirror `flyer_generator/api/schemas/social.py::PostCreateRequest` verbatim.
- **Status page is 20 lines.** Backlink + heading + `<JobStatusCard jobId={id} title="Social post" />` + a note that validation_report + audit_report are not in the v1 API.
- **2 new tests land.** `pnpm test --run` reports 18/18 across 9 files (16 prior + 2 new). `pnpm typecheck` exits 0. `pnpm build` emits 75.66 KB CSS + 624.16 KB JS.
- **Textarea primitive added.** Used by the topic + image_hint fields. Mirrors the Input primitive's Tailwind token chain so FormMessage error styling is consistent.

## Task Commits

1. **Task 1 RED:** `4118b60` — test: add failing tests for social post creator + Textarea primitive.
2. **Task 1 GREEN:** `7a8c7b2` — feat: ship social post creator + status page; both tests pass.

TDD gate compliance: `test(21-08)` commit precedes `feat(21-08)` commit. Clear RED → GREEN sequence in `git log`. No REFACTOR commit was needed — the GREEN code is already idiomatic.

_Orchestrator adds the metadata commit after all Wave 4 agents merge._

## Files Created/Modified

**Created:**
- `frontend/src/pages/social/posts/new.test.tsx` — 2 tests (empty brand_kit_slug zod error + valid-submit preserves defaults)
- `frontend/src/components/ui/textarea.tsx` — ShadCN-style Textarea primitive

**Modified:**
- `frontend/src/pages/social/posts/new.tsx` — plan-21-03 stub replaced with 312-line form page
- `frontend/src/pages/social/posts/status.tsx` — plan-21-03 stub replaced with 32-line wrapper

## Decisions Made

- **Absolute openapi-fetch path.** The plan's sample code had `client.POST("/social/posts", ...)`. The generated `paths` type is keyed by `/api/v1/social/posts` because FastAPI's `app.include_router(router, prefix="/api/v1")` bakes the prefix into every OpenAPI path (documented in the repo's `api/client.ts` header comment as a 21-04 finding). The implementation uses `/api/v1/social/posts` to match the generated types. This matches the 21-06 flyer form's `/api/v1/flyers` call. See "Deviations" Rule 1.
- **Strip empty-string optional fields.** The controlled form holds `""` for unset `cta` / `image_hint` / `style_preset`. The mutationFn uses `...(values.cta ? { cta: values.cta } : {})` so only truthy strings land in the body. Server-side this reads as `Field(default=None)` instead of `""`, which matches the domain semantics (absent vs. empty-user-input). See "Deviations" Rule 2.
- **Seed every field in `defaultValues`.** Controlled inputs use `{...field}` (for required fields) or `{...field} value={field.value ?? ""}` (for optional fields). Explicit `defaultValues` for `cta` / `image_hint` / `style_preset` (as `""`) avoids the uncontrolled-to-controlled React warning at first mount. Mirrors the 21-06 flyer form pattern.
- **Hand-wrote Textarea primitive.** The radix-nova ShadCN registry has known empty-stub issues (plan 21-05 documented this for `form`). The Input primitive already exists in radix-nova; mirroring its Tailwind token chain (focus-visible / disabled / aria-invalid) plus `field-sizing-content` for auto-growing + `min-h-[60px]` for starter height gives a visually consistent Textarea without registry friction. 27 lines, no dependencies beyond `cn()`.
- **2 tests, not 3+.** Mirrors the 21-06 precedent. The 2 tests cover the highest-risk branches (slug rejection + successful submit with enum defaults captured). Enum-override branches (user picks "twitter" instead of "linkedin") are typechecked by `z.enum(PLATFORMS)` / `z.enum(INTENTS)` but not test-covered — a fair trade against test-suite speed.
- **`noValidate` on `<form>`.** No HTML5-validated input types are present (no `type="url"` / `type="email"`), so strictly optional here. Kept for consistency with plans 21-05 and 21-06 and as future-proofing.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan used non-absolute openapi-fetch path literal**
- **Found during:** Task 1 GREEN (writing `new.tsx`).
- **Issue:** The plan's sample code called `client.POST("/social/posts", ...)`. The generated `schema.gen.ts` keys paths by FastAPI's absolute path (`/api/v1/social/posts`) because `app.include_router(router, prefix="/api/v1")` bakes the prefix into the OpenAPI doc. Non-absolute path would be a compile-time TS error ("Argument of type '/social/posts' is not assignable..."). This is the same correction the 21-06 flyer page made (`/api/v1/flyers` not `/flyers`).
- **Fix:** Used `/api/v1/social/posts`. Matches the client.ts header comment and the 21-06 precedent.
- **Files modified:** `frontend/src/pages/social/posts/new.tsx`.
- **Verification:** `pnpm typecheck` exits 0; the second test's msw handler (which already uses `/api/v1/social/posts`) intercepts the request correctly.
- **Committed in:** `7a8c7b2` (Task 1 GREEN).

**2. [Rule 2 - Missing Critical] Empty-string optional fields forwarded to server**
- **Found during:** Task 1 GREEN (form design review before first test run).
- **Issue:** Without intervention, the form POSTs `{cta: "", image_hint: "", style_preset: "", ...}` when the user leaves those optional fields blank. The Pydantic server accepts `max_length=200` including `""`, but that's semantically wrong — the Pydantic contract is `Field(default=None)` which signals "absent". Forwarding `""` breaks that contract and would produce misleading audit-report entries downstream (e.g. a `style_preset: ""` in a stored PostRecord).
- **Fix:** Conditional spread in the mutationFn body construction — `...(values.cta ? { cta: values.cta } : {})` for each optional. Empty strings don't land in the JSON body.
- **Files modified:** `frontend/src/pages/social/posts/new.tsx`.
- **Verification:** Second test (valid-submit) passes with the `captured` object showing the 4 required fields and omitting the 3 empty optionals. `pnpm typecheck` exits 0 — PostCreateRequestBody accepts a subset of optional keys per openapi-fetch's typing.
- **Committed in:** `7a8c7b2` (Task 1 GREEN).

**3. [Rule 2 - Missing Critical] Seeded optional fields in defaultValues**
- **Found during:** Task 1 GREEN (form mount in jsdom).
- **Issue:** The controlled inputs use `value={field.value ?? ""}` for optional fields. RHF's `useForm` without explicit `defaultValues` starts those fields as `undefined`, so the first render shows the input as an uncontrolled component, then React warns when `field.value` becomes `""` on first keystroke ("A component is changing an uncontrolled input to be controlled").
- **Fix:** Added `cta: ""`, `image_hint: ""`, `style_preset: ""` to useForm's defaultValues. Matches the 21-06 flyer pattern.
- **Files modified:** `frontend/src/pages/social/posts/new.tsx`.
- **Verification:** No React warnings in the test output.
- **Committed in:** `7a8c7b2` (Task 1 GREEN).

**4. [Rule 3 - Blocking] No Textarea primitive in the tree**
- **Found during:** Task 1 RED (writing the test + primitive together).
- **Issue:** The plan imports `@/components/ui/textarea` for the topic + image_hint fields. No `textarea.tsx` exists in `src/components/ui/`. Running `npx shadcn add textarea` against the project's radix-nova registry has a known risk of returning an empty stub (plan 21-05 documented this for `form`).
- **Fix:** Hand-wrote a 27-line Textarea primitive mirroring the existing Input primitive's Tailwind token chain (`focus-visible:ring-3`, `aria-invalid:border-destructive`, etc.) plus `field-sizing-content` for auto-growing + `min-h-[60px]` for starter height. Exports `{ Textarea }` with `React.ComponentProps<"textarea">` signature so `{...field}` from RHF's FormField spreads cleanly.
- **Files created:** `frontend/src/components/ui/textarea.tsx`.
- **Verification:** Both tests pass; `getByLabelText(/topic/i)` finds the textarea via the FormLabel ↔ FormControl ↔ id linkage; `pnpm typecheck` exits 0; the rendered page looks visually consistent with the Input primitive.
- **Committed in:** `4118b60` (Task 1 RED, same commit as the failing tests).

---

**Total deviations:** 4 auto-fixed (1 Rule 1 bug, 2 Rule 2 missing-critical, 1 Rule 3 blocking). No Rule 4 architectural. All plan acceptance criteria still met.
**Impact on plan:** Fix 1 is a typo correction (plan's sample vs. real generated types). Fixes 2 + 3 tighten the form/server contract without behavior change for the happy path. Fix 4 is net-new infrastructure (Textarea primitive) required by the plan.

## Issues Encountered

- **Worktree-vs-main-tree path confusion at startup.** The first file writes went to `/home/hoyack/work/autocreative/frontend/...` (main tree) rather than `/home/hoyack/work/autocreative/.claude/worktrees/agent-a8cc8399/frontend/...` (worktree). Recovered by `rm`-ing the misplaced files + writing to the worktree path. Not a plan deviation — a tooling-cwd interaction issue. Worktree frontend had no `node_modules` until `pnpm install --frozen-lockfile` was run first.
- **ShadCN Select's role-based label association in Testing Library.** `getByLabelText(/platform/i)` is NOT used in this plan's tests — the two tests query `getByLabelText(/brand kit slug/i)` and `getByLabelText(/topic/i)` (Input + Textarea, both with normal `<label htmlFor>` wiring via FormField). The Select primitive's aria-labelledby chain was not exercised by either test, so no Testing Library fragility surfaced. If a future test needs to change the Select value, `userEvent.click(screen.getByRole('combobox', { name: /platform/i }))` followed by `userEvent.click(screen.getByRole('option', { name: /twitter/i }))` is the recommended pattern (per Radix Select's accessibility tree).

## User Setup Required

None. The page+test pipeline runs entirely offline via msw mocks; no Phase 20 backend needed at test time.

## Output spec answers

Per the plan's `<output>` block:

- **Whether ShadCN Select's role-based label association in Testing Library worked first try:** NOT EXERCISED. Neither of the 2 required tests needed to interact with the Select primitive — both use the defaults (linkedin / announcement) and assert they land in the captured POST body. The slug rejection test targets the Input; the valid-submit test targets Input + Textarea + Button. So the Select's aria-labelledby chain was not put to the test here. The DOM-structural claim (getByLabelText will work on Select) remains unverified by this plan's tests; a future plan that test-switches the Select value will verify it. If it turns out to be fragile, the `getByRole('combobox', { name: ... })` + `getByRole('option')` pattern is the escape hatch.
- **Total Vitest test count:** 18 across 9 files (16 before this plan + 2 new in `src/pages/social/posts/new.test.tsx`). Duration ~6 s.

## Next Phase Readiness

- **Ready for plan 21-09 (campaigns):** This plan's `new.tsx` is the form-page template for 21-09 with only 2 adjustments — add a `platforms` multi-select (checkbox group or ShadCN multi-select) instead of the single `platform` Select, and swap the POST path to `/api/v1/social/campaigns`. The rest of the skeleton (zodResolver, .strict(), useMutation with invalidate + toast + navigate, empty-optional stripping, noValidate) carries over verbatim.
- **Ready for plan 21-07 (brochures):** This plan adds the Textarea primitive that the brochure form's `body_paragraphs[]` items will want. 21-07 should import `@/components/ui/textarea` — no CLI install needed.
- **Pattern to propagate:** The empty-optional-stripping idiom in mutationFn (`...(values.x ? { x: values.x } : {})`) should be applied in every form page where optional fields can be user-empty but the server's Pydantic default is `None`. 21-09's `cta` and `style_preset` (same as 21-08) and 21-07's optional `brand_kit_slug` all fit this shape.

## Known Stubs

None from this plan. The 2 stub pages from plan 21-03 (`social/posts/new.tsx`, `social/posts/status.tsx`) are both replaced with real implementations.

## Self-Check

**Created files exist:**
- `frontend/src/pages/social/posts/new.test.tsx` — FOUND (85 lines, 2 tests)
- `frontend/src/components/ui/textarea.tsx` — FOUND (27 lines)

**Modified files replaced stubs:**
- `frontend/src/pages/social/posts/new.tsx` — grep for `(stub` returns 0 matches (placeholder text gone)
- `frontend/src/pages/social/posts/status.tsx` — grep for `(stub` returns 0 matches

**Commits exist:**
- `4118b60` (Task 1 RED: failing tests + Textarea primitive) — FOUND
- `7a8c7b2` (Task 1 GREEN: form + status page) — FOUND

**Verify runs:**
- `pnpm typecheck` → exits 0 (clean)
- `pnpm test --run` → 18 passed / 9 files / Duration ~6.1 s
- `pnpm build` → emits 75.66 KB CSS + 624.16 KB JS; exits 0
- `grep -c ".strict()" src/pages/social/posts/new.tsx` → 4 (1 schema + 3 comments; plan required >=1 on PostFormSchema)
- PLATFORMS all 4 present (`linkedin`, `twitter`, `instagram`, `facebook`) — verified line-by-line via Grep
- INTENTS all 3 present (`announcement`, `value-prop`, `testimonial`) — verified line-by-line via Grep
- `/api/v1/social/posts` path present in `new.tsx` (2 occurrences)
- `JobStatusCard jobId={id}` present in `status.tsx` (1 occurrence)
- No `dangerouslySetInnerHTML` in either file

## TDD Gate Compliance

Task 1 was TDD. Git log shows the required sequence:
- Task 1: `4118b60` (test: RED) → `7a8c7b2` (feat: GREEN). Both commits present.

No REFACTOR commits were needed; GREEN code is already idiomatic.

## Self-Check: PASSED

---
*Phase: 21-react-frontend-dashboard*
*Completed: 2026-04-23*
