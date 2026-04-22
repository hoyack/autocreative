# Flyer, Brochure, Social Post & Brand Kit Generator

AI-assisted creative production for small-to-mid-sized brands. The repo takes a
website URL, a JSON brief, or a plain-English sentence and produces:

- **Event flyers** — 1080×1920 PNG, AI hero image + vision-placed text
- **Tri-fold brochures** — print-ready outside + inside PNGs + PDF (prompt-driven or schema-driven)
- **Social-media posts** — platform-correct LinkedIn, Twitter/X, Instagram, Facebook posts with brand-aware backdrops, copy, and adversarial audit
- **Brand kits** — scrape a website → extracted palette, typography, logos, voice directive → apply to any template

Every subsystem shares the same ComfyCloud image pipeline, Claude (or Ollama)
text + vision stack, CairoSVG rasterizer, and WCAG-AA contrast guardrails. Each
is a library module AND a CLI.

## Entrypoints

| Entrypoint | Output | Approach |
|---|---|---|
| `python -m flyer_generator` | Event flyer (1080×1920 PNG) | Structured event data → AI hero image + vision-evaluated text layout |
| `python -m flyer_generator.brochure` | Tri-fold brochure | Natural-language prompt (v2) or hand-authored `BrochureInput` (v1); LLM + ComfyCloud heavy |
| `python -m flyer_generator.brochure.schema_renderer` | Tri-fold brochure | **Schema-driven.** JSON template + content → SVG → PNG/PDF. Optional AI image fills. |
| `python -m flyer_generator.brand_kit` | Untracked brand kit under `.brand-kits/<slug>/` | Scrape palette / typography / logos / voice from a URL (Playwright primary, BS4 fallback) |
| `python -m flyer_generator.social` | Platform-compliant social-media posts (+ audit sidecar) | Brand-kit slug + post brief → voice-aware copy + AI backdrop + platform validator |

---

## Install

Requires Python ≥ 3.11, Cairo + libffi (for `cairosvg`).

```bash
# Ubuntu / Debian
sudo apt-get install libcairo2 libffi-dev

# macOS
brew install cairo libffi
```

```bash
# clone + install with uv (fastest)
uv sync --extra dev

# or with pip
pip install -e ".[dev]"
```

## Configure

Create a `.env` in the repo root. Only the keys for the surfaces you actually
call are required.

```bash
# Vision + text LLMs (pick one provider; anthropic is default)
FLYER_ANTHROPIC_API_KEY=sk-ant-...
FLYER_VISION_PROVIDER=anthropic           # or "ollama"
FLYER_OLLAMA_API_KEY=...                  # only if provider=ollama
FLYER_OLLAMA_BASE_URL=https://ollama.com  # or self-hosted
FLYER_OLLAMA_TEXT_MODEL=gemma4:31b-cloud
FLYER_OLLAMA_VISION_MODEL=gemma4:31b-cloud

# Image generation
FLYER_COMFYCLOUD_API_KEY=cc-...
FLYER_COMFYCLOUD_BASE_URL=https://cloud.comfy.org
FLYER_WORKFLOW=turbo_portrait             # flyer-path default
FLYER_MAX_BG_ATTEMPTS=3                   # hero vision retry budget
FLYER_POLL_MAX_ATTEMPTS=200               # bump on deep ComfyCloud queues
FLYER_POLL_INTERVAL_SECONDS=6

# Storage roots (both gitignored)
FLYER_BRAND_KITS_DIR=.brand-kits
FLYER_SOCIAL_CAMPAIGNS_DIR=.social-campaigns

# LLM resilience (retry + fallback chain)
FLYER_LLM_RETRY_MAX_ATTEMPTS=3
FLYER_LLM_RETRY_BASE_DELAY=1.0
FLYER_LLM_RETRY_MAX_DELAY=10.0
FLYER_OLLAMA_TEXT_MODEL_FALLBACKS=kimi-k2.6:cloud,qwen3.6:35b
FLYER_OLLAMA_VISION_MODEL_FALLBACKS=kimi-k2.6:cloud,qwen3.6:35b

# Logging
FLYER_LOG_LEVEL=INFO
FLYER_LOG_FORMAT=console                  # or "json"
```

## Quick smoke test

```bash
python -m pytest tests/ -q -m "not slow"   # 1136 pass, 2 slow deselected
```

---

## Generate a flyer

Structured single-flyer output sized 1080×1920.

### From CLI flags

