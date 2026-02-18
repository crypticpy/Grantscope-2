"""
Workstream Targeted Scan Service.

A lightweight, focused discovery service that scans for grant opportunities
relevant to a user's workstream (program) based on its keywords, pillars,
and grant type settings.

Key differences from broad discovery:
- Queries generated purely from workstream metadata (no default topic clamping)
- Lighter resource limits (fewer queries, sources, cards)
- Discovered cards go to global pool AND auto-added to user's workstream inbox
- Rate limited to 10 scans per workstream per day

Usage:
    from app.workstream_scan_service import WorkstreamScanService, WorkstreamScanConfig

    config = WorkstreamScanConfig(
        workstream_id="uuid",
        user_id="uuid",
        keywords=["HUD housing grants", "CDBG funding"],
        pillar_ids=["HH"],
        horizon="H2"
    )
    service = WorkstreamScanService(db, openai_client)
    result = await service.execute_scan(config)
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta, timezone
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
import uuid

from sqlalchemy import func, select, text
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
import openai

from app.helpers.db_utils import vector_search_cards
from app.models.db.card import Card, CardEmbedding
from app.models.db.source import Source
from app.models.db.workstream import WorkstreamCard, WorkstreamScan

from .ai_service import AIService, AnalysisResult, TriageResult
from .research_service import RawSource, ProcessedSource
from .source_validator import SourceValidator
from . import domain_reputation_service
from .openai_provider import get_chat_mini_deployment
from .source_fetchers import (
    fetch_rss_sources,
    fetch_news_articles,
    fetch_academic_papers,
    fetch_government_sources,
    fetch_tech_blog_articles,
    convert_to_raw_source as convert_academic_to_raw,
    convert_government_to_raw_source,
)
from .search_provider import (
    search_all as serper_search_all,
    is_available as serper_available,
    SearchResult,
)
from .content_enricher import enrich_sources

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
        db: AsyncSession,
        openai_client: openai.OpenAI,
    ):
        self.db = db
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
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            result = await self.db.execute(
                select(WorkstreamScan.id)
                .where(WorkstreamScan.workstream_id == config.workstream_id)
                .where(WorkstreamScan.created_at >= cutoff)
            )
            scan_count = len(result.all())
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
                    completed_at=datetime.now(timezone.utc),
                )
        except Exception as e:
            logger.warning(f"Rate limit check failed, proceeding with scan: {e}")

        start_time = datetime.now(timezone.utc)
        scan_result = ScanResult(
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

            # Step 1: Generate queries (AI-powered with static fallback)
            queries = await self._generate_queries_with_ai(config)
            scan_result.queries_executed = len(queries)
            logger.info(f"Generated {len(queries)} queries for workstream scan")

            # Step 2: Fetch sources (Serper primary, RSS + academic supplementary)
            raw_sources, sources_by_category = await self._fetch_sources(
                queries, config, workstream_id=config.workstream_id
            )
            scan_result.sources_fetched = len(raw_sources)
            scan_result.sources_by_category = sources_by_category
            logger.info(f"Fetched {len(raw_sources)} sources across categories")

            if not raw_sources:
                scan_result.status = "completed"
                scan_result.completed_at = datetime.now(timezone.utc)
                scan_result.execution_time_seconds = (
                    scan_result.completed_at - start_time
                ).total_seconds()
                await self._finalize_scan(config.scan_id, scan_result)
                return scan_result

            logger.info(f"Enriching {len(raw_sources)} sources with full content...")
            raw_sources = await enrich_sources(raw_sources, max_concurrent=5)

            # Step 2c: Preload domain reputation cache (Task 2.7)
            try:
                source_urls = [s.url for s in raw_sources if s.url]
                domain_reputation_service.get_reputation_batch(self.db, source_urls)
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
            scan_result.sources_triaged = len(processed_sources)
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
                scan_result.status = "completed"
                scan_result.completed_at = datetime.now(timezone.utc)
                scan_result.execution_time_seconds = (
                    scan_result.completed_at - start_time
                ).total_seconds()
                await self._finalize_scan(config.scan_id, scan_result)
                return scan_result

            # Step 4: Deduplicate
            logger.info(
                f"Starting deduplication of {len(processed_sources)} sources..."
            )
            unique_sources, enrichment_candidates, duplicates = await self._deduplicate(
                processed_sources, config
            )
            scan_result.duplicates_skipped = duplicates
            logger.info(
                f"Dedup complete: {len(unique_sources)} unique, "
                f"{len(enrichment_candidates)} enrichments, {duplicates} duplicates"
            )

            # Step 5: Process enrichments
            for source, card_id, similarity in enrichment_candidates:
                try:
                    source_id = await self._store_source_to_card(source, card_id)
                    if source_id and card_id not in scan_result.cards_enriched:
                        scan_result.cards_enriched.append(card_id)
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
                        scan_result.cards_created.append(card_id)
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
                    scan_result.errors.append(f"Card creation failed: {str(e)[:100]}")

            if sources_without_analysis > 0:
                logger.warning(
                    f"Skipped {sources_without_analysis} sources without analysis"
                )

            # Step 7: Auto-add to workstream inbox
            if config.auto_add_to_workstream:
                all_card_ids = scan_result.cards_created + scan_result.cards_enriched
                for card_id in all_card_ids:
                    try:
                        added = await self._add_to_workstream(
                            config.workstream_id, card_id, config.user_id
                        )
                        if added:
                            scan_result.cards_added_to_workstream.append(card_id)
                    except Exception as e:
                        logger.warning(
                            f"Failed to add card {card_id} to workstream: {e}"
                        )

            scan_result.status = "completed"

        except Exception as e:
            logger.exception(f"Workstream scan failed: {e}")
            scan_result.status = "failed"
            scan_result.errors.append(str(e))

        scan_result.completed_at = datetime.now(timezone.utc)
        scan_result.execution_time_seconds = (
            scan_result.completed_at - start_time
        ).total_seconds()
        await self._finalize_scan(config.scan_id, scan_result)

        return scan_result

    async def _get_workstream_context(
        self, config: WorkstreamScanConfig
    ) -> Tuple[List[str], Optional[str]]:
        """
        Fetch existing card names in this workstream and the last scan date.

        Returns:
            (existing_card_names, last_scan_completed_at_iso)
        """
        existing_names: List[str] = []
        last_scan_date: Optional[str] = None

        try:
            # Get card names already in this workstream
            ws_result = await self.db.execute(
                select(WorkstreamCard.card_id).where(
                    WorkstreamCard.workstream_id == config.workstream_id
                )
            )
            card_ids = [str(row.card_id) for row in ws_result.all()]

            if card_ids:
                # Fetch names in batches (cap to avoid huge queries)
                cards_result = await self.db.execute(
                    select(Card.name).where(Card.id.in_(card_ids[:50]))
                )
                existing_names = [row.name for row in cards_result.all()]

            # Get the last completed scan for this workstream
            last_scan_result = await self.db.execute(
                select(WorkstreamScan.completed_at)
                .where(WorkstreamScan.workstream_id == config.workstream_id)
                .where(WorkstreamScan.status == "completed")
                .order_by(WorkstreamScan.completed_at.desc())
                .limit(1)
            )
            row = last_scan_result.first()
            if row and row.completed_at:
                last_scan_date = row.completed_at.isoformat()

        except Exception as e:
            logger.warning(f"Failed to fetch workstream context: {e}")

        return existing_names, last_scan_date

    async def _generate_queries_with_ai(
        self, config: WorkstreamScanConfig
    ) -> List[str]:
        """
        Generate diverse, grant-focused search queries using the LLM.

        Context-aware: looks at existing cards in the workstream to avoid
        re-searching known grant opportunities, and uses the last scan date
        to narrow the time window for subsequent scans.
        """
        # Build context strings for the prompt
        keywords_str = (
            ", ".join(config.keywords)
            if config.keywords
            else "general grant opportunities city government"
        )
        pillar_names = [PILLAR_NAMES.get(pid, pid) for pid in config.pillar_ids]
        pillar_str = ", ".join(pillar_names) if pillar_names else "all categories"

        horizon_descriptions = {
            "H1": "Active grants — currently open NOFOs and RFPs accepting applications",
            "H2": "Upcoming grants — recurring programs expected to open, anticipated funding",
            "H3": "Emerging funding — new legislation, proposed programs, new funding sources",
            "ALL": "All grant types — active, upcoming, and emerging funding opportunities",
        }
        horizon_desc = horizon_descriptions.get(
            config.horizon, horizon_descriptions["ALL"]
        )

        today_str = date.today().isoformat()

        # Fetch what's already in the workstream
        existing_names, last_scan_date = await self._get_workstream_context(config)

        # Build context about existing coverage
        existing_context = ""
        if existing_names:
            names_sample = existing_names[:15]
            existing_context = f"""
