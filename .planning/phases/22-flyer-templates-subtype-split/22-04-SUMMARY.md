---
phase: 22-flyer-templates-subtype-split
plan: 04
subsystem: api-schema + pipeline-orchestrator
tags: [pydantic, fastapi-request-schema, pipeline, kwargs-threading, back-compat, tdd]

# Dependency graph
requires:
  - 22-01 (FlyerTemplateSchema + load_template)
  - 22-02 (FlyerInput + EventInput alias + LayoutZones/ResolvedLayout relaxation)
  - 22-03 (PosterComposer.compose accepts template kwarg)
provides:
  - FlyerCreateRequest.template required str (min_length=1, max_length=64)
  - FlyerCreateRequest.event annotated as FlyerInput (was EventInput; alias-equivalent)
  - FlyerGenerator.generate(*, template: FlyerTemplateSchema | None = None) keyword-only param
  - Pipeline retry loop forwards template= to composer.compose on the approval branch
affects:
  - 22-05 (worker): task_generate_flyer must read payload["template"], call load_template(payload["template"]) before Comfy work, and pass template into FlyerGenerator.generate(..., template=template)
  - 22-05 (DB): FlyerRecord must gain a template column (separate plan scope)
  - 22-11 (frontend): POST body must include "template": "<slug>"
  - tests/api/test_flyer_routes.py + tests/api/test_worker_tasks.py — 2+ tests now fail because they POST without template; Plan 05 fixes those

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Required-field plumbing parity with brochure: `template: str = Field(min_length=1, max_length=64)` mirrors BrochureCreateRequest verbatim"
    - "TYPE_CHECKING import for FlyerTemplateSchema in pipeline.py — avoids runtime cycle for CLI/direct callers that don't pass a template"
    - "Keyword-only kwarg with default None preserves positional back-compat for FlyerGenerator.generate(event)"
    - "Late-binding template plumb: schema accepts free-form `template: str`; validation happens at worker `load_template()` time per CONTEXT decision"

key-files:
  created:
    - tests/unit/test_pipeline_template_threading.py  (4 tests, 213 lines)
  modified:
    - flyer_generator/api/schemas/flyers.py
    - flyer_generator/pipeline.py
    - tests/api/test_schemas.py

key-decisions:
  - "Renamed import EventInput -> FlyerInput in flyers.py and pipeline.py for canonical naming. Behavior identical because EventInput = FlyerInput is a module-level alias from Plan 22-02."
  - "Added 9 tests for FlyerCreateRequest.template (vs the 6+ requested in the plan): covered 1-char and 64-char boundaries explicitly to lock the bounds. Also added test_template_wrong_type for 123 (int) which the plan listed as Test 5."
  - "Used `gen._comfy_client.generate` (not `.run`) as patch target — confirmed by reading flyer_generator/stages/comfy_client.py (the actual method name). Plan's example referenced `.run` which would have raised AttributeError; this is documented in the threading test for Plan 05's reference."
  - "Patched _preprocessor.upscale alongside the other stages because pipeline.py performs upscale between comfy and vision; without patching it, the test would attempt to upscale the mock comfy bytes through real Pillow code."
  - "Did NOT remove EventInput import from pipeline.py — it remains alongside FlyerInput for any in-file reference and keeps the import diff minimal. Both are aliases of the same class."

requirements-completed: [FT-01, FT-03]

# Metrics
duration: ~25min
completed: 2026-04-23
---

# Phase 22 Plan 04: API Schema + Pipeline Template Plumbing Summary

Threaded the flyer `template` slug through the API request schema (`FlyerCreateRequest`) and the pipeline orchestrator (`FlyerGenerator.generate`) down to the composer. After this plan, `POST /api/v1/flyers` requires a `template` field and the pipeline forwards a `FlyerTemplateSchema` (or None) to `PosterComposer.compose` on every approval branch of the retry loop. FT-01 (API-boundary half) + FT-03 (pipeline plumbing) are now satisfied.

## What Was Built

### Task 1 — `FlyerCreateRequest.template` required field (commits `49f852d` RED, `5a501e1` GREEN)

