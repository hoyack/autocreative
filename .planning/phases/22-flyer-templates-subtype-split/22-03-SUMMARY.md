---
phase: 22-flyer-templates-subtype-split
plan: 03
subsystem: composer
tags: [composer, svg, template-driven, subtype-aware, back-compat, xml-escape]

# Dependency graph
requires:
  - 22-01 (FlyerTemplateSchema + load_template)
  - 22-02 (FlyerInput.subtype + LayoutZones/ResolvedLayout details/fee_badge relaxation)
provides:
  - PosterComposer.compose(*, template: FlyerTemplateSchema | None = None) — keyword-only param
  - Five private template helpers on PosterComposer (_template_heading_family, _template_body_family, _template_scrim_opacity, _template_accent, _template_cover_title_size)
  - _build_details_elements helper (extracted event-subtype details block)
  - _build_info_description_elements helper (info-subtype description + CTA renderer)
  - Module-level _DEFAULT_HEADING_FAMILY / _DEFAULT_BODY_FAMILY / _DEFAULT_SCRIM_OPACITY_TOP / _DEFAULT_SCRIM_OPACITY_BOTTOM constants documenting the back-compat fallback values
  - _gradient_defs(fade_color, scrim_top, scrim_bottom) — opacity values are now parameters
affects:
  - 22-04 (pipeline.py): pipeline must thread template=template into composer.compose
  - 22-05 (worker): task_generate_flyer must load_template(payload['template']) and pass it through pipeline.generate
  - All future flyer-rendering callsites: template kwarg defaults to None (back-compat)

# Tech tracking
tech-stack:
  added: []  # No new deps — re-uses xml.sax.saxutils.escape, FlyerTemplateSchema from Plan 01
  patterns:
    - "Template-driven helpers with hardcoded fallbacks: every helper accepts template: FlyerTemplateSchema | None and returns a hardcoded constant when None — preserves byte-identical Phase-21 output for callers that omit the kwarg"
    - "TYPE_CHECKING import for FlyerTemplateSchema to avoid the brochure -> validate_hex_color runtime cycle for callers that never pass a template"
    - "Subtype dispatch via local is_info = event.subtype == 'info' boolean — used at three gates (details, fee badge, content_blocks assembly)"
    - "Defensive double-gate pattern: not is_info AND layout.X is not None — composer treats either signal as a skip-render directive (matches relaxed LayoutZones from Plan 02 + the locked subtype contract from CONTEXT)"
    - "Title font_size = template.cover_title_size (override) but max_chars still computed by length-bucket — the bucket's role is wrap-width planning, not type sizing"
    - "Description text wraps via existing _wrap_text helper (XML entities like &amp; / &lt; contain no whitespace, so word-boundary wrapping stays safe)"

key-files:
  created:
    - tests/unit/test_composer_template_driven.py  (16 tests)
  modified:
    - flyer_generator/stages/composer.py  (475 -> ~770 lines; ~402 insertions, 105 deletions)

key-decisions:
  - "Template's cover_title_size REPLACES the bucket default (it does not multiply or scale by length). The length-bucket logic in _title_params still drives max_chars (wrap budget), but the returned font_size is overridden by template when supplied. Rationale: templates declare a single visual scale; auto-shrink belongs to the bucket fallback only."
  - "Date element kept in 'Arial Black, Arial, sans-serif' (heading-feel) family even when template provides body_family. Date is the visual anchor of the details block — promoting it to body family would weaken the date->time->venue hierarchy. Templates that want a different date treatment can override via template.typography.heading_family which IS read for the title (consistent with cover_title role)."
  - "Optional date/time/venue/address/fees fields (Plan 02 relaxation) now safely XML-escape via `escape(field) if field else \"\"`. The pre-refactor composer would have crashed on info-subtype None values (`'NoneType' has no attribute replace`) — the new test_info_flyer_with_no_template_still_works regression test caught this."
  - "_build_info_description_elements is a NEW helper (not a reuse of details-block wrapping). The details block has fixed-position date/time/venue/address rows; description is free-form prose that needs word-wrap with overflow into multiple lines. Reused _wrap_text() for the word-boundary algorithm."
  - "Layout variant heuristic gracefully degrades for info flyers (where verdict.zones.details is None): falls back to centered/sidebar/minimal based on title row+col alone, never tries to dereference details_row."
  - "Body font is used for org_credit, fee badge text, time/venue/address, and the new info description+CTA. Template-supplied body_family flows through everywhere a non-title text element is rendered."

