---
phase: 21-react-frontend-dashboard
plan: 09
subsystem: ui
tags: [frontend, social-campaigns, form-page, rhf, zod, tanstack-query, shadcn-checkbox, radix-checkbox, job-polling, tdd, resize-observer-polyfill]

# Dependency graph
requires:
  - phase: 21-react-frontend-dashboard
    plan: 02
    provides: openapi-fetch client + CampaignCreateRequestBody alias + JobCreated aliases + queryKeys.jobs() + openapi.snapshot.json (already contains /api/v1/social/campaigns)
  - phase: 21-react-frontend-dashboard
    plan: 03
    provides: plan-21-03 stub pages at frontend/src/pages/social/campaigns/{new,status}.tsx (REPLACED here) and /social/campaigns/new + /social/campaigns/:id routes already wired in routes.tsx
  - phase: 21-react-frontend-dashboard
    plan: 04
    provides: <JobStatusCard/> array-result_ref branch + useJob hook + RenderPreview + vitest/msw harness + <Toaster/> position convention
  - phase: 21-react-frontend-dashboard
    plan: 05
    provides: ShadCN Form/Input/Select/Label primitives + RHF + zod + @hookform/resolvers + noValidate idiom + Toaster-in-test-utils pattern + matchMedia polyfill
  - phase: 21-react-frontend-dashboard
    plan: 06
    provides: form-page template + zod v4 default() idiom (seed via useForm defaultValues, not .default() on schema)
  - phase: 21-react-frontend-dashboard
    plan: 08
    provides: Textarea primitive + empty-optional-strip idiom + PostCreateRequest form-page structure (reused verbatim with 1 swap: single Select -> Checkbox group)
provides:
  - frontend/src/pages/social/campaigns/new.tsx — typed RHF + zod form mirroring CampaignCreateRequest. .strict() on the outer schema. `platforms: z.array(z.enum(PLATFORMS)).min(1, "select at least one platform").max(10)` is the array branch end-to-end. Submits POST /api/v1/social/campaigns, toasts, invalidates queryKeys.jobs(), navigates to /social/campaigns/:job_id on success. Empty-string optional fields (cta, style_preset) stripped before POST so the server sees absent => Field(default=None).
  - frontend/src/pages/social/campaigns/status.tsx — 35-line wrapper around <JobStatusCard jobId title="Campaign"/>. Exercises the Array.isArray(result_ref) branch of JobStatusCard (plan 21-04) — per-platform grid is rendered for free.
  - frontend/src/pages/social/campaigns/new.test.tsx — 2 tests (empty-platforms zod error + valid-submit with selected ["linkedin", "twitter"] captured by msw).
  - frontend/src/components/ui/checkbox.tsx — hand-rolled ShadCN-style Checkbox primitive (radix-nova). Wraps @radix-ui/react-checkbox via the `radix-ui` meta-package (same import idiom as label.tsx). Mirrors Input / Textarea token chain so FormMessage styling stays consistent. 47 lines.
  - frontend/src/test/setup.ts — adds a no-op ResizeObserver polyfill (Rule 3 blocking) so tests that render pages containing a ShadCN Checkbox don't crash at mount.
affects: [21-10-jobs-list, 21-11-renders-gallery]

# Tech tracking
tech-stack:
  added:
    - "ShadCN Checkbox primitive (hand-written; wraps the Checkbox namespace re-exported by the radix-ui meta package — same idiom as the existing label.tsx. We intentionally did NOT run `npx shadcn@latest add checkbox` per the 21-05 / 21-08 registry-empty-stub decision; the Input-mirror pattern is known-working)"
  patterns:
    - "Array-valued form fields wire through FormField (which IS Controller + FormFieldContext.Provider), NOT raw Controller. The plan's sample used Controller + FormItem + FormLabel which throws `useFormField should be used within <FormField>` at mount because FormLabel needs FormFieldContext that Controller alone doesn't populate. Any future multi-value form (array of enum, array of object, etc.) should follow this pattern if it wants FormLabel + FormMessage semantics."
  - "ResizeObserver polyfill for tests: jsdom does not implement ResizeObserver; @radix-ui/react-use-size (a transitive dep of @radix-ui/react-checkbox) calls `new ResizeObserver(...)` at mount. A no-op class in setup.ts (`observe/unobserve/disconnect`) is enough for Radix's surface area. This mirrors the existing 21-05 matchMedia polyfill pattern."
    - "Canonical enum order on array submit: when an array-valued field is driven by a Set-based toggle, sort the final array into the canonical enum declaration order (`PLATFORMS.filter((x) => next.has(x))`) before calling field.onChange. This means the submitted body is stable regardless of click order, which matches the plan's acceptance criterion `platforms: [\"linkedin\", \"twitter\"]` exactly."
    - "Multi-platform test pattern: userEvent.click(screen.getByText('linkedin')) works because the Checkbox is wrapped in a <label> with text content. The HTML <label> click contract delegates the event to the control — no need for getByRole('checkbox', {name: 'linkedin'}) or other higher-friction selectors."

