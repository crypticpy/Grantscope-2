"""
RSS/Atom feed fetcher for curated content sources.

This module fetches and parses RSS/Atom feeds with proper error handling,
rate limiting awareness, and content sanitization.

Usage:
    from backend.app.source_fetchers.rss_fetcher import fetch_rss_sources

    articles = await fetch_rss_sources([
        "https://news.ycombinator.com/rss",
        "https://feeds.arstechnica.com/arstechnica/technology-lab"
    ])
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from time import struct_time

import aiohttp
import feedparser
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class FetchedArticle:
    """
    Standardized article from any content source.

    This dataclass is used across all source fetchers to provide a consistent
    interface for downstream processing in the AI pipeline.
    """
    url: str
    title: str
    content: str
    source_name: str
    source_category: str = "rss"
    published_at: Optional[datetime] = None
    author: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    relevance: float = 0.7


@dataclass
class FeedFetchResult:
    """Result of fetching a single RSS feed."""
    feed_url: str
    success: bool
    articles: List[FetchedArticle] = field(default_factory=list)
    error_message: Optional[str] = None
    feed_title: Optional[str] = None
    feed_link: Optional[str] = None


# ============================================================================
# Helper Functions
# ============================================================================

def _parse_published_date(entry: Dict[str, Any]) -> Optional[datetime]:
    """
    Parse published date from feed entry.

    Tries multiple date fields commonly used in RSS/Atom feeds.
    """
    # Try published_parsed first (feedparser's normalized format)
    for date_field in ["published_parsed", "updated_parsed", "created_parsed"]:
        parsed_date = entry.get(date_field)
        if parsed_date and isinstance(parsed_date, struct_time):
            try:
                return datetime(*parsed_date[:6])
            except (ValueError, TypeError):
                continue

    # Try string date fields as fallback
    for date_field in ["published", "updated", "created", "pubDate"]:
        date_str = entry.get(date_field)
        if date_str:
            try:
                # feedparser usually provides parsed versions, but just in case
                from dateutil import parser as date_parser
                return date_parser.parse(date_str)
            except Exception:
                continue

    return None


def _extract_content(entry: Dict[str, Any]) -> str:
    """
    Extract and sanitize content from feed entry.

    Tries content, summary, and description fields in order of preference.
    Strips HTML tags and normalizes whitespace.
    """
    # Try content array first (Atom feeds)
    content_list = entry.get("content", [])
    if content_list and isinstance(content_list, list):
        for content_item in content_list:
            if isinstance(content_item, dict) and content_item.get("value"):
                raw_content = content_item["value"]
                break
        else:
            raw_content = ""
    else:
        raw_content = ""

    # Fall back to summary or description
    if not raw_content:
        raw_content = entry.get("summary", "") or entry.get("description", "")

    if not raw_content:
        return ""

    # Sanitize HTML content
    try:
        soup = BeautifulSoup(raw_content, "html.parser")
        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()
        # Get text and normalize whitespace
        text = soup.get_text(separator=" ", strip=True)
        # Normalize multiple spaces/newlines
        text = " ".join(text.split())
        return text[:10000]  # Limit content size
    except Exception as e:
        logger.warning(f"HTML parsing failed, using raw content: {e}")
        return raw_content[:10000]


def _extract_tags(entry: Dict[str, Any]) -> List[str]:
    """Extract tags/categories from feed entry."""
    tags = []

    # Try tags field (common in Atom)
    for tag in entry.get("tags", []):
        if isinstance(tag, dict):
            term = tag.get("term") or tag.get("label")
            if term:
                tags.append(str(term))
        elif isinstance(tag, str):
            tags.append(tag)

    # Try category field (common in RSS)
    category = entry.get("category")
    if category and isinstance(category, str):
        tags.append(category)

    return list(set(tags))[:10]  # Dedupe and limit


def _extract_author(entry: Dict[str, Any]) -> Optional[str]:
    """Extract author from feed entry."""
    # Try author field
    author = entry.get("author")
    if author:
        return str(author)[:200]

    # Try author_detail
    author_detail = entry.get("author_detail", {})
    if author_detail.get("name"):
        return str(author_detail["name"])[:200]

    # Try dc:creator (Dublin Core)
    creator = entry.get("dc_creator") or entry.get("creator")
    if creator:
        return str(creator)[:200]

    return None


# ============================================================================
# Main Fetcher Functions
# ============================================================================

async def fetch_single_feed(
    feed_url: str,
    session: Optional[aiohttp.ClientSession] = None,
    timeout: int = 30,
    max_articles: int = 50
) -> FeedFetchResult:
    """
    Fetch and parse a single RSS/Atom feed.

    Args:
        feed_url: URL of the RSS/Atom feed
        session: Optional aiohttp session for connection reuse
        timeout: Request timeout in seconds
        max_articles: Maximum number of articles to return from this feed

    Returns:
        FeedFetchResult with articles or error information
    """
    logger.debug(f"Fetching RSS feed: {feed_url}")

    # Create session if not provided
    close_session = session is None
    if session is None:
        session = aiohttp.ClientSession()

    try:
        # Fetch feed content
        headers = {
            "User-Agent": "Foresight-ContentPipeline/1.0 (https://foresight.city)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"
        }

        async with session.get(
            feed_url,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=timeout),
            allow_redirects=True
        ) as response:
            if response.status != 200:
                error_msg = f"HTTP {response.status}: {response.reason}"
                logger.warning(f"Feed fetch failed for {feed_url}: {error_msg}")
                return FeedFetchResult(
                    feed_url=feed_url,
                    success=False,
                    error_message=error_msg
                )

            content = await response.text()

        # Parse feed with feedparser
        feed = feedparser.parse(content)

        # Check for feed parsing errors
        if feed.bozo:
            bozo_exception = str(feed.bozo_exception) if feed.bozo_exception else "Unknown parsing error"
            logger.warning(f"Feed parsing warning for {feed_url}: {bozo_exception}")
            # Continue anyway - feedparser often succeeds partially

        # Extract feed metadata
        feed_title = feed.feed.get("title", "Unknown Feed")
        feed_link = feed.feed.get("link", feed_url)

        # Process entries
        articles = []
        for entry in feed.entries[:max_articles]:
            try:
                # Extract URL - required field
                url = entry.get("link") or entry.get("id")
                if not url:
                    continue

                # Extract title
                title = entry.get("title", "Untitled")
                if not title or title == "Untitled":
                    # Try to extract title from content
                    content_preview = _extract_content(entry)[:100]
                    if content_preview:
                        title = content_preview.split(".")[0][:100] or "Untitled"

                article = FetchedArticle(
                    url=url,
                    title=title[:500],  # Limit title length
                    content=_extract_content(entry),
                    source_name=feed_title,
                    source_category="rss",
                    published_at=_parse_published_date(entry),
                    author=_extract_author(entry),
                    tags=_extract_tags(entry),
                    metadata={
                        "feed_url": feed_url,
                        "entry_id": entry.get("id"),
                        "feed_link": feed_link
                    }
                )
                articles.append(article)

            except Exception as e:
                logger.warning(f"Failed to parse entry from {feed_url}: {e}")
                continue

        logger.info(f"Fetched {len(articles)} articles from {feed_url}")

        return FeedFetchResult(
            feed_url=feed_url,
            success=True,
            articles=articles,
            feed_title=feed_title,
            feed_link=feed_link
        )

    except asyncio.TimeoutError:
        error_msg = f"Timeout after {timeout}s"
        logger.warning(f"Feed fetch timeout for {feed_url}: {error_msg}")
        return FeedFetchResult(
            feed_url=feed_url,
            success=False,
            error_message=error_msg
        )

    except aiohttp.ClientError as e:
        error_msg = f"Client error: {str(e)}"
        logger.warning(f"Feed fetch client error for {feed_url}: {error_msg}")
        return FeedFetchResult(
            feed_url=feed_url,
            success=False,
            error_message=error_msg
        )

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"Feed fetch failed for {feed_url}: {error_msg}")
        return FeedFetchResult(
            feed_url=feed_url,
            success=False,
            error_message=error_msg
        )

    finally:
        if close_session:
            await session.close()


async def fetch_rss_sources(
    feed_urls: List[str],
    max_articles_per_feed: int = 50,
    timeout_per_feed: int = 30,
    max_concurrent: int = 5
) -> List[FetchedArticle]:
    """
    Fetch articles from multiple RSS/Atom feeds concurrently.

    This is the main entry point for RSS source fetching. It handles:
    - Concurrent fetching with rate limiting
    - Error handling per feed (failures don't stop other feeds)
    - Deduplication by URL
    - Proper session management

    Args:
        feed_urls: List of RSS/Atom feed URLs to fetch
        max_articles_per_feed: Maximum articles to fetch per feed
        timeout_per_feed: Timeout in seconds for each feed
        max_concurrent: Maximum concurrent feed fetches

    Returns:
        List of FetchedArticle from all successfully fetched feeds

    Example:
        >>> articles = await fetch_rss_sources([
        ...     "https://news.ycombinator.com/rss",
        ...     "https://feeds.arstechnica.com/arstechnica/technology-lab"
        ... ])
        >>> print(f"Fetched {len(articles)} articles")
    """
    if not feed_urls:
        logger.warning("No feed URLs provided to fetch_rss_sources")
        return []

    logger.info(f"Fetching RSS sources from {len(feed_urls)} feeds")

    # Use semaphore for rate limiting
    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_with_semaphore(url: str, session: aiohttp.ClientSession) -> FeedFetchResult:
        async with semaphore:
            return await fetch_single_feed(
                feed_url=url,
                session=session,
                timeout=timeout_per_feed,
                max_articles=max_articles_per_feed
            )

    # Create shared session for connection reuse
    connector = aiohttp.TCPConnector(limit=max_concurrent * 2)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Fetch all feeds concurrently
        tasks = [fetch_with_semaphore(url, session) for url in feed_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    all_articles = []
    seen_urls = set()
    successful_feeds = 0
    failed_feeds = 0

    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Feed fetch raised exception: {result}")
            failed_feeds += 1
            continue

        if not isinstance(result, FeedFetchResult):
            logger.error(f"Unexpected result type: {type(result)}")
            failed_feeds += 1
            continue

        if result.success:
            successful_feeds += 1
            for article in result.articles:
                # Deduplicate by URL
                if article.url not in seen_urls:
                    seen_urls.add(article.url)
                    all_articles.append(article)
        else:
            failed_feeds += 1
            logger.warning(f"Feed failed: {result.feed_url} - {result.error_message}")

    logger.info(
        f"RSS fetch complete: {len(all_articles)} articles from "
        f"{successful_feeds}/{len(feed_urls)} feeds "
        f"({failed_feeds} failed)"
    )

    return all_articles


# ============================================================================
# Default Feed Lists (Curated for Municipal Intelligence)
# ============================================================================

DEFAULT_TECH_FEEDS = [
    "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "https://www.wired.com/feed/rss",
    "https://www.theverge.com/rss/index.xml",
    "https://techcrunch.com/feed/",
]

DEFAULT_GOV_TECH_FEEDS = [
    "https://www.govtech.com/rss/",
    "https://statescoop.com/feed/",
    "https://fedscoop.com/feed/",
]

DEFAULT_NEWS_FEEDS = [
    "https://news.ycombinator.com/rss",
    "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
]

DEFAULT_RESEARCH_FEEDS = [
    "http://export.arxiv.org/rss/cs.AI",
    "http://export.arxiv.org/rss/cs.CY",  # Computers and Society
]


async def fetch_default_sources() -> List[FetchedArticle]:
    """
    Fetch from curated list of default RSS sources.

    This provides a quick way to get content from vetted sources
    relevant to municipal technology intelligence.
    """
    all_feeds = (
        DEFAULT_TECH_FEEDS +
        DEFAULT_GOV_TECH_FEEDS +
        DEFAULT_NEWS_FEEDS +
        DEFAULT_RESEARCH_FEEDS
    )
    return await fetch_rss_sources(all_feeds)
