# Roadmap: Flyer Generator

## Overview

This roadmap delivers an AI-powered event flyer generator, then extends the same pipeline to a tri-fold landscape brochure generator. Phases 1-4 deliver the flyer (data contracts → image generation → visual composition → orchestration). Phases 5-9 deliver the brochure extension (models/geometry → landscape workflow → SVG composition → PDF assembly → CLI/public API), reusing the flyer's ComfyCloud client, vision evaluator, preset registry, and rasterizer.

Design reference: [docs/brochure-plan.md](../docs/brochure-plan.md).

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation** - Data contracts, configuration, error hierarchy, style presets, and project scaffolding
- [x] **Phase 2: Image Pipeline** - AI background generation via ComfyCloud and vision evaluation via Claude (completed 2026-04-17)
- [x] **Phase 3: Composition** - Layout resolution, SVG composition with text overlays, and PNG rasterization (completed 2026-04-17)
- [x] **Phase 4: Orchestration & CLI** - Pipeline wiring with retry loop, CLI entrypoint, and public API surface (completed 2026-04-17)
- [x] **Phase 5: Brochure Models & Panel Geometry** - BrochureInput / BrochureSection / BrochureOutput Pydantic models and panel geometry layout module (completed 2026-04-18)
- [x] **Phase 6: Brochure Workflow & Prompt Builder** - turbo_landscape ComfyCloud workflow, brochure cover prompt builder, vision hook for cover evaluation (completed 2026-04-18)
- [x] **Phase 7: Brochure Composition** - Two-sheet SVG composer (outside + inside), rasterizer integration producing two 3376x2626 PNGs (bleed canvas; trim 3300x2550) (completed 2026-04-18)
- [x] **Phase 8: Brochure PDF Assembly** - reportlab-based 2-page print-ready PDF with bleed canvas and crop marks (completed 2026-04-18)
- [x] **Phase 9: Brochure CLI & Public API** - `python -m flyer_generator.brochure` subcommand, generate_brochure public API, BrochureGenerator orchestrator, end-to-end integration tests (completed 2026-04-18)
- [x] **Phase 10: Generative LLM Clients + Outline + Text Stages** - OllamaTextClient/AnthropicTextClient, BrochurePrompt/BrochureOutline models, outline + per-section text generation stages (completed 2026-04-18)
- [x] **Phase 11: Layout Selection + Template Library + Fit Optimization** - 6 named layout templates (editorial, minimalist, playful, gallery_strip, quote_driven, spotlight), LLM layout selection, text-fit rewrite loop (completed 2026-04-18)
- [x] **Phase 12: Vector Shape Library + Composer v2** - 6 parameterized SVG shapes (circle_offpage, rotated_block, accent_bar, dot_grid, pullquote_frame, corner_wedge), composer rewrite honoring LayoutChoice; fixes v1 fold-line print bug + back-panel kind leak (completed 2026-04-18)
- [x] **Phase 13: Imagery Orchestration + Verification Loop** - multi-image generation (1 hero + 0-3 spot images), 5-dimension rubric verification, weakest-stage regen loop (max 2 cycles) (completed 2026-04-18)
- [x] **Phase 14: Prompt-Driven Public API + CLI + End-to-End** - `generate_brochure_from_prompt()` async public API, `--prompt` CLI flag, end-to-end integration tests with mocked LLM + Comfy (completed 2026-04-18)
- [x] **Phase 15: Polish — Shape/Text Collision + Spot-Image Compositing** - constrain decorative shapes to avoid heading zones, composite spot images into inner panels + tuck flap, re-verify end-to-end visual output (completed 2026-04-18)
- [x] **Phase 16: Quality tuning — section distribution, heading hierarchy, verification teeth** - smarter multi-section panel assignment, accent rules under every heading, cover-title drop-shadow + auto-shrink, verify-loop regen with seed variation (completed 2026-04-18)
- [x] **Phase 17: Improvements pass (HIGH/MEDIUM/LOW from docs/brochure-improvements.md)** - rubric-driven verification, two-sheet scoring, verdict/lint on BrochureOutput + CLI surfacing, template typography threaded through composer, @font-face data-URI infrastructure, fit optimizer retry loop, tuck-flap tagline for N<4, aspect-aware spot crop, cover_image_concept field, mechanical output linter (completed 2026-04-18)
- [x] **Phase 18: Brand Kit System** - scrape website → untracked brand kit (colors/fonts/logos/voice) → apply to any schema_renderer template, WCAG contrast validation + auto-remediation, visual inspection + adversarial audit loop; also increase readable type size across templates (completed 2026-04-21)

