"""
Discovery orchestration service for Foresight.

Runs automated discovery scans to find emerging trends and technologies
relevant to municipal government. Uses the query generator to create
search queries and the research pipeline to discover, triage, analyze,
and store new sources.

Key Features:
- Generates queries from Pillars and Top 25 Priorities
- Executes searches using GPT Researcher + Exa
- Triages and analyzes results through AI pipeline
- Deduplicates against existing cards (vector similarity 0.92 threshold)
- Creates new cards or enriches existing ones
- Auto-approves high-confidence discoveries (>0.95)
- Configurable scope caps to control costs
- Multi-source content ingestion from 5 categories:
  1. RSS/Atom feeds - Curated feeds from various sources
  2. News outlets - Major news sites (Reuters, AP News, GCN)
  3. Academic publications - arXiv research papers
  4. Government sources - .gov domains, policy documents
  5. Tech blogs - TechCrunch, Ars Technica, company blogs

Usage:
    from app.discovery_service import DiscoveryService, DiscoveryConfig

    service = DiscoveryService(supabase_client, openai_client)
    config = DiscoveryConfig(
        max_queries_per_run=50,
        max_sources_total=200,
        pillars_filter=['CH', 'MC']
    )
    result = await service.execute_discovery_run(config)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
import uuid

from supabase import Client
import openai

from .query_generator import QueryGenerator, QueryConfig
from .ai_service import AIService, AnalysisResult, TriageResult
from .research_service import RawSource, ProcessedSource

# Import multi-source content fetchers (5 categories)
from .source_fetchers import (
    # RSS/Atom feeds
    fetch_rss_sources,
    FetchedArticle,
    # News outlets
    fetch_news_articles,
    NewsArticle,
    # Academic publications
    fetch_academic_papers,
    AcademicPaper,
    convert_to_raw_source as convert_academic_to_raw,
    # Government sources
    fetch_government_sources,
    GovernmentDocument,
    convert_government_to_raw_source,
    # Tech blogs
    fetch_tech_blog_articles,
    TechBlogArticle,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Source Category Tracking (5 Categories)
# ============================================================================

class SourceCategory(Enum):
    """
    Content source categories for multi-source ingestion.

    The pipeline fetches from 5 diverse source categories to ensure
    comprehensive coverage of emerging trends and technologies.
    """
    RSS = "rss"                     # RSS/Atom feeds from curated sources
    NEWS = "news"                   # Major news outlets (Reuters, AP, GCN)
    ACADEMIC = "academic"           # Academic publications (arXiv)
    GOVERNMENT = "government"       # Government sources (.gov domains)
    TECH_BLOG = "tech_blog"         # Tech blogs (TechCrunch, Ars Technica)


# Default RSS feeds for curated content
DEFAULT_RSS_FEEDS = [
    "https://news.ycombinator.com/rss",
    "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "https://www.govtech.com/rss/",
    "https://statescoop.com/feed/",
]

# Default search topics for multi-source content fetching
DEFAULT_SEARCH_TOPICS = [
    "smart city technology",
    "municipal innovation",
    "government AI",
    "public sector digital transformation",
    "civic technology",
]


# ============================================================================
# Configuration Classes
# ============================================================================

@dataclass
class SourceCategoryConfig:
    """Configuration for a specific source category."""
    enabled: bool = True
    max_sources: int = 50
    topics: List[str] = field(default_factory=list)
    # Category-specific settings
    rss_feeds: List[str] = field(default_factory=list)  # For RSS category


@dataclass
class DiscoveryConfig:
    """Configuration for a discovery run."""

    # Query limits
    max_queries_per_run: int = 100
    max_sources_per_query: int = 10
    max_sources_total: int = 500

    # Thresholds
    auto_approve_threshold: float = 0.95  # Auto-approve confidence threshold
    similarity_threshold: float = 0.92    # Strong match - add to existing card
    weak_match_threshold: float = 0.82    # Weak match - check with LLM

    # Filtering
    pillars_filter: List[str] = field(default_factory=list)  # Empty = all pillars
    horizons_filter: List[str] = field(default_factory=list)  # Empty = all horizons

    # Options
    include_priorities: bool = True
    dry_run: bool = False  # If True, don't persist anything
    skip_blocked_topics: bool = True

    # Multi-source category configuration
    source_categories: Dict[str, SourceCategoryConfig] = field(default_factory=dict)
    enable_multi_source: bool = True  # Enable fetching from all 5 source categories
    search_topics: List[str] = field(default_factory=list)  # Topics for source searches

    def __post_init__(self):
        """Initialize default source category configurations."""
        if not self.source_categories:
            self.source_categories = {
                SourceCategory.RSS.value: SourceCategoryConfig(
                    enabled=True,
                    max_sources=50,
                    rss_feeds=DEFAULT_RSS_FEEDS.copy()
                ),
                SourceCategory.NEWS.value: SourceCategoryConfig(
                    enabled=True,
                    max_sources=30
                ),
                SourceCategory.ACADEMIC.value: SourceCategoryConfig(
                    enabled=True,
                    max_sources=30
                ),
                SourceCategory.GOVERNMENT.value: SourceCategoryConfig(
                    enabled=True,
                    max_sources=30
                ),
                SourceCategory.TECH_BLOG.value: SourceCategoryConfig(
                    enabled=True,
                    max_sources=30
                ),
            }
        if not self.search_topics:
            self.search_topics = DEFAULT_SEARCH_TOPICS.copy()


class DiscoveryStatus(Enum):
    """Status of a discovery run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CardAction(Enum):
    """Action taken for a source during discovery."""
    CREATED = "created"           # New card created
    ENRICHED = "enriched"         # Added to existing card
    AUTO_APPROVED = "auto_approved"  # New card auto-approved
    PENDING_REVIEW = "pending_review"  # Awaiting human review
    DUPLICATE = "duplicate"       # Duplicate of existing source
    BLOCKED = "blocked"           # Matched blocked topic
    FILTERED = "filtered"         # Filtered by triage


# ============================================================================
# Result Classes
# ============================================================================

@dataclass
class DeduplicationResult:
    """Result of deduplication process."""
    unique_sources: List[ProcessedSource]
    duplicate_count: int
    enrichment_candidates: List[Tuple[ProcessedSource, str, float]]  # (source, card_id, similarity)
    new_concept_candidates: List[ProcessedSource]


@dataclass
class CardActionResult:
    """Result of card creation/enrichment."""
    cards_created: List[str]
    cards_enriched: List[str]
    sources_added: int
    auto_approved: int
    pending_review: int


