"""Search-related utility functions extracted from main.py.

Functions for applying advanced search filters, score threshold filters,
and extracting text highlights from search results.
"""

from typing import Any, Dict, List, Optional

from app.models.search import SearchFilters


def _apply_search_filters(
    results: List[Dict[str, Any]], filters: SearchFilters
) -> List[Dict[str, Any]]:
    """Apply advanced filters to search results."""
    filtered = results

    # Filter by pillar_ids
    if filters.pillar_ids:
        filtered = [r for r in filtered if r.get("pillar_id") in filters.pillar_ids]

    # Filter by goal_ids
    if filters.goal_ids:
        filtered = [r for r in filtered if r.get("goal_id") in filters.goal_ids]

    # Filter by stage_ids
    if filters.stage_ids:
        filtered = [r for r in filtered if r.get("stage_id") in filters.stage_ids]

    # Filter by horizon
    if filters.horizon and filters.horizon != "ALL":
        filtered = [r for r in filtered if r.get("horizon") == filters.horizon]

    # Filter by status
    if filters.status:
        filtered = [r for r in filtered if r.get("status") == filters.status]

    # Filter by date range
    if filters.date_range:
        if filters.date_range.start:
            start_str = filters.date_range.start.isoformat()
            filtered = [
                r
                for r in filtered
                if r.get("created_at") and r["created_at"][:10] >= start_str
            ]
        if filters.date_range.end:
            end_str = filters.date_range.end.isoformat()
            filtered = [
                r
                for r in filtered
                if r.get("created_at") and r["created_at"][:10] <= end_str
            ]

    # Filter by score thresholds
    if filters.score_thresholds:
        filtered = _apply_score_filters(filtered, filters.score_thresholds)

    return filtered


def _apply_score_filters(
    results: List[Dict[str, Any]], thresholds
) -> List[Dict[str, Any]]:
    """Apply score threshold filters to results."""
    filtered = results

    score_fields = [
        ("impact_score", thresholds.impact_score),
        ("relevance_score", thresholds.relevance_score),
        ("novelty_score", thresholds.novelty_score),
        ("maturity_score", thresholds.maturity_score),
        ("velocity_score", thresholds.velocity_score),
        ("risk_score", thresholds.risk_score),
        ("opportunity_score", thresholds.opportunity_score),
    ]

    for field_name, threshold in score_fields:
        if threshold:
            if threshold.min is not None:
                filtered = [
                    r
                    for r in filtered
                    if r.get(field_name) is not None and r[field_name] >= threshold.min
                ]
            if threshold.max is not None:
                filtered = [
                    r
                    for r in filtered
                    if r.get(field_name) is not None and r[field_name] <= threshold.max
                ]

    return filtered


def _extract_highlights(item: Dict[str, Any], query: str) -> Optional[List[str]]:
    """Extract text snippets containing the search query."""
    if not query:
        return None

    highlights = []
    query_lower = query.lower()

    # Check name
    name = item.get("name", "") or ""
    if query_lower in name.lower():
        highlights.append(name)

    # Check summary and extract snippet
    summary = item.get("summary", "") or ""
    if query_lower in summary.lower():
        # Find position and extract context
        pos = summary.lower().find(query_lower)
        start = max(0, pos - 50)
        end = min(len(summary), pos + len(query) + 50)
        snippet = (
            ("..." if start > 0 else "")
            + summary[start:end]
            + ("..." if end < len(summary) else "")
        )
        highlights.append(snippet)

    return highlights or None