## Phase Details

### Phase 1: Foundation
**Goal**: All data contracts, configuration, error types, and style presets exist and are importable -- the shared vocabulary every pipeline stage depends on
**Depends on**: Nothing (first phase)
**Requirements**: FOUND-01, FOUND-02, FOUND-03, FOUND-04, FOUND-05
**Success Criteria** (what must be TRUE):
  1. Running `python -c "from flyer_generator.models import EventInput, ComfyJob, GeneratedBackground, VisionVerdict, LayoutZones, ResolvedLayout, FlyerOutput"` succeeds
  2. Configuration loads from FLYER_-prefixed environment variables with sensible defaults
  3. All five exception types (ComfyError, VisionError, CompositionError, RasterizationError, MaxAttemptsExceededError) are importable and form a hierarchy
  4. Six style presets are registered and retrievable by name (photorealistic, anime, western_cartoon, scifi, watercolor, retro_poster)
  5. pyproject.toml defines all dependencies and the project installs cleanly with uv
**Plans:** 2 plans
Plans:
- [x] 01-01-PLAN.md -- Project scaffold, config, errors, logging
- [x] 01-02-PLAN.md -- Data models, zones, presets, tests, public API

### Phase 2: Image Pipeline
**Goal**: Given event data and a style preset, the system can generate an AI background image via ComfyCloud and evaluate it with Claude vision for suitability, zones, and text color
**Depends on**: Phase 1
**Requirements**: IGEN-01, IGEN-02, IGEN-03, IGEN-04, IGEN-05, VISN-01, VISN-02, VISN-03, VISN-04, VISN-05
**Success Criteria** (what must be TRUE):
  1. StylePromptBuilder produces correct positive/negative prompt strings from a preset, event concept, and optional refinement hint
  2. ComfyClient can submit a workflow to ComfyCloud, poll for completion with exponential backoff, and download the resulting image
  3. Downloaded 832x1472 image is upscaled to exactly 1080x1920 via Pillow LANCZOS
  4. VisionEvaluator sends background + context to Claude and returns a structured VisionVerdict with approval status, confidence, zones, and text color
  5. Confidence gate rejects verdicts below threshold, and zone validation rejects verdicts with invalid zone names
**Plans:** 3/3 plans complete
Plans:
- [x] 02-01-PLAN.md -- StylePromptBuilder and ImagePreprocessor (pure logic stages)
- [x] 02-02-PLAN.md -- ComfyClient (ComfyCloud submit, poll, download)
- [x] 02-03-PLAN.md -- VisionEvaluator (Claude vision evaluation with parsing and validation)

### Phase 3: Composition
**Goal**: Given a background image and vision verdict, the system can produce a complete 1080x1920 PNG flyer with properly placed text, scrims, badges, and accents
**Depends on**: Phase 2
**Requirements**: COMP-01, COMP-02, COMP-03, COMP-04, COMP-05, COMP-06, COMP-07, COMP-08, COMP-09
**Success Criteria** (what must be TRUE):
  1. LayoutResolver maps all zone labels to correct pixel coordinates on the 1080x1920 canvas
  2. PosterComposer generates valid SVG with base64-embedded background, text overlays, scrim gradients, fee badge pill, accent line, and accent stripe
  3. Title text auto-sizes based on length, wraps words correctly, and merges widow lines
  4. All user-supplied strings are XML-escaped before SVG insertion (no injection possible)
  5. Rasterizer produces a 1080x1920 PNG from the SVG via cairosvg with dimension verification
