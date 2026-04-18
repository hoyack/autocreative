# Brochure Generator v2 — Prompt-Driven Generative Pipeline

**Status:** design, pre-implementation
**Author:** brandon@hoyack.com
**Date:** 2026-04-18
**Supersedes (where noted):** content-generation sections of `docs/brochure-plan.md`
**Builds on:** v1 brochure module (phases 5-9) which remains the execution substrate

---

## 1. Context

Brochure v1 (phases 5-9) takes a fully-specified `BrochureInput` (title, sections, back panel, etc.) and renders it to PNGs + PDF. It works but puts the entire authoring burden on the caller. v1 is also visually thin — sparse inner panels, weak accent gradients, generic heading style, and fold lines that print.

v2 shifts the burden to an LLM-orchestrated pipeline. The caller supplies a **prompt** and a small amount of optional metadata; the system generates the outline, section text, layout, imagery, and composition, then verifies the result and re-runs weak stages as needed.

v1's pre-filled path (`generate_brochure(brochure: BrochureInput)`) stays live — power users can still supply a full BrochureInput and skip the generative stages. v2 is **additive**.

### Goals

- Accept a natural-language prompt and produce a polished brochure end-to-end.
- Use Ollama for all LLM calls (reuses existing `FLYER_VISION_PROVIDER=ollama` + `FLYER_OLLAMA_*` config, wires up the currently-unused `ollama_text_model`).
- Multi-stage orchestration: outline → text → layout → imagery → fit → compose → verify.
- Visual variety through a named layout template library + parameterized vector shape library.
- Verification loop scores the output on a 5-dimension rubric and re-runs the weakest stage (max 2 cycles).
- Keep v1 API and tests green (92 brochure tests + 179 flyer tests).

### Non-goals

- LLM-emitted raw SVG fragments (chose parameterized templates instead).
- Per-section AI images by default (opted for 1 hero + 0-3 LLM-chosen spot images).
- Per-stage verification loops (chose single holistic verification with targeted regen).
- Removing the `BrochureInput` programmatic path.
- A dedicated frontend / authoring UI.
- Multi-language output — v1 is English only.

---

## 2. Pipeline Overview

```
user prompt + optional (preset, audience, accent, target_length)
    │
    ▼
┌─────────────────┐  LLM text (Ollama) — one call
│ 1. OUTLINE      │  → BrochureOutline: sections[2..5], tone, cta_intent,
│                 │                     suggested_preset, suggested_accent
└─────────────────┘
    │
    ▼
┌─────────────────┐  LLM text (Ollama) — parallel per section
│ 2. TEXT         │  → each section: heading, body, image_hint (None|str)
└─────────────────┘
    │
    ▼
┌─────────────────┐  LLM text (Ollama) — one call
│ 3. LAYOUT       │  → LayoutChoice: template_name, shape_density,
│    SELECTION    │                  accent_placement, cover_treatment
└─────────────────┘
    │
    ▼
┌─────────────────┐  ComfyCloud landscape workflow
│ 4. IMAGERY      │  - 1 hero (cover) — skipped if cover_treatment="shapes_only"
│                 │  - 1-3 spot images for sections with image_hint != None
└─────────────────┘
    │
    ▼
┌─────────────────┐  Local measurement → LLM text only if off by >15%
│ 5. FIT OPTIMIZE │  Per section: measure wrapped-text height vs safe-zone
│                 │  capacity; tight → shorten, loose → expand.
└─────────────────┘
    │
    ▼
┌─────────────────┐  BrochureComposer v2 (template + shape aware)
│ 6. COMPOSE      │  → outside.svg + inside.svg + rasterize + PDF
└─────────────────┘
    │
    ▼
┌─────────────────┐  LLM vision (reuses existing vision provider)
│ 7. VERIFY       │  5-dim rubric → score 0-100
│    (up to 2×)   │  < threshold → identify weakest stage → re-run it with
│                 │  critique; max 2 verification cycles.
└─────────────────┘
    │
    ▼
  BrochureOutput (PNG front + back + PDF + verification report)
```

