# Brochure Generator — Session Handoff

**For a fresh session after `/clear`.** Full state-of-the-world for the schema-driven brochure subsystem.

Prior handoff (pre-schema era): `docs/brochure-improvement-v2.md`.

---

## 1. Quick orientation

- **Branch:** `master`, clean working tree
- **Tests:** `python -m pytest tests/ -q` → 634/634 pass in ~35s
- **Latest commits (newest first):**
  ```
  0ad3744 docs: write README covering flyer + brochure (v1/v2/schema-driven) paths
  1e84991 docs: mark Phase 4 shipped in HANDOFF, retarget §6-§8 to current state
  0ed9939 feat(brochure/schema-renderer): Phase 4 — image gate + placeholder embedding
  2a533a6 docs: session handoff — schema-renderer subsystem state + Phase 4 plan
  a56d5d6 fix(schemas/bold_diagonal_split): front cover text wrapping + negative leading
  d539b37 feat(brochure/schemas): adopt 10 user-contributed templates + 3 new content samples
  806b68e feat(brochure/schema-renderer): Phase 1 — schema-driven design-first rendering
  9072c99 feat(brochure): accept layout_choice on v1 BrochureGenerator.generate()
  65b626d feat(brochure): add --workflow CLI flag
  9946c49 feat(workflows): add ernie_turbo_landscape
  bc892e2 feat(workflows): add ernie_landscape
  1ea8d19 feat(workflows): add flux2_landscape (txt2img) + seed-field detection
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
| 1 | ✅ shipped | Schema foundation — pure data → SVG, 13 templates, 88+78 tests |
| 2 | next up | Ollama text-budgeting: given a template's char budgets, LLM writes text that exactly fits |
| 3 | deferred | Template-library expansion (already 13 — user may want 20+) + authoring docs |
| 4 | ✅ shipped | Image placeholders + vision gate — 4×4 gallery 16/16 green (commits `0ed9939`, `/tmp/phase4-gallery/`) |
| 5 | deferred | Text-on-image (flyer-pipeline safe-region port) |
| 6 | deferred | Logo placeholder: embed real SVG/PNG logos (current impl is monogram fallback) |

---

## 6. Phase 4 — shipped

**Commits:** `0ed9939 feat(brochure/schema-renderer): Phase 4 — image gate + placeholder embedding`.

**Gallery:** `/tmp/phase4-gallery/` — 4 templates × 4 contents = 16 cells. **16/16 green, 0 fallbacks.** Vision gate approved every first attempt (40 hero generations). Workflow: `ernie_landscape`, style preset: `photorealistic`. Avg cell time 110s (hero + 1–3 spots sequential hero + parallel spots). Summary at `/tmp/phase4-gallery/index.md`, full JSON at `/tmp/phase4-gallery/results.json`.

Templates exercised: `hero_image_dominant` (4 slots), `layered_depth_stack`, `radial_feature`, `editorial_spread` (2 slots each).

### What shipped
- `flyer_generator/brochure/schema_renderer/image_gate.py` — `generate_template_images(template, content, ...)` walks image_placeholder slots, generates hero via `BrochureCoverPromptBuilder` + vision retry, spots via minimal spot workflow in parallel. Failures are soft (missing slot → renderer falls back to `fallback_fill`). All components injectable (ComfyClient / cover_builder / cover_vision) for tests.
- `renderer.render_schema_brochure(..., images=)` — embeds PNG bytes as base64 `<image>` with `preserveAspectRatio="xMidYMid slice"` and mask-aware `<clipPath>` (none / rounded / circle).
- CLI `--generate-images / --workflow / --style-preset` — when set, runs image_gate and writes per-slot PNGs to `<output>/images/`.
- 23 new tests (16 image_gate + 7 renderer embedding). Full suite 634/634 green.

### Gotcha caught during implementation
- **1×1 fake PNGs + cairo OOM.** Initial renderer tests used a hand-rolled 1×1 PNG; cairo blew up with `CAIRO_STATUS_NO_MEMORY` when upsampling to ~900px. Fix: `Pillow.Image.new((128, 128), ...)` for test fixtures. Real ComfyUI outputs (1472×832) rasterize cleanly.
- `ImagePlaceholder.corner_radius` is `float` → serializes as `"22.0"`, not `"22"`. Existing Phase 1 fallback had the same behavior, so no change needed — tests match `rx="22`.

