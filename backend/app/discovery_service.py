"""
Discovery orchestration service for GrantScope.

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
- Multi-source content ingestion from 7 categories:
  1. RSS/Atom feeds - Curated feeds from various sources
  2. News outlets - Major news sites (Reuters, AP News, GCN)
  3. Academic publications - arXiv research papers
  4. Government sources - .gov domains, policy documents
  5. Tech blogs - TechCrunch, Ars Technica, company blogs
  6. Grants.gov - Federal grant opportunities
  7. SAM.gov - Federal procurement and grant opportunities

Usage:
    from app.discovery_service import DiscoveryService, DiscoveryConfig

    service = DiscoveryService(db_session, openai_client)
    config = DiscoveryConfig(
        max_queries_per_run=50,
        max_sources_total=200,
        pillars_filter=['CH', 'MC']
    )
    result = await service.execute_discovery_run(config)
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
import uuid

import openai
from sqlalchemy import (
    select,
    update as sa_update,
    delete as sa_delete,
    func,
    and_,
    or_,
    text,
)
from sqlalchemy.ext.asyncio import AsyncSession

from .query_generator import QueryGenerator, QueryConfig
from .ai_service import AIService, AnalysisResult, TriageResult
from .research_service import RawSource, ProcessedSource
from .source_validator import SourceValidator
from .story_clustering_service import cluster_sources, get_cluster_count
from . import domain_reputation_service

# SQLAlchemy ORM models
from app.models.db.card import Card
from app.models.db.source import Source, DiscoveredSource
from app.models.db.card_extras import CardTimeline
from app.models.db.discovery import DiscoveryRun, DiscoveryBlock
from app.models.db.workstream import Workstream, WorkstreamCard
from app.helpers.db_utils import compose_embedding_text, vector_search_cards

# Import multi-source content fetchers (7 categories)
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
# Source Category Tracking (7 Categories)
# ============================================================================


class SourceCategory(Enum):
    """
    Content source categories for multi-source ingestion.

    The pipeline fetches from 7 diverse source categories to ensure
    comprehensive coverage of emerging trends and technologies.
    """

    RSS = "rss"  # RSS/Atom feeds from curated sources
    NEWS = "news"  # Major news outlets (Reuters, AP, GCN)
    ACADEMIC = "academic"  # Academic publications (arXiv)
    GOVERNMENT = "government"  # Government sources (.gov domains)
    TECH_BLOG = "tech_blog"  # Tech blogs (TechCrunch, Ars Technica)
    GRANTS_GOV = "grants_gov"  # Grants.gov federal grant opportunities
    SAM_GOV = "sam_gov"  # SAM.gov procurement and grant opportunities


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
# Environment-based defaults (can be overridden in .env)
# ============================================================================


def get_discovery_defaults():
    """Get discovery defaults from environment variables."""
    return {
        "max_queries": int(os.getenv("DISCOVERY_MAX_QUERIES", "100")),
        "max_sources_per_query": int(
            os.getenv("DISCOVERY_MAX_SOURCES_PER_QUERY", "10")
        ),
        "max_sources_total": int(os.getenv("DISCOVERY_MAX_SOURCES_TOTAL", "500")),
    }


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

    # Query limits - defaults come from environment
    max_queries_per_run: int = None
    max_sources_per_query: int = None
    max_sources_total: int = None

    # Thresholds - TUNED TO PREFER ENRICHMENT OVER CREATION
    auto_approve_threshold: float = 0.95  # Auto-approve confidence threshold
    similarity_threshold: float = (
        0.85  # Strong match - add to existing card (lowered from 0.92)
    )
    weak_match_threshold: float = (
        0.75  # Weak match - check with LLM (lowered from 0.82)
    )
    name_similarity_threshold: float = 0.80  # Name-based matching threshold

    # Card creation limits - PREVENT RUNAWAY CARD CREATION
    max_new_cards_per_run: int = 15  # Maximum new cards per discovery run

    # Filtering
    pillars_filter: List[str] = field(default_factory=list)  # Empty = all pillars
    horizons_filter: List[str] = field(default_factory=list)  # Empty = all horizons

    # Options
    include_priorities: bool = True
    dry_run: bool = False  # If True, don't persist anything
    skip_blocked_topics: bool = True
    use_signal_agent: bool = (
        True  # Use AI agent for signal detection instead of deterministic clustering
    )

    # Multi-source category configuration
    source_categories: Dict[str, SourceCategoryConfig] = field(default_factory=dict)
    enable_multi_source: bool = True  # Enable fetching from all 7 source categories
    search_topics: List[str] = field(default_factory=list)  # Topics for source searches

    def __post_init__(self):
        """Apply environment defaults and initialize source category configurations."""
        # Step 1: Apply environment defaults for any None values
        defaults = get_discovery_defaults()
        if self.max_queries_per_run is None:
            self.max_queries_per_run = defaults["max_queries"]
        if self.max_sources_per_query is None:
            self.max_sources_per_query = defaults["max_sources_per_query"]
        if self.max_sources_total is None:
            self.max_sources_total = defaults["max_sources_total"]

        # Step 2: Initialize default source category configurations
        if not self.source_categories:
            self.source_categories = {
                SourceCategory.RSS.value: SourceCategoryConfig(
                    enabled=True, max_sources=50, rss_feeds=DEFAULT_RSS_FEEDS.copy()
                ),
                SourceCategory.NEWS.value: SourceCategoryConfig(
                    enabled=True, max_sources=30
                ),
                SourceCategory.ACADEMIC.value: SourceCategoryConfig(
                    enabled=True, max_sources=30
                ),
                SourceCategory.GOVERNMENT.value: SourceCategoryConfig(
                    enabled=True, max_sources=30
                ),
                SourceCategory.TECH_BLOG.value: SourceCategoryConfig(
                    enabled=True, max_sources=30
                ),
                SourceCategory.GRANTS_GOV.value: SourceCategoryConfig(
                    enabled=True, max_sources=50
                ),
                SourceCategory.SAM_GOV.value: SourceCategoryConfig(
                    enabled=True, max_sources=50
                ),
            }
        if not self.search_topics:
            self.search_topics = DEFAULT_SEARCH_TOPICS.copy()


async def apply_admin_settings(
    config: DiscoveryConfig, db: AsyncSession
) -> DiscoveryConfig:
    """Apply admin-configured discovery settings from ``system_settings``.

    Reads ``discovery_config`` from the database (cached 60s) and overrides
    matching fields on the provided config.  Falls back gracefully when no
    settings exist.
    """
    try:
        from app.helpers.settings_reader import get_setting

        admin_cfg = await get_setting(db, "discovery_config", None)
        if not isinstance(admin_cfg, dict):
            return config

        if "auto_approve_threshold" in admin_cfg:
            config.auto_approve_threshold = float(admin_cfg["auto_approve_threshold"])
        if "similarity_threshold" in admin_cfg:
            config.similarity_threshold = float(admin_cfg["similarity_threshold"])
        if "weak_match_threshold" in admin_cfg:
            config.weak_match_threshold = float(admin_cfg["weak_match_threshold"])
        if "max_new_cards_per_run" in admin_cfg:
            config.max_new_cards_per_run = int(admin_cfg["max_new_cards_per_run"])
        if "max_queries_per_run" in admin_cfg:
            config.max_queries_per_run = int(admin_cfg["max_queries_per_run"])
        if "max_sources_total" in admin_cfg:
            config.max_sources_total = int(admin_cfg["max_sources_total"])
    except Exception as exc:
        logger.warning("discovery: failed to read admin settings: %s", exc)

    return config


def apply_source_preferences(
    config: DiscoveryConfig, source_prefs: dict
) -> DiscoveryConfig:
    """
    Apply card-level source_preferences to a DiscoveryConfig.

    Reads the source_preferences JSONB from a card and overrides
    the config's source category toggles, custom RSS feeds,
    search topics (keywords), and priority domains.

    Args:
        config: Base discovery configuration to modify
        source_prefs: Dict from cards.source_preferences column

    Returns:
        Modified DiscoveryConfig with preferences applied
    """
    if not source_prefs:
        return config

    # Map frontend category names to SourceCategory enum values
    category_map = {
        "news": SourceCategory.NEWS.value,
        "academic": SourceCategory.ACADEMIC.value,
        "government": SourceCategory.GOVERNMENT.value,
        "tech_blog": SourceCategory.TECH_BLOG.value,
        "rss": SourceCategory.RSS.value,
        "grants_gov": SourceCategory.GRANTS_GOV.value,
        "sam_gov": SourceCategory.SAM_GOV.value,
    }

    # Apply enabled_categories: disable any category not in the list
    enabled = source_prefs.get("enabled_categories")
    if enabled and isinstance(enabled, list):
        enabled_values = {category_map.get(c) for c in enabled if c in category_map}
        for cat_key, cat_config in config.source_categories.items():
            cat_config.enabled = cat_key in enabled_values

    # Apply custom_rss_feeds: add to RSS category config
    custom_feeds = source_prefs.get("custom_rss_feeds")
    if custom_feeds and isinstance(custom_feeds, list):
        if rss_config := config.source_categories.get(SourceCategory.RSS.value):
            rss_config.rss_feeds = list(set(rss_config.rss_feeds + custom_feeds))
            rss_config.enabled = True

    # Apply keywords as search topics
    keywords = source_prefs.get("keywords")
    if keywords and isinstance(keywords, list):
        config.search_topics = list(set(config.search_topics + keywords))

    return config


class DiscoveryStatus(Enum):
    """Status of a discovery run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CardAction(Enum):
    """Action taken for a source during discovery."""

    CREATED = "created"  # New card created
    ENRICHED = "enriched"  # Added to existing card
    AUTO_APPROVED = "auto_approved"  # New card auto-approved
    PENDING_REVIEW = "pending_review"  # Awaiting human review
    DUPLICATE = "duplicate"  # Duplicate of existing source
    BLOCKED = "blocked"  # Matched blocked topic
    FILTERED = "filtered"  # Filtered by triage


# Stage number to ID mapping (matches stages table)
STAGE_NUMBER_TO_ID = {
    1: "1_concept",
    2: "2_exploring",
    3: "3_pilot",
    4: "4_proof",
    5: "5_implementing",
    6: "6_scaling",
    7: "7_mature",
    8: "8_declining",
}


# Pillar code mapping: AI codes -> Database pillar IDs
# All 6 canonical pillar codes pass through natively (no lossy conversion).
# The database pillars table has been updated to match the AI taxonomy.
PILLAR_CODE_MAP = {
    "CH": "CH",  # Community Health & Sustainability
    "EW": "EW",  # Economic & Workforce Development
    "HG": "HG",  # High-Performing Government
    "HH": "HH",  # Homelessness & Housing
    "MC": "MC",  # Mobility & Critical Infrastructure
    "PS": "PS",  # Public Safety
}


def convert_pillar_id(ai_pillar: str) -> Optional[str]:
    """
    Convert AI pillar code to database pillar ID.

    All 6 canonical pillar codes (CH, EW, HG, HH, MC, PS) pass through
    natively. Unknown codes are returned as-is.
    """
    if not ai_pillar:
        return None

    # Try direct mapping first
    if ai_pillar in PILLAR_CODE_MAP:
        return PILLAR_CODE_MAP[ai_pillar]

    # If not in map, return as-is (may fail FK constraint)
    logger.warning(f"Unknown pillar code: {ai_pillar}, using as-is")
    return ai_pillar


def convert_goal_id(ai_goal: str) -> str:
    """
    Convert AI goal format (e.g., "CH.1") to database format (e.g., "CH-01").

    AI returns: "CH.1", "MC.3", "HG.2"
    Database expects: "CH-01", "MC-03", "HG-02"
    """
    if not ai_goal or "." not in ai_goal:
        return ai_goal

    parts = ai_goal.split(".")
    if len(parts) != 2:
        return ai_goal

    pillar = parts[0]
    try:
        number = int(parts[1])
        # Pillar code passes through natively (no lossy conversion)
        mapped_pillar = PILLAR_CODE_MAP.get(pillar, pillar)
        return f"{mapped_pillar}-{number:02d}"
    except ValueError:
        return ai_goal


