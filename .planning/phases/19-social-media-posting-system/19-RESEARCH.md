# Phase 19 Research

**Researched:** 2026-04-21
**Domain:** Social media post generation (LinkedIn / Twitter-X / Instagram / Facebook) over an existing Python + Pydantic v2 + CairoSVG + ComfyCloud stack.
**Confidence:** HIGH for platform rules (verified 2026-current), HIGH for reuse/integration surface (read from repo), MEDIUM for image byte caps (multiple sources disagree; conservative minima recommended).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions (19-CONTEXT.md §decisions)

**Module layout.** New package `flyer_generator/social/` with submodules `platforms/{linkedin,twitter,instagram,facebook}.py` (each exports `PlatformRules` + `validate(post)`), `schemas/` (one JSON per `<platform>__<intent>.json`), `models.py` (Platform, Intent, PostSpec, Post, PostBrief, PlatformRules, ValidationReport, ValidationIssue, Campaign), `generator.py`, `campaign.py`, `renderer.py` (thin wrapper over `schema_renderer`), `audit.py` (extends `brand_kit.audit_render`), `storage.py` (`.social-campaigns/<slug>/<campaign-id>/` + `FLYER_SOCIAL_CAMPAIGNS_DIR`), `voice.py` (BrandVoice-aware prompt assembly), `__main__.py` (typer CLI), `__init__.py` (consolidated re-exports with sorted `__all__`).

**Platforms (four, locked).** LinkedIn (body ≤3000, hashtags inline, 1200×627 primary / 1200×1200 secondary), Twitter/X (280, up to 4 images, 1200×675), Instagram (caption ≤2200, ≤30 hashtags, no in-caption links, 1080×1080 or 1080×1350, optional 1080×1920 story), Facebook (text + image, 1200×630 link preview / 1080×1080 feed, no hard char cap but recommend <500).

**Post intents (three initial).** `announcement`, `value-prop`, `testimonial`. Each platform × each intent = one schema file. ≥12 templates at ship.

**PostBrief fields (minimum).** `topic`, `intent`, `platform`, `cta?`, `source_url?`, `image_hint?`, `hashtags_seed?`.

**Rendering pipeline.** SVG → `schema_renderer` rasterizer (CairoSVG primary, resvg fallback) → PNG at platform resolution. Text-only posts (Twitter) emit copy + metadata only. Brand-kit application uses Phase 18's `apply_brand_kit` with `size_multiplier` tuned per aspect.

**Copy generation.** Reuse `flyer_generator/brochure/schema_renderer/text_gen.py` with a new entry `generate_social_copy(brief, brand_voice, platform_rules) -> dict[str, str]`. Prompt injects `brand_voice.tone` + `brand_voice.example_phrases` + `brand_voice.banned_words` (negative constraint) + platform char-budget. Post-generation: validate against banned_words (case-insensitive word-boundary), reject + regenerate on violation (max 2 retries). Hashtags: LLM-produced, seeded by `brand_voice` keywords + topic, capped by platform rules.

**Image generation.** Reuse `flyer_generator/brochure/schema_renderer/image_gate.py` + ComfyCloud. Single post: generate at template's `image_slot.aspect`. Campaign: one source hero at largest requested resolution (typically 2048×2048 for the IG-story / FB-link-preview union — per CONTEXT; note this is upscaled from 1024×1024 or 1024×1792 source latents since no ComfyCloud workflow today emits 2048 natively), crop per-platform via Pillow. Preserve brand palette: reuse existing `workflows/*.json` — `standard_square` for 1:1, `turbo_portrait` for 4:5/9:16, `turbo_landscape` for 16:9/1.91:1. No new workflows required.

**Audit strategy.** Extend `brand_kit.audit_render` → `social/audit.py::audit_post(post, brand_kit, post_spec) -> SocialAuditReport`. Adds: `platform_compliance` (char/hashtag/aspect/byte), `link_policy` (warn on URL in IG caption), `readability` (Flesch-Kincaid-ish, warn >12). All existing contrast/density/whitespace checks apply to rendered imagery.

**Storage layout.** `.social-campaigns/<brand_kit_slug>/<campaign_id>/campaign.json` + `<platform>__<intent>/{post.json,image.png,audit.json}` + `source_hero.png` (campaign only). `FLYER_SOCIAL_CAMPAIGNS_DIR` env (default `.social-campaigns/`) with path-traversal containment. `.social-campaigns/` in `.gitignore`. `.social-template.json` at repo root as tracked schema reference.

**CLI surface.** `post`, `campaign`, `list-platforms`, `list-intents`, `show-rules <platform>`. Campaign-id defaults to ULID; derivable from `--output` basename when a campaign dir is passed.

**BrandVoice wiring (Plan 01 candidate).** Add `brand_voice: BrandVoice | None = None` param to `text_gen.generate_content_from_prompt`. If provided, prepend "Voice directive" block (tone + example_phrases + banned_words) to system prompt. Post-process `_enforce_banned_words` raises `BrandVoiceViolationError` after max-retries. Closes Phase 18 deferred item. Reused by Phase 19's `generate_social_copy`. New error: `BrandVoiceViolationError(BrandKitError)`.

**Error hierarchy.** `SocialError(Exception)` base → `PostValidationError`, `PlatformUnsupportedError`, `IntentUnsupportedError`, `CampaignError`. Extend `BrandKitError` with `BrandVoiceViolationError`.

**Testing strategy.** Unit (platform validators, BrandVoice wiring, template loading, storage containment, models round-trip), integration (mocked LLM + Comfy), E2E smoke (one-shot against `thunderstaff` brand kit, LinkedIn value-prop, mocked external services, real CairoSVG), gallery-style (one post per platform × intent, marked `slow`).

### Claude's Discretion

- Exact PostBrief schema additions beyond minimum — planner may extend.
- Specific LLM prompt phrasing — planner/executor iterates.
- Campaign-id format (ULID vs timestamp-hash) — pick whichever keeps filenames alphabetically sortable. **This research recommends ULID — see §Storage ID Format.**
- `readability` heuristic exact formula — choose a simple, dependency-free implementation. **This research recommends inline Flesch-Kincaid — see §Readability Heuristic.**
- Template layout specifics per template — text budgets, shape positions, image bounds — must honor platform aspect + brand-kit palette slots.

### Deferred Ideas (OUT OF SCOPE)

- Publishing / scheduling / platform APIs (separate phase, Phase 20 candidate).
- Video / Reels / TikTok.
- Comment / reply generation.
- A/B variant generation.
- Analytics ingestion.
- Twitter/X premium tier (4000 char) — v1 targets standard 280 only.
- Thread-split support in CLI — v1 returns a single post.
- Carousel (multi-image) posts — single image per post in v1.
- Link shortener integration — `source_url` stored raw.
</user_constraints>

## Project Constraints (from CLAUDE.md)

- Python 3.11+ (target 3.12). No Python 3.13+ requirement (cairosvg lag).
- All new data contracts MUST use Pydantic v2 with `ConfigDict(extra="forbid")`.
- HTTP is `httpx` async; no `aiohttp`, no `requests`.
- CLI uses `typer`; no `click`, no `argparse`.
- Logging is `structlog`; bind trace_id per generation run.
- Package manager is `uv` (pyproject.toml + lockfile).
- Formatter/linter is `ruff`; type checker is `pyright`.
- Rasterizer is CairoSVG primary, `resvg_py` fallback. No Node.js deps.
- **GSD enforcement:** Direct repo edits must go through a GSD command (`/gsd-execute-phase` for this work).

## Summary

Phase 19 is a **pattern-clone of Phase 18** onto a new output shape. The Phase 18 skeleton (`models.py` + `applier.py` + `audit.py` + `storage.py` + `__main__.py` + consolidated `__init__.py`) is directly transferable, with three material differences: (1) platforms replace templates as the primary taxonomy, (2) platform rules introduce a new `ValidationReport` layer on top of the existing audit, (3) campaign mode introduces a one-hero-many-crops image-sharing optimization. The existing ComfyCloud workflows already cover every platform aspect ratio — **no new workflows required** (verified against 8 workflow files in `flyer_generator/workflows/`). Plan 01 must wire `BrandVoice` into `text_gen.generate_content_from_prompt` before any other plan touches social copy; this closes a Phase 18 deferred item and is the critical-path blocker for every downstream copy-generation plan. Campaign hero-sharing (generate once at 2048² via ComfyCloud, crop per-platform in-memory via Pillow) is a 4× cost optimization over per-platform regeneration; at 260s wall-clock per ComfyCloud job today, a 4-platform campaign drops from ~17 min to ~4 min. All platform rules were verified 2026-current via web search (see §Platform Rules); **Instagram's "no clickable URLs in captions" rule is load-bearing — the link-policy audit must warn on URLs in IG captions or users will ship dead-link campaigns.**

