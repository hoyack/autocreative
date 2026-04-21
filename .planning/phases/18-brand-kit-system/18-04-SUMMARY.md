---
phase: 18-brand-kit-system
plan: 04
subsystem: brand_kit/scraper
tags: [brand-kit, scraper, playwright, bs4, async, httpx, ssrf, path-traversal]

dependency-graph:
  requires:
    - flyer_generator/brand_kit/models.py (Plan 02 -- BrandKit, BrandPalette, BrandLogo, etc.)
    - flyer_generator/brand_kit/storage.py (Plan 01 -- resolve_kit_dir, save_brand_kit)
    - flyer_generator/errors.py (Plan 01 -- BrandKitScrapeError)
    - flyer_generator/config.py (Plan 01 -- Settings.brand_kits_dir)
  provides:
    - flyer_generator.brand_kit.palette.extract_palette
    - flyer_generator.brand_kit.scraper.fetch_brand_kit
    - flyer_generator.brand_kit.scraper._is_safe_url
    - flyer_generator.brand_kit.scraper_bs4.scrape_bs4
    - flyer_generator.brand_kit.scraper_bs4.BS4Artifacts
    - flyer_generator.brand_kit.scraper_playwright.scrape_with_playwright
    - flyer_generator.brand_kit.scraper_playwright.PlaywrightArtifacts
  affects:
    - None (purely additive; no existing modules modified)

tech-stack:
  added:
    - beautifulsoup4>=4.14 (already declared in pyproject; installed into venv)
  patterns:
    - httpx.AsyncClient(timeout=180.0) + _owns_http ownership flag + finally aclose()
    - structlog.get_logger().bind(trace_id=...) at orchestrator boundary, propagated via log kwarg
    - Retry-style "continue, not break" on transient per-asset errors
    - Module-level lazy import + monkey-patchable reference (async_playwright pattern)
    - Pydantic v2 BrandKit with Optional nested models for partial-scrape round-trip
    - Pillow Image.quantize(MEDIANCUT) palette extraction (no sklearn/numpy/colorthief)

key-files:
  created:
    - flyer_generator/brand_kit/palette.py (40 lines)
    - flyer_generator/brand_kit/scraper.py (400+ lines, orchestrator)
    - flyer_generator/brand_kit/scraper_bs4.py (195 lines, fallback)
    - flyer_generator/brand_kit/scraper_playwright.py (140 lines, primary)
    - tests/brand_kit/fixtures/__init__.py
    - tests/brand_kit/fixtures/sample_site.html
    - tests/brand_kit/fixtures/sample_site.css
    - tests/brand_kit/fixtures/sample_logo.png
    - tests/brand_kit/test_palette.py (4 tests)
    - tests/brand_kit/test_scraper_bs4.py (5 tests)
    - tests/brand_kit/test_scraper_playwright.py (4 tests)
    - tests/brand_kit/test_scraper.py (13 tests)
  modified:
    - None (scraper.py was created in two passes: Task 2 shim -> Task 4 full orchestrator)

decisions:
  - "Put _is_safe_url in scraper.py (not scraper_ssrf.py); scraper_bs4.py imports it lazily inside the function to break the module-load cycle."
  - "Pillow Image.quantize MEDIANCUT preferred over MAXCOVERAGE: median-cut picks perceptually distinct colors (right heuristic for brand kits) while MAXCOVERAGE flattens toward high-pixel-count neutrals."
  - "scraper_playwright.async_playwright is a module-level name (None when playwright is not installed); the scrape function does the real `from playwright.async_api import async_playwright` lazy import inside its body and caches the result onto the module. This satisfies both (a) the `lazy-imported inside the function` acceptance criterion and (b) test-monkey-patchability without requiring the playwright package in CI."
  - "Logo aspect_ratio is stubbed to 1.0 in _download_logo -- proper aspect computation requires Pillow open + image mode inspection, deferred until applier (Plan 05) actually reads it."
  - "BS4 CSS-color-var heuristic mapping (primary/secondary/accent/neutral-dark/neutral-light) uses substring matching on custom-property names; this is intentionally permissive because real sites use inconsistent naming (`--brand-primary`, `--color-accent`, `--primary-500`)."

metrics:
  duration: "~11 min (19:34 -> 19:45)"
  completed: "2026-04-20"
  tasks: 4
  files_created: 12
  tests_added: 26 (4 palette + 5 BS4 + 4 Playwright + 13 scraper)
  tests_total_after: 753 (all pass; 0 regressions)
  commits: 4
