"""
Workstream Targeted Scan Service.

A lightweight, focused discovery service that scans for content relevant to
a user's workstream based on its keywords, pillars, and horizon settings.

Key differences from broad discovery:
- Queries generated purely from workstream metadata (no default topic clamping)
- Lighter resource limits (fewer queries, sources, cards)
- Discovered cards go to global pool AND auto-added to user's workstream inbox
- Rate limited to 2 scans per workstream per day

Usage:
    from app.workstream_scan_service import WorkstreamScanService, WorkstreamScanConfig

    config = WorkstreamScanConfig(
        workstream_id="uuid",
        user_id="uuid",
        keywords=["AI traffic signals", "smart parking"],
        pillar_ids=["MC"],
        horizon="H2"
    )
    service = WorkstreamScanService(supabase_client, openai_client)
    result = await service.execute_scan(config)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
import uuid

from supabase import Client
import openai

from .ai_service import AIService, AnalysisResult, TriageResult
from .research_service import RawSource, ProcessedSource
from .source_validator import SourceValidator
from . import domain_reputation_service
from .source_fetchers import (
    fetch_rss_sources,
    fetch_news_articles,
    fetch_academic_papers,
    fetch_government_sources,
    fetch_tech_blog_articles,
    convert_to_raw_source as convert_academic_to_raw,
    convert_government_to_raw_source,
)

logger = logging.getLogger(__name__)

# Import shared taxonomy constants
from .taxonomy import (
    PILLAR_NAMES,
    STAGE_NUMBER_TO_ID,
    convert_pillar_id,
    convert_goal_id,
)


@dataclass
class WorkstreamScanConfig:
    """Configuration for a workstream-targeted scan."""

    workstream_id: str
    user_id: str
    scan_id: str  # Pre-created scan record ID

    # From workstream metadata
    keywords: List[str] = field(default_factory=list)
    pillar_ids: List[str] = field(default_factory=list)
    horizon: str = "ALL"

    # Resource limits (lighter than broad discovery)
    max_queries: int = 15
    max_sources_per_category: int = 15
    max_new_cards: int = 8

    # Thresholds
    triage_threshold: float = 0.6
    similarity_threshold: float = 0.85
    auto_approve_threshold: float = 0.95

    # Auto-add to workstream inbox
    auto_add_to_workstream: bool = True

    # Card-level source preferences (merged from cards in the workstream)
    source_preferences: dict = field(default_factory=dict)


@dataclass
class ScanResult:
    """Result of a workstream scan."""

    scan_id: str
    workstream_id: str
    status: str  # completed, failed

    # Metrics
    queries_executed: int = 0
    sources_fetched: int = 0
    sources_by_category: Dict[str, int] = field(default_factory=dict)
    sources_triaged: int = 0
    cards_created: List[str] = field(default_factory=list)
    cards_enriched: List[str] = field(default_factory=list)
    cards_added_to_workstream: List[str] = field(default_factory=list)
    duplicates_skipped: int = 0

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time_seconds: float = 0.0

    # Errors
    errors: List[str] = field(default_factory=list)


class WorkstreamScanService:
    """
    Standalone service for workstream-targeted content discovery.
    """

    def __init__(
        self,
        supabase: Client,
        openai_client: openai.OpenAI,
    ):
        self.supabase = supabase
        self.openai_client = openai_client
        self.ai_service = AIService(openai_client)

    async def execute_scan(self, config: WorkstreamScanConfig) -> ScanResult:
        """
        Execute a targeted scan for a workstream.

        Steps:
        1. Rate limit check (max 10 scans per workstream per 24 hours)
        2. Generate queries from workstream keywords + pillars
        3. Fetch from all 5 source categories
        4. Validate content quality and freshness
        5. Triage and analyze sources
        6. Deduplicate against existing cards
        7. Create new cards (global pool)
        8. Auto-add to workstream inbox
        """
        # FIX-H5: Rate limiting - max 10 scans per workstream per 24 hours
        try:
            cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
            recent_scans = (
                self.supabase.table("workstream_scans")
                .select("id")
                .eq("workstream_id", config.workstream_id)
                .gte("created_at", cutoff)
                .execute()
            )
            scan_count = len(recent_scans.data) if recent_scans.data else 0
            if scan_count >= 10:
                logger.warning(
                    f"Rate limit exceeded for workstream {config.workstream_id}: "
                    f"{scan_count} scans in last 24h (max 10). Skipping scan."
                )
                return ScanResult(
                    scan_id=config.scan_id,
                    workstream_id=config.workstream_id,
                    status="rate_limited",
                    errors=[
                        f"Rate limit exceeded: {scan_count} scans in last 24 hours (max 10)"
                    ],
                    completed_at=datetime.now(),
                )
        except Exception as e:
            logger.warning(f"Rate limit check failed, proceeding with scan: {e}")

        start_time = datetime.now()
        result = ScanResult(
            scan_id=config.scan_id,
            workstream_id=config.workstream_id,
            status="running",
            started_at=start_time,
        )

        try:
            # Update scan status to running
            await self._update_scan_status(
                config.scan_id, "running", started_at=start_time
            )

            # Step 1: Generate queries
            queries = self._generate_queries(config)
            result.queries_executed = len(queries)
            logger.info(f"Generated {len(queries)} queries for workstream scan")

            # Step 2: Fetch sources from all categories
            raw_sources, sources_by_category = await self._fetch_sources(
                queries, config
            )
            result.sources_fetched = len(raw_sources)
            result.sources_by_category = sources_by_category
            logger.info(f"Fetched {len(raw_sources)} sources across categories")

            if not raw_sources:
                result.status = "completed"
                result.completed_at = datetime.now()
                result.execution_time_seconds = (
                    result.completed_at - start_time
                ).total_seconds()
                await self._finalize_scan(config.scan_id, result)
                return result

            # Step 2b: Preload domain reputation cache (Task 2.7)
            try:
                source_urls = [s.url for s in raw_sources if s.url]
                domain_reputation_service.get_reputation_batch(
                    self.supabase, source_urls
                )
                logger.info(
                    "Domain reputation cache preloaded for %d source URLs",
                    len(source_urls),
                )
            except Exception as e:
                logger.warning(
                    f"Domain reputation cache preload failed (non-fatal): {e}"
                )

            # Step 3: Triage and analyze
            logger.info(f"Starting triage of {len(raw_sources)} raw sources...")
            processed_sources = await self._triage_and_analyze(raw_sources, config)
            result.sources_triaged = len(processed_sources)
            logger.info(
                f"Triaged {len(processed_sources)} relevant sources (from {len(raw_sources)} raw)"
            )

            # Clear domain reputation batch cache after triage (Task 2.7)
            try:
                domain_reputation_service.clear_batch_cache()
            except Exception:
                pass  # Non-fatal

            if not processed_sources:
                logger.warning(
                    "No sources passed triage - completing scan with 0 cards"
                )
                result.status = "completed"
                result.completed_at = datetime.now()
                result.execution_time_seconds = (
                    result.completed_at - start_time
                ).total_seconds()
                await self._finalize_scan(config.scan_id, result)
                return result

            # Step 4: Deduplicate
            logger.info(
                f"Starting deduplication of {len(processed_sources)} sources..."
            )
            unique_sources, enrichment_candidates, duplicates = await self._deduplicate(
                processed_sources, config
            )
            result.duplicates_skipped = duplicates
            logger.info(
                f"Dedup complete: {len(unique_sources)} unique, "
                f"{len(enrichment_candidates)} enrichments, {duplicates} duplicates"
            )

            # Step 5: Process enrichments
            for source, card_id, similarity in enrichment_candidates:
                try:
                    source_id = await self._store_source_to_card(source, card_id)
                    if source_id and card_id not in result.cards_enriched:
                        result.cards_enriched.append(card_id)
                        logger.info(f"Enriched card {card_id}")
                except Exception as e:
                    logger.warning(f"Failed to enrich card {card_id}: {e}")

            # Step 6: Create new cards
            logger.info(
                f"Starting card creation for {len(unique_sources)} unique sources (max: {config.max_new_cards})"
            )
            cards_created_count = 0
            sources_without_analysis = 0
            for source in unique_sources:
                if cards_created_count >= config.max_new_cards:
                    logger.info(f"Reached max cards limit ({config.max_new_cards})")
                    break

                if not source.analysis:
                    sources_without_analysis += 1
                    continue

                try:
                    logger.info(
                        f"Creating card for: {source.analysis.suggested_card_name[:50]}..."
                    )
                    card_id = await self._create_card(source, config)
                    if card_id:
                        result.cards_created.append(card_id)
                        cards_created_count += 1
                        logger.info(
                            f"Created card {card_id}: {source.analysis.suggested_card_name}"
                        )
                    else:
                        logger.warning(
                            f"Card creation returned None for: {source.analysis.suggested_card_name[:50]}"
                        )
                except Exception as e:
                    logger.warning(f"Failed to create card: {e}", exc_info=True)
                    result.errors.append(f"Card creation failed: {str(e)[:100]}")

            if sources_without_analysis > 0:
                logger.warning(
                    f"Skipped {sources_without_analysis} sources without analysis"
                )

            # Step 7: Auto-add to workstream inbox
            if config.auto_add_to_workstream:
                all_card_ids = result.cards_created + result.cards_enriched
                for card_id in all_card_ids:
                    try:
                        added = await self._add_to_workstream(
                            config.workstream_id, card_id, config.user_id
                        )
                        if added:
                            result.cards_added_to_workstream.append(card_id)
                    except Exception as e:
                        logger.warning(
                            f"Failed to add card {card_id} to workstream: {e}"
                        )

            result.status = "completed"

        except Exception as e:
            logger.exception(f"Workstream scan failed: {e}")
            result.status = "failed"
            result.errors.append(str(e))

        result.completed_at = datetime.now()
        result.execution_time_seconds = (
            result.completed_at - start_time
        ).total_seconds()
        await self._finalize_scan(config.scan_id, result)

        return result

    def _generate_queries(self, config: WorkstreamScanConfig) -> List[str]:
        """
        Generate search queries from workstream metadata.

        No default topic clamping - queries are purely workstream-driven.
        """
        queries = []

        # Base modifiers for municipal context
        municipal_modifiers = [
            "smart city",
            "municipal government",
            "city innovation",
            "public sector",
            "urban technology",
        ]

        # Horizon-specific modifiers
        horizon_modifiers = {
            "H1": ["mainstream", "adopted", "implemented", "current"],
            "H2": ["emerging", "transitional", "piloting", "2025 2026"],
            "H3": ["transformative", "future", "experimental", "long-term"],
            "ALL": ["emerging", "innovation"],
        }

        horizon_mods = horizon_modifiers.get(config.horizon, horizon_modifiers["ALL"])

        # Generate queries from keywords
        for keyword in config.keywords[:10]:  # Limit keywords
            # Basic keyword query with municipal context
            queries.append(f'"{keyword}" {municipal_modifiers[0]}')

            # Keyword with horizon modifier
            queries.append(f"{keyword} {horizon_mods[0]} technology")

            # Keyword with pillar context
            for pillar_id in config.pillar_ids[:2]:  # Limit pillars
                pillar_name = PILLAR_NAMES.get(pillar_id, "")
                if pillar_name:
                    queries.append(f"{keyword} {pillar_name}")

        # Add pillar-specific queries if few keywords
        if len(config.keywords) < 3:
            for pillar_id in config.pillar_ids:
                pillar_name = PILLAR_NAMES.get(pillar_id, "")
                if pillar_name:
                    queries.append(f"{pillar_name} {horizon_mods[0]} technology city")
                    queries.append(f"{pillar_name} municipal innovation")

        # Dedupe and limit
        seen = set()
        unique_queries = []
        for q in queries:
            q_lower = q.lower()
            if q_lower not in seen:
                seen.add(q_lower)
                unique_queries.append(q)

        return unique_queries[: config.max_queries]

    async def _fetch_sources(
        self, queries: List[str], config: WorkstreamScanConfig
    ) -> Tuple[List[RawSource], Dict[str, int]]:
        """Fetch sources from all 5 categories, respecting source_preferences."""
        all_sources = []
        sources_by_category = {
            "news": 0,
            "tech_blog": 0,
            "academic": 0,
            "government": 0,
            "rss": 0,
        }

        # Determine which categories are enabled via source_preferences
        enabled = (
            config.source_preferences.get("enabled_categories")
            if config.source_preferences
            else None
        )

        # If enabled_categories is specified, only fetch from those; otherwise fetch all
        def is_enabled(cat: str) -> bool:
            if not enabled:
                return True
            return cat in enabled

        # Distribute queries across categories
        query_subset = queries[:5] if len(queries) >= 5 else queries

        # Inject keywords from source_preferences into queries
        extra_keywords = (
            config.source_preferences.get("keywords", [])
            if config.source_preferences
            else []
        )
        if extra_keywords:
            query_subset = list(set(query_subset + extra_keywords[:3]))

        if is_enabled("news"):
            try:
                # News articles
                news_sources = await self._fetch_news(
                    query_subset, config.max_sources_per_category
                )
                all_sources.extend(news_sources)
                sources_by_category["news"] = len(news_sources)
                logger.info(f"News: {len(news_sources)} sources")
            except Exception as e:
                logger.warning(f"News fetch failed: {e}", exc_info=True)

        if is_enabled("tech_blog"):
            try:
                # Tech blogs
                tech_sources = await self._fetch_tech_blogs(
                    query_subset, config.max_sources_per_category
                )
                all_sources.extend(tech_sources)
                sources_by_category["tech_blog"] = len(tech_sources)
                logger.info(f"Tech blogs: {len(tech_sources)} sources")
            except Exception as e:
                logger.warning(f"Tech blog fetch failed: {e}", exc_info=True)

        if is_enabled("academic"):
            try:
                # Academic papers
                academic_sources = await self._fetch_academic(
                    query_subset, config.max_sources_per_category
                )
                all_sources.extend(academic_sources)
                sources_by_category["academic"] = len(academic_sources)
                logger.info(f"Academic: {len(academic_sources)} sources")
            except Exception as e:
                logger.warning(f"Academic fetch failed: {e}", exc_info=True)

        if is_enabled("government"):
            try:
                # Government sources
                gov_sources = await self._fetch_government(
                    query_subset, config.max_sources_per_category
                )
                all_sources.extend(gov_sources)
                sources_by_category["government"] = len(gov_sources)
                logger.info(f"Government: {len(gov_sources)} sources")
            except Exception as e:
                logger.warning(f"Government fetch failed: {e}", exc_info=True)

        if is_enabled("rss"):
            try:
                # RSS feeds
                rss_sources = await self._fetch_rss(
                    query_subset, config.max_sources_per_category
                )
                all_sources.extend(rss_sources)
                sources_by_category["rss"] = len(rss_sources)
                logger.info(f"RSS: {len(rss_sources)} sources")
            except Exception as e:
                logger.warning(f"RSS fetch failed: {e}", exc_info=True)

        logger.info(f"Total sources collected: {len(all_sources)}")
        return all_sources, sources_by_category

    async def _fetch_news(self, queries: List[str], limit: int) -> List[RawSource]:
        """Fetch news articles - matches discovery_service.py pattern."""
        sources = []
        try:
            articles = await fetch_news_articles(topics=queries[:3], max_articles=limit)
            for article in articles[:limit]:
                source = RawSource(
                    url=article.url,
                    title=article.title,
                    content=article.content,
                    source_name=article.source_name,
                    relevance=article.relevance,
                )
                sources.append(source)
        except Exception as e:
            logger.warning(f"News fetch error: {e}")
        return sources

    async def _fetch_tech_blogs(
        self, queries: List[str], limit: int
    ) -> List[RawSource]:
        """Fetch tech blog articles - matches NewsArticle pattern."""
        sources = []
        try:
            articles = await fetch_tech_blog_articles(
                topics=queries[:3], max_articles=limit
            )
            for article in articles[:limit]:
                source = RawSource(
                    url=article.url,
                    title=article.title,
                    content=article.content,
                    source_name=article.source_name,
                    relevance=article.relevance,
                )
                sources.append(source)
        except Exception as e:
            logger.warning(f"Tech blog fetch error: {e}")
        return sources

    async def _fetch_academic(self, queries: List[str], limit: int) -> List[RawSource]:
        """Fetch academic papers."""
        sources = []
        try:
            for query in queries[:2]:
                result = await fetch_academic_papers(
                    query=query, max_results=limit // 2
                )
                # fetch_academic_papers returns AcademicFetchResult, access .papers
                for paper in result.papers:
                    raw = convert_academic_to_raw(paper)
                    sources.append(raw)
                if len(sources) >= limit:
                    break
        except Exception as e:
            logger.warning(f"Academic fetch error: {e}")
        return sources[:limit]

    async def _fetch_government(
        self, queries: List[str], limit: int
    ) -> List[RawSource]:
        """Fetch government sources."""
        sources = []
        try:
            for query in queries[:2]:
                docs = await fetch_government_sources(query, max_results=limit // 2)
                for doc in docs:
                    raw = convert_government_to_raw_source(doc)
                    sources.append(raw)
                if len(sources) >= limit:
                    break
        except Exception as e:
            logger.warning(f"Government fetch error: {e}")
        return sources[:limit]

    async def _fetch_rss(self, queries: List[str], limit: int) -> List[RawSource]:
        """Fetch from RSS feeds."""
        sources = []
        default_feeds = [
            "https://www.govtech.com/rss/",
            "https://statescoop.com/feed/",
        ]
        try:
            result = await fetch_rss_sources(
                default_feeds, max_items_per_feed=limit // 2
            )
            for article in result.articles[:limit]:
                sources.append(
                    RawSource(
                        url=article.url,
                        title=article.title,
                        content=article.content or article.summary or "",
                        source_name=article.feed_title or "RSS",
                        published_at=article.published_at,
                    )
                )
        except Exception as e:
            logger.warning(f"RSS fetch error: {e}")
        return sources[:limit]

    async def _triage_and_analyze(
        self, sources: List[RawSource], config: WorkstreamScanConfig
    ) -> List[ProcessedSource]:
        """Triage sources and analyze relevant ones, with pre-validation."""
        processed = []
        validator = SourceValidator()
        validation_skipped = 0
        preprint_count = 0

        for source in sources:
            try:
                # Pre-validation: content quality and freshness check
                published_date = getattr(source, "published_at", None)
                category = getattr(source, "source_type", "news")
                validation_result = validator.validate_all(
                    content=source.content,
                    published_date=published_date,
                    category=category,
                    url=source.url or "",
                )
                if not validation_result.is_valid:
                    content_code = validation_result.content_validation.reason_code
                    freshness_code = validation_result.freshness_validation.reason_code
                    logger.info(
                        f"Source skipped by validation: url={source.url} "
                        f"content={content_code} freshness={freshness_code}"
                    )
                    validation_skipped += 1
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

                # Skip if no content
                if not source.content:
                    triage = TriageResult(
                        is_relevant=True,
                        confidence=0.6,
                        primary_pillar=(
                            config.pillar_ids[0] if config.pillar_ids else None
                        ),
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
                    reputation = domain_reputation_service.get_reputation(
                        self.supabase, source.url or ""
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
                    triage.is_relevant and triage.confidence >= config.triage_threshold
                )

                # Record triage result for domain reputation stats (Task 2.7)
                try:
                    from urllib.parse import urlparse as _urlparse

                    _domain = _urlparse(source.url or "").netloc
                    if _domain:
                        domain_reputation_service.record_triage_result(
                            self.supabase, _domain, passed=passed_triage
                        )
                except Exception as e:
                    logger.debug(f"Domain triage recording failed (non-fatal): {e}")

                if passed_triage:
                    # Full analysis
                    analysis = await self.ai_service.analyze_source(
                        title=source.title,
                        content=source.content or "",
                        source_name=source.source_name,
                        published_at=datetime.now().isoformat(),
                    )

                    # Generate embedding
                    embed_text = f"{source.title} {analysis.summary}"
                    embedding = await self.ai_service.generate_embedding(embed_text)

                    processed.append(
                        ProcessedSource(
                            raw=source,
                            triage=triage,
                            analysis=analysis,
                            embedding=embedding,
                        )
                    )
            except Exception as e:
                logger.warning(f"Triage failed for {source.url}: {e}")
                continue

        if validation_skipped > 0:
            logger.info(
                f"Source validation filtered {validation_skipped}/{len(sources)} sources"
            )
        if preprint_count > 0:
            logger.info(
                f"Pre-print detection: {preprint_count} pre-prints detected in {len(sources)} sources"
            )

        return processed

    async def _deduplicate(
        self, sources: List[ProcessedSource], config: WorkstreamScanConfig
    ) -> Tuple[List[ProcessedSource], List[Tuple[ProcessedSource, str, float]], int]:
        """
        Deduplicate against existing cards.

        Returns: (unique_sources, enrichment_candidates, duplicate_count)
        """
        unique = []
        enrichments = []
        duplicate_count = 0

        for source in sources:
            try:
                # Check URL — only skip if this exact URL is already linked
                # to a card in THIS workstream (not globally across all cards).
                url_check = (
                    self.supabase.table("sources")
                    .select("id, card_id")
                    .eq("url", source.raw.url)
                    .execute()
                )

                if url_check.data:
                    # Check if any of these source cards are already in the workstream
                    existing_card_ids = {r["card_id"] for r in url_check.data}
                    ws_cards = (
                        self.supabase.table("workstream_cards")
                        .select("card_id")
                        .eq("workstream_id", config.workstream_id)
                        .in_("card_id", list(existing_card_ids))
                        .execute()
                    )
                    if ws_cards.data:
                        duplicate_count += 1
                        continue

                # Vector similarity check
                if source.embedding:
                    match_result = self.supabase.rpc(
                        "find_similar_cards",
                        {
                            "query_embedding": source.embedding,
                            "match_threshold": 0.75,
                            "match_count": 3,
                        },
                    ).execute()

                    if match_result.data:
                        top_match = match_result.data[0]
                        similarity = top_match.get("similarity", 0)

                        if similarity >= config.similarity_threshold:
                            # Strong match - enrich
                            enrichments.append((source, top_match["id"], similarity))
                            continue

                # New unique source
                unique.append(source)

            except Exception as e:
                logger.warning(f"Dedup error: {e}")
                unique.append(source)  # On error, treat as unique

        return unique, enrichments, duplicate_count

    async def _create_card(
        self, source: ProcessedSource, config: WorkstreamScanConfig
    ) -> Optional[str]:
        """Create a new card from a processed source."""
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

        # Map stage and goal
        stage_id = STAGE_NUMBER_TO_ID.get(analysis.suggested_stage, "4_proof")
        goal_id = convert_goal_id(analysis.goals[0]) if analysis.goals else None

        try:
            now = datetime.now().isoformat()

            result = (
                self.supabase.table("cards")
                .insert(
                    {
                        "name": analysis.suggested_card_name,
                        "slug": slug,
                        "summary": analysis.summary,
                        "horizon": analysis.horizon,
                        "stage_id": stage_id,
                        "pillar_id": (
                            convert_pillar_id(analysis.pillars[0])
                            if analysis.pillars
                            else None
                        ),
                        "goal_id": goal_id,
                        "maturity_score": int(analysis.credibility * 20),
                        "novelty_score": int(analysis.novelty * 20),
                        "impact_score": int(analysis.impact * 20),
                        "relevance_score": int(analysis.relevance * 20),
                        "velocity_score": int(analysis.velocity * 10),
                        "risk_score": int(analysis.risk * 10),
                        "status": "active",  # Workstream scans create active cards
                        "review_status": "pending_review",  # FIX-C2: Require human review
                        "discovered_at": now,
                        "discovery_metadata": {
                            "source": "workstream_scan",
                            "workstream_id": config.workstream_id,
                            "scan_id": config.scan_id,
                            "source_url": source.raw.url,
                            "source_title": source.raw.title,
                        },
                        "created_by": config.user_id,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
                .execute()
            )

            if result.data:
                card_id = result.data[0]["id"]

                # Store embedding on both cards.embedding (for find_similar_cards RPC)
                # and card_embeddings table (for consistency with other services)
                if source.embedding:
                    try:
                        self.supabase.table("cards").update(
                            {"embedding": source.embedding}
                        ).eq("id", card_id).execute()
                    except Exception as emb_err:
                        logger.warning(f"Failed to store embedding on card: {emb_err}")

                    try:
                        self.supabase.table("card_embeddings").upsert(
                            {
                                "card_id": card_id,
                                "embedding": source.embedding,
                                "created_at": now,
                            }
                        ).execute()
                    except Exception as emb_err:
                        logger.warning(f"Failed to store card_embedding: {emb_err}")

                # Store source
                await self._store_source_to_card(source, card_id)

                return card_id
        except Exception as e:
            logger.error(f"Card creation failed: {e}")
            raise

        return None

    async def _store_source_to_card(
        self, source: ProcessedSource, card_id: str
    ) -> Optional[str]:
        """Store source record linked to card."""
        try:
            # Look up domain reputation ID for this source (Task 2.7)
            _domain_reputation_id = None
            try:
                _rep = domain_reputation_service.get_reputation(
                    self.supabase, source.raw.url or ""
                )
                if _rep:
                    _domain_reputation_id = _rep.get("id")
            except Exception:
                pass  # Non-fatal

            source_record = {
                "card_id": card_id,
                "url": source.raw.url,
                "title": (source.raw.title or "Untitled")[:500],
                "publication": (
                    (source.raw.source_name or "")[:200]
                    if source.raw.source_name
                    else None
                ),
                "full_text": (
                    source.raw.content[:10000] if source.raw.content else None
                ),
                "ai_summary": (source.analysis.summary if source.analysis else None),
                "relevance_to_card": (
                    source.triage.confidence if source.triage else 0.5
                ),
                # Pre-print / peer-review status (Task 2.6)
                "is_peer_reviewed": (
                    False
                    if getattr(source.raw, "is_preprint", False)
                    else (
                        True
                        if getattr(source.raw, "source_type", None) == "academic"
                        else None
                    )
                ),
                "api_source": "workstream_scan",
                "ingested_at": datetime.now().isoformat(),
            }

            # Add domain_reputation_id if available (Task 2.7)
            if _domain_reputation_id:
                source_record["domain_reputation_id"] = _domain_reputation_id

            result = self.supabase.table("sources").insert(source_record).execute()

            if result.data:
                return result.data[0]["id"]
        except Exception as e:
            logger.warning(f"Source storage failed: {e}")

        return None

    async def _add_to_workstream(
        self, workstream_id: str, card_id: str, user_id: str
    ) -> bool:
        """Add card to workstream inbox if not already present."""
        try:
            # Check if already in workstream
            existing = (
                self.supabase.table("workstream_cards")
                .select("id")
                .eq("workstream_id", workstream_id)
                .eq("card_id", card_id)
                .execute()
            )

            if existing.data:
                return False  # Already in workstream

            # Add to inbox
            result = (
                self.supabase.table("workstream_cards")
                .insert(
                    {
                        "workstream_id": workstream_id,
                        "card_id": card_id,
                        "added_by": user_id,
                        "status": "inbox",
                        "position": 0,
                        "added_from": "workstream_scan",
                        "created_at": datetime.now().isoformat(),
                    }
                )
                .execute()
            )

            return bool(result.data)
        except Exception as e:
            logger.warning(f"Add to workstream failed: {e}")
            return False

    async def _update_scan_status(
        self,
        scan_id: str,
        status: str,
        started_at: Optional[datetime] = None,
        error_message: Optional[str] = None,
    ):
        """Update scan record status."""
        try:
            update_data = {"status": status}
            if started_at:
                update_data["started_at"] = started_at.isoformat()
            if error_message:
                update_data["error_message"] = error_message

            self.supabase.table("workstream_scans").update(update_data).eq(
                "id", scan_id
            ).execute()
        except Exception as e:
            logger.warning(f"Failed to update scan status: {e}")

    async def _finalize_scan(self, scan_id: str, result: ScanResult):
        """Finalize scan record with results."""
        try:
            self.supabase.table("workstream_scans").update(
                {
                    "status": result.status,
                    "completed_at": (
                        result.completed_at.isoformat() if result.completed_at else None
                    ),
                    "results": {
                        "queries_executed": result.queries_executed,
                        "sources_fetched": result.sources_fetched,
                        "sources_by_category": result.sources_by_category,
                        "sources_triaged": result.sources_triaged,
                        "cards_created": len(result.cards_created),
                        "cards_enriched": len(result.cards_enriched),
                        "cards_added_to_workstream": len(
                            result.cards_added_to_workstream
                        ),
                        "duplicates_skipped": result.duplicates_skipped,
                        "execution_time_seconds": result.execution_time_seconds,
                        "errors": result.errors,
                    },
                    "error_message": result.errors[0] if result.errors else None,
                }
            ).eq("id", scan_id).execute()
        except Exception as e:
            logger.warning(f"Failed to finalize scan: {e}")
