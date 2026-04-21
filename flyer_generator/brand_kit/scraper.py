"""Brand-kit scraper orchestrator (Task 4 expands this module).

For Task 2 (scraper_bs4.py) this module exposes only the SSRF gate
(`_is_safe_url`) so the BS4 fallback can gate stylesheet URLs before
issuing a follow-up GET (W8). Task 4 grows this file with
`fetch_brand_kit`, logo download + traversal guard, and BS4/Playwright
artifact merging.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

_ALLOWED_SCHEMES = {"http", "https"}


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
