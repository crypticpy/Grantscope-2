"""Wizard service for the Guided Grant Application Wizard.

Provides AI-powered grant extraction, plan synthesis, and card creation
to support the wizard workflow. Uses Azure OpenAI (gpt-4.1) for structured
data extraction and SQLAlchemy async ORM for persistence.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.crawler import crawl_url
from app.openai_provider import azure_openai_async_client, get_chat_deployment
from app.models.wizard import GrantContext, PlanData
from app.models.db.card import Card

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

GRANT_EXTRACTION_SYSTEM_PROMPT = """\
You are an expert grant analyst for the City of Austin, Texas. Your job is to \
extract structured information from grant opportunity documents with high accuracy.

You MUST return a valid JSON object with the following fields (use null for \
fields you cannot determine from the text):

{
  "grant_name": "Name of the grant program",
  "grantor": "Granting organization",
  "cfda_number": "CFDA/Assistance Listing number or null",
  "deadline": "Application deadline as ISO 8601 date string or human-readable",
  "funding_amount_min": 0.0,
  "funding_amount_max": 0.0,
  "grant_type": "federal|state|foundation|corporate|other",
  "eligibility_text": "Raw eligibility criteria text",
  "match_requirement": "Match/cost-share requirement description or null",
  "requirements": [
    {
      "category": "narrative|budget|timeline|evaluation|organizational|staffing|other",
      "description": "Description of the requirement",
      "is_mandatory": true
    }
  ],
  "key_dates": [
    {
      "date": "ISO 8601 date or human-readable string",
      "description": "What this date represents"
    }
  ],
  "evaluation_criteria": "How applications will be evaluated",
  "contact_info": "Grant program contact information",
  "summary": "A 2-3 sentence summary of the grant opportunity"
}

Be thorough but only include information actually present in the source text. \
Do not fabricate information. If a field is not present, use null (for strings/numbers) \
or an empty array (for lists).\
"""

PLAN_SYNTHESIS_SYSTEM_PROMPT = """\
You are an expert grant strategist for the City of Austin, Texas. Based on \
the grant opportunity context and the interview conversation, synthesize a \
comprehensive project plan.

You MUST return a valid JSON object with this structure:

{
  "program_overview": "High-level program description (2-3 paragraphs)",
  "staffing_plan": [
    {
      "role": "Position/role title",
      "fte": 1.0,
      "salary_estimate": 75000.0,
      "responsibilities": "Key responsibilities"
    }
  ],
  "budget": [
    {
      "category": "Budget category (personnel, equipment, supplies, etc.)",
      "amount": 0.0,
      "justification": "Justification for this expense"
    }
  ],
  "timeline": [
    {
      "phase": "Phase name",
      "start": "Start date",
      "end": "End date",
      "milestones": ["Milestone 1", "Milestone 2"]
    }
  ],
  "deliverables": ["Deliverable 1", "Deliverable 2"],
  "metrics": [
    {
      "metric": "Metric name",
      "target": "Target value or outcome",
      "measurement_method": "How this metric will be measured"
    }
  ],
  "partnerships": ["Partner organization 1", "Partner organization 2"]
}

Draw all details from the grant context and interview conversation. Be specific \
and realistic. Ensure budget amounts are reasonable for City of Austin municipal \
operations. Do not fabricate information not supported by the conversation.\
"""

PROGRAM_SUMMARY_SYNTHESIS_PROMPT = """\
You are an expert program development advisor for the City of Austin, Texas. \
Based on the interview conversation and any profile context provided, synthesize \
a concise program summary.

You MUST return a valid JSON object with this structure:

{
  "program_name": "Name of the program (from conversation or profile)",
  "department": "Department name (from profile or conversation)",
  "problem_statement": "1-2 paragraphs describing the problem this program addresses",
  "program_description": "2-3 paragraphs describing what the program will do",
  "target_population": "Who this program serves",
  "key_needs": ["Need 1", "Need 2", "Need 3"],
  "estimated_budget": "Budget range or description",
  "team_overview": "Description of team/staffing needs",
  "timeline_overview": "High-level timeline for the program",
  "strategic_alignment": "How this aligns with Austin's strategic framework and priorities"
}