---

# Phase 18 Plan 04: Scraper Subsystem Summary

Three-module brand-kit scraper (Playwright primary -> BS4 fallback) with SSRF + logo path-traversal + asset-size mitigations and pure-Pillow palette extraction, tested end-to-end without requiring a Chromium binary in CI.

## One-liner

Async `fetch_brand_kit(url, slug)` that scrapes a website into a Pydantic `BrandKit` (palette + typography + logos), writes it under `.brand-kits/<slug>/`, and returns partial kits (Optional fields = None) when any extraction step fails -- all behind a SSRF deny list plus a path-traversal containment guard.

## Architecture (three-file split)

```
flyer_generator/brand_kit/
  palette.py              -- extract_palette(png_bytes) via Pillow Image.quantize MEDIANCUT
  scraper_bs4.py          -- pure httpx + BeautifulSoup4 + tinycss2 fallback
  scraper_playwright.py   -- headless Chromium primary (graceful fallback to BS4 on any error)
  scraper.py              -- fetch_brand_kit orchestrator + SSRF gate + logo download
```

`scraper.py` owns `_is_safe_url` (the shared SSRF gate) and is the only entry point callers use. `scraper_bs4` lazily imports `_is_safe_url` inside its function body to break an import cycle. `scraper_playwright` keeps `async_playwright` as a module-level name (initially `None`) so tests can monkey-patch it without requiring the real playwright install; the function does the real lazy import on first non-patched use.

## Security Mitigations

### W8 - Stylesheet URL SSRF gate (`scraper_bs4.py`)

Every stylesheet URL discovered during BS4 parsing is passed through `_is_safe_url` BEFORE the follow-up `http_client.get(css_url, ...)`. Skipped URLs log `bs4_css_ssrf_blocked` with `ssrf_blocked=True` and continue processing the remaining stylesheets. Verified by `test_bs4_ssrf_css_url_is_skipped_before_get` which registers a respx route for `http://127.0.0.1/malicious.css` and asserts `bad_route.call_count == 0` after the scrape completes.

### W9 - Logo path-traversal guard (`scraper.py::_download_logo`)

`_download_logo` calls `dest.resolve().relative_to(dest.parent.resolve())` BEFORE any HTTP request; if the dest path contains `..` components that escape `kit_dir/logos/`, the function returns `None` and logs `logo_path_traversal_blocked_before_fetch` -- no fetch issued, no bytes written. A second check after download re-validates (race-free pattern). Directly exercised by `test_logo_download_rejects_traversal_path` which passes a crafted dest (`kit_dir / "logos" / ".." / ".." / "etc" / "bad.png"`) and a `_FakeClient.get` that raises `AssertionError` if called -- the test asserts both `result is None` AND the escape target `tmp_path / "etc" / "bad.png"` does not exist on disk.

### B6 - Multi-color screenshot fixture (`test_scraper.py::_multi_color_png_bytes`)

The happy-path test uses a four-quadrant PNG (top-left `#1E3A5F`, top-right `#BE1A1A`, bottom-left `#F0F0F0`, bottom-right `#282828`) so `_palette_from_screenshot` clears the `len(top) < 2` guard and returns a non-None palette even when the BS4 stub has `css_color_vars={}`. A solid-color fixture would have returned `None` from `extract_palette` and collapsed the palette-extraction assertion.

### W13 - BoundLogger propagation

The orchestrator creates exactly one `log = logger.bind(trace_id=uuid.uuid4().hex, slug=slug, url=url)` at entry and passes it to both scraper helpers:

```python
pw = await scrape_with_playwright(url, log=log)
bs4 = await scrape_bs4(url, http_client=http_client, log=log)
```

Both helpers accept `log: structlog.stdlib.BoundLogger | None = None` and fall back to their own module logger bindings when None. This keeps every structured-log record within a single `fetch_brand_kit` call tagged with the same `trace_id`, which matters when the primary path emits warnings, the fallback path emits warnings, and the orchestrator emits its `brand_kit_fetch_done` summary.

### SSRF deny list (STRIDE T-18-SCRAPER-01)