Stages 1-3, 5, and 7 use LLM calls (5-9 LLM calls total per brochure in the common case). Stage 4 runs 1-4 ComfyCloud generations. Stage 6 is pure local composition.

---

## 3. Data Models

New Pydantic models. All live in `flyer_generator/brochure/models.py` (or a `brochure/generative/models.py` sub-module — decide during implementation).

### `BrochurePrompt` (public input)

| Field | Type | Notes |
|---|---|---|
| `prompt` | `str` | Free-text description. Required. |
| `style_preset` | `str \| None` | Overrides LLM suggestion. One of the six flyer presets. |
| `audience` | `str \| None` | e.g. "young professionals, playful" or "B2B, authoritative" |
| `color_accent` | `HexColor \| None` | Overrides LLM suggestion. |
| `target_length` | `Literal["short","medium","long"]` | Default `"medium"` (~40-60 words/section). |

### `BrochureOutline` (stage 1 output)

| Field | Type | Notes |
|---|---|---|
| `sections` | `list[SectionSpec]` | 2-5 items |
| `tone` | `str` | e.g. "authoritative, warm" |
| `cta_intent` | `str` | 1-sentence description of back-panel CTA |
| `suggested_preset` | `str` | LLM pick from registry |
| `suggested_accent` | `HexColor` | LLM suggestion, can be overridden by caller |

### `SectionSpec` (part of outline)

| Field | Type | Notes |
|---|---|---|
| `heading` | `str` | Final heading |
| `body_brief` | `str` | 1-sentence direction for stage 2 (not the final body) |
| `image_hint` | `str \| None` | If non-None, stage 4 generates a spot image from this hint |
| `panel_role` | `Literal["cover","feature","detail","cta"]` | Informs layout placement |

### `SectionText` (stage 2 output, one per SectionSpec)

| Field | Type | Notes |
|---|---|---|
| `heading` | `str` | |
| `body` | `str` | Final body. May be rewritten in stage 5. |
| `image_hint` | `str \| None` | Carried from SectionSpec |

### `LayoutChoice` (stage 3 output)

| Field | Type | Notes |
|---|---|---|
| `template` | `LayoutTemplateName` (Literal) | One of the six templates |
| `shape_density` | `Literal["sparse","medium","dense"]` | Scales shape count |
| `accent_placement` | `Literal["top_rule","side_band","corner_block"]` | Style tweak |
| `cover_treatment` | `Literal["image_full","image_half_shapes","shapes_only"]` | Dictates stage 4 behavior |

### `GeneratedImagery` (stage 4 output)

| Field | Type | Notes |
|---|---|---|
| `hero_png_bytes` | `bytes \| None` | None if cover_treatment="shapes_only" |
| `spot_images` | `dict[str, bytes]` | Keyed by section heading |
| `hero_vision_verdict` | `VisionVerdict \| None` | Per-hero cover evaluation (reuses existing) |

### `VerificationVerdict` (stage 7 output)

| Field | Type | Notes |
|---|---|---|
| `score` | `int` | 0-100 weighted average |
| `dimension_scores` | `dict[str,int]` | 5 dimensions, each 0-100 |
| `critique` | `str` | Prose critique |
| `weakest_stage` | `Literal["outline","text","layout","imagery","compose"] \| None` | None if score >= threshold |
| `iteration` | `int` | Which verification cycle (1 or 2) |

### `BrochureOutput` (extended from v1)

Add these fields (keep existing):

| Field | Type | Notes |
|---|---|---|
| `verification` | `VerificationVerdict \| None` | None if generated via pre-filled path |
| `outline` | `BrochureOutline \| None` | Only set on prompt path |
| `layout_choice` | `LayoutChoice \| None` | Only set on prompt path |

---

## 4. Stage Specifications

### Stage 1: Outline

**Model:** `settings.ollama_text_model` (via new OllamaTextClient)
**Input:** `BrochurePrompt`
**Output:** `BrochureOutline`

