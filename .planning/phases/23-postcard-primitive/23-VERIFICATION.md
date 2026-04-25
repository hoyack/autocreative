---
phase: 23-postcard-primitive
verified: 2026-04-23T22:05:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
requirements_covered: [PC-01, PC-02, PC-03, PC-04, PC-05, PC-06]
human_verification:
  - test: "Run Playwright e2e harness /tmp/check-e2e-postcard-23.mjs against full FE+BE+arq stack"
    expected: "All 4 permutations (2 templates × with/without address) complete: JobRecord status=SUCCEEDED, 3 artifacts render in figure grid, exit code 0 with 'All 4 permutations passed'"
    why_human: "Requires live docker compose (Postgres+Redis) + uvicorn + arq worker + Vite dev server running concurrently; Plan 23-06 Task 2 is explicitly tagged checkpoint:human-verify gate='blocking'"
  - test: "Visual spot-check /postcards/new renders editorial PageHeader"
    expected: "Sidebar highlights 'New postcard'; header displays '08 / The Mail / New postcard'; form shows headline + body + template + optional address-block toggle"
    why_human: "Visual composition of multi-span PageHeader + sidebar highlighting cannot be verified programmatically"
  - test: "Visual spot-check /postcards/:id renders 3-artifact figure grid"
    expected: "After a succeeded postcard job, the status page shows 3 figures: Front PNG (inline preview), Back PNG (inline preview with visible address block when supplied), Print PDF (download link via RenderPreview isPdf)"
    why_human: "Requires a succeeded job + visual inspection of rendered PNGs including address block typography"
  - test: "Jobs gallery filter by postcard kind shows postcard jobs; Renders gallery filter by postcard_front/back/pdf shows matching artifacts"
    expected: "http://localhost:5173/jobs?kind=postcard lists 4 succeeded postcard jobs after e2e run; /renders with Kind=postcard_front shows 4 thumbnails (same for back + pdf)"
    why_human: "Live dashboard filter behavior against post-e2e DB state"
---

# Phase 23: Postcard Primitive — Verification Report

**Phase Goal:** A user can `POST /api/v1/postcards` and receive a job that produces a front PNG + back PNG + print-ready PDF, then view all three artifacts (plus a recipient address block rendered on the back panel) through the editorial React dashboard.

