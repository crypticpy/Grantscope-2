"""
Content enrichment service — thin wrapper around the unified crawler module.

Provides backward-compatible extract_content() and enrich_sources() functions
that delegate to app.crawler for actual content extraction.  Other modules that
import from content_enricher continue to work unchanged.

The crawler module handles:
- HTML boilerplate removal (trafilatura backend)
- JS-rendered pages (optional crawl4ai backend)
- PDF text extraction (PyMuPDF backend)
- Per-domain rate limiting and retries
"""

import logging
from typing import Optional, Tuple

from .crawler import crawl_url, crawl_urls

logger = logging.getLogger(__name__)


async def extract_content(url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract article text and title from a URL asynchronously.

    Delegates to crawler.crawl_url() and maps the CrawlResult back to the
    legacy (text, title) tuple format.

    Returns:
        (extracted_text, title) — either may be None
    """
    result = await crawl_url(url)
    if result.success:
        return result.markdown, result.title
    logger.warning("Content extraction failed for %s: %s", url, result.error)
    return None, None


async def enrich_sources(sources: list, max_concurrent: int = 5) -> list:
    """
    Enrich a list of RawSource objects with full article text.

    For sources that only have snippet content (e.g., from Serper),
    fetches the URL and replaces the snippet with full extracted text.
    Sources that already have substantial content (>500 chars) are skipped.

    Delegates to crawler.crawl_urls() for efficient batch processing with
    built-in concurrency control and per-domain rate limiting.

    Args:
        sources: List of RawSource objects
        max_concurrent: Max concurrent extractions

    Returns:
        The same list with content fields enriched in-place
    """
    # Identify sources that need enrichment (short content = likely a snippet)
    needs_enrichment = [
        (i, s) for i, s in enumerate(sources) if len(s.content or "") < 500 and s.url
    ]

    if not needs_enrichment:
        logger.info("No sources need content enrichment (all have substantial content)")
        return sources

    logger.info(
        f"Enriching {len(needs_enrichment)}/{len(sources)} sources with full article text"
    )

    # Batch crawl all URLs that need enrichment
    urls_to_crawl = [s.url for _, s in needs_enrichment]
    results = await crawl_urls(urls_to_crawl, max_concurrent=max_concurrent)

    # Map results back to sources
    enriched_count = 0
    failed_count = 0

    for (_, source), result in zip(needs_enrichment, results):
        if (
            result.success
            and result.markdown
            and len(result.markdown) > len(source.content or "")
        ):
            source.content = result.markdown
            # Update title if we got a better one and current is generic
            if result.title and (not source.title or len(source.title) < 10):
                source.title = result.title
            enriched_count += 1
        else:
            failed_count += 1

    logger.info(
        f"Content enrichment complete: {enriched_count} enriched, "
        f"{failed_count} failed/unchanged (out of {len(needs_enrichment)} attempted)"
    )

    return sources
