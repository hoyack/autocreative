# Roadmap: Flyer Generator

## Overview

This roadmap delivers an AI-powered event flyer generator in 4 phases, progressing from data contracts through image generation, visual composition, and finally pipeline orchestration with CLI exposure. Each phase delivers a coherent, testable capability that builds on the previous. The structure follows the natural data flow of the pipeline: define contracts, generate images, compose flyers, wire and expose.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation** - Data contracts, configuration, error hierarchy, style presets, and project scaffolding
- [x] **Phase 2: Image Pipeline** - AI background generation via ComfyCloud and vision evaluation via Claude (completed 2026-04-17)
- [x] **Phase 3: Composition** - Layout resolution, SVG composition with text overlays, and PNG rasterization (completed 2026-04-17)
- [ ] **Phase 4: Orchestration & CLI** - Pipeline wiring with retry loop, CLI entrypoint, and public API surface

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

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 2/2 | Complete | 2026-04-16 |
| 2. Image Pipeline | 3/3 | Complete   | 2026-04-17 |
| 3. Composition | 2/2 | Complete   | 2026-04-17 |
| 4. Orchestration & CLI | 0/TBD | Not started | - |
