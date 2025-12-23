"""
Research service using GPT Researcher + AI analysis pipeline.

This service implements a hybrid research approach:
1. GPT Researcher for source discovery (customized for municipal/foresight focus)
2. AI Triage for quick relevance filtering (gpt-4o-mini)
3. AI Analysis for full classification and scoring (gpt-4o)
4. Vector matching for card association
5. Storage with proper schema and graph-ready entities

Research Types:
- update: Quick refresh with 5-10 new sources
- deep_research: Comprehensive research with 15-20 sources and full analysis
- workstream_analysis: Research based on workstream keywords
"""

import asyncio
import logging
from datetime import date, datetime
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from gpt_researcher import GPTResearcher
from supabase import Client
import openai

from .ai_service import AIService, AnalysisResult, TriageResult

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class RawSource:
    """Source as returned from GPT Researcher."""
    url: str
    title: str
    content: str
    source_name: str
    relevance: float = 0.7


@dataclass
class ProcessedSource:
    """Fully processed source ready for storage."""
    raw: RawSource
    triage: TriageResult
    analysis: AnalysisResult
    embedding: List[float]


@dataclass
class ResearchResult:
    """Result of a research operation."""
    sources_found: int
    sources_relevant: int
    sources_added: int
    cards_matched: List[str]
    cards_created: List[str]
    entities_extracted: int
    cost_estimate: float
    report_preview: Optional[str] = None


# ============================================================================
# Query Templates for GPT Researcher
# ============================================================================

UPDATE_QUERY_TEMPLATE = """
Recent developments and news about {name} with focus on:
- Municipal and city government applications
- Implementation examples and pilot programs
- Key vendors and technology providers
- Challenges and lessons learned

Context: {summary}

Focus on concrete examples, case studies, and actionable insights for city planners.
"""

DEEP_RESEARCH_QUERY_TEMPLATE = """
Comprehensive research on {name} for municipal strategic planning:

1. CURRENT STATE: Technology maturity, adoption rates, key players
2. MUNICIPAL APPLICATIONS: City government use cases, service delivery improvements
3. IMPLEMENTATION: Pilot programs, deployment challenges, success factors
4. VENDORS & ECOSYSTEM: Key providers, partnerships, open-source options
5. COSTS & BENEFITS: Implementation costs, ROI examples, resource requirements
6. RISKS & CHALLENGES: Privacy concerns, equity implications, failure cases
7. FUTURE OUTLOOK: Emerging trends, expected developments, timeline

Context: {summary}

Prioritize sources from government publications, academic research, and reputable technology news.
Include specific examples from cities like Austin, Denver, Seattle, Boston, or similar municipalities.
"""

WORKSTREAM_QUERY_TEMPLATE = """
Emerging technologies and trends related to: {name}

Focus Areas:
- {keywords_list}

Research Scope:
1. Identify technologies relevant to municipal government
2. Find recent pilots and implementations in cities
3. Assess maturity and readiness for government adoption
4. Note key vendors and implementation partners

Description: {description}

Prioritize actionable intelligence for city strategic planning and horizon scanning.
"""


# ============================================================================
# Research Service
# ============================================================================

