"""
Academic publication fetcher with arXiv API integration.

This module fetches academic papers from arXiv, a free open-access repository
of scientific papers. The arXiv API returns Atom XML feeds which are parsed
using feedparser for consistent handling.

Features:
- Search arXiv for papers by query terms
- Filter by category (cs.AI, cs.LG, etc.)
- Support for date range filtering
- Configurable result limits
- Graceful error handling with retry logic

Usage:
    papers = await fetch_academic_papers(
        query="municipal technology",
        categories=["cs.AI", "cs.CY"],
        max_results=10
    )
"""

import asyncio
import logging
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import aiohttp
import feedparser

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class AcademicPaper:
    """Represents an academic paper from arXiv."""
    arxiv_id: str
    title: str
    abstract: str
    authors: List[str]
    published_date: str
    updated_date: Optional[str]
    categories: List[str]
    primary_category: str
    pdf_url: str
    arxiv_url: str
    source_category: str = "academic"


@dataclass
class AcademicFetchResult:
    """Result of an academic paper fetch operation."""
    papers: List[AcademicPaper]
    total_results: int
    query: str
    fetch_time: float
    errors: List[str]


# ============================================================================
# Constants
# ============================================================================

ARXIV_API_BASE = "http://export.arxiv.org/api/query"

# Default categories relevant to municipal technology and strategic planning
DEFAULT_CATEGORIES = [
    "cs.AI",    # Artificial Intelligence
    "cs.CY",    # Computers and Society
    "cs.LG",    # Machine Learning
    "cs.SI",    # Social and Information Networks
    "cs.HC",    # Human-Computer Interaction
    "econ.GN",  # General Economics
    "stat.ML",  # Machine Learning (Statistics)
]

# Municipal and government-relevant search terms
MUNICIPAL_SEARCH_TERMS = [
    "smart city",
    "municipal government",
    "urban planning",
    "public policy",
    "civic technology",
    "government automation",
    "public sector innovation",
]


# ============================================================================
# Helper Functions
# ============================================================================

