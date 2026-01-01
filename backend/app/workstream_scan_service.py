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
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
import uuid

from supabase import Client
import openai

from .ai_service import AIService, AnalysisResult, TriageResult
from .research_service import RawSource, ProcessedSource
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
        1. Generate queries from workstream keywords + pillars
        2. Fetch from all 5 source categories
        3. Triage and analyze sources
        4. Deduplicate against existing cards
        5. Create new cards (global pool)
        6. Auto-add to workstream inbox
        """
        start_time = datetime.now()
        result = ScanResult(
            scan_id=config.scan_id,
            workstream_id=config.workstream_id,
            status="running",
            started_at=start_time,
        )
        
        try:
            # Update scan status to running
            await self._update_scan_status(config.scan_id, "running", started_at=start_time)
            
            # Step 1: Generate queries
            queries = self._generate_queries(config)
            result.queries_executed = len(queries)
            logger.info(f"Generated {len(queries)} queries for workstream scan")
            
            # Step 2: Fetch sources from all categories
            raw_sources, sources_by_category = await self._fetch_sources(queries, config)
            result.sources_fetched = len(raw_sources)
            result.sources_by_category = sources_by_category
            logger.info(f"Fetched {len(raw_sources)} sources across categories")
            
            if not raw_sources:
                result.status = "completed"
                result.completed_at = datetime.now()
                result.execution_time_seconds = (result.completed_at - start_time).total_seconds()
                await self._finalize_scan(config.scan_id, result)
                return result
            
            # Step 3: Triage and analyze
            processed_sources = await self._triage_and_analyze(raw_sources, config)
            result.sources_triaged = len(processed_sources)
            logger.info(f"Triaged {len(processed_sources)} relevant sources")
            
            if not processed_sources:
                result.status = "completed"
                result.completed_at = datetime.now()
                result.execution_time_seconds = (result.completed_at - start_time).total_seconds()
                await self._finalize_scan(config.scan_id, result)
                return result
            
            # Step 4: Deduplicate
            unique_sources, enrichment_candidates, duplicates = await self._deduplicate(
                processed_sources, config
            )
            result.duplicates_skipped = duplicates
            logger.info(
                f"Dedup: {len(unique_sources)} unique, "
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
            cards_created_count = 0
            for source in unique_sources:
                if cards_created_count >= config.max_new_cards:
                    break
                
                if not source.analysis:
                    continue
                
                try:
                    card_id = await self._create_card(source, config)
                    if card_id:
                        result.cards_created.append(card_id)
                        cards_created_count += 1
                        logger.info(f"Created card: {source.analysis.suggested_card_name}")
                except Exception as e:
                    logger.warning(f"Failed to create card: {e}")
                    result.errors.append(f"Card creation failed: {str(e)[:100]}")
            
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
                        logger.warning(f"Failed to add card {card_id} to workstream: {e}")
            
            result.status = "completed"
            
        except Exception as e:
            logger.exception(f"Workstream scan failed: {e}")
            result.status = "failed"
            result.errors.append(str(e))
        
        result.completed_at = datetime.now()
        result.execution_time_seconds = (result.completed_at - start_time).total_seconds()
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
        
        return unique_queries[:config.max_queries]
    
    async def _fetch_sources(
        self,
        queries: List[str],
        config: WorkstreamScanConfig
    ) -> Tuple[List[RawSource], Dict[str, int]]:
        """Fetch sources from all 5 categories."""
        all_sources = []
        sources_by_category = {
            "news": 0,
            "tech_blog": 0,
            "academic": 0,
            "government": 0,
            "rss": 0,
        }
        
        # Distribute queries across categories
        query_subset = queries[:5] if len(queries) >= 5 else queries
        
        try:
            # News articles
            news_sources = await self._fetch_news(query_subset, config.max_sources_per_category)
            all_sources.extend(news_sources)
            sources_by_category["news"] = len(news_sources)
        except Exception as e:
            logger.warning(f"News fetch failed: {e}")
        
        try:
            # Tech blogs
            tech_sources = await self._fetch_tech_blogs(query_subset, config.max_sources_per_category)
            all_sources.extend(tech_sources)
            sources_by_category["tech_blog"] = len(tech_sources)
        except Exception as e:
            logger.warning(f"Tech blog fetch failed: {e}")
        
        try:
            # Academic papers
            academic_sources = await self._fetch_academic(query_subset, config.max_sources_per_category)
            all_sources.extend(academic_sources)
            sources_by_category["academic"] = len(academic_sources)
        except Exception as e:
            logger.warning(f"Academic fetch failed: {e}")
        
        try:
            # Government sources
            gov_sources = await self._fetch_government(query_subset, config.max_sources_per_category)
            all_sources.extend(gov_sources)
            sources_by_category["government"] = len(gov_sources)
        except Exception as e:
            logger.warning(f"Government fetch failed: {e}")
        
        try:
            # RSS feeds
            rss_sources = await self._fetch_rss(query_subset, config.max_sources_per_category)
            all_sources.extend(rss_sources)
            sources_by_category["rss"] = len(rss_sources)
        except Exception as e:
            logger.warning(f"RSS fetch failed: {e}")
        
        return all_sources, sources_by_category
    
    async def _fetch_news(self, queries: List[str], limit: int) -> List[RawSource]:
        """Fetch news articles."""
        sources = []
        try:
            # fetch_news_articles expects topics as a list
            articles = await fetch_news_articles(topics=queries[:3], max_articles=limit)
            for article in articles:
                sources.append(RawSource(
                    url=article.url,
                    title=article.title,
                    content=article.content or article.description or "",
                    source_name=article.source or "News",
                    published_at=article.published_at,
                ))
        except Exception as e:
            logger.warning(f"News fetch error: {e}")
        return sources[:limit]
    
    async def _fetch_tech_blogs(self, queries: List[str], limit: int) -> List[RawSource]:
        """Fetch tech blog articles."""
        sources = []
        try:
            # fetch_tech_blog_articles expects topics as a list
            articles = await fetch_tech_blog_articles(topics=queries[:3], max_articles=limit)
            for article in articles:
                sources.append(RawSource(
                    url=article.url,
                    title=article.title,
                    content=article.content or article.summary or "",
                    source_name=article.source or "Tech Blog",
                    published_at=article.published_at,
                ))
        except Exception as e:
            logger.warning(f"Tech blog fetch error: {e}")
        return sources[:limit]
    
    async def _fetch_academic(self, queries: List[str], limit: int) -> List[RawSource]:
        """Fetch academic papers."""
        sources = []
        try:
            for query in queries[:2]:
                result = await fetch_academic_papers(query=query, max_results=limit // 2)
                # fetch_academic_papers returns AcademicFetchResult, access .papers
                for paper in result.papers:
                    raw = convert_academic_to_raw(paper)
                    sources.append(raw)
                if len(sources) >= limit:
                    break
        except Exception as e:
            logger.warning(f"Academic fetch error: {e}")
        return sources[:limit]
    
    async def _fetch_government(self, queries: List[str], limit: int) -> List[RawSource]:
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
            result = await fetch_rss_sources(default_feeds, max_items_per_feed=limit // 2)
            for article in result.articles[:limit]:
                sources.append(RawSource(
                    url=article.url,
                    title=article.title,
                    content=article.content or article.summary or "",
                    source_name=article.feed_title or "RSS",
                    published_at=article.published_at,
                ))
        except Exception as e:
            logger.warning(f"RSS fetch error: {e}")
        return sources[:limit]
    
    async def _triage_and_analyze(
        self,
        sources: List[RawSource],
        config: WorkstreamScanConfig
    ) -> List[ProcessedSource]:
        """Triage sources and analyze relevant ones."""
        processed = []
        
        for source in sources:
            try:
                # Skip if no content
                if not source.content:
                    triage = TriageResult(
                        is_relevant=True,
                        confidence=0.6,
                        primary_pillar=config.pillar_ids[0] if config.pillar_ids else None,
                        reason="Auto-passed (no content)"
                    )
                else:
                    triage = await self.ai_service.triage_source(
                        title=source.title,
                        content=source.content
                    )
                
                if triage.is_relevant and triage.confidence >= config.triage_threshold:
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
                logger.warning(f"Triage failed for {source.url}: {e}")
                continue
        
        return processed
    
    async def _deduplicate(
        self,
        sources: List[ProcessedSource],
        config: WorkstreamScanConfig
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
                # Check URL first
                url_check = self.supabase.table("sources").select("id").eq(
                    "url", source.raw.url
                ).execute()
                
                if url_check.data:
                    duplicate_count += 1
                    continue
                
                # Vector similarity check
                if source.embedding:
                    match_result = self.supabase.rpc(
                        "find_similar_cards",
                        {
                            "query_embedding": source.embedding,
                            "match_threshold": 0.75,
                            "match_count": 3
                        }
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
        self,
        source: ProcessedSource,
        config: WorkstreamScanConfig
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
            
            result = self.supabase.table("cards").insert({
                "name": analysis.suggested_card_name,
                "slug": slug,
                "summary": analysis.summary,
                "horizon": analysis.horizon,
                "stage_id": stage_id,
                "pillar_id": convert_pillar_id(analysis.pillars[0]) if analysis.pillars else None,
                "goal_id": goal_id,
                "maturity_score": int(analysis.credibility * 20),
                "novelty_score": int(analysis.novelty * 20),
                "impact_score": int(analysis.impact * 20),
                "relevance_score": int(analysis.relevance * 20),
                "velocity_score": int(analysis.velocity * 10),
                "risk_score": int(analysis.risk * 10),
                "status": "active",  # Workstream scans create active cards
                "review_status": "approved",  # Auto-approved for workstream scans
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
            }).execute()
            
            if result.data:
                card_id = result.data[0]["id"]
                
                # Store embedding
                if source.embedding:
                    self.supabase.table("card_embeddings").insert({
                        "card_id": card_id,
                        "embedding": source.embedding,
                        "model": "text-embedding-3-small",
                        "created_at": now,
                    }).execute()
                
                # Store source
                await self._store_source_to_card(source, card_id)
                
                return card_id
        except Exception as e:
            logger.error(f"Card creation failed: {e}")
            raise
        
        return None
    
    async def _store_source_to_card(
        self,
        source: ProcessedSource,
        card_id: str
    ) -> Optional[str]:
        """Store source record linked to card."""
        try:
            result = self.supabase.table("sources").insert({
                "card_id": card_id,
                "url": source.raw.url,
                "title": source.raw.title,
                "source_name": source.raw.source_name,
                "content_type": "article",
                "ai_summary": source.analysis.summary if source.analysis else None,
                "relevance_to_card": source.triage.confidence if source.triage else 0.5,
                "api_source": "workstream_scan",
                "ingested_at": datetime.now().isoformat(),
            }).execute()
            
            if result.data:
                return result.data[0]["id"]
        except Exception as e:
            logger.warning(f"Source storage failed: {e}")
        
        return None
    
    async def _add_to_workstream(
        self,
        workstream_id: str,
        card_id: str,
        user_id: str
    ) -> bool:
        """Add card to workstream inbox if not already present."""
        try:
            # Check if already in workstream
            existing = self.supabase.table("workstream_cards").select("id").eq(
                "workstream_id", workstream_id
            ).eq("card_id", card_id).execute()
            
            if existing.data:
                return False  # Already in workstream
            
            # Add to inbox
            result = self.supabase.table("workstream_cards").insert({
                "workstream_id": workstream_id,
                "card_id": card_id,
                "added_by": user_id,
                "status": "inbox",
                "position": 0,
                "added_from": "workstream_scan",
                "created_at": datetime.now().isoformat(),
            }).execute()
            
            return bool(result.data)
        except Exception as e:
            logger.warning(f"Add to workstream failed: {e}")
            return False
    
    async def _update_scan_status(
        self,
        scan_id: str,
        status: str,
        started_at: Optional[datetime] = None,
        error_message: Optional[str] = None
    ):
        """Update scan record status."""
        try:
            update_data = {"status": status}
            if started_at:
                update_data["started_at"] = started_at.isoformat()
            if error_message:
                update_data["error_message"] = error_message
            
            self.supabase.table("workstream_scans").update(
                update_data
            ).eq("id", scan_id).execute()
        except Exception as e:
            logger.warning(f"Failed to update scan status: {e}")
    
    async def _finalize_scan(self, scan_id: str, result: ScanResult):
        """Finalize scan record with results."""
        try:
            self.supabase.table("workstream_scans").update({
                "status": result.status,
                "completed_at": result.completed_at.isoformat() if result.completed_at else None,
                "results": {
                    "queries_executed": result.queries_executed,
                    "sources_fetched": result.sources_fetched,
                    "sources_by_category": result.sources_by_category,
                    "sources_triaged": result.sources_triaged,
                    "cards_created": len(result.cards_created),
                    "cards_enriched": len(result.cards_enriched),
                    "cards_added_to_workstream": len(result.cards_added_to_workstream),
                    "duplicates_skipped": result.duplicates_skipped,
                    "execution_time_seconds": result.execution_time_seconds,
                    "errors": result.errors,
                },
                "error_message": result.errors[0] if result.errors else None,
            }).eq("id", scan_id).execute()
        except Exception as e:
            logger.warning(f"Failed to finalize scan: {e}")
