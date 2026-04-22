# Flyer / Brochure / Social / Brand Kit — Session Handoff

**For a fresh session after `/clear`.** Full state-of-the-world for the autocreative repo after Phase 19 (Social Media Posts) + 7 post-Phase-19 fixes + a cross-asset hoyack gallery + a brochure workflow adversarial battery.

---

## 1. Quick orientation

- **Branch:** `master`, clean tree (untracked: `.claude/`, `docs/brochure-gallery-plan.md`, `docs/brochure-templates/`, `docs/workflows-pending/` — none to worry about).
- **Tests:** `python -m pytest tests/ -q -m "not slow"` → **1136 passing, 2 deselected slow**, ~75s.
- **Latest commits (newest first):**
  ```
  e15bbb7 fix(social/campaign): persist per-post images + serialize LLM calls
  3aa3c87 feat: auto-shrink social title + flyer CLI parity (--style-preset, --brand-kit)
  28332fc feat(social): expose --style-preset on post and campaign CLIs
  3945100 docs(readme): document brand kit + social post subsystems
  b89af69 feat(social): swap landscape workflow ernie→qwen for text-free backdrops
  5f12879 feat(social): social_graphic preset + tighter linkedin template + better voice prompt
  dd03e3c fix(social/voice): unwrap nested {copy: {...}} LLM response
  7481068 docs(state): mark Phase 19 complete — 9/9 plans, 1136 tests green
  eb31ee4 docs(phase-19): verification report — all 11 criteria covered
  ee6cd44 docs(phase-19): update tracking after wave 7 — all plans complete
  ```
- **.env (still live):** `FLYER_ANTHROPIC_API_KEY`, `FLYER_COMFYCLOUD_API_KEY`, `FLYER_OLLAMA_API_KEY`, `FLYER_VISION_PROVIDER=ollama`, `FLYER_OLLAMA_TEXT_MODEL=gemma4:31b-cloud`, `FLYER_VISION_MODEL=claude-sonnet-4-5`.
- **Roadmap state:** Phase 19 (Social Media Posts) ✅ shipped with 921 → 1136 tests (+217). Next: **Phase 20 — FastAPI + SQLAlchemy + frontend wrapper** (see §7).

---

## 2. What landed since the previous HANDOFF (2026-04-21 → 2026-04-22)

### Phase 19 — Social Media Posting System (9 plans × 7 waves)

Full new subsystem under `flyer_generator/social/`. All 11 ROADMAP success criteria (SOC-01..SOC-11) verified COVERED. Per-plan summary:

