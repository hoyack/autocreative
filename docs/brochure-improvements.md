# Brochure Generator — Improvements & Handoff

**For a fresh session after `/clear`.** Everything in this doc is actionable today. For full history see `docs/brochure-plan.md` (v1 design), `docs/brochure-v2-plan.md` (v2 generative pipeline), and the ROADMAP.

> **Status (2026-04-18):** all 10 improvement items below are landed across commits `155fa8c` (verify rubric), `1fe5a85` (two-sheet verify), `cc943f9` (verdict on BrochureOutput + CLI), `90c8539` (template typography), `4dec5ef` (font-face defs), `279641f` (fit retry), `8a4e54e` (tuck-flap tagline), `77f63f5` (spot aspect), `898df97` (cover_image_concept), `beb4767` (output linter). Test suite: 445/445 passing. The sections below are kept for historical reference.

---

## 1. Quick orientation (current state)

- **Tests:** 445/445 pass → `python -m pytest tests/ -q` (≈25s)
- **Flyer suite:** 179 tests, untouched throughout brochure work
- **Brochure suite:** 266 tests across `tests/brochure/` (+ `tests/brochure/generative/`)
- **CLI:**
  - v1 pre-filled: `python -m flyer_generator.brochure --brochure-json data.json --output out/`
  - v2 prompt-driven: `python -m flyer_generator.brochure --prompt "…" --audience "…" --output out/`
- **Public API:**
  - `from flyer_generator.brochure import generate_brochure, generate_brochure_from_prompt`
- **Latest smoke outputs:**
  - `/tmp/brochure-v2-phase16b/` — post-phase-16 (N=3 sections)
  - `/tmp/brochure-v2-polish2/` — post-phase-15 (spot-image landing)
- **Working tree:** clean. Latest commit is `0ce72d0 docs(roadmap): mark phase 16 quality tuning complete`.

### What works well now

- End-to-end prompt → outline → text → layout → imagery → compose → verify → PDF
- All 3 inner panels fill even with minimum sections
- Accent rules under every heading (consistent visual anchor)
- Cover title auto-shrinks; no overflow; soft drop shadow
- Fold lines hidden by default (v1 print bug fixed)
- Back-panel `kind` maps to readable heading (Visit Us / About / Find Us / Contact)
- Spot images composite on matching panels (inner + tuck flap)
- XML-escaped throughout; all templates emit well-formed SVG
- Seed-nudge on verify retry actually shifts shape positions

---

## 2. Improvements (ranked by impact)

### HIGH — Template typography not wired to composer ✅ `90c8539` + `4dec5ef`

**Problem:** `LayoutTemplate` declares `heading_font_family`, `body_font_family`, `cover_title_font_size`, `heading_font_size`, `body_font_size`, `body_line_height`, `body_max_chars_per_line`. But the composer still uses module-level constants (`_FONT_TITLE`, `_FONT_BODY`, `_HEADING_FONT_SIZE`, etc.).

**Impact:** `editorial` (serif, conservative type) vs `playful` (casual, bold) vs `minimalist` (clean sans) all look *identical* because only shapes differ. The 6 templates collapse to ~3 visual signatures.

**Files:**
- `flyer_generator/brochure/stages/composer.py` — all text-rendering helpers (`_render_cover_text`, `_render_section_text`, `_render_section_text_below_image`, `_render_back_panel_text`, overflow renderer)
- `flyer_generator/brochure/templates/__init__.py` — source of typography values

**Approach:**
1. Pass `template: LayoutTemplate | None` through to every text helper (currently already plumbed at the top-level `compose_brochure_svgs`, needs to flow down)
2. Replace module constants with `template.heading_font_size`, etc. Fall back to current constants when `template is None` (v1 compatibility)
3. Test: render all 6 templates, parse each SVG for `font-family` attribute on heading text, assert they differ per template

**Gotcha:** cairosvg only rasterises fonts installed on the system. Declaring `'Playfair Display'` in SVG without Playfair installed silently falls back to Cairo's default sans. To actually see serif vs sans visually, either:
- (a) Bundle a handful of free fonts into `assets/fonts/` and load via `@font-face` data-URI in the SVG `<defs>`, or
- (b) Document the limitation and pick system-available generic families (`serif` / `sans-serif` / `monospace`) in templates

