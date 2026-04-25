# Roadmap: Flyer Generator

## Overview

This roadmap delivers an AI-powered event flyer generator, then extends the same pipeline to a tri-fold landscape brochure generator. Phases 1-4 deliver the flyer (data contracts → image generation → visual composition → orchestration). Phases 5-9 deliver the brochure extension (models/geometry → landscape workflow → SVG composition → PDF assembly → CLI/public API), reusing the flyer's ComfyCloud client, vision evaluator, preset registry, and rasterizer.

Design reference: [docs/brochure-plan.md](../docs/brochure-plan.md).

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation** - Data contracts, configuration, error hierarchy, style presets, and project scaffolding
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
- [x] **Phase 19: Social Media Posting System** - given a brand kit slug + a post brief (topic/intent/CTA), generate platform-specific social posts (LinkedIn, Twitter/X, Instagram, Facebook) with platform-appropriate copy, aspect-correct imagery, brand-kit-aware palette/typography, and adversarial audit against each platform's constraints (char limits, hashtag caps, aspect ratios, readability) (completed 2026-04-21)
- [x] **Phase 20: FastAPI + SQLAlchemy Backend** - HTTP + DB wrapper over the four existing subsystems (flyer / brochure / brand_kit / social). Async FastAPI app at `/api/v1/*`, SQLAlchemy 2.x async over SQLite (dev) / Postgres (prod) with Alembic, arq + Redis job queue for long-running ComfyCloud runs, single-user v1 (no auth, no org model), existing Python APIs reused verbatim (no reimplementation), `.brand-kits/` and `.social-campaigns/` filesystem roots preserved with DB metadata layer on top (completed 2026-04-22)
- [x] **Phase 21: React Frontend Dashboard** - React + Vite + ShadCN + Tailwind SPA consuming the Phase 20 API. Full dashboard: brand-kit list/detail + scrape, flyer creator, brochure creator, social post creator, campaign creator, job list + status stream, render gallery. Depends on Phase 20. (completed 2026-04-23)
- [x] **Phase 22: Flyer Templates & Subtype Split** - Flyer rendering becomes template-driven via a JSON-schema registry (5+ templates ship at launch) and splits into `event` and `info` subtypes on a single `FlyerInput`; FE flyer creator gains template and subtype pickers with conditional fields (completed 2026-04-25)
- [x] **Phase 23: Postcard Primitive** - `POST /api/v1/postcards` produces a front PNG + back PNG + print PDF (3 artifacts) with optional recipient address block; mirrors brochure's parallel-id / compensating-enqueue / detail-route pattern and lands in the editorial dashboard (completed 2026-04-25)
- [x] **Phase 24: Poster Primitive** - `POST /api/v1/posters` renders a larger-canvas flyer variant at 18×24 / 24×36 / 27×40, reusing the flyer pipeline with injected canvas dimensions and a dedicated poster template registry (completed 2026-04-25)
- [ ] **Phase 25: Invitation Primitive** - `POST /api/v1/invitations` renders a 5×7 portrait RSVP card at 300 DPI with heavy brand-kit conditioning; 3+ visually-distinct templates (`classic_serif`, `modern_sans`, `ornamental`) share the same RSVP schema
- [ ] **Phase 26: Adversarial Hardening Sweep** - Dedicated adversarial test suite covering prompt injection, path traversal, unicode/emoji stress, oversize payloads, PDF bombs, concurrent enqueue, and visual regression across every existing and v1.1 asset

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

