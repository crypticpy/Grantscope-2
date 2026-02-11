"""
Source Quality Index (SQI) calculation service for Foresight.

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
    breakdown = calculate_sqi(supabase_client, card_id="card-abc")

    # Read the stored breakdown without recalculating
    breakdown = get_breakdown(supabase_client, card_id="card-abc")

    # Batch recalculate every card in the system (nightly job)
    summary = recalculate_all_cards(supabase_client)
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from supabase import Client

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


def _calculate_source_authority(
    supabase_client: Client,
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
    supabase_client : Client
        Authenticated Supabase client.
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
    reputations = domain_reputation_service.get_reputation_batch(supabase_client, urls)

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
    if count == 1:
        return 20
    return 0


def _calculate_corroboration(
    supabase_client: Client,
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
    supabase_client : Client
        Authenticated Supabase client.
    card_id : str
        The card to evaluate.

    Returns
    -------
    tuple[int, int]
        (corroboration_score, cluster_count) -- the sub-score and the raw
        cluster count (stored in the breakdown for transparency).
    """
    cluster_count = story_clustering_service.get_cluster_count(supabase_client, card_id)

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
            # Supabase returns ISO 8601 strings; parse them.
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
    if avg_age <= 180:
        return 40
    return 20


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

        # Check for .gov domain
        url = source.get("url", "")
        if url:
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


def _fetch_card_sources(supabase_client: Client, card_id: str) -> list[dict]:
    """
    Fetch all source rows for a card.

    Retrieves the columns needed by all five SQI components in a single
    database round-trip.

    Parameters
    ----------
    supabase_client : Client
        Authenticated Supabase client.
    card_id : str
        The card whose sources to fetch.

    Returns
    -------
    list[dict]
        Source rows with id, url, api_source, published_at, created_at,
        and relevance_to_card fields.
    """
    try:
        resp = (
            supabase_client.table("sources")
            .select("id, url, api_source, published_at, created_at, relevance_to_card")
            .eq("card_id", card_id)
            .execute()
        )
        return resp.data or []
    except Exception as e:
        logger.error("Failed to fetch sources for card %s: %s", card_id, e)
        return []


def _compute_composite_sqi(
    authority: int,
    diversity: int,
    corroboration: int,
    recency: int,
    municipal_specificity: int,
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

    Returns
    -------
    int
        Composite SQI in [0, 100].
    """
    raw = (
        authority * WEIGHT_SOURCE_AUTHORITY
        + diversity * WEIGHT_SOURCE_DIVERSITY
        + corroboration * WEIGHT_CORROBORATION
        + recency * WEIGHT_RECENCY
        + municipal_specificity * WEIGHT_MUNICIPAL_SPECIFICITY
    )
    return max(0, min(100, round(raw)))


# ============================================================================
# Public API
# ============================================================================


def calculate_sqi(supabase_client: Client, card_id: str) -> dict:
    """
    Calculate the Source Quality Index for a card and persist the result.

    Fetches all sources linked to the card, computes each of the five SQI
    sub-scores, derives the weighted composite, and writes both
    ``quality_score`` and ``quality_breakdown`` to the ``cards`` table.

    This function is idempotent: calling it multiple times for the same
    card simply overwrites the previous score with a fresh calculation.

    Parameters
    ----------
    supabase_client : Client
        Authenticated Supabase client (service_role for write access).
    card_id : str
        UUID of the card to score.

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

    # 1. Fetch sources
    sources = _fetch_card_sources(supabase_client, card_id)
    source_count = len(sources)

    if source_count == 0:
        logger.info("Card %s has no sources; SQI will be 0", card_id)

    # 2. Calculate each component
    authority = _calculate_source_authority(supabase_client, sources)
    diversity = _calculate_source_diversity(sources)
    corroboration, cluster_count = _calculate_corroboration(supabase_client, card_id)
    recency = _calculate_recency(sources)
    municipal_specificity = _calculate_municipal_specificity(sources)

    # 3. Compute composite
    composite = _compute_composite_sqi(
        authority=authority,
        diversity=diversity,
        corroboration=corroboration,
        recency=recency,
        municipal_specificity=municipal_specificity,
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
        supabase_client.table("cards").update(
            {
                "quality_score": composite,
                "quality_breakdown": breakdown,
            }
        ).eq("id", card_id).execute()

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


def recalculate_all_cards(supabase_client: Client) -> dict:
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
    supabase_client : Client
        Authenticated Supabase client (service_role for write access).

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
        resp = supabase_client.table("cards").select("id").execute()
        card_rows = resp.data or []
    except Exception as e:
        msg = f"Failed to fetch card list for batch recalculation: {e}"
        logger.error(msg)
        summary["errors"].append(msg)
        return summary

    if not card_rows:
        logger.info("No cards found; batch recalculation has nothing to do")
        return summary

    logger.info("Starting batch SQI recalculation for %d cards", len(card_rows))

    # Clear the domain reputation batch cache before the run so we get
    # fresh data, then let it build up during the run for efficiency.
    domain_reputation_service.clear_batch_cache()

    for row in card_rows:
        card_id = row["id"]
        summary["cards_processed"] += 1

        try:
            calculate_sqi(supabase_client, card_id)
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


def get_breakdown(supabase_client: Client, card_id: str) -> Optional[dict]:
    """
    Retrieve the stored SQI breakdown for a card without recalculating.

    This is a lightweight read-only operation that simply fetches the
    ``quality_breakdown`` JSONB column from the ``cards`` table.  Use
    this when you need the breakdown for display or filtering but do
    not want to trigger a (potentially expensive) recalculation.

    Parameters
    ----------
    supabase_client : Client
        Authenticated Supabase client.
    card_id : str
        UUID of the card to look up.

    Returns
    -------
    Optional[dict]
        The quality_breakdown dict if the card exists and has been scored,
        or None if the card does not exist or has no breakdown stored.
    """
    try:
        resp = (
            supabase_client.table("cards")
            .select("quality_score, quality_breakdown")
            .eq("id", card_id)
            .execute()
        )
        rows = resp.data or []
    except Exception as e:
        logger.error("Failed to fetch quality breakdown for card %s: %s", card_id, e)
        return None

    if not rows:
        return None

    breakdown = rows[0].get("quality_breakdown")
    if not breakdown or breakdown == {}:
        return None

    return breakdown
