# Requirements: Flyer Generator

**Defined:** 2026-04-16
**Core Value:** Given structured event data and a style preset, produce a polished 1080x1920 event flyer with AI-generated artwork and intelligently placed text — every time, without manual design work.

## v1 Requirements

### Foundation

- [x] **FOUND-01**: Project uses Python 3.11+ with uv for dependency management and pyproject.toml config
- [x] **FOUND-02**: All cross-stage data contracts defined as Pydantic v2 models (EventInput, ComfyJob, GeneratedBackground, VisionVerdict, LayoutZones, ResolvedLayout, FlyerOutput)
- [x] **FOUND-03**: Configuration loaded from environment variables via Pydantic Settings with FLYER_ prefix
- [x] **FOUND-04**: Typed exception hierarchy covering every failure mode (ComfyError, VisionError, CompositionError, RasterizationError, MaxAttemptsExceededError)
- [x] **FOUND-05**: Six built-in style presets registered (photorealistic, anime, western_cartoon, scifi, watercolor, retro_poster) with exact prompt text from n8n workflow

### Image Generation

- [ ] **IGEN-01**: StylePromptBuilder composes positive/negative prompts from preset + event concept + optional refinement hint
- [ ] **IGEN-02**: ComfyClient submits workflow JSON to ComfyCloud API with X-API-Key header
- [ ] **IGEN-03**: ComfyClient polls job status with configurable interval and max attempts, with exponential backoff on 5xx
- [ ] **IGEN-04**: ComfyClient downloads result image via history_v2 + view endpoints
- [ ] **IGEN-05**: ImagePreprocessor upscales 832x1472 to 1080x1920 using Pillow LANCZOS

### Vision Evaluation

- [ ] **VISN-01**: VisionEvaluator sends background + event context to Claude in a single API call
- [ ] **VISN-02**: Vision response parsed into VisionVerdict with approved, confidence, zones, text_color, rejection_reasons
- [ ] **VISN-03**: Confidence gate flips approved to False when confidence < configurable threshold (default 0.6)
- [ ] **VISN-04**: Parse failure triggers one retry with "return valid JSON only" follow-up prompt
- [ ] **VISN-05**: Zone validation rejects approved verdicts with null or invalid zone names

### Composition

- [ ] **COMP-01**: LayoutResolver maps zone labels (TOP_LEFT, MIDDLE_CENTER, etc.) to pixel coordinates and text anchors on 1080x1920 canvas
- [ ] **COMP-02**: PosterComposer generates SVG with base64-embedded background image
- [ ] **COMP-03**: Title auto-sized by length with word-wrap and widow-line merge
- [ ] **COMP-04**: Text color (white/dark) and stroke applied from vision verdict
- [ ] **COMP-05**: Zone-specific scrim gradients applied only to zones used by title/details
- [ ] **COMP-06**: Fee badge rendered as pill shape with dynamic width clamped [140, 400]
- [ ] **COMP-07**: Accent line under title and accent stripe at bottom from event color_accent
- [ ] **COMP-08**: All user-supplied strings XML-escaped before SVG insertion
- [ ] **COMP-09**: Rasterizer converts SVG to 1080x1920 PNG via cairosvg with dimension sanity check

### Pipeline

- [ ] **PIPE-01**: FlyerGenerator orchestrates all stages in sequence with regeneration loop on vision rejection
- [ ] **PIPE-02**: Regeneration loop runs up to max_bg_attempts (default 3), feeding refinement hints back to prompt builder
- [ ] **PIPE-03**: Each pipeline run generates a trace_id (UUID4) for log correlation
- [ ] **PIPE-04**: Structured logging with structlog emitting key events (attempt_start, comfy_submitted, vision_approved/rejected, flyer_generated)

### CLI & API

- [ ] **CLI-01**: CLI entrypoint via `python -m flyer_generator` with full argument support (title, date, time, venue, address, fees, org, concept, preset, accent, output)
- [ ] **CLI-02**: `--event-json` flag loads EventInput from JSON file
- [ ] **CLI-03**: `--list-presets` enumerates available style presets
- [ ] **CLI-04**: `--dry-run` builds prompt and prints without calling ComfyCloud
- [ ] **CLI-05**: Public API exports generate_flyer(), FlyerGenerator, EventInput, FlyerOutput, PresetRegistry, StylePreset, and key exceptions
- [ ] **CLI-06**: Custom preset registration via PresetRegistry before calling generate_flyer()

## v2 Requirements

### Extensibility

- **EXT-01**: resvg-py fallback rasterizer when cairosvg has issues
- **EXT-02**: Alternative image backend support (local ComfyUI, Replicate, fal.ai)
- **EXT-03**: S3/cloud output via FlyerOutput.save_to_s3()
- **EXT-04**: FastAPI wrapper endpoint for generate_flyer()

### Quality

- **QUAL-01**: Batch generation orchestration
- **QUAL-02**: Font diversity beyond Arial/Helvetica
- **QUAL-03**: Multi-language / RTL / CJK text layout
- **QUAL-04**: Image content safety / NSFW detection stage

## Out of Scope

| Feature | Reason |
|---------|--------|
| Web UI | Wrap with FastAPI separately; this is a library + CLI |
| Batch orchestration | Design permits it but lives in a separate layer |
| Alternative image models | Extension point exists but only ComfyCloud implemented in v1 |
| Animation / video | Different output pipeline entirely |
| Font management | cairosvg font config is complex; Arial/Helvetica sufficient for v1 |
| Caching | Belongs at a higher layer if needed |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FOUND-01 | Phase 1 | Complete |
| FOUND-02 | Phase 1 | Complete |
| FOUND-03 | Phase 1 | Complete |
| FOUND-04 | Phase 1 | Complete |
| FOUND-05 | Phase 1 | Complete |
| IGEN-01 | Phase 2 | Pending |
| IGEN-02 | Phase 2 | Pending |
| IGEN-03 | Phase 2 | Pending |
| IGEN-04 | Phase 2 | Pending |
| IGEN-05 | Phase 2 | Pending |
| VISN-01 | Phase 2 | Pending |
| VISN-02 | Phase 2 | Pending |
| VISN-03 | Phase 2 | Pending |
| VISN-04 | Phase 2 | Pending |
| VISN-05 | Phase 2 | Pending |
| COMP-01 | Phase 3 | Pending |
| COMP-02 | Phase 3 | Pending |
| COMP-03 | Phase 3 | Pending |
| COMP-04 | Phase 3 | Pending |
| COMP-05 | Phase 3 | Pending |
| COMP-06 | Phase 3 | Pending |
| COMP-07 | Phase 3 | Pending |
| COMP-08 | Phase 3 | Pending |
| COMP-09 | Phase 3 | Pending |
| PIPE-01 | Phase 4 | Pending |
| PIPE-02 | Phase 4 | Pending |
| PIPE-03 | Phase 4 | Pending |
| PIPE-04 | Phase 4 | Pending |
| CLI-01 | Phase 4 | Pending |
| CLI-02 | Phase 4 | Pending |
| CLI-03 | Phase 4 | Pending |
| CLI-04 | Phase 4 | Pending |
| CLI-05 | Phase 4 | Pending |
| CLI-06 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 34 total
- Mapped to phases: 34
- Unmapped: 0

---
*Requirements defined: 2026-04-16*
*Last updated: 2026-04-16 after roadmap creation*
