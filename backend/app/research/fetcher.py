"""Polite page fetcher: honours robots.txt, never authenticates or bypasses access controls,
only fetches public http(s) pages and refuses private/internal network addresses (SSRF guard)."""
import ipaddress
import logging
import socket
import urllib.robotparser
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)
MAX_BYTES = 3 * 1024 * 1024


@dataclass
class FetchResult:
    url: str
    status: str  # fetched | blocked_robots | error | skipped
    http_status: int | None = None
    html: str | None = None
    error: str | None = None


class Fetcher:
    """Overridable for tests (see set_fetcher_override)."""

    def __init__(self) -> None:
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    @staticmethod
    def is_public_url(url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return False
        if parsed.username or parsed.password:
            return False
        try:
            for info in socket.getaddrinfo(parsed.hostname, None):
                ip = ipaddress.ip_address(info[4][0])
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                    return False
        except (socket.gaierror, ValueError):
            return False
        return True

    def robots_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = httpx.get(f"{base}/robots.txt", timeout=8, follow_redirects=True, headers={"User-Agent": get_settings().research_user_agent})
                if r.status_code in (401, 403):
                    rp.disallow_all = True
                elif r.status_code >= 400:
                    rp.allow_all = True
                else:
                    rp.parse(r.text.splitlines())
                self._robots[base] = rp
            except httpx.HTTPError:
                self._robots[base] = None  # robots unreachable -> treat as allowed (standard behaviour)
        rp = self._robots[base]
        return True if rp is None else rp.can_fetch(get_settings().research_user_agent, url)

    def fetch(self, url: str) -> FetchResult:
        if not self.is_public_url(url):
            return FetchResult(url, "skipped", error="Only public http(s) URLs can be researched.")
        if not self.robots_allowed(url):
            return FetchResult(url, "blocked_robots", error="Disallowed by the site's robots.txt")
        s = get_settings()
        try:
            with httpx.stream(
                "GET", url, timeout=s.research_timeout_seconds, follow_redirects=True,
                headers={"User-Agent": s.research_user_agent, "Accept": "text/html,application/xhtml+xml"},
            ) as r:
                if r.status_code in (401, 403):
                    return FetchResult(url, "skipped", r.status_code, error="Page requires authorisation; BUI does not bypass access controls.")
                if r.status_code >= 400:
                    return FetchResult(url, "error", r.status_code, error=f"HTTP {r.status_code}")
                ctype = r.headers.get("content-type", "")
                if "html" not in ctype and "text/plain" not in ctype:
                    return FetchResult(url, "skipped", r.status_code, error=f"Unsupported content type {ctype}")
                if not self.is_public_url(str(r.url)):
                    return FetchResult(url, "skipped", error="Redirected to a non-public address.")
                body = b""
                for part in r.iter_bytes():
                    body += part
                    if len(body) > MAX_BYTES:
                        break
                return FetchResult(str(r.url), "fetched", r.status_code, html=body.decode(r.encoding or "utf-8", errors="replace"))
        except httpx.HTTPError as exc:
            return FetchResult(url, "error", error=str(exc)[:300])


_override: Fetcher | None = None


def set_fetcher_override(f: Fetcher | None) -> None:
    global _override
    _override = f


def get_fetcher() -> Fetcher:
    return _override or Fetcher()