# Metrics
duration: ~25min
completed: 2026-04-23

requirements-completed: [FT-03]
---

# Phase 22 Plan 03: Template-Driven Composer + Subtype Rendering Summary

Refactored `PosterComposer` so its `compose()` method accepts an optional `template: FlyerTemplateSchema | None` keyword parameter and reads typography, scrim opacity, and accent color from the template instead of hardcoded constants. When `template is None`, the composer falls back to Phase-21 hardcoded values byte-identically. The composer is also subtype-aware: when `event.subtype == "info"` it skips the fee badge and details block, instead rendering `event.description` + `event.call_to_action` in the title-adjacent region. Satisfies FT-03.

## Performance

- **Duration:** ~25 minutes
- **Tasks:** 1 (TDD with RED -> GREEN gates)
- **Files created:** 1 (test file, 340 lines, 16 tests)
- **Files modified:** 1 (composer.py: 475 -> ~770 lines, ~402 insertions / 105 deletions)
- **New tests:** 16 — all pass
- **Existing composer tests:** 21 — all still pass (back-compat verified)
- **Broader suite:** 1365 passing, 19 deferred (Plans 04/05)

## Task Commits

TDD RED -> GREEN:

1. **Task 1 RED:** `809ab46` — `test(22-03): add failing tests for template-driven composer + subtype rendering` (15/16 fail with TypeError on missing template kwarg + 1 passes back-compat smoke)
2. **Task 1 GREEN:** `485ecc4` — `feat(22-03): template-driven + subtype-aware PosterComposer` (all 16 new + 21 existing tests pass)

No REFACTOR commit — code was written minimal-correct on first pass.

## Hardcoded Values Parameterized (line numbers before/after)

