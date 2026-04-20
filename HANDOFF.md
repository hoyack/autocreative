# Brochure Generator — Session Handoff

**For a fresh session after `/clear`.** Full state-of-the-world for the schema-driven brochure subsystem.

Prior handoff (pre-schema era): `docs/brochure-improvement-v2.md`.

---

## 1. Quick orientation

- **Branch:** `master`, clean working tree
- **Tests:** `python -m pytest tests/ -q` → 665/665 pass in ~35s
- **Latest commits (newest first):**
  ```
  0bcb02e fix(brochure): close back-panel whitespace + 180s httpx timeout
  3512a35 fix(brochure/image_gate): retry on generate error instead of aborting
  b82521d fix(brochure/text_gen): tighter hero_concept hint so vision gate approves
  fead116 fix(brochure/llm): separate text_max_tokens from vision_max_tokens + wrap JSON errors
  6822bde feat(brochure/schema-renderer): BrochureBrief intake model + brief-aware LLM
  e6c0769 fix(brochure/schema-renderer): loosen char-budget line count + prompt for per-section image_concept
  bb52f65 feat(brochure/schema-renderer): --color-accent CLI override for palette
  4a68382 docs: reflect shipped deferred phases (2 / 4-stretch / 6) in HANDOFF + README
  e1896f8 feat(brochure/schema-renderer): Phase 2 — LLM text budgeting
  0ddd85d feat(brochure/schema-renderer): Phase 6 — real logo embedding
  a08fe18 feat(brochure/schema-renderer): Phase 4 stretch — texture_slot → <pattern>
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
| 2a | ✅ shipped | `BrochureBrief` intake model + brief-aware LLM + verbatim contact overrides (commit `6822bde`) |
| 3 | deferred | Template-library expansion (already 13 — user may want 20+) + authoring docs |
| 4 | ✅ shipped | Image placeholders + vision gate — 4×4 gallery 16/16 green (commit `0ed9939`) |
| 4 stretch | ✅ shipped | `texture_slot` → `<pattern>` tile on shape fills (commit `a08fe18`) |
| 5 | deferred | Text-on-image (flyer-pipeline safe-region port) |
| 6 | ✅ shipped | Real logo embedding — PNG/JPG/SVG via `--logo` (commit `0ddd85d`) |
| **7** | **next up** | **Brand Kit system — scrape website → untracked brand schema → apply to any template. See §8.** |

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

### Phase 2a — `BrochureBrief` intake model (`6822bde`)
Structured interrogative intake: `target_audience`, `brand_voice`, `value_proposition`, `offerings[]`, `differentiators[]`, `testimonials[]`, `awards[]`, `key_stats[]`, `founded_year`, `hours`, `locations[]`, `primary_cta`, `secondary_cta`, `keywords[]`, `source_urls[]`. Attaches to `BrochureContent.brief` and serializes into the LLM user prompt as *INTAKE BRIEF* ground-truth block so the model draws copy from real facts instead of inventing.

`generate_content_from_prompt(..., brief=, contact=)` accepts both. Supplied contact fields override whatever the LLM produces (verbatim phone/address/email preservation). System prompt now pushes "aim for 80-95% of each budget — a half-filled region looks thin" and explicitly bans inventing contact values / testimonials when brief data is available.

CLI: `--brief-json <path>`, `--phone`, `--address`, `--email`, `--url`, `--color-accent #RRGGBB`.

### Live shrubnet one-shot (v7–v9)
End-to-end run against shrubnet.com: WebFetch → brief → `editorial_classic` with `--generate-images --logo --brief-json --email --address --color-accent`. After iteration (v4 → v9 over ~6 rebuilds), every inner-panel region now hits ≥60% of budget. Final commit `0bcb02e` closed the remaining back-sheet whitespace by:
  - Raising bullets `max_chars_per_item` from 60 → 100 so items wrap to 2 lines.
  - Adding a pull-quote region (y=2000 h=340) + attribution (y=2360 h=34) to each inner panel of `editorial_classic`, filling the 440px dead zone between bullets and `org_name`.
  - `_per_item_char_limit` now accounts for bullets-bbox vertical allowance (`lines_per_item = total_lines // max_items`).
  - `text_gen` system prompt now demands specific role-based quote attributions, not org-name repeats.

