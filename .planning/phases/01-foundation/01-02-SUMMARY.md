---
phase: 01-foundation
plan: 02
subsystem: models
tags: [pydantic, pydantic-v2, data-contracts, presets, zones, pytest]

# Dependency graph
requires:
  - phase: 01-foundation-01
    provides: "errors.py exception hierarchy, config.py Settings, logging_config.py"
provides:
  - "7 Pydantic v2 data models (EventInput, ComfyJob, GeneratedBackground, LayoutZones, VisionVerdict, ResolvedLayout, FlyerOutput)"
  - "9 zone coordinate definitions with pixel positions and text anchors"
  - "6 built-in style presets with verbatim n8n prompt text"
  - "PresetRegistry for custom preset registration"
  - "Complete public API surface via flyer_generator.__init__"
  - "43-test suite covering all foundation modules"
affects: [02-pipeline, 03-composition, 04-cli]

# Tech tracking
tech-stack:
  added: [pytest]
  patterns: [pydantic-v2-models, frozen-dataclass, preset-registry, field-validators, model-validators]

key-files:
  created:
    - flyer_generator/models.py
    - flyer_generator/zones.py
    - flyer_generator/presets.py
    - tests/test_models.py
    - tests/test_config.py
    - tests/test_errors.py
    - tests/test_zones.py
    - tests/test_presets.py
    - tests/fixtures/sample_events.py
  modified:
    - flyer_generator/__init__.py
    - .gitignore

key-decisions:
  - "ResolvedLayout uses BaseModel with arbitrary_types_allowed=True for ZoneCoord fields (consistency with other models)"
  - "style_preset on EventInput is plain str, not Literal -- validated against PresetRegistry at runtime in Phase 2"

patterns-established:
  - "Pydantic v2 BaseModel for all cross-stage contracts"
  - "Field(default_factory=list) for mutable defaults"
  - "field_validator for input sanitization (hex color regex)"
  - "model_validator(mode='after') for cross-field invariants"
  - "Frozen dataclass for immutable value objects (ZoneCoord)"
  - "Registry pattern for extensible preset system"

requirements-completed: [FOUND-02, FOUND-05]

# Metrics
duration: 4min
completed: 2026-04-16
---

# Phase 1 Plan 2: Data Contracts, Zones & Presets Summary

**7 Pydantic v2 data models, 9-zone coordinate grid, and 6 style presets with verbatim n8n prompt text -- all validated by 43 tests**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-16T23:42:47Z
- **Completed:** 2026-04-16T23:47:02Z
- **Tasks:** 2
- **Files modified:** 13

## Accomplishments
- All 7 cross-stage Pydantic v2 models implemented with validation (hex color, max_length, zones-required-when-approved)
- 9 zone coordinates mapped to correct pixel positions (180/540/900 x, 320/960/1600 y) with text anchors
- 6 built-in presets registered with exact n8n workflow prompt text, all containing {concept} placeholder
- PresetRegistry supports custom preset registration for extensibility
- 43 tests covering models, config, errors, zones, and presets -- all passing
- Public API surface finalized in __init__.py with __all__ exports

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement zones.py, models.py, and presets.py** - `43d3d7f` (feat)
2. **Task 2: Create test suite and finalize __init__.py public API** - `03e1652` (feat)

## Files Created/Modified
- `flyer_generator/zones.py` - ZoneName literal, ZoneCoord frozen dataclass, ZONE_COORDS dict with 9 entries
- `flyer_generator/models.py` - 7 Pydantic v2 models: EventInput, ComfyJob, GeneratedBackground, LayoutZones, VisionVerdict, ResolvedLayout, FlyerOutput
- `flyer_generator/presets.py` - StylePreset model, PresetRegistry class, 6 built-in presets, FLYER_DIRECTIVES, UNIVERSAL_NEGATIVE, COMFY_WORKFLOW_TEMPLATE
- `flyer_generator/__init__.py` - Full public API re-exports with __all__
- `tests/test_models.py` - 20 tests for all 7 models
- `tests/test_config.py` - 3 tests for Settings
- `tests/test_errors.py` - 5 tests for exception hierarchy
- `tests/test_zones.py` - 9 tests for zone coordinates
- `tests/test_presets.py` - 9 tests for preset registry
- `tests/fixtures/sample_events.py` - SAMPLE_EVENT and SAMPLE_EVENT_WITH_URL fixtures
- `.gitignore` - Updated with complete Python exclusions

## Decisions Made
- ResolvedLayout uses BaseModel with `arbitrary_types_allowed=True` rather than plain dataclass, keeping consistency with all other models being Pydantic BaseModel
- `style_preset` on EventInput is `str` (not Literal) -- validated against PresetRegistry at runtime in Phase 2 per RESEARCH.md guidance

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All foundation contracts ready for pipeline stages (Phase 2)
- EventInput, VisionVerdict, LayoutZones, ResolvedLayout provide typed interfaces for each stage
- PresetRegistry and COMFY_WORKFLOW_TEMPLATE ready for prompt builder stage
- ZONE_COORDS ready for layout resolver stage

## Self-Check: PASSED

All 11 created files verified present. Both task commits (43d3d7f, 03e1652) verified in git log.

---
*Phase: 01-foundation*
*Completed: 2026-04-16*
