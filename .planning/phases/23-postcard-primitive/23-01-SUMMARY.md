---
phase: 23-postcard-primitive
plan: 01
subsystem: postcard-templates
tags: [pydantic, json-schema, template-registry, postcard, schema-validation]

# Dependency graph
requires:
  - phase: 22-flyer-templates-subtype-split
    provides: flyer_generator/flyer/schema_renderer (JSON-schema template pattern source); validate_hex_color shared utility
  - phase: 05-brochure-subsystem
    provides: validate_hex_color (cross-package utility allowance)
provides:
  - flyer_generator/postcard/ package with JSON-schema template registry mirroring flyer/
  - PostcardTemplateSchema Pydantic model (TWO panels: front + back)
  - load_template(name_or_path) + list_templates() loader
  - 2 shipped postcard templates (classic_portrait 1200x1800, modern_landscape 1800x1200)
  - `from flyer_generator.postcard.schema_renderer import ...` public API surface
affects: [23-02-request-schema, 23-03-record-model, 23-04-renderer-worker, 23-05-routes, 23-06-frontend]

# Tech tracking
tech-stack:
  added: []  # Re-uses pydantic 2.x (already in stack)
  patterns:
    - "Two-sided postcard panel map: `panels: {front: {...}, back: {...}}` (vs. flyer single-hero, vs. brochure 6-panel)"
    - "Postcard Canvas requires explicit width/height (no defaults — 4x6 portrait 1200x1800 vs. 6x4 landscape 1800x1200 split)"
    - "Postcard PostcardTemplateSchema OMITS subtype_compat (postcards don't split into event/info — single primitive)"
    - "Postcard Palette KEEPS scrim_opacity_top/bottom (front panel composes scrim over hero image like flyer cover)"
    - "Locked content_key namespace per CONTEXT: `headline`, `body`, `address_block.{recipient_name,street,city_state_zip}`"
    - "Primitives (Fill/Stroke/Shape/Text/Bullets/LogoPlaceholder/ImagePlaceholder/Divider/PanelElement/PanelSchema) copied verbatim from flyer schema_model to keep postcard<->flyer decoupled at module boundary"
    - "validate_hex_color imported cross-package from flyer_generator.brochure.models (same shared-utility allowance as flyer schema)"
    - "Loader pattern: `_SCHEMAS_DIR = Path(__file__).parent.parent / 'schemas'`; bare-slug looked up under that dir, '.json'-suffix branch accepts arbitrary path (T-23-01 deferred to worker plan path-traversal guard)"

key-files:
  created:
    - flyer_generator/postcard/__init__.py
    - flyer_generator/postcard/schema_renderer/__init__.py
    - flyer_generator/postcard/schema_renderer/schema_model.py
    - flyer_generator/postcard/schema_renderer/loader.py
    - flyer_generator/postcard/schemas/classic_portrait.json
    - flyer_generator/postcard/schemas/modern_landscape.json
    - tests/postcard/__init__.py
    - tests/postcard/schema_renderer/__init__.py
    - tests/postcard/schema_renderer/test_schema_model.py
    - tests/postcard/schema_renderer/test_loader.py
  modified: []

key-decisions:
  - "Copy primitives verbatim into postcard schema_model rather than import from flyer.schema_renderer — keeps postcard->flyer dependency graph clean (only validate_hex_color crosses the boundary). Same rationale as Phase 22 (per 22-01-SUMMARY.md): copying is the lesser evil vs. cross-package schema_renderer import anti-pattern."
  - "Canvas requires explicit width/height (no default_factory). Unlike flyer (single 1080x1920 default) or brochure (single canvas), postcards have TWO equally-valid orientations (4x6 portrait 1200x1800 + 6x4 landscape 1800x1200 at 300 DPI USPS standard); no single default makes sense, so authors MUST declare canvas explicitly."
  - "PostcardTemplateSchema OMITS subtype_compat. Postcards are a single primitive (no event/info split like flyer). Adding the field would invite accidental misuse downstream."
  - "Palette keeps scrim_opacity_top/bottom even though back panels are typographic-only. Front panels DO compose scrim over hero (mirroring flyer cover treatment), and unused defaults are harmless."
  - "T-23-01 (loader path-traversal via .json-suffix branch) accepted at this layer; the worker plan (23-04) is responsible for the `_validate_template_slug` guard before calling load_template, mirroring Phase 22 worker pattern."
  - "Back panels are typographic-only (no image_placeholder, no scrim). Front panels carry the imagery. This decision is encoded in JSON, not the schema (schema permits any element type in either panel)."

