"""
Executive Brief Service for Foresight Application.

This service generates comprehensive executive briefs for strategic cards,
synthesizing card data, user notes, related cards, and source materials
into leadership-ready briefings with an Austin-specific perspective.

The brief generation is async - it creates a record immediately and processes
in the background, allowing the frontend to poll for completion.

Key Features:
- Austin-focused strategic intelligence perspective
- 800-1500 word comprehensive briefs
- Token usage tracking for cost monitoring
- Generation time tracking for performance monitoring
- Integration with workstream Kanban workflow
- Retry logic with exponential backoff for API resilience
"""

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from functools import wraps
from dataclasses import dataclass
from supabase import Client
import openai

# Azure OpenAI deployment names
from app.openai_provider import get_chat_deployment

logger = logging.getLogger(__name__)


# ============================================================================
# Retry Configuration (matches ai_service.py patterns)
# ============================================================================

MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds
BACKOFF_MULTIPLIER = 2.0
REQUEST_TIMEOUT = 120  # seconds - longer for comprehensive briefs


def with_retry(max_retries: int = MAX_RETRIES):
    """
    Decorator for retrying async functions with exponential backoff.

    Handles OpenAI API errors and rate limits gracefully.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            backoff = INITIAL_BACKOFF

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except openai.RateLimitError as e:
                    last_exception = e
                    wait_time = backoff * (BACKOFF_MULTIPLIER ** attempt)
                    logger.warning(
                        f"Rate limited on {func.__name__}, "
                        f"retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                except openai.APITimeoutError as e:
                    last_exception = e
                    wait_time = backoff * (BACKOFF_MULTIPLIER ** attempt)
                    logger.warning(
                        f"Timeout on {func.__name__}, "
                        f"retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                except openai.APIConnectionError as e:
                    last_exception = e
                    wait_time = backoff * (BACKOFF_MULTIPLIER ** attempt)
                    logger.warning(
                        f"Connection error on {func.__name__}, "
                        f"retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                except openai.APIStatusError as e:
                    # Don't retry on 4xx errors (except 429 which is RateLimitError)
                    if 400 <= e.status_code < 500:
                        logger.error(f"API error on {func.__name__}: {e.status_code} - {e.message}")
                        raise
                    last_exception = e
                    wait_time = backoff * (BACKOFF_MULTIPLIER ** attempt)
                    logger.warning(
                        f"API error on {func.__name__}, "
                        f"retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)

            logger.error(f"All {max_retries} retries exhausted for {func.__name__}")
            raise last_exception

        return wrapper
    return decorator


# ============================================================================
# Executive Brief Prompt (Austin-focused, comprehensive)
# ============================================================================

EXECUTIVE_BRIEF_PROMPT = """You are a strategic advisor preparing a comprehensive leadership briefing for City of Austin decision-makers.

Generate an executive brief on "{card_name}" that a City Manager could read on the car ride to an interview and sound knowledgeable about this topic. This brief should synthesize all available information into actionable intelligence with an Austin-specific perspective.

---

## CARD INFORMATION
Name: {card_name}
Summary: {summary}
Description: {description}
Pillar: {pillar}
Horizon: {horizon}
Stage: {stage}
Scores: Novelty={novelty}/100, Impact={impact}/100, Relevance={relevance}/100, Risk={risk}/100

## USER CONTEXT & NOTES
Workstream: {workstream_name}
Workstream Description: {workstream_description}
User Notes on Card: {user_notes}

## RELATED INTELLIGENCE
{related_cards_summary}

## SOURCE MATERIALS
{source_excerpts}

---

Create an executive brief with these sections:

## EXECUTIVE SUMMARY
(3-4 sentences capturing what this is, why it matters to Austin, and the key takeaway for leadership)

## VALUE PROPOSITION FOR AUSTIN
- What specific value does this offer the City of Austin?
- How does it align with Austin's strategic priorities?
- What problem does it solve or opportunity does it create?

## KEY TALKING POINTS
(5-7 bullet points a leader could use in conversation - clear, memorable, quotable)

