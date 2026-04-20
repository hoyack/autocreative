# Phase 18: Brand Kit System - Context

**Gathered:** 2026-04-20
**Status:** Ready for planning
**Source:** HANDOFF.md §8 — verbatim spec captured at /home/hoyack/work/autocreative/HANDOFF.md

<domain>
## Phase Boundary

**What this phase delivers:**

1. A new `flyer_generator/brand_kit/` subsystem that:
   - Scrapes a website (Playwright primary, httpx + BeautifulSoup fallback) into a structured, untracked `BrandKit` stored under `.brand-kits/<slug>/`.
   - Applies a `BrandKit` to any `TemplateSchema` from `flyer_generator/brochure/schema_renderer/`, swapping palette + typography + logo, and optionally scaling typography sizes up.
   - Validates contrast (WCAG AA) across every text region's measured background and auto-remediates failures by swapping to the opposite neutral from the kit's palette.
   - Audits rendered output for whitespace density per panel, contrast compliance per text region, and content-budget fill per resolved content key.
   - Runs an iterate loop (fix → re-render → re-audit) up to 3 cycles when audits find issues.

2. A `python -m flyer_generator.brand_kit` CLI (subcommands: `fetch`, `list`, `show`) for creating/inspecting kits.

3. Integration with the existing `python -m flyer_generator.brochure.schema_renderer` CLI via `--brand-kit <slug>` so one command produces a brand-verbatim brochure.

4. A typography uplift pass across the existing 13 templates to fix the documented "fonts read small" issue (HANDOFF.md §7), separately from runtime `size_multiplier`.

**What this phase does NOT deliver (deferred):**

- LLM/ComfyUI-driven texture generation (see HANDOFF.md §7 "Texture generation").
- Voice-driven copy rewriting guided by `BrandVoice.example_phrases` / `banned_words` (capture the model, wire it into existing `text_gen` as a future follow-up).
- Full PDF downstream integration — the output of `audit_render` is a report + iterated SVG/PNG, not yet a regenerated PDF.
- Text-on-image safe-region detection (HANDOFF.md §5, Phase 5 deferred).
- Template library expansion past 13 templates (HANDOFF.md §5, Phase 3 deferred).

**Integration contract:**

- This phase is **additive** to `flyer_generator/brochure/schema_renderer/`. No existing tests, CLI flags, or public imports from that subsystem may break.
- Renderer core (`render_schema_brochure`) already accepts `accent_override`, `logo_bytes`, `images`, `textures`. The applier produces a modified `TemplateSchema` + optional `logo_bytes` and reuses those same kwargs — no renderer signature changes needed unless forced by the audit remediation path.

</domain>

<decisions>
## Implementation Decisions (locked from HANDOFF.md §8)

### Data model (new `flyer_generator/brand_kit/models.py`)
- `BrandKit` Pydantic v2 model with fields:
  - `name: str` (required)
  - `source_url: str | None`
  - `fetched_at: datetime`
  - `palette: BrandPalette`
  - `typography: BrandTypography`
  - `logos: list[BrandLogo]`
  - `voice: BrandVoice | None`
  - `photography: BrandPhotoHints | None`
  - `source_artifacts: list[str]` — relative paths to screenshot/html/css captured during scrape
  - `size_multiplier: float = 1.0` — applied by `apply_brand_kit` to scale `typography.*_size` in the template
