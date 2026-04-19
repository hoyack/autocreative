# Brochure Generator — Session Handoff

**For a fresh session after `/clear`.** Full state-of-the-world for the schema-driven brochure subsystem.

Prior handoff (pre-schema era): `docs/brochure-improvement-v2.md`.

---

## 1. Quick orientation

- **Branch:** `master`, clean working tree
- **Tests:** `python -m pytest tests/ -q` → 611/611 pass in ~35s
- **Latest commits (newest first):**
  ```
  a56d5d6 fix(schemas/bold_diagonal_split): front cover text wrapping + negative leading
  856d7a7 feat(brochure/schemas): adopt 10 user-contributed templates + 3 new content samples
  806b68e feat(brochure/schema-renderer): Phase 1 — schema-driven design-first rendering
  9072c99 feat(brochure): accept layout_choice on v1 BrochureGenerator.generate()
  274d53c feat(brochure): force LayoutTemplate + cover treatment via CLI/API
  65b626d feat(brochure): add --workflow CLI flag
  9946c49 feat(workflows): add ernie_turbo_landscape
  bc892e2 feat(workflows): add ernie_landscape
  1ea8d19 feat(workflows): add flux2_landscape (txt2img) + seed-field detection
  92a04cf feat(workflows): add longcat_landscape
  3a5d58e feat(workflows): add qwen_landscape
  1090a3c feat(prompt-builder): make negative_prompt injection optional
  ```
- **.env:** `FLYER_ANTHROPIC_API_KEY`, `FLYER_COMFYCLOUD_API_KEY`, `FLYER_OLLAMA_API_KEY` all live.
- **Plan file:** `~/.claude/plans/lets-continue-testing-various-cheeky-puddle.md` — full phase plan (Phases 1–6).

---

## 2. What landed this session

### Phase 0 (pre-pivot)
- Wired 5 new ComfyUI workflows: `flux2_landscape` (converted img2img → txt2img), `qwen_landscape`, `ernie_landscape`, `ernie_turbo_landscape`, `longcat_landscape`. Live in `flyer_generator/workflows/`.
- Injection plumbing accepts optional `negative_prompt` and auto-detects `noise_seed` vs `seed` for the seed field.
- CLI: `--workflow` flag on v2 prompt-driven path.
- Ran a 6-workflow × 3-prompt adversarial battery. Winners (by avg built-in rubric): ernie_landscape (52.7), flux2_landscape (52.7 tied), ernie_turbo (51.3). All 5 new workflows beat the incumbent `turbo_landscape` (48.3). Scorecard at `/tmp/brochure-adversarial/scorecard.json`.
- Then started a 36-cell stratified matrix (templates × presets × workflows × samples). **Killed mid-run** because the user flagged the outputs as content-thin / whitespace-heavy — wanted a different direction.

### Phase 1 — the pivot (current subsystem)
Everything in `flyer_generator/brochure/schema_renderer/` is new and **additive**. The legacy prompt-driven pipeline (`generate_brochure_from_prompt`) and v1 `BrochureGenerator` are untouched.

**Architecture:** JSON schema + content JSON → SVG → PNG/PDF. Zero LLM, zero ComfyUI calls. Pure deterministic design rendering in ~1.2s per brochure.

**Modules** under `flyer_generator/brochure/schema_renderer/`:
| file | role |
|---|---|
| `schema_model.py` | Pydantic types for the template JSON: `TemplateSchema`, `ShapeElement`, `TextElement`, `BulletsElement`, `LogoPlaceholder`, `ImagePlaceholder`, `DividerElement` + fills (`SolidFill`, `LinearGradientFill`, `RadialGradientFill`, `TextureSlotFill`) |
| `content_model.py` | `BrochureContent` — carries the words keyed by role. Has `resolve_key()` for template `content_key` expressions and an adapter `BrochureContent.from_brochure_input()` for legacy payloads. |
| `shapes.py` | SVG emitters for rect, rounded_rect, circle, ellipse, polygon, ribbon, triangle, wave, line + gradient defs + panel bleed math |
| `text_fit.py` | Pure-Python text measurement + wrap + char-budget math (no browser dep) |
| `loader.py` | `load_template(name)` + `list_templates()` |
| `renderer.py` | `render_schema_brochure(template, content)` → `(outside_svg, inside_svg)` |
| `__main__.py` | CLI: `python -m flyer_generator.brochure.schema_renderer --template X --content Y.json --output /tmp/...` |