## CURRENT LANDSCAPE
- Where is this in terms of maturity and adoption?
- Who are the key players and what are peer cities doing?
- What's the trajectory - accelerating, stable, or declining?

## AUSTIN-SPECIFIC CONSIDERATIONS
- How does this intersect with Austin's unique context (growth, tech hub, equity focus)?
- Which city departments or initiatives would this affect?
- What existing Austin programs or infrastructure does this relate to?

## STRATEGIC IMPLICATIONS
- What decisions or preparations should city leadership consider?
- What happens if Austin acts vs. waits?
- What's the cost of inaction?

## RISK FACTORS & CONCERNS
- What could go wrong or what challenges exist?
- What are the equity, privacy, or political considerations?
- What unknowns or uncertainties should leadership be aware of?

## RECOMMENDED ACTIONS
(3-5 numbered, specific, actionable recommendations prioritized by urgency)

## TIMELINE & URGENCY
- How urgent is this? What's the decision window?
- What signals should Austin watch for?

---

Guidelines:
- Write for a busy executive who needs to sound informed in 10 minutes
- Be SPECIFIC with examples, numbers, and city names where available
- Frame everything through Austin's lens and priorities
- Include concrete talking points that could be quoted
- Use plain language - no jargon or acronyms without explanation
- If information is limited, acknowledge gaps and focus on what IS known
- Total length: 800-1500 words depending on available information
"""


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class BriefGenerationResult:
    """Result of brief generation operation."""
    content_markdown: str
    summary: str
    content_json: Dict[str, Any]
    prompt_tokens: int
    completion_tokens: int
    model_used: str


@dataclass
class PortfolioSynthesis:
    """
    AI-synthesized content for portfolio/bulk brief exports.
    
    Generated by analyzing multiple briefs together to create
    executive overview, cross-cutting themes, and prioritized recommendations.
    """
    executive_overview: str  # 2-3 paragraph synthesis of all cards
    key_themes: List[str]  # 3-5 common themes across cards
    priority_matrix: Dict[str, Any]  # Cards organized by impact/urgency
    cross_cutting_insights: List[str]  # Connections between cards
    recommended_actions: List[Dict[str, str]]  # Prioritized next steps with owners
    # New fields for enhanced portfolio presentations
    urgency_statement: str = ""  # Why this portfolio demands attention now
    implementation_guidance: Dict[str, List[str]] = None  # Cards by action type
    ninety_day_actions: List[Dict[str, str]] = None  # Concrete near-term actions
    risk_summary: str = ""  # Top risks if Austin doesn't act
    opportunity_summary: str = ""  # Top opportunities if Austin leads
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model_used: str = ""
    
    def __post_init__(self):
        if self.implementation_guidance is None:
            self.implementation_guidance = {}
        if self.ninety_day_actions is None:
            self.ninety_day_actions = []


@dataclass 
class PortfolioBrief:
    """A brief with its associated card data for portfolio generation."""
    card_id: str
    card_name: str
    pillar_id: str
    horizon: str
    stage_id: str
    brief_summary: str
    brief_content_markdown: str
    impact_score: int
    relevance_score: int
    velocity_score: int


# ============================================================================
# Helper Functions
# ============================================================================

def sections_to_markdown(sections: List[Dict[str, Any]], title: str = "") -> str:
    """Convert sections list to markdown format."""
    md_parts = []
    if title:
        md_parts.append(f"# {title}\n")

    for section in sorted(sections, key=lambda s: s.get("order", 0)):
        md_parts.append(f"## {section['title']}\n")
        md_parts.append(section["content"])
        md_parts.append("")

    return "\n".join(md_parts)


def get_stage_name(stage_id: Optional[str]) -> str:
    """Convert stage_id to human-readable name."""
    if not stage_id:
        return "Unknown"

    stage_map = {
        "1": "Concept (academic/theoretical)",
        "2": "Emerging (startups, VC interest)",
        "3": "Prototype (working demos)",
        "4": "Pilot (real-world testing)",
        "5": "Municipal Pilot (government testing)",
        "6": "Early Adoption (multiple cities)",
        "7": "Mainstream (widespread adoption)",
        "8": "Mature (established)"
    }

    # Handle formats like "5_implementing" or just "5"
    stage_num = stage_id.split("_")[0] if "_" in stage_id else stage_id
    return stage_map.get(stage_num, stage_id)


def get_pillar_name(pillar_id: Optional[str]) -> str:
    """Convert pillar_id to human-readable name."""
    if not pillar_id:
        return "Unknown"

    pillar_map = {
        "CH": "Community Health & Sustainability",
        "EW": "Economic & Workforce Development",
        "HG": "High-Performing Government",
        "HH": "Homelessness & Housing",
        "MC": "Mobility & Critical Infrastructure",
        "PS": "Public Safety"
    }

    return pillar_map.get(pillar_id, pillar_id)


def extract_executive_summary(content: str) -> str:
    """
    Extract the executive summary section from the brief.

    Args:
        content: Full brief markdown content

    Returns:
        Executive summary text (first 500 chars if section not found)
    """
    # Look for executive summary section
    pattern = r'##\s*EXECUTIVE\s*SUMMARY\s*\n(.*?)(?=\n##|\Z)'
    match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)

    if match:
        summary = match.group(1).strip()
        # Clean up and limit length
        summary = summary.replace('\n', ' ').strip()
        if len(summary) > 500:
            summary = summary[:497] + "..."
        return summary

    # Fallback: first paragraph
    paragraphs = content.split('\n\n')
    for p in paragraphs:
        p = p.strip()
        if p and not p.startswith('#'):
            if len(p) > 500:
                return p[:497] + "..."
            return p

    return content[:500] + "..." if len(content) > 500 else content


def parse_brief_sections(content: str) -> Dict[str, Any]:
    """
    Parse brief markdown into structured sections.

    Args:
        content: Full brief markdown content

    Returns:
        Dict with sections array and metadata
    """
    sections = []
    current_section = None
    current_content = []

    for line in content.split('\n'):
        # Check for section header (## SECTION NAME)
        if line.startswith('## '):
            # Save previous section
            if current_section:
                sections.append({
                    "title": current_section,
                    "content": '\n'.join(current_content).strip(),
                    "order": len(sections)
                })
            current_section = line[3:].strip()
            current_content = []
        elif current_section:
            current_content.append(line)

    # Save last section
    if current_section:
        sections.append({
            "title": current_section,
            "content": '\n'.join(current_content).strip(),
            "order": len(sections)
        })

    return {
        "sections": sections,
        "section_count": len(sections),
        "word_count": len(content.split())
    }


# ============================================================================
# Executive Brief Service
# ============================================================================

class ExecutiveBriefService:
    """
    Service for generating executive briefs for strategic cards.

    Handles async brief generation with background processing,
    status tracking, AI-powered content synthesis, and comprehensive
    metadata tracking for monitoring and cost analysis.
    """

    def __init__(self, supabase: Client, openai_client: openai.AsyncOpenAI):
        """
        Initialize the ExecutiveBriefService.

        Args:
            supabase: Supabase client for database operations
            openai_client: AsyncOpenAI client for AI generation
        """
        self.supabase = supabase
        self.openai_client = openai_client

    # ========================================================================
    # Brief CRUD Operations
    # ========================================================================

    async def create_brief_record(
        self,
        workstream_card_id: str,
        card_id: str,
        user_id: str,
        sources_since_previous: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create initial brief record with pending status.

        Automatically increments version number based on existing briefs
        for this workstream card.

        Args:
            workstream_card_id: ID of the workstream_cards record
            card_id: ID of the card to generate brief for
            user_id: ID of the requesting user
            sources_since_previous: Metadata about new sources since last brief

        Returns:
            Created brief record with version number
        """
        # Get the next version number
        version_result = self.supabase.table("executive_briefs").select(
            "version"
        ).eq("workstream_card_id", workstream_card_id).order(
            "version", desc=True
        ).limit(1).execute()

        next_version = 1
        if version_result.data:
            next_version = version_result.data[0]["version"] + 1

        now = datetime.utcnow().isoformat()
        brief_record = {
            "workstream_card_id": workstream_card_id,
            "card_id": card_id,
            "created_by": user_id,
            "status": "pending",
            "version": next_version,
            "sources_since_previous": sources_since_previous,
            "created_at": now,
            "updated_at": now
        }

        result = self.supabase.table("executive_briefs").insert(brief_record).execute()

        if not result.data:
            raise Exception("Failed to create brief record")

        logger.info(f"Created brief record version {next_version} for workstream_card {workstream_card_id}")
        return result.data[0]

    async def get_brief(self, brief_id: str) -> Optional[Dict[str, Any]]:
        """
        Get brief by ID.

        Args:
            brief_id: Brief identifier

        Returns:
            Brief record or None
        """
        result = self.supabase.table("executive_briefs").select("*").eq(
            "id", brief_id
        ).execute()

        return result.data[0] if result.data else None

    async def get_brief_by_workstream_card(
        self,
        workstream_card_id: str,
        version: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get brief for a specific workstream card.

        Returns the latest version by default, or a specific version if provided.

        Args:
            workstream_card_id: Workstream card identifier
            version: Optional specific version number to retrieve

        Returns:
            Brief record or None
        """
        query = self.supabase.table("executive_briefs").select("*").eq(
            "workstream_card_id", workstream_card_id
        )

        if version is not None:
            query = query.eq("version", version)
        else:
            # Get the latest version (highest version number)
            query = query.order("version", desc=True).limit(1)

        result = query.execute()
        return result.data[0] if result.data else None

    async def get_brief_versions(
        self,
        workstream_card_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all brief versions for a workstream card.

        Returns versions ordered by version number descending (newest first).

        Args:
            workstream_card_id: Workstream card identifier

        Returns:
            List of brief records (without full content for efficiency)
        """
        result = self.supabase.table("executive_briefs").select(
            "id, version, status, summary, sources_since_previous, "
            "generated_at, created_at, model_used"
        ).eq(
            "workstream_card_id", workstream_card_id
        ).order("version", desc=True).execute()

        return result.data if result.data else []

    async def get_latest_completed_brief(
        self,
        workstream_card_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get the most recent completed brief for a workstream card.

        Used to determine the timestamp for filtering new sources.

        Args:
            workstream_card_id: Workstream card identifier

        Returns:
            Latest completed brief or None
        """
        result = self.supabase.table("executive_briefs").select(
            "id, version, generated_at"
        ).eq(
            "workstream_card_id", workstream_card_id
        ).eq(
            "status", "completed"
        ).order("version", desc=True).limit(1).execute()

        return result.data[0] if result.data else None

    async def get_brief_status(self, brief_id: str) -> Optional[Dict[str, Any]]:
        """
        Get lightweight brief status for polling.

        Args:
            brief_id: Brief identifier

        Returns:
            Status data or None
        """
        result = self.supabase.table("executive_briefs").select(
            "id, status, version, summary, error_message, generated_at"
        ).eq("id", brief_id).execute()

        return result.data[0] if result.data else None

    async def update_brief_status(
        self,
        brief_id: str,
        status: str,
        error_message: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        Update brief status and optional fields.

        Args:
            brief_id: Brief identifier
            status: New status (pending, generating, completed, failed)
            error_message: Error message if failed
            **kwargs: Additional fields to update
        """
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        }

        if error_message:
            update_data["error_message"] = error_message

        update_data.update(kwargs)

        self.supabase.table("executive_briefs").update(update_data).eq(
            "id", brief_id
        ).execute()

    # ========================================================================
    # Context Gathering
    # ========================================================================

    async def _gather_card_context(self, card_id: str) -> Dict[str, Any]:
        """
        Gather all card data for brief generation.

        Args:
            card_id: Card identifier

        Returns:
            Card data with all relevant fields
        """
        result = self.supabase.table("cards").select("*").eq(
            "id", card_id
        ).execute()

        if not result.data:
            raise ValueError(f"Card not found: {card_id}")

        return result.data[0]

    async def _gather_workstream_context(
        self,
        workstream_card_id: str
    ) -> Dict[str, Any]:
        """
        Gather workstream and workstream_card context.

        Args:
            workstream_card_id: Workstream card identifier

        Returns:
            Dict with workstream info and user notes
        """
        # Get workstream_card with workstream details
        wsc_result = self.supabase.table("workstream_cards").select(
            "*, workstreams(id, name, description)"
        ).eq("id", workstream_card_id).execute()

        if not wsc_result.data:
            return {
                "workstream_name": "Unknown Workstream",
                "workstream_description": "",
                "user_notes": ""
            }

        wsc = wsc_result.data[0]
        workstream = wsc.get("workstreams", {}) or {}

        return {
            "workstream_name": workstream.get("name", "Unknown Workstream"),
            "workstream_description": workstream.get("description", ""),
            "user_notes": wsc.get("notes", "") or ""
        }

    async def _gather_related_cards(self, card_id: str, limit: int = 5) -> str:
        """
        Gather related cards summary for context.

        Args:
            card_id: Card identifier
            limit: Maximum number of related cards

        Returns:
            Formatted string with related cards summary
        """
        # Try to find related cards through card_relationships table
        result = self.supabase.table("card_relationships").select(
            "target_card_id, relationship_type, strength"
        ).eq("source_card_id", card_id).order(
            "strength", desc=True
        ).limit(limit).execute()

        if not result.data:
            return "No related cards identified."

        # Fetch details for related cards
        related_ids = [r["target_card_id"] for r in result.data]
        cards_result = self.supabase.table("cards").select(
            "id, name, summary, pillar_id, horizon"
        ).in_("id", related_ids).execute()

        if not cards_result.data:
            return "No related cards identified."

        # Build summary
        lines = []
        card_map = {c["id"]: c for c in cards_result.data}
        for rel in result.data:
            card = card_map.get(rel["target_card_id"])
            if card:
                summary_text = card.get('summary', 'No summary')
                if summary_text and len(summary_text) > 150:
                    summary_text = summary_text[:147] + "..."
                lines.append(
                    f"- **{card['name']}** ({rel['relationship_type']}, "
                    f"strength: {rel.get('strength', 0):.0%}): {summary_text}"
                )

        return "\n".join(lines) if lines else "No related cards identified."

    async def _gather_source_materials(
        self,
        card_id: str,
        limit: int = 10,
        since_timestamp: Optional[str] = None
    ) -> tuple[str, int]:
        """
        Gather source materials/excerpts for the card.

        Args:
            card_id: Card identifier
            limit: Maximum number of sources
            since_timestamp: Optional ISO timestamp to filter sources created after

        Returns:
            Tuple of (formatted string with source excerpts, count of sources)
        """
        query = self.supabase.table("discovered_sources").select(
            "title, url, domain, analysis_summary, analysis_key_excerpts, created_at"
        ).eq("resulting_card_id", card_id)

        if since_timestamp:
            query = query.gt("created_at", since_timestamp)

        result = query.order("created_at", desc=True).limit(limit).execute()

        if not result.data:
            if since_timestamp:
                return "No new source materials since last brief.", 0
            return "No source materials available.", 0

        lines = []
        for src in result.data:
            title = src.get("title", "Untitled")
            if len(title) > 80:
                title = title[:77] + "..."
            source = src.get("domain", "Unknown")
            summary = src.get("analysis_summary", "")
            if summary and len(summary) > 200:
                summary = summary[:197] + "..."
            url = src.get("url", "")

            line = f"- **{title}** ({source})"
            if summary:
                line += f": {summary}"
            if url:
                line += f" [Source: {url}]"
            lines.append(line)

        return "\n".join(lines) if lines else "No source materials available.", len(result.data)

    async def count_new_sources(
        self,
        card_id: str,
        since_timestamp: str
    ) -> int:
        """
        Count sources discovered since a given timestamp.

        Args:
            card_id: Card identifier
            since_timestamp: ISO timestamp to count sources after

        Returns:
            Count of new sources
        """
        result = self.supabase.table("discovered_sources").select(
            "id", count="exact"
        ).eq("resulting_card_id", card_id).gt(
            "created_at", since_timestamp
        ).execute()

        return result.count if result.count else 0

    # ========================================================================
    # Brief Generation
    # ========================================================================

    @with_retry(max_retries=MAX_RETRIES)
    async def _generate_brief_content(
        self,
        card: Dict[str, Any],
        workstream_context: Dict[str, Any],
        related_cards: str,
        source_materials: str
    ) -> BriefGenerationResult:
        """
        Generate brief content using OpenAI API.

        Args:
            card: Card data
            workstream_context: Workstream and notes context
            related_cards: Related cards summary string
            source_materials: Source excerpts string

        Returns:
            BriefGenerationResult with content and metadata
        """
        # Build the prompt
        prompt = EXECUTIVE_BRIEF_PROMPT.format(
            card_name=card.get("name", "Unknown"),
            summary=card.get("summary", "No summary available"),
            description=card.get("description", "No description available"),
            pillar=get_pillar_name(card.get("pillar_id")),
            horizon=card.get("horizon", "Unknown"),
            stage=get_stage_name(card.get("stage_id")),
            novelty=card.get("novelty_score", 0) or 0,
            impact=card.get("impact_score", 0) or 0,
            relevance=card.get("relevance_score", 0) or 0,
            risk=card.get("risk_score", 0) or 0,
            workstream_name=workstream_context.get("workstream_name", "Unknown"),
            workstream_description=workstream_context.get("workstream_description", ""),
            user_notes=workstream_context.get("user_notes", "No notes provided"),
            related_cards_summary=related_cards,
            source_excerpts=source_materials
        )

        logger.info(f"Generating executive brief for card: {card.get('name', 'Unknown')}")

        # Get Azure deployment name for chat completions
        model_deployment = get_chat_deployment()

        # Call Azure OpenAI API (synchronous client)
        response = self.openai_client.chat.completions.create(
            model=model_deployment,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a strategic advisor for the City of Austin. "
                        "Generate comprehensive, actionable executive briefs in clear markdown format."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=4000,
            temperature=0.7,
            timeout=REQUEST_TIMEOUT
        )

        content_markdown = response.choices[0].message.content

        # Extract executive summary for quick display
        summary = extract_executive_summary(content_markdown)

        # Parse sections into structured format
        content_json = parse_brief_sections(content_markdown)

        return BriefGenerationResult(
            content_markdown=content_markdown,
            summary=summary,
            content_json=content_json,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            model_used=model_deployment
        )

    async def generate_executive_brief(
        self,
        brief_id: str,
        workstream_card_id: str,
        card_id: str,
        since_timestamp: Optional[str] = None
    ) -> None:
        """
        Generate executive brief content (runs in background).

        This is the main entry point for brief generation, called
        asynchronously after creating the brief record.

        Args:
            brief_id: Brief identifier to update
            workstream_card_id: Workstream card identifier for context
            card_id: Card to generate brief for
            since_timestamp: Optional timestamp to filter sources (for regeneration)
        """
        start_time = time.time()

        try:
            # Update status to generating
            await self.update_brief_status(brief_id, "generating")

            # Gather all context
            card = await self._gather_card_context(card_id)
            workstream_context = await self._gather_workstream_context(workstream_card_id)
            related_cards = await self._gather_related_cards(card_id)
            source_materials, source_count = await self._gather_source_materials(
                card_id, since_timestamp=since_timestamp
            )

            # Generate the brief
            result = await self._generate_brief_content(
                card=card,
                workstream_context=workstream_context,
                related_cards=related_cards,
                source_materials=source_materials
            )

            # Calculate generation time
            generation_time_ms = int((time.time() - start_time) * 1000)

            # Update brief with generated content
            await self.update_brief_status(
                brief_id,
                "completed",
                content=result.content_json,
                content_markdown=result.content_markdown,
                summary=result.summary,
                generated_at=datetime.utcnow().isoformat(),
                generation_time_ms=generation_time_ms,
                model_used=result.model_used,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens
            )

            logger.info(
                f"Successfully generated brief {brief_id} for card {card_id} "
                f"in {generation_time_ms}ms ({result.prompt_tokens + result.completion_tokens} tokens)"
            )

        except Exception as e:
            logger.error(f"Failed to generate brief {brief_id}: {str(e)}")
            generation_time_ms = int((time.time() - start_time) * 1000)
            await self.update_brief_status(
                brief_id,
                "failed",
                error_message=str(e),
                generation_time_ms=generation_time_ms
            )

    # =========================================================================
    # Portfolio Synthesis (for Bulk Brief Export)
    # =========================================================================

    @with_retry(max_retries=MAX_RETRIES)
    async def synthesize_portfolio(
        self,
        briefs: List[PortfolioBrief],
        workstream_name: str
    ) -> PortfolioSynthesis:
        """
        Generate AI-synthesized content for a portfolio of briefs.
        
        Uses GPT-4 to analyze multiple briefs together and create:
        - Executive overview synthesizing all cards
        - Key themes across the portfolio
        - Priority matrix (impact vs urgency)
        - Cross-cutting insights and connections
        - Recommended actions with ownership
        
        Args:
            briefs: List of PortfolioBrief objects in display order
            workstream_name: Name of the workstream for context
            
        Returns:
            PortfolioSynthesis with all synthesized content
        """
        if not briefs:
            raise ValueError("Cannot synthesize empty portfolio")
        
        # Build context for each card
        card_summaries = []
        for i, brief in enumerate(briefs, 1):
            pillar_name = get_pillar_name(brief.pillar_id)
            horizon_name = f"H{brief.horizon[-1]}" if brief.horizon else "Unknown"
            stage_name = get_stage_name(brief.stage_id)
            
            card_summaries.append(f"""
### Card {i}: {brief.card_name}
- **Pillar**: {pillar_name} ({brief.pillar_id})
- **Horizon**: {horizon_name}
- **Stage**: {stage_name}
- **Impact Score**: {brief.impact_score}/100
- **Relevance Score**: {brief.relevance_score}/100
- **Velocity Score**: {brief.velocity_score}/100

**Summary**: {brief.brief_summary}

**Key Content**:
{brief.brief_content_markdown[:2000]}...
""")
        
        cards_context = "\n---\n".join(card_summaries)
        
        system_prompt = """You are a senior strategic analyst for the City of Austin, Texas. 
You synthesize multiple strategic intelligence briefs into executive-ready portfolio summaries.

Your analysis should be:
- Decision-oriented: Help leadership decide what to prioritize
- Implementation-focused: Tell them exactly what to DO with each trend
- Comparative: Show how trends relate to each other
- Austin-specific: Frame everything in terms of city impact
- Actionable: Provide concrete next steps, not vague recommendations

Output your analysis as valid JSON matching the specified structure."""

        user_prompt = f"""Analyze this portfolio of {len(briefs)} strategic intelligence briefs for the "{workstream_name}" workstream.

{cards_context}

Generate a comprehensive portfolio synthesis as JSON with this exact structure:
{{
    "executive_overview": "2-3 paragraphs synthesizing what leadership needs to know about these {len(briefs)} trends together. What's the big picture? How do they connect? What decisions need to be made?",
    
    "urgency_statement": "A compelling 2-3 sentence statement about why this portfolio demands attention NOW. What window of opportunity is closing? What risks are accelerating?",
    
    "key_themes": [
        "Theme 1: A common thread across multiple cards",
        "Theme 2: Another pattern you've identified",
        "Theme 3: etc (provide 3-5 themes)"
    ],
    
    "priority_matrix": {{
        "high_impact_urgent": ["Card names that need immediate attention"],
        "high_impact_strategic": ["Card names important but longer-term"],
        "monitor": ["Card names to watch but not act on yet"],
        "rationale": "Brief explanation of how you prioritized"
    }},
    
    "implementation_guidance": {{
        "pilot_now": ["Card names ready for small-scale testing - technology is mature enough"],
        "investigate_further": ["Card names needing more research before action"],
        "meet_with_vendors": ["Card names where vendor evaluation is the logical next step"],
        "policy_review": ["Card names requiring regulatory or policy analysis"],
        "staff_training": ["Card names where workforce readiness is the priority"],
        "budget_planning": ["Card names ready for larger deployment planning"]
    }},
    
    "cross_cutting_insights": [
        "Insight 1: How Card X connects to Card Y",
        "Insight 2: Resource implications across multiple cards",
        "Insight 3: etc (provide 3-5 insights)"
    ],
    
    "recommended_actions": [
        {{"action": "Specific action to take", "owner": "Department or role", "timeline": "Q1 2025", "cards": ["Related card names"]}},
        {{"action": "Another action", "owner": "Owner", "timeline": "Timeline", "cards": ["Cards"]}}
    ],
    
    "ninety_day_actions": [
        {{"action": "Concrete action for next 90 days", "owner": "Specific department", "by_when": "Within 30/60/90 days", "success_metric": "How we know it's done"}},
        {{"action": "Another 90-day action", "owner": "Owner", "by_when": "Timeline", "success_metric": "Metric"}}
    ],
    
    "risk_summary": "2-3 sentences on the top risks if Austin doesn't act on this portfolio. What could go wrong? What opportunities would be missed?",
    
    "opportunity_summary": "2-3 sentences on the top opportunities if Austin leads on these trends. What competitive advantage? What citizen benefits?"
}}

Respond with ONLY the JSON object, no markdown formatting or explanation."""

        model_deployment = get_chat_deployment()
        
        response = await asyncio.to_thread(
            self.openai_client.chat.completions.create,
            model=model_deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=4500,  # Increased for expanded synthesis fields
            timeout=REQUEST_TIMEOUT
        )
        
        # Parse response
        content = response.choices[0].message.content.strip()
        
        # Clean up potential markdown code blocks
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()
        
        try:
            synthesis_data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse portfolio synthesis JSON: {e}")
            logger.error(f"Raw content: {content[:500]}")
            # Return minimal synthesis on parse failure
            return PortfolioSynthesis(
                executive_overview=f"This portfolio contains {len(briefs)} strategic intelligence briefs for the {workstream_name} workstream.",
                key_themes=["Strategic technology trends", "Municipal service implications", "Resource considerations"],
                priority_matrix={"high_impact_urgent": [], "high_impact_strategic": [], "monitor": [], "rationale": "Unable to generate detailed analysis"},
                cross_cutting_insights=["Multiple trends may require coordinated response"],
                recommended_actions=[{"action": "Review individual briefs for detailed recommendations", "owner": "Leadership", "timeline": "Immediate", "cards": [b.card_name for b in briefs]}],
                prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                completion_tokens=response.usage.completion_tokens if response.usage else 0,
                model_used=model_deployment
            )
        
        return PortfolioSynthesis(
            executive_overview=synthesis_data.get("executive_overview", ""),
            key_themes=synthesis_data.get("key_themes", []),
            priority_matrix=synthesis_data.get("priority_matrix", {}),
            cross_cutting_insights=synthesis_data.get("cross_cutting_insights", []),
            recommended_actions=synthesis_data.get("recommended_actions", []),
            urgency_statement=synthesis_data.get("urgency_statement", ""),
            implementation_guidance=synthesis_data.get("implementation_guidance", {}),
            ninety_day_actions=synthesis_data.get("ninety_day_actions", []),
            risk_summary=synthesis_data.get("risk_summary", ""),
            opportunity_summary=synthesis_data.get("opportunity_summary", ""),
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
            model_used=model_deployment
        )