**Verified:** 2026-04-23T22:05:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `POST /api/v1/postcards` enqueues a job with parallel-id (`id == job_id`) + compensating-enqueue (`error_detail = {"reason": "enqueue_failed", "type": ...}`, never `str(exc)`); `GET /api/v1/postcards/{id}` returns `PostcardDetail` with 3 artifact URLs | VERIFIED | routes/postcards.py:72-90 (compensating-enqueue with `type(exc).__name__` only; `grep str(exc)` returns 0 in both route + worker files); tasks/postcard.py:204-215 (parallel-id `PostcardRecord(id=job_id, ...)`); routes/postcards.py:118-137 (PostcardDetail returns 3 URLs — front/back/pdf). 13/13 route tests pass; 18/18 worker tests pass |
| 2 | Optional `address_block` (recipient name, street, city/state/zip) renders typographically on the back panel | VERIFIED | schemas/postcards.py:34-40 (AddressBlock with 3 fields, 1-120 chars each); schema_renderer/content_model.py resolve_key handles address_block.* prefix; both JSON templates reference all 3 address content_keys (`grep -l "address_block.recipient_name" flyer_generator/postcard/schemas/*.json` returns both); pipeline smoke confirms "Jane Doe / 123 Main St / Springfield, IL 62701" appear in back_svg |
| 3 | ≥2 postcard templates ship (`classic_portrait`, `modern_landscape`); renderer reuses brochure SVG + rasterizer stack; back-PDF path mirrors `assemble_brochure_pdf` | VERIFIED | 2 JSON templates exist (classic_portrait 1200×1800, modern_landscape 1800×1200); renderer.py imports from `flyer_generator.brochure.schema_renderer.shapes` (render_fill/render_shape/_fill_opacity) + `.text_fit` (wrap_text/fit_to_bbox/chars_per_line); postcard/stages/pdf.py mirrors brochure PDF pattern with caller-supplied page dims + no crop marks; 2-page PDF round-trip verified via pypdf (both templates; mediabox dims match canvas) |
| 4 | `/postcards/new` + `/postcards/:id` exist; editorial PageHeader kicker "08 / THE MAIL"; sidebar nav entry; 3-artifact figure grid mirroring brochure | VERIFIED | routes.tsx:48-49 registers both paths; DashboardLayout.tsx:7 has `{ to: "/postcards/new", label: "New postcard" }`; pages/postcards/new.tsx:146-147 uses `number="08" kicker="The Mail"`; pages/postcards/status.tsx:87-116 renders `<figure>` × 3 with `front_render_url`, `back_render_url`, `pdf_render_url` (last with `isPdf`); 5/5 vitest tests pass |
| 5 | Jobs filter + `statusPathFor` + Renders gallery filter include `postcard` JobKind and 3 RenderKinds | VERIFIED | jobs/list.tsx:38 KINDS includes `"postcard"`; lines 56-57 `case "postcard": return /postcards/${id};`; renders/gallery.tsx:40-42 KINDS includes `"postcard_front"`, `"postcard_back"`, `"postcard_pdf"`; backend JobKind.POSTCARD = "postcard" (models/job.py:18); worker writes 3 RenderRecord kinds (tasks/postcard.py:191-199) |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `flyer_generator/postcard/schema_renderer/schema_model.py` | PostcardTemplateSchema with front+back panel validator | VERIFIED | 12KB; defines PostcardTemplateSchema, _PanelName=Literal["front","back"], @field_validator rejects missing panels |
| `flyer_generator/postcard/schema_renderer/loader.py` | load_template + list_templates | VERIFIED | 1.2KB; load_template + list_templates exported via barrel |
| `flyer_generator/postcard/schemas/classic_portrait.json` | 4×6 portrait 1200×1800 | VERIFIED | Canvas 1200×1800; has front+back panels; references headline + body + 3 address_block content_keys |
| `flyer_generator/postcard/schemas/modern_landscape.json` | 6×4 landscape 1800×1200 | VERIFIED | Canvas 1800×1200; has front+back panels; references headline + body + 3 address_block content_keys |
| `flyer_generator/postcard/schema_renderer/content_model.py` | PostcardContent + resolve_key | VERIFIED | 4.7KB; resolve_key handles headline/body/image_hint/address_block.* |
| `flyer_generator/postcard/schema_renderer/renderer.py` | render_postcard with XML-escape | VERIFIED | 19KB; imports brochure shapes + text_fit; xml_escape on all user-supplied strings (7+ sites per 23-03 summary) |
| `flyer_generator/postcard/stages/pdf.py` | assemble_postcard_pdf + PostcardPDFError | VERIFIED | 3.7KB; PostcardPDFError extends RasterizationError; 2-page PDF with caller-supplied page dims; no crop marks |
| `flyer_generator/api/schemas/postcards.py` | PostcardCreateRequest, AddressBlock, PostcardDetail | VERIFIED | All 3 classes exist; extra="forbid" on each BaseModel; AddressBlock fields 1-120 chars; 16/16 schema tests pass |
| `flyer_generator/api/models/postcard.py` | PostcardRecord with no default on id | VERIFIED | `id: Mapped[str] = mapped_column(String(26), primary_key=True)` — NO default=new_ulid; 7/7 DDL tests pass (including regression test for no default factory) |
| `alembic/versions/f23t01_postcard_primitive.py` | Creates postcards table + extends JobKind | VERIFIED | down_revision="f22t01"; creates postcards table + 4 indexes; Postgres `ALTER TYPE jobkind ADD VALUE IF NOT EXISTS 'POSTCARD'` inside autocommit_block; `alembic heads` reports `f23t01 (head)`; 6/6 migration tests pass |
| `flyer_generator/api/tasks/postcard.py` | Worker with path-traversal guard + parallel-id + 3 RenderRecords | VERIFIED | Module-scope imports (load_template, render_postcard, Rasterizer, assemble_postcard_pdf); `_validate_template_slug` rejects `.json`/`/`/`\\` with 'bare slug' msg; writes 3 RenderRecord kinds (postcard_front/back/pdf); PostcardRecord(id=job_id, ...); registered in ALL_TASKS; 18/18 worker tests pass |
| `flyer_generator/api/routes/postcards.py` | POST (compensating-enqueue) + GET (3 URLs) | VERIFIED | POST creates JobRecord with JobKind.POSTCARD, enqueues task_generate_postcard, try/except flips to FAILED with `{"reason": "enqueue_failed", "type": type(exc).__name__}`; `grep str(exc)` returns 0; GET 26-char PathParam, returns PostcardDetail with 3 URLs; router in ROUTERS; 13/13 route tests pass |
| `frontend/src/pages/postcards/new.tsx` | NewPostcardPage with form + kicker "08 / The Mail" | VERIFIED | 290 lines; `number="08"` + `kicker="The Mail"`; client.POST("/api/v1/postcards"); zod .strict() + address-block refine; on success invalidates jobs query + navigates to /postcards/{job_id}; 5/5 vitest tests pass |
| `frontend/src/pages/postcards/status.tsx` | PostcardStatusPage with 3-artifact grid | VERIFIED | Uses queryKeys.postcard(id); calls client.GET("/api/v1/postcards/{postcard_id}"); renders 3 `<figure>` elements with front/back PNG + PDF (isPdf); gated on job.status === 'succeeded' |
| `frontend/src/components/DashboardLayout.tsx` | NAV entry "New postcard" | VERIFIED | Line 7: `{ to: "/postcards/new", label: "New postcard" }` |
| `frontend/src/pages/jobs/list.tsx` | KINDS includes postcard + statusPathFor | VERIFIED | Line 38: KINDS has "postcard"; lines 56-57: `case "postcard": return /postcards/${id};` |
| `frontend/src/pages/renders/gallery.tsx` | KINDS includes 3 postcard render kinds | VERIFIED | Lines 40-42: `"postcard_front"`, `"postcard_back"`, `"postcard_pdf"` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| routes/postcards.py | task_generate_postcard (arq) | `arq_pool.enqueue_job("task_generate_postcard", ...)` | WIRED | Line 73-77 |
| tasks/postcard.py | PostcardRecord | `PostcardRecord(id=job_id, ...)` | WIRED | Line 204-212; parallel-id |
| tasks/__init__.py | tasks/postcard.py | `from ... import task_generate_postcard; ALL_TASKS.append(...)` | WIRED | import + ALL_TASKS entry + __all__ (3 refs) |
| routes/__init__.py | routes/postcards.py | `ROUTERS.append(postcards.router)` | WIRED | import + ROUTERS + __all__ (3 refs) |
| frontend/pages/postcards/new.tsx | POST /api/v1/postcards | openapi-fetch typed `client.POST` | WIRED | Line 119-123 |
| frontend/pages/postcards/status.tsx | GET /api/v1/postcards/{postcard_id} | openapi-fetch typed `client.GET` | WIRED | Line 24-27 |
| frontend/api/schema.gen.ts | OpenAPI postcard routes | Generated from snapshot | WIRED | 4 grep hits for `/api/v1/postcards` |
| routes/postcards.py (GET) | session.get(PostcardRecord, postcard_id) | SQLAlchemy async session | WIRED | Line 115 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| PostcardStatusPage | `detail` | GET /api/v1/postcards/{id} → session.get(PostcardRecord) | Yes — record + 3 FK URLs fused | FLOWING |
| routes/postcards.py GET | `record` | `session.get(PostcardRecord, postcard_id)` | Yes — real DB lookup | FLOWING |
| task_generate_postcard | `front_svg`, `back_svg` | render_postcard(template, content) | Yes — renderer produces non-empty SVG with interpolated user content | FLOWING |
| task_generate_postcard | `pdf_bytes` | assemble_postcard_pdf(...) | Yes — 2-page PDF starting with `%PDF-` | FLOWING |
| NewPostcardPage | form values | RHF useForm() → zod validation → mutationFn body | Yes — form data flows to POST | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All postcard + API pytests pass | `.venv/bin/pytest tests/postcard/ tests/api/test_postcard_*.py -q` | 138 passed, 1 warning in 7.46s | PASS |
| Module imports + parallel-id guard | `python -c "from flyer_generator.api.models import PostcardRecord; assert PostcardRecord.__table__.columns['id'].default is None"` | OK all registrations + parallel-id guard | PASS |
| End-to-end pipeline smoke (template → SVG → PNG → PDF) | `python -c "load_template + render_postcard + Rasterizer + assemble_postcard_pdf with address_block"` | OK pipeline smoke: 3-artifact generation + address block flows | PASS |
| Path-traversal guard rejects hostile inputs | `_validate_template_slug('foo.json' / '../etc/passwd' / 'dir/tpl' / 'dir\\tpl')` | All 4 raise ValueError with 'bare slug' | PASS |
| alembic heads | `.venv/bin/alembic heads` | `f23t01 (head)` | PASS |
| Frontend vitest for postcard pages | `cd frontend && pnpm test --run src/pages/postcards/` | Test Files 1 passed (1); Tests 5 passed (5) | PASS |
| OpenAPI snapshot contains postcard routes | `grep -c "/api/v1/postcards" frontend/src/api/schema.gen.ts` | 4 | PASS |
| `str(exc)` leak guard on compensating-enqueue | `grep -c "str(exc)" flyer_generator/api/routes/postcards.py flyer_generator/api/tasks/postcard.py` | 0 / 0 | PASS |
| JobKind.POSTCARD enum value | `python -c "from flyer_generator.api.models import JobKind; assert JobKind.POSTCARD.value == 'postcard'"` | OK | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| PC-01 | 23-02, 23-04, 23-06 | POST/GET routes + 3-artifact flow | SATISFIED | routes/postcards.py (POST + GET); schemas/postcards.py (PostcardCreateRequest + PostcardDetail); HTTP permutation pytest covers 4 cases (2 templates × 2 addr-flags); 13/13 route tests pass |
| PC-02 | 23-02, 23-04 | Parallel-id (`id == job_id`) + compensating-enqueue typed error_detail | SATISFIED | PostcardRecord.id has NO default factory (DDL regression test); worker sets `PostcardRecord(id=job_id, ...)`; routes/postcards.py line 85-88 uses `{"reason": "enqueue_failed", "type": type(exc).__name__}`; `grep str(exc)` returns 0 |
| PC-03 | 23-02, 23-03, 23-04 | Optional AddressBlock rendered typographically on back panel | SATISFIED | AddressBlock schema with 3 fields (1-120 chars); both JSON templates declare all 3 address content_keys; PostcardContent.resolve_key returns "" when address_block is None; render_smoke test asserts "Jane Doe"/"123 Main St"/"Springfield, IL 62701" appear in back_svg |
| PC-04 | 23-01, 23-03, 23-04 | ≥2 templates + renderer reuses brochure SVG/rasterizer + back-PDF mirrors `assemble_brochure_pdf` | SATISFIED | classic_portrait + modern_landscape JSONs; renderer.py imports brochure shapes + text_fit cross-package; postcard/stages/pdf.py follows same Canvas + drawImage + showPage pattern |
| PC-05 | 23-05 | /postcards/new + /postcards/:id + editorial PageHeader + sidebar entry + 3-artifact grid | SATISFIED | new.tsx uses `number="08" kicker="The Mail"`; status.tsx renders 3 `<figure>` elements; DashboardLayout adds "New postcard"; 5/5 vitest tests pass |
| PC-06 | 23-02, 23-04, 23-05 | Jobs filter + statusPathFor + Renders gallery + JobKind.POSTCARD + 3 RenderKinds | SATISFIED | JobKind.POSTCARD="postcard"; worker writes 3 RenderRecord kinds; jobs/list.tsx KINDS + statusPathFor include postcard; renders/gallery.tsx KINDS adds 3 postcard_* entries |

