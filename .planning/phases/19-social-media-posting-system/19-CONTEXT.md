# Phase 19: Social Media Posting System — Context

**Gathered:** 2026-04-21
**Status:** Ready for planning
**Source:** HANDOFF.md §7 (user-authored spec, reviewed and approved pre-`/clear`)

<domain>
## Phase Boundary

Phase 19 delivers a **social-media post generator** that consumes Phase 18 brand kits and produces platform-compliant social posts as persistent artifacts (copy + image bytes + audit sidecar). The system is artifact-producing only — actual publishing to platform APIs (LinkedIn, Twitter/X, Meta Graph) is explicitly deferred to a future phase.

**In scope:**
- Four-platform support: LinkedIn, Twitter/X, Instagram, Facebook
- Per-platform `PlatformRules` (char limits, hashtag caps, aspect ratios, image byte caps) + `validate(post)` functions
- Post templates parallel to `flyer_generator/brochure/schema_renderer/templates/` — SVG-based, platform+intent keyed, ≥3 intents × 4 platforms (≥12 templates)
- Single-post CLI + campaign CLI (multi-platform from one topic, shared source hero cropped per-platform)
- BrandVoice wiring into `text_gen` (closes a Phase 18 deferred item)
- Audit extension: platform-rule compliance + existing contrast/density/whitespace checks
- Untracked storage under `.social-campaigns/<slug>/<campaign-id>/`; tracked `.social-template.json` schema reference
- Tests across all layers

**Out of scope:**
- Publishing / scheduling / posting to platform APIs
- Analytics / engagement tracking
- Video or carousel-with-multiple-images beyond template aspect
- Comment/reply generation
- A/B testing of post variants (can be a follow-up phase)

</domain>

<decisions>
## Implementation Decisions