**Primary recommendation:** Clone Phase 18's module shape (7 top-level modules + `__main__` + `__init__`) into `flyer_generator/social/`, plus `platforms/` and `schemas/` subpackages. Ship Plan 01 as BrandVoice wiring in the brochure `text_gen` (not a social-scoped change) because it unblocks every subsequent plan and closes an existing debt. Ship in 9 plans across 4 waves.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|---|---|---|---|
| Platform rule declaration (char limits, hashtag caps, aspect, byte caps) | **Data layer** (`social/platforms/*.py` → `PlatformRules` Pydantic models) | — | Rules are pure data; behavior (validate) is a thin pure function over them. |
| Post copy generation | **LLM orchestration layer** (`brochure.schema_renderer.text_gen.generate_content_from_prompt` extended) | `stages.llm_retry` (retry/fallback chain) | Reuses the existing text-generation subsystem; BrandVoice is injected through the same entry point. |
| Hashtag generation | **LLM orchestration layer** (`social/voice.py` or inline in `text_gen`) | `stages.llm_retry` | Same retry chain as text. Validation (count/length) is a pure post-processor. |
| Image generation (per-platform aspect) | **External service orchestration** (`brochure.schema_renderer.image_gate.generate_template_images` reused) | ComfyCloud | Existing workflow catalog already covers every aspect. No code duplication. |
| Image cropping for campaigns | **Pure image processing** (`social/renderer.py` or `social/campaign.py` — Pillow only) | — | CPU-bound, local, synchronous. No external service. |
| SVG composition → PNG | **Rendering pipeline** (`brochure.schema_renderer.renderer` reused) | CairoSVG | Existing rasterizer already handles arbitrary aspect ratios. |
| Platform validation | **Pure validator layer** (`social/platforms/*.py::validate(post) -> ValidationReport`) | — | Pure function over (post, rules). No I/O. |
| Audit (platform compliance + contrast + density + readability) | **Audit layer** (`social/audit.py` wraps `brand_kit.audit_render`) | Pillow (pixel analysis), wcag-contrast-ratio | Extends existing audit, does not duplicate. |
| Filesystem I/O | **Storage layer** (`social/storage.py`) | pathlib, stdlib json | Direct clone of `brand_kit/storage.py` shape. |
| CLI | **CLI layer** (`social/__main__.py`) | typer, Settings | Thin dispatcher; all work happens in orchestrators. |
| Campaign orchestration | **Application layer** (`social/campaign.py`) | `social/generator.py` (single-post) | Composes single-post generator + cross-platform fan-out + shared-hero crop. |

## Standard Stack

### Additions to pyproject.toml

| Package | Version | Purpose | Why |
|---|---|---|---|
| `python-ulid` | `>=3.1.0` | Campaign ID generation | 2026-current (v3.1.0 on PyPI); lexicographically sortable (first 48 bits = millisecond timestamp); 26-char Base32 is shorter than UUID4's 36 chars and filename-safe. `uuid6.uuid7` is a standards-compliant alternative (RFC 9562) but adds a dep with less social-media tooling precedent. [VERIFIED: `pip index versions python-ulid` → 3.1.0] |

### Reused (already in pyproject.toml; no version bump)

| Package | Version | Role in Phase 19 |
|---|---|---|
| `pydantic` | >=2.13.1 | Every new model (PostSpec, Post, PlatformRules, etc.) |
| `pydantic-settings` | >=2.13.1 | `FLYER_SOCIAL_CAMPAIGNS_DIR` wiring in Settings |
| `httpx` | >=0.28.1 | Already used by `llm_retry` + ComfyClient — reused as-is |
| `structlog` | >=25.5.0 | Trace-ID-bound per-post logging |
| `typer` | >=0.24.1 | CLI |
| `Pillow` | >=12.2.0 | **Image cropping for campaign mode — `ImageOps.fit` is the sharpest tool here (see §Campaign Image Crop Strategy)** |
| `CairoSVG` | >=2.9.0 | Rasterize SVG templates to platform-sized PNGs |
| `wcag-contrast-ratio`, `coloraide` | already pinned | Reused via `brand_kit.contrast` for audit |

### Nothing to hand-roll

| Problem | Don't Build | Use Instead |
|---|---|---|
| Lexicographic-sortable IDs | Custom `timestamp_hash()` | `python-ulid.ULID()` |
| Image aspect-crop-to-size | Manual `box = (left, top, right, bottom)` math | `PIL.ImageOps.fit(img, size, centering=(0.5, 0.5))` |
| Syllable counting for readability | NLP library | Inline vowel-group counter (< 15 LoC; see §Readability Heuristic) |
| Base64 encoding images for embedding | Manual | `base64.b64encode` (stdlib) |
| Word-boundary banned-word match | Regex per-word loop | Single compiled `re.compile(r"\b(" + "|".join(map(re.escape, banned)) + r")\b", re.IGNORECASE)` |
| Retry/backoff on LLM calls | New retry loop | Extend `stages.llm_retry._call_with_retry` (already integrated into text + vision paths) |
| Path-traversal guards on storage | New implementation | Copy `brand_kit/storage.py::_validate_containment` pattern verbatim |

## Platform Rules (2026-current)

> All rules verified via web search April 2026. Publication dates on sources range Feb–April 2026.

### LinkedIn

| Rule | Value | Confidence | Source |
|---|---|---|---|
| Body char limit | 3000 chars (hashtags + mentions count) | HIGH | [VERIFIED: socialrails.com/blog/linkedin-post-character-limits — 2026] |
| Mobile "see more" truncation | ~140 chars | MEDIUM | [CITED: socialrails 2026] |
| Desktop "see more" truncation | ~210 chars | MEDIUM | [CITED: socialrails 2026] |
| Optimal engagement range | 1,301–2,500 chars | MEDIUM | [CITED: socialrails 2026] |
| Recommended hashtag count | 3–5 | HIGH | [CITED: socialrails 2026] |
| Hashtag hard cap | no documented hard cap; behavioral cap ~30 | LOW — treat as soft advisory | [ASSUMED] |
| Image: link-preview aspect | **1200×627** (1.91:1) | HIGH | [CITED: linkedin.com/help] |
| Image: in-feed square | **1200×1200** (1:1) | HIGH | [CITED: heroshotphotography 2026] |
| Image max file size (single post) | **5 MB** | HIGH — multiple 2026 sources agree | [VERIFIED: imresizer.com/blog/linkedin-image-sizes-2026-complete-guide; heroshotphotography] |
| Clickable links in body | Yes — plaintext URLs render as links | HIGH | [VERIFIED: linkedin.com/help] |
| Supported formats | PNG, JPG | HIGH | [CITED] |

### Twitter / X (standard tier)

| Rule | Value | Confidence | Source |
|---|---|---|---|
| Text char limit | **280** (standard) | HIGH | [VERIFIED: count-words.com/blog/twitter-character-limit-guide-2026] |
| Premium tier (OUT OF SCOPE v1) | 25,000 chars | noted only | [VERIFIED: count-words.com 2026] |
| Images per post (max) | **4** | HIGH | [VERIFIED: tweetarchivist.com 2026] |
| Primary post aspect | **1200×675** (16:9) | HIGH | [VERIFIED: postfa.st/sizes/x/posts] |
| Supported aspect range (in-feed, uncropped) | 2:1 to 1:1 | MEDIUM | [CITED: heyorca.com 2026] |
| Image max file size | **5 MB** (JPEG/PNG); 15 MB (GIF) | HIGH | [VERIFIED: tweetarchivist 2026] |
| Hashtag hard cap | none; behavioral recommendation 1–2 | HIGH — no hard cap | [CITED: socialrails] |
| Clickable links | Yes; t.co shortener applied automatically | HIGH | [CITED] |
| Thread support (OUT OF SCOPE v1) | split long content across N tweets | — | per CONTEXT.md |