### Phase 19: Social Media Posting System
**Goal**: A developer can run `python -m flyer_generator.social post --brand-kit <slug> --platform <linkedin|twitter|instagram|facebook> --intent <value-prop|announcement|testimonial|faq|carousel> --topic "<topic>" --output <dir>` to produce a platform-compliant post (copy + image bytes + audit sidecar) that respects the brand kit's palette/typography/voice, passes all platform rule validators (char limits, hashtag caps, image aspect + size), and passes WCAG AA contrast + brand-color compliance on any rendered imagery. A campaign mode generates one cohesive set of posts across multiple platforms from a single topic using shared source imagery cropped per-platform.
**Depends on**: Phase 18 (brand_kit subsystem), Phase 14 (prompt-driven public API + text_gen), Phase 13 (imagery orchestration via ComfyCloud)
**Requirements**: SOC-01, SOC-02, SOC-03, SOC-04, SOC-05, SOC-06, SOC-07, SOC-08, SOC-09, SOC-10, SOC-11
**Success Criteria** (what must be TRUE):
  1. `from flyer_generator.social import PostSpec, Post, Platform, generate_post, generate_campaign, load_platform_rules, validate_post` succeeds; all models are Pydantic v2 and round-trip to JSON
  2. Four platforms implemented with typed `PlatformRules`: LinkedIn (3000-char body, 1200×627 or 1200×1200 image), Twitter/X (280 char, up to 4 images 1200×675, optional threading), Instagram (2200-char caption, ≤30 hashtags, 1080×1080 or 1080×1350, optional 1080×1920 story), Facebook (text + image, link preview). Each ships a `validate(post)` function returning `ValidationReport` with per-rule pass/fail
  3. At least 3 post intents × 4 platforms (≥12 post templates) under `flyer_generator/social/schemas/` — each template declares `{platform, intent, aspect, text_budgets, image_slots, layout}` mirroring the schema_renderer template pattern; SVG rasterization reuses `schema_renderer` rendering pipeline for image posts
  4. `BrandVoice` (tone, example_phrases, banned_words) from Phase 18 is actually wired into text generation: `text_gen.generate_content_from_prompt` accepts a `BrandVoice` parameter and the prompt injects tone guidance + banned-word filter; generated copy is validated against banned_words before returning
  5. `generate_post(brand_kit_slug, PostBrief) → Post` orchestrates: select template → generate copy via text_gen (voice-aware) → (if image slot) generate hero via ComfyCloud using brand palette + aspect → render SVG → rasterize → audit. Output is `Post(platform, intent, copy, hashtags, image_bytes|None, validation_report, audit_report)`
  6. `generate_campaign(brand_kit_slug, topic, platforms) → Campaign` generates one source hero image at the largest required resolution (e.g. 2048×2048), then crops per-platform aspects; copy is re-generated per-platform (not merely truncated) to respect platform voice
  7. Audit extends Phase 18's `audit_render` to include platform-specific dimensions: char-count vs budget, hashtag count/length, image aspect match, image file size (platforms cap image bytes), link presence vs link-support, plus all existing contrast + density + whitespace checks
  8. CLI: `python -m flyer_generator.social post …` and `python -m flyer_generator.social campaign …` work end-to-end against the three existing brand kits (shrubnet, hoyack, thunderstaff); `list-platforms`, `list-intents`, `show-rules <platform>` CLI subcommands exist for inspection
  9. Untracked storage: `.social-campaigns/<slug>/<campaign-id>/` per-post JSON + image bytes + audit sidecar; `.social-campaigns/` in `.gitignore`; `.social-template.json` tracked as schema reference; `FLYER_SOCIAL_CAMPAIGNS_DIR` env var honored
 10. Tests cover platform validators (all 4 platforms × pass/fail cases), BrandVoice wiring (tone injection, banned-word filter), post templates (≥12 templates validate shape + produce rendered output), generator (mocked LLM + Comfy, end-to-end Post), campaign (shared hero cropped correctly per-platform), audit (platform-rule coverage), CLI (post + campaign + list + show) — all net-new tests green in < 5 min
 11. Publishing/scheduling is EXPLICITLY out of scope — phase 19 produces artifacts only. No LinkedIn API, Twitter API, Meta Graph, or scheduler integration; defer to a future phase
**Plans:** 9/9 plans complete
Plans:
- [x] 19-01-PLAN.md -- BrandVoice wiring in text_gen + BrandVoiceViolationError
- [x] 19-02-PLAN.md -- Errors tree + Pydantic models + storage + .gitignore + .social-template.json + pyproject dep bump
- [x] 19-03-PLAN.md -- Platform rules registry (4 platforms) + shared validators + Flesch-Kincaid readability
- [x] 19-04-PLAN.md -- Workflow-aspect map + Pillow crop helpers (PLATFORM_CROP_SIZES)
- [x] 19-05-PLAN.md -- Post template schema + loader + 12 JSON templates (3 intents x 4 platforms)
- [x] 19-06-PLAN.md -- Renderer (SVG build + CairoSVG rasterize + brand-kit apply)
- [x] 19-07-PLAN.md -- Voice-aware social copy generator + single-post orchestrator (generate_post)
- [x] 19-08-PLAN.md -- Audit extension (SocialAuditReport wrapping AuditReport + platform_compliance + link_policy + readability)
- [x] 19-09-PLAN.md -- Campaign orchestrator (shared hero) + typer CLI + barrel __init__ + e2e integration

