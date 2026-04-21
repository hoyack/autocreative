"""Playwright scraper tests: mock the entire Playwright API surface.

No Chromium binary is required -- every call is stubbed via AsyncMock.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from flyer_generator.brand_kit.scraper_playwright import (
    PlaywrightArtifacts,
    scrape_with_playwright,
)


def _mock_playwright(
    html: str = "<html><body><h1>X</h1></body></html>",
    screenshot: bytes = b"\x89PNG-fake",
    computed: dict[str, object] | None = None,
    stylesheets: list[str] | None = None,
    logos: list[str] | None = None,
) -> MagicMock:
    """Build a chain of AsyncMock/MagicMock matching playwright.async_api."""
    if computed is None:
        computed = {
            "body": {"fontFamily": "Inter, sans-serif"},
            "h1": {"fontFamily": "Playfair, serif"},
            "h2": None,
        }
    if stylesheets is None:
        stylesheets = ["https://cdn.example.com/style.css"]
    if logos is None:
        logos = ["https://cdn.example.com/logo.png"]

    fake_page = MagicMock()
    fake_page.goto = AsyncMock()
    fake_page.wait_for_timeout = AsyncMock()
    fake_page.screenshot = AsyncMock(return_value=screenshot)
    fake_page.content = AsyncMock(return_value=html)
    fake_page.evaluate = AsyncMock(side_effect=[computed, stylesheets, logos])

    fake_context = MagicMock()
    fake_context.new_page = AsyncMock(return_value=fake_page)

    fake_browser = MagicMock()
    fake_browser.new_context = AsyncMock(return_value=fake_context)
    fake_browser.close = AsyncMock()

    fake_pw = MagicMock()
    fake_pw.chromium.launch = AsyncMock(return_value=fake_browser)

    fake_cm = MagicMock()
    fake_cm.__aenter__ = AsyncMock(return_value=fake_pw)
    fake_cm.__aexit__ = AsyncMock(return_value=None)

    return fake_cm


async def test_playwright_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_cm = _mock_playwright()
    monkeypatch.setattr(
        "flyer_generator.brand_kit.scraper_playwright.async_playwright",
        lambda: fake_cm,
        raising=False,
    )
    artifacts = await scrape_with_playwright("https://example.com")
    assert isinstance(artifacts, PlaywrightArtifacts)
    assert artifacts.screenshot == b"\x89PNG-fake"
    assert "<h1>" in artifacts.rendered_html.lower()
    assert artifacts.stylesheet_urls == ["https://cdn.example.com/style.css"]
    assert artifacts.logo_urls == ["https://cdn.example.com/logo.png"]


async def test_playwright_launch_failure_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_cm = MagicMock()
    fake_pw = MagicMock()
    fake_pw.chromium.launch = AsyncMock(side_effect=Exception("chromium not installed"))
    fake_cm.__aenter__ = AsyncMock(return_value=fake_pw)
    fake_cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "flyer_generator.brand_kit.scraper_playwright.async_playwright",
        lambda: fake_cm,
        raising=False,
    )
    result = await scrape_with_playwright("https://example.com")
    assert result is None


async def test_playwright_goto_timeout_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_page = MagicMock()
    fake_page.goto = AsyncMock(side_effect=Exception("Timeout 30000ms exceeded"))

    fake_context = MagicMock()
    fake_context.new_page = AsyncMock(return_value=fake_page)

    fake_browser = MagicMock()
    fake_browser.new_context = AsyncMock(return_value=fake_context)
    fake_browser.close = AsyncMock()

    fake_pw = MagicMock()
    fake_pw.chromium.launch = AsyncMock(return_value=fake_browser)

    fake_cm = MagicMock()
    fake_cm.__aenter__ = AsyncMock(return_value=fake_pw)
    fake_cm.__aexit__ = AsyncMock(return_value=None)

    monkeypatch.setattr(
        "flyer_generator.brand_kit.scraper_playwright.async_playwright",
        lambda: fake_cm,
        raising=False,
    )
    result = await scrape_with_playwright("https://slow.example.com", timeout_ms=100)
    assert result is None


async def test_playwright_uses_wait_until_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pitfall 3 mitigation: must NOT use networkidle (hangs on analytics sites)."""
    fake_cm = _mock_playwright()
    monkeypatch.setattr(
        "flyer_generator.brand_kit.scraper_playwright.async_playwright",
        lambda: fake_cm,
        raising=False,
    )
    await scrape_with_playwright("https://example.com")
    pw = fake_cm.__aenter__.return_value
    browser = pw.chromium.launch.return_value
    ctx = browser.new_context.return_value
    page = ctx.new_page.return_value
    goto_call = page.goto.call_args
    assert goto_call is not None
    assert goto_call.kwargs.get("wait_until") == "load"
