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

    MODEL = "gpt-4o"

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

        # Call OpenAI API (synchronous client)
        response = self.openai_client.chat.completions.create(
            model=self.MODEL,
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
            model_used=self.MODEL
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