| Plan | Module | Role |
|---|---|---|
| 19-01 | `brochure/schema_renderer/text_gen.py` (edit) + `errors.py` | Wire `BrandVoice` (tone/example_phrases/banned_words) into `generate_content_from_prompt`. New `BrandVoiceViolationError`. Closes Phase 18 deferred item. |
| 19-02 | `social/models.py`, `social/storage.py`, `errors.py`, `.social-template.json`, `.gitignore`, `pyproject.toml` | Errors tree + Pydantic v2 models (`Post`, `PostSpec`, `PostBrief`, `Campaign`, `ValidationReport`, `PlatformRules`) + storage with path-traversal guards + `python-ulid>=3.1.0` dep |
| 19-03 | `social/platforms/{linkedin,twitter,x,instagram,facebook}.py`, `validation.py`, `readability.py` | 4-platform rules registry + per-platform `validate(post, rules)` + shared validation primitives + dependency-free Flesch-Kincaid |
| 19-04 | `social/workflow_map.py`, `social/crop.py` | ComfyCloud workflow ↔ platform-aspect map + Pillow aspect-preserving crops for campaign shared-hero fan-out |
| 19-05 | `social/schemas/{schema_model,loader}.py` + 12 JSON templates | `PostTemplate` model + loader + 12 templates (4 platforms × 3 intents: announcement / value-prop / testimonial). Palette + typography are `null` — kit application at render time fills them. |
| 19-06 | `social/renderer.py` | `render_post(template, copy, brand_kit, hero_image_bytes) → bytes`. Applies kit palette + typography, builds SVG via real `render_rect` (not the phantom `shape_to_svg` earlier drafts assumed), rasterizes to PNG at template canvas dims. |
| 19-07 | `brochure/schema_renderer/image_gate.py` (add helper), `social/voice.py`, `social/generator.py` | `generate_single_image` helper with correct `ComfyClient(settings, http_client)` init; voice-aware `generate_social_copy`; `generate_post` orchestrator (load template → copy → hero → render → validate → audit → Post) |
| 19-08 | `brand_kit/audit.py` (extract primitives) + `social/audit.py` | Extracted `scan_text_contrast` + `scan_image_density` from brand_kit audit as shared primitives. `audit_post` wraps a real `AuditReport` (not the silent-None degradation earlier drafts would have shipped). Includes B-04 regression guard test. |
| 19-09 | `social/campaign.py`, `social/__init__.py` (barrel), `social/__main__.py` (5-command typer CLI), integration tests | `generate_campaign` (shared hero + per-platform crops + per-platform voice-aware copy); typer CLI (`post`, `campaign`, `list-platforms`, `list-intents`, `show-rules`); barrel with 33 exported symbols; `tests/social/test_integration.py` e2e smoke with mocked LLM + Comfy; `test_package_exports.py::test_no_platform_api_imports_in_social_package` asserts SOC-11 (no publishing SDK imports). |

### 7 post-Phase-19 commits (fixes + follow-ups surfaced by real-world use)

| Commit | Change |
|---|---|
| `dd03e3c` | **fix**: `_normalize_to_post_copy` now handles the nested `{copy: {title, body, ...}}` shape that most LLMs return for the declared `copy.title` / `copy.body` prompt. Without this, every single post produced empty copy — only the first CLI invocation got lucky with a flat-dotted-keys response. |
| `5f12879` | **feat**: new `social_graphic` style preset (flat / abstract / no-text / no-people / navy+teal palette) + `linkedin__value-prop` template title budget `80 → 36` chars + body budget `1400 → 500` chars + voice prompt "quality bar" block (≤35-char titles, niche hashtags over saturated, 60-80% body budget). Moved top hoyack adversarial-loop score from 32/60 → 43/60. |
| `b89af69` | **feat**: swapped social landscape workflow from `ernie_landscape` → `qwen_landscape`. Ernie hallucinated garbled text ("B2BB Saw", "B2B SAVS") in abstract backdrops even with explicit `no text, no letters` negative prompts. Qwen-Image-2512 obeys. `WorkflowName` Literal extended to include `qwen_landscape` + `flux2_landscape`. |
| `3945100` | **docs**: README rewrite covering brand-kit + social subsystems. 3 → 5 entrypoints table; new Scrape-a-brand-kit section; new Generate-a-social-post + Campaign section; repo map updated. 339 lines added. |
| `28332fc` | **feat**: `--style-preset` flag on social `post` + `campaign` CLIs (previously hardcoded to `social_graphic`). Threads through `generate_post` + `generate_campaign` + `_generate_hero_image` + `_generate_shared_hero`. All 7 built-in presets now usable per invocation. |
| `3aa3c87` | **feat**: social `renderer._fit_font_size` auto-shrink heuristic (0.55 sans-serif advance coefficient, 65% legibility floor) — fixes the ~31-char title clipping ceiling every prior hoyack post hit. Plus flyer-CLI parity: `--style-preset` added as alias to `--preset`, and `--brand-kit <slug>` that pulls `kit.palette.accent` to override the default `--accent`. |
| `e15bbb7` | **fix**: 3 bugs from the hoyack 4-platform campaign run. (a) scraped page titles with `|` broke the storage slug validator — now sanitised with `[^a-z0-9]+ → "-"`. (b) Ollama cloud 429'd at 4-way parallelism — dropped campaign LLM semaphore to 1 (fully serial per-platform, ~20s for 4 platforms). (c) `save_campaign` only wrote `campaign.json` — images + per-post JSON were lost because `Campaign.posts` strips `image_bytes` on serialize. Added in-memory `Campaign.posts_full: dict[str, Post]` (excluded from JSON), CLI iterates it and calls `save_post` per platform. Dropped dead `qwen3.6:35b` from default fallback chain (404 on hoyack's Ollama account). |