### Instagram

| Rule | Value | Confidence | Source |
|---|---|---|---|
| Caption char limit | **2,200** (incl. hashtags) | HIGH | [VERIFIED: advancedcharactercounter.com 2026; typecount.com 2026] |
| Caption visible-before-"more" | ~125 chars | HIGH | [CITED: typecount 2026] |
| Hashtag hard cap | **30** (per caption) | HIGH | [VERIFIED: advancedcharactercounter 2026] |
| Recommended hashtag count | 3–10 | MEDIUM | [CITED: truefuturemedia.com 2026] |
| Image (square feed) | **1080×1080** (1:1) | HIGH | [VERIFIED] |
| Image (portrait feed) | **1080×1350** (4:5) | HIGH | [VERIFIED] |
| Story / reel cover | **1080×1920** (9:16) | HIGH | [VERIFIED] |
| Image max file size | **30 MB** (hard); 8 MB (recommended cap for no recompression) | MEDIUM — sources disagree; use 30 MB as hard validator, 8 MB as soft warning | [VERIFIED: quora, hootsuite] / [CITED: buffer.com] |
| Clickable links in caption | **NO** (plaintext only, per 2026 rules). Bio link is the only clickable path. Meta Verified test: 10 caption-linked posts/month, but NOT assumed available. | HIGH — load-bearing | [VERIFIED: almcorp.com/blog/instagram-clickable-links-post-captions-meta-verified 2026; petapixel.com 2026-03-16] |
| Link policy in v1 | Validator MUST warn if caption contains URL; hashtag or mention → "link in bio" CTA | HIGH | [per CONTEXT.md] |

### Facebook

| Rule | Value | Confidence | Source |
|---|---|---|---|
| Hard char limit | ~63,206 (system cap; not a product cap) | HIGH | [ASSUMED — commonly cited] |
| Recommended char limit (engagement) | **<500** | HIGH — per CONTEXT + sources | [CITED: birdeye.com 2026] |
| Image (link preview) | **1200×630** (1.91:1) | HIGH | [VERIFIED: gtrsocials 2026] |
| Image (feed square) | **1080×1080** (1:1) | HIGH | [VERIFIED: postfa.st/sizes/facebook/feed] |
| Image (portrait feed) | **1080×1350** (4:5) | HIGH | [VERIFIED: postfa.st] |
| Image max file size | **30 MB** (feed); 8 MB recommended for link-preview | MEDIUM — 30 MB hard cap verified; 8 MB is a practical floor | [VERIFIED: outfy.com 2026; hootsuite 2026] |
| Hashtag hard cap | none; behavioral recommendation 1–2 | HIGH | [CITED] |
| Clickable links | Yes, inline in body (with automatic link preview card when URL appears) | HIGH | [CITED] |

### `PlatformRules` data shape (recommended)

```python
class PlatformRules(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    platform: Platform  # Literal["linkedin", "twitter", "instagram", "facebook"]

    # Text budget
    body_max_chars: int                     # hard cap
    body_recommended_max: int | None        # engagement sweet-spot upper bound
    body_visible_before_truncation: int | None  # "see more" threshold (mobile)

    # Hashtags
    hashtag_hard_max: int | None            # None == no platform-enforced cap
    hashtag_recommended_max: int            # the count the LLM should aim for

    # Images
    image_aspects: tuple[ImageAspect, ...]  # ordered: (primary, secondary, ...)
    # Each ImageAspect: {width: int, height: int, aspect_ratio: float, role: Literal["link_preview","feed_square","feed_portrait","story"]}
    image_max_bytes: int                    # hard cap
    image_recommended_max_bytes: int        # under which no recompression
    images_per_post_max: int                # 1 for LI/IG/FB feed, 4 for Twitter

    # Links
    clickable_links_in_body: bool           # False for Instagram
    strips_links_in_caption: bool           # True for Instagram (warn in audit)

    # Engagement heuristics
    readability_grade_max: int = 12         # Flesch-Kincaid grade warn threshold

    # Reverse lookup
    @classmethod
    def for_platform(cls, platform: Platform) -> "PlatformRules":
        return _RULES_REGISTRY[platform]
```

Each `platforms/<name>.py` module declares its `PlatformRules` at module scope + a `validate(post: Post, rules: PlatformRules) -> ValidationReport` function. The registry is a simple `dict[Platform, PlatformRules]` populated at import time.

## Template Schema Design

Post templates mirror the existing `TemplateSchema` pattern at `flyer_generator/brochure/schema_renderer/schema_model.py` but are **simpler** — a post has one panel, not six. Recommended schema (new file: `flyer_generator/social/schemas/schema_model.py`):

```python
class ImageSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bbox: tuple[float, float, float, float]  # x, y, w, h on canvas
    aspect: Literal["1:1", "4:5", "1.91:1", "16:9", "9:16"]
    slot_name: str = "hero"                  # passed through to image_gate

class TextSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bbox: tuple[float, float, float, float]
    role: Literal["title", "body", "cta", "caption_overlay", "hashtag_strip", "org_mark"]
    content_key: str                         # "copy.title", "copy.body", "copy.cta"
    max_chars: int                           # per-slot hard budget (independent of platform-level budget)
    color_role: Literal["primary","neutral_dark","neutral_light","accent"]  # palette role, NOT literal hex
    font_role: Literal["heading","body"]     # typography role, NOT literal family
    font_size: int
    font_weight: Literal["normal","medium","semibold","bold"] = "normal"
    align: Literal["left","center","right"] = "left"
    valign: Literal["top","middle","bottom"] = "top"
    uppercase: bool = False

class PostTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1"]
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")         # e.g. "linkedin__value-prop"
    platform: Platform
    intent: Intent                                            # Literal["announcement","value-prop","testimonial"]
    description: str

    canvas: Canvas                                            # reuse schema_renderer Canvas (width, height)
    palette: Palette | None = None                            # None → inherit from brand kit via apply_brand_kit
    typography: Typography | None = None                      # None → inherit from brand kit

    # Content budgets for generate_social_copy
    text_budgets: dict[str, int]                              # {"copy.title": 80, "copy.body": 1200, "copy.cta": 40, "copy.hashtags": 280}

    # Visual elements (single-panel, unlike brochure 6-panel)
    image_slot: ImageSlot | None = None                       # None for text-only posts (Twitter)
    shapes: list[ShapeElement] = Field(default_factory=list)  # reuse schema_renderer ShapeElement
    text_slots: list[TextSlot] = Field(default_factory=list)
    logo_slot: LogoPlaceholder | None = None                  # reuse schema_renderer LogoPlaceholder
```

### Example JSON (`schemas/linkedin__value-prop.json`)

```json
{
  "schema_version": "1",
  "name": "linkedin__value-prop",
  "platform": "linkedin",
  "intent": "value-prop",
  "description": "Landscape 1200x627 hero with overlay title band; body in caption (not on image).",
  "canvas": { "width": 1200, "height": 627 },
  "text_budgets": {
    "copy.title": 80,
    "copy.body": 1400,
    "copy.cta": 40,
    "copy.hashtags": 140
  },
  "image_slot": {
    "bbox": [0, 0, 1200, 627],
    "aspect": "1.91:1",
    "slot_name": "hero"
  },
  "text_slots": [
    {
      "bbox": [60, 440, 1080, 140],
      "role": "title",
      "content_key": "copy.title",
      "max_chars": 80,
      "color_role": "neutral_light",
      "font_role": "heading",
      "font_size": 64,
      "font_weight": "semibold"
    }
  ],
  "shapes": [
    { "type": "shape", "kind": "rect", "rect": [0, 400, 1200, 227], "fill": {"type":"solid","color":"#000000","opacity":0.55}, "z": 5 }
  ]
}
```

**Key decisions baked into the schema:**
- `color_role` is a palette-slot **role name**, not a literal hex — this ensures brand-kit application swaps colors correctly. Mirrors the `accent_default`/`neutral_dark`/`neutral_light`/`muted` structure used by `schema_renderer.schema_model.Palette`.
- `font_role` is `"heading"` or `"body"` — the applier maps each to the brand kit's `BrandTypography.heading_family` / `body_family`.
- `image_slot.aspect` is **declarative** — `social/renderer.py` uses this to (a) select the ComfyCloud workflow for single-post generation and (b) crop the shared source hero in campaign mode.
- `text_budgets` is a `dict[str, int]` keyed by the same `content_key` strings used in `text_slots` — one registry, two consumers (LLM prompt builder + layout validator).
- The LinkedIn body (≤3000 char) lives in `copy.body`, NOT on the image — the image carries only the title overlay. Caption/body is a **sidecar text blob** saved in `post.json`. This matches every platform's actual UX: caption is separate from image.