### Phase 20: FastAPI + SQLAlchemy Backend
**Goal**: A developer can run `uv run uvicorn flyer_generator.api:app --reload` alongside `uv run arq flyer_generator.api.worker.WorkerSettings` and, against a clean database, (a) POST `/api/v1/brand-kits/fetch` to scrape a brand kit asynchronously and poll the returned job to `succeeded`, (b) POST `/api/v1/flyers` with structured event data + a preset + optional brand-kit slug and poll the job to `succeeded`, (c) POST `/api/v1/brochures` with a content JSON + template + style preset + brand-kit and poll to `succeeded`, (d) POST `/api/v1/social/posts` with a `PostBrief` and poll to `succeeded`, (e) POST `/api/v1/social/campaigns` with topic + platforms and poll to `succeeded`, (f) stream the rendered artifact via `GET /api/v1/renders/{id}/image`. Single-user v1 (no `User`/`Organization` models exposed, no auth middleware). All five existing Python entrypoints (`FlyerGenerator.generate`, `render_schema_brochure` + `generate_template_images`, `fetch_brand_kit`/`load_brand_kit`/`apply_brand_kit`, `generate_post`, `generate_campaign`) are wrapped, not reimplemented. `.brand-kits/` and `.social-campaigns/` filesystem roots remain canonical artifact stores; DB rows record metadata + paths. Existing 1136 tests remain green; new `tests/api/` route-level suite adds ≥50 tests using `httpx.AsyncClient` + `respx` + in-memory SQLite.
**Depends on**: Phase 18 (brand_kit), Phase 19 (social), Phase 14 (brochure prompt-driven public API), Phase 4 (flyer public API)
**Requirements**: API-01, API-02, API-03, API-04, API-05, API-06, API-07, API-08, API-09, API-10, API-11, API-12, API-13, API-14, API-15
**Success Criteria** (what must be TRUE):
  1. `flyer_generator/api/__init__.py` exports a FastAPI `app` with versioned `/api/v1` prefix, CORS middleware (origins from `FLYER_CORS_ORIGINS` env, default `["http://localhost:5173"]`), request-ID injection bound into structlog ContextVars, `/docs` and `/redoc` auto-generated from Pydantic models; `uv run uvicorn flyer_generator.api:app --reload` starts cleanly
  2. A single error-to-HTTP mapper translates the existing error hierarchy: `BrandKitNotFoundError → 404`, `BrandKitError` / `FlyerError` / `BrochureError` / `SocialError` / pydantic validation → 400/422, `BrandVoiceViolationError → 422`, `ComfyError` / `VisionAPIError` / `LLMAPIError` → 502, `LLMRateLimitError → 503 (Retry-After)`, all others → 500; every response body is `{detail, error_type, trace_id}`
  3. SQLAlchemy 2.x **async** engine + `async_sessionmaker` in `flyer_generator/api/db.py`; `get_session` FastAPI dependency yields `AsyncSession`; connection URL from `FLYER_DATABASE_URL` env (default `sqlite+aiosqlite:///./flyer.db`); Alembic configured with async-capable `env.py`, `alembic.ini`, and an initial migration that creates all Phase-20 tables
  4. ORM models in `flyer_generator/api/models/`: `BrandKitRecord` (slug PK, source_url, scraped_at, palette/typography/voice JSON), `FlyerRecord`, `BrochureRecord`, `CampaignRecord`, `PostRecord`, `RenderRecord` (id, kind, file_path, comfy_job_id, vision_verdict JSON, created_at), `JobRecord` (ULID id, kind, status enum, started_at, completed_at, error_detail, result_ref, input_payload JSON); relationships: `Campaign 1-N Post`, `Post 1-1 Render`, every creative row 1-1 `Render`
  5. Brand-kit routes in `flyer_generator/api/routes/brand_kits.py`: `POST /api/v1/brand-kits/fetch` (body `{url, slug}` → enqueues `fetch_brand_kit` worker task, returns `{job_id}` 202), `GET /api/v1/brand-kits` (paginated list from DB + filesystem sync), `GET /api/v1/brand-kits/{slug}` (DB row + palette/typography/logos/voice payload)
  6. Flyer route `POST /api/v1/flyers` (body `{event: EventInput, preset, brand_kit_slug?, accent?, max_bg_attempts?}` → enqueues `generate_flyer` worker that calls existing `FlyerGenerator.generate`, writes `FlyerRecord` + `RenderRecord` with the existing PNG path, returns `{job_id}` 202)
  7. Brochure route `POST /api/v1/brochures` (body `{content, template, brand_kit_slug?, generate_images, workflow, style_preset}` → enqueues worker that calls existing `render_schema_brochure` + `generate_template_images`, writes `BrochureRecord` + two `RenderRecord`s (front/back) + PDF path, returns `{job_id}` 202)
  8. Social post route `POST /api/v1/social/posts` (body `{brand_kit_slug, platform, intent, topic, cta?, image_hint?, style_preset?}` → enqueues worker calling `generate_post`, writes `PostRecord` + `RenderRecord`, returns `{job_id}` 202)
  9. Social campaign route `POST /api/v1/social/campaigns` (body `{brand_kit_slug, platforms, intent, topic, cta?, style_preset?}` → enqueues worker calling `generate_campaign`, writes one `CampaignRecord` + N `PostRecord`s + N `RenderRecord`s, returns `{job_id}` 202)
 10. Job polling `GET /api/v1/jobs/{id}` returns `{id, kind, status, started_at, completed_at, error_detail, result_ref}`; `result_ref` is a stable URL path (e.g. `/api/v1/renders/{render_id}/image`) or a list of such URLs for campaigns; status transitions `queued → running → {succeeded, failed, cancelled}` and are persisted on every hop
 11. Render artifact route `GET /api/v1/renders/{id}/image` streams the PNG/PDF from its filesystem path with correct `Content-Type` (`image/png`, `application/pdf`) and `Content-Disposition: inline`; path lookup rejects `..` traversal; renders outside the configured artifact roots (`.brand-kits/`, `.social-campaigns/`, and configurable `FLYER_OUTPUT_ROOT`) return 404
 12. arq worker in `flyer_generator/api/worker.py` with `WorkerSettings` (Redis from `FLYER_REDIS_URL`, default `redis://localhost:6379`), task functions wrap `fetch_brand_kit` / `generate_flyer` / `render_schema_brochure` / `generate_post` / `generate_campaign`, every state transition updates the corresponding `JobRecord` row in a committed transaction; worker boots under `uv run arq flyer_generator.api.worker.WorkerSettings`
 13. `flyer_generator/api/config.py` `AppSettings` (pydantic-settings, `FLYER_` prefix) adds `database_url`, `redis_url`, `cors_origins`, `artifact_root_flyer`, `artifact_root_brochure` on top of the existing `Settings`; reads `.env` at startup; validates at boot (not per-request)
 14. Tests in `tests/api/`: `test_app_smoke.py`, `test_error_mapping.py`, `test_brand_kits_routes.py`, `test_flyer_routes.py`, `test_brochure_routes.py`, `test_social_routes.py`, `test_jobs_routes.py`, `test_renders_routes.py`, `test_worker_tasks.py`. Use `httpx.AsyncClient(transport=ASGITransport(app=app))`, in-memory SQLite fixture (`sqlite+aiosqlite:///:memory:`), in-process arq worker or direct task invocation, `respx` for ComfyCloud / LLM mocks. ≥50 new tests; the existing 1136 tests MUST still pass (`python -m pytest tests/ -q -m "not slow"` → 1186+ passing)
 15. Developer experience: `docker-compose.yml` at repo root with `postgres:16` + `redis:7` services (named `flyer-postgres` + `flyer-redis`), `alembic upgrade head` one-liner, README section "API server (Phase 20)" documenting the two-command boot (`uvicorn` + `arq`), and a `Makefile` or `uv run` recipe `serve` that starts both with aggregated logs
