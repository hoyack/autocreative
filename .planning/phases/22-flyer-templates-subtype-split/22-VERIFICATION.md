---
phase: 22-flyer-templates-subtype-split
verified: 2026-04-23T00:00:00Z
status: human_needed
score: 5/5 success criteria verified
overrides_applied: 0
human_verification:
  - test: "Visit /flyers/new in the running FE; pick each of the 6 templates × 2 subtypes (skip retro_poster+info and bold_modern+info per subtype_compat) and submit"
    expected: "Form renders the template Select with 6 entries and the subtype Select with event/info; switching to info hides date/time/venue/fees and exposes description+CTA; submission yields a /flyers/:id status page that eventually shows a rendered PNG"
    why_human: "Visual quality, real-time worker progression, and PNG appearance cannot be asserted programmatically; Phase 22 ships pixel-bearing artifacts whose look-and-feel is the deliverable"
  - test: "Run /tmp/check-e2e-flyer-22.mjs against a live four-service stack (uvicorn :8000 on Phase-22 code, arq worker, redis, vite :5173)"
    expected: "All 10 valid permutations produce status-page screenshots with rendered PNGs in /tmp/phase22-shots/; script exits 0 with 'Total: 10, Passed: 10, Failed: 0'"
    why_human: "Plan 07 explicitly deferred the end-to-end run because the user's :8000 backend was running pre-Phase-22 code at execute time; only static syntax/coverage checks were performed"
---

# Phase 22: Flyer Templates & Subtype Split Verification Report

**Phase Goal:** A user can render a flyer by picking one of 5+ JSON-defined templates and a subtype (`event` or `info`), and the API, worker, pipeline, database kind enum, and React creator page all honor the selection with event-only fields conditionally hidden for info flyers.

