# Brochure Generator — Improvements v2 & Handoff

**For a fresh session after `/clear`.** This doc is the full state-of-the-world after two full improvement passes (v1 + v2). For earlier history see `docs/brochure-improvements.md` (v1 pass, now all 10 items landed) and `docs/brochure-v2-plan.md` (original generative pipeline design).

---

## 1. Quick orientation (current state)

- **Tests:** 445/445 pass → `python -m pytest tests/ -q` (~25s)
- **Flyer suite:** 179 tests, untouched throughout brochure work
- **Brochure suite:** 266 tests across `tests/brochure/` and `tests/brochure/generative/`
- **Latest commit:** `83f3c8a fix(composer): thicker crop marks for rasterised print output`
- **Working tree:** clean.
- **CLI:**
  - v1 pre-filled: `python -m flyer_generator.brochure --brochure-json data.json --output out/`
  - v2 prompt-driven: `python -m flyer_generator.brochure --prompt "…" --audience "…" --output out/`
- **Public API:** `from flyer_generator.brochure import generate_brochure, generate_brochure_from_prompt`
- **Credentials in `.env`:** FLYER_ANTHROPIC_API_KEY, FLYER_COMFYCLOUD_API_KEY, FLYER_OLLAMA_API_KEY all live. Vision provider is `ollama` with gemma4:31b-cloud.
- **Latest live smoke outputs:** `/tmp/brochure-adversarial/` — battery 5 outputs + `run_test.py` harness.

### Commits added in this improvement session (chronological)

Everything below landed on `master` as atomic commits in this session:

```
155fa8c feat(verify): parse rubric JSON from vision raw_response
1fe5a85 feat(verify): evaluate both outside and inside sheets
cc943f9 fix(brochure): attach VerificationVerdict to BrochureOutput + CLI print
90c8539 feat(composer): thread LayoutTemplate typography to text renderers
4dec5ef feat(fonts): inline @font-face data-URIs from bundled woff2 files
279641f feat(fit): inner retry loop with target tightening
8a4e54e feat(composer): tuck-flap tagline when fewer than 4 sections
77f63f5 feat(composer): aspect-aware crop for portrait spot images
898df97 feat(outline): add cover_image_concept for dedicated hero prompts
beb4767 feat(lint): mechanical output validator + BrochureOutput integration
a1f3178 docs(brochure): mark all 10 improvements complete + add phase 17 to roadmap
cea867d fix(brochure): graceful fallback when hero gen fails + fill empty panels + lint counter
2c762b7 fix(brochure): eliminate remaining blank-panel / placeholder-text defects
3c550cf feat(composer): center placeholder cover title + default decorative shapes
83f3c8a fix(composer): thicker crop marks for rasterised print output
```

First 11 closed `docs/brochure-improvements.md`; last 4 came from running the adversarial battery loop.

---

## 2. What the system does now (works-as-designed)

### Pipeline stages (prompt-driven)
1. **Outline** (LLM) — produces `BrochureOutline` with sections, tone, cta_intent, suggested_preset, suggested_accent, **org_name**, and **cover_image_concept** (new v2).
2. **Section text** (LLM) — generates body prose per section.
3. **Layout selection** (LLM) — picks one of 6 `LayoutTemplate` presets.
4. **Fit optimization** — retries body rewrites up to `max_rewrites=2` to hit a tighter 30% capacity target.
5. **Imagery** (ComfyCloud + vision) — hero via `BrochureCoverVisionEvaluator`, spot images (no vision gate). **New: pipeline now catches `MaxAttemptsExceededError` and falls back to `shapes_only` placeholder cover.**
6. **Compose** (SVG) — two sheets with typography threaded from `LayoutTemplate`, `@font-face` defs from `flyer_generator/assets/fonts/` (graceful no-op when empty), aspect-aware spot image crops, fallback taglines for empty inner panels.
7. **Verify** (vision, both sheets) — real 5-dim rubric parsed from vision `raw_response`; scores averaged outside + inside. Verdict attached to `BrochureOutput.verification`.
8. **Lint** — mechanical XML/crop-mark/empty-panel/text-clip checks. Attached to `BrochureOutput.lint_report` with `_summary` field like `"14/16 checks passed"`.