patterns-established:
  - "Postcard template JSON shape: `front` panel = image_placeholder slot='hero' + bottom scrim shape + cover_title TextElement (content_key='headline') + accent shape; `back` panel = body TextElement (content_key='body') + divider + 3 address_block.* TextElements + dashed stamp shape + static stamp label TextElement"
  - "PostcardTemplateSchema validation: strict extra='forbid' + @field_validator on `panels` rejecting missing front OR back with message 'template missing panels'"
  - "Test layout mirrors tests/flyer/schema_renderer/: test_loader.py (load + list + path + malformed + parametrized canvas + parametrized address_block content_keys), test_schema_model.py (_minimal_template_dict helper + primitive smoke tests)"

requirements-completed: [PC-04]  # template registry foundation; renderer wiring is plan 23-04

# Metrics
duration: ~12min
completed: 2026-04-25
---

# Phase 23 Plan 01: Postcard Template Registry Foundation Summary

**JSON-schema postcard template registry (PostcardTemplateSchema Pydantic + load_template loader + 2 starter templates) mirroring the Phase 22 flyer pattern but with TWO panels (`front` + `back`), explicit canvas dims, and a locked `headline`/`body`/`address_block.*` content_key namespace.**

## Performance

- **Duration:** ~12 minutes
- **Tasks:** 2 (both autonomous, both TDD)
- **Files created:** 10 (4 code + 2 JSON + 4 test/init)
- **Tests:** 34 (all passing)
- **Regressions:** 0 (flyer + brochure schema_renderer suites — 284 tests — unchanged)

## Accomplishments

