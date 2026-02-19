"""Card analysis service for automatic AI-powered grant opportunity analysis.

When a card is created through any creation path, a ``card_analysis`` task is
queued for the background worker.  The worker calls
:func:`execute_card_analysis` which enriches the card with a comprehensive
AI-generated description, structured scores, and a fresh embedding.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.research import ResearchTask

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass — attributes match what execute_research_task_background()
# extracts in its result_summary dict (research.py lines 186-195).
# ---------------------------------------------------------------------------


@dataclass
class CardAnalysisResult:
    """Holds the outcome of a card analysis run."""

    sources_found: int = 0
    sources_relevant: int = 0
    sources_added: int = 0
    cards_matched: int = 0
    cards_created: int = 0
    entities_extracted: int = 0
    cost_estimate: float = 0.0
    report_preview: str = ""


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

COMPREHENSIVE_ANALYSIS_PROMPT = """\
You are a senior grant analyst for the City of Austin, Texas. Your task is to \
produce a comprehensive, professional description of a grant opportunity and \
provide structured scoring.

IMPORTANT: You are writing for municipal government grant coordinators who need \
actionable intelligence for go/no-go decisions.

## Output Format

Write a detailed description in markdown, then put `---` on its own line, \
then output a JSON object with scores.

## Description Sections (before ---)

### Grant Overview
Provide specific details: funding amount, grantor agency, program name, CFDA \
number if available. Include key dates and any program-specific numbers.

### Eligibility & Requirements
Who can apply? What are the specific requirements? Does the City of Austin \
qualify? What about subrecipient requirements?

### Strategic Fit for Austin
How does this align with Austin's strategic framework? Which departments or \
divisions could benefit? Connect to existing city programs or initiatives.

### Application Considerations
Competition level assessment. Key dates and deadlines. Preparation \
requirements. Match/cost-share requirements if any.

### Key Details
Reporting requirements, performance metrics, multi-year provisions, and \
any other operationally important information.

TARGET LENGTH: 500-800 words. Descriptions under 400 words are inadequate. \
Be specific, use actual numbers and dates when available.

## Scores (after --- separator)

Output ONLY a JSON object (no markdown fences) with these fields, each 0-100:

{
  "alignment_score": <int>,
  "readiness_score": <int>,
  "competition_score": <int>,
  "urgency_score": <int>,
  "probability_score": <int>,
  "impact_score": <int>,
  "relevance_score": <int>,
  "summary": "<1-2 sentence summary for card display>"
}