**Prompt:**
```
You are a senior brochure copywriter. Based on the user's prompt, produce a
structured outline for a US Letter tri-fold brochure (max 5 sections).

User prompt: {prompt}
Optional context: audience={audience|none}, style_preset={preset|any},
accent={accent|any}, target_length={target_length}

Return JSON:
{
  "sections": [
    {"heading": "...", "body_brief": "one-sentence direction", "image_hint": "..." or null, "panel_role": "cover"|"feature"|"detail"|"cta"},
    ...
  ],
  "tone": "...",
  "cta_intent": "one sentence describing the back-panel call to action",
  "suggested_preset": "photorealistic|anime|western_cartoon|scifi|watercolor|retro_poster",
  "suggested_accent": "#RRGGBB"
}

Rules:
- 2 to 5 sections total.
- Exactly one section has panel_role="cover" (the hero section).
- image_hint may be non-null on at most 3 sections total (spot images are expensive).
- Honor overrides: if the user specified preset/accent/audience, reflect that in your choices.
```

**Retry policy:** one retry on parse failure, then raise `BrochureOutlineError`.

### Stage 2: Text

**Model:** `settings.ollama_text_model`
**Input:** one `SectionSpec` + parent `BrochureOutline` + `target_length`
**Output:** `SectionText`

Runs N calls in parallel (one per section).

**Prompt:**
```
You are writing one section of a tri-fold brochure.

Brochure tone: {outline.tone}
Section heading: {spec.heading}
Section direction: {spec.body_brief}
Panel role: {spec.panel_role}
Target length: {target_length} (short=~25 words, medium=~50 words, long=~80 words)

Write only the body prose. No heading, no markdown fences. Max one paragraph,
or 2-4 short lines starting with "- " for bullet lists.

Output the body text only.
```

Returns plain text; wrapped into `SectionText` with heading carried from spec.

### Stage 3: Layout selection

**Model:** `settings.ollama_text_model`
**Input:** `BrochureOutline`, optional user preferences
**Output:** `LayoutChoice`

**Prompt:**
```
Choose a layout template for a tri-fold brochure.

Outline:
- Tone: {tone}
- Sections: {for each: heading + role}
- CTA intent: {cta_intent}

Layout templates available:
1. editorial — professional services, B2B, conservative
2. minimalist — tech/SaaS/design studios, lots of whitespace
3. playful — events, kids, food, casual
4. gallery_strip — portfolios, retail, image-heavy
5. quote_driven — non-profits, manifestos, pull-quotes
6. spotlight — single-product or single-event focus

Return JSON:
{
  "template": "<one of the six>",
  "shape_density": "sparse"|"medium"|"dense",
  "accent_placement": "top_rule"|"side_band"|"corner_block",
  "cover_treatment": "image_full"|"image_half_shapes"|"shapes_only"
}

Rules:
- Match template to tone. B2B → editorial; kid-focused → playful.
- shape_density: match tone (conservative → sparse, playful → dense).
- cover_treatment: image_full for most; shapes_only when the concept is abstract/conceptual.
```

**Retry policy:** one retry on parse failure, fall back to `editorial` + `medium` + `top_rule` + `image_full` if still invalid.

### Stage 4: Imagery

**Inputs:** `BrochureOutline`, `LayoutChoice`, style_preset (resolved)
**Output:** `GeneratedImagery`