### Hoyack cross-asset gallery (end-to-end proof)

`/tmp/hoyack-gallery/` contains:

| Asset | Path | Style | Brand-kit? | Result |
|---|---|---|---|---|
| Flyer (Hoyack Dev Summit 2026, fake event) | `flyer-scifi.png` | scifi | — | vision-approved 0.9, 1 attempt |
| Brochure (services tri-fold) | `brochure/{brochure_front.png, brochure_back.png, brochure_print.pdf}` | photorealistic + editorial_classic | hoyack | AA pass both sheets |
| Social post (topic "Ship features at the speed of now") | `social-default/hoyack/.../linkedin__value-prop/image.png` | social_graphic | hoyack | PASSED |
| Social post | `social-anime/hoyack/.../linkedin__value-prop/image.png` | anime | hoyack | PASSED |
| Social post | `social-retro/hoyack/.../linkedin__value-prop/image.png` | retro_poster | hoyack | PASSED |

And `/tmp/hoyack-campaign/hoyack/01KPSHY57DP6MC1CS1A169XZ4S/` — full 4-platform campaign (one shared hero cropped to 1200×627 LinkedIn, 1200×675 Twitter, 1080×1080 Instagram, 1200×630 Facebook; per-platform copy regenerated serially via semaphore=1).

Confirms cross-axis parity: (style preset × template × brand kit × workflow) all compose cleanly across flyer + brochure + social; brand-kit palette/typography survives all three output paths.

### Brochure workflow adversarial battery

`/tmp/brochure-adversarial/` (from an earlier parallel session): 5 landscape ComfyCloud workflows × 3 brochure prompts × built-in verification + adversarial outside/inside scoring.

| Workflow | Built-in (avg) | Adv outside | Adv inside | Gen (s) | Hero vision-approved |
|---|---:|---:|---:|---:|---|
| **`ernie_landscape`** | **52.7** | 31.7 | 38.3 | 225.9 | 2/3 |
| `ernie_turbo_landscape` | 51.3 | 30.0 | 35.0 | 146.0 | 2/3 |
| `turbo_landscape` | 48.3 | 20.0 | 35.0 | 266.3 | 1/3 |
| **`flux2_landscape`** | **52.7** | **33.3** | 26.7 | 211.0 | 2/3 |
| `longcat_landscape` | 50.7 | 30.0 | 26.7 | 198.3 | 1/3 |
| `qwen_landscape` | 51.0 | 28.3 | 33.3 | 180.7 | 2/3 |

**Winners:** `ernie_landscape` + `flux2_landscape` tied on built-in (52.7). `flux2_landscape` edges ahead on adversarial-outside (33.3 vs 31.7). `ernie_turbo_landscape` gives ~35% speedup for only a 1.4pt quality drop — best speed/quality ratio. For **social**: `qwen_landscape` remains preferred (obeys "no text" negative prompt, which is the ruling constraint).

---

## 3. Current open issues / debt

### A. ComfyCloud poll budget workaround still required (MEDIUM, unchanged)

`flyer_generator/stages/comfy_client.py` default `poll_max_attempts=20 × poll_interval_seconds=4 = 80s`. Deep queues (observed 5-10 min on `queued_limited`) still need env-var override: `FLYER_POLL_MAX_ATTEMPTS=200 FLYER_POLL_INTERVAL_SECONDS=6`. Proper fix (differentiate `queued_*` from `preparing`/`executing` budgets) still deferred.

### B. `remediate_contrast` can't fix same-color collisions (MEDIUM, unchanged)

