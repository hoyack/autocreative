# Brochure Generator — Session Handoff

**For a fresh session after `/clear`.** Full state-of-the-world for the schema-driven brochure subsystem.

Prior handoff (pre-schema era): `docs/brochure-improvement-v2.md`.

---

## 1. Quick orientation

- **Branch:** `master`, clean working tree
- **Tests:** `python -m pytest tests/ -q` → 658/658 pass in ~35s
- **Latest commits (newest first):**
  ```
  e1896f8 feat(brochure/schema-renderer): Phase 2 — LLM text budgeting
  0ddd85d feat(brochure/schema-renderer): Phase 6 — real logo embedding
  a08fe18 feat(brochure/schema-renderer): Phase 4 stretch — texture_slot → <pattern>
  1992c80 docs: refresh HANDOFF staleness — test count, commits, file index, TL;DR
  0ad3744 docs: write README covering flyer + brochure (v1/v2/schema-driven) paths
  1e84991 docs: mark Phase 4 shipped in HANDOFF, retarget §6-§8 to current state
  0ed9939 feat(brochure/schema-renderer): Phase 4 — image gate + placeholder embedding
  2a533a6 docs: session handoff — schema-renderer subsystem state + Phase 4 plan
  a56d5d6 fix(schemas/bold_diagonal_split): front cover text wrapping + negative leading
  d539b37 feat(brochure/schemas): adopt 10 user-contributed templates + 3 new content samples
  806b68e feat(brochure/schema-renderer): Phase 1 — schema-driven design-first rendering
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
95 unit tests (schema model, shapes, text fit, content model, loader, renderer, image_gate) + 78 dynamic gallery tests (every template × every content sample × every rasterization, auto-picked up when a new JSON is added) + 16 image_gate tests. 634 total tests in the repo.

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
| 1 | ✅ shipped | Schema foundation — pure data → SVG, 13 templates |
| 2 | ✅ shipped | LLM text-budgeting: `--prompt` → Ollama/Anthropic writes copy fitting every region (commit `e1896f8`) |
| 3 | deferred | Template-library expansion (already 13 — user may want 20+) + authoring docs |
| 4 | ✅ shipped | Image placeholders + vision gate — 4×4 gallery 16/16 green (commit `0ed9939`) |
| 4 stretch | ✅ shipped | `texture_slot` → `<pattern>` tile on shape fills (commit `a08fe18`) |
| 5 | deferred | Text-on-image (flyer-pipeline safe-region port) |
| 6 | ✅ shipped | Real logo embedding — PNG/JPG/SVG via `--logo` (commit `0ddd85d`) |

---

## 6. Recently shipped

### Phase 4 — image placeholders + vision gate (`0ed9939`)
Gallery `/tmp/phase4-gallery/` — 4 templates × 4 contents = 16 cells. **16/16 green, 0 fallbacks.** Vision gate approved 40/40 hero generations first try. Workflow `ernie_landscape`, preset `photorealistic`. Avg cell time 110s.

`image_gate.generate_template_images(template, content, ...)` walks image_placeholder slots, runs hero through `BrochureCoverPromptBuilder` + vision retry, spots via minimal spot workflow in parallel. `render_schema_brochure(..., images=)` base64-embeds PNGs with `xMidYMid slice` and mask-aware `<clipPath>`. CLI: `--generate-images / --workflow / --style-preset`.

### Phase 4 stretch — texture_slot → `<pattern>` (`a08fe18`)
`render_fill(fill, salt, textures=)` now resolves `TextureSlotFill` to a tiled `<pattern>` when the slot matches; falls through to `fallback:` fill otherwise. Tiles at 512×512 (`TEXTURE_TILE_PX`), userSpaceOnUse. `textures` plumbs through every shape renderer → `render_shape` → `_render_panel` → `render_schema_brochure(..., textures=)`. CLI: `--textures-dir <path>` loads `<slot>.png` files.

### Phase 6 — real logo embedding (`0ddd85d`)
`render_schema_brochure(..., logo_bytes=)` fills every `logo_placeholder` with the supplied bytes; absent → monogram fallback as before. PNG/JPG base64-embedded with `xMidYMid meet` (letterboxing, never crops); JPEG detected via SOI marker. SVG inlined as a nested `<svg>` viewport after stripping the XML prolog + DOCTYPE (caught in live smoke — cairosvg rejects nested `<?xml?>`). CLI: `--logo <path>` accepts PNG/JPG/SVG.

### Phase 2 — LLM text budgeting (`e1896f8`)
`text_gen.generate_content_from_prompt(template, prompt, audience=)` collects every TextElement + BulletsElement's tightest char budget per content_key, then asks the configured TextClient (Ollama or Anthropic, via `settings.vision_provider`) for a JSON object shaped to those limits. Overflow fields get one retry with a stricter instruction; word-boundary truncation is the final fallback. CLI: `--prompt <text>` mutually exclusive with `--content`, persists LLM output to `<output>/content.json`.

Live smoke (editorial_classic × Anthropic): 21 budgeted fields filled in one call, cogent on-tone copy; 0 overflow retries needed for this prompt.

### Gotchas caught
- **1×1 fake PNGs + cairo OOM.** Initial renderer tests used a hand-rolled 1×1 PNG; cairo OOM'd upsampling to ~900px. Fix: `Pillow.Image.new((128, 128), ...)` for test fixtures.
- **Nested `<?xml?>`** inside another SVG breaks cairosvg. `_strip_svg_prolog()` removes the XML declaration + DOCTYPE before inlining SVG logos.
- `ImagePlaceholder.corner_radius` is `float` → serializes as `"22.0"`; asserts match `rx="22`.