### Anti-Patterns Found

No blockers found. Notable items:

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No TODO/FIXME/placeholder strings in new files (verified via broad grep on phase files) | Info | Clean |
| — | — | No `str(exc)` in routes/postcards.py or tasks/postcard.py | Info | Compensating-enqueue leak guard enforced |
| — | — | No hardcoded-empty props at status page call site (`detail?.front_render_url` conditionals gate each figure on real data) | Info | Clean |
| flyer_generator/postcard/__init__.py | — | Empty file (0 bytes) | Info | Intentional package marker |
| flyer_generator/postcard/stages/__init__.py | — | Empty file (0 bytes) | Info | Intentional package marker |

Note: image_placeholder + logo_placeholder in postcard renderer always render fallback fill (documented in 23-03 SUMMARY as intentional — Comfy hero generation is deferred). This is a documented architectural decision, not an unfinished stub.

### Human Verification Required

Plan 23-06 Task 2 is explicitly tagged `checkpoint:human-verify gate="blocking"`. The 23-06 SUMMARY auto-approved this under auto-mode protocol but explicitly deferred the live-stack runtime verification to the user.

#### 1. Run Playwright e2e harness (/tmp/check-e2e-postcard-23.mjs)

**Test:** Bring up docker compose (Postgres+Redis) + `uv run alembic upgrade head` + `uv run uvicorn flyer_generator.api:app --reload` + `uv run arq flyer_generator.api.worker.WorkerSettings` + `cd frontend && pnpm dev`, then `node /tmp/check-e2e-postcard-23.mjs`.