**`flyer_generator/api/schemas/flyers.py` (final shape):**

```python
"""POST /api/v1/flyers request schema — wraps FlyerInput (event/info subtype)."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from flyer_generator.models import FlyerInput

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class FlyerCreateRequest(BaseModel):
    """Body of POST /api/v1/flyers.

    Re-uses FlyerInput verbatim (no field-by-field redefinition). Adds API-layer
    options: template slug (mirrors brochure; validated at worker-time via
    load_template()), preset, optional brand-kit slug, optional accent
    override, optional max background retry cap.
    """

    model_config = ConfigDict(extra="forbid")

    event: FlyerInput
    template: str = Field(min_length=1, max_length=64)
    preset: str = Field(min_length=1, max_length=64)
    brand_kit_slug: str | None = Field(default=None, max_length=64)
    accent: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    max_bg_attempts: int | None = Field(default=None, ge=1, le=10)

    @field_validator("brand_kit_slug")
    @classmethod
    def _validate_slug(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not _SLUG_RE.match(v):
            raise ValueError("brand_kit_slug must match ^[a-z0-9][a-z0-9-]*$")
        return v
```

**Changes:**
- Module docstring: `"...wraps EventInput."` → `"...wraps FlyerInput (event/info subtype)."`
- Import: `from flyer_generator.models import EventInput` → `from flyer_generator.models import FlyerInput`
- `event: EventInput` → `event: FlyerInput` (alias — semantically identical)
- New required field: `template: str = Field(min_length=1, max_length=64)` between `event` and `preset`

**Tests added in `tests/api/test_schemas.py::TestFlyerCreateRequestTemplate`** (9 tests):

1. `test_template_required` — missing template raises `ValidationError` mentioning the field
2. `test_template_min_length` — empty string rejected
3. `test_template_max_length` — 65-char string rejected
4. `test_template_wrong_type` — int 123 rejected
5. `test_event_subtype_info_without_event_fields` — info-subtype event accepted with only title/subtype/description/org/style_*
6. `test_valid_event_with_template_roundtrip` — `model_dump(mode="json")` round-trips
7. `test_extra_fields_forbidden` — top-level `"foo": "bar"` rejected (`ConfigDict(extra="forbid")` preserved)
8. `test_template_max_length_64_accepted` — 64-char boundary accepted
9. `test_template_min_length_1_accepted` — 1-char boundary accepted

**Existing test updated:**
- `test_flyer_create_request_round_trips_with_event_input` — added `template="editorial_classic"` to constructor call (was missing required field)
- `test_flyer_create_request_accepts_good_accent` — added `template="t"` to constructor call (Rule 3 fix — existing test broke once `template` became required)

### Task 2 — `FlyerGenerator.generate(*, template=...)` (commits `5d68e95` RED, `1e5d324` GREEN)

**`flyer_generator/pipeline.py` final signature:**

```python
async def generate(
    self,
    event: FlyerInput,
    *,
    template: "FlyerTemplateSchema | None" = None,
) -> FlyerOutput:
    """Run the full flyer generation pipeline.

    Args:
        event: FlyerInput (event or info subtype) — title + org +
            style_concept + style_preset are required; event-specific
            fields (date/time/location/fees) and info-specific fields
            (description/call_to_action) are optional and gated on
            ``event.subtype``.
        template: Optional FlyerTemplateSchema. When supplied, the
            composer reads typography / scrim opacity / accent color
            from the template instead of the Phase-21 hardcoded
            defaults. When ``None``, preserves pre-Phase-22 byte-
            identical output (back-compat for CLI / direct callers).
    ...
    """
```

**Exact line numbers modified in `flyer_generator/pipeline.py` (for Plan 05 reference):**

| Change | Line(s) |
|---|---|
| Added `from typing import TYPE_CHECKING` | 7 |
| Added `FlyerInput` to models import | 15 |
| TYPE_CHECKING block importing `FlyerTemplateSchema` | 26-29 |
| `generate()` signature with `template` keyword-only param | 65-70 |
| Updated docstring | 71-87 |
| Composer call updated to forward `template=template` | 132-134 |