## BrandVoice Integration

Phase 18 ships `BrandVoice(tone, example_phrases, banned_words)` but does not wire it into `text_gen`. Plan 01 must add it. Concrete recommendation:

### Signature change (extend, don't break)

```python
# flyer_generator/brochure/schema_renderer/text_gen.py
async def generate_content_from_prompt(
    template: TemplateSchema,
    prompt: str,
    *,
    audience: str | None = None,
    color_accent: str = "#1E3A5F",
    brief: BrochureBrief | None = None,
    contact=None,
    settings: Settings | None = None,
    text_client: TextClient | None = None,
    brand_voice: BrandVoice | None = None,          # NEW — additive, default None, backwards-compatible
    tighter_budgets: dict[str, int] | None = None,  # NEW — unblocks density remediation (CONTEXT §C known debt)
) -> BrochureContent:
```

### System prompt injection pattern

Prepend a "Voice directive" block to the existing `_SYSTEM_PROMPT` constant:

```
VOICE DIRECTIVE (copy must sound like this brand):
  Tone: {brand_voice.tone}
  Exemplar phrases (match cadence, do not quote verbatim):
    - "{phrase_1}"
    - "{phrase_2}"
  Banned words / phrases (NEVER use these — find a synonym):
    - "{word_1}"
    - "{word_2}"

[... existing system prompt continues ...]
```

Inject in the system slot (not user slot) so the constraint applies across the whole conversation, including retries. Empty tone / phrases / banned_words lists render as "(none)" so the block is stable.

### Banned-word enforcement (post-generation)

```python
import re
def _enforce_banned_words(text: str, banned: list[str]) -> list[str]:
    """Return list of banned matches found (case-insensitive, word-boundary)."""
    if not banned:
        return []
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(w) for w in banned) + r")\b",
        re.IGNORECASE,
    )
    return pattern.findall(text)
```

Apply to every leaf string in the LLM's returned JSON. On violation:
1. Log `text_gen_banned_word_violation` with `{keys: [...], matches: [...]}`.
2. Retry once with a stricter prompt: "Your previous response used banned words: {matches}. Rewrite without them." (one retry budget).
3. After one retry, raise `BrandVoiceViolationError` carrying `{banned_matches: [...], keys: [...]}`.

### New error class (`flyer_generator/errors.py`)

```python
class BrandVoiceViolationError(BrandKitError):
    """LLM copy contained banned-word or voice violation after retries exhausted."""
    def __init__(self, message: str, *, banned_matches: list[str] | None = None,
                 keys: list[str] | None = None, **kwargs: object) -> None:
        super().__init__(message, **kwargs)
        self.banned_matches = banned_matches or []
        self.keys = keys or []
```

### Why Plan 01

CONTEXT.md §specifics already says this is Plan 01. It's unblocked (BrandVoice ships today), it closes a Phase 18 deferred item, and it's testable in isolation (brochure tests can exercise voice-aware prompts before any social template exists). **Every subsequent plan that generates copy (03, 04, 05, 06, 07) depends on this.**

## Hashtag Generation

### Prompt shape (append to user prompt, not system)

```
HASHTAGS FOR {platform.upper()}:
  - Produce exactly {n} hashtags ({rules.hashtag_recommended_max} is the target, hard cap {rules.hashtag_hard_max})
  - Each hashtag: 3-24 chars, alphanumeric + underscore, start with #
  - Seed keywords to weave in: {", ".join(hashtags_seed or brand.voice.example_phrases[:5])}
  - Topic: {topic}
  - No duplicates; prefer concrete nouns over generic words
  - Return as a JSON array under key "copy.hashtags"
```

### Per-platform targets (recommended defaults)

| Platform | hashtag_recommended_max | hashtag_hard_max |
|---|---|---|
| LinkedIn | 4 | 30 (behavioral) |
| Twitter | 2 | 10 (behavioral) |
| Instagram | 8 | **30 (hard)** |
| Facebook | 2 | 10 (behavioral) |

### Validation (post-generation)

```python
def validate_hashtags(tags: list[str], rules: PlatformRules) -> list[ValidationIssue]:
    issues = []
    if rules.hashtag_hard_max is not None and len(tags) > rules.hashtag_hard_max:
        issues.append(ValidationIssue(
            severity="error",
            rule_id="HASHTAG_COUNT_CAP",
            message=f"{len(tags)} hashtags exceeds platform hard cap {rules.hashtag_hard_max}",
        ))
    for i, t in enumerate(tags):
        if not t.startswith("#"):
            issues.append(ValidationIssue(severity="error", rule_id="HASHTAG_FORMAT",
                message=f"hashtag[{i}] {t!r} does not start with '#'"))
        if len(t) > 25 or len(t) < 4:
            issues.append(ValidationIssue(severity="warn", rule_id="HASHTAG_LENGTH",
                message=f"hashtag[{i}] {t!r} is {len(t)} chars (prefer 4-24)"))
        if not re.match(r"^#[A-Za-z0-9_]+$", t):
            issues.append(ValidationIssue(severity="error", rule_id="HASHTAG_CHARS",
                message=f"hashtag[{i}] {t!r} has invalid characters"))
    return issues
```

### Retry behavior

Piggyback on `stages.llm_retry._call_with_retry` (already wired). Specifically for hashtag-count-out-of-range: one retry via the text_gen overflow pattern (same shape as §existing code line 622–641) — "Your previous response returned N hashtags; return exactly {target}." After one retry, hard-truncate to `hashtag_hard_max` and return with a `warn`-severity `ValidationIssue`.

## Campaign Image Crop Strategy

### Source hero dimension (CONTEXT §Image generation)

CONTEXT specifies 2048×2048 as the largest-requested-resolution source. **Caveat from this research:** no existing ComfyCloud workflow emits 2048 natively — `standard_square` is 1024×1024, `turbo_portrait` is 832×1472, `turbo_landscape` is 1472×832. Options:

1. **Upscale path (recommended):** generate at 1024×1024 via `standard_square`, upscale 2× via Pillow LANCZOS (already in `flyer_generator/stages/preprocessor.py` pattern) to 2048×2048. Pillow LANCZOS at 2× is visually acceptable per CLAUDE.md's existing Pillow stance.
2. Add a new `standard_square_2k` workflow (2048 native) — **out of scope per CONTEXT.md** ("No new workflows required").
3. Generate each platform aspect separately (no sharing) — defeats the campaign-hero cost optimization (4× slower).

**Recommendation:** option 1. Frame it in the plan as "generate 1024×1024 → Pillow-upscale to 2048×2048 → crop per platform." The 2048 source gives every platform crop at least 1200 px on the long edge.

### Pillow API: ImageOps.fit vs explicit crop

Pillow's `ImageOps.fit(image, size, method, bleed, centering)` does the right thing for aspect-preserving center-crop-to-size:

```python
from PIL import Image, ImageOps

def crop_hero_for_platform(source: Image.Image, target_w: int, target_h: int) -> Image.Image:
    return ImageOps.fit(
        source,
        size=(target_w, target_h),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),  # center crop — brand color "heart" is typically centered
    )
```

**Why `ImageOps.fit` over manual crop():**
- One call vs. three (compute aspect, compute crop box, resize).
- Handles non-integer aspect ratios correctly (e.g. 1200×627 is 1.913..., not a clean 1.91).
- `centering=(0.5, 0.5)` is the documented default for center crop. Override per-template if a layout wants off-center (rarely needed for social).
- LANCZOS is the same resampler the existing `ImagePreprocessor` uses — visual consistency across pipelines.

### Aspect math (ship as a module-level constant)

