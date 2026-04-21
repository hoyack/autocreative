---
phase: 19-social-media-posting-system
plan: 07
subsystem: social
tags: [social, voice, comfycloud, orchestrator, brand-voice, post-generation]

requires:
  - phase: 19-01
    provides: _enforce_banned_words + BrandVoiceViolationError + BrandVoice-wired text_gen
  - phase: 19-03
    provides: PlatformRules + validate_post + PLATFORM_REGISTRY
  - phase: 19-04
    provides: select_workflow_for_aspect + ComfyCloud workflow resolution
  - phase: 19-05
    provides: PostTemplate + load_post_template (12 shipped templates)
  - phase: 19-06
    provides: render_post + brand-kit application + SVG rasterization
provides:
  - generate_single_image shared ComfyCloud entry point for social/campaign
  - generate_social_copy voice-aware LLM copy generator
  - generate_post single-post orchestrator (SOC-05 public API)
affects: [19-09 campaign-generator, phase-20-publishing]

tech-stack:
  added: []
  patterns:
    - "Shared single-image helper with caller-owned httpx lifecycle"
    - "ComfyCloud errors wrapped as SocialError at orchestrator boundary"
    - "Voice directive block prepended to system prompt; banned-word retry loop"
    - "Text-only branch skips ComfyCloud entirely when template.image_slot is None"

key-files:
  created:
    - flyer_generator/social/voice.py
    - flyer_generator/social/generator.py
    - tests/brochure/test_image_gate.py
    - tests/social/test_voice_social_copy.py
    - tests/social/test_generator.py
  modified:
    - flyer_generator/brochure/schema_renderer/image_gate.py

key-decisions:
  - "Delegate all ComfyClient construction to generate_single_image helper (B-05 fix) — generator.py never constructs ComfyClient directly"
  - "Import build_text_client from brochure.llm_client (canonical path) rather than text_gen re-export"
  - "Wrap ComfySubmitError as SocialError at orchestrator boundary so callers catch one family"
  - "180s httpx timeout on production path (ComfyCloud jobs take 30-90s)"
  - "Audit is advisory in Plan 07 (extension point for Plan 08); broad except is intentional to avoid blocking Post return"
  - "Text-only branch: image_slot None => hero_bytes None => post.image_bytes None (Open Risks #8)"

patterns-established:
  - "Single-image ComfyCloud call: load_workflow + _build_spot_workflow + ComfyClient(settings, http_client).generate(wf, 1)"
  - "Voice-aware LLM pattern: format_voice_directive + banned-word scan + one-shot retry + raise-after-retry"
  - "Orchestrator log discipline: bind trace_id once; info events at every pipeline step"

requirements-completed: [SOC-04, SOC-05]

duration: 15min
completed: 2026-04-21
---

# Phase 19 Plan 07: Single-Post Generator Summary

**Voice-aware social copy + single-post orchestrator (generate_post) wiring brand-voice, platform validation, and shared ComfyCloud hero generation via a new generate_single_image helper that fixes the B-05 ComfyClient init bug**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-21T20:27:00Z (approx)
- **Completed:** 2026-04-21T20:43:00Z
- **Tasks:** 3 (each TDD: RED + GREEN = 6 commits)
- **Files created:** 5 (2 modules + 3 test files)
- **Files modified:** 1 (image_gate.py +41 lines)

## Accomplishments

- `flyer_generator.brochure.schema_renderer.image_gate.generate_single_image(workflow_name, prompt, *, settings, http_client, style_preset, presets)` — shared single-image ComfyCloud entry point reusing canonical `ComfyClient(settings, http_client)` init + existing `_build_spot_workflow`. `generate_template_images` untouched (regression-safe).
- `flyer_generator.social.voice.generate_social_copy(brief, platform_rules, template, *, brand_voice, settings, text_client)` — produces `PostCopy` with title/body/cta/hashtags. Prepends a `VOICE DIRECTIVE` block to the system prompt when `brand_voice` is provided. Reuses `_enforce_banned_words` from `text_gen` (canonical Plan 01 helper). On banned-word hit, issues one retry with an explicit rewrite instruction; on repeat violation, raises `BrandVoiceViolationError`. Hashtags hard-capped to `platform_rules.hashtag_hard_max`. Instagram link-policy hint injected when `strips_links_in_caption=True`.
- `flyer_generator.social.generator.generate_post(brief, brand_kit, *, template, settings, text_client, comfy_client, audit)` — full single-post pipeline: load template (default `"{platform}__{intent}"`) → resolve platform rules → `generate_social_copy` → (optional) hero via `_generate_hero_image` which delegates to `generate_single_image` unless a mock `comfy_client` is injected → `render_post` → platform `validate()` → `Post(...)`. Text-only branch (`template.image_slot is None`) skips ComfyCloud and the image-bytes slot entirely. `trace_id` bound across all structured logs (`generate_post_start`, `_template_loaded`, `_copy_ready`, `_hero_start/ready`, `_text_only`, `_render_ready`, `_validate_ready`, `_end`).
- `ComfySubmitError` wrapped as `SocialError` at the orchestrator boundary so callers catch one family while retaining causal chain via `from err`.
- 14 new tests (2 image_gate + 9 voice + 3 generator) all passing; 1123 total tests green.

## Task Commits

Each task was committed atomically with the TDD RED/GREEN cycle:

1. **Task 1: generate_single_image helper** (image_gate.py)
   - RED: `3b0825b` — `test(19-07): add failing tests for generate_single_image helper`
   - GREEN: `f823e25` — `feat(19-07): add generate_single_image helper to image_gate`

