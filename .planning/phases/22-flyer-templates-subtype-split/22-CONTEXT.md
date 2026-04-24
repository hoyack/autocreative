# Phase 22: Flyer Templates & Subtype Split — Context

**Gathered:** 2026-04-24
**Status:** Ready for planning
**Source:** User-approved plan at `/home/hoyack/.claude/plans/lets-expand-the-flyer-gentle-cat.md` + Phase 21 exploration

<domain>
## Phase Boundary

This phase makes flyers **templated** (like brochures) and **subtype-aware** (event vs. info).

**In scope:**
- JSON-schema flyer template registry mirroring `flyer_generator/brochure/schemas/`
- 5+ flyer templates shipping at launch
- `FlyerInput` model with `subtype: Literal["event", "info"]` and optional event-only fields
- Vision prompt branching on subtype (info flyers omit DETAILS / FEE_BADGE zones)
- `RenderRecord.kind` migration: `flyer_final` → `flyer_event_final` | `flyer_info_final`
- FE flyer creator: template `<Select>` + subtype `<Select>` + conditional date/time/venue/fees fields
- Jobs filter + Renders gallery filter additions for the new kinds
- Backend tests + FE tests + Playwright permutation harness

**Out of scope (deferred to later phases / future):**
- Template discovery API (`GET /api/v1/flyers/templates`) — FE hardcodes the list, same as brochures
- LLM-driven template selection (tone-based) — the brochure equivalent (`brochure.generative.layout.select_template_for_tone`) exists and could be ported, but is not required
- Postcard / poster / invitation primitives (Phases 23, 24, 25)
- Adversarial test coverage (Phase 26)
- Cross-asset visual regression (Phase 26)
</domain>

<decisions>
## Implementation Decisions (locked from plan)

### Template mechanism

**LOCKED:** Mirror the brochure JSON-schema pattern *verbatim*.

- Registry path: `flyer_generator/flyer/schemas/*.json`
- Pydantic model: `flyer_generator/flyer/schema_renderer/schema_model.py::FlyerTemplateSchema` — copy structure from `flyer_generator/brochure/schema_renderer/schema_model.py`
- Loader: `flyer_generator/flyer/schema_renderer/loader.py::load_template(name_or_path)` — copy from brochure loader
- Selection: `template: str` field on `FlyerCreateRequest` (no enum), validation at worker `load_template()` time, not at schema layer
- Templates ship at launch: `editorial_classic`, `bold_modern`, `minimal_photo`, `retro_poster`, `zine`, `tight_typographic` (6 templates — adjust if any prove redundant during rendering)
- Templates declare typography scale, scrim opacity, accent placement, and shape mix — NOT just color overrides

### Flyer subtype split

**LOCKED:** Single `FlyerInput` model with `subtype` field; no discriminated union.

- Add `subtype: Literal["event", "info"] = "event"` to `flyer_generator/models.py::EventInput`
- Rename `EventInput` → `FlyerInput`; keep `EventInput = FlyerInput` alias (mark deprecated in docstring)
- Make all event-only fields optional: `date`, `time`, `location_name`, `location_address`, `fees`
- Add info-only fields: `description: str | None = None`, `call_to_action: str | None = None`
- Default `subtype="event"` preserves existing API contract for callers that omit it

### Vision prompt branching

**LOCKED:** `flyer_generator/stages/vision.py` system prompt branches on `subtype`.

- Event subtype: existing zones — TITLE, DETAILS, FEE_BADGE, ORG_CREDIT
- Info subtype: TITLE, DESCRIPTION, ORG_CREDIT (no DETAILS, no FEE_BADGE)
- Both subtypes use the same `VisionVerdict` schema; `zones` map keys are subtype-specific

### Composer refactor

**LOCKED:** Template selection plugs in between `LayoutResolver.resolve()` and `PosterComposer.compose()`.

- Plug-in point: `flyer_generator/pipeline.py` line ~111 (after `layout = self._layout.resolve(verdict.zones)`, before `svg = self._composer.compose(...)`)
- `PosterComposer.compose()` signature gains `template: FlyerTemplateSchema` param
- Hardcoded typography (`_title_params`), scrim opacity (`_scrim_for_zone`), accent placement become template-driven lookups
- Template content_key resolution: borrow `BrochureContent.resolve_key()` pattern — flyer `content_key` strings include `"event.title"`, `"event.date"`, `"event.description"`, `"org_credit"`, etc.

### Render kind migration

**LOCKED:** Alembic migration rewrites existing `flyer_final` rows by inspecting `FlyerRecord.event_payload.subtype` (defaults to `event`).

- New `RenderRecord.kind` values: `flyer_event_final`, `flyer_info_final`
- Migration up: rewrite all `flyer_final` rows. Migration down: reverse to `flyer_final`.
- Frontend `KINDS` arrays updated in same phase

### FE conditional fields

**LOCKED:** `frontend/src/pages/flyers/new.tsx` shows event-only fields (date, time, venue, address, fees) only when `subtype === "event"`. Form schema uses `z.discriminatedUnion` or conditional refinement so info-flyer submission doesn't fail validation on empty event fields.

