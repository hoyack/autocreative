"""Brand-kit scraper orchestrator.

Primary path: Playwright (scraper_playwright.py).
Fallback: httpx + BS4 + tinycss2 (scraper_bs4.py).

Both paths are wrapped in SSRF gating + logo-URL path-traversal guards.
Everything the scraper cannot confidently extract stays `None` on the
resulting `BrandKit` -- partial kits are the expected norm.

The orchestrator writes `brand.json`, `source/rendered.html` (+ screenshot
if Playwright ran), and `logos/*` under `<kit_dir>/`. Use `save_brand_kit`
from storage.py for `brand.json` (reuses slug + containment validation).

**W13:** One BoundLogger is created at entry
(`logger.bind(trace_id=..., slug=..., url=...)`) and passed to every
scraper helper so downstream log records share the trace context.
"""

from __future__ import annotations

import ipaddress
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
import structlog

from flyer_generator.brand_kit.models import (
    BrandKit,
    BrandLogo,
    BrandPalette,
    BrandPhotoHints,
    BrandTypography,
    ColorUsage,
)
from flyer_generator.brand_kit.palette import extract_palette
from flyer_generator.brand_kit.scraper_bs4 import BS4Artifacts, scrape_bs4
from flyer_generator.brand_kit.scraper_playwright import (
    PlaywrightArtifacts,
    scrape_with_playwright,
)
from flyer_generator.brand_kit.storage import resolve_kit_dir, save_brand_kit
from flyer_generator.errors import BrandKitScrapeError

logger = structlog.get_logger()

_ALLOWED_SCHEMES = {"http", "https"}
_MAX_ASSET_BYTES = 20 * 1024 * 1024
_MAX_TOTAL_BYTES = 50 * 1024 * 1024
_SAFE_FILENAME_RE = re.compile(r"[^a-zA-Z0-9._-]+")


# ---- SSRF gating --------------------------------------------------------


def _is_safe_url(url: str) -> tuple[bool, str]:
    """Return (ok, reason).

    Exported so `scraper_bs4.scrape_bs4` can call it on stylesheet URLs
    (W8 -- lazy-imported inside that function to avoid a module cycle
    with this file).

    Rejects: unparseable URLs, non-http(s) schemes, missing hosts,
    localhost, loopback/link-local/private/multicast/reserved IPs.
    Hostnames (not IPs) pass through so DNS resolution happens at
    request time -- the caller layers httpx on top of this gate.
    """
    try:
        parsed = urlparse(url)
    except Exception as err:  # noqa: BLE001
        return False, f"unparseable: {err}"
    if parsed.scheme not in _ALLOWED_SCHEMES:
        return False, f"scheme {parsed.scheme!r} not in {sorted(_ALLOWED_SCHEMES)}"
    host = parsed.hostname or ""
    if not host:
        return False, "missing host"
    if host.lower() in ("localhost", "localhost.localdomain"):
        return False, "localhost blocked"
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return True, ""  # hostname form -- let DNS resolve
    if (
        addr.is_loopback
        or addr.is_link_local
        or addr.is_private
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    ):
        return False, f"ip {host} is loopback/private/link-local/etc."
    return True, ""


# ---- Logo sanitization --------------------------------------------------


def _safe_logo_filename(url: str, fallback: str) -> str:
    try:
        name = Path(urlparse(url).path).name or fallback
    except Exception:  # noqa: BLE001
        name = fallback
    sanitized = _SAFE_FILENAME_RE.sub("_", name).strip("_.")
    if not sanitized:
        sanitized = fallback
    return sanitized[:128]


async def _download_logo(
    url: str,
    dest: Path,
    *,
    http_client: httpx.AsyncClient,
    log: "structlog.stdlib.BoundLogger",
) -> BrandLogo | None:
    """Download a single logo; returns BrandLogo on success, None on skip.

    W9: the write target is validated with `resolve() + relative_to(parent)`
    so a crafted dest (`../etc/bad.png`) aborts the write BEFORE any fetch.
    """
    # W9: containment guard BEFORE issuing any request
    try:
        target = dest.resolve()
        parent = dest.parent.resolve()
        target.relative_to(parent)
    except ValueError:
        log.warning(
            "logo_path_traversal_blocked_before_fetch",
            url=url,
            dest=str(dest),
        )
        return None

    try:
        resp = await http_client.get(url, timeout=60.0)
        if resp.status_code != 200:
            log.warning("logo_fetch_bad_status", url=url, status=resp.status_code)
            return None
        content = resp.content
        if len(content) > _MAX_ASSET_BYTES:
            log.warning("logo_too_large", url=url, bytes=len(content))
            return None
    except Exception as err:  # noqa: BLE001
        log.warning("logo_fetch_error", url=url, error=str(err))
        return None

    # W9: re-verify after download (race-free)
    try:
        target = dest.resolve()
        parent = dest.parent.resolve()
        target.relative_to(parent)
    except ValueError:
        log.warning("logo_path_traversal_blocked", url=url, target=str(target))
        return None

    dest.write_bytes(content)

    # Heuristic format detection
    fmt: str
    if (
        url.lower().endswith(".svg")
        or content[:4] == b"<svg"
        or b"<svg " in content[:128]
    ):
        fmt = "svg"
    elif content[:3] == b"\xff\xd8\xff":
        fmt = "jpg"
    elif content[:8] == b"\x89PNG\r\n\x1a\n":
        fmt = "png"
    else:
        fmt = "png"

    return BrandLogo(
        path=f"logos/{dest.name}",
        variant="primary",
        format=fmt,  # type: ignore[arg-type]
        aspect_ratio=1.0,
    )