**Schemas** under `flyer_generator/brochure/schemas/`:
13 templates total. My 3 starters: `editorial_classic`, `geometric_bold`, `quote_center`. 10 user-contributed: `bold_diagonal_split`, `edge_anchored_geometry`, `editorial_spread`, `hero_image_dominant`, `layered_depth_stack`, `minimal_panel_overlay`, `modular_grid_system`, `pattern_overlay_hybrid`, `radial_feature`, `technical_futuristic_grid`. All validate against the same Pydantic schema — no code changes were needed to accept the user-contributed ones.

**Sample content JSONs** under `docs/brochure/sample-content/`:
`law_firm.json`, `kids_coding_camp.json`, `tech_startup.json`, `nonprofit.json`. Rich structured data with lead paragraphs + bullet arrays per section + structured back_panel + full ContactBlock.

**Tests** under `tests/brochure/schema_renderer/`:
88 unit tests (schema model, shapes, text fit, content model, loader, renderer) + 78 dynamic gallery tests (every template × every content sample × every rasterization, auto-picked up when a new JSON is added). 611 total tests in the repo.

**Gallery:** `/tmp/brochure-gallery/` has 52 brochures (13 × 4) rendered by `/tmp/brochure-adversarial/render_gallery.py`. Open `/tmp/brochure-gallery/index.md` for a markdown catalog with file:// links.

### Known-good fix
- `bold_diagonal_split` had cramped title wrapping + negative leading on front cover. Fixed in commit `a56d5d6`.

---

## 3. Key concepts to know

### Template schema (one file per template)

```json
{
  "schema_version": "1",
  "name": "snake_case_name",
  "description": "...",
  "tone_keywords": ["..."],
  "canvas": { "width": 1100, "height": 2550 },   // per-panel, trim-sized
  "palette": { "accent_default": "#...", ... },
  "typography": { "heading_family": "...", "cover_title_size": 104, ... },
  "panels": {
    "front_cover": { "background": Fill?, "elements": [...] },
    "back_cover":  { ... },
    "tuck_flap":   { ... },
    "inner_left":  { ... },
    "inner_center": { ... },
    "inner_right": { ... }
  }
}
```

### Element types
- **`shape`** — `rect | rounded_rect | circle | ellipse | polygon | ribbon | triangle | wave | line`, with `fill` (solid / linear_gradient / radial_gradient / texture_slot), optional `stroke`, `rotation`, `opacity`, `bleed` (true / `"top"` / `"left"` / …).
- **`text`** — bbox + `role` (cover_title / section_heading / body / bullet / quote / cta_heading / etc.) + `content_key` (e.g. `sections[0].heading`, `back_panel.bullets`, `contact.phone`).
- **`bullets`** — bbox + `content_key` pointing to a `list[str]` + `bullet_style` (`disc | dash | square | accent_block | numbered`).
- **`logo_placeholder`** — bbox + fallback monogram (circle / square / plain).
- **`image_placeholder`** — bbox + `slot` (`hero` / `spot_1` / `spot_2` / `spot_3`) + `fallback_fill`. **Phase 1 only renders the fallback — actual image embedding is Phase 4 work.**
- **`divider`** — rule line.

### Coordinate system
Element coordinates are **panel-local**. `(0,0)` is top-left of each panel's **trim** rect. The panel is 1100×2550. Renderer translates each panel group into sheet coordinates and dynamically applies the panel's actual bleed margins (derived from `compute_panel_layout()`). Tuck flap and cover panels have different bleed margins; the renderer handles this transparently.