| Knob | Before (line) | After (line) | Source |
|---|---|---|---|
| Title font family `'Arial Black', 'Helvetica Neue', Arial, sans-serif` | composer.py:247 | composer.py:344 (`title_font = self._template_heading_family(template)`) | template.typography.heading_family |
| Body font family for time/venue/address/url/org_credit/fee-badge text | composer.py:353,359,364,371,372,419 | composer.py:345 (`body_font = ...`) threaded through `_build_details_elements` and emitted by org_credit + fee text | template.typography.body_family |
| Scrim opacity top `0.75` | composer.py:137 (in `_gradient_defs`) | composer.py:166 (parameter `scrim_top`), supplied by `_template_scrim_opacity(template, "top")` at composer.py:562 | template.palette.scrim_opacity_top |
| Scrim opacity bottom `0.85` | composer.py:142 | composer.py:170, supplied by `_template_scrim_opacity(template, "bottom")` at composer.py:563 | template.palette.scrim_opacity_bottom |
| Accent stripe color `event.color_accent` (hardcoded source: event field, not template) | composer.py:227,447 | composer.py:341 (`accent_color = self._template_accent(template, event.color_accent)`); flows to all rect/circle/line accent uses | template.palette.accent_default (overrides event.color_accent) |
| Title font_size length-bucket result (52/62/72/82) | composer.py:38,40,42,44 (in `_title_params`) | composer.py:355-356 (`bucket_font_size = _title_params(...)` then `font_size = self._template_cover_title_size(template, bucket_font_size)`) | template.typography.cover_title_size (replaces bucket default) |
| Middle radial scrim opacity `0.6` | composer.py:145 | composer.py:175 (still hardcoded — templates don't declare middle-scrim opacity in the current schema) | n/a (deliberately not parameterized) |

## Auto-shrink vs Template `cover_title_size` Interaction

The Phase-21 `_title_params` step-function returns `(font_size, max_chars)` based on `len(title)`. After the refactor:

- **`max_chars`** still comes from the bucket — this is the wrap budget for `_wrap_text`, sized to the safe horizontal margin minus the title's expected character width.
- **`font_size`** is now `self._template_cover_title_size(template, bucket_font_size)` — the template's declared size REPLACES the bucket default.

This means a template with `cover_title_size=88` (e.g. `editorial_classic`) renders all titles at 88pt regardless of length. Long titles will still wrap to multiple lines (because `max_chars` drops with the bucket), but each line stays at 88pt. This matches the design intent that templates declare a single visual scale.

If a future plan wants to auto-shrink within a template (e.g. "use template's size as a max, scale down for long titles"), the helper signature already accepts the bucket default, so the override could be reformulated as `min(template_size, bucket_size)`. Out of scope for FT-03.

## Info-Flyer Description Wrapping — New Helper

The plan suggested potentially reusing the details-block wrapping pattern. After inspection:

- The details block has **5 fixed-row text elements** (date / time / separator / venue / address [+ optional url]) at hardcoded y-offsets (`dy - 40`, `dy + 15`, `dy + 90`, `dy + 130`, `dy + 210`). Each row is a single `<text>`, no wrapping.
- The description block needs **free-form word-wrapped prose** that may produce 1–4 lines depending on content + `max_chars_per_line` (32 by default from `template.typography.body_max_chars_per_line`).

These are different rendering models, so `_build_info_description_elements` is a NEW helper. It does reuse the existing `_wrap_text` function for word-boundary wrapping with widow-merge — that's the only line-breaking primitive the codebase has, and it works correctly on XML-escaped strings (entity sequences like `&amp;` contain no whitespace so word-boundary wrap is safe).

Description renders below the title with an 80px gap (room for the accent line). When `event.call_to_action` is also present, it renders below the description with `body_size + 4` for mild emphasis and `font-weight="bold"`.

When BOTH `event.description` AND `event.call_to_action` are None, `_build_info_description_elements` returns `[]` and the info flyer ends up with title + accent + org credit + accent stripe only.

## Code Smell Reminder for Plans 04 / 05

The pipeline entry point `FlyerGenerator.generate` in `flyer_generator/pipeline.py` calls `self._composer.compose(event, background, verdict, layout)` (no template kwarg). For Plan 04, that callsite needs to:

1. Accept `template: FlyerTemplateSchema | None = None` on `FlyerGenerator.generate`.
2. Forward it: `self._composer.compose(event, background, verdict, layout, template=template)`.

Plan 22-PATTERNS line 600-601 shows the target pattern: `svg = self._composer.compose(event, background, verdict, layout, template=template)`. Until Plan 04 lands, all pipeline-driven flyer renders use the back-compat (template=None) path — which is byte-identical to Phase-21 output, so nothing breaks in the meantime.

For Plan 05, the worker (`flyer_generator/api/tasks/flyer.py::task_generate_flyer`) must:

1. Read `payload["template"]` (a string, e.g. `"editorial_classic"`).
2. Call `template = load_template(payload["template"])` BEFORE any Comfy work (so a typo fails fast with `FileNotFoundError`).
3. Pass `template` into `FlyerGenerator.generate(..., template=template)`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Composer crashed on info-subtype None values for date/time/venue/address/fees**

- **Found during:** Task 1 RED (the `test_info_flyer_with_no_template_still_works` test).
- **Issue:** Plan 02 made `FlyerInput.{date, time, location_name, location_address, fees}` Optional, but the Phase-21 composer called `escape(event.date)` etc. unconditionally. For info flyers (where these are `None`), this raised `'NoneType' object has no attribute 'replace'` inside `xml.sax.saxutils.escape`, surfaced as `CompositionError: SVG composition failed: 'NoneType' object has no attribute 'replace'`.
- **Fix:** Each optional field now uses `escape(field) if field else ""` — falsy-safe and produces an empty string when absent. The empty-string sentinel is what the existing `if fees_esc:` gate already expected, so downstream logic continues to no-op cleanly.
- **Files modified:** `flyer_generator/stages/composer.py` (lines 320-326)
- **Test coverage:** `test_info_flyer_with_no_template_still_works` regresses against this.
- **Committed in:** `485ecc4` (Task 1 GREEN)

**2. [Rule 2 - Missing critical functionality] Layout variant heuristic dereferenced verdict.zones.details unconditionally**

- **Found during:** Task 1 GREEN (during the `not is_info` refactor pass).
- **Issue:** `_select_layout_variant(title_row, details_row, title_col)` requires `details_row`, computed from `verdict.zones.details.split("_")[0]`. For info flyers, `verdict.zones.details is None` (Plan 02 contract), so the unconditional `verdict.zones.details.split("_")[0]` would have AttributeError'd. The pre-refactor code did the same dereference at composer.py:263.
- **Fix:** Guarded the call: when `verdict.zones.details is None`, the variant is picked from title row+col alone (`sidebar` for LEFT, `centered` for TOP+CENTER, `minimal` otherwise). This matches the spirit of `_select_layout_variant` — it's a heuristic, and for info flyers the title<->details axis it was designed around doesn't exist.
- **Files modified:** `flyer_generator/stages/composer.py` (lines 384-396)
- **Test coverage:** All `TestSubtypeRendering` tests exercise info-subtype paths; the variant fallback is reached implicitly.
- **Committed in:** `485ecc4` (Task 1 GREEN)

**3. [Rule 3 - Blocking] _get_scrim_zones dereferenced details_zone unconditionally**

- **Found during:** Task 1 GREEN.
- **Issue:** `_get_scrim_zones(title_zone, details_zone)` called `details_zone.split("_")[0]` unconditionally — would AttributeError for info flyers where `verdict.zones.details is None`.
- **Fix:** Made `details_zone: str | None`; skip the `rows.add` for that side when None.
- **Files modified:** `flyer_generator/stages/composer.py` (lines 122-129).
- **Committed in:** `485ecc4` (Task 1 GREEN).

**Total deviations:** 3 auto-fixed (1 bug, 1 missing functionality, 1 blocking — all caused by Plan 02's LayoutZones / FlyerInput Optional-field relaxation that Plan 03's refactor scope was inevitably going to touch).

**Impact on plan:** Zero — all three were within-scope precondition fixes that the test suite caught immediately. The plan's `<threat_model>` Rule 2 explicitly covers "essential features for correctness" and the Optional-field handling is pure correctness.

## Threat Model Posture

- **T-22-06 (Tampering: description / call_to_action embedded in SVG `<text>` content) — mitigated**: Both fields pass through `xml.sax.saxutils.escape` BEFORE insertion into SVG markup at composer.py lines 325-326. Test `test_info_flyer_renders_description_xml_escaped` regresses with `evil_desc = "Closure <script>alert(1)</script> notice"` — the raw `<script>` is absent and `&lt;script&gt;` is present in output. `test_call_to_action_with_special_chars_escaped` covers the CTA path the same way.
- **T-22-07 (Tampering: template.typography.{heading,body}_family emitted as raw SVG font-family) — accept**: Templates are in-repo JSON, validated by FlyerTemplateSchema at load time. Template JSONs are not user-supplied in this phase (Plan 05 worker loads by slug only). Attack surface is only reachable by repo compromise — out of scope.

## Test File Updates

`tests/test_composer.py` (the existing 21-test file) needed **NO** updates. Because:

- All 21 existing tests omit the `template` kwarg, exercising the back-compat path. Hardcoded values (e.g. `'Arial Black'`, `0.75`, `0.85`, `font-size="82"` for short title, `'Arial, sans-serif'`, `event.color_accent` as accent) are preserved byte-identically by the helper fallbacks.
- All existing test fixtures use `subtype="event"` (the default), so the new is_info branch is never taken.
- The `EventInput = FlyerInput` alias from Plan 02 means existing test imports of `EventInput` continue to construct `FlyerInput` instances.

`tests/unit/test_composer_template_driven.py` (NEW) — 16 tests across 4 test classes covering the new template + subtype paths.

## Verification Commands Run

```bash
# RED gate — initial test run before implementation
.venv/bin/pytest tests/unit/test_composer_template_driven.py -q
# -> 15 failed, 1 passed (back-compat smoke)

# GREEN gate — after composer refactor
.venv/bin/pytest tests/unit/test_composer_template_driven.py -q
# -> 16 passed in 1.26s

# Back-compat verification — all existing composer tests
.venv/bin/pytest tests/test_composer.py -q
# -> 21 passed in 1.27s

# Full suite (excluding Plan 04/05 deferrals)
.venv/bin/pytest tests/ -q -k "not slow" \
  --deselect tests/api/test_flyer_routes.py \
  --deselect tests/api/test_worker_tasks.py
# -> 1365 passed, 19 deselected, 1 warning in 90.45s

# Smoke import (acceptance criterion)
python -c "from flyer_generator.stages.composer import PosterComposer; \
           from flyer_generator.flyer.schema_renderer.loader import load_template; \
           tpl = load_template('editorial_classic'); print('ok')"
# -> ok
```

## Acceptance Criteria — All Pass

- [x] `grep -n "template: \"FlyerTemplateSchema | None\"" flyer_generator/stages/composer.py` returns ≥1 line (returns 4: helper signatures + compose() + _build_svg() + _build_info_description_elements())
- [x] `grep -n "_template_heading_family\|_template_body_family\|_template_scrim_opacity\|_template_accent\|_template_cover_title_size" flyer_generator/stages/composer.py` returns ≥5 unique helper names (returns 5 definitions + 6 callsites)
- [x] `grep -n "event.subtype" flyer_generator/stages/composer.py` returns ≥2 lines (composer also uses `is_info` boolean derived once at line 310; subtype gate referenced at lines 14, 310, 446, 470, 483, 575)
- [x] `grep -n "layout.fee_badge is None\|layout.details is None" flyer_generator/stages/composer.py` returns ≥2 lines (in comments + in conditional checks at 453 / 487)
- [x] `grep -n "escape(event.description)\|escape(event.call_to_action)" flyer_generator/stages/composer.py` returns ≥1 line each (returns 1 each at lines 325 and 326)
- [x] `.venv/bin/pytest tests/unit/test_composer_template_driven.py -q` reports 16 tests passing, 0 failing (≥12 required)
- [x] `.venv/bin/pytest tests/test_composer.py -q` (existing composer tests) all 21 pass — back-compat preserved
- [x] Smoke import returns "ok"

## Self-Check: PASSED

Verified each created file exists and each commit hash is reachable:

- `tests/unit/test_composer_template_driven.py` FOUND
- `flyer_generator/stages/composer.py` FOUND (modified)
- `.planning/phases/22-flyer-templates-subtype-split/22-03-SUMMARY.md` (this file) FOUND
- Commit `809ab46` (test RED) FOUND
- Commit `485ecc4` (feat GREEN) FOUND

## TDD Gate Compliance

Plan-level type was `tdd="true"` for the single task. Both gates satisfied:

- **RED commit `809ab46`** — `test(22-03): add failing tests for template-driven composer + subtype rendering` (15 of 16 tests fail before implementation; 1 back-compat smoke passes incidentally)
- **GREEN commit `485ecc4`** — `feat(22-03): template-driven + subtype-aware PosterComposer` (all 16 tests pass)
- **REFACTOR** — no commit needed; code written minimal-correct on first GREEN pass.

## Next Phase Readiness

- **Plan 22-04 (pipeline.py refactor):** Ready. `PosterComposer.compose` now accepts the `template` kwarg via keyword-only. The pipeline must thread `template=template` from `FlyerGenerator.generate` down to `composer.compose` (single-line change on the existing call). Until Plan 04 lands, the pipeline keeps calling `compose(event, background, verdict, layout)` without a template — fully back-compat and byte-identical to Phase-21 output.
- **Plan 22-05 (worker):** Ready. Worker can `template = load_template(payload["template"])` at task entry and pass `template` into the pipeline. Auth / config / Comfy work is unchanged.
- **Plan 22-11 (FE):** No FE coupling in this plan.

---

*Phase: 22-flyer-templates-subtype-split*
*Completed: 2026-04-23*
