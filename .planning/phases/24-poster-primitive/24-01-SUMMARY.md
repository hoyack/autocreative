---
phase: 24-poster-primitive
plan: 01
subsystem: poster

tags: [poster, schema, pydantic-v2, template-registry, print-typography, json-templates]

requires:
  - phase: 22-flyer-templates
    provides: FlyerTemplateSchema + load_template/list_templates pattern (cloned verbatim)
  - phase: 22-flyer-templates
    provides: validate_hex_color helper exported from flyer_generator.brochure.models
provides:
  - PosterTemplateSchema Pydantic v2 model with print-scaled defaults (Canvas 5400x7200, cover_title_size=300)
  - load_template / list_templates string-lookup loader for poster JSON templates
  - 3 shipped poster templates (editorial_grand, bold_announcement, cinematic_onesheet)
  - _SCHEMAS_DIR convention rooted at flyer_generator/poster/schemas/
affects:
  - 24-02-poster-request-schema  # PosterCreateRequest.template field validates against list_templates()
  - 24-04-poster-worker  # task_generate_poster will call load_template(slug) at module scope (BLOCKER-2 mirror)
  - 24-03-pipeline-injectable-canvas  # FlyerGenerator(canvas_dimensions=...) renders the templates' design canvas

tech-stack:
  added: []
  patterns:
    - "Verbatim primitive copy from flyer schema_model — same Pydantic primitives (GradientStop, Fill discriminated union, ShapeElement, TextElement, etc.), only the top-level wrapper class + Canvas + Typography defaults differ. Avoids cross-package imports at module boundary."
    - "Print-scaled typography defaults (cover_title_size=300 vs flyer's 82) baked into Pydantic Field defaults — templates may override per design intent (editorial_grand=360, bold_announcement=420, cinematic_onesheet=380)."
    - "subtype_compat field dropped via extra='forbid' — posters have no event/info split."

key-files:
  created:
    - flyer_generator/poster/__init__.py
    - flyer_generator/poster/schema_renderer/__init__.py
    - flyer_generator/poster/schema_renderer/schema_model.py
    - flyer_generator/poster/schema_renderer/loader.py
    - flyer_generator/poster/schemas/editorial_grand.json
    - flyer_generator/poster/schemas/bold_announcement.json
    - flyer_generator/poster/schemas/cinematic_onesheet.json
    - tests/poster/__init__.py
    - tests/poster/schema_renderer/__init__.py
    - tests/poster/schema_renderer/test_schema_model.py
    - tests/poster/schema_renderer/test_loader.py
  modified: []

key-decisions:
  - "Cloned flyer schema_model.py verbatim (primitive cascade) to avoid cross-package import from poster -> flyer; same justification as flyer's clone of brochure primitives."
  - "Canvas defaults to 5400x7200 (18x24 portrait at 300 DPI) — the template's design canvas; the worker re-canvases per requested size preset (24x36 / 27x40) at render time per locked decision in 24-CONTEXT.md."
  - "Typography.cover_title_size defaults to 300 (~3.65× flyer's 82) for print-distance reading. Per-template overrides land in the JSON: editorial_grand=360 (serif), bold_announcement=420 (display), cinematic_onesheet=380 (theatrical)."
  - "Dropped subtype_compat field — posters have no event/info subtype split. extra='forbid' rejects the field if accidentally included in a JSON template."

patterns-established:
  - "Poster template registry mirrors the flyer registry pattern verbatim — same _SCHEMAS_DIR resolution, same load_template name-or-path branching, same FileNotFoundError-with-available-list error message."
  - "Print-scaled typography is a poster-package concern, not a renderer concern. The composer reads typography.cover_title_size as a point value at 300 DPI; no callsite-side magic numbers."
  - "Each poster JSON template ships at least one ShapeElement + one TextElement to prove the schema accepts non-trivial content; verified by parametrized tests."

requirements-completed: [PO-03]

# Metrics
duration: 6min
completed: 2026-04-25
---

# Phase 24 Plan 01: Poster Template Registry Summary