### Claude's Discretion

- Exact JSON shape of each flyer template (panel naming, color binding, shape declarations) — can adapt brochure structure to single-canvas
- Specific decorative details per template — designers' call within the locked typography/scrim/accent contract
- Whether to ship 5 or 6 templates initially — drop one if it duplicates another visually
- Test naming + organization within `tests/flyer/schema_renderer/` — mirror brochure test layout
- Migration version number — alembic auto-assigns
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Brochure pattern (verbatim source of truth)
- `flyer_generator/brochure/schemas/editorial_classic.json` — JSON template shape to mirror
- `flyer_generator/brochure/schema_renderer/schema_model.py` — Pydantic `TemplateSchema` to copy structure
- `flyer_generator/brochure/schema_renderer/loader.py` — `load_template()` pattern to copy
- `flyer_generator/brochure/schema_renderer/content_model.py::BrochureContent.resolve_key` — content_key resolution pattern
- `flyer_generator/api/tasks/brochure.py::task_generate_brochure` — late-binding template lookup
- `flyer_generator/api/schemas/brochures.py::BrochureCreateRequest` — `template: str` field shape
- `frontend/src/pages/brochures/new.tsx` — FE template input pattern

### Flyer pipeline (what gets refactored)
- `flyer_generator/models.py::EventInput` — base input model to evolve
- `flyer_generator/api/schemas/flyers.py::FlyerCreateRequest` — request schema to extend
- `flyer_generator/api/tasks/flyer.py::task_generate_flyer` — worker to plumb template through
- `flyer_generator/pipeline.py` — plug-in point at line ~111
- `flyer_generator/stages/composer.py::PosterComposer.compose` — function to template-drive
- `flyer_generator/stages/vision.py` — system prompt to branch on subtype
- `flyer_generator/api/models/flyer.py::FlyerRecord` — DB model gains `template` column
- `flyer_generator/api/models/render.py::RenderKind` — enum to extend

### Frontend
- `frontend/src/pages/flyers/new.tsx` — form to extend with template + subtype `<Select>`
- `frontend/src/pages/renders/gallery.tsx::KINDS` — filter list to extend
- `frontend/src/pages/jobs/list.tsx::KINDS` — filter list to extend
- `frontend/src/api/openapi.snapshot.json` + `frontend/src/api/schema.gen.ts` — regen after BE schema change

### Tests
- `tests/brochure/schema_renderer/` — test layout to mirror under `tests/flyer/schema_renderer/`
- `tests/api/test_flyer_routes.py` — extend (don't replace)
- `tests/api/test_worker_tasks.py` — extend `test_flyer_*` group
- `frontend/src/pages/flyers/new.test.tsx` — extend with template + subtype coverage

### Approved plan
- `/home/hoyack/.claude/plans/lets-expand-the-flyer-gentle-cat.md` — full v1.1 milestone plan; Phase 22 section is the source of truth for this work
</canonical_refs>

<specifics>
## Specific Ideas

- Each flyer template's JSON file declares (mirroring brochure):
  - `schema_version`, `name`, `tone_keywords`
  - `palette` (with brand-kit override hooks)
  - `typography` (heading family, body family, scale)
  - `panels: { hero: {...} }` — single-panel for flyer (vs. brochure's 6-panel)
  - Each panel element: `{type: "text"|"shape"|"image_placeholder", content_key, style, position}`

- Initial template variants:
  - **`editorial_classic`** — serif title, narrow scrim, subtle accent rule
  - **`bold_modern`** — sans-serif slab title, full-bleed scrim, thick accent stripe
  - **`minimal_photo`** — sans title bottom-left, no scrim, single accent dot
  - **`retro_poster`** — display title with stroke, halftone-style scrim, multiple accent shapes
  - **`zine`** — collage-feel typography, off-axis text, asymmetric scrim
  - **`tight_typographic`** — typography-first, minimal imagery emphasis, structured grid

- Info flyer use cases (vision prompt should hint these):
  - Community announcement (lost dog, public meeting, road closure)
  - Educational notice (course offering, safety reminder)
  - Promotional flyer without a specific event date (sale, service launch)

- Migration safety: when rewriting `flyer_final` rows, the migration MUST be idempotent — re-running it must not flip the subtype-derived kind. Use `WHERE kind = 'flyer_final'` in the UPDATE.
</specifics>

<deferred>
## Deferred Ideas

- **Template discovery API** — `GET /api/v1/flyers/templates` returning the registry — nice-to-have; FE hardcodes the list at launch (same approach as brochures)
- **LLM-driven template selection** — port `brochure.generative.layout.select_template_for_tone` once flyer template library is mature
- **A/B template comparison UI** — render the same EventInput through two templates side-by-side
- **Custom-template upload** — user-supplied JSON via API; out of scope for v1.1
- **Per-template preview thumbnails** — pre-rendered PNG samples shown in the FE template `<Select>`
</deferred>

---

*Phase: 22-flyer-templates-subtype-split*
*Context gathered: 2026-04-24 from approved plan + Phase 21 exploration*
