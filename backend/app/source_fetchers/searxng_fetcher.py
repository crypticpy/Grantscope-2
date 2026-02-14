"""
SearXNG self-hosted meta-search engine fetcher.

Queries a local or remote SearXNG instance for web and news results.
SearXNG aggregates results from Google, Bing, DuckDuckGo, and others
without requiring any API keys — the zero-cost, self-hosted alternative
to Serper and Tavily.

Configure via:
    SEARXNG_BASE_URL  — e.g. http://localhost:8888  (no trailing slash)

SearXNG must be running with JSON format enabled in its settings.yml:
    search:
      formats:
        - html
        - json
"""

import os
import logging
import asyncio
from dataclasses import dataclass
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://localhost:8888"


def _get_base_url() -> str:
    """Get the configured SearXNG base URL, falling back to localhost default."""
    return os.getenv("SEARXNG_BASE_URL", "") or _DEFAULT_BASE_URL


@dataclass
class SearXNGResult:
    """A single search result from SearXNG."""

    title: str
    url: str
    snippet: str
    source_name: str = ""
    date: Optional[str] = None
    score: float = 0.0
    engine: str = ""


# ---------------------------------------------------------------------------
# Date filter mapping
# ---------------------------------------------------------------------------
# SearXNG uses "time_range" parameter with values: day, week, month, year
# Serper uses "qdr:d", "qdr:w", "qdr:m" — we accept both and translate.

_DATE_FILTER_MAP = {
    "qdr:d": "day",
    "qdr:w": "week",
    "qdr:m": "month",
    "qdr:y": "year",
    "day": "day",
    "week": "week",
    "month": "month",
    "year": "year",
}


def _translate_date_filter(date_filter: Optional[str]) -> Optional[str]:
    """Translate Serper-style date filters to SearXNG format."""
    if not date_filter:
        return None
    return _DATE_FILTER_MAP.get(date_filter, date_filter)


# ---------------------------------------------------------------------------
# Core search functions
# ---------------------------------------------------------------------------


async def search_web(
    query: str,
    num_results: int = 10,
    date_filter: Optional[str] = None,
) -> List[SearXNGResult]:
    """
    Search via SearXNG general category (web results).

    Args:
        query: Search query string.
        num_results: Desired number of results.
        date_filter: Time filter — accepts Serper-style ("qdr:w") or
                     SearXNG-style ("week").
    """
    base_url = _get_base_url()

    params = {
        "q": query,
        "format": "json",
        "categories": "general",
        "pageno": 1,
    }

    time_range = _translate_date_filter(date_filter)
    if time_range:
        params["time_range"] = time_range

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{base_url}/search",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

        results = [
            SearXNGResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", ""),
                source_name=item.get("engine", ""),
                date=item.get("publishedDate"),
                score=item.get("score", 0.0),
                engine=item.get("engine", ""),
            )
            for item in data.get("results", [])[:num_results]
        ]
        logger.info(f"SearXNG web search: '{query[:50]}' -> {len(results)} results")
        return results

    except httpx.ConnectError:
        logger.warning(f"SearXNG not reachable at {base_url} — is it running?")
        return []
    except Exception as e:
        logger.warning(f"SearXNG web search failed for '{query[:50]}': {e}")
        return []


async def search_news(
    query: str,
    num_results: int = 10,
    date_filter: Optional[str] = None,
) -> List[SearXNGResult]:
    """
    Search SearXNG news category.

    Returns news articles sorted by recency.
    """
    base_url = _get_base_url()

    params = {
        "q": query,
        "format": "json",
        "categories": "news",
        "pageno": 1,
    }

    time_range = _translate_date_filter(date_filter)
    if time_range:
        params["time_range"] = time_range

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{base_url}/search",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

        results = [
            SearXNGResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", ""),
                source_name=item.get("engine", ""),
                date=item.get("publishedDate"),
                score=item.get("score", 0.0),
                engine=item.get("engine", ""),
            )
            for item in data.get("results", [])[:num_results]
        ]
        logger.info(f"SearXNG news search: '{query[:50]}' -> {len(results)} results")
        return results

    except httpx.ConnectError:
        logger.warning(f"SearXNG not reachable at {base_url} — is it running?")
        return []
    except Exception as e:
        logger.warning(f"SearXNG news search failed for '{query[:50]}': {e}")
        return []


async def search_all(
    queries: List[str],
    num_results_per_query: int = 10,
    date_filter: Optional[str] = "week",
    include_news: bool = True,
    include_web: bool = True,
) -> List[SearXNGResult]:
    """
    Run multiple queries across web and news categories, deduplicating by URL.

    Args:
        queries: List of search queries.
        num_results_per_query: Results per query per category.
        date_filter: Time filter (default: past week).
        include_news: Include news category results.
        include_web: Include general/web results.

    Returns:
        Deduplicated list of SearXNGResult objects.
    """
    tasks = []

    for query in queries:
        if include_web:
            tasks.append(search_web(query, num_results_per_query, date_filter))
        if include_news:
            tasks.append(search_news(query, num_results_per_query, date_filter))

    if not tasks:
        return []

    all_results_lists = await asyncio.gather(*tasks, return_exceptions=True)

    seen_urls: set[str] = set()
    unique_results: list[SearXNGResult] = []

    for result_list in all_results_lists:
        if isinstance(result_list, Exception):
            logger.warning(f"SearXNG search task failed: {result_list}")
            continue
        for result in result_list:
            if result.url and result.url not in seen_urls:
                seen_urls.add(result.url)
                unique_results.append(result)

    total = sum(len(r) for r in all_results_lists if not isinstance(r, Exception))
    logger.info(
        f"SearXNG search_all: {len(queries)} queries -> "
        f"{len(unique_results)} unique results (from {total} total)"
    )
    return unique_results


def is_available() -> bool:
    """Check if SearXNG is configured (SEARXNG_BASE_URL env var is set)."""
    return bool(os.getenv("SEARXNG_BASE_URL", ""))


async def health_check() -> dict:
    """
    Check SearXNG connectivity via the /healthz endpoint.

    Returns a dict like:
        {"available": True, "base_url": "http://..."}
    """
    base_url = _get_base_url()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{base_url}/healthz")
            response.raise_for_status()
            return {
                "available": True,
                "base_url": base_url,
            }
    except Exception as e:
        return {
            "available": False,
            "base_url": base_url,
            "error": str(e),
        }