**PosterTemplateSchema Pydantic v2 model + string-lookup loader + 3 shipped JSON templates (editorial_grand / bold_announcement / cinematic_onesheet) tuned for 18x24 to 27x40 print-distance reading.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-25T07:31:10Z
- **Completed:** 2026-04-25T07:37:09Z
- **Tasks:** 2 (TDD plan: 1 test commit + 2 feat commits)
- **Files created:** 11

## Accomplishments

- `PosterTemplateSchema` lands as a strict Pydantic v2 model (`extra="forbid"`) with print-scaled defaults baked in: Canvas 5400x7200, cover_title_size=300, body_size=120, body_line_height=160. The full primitive cascade (GradientStop → Fill discriminated union → ShapeElement / TextElement / BulletsElement / LogoPlaceholder / ImagePlaceholder / DividerElement → PanelElement → PanelSchema) is copied verbatim from the flyer schema_model to avoid a cross-package dependency at module boundary.
- `load_template` + `list_templates` string-lookup loader mirrors the flyer pattern verbatim: name-or-path branching on `.endswith(".json")`, FileNotFoundError-with-available-list messaging, sorted directory listing.
- Three shipped poster templates each ship at least one ShapeElement + one TextElement, declare cover_title_size >= 200 (print-distance reading), and validate against the schema:
  - **editorial_grand** — serif title (Playfair Display / Source Serif Pro), cover_title_size=360, narrow scrim, full-bleed hero, accent rule along bottom.
  - **bold_announcement** — sans display title (Helvetica Neue / Arial Black), cover_title_size=420 uppercase, full-canvas dark linear-gradient scrim (0.85→0.50), red 40px accent stripe, centered title + CTA tag.
  - **cinematic_onesheet** — Bebas Neue / Impact display, cover_title_size=380, upper-70% image + lower-30% solid dark block carrying subtitle/body/CTA in white-on-dark, framed by two 12px gold accent stripes inset 50px.
- 33/33 poster tests pass (12+ behavior requirement easily exceeded). 1627 total tests pass — no regressions in flyer, brochure, postcard, social, API, or any other subsystem.

## Task Commits

1. **RED gate (Task 1 tests):** `407c978` — `test(24-01): add failing tests for poster schema_model + loader`
2. **GREEN gate (Task 1 implementation):** `9d4fe96` — `feat(24-01): add PosterTemplateSchema + load_template (PO-03)`
3. **Task 2 (3 JSON templates):** `988c0b0` — `feat(24-01): add 3 poster JSON templates (editorial_grand/bold_announcement/cinematic_onesheet)`

REFACTOR gate: not needed — implementation followed the plan's verbatim-clone directive; no cleanup pass required.

## Files Created/Modified

- `flyer_generator/poster/__init__.py` — package marker with public-API docstring.
- `flyer_generator/poster/schema_renderer/__init__.py` — barrel re-exporting `PosterTemplateSchema`, `load_template`, `list_templates`.
- `flyer_generator/poster/schema_renderer/schema_model.py` — full primitive cascade + `PosterTemplateSchema` (no `subtype_compat`); Canvas defaults to (5400, 7200); Typography defaults print-scaled with cover_title_size=300; `_validate_panels_complete` requires {"hero"}.
- `flyer_generator/poster/schema_renderer/loader.py` — `load_template(name_or_path) -> PosterTemplateSchema` + `list_templates() -> list[str]`; `_SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"`.
- `flyer_generator/poster/schemas/editorial_grand.json` — serif title, narrow scrim, full-bleed hero (3 elements + image_placeholder).
- `flyer_generator/poster/schemas/bold_announcement.json` — sans display, full-canvas scrim, accent stripe (5 elements + image_placeholder).
- `flyer_generator/poster/schemas/cinematic_onesheet.json` — heavy bottom block, two accent stripes, theatrical layout (7 elements + image_placeholder).
- `tests/poster/schema_renderer/test_schema_model.py` — 17 tests (TestPosterTemplateSchema, TestShapeElement, TestTextElement, plus barrel-import smoke).
- `tests/poster/schema_renderer/test_loader.py` — 16 tests (list_templates, load_template by name + path, FileNotFoundError, malformed JSON, missing-dir handling, plus 3 parametrized × 3 templates = 9 assertions on shipped templates).
- `tests/poster/__init__.py`, `tests/poster/schema_renderer/__init__.py` — package markers.

## Decisions Made

