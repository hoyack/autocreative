"""BS4 fallback scraper tests via respx.

Direct-module imports only (B1). Includes W8 coverage: stylesheet URLs
pointing to SSRF targets must be skipped BEFORE the GET issues."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from flyer_generator.brand_kit.scraper_bs4 import scrape_bs4
from flyer_generator.errors import BrandKitScrapeError

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@respx.mock
async def test_bs4_happy_path() -> None:
    html = (FIXTURE_DIR / "sample_site.html").read_text()
    css = (FIXTURE_DIR / "sample_site.css").read_text()
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=html))
    respx.get("https://example.com/style.css").mock(
        return_value=httpx.Response(200, text=css)
    )

    artifacts = await scrape_bs4("https://example.com/")

    assert artifacts.title == "Acme Widgets"
    assert artifacts.h1 == "Welcome to Acme"
    assert any("/assets/logo.png" in u for u in artifacts.logo_urls)
    assert "https://example.com/style.css" in artifacts.stylesheet_urls
    assert any("playfair-display.woff2" in u for u in artifacts.font_urls)
    assert artifacts.css_color_vars.get("--brand-primary") == "#1E3A5F"


@respx.mock
async def test_bs4_500_on_html_raises_scrape_error() -> None:
    respx.get("https://broken.example.com/").mock(return_value=httpx.Response(500))
    with pytest.raises(BrandKitScrapeError):
        await scrape_bs4("https://broken.example.com/")


@respx.mock
async def test_bs4_css_500_is_skipped_not_fatal() -> None:
    html = (FIXTURE_DIR / "sample_site.html").read_text()
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=html))
    respx.get("https://example.com/style.css").mock(return_value=httpx.Response(500))

    artifacts = await scrape_bs4("https://example.com/")
    # CSS failed -> font_urls + css_color_vars empty, but scrape still succeeds
    assert artifacts.font_urls == []
    assert artifacts.css_color_vars == {}
    assert artifacts.title == "Acme Widgets"


@respx.mock
async def test_bs4_no_logos_returns_empty_list() -> None:
    html = "<html><body><h1>No logos here</h1></body></html>"
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=html))
    artifacts = await scrape_bs4("https://example.com/")
    assert artifacts.logo_urls == []


@respx.mock
async def test_bs4_ssrf_css_url_is_skipped_before_get() -> None:
    """W8: a stylesheet URL resolving to a private IP must be skipped
    BEFORE the follow-up httpx.get -- no request is issued."""
    # HTML links to a CSS URL that points at 127.0.0.1
    html = (
        '<html><head><title>X</title>'
        '<link rel="stylesheet" href="http://127.0.0.1/malicious.css">'
        '</head><body><h1>Hi</h1></body></html>'
    )
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=html))
    # Also register a route for the bad URL -- if it were hit, we'd know.
    bad_route = respx.get("http://127.0.0.1/malicious.css").mock(
        return_value=httpx.Response(200, text=":root { --pwned: #000; }")
    )

    artifacts = await scrape_bs4("https://example.com/")

    assert "http://127.0.0.1/malicious.css" in artifacts.stylesheet_urls
    assert artifacts.css_color_vars == {}  # nothing parsed -- it was skipped
    assert bad_route.call_count == 0, "SSRF guard failed: private IP was fetched"