Option (a) gives real typography differentiation. Option (b) is cheaper but cosmetic impact is smaller.

**Effort:** ~2–3 hours for option (b) + tests. Option (a) is a day.

---

### HIGH — Verification loop is confidence-driven, not rubric-driven ✅ `155fa8c`

**Problem:** `verify_brochure` in `flyer_generator/brochure/generative/verify.py` uses `VisionEvaluator.evaluate_cover` which returns a `VisionVerdict`. The score is just `verdict.confidence * 100` — it does NOT actually run the 5-dimension rubric prompt the design specified. The `dimension_scores` dict fills all dimensions with the same confidence value.

**Impact:** Weak gating — the verifier can't really tell WHICH dimension is bad, so `weakest_stage` is a guess between `compose` (confidence low but approved) or `text` (rejected). Regen loop ends up bouncing compose seeds without addressing real issues.

**Files:**
- `flyer_generator/brochure/generative/verify.py` — `verify_brochure`

**Approach:**
1. Make `verify_brochure` do TWO calls: (a) vision evaluate cover for raw quality approval, (b) text-only LLM call with the rubric prompt and the outline summary → parse 5 dim_scores from JSON
2. OR: use `VisionEvaluator` with a system prompt that explicitly requests rubric JSON back, parse that out of `raw_response`. The current `evaluate_cover` path throws the rubric JSON into `raw_response` already — just add a second parse step in `verify_brochure`
3. Keep the existing confidence-only path as a fallback for when JSON parse fails

**Test:** mock the vision/text responses to return a known rubric JSON; assert `dimension_scores` reflect the JSON values, not uniform.

**Effort:** 1–2 hours + tests.

---

### MEDIUM — Tuck-flap dead zone when N=3 sections ✅ `8a4e54e`

**Problem:** When the outline produces 3 content sections + 1 CTA, inner panels fill but tuck flap is gradient + shapes only (no text). Phase-16 screenshots show this as a wide empty panel on the outside sheet right.

**Impact:** Wasted panel real estate. A well-designed tri-fold usually has something on every panel.

**Approach options (pick one):**
1. **Echo the back-cover CTA content on tuck flap** (compressed) — user sees the call-to-action twice, reinforcing it
2. **Render a QR code placeholder + URL** — good for CTAs that are URLs
3. **Render the org name + short tagline** taken from `outline.cta_intent`
4. **Add a "Highlights" bullet list** pulled from the first 2 words of each inner-panel heading

Option 3 is the lowest-friction win.

**Files:**
- `flyer_generator/brochure/stages/composer.py` — tuck-flap branch of `compose_brochure_svgs`

**Test:** render a N=3 brochure, assert tuck flap area contains the org name or a non-empty text element.

**Effort:** 1 hour.

---

### MEDIUM — Fit optimizer has no inner loop ✅ `279641f`

**Problem:** `optimize_fit` in `flyer_generator/brochure/generative/fit.py` does ONE rewrite per section and accepts whatever comes back, even if still off-target. Comment `# Single rewrite per section (no inner loop); verification catches persistent misfit` is intentional for simplicity but leaves real misfits to the verify stage which, per the second HIGH item above, doesn't actually diagnose misfit dimensions.

**Impact:** Occasional text overflow or underflow ships. Cascades into lower verify scores the user can't interpret.

**Approach:**
1. Add `max_rewrites: int = 2` to `optimize_fit`
2. After each rewrite, re-check `needs_rewrite`; if still needs rewrite and have iterations left, loop
3. Add a `_char_target` tightening pressure (shrink target 10% per iteration) so the LLM tries harder on retry

**Test:** mock text_client to return sequentially-shrinking bodies; assert `optimize_fit` stops when target is hit, or caps at `max_rewrites`.

**Effort:** 1 hour + tests.

---

### MEDIUM — Output validator / linter absent ✅ `beb4767`

**Problem:** There's no post-render quality check. Verification runs on the rasterized PNG but only for tone/legibility judgment, not mechanical correctness.

**Suggested linter (new module):** `flyer_generator/brochure/generative/lint.py`

