"""
Tech blog fetcher for TechCrunch, Ars Technica, and company blogs.

This module fetches articles from major tech blogs using aiohttp and
BeautifulSoup for HTML parsing, with optional RSS feed fallback for
reliable content extraction.

Usage:
    from backend.app.source_fetchers.tech_blog_fetcher import fetch_tech_blog_articles

    articles = await fetch_tech_blog_articles(
        topics=["smart city", "municipal technology"],
        max_articles=10
    )
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse, quote_plus

import aiohttp
from bs4 import BeautifulSoup
import feedparser

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

# Tech blog source configurations
TECH_BLOG_SOURCES: List[Dict[str, Any]] = [
    {
        "name": "TechCrunch",
        "base_url": "https://techcrunch.com",
        "search_url": "https://techcrunch.com/?s={query}",
        "rss_url": "https://techcrunch.com/feed/",
        "article_selector": "article",
        "title_selector": "h1, .article-header h1, .post-title",
        "content_selector": ".article-content p, .entry-content p, article p",
        "link_selector": "a[href*='/20']",  # TechCrunch uses date-based URLs
        "category": "tech_blog",
        "priority": 1,
    },
    {
        "name": "Ars Technica",
        "base_url": "https://arstechnica.com",
        "search_url": "https://arstechnica.com/search/?q={query}",
        "rss_url": "https://feeds.arstechnica.com/arstechnica/index",
        "article_selector": "article",
        "title_selector": "h1, .heading, .article-title",
        "content_selector": ".article-content p, .post-content p, article p",
        "link_selector": "a[href*='/20'], a[href*='/information-technology/'], a[href*='/tech-policy/']",
        "category": "tech_blog",
        "priority": 1,
    },
    {
        "name": "The Verge",
        "base_url": "https://www.theverge.com",
        "search_url": "https://www.theverge.com/search?q={query}",
        "rss_url": "https://www.theverge.com/rss/index.xml",
        "article_selector": "article",
        "title_selector": "h1",
        "content_selector": "article p, .article-body p",
        "link_selector": "a[href*='/20']",
        "category": "tech_blog",
        "priority": 2,
    },
    {
        "name": "Wired",
        "base_url": "https://www.wired.com",
        "search_url": "https://www.wired.com/search/?q={query}",
        "rss_url": "https://www.wired.com/feed/rss",
        "article_selector": "article",
        "title_selector": "h1",
        "content_selector": "article p, .body-content p",
        "link_selector": "a[href*='/story/'], a[href*='/article/']",
        "category": "tech_blog",
        "priority": 2,
    },
    # Company/Engineering Blogs
    {
        "name": "Google AI Blog",
        "base_url": "https://ai.googleblog.com",
        "search_url": "https://ai.googleblog.com/search?q={query}",
        "rss_url": "https://ai.googleblog.com/feeds/posts/default",
        "article_selector": ".post",
        "title_selector": "h1, .post-title",
        "content_selector": ".post-body p, .post-content p",
        "link_selector": "a[href*='/20']",
        "category": "company_blog",
        "priority": 2,
    },
    {
        "name": "Microsoft Research Blog",
        "base_url": "https://www.microsoft.com/en-us/research/blog",
        "search_url": "https://www.microsoft.com/en-us/research/search/?q={query}",
        "rss_url": "https://www.microsoft.com/en-us/research/feed/",
        "article_selector": "article",
        "title_selector": "h1",
        "content_selector": "article p, .post-content p",
        "link_selector": "a[href*='/blog/']",
        "category": "company_blog",
        "priority": 2,
    },
    {
        "name": "OpenAI Blog",
        "base_url": "https://openai.com/blog",
        "search_url": None,  # No search, use RSS/scrape
        "rss_url": "https://openai.com/blog/rss/",
        "article_selector": "article",
        "title_selector": "h1",
        "content_selector": "article p, .post-content p",
        "link_selector": "a[href*='/blog/']",
        "category": "company_blog",
        "priority": 1,
    },
    {
        "name": "AWS Architecture Blog",
        "base_url": "https://aws.amazon.com/blogs/architecture",
        "search_url": None,  # Use RSS
        "rss_url": "https://aws.amazon.com/blogs/architecture/feed/",
        "article_selector": "article",
        "title_selector": "h1",
        "content_selector": "article p, .entry-content p",
        "link_selector": "a[href*='/blogs/']",
        "category": "company_blog",
        "priority": 3,
    },
]

# RSS feeds optimized for government/municipal tech topics
GOV_TECH_BLOG_FEEDS = [
    "https://www.govtech.com/rss/",
    "https://statescoop.com/feed/",
    "https://gcn.com/feed/",
]


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class TechBlogArticle:
    """Represents a fetched tech blog article."""

    url: str
    title: str
    content: str
    source_name: str
    source_category: str = "tech_blog"
    published_at: Optional[datetime] = None
    author: Optional[str] = None
    excerpt: Optional[str] = None
    tags: List[str] = field(default_factory=list)
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
            "published_at": (
                self.published_at.isoformat() if self.published_at else None
            ),
            "author": self.author,
            "excerpt": self.excerpt,
            "tags": self.tags,
            "relevance": self.relevance,
            "metadata": self.metadata,
        }


@dataclass
class TechBlogFetchResult:
    """Result of fetching tech blog articles."""

    articles: List[TechBlogArticle]
    source_name: str
    success: bool
    error_message: Optional[str] = None
    articles_found: int = 0


# ============================================================================
# Tech Blog Fetcher Class
# ============================================================================


class TechBlogFetcher:
    """
    Fetches articles from major tech blogs using BeautifulSoup with RSS fallback.

    Features:
    - Async HTTP requests with aiohttp
    - BeautifulSoup HTML parsing with lxml
    - RSS feed fallback for reliable content
    - Configurable blog sources
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
        Initialize the tech blog fetcher.

        Args:
            sources: List of blog source configurations (defaults to TECH_BLOG_SOURCES)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
        """
        self.sources = sources or TECH_BLOG_SOURCES
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
                        wait_time = 2**attempt
                        logger.warning(f"Rate limited on {url}, waiting {wait_time}s")
                        await asyncio.sleep(wait_time)
                    elif response.status == 403:
                        logger.warning(f"Access denied (403) for {url}")
                        return None
                    else:
                        logger.warning(f"HTTP {response.status} for {url}")
                        return None
            except asyncio.TimeoutError:
                logger.warning(
                    f"Timeout fetching {url} (attempt {attempt + 1}/{self.max_retries})"
                )
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
        self, soup: BeautifulSoup, source_config: Dict[str, Any]
    ) -> tuple[str, str, Optional[str], List[str]]:
        """
        Extract title, content, author, and tags from parsed HTML.

        Args:
            soup: BeautifulSoup parsed HTML
            source_config: Source configuration with selectors

        Returns:
            Tuple of (title, content, author, tags)
        """
        # Extract title
        title = ""
        title_selector = source_config.get("title_selector", "h1")
        for selector in title_selector.split(", "):
            if title_elem := soup.select_one(selector.strip()):
                title = title_elem.get_text(strip=True)
                break

        # Fallback title extraction
        if not title:
            if title_elem := soup.find("title"):
                title = title_elem.get_text(strip=True)
                # Remove site name suffix
                title = re.sub(
                    r"\s*[|\-–]\s*(TechCrunch|Ars Technica|The Verge|Wired).*$",
                    "",
                    title,
                    flags=re.I,
                )

        # Extract content
        content = ""
        content_selector = source_config.get("content_selector", "article p")
        if content_elems := soup.select(content_selector):
            paragraphs = [elem.get_text(strip=True) for elem in content_elems]
            content = "\n\n".join(p for p in paragraphs if p and len(p) > 20)

        # Fallback content extraction
        if not content or len(content) < 100:
            if main_content := (
                soup.find("article")
                or soup.find("main")
                or soup.find(class_=re.compile(r"content|article|body|post", re.I))
            ):
                content = main_content.get_text(separator="\n\n", strip=True)

        # Truncate content if too long
        if len(content) > MAX_CONTENT_LENGTH:
            content = f"{content[:MAX_CONTENT_LENGTH]}..."

        # Extract author
        author = None
        author_patterns = [
            soup.find(class_=re.compile(r"author|byline|writer", re.I)),
            soup.find("meta", attrs={"name": "author"}),
            soup.find("meta", attrs={"property": "article:author"}),
            soup.find("a", attrs={"rel": "author"}),
        ]
        for author_elem in author_patterns:
            if author_elem:
                if hasattr(author_elem, "get_text"):
                    author = author_elem.get_text(strip=True)
                elif author_elem.get("content"):
                    author = author_elem.get("content")
                if author:
                    break

        # Extract tags
        tags = []
        tag_elems = soup.select(
            'a[rel="tag"], .tags a, .tag-list a, meta[property="article:tag"]'
        )
        for tag_elem in tag_elems:
            if hasattr(tag_elem, "get_text"):
                tag = tag_elem.get_text(strip=True)
            else:
                tag = tag_elem.get("content", "")
            if tag and tag not in tags:
                tags.append(tag)

        return title, content, author, tags[:10]  # Limit tags

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
            soup.find("meta", attrs={"name": "DC.date.issued"}),
        ]

        for meta in date_metas:
            if meta and meta.get("content"):
                try:
                    date_str = meta["content"]
                    # Handle various ISO formats
                    date_str = date_str.replace("Z", "+00:00")
                    return datetime.fromisoformat(date_str)
                except (ValueError, TypeError):
                    continue

        if time_elem := soup.find("time"):
            if datetime_attr := time_elem.get("datetime"):
                try:
                    return datetime.fromisoformat(datetime_attr.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

        if script_ld := soup.find("script", type="application/ld+json"):
            try:
                import json

                ld_data = json.loads(script_ld.string)
                if isinstance(ld_data, list):
                    ld_data = ld_data[0] if ld_data else {}
                if date_str := ld_data.get("datePublished") or ld_data.get(
                    "dateCreated"
                ):
                    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                pass

        return None

    async def fetch_article(
        self, url: str, source_config: Optional[Dict[str, Any]] = None
    ) -> Optional[TechBlogArticle]:
        """
        Fetch and parse a single article.

        Args:
            url: Article URL
            source_config: Optional source configuration for parsing

        Returns:
            TechBlogArticle or None on failure
        """
        html = await self._fetch_url(url)
        if not html:
            return None

        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception as e:
            logger.warning(f"Failed to parse HTML for {url}: {e}")
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
                "category": "tech_blog",
            }

        title, content, author, tags = self._extract_article_content(
            soup, source_config
        )
        published_at = self._extract_published_date(soup)

        if not title or not content:
            logger.warning(f"Could not extract title/content from {url}")
            return None

        # Create excerpt from first 200 chars of content
        excerpt = f"{content[:200]}..." if len(content) > 200 else content

        return TechBlogArticle(
            url=url,
            title=title,
            content=content,
            source_name=source_config.get("name", "Unknown"),
            source_category=source_config.get("category", "tech_blog"),
            published_at=published_at,
            author=author,
            excerpt=excerpt,
            tags=tags,
            relevance=0.7,
            metadata={"fetched_at": datetime.now(timezone.utc).isoformat()},
        )

    async def fetch_from_rss(
        self, source_config: Dict[str, Any], max_articles: int = 10
    ) -> List[TechBlogArticle]:
        """
        Fetch articles from RSS feed of a tech blog.

        Args:
            source_config: Source configuration with rss_url
            max_articles: Maximum articles to return

        Returns:
            List of TechBlogArticle objects
        """
        rss_url = source_config.get("rss_url")
        if not rss_url:
            return []

        source_name = source_config.get("name", "Unknown")
        logger.info(f"Fetching RSS feed from {source_name}: {rss_url}")

        html = await self._fetch_url(rss_url)
        if not html:
            logger.warning(f"Failed to fetch RSS feed from {source_name}")
            return []

        try:
            feed = feedparser.parse(html)
        except Exception as e:
            logger.warning(f"Failed to parse RSS feed from {source_name}: {e}")
            return []

        articles = []
        for entry in feed.entries[:max_articles]:
            try:
                url = entry.get("link", "")
                if not url:
                    continue

                title = entry.get("title", "Untitled")

                # Get content from entry
                content = ""
                if entry.get("content"):
                    content = entry.content[0].get("value", "")
                elif entry.get("summary"):
                    content = entry.summary

                # Sanitize HTML content
                if content:
                    content_soup = BeautifulSoup(content, "html.parser")
                    content = content_soup.get_text(separator="\n\n", strip=True)
                    content = content[:MAX_CONTENT_LENGTH]

                # Parse date
                published_at = None
                if entry.get("published_parsed"):
                    try:
                        published_at = datetime(*entry.published_parsed[:6])
                    except (ValueError, TypeError):
                        pass

                # Extract author
                author = entry.get("author", None)

                # Extract tags
                tags = []
                for tag in entry.get("tags", []):
                    if isinstance(tag, dict):
                        if term := tag.get("term", ""):
                            tags.append(term)

                article = TechBlogArticle(
                    url=url,
                    title=title,
                    content=content,
                    source_name=source_name,
                    source_category=source_config.get("category", "tech_blog"),
                    published_at=published_at,
                    author=author,
                    excerpt=(f"{content[:200]}..." if len(content) > 200 else content),
                    tags=tags[:10],
                    relevance=0.7,
                    metadata={
                        "feed_url": rss_url,
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                articles.append(article)

            except Exception as e:
                logger.warning(f"Failed to parse RSS entry from {source_name}: {e}")
                continue

        logger.info(f"Fetched {len(articles)} articles from {source_name} RSS feed")
        return articles

    async def search_source(
        self, source_config: Dict[str, Any], query: str, max_articles: int = 5
    ) -> List[TechBlogArticle]:
        """
        Search a tech blog for articles matching a query.

        Falls back to RSS feed if search is not available or fails.

        Args:
            source_config: Source configuration
            query: Search query
            max_articles: Maximum articles to return

        Returns:
            List of TechBlogArticle objects
        """
        source_name = source_config.get("name", "Unknown")
        search_url_template = source_config.get("search_url")

        # If no search URL, fall back to RSS
        if not search_url_template:
            return await self.fetch_from_rss(source_config, max_articles)

        search_url = search_url_template.format(query=quote_plus(query))
        logger.info(f"Searching {source_name} for: {query}")

        html = await self._fetch_url(search_url)
        if not html:
            logger.warning(f"Search failed for {source_name}, falling back to RSS")
            return await self.fetch_from_rss(source_config, max_articles)

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
            skip_patterns = [
                "#",
                "javascript:",
                "mailto:",
                "/tag/",
                "/category/",
                "/author/",
                "/page/",
                "/feed/",
                "/search/",
            ]
            if any(skip in href for skip in skip_patterns):
                continue

            seen_urls.add(href)
            article_urls.append(href)

            if len(article_urls) >= max_articles * 2:
                break

        if not article_urls:
            logger.warning(
                f"No articles found in search for {source_name}, falling back to RSS"
            )
            return await self.fetch_from_rss(source_config, max_articles)

        logger.info(f"Found {len(article_urls)} potential articles from {source_name}")

        # Fetch articles concurrently
        tasks = [
            self.fetch_article(url, source_config)
            for url in article_urls[: max_articles * 2]
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        articles = []
        for result in results:
            if isinstance(result, TechBlogArticle):
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
        max_total_articles: int = 20,
    ) -> List[TechBlogArticle]:
        """
        Fetch articles from all configured tech blog sources.

        Args:
            topics: List of search topics/keywords
            max_articles_per_source: Max articles per source per topic
            max_total_articles: Maximum total articles to return

        Returns:
            List of TechBlogArticle objects from all sources
        """
        all_articles: List[TechBlogArticle] = []
        seen_urls: set = set()

        # Sort sources by priority
        sorted_sources = sorted(self.sources, key=lambda x: x.get("priority", 99))

        for topic in topics:
            for source_config in sorted_sources:
                if len(all_articles) >= max_total_articles:
                    break

                try:
                    articles = await self.search_source(
                        source_config, topic, max_articles=max_articles_per_source
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
                    continue

        logger.info(f"Total articles fetched from tech blogs: {len(all_articles)}")
        return all_articles


# ============================================================================
# Convenience Functions
# ============================================================================


async def fetch_tech_blog_articles(
    topics: Optional[List[str]] = None,
    urls: Optional[List[str]] = None,
    max_articles: int = 20,
    sources: Optional[List[Dict[str, Any]]] = None,
    include_rss_only: bool = False,
) -> List[TechBlogArticle]:
    """
    Fetch tech blog articles from major tech publications.

    This is the main entry point for fetching tech blog articles. It can either:
    1. Search configured tech blogs for topics
    2. Fetch specific URLs directly
    3. Fetch from RSS feeds only

    Args:
        topics: List of search topics (e.g., ["smart city", "municipal AI"])
        urls: List of specific article URLs to fetch
        max_articles: Maximum number of articles to return
        sources: Optional custom source configurations
        include_rss_only: If True, fetch from RSS feeds without search

    Returns:
        List of TechBlogArticle objects

    Example:
        >>> articles = await fetch_tech_blog_articles(
        ...     topics=["smart city technology", "municipal innovation"],
        ...     max_articles=10
        ... )
        >>> for article in articles:
        ...     print(f"{article.title} - {article.source_name}")
    """
    async with TechBlogFetcher(sources=sources) as fetcher:
        articles: List[TechBlogArticle] = []

        # Fetch from RSS only if requested
        if include_rss_only:
            for source_config in fetcher.sources:
                if len(articles) >= max_articles:
                    break
                rss_articles = await fetcher.fetch_from_rss(
                    source_config, max_articles=5
                )
                articles.extend(rss_articles)

        # Fetch by topics if provided
        elif topics:
            topic_articles = await fetcher.fetch_from_all_sources(
                topics=topics, max_total_articles=max_articles
            )
            articles.extend(topic_articles)

        # Fetch specific URLs if provided
        if urls:
            url_tasks = [fetcher.fetch_article(url) for url in urls[:max_articles]]
            url_results = await asyncio.gather(*url_tasks, return_exceptions=True)

            for result in url_results:
                if isinstance(result, TechBlogArticle):
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


async def fetch_tech_blog_rss_feeds(
    feed_urls: Optional[List[str]] = None, max_articles_per_feed: int = 10
) -> List[TechBlogArticle]:
    """
    Fetch articles from tech blog RSS feeds.

    Args:
        feed_urls: List of RSS feed URLs (uses default tech feeds if None)
        max_articles_per_feed: Maximum articles per feed

    Returns:
        List of TechBlogArticle objects
    """
    # Default feeds if none provided
    if feed_urls is None:
        feed_urls = [s.get("rss_url") for s in TECH_BLOG_SOURCES if s.get("rss_url")]

    async with TechBlogFetcher() as fetcher:
        all_articles: List[TechBlogArticle] = []
        seen_urls: set = set()

        for feed_url in feed_urls:
            if not feed_url:
                continue

            source_config = next(
                (src for src in TECH_BLOG_SOURCES if src.get("rss_url") == feed_url),
                None,
            )
            if source_config is None:
                source_config = {
                    "name": urlparse(feed_url).netloc,
                    "rss_url": feed_url,
                    "category": "tech_blog",
                }

            articles = await fetcher.fetch_from_rss(
                source_config, max_articles_per_feed
            )

            for article in articles:
                if article.url not in seen_urls:
                    seen_urls.add(article.url)
                    all_articles.append(article)

        return all_articles


async def fetch_articles_from_urls(urls: List[str]) -> List[TechBlogArticle]:
    """
    Fetch articles from a list of specific URLs.

    Args:
        urls: List of article URLs to fetch

    Returns:
        List of successfully fetched TechBlogArticle objects
    """
    async with TechBlogFetcher() as fetcher:
        tasks = [fetcher.fetch_article(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return [result for result in results if isinstance(result, TechBlogArticle)]