`fg == bg` literal matches still not detected; remediation iterate-loop gives up after 2 cycles. Fix direction noted in old HANDOFF §4B.

### C. Density remediation not wired to text_gen (LOW, unchanged)

`iterate_audit_loop.remediate_density` still a no-op because `text_gen.generate_content_from_prompt` doesn't accept per-key `tighter_budgets`.

### D. NEW — Ollama cloud concurrency is tight

Observed: 4-platform campaign → 429 "too many concurrent requests" at semaphore=2. Campaign LLM semaphore is now hardcoded to 1 (fully serial; ~20s for 4 platforms). Phase 20's text generator should consider switching to Anthropic for LLM text to remove this bottleneck (already configured via `FLYER_VISION_PROVIDER=anthropic`).

### E. NEW — Fallback chain is account-specific

`qwen3.6:35b` 404s on the current Ollama account → dropped from the default fallback chain. Remaining default: `[kimi-k2.6:cloud]`. Phase 20 should expose per-account fallback config via DB settings.

### F. NEW — `_fit_font_size` is a heuristic

0.55 sans-serif advance coefficient with 65% legibility floor works well for Inter/Roboto-style weights. Will need per-font tuning when web-font support lands.

### G. NEW — Campaign doesn't persist `source_hero.png`

The uncropped 2048² source hero is discarded after per-platform crops. README §"Campaign" documents the file as present — it's NOT. Low priority. Fix either: (a) update README to match reality, or (b) add `save_source_hero=True` option. Will address in Phase 20 alongside DB persistence.

### H. NEW — Critic preference vs. human preference diverged

Adversarial loop's Claude-vision critic consistently penalised "too literal" imagery and oscillated on subjective copy preferences (negative framing, CTA generic-ness, hashtag alignment). Scores plateaued around 44/60 after 6 loops of iteration. Real ceiling is critic preference, not pipeline capability.

### I. NEW — Social template title fit ceiling

Before `_fit_font_size`, template declared `max_chars: 36` at 64px over 1080px slot. Titles 37+ chars clipped at render time. Auto-shrink now kicks in, but very long (60+ char) titles hit the 65% legibility floor and still overflow. If Phase 20 needs to support long titles, either raise the legibility floor or add multi-line wrap.

### J. ComfyCloud account attention still needed

Billing endpoints (`/api/account`, `/api/usage`) still return 401 with current API key. Dashboard at https://cloud.comfy.org.

---

## 4. How to run things

### Brand kit lifecycle (unchanged from prev HANDOFF)

```bash
python -m flyer_generator.brand_kit fetch https://example.com --slug example
python -m flyer_generator.brand_kit list
python -m flyer_generator.brand_kit show example
```

### Flyer

```bash
python -m flyer_generator \
    --event-json /tmp/example-event.json \
    --preset scifi \
    --brand-kit example \
    --output /tmp/example-flyer.png
```

`--style-preset` is an alias for `--preset` (naming parity). `--brand-kit <slug>` pulls accent color; fuller palette/typography threading on the flyer path is deferred (flyer uses vision-determined zones, not schema_renderer).

### Brochure — schema-driven (with brand kit + ComfyCloud hero)

```bash
FLYER_POLL_MAX_ATTEMPTS=200 FLYER_POLL_INTERVAL_SECONDS=6 \
python -m flyer_generator.brochure.schema_renderer \
    --template editorial_classic \
    --content /tmp/example-content.json \
    --brand-kit example \
    --generate-images --workflow ernie_landscape --style-preset photorealistic \
    --output /tmp/example-brochure
```

### Social post

```bash
python -m flyer_generator.social post \
    --brand-kit hoyack \
    --platform linkedin --intent value-prop \
    --topic "Ship features at the speed of now" \
    --cta "Start a Project" \
    --image-hint "abstract geometric network, navy + teal, no text no people" \
    --style-preset social_graphic \
    --output /tmp/hoyack-post
```

