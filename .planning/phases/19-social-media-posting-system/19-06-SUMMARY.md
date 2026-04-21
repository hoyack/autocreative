---
phase: 19-social-media-posting-system
plan: 06
subsystem: rendering
tags: [social, svg, cairosvg, pillow, brand-kit, rasterization, xml-escape]

# Dependency graph
requires:
  - phase: 18-brand-kit
    provides: apply_brand_kit transform pattern + BrandKit/BrandPalette/BrandTypography models
  - phase: 19-social-media-posting-system
    provides: PostTemplate schema + 12 built-in JSON templates (Plan 05); PostCopy model (Plan 02); SocialError taxonomy (Plan 02); _MAX_IMAGE_MP 50 MP cap pattern (Plan 04)
  - phase: 17-brochure-schema-renderer
    provides: schema_renderer.shapes.render_rect; schema_model.Palette + Typography; SolidFill + ShapeElement models
provides:
  - render_post(template, copy, brand_kit, *, hero_image_bytes=None) -> PNG bytes
  - _apply_brand_kit_to_post_template helper (PostTemplate analog of Phase 18 apply_brand_kit)
  - Single chokepoint for post rasterization (Plan 07 generator depends on it)
affects:
  - 19-07 (generator orchestrator calls render_post per post)
  - 19-08 (audit consumes render_post output)
  - 19-09 (CLI/storage persistence of rendered PNGs)

# Tech tracking
tech-stack:
  added: []  # No new dependencies; reused cairosvg, pillow, structlog, pydantic
  patterns:
    - "PostTemplate brand-kit application via model_copy(update={...}) -- mirrors Phase 18 applier semantics locally instead of widening applier.py's signature (keeps applier.py brochure-focused)"
    - "Non-rect shape skip with structlog warning -- forward-compatible for future shape-kind expansion without breaking v1 templates"
    - "CairoSVG primary + resvg_py optional fallback via ImportError chain"
    - "xml_escape on every user-supplied content value before <text> node insertion (T-19-06-01 mitigation)"

key-files:
  created:
    - flyer_generator/social/renderer.py
    - tests/social/test_renderer.py
  modified: []

key-decisions:
  - "Implemented _apply_brand_kit_to_post_template locally in renderer.py rather than extending Phase 18 applier.apply_brand_kit to accept PostTemplate. Keeps applier.py brochure-focused (per plan's 'preferred option (b)' guidance) and avoids coupling the brand-kit subsystem to social post types."
  - "Emitted SVG inline (single-panel composition) rather than invoking the brochure schema_renderer's 6-panel render_schema_brochure. One panel is simpler than the brochure's _render_sheet loop; no meaningful reuse beyond shape primitives."
  - "v1 renders only rect shapes. Non-rect ShapeElement kinds (circle/polygon/etc.) are logged via structlog and skipped. All 12 Plan 05 templates use rect only, so this is not a functional limitation; future phases can widen by importing render_shape from the dispatch entry point."
  - "Rasterizer uses CairoSVG as primary and treats resvg_py as optional fallback (ImportError chain). resvg_py is not currently installed in the env; tests exercise the CairoSVG path."
  - "50 MP canvas cap is checked BEFORE brand-kit application so a pathological template fails fast without triggering Pydantic model_copy overhead."

patterns-established:
  - "Social rendering chokepoint: every rendered-post path funnels through render_post, enforcing XML-escape + 50 MP cap + brand-kit application in one place."
  - "Content-key resolver (_get_content_value) tolerates unknown keys by returning empty string -- future content_key additions (e.g. copy.promo_price) won't crash older renderers; text_slot is just silently dropped."

requirements-completed: [SOC-05]

# Metrics
duration: ~15min
completed: 2026-04-21
---

# Phase 19 Plan 06: Social Renderer Summary

**Single-panel SVG composition + CairoSVG rasterization wrapper that applies a BrandKit to a PostTemplate and emits PNG bytes at canvas dimensions; covers all 12 built-in templates including the Twitter text-only path.**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-04-21T20:21:27Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files created:** 2

## Accomplishments

- `render_post(template, copy, brand_kit, *, hero_image_bytes=None) -> bytes` is the single rasterization chokepoint for Phase 19 post rendering.
- `_apply_brand_kit_to_post_template` mirrors Phase 18 applier semantics for PostTemplate without widening applier.py's brochure-focused signature.
- All 12 Plan 05 templates (3 platforms × 3 intents plus twitter variants) smoke-render at correct canvas dimensions.
- Twitter text-only branch (`image_slot=None`) produces valid PNG — required by 19-RESEARCH.md Open Risks #8.
- Threat model mitigations wired:
  - T-19-06-01: `xml.sax.saxutils.escape` on every user-supplied content value before SVG `<text>` insertion.
  - T-19-06-02: 50 MP canvas cap raises `SocialError` before CairoSVG allocation.
- Forward-compatible non-rect shape handling: unsupported `kind` values log a `social_renderer_shape_kind_unsupported_in_v1` structlog warning and skip rather than crashing.
- Full regression green: 1095 tests pass (2 deselected as `not slow`).

## Task Commits

TDD task — two commits:

1. **Task 1 RED: failing tests** — `951b181` (test)
2. **Task 1 GREEN: implementation** — `05e9ba2` (feat)

