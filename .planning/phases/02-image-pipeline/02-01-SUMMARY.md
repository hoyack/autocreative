---
phase: 02-image-pipeline
plan: 01
subsystem: image-pipeline
tags: [pydantic, pillow, comfycloud, prompt-composition, image-upscale]

requires:
  - phase: 01-foundations
    provides: PresetRegistry, FLYER_DIRECTIVES, UNIVERSAL_NEGATIVE, COMFY_WORKFLOW_TEMPLATE, EventInput, ComfyJob, GeneratedBackground, UnknownPresetError

provides:
  - StylePromptBuilder class for composing ComfyCloud workflow JSON from presets
  - ComfyWorkflow Pydantic model wrapping workflow dict with prompts and seed
  - ImagePreprocessor class for upscaling 832x1472 to 1080x1920
affects: [02-02-comfy-client, 02-03-vision-evaluator, 03-composition]

tech-stack:
  added: [Pillow (LANCZOS resampling), secrets (seed generation), copy (deep-copy)]
  patterns: [stage-class pattern with single responsibility, deep-copy for template safety]

key-files:
  created:
    - flyer_generator/stages/prompt_builder.py
    - flyer_generator/stages/preprocessor.py
    - tests/test_prompt_builder.py
    - tests/test_preprocessor.py
  modified: []

key-decisions:
  - "Used secrets.randbelow(2**31) for seed generation -- cryptographically unnecessary but free and avoids random module state"
  - "ImagePreprocessor.upscale() accepts arbitrary source dimensions, recording actual size rather than enforcing 832x1472"

patterns-established:
  - "Stage class pattern: single-method class (build/upscale) with injected dependencies via constructor"
  - "Deep-copy template mutation: copy.deepcopy before injecting values into shared workflow template"

requirements-completed: [IGEN-01, IGEN-05]

duration: 2min
completed: 2026-04-17
---

# Phase 2 Plan 1: Prompt Builder and Image Preprocessor Summary

**StylePromptBuilder composes ComfyCloud workflow JSON from preset fragments with concept substitution, and ImagePreprocessor upscales 832x1472 to 1080x1920 via Pillow LANCZOS**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-17T00:24:47Z
- **Completed:** 2026-04-17T00:26:54Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- StylePromptBuilder.build() composes positive prompt (preset fragments + FLYER_DIRECTIVES + optional refinement hint) and negative prompt (UNIVERSAL_NEGATIVE + preset negative_fragment)
- ComfyWorkflow model wraps deep-copied COMFY_WORKFLOW_TEMPLATE with injected prompts and seed
- ImagePreprocessor.upscale() resizes to exactly 1080x1920 via LANCZOS, recording source and final dimensions
- 22 tests total covering all prompt composition logic, deep-copy safety, upscale dimensions, and error cases

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement StylePromptBuilder and ComfyWorkflow model** - `67e66c7` (feat)
2. **Task 2: Implement ImagePreprocessor with Pillow upscale** - `07a0e3d` (feat)

## Files Created/Modified
- `flyer_generator/stages/prompt_builder.py` - StylePromptBuilder class and ComfyWorkflow Pydantic model
- `flyer_generator/stages/preprocessor.py` - ImagePreprocessor class with Pillow LANCZOS upscale
- `tests/test_prompt_builder.py` - 15 tests for prompt composition logic
- `tests/test_preprocessor.py` - 7 tests for image upscale behavior

## Decisions Made
- Used secrets.randbelow(2**31) for seed generation -- cryptographically unnecessary but free and avoids random module state concerns
- ImagePreprocessor.upscale() accepts and records arbitrary source dimensions rather than enforcing 832x1472 only -- more resilient to upstream changes

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- StylePromptBuilder ready for ComfyClient to consume ComfyWorkflow in plan 02-02
- ImagePreprocessor ready to upscale raw ComfyCloud output after download in plan 02-02
- Both modules import cleanly from Phase 1 foundations

---
*Phase: 02-image-pipeline*
*Completed: 2026-04-17*