1. If `cover_treatment != "shapes_only"`: run the existing `BrochureCoverPromptBuilder` + Comfy + vision for the hero. Reuses phase-6 machinery verbatim.
2. For each section where `image_hint is not None` (capped at 3): run a "spot image" generator — same landscape workflow but at smaller target dims and different composition directives (no need for title-safe edges). Simpler prompt: just the style preset + image_hint.
3. Spot images skip vision evaluation (they're decorative — not worth the cost).

### Stage 5: Fit optimization

**Inputs:** Full `BrochureInput` candidate (from stages 1-2), `ResolvedBrochureLayout`
**Output:** Revised `BrochureInput` with tightened/expanded section bodies

Process per section:
1. Compute rendered text height using existing composer's word-wrap + font sizing.
2. Compute safe-zone capacity (panel height - heading - padding).
3. If rendered > 1.15 × capacity: LLM rewrite tighter.
4. If rendered < 0.6 × capacity: LLM rewrite longer (unless `target_length == "short"`).
5. Otherwise: no-op.

**LLM prompt (tighten example):**
```
Rewrite this brochure section body to fit a smaller space.
Current: {body}
Target: about {target_words} words. Preserve key facts and tone. Output the
revised body only.
```

Cap fit optimization at one LLM call per section (no inner loop). If still off after one rewrite, ship as-is and let verification catch it.

### Stage 6: Compose

Uses `BrochureComposer v2`:
- Accepts `LayoutChoice` and `GeneratedImagery` alongside the existing `BrochureInput` + `ResolvedBrochureLayout`.
- Picks rendering strategy from `layout_choice.template` (see §5).
- Picks shape mix from `layout_choice.shape_density` + template-declared shapes.
- Embeds spot images into sections that have them (inner panels).
- Fold lines render only when `render_guides=True` (default False) — fixes v1 print bug.

### Stage 7: Verification

**Model:** existing vision provider (Anthropic or Ollama vision) — reuses `VisionEvaluator` with a new system prompt
**Input:** The composed outside PNG, inside PNG, original prompt, outline summary
**Output:** `VerificationVerdict`

**Prompt:**
```
You are a senior brand designer reviewing a tri-fold brochure.

Original prompt: {prompt}
Outline summary: {sections_as_bullets}
Attached: two images — outside sheet and inside sheet.

Score each dimension 0-100:
1. Content fit — does the copy match the prompt's intent and tone?
2. Visual balance — are panel weights visually even? Any panel cramped or empty?
3. Text legibility — does text fit safely? Any overflow/clipping? Adequate contrast?
4. Layout coherence — does the template suit the content tone?
5. Print readiness — crop marks present? No fold-line bleed? Bleed coverage OK?

Return JSON:
{
  "dimension_scores": {"content_fit": 0-100, "visual_balance": 0-100,
                       "text_legibility": 0-100, "layout_coherence": 0-100,
                       "print_readiness": 0-100},
  "critique": "<2-3 sentence explanation of the lowest-scoring dimension>",
  "weakest_stage": "outline"|"text"|"layout"|"imagery"|"compose"|null
}
```

**Loop behavior:**
- Compute `score = mean(dimension_scores)`. Threshold: 70.
- If score >= 70, accept and return.
- Else if `iteration < 2`: re-run only `weakest_stage` (plus any downstream stages it invalidates) using the `critique` as the revision hint. Re-verify.
- Else: return with `VerificationVerdict` attached; don't loop again.

---

## 5. Layout Template Library

Each template is a Python dataclass / module that declares:
- Default shape mix per panel (front cover, back cover, tuck flap, inner 1-3)
- Typography scale (heading size, body size, accent treatment)
- Accent placement strategy (top_rule / side_band / corner_block)
- Background gradient opacity
- Text alignment and column behavior

### The six v1 templates

| Name | Best for | Shape mix (typical) | Type scale |
|---|---|---|---|
| `editorial` | Professional services, B2B | Top rule + minimal accent bars, serif body | Heading 64px, body 36px, heading tracks tight |
| `minimalist` | Tech, SaaS, design studios | One large accent block per inner panel, lots of whitespace | Heading 72px, body 32px, heading ultra-light weight |
| `playful` | Events, kids, food | Circles off-page on inner panels, rotated blocks for pull-quotes, dot-grid background | Heading 80px, body 36px, heading extrabold |
| `gallery_strip` | Portfolios, retail | Horizontal image band (top half) + text below per panel; fewer shapes | Heading 56px, body 34px, sans |
| `quote_driven` | Non-profits, manifestos | One large pullquote frame per panel, minimal body, accent corner wedge | Heading 48px, body 40px in oval frames |
| `spotlight` | Single-product focus | Oversized hero spanning cover + tuck flap; inner panels have single accent block + short text | Heading 96px on cover, 56px inside |

Templates live in `flyer_generator/brochure/templates/` as one file each. Each file exports a `LayoutTemplate` dataclass instance; a module-level registry maps name → instance.

---

## 6. Vector Shape Library

Parameterized SVG component library in `flyer_generator/brochure/shapes/`. Each shape is a function taking common args + shape-specific args, returning an SVG fragment string.

### Common args

| Arg | Type | Notes |
|---|---|---|
| `panel_rect` | `PanelRect` | The panel the shape lives on |
| `accent_hex` | `str` | Primary accent color |
| `seed` | `int` | Deterministic variation |

### Shape catalog

1. **`circle_offpage(size, offset_direction, text=None)`**
   - Circle partially clipped by the panel edge.
   - `offset_direction` ∈ {top-left, top-right, bottom-left, bottom-right, left, right}
   - Optional text rendered centered within the visible portion.
   - SVG: `<circle>` with `clip-path` at panel bounds.

2. **`rotated_block(angle, width, height, text=None, fill="accent")`**
   - Rectangle rotated by `angle` degrees (typically -15° to +15°).
   - Fill: accent color or transparent with accent stroke.
   - SVG: `<g transform="rotate(...)"><rect>...</rect><text>...</text></g>`

3. **`accent_bar(placement, thickness)`**
   - Placement ∈ {top, side, diagonal}. Solid or dashed.
   - SVG: `<line>` or `<rect>`.

4. **`dot_grid(density, color)`**
   - Regular dot pattern filling the panel bleed background.
   - Density: 'sparse' (24px spacing), 'medium' (16px), 'dense' (8px).
   - SVG: `<pattern>` + `<rect fill="url(#...)">`.

5. **`pullquote_frame(shape, text)`**
   - Shape ∈ {oval, asym_block}. Contains wrapped text.
   - SVG: `<ellipse>` or `<path>` + `<text>` inside.

6. **`corner_wedge(corner, size, pattern)`**
   - Solid / striped / dotted triangle filling a corner.
   - SVG: `<polygon>` or `<path>`.

### Shape selection

LayoutTemplate declares per-panel shape mix like:
```python
shape_mix = {
    "cover": [],  # hero image carries the cover
    "back_cover": ["accent_bar(top)", "corner_wedge(bottom-right)"],
    "tuck_flap": ["rotated_block(text=heading_hint)"],
    "inner_left": ["dot_grid(sparse)", "circle_offpage(top-left)"],
    "inner_center": ["pullquote_frame(oval)"],
    "inner_right": ["circle_offpage(bottom-right)", "accent_bar(top)"],
}
```

`shape_density` from LayoutChoice scales the mix: `sparse` → drop every other decorative shape; `dense` → duplicate or add secondary shapes (determined by template).

---

## 7. Verification Rubric (Details)

Scoring is 0-100 per dimension; equal weights for the average.

### Dimensions

1. **Content fit** — does the copy match the prompt's intent and tone? (Sentinel: does at least one section directly address the prompt's main subject?)
2. **Visual balance** — panel weights visually balanced; no panel empty or overstuffed.
3. **Text legibility** — no clipping, overflow, or low-contrast text against accent areas.
4. **Layout coherence** — template choice appropriate for the content tone.
5. **Print readiness** — crop marks present, no fold-line printing, bleed coverage present, no raw `null` / `None` strings leaking into output.