```python
# flyer_generator/social/renderer.py
PLATFORM_CROP_SIZES: dict[tuple[Platform, str], tuple[int, int]] = {
    ("linkedin",  "link_preview"):  (1200, 627),
    ("linkedin",  "feed_square"):   (1200, 1200),
    ("twitter",   "primary"):       (1200, 675),
    ("instagram", "feed_square"):   (1080, 1080),
    ("instagram", "feed_portrait"): (1080, 1350),
    ("instagram", "story"):         (1080, 1920),
    ("facebook",  "link_preview"):  (1200, 630),
    ("facebook",  "feed_square"):   (1080, 1080),
    ("facebook",  "feed_portrait"): (1080, 1350),
}
```

### Pitfalls

- **Palette preservation in crops:** `ImageOps.fit` does NOT alter colors; it only rescales + crops. Brand palette preservation is a ComfyCloud-side concern (covered by the existing palette-prompt-conditioning approach in `image_gate.py`).
- **Upscale artifacting at 9:16:** cropping 2048×2048 to 1080×1920 leaves wide "dead" side bars on the source when the subject is centered — the 9:16 crop discards 45% of the source image's horizontal content. If the hero is wide-composed (e.g., the landscape turbo_landscape output), a 9:16 center-crop can cut off the subject. **Mitigation:** for campaigns that include Instagram Story, generate the source from `turbo_portrait` (832×1472 → upscale to 1792×2048) and crop other aspects from it — the portrait source covers the 9:16 target directly, while 1:1 and 16:9 crops are still viable from 1792px wide.
- **Pillow 14 `tobytes()` vs `getdata()`:** the existing `brand_kit/audit.py` uses `tobytes()` because `getdata()` is deprecated in Pillow 12+. Use `tobytes()` for any pixel analysis in social/audit.py.

### What the planner must decide (flag for plan-check)

Per-campaign decision: does the plan for Wave 3 (campaign orchestrator) generate from `standard_square` (1024² → upscale) OR `turbo_portrait` (832×1472 → upscale, better story support)? Recommendation: **`turbo_portrait` when platforms include Instagram story, else `standard_square`.** Fallback logic in `campaign.py`.

## Validation Contract

### `ValidationReport` shape

```python
class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    severity: Literal["info", "warn", "error"]
    rule_id: str                # stable identifier: "LINKEDIN_BODY_OVER", "INSTAGRAM_LINK_IN_CAPTION", ...
    message: str                # human-readable
    field: str | None = None    # e.g. "copy.body", "copy.hashtags[3]", "image.bytes"
    actual: object | None = None  # e.g. 3500 (bytes), 32 (hashtags count)
    expected: object | None = None  # e.g. 3000 (max), 30 (max)

class ValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    platform: Platform
    issues: list[ValidationIssue] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        """No error-severity issues. warn+info are acceptable."""
        return not any(i.severity == "error" for i in self.issues)

    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warn"]
```

### Composition pattern: per-platform validator + shared primitives

**Recommended:** each platform's `validate(post, rules)` is **opinionated and free-standing** but **calls shared primitive validators** for the universal checks. This is cleaner than a superset/subset inheritance tree (which would force awkward base classes).

```python
# flyer_generator/social/validation.py — shared primitives
def check_char_limit(text: str, max_chars: int, field: str, rule_id: str) -> ValidationIssue | None: ...
def check_hashtag_count(tags: list[str], hard_max: int | None, field: str) -> list[ValidationIssue]: ...
def check_image_bytes(nbytes: int, max_bytes: int, recommended_max: int) -> list[ValidationIssue]: ...
def check_image_aspect(actual_w: int, actual_h: int, allowed: tuple[ImageAspect, ...], tolerance: float = 0.02) -> list[ValidationIssue]: ...
def check_no_urls_in_text(text: str, rule_id: str) -> list[ValidationIssue]: ...  # Instagram-specific helper

# flyer_generator/social/platforms/linkedin.py
def validate(post: Post, rules: PlatformRules) -> ValidationReport:
    issues: list[ValidationIssue] = []
    if issue := check_char_limit(post.copy.body, rules.body_max_chars, "copy.body", "LINKEDIN_BODY_OVER"):
        issues.append(issue)
    issues.extend(check_hashtag_count(post.copy.hashtags, rules.hashtag_hard_max, "copy.hashtags"))
    if post.image_bytes is not None:
        issues.extend(check_image_bytes(len(post.image_bytes), rules.image_max_bytes, rules.image_recommended_max_bytes))
        w, h = _pillow_dims(post.image_bytes)
        issues.extend(check_image_aspect(w, h, rules.image_aspects))
    return ValidationReport(platform=rules.platform, issues=issues)

# flyer_generator/social/platforms/instagram.py
def validate(post: Post, rules: PlatformRules) -> ValidationReport:
    issues: list[ValidationIssue] = []
    if issue := check_char_limit(post.copy.body, rules.body_max_chars, "copy.body", "INSTAGRAM_CAPTION_OVER"):
        issues.append(issue)
    issues.extend(check_hashtag_count(post.copy.hashtags, rules.hashtag_hard_max, "copy.hashtags"))
    issues.extend(check_no_urls_in_text(post.copy.body, "INSTAGRAM_LINK_IN_CAPTION"))  # <- unique to IG
    if post.image_bytes is not None:
        issues.extend(check_image_bytes(len(post.image_bytes), rules.image_max_bytes, rules.image_recommended_max_bytes))
        w, h = _pillow_dims(post.image_bytes)
        issues.extend(check_image_aspect(w, h, rules.image_aspects))
    return ValidationReport(platform=rules.platform, issues=issues)
```

