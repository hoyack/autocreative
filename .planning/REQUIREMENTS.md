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

- [x] **IGEN-01**: StylePromptBuilder composes positive/negative prompts from preset + event concept + optional refinement hint
- [x] **IGEN-02**: ComfyClient submits workflow JSON to ComfyCloud API with X-API-Key header
- [x] **IGEN-03**: ComfyClient polls job status with configurable interval and max attempts, with exponential backoff on 5xx
- [x] **IGEN-04**: ComfyClient downloads result image via history_v2 + view endpoints
- [x] **IGEN-05**: ImagePreprocessor upscales 832x1472 to 1080x1920 using Pillow LANCZOS

### Vision Evaluation

- [x] **VISN-01**: VisionEvaluator sends background + event context to Claude in a single API call
- [x] **VISN-02**: Vision response parsed into VisionVerdict with approved, confidence, zones, text_color, rejection_reasons
- [x] **VISN-03**: Confidence gate flips approved to False when confidence < configurable threshold (default 0.6)
- [x] **VISN-04**: Parse failure triggers one retry with "return valid JSON only" follow-up prompt
- [x] **VISN-05**: Zone validation rejects approved verdicts with null or invalid zone names

### Composition

- [x] **COMP-01**: LayoutResolver maps zone labels (TOP_LEFT, MIDDLE_CENTER, etc.) to pixel coordinates and text anchors on 1080x1920 canvas
- [x] **COMP-02**: PosterComposer generates SVG with base64-embedded background image
- [x] **COMP-03**: Title auto-sized by length with word-wrap and widow-line merge
- [x] **COMP-04**: Text color (white/dark) and stroke applied from vision verdict
- [x] **COMP-05**: Zone-specific scrim gradients applied only to zones used by title/details
- [x] **COMP-06**: Fee badge rendered as pill shape with dynamic width clamped [140, 400]
- [x] **COMP-07**: Accent line under title and accent stripe at bottom from event color_accent
- [x] **COMP-08**: All user-supplied strings XML-escaped before SVG insertion
- [x] **COMP-09**: Rasterizer converts SVG to 1080x1920 PNG via cairosvg with dimension sanity check

### Pipeline

- [x] **PIPE-01**: FlyerGenerator orchestrates all stages in sequence with regeneration loop on vision rejection
- [x] **PIPE-02**: Regeneration loop runs up to max_bg_attempts (default 3), feeding refinement hints back to prompt builder
- [x] **PIPE-03**: Each pipeline run generates a trace_id (UUID4) for log correlation
- [x] **PIPE-04**: Structured logging with structlog emitting key events (attempt_start, comfy_submitted, vision_approved/rejected, flyer_generated)

### CLI & API

- [x] **CLI-01**: CLI entrypoint via `python -m flyer_generator` with full argument support (title, date, time, venue, address, fees, org, concept, preset, accent, output)
- [x] **CLI-02**: `--event-json` flag loads EventInput from JSON file
- [x] **CLI-03**: `--list-presets` enumerates available style presets
- [x] **CLI-04**: `--dry-run` builds prompt and prints without calling ComfyCloud
- [x] **CLI-05**: Public API exports generate_flyer(), FlyerGenerator, EventInput, FlyerOutput, PresetRegistry, StylePreset, and key exceptions
- [x] **CLI-06**: Custom preset registration via PresetRegistry before calling generate_flyer()

### Social Media Posting (Phase 19)

