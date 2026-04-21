"""Playwright-backed primary scraper. Isolated from scraper.py so tests
that don't need Chromium never import Playwright.

Returns `None` (not raise) when Chromium cannot launch -- caller falls
back to BS4. **W13:** accepts optional `log: BoundLogger` kwarg from the
orchestrator for trace_id propagation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger()


# Module-level name kept as None so tests can monkeypatch it without
# the real playwright package installed. The scrape function does the
# real lazy import inside its body (so the import cost only hits when
# a caller actually uses the primary path) and binds the result back
# onto the module so subsequent calls skip the re-import.
async_playwright = None  # type: ignore[assignment]


@dataclass(frozen=True)
class PlaywrightArtifacts:
    screenshot: bytes
    rendered_html: str
    computed: dict[str, object] = field(default_factory=dict)
    stylesheet_urls: list[str] = field(default_factory=list)
    logo_urls: list[str] = field(default_factory=list)


_COMPUTED_JS = """() => {
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
    h1: pick('h1'),
    h2: pick('h2'),
  };
}"""

_STYLESHEETS_JS = """() => {
  return Array.from(document.styleSheets).map(s => s.href).filter(Boolean);
}"""

_LOGOS_JS = """() => {
  const hdr = document.querySelector('header') || document.body;
  const imgs = Array.from(hdr.querySelectorAll('img'));
  return imgs
    .filter(i => /logo/i.test((i.className || '') + ' ' + (i.alt || '') + ' ' + (i.src || '')))
    .map(i => i.src);
}"""


async def scrape_with_playwright(
    url: str,
    *,
    timeout_ms: int = 30_000,
    log: "structlog.stdlib.BoundLogger | None" = None,
) -> PlaywrightArtifacts | None:
    """Return artifacts, or None if Playwright/Chromium fails to launch.

    Uses `wait_until="load"` (Pitfall 3: `networkidle` hangs on
    analytics-heavy sites). Every failure mode returns None instead of
    raising so the orchestrator can fall through to BS4.
    """
    if log is None:
        log = logger.bind(scraper="playwright", url=url)

    # Read the module-level `async_playwright` first so tests that
    # monkeypatch it get their stub without hitting the real import.
    # On a real install where the name is still None (module was just
    # imported), do the lazy import inside the function and cache it
    # on the module for subsequent calls.
    pw_factory = async_playwright
    if pw_factory is None:
        try:
            from playwright.async_api import async_playwright as _pw  # noqa: PLC0415
        except ImportError as err:
            log.warning("brand_kit_playwright_import_failed", error=str(err))
            return None
        globals()["async_playwright"] = _pw
        pw_factory = _pw

    try:
        async with pw_factory() as p:
            try:
                browser = await p.chromium.launch(headless=True)
            except Exception as err:  # noqa: BLE001
                log.warning(
                    "brand_kit_playwright_launch_failed", error=str(err)[:200]
                )
                return None
            try:
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent=(
                        "Mozilla/5.0 (compatible; flyer-generator-brand-kit/1.0)"
                    ),
                )
                page = await context.new_page()
                try:
                    await page.goto(url, wait_until="load", timeout=timeout_ms)
                except Exception as err:  # noqa: BLE001
                    log.warning(
                        "brand_kit_playwright_goto_failed",
                        error=str(err)[:200],
                    )
                    return None
                try:
                    await page.wait_for_timeout(2000)  # let fonts/CSS settle
                except Exception:  # noqa: BLE001
                    pass

                screenshot_bytes = await page.screenshot(
                    full_page=False, type="png"
                )
                html = await page.content()
                computed = await page.evaluate(_COMPUTED_JS)
                stylesheets = await page.evaluate(_STYLESHEETS_JS)
                logos = await page.evaluate(_LOGOS_JS)

                return PlaywrightArtifacts(
                    screenshot=screenshot_bytes,
                    rendered_html=html,
                    computed=computed or {},
                    stylesheet_urls=list(stylesheets or []),
                    logo_urls=list(logos or []),
                )
            finally:
                await browser.close()
    except Exception as err:  # noqa: BLE001 - scraper must never abort orchestrator
        log.warning("brand_kit_playwright_failed", error=str(err)[:200])
        return None