**Plans:** 2/2 plans complete
Plans:
- [x] 03-01-PLAN.md -- LayoutResolver and Rasterizer (zone mapping + SVG-to-PNG)
- [x] 03-02-PLAN.md -- PosterComposer (SVG composition with all overlays)

### Phase 4: Orchestration & CLI
**Goal**: All pipeline stages are wired into a complete generate-evaluate-retry loop with CLI access and a clean public API
**Depends on**: Phase 3
**Requirements**: PIPE-01, PIPE-02, PIPE-03, PIPE-04, CLI-01, CLI-02, CLI-03, CLI-04, CLI-05, CLI-06
**Success Criteria** (what must be TRUE):
  1. Running `python -m flyer_generator --title "Test" --date "2026-05-01" --venue "Hall" --preset photorealistic --output flyer.png` produces a flyer PNG
  2. Vision rejection triggers regeneration with refinement hints, up to max_bg_attempts (default 3)
  3. `--list-presets` prints all available presets, `--dry-run` prints the prompt without calling ComfyCloud, `--event-json` loads event data from file
  4. Public API (generate_flyer, FlyerGenerator, EventInput, FlyerOutput, PresetRegistry) is importable and functional
  5. Every pipeline run emits structured logs with a trace_id correlating all events from attempt_start through flyer_generated
**Plans:** 3/3 plans complete
Plans:
- [x] 04-01-PLAN.md -- FlyerGenerator pipeline orchestrator with retry loop and structured logging
- [x] 04-02-PLAN.md -- CLI entrypoint via typer with all flags
- [x] 04-03-PLAN.md -- Public API surface (generate_flyer, exports, custom preset registration)

### Phase 5: Brochure Models & Panel Geometry
**Goal**: BrochureInput, BrochureSection, BrochureBackPanel, ContactBlock, and BrochureOutput Pydantic models exist and validate correctly; a pure-function panel geometry module returns correct pixel rectangles (with bleed and safe zones) for all six tri-fold panels on a 3300x2550 landscape sheet
**Depends on**: Phase 4
**Requirements**: From docs/brochure-plan.md sections 2 and 3
**Success Criteria** (what must be TRUE):
  1. `from flyer_generator.brochure.models import BrochureInput, BrochureSection, BrochureBackPanel, ContactBlock, BrochureOutput` succeeds
  2. BrochureInput validates hex accent colours, enforces 2-5 sections, and accepts optional contact/back_panel fields
  3. flyer_generator.brochure.stages.layout.compute_panel_layout(dims, bleed, safe_zone) returns a ResolvedBrochureLayout with six panel rectangles in correct positions
  4. Unit tests cover geometry math (panel widths sum to sheet width, safe zones inset correctly, bleed canvas larger than trim) and model validation (boundary section counts, invalid colours rejected)
  5. No runtime dependency on ComfyCloud, Anthropic, or reportlab in this phase

### Phase 6: Brochure Workflow & Prompt Builder
**Goal**: The system can generate a landscape cover hero image end-to-end (ComfyCloud → upscale → vision evaluation) using a new brochure-specific prompt and workflow, with no composition yet
**Depends on**: Phase 5
**Requirements**: From docs/brochure-plan.md sections 4, 5, and 6
**Success Criteria** (what must be TRUE):
  1. `flyer_generator/workflows/turbo_landscape.json` exists with latent_dimensions [1472, 832] and valid injection_points; workflow_loader.load_workflow('turbo_landscape') returns a valid WorkflowConfig
  2. A brochure prompt builder composes positive/negative prompts from a style preset, hero_concept, and BROCHURE_COVER_DIRECTIVES (centred subject, clean edges, landscape framing)
  3. VisionEvaluator accepts an optional prompt_template parameter that swaps the flyer template for a brochure cover template (no 9-zone grid)
  4. An async hero-generation entrypoint returns upscaled bytes + VisionVerdict given a BrochureInput, mirroring flyer's attempt/retry semantics
  5. Integration tests with respx-mocked ComfyCloud and anthropic stubs confirm regen loop, confidence gate, and attempt limit behave identically to flyer pipeline

