"""
Grant Opportunity Summary Service for GrantScope2 Application.

This service generates comprehensive grant opportunity summaries for grant cards,
synthesizing card data, user notes, related opportunities, and source materials
into actionable opportunity assessments with an Austin-specific perspective.

The summary generation is async - it creates a record immediately and processes
in the background, allowing the frontend to poll for completion.

Key Features:
- Austin-focused grant opportunity assessment perspective
- 800-1500 word comprehensive summaries
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

from sqlalchemy import select, update as sa_update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.brief import ExecutiveBrief
from app.models.db.card import Card
from app.models.db.card_extras import CardRelationship
from app.models.db.source import DiscoveredSource
from app.models.db.workstream import WorkstreamCard, Workstream

import openai

# Azure OpenAI deployment names
from app.openai_provider import get_chat_deployment
from app.taxonomy import PILLAR_NAMES

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
                    wait_time = backoff * (BACKOFF_MULTIPLIER**attempt)
                    logger.warning(
                        f"Rate limited on {func.__name__}, "
                        f"retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                except openai.APITimeoutError as e:
                    last_exception = e
                    wait_time = backoff * (BACKOFF_MULTIPLIER**attempt)
                    logger.warning(
                        f"Timeout on {func.__name__}, "
                        f"retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                except openai.APIConnectionError as e:
                    last_exception = e
                    wait_time = backoff * (BACKOFF_MULTIPLIER**attempt)
                    logger.warning(
                        f"Connection error on {func.__name__}, "
                        f"retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                except openai.APIStatusError as e:
                    # Don't retry on 4xx errors (except 429 which is RateLimitError)
                    if 400 <= e.status_code < 500:
                        logger.error(
                            f"API error on {func.__name__}: {e.status_code} - {e.message}"
                        )
                        raise
                    last_exception = e
                    wait_time = backoff * (BACKOFF_MULTIPLIER**attempt)
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
# Grant Opportunity Summary Prompt (Austin-focused, comprehensive)
# ============================================================================

GRANT_OPPORTUNITY_PROMPT = """You are a grants specialist preparing a comprehensive grant opportunity assessment for City of Austin decision-makers and grants management staff.

Generate a grant opportunity summary for "{card_name}" that helps the grants team quickly evaluate whether to pursue this funding opportunity. This summary should synthesize all available information into an actionable assessment with an Austin-specific perspective.

---

## GRANT OPPORTUNITY INFORMATION
Name: {card_name}
Summary: {summary}
Description: {description}
Category: {pillar}
Horizon: {horizon}
Stage: {stage}
Scores: Novelty={novelty}/100, Impact={impact}/100, Relevance={relevance}/100, Risk={risk}/100

## USER CONTEXT & NOTES
Workstream: {workstream_name}
Workstream Description: {workstream_description}
User Notes on Opportunity: {user_notes}

## RELATED OPPORTUNITIES
{related_cards_summary}

## SOURCE MATERIALS
{source_excerpts}

---

Create a grant opportunity summary with these sections:

## EXECUTIVE SUMMARY
(2-3 paragraphs providing an overview of the grant opportunity, the funding agency, available amounts, and strategic fit for City of Austin)

## GRANT DETAILS
- **Funding Agency**: (Name of the federal, state, or foundation grantor)
- **CFDA Number**: (If federal, provide the CFDA/ALN number if available, otherwise note "Not identified")
- **Funding Range**: (Minimum and maximum award amounts, or estimated range)
- **Application Deadline**: (Known or estimated deadline)
- **Eligible Applicants**: (Who can apply - municipalities, nonprofits, etc.)
- **Cost Sharing Requirements**: (Match requirements, in-kind allowances)
- **Grant Type**: (Formula, competitive, pass-through, etc.)
- **Performance Period**: (Duration of the grant if known)

## STRATEGIC ALIGNMENT
- How does this opportunity align with Austin's strategic priorities and CMO Top 25?
- Which City of Austin departments would benefit most?
- Has Austin or peer cities received similar grants in the past?
- How does this connect to existing city programs or initiatives?

## ELIGIBILITY ASSESSMENT
- Does the City of Austin meet all eligibility criteria?
- Are there any potentially disqualifying factors?
- What certifications or pre-requisites are required (SAM registration, etc.)?
- Are there geographic, demographic, or programmatic restrictions?