**Verified:** 2026-04-23
**Status:** human_needed (5/5 success criteria verified programmatically; 2 visual/runtime items defer to human)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `POST /api/v1/flyers` accepts a required `template` field and a `subtype` field defaulting to `"event"`; back-compat for omitted subtype | VERIFIED | `flyer_generator/api/schemas/flyers.py:26` defines `template: str = Field(min_length=1, max_length=64)`. Spot-check rejects missing/empty template with ValidationError. `FlyerInput.subtype` defaults to `"event"`. `frontend/src/api/openapi.snapshot.json` reports `FlyerCreateRequest.required = ['event', 'template', 'preset']`. |
| 2 | Template registry at `flyer_generator/flyer/schemas/*.json` ships 5+ templates validated by `FlyerTemplateSchema`; `PosterComposer.compose()` reads typography scale, scrim opacity, accent placement, shape mix from the selected template | VERIFIED | `flyer_generator/flyer/schemas/` contains 6 JSON files (bold_modern, editorial_classic, minimal_photo, retro_poster, tight_typographic, zine). All load via `load_template()`; canvas 1080x1920; 5–10 hero elements each. `flyer_generator/stages/composer.py` defines `_template_heading_family`, `_template_body_family`, `_template_scrim_opacity`, `_template_accent`, `_template_cover_title_size` (lines 202–242) and consumes them in `_build_svg`. |
| 3 | Info flyer accepts `description`+optional `call_to_action` (no date/venue/fees required); vision prompt names TITLE+DESCRIPTION+ORG_CREDIT only | VERIFIED | `flyer_generator/models.py:27` FlyerInput exposes optional `description: str \| None = Field(max_length=600)` and `call_to_action`. `flyer_generator/stages/vision.py:30,68,100` defines `VISION_SYSTEM_PROMPT_EVENT`, `VISION_SYSTEM_PROMPT_INFO`, and back-compat alias `VISION_SYSTEM_PROMPT = VISION_SYSTEM_PROMPT_EVENT`. `evaluate()` branches on `event.subtype` (line 156). |
| 4 | `RenderRecord.kind` stores `flyer_event_final`/`flyer_info_final`; alembic migration rewrites pre-existing `flyer_final` rows from `event_payload.event.subtype` (default 'event') | VERIFIED | `alembic/versions/f22t01_flyer_template_and_subtype_split.py` revision `f22t01`, down `2f5971e114b3`, head confirmed via alembic. UPDATE filters `WHERE kind = 'flyer_final'` (idempotent); SQLite `json_extract` and Postgres `->'event'->>'subtype'` paths both present; downgrade collapses both back to `flyer_final` and drops the column. `tests/api/test_migrations.py` runs (6 tests pass) including idempotency + downgrade. |
| 5 | `/flyers/new` exposes template + subtype Selects with conditional event-only fields; gallery filter includes `flyer_event_final` + `flyer_info_final` | VERIFIED | `frontend/src/pages/flyers/new.tsx` has `TEMPLATES` (6) + `SUBTYPES` (2) tuples, FormFields `name="template"`, `name="event.subtype"`, `name="event.description"`, `name="event.call_to_action"`, conditional blocks `subtype === "event"` (line 322) and `subtype === "info"` (line 413), and `superRefine` (line 137) enforcing subtype-specific required fields. `frontend/src/pages/renders/gallery.tsx:31-32` lists `flyer_event_final, flyer_info_final` (legacy `flyer_final` removed from KINDS). `tests/flyer/schema_renderer/test_render_smoke.py` + `tests/api/test_flyer_e2e_permutations.py` cover all 10 permutations programmatically. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `flyer_generator/flyer/schema_renderer/schema_model.py` | FlyerTemplateSchema + primitives | VERIFIED | exists; class declared; subtype_compat defaults to ['event','info'] |
| `flyer_generator/flyer/schema_renderer/loader.py` | load_template + list_templates | VERIFIED | exists; functions defined at lines 13, 35; _SCHEMAS_DIR points at parent/schemas |
| `flyer_generator/flyer/schema_renderer/__init__.py` | Public barrel | VERIFIED | exists; re-exports FlyerTemplateSchema, load_template, list_templates |
| `flyer_generator/flyer/schemas/{6 templates}.json` | 6 template JSONs | VERIFIED | All 6 load successfully; all 1080x1920; subtype_compat correct (bold_modern + retro_poster = event-only) |
| `flyer_generator/models.py::FlyerInput + EventInput alias` | FlyerInput + alias + relaxed LayoutZones | VERIFIED | `class FlyerInput` at line 27; `EventInput = FlyerInput` at line 66; LayoutZones `details: ZoneName \| None = None` (line 98), `fee_badge: ZoneName \| None = None` (line 99) |
| `flyer_generator/__init__.py` | Re-exports FlyerInput | VERIFIED | line 12 imports both; `__all__` includes both |
| `flyer_generator/stages/vision.py` | Subtype-aware prompts + branching | VERIFIED | EVENT/INFO/alias defined; `evaluate()` branches at line 156 |
| `flyer_generator/stages/composer.py` | Template kwarg + subtype-aware rendering | VERIFIED | `compose(...) template: FlyerTemplateSchema \| None = None` at line 260; 5 helpers; `is_info` branch at line 310; xml_escape applied to all user-supplied strings |
| `flyer_generator/pipeline.py` | FlyerGenerator.generate template kwarg | VERIFIED | KEYWORD_ONLY `template` at line 70 with default None; `template=template` passed to composer at line 134 |
| `flyer_generator/api/schemas/flyers.py` | FlyerCreateRequest.template required | VERIFIED | line 26 `template: str = Field(min_length=1, max_length=64)`; `event: FlyerInput` at line 25 |
| `flyer_generator/api/models/flyer.py` | FlyerRecord.template column | VERIFIED | line 22 `template: Mapped[str] = mapped_column(String(64), nullable=False)` |
| `flyer_generator/api/models/render.py` | Updated kind comment | VERIFIED | lines 23–26 enumerate `flyer_event_final`, `flyer_info_final`, document deprecated `flyer_final` |
| `flyer_generator/api/tasks/flyer.py` | Worker template loading + subtype-derived kind + slug guard | VERIFIED | module-scope import line 29; `_validate_template_slug` line 34 (rejects `.json`, `/`, `\\`); load_template called line 91; render_kind derived line 105–107; `template=template_name` line 126 |
| `alembic/versions/f22t01_flyer_template_and_subtype_split.py` | Migration adds template column + rewrites kinds | VERIFIED | revision f22t01 head confirmed; SQLite + Postgres branches; idempotent WHERE clause; reversible downgrade |
| `frontend/src/pages/flyers/new.tsx` | Template + subtype Selects + conditional fields | VERIFIED | TEMPLATES tuple (6 items) + SUBTYPES tuple; superRefine subtype validation; conditional blocks for event vs info |
| `frontend/src/pages/renders/gallery.tsx` | KINDS includes both new flyer kinds | VERIFIED | lines 31–32 list new kinds in tuple; legacy `flyer_final` only present in explanatory comment, NOT in KINDS array |
| `frontend/src/pages/jobs/list.tsx` | Unchanged with documented no-op | VERIFIED | lines 28–32 explain RenderKind-level vs JobKind-level decision; KINDS still has plain `flyer` |
| `frontend/src/api/openapi.snapshot.json` | Regen with template + subtype | VERIFIED | `FlyerCreateRequest.required` includes `template`; `FlyerInput.subtype` enum `event\|info` default `event`; `FlyerInput.description` + `call_to_action` present |
| `frontend/src/api/schema.gen.ts` | Regenerated TS types | VERIFIED | `template: string` at lines 623/656/752; `subtype: "event" \| "info"` at line 779 |
| `tests/flyer/schema_renderer/test_render_smoke.py` | Composer permutation matrix | VERIFIED | exists; 20 tests; matrix derived from list_templates() + subtype_compat |
| `tests/api/test_flyer_e2e_permutations.py` | HTTP+worker permutation suite | VERIFIED | exists; 21 tests; covers 10 permutations |
| `tests/api/test_migrations.py` | Migration up/down + idempotency | VERIFIED | exists; 6 tests; passes |
| `/tmp/check-e2e-flyer-22.mjs` | Playwright harness | VERIFIED (static) | file exists, executable, parses with `node --check`, contains 10 PERMUTATIONS, references all 6 templates and both subtypes |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `frontend/src/pages/flyers/new.tsx` | `POST /api/v1/flyers` | openapi-fetch POST | WIRED | Submit handler builds body with template + subtype-cleaned event; uses generated TS types |
| `frontend/src/pages/flyers/new.tsx` | `frontend/src/api/schema.gen.ts::FlyerCreateRequest` | TypeScript type import | WIRED | Form schema + submit body shape track regenerated types; pnpm typecheck passes |
| `flyer_generator/api/tasks/flyer.py` | `flyer_generator.flyer.schema_renderer.loader::load_template` | module-scope import (BLOCKER-2 pattern) | WIRED | line 29 imports load_template at module scope; line 91 calls it with the slug; tests patch via `flyer_generator.api.tasks.flyer.load_template` |
| `flyer_generator/api/tasks/flyer.py` | `FlyerGenerator.generate` | `template=template` kwarg | WIRED | line 96 `await gen.generate(flyer_input, template=template)` — loaded schema (not the slug) is threaded |
| `flyer_generator/pipeline.py` | `flyer_generator/stages/composer.py::PosterComposer.compose` | `template=template` kwarg | WIRED | pipeline line 134 passes `template=template` |
| `flyer_generator/stages/vision.py::evaluate` | `VISION_SYSTEM_PROMPT_INFO` | `if event.subtype == "info"` branch | WIRED | line 156 selects info prompt; user-text differs (Headline/Description vs Date/Venue) |
| `alembic f22t01.upgrade` | `renders.kind` rewrite | `WHERE kind = 'flyer_final'` UPDATE | WIRED | idempotent guard; COALESCE defaults missing subtype to 'event'; SQLite + Postgres dialect branches; downgrade is reversible |
| `frontend/src/pages/renders/gallery.tsx::KINDS` | renders.kind values emitted by worker | tuple membership | WIRED | both `flyer_event_final` and `flyer_info_final` in tuple; legacy removed |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 6 templates load | `python -c "from flyer_generator.flyer.schema_renderer import list_templates, load_template; [load_template(n) for n in list_templates()]"` | 6 templates load; canvas 1080x1920 each; subtype_compat as expected (bold_modern + retro_poster event-only) | PASS |
| FlyerCreateRequest enforces template | `FlyerCreateRequest.model_validate({...no template...})` and `template=""` | both raise ValidationError | PASS |
| EventInput alias | `EventInput is FlyerInput` | True | PASS |
| FlyerInput.subtype defaults to 'event' | `FlyerInput.model_fields['subtype'].default` | `'event'` | PASS |
| FlyerGenerator.generate has KEYWORD_ONLY template | inspect.signature | `(self, event, *, template: ... = None)` | PASS |
| Worker rejects path-like slugs | `_validate_template_slug` for `foo.json`, `../etc/passwd`, `a/b`, `a\b` | all raise ValueError; bare slugs accepted | PASS |
| alembic head | `.venv/bin/alembic heads` | `f22t01 (head)` | PASS |
| Permutation + migration test suite | `.venv/bin/pytest tests/flyer/schema_renderer/test_render_smoke.py tests/api/test_flyer_e2e_permutations.py tests/api/test_migrations.py -q` | 47 passed, 0 failed | PASS |
| Phase 22 backend test scope | `.venv/bin/pytest tests/api/ tests/flyer/ tests/unit/test_composer_template_driven.py tests/unit/test_pipeline_template_threading.py tests/unit/test_models_flyer_input.py tests/unit/test_vision_subtype_prompt.py -q` | 320 passed, 0 failed | PASS |
| Playwright harness syntax | `node --check /tmp/check-e2e-flyer-22.mjs` | exits 0 (valid ESM) | PASS |
| OpenAPI snapshot Phase-22 schema | `python ... json.load(...)['components']['schemas']['FlyerCreateRequest']['required']` | `['event', 'template', 'preset']` and `subtype` enum + default present, description + call_to_action present | PASS |
| Layout resolver None-aware | grep `flyer_generator/stages/layout.py` | `details=(... if zones.details is not None else None)` and same for fee_badge | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| FT-01 | 22-04, 22-05 | Required `template` field at POST + worker loads template by name | SATISFIED | FlyerCreateRequest.template required (Field min/max length); worker loads + slug-guards + threads template; FlyerRecord.template column + populated row |
| FT-02 | 22-01 | 5+ JSON-defined templates validated by FlyerTemplateSchema | SATISFIED | 6 JSON templates (`flyer_generator/flyer/schemas/*.json`) all load via `load_template()`; FlyerTemplateSchema enforces `panels.hero` |
| FT-03 | 22-01, 22-03 | Templates declare typography + scrim + accent + shape mix; composer reads them | SATISFIED | Each template declares typography/scrim/accent/shape (verified by tests/flyer/schema_renderer/test_loader.py::test_template_declares_typography_or_scrim_or_shape); composer pulls all four via 5 `_template_*` helpers |
| FT-04 | 22-02 | FlyerInput adds subtype Literal + relaxes event-only fields | SATISFIED | `class FlyerInput` line 27 with subtype Literal['event','info']='event'; date/time/location_*/fees all `str \| None = None`; LayoutZones details/fee_badge None-able |
| FT-05 | 22-02 | Info subtype with description + call_to_action; vision branches | SATISFIED | description/call_to_action fields present; VISION_SYSTEM_PROMPT_INFO defined and selected by `evaluate()` when subtype=='info' |
| FT-06 | 22-05 | RenderRecord.kind gains flyer_event_final/flyer_info_final; alembic migrates flyer_final by inspecting subtype | SATISFIED | RenderRecord.kind comment lists both new kinds; f22t01 migration rewrites with COALESCE default 'event'; idempotent + reversible |
| FT-07 | 22-06 | FE flyer creator: template + subtype Selects + conditional fields | SATISFIED | TEMPLATES + SUBTYPES tuples in flyers/new.tsx; FormFields for template, event.subtype, event.description, event.call_to_action; superRefine enforces subtype rules; conditional event-only block |
| FT-08 | 22-06, 22-07 | Gallery KINDS includes new kinds; permutation harness extended | SATISFIED | gallery.tsx KINDS tuple updated; tests/flyer/.../test_render_smoke.py (20 tests) + tests/api/test_flyer_e2e_permutations.py (21 tests) cover all 10 permutations; /tmp/check-e2e-flyer-22.mjs Playwright script exists and parses cleanly. End-to-end run deferred to human verification |

