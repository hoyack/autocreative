---
phase: 22-flyer-templates-subtype-split
plan: 02
subsystem: models + vision
tags: [models, vision-prompt, subtype, backward-compat]
requires:
  - Phase 22 CONTEXT locked decisions (subtype split, vision prompt branching, LayoutZones relaxation)
provides:
  - FlyerInput Pydantic model (event+info via subtype Literal)
  - EventInput back-compat alias (= FlyerInput)
  - VISION_SYSTEM_PROMPT_EVENT (renamed from VISION_SYSTEM_PROMPT)
  - VISION_SYSTEM_PROMPT_INFO (new)
  - VISION_SYSTEM_PROMPT (alias for VISION_SYSTEM_PROMPT_EVENT, preserved)
  - VisionEvaluator.evaluate() subtype branching
  - VisionEvaluator._call_backend() seam (background + user_text + per-call system_prompt override)
  - Relaxed LayoutZones (details/fee_badge Optional)
  - Relaxed ResolvedLayout (details/fee_badge Optional)
affects:
  - flyer_generator/stages/composer.py (Plan 03): must guard against verdict.zones.details / fee_badge / layout.details / layout.fee_badge being None on info flyers
  - flyer_generator/stages/layout.py (Plan 03): must emit None for details/fee_badge when zones.details/fee_badge are None
  - flyer_generator/pipeline.py (Plan 03/04): flyer_input.subtype drives render kind (flyer_event_final | flyer_info_final)
  - flyer_generator/api/schemas/flyers.py + api/tasks/flyer.py (Plan 04): FlyerCreateRequest + worker now see subtype + optional event fields + description/call_to_action
tech-stack:
  added: []
  patterns:
    - "Single-model + Literal discriminator (not discriminated union) — matches CONTEXT decision"
    - "Per-call system_prompt override threaded through private backend helpers (kwargs-only)"
    - "Back-compat via module-level alias: old name = new name"
key-files:
  created:
    - tests/unit/__init__.py
    - tests/unit/test_models_flyer_input.py
    - tests/unit/test_vision_subtype_prompt.py
  modified:
    - flyer_generator/models.py
    - flyer_generator/__init__.py
    - flyer_generator/stages/vision.py
decisions:
  - "FlyerInput uses `subtype: Literal['event', 'info'] = 'event'` (not discriminated union) — preserves existing API contract for callers that omit subtype"
  - "`EventInput = FlyerInput` module-level alias kept through at least Phase 23 to avoid breaking external callers mid-milestone"
  - "Vision backend helpers accept `system_prompt` as a keyword-only override; when None, fall back to `self._system_prompt` — preserves brochure's `evaluate_cover` path that sets its own system_prompt via __init__"
  - "Introduce `_call_backend(*, background, user_text, system_prompt)` wrapper for test patching; it forwards to `_evaluate_with_text(background.image_bytes, user_text, system_prompt=...)`. Direct byte callers (evaluate_cover) keep calling `_evaluate_with_text` unchanged"
  - "Relax `LayoutZones.details` and `LayoutZones.fee_badge` to `Optional[ZoneName]` rather than introducing a second model variant — less invasive and matches how Plan 03 composer will handle missing keys"
  - "Also relax `ResolvedLayout.details` / `fee_badge` in lockstep; Plan 03 will add None guards before rendering those blocks"
metrics:
  duration_minutes: ~15
  tasks_completed: 2
  tests_added: 19 (12 FlyerInput + 7 vision subtype)
  tests_total_passing: 1314
  completed_date: 2026-04-23
---

# Phase 22 Plan 02: FlyerInput + Vision Subtype Branching Summary

Evolved `EventInput` → `FlyerInput` with a `subtype` Literal discriminator and relaxed event-specific fields; made `LayoutZones` / `ResolvedLayout` tolerate missing `details` / `fee_badge`; branched the Claude vision system prompt on subtype so info flyers get a TITLE+DESCRIPTION+ORG_CREDIT schema instead of the event schema. `EventInput` and the old `VISION_SYSTEM_PROMPT` constant remain as aliases so nothing downstream breaks.

## What Was Built

### Task 1 — FlyerInput + LayoutZones relaxation + re-exports (commit `4282667`, RED `98451b8`)

**`flyer_generator/models.py`:**
- Renamed `class EventInput(BaseModel)` → `class FlyerInput(BaseModel)` (models.py line 27).
- Added `subtype: Literal["event", "info"] = "event"` (line 37).
- Made `date`, `time`, `location_name`, `location_address`, `fees` all `str | None = Field(default=None, max_length=120)` (lines 40–44). `max_length=120` preserved.
- Added info-only fields: `description: str | None = Field(default=None, max_length=600)` and `call_to_action: str | None = Field(default=None, max_length=120)` (lines 46–47).
- Kept `org`, `url`, `style_concept`, `style_preset`, `color_accent`, and the `_validate_hex_color` field_validator unchanged.
- Added `EventInput = FlyerInput` back-compat alias at line 66 with a deprecation comment.
- Relaxed `LayoutZones`: `details: ZoneName | None = None` and `fee_badge: ZoneName | None = None` (lines 97–98), `title` and `org_credit` unchanged.
- Relaxed `ResolvedLayout`: `details: ZoneCoord | None = None` and `fee_badge: ZoneCoord | None = None` (lines 115–116).

