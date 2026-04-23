---
status: partial
phase: 21-react-frontend-dashboard
source: [21-VERIFICATION.md]
started: 2026-04-23T15:00:00Z
updated: 2026-04-23T15:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Capability (a): Browse brand kits + scrape a new one via URL
expected: Navigate /brand-kits -> see card grid; click Add brand kit; enter URL + slug; submit; watch job progress to succeeded; return to /brand-kits and see new kit; click card -> detail shows palette swatches + typography + logos + voice
result: [pending]

### 2. Capability (b): Flyer form -> job progress -> rendered PNG
expected: Navigate /flyers/new; fill EventInput fields + preset + accent; submit; on /flyers/:id see queued -> running (elapsed counter ticks) -> succeeded with PNG preview rendered inline
result: [pending]

### 3. Capability (c): Brochure form -> two sheets + PDF render
expected: Navigate /brochures/new; paste content JSON + fill template/preset/brand-kit; submit; on /brochures/:id see job polling and, after succeeded, 3 artifacts: front PNG inline + back PNG inline + Print PDF download link
result: [pending]

### 4. Capability (d): Social post form -> copy + image + validation report
expected: Navigate /social/posts/new; pick platform/intent + fill topic/cta/image_hint/brand-kit; submit; on /social/posts/:id watch job poll to succeeded; see rendered post image. NOTE: validation_report and audit_report are NOT yet surfaced in v1 (documented deviation per plan 21-08) — confirm the image-only UX matches v1 expectation.
result: [pending]

### 5. Capability (e): Campaign form -> N platform variants render
expected: Navigate /social/campaigns/new; pick 2+ platforms via checkbox group + intent/topic/brand-kit; submit; on /social/campaigns/:id see per-platform grid with one RenderPreview per platform
result: [pending]

### 6. Capability (f): Browse past renders with download + inline preview
expected: Navigate /renders; see CSS grid of render cards; PNG kinds render inline via <img>; PDF kinds show Download PDF link; Kind dropdown filters results; pagination works
result: [pending]

### 7. Jobs page (FE-09): global list with row-level status polling
expected: Navigate /jobs; see Table with Created/Kind/Status/Id columns; Kind + Status filters refine list; non-terminal rows poll and update status in place every 1s; row click navigates to the creative's status page
result: [pending]

### 8. Sidebar navigation: 7 links with active-state highlighting
expected: DashboardLayout sidebar shows Brand kits / New flyer / New brochure / New post / New campaign / Jobs / Renders. Current route's NavLink has aria-current or data-active styling.
result: [pending]

### 9. Dev loop: cd frontend && pnpm dev boots on :5173 and talks to Phase 20 via proxy
expected: Vite dev server starts on :5173; HMR works; /api/* requests proxy to http://localhost:8000; no CORS errors in browser console
result: [pending]

## Summary

total: 9
passed: 0
issues: 0
pending: 9
skipped: 0
blocked: 0

## Gaps