All 8 declared requirement IDs are accounted for; no orphaned requirements found in REQUIREMENTS.md mapping for Phase 22.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `flyer_generator/flyer/schemas/*.json` | various | hardcoded values inside JSON template definitions | Info | Expected — templates are configuration data, not stubs. |
| `frontend/src/pages/renders/gallery.tsx` | 25–28 | comment references legacy `flyer_final` | Info | Documented as intentional in 22-06-SUMMARY (preserves migration documentation); the literal grep criterion is functionally satisfied because the legacy value is gone from the KINDS tuple itself. |

No blocker (🛑) or warning (⚠️) anti-patterns found. The composer's hardcoded fallback values inside `_template_*` helpers (e.g., default 0.75 scrim, default 'Arial Black' family) are intentional back-compat fallbacks for the `template=None` path, not stubs.

### Human Verification Required

#### 1. Visual smoke of /flyers/new

**Test:** Navigate to `/flyers/new` in the running FE; pick each of the 6 templates with subtype=event, then editorial_classic/minimal_photo/zine/tight_typographic with subtype=info. Submit each.
**Expected:** Form renders the template Select with 6 entries and the subtype Select with event/info; switching to info hides date/time/venue/fees and exposes description+CTA; submission yields a `/flyers/:id` status page that eventually shows a rendered PNG.
**Why human:** Visual quality, real-time worker progression, and PNG appearance cannot be asserted programmatically; Phase 22 ships pixel-bearing artifacts whose look-and-feel is the deliverable.

