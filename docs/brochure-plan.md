# Brochure Generator — Design Plan

**Status:** design, pre-implementation
**Author:** brandon@hoyack.com
**Date:** 2026-04-17
**Relates to:** `docs/spec.md` (flyer generator v1)

---

## 1. Overview

This project currently generates **1080×1920 portrait event flyers**. The pipeline is: event input → prompt build → ComfyCloud background generation → Pillow upscale → Claude (default) or Ollama (alternate) vision evaluation → SVG layout → CairoSVG rasterise → PNG.

> Note: the stack is **ComfyCloud** (hosted, REST API) and **Anthropic Claude** by default, with **Ollama / OpenAI-compatible** as an alternate vision backend. It is *not* a local-ComfyUI-plus-Ollama setup.

We want to extend the system to produce a second artifact: a **tri-fold landscape brochure**. The goals are:

- Reuse the existing ComfyCloud + vision + rasterisation plumbing.
- Leave the flyer pipeline untouched and stable.
- Produce print-ready output (PNG sheets + a combined PDF with bleed and crop marks).
- Keep the content model general-purpose so brochures aren't restricted to events.

This document is the design that a later implementation phase (GSD) will work from. It is not itself an implementation plan — no code is written in this session.

---

## 2. Print Format & Geometry

**Sheet:** US Letter landscape, 11″ × 8.5″, 300 DPI → **3300 × 2550 px** per sheet.

**Bleed:** 0.125″ on all sides → working canvas **3375 × 2625 px**, trimmed to 3300 × 2550.

**Safe zone:** 0.25″ inside the trim line — no critical text or logos outside of it.

**Tri-fold geometry (two sheets, six panels):**

```
OUTSIDE sheet (printed side, what's visible when folded closed)
+------+------+------+
|  6   |  1   |  2   |   panel 6 = back cover
| back | front| tuck |   panel 1 = front cover
|cover |cover | flap |   panel 2 = tuck flap
+------+------+------+

INSIDE sheet (printed side, what's visible when folded open)
+------+------+------+
|  3   |  4   |  5   |   panels 3/4/5 = inner spread, left→right
| inner| inner| inner|
|  L   |  C   |  R   |
+------+------+------+
```

**Panel width:** v1 renders all three panels at equal width (sheet ÷ 3). The real-world convention is to make the tuck-flap ≈1/16″ narrower so it seats cleanly when folded; we'll add that asymmetry as a follow-up if prototype folds misalign.

**Fold lines:** two vertical folds per sheet at 1/3 and 2/3 of the width. Rendered as non-printing guide marks on a separate SVG layer so they don't appear in the final print.

**Crop marks:** 0.25″ L-shaped marks at each of the four trim corners, positioned in the bleed area.

---

## 3. Data Model

New Pydantic v2 models (mirror the patterns in `flyer_generator/models.py`):

### `BrochureInput`

| Field | Type | Notes |
|---|---|---|
| `title` | `str` | Front cover headline. |
| `subtitle` | `str \| None` | Optional cover subtitle. |
| `hero_concept` | `str` | Feeds ComfyCloud prompt; analogue of `EventInput.style_concept`. |
| `style_preset` | `str` | Reuses existing `PresetRegistry` (photorealistic, anime, watercolor, etc.). |
| `color_accent` | `HexColor` | Hex-validated; same validator as flyer. |
| `org` | `str` | Publisher / issuer. |
| `contact` | `ContactBlock` | name, phone, email, url, address — all optional. |
| `sections` | `list[BrochureSection]` | 2–5 items enforced via `Field(min_length=2, max_length=5)`. |
| `back_panel` | `BrochureBackPanel \| None` | If `None`, auto-fill with org + contact block. |

### `BrochureSection`

| Field | Type | Notes |
|---|---|---|
| `heading` | `str` | Section title. |
| `body` | `str` | Plain text with light markdown: lines starting `- ` become bullets. |
| `icon_hint` | `str \| None` | Reserved for future icon selection; v1 ignores. |

### `BrochureBackPanel`

| Field | Type | Notes |
|---|---|---|
| `kind` | `Literal["cta", "bio", "map_stub", "contact"]` | Picks a rendering template. |
| `content` | `str` | Free text; interpretation depends on `kind`. |

### `ContactBlock`

| Field | Type |
|---|---|
| `name`, `phone`, `email`, `url`, `address` | all `str \| None` |

### `BrochureOutput`

| Field | Type | Notes |
|---|---|---|
| `front_png_bytes` | `bytes` | Outside sheet, 3300×2550. |
| `back_png_bytes` | `bytes` | Inside sheet, 3300×2550. |
| `pdf_bytes` | `bytes` | 2-page PDF with bleed + crop marks. |
| `dimensions` | `tuple[int, int]` | `(3300, 2550)`. |
| `attempts_used` | `int` | Hero-image regen attempts. |
| `hero_vision_verdict` | `VisionVerdict` | Reused from flyer models. |
| `trace_id` | `str` | Per-run correlation. |
| `.save(dir)` | method | Writes `brochure_front.png`, `brochure_back.png`, `brochure_print.pdf`. |