### Content resolution
Templates reference content via `content_key` strings. Supported forms:
- `title`, `subtitle`, `tagline`, `org`, `hero_concept`
- `contact.name`, `contact.phone`, `contact.email`, `contact.url`, `contact.address`
- `sections[N].heading`, `sections[N].lead_paragraph`, `sections[N].body_paragraphs`, `sections[N].bullets`, `sections[N].quote`, `sections[N].image_concept`
- `back_panel.heading`, `back_panel.body`, `back_panel.bullets`, `back_panel.cta_label`, `back_panel.footer_note`
- `extras.<any_key>`
- `section.<field>` — shorthand when `section_index` is supplied on the element

---

## 4. How to run things

### Render one brochure
```bash
python -m flyer_generator.brochure.schema_renderer \
    --template editorial_classic \
    --content docs/brochure/sample-content/law_firm.json \
    --output /tmp/out
```
Produces `outside.svg`, `inside.svg`, `brochure_front.png`, `brochure_back.png`, `brochure_print.pdf`.

### List templates
```bash
python -m flyer_generator.brochure.schema_renderer --list-templates
```

### Render the full gallery (13 templates × 4 contents, ~60s)
```bash
python /tmp/brochure-adversarial/render_gallery.py
# → /tmp/brochure-gallery/index.md + 52 cells
```

### Run tests
```bash
python -m pytest tests/ -q                                   # 611 tests, ~35s
python -m pytest tests/brochure/schema_renderer/ -q          # 166 tests, ~10s
```

---

## 5. Phase roadmap (from `~/.claude/plans/lets-continue-testing-various-cheeky-puddle.md`)

| Phase | Status | Scope |
|---|---|---|
| 1 | ✅ shipped | Schema foundation — pure data → SVG, 13 templates, 88+78 tests |
| 2 | next up | Ollama text-budgeting: given a template's char budgets, LLM writes text that exactly fits |
| 3 | deferred | Template-library expansion (already 13 — user may want 20+) + authoring docs |
| 4 | **priority for next session** | Image placeholders + vision gate (see §6) |
| 5 | deferred | Text-on-image (flyer-pipeline safe-region port) |
| 6 | deferred | Logo placeholder: embed real SVG/PNG logos (current impl is monogram fallback) |

---

## 6. Next session — user's stated goal

> "Another round of test generations across the styles and sample concepts, and I want these to also include the image generation, be it images - or textures and I want it to include any edits to make the images into the geometric boxes if needed, etc."

**Translation:** Phase 4 — wire ComfyUI image generation into the schema renderer's `image_placeholder` and (stretch) shape `texture_slot` fills. Then re-render the 52-cell gallery with real images, cropped/masked to fit the placeholder bboxes.

### What needs to happen

1. **Identify image slots per template**
   Walk each template, collect every `image_placeholder` element. Group by `slot` name (`hero`, `spot_1`, `spot_2`, `spot_3`).

2. **Generate content image concepts**
   Content JSONs already carry:
   - `hero_concept` at the top level
   - `sections[i].image_concept` per section (may be null)
   Templates' image slots are mapped to these via the `slot` field:
   - `slot: "hero"` → `content.hero_concept`
   - `slot: "spot_1"` → `sections[0].image_concept` (or `icon_hint`)
   - etc.

3. **Image generation integration**
   Reuse the existing path in `flyer_generator/brochure/generative/imagery.py`:
   - Hero: `BrochureCoverPromptBuilder` + `BrochureCoverVisionEvaluator` (vision gate: rejects images with text artifacts) + ComfyUI client
   - Spots: `_build_spot_workflow` (no vision gate)
   - Best workflow per last battery: **ernie_landscape** or **flux2_landscape**
   - Workflow choice is a CLI arg (`--workflow`)