- Stood up `flyer_generator/postcard/` package with `schema_renderer/` + `schemas/` subdirectories, mirroring the Phase 22 flyer layout
- Implemented `PostcardTemplateSchema` Pydantic model with postcard-specific divergences:
  - `_PanelName = Literal["front", "back"]` (vs. flyer's single `hero`)
  - `Canvas` requires explicit `width` + `height` (no `default_factory`)
  - `@field_validator("panels")` rejects missing `front` OR `back` with `template missing panels: [...]`
  - Omits `subtype_compat` (postcards are a single primitive)
  - `Palette` retains `scrim_opacity_top` / `scrim_opacity_bottom` defaults (0.75 / 0.85) — front panel may scrim hero
- Implemented `load_template(name_or_path)` + `list_templates()` near-verbatim from flyer loader (only the imported schema name differs)
- Shipped 2 visually-distinct starter templates honoring the locked content_key namespace:
  - **`classic_portrait`** — 1200×1800 (4×6 @ 300 DPI), Playfair Display 96pt serif title, navy `#1E3A5F` accent, scrim 0.55/0.65 over hero, typographic back with vertical divider + address column + dashed stamp box
  - **`modern_landscape`** — 1800×1200 (6×4 @ 300 DPI), Inter 132pt bold sans title, red `#FF2E4D` accent, asymmetric front (left-third black overlay) + back (red top stripe, wide body, right-aligned address)
- Both templates reference required content_keys: `headline` (front), `body` + `address_block.recipient_name` + `address_block.street` + `address_block.city_state_zip` (back)
- 34 tests across `tests/postcard/schema_renderer/` all pass; brochure's 229 + flyer's 55 schema_renderer tests continue to pass (no regressions)

## Task Commits

Each task followed TDD RED → GREEN gates with explicit commits:

1. **Task 1+2 RED:** `ac8d030` — `test(23-01): add failing tests for PostcardTemplateSchema + loader`
   (Combined RED for both tasks: schema validation tests + template-dependent loader parametrized tests written upfront)
2. **Task 1 GREEN:** `8fa4ec6` — `feat(23-01): implement PostcardTemplateSchema + loader + package barrel`
3. **Task 2 GREEN:** `4f2b24d` — `feat(23-01): ship 2 starter postcard templates (classic_portrait + modern_landscape)`

Plan metadata commit (this SUMMARY.md) will follow.

## Files Created

### Package code
- `flyer_generator/postcard/__init__.py` — empty package marker
- `flyer_generator/postcard/schema_renderer/__init__.py` — barrel re-exporting `PostcardTemplateSchema`, `load_template`, `list_templates`
- `flyer_generator/postcard/schema_renderer/schema_model.py` — Pydantic model (~370 lines: primitives + Canvas + Palette + Typography + PostcardTemplateSchema with required-front+back validator)
- `flyer_generator/postcard/schema_renderer/loader.py` — `load_template` + `list_templates` (~40 lines, near-verbatim from flyer loader with `PostcardTemplateSchema` swap)

### Template JSON files (under `flyer_generator/postcard/schemas/`)
- `classic_portrait.json` — Playfair Display 96pt, navy `#1E3A5F` accent rule 12px, scrim 0.55/0.65, 4×6 portrait
- `modern_landscape.json` — Inter 132pt bold, red `#FF2E4D` accent stripe 60px, scrim 0.0/0.85, 6×4 landscape

### Tests
- `tests/postcard/__init__.py` — package marker
- `tests/postcard/schema_renderer/__init__.py` — package marker
- `tests/postcard/schema_renderer/test_schema_model.py` — 17 tests: import smoke, minimal template, missing front/back rejection, schema_version=='1', snake_case name, extra-forbid top-level, hex validation, canvas required + zero-dim rejection, scrim defaults preserved, cross-package validate_hex_color import, ShapeElement variants (rect/linear/radial), TextElement (content_key + static)
- `tests/postcard/schema_renderer/test_loader.py` — 17 tests: list_templates returns list, includes starters, unknown raises FileNotFoundError, by-path branch, malformed JSON, classic_portrait + modern_landscape canvas dim assertions, parametrized front-has-image_placeholder-hero, front-has-headline-content_key, back-has-all-3-address_block-content_keys, has-front-and-back-panels, load-each-template

**Total:** 34 tests, all passing.

## Decisions Made

- **Copy vs. import flyer primitives:** Copied `GradientStop`/`SolidFill`/`Linear+RadialGradientFill`/`TextureSlotFill`/`Fill`/`Stroke`/`ShapeElement`/`TextElement`/`BulletsElement`/`LogoPlaceholder`/`ImagePlaceholder`/`DividerElement`/`PanelElement`/`PanelSchema` verbatim rather than importing from `flyer_generator.flyer.schema_renderer.schema_model`. This keeps the postcard→flyer dependency graph limited to one shared utility (`validate_hex_color` from brochure.models). Rationale matches 22-01-SUMMARY.md decision (copying is the lesser evil vs. cross-package `schema_renderer` import anti-pattern).
- **Canvas required, no defaults:** Postcards have two equally-valid USPS-standard sizes (4×6 portrait 1200×1800, 6×4 landscape 1800×1200). No single default canvas makes sense — authors MUST declare it.
- **Omitted `subtype_compat`:** Postcards are a single creative primitive. Unlike flyer's event/info split, the postcard request schema doesn't subtype, so the field would be dead surface area inviting downstream confusion.
- **Palette keeps scrim_opacity:** Front panels DO compose scrim over hero (mirroring flyer cover treatment). Even though back panels typically ignore these knobs, defaults are harmless when unused.
- **Back panel = typographic-only convention (encoded in JSON, not schema):** Both shipped templates put image_placeholder only on the front. The schema permits any element on either panel; the convention is enforced by-template, leaving authors flexibility for future templates that might place imagery on the back.
- **content_key namespace locked per CONTEXT.md:** `headline` (front title), `body` (back body), `address_block.recipient_name` / `.street` / `.city_state_zip` (back address column). Both shipped templates reference these exact keys, ready for the content resolver in plan 23-04.

## Deviations from Plan

None — plan executed exactly as written. The TDD RED→GREEN cycle caught no schema/JSON mismatches on first run; all 34 tests passed without iteration after the JSONs were authored.

## Issues Encountered

None.

## Threat Flags

None — the trust-boundary mitigations documented in the plan's `<threat_model>` are all satisfied:

- **T-23-02 (Malformed JSON panic):** Mitigated. `extra="forbid"` on every `BaseModel` (18 occurrences in `schema_model.py`) plus required-panel validator force failure at load time.
- **T-23-01 (loader .json-suffix path traversal):** Accepted at this layer per plan disposition — deferred to worker plan 23-04 which MUST add `_validate_template_slug` guard before calling `load_template`. This SUMMARY records the deferred mitigation.
- **T-23-03 (FileNotFoundError path leak):** Accepted per plan disposition — server-internal path, FE never displays raw exception strings.

No new threat surface introduced beyond the registered items.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Plan 23-02 (request schema):** `PostcardCreateRequest.template` field can validate against `list_templates()` (returns `['classic_portrait', 'modern_landscape']` sorted) for early-rejection of unknown templates.
- **Plan 23-04 (renderer + worker):** Can `from flyer_generator.postcard.schema_renderer import load_template` at module scope. MUST add `_validate_template_slug` guard rejecting `.json` suffix and path separators BEFORE calling `load_template` (T-23-01 mitigation; mirror Phase 22 worker pattern). Both shipped templates declare both panels with all 5 required content_keys ready for the content resolver to populate.
- **FE template list (plan 23-06):** `list_templates()` is sorted alphabetically; FE can rely on the order `['classic_portrait', 'modern_landscape']`.

## TDD Gate Compliance

Both tasks followed RED→GREEN cycle with explicit commits visible in `git log`:

- **Combined RED (Task 1+2 tests):** `ac8d030` — `test(23-01): add failing tests for PostcardTemplateSchema + loader` (writes 34 tests; all fail with `ModuleNotFoundError: No module named 'flyer_generator.postcard'`)
- **Task 1 GREEN:** `8fa4ec6` — `feat(23-01): implement PostcardTemplateSchema + loader + package barrel` (17/17 schema tests pass; 4/17 loader tests pass; 13 remain failing pending JSONs)
- **Task 2 GREEN:** `4f2b24d` — `feat(23-01): ship 2 starter postcard templates` (final 34/34 pass)

No REFACTOR phase commits needed — code was minimal-correct on first pass. The verbatim primitive copy from flyer schema means no test-driven evolution was required at the primitive layer.

## Self-Check: PASSED

Verified each created file exists and each commit hash is reachable:

- `flyer_generator/postcard/__init__.py` FOUND
- `flyer_generator/postcard/schema_renderer/__init__.py` FOUND
- `flyer_generator/postcard/schema_renderer/schema_model.py` FOUND
- `flyer_generator/postcard/schema_renderer/loader.py` FOUND
- `flyer_generator/postcard/schemas/classic_portrait.json` FOUND
- `flyer_generator/postcard/schemas/modern_landscape.json` FOUND
- `tests/postcard/__init__.py` FOUND
- `tests/postcard/schema_renderer/__init__.py` FOUND
- `tests/postcard/schema_renderer/test_schema_model.py` FOUND
- `tests/postcard/schema_renderer/test_loader.py` FOUND
- Commit ac8d030 FOUND
- Commit 8fa4ec6 FOUND
- Commit 4f2b24d FOUND

---
*Phase: 23-postcard-primitive*
*Completed: 2026-04-25*
