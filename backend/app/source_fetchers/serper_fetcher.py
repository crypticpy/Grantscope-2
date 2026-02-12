"""
Serper.dev Google Search API fetcher.

Uses Google Search and Google News via Serper.dev API for real-time,
fresh content discovery. Primary search backend for workstream scans.

Advantages over web scraping:
- Returns fresh, time-sorted results
- Supports date filtering (past day/week/month)
- Google-quality relevance ranking
- No scraping fragility (403s, layout changes)
"""

import os
import logging
import asyncio
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

SERPER_API_URL = "https://google.serper.dev"
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")


@dataclass
class SerperResult:
    """A single search result from Serper."""

    title: str
    url: str
    snippet: str
    source_name: str = ""
    date: Optional[str] = None


async def search_web(
    query: str,
    num_results: int = 10,
    date_filter: Optional[str] = None,  # "qdr:d", "qdr:w", "qdr:m"
) -> List[SerperResult]:
    """
    Search Google Web via Serper API.

    Args:
        query: Search query string
        num_results: Number of results to return (max 100)
        date_filter: Time-based filter (qdr:d=day, qdr:w=week, qdr:m=month)
    """
    api_key = os.getenv("SERPER_API_KEY", SERPER_API_KEY)
    if not api_key:
        logger.warning("SERPER_API_KEY not set, skipping web search")
        return []

    payload = {"q": query, "num": min(num_results, 100)}
    if date_filter:
        payload["tbs"] = date_filter

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{SERPER_API_URL}/search",
                json=payload,
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data.get("organic", []):
            results.append(
                SerperResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    date=item.get("date"),
                )
            )

        logger.info(f"Serper web search: '{query[:50]}' → {len(results)} results")
        return results

    except Exception as e:
        logger.warning(f"Serper web search failed for '{query[:50]}': {e}")
        return []


async def search_news(
    query: str,
    num_results: int = 10,
    date_filter: Optional[str] = None,
) -> List[SerperResult]:
    """
    Search Google News via Serper API.

    Returns news articles sorted by recency with source attribution.
    """
    api_key = os.getenv("SERPER_API_KEY", SERPER_API_KEY)
    if not api_key:
        logger.warning("SERPER_API_KEY not set, skipping news search")
        return []

    payload = {"q": query, "num": min(num_results, 100)}
    if date_filter:
        payload["tbs"] = date_filter

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{SERPER_API_URL}/news",
                json=payload,
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data.get("news", []):
            results.append(
                SerperResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    source_name=item.get("source", ""),
                    date=item.get("date"),
                )
            )

        logger.info(f"Serper news search: '{query[:50]}' → {len(results)} results")
        return results

    except Exception as e:
        logger.warning(f"Serper news search failed for '{query[:50]}': {e}")
        return []


async def search_all(
    queries: List[str],
    num_results_per_query: int = 10,
    date_filter: Optional[str] = "qdr:w",  # Default to past week
    include_news: bool = True,
    include_web: bool = True,
) -> List[SerperResult]:
    """
    Run multiple queries across web and news search, deduplicating by URL.

    Args:
        queries: List of search queries
        num_results_per_query: Results per query per search type
        date_filter: Time filter (default: past week)
        include_news: Include Google News results
        include_web: Include Google Web results

    Returns:
        Deduplicated list of SerperResult objects
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

    # Flatten and deduplicate by URL
    seen_urls = set()
    unique_results = []

    for result_list in all_results_lists:
        if isinstance(result_list, Exception):
            logger.warning(f"Search task failed: {result_list}")
            continue
        for result in result_list:
            if result.url and result.url not in seen_urls:
                seen_urls.add(result.url)
                unique_results.append(result)

    logger.info(
        f"Serper search_all: {len(queries)} queries → "
        f"{len(unique_results)} unique results (from {sum(len(r) for r in all_results_lists if not isinstance(r, Exception))} total)"
    )
    return unique_results


def is_available() -> bool:
    """Check if Serper API key is configured."""
    return bool(os.getenv("SERPER_API_KEY", ""))