key-files:
  created:
    - "frontend/src/pages/social/campaigns/new.test.tsx (94 lines, 2 tests)"
    - "frontend/src/components/ui/checkbox.tsx (47 lines, hand-rolled ShadCN-style primitive)"
  modified:
    - "frontend/src/pages/social/campaigns/new.tsx (was 9-line stub; now 337 lines)"
    - "frontend/src/pages/social/campaigns/status.tsx (was 9-line stub; now 35 lines)"
    - "frontend/src/test/setup.ts (16 lines added — no-op ResizeObserver polyfill)"

key-decisions:
  - "[Rule 1 - Bug] Used FormField (not raw Controller) for the platforms checkbox group. The plan's sample code called `<Controller ...>` then inside the render prop wrapped the grid in `<FormItem><FormLabel>Platforms</FormLabel>...</FormItem>`. FormLabel calls useFormField which requires FormFieldContext — Controller alone doesn't provide it. First test run threw `useFormField should be used within <FormField>` on mount. Fix: swap Controller for FormField (which is literally `<FormFieldContext.Provider value={{name}}><Controller {...props}/></FormFieldContext.Provider>` per form.tsx:29-40). Semantics identical; FormLabel / FormMessage now work. Net behavior change: none — both render the same useForm state; FormField just adds the missing context provider."
  - "[Rule 3 - Blocking] Added a no-op ResizeObserver polyfill to setup.ts. jsdom doesn't implement ResizeObserver; @radix-ui/react-use-size (transitive of @radix-ui/react-checkbox, pulled via the radix-ui meta pkg) calls `new ResizeObserver(...)` at mount. Without the polyfill, both tests failed with `ReferenceError: ResizeObserver is not defined` at React commit. Fix: a 4-line class with `observe/unobserve/disconnect` no-ops. Net behavior change: zero — production browsers provide ResizeObserver natively; the polyfill only activates in jsdom where `typeof globalThis.ResizeObserver === 'undefined'`. Same pattern as the existing matchMedia polyfill for sonner."
  - "Hand-rolled the Checkbox primitive rather than running `npx shadcn@latest add checkbox`. Plans 21-05 / 21-08 documented that the radix-nova ShadCN registry is known to return empty stubs for several components. The existing Label primitive uses `import { Label as LabelPrimitive } from 'radix-ui'` — same meta-package entrypoint that re-exports Checkbox. Mirroring Input's Tailwind token chain (focus-visible / disabled / aria-invalid) + adding the `data-[state=checked]:bg-primary` pair gives a visually consistent Checkbox with zero registry risk. 47 lines, one icon dep (`Check` from lucide-react already in the tree)."
  - "Canonical PLATFORMS order on submit. The plan's sample computed `Array.from(next)` from a Set, which preserves insertion order (click order). Submitting in click order works for the test (the test clicks linkedin then twitter, so Array.from gives [linkedin, twitter]), but if a user clicks facebook-then-linkedin the body order is [facebook, linkedin] — fine for correctness but less predictable. Fix: `PLATFORMS.filter((x) => next.has(x))` — the final array is always in the enum declaration order. Test still passes (linkedin comes before twitter in PLATFORMS). Body contract is now order-stable regardless of click sequence."
  - "Empty-optional-strip idiom reused from 21-08. `cta` and `style_preset` are optional `string | null` on the server; the form holds `''` for unset controlled inputs; the mutationFn uses `...(values.cta ? { cta: values.cta } : {})` so empty strings don't land in the body. Matches the 21-08 decision verbatim. Required fields (brand_kit_slug / platforms / intent / topic) are always forwarded."
  - "2 tests, matching the plan's `<behavior>` block and mirroring the 21-06 / 21-08 precedent. The 2 tests cover the two highest-value branches for this page: (a) the array's min(1) rejection — unique to campaigns vs. single-platform posts, and (b) happy-path submit with the serialized array captured via msw. Intent override, cta/style_preset population, and platforms.max(10) are typechecked but not test-covered — a fair trade against test-suite speed."
  - "noValidate on <form>. No HTML5-validated input types present (no type='url' / type='email'). Kept for consistency with 21-05 / 21-06 / 21-08 and as future-proofing. Signals zod is the single validation path."