### Still deferred
- **Phase 4 stretch — `texture_slot` → `<pattern>`.** Not shipped. `TextureSlotFill` still falls back to its `fallback:` SolidFill/LinearGradient/RadialGradient. When someone wants real texture generation into shape fills: extend `render_fill()` in `shapes.py` to accept a `textures: dict[slot, bytes]` kwarg and emit a `<pattern>` referencing the bytes.
- **Phase 5 — text-on-image safe-region detection.** Not started.
- **Phase 6 — real logo embedding.** Still monogram.

---

## 7. Open issues / gotchas

- **`texture_slot` falls back to solid/gradient.** Not wired to ComfyUI textures yet. Phase 4 stretch, deferred.
- **`logo_placeholder` renders a monogram, not a real logo.** Phase 6.
- **Template font families are CSS strings** (`'Playfair Display', serif`). If the rasterizer doesn't have the font installed, it falls back to the next in the stack. `flyer_generator/assets/fonts/` is empty — drop subsetted woff2 files to get exact typography. Not blocking.
- **`docs/brochure-templates/`** still contains the 10 original JSONs (copied into `flyer_generator/brochure/schemas/` rather than moved — docs/brochure-templates/ is the "design reference" directory). No harm; identical.
- **`/tmp/brochure-adversarial/`** — old adversarial battery data. Not touched by the schema renderer.
- **Gallery PDFs are large** (~17 MB per cell) because each embeds 2–4 real 1472×832 photos base64'd into SVG, then rasterized at 3376×2626 and wrapped in PDF. Acceptable for print; if this grows, downscale embedded PNGs before base64 or cache-dedupe shared slots across sheets.

---

## 8. When you come back after `/clear`

1. `git log --oneline | head -10` → confirm tree state (expect `0ed9939 feat(brochure/schema-renderer): Phase 4 …` at top).
2. `python -m pytest tests/ -q` → confirm 634/634 pass.
3. `ls /tmp/phase4-gallery/` → Phase 4 gallery artifacts (may be purged by /tmp rotation; rerun `PYTHONPATH=$PWD python /tmp/phase4-gallery/run.py` if needed, ~30 min).
4. Open `HANDOFF.md` (this file) + `~/.claude/plans/lets-continue-testing-various-cheeky-puddle.md` for full plan context.
5. Next candidate phases:
   - **Phase 2 — Ollama text budgeting** (make the LLM write text that fits char budgets declared in the template).
   - **Phase 4 stretch — `texture_slot` patterns** (generate textures for shape fills).
   - **Phase 6 — real logo embedding** (swap monogram for user-supplied PNG/SVG).

---

## 9. Quick-reference file index

```
flyer_generator/brochure/
├── schema_renderer/          ← Phase 1 + Phase 4 subsystem
│   ├── __init__.py           exports load_template, list_templates, render_schema_brochure, BrochureContent, TemplateSchema, generate_template_images, collect_image_slots, resolve_concept_for_slot
│   ├── __main__.py           CLI (+ --generate-images / --workflow / --style-preset flags)
│   ├── content_model.py      BrochureContent + adapter from BrochureInput
│   ├── image_gate.py         Phase 4: ComfyUI image fill for image_placeholder slots (hero vision gate + parallel spots)
│   ├── loader.py             load_template + list_templates
│   ├── renderer.py           render_schema_brochure(images=) — CORE, embeds base64 PNGs with clipPath masks
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
├── test_renderer.py          24 tests (Phase 4 added 7 embedding tests)
├── test_image_gate.py        16 tests (Phase 4)
└── test_gallery.py           78 dynamic tests (grows with schemas + content)
```

---

**TL;DR for next session:** Phases 1 + 4 shipped. 13 templates, zero-API rendering in 1.2s; or with `--generate-images` generates hero (vision-gated) + spot photos via ComfyCloud, base64-embedded with clipPath masks. 634/634 tests, 16/16 live gallery cells green. README is written. Deferred: Phase 2 Ollama text budgeting, Phase 4 stretch (texture_slot → `<pattern>`), Phase 3 template expansion, Phase 5 text-on-image, Phase 6 real logo embedding.
