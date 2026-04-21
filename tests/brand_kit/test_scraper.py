"""Orchestrator tests for fetch_brand_kit: SSRF, fallback, logo safety, traversal.

Direct-module imports only (B1). Includes:
- W9: a dedicated traversal test injecting a dest path with `..`
  components and asserting the containment guard skips the write.
- B6: the happy-path test uses a MULTI-COLOR screenshot (four quadrants)
  so `_palette_from_screenshot` returns non-None.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
import respx
from PIL import Image, ImageDraw

from flyer_generator.brand_kit.scraper import _download_logo, fetch_brand_kit
from flyer_generator.brand_kit.scraper_bs4 import BS4Artifacts
from flyer_generator.brand_kit.scraper_playwright import PlaywrightArtifacts
from flyer_generator.brand_kit.storage import load_brand_kit
from flyer_generator.errors import BrandKitScrapeError


def _multi_color_png_bytes() -> bytes:
    """B6: four-quadrant multi-color screenshot so palette extraction returns >=2 hexes."""
    img = Image.new("RGB", (64, 64), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 31, 31], fill=(30, 58, 95))      # #1E3A5F top-left
    d.rectangle([32, 0, 63, 31], fill=(190, 26, 26))    # #BE1A1A top-right
    d.rectangle([0, 32, 31, 63], fill=(240, 240, 240))  # #F0F0F0 bottom-left
    d.rectangle([32, 32, 63, 63], fill=(40, 40, 40))    # #282828 bottom-right
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---- SSRF gating --------------------------------------------------------


@pytest.mark.parametrize(
    "bad_url",
    [
        "http://127.0.0.1/",
        "http://localhost/",
        "http://169.254.169.254/",
        "http://10.0.0.1/",
        "http://192.168.1.1/",
        "file:///etc/passwd",
        "ftp://example.com/",
        "javascript:alert(1)",
    ],
)
async def test_ssrf_blocked(bad_url: str, tmp_path: Path) -> None:
    with pytest.raises(BrandKitScrapeError) as ei:
        await fetch_brand_kit(bad_url, "ssrf-test", base_dir=tmp_path)
    blob = str(ei.value).lower() + " " + str(ei.value.context.get("reason", "")).lower()
    assert (
        "scheme" in blob
        or "blocked" in blob
        or "ip " in blob
        or "loopback" in blob
        or "ssrf" in blob
        or "private" in blob
        or "missing host" in blob
    )


# ---- Fallback engagement ------------------------------------------------


@respx.mock
async def test_playwright_none_falls_through_to_bs4(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "flyer_generator.brand_kit.scraper.scrape_with_playwright",
        AsyncMock(return_value=None),
    )
    html = "<html><head><title>Acme</title></head><body><h1>Hello</h1></body></html>"
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=html))

    kit = await fetch_brand_kit(
        "https://example.com/", "fallback-kit", base_dir=tmp_path
    )
    assert kit.name == "Acme"
    assert kit.source_url == "https://example.com/"
    assert (tmp_path / "fallback-kit" / "brand.json").is_file()
    assert "source/rendered.html" in kit.source_artifacts

    reloaded = load_brand_kit("fallback-kit", base_dir=tmp_path)
    assert reloaded.name == "Acme"


@respx.mock
async def test_both_fail_raises_scrape_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "flyer_generator.brand_kit.scraper.scrape_with_playwright",
        AsyncMock(return_value=None),
    )
    respx.get("https://broken.example.com/").mock(return_value=httpx.Response(500))
    with pytest.raises(BrandKitScrapeError) as ei:
        await fetch_brand_kit("https://broken.example.com/", "x", base_dir=tmp_path)
    assert "playwright_error" in ei.value.context
    assert "bs4_error" in ei.value.context


# ---- Logo URL / traversal safety ---------------------------------------


@respx.mock
async def test_logo_traversal_skipped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """URL-level traversal: `../` in src is collapsed by urljoin, resulting URL is still
    scoped to https://example.com/. Kit dir must not contain escaped files."""
    monkeypatch.setattr(
        "flyer_generator.brand_kit.scraper.scrape_with_playwright",
        AsyncMock(return_value=None),
    )
    html = (
        '<html><body><img class="logo" src="../../../etc/passwd.png"></body></html>'
    )
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=html))
    respx.get("https://example.com/etc/passwd.png").mock(
        return_value=httpx.Response(404)
    )

    kit = await fetch_brand_kit(
        "https://example.com/", "logo-safe", base_dir=tmp_path
    )
    assert kit.logos == []
    base = (tmp_path / "logo-safe").resolve()
    for p in base.rglob("*"):
        assert base in p.resolve().parents or p.resolve() == base


