---
phase: 21-react-frontend-dashboard
plan: 14
subsystem: ui
tags: [react, vitest, testing-library, pdf-detection, regression, regex]

# Dependency graph
requires:
  - phase: 21-react-frontend-dashboard
    provides: "RenderPreview component (21-04) and brochure status page consumer (21-07)"
provides:
  - "Strict `.pdf` suffix regex PDF detection in RenderPreview (no substring false positives)"
  - "Explicit `isPdf` prop on RenderPreview for caller-asserted content-type hints"
  - "`suggestPdfFilename()` helper — IN-01 companion fix so download filenames always end in .pdf"
  - "Vitest regression coverage pinning WR-04 false-positive + happy-path PDF + isPdf prop behavior"
affects:
  - "Future gallery work that adds non-image render kinds"
  - "Any future caller needing deterministic PDF branch on RenderPreview"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Strict suffix regex for content-type sniffing from URL"
    - "Caller-asserted content-type override via optional boolean prop"
    - "Pure-path filename derivation helper (no URL parser dependency)"

key-files:
  created:
    - "frontend/src/components/RenderPreview.test.tsx — 4 Vitest regression cases"
  modified:
    - "frontend/src/components/RenderPreview.tsx — regex + isPdf + suggestPdfFilename"
    - "frontend/src/pages/brochures/status.tsx — pass isPdf on pdf_render_url slot"

key-decisions:
  - "Combined fix (Option A + B from 21-REVIEW): strict `.pdf` suffix regex `/\\.pdf($|\\?)/i` AND an optional `isPdf` prop. `isPdf` is OR'd with suffix match (not AND) — explicit true forces PDF branch; explicit false falls back to suffix check rather than overriding a real .pdf URL."
  - "Only brochures/status.tsx pdf_render_url slot receives isPdf. Gallery.tsx branches via isPdfKind(r.kind) upstream and never hits RenderPreview for PDFs; JobStatusCard.tsx lacks kind context at the single-render view and relies on the suffix regex (safe because backend `/renders/{id}/image` URLs never have a .pdf suffix)."
  - "suggestPdfFilename prefers {ulid}.pdf for the /renders/{id}/image shape (IN-01), falling back to last-segment + .pdf append so OS Save dialogs always see a .pdf extension."
  - "download attribute is a STRING not a boolean — React emits an empty `download` attribute for boolean true which lets the browser guess from href; a deterministic string gives stable filename behavior."

patterns-established:
  - "Content-type detection from URL: use strict suffix regex anchored with `$` or `?`, NOT substring `includes`. Substring checks are latent false-positive landmines the moment URL shapes change."
  - "Caller content-type hint pattern: optional `is<Type>?: boolean` prop OR'd with URL-based fallback so callers with deterministic knowledge get deterministic behavior and callers without it still work."

requirements-completed: [FE-10, FE-06]

# Metrics
duration: ~10min
completed: 2026-04-23
---

# Phase 21 Plan 14: Gap Closure WR-04 + IN-01 Summary

**Replace permissive `/pdf` URL substring check in RenderPreview with strict `.pdf` suffix regex + explicit `isPdf` prop, and land Vitest regression coverage for both the false-positive and happy paths.**

## Performance

- **Duration:** ~10 min (wall clock)
- **Started:** 2026-04-23T20:30:00Z (approx, plan start)
- **Completed:** 2026-04-23T20:41:24Z
- **Tasks:** 1
- **Files modified:** 3 (2 modified, 1 created)

## Accomplishments

- **WR-04 closed:** eliminated the `lower.includes("/pdf")` substring false-positive that would have misrendered any URL with `/pdf` in its path (e.g. a ULID beginning with `pdf`) as a PDF-download anchor instead of an inline image.
- **Explicit `isPdf` prop:** callers with deterministic content-type knowledge (brochures/status.tsx `pdf_render_url` slot) can now force the download branch without depending on URL inspection.
- **IN-01 companion fix:** `suggestPdfFilename()` derives `{ulid}.pdf` for `/renders/{id}/image` URLs and otherwise appends `.pdf` to the last path segment — the OS Save dialog now always sees a `.pdf` extension.
- **Regression coverage locked in:** 4 Vitest cases in `RenderPreview.test.tsx` pin the fix (false-positive, `.pdf` suffix, `.pdf?query` suffix, explicit `isPdf` prop + filename). Full frontend suite 26/26 passing; typecheck clean.

## Task Commits

TDD atomic commits:

1. **Task 1 RED — failing tests** — `4342f15` (test)
   - Added `RenderPreview.test.tsx` with 4 `it()` blocks. Tests 1 + 4 failed on pre-fix code as expected (false-positive + missing `isPdf` prop). Tests 2 + 3 passed already (happy-path suffix matching).
2. **Task 1 GREEN — fix + caller update** — `992390d` (fix)
   - Rewrote `RenderPreview.tsx` with `PDF_SUFFIX_RE`, `isPdf` prop, `suggestPdfFilename()` helper. Added `isPdf` to brochures/status.tsx pdf_render_url slot. All 4 new tests pass; full 26/26 suite green; typecheck clean.

## Files Created/Modified

- `frontend/src/components/RenderPreview.tsx` (modified) — Replaced substring check with `PDF_SUFFIX_RE = /\.pdf($|\?)/i`. Added `isPdf?: boolean` prop, `suggestPdfFilename()` helper, OR logic `isPdf === true || PDF_SUFFIX_RE.test(url)`, string `download` attribute with derived filename.
- `frontend/src/components/RenderPreview.test.tsx` (created) — 4 Vitest regression cases: WR-04 false-positive, `.pdf` suffix, `.pdf?query` suffix, explicit `isPdf` prop + `.pdf` filename derivation.
- `frontend/src/pages/brochures/status.tsx` (modified) — Added `isPdf` prop to the third `<RenderPreview>` call (pdf_render_url slot). Front and back PNG calls left unchanged.