```bash
python -m flyer_generator \
    --title "Community Art Night" \
    --date "Fri Apr 26" \
    --time "7 PM" \
    --venue "Maple Hall" \
    --address "12 Main St, Pleasant, CA" \
    --fees "Free" \
    --org "Pleasant Arts Council" \
    --concept "Warm evening gallery scene with glowing paper lanterns" \
    --preset photorealistic \
    --output ./output/flyer.png
```

### From a JSON event file

```json
{
  "title": "Community Art Night",
  "date": "Fri Apr 26",
  "time": "7 PM",
  "location_name": "Maple Hall",
  "location_address": "12 Main St, Pleasant, CA",
  "fees": "Free",
  "org": "Pleasant Arts Council",
  "style_concept": "Warm evening gallery scene with glowing paper lanterns",
  "style_preset": "photorealistic",
  "color_accent": "#F59E0B"
}
```

```bash
python -m flyer_generator --event-json event.json --output ./output/flyer.png
```

### Useful flags

| Flag | Purpose |
|---|---|
| `--list-presets` | List style presets (`photorealistic`, `anime`, `scifi`, `watercolor`, `retro_poster`, `western_cartoon`, `social_graphic`) |
| `--dry-run` | Print the composed positive + negative prompts without generating |
| `--workflow <name>` | Pick a ComfyCloud workflow from `flyer_generator/workflows/` (default `turbo_portrait`) |
| `--max-attempts <n>` | Override hero vision-retry budget |
| `--accent "#RRGGBB"` | Accent color for text/shape overlays |
| `--preset` / `--style-preset <name>` | Style preset name (both flags accepted — parity with brochure + social CLIs) |
| `--brand-kit <slug>` | Pull accent color from a scraped brand kit (minimal integration — the flyer path uses vision-determined zones, not schema_renderer, so fuller palette/typography threading is deferred) |

---

## Generate a brochure — prompt-driven (v2)

Give it a sentence; the pipeline drafts outline → text → layout → imagery → self-verification.

```bash
python -m flyer_generator.brochure \
    --prompt "A boutique estate-planning law firm specialising in young families" \
    --audience "parents under 45, busy professionals, warm tone" \
    --preset photorealistic \
    --workflow ernie_landscape \
    --output ./output/brochure
```

Writes `brochure_front.png`, `brochure_back.png`, `brochure_print.pdf` into the
output dir. A `trace_id` plus lint + verification summary are echoed at the end.

**Force a specific layout** (skip the LLM template picker):

```bash
python -m flyer_generator.brochure \
    --prompt "..." --preset photorealistic \
    --template editorial --cover-treatment image_full --shape-density medium
```

`--template` accepts `editorial | minimalist | playful | gallery_strip | quote_driven | spotlight`.

## Generate a brochure — hand-authored (v1)

Assemble a `BrochureInput` JSON (see `docs/brochure/sample-content/*.json` for
rich examples) and render without the LLM outline stage.

```bash
python -m flyer_generator.brochure \
    --brochure-json my_brochure.json \
    --output ./output/brochure
```

## Generate a brochure — schema-driven

JSON **template** declares the visual design (shapes, text regions with char
budgets, image placeholders); JSON **content** document — or a
natural-language `--prompt` — supplies the words. Deterministic ~1.2 s render
with zero API calls, or optional ComfyCloud image fills for `image_placeholder`
slots, real logos, and tiled shape textures.

### Design-only render (no API calls)

```bash
python -m flyer_generator.brochure.schema_renderer \
    --template editorial_classic \
    --content docs/brochure/sample-content/law_firm.json \
    --output /tmp/brochure-out
```

Writes `outside.svg`, `inside.svg`, `brochure_front.png`, `brochure_back.png`,
`brochure_print.pdf`.

List built-in templates:

```bash
python -m flyer_generator.brochure.schema_renderer --list-templates
```

13 templates ship today: `bold_diagonal_split`, `edge_anchored_geometry`,
`editorial_classic`, `editorial_spread`, `geometric_bold`, `hero_image_dominant`,
`layered_depth_stack`, `minimal_panel_overlay`, `modular_grid_system`,
`pattern_overlay_hybrid`, `quote_center`, `radial_feature`,
`technical_futuristic_grid`.

### With real AI images (ComfyCloud + vision gate)

```bash
python -m flyer_generator.brochure.schema_renderer \
    --template hero_image_dominant \
    --content docs/brochure/sample-content/law_firm.json \
    --generate-images \
    --workflow ernie_landscape \
    --style-preset photorealistic \
    --output /tmp/brochure-out
```

