"""
Unified search provider for Foresight.

Routes search requests to the configured backend — SearXNG (self-hosted),
Serper (paid API), or Tavily (paid API) — via a single interface that
all consumers import instead of importing individual fetchers directly.

Configure via environment variable:
    SEARCH_PROVIDER=searxng | serper | tavily | auto

When set to "auto" (default), the provider tries backends in order:
    1. SearXNG  (if SEARXNG_BASE_URL is set)
    2. Serper   (if SERPER_API_KEY is set)
    3. Tavily   (if TAVILY_API_KEY is set)

The first available backend wins. If none are configured, search calls
return empty results with a warning — the system degrades gracefully
to RSS-only discovery.
"""

import os
import logging
import asyncio
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Unified search result — compatible with SerperResult
# ---------------------------------------------------------------------------


@dataclass
class SearchResult:
    """A single search result from any provider."""

    title: str
    url: str
    snippet: str
    source_name: str = ""
    date: Optional[str] = None
    provider: str = ""


# ---------------------------------------------------------------------------
# Provider detection
# ---------------------------------------------------------------------------


def get_active_provider() -> str:
    """
    Determine which search provider to use based on configuration.

    Returns one of: "searxng", "serper", "tavily", or "none".
    """
    explicit = os.getenv("SEARCH_PROVIDER", "auto").lower().strip()

    if explicit == "auto":
        if os.getenv("SEARXNG_BASE_URL", ""):
            return "searxng"
        if os.getenv("SERPER_API_KEY", ""):
            return "serper"
        if os.getenv("TAVILY_API_KEY", ""):
            return "tavily"
        return "none"

    if explicit in ("searxng", "serper", "tavily"):
        return explicit

    logger.warning(f"Unknown SEARCH_PROVIDER='{explicit}', falling back to auto")
    return (
        get_active_provider.__wrapped__()
        if hasattr(get_active_provider, "__wrapped__")
        else "none"
    )


def is_available() -> bool:
    """Check if any search provider is configured."""
    return get_active_provider() != "none"


def get_provider_info() -> dict:
    """Return info about the active search provider for health checks."""
    provider = get_active_provider()
    info = {"provider": provider, "available": provider != "none"}

    if provider == "searxng":
        info["base_url"] = os.getenv("SEARXNG_BASE_URL", "")
    elif provider == "serper":
        info["has_api_key"] = bool(os.getenv("SERPER_API_KEY", ""))
    elif provider == "tavily":
        info["has_api_key"] = bool(os.getenv("TAVILY_API_KEY", ""))

    return info


# ---------------------------------------------------------------------------
# SearXNG adapter
# ---------------------------------------------------------------------------


async def _searxng_search_web(
    query: str, num_results: int, date_filter: Optional[str]
) -> List[SearchResult]:
    from .source_fetchers.searxng_fetcher import search_web as sx_search_web

    raw = await sx_search_web(query, num_results, date_filter)
    return [
        SearchResult(
            title=r.title,
            url=r.url,
            snippet=r.snippet,
            source_name=r.source_name,
            date=r.date,
            provider="searxng",
        )
        for r in raw
    ]


async def _searxng_search_news(
    query: str, num_results: int, date_filter: Optional[str]
) -> List[SearchResult]:
    from .source_fetchers.searxng_fetcher import search_news as sx_search_news

    raw = await sx_search_news(query, num_results, date_filter)
    return [
        SearchResult(
            title=r.title,
            url=r.url,
            snippet=r.snippet,
            source_name=r.source_name,
            date=r.date,
            provider="searxng",
        )
        for r in raw
    ]


# ---------------------------------------------------------------------------
# Serper adapter
# ---------------------------------------------------------------------------


async def _serper_search_web(
    query: str, num_results: int, date_filter: Optional[str]
) -> List[SearchResult]:
    from .source_fetchers.serper_fetcher import search_web as sp_search_web

    raw = await sp_search_web(query, num_results, date_filter)
    return [
        SearchResult(
            title=r.title,
            url=r.url,
            snippet=r.snippet,
            source_name=r.source_name,
            date=r.date,
            provider="serper",
        )
        for r in raw
    ]


