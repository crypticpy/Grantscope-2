"""
Domain reputation service for Foresight.

Provides domain-level credibility scoring used by the discovery pipeline's
triage step and the Source Quality Index (SQI) calculation. Each domain in
the `domain_reputation` table carries a curated tier, crowd-sourced quality
ratings, and pipeline triage statistics, which are combined into a single
composite score via a weighted formula:

    composite_score = (curated_tier_score * 0.50)
                    + (user_quality_avg_normalized * 0.30)
                    + (triage_pass_rate * 100 * 0.20)
                    + texas_relevance_bonus

Where:
    curated_tier_score:  Tier 1 = 85, Tier 2 = 60, Tier 3 = 35, NULL = 20
    user_quality_avg_normalized:  (user_quality_avg / 5.0) * 100
    triage_pass_rate * 100:  fraction converted to 0-100 scale

Key capabilities:
- Look up domain reputation for a given URL (extract domain, match against
  patterns including wildcards)
- Compute composite scores from curated tier + user ratings + pipeline perf
- Handle wildcard matching with priority: exact > parent > subdomain > TLD
- Recalculate aggregated user ratings from source_ratings table
- Recalculate triage pass rates from discovered_sources table
- Apply Texas relevance bonus
- In-memory cache for batch processing during discovery runs

Usage:
    from app.domain_reputation_service import (
        get_reputation, get_reputation_batch,
        get_authority_score, get_confidence_adjustment,
        recalculate_all, record_triage_result,
    )

    reputation = get_reputation(supabase_client, "https://gartner.com/article")
    authority = get_authority_score(reputation)
    adjustment = get_confidence_adjustment(reputation)
"""

import logging
from typing import Optional
from urllib.parse import urlparse

from supabase import Client

logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Curated tier -> base score mapping.
# Tier 1 (Authoritative): 85  -- Gartner, McKinsey, federal agencies
# Tier 2 (Credible):      60  -- ICMA, Bloomberg Cities, state agencies
# Tier 3 (General):       35  -- news outlets, trade publications
# NULL (Untiered):         20  -- not yet reviewed or uncategorized
TIER_SCORES: dict[int | None, int] = {
    1: 85,
    2: 60,
    3: 35,
    None: 20,
}

# Composite score weights (must sum to 1.0 before texas bonus)
WEIGHT_CURATED_TIER = 0.50
WEIGHT_USER_RATINGS = 0.30
WEIGHT_PIPELINE_PERF = 0.20

# Relevance encoding for user relevance_rating aggregation.
# Maps the text enum from source_ratings.relevance_rating to a numeric scale.
RELEVANCE_ENCODING: dict[str, int] = {
    "high": 4,
    "medium": 3,
    "low": 2,
    "not_relevant": 1,
}

# Confidence adjustment thresholds (applied during triage).
# Based on the domain's composite_score, the triage confidence is
# boosted or penalised so that sources from well-known domains
# get a slight advantage and unknown domains get scrutiny.
#
# Tier 1 equivalent (composite >= 80): +0.10
# Tier 2 equivalent (composite >= 50): +0.05
# Tier 3 equivalent (composite >= 30): +0.00 (neutral)
# Untiered         (composite <  30): -0.05
# Low user ratings (composite <  15): -0.10
CONFIDENCE_THRESHOLDS: list[tuple[float, float]] = [
    (80.0, 0.10),  # Tier 1 equivalent
    (50.0, 0.05),  # Tier 2 equivalent
    (30.0, 0.00),  # Tier 3 equivalent (neutral)
    (15.0, -0.05),  # Untiered
]
CONFIDENCE_FLOOR = -0.10  # Below the lowest threshold


# ============================================================================
# Internal Helpers
# ============================================================================


