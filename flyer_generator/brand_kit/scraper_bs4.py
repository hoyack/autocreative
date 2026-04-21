"""Pure-httpx + BeautifulSoup4 + tinycss2 scraper (fallback path).

Used when Playwright fails to launch (e.g. Chromium binary not installed
in CI). This path does NOT require a browser, so it's the test-harness
backbone -- every unit test exercises it with respx-mocked responses.

Design: deterministic I/O. Every external fetch is bounded by httpx
timeout (60.0s for CSS, 180.0s for the initial HTML). Every bytes
download is capped at 20 MB per asset. **W8:** stylesheet URLs are
SSRF-gated via `_is_safe_url` (imported lazily from scraper.py to
avoid an import cycle) BEFORE each follow-up GET. **W13:** accepts an
optional `log: structlog.stdlib.BoundLogger` kwarg so the orchestrator
can propagate its trace_id / slug bindings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

import httpx
import structlog
import tinycss2
from bs4 import BeautifulSoup

from flyer_generator.errors import BrandKitScrapeError

logger = structlog.get_logger()

_LOGO_RE = re.compile(r"logo", re.IGNORECASE)
_MAX_ASSET_BYTES = 20 * 1024 * 1024  # 20 MB per asset
_USER_AGENT = "flyer-generator-brand-kit/1.0 (+https://github.com/example)"


@dataclass(frozen=True)
class BS4Artifacts:
    """Everything the BS4 fallback could extract."""

    html: str
    title: str
    h1: str
    logo_urls: list[str] = field(default_factory=list)
    stylesheet_urls: list[str] = field(default_factory=list)
    font_urls: list[str] = field(default_factory=list)
    css_color_vars: dict[str, str] = field(default_factory=dict)
    computed_body: dict[str, str] = field(default_factory=dict)


async def scrape_bs4(
    url: str,
    *,
    http_client: httpx.AsyncClient | None = None,
    max_stylesheets: int = 5,
    log: "structlog.stdlib.BoundLogger | None" = None,
) -> BS4Artifacts:
    """Fetch + parse `url` via pure HTTP; caller is responsible for SSRF gating
    on the INITIAL URL. This function SSRF-gates each stylesheet URL before
    the follow-up GET (W8)."""
    # W8: lazy import to avoid cycle with scraper.py
    from flyer_generator.brand_kit.scraper import _is_safe_url  # noqa: PLC0415

    # W13: use caller's logger if provided; else bind our own
    if log is None:
        log = logger.bind(scraper="bs4", url=url)

    _owns_http = False
    if http_client is None:
        http_client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=180.0,
            headers={"User-Agent": _USER_AGENT},
        )
        _owns_http = True

    try:
        try:
            resp = await http_client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as err:
            raise BrandKitScrapeError(
                "bs4: HTML fetch failed",
                url=url,
                error=str(err),
            ) from err
        html = resp.text

        soup = BeautifulSoup(html, "html.parser")
        title = (soup.title.string.strip() if (soup.title and soup.title.string) else "")
        og = soup.find("meta", {"property": "og:site_name"})
        if og is not None and og.get("content"):
            title = str(og["content"]).strip()
        h1_tag = soup.find("h1")
        h1_text = h1_tag.get_text(strip=True) if h1_tag else ""

        logo_urls: list[str] = []
        for img in soup.find_all("img"):
            cls = img.get("class") or []
            cls_str = " ".join(cls) if isinstance(cls, list) else str(cls)
            haystack = " ".join([cls_str, str(img.get("alt", "")), str(img.get("src", ""))])
            if _LOGO_RE.search(haystack):
                src = img.get("src")
                if src:
                    logo_urls.append(urljoin(url, str(src)))

        stylesheet_urls: list[str] = []
        for link in soup.find_all("link", rel="stylesheet"):
            href = link.get("href")
            if href:
                stylesheet_urls.append(urljoin(url, str(href)))

        # Heuristic scrape of inline <body style="...">
        computed_body: dict[str, str] = {}
        body_tag = soup.find("body")
        if body_tag and body_tag.get("style"):
            for decl in str(body_tag["style"]).split(";"):
                if ":" in decl:
                    k, v = decl.split(":", 1)
                    computed_body[k.strip()] = v.strip()

        # Fetch + parse CSS -- W8: SSRF-gate each URL before GET
        font_urls: list[str] = []
        css_color_vars: dict[str, str] = {}
        for css_url in stylesheet_urls[:max_stylesheets]:
            ok, reason = _is_safe_url(css_url)
            if not ok:
                log.warning(
                    "bs4_css_ssrf_blocked",
                    css_url=css_url,
                    reason=reason,
                    ssrf_blocked=True,
                )
                continue
            try:
                css_resp = await http_client.get(css_url, timeout=60.0)
                if css_resp.status_code != 200:
                    log.warning(
                        "bs4_css_fetch_skip",
                        css_url=css_url,
                        status=css_resp.status_code,
                    )
                    continue
                if len(css_resp.content) > _MAX_ASSET_BYTES:
                    log.warning(
                        "bs4_css_too_large",
                        css_url=css_url,
                        bytes=len(css_resp.content),
                    )
                    continue
                css_text = css_resp.text
            except Exception as err:  # noqa: BLE001 - fallback must not abort
                log.warning("bs4_css_fetch_error", css_url=css_url, error=str(err))
                continue

            rules = tinycss2.parse_stylesheet(
                css_text, skip_whitespace=True, skip_comments=True
            )
            for rule in rules:
                if rule.type == "at-rule" and rule.at_keyword == "font-face":
                    for tok in rule.content or []:
                        if tok.type == "url":
                            font_urls.append(urljoin(css_url, tok.value))
                elif rule.type == "qualified-rule":
                    sel = tinycss2.serialize(rule.prelude).strip()
                    if sel in (":root", "html", "body"):
                        try:
                            declarations = tinycss2.parse_declaration_list(
                                rule.content,
                                skip_whitespace=True,
                                skip_comments=True,
                            )
                        except Exception:  # noqa: BLE001
                            continue
                        for d in declarations:
                            if d.type != "declaration":
                                continue
                            if d.name.startswith("--"):
                                val = tinycss2.serialize(d.value).strip()
                                if val.startswith("#") and len(val) in (4, 7, 9):
                                    css_color_vars[d.name] = val

        return BS4Artifacts(
            html=html,
            title=title,
            h1=h1_text,
            logo_urls=logo_urls,
            stylesheet_urls=stylesheet_urls,
            font_urls=font_urls,
            css_color_vars=css_color_vars,
            computed_body=computed_body,
        )
    finally:
        if _owns_http and http_client is not None:
            await http_client.aclose()