### Gotchas caught (cumulative)
- **1×1 fake PNGs + cairo OOM.** Initial renderer tests used a hand-rolled 1×1 PNG; cairo OOM'd upsampling to ~900px. Fix: `Pillow.Image.new((128, 128), ...)` for test fixtures.
- **Nested `<?xml?>`** inside another SVG breaks cairosvg. `_strip_svg_prolog()` removes the XML declaration + DOCTYPE before inlining SVG logos.
- `ImagePlaceholder.corner_radius` is `float` → serializes as `"22.0"`; asserts match `rx="22`.
- **`vision_max_tokens=1024` starved text completions** at ~21 fields (truncates JSON mid-response, same spot twice). Split into `text_max_tokens=8192` in `fead116`. Vision calls keep 1024.
- **`_extract_json` leaked `JSONDecodeError`** instead of wrapping in `VisionResponseParseError` — retry path never triggered. Fixed in `fead116`.
- **`httpx.AsyncClient()` default timeout is 5s** — every ComfyCloud hero submit `ReadTimeout`'d before execution. `0bcb02e` sets `timeout=180.0` in `image_gate`.
- **`image_gate` `break` on transient errors** burned remaining hero retries. Changed to `continue` in `3512a35`.
- **Hero vision gate rejects tech-dense imagery** (server racks, UI screens, tight framing) because its rubric demands clean edges for title overlay. `b82521d` tightened the `hero_concept` hint to require landscape composition + low-detail edges.
- **`int(h / line_height)` floored tall title bboxes to 1 line** when they actually fit 1.5–2 lines. Changed to `round()` in `e6c0769`.
- **`content.color_accent` was dead** — renderer only read `template.palette.accent_default`. Added `accent_override` kwarg + `--color-accent` CLI in `bb52f65`.

---

## 7. Open issues / gotchas

- **Fonts read a bit small on the rendered brochure** — particularly inside-panel bullet text and lead paragraphs. Likely a mix of (a) template `body_size`/`bullet_size` set conservatively, (b) `text_fit` `_DEFAULT_EM=0.55` + `safety=0.92` underestimates width, encouraging tighter sizes than needed. Worth revisiting after the brand-kit phase: either bump template typography sizes, or re-calibrate the char-width table so budgets allow larger type for the same region. Not an actual blocker — just worth fixing before calling outputs "production-ready."
- **Phase 3** — template library expansion still open; 13 templates today. Adding templates is JSON-only, no Python.
- **Phase 5** — text-on-image safe-region detection (flyer-pipeline port). Not started.
- **Template font families are CSS strings** (`'Playfair Display', serif`). If the rasterizer doesn't have the font installed, it falls back to the next in the stack. `flyer_generator/assets/fonts/` is empty — drop subsetted woff2 files to get exact typography. Not blocking but looks less polished without.
- **`docs/brochure-templates/`** still contains the 10 original JSONs (copied into `flyer_generator/brochure/schemas/` rather than moved — docs/brochure-templates/ is the "design reference" directory). No harm; identical.
- **Gallery PDFs are large** (~17 MB per cell) because each embeds 2–4 real 1472×832 photos base64'd into SVG, then rasterized at 3376×2626 and wrapped in PDF. Acceptable for print; if this grows, downscale embedded PNGs before base64 or cache-dedupe shared slots across sheets.
- **Texture generation** — `--textures-dir` is fed by the user today. There is no LLM/ComfyUI orchestrator that generates textures to match a template's needs; that's a future iteration (could piggyback on `image_gate`).
- **Hero vision gate rejects tech-dense imagery for text-forward templates.** For brand-kit demos where the business is explicitly technical, prefer landscape-oriented abstractions (bokeh, mesh-fade horizons) rather than literal server rooms / screens.

---

## 8. Next up — Phase 7: Brand Kit system

User spec (verbatim intent, paraphrased for clarity):

> Store untracked brand schemas defined from a tracked template schema. Generate a brand-kit schema from a website — headless Playwright likely, simple `requests` as fallback. Capture brand colors, fonts, styles, logo, plus everything you'd have in a professional brand kit. Apply the kit to the brochure template so it injects colors. Use a library that checks safe color combos. Watch for contrast across shapes. Build a visual inspection + adversarial testing loop. (Fonts often read a bit small — worth addressing at the same time.)

### Architecture sketch (for `/gsd-plan-phase`)

**Data model** (new `flyer_generator/brand_kit/`):
- `BrandKit` Pydantic:
  - `name: str` + `source_url: str | None` + `fetched_at: datetime`
  - `palette: BrandPalette` — primary, secondary, accent, neutral_dark, neutral_light, extras (dict); each color also carries `usage_hint` ("primary CTA", "heading", etc.)
  - `typography: BrandTypography` — heading_family (CSS stack), body_family, size_scale (hero, display, heading, subheading, body, caption), font_sources (urls to woff2 if fetchable)
  - `logos: list[BrandLogo]` — each with path/url, variant ("primary", "mono-dark", "mono-light", "mark-only"), format, aspect_ratio
  - `voice: BrandVoice | None` — tone, example_phrases, banned_words
  - `photography: BrandPhotoHints | None` — preferred style_preset, color grade notes
  - `source_artifacts: list[str]` — screenshot paths, html dumps, css files captured during scrape