async def _serper_search_news(
    query: str, num_results: int, date_filter: Optional[str]
) -> List[SearchResult]:
    from .source_fetchers.serper_fetcher import search_news as sp_search_news

    raw = await sp_search_news(query, num_results, date_filter)
    return [
        SearchResult(
            title=r.title,
            url=r.url,
            snippet=r.snippet,
            source_name=r.source_name,
            date=r.date,
            provider="serper",
        )
        for r in raw
    ]


# ---------------------------------------------------------------------------
# Tavily adapter
# ---------------------------------------------------------------------------


async def _tavily_search_web(
    query: str, num_results: int, date_filter: Optional[str]
) -> List[SearchResult]:
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        return []

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        data = await asyncio.to_thread(
            client.search,
            query=query,
            max_results=num_results,
            search_depth="basic",
        )
        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("content", ""),
                source_name=r.get("source", ""),
                date=r.get("published_date"),
                provider="tavily",
            )
            for r in data.get("results", [])
        ]
    except Exception as e:
        logger.warning(f"Tavily search failed for '{query[:50]}': {e}")
        return []


async def _tavily_search_news(
    query: str, num_results: int, date_filter: Optional[str]
) -> List[SearchResult]:
    # Tavily doesn't have a separate news endpoint — use topic=news
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        return []

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        data = await asyncio.to_thread(
            client.search,
            query=query,
            max_results=num_results,
            topic="news",
        )
        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("content", ""),
                source_name=r.get("source", ""),
                date=r.get("published_date"),
                provider="tavily",
            )
            for r in data.get("results", [])
        ]
    except Exception as e:
        logger.warning(f"Tavily news search failed for '{query[:50]}': {e}")
        return []


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_DISPATCH = {
    "searxng": (_searxng_search_web, _searxng_search_news),
    "serper": (_serper_search_web, _serper_search_news),
    "tavily": (_tavily_search_web, _tavily_search_news),
}


# ---------------------------------------------------------------------------
# Public API — drop-in replacement for serper_fetcher imports
# ---------------------------------------------------------------------------


async def search_web(
    query: str,
    num_results: int = 10,
    date_filter: Optional[str] = None,
) -> List[SearchResult]:
    """
    Search the web using the configured provider.

    Interface matches serper_fetcher.search_web() for drop-in replacement.
    """
    provider = get_active_provider()
    if provider == "none":
        logger.warning("No search provider configured — returning empty results")
        return []

    fn_web, _ = _DISPATCH[provider]
    return await fn_web(query, num_results, date_filter)


async def search_news(
    query: str,
    num_results: int = 10,
    date_filter: Optional[str] = None,
) -> List[SearchResult]:
    """
    Search news using the configured provider.

    Interface matches serper_fetcher.search_news() for drop-in replacement.
    """
    provider = get_active_provider()
    if provider == "none":
        logger.warning("No search provider configured — returning empty results")
        return []

    _, fn_news = _DISPATCH[provider]
    return await fn_news(query, num_results, date_filter)


async def search_all(
    queries: List[str],
    num_results_per_query: int = 10,
    date_filter: Optional[str] = "qdr:w",
    include_news: bool = True,
    include_web: bool = True,
) -> List[SearchResult]:
    """
    Run multiple queries across web and news, deduplicating by URL.

    Interface matches serper_fetcher.search_all() for drop-in replacement.
    """
    provider = get_active_provider()
    if provider == "none":
        logger.warning("No search provider configured — returning empty results")
        return []

    fn_web, fn_news = _DISPATCH[provider]
    tasks = []

    for query in queries:
        if include_web:
            tasks.append(fn_web(query, num_results_per_query, date_filter))
        if include_news:
            tasks.append(fn_news(query, num_results_per_query, date_filter))

    if not tasks:
        return []

    all_results_lists = await asyncio.gather(*tasks, return_exceptions=True)

    seen_urls: set[str] = set()
    unique_results: list[SearchResult] = []

    for result_list in all_results_lists:
        if isinstance(result_list, Exception):
            logger.warning(f"Search task failed: {result_list}")
            continue
        for result in result_list:
            if result.url and result.url not in seen_urls:
                seen_urls.add(result.url)
                unique_results.append(result)

    total = sum(len(r) for r in all_results_lists if not isinstance(r, Exception))
    logger.info(
        f"search_all ({provider}): {len(queries)} queries -> "
        f"{len(unique_results)} unique results (from {total} total)"
    )
    return unique_results