**Expected:** All 4 permutations (classic_portrait+modern_landscape × with/without address) complete with exit code 0 and stdout `"All 4 permutations passed"`; per-permutation: JobRecord.status=SUCCEEDED, `/postcards/:id` renders ≥3 `<figure>` elements.

**Why human:** Harness requires 5 concurrent local services; no CI runner currently has this stack; `/tmp` files live outside repo; plan tagged `gate="blocking"`.

#### 2. Visual spot-check /postcards/new

**Test:** Navigate to `http://localhost:5173/postcards/new` after starting FE dev server.

**Expected:** Sidebar nav highlights "New postcard" entry; editorial PageHeader displays the "08 / THE MAIL / New postcard" composition (3 separate spans rendered together); form shows headline Input, body Textarea, template Input defaulting to "classic_portrait", optional image_hint + brand_kit_slug, and an address-block Switch revealing 3 sub-fields when toggled.

**Why human:** Multi-span PageHeader composition + sidebar highlight + form visual polish require visual inspection.

#### 3. Visual spot-check /postcards/:id 3-artifact grid

**Test:** After running the Playwright harness (or submitting a postcard via the form), visit `/postcards/:id` for a succeeded job.

**Expected:** Three `<figure>` elements render side-by-side: Front · PNG (inline preview), Back · PNG (inline preview — back panel visibly shows address block typography when supplied), Print · PDF (download link via RenderPreview `isPdf`).

