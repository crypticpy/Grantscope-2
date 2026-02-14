"""
Research service using GPT Researcher + AI analysis pipeline.

This service implements a hybrid research approach:
1. GPT Researcher for source discovery (Tavily Extract scraping)
2. Serper + crawler for supplementary high-quality sources
3. Unified crawler module for content backfill when sources lack content
4. AI Triage for quick relevance filtering (gpt-4o-mini)
5. AI Analysis for full classification and scoring (gpt-4o)
6. Vector matching for card association
7. Storage with proper schema and graph-ready entities

Research Types:
- update: Quick refresh with 5-10 new sources
- deep_research: Comprehensive research with 15-20 sources and full analysis
- workstream_analysis: Research based on workstream keywords
"""

import asyncio
import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from gpt_researcher import GPTResearcher
from supabase import Client
import openai

# Optional imports for enhanced source fetching
try:
    from exa_py import Exa

    EXA_AVAILABLE = True
except ImportError:
    EXA_AVAILABLE = False

from .ai_service import AIService, AnalysisResult, TriageResult

logger = logging.getLogger(__name__)


# ============================================================================
# GPT Researcher Azure OpenAI Configuration
# ============================================================================
# GPT Researcher requires specific env var formats that differ from our app's config.
# This function ensures the correct format is set before GPTResearcher is used.


def _configure_gpt_researcher_for_azure():
    """
    Configure environment variables for GPT Researcher to use Azure OpenAI.

    GPT Researcher expects:
    - SMART_LLM = "azure_openai:<deployment-name>"
    - FAST_LLM = "azure_openai:<deployment-name>"
    - EMBEDDING = "azure_openai:<deployment-name>"
    - AZURE_OPENAI_API_KEY (not AZURE_OPENAI_KEY)
    - OPENAI_API_VERSION (not AZURE_OPENAI_API_VERSION)

    Our app uses different naming, so we translate here.
    """
    # Get our app's Azure config
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    azure_key = os.getenv("AZURE_OPENAI_KEY") or os.getenv("AZURE_OPENAI_API_KEY", "")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

    # Get deployment names from our config
    chat_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_CHAT", "gpt-4.1")
    chat_mini_deployment = os.getenv(
        "AZURE_OPENAI_DEPLOYMENT_CHAT_MINI", "gpt-4.1-mini"
    )
    embedding_deployment = os.getenv(
        "AZURE_OPENAI_DEPLOYMENT_EMBEDDING", "text-embedding-ada-002"
    )

    # Set GPT Researcher expected env vars with azure_openai: prefix
    gptr_config = {
        # LLM config with required azure_openai: prefix
        "SMART_LLM": f"azure_openai:{chat_deployment}",
        "FAST_LLM": f"azure_openai:{chat_mini_deployment}",
        "EMBEDDING": f"azure_openai:{embedding_deployment}",
        # Azure credentials (GPT Researcher expects these exact names)
        "AZURE_OPENAI_API_KEY": azure_key,
        "AZURE_OPENAI_ENDPOINT": azure_endpoint,
        "OPENAI_API_VERSION": api_version,
        # Some GPT Researcher components (e.g. embeddings) read this directly.
        "AZURE_OPENAI_API_VERSION": api_version,
        # Token limits
        "FAST_TOKEN_LIMIT": "4000",
        "SMART_TOKEN_LIMIT": "4000",
        "STRATEGIC_TOKEN_LIMIT": "4000",
    }

    # Set each env var if not already correctly set
    for key, value in gptr_config.items():
        if value:  # Only set if we have a value
            current = os.getenv(key, "")
            if current != value:
                os.environ[key] = value
                logger.debug(
                    f"GPT Researcher config: {key}={value[:50]}..."
                    if len(value) > 50
                    else f"GPT Researcher config: {key}={value}"
                )

    logger.info(
        f"GPT Researcher configured for Azure OpenAI: SMART_LLM={gptr_config['SMART_LLM']}, FAST_LLM={gptr_config['FAST_LLM']}"
    )


# Configure GPT Researcher on module load
_configure_gpt_researcher_for_azure()


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
    # Added for persistence tracking
    published_at: Optional[str] = None
    source_type: Optional[str] = None
    discovered_source_id: Optional[str] = None  # ID in discovered_sources table
    is_preprint: bool = False  # Flag set by SourceValidator.detect_preprint()