4. **Placeholder → image embedding in renderer**
   Currently `_render_image_placeholder` in `schema_renderer/renderer.py` emits only the fallback gradient + "[hero]" label. Extend it so when an `images: dict[slot, bytes]` map is passed into `render_schema_brochure()`, the matching slot's bytes are base64-embedded into the placeholder's bbox with correct `preserveAspectRatio`:
   - `mask: "none"` → embedded `<image>` with `xMidYMid slice` (crop-to-fill)
   - `mask: "rounded"` → same but clipped to a `<clipPath>` with `rx=corner_radius`
   - `mask: "circle"` → clipped to a circular clipPath
   - Fallback stays for when the slot didn't generate successfully

5. **Texture_slot fills** (stretch)
   `TextureSlotFill` already exists in the schema. Extend `render_fill()` in `shapes.py` to accept a `textures: dict[slot_name, bytes]` map and emit a `<pattern>` referencing the bytes as a tiled image. For now, `texture_slot` falls back to its `fallback: SolidFill | LinearGradientFill | RadialGradientFill`.

6. **New CLI + orchestrator**
   ```bash
   python -m flyer_generator.brochure.schema_renderer \
       --template hero_image_dominant \
       --content docs/brochure/sample-content/law_firm.json \
       --workflow ernie_landscape \
       --generate-images \
       --output /tmp/out
   ```
   When `--generate-images`, the CLI:
   1. Collects image slots from the template.
   2. For each slot, runs the imagery pipeline (hero via `generate_imagery` helper, spots via `_build_spot_workflow`).
   3. Passes the `{slot: bytes}` dict into `render_schema_brochure()`.

7. **Vision gate is non-negotiable for hero**
   The prior battery showed cloud models produce legible text inside images ~1/3 of the time. `BrochureCoverVisionEvaluator` already rejects those. Keep max attempts = 3; on full rejection, fall back to the placeholder's `fallback_fill` — the design still works.

8. **Second gallery run**
   After wiring, re-render the 13-template × 4-content gallery *with* image generation. At ~3 min per cell (hero retry + 3 spots) × 52 cells = ~2.5 hours. Probably better to start with:
   - 4 templates × 4 contents = 16 cells (~50 min) for a first look
   - Then expand

### Files that will need to change (Phase 4)

| file | change |
|---|---|
| `flyer_generator/brochure/schema_renderer/renderer.py` | accept `images: dict[str, bytes]` kwarg, thread to image_placeholder renderer |
| `flyer_generator/brochure/schema_renderer/image_gate.py` (NEW) | wraps `generate_imagery` for each slot, handles rejection → fallback |
| `flyer_generator/brochure/schema_renderer/__main__.py` | `--generate-images` + `--workflow` flags |
| `flyer_generator/brochure/schema_renderer/shapes.py` | `texture_slot` fill → `<pattern>` when texture bytes supplied |
| `tests/brochure/schema_renderer/test_image_gate.py` (NEW) | mocked ComfyClient + vision; verify retry + fallback |

### Reuse
- `flyer_generator.brochure.generative.imagery.generate_imagery` — already takes `workflow_name`, does hero retry loop, returns `GeneratedImagery(hero_png_bytes, spot_images)`.
- `flyer_generator.brochure.stages.vision.BrochureCoverVisionEvaluator` — rejects text-in-image artifacts.
- `flyer_generator.stages.comfy_client.ComfyClient` — POST workflow / poll / download.
- `flyer_generator.workflow_loader.load_workflow` — loads any of the 8 workflows.

---

## 7. Open issues / gotchas

