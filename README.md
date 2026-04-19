# Flyer & Brochure Generator

AI-assisted event flyers (1080×1920 PNG) and print-ready tri-fold brochures
(outside + inside PNGs + PDF), generated with ComfyCloud image backgrounds and
Claude vision gating for layout safety.

The repo ships three independent entrypoints:

| Entrypoint | Output | Approach |
|---|---|---|
| `python -m flyer_generator` | Event flyer (1080×1920 PNG) | Structured event data → AI hero image + vision-evaluated text layout |
| `python -m flyer_generator.brochure` | Tri-fold brochure (front + back + PDF) | Either a natural-language prompt (v2) or a hand-authored `BrochureInput` (v1); LLM + ComfyUI heavy |
| `python -m flyer_generator.brochure.schema_renderer` | Tri-fold brochure (front + back + PDF) | **Schema-driven, design-first.** JSON template + content JSON → SVG → PNG/PDF. Optional ComfyUI image fills for `image_placeholder` slots. |

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

Create a `.env` in the repo root:

```bash
FLYER_ANTHROPIC_API_KEY=sk-ant-...
FLYER_COMFYCLOUD_API_KEY=cc-...
# optional
FLYER_COMFYCLOUD_BASE_URL=https://cloud.comfy.org
FLYER_WORKFLOW=turbo_portrait       # default for flyer path
FLYER_MAX_BG_ATTEMPTS=3              # hero vision retry budget
FLYER_LOG_LEVEL=INFO
FLYER_LOG_FORMAT=console             # or "json"
```

## Quick smoke test

```bash
python -m pytest tests/ -q           # 634/634 expected
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
| `--list-presets` | List style presets (`photorealistic`, `anime`, `scifi`, `watercolor`, `retro_poster`, `western_cartoon`) |
| `--dry-run` | Print the composed positive + negative prompts without generating |
| `--workflow <name>` | Pick a ComfyUI workflow from `flyer_generator/workflows/` (default `turbo_portrait`) |
| `--max-attempts <n>` | Override hero vision-retry budget |
| `--accent "#RRGGBB"` | Accent color for text/shape overlays |

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

Or the inline form for quick tests:

```bash
python -m flyer_generator.brochure \
    --title "Protecting Your Family's Tomorrow" \
    --concept "Warm golden-hour photo of a young family" \
    --preset photorealistic \
    --org "Harbor & Vale" \
    --sections-json sections.json \
    --output ./output/brochure
```

---

## Generate a brochure — schema-driven (Phase 1 + Phase 4)

The newest path. A JSON **template** declares the visual design (shapes, text
regions with char budgets, image placeholders); a JSON **content** document
carries the words. Renders deterministically in ~1.2 s with zero API calls,
or optionally fills `image_placeholder` slots via ComfyUI.

### Design-only render (no API calls, ~1.2 s)

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

Four sample content JSONs live at `docs/brochure/sample-content/`.

### With real images (ComfyUI + vision gate)

Appending `--generate-images` pipes each template `image_placeholder` slot
through ComfyCloud. The **hero** slot runs a vision-gated retry loop
(rejects AI images that contain legible text); **spot** slots run in
parallel with no vision gate. Failed slots silently fall back to the
placeholder's `fallback_fill` so the design still works.

```bash
python -m flyer_generator.brochure.schema_renderer \
    --template hero_image_dominant \
    --content docs/brochure/sample-content/law_firm.json \
    --generate-images \
    --workflow ernie_landscape \
    --style-preset photorealistic \
    --output /tmp/brochure-out
```

Per-slot generated PNGs are persisted to `<output>/images/{hero,spot_1,…}.png`
for inspection.

**Best workflow today:** `ernie_landscape` — 40/40 first-try vision approvals
across a 16-cell test gallery; tied-top on the scored adversarial battery.
See `HANDOFF.md` §6 for the full comparison table.

Typical timings (single cell, ComfyCloud cold):
- template with 1 hero + 1 spot: ~75–115 s
- template with 1 hero + 3 spots (`hero_image_dominant`): ~115–135 s

---

## Python API

Every CLI path is a thin wrapper over a library function. Minimal usage:

```python
import asyncio
from flyer_generator.brochure.schema_renderer import (
    BrochureContent,
    generate_template_images,
    load_template,
    render_schema_brochure,
)
from flyer_generator.config import Settings
import json

tmpl = load_template("hero_image_dominant")
content = BrochureContent.model_validate(
    json.loads(open("docs/brochure/sample-content/law_firm.json").read())
)

# Optional: generate images; pass {} (or omit) for a pure-design render.
images = asyncio.run(
    generate_template_images(
        tmpl, content,
        style_preset="photorealistic",
        workflow_name="ernie_landscape",
        settings=Settings(),
    )
)

outside_svg, inside_svg = render_schema_brochure(tmpl, content, images=images)
```

---

## Authoring custom templates

Drop a new JSON under `flyer_generator/brochure/schemas/` (or an absolute path
via `--template /abs/path.json`). Schema is validated by
`flyer_generator/brochure/schema_renderer/schema_model.py:TemplateSchema` on
load; malformed templates fail loud at load time, not at render time.

Each of six panels (`front_cover`, `back_cover`, `tuck_flap`, `inner_left`,
`inner_center`, `inner_right`) holds a list of elements: `shape`, `text`,
`bullets`, `logo_placeholder`, `image_placeholder`, `divider`. Coordinates are
panel-local (1100×2550 trim); `bleed` extends a shape to the nearest panel edge.

Existing templates are the best spec; start by copying `editorial_classic.json`
or `hero_image_dominant.json` and tweaking.

---

## Repo map

```
flyer_generator/
├── __main__.py                     # flyer CLI
├── pipeline.py                     # FlyerGenerator
├── workflows/                      # 8 ComfyUI workflow JSONs
├── stages/                         # prompt builder, comfy client, vision, rasterizer
└── brochure/
    ├── __main__.py                 # brochure CLI (v1 + v2)
    ├── pipeline.py                 # v1 BrochureGenerator
    ├── generative/                 # v2 prompt-driven pipeline (outline → imagery → verify)
    ├── stages/                     # brochure-specific composer, layout, PDF, vision
    ├── schemas/                    # 13 template JSONs
    └── schema_renderer/            # Phase 1 + Phase 4
        ├── __main__.py             # schema-driven CLI
        ├── renderer.py             # template + content → SVG; embeds images
        ├── image_gate.py           # Phase 4: ComfyUI image fill for image_placeholder slots
        ├── schema_model.py         # Pydantic template schema
        └── content_model.py        # BrochureContent
docs/brochure/sample-content/       # four rich content JSONs
tests/                              # 634 tests
```

## Tests

```bash
python -m pytest tests/ -q
```

---

## See also

- `HANDOFF.md` — current state of the schema renderer + Phase 4 outcomes
- `~/.claude/plans/lets-continue-testing-various-cheeky-puddle.md` — phase plan
- `flyer_generator/brochure/schemas/*.json` — every template
- `docs/brochure/sample-content/*.json` — example content documents