- `BrandPalette`: `primary: ColorUsage`, `secondary: ColorUsage`, `accent: ColorUsage`, `neutral_dark: ColorUsage`, `neutral_light: ColorUsage`, `extras: dict[str, ColorUsage]`. Each `ColorUsage` = `{hex: str, usage_hint: str | None}` (e.g. "primary CTA", "heading").
- `BrandTypography`: `heading_family: str` (CSS stack), `body_family: str` (CSS stack), `size_scale: dict[str, int]` (keys: `hero`, `display`, `heading`, `subheading`, `body`, `caption`), `font_sources: list[str]` (URLs to woff2 if fetchable).
- `BrandLogo`: `path: str` (relative to kit dir), `variant: Literal["primary", "mono_dark", "mono_light", "mark_only"]`, `format: Literal["png", "jpg", "svg"]`, `aspect_ratio: float`.
- `BrandVoice` (optional): `tone: str`, `example_phrases: list[str]`, `banned_words: list[str]`.
- `BrandPhotoHints` (optional): `preferred_style_preset: str | None` (matches existing schema_renderer style presets), `color_grade_notes: str | None`.

### Storage
- **Tracked in repo:** `.brand-kit-template.json` at repo root — a reference shape file kept in lockstep with `BrandKit` Pydantic model.
- **Untracked:** `.brand-kits/<slug>/` with `brand.json`, `logos/*.png`, `source/*.html`, `source/*.css`, `source/screenshot.png`.
- Path configurable via env var `FLYER_BRAND_KITS_DIR` (default `.brand-kits/` relative to CWD).
- **Must** add `.brand-kits/` to `.gitignore`.

### Scraper (`brand_kit/scraper.py`)
- **Primary path:** `playwright` async, headless Chromium.
  - Navigate → wait for network-idle.
  - Screenshot to `source/screenshot.png` at 1920x1080.
  - Dump final rendered HTML to `source/rendered.html`.
  - Walk `@font-face` rules + `<link rel="stylesheet">` for font URLs.
  - Compute `font-family` on `h1`, `h2`, `body` via `page.evaluate`.
  - Candidate logos: `<img>` in header whose `class`/`alt`/`src` matches `/logo/i`; inline `<svg>` with `/logo/i` class.
  - Extract dominant palette via `Pillow.Image.getcolors(maxcolors=4096)` → quantize to top-5 using scikit-learn KMeans OR `colorthief` (decide in research phase; prefer stdlib-adjacent).
- **Fallback path:** `httpx.AsyncClient` + `beautifulsoup4`.
  - Parses `<meta>` (og:site_name, description), `<title>`, first `<h1>`, `<link rel="stylesheet">` hrefs.
  - Download main CSS → regex `@font-face src: url(...)` → font families.
  - Candidate logos: `<img>` with `/logo/i` in `class`/`alt`/`src`.
  - No screenshot-based palette — use CSS `color:` / `background:` declarations on `:root`, `body`, `header`.
- **Output rule:** every field the scraper cannot confidently populate stays `null`. The model MUST accept partially populated kits.

### Contrast (`brand_kit/contrast.py`)
- Depend on `wcag-contrast-ratio>=0.9` (simple, correct) and `coloraide>=4.0` (tone adjustment for remediation).
- Rules:
  - Body text on panel background ≥ 4.5 (AA).
  - Large text (≥ 24 pt) ≥ 3.0.
  - Shape-on-shape: walk the panel tree; every text element computes its effective background by stacking its containing shapes (respecting z-order + opacity).
- **Auto-remediation:** if a text color on a shape-filled bbox fails contrast, swap to the opposite neutral (`neutral_dark` ↔ `neutral_light`) from the palette. If neither neutral passes, log and fall through to unmodified render with a flag in the audit report.
- Return a `ContrastReport(pairs: list[ContrastPair], overall_aa_pass: bool)` where each `ContrastPair` records `{fg, bg, ratio, level: "AA" | "AAA" | "FAIL", remediation: str | None}`.

### Applier (`brand_kit/applier.py`)
- `apply_brand_kit(template: TemplateSchema, kit: BrandKit) -> tuple[TemplateSchema, bytes | None]` — returns a new template (immutable copy via `model_copy(deep=True)`) with:
  - `template.palette` swapped from kit palette (primary → `accent_default`; secondary/neutrals → derived fields; **preserve** existing key shape; validate AA contrast of derived pairs).
  - `template.typography.heading_family` ← `kit.typography.heading_family`; `body_family` ← `kit.typography.body_family`.
  - Every `typography.*_size` integer scaled by `round(value * kit.size_multiplier)`; default `size_multiplier = 1.0` (no-op).
  - Returns `logo_bytes` read from `kit.logos[0]` (primary variant preferred) or `None` if kit has no logo.