### What reads well in rendered output
- Template-differentiated typography (serif EDITORIAL, display PLAYFUL, sans MINIMALIST)
- Org name on tuck flap and empty inner panels (N<3 case)
- Cover title in accent colour with anchor bar + footer bar when no hero image
- Default decorative shapes (`accent_bar` + `corner_wedge`) on placeholder covers
- Readable spot images when Comfy succeeds (`tech-startup` in battery 5 had clean team photo + workstation shot)
- Crop marks visible at 72px/6px stroke (recently bumped from 36/3)

---

## 3. Current brochure quality — last battery numbers

Battery 5 (three prompts, live API, verify_threshold=70):

| Prompt | Built-in verify | Lint | Adv outside | Adv inside |
|--|--|--|--|--|
| Law firm (editorial) | 49 (weakest=compose) | 14/16 | 20 | 35 |
| Kids coding camp (playful) | 38 (weakest=compose) | 13/16 | 15 | 30 |
| Tech startup (minimalist) | 50 (weakest=layout) | 14/16 | 30 | 40 |

Dimension breakdowns (law firm, representative):
`{'visual_balance': 25, 'print_readiness': 30, 'content_fit': 72, 'text_legibility': 85, 'layout_coherence': 35}`

Adversarial vision is very harsh — most "defects" it finds are subjective layout balance complaints on placeholder covers (no hero image). When a real hero/spot image lands, scores rise materially.

---

## 4. Known unresolved issues

### HIGH priority
**ComfyCloud Turbo model (`turbo_landscape`) produces text-overlay artifacts on certain prompts** (law, kids-camp). The `BrochureCoverVisionEvaluator`'s "no graphic overlays" rule correctly rejects, but we run out of `max_bg_attempts=3` and fall back to placeholder cover. Only ~1/3 of prompts currently get real hero imagery.

**Addressing this is what §5 is about** — wire alternate ComfyUI workflows and benchmark which model has lowest text-artifact rate.

### MEDIUM
- **Font bundling**: `flyer_generator/assets/fonts/` is empty. Drop subsetted `Inter.woff2`, `Playfair_Display.woff2`, `Fredoka.woff2`, `Source_Serif_Pro.woff2` into that dir and rendered SVGs immediately get true typography. Infrastructure is committed; just needs binaries + licences. See `flyer_generator/assets/fonts/README.md`.
- **Adversarial JSON parsing is brittle**: our `/tmp/brochure-adversarial/run_test.py` packs `approved`/`confidence`/`score`/`defects` into the adversarial system prompt, because `VisionEvaluator._parse_and_validate` requires `approved`+`confidence` before returning. If we ever want a lower-level adversarial path, bypass `evaluate_cover` and hit `_call_anthropic` / `_call_ollama` directly.
- **`vision_timeout_seconds` default is 60s**; cloud models take 30-90s per call. The test harness uses `Settings(vision_timeout_seconds=300)` as an override. Consider bumping default to 180-240 in `flyer_generator/config.py:33` so users don't hit silent timeouts on first run.

### LOW
- Tuck-flap tagline renders at the same vertical centre as placeholder cover title — they visually align on the outside sheet which is a design oddity, not a bug.
- Spot image prompts still use `UNIVERSAL_NEGATIVE`; no vision gate on spots, so occasional text artifacts ship on inner panels.

---

## 5. Next step: wire additional ComfyUI workflows

The user has placed **5 new model workflows** in `docs/workflows-pending/`:

| File | Model |
|--|--|
| `image_longcat_text_to_image.json` | LongCat |
| `image_ernie_image.json` | Baidu ERNIE Image |
| `image_ernie_image_turbo.json` | Baidu ERNIE Image Turbo |
| `image_flux2.json` | Flux.2 (Black Forest Labs) |
| `image_qwen_Image_2512.json` | Alibaba Qwen Image 2512 |

These are raw ComfyUI graph exports — they are **not yet in the `_flyer_meta` format** the loader expects. The currently-shipped workflow template (`flyer_generator/workflows/turbo_landscape.json`) prepends a `_flyer_meta` block like:

```json
{
  "_flyer_meta": {
    "name": "turbo_landscape",
    "description": "Z-Image Turbo, 8 steps, cfg=1, 1472x832 landscape",
    "latent_dimensions": [1472, 832],
    "injection_points": {
      "positive_prompt": "57:27",
      "negative_prompt": "57:34",
      "seed": "57:3"
    }
  },
  ...rest of the Comfy graph...
}
```

### Per-workflow wiring plan

For each pending file, do the following (one commit per model):