- alignment_score: How well this fits Austin's strategic priorities
- readiness_score: How prepared Austin is to apply (staff, systems, history)
- competition_score: Estimated competition level (100 = low competition = good)
- urgency_score: Time pressure (100 = deadline approaching fast)
- probability_score: Likelihood of successful application
- impact_score: Potential impact on Austin residents/operations
- relevance_score: Overall relevance to city needs
- summary: Concise 1-2 sentence summary
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def queue_card_analysis(
    db: AsyncSession,
    card_id: str,
    user_id: str,
) -> Optional[str]:
    """Queue a background ``card_analysis`` task for *card_id*.

    Idempotent: if there is already a queued or processing task for this card,
    returns ``None`` instead of creating a duplicate.

    Returns the task ID as a string, or ``None`` if already queued.
    """
    card_uuid = uuid.UUID(card_id)

    # Check for an existing queued/processing card_analysis task for this card
    stmt = (
        select(ResearchTask.id)
        .where(ResearchTask.card_id == card_uuid)
        .where(ResearchTask.task_type == "card_analysis")
        .where(ResearchTask.status.in_(["queued", "processing"]))
        .limit(1)
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing is not None:
        logger.debug(
            "card_analysis already queued/processing for card %s (task %s)",
            card_id,
            existing,
        )
        return None

    task = ResearchTask(
        card_id=card_uuid,
        user_id=uuid.UUID(user_id),
        task_type="card_analysis",
        status="queued",
    )
    db.add(task)
    await db.flush()

    task_id = str(task.id)
    logger.info("Queued card_analysis task %s for card %s", task_id, card_id)
    return task_id


async def execute_card_analysis(
    db: AsyncSession,
    card_id: str,
    task_id: str,
) -> CardAnalysisResult:
    """Run the full AI analysis pipeline for a card.

    Steps:
    1. Fetch card metadata from DB
    2. Gather linked source context
    3. Optionally fetch grants.gov details
    4. Optionally web-search for additional context if description is thin
    5. Call Azure OpenAI gpt-4.1 for comprehensive analysis
    6. Parse response (description + JSON scores)
    7. Update card with enriched description, summary, and scores
    8. Generate and store embedding
    9. Record timeline event

    Returns a :class:`CardAnalysisResult` compatible with the worker's
    result_summary extraction.
    """

    # ------------------------------------------------------------------
    # 1. Fetch card
    # ------------------------------------------------------------------
    card_row = await db.execute(
        text(
            "SELECT name, summary, description, grants_gov_id, "
            "sam_opportunity_id, grantor, source_url "
            "FROM cards WHERE id = CAST(:card_id AS uuid)"
        ),
        {"card_id": card_id},
    )
    card = card_row.one_or_none()
    if card is None:
        raise ValueError(f"Card {card_id} not found")

    card_name = card.name or "Unnamed opportunity"
    card_summary = card.summary or ""
    card_description = card.description or ""
    grants_gov_id = card.grants_gov_id
    grantor = card.grantor or ""
    source_url = card.source_url or ""

    # ------------------------------------------------------------------
    # 2. Gather linked source context
    # ------------------------------------------------------------------
    source_rows = await db.execute(
        text(
            "SELECT s.title, s.url, s.ai_summary, s.full_text "
            "FROM sources s "
            "JOIN signal_sources ss ON s.id = ss.source_id "
            "WHERE ss.card_id = CAST(:card_id AS uuid) "
            "LIMIT 10"
        ),
        {"card_id": card_id},
    )
    sources: List[Dict[str, Any]] = [
        {
            "title": r.title,
            "url": r.url,
            "ai_summary": r.ai_summary,
            "full_text": (r.full_text or "")[:2000],
        }
        for r in source_rows
    ]

    sources_found = len(sources)

    # ------------------------------------------------------------------
    # 3. Optionally fetch grants.gov details
    # ------------------------------------------------------------------
    grants_gov_detail: Optional[Dict[str, Any]] = None
    if grants_gov_id:
        try:
            from app.source_fetchers.grants_gov_fetcher import (
                fetch_opportunity_details,
            )

            grants_gov_detail = await fetch_opportunity_details(grants_gov_id)
        except Exception as e:
            logger.debug(
                "Could not fetch grants.gov detail for %s: %s", grants_gov_id, e
            )

    # ------------------------------------------------------------------
    # 4. Multi-source search for thin descriptions
    # ------------------------------------------------------------------
    web_results: List[Dict[str, str]] = []
    if len(card_description) < 1600:
        try:
            from app.multi_source_search import search_all_sources

            search_query = f"{card_name} grant opportunity"
            multi_results = await search_all_sources(
                search_query,
                max_results_per_source=3,
                include_academic=False,
            )
            web_results = [
                {
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet,
                }
                for r in multi_results
            ]
            sources_found += len(web_results)
        except Exception as e:
            logger.debug("Multi-source search failed for card %s: %s", card_id, e)

    # ------------------------------------------------------------------
    # 5. Build context for the AI prompt
    # ------------------------------------------------------------------
    context_parts = [
        f"# Grant Opportunity: {card_name}",
        f"Grantor: {grantor}" if grantor else "",
        f"Source URL: {source_url}" if source_url else "",
        "",
        "## Current Description",
        card_description or "(no description yet)",
        "",
    ]

    if card_summary:
        context_parts.append(f"## Current Summary\n{card_summary}\n")

    if grants_gov_detail:
        context_parts.append("## Grants.gov Details")
        # Include relevant fields from the detail dict
        for key in (
            "synopsis",
            "description",
            "eligibility",
            "funding_amount",
            "close_date",
            "cfda_number",
            "agency_name",
        ):
            val = grants_gov_detail.get(key)
            if val:
                context_parts.append(f"**{key}**: {str(val)[:3000]}")
        context_parts.append("")

    if sources:
        context_parts.append("## Linked Sources")
        for src in sources:
            context_parts.append(f"### {src['title'] or 'Untitled'}")
            if src["url"]:
                context_parts.append(f"URL: {src['url']}")
            if src["ai_summary"]:
                context_parts.append(src["ai_summary"])
            elif src["full_text"]:
                context_parts.append(src["full_text"][:1500])
            context_parts.append("")

    if web_results:
        context_parts.append("## Web Search Results")
        for wr in web_results:
            context_parts.append(f"- **{wr['title']}** ({wr['url']})")
            if wr["snippet"]:
                context_parts.append(f"  {wr['snippet']}")
        context_parts.append("")

    context_text = "\n".join(context_parts)

    # ------------------------------------------------------------------
    # 6. Call Azure OpenAI for analysis
    # ------------------------------------------------------------------
    from app.openai_provider import azure_openai_async_client, get_chat_deployment

    response = await azure_openai_async_client.chat.completions.create(
        model=get_chat_deployment(),
        messages=[
            {"role": "system", "content": COMPREHENSIVE_ANALYSIS_PROMPT},
            {"role": "user", "content": context_text},
        ],
        temperature=0.3,
        max_tokens=4000,
    )

    raw_content = (response.choices[0].message.content or "").strip()

    # ------------------------------------------------------------------
    # 7. Parse response: description (before ---) and scores (after ---)
    # ------------------------------------------------------------------
    new_description = raw_content
    new_summary = card_summary
    scores: Dict[str, Any] = {}

    if "---" in raw_content:
        parts = raw_content.split("---", 1)
        new_description = parts[0].strip()
        json_part = parts[1].strip()

        # Strip markdown code fences if present
        if json_part.startswith("```"):
            lines = json_part.split("\n")
            lines = [ln for ln in lines if not ln.strip().startswith("```")]
            json_part = "\n".join(lines)

        try:
            scores = json.loads(json_part)
            # Extract summary from scores if present
            if "summary" in scores and scores["summary"]:
                new_summary = scores["summary"]
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse scores JSON for card %s: %s", card_id, e)

    # ------------------------------------------------------------------
    # 8. Update card with enriched description, summary, and scores
    # ------------------------------------------------------------------
    from sqlalchemy import update as sa_update
    from app.models.db.card import Card as CardModel
    from datetime import datetime, timezone

    update_values: Dict[str, Any] = {
        "description": new_description,
        "summary": new_summary,
        "updated_at": datetime.now(timezone.utc),
    }

    # Add parsed score values (clamped to 0-100)
    score_fields = [
        "alignment_score",
        "readiness_score",
        "competition_score",
        "urgency_score",
        "probability_score",
        "impact_score",
        "relevance_score",
    ]
    for sf in score_fields:
        val = scores.get(sf)
        if val is not None:
            try:
                update_values[sf] = max(0, min(100, int(val)))
            except (ValueError, TypeError):
                pass

    card_uuid = uuid.UUID(card_id)
    await db.execute(
        sa_update(CardModel).where(CardModel.id == card_uuid).values(**update_values)
    )
    await db.flush()

    # ------------------------------------------------------------------
    # 9. Generate and store embedding
    # ------------------------------------------------------------------
    try:
        from app.helpers.db_utils import generate_and_store_embedding

        await generate_and_store_embedding(db, card_id)
    except Exception as e:
        logger.warning("Failed to generate embedding for card %s: %s", card_id, e)

    # ------------------------------------------------------------------
    # 10. Create timeline event
    # ------------------------------------------------------------------
    try:
        from app.models.db.card_extras import CardTimeline

        timeline = CardTimeline(
            card_id=uuid.UUID(card_id),
            event_type="ai_analysis_complete",
            title="AI Analysis Complete",
            description=f"Comprehensive AI analysis generated ({len(new_description)} chars)",
        )
        db.add(timeline)
        await db.flush()
    except Exception as e:
        logger.warning("Failed to create timeline event for card %s: %s", card_id, e)

    # ------------------------------------------------------------------
    # 11. Return result
    # ------------------------------------------------------------------
    return CardAnalysisResult(
        sources_found=sources_found,
        sources_relevant=len(sources),
        sources_added=0,
        cards_matched=0,
        cards_created=0,
        entities_extracted=0,
        cost_estimate=0.0,
        report_preview=new_description[:500],
    )
