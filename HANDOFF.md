# Flyer Generator — Session Handoff

**For a fresh session after `/clear`.** Full state-of-the-world for the autocreative repo after Phase 18 (Brand Kit) + 2 quick tasks shipped today.

---

## 1. Quick orientation

- **Branch:** `master`, clean tree (untracked: `.claude/`, `docs/brochure-gallery-plan.md`, `docs/brochure-templates/`, `docs/workflows-pending/` — none to worry about).
- **Tests:** `python -m pytest tests/ -q -m "not slow"` → **921 passing, 2 deselected slow**, ~72s.
- **Latest commits (newest first):**
  ```
  272667f docs(quick-260421-epk): auto-audit in schema_renderer CLI
  a976152 feat(260421-epk): auto-audit every schema_renderer render
  4039fba docs(quick-260421-c1n): resilient Ollama LLM client
  38361bf docs(260421-c1n): complete resilient Ollama LLM client quick task
  2399991 docs(260421-c1n): document LLM retry + model fallback behavior
  b9e843b feat(260421-c1n): add LLM retry helper + wire Ollama clients to it
  6ab79a9 feat(260421-c1n): add LLM error hierarchy and retry/fallback config
  6157099 fix(brand_kit/applier): normalize CSS font-stack quotes for SVG attrs
  11bf1de docs(phase-18): code review report
  f1ba27f docs(phase-18): verification report
  ```
- **.env (still live):** `FLYER_ANTHROPIC_API_KEY`, `FLYER_COMFYCLOUD_API_KEY`, `FLYER_OLLAMA_API_KEY`, `FLYER_VISION_PROVIDER=ollama`, `FLYER_OLLAMA_TEXT_MODEL=gemma4:31b-cloud`, `FLYER_VISION_MODEL=claude-sonnet-4-5`.
- **Roadmap state:** Phase 18 (Brand Kit) ✅ shipped with 912→921 tests. Next: **Phase 19 — Social Media Posting System** (see §7).

---

## 2. What landed this session (2026-04-20 → 2026-04-21)

### Phase 18 — Brand Kit System (8 plans, 5 waves)

Full new subsystem under `flyer_generator/brand_kit/`:

| Module | Role |
|---|---|
| `storage.py` | Read/write `.brand-kits/<slug>/` (env: `FLYER_BRAND_KITS_DIR`, default `.brand-kits/`) with slug regex + path-traversal containment + `FLYER_BRAND_KITS_ALLOW_SYSTEM` escape |
| `models.py` | Pydantic v2: `BrandKit`, `BrandPalette` (primary/secondary/accent/neutral_dark/neutral_light/extras — each a `ColorUsage`), `BrandTypography`, `BrandLogo`, `BrandVoice`, `BrandPhotoHints`, `ColorUsage`. All nested palette/typography/voice/photography fields are Optional (partial scrapes round-trip) |
| `contrast.py` | `wcag_ratio`, `passes_aa`, `passes_aaa`, `classify_level`, `remediate` (opposite-neutral swap → OKLCH binary search fallback), `ensure_aa`, `ContrastPair`, `ContrastReport`. Uses `wcag-contrast-ratio>=0.9` + `coloraide>=8,<9`. `wcag_ratio` takes hex strings, normalizes to float 0-1 before calling the lib (the lib pitfall) |
| `scraper.py` / `scraper_playwright.py` / `scraper_bs4.py` / `palette.py` | Async scraper: Playwright primary → BS4+httpx+tinycss2 fallback. Palette extraction via `Pillow.Image.quantize(colors=5, method=MEDIANCUT)` — no extra deps. SSRF deny list on entry URL + CSS URLs + logo URLs. Path-traversal containment on logo downloads. 50MB per-asset + 50MB total download caps |
| `applier.py` | `apply_brand_kit(template, kit, *, slug=None, size_multiplier=None) -> (TemplateSchema, bytes | None)` — immutable via `model_copy(deep=True)`. AA contrast guardrail on applied palette (fires `brand_kit_palette_aa_fix` log + OKLCH nudge when needed). Includes `_normalize_font_stack` — replaces `"` → `'` in CSS font stacks to avoid `font-family=""Open Sans"..."` SVG breakage (caught live on hoyack.com) |
| `audit.py` | `audit_render(content, template, png_bytes, *, side="outside", cycle=0) -> AuditReport`. Report has `whitespace` (per-panel density ratio), `contrast` (`ContrastReport`), `density` (per content_key fill ratio), `issues` (AuditIssue list with severity/category/panel/content_key/detail). Also exports `iterate_audit_loop` + `remediate_contrast` + `remediate_density` |
| `__main__.py` | typer CLI: `fetch <url> --slug <slug>`, `list`, `show <slug>` |
| `__init__.py` | Consolidated re-exports (27 public names, sorted `__all__`) |