def _extract_domain(url: str) -> str:
    """
    Extract the bare domain (no scheme, no path, no port) from a URL.

    Args:
        url: Full URL string, e.g. "https://research.gartner.com/article/123"

    Returns:
        Lowercase domain string, e.g. "research.gartner.com".
        Returns empty string if parsing fails.
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        return hostname.lower().strip()
    except Exception:
        logger.warning("Failed to parse URL for domain extraction: %s", url)
        return ""


def _get_parent_domain(domain: str) -> Optional[str]:
    """
    Return the parent domain by stripping the leftmost subdomain label.

    Args:
        domain: e.g. "research.gartner.com"

    Returns:
        Parent domain e.g. "gartner.com", or None if the domain has
        two or fewer labels (i.e., it is already a root domain like
        "gartner.com" or "localhost").
    """
    parts = domain.split(".")
    # Need at least 3 parts to have a subdomain (sub.domain.tld)
    if len(parts) <= 2:
        return None
    return ".".join(parts[1:])


def _get_tld_wildcard(domain: str) -> Optional[str]:
    """
    Build a TLD wildcard pattern from a domain.

    Args:
        domain: e.g. "data.texas.gov"

    Returns:
        TLD wildcard e.g. "*.gov", or None if the domain has no TLD.
    """
    parts = domain.split(".")
    if len(parts) < 2:
        return None
    tld = parts[-1]
    return f"*.{tld}"


def _get_subdomain_wildcard(domain: str) -> Optional[str]:
    """
    Build a subdomain wildcard pattern from a domain.

    The subdomain wildcard matches any subdomain under the parent domain.
    For example, "research.gartner.com" produces "*.gartner.com".

    Args:
        domain: e.g. "research.gartner.com"

    Returns:
        Subdomain wildcard e.g. "*.gartner.com", or None if the domain
        has two or fewer labels.
    """
    parent = _get_parent_domain(domain)
    if parent is None:
        return None
    return f"*.{parent}"


def _compute_composite_score(
    curated_tier: Optional[int],
    user_quality_avg: float,
    triage_pass_rate: float,
    texas_relevance_bonus: int,
) -> float:
    """
    Compute the weighted composite reputation score.

    Formula:
        composite = (tier_score * 0.50)
                  + ((user_quality_avg / 5.0) * 100 * 0.30)
                  + (triage_pass_rate * 100 * 0.20)
                  + texas_relevance_bonus

    Args:
        curated_tier: 1, 2, 3, or None.
        user_quality_avg: Average user quality rating on a 1-5 scale.
        triage_pass_rate: Fraction of sources that passed triage (0.0 - 1.0).
        texas_relevance_bonus: Integer bonus points (typically 0 or 10).

    Returns:
        Composite score as a float.  Typically 0-100 range but can exceed
        100 with a Texas bonus applied to a high-scoring domain.
    """
    # 50% curated tier
    tier_score = TIER_SCORES.get(curated_tier, TIER_SCORES[None])
    tier_component = tier_score * WEIGHT_CURATED_TIER

    # 30% user ratings (normalize 1-5 scale to 0-100)
    user_score = (user_quality_avg / 5.0) * 100.0 if user_quality_avg > 0 else 0.0
    user_component = user_score * WEIGHT_USER_RATINGS

    # 20% pipeline performance (fraction -> 0-100)
    pipeline_score = triage_pass_rate * 100.0
    pipeline_component = pipeline_score * WEIGHT_PIPELINE_PERF

    return tier_component + user_component + pipeline_component + texas_relevance_bonus


# ============================================================================
# In-Memory Cache for Batch Processing
# ============================================================================


class _ReputationCache:
    """
    Simple in-memory cache for domain reputation lookups during batch
    processing.  Avoids repeated database round-trips when processing
    hundreds of URLs in a single discovery run.

    The cache is instance-scoped: create a new instance for each
    discovery run to avoid stale data across runs.
    """

    def __init__(self) -> None:
        # domain_pattern -> reputation dict (or None for cache-miss sentinel)
        self._pattern_cache: dict[str, Optional[dict]] = {}
        # raw domain -> resolved reputation dict (final match result)
        self._domain_cache: dict[str, Optional[dict]] = {}
        # All reputation rows keyed by domain_pattern, loaded lazily
        self._all_reputations: Optional[list[dict]] = None

    def get_domain(self, domain: str) -> tuple[bool, Optional[dict]]:
        """Check if a domain lookup result is cached.

        Returns:
            (hit, value) -- hit is True if the domain was previously
            looked up (even if the result was None = no reputation found).
        """
        if domain in self._domain_cache:
            return True, self._domain_cache[domain]
        return False, None

    def set_domain(self, domain: str, reputation: Optional[dict]) -> None:
        """Cache a domain lookup result."""
        self._domain_cache[domain] = reputation

    def get_all_reputations(self) -> Optional[list[dict]]:
        """Return the bulk-loaded reputation list, or None if not yet loaded."""
        return self._all_reputations

    def set_all_reputations(self, reputations: list[dict]) -> None:
        """Store the bulk-loaded reputation list."""
        self._all_reputations = reputations
        # Also index by pattern for fast wildcard matching
        for rep in reputations:
            self._pattern_cache[rep["domain_pattern"]] = rep

    def get_by_pattern(self, pattern: str) -> Optional[dict]:
        """Look up a reputation row by its domain_pattern."""
        return self._pattern_cache.get(pattern)

    def clear(self) -> None:
        """Reset all caches."""
        self._pattern_cache.clear()
        self._domain_cache.clear()
        self._all_reputations = None


# Module-level cache instance, reset between batch runs
_batch_cache = _ReputationCache()


# ============================================================================
# Public API
# ============================================================================


def get_reputation(supabase_client: Client, url: str) -> Optional[dict]:
    """
    Look up domain reputation for a given URL.

    Extracts the domain from the URL and searches the domain_reputation
    table using a priority-ordered matching strategy:

        1. Exact domain match  (e.g., "gartner.com")
        2. Parent domain match (e.g., "research.gartner.com" -> "gartner.com")
        3. Subdomain wildcard  (e.g., "*.harvard.edu")
        4. TLD wildcard        (e.g., "*.gov")

    The first match found wins.  Inactive rows (is_active=False) are excluded.

    Args:
        supabase_client: Authenticated Supabase client instance.
        url: Full URL of the source to look up.

    Returns:
        A dict with all domain_reputation columns if a match is found,
        or None if no matching pattern exists in the database.
    """
    domain = _extract_domain(url)
    if not domain:
        return None

    # Check batch cache first
    hit, cached = _batch_cache.get_domain(domain)
    if hit:
        return cached

    # Build the list of candidate patterns to try, in priority order.
    # Priority: exact domain > parent domain > subdomain wildcard > TLD wildcard
    candidates: list[str] = [domain]

    parent = _get_parent_domain(domain)
    if parent:
        candidates.append(parent)

    subdomain_wc = _get_subdomain_wildcard(domain)
    if subdomain_wc:
        candidates.append(subdomain_wc)

    tld_wc = _get_tld_wildcard(domain)
    if tld_wc:
        candidates.append(tld_wc)

    # Query all candidates in one round-trip, then pick the highest-priority match
    try:
        response = (
            supabase_client.table("domain_reputation")
            .select("*")
            .in_("domain_pattern", candidates)
            .eq("is_active", True)
            .execute()
        )
        rows = response.data or []
    except Exception as e:
        logger.error("Error querying domain_reputation for %s: %s", domain, e)
        return None

    if not rows:
        _batch_cache.set_domain(domain, None)
        return None

    # Index rows by pattern for O(1) priority lookup
    rows_by_pattern: dict[str, dict] = {row["domain_pattern"]: row for row in rows}

    # Return the first match in priority order
    for candidate in candidates:
        if candidate in rows_by_pattern:
            result = rows_by_pattern[candidate]
            _batch_cache.set_domain(domain, result)
            return result

    # Should not reach here if the query returned rows for our candidates,
    # but be defensive.
    _batch_cache.set_domain(domain, None)
    return None


def get_reputation_batch(supabase_client: Client, urls: list[str]) -> dict[str, dict]:
    """
    Look up domain reputations for a batch of URLs with caching.

    Optimised for discovery runs where hundreds of URLs are processed.
    On the first call, all active domain_reputation rows are bulk-loaded
    into an in-memory cache.  Subsequent lookups are resolved entirely
    from memory using the same matching priority as get_reputation().

    The cache persists across calls within the same process.  Call
    ``clear_batch_cache()`` between discovery runs to avoid stale data.

    Args:
        supabase_client: Authenticated Supabase client instance.
        urls: List of full source URLs.

    Returns:
        Dict mapping each URL to its matched reputation dict.
        URLs with no match are omitted from the result.
    """
    # Bulk-load all reputations into cache if not yet loaded
    if _batch_cache.get_all_reputations() is None:
        try:
            response = (
                supabase_client.table("domain_reputation")
                .select("*")
                .eq("is_active", True)
                .execute()
            )
            all_rows = response.data or []
            _batch_cache.set_all_reputations(all_rows)
            logger.info(
                "Loaded %d domain reputation rows into batch cache", len(all_rows)
            )
        except Exception as e:
            logger.error("Failed to bulk-load domain reputations: %s", e)
            _batch_cache.set_all_reputations([])

    results: dict[str, dict] = {}

    for url in urls:
        domain = _extract_domain(url)
        if not domain:
            continue

        # Check domain-level cache
        hit, cached = _batch_cache.get_domain(domain)
        if hit:
            if cached is not None:
                results[url] = cached
            continue

        # Resolve against the in-memory pattern index using priority order
        reputation = _resolve_from_cache(domain)
        _batch_cache.set_domain(domain, reputation)
        if reputation is not None:
            results[url] = reputation

    return results


def _resolve_from_cache(domain: str) -> Optional[dict]:
    """
    Resolve a domain against the cached reputation patterns.

    Uses the same priority order as get_reputation():
        1. Exact domain match
        2. Parent domain match
        3. Subdomain wildcard
        4. TLD wildcard

    Args:
        domain: Bare domain string (e.g., "research.gartner.com").

    Returns:
        Matched reputation dict or None.
    """
    # Priority 1: exact match
    exact = _batch_cache.get_by_pattern(domain)
    if exact is not None:
        return exact

    # Priority 2: parent domain match
    parent = _get_parent_domain(domain)
    if parent:
        parent_match = _batch_cache.get_by_pattern(parent)
        if parent_match is not None:
            return parent_match

    # Priority 3: subdomain wildcard
    subdomain_wc = _get_subdomain_wildcard(domain)
    if subdomain_wc:
        sub_match = _batch_cache.get_by_pattern(subdomain_wc)
        if sub_match is not None:
            return sub_match

    # Priority 4: TLD wildcard
    tld_wc = _get_tld_wildcard(domain)
    if tld_wc:
        tld_match = _batch_cache.get_by_pattern(tld_wc)
        if tld_match is not None:
            return tld_match

    return None


def clear_batch_cache() -> None:
    """
    Clear the in-memory batch cache.

    Should be called between discovery runs to ensure fresh data.
    """
    _batch_cache.clear()
    logger.debug("Domain reputation batch cache cleared")


def get_authority_score(reputation: Optional[dict]) -> int:
    """
    Convert a domain reputation record to a 0-100 authority score for SQI.

    The authority score is derived from the composite_score, clamped to
    the [0, 100] range.  If no reputation exists, returns a conservative
    default of 20 (equivalent to an untiered domain).

    Args:
        reputation: A domain_reputation row dict, or None if the domain
                    has no entry.

    Returns:
        Integer authority score in the range [0, 100].
    """
    if reputation is None:
        # No reputation data: return the untiered default
        return TIER_SCORES[None]

    composite = float(reputation.get("composite_score", 0))
    # Clamp to [0, 100]
    return max(0, min(100, round(composite)))


def get_confidence_adjustment(reputation: Optional[dict]) -> float:
    """
    Return a confidence boost or penalty for the triage step based on
    the domain's composite reputation score.

    The adjustment is added to the AI triage confidence value so that
    sources from well-known authoritative domains (Tier 1) are slightly
    more likely to pass triage, while unknown or poorly-rated domains
    receive a small penalty.

    Thresholds:
        composite >= 80  ->  +0.10  (Tier 1 equivalent)
        composite >= 50  ->  +0.05  (Tier 2 equivalent)
        composite >= 30  ->  +0.00  (Tier 3 equivalent, neutral)
        composite >= 15  ->  -0.05  (Untiered)
        composite <  15  ->  -0.10  (Low user ratings / unknown)

    Args:
        reputation: A domain_reputation row dict, or None.

    Returns:
        Float adjustment value, typically in [-0.10, +0.10].
    """
    if reputation is None:
        # Unknown domain: apply the small penalty for untiered
        return -0.05

    composite = float(reputation.get("composite_score", 0))

    # Walk thresholds from highest to lowest; first match wins
    for threshold, adjustment in CONFIDENCE_THRESHOLDS:
        if composite >= threshold:
            return adjustment

    # Below the lowest explicit threshold
    return CONFIDENCE_FLOOR


def recalculate_all(supabase_client: Client) -> dict:
    """
    Recalculate composite scores for all active domain_reputation rows.

    This function performs a full refresh by:
    1. Aggregating user quality/relevance ratings from source_ratings,
       grouped by domain (via join on sources.url).
    2. Aggregating triage pass rates from discovered_sources, grouped
       by domain.
    3. Recomputing the composite_score for every row using the standard
       weighted formula.

    Intended to be run as a nightly background job by the worker.

    Args:
        supabase_client: Supabase client with service_role credentials
                         (required for write access).

    Returns:
        Summary dict with keys:
            - "domains_updated": int, number of rows updated
            - "domains_skipped": int, rows that had no changes
            - "errors": list[str], any errors encountered
    """
    summary = {"domains_updated": 0, "domains_skipped": 0, "errors": []}

    # ----------------------------------------------------------------
    # Step 1: Fetch all active domain_reputation rows
    # ----------------------------------------------------------------
    try:
        rep_response = (
            supabase_client.table("domain_reputation")
            .select("*")
            .eq("is_active", True)
            .execute()
        )
        reputation_rows = rep_response.data or []
    except Exception as e:
        msg = f"Failed to fetch domain_reputation rows: {e}"
        logger.error(msg)
        summary["errors"].append(msg)
        return summary

    if not reputation_rows:
        logger.info("No active domain_reputation rows found; nothing to recalculate")
        return summary

    # ----------------------------------------------------------------
    # Step 2: Aggregate user ratings from source_ratings
    #
    # source_ratings links to sources via source_id.  We extract the
    # domain from sources.url and group ratings by domain to produce
    # average quality and relevance values.
    # ----------------------------------------------------------------
    user_agg_by_domain: dict[str, dict] = {}
    try:
        # Fetch all source_ratings joined with source URL
        ratings_response = (
            supabase_client.table("source_ratings")
            .select("quality_rating, relevance_rating, source_id, sources!inner(url)")
            .execute()
        )
        ratings_rows = ratings_response.data or []

        # Group by domain
        domain_ratings: dict[str, list[dict]] = {}
        for row in ratings_rows:
            source_url = ""
            # The join returns sources as a nested dict or list
            sources_data = row.get("sources")
            if isinstance(sources_data, dict):
                source_url = sources_data.get("url", "")
            elif isinstance(sources_data, list) and sources_data:
                source_url = sources_data[0].get("url", "")

            domain = _extract_domain(source_url)
            if domain:
                domain_ratings.setdefault(domain, []).append(row)

        # Compute averages per domain
        for domain, ratings in domain_ratings.items():
            quality_sum = sum(r["quality_rating"] for r in ratings)
            quality_avg = quality_sum / len(ratings)

            relevance_sum = sum(
                RELEVANCE_ENCODING.get(r["relevance_rating"], 2) for r in ratings
            )
            relevance_avg = relevance_sum / len(ratings)

            user_agg_by_domain[domain] = {
                "user_quality_avg": round(quality_avg, 2),
                "user_relevance_avg": round(relevance_avg, 2),
                "user_rating_count": len(ratings),
            }

        logger.info(
            "Aggregated user ratings for %d domains from %d ratings",
            len(user_agg_by_domain),
            len(ratings_rows),
        )
    except Exception as e:
        msg = f"Failed to aggregate user ratings: {e}"
        logger.warning(msg)
        summary["errors"].append(msg)
        # Continue with empty user ratings -- we can still recalculate
        # based on curated tier and pipeline stats

    # ----------------------------------------------------------------
    # Step 3: Aggregate triage pass rates from discovered_sources
    #
    # discovered_sources has a `domain` column and `triage_is_relevant`
    # boolean.  We count total and passed per domain.
    # ----------------------------------------------------------------
    triage_agg_by_domain: dict[str, dict] = {}
    try:
        # Fetch triage results -- only rows that have been triaged
        triage_response = (
            supabase_client.table("discovered_sources")
            .select("domain, triage_is_relevant")
            .not_.is_("triage_is_relevant", "null")
            .execute()
        )
        triage_rows = triage_response.data or []

        # Group by domain
        domain_triage: dict[str, dict[str, int]] = {}
        for row in triage_rows:
            domain = (row.get("domain") or "").lower().strip()
            if not domain:
                continue
            if domain not in domain_triage:
                domain_triage[domain] = {"total": 0, "passed": 0}
            domain_triage[domain]["total"] += 1
            if row.get("triage_is_relevant"):
                domain_triage[domain]["passed"] += 1

        for domain, counts in domain_triage.items():
            total = counts["total"]
            passed = counts["passed"]
            triage_agg_by_domain[domain] = {
                "triage_pass_rate": round(passed / total, 4) if total > 0 else 0.0,
                "triage_total_count": total,
                "triage_pass_count": passed,
            }

        logger.info(
            "Aggregated triage stats for %d domains from %d triage results",
            len(triage_agg_by_domain),
            len(triage_rows),
        )
    except Exception as e:
        msg = f"Failed to aggregate triage stats: {e}"
        logger.warning(msg)
        summary["errors"].append(msg)

    # ----------------------------------------------------------------
    # Step 4: Recompute composite_score for each domain_reputation row
    # ----------------------------------------------------------------
    for rep_row in reputation_rows:
        domain_pattern = rep_row["domain_pattern"]
        rep_id = rep_row["id"]

        # Look up the pattern in user and triage aggregations.
        # For wildcard patterns (e.g., "*.gov"), we need the exact pattern
        # as a domain, which won't match.  That's expected -- wildcards
        # get their score primarily from the curated tier.
        # For exact-domain patterns, the domain matches directly.
        user_data = user_agg_by_domain.get(domain_pattern, {})
        triage_data = triage_agg_by_domain.get(domain_pattern, {})

        # Build updated values, falling back to current DB values
        # if no new aggregation data is available
        new_user_quality_avg = user_data.get(
            "user_quality_avg", float(rep_row.get("user_quality_avg", 0))
        )
        new_user_relevance_avg = user_data.get(
            "user_relevance_avg", float(rep_row.get("user_relevance_avg", 0))
        )
        new_user_rating_count = user_data.get(
            "user_rating_count", rep_row.get("user_rating_count", 0)
        )

        new_triage_pass_rate = triage_data.get(
            "triage_pass_rate", float(rep_row.get("triage_pass_rate", 0))
        )
        new_triage_total_count = triage_data.get(
            "triage_total_count", rep_row.get("triage_total_count", 0)
        )
        new_triage_pass_count = triage_data.get(
            "triage_pass_count", rep_row.get("triage_pass_count", 0)
        )

        texas_bonus = rep_row.get("texas_relevance_bonus", 0) or 0
        curated_tier = rep_row.get("curated_tier")

        new_composite = _compute_composite_score(
            curated_tier=curated_tier,
            user_quality_avg=new_user_quality_avg,
            triage_pass_rate=new_triage_pass_rate,
            texas_relevance_bonus=texas_bonus,
        )

        # Prepare update payload
        update_data = {
            "user_quality_avg": new_user_quality_avg,
            "user_relevance_avg": new_user_relevance_avg,
            "user_rating_count": new_user_rating_count,
            "triage_pass_rate": new_triage_pass_rate,
            "triage_total_count": new_triage_total_count,
            "triage_pass_count": new_triage_pass_count,
            "composite_score": round(new_composite, 2),
        }

        try:
            supabase_client.table("domain_reputation").update(update_data).eq(
                "id", rep_id
            ).execute()
            summary["domains_updated"] += 1
        except Exception as e:
            msg = f"Failed to update domain_reputation id={rep_id} ({domain_pattern}): {e}"
            logger.error(msg)
            summary["errors"].append(msg)

    logger.info(
        "recalculate_all complete: %d updated, %d skipped, %d errors",
        summary["domains_updated"],
        summary["domains_skipped"],
        len(summary["errors"]),
    )

    # Clear the batch cache since data has changed
    clear_batch_cache()

    return summary


def record_triage_result(supabase_client: Client, domain: str, passed: bool) -> None:
    """
    Record a single triage outcome for a domain.

    Increments the triage_total_count (and triage_pass_count if passed)
    and recalculates the triage_pass_rate and composite_score inline.
    This provides real-time updates during discovery runs without waiting
    for the nightly recalculate_all() job.

    If the domain does not have an entry in domain_reputation, this
    function silently returns (the domain is untiered/unknown).

    Args:
        supabase_client: Supabase client with service_role credentials.
        domain: Bare domain string (e.g., "gartner.com").
        passed: True if the source from this domain passed triage.
    """
    domain = domain.lower().strip()
    if not domain:
        return

    # Find the matching reputation row.  Try exact match first, then
    # parent domain (same logic as get_reputation, but simplified since
    # we already have the domain, not a full URL).
    candidates = [domain]
    parent = _get_parent_domain(domain)
    if parent:
        candidates.append(parent)
    subdomain_wc = _get_subdomain_wildcard(domain)
    if subdomain_wc:
        candidates.append(subdomain_wc)
    tld_wc = _get_tld_wildcard(domain)
    if tld_wc:
        candidates.append(tld_wc)

    try:
        response = (
            supabase_client.table("domain_reputation")
            .select("*")
            .in_("domain_pattern", candidates)
            .eq("is_active", True)
            .execute()
        )
        rows = response.data or []
    except Exception as e:
        logger.error("Error looking up domain for triage recording (%s): %s", domain, e)
        return

    if not rows:
        # Domain is not in the reputation table; nothing to update
        return

    # Pick the highest-priority match
    rows_by_pattern = {row["domain_pattern"]: row for row in rows}
    matched_row = None
    for candidate in candidates:
        if candidate in rows_by_pattern:
            matched_row = rows_by_pattern[candidate]
            break

    if matched_row is None:
        return

    # Increment counters
    new_total = (matched_row.get("triage_total_count", 0) or 0) + 1
    new_passed = (matched_row.get("triage_pass_count", 0) or 0) + (1 if passed else 0)
    new_pass_rate = round(new_passed / new_total, 4) if new_total > 0 else 0.0

    # Recompute composite score with updated pipeline stats
    curated_tier = matched_row.get("curated_tier")
    user_quality_avg = float(matched_row.get("user_quality_avg", 0))
    texas_bonus = matched_row.get("texas_relevance_bonus", 0) or 0

    new_composite = _compute_composite_score(
        curated_tier=curated_tier,
        user_quality_avg=user_quality_avg,
        triage_pass_rate=new_pass_rate,
        texas_relevance_bonus=texas_bonus,
    )

    update_data = {
        "triage_total_count": new_total,
        "triage_pass_count": new_passed,
        "triage_pass_rate": new_pass_rate,
        "composite_score": round(new_composite, 2),
    }

    try:
        supabase_client.table("domain_reputation").update(update_data).eq(
            "id", matched_row["id"]
        ).execute()
        logger.debug(
            "Recorded triage result for %s (passed=%s): new rate=%.4f, composite=%.2f",
            domain,
            passed,
            new_pass_rate,
            new_composite,
        )
    except Exception as e:
        logger.error("Failed to record triage result for %s: %s", domain, e)

    # Invalidate batch cache entry for this domain since data changed
    _batch_cache.set_domain(domain, None)