**Storage**:
- Tracked: `.brand-kit-template.json` (shape reference; live in-repo so schema stays in sync with code)
- Untracked: `.brand-kits/<slug>/` with `brand.json`, `logos/*.png`, `source/*.html`, `source/*.css`, `source/screenshot.png`. User-configurable via env var `FLYER_BRAND_KITS_DIR` (default `.brand-kits/` relative to cwd). Add to `.gitignore`.

**Scraper** (`brand_kit/scraper.py`):
- Primary: Playwright async, headless, navigates → waits for network idle → extracts:
  - Dominant colors (from screenshot via `Pillow` + `scikit-image` quantization, OR from computed CSS of `:root`, `body`, known selectors)
  - Font families (scrape `<link>` to Google Fonts / self-hosted, `@font-face` from CSS, computed `font-family` on H1/body)
  - Logo candidates (`<img>` in header with "logo" in class/alt/filename; `<svg>` inline with "logo" in class)
  - Meta: `og:site_name`, `title`, description, first H1
- Fallback: `httpx` + `beautifulsoup4` for no-JS sites; loses dynamic CSS but grabs enough for a minimum-viable kit.
- Output: `BrandKit` with everything the scrape could infer. Missing fields stay null — brand-kit editing pass fills them in.

**Color safety / contrast**:
- Library candidates:
  - `wcag-contrast-ratio` (simple; WCAG 2.1 AA/AAA ratio calc)
  - `colour-science` (full CIE-level analysis, overkill for just contrast)
  - `coloraide` (Pydantic-friendly; handles OKLCH / CAM16)
  - Probably `wcag-contrast-ratio` + `coloraide` pair: first for pass/fail AA, second for contrast-preserving tone adjustments.
- Validation rules:
  - Body text on panel background ≥ 4.5 (AA) / 7.0 (AAA)
  - Large text (≥ 24pt) ≥ 3.0
  - Shape fill over shape fill: track every shape and its immediate children in `_render_panel`, compute the contrast ratio of text placed over each, flag if below threshold.
- Auto-remediation: if a text color on a shape-filled bbox fails contrast, swap to the opposite neutral (dark ↔ light) from the palette.

**Applying a kit to a template** (`brand_kit/applier.py`):
- `apply_brand_kit(template: TemplateSchema, kit: BrandKit) -> TemplateSchema` returns a new template with:
  - `palette` swapped from kit palette (with contrast validation against known text roles)
  - `typography.heading_family` and `body_family` replaced by kit stacks
  - `typography.*_size` optionally scaled by a kit-level `size_multiplier` to fix the "fonts are small" observation
- Also pass `logo_bytes` directly to `render_schema_brochure` from the kit's primary logo.
- CLI: `--brand-kit <slug>` loads and applies the kit; orchestrates logo + color + font + photography style.

**Visual inspection + adversarial loop**:
- `brand_kit/audit.py` — after render, run:
  - PIL-based whitespace detector per panel (histogram of pixel density in grid cells; flag cells below threshold)
  - Contrast audit of every text region over its measured background
  - Same budget-fill audit I ran inline this session (formalize it into `audit_content_density(content, template)`)
- Each audit returns structured findings; the orchestrator iterates: fix → re-render → re-audit until clean or max iterations (~3).

### Phase 7 CLI target

```bash
# 1. Create / refresh a brand kit from a website
python -m flyer_generator.brand_kit fetch https://shrubnet.com --slug shrubnet

# 2. Render a brochure with the kit applied
python -m flyer_generator.brochure.schema_renderer \
    --template editorial_classic \
    --prompt "..." \
    --brand-kit shrubnet \
    --generate-images --workflow ernie_landscape \
    --output /tmp/out
```

### Files to create (non-binding — `/gsd-plan-phase` will firm it up)

- `flyer_generator/brand_kit/__init__.py`
- `flyer_generator/brand_kit/models.py` — `BrandKit`, `BrandPalette`, `BrandTypography`, `BrandLogo`, `BrandVoice`
- `flyer_generator/brand_kit/scraper.py` — Playwright-backed, requests fallback
- `flyer_generator/brand_kit/contrast.py` — WCAG checker + remediation
- `flyer_generator/brand_kit/applier.py` — merge a kit into a `TemplateSchema`
- `flyer_generator/brand_kit/storage.py` — read/write `.brand-kits/<slug>/`
- `flyer_generator/brand_kit/audit.py` — post-render visual adversarial loop
- `flyer_generator/brand_kit/__main__.py` — `fetch`, `list`, `show`, `edit` subcommands
- `flyer_generator/brochure/schema_renderer/__main__.py` — accept `--brand-kit <slug>`
- `tests/brand_kit/` — scraper (mocked HTML), models, contrast, applier, audit