**Commits:** `6ab79a9` → `11bf1de` (24 commits on master covering 8 plans + 3 revisions).

### Quick task 260421-c1n — Resilient Ollama LLM client

- New module `flyer_generator/stages/llm_retry.py` with `_call_with_retry(http_client, url, payload, *, model_chain, max_attempts, base_delay, max_delay, log)`.
- Classifies errors: 429 → `LLMRateLimitError` (honor `Retry-After` int-seconds or HTTP-date), 500/502/503 → `LLMServiceUnavailableError`, ReadTimeout/ConnectError → `LLMTimeoutError`, 404/model-not-found → `LLMModelUnavailableError` (skip model, not retry), 400/401/403 → `LLMAPIError` (fatal, no retry/fallback).
- Exponential backoff + jitter: `min(max_delay, base*2**(attempt-1)) + jitter(0..base/2)`.
- Model fallback chain: after primary's `max_attempts` retries exhaust, advance to next model in chain. Emits `llm_model_fallback` log.
- Wires both `flyer_generator/stages/vision.py` (vision path) AND `flyer_generator/brochure/llm_client.py` (text path). No signature changes on public methods.
- New config: `ollama_text_model_fallbacks`, `ollama_vision_model_fallbacks` (both default `["kimi-k2.6:cloud", "qwen3.6:35b"]`), `llm_retry_max_attempts=3`, `llm_retry_base_delay=1.0`, `llm_retry_max_delay=10.0`.
- New errors: `LLMAPIError`, `LLMRateLimitError`, `LLMServiceUnavailableError`, `LLMTimeoutError`, `LLMModelUnavailableError`. `VisionAPIError = LLMAPIError` kept as deprecated alias (all existing `except VisionAPIError` still catches).
- **Proven in production** this session: `gemma4:31b-cloud` ReadTimeout → retry attempt 2 → succeeded, no chain fallthrough needed.

### Quick task 260421-epk — Auto-audit in schema_renderer CLI

- CLI flags on `python -m flyer_generator.brochure.schema_renderer`:
  - `--audit / --no-audit` — default on. Writes `<output>/audit.json` with `{outside, inside, is_clean_overall}`.
  - `--iterate-audit N` — run `iterate_audit_loop` up to `min(N, 3)` cycles when issues found (default 0 = single pass).
  - `--audit-json PATH` — override sidecar path.
- Per-sheet stderr summary prints after rasterize:
  ```
  Audit [outside]: AA pass=True (0/18 fail), density_min=0.20, whitespace_max=0.83, issues=8 (0 warn, 8 info)
  Audit [inside]:  AA pass=True (0/21 fail), density_min=0.14, whitespace_max=0.77, issues=8 (0 warn, 8 info)
  ```
- 9 new tests in `tests/brochure/schema_renderer/test_auto_audit.py`.
- **Scope note (deferred):** density-remediation in the iterate loop is currently a no-op because `text_gen.generate_content_from_prompt` doesn't yet accept per-key `tighter_budgets`. Contrast-swap remediation works when `--brand-kit` is supplied.

---

## 3. Real-world runs this session (end-to-end proof)