### Phase 7: Brochure Composition
**Goal**: Given a BrochureInput plus a generated hero image, the system produces two 3300x2550 PNGs (outside sheet, inside sheet) with the hero embedded on the front cover, accent-tinted gradients on other panels, panel text laid out within safe zones, and fold/crop marks on a separate non-printing SVG layer
**Depends on**: Phase 6
**Requirements**: From docs/brochure-plan.md sections 4 and 7
**Success Criteria** (what must be TRUE):
  1. BrochureComposer produces two valid SVG documents (outside, inside) with six panels total
  2. Front cover panel embeds the hero image as base64; other five panels render accent-tinted gradients derived from BrochureInput.color_accent
  3. Each panel's heading and body text renders within the safe zone with word wrapping and auto font-size reduction on overflow
  4. Fold lines and crop marks are on a separate SVG layer that can be toggled non-printing
  5. Existing Rasterizer.rasterize() (cairosvg) converts both SVGs to PNGs at exactly 3300x2550; all user-supplied strings are XML-escaped

### Phase 8: Brochure PDF Assembly
**Goal**: A 2-page print-ready PDF is produced from the two brochure PNGs, sized to the bleed canvas (3375x2625 @ 300 DPI), with crop marks drawn in the bleed area and pages ordered outside-first then inside
**Depends on**: Phase 7
**Requirements**: From docs/brochure-plan.md section 7
**Success Criteria** (what must be TRUE):
  1. `reportlab` is added to pyproject.toml and installs cleanly
  2. A pdf assembly module accepts front_png_bytes + back_png_bytes and returns a 2-page PDF as bytes
  3. PDF page dimensions match the bleed canvas (3375x2625 at 300 DPI); images placed with correct origin offset so trim area aligns
  4. Crop marks are drawn in the bleed area at all four trim corners on both pages
  5. A new BrochurePDFError is raised on assembly failure; tests verify page count, dimensions, and crop mark presence (parsed via pypdf)

### Phase 9: Brochure CLI & Public API
**Goal**: End-to-end `python -m flyer_generator brochure ...` produces brochure_front.png, brochure_back.png, and brochure_print.pdf from CLI arguments or a JSON input file; public API exposes generate_brochure, BrochureGenerator, and related models
**Depends on**: Phase 8
**Requirements**: From docs/brochure-plan.md sections 8 and 9
**Success Criteria** (what must be TRUE):
  1. Running `python -m flyer_generator brochure --brochure-json sample.json --output out/` produces three files without errors
  2. `from flyer_generator.brochure import generate_brochure, BrochureGenerator, BrochureInput, BrochureOutput` succeeds
  3. BrochureGenerator orchestrates prompt_builder → comfy_client → preprocessor → vision → composer → rasterizer → pdf with structured logging and trace_id propagation
  4. CLI flags include --title, --subtitle, --concept, --preset, --accent, --org, --sections-json, --brochure-json, --output, --dry-run, --max-attempts; --dry-run prints prompt and panel plan without API calls
  5. Smoke test with mocked ComfyCloud + vision produces three artifacts of correct type and dimensions; existing flyer CLI behaviour is unchanged