@dataclass
class ProcessedSource:
    """Fully processed source ready for storage."""

    raw: RawSource
    triage: TriageResult
    analysis: AnalysisResult
    embedding: List[float]
    discovered_source_id: Optional[str] = None  # ID in discovered_sources table


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
    1. Discovery: GPT Researcher with Tavily Extract scraping
    2. Enhancement: Serper + crawler for supplementary sources
    3. Backfill: Unified crawler module for missing content
    4. Triage: Quick relevance check with gpt-4o-mini
    5. Analysis: Full classification with gpt-4o
    6. Matching: Vector similarity to existing cards
    7. Storage: Persist with proper schema and entities
    """

    DAILY_DEEP_RESEARCH_LIMIT = 2
    MAX_SOURCES_UPDATE = 5
    MAX_SOURCES_DEEP = 25
    TRIAGE_THRESHOLD = 0.6
    VECTOR_MATCH_THRESHOLD = 0.82
    STRONG_MATCH_THRESHOLD = 0.92

    def __init__(self, supabase: Client, openai_client: openai.OpenAI):
        self.supabase = supabase
        self.openai_client = openai_client
        self.ai_service = AIService(openai_client)

        # Initialize Exa if available
        self.exa = None
        if EXA_AVAILABLE and os.getenv("EXA_API_KEY"):
            try:
                self.exa = Exa(os.getenv("EXA_API_KEY"))
                logger.info("Exa AI initialized for enhanced search")
            except Exception as e:
                logger.warning(f"Exa initialization failed: {e}")

    # ========================================================================
    # Rate Limiting
    # ========================================================================

    async def check_rate_limit(self, card_id: str) -> bool:
        """Check if deep research is allowed for this card today."""
        result = (
            self.supabase.table("cards")
            .select("deep_research_count_today, deep_research_reset_date")
            .eq("id", card_id)
            .single()
            .execute()
        )

        if not result.data:
            return False

        card = result.data
        today = date.today().isoformat()

        if card.get("deep_research_reset_date") != today:
            self.supabase.table("cards").update(
                {"deep_research_count_today": 0, "deep_research_reset_date": today}
            ).eq("id", card_id).execute()
            return True

        return card.get("deep_research_count_today", 0) < self.DAILY_DEEP_RESEARCH_LIMIT

    async def increment_research_count(self, card_id: str) -> None:
        """Increment the daily research counter for a card."""
        self.supabase.rpc(
            "increment_deep_research_count", {"p_card_id": card_id}
        ).execute()

    # ========================================================================
    # Step 1: Discovery (GPT Researcher + Serper Enhancement)
    # ========================================================================

    async def _discover_sources(
        self,
        query: str,
        report_type: str = "research_report",
        existing_source_urls: Optional[List[str]] = None,
    ) -> Tuple[List[RawSource], str, float]:
        """
        Use GPT Researcher to discover sources, enhanced with Serper + crawler.

        Args:
            query: Research query (customized for municipal focus)
            report_type: 'research_report' for quick, 'detailed_report' for deep

        Returns:
            Tuple of (sources, report_text, cost)
        """
        # Use Tavily Extract for page scraping — leverages existing Tavily
        # subscription for cleaner content extraction than BeautifulSoup.
        os.environ["SCRAPER"] = "tavily_extract"

        researcher = GPTResearcher(
            query=query,
            report_type=report_type,
            max_subtopics=10,
            source_urls=existing_source_urls or None,
            complement_source_urls=bool(existing_source_urls),
            verbose=False,
        )

        # Wrap GPT Researcher calls with timeouts to prevent indefinite hangs
        try:
            await asyncio.wait_for(researcher.conduct_research(), timeout=300)
            report = await asyncio.wait_for(researcher.write_report(), timeout=120)
            raw_sources = researcher.get_research_sources()
            costs = researcher.get_costs()
        except asyncio.TimeoutError:
            logger.warning(
                "GPT Researcher timed out during conduct_research/write_report"
            )
            raw_sources = []
            report = None
            costs = 0.0
        except (TypeError, ValueError) as e:
            # Handle case where LLM returns None or invalid response
            logger.warning(f"GPT Researcher failed (likely LLM timeout): {e}")
            raw_sources = []
            report = None
            costs = 0.0
        except Exception as e:
            logger.error(f"GPT Researcher unexpected error: {e}")
            raw_sources = []
            report = None
            costs = 0.0

        # Convert to our RawSource format
        sources = []
        seen_urls = set()
        for src in raw_sources:
            url = src.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)

                # Extract title - GPT Researcher may return empty title for PDFs
                raw_title = src.get("title", "") or ""

                # If title is empty or just whitespace, try to extract from URL or content
                if not raw_title.strip():
                    # Try LLM-based title generation if content is available
                    content_for_title = src.get("content", "") or ""
                    if content_for_title and len(content_for_title) > 50:
                        try:
                            raw_title = await self.ai_service.generate_source_title(
                                url=url,
                                content_snippet=content_for_title[:1000],
                            )
                            logger.debug(f"LLM-generated title: {raw_title}")
                        except Exception:
                            pass

                    # Fallback: extract from URL filename for PDFs
                    if not raw_title.strip() and url.lower().endswith(".pdf"):
                        from urllib.parse import urlparse, unquote

                        path = urlparse(url).path
                        filename = unquote(path.split("/")[-1])
                        raw_title = (
                            filename.replace(".pdf", "")
                            .replace("_", " ")
                            .replace("-", " ")
                            .strip()
                        )
                        logger.debug(f"PDF title from URL: {raw_title}")

                    # If still empty, use "Untitled"
                    if not raw_title.strip():
                        raw_title = "Untitled"

                # Log source data for debugging
                logger.debug(
                    f"Source from GPT Researcher: url={url[:80]}, title={raw_title[:50] if raw_title else 'EMPTY'}, keys={list(src.keys())}"
                )

                sources.append(
                    RawSource(
                        url=url,
                        title=raw_title,
                        content=src.get("content", "") or "",
                        source_name=src.get("source", "") or src.get("domain", ""),
                        relevance=src.get("relevance", src.get("score", 0.7)),
                    )
                )

        logger.info(f"GPT Researcher found {len(sources)} sources")

        # Supplement with Serper search for additional high-quality sources (primary supplement)
        try:
            serper_sources = await self._search_with_serper(query, num_results=10)
            for src in serper_sources:
                if src.url not in seen_urls:
                    seen_urls.add(src.url)
                    sources.append(src)
            if serper_sources:
                logger.info(f"Serper added {len(serper_sources)} additional sources")
        except Exception as e:
            logger.warning(
                f"Serper search failed (continuing with GPT Researcher sources): {e}"
            )

        # Exa neural search as FALLBACK — only when Tavily+Serper didn't find enough
        MIN_SOURCES_BEFORE_EXA = 10
        if len(sources) < MIN_SOURCES_BEFORE_EXA:
            logger.info(
                f"Only {len(sources)} sources from Tavily+Serper (need {MIN_SOURCES_BEFORE_EXA}), falling back to Exa"
            )
            try:
                exa_sources = await self._search_with_exa(query, num_results=10)
                exa_added = 0
                for src in exa_sources:
                    if src.url not in seen_urls:
                        seen_urls.add(src.url)
                        sources.append(src)
                        exa_added += 1
                if exa_added:
                    logger.info(f"Exa fallback added {exa_added} additional sources")
            except Exception as e:
                logger.warning(f"Exa fallback search failed: {e}")
        else:
            logger.info(
                f"Tavily+Serper found {len(sources)} sources, skipping Exa (cost savings)"
            )

        return sources, report, costs

    async def _search_with_exa(
        self, query: str, num_results: int = 10
    ) -> List[RawSource]:
        """
        Search with Exa AI neural search for high-quality sources with content.

        Args:
            query: Search query
            num_results: Max number of results

        Returns:
            List of RawSource with content included
        """
        if not self.exa:
            return []

        try:
            # Calculate date range (last 180 days for broader coverage)
            start_date = (datetime.now(timezone.utc) - timedelta(days=180)).strftime(
                "%Y-%m-%d"
            )

            # Exa search with content retrieval
            results = self.exa.search_and_contents(
                query,
                num_results=num_results,
                start_published_date=start_date,
                type="neural",
                text=True,
                highlights=True,
            )

            sources = []
            for result in results.results:
                # Combine text and highlights for content
                content = result.text or ""
                if result.highlights:
                    content = "\n\n".join(result.highlights) + "\n\n" + content

                sources.append(
                    RawSource(
                        url=result.url,
                        title=result.title or "Untitled",
                        content=content[:10000],  # Limit content size
                        source_name=result.author or "",
                        relevance=result.score if hasattr(result, "score") else 0.8,
                    )
                )

            return sources

        except Exception as e:
            logger.warning(f"Exa search error: {e}")
            return []

    async def _search_with_serper(
        self, query: str, num_results: int = 5
    ) -> List[RawSource]:
        """
        Search with Serper + crawler for supplementary sources.

        Uses Serper for web + news search and the unified crawler module
        for full-text extraction.

        Args:
            query: Search query
            num_results: Max number of results to return

        Returns:
            List of RawSource with content included
        """
        from .source_fetchers.serper_fetcher import (
            search_web,
            search_news,
            is_available as serper_available,
        )
        from .crawler import crawl_url

        if not serper_available():
            logger.warning("Serper not available for supplementary search")
            return []

        sources = []
        try:
            # Search web and news
            web_results = await search_web(query, num_results=num_results)
            news_results = await search_news(query, num_results=num_results)

            # Deduplicate by URL
            seen_urls = set()
            all_results = []
            for r in web_results + news_results:
                if r.url not in seen_urls:
                    seen_urls.add(r.url)
                    all_results.append(r)

            # Extract content for top results
            for result in all_results[:num_results]:
                content = result.snippet
                try:
                    crawl_result = await crawl_url(result.url)
                    if (
                        crawl_result.success
                        and crawl_result.markdown
                        and len(crawl_result.markdown) > len(content)
                    ):
                        content = crawl_result.markdown
                except Exception as e:
                    logger.warning(f"Content extraction failed for {result.url}: {e}")

                sources.append(
                    RawSource(
                        url=result.url,
                        title=result.title,
                        content=content,
                        source_name=result.source_name or "Web Search",
                    )
                )

            logger.info(f"Serper search found {len(sources)} sources for: {query[:50]}")
        except Exception as e:
            logger.warning(f"Serper search failed: {e}")

        return sources

    async def _backfill_content(self, sources: List[RawSource]) -> List[RawSource]:
        """
        Fetch content for sources that have URLs but no content using the
        unified crawler module.

        Args:
            sources: List of sources, some may have empty content

        Returns:
            Same list with content backfilled where possible
        """
        from .crawler import crawl_urls

        sources_needing_content = [s for s in sources if s.url and not s.content]
        if not sources_needing_content:
            logger.info("All sources already have content")
            return sources

        logger.info(
            f"Backfilling content for {len(sources_needing_content)} sources via crawler"
        )

        # Batch crawl all URLs that need content
        urls = [s.url for s in sources_needing_content]
        results = await crawl_urls(urls, max_concurrent=5)

        backfilled_count = 0
        for source, result in zip(sources_needing_content, results):
            if result.success and result.markdown:
                source.content = result.markdown[:10000]
                backfilled_count += 1

            # Update title if crawler returned one and current title is generic
            if result.title and result.title.strip():
                current_title = source.title or ""
                if (
                    not current_title.strip()
                    or current_title == "Untitled"
                    or len(current_title) < 5
                ):
                    source.title = result.title.strip()[:500]

            # If title is still generic after crawling, try LLM generation
            current_title = source.title or ""
            if source.content and (
                not current_title.strip()
                or current_title == "Untitled"
                or len(current_title) < 5
            ):
                try:
                    llm_title = await self.ai_service.generate_source_title(
                        url=source.url,
                        content_snippet=source.content[:1000],
                    )
                    if llm_title and llm_title != "Untitled":
                        source.title = llm_title
                        logger.debug(
                            f"LLM-generated title after backfill: {llm_title[:50]}"
                        )
                except Exception:
                    pass

        logger.info(
            f"Crawler backfilled content for {backfilled_count}/{len(sources_needing_content)} sources"
        )
        return sources

    # ========================================================================
    # Step 2: Triage (Quick Filtering)
    # ========================================================================

    async def _triage_sources(
        self, sources: List[RawSource]
    ) -> List[Tuple[RawSource, TriageResult]]:
        """
        Quick relevance check on sources using cheap model.

        Sources without content are auto-passed with default relevance to allow
        storage of URL/title for future reference.

        Args:
            sources: List of raw sources from discovery

        Returns:
            List of (source, triage_result) tuples for relevant sources
        """
        relevant = []
        skipped_no_url = 0
        auto_passed = 0
        ai_triaged = 0

        for source in sources:
            # Must have a URL
            if not source.url:
                skipped_no_url += 1
                continue

            # If no content, auto-pass with default relevance
            # We still want to store the URL/title for reference
            if not source.content:
                auto_passed += 1
                default_triage = TriageResult(
                    is_relevant=True,
                    confidence=0.65,  # Just above threshold
                    primary_pillar=None,
                    reason="Source passed without content - URL/title preserved for reference",
                )
                relevant.append((source, default_triage))
                continue

            # Full AI triage for sources with content
            try:
                triage = await self.ai_service.triage_source(
                    title=source.title, content=source.content
                )
                ai_triaged += 1

                if triage.is_relevant and triage.confidence >= self.TRIAGE_THRESHOLD:
                    relevant.append((source, triage))
            except Exception as e:
                logger.warning(f"Triage failed for {source.url}: {e}")
                # On triage error, auto-pass to not lose potentially good sources
                default_triage = TriageResult(
                    is_relevant=True,
                    confidence=0.6,
                    primary_pillar=None,
                    reason=f"Triage failed: {str(e)[:100]}",
                )
                relevant.append((source, default_triage))

        logger.info(
            f"Triage: {len(relevant)} passed ({auto_passed} auto-passed, {ai_triaged} AI-triaged), {skipped_no_url} skipped (no URL)"
        )
        return relevant

    # ========================================================================
    # Step 3: Full Analysis
    # ========================================================================

    async def _analyze_sources(
        self, triaged_sources: List[Tuple[RawSource, TriageResult]]
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
                published_at=datetime.now(
                    timezone.utc
                ).isoformat(),  # GPT Researcher doesn't always provide dates
            )

            # Generate embedding for vector matching
            embed_text = f"{source.title} {analysis.summary}"
            embedding = await self.ai_service.generate_embedding(embed_text)

            processed.append(
                ProcessedSource(
                    raw=source, triage=triage, analysis=analysis, embedding=embedding
                )
            )

        return processed

    # ========================================================================
    # Step 4: Card Matching (Vector Similarity)
    # ========================================================================

    async def _match_to_cards(
        self, processed: ProcessedSource, card_id: Optional[str] = None
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
                    "match_count": 5,
                },
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
                card = (
                    self.supabase.table("cards")
                    .select("name, summary")
                    .eq("id", top_match["id"])
                    .single()
                    .execute()
                )

                if card.data:
                    decision = await self.ai_service.check_card_match(
                        source_summary=processed.analysis.summary,
                        source_card_name=processed.analysis.suggested_card_name,
                        existing_card_name=card.data["name"],
                        existing_card_summary=card.data.get("summary", ""),
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
        self, card_id: str, processed: ProcessedSource
    ) -> Optional[str]:
        """
        Store processed source with full schema.

        Runs embedding-based deduplication before inserting.  If the source
        is a duplicate (>0.95 similarity), it is skipped.  If related
        (0.85-0.95), it is stored with ``duplicate_of`` set.

        Args:
            card_id: Card to associate source with
            processed: Fully processed source

        Returns:
            Source ID if created, None if duplicate or error
        """
        try:
            # --- Deduplication check (URL + embedding) ---
            from app.deduplication import check_duplicate

            dedup_result = await check_duplicate(
                supabase=self.supabase,
                card_id=card_id,
                content=processed.raw.content or "",
                url=processed.raw.url or "",
                embedding=(
                    processed.embedding if hasattr(processed, "embedding") else None
                ),
                ai_service=self.ai_service,
            )

            if dedup_result.action == "skip":
                logger.debug(
                    f"Dedup: skipping duplicate source (sim={dedup_result.similarity:.4f}): "
                    f"{processed.raw.url[:50]}..."
                )
                return None

            # Prepare insert data with safe defaults
            from app.source_quality import extract_domain

            insert_data = {
                "card_id": card_id,
                "url": processed.raw.url,
                "title": (processed.raw.title or "Untitled")[:500],
                "publication": (
                    (processed.raw.source_name or "")[:200]
                    if processed.raw.source_name
                    else None
                ),
                "full_text": (
                    processed.raw.content[:10000] if processed.raw.content else None
                ),
                "ai_summary": (
                    processed.analysis.summary if processed.analysis else None
                ),
                "key_excerpts": (
                    processed.analysis.key_excerpts[:5]
                    if processed.analysis and processed.analysis.key_excerpts
                    else []
                ),
                "relevance_to_card": (
                    processed.analysis.relevance if processed.analysis else 0.5
                ),
                "api_source": "gpt_researcher",
                "domain": extract_domain(processed.raw.url or ""),
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            }

            # If related (0.85-0.95 similarity), mark duplicate_of
            if (
                dedup_result.action == "store_as_related"
                and dedup_result.duplicate_of_id
            ):
                insert_data["duplicate_of"] = dedup_result.duplicate_of_id

            # Insert with full schema
            result = self.supabase.table("sources").insert(insert_data).execute()

            if result.data:
                source_id = result.data[0]["id"]
                logger.info(
                    f"Stored source: {processed.raw.title[:50]}... (id: {source_id})"
                )

                # Store entities for graph (non-blocking)
                try:
                    if processed.analysis and processed.analysis.entities:
                        await self._store_entities(
                            source_id, card_id, processed.analysis.entities
                        )
                except Exception as e:
                    logger.warning(f"Entity storage failed (source still saved): {e}")

                # Create timeline event (non-blocking)
                try:
                    await self._create_timeline_event(
                        card_id=card_id,
                        event_type="source_added",
                        description=f"New source: {processed.raw.title[:100]}",
                        source_id=source_id,
                    )
                except Exception as e:
                    logger.warning(f"Timeline event failed (source still saved): {e}")

                # Compute and store source quality score (non-blocking)
                try:
                    from app.source_quality import compute_and_store_quality_score

                    compute_and_store_quality_score(
                        self.supabase,
                        source_id,
                        analysis=(
                            processed.analysis
                            if hasattr(processed, "analysis")
                            else None
                        ),
                        triage=(
                            processed.triage if hasattr(processed, "triage") else None
                        ),
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to compute quality score for source {source_id}: {e}"
                    )

                return source_id

            logger.warning(f"Insert returned no data for: {processed.raw.url[:50]}...")
            return None

        except Exception as e:
            error_msg = str(e)
            # Log detailed error for debugging
            logger.error(
                f"Source storage failed for {processed.raw.url[:50]}...: {error_msg}"
            )

            # Check for specific error types
            if "duplicate" in error_msg.lower() or "unique" in error_msg.lower():
                logger.debug("Duplicate detected via error (OK)")
                return None
            elif "column" in error_msg.lower():
                logger.error(f"Schema mismatch - missing column: {error_msg}")
            elif "permission" in error_msg.lower() or "rls" in error_msg.lower():
                logger.error(f"Permission/RLS error: {error_msg}")

            return None

    async def _store_entities(
        self, source_id: str, card_id: str, entities: List[Any]
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
                self.supabase.table("entities").insert(
                    {
                        "name": entity.name,
                        "entity_type": entity.entity_type,
                        "context": entity.context,
                        "source_id": source_id,
                        "card_id": card_id,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                ).execute()
        except Exception as e:
            # Table might not exist yet - log but don't fail
            logger.warning(f"Entity storage failed (table may not exist): {e}")

    async def _create_card(
        self, processed: ProcessedSource, created_by: Optional[str] = None
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
            slug = f"{slug}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        result = (
            self.supabase.table("cards")
            .insert(
                {
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
                    # Scoring (convert AI scale to 0-100 and clamp)
                    "maturity_score": max(
                        0, min(int(analysis.credibility * 20), 100)
                    ),  # 1-5 -> 0-100
                    "novelty_score": max(
                        0, min(int(analysis.novelty * 20), 100)
                    ),  # 1-5 -> 0-100
                    "impact_score": max(
                        0, min(int(analysis.impact * 20), 100)
                    ),  # 1-5 -> 0-100
                    "relevance_score": max(
                        0, min(int(analysis.relevance * 20), 100)
                    ),  # 1-5 -> 0-100
                    "velocity_score": max(
                        0, min(int(analysis.velocity * 10), 100)
                    ),  # 1-10 -> 0-100
                    "status": "active",
                    "created_by": created_by,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            .execute()
        )

        if result.data:
            card_id = result.data[0]["id"]

            # Create timeline event
            await self._create_timeline_event(
                card_id=card_id,
                event_type="created",
                description="Card created from research",
            )

            return card_id

        raise Exception("Failed to create card")

    async def _create_timeline_event(
        self,
        card_id: str,
        event_type: str,
        description: str,
        source_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Create a timeline event for a card."""
        self.supabase.table("card_timeline").insert(
            {
                "card_id": card_id,
                "event_type": event_type,
                "title": event_type.replace("_", " ").title(),
                "description": description,
                "triggered_by_source_id": source_id,
                "metadata": metadata or {},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()

    async def _update_card_from_analysis(
        self, card_id: str, analysis: AnalysisResult
    ) -> None:
        """Update card metrics based on new analysis."""
        self.supabase.table("cards").update(
            {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                # Optionally update scores if novelty warrants it
                # This could be more sophisticated - averaging, weighting, etc.
            }
        ).eq("id", card_id).execute()

    # ========================================================================
    # Profile Auto-Refresh
    # ========================================================================

    async def _maybe_refresh_profile(self, card_id: str) -> None:
        """Check if a card's profile should be regenerated based on new sources.

        Triggers regeneration when 3+ new sources have been added since the
        last profile generation.  Uses the existing ``generate_signal_profile``
        method from ``AIService`` with incremental context from the previous
        profile.
        """
        try:
            # Get card data including profile tracking columns
            card = (
                self.supabase.table("cards")
                .select(
                    "id, name, summary, description, pillar_id, horizon, "
                    "profile_generated_at, profile_source_count"
                )
                .eq("id", card_id)
                .single()
                .execute()
            )

            if not card.data:
                return

            card_data = card.data

            # Count current sources on this card
            source_count_resp = (
                self.supabase.table("sources")
                .select("id", count="exact")
                .eq("card_id", card_id)
                .execute()
            )
            current_source_count = source_count_resp.count or len(
                source_count_resp.data or []
            )

            # Check if enough new sources to warrant refresh
            previous_count = card_data.get("profile_source_count") or 0
            new_sources = current_source_count - previous_count

            if new_sources < 3:
                logger.debug(
                    f"Card {card_id}: only {new_sources} new sources, "
                    "skipping profile refresh"
                )
                return

            logger.info(
                f"Card {card_id}: {new_sources} new sources, refreshing profile"
            )

            # Get source data for profile generation
            sources_resp = (
                self.supabase.table("sources")
                .select(
                    "title, ai_summary, key_excerpts, url, full_text, ingested_at, created_at"
                )
                .eq("card_id", card_id)
                .order("created_at", desc=True)
                .limit(20)
                .execute()
            )

            if not sources_resp.data:
                return

            # Build source_analyses list in the format expected by
            # AIService.generate_signal_profile
            source_analyses = []
            for src in sources_resp.data:
                source_analyses.append(
                    {
                        "title": src.get("title", "Untitled"),
                        "url": src.get("url", ""),
                        "summary": src.get("ai_summary", ""),
                        "key_excerpts": src.get("key_excerpts") or [],
                        "content": src.get("full_text", "") or "",
                    }
                )

            # Use ai_service to generate updated profile
            updated_profile = await self.ai_service.generate_signal_profile(
                signal_name=card_data.get("name", ""),
                signal_summary=card_data.get("summary", ""),
                pillar_id=card_data.get("pillar_id", ""),
                horizon=card_data.get("horizon", "H2"),
                source_analyses=source_analyses,
            )

            if updated_profile:
                update_data = {
                    "description": updated_profile,
                    "profile_generated_at": datetime.now(timezone.utc).isoformat(),
                    "profile_source_count": current_source_count,
                }

                # Analyze trend trajectory from source publication patterns
                try:
                    source_dates = [
                        s.get("ingested_at") or s.get("created_at", "")
                        for s in sources_resp.data
                    ]
                    source_summaries = [
                        s.get("ai_summary", "") for s in sources_resp.data
                    ]
                    trend = await self.ai_service.analyze_trend_trajectory(
                        signal_name=card_data.get("name", ""),
                        source_dates=source_dates,
                        source_summaries=source_summaries,
                    )
                    if trend and trend != "unknown":
                        update_data["trend_direction"] = trend
                        logger.info(f"Card {card_id}: trend trajectory = {trend}")
                except Exception as te:
                    logger.warning(f"Trend analysis failed for card {card_id}: {te}")

                self.supabase.table("cards").update(update_data).eq(
                    "id", card_id
                ).execute()

                # Log timeline event
                self.supabase.table("card_timeline").insert(
                    {
                        "card_id": card_id,
                        "event_type": "profile_updated",
                        "title": "Profile Updated",
                        "description": (
                            f"Profile auto-refreshed with {new_sources} new sources"
                        ),
                        "metadata": {
                            "new_sources": new_sources,
                            "total_sources": current_source_count,
                            "trend_direction": update_data.get("trend_direction"),
                        },
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                ).execute()

                logger.info(
                    f"Card {card_id}: profile refreshed "
                    f"({len(updated_profile)} chars)"
                )
        except Exception as e:
            logger.warning(f"Profile refresh failed for card {card_id}: {e}")

    # ========================================================================
    # Connection Discovery
    # ========================================================================

    async def _discover_connections(self, card_id: str) -> None:
        """Discover and create connections to related signals.

        Non-blocking: logs warnings on failure and continues.
        """
        try:
            from .connection_service import ConnectionService

            conn_service = ConnectionService(self.supabase, self.ai_service)
            count = await conn_service.discover_connections(card_id)
            if count > 0:
                logger.info(f"Card {card_id}: discovered {count} new connections")
        except Exception as e:
            logger.warning(f"Connection discovery failed for card {card_id}: {e}")

    # ========================================================================
    # Main Entry Points
    # ========================================================================

    async def execute_update(self, card_id: str, task_id: str) -> ResearchResult:
        """
        Execute quick update research for a card.

        Pipeline:
        1. Build municipal-focused query
        2. Discover sources with GPT Researcher + Serper
        3. Backfill missing content via unified crawler
        4. Triage for relevance
        5. Analyze relevant sources
        6. Store to existing card
        """
        logger.info(f"Starting update research for card {card_id} (task: {task_id})")

        # Get card details
        card_result = (
            self.supabase.table("cards")
            .select("name, summary")
            .eq("id", card_id)
            .single()
            .execute()
        )

        if not card_result.data:
            raise ValueError(f"Card not found: {card_id}")

        card = card_result.data

        # Step 1: Build customized query
        query = UPDATE_QUERY_TEMPLATE.format(
            name=card["name"], summary=card.get("summary", "")
        )

        # Step 2: Discover sources (GPT Researcher + Serper)
        sources, report, cost = await self._discover_sources(
            query=query, report_type="research_report"
        )

        # Step 3: Backfill missing content via unified crawler
        sources = await self._backfill_content(sources)

        # Step 4: Triage
        triaged = await self._triage_sources(sources[: self.MAX_SOURCES_UPDATE * 2])

        # Step 5: Analyze (limit to MAX_SOURCES_UPDATE)
        processed = await self._analyze_sources(triaged[: self.MAX_SOURCES_UPDATE])

        # Step 6: Store
        sources_added = 0
        for proc in processed:
            source_id = await self._store_source(card_id, proc)
            if source_id:
                sources_added += 1

        # Step 6b: Check if profile needs refresh (auto-regenerate after 3+ new sources)
        if sources_added > 0:
            await self._maybe_refresh_profile(card_id)
            await self._discover_connections(card_id)

        # Step 7: Enhance card with research insights (Level Up!)
        if sources_added > 0 or report:
            try:
                # Get full card details for enhancement
                full_card = (
                    self.supabase.table("cards")
                    .select("name, summary, description")
                    .eq("id", card_id)
                    .single()
                    .execute()
                )

                if full_card.data:
                    # Collect source summaries for enhancement
                    source_summaries = [
                        p.analysis.summary
                        for p in processed
                        if p.analysis and p.analysis.summary
                    ]

                    enhancement = await self.ai_service.enhance_card_from_research(
                        current_name=full_card.data["name"],
                        current_summary=full_card.data.get("summary", ""),
                        current_description=full_card.data.get("description", ""),
                        research_report=report or "",
                        source_summaries=source_summaries,
                    )

                    # Update card with enhanced content
                    self.supabase.table("cards").update(
                        {
                            "summary": enhancement.get(
                                "enhanced_summary", full_card.data.get("summary")
                            ),
                            "description": enhancement.get(
                                "enhanced_description",
                                full_card.data.get("description"),
                            ),
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }
                    ).eq("id", card_id).execute()

                    logger.info(
                        f"Card {card_id} enhanced with research insights: {enhancement.get('key_updates', [])}"
                    )
            except Exception as e:
                logger.warning(f"Card enhancement failed (research still saved): {e}")
                # Still update timestamp even if enhancement fails
                self.supabase.table("cards").update(
                    {"updated_at": datetime.now(timezone.utc).isoformat()}
                ).eq("id", card_id).execute()
        else:
            # Just update timestamp if no new sources
            self.supabase.table("cards").update(
                {"updated_at": datetime.now(timezone.utc).isoformat()}
            ).eq("id", card_id).execute()

        # Create summary timeline event
        await self._create_timeline_event(
            card_id=card_id,
            event_type="updated",
            description=f"Quick update: {sources_added} new sources from {len(sources)} discovered",
            metadata={
                "sources_found": len(sources),
                "sources_added": sources_added,
                "cost": cost,
            },
        )

        logger.info(
            f"Update research complete for card {card_id}: {sources_added} sources added from {len(sources)} discovered"
        )

        return ResearchResult(
            sources_found=len(sources),
            sources_relevant=len(triaged),
            sources_added=sources_added,
            cards_matched=[card_id],
            cards_created=[],
            entities_extracted=sum(
                len(p.analysis.entities) for p in processed if p.analysis
            ),
            cost_estimate=cost,
            report_preview=(
                report[:10000] if report else None
            ),  # Store up to 10KB of report
        )

    async def execute_deep_research(self, card_id: str, task_id: str) -> ResearchResult:
        """
        Execute comprehensive deep research for a card.

        Pipeline with Serper/trafilatura enhancement:
        1. Build comprehensive query
        2. Discover sources (GPT Researcher + Serper)
        3. Backfill missing content via unified crawler
        4. Triage for relevance
        5. Analyze relevant sources
        6. Store to existing card
        """
        logger.info(f"Starting deep research for card {card_id} (task: {task_id})")

        # Check rate limit
        if not await self.check_rate_limit(card_id):
            logger.warning(f"Rate limit exceeded for card {card_id}")
            raise Exception("Daily deep research limit reached (2 per day per card)")

        # Get card details
        card_result = (
            self.supabase.table("cards")
            .select("*")
            .eq("id", card_id)
            .single()
            .execute()
        )

        if not card_result.data:
            raise ValueError(f"Card not found: {card_id}")

        card = card_result.data

        # Step 1: Build comprehensive query
        query = DEEP_RESEARCH_QUERY_TEMPLATE.format(
            name=card["name"], summary=card.get("summary", "")
        )

        if source_prefs := card.get("source_preferences") or {}:
            steer_parts = []
            if priority_domains := source_prefs.get("priority_domains"):
                steer_parts.append(
                    f"Focus on sources from: {', '.join(priority_domains)}."
                )
            preferred_type = source_prefs.get("preferred_type")
            type_labels = {
                "federal": "federal government reports and .gov publications",
                "academic": "academic papers and research publications",
                "news": "news articles from reputable outlets",
                "blogs": "technology blog posts and analysis",
                "pdf": "PDF reports and whitepapers",
            }
            if preferred_type and preferred_type in type_labels:
                steer_parts.append(f"Prefer {type_labels[preferred_type]}.")
            if keywords := source_prefs.get("keywords"):
                steer_parts.append(f"Key topics to emphasize: {', '.join(keywords)}.")
            if steer_parts:
                query += "\n\n" + " ".join(steer_parts)

        # Step 1b: Fetch existing card sources to seed research
        existing_source_urls = []
        existing_source_context = []
        try:
            existing_sources_result = (
                self.supabase.table("sources")
                .select("url, title, ai_summary, full_text")
                .eq("card_id", card_id)
                .order("created_at", desc=True)
                .limit(20)
                .execute()
            )
            if existing_sources_result.data:
                for es in existing_sources_result.data:
                    if es.get("url"):
                        existing_source_urls.append(es["url"])
                    if es.get("ai_summary"):
                        existing_source_context.append(
                            {
                                "title": es.get("title", "Untitled"),
                                "url": es.get("url", ""),
                                "summary": es["ai_summary"],
                            }
                        )
                logger.info(
                    f"Found {len(existing_source_urls)} existing sources for card {card_id}"
                )
        except Exception as e:
            logger.warning(f"Failed to fetch existing sources: {e}")

        # Step 2: Discover sources (GPT Researcher + Serper - detailed report for more depth)
        sources, report, cost = await self._discover_sources(
            query=query,
            report_type="detailed_report",
            existing_source_urls=existing_source_urls or None,
        )

        # Step 3: Backfill missing content via unified crawler
        sources = await self._backfill_content(sources)

        # Step 4: Triage
        triaged = await self._triage_sources(sources)

        # Step 5: Analyze Round 1 sources
        processed = await self._analyze_sources(triaged[: self.MAX_SOURCES_DEEP])
        round_1_count = len(processed)

        # Step 5b: Multi-round research — identify gaps and run follow-up queries
        round_2_count = 0
        try:
            if report and len(processed) >= 3:
                round_1_summaries = [
                    p.analysis.summary
                    for p in processed
                    if p.analysis and p.analysis.summary
                ]
                follow_up_queries = await self.ai_service.generate_gap_analysis(
                    card_name=card["name"],
                    initial_report=report,
                    source_summaries=round_1_summaries,
                )
                if follow_up_queries:
                    logger.info(
                        f"Round 2: running {len(follow_up_queries)} follow-up queries"
                    )
                    # Combine follow-up queries into a single search
                    combined_query = " OR ".join(
                        f'"{q}"' for q in follow_up_queries[:3]
                    )
                    round_2_sources = await self._search_with_serper(
                        combined_query, max_results=10
                    )
                    if round_2_sources:
                        round_2_sources = await self._backfill_content(round_2_sources)
                        round_2_triaged = await self._triage_sources(round_2_sources)
                        round_2_processed = await self._analyze_sources(
                            round_2_triaged[:8]
                        )
                        round_2_count = len(round_2_processed)
                        processed.extend(round_2_processed)
                        logger.info(
                            f"Round 2 added {round_2_count} sources "
                            f"(total: {len(processed)})"
                        )
        except Exception as e:
            logger.warning(f"Multi-round research failed (continuing): {e}")

        # Step 6: Store
        sources_added = 0
        for proc in processed:
            source_id = await self._store_source(card_id, proc)
            if source_id:
                sources_added += 1

        # Step 6b: Check if profile needs refresh (auto-regenerate after 3+ new sources)
        if sources_added > 0:
            await self._maybe_refresh_profile(card_id)
            await self._discover_connections(card_id)

        # Calculate entities count and collect all entities
        entities_count = sum(len(p.analysis.entities) for p in processed if p.analysis)
        all_entities = []
        for p in processed:
            if p.analysis and p.analysis.entities:
                for ent in p.analysis.entities:
                    all_entities.append(
                        {
                            "name": ent.name,
                            "type": ent.entity_type,
                            "context": ent.context,
                        }
                    )

        # Step 7: Generate COMPREHENSIVE strategic intelligence report
        comprehensive_report = None
        try:
            source_analyses = [
                {
                    "title": p.raw.title,
                    "url": p.raw.url,  # Include URL for source citations
                    "source_name": p.raw.source_name,  # Include publication/source name
                    "summary": p.analysis.summary,
                    "key_excerpts": p.analysis.key_excerpts,
                    "relevance": p.analysis.relevance,
                }
                for p in processed
                if p.analysis
            ]
            # Include existing card sources in report context
            for ctx in existing_source_context:
                if ctx["url"] not in {s.get("url") for s in source_analyses}:
                    source_analyses.append(
                        {
                            "title": ctx["title"],
                            "url": ctx["url"],
                            "source_name": "Previously discovered",
                            "summary": ctx["summary"],
                            "key_excerpts": [],
                            "relevance": 0.8,
                        }
                    )
            # Step 7a: Source verification — cross-reference claims
            verification = {}
            try:
                verification = await self.ai_service.verify_source_claims(
                    source_analyses
                )
            except Exception as ve:
                logger.warning(f"Source verification skipped: {ve}")

            # Parse stage_id safely - it could be "4", "4_stage", "4_proof", etc.
            stage_id_raw = card.get("stage_id", "4") or "4"
            try:
                # Extract just the number from stage_id
                stage_num = int(
                    "".join(c for c in str(stage_id_raw) if c.isdigit()) or "4"
                )
            except (ValueError, TypeError):
                stage_num = 4

            comprehensive_report = await self.ai_service.generate_deep_research_report(
                card_name=card["name"],
                current_summary=card.get("summary", ""),
                current_description=card.get("description", ""),
                horizon=card.get("horizon", "H2"),
                stage=stage_num,
                pillar=card.get("pillar_id", ""),
                gpt_researcher_report=report or "",
                source_analyses=source_analyses,
                entities=all_entities,
            )
            # Append source confidence section from verification results
            if verification and comprehensive_report:
                confidence = verification.get("confidence_summary", "")
                verified = verification.get("verified_claims", [])
                single = verification.get("single_source_claims", [])
                contradictions = verification.get("contradictions", [])
                if confidence or verified or single or contradictions:
                    confidence_section = (
                        "\n\n---\n\n## Source Confidence Assessment\n\n"
                    )
                    if confidence:
                        confidence_section += f"{confidence}\n\n"
                    if verified:
                        confidence_section += (
                            "**Corroborated findings** (2+ sources):\n"
                        )
                        for v in verified[:5]:
                            confidence_section += f"- {v.get('claim', '')}\n"
                        confidence_section += "\n"
                    if single:
                        confidence_section += (
                            "**Single-source claims** (lower confidence):\n"
                        )
                        for s in single[:5]:
                            confidence_section += (
                                f"- \\[Single Source\\] {s.get('claim', '')}\n"
                            )
                        confidence_section += "\n"
                    if contradictions:
                        confidence_section += "**Contested findings**:\n"
                        for c in contradictions[:3]:
                            confidence_section += (
                                f"- \\[Contested\\] {c.get('claim_a', '')} "
                                f"vs. {c.get('claim_b', '')}\n"
                            )
                    comprehensive_report += confidence_section

            # Append round metadata if multi-round research was performed
            if round_2_count > 0 and comprehensive_report:
                comprehensive_report += (
                    f"\n\n---\n\n*Research conducted in 2 rounds: "
                    f"Round 1 ({round_1_count} sources), "
                    f"Round 2 ({round_2_count} follow-up sources)*\n"
                )

            logger.info(
                f"Generated comprehensive report ({len(comprehensive_report)} chars) for card {card_id}"
            )
        except Exception as e:
            logger.warning(f"Comprehensive report generation failed: {e}")
            # Fallback: try to generate a minimal report from source analyses
            if source_analyses:
                try:
                    # Generate a simpler report with just source summaries
                    fallback_report = f"""# Deep Research Report: {card["name"]}

**Generated:** {datetime.now(timezone.utc).strftime('%B %d, %Y at %I:%M %p')}
**Sources Analyzed:** {len(source_analyses)}

---

## EXECUTIVE SUMMARY

Research analyzed {len(source_analyses)} sources related to {card["name"]}.

## KEY FINDINGS

"""
                    for i, src in enumerate(source_analyses[:10], 1):
                        title = src.get("title", "Untitled")
                        url = src.get("url", "")
                        # Format as clickable link if URL available
                        if url and url.startswith(("http://", "https://")):
                            fallback_report += f"### {i}. [{title}]({url})\n\n"
                        else:
                            fallback_report += f"### {i}. {title}\n\n"
                        fallback_report += (
                            f"{src.get('summary', 'No summary available.')}\n\n"
                        )

                    # Add sources section
                    fallback_report += "\n---\n\n## Sources Cited\n\n"
                    for i, src in enumerate(source_analyses[:10], 1):
                        title = src.get("title", "Untitled")
                        url = src.get("url", "")
                        source_name = src.get("source_name", "")
                        if url and url.startswith(("http://", "https://")):
                            entry = f"{i}. [{title}]({url})"
                        else:
                            entry = f"{i}. {title}"
                        if source_name:
                            entry += f" — *{source_name}*"
                        fallback_report += entry + "\n"

                    comprehensive_report = fallback_report
                    logger.info(
                        f"Generated fallback report from {len(source_analyses)} source analyses"
                    )
                except Exception as e2:
                    logger.error(f"Fallback report generation also failed: {e2}")
                    comprehensive_report = (
                        report  # Use GPT Researcher report as last resort
                    )
            else:
                comprehensive_report = (
                    report  # Use GPT Researcher report if no source analyses
                )

        # Step 8: Enhance card with research insights
        try:
            source_summaries = [
                p.analysis.summary
                for p in processed
                if p.analysis and p.analysis.summary
            ]

            enhancement = await self.ai_service.enhance_card_from_research(
                current_name=card["name"],
                current_summary=card.get("summary", ""),
                current_description=card.get("description", ""),
                research_report=report or "",
                source_summaries=source_summaries,
            )

            # Update card with enhanced content and timestamps
            self.supabase.table("cards").update(
                {
                    "summary": enhancement.get("enhanced_summary", card.get("summary")),
                    "description": enhancement.get(
                        "enhanced_description", card.get("description")
                    ),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "deep_research_at": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("id", card_id).execute()

            logger.info(
                f"Card {card_id} enhanced with deep research insights: {enhancement.get('key_updates', [])}"
            )
        except Exception as e:
            logger.warning(f"Card enhancement failed (research still saved): {e}")
            # Still update timestamps even if enhancement fails
            self.supabase.table("cards").update(
                {
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "deep_research_at": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("id", card_id).execute()

        # Increment rate limit
        await self.increment_research_count(card_id)

        # Create timeline event with the COMPREHENSIVE strategic report
        await self._create_timeline_event(
            card_id=card_id,
            event_type="deep_research",
            description=f"Deep research completed: {sources_added} sources analyzed from {len(sources)} discovered",
            metadata={
                "sources_found": len(sources),
                "sources_relevant": len(triaged),
                "sources_added": sources_added,
                "entities_extracted": entities_count,
                "cost": cost,
                "research_rounds": 2 if round_2_count > 0 else 1,
                "round_1_sources": round_1_count,
                "round_2_sources": round_2_count,
                "verification_summary": (
                    verification.get("confidence_summary") if verification else None
                ),
                "detailed_report": (
                    comprehensive_report[:50000] if comprehensive_report else None
                ),
            },
        )

        logger.info(
            f"Deep research complete for card {card_id}: {sources_added} sources added, {entities_count} entities extracted"
        )

        return ResearchResult(
            sources_found=len(sources),
            sources_relevant=len(triaged),
            sources_added=sources_added,
            cards_matched=[card_id],
            cards_created=[],
            entities_extracted=entities_count,
            cost_estimate=cost,
            report_preview=(
                comprehensive_report[:50000] if comprehensive_report else None
            ),  # Full report with sources section
        )

    async def execute_workstream_analysis(
        self, workstream_id: str, task_id: str, user_id: str
    ) -> ResearchResult:
        """
        Analyze a workstream and find/create relevant cards.

        Pipeline with Serper/crawler enhancement:
        1. Build workstream query
        2. Discover sources (GPT Researcher + Serper)
        3. Backfill missing content via unified crawler
        4. Triage for relevance
        5. Analyze relevant sources
        6. Match or create cards
        """
        logger.info(
            f"Starting workstream analysis for {workstream_id} (task: {task_id})"
        )

        # Get workstream details
        ws_result = (
            self.supabase.table("workstreams")
            .select("*")
            .eq("id", workstream_id)
            .single()
            .execute()
        )

        if not ws_result.data:
            raise ValueError(f"Workstream not found: {workstream_id}")

        ws = ws_result.data
        keywords = ws.get("keywords", [])

        # Step 1: Build workstream query
        query = WORKSTREAM_QUERY_TEMPLATE.format(
            name=ws.get("name", ""),
            keywords_list=", ".join(keywords) if keywords else "emerging technologies",
            description=ws.get("description", ""),
        )

        # Step 2: Discover sources (GPT Researcher + Serper)
        sources, report, cost = await self._discover_sources(
            query=query, report_type="research_report"
        )

        # Step 3: Backfill missing content via unified crawler
        sources = await self._backfill_content(sources)

        # Step 4: Triage
        triaged = await self._triage_sources(sources)

        # Step 5: Analyze
        processed = await self._analyze_sources(triaged[:15])

        # Step 6: Match or create cards
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

            elif should_create and proc.analysis:
                # Create new card
                try:
                    new_card_id = await self._create_card(proc, created_by=user_id)
                    await self._store_source(new_card_id, proc)
                    cards_created.append(new_card_id)
                    sources_added += 1
                    logger.info(
                        f"Created new card: {proc.analysis.suggested_card_name}"
                    )
                except Exception as e:
                    logger.error(f"Failed to create card: {e}")

        logger.info(
            f"Workstream analysis complete for {workstream_id}: matched {len(cards_matched)} cards, created {len(cards_created)} new cards"
        )

        return ResearchResult(
            sources_found=len(sources),
            sources_relevant=len(triaged),
            sources_added=sources_added,
            cards_matched=cards_matched,
            cards_created=cards_created,
            entities_extracted=sum(
                len(p.analysis.entities) for p in processed if p.analysis
            ),
            cost_estimate=cost,
            report_preview=report[:10000] if report else None,  # Store full report
        )