## Files Created/Modified

- `flyer_generator/social/renderer.py` — 400-line renderer with brand-kit application, SVG composition, CairoSVG rasterization, and 50 MP / XML-escape guardrails.
- `tests/social/test_renderer.py` — 7 tests covering canvas dims on value-prop LinkedIn, Twitter text-only path, brand-kit-required-on-null-palette, XML escape under injection attempt, 50 MP cap enforcement, non-rect shape skip warning (capsys), and 12-template smoke.

## Decisions Made

See `key-decisions` in frontmatter above. Highlights:

- Local `_apply_brand_kit_to_post_template` (Option B from plan) preserves applier.py's brochure focus.
- v1 renders `kind: "rect"` only; all 12 templates satisfy this.
- CairoSVG primary + resvg_py optional fallback.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `Typography` construction did not match brochure schema**

- **Found during:** Task 1 (initial implementation review before RED run)
- **Issue:** The plan's sample code built `Typography(heading_family=..., body_family=..., size_scale={...})` with a `size_scale` kwarg. The actual `flyer_generator.brochure.schema_renderer.schema_model.Typography` ships `cover_title_size`, `body_size`, `bullet_size`, etc. — no `size_scale` field — and uses `ConfigDict(extra="forbid")`, so constructing it with `size_scale=` would raise a Pydantic ValidationError. Would have caused every render to explode.
- **Fix:** Reused the brochure Typography's actual size fields via `_TYPOGRAPHY_SIZE_FIELDS` tuple plus `model_copy(update={...})` for the scale-by-multiplier step, exactly mirroring `flyer_generator/brand_kit/applier.py::_build_typography`.
- **Files modified:** flyer_generator/social/renderer.py
- **Verification:** All 7 tests in tests/social/test_renderer.py pass; Typography builds cleanly for every template under the default `size_multiplier=1.0`.
- **Committed in:** 05e9ba2 (Task 1 GREEN commit)

**2. [Rule 1 - Bug] Non-rect shape test used `caplog` which structlog ignores**

- **Found during:** Task 1 GREEN run
- **Issue:** The plan's test asserted via pytest's `caplog` that a structlog-emitted warning appeared. This project's structlog configuration writes to stdout via `ConsoleRenderer` and does NOT route through the stdlib `logging` module, so `caplog.records` was always empty and the assertion failed even though the warning WAS emitted (visible in pytest "Captured stdout call").
- **Fix:** Switched the test to `capsys`, assert against `captured.out + captured.err` for the `social_renderer_shape_kind_unsupported_in_v1` event name or `circle` token. This matches structlog's actual sink in this project.
- **Files modified:** tests/social/test_renderer.py
- **Verification:** 7/7 tests now pass; the captured stdout shows the expected warning.
- **Committed in:** 05e9ba2 (Task 1 GREEN commit, bundled with renderer implementation since it was a single TDD task)

---

**Total deviations:** 2 auto-fixed (both Rule 1 bugs in the plan's sample code).
**Impact on plan:** Both fixes were necessary for the task to pass its own acceptance criteria. No scope creep; fixes are confined to the two files the plan already enumerated.

## Issues Encountered

None — once the two Rule 1 bugs in the plan's sample code were fixed, every acceptance criterion passed on the first end-to-end run. No iteration required on the actual rendering logic.

## TDD Gate Compliance

Gate sequence verified in git log:

- RED gate: `951b181 test(19-06): add failing tests for social.renderer.render_post` — confirmed failing with `ModuleNotFoundError` before implementation.
- GREEN gate: `05e9ba2 feat(19-06): implement social.renderer.render_post` — all 7 tests pass after implementation.
- REFACTOR gate: Not required; implementation was clean on first GREEN pass (one local edit to remove dead fall-through code was absorbed into the GREEN commit before it was staged).

## User Setup Required

None — no external service configuration required. CairoSVG system dependency (Cairo + libffi) is already required by Phase 3 composition and the brochure renderer.

## Next Phase Readiness

- Plan 07 (generator orchestrator) can import `render_post` and call it with no additional plumbing.
- Plan 08 (audit) can consume the rendered PNG bytes via `audit_post`.
- No blockers.

## Self-Check: PASSED

**Files created:**

- FOUND: flyer_generator/social/renderer.py
- FOUND: tests/social/test_renderer.py
- FOUND: .planning/phases/19-social-media-posting-system/19-06-SUMMARY.md

**Commits present in git log:**

- FOUND: 951b181 (RED)
- FOUND: 05e9ba2 (GREEN)

**Acceptance criteria grep totals:**

- `def render_post`: 1
- `def _apply_brand_kit_to_post_template`: 1
- `def _rasterize_svg`: 1
- `xml_escape`: 3
- `base64.b64encode`: 1
- `_MAX_IMAGE_MP`: 2
- `raise SocialError`: 3
- `from flyer_generator.brochure.schema_renderer.shapes import`: 1
- `render_rect`: 3
- `shape_to_svg`: 0 (correct — symbol never existed)
- `social_renderer_shape_kind_unsupported_in_v1`: 1

**Test results:**

- tests/social/test_renderer.py: 7/7 passed
- tests/ (not slow): 1095 passed, 0 failed

---
*Phase: 19-social-media-posting-system*
*Completed: 2026-04-21*