**Best workflows today:** `ernie_landscape` and `flux2_landscape` tied at 52.7
avg verification score across 3 prompts in the latest adversarial battery;
`flux2_landscape` edges ahead on adversarial-outside (33.3 vs 31.7).
`ernie_turbo_landscape` is ~35% faster for only a 1.4pt drop — best
speed/quality ratio. Full comparison in `HANDOFF.md` §2.

### Auto-audit every render

```bash
python -m flyer_generator.brochure.schema_renderer \
    --template editorial_classic \
    --content my_content.json \
    --brand-kit my-slug \
    --audit \                         # default on
    --iterate-audit 3 \               # up to 3 remediation cycles
    --output /tmp/out
```

Produces `<output>/audit.json` with per-sheet contrast + density + whitespace
report. Contrast failures auto-remediate by swapping to the kit's opposite
neutral. Stderr summary:

```
Audit [outside]: AA pass=True (0/18 fail), density_min=0.20, whitespace_max=0.83, issues=8
Audit [inside]:  AA pass=True (0/21 fail), density_min=0.14, whitespace_max=0.77, issues=8
```

---

## Scrape a brand kit

Scrape a website → extract palette + typography + logos + voice → persist as an
untracked brand kit at `.brand-kits/<slug>/`. Playwright primary, BS4 + httpx +
tinycss2 deterministic fallback. Missing fields remain `null` rather than
invented.

```bash
# Fetch
python -m flyer_generator.brand_kit fetch https://example.com --slug example

# Inspect
python -m flyer_generator.brand_kit list
python -m flyer_generator.brand_kit show example
```

Writes:

```
.brand-kits/example/
├── brand.json                  # BrandPalette + BrandTypography + BrandLogo + BrandVoice
├── logos/
│   └── primary.png             # scraped logos
└── source/
    └── screenshot.png          # viewport screenshot for audit
```

The shape is in `.brand-kit-template.json` at repo root (tracked schema
reference).

### Apply a brand kit to any output

Pass `--brand-kit <slug>` to the schema renderer, the social post CLI, or the
social campaign CLI. The applier merges palette + typography + logo into the
target template and runs a WCAG-AA contrast guardrail (auto-remediates failures
by swapping text color to the kit's opposite neutral, with an OKLCH binary-search
fallback).

```bash
# On a brochure
python -m flyer_generator.brochure.schema_renderer \
    --template editorial_classic --content my_content.json \
    --brand-kit thunderstaff \
    --output /tmp/brochure

# On a social post (see below)
python -m flyer_generator.social post \
    --brand-kit thunderstaff --platform linkedin --intent value-prop \
    --topic "..." --output /tmp/post
```

### Python API

```python
from flyer_generator.brand_kit import (
    fetch_brand_kit, load_brand_kit, apply_brand_kit, audit_render,
)
from flyer_generator.brochure.schema_renderer import load_template

kit = await fetch_brand_kit("https://example.com", slug="example")
# or load an already-scraped one
kit = load_brand_kit("example")

template = load_template("editorial_classic")
branded, png_bytes = apply_brand_kit(template, kit, slug="example")

# Adversarial audit on a rendered PNG
report = audit_render(content, branded, rendered_png_bytes, side="outside")
print(report.contrast.pairs, report.density, report.issues)
```

---

## Generate a social-media post

Single platform-compliant post (copy + image + audit sidecar) rendered in the
brand-kit palette/typography. Publishing is out of scope — this produces
artifacts only.

```bash
python -m flyer_generator.social post \
    --brand-kit hoyack \
    --platform linkedin \
    --intent value-prop \
    --topic "Why U.S.-based engineering teams ship faster than offshore" \
    --cta "Start a Project" \
    --source-url https://hoyack.com \
    --image-hint "abstract geometric network of navy and electric blue nodes, no text, no people" \
    --output /tmp/hoyack-post
```

Writes:

```
/tmp/hoyack-post/
└── hoyack/
    └── <campaign_id>/             # ULID, lexicographically sortable
        └── linkedin__value-prop/
            ├── post.json          # copy + hashtags + validation + audit summary
            └── image.png          # 1200×627 rendered PNG
```

The pipeline:

1. Load `linkedin__value-prop` template (12 templates ship: 4 platforms × 3 intents)
2. Resolve platform rules (LinkedIn 3000-char body, hashtag cap, link policy)
3. Generate voice-aware copy via Ollama/Anthropic — honors the kit's `BrandVoice`
   (tone, example phrases, banned words). Retries once on banned-word violation,
   then raises `BrandVoiceViolationError`.
4. Generate hero via ComfyCloud using the `social_graphic` preset (text-free,
   people-free abstract backdrops) on the `qwen_landscape` workflow
