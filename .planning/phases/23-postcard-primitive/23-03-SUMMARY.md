---
phase: 23-postcard-primitive
plan: 03
subsystem: postcard-renderer + pdf-assembly
tags: [pydantic-v2, svg-renderer, reportlab, pdf-assembly, xml-escape, tdd, pc-03, pc-04]

# Dependency graph
requires:
  - phase: 23-postcard-primitive
    plan: 01
    provides: PostcardTemplateSchema, load_template, list_templates, classic_portrait + modern_landscape JSON templates
  - phase: 05-brochure-subsystem
    provides: render_shape / render_fill / _fill_opacity (shape primitives), chars_per_line / fit_to_bbox / wrap_text (text-fit helpers), RasterizationError (parent class for PostcardPDFError)
provides:
  - flyer_generator.postcard.schema_renderer.PostcardContent (runtime payload model)
  - flyer_generator.postcard.schema_renderer.PostcardAddressBlock (address-block model)
  - flyer_generator.postcard.schema_renderer.render_postcard (template + content -> (front_svg, back_svg))
  - flyer_generator.postcard.stages.pdf.assemble_postcard_pdf (2-page PDF, no crop marks)
  - flyer_generator.postcard.stages.pdf.PostcardPDFError (RasterizationError subclass)
affects:
  - 23-04 (worker task_generate_postcard) — can now `from flyer_generator.postcard.schema_renderer import render_postcard, PostcardContent, PostcardAddressBlock` and `from flyer_generator.postcard.stages.pdf import assemble_postcard_pdf, PostcardPDFError`. Worker translates PostcardCreateRequest -> PostcardContent, calls render_postcard, rasterizes each panel via Rasterizer(width=canvas.w, height=canvas.h), then calls assemble_postcard_pdf to produce the third artifact.
  - 26 (adversarial sweep) — XML-escape on every interpolated user string is the load-bearing T-23-09 mitigation. Phase 26 will add zalgo / oversize / control-char coverage on top of the basic injection-guard tests in this plan.

# Tech tracking
tech-stack:
  added: []  # Re-uses pydantic 2.x, reportlab, Pillow, pypdf already in stack
  patterns:
    - "Postcard renderer per-panel single-canvas topology: each panel IS the entire canvas (no <g translate>, no bleed math, no fold lines), unlike brochure which wraps each of 6 panels in a panel-local transform."
    - "PostcardContent.resolve_key flat namespace: 'headline', 'body', 'image_hint', 'address_block.{recipient_name,street,city_state_zip}'. address_block prefix returns '' (not None) when address_block is None so address TextElements render empty rather than skip."
    - "Cross-package utility imports (allowed): flyer_generator.brochure.schema_renderer.shapes (render_fill/render_shape/_fill_opacity) + .text_fit (chars_per_line/fit_to_bbox/wrap_text). These are pure utilities free of brochure-specific layout. Element helpers (text/bullets/divider/image_placeholder/logo_placeholder) copied into the postcard renderer because their Typography access pattern is type-narrowed to PostcardTemplateSchema."
    - "PostcardPDFError extends RasterizationError so existing `except RasterizationError` sites continue to work; worker plan 23-04 will surface the typed name to JobRecord.error_detail per T-23-11."
    - "Postcard PDF assembler diverges from assemble_brochure_pdf: caller-supplied page_width/page_height (no fixed bleed canvas), no crop marks (postcards print at exact USPS 4x6 / 6x4 dimensions with no bleed), and no _draw_crop_marks helper."
    - "All interpolated user strings (headline / body / address fields / static text in tspan or text content) pass through xml.sax.saxutils.escape; T-23-09 mitigation enforced by 4 dedicated injection-guard tests (script tag, img onerror, bold tag in address, plus the headline/body baseline cases)."