None beyond what was locked in `24-01-PLAN.md` and `24-CONTEXT.md`. Plan executed exactly as written:

- Verbatim primitive copy from flyer `schema_model.py` (per plan's `<patterns>` block).
- Canvas defaults match plan's `<interfaces>` block (5400, 7200).
- Typography defaults match plan's `<interfaces>` block (cover_title_size=300, etc.).
- `subtype_compat` dropped (per plan).
- `_PanelName = Literal["hero"]` retained (single-canvas, per plan).
- Loader is a verbatim clone of the flyer loader with the schema class swapped (per plan).
- Three template names + tone keywords match plan's locked list.

## Deviations from Plan

None — plan executed exactly as written.

The plan's <action> block specified:
- "12+ pytests" — delivered **33** (8 schema_model behavior + 3 ShapeElement + 2 TextElement + 1 import smoke + 7 loader behavior + 9 parametrized assertions across 3 templates + 3 misc).
- "cover_title_size >= 200" — all three templates clear this floor (360, 420, 380 respectively).
- "extras dict" on Palette retained from flyer — not explicitly in the JSON templates, but available for future use.

The TDD gate sequence was followed:
1. RED commit (`407c978`): tests collected with `ModuleNotFoundError` as expected before implementation.
2. GREEN commit (`9d4fe96`): 23/33 tests pass after schema_model + loader land; remaining 10 fail on missing JSON templates (expected — those land in Task 2).
3. Task 2 commit (`988c0b0`): 33/33 tests pass after JSON templates land.

## Issues Encountered

None.

## TDD Gate Compliance

- RED gate: `407c978` (`test(24-01): ...`) — failing tests committed before implementation. Confirmed `ModuleNotFoundError` at collection time.
- GREEN gate: `9d4fe96` (`feat(24-01): add PosterTemplateSchema + load_template (PO-03)`) — minimal implementation to make schema_model + loader tests pass. 23/33 pass at this point (the 10 remaining all depend on the JSON templates landing in Task 2, which is the plan's explicit task split).
- REFACTOR gate: skipped (not needed; implementation followed plan's verbatim-clone directive).

## User Setup Required

None — no external service configuration required. The poster template registry is internal Python, file-system only.

## Next Phase Readiness

This plan is the foundation for the rest of Phase 24:

- **24-02 (poster request schema):** `PosterCreateRequest.template` slug validates against `list_templates()`. Ready.
- **24-03 (pipeline injectable canvas):** `FlyerGenerator(canvas_dimensions=size_to_dim(size))` consumes the templates' design canvas (5400x7200) and rasterizes at the requested print preset. Ready.
- **24-04 (poster worker):** `task_generate_poster` will `from flyer_generator.poster.schema_renderer.loader import load_template` at module scope (BLOCKER-2 mirror) + path-traversal-guard the slug. Ready.
- **24-05/06 (frontend / route):** `template` Select on `/posters/new` enumerates `list_templates()` via the existing pattern. Ready.

No blockers. No deferred items.

## Self-Check: PASSED

Files verified to exist:
- FOUND: flyer_generator/poster/__init__.py
- FOUND: flyer_generator/poster/schema_renderer/__init__.py
- FOUND: flyer_generator/poster/schema_renderer/schema_model.py
- FOUND: flyer_generator/poster/schema_renderer/loader.py
- FOUND: flyer_generator/poster/schemas/editorial_grand.json
- FOUND: flyer_generator/poster/schemas/bold_announcement.json
- FOUND: flyer_generator/poster/schemas/cinematic_onesheet.json
- FOUND: tests/poster/__init__.py
- FOUND: tests/poster/schema_renderer/__init__.py
- FOUND: tests/poster/schema_renderer/test_schema_model.py
- FOUND: tests/poster/schema_renderer/test_loader.py

Commits verified to exist on master:
- FOUND: 407c978 (RED gate — failing tests)
- FOUND: 9d4fe96 (GREEN gate — schema_model + loader)
- FOUND: 988c0b0 (Task 2 — 3 JSON templates)

Test count: 33 poster tests pass. 1627 total tests pass (no regressions).

---
*Phase: 24-poster-primitive*
*Plan: 01*
*Completed: 2026-04-25*
