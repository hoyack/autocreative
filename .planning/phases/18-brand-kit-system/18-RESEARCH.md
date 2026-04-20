# Phase 18: Brand Kit System - Research

**Researched:** 2026-04-20
**Domain:** Web scraping + color science + template application + visual audit loop
**Confidence:** HIGH (libraries + APIs) / MEDIUM (whitespace thresholds, palette calibration)

## Summary

Phase 18 adds a brand-kit subsystem that scrapes a website (Playwright primary, httpx+BS4 fallback), materializes an untracked `BrandKit` under `.brand-kits/<slug>/`, applies that kit to any of the 13 existing `TemplateSchema` templates, validates WCAG AA contrast for every text region, auto-remediates by swapping to the opposite neutral, and runs a post-render audit loop (whitespace + contrast + density) up to 3 cycles. It also raises baseline typography sizes across all templates so print-scale body/bullet text reads comfortably.

Every library this phase needs is on PyPI with current, maintained wheels. The biggest external cost is Playwright's bundled Chromium (~175 MB download via `playwright install chromium`), which is a one-time CI step. Every other dep (`beautifulsoup4`, `wcag-contrast-ratio`, `coloraide`, `tinycss2`) is a pure-Python wheel. For palette extraction, **use Pillow's built-in `Image.quantize(colors=5, method=Image.Quantize.MEDIANCUT)` + `getcolors()`** — no new dep required, and `colorthief` is abandoned (2017, Python 2 only).

**Primary recommendation:** ship Playwright + httpx+BS4 scraper in parallel, favor the fallback as the test-harness backbone (BS4 path fully mockable with fixture HTML), gate on Pillow `quantize` for palette, `wcag-contrast-ratio` for pass/fail, and `coloraide` 8.x's `Color.contrast()` + OKLCH `lightness` manipulation for remediation. The audit loop's whitespace metric should be the simplest thing that works: grayscale `Pillow.Image.crop(panel_rect)` → histogram → ratio of pixels within ±8 of the panel background color. Calibrate threshold against the known shrubnet-v9 baseline.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Website scraping (dynamic) | `scraper.py` (Playwright) | `scraper.py` (httpx+BS4 fallback) | Dual-path design: headless browser for rendered pages, pure-HTTP fallback for CI / no-Chromium envs |
| Scrape artifact persistence | `storage.py` | — | Filesystem I/O under `.brand-kits/<slug>/` |
| BrandKit data model | `models.py` (Pydantic v2) | — | Immutable value-object with round-trip to `brand.json` |
| Palette extraction | `scraper.py` (via Pillow quantize) | — | Pure-Python, no new dep |
| Contrast validation | `contrast.py` (wcag-contrast-ratio) | — | Simple ratio math, well-tested lib |
| Contrast remediation | `contrast.py` (coloraide OKLCH) | fallback: swap neutrals | Preserve hue family when possible; fall through to palette neutrals |
| Apply kit → template | `applier.py` | existing `render_schema_brochure` | Pure transform on `TemplateSchema`; renderer already supports `accent_override` + `logo_bytes` |
| Render (unchanged) | `schema_renderer/renderer.py` | — | Phase 18 is additive; renderer signature stable |
| Post-render audit | `audit.py` | Pillow (whitespace) + contrast.py | Rasterized PNG → per-panel metrics + structured issues |
| Iteration orchestrator | `audit.py` (or a thin wrapper in `__main__.py`) | `text_gen.generate_content_from_prompt` for copy regen | 3-cycle loop: fix → re-render → re-audit |
| CLI (`fetch` / `list` / `show`) | `brand_kit/__main__.py` | typer | Mirrors existing `schema_renderer.__main__` patterns |
| CLI plumbing (`--brand-kit`) | `schema_renderer/__main__.py` (extend) | applier | Kit loads → applier returns `(TemplateSchema, logo_bytes)` → existing renderer call |

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Data model (new `flyer_generator/brand_kit/models.py`)**
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
- `BrandPalette`: `primary: ColorUsage`, `secondary: ColorUsage`, `accent: ColorUsage`, `neutral_dark: ColorUsage`, `neutral_light: ColorUsage`, `extras: dict[str, ColorUsage]`. Each `ColorUsage` = `{hex: str, usage_hint: str | None}`.
- `BrandTypography`: `heading_family: str` (CSS stack), `body_family: str` (CSS stack), `size_scale: dict[str, int]` (keys: hero, display, heading, subheading, body, caption), `font_sources: list[str]` (URLs to woff2 if fetchable).
- `BrandLogo`: `path: str` (relative to kit dir), `variant: Literal["primary", "mono_dark", "mono_light", "mark_only"]`, `format: Literal["png", "jpg", "svg"]`, `aspect_ratio: float`.
- `BrandVoice` (optional): `tone: str`, `example_phrases: list[str]`, `banned_words: list[str]`.
- `BrandPhotoHints` (optional): `preferred_style_preset: str | None`, `color_grade_notes: str | None`.

**Storage**
- Tracked: `.brand-kit-template.json` at repo root (reference shape file).
- Untracked: `.brand-kits/<slug>/` with `brand.json`, `logos/*.png`, `source/*.html`, `source/*.css`, `source/screenshot.png`.
- Path configurable via env var `FLYER_BRAND_KITS_DIR` (default `.brand-kits/` relative to CWD).
- Must add `.brand-kits/` to `.gitignore`.

**Scraper**
- Primary: `playwright` async, headless Chromium — navigate, wait-for-network-idle, screenshot 1920×1080, dump rendered HTML, walk `@font-face` + `<link rel="stylesheet">`, compute `font-family` on `h1`/`h2`/`body` via `page.evaluate`, identify logos (`<img>` matching `/logo/i`, inline `<svg>`), extract palette from screenshot.
- Fallback: `httpx.AsyncClient` + `beautifulsoup4` — parses meta/title/h1/`<link rel=stylesheet>`, downloads main CSS, regex/tinycss2 for `@font-face`, logo candidates from `<img>` matching `/logo/i`, no screenshot palette (use CSS `color:`/`background:` on `:root`/`body`/`header`).
- Every field the scraper cannot confidently populate stays `null`. Partially populated kits MUST validate.

**Contrast**
- Depend on `wcag-contrast-ratio>=0.9` (pass/fail) and `coloraide>=4.0` (tone adjustment for remediation).
- AA rules: body ≥ 4.5, large text (≥ 24pt) ≥ 3.0. AAA where declared.
- Shape-on-shape: walk the panel tree; every text element computes its effective background by stacking containing shapes (respecting z-order + opacity).
- Auto-remediation: if a text color on a shape-filled bbox fails contrast, swap to opposite neutral (`neutral_dark` ↔ `neutral_light`) from the palette. If neither passes, log + fall through to unmodified render with a flag in the audit report.
- Return `ContrastReport(pairs: list[ContrastPair], overall_aa_pass: bool)` with per-pair `{fg, bg, ratio, level, remediation}`.

**Applier**
- `apply_brand_kit(template: TemplateSchema, kit: BrandKit) -> tuple[TemplateSchema, bytes | None]`.
- New template (immutable via `model_copy(deep=True)`): palette swapped (primary → `accent_default`; secondary/neutrals → derived; preserve existing key shape; validate AA of derived pairs), `heading_family`/`body_family` replaced, every `typography.*_size` scaled by `round(value * kit.size_multiplier)` (default `1.0`).
- Returns `logo_bytes` from `kit.logos[0]` (primary variant preferred) or `None`.
- No mutation of passed-in template — always fresh copy.

**CLI integration**
- `python -m flyer_generator.brand_kit fetch <url> --slug <slug>` writes `.brand-kits/<slug>/`.
- `python -m flyer_generator.brand_kit list` enumerates slugs under `FLYER_BRAND_KITS_DIR`.
- `python -m flyer_generator.brand_kit show <slug>` prints resolved kit as JSON.
- `python -m flyer_generator.brochure.schema_renderer --brand-kit <slug>` loads kit → applies to template → plumbs `logo_bytes` + modified template to renderer. Composable with `--prompt`, `--brief-json`, `--color-accent`, `--generate-images`, etc.
- `--brand-kit` overrides `--color-accent` (kit wins, log warning).

**Audit**
- `audit_render(content, template, rendered_svg_or_png) -> AuditReport` → `whitespace: dict[PanelId, float]`, `contrast: ContrastReport`, `density: dict[str, float]` (per-content_key resolved fill % of char budget), `issues: list[AuditIssue]`.
- Iterate loop: `fix (text regen / contrast swap) → re-render → re-audit` up to 3 cycles; short-circuit on clean pass.

**Dependencies to add (pyproject.toml)**
- `playwright>=1.50` — CI needs `playwright install chromium`.
- `beautifulsoup4>=4.13`.
- `wcag-contrast-ratio>=0.9`.
- `coloraide>=4.0`.
- Optionally `colorthief` for palette quantization (decide in research — see below).

