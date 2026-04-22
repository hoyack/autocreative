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

### FastAPI + SQLAlchemy Backend (Phase 20)

- [ ] **API-01**: FastAPI `app` instance in `flyer_generator/api/__init__.py` with `/api/v1` versioned prefix, CORS middleware (origins from `FLYER_CORS_ORIGINS` env, default `http://localhost:5173`), request-ID middleware binding `trace_id` into structlog ContextVars, auto-generated `/docs` and `/redoc` powered by existing Pydantic v2 models; `uv run uvicorn flyer_generator.api:app --reload` boots cleanly
- [ ] **API-02**: Single error-to-HTTPException mapper — `BrandKitNotFoundError → 404`, `BrandKitError` / `FlyerError` / `BrochureError` / `SocialError` / `ValidationError` → 400/422, `BrandVoiceViolationError → 422`, `ComfyError` / `VisionAPIError` / `LLMAPIError` → 502, `LLMRateLimitError → 503 (sets Retry-After header)`, everything else → 500; every response body is `{detail, error_type, trace_id}` for client debugging
- [ ] **API-03**: SQLAlchemy 2.x **async** engine + `async_sessionmaker` in `flyer_generator/api/db.py`; `get_session` FastAPI dependency yields `AsyncSession` per request; connection URL from `FLYER_DATABASE_URL` (default `sqlite+aiosqlite:///./flyer.db`); Alembic configured with async-capable `env.py`, `alembic.ini`, and an initial migration that creates every Phase-20 table
- [ ] **API-04**: ORM models under `flyer_generator/api/models/` — `BrandKitRecord` (slug PK, source_url, scraped_at, palette/typography/voice JSON columns), `FlyerRecord`, `BrochureRecord`, `CampaignRecord`, `PostRecord`, `RenderRecord` (id PK, kind enum, file_path, comfy_job_id, vision_verdict JSON, created_at), `JobRecord` (ULID PK, kind enum, status enum, started_at, completed_at, error_detail, result_ref, input_payload JSON); relationships: `Campaign 1-N Post`, each creative row 1-1 `Render`, `Job 1-1` (polymorphic) to the creative row it produced
- [ ] **API-05**: Brand-kit routes in `flyer_generator/api/routes/brand_kits.py` — `POST /api/v1/brand-kits/fetch` (body `{url, slug}`, enqueues `fetch_brand_kit` worker task, returns `{job_id}` 202), `GET /api/v1/brand-kits` (paginated list fused from DB + filesystem for migration grace), `GET /api/v1/brand-kits/{slug}` (detail row with palette/typography/logos/voice fields)
- [ ] **API-06**: Flyer route `POST /api/v1/flyers` (body `{event: EventInput, preset, brand_kit_slug?, accent?, max_bg_attempts?}`, enqueues worker that calls existing `FlyerGenerator.generate`, writes `FlyerRecord` + `RenderRecord`, returns `{job_id}` 202); reuses existing `EventInput` Pydantic model as the request schema
- [ ] **API-07**: Brochure route `POST /api/v1/brochures` (body `{content, template, brand_kit_slug?, generate_images, workflow, style_preset}`, enqueues worker calling `render_schema_brochure` + `generate_template_images`, writes `BrochureRecord` + two `RenderRecord`s (front/back) + PDF path, returns `{job_id}` 202)
- [ ] **API-08**: Social post route `POST /api/v1/social/posts` (body `{brand_kit_slug, platform, intent, topic, cta?, image_hint?, style_preset?}`, enqueues worker calling `generate_post`, writes `PostRecord` + `RenderRecord`, returns `{job_id}` 202)
- [ ] **API-09**: Social campaign route `POST /api/v1/social/campaigns` (body `{brand_kit_slug, platforms, intent, topic, cta?, style_preset?}`, enqueues worker calling `generate_campaign`, writes one `CampaignRecord` + N `PostRecord`s + N `RenderRecord`s for the shared hero + per-platform crops, returns `{job_id}` 202)
- [ ] **API-10**: Job polling `GET /api/v1/jobs/{id}` returns `{id, kind, status, started_at, completed_at, error_detail, result_ref}` where `result_ref` is a stable `/api/v1/renders/{render_id}/image` URL (single render) or `[{platform, url}]` (campaign); worker transitions `queued → running → {succeeded, failed, cancelled}` and every hop commits to `JobRecord`
- [ ] **API-11**: Render artifact route `GET /api/v1/renders/{id}/image` streams the PNG / PDF from its filesystem path with correct `Content-Type` and `Content-Disposition: inline`; path lookup rejects `..` / symlink traversal; renders outside configured roots (`.brand-kits/`, `.social-campaigns/`, `FLYER_OUTPUT_ROOT`) return 404 regardless of DB state
- [ ] **API-12**: arq worker in `flyer_generator/api/worker.py` with `WorkerSettings` (Redis from `FLYER_REDIS_URL`, default `redis://localhost:6379`), task functions wrap `fetch_brand_kit` / `generate_flyer` / `render_schema_brochure` / `generate_post` / `generate_campaign`; every state transition updates the corresponding `JobRecord` row in a committed transaction; worker boots under `uv run arq flyer_generator.api.worker.WorkerSettings`
- [ ] **API-13**: `flyer_generator/api/config.py` `AppSettings` (pydantic-settings, `FLYER_` prefix) adds `database_url`, `redis_url`, `cors_origins`, `artifact_root_flyer`, `artifact_root_brochure`, `artifact_root_brand_kit` on top of the existing `Settings`; reads `.env` at startup; validates at boot (not per-request)
- [ ] **API-14**: Tests in `tests/api/` — `test_app_smoke.py`, `test_error_mapping.py`, `test_brand_kits_routes.py`, `test_flyer_routes.py`, `test_brochure_routes.py`, `test_social_routes.py`, `test_jobs_routes.py`, `test_renders_routes.py`, `test_worker_tasks.py` — using `httpx.AsyncClient(transport=ASGITransport(app=app))`, in-memory SQLite (`sqlite+aiosqlite:///:memory:`) fixture, in-process arq or direct task invocation, `respx` for ComfyCloud + LLM mocks; ≥50 new tests green, existing 1136 tests MUST remain green (target `python -m pytest tests/ -q -m "not slow"` → 1186+ passing)
- [ ] **API-15**: Developer experience — `docker-compose.yml` at repo root with `postgres:16` + `redis:7` services (named `flyer-postgres` + `flyer-redis`), an `alembic upgrade head` one-liner, README "API server (Phase 20)" section documenting the two-command boot (`uvicorn` + `arq`), and a `uv run` recipe `serve` that starts both with aggregated logs

