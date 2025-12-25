"""
Source fetchers for multi-source content ingestion.

This module provides fetchers for 5 diverse content source categories:
1. RSS/Atom feeds - Curated feeds from various sources
2. News outlets - Major news sites (NYT, WSJ, Reuters)
3. Academic publications - arXiv, research papers
4. Government sources - .gov domains, policy documents
5. Tech blogs - TechCrunch, Ars Technica, company blogs

Each fetcher returns standardized FetchedArticle objects for downstream
processing in the AI pipeline.
"""

from .rss_fetcher import (
    fetch_rss_sources,
    fetch_single_feed,
    FetchedArticle,
    FeedFetchResult,
)

from .academic_fetcher import (
    fetch_academic_papers,
    fetch_recent_papers,
    fetch_municipal_tech_papers,
    fetch_and_convert_papers,
    convert_to_raw_source,
    AcademicPaper,
    AcademicFetchResult,
)

from .news_fetcher import (
    fetch_news_articles,
    fetch_articles_from_urls,
    NewsFetcher,
    NewsArticle,
)

__all__ = [
    # RSS Fetcher
    "fetch_rss_sources",
    "fetch_single_feed",
    "FetchedArticle",
    "FeedFetchResult",
    # Academic Fetcher
    "fetch_academic_papers",
    "fetch_recent_papers",
    "fetch_municipal_tech_papers",
    "fetch_and_convert_papers",
    "convert_to_raw_source",
    "AcademicPaper",
    "AcademicFetchResult",
    # News Fetcher
    "fetch_news_articles",
    "fetch_articles_from_urls",
    "NewsFetcher",
    "NewsArticle",
]
