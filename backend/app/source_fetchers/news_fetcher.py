"""
News outlet fetcher with BeautifulSoup for major news sites.

This module fetches articles from major news outlets using aiohttp and
BeautifulSoup for HTML parsing. Supports sites like Reuters, AP News,
and other municipal/government-focused news sources.

Usage:
    from backend.app.source_fetchers.news_fetcher import fetch_news_articles

    articles = await fetch_news_articles(
        topics=["smart city", "municipal technology"],
        max_articles=10
    )
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

# Default timeout for HTTP requests (seconds)
DEFAULT_TIMEOUT = 30

# Maximum content length to extract (characters)
MAX_CONTENT_LENGTH = 10000

# User agent for requests
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# News source configurations with selectors for content extraction
NEWS_SOURCES: List[Dict[str, Any]] = [
    {
        "name": "Reuters",
        "base_url": "https://www.reuters.com",
        "search_url": "https://www.reuters.com/site-search/?query={query}",
        "article_selector": "article",
        "title_selector": "h1",
        "content_selector": "article p",
        "link_selector": "a[href*='/technology/'], a[href*='/world/'], a[href*='/business/']",
        "category": "news",
    },
    {
        "name": "AP News",
        "base_url": "https://apnews.com",
        "search_url": "https://apnews.com/search?q={query}",
        "article_selector": "article",
        "title_selector": "h1",
        "content_selector": "article p",
        "link_selector": "a[href*='/article/']",
        "category": "news",
    },
    {
        "name": "GCN (Government Computing News)",
        "base_url": "https://gcn.com",
        "search_url": "https://gcn.com/?s={query}",
        "article_selector": "article",
        "title_selector": "h1",
        "content_selector": "article p, .entry-content p",
        "link_selector": "a[href*='/articles/']",
        "category": "news",
    },
    {
        "name": "Government Technology",
        "base_url": "https://www.govtech.com",
        "search_url": "https://www.govtech.com/search?q={query}",
        "article_selector": "article",
        "title_selector": "h1",
        "content_selector": "article p, .Article-body p",
        "link_selector": "a[href*='/']",
        "category": "news",
    },
    {
        "name": "StateScoop",
        "base_url": "https://statescoop.com",
        "search_url": "https://statescoop.com/?s={query}",
        "article_selector": "article",
        "title_selector": "h1",
        "content_selector": "article p, .entry-content p",
        "link_selector": "a[href*='/news/']",
        "category": "news",
    },
]


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class NewsArticle:
    """Represents a fetched news article."""
    url: str
    title: str
    content: str
    source_name: str
    source_category: str = "news"
    published_at: Optional[datetime] = None
    author: Optional[str] = None
    excerpt: Optional[str] = None
    relevance: float = 0.7
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "source_name": self.source_name,
            "source_category": self.source_category,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "author": self.author,
            "excerpt": self.excerpt,
            "relevance": self.relevance,
            "metadata": self.metadata,
        }


# ============================================================================
# News Fetcher Class
# ============================================================================

class NewsFetcher:
    """
    Fetches articles from major news outlets using BeautifulSoup.

    Features:
    - Async HTTP requests with aiohttp
    - BeautifulSoup HTML parsing with lxml
    - Configurable news sources
    - Robust error handling with graceful degradation
    - Content extraction with fallback selectors
    """

    def __init__(
        self,
        sources: Optional[List[Dict[str, Any]]] = None,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = 3,
    ):
        """
        Initialize the news fetcher.

        Args:
            sources: List of news source configurations (defaults to NEWS_SOURCES)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
        """
        self.sources = sources or NEWS_SOURCES
        self.timeout = timeout
        self.max_retries = max_retries
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure an aiohttp session exists."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            headers = {"User-Agent": USER_AGENT}
            self._session = aiohttp.ClientSession(timeout=timeout, headers=headers)
        return self._session

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _fetch_url(self, url: str) -> Optional[str]:
        """
        Fetch HTML content from a URL with retries.

        Args:
            url: URL to fetch

        Returns:
            HTML content string or None on failure
        """
        session = await self._ensure_session()

        for attempt in range(self.max_retries):
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 429:
                        # Rate limited - wait and retry
                        wait_time = 2 ** attempt
                        logger.warning(f"Rate limited on {url}, waiting {wait_time}s")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.warning(f"HTTP {response.status} for {url}")
                        return None
            except asyncio.TimeoutError:
                logger.warning(f"Timeout fetching {url} (attempt {attempt + 1}/{self.max_retries})")
                await asyncio.sleep(1)
            except aiohttp.ClientError as e:
                logger.warning(f"Client error fetching {url}: {e}")
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Unexpected error fetching {url}: {e}")
                return None

        logger.error(f"Failed to fetch {url} after {self.max_retries} attempts")
        return None

    def _extract_article_content(
        self,
        soup: BeautifulSoup,
        source_config: Dict[str, Any]
    ) -> tuple[str, str, Optional[str]]:
        """
        Extract title, content, and author from parsed HTML.

        Args:
            soup: BeautifulSoup parsed HTML
            source_config: Source configuration with selectors

        Returns:
            Tuple of (title, content, author)
        """
        # Extract title
        title = ""
        title_elem = soup.select_one(source_config.get("title_selector", "h1"))
        if title_elem:
            title = title_elem.get_text(strip=True)

        # Fallback title extraction
        if not title:
            title_elem = soup.find("title")
            if title_elem:
                title = title_elem.get_text(strip=True)

        # Extract content
        content = ""
        content_selector = source_config.get("content_selector", "article p")
        content_elems = soup.select(content_selector)

        if content_elems:
            paragraphs = [elem.get_text(strip=True) for elem in content_elems]
            content = "\n\n".join(p for p in paragraphs if p and len(p) > 20)

        # Fallback content extraction
        if not content or len(content) < 100:
            # Try main content area
            main_content = soup.find("article") or soup.find("main") or soup.find(class_=re.compile(r"content|article|body", re.I))
            if main_content:
                content = main_content.get_text(separator="\n\n", strip=True)

        # Truncate content if too long
        if len(content) > MAX_CONTENT_LENGTH:
            content = content[:MAX_CONTENT_LENGTH] + "..."

        # Extract author
        author = None
        author_elem = soup.find(class_=re.compile(r"author|byline", re.I)) or soup.find("meta", attrs={"name": "author"})
        if author_elem:
            if hasattr(author_elem, "get_text"):
                author = author_elem.get_text(strip=True)
            elif author_elem.get("content"):
                author = author_elem.get("content")

        return title, content, author

    def _extract_published_date(self, soup: BeautifulSoup) -> Optional[datetime]:
        """
        Extract publication date from HTML.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            Datetime object or None
        """
        # Try meta tags first
        date_metas = [
            soup.find("meta", attrs={"property": "article:published_time"}),
            soup.find("meta", attrs={"name": "date"}),
            soup.find("meta", attrs={"name": "pubdate"}),
            soup.find("meta", attrs={"property": "og:updated_time"}),
        ]

        for meta in date_metas:
            if meta and meta.get("content"):
                try:
                    return datetime.fromisoformat(meta["content"].replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    continue

        # Try time element
        time_elem = soup.find("time")
        if time_elem:
            datetime_attr = time_elem.get("datetime")
            if datetime_attr:
                try:
                    return datetime.fromisoformat(datetime_attr.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

        return None

    async def fetch_article(
        self,
        url: str,
        source_config: Optional[Dict[str, Any]] = None
    ) -> Optional[NewsArticle]:
        """
        Fetch and parse a single article.

        Args:
            url: Article URL
            source_config: Optional source configuration for parsing

        Returns:
            NewsArticle or None on failure
        """
        html = await self._fetch_url(url)
        if not html:
            return None

        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception as e:
            logger.warning(f"Failed to parse HTML for {url}: {e}")
            # Fallback to html.parser
            try:
                soup = BeautifulSoup(html, "html.parser")
            except Exception as e2:
                logger.error(f"All parsers failed for {url}: {e2}")
                return None

        # Use default config if not provided
        if source_config is None:
            source_config = {
                "name": urlparse(url).netloc,
                "title_selector": "h1",
                "content_selector": "article p",
                "category": "news",
            }

        title, content, author = self._extract_article_content(soup, source_config)
        published_at = self._extract_published_date(soup)

        if not title or not content:
            logger.warning(f"Could not extract title/content from {url}")
            return None

        # Create excerpt from first 200 chars of content
        excerpt = content[:200] + "..." if len(content) > 200 else content

        return NewsArticle(
            url=url,
            title=title,
            content=content,
            source_name=source_config.get("name", "Unknown"),
            source_category=source_config.get("category", "news"),
            published_at=published_at,
            author=author,
            excerpt=excerpt,
            relevance=0.7,
            metadata={"fetched_at": datetime.now().isoformat()},
        )

    async def search_source(
        self,
        source_config: Dict[str, Any],
        query: str,
        max_articles: int = 5
    ) -> List[NewsArticle]:
        """
        Search a news source for articles matching a query.

        Args:
            source_config: Source configuration
            query: Search query
            max_articles: Maximum articles to return

        Returns:
            List of NewsArticle objects
        """
        source_name = source_config.get("name", "Unknown")
        search_url = source_config.get("search_url", "").format(query=query.replace(" ", "+"))

        if not search_url:
            logger.warning(f"No search URL configured for {source_name}")
            return []

        logger.info(f"Searching {source_name} for: {query}")

        html = await self._fetch_url(search_url)
        if not html:
            logger.warning(f"Failed to fetch search results from {source_name}")
            return []

        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")

        # Find article links
        link_selector = source_config.get("link_selector", "a[href*='/']")
        links = soup.select(link_selector)

        # Extract unique article URLs
        base_url = source_config.get("base_url", "")
        seen_urls = set()
        article_urls = []

        for link in links:
            href = link.get("href", "")
            if not href:
                continue

            # Make absolute URL
            if href.startswith("/"):
                href = urljoin(base_url, href)
            elif not href.startswith("http"):
                continue

            # Skip duplicates and non-article URLs
            if href in seen_urls:
                continue
            if any(skip in href for skip in ["#", "javascript:", "mailto:", "/tag/", "/category/", "/author/"]):
                continue

            seen_urls.add(href)
            article_urls.append(href)

            if len(article_urls) >= max_articles * 2:  # Get extra in case some fail
                break

        logger.info(f"Found {len(article_urls)} potential articles from {source_name}")

        # Fetch articles concurrently
        tasks = [self.fetch_article(url, source_config) for url in article_urls[:max_articles * 2]]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        articles = []
        for result in results:
            if isinstance(result, NewsArticle):
                articles.append(result)
                if len(articles) >= max_articles:
                    break
            elif isinstance(result, Exception):
                logger.warning(f"Article fetch failed: {result}")

        logger.info(f"Successfully fetched {len(articles)} articles from {source_name}")
        return articles

    async def fetch_from_all_sources(
        self,
        topics: List[str],
        max_articles_per_source: int = 3,
        max_total_articles: int = 20
    ) -> List[NewsArticle]:
        """
        Fetch articles from all configured news sources.

        Args:
            topics: List of search topics/keywords
            max_articles_per_source: Max articles per source per topic
            max_total_articles: Maximum total articles to return

        Returns:
            List of NewsArticle objects from all sources
        """
        all_articles: List[NewsArticle] = []
        seen_urls: set = set()

        for topic in topics:
            for source_config in self.sources:
                if len(all_articles) >= max_total_articles:
                    break

                try:
                    articles = await self.search_source(
                        source_config,
                        topic,
                        max_articles=max_articles_per_source
                    )

                    for article in articles:
                        if article.url not in seen_urls:
                            seen_urls.add(article.url)
                            all_articles.append(article)

                            if len(all_articles) >= max_total_articles:
                                break

                except Exception as e:
                    source_name = source_config.get("name", "Unknown")
                    logger.error(f"Failed to fetch from {source_name}: {e}")
                    # Continue with other sources - graceful degradation
                    continue

        logger.info(f"Total articles fetched from news sources: {len(all_articles)}")
        return all_articles


# ============================================================================
# Convenience Functions
# ============================================================================

async def fetch_news_articles(
    topics: Optional[List[str]] = None,
    urls: Optional[List[str]] = None,
    max_articles: int = 20,
    sources: Optional[List[Dict[str, Any]]] = None,
) -> List[NewsArticle]:
    """
    Fetch news articles from major news outlets.

    This is the main entry point for fetching news articles. It can either:
    1. Search configured news sources for topics
    2. Fetch specific URLs directly

    Args:
        topics: List of search topics (e.g., ["smart city", "municipal AI"])
        urls: List of specific article URLs to fetch
        max_articles: Maximum number of articles to return
        sources: Optional custom source configurations

    Returns:
        List of NewsArticle objects

    Example:
        >>> articles = await fetch_news_articles(
        ...     topics=["smart city technology", "municipal innovation"],
        ...     max_articles=10
        ... )
        >>> for article in articles:
        ...     print(f"{article.title} - {article.source_name}")
    """
    async with NewsFetcher(sources=sources) as fetcher:
        articles: List[NewsArticle] = []

        # Fetch by topics if provided
        if topics:
            topic_articles = await fetcher.fetch_from_all_sources(
                topics=topics,
                max_total_articles=max_articles
            )
            articles.extend(topic_articles)

        # Fetch specific URLs if provided
        if urls:
            url_tasks = [fetcher.fetch_article(url) for url in urls[:max_articles]]
            url_results = await asyncio.gather(*url_tasks, return_exceptions=True)

            for result in url_results:
                if isinstance(result, NewsArticle):
                    articles.append(result)
                elif isinstance(result, Exception):
                    logger.warning(f"Failed to fetch URL: {result}")

        # Remove duplicates by URL
        seen = set()
        unique_articles = []
        for article in articles:
            if article.url not in seen:
                seen.add(article.url)
                unique_articles.append(article)

        return unique_articles[:max_articles]


async def fetch_articles_from_urls(urls: List[str]) -> List[NewsArticle]:
    """
    Fetch articles from a list of specific URLs.

    Args:
        urls: List of article URLs to fetch

    Returns:
        List of successfully fetched NewsArticle objects
    """
    async with NewsFetcher() as fetcher:
        tasks = [fetcher.fetch_article(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        articles = []
        for result in results:
            if isinstance(result, NewsArticle):
                articles.append(result)

        return articles
