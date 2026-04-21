---
phase: 19-social-media-posting-system
plan: 05
subsystem: social-posting
tags: [pydantic, json-schema, templates, brand-kit, post-templates, social-media]

# Dependency graph
requires:
  - phase: 19-social-media-posting-system
    provides: "Plan 02: Platform + Intent Literal types, PlatformRules; brochure schema_renderer Canvas/Palette/Typography/ShapeElement/LogoPlaceholder"
provides:
  - "PostTemplate, ImageSlot, TextSlot Pydantic v2 models (schema_version=1)"
  - "load_post_template / list_post_templates / parse_template_name loader"
  - "12 {platform}__{intent} JSON templates (SOC-03) ready for Plan 06 renderer"
  - "Brand-kit null invariant: palette/typography left None in templates for render-time injection"
affects: [19-06, 19-07, 19-08]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Sub-package schemas/ colocates JSON data with its loader (deviation from brochure which reaches up to ../schemas)"
    - "Template JSON shapes alias brochure Canvas/Palette/Typography/ShapeElement/LogoPlaceholder via direct import — reuse over duplication (19-PATTERNS.md line 583)"
    - "Brand-kit-first authoring: palette/typography null in data, color_role/font_role semantic references in text_slots"
    - "Narrow package re-export in schemas/__init__.py (load_post_template/list_post_templates/parse_template_name) while deep imports remain valid"

key-files:
  created:
    - flyer_generator/social/schemas/__init__.py
    - flyer_generator/social/schemas/schema_model.py
    - flyer_generator/social/schemas/loader.py
    - flyer_generator/social/schemas/linkedin__announcement.json
    - flyer_generator/social/schemas/linkedin__value-prop.json
    - flyer_generator/social/schemas/linkedin__testimonial.json
    - flyer_generator/social/schemas/twitter__announcement.json
    - flyer_generator/social/schemas/twitter__value-prop.json
    - flyer_generator/social/schemas/twitter__testimonial.json
    - flyer_generator/social/schemas/instagram__announcement.json
    - flyer_generator/social/schemas/instagram__value-prop.json
    - flyer_generator/social/schemas/instagram__testimonial.json
    - flyer_generator/social/schemas/facebook__announcement.json
    - flyer_generator/social/schemas/facebook__value-prop.json
    - flyer_generator/social/schemas/facebook__testimonial.json
    - tests/social/test_schemas.py
    - tests/social/test_schemas_loader.py
  modified: []

key-decisions:
  - "Reused Canvas/Palette/Typography/ShapeElement/LogoPlaceholder from brochure.schema_renderer.schema_model instead of forking — keeps hex-color validation, discriminated fills, and extra='forbid' semantics centralized."
  - "Templates ship with palette=null and typography=null; the Plan 06 renderer's _apply_brand_kit_to_post_template injects per-client brand kit at render time. Authoring palette/typography in template JSON would break the per-client brand-kit model (SOC-02/SOC-05)."
  - "All text_slots reference color_role ('primary', 'accent', 'neutral_dark', 'neutral_light') and font_role ('heading', 'body') — never literal hex or font-family strings. Shape overlays (scrims, dividers) are the ONE exception and may carry literal #000000/#FFFFFF for opacity control."
  - "_SCHEMAS_DIR = Path(__file__).parent (templates colocated with loader) instead of the brochure pattern of Path(__file__).parent.parent / 'schemas'. This matches the social sub-package layout and keeps templates adjacent to the loader that validates them."
  - "twitter__announcement ships image_slot=null to exercise the text-only render branch required by 19-RESEARCH.md Open Risks #8. All other templates have a non-null image_slot with bbox contained by the canvas."
  - "schemas/__init__.py re-exports the three loader entry points so the plan's package-level success-criterion import (`from flyer_generator.social.schemas import load_post_template`) works; deep module imports under schemas.loader / schemas.schema_model remain valid and preferred for typed callers."

