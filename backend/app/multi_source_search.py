"""Multi-source search -- unified interface to all source fetchers.

Provides a single async function that searches across Grants.gov, SAM.gov,
web (SearXNG/Serper/Tavily), news outlets, government publications, and
academic papers in parallel.

Each source fetcher is imported lazily inside its wrapper coroutine so that
a missing dependency for one source never prevents the others from working.
Every wrapper catches all exceptions and returns an empty list (with logging),
ensuring that one failing source never breaks the aggregate result.

Used by:
- Chat tools (search_all_sources)
- Card analysis service (gathering context for new cards)
- Enrichment service (finding sources for thin descriptions)
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any, List

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Normalised result dataclass
# ---------------------------------------------------------------------------


@dataclass
class MultiSourceResult:
    """Normalized search result from any source type.

    Attributes:
        title:       Human-readable title of the result.
        url:         Canonical URL (used for deduplication).
        snippet:     Short text excerpt / description (max ~300 chars).
        source_type: One of: grants_gov, sam_gov, web, news, government, academic.
        metadata:    Source-specific extra fields (agency, deadline, authors, etc.).
        rrf_score:   Reciprocal Rank Fusion score assigned during reranking.
                     Higher means the result appeared near the top of multiple
                     source lists.  Zero before reranking is applied.
    """

    title: str
    url: str
    snippet: str
    source_type: str  # grants_gov | sam_gov | web | news | government | academic
    metadata: dict[str, Any] = field(default_factory=dict)
    rrf_score: float = 0.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalize_url_for_dedup(url: str) -> str:
    """Lowercase, strip trailing slashes, and strip fragment for dedup."""
    return url.lower().rstrip("/").split("#")[0]


# ---------------------------------------------------------------------------
# Source weights for RRF reranking
# ---------------------------------------------------------------------------

# Grant-focused sources get higher weight since this is a grant discovery
# platform.  Weights are relative -- doubling a weight doubles that source's
# contribution to the fused score.
DEFAULT_SOURCE_WEIGHTS: dict[str, float] = {
    "grants_gov": 1.5,
    "sam_gov": 1.5,
    "web": 1.0,
    "news": 0.8,
    "government": 1.2,
    "academic": 0.6,
}


def _rrf_rerank(
    results_per_source: List[List[MultiSourceResult]],
    source_labels: List[str],
    *,
    rrf_k: int = 60,
    source_weights: dict[str, float] | None = None,
) -> List[MultiSourceResult]:
    """Apply Reciprocal Rank Fusion to merge and rerank multi-source results.

    Each source provides results in its own ranked order (position 0 is best).
    For every unique result (keyed by normalised URL) the RRF score is::

        score(d) = Σ  weight_s / (rrf_k + rank_s(d))
                   s ∈ sources containing d

    Results that appear in *multiple* sources accumulate contributions from
    all of them, producing a natural cross-source agreement boost.

    Edge cases handled
    ------------------
    * **Source returns 0 results** — no entries, no contribution.
    * **Single source enabled** — degenerates to the source's own ordering.
    * **Duplicate URLs across sources** — merged; the more-informative
      record (longer snippet) is kept and scores are accumulated.
    * **All sources empty** — returns ``[]``.

    Parameters
    ----------
    results_per_source:
        One list of ``MultiSourceResult`` per source, in source-rank order.
    source_labels:
        Parallel list naming each source (``"grants_gov"``, ``"web"``, …).
    rrf_k:
        The constant *k* in the RRF denominator.  Standard value is 60.
        Larger values dampen rank-position differences; smaller values
        amplify them.
    source_weights:
        Per-source multipliers.  Defaults to :data:`DEFAULT_SOURCE_WEIGHTS`.

    Returns
    -------
    list[MultiSourceResult]
        Deduplicated results sorted by descending RRF score, with
        ``rrf_score`` and ``metadata["source_types"]`` populated.
    """
    weights = source_weights or DEFAULT_SOURCE_WEIGHTS

    # Map: normalised URL -> (best MultiSourceResult, accumulated score, source_types)
    url_map: dict[str, tuple[MultiSourceResult, float, set[str]]] = {}

    for source_results, label in zip(results_per_source, source_labels):
        if not isinstance(source_results, list):
            continue

        source_weight = weights.get(label, 1.0)

        for rank_zero, result in enumerate(source_results):
            norm_url = _normalize_url_for_dedup(result.url)
            # RRF uses 1-indexed rank: position 0 → rank 1
            rrf_contribution = source_weight / (rrf_k + rank_zero + 1)

            if norm_url in url_map:
                existing_result, existing_score, source_types = url_map[norm_url]
                new_score = existing_score + rrf_contribution
                source_types.add(label)
                # Keep the record with the longer snippet (more informative)
                keeper = (
                    result
                    if len(result.snippet) > len(existing_result.snippet)
                    else existing_result
                )
                url_map[norm_url] = (keeper, new_score, source_types)
            else:
                url_map[norm_url] = (result, rrf_contribution, {label})

    if not url_map:
        return []

    # Sort by RRF score descending, break ties alphabetically by URL for
    # deterministic ordering.
    scored = sorted(
        url_map.values(),
        key=lambda t: (-t[1], t[0].url),
    )

    merged: List[MultiSourceResult] = []
    for result, score, source_types in scored:
        result.rrf_score = round(score, 6)
        result.metadata["source_types"] = sorted(source_types)
        merged.append(result)

    return merged


# ---------------------------------------------------------------------------
# Per-source wrapper coroutines
# ---------------------------------------------------------------------------


async def _search_grants_gov(query: str, max_results: int) -> List[MultiSourceResult]:
    """Search Grants.gov for federal grant opportunities matching *query*."""
    try:
        from app.source_fetchers.grants_gov_fetcher import (
            fetch_grants_gov_opportunities,
        )

        result = await fetch_grants_gov_opportunities(
            topics=[query],
            max_results=max_results,
            posted_only=True,
            filter_relevant=False,  # caller is doing a broad search
        )

        results: List[MultiSourceResult] = []
        for opp in result.opportunities[:max_results]:
            url = (
                opp.opportunity_url
                or f"https://www.grants.gov/search-results-detail/{opp.id}"
            )
            results.append(
                MultiSourceResult(
                    title=opp.title,
                    url=url,
                    snippet=(opp.description[:300] if opp.description else ""),
                    source_type="grants_gov",
                    metadata={
                        "opportunity_id": opp.id,
                        "agency": opp.agency,
                        "close_date": (
                            opp.close_date.isoformat() if opp.close_date else None
                        ),
                        "estimated_funding": opp.estimated_funding,
                        "award_ceiling": opp.award_ceiling,
                        "opportunity_number": opp.opportunity_number,
                        "cfda_numbers": opp.cfda_numbers,
                    },
                )
            )
        return results

    except Exception:
        logger.exception("Grants.gov search failed for query=%r", query)
        return []


async def _search_sam_gov(query: str, max_results: int) -> List[MultiSourceResult]:
    """Search SAM.gov for federal grant/contract opportunities matching *query*.

    Requires the SAM_GOV_API_KEY environment variable to be set.
    """
    if not os.getenv("SAM_GOV_API_KEY", "").strip():
        logger.debug("SAM_GOV_API_KEY not set -- skipping SAM.gov search")
        return []

    try:
        from app.source_fetchers.sam_gov_fetcher import fetch_sam_gov_opportunities

        result = await fetch_sam_gov_opportunities(
            topics=[query],
            max_results=max_results,
            include_grants=True,
            include_contracts=False,
            filter_relevant=False,
        )

        results: List[MultiSourceResult] = []
        for opp in result.opportunities[:max_results]:
            results.append(
                MultiSourceResult(
                    title=opp.title,
                    url=opp.opportunity_url,
                    snippet=(opp.description[:300] if opp.description else ""),
                    source_type="sam_gov",
                    metadata={
                        "notice_id": opp.notice_id,
                        "solicitation_number": opp.solicitation_number,
                        "department": opp.department,
                        "response_deadline": (
                            opp.response_deadline.isoformat()
                            if opp.response_deadline
                            else None
                        ),
                        "procurement_type": opp.procurement_type,
                        "naics_code": opp.naics_code,
                    },
                )
            )
        return results

    except Exception:
        logger.exception("SAM.gov search failed for query=%r", query)
        return []


async def _search_web(query: str, max_results: int) -> List[MultiSourceResult]:
    """Search the web via the configured search provider (SearXNG/Serper/Tavily)."""
    try:
        from app.search_provider import is_available, search_web

        if not is_available():
            logger.debug("No web search provider configured -- skipping web search")
            return []

        search_results = await search_web(query, num_results=max_results)

        return [
            MultiSourceResult(
                title=r.title,
                url=r.url,
                snippet=r.snippet[:300] if r.snippet else "",
                source_type="web",
                metadata={
                    "source_name": r.source_name,
                    "date": r.date,
                    "provider": r.provider,
                },
            )
            for r in search_results[:max_results]
        ]

    except Exception:
        logger.exception("Web search failed for query=%r", query)
        return []


async def _search_news(query: str, max_results: int) -> List[MultiSourceResult]:
    """Search news via the configured search provider (SearXNG/Serper/Tavily)."""
    try:
        from app.search_provider import is_available, search_news

        if not is_available():
            logger.debug("No search provider configured -- skipping news search")
            return []

        search_results = await search_news(query, num_results=max_results)

        return [
            MultiSourceResult(
                title=r.title,
                url=r.url,
                snippet=r.snippet[:300] if r.snippet else "",
                source_type="news",
                metadata={
                    "source_name": r.source_name,
                    "date": r.date,
                    "provider": r.provider,
                },
            )
            for r in search_results[:max_results]
        ]

    except Exception:
        logger.exception("News search failed for query=%r", query)
        return []


async def _search_government(query: str, max_results: int) -> List[MultiSourceResult]:
    """Search government (.gov) sources for documents matching *query*."""
    try:
        from app.source_fetchers.government_fetcher import fetch_government_sources

        documents = await fetch_government_sources(
            topics=[query],
            max_results=max_results,
        )

        return [
            MultiSourceResult(
                title=doc.title,
                url=doc.url,
                snippet=(doc.excerpt or doc.content[:300] if doc.content else ""),
                source_type="government",
                metadata={
                    "source_name": doc.source_name,
                    "agency": doc.agency,
                    "document_type": doc.document_type,
                    "subcategory": doc.subcategory,
                    "published_at": (
                        doc.published_at.isoformat() if doc.published_at else None
                    ),
                },
            )
            for doc in documents[:max_results]
        ]

    except Exception:
        logger.exception("Government search failed for query=%r", query)
        return []


async def _search_academic(query: str, max_results: int) -> List[MultiSourceResult]:
    """Search arXiv for academic papers matching *query*."""
    try:
        from app.source_fetchers.academic_fetcher import fetch_academic_papers

        result = await fetch_academic_papers(
            query=query,
            max_results=max_results,
        )

        return [
            MultiSourceResult(
                title=paper.title,
                url=paper.arxiv_url,
                snippet=(paper.abstract[:300] if paper.abstract else ""),
                source_type="academic",
                metadata={
                    "arxiv_id": paper.arxiv_id,
                    "authors": paper.authors,
                    "primary_category": paper.primary_category,
                    "published_date": paper.published_date,
                    "pdf_url": paper.pdf_url,
                },
            )
            for paper in result.papers[:max_results]
        ]

    except Exception:
        logger.exception("Academic search failed for query=%r", query)
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def search_all_sources(
    query: str,
    *,
    include_grants_gov: bool = True,
    include_sam_gov: bool = True,
    include_web: bool = True,
    include_news: bool = True,
    include_government: bool = True,
    include_academic: bool = False,
    max_results_per_source: int = 5,
    rrf_k: int = 60,
    source_weights: dict[str, float] | None = None,
) -> List[MultiSourceResult]:
    """Search across multiple source types in parallel and return merged results.

    This is the primary entry point for consumers that need a broad search
    across all configured data sources.  Each source runs in its own async
    coroutine; failures in one source are logged and do not affect the others.

    Results are merged using **Reciprocal Rank Fusion** (RRF), which
    combines per-source rankings into a single unified ranking.  Results
    that appear in multiple sources receive a natural boost.

    Args:
        query: The search query string (required).
        include_grants_gov: Search Grants.gov for federal grant opportunities.
        include_sam_gov: Search SAM.gov for federal opportunities (requires
            ``SAM_GOV_API_KEY`` env var).
        include_web: Search the web via SearXNG / Serper / Tavily.
        include_news: Search news outlets via SearXNG / Serper / Tavily.
        include_government: Search .gov domains for policy documents and
            press releases.
        include_academic: Search arXiv for academic papers.  Off by default
            because it is slower and often less relevant for grant discovery.
        max_results_per_source: Maximum results to request from each
            individual source (default 5).
        rrf_k: The RRF constant *k* (default 60, matching our hybrid
            search implementation).  Higher values smooth rank differences.
        source_weights: Per-source weight multipliers.  Defaults to
            :data:`DEFAULT_SOURCE_WEIGHTS` which favours grant sources.

    Returns:
        A flat list of :class:`MultiSourceResult` objects, deduplicated by URL
        and sorted by descending RRF score.  Each result has ``rrf_score``
        populated and ``metadata["source_types"]`` listing which sources
        contributed.
    """
    if not query or not query.strip():
        logger.warning("search_all_sources called with empty query")
        return []

    query = query.strip()[:1000]  # Cap query length to prevent oversized API calls
    max_results_per_source = max(1, min(max_results_per_source, 50))

    # Build the list of coroutines for enabled sources.
    tasks: List[Any] = []
    source_labels: List[str] = []

    if include_grants_gov:
        tasks.append(_search_grants_gov(query, max_results_per_source))
        source_labels.append("grants_gov")

    if include_sam_gov:
        tasks.append(_search_sam_gov(query, max_results_per_source))
        source_labels.append("sam_gov")

    if include_web:
        tasks.append(_search_web(query, max_results_per_source))
        source_labels.append("web")

    if include_news:
        tasks.append(_search_news(query, max_results_per_source))
        source_labels.append("news")

    if include_government:
        tasks.append(_search_government(query, max_results_per_source))
        source_labels.append("government")

    if include_academic:
        tasks.append(_search_academic(query, max_results_per_source))
        source_labels.append("academic")

    if not tasks:
        logger.info("search_all_sources: no sources enabled")
        return []

    # Run all source searches in parallel with a timeout.  Exceptions inside
    # each wrapper are already caught, so return_exceptions=False is fine.
    # The 30-second timeout prevents a hung source from blocking all callers.
    try:
        results_per_source: List[List[MultiSourceResult]] = await asyncio.wait_for(
            asyncio.gather(*tasks), timeout=30
        )
    except asyncio.TimeoutError:
        logger.warning(
            "search_all_sources: timed out after 30s for query=%r", query[:80]
        )
        results_per_source = []

    # Log per-source counts for observability.
    for label, source_results in zip(source_labels, results_per_source):
        count = len(source_results) if isinstance(source_results, list) else 0
        logger.info("search_all_sources [%s]: %d results", label, count)

    # Merge, deduplicate, and rerank via Reciprocal Rank Fusion.
    merged = _rrf_rerank(
        results_per_source,
        source_labels,
        rrf_k=rrf_k,
        source_weights=source_weights,
    )

    logger.info(
        "search_all_sources: query=%r -> %d unique results from %d sources "
        "(top rrf_score=%.4f)",
        query[:80],
        len(merged),
        len(source_labels),
        merged[0].rrf_score if merged else 0.0,
    )

    return merged