key-files:
  created:
    - flyer_generator/postcard/schema_renderer/content_model.py  (108 lines — PostcardContent + PostcardAddressBlock + resolve_key)
    - flyer_generator/postcard/schema_renderer/renderer.py  (498 lines — render_postcard + per-panel canvas walker + 5 element helpers)
    - flyer_generator/postcard/stages/__init__.py  (empty package marker)
    - flyer_generator/postcard/stages/pdf.py  (108 lines — assemble_postcard_pdf + PostcardPDFError)
    - tests/postcard/schema_renderer/test_renderer.py  (291 lines — 18 tests)
    - tests/postcard/stages/__init__.py  (empty package marker)
    - tests/postcard/stages/test_pdf.py  (209 lines — 13 tests)
  modified:
    - flyer_generator/postcard/schema_renderer/__init__.py  (added 3 new exports: PostcardContent, PostcardAddressBlock, render_postcard)

key-decisions:
  - "Cross-package import of brochure utilities (shapes + text_fit) is acceptable per CONTEXT.md and the established pattern in Phase 22 (flyer schema_renderer imports validate_hex_color). The element-level helpers (_render_text_element, _render_bullets_element, etc.) are copied into the postcard package rather than imported because their Typography field access is type-narrowed to PostcardTemplateSchema; sharing them would force the brochure renderer's helpers to accept a Union of TemplateSchema | PostcardTemplateSchema | FlyerTemplateSchema, expanding the cross-package surface beyond what's worth saving in code volume."
  - "PostcardContent.resolve_key returns '' (not None) when an address_block.* key is requested and address_block is None. This keeps the renderer's `if not text: return ''` early-out at the element level firing on empty content, but it preserves the option for future renderer changes to treat the empty-address path differently from the unknown-key path. Plan must_have explicitly required '(no exception, no NULL string in SVG)'."
  - "No crop marks on postcards. Postcards are printed at exact USPS 4x6 / 6x4 dimensions; mailing carriers do not require trim guides. Brochures (3376x2626 bleed canvas trimmed down to 3300x2550) DO need crop marks. This is the load-bearing reason a postcard-specific assembler exists alongside assemble_brochure_pdf rather than a single shared function."
  - "Caller-supplied page dimensions (vs. brochure's hardcoded BLEED_CANVAS_WIDTH/HEIGHT). Both shipped templates differ (1200x1800 portrait, 1800x1200 landscape) and a future template might use 1500x2100 for an oversized postcard. Hardcoding either dimension would force the worker to know which template orientation it has; passing them through is simpler."
  - "Test relaxation: the test_front_svg_xml_escapes_headline assertion was tightened during GREEN to check each escape token (`&amp;`, `&lt;World&gt;`) independently rather than the full escaped string. The original strict assertion would have required the headline to render on a single line, but fit_to_bbox legitimately wraps long headlines across multiple <tspan> elements (the cover_title bbox is 1040x300 at 96pt; 'Hello & Goodbye <World>' overflows). The renderer is correct; the test was overly rigid."
  - "Image / logo placeholder helpers in the postcard renderer DO NOT accept image bytes. Phase 23-03 is the 'no-image-binding' tier — the worker plan (23-04) is responsible for wiring generated image bytes into the placeholder either before render (by editing the template's fallback_fill) or after render (by compositing on top of the rasterized PNG). For this plan, image_placeholder always renders the fallback fill + label; logo_placeholder always renders a monogram '•' (PostcardContent has no org field, unlike BrochureContent)."

patterns-established:
  - "Postcard renderer file layout: content_model.py (Pydantic payload + resolve_key), renderer.py (render_postcard + element helpers), schema_model.py + loader.py from Phase 23-01."
  - "Postcard PDF stage layout: stages/pdf.py exports assemble_postcard_pdf + PostcardPDFError. Mirrors brochure's stages/pdf.py file but with a postcard-specific PDF assembler signature."
  - "Test file layout: tests/postcard/schema_renderer/test_renderer.py + tests/postcard/stages/test_pdf.py (mirroring tests/brochure/{schema_renderer/...,test_pdf.py})."

requirements-completed: [PC-04]  # PC-04 renderer + PDF half. PC-03 (address-block typography precision) is shared with this plan; the schema-renderer + content_model bits land here, full PC-03 closure happens when Phase 23-04 wires address blocks through the worker.