2. **Task 2: voice-aware social copy generator** (voice.py)
   - RED: `3197106` — `test(19-07): add failing tests for generate_social_copy`
   - GREEN: `7b6bd86` — `feat(19-07): ship voice-aware social copy generator`

3. **Task 3: generate_post orchestrator** (generator.py)
   - RED: `1f56434` — `test(19-07): add failing tests for generate_post orchestrator`
   - GREEN: `e1b7778` — `feat(19-07): ship generate_post orchestrator`

## Files Created/Modified

- `flyer_generator/brochure/schema_renderer/image_gate.py` — NEW `generate_single_image` (+41 lines) reusing `_build_spot_workflow` + canonical `ComfyClient(settings, http_client)` init. `generate_template_images` untouched.
- `flyer_generator/social/voice.py` — Voice-aware social copy generator. Imports `_enforce_banned_words` from `text_gen` (Plan 01 canonical) and `build_text_client` from `brochure.llm_client` (canonical location, NOT `text_gen` re-export).
- `flyer_generator/social/generator.py` — Single-post orchestrator. Private `_generate_hero_image` delegates to `generate_single_image` on production path; accepts an injected mock `comfy_client` for tests.
- `tests/brochure/test_image_gate.py` — 2 tests: happy-path + B-05 regression guard that monkeypatches `ComfyClient.__init__` to verify both positional args are passed.
- `tests/social/test_voice_social_copy.py` — 9 tests: happy path, banned-word retry, raise-after-retry, hashtag hard-cap, IG link-policy injection, voice-directive formatting.
- `tests/social/test_generator.py` — 3 tests: LinkedIn value-prop E2E with mocked text + comfy; Twitter announcement text-only path skips ComfyCloud; validation_report attached.

## Decisions Made

- **Wrap ComfySubmitError as SocialError at orchestrator boundary.** Callers of `generate_post` should catch one error family (`SocialError`) rather than distinguishing between social-layer and ComfyCloud errors. Preserved the underlying cause via `raise ... from err`.
- **Delegate all ComfyClient construction to generate_single_image.** `generator.py` never imports `ComfyClient` directly. This keeps B-05 mitigation mechanical — the only code that instantiates `ComfyClient` is the one helper whose tests guard the correct 2-arg init.
- **Import build_text_client from canonical location.** Plan 01's `text_gen` re-exports `build_text_client`, but the canonical definition lives in `flyer_generator.brochure.llm_client`. Importing from the canonical path keeps the dependency graph obvious and avoids relying on re-export stability.
- **Audit is advisory in Plan 07, not a gate.** When `audit=True`, any audit failure is logged and stored as a string in `post.audit_summary` but never prevents `Post` return. Plan 08 may tighten this to raise on hard findings.

## Deviations from Plan

None — plan executed exactly as written. Task 1 (numbered Task 0 in plan, Task 1 in prompt), Task 2 (voice.py), Task 3 (generator.py) all implemented verbatim per the `<action>` code blocks. The plan's author pre-anchored the implementation so no Rule 1-3 auto-fixes were needed.

## Issues Encountered

None. The TDD cycle was clean: RED failed exactly as expected (ImportError / ModuleNotFoundError), GREEN passed on first implementation. No flake, no unrelated regressions.

## User Setup Required

None — no external service configuration required. ComfyCloud credentials and Ollama/Anthropic keys were already configured for earlier phases.

## Verification

- `pytest tests/brochure/test_image_gate.py tests/social/test_voice_social_copy.py tests/social/test_generator.py` — 14 passed
- `pytest tests/ -x -q -m "not slow"` — 1123 passed, 2 deselected
- `pytest tests/social/ tests/brochure/ tests/brand_kit/` — 936 passed (full regression)
- B-05 regression guard: `grep "ComfyClient(settings=settings)" flyer_generator/` → ZERO matches
- B-05 regression guard: `grep "client.submit(workflow=" flyer_generator/social/` → ZERO matches
- Canonical import: `grep "from flyer_generator.brochure.llm_client import build_text_client" flyer_generator/social/voice.py` → MATCH
- Import smoke: `python -c "from flyer_generator.social.generator import generate_post; from flyer_generator.social.voice import generate_social_copy"` exits 0

## Next Phase Readiness

- **Plan 19-09 (campaign generator):** Can now compose `generate_post` across platforms with a shared hero via `generate_single_image` (the planner called this out in key_links). No additional scaffolding needed.
- **SOC-04 + SOC-05 requirements satisfied.** BrandVoice flows end-to-end: `BrandKit → generate_post → generate_social_copy → _build_system_prompt → LLM → banned-word scan`.
- **No blockers.** All 1123 tests green, no deferred items, no pending architectural decisions.

## TDD Gate Compliance

- Task 1: RED (`3b0825b` test commit) → GREEN (`f823e25` feat commit). Gate sequence compliant.
- Task 2: RED (`3197106` test commit) → GREEN (`7b6bd86` feat commit). Gate sequence compliant.
- Task 3: RED (`1f56434` test commit) → GREEN (`e1b7778` feat commit). Gate sequence compliant.

No REFACTOR phase was needed — initial implementations were idiomatic and within scope. Code was not touched post-GREEN.

## Self-Check: PASSED

- All 7 target files present on disk (1 modified + 2 new source modules + 3 new test files + SUMMARY.md)
- All 6 task commits present in git log (3 RED test commits + 3 GREEN feat commits)
- All success-criteria grep checks pass (ComfyClient regression guards at ZERO, canonical import present)
- All 14 plan-level tests pass; 1123 total test suite green

---

*Phase: 19-social-media-posting-system*
*Plan: 07*
*Completed: 2026-04-21*