### Threshold and loop

- Pass: score ≥ 70.
- Fail: LLM names `weakest_stage`. Re-run that stage only (plus any dependent stages — e.g., re-running `text` implies re-running `fit` and `compose`). Re-verify.
- Max 2 verification loops. On exhaustion, attach the last `VerificationVerdict` and return.

### Escape hatch

Users can pass `verify_threshold: int = 0` to skip verification entirely (fast mode for drafts / demos).

---

## 8. Backward Compatibility & Public API

### Kept as-is

- `BrochureGenerator(settings).generate(brochure: BrochureInput)` — unchanged.
- `generate_brochure(brochure, settings, presets)` — unchanged.
- All 92 existing brochure tests + 179 flyer tests stay green.

### Added

```python
# New public-API entry point
from flyer_generator.brochure import generate_brochure_from_prompt

async def generate_brochure_from_prompt(
    prompt: str,
    settings: Settings | None = None,
    style_preset: str | None = None,
    audience: str | None = None,
    color_accent: str | None = None,
    target_length: Literal["short","medium","long"] = "medium",
    verify_threshold: int = 70,
    max_verify_iterations: int = 2,
) -> BrochureOutput: ...
```

Under the hood this constructs a `BrochurePrompt`, runs the generative pipeline (stages 1-5) to produce a `BrochureInput` + `LayoutChoice` + `GeneratedImagery`, then runs the existing composer (stage 6) + verification loop (stage 7).