# ---- Artifact merging ---------------------------------------------------


def _bs4_to_palette(artifacts: BS4Artifacts) -> BrandPalette | None:
    vars_ = artifacts.css_color_vars
    if not vars_:
        return None

    def _pick(keys: list[str]) -> str | None:
        for k in keys:
            for vk, vv in vars_.items():
                if k in vk.lower():
                    return vv
        return None

    primary = _pick(["primary", "accent", "brand"]) or "#000000"
    secondary = _pick(["secondary"]) or primary
    neutral_dark = _pick(["dark", "black", "neutral-dark"]) or "#1A1A1A"
    neutral_light = (
        _pick(["light", "white", "bg", "background", "neutral-light"]) or "#FAFAF7"
    )
    try:
        return BrandPalette(
            primary=ColorUsage(hex=primary, usage_hint="primary (from CSS var)"),
            secondary=ColorUsage(hex=secondary, usage_hint="secondary (heuristic)"),
            accent=ColorUsage(hex=primary, usage_hint="accent (copied from primary)"),
            neutral_dark=ColorUsage(hex=neutral_dark),
            neutral_light=ColorUsage(hex=neutral_light),
            extras={},
        )
    except Exception:  # noqa: BLE001
        return None


def _palette_from_screenshot(
    screenshot: bytes, log: "structlog.stdlib.BoundLogger"
) -> BrandPalette | None:
    try:
        top = extract_palette(screenshot, n_colors=5)
    except Exception as err:  # noqa: BLE001
        log.warning("palette_extract_error", error=str(err))
        return None
    if len(top) < 2:
        return None
    hexes = [h for h, _ in top[:5]]
    pad = "#808080"
    hexes += [pad] * (5 - len(hexes))
    try:
        return BrandPalette(
            primary=ColorUsage(hex=hexes[0], usage_hint="primary (screenshot top-1)"),
            secondary=ColorUsage(
                hex=hexes[1], usage_hint="secondary (screenshot top-2)"
            ),
            accent=ColorUsage(hex=hexes[2], usage_hint="accent (screenshot top-3)"),
            neutral_dark=ColorUsage(hex=hexes[3]),
            neutral_light=ColorUsage(hex=hexes[4]),
            extras={},
        )
    except Exception as err:  # noqa: BLE001
        log.warning("palette_build_error", error=str(err))
        return None


def _typography_from_computed(
    computed: dict[str, object] | None,
    font_urls: list[str],
) -> BrandTypography | None:
    if not computed:
        return None
    body = computed.get("body") if isinstance(computed, dict) else None
    h1 = computed.get("h1") if isinstance(computed, dict) else None
    heading_family = None
    body_family = None
    if isinstance(h1, dict):
        heading_family = h1.get("fontFamily")
    if isinstance(body, dict):
        body_family = body.get("fontFamily")
    if not heading_family and not body_family:
        return None
    return BrandTypography(
        heading_family=str(heading_family) if heading_family else "sans-serif",
        body_family=str(body_family) if body_family else "sans-serif",
        size_scale={},
        font_sources=list(font_urls),
    )


# ---- Orchestrator -------------------------------------------------------


