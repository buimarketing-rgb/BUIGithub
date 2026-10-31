"""Configurable web-search adapters. SearXNG (self-hosted, free) is the default."""
import logging
from dataclasses import dataclass

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)


@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str


class SearchUnavailable(RuntimeError):
    pass


class SearchProvider:
    name = "base"

    def search(self, query: str, limit: int) -> list[SearchResult]:  # pragma: no cover - interface
        raise NotImplementedError


class SearxngProvider(SearchProvider):
    name = "searxng"

    def __init__(self, base_url: str) -> None:
        self.base = base_url.rstrip("/")

    def search(self, query: str, limit: int) -> list[SearchResult]:
        try:
            r = httpx.get(
                f"{self.base}/search",
                params={"q": query, "format": "json", "safesearch": 1, "language": "en"},
                timeout=get_settings().research_timeout_seconds,
                headers={"User-Agent": get_settings().research_user_agent},
            )
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise SearchUnavailable(f"SearXNG unavailable at {self.base}: {exc}") from exc
        out = []
        for item in r.json().get("results", [])[:limit]:
            if item.get("url", "").startswith(("http://", "https://")):
                out.append(SearchResult(item["url"], item.get("title") or item["url"], item.get("content") or ""))
        return out


class BraveProvider(SearchProvider):
    """Optional: Brave Search API (has a limited free tier; requires BRAVE_API_KEY)."""

    name = "brave"

    def __init__(self, key: str) -> None:
        self.key = key

    def search(self, query: str, limit: int) -> list[SearchResult]:
        try:
            r = httpx.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": limit},
                headers={"X-Subscription-Token": self.key, "Accept": "application/json"},
                timeout=get_settings().research_timeout_seconds,
            )
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise SearchUnavailable(f"Brave search failed: {exc}") from exc
        return [
            SearchResult(i["url"], i.get("title", i["url"]), i.get("description", ""))
            for i in r.json().get("web", {}).get("results", [])[:limit]
        ]


_override: SearchProvider | None = None


def set_search_provider_override(provider: SearchProvider | None) -> None:
    """Used by tests to inject a fake provider."""
    global _override
    _override = provider


def get_search_provider() -> SearchProvider | None:
    if _override is not None:
        return _override
    s = get_settings()
    if s.search_provider == "searxng" and s.searxng_url:
        return SearxngProvider(s.searxng_url)
    if s.search_provider == "brave" and s.brave_api_key:
        return BraveProvider(s.brave_api_key)
    return None