## APPLICATION REQUIREMENTS
- What documents are required (narrative, budget, letters of support, etc.)?
- What certifications or registrations must be current?
- Are there pre-application requirements (letter of intent, pre-proposal)?
- What is the estimated timeline from start to submission?
- Are there page limits, formatting requirements, or other constraints?

## BUDGET CONSIDERATIONS
- What is the realistic budget range for a competitive application?
- What matching fund requirements exist (cash match, in-kind)?
- What indirect cost rate applies?
- Are there budget category restrictions or caps?
- What are the likely staffing and administrative costs?

## COMPETITIVE LANDSCAPE
- How many applicants are expected (based on historical data if available)?
- What is the historical award rate?
- What are Austin's competitive advantages for this opportunity?
- What weaknesses or gaps might reviewers flag?
- Are there scoring criteria or priority areas that favor Austin?

## RECOMMENDATIONS
- **Go/No-Go Recommendation**: (Clear recommendation with rationale)
- **Key Strengths**: What makes Austin a strong candidate?
- **Key Risks**: What could prevent a successful application or award?
- **Mitigations**: How can identified risks be addressed?
- **Confidence Level**: (High/Medium/Low) confidence in success if applied

## NEXT STEPS
(Numbered list of specific action items with target dates for pursuing this opportunity, such as:)
1. Identify lead department and grant writer
2. Confirm eligibility and registration status
3. Schedule kickoff meeting with stakeholders
4. Draft project narrative outline
5. Develop budget framework
6. Secure letters of support
7. Internal review and submission

---

Guidelines:
- Write for grants professionals who need to quickly assess opportunity fit
- Be SPECIFIC with dollar amounts, dates, and agency names where available
- Frame everything through Austin's lens: departments, programs, and community needs
- If information is limited, clearly note what is unknown and needs further research
- Include practical details that accelerate the application process
- Use plain language - spell out all acronyms on first use
- Total length: 800-1500 words depending on available information
"""


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class BriefGenerationResult:
    """Result of grant opportunity summary generation operation."""

    content_markdown: str
    summary: str
    content_json: Dict[str, Any]
    prompt_tokens: int
    completion_tokens: int
    model_used: str


@dataclass
class PortfolioSynthesis:
    """
    AI-synthesized content for portfolio/bulk grant summary exports.

    Generated by analyzing multiple grant opportunity summaries together to create
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
    """A grant opportunity summary with its associated card data for portfolio generation."""

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
        md_parts.extend((f"## {section['title']}\n", section["content"], ""))
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
        "8": "Mature (established)",
    }

    # Handle formats like "5_implementing" or just "5"
    stage_num = stage_id.split("_")[0] if "_" in stage_id else stage_id
    return stage_map.get(stage_num, stage_id)


def get_pillar_name(pillar_id: Optional[str]) -> str:
    """Convert pillar_id to human-readable name."""
    if not pillar_id:
        return "Unknown"

    return PILLAR_NAMES.get(pillar_id, pillar_id)


def extract_executive_summary(content: str) -> str:
    """
    Extract the executive summary section from the brief.

    Args:
        content: Full brief markdown content

    Returns:
        Executive summary text (first 500 chars if section not found)
    """
    # Look for executive summary section
    pattern = r"##\s*EXECUTIVE\s*SUMMARY\s*\n(.*?)(?=\n##|\Z)"
    if match := re.search(pattern, content, re.IGNORECASE | re.DOTALL):
        summary = match[1].strip()
        # Clean up and limit length
        summary = summary.replace("\n", " ").strip()
        if len(summary) > 500:
            summary = f"{summary[:497]}..."
        return summary

    # Fallback: first paragraph
    paragraphs = content.split("\n\n")
    for p in paragraphs:
        p = p.strip()
        if p and not p.startswith("#"):
            return f"{p[:497]}..." if len(p) > 500 else p
    return f"{content[:500]}..." if len(content) > 500 else content


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

    for line in content.split("\n"):
        # Check for section header (## SECTION NAME)
        if line.startswith("## "):
            # Save previous section
            if current_section:
                sections.append(
                    {
                        "title": current_section,
                        "content": "\n".join(current_content).strip(),
                        "order": len(sections),
                    }
                )
            current_section = line[3:].strip()
            current_content = []
        elif current_section:
            current_content.append(line)

    # Save last section
    if current_section:
        sections.append(
            {
                "title": current_section,
                "content": "\n".join(current_content).strip(),
                "order": len(sections),
            }
        )

    return {
        "sections": sections,
        "section_count": len(sections),
        "word_count": len(content.split()),
    }