class ResearchService:
    """
    Handles research operations using hybrid GPT Researcher + AI analysis pipeline.

    Pipeline:
    1. Discovery: GPT Researcher with customized municipal-focused queries
    2. Triage: Quick relevance check with gpt-4o-mini
    3. Analysis: Full classification with gpt-4o
    4. Matching: Vector similarity to existing cards
    5. Storage: Persist with proper schema and entities
    """

    DAILY_DEEP_RESEARCH_LIMIT = 2
    MAX_SOURCES_UPDATE = 5
    MAX_SOURCES_DEEP = 15
    TRIAGE_THRESHOLD = 0.6
    VECTOR_MATCH_THRESHOLD = 0.82
    STRONG_MATCH_THRESHOLD = 0.92

    def __init__(
        self,
        supabase: Client,
        openai_client: openai.OpenAI
    ):
        self.supabase = supabase
        self.openai_client = openai_client
        self.ai_service = AIService(openai_client)

    # ========================================================================
    # Rate Limiting
    # ========================================================================

    async def check_rate_limit(self, card_id: str) -> bool:
        """Check if deep research is allowed for this card today."""
        result = self.supabase.table("cards").select(
            "deep_research_count_today, deep_research_reset_date"
        ).eq("id", card_id).single().execute()

        if not result.data:
            return False

        card = result.data
        today = date.today().isoformat()

        if card.get("deep_research_reset_date") != today:
            self.supabase.table("cards").update({
                "deep_research_count_today": 0,
                "deep_research_reset_date": today
            }).eq("id", card_id).execute()
            return True

        return card.get("deep_research_count_today", 0) < self.DAILY_DEEP_RESEARCH_LIMIT

    async def increment_research_count(self, card_id: str) -> None:
        """Increment the daily research counter for a card."""
        self.supabase.rpc("increment_deep_research_count", {"p_card_id": card_id}).execute()

    # ========================================================================
    # Step 1: Discovery (GPT Researcher)
    # ========================================================================

    async def _discover_sources(
        self,
        query: str,
        report_type: str = "research_report"
    ) -> Tuple[List[RawSource], str, float]:
        """
        Use GPT Researcher to discover sources.

        Args:
            query: Research query (customized for municipal focus)
            report_type: 'research_report' for quick, 'detailed_report' for deep

        Returns:
            Tuple of (sources, report_text, cost)
        """
        researcher = GPTResearcher(
            query=query,
            report_type=report_type,
        )

        await researcher.conduct_research()
        report = await researcher.write_report()

        raw_sources = researcher.get_research_sources()
        costs = researcher.get_costs()

        # Convert to our RawSource format
        sources = []
        for src in raw_sources:
            sources.append(RawSource(
                url=src.get("url", ""),
                title=src.get("title", "Untitled"),
                content=src.get("content", "") or "",
                source_name=src.get("source", "") or src.get("domain", ""),
                relevance=src.get("relevance", src.get("score", 0.7))
            ))

        return sources, report, costs

    # ========================================================================
    # Step 2: Triage (Quick Filtering)
    # ========================================================================

    async def _triage_sources(
        self,
        sources: List[RawSource]
    ) -> List[Tuple[RawSource, TriageResult]]:
        """
        Quick relevance check on sources using cheap model.

        Args:
            sources: List of raw sources from discovery

        Returns:
            List of (source, triage_result) tuples for relevant sources
        """
        relevant = []

        for source in sources:
            if not source.url or not source.content:
                continue

            triage = await self.ai_service.triage_source(
                title=source.title,
                content=source.content
            )

            if triage.is_relevant and triage.confidence >= self.TRIAGE_THRESHOLD:
                relevant.append((source, triage))

        return relevant

    # ========================================================================
    # Step 3: Full Analysis
    # ========================================================================

    async def _analyze_sources(
        self,
        triaged_sources: List[Tuple[RawSource, TriageResult]]
    ) -> List[ProcessedSource]:
        """
        Full analysis of triaged sources using powerful model.

        Args:
            triaged_sources: Sources that passed triage

        Returns:
            List of fully processed sources
        """
        processed = []

        for source, triage in triaged_sources:
            # Full analysis
            analysis = await self.ai_service.analyze_source(
                title=source.title,
                content=source.content,
                source_name=source.source_name,
                published_at=datetime.now().isoformat()  # GPT Researcher doesn't always provide dates
            )

            # Generate embedding for vector matching
            embed_text = f"{source.title} {analysis.summary}"
            embedding = await self.ai_service.generate_embedding(embed_text)

            processed.append(ProcessedSource(
                raw=source,
                triage=triage,
                analysis=analysis,
                embedding=embedding
            ))

        return processed

    # ========================================================================
    # Step 4: Card Matching (Vector Similarity)
    # ========================================================================

    async def _match_to_cards(
        self,
        processed: ProcessedSource,
        card_id: Optional[str] = None
    ) -> Tuple[Optional[str], bool]:
        """
        Match processed source to existing card using vector similarity.

        Args:
            processed: Fully processed source
            card_id: If provided, match directly to this card

        Returns:
            Tuple of (matched_card_id, should_create_new)
        """
        if card_id:
            # Direct match to specified card
            return card_id, False

        # Vector similarity search against existing cards
        # Note: This requires pgvector extension and proper embedding column
        try:
            # Use Supabase RPC for vector similarity search
            result = self.supabase.rpc(
                "match_cards_by_embedding",
                {
                    "query_embedding": processed.embedding,
                    "match_threshold": self.VECTOR_MATCH_THRESHOLD,
                    "match_count": 5
                }
            ).execute()

            if not result.data:
                return None, processed.analysis.is_new_concept

            top_match = result.data[0]
            similarity = top_match.get("similarity", 0)

            if similarity > self.STRONG_MATCH_THRESHOLD:
                # Strong match - add to existing card
                return top_match["id"], False

            elif similarity > self.VECTOR_MATCH_THRESHOLD:
                # Moderate match - use LLM to decide
                card = self.supabase.table("cards").select(
                    "name, summary"
                ).eq("id", top_match["id"]).single().execute()

                if card.data:
                    decision = await self.ai_service.check_card_match(
                        source_summary=processed.analysis.summary,
                        source_card_name=processed.analysis.suggested_card_name,
                        existing_card_name=card.data["name"],
                        existing_card_summary=card.data.get("summary", "")
                    )

                    if decision.get("is_match") and decision.get("confidence", 0) > 0.7:
                        return top_match["id"], False

            return None, processed.analysis.is_new_concept

        except Exception as e:
            # If vector search fails (e.g., function doesn't exist yet),
            # fall back to creating new concept
            logger.warning(f"Vector search failed (falling back to new concept): {e}")
            return None, processed.analysis.is_new_concept

    # ========================================================================
    # Step 5: Storage
    # ========================================================================

    async def _store_source(
        self,
        card_id: str,
        processed: ProcessedSource
    ) -> Optional[str]:
        """
        Store processed source with full schema.

        Args:
            card_id: Card to associate source with
            processed: Fully processed source

        Returns:
            Source ID if created, None if duplicate
        """
        # Check for duplicate URL
        existing = self.supabase.table("sources").select("id").eq(
            "card_id", card_id
        ).eq("url", processed.raw.url).execute()

        if existing.data:
            return None  # Already exists

        # Insert with full schema
        result = self.supabase.table("sources").insert({
            "card_id": card_id,
            "url": processed.raw.url,
            "title": processed.raw.title[:500],
            "publication": processed.raw.source_name[:200] if processed.raw.source_name else None,
            "full_text": processed.raw.content[:10000] if processed.raw.content else None,
            "ai_summary": processed.analysis.summary,
            "key_excerpts": processed.analysis.key_excerpts[:5],
            "relevance_to_card": processed.analysis.relevance,
            "api_source": "gpt_researcher",
            "ingested_at": datetime.now().isoformat(),
            # Note: embedding storage requires pgvector - may need separate handling
        }).execute()

        if result.data:
            source_id = result.data[0]["id"]

            # Store entities for graph
            await self._store_entities(source_id, card_id, processed.analysis.entities)

            # Create timeline event
            await self._create_timeline_event(
                card_id=card_id,
                event_type="source_added",
                description=f"New source: {processed.raw.title[:100]}",
                source_id=source_id
            )

            return source_id

        return None

    async def _store_entities(
        self,
        source_id: str,
        card_id: str,
        entities: List[Any]
    ) -> None:
        """
        Store extracted entities for graph building.

        Args:
            source_id: Associated source
            card_id: Associated card
            entities: List of ExtractedEntity objects
        """
        if not entities:
            return

        # Store in entities table (if exists)
        try:
            for entity in entities:
                self.supabase.table("entities").insert({
                    "name": entity.name,
                    "entity_type": entity.entity_type,
                    "context": entity.context,
                    "source_id": source_id,
                    "card_id": card_id,
                    "created_at": datetime.now().isoformat()
                }).execute()
        except Exception as e:
            # Table might not exist yet - log but don't fail
            logger.warning(f"Entity storage failed (table may not exist): {e}")

    async def _create_card(
        self,
        processed: ProcessedSource,
        created_by: Optional[str] = None
    ) -> str:
        """
        Create a new card from processed source.

        Args:
            processed: Fully processed source
            created_by: User ID who triggered the research

        Returns:
            New card ID
        """
        analysis = processed.analysis

        # Generate slug from name
        slug = analysis.suggested_card_name.lower()
        slug = "".join(c if c.isalnum() or c == " " else "" for c in slug)
        slug = "-".join(slug.split())[:50]

        # Ensure unique slug
        existing = self.supabase.table("cards").select("id").eq("slug", slug).execute()
        if existing.data:
            slug = f"{slug}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        result = self.supabase.table("cards").insert({
            "name": analysis.suggested_card_name,
            "slug": slug,
            "summary": analysis.summary,

            "horizon": analysis.horizon,
            "stage_id": f"{analysis.suggested_stage}_stage",  # Adjust to your schema
            "pillar_id": analysis.pillars[0] if analysis.pillars else None,
            "goal_id": analysis.goals[0] if analysis.goals else None,

            # Arrays (if your schema supports them)
            # "pillars": analysis.pillars,
            # "goals": analysis.goals,
            # "steep_categories": analysis.steep_categories,
            # "anchors": analysis.anchors,

            # Scoring
            "maturity_score": int(analysis.credibility * 20),  # Convert 1-5 to 0-100
            "novelty_score": int(analysis.novelty * 20),
            "impact_score": int(analysis.impact * 20),
            "relevance_score": int(analysis.relevance * 20),
            "velocity_score": int(analysis.likelihood * 11),  # Convert 1-9 to 0-100

            "status": "active",
            "created_by": created_by,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }).execute()

        if result.data:
            card_id = result.data[0]["id"]

            # Create timeline event
            await self._create_timeline_event(
                card_id=card_id,
                event_type="created",
                description=f"Card created from research"
            )

            return card_id

        raise Exception("Failed to create card")

    async def _create_timeline_event(
        self,
        card_id: str,
        event_type: str,
        description: str,
        source_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """Create a timeline event for a card."""
        self.supabase.table("card_timeline").insert({
            "card_id": card_id,
            "event_type": event_type,
            "title": event_type.replace("_", " ").title(),
            "description": description,
            "triggered_by_source_id": source_id,
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat()
        }).execute()

    async def _update_card_from_analysis(
        self,
        card_id: str,
        analysis: AnalysisResult
    ) -> None:
        """Update card metrics based on new analysis."""
        self.supabase.table("cards").update({
            "updated_at": datetime.now().isoformat(),
            # Optionally update scores if novelty warrants it
            # This could be more sophisticated - averaging, weighting, etc.
        }).eq("id", card_id).execute()

    # ========================================================================
    # Main Entry Points
    # ========================================================================

    async def execute_update(
        self,
        card_id: str,
        task_id: str
    ) -> ResearchResult:
        """
        Execute quick update research for a card.

        Pipeline:
        1. Build municipal-focused query
        2. Discover sources with GPT Researcher
        3. Triage for relevance
        4. Analyze relevant sources
        5. Store to existing card
        """
        logger.info(f"Starting update research for card {card_id} (task: {task_id})")

        # Get card details
        card_result = self.supabase.table("cards").select(
            "name, summary"
        ).eq("id", card_id).single().execute()

        if not card_result.data:
            raise ValueError(f"Card not found: {card_id}")

        card = card_result.data

        # Step 1: Build customized query
        query = UPDATE_QUERY_TEMPLATE.format(
            name=card["name"],
            summary=card.get("summary", "")
        )

        # Step 2: Discover sources
        sources, report, cost = await self._discover_sources(
            query=query,
            report_type="research_report"
        )

        # Step 3: Triage
        triaged = await self._triage_sources(sources[:self.MAX_SOURCES_UPDATE * 2])

        # Step 4: Analyze (limit to MAX_SOURCES_UPDATE)
        processed = await self._analyze_sources(triaged[:self.MAX_SOURCES_UPDATE])

        # Step 5: Store
        sources_added = 0
        for proc in processed:
            source_id = await self._store_source(card_id, proc)
            if source_id:
                sources_added += 1

        # Update card timestamp
        self.supabase.table("cards").update({
            "updated_at": datetime.now().isoformat()
        }).eq("id", card_id).execute()

        # Create summary timeline event
        await self._create_timeline_event(
            card_id=card_id,
            event_type="updated",
            description=f"Quick update: {sources_added} new sources from {len(sources)} discovered",
            metadata={"sources_found": len(sources), "sources_added": sources_added, "cost": cost}
        )

        logger.info(f"Update research complete for card {card_id}: {sources_added} sources added from {len(sources)} discovered")

        return ResearchResult(
            sources_found=len(sources),
            sources_relevant=len(triaged),
            sources_added=sources_added,
            cards_matched=[card_id],
            cards_created=[],
            entities_extracted=sum(len(p.analysis.entities) for p in processed),
            cost_estimate=cost,
            report_preview=report[:500] if report else None
        )

    async def execute_deep_research(
        self,
        card_id: str,
        task_id: str
    ) -> ResearchResult:
        """
        Execute comprehensive deep research for a card.

        Same pipeline as update but:
        - More comprehensive query
        - More sources (15+)
        - Rate limited (2/day/card)
        """
        logger.info(f"Starting deep research for card {card_id} (task: {task_id})")

        # Check rate limit
        if not await self.check_rate_limit(card_id):
            logger.warning(f"Rate limit exceeded for card {card_id}")
            raise Exception("Daily deep research limit reached (2 per day per card)")

        # Get card details
        card_result = self.supabase.table("cards").select("*").eq("id", card_id).single().execute()

        if not card_result.data:
            raise ValueError(f"Card not found: {card_id}")

        card = card_result.data

        # Step 1: Build comprehensive query
        query = DEEP_RESEARCH_QUERY_TEMPLATE.format(
            name=card["name"],
            summary=card.get("summary", "")
        )

        # Step 2: Discover sources (detailed report for more depth)
        sources, report, cost = await self._discover_sources(
            query=query,
            report_type="detailed_report"
        )

        # Step 3: Triage
        triaged = await self._triage_sources(sources)

        # Step 4: Analyze (more sources for deep research)
        processed = await self._analyze_sources(triaged[:self.MAX_SOURCES_DEEP])

        # Step 5: Store
        sources_added = 0
        for proc in processed:
            source_id = await self._store_source(card_id, proc)
            if source_id:
                sources_added += 1
                # Update card metrics from high-novelty sources
                if proc.analysis.novelty > 3.5:
                    await self._update_card_from_analysis(card_id, proc.analysis)

        # Update timestamps
        self.supabase.table("cards").update({
            "updated_at": datetime.now().isoformat(),
            "deep_research_at": datetime.now().isoformat()
        }).eq("id", card_id).execute()

        # Increment rate limit
        await self.increment_research_count(card_id)

        # Create timeline event
        await self._create_timeline_event(
            card_id=card_id,
            event_type="deep_research",
            description=f"Deep research: {sources_added} sources from {len(sources)} discovered",
            metadata={
                "sources_found": len(sources),
                "sources_relevant": len(triaged),
                "sources_added": sources_added,
                "cost": cost
            }
        )

        logger.info(f"Deep research complete for card {card_id}: {sources_added} sources added, {sum(len(p.analysis.entities) for p in processed)} entities extracted")

        return ResearchResult(
            sources_found=len(sources),
            sources_relevant=len(triaged),
            sources_added=sources_added,
            cards_matched=[card_id],
            cards_created=[],
            entities_extracted=sum(len(p.analysis.entities) for p in processed),
            cost_estimate=cost,
            report_preview=report[:1000] if report else None
        )

    async def execute_workstream_analysis(
        self,
        workstream_id: str,
        task_id: str,
        user_id: str
    ) -> ResearchResult:
        """
        Analyze a workstream and find/create relevant cards.

        This can create new cards if novel concepts are discovered.
        """
        logger.info(f"Starting workstream analysis for {workstream_id} (task: {task_id})")

        # Get workstream details
        ws_result = self.supabase.table("workstreams").select("*").eq("id", workstream_id).single().execute()

        if not ws_result.data:
            raise ValueError(f"Workstream not found: {workstream_id}")

        ws = ws_result.data
        keywords = ws.get("keywords", [])

        # Step 1: Build workstream query
        query = WORKSTREAM_QUERY_TEMPLATE.format(
            name=ws.get("name", ""),
            keywords_list=", ".join(keywords) if keywords else "emerging technologies",
            description=ws.get("description", "")
        )

        # Step 2: Discover sources
        sources, report, cost = await self._discover_sources(
            query=query,
            report_type="research_report"
        )

        # Step 3: Triage
        triaged = await self._triage_sources(sources)

        # Step 4: Analyze
        processed = await self._analyze_sources(triaged[:15])

        # Step 5: Match or create cards
        cards_matched = []
        cards_created = []
        sources_added = 0

        for proc in processed:
            # Try to match to existing card
            matched_card_id, should_create = await self._match_to_cards(proc)

            if matched_card_id:
                source_id = await self._store_source(matched_card_id, proc)
                if source_id:
                    sources_added += 1
                    if matched_card_id not in cards_matched:
                        cards_matched.append(matched_card_id)

            elif should_create:
                # Create new card
                try:
                    new_card_id = await self._create_card(proc, created_by=user_id)
                    await self._store_source(new_card_id, proc)
                    cards_created.append(new_card_id)
                    sources_added += 1
                    logger.info(f"Created new card: {proc.analysis.suggested_card_name}")
                except Exception as e:
                    logger.error(f"Failed to create card: {e}")

        logger.info(f"Workstream analysis complete for {workstream_id}: matched {len(cards_matched)} cards, created {len(cards_created)} new cards")

        return ResearchResult(
            sources_found=len(sources),
            sources_relevant=len(triaged),
            sources_added=sources_added,
            cards_matched=cards_matched,
            cards_created=cards_created,
            entities_extracted=sum(len(p.analysis.entities) for p in processed),
            cost_estimate=cost,
            report_preview=report[:500] if report else None
        )