**`flyer_generator/__init__.py`:**
- Import now reads `from flyer_generator.models import EventInput, FlyerInput, FlyerOutput` (line 12).
- `generate_flyer()` signature annotated as `event: FlyerInput` (line 18) — alias-compatible, so any existing caller passing an `EventInput` instance continues to work.
- `__all__` now lists `"FlyerInput"` ahead of `"EventInput"` with an inline `# deprecated alias for FlyerInput` comment (lines 36–37).

**`tests/unit/__init__.py`** (new, empty) and **`tests/unit/test_models_flyer_input.py`** (new, 151 lines, 12 tests) — cover minimal-event / minimal-info / fully-populated-event / bogus-subtype-rejected / description-max-length / call-to-action-accepted / alias-identity / legacy-payload back-compat / package-level re-export / LayoutZones relaxation (details+fee_badge optional, info shape, event shape).

**Verification:**
- `.venv/bin/pytest tests/unit/test_models_flyer_input.py -q` → **12 passed**
- `.venv/bin/pytest tests/ -q -k "not slow" --deselect tests/api/test_flyer_routes.py --deselect tests/api/test_worker_tasks.py` → **1307 passed, 19 deselected** (Plan 04/05 deferrals)

### Task 2 — Vision subtype-aware system prompts + evaluate() branching (commit `4b3ebcd`, RED `c3c0188`)

**`flyer_generator/stages/vision.py`:**
- Changed `from flyer_generator.models import EventInput` → `FlyerInput` (line 24) — alias identity preserves behavior.
- Renamed the existing `VISION_SYSTEM_PROMPT = """..."""` constant to `VISION_SYSTEM_PROMPT_EVENT` (line 30). **Body text is verbatim the original** — no wording changed.
- Added `VISION_SYSTEM_PROMPT_INFO` (line 68) per the locked spec in `22-02-PLAN.md` lines 353–381: TITLE + DESCRIPTION + ORG_CREDIT, `zones.details` / `zones.fee_badge` MUST be null, nine-cell 3×3 zone-name glossary included.
- Added `VISION_SYSTEM_PROMPT = VISION_SYSTEM_PROMPT_EVENT` back-compat alias (line 100). `tests/test_vision.py` lines 112/234/422 assert against `VISION_SYSTEM_PROMPT` — these keep passing verbatim because the alias resolves to the event prompt and event flyers still produce that prompt.
- Rewrote `VisionEvaluator.evaluate(background, event)` (lines 140–179) to:
    - If `event.subtype == "info"`: set `system_prompt = VISION_SYSTEM_PROMPT_INFO`; build user text from `Headline / Description / Call to action / Organizer / Style`.
    - Else: set `system_prompt = VISION_SYSTEM_PROMPT_EVENT`; build user text from `Event / Date / Time / Venue / Address / Fees / Organizer / Style` (every event field uses `… or ''` to tolerate the newly-optional `None`s).
    - Call `self._call_backend(background=..., user_text=..., system_prompt=...)`.
- Added **`async def _call_backend(*, background, user_text, system_prompt=None)`** (lines 180–201) — thin wrapper around `_evaluate_with_text`. This is the new patch seam the subtype test targets via `patch.object(ev, "_call_backend", ...)`.
- Updated `_evaluate_with_text` signature to `_evaluate_with_text(self, image_bytes, user_text, *, system_prompt: str | None = None)` (lines 203–248). When `system_prompt` is None, falls back to `self._system_prompt` (preserves existing `evaluate_cover` path used by brochure, which constructs the evaluator with a brochure-specific `system_prompt` via `__init__`).
- Threaded the `system_prompt` kwarg through `_call_anthropic`, `_call_anthropic_retry`, `_call_ollama`, `_call_ollama_retry` — each now accepts `*, system_prompt: str | None = None`. All four compute `effective_system = system_prompt or self._system_prompt` before sending to the vendor API. No callsite outside `_evaluate_with_text` is required to pass the kwarg, so brochure callsites remain unchanged.

**`tests/unit/test_vision_subtype_prompt.py`** (new, 157 lines, 7 tests) — cover prompt-constant exports, back-compat alias identity, INFO prompt content (contains TITLE/DESCRIPTION/ORG_CREDIT/"null", omits FEE_BADGE/DETAILS), EVENT prompt content (contains all four zones), and evaluate() branching (event path selects EVENT prompt + Date/Fees/Venue user text; info path selects INFO prompt + Headline/Description/Call to action user text, omits Date/Fees).