Checks to run on rendered PNGs + SVG source:
1. **Empty-quadrant detector** — PIL: sample each panel's safe-rect as a tile; if >95% pixels are within 5 units of the dominant color, flag "empty panel"
2. **Text clipping detector** — parse SVG for text elements; compute bounding boxes; assert each lies inside its panel's safe rect
3. **XML validity** — already implicit but could be an explicit `ET.fromstring` gate
4. **Crop mark presence** — count crop marks in the PNG via edge detection or just verify SVG has them

Attach results to `BrochureOutput.verification` as a new `lint_report: dict[str, bool | str]` field (add to `BrochureOutput`).

**Effort:** 3–4 hours. High value because the output becomes "validated" in a mechanical sense the user explicitly asked for.

---

### MEDIUM — Hero concept derivation is weak ✅ `898df97`

**Problem:** `_assemble_brochure_input` in `flyer_generator/brochure/generative/pipeline.py` sets `hero_concept = cover_section.body_brief or prompt.prompt[:120]`. The outline's cover section `body_brief` is a 1-sentence direction for a copywriter (e.g. "welcoming yoga studio designed for new moms"), not an image concept. That gets fed to ComfyCloud verbatim — the model doesn't know it's a composition direction, not a visual hint.

**Impact:** Cover hero images drift because the prompt text is about *writing style*, not about *what to render*.

**Approach:** Add a stage 1.5 (or extend outline prompt) to produce a dedicated `cover_image_concept` field on BrochureOutline. Or do a lightweight LLM call to rewrite `cover_section.body_brief` into a concrete image concept before feeding to Comfy.

**Effort:** 1–2 hours.

---

### LOW — Templates use non-system fonts ✅ `4dec5ef` (infrastructure; drop woff2 files into `flyer_generator/assets/fonts/` to enable)

**Problem:** Templates reference `'Playfair Display'`, `'Inter'`, `'Fredoka'`, `'Source Serif Pro'`, `'Avenir Next'` — none of which are guaranteed on the cairosvg renderer's system. Cairo silently falls back to default sans.

**Impact:** Templates look more similar than their declarations suggest. Related to the HIGH template-typography item above.

**Approach:** Bundle 3–4 open-licensed fonts (Inter, Source Serif Pro, Fredoka, Playfair Display) in `flyer_generator/assets/fonts/` and inline them via `@font-face` with `url(data:font/woff2;base64,…)` in the SVG `<defs>`. CairoSVG supports embedded font faces.

**Effort:** 3 hours (font download, base64 embedding helper, template mapping).

---

### LOW — Spot images not scaled intelligently ✅ `77f63f5`

**Problem:** `_render_spot_image` sets image height to 40% of the panel's safe_rect height regardless of the image's aspect ratio. Cairo crops via `preserveAspectRatio="xMidYMid slice"` which is correct, but the image's interesting subject may be cropped out if the Comfy spot happens to be portrait-oriented.

**Impact:** Hero-style spots that depend on framing will be off. Mostly visible when real ComfyCloud outputs replace test placeholders.

**Approach:** Either (a) constrain spot workflow to landscape aspect ratio (already does via `turbo_landscape`), or (b) add an image-center-of-mass detection via Pillow so the rendered crop picks the subject.

**Effort:** 2 hours. Lower priority because (a) already mostly covers it.

---

### LOW — Verification only evaluates outside sheet ✅ `1fe5a85`

**Problem:** `verify_brochure(outside_png, inside_png, …)` receives both but only passes `outside_png_bytes` into `evaluate_cover`. The inside sheet is never visually judged.

**Approach:** Either call vision twice (once per sheet) and average, or use an Anthropic multi-image message that sends both + outline summary in one call.

**Effort:** 1 hour.

---

### LOW — No CLI output for verification results ✅ `cc943f9`

**Problem:** The CLI prints `trace_id` and `attempts_used` but does not surface the final verification verdict. Users have to introspect the returned `BrochureOutput` object.

**Approach:** When `verify_threshold > 0`, print a one-line "Verification: score=XX passed" or "Verification: score=XX below threshold, weakest=layout — accepted anyway" after `--prompt` CLI runs.

**Effort:** 30 min.

---

## 3. Testing quick-start

