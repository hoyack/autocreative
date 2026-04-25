# Phase 23: Postcard Primitive — Context

**Gathered:** 2026-04-25
**Status:** Ready for planning
**Source:** User-approved plan at `/home/hoyack/.claude/plans/lets-expand-the-flyer-gentle-cat.md` + Phase 21–22 patterns

<domain>
## Phase Boundary

This phase introduces the **postcard** creative primitive — a 2-sided direct-mail format that produces a front PNG, back PNG, and print-ready PDF. The front is imagery-heavy (Comfy-generated background + headline); the back is typographic (body copy + optional address block + stamp placeholder).

**In scope:**
- Pydantic request schema `PostcardCreateRequest` mirroring brochure shape
- `PostcardRecord` SQLAlchemy model with parallel-id pattern (`id == job_id`)
- Alembic migration adding the `postcards` table + 3 new RenderKind values
- 2+ JSON templates (`classic_portrait`, `modern_landscape`)
- Renderer at `flyer_generator/postcard/schema_renderer/` mirroring brochure
- Worker `task_generate_postcard` reusing `Rasterizer` + brochure-style PDF assembly
- Routes: `POST /api/v1/postcards`, `GET /api/v1/postcards/{id}` (returns `PostcardDetail` with 3 URLs)
- Worker registration + JobKind enum extension
- FE: creator page `/postcards/new`, status page `/postcards/:id` (3-artifact figure grid), sidebar nav entry, Jobs + Renders filter entries

**Out of scope:**
- Postcard template discovery API
- Live carrier-route/postage integration
- Phase 22's flyer template registry (already shipped)
- Phase 24's poster primitive
- Phase 26's adversarial sweep
</domain>

<decisions>
## Implementation Decisions (locked from plan)

### Schema + model

**LOCKED:**
- `flyer_generator/api/schemas/postcards.py::PostcardCreateRequest` with fields: `headline: str`, `body: str`, `image_hint: str | None`, `brand_kit_slug: str | None`, `template: str` (required, min 1 / max 64), optional `address_block: AddressBlock | None`
- `AddressBlock` schema: `recipient_name: str`, `street: str`, `city_state_zip: str` (single line), all max 120
- `PostcardRecord(id, job_id, template, front_png_path, back_png_path, pdf_path, created_at)` — `id == job_id` (parallel-id pattern from 21-07)
- New table `postcards` via alembic migration

### Rendering

**LOCKED:**
- New package `flyer_generator/postcard/schema_renderer/` mirrors `flyer_generator/brochure/schema_renderer/` and `flyer_generator/flyer/schema_renderer/` (just shipped in Phase 22)
- `PostcardTemplateSchema` Pydantic model — clone Phase 22's `FlyerTemplateSchema` shape but with TWO panels: `front` and `back`
- 2 templates ship at launch:
  - **`classic_portrait`** — 4×6 portrait (1200×1800 @ 300 DPI), serif title + clean back layout
  - **`modern_landscape`** — 6×4 landscape (1800×1200 @ 300 DPI), bold sans title + asymmetric back layout
- Renderer produces two SVGs (front, back) → rasterizes each to PNG → assembles into 2-page PDF
- Reuse `flyer_generator/brochure/stages/pdf.py::assemble_brochure_pdf` if its signature is generic enough; otherwise create `flyer_generator/postcard/stages/pdf.py::assemble_postcard_pdf`

### Worker

**LOCKED:**
- `flyer_generator/api/tasks/postcard.py::task_generate_postcard`
- Module-scope `from flyer_generator.postcard.schema_renderer import load_template` (BLOCKER-2 mirror)
- Path-traversal guard `_validate_template_slug` mirrors Phase 22 worker
- Compensating-enqueue pattern from Phase 21-12: try/except around `enqueue_job` with `error_detail = {"reason": "enqueue_failed", "type": ...}` (NOT `str(exc)`)
- 3 `RenderRecord` rows: `postcard_front`, `postcard_back`, `postcard_pdf`
- 1 `PostcardRecord` with id == job_id

### Routes