Three sites exercised end-to-end: shrubnet.com, hoyack.com, thunderstaff.com. All three have untracked brand kits under `.brand-kits/<slug>/` (gitignored). Generated brochures on disk:

| Site | Path | Template | Images | Audit verdict |
|---|---|---|---|---|
| shrubnet | `/tmp/shrubnet-bk-full/` | editorial_classic | ernie hero, vision-approved 0.95 | AA pass, 0 fails, is_clean=True (outside) / False on 1 inner_center whitespace |
| shrubnet | `/tmp/shrubnet-bk-gallery/<template>/` × 4 templates | varies | text-only | clean |
| hoyack | `/tmp/hoyack-bk-full/` | editorial_classic | ernie hero, vision-approved 0.85 | AA pass, is_clean=True both sheets |
| hoyack | `/tmp/hoyack-bk-gallery/<template>/` × 3 templates | varies | text-only | clean |
| hoyack | `/tmp/hoyack-ldstack-v2/` | layered_depth_stack | text-only | 2 whitespace warns (minimalist template, expected) |
| thunderstaff | `/tmp/thunderstaff-v1/` | editorial_classic | text-only | AA pass both sheets, is_clean=True |
| thunderstaff | `/tmp/thunderstaff-poh-v1/` | pattern_overlay_hybrid | text-only | 4 whitespace warns (template is image-forward, placeholders insufficient) |
| **thunderstaff** | **`/tmp/thunderstaff-bds-v1/`** | **bold_diagonal_split** | **ernie hero + ernie spot_1, vision-approved 0.85** | **2 contrast fails: `#FFF8F4 on #FFF8F4` — audit caught a template/palette collision bug** |

One-shot inputs still on disk: `/tmp/shrubnet-brief.json`, `/tmp/hoyack-brief.json`, `/tmp/thunderstaff-brief.json`, `/tmp/shrubnet-e2e/logo.png`.

---

## 4. Open issues / debt (surfaced by this session, NOT yet fixed)

### A. ComfyCloud poll budget is too short for deep queues (MEDIUM)

`flyer_generator/stages/comfy_client.py` polls with `poll_max_attempts=20 × poll_interval_seconds=4 = 80s`. On a busy ComfyCloud queue, jobs take 5-10+ min (most time in `queued_limited` / `queued_waiting` state, waiting for a worker slot). The client gives up too early, logs timeout, falls back to a placeholder — then the caller often resubmits, pushing the queue deeper. Today this self-amplified into 19 pending jobs.

**Workaround today:** `FLYER_POLL_MAX_ATTEMPTS=200 FLYER_POLL_INTERVAL_SECONDS=6` (20-min budget). This proved the pipeline works (ernie hero shipped in 260s wall-clock, 213s in queue → 47s actual work).

