---
phase: 22-flyer-templates-subtype-split
plan: 01
subsystem: flyer-templates
tags: [pydantic, json-schema, template-registry, flyer, schema-validation]

# Dependency graph
requires:
  - phase: 05-brochure-subsystem
    provides: flyer_generator/brochure/schema_renderer (JSON-schema template pattern); validate_hex_color shared utility
provides:
  - flyer_generator/flyer/ package with JSON-schema template registry mirroring brochure/
  - FlyerTemplateSchema Pydantic model (single-canvas `hero` panel)
  - load_template(name_or_path) + list_templates() loader
  - 6 shipped flyer templates declaring typography scale + scrim opacity + accent placement + shape mix
  - `from flyer_generator.flyer.schema_renderer import ...` public API surface
affects: [22-02-content-resolver, 22-03-composer-refactor, 22-04-pipeline, 22-05-worker, 22-11-frontend]

# Tech tracking
tech-stack:
  added: []  # Re-uses pydantic 2.x, already in stack
  patterns:
    - "Single-canvas flyer panel map: `panels: {hero: {elements: [...]}}` (vs. brochure's 6-panel set)"
    - "Flat FlyerInput content_key namespace: `event.title`, `event.date`, `event.location_name`, `org` (vs. brochure's `sections[i].heading`, `back_panel.body`)"
    - "Flyer palette adds scrim_opacity_top/bottom knobs (brochure has no scrim concept)"
    - "subtype_compat: list[Literal['event', 'info']] on FlyerTemplateSchema lets templates opt into subtypes (default both)"
    - "Primitives (Fill/Stroke/Shape/Text/Bullets/LogoPlaceholder/ImagePlaceholder/Divider/PanelElement/PanelSchema) copied verbatim from brochure to keep flyer<->brochure decoupled at module boundary"
    - "validate_hex_color imported cross-package from flyer_generator.brochure.models (small shared utility, not brochure-specific)"

key-files:
  created:
    - flyer_generator/flyer/__init__.py
    - flyer_generator/flyer/schema_renderer/__init__.py
    - flyer_generator/flyer/schema_renderer/schema_model.py
    - flyer_generator/flyer/schema_renderer/loader.py
    - flyer_generator/flyer/schemas/editorial_classic.json
    - flyer_generator/flyer/schemas/bold_modern.json
    - flyer_generator/flyer/schemas/minimal_photo.json
    - flyer_generator/flyer/schemas/retro_poster.json
    - flyer_generator/flyer/schemas/zine.json
    - flyer_generator/flyer/schemas/tight_typographic.json
    - tests/flyer/__init__.py
    - tests/flyer/schema_renderer/__init__.py
    - tests/flyer/schema_renderer/test_loader.py
    - tests/flyer/schema_renderer/test_schema_model.py
  modified: []

key-decisions:
  - "Copy primitives verbatim into flyer schema_model rather than import from brochure.schema_renderer — keeps flyer->brochure dependency graph clean (only validate_hex_color crosses the boundary)"
  - "TextElement has no stroke field — retro_poster simulates title stroke via translucent dark rect behind the text (z=8, below title at z=10)"
  - "retro_poster + bold_modern shipped with subtype_compat=['event'] (fee-badge/date-block driven layouts not suited to info flyers per plan behavior Test 5); the other 4 default to ['event', 'info']"
  - "Typography defaults match composer.py hardcoded values (cover_title_size=82 from _title_params line 38, body_size=34, body_line_height=44) so default template render matches existing pipeline output"
  - "Canvas gains default_factory (width=1080, height=1920) so minimal templates can omit canvas block entirely"

patterns-established:
  - "Flyer template JSON shape: single `hero` panel, image_placeholder + shape(s) + text elements; content_key uses flat `event.*` / `org` / `tagline` namespace"
  - "FlyerTemplateSchema validation: strict extra='forbid' + @field_validator on `panels` rejecting missing `hero` with message 'template missing panels'"
  - "Test layout mirrors tests/brochure/schema_renderer/: test_loader.py (load + list + path + malformed), test_schema_model.py (minimal_template helper + primitive tests)"

requirements-completed: [FT-02]

# Metrics
duration: ~20min
completed: 2026-04-24
---

# Phase 22 Plan 01: Flyer Template Registry Foundation Summary

**JSON-schema flyer template registry (FlyerTemplateSchema Pydantic + load_template loader + 6 starter templates) mirroring the brochure pattern with single-canvas `hero` panel, flat FlyerInput content_key namespace, and subtype_compat opt-in.**

## Performance

- **Duration:** ~20 minutes
- **Started:** 2026-04-24T23:00Z (approx)
- **Completed:** 2026-04-24T23:15Z (approx)
- **Tasks:** 2 (both autonomous, both TDD)
- **Files created:** 14 (4 code + 6 JSON + 4 test)

## Accomplishments