# Metrics
duration: ~10min
tasks: 2
files_created: 7
files_modified: 1
tests_added: 31
tests_total_local: 31  # 18 renderer + 13 PDF
tests_total_subsystem: 617  # postcard + brochure + flyer (no regressions)
completed: 2026-04-25
---

# Phase 23 Plan 03: Postcard Renderer + PDF Assembler Summary

**Schema -> SVG renderer (`render_postcard`) and 2-page PDF assembler (`assemble_postcard_pdf`) for the postcard primitive — `PostcardContent` payload + `PostcardAddressBlock` + cross-panel address-block resolution + XML-escape on every user string.**

## Performance

- **Duration:** ~10 minutes
- **Tasks:** 2 (both autonomous, both TDD)
- **Files created:** 7 (4 code + 1 modified barrel + 2 test/init)
- **Tests added:** 31 (18 renderer + 13 PDF)
- **Subsystem-wide tests:** 617 across postcard + brochure + flyer (no regressions vs. plan 23-02 baseline)

## Accomplishments

- Implemented `PostcardContent` Pydantic payload mirroring `PostcardCreateRequest` shape but decoupled at the module boundary (the renderer never imports `flyer_generator.api.*`):
  - `headline: str (1..200)`, `body: str (1..2000)`, `image_hint: str | None (..500)`, `address_block: PostcardAddressBlock | None`
  - `PostcardAddressBlock` with `recipient_name` / `street` / `city_state_zip` (each 1..120, matching api/AddressBlock)
  - `resolve_key()` flat namespace: `headline`, `body`, `image_hint`, `address_block.{recipient_name,street,city_state_zip}`. Address-block prefix resolves to `""` when `address_block is None` (renders empty TextElement rather than skipping).
- Implemented `render_postcard(template, content) -> (front_svg, back_svg)`:
  - Walks each panel as a full canvas (no `<g translate>`, no bleed math, no fold lines)
  - Re-uses brochure shape primitives (`render_shape`, `render_fill`, `_fill_opacity`) and text-fit helpers (`chars_per_line`, `fit_to_bbox`, `wrap_text`) via cross-package imports
  - Element helpers (text / bullets / divider / image_placeholder / logo_placeholder) copied into the postcard renderer with the simpler topology
  - Every interpolated user string passes through `xml.sax.saxutils.escape` (T-23-09 mitigation, verified by 4 dedicated injection-guard tests)
  - Handles both shipped templates: `classic_portrait` (1200x1800 portrait) and `modern_landscape` (1800x1200 landscape)
- Implemented `assemble_postcard_pdf(front_png, back_png, page_width, page_height) -> bytes`:
  - 2-page PDF (page 1 = front, page 2 = back)
  - Caller-supplied page dimensions (no fixed bleed canvas)
  - **No crop marks** — postcards print at exact USPS 4x6 / 6x4 dimensions with no bleed
  - Wraps reportlab/PIL exceptions as `PostcardPDFError` (subclass of `RasterizationError`)
  - Validates inputs: empty front/back bytes raise with field name in message; non-positive page dims raise with "page dimensions" in message
- Updated `flyer_generator/postcard/schema_renderer/__init__.py` to barrel-export the 3 new symbols (`PostcardAddressBlock`, `PostcardContent`, `render_postcard`) alongside the existing 3 (`PostcardTemplateSchema`, `list_templates`, `load_template`).
- End-to-end smoke verified for both shipped templates: load_template -> render_postcard -> Rasterizer.rasterize -> assemble_postcard_pdf produces PDFs of 431KB (portrait) and 208KB (landscape) starting with the `%PDF-` magic bytes.

## Task Commits

Each task followed the TDD RED -> GREEN gates with explicit commits:

