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

from .government_fetcher import (
    fetch_government_sources,
    fetch_documents_from_urls,
    fetch_municipal_government_content,
    fetch_and_convert_documents,
    convert_to_raw_source as convert_government_to_raw_source,
    GovernmentFetcher,
    GovernmentDocument,
    GovernmentFetchResult,
)

from .tech_blog_fetcher import (
    fetch_tech_blog_articles,
    fetch_tech_blog_rss_feeds,
    fetch_articles_from_urls as fetch_tech_blog_urls,
    TechBlogFetcher,
    TechBlogArticle,
    TechBlogFetchResult,
)

from .searxng_fetcher import (
    search_web as searxng_search_web,
    search_news as searxng_search_news,
    search_all as searxng_search_all,
    is_available as searxng_available,
    health_check as searxng_health_check,
    SearXNGResult,
)

__all__ = [
    # SearXNG Fetcher
    "searxng_search_web",
    "searxng_search_news",
    "searxng_search_all",
    "searxng_available",
    "searxng_health_check",
    "SearXNGResult",
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
    # Government Fetcher
    "fetch_government_sources",
    "fetch_documents_from_urls",
    "fetch_municipal_government_content",
    "fetch_and_convert_documents",
    "convert_government_to_raw_source",
    "GovernmentFetcher",
    "GovernmentDocument",
    "GovernmentFetchResult",
    # Tech Blog Fetcher
    "fetch_tech_blog_articles",
    "fetch_tech_blog_rss_feeds",
    "fetch_tech_blog_urls",
    "TechBlogFetcher",
    "TechBlogArticle",
    "TechBlogFetchResult",
]