# ============================================================================
# Grant Opportunity Summary Service
# ============================================================================


class ExecutiveBriefService:
    """
    Service for generating grant opportunity summaries for grant cards.

    Handles async summary generation with background processing,
    status tracking, AI-powered content synthesis, and comprehensive
    metadata tracking for monitoring and cost analysis.
    """

    def __init__(self, db: AsyncSession, openai_client: openai.AsyncOpenAI):
        """
        Initialize the ExecutiveBriefService.

        Args:
            db: AsyncSession for database operations
            openai_client: AsyncOpenAI client for AI generation
        """
        self.db = db
        self.openai_client = openai_client

    # ========================================================================
    # Brief CRUD Operations
    # ========================================================================

    async def create_brief_record(
        self,
        workstream_card_id: str,
        card_id: str,
        user_id: str,
        sources_since_previous: Optional[Dict[str, Any]] = None,
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
        version_result = await self.db.execute(
            select(ExecutiveBrief.version)
            .where(ExecutiveBrief.workstream_card_id == workstream_card_id)
            .order_by(ExecutiveBrief.version.desc())
            .limit(1)
        )
        latest_version = version_result.scalar_one_or_none()

        next_version = 1
        if latest_version is not None:
            next_version = latest_version + 1

        now = datetime.utcnow().isoformat()
        brief = ExecutiveBrief(
            workstream_card_id=workstream_card_id,
            card_id=card_id,
            created_by=user_id,
            status="pending",
            version=next_version,
            sources_since_previous=sources_since_previous,
        )
        self.db.add(brief)
        await self.db.flush()
        await self.db.refresh(brief)

        logger.info(
            f"Created brief record version {next_version} for workstream_card {workstream_card_id}"
        )
        return {
            "id": str(brief.id),
            "workstream_card_id": str(brief.workstream_card_id),
            "card_id": str(brief.card_id),
            "created_by": str(brief.created_by),
            "status": brief.status,
            "version": brief.version,
            "sources_since_previous": brief.sources_since_previous,
            "created_at": brief.created_at.isoformat() if brief.created_at else now,
            "updated_at": brief.updated_at.isoformat() if brief.updated_at else now,
        }

    async def get_brief(self, brief_id: str) -> Optional[Dict[str, Any]]:
        """
        Get brief by ID.

        Args:
            brief_id: Brief identifier

        Returns:
            Brief record or None
        """
        result = await self.db.execute(
            select(ExecutiveBrief).where(ExecutiveBrief.id == brief_id)
        )
        brief = result.scalar_one_or_none()
        if not brief:
            return None
        return self._brief_to_dict(brief)

    async def get_brief_by_workstream_card(
        self, workstream_card_id: str, version: Optional[int] = None
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
        query = select(ExecutiveBrief).where(
            ExecutiveBrief.workstream_card_id == workstream_card_id
        )

        if version is not None:
            query = query.where(ExecutiveBrief.version == version)
        else:
            # Get the latest version (highest version number)
            query = query.order_by(ExecutiveBrief.version.desc()).limit(1)

        result = await self.db.execute(query)
        brief = result.scalar_one_or_none()
        if not brief:
            return None
        return self._brief_to_dict(brief)

    async def get_brief_versions(self, workstream_card_id: str) -> List[Dict[str, Any]]:
        """
        Get all brief versions for a workstream card.

        Returns versions ordered by version number descending (newest first).

        Args:
            workstream_card_id: Workstream card identifier

        Returns:
            List of brief records (without full content for efficiency)
        """
        result = await self.db.execute(
            select(
                ExecutiveBrief.id,
                ExecutiveBrief.version,
                ExecutiveBrief.status,
                ExecutiveBrief.summary,
                ExecutiveBrief.sources_since_previous,
                ExecutiveBrief.generated_at,
                ExecutiveBrief.created_at,
                ExecutiveBrief.model_used,
            )
            .where(ExecutiveBrief.workstream_card_id == workstream_card_id)
            .order_by(ExecutiveBrief.version.desc())
        )

        rows = result.all()
        return [
            {
                "id": str(row.id),
                "version": row.version,
                "status": row.status,
                "summary": row.summary,
                "sources_since_previous": row.sources_since_previous,
                "generated_at": (
                    row.generated_at.isoformat() if row.generated_at else None
                ),
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "model_used": row.model_used,
            }
            for row in rows
        ]

    async def get_latest_completed_brief(
        self, workstream_card_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get the most recent completed brief for a workstream card.

        Used to determine the timestamp for filtering new sources.

        Args:
            workstream_card_id: Workstream card identifier

        Returns:
            Latest completed brief or None
        """
        result = await self.db.execute(
            select(
                ExecutiveBrief.id, ExecutiveBrief.version, ExecutiveBrief.generated_at
            )
            .where(
                ExecutiveBrief.workstream_card_id == workstream_card_id,
                ExecutiveBrief.status == "completed",
            )
            .order_by(ExecutiveBrief.version.desc())
            .limit(1)
        )

        row = result.one_or_none()
        if not row:
            return None
        return {
            "id": str(row.id),
            "version": row.version,
            "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        }

    async def get_brief_status(self, brief_id: str) -> Optional[Dict[str, Any]]:
        """
        Get lightweight brief status for polling.

        Args:
            brief_id: Brief identifier

        Returns:
            Status data or None
        """
        result = await self.db.execute(
            select(
                ExecutiveBrief.id,
                ExecutiveBrief.status,
                ExecutiveBrief.version,
                ExecutiveBrief.summary,
                ExecutiveBrief.error_message,
                ExecutiveBrief.generated_at,
            ).where(ExecutiveBrief.id == brief_id)
        )

        row = result.one_or_none()
        if not row:
            return None
        return {
            "id": str(row.id),
            "status": row.status,
            "version": row.version,
            "summary": row.summary,
            "error_message": row.error_message,
            "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        }

    async def update_brief_status(
        self, brief_id: str, status: str, error_message: Optional[str] = None, **kwargs
    ) -> None:
        """
        Update brief status and optional fields.

        Args:
            brief_id: Brief identifier
            status: New status (pending, generating, completed, failed)
            error_message: Error message if failed
            **kwargs: Additional fields to update
        """
        update_data = {"status": status, "updated_at": datetime.utcnow().isoformat()}

        if error_message:
            update_data["error_message"] = error_message

        update_data |= kwargs

        await self.db.execute(
            sa_update(ExecutiveBrief)
            .where(ExecutiveBrief.id == brief_id)
            .values(**update_data)
        )
        await self.db.flush()

    # ========================================================================
    # Context Gathering
    # ========================================================================

    async def _gather_card_context(self, card_id: str) -> Dict[str, Any]:
        """
        Gather all card data for grant opportunity summary generation.

        Args:
            card_id: Card identifier

        Returns:
            Card data with all relevant fields
        """
        result = await self.db.execute(select(Card).where(Card.id == card_id))
        card = result.scalar_one_or_none()

        if not card:
            raise ValueError(f"Card not found: {card_id}")

        return self._card_to_dict(card)

    async def _gather_workstream_context(
        self, workstream_card_id: str
    ) -> Dict[str, Any]:
        """
        Gather workstream and workstream_card context.

        Args:
            workstream_card_id: Workstream card identifier

        Returns:
            Dict with workstream info and user notes
        """
        # Get workstream_card
        wsc_result = await self.db.execute(
            select(WorkstreamCard).where(WorkstreamCard.id == workstream_card_id)
        )
        wsc = wsc_result.scalar_one_or_none()

        if not wsc:
            return {
                "workstream_name": "Unknown Workstream",
                "workstream_description": "",
                "user_notes": "",
            }

        # Get the workstream
        ws_result = await self.db.execute(
            select(Workstream).where(Workstream.id == wsc.workstream_id)
        )
        workstream = ws_result.scalar_one_or_none()

        return {
            "workstream_name": workstream.name if workstream else "Unknown Workstream",
            "workstream_description": workstream.description if workstream else "",
            "user_notes": wsc.notes or "",
        }

    async def _gather_related_cards(self, card_id: str, limit: int = 5) -> str:
        """
        Gather related grant opportunities summary for context.

        Args:
            card_id: Card identifier
            limit: Maximum number of related cards

        Returns:
            Formatted string with related opportunities summary
        """
        # Try to find related cards through card_relationships table
        result = await self.db.execute(
            select(
                CardRelationship.target_card_id,
                CardRelationship.relationship_type,
                CardRelationship.strength,
            )
            .where(CardRelationship.source_card_id == card_id)
            .order_by(CardRelationship.strength.desc())
            .limit(limit)
        )
        relationships = result.all()

        if not relationships:
            return "No related opportunities identified."

        # Fetch details for related cards
        related_ids = [r.target_card_id for r in relationships]
        cards_result = await self.db.execute(
            select(
                Card.id, Card.name, Card.summary, Card.pillar_id, Card.horizon
            ).where(Card.id.in_(related_ids))
        )
        related_cards = cards_result.all()

        if not related_cards:
            return "No related opportunities identified."

        # Build summary
        lines = []
        card_map = {str(c.id): c for c in related_cards}
        for rel in relationships:
            card = card_map.get(str(rel.target_card_id))
            if card:
                summary_text = card.summary or "No summary"
                if summary_text and len(summary_text) > 150:
                    summary_text = f"{summary_text[:147]}..."
                strength_val = float(rel.strength) if rel.strength else 0
                lines.append(
                    f"- **{card.name}** ({rel.relationship_type}, "
                    f"strength: {strength_val:.0%}): {summary_text}"
                )

        return "\n".join(lines) if lines else "No related opportunities identified."

    async def _gather_source_materials(
        self, card_id: str, limit: int = 10, since_timestamp: Optional[str] = None
    ) -> tuple[str, int]:
        """
        Gather source materials/excerpts for the grant opportunity card.

        Args:
            card_id: Card identifier
            limit: Maximum number of sources
            since_timestamp: Optional ISO timestamp to filter sources created after

        Returns:
            Tuple of (formatted string with source excerpts, count of sources)
        """
        query = select(
            DiscoveredSource.title,
            DiscoveredSource.url,
            DiscoveredSource.domain,
            DiscoveredSource.analysis_summary,
            DiscoveredSource.analysis_key_excerpts,
            DiscoveredSource.created_at,
        ).where(DiscoveredSource.resulting_card_id == card_id)

        if since_timestamp:
            query = query.where(DiscoveredSource.created_at > since_timestamp)

        query = query.order_by(DiscoveredSource.created_at.desc()).limit(limit)

        result = await self.db.execute(query)
        rows = result.all()

        if not rows:
            if since_timestamp:
                return "No new source materials since last summary.", 0
            return "No source materials available.", 0

        lines = []
        for src in rows:
            title = src.title or "Untitled"
            if len(title) > 80:
                title = f"{title[:77]}..."
            source = src.domain or "Unknown"
            summary = src.analysis_summary or ""
            if summary and len(summary) > 200:
                summary = f"{summary[:197]}..."
            url = src.url or ""

            line = f"- **{title}** ({source})"
            if summary:
                line += f": {summary}"
            if url:
                line += f" [Source: {url}]"
            lines.append(line)

        return "\n".join(lines) if lines else "No source materials available.", len(
            rows
        )

    async def count_new_sources(self, card_id: str, since_timestamp: str) -> int:
        """
        Count sources discovered since a given timestamp for a grant opportunity.

        Args:
            card_id: Card identifier
            since_timestamp: ISO timestamp to count sources after

        Returns:
            Count of new sources
        """
        result = await self.db.execute(
            select(func.count(DiscoveredSource.id)).where(
                DiscoveredSource.resulting_card_id == card_id,
                DiscoveredSource.created_at > since_timestamp,
            )
        )

        return result.scalar() or 0

    # ========================================================================
    # Grant Opportunity Summary Generation
    # ========================================================================

    @with_retry(max_retries=MAX_RETRIES)
    async def _generate_brief_content(
        self,
        card: Dict[str, Any],
        workstream_context: Dict[str, Any],
        related_cards: str,
        source_materials: str,
    ) -> BriefGenerationResult:
        """
        Generate grant opportunity summary content using OpenAI API.

        Args:
            card: Card data
            workstream_context: Workstream and notes context
            related_cards: Related opportunities summary string
            source_materials: Source excerpts string

        Returns:
            BriefGenerationResult with content and metadata
        """
        # Build the prompt
        prompt = GRANT_OPPORTUNITY_PROMPT.format(
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
            source_excerpts=source_materials,
        )

        logger.info(
            f"Generating grant opportunity summary for card: {card.get('name', 'Unknown')}"
        )

        # Get Azure deployment name for chat completions
        model_deployment = get_chat_deployment()

        # Call Azure OpenAI API (synchronous client)
        response = self.openai_client.chat.completions.create(
            model=model_deployment,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a grants specialist for the City of Austin. "
                        "Generate comprehensive, actionable grant opportunity summaries in clear markdown format."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=4000,
            temperature=0.7,
            timeout=REQUEST_TIMEOUT,
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
            model_used=model_deployment,
        )

    async def generate_executive_brief(
        self,
        brief_id: str,
        workstream_card_id: str,
        card_id: str,
        since_timestamp: Optional[str] = None,
    ) -> None:
        """
        Generate grant opportunity summary content (runs in background).

        This is the main entry point for summary generation, called
        asynchronously after creating the brief record.

        Args:
            brief_id: Brief identifier to update
            workstream_card_id: Workstream card identifier for context
            card_id: Card to generate summary for
            since_timestamp: Optional timestamp to filter sources (for regeneration)
        """
        start_time = time.time()

        try:
            # Update status to generating
            await self.update_brief_status(brief_id, "generating")

            # Gather all context
            card = await self._gather_card_context(card_id)
            workstream_context = await self._gather_workstream_context(
                workstream_card_id
            )
            related_cards = await self._gather_related_cards(card_id)
            source_materials, source_count = await self._gather_source_materials(
                card_id, since_timestamp=since_timestamp
            )

            # Generate the brief
            result = await self._generate_brief_content(
                card=card,
                workstream_context=workstream_context,
                related_cards=related_cards,
                source_materials=source_materials,
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
                completion_tokens=result.completion_tokens,
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
                generation_time_ms=generation_time_ms,
            )

    # =========================================================================
    # Portfolio Synthesis (for Bulk Grant Summary Export)
    # =========================================================================

    @with_retry(max_retries=MAX_RETRIES)
    async def synthesize_portfolio(
        self, briefs: List[PortfolioBrief], workstream_name: str
    ) -> PortfolioSynthesis:
        """
        Generate AI-synthesized content for a portfolio of grant opportunity summaries.

        Uses GPT-4 to analyze multiple grant summaries together and create:
        - Executive overview synthesizing all opportunities
        - Key themes across the portfolio
        - Priority matrix (funding impact vs deadline urgency)
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

            card_summaries.append(
                f"""
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
"""
            )

        cards_context = "\n---\n".join(card_summaries)

        system_prompt = """You are a senior grants analyst for the City of Austin, Texas.
You synthesize multiple grant opportunity summaries into executive-ready portfolio assessments.

Your analysis should be:
- Decision-oriented: Help leadership decide which grants to prioritize
- Implementation-focused: Tell them exactly what to DO with each opportunity
- Comparative: Show how opportunities relate to each other and can be combined
- Austin-specific: Frame everything in terms of city needs and capacity
- Actionable: Provide concrete next steps, not vague recommendations

Output your analysis as valid JSON matching the specified structure."""

        user_prompt = f"""Analyze this portfolio of {len(briefs)} grant opportunity summaries for the "{workstream_name}" workstream.

{cards_context}

Generate a comprehensive portfolio synthesis as JSON with this exact structure:
{{
    "executive_overview": "2-3 paragraphs synthesizing what leadership needs to know about these {len(briefs)} grant opportunities together. What's the total funding landscape? How do they connect? What decisions need to be made about which to pursue?",

    "urgency_statement": "A compelling 2-3 sentence statement about why this grant portfolio demands attention NOW. What deadlines are approaching? What funding windows are closing?",

    "key_themes": [
        "Theme 1: A common funding thread across multiple opportunities",
        "Theme 2: Another pattern you've identified",
        "Theme 3: etc (provide 3-5 themes)"
    ],

    "priority_matrix": {{
        "high_impact_urgent": ["Grant names with approaching deadlines and high funding potential"],
        "high_impact_strategic": ["Grant names with large awards but longer timelines"],
        "monitor": ["Grant names to track but not pursue immediately"],
        "rationale": "Brief explanation of how you prioritized"
    }},

    "implementation_guidance": {{
        "apply_now": ["Grant names ready for immediate application - strong fit and capacity exists"],
        "investigate_further": ["Grant names needing more eligibility or feasibility research"],
        "build_partnerships": ["Grant names where partner or subrecipient coordination is needed"],
        "policy_review": ["Grant names requiring council approval or policy changes"],
        "capacity_building": ["Grant names where staff training or hiring is a prerequisite"],
        "budget_planning": ["Grant names requiring match funding or budget allocation"]
    }},

    "cross_cutting_insights": [
        "Insight 1: How Grant X could complement Grant Y for greater impact",
        "Insight 2: Shared matching fund or staffing requirements across grants",
        "Insight 3: etc (provide 3-5 insights)"
    ],

    "recommended_actions": [
        {{"action": "Specific action to take", "owner": "Department or role", "timeline": "Q1 2025", "cards": ["Related grant names"]}},
        {{"action": "Another action", "owner": "Owner", "timeline": "Timeline", "cards": ["Grants"]}}
    ],

    "ninety_day_actions": [
        {{"action": "Concrete action for next 90 days", "owner": "Specific department", "by_when": "Within 30/60/90 days", "success_metric": "How we know it's done"}},
        {{"action": "Another 90-day action", "owner": "Owner", "by_when": "Timeline", "success_metric": "Metric"}}
    ],

    "risk_summary": "2-3 sentences on the top risks if Austin doesn't pursue these grants. What funding would be left on the table? What peer cities might gain advantage?",

    "opportunity_summary": "2-3 sentences on the total funding potential if Austin pursues this portfolio strategically. What programs could be funded? What community impact?"
}}

Respond with ONLY the JSON object, no markdown formatting or explanation."""

        model_deployment = get_chat_deployment()

        response = await asyncio.to_thread(
            self.openai_client.chat.completions.create,
            model=model_deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=4500,  # Increased for expanded synthesis fields
            timeout=REQUEST_TIMEOUT,
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
                executive_overview=f"This portfolio contains {len(briefs)} grant opportunity summaries for the {workstream_name} workstream.",
                key_themes=[
                    "Grant funding opportunities",
                    "Municipal program alignment",
                    "Resource and capacity considerations",
                ],
                priority_matrix={
                    "high_impact_urgent": [],
                    "high_impact_strategic": [],
                    "monitor": [],
                    "rationale": "Unable to generate detailed analysis",
                },
                cross_cutting_insights=[
                    "Multiple grant opportunities may benefit from coordinated pursuit"
                ],
                recommended_actions=[
                    {
                        "action": "Review individual grant summaries for detailed recommendations",
                        "owner": "Grants Management",
                        "timeline": "Immediate",
                        "cards": [b.card_name for b in briefs],
                    }
                ],
                prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                completion_tokens=(
                    response.usage.completion_tokens if response.usage else 0
                ),
                model_used=model_deployment,
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
            model_used=model_deployment,
        )

    # ========================================================================
    # Private helpers
    # ========================================================================

    @staticmethod
    def _brief_to_dict(brief: ExecutiveBrief) -> Dict[str, Any]:
        """Convert an ExecutiveBrief ORM object to a dict."""
        return {
            "id": str(brief.id),
            "workstream_card_id": str(brief.workstream_card_id),
            "card_id": str(brief.card_id),
            "created_by": str(brief.created_by),
            "status": brief.status,
            "content": brief.content,
            "content_markdown": brief.content_markdown,
            "summary": brief.summary,
            "generated_at": (
                brief.generated_at.isoformat() if brief.generated_at else None
            ),
            "generation_time_ms": brief.generation_time_ms,
            "model_used": brief.model_used,
            "prompt_tokens": brief.prompt_tokens,
            "completion_tokens": brief.completion_tokens,
            "error_message": brief.error_message,
            "version": brief.version,
            "sources_since_previous": brief.sources_since_previous,
            "created_at": brief.created_at.isoformat() if brief.created_at else None,
            "updated_at": brief.updated_at.isoformat() if brief.updated_at else None,
        }

    @staticmethod
    def _card_to_dict(card: Card) -> Dict[str, Any]:
        """Convert a Card ORM object to a dict for prompt generation."""
        return {
            "id": str(card.id),
            "name": card.name,
            "slug": card.slug,
            "summary": card.summary,
            "description": card.description,
            "pillar_id": card.pillar_id,
            "horizon": card.horizon,
            "stage_id": card.stage_id,
            "novelty_score": card.novelty_score,
            "impact_score": card.impact_score,
            "relevance_score": card.relevance_score,
            "risk_score": card.risk_score,
            "velocity_score": card.velocity_score,
            "opportunity_score": card.opportunity_score,
            "status": card.status,
        }
