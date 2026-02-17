"""
Query generator for grant discovery system.

Generates search queries from Pillars and Top 25 Priorities for automated
grant opportunity discovery. Queries are tailored for finding federal, state,
and foundation grant opportunities relevant to city government, with
grant-type-specific modifiers.

Usage:
    generator = QueryGenerator()
    queries = generator.generate_queries(pillars_filter=['CH', 'MC'], max_queries=50)
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from enum import Enum

from app.taxonomy import PILLAR_DEFINITIONS

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class QueryConfig:
    """Configuration for a single search query."""

    query_text: str
    pillar_code: str
    priority_id: Optional[str] = None
    horizon_target: str = "H2"  # H1, H2, or H3
    source_context: str = "pillar"  # pillar, priority, or cross_pillar


class HorizonTarget(Enum):
    """Horizon targeting for queries."""

    H1 = "H1"  # Mainstream - 0-3 years
    H2 = "H2"  # Transitional - 3-7 years
    H3 = "H3"  # Transformative - 7-15+ years


# ============================================================================
# Top 25 Priorities
# ============================================================================

TOP_25_PRIORITIES: List[Dict[str, str]] = [
    {"id": "top25-01", "title": "First ACME Strategic Plan", "pillar_code": "EW"},
    {
        "id": "top25-02",
        "title": "Airline Use & Lease Agreement (Airport)",
        "pillar_code": "MC",
    },
    {"id": "top25-03", "title": "Shared Services Implementation", "pillar_code": "HG"},
    {"id": "top25-04", "title": "2026 Bond Program Development", "pillar_code": "HG"},
    {"id": "top25-05", "title": "Climate Revolving Fund", "pillar_code": "CH"},
    {
        "id": "top25-06",
        "title": "Expedited Site Plan Review Pilot",
        "pillar_code": "HG",
    },
    {
        "id": "top25-07",
        "title": "Development Code/Criteria Streamlining",
        "pillar_code": "HG",
    },
    {"id": "top25-08", "title": "Economic Development Roadmap", "pillar_code": "EW"},
    {"id": "top25-09", "title": "AE Resiliency Plan", "pillar_code": "MC"},
    {"id": "top25-10", "title": "Human Rights Framework", "pillar_code": "HG"},
    {
        "id": "top25-11",
        "title": "Facility Condition Assessment Contract",
        "pillar_code": "MC",
    },
    {"id": "top25-12", "title": "New Fire Labor Agreement", "pillar_code": "PS"},
    {"id": "top25-13", "title": "Rapid Rehousing Program Model", "pillar_code": "HH"},
    {
        "id": "top25-14",
        "title": "10-Year Housing Blueprint Update",
        "pillar_code": "HH",
    },
    {"id": "top25-15", "title": "AHFC 5-Year Strategic Plan", "pillar_code": "HH"},
    {
        "id": "top25-16",
        "title": "Phase 2 Compensation Recalibration",
        "pillar_code": "HG",
    },
    {
        "id": "top25-17",
        "title": "Alternative Parks Funding Strategies",
        "pillar_code": "CH",
    },
    {"id": "top25-18", "title": "Imagine Austin Update", "pillar_code": "HG"},
    {
        "id": "top25-19",
        "title": "Comprehensive Crime Reduction Plan",
        "pillar_code": "PS",
    },
    {"id": "top25-20", "title": "Police OCM Plan (BerryDunn)", "pillar_code": "PS"},
    {"id": "top25-21", "title": "Light Rail Interlocal Agreement", "pillar_code": "MC"},
    {
        "id": "top25-22",
        "title": "Citywide Technology Strategic Plan",
        "pillar_code": "HG",
    },
    {
        "id": "top25-23",
        "title": "IT Organizational Alignment (Phase 1)",
        "pillar_code": "HG",
    },
    {
        "id": "top25-24",
        "title": "Austin FIRST EMS Mental Health Pilot",
        "pillar_code": "PS",
    },
]


# ============================================================================
# Horizon Modifiers
# ============================================================================

HORIZON_MODIFIERS: Dict[str, Dict[str, Any]] = {
    "H1": {
        "name": "Active Grants",
        "timeframe": "Open now or opening soon",
        "description": "Currently open or recently announced grant opportunities",
        "search_modifiers": [
            "grant announcement",
            "NOFO",
            "notice of funding opportunity",
            "RFP",
            "request for proposals",
            "open for applications",
            "funding available",
        ],
        "time_qualifiers": [
            "2025",
            "2026",
            "FY2025",
            "FY2026",
            "now accepting",
        ],
        "signal_keywords": [
            "applications due",
            "deadline",
            "apply now",
            "funding announcement",
            "grant awarded",
        ],
    },
    "H2": {
        "name": "Upcoming Grants",
        "timeframe": "Expected within 1-2 years",
        "description": "Anticipated or recurring grant programs opening soon",
        "search_modifiers": [
            "grant program",
            "funding opportunity",
            "federal grant",
            "state grant",
            "grant application",
            "competitive grant",
            "formula grant",
        ],
        "time_qualifiers": [
            "upcoming",
            "anticipated",
            "expected",
            "annual",
            "recurring",
        ],
        "signal_keywords": [
            "expected to open",
            "annual funding cycle",
            "recurring grant",
            "new program",
            "reauthorized",
        ],
    },
    "H3": {
        "name": "Emerging Funding",
        "timeframe": "New or proposed programs",
        "description": "New legislation, proposed programs, and emerging funding sources",
        "search_modifiers": [
            "new grant program",
            "proposed funding",
            "legislation grants",
            "appropriations",
            "new federal funding",
            "bipartisan infrastructure",
            "Inflation Reduction Act",
        ],
        "time_qualifiers": [
            "proposed",
            "new program",
            "legislation",
            "appropriation",
            "authorization",
            "pilot program",
        ],
        "signal_keywords": [
            "new funding stream",
            "proposed legislation",
            "budget request",
            "new appropriations",
            "pilot grant program",
        ],
    },
}


# ============================================================================
# Municipal Keywords
# ============================================================================

GRANT_KEYWORDS: List[str] = [
    "grant",
    "grants",
    "funding opportunity",
    "NOFO",
    "notice of funding",
    "RFP",
    "grant application",
    "federal grant",
    "state grant",
    "foundation grant",
    "competitive grant",
    "formula grant",
    "city government",
    "local government",
    "municipal",
    "grant program",
    "funding announcement",
]


# ============================================================================
# Priority Search Templates
# ============================================================================

PRIORITY_SEARCH_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "top25-01": {  # First ACME Strategic Plan
        "topics": [
            "federal grants strategic planning local government",
            "grants.gov strategic plan implementation city",
            "EDA planning grants municipal government",
        ],
        "horizon_focus": "H1",
    },
    "top25-02": {  # Airline Use & Lease Agreement
        "topics": [
            "FAA airport improvement program grants",
            "federal aviation grants municipal airport",
            "airport infrastructure grants city government",
        ],
        "horizon_focus": "H1",
    },
    "top25-03": {  # Shared Services Implementation
        "topics": [
            "federal grants shared services government",
            "grants government consolidation efficiency",
            "intergovernmental cooperation grants city",
        ],
        "horizon_focus": "H2",
    },
    "top25-04": {  # 2026 Bond Program Development
        "topics": [
            "federal grants capital improvement city government",
            "infrastructure grants municipal bond programs",
            "HUD capital grants local government",
        ],
        "horizon_focus": "H1",
    },
    "top25-05": {  # Climate Revolving Fund
        "topics": [
            "EPA climate grants municipal government",
            "DOE clean energy grants city",
            "Inflation Reduction Act grants local government climate",
        ],
        "horizon_focus": "H2",
    },
    "top25-06": {  # Expedited Site Plan Review
        "topics": [
            "HUD planning grants development review",
            "federal grants permitting modernization city",
            "technology grants development services municipal",
        ],
        "horizon_focus": "H2",
    },
    "top25-07": {  # Development Code Streamlining
        "topics": [
            "HUD zoning reform grants city government",
            "federal grants land use planning municipal",
            "planning capacity building grants local government",
        ],
        "horizon_focus": "H2",
    },
    "top25-08": {  # Economic Development Roadmap
        "topics": [
            "EDA economic development grants city government",
            "SBA grants economic development municipal",
            "CDBG economic development funding local government",
        ],
        "horizon_focus": "H2",
    },
    "top25-09": {  # AE Resiliency Plan
        "topics": [
            "DOE grid resilience grants municipal utility",
            "FEMA resilience grants energy infrastructure",
            "Inflation Reduction Act energy grants city utility",
        ],
        "horizon_focus": "H2",
    },
    "top25-10": {  # Human Rights Framework
        "topics": [
            "DOJ civil rights grants local government",
            "federal equity grants city government",
            "HHS grants human rights municipal",
        ],
        "horizon_focus": "H1",
    },
    "top25-11": {  # Facility Condition Assessment
        "topics": [
            "federal facility improvement grants city government",
            "DOE building efficiency grants municipal",
            "GSA facility grants local government",
        ],
        "horizon_focus": "H2",
    },
    "top25-12": {  # Fire Labor Agreement
        "topics": [
            "FEMA SAFER grants fire department staffing",
            "FEMA Assistance to Firefighters grants",
            "federal fire department grants city government",
        ],
        "horizon_focus": "H1",
    },
    "top25-13": {  # Rapid Rehousing Program
        "topics": [
            "HUD rapid rehousing grants city government",
            "Emergency Solutions Grants homeless assistance",
            "continuum of care grants rapid rehousing",
        ],
        "horizon_focus": "H2",
    },
    "top25-14": {  # 10-Year Housing Blueprint
        "topics": [
            "HUD housing planning grants city government",
            "HOME Investment Partnerships grants municipal",
            "affordable housing grants local government NOFO",
        ],
        "horizon_focus": "H2",
    },
    "top25-15": {  # AHFC 5-Year Strategic Plan
        "topics": [
            "HUD public housing grants housing authority",
            "HUD capital fund grants housing",
            "housing authority grants modernization federal",
        ],
        "horizon_focus": "H2",
    },
    "top25-16": {  # Compensation Recalibration
        "topics": [
            "federal workforce grants local government",
            "DOL grants government workforce development",
            "grants public sector workforce city",
        ],
        "horizon_focus": "H1",
    },
    "top25-17": {  # Alternative Parks Funding
        "topics": [
            "Land and Water Conservation Fund grants city",
            "NPS park grants municipal government",
            "federal recreation grants city parks",
        ],
        "horizon_focus": "H2",
    },
    "top25-18": {  # Imagine Austin Update
        "topics": [
            "HUD comprehensive planning grants city",
            "EDA planning grants local government",
            "federal grants community planning municipal",
        ],
        "horizon_focus": "H2",
    },
    "top25-19": {  # Comprehensive Crime Reduction
        "topics": [
            "DOJ Byrne JAG grants crime reduction city",
            "BJA community violence intervention grants",
            "federal crime reduction grants local government",
        ],
        "horizon_focus": "H2",
    },
    "top25-20": {  # Police OCM Plan
        "topics": [
            "COPS Office grants police department city",
            "DOJ law enforcement grants municipal",
            "federal police modernization grants city government",
        ],
        "horizon_focus": "H2",
    },
    "top25-21": {  # Light Rail Interlocal Agreement
        "topics": [
            "FTA Capital Investment Grants light rail",
            "FTA New Starts grants transit city",
            "federal transit grants rail municipal",
        ],
        "horizon_focus": "H2",
    },
    "top25-22": {  # Citywide Technology Strategic Plan
        "topics": [
            "NTIA digital equity grants city government",
            "federal technology grants municipal government",
            "DHS cybersecurity grants city IT modernization",
        ],
        "horizon_focus": "H2",
    },
    "top25-23": {  # IT Organizational Alignment
        "topics": [
            "federal IT modernization grants local government",
            "technology grants government operations city",
            "NSF grants smart city technology municipal",
        ],
        "horizon_focus": "H1",
    },
    "top25-24": {  # Austin FIRST EMS Mental Health
        "topics": [
            "SAMHSA mental health grants crisis response city",
            "HHS grants mental health EMS co-responder",
            "federal crisis intervention grants local government",
            "SAMHSA community mental health grants municipal",
        ],
        "horizon_focus": "H2",
    },
}


# ============================================================================
# Query Generator Class
# ============================================================================


class QueryGenerator:
    """
    Generates search queries for grant discovery system.

    Creates grant-focused queries from:
    - Pillar definitions with federal/state grant programs and agencies
    - Top 25 Priorities with grant-specific search topics
    - Grant-type modifiers (active NOFOs, upcoming, emerging funding)

    Example:
        generator = QueryGenerator()

        # Generate queries for specific pillars
        queries = generator.generate_queries(
            pillars_filter=['CH', 'MC'],
            max_queries=50
        )

        # Generate queries for all grant types
        queries = generator.generate_queries(
            horizons=['H1', 'H2', 'H3'],
            max_queries=100
        )
    """

    def __init__(self):
        self.pillars = PILLAR_DEFINITIONS
        self.priorities = TOP_25_PRIORITIES
        self.horizon_modifiers = HORIZON_MODIFIERS
        self.grant_keywords = GRANT_KEYWORDS
        self.priority_templates = PRIORITY_SEARCH_TEMPLATES

    def generate_queries(
        self,
        pillars_filter: Optional[List[str]] = None,
        horizons: Optional[List[str]] = None,
        include_priorities: bool = True,
        max_queries: int = 100,
    ) -> List[QueryConfig]:
        """
        Generate search queries based on filters.

        Args:
            pillars_filter: List of pillar codes to include (default: all)
            horizons: List of horizons to target (default: ['H1', 'H2', 'H3'])
            include_priorities: Whether to include Top 25 priority queries
            max_queries: Maximum number of queries to generate

        Returns:
            List of QueryConfig objects ready for search execution
        """
        queries: List[QueryConfig] = []

        # Default to all pillars if not specified
        target_pillars = pillars_filter or list(self.pillars.keys())

        # Default to all horizons
        target_horizons = horizons or ["H1", "H2", "H3"]

        logger.info(
            f"Generating queries for pillars={target_pillars}, "
            f"horizons={target_horizons}, max={max_queries}"
        )

        # Generate pillar-based queries
        for pillar_code in target_pillars:
            if pillar_code in self.pillars:
                pillar_queries = self._generate_pillar_queries(
                    pillar_code, target_horizons
                )
                queries.extend(pillar_queries)

        # Generate priority-based queries
        if include_priorities:
            for priority in self.priorities:
                if priority["pillar_code"] in target_pillars:
                    priority_queries = self._generate_priority_queries(priority)
                    queries.extend(priority_queries)

        # Deduplicate by query text
        seen_queries = set()
        unique_queries = []
        for q in queries:
            if q.query_text.lower() not in seen_queries:
                seen_queries.add(q.query_text.lower())
                unique_queries.append(q)

        # Limit to max_queries
        if len(unique_queries) > max_queries:
            # Prioritize priority queries, then distribute evenly across pillars
            priority_queries = [q for q in unique_queries if q.priority_id]
            pillar_queries = [q for q in unique_queries if not q.priority_id]

            # Take all priority queries up to half the limit
            max_priority = min(len(priority_queries), max_queries // 2)
            selected = priority_queries[:max_priority]

            # Fill remaining with pillar queries
            remaining = max_queries - len(selected)
            selected.extend(pillar_queries[:remaining])

            unique_queries = selected

        logger.info(f"Generated {len(unique_queries)} unique queries")
        return unique_queries

    def _generate_pillar_queries(
        self, pillar_code: str, horizons: List[str]
    ) -> List[QueryConfig]:
        """
        Generate queries for a specific pillar across target horizons.

        Args:
            pillar_code: Pillar code (e.g., 'CH', 'MC')
            horizons: List of horizon codes to target

        Returns:
            List of QueryConfig for this pillar
        """
        queries = []
        pillar = self.pillars.get(pillar_code)

        if not pillar:
            logger.warning(f"Unknown pillar code: {pillar_code}")
            return queries

        # Generate from focus areas
        for focus_area in pillar.get("focus_areas", []):
            for horizon in horizons:
                modified_query = self._add_horizon_modifiers(focus_area, horizon)
                queries.append(
                    QueryConfig(
                        query_text=modified_query,
                        pillar_code=pillar_code,
                        horizon_target=horizon,
                        source_context="pillar",
                    )
                )

        # Generate from search terms
        for search_term in pillar.get("search_terms", []):
            for horizon in horizons:
                modified_query = self._add_horizon_modifiers(search_term, horizon)
                queries.append(
                    QueryConfig(
                        query_text=modified_query,
                        pillar_code=pillar_code,
                        horizon_target=horizon,
                        source_context="pillar",
                    )
                )

        return queries

    def _generate_priority_queries(self, priority: Dict[str, str]) -> List[QueryConfig]:
        """
        Generate queries for a specific Top 25 priority.

        Args:
            priority: Priority dict with id, title, pillar_code

        Returns:
            List of QueryConfig for this priority
        """
        queries = []
        priority_id = priority["id"]
        pillar_code = priority["pillar_code"]

        if template := self.priority_templates.get(priority_id):
            topics = template.get("topics", [])
            horizon_focus = template.get("horizon_focus", "H2")

            for topic in topics:
                # Generate with primary horizon focus
                modified_query = self._add_horizon_modifiers(topic, horizon_focus)
                queries.append(
                    QueryConfig(
                        query_text=modified_query,
                        pillar_code=pillar_code,
                        priority_id=priority_id,
                        horizon_target=horizon_focus,
                        source_context="priority",
                    )
                )

                # Also generate one query for adjacent horizon
                adjacent_horizon = "H3" if horizon_focus == "H2" else "H2"
                adjacent_query = self._add_horizon_modifiers(topic, adjacent_horizon)
                queries.append(
                    QueryConfig(
                        query_text=adjacent_query,
                        pillar_code=pillar_code,
                        priority_id=priority_id,
                        horizon_target=adjacent_horizon,
                        source_context="priority",
                    )
                )
        else:
            # Fallback: generate generic query from priority title
            title = priority["title"]
            for horizon in ["H1", "H2"]:  # Search active and upcoming grants
                query_text = f"{title} federal grants city government funding"
                modified_query = self._add_horizon_modifiers(query_text, horizon)
                queries.append(
                    QueryConfig(
                        query_text=modified_query,
                        pillar_code=pillar_code,
                        priority_id=priority_id,
                        horizon_target=horizon,
                        source_context="priority",
                    )
                )

        return queries

    def _add_horizon_modifiers(self, base_query: str, horizon: str) -> str:
        """
        Add grant-type-specific modifiers to a base query.

        Args:
            base_query: Base search query
            horizon: Grant type target (H1=active, H2=upcoming, H3=emerging)

        Returns:
            Modified query string with grant discovery context
        """
        horizon_config = self.horizon_modifiers.get(
            horizon, self.horizon_modifiers["H2"]
        )

        # Select a modifier based on query content
        modifiers = horizon_config.get("search_modifiers", [])
        time_qualifiers = horizon_config.get("time_qualifiers", [])

        # Use first modifier and time qualifier for consistency
        modifier = modifiers[0] if modifiers else ""
        time_qual = time_qualifiers[0] if time_qualifiers else ""

        # Construct modified query
        current_year = datetime.now(timezone.utc).year
        if horizon == "H1":
            # H1: Currently open grant opportunities
            return f"{base_query} {modifier} {current_year} {time_qual}"
        elif horizon == "H2":
            # H2: Upcoming and recurring grant programs
            return f"{base_query} {modifier} {time_qual}"
        else:
            # H3: New and proposed funding programs
            return f"{base_query} {modifier} city government"

    def get_pillar_info(self, pillar_code: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific pillar."""
        return self.pillars.get(pillar_code)

    def get_priority_info(self, priority_id: str) -> Optional[Dict[str, str]]:
        """Get information about a specific priority."""
        return next(
            (priority for priority in self.priorities if priority["id"] == priority_id),
            None,
        )

    def get_priorities_for_pillar(self, pillar_code: str) -> List[Dict[str, str]]:
        """Get all priorities for a specific pillar."""
        return [p for p in self.priorities if p["pillar_code"] == pillar_code]


# ============================================================================
# Convenience Functions
# ============================================================================


def generate_discovery_queries(
    pillars: Optional[List[str]] = None, max_queries: int = 100
) -> List[QueryConfig]:
    """
    Convenience function to generate grant discovery queries.

    Args:
        pillars: Optional list of pillar codes to filter
        max_queries: Maximum number of queries

    Returns:
        List of QueryConfig objects for grant opportunity search
    """
    generator = QueryGenerator()
    return generator.generate_queries(pillars_filter=pillars, max_queries=max_queries)


def get_all_pillar_codes() -> List[str]:
    """Get all available pillar codes."""
    return list(PILLAR_DEFINITIONS.keys())


def get_all_priority_ids() -> List[str]:
    """Get all available priority IDs."""
    return [p["id"] for p in TOP_25_PRIORITIES]