### Phase 18: Brand Kit System
**Goal**: A developer can run `python -m flyer_generator.brand_kit fetch <url> --slug <slug>` to produce an untracked brand kit under `.brand-kits/<slug>/` (palette, typography, logos, voice hints, source artifacts), then render a brochure with `--brand-kit <slug>` that replaces the template's palette/typography/logo while validating every text region meets WCAG AA contrast and auto-remediating failures; a post-render audit flags low-density panels, low-contrast text regions, and under-filled content budgets. Templates also gain a typography-scale pass so inside-panel body/bullet text reads comfortably at print size.
**Depends on**: Phase 17 (schema_renderer subsystem — templates, renderer, text_gen, image_gate)
**Requirements**: From HANDOFF.md §8 (BrandKit models, scraper, contrast, applier, audit, storage, CLI, typography uplift)
**Success Criteria** (what must be TRUE):
  1. `from flyer_generator.brand_kit import BrandKit, BrandPalette, BrandTypography, BrandLogo, BrandVoice, fetch_brand_kit, load_brand_kit, apply_brand_kit, audit_render` succeeds; all models are Pydantic v2 and round-trip to `brand.json`
  2. `python -m flyer_generator.brand_kit fetch <url> --slug <slug>` writes `.brand-kits/<slug>/brand.json` + `logos/*` + `source/screenshot.png` using Playwright when available and `httpx + beautifulsoup4` as deterministic fallback; missing fields remain null rather than invented
  3. `apply_brand_kit(template, kit)` returns a new `TemplateSchema` with palette + typography replaced and typography sizes scaled by `kit.size_multiplier` (default `1.0`), preserving schema validity; `--brand-kit <slug>` in `python -m flyer_generator.brochure.schema_renderer` plumbs through logo + colors + fonts
  4. A contrast module built on `wcag-contrast-ratio` (+ `coloraide` for tone adjustment) validates every body/heading text region against its background; failing regions are auto-remediated by swapping to the opposite neutral from the kit, and the final `ContrastReport` lists every pair with ratio + AA/AAA verdict
  5. A `BrandKitError` (+ subclasses for scrape / contrast / audit failure) raises cleanly with typed context; all new deps pinned in `pyproject.toml`; `.brand-kits/` is added to `.gitignore` and `.brand-kit-template.json` is tracked as the schema reference
  6. Post-render audit (`audit_render`) produces a structured report with per-panel whitespace density, contrast violations, and per-region content-budget fill — plus an iterate loop that regenerates copy / swaps contrast up to 3 cycles when issues are found
  7. Tests cover: scraper with mocked HTML (Playwright + BS4 paths), models round-trip, contrast ratios (known pairs + remediation), applier (palette + typography + logo merge + size_multiplier), audit (whitespace + contrast + density fixtures), CLI (fetch + list + show), and an end-to-end smoke that applies a seeded kit to `editorial_classic` and confirms AA-clean output
  8. Templates' inside-panel body/bullet sizes are raised so that default-density content no longer reads thin at print scale; the existing 78-cell schema-renderer gallery still renders without overflow, and the shrubnet v9 sample renders with the kit applied and passes contrast + density audits
**Plans:** 8/8 plans complete
Plans:
- [x] 18-01-PLAN.md -- Dependencies + errors + storage scaffold + `.brand-kit-template.json` + `.gitignore`
- [x] 18-02-PLAN.md -- Pydantic v2 data models (BrandKit, BrandPalette, BrandTypography, BrandLogo, BrandVoice, BrandPhotoHints, ColorUsage)
- [x] 18-03-PLAN.md -- Contrast module (wcag_ratio + AA/AAA classification + opposite-neutral swap + OKLCH remediation)
- [x] 18-04-PLAN.md -- Scraper (Playwright primary + httpx/BS4/tinycss2 fallback + SSRF gating + palette extraction)
- [x] 18-05-PLAN.md -- Applier (apply_brand_kit immutable transform with palette/typography swap + size_multiplier scaling + AA guardrail)
- [x] 18-06-PLAN.md -- Audit module (whitespace density + contrast + content-budget fill + iterate_audit_loop)
- [x] 18-07-PLAN.md -- CLI (fetch/list/show) + --brand-kit flag in schema_renderer + end-to-end integration smoke
- [x] 18-08-PLAN.md -- Typography uplift across 13 templates (body_size, bullet_size baseline bumps)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 2/2 | Complete | 2026-04-16 |
| 2. Image Pipeline | 3/3 | Complete   | 2026-04-17 |
| 3. Composition | 2/2 | Complete   | 2026-04-17 |
| 4. Orchestration & CLI | 3/3 | Complete   | 2026-04-17 |
| 5. Brochure Models & Panel Geometry | 0/? | Not Started | - |
| 6. Brochure Workflow & Prompt Builder | 0/? | Not Started | - |
| 7. Brochure Composition | 0/? | Not Started | - |
| 8. Brochure PDF Assembly | 0/? | Not Started | - |
| 9. Brochure CLI & Public API | 0/? | Not Started | - |
| 18. Brand Kit System | 8/8 | Complete   | 2026-04-21 |