requirements-completed: [FE-08]

# Metrics
duration: ~10min
completed: 2026-04-23
---

# Phase 21 Plan 09: Campaign Creator + Status Page Summary

**Typed social campaign creation flow end-to-end: /social/campaigns/new replaces the plan-21-03 stub with a react-hook-form + zod form mirroring CampaignCreateRequest (.strict() + `platforms: z.array(z.enum).min(1).max(10)`). Checkbox group drives the multi-platform array through FormField (not raw Controller — FormLabel needs FormFieldContext). Submits to /api/v1/social/campaigns, toasts, and navigates to /social/campaigns/:job_id; /social/campaigns/:id is a 35-line wrapper around <JobStatusCard/> which exercises the Array.isArray(result_ref) per-platform grid branch implemented in plan 21-04. Added a hand-rolled ShadCN Checkbox primitive (radix-nova, wraps @radix-ui/react-checkbox via the radix-ui meta-package) and a no-op ResizeObserver polyfill for jsdom. 2 new Vitest tests land (total 20 across 10 files, up from 18).**

## Performance

- **Duration:** ~10 min (worktree install + baseline + RED/GREEN cycle + 2 inline Rule-N fixes + SUMMARY)
- **Tasks:** 1 (TDD — 2 commits: RED + GREEN)
- **Files created:** 2 (`src/pages/social/campaigns/new.test.tsx` + `src/components/ui/checkbox.tsx`)
- **Files modified:** 3 (`src/pages/social/campaigns/new.tsx`, `src/pages/social/campaigns/status.tsx`, `src/test/setup.ts`)
- **Commits:** 2 (`df47ad7` RED + `5c41901` GREEN)

## Accomplishments

- **Stubs replaced.** `src/pages/social/campaigns/{new,status}.tsx` no longer contain the `(stub — plan 21-09 replaces)` placeholder. `grep -rn "stub — plan 21-09"` in the directory returns 0 matches post-GREEN.
- **Typed form with all 6 CampaignCreateRequest fields.** brand_kit_slug (required, SLUG regex + 1..64) + platforms Checkbox group (required, 1..10, z.array(z.enum(PLATFORMS))) + intent Select (3 enum) + topic Textarea (1..400) + cta Input (optional, ≤200) + style_preset Input (optional, ≤64). All mirror `flyer_generator/api/schemas/social.py::CampaignCreateRequest` verbatim.
- **Checkbox group wired correctly.** Platforms field uses FormField (Controller + FormFieldContext) so FormLabel + FormMessage resolve. Canonical enum order is preserved on submit so the body is order-stable regardless of click sequence.
- **Status page is 35 lines.** Backlink + heading + `<JobStatusCard jobId={id} title="Campaign" />`. The array-result_ref branch of JobStatusCard (plan 21-04) renders the per-platform grid — no special-casing needed here.
- **2 new tests land.** `pnpm test --run` reports 20/20 across 10 files (18 prior + 2 new). `pnpm typecheck` exits 0. `pnpm build` emits 76.42 KB CSS + 631.92 KB JS (+7.76 KB JS over pre-plan — the Checkbox + form code).
- **Checkbox primitive added.** 47-line ShadCN-style radix-nova primitive wrapping the `Checkbox` namespace from the `radix-ui` meta package. Mirrors Input's token chain for consistent FormMessage styling.
- **ResizeObserver polyfill added.** 16-line no-op class in setup.ts so any future test that mounts a Radix Checkbox descendant doesn't crash in jsdom.

## Task Commits

1. **Task 1 RED:** `df47ad7` — test: add failing tests for campaign creator + Checkbox primitive.
2. **Task 1 GREEN:** `5c41901` — feat: ship campaign creator + status page; both tests pass.

TDD gate compliance: `test(21-09)` commit precedes `feat(21-09)` commit. Clear RED → GREEN sequence in `git log`. No REFACTOR commit was needed — the GREEN code is already idiomatic.