@dataclass
class SourceDiversityMetrics:
    """
    Comprehensive source diversity metrics for observability.

    Tracks multiple dimensions of diversity to ensure balanced content ingestion
    across all 5 source categories.
    """
    # Category distribution
    sources_by_category: Dict[str, int]
    total_sources: int
    categories_fetched: int  # Number of categories that contributed sources

    # Diversity scores (0-1 scale, higher = more diverse)
    category_coverage: float  # Percentage of categories with sources
    balance_score: float      # How evenly distributed sources are
    shannon_entropy: float    # Information-theoretic diversity measure

    # Category-level details
    dominant_category: Optional[str] = None
    underrepresented_categories: List[str] = field(default_factory=list)

    @classmethod
    def compute(cls, sources_by_category: Dict[str, int]) -> "SourceDiversityMetrics":
        """
        Compute diversity metrics from source category counts.

        Args:
            sources_by_category: Count of sources per category

        Returns:
            SourceDiversityMetrics with all computed values
        """
        import math

        total = sum(sources_by_category.values())
        active_categories = [cat for cat, count in sources_by_category.items() if count > 0]
        num_active = len(active_categories)
        num_total_categories = 5  # Total number of source categories

        # Category coverage (0-1)
        category_coverage = num_active / num_total_categories if num_total_categories > 0 else 0.0

        # Balance score: 1 - normalized standard deviation
        # Perfect balance = 1.0, all in one category = 0.0
        if total > 0 and num_active > 0:
            mean_per_category = total / num_total_categories
            variance = sum((count - mean_per_category) ** 2 for count in sources_by_category.values()) / num_total_categories
            std_dev = math.sqrt(variance)
            max_std_dev = mean_per_category * math.sqrt(num_total_categories - 1)  # Worst case: all in one category
            balance_score = 1.0 - (std_dev / max_std_dev) if max_std_dev > 0 else 1.0
        else:
            balance_score = 0.0

        # Shannon entropy (normalized to 0-1)
        # H = -sum(p * log(p)) / log(n) where n is number of categories
        if total > 0 and num_active > 1:
            entropy = 0.0
            for count in sources_by_category.values():
                if count > 0:
                    p = count / total
                    entropy -= p * math.log(p)
            max_entropy = math.log(num_total_categories)
            shannon_entropy = entropy / max_entropy if max_entropy > 0 else 0.0
        else:
            shannon_entropy = 0.0

        # Find dominant and underrepresented categories
        dominant_category = None
        underrepresented = []

        if total > 0:
            max_count = max(sources_by_category.values())
            threshold = total / num_total_categories * 0.3  # 30% of expected average

            for cat, count in sources_by_category.items():
                if count == max_count and max_count > 0:
                    dominant_category = cat
                if count < threshold:
                    underrepresented.append(cat)

        return cls(
            sources_by_category=sources_by_category,
            total_sources=total,
            categories_fetched=num_active,
            category_coverage=round(category_coverage, 3),
            balance_score=round(balance_score, 3),
            shannon_entropy=round(shannon_entropy, 3),
            dominant_category=dominant_category,
            underrepresented_categories=underrepresented
        )

    def log_metrics(self, logger_instance: logging.Logger) -> None:
        """Log diversity metrics for observability."""
        logger_instance.info(
            f"Source Diversity Metrics: "
            f"coverage={self.category_coverage:.1%}, "
            f"balance={self.balance_score:.2f}, "
            f"entropy={self.shannon_entropy:.2f}, "
            f"categories={self.categories_fetched}/5"
        )
        if self.underrepresented_categories:
            logger_instance.warning(
                f"Underrepresented source categories: {', '.join(self.underrepresented_categories)}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for storage/API response."""
        return {
            "sources_by_category": self.sources_by_category,
            "total_sources": self.total_sources,
            "categories_fetched": self.categories_fetched,
            "category_coverage": self.category_coverage,
            "balance_score": self.balance_score,
            "shannon_entropy": self.shannon_entropy,
            "dominant_category": self.dominant_category,
            "underrepresented_categories": self.underrepresented_categories,
        }


@dataclass
class MultiSourceFetchResult:
    """Result of multi-source content fetching across all 5 categories."""
    sources: List[RawSource]
    sources_by_category: Dict[str, int]  # Count per category
    total_sources: int
    categories_fetched: int  # Number of categories that contributed sources
    fetch_time_seconds: float
    errors_by_category: Dict[str, List[str]]
    diversity_metrics: Optional[SourceDiversityMetrics] = None

    def __post_init__(self):
        """Compute diversity metrics after initialization."""
        if self.diversity_metrics is None and self.sources_by_category:
            self.diversity_metrics = SourceDiversityMetrics.compute(self.sources_by_category)

    @property
    def category_diversity(self) -> float:
        """Calculate diversity score (0-1) based on category distribution."""
        if self.total_sources == 0:
            return 0.0
        active_categories = sum(1 for count in self.sources_by_category.values() if count > 0)
        return active_categories / 5.0  # 5 categories total


@dataclass
class ProcessingTimeMetrics:
    """
    Granular timing metrics for each pipeline phase.

    Provides observability into processing time distribution across
    the discovery pipeline for performance optimization and debugging.
    """
    query_generation_seconds: float = 0.0
    multi_source_fetch_seconds: float = 0.0
    query_search_seconds: float = 0.0
    triage_seconds: float = 0.0
    blocked_topic_check_seconds: float = 0.0
    deduplication_seconds: float = 0.0
    card_creation_seconds: float = 0.0
    total_seconds: float = 0.0

    def log_metrics(self, logger_instance: logging.Logger) -> None:
        """Log processing time metrics for observability."""
        logger_instance.info(
            f"Processing Time Breakdown: "
            f"query_gen={self.query_generation_seconds:.2f}s, "
            f"multi_source={self.multi_source_fetch_seconds:.2f}s, "
            f"query_search={self.query_search_seconds:.2f}s, "
            f"triage={self.triage_seconds:.2f}s, "
            f"block_check={self.blocked_topic_check_seconds:.2f}s, "
            f"dedup={self.deduplication_seconds:.2f}s, "
            f"card_create={self.card_creation_seconds:.2f}s, "
            f"total={self.total_seconds:.2f}s"
        )

    def to_dict(self) -> Dict[str, float]:
        """Convert metrics to dictionary for storage/API response."""
        return {
            "query_generation_seconds": self.query_generation_seconds,
            "multi_source_fetch_seconds": self.multi_source_fetch_seconds,
            "query_search_seconds": self.query_search_seconds,
            "triage_seconds": self.triage_seconds,
            "blocked_topic_check_seconds": self.blocked_topic_check_seconds,
            "deduplication_seconds": self.deduplication_seconds,
            "card_creation_seconds": self.card_creation_seconds,
            "total_seconds": self.total_seconds,
        }


@dataclass
class APITokenUsage:
    """
    Token usage metrics for API cost tracking.

    Tracks token consumption across different AI operations
    for cost monitoring and budget management.
    """
    triage_tokens: int = 0
    analysis_tokens: int = 0
    embedding_tokens: int = 0
    card_match_tokens: int = 0
    total_tokens: int = 0

    # Token costs (approximate, based on GPT-4 pricing)
    # These are rough estimates for monitoring purposes
    estimated_cost_usd: float = 0.0

    def add_tokens(self, operation: str, tokens: int) -> None:
        """Add tokens for a specific operation."""
        if operation == "triage":
            self.triage_tokens += tokens
        elif operation == "analysis":
            self.analysis_tokens += tokens
        elif operation == "embedding":
            self.embedding_tokens += tokens
        elif operation == "card_match":
            self.card_match_tokens += tokens
        self.total_tokens += tokens
        # Rough cost estimate: $0.03 per 1K tokens (GPT-4 average)
        self.estimated_cost_usd = self.total_tokens * 0.00003

    def log_metrics(self, logger_instance: logging.Logger) -> None:
        """Log API token usage metrics for observability."""
        logger_instance.info(
            f"API Token Usage: "
            f"triage={self.triage_tokens:,}, "
            f"analysis={self.analysis_tokens:,}, "
            f"embedding={self.embedding_tokens:,}, "
            f"card_match={self.card_match_tokens:,}, "
            f"total={self.total_tokens:,}, "
            f"est_cost=${self.estimated_cost_usd:.4f}"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for storage/API response."""
        return {
            "triage_tokens": self.triage_tokens,
            "analysis_tokens": self.analysis_tokens,
            "embedding_tokens": self.embedding_tokens,
            "card_match_tokens": self.card_match_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
        }


@dataclass
class DiscoveryResult:
    """Complete result of a discovery run."""
    run_id: str
    status: DiscoveryStatus
    started_at: datetime
    completed_at: Optional[datetime]

    # Query stats
    queries_generated: int
    queries_executed: int

    # Source stats
    sources_discovered: int
    sources_triaged: int
    sources_blocked: int
    sources_duplicate: int

    # Multi-source category tracking
    sources_by_category: Dict[str, int] = field(default_factory=dict)
    categories_fetched: int = 0
    diversity_metrics: Optional[Dict[str, Any]] = None  # SourceDiversityMetrics as dict

    # Card stats
    cards_created: List[str] = field(default_factory=list)
    cards_enriched: List[str] = field(default_factory=list)
    sources_added: int = 0
    auto_approved: int = 0
    pending_review: int = 0

    # Cost and performance
    estimated_cost: float = 0.0
    execution_time_seconds: float = 0.0

    # Enhanced metrics (Phase 4)
    processing_time: Optional[Dict[str, float]] = None  # ProcessingTimeMetrics as dict
    api_token_usage: Optional[Dict[str, Any]] = None  # APITokenUsage as dict

    # Summary
    summary_report: Optional[str] = None
    errors: List[str] = field(default_factory=list)


# ============================================================================
# Discovery Service
# ============================================================================

class DiscoveryService:
    """
    Orchestrates automated discovery runs.

    Pipeline:
    1. Generate queries from pillars and priorities
    2. Execute searches using GPT Researcher + Exa
    3. Triage sources for relevance
    4. Check against blocked topics
    5. Deduplicate against existing cards
    6. Create new cards or enrich existing ones
    7. Auto-approve high-confidence discoveries
    """

    def __init__(
        self,
        supabase: Client,
        openai_client: openai.OpenAI
    ):
        """
        Initialize discovery service.

        Args:
            supabase: Supabase client for database operations
            openai_client: OpenAI client for AI operations
        """
        self.supabase = supabase
        self.openai_client = openai_client
        self.ai_service = AIService(openai_client)
        self.query_generator = QueryGenerator()

        # Import research service components for search execution
        # Using dynamic import to avoid circular dependencies
        from .research_service import ResearchService
        self.research_service = ResearchService(supabase, openai_client)

    # ========================================================================
    # Main Entry Point
    # ========================================================================

    async def execute_discovery_run(
        self,
        config: DiscoveryConfig
    ) -> DiscoveryResult:
        """
        Execute a complete discovery run.

        Args:
            config: Configuration for this run

        Returns:
            DiscoveryResult with complete statistics
        """
        start_time = datetime.now()
        run_id = await self._create_run_record(config)
        errors: List[str] = []
        sources_by_category: Dict[str, int] = {}
        categories_fetched: int = 0
        diversity_metrics: Optional[SourceDiversityMetrics] = None

        # Initialize enhanced metrics tracking
        processing_time = ProcessingTimeMetrics()
        api_token_usage = APITokenUsage()

        logger.info(f"Starting discovery run {run_id} with config: {config}")

        try:
            # Step 1: Generate queries
            step_start = datetime.now()
            queries = await self._generate_queries(config)
            processing_time.query_generation_seconds = (datetime.now() - step_start).total_seconds()
            logger.info(f"Generated {len(queries)} queries in {processing_time.query_generation_seconds:.2f}s")

            # Step 2a: Multi-source content fetching (5 categories)
            raw_sources: List[RawSource] = []
            search_cost = 0.0

            if config.enable_multi_source:
                step_start = datetime.now()
                logger.info("Fetching from all 5 source categories...")
                multi_source_result = await self._fetch_from_all_source_categories(config)
                raw_sources.extend(multi_source_result.sources)
                sources_by_category = multi_source_result.sources_by_category.copy()
                categories_fetched = multi_source_result.categories_fetched
                diversity_metrics = multi_source_result.diversity_metrics
                processing_time.multi_source_fetch_seconds = (datetime.now() - step_start).total_seconds()

                # Add any multi-source errors to error list
                for category, cat_errors in multi_source_result.errors_by_category.items():
                    for error in cat_errors:
                        errors.append(f"[{category}] {error}")

                logger.info(
                    f"Multi-source fetch: {len(raw_sources)} sources from "
                    f"{categories_fetched}/5 categories in {processing_time.multi_source_fetch_seconds:.2f}s"
                )

            # Step 2b: Execute query-based searches (traditional GPT Researcher + Exa)
            if queries:
                step_start = datetime.now()
                query_sources, query_cost = await self._execute_searches(
                    queries[:config.max_queries_per_run],
                    config
                )
                search_cost += query_cost
                processing_time.query_search_seconds = (datetime.now() - step_start).total_seconds()

                # Deduplicate query sources against multi-source results
                seen_urls = {s.url for s in raw_sources if s.url}
                for source in query_sources:
                    if source.url and source.url not in seen_urls:
                        seen_urls.add(source.url)
                        raw_sources.append(source)
                        # Track as "query" category
                        sources_by_category["query"] = sources_by_category.get("query", 0) + 1

                logger.info(f"Query-based search: {len(query_sources)} additional sources in {processing_time.query_search_seconds:.2f}s")

            logger.info(f"Total raw sources discovered: {len(raw_sources)}")

            if not raw_sources and not queries:
                logger.warning("No queries generated and no multi-source results - completing run")
                processing_time.total_seconds = (datetime.now() - start_time).total_seconds()
                return await self._finalize_run(
                    run_id=run_id,
                    start_time=start_time,
                    queries_generated=0,
                    queries_executed=0,
                    sources_discovered=0,
                    sources_triaged=0,
                    sources_blocked=0,
                    sources_duplicate=0,
                    sources_by_category=sources_by_category,
                    categories_fetched=categories_fetched,
                    diversity_metrics=diversity_metrics,
                    card_result=CardActionResult([], [], 0, 0, 0),
                    cost=0.0,
                    errors=["No queries generated and no multi-source results"],
                    status=DiscoveryStatus.COMPLETED,
                    processing_time_metrics=processing_time,
                    api_token_usage_metrics=api_token_usage
                )

            if not raw_sources:
                logger.warning("No sources discovered - completing run")
                processing_time.total_seconds = (datetime.now() - start_time).total_seconds()
                return await self._finalize_run(
                    run_id=run_id,
                    start_time=start_time,
                    queries_generated=len(queries),
                    queries_executed=min(len(queries), config.max_queries_per_run),
                    sources_discovered=0,
                    sources_triaged=0,
                    sources_blocked=0,
                    sources_duplicate=0,
                    sources_by_category=sources_by_category,
                    categories_fetched=categories_fetched,
                    diversity_metrics=diversity_metrics,
                    card_result=CardActionResult([], [], 0, 0, 0),
                    cost=search_cost,
                    errors=[],
                    status=DiscoveryStatus.COMPLETED,
                    processing_time_metrics=processing_time,
                    api_token_usage_metrics=api_token_usage
                )

            # Step 3: Triage sources
            step_start = datetime.now()
            triaged_sources, triage_tokens = await self._triage_sources_with_metrics(raw_sources)
            processing_time.triage_seconds = (datetime.now() - step_start).total_seconds()
            api_token_usage.add_tokens("triage", triage_tokens)
            logger.info(f"Triaged to {len(triaged_sources)} relevant sources in {processing_time.triage_seconds:.2f}s")

            # Step 4: Check blocked topics
            step_start = datetime.now()
            if config.skip_blocked_topics:
                filtered_sources, blocked_count = await self._check_blocked_topics(
                    triaged_sources
                )
                logger.info(f"Filtered {blocked_count} blocked sources")
            else:
                filtered_sources = triaged_sources
                blocked_count = 0
            processing_time.blocked_topic_check_seconds = (datetime.now() - step_start).total_seconds()

            # Step 5: Deduplicate against existing cards
            step_start = datetime.now()
            dedup_result, dedup_tokens = await self._deduplicate_sources_with_metrics(filtered_sources, config)
            processing_time.deduplication_seconds = (datetime.now() - step_start).total_seconds()
            api_token_usage.add_tokens("card_match", dedup_tokens)
            logger.info(
                f"Deduplication: {dedup_result.duplicate_count} duplicates, "
                f"{len(dedup_result.enrichment_candidates)} enrichments, "
                f"{len(dedup_result.new_concept_candidates)} new concepts in {processing_time.deduplication_seconds:.2f}s"
            )

            # Step 6: Create or enrich cards (skip if dry run)
            step_start = datetime.now()
            if config.dry_run:
                logger.info("Dry run - skipping card creation/enrichment")
                card_result = CardActionResult([], [], 0, 0, 0)
            else:
                card_result = await self._create_or_enrich_cards(
                    dedup_result,
                    config
                )
                logger.info(
                    f"Card actions: {len(card_result.cards_created)} created, "
                    f"{len(card_result.cards_enriched)} enriched, "
                    f"{card_result.auto_approved} auto-approved"
                )
            processing_time.card_creation_seconds = (datetime.now() - step_start).total_seconds()

            # Step 7: Finalize run
            # Recompute diversity metrics to include query sources
            if sources_by_category:
                diversity_metrics = SourceDiversityMetrics.compute(sources_by_category)

            # Calculate total processing time
            processing_time.total_seconds = (datetime.now() - start_time).total_seconds()

            # Log comprehensive metrics summary
            logger.info(f"Discovery run {run_id} metrics summary:")
            logger.info(f"  Sources by category: {sources_by_category}")
            processing_time.log_metrics(logger)
            api_token_usage.log_metrics(logger)

            return await self._finalize_run(
                run_id=run_id,
                start_time=start_time,
                queries_generated=len(queries),
                queries_executed=min(len(queries), config.max_queries_per_run),
                sources_discovered=len(raw_sources),
                sources_triaged=len(triaged_sources),
                sources_blocked=blocked_count,
                sources_duplicate=dedup_result.duplicate_count,
                sources_by_category=sources_by_category,
                categories_fetched=categories_fetched,
                diversity_metrics=diversity_metrics,
                card_result=card_result,
                cost=search_cost,
                errors=errors,
                status=DiscoveryStatus.COMPLETED,
                processing_time_metrics=processing_time,
                api_token_usage_metrics=api_token_usage
            )

        except Exception as e:
            logger.error(f"Discovery run failed: {e}", exc_info=True)
            errors.append(str(e))
            processing_time.total_seconds = (datetime.now() - start_time).total_seconds()

            return await self._finalize_run(
                run_id=run_id,
                start_time=start_time,
                queries_generated=0,
                queries_executed=0,
                sources_discovered=0,
                sources_triaged=0,
                sources_blocked=0,
                sources_duplicate=0,
                sources_by_category=sources_by_category,
                categories_fetched=categories_fetched,
                diversity_metrics=diversity_metrics,
                card_result=CardActionResult([], [], 0, 0, 0),
                cost=0.0,
                errors=errors,
                status=DiscoveryStatus.FAILED,
                processing_time_metrics=processing_time,
                api_token_usage_metrics=api_token_usage
            )

    # ========================================================================
    # Step 1: Create Run Record
    # ========================================================================

    async def _create_run_record(self, config: DiscoveryConfig) -> str:
        """
        Create a discovery run record in the database.

        Args:
            config: Run configuration

        Returns:
            Run ID
        """
        run_id = str(uuid.uuid4())

        try:
            self.supabase.table("discovery_runs").insert({
                "id": run_id,
                "status": DiscoveryStatus.RUNNING.value,
                "config": {
                    "max_queries_per_run": config.max_queries_per_run,
                    "max_sources_per_query": config.max_sources_per_query,
                    "max_sources_total": config.max_sources_total,
                    "auto_approve_threshold": config.auto_approve_threshold,
                    "similarity_threshold": config.similarity_threshold,
                    "pillars_filter": config.pillars_filter,
                    "horizons_filter": config.horizons_filter,
                    "dry_run": config.dry_run,
                },
                "started_at": datetime.now().isoformat(),
            }).execute()
        except Exception as e:
            # Log but don't fail - table might not exist yet
            logger.warning(f"Could not create run record (table may not exist): {e}")

        return run_id

    # ========================================================================
    # Step 2: Generate Queries
    # ========================================================================

    async def _generate_queries(
        self,
        config: DiscoveryConfig
    ) -> List[QueryConfig]:
        """
        Generate search queries based on configuration.

        Args:
            config: Run configuration

        Returns:
            List of QueryConfig objects
        """
        return self.query_generator.generate_queries(
            pillars_filter=config.pillars_filter if config.pillars_filter else None,
            horizons=config.horizons_filter if config.horizons_filter else None,
            include_priorities=config.include_priorities,
            max_queries=config.max_queries_per_run
        )

    # ========================================================================
    # Step 3: Execute Searches
    # ========================================================================

    async def _execute_searches(
        self,
        queries: List[QueryConfig],
        config: DiscoveryConfig
    ) -> Tuple[List[RawSource], float]:
        """
        Execute searches for all queries using GPT Researcher.

        Args:
            queries: List of queries to execute
            config: Run configuration

        Returns:
            Tuple of (raw_sources, total_cost)
        """
        all_sources: List[RawSource] = []
        total_cost = 0.0
        seen_urls = set()

        # Process queries in batches to avoid rate limits
        batch_size = 5
        for i in range(0, len(queries), batch_size):
            batch = queries[i:i + batch_size]

            # Execute batch concurrently
            tasks = [
                self._execute_single_search(query, config)
                for query in batch
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    logger.warning(f"Search failed: {result}")
                    continue

                sources, cost = result
                total_cost += cost

                # Deduplicate by URL
                for source in sources:
                    if source.url and source.url not in seen_urls:
                        seen_urls.add(source.url)
                        all_sources.append(source)

            # Check if we've hit the total source limit
            if len(all_sources) >= config.max_sources_total:
                logger.info(f"Hit max_sources_total limit ({config.max_sources_total})")
                break

            # Small delay between batches to avoid rate limiting
            if i + batch_size < len(queries):
                await asyncio.sleep(1)

        return all_sources[:config.max_sources_total], total_cost

    async def _execute_single_search(
        self,
        query: QueryConfig,
        config: DiscoveryConfig
    ) -> Tuple[List[RawSource], float]:
        """
        Execute a single search query.

        Args:
            query: Query configuration
            config: Run configuration

        Returns:
            Tuple of (sources, cost)
        """
        try:
            # Use the research service's discovery method
            sources, _report, cost = await self.research_service._discover_sources(
                query=query.query_text,
                report_type="research_report"
            )

            # Limit sources per query
            sources = sources[:config.max_sources_per_query]

            # Add query context to sources for tracking
            for source in sources:
                # Store query context in source for later use
                source.pillar_code = query.pillar_code  # type: ignore
                source.priority_id = query.priority_id  # type: ignore
                source.horizon_target = query.horizon_target  # type: ignore

            return sources, cost

        except Exception as e:
            logger.warning(f"Search failed for query '{query.query_text[:50]}...': {e}")
            return [], 0.0

    # ========================================================================
    # Step 3b: Multi-Source Content Fetching (5 Categories)
    # ========================================================================

    async def _fetch_from_all_source_categories(
        self,
        config: DiscoveryConfig
    ) -> MultiSourceFetchResult:
        """
        Fetch content from all 5 source categories concurrently.

        Categories:
        1. RSS/Atom feeds - Curated feeds from various sources
        2. News outlets - Major news sites (Reuters, AP News, GCN)
        3. Academic publications - arXiv research papers
        4. Government sources - .gov domains, policy documents
        5. Tech blogs - TechCrunch, Ars Technica, company blogs

        Args:
            config: Discovery configuration with source category settings

        Returns:
            MultiSourceFetchResult with sources from all categories
        """
        start_time = datetime.now()
        all_sources: List[RawSource] = []
        sources_by_category: Dict[str, int] = {cat.value: 0 for cat in SourceCategory}
        errors_by_category: Dict[str, List[str]] = {cat.value: [] for cat in SourceCategory}
        seen_urls: set = set()

        topics = config.search_topics or DEFAULT_SEARCH_TOPICS

        logger.info(f"Starting multi-source fetch from 5 categories with topics: {topics[:3]}...")

        # Create tasks for each source category
        tasks = []

        # 1. RSS/Atom feeds
        rss_config = config.source_categories.get(SourceCategory.RSS.value, SourceCategoryConfig())
        if rss_config.enabled:
            feeds = rss_config.rss_feeds or DEFAULT_RSS_FEEDS
            tasks.append(self._fetch_rss_sources(feeds, rss_config.max_sources))

        # 2. News outlets
        news_config = config.source_categories.get(SourceCategory.NEWS.value, SourceCategoryConfig())
        if news_config.enabled:
            tasks.append(self._fetch_news_sources(topics, news_config.max_sources))

        # 3. Academic publications
        academic_config = config.source_categories.get(SourceCategory.ACADEMIC.value, SourceCategoryConfig())
        if academic_config.enabled:
            tasks.append(self._fetch_academic_sources(topics, academic_config.max_sources))

        # 4. Government sources
        gov_config = config.source_categories.get(SourceCategory.GOVERNMENT.value, SourceCategoryConfig())
        if gov_config.enabled:
            tasks.append(self._fetch_government_sources(topics, gov_config.max_sources))

        # 5. Tech blogs
        tech_config = config.source_categories.get(SourceCategory.TECH_BLOG.value, SourceCategoryConfig())
        if tech_config.enabled:
            tasks.append(self._fetch_tech_blog_sources(topics, tech_config.max_sources))

        # Execute all fetches concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        category_order = [
            SourceCategory.RSS.value,
            SourceCategory.NEWS.value,
            SourceCategory.ACADEMIC.value,
            SourceCategory.GOVERNMENT.value,
            SourceCategory.TECH_BLOG.value,
        ]

        result_idx = 0
        for category in category_order:
            cat_config = config.source_categories.get(category, SourceCategoryConfig())
            if not cat_config.enabled:
                continue

            if result_idx >= len(results):
                break

            result = results[result_idx]
            result_idx += 1

            if isinstance(result, Exception):
                error_msg = f"Category {category} fetch failed: {str(result)}"
                logger.warning(error_msg)
                errors_by_category[category].append(error_msg)
                continue

            sources, category_name = result
            for source in sources:
                if source.url and source.url not in seen_urls:
                    seen_urls.add(source.url)
                    # Tag source with category
                    source.source_category = category  # type: ignore
                    all_sources.append(source)
                    sources_by_category[category] += 1

        # Calculate metrics
        fetch_time = (datetime.now() - start_time).total_seconds()
        categories_fetched = sum(1 for count in sources_by_category.values() if count > 0)

        logger.info(
            f"Multi-source fetch complete: {len(all_sources)} sources from "
            f"{categories_fetched}/5 categories in {fetch_time:.1f}s"
        )
        for cat, count in sources_by_category.items():
            if count > 0:
                logger.info(f"  - {cat}: {count} sources")

        # Compute diversity metrics for observability
        diversity_metrics = SourceDiversityMetrics.compute(sources_by_category)
        diversity_metrics.log_metrics(logger)

        return MultiSourceFetchResult(
            sources=all_sources,
            sources_by_category=sources_by_category,
            total_sources=len(all_sources),
            categories_fetched=categories_fetched,
            fetch_time_seconds=fetch_time,
            errors_by_category=errors_by_category,
            diversity_metrics=diversity_metrics
        )

    async def _fetch_rss_sources(
        self,
        feed_urls: List[str],
        max_sources: int
    ) -> Tuple[List[RawSource], str]:
        """Fetch sources from RSS/Atom feeds."""
        try:
            articles = await fetch_rss_sources(
                feed_urls=feed_urls,
                max_articles_per_feed=max_sources // len(feed_urls) if feed_urls else 10
            )

            sources = []
            for article in articles[:max_sources]:
                source = RawSource(
                    url=article.url,
                    title=article.title,
                    content=article.content,
                    source_name=article.source_name,
                    relevance=article.relevance
                )
                sources.append(source)

            return sources, SourceCategory.RSS.value

        except Exception as e:
            logger.warning(f"RSS fetch failed: {e}")
            return [], SourceCategory.RSS.value

    async def _fetch_news_sources(
        self,
        topics: List[str],
        max_sources: int
    ) -> Tuple[List[RawSource], str]:
        """Fetch sources from news outlets."""
        try:
            articles = await fetch_news_articles(
                topics=topics[:3],  # Limit topics to avoid rate limiting
                max_articles=max_sources
            )

            sources = []
            for article in articles[:max_sources]:
                source = RawSource(
                    url=article.url,
                    title=article.title,
                    content=article.content,
                    source_name=article.source_name,
                    relevance=article.relevance
                )
                sources.append(source)

            return sources, SourceCategory.NEWS.value

        except Exception as e:
            logger.warning(f"News fetch failed: {e}")
            return [], SourceCategory.NEWS.value

    async def _fetch_academic_sources(
        self,
        topics: List[str],
        max_sources: int
    ) -> Tuple[List[RawSource], str]:
        """Fetch sources from academic publications (arXiv)."""
        try:
            # Combine topics into search query
            query = " OR ".join([f'"{topic}"' for topic in topics[:3]])

            result = await fetch_academic_papers(
                query=query,
                max_results=max_sources
            )

            sources = []
            for paper in result.papers[:max_sources]:
                raw_source_dict = convert_academic_to_raw(paper)
                source = RawSource(
                    url=raw_source_dict["url"],
                    title=raw_source_dict["title"],
                    content=raw_source_dict["content"],
                    source_name=raw_source_dict["source_name"],
                    relevance=raw_source_dict.get("relevance", 0.8)
                )
                sources.append(source)

            return sources, SourceCategory.ACADEMIC.value

        except Exception as e:
            logger.warning(f"Academic fetch failed: {e}")
            return [], SourceCategory.ACADEMIC.value

    async def _fetch_government_sources(
        self,
        topics: List[str],
        max_sources: int
    ) -> Tuple[List[RawSource], str]:
        """Fetch sources from government websites (.gov domains)."""
        try:
            documents = await fetch_government_sources(
                topics=topics[:3],  # Limit topics
                max_results=max_sources
            )

            sources = []
            for doc in documents[:max_sources]:
                raw_source_dict = convert_government_to_raw_source(doc)
                source = RawSource(
                    url=raw_source_dict["url"],
                    title=raw_source_dict["title"],
                    content=raw_source_dict["content"],
                    source_name=raw_source_dict["source_name"],
                    relevance=raw_source_dict.get("relevance", 0.75)
                )
                sources.append(source)

            return sources, SourceCategory.GOVERNMENT.value

        except Exception as e:
            logger.warning(f"Government fetch failed: {e}")
            return [], SourceCategory.GOVERNMENT.value

    async def _fetch_tech_blog_sources(
        self,
        topics: List[str],
        max_sources: int
    ) -> Tuple[List[RawSource], str]:
        """Fetch sources from tech blogs."""
        try:
            articles = await fetch_tech_blog_articles(
                topics=topics[:3],  # Limit topics
                max_articles=max_sources
            )

            sources = []
            for article in articles[:max_sources]:
                source = RawSource(
                    url=article.url,
                    title=article.title,
                    content=article.content,
                    source_name=article.source_name,
                    relevance=article.relevance
                )
                sources.append(source)

            return sources, SourceCategory.TECH_BLOG.value

        except Exception as e:
            logger.warning(f"Tech blog fetch failed: {e}")
            return [], SourceCategory.TECH_BLOG.value

    # ========================================================================
    # Step 4: Triage Sources
    # ========================================================================

    async def _triage_sources(
        self,
        sources: List[RawSource]
    ) -> List[ProcessedSource]:
        """
        Triage sources for municipal relevance.

        Args:
            sources: Raw sources from search

        Returns:
            List of processed sources that passed triage
        """
        processed = []
        triage_threshold = 0.6

        for source in sources:
            try:
                # Skip sources without content for full triage
                if not source.content:
                    # Auto-pass URL-only sources with lower confidence
                    triage = TriageResult(
                        is_relevant=True,
                        confidence=0.65,
                        primary_pillar=getattr(source, 'pillar_code', None),
                        reason="Auto-passed (no content)"
                    )
                else:
                    triage = await self.ai_service.triage_source(
                        title=source.title,
                        content=source.content
                    )

                if triage.is_relevant and triage.confidence >= triage_threshold:
                    # Full analysis
                    analysis = await self.ai_service.analyze_source(
                        title=source.title,
                        content=source.content or "",
                        source_name=source.source_name,
                        published_at=datetime.now().isoformat()
                    )

                    # Generate embedding
                    embed_text = f"{source.title} {analysis.summary}"
                    embedding = await self.ai_service.generate_embedding(embed_text)

                    processed.append(ProcessedSource(
                        raw=source,
                        triage=triage,
                        analysis=analysis,
                        embedding=embedding
                    ))

            except Exception as e:
                logger.warning(f"Triage/analysis failed for {source.url}: {e}")
                continue

        return processed

    async def _triage_sources_with_metrics(
        self,
        sources: List[RawSource]
    ) -> Tuple[List[ProcessedSource], int]:
        """
        Triage sources for municipal relevance with token usage tracking.

        Args:
            sources: Raw sources from search

        Returns:
            Tuple of (processed sources, estimated token count)
        """
        processed = []
        triage_threshold = 0.6
        total_tokens = 0

        for source in sources:
            try:
                # Skip sources without content for full triage
                if not source.content:
                    # Auto-pass URL-only sources with lower confidence
                    triage = TriageResult(
                        is_relevant=True,
                        confidence=0.65,
                        primary_pillar=getattr(source, 'pillar_code', None),
                        reason="Auto-passed (no content)"
                    )
                else:
                    triage = await self.ai_service.triage_source(
                        title=source.title,
                        content=source.content
                    )
                    # Estimate tokens: ~4 chars per token for input, fixed output
                    input_tokens = len(source.title or "") // 4 + len(source.content or "") // 4
                    output_tokens = 100  # Estimated output tokens for triage
                    total_tokens += input_tokens + output_tokens

                if triage.is_relevant and triage.confidence >= triage_threshold:
                    # Full analysis
                    analysis = await self.ai_service.analyze_source(
                        title=source.title,
                        content=source.content or "",
                        source_name=source.source_name,
                        published_at=datetime.now().isoformat()
                    )
                    # Estimate tokens for analysis
                    input_tokens = len(source.title or "") // 4 + len(source.content or "") // 4
                    output_tokens = 500  # Estimated output tokens for analysis
                    total_tokens += input_tokens + output_tokens

                    # Generate embedding
                    embed_text = f"{source.title} {analysis.summary}"
                    embedding = await self.ai_service.generate_embedding(embed_text)
                    # Estimate tokens for embedding
                    total_tokens += len(embed_text) // 4

                    processed.append(ProcessedSource(
                        raw=source,
                        triage=triage,
                        analysis=analysis,
                        embedding=embedding
                    ))

            except Exception as e:
                logger.warning(f"Triage/analysis failed for {source.url}: {e}")
                continue

        return processed, total_tokens

    # ========================================================================
    # Step 5: Check Blocked Topics
    # ========================================================================

    async def _check_blocked_topics(
        self,
        sources: List[ProcessedSource]
    ) -> Tuple[List[ProcessedSource], int]:
        """
        Filter out sources that match blocked topics.

        Args:
            sources: Processed sources to check

        Returns:
            Tuple of (filtered_sources, blocked_count)
        """
        try:
            # Get blocked topics from database
            result = self.supabase.table("discovery_blocks").select(
                "topic_name, block_type, keywords"
            ).eq("is_active", True).execute()

            if not result.data:
                return sources, 0

            blocked_keywords = set()
            for block in result.data:
                keywords = block.get("keywords", [])
                if isinstance(keywords, list):
                    blocked_keywords.update(kw.lower() for kw in keywords)
                topic = block.get("topic_name", "")
                if topic:
                    blocked_keywords.add(topic.lower())

            if not blocked_keywords:
                return sources, 0

            # Filter sources
            filtered = []
            blocked_count = 0

            for source in sources:
                # Check title and summary for blocked keywords
                check_text = f"{source.raw.title} {source.analysis.summary}".lower()

                is_blocked = any(kw in check_text for kw in blocked_keywords)

                if is_blocked:
                    blocked_count += 1
                    logger.debug(f"Blocked source: {source.raw.title[:50]}")
                else:
                    filtered.append(source)

            return filtered, blocked_count

        except Exception as e:
            logger.warning(f"Block check failed (continuing without filtering): {e}")
            return sources, 0

    # ========================================================================
    # Step 6: Deduplicate Sources
    # ========================================================================

    async def _deduplicate_sources(
        self,
        sources: List[ProcessedSource],
        config: DiscoveryConfig
    ) -> DeduplicationResult:
        """
        Deduplicate sources against existing cards using vector similarity.

        Args:
            sources: Processed sources to deduplicate
            config: Run configuration

        Returns:
            DeduplicationResult with categorized sources
        """
        unique_sources = []
        duplicate_count = 0
        enrichment_candidates = []
        new_concept_candidates = []

        for source in sources:
            try:
                # Check for existing URL first
                url_check = self.supabase.table("sources").select("id").eq(
                    "url", source.raw.url
                ).execute()

                if url_check.data:
                    duplicate_count += 1
                    continue

                # Vector similarity search against existing cards
                try:
                    match_result = self.supabase.rpc(
                        "find_similar_cards",
                        {
                            "query_embedding": source.embedding,
                            "match_threshold": config.weak_match_threshold,
                            "match_count": 3
                        }
                    ).execute()

                    if match_result.data:
                        top_match = match_result.data[0]
                        similarity = top_match.get("similarity", 0)

                        if similarity >= config.similarity_threshold:
                            # Strong match - enrich existing card
                            enrichment_candidates.append(
                                (source, top_match["id"], similarity)
                            )
                        elif similarity >= config.weak_match_threshold:
                            # Weak match - use LLM to decide
                            card = self.supabase.table("cards").select(
                                "name, summary"
                            ).eq("id", top_match["id"]).single().execute()

                            if card.data:
                                decision = await self.ai_service.check_card_match(
                                    source_summary=source.analysis.summary,
                                    source_card_name=source.analysis.suggested_card_name,
                                    existing_card_name=card.data["name"],
                                    existing_card_summary=card.data.get("summary", "")
                                )

                                if decision.get("is_match") and decision.get("confidence", 0) > 0.7:
                                    enrichment_candidates.append(
                                        (source, top_match["id"], similarity)
                                    )
                                else:
                                    new_concept_candidates.append(source)
                            else:
                                new_concept_candidates.append(source)
                        else:
                            new_concept_candidates.append(source)
                    else:
                        new_concept_candidates.append(source)

                except Exception as e:
                    # Vector search failed - treat as new concept
                    logger.warning(f"Vector search failed (treating as new): {e}")
                    new_concept_candidates.append(source)

                unique_sources.append(source)

            except Exception as e:
                logger.warning(f"Deduplication failed for {source.raw.url}: {e}")
                continue

        return DeduplicationResult(
            unique_sources=unique_sources,
            duplicate_count=duplicate_count,
            enrichment_candidates=enrichment_candidates,
            new_concept_candidates=new_concept_candidates
        )

    async def _deduplicate_sources_with_metrics(
        self,
        sources: List[ProcessedSource],
        config: DiscoveryConfig
    ) -> Tuple[DeduplicationResult, int]:
        """
        Deduplicate sources against existing cards with token usage tracking.

        Args:
            sources: Processed sources to deduplicate
            config: Run configuration

        Returns:
            Tuple of (DeduplicationResult, estimated token count)
        """
        unique_sources = []
        duplicate_count = 0
        enrichment_candidates = []
        new_concept_candidates = []
        total_tokens = 0

        for source in sources:
            try:
                # Check for existing URL first
                url_check = self.supabase.table("sources").select("id").eq(
                    "url", source.raw.url
                ).execute()

                if url_check.data:
                    duplicate_count += 1
                    continue

                # Vector similarity search against existing cards
                try:
                    match_result = self.supabase.rpc(
                        "find_similar_cards",
                        {
                            "query_embedding": source.embedding,
                            "match_threshold": config.weak_match_threshold,
                            "match_count": 3
                        }
                    ).execute()

                    if match_result.data:
                        top_match = match_result.data[0]
                        similarity = top_match.get("similarity", 0)

                        if similarity >= config.similarity_threshold:
                            # Strong match - enrich existing card
                            enrichment_candidates.append(
                                (source, top_match["id"], similarity)
                            )
                        elif similarity >= config.weak_match_threshold:
                            # Weak match - use LLM to decide
                            card = self.supabase.table("cards").select(
                                "name, summary"
                            ).eq("id", top_match["id"]).single().execute()

                            if card.data:
                                decision = await self.ai_service.check_card_match(
                                    source_summary=source.analysis.summary,
                                    source_card_name=source.analysis.suggested_card_name,
                                    existing_card_name=card.data["name"],
                                    existing_card_summary=card.data.get("summary", "")
                                )
                                # Estimate tokens for card match check
                                input_text = f"{source.analysis.summary} {source.analysis.suggested_card_name} {card.data['name']} {card.data.get('summary', '')}"
                                total_tokens += len(input_text) // 4 + 100  # input + output estimate

                                if decision.get("is_match") and decision.get("confidence", 0) > 0.7:
                                    enrichment_candidates.append(
                                        (source, top_match["id"], similarity)
                                    )
                                else:
                                    new_concept_candidates.append(source)
                            else:
                                new_concept_candidates.append(source)
                        else:
                            new_concept_candidates.append(source)
                    else:
                        new_concept_candidates.append(source)

                except Exception as e:
                    # Vector search failed - treat as new concept
                    logger.warning(f"Vector search failed (treating as new): {e}")
                    new_concept_candidates.append(source)

                unique_sources.append(source)

            except Exception as e:
                logger.warning(f"Deduplication failed for {source.raw.url}: {e}")
                continue

        return DeduplicationResult(
            unique_sources=unique_sources,
            duplicate_count=duplicate_count,
            enrichment_candidates=enrichment_candidates,
            new_concept_candidates=new_concept_candidates
        ), total_tokens

    # ========================================================================
    # Step 7: Create or Enrich Cards
    # ========================================================================

    async def _create_or_enrich_cards(
        self,
        dedup_result: DeduplicationResult,
        config: DiscoveryConfig
    ) -> CardActionResult:
        """
        Create new cards or enrich existing ones based on deduplication results.

        Args:
            dedup_result: Deduplication results
            config: Run configuration

        Returns:
            CardActionResult with action statistics
        """
        cards_created = []
        cards_enriched = []
        sources_added = 0
        auto_approved = 0
        pending_review = 0

        # Process enrichment candidates first
        for source, card_id, similarity in dedup_result.enrichment_candidates:
            try:
                source_id = await self._store_source_to_card(source, card_id)
                if source_id:
                    sources_added += 1
                    if card_id not in cards_enriched:
                        cards_enriched.append(card_id)
            except Exception as e:
                logger.warning(f"Failed to enrich card {card_id}: {e}")

        # Process new concept candidates
        for source in dedup_result.new_concept_candidates:
            if not source.analysis or not source.analysis.is_new_concept:
                continue

            try:
                # Calculate confidence score for auto-approval
                confidence = self._calculate_discovery_confidence(source)

                # Create new card
                card_id = await self._create_card_from_source(source)
                if not card_id:
                    continue

                cards_created.append(card_id)

                # Store source to new card
                source_id = await self._store_source_to_card(source, card_id)
                if source_id:
                    sources_added += 1

                # Auto-approve if confidence exceeds threshold
                if confidence >= config.auto_approve_threshold:
                    await self._auto_approve_card(card_id)
                    auto_approved += 1
                else:
                    pending_review += 1

            except Exception as e:
                logger.warning(f"Failed to create card for {source.raw.title}: {e}")

        return CardActionResult(
            cards_created=cards_created,
            cards_enriched=cards_enriched,
            sources_added=sources_added,
            auto_approved=auto_approved,
            pending_review=pending_review
        )

    def _calculate_discovery_confidence(self, source: ProcessedSource) -> float:
        """
        Calculate confidence score for a discovered source.

        Combines triage confidence, analysis scores, and source quality.

        Args:
            source: Processed source

        Returns:
            Confidence score between 0 and 1
        """
        if not source.analysis:
            return 0.5

        # Weight different factors
        triage_weight = 0.2
        credibility_weight = 0.3
        relevance_weight = 0.3
        novelty_weight = 0.2

        # Normalize scores (credibility, relevance, novelty are 1-5 scale)
        triage_score = source.triage.confidence if source.triage else 0.5
        credibility_score = (source.analysis.credibility - 1) / 4  # Convert 1-5 to 0-1
        relevance_score = (source.analysis.relevance - 1) / 4
        novelty_score = (source.analysis.novelty - 1) / 4

        confidence = (
            triage_score * triage_weight +
            credibility_score * credibility_weight +
            relevance_score * relevance_weight +
            novelty_score * novelty_weight
        )

        return min(max(confidence, 0.0), 1.0)

    async def _create_card_from_source(
        self,
        source: ProcessedSource
    ) -> Optional[str]:
        """
        Create a new card from a processed source.

        Args:
            source: Processed source with analysis

        Returns:
            New card ID or None if failed
        """
        if not source.analysis:
            return None

        analysis = source.analysis

        # Generate slug
        slug = analysis.suggested_card_name.lower()
        slug = "".join(c if c.isalnum() or c == " " else "" for c in slug)
        slug = "-".join(slug.split())[:50]

        # Ensure unique slug
        existing = self.supabase.table("cards").select("id").eq("slug", slug).execute()
        if existing.data:
            slug = f"{slug}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        try:
            result = self.supabase.table("cards").insert({
                "name": analysis.suggested_card_name,
                "slug": slug,
                "summary": analysis.summary,

                "horizon": analysis.horizon,
                "stage_id": analysis.suggested_stage,
                "pillar_id": analysis.pillars[0] if analysis.pillars else None,
                "goal_id": analysis.goals[0] if analysis.goals else None,

                # Scoring (4-dimensional: Impact, Velocity, Novelty, Risk)
                "maturity_score": int(analysis.credibility * 20),
                "novelty_score": int(analysis.novelty * 20),
                "impact_score": int(analysis.impact * 20),
                "relevance_score": int(analysis.relevance * 20),
                "velocity_score": int(analysis.velocity * 10),  # 1-10 scale to 0-100
                "risk_score": int(analysis.risk * 10),  # 1-10 scale to 0-100

                "status": "draft",  # New cards start as draft
                "discovery_source": "automated",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }).execute()

            if result.data:
                card_id = result.data[0]["id"]

                # Create timeline event
                await self._create_timeline_event(
                    card_id=card_id,
                    event_type="discovered",
                    description=f"Card discovered via automated scan"
                )

                return card_id

        except Exception as e:
            logger.error(f"Failed to create card: {e}")

        return None

    async def _store_source_to_card(
        self,
        source: ProcessedSource,
        card_id: str
    ) -> Optional[str]:
        """
        Store a processed source to a card.

        Args:
            source: Processed source
            card_id: Target card ID

        Returns:
            Source ID or None if failed
        """
        try:
            # Check for duplicate URL
            existing = self.supabase.table("sources").select("id").eq(
                "card_id", card_id
            ).eq("url", source.raw.url).execute()

            if existing.data:
                return None

            result = self.supabase.table("sources").insert({
                "card_id": card_id,
                "url": source.raw.url,
                "title": (source.raw.title or "Untitled")[:500],
                "publication": (source.raw.source_name or "")[:200] if source.raw.source_name else None,
                "full_text": source.raw.content[:10000] if source.raw.content else None,
                "ai_summary": source.analysis.summary if source.analysis else None,
                "key_excerpts": source.analysis.key_excerpts[:5] if source.analysis and source.analysis.key_excerpts else [],
                "relevance_to_card": source.analysis.relevance if source.analysis else 0.5,
                "api_source": "discovery_scan",
                "ingested_at": datetime.now().isoformat(),
            }).execute()

            if result.data:
                return result.data[0]["id"]

        except Exception as e:
            logger.error(f"Failed to store source: {e}")

        return None

    async def _auto_approve_card(self, card_id: str) -> None:
        """
        Auto-approve a card that meets confidence threshold.

        Args:
            card_id: Card to approve
        """
        try:
            self.supabase.table("cards").update({
                "status": "active",
                "auto_approved_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }).eq("id", card_id).execute()

            await self._create_timeline_event(
                card_id=card_id,
                event_type="auto_approved",
                description="Card auto-approved based on high confidence score"
            )

        except Exception as e:
            logger.warning(f"Failed to auto-approve card {card_id}: {e}")

    async def _create_timeline_event(
        self,
        card_id: str,
        event_type: str,
        description: str,
        source_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """Create a timeline event for a card."""
        try:
            self.supabase.table("card_timeline").insert({
                "card_id": card_id,
                "event_type": event_type,
                "title": event_type.replace("_", " ").title(),
                "description": description,
                "triggered_by_source_id": source_id,
                "metadata": metadata or {},
                "created_at": datetime.now().isoformat()
            }).execute()
        except Exception as e:
            logger.warning(f"Failed to create timeline event: {e}")

    # ========================================================================
    # Step 8: Update Run Record
    # ========================================================================

    async def _update_run_record(
        self,
        run_id: str,
        result: DiscoveryResult
    ) -> None:
        """
        Update the discovery run record with results.

        Args:
            run_id: Run ID
            result: Discovery result
        """
        try:
            self.supabase.table("discovery_runs").update({
                "status": result.status.value,
                "completed_at": result.completed_at.isoformat() if result.completed_at else None,
                "queries_generated": result.queries_generated,
                "queries_executed": result.queries_executed,
                "sources_discovered": result.sources_discovered,
                "sources_triaged": result.sources_triaged,
                "sources_blocked": result.sources_blocked,
                "sources_duplicate": result.sources_duplicate,
                "cards_created": result.cards_created,
                "cards_enriched": result.cards_enriched,
                "sources_added": result.sources_added,
                "auto_approved": result.auto_approved,
                "pending_review": result.pending_review,
                "estimated_cost": result.estimated_cost,
                "execution_time_seconds": result.execution_time_seconds,
                "summary_report": result.summary_report,
                "errors": result.errors,
            }).eq("id", run_id).execute()
        except Exception as e:
            logger.warning(f"Failed to update run record: {e}")

    # ========================================================================
    # Step 9: Finalize Run
    # ========================================================================

    async def _finalize_run(
        self,
        run_id: str,
        start_time: datetime,
        queries_generated: int,
        queries_executed: int,
        sources_discovered: int,
        sources_triaged: int,
        sources_blocked: int,
        sources_duplicate: int,
        card_result: CardActionResult,
        cost: float,
        errors: List[str],
        status: DiscoveryStatus,
        sources_by_category: Optional[Dict[str, int]] = None,
        categories_fetched: int = 0,
        diversity_metrics: Optional[SourceDiversityMetrics] = None,
        processing_time_metrics: Optional[ProcessingTimeMetrics] = None,
        api_token_usage_metrics: Optional[APITokenUsage] = None
    ) -> DiscoveryResult:
        """
        Finalize the discovery run and generate summary report.

        Args:
            run_id: Run ID
            start_time: When run started
            ... (various statistics)
            status: Final status
            sources_by_category: Count of sources per category (5 categories)
            categories_fetched: Number of source categories that contributed
            diversity_metrics: Computed source diversity metrics
            processing_time_metrics: Granular timing metrics for each phase
            api_token_usage_metrics: Token usage metrics for API cost tracking

        Returns:
            Complete DiscoveryResult
        """
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        # Default sources_by_category if not provided
        if sources_by_category is None:
            sources_by_category = {}

        # Compute diversity metrics if not provided but we have category data
        if diversity_metrics is None and sources_by_category:
            diversity_metrics = SourceDiversityMetrics.compute(sources_by_category)

        # Generate summary report
        summary = self._generate_summary_report(
            queries_generated=queries_generated,
            queries_executed=queries_executed,
            sources_discovered=sources_discovered,
            sources_triaged=sources_triaged,
            sources_blocked=sources_blocked,
            sources_duplicate=sources_duplicate,
            sources_by_category=sources_by_category,
            categories_fetched=categories_fetched,
            card_result=card_result,
            cost=cost,
            execution_time=execution_time,
            errors=errors,
            diversity_metrics=diversity_metrics,
            processing_time_metrics=processing_time_metrics,
            api_token_usage_metrics=api_token_usage_metrics
        )

        result = DiscoveryResult(
            run_id=run_id,
            status=status,
            started_at=start_time,
            completed_at=end_time,
            queries_generated=queries_generated,
            queries_executed=queries_executed,
            sources_discovered=sources_discovered,
            sources_triaged=sources_triaged,
            sources_blocked=sources_blocked,
            sources_duplicate=sources_duplicate,
            sources_by_category=sources_by_category,
            categories_fetched=categories_fetched,
            diversity_metrics=diversity_metrics.to_dict() if diversity_metrics else None,
            cards_created=card_result.cards_created,
            cards_enriched=card_result.cards_enriched,
            sources_added=card_result.sources_added,
            auto_approved=card_result.auto_approved,
            pending_review=card_result.pending_review,
            estimated_cost=cost,
            execution_time_seconds=execution_time,
            processing_time=processing_time_metrics.to_dict() if processing_time_metrics else None,
            api_token_usage=api_token_usage_metrics.to_dict() if api_token_usage_metrics else None,
            summary_report=summary,
            errors=errors
        )

        # Update database record
        await self._update_run_record(run_id, result)

        logger.info(f"Discovery run {run_id} completed: {summary[:200]}...")

        return result

    def _generate_summary_report(
        self,
        queries_generated: int,
        queries_executed: int,
        sources_discovered: int,
        sources_triaged: int,
        sources_blocked: int,
        sources_duplicate: int,
        card_result: CardActionResult,
        cost: float,
        execution_time: float,
        errors: List[str],
        sources_by_category: Optional[Dict[str, int]] = None,
        categories_fetched: int = 0,
        diversity_metrics: Optional[SourceDiversityMetrics] = None,
        processing_time_metrics: Optional[ProcessingTimeMetrics] = None,
        api_token_usage_metrics: Optional[APITokenUsage] = None
    ) -> str:
        """Generate a human-readable summary report."""
        report = f"""# Discovery Run Summary

## Overview
- **Queries Generated**: {queries_generated}
- **Queries Executed**: {queries_executed}
- **Execution Time**: {execution_time:.1f} seconds
- **Estimated Cost**: ${cost:.4f}

## Sources
- **Discovered**: {sources_discovered}
- **Passed Triage**: {sources_triaged}
- **Blocked**: {sources_blocked}
- **Duplicates**: {sources_duplicate}
"""

        # Add source category breakdown if available
        if sources_by_category:
            report += f"""
## Source Categories ({categories_fetched}/5 categories)
"""
            for category, count in sources_by_category.items():
                if count > 0:
                    report += f"- **{category}**: {count} sources\n"

        # Add diversity metrics if available
        if diversity_metrics:
            report += f"""
## Source Diversity Metrics
- **Category Coverage**: {diversity_metrics.category_coverage:.1%}
- **Balance Score**: {diversity_metrics.balance_score:.2f}
- **Shannon Entropy**: {diversity_metrics.shannon_entropy:.2f}
"""
            if diversity_metrics.dominant_category:
                report += f"- **Dominant Category**: {diversity_metrics.dominant_category}\n"
            if diversity_metrics.underrepresented_categories:
                report += f"- **Underrepresented**: {', '.join(diversity_metrics.underrepresented_categories)}\n"

        # Add processing time breakdown if available
        if processing_time_metrics:
            report += f"""
## Processing Time Breakdown
- **Query Generation**: {processing_time_metrics.query_generation_seconds:.2f}s
- **Multi-Source Fetch**: {processing_time_metrics.multi_source_fetch_seconds:.2f}s
- **Query Search**: {processing_time_metrics.query_search_seconds:.2f}s
- **Triage**: {processing_time_metrics.triage_seconds:.2f}s
- **Block Check**: {processing_time_metrics.blocked_topic_check_seconds:.2f}s
- **Deduplication**: {processing_time_metrics.deduplication_seconds:.2f}s
- **Card Creation**: {processing_time_metrics.card_creation_seconds:.2f}s
- **Total**: {processing_time_metrics.total_seconds:.2f}s
"""

        # Add API token usage if available
        if api_token_usage_metrics:
            report += f"""
## API Token Usage
- **Triage Tokens**: {api_token_usage_metrics.triage_tokens:,}
- **Analysis Tokens**: {api_token_usage_metrics.analysis_tokens:,}
- **Embedding Tokens**: {api_token_usage_metrics.embedding_tokens:,}
- **Card Match Tokens**: {api_token_usage_metrics.card_match_tokens:,}
- **Total Tokens**: {api_token_usage_metrics.total_tokens:,}
- **Estimated Cost**: ${api_token_usage_metrics.estimated_cost_usd:.4f}
"""

        report += f"""
## Cards
- **Created**: {len(card_result.cards_created)}
- **Enriched**: {len(card_result.cards_enriched)}
- **Sources Added**: {card_result.sources_added}
- **Auto-Approved**: {card_result.auto_approved}
- **Pending Review**: {card_result.pending_review}
"""

        if errors:
            report += f"\n## Errors\n"
            for error in errors:
                report += f"- {error}\n"

        return report


# ============================================================================
# Convenience Functions
# ============================================================================

async def run_weekly_discovery(
    supabase: Client,
    openai_client: openai.OpenAI,
    pillars: Optional[List[str]] = None
) -> DiscoveryResult:
    """
    Convenience function to run weekly discovery scan.

    Args:
        supabase: Supabase client
        openai_client: OpenAI client
        pillars: Optional list of pillar codes to filter

    Returns:
        DiscoveryResult
    """
    service = DiscoveryService(supabase, openai_client)
    config = DiscoveryConfig(
        max_queries_per_run=100,
        max_sources_total=500,
        pillars_filter=pillars or [],
        include_priorities=True
    )
    return await service.execute_discovery_run(config)


async def run_pillar_discovery(
    supabase: Client,
    openai_client: openai.OpenAI,
    pillar_code: str
) -> DiscoveryResult:
    """
    Run discovery for a specific pillar.

    Args:
        supabase: Supabase client
        openai_client: OpenAI client
        pillar_code: Pillar code (e.g., 'CH', 'MC')

    Returns:
        DiscoveryResult
    """
    service = DiscoveryService(supabase, openai_client)
    config = DiscoveryConfig(
        max_queries_per_run=25,
        max_sources_total=100,
        pillars_filter=[pillar_code],
        include_priorities=True
    )
    return await service.execute_discovery_run(config)