### Panel Assignment Algorithm (v1, deterministic)

1. Front cover (panel 1) → hero AI image + `title` + `subtitle`.
2. Back cover (panel 6) → `back_panel` if present, else auto org/contact.
3. Tuck flap (panel 2) → `sections[0]` compressed (heading + first 2 sentences of body), or contact fallback.
4. Inner panels (3, 4, 5) → `sections[1..3]` in order.
5. If `sections` has a 5th item, it overflows as a compact list at the bottom of panel 5.

---

## 4. Pipeline & Module Layout

New parallel module `flyer_generator/brochure/` alongside the existing flyer code. Shares the core plumbing.

```
flyer_generator/
├── brochure/
│   ├── __init__.py              # exports generate_brochure, BrochureGenerator, models
│   ├── models.py                # BrochureInput, BrochureSection, BrochureBackPanel, BrochureOutput, ...
│   ├── pipeline.py              # BrochureGenerator orchestrator + regen loop
│   └── stages/
│       ├── prompt_builder.py    # landscape cover prompt; reuses PresetRegistry + FLYER_DIRECTIVES
│       ├── layout.py            # panel rects w/ bleed & safe zone; replaces 9-zone grid
│       ├── composer.py          # builds two SVG docs (outside, inside)
│       └── pdf.py               # reportlab: combines 2 PNGs into print PDF + crop marks
└── workflows/
    └── turbo_landscape.json     # NEW — landscape variant of turbo_portrait
```

### Stage-by-stage

1. **`brochure/stages/prompt_builder.py`** — composes the ComfyCloud workflow JSON for the cover hero. Reuses `PresetRegistry`, `StylePreset`, `FLYER_DIRECTIVES`, `UNIVERSAL_NEGATIVE` from `flyer_generator/presets.py`. Adds a `BROCHURE_COVER_DIRECTIVES` block (centred subject, clean left/right edges for text overlay, landscape framing). Loads `turbo_landscape.json` via `workflow_loader.load_workflow()`.

2. **`ComfyClient`** — reused **unchanged** from `flyer_generator/stages/comfy_client.py`. Same submit/poll/download cycle.

3. **`ImagePreprocessor`** — reused **unchanged** from `flyer_generator/stages/preprocessor.py`. Upscales the 1472×832 Comfy output to cover panel size using Pillow LANCZOS.

4. **`VisionEvaluator`** — reused from `flyer_generator/stages/vision.py` with a **brochure-specific prompt variant**. Key difference: no 9-zone assignment needed — the cover layout is fixed. Prompt asks "is this image appropriate as a landscape brochure cover for `{concept}`?" plus quality/subject-match checks. Confidence gate and regen loop are identical to flyer.

5. **`brochure/stages/layout.py`** — computes each panel's pixel rect, given sheet dims, bleed, and safe zone. Returns a `ResolvedBrochureLayout` with six panel rectangles and associated safe-zones. Pure function; no I/O.

6. **`brochure/stages/composer.py`** — builds **two** SVG documents:
   - Outside sheet: hero image base64-embedded on panel 1; accent-tinted gradient backgrounds on panels 2 and 6; text layers per panel using the safe-zone rects.
   - Inside sheet: gradient backgrounds on all three panels; text layers.
   - Both sheets get fold lines and crop marks on a separate non-printing layer.
   - Text layout logic: heading + body, word-wrapped, font-size scales down if overflow (pattern from existing composer).

7. **`Rasterizer`** — reused **unchanged** from `flyer_generator/stages/rasterizer.py`. Runs twice (once per sheet), producing 3300×2550 PNG bytes.

8. **`brochure/stages/pdf.py`** — **new capability.** Uses `reportlab` to build a 2-page PDF sized to the bleed canvas (3375×2625 @ 300 DPI), places each PNG at the correct origin, draws crop marks in the bleed area.

### Regeneration loop