### CLI

```bash
# Existing (unchanged):
python -m flyer_generator.brochure --brochure-json data.json --output out/

# New:
python -m flyer_generator.brochure \
  --prompt "Tri-fold brochure for a local yoga studio for new moms" \
  --audience "new moms, friendly" \
  --accent "#7BB661" \
  --output out/

# New flags:
--prompt TEXT           # the user prompt (mutually exclusive with --brochure-json and --title)
--audience TEXT         # audience/tone hint
--target-length TEXT    # short|medium|long (default medium)
--verify-threshold INT  # default 70, pass 0 to skip verification
```

---

## 9. Ollama Wiring

### Existing (phase 6)

- `FLYER_VISION_PROVIDER=ollama` → VisionEvaluator uses OpenAI-compatible /v1/chat/completions
- `ollama_vision_model` → drives cover vision evaluation
- `ollama_text_model` → declared in config, not wired to any stage

### v2 additions

- New `OllamaTextClient` in `flyer_generator/brochure/llm_client.py`
  - Mirrors VisionEvaluator's httpx transport (same base URL, same auth header)
  - Exposes `async def complete(system: str, user: str, *, response_format: Literal["text","json"]) -> str`
  - For json mode: retries once on parse failure, else raises
- All text-only stages (1, 2, 3, 5, and verification's text critique) use this client
- Verification's vision call continues to use the existing `VisionEvaluator`
- If `vision_provider="anthropic"`: provide a sibling `AnthropicTextClient` with identical interface so stages work on either backend without branching

### Model resolution logic

```python
if settings.vision_provider == "ollama":
    text_client = OllamaTextClient(settings)       # uses ollama_text_model
    vision_client = VisionEvaluator(settings, require_zones=False, system_prompt=VERIFY_PROMPT)
else:
    text_client = AnthropicTextClient(settings)    # uses vision_model (same Claude for text)
    vision_client = VisionEvaluator(settings, require_zones=False, system_prompt=VERIFY_PROMPT)
```

---

## 10. Phased Rollout

Five new phases. Each is individually shippable and testable; phases 10-12 do not require ComfyCloud or Anthropic credentials to develop and test.

### Phase 10 — LLM Clients + Outline + Text Stages

**Deliverables:**
- `flyer_generator/brochure/llm_client.py` — `OllamaTextClient` + `AnthropicTextClient` sharing a `TextClient` protocol
- `flyer_generator/brochure/generative/outline.py` — `generate_outline(prompt, text_client) -> BrochureOutline`
- `flyer_generator/brochure/generative/text.py` — `generate_section_texts(outline, text_client) -> list[SectionText]`
- New models: `BrochurePrompt`, `BrochureOutline`, `SectionSpec`, `SectionText`
- Tests with mocked text clients

**Gates:**
- Outline for a given prompt produces 2-5 sections with valid structure
- Each section gets body text within target-length tolerance
- JSON parse retry works; malformed JSON on both attempts raises `BrochureOutlineError`

### Phase 11 — Layout Selection + Template Library

**Deliverables:**
- `flyer_generator/brochure/templates/` — six `LayoutTemplate` instances (editorial, minimalist, playful, gallery_strip, quote_driven, spotlight)
- `flyer_generator/brochure/generative/layout.py` — `choose_layout(outline, text_client) -> LayoutChoice`
- `flyer_generator/brochure/generative/fit.py` — `optimize_fit(brochure_input, layout, text_client) -> BrochureInput`
- Tests: each template renders correctly with FULL_BROCHURE fixture; layout selection logic exercised with canned outlines

**Gates:**
- Six templates render without overlap; distinct visual signatures (spot-check via rasterized PNGs committed to `tests/brochure/fixtures/expected/`)
- `choose_layout` returns valid LayoutChoice for every canned outline
- Fit optimizer converges after one pass for 80% of cases

### Phase 12 — Vector Shape Library + Composer v2

**Deliverables:**
- `flyer_generator/brochure/shapes/` — six shape functions (circle_offpage, rotated_block, accent_bar, dot_grid, pullquote_frame, corner_wedge)
- `flyer_generator/brochure/stages/composer.py` refactor to accept `LayoutChoice` and render template + shapes
- Fix v1 fold-line bug: `render_guides: bool = False` parameter
- Fix v1 back-panel `kind` leak: map kind → heading title or blank
- Tests: each shape renders as valid SVG, composer respects LayoutChoice

**Gates:**
- All 6 shapes emit valid SVG within panel bounds
- No fold lines in production output (only when `render_guides=True`)
- Composer v2 passes all existing v1 composer tests (via a compatibility layer that synthesizes a default LayoutChoice when none provided)

### Phase 13 — Imagery Orchestration + Verification Loop

**Deliverables:**
- `flyer_generator/brochure/generative/imagery.py` — `generate_imagery(outline, layout_choice, settings) -> GeneratedImagery`
- Spot-image prompt variant (no vision eval, simpler directives)
- `flyer_generator/brochure/generative/verify.py` — `verify_brochure(images, prompt, outline, vision_client, text_client) -> VerificationVerdict`
- Verification loop orchestrator that re-runs weakest stage
- Tests: mock ComfyCloud for spot images; mock vision for verification; verify loop limits iterations correctly

**Gates:**
- 1 hero + up to 3 spot images generated correctly; `shapes_only` cover skips hero
- Verification returns valid VerificationVerdict with score 0-100
- Loop terminates after max 2 iterations even when score stays low

### Phase 14 — Public API + CLI + End-to-End

**Deliverables:**
- `generate_brochure_from_prompt()` public API wiring all stages
- CLI `--prompt`, `--audience`, `--target-length`, `--verify-threshold` flags
- Integration tests with mocked Comfy + LLM producing end-to-end output
- One "golden path" test that runs the full pipeline with canned mocks and asserts on BrochureOutput structure + verification verdict attached
- Update `docs/brochure-v2-plan.md` status to "implemented"; add usage examples to project README (if exists)

**Gates:**
- `python -m flyer_generator.brochure --prompt "..." --output out/` produces three files + verification report
- All phases 5-14 tests green; 179 flyer tests still green
- CLI `--prompt` + `--brochure-json` mutual exclusion enforced

---

## 11. Open Questions (resolved during implementation)

1. **Spot image dims.** What target size for non-cover spot images? Proposal: same 1472×832 landscape but downscaled to ~600×400 at compose time. Decide in phase 13.
2. **Verification re-run scope.** If `weakest_stage == "compose"`, is it worth re-running compose without changing inputs (different shape seed)? Lean yes — variance in shape placement might fix visual balance.
3. **Ollama model choice.** Config says `llama3.2` for text, `llama3.2-vision` for vision. For complex JSON outputs in stage 1 & 3, is llama3.2 smart enough or do we need a bigger Ollama model? Validate in phase 10 with benchmark prompts.
4. **Fit optimization fallback.** If the rewritten body is still off-capacity, do we clip, shrink font, or accept? Proposal: accept, let verification flag it.
5. **Per-section image hints.** Should we allow the user to steer spot-image content, or strictly let the LLM decide? Proposal: expose an `allow_spot_images: bool = True` param; no finer control in v1.

---

## 12. Non-Goals (explicit)

- LLM-emitted raw SVG (chose parameterized templates instead).
- Per-section AI images by default (opted for cover + 0-3 spots).
- Per-stage verification loops (chose single holistic pass).
- Removing the `BrochureInput` programmatic path.
- Multi-language brochures.
- Custom font uploading.
- A browser-based authoring UI.
- Real-time preview during generation.

---

## 13. Next Steps

1. Review this doc; push back on anything that's wrong or missing before implementation starts.
2. Add phases 10-14 to `.planning/ROADMAP.md`.
3. Open phase 10 via `/gsd-plan-phase 10` (or proceed through `/gsd-autonomous` for autonomous delivery).
4. Retain v1 doc (`docs/brochure-plan.md`) — it still describes the composition substrate accurately.