**LOCKED:**
- `flyer_generator/api/routes/postcards.py` with `POST /api/v1/postcards` (returns `JobEnqueueResponse`) and `GET /api/v1/postcards/{postcard_id}` (returns `PostcardDetail` with 3 artifact URLs)
- Mirror `flyer_generator/api/routes/brochures.py::get_brochure_detail` for the detail route

### Frontend

**LOCKED:**
- `frontend/src/pages/postcards/new.tsx` — mirror `frontend/src/pages/brochures/new.tsx`; editorial PageHeader (kicker `"08 / THE MAIL"`, title `"New postcard"`)
- `frontend/src/pages/postcards/status.tsx` — mirror brochure status (3-artifact figure grid)
- `frontend/src/routes.tsx` — add `/postcards/new` + `/postcards/:id`
- `frontend/src/components/DashboardLayout.tsx::NAV` — add `{ to: "/postcards/new", label: "New postcard" }`
- `frontend/src/pages/jobs/list.tsx::KINDS` + `statusPathFor` — add `postcard`
- `frontend/src/pages/renders/gallery.tsx::KINDS` — add 3 new render kinds

### Claude's Discretion

- Exact JSON shape of each postcard template panel (front vs. back element layout)
- Whether to share the brochure PDF assembler or fork
- Page ordering in the printed PDF (front first vs. back first)
- Address-block typography details
</decisions>

<canonical_refs>
## Canonical References

### Brochure pattern (closest analog)
- `flyer_generator/brochure/schema_renderer/{schema_model,loader,renderer}.py`
- `flyer_generator/brochure/stages/pdf.py::assemble_brochure_pdf`
- `flyer_generator/api/schemas/brochures.py::BrochureCreateRequest, BrochureDetail`
- `flyer_generator/api/models/brochure.py::BrochureRecord`
- `flyer_generator/api/routes/brochures.py::create_brochure, get_brochure_detail`
- `flyer_generator/api/tasks/brochure.py::task_generate_brochure` (parallel-id + path-traversal guard pattern)

### Phase 22 (just shipped — fresh patterns)
- `flyer_generator/flyer/schema_renderer/{schema_model,loader}.py`
- `flyer_generator/flyer/schemas/*.json`
- `flyer_generator/api/tasks/flyer.py::task_generate_flyer` (BLOCKER-2 module-scope import + `_validate_template_slug`)
- `alembic/versions/f22t01_*.py` (idempotent + reversible migration shape)

### Frontend
- `frontend/src/pages/brochures/{new,status}.tsx` — closest analog for FE form + 3-artifact status
- `frontend/src/components/PageHeader.tsx`, `DashboardLayout.tsx::NAV`, `routes.tsx`

### Compensating-enqueue + parallel-id
- `flyer_generator/api/routes/brochures.py::create_brochure` — post-21-12 fix has the try/except shape
- `flyer_generator/api/tasks/brochure.py` — parallel-id (job_id == brochure_id) is the pattern

### Approved plan
- `/home/hoyack/.claude/plans/lets-expand-the-flyer-gentle-cat.md` — Phase 23 section
</canonical_refs>

<specifics>
## Specific Ideas

- Postcard panels naming: `front` and `back` (vs. brochure's 6-panel layout)
- Front panel: image_placeholder + headline + (optional) tagline; small "stamp area" box on landscape variant
- Back panel: body text block + (optional) address block + return address area + (optional) call-to-action footer
- Default canvas: 1200×1800 portrait or 1800×1200 landscape at 300 DPI (4×6" / 6×4" — USPS standard)
- Front PDF page is page 1; back is page 2

## Permutation tests
- 2 templates × 2 subtypes (with-address-block vs. without) = 4 permutations to render
- HTTP route permutation tests submit each
- Playwright harness `/tmp/check-e2e-postcard-23.mjs`

## Editorial nav kicker
- `"08 / THE MAIL"` — fits the editorial design system established in Phase 21

</specifics>

<deferred>
## Deferred Ideas
- Postcard template discovery API
- USPS Intelligent Mail barcode + addressing service integration
- LLM-driven template selection by tone (when postcard library grows)
- Custom postcard size presets beyond 4×6 / 6×4
- Postage payment / mailing service integration
</deferred>

---

*Phase: 23-postcard-primitive*
*Context gathered: 2026-04-25 from approved plan*