1. **Identify injection points** by reading the graph:
   - `positive_prompt` — the `CLIPTextEncode` / `CLIPTextEncodeFlux` / equivalent node that feeds the positive prompt
   - `negative_prompt` — same pattern; **may not exist** for models with CFG=1 (Flux2 often omits negative). When absent, drop the key from `injection_points` and update `llm_client` / `prompt_builder` to tolerate missing neg.
   - `seed` — the sampler or seed node
2. **Pick `latent_dimensions`** suitable for a brochure cover hero — landscape 16:9-ish, ~1472×832 or the nearest model-native size. Flux2 wants 1024×1024 or 16:9 equivalents; Qwen Image typically 1024-based.
3. **Wrap in `_flyer_meta`** and move to `flyer_generator/workflows/<name>.json`. Use consistent naming: `flux2_landscape.json`, `qwen_landscape.json`, `ernie_landscape.json`, `ernie_turbo_landscape.json`, `longcat_landscape.json`.
4. **Validate** the new workflow loads:
   ```python
   from flyer_generator.workflow_loader import load_workflow
   load_workflow("flux2_landscape")
   ```
5. **Small smoke test**: fire a one-shot spot-image workflow against it through `ComfyClient.generate(wf, attempt=1)` to confirm the Comfy server accepts the graph.
6. **Support wiring for `--workflow` CLI flag** already exists (see `--max-attempts` in `flyer_generator/brochure/__main__.py`); add a new typer option `--workflow <name>` that overrides `settings.workflow` for the brochure path. Same for `generate_brochure_from_prompt` — add `workflow_name` kwarg that propagates to `generate_imagery`.

### Post-wiring: run the adversarial benchmark battery

Once all 5 new workflows load, run the existing harness once per workflow against the same 3 canonical prompts. The harness to extend: `/tmp/brochure-adversarial/run_test.py`.

Enhancements needed:
- Accept `workflow_name` per prompt (loop prompts × workflows = 15 runs)
- Write per-workflow summary.json so runs are comparable
- Aggregate: mean built-in score, mean adversarial score, hero-success rate, avg gen time, text-artifact reject count per workflow

Expected output: a scorecard like
```
workflow            hero_ok  avg_built_in  avg_adv_out  avg_adv_in  avg_gen_s  rejects
turbo_landscape     1/3      46            22           35          400        6.3
flux2_landscape     ?        ?             ?            ?           ?          ?
qwen_landscape      ?        ?             ?            ?           ?          ?
ernie_landscape     ?        ?             ?            ?           ?          ?
ernie_turbo         ?        ?             ?            ?           ?          ?
longcat             ?        ?             ?            ?           ?          ?
```

Best-performing workflow by prompt category becomes the new default. Likely outcome: we'll keep `turbo_landscape` as the fast fallback and promote one of Flux2/Qwen/Ernie for quality default based on actual numbers.

### Budget & time estimate
- Wiring 5 workflows: ~2-4 hours including validation (most time spent identifying correct injection node IDs + testing)
- Full benchmark battery (5 × 3 = 15 prompt runs, ~5-10min each): ~1-2.5 hours of wall time, mostly unattended
- Analysis + picking winner + making it the default: ~1 hour
- Total: roughly half a day of focused work + API cost (~$5-15 in compute)

---

## 6. Next step (optional, after §5): productise