**Why human:** Visual verification of printed-PDF preview, address-block typography quality, and composite grid layout.

#### 4. Jobs + Renders filter behavior against live DB

**Test:** After e2e harness run, visit `http://localhost:5173/jobs?kind=postcard` and `/renders` with Kind filter set to `postcard_front` / `postcard_back` / `postcard_pdf`.

**Expected:** Jobs view shows 4 succeeded postcard jobs; each Renders kind filter shows 4 thumbnails; clicking a job routes to `/postcards/{id}` via `statusPathFor`.

**Why human:** Live DB-backed filter behavior requires a post-e2e run state.

### Deferred Items

None — all phase 23 goals are in-scope for phase 23. No phase 23 truths are addressed by later phases (24, 25, 26 deal with different primitives).

### Gaps Summary

No gaps found at the automated verification layer. All 5 ROADMAP Success Criteria are satisfied by live code (not SUMMARY claims): 138 backend pytests pass (covering schemas, ORM, migration, worker, routes, render-smoke, HTTP permutations, PDF assembly), 5 frontend vitests pass, alembic head is f23t01, end-to-end pipeline smoke produces a 3-artifact output with address block flowing through to the back SVG, path-traversal guard rejects all 3 hostile patterns, compensating-enqueue has zero `str(exc)` occurrences, parallel-id is enforced by a DDL-level regression test, and all frontend wiring (sidebar, routes, filter arrays, queryKeys, typed OpenAPI client) is in place.

**Status is `human_needed` because Plan 23-06 Task 2 is an explicit `checkpoint:human-verify gate="blocking"` for the Playwright e2e harness against a live FE+BE+arq stack.** The 23-06 SUMMARY auto-approved this under auto-mode but deferred runtime verification to the user — this verification report surfaces that deferral as the primary human gate.

---

*Verified: 2026-04-23T22:05:00Z*
*Verifier: Claude (gsd-verifier)*
