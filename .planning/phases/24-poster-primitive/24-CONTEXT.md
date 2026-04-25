# Phase 24: Poster Primitive — Context

**Gathered:** 2026-04-25
**Status:** Ready for planning
**Source:** User-approved plan + Phase 22 patterns

<domain>
## Phase Boundary

Posters are essentially **larger-canvas flyers** with explicit print-size presets. The pipeline is the existing flyer pipeline (Comfy + vision + composer + rasterizer) parameterized with a different canvas constant. Single PNG output, no PDF.

**In scope:**
- `PosterCreateRequest` Pydantic schema with `size: Literal["18x24", "24x36", "27x40"]` + `template` + flyer-like fields
- `PosterRecord` SQLAlchemy model with parallel-id pattern
- `JobKind.POSTER` + `RenderKind.poster_final` enum extensions + alembic migration
- 3+ poster JSON templates with typography pre-scaled for print canvas
- Worker `task_generate_poster` reuses `FlyerGenerator.generate()` with injected dimensions
- `FlyerGenerator.__init__` accepts injected canvas dimensions (refactor from hardcoded `(1080, 1920)`)
- `POST /api/v1/posters` route with compensating enqueue
- FE creator at `/posters/new` (size + template Selects), status via existing `JobStatusCard`, sidebar nav, Jobs + Renders filters

**Out of scope:**
- Multi-page posters (single canvas only)
- Brochure-style PDF assembly (poster ships as PNG only)
- Phase 25's invitation primitive
- Phase 26's adversarial sweep
</domain>

<decisions>
## Implementation Decisions (locked from plan)

### Pipeline reuse, not fork

**LOCKED:** `FlyerGenerator.__init__` accepts an optional `canvas_dimensions: tuple[int, int] | None = None` kwarg. When None, falls back to `(1080, 1920)` (existing flyer behavior). When provided, the entire pipeline (Comfy prompt sizing, ImagePreprocessor upscale target, Composer canvas, Rasterizer output dimensions) uses the injected size.

This is a non-breaking refactor — the flyer worker continues to call `FlyerGenerator()` with no args.

### Schema

**LOCKED:**
- `PosterCreateRequest`: `headline: str` (max 120), `subheading: str | None = None`, `cta_text: str | None = None`, `image_hint: str | None = None`, `brand_kit_slug: str | None = None`, `style_preset: str` (max 64), `template: str` (max 64), `size: Literal["18x24", "24x36", "27x40"]`
- Size to dimensions mapping (300 DPI):
  - `"18x24"` → 5400×7200 (18×24" portrait)
  - `"24x36"` → 7200×10800 (24×36" portrait)
  - `"27x40"` → 8100×12000 (27×40" portrait, theatrical one-sheet)

### Templates

**LOCKED:** 3 poster JSON templates ship at launch:
- `editorial_grand` — serif title scaled for 18×24" reading distance
- `bold_announcement` — sans display title, full-bleed scrim
- `cinematic_onesheet` — heavy bottom block + accent stripes (designed for 27×40")

All templates declare typography in **points at 300 DPI**, not pixels — the composer scales appropriately.

### Worker + routes

**LOCKED:**
- `task_generate_poster` in `flyer_generator/api/tasks/poster.py` — module-scope `load_template` import (BLOCKER-2 mirror) + `_validate_template_slug` guard + `FlyerGenerator(canvas_dimensions=size_to_dim(size))`
- `POST /api/v1/posters` route in `flyer_generator/api/routes/posters.py` with compensating-enqueue pattern (typed error_detail, NEVER `str(exc)`)
- No `GET /api/v1/posters/{id}` detail route — single artifact, status page reads result_ref directly via existing `JobStatusCard`
- `RenderRecord.kind = "poster_final"` (single artifact) — no front/back/pdf split
- `PosterRecord` parallel-id (id == job_id) for consistency with other primitives

### Frontend

**LOCKED:**
- `frontend/src/pages/posters/new.tsx` — editorial PageHeader (kicker `"09 / THE BIG ONE"`), size + template + brand-kit Selects + headline/subheading/CTA fields
- `frontend/src/pages/posters/status.tsx` — thin wrapper around `JobStatusCard` (mirrors flyer status page)
- `routes.tsx`: `/posters/new` + `/posters/:id`
- `DashboardLayout.NAV` adds `{ to: "/posters/new", label: "New poster" }`
- `jobs/list.tsx::KINDS` + `statusPathFor` add `poster`
- `renders/gallery.tsx::KINDS` adds `poster_final`

### Claude's Discretion

- Whether posters need their own `RenderKind` namespace or share with flyer
- Specific template JSON shape — single panel like flyer
- CTA placement (whether to render only when present, etc.)
</decisions>

<canonical_refs>
## Canonical References

### Phase 22 (closest analog — flyer pipeline)
- `flyer_generator/pipeline.py::FlyerGenerator` (refactor target)
- `flyer_generator/flyer/schema_renderer/{schema_model,loader}.py` (template registry pattern)
- `flyer_generator/api/tasks/flyer.py` (BLOCKER-2 + path-traversal guard)
- `flyer_generator/api/schemas/flyers.py::FlyerCreateRequest` (request shape)
- `flyer_generator/stages/composer.py` (template-aware composer; needs to handle larger canvas)
- `frontend/src/pages/flyers/{new,status}.tsx` (FE pattern)

### Phase 23 (just shipped — new asset shell)
- `flyer_generator/api/models/postcard.py::PostcardRecord` (parallel-id ORM pattern)
- `flyer_generator/api/routes/postcards.py::create_postcard` (compensating-enqueue pattern)
- `flyer_generator/api/tasks/postcard.py` (worker pattern)
- `alembic/versions/f23t01_*.py` (migration shape)

### Approved plan
- `/home/hoyack/.claude/plans/lets-expand-the-flyer-gentle-cat.md` — Phase 24 section
</canonical_refs>

<specifics>
## Specific Ideas

- 3 size presets is enough for v1; extending to ANSI/ISO sizes later is a future ask
- Typography units in **points** (declared in JSON template) — composer converts to pixels via dpi=300 scale factor
- Default subheading and CTA: render only when present (no placeholder ghost text)
- For brand-kit conditioning: same flow as flyer (palette + typography overrides on template)

## Permutation tests
- 3 templates × 3 sizes = 9 permutations
- Render-smoke validates output PNG dimensions match size preset
- HTTP route permutations
- Playwright harness `/tmp/check-e2e-poster-24.mjs`

</specifics>

<deferred>
## Deferred Ideas
- ANSI / ISO size presets (A1, A2, B1, etc.)
- Landscape orientations (current is portrait-only)
- Multi-page posters (e.g., infographic series)
- LLM-driven template selection
- Poster mockup preview (rendered onto a wall scene)
</deferred>

---

*Phase: 24-poster-primitive*
*Context gathered: 2026-04-25 from approved plan*