- **No mutation** of the passed-in template — always return a fresh copy.

### CLI integration
- `python -m flyer_generator.brand_kit fetch <url> --slug <slug>` writes `.brand-kits/<slug>/`.
- `python -m flyer_generator.brand_kit list` enumerates slugs under `FLYER_BRAND_KITS_DIR`.
- `python -m flyer_generator.brand_kit show <slug>` prints resolved `BrandKit` as JSON.
- `python -m flyer_generator.brochure.schema_renderer --brand-kit <slug>` plumbs kit through: loads kit → applies to template → hands `logo_bytes` + modified template to renderer. Mutually composable with existing flags (`--prompt`, `--brief-json`, `--color-accent`, `--generate-images`, etc.).
- `--brand-kit` **overrides** `--color-accent` when both are supplied (kit palette wins; log a warning).

### Audit (`brand_kit/audit.py`)
- `audit_render(content, template, rendered_svg_or_png) -> AuditReport` returns:
  - `whitespace: dict[PanelId, float]` — per-panel pixel-density ratio (Pillow histogram + thresholding).
  - `contrast: ContrastReport` — from `contrast.py`.
  - `density: dict[str, float]` — per content_key resolved fill % of char budget.
  - `issues: list[AuditIssue]` with severity + suggested remediation.
- Orchestrator loop: `fix (text regen / contrast swap) → re-render → re-audit` up to 3 cycles; short-circuit on clean pass.

### Dependencies to add (`pyproject.toml`)
- `playwright>=1.50` — dev-optional group, pure-Python wheels not enough; CI will need `playwright install chromium`.
- `beautifulsoup4>=4.13`.
- `wcag-contrast-ratio>=0.9`.
- `coloraide>=4.0`.
- Optionally `colorthief` for palette quantization (decide in research).

### Typography uplift
- Separate from runtime `size_multiplier`: bump baseline sizes in the 13 templates so default-density content reads comfortably at print scale. Touch `typography.body_size`, `typography.bullet_size`, potentially `typography.lead_paragraph_size` where present.
- **Guardrail:** the existing 78-cell schema_renderer gallery tests must still render without text overflow (fit-retry may trigger, but no hard clipping).

### Claude's Discretion
- Exact palette quantization algorithm (ColorThief vs. KMeans vs. `Pillow.Image.quantize()`).
- Exact whitespace density thresholds (calibrate against the shrubnet-v9 baseline).
- `size_multiplier` default calibration (likely `1.15` — tune against gallery).
- Test fixture design (mock HTML for scraper; synthetic SVG for audit).
- Internal module layout beyond the listed files.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase spec (source of truth for Phase 18)
- `HANDOFF.md` §8 (Brand Kit system) — verbatim user intent.
- `HANDOFF.md` §7 — open issues including the typography uplift.

### Existing schema_renderer subsystem (what Phase 18 plugs into)
- `flyer_generator/brochure/schema_renderer/schema_model.py` — `TemplateSchema`, `palette`, `typography`, element types.
- `flyer_generator/brochure/schema_renderer/content_model.py` — `BrochureContent`, `BrochureBrief`, `resolve_key`.
- `flyer_generator/brochure/schema_renderer/renderer.py` — `render_schema_brochure(template, content, *, accent_override, logo_bytes, images, textures)`.
- `flyer_generator/brochure/schema_renderer/shapes.py` — fill resolution (for contrast background computation).
- `flyer_generator/brochure/schema_renderer/text_fit.py` — char budgets (for density audit + size-multiplier guardrails).
- `flyer_generator/brochure/schema_renderer/text_gen.py` — LLM copy generation (audit loop remediation hook).
- `flyer_generator/brochure/schema_renderer/image_gate.py` — vision gate pattern to mirror for async httpx timeouts + retry behaviour.
- `flyer_generator/brochure/schema_renderer/__main__.py` — CLI for `--brand-kit` integration point.
- `flyer_generator/brochure/schemas/*.json` — 13 templates to typography-uplift and test against.