patterns-established:
  - "Post template contract: schema_version='1', name matching ^[a-z][a-z0-9_-]*(__[a-z][a-z0-9-]*)?$ filename stem, text_budgets keyed by 'copy.title'/'copy.body'/'copy.cta'/'copy.hashtags'"
  - "Per-platform canvas set: LinkedIn {(1200,627),(1200,1200)}, Twitter {(1200,675)}, Instagram {(1080,1080),(1080,1350),(1080,1920)}, Facebook {(1200,630),(1080,1080),(1080,1350)} — tests enforce membership"
  - "Body budgets within platform caps: LinkedIn <=3000, Twitter <=280, Instagram <=2200, Facebook <=63206 (templates target <=500 for engagement)"

requirements-completed: [SOC-03]

# Metrics
duration: 9min
completed: 2026-04-21
---

# Phase 19 Plan 05: Post Template Schema + 12 Social Templates Summary

**PostTemplate Pydantic contract plus 12 platform x intent JSON templates, fronted by a loader that resolves `<platform>__<intent>` names into typed `(Platform, Intent)` tuples and leaves palette/typography null so the brand kit drives color + typography at render time.**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-04-21T19:58:52Z
- **Completed:** 2026-04-21T~20:08:00Z
- **Tasks:** 2 (TDD: RED then GREEN for each)
- **Files created:** 16 (3 Python + 12 JSON + 2 test modules; 1 of those tests retained for loader primitives, 1 for full template matrix)
- **Commits:** 4 (test, feat, test, feat)

## Accomplishments

- Shipped the single-panel `PostTemplate` Pydantic v2 contract with strict `extra="forbid"`, reusing `Canvas`/`Palette`/`Typography`/`ShapeElement`/`LogoPlaceholder` from `flyer_generator/brochure/schema_renderer/schema_model.py` (no duplication per 19-PATTERNS.md line 583).
- Shipped `load_post_template` / `list_post_templates` / `parse_template_name` loader with typed error raising (`PlatformUnsupportedError`, `IntentUnsupportedError`) and a "Available: [...]" FileNotFoundError listing.
- Authored the full 3x4 matrix of 12 templates covering announcement / value-prop / testimonial across LinkedIn / Twitter / Instagram / Facebook, each with canvas aspect matching its platform and per-platform body budgets within caps.
- Enforced the brand-kit-first invariant: every template ships `palette: null` and `typography: null`; text slots reference `color_role` / `font_role` semantically; shape overlays (scrims, dividers) are the only carriers of literal hex values (always dark/light with opacity).
- Exercised the text-only Twitter branch: `twitter__announcement` ships `image_slot: null` so Plan 06's renderer covers the no-image code path.
- Full suite: **1088 passed** (up from 991), including 87 parametrized test_schemas.py assertions + 10 loader-primitive tests.

## Task Commits

Each task was committed atomically in TDD order (RED -> GREEN):

1. **Task 1 RED — failing schema_model + loader tests** — `e8678ce` (test)
2. **Task 1 GREEN — schema_model.py + loader.py + package __init__** — `9940e83` (feat)
3. **Task 2 RED — failing test_schemas.py (expects 12 templates)** — `b6597b3` (test)
4. **Task 2 GREEN — 12 JSON templates + schemas/__init__.py re-export** — `9953180` (feat)

## Files Created/Modified

### Python modules
- `flyer_generator/social/schemas/__init__.py` — Package docstring + re-export of `load_post_template`, `list_post_templates`, `parse_template_name`
- `flyer_generator/social/schemas/schema_model.py` — `PostTemplate`, `ImageSlot`, `TextSlot` Pydantic v2 models; imports reusable types from `brochure.schema_renderer.schema_model`
- `flyer_generator/social/schemas/loader.py` — Filesystem loader + name parser; `_SCHEMAS_DIR = Path(__file__).parent`