async def fetch_brand_kit(
    url: str,
    slug: str,
    *,
    http_client: httpx.AsyncClient | None = None,
    base_dir: Path | None = None,
    force: bool = False,
) -> BrandKit:
    """Scrape `url` into a `BrandKit` and persist under `.brand-kits/<slug>/`.

    Playwright primary -> BS4 fallback. SSRF-gates the initial URL and
    every logo URL; delegates stylesheet SSRF gating to `scrape_bs4`
    (W8). Writes `brand.json`, `source/rendered.html` (+ screenshot if
    Playwright ran), and `logos/<file>` under the kit dir.

    Raises `BrandKitScrapeError` on SSRF violation (input URL) or when
    both scraper paths fail to yield any usable data.
    """
    trace_id = uuid.uuid4().hex
    log = logger.bind(trace_id=trace_id, slug=slug, url=url)  # W13
    log.info("brand_kit_fetch_start")

    ok, reason = _is_safe_url(url)
    if not ok:
        raise BrandKitScrapeError(
            "url blocked by SSRF policy",
            trace_id=trace_id,
            url=url,
            reason=reason,
        )

    kit_dir = resolve_kit_dir(slug, base_dir=base_dir)
    kit_dir.mkdir(parents=True, exist_ok=True)
    (kit_dir / "logos").mkdir(parents=True, exist_ok=True)
    (kit_dir / "source").mkdir(parents=True, exist_ok=True)

    _owns_http = False
    if http_client is None:
        http_client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=180.0,
            headers={"User-Agent": "flyer-generator-brand-kit/1.0"},
        )
        _owns_http = True

    try:
        pw_err: str | None = None
        pw: PlaywrightArtifacts | None = None
        try:
            pw = await scrape_with_playwright(url, log=log)  # W13
        except Exception as err:  # noqa: BLE001
            pw_err = str(err)[:200]
            log.warning("brand_kit_playwright_exception", error=pw_err)

        bs4: BS4Artifacts | None = None
        bs4_err: str | None = None
        try:
            bs4 = await scrape_bs4(url, http_client=http_client, log=log)  # W13
        except Exception as err:  # noqa: BLE001
            bs4_err = str(err)[:200]
            log.warning("brand_kit_bs4_exception", error=bs4_err)

        if pw is None and bs4 is None:
            raise BrandKitScrapeError(
                "both playwright and bs4 scraping failed",
                trace_id=trace_id,
                url=url,
                playwright_error=pw_err or "launch failed",
                bs4_error=bs4_err or "fetch failed",
            )

        source_artifacts: list[str] = []
        if pw is not None:
            (kit_dir / "source" / "screenshot.png").write_bytes(pw.screenshot)
            source_artifacts.append("source/screenshot.png")
            (kit_dir / "source" / "rendered.html").write_text(
                pw.rendered_html, encoding="utf-8"
            )
            source_artifacts.append("source/rendered.html")
        elif bs4 is not None:
            (kit_dir / "source" / "rendered.html").write_text(
                bs4.html, encoding="utf-8"
            )
            source_artifacts.append("source/rendered.html")

        palette: BrandPalette | None = None
        if pw is not None:
            palette = _palette_from_screenshot(pw.screenshot, log)
        if palette is None and bs4 is not None:
            palette = _bs4_to_palette(bs4)

        computed = pw.computed if pw is not None else None
        font_urls = (
            (pw.stylesheet_urls if pw is not None else [])
            + (bs4.font_urls if bs4 is not None else [])
        )
        typography = _typography_from_computed(computed, font_urls)

        logos: list[BrandLogo] = []
        total_bytes = 0
        candidate_urls: list[str] = []
        if pw is not None:
            candidate_urls += pw.logo_urls
        if bs4 is not None:
            candidate_urls += bs4.logo_urls
        seen: set[str] = set()
        for raw in candidate_urls:
            if raw in seen:
                continue
            seen.add(raw)
            if len(logos) >= 3:
                break
            full_url = urljoin(url, raw)
            ok, reason = _is_safe_url(full_url)
            if not ok:
                log.warning("logo_url_unsafe", url=full_url, reason=reason)
                continue
            if total_bytes >= _MAX_TOTAL_BYTES:
                log.warning("logo_total_budget_exhausted", total_bytes=total_bytes)
                break
            filename = _safe_logo_filename(
                full_url, fallback=f"logo_{len(logos)}.png"
            )
            dest = kit_dir / "logos" / filename
            lg = await _download_logo(
                full_url, dest, http_client=http_client, log=log
            )
            if lg is not None:
                logos.append(lg)
                if dest.resolve().exists():
                    total_bytes += dest.stat().st_size

        title = ""
        if bs4 is not None:
            title = bs4.title
        if not title and pw is not None:
            m = re.search(
                r"<title[^>]*>([^<]+)</title>", pw.rendered_html, re.IGNORECASE
            )
            if m:
                title = m.group(1).strip()
        if not title:
            title = urlparse(url).hostname or "unknown"

        kit = BrandKit(
            name=title,
            source_url=url,
            fetched_at=datetime.now(timezone.utc),
            palette=palette,
            typography=typography,
            logos=logos,
            voice=None,
            photography=BrandPhotoHints(),
            source_artifacts=source_artifacts,
            size_multiplier=1.0,
        )

        save_brand_kit(kit, slug, base_dir=base_dir)
        log.info(
            "brand_kit_fetch_done",
            has_palette=palette is not None,
            has_typography=typography is not None,
            n_logos=len(logos),
        )
        return kit
    finally:
        if _owns_http and http_client is not None:
            await http_client.aclose()
