---
phase: 02-image-pipeline
plan: 03
subsystem: vision
tags: [anthropic, claude-vision, async, pydantic, json-parsing, confidence-gating]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: Settings, EventInput, VisionVerdict, LayoutZones, error hierarchy, ZoneName
provides:
  - VisionEvaluator class with evaluate() method for background approval and zone placement
  - VISION_SYSTEM_PROMPT constant (verbatim from n8n)
  - Robust response parsing with markdown fence stripping and JSON extraction
  - Confidence gating and zone validation
affects: [03-composition, orchestrator, retry-loop]

# Tech tracking
tech-stack:
  added: [anthropic AsyncAnthropic SDK]
  patterns: [async SDK client injection via Settings, parse-validate-gate pipeline, single retry on parse failure]

key-files:
  created:
    - flyer_generator/stages/vision.py
    - tests/test_vision.py
    - tests/fixtures/vision_responses.py
  modified: []

key-decisions:
  - "Zone validation nulls out zones dict when invalid names detected to prevent Pydantic validation error cascading"
  - "AsyncAnthropic client created in __init__ with timeout from settings (no httpx client injection per spec discretion)"

patterns-established:
  - "Vision parse pipeline: strip fences -> extract braces -> json.loads -> confidence gate -> zone validate -> Pydantic"
  - "Single retry pattern: on parse failure, send original exchange + 'Return valid JSON only' follow-up"

requirements-completed: [VISN-01, VISN-02, VISN-03, VISN-04, VISN-05]

# Metrics
duration: 3min
completed: 2026-04-17
---

# Phase 2 Plan 3: VisionEvaluator Summary

**Claude vision evaluator with robust JSON parsing, confidence gating, zone validation, and single-retry recovery**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-17T00:33:59Z
- **Completed:** 2026-04-17T00:37:10Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- VisionEvaluator sends background image + event context to Claude via AsyncAnthropic SDK
- Response parsing handles clean JSON, markdown-fenced, and prose-wrapped LLM output
- Confidence gate flips approved to False below 0.6 threshold with rejection reason
- Zone validation catches null zones and invalid zone names for approved verdicts
- 18 comprehensive tests covering all parsing, gating, validation, and retry paths

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement VisionEvaluator with system prompt, parsing, and validation gates** - `2cad96e` (feat)
2. **Task 2: Create comprehensive tests for VisionEvaluator** - `8263df4` (test)

## Files Created/Modified
- `flyer_generator/stages/vision.py` - VisionEvaluator class with VISION_SYSTEM_PROMPT, evaluate(), _parse_and_validate()
- `tests/test_vision.py` - 18 tests: parsing, confidence gate, zone validation, evaluate with mock SDK
- `tests/fixtures/vision_responses.py` - Mock response fixtures (approved, rejected, low-confidence, invalid zones, wrapped)

## Decisions Made
- Zone validation nulls out the zones dict when invalid zone names are detected, preventing Pydantic's LayoutZones Literal validator from raising before VisionResponseParseError can be thrown
- AsyncAnthropic client created directly in __init__ (no httpx client injection) per spec discretion note

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Zone validation must null zones dict on invalid names**
- **Found during:** Task 2 (test_zone_validation_rejects_invalid_zone_name)
- **Issue:** When zone validation detected invalid zone names and flipped approved to False, the invalid zone dict was still passed to Pydantic, which raised a Literal validation error instead of allowing the graceful rejection path
- **Fix:** Added `data["zones"] = None` when invalid zones are detected, so Pydantic accepts the now-rejected verdict
- **Files modified:** flyer_generator/stages/vision.py
- **Verification:** test_zone_validation_rejects_invalid_zone_name passes
- **Committed in:** 8263df4 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential for correctness of zone validation path. No scope creep.

## Issues Encountered
None beyond the auto-fixed bug above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- VisionEvaluator ready for integration in orchestrator retry loop
- All stage modules (preprocessor, prompt_builder, comfy_client, vision) now complete for Phase 2

---
*Phase: 02-image-pipeline*
*Completed: 2026-04-17*
