"""
Content enrichment service — self-hosted Firecrawl replacement.

Uses trafilatura for high-quality article text extraction from URLs.
Eliminates dependency on Firecrawl's paid API ($83/100K pages → $0).

trafilatura handles:
- HTML boilerplate removal (navs, footers, ads)
- Paywall detection (returns None gracefully)
- Encoding issues
- Various CMS formats (WordPress, Medium, etc.)
"""

import logging
import asyncio
from typing import Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

import trafilatura

logger = logging.getLogger(__name__)

# Reusable thread pool for blocking I/O (trafilatura is sync)
_executor = ThreadPoolExecutor(max_workers=5)


def _extract_sync(url: str, timeout: int = 10) -> Tuple[Optional[str], Optional[str]]:
    """
    Synchronous extraction — runs in thread pool.

    Returns:
        (extracted_text, title) — either may be None on failure
    """
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None, None

        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            favor_precision=True,  # Prefer precision over recall
            deduplicate=True,
        )

        # Also try to get the title from metadata
        metadata = trafilatura.extract_metadata(downloaded)
        title = metadata.title if metadata else None

        return text, title
    except Exception as e:
        logger.warning(f"Content extraction failed for {url}: {e}")
        return None, None


async def extract_content(url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract article text and title from a URL asynchronously.

    Returns:
        (extracted_text, title) — either may be None
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _extract_sync, url)


async def enrich_sources(sources: list, max_concurrent: int = 5) -> list:
    """
    Enrich a list of RawSource objects with full article text.

    For sources that only have snippet content (e.g., from Serper),
    fetches the URL and replaces the snippet with full extracted text.
    Sources that already have substantial content (>500 chars) are skipped.

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

    # Process in batches to limit concurrency
    enriched_count = 0
    failed_count = 0

    semaphore = asyncio.Semaphore(max_concurrent)

    async def enrich_one(index: int, source):
        nonlocal enriched_count, failed_count
        async with semaphore:
            text, title = await extract_content(source.url)
            if text and len(text) > len(source.content or ""):
                source.content = text
                # Update title if we got a better one and current is generic
                if title and (not source.title or len(source.title) < 10):
                    source.title = title
                enriched_count += 1
            else:
                failed_count += 1

    tasks = [enrich_one(i, s) for i, s in needs_enrichment]
    await asyncio.gather(*tasks, return_exceptions=True)

    logger.info(
        f"Content enrichment complete: {enriched_count} enriched, "
        f"{failed_count} failed/unchanged (out of {len(needs_enrichment)} attempted)"
    )

    return sources