1. **Task 1 RED:** `9b6c49c` — `test(23-03): add failing tests for PostcardContent + render_postcard`
   (18 tests; all fail at the import boundary because PostcardContent / PostcardAddressBlock / render_postcard don't exist yet)
2. **Task 1 GREEN:** `1ecc6eb` — `feat(23-03): implement PostcardContent + render_postcard renderer`
   (18/18 pass; broader 336 schema_renderer tests across postcard + brochure + flyer also pass)
3. **Task 2 RED:** `eb37837` — `test(23-03): add failing tests for assemble_postcard_pdf + PostcardPDFError`
   (13 tests; all fail with `ModuleNotFoundError: No module named 'flyer_generator.postcard.stages'`)
4. **Task 2 GREEN:** `e9eec4d` — `feat(23-03): implement assemble_postcard_pdf + PostcardPDFError`
   (13/13 PDF tests pass; broader 617 tests across postcard + brochure + flyer suites pass)

Plan metadata commit (this SUMMARY.md) will follow.

## Files Created

### Package code
- `flyer_generator/postcard/schema_renderer/content_model.py` — PostcardContent + PostcardAddressBlock + resolve_key (108 lines)
- `flyer_generator/postcard/schema_renderer/renderer.py` — render_postcard + 6 element helpers + per-panel canvas walker (498 lines)
- `flyer_generator/postcard/stages/__init__.py` — empty package marker
- `flyer_generator/postcard/stages/pdf.py` — assemble_postcard_pdf + PostcardPDFError (108 lines)

### Tests
- `tests/postcard/schema_renderer/test_renderer.py` — 18 tests covering barrel re-exports, content_key resolution (5), render_postcard return shape (3), XML escape on headline/body/address (3), address-None path + landscape canvas (2), SVG injection guards (3) (291 lines)
- `tests/postcard/stages/__init__.py` — empty package marker
- `tests/postcard/stages/test_pdf.py` — 13 tests covering import + RasterizationError subclass relation (2), empty-input rejection (2), PDF magic + 2-page count + per-page dims for portrait + landscape (5), determinism (1), corrupt-PNG + zero-dim guards (2), per-page image XObject presence (1) (209 lines)

### Modified files
- `flyer_generator/postcard/schema_renderer/__init__.py` — added 3 new exports

## Decisions Made

- **Cross-package imports of brochure utilities (shapes + text_fit):** The shape primitives and text-fit helpers are pure utility modules with no brochure-specific layout assumptions, so importing them from the postcard renderer is a clean dependency. Element-level helpers (`_render_text_element` etc.) were copied rather than shared because their `Typography` field access is type-narrowed to `PostcardTemplateSchema`; sharing would force a `Union[TemplateSchema, PostcardTemplateSchema, FlyerTemplateSchema]` signature on the brochure helpers, expanding the cross-package surface beyond what's worth saving.
- **`resolve_key` returns `""` (not `None`) for address-block keys when `address_block is None`:** Plan must_have required "address-block TextElements render empty (no exception, no NULL string in SVG)". Returning `""` keeps the renderer's `if not text: return ""` early-out firing at the element level — visually equivalent to skipping, but with explicit semantics that don't conflate "address not supplied" with "key not recognised by the resolver" (which still returns `None`).
- **No crop marks on postcards:** Postcards print at exact USPS 4x6 / 6x4 dimensions; mailing carriers do not require trim guides. The brochure assembler retains its crop marks because its bleed canvas (3376x2626) is trimmed to 3300x2550 by the printer. This functional difference is the load-bearing reason a postcard-specific PDF assembler exists alongside `assemble_brochure_pdf`.
- **Caller-supplied page dimensions in `assemble_postcard_pdf`:** Both shipped templates differ in canvas dims (1200x1800 vs. 1800x1200) and a future template might be 1500x2100. Hardcoding either dimension would force the worker to know which orientation it has; passing them through is simpler.
- **Test relaxation for headline XML escape:** The original `assert "Hello &amp; Goodbye &lt;World&gt;" in fr` failed because `fit_to_bbox` legitimately wraps long headlines across multiple `<tspan>` elements (cover_title bbox is 1040x300 at 96pt; "Hello & Goodbye <World>" overflows). The renderer is correct; the test was tightened to check each escape token (`&amp;`, `&lt;World&gt;`) independently while still asserting the raw unescaped form is absent. The test refinement is a Rule 1 fix (test was overly rigid; renderer correctness is preserved).
- **Postcard image / logo placeholders are fallback-only in this plan:** `PostcardContent` has no `org` field (so logo monogram falls back to a "•" glyph), and `render_postcard` doesn't accept an `images=` argument (so `image_placeholder` always renders the fallback fill + label). Wiring real image / logo bytes is a worker-plan concern (23-04 onward).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Test correction] Headline XML-escape assertion was too strict for fit_to_bbox wrapping**

- **Found during:** Task 1 GREEN (post-implementation pytest run)
- **Issue:** The plan's behavior spec for Test 11 said "front SVG contains the headline string XML-escaped (test with content.headline = 'Hello & Goodbye <World>')". The literal interpretation — `assert "Hello &amp; Goodbye &lt;World&gt;" in fr` — failed because `fit_to_bbox` wraps the headline across two `<tspan>` elements at cover_title's 96pt size in classic_portrait's 1040x300 cover bbox. The renderer's escaping IS correct; the assertion was over-specifying that the entire headline must render on a single line.
- **Fix:** Relaxed the test to check each escape token independently (`&amp;` present, `&lt;World&gt;` present) and assert the raw unescaped form (`<World>` and ` & ` — the raw ampersand surrounded by spaces — neither match a legitimate SVG production) is absent. The test still proves XML-escape mitigation; it no longer over-couples to fit_to_bbox layout decisions.
- **Files modified:** `tests/postcard/schema_renderer/test_renderer.py`
- **Committed in:** `1ecc6eb` (Task 1 GREEN)

**Total deviations:** 1 — a test relaxation aligning the assertion with the rendered tspan-per-line output. No code-side deviations; no scope creep.

## Issues Encountered

None — both tasks went RED -> GREEN on first GREEN attempt (modulo the headline-escape test relaxation noted above).

## Threat Flags

None — the trust-boundary mitigations documented in the plan's `<threat_model>` are all satisfied:

- **T-23-09 (Tampering: SVG injection via headline / body / address fields):** Mitigated. `xml_escape` appears 7 times in `renderer.py`. 4 dedicated injection-guard tests verify: `<script>` in body, `<img src=x onerror=alert(1)>` in headline, `<b>Bold</b>` in `recipient_name`, plus the headline/body baseline `&` / `<` / `>` cases. None of the raw forms appear in rendered output; all escaped forms do.
- **T-23-10 (DoS: pathological text-wrap loop):** Mitigated upstream by `fit_to_bbox` (verbatim from brochure renderer; bails on overflow). Phase 26 will add adversarial oversize-payload coverage.
- **T-23-11 (Tampering: corrupt PNG bytes crash worker):** Mitigated. reportlab/PIL exceptions are caught and re-raised as `PostcardPDFError("PDF assembly failed: ...")`. Test `test_corrupt_png_raises_postcard_pdf_error` confirms b"not-a-png" inputs land on this branch with the expected error type. Worker plan 23-04 will surface the typed name to `JobRecord.error_detail`.

No new threat surface introduced beyond the registered items.

## Known Stubs

None — every artifact this plan claims to provide is wired and tested:

- `PostcardContent` + `PostcardAddressBlock` Pydantic models: validated, barrel-exported, regression-tested via 5 resolve_key tests
- `render_postcard`: returns 2 SVGs, both sized to `template.canvas`, both with XML-escaped user content; verified end-to-end via `Rasterizer.rasterize -> assemble_postcard_pdf` smoke
- `assemble_postcard_pdf`: 2-page PDF, caller-supplied dims, no crop marks; verified via 4 mediabox-dimension tests + corrupt-PNG handling
- `PostcardPDFError`: subclass of `RasterizationError`; verified by `issubclass` test

The `image_placeholder` and `logo_placeholder` helpers in the renderer always render their fallback (gradient + label / monogram circle). This is an INTENTIONAL stub — wiring real generated-image bytes through the renderer is the worker's responsibility (23-04). The plan's success_criteria do not require image-binding, and the deferred wiring is documented above under "Decisions Made".

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Plan 23-04 (worker `task_generate_postcard`):** Can `from flyer_generator.postcard.schema_renderer import render_postcard, PostcardContent, PostcardAddressBlock` and `from flyer_generator.postcard.stages.pdf import assemble_postcard_pdf, PostcardPDFError` at module scope. Worker translates `PostcardCreateRequest` (already shipped in 23-02) into `PostcardContent` (1:1 field map: headline / body / image_hint / address_block), calls `render_postcard(load_template(req.template), content)`, rasterizes each panel via `Rasterizer(width=template.canvas.width, height=template.canvas.height).rasterize(svg)`, then calls `assemble_postcard_pdf(front_png, back_png, template.canvas.width, template.canvas.height)`. Catches `PostcardPDFError` (subclass of `RasterizationError`) for `JobRecord.error_detail`.
- **Plan 23-05 (routes):** Routes consume the worker — no direct dependency on this plan's exports.
- **Plan 23-06 (frontend):** Frontend consumes the artifact URLs from the GET detail route — no direct dependency on this plan's exports.

## TDD Gate Compliance

Both Task 1 and Task 2 were tagged `tdd="true"`. RED -> GREEN gates satisfied with explicit commits:

- **Task 1 RED:** `9b6c49c` `test(23-03): add failing tests for PostcardContent + render_postcard` (18 tests; all fail with `ImportError: cannot import name 'PostcardContent' from 'flyer_generator.postcard.schema_renderer'`)
- **Task 1 GREEN:** `1ecc6eb` `feat(23-03): implement PostcardContent + render_postcard renderer` (18/18 pass; 336 schema_renderer subsystem tests pass)
- **Task 2 RED:** `eb37837` `test(23-03): add failing tests for assemble_postcard_pdf + PostcardPDFError` (13 tests; all fail with `ModuleNotFoundError: No module named 'flyer_generator.postcard.stages'`)
- **Task 2 GREEN:** `e9eec4d` `feat(23-03): implement assemble_postcard_pdf + PostcardPDFError` (13/13 PDF tests pass; 617 subsystem tests pass)

No REFACTOR commits needed — both GREEN passes were minimal-correct on first try, with one in-place test relaxation during Task 1 GREEN (committed alongside the GREEN work, not as a separate commit).

## Self-Check: PASSED

Verified each created/modified file exists and each commit hash is reachable:

- `flyer_generator/postcard/schema_renderer/content_model.py` FOUND (created)
- `flyer_generator/postcard/schema_renderer/renderer.py` FOUND (created)
- `flyer_generator/postcard/schema_renderer/__init__.py` FOUND (modified — barrel adds 3 exports)
- `flyer_generator/postcard/stages/__init__.py` FOUND (created)
- `flyer_generator/postcard/stages/pdf.py` FOUND (created)
- `tests/postcard/schema_renderer/test_renderer.py` FOUND (created — 18 tests)
- `tests/postcard/stages/__init__.py` FOUND (created)
- `tests/postcard/stages/test_pdf.py` FOUND (created — 13 tests)
- Commit `9b6c49c` (Task 1 RED) FOUND
- Commit `1ecc6eb` (Task 1 GREEN) FOUND
- Commit `eb37837` (Task 2 RED) FOUND
- Commit `e9eec4d` (Task 2 GREEN) FOUND

31 tests across 2 new test files green; 617 tests/postcard + tests/brochure + tests/flyer pass with no regressions vs. the 23-02 baseline. End-to-end smoke verifies the full template -> SVG -> PNG -> PDF chain for both `classic_portrait` (1200x1800, with address) and `modern_landscape` (1800x1200, no address) templates.

---

*Phase: 23-postcard-primitive*
*Completed: 2026-04-25*