If Flux2 or similar lands significantly better than Turbo:
- Remove the `MaxAttemptsExceededError` fallback from `pipeline.py:212-220` (since the better model won't need it) — or keep it as defence-in-depth
- Loosen `BROCHURE_COVER_SYSTEM_PROMPT` (`flyer_generator/brochure/stages/vision.py`) since better model doesn't produce text artifacts
- Remove the default decorative shapes on placeholder covers (still useful but no longer load-bearing)

If no model clearly wins:
- Add a `workflow: Literal[...]` field to `LayoutChoice` so the LLM picks the best workflow per prompt category
- Outline prompt gets an extra field suggesting which workflow fits the tone

---

## 7. Where to focus first (recommendation)

1. **Wire `flux2_landscape` first** — likely highest quality based on public benchmarks
2. **Smoke test** with one prompt, visually inspect result
3. **If clean**, wire the remaining 4 without visual-check bottleneck
4. **Run benchmark battery** in the background; review scorecard when done
5. **Update `.env` or `Settings`** with the winning workflow as default

---

## 8. Files to modify (cheat sheet)

### Adding a new workflow
- **Edit:** `flyer_generator/workflows/<name>.json` (new file; copy from `docs/workflows-pending/` with `_flyer_meta` prepended)
- **No edit needed to loader** — `workflow_loader.list_workflows()` auto-discovers
- **Test:** `python -c "from flyer_generator.workflow_loader import load_workflow; print(load_workflow('<name>'))"`

### Adding `--workflow` CLI flag
- **Edit:** `flyer_generator/brochure/__main__.py` — add typer.Option, pass through
- **Edit:** `flyer_generator/brochure/generative/pipeline.py` → `generate_brochure_from_prompt(workflow_name: str = "turbo_landscape")`
- **Edit:** `flyer_generator/brochure/generative/imagery.py` → `generate_imagery(..., workflow_name: str = "turbo_landscape")` already takes the param; thread it end-to-end

### Relaxing the hero vision gate (if needed)
- **Edit:** `flyer_generator/brochure/stages/vision.py` — adjust `BROCHURE_COVER_SYSTEM_PROMPT` to allow minor text in non-title areas
- Alternative: lower `Settings.vision_confidence_threshold` from 0.6 to 0.5

### Extending adversarial harness
- **Edit:** `/tmp/brochure-adversarial/run_test.py` — add workflow dimension to the loop; write `/tmp/brochure-adversarial/<workflow>/` per run
- **New:** `/tmp/brochure-adversarial/aggregate.py` — walk all summary.json files + produce the scorecard

---

## 9. Architectural notes (avoid surprises)

- **Composer signature:** `compose_brochure_svgs(brochure, layout, hero_png_bytes, layout_choice=None, template=None, spot_images=None, *, render_guides=False, hero_is_placeholder=False)`. The `hero_is_placeholder` kwarg is set by the pipeline when imagery falls back; it tells the composer to render the dark title + default shapes instead of the invisible white title over a 1×1 transparent PNG.
- **`BrochureOutline.org_name`** is optional. When None, pipeline derives from title. Outline prompt now asks LLM to populate it explicitly.
- **`BrochureOutput.verification` and `.lint_report`** are both optional fields added in this session. Pre-existing callers constructing `BrochureOutput` directly (test fixtures) are unaffected because Pydantic defaults them to None.
- **Seed derivation for shapes:** `seed_base = hash(brochure.title) & 0xFFFF`. Verify-loop nudges title with U+200B on retry.
- **Tuck-flap tagline helper is used for both tuck flap and inner-center** (the N=2 case). Single centered strap with accent rule; no wrapped body.
- **`_render_placeholder_cover` vs `_render_cover_text`**: the composer picks between them via `hero_is_placeholder`. First one renders dark accent-coloured title; second renders white title with drop shadow (for real hero images).

---

## 10. Testing quick-start

```bash
# Full suite
python -m pytest tests/ -q

# Brochure only (faster)
python -m pytest tests/brochure/ -q

# Lint module alone
python -m pytest tests/brochure/generative/test_lint.py -v

# Offline quick compose (no APIs) — exercises all composer branches
python /tmp/brochure-adversarial/quick_compose.py
# → writes /tmp/brochure-adversarial/quick/{law-firm-n3,kids-coding-n2,tech-minimal-n4}/{outside,inside}.{png,svg}

# Live end-to-end battery (costs API credits)
python /tmp/brochure-adversarial/run_test.py
# → writes /tmp/brochure-adversarial/{slug}/{brochure_front.png,brochure_back.png,brochure_print.pdf,report.json}
# → writes /tmp/brochure-adversarial/summary.json

# View rendered output
ls -la /tmp/brochure-adversarial/*/brochure_*.png
```

---

## 11. When you come back in a fresh session

1. `git log --oneline | head -20` — confirm tree state (expect `83f3c8a fix(composer): thicker crop marks...` at top)
2. `python -m pytest tests/ -q` — confirm 445/445
3. `ls docs/workflows-pending/` — confirm 5 JSON files still there
4. Pick `flux2_landscape` or whichever you prefer to wire first; follow §5 steps 1-6
5. One atomic commit per workflow wire-up (`feat(workflows): add <name>`)
6. Extend `/tmp/brochure-adversarial/run_test.py` with workflow loop
7. Run overnight; review scorecard in the morning
8. Update `flyer_generator/config.py` `workflow` default to the winner
9. Update this doc (or write brochure-improvement-v3.md) with battery results + recommendation

The `.planning/ROADMAP.md` entry for Phase 17 is marked complete; add a Phase 18 entry when you start this workflow-benchmarking pass.