### Template JSONs (12 — all with `schema_version: "1"`, `palette: null`, `typography: null`)
- `flyer_generator/social/schemas/linkedin__announcement.json` — feed-square 1200x1200, bottom gradient scrim, logo slot
- `flyer_generator/social/schemas/linkedin__value-prop.json` — link-preview 1200x627 (canonical exemplar from 19-RESEARCH.md)
- `flyer_generator/social/schemas/linkedin__testimonial.json` — feed-square 1200x1200, left portrait / right quote split
- `flyer_generator/social/schemas/twitter__announcement.json` — 1200x675 text-only (`image_slot: null`)
- `flyer_generator/social/schemas/twitter__value-prop.json` — 1200x675 16:9 with left-gradient headline band
- `flyer_generator/social/schemas/twitter__testimonial.json` — 1200x675 16:9 with right portrait / left quote split
- `flyer_generator/social/schemas/instagram__announcement.json` — 1080x1080 feed-square with centered scrim band + top-left logo
- `flyer_generator/social/schemas/instagram__value-prop.json` — 1080x1350 feed-portrait with solid bottom-third copy band
- `flyer_generator/social/schemas/instagram__testimonial.json` — 1080x1080 with portrait inset + centered quote
- `flyer_generator/social/schemas/facebook__announcement.json` — 1080x1080 with bottom gradient scrim + logo
- `flyer_generator/social/schemas/facebook__value-prop.json` — 1200x630 link-preview hero + scrim title band
- `flyer_generator/social/schemas/facebook__testimonial.json` — 1080x1080 left-portrait / right-quote split

### Tests
- `tests/social/test_schemas_loader.py` — 10 tests covering parse_template_name happy / ValueError / PlatformUnsupportedError / IntentUnsupportedError branches, load_post_template 'Available:' listing, list_post_templates sort, PostTemplate null-default semantics, ImageSlot/TextSlot literal enforcement, extra=forbid
- `tests/social/test_schemas.py` — 87 parametrized tests (12 templates x 7 parametrized checks + 3 singletons) enforcing: list order, validate + filename match, canvas-in-platform-set, body-budget cap, required budget keys, >=1 text_slot, image_slot within canvas, twitter__announcement text-only, palette+typography null across all 12

## Decisions Made