def _build_arxiv_query(
    query: str,
    categories: Optional[List[str]] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> str:
    """
    Build an arXiv API search query string.

    Args:
        query: Main search terms
        categories: arXiv category codes (e.g., cs.AI)
        date_from: Start date for filtering
        date_to: End date for filtering

    Returns:
        URL-encoded query string for arXiv API
    """
    query_parts = []

    # Main search query (searches title and abstract)
    if query:
        # Escape special characters and wrap in search field
        clean_query = query.replace('"', '\\"')
        query_parts.append(f'all:"{clean_query}"')

    # Category filter
    if categories:
        cat_filter = " OR ".join([f"cat:{cat}" for cat in categories])
        if len(categories) > 1:
            query_parts.append(f"({cat_filter})")
        else:
            query_parts.append(cat_filter)

    return " AND ".join(query_parts) if query_parts else "cat:cs.AI"


def _parse_arxiv_entry(entry: Dict[str, Any]) -> Optional[AcademicPaper]:
    """
    Parse a single arXiv Atom entry into an AcademicPaper.

    Args:
        entry: Parsed feedparser entry

    Returns:
        AcademicPaper or None if parsing fails
    """
    try:
        # Extract arXiv ID from the entry ID URL
        entry_id = entry.get("id", "")
        arxiv_id = entry_id.split("/abs/")[-1] if "/abs/" in entry_id else entry_id

        # Extract authors
        authors = []
        author_list = entry.get("authors", [])
        for author in author_list:
            name = author.get("name", "")
            if name:
                authors.append(name)

        # Extract categories
        categories = []
        primary_category = ""
        tags = entry.get("tags", [])
        for tag in tags:
            term = tag.get("term", "")
            if term:
                categories.append(term)
                # First tag is usually primary category
                if not primary_category:
                    primary_category = term

        # Also check arxiv_primary_category if available
        if hasattr(entry, "arxiv_primary_category"):
            primary_category = entry.arxiv_primary_category.get("term", primary_category)

        # Extract dates
        published = entry.get("published", "")
        updated = entry.get("updated", "")

        # Find PDF link
        pdf_url = ""
        links = entry.get("links", [])
        for link in links:
            if link.get("type") == "application/pdf":
                pdf_url = link.get("href", "")
                break
            elif link.get("title") == "pdf":
                pdf_url = link.get("href", "")
                break

        # Fallback PDF URL construction
        if not pdf_url and arxiv_id:
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        # Construct arXiv abstract URL
        arxiv_url = f"https://arxiv.org/abs/{arxiv_id}"

        # Get abstract (summary)
        abstract = entry.get("summary", "")
        # Clean up abstract - remove extra whitespace
        abstract = " ".join(abstract.split())

        return AcademicPaper(
            arxiv_id=arxiv_id,
            title=entry.get("title", "Untitled"),
            abstract=abstract,
            authors=authors,
            published_date=published,
            updated_date=updated if updated != published else None,
            categories=categories,
            primary_category=primary_category,
            pdf_url=pdf_url,
            arxiv_url=arxiv_url,
            source_category="academic"
        )

    except Exception as e:
        logger.warning(f"Failed to parse arXiv entry: {e}")
        return None


# ============================================================================
# Main Fetcher Functions
# ============================================================================

async def fetch_academic_papers(
    query: str = "",
    categories: Optional[List[str]] = None,
    max_results: int = 20,
    start: int = 0,
    sort_by: str = "relevance",
    sort_order: str = "descending",
    timeout: int = 30,
    retry_count: int = 3,
    retry_delay: float = 1.0
) -> AcademicFetchResult:
    """
    Fetch academic papers from arXiv API.

    Args:
        query: Search query terms (searches title, abstract, authors)
        categories: List of arXiv category codes (e.g., ["cs.AI", "cs.CY"])
        max_results: Maximum number of results to return (default: 20, max: 100)
        start: Starting index for pagination
        sort_by: Sort field - "relevance", "lastUpdatedDate", or "submittedDate"
        sort_order: "ascending" or "descending"
        timeout: Request timeout in seconds
        retry_count: Number of retries on failure
        retry_delay: Delay between retries in seconds (doubles each retry)

    Returns:
        AcademicFetchResult containing papers, metadata, and any errors
    """
    start_time = datetime.now()
    errors = []
    papers = []

    # Validate and cap max_results
    max_results = min(max_results, 100)  # arXiv API limit

    # Use default categories if none provided
    if not categories:
        categories = DEFAULT_CATEGORIES

    # Build query
    search_query = _build_arxiv_query(query, categories)

    # Build API URL
    params = {
        "search_query": search_query,
        "start": start,
        "max_results": max_results,
        "sortBy": sort_by,
        "sortOrder": sort_order,
    }
    url = f"{ARXIV_API_BASE}?{urllib.parse.urlencode(params)}"

    logger.info(f"Fetching arXiv papers: query='{query}', categories={categories}, max={max_results}")
    logger.debug(f"arXiv API URL: {url}")

    # Fetch with retry logic
    current_delay = retry_delay
    for attempt in range(retry_count):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    headers={"User-Agent": "Foresight-App/1.0 (Research Pipeline)"}
                ) as response:
                    if response.status == 200:
                        content = await response.text()

                        # Parse Atom feed
                        feed = feedparser.parse(content)

                        # Check for feed parsing errors
                        if feed.bozo:
                            logger.warning(f"arXiv feed parsing warning: {feed.bozo_exception}")
                            errors.append(f"Feed parsing warning: {str(feed.bozo_exception)[:100]}")

                        # Extract total results from feed
                        total_results = 0
                        if hasattr(feed.feed, "opensearch_totalresults"):
                            try:
                                total_results = int(feed.feed.opensearch_totalresults)
                            except (ValueError, TypeError):
                                total_results = len(feed.entries)
                        else:
                            total_results = len(feed.entries)

                        # Parse entries
                        for entry in feed.entries:
                            paper = _parse_arxiv_entry(entry)
                            if paper:
                                papers.append(paper)

                        logger.info(f"arXiv fetch successful: {len(papers)} papers from {total_results} total")
                        break

                    elif response.status == 503:
                        # arXiv rate limiting
                        logger.warning(f"arXiv rate limit hit (attempt {attempt + 1}/{retry_count})")
                        errors.append(f"Rate limit hit on attempt {attempt + 1}")
                        if attempt < retry_count - 1:
                            await asyncio.sleep(current_delay)
                            current_delay *= 2

                    else:
                        error_msg = f"arXiv API error: status {response.status}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        break

        except asyncio.TimeoutError:
            error_msg = f"arXiv request timeout (attempt {attempt + 1}/{retry_count})"
            logger.warning(error_msg)
            errors.append(error_msg)
            if attempt < retry_count - 1:
                await asyncio.sleep(current_delay)
                current_delay *= 2

        except aiohttp.ClientError as e:
            error_msg = f"arXiv connection error: {str(e)[:100]}"
            logger.warning(f"{error_msg} (attempt {attempt + 1}/{retry_count})")
            errors.append(error_msg)
            if attempt < retry_count - 1:
                await asyncio.sleep(current_delay)
                current_delay *= 2

        except Exception as e:
            error_msg = f"arXiv fetch error: {str(e)[:100]}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)
            break

    fetch_time = (datetime.now() - start_time).total_seconds()

    return AcademicFetchResult(
        papers=papers,
        total_results=total_results if papers else 0,
        query=query,
        fetch_time=fetch_time,
        errors=errors
    )