**Verification:**
- `.venv/bin/pytest tests/unit/test_vision_subtype_prompt.py -q` → **7 passed**
- `.venv/bin/pytest tests/test_vision.py tests/brochure/test_vision.py -q` → **29 passed** (all existing vision + brochure-cover tests unchanged)
- `.venv/bin/pytest tests/ -q -k "not slow" --deselect tests/api/test_flyer_routes.py --deselect tests/api/test_worker_tasks.py` → **1314 passed, 19 deselected**

## Signature Reference (for Plans 03 / 04 / 05)

**Private vision backend entry point:** `VisionEvaluator._call_backend(*, background: GeneratedBackground, user_text: str, system_prompt: str | None = None) -> VisionVerdict` — forwards to `_evaluate_with_text(background.image_bytes, user_text, system_prompt=system_prompt)`.

**Shared internal path:** `VisionEvaluator._evaluate_with_text(image_bytes: bytes, user_text: str, *, system_prompt: str | None = None) -> VisionVerdict` — unchanged for brochure callsite (`evaluate_cover` does not pass `system_prompt`; the evaluator's `self._system_prompt` is set via `__init__`).

**Public vision entry point:** `VisionEvaluator.evaluate(background: GeneratedBackground, event: FlyerInput) -> VisionVerdict` — branches on `event.subtype`.

**Public flyer model:** `flyer_generator.models.FlyerInput` — same class as `flyer_generator.models.EventInput` (alias). Both also re-exported from `flyer_generator` package root.

## Deviations from Plan

None — the plan executed exactly as written. The only minor judgement call was adding a `call_to_action_accepted` test beyond the 10 listed in the plan's `<behavior>` section, giving 12 FlyerInput tests total (plan asked for ≥10). Every plan acceptance criterion and verification gate passed.

## Test File Updates

**No existing test file needed to be updated.** Because:
- The `EventInput` alias means every existing test that constructs `EventInput(date=..., time=..., ...)` continues to validate the same fields with the same constraints.
- `VISION_SYSTEM_PROMPT` is an alias for `VISION_SYSTEM_PROMPT_EVENT`, so `tests/test_vision.py` lines 112/234/422 (three assertions against the constant) keep their existing semantics — they are assertions that the *event* flyer path sends the event prompt, which is exactly what the new subtype-branching code does when given the existing event `EventInput` fixture.
- `LayoutZones` field relaxation (required → Optional with default None) is backward-compatible — every existing test that calls `LayoutZones(title="...", details="...", fee_badge="...")` keeps validating.

## Deferred Issues

`tests/api/test_flyer_routes.py` and `tests/api/test_worker_tasks.py` were deselected per the plan's acceptance criteria — these will be updated in Plan 04 / 05 when the API schemas and worker task grow the `template` column and `subtype`-aware enqueue path. This is expected and documented in 22-02-PLAN.md line 323.

## Threat Model Posture

- **T-22-04 (Tampering: FlyerInput.subtype accepted as arbitrary string) — mitigated**: `subtype: Literal["event", "info"]` rejects all other values with `ValidationError`. Test `TestFlyerInputDefaults.test_bogus_subtype_rejected` asserts this behavior.
- **T-22-03 (Spoofing / injection via description) — accepted**: The new `description` field (max 600 chars) is interpolated into the info vision user text verbatim, inheriting the existing vision-layer posture. Prompt-injection hardening is Phase 26 (ADV-01).
- **T-22-05 (Information disclosure via prompt) — accepted**: `VISION_SYSTEM_PROMPT_INFO` contains no secrets or PII; same stance as the existing event prompt.

## Self-Check: PASSED

- flyer_generator/models.py: FOUND
- flyer_generator/__init__.py: FOUND
- flyer_generator/stages/vision.py: FOUND
- tests/unit/__init__.py: FOUND
- tests/unit/test_models_flyer_input.py: FOUND
- tests/unit/test_vision_subtype_prompt.py: FOUND
- Commit 98451b8 (test RED Task 1): FOUND
- Commit 4282667 (feat GREEN Task 1): FOUND
- Commit c3c0188 (test RED Task 2): FOUND
- Commit 4b3ebcd (feat GREEN Task 2): FOUND

## TDD Gate Compliance

- **Task 1** — RED commit `98451b8` `test(22-02): add failing tests for FlyerInput + LayoutZones relaxation` → GREEN commit `4282667` `feat(22-02): rename EventInput to FlyerInput with subtype + optional event fields`. No REFACTOR pass needed.
- **Task 2** — RED commit `c3c0188` `test(22-02): add failing tests for vision subtype-aware prompts` → GREEN commit `4b3ebcd` `feat(22-02): branch vision system prompt on flyer subtype`. No REFACTOR pass needed.

All gates satisfied.