_Orchestrator adds the metadata commit after all Wave 4 agents merge._

## Files Created/Modified

**Created:**
- `frontend/src/pages/social/campaigns/new.test.tsx` — 2 tests (empty-platforms zod error + valid-submit with array captured)
- `frontend/src/components/ui/checkbox.tsx` — hand-rolled ShadCN-style Checkbox primitive

**Modified:**
- `frontend/src/pages/social/campaigns/new.tsx` — plan-21-03 stub replaced with 337-line form page
- `frontend/src/pages/social/campaigns/status.tsx` — plan-21-03 stub replaced with 35-line wrapper
- `frontend/src/test/setup.ts` — ResizeObserver no-op polyfill added (16 lines)

## Decisions Made

- **Used FormField (not raw Controller) for the platforms checkbox group.** See Deviations Rule 1. The plan's sample used Controller + FormLabel, which throws `useFormField should be used within <FormField>` because FormLabel requires FormFieldContext. FormField is the exact combinator needed (Controller + context provider in one).
- **Canonical PLATFORMS order on array submit.** `PLATFORMS.filter((x) => next.has(x))` instead of `Array.from(next)`. Body is order-stable regardless of click sequence. The test still passes (linkedin precedes twitter in PLATFORMS declaration order).
- **Hand-rolled Checkbox primitive.** Plans 21-05 / 21-08 documented the radix-nova registry's empty-stub risk. The existing label.tsx uses `import { Label as LabelPrimitive } from "radix-ui"` — same meta-package entrypoint that re-exports Checkbox. Mirrored Input's Tailwind token chain (focus-visible / disabled / aria-invalid) + added `data-[state=checked]:bg-primary` for the checked variant. 47 lines, one icon import (lucide-react's Check already in the tree).
- **No-op ResizeObserver polyfill.** See Deviations Rule 3. jsdom doesn't implement ResizeObserver; @radix-ui/react-use-size (transitive of @radix-ui/react-checkbox) calls `new ResizeObserver(...)` at mount. Same pattern as the existing matchMedia polyfill for sonner.
- **Empty-optional-strip idiom** carried over from 21-08 verbatim. `cta` / `style_preset` empty strings are stripped from the body so the server sees absent => Field(default=None) rather than `""`.
- **2 tests, matching the plan's `<behavior>` block.** Empty-platforms rejection (the unique-to-campaigns branch) + valid-submit with array captured. Intent override / max(10) / cta-style_preset population are typechecked but not test-covered.
- **noValidate on `<form>`.** No HTML5-validated input types present. Kept for consistency with 21-05 / 21-06 / 21-08.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan's Controller + FormLabel combo throws `useFormField should be used within <FormField>`**
- **Found during:** Task 1 GREEN first test run (both tests failed on mount with the `useFormField` error from form.tsx:48).
- **Issue:** The plan's sample code used `<Controller control={form.control} name="platforms" render={({field, fieldState}) => (<FormItem><FormLabel>Platforms</FormLabel>...`. `FormLabel` calls `useFormField`, which reads `FormFieldContext` — but raw `Controller` does NOT populate that context (only the ShadCN `FormField` wrapper does; see form.tsx:29-40 where `FormField` is literally `<FormFieldContext.Provider><Controller/></...>`). Every mount of the page crashed before the test body could run.
- **Fix:** Dropped the `Controller` import; swapped `<Controller .../>` for `<FormField .../>`. Props are identical (both accept `control` / `name` / `render`). FormLabel + FormMessage now resolve. Runtime DOM is identical to what the plan intended.
- **Files modified:** `frontend/src/pages/social/campaigns/new.tsx`.
- **Verification:** `pnpm test --run src/pages/social/campaigns/` → 2 pass (after Rule 3 ResizeObserver fix below). `pnpm typecheck` exits 0.
- **Committed in:** `5c41901` (Task 1 GREEN).

**2. [Rule 3 - Blocking] jsdom missing ResizeObserver — Radix Checkbox crashes at mount**
- **Found during:** Task 1 GREEN second test run (after Rule 1 fix, tests then failed with `ReferenceError: ResizeObserver is not defined` in @radix-ui/react-use-size/src/use-size.tsx:14 during React's commit phase).
- **Issue:** @radix-ui/react-checkbox pulls @radix-ui/react-use-size, which constructs `new ResizeObserver(...)` at mount to observe the indicator's size. jsdom doesn't implement ResizeObserver. Any test that renders a ShadCN Checkbox descendant crashes — both tests here mount the campaign form which contains 4 Checkboxes.
- **Fix:** Added a 16-line conditional polyfill to `src/test/setup.ts` that installs a no-op class with `observe`, `unobserve`, and `disconnect` no-op methods onto `globalThis.ResizeObserver` only when it's undefined. Same pattern as the existing matchMedia polyfill for sonner (21-05).
- **Files modified:** `frontend/src/test/setup.ts`.
- **Verification:** Both tests now pass. Full suite (20/20 across 10 files) still passes — the polyfill doesn't affect any existing test because it's a no-op in jsdom where ResizeObserver was already undefined.
- **Committed in:** `5c41901` (Task 1 GREEN, same commit as Rule 1 fix).

**3. [Rule 2 - Missing Critical] Canonical enum order on array submit**
- **Found during:** Form design review before first test run.
- **Issue:** The plan's sample used `Array.from(next)` to convert the Set of checked platforms to an array. Set preserves insertion order (click order), so clicking facebook-then-linkedin gives `["facebook", "linkedin"]` while clicking linkedin-then-facebook gives `["linkedin", "facebook"]`. Both pass Pydantic validation, but the body contract is click-order-dependent which is a hidden surprise for downstream consumers (e.g. audit logs).
- **Fix:** `PLATFORMS.filter((x) => next.has(x))` — the final array is always in enum declaration order regardless of click sequence. Stable, predictable, matches the plan's acceptance criterion `platforms: ["linkedin", "twitter"]` exactly regardless of user interaction order.
- **Files modified:** `frontend/src/pages/social/campaigns/new.tsx`.
- **Verification:** Both tests pass; the valid-submit test's `expect(captured!.platforms).toEqual(["linkedin", "twitter"])` matches regardless of whether the test clicks linkedin-then-twitter or twitter-then-linkedin.
- **Committed in:** `5c41901` (Task 1 GREEN, same commit).

---

**Total deviations:** 3 auto-fixed (1 Rule 1 bug, 1 Rule 2 missing-critical, 1 Rule 3 blocking). No Rule 4 architectural. All plan acceptance criteria still met.
**Impact on plan:** Fix 1 is a plan-sample correction (Controller → FormField). Fix 2 is test-infrastructure (no production impact). Fix 3 tightens body contract with zero behavior change for happy-path click sequences.

## Issues Encountered

- **`useFormField should be used within <FormField>` on mount.** Surfaced immediately on first GREEN test run. The plan's sample code paired raw Controller with FormLabel, but FormLabel reads a context that only the ShadCN FormField combinator populates. Future plans using multi-value RHF fields should use FormField, not raw Controller, if they want FormLabel / FormMessage semantics. Deviation Rule 1 documents this.
- **`ReferenceError: ResizeObserver is not defined`.** Surfaced after the Rule-1 fix unblocked mount. @radix-ui/react-use-size wants ResizeObserver at commit time. jsdom doesn't provide it. A 4-line no-op class is sufficient — the same pattern that matchMedia used in 21-05. Any future test that mounts a Radix component depending on ResizeObserver (dropdown menu, popover, tooltip with collision detection, etc.) will now Just Work because the polyfill is in setup.ts.
- **Registry-empty-stub risk avoided by hand-writing Checkbox.** Plans 21-05 / 21-08 documented that `npx shadcn add <component>` against the radix-nova registry has returned empty stubs for `form` and was expected to for `textarea`. Hand-writing the Checkbox primitive (47 lines, same idiom as the existing Label primitive) avoided that risk entirely. If the registry gains a real radix-nova Checkbox later, the primitive can be replaced — its external API is {className, ...props} passed through to @radix-ui/react-checkbox's Root.

## User Setup Required

None. The page+test pipeline runs entirely offline via msw mocks; no Phase 20 backend needed at test time. Runtime (dev server) usage requires the Phase 20 backend on :8000 for the POST /api/v1/social/campaigns to actually enqueue a job — unchanged from any previous plan.

## Output spec answers

Per the plan's `<output>` block:

- **Whether Testing Library's `userEvent.click` on `<label><Checkbox/></label>` worked first try (label-association is fragile):** YES, label-association worked on the first attempt. `userEvent.click(screen.getByText("linkedin"))` successfully toggled the wrapped Checkbox in both test runs (pre- and post-polyfill). The HTML `<label>` click contract delegates to the enclosed `<button role="checkbox">` which Radix Checkbox renders, and Testing Library's user-event walks the DOM tree to find the associated control. No `getByRole('checkbox', { name: 'linkedin' })` fallback was needed. The only fragility here was the Radix mount-time ResizeObserver call, which is orthogonal to label association.
- **Total Vitest test count:** 20 across 10 files (18 before this plan + 2 new in `src/pages/social/campaigns/new.test.tsx`). Duration ~6.1 s. Plan's ≥17 acceptance threshold exceeded.

## Next Phase Readiness

- **Ready for plan 21-10 (jobs list) and 21-11 (renders gallery):** Both plans will mount pages that likely use Radix descendants (Table, Dialog, Tooltip) — any of which may internally use ResizeObserver. The polyfill is now in place, so those plans won't re-debug the same class of issue.
- **Pattern for multi-value RHF fields (array / nested object):** Use FormField, not raw Controller. The 21-07 brochure creator's `content.sections[]` nested-array form will follow this pattern if it wants FormLabel semantics on the section group. Documented in the tech-stack.patterns field above.
- **Canonical-order idiom** applies to any future form with a Set-based toggle (tag picker, role multiselect, etc.). `ENUM.filter((x) => next.has(x))` is the cleanest way to produce an order-stable array from click-order Set state.
- **JobStatusCard array branch proven end-to-end.** Plan 21-04 implemented it; this plan exercises it. Any future status page that wants a per-result grid (e.g. a batch flyer generator that produces N variants) can reuse JobStatusCard without modification.

## Known Stubs

None from this plan. The 2 stub pages from plan 21-03 (`social/campaigns/new.tsx`, `social/campaigns/status.tsx`) are both replaced with real implementations.

## Self-Check

**Created files exist:**
- `frontend/src/pages/social/campaigns/new.test.tsx` — FOUND (94 lines, 2 tests)
- `frontend/src/components/ui/checkbox.tsx` — FOUND (47 lines)

**Modified files replaced stubs:**
- `frontend/src/pages/social/campaigns/new.tsx` — `grep -n "stub — plan 21-09"` returns 0 matches (placeholder text gone); file is 337 lines
- `frontend/src/pages/social/campaigns/status.tsx` — `grep -n "stub — plan 21-09"` returns 0 matches; file is 35 lines
- `frontend/src/test/setup.ts` — grows from 47 lines to 63 lines with the ResizeObserver polyfill

**Commits exist:**
- `df47ad7` (Task 1 RED: failing tests + Checkbox primitive) — FOUND in git log
- `5c41901` (Task 1 GREEN: form + status page + ResizeObserver polyfill) — FOUND in git log

**Verify runs (post-GREEN, from worktree frontend/):**
- `pnpm typecheck` → exits 0 (clean)
- `pnpm test --run` → 20 passed / 10 files / Duration ~6.1 s
- `pnpm build` → emits 76.42 KB CSS + 631.92 KB JS; exits 0
- `grep -c ".strict()" src/pages/social/campaigns/new.tsx` → 4 (1 schema + 3 comments; plan required >=1 on CampaignFormSchema)
- `grep -c 'min(1, "select at least' src/pages/social/campaigns/new.tsx` → 1 (the platforms array)
- `grep -c "/api/v1/social/campaigns" src/pages/social/campaigns/new.tsx` → 2 (openapi-fetch POST path literal + optional comment reference)
- `grep -c "JobStatusCard jobId={id}" src/pages/social/campaigns/status.tsx` → 1
- `grep -c "stub — plan 21-09" frontend/src/pages/social/campaigns/` → 0 (both stubs fully replaced)

## TDD Gate Compliance

Task 1 was TDD. Git log shows the required sequence:
- Task 1: `df47ad7` (test: RED) → `5c41901` (feat: GREEN). Both commits present.

The RED commit fails both tests (confirmed by running tests before writing implementation; the stub has no brand_kit_slug label so `getByLabelText(/brand kit slug/i)` threw `TestingLibraryElementError: Unable to find a label...`). The GREEN commit makes both pass. No REFACTOR commits were needed; GREEN code is already idiomatic.

## Self-Check: PASSED

---
*Phase: 21-react-frontend-dashboard*
*Completed: 2026-04-23*