**Plans:** 13/12 plans complete
Plans:
- [x] 20-01-PLAN.md — Dependencies + errors (BrandKitNotFoundError) + logging_config + .gitignore
- [x] 20-02-PLAN.md — AppSettings (flyer_generator/api/config.py) + api package marker
- [x] 20-03-PLAN.md — 7 ORM Records (Base + BrandKit + Flyer + Brochure + Campaign + Post + Render + Job) + DDL smoke test
- [x] 20-04-PLAN.md — flyer_generator/api/db.py + Alembic async init + initial migration + session smoke test
- [x] 20-05-PLAN.md — Pydantic v2 API request/response schemas (12 models across 7 files)
- [x] 20-06-PLAN.md — App factory + lifespan + middleware (CORS + correlation-id) + 8 exception handlers + 6 route stubs + conftest + smoke + error-mapping tests
- [x] 20-07-PLAN.md — arq WorkerSettings + 5 wrapper tasks (brand_kit, flyer, brochure via asyncio.to_thread, post, campaign) + state-transition helpers + direct-invocation tests
- [x] 20-08-PLAN.md — POST /brand-kits/fetch + GET /brand-kits (DB+FS fuse) + GET /brand-kits/{slug} (BrandKitNotFoundError → 404) + tests
- [x] 20-09-PLAN.md — POST /api/v1/flyers + tests (T-6 body-size guard)
- [x] 20-10-PLAN.md — POST /api/v1/brochures + POST /api/v1/social/posts + POST /api/v1/social/campaigns + tests
- [x] 20-11-PLAN.md — GET /api/v1/jobs/{id} (campaign-fusing result_ref) + GET /api/v1/renders/{id}/image (T-1 HIGH path-traversal mitigation) + tests
- [x] 20-12-PLAN.md — docker-compose (postgres:16 + redis:7) + Procfile + Makefile + README "API server" section + regression sweep