- **No image generation yet in schema renderer.** That's Phase 4 (next session).
- **`texture_slot` falls back to solid/gradient.** Intentional until Phase 4.
- **`logo_placeholder` renders a monogram, not a real logo.** Phase 6. For now, all gallery cells use the fallback monogram.
- **Template font families are CSS strings** (`'Playfair Display', serif`). If the rasterizer doesn't have the font installed, it falls back to the next in the stack. `flyer_generator/assets/fonts/` is empty — drop subsetted woff2 files to get exact typography. Not blocking.
- **`docs/brochure-templates/`** still contains the 10 original JSONs (I copied them into `flyer_generator/brochure/schemas/` rather than moving — docs/brochure-templates/ is the "design reference" directory). No harm; they're identical.
- **`/tmp/brochure-adversarial/`** — old adversarial battery data. `run_matrix.py` + `build_index.py` + `aggregate.py` are there if we ever want to re-run. Not touched by the schema renderer.

---

## 8. When you come back after `/clear`

1. `git log --oneline | head -10` → confirm tree state (expect `a56d5d6 fix(schemas/bold_diagonal_split)…` at top).
2. `python -m pytest tests/ -q` → confirm 611/611 pass.
3. `ls flyer_generator/brochure/schemas/` → confirm 13 templates present.
4. `ls /tmp/brochure-gallery/` → confirm prior gallery artifacts still there (they may have been purged by /tmp rotation; rerun `python /tmp/brochure-adversarial/render_gallery.py` if needed, ~60s).
5. Open `HANDOFF.md` (this file) + `~/.claude/plans/lets-continue-testing-various-cheeky-puddle.md` for full context.
6. Begin Phase 4: image placeholders + texture slots. Start by reading `flyer_generator/brochure/generative/imagery.py` and `flyer_generator/brochure/schema_renderer/renderer.py:_render_image_placeholder`.

---

## 9. Quick-reference file index

```
flyer_generator/brochure/
├── schema_renderer/          ← NEW subsystem (Phase 1)
│   ├── __init__.py           exports load_template, list_templates, render_schema_brochure, BrochureContent, TemplateSchema
│   ├── __main__.py           CLI
│   ├── content_model.py      BrochureContent + adapter from BrochureInput
│   ├── loader.py             load_template + list_templates
│   ├── renderer.py           render_schema_brochure — CORE
│   ├── schema_model.py       TemplateSchema + every element Pydantic type
│   ├── shapes.py             SVG primitive emitters
│   └── text_fit.py           text measurement + wrap + char budget
├── schemas/                  ← 13 template JSONs
│   ├── bold_diagonal_split.json
│   ├── edge_anchored_geometry.json
│   ├── editorial_classic.json   (my starter)
│   ├── editorial_spread.json
│   ├── geometric_bold.json      (my starter)
│   ├── hero_image_dominant.json
│   ├── layered_depth_stack.json
│   ├── minimal_panel_overlay.json
│   ├── modular_grid_system.json
│   ├── pattern_overlay_hybrid.json
│   ├── quote_center.json        (my starter)
│   ├── radial_feature.json
│   └── technical_futuristic_grid.json
├── generative/               ← LLM-driven legacy path (untouched)
│   ├── pipeline.py           generate_brochure_from_prompt
│   ├── imagery.py            generate_imagery (reuse in Phase 4)
│   └── …
├── stages/                   ← shared stages (composer, layout, pdf, vision, prompt_builder)
└── pipeline.py               v1 BrochureGenerator (layout_choice-aware)

docs/brochure/
└── sample-content/           ← 4 content JSONs (law_firm, kids_coding_camp, tech_startup, nonprofit)

tests/brochure/schema_renderer/
├── test_schema_model.py      20 tests
├── test_shapes.py            19 tests
├── test_text_fit.py          11 tests
├── test_content_model.py     13 tests
├── test_loader.py            7 tests
├── test_renderer.py          17 tests
└── test_gallery.py           78 dynamic tests (grows with schemas + content)
```

---

**TL;DR for next session:** Phase 1 shipped. 13 templates. Zero-API rendering in 1.2s per brochure. Next up: Phase 4 — wire ComfyUI image generation into `image_placeholder` slots (and optionally `texture_slot` fills for shapes), respect the existing vision gate that rejects text-in-image, then re-render the gallery with real hero photos + spot images.