- [ ] **SOC-01**: `from flyer_generator.social import PostSpec, Post, Platform, generate_post, generate_campaign, load_platform_rules, validate_post` succeeds; all models Pydantic v2 and JSON round-trip
- [ ] **SOC-02**: Four platform rule registries implemented with typed `PlatformRules` — LinkedIn (3000-char body, 1200×627 or 1200×1200 image), Twitter/X (280-char text, up to 4 images 1200×675), Instagram (2200-char caption, ≤30 hashtags, 1080×1080/1080×1350/1080×1920), Facebook (text + 1200×630 link preview / 1080×1080 feed); each ships `validate(post) → ValidationReport` with per-rule pass/fail
- [ ] **SOC-03**: ≥12 post templates (3 intents × 4 platforms) under `flyer_generator/social/schemas/`; each declares `{platform, intent, aspect, text_budgets, image_slots, layout}` mirroring `schema_renderer` template shape; SVG rasterization reuses `schema_renderer` pipeline
- [ ] **SOC-04**: `BrandVoice` (tone, example_phrases, banned_words) from Phase 18 wired into `text_gen.generate_content_from_prompt` as `brand_voice: BrandVoice | None = None`; prompt injects tone + banned-word constraint; generated copy validated against `banned_words` (case-insensitive word-boundary) with one retry then raises `BrandVoiceViolationError`
- [ ] **SOC-05**: `generate_post(brand_kit_slug, PostBrief) → Post` orchestrates: select template → generate copy via voice-aware text_gen → (if image slot) generate hero via ComfyCloud using brand palette + aspect → render SVG → rasterize → audit; returns `Post(platform, intent, copy, hashtags, image_bytes|None, validation_report, audit_report)`
- [ ] **SOC-06**: `generate_campaign(brand_kit_slug, topic, platforms) → Campaign` generates ONE source hero at largest-requested resolution (2048×2048 after Pillow-LANCZOS upscale), crops per-platform via `ImageOps.fit`; copy regenerated per-platform (not truncated) to respect per-platform voice/budget
- [ ] **SOC-07**: `audit_post` extends Phase 18's `audit_render` with platform-specific dimensions: char-count vs budget, hashtag count/length, image aspect match (±2%), image file size vs platform cap, link presence vs link-support (Instagram warn on URL in caption), Flesch-Kincaid-ish readability warn at grade > 12, plus all existing contrast + density + whitespace checks
- [ ] **SOC-08**: CLI `python -m flyer_generator.social {post,campaign,list-platforms,list-intents,show-rules}` works end-to-end against existing brand kits (shrubnet, hoyack, thunderstaff)
- [ ] **SOC-09**: Untracked storage `.social-campaigns/<slug>/<campaign-id>/` — per-post JSON + image bytes + audit sidecar; `.social-campaigns/` in `.gitignore`; `.social-template.json` tracked as schema reference; `FLYER_SOCIAL_CAMPAIGNS_DIR` env var honored with path-traversal containment
- [ ] **SOC-10**: Tests cover platform validators (all 4 × pass/fail), BrandVoice wiring (tone injection, banned-word filter + retry + raise), post templates (≥12 validate shape + render), generator (mocked LLM + Comfy), campaign (shared hero cropped correctly per-platform), audit (platform-rule coverage), CLI (post + campaign + list + show); all net-new tests green in < 5 min
- [ ] **SOC-11**: Publishing/scheduling EXPLICITLY out of scope — Phase 19 produces artifacts only; no LinkedIn API / Twitter API / Meta Graph / scheduler integration

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
| IGEN-01 | Phase 2 | Complete |
| IGEN-02 | Phase 2 | Complete |
| IGEN-03 | Phase 2 | Complete |
| IGEN-04 | Phase 2 | Complete |
| IGEN-05 | Phase 2 | Complete |
| VISN-01 | Phase 2 | Complete |
| VISN-02 | Phase 2 | Complete |
| VISN-03 | Phase 2 | Complete |
| VISN-04 | Phase 2 | Complete |
| VISN-05 | Phase 2 | Complete |
| COMP-01 | Phase 3 | Complete |
| COMP-02 | Phase 3 | Complete |
| COMP-03 | Phase 3 | Complete |
| COMP-04 | Phase 3 | Complete |
| COMP-05 | Phase 3 | Complete |
| COMP-06 | Phase 3 | Complete |
| COMP-07 | Phase 3 | Complete |
| COMP-08 | Phase 3 | Complete |
| COMP-09 | Phase 3 | Complete |
| PIPE-01 | Phase 4 | Complete |
| PIPE-02 | Phase 4 | Complete |
| PIPE-03 | Phase 4 | Complete |
| PIPE-04 | Phase 4 | Complete |
| CLI-01 | Phase 4 | Complete |
| CLI-02 | Phase 4 | Complete |
| CLI-03 | Phase 4 | Complete |
| CLI-04 | Phase 4 | Complete |
| CLI-05 | Phase 4 | Complete |
| CLI-06 | Phase 4 | Complete |
| SOC-01 | Phase 19 | Not Started |
| SOC-02 | Phase 19 | Not Started |
| SOC-03 | Phase 19 | Not Started |
| SOC-04 | Phase 19 | Not Started |
| SOC-05 | Phase 19 | Not Started |
| SOC-06 | Phase 19 | Not Started |
| SOC-07 | Phase 19 | Not Started |
| SOC-08 | Phase 19 | Not Started |
| SOC-09 | Phase 19 | Not Started |
| SOC-10 | Phase 19 | Not Started |
| SOC-11 | Phase 19 | Not Started |

**Coverage:**
- v1 requirements: 34 total + 11 Phase 19 = 45 total
- Mapped to phases: 45
- Unmapped: 0

---
*Requirements defined: 2026-04-16*
*Last updated: 2026-04-21 after Phase 19 SOC-* additions*