## New Vitest Cases (for traceability)

1. `RenderPreview > does not treat a URL containing the substring '/pdf' as a PDF (WR-04)` — renders inline `<img>` for `/api/v1/renders/pdf01habcdefghjkmnpqrstvwxyz/image`; asserts no anchor.
2. `RenderPreview > renders a download anchor for a URL ending in .pdf` — `/files/report.pdf` renders `<a download>` with matching href.
3. `RenderPreview > renders a download anchor for a URL ending in .pdf?query` — `/files/report.pdf?v=2` also triggers the anchor path; the `.pdf?` branch survives.
4. `RenderPreview > renders a download anchor when isPdf=true even without a .pdf suffix` — explicit prop forces anchor for `/api/v1/renders/{ulid}/image`; IN-01 companion: `download` attr matches `/\.pdf$/`.

## Grep-verifiable Evidence

```
=== no lower.includes('/pdf') ===
PASS: gone
=== PDF_SUFFIX_RE in RenderPreview.tsx ===
2 matches (declaration + usage)
=== isPdf in RenderPreview.tsx ===
4 matches (prop typing, destructure default, branch expression, comment)
=== isPdf in brochures/status.tsx ===
1 match (pdf_render_url call site)
=== it() count in RenderPreview.test.tsx ===
4
=== pnpm test --run ===
Test Files  12 passed (12)
     Tests  26 passed (26)
=== pnpm typecheck ===
exit 0
```

## Decisions Made

- **Combined Option A + B fix** (per 21-REVIEW.md WR-04 recommendation): strict regex for URL-based detection + explicit `isPdf` prop for caller-asserted content type. `isPdf` is OR'd with regex match (not AND) so explicit `true` forces the anchor without requiring a .pdf suffix, while explicit `false`/omitted falls back to the regex. The plan deliberately does not assert the `isPdf={false}` override case to keep the contract simple.
- **Only one caller updated** — brochures/status.tsx pdf_render_url slot. Gallery.tsx already branches on `isPdfKind(r.kind)` upstream and never hits RenderPreview for PDFs; JobStatusCard.tsx uses the component in single-render contexts where `kind` isn't known, relying safely on the regex fallback.
- **Filename strategy:** `{ulid}.pdf` for `/renders/{id}/image` URLs (the exact shape the backend emits), otherwise last-path-segment + `.pdf` append. This ensures the OS Save dialog always picks up `.pdf` (IN-01 companion) even when the URL itself has no extension.

## Deviations from Plan

None of material scope. One minor cosmetic adjustment:

### Minor adjustments

**1. [Success-criterion hygiene] Rewrote an in-file comment to avoid a literal `lower.includes("/pdf")` substring**
- **Found during:** Final grep verification step
- **Issue:** The plan's success criterion `! grep 'lower.includes("/pdf")' frontend/src/components/RenderPreview.tsx` required zero matches. The original GREEN implementation carried a historical comment citing the old code literally, which tripped the grep.
- **Fix:** Rephrased the comment to describe the old permissive check without repeating its exact source token. Logic unchanged.
- **Files modified:** `frontend/src/components/RenderPreview.tsx` (comment only)
- **Verification:** Re-ran grep (zero matches), re-ran tests (4/4), re-ran full suite (26/26), re-ran typecheck (clean). Folded into the GREEN commit.

---

**Total deviations:** 1 cosmetic (no logic/test impact)
**Impact on plan:** None. Acceptance criteria satisfied as written.

## Issues Encountered

- `frontend/node_modules` was missing at executor start (fresh worktree). Ran `pnpm install` — standard first-run setup, not a plan deviation.

## User Setup Required

None — UI-only fix, no environment variables, no external services.

## Next Phase Readiness

- WR-04 (review warning) closed. IN-01 (`.pdf` filename) companion closed.
- No follow-ups queued for this plan. The regression test pins the behavior; any future revert of the substring check would be caught immediately by CI.
- Other 21-REVIEW.md warnings (if any remain) are out of scope and tracked by their own gap-closure plans.

## Self-Check: PASSED

Verified before finalization:

- `[FOUND]` `frontend/src/components/RenderPreview.tsx` (modified, post-fix)
- `[FOUND]` `frontend/src/components/RenderPreview.test.tsx` (created, 4 `it()` blocks)
- `[FOUND]` `frontend/src/pages/brochures/status.tsx` (`isPdf` present at pdf_render_url call site)
- `[FOUND]` commit `4342f15` — RED test commit (`git log | grep 4342f15` matches)
- `[FOUND]` commit `992390d` — GREEN fix commit (`git log | grep 992390d` matches)
- `[PASS]` `pnpm test --run` — 26/26 tests green (12 test files)
- `[PASS]` `pnpm typecheck` — exit 0
- `[PASS]` `grep lower.includes("/pdf") RenderPreview.tsx` — zero matches
- `[PASS]` `grep PDF_SUFFIX_RE RenderPreview.tsx` — 2 matches
- `[PASS]` `grep isPdf RenderPreview.tsx` — 4 matches
- `[PASS]` `grep isPdf brochures/status.tsx` — 1 match

---
*Phase: 21-react-frontend-dashboard*
*Plan: 14*
*Completed: 2026-04-23*