Writes `<output>/<slug>/<campaign_id>/<platform>__<intent>/{post.json,image.png}`.

### Social campaign (4 platforms, one shared hero)

```bash
FLYER_POLL_MAX_ATTEMPTS=200 FLYER_POLL_INTERVAL_SECONDS=6 \
python -m flyer_generator.social campaign \
    --brand-kit hoyack \
    --platforms linkedin,twitter,instagram,facebook \
    --topic "Ship features at the speed of now" \
    --cta "Start a Project" \
    --style-preset social_graphic \
    --output /tmp/hoyack-campaign
```

One ComfyCloud hero call + 4 serial per-platform LLM copy calls + 4 crops + 4 renders. ~90s wall-clock end-to-end.

### Inspection

```bash
python -m flyer_generator.social list-platforms
python -m flyer_generator.social list-intents
python -m flyer_generator.social show-rules linkedin
```

### Tests

```bash
python -m pytest tests/ -q -m "not slow"          # 1136 pass, 2 deselected
python -m pytest tests/social/ -q                 # 206 tests (Phase 19)
python -m pytest tests/brand_kit/ -q              # 239 tests (Phase 18)
python -m pytest tests/brochure/ -q               # brochure suite
```

---

## 5. Quick-reference file index (delta since last HANDOFF)

```
flyer_generator/
├── social/                            ← ENTIRE NEW SUBSYSTEM (Phase 19)
│   ├── __init__.py                    consolidated barrel, 33 public names
│   ├── __main__.py                    typer CLI: post / campaign / list-platforms / list-intents / show-rules
│   ├── models.py                      Post, PostSpec, PostBrief, Campaign, PlatformRules, ValidationReport
│   ├── platforms/                     linkedin.py / twitter.py (x alias) / instagram.py / facebook.py
│   ├── schemas/                       PostTemplate model + loader + 12 JSON templates
│   ├── voice.py                       voice-aware copy generation (unwraps nested LLM shapes)
│   ├── renderer.py                    template → SVG → PNG with _fit_font_size auto-shrink
│   ├── generator.py                   generate_post orchestrator
│   ├── campaign.py                    generate_campaign (shared hero + serial per-platform fan-out)
│   ├── validation.py                  shared validation primitives
│   ├── readability.py                 dependency-free Flesch-Kincaid
│   ├── workflow_map.py                aspect → ComfyCloud workflow (qwen_landscape default for landscape)
│   ├── crop.py                        Pillow aspect-preserving crops
│   ├── audit.py                       audit_post + SocialAuditReport (wraps shared brand_kit primitives)
│   └── storage.py                     .social-campaigns/<slug>/<campaign_id>/ layout
│
├── presets.py                         ← EXTENDED: added social_graphic (7 total presets)
├── brand_kit/
│   └── audit.py                       ← EXTENDED: extracted scan_text_contrast + scan_image_density primitives
├── brochure/schema_renderer/
│   ├── text_gen.py                    ← EXTENDED: brand_voice param + BrandVoiceViolationError
│   └── image_gate.py                  ← EXTENDED: generate_single_image helper (shared by social)
├── config.py                          ← EXTENDED: ollama_text_model_fallbacks default trimmed to [kimi-k2.6:cloud]
└── errors.py                          ← EXTENDED: SocialError + BrandVoiceViolationError hierarchy

tests/
├── social/                            ← NEW dir: 206 tests
│   ├── test_models.py / test_storage.py / test_voice.py / test_voice_social_copy.py
│   ├── test_platforms_{linkedin,twitter,instagram,facebook}.py
│   ├── test_schemas.py / test_schemas_loader.py / test_readability.py
│   ├── test_workflow_map.py / test_crop.py / test_renderer.py
│   ├── test_audit.py / test_generator.py / test_campaign.py / test_cli.py
│   ├── test_package_exports.py (includes SOC-11 no-publishing-SDK-imports guard)
│   └── test_integration.py (e2e mocked LLM+Comfy)
└── brochure/test_image_gate.py        ← NEW: generate_single_image helper tests

.social-campaigns/                     ← UNTRACKED (.gitignore). Holds generated campaigns.
.social-template.json                  ← TRACKED: social-template schema reference
```