- Stood up `flyer_generator/flyer/` package with `schema_renderer/` + `schemas/` subdirectories, mirroring the brochure layout
- Implemented `FlyerTemplateSchema` Pydantic model with flyer-specific divergences: single `hero` panel, Canvas default 1080x1920, Palette with scrim_opacity_top/bottom, subtype_compat opt-in
- Implemented `load_template(name_or_path)` + `list_templates()` as near-verbatim copies of the brochure loader
- Shipped 6 visually-distinct starter templates: editorial_classic, bold_modern, minimal_photo, retro_poster, zine, tight_typographic — each declaring typography scale + scrim opacity + accent placement + shape mix (satisfying FT-03 requirement)
- 2 of 6 templates (retro_poster, bold_modern) opt into event-only via subtype_compat=['event']; the other 4 support both event + info subtypes
- 35 tests across `tests/flyer/schema_renderer/` all pass; brochure's 229 schema_renderer tests continue to pass (no regressions)

## Task Commits

Each task was committed atomically following TDD RED -> GREEN gates:

1. **Task 1 RED: add failing tests for FlyerTemplateSchema + loader** — `1314139` (test)
2. **Task 1 GREEN: implement FlyerTemplateSchema + loader + package barrel** — `ed2fc4a` (feat)
3. **Task 2 RED: add failing tests for 6 shipped flyer templates** — `8f98a0b` (test)
4. **Task 2 GREEN: add 6 shipped flyer template JSON files** — `d36ede1` (feat)

Plan metadata commit (this SUMMARY.md) will follow.

## Files Created

### Package code
- `flyer_generator/flyer/__init__.py` — empty package marker
- `flyer_generator/flyer/schema_renderer/__init__.py` — barrel re-exporting FlyerTemplateSchema, load_template, list_templates
- `flyer_generator/flyer/schema_renderer/schema_model.py` — Pydantic model (409 lines: primitives + Canvas + Palette + Typography + FlyerTemplateSchema)
- `flyer_generator/flyer/schema_renderer/loader.py` — load_template + list_templates (40 lines, near-verbatim from brochure loader)

### Template JSON files (all under `flyer_generator/flyer/schemas/`)
- `editorial_classic.json` — Playfair Display 88pt serif title, #1E3A5F navy accent rule 8px at bottom, narrow scrim 0.60/0.70, subtype_compat=['event','info']
- `bold_modern.json` — Impact 140pt slab, #FF2E4D red 120px bottom accent stripe, full-bleed scrim 0.85/0.90, subtype_compat=['event']
- `minimal_photo.json` — Inter 68pt bottom-left, no top scrim (0.0), #FBBF24 yellow 30x30 accent dot, subtype_compat=['event','info']
- `retro_poster.json` — Bungee 120pt display, three accent shapes (top band, bottom band, top-right circle), translucent dark rect behind title simulating stroke, subtype_compat=['event']
- `zine.json` — Courier 96pt monospace title off-axis, two rotated accent stripes (+4/-3 deg), asymmetric scrim 0.50/0.65, subtype_compat=['event','info']
- `tight_typographic.json` — Helvetica 110pt, bounded top image region (60..660), structured grid (4px rules at y=700/1800), subtype_compat=['event','info']

### Tests
- `tests/flyer/__init__.py` — package marker
- `tests/flyer/schema_renderer/__init__.py` — package marker
- `tests/flyer/schema_renderer/test_schema_model.py` — 14 tests: import smoke, minimal template, missing-hero rejection, schema_version=='1' enforcement, snake_case name, hex validation, subtype_compat default/override, canvas defaults, shape/text primitive smoke, validate_hex_color cross-package import
- `tests/flyer/schema_renderer/test_loader.py` — 21 tests: list_templates isinstance, all-6-starters, unknown raises FileNotFoundError, load-by-path branch, malformed JSON rejection, parameterized load for each of 6 starters (canvas 1080x1920 + non-empty hero), FT-03 typography-or-scrim-or-shape per template, subtype_compat for retro_poster/bold_modern/editorial_classic

**Total:** 35 tests, all passing.

## Decisions Made

