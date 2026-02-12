"""
Government source fetcher for .gov domains and policy documents.

This module fetches content from government sources including federal, state,
and local government websites, policy documents, and official announcements.
Focuses on municipal-relevant content for strategic planning.

Features:
- Search and fetch from .gov domains
- Parse government press releases and policy documents
- Support for multiple government source types
- Graceful error handling with retry logic
- RSS feeds from government agencies

Usage:
    from backend.app.source_fetchers.government_fetcher import fetch_government_sources

    documents = await fetch_government_sources(
        topics=["smart city", "municipal technology"],
        max_results=20
    )
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
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
MAX_CONTENT_LENGTH = 15000

# User agent for government site requests
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 "
    "Foresight-Research-Bot/1.0"
)

# Government source configurations
GOVERNMENT_SOURCES: List[Dict[str, Any]] = [
    {
        "name": "USA.gov",
        "base_url": "https://www.usa.gov",
        "search_url": "https://www.usa.gov/search?query={query}",
        "rss_url": None,
        "article_selector": "article, .content-block, .usa-prose",
        "title_selector": "h1",
        "content_selector": "article p, .content-block p, .usa-prose p",
        "link_selector": "a[href*='usa.gov']",
        "category": "government",
        "subcategory": "federal",
    },
    {
        "name": "Data.gov",
        "base_url": "https://data.gov",
        "search_url": "https://catalog.data.gov/dataset?q={query}",
        "rss_url": None,
        "article_selector": ".dataset-content, .module-content",
        "title_selector": "h1, .dataset-heading",
        "content_selector": ".notes p, .dataset-content p",
        "link_selector": "a[href*='/dataset/']",
        "category": "government",
        "subcategory": "data",
    },
    {
        "name": "GSA (General Services Administration)",
        "base_url": "https://www.gsa.gov",
        "search_url": "https://www.gsa.gov/search?search={query}",
        "rss_url": "https://www.gsa.gov/about-us/newsroom/news-releases/rss",
        "article_selector": "article, .main-content",
        "title_selector": "h1",
        "content_selector": "article p, .main-content p",
        "link_selector": "a[href*='gsa.gov']",
        "category": "government",
        "subcategory": "federal",
    },
    {
        "name": "NIST (National Institute of Standards and Technology)",
        "base_url": "https://www.nist.gov",
        "search_url": "https://www.nist.gov/search?s={query}",
        "rss_url": "https://www.nist.gov/news-events/news/rss.xml",
        "article_selector": "article, .main-content",
        "title_selector": "h1",
        "content_selector": "article p, .main-content p, .field-body p",
        "link_selector": "a[href*='nist.gov']",
        "category": "government",
        "subcategory": "standards",
    },
    {
        "name": "Digital.gov",
        "base_url": "https://digital.gov",
        "search_url": "https://digital.gov/search/?query={query}",
        "rss_url": "https://digital.gov/index.xml",
        "article_selector": "article, .content",
        "title_selector": "h1",
        "content_selector": "article p, .content p",
        "link_selector": "a[href*='digital.gov']",
        "category": "government",
        "subcategory": "digital",
    },
    {
        "name": "Census Bureau",
        "base_url": "https://www.census.gov",
        "search_url": "https://www.census.gov/search-results.html?q={query}",
        "rss_url": "https://www.census.gov/content/census/en/newsroom/press-releases.rss.xml",
        "article_selector": "article, .uscb-layout-column-main",
        "title_selector": "h1",
        "content_selector": "article p, .uscb-layout-column-main p",
        "link_selector": "a[href*='census.gov']",
        "category": "government",
        "subcategory": "data",
    },
    {
        "name": "HUD (Housing and Urban Development)",
        "base_url": "https://www.hud.gov",
        "search_url": "https://www.hud.gov/search/site/{query}",
        "rss_url": "https://www.hud.gov/rss/pressreleases.xml",
        "article_selector": "article, .content-main",
        "title_selector": "h1",
        "content_selector": "article p, .content-main p",
        "link_selector": "a[href*='hud.gov']",
        "category": "government",
        "subcategory": "housing",
    },
    {
        "name": "DOT (Department of Transportation)",
        "base_url": "https://www.transportation.gov",
        "search_url": "https://www.transportation.gov/search?search={query}",
        "rss_url": "https://www.transportation.gov/rss/briefing-room/all",
        "article_selector": "article, .node-content",
        "title_selector": "h1",
        "content_selector": "article p, .node-content p, .field-body p",
        "link_selector": "a[href*='transportation.gov']",
        "category": "government",
        "subcategory": "transportation",
    },
    {
        "name": "EPA (Environmental Protection Agency)",
        "base_url": "https://www.epa.gov",
        "search_url": "https://www.epa.gov/search?search={query}",
        "rss_url": "https://www.epa.gov/newsreleases/rss.xml",
        "article_selector": "article, .main-content",
        "title_selector": "h1",
        "content_selector": "article p, .main-content p",
        "link_selector": "a[href*='epa.gov']",
        "category": "government",
        "subcategory": "environment",
    },
    {
        "name": "FCC (Federal Communications Commission)",
        "base_url": "https://www.fcc.gov",
        "search_url": "https://www.fcc.gov/search#q={query}",
        "rss_url": "https://www.fcc.gov/news-events/rss.xml",
        "article_selector": "article, .node-content",
        "title_selector": "h1",
        "content_selector": "article p, .node-content p",
        "link_selector": "a[href*='fcc.gov']",
        "category": "government",
        "subcategory": "communications",
    },
]

# Municipal-relevant search terms for government sources
MUNICIPAL_SEARCH_TERMS = [
    "smart city",
    "municipal technology",
    "local government innovation",
    "city services",
    "urban planning technology",
    "digital government",
    "public sector AI",
    "civic technology",
    "government modernization",
    "municipal broadband",
]


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class GovernmentDocument:
    """Represents a document from a government source."""
    url: str
    title: str
    content: str
    source_name: str
    source_category: str = "government"
    subcategory: str = "federal"
    published_at: Optional[datetime] = None
    agency: Optional[str] = None
    document_type: Optional[str] = None
    excerpt: Optional[str] = None
    relevance: float = 0.75
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "source_name": self.source_name,
            "source_category": self.source_category,
            "subcategory": self.subcategory,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "agency": self.agency,
            "document_type": self.document_type,
            "excerpt": self.excerpt,
            "relevance": self.relevance,
            "metadata": self.metadata,
        }


@dataclass
class GovernmentFetchResult:
    """Result of a government source fetch operation."""
    documents: List[GovernmentDocument]
    total_fetched: int
    sources_queried: int
    fetch_time: float
    errors: List[str]


# ============================================================================
# Government Fetcher Class
# ============================================================================

class GovernmentFetcher:
    """
    Fetches content from government sources using BeautifulSoup.

    Features:
    - Async HTTP requests with aiohttp
    - BeautifulSoup HTML parsing with lxml
    - Configurable government sources
    - Robust error handling with graceful degradation
    - Content extraction with fallback selectors
    - RSS feed support for agencies with feeds
    """

    def __init__(
        self,
        sources: Optional[List[Dict[str, Any]]] = None,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = 3,
    ):
        """
        Initialize the government fetcher.

        Args:
            sources: List of government source configurations
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
        """
        self.sources = sources or GOVERNMENT_SOURCES
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
                async with session.get(url, allow_redirects=True) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 429:
                        # Rate limited - wait and retry
                        wait_time = 2 ** attempt
                        logger.warning(f"Rate limited on {url}, waiting {wait_time}s")
                        await asyncio.sleep(wait_time)
                    elif response.status in (403, 451):
                        # Forbidden or blocked - don't retry
                        logger.warning(f"Access denied ({response.status}) for {url}")
                        return None
                    else:
                        logger.warning(f"HTTP {response.status} for {url}")
                        if response.status >= 500:
                            # Server error - retry
                            await asyncio.sleep(1)
                        else:
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

    def _extract_document_content(
        self,
        soup: BeautifulSoup,
        source_config: Dict[str, Any]
    ) -> tuple[str, str, Optional[str]]:
        """
        Extract title, content, and document type from parsed HTML.

        Args:
            soup: BeautifulSoup parsed HTML
            source_config: Source configuration with selectors

        Returns:
            Tuple of (title, content, document_type)
        """
        # Extract title
        title = ""
        if title_elem := soup.select_one(
            source_config.get("title_selector", "h1")
        ):
            title = title_elem.get_text(strip=True)

        # Fallback title extraction
        if not title:
            if title_elem := soup.find("title"):
                title = title_elem.get_text(strip=True)
                # Clean up common title suffixes
                title = re.sub(r'\s*\|\s*[^|]+$', '', title)

        # Extract content
        content = ""
        content_selector = source_config.get("content_selector", "article p")
        if content_elems := soup.select(content_selector):
            paragraphs = [elem.get_text(strip=True) for elem in content_elems]
            content = "\n\n".join(p for p in paragraphs if p and len(p) > 20)

        # Fallback content extraction
        if not content or len(content) < 100:
            # Try main content areas common in government sites
            for selector in ["main", "article", "#content", ".content", ".main-content"]:
                if main_content := soup.select_one(selector):
                    # Remove navigation, headers, footers
                    for elem in main_content(["nav", "header", "footer", "aside", "script", "style"]):
                        elem.decompose()
                    content = main_content.get_text(separator="\n\n", strip=True)
                    if len(content) > 100:
                        break

        # Truncate content if too long
        if len(content) > MAX_CONTENT_LENGTH:
            content = f"{content[:MAX_CONTENT_LENGTH]}..."

        # Detect document type
        document_type = self._detect_document_type(soup, content)

        return title, content, document_type

    def _detect_document_type(self, soup: BeautifulSoup, content: str) -> Optional[str]:
        """
        Detect the type of government document.

        Args:
            soup: BeautifulSoup parsed HTML
            content: Extracted content

        Returns:
            Document type string or None
        """
        # Check meta tags
        doc_type_meta = soup.find("meta", attrs={"name": "dc.type"})
        if doc_type_meta and doc_type_meta.get("content"):
            return doc_type_meta["content"]

        # Infer from URL and content
        url = soup.find("link", rel="canonical")
        url_str = url.get("href", "") if url else ""

        content_lower = content.lower()[:1000]

        if any(kw in url_str.lower() for kw in ["press-release", "newsroom", "news"]):
            return "press_release"
        elif any(kw in url_str.lower() for kw in ["policy", "guidance", "directive"]):
            return "policy_document"
        elif any(kw in url_str.lower() for kw in ["report", "publication"]):
            return "report"
        elif any(kw in url_str.lower() for kw in ["dataset", "data"]):
            return "dataset"
        elif "public comment" in content_lower or "federal register" in content_lower:
            return "public_notice"
        elif "grant" in content_lower and ("funding" in content_lower or "opportunity" in content_lower):
            return "grant_announcement"

        return "general"

    def _extract_published_date(self, soup: BeautifulSoup) -> Optional[datetime]:
        """
        Extract publication date from government document HTML.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            Datetime object or None
        """
        # Try meta tags first (common in government sites)
        date_metas = [
            soup.find("meta", attrs={"name": "DC.date.created"}),
            soup.find("meta", attrs={"name": "DC.date.modified"}),
            soup.find("meta", attrs={"name": "dcterms.created"}),
            soup.find("meta", attrs={"property": "article:published_time"}),
            soup.find("meta", attrs={"name": "date"}),
            soup.find("meta", attrs={"name": "pubdate"}),
        ]

        for meta in date_metas:
            if meta and meta.get("content"):
                try:
                    date_str = meta["content"]
                    # Handle various date formats
                    for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%B %d, %Y", "%m/%d/%Y"]:
                        try:
                            return datetime.strptime(date_str[:len(fmt) + 5], fmt)
                        except ValueError:
                            continue
                    # Try ISO format
                    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    continue

        if time_elem := soup.find("time"):
            if datetime_attr := time_elem.get("datetime"):
                try:
                    return datetime.fromisoformat(datetime_attr.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

        # Try common date class patterns in government sites
        date_patterns = [".date", ".publish-date", ".post-date", ".release-date"]
        for pattern in date_patterns:
            if date_elem := soup.select_one(pattern):
                date_text = date_elem.get_text(strip=True)
                # Try to parse common formats
                for fmt in ["%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%Y-%m-%d"]:
                    try:
                        return datetime.strptime(date_text, fmt)
                    except ValueError:
                        continue

        return None

    async def fetch_document(
        self,
        url: str,
        source_config: Optional[Dict[str, Any]] = None
    ) -> Optional[GovernmentDocument]:
        """
        Fetch and parse a single government document.

        Args:
            url: Document URL
            source_config: Optional source configuration for parsing

        Returns:
            GovernmentDocument or None on failure
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
            parsed_url = urlparse(url)
            source_config = {
                "name": parsed_url.netloc,
                "title_selector": "h1",
                "content_selector": "article p, main p",
                "category": "government",
                "subcategory": "general",
            }

        title, content, document_type = self._extract_document_content(soup, source_config)
        published_at = self._extract_published_date(soup)

        if not title or not content:
            logger.warning(f"Could not extract title/content from {url}")
            return None

        # Create excerpt from first 200 chars of content
        excerpt = f"{content[:200]}..." if len(content) > 200 else content

        return GovernmentDocument(
            url=url,
            title=title,
            content=content,
            source_name=source_config.get("name", "Unknown"),
            source_category="government",
            subcategory=source_config.get("subcategory", "general"),
            published_at=published_at,
            agency=source_config.get("name"),
            document_type=document_type,
            excerpt=excerpt,
            relevance=0.75,
            metadata={
                "fetched_at": datetime.now().isoformat(),
                "base_url": source_config.get("base_url", ""),
            },
        )

    async def search_source(
        self,
        source_config: Dict[str, Any],
        query: str,
        max_documents: int = 5
    ) -> List[GovernmentDocument]:
        """
        Search a government source for documents matching a query.

        Args:
            source_config: Source configuration
            query: Search query
            max_documents: Maximum documents to return

        Returns:
            List of GovernmentDocument objects
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

        # Find document links
        link_selector = source_config.get("link_selector", "a[href*='.gov']")
        links = soup.select(link_selector)

        # Extract unique document URLs
        base_url = source_config.get("base_url", "")
        seen_urls = set()
        document_urls = []

        for link in links:
            href = link.get("href", "")
            if not href:
                continue

            # Make absolute URL
            if href.startswith("/"):
                href = urljoin(base_url, href)
            elif not href.startswith("http"):
                continue

            # Skip duplicates and non-document URLs
            if href in seen_urls:
                continue
            if any(skip in href for skip in [
                "#", "javascript:", "mailto:", "/search", "/login",
                "/signup", "/contact", ".pdf", ".zip", ".xlsx"
            ]):
                continue

            # Ensure it's a .gov domain
            if ".gov" not in urlparse(href).netloc:
                continue

            seen_urls.add(href)
            document_urls.append(href)

            if len(document_urls) >= max_documents * 2:  # Get extra in case some fail
                break

        logger.info(f"Found {len(document_urls)} potential documents from {source_name}")

        # Fetch documents concurrently
        tasks = [self.fetch_document(url, source_config) for url in document_urls[:max_documents * 2]]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        documents = []
        for result in results:
            if isinstance(result, GovernmentDocument):
                documents.append(result)
                if len(documents) >= max_documents:
                    break
            elif isinstance(result, Exception):
                logger.warning(f"Document fetch failed: {result}")

        logger.info(f"Successfully fetched {len(documents)} documents from {source_name}")
        return documents

    async def fetch_from_all_sources(
        self,
        topics: List[str],
        max_documents_per_source: int = 3,
        max_total_documents: int = 30
    ) -> List[GovernmentDocument]:
        """
        Fetch documents from all configured government sources.

        Args:
            topics: List of search topics/keywords
            max_documents_per_source: Max documents per source per topic
            max_total_documents: Maximum total documents to return

        Returns:
            List of GovernmentDocument objects from all sources
        """
        all_documents: List[GovernmentDocument] = []
        seen_urls: set = set()

        for topic in topics:
            for source_config in self.sources:
                if len(all_documents) >= max_total_documents:
                    break

                try:
                    documents = await self.search_source(
                        source_config,
                        topic,
                        max_documents=max_documents_per_source
                    )

                    for doc in documents:
                        if doc.url not in seen_urls:
                            seen_urls.add(doc.url)
                            all_documents.append(doc)

                            if len(all_documents) >= max_total_documents:
                                break

                except Exception as e:
                    source_name = source_config.get("name", "Unknown")
                    logger.error(f"Failed to fetch from {source_name}: {e}")
                    # Continue with other sources - graceful degradation
                    continue

        logger.info(f"Total documents fetched from government sources: {len(all_documents)}")
        return all_documents


# ============================================================================
# Convenience Functions
# ============================================================================

async def fetch_government_sources(
    topics: Optional[List[str]] = None,
    urls: Optional[List[str]] = None,
    max_results: int = 30,
    sources: Optional[List[Dict[str, Any]]] = None,
) -> List[GovernmentDocument]:
    """
    Fetch documents from government sources (.gov domains).

    This is the main entry point for fetching government content. It can either:
    1. Search configured government sources for topics
    2. Fetch specific URLs directly

    Args:
        topics: List of search topics (e.g., ["smart city", "municipal AI"])
        urls: List of specific document URLs to fetch
        max_results: Maximum number of documents to return
        sources: Optional custom source configurations

    Returns:
        List of GovernmentDocument objects

    Example:
        >>> documents = await fetch_government_sources(
        ...     topics=["smart city technology", "municipal innovation"],
        ...     max_results=20
        ... )
        >>> for doc in documents:
        ...     print(f"{doc.title} - {doc.agency}")
    """
    # Use default municipal search terms if no topics provided
    if topics is None and urls is None:
        topics = MUNICIPAL_SEARCH_TERMS[:3]  # Use first 3 default terms

    async with GovernmentFetcher(sources=sources) as fetcher:
        documents: List[GovernmentDocument] = []

        # Fetch by topics if provided
        if topics:
            topic_documents = await fetcher.fetch_from_all_sources(
                topics=topics,
                max_total_documents=max_results
            )
            documents.extend(topic_documents)

        # Fetch specific URLs if provided
        if urls:
            url_tasks = [fetcher.fetch_document(url) for url in urls[:max_results]]
            url_results = await asyncio.gather(*url_tasks, return_exceptions=True)

            for result in url_results:
                if isinstance(result, GovernmentDocument):
                    documents.append(result)
                elif isinstance(result, Exception):
                    logger.warning(f"Failed to fetch URL: {result}")

        # Remove duplicates by URL
        seen = set()
        unique_documents = []
        for doc in documents:
            if doc.url not in seen:
                seen.add(doc.url)
                unique_documents.append(doc)

        return unique_documents[:max_results]


async def fetch_documents_from_urls(urls: List[str]) -> List[GovernmentDocument]:
    """
    Fetch government documents from a list of specific URLs.

    Args:
        urls: List of government document URLs to fetch

    Returns:
        List of successfully fetched GovernmentDocument objects
    """
    async with GovernmentFetcher() as fetcher:
        tasks = [fetcher.fetch_document(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return [result for result in results if isinstance(result, GovernmentDocument)]


async def fetch_municipal_government_content(
    max_results: int = 30,
    additional_topics: Optional[List[str]] = None
) -> List[GovernmentDocument]:
    """
    Fetch government content specifically relevant to municipal planning.

    This function uses predefined municipal-relevant search terms
    to find government content useful for city strategic planning.

    Args:
        max_results: Maximum documents to return
        additional_topics: Additional search topics to include

    Returns:
        List of GovernmentDocument objects
    """
    topics = MUNICIPAL_SEARCH_TERMS.copy()
    if additional_topics:
        topics.extend(additional_topics)

    # Limit topics to avoid too many requests
    topics = topics[:5]

    return await fetch_government_sources(
        topics=topics,
        max_results=max_results
    )


def convert_to_raw_source(document: GovernmentDocument) -> Dict[str, Any]:
    """
    Convert a GovernmentDocument to a format compatible with the research pipeline.

    This allows government documents to be processed through the same pipeline
    as other content sources.

    Args:
        document: GovernmentDocument instance

    Returns:
        Dict matching RawSource structure
    """
    # Construct enhanced content with metadata
    content = f"""
Title: {document.title}

Agency: {document.agency or 'Unknown Agency'}

Document Type: {document.document_type or 'General'}

{document.content}
"""

    return {
        "url": document.url,
        "title": document.title,
        "content": content.strip(),
        "source_name": document.source_name,
        "source_category": "government",
        "relevance": document.relevance,
        "metadata": {
            "agency": document.agency,
            "subcategory": document.subcategory,
            "document_type": document.document_type,
            "published_at": document.published_at.isoformat() if document.published_at else None,
            **document.metadata,
        }
    }


async def fetch_and_convert_documents(
    topics: Optional[List[str]] = None,
    max_results: int = 20
) -> List[Dict[str, Any]]:
    """
    Convenience function to fetch government documents and convert to raw source format.

    This is the recommended function for integration with the research pipeline.

    Args:
        topics: Search query terms
        max_results: Maximum documents to return

    Returns:
        List of source dicts compatible with research pipeline
    """
    documents = await fetch_government_sources(
        topics=topics,
        max_results=max_results
    )

    return [convert_to_raw_source(doc) for doc in documents]