---

## 6. Latest real-world artifacts on disk

| Path | Contents |
|---|---|
| `/tmp/hoyack-gallery/flyer-scifi.png` | 1080×1920 event flyer, Hoyack Dev Summit 2026 in scifi preset |
| `/tmp/hoyack-gallery/brochure/` | Front + back PNG + PDF, editorial_classic + photorealistic + hoyack brand kit |
| `/tmp/hoyack-gallery/social-{default,anime,retro}/` | 3 social variants, same copy, different style preset |
| `/tmp/hoyack-campaign/hoyack/01KPSHY57DP6MC1CS1A169XZ4S/` | 4-platform campaign: `campaign.json` + `{linkedin,twitter,instagram,facebook}__value-prop/{post.json,image.png}` |
| `/tmp/brochure-adversarial/{ernie,flux2,qwen,longcat,turbo}_landscape/` | Per-workflow 3-prompt battery with `summary.json` — basis for §2 workflow-scoring table |

Inputs still on disk: `/tmp/hoyack-brief.json`, `/tmp/hoyack-event.json`, `/tmp/hoyack-brochure.json`. Three scraped brand kits under `.brand-kits/{hoyack,shrubnet,thunderstaff}/`.

---

## 7. Next phase spec — Phase 20: FastAPI + SQLAlchemy + frontend

**User intent (verbatim from this session):** "We will be next building a front end for this project and wrapping it with fastapi and implementing sqlalchemy."

### Architecture sketch (for `/gsd-plan-phase` to firm up)

**Reuses from Phases 1-19 (no duplication):**

- All five Python API entrypoints: `FlyerGenerator.generate()`, schema-renderer's `render_schema_brochure()` + `generate_template_images()`, brand_kit's `fetch_brand_kit()` / `load_brand_kit()` / `apply_brand_kit()`, social's `generate_post()` / `generate_campaign()`.
- Existing Pydantic v2 models — direct ORM-adjacent mapping candidates (`EventInput`, `BrandKit`, `PostBrief`, `Post`, `Campaign`, `ValidationReport`, etc.).
- `flyer_generator.stages.llm_retry` for resilience.
- ComfyCloud pipeline via `generate_single_image`.
- Filesystem roots `.brand-kits/` + `.social-campaigns/` — pair with DB for metadata + paths, rather than replace.
- `flyer_generator.config.Settings` (pydantic-settings) — promote to a startup `AppSettings` the app reads once.

**New for Phase 20 (sketch — planner to firm up):**

1. **FastAPI skeleton** (`flyer_generator/api/`):
   - Async routes, Pydantic-v2 request/response models, OpenAPI auto-docs
   - CORS middleware, request-id + structlog binding
   - Error-hierarchy → HTTPException mapping (SocialError → 400, BrandKitError → 400/404, ComfyError → 502, VisionError → 502)
   - Versioned prefix: `/api/v1/...`

2. **SQLAlchemy 2.x async** + **Alembic** migrations:
   - Primary: Postgres (prod). Dev: SQLite.
   - Async session factory, dependency-injected per-request.
   - Data model sketch:
     - `User` (id, email, auth_provider, created_at)
     - `Organization` (tenancy boundary — v1 can be single-org)
     - `BrandKit` (mirrors Pydantic model + `source_url`, `scraped_at`, `org_id`)
     - `Flyer`, `Brochure`, `Campaign`, `Post`
     - `Render` (links Post/Flyer/Brochure ↔ file paths ↔ ComfyCloud job IDs ↔ vision verdicts)
     - `Job` (async task tracking for long ComfyCloud runs: status, started_at, completed_at, error, result_ref)