### Module layout
- New package: `flyer_generator/social/`
- Submodules:
  - `platforms/linkedin.py`, `platforms/twitter.py` (alias `x.py` re-export), `platforms/instagram.py`, `platforms/facebook.py` — each exports `PlatformRules` + `validate(post)`
  - `schemas/` — post templates, one JSON per `<platform>__<intent>.json`
  - `models.py` — `Platform`, `Intent`, `PostSpec`, `Post`, `PostBrief`, `PlatformRules`, `ValidationReport`, `ValidationIssue`, `Campaign`
  - `generator.py` — `generate_post()` orchestrator
  - `campaign.py` — `generate_campaign()` orchestrator
  - `renderer.py` — SVG-based post renderer (thin wrapper that reuses `schema_renderer` rendering primitives)
  - `audit.py` — platform-aware audit extending `brand_kit.audit_render`
  - `storage.py` — `.social-campaigns/<slug>/<campaign-id>/` layout + env (`FLYER_SOCIAL_CAMPAIGNS_DIR`)
  - `voice.py` — `BrandVoice`-aware prompt assembly for `text_gen` (this module also lives here since it's the primary consumer)
  - `__main__.py` — typer CLI (`post`, `campaign`, `list-platforms`, `list-intents`, `show-rules`)
  - `__init__.py` — consolidated re-exports with sorted `__all__`

### Platforms (four, locked)
| Platform | Key rules | Primary image aspect | Secondary aspects |
|---|---|---|---|
| LinkedIn | body ≤3000 chars, hashtags inline, link preview metadata | 1200×627 (1.91:1 link preview) | 1200×1200 (1:1 in-feed) |
| Twitter/X | 280 char (standard tier, no premium detection), up to 4 images, optional thread | 1200×675 (16:9) | n/a initially |
| Instagram | caption ≤2200 chars, ≤30 hashtags, no in-caption links | 1080×1080 (1:1 feed), 1080×1350 (4:5 feed) | 1080×1920 (9:16 story variant) |
| Facebook | text + image, link preview, no hard char cap but recommended <500 for engagement | 1200×630 (link preview) | 1080×1080 (1:1) |

### Post intents (three initial, expandable)
- `announcement` — news/launch/event
- `value-prop` — educational/capability-highlight
- `testimonial` — quote-forward, proof-driven

Each platform × each intent = one schema file. ≥12 templates at ship.

### PostBrief fields (minimum)
- `topic` (required, str) — the subject
- `intent` (required, Intent enum)
- `platform` (required, Platform enum; for `generate_post`; campaign mode accepts a list)
- `cta` (optional, str) — overrides brand-kit-derived CTA
- `source_url` (optional, HttpUrl) — for link-preview metadata
- `image_hint` (optional, str) — seed phrase for ComfyCloud hero image
- `hashtags_seed` (optional, list[str]) — brand keywords to include

### Rendering pipeline
- For image-slotted posts: SVG template → `schema_renderer` rasterizer (CairoSVG primary, resvg fallback) → PNG bytes at target platform resolution
- For text-only posts (e.g. Twitter standard text tweet): no image artifact, just copy + metadata
- Brand-kit application uses **Phase 18's `apply_brand_kit`** with `size_multiplier` tuned per platform aspect (portraits need larger multipliers to keep text legible)

### Copy generation
- Reuse `flyer_generator/brochure/text_gen.py` — add a new entry `generate_social_copy(brief, brand_voice, platform_rules) → dict[str, str]`
- Prompt injects: `brand_voice.tone`, `brand_voice.example_phrases`, `brand_voice.banned_words` (as negative constraint), platform char-budget
- Post-generation pass: validate against `banned_words` (case-insensitive word-boundary match); reject + regenerate on violation (max 2 retries)
- Hashtag generation: **LLM-produced**, seeded by `brand_voice` keywords + topic; capped per-platform rules

### Image generation
- Reuse `flyer_generator/brochure/image_gate.py` + ComfyCloud client
- For single post: generate at template's declared `image_slot.aspect`
- For campaign: generate one source hero at the **largest requested resolution** (typically 2048×2048 for Instagram story / Facebook link preview union), then crop per-platform via Pillow
- Shared hero must preserve brand palette (use ComfyCloud workflow that accepts color constraints — reuse the existing `workflows/*.json` catalog; prefer `standard_square` for 1:1, `turbo_portrait` for 4:5/9:16, `turbo_landscape` for 16:9 / 1.91:1)

### Audit strategy
- Extend `brand_kit.audit_render` → new `flyer_generator/social/audit.py::audit_post(post, brand_kit, post_spec) → SocialAuditReport`
- Added dimensions:
  - `platform_compliance` — char-count vs budget, hashtag count vs cap, image aspect match (±2% tolerance), image byte size vs cap (platform-specific)
  - `link_policy` — warns if caption contains URL on a platform that strips links (Instagram)
  - `readability` — Flesch-Kincaid-ish heuristic for caption (warn if grade > 12)
- All existing contrast/density/whitespace checks apply to rendered imagery

### Storage layout
```
.social-campaigns/
  <brand_kit_slug>/
    <campaign_id>/
      campaign.json           # Campaign metadata (topic, platforms, created_at, brand_kit_slug)
      <platform>__<intent>/
        post.json             # Post metadata + copy + hashtags + validation + audit summary
        image.png             # if image slot; omitted for text-only
        audit.json            # full SocialAuditReport
      source_hero.png         # campaign mode only: the uncropped source image
```
- `FLYER_SOCIAL_CAMPAIGNS_DIR` env var (default `.social-campaigns/`) honored with path-traversal containment (mirror `brand_kit.storage`)
- `.social-campaigns/` added to `.gitignore`
- `.social-template.json` at repo root as tracked schema reference

### CLI surface
```
python -m flyer_generator.social post \
  --brand-kit <slug> --platform <linkedin|twitter|instagram|facebook> \
  --intent <value-prop|announcement|testimonial> \
  --topic "<topic>" [--cta "<cta>"] [--source-url <url>] [--image-hint "<hint>"] \
  --output <dir> [--campaign-id <id>] [--audit / --no-audit]

python -m flyer_generator.social campaign \
  --brand-kit <slug> --platforms linkedin,twitter,instagram[,facebook] \
  --topic "<topic>" [--intent <intent>] [--cta "<cta>"] \
  --output <dir> [--campaign-id <id>]

python -m flyer_generator.social list-platforms
python -m flyer_generator.social list-intents
python -m flyer_generator.social show-rules <platform>
```

Campaign-id defaults to a ULID; if `--output` is a campaign dir path, `<campaign-id>` is derived from its basename.

### BrandVoice wiring (Plan 01 candidate)
- `text_gen.generate_content_from_prompt(...)` currently does not accept `BrandVoice`.
- Plan 01 should:
  1. Add `brand_voice: BrandVoice | None = None` parameter
  2. If provided, prepend a "Voice directive" block to the system prompt: tone + example_phrases + banned_words
  3. Post-process: `_enforce_banned_words(text, banned_words)` raises `BrandVoiceViolationError` after max-retries
  4. This closes Phase 18's deferred item AND is reused by Phase 19's `generate_social_copy`
- New error: `BrandVoiceViolationError(BrandKitError)`

### Error hierarchy
- New: `SocialError(Exception)` — base
  - `PostValidationError(SocialError)` — hard validation failure
  - `PlatformUnsupportedError(SocialError)` — unknown platform
  - `IntentUnsupportedError(SocialError)` — unknown intent
  - `CampaignError(SocialError)` — campaign-level failure
- Extend `BrandKitError` tree with `BrandVoiceViolationError` (for text_gen wiring)

### Testing strategy
- Unit: platform validators (pass + every fail case), BrandVoice wiring (tone injection appears in prompt, banned-word filter rejects + retries + raises), template loading, storage containment, models round-trip
- Integration: mocked LLM + Comfy → `generate_post` produces `Post` with valid structure; `generate_campaign` produces matching set
- E2E smoke: one-shot against `thunderstaff` brand kit, LinkedIn value-prop, with mocked external services; real CairoSVG rasterize
- Gallery-style: generate one post per platform × per intent against a seeded brand kit, capture as test fixtures (not per-run CI — marked `slow`)

### Claude's Discretion
- Exact PostBrief schema additions beyond minimum — planner can extend
- Specific LLM prompt phrasing — planner/executor iterates
- Campaign-id format (ULID vs timestamp-hash) — pick whichever keeps filenames alphabetically sortable
- `readability` heuristic exact formula — choose a simple, dependency-free implementation
- Template layout specifics per template — text budgets, shape positions, image bounds — but must honor platform aspect + brand-kit palette slots

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 18 patterns to mirror
- `flyer_generator/brand_kit/models.py` — Pydantic v2 BrandKit + ColorUsage shape (new PostSpec/Post models follow the same nested-Optional style)
- `flyer_generator/brand_kit/applier.py` — immutable transform via `model_copy(deep=True)`, AA guardrail, font-stack normalization
- `flyer_generator/brand_kit/audit.py` — `AuditReport`, `AuditIssue`, severity/category/detail shape, `iterate_audit_loop` pattern
- `flyer_generator/brand_kit/storage.py` — env-var dir + slug regex + path-traversal guards (mirror exactly for `.social-campaigns/`)
- `flyer_generator/brand_kit/__main__.py` — typer CLI shape (fetch / list / show) — social CLI follows same pattern

### Rendering pipeline to reuse
- `flyer_generator/brochure/schema_renderer/content_model.py` — content models
- `flyer_generator/brochure/schema_renderer/` — template loading + rasterization entry points
- `flyer_generator/brochure/text_gen.py` — primary integration point for BrandVoice (this file is edited by Plan 01)
- `flyer_generator/brochure/image_gate.py` — ComfyCloud hero generation (wrapped, not duplicated)

### Error + LLM resilience
- `flyer_generator/errors.py` — error hierarchy extension point
- `flyer_generator/stages/llm_retry.py` — retry + fallback helper; reuse for social copy generation

### Roadmap + requirements
- `.planning/ROADMAP.md` §Phase 19 — goal + success criteria
- `.planning/REQUIREMENTS.md` — existing requirement IDs (Phase 19 introduces new SOC-* IDs if the planner adds them)

### User-authored spec
- `HANDOFF.md` §7 — user spec (this document is the ground truth for platform choice, CLI shape, storage layout)

### External (read via WebSearch / docs during research)
- LinkedIn post + image spec (char limits, 3000 body, image aspect)
- Twitter/X developer platform text length + media spec
- Instagram caption + hashtag policy (2200 chars, 30 hashtags, no in-caption links)
- Facebook post spec (link preview, recommended text length)

</canonical_refs>

<specifics>
## Specific Ideas

### First plan should be BrandVoice wiring
Per HANDOFF.md §7 "Open questions": Plan 01 = wire `BrandVoice` into `text_gen.generate_content_from_prompt`. This closes a Phase 18 deferred item, is unblocked (Phase 18's `BrandVoice` already ships), and is a prerequisite for all subsequent social copy generation. It's also testable in isolation — brochure tests can exercise voice-aware prompts before any social template exists.

### Campaign hero sharing is a cost optimization
One ComfyCloud generation per campaign vs. one per platform. At 260s wall-clock per hero (today's observed), a 4-platform campaign goes from ~17 min to ~4 min. Pillow crops add <1s. This is the single biggest cost lever in Phase 19.

### Hashtag generation uses LLM, seeded by brand
Do NOT rule-extract from body text. Ask the LLM for `{N}` platform-appropriate hashtags given brand keywords + topic, capped by platform rule. Fall through same `llm_retry` helper.

### Existing inputs to seed testing
- `.brand-kits/{shrubnet,hoyack,thunderstaff}/` — three live brand kits (gitignored) with real scraped palettes
- `/tmp/{shrubnet,hoyack,thunderstaff}-brief.json` — brochure briefs on disk; `audience`/`voice`/`value_proposition`/`differentiators`/`primary_cta` transfer directly to `PostBrief` for manual testing

### Existing ComfyCloud workflows already match platform aspects
- `standard_square` (1024×1024) → Instagram/Facebook 1:1 posts (upscale to 1080×1080 via Pillow)
- `turbo_portrait` (1024×1792) → Instagram 4:5 or 9:16 story (crop)
- `turbo_landscape` (1792×1024) → LinkedIn 1.91:1 + Twitter 16:9 (crop)
- No new workflows required.

### CairoSVG is the rasterizer of record
Same as brochure pipeline. resvg_py fallback kept for Cairo-free environments.

</specifics>

<deferred>
## Deferred Ideas

- **Publishing/scheduling:** Separate phase (Phase 20 candidate). Requires OAuth flows, rate-limit management, draft vs. publish state.
- **Video posts / Reels / TikTok:** Out of scope — image + text only.
- **Comment/reply generation:** Out of scope.
- **A/B variant generation:** Single post, single campaign. Variants are a future optimization.
- **Analytics ingestion:** Out of scope.
- **Twitter/X premium tier (4000 char):** v1 targets standard 280. Premium detection is a later concern.
- **Thread support in CLI:** If a LinkedIn body or Twitter copy naturally wants to be a thread, v1 returns a single post. Thread splitting can be a follow-up.
- **Carousel (multi-image) posts:** Single image per post in v1. Carousel is a post-type extension, not a platform primitive.
- **Link shortener integration:** `source_url` stored raw. Shortening deferred.

</deferred>

---

*Phase: 19-social-media-posting-system*
*Context gathered: 2026-04-21 from HANDOFF.md §7 (user-authored spec, auto mode)*
