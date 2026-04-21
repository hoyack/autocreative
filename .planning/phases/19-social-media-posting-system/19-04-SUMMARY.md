---
phase: 19-social-media-posting-system
plan: 04
subsystem: social
tags: [pillow, imageops, aspect-ratio, workflow-selection, comfycloud, lanczos]

requires:
  - phase: 19-social-media-posting-system
    provides: "Platform/ImageRole Literal types and SocialError from Plans 01-02"
provides:
  - "select_workflow_for_aspect(aspect) -> standard_square | turbo_portrait | turbo_landscape"
  - "select_workflow_for_campaign(platforms, include_story=...) -> single workflow name"
  - "PLATFORM_TO_ASPECT mapping from Platform to primary aspect string"
  - "PLATFORM_CROP_SIZES table (9 entries) of (platform, role) -> (w, h)"
  - "crop_hero_for_platform(src_bytes, w, h) -> PNG bytes via ImageOps.fit LANCZOS"
  - "upscale_source_hero(src_bytes, target=(2048,2048)) -> PNG bytes"
  - "crop_all_platforms(src_bytes, [(platform,role)...]) -> dict[(p,r),bytes]"
  - "workflow_for_aspect / crop_to_aspect short-form aliases"
affects:
  - 19-05-single-post-generator
  - 19-06-single-post-image-generation
  - 19-07-campaign-shared-hero

tech-stack:
  added: []
  patterns:
    - "50 MP decode/allocate cap on untrusted PNG bytes (matches brand_kit/audit.py)"
    - "Image.verify() probe-then-reopen pattern for untrusted bytes"
    - "Pure stateless utility module — no I/O, no global state"
    - "Lazy PIL imports (noqa: PLC0415) inside functions to keep import-time cost low"

key-files:
  created:
    - "flyer_generator/social/workflow_map.py"
    - "flyer_generator/social/crop.py"
    - "tests/social/test_workflow_map.py"
    - "tests/social/test_crop.py"
  modified: []

key-decisions:
  - "ValueError (not SocialError) on unknown aspect — programmer error, not user input"
  - "include_story=True short-circuits to turbo_portrait even if other platforms prefer landscape, because 9:16 crop from landscape loses ~45% of horizontal content per 19-RESEARCH"
  - "Mixed-aspect campaigns default to standard_square (best letterbox compromise)"
  - "upscale_source_hero defaults to (2048, 2048) to cover the widest LinkedIn link_preview need (1200x627) without extra scaling for any consumer"
  - "Added short-form aliases workflow_for_aspect and crop_to_aspect to satisfy orchestrator success-criteria contract"

patterns-established:
  - "Pure module pattern: no I/O, no config, only deterministic helpers"
  - "Untrusted PNG guard: verify() then reopen-convert-RGB + 50 MP cap before any allocation"

requirements-completed:
  - SOC-06

duration: 5min
completed: 2026-04-21
---

# Phase 19 Plan 04: Workflow Map + Crop Helpers Summary

**ComfyCloud workflow selector plus Pillow-based campaign hero crop utilities (ImageOps.fit, LANCZOS, 9-slot PLATFORM_CROP_SIZES table) with 50 MP memory-safety cap.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-21T19:11:29Z (plan kickoff)
- **Completed:** 2026-04-21
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 4 (2 source + 2 test)

## Accomplishments

- `workflow_map.py`: `select_workflow_for_aspect` + `select_workflow_for_campaign` + `PLATFORM_TO_ASPECT` ready for consumption by Plans 06 and 07.
- `crop.py`: `PLATFORM_CROP_SIZES` (all 9 research-spec entries), `crop_hero_for_platform`, `upscale_source_hero`, `crop_all_platforms` ready for the campaign shared-hero fan-out.
- 16 unit tests cover every branch (square/portrait/landscape selection, include_story, empty-platforms ValueError, garbage PNG → SocialError, 50 MP target overflow → SocialError).
- 962 regression tests still green — no existing functionality affected.

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests for workflow_map + crop** — `4023428` (test)
2. **Task 1 (GREEN): Implement workflow_map + crop helpers** — `4b8d89a` (feat)

**Plan metadata (pending):** will be added by the post-plan docs commit.

## Files Created/Modified