3. **HTTP endpoint surface (sketch):**
   - `POST   /api/v1/brand-kits/fetch` — async scrape, returns `job_id`
   - `GET    /api/v1/brand-kits` / `GET /api/v1/brand-kits/{slug}`
   - `POST   /api/v1/flyers` — structured event → flyer job
   - `POST   /api/v1/brochures` — prompt or content JSON → brochure job
   - `POST   /api/v1/social/posts` — brief → post job
   - `POST   /api/v1/social/campaigns` — campaign job
   - `GET    /api/v1/jobs/{id}` — status poll
   - `GET    /api/v1/renders/{id}/image` — serves PNG/PDF artifact
   - `WS     /api/v1/jobs/{id}/stream` — live progress (optional)

4. **Job queue** — ComfyCloud runs are 60-300s, too long for request lifetime. Options for planner:
   - **arq** (Redis-based, async-native, lightweight — recommended)
   - Celery + Redis (industry standard, heavier)
   - FastAPI `BackgroundTasks` (in-process, OK for dev, NOT for prod)

5. **Frontend (sketch — open question):**
   - React + Vite + ShadCN + Tailwind (most ecosystem momentum)
   - SvelteKit (simpler reactivity)
   - HTMX + server-rendered templates (simplest — low-JS)
   - Planner should propose; Phase 20 plan will include a decision.

6. **File storage:** keep `.brand-kits/` + `.social-campaigns/` filesystem roots for v1; add an S3/R2 path-adapter for production in a later increment.

7. **Tests:** add `tests/api/` for route-level tests (httpx `AsyncClient`). Keep existing 1136 tests green.

### Open questions the planner will need to surface to the user

- **Multi-tenant or single-user v1?** (Shapes the `Organization` model and every foreign key)
- **Auth mechanism?** Magic link? OAuth (Google/GitHub)? None for v1 behind a private IP?
- **Frontend framework?** React vs. SvelteKit vs. HTMX
- **Job queue choice?** arq vs. Celery vs. BackgroundTasks
- **Primary DB?** Postgres (docker) vs. SQLite-only for v1
- **Deployment target?** Local dev only vs. cloud-deployable (Fly.io / Railway / Render / self-hosted Docker)

### Inputs already seeded on disk

- 3 scraped brand kits (`hoyack`, `shrubnet`, `thunderstaff`) — candidates for seed-fixture migration on startup
- `/tmp/hoyack-campaign/hoyack/01KPSHY.../` — full campaign, possible e2e-smoke fixture
- `/tmp/brochure-adversarial/` — workflow benchmark, possible admin-page seed data
- `/tmp/hoyack-gallery/` — 5-variant sample gallery

### When you come back after `/clear`

1. `git log --oneline | head -10` — expect a `docs: update HANDOFF + README for Phase 19 completion + Phase 20 sketch` commit at top.
2. `python -m pytest tests/ -q -m "not slow"` — confirm 1136/1136 pass (2 slow deselected).
3. Read this HANDOFF.
4. Run `/gsd-plan-phase` with intent "Phase 20 — FastAPI + SQLAlchemy + frontend" using §7 here as the spec source. Expect the planner to split into ~10-12 plans across 5-7 waves; the 6 open questions above should surface in the first discussion round.

---

## 8. TL;DR for next session

All four creative subsystems ship: **flyer + brochure + brand kit + social**. Adversarial iteration loop on hoyack surfaced + fixed 3 real Phase-19 bugs (normalizer, template budgets, workflow swap) and drove 4 follow-up features (social_graphic preset, voice-prompt quality bar, CLI --style-preset parity, auto-shrink). Hoyack cross-asset gallery on disk proves style × template × brand-kit × workflow all compose. Full 4-platform campaign on disk proves shared-hero + per-platform-crop + serial-LLM works end-to-end. Brochure workflow benchmark across 5 ComfyCloud models — `ernie_landscape` and `flux2_landscape` tied best. Next: HTTP + DB + UI wrapper so non-CLI users can drive all of this. Spec in §7, 6 open questions for the planner.

1136/1136 tests passing. All work committed. Safe to `/clear`.
