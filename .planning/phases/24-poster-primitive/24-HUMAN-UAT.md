---
status: partial
phase: 24-poster-primitive
source: [24-VERIFICATION.md]
started: 2026-04-25T09:06:23Z
updated: 2026-04-25T09:06:23Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Live-stack poster render
expected: Status page at /posters/{job_id} shows a succeeded JobStatusCard with an inline PNG preview at the expected canvas aspect ratio; navigating back to /posters/new works correctly
result: [pending]

How to run:
1. Start the 5-service stack (Postgres + Redis + uvicorn + arq worker + Vite dev)
2. Navigate to http://localhost:5173/posters/new
3. Submit a poster with `size=18x24` and `template=editorial_grand`
4. Wait for the status page to show a rendered PNG
5. Confirm the PNG is visually legible at poster scale and matches the chosen size's aspect ratio
6. Repeat for at least one other size (e.g., 27x40) to spot-check large canvas

### 2. Playwright permutation harness runtime
expected: All 9 permutations passed (editorial_grand/bold_announcement/cinematic_onesheet × 18x24/24x36/27x40); exit 0
result: [pending]

How to run:
1. With the same 5-service stack still running
2. `node /tmp/check-e2e-poster-24.mjs`
3. Confirm exit 0 and "All 9 permutations passed" message

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