**Proper fix:** make the poll loop differentiate "queued" (don't count against budget) from "preparing"/"executing" (do count). Status taxonomy observed:
- `queued_waiting` — submitted, no worker assigned yet. Queue is moving.
- `queued_limited` — submitted, concurrent-slot cap hit. Queue is blocked waiting for a slot.
- `preparing` — worker assigned (`assigned_inference` populated). This is the "Initializing - almost ready" log message in ComfyCloud dashboard.
- `executing` — actively running.
- `success` — done.

Only `preparing` + `executing` should count toward the 20-attempt budget. `queued_*` should poll ~indefinitely with a slower interval (every 15-30s).

### B. `remediate_contrast` can't fix same-color collisions (MEDIUM)

Today's thunderstaff + `bold_diagonal_split` run surfaced `fg=#FFF8F4 bg=#FFF8F4 ratio=1.00` on 2 text regions — text color equals background exactly. The Phase 18 opposite-neutral-swap remediation doesn't detect "fg == bg literally." Iterate loop ran 2 cycles and couldn't fix.

**Fix direction:** extend `remediate_contrast` to detect `ratio < 2.0` (effectively invisible) and pick any AA-passing palette color, not just the opposite neutral. OR: add a palette-apply-time sanity check that walks every text-over-shape pair and pre-resolves collisions before render.

### C. Density remediation is not wired (LOW — acknowledged at ship time)

`iterate_audit_loop`'s `remediate_density` requires `text_gen.generate_content_from_prompt` to accept per-key `tighter_budgets: dict[str, int]`. It doesn't today. Documented inline in `__main__.py`. Fix when we re-enter `text_gen` for Phase 19 or a followup.

### D. "Fonts read small" still partially open

Phase 18 Plan 08 bumped body/bullet sizes across all 13 templates (`body_size >= 34`, `bullet_size >= 32`). But user-reported "fonts read a bit small" was a gestalt observation — it's worth doing one visual pass with a fresh set of eyes once brand kits are in play (some dark-palette kits push text toward edges).

### E. ComfyCloud account needs attention

19 jobs pending at start of today's thunderstaff run, 0 running. Billing endpoints (`/api/account`, `/api/usage`) return 401 with the current API key. Dashboard at https://cloud.comfy.org — check credits/plan/stuck-job-cancel. Not a code issue but blocks image generation when the queue saturates.

---

## 5. How to run things

### Brand kit lifecycle
```bash
# 1. Scrape a brand from a URL
python -m flyer_generator.brand_kit fetch https://example.com --slug example

# 2. Inspect
python -m flyer_generator.brand_kit list
python -m flyer_generator.brand_kit show example

# 3. Apply to a brochure (auto-audit on by default)
python -m flyer_generator.brochure.schema_renderer \
    --template editorial_classic \
    --brief-json /tmp/example-brief.json \
    --prompt "..." \
    --brand-kit example \
    --generate-images --workflow ernie_landscape --style-preset photorealistic \
    --output /tmp/example-out

# With a deep ComfyCloud queue, bump the poll budget:
FLYER_POLL_MAX_ATTEMPTS=200 FLYER_POLL_INTERVAL_SECONDS=6 \
    python -m flyer_generator.brochure.schema_renderer ...
```

### Audit an existing render
```python
from flyer_generator.brand_kit import load_brand_kit, apply_brand_kit, audit_render
from flyer_generator.brochure.schema_renderer import load_template
from flyer_generator.brochure.schema_renderer.content_model import BrochureContent

kit = load_brand_kit("example")
template = load_template("editorial_classic")
applied, _ = apply_brand_kit(template, kit, slug="example")
content = BrochureContent.model_validate(json.loads(Path(".../content.json").read_text()))
png_bytes = Path(".../brochure_front.png").read_bytes()
report = audit_render(content, applied, png_bytes, side="outside")
```

### Tests
```bash
python -m pytest tests/ -q -m "not slow"          # 921 pass, 2 deselected
python -m pytest tests/brand_kit/ -q              # 239 tests
python -m pytest tests/brochure/schema_renderer/  # gallery + auto-audit
```

---

## 6. Quick-reference file index (delta since last HANDOFF)

```
flyer_generator/
├── brand_kit/                    ← ENTIRE NEW SUBSYSTEM (Phase 18)
│   ├── __init__.py               consolidated re-exports, sorted __all__
│   ├── __main__.py               typer CLI: fetch / list / show
│   ├── applier.py                apply_brand_kit + AA guardrail + _normalize_font_stack
│   ├── audit.py                  audit_render + iterate_audit_loop + remediate_contrast/density
│   ├── contrast.py               wcag_ratio + ensure_aa + ContrastPair/Report
│   ├── models.py                 BrandKit + BrandPalette + BrandTypography + BrandLogo + BrandVoice + BrandPhotoHints + ColorUsage
│   ├── palette.py                Pillow quantize-based palette extraction
│   ├── scraper.py                orchestrator: Playwright primary → BS4 fallback
│   ├── scraper_bs4.py            httpx + beautifulsoup4 + tinycss2 fallback
│   ├── scraper_playwright.py     Playwright async primary
│   └── storage.py                .brand-kits/<slug>/ layout + env + guards
│
├── stages/
│   └── llm_retry.py              ← NEW (quick task 260421-c1n): shared retry helper
│
├── errors.py                     ← EXTENDED: LLMAPIError hierarchy + VisionAPIError alias + BrandKitError hierarchy
├── config.py                     ← EXTENDED: brand_kits_dir + llm_retry_* + ollama_*_fallbacks
└── brochure/schema_renderer/
    └── __main__.py               ← EXTENDED: --brand-kit, --audit/--no-audit, --iterate-audit, --audit-json

tests/
├── brand_kit/                    ← NEW dir (Phase 18): 239 tests across 15 files
├── test_llm_resilience.py        ← NEW (quick 260421-c1n): 10 retry/fallback tests
└── brochure/schema_renderer/
    └── test_auto_audit.py        ← NEW (quick 260421-epk): 9 CLI auto-audit tests

.brand-kits/                      ← UNTRACKED (.gitignore). Holds scraped shrubnet/hoyack/thunderstaff kits today.
.brand-kit-template.json          ← TRACKED: schema-shape reference at repo root
```

---

## 7. Next up — Phase 19: Social Media Posting System

**User intent (verbatim):** build a social media posting system that generates social media posts after scraping the org and getting its brand.

### Architecture sketch (for `/gsd-plan-phase` to firm up)

**Reuses from Phase 18:**
- `flyer_generator.brand_kit` subsystem — palette, typography, logo scraping is already done.
- `BrochureBrief` (rename to `BrandBrief` or add a `ContentBrief` variant?) — same interrogative intake: audience, voice, offerings, differentiators, CTA.
- `flyer_generator.stages.llm_retry` — shared retry + fallback chain.
- ComfyCloud pipeline via `image_gate` — same workflow catalog.
- `audit_render`-style adversarial validation, but for post-sized canvases.

**New for Phase 19:**

1. **Platform catalog** (`flyer_generator/social/platforms/`):
   - `linkedin.py` — post model: headline + body (max ~3000 chars) + optional 1200×627 or 1200×1200 image. Hashtags inline, link preview metadata.
   - `twitter.py` / `x.py` — post model: text (280 chars, or premium 4000) + up to 4 images 1200×675. Thread support (split long content into N posts).
   - `instagram.py` — post model: caption (2200 chars) + hashtags (up to 30) + 1–10 1080×1080 or 1080×1350 images + optional 1080×1920 story variant.
   - `facebook.py` (optional) — post model: text + image/images + optional link preview.
   - Each platform ships a Pydantic `PostSpec` + a `validate(post)` function against platform rules.

2. **Post templates** (`flyer_generator/social/schemas/`):
   - Parallel to brochure template schemas. Each template is `{platform, intent (announcement/testimonial/value-prop/faq/carousel/etc), layout, text_budgets, image_slots}`.
   - Could be 5-10 templates per platform spanning common intents.
   - SVG-to-raster for image platforms (reuse schema_renderer approach for branded image posts).
   - Pure-text for text-only post intents.

3. **Post generator orchestrator** (`flyer_generator/social/generator.py`):
   - Input: `BrandKit` slug + `PostBrief` (topic/intent/cta/optional date/optional source URL).
   - Output: `Post` Pydantic model — `{platform, intent, copy, hashtags, image_bytes | None, audit_report}`.
   - Flow: select template → generate copy via text_gen → (if image slot) generate hero via ComfyCloud → render SVG → rasterize → audit.
   - Audit dimensions: platform char-limit compliance, hashtag count/length, image aspect, contrast, brand-kit color compliance, readability.

4. **Campaign concept** (`flyer_generator/social/campaign.py`):
   - Takes a single brand + topic + list-of-platforms → generates a matching set of posts (one per platform, auto-sized/cropped images from same hero).
   - Or: "weekly drip" — one brand + N topics → N posts scheduled across a date range.
   - Output: structured campaign JSON + per-post rendered artifacts.

5. **Tracked vs. untracked storage:**
   - Tracked: `.social-template.json` schema reference + platform JSON schemas.
   - Untracked: `.social-campaigns/<slug>/<campaign-id>/` with per-platform post JSON + image bytes + audit sidecar.
   - Env: `FLYER_SOCIAL_CAMPAIGNS_DIR` (default `.social-campaigns/`).

6. **CLI:**
   ```bash
   # Single post
   python -m flyer_generator.social post \
       --brand-kit thunderstaff --platform linkedin --intent value-prop \
       --topic "Why RPA alternatives need on-prem execution" \
       --output /tmp/post

   # Campaign
   python -m flyer_generator.social campaign \
       --brand-kit hoyack --platforms linkedin,twitter,instagram \
       --topics /tmp/hoyack-topics.yaml \
       --output /tmp/hoyack-campaign-2026-q2
   ```

### Open questions the planner will need to surface

- **Scheduling/publishing?** Phase 19 scope should probably be "generate artifacts" — actual posting to platform APIs (LinkedIn, Twitter, Meta Graph) is a separate phase. User confirm.
- **Image policy per platform:** LinkedIn/Twitter/Instagram have very different aspect + size sweet spots. Do we generate one source hero (say 2048×2048) and crop per-platform, or regenerate per-platform? Tradeoff: cost vs. visual coherence.
- **Voice/tone consistency:** `BrandVoice` (in BrandKit today) has `tone`, `example_phrases`, `banned_words`. Phase 19 should actually WIRE those into `text_gen` (Phase 18 deferred this). Good candidate for Plan 01 of Phase 19.
- **Hashtag generation:** rule-based off keywords or LLM-generated? Probably LLM with brand-keyword seed.
- **Call-to-action rotation:** primary_cta / secondary_cta from brief; platform-appropriate wrapping ("Book a call" on LinkedIn vs. "DM us" on Instagram).
- **Compliance:** per-platform character limits, hashtag count caps, link-count caps (Instagram doesn't support links in captions; LinkedIn truncates at 3000 chars).
- **Existing social-media plan file?** `docs/workflows-pending/` is in the untracked list — might contain prior spec. Next session should grep it.

### Inputs ready for seeding

- `/tmp/shrubnet-brief.json`, `/tmp/hoyack-brief.json`, `/tmp/thunderstaff-brief.json` — these are already BrochureBrief-shaped. For posts, audience + voice + value_proposition + differentiators + CTAs are the fields that matter; offerings become post topic candidates.
- `.brand-kits/{shrubnet,hoyack,thunderstaff}/` — three kits with real scraped palettes + logos + typography.
- ComfyCloud workflows (`flyer_generator/workflows/*.json`) — 8 workflows with different aspect ratios. `turbo_portrait` (portrait, 1024×1792) is the closest to Instagram story / 4:5 post. `standard_square` (1024×1024) is already perfect for square posts.

### When you come back after `/clear`

1. `git log --oneline | head -10` — expect `272667f docs(quick-260421-epk)...` at top.
2. `python -m pytest tests/ -q -m "not slow"` — confirm 921/921 pass (2 slow deselected).
3. Read this HANDOFF.
4. Optional: `cat docs/workflows-pending/*.md 2>/dev/null | head -100` — check for prior social-media spec.
5. Run `/gsd-plan-phase` with intent "Phase 19 — Social Media Posting System" using §7 here as the spec source. Expect the planner to split into ~8-10 plans across 4-5 waves (parallel to Phase 18's shape).

---

## 8. TL;DR for next session

Phase 18 shipped. Brand kits work. Scraper works. Applier works (fixed one SVG XML bug today). Auto-audit now ships on every render by default. Ollama has retry + fallback chain. ComfyCloud works but poll budget needs a smart-fix (see §4A). Three real brand-kit brochures on disk across shrubnet/hoyack/thunderstaff. Next up: **Phase 19 — Social Media Posting System** using the same scrape-then-apply pattern, output post-shaped artifacts per platform. Spec in §7. Kick off with `/gsd-plan-phase`.

921/921 tests passing. All work committed. Safe to `/clear`.