---

## 7. Open issues / gotchas

- **Phase 3** — template library expansion is still open; 13 templates today. Adding templates requires no code changes, just JSON.
- **Phase 5** — text-on-image safe-region detection (flyer-pipeline port). Not started.
- **Template font families are CSS strings** (`'Playfair Display', serif`). If the rasterizer doesn't have the font installed, it falls back to the next in the stack. `flyer_generator/assets/fonts/` is empty — drop subsetted woff2 files to get exact typography. Not blocking.
- **`docs/brochure-templates/`** still contains the 10 original JSONs (copied into `flyer_generator/brochure/schemas/` rather than moved — docs/brochure-templates/ is the "design reference" directory). No harm; identical.
- **`/tmp/brochure-adversarial/`** — old adversarial battery data. Not touched by the schema renderer.
- **Gallery PDFs are large** (~17 MB per cell) because each embeds 2–4 real 1472×832 photos base64'd into SVG, then rasterized at 3376×2626 and wrapped in PDF. Acceptable for print; if this grows, downscale embedded PNGs before base64 or cache-dedupe shared slots across sheets.
- **Texture generation** — `--textures-dir` is fed by the user today. There is no LLM/ComfyUI orchestrator that generates textures to match a template's needs; that's a future iteration (could piggyback on `image_gate`).

---

## 8. When you come back after `/clear`

1. `git log --oneline | head -10` → expect `e1896f8 feat(brochure/schema-renderer): Phase 2 …` at top.
2. `python -m pytest tests/ -q` → confirm 658/658 pass.
3. `ls /tmp/phase4-gallery/` → Phase 4 gallery artifacts (may be purged by /tmp rotation; rerun `PYTHONPATH=$PWD python /tmp/phase4-gallery/run.py` if needed, ~30 min).
4. Open `HANDOFF.md` (this file) + `README.md` for full context.
5. Try the end-to-end path, one sentence → finished brochure with photos + logo:
   ```bash
   python -m flyer_generator.brochure.schema_renderer \
       --template hero_image_dominant \
       --prompt "a boutique estate-planning law firm for young families" \
       --audience "parents under 45, warm tone" \
       --generate-images --workflow ernie_landscape \
       --logo path/to/logo.png \
       --output /tmp/oneshot
   ```
6. Remaining candidates:
   - **Phase 3** — 5–9 more templates (JSON-only, no Python).
   - **Phase 5** — text-on-image safe-region detection (port from flyer pipeline).
   - **Auto-texture** — wire an LLM concept generator + ComfyUI into `--textures-dir` so textures are generated per template rather than fed by hand.

---

## 9. Quick-reference file index

```
flyer_generator/brochure/
├── schema_renderer/          ← Phases 1, 2, 4 (+ stretch), 6 subsystem
│   ├── __init__.py           load_template, list_templates, render_schema_brochure,
│   │                         BrochureContent, TemplateSchema, TextBudget,
│   │                         generate_template_images, generate_content_from_prompt,
│   │                         collect_image_slots, collect_text_budgets, resolve_concept_for_slot
│   ├── __main__.py           CLI — accepts --content OR --prompt; flags
│   │                         --generate-images, --workflow, --style-preset,
│   │                         --logo, --textures-dir, --audience
│   ├── content_model.py      BrochureContent + adapter from BrochureInput
│   ├── image_gate.py         Phase 4: ComfyUI image fill for image_placeholder slots (hero vision gate + parallel spots)
│   ├── loader.py             load_template + list_templates
│   ├── renderer.py           render_schema_brochure(images=, textures=, logo_bytes=) — CORE
│   ├── schema_model.py       TemplateSchema + every element Pydantic type
│   ├── shapes.py             SVG primitive emitters + texture_slot → <pattern>
│   ├── text_fit.py           text measurement + wrap + char budget
│   └── text_gen.py           Phase 2: LLM text budgeting (Ollama / Anthropic)
├── schemas/                  ← 13 template JSONs
├── generative/               ← LLM-driven legacy path (untouched)
├── stages/                   ← shared stages (composer, layout, pdf, vision, prompt_builder)
└── pipeline.py               v1 BrochureGenerator (layout_choice-aware)

docs/brochure/
└── sample-content/           ← 4 content JSONs (law_firm, kids_coding_camp, tech_startup, nonprofit)

tests/brochure/schema_renderer/
├── test_schema_model.py      20 tests
├── test_shapes.py            23 tests (Phase 4 stretch added 4 texture_slot tests)
├── test_text_fit.py          11 tests
├── test_content_model.py     13 tests
├── test_loader.py            7 tests
├── test_renderer.py          38 tests (Phase 4 + 4-stretch + Phase 6 additions)
├── test_image_gate.py        16 tests (Phase 4)
├── test_text_gen.py          14 tests (Phase 2)
└── test_gallery.py           78 dynamic tests (grows with schemas + content)
```

---

**TL;DR for next session:** Phases 1, 2, 4 (+ stretch), 6 all shipped. One CLI command turns a single sentence into a print-ready tri-fold brochure with LLM-budgeted copy, ComfyUI hero + spot photos (vision-gated), embedded logo, and optional tiled textures. 658/658 tests. 16/16 live gallery cells green. Deferred: Phase 3 template expansion, Phase 5 text-on-image.