### Dependencies to add (`pyproject.toml`)
- `playwright>=1.50` + `playwright install chromium` step in CI
- `wcag-contrast-ratio>=0.9`
- `coloraide>=4.0` (OKLCH + CAM16 color science)
- `beautifulsoup4>=4.13` (requests-fallback scraper)

### When you come back after `/clear`

1. `git log --oneline | head -10` → expect `0bcb02e fix(brochure): close back-panel whitespace …` at top.
2. `python -m pytest tests/ -q` → confirm 665/665 pass.
3. Read this HANDOFF + `README.md`.
4. Run `/gsd-plan-phase` to create a full PLAN.md for Phase 7 Brand Kit, using §8 here as the spec source.
5. Execute the plan with `/gsd-execute-phase`.
6. Live test with `/tmp/shrubnet-brief.json` + `/tmp/shrubnet-e2e/logo.png` as baseline inputs — they're still on disk.

---

## 9. Quick-reference file index

```
flyer_generator/brochure/
├── schema_renderer/          ← Phases 1, 2, 2a, 4 (+ stretch), 6 subsystem
│   ├── __init__.py           load_template, list_templates, render_schema_brochure,
│   │                         BrochureContent, BrochureBrief, Testimonial, TemplateSchema,
│   │                         TextBudget, generate_template_images,
│   │                         generate_content_from_prompt, collect_image_slots,
│   │                         collect_text_budgets, resolve_concept_for_slot
│   ├── __main__.py           CLI — accepts --content OR --prompt; flags
│   │                         --generate-images, --workflow, --style-preset,
│   │                         --logo, --textures-dir, --audience, --brief-json,
│   │                         --phone, --address, --email, --url, --color-accent
│   ├── content_model.py      BrochureContent + BrochureBrief + Testimonial + adapter
│   ├── image_gate.py         Phase 4: ComfyUI image fill (hero vision gate, 180s httpx timeout, retry-on-error)
│   ├── loader.py             load_template + list_templates
│   ├── renderer.py           render_schema_brochure(images=, textures=, logo_bytes=, accent_override=) — CORE
│   ├── schema_model.py       TemplateSchema + every element Pydantic type
│   ├── shapes.py             SVG primitive emitters + texture_slot → <pattern>
│   ├── text_fit.py           text measurement + wrap + char budget (line-count via round())
│   └── text_gen.py           Phase 2 + 2a: LLM text budgeting, brief-aware, contact-verbatim
├── schemas/                  ← 13 template JSONs (editorial_classic enhanced with inner-panel pull-quote regions)
├── generative/               ← LLM-driven legacy path (untouched)
├── stages/                   ← shared stages (composer, layout, pdf, vision, prompt_builder)
└── pipeline.py               v1 BrochureGenerator (layout_choice-aware)

docs/brochure/
└── sample-content/           ← 4 content JSONs (law_firm, kids_coding_camp, tech_startup, nonprofit)

tests/brochure/schema_renderer/
├── test_schema_model.py      20 tests
├── test_shapes.py            23 tests (+4 texture_slot)
├── test_text_fit.py          11 tests
├── test_content_model.py     13 tests
├── test_loader.py            7 tests
├── test_renderer.py          40 tests (Phase 4 + 4-stretch + Phase 6 + accent override)
├── test_image_gate.py        17 tests (+1 retry-on-transient-error)
├── test_text_gen.py          18 tests (Phase 2 + 2a brief/contact passthrough)
└── test_gallery.py           78 dynamic tests

One-shot inputs still on disk for Phase 7 seeding:
  /tmp/shrubnet-brief.json    — BrochureBrief JSON from scraped shrubnet.com
  /tmp/shrubnet-e2e/logo.png  — 1024×1024 RGBA logo
  /tmp/shrubnet-v9/           — final v9 brochure artifacts (front/back/PDF/content)
```

---

**TL;DR for next session:** Phases 1, 2 (+ 2a brief), 4 (+ stretch), 6 all shipped. One CLI command turns `(--prompt + --brief-json + --email/--address + --logo + --color-accent)` into a dense, brand-verbatim tri-fold brochure with vision-gated hero photo. Iterated adversarial audits this session produced a near-final shrubnet example (`/tmp/shrubnet-v9/brochure_print.pdf`) with every inner-panel region ≥60% of budget. 665/665 tests. Next up: **Phase 7 — Brand Kit system** (scrape site → untracked kit → apply to template → WCAG-validated colors + visual audit loop); spec in §8. Run `/gsd-plan-phase` to kick it off.
