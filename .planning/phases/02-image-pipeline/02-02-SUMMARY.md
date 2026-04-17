---
phase: 02-image-pipeline
plan: 02
subsystem: api
tags: [httpx, async, comfycloud, polling, backoff, respx]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: Settings, error hierarchy, ComfyJob/GeneratedBackground models
  - phase: 02-image-pipeline plan 01
    provides: ComfyWorkflow model from prompt_builder
provides:
  - ComfyClient class with submit, wait_for_completion, download_result, generate methods
  - Mock ComfyCloud response fixtures for testing
affects: [04-pipeline-orchestrator, 02-image-pipeline plan 03]

# Tech tracking
tech-stack:
  added: [respx (test mocking)]
  patterns: [async HTTP client with exponential backoff, protocol-based typing for loose coupling]

key-files:
  created:
    - flyer_generator/stages/comfy_client.py
    - tests/test_comfy_client.py
    - tests/fixtures/comfy_responses.py
  modified: []

key-decisions:
  - "Used ComfyWorkflowLike Protocol for loose coupling with prompt_builder module"
  - "generate() returns (ComfyJob, bytes) tuple instead of GeneratedBackground to separate concerns"
  - "Extracted _request_with_backoff helper to DRY backoff logic across submit and polling"

patterns-established:
  - "Exponential backoff: 3 retries starting at 1s (1s, 2s, 4s) on 5xx responses"
  - "Protocol-based typing: ComfyWorkflowLike avoids hard import dependency between stages"
  - "respx mock pattern: fixtures in tests/fixtures/, base_url scoped router"

requirements-completed: [IGEN-02, IGEN-03, IGEN-04]

# Metrics
duration: 3min
completed: 2026-04-17
---

# Phase 02 Plan 02: ComfyClient Summary

**Async ComfyCloud HTTP client with submit/poll/download lifecycle, exponential backoff on 5xx, and 20 respx-mocked tests**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-17T00:29:01Z
- **Completed:** 2026-04-17T00:31:40Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- ComfyClient with full async lifecycle: submit workflow, poll status with configurable timing, download via history_v2+view chain
- Exponential backoff (3 retries, 1s base) on 5xx for both submit and polling endpoints
- 20 async tests covering all happy paths, error paths, backoff, timeout, and orchestration using respx

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement ComfyClient with submit, polling, and download** - `4a32a0b` (feat)
2. **Task 2: Create comprehensive async tests for ComfyClient** - `4b6226c` (test)

## Files Created/Modified
- `flyer_generator/stages/comfy_client.py` - ComfyClient class with submit, wait_for_completion, download_result, generate methods
- `tests/test_comfy_client.py` - 20 async tests covering submit (5), polling (8), download (4), generate (3)
- `tests/fixtures/comfy_responses.py` - Mock API response data and valid tiny PNG fixture

## Decisions Made
- Used ComfyWorkflowLike Protocol for structural typing to avoid hard import dependency on prompt_builder.py -- enables parallel development
- generate() returns (ComfyJob, bytes) tuple rather than constructing GeneratedBackground directly -- the pipeline orchestrator (Phase 4) combines with ImagePreprocessor to create the full model
- Extracted _request_with_backoff helper to share backoff logic between submit and polling

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- ComfyClient ready for integration with pipeline orchestrator in Phase 4
- Image download returns raw bytes ready for ImagePreprocessor (already built in 02-01)
- All error types properly raised for retry/regen logic in orchestrator

---
*Phase: 02-image-pipeline*
*Completed: 2026-04-17*