**`tests/unit/test_pipeline_template_threading.py` (4 tests, 213 lines):**

1. `TestPipelineSignature::test_generate_has_keyword_only_template_param` — `inspect.signature` exposes `template` as KEYWORD_ONLY with default `None`
2. `TestTemplateThreading::test_template_threaded_to_composer` — `gen.generate(event, template=tpl)` results in `composer.compose(..., template=tpl)`
3. `TestTemplateThreading::test_no_template_passes_none_to_composer` — back-compat: `gen.generate(event)` → `composer.compose(..., template=None)`
4. `TestTemplateThreading::test_template_passed_on_every_attempt_in_retry_loop` — vision rejects 2× then approves; composer is called exactly once and receives `template=tpl`

## FlyerGenerator Internal Stage Attribute Names (for Plan 05 patching reference)

These are the **real attribute names** the test patches successfully. Plan 05 (worker) and any future test that mocks pipeline internals can use them verbatim:

| Attribute | Type | Method patched |
|---|---|---|
| `self._prompt_builder` | `StylePromptBuilder` | `.build()` (sync) |
| `self._comfy_client` | `ComfyClient` | `.generate()` (async — note: NOT `.run()`) |
| `self._preprocessor` | `ImagePreprocessor` | `.upscale()` (sync) |
| `self._vision` | `VisionEvaluator` | `.evaluate()` (async) |
| `self._layout` | `LayoutResolver` | `.resolve()` (sync) |
| `self._composer` | `PosterComposer` | `.compose()` (sync) |
| `self._rasterizer` | `Rasterizer` | `.rasterize()` (sync) |

The plan's example referred to `_comfy_client.run` — that's incorrect; the actual method is `.generate()` returning `(ComfyJob, raw_bytes)` tuple. Plan 05 should use `.generate()`.

## Verification Run Log

```bash
# RED gate (Task 1)
.venv/bin/pytest tests/api/test_schemas.py::TestFlyerCreateRequestTemplate -q
# -> 5 failed, 4 passed (4 negative tests pass coincidentally because pydantic rejects "extra" template field)

# GREEN gate (Task 1)
.venv/bin/pytest tests/api/test_schemas.py::TestFlyerCreateRequestTemplate -q
# -> 9 passed

# Full test_schemas.py
.venv/bin/pytest tests/api/test_schemas.py -q
# -> 81 passed

# RED gate (Task 2)
.venv/bin/pytest tests/unit/test_pipeline_template_threading.py -q
# -> 3 failed, 1 passed (test_no_template_passes_none_to_composer passes coincidentally — kwargs.get("template") is None when no kwarg supplied)

# GREEN gate (Task 2)
.venv/bin/pytest tests/unit/test_pipeline_template_threading.py -q
# -> 4 passed

# Full unit suite
.venv/bin/pytest tests/unit/ -q
# -> 39 passed

# Full suite excluding Plan 04/05 deferrals
.venv/bin/pytest tests/ -q -k "not slow" \
  --deselect tests/api/test_flyer_routes.py \
  --deselect tests/api/test_worker_tasks.py
# -> 1378 passed, 19 deselected, 1 warning

# Plan acceptance — required-fields list
python -c "from flyer_generator.api.schemas.flyers import FlyerCreateRequest; print(FlyerCreateRequest.model_json_schema()['required'])"
# -> ['event', 'template', 'preset']

# Plan acceptance — generate signature contains template
python -c "import inspect; from flyer_generator import FlyerGenerator; print(list(inspect.signature(FlyerGenerator.generate).parameters))"
# -> ['self', 'event', 'template']

# Plan acceptance — runtime smoke
python -c "from flyer_generator.api.schemas.flyers import FlyerCreateRequest; req = FlyerCreateRequest.model_validate({'event': {'title':'T','date':'d','time':'t','location_name':'l','location_address':'a','fees':'f','org':'o','style_concept':'c','style_preset':'p'}, 'template':'editorial_classic', 'preset':'photorealistic'}); print(req.template)"
# -> editorial_classic
```