async def fetch_recent_papers(
    categories: Optional[List[str]] = None,
    days_back: int = 7,
    max_results: int = 50
) -> AcademicFetchResult:
    """
    Fetch recently published papers from specified categories.

    This is useful for horizon scanning and discovering new research
    in relevant fields.

    Args:
        categories: arXiv category codes to search
        days_back: How many days back to search (default: 7)
        max_results: Maximum papers to return

    Returns:
        AcademicFetchResult with recent papers
    """
    if not categories:
        categories = DEFAULT_CATEGORIES

    # arXiv doesn't have date range in API, so we fetch by lastUpdatedDate
    # and filter client-side if needed
    return await fetch_academic_papers(
        query="",  # Empty query to get all from categories
        categories=categories,
        max_results=max_results,
        sort_by="submittedDate",
        sort_order="descending"
    )


async def fetch_municipal_tech_papers(
    max_results: int = 30,
    additional_terms: Optional[List[str]] = None
) -> AcademicFetchResult:
    """
    Fetch papers specifically relevant to municipal technology and smart cities.

    This function combines municipal-specific search terms with relevant
    categories to find academic research useful for city strategic planning.

    Args:
        max_results: Maximum papers to return
        additional_terms: Additional search terms to include

    Returns:
        AcademicFetchResult with municipal-relevant papers
    """
    # Combine default municipal terms with any additional terms
    search_terms = MUNICIPAL_SEARCH_TERMS.copy()
    if additional_terms:
        search_terms.extend(additional_terms)

    # Build combined query
    query = " OR ".join([f'"{term}"' for term in search_terms[:5]])  # Limit to avoid too long query

    # Focus on categories most relevant to municipal applications
    municipal_categories = [
        "cs.CY",    # Computers and Society - most relevant
        "cs.AI",    # AI applications
        "cs.HC",    # Human-Computer Interaction
        "econ.GN",  # Economics
    ]

    return await fetch_academic_papers(
        query=query,
        categories=municipal_categories,
        max_results=max_results,
        sort_by="relevance"
    )


def convert_to_raw_source(paper: AcademicPaper) -> Dict[str, Any]:
    """
    Convert an AcademicPaper to a format compatible with the research pipeline.

    This allows academic papers to be processed through the same pipeline
    as other content sources.

    Args:
        paper: AcademicPaper instance

    Returns:
        Dict matching RawSource structure
    """
    # Construct content from abstract and metadata
    content = f"""
Title: {paper.title}

Authors: {', '.join(paper.authors)}

Abstract: {paper.abstract}

Categories: {', '.join(paper.categories)}
Published: {paper.published_date}
arXiv ID: {paper.arxiv_id}
"""

    return {
        "url": paper.arxiv_url,
        "title": paper.title,
        "content": content.strip(),
        "source_name": "arXiv",
        "source_category": "academic",
        "relevance": 0.8,  # Default relevance for academic sources
        "metadata": {
            "arxiv_id": paper.arxiv_id,
            "authors": paper.authors,
            "categories": paper.categories,
            "primary_category": paper.primary_category,
            "published_date": paper.published_date,
            "pdf_url": paper.pdf_url,
        }
    }


async def fetch_and_convert_papers(
    query: str = "",
    categories: Optional[List[str]] = None,
    max_results: int = 20
) -> List[Dict[str, Any]]:
    """
    Convenience function to fetch papers and convert to raw source format.

    This is the recommended function for integration with the research pipeline.

    Args:
        query: Search query terms
        categories: arXiv category codes
        max_results: Maximum papers to return

    Returns:
        List of source dicts compatible with research pipeline
    """
    result = await fetch_academic_papers(
        query=query,
        categories=categories,
        max_results=max_results
    )

    return [convert_to_raw_source(paper) for paper in result.papers]