5. Apply brand-kit palette + typography, composite title overlay, rasterize
6. Validate against platform rules → `ValidationReport`
7. Audit: contrast (via shared `scan_text_contrast` primitive), density,
   readability (Flesch-Kincaid grade), platform compliance

### Campaign — one hero, N platforms

Shared ComfyCloud generation + per-platform crops (massive cost reduction).
Copy is regenerated per-platform to honor each platform's voice + char budget.

```bash
python -m flyer_generator.social campaign \
    --brand-kit hoyack \
    --platforms linkedin,twitter,instagram,facebook \
    --topic "AI embedded from day one, not bolted on in year two" \
    --output /tmp/hoyack-campaign
```

Writes:

```
/tmp/hoyack-campaign/
└── hoyack/
    └── <campaign_id>/
        ├── campaign.json                # campaign metadata
        ├── source_hero.png              # the shared source (2048²)
        ├── linkedin__value-prop/
        │   ├── post.json
        │   └── image.png                # 1200×627 crop + overlay
        ├── twitter__value-prop/
        │   ├── post.json
        │   └── image.png                # 1200×675 crop
        ├── instagram__value-prop/
        │   ├── post.json
        │   └── image.png                # 1080×1080 crop
        └── facebook__value-prop/
            ├── post.json
            └── image.png                # 1200×630 crop
```

### Inspection commands

```bash
python -m flyer_generator.social list-platforms    # 4 platforms
python -m flyer_generator.social list-intents      # 3 intents
python -m flyer_generator.social show-rules linkedin
```

### Python API

```python
import asyncio
from flyer_generator.brand_kit import load_brand_kit
from flyer_generator.social import generate_post, PostBrief
from flyer_generator.social.storage import save_post
from ulid import ULID

async def main() -> None:
    kit = load_brand_kit("hoyack")
    brief = PostBrief(
        topic="Why U.S.-based engineering teams ship faster than offshore",
        platform="linkedin",
        intent="value-prop",
        cta="Start a Project",
        source_url="https://hoyack.com",
        image_hint="abstract geometric network, navy + electric blue, no text no people",
        hashtags_seed=["USEngineering", "AIEngineering", "SOC2", "FractionalCTO"],
    )
    post = await generate_post(brief, kit, audit=True)
    save_post(post, "hoyack", str(ULID()),
              template_name="linkedin__value-prop",
              base_dir="/tmp/out")

asyncio.run(main())
```

### Platform rules at a glance

| Platform | Body char max | Hashtag cap | Primary aspect | Link in caption |
|---|---|---|---|---|
| LinkedIn | 3000 | — | 1200×627 (1.91:1) | clickable |
| Twitter / X | 280 | — | 1200×675 (16:9) | clickable |
| Instagram | 2200 | 30 (hard) | 1080×1080 (1:1) | **stripped — use "link in bio"** |
| Facebook | no hard cap | — | 1200×630 (1.91:1) | clickable |

Full rules are printed by `show-rules <platform>`.

### Publishing is deferred

The social subsystem produces artifacts only. No LinkedIn API, Twitter API,
Meta Graph integration, or scheduler. A guard test asserts no `linkedin_api`,
`tweepy`, `facebook_sdk`, `googleapiclient`, or `instagrapi` imports in the
package.

---

## Python API (cross-cutting)

Every CLI path is a thin wrapper over a library function. Mixing subsystems:

```python
import asyncio, json
from flyer_generator.brand_kit import load_brand_kit, apply_brand_kit
from flyer_generator.brochure.schema_renderer import (
    BrochureContent, generate_template_images, load_template, render_schema_brochure,
)
from flyer_generator.config import Settings

kit = load_brand_kit("example")
tmpl = load_template("hero_image_dominant")
branded, logo_bytes = apply_brand_kit(tmpl, kit, slug="example")

content = BrochureContent.model_validate(
    json.loads(open("docs/brochure/sample-content/law_firm.json").read())
)

images = asyncio.run(
    generate_template_images(
        branded, content,
        style_preset="photorealistic",
        workflow_name="ernie_landscape",
        settings=Settings(),
    )
)

outside_svg, inside_svg = render_schema_brochure(branded, content, images=images)
```

---

## Authoring custom templates

**Brochure templates:** drop a new JSON under `flyer_generator/brochure/schemas/`.
Schema is validated by `TemplateSchema` on load; malformed templates fail loud.
Each of six panels (`front_cover`, `back_cover`, `tuck_flap`, `inner_left`,
`inner_center`, `inner_right`) holds a list of elements: `shape`, `text`,
`bullets`, `logo_placeholder`, `image_placeholder`, `divider`. Coordinates are
panel-local (1100×2550 trim); `bleed` extends a shape to the nearest panel edge.