### Sample content + gallery fixtures
- `docs/brochure/sample-content/{law_firm,kids_coding_camp,tech_startup,nonprofit}.json`.
- Gallery test: `tests/brochure/schema_renderer/test_gallery.py` (must stay green).
- One-shot integration inputs still on disk: `/tmp/shrubnet-brief.json`, `/tmp/shrubnet-e2e/logo.png`.

### Project / stack
- `CLAUDE.md` — project-wide rules (Python 3.11+, uv, Pydantic v2, httpx, structlog, ruff, pyright, no Node deps).
- `pyproject.toml` — where new deps land.

</canonical_refs>

<specifics>
## Specific Ideas

- **Deterministic fallback scraper is not a nice-to-have.** It is the test harness backbone — unit tests mock HTML and run through the BS4 path, which means all logic that doesn't strictly require a headless browser must be reachable there. Browser-only extractions (rendered screenshots, computed styles) get their own thin module that tests skip/mock.
- **Mirror `image_gate` conventions** for any HTTP or async subprocess call: `httpx.AsyncClient(timeout=180.0)`, `retry on transient errors (continue, not break)`, `structlog.bind(trace_id=...)` at orchestration boundary.
- **Palette application must preserve AA contrast for hardcoded text roles.** When swapping `template.palette`, compute contrast of `body_color` against `background_fill_color` for every panel; if swap fails AA, pick the opposite neutral from the kit instead of blindly writing. Log every swap in the audit report.
- **CLI surface compatibility matrix** for `schema_renderer` must be preserved:
  - `--brand-kit` + `--color-accent` → kit wins, log warning.
  - `--brand-kit` + `--logo` → explicit `--logo` wins (user override).
  - `--brand-kit` + `--prompt` → both active; brand voice/example phrases feed into `text_gen` (best effort — if text_gen doesn't support brand voice yet, note in audit, don't crash).
  - `--brand-kit` + `--brief-json` → kit palette + typography layered on top of brief-driven content.
- **Typography uplift is two-track:**
  1. Baseline template sizes in the 13 JSONs (one-time edit, committed).
  2. Runtime `kit.size_multiplier` for brand kits that demand bigger/smaller type.
- **Failure isolation in the scraper:** a failing Playwright launch must fall through to BS4, not abort. Missing logos, failed palette quantization, etc. must keep going and record the gap in `BrandKit.source_artifacts` / null fields.

</specifics>

<deferred>
## Deferred Ideas

- **Voice-driven copy rewriting** — capture `BrandVoice` in the model now, but wiring `text_gen.generate_content_from_prompt` to consume `voice.tone` / `banned_words` / `example_phrases` is a future follow-up (to avoid a breaking change in Phase 18's scope).
- **PDF regeneration in audit loop** — the audit works on SVG/PNG; regenerating the full PDF after every audit cycle is expensive and not in scope. Optional in a later phase.
- **Texture generation via LLM/ComfyUI orchestrator** — `--textures-dir` stays user-fed (HANDOFF.md §7).
- **Template library expansion past 13** — JSON-only work, tracked as "Phase 3 deferred" in HANDOFF.md §5. Not in this phase.
- **Text-on-image safe-region detection** — Phase 5 deferred in HANDOFF §5.
- **`colour-science` / CAM16** — overkill for contrast validation. `wcag-contrast-ratio` + `coloraide` is sufficient.

</deferred>

---

*Phase: 18-brand-kit-system*
*Context gathered: 2026-04-20 via HANDOFF.md §8 express path*