```bash
# Full suite
python -m pytest tests/ -q

# Brochure only (faster)
python -m pytest tests/brochure/ -q

# Specific phase (e.g. phase 16 changes)
python -m pytest tests/brochure/test_phase16.py tests/brochure/test_polish.py -v

# Offline smoke — no Comfy/Anthropic credentials needed
python <<'PYEOF'
# see /tmp/brochure-v2-phase16b rendering command in commit fa59ac9 body
PYEOF
```

---

## 4. Architectural notes (avoid surprises)

- **Composer signature:** `compose_brochure_svgs(brochure, layout, hero, layout_choice=None, template=None, spot_images=None, *, render_guides=False)`. All new args are kwargs-only friendly; v1 callers unaffected.
- **Rasterizer is dimension-agnostic:** `Rasterizer(width=3376, height=2626)` for brochure; `Rasterizer()` defaults to 1080×1920 for flyer.
- **Ollama config is the primary LLM backend path.** `FLYER_VISION_PROVIDER=ollama` + `FLYER_OLLAMA_*` env vars drive both text + vision. Anthropic backend is the other branch, picked by the same env var.
- **Templates' `shape_mix` uses string recipes** like `"accent_bar(placement=top, thickness=4)"`. Parsed by `flyer_generator/brochure/shapes/parse_shape_recipe`. Coerces numeric strings to int.
- **Seed derivation for shapes:** `seed_base = hash(brochure.title) & 0xFFFF`. Verify-loop nudges title with U+200B on retry to change this seed.
- **Back-panel kind mapping:** `_BACK_PANEL_HEADINGS` in composer.py — kind ∈ {cta, bio, map_stub, contact} → headings {Visit Us, About, Find Us, Contact}. Fallback "Details".
- **Section assignment (inner-first):**
  - N=2 → inner_left, _, inner_right
  - N=3 → inner_left, inner_center, inner_right (tuck flap empty)
  - N=4 → inner_left/center/right + tuck flap = sections[3]
  - N=5 → same + sections[4] overflow on inner_right
- **Pipeline structure:** `generate_brochure_from_prompt` calls outline → text → layout → fit → assemble-BrochureInput → imagery → render-and-verify. The `_assemble_brochure_input` step is where outline sections map into the BrochureInput schema.

---

## 5. Where to focus first (my recommendation)

In order of ROI for "professional, clean, validated":

1. **Fix verification to actually use the rubric** (HIGH #2) — unlocks meaningful regen, gives users a real score
2. **Wire template typography to composer** (HIGH #1, option b first — use system-generic families, skip bundled fonts for now) — templates stop looking identical
3. **Add output linter** (MEDIUM #5) — delivers the "validated" part of the user request in a measurable way
4. **Tuck-flap echo for N=3** (MEDIUM #3) — easy visual density win
5. **Fit optimizer inner loop** (MEDIUM #4) — defensive, low-risk improvement

Items 1+2 together are roughly 4 hours and would deliver the majority of the remaining "high quality, professional, clean" impact. Item 3 is another 3–4 hours and closes the "validated" loop.

---

## 6. Commit reference for context

Relevant commits for browsing:

- `fa59ac9 feat(16): quality tuning` — section distribution + accent rules + title fit + verify teeth
- `d2cff92 feat(15): polish` — shape/text collision + spot compositing
- `d5d5d1c feat(14): end-to-end prompt-driven pipeline`
- `7aae3e0 feat(13): imagery + verification`
- `925dd70 feat(12): vector shapes + composer v2` — v1 bug fixes here (fold lines, kind leak)
- `6d95e82 feat(11): templates + layout + fit`
- `2e9a470 feat(10): LLM clients + outline + text`
- `4cf36da docs: brochure-v2 design`

Phase 5–9 commits cover the v1 substrate (models, geometry, workflow, composition, PDF, CLI).

---

## 7. When you come back in a fresh session

1. `git log --oneline | head -20` — confirm tree state
2. `python -m pytest tests/ -q` — confirm 400/400
3. Pick an item from §2; read the relevant source file listed under **Files**
4. Write tests FIRST (test-driven), then implement, then render + visual diff
5. Commit atomically: one feature per commit, descriptive message

The `docs/brochure-v2-plan.md` design doc is still current — treat it as the spec. Any new behavior beyond what's listed there should update that doc alongside the code change.