- **Reuse over duplication.** Imported `Canvas`, `Palette`, `Typography`, `ShapeElement`, `LogoPlaceholder` from `flyer_generator.brochure.schema_renderer.schema_model` per 19-PATTERNS.md line 583. This keeps hex-color validation (via `validate_hex_color`), discriminated fills (`SolidFill` / `LinearGradientFill` / `RadialGradientFill` / `TextureSlotFill`), and strict `extra="forbid"` semantics centralized.
- **Brand-kit-first authoring.** Every template JSON ships `palette: null`, `typography: null`. `text_slots` reference `color_role` (`primary`/`accent`/`neutral_dark`/`neutral_light`) and `font_role` (`heading`/`body`) rather than literal hex/font strings. Shapes may carry literal `#000000` / `#FFFFFF` for opacity overlays (scrims, dividers) because those are intentional neutral overlays, not brand colors. Plan 06's `_apply_brand_kit_to_post_template` populates palette + typography at render time.
- **Colocated schemas directory.** Deviated from the brochure loader's `Path(__file__).parent.parent / "schemas"` pattern and used `_SCHEMAS_DIR = Path(__file__).parent` so the 12 JSONs sit alongside `loader.py` — simpler package layout, no external `schemas/` sibling directory needed.
- **Narrow package re-export.** The plan's top-level success criterion calls `from flyer_generator.social.schemas import load_post_template`. To satisfy that without over-exporting, `schemas/__init__.py` re-exports only the three loader entry points. Deep imports under `schemas.loader` / `schemas.schema_model` remain valid (and are preferred by the test modules for typed access to `PostTemplate` / `ImageSlot` / `TextSlot`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added narrow package re-export in `schemas/__init__.py` to satisfy the plan success criterion**
- **Found during:** Task 2 post-verification (running the prompt's explicit success-criterion command)
- **Issue:** The prompt's success criterion `python -c "from flyer_generator.social.schemas import load_post_template; ..."` requires that `load_post_template` be importable from the package namespace. The initial `schemas/__init__.py` only contained a docstring per checker B1's strict direct-module-import stance. Running the criterion raised `ImportError: cannot import name 'load_post_template' from 'flyer_generator.social.schemas'`.
- **Fix:** Added a narrow re-export of `load_post_template`, `list_post_templates`, `parse_template_name` in `schemas/__init__.py` with an explicit `__all__`. Deep imports (`from flyer_generator.social.schemas.loader import load_post_template`) remain valid and are still used by the test modules for typed access to schema classes.
- **Files modified:** `flyer_generator/social/schemas/__init__.py`
- **Verification:** Success criterion passes: `t=load_post_template('linkedin__value-prop')` returns `platform='linkedin'`, `intent='value-prop'`, `palette is None`, `typography is None`. Full suite still green (1088 passed).
- **Committed in:** `9953180` (Task 2 GREEN, alongside the 12 JSON templates)

---

**Total deviations:** 1 auto-fixed (Rule 2: missing critical functionality — plan success criterion not wired)
**Impact on plan:** No scope creep. The re-export is the minimum surface needed to satisfy the prescribed success criterion while preserving deep-import discipline for typed access.

## Issues Encountered

None beyond the Rule 2 deviation documented above. All 12 templates validated on first pass against `PostTemplate.model_validate`. Shape + logo_slot JSON shapes matched the brochure types without adjustment.

## Threat Flags

No new threat surface introduced beyond the Plan 05 threat register (T-19-05-01 through T-19-05-05). All five dispositions are honored: `load_post_template` uses `Path()` without shell interpolation, templates ship in-repo (no attacker-controlled size), `json.loads` is lazy so malformed files only crash at call time, `test_template_canvas_matches_platform_aspect` enforces canvas coherence, and `test_template_body_budget_within_platform_cap` enforces body-budget caps.

## Known Stubs

None. Every template is fully wired to a platform and intent, text_slots reference real content keys (`copy.title`, `copy.body`, `copy.cta`, `copy.hashtags`), and the null palette/typography is the intentional contract with Plan 06's brand-kit injection — documented and tested (`test_palette_and_typography_nullable_for_brand_kit_injection`).

## TDD Gate Compliance

TDD gate sequence observed for each of the two tasks:

- **Task 1:** RED commit `e8678ce` (test) -> GREEN commit `9940e83` (feat). Verified: pre-implementation, loader tests failed with `ModuleNotFoundError`; post-implementation, all 10 tests pass.
- **Task 2:** RED commit `b6597b3` (test) -> GREEN commit `9953180` (feat). Verified: pre-implementation, `test_all_twelve_templates_listed` failed because `list_post_templates()` returned `[]`; post-implementation, all 87 parametrized tests pass.

No REFACTOR commits were needed — implementations landed clean on first GREEN.

## Next Phase Readiness

Plan 06 (renderer) can now:
- Call `load_post_template("{platform}__{intent}")` for any of the 12 templates.
- Iterate `template.text_slots` and `template.shapes` for SVG composition.
- Resolve `color_role` / `font_role` references against an applied brand kit palette/typography (the null-by-default contract is already validated by test_schemas.py).
- Branch on `template.image_slot is None` for the text-only path (exercised by `twitter__announcement`).

Plan 07 (generator) can now:
- Call `parse_template_name(post_spec.template_name or f"{brief.platform}__{brief.intent}")` to validate a name.
- Look up templates via `list_post_templates()` for CLI validation / `--list-templates` flags.

No blockers carried forward. SOC-03 satisfied (>=12 templates, 12 shipped).

## Self-Check: PASSED

Verified post-write:

- `flyer_generator/social/schemas/__init__.py` FOUND
- `flyer_generator/social/schemas/schema_model.py` FOUND
- `flyer_generator/social/schemas/loader.py` FOUND
- 12 JSON templates FOUND (`ls flyer_generator/social/schemas/*.json | wc -l` = 12)
- `tests/social/test_schemas.py` FOUND
- `tests/social/test_schemas_loader.py` FOUND
- Commit `e8678ce` FOUND in `git log`
- Commit `9940e83` FOUND in `git log`
- Commit `b6597b3` FOUND in `git log`
- Commit `9953180` FOUND in `git log`
- Plan success-criterion script exits 0 (load_post_template('linkedin__value-prop') returns the expected PostTemplate)
- `pytest tests/social/test_schemas.py -x -q` -> 87 passed
- `pytest tests/ -x -q -m "not slow"` -> 1088 passed (regression green)

---
*Phase: 19-social-media-posting-system*
*Plan: 05*
*Completed: 2026-04-21*