- **Copy vs. import brochure primitives:** Copied GradientStop/SolidFill/Linear+RadialGradientFill/TextureSlotFill/Fill/Stroke/ShapeElement/TextElement/BulletsElement/LogoPlaceholder/ImagePlaceholder/DividerElement/PanelElement/PanelSchema verbatim rather than importing from `flyer_generator.brochure.schema_renderer.schema_model`. This keeps the flyer->brochure dependency graph limited to one shared utility (`validate_hex_color`). Rationale matches 22-PATTERNS line 200 ("copying is the lesser evil vs. `flyer.schema_renderer` -> `brochure.schema_renderer` anti-pattern").
- **Typography defaults mirror composer.py hardcoded values:** `cover_title_size=82`, `body_size=34`, `body_line_height=44`. This means Plan 03's composer refactor can fall back to template defaults and match the current rendered output byte-for-byte when no template declares overrides.
- **Flyer Palette adds scrim_opacity_top/bottom knobs:** Brochure's Palette doesn't have these (print brochures have no vision-driven scrim); flyer templates need to control scrim intensity per design. Default 0.75/0.85 matches composer.py's current hardcoded scrim gradient values.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] retro_poster.json used `stroke` field on TextElement that doesn't exist in schema**
- **Found during:** Task 2 GREEN (first pytest run after authoring all 6 JSONs)
- **Issue:** Plan action text for retro_poster said "TextElement cover_title with explicit `stroke` on the TextElement (or a background rect providing outline)". I wrote `"stroke": {"color": "#1F1B16", "width": 4}` on the TextElement, but the brochure `TextElement` primitive (which I copied verbatim) has no `stroke` field — only `ShapeElement` does. Pydantic raised `extra_forbidden` on validation.
- **Fix:** Took the plan's "or" branch — added a translucent dark ShapeElement (rect, z=8, opacity 0.55) behind the title bbox (z=10) to provide visual backdrop emphasis that simulates the poster-stroke look.
- **Files modified:** `flyer_generator/flyer/schemas/retro_poster.json`
- **Verification:** All 3 previously-failing retro_poster tests now pass (`test_load_each_template[retro_poster]`, `test_template_declares_typography_or_scrim_or_shape[retro_poster]`, `test_retro_poster_is_event_only`).
- **Committed in:** `d36ede1` (Task 2 GREEN — single commit alongside all 6 JSONs)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minimal — the plan's action text explicitly allowed the "background rect providing outline" alternative, so this wasn't scope creep, just following the explicit fallback. No schema change was needed; the extra `stroke` field was user-authored invalid JSON.

## Issues Encountered

None — the TDD RED->GREEN cycle caught the retro_poster stroke bug on first run, and no other complications arose. Brochure's 229 existing tests pass unchanged.

## Threat Flags

None — the trust-boundary mitigations documented in the plan's `<threat_model>` (T-22-01 loader path-traversal, T-22-02 FileNotFoundError info disclosure) are both satisfied by mirroring brochure's loader verbatim. No new surface introduced in this plan.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Plan 22-02 (content resolver):** Can import `load_template` and assume `content_key` strings like `"event.title"`, `"event.date"`, `"org"`, `"tagline"` are what the 6 shipped templates actually use. Verified: all 6 JSONs reference only the flat `event.*` / `org` namespace.
- **Plan 22-03 (composer refactor):** Can graft `template: FlyerTemplateSchema | None = None` kwarg onto `PosterComposer.compose()` and call `template.typography.cover_title_size`, `template.palette.scrim_opacity_top`, etc. Typography defaults match current composer values so the `template is None` branch renders unchanged.
- **Plan 22-05 (worker):** Can call `load_template(payload["template"])` at worker entry and surface `FileNotFoundError` / `ValidationError` before any Comfy work.
- **FE template list:** Once FE regen runs in Plan 22-11, the `list_templates()` return order is already sorted alphabetically — FE can hardcode the 6 names in that exact order: `bold_modern, editorial_classic, minimal_photo, retro_poster, tight_typographic, zine`.

## TDD Gate Compliance

Both tasks followed RED->GREEN cycle with explicit commits:
- Task 1: `test(22-01): add failing tests...` (1314139) then `feat(22-01): implement...` (ed2fc4a)
- Task 2: `test(22-01): add failing tests for 6 shipped...` (8f98a0b) then `feat(22-01): add 6 shipped flyer template JSON files` (d36ede1)

No REFACTOR phase commits needed — code was written minimal-correct on first pass; the only iteration was the retro_poster stroke bug fix captured inline in Task 2 GREEN.

## Self-Check: PASSED

Verified each created file exists and each commit hash is reachable:
- `flyer_generator/flyer/__init__.py` FOUND
- `flyer_generator/flyer/schema_renderer/__init__.py` FOUND
- `flyer_generator/flyer/schema_renderer/schema_model.py` FOUND
- `flyer_generator/flyer/schema_renderer/loader.py` FOUND
- `flyer_generator/flyer/schemas/editorial_classic.json` FOUND
- `flyer_generator/flyer/schemas/bold_modern.json` FOUND
- `flyer_generator/flyer/schemas/minimal_photo.json` FOUND
- `flyer_generator/flyer/schemas/retro_poster.json` FOUND
- `flyer_generator/flyer/schemas/zine.json` FOUND
- `flyer_generator/flyer/schemas/tight_typographic.json` FOUND
- `tests/flyer/__init__.py` FOUND
- `tests/flyer/schema_renderer/__init__.py` FOUND
- `tests/flyer/schema_renderer/test_loader.py` FOUND
- `tests/flyer/schema_renderer/test_schema_model.py` FOUND
- Commit 1314139 FOUND
- Commit ed2fc4a FOUND
- Commit 8f98a0b FOUND
- Commit d36ede1 FOUND

---
*Phase: 22-flyer-templates-subtype-split*
*Completed: 2026-04-24*