async def test_logo_download_rejects_traversal_path(tmp_path: Path) -> None:
    """W9: calling `_download_logo` with a crafted dest path containing `..` MUST
    be rejected by the containment guard -- NO file is written outside kit_dir."""
    import structlog

    log = structlog.get_logger().bind(test="w9")
    kit_dir = tmp_path / "w9-kit"
    (kit_dir / "logos").mkdir(parents=True)
    # Crafted dest path with traversal component
    bad_dest = kit_dir / "logos" / ".." / ".." / "etc" / "bad.png"

    # Even if the HTTP response would be 200 with valid PNG bytes, the guard must
    # fire BEFORE any fetch. Pass a no-op client that would crash if called.
    async def _crash_get(*args, **kwargs):  # pragma: no cover
        raise AssertionError("guard should have fired before GET")

    class _FakeClient:
        async def get(self, *args, **kwargs):
            await _crash_get(*args, **kwargs)

    result = await _download_logo(
        "https://example.com/bad.png",
        bad_dest,
        http_client=_FakeClient(),  # type: ignore[arg-type]
        log=log,
    )
    assert result is None
    # Confirm nothing escaped kit_dir
    escape_target = tmp_path / "etc" / "bad.png"
    assert not escape_target.exists()


# ---- Happy path with playwright mock (B6: multi-color screenshot) ------


async def test_playwright_happy_path_writes_screenshot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """B6: use a MULTI-COLOR screenshot so `_palette_from_screenshot` clears the
    `len(top) < 2` guard and returns a non-None palette."""
    pw_artifacts = PlaywrightArtifacts(
        screenshot=_multi_color_png_bytes(),
        rendered_html=(
            "<html><head><title>Acme</title></head>"
            "<body><h1>Hi</h1></body></html>"
        ),
        computed={
            "body": {"fontFamily": "Inter, sans-serif"},
            "h1": {"fontFamily": "Playfair, serif"},
        },
        stylesheet_urls=[],
        logo_urls=[],
    )
    monkeypatch.setattr(
        "flyer_generator.brand_kit.scraper.scrape_with_playwright",
        AsyncMock(return_value=pw_artifacts),
    )
    monkeypatch.setattr(
        "flyer_generator.brand_kit.scraper.scrape_bs4",
        AsyncMock(
            return_value=BS4Artifacts(
                html=(
                    "<html><head><title>Acme</title></head><body></body></html>"
                ),
                title="Acme",
                h1="",
                logo_urls=[],
                stylesheet_urls=[],
                font_urls=[],
                css_color_vars={},  # empty -- palette must come from multi-color screenshot
                computed_body={},
            )
        ),
    )

    kit = await fetch_brand_kit("https://example.com", "happy", base_dir=tmp_path)
    assert (tmp_path / "happy" / "source" / "screenshot.png").is_file()
    assert (tmp_path / "happy" / "source" / "rendered.html").is_file()
    assert "source/screenshot.png" in kit.source_artifacts
    assert kit.palette is not None, (
        "B6: multi-color screenshot must yield a non-None palette"
    )
    assert kit.typography is not None