def calculate_name_similarity(name1: str, name2: str) -> float:
    """
    Calculate similarity between two card/concept names.
    Uses normalized Levenshtein-like comparison for fuzzy matching.

    Returns a score between 0.0 and 1.0.
    """
    if not name1 or not name2:
        return 0.0

    # Normalize: lowercase, remove punctuation, strip whitespace
    import re

    def normalize(s):
        s = s.lower().strip()
        s = re.sub(r"[^\w\s]", "", s)
        return " ".join(s.split())

    n1 = normalize(name1)
    n2 = normalize(name2)

    if n1 == n2:
        return 1.0

    # Check if one contains the other (high similarity)
    if n1 in n2 or n2 in n1:
        shorter = min(len(n1), len(n2))
        longer = max(len(n1), len(n2))
        return shorter / longer if longer > 0 else 0.0

    # Word overlap calculation
    words1 = set(n1.split())
    words2 = set(n2.split())

    if not words1 or not words2:
        return 0.0

    intersection = words1 & words2
    union = words1 | words2

    # Jaccard similarity
    return len(intersection) / len(union) if union else 0.0


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors in Python.

    This is a fallback when the database RPC function fails due to
    vector extension schema issues.

    Args:
        vec1: First embedding vector
        vec2: Second embedding vector

    Returns:
        Cosine similarity score between 0.0 and 1.0
    """
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0

    # Calculate dot product and magnitudes
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = sum(a * a for a in vec1) ** 0.5
    magnitude2 = sum(b * b for b in vec2) ** 0.5

    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    return dot_product / (magnitude1 * magnitude2)


# ============================================================================
# Result Classes
# ============================================================================


@dataclass
class DeduplicationResult:
    """Result of deduplication process."""

    unique_sources: List[ProcessedSource]
    duplicate_count: int
    enrichment_candidates: List[
        Tuple[ProcessedSource, str, float]
    ]  # (source, card_id, similarity)
    new_concept_candidates: List[ProcessedSource]


@dataclass
class CardActionResult:
    """Result of card creation/enrichment."""

    cards_created: List[str]
    cards_enriched: List[str]
    sources_added: int
    auto_approved: int
    pending_review: int
    story_cluster_count: int = 0


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
    balance_score: float  # How evenly distributed sources are
    shannon_entropy: float  # Information-theoretic diversity measure

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
        active_categories = [
            cat for cat, count in sources_by_category.items() if count > 0
        ]
        num_active = len(active_categories)
        num_total_categories = 5  # Total number of source categories

        # Category coverage (0-1)
        category_coverage = (
            num_active / num_total_categories if num_total_categories > 0 else 0.0
        )

        # Balance score: 1 - normalized standard deviation
        # Perfect balance = 1.0, all in one category = 0.0
        if total > 0 and num_active > 0:
            mean_per_category = total / num_total_categories
            variance = (
                sum(
                    (count - mean_per_category) ** 2
                    for count in sources_by_category.values()
                )
                / num_total_categories
            )
            std_dev = math.sqrt(variance)
            max_std_dev = mean_per_category * math.sqrt(
                num_total_categories - 1
            )  # Worst case: all in one category
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
            underrepresented_categories=underrepresented,
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
            self.diversity_metrics = SourceDiversityMetrics.compute(
                self.sources_by_category
            )

    @property
    def category_diversity(self) -> float:
        """Calculate diversity score (0-1) based on category distribution."""
        if self.total_sources == 0:
            return 0.0
        active_categories = sum(
            bool(count > 0) for count in self.sources_by_category.values()
        )
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
        db: AsyncSession,
        openai_client: openai.OpenAI,
        triggered_by_user_id: Optional[str] = None,
    ):
        """
        Initialize discovery service.

        Args:
            db: SQLAlchemy async session for database operations
            openai_client: OpenAI client for AI operations
            triggered_by_user_id: Optional user ID to attribute created cards to
        """
        self.db = db
        self.openai_client = openai_client
        self.triggered_by_user_id = triggered_by_user_id
        self.ai_service = AIService(openai_client)
        self.query_generator = QueryGenerator()

        # Import research service components for search execution
        # Using dynamic import to avoid circular dependencies
        from .research_service import ResearchService

        self.research_service = ResearchService(db, openai_client)

    # ========================================================================
    # Main Entry Point
    # ========================================================================

    async def execute_discovery_run(
        self, config: DiscoveryConfig, existing_run_id: Optional[str] = None
    ) -> DiscoveryResult:
        """
        Execute a complete discovery run.

        Args:
            config: Configuration for this run
            existing_run_id: Optional existing run ID to use (skips creating new record)

        Returns:
            DiscoveryResult with complete statistics
        """
        # Apply admin-configurable settings (cached, 60s TTL)
        config = await apply_admin_settings(config, self.db)

        start_time = datetime.now(timezone.utc)

        # Use existing run_id if provided, otherwise create new record
        if existing_run_id:
            run_id = existing_run_id
            logger.info(f"Using existing discovery run {run_id}")
        else:
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
            await self._update_progress_simple(
                run_id,
                "queries",
                "Generating search queries from pillars and priorities...",
                [],
            )
            step_start = datetime.now(timezone.utc)
            queries = await self._generate_queries(config)
            processing_time.query_generation_seconds = (
                datetime.now(timezone.utc) - step_start
            ).total_seconds()
            logger.info(
                f"Generated {len(queries)} queries in {processing_time.query_generation_seconds:.2f}s"
            )

            # Step 2a: Multi-source content fetching (5 categories)
            raw_sources: List[RawSource] = []
            search_cost = 0.0

            if config.enable_multi_source:
                step_start = datetime.now(timezone.utc)
                logger.info("Fetching from all 5 source categories...")
                multi_source_result = await self._fetch_from_all_source_categories(
                    config
                )
                raw_sources.extend(multi_source_result.sources)
                sources_by_category = multi_source_result.sources_by_category.copy()
                categories_fetched = multi_source_result.categories_fetched
                diversity_metrics = multi_source_result.diversity_metrics
                processing_time.multi_source_fetch_seconds = (
                    datetime.now(timezone.utc) - step_start
                ).total_seconds()

                # Add any multi-source errors to error list
                for (
                    category,
                    cat_errors,
                ) in multi_source_result.errors_by_category.items():
                    for error in cat_errors:
                        errors.append(f"[{category}] {error}")

                logger.info(
                    f"Multi-source fetch: {len(raw_sources)} sources from "
                    f"{categories_fetched}/5 categories in {processing_time.multi_source_fetch_seconds:.2f}s"
                )

            # Step 2b: Execute query-based searches (traditional GPT Researcher + Exa)
            # Note: This step depends on Firecrawl. If Firecrawl is down/out of credits,
            # individual queries will timeout at 120s each. We also cap total step time at 5min.
            if queries:
                step_start = datetime.now(timezone.utc)
                try:
                    query_sources, query_cost = await asyncio.wait_for(
                        self._execute_searches(
                            queries[: config.max_queries_per_run], config
                        ),
                        timeout=300,  # 5 minute total cap for query-based searches
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "Query-based search step timed out after 300s - continuing with multi-source results only"
                    )
                    query_sources, query_cost = [], 0.0
                search_cost += query_cost
                processing_time.query_search_seconds = (
                    datetime.now(timezone.utc) - step_start
                ).total_seconds()

                # Deduplicate query sources against multi-source results
                seen_urls = {s.url for s in raw_sources if s.url}
                for source in query_sources:
                    if source.url and source.url not in seen_urls:
                        seen_urls.add(source.url)
                        raw_sources.append(source)
                        # Track as "query" category
                        sources_by_category["query"] = (
                            sources_by_category.get("query", 0) + 1
                        )

                logger.info(
                    f"Query-based search: {len(query_sources)} additional sources in {processing_time.query_search_seconds:.2f}s"
                )

            logger.info(f"Total raw sources discovered: {len(raw_sources)}")

            if not raw_sources and not queries:
                logger.warning(
                    "No queries generated and no multi-source results - completing run"
                )
                processing_time.total_seconds = (
                    datetime.now(timezone.utc) - start_time
                ).total_seconds()
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
                    api_token_usage_metrics=api_token_usage,
                )

            if not raw_sources:
                logger.warning("No sources discovered - completing run")
                processing_time.total_seconds = (
                    datetime.now(timezone.utc) - start_time
                ).total_seconds()
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
                    api_token_usage_metrics=api_token_usage,
                )

            # Step 2c: Content and freshness validation (Task 2.1)
            # Step 2d: Pre-print detection (Task 2.6)
            validator = SourceValidator()
            validated_sources = []
            content_filter_count = 0
            freshness_filter_count = 0
            preprint_count = 0

            for source in raw_sources:
                content_result = validator.validate_content(source.content or "")
                if not content_result.is_valid:
                    content_filter_count += 1
                    logger.info(
                        f"Source filtered (content): {source.url or 'unknown'} - {content_result.reason_code}"
                    )
                    continue

                freshness_result = validator.validate_freshness(
                    source.published_at,
                    source.source_type or "default",
                )
                if not freshness_result.is_valid:
                    freshness_filter_count += 1
                    logger.info(
                        f"Source filtered (freshness): {source.url or 'unknown'} - {freshness_result.reason_code}"
                    )
                    continue

                # Pre-print detection (Task 2.6): flag before triage so AI can use it
                preprint_result = validator.detect_preprint(
                    source.url or "", source.content
                )
                if preprint_result.is_preprint:
                    source.is_preprint = True
                    preprint_count += 1
                    logger.info(
                        f"Pre-print detected ({preprint_result.confidence}): "
                        f"{source.url or 'unknown'} - {preprint_result.indicators}"
                    )

                validated_sources.append(source)

            logger.info(
                f"Content validation: {content_filter_count} filtered, "
                f"freshness validation: {freshness_filter_count} filtered, "
                f"pre-prints detected: {preprint_count}, "
                f"{len(validated_sources)}/{len(raw_sources)} sources passed"
            )

            # Persist quality_stats to discovery run's summary_report
            quality_stats = {
                "content_filter_count": content_filter_count,
                "freshness_filter_count": freshness_filter_count,
                "preprint_count": preprint_count,
                "sources_before_validation": len(raw_sources),
                "sources_after_validation": len(validated_sources),
            }
            try:
                result_dr = await self.db.execute(
                    select(DiscoveryRun).where(
                        DiscoveryRun.id == uuid.UUID(run_id)
                        if isinstance(run_id, str)
                        else run_id
                    )
                )
                dr_row = result_dr.scalar_one_or_none()
                report = (
                    dr_row.summary_report if dr_row and dr_row.summary_report else {}
                ) or {}
                if not isinstance(report, dict):
                    report = {}
                report["quality_stats"] = quality_stats
                await self.db.execute(
                    sa_update(DiscoveryRun)
                    .where(
                        DiscoveryRun.id
                        == (uuid.UUID(run_id) if isinstance(run_id, str) else run_id)
                    )
                    .values(summary_report=report)
                )
                await self.db.flush()
            except Exception as e:
                logger.warning(f"Failed to persist quality_stats: {e}")

            # Step 2e: Preload domain reputation cache (Task 2.7)
            try:
                source_urls = [s.url for s in validated_sources if s.url]
                await domain_reputation_service.get_reputation_batch(
                    self.db, source_urls
                )
                logger.info(
                    "Domain reputation cache preloaded for %d source URLs",
                    len(source_urls),
                )
            except Exception as e:
                logger.warning(
                    f"Domain reputation cache preload failed (non-fatal): {e}"
                )

            # Step 3: Triage sources
            await self._update_progress_simple(
                run_id,
                "triage",
                f"Triaging {len(validated_sources)} sources for relevance...",
                ["queries", "search"],
                {"queries_generated": len(queries), "sources_found": len(raw_sources)},
            )
            step_start = datetime.now(timezone.utc)
            self._current_run_id = (
                run_id  # For domain reputation stats persistence (Task 2.7)
            )
            triaged_sources, triage_tokens = await self._triage_sources_with_metrics(
                validated_sources
            )
            processing_time.triage_seconds = (
                datetime.now(timezone.utc) - step_start
            ).total_seconds()
            api_token_usage.add_tokens("triage", triage_tokens)
            logger.info(
                f"Triaged to {len(triaged_sources)} relevant sources in {processing_time.triage_seconds:.2f}s"
            )

            # Step 3b: Clear domain reputation batch cache (Task 2.7)
            try:
                domain_reputation_service.clear_batch_cache()
            except Exception:
                pass  # Non-fatal

            # Step 4: Check blocked topics
            await self._update_progress_simple(
                run_id,
                "blocked",
                f"Checking {len(triaged_sources)} sources against blocked topics...",
                ["queries", "search", "triage"],
                {
                    "queries_generated": len(queries),
                    "sources_found": len(raw_sources),
                    "sources_relevant": len(triaged_sources),
                },
            )
            step_start = datetime.now(timezone.utc)
            if config.skip_blocked_topics:
                filtered_sources, blocked_count = await self._check_blocked_topics(
                    triaged_sources
                )
                logger.info(f"Filtered {blocked_count} blocked sources")
            else:
                filtered_sources = triaged_sources
                blocked_count = 0
            processing_time.blocked_topic_check_seconds = (
                datetime.now(timezone.utc) - step_start
            ).total_seconds()

            # Step 5-6: Signal detection (agent-based or legacy)
            step_start = datetime.now(timezone.utc)

            # Initialize dedup_result for both paths (signal agent skips dedup)
            dedup_result = DeduplicationResult(
                unique_sources=[],
                duplicate_count=0,
                enrichment_candidates=[],
                new_concept_candidates=[],
            )

            if config.use_signal_agent and not config.dry_run:
                # --- AI Agent-based signal detection ---
                from app.signal_agent_service import SignalAgentService

                await self._update_progress_simple(
                    run_id,
                    "signals",
                    f"AI agent analyzing {len(filtered_sources)} sources for signal detection...",
                    ["queries", "search", "triage", "blocked"],
                    {
                        "queries_generated": len(queries),
                        "sources_found": len(raw_sources),
                        "sources_relevant": len(triaged_sources),
                    },
                )

                signal_agent = SignalAgentService(
                    db=self.db,
                    run_id=run_id,
                    triggered_by_user_id=self.triggered_by_user_id,
                )
                signal_result = await signal_agent.run_signal_detection(
                    processed_sources=filtered_sources,
                    config=config,
                )

                # Map SignalDetectionResult -> CardActionResult for backward compat
                card_result = CardActionResult(
                    cards_created=signal_result.signals_created,
                    cards_enriched=signal_result.signals_enriched,
                    sources_added=signal_result.sources_linked,
                    auto_approved=signal_result.auto_approved_count,
                    pending_review=len(signal_result.signals_created)
                    - signal_result.auto_approved_count,
                    story_cluster_count=0,
                )
                logger.info(
                    f"Signal agent: {len(signal_result.signals_created)} signals created, "
                    f"{len(signal_result.signals_enriched)} enriched, "
                    f"{signal_result.sources_linked} sources linked, "
                    f"cost ~${signal_result.cost_estimate:.2f}"
                )
            else:
                # --- Legacy deterministic pipeline ---
                await self._update_progress_simple(
                    run_id,
                    "dedupe",
                    f"Deduplicating {len(filtered_sources)} sources against existing cards...",
                    ["queries", "search", "triage", "blocked"],
                    {
                        "queries_generated": len(queries),
                        "sources_found": len(raw_sources),
                        "sources_relevant": len(triaged_sources),
                    },
                )
                dedup_result, dedup_tokens = (
                    await self._deduplicate_sources_with_metrics(
                        filtered_sources, config
                    )
                )
                api_token_usage.add_tokens("card_match", dedup_tokens)
                logger.info(
                    f"Deduplication: {dedup_result.duplicate_count} duplicates, "
                    f"{len(dedup_result.enrichment_candidates)} enrichments, "
                    f"{len(dedup_result.new_concept_candidates)} new concepts"
                )

                await self._update_progress_simple(
                    run_id,
                    "cards",
                    f"Creating/enriching cards from {len(dedup_result.new_concept_candidates)} new concepts...",
                    ["queries", "search", "triage", "blocked", "dedupe"],
                    {
                        "queries_generated": len(queries),
                        "sources_found": len(raw_sources),
                        "sources_relevant": len(triaged_sources),
                        "duplicates": dedup_result.duplicate_count,
                        "enrichments": len(dedup_result.enrichment_candidates),
                        "new_concepts": len(dedup_result.new_concept_candidates),
                    },
                )
                if config.dry_run:
                    logger.info("Dry run - skipping card creation/enrichment")
                    card_result = CardActionResult([], [], 0, 0, 0)
                else:
                    card_result = await self._create_or_enrich_cards(
                        run_id, dedup_result, config
                    )
                    logger.info(
                        f"Card actions: {len(card_result.cards_created)} created, "
                        f"{len(card_result.cards_enriched)} enriched, "
                        f"{card_result.auto_approved} auto-approved"
                    )

            processing_time.card_creation_seconds = (
                datetime.now(timezone.utc) - step_start
            ).total_seconds()

            # Persist story_cluster_count to quality_stats
            if card_result.story_cluster_count > 0:
                try:
                    _run_id = uuid.UUID(run_id) if isinstance(run_id, str) else run_id
                    result_dr = await self.db.execute(
                        select(DiscoveryRun).where(DiscoveryRun.id == _run_id)
                    )
                    dr_row = result_dr.scalar_one_or_none()
                    report = (
                        dr_row.summary_report
                        if dr_row and dr_row.summary_report
                        else {}
                    ) or {}
                    if not isinstance(report, dict):
                        report = {}
                    qs = report.get("quality_stats", {})
                    if not isinstance(qs, dict):
                        qs = {}
                    qs["story_cluster_count"] = card_result.story_cluster_count
                    report["quality_stats"] = qs
                    await self.db.execute(
                        sa_update(DiscoveryRun)
                        .where(DiscoveryRun.id == _run_id)
                        .values(summary_report=report)
                    )
                    await self.db.flush()
                except Exception as e:
                    logger.warning(f"Failed to persist story_cluster_count: {e}")

            # Step 7: Finalize run
            # Recompute diversity metrics to include query sources
            if sources_by_category:
                diversity_metrics = SourceDiversityMetrics.compute(sources_by_category)

            # Calculate total processing time
            processing_time.total_seconds = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds()

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
                api_token_usage_metrics=api_token_usage,
            )

        except Exception as e:
            logger.error(f"Discovery run failed: {e}", exc_info=True)
            errors.append(str(e))
            processing_time.total_seconds = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds()

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
                api_token_usage_metrics=api_token_usage,
            )

    # ========================================================================
    # Progress Tracking
    # ========================================================================

    async def _update_progress(
        self,
        run_id: str,
        stage: str,
        message: str,
        stages_status: Dict[str, str],
        stats: Optional[Dict[str, int]] = None,
    ) -> None:
        """
        Update progress in the discovery_runs record.

        Args:
            run_id: Discovery run ID
            stage: Current stage name
            message: Human-readable progress message
            stages_status: Dict of stage_name -> status (pending/in_progress/completed)
            stats: Optional dict of current statistics
        """
        try:
            # Build progress object
            progress = {
                "current_stage": stage,
                "message": message,
                "stages": stages_status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            if stats:
                progress["stats"] = stats

            # Read current summary_report
            _run_id = uuid.UUID(run_id) if isinstance(run_id, str) else run_id
            result_dr = await self.db.execute(
                select(DiscoveryRun).where(DiscoveryRun.id == _run_id)
            )
            dr_row = result_dr.scalar_one_or_none()
            current_report = (
                dr_row.summary_report if dr_row and dr_row.summary_report else {}
            ) or {}

            # Merge progress into summary_report
            updated_report = {**current_report, "progress": progress}

            # Update the record
            await self.db.execute(
                sa_update(DiscoveryRun)
                .where(DiscoveryRun.id == _run_id)
                .values(summary_report=updated_report)
            )
            await self.db.flush()

            logger.debug(f"Progress update: {stage} - {message}")
        except Exception as e:
            # Don't fail on progress update errors
            logger.warning(f"Could not update progress: {e}")

    async def _update_progress_simple(
        self,
        run_id: str,
        stage: str,
        message: str,
        completed_stages: List[str],
        stats: Optional[Dict[str, int]] = None,
    ) -> None:
        """
        Simplified progress update that builds stages_status automatically.
        """
        all_stages = ["queries", "search", "triage", "blocked", "dedupe", "cards"]
        stages_status = {}

        for s in all_stages:
            if s in completed_stages:
                stages_status[s] = "completed"
            elif s == stage:
                stages_status[s] = "in_progress"
            else:
                stages_status[s] = "pending"

        await self._update_progress(run_id, stage, message, stages_status, stats)

    # ========================================================================
    # Source Persistence (saves all discovery data)
    # ========================================================================

    async def _persist_discovered_source(
        self, run_id: str, source: "RawSource", query: Optional["QueryConfig"] = None
    ) -> Optional[str]:
        """
        Persist a discovered source immediately when found.
        Returns the discovered_source ID for later updates.
        """
        try:
            from urllib.parse import urlparse

            domain = urlparse(source.url).netloc if source.url else None

            # Look up domain reputation ID (Task 2.7)
            _domain_rep_id = None
            try:
                if _rep := await domain_reputation_service.get_reputation(
                    self.db, source.url or ""
                ):
                    _domain_rep_id = _rep.get("id")
            except Exception:
                pass  # Non-fatal

            obj = DiscoveredSource(
                discovery_run_id=(
                    uuid.UUID(run_id) if isinstance(run_id, str) else run_id
                ),
                url=source.url,
                title=source.title,
                content_snippet=(source.content or "")[:2000],
                full_content=source.content,
                published_at=source.published_at,
                source_type=source.source_type,
                domain=domain,
                search_query=query.query_text if query else None,
                query_pillar=query.pillar_code if query else None,
                query_priority=query.priority_id if query else None,
                processing_status="discovered",
            )

            # Note: domain_reputation_id is not on DiscoveredSource model;
            # it will be set on the Source record when the source is stored to a card.

            self.db.add(obj)
            await self.db.flush()
            await self.db.refresh(obj)
            return str(obj.id)
        except Exception as e:
            logger.warning(f"Could not persist discovered source: {e}")
        return None

    async def _update_source_triage(
        self, source_id: str, triage: "TriageResult", passed: bool
    ) -> None:
        """Update source with triage results."""
        try:
            _sid = uuid.UUID(source_id) if isinstance(source_id, str) else source_id
            await self.db.execute(
                sa_update(DiscoveredSource)
                .where(DiscoveredSource.id == _sid)
                .values(
                    triage_is_relevant=triage.is_relevant,
                    triage_confidence=triage.confidence,
                    triage_primary_pillar=triage.primary_pillar,
                    triage_reason=triage.reason,
                    triaged_at=datetime.now(timezone.utc),
                    processing_status="triaged" if passed else "filtered_triage",
                )
            )
            await self.db.flush()
        except Exception as e:
            logger.warning(f"Could not update source triage: {e}")

    async def _update_source_analysis(
        self, source_id: str, analysis: "AnalysisResult"
    ) -> None:
        """Update source with full analysis results."""
        try:
            entities_json = [
                {"name": e.name, "type": e.entity_type, "context": e.context}
                for e in (analysis.entities or [])
            ]

            _sid = uuid.UUID(source_id) if isinstance(source_id, str) else source_id
            await self.db.execute(
                sa_update(DiscoveredSource)
                .where(DiscoveredSource.id == _sid)
                .values(
                    analysis_summary=analysis.summary,
                    analysis_key_excerpts=analysis.key_excerpts,
                    analysis_pillars=analysis.pillars,
                    analysis_goals=analysis.goals,
                    analysis_steep_categories=analysis.steep_categories,
                    analysis_anchors=analysis.anchors,
                    analysis_horizon=analysis.horizon,
                    analysis_suggested_stage=analysis.suggested_stage,
                    analysis_triage_score=analysis.triage_score,
                    analysis_credibility=analysis.credibility,
                    analysis_novelty=analysis.novelty,
                    analysis_likelihood=analysis.likelihood,
                    analysis_impact=analysis.impact,
                    analysis_relevance=analysis.relevance,
                    analysis_time_to_awareness_months=analysis.time_to_awareness_months,
                    analysis_time_to_prepare_months=analysis.time_to_prepare_months,
                    analysis_suggested_card_name=analysis.suggested_card_name,
                    analysis_is_new_concept=analysis.is_new_concept,
                    analysis_reasoning=analysis.reasoning,
                    analysis_entities=entities_json,
                    analyzed_at=datetime.now(timezone.utc),
                    processing_status="analyzed",
                )
            )
            await self.db.flush()
        except Exception as e:
            logger.warning(f"Could not update source analysis: {e}")

    async def _update_source_dedup(
        self,
        source_id: str,
        status: str,  # 'unique', 'duplicate', 'enrichment_candidate'
        matched_card_id: Optional[str] = None,
        similarity: Optional[float] = None,
    ) -> None:
        """Update source with deduplication results."""
        try:
            processing_status = {
                "unique": "deduplicated",
                "duplicate": "filtered_duplicate",
                "enrichment_candidate": "deduplicated",
            }.get(status, "deduplicated")

            _sid = uuid.UUID(source_id) if isinstance(source_id, str) else source_id
            _matched_card = (
                uuid.UUID(matched_card_id)
                if matched_card_id and isinstance(matched_card_id, str)
                else matched_card_id
            )
            await self.db.execute(
                sa_update(DiscoveredSource)
                .where(DiscoveredSource.id == _sid)
                .values(
                    dedup_status=status,
                    dedup_matched_card_id=_matched_card,
                    dedup_similarity_score=similarity,
                    deduplicated_at=datetime.now(timezone.utc),
                    processing_status=processing_status,
                )
            )
            await self.db.flush()
        except Exception as e:
            logger.warning(f"Could not update source dedup: {e}")

    async def _update_source_outcome(
        self,
        source_id: str,
        status: str,  # 'card_created', 'card_enriched', 'filtered_blocked', 'error'
        card_id: Optional[str] = None,
        source_record_id: Optional[str] = None,
        error_message: Optional[str] = None,
        error_stage: Optional[str] = None,
    ) -> None:
        """Update source with final outcome."""
        try:
            _sid = uuid.UUID(source_id) if isinstance(source_id, str) else source_id
            values: Dict[str, Any] = {
                "processing_status": status,
                "resulting_card_id": (
                    uuid.UUID(card_id)
                    if card_id and isinstance(card_id, str)
                    else card_id
                ),
                "resulting_source_id": (
                    uuid.UUID(source_record_id)
                    if source_record_id and isinstance(source_record_id, str)
                    else source_record_id
                ),
            }
            if error_message:
                values["error_message"] = error_message
                values["error_stage"] = error_stage

            await self.db.execute(
                sa_update(DiscoveredSource)
                .where(DiscoveredSource.id == _sid)
                .values(**values)
            )
            await self.db.flush()
        except Exception as e:
            logger.warning(f"Could not update source outcome: {e}")

    async def _python_vector_search(
        self,
        query_embedding: List[float],
        config: DiscoveryConfig,
        suggested_name: str,
        source: ProcessedSource,
        enrichment_candidates: List[Tuple[ProcessedSource, str, float]],
        new_concept_candidates: List[ProcessedSource],
    ) -> str:
        """
        Python-based fallback for vector similarity search when RPC fails.

        This fetches cards with embeddings from the database and calculates
        cosine similarity in Python. Less efficient than DB-side computation
        but works around schema/extension issues.

        Args:
            query_embedding: The source embedding to compare
            config: Discovery configuration with thresholds
            suggested_name: Suggested card name for logging
            source: The source being processed
            enrichment_candidates: List to append enrichment candidates
            new_concept_candidates: List to append new concepts

        Returns:
            "enriched" if matched to existing card, "new" if new concept
        """
        # Fetch cards with embeddings (non-rejected only)
        result_cards = await self.db.execute(
            select(Card)
            .where(Card.review_status != "rejected")
            .where(Card.embedding.isnot(None))
            .limit(100)
        )
        cards_with_emb = result_cards.scalars().all()

        if not cards_with_emb:
            logger.info("PYTHON FALLBACK: No cards with embeddings found - NEW CONCEPT")
            new_concept_candidates.append(source)
            if source.discovered_source_id:
                await self._update_source_dedup(source.discovered_source_id, "unique")
            return "new"

        # Calculate similarities using Python
        best_match = None
        best_similarity = 0.0

        for card in cards_with_emb:
            card_embedding = card.embedding
            if not card_embedding:
                continue

            similarity = cosine_similarity(query_embedding, card_embedding)

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = card

        if best_match and best_similarity >= config.similarity_threshold:
            # Strong match - enrich existing card
            logger.info(
                f"PYTHON FALLBACK MATCH (strong): '{suggested_name}' -> '{best_match.name}' "
                f"(similarity: {best_similarity:.3f}) - ENRICHING"
            )
            enrichment_candidates.append((source, str(best_match.id), best_similarity))
            if source.discovered_source_id:
                await self._update_source_dedup(
                    source.discovered_source_id,
                    "enrichment_candidate",
                    str(best_match.id),
                    best_similarity,
                )
            return "enriched"

        elif best_match and best_similarity >= config.weak_match_threshold:
            # Weak match - use LLM to decide
            decision = await self.ai_service.check_card_match(
                source_summary=source.analysis.summary,
                source_card_name=source.analysis.suggested_card_name,
                existing_card_name=best_match.name,
                existing_card_summary=best_match.summary or "",
            )

            if decision.get("is_match") and decision.get("confidence", 0) >= 0.6:
                logger.info(
                    f"PYTHON FALLBACK + LLM MATCH: '{suggested_name}' -> '{best_match.name}' "
                    f"(similarity: {best_similarity:.3f}, llm_conf: {decision.get('confidence', 0):.2f}) - ENRICHING"
                )
                enrichment_candidates.append(
                    (source, str(best_match.id), best_similarity)
                )
                if source.discovered_source_id:
                    await self._update_source_dedup(
                        source.discovered_source_id,
                        "enrichment_candidate",
                        str(best_match.id),
                        best_similarity,
                    )
                return "enriched"
            else:
                logger.info(
                    f"PYTHON FALLBACK + LLM NO MATCH: '{suggested_name}' vs '{best_match.name}' "
                    f"(reason: {decision.get('reasoning', 'unknown')[:80]}) - NEW CONCEPT"
                )
                new_concept_candidates.append(source)
                if source.discovered_source_id:
                    await self._update_source_dedup(
                        source.discovered_source_id, "unique"
                    )
                return "new"

        else:
            logger.info(
                f"PYTHON FALLBACK NO MATCH: '{suggested_name}' - best similarity {best_similarity:.3f} "
                f"below threshold {config.weak_match_threshold} - NEW CONCEPT"
            )
            new_concept_candidates.append(source)
            if source.discovered_source_id:
                await self._update_source_dedup(source.discovered_source_id, "unique")
            return "new"

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
            obj = DiscoveryRun(
                id=uuid.UUID(run_id),
                status=DiscoveryStatus.RUNNING.value,
                triggered_by="manual",
                pillars_scanned=config.pillars_filter or [],
                priorities_scanned=config.horizons_filter or [],
                started_at=datetime.now(timezone.utc),
                summary_report={
                    "config": {
                        "max_queries_per_run": config.max_queries_per_run,
                        "max_sources_per_query": config.max_sources_per_query,
                        "max_sources_total": config.max_sources_total,
                        "auto_approve_threshold": config.auto_approve_threshold,
                        "similarity_threshold": config.similarity_threshold,
                        "dry_run": config.dry_run,
                    }
                },
            )
            self.db.add(obj)
            await self.db.flush()
        except Exception as e:
            # Log but don't fail - table might not exist yet
            logger.warning(f"Could not create run record (table may not exist): {e}")

        return run_id

    # ========================================================================
    # Step 2: Generate Queries
    # ========================================================================

    async def _generate_queries(self, config: DiscoveryConfig) -> List[QueryConfig]:
        """
        Generate search queries based on configuration.

        Args:
            config: Run configuration

        Returns:
            List of QueryConfig objects
        """
        return self.query_generator.generate_queries(
            pillars_filter=config.pillars_filter or None,
            horizons=config.horizons_filter or None,
            include_priorities=config.include_priorities,
            max_queries=config.max_queries_per_run,
        )

    # ========================================================================
    # Step 3: Execute Searches
    # ========================================================================

    async def _execute_searches(
        self, queries: List[QueryConfig], config: DiscoveryConfig
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
            batch = queries[i : i + batch_size]

            # Execute batch concurrently
            tasks = [self._execute_single_search(query, config) for query in batch]

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

        return all_sources[: config.max_sources_total], total_cost

    async def _execute_single_search(
        self, query: QueryConfig, config: DiscoveryConfig
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
            # Use the research service's discovery method with timeout
            # GPT Researcher can hang if Firecrawl is down/out of credits
            sources, _report, cost = await asyncio.wait_for(
                self.research_service._discover_sources(
                    query=query.query_text, report_type="research_report"
                ),
                timeout=120,  # 2 minute timeout per query
            )

            # Limit sources per query
            sources = sources[: config.max_sources_per_query]

            # Add query context to sources for tracking
            for source in sources:
                # Store query context in source for later use
                source.pillar_code = query.pillar_code  # type: ignore
                source.priority_id = query.priority_id  # type: ignore
                source.horizon_target = query.horizon_target  # type: ignore

            return sources, cost

        except asyncio.TimeoutError:
            logger.warning(
                f"Search timed out for query '{query.query_text[:50]}...' (120s)"
            )
            return [], 0.0
        except Exception as e:
            logger.warning(f"Search failed for query '{query.query_text[:50]}...': {e}")
            return [], 0.0

    # ========================================================================
    # Step 3b: Multi-Source Content Fetching (7 Categories)
    # ========================================================================

    async def _fetch_from_all_source_categories(
        self, config: DiscoveryConfig
    ) -> MultiSourceFetchResult:
        """
        Fetch content from all 7 source categories concurrently.

        Categories:
        1. RSS/Atom feeds - Curated feeds from various sources
        2. News outlets - Major news sites (Reuters, AP News, GCN)
        3. Academic publications - arXiv research papers
        4. Government sources - .gov domains, policy documents
        5. Tech blogs - TechCrunch, Ars Technica, company blogs
        6. Grants.gov - Federal grant opportunities
        7. SAM.gov - Federal procurement and grant opportunities

        Args:
            config: Discovery configuration with source category settings

        Returns:
            MultiSourceFetchResult with sources from all categories
        """
        start_time = datetime.now(timezone.utc)
        all_sources: List[RawSource] = []
        sources_by_category: Dict[str, int] = {cat.value: 0 for cat in SourceCategory}
        errors_by_category: Dict[str, List[str]] = {
            cat.value: [] for cat in SourceCategory
        }
        seen_urls: set = set()

        topics = config.search_topics or DEFAULT_SEARCH_TOPICS

        num_categories = len(SourceCategory)
        logger.info(
            f"Starting multi-source fetch from {num_categories} categories "
            f"with topics: {topics[:3]}..."
        )

        # Create tasks for each source category
        tasks = []

        # 1. RSS/Atom feeds
        rss_config = config.source_categories.get(
            SourceCategory.RSS.value, SourceCategoryConfig()
        )
        if rss_config.enabled:
            feeds = rss_config.rss_feeds or DEFAULT_RSS_FEEDS
            tasks.append(self._fetch_rss_sources(feeds, rss_config.max_sources))

        # 2. News outlets
        news_config = config.source_categories.get(
            SourceCategory.NEWS.value, SourceCategoryConfig()
        )
        if news_config.enabled:
            tasks.append(self._fetch_news_sources(topics, news_config.max_sources))

        # 3. Academic publications
        academic_config = config.source_categories.get(
            SourceCategory.ACADEMIC.value, SourceCategoryConfig()
        )
        if academic_config.enabled:
            tasks.append(
                self._fetch_academic_sources(topics, academic_config.max_sources)
            )

        # 4. Government sources
        gov_config = config.source_categories.get(
            SourceCategory.GOVERNMENT.value, SourceCategoryConfig()
        )
        if gov_config.enabled:
            tasks.append(self._fetch_government_sources(topics, gov_config.max_sources))

        # 5. Tech blogs
        tech_config = config.source_categories.get(
            SourceCategory.TECH_BLOG.value, SourceCategoryConfig()
        )
        if tech_config.enabled:
            tasks.append(self._fetch_tech_blog_sources(topics, tech_config.max_sources))

        # 6. Grants.gov
        grants_gov_config = config.source_categories.get(
            SourceCategory.GRANTS_GOV.value, SourceCategoryConfig()
        )
        if grants_gov_config.enabled:
            tasks.append(
                self._fetch_grants_gov_sources(topics, grants_gov_config.max_sources)
            )

        # 7. SAM.gov
        sam_gov_config = config.source_categories.get(
            SourceCategory.SAM_GOV.value, SourceCategoryConfig()
        )
        if sam_gov_config.enabled:
            tasks.append(
                self._fetch_sam_gov_sources(topics, sam_gov_config.max_sources)
            )

        # Execute all fetches concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        category_order = [
            SourceCategory.RSS.value,
            SourceCategory.NEWS.value,
            SourceCategory.ACADEMIC.value,
            SourceCategory.GOVERNMENT.value,
            SourceCategory.TECH_BLOG.value,
            SourceCategory.GRANTS_GOV.value,
            SourceCategory.SAM_GOV.value,
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
        fetch_time = (datetime.now(timezone.utc) - start_time).total_seconds()
        categories_fetched = sum(
            bool(count > 0) for count in sources_by_category.values()
        )

        logger.info(
            f"Multi-source fetch complete: {len(all_sources)} sources from "
            f"{categories_fetched}/{num_categories} categories in {fetch_time:.1f}s"
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
            diversity_metrics=diversity_metrics,
        )

    async def _fetch_rss_sources(
        self, feed_urls: List[str], max_sources: int
    ) -> Tuple[List[RawSource], str]:
        """Fetch sources from RSS/Atom feeds."""
        try:
            articles = await fetch_rss_sources(
                feed_urls=feed_urls,
                max_articles_per_feed=(
                    max_sources // len(feed_urls) if feed_urls else 10
                ),
            )

            sources = []
            for article in articles[:max_sources]:
                source = RawSource(
                    url=article.url,
                    title=article.title,
                    content=article.content,
                    source_name=article.source_name,
                    relevance=article.relevance,
                )
                sources.append(source)

            return sources, SourceCategory.RSS.value

        except Exception as e:
            logger.warning(f"RSS fetch failed: {e}")
            return [], SourceCategory.RSS.value

    async def _fetch_news_sources(
        self, topics: List[str], max_sources: int
    ) -> Tuple[List[RawSource], str]:
        """Fetch sources from news outlets."""
        try:
            articles = await fetch_news_articles(
                topics=topics[:3],  # Limit topics to avoid rate limiting
                max_articles=max_sources,
            )

            sources = []
            for article in articles[:max_sources]:
                source = RawSource(
                    url=article.url,
                    title=article.title,
                    content=article.content,
                    source_name=article.source_name,
                    relevance=article.relevance,
                )
                sources.append(source)

            return sources, SourceCategory.NEWS.value

        except Exception as e:
            logger.warning(f"News fetch failed: {e}")
            return [], SourceCategory.NEWS.value

    async def _fetch_academic_sources(
        self, topics: List[str], max_sources: int
    ) -> Tuple[List[RawSource], str]:
        """Fetch sources from academic publications (arXiv)."""
        try:
            # Combine topics into search query
            query = " OR ".join([f'"{topic}"' for topic in topics[:3]])

            result = await fetch_academic_papers(query=query, max_results=max_sources)

            sources = []
            for paper in result.papers[:max_sources]:
                raw_source_dict = convert_academic_to_raw(paper)
                source = RawSource(
                    url=raw_source_dict["url"],
                    title=raw_source_dict["title"],
                    content=raw_source_dict["content"],
                    source_name=raw_source_dict["source_name"],
                    relevance=raw_source_dict.get("relevance", 0.8),
                )
                sources.append(source)

            return sources, SourceCategory.ACADEMIC.value

        except Exception as e:
            logger.warning(f"Academic fetch failed: {e}")
            return [], SourceCategory.ACADEMIC.value

    async def _fetch_government_sources(
        self, topics: List[str], max_sources: int
    ) -> Tuple[List[RawSource], str]:
        """Fetch sources from government websites (.gov domains)."""
        try:
            documents = await fetch_government_sources(
                topics=topics[:3], max_results=max_sources  # Limit topics
            )

            sources = []
            for doc in documents[:max_sources]:
                raw_source_dict = convert_government_to_raw_source(doc)
                source = RawSource(
                    url=raw_source_dict["url"],
                    title=raw_source_dict["title"],
                    content=raw_source_dict["content"],
                    source_name=raw_source_dict["source_name"],
                    relevance=raw_source_dict.get("relevance", 0.75),
                )
                sources.append(source)

            return sources, SourceCategory.GOVERNMENT.value

        except Exception as e:
            logger.warning(f"Government fetch failed: {e}")
            return [], SourceCategory.GOVERNMENT.value

    async def _fetch_tech_blog_sources(
        self, topics: List[str], max_sources: int
    ) -> Tuple[List[RawSource], str]:
        """Fetch sources from tech blogs."""
        try:
            articles = await fetch_tech_blog_articles(
                topics=topics[:3], max_articles=max_sources  # Limit topics
            )

            sources = []
            for article in articles[:max_sources]:
                source = RawSource(
                    url=article.url,
                    title=article.title,
                    content=article.content,
                    source_name=article.source_name,
                    relevance=article.relevance,
                )
                sources.append(source)

            return sources, SourceCategory.TECH_BLOG.value

        except Exception as e:
            logger.warning(f"Tech blog fetch failed: {e}")
            return [], SourceCategory.TECH_BLOG.value

    async def _fetch_grants_gov_sources(
        self, topics: List[str], max_sources: int
    ) -> Tuple[List[RawSource], str]:
        """Fetch grant opportunities from Grants.gov API."""
        try:
            from app.source_fetchers.grants_gov_fetcher import (
                fetch_and_convert_opportunities,
            )

            sources, category = await fetch_and_convert_opportunities(
                topics=topics, max_results=max_sources
            )
            logger.info(f"Grants.gov: fetched {len(sources)} opportunities")
            return sources, SourceCategory.GRANTS_GOV.value

        except Exception as e:
            logger.warning(f"Grants.gov fetch failed: {e}")
            return [], SourceCategory.GRANTS_GOV.value

    async def _fetch_sam_gov_sources(
        self, topics: List[str], max_sources: int
    ) -> Tuple[List[RawSource], str]:
        """Fetch opportunities from SAM.gov API."""
        try:
            from app.source_fetchers.sam_gov_fetcher import (
                fetch_and_convert_opportunities,
            )

            sources, category = await fetch_and_convert_opportunities(
                topics=topics, max_results=max_sources
            )
            logger.info(f"SAM.gov: fetched {len(sources)} opportunities")
            return sources, SourceCategory.SAM_GOV.value

        except Exception as e:
            logger.warning(f"SAM.gov fetch failed: {e}")
            return [], SourceCategory.SAM_GOV.value

    # ========================================================================
    # Step 4: Triage Sources
    # ========================================================================

    async def _triage_sources(self, sources: List[RawSource]) -> List[ProcessedSource]:
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
                        primary_pillar=getattr(source, "pillar_code", None),
                        reason="Auto-passed (no content)",
                    )
                else:
                    triage = await self.ai_service.triage_source(
                        title=source.title, content=source.content
                    )

                # Pre-print relevance penalty (Task 2.6): soft penalty, not a hard block
                if getattr(source, "is_preprint", False) and triage.confidence > 0:
                    original_confidence = triage.confidence
                    triage.confidence = max(0.0, triage.confidence - 0.2)
                    logger.debug(
                        f"Pre-print penalty applied: {source.url} "
                        f"confidence {original_confidence:.2f} -> {triage.confidence:.2f}"
                    )

                # Domain reputation confidence adjustment (Task 2.7)
                try:
                    reputation = await domain_reputation_service.get_reputation(
                        self.db, source.url or ""
                    )
                    adj = domain_reputation_service.get_confidence_adjustment(
                        reputation
                    )
                    if adj != 0.0:
                        pre_adj_confidence = triage.confidence
                        triage.confidence = max(0.0, min(1.0, triage.confidence + adj))
                        logger.debug(
                            f"Domain reputation adjustment: {source.url} "
                            f"adj={adj:+.2f} confidence "
                            f"{pre_adj_confidence:.2f} -> {triage.confidence:.2f}"
                        )
                except Exception as e:
                    logger.debug(f"Domain reputation lookup failed (non-fatal): {e}")

                # Determine triage pass/fail
                passed_triage = (
                    triage.is_relevant and triage.confidence >= triage_threshold
                )

                # Record triage result for domain reputation stats (Task 2.7)
                try:
                    from urllib.parse import urlparse as _urlparse

                    if _domain := _urlparse(source.url or "").netloc:
                        await domain_reputation_service.record_triage_result(
                            self.db, _domain, passed=passed_triage
                        )
                except Exception as e:
                    logger.debug(f"Domain triage recording failed (non-fatal): {e}")

                if passed_triage:
                    # Update discovered_sources with triage passed
                    if source.discovered_source_id:
                        await self._update_source_triage(
                            source.discovered_source_id, triage, True
                        )

                    # Full analysis
                    analysis = await self.ai_service.analyze_source(
                        title=source.title,
                        content=source.content or "",
                        source_name=source.source_name,
                        published_at=datetime.now(timezone.utc).isoformat(),
                    )

                    # Update discovered_sources with analysis
                    if source.discovered_source_id:
                        await self._update_source_analysis(
                            source.discovered_source_id, analysis
                        )

                    # Generate embedding
                    embed_text = f"{source.title} {analysis.summary}"
                    embedding = await self.ai_service.generate_embedding(embed_text)

                    processed_source = ProcessedSource(
                        raw=source,
                        triage=triage,
                        analysis=analysis,
                        embedding=embedding,
                        discovered_source_id=source.discovered_source_id,
                    )
                    processed.append(processed_source)
                else:
                    # Update discovered_sources with triage failed
                    if source.discovered_source_id:
                        await self._update_source_triage(
                            source.discovered_source_id, triage, False
                        )

            except Exception as e:
                logger.warning(f"Triage/analysis failed for {source.url}: {e}")
                # Mark error in discovered_sources
                if source.discovered_source_id:
                    await self._update_source_outcome(
                        source.discovered_source_id,
                        "error",
                        error_message=str(e),
                        error_stage="triage",
                    )
                continue

        return processed

    async def _triage_sources_with_metrics(
        self, sources: List[RawSource]
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

        # Domain reputation stats tracking (Task 2.7)
        domain_rep_stats = {
            "domain_reputation_lookups": 0,
            "confidence_adjustments": 0,
            "tier1_source_count": 0,
            "tier2_source_count": 0,
            "tier3_source_count": 0,
            "untiered_source_count": 0,
        }

        for source in sources:
            try:
                # Skip sources without content for full triage
                if not source.content:
                    # Auto-pass URL-only sources with lower confidence
                    triage = TriageResult(
                        is_relevant=True,
                        confidence=0.65,
                        primary_pillar=getattr(source, "pillar_code", None),
                        reason="Auto-passed (no content)",
                    )
                else:
                    triage = await self.ai_service.triage_source(
                        title=source.title, content=source.content
                    )
                    # Estimate tokens: ~4 chars per token for input, fixed output
                    input_tokens = (
                        len(source.title or "") // 4 + len(source.content or "") // 4
                    )
                    output_tokens = 100  # Estimated output tokens for triage
                    total_tokens += input_tokens + output_tokens

                # Pre-print relevance penalty (Task 2.6): soft penalty, not a hard block
                if getattr(source, "is_preprint", False) and triage.confidence > 0:
                    original_confidence = triage.confidence
                    triage.confidence = max(0.0, triage.confidence - 0.2)
                    logger.debug(
                        f"Pre-print penalty applied: {source.url} "
                        f"confidence {original_confidence:.2f} -> {triage.confidence:.2f}"
                    )

                # Domain reputation confidence adjustment (Task 2.7)
                try:
                    reputation = await domain_reputation_service.get_reputation(
                        self.db, source.url or ""
                    )
                    domain_rep_stats["domain_reputation_lookups"] += 1

                    # Track tier distribution
                    if reputation:
                        tier = reputation.get("curated_tier")
                        if tier == 1:
                            domain_rep_stats["tier1_source_count"] += 1
                        elif tier == 2:
                            domain_rep_stats["tier2_source_count"] += 1
                        elif tier == 3:
                            domain_rep_stats["tier3_source_count"] += 1
                        else:
                            domain_rep_stats["untiered_source_count"] += 1
                    else:
                        domain_rep_stats["untiered_source_count"] += 1

                    adj = domain_reputation_service.get_confidence_adjustment(
                        reputation
                    )
                    if adj != 0.0:
                        pre_adj_confidence = triage.confidence
                        triage.confidence = max(0.0, min(1.0, triage.confidence + adj))
                        domain_rep_stats["confidence_adjustments"] += 1
                        logger.debug(
                            f"Domain reputation adjustment: {source.url} "
                            f"adj={adj:+.2f} confidence "
                            f"{pre_adj_confidence:.2f} -> {triage.confidence:.2f}"
                        )
                except Exception as e:
                    logger.debug(f"Domain reputation lookup failed (non-fatal): {e}")

                # Determine triage pass/fail
                passed_triage = (
                    triage.is_relevant and triage.confidence >= triage_threshold
                )

                # Record triage result for domain reputation stats (Task 2.7)
                try:
                    from urllib.parse import urlparse as _urlparse

                    if _domain := _urlparse(source.url or "").netloc:
                        await domain_reputation_service.record_triage_result(
                            self.db, _domain, passed=passed_triage
                        )
                except Exception as e:
                    logger.debug(f"Domain triage recording failed (non-fatal): {e}")

                if passed_triage:
                    # Full analysis
                    analysis = await self.ai_service.analyze_source(
                        title=source.title,
                        content=source.content or "",
                        source_name=source.source_name,
                        published_at=datetime.now(timezone.utc).isoformat(),
                    )
                    # Estimate tokens for analysis
                    input_tokens = (
                        len(source.title or "") // 4 + len(source.content or "") // 4
                    )
                    output_tokens = 500  # Estimated output tokens for analysis
                    total_tokens += input_tokens + output_tokens

                    # Generate embedding
                    embed_text = f"{source.title} {analysis.summary}"
                    embedding = await self.ai_service.generate_embedding(embed_text)
                    # Estimate tokens for embedding
                    total_tokens += len(embed_text) // 4

                    processed.append(
                        ProcessedSource(
                            raw=source,
                            triage=triage,
                            analysis=analysis,
                            embedding=embedding,
                        )
                    )

            except Exception as e:
                logger.warning(f"Triage/analysis failed for {source.url}: {e}")
                continue

        # Log domain reputation stats (Task 2.7)
        if domain_rep_stats["domain_reputation_lookups"] > 0:
            logger.info(
                f"Domain reputation triage stats: "
                f"{domain_rep_stats['domain_reputation_lookups']} lookups, "
                f"{domain_rep_stats['confidence_adjustments']} adjustments, "
                f"tier1={domain_rep_stats['tier1_source_count']}, "
                f"tier2={domain_rep_stats['tier2_source_count']}, "
                f"tier3={domain_rep_stats['tier3_source_count']}, "
                f"untiered={domain_rep_stats['untiered_source_count']}"
            )

        # Persist domain reputation stats to quality_stats (Task 2.7)
        try:
            # We need to get run_id from the caller context; use the _current_run_id if available
            if hasattr(self, "_current_run_id") and self._current_run_id:
                _run_id = (
                    uuid.UUID(self._current_run_id)
                    if isinstance(self._current_run_id, str)
                    else self._current_run_id
                )
                result_dr = await self.db.execute(
                    select(DiscoveryRun).where(DiscoveryRun.id == _run_id)
                )
                dr_row = result_dr.scalar_one_or_none()
                report = (
                    dr_row.summary_report if dr_row and dr_row.summary_report else {}
                ) or {}
                if not isinstance(report, dict):
                    report = {}
                qs = report.get("quality_stats", {})
                qs.update(domain_rep_stats)
                report["quality_stats"] = qs
                await self.db.execute(
                    sa_update(DiscoveryRun)
                    .where(DiscoveryRun.id == _run_id)
                    .values(summary_report=report)
                )
                await self.db.flush()
        except Exception as e:
            logger.debug(f"Failed to persist domain reputation stats: {e}")

        return processed, total_tokens

    # ========================================================================
    # Step 5: Check Blocked Topics
    # ========================================================================

    async def _check_blocked_topics(
        self, sources: List[ProcessedSource]
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
            result_blocks = await self.db.execute(
                select(DiscoveryBlock).where(DiscoveryBlock.is_active == True)
            )
            blocks = result_blocks.scalars().all()

            if not blocks:
                return sources, 0

            blocked_keywords = set()
            for block in blocks:
                keywords = block.keywords or []
                if isinstance(keywords, list):
                    blocked_keywords.update(kw.lower() for kw in keywords)
                if topic := (block.topic_name or ""):
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
                    # Update discovered_sources with blocked status
                    if source.discovered_source_id:
                        await self._update_source_outcome(
                            source.discovered_source_id, "filtered_blocked"
                        )
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
        self, sources: List[ProcessedSource], config: DiscoveryConfig
    ) -> DeduplicationResult:
        """
        Deduplicate sources against existing cards using multi-tier matching:
        1. Exact URL match
        2. Name similarity match
        3. Vector similarity match
        4. LLM decision for weak matches

        PHILOSOPHY: Prefer enrichment over creation. When in doubt, add to existing card.

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

        # Pre-fetch existing card names for name-based matching
        try:
            result_cards = await self.db.execute(
                select(Card).where(Card.review_status != "rejected")
            )
            existing_card_objs = result_cards.scalars().all()
            card_name_map = {
                str(c.id): {"id": str(c.id), "name": c.name, "summary": c.summary}
                for c in existing_card_objs
            }
            logger.info(f"Loaded {len(card_name_map)} existing cards for deduplication")
        except Exception as e:
            logger.warning(f"Could not load existing cards for name matching: {e}")
            card_name_map = {}

        for source in sources:
            try:
                suggested_name = (
                    source.analysis.suggested_card_name if source.analysis else ""
                )
                logger.debug(
                    f"Deduplicating: '{suggested_name}' from {source.raw.url[:50]}..."
                )

                # STEP 1: Check for existing URL first
                url_result = await self.db.execute(
                    select(Source.id).where(Source.url == source.raw.url)
                )
                url_existing = url_result.scalars().first()

                if url_existing:
                    duplicate_count += 1
                    logger.info(f"URL duplicate found: {source.raw.url[:60]}")
                    if source.discovered_source_id:
                        await self._update_source_dedup(
                            source.discovered_source_id, "duplicate"
                        )
                    continue

                # STEP 2: Name-based matching (fast, no AI call needed)
                name_match_found = False
                if suggested_name and card_name_map:
                    for card_id, card_data in card_name_map.items():
                        name_sim = calculate_name_similarity(
                            suggested_name, card_data["name"]
                        )
                        if name_sim >= config.name_similarity_threshold:
                            logger.info(
                                f"NAME MATCH: '{suggested_name}' -> '{card_data['name']}' "
                                f"(similarity: {name_sim:.2f}) - ENRICHING"
                            )
                            enrichment_candidates.append((source, card_id, name_sim))
                            if source.discovered_source_id:
                                await self._update_source_dedup(
                                    source.discovered_source_id,
                                    "enrichment_candidate",
                                    card_id,
                                    name_sim,
                                )
                            name_match_found = True
                            break

                if name_match_found:
                    unique_sources.append(source)
                    continue

                # STEP 3: Vector similarity search against existing cards
                try:
                    match_data = await vector_search_cards(
                        self.db,
                        query_embedding=source.embedding,
                        match_threshold=config.weak_match_threshold,
                        match_count=5,
                    )

                    if match_data:
                        top_match = match_data[0]
                        similarity = top_match.get("similarity", 0)

                        if similarity >= config.similarity_threshold:
                            # Strong vector match - enrich existing card
                            logger.info(
                                f"VECTOR MATCH (strong): '{suggested_name}' -> '{top_match.get('name', 'unknown')}' "
                                f"(similarity: {similarity:.3f}) - ENRICHING"
                            )
                            enrichment_candidates.append(
                                (source, top_match["id"], similarity)
                            )
                            if source.discovered_source_id:
                                await self._update_source_dedup(
                                    source.discovered_source_id,
                                    "enrichment_candidate",
                                    top_match["id"],
                                    similarity,
                                )
                        elif similarity >= config.weak_match_threshold:
                            # Weak match - use LLM to decide (biased toward enrichment)
                            card_result_q = await self.db.execute(
                                select(Card).where(
                                    Card.id == uuid.UUID(top_match["id"])
                                )
                            )
                            card_obj = card_result_q.scalar_one_or_none()

                            if card_obj:
                                decision = await self.ai_service.check_card_match(
                                    source_summary=source.analysis.summary,
                                    source_card_name=source.analysis.suggested_card_name,
                                    existing_card_name=card_obj.name,
                                    existing_card_summary=card_obj.summary or "",
                                )

                                # Lower threshold from 0.7 to 0.6 - prefer enrichment
                                if (
                                    decision.get("is_match")
                                    and decision.get("confidence", 0) >= 0.6
                                ):
                                    logger.info(
                                        f"LLM MATCH: '{suggested_name}' -> '{card_obj.name}' "
                                        f"(vector: {similarity:.3f}, llm_conf: {decision.get('confidence', 0):.2f}) - ENRICHING"
                                    )
                                    enrichment_candidates.append(
                                        (source, top_match["id"], similarity)
                                    )
                                    if source.discovered_source_id:
                                        await self._update_source_dedup(
                                            source.discovered_source_id,
                                            "enrichment_candidate",
                                            top_match["id"],
                                            similarity,
                                        )
                                else:
                                    logger.info(
                                        f"LLM NO MATCH: '{suggested_name}' vs '{card_obj.name}' "
                                        f"(reason: {decision.get('reasoning', 'unknown')[:80]}) - NEW CONCEPT"
                                    )
                                    new_concept_candidates.append(source)
                                    if source.discovered_source_id:
                                        await self._update_source_dedup(
                                            source.discovered_source_id, "unique"
                                        )
                            else:
                                new_concept_candidates.append(source)
                                if source.discovered_source_id:
                                    await self._update_source_dedup(
                                        source.discovered_source_id, "unique"
                                    )
                        else:
                            logger.info(
                                f"NO MATCH: '{suggested_name}' - best vector similarity {similarity:.3f} "
                                f"below threshold {config.weak_match_threshold} - NEW CONCEPT"
                            )
                            new_concept_candidates.append(source)
                            if source.discovered_source_id:
                                await self._update_source_dedup(
                                    source.discovered_source_id, "unique"
                                )
                    else:
                        logger.info(
                            f"NO MATCHES FOUND: '{suggested_name}' - NEW CONCEPT"
                        )
                        new_concept_candidates.append(source)
                        if source.discovered_source_id:
                            await self._update_source_dedup(
                                source.discovered_source_id, "unique"
                            )

                except Exception as e:
                    # Vector search failed - use Python fallback
                    logger.warning(f"Vector search failed for '{suggested_name}': {e}")
                    logger.info("Falling back to Python-based similarity search...")

                    # Python fallback: fetch cards with embeddings and calculate similarity locally
                    try:
                        fallback_result = await self._python_vector_search(
                            source.embedding,
                            config,
                            suggested_name,
                            source,
                            enrichment_candidates,
                            new_concept_candidates,
                        )
                    except Exception as fallback_error:
                        logger.error(f"Python fallback also failed: {fallback_error}")
                        new_concept_candidates.append(source)
                        if source.discovered_source_id:
                            await self._update_source_dedup(
                                source.discovered_source_id, "unique"
                            )

                unique_sources.append(source)

            except Exception as e:
                logger.warning(f"Deduplication failed for {source.raw.url}: {e}")
                continue

        # Summary logging
        logger.info(
            f"Deduplication complete: {len(sources)} sources -> "
            f"{duplicate_count} duplicates, {len(enrichment_candidates)} enrichments, "
            f"{len(new_concept_candidates)} new concepts"
        )

        return DeduplicationResult(
            unique_sources=unique_sources,
            duplicate_count=duplicate_count,
            enrichment_candidates=enrichment_candidates,
            new_concept_candidates=new_concept_candidates,
        )

    async def _deduplicate_sources_with_metrics(
        self, sources: List[ProcessedSource], config: DiscoveryConfig
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
                url_result = await self.db.execute(
                    select(Source.id).where(Source.url == source.raw.url)
                )
                url_existing = url_result.scalars().first()

                if url_existing:
                    duplicate_count += 1
                    continue

                # Vector similarity search against existing cards
                try:
                    match_data = await vector_search_cards(
                        self.db,
                        query_embedding=source.embedding,
                        match_threshold=config.weak_match_threshold,
                        match_count=3,
                    )

                    if match_data:
                        top_match = match_data[0]
                        similarity = top_match.get("similarity", 0)

                        if similarity >= config.similarity_threshold:
                            # Strong match - enrich existing card
                            enrichment_candidates.append(
                                (source, top_match["id"], similarity)
                            )
                        elif similarity >= config.weak_match_threshold:
                            # Weak match - use LLM to decide
                            card_result_q = await self.db.execute(
                                select(Card).where(
                                    Card.id == uuid.UUID(top_match["id"])
                                )
                            )
                            card_obj = card_result_q.scalar_one_or_none()

                            if card_obj:
                                decision = await self.ai_service.check_card_match(
                                    source_summary=source.analysis.summary,
                                    source_card_name=source.analysis.suggested_card_name,
                                    existing_card_name=card_obj.name,
                                    existing_card_summary=card_obj.summary or "",
                                )
                                # Estimate tokens for card match check
                                input_text = f"{source.analysis.summary} {source.analysis.suggested_card_name} {card_obj.name} {card_obj.summary or ''}"
                                total_tokens += (
                                    len(input_text) // 4 + 100
                                )  # input + output estimate

                                if (
                                    decision.get("is_match")
                                    and decision.get("confidence", 0) > 0.7
                                ):
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

        return (
            DeduplicationResult(
                unique_sources=unique_sources,
                duplicate_count=duplicate_count,
                enrichment_candidates=enrichment_candidates,
                new_concept_candidates=new_concept_candidates,
            ),
            total_tokens,
        )

    # ========================================================================
    # Step 7: Create or Enrich Cards
    # ========================================================================

    async def _create_or_enrich_cards(
        self, run_id: str, dedup_result: DeduplicationResult, config: DiscoveryConfig
    ) -> CardActionResult:
        """
        Create new cards or enrich existing ones based on deduplication results.

        SAFEGUARDS:
        - Limits new cards per run (max_new_cards_per_run)
        - Clusters similar new concepts before creation
        - Enrichment always processed first (unlimited)

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
        all_stored_source_ids: List[str] = []  # Track for story clustering

        logger.info(
            f"Processing card actions: {len(dedup_result.enrichment_candidates)} enrichments, "
            f"{len(dedup_result.new_concept_candidates)} new concepts"
        )

        # STEP 1: Process enrichment candidates first (no limit - always enrich)
        for source, card_id, similarity in dedup_result.enrichment_candidates:
            try:
                source_id = await self._store_source_to_card(source, card_id)
                if source_id:
                    sources_added += 1
                    all_stored_source_ids.append(source_id)
                    if card_id not in cards_enriched:
                        cards_enriched.append(card_id)
                        logger.info(
                            f"Enriched card {card_id} with source: {source.raw.title[:50]}"
                        )
                    # Update discovered_sources with enrichment outcome
                    if source.discovered_source_id:
                        await self._update_source_outcome(
                            source.discovered_source_id,
                            "card_enriched",
                            card_id=card_id,
                            source_record_id=source_id,
                        )
            except Exception as e:
                logger.warning(f"Failed to enrich card {card_id}: {e}")
                if source.discovered_source_id:
                    await self._update_source_outcome(
                        source.discovered_source_id,
                        "error",
                        error_message=str(e),
                        error_stage="enrichment",
                    )

        # Score alignment for enriched cards (non-blocking)
        for enriched_card_id in cards_enriched:
            await self._score_alignment_for_card(enriched_card_id)

        # STEP 2: Cluster similar new concepts before creation
        # Group sources with similar names to avoid creating near-duplicate cards
        new_concepts = dedup_result.new_concept_candidates
        if len(new_concepts) > 1:
            clustered = self._cluster_similar_concepts(new_concepts, config)
            logger.info(
                f"Clustered {len(new_concepts)} new concepts into {len(clustered)} groups"
            )
        else:
            # Each source is its own cluster
            clustered = [[s] for s in new_concepts]

        # STEP 3: Create cards with limit enforcement
        cards_created_count = 0
        skipped_due_to_limit = 0

        for cluster in clustered:
            if cards_created_count >= config.max_new_cards_per_run:
                skipped_due_to_limit += len(cluster)
                for source in cluster:
                    if source.discovered_source_id:
                        await self._update_source_outcome(
                            source.discovered_source_id,
                            "error",
                            error_message=f"Card limit reached ({config.max_new_cards_per_run})",
                            error_stage="card_creation",
                        )
                continue

            # Pick the best source from the cluster as the card template
            primary_source = cluster[0]  # First source (could use confidence ranking)
            if not primary_source.analysis:
                logger.warning(
                    f"Skipping cluster without analysis: {primary_source.raw.title}"
                )
                continue

            try:
                # Calculate confidence score for auto-approval
                confidence = self._calculate_discovery_confidence(primary_source)

                # Create new card from primary source
                card_id = await self._create_card_from_source(
                    primary_source, run_id=run_id, confidence=confidence
                )
                if not card_id:
                    if primary_source.discovered_source_id:
                        await self._update_source_outcome(
                            primary_source.discovered_source_id,
                            "error",
                            error_message="Card creation returned no ID",
                            error_stage="card_creation",
                        )
                    continue

                cards_created.append(card_id)
                cards_created_count += 1
                logger.info(
                    f"Created card {cards_created_count}/{config.max_new_cards_per_run}: "
                    f"'{primary_source.analysis.suggested_card_name}'"
                )

                # Store primary source to new card
                source_id = await self._store_source_to_card(primary_source, card_id)
                if source_id:
                    sources_added += 1
                    all_stored_source_ids.append(source_id)

                # Update discovered_sources for primary
                if primary_source.discovered_source_id:
                    await self._update_source_outcome(
                        primary_source.discovered_source_id,
                        "card_created",
                        card_id=card_id,
                        source_record_id=source_id,
                    )

                # Add remaining cluster sources to the same card (enrichment)
                for additional_source in cluster[1:]:
                    try:
                        add_source_id = await self._store_source_to_card(
                            additional_source, card_id
                        )
                        if add_source_id:
                            sources_added += 1
                            all_stored_source_ids.append(add_source_id)
                            logger.debug(
                                f"Added clustered source to card: {additional_source.raw.title[:40]}"
                            )
                        if additional_source.discovered_source_id:
                            await self._update_source_outcome(
                                additional_source.discovered_source_id,
                                "card_enriched",
                                card_id=card_id,
                                source_record_id=add_source_id,
                            )
                    except Exception as e:
                        logger.warning(f"Failed to add clustered source: {e}")

                # Auto-approve if confidence exceeds threshold
                if confidence >= config.auto_approve_threshold:
                    await self._auto_approve_card(card_id)
                    auto_approved += 1
                else:
                    pending_review += 1

                # Score alignment against active workstreams (non-blocking)
                await self._score_alignment_for_card(card_id)

            except Exception as e:
                logger.warning(
                    f"Failed to create card for {primary_source.raw.title}: {e}"
                )
                if primary_source.discovered_source_id:
                    await self._update_source_outcome(
                        primary_source.discovered_source_id,
                        "error",
                        error_message=str(e),
                        error_stage="card_creation",
                    )

        if skipped_due_to_limit > 0:
            logger.warning(
                f"Card creation limit reached: {skipped_due_to_limit} sources skipped "
                f"(limit: {config.max_new_cards_per_run})"
            )

        # STEP 4: Story-level deduplication via semantic clustering
        # Sources are now persisted with DB IDs, so we can cluster them.
        # This assigns story_cluster_id to each source, enabling corroboration
        # counting and deduplication in the discovery queue.
        story_cluster_count = 0
        if all_stored_source_ids:
            try:
                cluster_result = cluster_sources(self.db, all_stored_source_ids)
                story_cluster_count = cluster_result.get("cluster_count", 0)
                logger.info(
                    f"Story clustering: {len(all_stored_source_ids)} sources -> "
                    f"{story_cluster_count} story clusters"
                )
            except Exception as e:
                logger.warning(f"Story clustering failed (non-fatal): {e}")

        return CardActionResult(
            cards_created=cards_created,
            cards_enriched=cards_enriched,
            sources_added=sources_added,
            auto_approved=auto_approved,
            pending_review=pending_review,
            story_cluster_count=story_cluster_count,
        )

    def _cluster_similar_concepts(
        self, sources: List[ProcessedSource], config: DiscoveryConfig
    ) -> List[List[ProcessedSource]]:
        """
        Cluster similar new concepts to avoid creating near-duplicate cards.

        Uses a two-tier approach:
        1. Embedding cosine similarity (semantic meaning) — primary signal
        2. Name similarity (word overlap) — fallback when embeddings are missing

        This prevents the situation where 5 sources about "AI in healthcare" create
        5 different cards instead of 1 card with 5 sources.

        Args:
            sources: List of new concept sources to cluster
            config: Discovery configuration with thresholds

        Returns:
            List of clusters, where each cluster is a list of sources
        """
        if not sources:
            return []

        # Use a simple greedy clustering approach
        clusters: List[List[ProcessedSource]] = []
        used = set()

        # Threshold for embedding-based clustering (lower than dedup's 0.85
        # to catch topically-related articles that aren't exact duplicates)
        EMBEDDING_CLUSTER_THRESHOLD = 0.80
        NAME_CLUSTER_THRESHOLD = 0.6

        # Sort by confidence (highest first) to pick best source as cluster representative
        sorted_sources = sorted(
            sources, key=lambda s: self._calculate_discovery_confidence(s), reverse=True
        )

        for source in sorted_sources:
            if id(source) in used:
                continue

            # Start a new cluster with this source
            cluster = [source]
            used.add(id(source))

            source_name = source.analysis.suggested_card_name if source.analysis else ""
            source_embedding = source.embedding if source.embedding else None

            if not source_name and not source_embedding:
                clusters.append(cluster)
                continue

            # Find similar sources to add to this cluster
            for other in sorted_sources:
                if id(other) in used:
                    continue

                matched = False
                match_reason = ""
                match_score = 0.0

                # Tier 1: Embedding cosine similarity (semantic)
                other_embedding = other.embedding if other.embedding else None
                if source_embedding and other_embedding:
                    sim = cosine_similarity(source_embedding, other_embedding)
                    if sim >= EMBEDDING_CLUSTER_THRESHOLD:
                        matched = True
                        match_reason = "embedding"
                        match_score = sim

                # Tier 2: Name similarity fallback (when embeddings unavailable)
                if not matched:
                    other_name = (
                        other.analysis.suggested_card_name if other.analysis else ""
                    )
                    if source_name and other_name:
                        name_sim = calculate_name_similarity(source_name, other_name)
                        if name_sim >= NAME_CLUSTER_THRESHOLD:
                            matched = True
                            match_reason = "name"
                            match_score = name_sim

                if matched:
                    cluster.append(other)
                    used.add(id(other))
                    other_name = (
                        other.analysis.suggested_card_name
                        if other.analysis
                        else other.raw.title[:40]
                    )
                    logger.info(
                        f"Clustered '{other_name}' with '{source_name}' "
                        f"({match_reason} similarity: {match_score:.2f})"
                    )

            clusters.append(cluster)

        return clusters

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
            triage_score * triage_weight
            + credibility_score * credibility_weight
            + relevance_score * relevance_weight
            + novelty_score * novelty_weight
        )

        return min(max(confidence, 0.0), 1.0)

    async def _create_card_from_source(
        self,
        source: ProcessedSource,
        run_id: str,
        confidence: Optional[float] = None,
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
        slug_result = await self.db.execute(select(Card.id).where(Card.slug == slug))
        if slug_result.scalars().first():
            slug = f"{slug}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        # Convert stage number to stage_id (foreign key)
        stage_id = STAGE_NUMBER_TO_ID.get(analysis.suggested_stage, "4_proof")

        goal_id = convert_goal_id(analysis.goals[0]) if analysis.goals else None
        try:
            now = datetime.now(timezone.utc)
            ai_confidence = None
            if confidence is not None:
                try:
                    ai_confidence = round(float(confidence), 2)
                except Exception:
                    ai_confidence = None

            card_obj = Card(
                name=analysis.suggested_card_name,
                slug=slug,
                summary=analysis.summary,
                horizon=analysis.horizon,
                stage_id=stage_id,
                pillar_id=(
                    convert_pillar_id(analysis.pillars[0]) if analysis.pillars else None
                ),
                goal_id=goal_id,
                maturity_score=int(analysis.credibility * 20),
                novelty_score=int(analysis.novelty * 20),
                impact_score=int(analysis.impact * 20),
                relevance_score=int(analysis.relevance * 20),
                velocity_score=int(analysis.velocity * 10),
                risk_score=int(analysis.risk * 10),
                status="draft",
                review_status="pending_review",
                discovered_at=now,
                discovery_run_id=(
                    uuid.UUID(run_id) if isinstance(run_id, str) else run_id
                ),
                ai_confidence=ai_confidence,
                discovery_metadata={
                    "source_url": source.raw.url,
                    "source_title": source.raw.title,
                    "source_name": source.raw.source_name,
                },
                created_by=(
                    uuid.UUID(self.triggered_by_user_id)
                    if self.triggered_by_user_id
                    else None
                ),
                created_at=now,
                updated_at=now,
            )
            self.db.add(card_obj)
            await self.db.flush()
            await self.db.refresh(card_obj)

            card_id = str(card_obj.id)

            # Store embedding on the card for Related Trends feature
            # pgvector NullType column requires raw SQL with CAST
            try:
                emb_data = source.embedding
                if not emb_data:
                    embed_text = compose_embedding_text(
                        analysis.suggested_card_name, analysis.summary
                    )
                    emb_data = await self.ai_service.generate_embedding(embed_text)
                if emb_data:
                    vec_str = "[" + ",".join(str(v) for v in emb_data) + "]"
                    await self.db.execute(
                        text(
                            "UPDATE cards SET embedding = CAST(:vec AS vector) WHERE id = CAST(:cid AS uuid)"
                        ),
                        {"vec": vec_str, "cid": card_id},
                    )
                    await self.db.flush()
            except Exception as e:
                logger.warning(f"Failed to store embedding on card {card_id}: {e}")

            # Create timeline event
            await self._create_timeline_event(
                card_id=card_id,
                event_type="discovered",
                description="Card discovered via automated scan",
            )

            return card_id

        except Exception as e:
            logger.error(f"Failed to create card: {e}")

        return None

    async def _store_source_to_card(
        self, source: ProcessedSource, card_id: str
    ) -> Optional[str]:
        """
        Store a processed source to a card.

        Runs embedding-based deduplication before inserting.  If the source
        is a duplicate (>0.95 similarity), it is skipped.  If related
        (0.85-0.95), it is stored with ``duplicate_of`` set.

        Args:
            source: Processed source
            card_id: Target card ID

        Returns:
            Source ID or None if failed
        """
        try:
            # --- Deduplication check (URL + embedding) ---
            from app.deduplication import check_duplicate

            dedup_result = await check_duplicate(
                db=self.db,
                card_id=card_id,
                content=source.raw.content or "",
                url=source.raw.url or "",
                embedding=source.embedding if hasattr(source, "embedding") else None,
                ai_service=self.ai_service,
            )

            if dedup_result.action == "skip":
                logger.debug(
                    f"Dedup: skipping duplicate source (sim={dedup_result.similarity:.4f}): "
                    f"{source.raw.url[:50]}..."
                )
                return None

            # Look up domain reputation ID for this source (Task 2.7)
            _domain_reputation_id = None
            try:
                if _rep := await domain_reputation_service.get_reputation(
                    self.db, source.raw.url or ""
                ):
                    _domain_reputation_id = _rep.get("id")
            except Exception:
                pass  # Non-fatal

            from app.source_quality import extract_domain

            _is_peer_reviewed = (
                False
                if getattr(source.raw, "is_preprint", False)
                else (
                    True
                    if getattr(source.raw, "source_type", None) == "academic"
                    else None
                )
            )

            source_obj = Source(
                card_id=uuid.UUID(card_id) if isinstance(card_id, str) else card_id,
                url=source.raw.url,
                title=(source.raw.title or "Untitled")[:500],
                publication=(
                    (source.raw.source_name or "")[:200]
                    if source.raw.source_name
                    else None
                ),
                full_text=(source.raw.content[:10000] if source.raw.content else None),
                ai_summary=(source.analysis.summary if source.analysis else None),
                key_excerpts=(
                    source.analysis.key_excerpts[:5]
                    if source.analysis and source.analysis.key_excerpts
                    else []
                ),
                relevance_to_card=(
                    source.analysis.relevance if source.analysis else 0.5
                ),
                is_peer_reviewed=_is_peer_reviewed,
                api_source="discovery_scan",
                domain=extract_domain(source.raw.url or ""),
                ingested_at=datetime.now(timezone.utc),
            )

            # If related (0.85-0.95 similarity), mark duplicate_of
            if (
                dedup_result.action == "store_as_related"
                and dedup_result.duplicate_of_id
            ):
                source_obj.duplicate_of = (
                    uuid.UUID(dedup_result.duplicate_of_id)
                    if isinstance(dedup_result.duplicate_of_id, str)
                    else dedup_result.duplicate_of_id
                )

            # Add domain_reputation_id if available (Task 2.7)
            if _domain_reputation_id:
                source_obj.domain_reputation_id = (
                    uuid.UUID(_domain_reputation_id)
                    if isinstance(_domain_reputation_id, str)
                    else _domain_reputation_id
                )

            self.db.add(source_obj)
            await self.db.flush()
            await self.db.refresh(source_obj)
            source_id = str(source_obj.id)

            # Compute and store source quality score (non-blocking)
            try:
                from app.source_quality import compute_and_store_quality_score

                await compute_and_store_quality_score(
                    self.db,
                    source_id,
                    analysis=(source.analysis if hasattr(source, "analysis") else None),
                    triage=source.triage if hasattr(source, "triage") else None,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to compute quality score for source {source_id}: {e}"
                )

            return source_id

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
            _cid = uuid.UUID(card_id) if isinstance(card_id, str) else card_id
            await self.db.execute(
                sa_update(Card)
                .where(Card.id == _cid)
                .values(
                    status="active",
                    review_status="active",
                    auto_approved_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await self.db.flush()

            await self._create_timeline_event(
                card_id=card_id,
                event_type="auto_approved",
                description="Card auto-approved based on high confidence score",
            )

        except Exception as e:
            logger.warning(f"Failed to auto-approve card {card_id}: {e}")

    async def _score_alignment_for_card(self, card_id: str) -> None:
        """Score a newly created/enriched card against all active workstreams.

        Stores the highest alignment score on the card record and auto-adds
        the card to any workstream scoring >= 60 as "discovered" status.

        This is a best-effort operation -- failures are logged but never
        block the main discovery pipeline.
        """
        try:
            from app.alignment_service import AlignmentService

            _cid = uuid.UUID(card_id) if isinstance(card_id, str) else card_id

            # Fetch the card record
            card_result_q = await self.db.execute(select(Card).where(Card.id == _cid))
            card_obj = card_result_q.scalar_one_or_none()
            if not card_obj:
                return
            # Convert to dict for alignment service compatibility
            card = {c.key: getattr(card_obj, c.key) for c in Card.__table__.columns}
            card["id"] = str(card_obj.id)

            # Fetch all active workstreams for this user
            _uid = (
                uuid.UUID(self.triggered_by_user_id)
                if self.triggered_by_user_id
                and isinstance(self.triggered_by_user_id, str)
                else self.triggered_by_user_id
            )
            ws_result = await self.db.execute(
                select(Workstream).where(
                    and_(Workstream.is_active == True, Workstream.user_id == _uid)
                )
            )
            workstream_objs = ws_result.scalars().all()
            if not workstream_objs:
                return

            alignment_svc = AlignmentService()
            best_score = 0
            auto_added_count = 0

            for ws_obj in workstream_objs:
                try:
                    # Convert to dict for alignment service compatibility
                    ws = {
                        c.key: getattr(ws_obj, c.key)
                        for c in Workstream.__table__.columns
                    }
                    ws["id"] = str(ws_obj.id)
                    result = await alignment_svc.score_grant_against_program(card, ws)
                    if result.overall_score > best_score:
                        best_score = result.overall_score

                    # Auto-add to workstream pipeline if score >= 60
                    if result.overall_score >= 60:
                        # Check if already present
                        existing_wc = await self.db.execute(
                            select(WorkstreamCard.id)
                            .where(
                                and_(
                                    WorkstreamCard.workstream_id == ws_obj.id,
                                    WorkstreamCard.card_id == _cid,
                                )
                            )
                            .limit(1)
                        )
                        if not existing_wc.scalars().first():
                            now = datetime.now(timezone.utc)
                            wc_obj = WorkstreamCard(
                                workstream_id=ws_obj.id,
                                card_id=_cid,
                                added_by=_uid,
                                added_at=now,
                                status="discovered",
                                position=0,
                                added_from="auto",
                                updated_at=now,
                            )
                            self.db.add(wc_obj)
                            await self.db.flush()
                            auto_added_count += 1
                            logger.info(
                                "Alignment auto-add: card %s -> workstream %s "
                                "(score=%d)",
                                card_id,
                                str(ws_obj.id),
                                result.overall_score,
                            )
                except Exception as ws_err:
                    logger.warning(
                        "Alignment scoring failed for card %s vs workstream %s: %s",
                        card_id,
                        str(ws_obj.id) if ws_obj else "?",
                        ws_err,
                    )

            # Store highest alignment score on the card
            if best_score > 0:
                await self.db.execute(
                    sa_update(Card)
                    .where(Card.id == _cid)
                    .values(alignment_score=best_score)
                )
                await self.db.flush()
                logger.info(
                    "Alignment score stored for card %s: %d (auto-added to %d workstreams)",
                    card_id,
                    best_score,
                    auto_added_count,
                )

        except Exception as e:
            logger.warning(
                "Alignment scoring failed for card %s (non-fatal): %s",
                card_id,
                e,
            )

    async def _create_timeline_event(
        self,
        card_id: str,
        event_type: str,
        description: str,
        source_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Create a timeline event for a card."""
        try:
            tl_obj = CardTimeline(
                card_id=uuid.UUID(card_id) if isinstance(card_id, str) else card_id,
                event_type=event_type,
                title=event_type.replace("_", " ").title(),
                description=description,
                triggered_by_source_id=(
                    uuid.UUID(source_id)
                    if source_id and isinstance(source_id, str)
                    else source_id
                ),
                metadata_=metadata or {},
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(tl_obj)
            await self.db.flush()
        except Exception as e:
            logger.warning(f"Failed to create timeline event: {e}")

    # ========================================================================
    # Step 8: Update Run Record
    # ========================================================================

    async def _update_run_record(self, run_id: str, result: DiscoveryResult) -> None:
        """
        Update the discovery run record with results.

        Args:
            run_id: Run ID
            result: Discovery result
        """
        try:
            _run_id = uuid.UUID(run_id) if isinstance(run_id, str) else run_id

            # Preserve any existing fields (e.g., initial config + live progress)
            # that may have been written into `summary_report` earlier in the run.
            existing_report: Dict[str, Any] = {}
            try:
                result_dr = await self.db.execute(
                    select(DiscoveryRun).where(DiscoveryRun.id == _run_id)
                )
                dr_row = result_dr.scalar_one_or_none()
                raw_report = dr_row.summary_report if dr_row else None
                if isinstance(raw_report, dict):
                    existing_report = raw_report
            except Exception:
                existing_report = {}

            final_report = {
                "stage": result.status.value,
                "markdown": result.summary_report,
                "queries_executed": result.queries_executed,
                "sources_blocked": result.sources_blocked,
                "sources_added": result.sources_added,
                "auto_approved": result.auto_approved,
                "pending_review": result.pending_review,
                "execution_time_seconds": result.execution_time_seconds,
                "cards_created_ids": result.cards_created,
                "cards_enriched_ids": result.cards_enriched,
            }

            updated_report = existing_report | final_report

            await self.db.execute(
                sa_update(DiscoveryRun)
                .where(DiscoveryRun.id == _run_id)
                .values(
                    status=result.status.value,
                    completed_at=result.completed_at,
                    queries_generated=result.queries_generated,
                    sources_found=result.sources_discovered,
                    sources_relevant=result.sources_triaged,
                    cards_created=(
                        len(result.cards_created)
                        if isinstance(result.cards_created, list)
                        else result.cards_created
                    ),
                    cards_enriched=(
                        len(result.cards_enriched)
                        if isinstance(result.cards_enriched, list)
                        else result.cards_enriched
                    ),
                    cards_deduplicated=result.sources_duplicate,
                    estimated_cost=result.estimated_cost,
                    error_message=result.errors[0] if result.errors else None,
                    error_details=(
                        {"errors": result.errors} if result.errors else None
                    ),
                    summary_report=updated_report,
                )
            )
            await self.db.flush()
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
        api_token_usage_metrics: Optional[APITokenUsage] = None,
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
        end_time = datetime.now(timezone.utc)
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
            api_token_usage_metrics=api_token_usage_metrics,
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
            diversity_metrics=(
                diversity_metrics.to_dict() if diversity_metrics else None
            ),
            cards_created=card_result.cards_created,
            cards_enriched=card_result.cards_enriched,
            sources_added=card_result.sources_added,
            auto_approved=card_result.auto_approved,
            pending_review=card_result.pending_review,
            estimated_cost=cost,
            execution_time_seconds=execution_time,
            processing_time=(
                processing_time_metrics.to_dict() if processing_time_metrics else None
            ),
            api_token_usage=(
                api_token_usage_metrics.to_dict() if api_token_usage_metrics else None
            ),
            summary_report=summary,
            errors=errors,
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
        api_token_usage_metrics: Optional[APITokenUsage] = None,
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
                report += (
                    f"- **Dominant Category**: {diversity_metrics.dominant_category}\n"
                )
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
    db: AsyncSession, openai_client: openai.OpenAI, pillars: Optional[List[str]] = None
) -> DiscoveryResult:
    """
    Convenience function to run weekly discovery scan.

    Args:
        db: SQLAlchemy async session
        openai_client: OpenAI client
        pillars: Optional list of pillar codes to filter

    Returns:
        DiscoveryResult
    """
    service = DiscoveryService(db, openai_client)
    config = DiscoveryConfig(
        max_queries_per_run=100,
        max_sources_total=500,
        pillars_filter=pillars or [],
        include_priorities=True,
    )
    return await service.execute_discovery_run(config)


async def run_pillar_discovery(
    db: AsyncSession, openai_client: openai.OpenAI, pillar_code: str
) -> DiscoveryResult:
    """
    Run discovery for a specific pillar.

    Args:
        db: SQLAlchemy async session
        openai_client: OpenAI client
        pillar_code: Pillar code (e.g., 'CH', 'MC')

    Returns:
        DiscoveryResult
    """
    service = DiscoveryService(db, openai_client)
    config = DiscoveryConfig(
        max_queries_per_run=25,
        max_sources_total=100,
        pillars_filter=[pillar_code],
        include_priorities=True,
    )
    return await service.execute_discovery_run(config)
