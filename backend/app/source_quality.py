"""
Source-level quality scoring for GrantScope.

Computes a composite quality score (0-100) for each individual source based
on five dimensions: content richness, relevance, domain reputation, source
credibility, and recency.  This is distinct from the card-level SQI in
``quality_service.py``; the source quality score evaluates a *single*
source's trustworthiness and informativeness.

Score Breakdown (100 points total)
----------------------------------
- **Content Richness  (0-25)**:  presence and length of full_text, summary,
  and key excerpts.
- **Relevance         (0-25)**:  triage relevance_level or relevance_to_card.
- **Domain Reputation  (0-25)**:  curated tier, composite score, or TLD
  heuristics.
- **Source Credibility (0-15)**:  peer-review status and AI credibility score.
- **Recency           (0-10)**:  how recently the source was published.

Usage
-----
    from app.source_quality import (
        score_source,
        extract_domain,
        compute_and_store_quality_score,
        backfill_quality_scores,
        get_domain_stats,
    )

    # Score a source dict
    quality = score_source(source_data, analysis=analysis, domain_reputation=rep)

    # Compute, persist, and return score for a single source
    score = await compute_and_store_quality_score(db, source_id)

    # Backfill all unscored sources
    stats = await backfill_quality_scores(db, batch_size=100)

Dependencies
------------
- ``ai_service.AnalysisResult`` / ``TriageResult`` -- optional scoring inputs.
- ``domain_reputation`` table -- looked up when a source has a
  ``domain_reputation_id``.
- ``sources`` table columns added by migration ``20260213_source_quality_dedup``.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from sqlalchemy import select, update as sa_update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.source import Source
from app.models.db.analytics import DomainReputation

from .ai_service import AnalysisResult, TriageResult

logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Known high-credibility TLDs used as fallback when no domain_reputation row
# exists.  Scores approximate what a curated Tier 1/2 entry would yield.
_TLD_SCORES: Dict[str, int] = {
    ".gov": 22,
    ".edu": 20,
    ".mil": 22,
    ".int": 20,
}

# Domains we recognise even without a domain_reputation entry.  These are
# common sources that appear in discovery but may not yet be seeded in the
# domain_reputation table.
_KNOWN_DOMAIN_SCORES: Dict[str, int] = {
    "nature.com": 20,
    "science.org": 20,
    "ieee.org": 18,
    "acm.org": 18,
    "nih.gov": 22,
    "who.int": 20,
    "worldbank.org": 18,
    "brookings.edu": 20,
    "rand.org": 18,
    "nist.gov": 22,
    "gartner.com": 18,
    "mckinsey.com": 18,
    "deloitte.com": 15,
    "reuters.com": 15,
    "apnews.com": 15,
    "bbc.com": 15,
    "nytimes.com": 15,
    "washingtonpost.com": 15,
    "bloomberg.com": 15,
}

# Default score when domain is completely unknown.
_UNKNOWN_DOMAIN_SCORE = 8


# ============================================================================
# Domain Extraction
# ============================================================================


def extract_domain(url: str) -> str:
    """Extract the registered domain from a URL.

    Strips the ``www.`` prefix and returns the base domain.  For example::

        "https://www.austin.gov/news/article" -> "austin.gov"
        "http://research.gartner.com/report"  -> "research.gartner.com"
        "ftp://files.example.org/data.csv"    -> "files.example.org"

    Parameters
    ----------
    url : str
        A fully-qualified URL.  If the scheme is missing the function
        attempts a best-effort parse.

    Returns
    -------
    str
        The extracted domain in lowercase, or an empty string if extraction
        fails.
    """
    if not url:
        return ""

    try:
        # Handle URLs that may be missing a scheme.
        if "://" not in url:
            url = "https://" + url

        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower().strip()

        if not hostname:
            return ""

        # Strip leading "www." to normalise.
        if hostname.startswith("www."):
            hostname = hostname[4:]

        return hostname
    except Exception:
        logger.debug("Failed to extract domain from URL: %s", url)
        return ""


# ============================================================================
# Score Components
# ============================================================================


def _score_content_richness(source: dict) -> int:
    """Content Richness sub-score (0-25).

    Rewards sources that have rich, extractable content.  More text and
    structured summaries indicate a source that can meaningfully inform
    a strategic intelligence card.

    Parameters
    ----------
    source : dict
        A source row from the ``sources`` table.

    Returns
    -------
    int
        Score in [0, 25].
    """
    score = 0

    # Has full_text with meaningful content (>200 chars).
    full_text = source.get("full_text") or source.get("content") or ""
    if isinstance(full_text, str) and len(full_text) > 200:
        score += 10

    # Has AI summary.
    ai_summary = source.get("ai_summary") or source.get("summary") or ""
    if isinstance(ai_summary, str) and len(ai_summary.strip()) > 0:
        score += 5

    # Has key excerpts (non-empty array).
    key_excerpts = source.get("key_excerpts")
    if isinstance(key_excerpts, list) and len(key_excerpts) > 0:
        score += 5

    # Bonus for length of full_text.
    text_len = len(full_text) if isinstance(full_text, str) else 0
    if text_len > 5000:
        score += 5
    elif text_len > 2000:
        score += 3
    elif text_len > 500:
        score += 1

    return min(score, 25)


def _score_relevance(
    source: dict,
    triage: Optional[TriageResult] = None,
) -> int:
    """Relevance sub-score (0-25).

    Prefers the triage relevance_level when available (set by the discovery
    pipeline's AI triage step) and falls back to the numeric
    ``relevance_to_card`` value stored on the source row.

    Parameters
    ----------
    source : dict
        A source row from the ``sources`` table.
    triage : TriageResult, optional
        Triage result from the discovery pipeline, if available.

    Returns
    -------
    int
        Score in [0, 25].
    """
    # Prefer triage relevance_level when available.
    if triage is not None:
        level = getattr(triage, "relevance_level", None) or ""
        level = level.lower().strip()
        if level == "high":
            return 25
        elif level == "medium":
            return 15
        elif level == "low":
            return 5

    # Fall back to relevance_to_card (NUMERIC 0.00-1.00 in the DB, or
    # sometimes stored as 0-5).
    relevance = source.get("relevance_to_card")
    if relevance is not None:
        try:
            val = float(relevance)
            # If the value is on a 0-1 scale, multiply by 25.
            # If on a 0-5 scale, multiply by 5.
            if val <= 1.0:
                return min(int(round(val * 25)), 25)
            else:
                return min(int(round(val * 5)), 25)
        except (TypeError, ValueError):
            pass

    # Fall back to relevance_score (INTEGER 0-100) mapped to 0-25.
    relevance_score = source.get("relevance_score")
    if relevance_score is not None:
        try:
            return min(int(round(float(relevance_score) / 4)), 25)
        except (TypeError, ValueError):
            pass

    # Unknown relevance -- conservative middle score.
    return 10


def _score_domain_reputation(
    source: dict,
    domain_reputation: Optional[dict] = None,
) -> int:
    """Domain Reputation sub-score (0-25).

    Uses the ``domain_reputation`` record when available, falling back to
    TLD-based heuristics for common government and academic domains.

    Parameters
    ----------
    source : dict
        A source row from the ``sources`` table.
    domain_reputation : dict, optional
        A row from the ``domain_reputation`` table, if looked up.

    Returns
    -------
    int
        Score in [0, 25].
    """
    if domain_reputation:
        # Use curated_tier if available -- it's the most authoritative signal.
        curated_tier = domain_reputation.get("curated_tier")
        if curated_tier is not None:
            try:
                tier = int(curated_tier)
                if tier == 1:
                    return 25
                elif tier == 2:
                    return 18
                elif tier == 3:
                    return 10
            except (TypeError, ValueError):
                pass

        # Fall back to composite_score mapped to 0-25.
        composite = domain_reputation.get("composite_score")
        if composite is not None:
            try:
                # composite_score is 0-100+; map linearly to 0-25.
                return min(int(round(float(composite) / 4)), 25)
            except (TypeError, ValueError):
                pass

    # No domain_reputation row -- use TLD and known-domain heuristics.
    url = source.get("url") or ""
    domain = extract_domain(url)

    if not domain:
        return _UNKNOWN_DOMAIN_SCORE

    # Check known domains first (exact match).
    if domain in _KNOWN_DOMAIN_SCORES:
        return _KNOWN_DOMAIN_SCORES[domain]

    # Check TLD heuristics.
    for tld, tld_score in _TLD_SCORES.items():
        if domain.endswith(tld):
            return tld_score

    return _UNKNOWN_DOMAIN_SCORE


def _score_credibility(
    source: dict,
    analysis: Optional[AnalysisResult] = None,
) -> int:
    """Source Credibility sub-score (0-15).

    Combines peer-review status (a strong positive signal) with the AI
    credibility rating from analysis.

    Parameters
    ----------
    source : dict
        A source row from the ``sources`` table.
    analysis : AnalysisResult, optional
        Full analysis result from the AI pipeline, if available.

    Returns
    -------
    int
        Score in [0, 15].
    """
    score = 0

    # Peer-reviewed status is a strong credibility signal.
    is_peer_reviewed = source.get("is_peer_reviewed")
    if is_peer_reviewed is True:
        score += 10

    # AI credibility score (1.0-5.0 scale from AnalysisResult).
    if analysis is not None:
        credibility = getattr(analysis, "credibility", None)
        if credibility is not None:
            try:
                cred_val = float(credibility)
                # Map 1.0-5.0 to 0-15: (cred - 1) / 4 * 15
                mapped = (cred_val - 1.0) / 4.0 * 15.0
                score += int(round(max(0.0, min(mapped, 15.0))))
            except (TypeError, ValueError):
                score += 7  # Neutral fallback
    elif is_peer_reviewed is not True:
        # No analysis and not peer-reviewed -- neutral fallback.
        score += 7

    return min(score, 15)


def _score_recency(source: dict) -> int:
    """Recency sub-score (0-10).

    Rewards recently published sources.  For horizon scanning, fresher
    evidence is generally more actionable.

    Parameters
    ----------
    source : dict
        A source row from the ``sources`` table.

    Returns
    -------
    int
        Score in [0, 10].
    """
    published = source.get("published_date")
    if not published:
        return 1  # Unknown publication date -- minimal score.

    try:
        if isinstance(published, str):
            # Parse ISO 8601 datetime string.  Handles both aware and naive.
            pub_str = published.replace("Z", "+00:00")
            pub_date = datetime.fromisoformat(pub_str)
        elif isinstance(published, datetime):
            pub_date = published
        else:
            return 1

        # Ensure timezone-aware for comparison.
        if pub_date.tzinfo is None:
            pub_date = pub_date.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        age_days = (now - pub_date).days

        if age_days < 0:
            # Future date -- treat as very recent (data entry artefact).
            return 10
        elif age_days <= 30:
            return 10
        elif age_days <= 90:
            return 7
        elif age_days <= 180:
            return 5
        elif age_days <= 365:
            return 3
        else:
            return 1

    except (ValueError, TypeError, OverflowError):
        logger.debug("Failed to parse published_date: %s", published)
        return 1


# ============================================================================
# Main Scoring Function
# ============================================================================


def score_source(
    source_data: dict,
    analysis: Optional[AnalysisResult] = None,
    triage: Optional[TriageResult] = None,
    domain_reputation: Optional[dict] = None,
) -> int:
    """Compute a composite quality score (0-100) for a single source.

    The score is the sum of five independently computed sub-scores:

    - Content Richness  (0-25)
    - Relevance         (0-25)
    - Domain Reputation  (0-25)
    - Source Credibility (0-15)
    - Recency           (0-10)

    All inputs are optional and gracefully degrade to conservative defaults
    when missing.  The function never raises; it returns a valid integer in
    [0, 100] under all circumstances.

    Parameters
    ----------
    source_data : dict
        A row from the ``sources`` table (or an equivalent dict).
    analysis : AnalysisResult, optional
        Full AI analysis result containing credibility scores.
    triage : TriageResult, optional
        Triage result with relevance_level from the discovery pipeline.
    domain_reputation : dict, optional
        A row from the ``domain_reputation`` table for this source's domain.

    Returns
    -------
    int
        Composite quality score in [0, 100].
    """
    try:
        content = _score_content_richness(source_data)
        relevance = _score_relevance(source_data, triage)
        domain_rep = _score_domain_reputation(source_data, domain_reputation)
        credibility = _score_credibility(source_data, analysis)
        recency = _score_recency(source_data)

        total = content + relevance + domain_rep + credibility + recency

        # Clamp to [0, 100] as a safety measure (sub-scores are individually
        # capped, but belt-and-suspenders).
        return max(0, min(total, 100))

    except Exception:
        logger.exception("Unexpected error computing quality score for source")
        return 0


# ============================================================================
# Database Integration
# ============================================================================


def _source_to_dict(source_obj: Source) -> dict:
    """Convert a Source ORM object to a dict for scoring functions."""
    return {
        "id": str(source_obj.id) if source_obj.id else None,
        "url": source_obj.url,
        "full_text": source_obj.full_text,
        "content": source_obj.content,
        "ai_summary": source_obj.ai_summary,
        "summary": source_obj.summary,
        "key_excerpts": source_obj.key_excerpts,
        "relevance_to_card": source_obj.relevance_to_card,
        "relevance_score": source_obj.relevance_score,
        "published_date": source_obj.published_date,
        "is_peer_reviewed": source_obj.is_peer_reviewed,
        "domain_reputation_id": source_obj.domain_reputation_id,
        "quality_score": source_obj.quality_score,
        "domain": source_obj.domain,
    }


def _domain_rep_to_dict(dr_obj: DomainReputation) -> dict:
    """Convert a DomainReputation ORM object to a dict for scoring functions."""
    return {
        "id": str(dr_obj.id) if dr_obj.id else None,
        "domain_pattern": dr_obj.domain_pattern,
        "curated_tier": dr_obj.curated_tier,
        "composite_score": dr_obj.composite_score,
        "user_quality_avg": dr_obj.user_quality_avg,
        "triage_pass_rate": dr_obj.triage_pass_rate,
        "texas_relevance_bonus": dr_obj.texas_relevance_bonus,
        "is_active": dr_obj.is_active,
    }


async def compute_and_store_quality_score(
    db: AsyncSession,
    source_id: str,
    analysis: Optional[AnalysisResult] = None,
    triage: Optional[TriageResult] = None,
) -> int:
    """Compute the quality score for a source and persist it.

    Fetches the source record and its linked domain_reputation (if any),
    computes the quality score via :func:`score_source`, extracts the
    domain, and writes both ``quality_score`` and ``domain`` back to the
    ``sources`` table.

    Parameters
    ----------
    db : AsyncSession
        SQLAlchemy async database session.
    source_id : str
        UUID of the source to score.
    analysis : AnalysisResult, optional
        AI analysis result, if available.
    triage : TriageResult, optional
        Triage result, if available.

    Returns
    -------
    int
        The computed quality score (0-100), or 0 if the source was not found.
    """
    try:
        # Fetch the source record.
        result = await db.execute(select(Source).where(Source.id == source_id).limit(1))
        source_obj = result.scalar_one_or_none()
        if not source_obj:
            logger.warning("Source not found for quality scoring: %s", source_id)
            return 0

        source_data = _source_to_dict(source_obj)

        # Look up domain reputation if the source has a linked entry.
        domain_rep = None
        dr_id = source_obj.domain_reputation_id
        if dr_id:
            dr_result = await db.execute(
                select(DomainReputation).where(DomainReputation.id == dr_id).limit(1)
            )
            dr_obj = dr_result.scalar_one_or_none()
            if dr_obj:
                domain_rep = _domain_rep_to_dict(dr_obj)

        # Compute score.
        quality = score_source(
            source_data,
            analysis=analysis,
            triage=triage,
            domain_reputation=domain_rep,
        )

        # Extract domain from URL.
        url = source_obj.url or ""
        domain = extract_domain(url)

        # Persist quality_score and domain.
        update_values: Dict[str, Any] = {"quality_score": quality}
        if domain:
            update_values["domain"] = domain

        await db.execute(
            sa_update(Source).where(Source.id == source_id).values(**update_values)
        )
        await db.flush()

        logger.debug(
            "Scored source %s: quality=%d, domain=%s",
            source_id,
            quality,
            domain or "(none)",
        )
        return quality

    except Exception:
        logger.exception(
            "Failed to compute/store quality score for source %s", source_id
        )
        return 0


# ============================================================================
# Domain Statistics
# ============================================================================


async def get_domain_stats(db: AsyncSession, limit: int = 50) -> List[dict]:
    """Return aggregated quality statistics per domain.

    Queries the ``sources`` table grouped by the ``domain`` column to
    produce a leaderboard of domains with their quality score distribution
    and source counts.

    Parameters
    ----------
    db : AsyncSession
        SQLAlchemy async database session.
    limit : int
        Maximum number of domains to return (default 50).

    Returns
    -------
    list[dict]
        Each entry contains:
        - ``domain``: the domain name.
        - ``total_sources``: count of sources from this domain.
        - ``avg_quality``: average quality_score (rounded).
        - ``min_quality``: minimum quality_score.
        - ``max_quality``: maximum quality_score.
        - ``scored_sources``: count of sources that have a quality_score.
    """
    try:
        # Fetch scored sources grouped by domain using SQLAlchemy aggregation.
        scored_stmt = (
            select(
                Source.domain,
                func.count(Source.id).label("scored_sources"),
                func.avg(Source.quality_score).label("avg_quality"),
                func.min(Source.quality_score).label("min_quality"),
                func.max(Source.quality_score).label("max_quality"),
            )
            .where(
                and_(
                    Source.domain.isnot(None),
                    Source.quality_score.isnot(None),
                )
            )
            .group_by(Source.domain)
        )
        scored_result = await db.execute(scored_stmt)
        scored_rows = scored_result.all()

        if not scored_rows:
            return []

        # Build result dict keyed by domain.
        domain_data: Dict[str, dict] = {}
        for row in scored_rows:
            domain_data[row.domain] = {
                "domain": row.domain,
                "scored_sources": row.scored_sources,
                "avg_quality": round(float(row.avg_quality)) if row.avg_quality else 0,
                "min_quality": row.min_quality or 0,
                "max_quality": row.max_quality or 0,
                "total_sources": row.scored_sources,  # Will be overwritten below
            }

        # Also count total sources per domain (including unscored).
        total_stmt = (
            select(
                Source.domain,
                func.count(Source.id).label("total"),
            )
            .where(Source.domain.isnot(None))
            .group_by(Source.domain)
        )
        total_result = await db.execute(total_stmt)
        total_rows = total_result.all()

        for row in total_rows:
            if row.domain in domain_data:
                domain_data[row.domain]["total_sources"] = row.total

        # Sort by total_sources descending, limit.
        results = sorted(
            domain_data.values(), key=lambda x: x["total_sources"], reverse=True
        )
        return results[:limit]

    except Exception:
        logger.exception("Failed to compute domain stats")
        return []


# ============================================================================
# Backfill
# ============================================================================


async def backfill_quality_scores(
    db: AsyncSession,
    batch_size: int = 50,
) -> dict:
    """Batch-score sources that don't have a quality_score yet.

    Processes sources in batches, computing and persisting quality scores
    and extracted domains.  Designed to be run as a one-off migration task
    or periodic maintenance job.

    Parameters
    ----------
    db : AsyncSession
        SQLAlchemy async database session.
    batch_size : int
        Number of sources to process per batch (default 50).

    Returns
    -------
    dict
        Summary statistics::

            {
                "total_processed": 150,
                "total_scored": 148,
                "total_failed": 2,
                "avg_quality": 42,
            }
    """
    total_processed = 0
    total_scored = 0
    total_failed = 0
    all_scores: List[int] = []

    logger.info("Starting quality score backfill (batch_size=%d)", batch_size)

    while True:
        try:
            # Fetch a batch of unscored sources.
            result = await db.execute(
                select(Source).where(Source.quality_score.is_(None)).limit(batch_size)
            )
            batch = result.scalars().all()

            if not batch:
                logger.info("No more unscored sources. Backfill complete.")
                break

            logger.info("Processing batch of %d unscored sources", len(batch))

            for source_obj in batch:
                total_processed += 1
                source_id = source_obj.id
                if not source_id:
                    total_failed += 1
                    continue

                try:
                    source_data = _source_to_dict(source_obj)

                    # Look up domain reputation if linked.
                    domain_rep = None
                    dr_id = source_obj.domain_reputation_id
                    if dr_id:
                        dr_result = await db.execute(
                            select(DomainReputation)
                            .where(DomainReputation.id == dr_id)
                            .limit(1)
                        )
                        dr_obj = dr_result.scalar_one_or_none()
                        if dr_obj:
                            domain_rep = _domain_rep_to_dict(dr_obj)

                    # Compute score.
                    quality = score_source(source_data, domain_reputation=domain_rep)

                    # Extract domain.
                    url = source_obj.url or ""
                    domain = extract_domain(url)

                    # Persist.
                    update_values: Dict[str, Any] = {"quality_score": quality}
                    if domain:
                        update_values["domain"] = domain

                    await db.execute(
                        sa_update(Source)
                        .where(Source.id == source_id)
                        .values(**update_values)
                    )
                    await db.flush()

                    total_scored += 1
                    all_scores.append(quality)

                except Exception:
                    logger.exception(
                        "Failed to score source %s during backfill", source_id
                    )
                    total_failed += 1

            # If the batch was smaller than batch_size, we've exhausted all
            # unscored sources.
            if len(batch) < batch_size:
                break

        except Exception:
            logger.exception("Error fetching batch during backfill")
            break

    avg_quality = round(sum(all_scores) / len(all_scores)) if all_scores else 0

    summary = {
        "total_processed": total_processed,
        "total_scored": total_scored,
        "total_failed": total_failed,
        "avg_quality": avg_quality,
    }
    logger.info("Quality score backfill complete: %s", summary)
    return summary