**Typography uplift**
- Separate from runtime `size_multiplier`: bump baseline sizes in 13 templates so default-density content reads comfortably at print scale. Touch `typography.body_size`, `typography.bullet_size`, optionally `typography.lead_paragraph_size`.
- Guardrail: the existing 78-cell schema_renderer gallery tests MUST still render without hard clipping (fit-retry may trigger, that's fine).

### Claude's Discretion

- Exact palette quantization algorithm (ColorThief vs. KMeans vs. `Pillow.Image.quantize()`).
- Exact whitespace density thresholds (calibrate against the shrubnet-v9 baseline at `/tmp/shrubnet-v9/`).
- `size_multiplier` default calibration (likely `1.15` — tune against gallery).
- Test fixture design (mock HTML for scraper; synthetic SVG for audit).
- Internal module layout beyond the listed files.

### Deferred Ideas (OUT OF SCOPE)

- Voice-driven copy rewriting guided by `BrandVoice.example_phrases` / `banned_words` (model captured, wiring deferred).
- Full PDF downstream integration (`audit_render` outputs SVG/PNG report, not regenerated PDF).
- Text-on-image safe-region detection (HANDOFF.md §5 Phase 5 deferred).
- Template library expansion past 13 templates (HANDOFF §5 Phase 3 deferred).
- Texture generation via LLM/ComfyUI orchestrator (`--textures-dir` stays user-fed).
- `colour-science` / CAM16 — overkill for contrast validation.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

Derived from ROADMAP.md Phase 18 success criteria + HANDOFF.md §8 spec.

| ID | Description | Research Support |
|----|-------------|------------------|
| BK-01 | `BrandKit`, `BrandPalette`, `BrandTypography`, `BrandLogo`, `BrandVoice`, `BrandPhotoHints` Pydantic v2 models round-trip to `brand.json`; partial kits with null fields validate | Pydantic v2 `model_validate_json` + `extra="forbid"` pattern already used repo-wide in `schema_model.py` |
| BK-02 | `fetch_brand_kit(url, slug)` produces `.brand-kits/<slug>/brand.json` + `logos/*` + `source/screenshot.png` via Playwright; falls back to BS4 when Playwright launch fails | Playwright 1.58 async API (§Playwright below); BS4 4.14 + tinycss2 1.5 for fallback |
| BK-03 | `apply_brand_kit(template, kit)` returns fresh `TemplateSchema` + optional `logo_bytes` with palette/typography swapped and sizes scaled by `size_multiplier`; schema remains valid | `TemplateSchema.model_copy(deep=True)` — already used in `renderer.py` line 753 for `accent_override` |
| BK-04 | `python -m flyer_generator.brochure.schema_renderer --brand-kit <slug>` plumbs kit through; mutually composable with `--prompt`, `--logo`, `--color-accent`, `--generate-images`; `--brand-kit` overrides `--color-accent` | typer + existing CLI pattern in `schema_renderer/__main__.py` |
| BK-05 | Contrast module validates every body/heading text region against its background; failing regions auto-remediated via opposite-neutral swap; final `ContrastReport` lists every pair | `wcag-contrast-ratio` 0.9 for AA verdict; `coloraide` 8.x `Color.contrast()` + OKLCH lightness nudge |
| BK-06 | `BrandKitError` hierarchy (`BrandKitScrapeError`, `BrandKitContrastError`, `BrandKitAuditError`) raises with typed context; `.brand-kits/` in `.gitignore`; `.brand-kit-template.json` tracked | Existing typed exception pattern in `flyer_generator/errors.py` |
| BK-07 | `audit_render(content, template, rendered_png) -> AuditReport` produces per-panel whitespace density, contrast violations, per-region content-budget fill; iterate loop regenerates copy / swaps contrast up to 3 cycles | Pillow histogram (§Audit below); existing `text_gen.generate_content_from_prompt` + truncation loop |
| BK-08 | Tests cover: scraper (mocked HTML for BS4, fake Page for Playwright), models round-trip, contrast (known pairs + remediation), applier (palette + typography + logo + size_multiplier), audit (whitespace + contrast + density fixtures), CLI (`fetch`/`list`/`show`), end-to-end smoke (kit → `editorial_classic` → AA-clean output) | pytest-asyncio auto-mode + `unittest.mock.AsyncMock` (existing test pattern in `test_image_gate.py`); respx for any HTTP mocking |
| BK-09 | Inside-panel body/bullet sizes raised in 13 templates; 78-cell gallery still renders without overflow; shrubnet v9 sample renders with kit applied and passes contrast + density audits | Existing `text_fit.fit_to_bbox` already word-boundary truncates (safe); gallery test at `tests/brochure/schema_renderer/test_gallery.py` is the guardrail |
</phase_requirements>

---

## Standard Stack

### Core (new deps)

| Library | Version | Purpose | Why Standard | Confidence |
|---------|---------|---------|--------------|------------|
| `playwright` | `>=1.58` | Headless Chromium for dynamic scraping | [VERIFIED: PyPI] v1.58.0 released 2026-01-30; bundles Chromium 145; wheels for Linux/macOS/Windows (manylinux, universal2, ARM64). Async API is the standard pattern. | HIGH |
| `beautifulsoup4` | `>=4.14` | HTML parsing for BS4 fallback scraper | [VERIFIED: PyPI] v4.14.3 released 2025-11-30; pure-Python `py3-none-any` wheel; `Requires: Python >=3.7.0` | HIGH |
| `tinycss2` | `>=1.5` | CSS parser for `@font-face`, custom props | [VERIFIED: PyPI] v1.5.1 released 2025-11-23; maintained by Kozea (WeasyPrint team, same authors as CairoSVG already in stack); pure-Python | HIGH |
| `wcag-contrast-ratio` | `>=0.9` | WCAG 2.0/2.1 AA/AAA pass/fail | [VERIFIED: PyPI] v0.9 (2015-07-30) — old but correct (math is stable); API takes float tuples in 0.0-1.0 range; ships `passes_AA()`/`passes_AAA()` helpers | HIGH |
| `coloraide` | `>=8.0` | Contrast-preserving tone adjustment | [VERIFIED: PyPI] **v8.8.1 (2026-03-22)** — user spec says `>=4.0` but current is 8.x; `Color.contrast(other, method='wcag21')` built-in; OKLCH space for hue-preserving lightness changes | HIGH |

**Correction to CONTEXT.md:** The locked constraint `coloraide>=4.0` was based on stale info. Current is `8.8.1`. Recommend pinning `coloraide>=8,<9` (follows semver, same API surface).

### Already in stack (reused)

| Library | Version | Purpose |
|---------|---------|---------|
| `httpx` | `>=0.28.1` | Async HTTP for BS4 fallback + font-url download (already installed; mirror `image_gate.py` timeout=180.0 pattern) |
| `pillow` | `>=12.2.0` | Palette extraction via `Image.quantize()`; whitespace histogram in audit (already installed) |
| `pydantic` | `>=2.13.1` | All new models (already installed) |
| `pydantic-settings` | `>=2.13.1` | `FLYER_BRAND_KITS_DIR` env var (already installed) |
| `typer` | `>=0.24.1` | CLI (already installed) |
| `structlog` | `>=25.5.0` | Bound trace_id per fetch (already installed; mirror `image_gate.py`) |
| `respx` | `>=0.22.0` (dev) | Mock `httpx.AsyncClient` calls in BS4 fallback tests (already installed) |

### Deliberately NOT added

| Library | Why Not |
|---------|---------|
| `colorthief` | [VERIFIED: PyPI] Last release 2017-02-09 (v0.2.1), classifiers list Python 2.6/2.7 only — abandoned. Do NOT depend on it. |
| `modern-colorthief` | [VERIFIED: PyPI page fails to load reliably in webfetch, docs indicate Rust-based 100× faster] — requires Rust wheels. Overkill; Pillow quantize is sufficient. |
| `Pylette` | [CITED: PyPI/2.0.1] Offers KMeans + median-cut but adds a full scikit-learn subtree. Unnecessary complexity. |
| `scikit-learn` | [ASSUMED] Would pull scipy/numpy as transitive deps — heavy for a 5-color extraction. |
| `cssutils` | [ASSUMED] Unmaintained for years; tinycss2 is the modern replacement in the Kozea ecosystem. |
| `requests` | Project stack is httpx-first (CLAUDE.md). |
| `colour-science` | Explicitly deferred in CONTEXT.md — overkill for WCAG. |

### Installation

```bash
# Add to pyproject.toml [project] dependencies:
uv add "playwright>=1.58"
uv add "beautifulsoup4>=4.14"
uv add "tinycss2>=1.5"
uv add "wcag-contrast-ratio>=0.9"
uv add "coloraide>=8,<9"

# One-time (CI + local dev): download Chromium binary (~175 MB).
# Use --with-deps on Linux CI to also install system libs.
python -m playwright install chromium
# Or in CI (Ubuntu):
python -m playwright install --with-deps chromium
```

**Version verification (performed 2026-04-20):**
```
playwright 1.58.0           (2026-01-30)
beautifulsoup4 4.14.3       (2025-11-30)
tinycss2 1.5.1              (2025-11-23)
wcag-contrast-ratio 0.9     (2015-07-30)
coloraide 8.8.1             (2026-03-22)
```

---

## Architecture Patterns

### System Architecture Diagram

```
                   +--------------------+
                   |   CLI entry point  |
                   |  brand_kit/__main__|
                   +----------+---------+
                              |
              +---------------+----------------+
              | fetch           list/show     |
              v                                v
     +--------+---------+            +---------+--------+
     |   scraper.py     |            |   storage.py     |
     |  (async)         |            |  read/write      |
     |                  |            |  brand.json      |
     |  +---------+     |            +------------------+
     |  |Playwright|---->  source/screenshot.png
     |  |  path    |     |         source/rendered.html
     |  |(primary) |     |         source/*.css
     |  +----+----+     |         logos/*.png
     |       |fail?     |
     |       v          |
     |  +---------+     |
     |  |httpx+BS4|     |
     |  |   path  |     |
     |  |(fallback)|    |
     |  +----+----+     |
     +------+-----------+
            |
            v
      +-----+------+   palette extract: Pillow Image.quantize(5, MEDIANCUT)
      |  BrandKit  |   typography: tinycss2 + page.evaluate
      |  Pydantic  |   logos: <img>/logo/i regex + inline <svg>
      |   model    |
      +-----+------+
            |
            +---------------write to----> .brand-kits/<slug>/brand.json
            |
            v
    ===========================================================
    |          APPLY + RENDER (orchestrated by                |
    |          schema_renderer/__main__.py --brand-kit)       |
    ===========================================================
            |
            v
      +-----+------+
      |applier.py  |  apply_brand_kit(template, kit) ->
      |            |    (TemplateSchema', logo_bytes | None)
      +-----+------+
            |
            v                         +---- images/ (optional)
      +-----+-----------------+       +---- textures/ (optional)
      | render_schema_brochure | <---+
      | (unchanged signature) |
      +-----+-----------------+
            |
            v  (outside_svg, inside_svg)
      +-----+------+        +-------------------+
      | Rasterizer |------->| brochure_*.png    |
      +-----+------+        +-------------------+
            |
            v
      ===========================================================
      |           AUDIT LOOP (up to 3 cycles)                   |
      ===========================================================
            |
            v
      +-----+------+      +------------------+
      | audit.py   | ---> | AuditReport      |
      |            |      | {whitespace,     |
      | Pillow     |      |  contrast,       |
      | histogram  |      |  density,        |
      | + contrast |      |  issues[]}       |
      | + density  |      +------------------+
      +-----+------+
            |
            |   if issues: remediate
            |    (swap contrast | regenerate_overflowed_copy)
            +------------ re-render (max 3 cycles)
```

### Recommended Project Structure

```
flyer_generator/brand_kit/
├── __init__.py              # public re-exports: BrandKit, fetch_brand_kit, apply_brand_kit, audit_render
├── __main__.py              # typer app with fetch/list/show subcommands
├── models.py                # BrandKit, BrandPalette, BrandTypography, BrandLogo, BrandVoice, BrandPhotoHints, ColorUsage
├── scraper.py               # fetch_brand_kit (orchestrates playwright_path + bs4_path); runtime fallback
├── scraper_playwright.py    # headless Chromium scraper (optional import — wraps import errors → None)
├── scraper_bs4.py           # pure httpx + BeautifulSoup4 scraper (test-harness backbone)
├── palette.py               # Pillow-based dominant-color extraction (quantize + getcolors)
├── contrast.py              # wcag_contrast_ratio + coloraide remediation; ContrastReport
├── applier.py               # apply_brand_kit(template, kit) -> (TemplateSchema, logo_bytes | None)
├── audit.py                 # audit_render(content, template, rendered_png_bytes) -> AuditReport; iterate_audit_loop
└── storage.py               # read/write .brand-kits/<slug>/; resolve FLYER_BRAND_KITS_DIR

tests/brand_kit/
├── __init__.py
├── fixtures/
│   ├── sample_site.html     # static HTML for BS4 fallback test
│   ├── sample_site.css      # @font-face + :root vars
│   └── sample_logo.png
├── test_models.py
├── test_scraper_bs4.py      # mocks httpx via respx, feeds fixture HTML
├── test_scraper_playwright.py  # mocks Page via unittest.mock.AsyncMock
├── test_palette.py          # synthetic PIL image → expected dominant colors
├── test_contrast.py         # known pairs (black/white → 21, red/red → 1) + remediation
├── test_applier.py          # sample kit + editorial_classic → assert palette swap + size scale
├── test_audit.py            # synthetic SVG with known low-contrast region + whitespace
├── test_storage.py          # tmp_path round-trip
├── test_cli.py              # typer CliRunner against fetch/list/show
└── test_e2e.py              # one kit + editorial_classic + mocked scrape → AA-clean assertion
```

The split between `scraper_playwright.py` (optional, isolated in its own module) and `scraper_bs4.py` (always importable) means `playwright` can be a hard dep in pyproject.toml but the import inside `scraper_playwright.py` is guarded so tests that don't need a browser never touch it.

### Pattern 1: Playwright async with graceful fallback

```python
# Source: Playwright Python docs https://playwright.dev/python/docs/library
from __future__ import annotations

import structlog
from playwright.async_api import async_playwright, Page, Browser

logger = structlog.get_logger()

async def scrape_with_playwright(url: str) -> PlaywrightArtifacts | None:
    """Return None if Playwright fails to launch; caller falls back to BS4."""
    try:
        async with async_playwright() as p:
            # launch() raises if Chromium binary is missing → caller falls back
            browser: Browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (compatible; flyer-generator-brand-kit/1.0)",
                )
                page: Page = await context.new_page()
                await page.goto(url, wait_until="networkidle", timeout=30_000)
                # Screenshot for palette extraction
                screenshot_bytes = await page.screenshot(full_page=False, type="png")
                # Dump rendered HTML for provenance
                html = await page.content()
                # Computed styles via evaluate()
                styles = await page.evaluate("""() => {
                    const pick = (sel) => {
                      const el = document.querySelector(sel);
                      if (!el) return null;
                      const cs = window.getComputedStyle(el);
                      return {
                        fontFamily: cs.fontFamily,
                        color: cs.color,
                        backgroundColor: cs.backgroundColor,
                      };
                    };
                    return {
                      body: pick('body'),
                      h1:   pick('h1'),
                      h2:   pick('h2'),
                    };
                }""")
                # Walk stylesheets for @font-face
                stylesheets = await page.evaluate("""() => {
                    return Array.from(document.styleSheets)
                      .map(s => s.href)
                      .filter(Boolean);
                }""")
                # Logo candidates: <img> with /logo/i and first inline <svg> in header
                logos = await page.evaluate("""() => {
                    const hdr = document.querySelector('header') || document.body;
                    const imgs = Array.from(hdr.querySelectorAll('img'));
                    return imgs
                      .filter(i => /logo/i.test(i.className + ' ' + i.alt + ' ' + i.src))
                      .map(i => i.src);
                }""")
                return PlaywrightArtifacts(
                    screenshot=screenshot_bytes,
                    rendered_html=html,
                    computed=styles,
                    stylesheet_urls=stylesheets,
                    logo_urls=logos,
                )
            finally:
                await browser.close()
    except Exception as err:  # includes playwright._impl._errors.Error when browser not installed
        logger.warning("brand_kit_playwright_failed", error=str(err)[:200])
        return None
```

**Key points (confirmed against Playwright docs):**
- `async with async_playwright()` is the correct context manager; `launch()` is awaitable.
- `wait_until="networkidle"` waits until no network activity for 500ms; works for SPA and static sites.
- `page.evaluate(...)` takes a JS function or expression, returns JSON-serializable values.
- `viewport={"width": 1920, "height": 1080}` sets logical viewport (used for screenshot sizing).
- `timeout` in milliseconds (Playwright convention, distinct from httpx's seconds).
- `browser.close()` in `finally` is idiomatic; `async_playwright()` context manager already handles the Playwright process itself.

### Pattern 2: BS4 fallback scraper

```python
# Source: beautifulsoup4 4.14 + httpx 0.28 + tinycss2 1.5
import re
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup
import tinycss2

_LOGO_RE = re.compile(r"logo", re.IGNORECASE)

async def scrape_bs4(url: str) -> BS4Artifacts:
    """Pure-HTTP scraper for no-JS sites and for testability."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=180.0) as client:
        resp = await client.get(url, headers={"User-Agent": "flyer-generator-brand-kit/1.0"})
        resp.raise_for_status()
        html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    # Meta
    title = (soup.title.string or "").strip() if soup.title else ""
    og = soup.find("meta", {"property": "og:site_name"})
    site_name = og["content"] if og and og.has_attr("content") else title
    h1 = soup.find("h1")
    h1_text = h1.get_text(strip=True) if h1 else ""

    # Logos
    logos = []
    for img in soup.find_all("img"):
        hay = " ".join([img.get("class", [""])[0] if img.get("class") else "",
                        img.get("alt", ""), img.get("src", "")])
        if _LOGO_RE.search(hay):
            logos.append(urljoin(url, img["src"]))

    # Stylesheets
    stylesheet_urls = [
        urljoin(url, link["href"])
        for link in soup.find_all("link", rel="stylesheet")
        if link.get("href")
    ]

    # Fetch CSS + extract @font-face + :root vars
    font_urls: list[str] = []
    color_vars: dict[str, str] = {}
    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
        for css_url in stylesheet_urls[:5]:  # cap — some sites ship 20+ bundles
            try:
                r = await client.get(css_url)
                if r.status_code != 200:
                    continue
                rules = tinycss2.parse_stylesheet(r.text, skip_whitespace=True, skip_comments=True)
                for rule in rules:
                    if rule.type == "at-rule" and rule.at_keyword == "font-face":
                        # Extract url(...) from content
                        for tok in rule.content or []:
                            if tok.type == "url":
                                font_urls.append(urljoin(css_url, tok.value))
                    elif rule.type == "qualified-rule":
                        # Look for :root { --var: #... }
                        sel = tinycss2.serialize(rule.prelude).strip()
                        if sel in (":root", "html"):
                            declarations = tinycss2.parse_declaration_list(
                                rule.content, skip_whitespace=True, skip_comments=True
                            )
                            for d in declarations:
                                if d.type == "declaration" and d.name.startswith("--"):
                                    val = tinycss2.serialize(d.value).strip()
                                    if val.startswith("#"):
                                        color_vars[d.name] = val
            except Exception:
                continue

    return BS4Artifacts(
        html=html, title=site_name, h1=h1_text,
        logo_urls=logos, stylesheet_urls=stylesheet_urls,
        font_urls=font_urls, css_color_vars=color_vars,
    )
```

**Why tinycss2 over regex:** regex on CSS is a known lossy path (nested `@media`, comments, `url("...")` vs `url('...')` vs `url(...)`). tinycss2 is ~200 KB, maintained, and pulls no transitive deps.

### Pattern 3: Palette extraction via Pillow (no new dep)

```python
# Source: Pillow docs https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.quantize
from PIL import Image
from io import BytesIO

def extract_palette(screenshot_bytes: bytes, n_colors: int = 5) -> list[tuple[str, int]]:
    """Return [(hex, pixel_count), ...] for the top-n dominant colors.

    Uses MEDIANCUT on RGB image (Pillow's default). Order is by pixel count
    descending. Hex is '#RRGGBB'.
    """
    img = Image.open(BytesIO(screenshot_bytes)).convert("RGB")
    # Downsample for speed — median cut over 2M pixels is ~1.5s; over 200K is ~100ms
    img.thumbnail((800, 600))
    # kmeans=0 means pure median-cut; kmeans=1 refines centroids but slower
    quantized = img.quantize(colors=n_colors, method=Image.Quantize.MEDIANCUT, kmeans=0)
    palette = quantized.getpalette()  # list[int] of length 256*3
    # getcolors returns [(count, index), ...] for palette-mode images
    counts = quantized.getcolors(maxcolors=n_colors) or []
    counts.sort(key=lambda t: -t[0])  # most frequent first
    out = []
    for count, idx in counts:
        r, g, b = palette[idx * 3], palette[idx * 3 + 1], palette[idx * 3 + 2]
        out.append((f"#{r:02X}{g:02X}{b:02X}", count))
    return out
```

**Why MEDIANCUT over MAXCOVERAGE or FASTOCTREE:**
- MEDIANCUT prioritizes perceptually distinct colors → better for "brand colors."
- MAXCOVERAGE prioritizes pixel count → would return 5 near-identical neutrals on a mostly-white site.
- FASTOCTREE is fastest but noisiest.

**Calibration note:** Run this against the shrubnet-v9 screenshot during implementation to confirm the top-5 are {brand-green, dark-text, light-bg, accent-lime, photo-mid-tone}-ish. If shrubnet's hero photo dominates the palette, bump `thumbnail` to a square crop of the header region before quantizing.

### Pattern 4: WCAG contrast with remediation

```python
# Source: wcag-contrast-ratio 0.9 + coloraide 8.8 docs
import wcag_contrast_ratio as contrast
from coloraide import Color

def _hex_to_floats(hex_color: str) -> tuple[float, float, float]:
    """'#1E3A5F' -> (0.118, 0.227, 0.372)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (r / 255.0, g / 255.0, b / 255.0)

def wcag_ratio(fg_hex: str, bg_hex: str) -> float:
    return contrast.rgb(_hex_to_floats(fg_hex), _hex_to_floats(bg_hex))

def passes_aa(fg_hex: str, bg_hex: str, large_text: bool = False) -> bool:
    r = wcag_ratio(fg_hex, bg_hex)
    threshold = 3.0 if large_text else 4.5
    return r >= threshold

def remediate(
    fg_hex: str,
    bg_hex: str,
    neutrals: tuple[str, str],  # (dark_hex, light_hex) from kit.palette
    large_text: bool = False,
) -> tuple[str, str]:
    """Return (new_fg, note) that passes AA. Strategy:

    1. If current fg already passes AA → return unchanged.
    2. Try opposite neutral (pick the one that DOESN'T match fg's luminance band).
    3. If still failing, nudge fg's lightness in OKLCH toward the neutral that
       passes, preserving hue family.
    4. If no solution found → return fg unchanged with a FAIL note.
    """
    if passes_aa(fg_hex, bg_hex, large_text):
        return fg_hex, "pass"

    dark, light = neutrals
    # Pick the neutral farther from bg's luminance
    bg_l = Color(bg_hex).convert("oklab")["lightness"]
    candidate = dark if bg_l > 0.5 else light
    if passes_aa(candidate, bg_hex, large_text):
        return candidate, f"swapped to {'neutral_dark' if candidate == dark else 'neutral_light'}"

    # OKLCH lightness nudge (binary search), preserving hue
    c = Color(fg_hex).convert("oklch")
    target = 4.5 if not large_text else 3.0
    lo, hi = 0.0, 1.0
    best = fg_hex
    for _ in range(12):  # ~0.02 precision in lightness
        mid = (lo + hi) / 2
        c["lightness"] = mid
        trial = c.convert("srgb").to_string(hex=True)
        ratio = wcag_ratio(trial, bg_hex)
        if ratio >= target:
            best = trial
            # Find the minimum perturbation: walk BACK toward original
            orig_l = Color(fg_hex).convert("oklch")["lightness"]
            if mid > orig_l:
                hi = mid  # we went too far light; try less
            else:
                lo = mid  # we went too far dark; try less
        else:
            if mid > 0.5:
                hi = mid
            else:
                lo = mid
    if passes_aa(best, bg_hex, large_text):
        return best, f"OKLCH lightness nudge {Color(fg_hex).convert('oklch')['lightness']:.2f}→{Color(best).convert('oklch')['lightness']:.2f}"

    return fg_hex, "FAIL: no AA-compliant fg found"
```

**Key API facts (verified):**
- `wcag_contrast_ratio.rgb()` takes **tuples of floats 0.0-1.0**, NOT ints 0-255. Returns a float (symmetric: order doesn't matter).
- `coloraide.Color(hex).contrast(other, method='wcag21')` exists and is the canonical WCAG ratio method in coloraide. So either lib can compute the ratio; prefer `wcag-contrast-ratio` for validation (simpler) and `coloraide` for color-space math.
- coloraide does NOT ship a built-in "adjust until passing" helper. We write the binary search (shown above) or use the opposite-neutral swap as primary strategy.
- OKLCH is the right color space for hue-preserving lightness changes — better than HSL (which distorts saturation).

### Pattern 5: Apply kit → template

```python
# Source: TemplateSchema at flyer_generator/brochure/schema_renderer/schema_model.py:355
from flyer_generator.brochure.schema_renderer.schema_model import (
    TemplateSchema, Palette, Typography,
)

def apply_brand_kit(
    template: TemplateSchema, kit: BrandKit
) -> tuple[TemplateSchema, bytes | None]:
    """Return (new_template, logo_bytes). Never mutates the input."""
    # Palette mapping
    new_palette = Palette(
        accent_default=kit.palette.primary.hex,
        neutral_dark=kit.palette.neutral_dark.hex,
        neutral_light=kit.palette.neutral_light.hex,
        muted=kit.palette.secondary.hex or template.palette.muted,
        extras={k: v.hex for k, v in kit.palette.extras.items()},
    )

    # Typography — scale sizes by size_multiplier, swap families
    typ = template.typography
    scaled_fields = {
        f: round(getattr(typ, f) * kit.size_multiplier)
        for f in (
            "cover_title_size", "cover_subtitle_size", "heading_size",
            "body_size", "body_line_height", "bullet_size", "bullet_line_height",
        )
    }
    new_typography = typ.model_copy(update={
        "heading_family": kit.typography.heading_family,
        "body_family": kit.typography.body_family,
        **scaled_fields,
    })

    new_template = template.model_copy(update={
        "palette": new_palette,
        "typography": new_typography,
    })

    # Logo bytes — primary variant preferred
    logo_bytes: bytes | None = None
    if kit.logos:
        primary = next((l for l in kit.logos if l.variant == "primary"), kit.logos[0])
        kit_dir = resolve_kit_dir(kit.name)  # from storage.py
        logo_path = kit_dir / primary.path
        if logo_path.is_file():
            logo_bytes = logo_path.read_bytes()

    return new_template, logo_bytes
```

**Integration with existing CLI** (addition to `schema_renderer/__main__.py`):

```python
brand_kit_slug: Annotated[
    Optional[str],
    typer.Option("--brand-kit", help="Apply a brand kit by slug."),
] = None,

# ... after loading template ...
if brand_kit_slug is not None:
    kit = load_brand_kit(brand_kit_slug)
    tmpl, kit_logo_bytes = apply_brand_kit(tmpl, kit)
    if color_accent is not None:
        typer.echo(
            f"Warning: --brand-kit overrides --color-accent ({color_accent} ignored)",
            err=True,
        )
        color_accent = None
    # Logo precedence: explicit --logo wins over kit
    if logo is None and kit_logo_bytes is not None:
        logo_bytes = kit_logo_bytes
```

### Pattern 6: Whitespace density audit

```python
# Source: Pillow docs https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.histogram
from PIL import Image
from io import BytesIO

def panel_whitespace_ratio(
    rendered_png_bytes: bytes,
    panel_bleed_rect: tuple[int, int, int, int],  # (x, y, w, h) in sheet coords
    background_hex: str,
    tolerance: int = 12,
) -> float:
    """Ratio of pixels within `tolerance` channels of `background_hex`.

    1.0 = panel is entirely whitespace (bad).
    0.0 = every pixel differs from background (good — content everywhere).

    Typical "empty" values to flag: > 0.85.
    """
    img = Image.open(BytesIO(rendered_png_bytes)).convert("RGB")
    x, y, w, h = panel_bleed_rect
    panel = img.crop((x, y, x + w, y + h))
    # Parse background hex
    bh = background_hex.lstrip("#")
    br, bg, bb = int(bh[0:2], 16), int(bh[2:4], 16), int(bh[4:6], 16)

    # Count pixels within tolerance — vectorized in pure Pillow via point + compare
    # Simplest portable approach: iterate histogram of each channel separately
    # and compute approximate match rate. For exactness, fall back to numpy-free
    # loop over resized panel (fine at 220x510 at 1/15 scale).
    panel_small = panel.resize((max(1, w // 15), max(1, h // 15)), Image.Resampling.LANCZOS)
    total = 0
    hits = 0
    for pr, pg, pb in panel_small.getdata():
        total += 1
        if abs(pr - br) <= tolerance and abs(pg - bg) <= tolerance and abs(pb - bb) <= tolerance:
            hits += 1
    return hits / max(1, total)
```

**Alternatives considered:**
- **Bounding-box occupancy:** sum every panel element's bbox area / panel area. Fast (no image read) but wrong — a huge background shape registers as "full" even when visually empty. **Rejected.**
- **Grid-cell entropy:** split panel into N×M cells, count cells with variance > threshold. Correct but more parameters to tune. **Deferred as v2.**
- **The histogram ratio above** is the simplest correct thing, runs in ~20ms per panel at 1/15 scale.

**Threshold calibration:** run against `/tmp/shrubnet-v9/brochure_front.png` first — expect inner-panel ratios around 0.55-0.70 (good) and back-sheet tuck-flap around 0.80 (mostly solid color with center logo — should be explicitly excluded from the density check, or have a panel-specific threshold).

### Anti-Patterns to Avoid

- **Hand-rolling WCAG math.** The formula is "simple" but has edge cases (sRGB gamma, the `0.03928` threshold, linear-to-relative-luminance). Use `wcag-contrast-ratio`.
- **Running Playwright inside a running event loop without `async with`.** Playwright has its own process lifecycle; the context manager is non-negotiable.
- **Using `requests` for CSS/logo downloads in the BS4 path.** Stack is httpx-first; mixing breaks respx mocking and adds an accidental dep.
- **Regexing CSS.** `@font-face` rules can contain comments, nested strings, and `url()` syntax variations. Use tinycss2.
- **Blocking call to `playwright install` at runtime.** Document it as a one-time setup step; do not invoke it from code.
- **Mutating the passed-in `TemplateSchema` in `apply_brand_kit`.** Always `model_copy(deep=True)` — the renderer already does this for `accent_override` (renderer.py:753), match that convention.
- **Calling `asyncio.run()` inside `asyncio.run()`.** The CLI entry is synchronous; it calls `asyncio.run(fetch_brand_kit(...))`. Library code never calls `asyncio.run()`.
- **Storing Playwright as a conditional / dev-only dep.** It's a hard runtime dep of the primary scraper path; make it a regular `[project].dependencies` entry. (The BS4 path is the fallback, not the primary.)

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WCAG ratio calculation | Custom luminance math | `wcag-contrast-ratio` | sRGB gamma decode + relative luminance + 0.03928 threshold are easy to get wrong |
| CSS parsing (@font-face, :root vars) | Regex | `tinycss2` | Nested selectors, comments, `url("...")`/`url('...')`/`url(...)`, `@media` wrappers all break regex |
| Image palette extraction | KMeans from scratch | `PIL.Image.quantize(colors=5, method=MEDIANCUT)` | Built into existing Pillow dep; median-cut is the standard algorithm |
| HTML parsing | Regex | `beautifulsoup4` | Malformed HTML, self-closing tags, entity decoding — not worth it |
| Headless browser | subprocess + CDP | `playwright` | Chromium process lifecycle, WS protocol, resource cleanup all handled |
| OKLCH color math | Custom conversion | `coloraide` | Gamma, gamut mapping, whitepoint conversions are spec-heavy |
| CSS URL resolution | String concat | `urllib.parse.urljoin` | Handles `//cdn.x.com/a.css`, `../`, absolute, base tags correctly |
| Pydantic JSON round-trip | Manual `json.dumps` | `model.model_dump_json()` / `Model.model_validate_json()` | Already used repo-wide |
| CLI arg parsing | argparse | `typer` | Matches existing `schema_renderer/__main__.py` style (type hints → flags) |

**Key insight:** this phase is a glue layer. Every "hard" problem (HTML, CSS, headless, colors, WCAG) has a battle-tested library. Our job is orchestration + the audit loop logic, not reimplementing browser automation or color science.

---

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `.brand-kits/<slug>/brand.json` + `logos/*` + `source/*` | Purely additive (Phase 18 introduces this; no existing data to migrate) |
| Live service config | None — no external services modify state | none |
| OS-registered state | Playwright installs Chromium to `~/.cache/ms-playwright/` (Linux) / `~/Library/Caches/ms-playwright/` (macOS) / `%USERPROFILE%\AppData\Local\ms-playwright\` (Windows) | Documented one-time `playwright install chromium` step — no cleanup needed; gitignored by default |
| Secrets/env vars | **New:** `FLYER_BRAND_KITS_DIR` — optional, defaults to `.brand-kits/` CWD-relative | Add to `Settings` in `flyer_generator/config.py` |
| Build artifacts | None — no generated Python modules, no compiled assets | none |

**No existing data to migrate.** Phase 18 is additive: new directory, new model, new CLI subcommand. The only "state" that exists after this phase ships is whatever the user materializes by calling `fetch`.

---

## Common Pitfalls

### Pitfall 1: Playwright Chromium binary is not installed at runtime

**What goes wrong:** `playwright.async_api.async_playwright()` context manager succeeds but `p.chromium.launch()` raises `playwright._impl._errors.Error: Executable doesn't exist at /home/user/.cache/ms-playwright/chromium-xxxx/chrome-linux/chrome`.

**Why it happens:** `pip install playwright` installs the Python library only. The Chromium binary is downloaded by the separate `playwright install chromium` command. On fresh CI runners or new dev machines this is an easy-to-miss step.

**How to avoid:**
- Document in README: `python -m playwright install chromium` as post-install step.
- In `scraper.py`, catch launch errors → fall through to BS4 fallback automatically.
- In tests, mock `async_playwright` entirely (no binary needed).
- In CI, add `python -m playwright install --with-deps chromium` to the job (pulls system libs on Ubuntu).

**Warning signs:** First-time test run fails with "Executable doesn't exist" — tell user to run install command.

### Pitfall 2: `wcag-contrast-ratio.rgb()` accepts float tuples, not int tuples

**What goes wrong:** `contrast.rgb((30, 58, 95), (255, 255, 255))` returns a nonsense ratio (the library treats ints > 1 as floats in an extended color space).

**Why it happens:** The 2015-era API convention predates common "hex string / int 0-255" norms and assumes sRGB-normalized floats.

**How to avoid:** Always divide by 255.0 before calling. Wrap in a `wcag_ratio(fg_hex, bg_hex)` helper that handles the conversion.

**Warning signs:** Contrast ratios > 21 or < 1 (the library's valid range is exactly 1.0-21.0).

### Pitfall 3: Network-idle never fires on sites with long-polling / analytics

**What goes wrong:** `await page.goto(url, wait_until="networkidle")` hangs up to Playwright's 30s default timeout because an analytics script polls every 5s, preventing network-idle.

**Why it happens:** `networkidle` requires 500ms of zero network activity — sites with Hotjar, Intercom, analytics pixels never reach that.

**How to avoid:**
- Wrap in `try: ...goto(... wait_until="networkidle", timeout=15_000)... except PlaywrightTimeoutError: await page.goto(url, wait_until="domcontentloaded")`.
- Or use `wait_until="load"` (waits for `load` event, not full quiescence) as primary and skip networkidle.
- **Recommended:** `wait_until="load"` + explicit `page.wait_for_timeout(2000)` to let CSS/fonts settle for screenshot.

**Warning signs:** Scraper times out on common marketing sites (Hubspot, Intercom-enabled).

### Pitfall 4: Partial `BrandKit` fails Pydantic validation

**What goes wrong:** Scraper can't extract typography → `BrandTypography` can't be constructed because `heading_family`/`body_family` are required → whole `BrandKit` validation fails.

**Why it happens:** The CONTEXT.md spec says "missing fields stay null" but Pydantic defaults are strict.

**How to avoid:**
- Make every nested model's required fields have sensible fallback defaults:
  - `BrandTypography.heading_family: str = "sans-serif"`
  - `BrandTypography.body_family: str = "sans-serif"`
  - `BrandPalette.primary: ColorUsage` — use a fallback `ColorUsage(hex="#000000", usage_hint="scraper default")` if nothing was extracted.
- Or: `BrandTypography | None` at the `BrandKit` level, and the applier handles the null case by keeping the template's existing typography.

**Recommendation:** the second option is cleaner — `palette: BrandPalette | None`, `typography: BrandTypography | None`, `logos: list[BrandLogo] = []`. The applier becomes:

```python
if kit.palette is not None:
    new_palette = ...  # swap
else:
    new_palette = template.palette  # keep template
```

This preserves the "missing fields stay null" semantic at the field level and defers the interpretation to the applier.

**Warning signs:** Tests that feed a minimal fixture HTML fail to construct `BrandKit` — tighten the fallback defaults or switch to Optional.

### Pitfall 5: Bumping body_size causes `fit_to_bbox` truncation cascade

**What goes wrong:** Raising `body_size` from 30 → 36 across templates causes `text_fit.fit_to_bbox()` to exceed max_lines in tight bboxes → content silently truncates → end-to-end renders show "..." where before showed full paragraphs.

**Why it happens:** `fit_to_bbox` at `text_fit.py:122-134` floors `max_lines = int(h / line_height)`, then slices `all_lines[:max_lines]` with `overflowed = True`.

**How to avoid:**
- For each template touched, run the gallery test suite BEFORE and AFTER size bump; compare `FittedText.overflowed` flags (can instrument `fit_to_bbox` to log the counts).
- Couple every `body_size` bump with a proportional `body_line_height` bump AND, where bboxes are tight, an `h` bump.
- **Safer alternative:** do NOT edit the JSONs; instead bump the runtime `size_multiplier` default from `1.0` → `1.15`. The `_apply_budgets` / `_per_item_char_limit` math will auto-tighten the char budget so LLM writes shorter copy for the same region. This preserves 78-cell gallery stability without touching 13 JSONs.
- **Recommended two-track approach from CONTEXT.md:** do both. Baseline JSON sizes bump slightly (body 30 → 32, bullet 30 → 32), AND `size_multiplier` default stays `1.0` (opt-in per-kit). A brand kit can push `size_multiplier=1.15` when it wants bigger type without forcing every template to a higher baseline.

**Warning signs:** Gallery test `test_gallery` asserts overflowed = False; any new truncation will fail it.

### Pitfall 6: Palette from hero-dominated screenshot is hero-colored, not brand-colored

**What goes wrong:** A site like shrubnet.com has a huge hero photo → the top-5 colors are dominated by photo tones, not brand swatches.

**Why it happens:** Median-cut quantizes ALL pixels in the screenshot equally — photos have vastly more pixel area than a small logo or headline.

**How to avoid:**
- **Primary strategy:** compose the palette from BOTH screenshot-quantized colors AND CSS `:root` custom properties. CSS vars are authored deliberately by the designer.
- **Secondary strategy:** crop out the hero region before quantizing. Default crop: top 15% of page + bottom 15% (header + footer usually contain brand colors; middle is hero content).
- **Tertiary:** allow manual override via `--color-primary <hex>` flag on `fetch` that the user can pass when the auto-extraction looks wrong.

**Warning signs:** Visual inspection of `brand.json` shows palette is all mid-tone grays/beiges — signals the photo dominated.

### Pitfall 7: `--brand-kit` + `--color-accent` ambiguity

**What goes wrong:** User supplies both; neither spec nor CLI makes precedence obvious → two commits later it's a bug report.

**Why it happens:** Both flags write to the same slot (`palette.accent_default`).

**How to avoid:** Locked decision from CONTEXT.md: `--brand-kit` wins, log a warning. Implement as:

```python
if brand_kit_slug is not None and color_accent is not None:
    logger.warning("brand_kit_overrides_color_accent", kit=brand_kit_slug, ignored=color_accent)
    color_accent = None
```

Do the same for `--logo` vs kit logo: `--logo` wins (user's explicit override), kit logo is only used when `--logo` is absent.

**Warning signs:** Test the specific combination `python -m ... --brand-kit foo --color-accent #FF00FF` and assert the kit's primary color is what ends up in the render.

---

## Code Examples

### Example 1: End-to-end fetch (CLI handler)

```python
# flyer_generator/brand_kit/__main__.py
import asyncio
from pathlib import Path
from typing import Annotated, Optional
import typer
import structlog

from flyer_generator.brand_kit.scraper import fetch_brand_kit
from flyer_generator.brand_kit.storage import list_kits, load_kit, resolve_kits_dir

app = typer.Typer(help="Brand kit scraper and applier.")
logger = structlog.get_logger()


@app.command()
def fetch(
    url: Annotated[str, typer.Argument(help="Website URL to scrape.")],
    slug: Annotated[str, typer.Option("--slug", help="Output slug (identifier).")],
    force: Annotated[bool, typer.Option("--force", help="Overwrite existing.")] = False,
) -> None:
    """Scrape `url` into .brand-kits/<slug>/."""
    kit = asyncio.run(fetch_brand_kit(url, slug, force=force))
    typer.echo(f"Wrote .brand-kits/{slug}/brand.json")
    typer.echo(f"  palette: primary={kit.palette.primary.hex if kit.palette else 'null'}")
    typer.echo(f"  typography: {kit.typography.heading_family if kit.typography else 'null'}")
    typer.echo(f"  logos: {len(kit.logos)}")


@app.command()
def list() -> None:
    """List slugs under FLYER_BRAND_KITS_DIR."""
    for name in list_kits():
        typer.echo(name)


@app.command()
def show(slug: str) -> None:
    """Print a kit as JSON."""
    kit = load_kit(slug)
    typer.echo(kit.model_dump_json(indent=2))


if __name__ == "__main__":
    app()
```

### Example 2: Test mocking Playwright Page

```python
# tests/brand_kit/test_scraper_playwright.py
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from flyer_generator.brand_kit.scraper_playwright import scrape_with_playwright


@pytest.mark.asyncio
async def test_playwright_scraper_happy_path():
    fake_page = MagicMock()
    fake_page.goto = AsyncMock()
    fake_page.screenshot = AsyncMock(return_value=b"\x89PNG\r\n...")
    fake_page.content = AsyncMock(return_value="<html><body><h1>X</h1></body></html>")
    fake_page.evaluate = AsyncMock(side_effect=[
        {"body": {"fontFamily": "Inter, sans-serif", "color": "rgb(0,0,0)",
                  "backgroundColor": "rgb(255,255,255)"},
         "h1":   {"fontFamily": "Playfair, serif", "color": "rgb(20,20,20)",
                  "backgroundColor": "rgb(255,255,255)"},
         "h2":   None},
        ["https://cdn.site.com/style.css"],
        ["https://cdn.site.com/logo.png"],
    ])

    fake_context = MagicMock()
    fake_context.new_page = AsyncMock(return_value=fake_page)

    fake_browser = MagicMock()
    fake_browser.new_context = AsyncMock(return_value=fake_context)
    fake_browser.close = AsyncMock()

    fake_pw = MagicMock()
    fake_pw.chromium.launch = AsyncMock(return_value=fake_browser)

    with patch("flyer_generator.brand_kit.scraper_playwright.async_playwright") as mock_apw:
        mock_apw.return_value.__aenter__ = AsyncMock(return_value=fake_pw)
        mock_apw.return_value.__aexit__ = AsyncMock()

        artifacts = await scrape_with_playwright("https://example.com")

    assert artifacts is not None
    assert artifacts.screenshot == b"\x89PNG\r\n..."
    assert "h1" in artifacts.rendered_html.lower()
    assert artifacts.computed["body"]["fontFamily"] == "Inter, sans-serif"


@pytest.mark.asyncio
async def test_playwright_failure_returns_none():
    """Playwright launch failure → None (caller falls back to BS4)."""
    with patch("flyer_generator.brand_kit.scraper_playwright.async_playwright") as mock_apw:
        mock_apw.return_value.__aenter__ = AsyncMock(
            side_effect=Exception("chromium not installed")
        )
        result = await scrape_with_playwright("https://example.com")
    assert result is None
```

### Example 3: Test BS4 path with respx

```python
# tests/brand_kit/test_scraper_bs4.py
import respx
import httpx
import pytest
from pathlib import Path

from flyer_generator.brand_kit.scraper_bs4 import scrape_bs4

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
@respx.mock
async def test_bs4_scraper_extracts_logo_and_fonts():
    html = (FIXTURE_DIR / "sample_site.html").read_text()
    css  = (FIXTURE_DIR / "sample_site.css").read_text()
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=html))
    respx.get("https://example.com/style.css").mock(return_value=httpx.Response(200, text=css))

    artifacts = await scrape_bs4("https://example.com/")

    assert "example.com/assets/logo.png" in " ".join(artifacts.logo_urls)
    assert any("Playfair" in u or "playfair" in u for u in artifacts.font_urls + [css])
    assert artifacts.css_color_vars.get("--brand-primary", "").startswith("#")
```

### Example 4: Synthetic SVG for audit test

```python
# tests/brand_kit/test_audit.py
import io
import pytest
from PIL import Image

from flyer_generator.brand_kit.audit import panel_whitespace_ratio


def _synthetic_panel_png(width: int, height: int,
                         bg_hex: str, content_rect: tuple[int,int,int,int] | None) -> bytes:
    img = Image.new("RGB", (width, height),
                    tuple(int(bg_hex.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)))
    if content_rect:
        # Draw a non-bg block to simulate content
        from PIL import ImageDraw
        d = ImageDraw.Draw(img)
        d.rectangle(content_rect, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_empty_panel_is_full_whitespace():
    png = _synthetic_panel_png(1100, 2550, "#FAFAF7", content_rect=None)
    ratio = panel_whitespace_ratio(png, (0, 0, 1100, 2550), "#FAFAF7")
    assert ratio > 0.95


def test_half_filled_panel_is_half_whitespace():
    png = _synthetic_panel_png(1100, 2550, "#FAFAF7",
                                content_rect=(0, 0, 1100, 1275))  # top half black
    ratio = panel_whitespace_ratio(png, (0, 0, 1100, 2550), "#FAFAF7")
    assert 0.40 < ratio < 0.60
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Selenium + chromedriver | Playwright async | 2020-2022 across industry | Playwright is ~2-3× faster, has a more modern API (no implicit waits), and bundles its own browser |
| `colorthief` (Python 2 era) | Pillow `Image.quantize()` | colorthief abandoned 2017 | Built into existing dep, no new install, identical median-cut algorithm |
| `cssutils` | `tinycss2` | cssutils stagnated ~2018; tinycss2 actively maintained by WeasyPrint team | Same API surface for common ops, saner error handling |
| WCAG 2.0 | WCAG 2.1 (ratios unchanged) / APCA experimental | W3C 2018 / ongoing | `wcag-contrast-ratio` implements the ratio formula unchanged since 2008; APCA is a candidate for WCAG 3 but not settled — don't chase it yet |
| Manual `@font-face` regex | tinycss2 AST walk | Always correct | Handles nested @-rules, comments, escaped strings |
| `requests` sync HTTP | `httpx` async | 2020+ | Matches project stack (CLAUDE.md); respx mocks work cleanly |

**Deprecated/outdated:**
- `colorthief` (2017, Python 2) → replaced by Pillow native.
- `cssutils` → replaced by `tinycss2`.
- `selenium` for Python scraping → replaced by Playwright.
- Anything using `webdriver-manager` / `chromedriver-autoinstaller` → Playwright bundles its own binaries.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Pillow `Image.quantize(MEDIANCUT)` on a full-page screenshot produces brand-representative colors for most sites | Pattern 3, Pitfall 6 | Low — mitigated by combining with CSS `:root` vars and optional `--color-primary` override |
| A2 | Default `size_multiplier = 1.15` is a reasonable baseline for typography uplift | Pattern 5, Pitfall 5 | Medium — must calibrate against gallery; safer to default 1.0 and require explicit opt-in |
| A3 | Whitespace ratio > 0.85 is a reliable "empty panel" signal across all 13 templates | Pattern 6, Pitfall — | Medium — tuck_flap panels are typically 90%+ single color; need per-panel thresholds or a deny-list |
| A4 | OKLCH binary-search remediation converges within 12 iterations for any fg/bg pair | Pattern 4 | Low — logarithmic convergence; 12 iters = ~0.02 lightness precision |
| A5 | Playwright's `wait_until="networkidle"` is reliable enough to use as primary wait strategy | Pitfall 3 | Medium — fall back to `wait_until="load"` + explicit wait_for_timeout on analytics-heavy sites |
| A6 | The existing 78-cell gallery test is the right regression harness for typography uplift | Requirement BK-09 | Low — verified by reading `tests/brochure/schema_renderer/test_gallery.py` reference in HANDOFF §9 |
| A7 | `coloraide>=8.0` is API-compatible with the spec's `>=4.0` pin | Standard Stack | Low — `Color.contrast()` is a stable core API; major version bumps have been additive in coloraide |
| A8 | No existing project skills in `.claude/skills/` or `.agents/skills/` affect brand kit research | Project context | Verified empty by directory listing |
| A9 | Pillow whitespace audit at 1/15 scale (~220×510 per panel) samples enough pixels for stable density | Pattern 6 | Low — ~112K samples per panel is statistically ample |

---

## Open Questions

1. **coloraide OKLCH lightness nudging — is there a built-in "reach target ratio" helper?**
   - What we know: `Color.contrast()` returns a ratio; `Color[space_channel]` indexing lets you mutate channels.
   - What's unclear: whether a newer coloraide helper (e.g. `Color.interpolate(...)` with a contrast constraint) obviates the binary search.
   - Recommendation: implement the binary search as shown in Pattern 4; check `coloraide` docs for `contrast-finder` or similar during implementation and swap if found. Not a blocker — binary search is 20 lines.

2. **When the BS4 fallback encounters a site with all CSS loaded via JS (`<script src="...inject-styles...">`), what's the minimum viable brand kit?**
   - What we know: `font-family: sans-serif; color: #000` defaults can be extracted from `<body>`'s inline styles if present.
   - What's unclear: how often the fallback produces an unusably sparse kit.
   - Recommendation: require at least `palette.primary` to be set for a kit to be "valid"; if neither Playwright nor BS4 can populate it, raise `BrandKitScrapeError` with the partial artifacts so the user can fill manually.

3. **Should the audit loop's `text_gen` remediation pass the PRIOR generated content back to the LLM, or regenerate from scratch?**
   - What we know: `generate_content_from_prompt` (text_gen.py:555) takes `prompt`, `brief`, `contact` — does NOT accept existing content to edit.
   - What's unclear: whether adding an `edit_prior=BrochureContent` param is Phase 18 scope or Phase 19.
   - Recommendation: **Phase 18 audit loop** should remediate only by (a) contrast-swap (no LLM call) and (b) retrying text_gen with the failing regions' tighter char budgets. Edit-in-place is Phase 19. This keeps the 3-cycle budget cheap (contrast swap is microseconds; LLM call is 5-20s).

4. **Default palette strategy when scraper finds zero hex colors in CSS and screenshot palette is saturation-flat (grayscale photo site)?**
   - What we know: Some sites (film sites, minimal portfolios) render entirely in grays.
   - What's unclear: whether a black-and-white brand kit renders any differently from the template default palette.
   - Recommendation: treat as valid — kit.palette.primary = extracted dark gray, neutral_dark = pure black, neutral_light = pure white. Log `brand_kit_monochrome_detected` structlog event; applier returns this kit unchanged; the rendered brochure is legitimately grayscale. Acceptable.

5. **Where does `BrandKitError` live?**
   - Pattern: existing `flyer_generator/errors.py` hosts `ComfyError`, `VisionError`, etc.
   - Recommendation: add `BrandKitError` and subclasses (`BrandKitScrapeError`, `BrandKitContrastError`, `BrandKitAuditError`) to the same `errors.py` module to match convention.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | ✓ | 3.11+ | — |
| uv | Package mgmt | ✓ (per CLAUDE.md) | >=0.11 | pip |
| Playwright Chromium binary | Primary scraper | ✗ (needs `python -m playwright install chromium`) | would be 145.x | BS4 + httpx fallback path |
| Cairo (system lib) | Existing (cairosvg) | ✓ (repo already uses it) | — | — |
| libjpeg / zlib | Existing (Pillow) | ✓ | — | — |
| Internet egress | Scraper fetch + font downloads | Assumed ✓ | — | — |

**Missing dependencies with no fallback:**
- None — every required piece has either an installed-by-pip wheel or a graceful fallback path.

**Missing dependencies with fallback:**
- Playwright Chromium binary → BS4+httpx fallback. First-time-use docs must document `python -m playwright install chromium`.

---

## Project Constraints (from CLAUDE.md)

| Directive | Source | How Phase 18 Complies |
|-----------|--------|------------------------|
| Python 3.11+ (target 3.12) | CLAUDE.md Runtime | All new code targets 3.11+; type hints use `X | None` syntax |
| uv for package management | CLAUDE.md Runtime | New deps added via `uv add`; lockfile updated |
| Pydantic v2 for all data contracts | CLAUDE.md Core | BrandKit, BrandPalette, BrandTypography, etc. use `BaseModel` + `ConfigDict(extra="forbid")` |
| pydantic-settings for config | CLAUDE.md Core | `FLYER_BRAND_KITS_DIR` added to `Settings` class in `flyer_generator/config.py` |
| httpx async for all API calls | CLAUDE.md Core | BS4 scraper uses `httpx.AsyncClient(timeout=180.0)` mirroring `image_gate.py` |
| structlog for logging | CLAUDE.md Core | `logger = structlog.get_logger()` at module top; `logger.info("brand_kit_fetched", slug=...)` |
| typer for CLI | CLAUDE.md Core | `brand_kit/__main__.py` uses `typer.Typer()` + `@app.command()` decorators |
| Pillow for image processing | CLAUDE.md Image Processing | Palette extraction + whitespace audit use Pillow — no new image dep |
| CairoSVG primary, resvg fallback | CLAUDE.md Image Processing | Audit loop re-renders via existing `Rasterizer` which already handles this |
| pytest + pytest-asyncio auto-mode | CLAUDE.md Dev & Testing | `mode="auto"` in `[tool.pytest.ini_options]` — no `@pytest.mark.asyncio` needed |
| respx for httpx mocking | CLAUDE.md Dev & Testing | BS4 scraper tests use `@respx.mock` + `respx.get(...).mock(return_value=httpx.Response(200, text=...))` |
| ruff lint + format | CLAUDE.md Dev & Testing | New modules conform to `select = ["E", "F", "I", "N", "W", "UP", "B", "SIM", "TCH"]` |
| No Node.js deps | CLAUDE.md Constraints | Playwright is Python — despite driving Chromium (a C++ binary), no Node stack required |
| XML-escape user strings | CLAUDE.md convention (implicit via existing code) | Renderer already does this (`xml.sax.saxutils.escape`); no new SVG emission in brand kit modules |
| trace_id per generation | CLAUDE.md convention | `scraper.fetch_brand_kit` binds a trace_id at entry: `structlog.contextvars.bind_contextvars(trace_id=uuid4().hex)` |

---

## Sources

### Primary (HIGH confidence — verified this session)

- [Playwright Python PyPI](https://pypi.org/project/playwright/) — v1.58.0, 2026-01-30, wheels for Linux/macOS/Windows incl. ARM64
- [Playwright Python getting started](https://playwright.dev/python/docs/intro) — install flow, async usage
- [Playwright Browsers docs](https://playwright.dev/python/docs/browsers) — `playwright install chromium`, `--only-shell` option
- [beautifulsoup4 PyPI](https://pypi.org/project/beautifulsoup4/) — v4.14.3, 2025-11-30, pure-Python wheel
- [tinycss2 PyPI + docs](https://doc.courtbouillon.org/tinycss2/stable/api_reference.html) — v1.5.1, 2025-11-23; `parse_stylesheet`, `parse_stylesheet_bytes`
- [wcag-contrast-ratio PyPI](https://pypi.org/project/wcag-contrast-ratio/) — v0.9, 2015-07-30; `rgb()` takes float tuples
- [coloraide PyPI](https://pypi.org/project/coloraide/) — v8.8.1, 2026-03-22
- [coloraide Contrast API](https://facelessuser.github.io/coloraide/contrast/) — `Color.contrast(other, method='wcag21')`, WCAG 2.1 + Lstar methods
- [Pillow Image module](https://pillow.readthedocs.io/en/stable/reference/Image.html) — `Image.quantize(colors, method, kmeans)`
- [Pillow ImageStat / histogram](https://pillow.readthedocs.io/en/stable/reference/ImageStat.html) — histogram for density math
- [colorthief PyPI](https://pypi.org/project/colorthief/) — v0.2.1, 2017 (ABANDONED — do not use)
- Repo source files (read this session):
  - `/home/hoyack/work/autocreative/CLAUDE.md`
  - `/home/hoyack/work/autocreative/HANDOFF.md` §7, §8
  - `/home/hoyack/work/autocreative/.planning/ROADMAP.md`
  - `/home/hoyack/work/autocreative/pyproject.toml`
  - `/home/hoyack/work/autocreative/.gitignore`
  - `/home/hoyack/work/autocreative/.planning/config.json`
  - `/home/hoyack/work/autocreative/flyer_generator/brochure/schema_renderer/schema_model.py`
  - `/home/hoyack/work/autocreative/flyer_generator/brochure/schema_renderer/renderer.py`
  - `/home/hoyack/work/autocreative/flyer_generator/brochure/schema_renderer/text_fit.py`
  - `/home/hoyack/work/autocreative/flyer_generator/brochure/schema_renderer/text_gen.py`
  - `/home/hoyack/work/autocreative/flyer_generator/brochure/schema_renderer/__main__.py`
  - `/home/hoyack/work/autocreative/flyer_generator/brochure/schema_renderer/image_gate.py`
  - `/home/hoyack/work/autocreative/flyer_generator/config.py`
  - `/home/hoyack/work/autocreative/flyer_generator/brochure/schemas/editorial_classic.json`
  - `/home/hoyack/work/autocreative/tests/brochure/schema_renderer/test_image_gate.py`

### Secondary (MEDIUM confidence — verified via authoritative but non-official sources)

- [pytest-playwright-async PyPI](https://pypi.org/project/pytest_playwright_async/) — fixture patterns for async tests
- [Qxf2 asynchronous Playwright + pytest](https://qxf2.com/blog/creating-asynchronous-automation-test-using-playwright-pytest/) — coroutine fixture approach
- [Quantize image methods benchmark (GitHub Chadys)](https://github.com/Chadys/QuantizeImageMethods) — relative speed of median-cut vs k-means
- [GitHub ZugBahnHof/color-contrast](https://github.com/ZugBahnHof/color-contrast) — prior-art for Python WCAG 2.1 + contrast modulation

### Tertiary (LOW confidence — flagged for validation during implementation)

- Exact remediation behavior of `coloraide.Color.interpolate()` when a contrast constraint is attached — check coloraide docs during implementation; may replace hand-rolled binary search.
- Whether `wait_until="networkidle"` is reliable for > 90% of marketing sites — validate empirically against shrubnet.com during first smoke test.

---

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — every package version verified against PyPI this session; Playwright async/BS4/tinycss2/wcag-contrast-ratio/coloraide/Pillow all confirmed current
- Architecture: **HIGH** — all integration points (TemplateSchema, render_schema_brochure, text_gen, image_gate) read in full; renderer already supports `accent_override` + `logo_bytes` so no signature changes required
- Contrast math: **HIGH** — wcag-contrast-ratio API verified (float tuples 0.0-1.0); coloraide `Color.contrast()` verified
- Pitfalls: **MEDIUM-HIGH** — pitfalls 1-4 and 7 are well-understood; pitfalls 5 (size uplift regression) and 6 (hero-dominated palette) require live calibration during implementation
- Whitespace density: **MEDIUM** — approach is sound; exact thresholds must be calibrated against shrubnet-v9 and the 78-cell gallery, not set a priori
- Typography uplift: **MEDIUM** — safer path (runtime `size_multiplier`) identified; actual baseline bump values need measurement against gallery

**Research date:** 2026-04-20
**Valid until:** 2026-07-20 (3 months — all libraries are actively released; Playwright in particular ships monthly)