### Phase 21: React Frontend Dashboard
**Goal**: A developer can run `cd frontend && pnpm dev` and, against a running Phase 20 API, use a single-page React dashboard to (a) browse brand kits + scrape a new one via URL, (b) fill a flyer form and watch its job progress to a rendered PNG, (c) fill a brochure form and watch its two sheets + PDF render, (d) fill a social post form and watch copy + image + validation report render, (e) fill a campaign form and watch all N platform variants render, (f) browse past renders in a gallery with download + inline preview. Single-user v1 (no login). All dashboard pages use ShadCN components + Tailwind; job status polls Phase 20's `/api/v1/jobs/{id}` endpoint (no WebSocket for v1).
**Depends on**: Phase 20 (FastAPI + SQLAlchemy backend)
**Requirements**: FE-01, FE-02, FE-03, FE-04, FE-05, FE-06, FE-07, FE-08, FE-09, FE-10
**Plans:** 14/14 plans complete
Plans:
- [x] 21-01-PLAN.md -- Vite + React 19 + TS + Tailwind v4 + ShadCN scaffold + CLAUDE.md amendment + README section
- [x] 21-02-PLAN.md -- openapi-typescript codegen + openapi-fetch client.ts + queryKeys.ts registry
- [x] 21-03-PLAN.md -- React Router v7 data-router + Sidebar layout + 404 + ErrorPage + 13 stub pages
- [x] 21-04-PLAN.md -- TanStack Query provider + useJob polling hook + JobStatusCard + RenderPreview + Vitest+msw infra
- [x] 21-05-PLAN.md -- FE-04 Brand Kits (list + detail + scrape) + new BE GET /brand-kits/{slug}/logos/{filename} (T-1 mitigation)
- [x] 21-06-PLAN.md -- FE-05 Flyer creator (typed RHF form mirroring EventInput) + status page
- [x] 21-07-PLAN.md -- FE-06 Brochure creator + 3-artifact status page + BE parallel-id pattern + GET /brochures/{id}
- [x] 21-08-PLAN.md -- FE-07 Social post creator + status page
- [x] 21-09-PLAN.md -- FE-08 Campaign creator (multi-platform Checkbox group) + status page (per-platform grid)
- [x] 21-10-PLAN.md -- FE-09 Jobs page (Table + filters) + new BE GET /api/v1/jobs (paginated)
- [x] 21-11-PLAN.md -- FE-10 Renders gallery + new BE GET /api/v1/renders (paginated)
- [x] 21-12-PLAN.md -- Gap closure: WR-01 (brochure worker workflow key) + WR-03 brochures half (enqueue failure -> FAILED)
- [x] 21-13-PLAN.md -- Gap closure: WR-02 (list_brand_kits dedup + stable total + IN-03 sort) + WR-03 brand-kits half
- [x] 21-14-PLAN.md -- Gap closure: WR-04 (RenderPreview strict .pdf detection + isPdf prop) + IN-01 companion

### Phase 22: Flyer Templates & Subtype Split
**Goal**: A user can render a flyer by picking one of 5+ JSON-defined templates and a subtype (`event` or `info`), and the API, worker, pipeline, database kind enum, and React creator page all honor the selection with event-only fields conditionally hidden for info flyers.
**Depends on**: Phase 21
**Requirements**: FT-01, FT-02, FT-03, FT-04, FT-05, FT-06, FT-07, FT-08
**Success Criteria** (what must be TRUE):
  1. `POST /api/v1/flyers` accepts a required `template` field and a `subtype` field defaulting to `"event"`; submitting with no subtype still produces the same artifact shape the Phase 20 API produced, preserving back-compat
  2. The flyer template registry at `flyer_generator/flyer/schemas/*.json` ships 5+ templates validated by a `FlyerTemplateSchema` Pydantic model, and `PosterComposer.compose()` reads typography scale, scrim opacity, accent placement, and shape mix from the selected template instead of hardcoded values
  3. A user can submit an info flyer with `description` + optional `call_to_action` (no date/venue/fees required), and the Claude vision prompt names TITLE + DESCRIPTION + ORG_CREDIT zones only (no DETAILS or FEE_BADGE) for that subtype
  4. `RenderRecord.kind` stores `flyer_event_final` and `flyer_info_final`; the alembic migration rewrites pre-existing `flyer_final` rows by inspecting `FlyerRecord.event_payload.subtype` (defaulting to `event`)
  5. `/flyers/new` in the FE exposes template and subtype `<Select>`s with event-only fields show/hide conditionally; `/tmp/check-e2e.mjs` submits every template×subtype permutation and the status page renders the PNG; Jobs filter + Renders gallery filter both include `flyer_event_final` and `flyer_info_final`