## Tests Now Failing (Plan 05 Will Fix)

`.venv/bin/pytest tests/api/test_flyer_routes.py tests/api/test_worker_tasks.py -q` — **2 failures, 15 passed**:

1. `tests/api/test_flyer_routes.py::test_post_flyer_returns_202` — POSTs to `/api/v1/flyers` without a `template` field, now returns 422 instead of 202.
2. `tests/api/test_flyer_routes.py::test_post_flyer_carries_brand_kit_slug_into_payload` — same root cause: missing `template` in the request body.

Both are deferred to Plan 22-05 per the plan's `<acceptance_criteria>` block: "tests/api/test_flyer_routes.py and tests/api/test_worker_tasks.py may show failures that Plan 05 will close". Plan 22-02-SUMMARY.md confirms this is a 19-test deselection scope.

## Acceptance Criteria — All Pass

### Task 1
- [x] `grep -n "template: str = Field" flyer_generator/api/schemas/flyers.py` returns exactly 1 line (line 26)
- [x] `grep -n "event: FlyerInput" flyer_generator/api/schemas/flyers.py` returns exactly 1 line (line 25)
- [x] `grep -n "from flyer_generator.models import FlyerInput" flyer_generator/api/schemas/flyers.py` returns exactly 1 line (line 9)
- [x] `grep -n "from flyer_generator.models import EventInput" flyer_generator/api/schemas/flyers.py` returns 0 lines (clean)
- [x] Runtime smoke prints `editorial_classic`
- [x] `TestFlyerCreateRequestTemplate` reports 9 tests passing (≥6 required)
- [x] `tests/api/test_schemas.py` whole file (81 tests) passes
- [x] tests/api/test_flyer_routes.py and test_worker_tasks.py failures noted (above)

### Task 2
- [x] `grep -n "template:" flyer_generator/pipeline.py` returns 2 lines (signature + docstring) — ≥2
- [x] `grep -n "template=template" flyer_generator/pipeline.py` returns 1 line (composer call site)
- [x] `grep -n "FlyerTemplateSchema" flyer_generator/pipeline.py` returns 3 lines (TYPE_CHECKING import + signature annotation + docstring)
- [x] `inspect.signature(FlyerGenerator.generate).parameters['template']` is KEYWORD_ONLY with default None — ✓
- [x] `tests/unit/test_pipeline_template_threading.py` reports 4 tests passing (≥3 required)
- [x] Existing `tests/unit/` callers don't construct `FlyerGenerator().generate(event)` outside this test, but every other test in the unit suite passes
- [x] Full suite (excluding deferrals) passes — 1378 passed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `test_flyer_create_request_accepts_good_accent` broke after template became required**

- **Found during:** Task 1 GREEN, immediately after the schema change.
- **Issue:** The existing parametrized test `test_flyer_create_request_accepts_good_accent` at `tests/api/test_schemas.py:396-398` constructed `FlyerCreateRequest(event=_event(), preset="p", accent=good_accent)` with no `template`. Once `template` became required, all 4 parametrized cases (`#F59E0B`, `#000000`, `#ffffff`, `#aAbBcC`) raised `ValidationError: template - Field required`.
- **Fix:** Added `template="t"` to the constructor call. The test still validates accent regex correctly — it just supplies a stub template since the test isn't about the template field.
- **Files modified:** `tests/api/test_schemas.py` line 397.
- **Committed in:** `5a501e1` (Task 1 GREEN — alongside the schema change).

**2. [Plan-correction] Plan example referenced `_comfy_client.run`; actual method is `.generate`**