Grant opportunities already tracked (DO NOT search for these — find NEW, DIFFERENT opportunities):
{chr(10).join(f'- {name}' for name in names_sample)}
{f'... and {str(len(existing_names) - 15)} more' if len(existing_names) > 15 else ''}
"""

        # Determine scan mode: seed (no cards yet) vs follow-up (has cards)
        # Using card count rather than scan history handles edge cases:
        # - Scan ran but found 0 cards -> still seed mode (need broad search)
        # - Cards manually added, no scan ever ran -> follow-up mode (have context)
        is_seed = len(existing_names) == 0
        scan_mode_hint = ""
        if is_seed:
            scan_mode_hint = (
                "\nThis is a SEED scan — the program has no grant opportunities tracked yet. "
                "Cast a WIDE net: search for active NOFOs, recently closed grants (to track "
                "recurring cycles), major federal programs, state programs, and foundation "
                "grants. Include queries for grants.gov, SAM.gov, and specific agency "
                "grant pages. Mix broad grant searches with agency-specific queries."
            )
        elif last_scan_date:
            scan_mode_hint = (
                f"\nThis is a FOLLOW-UP scan (last scan: {last_scan_date}). "
                f"Focus on finding grant opportunities announced or updated AFTER that date. "
                f"Look for new NOFOs, updated deadlines, newly available funding, "
                f"and recently announced grant programs we haven't covered yet."
            )
        else:
            scan_mode_hint = (
                "\nThis program has tracked opportunities but no prior scan history. "
                "Focus on finding recently announced grants (past few weeks) that "
                "complement what's already tracked."
            )

        prompt = f"""You are a grant research specialist for the City of Austin, Texas municipal government.