**Plans:** 7/7 plans complete
Plans:
- [x] 22-01-PLAN.md — Flyer template registry foundation (schema_model + loader + 6 JSON templates + tests) [Wave 1]
- [x] 22-02-PLAN.md — FlyerInput subtype evolution + LayoutZones relaxation + vision subtype-aware prompts [Wave 1]
- [x] 22-03-PLAN.md — PosterComposer template kwarg + typography/scrim/accent extraction + subtype-aware rendering [Wave 2]
- [x] 22-04-PLAN.md — FlyerCreateRequest.template field + FlyerGenerator.generate template kwarg threading [Wave 3]
- [x] 22-05-PLAN.md — FlyerRecord.template column + alembic migration + worker template loading + subtype-derived kind [Wave 4]
- [x] 22-06-PLAN.md — Frontend: OpenAPI regen + template/subtype Selects + conditional fields + gallery KINDS update [Wave 5]
- [x] 22-07-PLAN.md — Permutation test coverage: composer smoke + HTTP permutations + Playwright harness [Wave 6]
**UI hint**: yes

### Phase 23: Postcard Primitive
**Goal**: A user can `POST /api/v1/postcards` and receive a job that produces a front PNG + back PNG + print-ready PDF, then view all three artifacts (plus a recipient address block rendered on the back panel) through the editorial React dashboard.
**Depends on**: Phase 22
**Requirements**: PC-01, PC-02, PC-03, PC-04, PC-05, PC-06
**Success Criteria** (what must be TRUE):
  1. `POST /api/v1/postcards` enqueues a job with the parallel-id pattern (`id == job_id`) and compensating-enqueue transition (`error_detail = {"reason": "enqueue_failed", "type": ...}` — never `str(exc)`); `GET /api/v1/postcards/{id}` returns `PostcardDetail` with 3 artifact URLs
  2. A user can supply an optional `address_block` (recipient name, street, city/state/zip) and the rendered back PNG shows a typographically precise address block in the template's designated region
  3. At least 2 postcard templates (`classic_portrait`, `modern_landscape`) ship at launch; the renderer reuses the brochure SVG + rasterizer stack and the back-PDF path reuses or mirrors `assemble_brochure_pdf`
  4. `/postcards/new` + `/postcards/:id` pages exist with an editorial PageHeader (kicker "08 / THE MAIL"), a sidebar nav entry, and a 3-artifact figure grid mirroring the brochure status page
  5. Jobs filter, router (`statusPathFor`), and Renders gallery filter all include the new `postcard` JobKind and `postcard_front` / `postcard_back` / `postcard_pdf` RenderKinds
**Plans:** 6/6 plans complete
Plans:
- [x] 23-01-PLAN.md — Postcard schema_renderer foundation (PostcardTemplateSchema + loader + 2 JSON templates + tests) [Wave 1]
- [x] 23-02-PLAN.md — Pydantic schemas + PostcardRecord ORM + JobKind.POSTCARD + alembic migration f23t01 [Wave 1]
- [x] 23-03-PLAN.md — PostcardContent + render_postcard renderer + assemble_postcard_pdf [Wave 2]
- [x] 23-04-PLAN.md — task_generate_postcard worker + POST/GET routes + barrels [Wave 3]
- [x] 23-05-PLAN.md — Frontend: OpenAPI regen + creator + status + sidebar nav + Jobs/Renders KINDS additions [Wave 4]
- [x] 23-06-PLAN.md — Render-smoke + HTTP permutation pytest + Playwright e2e harness [Wave 5]
**UI hint**: yes