#### 2. Live Playwright permutation run

**Test:** Bring up the four-service stack against Phase-22 worktree code (uvicorn :8000, arq worker, redis :6379, vite :5173) and run `node /tmp/check-e2e-flyer-22.mjs`.
**Expected:** All 10 valid permutations produce status-page screenshots with rendered PNGs in `/tmp/phase22-shots/`; script exits 0 with `Total: 10, Passed: 10, Failed: 0`.
**Why human:** Plan 07 explicitly deferred the end-to-end run because the user's :8000 backend was running pre-Phase-22 code at execute time. Only static (syntax + coverage) checks were performed. Re-running against a fresh stack is required to confirm FT-08's harness-side guarantee.

### Gaps Summary

No gaps. All 5 ROADMAP success criteria are satisfied programmatically by the codebase. All 8 requirement IDs (FT-01 through FT-08) map to verified evidence. Two human-verification items remain because (a) visual quality of generated flyers cannot be auto-asserted and (b) the Playwright harness needs the four-service stack online — these are validation steps, not implementation gaps.

Notable bonus discoveries during execution that strengthen the phase:
- Plan 07 caught and fixed a Rule-1 production bug in `flyer_generator/stages/layout.py`: `LayoutResolver.resolve()` was crashing with `KeyError(None)` for any info-subtype flyer because Plan 02's Optional relaxation never reached the resolver. Fix is one-line None passthrough; verified by grep + 20 render-smoke tests passing.
- T-22-10 path-traversal mitigation (`_validate_template_slug`) sits in the worker BEFORE `load_template`, blocking `.json`, `/`, and `\\` slugs even though FlyerCreateRequest's max_length=64 alone would not.

---

*Verified: 2026-04-23*
*Verifier: Claude (gsd-verifier)*