`_is_safe_url` rejects:
- Non-`http`/`https` schemes (file, ftp, javascript, data)
- Missing hostnames
- Case-insensitive `localhost` and `localhost.localdomain`
- IP literals matching any of: loopback (127/8, ::1), link-local (169.254/16 including the AWS/GCP metadata endpoint), private (10/8, 172.16/12, 192.168/16, fc00::/7), multicast, reserved, unspecified (0.0.0.0)

Hostname strings pass through the gate (DNS resolution happens at request time via httpx); a more aggressive DNS-resolve-and-re-check gate is deferred.

### Asset-size caps (STRIDE T-18-SCRAPER-02)

- 20 MB per-asset cap enforced on BS4 CSS fetches and logo downloads
- 50 MB per-kit total budget short-circuits the logo loop once exceeded
- 60s timeout per logo/CSS; 180s timeout on the initial HTML fetch (matches the image_gate convention for long-running ComfyCloud ops)

## BS4 Heuristic Palette Mapping

When Playwright is unavailable AND CSS custom properties exist, `_bs4_to_palette` maps CSS var names to palette roles using substring matching:

| Role          | Substring match keys (first hit wins)                                           |
| ------------- | ------------------------------------------------------------------------------- |
| primary       | `primary`, `accent`, `brand`                                                    |
| secondary     | `secondary` (falls back to primary's value)                                     |
| accent        | copied from primary                                                             |
| neutral_dark  | `dark`, `black`, `neutral-dark` (default `#1A1A1A`)                             |
| neutral_light | `light`, `white`, `bg`, `background`, `neutral-light` (default `#FAFAF7`)       |

This is intentionally permissive because real sites use `--brand-primary`, `--color-accent`, `--primary-500`, `--cta-color`, etc. with no consistent naming. When no custom vars exist, `_bs4_to_palette` returns `None` and the BrandKit palette field is left null.

## Direct-Module Import Strategy (B1)

Per the checker-iteration B1 constraint, **this plan does not touch `flyer_generator/brand_kit/__init__.py`.** Every test and every internal import uses direct-module paths:

```python
from flyer_generator.brand_kit.scraper import fetch_brand_kit
from flyer_generator.brand_kit.palette import extract_palette
from flyer_generator.brand_kit.scraper_bs4 import scrape_bs4, BS4Artifacts
from flyer_generator.brand_kit.scraper_playwright import scrape_with_playwright
```

Plan 07 will consolidate these into a single re-export block on `__init__.py`.

## TDD Gate Compliance

Each task committed as a single `feat(...)` commit (code + tests in one commit per task). All four task commits passed their verify steps locally (`pytest tests/brand_kit/test_*.py -q`) before progressing.

| Task | Commit   | Files                                                                       | Tests             |
| ---- | -------- | --------------------------------------------------------------------------- | ----------------- |
| 1    | f94c2b1  | palette.py, test_palette.py                                                 | 4 tests           |
| 2    | f0c81ab  | scraper.py (shim), scraper_bs4.py, fixtures/, test_scraper_bs4.py           | 5 tests           |
| 3    | 6bb37ae  | scraper_playwright.py, test_scraper_playwright.py                           | 4 tests           |
| 4    | 26c4020  | scraper.py (full), test_scraper.py                                          | 13 tests          |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed beautifulsoup4 into venv**
- **Found during:** Task 2 baseline check before writing scraper_bs4.py
- **Issue:** `python -c "import bs4"` failed in the project venv even though `beautifulsoup4>=4.14` is declared in `pyproject.toml` dependencies.
- **Fix:** Bootstrapped pip via `python -m ensurepip` (venv was missing pip) then ran `python -m pip install "beautifulsoup4>=4.14"`. No change to `pyproject.toml` -- the dependency was already declared correctly; the local venv was just out of sync. `uv` was unavailable and `pip install -e .[dev]` failed due to the build backend lacking PEP 660 (build_editable) support.
- **Files modified:** None committed (venv state only).
- **Commit:** N/A (environment fix).

**2. [Rule 1 - Bug] Playwright module-level lazy import to support test monkeypatching**
- **Found during:** Task 3 first `pytest` run
- **Issue:** The test file monkey-patches `flyer_generator.brand_kit.scraper_playwright.async_playwright`, but the original function had `from playwright.async_api import async_playwright` inline. With no real playwright package installed, that inline import raised `ImportError` before reaching the patched module attribute, so `test_playwright_happy_path` and `test_playwright_uses_wait_until_load` failed.
- **Fix:** Added a module-level `async_playwright = None` shim so tests can monkey-patch it. The scrape function reads the module-level name first, and only if still None does it attempt the real `from playwright.async_api import async_playwright` lazy import and cache the result back onto the module via `globals()["async_playwright"] = _pw`. Both acceptance criteria hold: (a) the real lazy `from ...import` stays inside the function body, (b) the grep for the import line still succeeds.
- **Files modified:** `flyer_generator/brand_kit/scraper_playwright.py`
- **Commit:** 6bb37ae (included in Task 3 commit -- discovered and fixed before commit)

**3. [Rule 3 - Blocking] Task 2 minimal scraper.py shim**
- **Found during:** Task 2 (scraper_bs4.py lazy-imports `_is_safe_url` from scraper.py)
- **Issue:** Plan sequences scraper.py in Task 4, but scraper_bs4 in Task 2 needs `_is_safe_url` for the W8 SSRF gate test (`test_bs4_ssrf_css_url_is_skipped_before_get`).
- **Fix:** Created a minimal `scraper.py` containing only `_is_safe_url` + `_ALLOWED_SCHEMES` + module docstring noting "Task 4 expands this" in the Task 2 commit. Task 4's commit overwrites the file with the full orchestrator, keeping `_is_safe_url` byte-identical.
- **Files modified:** `flyer_generator/brand_kit/scraper.py` (created Task 2, expanded Task 4)
- **Commits:** f0c81ab (shim), 26c4020 (full)

## Known TODOs (deferred)

- **Logo aspect_ratio stub:** `_download_logo` returns `BrandLogo(aspect_ratio=1.0, ...)` unconditionally. Proper aspect computation needs `PIL.Image.open(BytesIO(content)).size` -> `w / h`. Deferred until applier (Plan 05) actually consumes the field.
- **DNS-based SSRF check:** hostname-form URLs pass `_is_safe_url` without DNS resolution; a compromised DNS-rebinding attack could still resolve `evil.example.com` to `127.0.0.1` after the gate check. Full mitigation would require resolving the hostname first, validating the returned IP, then using a custom transport to pin that IP. Out of scope for Phase 18 (acceptable per threat model).
- **BrandKit palette role inference:** The BS4 heuristic (substring match on CSS var names) is a best-effort heuristic. A better approach would look at how each var is USED in declarations (`color:`, `background:`, `border-color:`) -- deferred as a future enhancement.

## Self-Check: PASSED

**Files created (verified on disk):**
- FOUND: `flyer_generator/brand_kit/palette.py`
- FOUND: `flyer_generator/brand_kit/scraper.py`
- FOUND: `flyer_generator/brand_kit/scraper_bs4.py`
- FOUND: `flyer_generator/brand_kit/scraper_playwright.py`
- FOUND: `tests/brand_kit/fixtures/__init__.py`
- FOUND: `tests/brand_kit/fixtures/sample_site.html`
- FOUND: `tests/brand_kit/fixtures/sample_site.css`
- FOUND: `tests/brand_kit/fixtures/sample_logo.png`
- FOUND: `tests/brand_kit/test_palette.py`
- FOUND: `tests/brand_kit/test_scraper_bs4.py`
- FOUND: `tests/brand_kit/test_scraper_playwright.py`
- FOUND: `tests/brand_kit/test_scraper.py`

**Commits (verified in git log):**
- FOUND: f94c2b1 (Task 1 -- palette)
- FOUND: f0c81ab (Task 2 -- BS4 scraper + scraper.py shim)
- FOUND: 6bb37ae (Task 3 -- Playwright scraper)
- FOUND: 26c4020 (Task 4 -- orchestrator + test_scraper.py)

**Constraints verified:**
- `flyer_generator/brand_kit/__init__.py` UNCHANGED vs. base 8c646d4 (B1)
- `pytest tests/brand_kit/ -q` -> 88 passed
- `pytest tests/ -q` -> 753 passed (0 regressions)
- `python -c "from flyer_generator.brand_kit.scraper import fetch_brand_kit; print('ok')"` -> ok
- SSRF test parametrized over 8 bad URLs (127.0.0.1, localhost, 169.254.169.254, 10.x, 192.168.x, file://, ftp://, javascript:)
- W8 test asserts zero httpx calls to the blocked URL
- W9 test asserts crafted dest with `..` returns None without issuing a fetch
- B6 test asserts kit.palette is not None when screenshot is multi-color