- **Found during:** Task 2 RED test authoring.
- **Issue:** The plan's action text suggested patching `gen._comfy_client.run` with `AsyncMock`. Reading `flyer_generator/stages/comfy_client.py` showed the actual method is `async def generate(...)` returning `(ComfyJob, raw_bytes)`. Patching a non-existent attribute would raise `AttributeError` at test setup.
- **Fix:** Patched `_comfy_client.generate` instead. Set return value to a `(ComfyJob, raw_bytes)` tuple. Also added `_preprocessor.upscale` patch (which sits between comfy and vision in the pipeline; without patching it, the test would feed mock bytes to real Pillow code and explode).
- **Files modified:** `tests/unit/test_pipeline_template_threading.py`.
- **Committed in:** `5d68e95` (Task 2 RED).
- **Note for Plan 05:** Use `_comfy_client.generate`, not `.run`.

**Total deviations:** 2 — both auto-fixed (1 blocking-test fix, 1 plan-example correction). No scope creep.

## Threat Model Posture

- **T-22-08 (Tampering: `FlyerCreateRequest.template` user-supplied) — mitigate**: `Field(min_length=1, max_length=64)` enforced at schema layer. Tests `test_template_min_length` and `test_template_max_length` regress against bound bypass attempts. Worker-side path-traversal mitigation is Plan 05 scope (`load_template(slug)` only appends `.json` to safe registry path).
- **T-22-09 (DoS via pathological `template` values) — accept**: 64-char bound caps payload size. Unicode-bomb / lexer-exhaustion vectors are explicitly Phase 26 scope.

## Threat Flags

None — no new trust boundaries introduced. The `template` field becomes a first-class part of an already-trust-bounded HTTP→API surface. No file system / database / network changes in this plan.

## Known Stubs

None — `template` is a free-form `str` validated at the schema layer; full validation (slug-shape + filesystem existence) is Plan 05's scope per the locked CONTEXT decision. This is intentional separation, not a stub.

## Next Phase Readiness (for Plan 05)

The two plumbing layers are now in place. Plan 05 must:

1. **Worker (`flyer_generator/api/tasks/flyer.py::task_generate_flyer`):**
   - Read `payload["template"]` (a string slug, e.g. `"editorial_classic"`).
   - Call `template = load_template(payload["template"])` BEFORE any Comfy work — fail fast with `FileNotFoundError` on typo.
   - Call `FlyerGenerator(...).generate(event, template=template)` — composer will then drive typography/scrim/accent from the loaded schema.
2. **DB model (`flyer_generator/api/models/flyer.py::FlyerRecord`):**
   - Add `template: Mapped[str]` column.
   - Alembic migration to add the column.
3. **Route handler (`flyer_generator/api/routes/flyers.py`):**
   - Pass `body.template` into the worker payload (the request schema already validates it).
4. **Test fixtures:**
   - `tests/api/test_flyer_routes.py` and `tests/api/test_worker_tasks.py` — add `"template": "<slug>"` to all test request bodies (closes the 2 currently-failing tests + 17 deselected).

## TDD Gate Compliance

Plan-level type was `tdd="true"` for both tasks. Both gates satisfied with explicit RED → GREEN commits:

- **Task 1 RED:** `49f852d` `test(22-04): add failing tests for FlyerCreateRequest.template + subtype-info event`
- **Task 1 GREEN:** `5a501e1` `feat(22-04): add required template field to FlyerCreateRequest`
- **Task 2 RED:** `5d68e95` `test(22-04): add failing tests for FlyerGenerator.generate template threading`
- **Task 2 GREEN:** `1e5d324` `feat(22-04): thread template kwarg through FlyerGenerator.generate`

No REFACTOR commits needed — both tasks were minimal-correct on first GREEN pass.

## Self-Check: PASSED

Verified each created/modified file exists and each commit hash is reachable:

- `flyer_generator/api/schemas/flyers.py` FOUND (modified)
- `flyer_generator/pipeline.py` FOUND (modified)
- `tests/api/test_schemas.py` FOUND (modified)
- `tests/unit/test_pipeline_template_threading.py` FOUND (created)
- Commit `49f852d` (Task 1 RED) FOUND
- Commit `5a501e1` (Task 1 GREEN) FOUND
- Commit `5d68e95` (Task 2 RED) FOUND
- Commit `1e5d324` (Task 2 GREEN) FOUND

---

*Phase: 22-flyer-templates-subtype-split*
*Completed: 2026-04-23*