- `flyer_generator/social/workflow_map.py` — aspect → workflow mapping, campaign workflow picker, `PLATFORM_TO_ASPECT`, `workflow_for_aspect` alias.
- `flyer_generator/social/crop.py` — `PLATFORM_CROP_SIZES` (9 entries), `crop_hero_for_platform` (ImageOps.fit LANCZOS), `upscale_source_hero`, `crop_all_platforms`, `crop_to_aspect` alias.
- `tests/social/test_workflow_map.py` — 9 tests for aspect/campaign selection + error paths.
- `tests/social/test_crop.py` — 7 tests for crop/upscale/fan-out + 50 MP/garbage guards.

## Decisions Made

- Used `ValueError` (not `SocialError`) for unknown aspect strings — per plan behavior spec, this is a programmer error in calling code, not user-input validation.
- `include_story=True + instagram in platforms` short-circuits to `turbo_portrait` even when other platforms prefer landscape — 19-RESEARCH.md line 503 calls out the 45% horizontal-content loss when cropping landscape into 9:16 story.
- Mixed-aspect campaigns default to `standard_square` — best compromise when no uniform aspect exists among requested platforms.
- `upscale_source_hero` default target `(2048, 2048)` covers the widest consumer (LinkedIn link_preview 1200×627) with comfortable headroom; callers can override per-campaign.
- Exposed short-form aliases `workflow_for_aspect` and `crop_to_aspect` to satisfy the orchestrator's success-criteria import check without renaming the canonical symbols in the plan.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Short-form aliases `workflow_for_aspect` / `crop_to_aspect`**
- **Found during:** Task 1 verification (success-criteria import check)
- **Issue:** Plan behavior/artifacts specify `select_workflow_for_aspect` and `crop_hero_for_platform` (canonical names), but the orchestrator's `<success_criteria>` included an import check for `workflow_for_aspect` and `crop_to_aspect` (short-form). Without aliases the criterion would fail despite the contract being met.
- **Fix:** Added module-level aliases `workflow_for_aspect = select_workflow_for_aspect` in `workflow_map.py` and `crop_to_aspect = crop_hero_for_platform` in `crop.py`. Docstring comment marks the canonical name as preferred for new call sites.
- **Files modified:** `flyer_generator/social/workflow_map.py`, `flyer_generator/social/crop.py`
- **Verification:** `python -c "from flyer_generator.social.workflow_map import workflow_for_aspect; from flyer_generator.social.crop import crop_to_aspect"` exits 0.
- **Committed in:** `4b8d89a` (GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical alias)
**Impact on plan:** Zero behavioral change; purely additive exports to satisfy the orchestrator-level contract. Canonical symbols remain the intended API.

## Issues Encountered

None.

## Threat Model Compliance

All four `mitigate` dispositions from the plan's STRIDE register implemented:

| Threat ID | Mitigation Status |
|---|---|
| T-19-04-01 (DoS zip-bomb PNG) | `Image.verify()` + 50 MP source cap in both `crop_hero_for_platform` and `upscale_source_hero` |
| T-19-04-02 (DoS huge target) | 50 MP target cap before allocation in both functions |
| T-19-04-03 (Pillow CVE) | Accepted per plan — relies on pinned Pillow >=12.2.0 |
| T-19-04-05 (Logic error: wrong workflow) | Unit matrix covers every (platforms × include_story) branch |

## User Setup Required

None — pure library code, no external services touched.

## Next Phase Readiness

- Plan 06 (single-post image generation) can call `select_workflow_for_aspect(template.image_slot.aspect)` immediately.
- Plan 07 (campaign shared-hero fan-out) can chain `select_workflow_for_campaign(...)` → generate hero → `upscale_source_hero(...)` → `crop_all_platforms(...)` for the fan-out.
- No blockers; Wave 3 delivery complete for this parallel plan.

## Self-Check: PASSED

Verified:
- `flyer_generator/social/workflow_map.py` exists
- `flyer_generator/social/crop.py` exists
- `tests/social/test_workflow_map.py` exists
- `tests/social/test_crop.py` exists
- Commit `4023428` (RED) present in git log
- Commit `4b8d89a` (GREEN) present in git log
- `python -m pytest tests/social/test_workflow_map.py tests/social/test_crop.py -x -q` exits 0 (16 tests)
- `python -m pytest tests/ -x -q -m "not slow"` exits 0 (962 tests)
- `python -c "from flyer_generator.social.workflow_map import workflow_for_aspect; from flyer_generator.social.crop import crop_to_aspect"` exits 0

---
*Phase: 19-social-media-posting-system*
*Completed: 2026-04-21*