### React Frontend Dashboard (Phase 21 — stub)

- [ ] **FE-01**: React + Vite + TypeScript + ShadCN + Tailwind project under `frontend/`; `pnpm dev` boots; `pnpm build` emits a production bundle
- [ ] **FE-02**: Typed API client generated from Phase 20's OpenAPI schema (e.g. via `openapi-typescript`) living at `frontend/src/api/`; dev proxy to `http://localhost:8000/api/v1`
- [ ] **FE-03**: Dashboard shell with sidebar navigation for Brand Kits / Flyers / Brochures / Social / Campaigns / Jobs / Renders; uses ShadCN `Sheet` + `NavigationMenu` components
- [ ] **FE-04**: Brand Kits page — list view with cards, detail view with palette swatches + typography sample + scraped logo gallery, "Add" modal that POSTs to `/brand-kits/fetch` and tails the job
- [ ] **FE-05**: Flyer creator page — typed form matching `EventInput`, preset picker, brand-kit picker, submit → job polling UI → rendered PNG preview + download
- [ ] **FE-06**: Brochure creator page — content JSON editor (schema-driven form), template picker, preset picker, brand-kit picker, submit → job polling → front/back PNG + PDF preview
- [ ] **FE-07**: Social post creator — platform / intent / topic / CTA / image_hint inputs + brand-kit + style-preset, submit → job polling → copy preview + image preview + validation report + audit report
- [ ] **FE-08**: Campaign creator — topic / platforms multi-select / intent / brand-kit / style-preset, submit → job polling → per-platform result grid with shared source hero
- [ ] **FE-09**: Jobs page — global list of every job with filtering by status + kind, click-through to the originating creative; row-level status polling via `/jobs/{id}`
- [ ] **FE-10**: Renders gallery — grid of all renders across all kinds, download button, inline preview (PNG inline, PDF via object tag); filter by kind + date

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
| API-01 | Phase 20 | Not Started |
| API-02 | Phase 20 | Not Started |
| API-03 | Phase 20 | Not Started |
| API-04 | Phase 20 | Not Started |
| API-05 | Phase 20 | Not Started |
| API-06 | Phase 20 | Not Started |
| API-07 | Phase 20 | Not Started |
| API-08 | Phase 20 | Not Started |
| API-09 | Phase 20 | Not Started |
| API-10 | Phase 20 | Not Started |
| API-11 | Phase 20 | Not Started |
| API-12 | Phase 20 | Not Started |
| API-13 | Phase 20 | Not Started |
| API-14 | Phase 20 | Not Started |
| API-15 | Phase 20 | Not Started |
| FE-01 | Phase 21 | Not Started |
| FE-02 | Phase 21 | Not Started |
| FE-03 | Phase 21 | Not Started |
| FE-04 | Phase 21 | Not Started |
| FE-05 | Phase 21 | Not Started |
| FE-06 | Phase 21 | Not Started |
| FE-07 | Phase 21 | Not Started |
| FE-08 | Phase 21 | Not Started |
| FE-09 | Phase 21 | Not Started |
| FE-10 | Phase 21 | Not Started |

**Coverage:**
- v1 requirements: 34 + Phase 19 (11) + Phase 20 (15) + Phase 21 (10) = 70 total
- Mapped to phases: 70
- Unmapped: 0

---
*Requirements defined: 2026-04-16*
*Last updated: 2026-04-22 after Phase 20 API-* and Phase 21 FE-* additions*