**Social templates:** drop a JSON under `flyer_generator/social/schemas/` named
`<platform>__<intent>.json`. Schema is validated by `PostTemplate` on load.
Declares `{canvas, text_budgets, image_slot, shapes, text_slots}`. Keep
`palette=null` and `typography=null` — brand-kit application at render time
populates them.

Existing templates are the best spec; start by copying an analog and tweaking.

---

## Repo map

```
flyer_generator/
├── __main__.py                        # flyer CLI
├── pipeline.py                        # FlyerGenerator
├── presets.py                         # 7 style presets incl. social_graphic
├── workflows/                         # 8 ComfyCloud workflow JSONs
├── stages/                            # prompt builder, comfy client, vision, LLM retry helper
├── brand_kit/                         # Phase 18: scrape / apply / audit / contrast
│   ├── __main__.py                    #   CLI: fetch / list / show
│   ├── models.py                      #   BrandKit, BrandPalette, BrandVoice, …
│   ├── scraper.py, scraper_*.py       #   Playwright + BS4 fallback
│   ├── palette.py                     #   Pillow quantize extraction
│   ├── contrast.py                    #   WCAG ratio + opposite-neutral + OKLCH remediation
│   ├── applier.py                     #   apply_brand_kit(template, kit)
│   ├── audit.py                       #   audit_render + scan_text_contrast + scan_image_density
│   └── storage.py                     #   .brand-kits/<slug>/ layout + path-traversal guard
├── social/                            # Phase 19: social posts + campaigns
│   ├── __main__.py                    #   CLI: post / campaign / list-platforms / list-intents / show-rules
│   ├── models.py                      #   Post, PostSpec, PostBrief, Campaign, PlatformRules, ValidationReport
│   ├── platforms/                     #   linkedin.py / twitter.py (x alias) / instagram.py / facebook.py
│   ├── schemas/                       #   12 post templates (4 platforms × 3 intents)
│   ├── voice.py                       #   voice-aware copy generation
│   ├── renderer.py                    #   template → SVG → PNG
│   ├── generator.py                   #   generate_post orchestrator
│   ├── campaign.py                    #   generate_campaign (shared hero + per-platform crops)
│   ├── validation.py                  #   shared validation primitives
│   ├── readability.py                 #   dependency-free Flesch-Kincaid
│   ├── workflow_map.py                #   aspect → ComfyCloud workflow
│   ├── crop.py                        #   Pillow aspect-preserving crops
│   ├── audit.py                       #   audit_post + SocialAuditReport
│   └── storage.py                     #   .social-campaigns/<slug>/<campaign_id>/ layout
└── brochure/
    ├── __main__.py                    # brochure CLI (v1 + v2)
    ├── pipeline.py                    # v1 BrochureGenerator
    ├── generative/                    # v2 prompt-driven pipeline
    ├── stages/                        # brochure composer, layout, PDF, vision
    ├── schemas/                       # 13 brochure template JSONs
    └── schema_renderer/               # schema-driven path
        ├── __main__.py                #   CLI
        ├── renderer.py                #   template + content → SVG
        ├── text_gen.py                #   LLM copy generator (brand-voice aware)
        ├── image_gate.py              #   ComfyCloud image fill + generate_single_image helper
        ├── schema_model.py            #   TemplateSchema
        └── content_model.py           #   BrochureContent

docs/brochure/sample-content/          # four rich content JSONs
tests/                                 # 1136 tests (not-slow), 2 slow deselected
.brand-kits/                           # UNTRACKED — scraped brand kits live here
.social-campaigns/                     # UNTRACKED — generated campaigns live here
.brand-kit-template.json               # tracked brand-kit schema reference
.social-template.json                  # tracked social-template schema reference
```

## Tests

```bash
python -m pytest tests/ -q -m "not slow"       # 1136 pass
python -m pytest tests/brand_kit/ -q           # 239 tests
python -m pytest tests/social/ -q              # 206 tests
python -m pytest tests/brochure/ -q            # brochure suite
```

---

## See also

- `HANDOFF.md` — most recent session handoff with current state-of-the-world
- `.planning/ROADMAP.md` — all phases (1-19) with success criteria
- `.planning/phases/18-brand-kit-system/` — Phase 18 artifacts (research, plans, verification)
- `.planning/phases/19-social-media-posting-system/` — Phase 19 artifacts
- `flyer_generator/brochure/schemas/*.json` — every brochure template
- `flyer_generator/social/schemas/*.json` — every social template
- `docs/brochure/sample-content/*.json` — example content documents