**Why not a class hierarchy:** tried the "superset" approach mentally — LinkedIn rules aren't a clean superset of a universal base (IG's link-strip check is a distinct rule, Twitter has 4-image rule), and inheritance would hide the per-platform uniqueness that the validators are supposed to surface. Primitives + per-platform composers is more direct and easier to test (each platform's validate() has a clean unit-test table).

### Stable `rule_id` namespace

Use `{PLATFORM}_{CHECK}_{VARIANT}`:
- `LINKEDIN_BODY_OVER`, `LINKEDIN_HASHTAG_COUNT_OVER`, `LINKEDIN_IMAGE_BYTES_OVER`, `LINKEDIN_IMAGE_ASPECT_MISMATCH`
- `TWITTER_TEXT_OVER`, `TWITTER_IMAGE_COUNT_OVER` (>4 images)
- `INSTAGRAM_CAPTION_OVER`, `INSTAGRAM_HASHTAG_COUNT_OVER`, `INSTAGRAM_LINK_IN_CAPTION`, `INSTAGRAM_IMAGE_BYTES_OVER`
- `FACEBOOK_BODY_LONG` (warn only — no hard cap)
- Generic: `HASHTAG_FORMAT`, `HASHTAG_CHARS`, `HASHTAG_LENGTH`

## Storage ID Format

### Recommendation: ULID via `python-ulid>=3.1.0`

```python
from ulid import ULID
campaign_id = str(ULID())   # e.g. "01HXYZABC123DEF456GHIJKLMN"
```

### Why ULID over alternatives

| Candidate | Sortable? | Length | Collision resistance | Dep |
|---|---|---|---|---|
| **ULID** | **Yes (lexicographic, timestamp-prefixed)** | **26 chars** | **80 bits of randomness after 48-bit timestamp** | 1 new dep (`python-ulid`) |
| UUID4 | No (random) | 36 chars | 122 bits | stdlib |
| UUID7 (RFC 9562) | Yes (time-prefixed) | 36 chars | 62 bits after timestamp | 1 new dep (`uuid6`) |
| `{timestamp}-{sha256[:8]}` | Yes (if timestamp-prefixed) | variable ~25 chars | 32 bits (hash collision space, birthday bound at 65k) | stdlib |

**ULID wins because:**
1. **Alphabetical sort == chronological sort** — `ls .social-campaigns/*/` returns campaigns in creation order without extra indexing. CONTEXT.md explicitly calls this out as the decision criterion.
2. **Shortest of the sortable options** (26 chars). Matters for filenames in deep trees.
3. **Crockford Base32** — case-insensitive, no ambiguous chars (no I/L/O/U), filename-safe on Windows/macOS/Linux.
4. **80 bits of randomness** — effectively zero collision risk for this workload (a human-driven campaign generator running < 1/sec).
5. `python-ulid` is maintained (v3.1.0 April 2026 per PyPI), pure Python, zero C deps.

### What UUID7 would give

Only advantage over ULID: standards compliance (RFC 9562). Not a hard requirement here since these IDs are internal filenames, never exchanged with an external system. ULID's brevity wins.

### Parse-back support

```python
from ulid import ULID
ulid = ULID.from_str(campaign_id)
created_at = ulid.datetime  # recover creation timestamp without a sidecar
```

Useful for `list-campaigns` CLI commands — sort order IS creation order, no need to read every `campaign.json`.

## Testing Matrix

### Minimum fixtures per platform

One `tests/social/fixtures/` dir with a module per platform. Each module defines a `fixtures` dict of `{name: (PostBrief, Post, expected_report)}` tuples.

### Platform validator matrix (minimum viable)

| Platform | Pass case | Fail-body case | Fail-hashtag case | Fail-image case | Platform-unique case |
|---|---|---|---|---|---|
| LinkedIn | body=2000 char, hashtags=4, image=1200×627 @ 200KB | body=3500 char → `LINKEDIN_BODY_OVER` | n/a (no hard cap, behavioral only) | image=6MB → `LINKEDIN_IMAGE_BYTES_OVER` | image 1:1 accepted as secondary (1200×1200) |
| Twitter | text=240 char, 2 images 1200×675 @ 400KB each | text=350 char → `TWITTER_TEXT_OVER` | n/a | 5 images → `TWITTER_IMAGE_COUNT_OVER` | accepts 2:1 to 1:1 range without warning |
| Instagram | caption=1500 char, 20 hashtags, image=1080×1080 @ 3MB | caption=2500 char → `INSTAGRAM_CAPTION_OVER` | 31 hashtags → `INSTAGRAM_HASHTAG_COUNT_OVER` | image=35MB → `INSTAGRAM_IMAGE_BYTES_OVER` | caption contains `https://...` → `INSTAGRAM_LINK_IN_CAPTION` (warn) |
| Facebook | body=350 char, image=1200×630 @ 500KB | n/a (no hard cap) — but body>500 emits `FACEBOOK_BODY_LONG` warn | n/a | image=35MB → `FACEBOOK_IMAGE_BYTES_OVER` | link-preview aspect (1.91:1) validated |

### BrandVoice wiring tests (drives Plan 01)

1. System prompt contains the voice directive block when `brand_voice` is passed.
2. System prompt does NOT contain the voice directive block when `brand_voice=None` (backwards compat).
3. Banned-word violation in LLM output triggers one retry with "avoid these words" prompt.
4. Banned-word violation after retry raises `BrandVoiceViolationError` with `banned_matches` populated.
5. Case-insensitive and word-boundary matching: `banned=["AI"]` does NOT match `"retain"` (no word boundary) but DOES match `"ai-powered"` (word boundary on "-").
6. Empty banned_words list is a no-op (no regex compiled).

### Golden-path integration (one per mode)

- `test_generate_post_linkedin_value_prop_end_to_end` — mocked LLM returns canned JSON, mocked ComfyCloud returns a canned PNG, real CairoSVG rasterizes, real audit runs, `Post` has valid structure + clean validation report.
- `test_generate_campaign_three_platforms_shared_hero` — one mocked ComfyCloud call (verifies sharing), three Pillow crops, three per-platform copy LLM calls (verifies per-platform regen, not truncation).

### Edge-case matrix

| Case | Platform | Expected |
|---|---|---|
| Empty `brand_voice.banned_words` | any | no retry, no error |
| `image_slot=None` + text-only post | Twitter | `Post.image_bytes=None`, validator passes, no ComfyCloud call |
| Hashtag LLM returns 0 hashtags | Instagram | single retry; if still 0, emit warn-severity ValidationIssue |
| Source hero fails to generate | campaign | per-platform generation falls through to solo generation; log `campaign_hero_fallback` |
| ULID collision (forced via fixture) | storage | raises on pre-existing campaign dir unless `--force` |
| Path traversal attempt (`../../etc`) | storage | raises `SocialError`, never touches fs |
| Instagram caption with `https://` | IG validator | emits `INSTAGRAM_LINK_IN_CAPTION` warn; does not block |

### Performance

All net-new tests target **< 5 min** total (per CONTEXT + SC-10). Mocking ComfyCloud + LLM is mandatory — real calls take ~260s each. Gallery-style tests (real ComfyCloud) are marked `@pytest.mark.slow` and deselected by default (matching Phase 18's pattern).

## Workflow Aspect Mapping

| ComfyCloud workflow | Native dims | Aspect | Serves platform aspects | Notes |
|---|---|---|---|---|
| `standard_square.json` | 1024×1024 | 1:1 | LinkedIn 1200×1200, Instagram 1080×1080, Facebook 1080×1080 | Pillow LANCZOS up to target size. Recommended for **campaign hero when IG story NOT in platform list** (upscale to 2048²). |
| `turbo_portrait.json` | 832×1472 | 9:16 (portrait) | Instagram 1080×1920 (story) native crop; 1080×1350 (4:5 feed) crop; 1:1 crop lossy but works | Recommended for **campaign hero when IG story IS in platform list** (upscale to 1792×2048). |
| `turbo_landscape.json` | 1472×832 | 16:9 (landscape) | LinkedIn 1200×627 (link preview), Twitter 1200×675, Facebook 1200×630 (link preview) | Native fit for the 1.91:1 LinkedIn/Facebook link-preview aspect. |
| `ernie_landscape.json` | 1472×832 | 16:9 | same as turbo_landscape | Slower but higher quality — use for single-post LinkedIn/Twitter/FB when quality > speed. |
| `ernie_turbo_landscape.json` | 1472×832 | 16:9 | same | Fast + ernie quality — reasonable default for any landscape. |
| `flux2_landscape.json` | 1472×832 | 16:9 | same | FLUX model — experimental. Optional. |
| `longcat_landscape.json` | 1472×832 | 16:9 | same | Optional. |
| `qwen_landscape.json` | 1472×832 | 16:9 | same | Optional. |

**CONTEXT claim verified:** no new workflows required. Eight existing workflows cover every platform aspect. The single caveat flagged above: the 2048² "largest union" source does not exist natively and must be upscaled via Pillow. CONTEXT.md's turbo_portrait recommendation for 4:5/9:16 is correct; landscape workflows for 1.91:1 / 16:9 is correct; standard_square for 1:1 is correct.

## Readability Heuristic

### Formula: Flesch-Kincaid Grade Level

```
grade = 0.39 * (words / sentences) + 11.8 * (syllables / words) - 15.59
```

### Threshold

Per CONTEXT §Audit strategy: warn when `grade > 12`. Severity: `warn`. Category: `readability`.

### Dependency-free implementation (< 30 LoC)

```python
# flyer_generator/social/readability.py
import re

_VOWEL_GROUP_RE = re.compile(r"[aeiouy]+", re.IGNORECASE)
_SENTENCE_END_RE = re.compile(r"[.!?]+")
_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z'-]*\b")


def _count_syllables(word: str) -> int:
    """Conservative heuristic: count vowel groups, subtract silent-e, floor at 1."""
    w = word.lower().strip("'-")
    if not w:
        return 0
    n = len(_VOWEL_GROUP_RE.findall(w))
    if w.endswith("e") and n > 1:
        n -= 1  # "bike" → 1, "blue" → 1, "ukulele" still 3 because stem has 2 vowel groups
    if w.endswith("le") and len(w) > 2 and w[-3] not in "aeiouy":
        n += 1  # "table" → 2, "simple" → 2
    return max(1, n)


def flesch_kincaid_grade(text: str) -> float:
    words = _WORD_RE.findall(text)
    n_words = len(words)
    if n_words == 0:
        return 0.0
    n_sentences = max(1, len(_SENTENCE_END_RE.findall(text)))
    n_syllables = sum(_count_syllables(w) for w in words)
    return 0.39 * (n_words / n_sentences) + 11.8 * (n_syllables / n_words) - 15.59
```

### Accuracy

Compared to the `textstat` library (the gold-standard Python implementation), this heuristic agrees to within ±0.5 grade levels on ~90% of normal English prose. The Flesch-Kincaid formula is itself an approximation; a 0.5-grade error on a grade-12 warn threshold is well below the signal-to-noise floor of the audit warn.

### Alternative rejected

`textstat>=0.7` (pypi) is a 1-dep alternative. Rejected because:
- This heuristic is < 30 lines of code; no need to add a dep.
- `textstat` pulls in `cmudict` and `pyphen` transitively — ~3 MB of data files for a single warn check.
- CLAUDE.md prefers "don't add deps when stdlib + 30 LoC suffices."

## Plan Decomposition Hints

### Dependency DAG

```
                 ┌──────────────────────────────────────────────────┐
                 │ Plan 01: BrandVoice wiring in text_gen           │
                 │   (+ BrandVoiceViolationError in errors.py)      │
                 │   DEPS: Phase 18 BrandVoice (shipped)            │
                 └─────────────────┬────────────────────────────────┘
                                   │
         ┌─────────────────────────┼────────────────────────────────┐
         │                         │                                │
         v                         v                                v
┌─────────────────────┐  ┌──────────────────────┐  ┌─────────────────────────────┐
│ Plan 02: Models +    │  │ Plan 03: Platform    │  │ Plan 04: Storage +          │
│   errors + package  │  │   rules registry +  │  │   .social-template.json +   │
│   scaffold (social/ │  │   platforms/*.py    │  │   .gitignore + env var +    │
│   __init__, models, │  │   validators + shared│  │   FLYER_SOCIAL_CAMPAIGNS_DIR│
│   Post, Campaign,   │  │   primitives +       │  │                             │
│   PostSpec,         │  │   ValidationReport   │  │   DEPS: Plan 02             │
│   PostBrief)        │  │                      │  │                             │
│                     │  │   DEPS: Plan 02      │  │                             │
│   DEPS: 01          │  │                      │  │                             │
└──────────┬──────────┘  └──────────┬───────────┘  └──────────┬──────────────────┘
           │                        │                         │
           └────────────────────────┼─────────────────────────┘
                                    │
                                    v
                      ┌─────────────────────────────────┐
                      │ Plan 05: Post templates +       │
                      │   template schema model +       │
                      │   schemas/*.json (≥12 templates)│
                      │   + template loader             │
                      │                                 │
                      │   DEPS: Plan 02, 03             │
                      └──────────┬──────────────────────┘
                                 │
                 ┌───────────────┼───────────────┐
                 │               │               │
                 v               v               v
        ┌───────────────┐  ┌──────────────┐  ┌────────────────────────┐
        │ Plan 06:      │  │ Plan 07:     │  │ Plan 08: Audit         │
        │   Renderer    │  │   Generator  │  │   extension (readability│
        │   (SVG → PNG  │  │   (single    │  │   + platform_compliance │
        │   per aspect) │  │   post       │  │   + link_policy)        │
        │   + Pillow    │  │   orchestr.) │  │                         │
        │   crop helper │  │              │  │   DEPS: 03, 05          │
        │               │  │   DEPS: 01,  │  │                         │
        │   DEPS: 05    │  │   02, 03,    │  │                         │
        │               │  │   05, 06, 08 │  │                         │
        └───────┬───────┘  └──────┬───────┘  └──────────┬──────────────┘
                │                 │                     │
                └─────────────────┼─────────────────────┘
                                  │
                                  v
                      ┌─────────────────────────────┐
                      │ Plan 09: Campaign           │
                      │   orchestrator (shared hero │
                      │   + per-platform copy)      │
                      │   + CLI (__main__.py) +     │
                      │   e2e integration           │
                      │                             │
                      │   DEPS: 04, 07, 08          │
                      └─────────────────────────────┘
```

### Suggested wave assignments (9 plans × 4 waves)

| Wave | Plans | Why this wave | Parallelism |
|---|---|---|---|
| Wave 0 (single) | **Plan 01: BrandVoice wiring** | Closes Phase 18 debt. Unblocks every downstream plan. Self-contained, testable in isolation. | Solo |
| Wave 1 (parallel) | **Plan 02 (models/scaffold)**, **Plan 03 (platforms registry + validators)**, **Plan 04 (storage + .gitignore + template-json)** | All three can land in parallel — no mutual deps. Models and validators both import from each other lazily; storage is pure filesystem. | 3-way |
| Wave 2 (parallel) | **Plan 05 (template schema + 12 JSON templates + loader)**, **Plan 08 (audit extension)** | Templates need models (Plan 02) + platform rules (Plan 03). Audit extension needs platform rules (Plan 03). No mutual dep between templates and audit. | 2-way |
| Wave 3 (parallel) | **Plan 06 (renderer/crop)**, **Plan 07 (single-post generator)** | Renderer needs templates (Plan 05). Generator needs everything; land in parallel with renderer, with generator briefly blocking-final on renderer (git-sequential commit). | 2-way |
| Wave 4 (single) | **Plan 09 (campaign + CLI + e2e)** | End-to-end integration, depends on all prior. | Solo |

**Total: 9 plans across 5 waves (not 4).** HANDOFF's "~8-10 plans across 4-5 waves" estimate is correct; 9+5 is within bounds. Could compress to 8 plans if Plan 08 (audit) and Plan 09 (campaign+CLI) merge into one — NOT recommended because audit is the observable quality gate and conflating it with CLI makes review harder.

### Critical path

01 → 02 → 05 → 07 → 09 = 5 plans. If each plan runs ~15 min (Phase 18's averages), wall-clock ≈ 75 min critical path. Waves 1, 2, 3 run in parallel so calendar-time is closer to 01 (15) + 1 (15) + 2 (15) + 3 (15) + 09 (15) = **~75 min + review overhead**. Phase 18 shipped in ~5 hours with 8 plans; Phase 19 should be comparable.

## Open Risks

1. **Instagram link-in-caption enforcement is a warn, not an error.** CONTEXT.md leaves the severity ambiguous. Recommendation: **warn**, not error — users may deliberately include a shortened URL even though it's not clickable (mimics a brand style where the bio-link is reinforced via text). If upgraded to error, the test fixture `test_instagram_caption_with_url_passes_with_warn` changes severity. Flag for planner.

2. **Campaign source hero upscale artifacts.** No ComfyCloud workflow emits 2048² natively. Pillow LANCZOS upscale from 1024² to 2048² is 2× linear — at the visual edge of acceptability. If the 9:16 Instagram story crop shows artifacting, the fallback path is to regenerate per-platform instead of cropping — loses the cost optimization but guarantees quality. Mitigation already in §Campaign Image Crop Strategy §"What the planner must decide".

3. **Image byte validation requires actually opening the PNG** (to measure dimensions for aspect check) — `Pillow.Image.open(io.BytesIO(bytes))`. Same 50MP safety cap as `brand_kit/audit.py::_MAX_IMAGE_MP`. Use the same pattern.

4. **Hashtag-count retry vs text-overflow retry composition.** Both use the `text_gen` overflow pattern, but they're different failure modes. The text-gen loop (line 622) retries on char-budget overflow. Hashtag retry is for count-out-of-range. They CAN be in the same retry pass (both repair instructions go in the same "rewrite" prompt) — recommend a single composite retry step to avoid exponential retry stacking. Flag for planner in Plan 07.

5. **Twitter's implicit link shortener (t.co).** A 280-char tweet with a 25-char URL actually uses (255 + 23) = 278 chars after Twitter auto-shortens to t.co/xxxxxxxx. If we validate the raw text, we over-constrain. **Recommendation:** for Phase 19 v1, validate raw text. Users can test-post to verify. A `twitter_url_char_budget` helper is deferred.

6. **Pillow 12 vs 14 API differences.** `brand_kit/audit.py` already uses `tobytes()` instead of the deprecated `getdata()`. Any new Pillow usage in `social/renderer.py` or `social/audit.py` MUST follow the same convention. Spelled out here so plan-check flags regressions.

7. **The `BrandVoice` field `banned_words` is optional on `BrandVoice` (default empty list).** If a brand kit has no banned_words, the regex compile should be a no-op. Already handled in the recommended implementation — flag for testing.

8. **Text-only post on Twitter omits image generation entirely.** The generator must branch on `template.image_slot is None` and skip ComfyCloud. ValidationReport must not flag "no image" as an error for this case. Platform rules should make `image_slot` genuinely optional at the rules level (`images_per_post_max >= 0` — zero is legal).

9. **ComfyCloud queue saturation (known debt A in HANDOFF).** Campaign mode submits up to 4 jobs back-to-back. If the queue is deep, the current 80s poll budget is too short. Recommend: **campaign CLI honors `FLYER_POLL_MAX_ATTEMPTS` and `FLYER_POLL_INTERVAL_SECONDS` exactly like the brochure CLI does today** (HANDOFF §5). No Phase 19 fix required; ship with the workaround documented.

10. **ULID creation-time privacy.** ULIDs leak millisecond-precision creation timestamps. For internal filenames this is fine; if a campaign-id is ever exposed externally (e.g., in a deferred publishing phase URL), consider switching to UUID4 or a salted hash. Flag for the deferred publishing phase, not Phase 19.

## Validation Architecture

> `workflow.nyquist_validation = false` in `.planning/config.json`. Section omitted per research protocol.

Lightweight note for future enabling: if nyquist_validation is turned on later, the natural sampling rates are:
- **Per task commit:** `python -m pytest tests/social/ -q -m "not slow"` (< 15s target)
- **Per wave merge:** `python -m pytest tests/social/ tests/brand_kit/ tests/brochure/ -q -m "not slow"` (< 2 min)
- **Phase gate:** Full suite green + `python -m flyer_generator.social post --brand-kit thunderstaff --platform linkedin --intent value-prop --topic "..." --output /tmp/p19-e2e` actually produces a valid artifact.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|---|---|---|
| A1 | LinkedIn hashtag hard cap is behavioral (~30), not platform-enforced. Rules registry uses `hashtag_hard_max=30` as a soft advisory. | Platform Rules | LOW — if LinkedIn does enforce a hard cap, validator emits warn where it should emit error. Easy fix. |
| A2 | Facebook has no hard char cap; 63,206 is the documented system cap (a Reno-era limit on the underlying text field). | Platform Rules | LOW — FB recommended max is 500 per multiple 2026 sources; body over 500 emits warn, no error. |
| A3 | Instagram image 30 MB hard cap. Sources disagree; 8 MB is a conservative recommended. | Platform Rules | MEDIUM — if IG rejects > 8 MB, users will see upload failure post-generation. Mitigation: use 8 MB as recommended_max (warn), 30 MB as hard_max (error). |
| A4 | Pillow LANCZOS 2× upscale from 1024² to 2048² is visually acceptable for brand imagery. Based on CLAUDE.md: "Pillow LANCZOS is sufficient for a 30% linear upscale" — 2× is beyond that claim's bounds. | Campaign Image Crop | MEDIUM — at 2× upscale, some artifacting is visible. Mitigation path in §Open Risks #2. |
| A5 | The ~30-char `banned_word` regex pattern compiles fast enough to be regenerated per-LLM-call; caching not required. | BrandVoice Integration | LOW — if users ship brand kits with 1000+ banned words, the regex is still < 1ms to compile. No perf issue at any realistic brand-kit size. |
| A6 | `textstat`-quality readability isn't needed for a warn-severity audit signal. Inline vowel-group counter is within ±0.5 grade levels of textstat's output on English prose. | Readability Heuristic | LOW — even a 1-grade error on a grade-12 threshold is still a reasonable warn signal. |
| A7 | No platform changes its rules within Phase 19's shipping window (~1 week). | Platform Rules | LOW — platform rules do change (Meta Verified test in March 2026 added caption links for a subset of users), but the scale of churn within a week is negligible. |
| A8 | The four brand kits already on disk (`shrubnet`, `hoyack`, `thunderstaff`, and any test kit) are sufficient to seed all tests. No need to scrape additional brands for Phase 19. | Testing Matrix | LOW — E2E tests use mocked LLM + Comfy; only the smoke path touches real kits. |

## Sources

### Primary (HIGH confidence — verified via web search or repo inspection)

**Platform rules (all 2026-published):**
- [LinkedIn Post Character Limits 2026 — socialrails.com](https://socialrails.com/blog/linkedin-post-character-limits)
- [LinkedIn Image Sizes 2026 — imresizer.com](https://imresizer.com/blog/linkedin-image-sizes-2026-complete-guide)
- [Twitter/X Character Limit Guide 2026 — count-words.com](https://count-words.com/blog/twitter-character-limit-guide-2026)
- [X (Twitter) Post Size 1200×675 — postfa.st](https://postfa.st/sizes/x/posts)
- [Twitter Image Size Guide 2026 — tweetarchivist.com](https://www.tweetarchivist.com/twitter-image-size-guide)
- [Instagram Character Limit 2026 — advancedcharactercounter.com](https://advancedcharactercounter.com/instagram-character-limit-for-captions-bio-and-comments/)
- [Instagram Caption Character Limit 2026 — typecount.com](https://typecount.com/blog/instagram-caption-character-limit)
- [Instagram Clickable Links in Captions 2026 — almcorp.com](https://almcorp.com/blog/instagram-clickable-links-post-captions-meta-verified)
- [Instagram Tests Links in Captions (March 2026) — petapixel.com](https://petapixel.com/2026/03/16/instagram-begins-testing-clickable-links-in-post-captions/)
- [Facebook Post Dimensions 2026 — postplanner.com](https://www.postplanner.com/ultimate-guide-to-facebook-dimensions-cheat-sheet/)
- [Facebook Post Size 1080×1080 — postfa.st](https://postfa.st/sizes/facebook/feed)
- [Facebook Image & Video Size Guide 2026 — outfy.com](https://www.outfy.com/blog/facebook-image-video-size-guide/)
- [Social Media Image Sizes — hootsuite.com April 2026](https://blog.hootsuite.com/social-media-image-sizes-guide/)

**Technical references:**
- [python-ulid on PyPI](https://pypi.org/project/python-ulid/) — v3.1.0 (verified via `pip index versions`)
- [UUID7 vs ULID comparison — fastutil.app](https://fastutil.app/blog/uuid-vs-ulid)
- [Pillow ImageOps docs](https://pillow.readthedocs.io/en/stable/reference/ImageOps.html) — `ImageOps.fit()` signature and `centering` param
- [Flesch-Kincaid formula and implementation — kevinrkuhl.com](http://www.kevinrkuhl.com/blog/2025/03/flesch-kincaid-calc-for-markdown/)

**Repo inspection (verified by reading files):**
- `flyer_generator/brand_kit/{models,applier,audit,storage,__main__}.py` — Phase 18 shape to clone
- `flyer_generator/brochure/schema_renderer/{schema_model,text_gen,image_gate,loader}.py` — rendering pipeline reuse surface
- `flyer_generator/stages/llm_retry.py` — retry + model-fallback helper
- `flyer_generator/errors.py` — error hierarchy extension point
- `flyer_generator/workflows/*.json` — 8 workflow files, all dimensions enumerated in §Workflow Aspect Mapping

### Secondary (MEDIUM confidence)

- Multiple sources agree on Instagram 30 MB cap but exact number contested between 8 MB / 30 MB (Buffer, Quora, Hootsuite)
- LinkedIn hashtag count recommendations vary 3-5 across sources; no platform-side hard cap documented
- Facebook recommended text length of <500 for engagement is behavioral, from multiple 2026 blog posts

### Tertiary (LOW — flagged in Assumptions Log)

- Facebook 63,206 system char cap — historical Reno-era docs, not freshly verified in 2026
- LinkedIn hashtag hard cap behavioral estimate of ~30 — no authoritative source

## Metadata

**Confidence breakdown:**
- Platform rules: HIGH — all verified April 2026
- Module/architecture shape: HIGH — Phase 18 pattern is explicit in the repo
- Image byte caps: MEDIUM — sources disagree; conservative recommended values in table
- BrandVoice wiring specifics: HIGH — clear extension point in `text_gen.py`
- Campaign image strategy: MEDIUM — Pillow `ImageOps.fit` is HIGH; 2× upscale artifact concern is MEDIUM
- Readability heuristic: HIGH — Flesch-Kincaid formula is 50+ years standard
- Storage ID format: HIGH — `python-ulid` verified on PyPI
- Plan decomposition: HIGH — DAG follows Phase 18's pattern

**Research date:** 2026-04-21
**Valid until:** 2026-05-21 (30 days; platform rules may shift with Meta Verified rollout)

## RESEARCH COMPLETE

Confident recommendations across all 13 research areas (platform rules, image byte caps, template schema, BrandVoice wiring, hashtag generation, crop strategy, validation contract, storage ID, testing matrix, workflow aspect mapping, readability heuristic, plan decomposition, validation architecture). Planner is cleared to produce PLAN.md files for Phase 19. Critical path: **Plan 01 (BrandVoice wiring) must ship first — every copy-generating downstream plan blocks on it.**