Same semantics as `FlyerGenerator`: if vision rejects the hero image, feed the refinement hint back to the prompt builder and retry up to `max_bg_attempts`. No per-panel regen (other panels don't have AI content).

---

## 5. ComfyCloud Workflow — Landscape Variant

Add `flyer_generator/workflows/turbo_landscape.json`, a copy of `turbo_portrait.json` with:

- `_flyer_meta.name` = `"turbo_landscape"`
- `_flyer_meta.latent_dimensions` = `[1472, 832]` (landscape 16:9-ish)
- `_flyer_meta.injection_points` — same keys (`positive_prompt`, `negative_prompt`, `seed`), same node IDs
- Node graph: identical to portrait except the EmptyLatentImage (or SDXL latent node) width/height swapped.

The existing `workflow_loader.load_workflow(name)` works without modification — it already resolves by name against `flyer_generator/workflows/`.

Generation flow: ComfyCloud returns 1472×832 → `ImagePreprocessor.upscale` → composition fits the cover panel (~1100 × 2550 trimmed area → the image is cropped to the panel aspect at compose time).

---

## 6. Vision Evaluation

Vision runs on the **hero image only**. Other panels are gradient-filled and don't need evaluation.

The vision prompt is a variant of the flyer prompt that:

- Evaluates subject match, mood, visual quality, absence of distorted people/text.
- Returns `approved: bool`, `confidence: 0..1`, `rejection_reasons`, `refinement_hint`, `text_color: "white" | "dark"`.
- **Skips** the 9-zone grid classification.

The `VisionEvaluator` class stays generic enough to accept either prompt variant. Simplest implementation: add an optional `prompt_template` parameter (defaults to flyer template); the brochure pipeline passes the brochure template.

Confidence gate (`vision_confidence_threshold`) and retry-on-parse-failure behaviour are reused as-is.

---

## 7. Output

The brochure generator emits three artifacts:

| File | Format | Dimensions |
|---|---|---|
| `brochure_front.png` | PNG | 3300×2550 (trimmed) or 3375×2625 (with bleed, configurable) |
| `brochure_back.png` | PNG | same |
| `brochure_print.pdf` | PDF | 2 pages, 3375×2625 @ 300 DPI (with bleed), crop marks in bleed area |

`BrochureOutput.save(dir)` writes all three.

**PDF library choice:** `reportlab` — mature, pure-Python, precise drawing primitives, supports custom crop marks and exact placement. Adds a dep to `pyproject.toml`. Considered alternatives:

| Lib | Verdict |
|---|---|
| `reportlab` | **Chosen.** Drawing + page assembly in one tool. |
| `pypdf` | Rejected. Good for assembly, can't draw crop marks. |
| `cairosvg` + SVG pages | Rejected. SVG→PDF via cairo produces correct pages but we'd have to hand-build the bleed canvas in SVG anyway, so we'd be duplicating reportlab's job. |
| `weasyprint` | Rejected. HTML/CSS pipeline; doesn't fit our SVG-first composer. |

---

## 8. Configuration

Three new settings added to `flyer_generator/config.py` with the `FLYER_` env prefix:

| Setting | Default | Purpose |
|---|---|---|
| `brochure_workflow` | `"turbo_landscape"` | Workflow name for brochure hero generation. |
| `brochure_dpi` | `300` | Target DPI; multiplied against inch-based dims. |
| `brochure_output_dir` | `./output/brochures` | Default output directory. |

Existing settings (API keys, vision provider, regen policy, polling) are reused without change.

`.env.example` gains entries for the three new keys.

---

## 9. CLI & Public API

**CLI:** add a subcommand rather than a flag — cleaner than overloading `flyer-generator` with a `--kind brochure` switch.

```bash
# Existing (unchanged):
python -m flyer_generator --title "..." --date "..." ...

# New:
python -m flyer_generator brochure \
    --title "..." \
    --concept "..." \
    --preset photorealistic \
    --accent "#F59E0B" \
    --sections-json sections.json \
    --org "Acme" \
    --output ./output/brochures/
```

Brochure-specific flags:

| Flag | Purpose |
|---|---|
| `--title` / `--subtitle` | Cover text. |
| `--concept` | Hero image concept. |
| `--preset` | Style preset. |
| `--accent` | Hex colour. |
| `--org` | Publisher. |
| `--sections-json` | Path to JSON file with list of `{heading, body}` sections. |
| `--brochure-json` | Load full `BrochureInput` from JSON (analogue of `--event-json`). |
| `--output` | Output directory (default from settings). |
| `--dry-run` | Print prompts / panel plan, don't call APIs. |
| `--max-attempts` | Override hero regen attempts. |

**Public API:**

```python
from flyer_generator.brochure import (
    BrochureGenerator,
    BrochureInput,
    BrochureSection,
    BrochureOutput,
    generate_brochure,  # async convenience function
)
```

Parallel to `generate_flyer` — a one-shot async function for module users.

---

## 10. Testing Strategy

Parallel to the existing `tests/` tree:

```
tests/
└── brochure/
    ├── fixtures/
    │   └── sample_brochures.py      # 2–3 canned BrochureInput examples
    ├── test_models.py               # section count bounds, hex validation, defaults
    ├── test_layout.py               # panel geometry math (bleed, safe zone, fold positions)
    ├── test_prompt_builder.py       # concept substitution, brochure cover directives applied
    ├── test_composer.py             # SVG structure: 6 panels, gradients on non-cover, hero embedded, crop marks on separate layer
    ├── test_pipeline.py             # integration w/ mocked ComfyClient + VisionEvaluator; regen loop and error paths
    ├── test_pdf.py                  # PDF page count, page size, crop mark presence (parse bytes w/ pypdf)
    └── test_cli.py                  # brochure subcommand arg parsing, dry-run, brochure-json loading
```

Patterns mirror existing tests — `respx` for HTTP mocking, `pytest-asyncio` for async stages, Pydantic model round-trips for validation.

---

## 11. Phased Rollout (for the implementation plan)

Proposed split into GSD phases — each phase ships a clean, testable slice:

| Phase | Deliverable | Gates |
|---|---|---|
| **B1** | `BrochureInput` + related models, panel geometry (`layout.py`) with unit tests. No rendering. | Models validate, layout rects pass geometry assertions. |
| **B2** | `turbo_landscape.json` workflow, brochure prompt builder, vision hook for cover evaluation. End-to-end hero-image generation (no composition yet). | Hero image bytes returned; vision verdict parseable. |
| **B3** | SVG composer for outside + inside sheets, rasteriser integration → two 3300×2550 PNGs. | PNGs open, dimensions correct, gradients + hero + text present. |
| **B4** | PDF assembly with `reportlab`, bleed canvas, crop marks. | 2-page PDF, correct page size, crop marks in bleed. |
| **B5** | CLI subcommand, public API, smoke test with a real sample brochure. | `python -m flyer_generator brochure ...` produces 3 files. |

Each phase gets its own `.planning/phases/NN-brochure-BX/` directory under the normal GSD flow.

---

## 12. Shared vs. New Code — Summary

### Reused unchanged
- `flyer_generator/config.py` (plus 3 new settings added)
- `flyer_generator/presets.py` — `PresetRegistry`, `StylePreset`, `FLYER_DIRECTIVES`, `UNIVERSAL_NEGATIVE`
- `flyer_generator/stages/comfy_client.py` — `ComfyClient`
- `flyer_generator/stages/preprocessor.py` — `ImagePreprocessor`
- `flyer_generator/stages/rasterizer.py` — `Rasterizer` (cairosvg)
- `flyer_generator/workflow_loader.py` — `load_workflow()`
- `flyer_generator/models.py` — `VisionVerdict`, `HexColor` validator pattern
- Error hierarchy (`MaxAttemptsExceededError`, etc.)

### Reused with a parameter change
- `flyer_generator/stages/vision.py` — `VisionEvaluator` accepts an optional brochure prompt template

### New
- `flyer_generator/brochure/` — module tree above
- `flyer_generator/workflows/turbo_landscape.json`
- `tests/brochure/` — test tree above
- `reportlab` dependency in `pyproject.toml`
- `BROCHURE_COVER_DIRECTIVES` prompt block
- `BrochurePDFError` exception

### Untouched
- `flyer_generator/pipeline.py` (flyer orchestrator)
- `flyer_generator/stages/composer.py` (flyer composer)
- `flyer_generator/stages/prompt_builder.py` (flyer prompt builder)
- `flyer_generator/__main__.py` existing CLI surface (new `brochure` subcommand is additive)
- `flyer_generator/__init__.py` existing exports (new imports are additive)

---

## 13. Open Questions

To resolve during implementation, not now:

1. **Typography:** reuse the flyer's font stack, or introduce a serif for body text to suit brochure density?
2. **Icon rendering:** the `icon_hint` field on `BrochureSection` — resolve against a local SVG library (feather/heroicons) or skip for v1?
3. **Print-shop variants:** A4 landscape and 11×17 half-fold as future formats. Not v1 — flagged for B6+.
4. **Tuck-flap width asymmetry:** defer the 1/16″ narrowing until a real fold test shows it's needed.
5. **Accent gradient style:** linear top→bottom, radial, or subtle noise-textured? Cosmetic; decide in B3 review.
6. **Section overflow:** if a user passes 5 sections, we overflow into a bottom list on panel 5. Alternative: reject at validation. Current v1: overflow, warn.

---

## 14. Non-Goals

Explicitly out of scope for this design and the first implementation:

- Multi-page stacked brochures (>2 sheets).
- Bi-fold or gate-fold formats.
- Per-panel AI imagery (all 6 panels being AI-generated).
- Interactive / clickable PDF features.
- Custom font uploading.
- Automatic translation / localisation.
- Editable source files (PSD/AI/InDesign export).

---

## 15. Next Steps

1. Review this document; flag changes.
2. Open GSD phase **B1** (models + geometry) via `/gsd-plan-phase`.
3. After B1 lands, iterate through B2 → B5 as defined in §11.