Generate 10-12 diverse Google search queries to discover NEW grant funding opportunities.

Program context:
- Keywords: {keywords_str}
- Focus areas: {pillar_str}
- Grant type focus: {horizon_desc}
- Today's date: {today_str}
{scan_mode_hint}
{existing_context}
Requirements:
- Each query should find DIFFERENT grant opportunities (vary agencies, programs, funding types)
- Include grant-specific terms: "NOFO", "RFP", "grant", "funding opportunity", "notice of funding"
- Search across federal agencies (HUD, DOT, EPA, DOJ, HHS, FEMA, DOE, EDA, USDA, etc.)
- Include state-level grants (Texas state agencies, TCEQ, TxDOT, TWC, etc.)
- Include foundation and private grants where relevant
- Search grants.gov, SAM.gov, and agency-specific grant pages
- Include fiscal year and deadline-related terms (e.g., "FY2026", "deadline 2026")
- Don't just prepend/append the same modifiers — target specific grant programs by name
- Avoid queries that would return opportunities we already track (see list above)
- Think about related grant programs, matching funds, and cross-agency opportunities

Return ONLY a JSON array of query strings, no other text.
Example: ["query 1", "query 2", ...]"""

        try:
            model = get_chat_mini_deployment()
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.9,
                max_tokens=1000,
            )

            raw_text = response.choices[0].message.content.strip()

            # Parse the JSON array from the response
            # Handle cases where the model wraps in markdown code blocks
            if raw_text.startswith("```"):
                raw_text = raw_text.strip("`").strip()
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:].strip()

            queries = json.loads(raw_text)

            if not isinstance(queries, list) or len(queries) == 0:
                raise ValueError(f"Expected non-empty JSON array, got: {type(queries)}")

            # Filter to strings only and limit
            queries = [q for q in queries if isinstance(q, str) and q.strip()]
            queries = queries[: config.max_queries]

            logger.info(
                f"AI query generation produced {len(queries)} queries for workstream "
                f"{config.workstream_id} (keywords: {keywords_str[:60]}, "
                f"existing_cards: {len(existing_names)}, "
                f"mode: {'follow-up' if last_scan_date else 'seed'})"
            )
            return queries

        except Exception as e:
            logger.warning(
                f"AI query generation failed, falling back to static method: {e}"
            )
            return self._generate_queries_static(config)

    def _generate_queries_static(self, config: WorkstreamScanConfig) -> List[str]:
        """
        Generate grant search queries from workstream metadata (static/fallback method).

        No default topic clamping - queries are purely workstream-driven.
        Used as a fallback when AI-powered query generation fails.
        """
        queries = []

        # Base modifiers for grant discovery context
        grant_modifiers = [
            "grants city government",
            "federal grants municipal",
            "funding opportunity NOFO",
            "grant program local government",
            "state grants Texas city",
        ]

        # Grant-type-specific modifiers (mapped from horizon)
        grant_type_modifiers = {
            "H1": [
                "NOFO open",
                "grant application deadline 2026",
                "accepting applications",
                "FY2026",
            ],
            "H2": ["grant program", "annual funding", "recurring grants", "2025 2026"],
            "H3": [
                "new grant program",
                "proposed funding",
                "legislation grants",
                "appropriations",
            ],
            "ALL": ["grants funding", "NOFO grant program"],
        }

        grant_mods = grant_type_modifiers.get(
            config.horizon, grant_type_modifiers["ALL"]
        )

        # Generate queries from keywords
        for keyword in config.keywords[:10]:  # Limit keywords
            queries.extend(
                (
                    f'"{keyword}" {grant_modifiers[0]}',
                    f"{keyword} {grant_mods[0]}",
                )
            )
            # Keyword with pillar context
            for pillar_id in config.pillar_ids[:2]:  # Limit pillars
                if pillar_name := PILLAR_NAMES.get(pillar_id, ""):
                    queries.append(f"{keyword} {pillar_name} grants")

        # Add pillar-specific grant queries if few keywords
        if len(config.keywords) < 3:
            for pillar_id in config.pillar_ids:
                if pillar_name := PILLAR_NAMES.get(pillar_id, ""):
                    queries.extend(
                        (
                            f"{pillar_name} {grant_mods[0]} city government",
                            f"{pillar_name} federal grants municipal",
                        )
                    )
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
        self,
        queries: List[str],
        config: WorkstreamScanConfig,
        workstream_id: Optional[str] = None,
    ) -> Tuple[List[RawSource], Dict[str, int]]:
        """
        Fetch sources using Serper as the primary backend, with RSS and
        academic (arXiv) as supplementary free sources.

        Automatically narrows the date filter for follow-up scans:
        - First scan (seed): past month for broad coverage
        - Follow-up within a week: past week
        - Follow-up within a day: past day

        Falls back to the old multi-scraper approach if Serper is not available.
        """
        all_sources: List[RawSource] = []
        sources_by_category: Dict[str, int] = {}

        # Inject extra keywords from source_preferences into queries
        extra_keywords = (
            config.source_preferences.get("keywords", [])
            if config.source_preferences
            else []
        )
        all_queries = list(queries)
        if extra_keywords:
            all_queries = list(set(all_queries + extra_keywords[:3]))

        if serper_available():
            # ----------------------------------------------------------
            # PRIMARY PATH: Serper.dev Google Search + News
            # ----------------------------------------------------------

            # Determine date filter based on workstream state:
            #
            # SEED scan (no cards yet):
            #   No date filter -- find everything available on this topic,
            #   including historical articles, landmark reports, foundational
            #   research. Some topics have years of relevant history.
            #
            # FOLLOW-UP scan (has cards, progressively narrow):
            #   < 2 days since last scan  -> past day   (qdr:d)
            #   2-7 days since last scan  -> past week  (qdr:w)
            #   8-30 days since last scan -> past month  (qdr:m)
            #   31-365 days since last    -> past year   (qdr:y)
            #   > 1 year or no prior scan -> past year   (qdr:y)
            #
            date_filter: Optional[str] = None  # None = no date restriction
            has_cards = False
            try:
                if workstream_id:
                    # Check if the workstream has any cards (determines seed vs follow-up)
                    card_count_result = await self.db.execute(
                        select(func.count(WorkstreamCard.id)).where(
                            WorkstreamCard.workstream_id == workstream_id
                        )
                    )
                    count_val = card_count_result.scalar() or 0
                    has_cards = count_val > 0

                    if has_cards:
                        # Follow-up mode: narrow based on last successful scan
                        last_scan_result = await self.db.execute(
                            select(WorkstreamScan.completed_at)
                            .where(WorkstreamScan.workstream_id == workstream_id)
                            .where(WorkstreamScan.status == "completed")
                            .order_by(WorkstreamScan.completed_at.desc())
                            .limit(1)
                        )
                        last_scan_row = last_scan_result.first()
                        if last_scan_row and last_scan_row.completed_at:
                            last_completed = last_scan_row.completed_at
                            try:
                                last_dt = last_completed
                                if last_dt.tzinfo is None:
                                    from datetime import timezone as tz

                                    last_dt = last_dt.replace(tzinfo=tz.utc)
                                days_since = (
                                    datetime.now(last_dt.tzinfo) - last_dt
                                ).days
                                if days_since <= 1:
                                    date_filter = "qdr:d"
                                elif days_since <= 7:
                                    date_filter = "qdr:w"
                                elif days_since <= 30:
                                    date_filter = "qdr:m"
                                else:
                                    date_filter = "qdr:y"
                            except (ValueError, TypeError):
                                date_filter = "qdr:y"
                        else:
                            # Has cards but no completed scan (cards added manually)
                            date_filter = "qdr:m"
                    # else: seed scan -- date_filter stays None (no restriction)

            except Exception as e:
                logger.warning(f"Date filter lookup failed, using no filter: {e}")

            filter_label = date_filter or "none (seed scan)"
            logger.info(f"Smart date filter: has_cards={has_cards} -> {filter_label}")

            try:
                serper_results: List[SearchResult] = await serper_search_all(
                    all_queries,
                    num_results_per_query=10,
                    date_filter=date_filter,
                )
                serper_sources = [
                    RawSource(
                        url=result.url,
                        title=result.title,
                        content=result.snippet,
                        source_name=result.source_name or "Google Search",
                        published_at=result.date,
                    )
                    for result in serper_results
                ]
                all_sources.extend(serper_sources)
                sources_by_category["serper"] = len(serper_sources)
                logger.info(
                    f"Serper: {len(serper_sources)} sources from {len(all_queries)} queries"
                )
            except Exception as e:
                logger.warning(f"Serper fetch failed: {e}", exc_info=True)
                sources_by_category["serper"] = 0

            # SUPPLEMENTARY: RSS feeds (free)
            try:
                rss_sources = await self._fetch_rss(
                    all_queries, config.max_sources_per_category
                )
                all_sources.extend(rss_sources)
                sources_by_category["rss"] = len(rss_sources)
                logger.info(f"RSS (supplementary): {len(rss_sources)} sources")
            except Exception as e:
                logger.warning(f"RSS fetch failed: {e}", exc_info=True)
                sources_by_category["rss"] = 0

            # SUPPLEMENTARY: Academic / arXiv (free)
            try:
                academic_sources = await self._fetch_academic(
                    all_queries, config.max_sources_per_category
                )
                all_sources.extend(academic_sources)
                sources_by_category["academic"] = len(academic_sources)
                logger.info(
                    f"Academic (supplementary): {len(academic_sources)} sources"
                )
            except Exception as e:
                logger.warning(f"Academic fetch failed: {e}", exc_info=True)
                sources_by_category["academic"] = 0

        else:
            # ----------------------------------------------------------
            # FALLBACK PATH: Old multi-scraper approach (no Serper key)
            # ----------------------------------------------------------
            logger.warning(
                "SERPER_API_KEY not set — falling back to legacy scraper sources"
            )
            # Use only first 5 queries for scraping (rate-limit friendly)
            query_subset = all_queries[:5]

            for category, fetcher in [
                ("news", lambda qs, lim: self._fetch_news(qs, lim)),
                ("tech_blog", lambda qs, lim: self._fetch_tech_blogs(qs, lim)),
                ("academic", lambda qs, lim: self._fetch_academic(qs, lim)),
                ("government", lambda qs, lim: self._fetch_government(qs, lim)),
                ("rss", lambda qs, lim: self._fetch_rss(qs, lim)),
            ]:
                try:
                    cat_sources = await fetcher(
                        query_subset, config.max_sources_per_category
                    )
                    all_sources.extend(cat_sources)
                    sources_by_category[category] = len(cat_sources)
                    logger.info(f"{category}: {len(cat_sources)} sources")
                except Exception as e:
                    logger.warning(f"{category} fetch failed: {e}", exc_info=True)
                    sources_by_category[category] = 0

        logger.info(
            f"Total sources collected: {len(all_sources)} "
            f"(breakdown: {sources_by_category})"
        )
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
            sources.extend(
                RawSource(
                    url=article.url,
                    title=article.title,
                    content=article.content or article.summary or "",
                    source_name=article.feed_title or "RSS",
                    published_at=article.published_at,
                )
                for article in result.articles[:limit]
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
                    triage.is_relevant and triage.confidence >= config.triage_threshold
                )

                # Record triage result for domain reputation stats (Task 2.7)
                try:
                    from urllib.parse import urlparse as _urlparse

                    if _domain := _urlparse(source.url or "").netloc:
                        domain_reputation_service.record_triage_result(
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
                # Check URL -- only skip if this exact URL is already linked
                # to a card in THIS workstream (not globally across all cards).
                url_result = await self.db.execute(
                    select(Source.id, Source.card_id).where(
                        Source.url == source.raw.url
                    )
                )
                url_rows = url_result.all()

                if url_rows:
                    # Check if any of these source cards are already in the workstream
                    existing_card_ids = [str(r.card_id) for r in url_rows if r.card_id]
                    if existing_card_ids:
                        ws_result = await self.db.execute(
                            select(WorkstreamCard.card_id)
                            .where(WorkstreamCard.workstream_id == config.workstream_id)
                            .where(WorkstreamCard.card_id.in_(existing_card_ids))
                        )
                        if ws_result.first():
                            duplicate_count += 1
                            continue

                # Vector similarity check
                if source.embedding:
                    matches = await vector_search_cards(
                        self.db,
                        source.embedding,
                        match_threshold=0.75,
                        match_count=3,
                    )

                    if matches:
                        top_match = matches[0]
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
        existing_result = await self.db.execute(
            select(Card.id).where(Card.slug == slug)
        )
        if existing_result.first():
            slug = f"{slug}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        # Map stage and goal
        stage_id = STAGE_NUMBER_TO_ID.get(analysis.suggested_stage, "4_proof")
        goal_id = convert_goal_id(analysis.goals[0]) if analysis.goals else None

        try:
            now = datetime.now(timezone.utc)

            card = Card(
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
                status="active",  # Workstream scans create active cards
                review_status="pending_review",  # FIX-C2: Require human review
                discovered_at=now,
                discovery_metadata={
                    "source": "workstream_scan",
                    "workstream_id": config.workstream_id,
                    "scan_id": config.scan_id,
                    "source_url": source.raw.url,
                    "source_title": source.raw.title,
                },
                created_by=config.user_id,
                created_at=now,
                updated_at=now,
            )
            self.db.add(card)
            await self.db.flush()

            card_id = str(card.id)

            # Store embedding on both cards.embedding (for find_similar_cards RPC)
            # and card_embeddings table (for consistency with other services)
            if source.embedding:
                try:
                    embedding_str = (
                        "[" + ",".join(str(v) for v in source.embedding) + "]"
                    )
                    await self.db.execute(
                        text(
                            "UPDATE cards SET embedding = :emb::vector WHERE id = :cid"
                        ),
                        {"emb": embedding_str, "cid": card_id},
                    )
                    await self.db.flush()
                except Exception as emb_err:
                    logger.warning(f"Failed to store embedding on card: {emb_err}")

                try:
                    stmt = (
                        pg_insert(CardEmbedding)
                        .values(
                            card_id=card_id,
                            created_at=now,
                        )
                        .on_conflict_do_update(
                            index_elements=["card_id"],
                            set_={"updated_at": now},
                        )
                    )
                    # Store embedding via raw SQL since CardEmbedding.embedding is NullType
                    await self.db.execute(
                        text(
                            "INSERT INTO card_embeddings (card_id, embedding, created_at) "
                            "VALUES (:card_id, :emb::vector, :created_at) "
                            "ON CONFLICT (card_id) DO UPDATE SET "
                            "embedding = :emb::vector, updated_at = :updated_at"
                        ),
                        {
                            "card_id": card_id,
                            "emb": embedding_str,
                            "created_at": now,
                            "updated_at": now,
                        },
                    )
                    await self.db.flush()
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
                if _rep := domain_reputation_service.get_reputation(
                    self.db, source.raw.url or ""
                ):
                    _domain_reputation_id = _rep.get("id")
            except Exception:
                pass  # Non-fatal

            source_obj = Source(
                card_id=card_id,
                url=source.raw.url,
                title=(source.raw.title or "Untitled")[:500],
                publication=(
                    (source.raw.source_name or "")[:200]
                    if source.raw.source_name
                    else None
                ),
                full_text=(source.raw.content[:10000] if source.raw.content else None),
                ai_summary=(source.analysis.summary if source.analysis else None),
                relevance_to_card=(source.triage.confidence if source.triage else 0.5),
                # Pre-print / peer-review status (Task 2.6)
                is_peer_reviewed=(
                    False
                    if getattr(source.raw, "is_preprint", False)
                    else (
                        True
                        if getattr(source.raw, "source_type", None) == "academic"
                        else None
                    )
                ),
                api_source="workstream_scan",
                ingested_at=datetime.now(timezone.utc),
            )

            # Add domain_reputation_id if available (Task 2.7)
            if _domain_reputation_id:
                source_obj.domain_reputation_id = _domain_reputation_id

            self.db.add(source_obj)
            await self.db.flush()

            return str(source_obj.id)
        except Exception as e:
            logger.warning(f"Source storage failed: {e}")

        return None

    async def _add_to_workstream(
        self, workstream_id: str, card_id: str, user_id: str
    ) -> bool:
        """Add card to workstream inbox if not already present."""
        try:
            # Check if already in workstream
            existing_result = await self.db.execute(
                select(WorkstreamCard.id)
                .where(WorkstreamCard.workstream_id == workstream_id)
                .where(WorkstreamCard.card_id == card_id)
            )

            if existing_result.first():
                return False  # Already in workstream

            # Add to inbox
            ws_card = WorkstreamCard(
                workstream_id=workstream_id,
                card_id=card_id,
                added_by=user_id,
                status="inbox",
                position=0,
                added_from="workstream_scan",
                added_at=datetime.now(timezone.utc),
            )
            self.db.add(ws_card)
            await self.db.flush()

            return True
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
            values: Dict[str, Any] = {"status": status}
            if started_at:
                values["started_at"] = started_at
            if error_message:
                values["error_message"] = error_message

            await self.db.execute(
                sa_update(WorkstreamScan)
                .where(WorkstreamScan.id == scan_id)
                .values(**values)
            )
            await self.db.flush()
        except Exception as e:
            logger.warning(f"Failed to update scan status: {e}")

    async def _finalize_scan(self, scan_id: str, result: ScanResult):
        """Finalize scan record with results."""
        try:
            await self.db.execute(
                sa_update(WorkstreamScan)
                .where(WorkstreamScan.id == scan_id)
                .values(
                    status=result.status,
                    completed_at=result.completed_at,
                    results={
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
                    error_message=result.errors[0] if result.errors else None,
                )
            )
            await self.db.flush()
        except Exception as e:
            logger.warning(f"Failed to finalize scan: {e}")