Draw all details from the interview conversation and profile data. Be specific \
and realistic. Use what the user actually said — do not fabricate details they \
did not mention. If they didn't discuss a topic, use a brief placeholder like \
"To be determined" rather than making up specifics.\
"""


# ---------------------------------------------------------------------------
# WizardService
# ---------------------------------------------------------------------------


class WizardService:
    """Stateless service for wizard AI operations and card creation."""

    def __init__(self) -> None:
        self.async_client = azure_openai_async_client
        self.model = get_chat_deployment()

    # -- Grant extraction ---------------------------------------------------

    async def extract_grant_from_text(self, text: str) -> GrantContext:
        """Extract structured grant context from raw text using gpt-4.1.

        Args:
            text: Raw text content from a grant opportunity document.

        Returns:
            Parsed GrantContext model.

        Raises:
            ValueError: If the AI response cannot be parsed into GrantContext.
            Exception: If the Azure OpenAI call fails.
        """
        if not text or not text.strip():
            raise ValueError("Cannot extract grant context from empty text")

        # Truncate very long documents to stay within token limits
        max_chars = 80_000
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n[Content truncated for processing]"

        logger.info(
            "Extracting grant context from text (%d chars) using %s",
            len(text),
            self.model,
        )

        response = await self.async_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": GRANT_EXTRACTION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Extract structured grant information from the following "
                        "document text:\n\n" + text
                    ),
                },
            ],
            temperature=0.2,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )

        raw_content = response.choices[0].message.content or "{}"

        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse grant extraction JSON: %s", e)
            raise ValueError(
                f"AI returned invalid JSON for grant extraction: {e}"
            ) from e

        try:
            grant_context = GrantContext(**parsed)
        except Exception as e:
            logger.error("Failed to validate grant context: %s", e)
            raise ValueError(
                f"AI response did not match expected grant context schema: {e}"
            ) from e

        logger.info(
            "Successfully extracted grant context: %s",
            grant_context.grant_name or "Unknown Grant",
        )
        return grant_context

    async def extract_grant_from_url(self, url: str) -> GrantContext:
        """Crawl a URL and extract structured grant context.

        Args:
            url: URL of the grant opportunity page or PDF.

        Returns:
            Parsed GrantContext model.

        Raises:
            ValueError: If the URL cannot be crawled or yields no content.
        """
        logger.info("Extracting grant context from URL: %s", url)

        result = await crawl_url(url)

        if not result.success:
            raise ValueError(
                f"Failed to fetch content from URL: {result.error or 'Unknown error'}"
            )

        if not result.markdown or not result.markdown.strip():
            raise ValueError(
                "URL was fetched successfully but contained no extractable text content"
            )

        return await self.extract_grant_from_text(result.markdown)

    # -- Plan synthesis -----------------------------------------------------

    async def synthesize_plan(
        self,
        grant_context: Dict[str, Any],
        messages: List[Dict[str, Any]],
        *,
        profile_context: Optional[Dict[str, Any]] = None,
    ) -> PlanData:
        """Synthesize a structured project plan from grant context and interview.

        Args:
            grant_context: Grant context dict (from the wizard session).
            messages: List of conversation message dicts (the interview transcript).

        Returns:
            Parsed PlanData model.

        Raises:
            ValueError: If the AI response cannot be parsed into PlanData.
        """
        # Build the conversation transcript
        transcript_lines: list[str] = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            transcript_lines.append(f"**{role.title()}**: {content}")
        transcript = "\n\n".join(transcript_lines)

        profile_section = ""
        if profile_context:
            profile_section = (
                "## User Profile Context\n"
                f"```json\n{json.dumps(profile_context, indent=2, default=str)}\n```\n\n"
            )

        grant_section = ""
        if grant_context:
            grant_section = (
                "## Grant Opportunity Context\n"
                f"```json\n{json.dumps(grant_context, indent=2, default=str)}\n```\n\n"
            )

        user_prompt = (
            f"{profile_section}"
            f"{grant_section}"
            "## Interview Transcript\n"
            f"{transcript}\n\n"
            "Based on the context and interview above, synthesize a "
            "comprehensive project plan as a JSON object."
        )

        logger.info(
            "Synthesizing plan from grant context and %d messages using %s",
            len(messages),
            self.model,
        )

        response = await self.async_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": PLAN_SYNTHESIS_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=6000,
            response_format={"type": "json_object"},
        )

        raw_content = response.choices[0].message.content or "{}"

        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse plan synthesis JSON: %s", e)
            raise ValueError(f"AI returned invalid JSON for plan synthesis: {e}") from e

        try:
            plan_data = PlanData(**parsed)
        except Exception as e:
            logger.error("Failed to validate plan data: %s", e)
            raise ValueError(
                f"AI response did not match expected plan data schema: {e}"
            ) from e

        logger.info("Successfully synthesized project plan")
        return plan_data

    # -- Program summary synthesis ------------------------------------------

    async def synthesize_program_summary(
        self,
        messages: List[Dict[str, Any]],
        profile_context: Optional[Dict[str, Any]] = None,
    ) -> "ProgramSummary":
        """Synthesize a program summary from interview conversation and profile.

        Args:
            messages: List of conversation message dicts (the interview transcript).
            profile_context: Optional dict of user profile data.

        Returns:
            Parsed ProgramSummary model.

        Raises:
            ValueError: If the AI response cannot be parsed.
        """
        from app.models.wizard import ProgramSummary

        # Build the conversation transcript
        transcript_lines: list[str] = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            transcript_lines.append(f"**{role.title()}**: {content}")
        transcript = "\n\n".join(transcript_lines)

        # Build profile context section
        profile_section = ""
        if profile_context:
            profile_section = (
                "## User Profile Context\n"
                f"```json\n{json.dumps(profile_context, indent=2, default=str)}\n```\n\n"
            )

        user_prompt = (
            f"{profile_section}"
            "## Interview Transcript\n"
            f"{transcript}\n\n"
            "Based on the interview and any profile context above, synthesize a "
            "comprehensive program summary as a JSON object."
        )

        logger.info(
            "Synthesizing program summary from %d messages using %s",
            len(messages),
            self.model,
        )

        response = await self.async_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": PROGRAM_SUMMARY_SYNTHESIS_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )

        raw_content = response.choices[0].message.content or "{}"

        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse program summary JSON: %s", e)
            raise ValueError(
                f"AI returned invalid JSON for program summary: {e}"
            ) from e

        try:
            summary = ProgramSummary(**parsed)
        except Exception as e:
            logger.error("Failed to validate program summary: %s", e)
            raise ValueError(
                f"AI response did not match expected program summary schema: {e}"
            ) from e

        logger.info(
            "Successfully synthesized program summary: %s", summary.program_name
        )
        return summary

    # -- Grant search query builder -----------------------------------------

    def build_grant_search_query(
        self,
        interview_data: Dict[str, Any],
        profile_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build a search query string for finding matching grants.

        Combines program description, needs, and categories from interview
        data and profile context into a text string suitable for embedding-based
        vector search.

        Args:
            interview_data: Interview data dict from the wizard session.
            profile_context: Optional dict of user profile data.

        Returns:
            A search query string, or empty string if insufficient data.
        """
        parts: list[str] = []

        # From program summary (if synthesized)
        summary = interview_data.get("program_summary", {})
        if summary:
            if summary.get("program_description"):
                parts.append(summary["program_description"])
            if summary.get("problem_statement"):
                parts.append(summary["problem_statement"])
            if summary.get("target_population"):
                parts.append(f"Target population: {summary['target_population']}")
            if summary.get("key_needs"):
                parts.append("Needs: " + ", ".join(map(str, summary["key_needs"])))

        # From profile context
        if profile_context:
            if profile_context.get("program_name"):
                parts.append(f"Program: {profile_context['program_name']}")
            if profile_context.get("program_mission"):
                parts.append(profile_context["program_mission"])
            if profile_context.get("grant_categories"):
                cats = profile_context["grant_categories"]
                if isinstance(cats, list):
                    parts.append("Grant categories: " + ", ".join(map(str, cats)))
            if profile_context.get("strategic_pillars"):
                pillars = profile_context["strategic_pillars"]
                if isinstance(pillars, list):
                    parts.append("Strategic pillars: " + ", ".join(map(str, pillars)))

        # Combine and truncate
        query = " ".join(parts)
        # Truncate to reasonable length for embedding
        return query[:2000]

    # -- Profile enrichment -------------------------------------------------

    async def enrich_session_with_profile(
        self,
        db: AsyncSession,
        session_obj,
        user_id: str,
    ) -> None:
        """Load user profile fields and store them in session interview_data.

        Queries the User table for profile fields (department, program info,
        grant preferences, etc.) and stores them in
        ``session_obj.interview_data["profile_context"]``.

        Args:
            db: AsyncSession instance.
            session_obj: The WizardSession ORM object to enrich (mutated in place).
            user_id: UUID string of the authenticated user.
        """
        import uuid as _uuid

        from sqlalchemy import select as sa_select

        from app.models.db.user import User

        profile_context: Dict[str, Any] = {}
        try:
            user_result = await db.execute(
                sa_select(User).where(User.id == _uuid.UUID(user_id))
            )
            user_obj = user_result.scalar_one_or_none()
            if user_obj:
                for field in [
                    "display_name",
                    "department",
                    "department_id",
                    "program_name",
                    "program_mission",
                    "team_size",
                    "budget_range",
                    "grant_experience",
                    "grant_categories",
                    "strategic_pillars",
                    "bio",
                    "title",
                ]:
                    val = getattr(user_obj, field, None)
                    if val:
                        profile_context[field] = (
                            val if not isinstance(val, list) else list(val)
                        )
            if profile_context:
                existing_interview = session_obj.interview_data or {}
                existing_interview["profile_context"] = profile_context
                session_obj.interview_data = existing_interview
                await db.flush()
                await db.refresh(session_obj)
        except Exception as e:
            logger.warning("Failed to load profile context: %s", e)

    # -- Grant matching -----------------------------------------------------

    async def match_grants(
        self,
        db: AsyncSession,
        interview_data: dict,
        profile_context: dict,
    ) -> dict:
        """Find matching grants from the cards table based on program description.

        Builds a search query from interview data, embeds it for vector search,
        and falls back to text search if vector search fails.

        Args:
            db: AsyncSession instance.
            interview_data: Interview data dict from the wizard session.
            profile_context: Profile context dict from the session.

        Returns:
            Dict with "grants" list and "query_used" string.

        Raises:
            ValueError: If there's not enough data to build a search query.
        """
        from sqlalchemy import select as sa_select, or_

        from app.helpers.db_utils import vector_search_cards
        from app.openai_provider import (
            azure_openai_async_embedding_client,
            get_embedding_deployment,
        )

        search_query = self.build_grant_search_query(
            interview_data=interview_data,
            profile_context=profile_context,
        )

        if not search_query:
            raise ValueError(
                "Not enough information to search for grants. "
                "Complete more of the interview first."
            )

        # Try vector search first, fall back to text search
        try:
            embed_response = (
                await azure_openai_async_embedding_client.embeddings.create(
                    model=get_embedding_deployment(),
                    input=search_query[:8000],
                )
            )
            embedding = embed_response.data[0].embedding
            results = await vector_search_cards(
                db,
                embedding,
                match_threshold=0.5,
                match_count=10,
                require_active=True,
            )
        except Exception as e:
            logger.warning("Vector search failed, falling back to text search: %s", e)
            # Fallback: simple text search on cards
            try:
                # Escape LIKE wildcards to prevent pattern manipulation
                escaped_q = (
                    search_query[:50]
                    .replace("\\", "\\\\")
                    .replace("%", "\\%")
                    .replace("_", "\\_")
                )
                search_result = await db.execute(
                    sa_select(Card)
                    .where(
                        or_(
                            Card.name.ilike(f"%{escaped_q}%"),
                            Card.summary.ilike(f"%{escaped_q}%"),
                        ),
                        Card.status == "active",
                    )
                    .limit(10)
                )
                rows = search_result.scalars().all()
                results = []
                for r in rows:
                    results.append(
                        {
                            "id": str(r.id),
                            "name": r.name,
                            "summary": r.summary,
                            "grantor": r.grantor,
                            "deadline": r.deadline.isoformat() if r.deadline else None,
                            "funding_amount_min": (
                                float(r.funding_amount_min)
                                if r.funding_amount_min is not None
                                else None
                            ),
                            "funding_amount_max": (
                                float(r.funding_amount_max)
                                if r.funding_amount_max is not None
                                else None
                            ),
                            "grant_type": r.grant_type,
                            "similarity": 0,
                        }
                    )
            except Exception as e2:
                logger.error("Text search also failed: %s", e2)
                results = []

        # Format results
        matched_grants = []
        for card in results:
            matched_grants.append(
                {
                    "card_id": str(card.get("id", "")),
                    "grant_name": card.get("name", ""),
                    "grantor": card.get("grantor", ""),
                    "summary": card.get("summary", ""),
                    "deadline": card.get("deadline"),
                    "funding_amount_min": card.get("funding_amount_min"),
                    "funding_amount_max": card.get("funding_amount_max"),
                    "grant_type": card.get("grant_type"),
                    "similarity": card.get("similarity", 0),
                }
            )

        return {"grants": matched_grants, "query_used": search_query[:200]}

    # -- Card creation ------------------------------------------------------

    async def create_card_from_grant(
        self,
        db: AsyncSession,
        grant_context: GrantContext,
        user_id: str,
        source_url: Optional[str] = None,
    ) -> str:
        """Create a card in the cards table from extracted grant data.

        Args:
            db: AsyncSession instance.
            grant_context: Parsed grant context from AI extraction.
            user_id: UUID of the user creating the card.
            source_url: Optional source URL for the grant.

        Returns:
            The UUID of the newly created card.

        Raises:
            Exception: If the database insert fails.
        """
        now = datetime.now(timezone.utc)

        # Generate a unique slug from the grant name
        card_name = grant_context.grant_name or "Untitled Grant Opportunity"
        slug = card_name.lower()
        slug = "".join(c if c.isalnum() or c == " " else "" for c in slug)
        slug = "-".join(slug.split())
        slug = slug[:50]
        # Append short UUID suffix for uniqueness
        slug = f"{slug}-{uuid.uuid4().hex[:8]}"

        card_data: Dict[str, Any] = {
            "name": card_name,
            "slug": slug,
            "summary": grant_context.summary or "",
            "description": grant_context.summary or "",
            "grantor": grant_context.grantor,
            "deadline": grant_context.deadline,
            "funding_amount_min": grant_context.funding_amount_min,
            "funding_amount_max": grant_context.funding_amount_max,
            "eligibility_text": grant_context.eligibility_text,
            "grant_type": grant_context.grant_type,
            "cfda_number": grant_context.cfda_number,
            "match_requirement": grant_context.match_requirement,
            "created_by": user_id,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }

        if source_url:
            card_data["source_url"] = source_url

        logger.info(
            "Creating card from grant context: %s (user=%s)",
            card_data["name"],
            user_id,
        )

        # Only set attributes that exist on the Card model
        card_kwargs = {k: v for k, v in card_data.items() if hasattr(Card, k)}
        card_obj = Card(**card_kwargs)
        db.add(card_obj)
        await db.flush()
        await db.refresh(card_obj)

        card_id = str(card_obj.id)
        logger.info("Created card %s from grant context", card_id)
        return card_id