### Phase 24: Poster Primitive
**Goal**: A user can `POST /api/v1/posters` with a size preset (18×24, 24×36, or 27×40) and a template, and the existing flyer pipeline renders a single print-sized PNG with typography pre-scaled for the larger canvas.
**Depends on**: Phase 22
**Requirements**: PO-01, PO-02, PO-03, PO-04
**Success Criteria** (what must be TRUE):
  1. `POST /api/v1/posters` accepts `size: Literal["18x24", "24x36", "27x40"]` + `template` + flyer-like fields and produces a single PNG output (no PDF); each rendered PNG matches the canvas dimensions derived from its size preset
  2. `FlyerGenerator.__init__` accepts injected canvas dimensions and the poster worker reuses the flyer pipeline (Comfy + vision + composer + rasterizer) end-to-end, with no forked rendering code path
  3. The poster template registry at `flyer_generator/poster/schemas/*.json` ships 3+ templates whose typography scale is tuned for print (headlines sized for 18"+ reading distance)
  4. `/posters/new` exposes size and template `<Select>`s; the status page uses `JobStatusCard` directly; a sidebar nav entry is added; Jobs filter + Renders gallery filter both include `poster` and `poster_final`
**Plans:** 6/6 plans complete
Plans:
- [x] 24-01-PLAN.md — Poster schema_renderer foundation (PosterTemplateSchema + loader + 3 JSON templates) [Wave 1]
- [x] 24-02-PLAN.md — FlyerGenerator pipeline refactor (canvas_dimensions kwarg, non-breaking) [Wave 1]
- [x] 24-03-PLAN.md — API schemas + PosterRecord ORM + JobKind.POSTER + alembic f24t01 [Wave 1]
- [x] 24-04-PLAN.md — Worker (task_generate_poster) + POST /api/v1/posters route [Wave 2]
- [x] 24-05-PLAN.md — Frontend creator + status + nav + Jobs/Renders KINDS additions [Wave 3]
- [x] 24-06-PLAN.md — 9-permutation render-smoke + HTTP perms + Playwright harness [Wave 4]
**UI hint**: yes

### Phase 24.1: perception-loop-fixes (INSERTED)

**Goal:** Fix 4 cross-phase bugs surfaced by the 2026-04-25 perception loop run (`/tmp/perception/PERCEPTION-REPORT.md`). Postcards must render `body` text and produce an AI image from `image_hint` (not `[ hero ]` placeholder). Brochures must render the supplied `content.sections` with no hardcoded "ESTATE PLANNING" kicker, and `generate_images: true` must actually invoke Comfy. Flyer `bold_modern` template must not collide its detail text against the headline. Poster vision pipeline must downsample the background before sending to the LLM so 5400×7200 PNGs no longer time out the upload window.
**Requirements**: PLF-01, PLF-02, PLF-03, PLF-04
**Success Criteria** (what must be TRUE):
  1. `POST /api/v1/postcards` with `body` and `image_hint` produces a render where the body text is visible AND a Comfy-generated image fills the hero area (no `[ hero ]` placeholder); both `classic_portrait` and `modern_landscape` templates honor body + image_hint
  2. `POST /api/v1/brochures` with `content.sections=[...]` and `generate_images: true` produces a render where every supplied section's heading + body_paragraphs are visible, the kicker matches the brief (not the hardcoded "ESTATE PLANNING"), and the hero panel is a real Comfy-generated image
  3. `POST /api/v1/flyers` with `template="bold_modern"` produces a render where the headline and the date/time/venue text do not visually overlap; the layout-collision pytest catches the overlap (RED→GREEN)
  4. `POST /api/v1/posters` with any size completes successfully end-to-end on a 100Mbps consumer connection within `FLYER_VISION_TIMEOUT_SECONDS=60`; vision input is downsampled (e.g., to ≤1920px on long edge) before base64-encoding for the LLM call; the existing 9 render-smoke pytests still pass
**Depends on:** Phase 24
**Plans:** 4/4 plans complete

Plans:
- [x] 24.1-01-PLAN.md — Postcard Comfy generation + body text rendering (PLF-01) [Wave 1]
- [x] 24.1-02-PLAN.md — Brochure sections + kicker derivation + generate_images wiring (PLF-02) [Wave 1]
- [x] 24.1-03-PLAN.md — Poster vision input downsampling (PLF-04) [Wave 1]
- [x] 24.1-04-PLAN.md — Flyer bold_modern z-order layout fix (PLF-03) [Wave 1]

### Phase 24.2: renders-management (INSERTED)

**Goal:** Two cross-cutting render-related fixes/features. (1) Fix the print PDF page-size bug discovered via the post-Phase 24.1 perception loop: brochure tri-fold PDF outputs at 46.89×36.47in instead of the correct 11.25×8.75in (postcard PDFs have the same bug — 16.67×25in instead of 4×6in) because both `flyer_generator/{brochure,postcard}/stages/pdf.py` pass 300dpi pixel dimensions directly to reportlab's Canvas which interprets them as PostScript points. (2) Add a delete capability to the Renders gallery: backend DELETE `/api/v1/renders/{id}` endpoint + frontend trash-icon button with confirmation modal in `frontend/src/pages/renders/gallery.tsx`.
**Requirements**: RM-01, RM-02
**Success Criteria** (what must be TRUE):
  1. Brochure PDF artifacts have page size 11.25×8.75in (not 46.89×36.47in); postcard PDF artifacts have page size 4×6in or 6×4in depending on template orientation (not 16.67×25in or 25×16.67in); pdf metadata inspectable via `pypdf.PdfReader` confirms; existing pytest coverage extended to assert page dimensions in inches/points
  2. `DELETE /api/v1/renders/{render_id}` returns 204 on success; returns 404 if render does not exist; deletes the underlying RenderRecord row + the on-disk PNG/PDF file at `<artifact_root>/.../<render_id>.{png,pdf}`; idempotent on re-delete
  3. Renders gallery shows a trash icon on every card; clicking opens a confirmation modal ("Delete render? This cannot be undone."); confirming triggers DELETE + optimistic refresh of the list; rejected renders stay visible until backend confirms
  4. No regressions: 1787 backend pytests + 43 frontend tests still pass; OpenAPI snapshot regenerated to expose the DELETE route + typed client alias
**Depends on:** Phase 24.1
**Plans:** 2/2 plans complete

Plans:
- [x] 24.2-01-PLAN.md — Postcard + brochure PDF page-size fix (RM-01) [Wave 1]
- [x] 24.2-02-PLAN.md — Render delete capability: DELETE route + FE trash icon (RM-02) [Wave 1]

### Phase 25: Invitation Primitive
**Goal**: A user can `POST /api/v1/invitations` with RSVP-focused fields (host, event, date, time, venue, RSVP contact) and a brand kit, and the API returns a 5×7 portrait invitation PNG at 300 DPI rendered through one of three visually-distinct templates.
**Depends on**: Phase 22
**Requirements**: IN-01, IN-02, IN-03, IN-04
**Success Criteria** (what must be TRUE):
  1. `POST /api/v1/invitations` produces a 1500×2100 PNG (5×7 inches @ 300 DPI) with heavy brand-kit conditioning on palette, typography, and logo placement
  2. The invitation request schema accepts `host_name`, `event_title`, `event_date`, `event_time`, `venue`, `rsvp_contact`, optional `rsvp_deadline`, `brand_kit_slug`, and `template`
  3. At least 3 invitation templates (`classic_serif`, `modern_sans`, `ornamental`) ship at launch, and rendering the same content through each template produces visually distinct output
  4. `/invitations/new` + `/invitations/:id` pages exist with a distinct RSVP-focused form layout (no style-preset picker; strong brand-kit coupling); Jobs filter + Renders gallery filter both include `invitation` and `invitation_final`
**Plans:** 0/? (not yet planned)
**UI hint**: yes

### Phase 26: Adversarial Hardening Sweep
**Goal**: Every asset primitive in the catalog (flyer event/info, brochure, postcard, poster, invitation, social post, social campaign, brand kit) is covered by a dedicated adversarial test suite that regresses prompt injection, path traversal, unicode stress, oversize payloads, PDF bombs, concurrent enqueue, and visual regression.
**Depends on**: Phase 22, Phase 23, Phase 24, Phase 25
**Requirements**: ADV-01, ADV-02, ADV-03, ADV-04, ADV-05, ADV-06, ADV-07
**Success Criteria** (what must be TRUE):
  1. A prompt-injection regression suite feeds known-malicious strings into every field routed to Claude vision or LLM text gen (`EventInput.title`, `BrochureContent.*`, `PostCreateRequest.topic`, etc.) and asserts the structured verdict schema is preserved and no injected directive alters the output contract
  2. A path-traversal regression suite exercises every slug/id path-param (`/brand-kits/{slug}/logos/{filename}`, `/renders/{id}/image`, `/brochures/{id}`, `/postcards/{id}`) with `../../`, URL-encoded, and null-byte variants; every response is 404 or 422, never a 200 that leaks a file outside the configured artifact roots
  3. Unicode/emoji stress tests render zalgo, RTL, mixed scripts, and emoji-cluster content through every primitive's text fields without crash, layout break, or byte-serialization error; oversize-payload tests return 422 cleanly at `max+1` without server-side truncation
  4. A synthesized pathological SVG (nested groups, recursive filters, enormous paths) causes the rasterizer to fail fast (<30 seconds) with a typed error, and a concurrent-enqueue load test (100 jobs via `asyncio.gather`) lands all jobs as `queued` with no DB deadlocks or dropped jobs
  5. A visual-regression suite renders each primitive with a fixed seed and asserts SHA-256 match (or SSIM > 0.99) against reference snapshots committed under `tests/adversarial/snapshots/`; reference updates require an explicit snapshot refresh step (not silent acceptance)
**Plans:** 0/? (not yet planned)

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
| 19. Social Media Posting System | 9/9 | Complete   | 2026-04-21 |
| 20. FastAPI + SQLAlchemy Backend | 13/12 | Complete   | 2026-04-22 |
| 21. React Frontend Dashboard | 14/14 | Complete   | 2026-04-23 |
| 22. Flyer Templates & Subtype Split | 7/7 | Complete    | 2026-04-25 |
| 23. Postcard Primitive | 6/6 | Complete    | 2026-04-25 |
| 24. Poster Primitive | 6/6 | Complete    | 2026-04-25 |
| 25. Invitation Primitive | 0/? | Not Started | - |
| 26. Adversarial Hardening Sweep | 0/? | Not Started | - |
