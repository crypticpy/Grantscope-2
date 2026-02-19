"""
Source Quality Index (SQI) calculation service for GrantScope.

Computes a composite quality score (0-100) for each card based on the
credibility, diversity, and freshness of its underlying sources.  The SQI
is designed to give decision-makers a quick, defensible signal about how
much weight to place on a card's claims.

Architecture
------------
The SQI is a weighted composite of five independent dimensions:

    SQI = (source_authority   * 0.30)
        + (source_diversity   * 0.20)
        + (corroboration      * 0.20)
        + (recency            * 0.15)
        + (municipal_specificity * 0.15)

Each dimension produces a sub-score in the range [0, 100].  The weighted
sum is rounded to the nearest integer and clamped to [0, 100].

Weight Rationale
----------------
- **Source Authority (30%)** receives the largest weight because the
  credibility of the originating domain (e.g., a Tier 1 research firm
  vs. an unknown blog) is the single strongest predictor of information
  reliability.

- **Source Diversity (20%)** rewards cards that draw from multiple
  *types* of sources (RSS, news API, academic, government, etc.).
  Cross-type corroboration is harder to fake and reduces single-source
  risk.

- **Corroboration (20%)** counts how many *independent stories* (via
  the story clustering service) back the card's claims.  Multiple
  clusters mean multiple editorial or research teams arrived at the
  same conclusion independently.

- **Recency (15%)** ensures that cards built on fresh evidence rank
  higher than those relying on dated material.  This is especially
  important for horizon scanning, where timeliness matters.

- **Municipal Specificity (15%)** captures how directly relevant the
  sources are to municipal government operations.  A .gov-domain
  bonus further lifts cards backed by official government publications.

Storage
-------
Results are persisted to two columns on the ``cards`` table:

- ``quality_score`` (INTEGER 0-100): the composite SQI.
- ``quality_breakdown`` (JSONB): the five sub-scores plus metadata::

    {
        "source_authority": 85,
        "source_diversity": 70,
        "corroboration": 50,
        "recency": 100,
        "municipal_specificity": 75,
        "calculated_at": "2025-02-10T12:00:00Z",
        "source_count": 5,
        "cluster_count": 3
    }

Dependencies
------------
- ``domain_reputation_service`` -- provides per-URL authority scores.
- ``story_clustering_service``  -- provides cluster counts for
  corroboration scoring.

Usage
-----
    from app.quality_service import calculate_sqi, recalculate_all_cards, get_breakdown

    # Calculate (or recalculate) SQI for one card
    breakdown = await calculate_sqi(db, card_id="card-abc")

    # Read the stored breakdown without recalculating
    breakdown = await get_breakdown(db, card_id="card-abc")

    # Batch recalculate every card in the system (nightly job)
    summary = await recalculate_all_cards(db)
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.card import Card
from app.models.db.source import Source
from . import domain_reputation_service
from . import story_clustering_service

logger = logging.getLogger(__name__)


# ============================================================================
# SQI Component Weights (must sum to 1.0)
# ============================================================================

WEIGHT_SOURCE_AUTHORITY = 0.30
WEIGHT_SOURCE_DIVERSITY = 0.20
WEIGHT_CORROBORATION = 0.20
WEIGHT_RECENCY = 0.15
WEIGHT_MUNICIPAL_SPECIFICITY = 0.15


# ============================================================================
# Internal Component Calculators
# ============================================================================


async def _calculate_source_authority(
    db: AsyncSession,
    sources: list[dict],
) -> int:
    """
    Calculate the Source Authority sub-score (0-100).

    Measures the average credibility of the domains behind a card's sources
    using the domain reputation system.

    Algorithm
    ---------
    1. Collect all source URLs.
    2. Look up domain reputations in batch (uses in-memory cache for speed).
    3. Convert each reputation to a 0-100 authority score via
       ``domain_reputation_service.get_authority_score()``.
    4. Return the arithmetic mean, rounded to the nearest integer.

    Scoring examples
    ----------------
    - All Tier 1 domains (Gartner, McKinsey): ~85
    - Mix of Tier 1 and Tier 2: ~70
    - All unknown/untiered domains: ~20
    - No sources at all: 0

    Parameters
    ----------
    db : AsyncSession
        SQLAlchemy async session.
    sources : list[dict]
        Source rows from the ``sources`` table.

    Returns
    -------
    int
        Authority sub-score in [0, 100].
    """
    if not sources:
        return 0

    urls = [s["url"] for s in sources if s.get("url")]
    if not urls:
        return 0

    # Batch lookup -- leverages the in-memory cache for efficiency.
    reputations = domain_reputation_service.get_reputation_batch(db, urls)

    # Score each URL.  URLs not found in the reputation table get None,
    # which get_authority_score() handles by returning the untiered default (20).
    authority_scores: list[int] = []
    for url in urls:
        reputation = reputations.get(url)
        authority_scores.append(
            domain_reputation_service.get_authority_score(reputation)
        )

    avg = sum(authority_scores) / len(authority_scores)
    return max(0, min(100, round(avg)))


def _calculate_source_diversity(sources: list[dict]) -> int:
    """
    Calculate the Source Diversity sub-score (0-100).

    Measures how many distinct *types* of sources (API source categories)
    back a card's claims.  Cross-type diversity is valuable because it
    means the information was picked up by fundamentally different
    information channels (e.g., an RSS feed AND an academic paper AND a
    government report).

    Algorithm
    ---------
    Count distinct ``api_source`` values across the card's sources, then
    map through a step-function curve.

    Score curve
    -----------
    ========  =====
    Categories Score
    ========  =====
    5+         100
    4           85
    3           70
    2           50
    1           20
    0            0
    ========  =====

    Scoring examples
    ----------------
    - Sources from rss, newsapi, tavily, academic, gov: 5 categories -> 100
    - Sources from rss, newsapi: 2 categories -> 50
    - All sources from rss only: 1 category -> 20
    - No sources: 0

    Parameters
    ----------
    sources : list[dict]
        Source rows from the ``sources`` table.

    Returns
    -------
    int
        Diversity sub-score in [0, 100].
    """
    if not sources:
        return 0

    distinct_categories = {s.get("api_source") for s in sources if s.get("api_source")}
    count = len(distinct_categories)

    if count >= 5:
        return 100
    if count == 4:
        return 85
    if count == 3:
        return 70
    if count == 2:
        return 50
    return 20 if count == 1 else 0


async def _calculate_corroboration(
    db: AsyncSession,
    card_id: str,
) -> tuple[int, int]:
    """
    Calculate the Corroboration sub-score (0-100).

    Measures how many *independent stories* (as determined by the story
    clustering service) back a card.  Multiple independent story clusters
    mean that separate editorial teams, researchers, or agencies have
    reported on the same topic -- strong evidence of reliability.

    Algorithm
    ---------
    1. Query ``story_clustering_service.get_cluster_count()`` for the card.
    2. Map the cluster count through a step-function curve.

    Score curve
    -----------
    ========  =====
    Clusters  Score
    ========  =====
    5+         100
    4           85
    3           70
    2           50
    1           20
    0            0
    ========  =====

    Scoring examples
    ----------------
    - 6 independent story clusters: 100
    - 3 clusters: 70
    - 1 cluster (all sources same story): 20
    - No sources: 0

    Parameters
    ----------
    db : AsyncSession
        SQLAlchemy async session.
    card_id : str
        The card to evaluate.

    Returns
    -------
    tuple[int, int]
        (corroboration_score, cluster_count) -- the sub-score and the raw
        cluster count (stored in the breakdown for transparency).
    """
    cluster_count = await story_clustering_service.get_cluster_count(db, card_id)

    if cluster_count >= 5:
        score = 100
    elif cluster_count == 4:
        score = 85
    elif cluster_count == 3:
        score = 70
    elif cluster_count == 2:
        score = 50
    elif cluster_count == 1:
        score = 20
    else:
        score = 0

    return score, cluster_count


def _calculate_recency(sources: list[dict]) -> int:
    """
    Calculate the Recency sub-score (0-100).

    Measures the average freshness of a card's sources.  In horizon scanning,
    newer sources are more valuable because they are more likely to reflect
    the current state of an emerging trend.

    Algorithm
    ---------
    1. For each source, determine its age in days from ``published_at``
       (preferred) or ``created_at`` (fallback).
    2. Compute the arithmetic mean of all source ages.
    3. Map the average age through a step-function curve.

    Score curve
    -----------
    =================  =====
    Avg age (days)     Score
    =================  =====
    0 - 30              100
    31 - 90              70
    91 - 180             40
    > 180                20
    =================  =====

    Scoring examples
    ----------------
    - All sources published this week (avg 4 days): 100
    - Mix of recent and older (avg 60 days): 70
    - All sources > 6 months old (avg 200 days): 20
    - No sources with dates: 20 (conservative default)

    Parameters
    ----------
    sources : list[dict]
        Source rows from the ``sources`` table.

    Returns
    -------
    int
        Recency sub-score in [0, 100].
    """
    if not sources:
        return 0

    now = datetime.now(timezone.utc)
    ages_days: list[float] = []

    for source in sources:
        # Prefer published_at, fall back to created_at
        date_str = source.get("published_at") or source.get("created_at")
        if not date_str:
            continue

        try:
            # Parse ISO 8601 strings or datetime objects
            if isinstance(date_str, str):
                # Handle both "Z" suffix and "+00:00" offset formats
                date_str = date_str.replace("Z", "+00:00")
                dt = datetime.fromisoformat(date_str)
            elif isinstance(date_str, datetime):
                dt = date_str
            else:
                continue

            # Ensure timezone-aware
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            age = (now - dt).total_seconds() / 86400.0  # seconds -> days
            ages_days.append(max(0.0, age))  # Guard against future dates
        except (ValueError, TypeError):
            logger.debug("Could not parse date for source %s", source.get("id"))
            continue

    if not ages_days:
        # No parseable dates -- conservative default
        return 20

    avg_age = sum(ages_days) / len(ages_days)

    if avg_age <= 30:
        return 100
    if avg_age <= 90:
        return 70
    return 40 if avg_age <= 180 else 20


def _calculate_municipal_specificity(sources: list[dict]) -> int:
    """
    Calculate the Municipal Specificity sub-score (0-100).

    Measures how directly relevant the card's sources are to municipal
    government operations.  Cards backed by government publications and
    high-relevance sources score higher.

    Algorithm
    ---------
    1. Average the ``relevance_to_card`` field across all sources.
       This field is a 0.0-1.0 float assigned during the AI triage step.
    2. Multiply by 100 to get a base score.
    3. Apply a +10 bonus if *any* source originates from a ``.gov``
       domain (capped at 100).

    Scoring examples
    ----------------
    - avg relevance 0.80, one .gov source: min(80 + 10, 100) = 90
    - avg relevance 0.95, one .gov source: min(95 + 10, 100) = 100
    - avg relevance 0.60, no .gov sources: 60
    - No sources: 0

    Parameters
    ----------
    sources : list[dict]
        Source rows from the ``sources`` table.

    Returns
    -------
    int
        Municipal specificity sub-score in [0, 100].
    """
    if not sources:
        return 0

    # Gather relevance_to_card values
    relevance_values: list[float] = []
    has_gov_domain = False

    for source in sources:
        # Accumulate relevance scores
        relevance = source.get("relevance_to_card")
        if relevance is not None:
            try:
                relevance_values.append(float(relevance))
            except (ValueError, TypeError):
                pass

        if url := source.get("url", ""):
            try:
                hostname = urlparse(url).hostname or ""
                if hostname.lower().endswith(".gov"):
                    has_gov_domain = True
            except Exception:
                pass

    if not relevance_values:
        # No relevance data available; use a conservative baseline
        base_score = 0
    else:
        avg_relevance = sum(relevance_values) / len(relevance_values)
        base_score = round(avg_relevance * 100)

    # .gov domain bonus
    if has_gov_domain:
        base_score += 10

    return max(0, min(100, base_score))


# ============================================================================
# Internal Helpers
# ============================================================================


async def _fetch_card_sources(db: AsyncSession, card_id: str) -> list[dict]:
    """
    Fetch all source rows for a card.

    Retrieves the columns needed by all five SQI components in a single
    database round-trip.

    Parameters
    ----------
    db : AsyncSession
        SQLAlchemy async session.
    card_id : str
        The card whose sources to fetch.

    Returns
    -------
    list[dict]
        Source rows with id, url, api_source, published_at, created_at,
        and relevance_to_card fields.
    """
    try:
        result = await db.execute(
            select(
                Source.id,
                Source.url,
                Source.api_source,
                Source.published_at,
                Source.created_at,
                Source.relevance_to_card,
            ).where(Source.card_id == card_id)
        )
        rows = result.all()
        return [
            {
                "id": str(row.id),
                "url": row.url,
                "api_source": row.api_source,
                "published_at": row.published_at,
                "created_at": row.created_at,
                "relevance_to_card": (
                    float(row.relevance_to_card)
                    if row.relevance_to_card is not None
                    else None
                ),
            }
            for row in rows
        ]
    except Exception as e:
        logger.error("Failed to fetch sources for card %s: %s", card_id, e)
        return []


def _compute_composite_sqi(
    authority: int,
    diversity: int,
    corroboration: int,
    recency: int,
    municipal_specificity: int,
    weights: dict[str, float] | None = None,
) -> int:
    """
    Combine the five sub-scores into a single SQI composite.

    Parameters
    ----------
    authority : int
        Source Authority sub-score (0-100).
    diversity : int
        Source Diversity sub-score (0-100).
    corroboration : int
        Corroboration sub-score (0-100).
    recency : int
        Recency sub-score (0-100).
    municipal_specificity : int
        Municipal Specificity sub-score (0-100).
    weights : dict[str, float] | None
        Optional custom weights from admin settings.  When ``None``,
        the module-level ``WEIGHT_*`` constants are used.

    Returns
    -------
    int
        Composite SQI in [0, 100].
    """
    if weights:
        w_auth = weights.get("source_authority", WEIGHT_SOURCE_AUTHORITY)
        w_div = weights.get("source_diversity", WEIGHT_SOURCE_DIVERSITY)
        w_corr = weights.get("corroboration", WEIGHT_CORROBORATION)
        w_rec = weights.get("recency", WEIGHT_RECENCY)
        w_muni = weights.get("municipal_specificity", WEIGHT_MUNICIPAL_SPECIFICITY)
    else:
        w_auth = WEIGHT_SOURCE_AUTHORITY
        w_div = WEIGHT_SOURCE_DIVERSITY
        w_corr = WEIGHT_CORROBORATION
        w_rec = WEIGHT_RECENCY
        w_muni = WEIGHT_MUNICIPAL_SPECIFICITY

    raw = (
        authority * w_auth
        + diversity * w_div
        + corroboration * w_corr
        + recency * w_rec
        + municipal_specificity * w_muni
    )
    return max(0, min(100, round(raw)))


# ============================================================================
# Public API
# ============================================================================


async def _load_custom_weights(db: AsyncSession) -> dict[str, float] | None:
    """Load admin-configured SQI weights from system_settings.

    Returns the persisted weight dict if valid, otherwise ``None``
    (which causes the caller to fall back to default constants).
    """
    try:
        from app.helpers.settings_reader import get_setting

        persisted = await get_setting(db, "signal_quality_weights", None)
        if isinstance(persisted, dict) and len(persisted) == 5:
            # Basic sanity: all values numeric and roughly sum to 1.0
            total = sum(float(v) for v in persisted.values())
            if abs(total - 1.0) <= 0.02:
                return {k: float(v) for k, v in persisted.items()}
    except Exception as exc:
        logger.debug("Could not load custom SQI weights: %s", exc)
    return None


async def calculate_sqi(
    db: AsyncSession,
    card_id: str,
    weights: dict[str, float] | None = None,
) -> dict:
    """
    Calculate the Source Quality Index for a card and persist the result.

    Fetches all sources linked to the card, computes each of the five SQI
    sub-scores, derives the weighted composite, and writes both
    ``quality_score`` and ``quality_breakdown`` to the ``cards`` table.

    This function is idempotent: calling it multiple times for the same
    card simply overwrites the previous score with a fresh calculation.

    Parameters
    ----------
    db : AsyncSession
        SQLAlchemy async session (service_role for write access).
    card_id : str
        UUID of the card to score.
    weights : dict[str, float] | None
        Optional pre-loaded custom weights.  When ``None``, weights are
        loaded from ``system_settings`` (with 60 s cache).  Pass
        explicitly in batch paths to avoid repeated DB lookups.

    Returns
    -------
    dict
        The full quality_breakdown dict (see module docstring for shape),
        including the composite ``quality_score`` key for convenience::

            {
                "source_authority": 85,
                "source_diversity": 70,
                "corroboration": 50,
                "recency": 100,
                "municipal_specificity": 75,
                "calculated_at": "2025-02-10T12:00:00+00:00",
                "source_count": 5,
                "cluster_count": 3,
            }
    """
    logger.info("Calculating SQI for card %s", card_id)

    # 0. Load custom weights if not provided
    if weights is None:
        weights = await _load_custom_weights(db)

    # 1. Fetch sources
    sources = await _fetch_card_sources(db, card_id)
    source_count = len(sources)

    if source_count == 0:
        logger.info("Card %s has no sources; SQI will be 0", card_id)

    # 2. Calculate each component
    authority = await _calculate_source_authority(db, sources)
    diversity = _calculate_source_diversity(sources)
    corroboration, cluster_count = await _calculate_corroboration(db, card_id)
    recency = _calculate_recency(sources)
    municipal_specificity = _calculate_municipal_specificity(sources)

    # 3. Compute composite (uses custom admin weights when available)
    composite = _compute_composite_sqi(
        authority=authority,
        diversity=diversity,
        corroboration=corroboration,
        recency=recency,
        municipal_specificity=municipal_specificity,
        weights=weights,
    )

    # 4. Build breakdown
    calculated_at = datetime.now(timezone.utc).isoformat()
    breakdown = {
        "source_authority": authority,
        "source_diversity": diversity,
        "corroboration": corroboration,
        "recency": recency,
        "municipal_specificity": municipal_specificity,
        "calculated_at": calculated_at,
        "source_count": source_count,
        "cluster_count": cluster_count,
    }

    # 5. Persist to cards table
    try:
        await db.execute(
            sa_update(Card)
            .where(Card.id == card_id)
            .values(
                signal_quality_score=composite,
                quality_breakdown=breakdown,
            )
        )
        await db.flush()

        logger.info(
            "SQI for card %s: %d (authority=%d, diversity=%d, corroboration=%d, "
            "recency=%d, municipal_specificity=%d, sources=%d, clusters=%d)",
            card_id,
            composite,
            authority,
            diversity,
            corroboration,
            recency,
            municipal_specificity,
            source_count,
            cluster_count,
        )
    except Exception as e:
        logger.error("Failed to persist SQI for card %s: %s", card_id, e)

    return breakdown


async def recalculate_all_cards(db: AsyncSession) -> dict:
    """
    Batch recalculate the SQI for every card in the system.

    Intended to be run as a periodic background job (e.g., nightly) by
    the worker to keep quality scores current as new sources are added,
    domain reputations change, or clustering is updated.

    The function iterates through all cards and calls ``calculate_sqi()``
    for each.  Errors on individual cards are logged but do not halt the
    batch.

    Parameters
    ----------
    db : AsyncSession
        SQLAlchemy async session (service_role for write access).

    Returns
    -------
    dict
        Summary with keys:

        - ``cards_processed`` (int): Total cards attempted.
        - ``cards_succeeded`` (int): Cards successfully scored.
        - ``cards_failed`` (int): Cards that encountered errors.
        - ``errors`` (list[str]): Error messages for failed cards.
    """
    summary: dict = {
        "cards_processed": 0,
        "cards_succeeded": 0,
        "cards_failed": 0,
        "errors": [],
    }

    # Fetch all card IDs
    try:
        result = await db.execute(select(Card.id))
        card_rows = result.all()
    except Exception as e:
        msg = f"Failed to fetch card list for batch recalculation: {e}"
        logger.error(msg)
        summary["errors"].append(msg)
        return summary

    if not card_rows:
        logger.info("No cards found; batch recalculation has nothing to do")
        return summary

    logger.info("Starting batch SQI recalculation for %d cards", len(card_rows))

    # Load custom weights once for the entire batch (avoids repeated
    # DB lookups via the 60s-cached settings_reader).
    custom_weights = await _load_custom_weights(db)

    # Clear the domain reputation batch cache before the run so we get
    # fresh data, then let it build up during the run for efficiency.
    domain_reputation_service.clear_batch_cache()

    for row in card_rows:
        card_id = str(row[0])
        summary["cards_processed"] += 1

        try:
            await calculate_sqi(db, card_id, weights=custom_weights)
            summary["cards_succeeded"] += 1
        except Exception as e:
            msg = f"Failed to calculate SQI for card {card_id}: {e}"
            logger.error(msg)
            summary["errors"].append(msg)
            summary["cards_failed"] += 1

    logger.info(
        "Batch SQI recalculation complete: %d processed, %d succeeded, %d failed",
        summary["cards_processed"],
        summary["cards_succeeded"],
        summary["cards_failed"],
    )

    return summary


async def get_breakdown(db: AsyncSession, card_id: str) -> Optional[dict]:
    """
    Retrieve the stored SQI breakdown for a card without recalculating.

    This is a lightweight read-only operation that simply fetches the
    ``quality_breakdown`` JSONB column from the ``cards`` table.  Use
    this when you need the breakdown for display or filtering but do
    not want to trigger a (potentially expensive) recalculation.

    Parameters
    ----------
    db : AsyncSession
        SQLAlchemy async session.
    card_id : str
        UUID of the card to look up.

    Returns
    -------
    Optional[dict]
        The quality_breakdown dict if the card exists and has been scored,
        or None if the card does not exist or has no breakdown stored.
    """
    try:
        result = await db.execute(
            select(Card.signal_quality_score, Card.quality_breakdown).where(
                Card.id == card_id
            )
        )
        row = result.first()
    except Exception as e:
        logger.error("Failed to fetch quality breakdown for card %s: %s", card_id, e)
        return None

    if not row:
        return None

    breakdown = row.quality_breakdown
    return None if not breakdown or breakdown == {} else breakdown
