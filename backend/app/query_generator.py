"""
Query generator for discovery system.

Generates search queries from Pillars and Top 25 Priorities for automated
horizon scanning. Queries are tailored for municipal government context
with horizon-specific modifiers.

Usage:
    generator = QueryGenerator()
    queries = generator.generate_queries(pillars_filter=['CH', 'MC'], max_queries=50)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum

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
# Pillar Definitions
# ============================================================================

PILLAR_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "CH": {
        "name": "Community Health & Sustainability",
        "description": "Public health, parks, climate, preparedness, and animal services",
        "focus_areas": [
            "public health technology",
            "parks and recreation innovation",
            "climate change mitigation",
            "emergency preparedness systems",
            "environmental monitoring",
            "community wellness programs",
            "urban green infrastructure",
            "air quality management",
            "water conservation technology",
            "renewable energy municipal",
        ],
        "search_terms": [
            "municipal public health technology",
            "smart parks city government",
            "climate resilience cities",
            "emergency management innovation",
            "urban sustainability technology",
            "city environmental monitoring",
            "community health platforms",
        ],
    },
    "EW": {
        "name": "Economic & Workforce Development",
        "description": "Economic mobility, small business support, and creative economy",
        "focus_areas": [
            "workforce development technology",
            "small business support platforms",
            "economic development tools",
            "job training automation",
            "creative economy platforms",
            "entrepreneurship ecosystems",
            "digital skills training",
            "gig economy regulation",
            "local business analytics",
            "economic impact measurement",
        ],
        "search_terms": [
            "municipal workforce development",
            "small business city programs",
            "economic development technology cities",
            "job training government programs",
            "creative economy city initiatives",
            "entrepreneur support municipal",
        ],
    },
    "HG": {
        "name": "High-Performing Government",
        "description": "Fiscal integrity, technology, workforce, and community engagement",
        "focus_areas": [
            "government technology modernization",
            "civic engagement platforms",
            "municipal process automation",
            "government AI applications",
            "public sector analytics",
            "digital government services",
            "transparency technology",
            "citizen feedback systems",
            "government workforce tools",
            "municipal data platforms",
        ],
        "search_terms": [
            "government technology innovation",
            "civic tech municipal",
            "city automation solutions",
            "public sector AI",
            "digital government transformation",
            "municipal data analytics",
            "government efficiency technology",
        ],
    },
    "HH": {
        "name": "Homelessness & Housing",
        "description": "Complete communities, affordable housing, and homelessness reduction",
        "focus_areas": [
            "affordable housing technology",
            "homelessness prevention systems",
            "housing management platforms",
            "tenant services technology",
            "housing construction innovation",
            "supportive housing models",
            "housing voucher systems",
            "property management automation",
            "housing market analytics",
            "community development tools",
        ],
        "search_terms": [
            "affordable housing technology cities",
            "homelessness solutions municipal",
            "housing management city government",
            "tenant support technology",
            "housing innovation government",
            "supportive housing technology",
        ],
    },
    "MC": {
        "name": "Mobility & Critical Infrastructure",
        "description": "Transportation, transit, utilities, and facility management",
        "focus_areas": [
            "autonomous vehicles municipal",
            "smart traffic systems",
            "public transit technology",
            "electric vehicle infrastructure",
            "smart grid technology",
            "water infrastructure monitoring",
            "facility management automation",
            "micromobility regulation",
            "transportation demand management",
            "infrastructure maintenance AI",
        ],
        "search_terms": [
            "smart city transportation",
            "municipal transit technology",
            "autonomous vehicles cities",
            "EV infrastructure municipal",
            "smart infrastructure city",
            "utility technology government",
            "facility management cities",
        ],
    },
    "PS": {
        "name": "Public Safety",
        "description": "Community relationships, fair delivery, and disaster preparedness",
        "focus_areas": [
            "public safety technology",
            "emergency response systems",
            "crime prevention technology",
            "community policing tools",
            "disaster preparedness systems",
            "fire service technology",
            "EMS innovation",
            "911 systems modernization",
            "mental health crisis response",
            "violence prevention programs",
        ],
        "search_terms": [
            "public safety technology cities",
            "emergency response innovation",
            "crime prevention municipal",
            "community safety technology",
            "disaster preparedness city",
            "fire service innovation",
            "EMS technology government",
        ],
    },
}


# ============================================================================
# Top 25 Priorities
# ============================================================================

TOP_25_PRIORITIES: List[Dict[str, str]] = [
    {"id": "top25-01", "title": "First ACME Strategic Plan", "pillar_code": "EW"},
    {"id": "top25-02", "title": "Airline Use & Lease Agreement (Airport)", "pillar_code": "MC"},
    {"id": "top25-03", "title": "Shared Services Implementation", "pillar_code": "HG"},
    {"id": "top25-04", "title": "2026 Bond Program Development", "pillar_code": "HG"},
    {"id": "top25-05", "title": "Climate Revolving Fund", "pillar_code": "CH"},
    {"id": "top25-06", "title": "Expedited Site Plan Review Pilot", "pillar_code": "HG"},
    {"id": "top25-07", "title": "Development Code/Criteria Streamlining", "pillar_code": "HG"},
    {"id": "top25-08", "title": "Economic Development Roadmap", "pillar_code": "EW"},
    {"id": "top25-09", "title": "AE Resiliency Plan", "pillar_code": "MC"},
    {"id": "top25-10", "title": "Human Rights Framework", "pillar_code": "HG"},
    {"id": "top25-11", "title": "Facility Condition Assessment Contract", "pillar_code": "MC"},
    {"id": "top25-12", "title": "New Fire Labor Agreement", "pillar_code": "PS"},
    {"id": "top25-13", "title": "Rapid Rehousing Program Model", "pillar_code": "HH"},
    {"id": "top25-14", "title": "10-Year Housing Blueprint Update", "pillar_code": "HH"},
    {"id": "top25-15", "title": "AHFC 5-Year Strategic Plan", "pillar_code": "HH"},
    {"id": "top25-16", "title": "Phase 2 Compensation Recalibration", "pillar_code": "HG"},
    {"id": "top25-17", "title": "Alternative Parks Funding Strategies", "pillar_code": "CH"},
    {"id": "top25-18", "title": "Imagine Austin Update", "pillar_code": "HG"},
    {"id": "top25-19", "title": "Comprehensive Crime Reduction Plan", "pillar_code": "PS"},
    {"id": "top25-20", "title": "Police OCM Plan (BerryDunn)", "pillar_code": "PS"},
    {"id": "top25-21", "title": "Light Rail Interlocal Agreement", "pillar_code": "MC"},
    {"id": "top25-22", "title": "Citywide Technology Strategic Plan", "pillar_code": "HG"},
    {"id": "top25-23", "title": "IT Organizational Alignment (Phase 1)", "pillar_code": "HG"},
    {"id": "top25-24", "title": "Austin FIRST EMS Mental Health Pilot", "pillar_code": "PS"},
]


# ============================================================================
# Horizon Modifiers
# ============================================================================

HORIZON_MODIFIERS: Dict[str, Dict[str, Any]] = {
    "H1": {
        "name": "Mainstream",
        "timeframe": "0-3 years",
        "description": "Current system, confirms baseline",
        "search_modifiers": [
            "implementation",
            "deployment",
            "rollout",
            "adoption",
            "case study",
            "results",
            "lessons learned",
        ],
        "time_qualifiers": [
            "2024",
            "2025",
            "currently deployed",
            "in production",
            "operational",
        ],
        "signal_keywords": [
            "cities across the country",
            "widespread adoption",
            "industry standard",
            "best practices",
            "proven approach",
        ],
    },
    "H2": {
        "name": "Transitional",
        "timeframe": "3-7 years",
        "description": "Emerging alternatives, pilots",
        "search_modifiers": [
            "pilot program",
            "pilot project",
            "testing",
            "trial",
            "early adoption",
            "proof of concept",
            "demonstration",
        ],
        "time_qualifiers": [
            "pilot",
            "testing",
            "evaluating",
            "considering",
            "planning",
        ],
        "signal_keywords": [
            "city announces pilot",
            "testing new approach",
            "innovative program",
            "first to implement",
            "early results",
        ],
    },
    "H3": {
        "name": "Transformative",
        "timeframe": "7-15+ years",
        "description": "Weak signals, novel possibilities",
        "search_modifiers": [
            "emerging technology",
            "research",
            "breakthrough",
            "future of",
            "next generation",
            "revolutionary",
            "transformative",
        ],
        "time_qualifiers": [
            "research",
            "concept",
            "prototype",
            "startup",
            "venture capital",
            "patent",
        ],
        "signal_keywords": [
            "could transform",
            "potential to disrupt",
            "researchers develop",
            "startup raises",
            "breakthrough in",
        ],
    },
}


# ============================================================================
# Municipal Keywords
# ============================================================================

MUNICIPAL_KEYWORDS: List[str] = [
    "municipal",
    "city government",
    "local government",
    "city of",
    "public sector",
    "government agency",
    "urban",
    "metropolitan",
    "county government",
    "city council",
    "city manager",
    "civic",
    "public administration",
    "government services",
    "taxpayer",
    "constituent",
    "citizen services",
]


# ============================================================================
# Priority Search Templates
# ============================================================================

PRIORITY_SEARCH_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "top25-01": {  # First ACME Strategic Plan
        "topics": ["strategic planning technology", "municipal strategic plan software", "government strategic alignment"],
        "horizon_focus": "H1",
    },
    "top25-02": {  # Airline Use & Lease Agreement
        "topics": ["airport lease management", "airline agreement technology", "airport revenue management"],
        "horizon_focus": "H1",
    },
    "top25-03": {  # Shared Services Implementation
        "topics": ["shared services government", "municipal shared services", "government consolidation technology"],
        "horizon_focus": "H2",
    },
    "top25-04": {  # 2026 Bond Program Development
        "topics": ["municipal bond management", "government bond issuance technology", "capital improvement planning"],
        "horizon_focus": "H1",
    },
    "top25-05": {  # Climate Revolving Fund
        "topics": ["climate finance municipal", "green revolving fund", "sustainability financing government"],
        "horizon_focus": "H2",
    },
    "top25-06": {  # Expedited Site Plan Review
        "topics": ["automated plan review", "permit automation", "development review AI"],
        "horizon_focus": "H2",
    },
    "top25-07": {  # Development Code Streamlining
        "topics": ["zoning code modernization", "development code automation", "land use regulation technology"],
        "horizon_focus": "H2",
    },
    "top25-08": {  # Economic Development Roadmap
        "topics": ["economic development strategy", "municipal economic planning", "business attraction technology"],
        "horizon_focus": "H2",
    },
    "top25-09": {  # AE Resiliency Plan
        "topics": ["utility resiliency", "grid resilience", "energy infrastructure security"],
        "horizon_focus": "H2",
    },
    "top25-10": {  # Human Rights Framework
        "topics": ["human rights technology", "equity measurement tools", "civil rights compliance"],
        "horizon_focus": "H1",
    },
    "top25-11": {  # Facility Condition Assessment
        "topics": ["facility assessment technology", "building condition monitoring", "asset management AI"],
        "horizon_focus": "H2",
    },
    "top25-12": {  # Fire Labor Agreement
        "topics": ["fire department technology", "first responder scheduling", "public safety workforce"],
        "horizon_focus": "H1",
    },
    "top25-13": {  # Rapid Rehousing Program
        "topics": ["rapid rehousing technology", "housing placement systems", "homelessness management platform"],
        "horizon_focus": "H2",
    },
    "top25-14": {  # 10-Year Housing Blueprint
        "topics": ["housing strategy technology", "affordable housing planning", "housing market analytics"],
        "horizon_focus": "H2",
    },
    "top25-15": {  # AHFC 5-Year Strategic Plan
        "topics": ["housing authority technology", "public housing modernization", "housing finance innovation"],
        "horizon_focus": "H2",
    },
    "top25-16": {  # Compensation Recalibration
        "topics": ["public sector compensation", "government pay equity", "workforce compensation analytics"],
        "horizon_focus": "H1",
    },
    "top25-17": {  # Alternative Parks Funding
        "topics": ["parks funding innovation", "recreation revenue technology", "public space financing"],
        "horizon_focus": "H2",
    },
    "top25-18": {  # Imagine Austin Update
        "topics": ["comprehensive plan technology", "urban planning software", "community visioning tools"],
        "horizon_focus": "H2",
    },
    "top25-19": {  # Comprehensive Crime Reduction
        "topics": ["crime reduction technology", "public safety analytics", "violence intervention systems"],
        "horizon_focus": "H2",
    },
    "top25-20": {  # Police OCM Plan
        "topics": ["police modernization", "law enforcement technology", "public safety reform"],
        "horizon_focus": "H2",
    },
    "top25-21": {  # Light Rail Interlocal Agreement
        "topics": ["light rail technology", "transit expansion", "rail transit innovation"],
        "horizon_focus": "H2",
    },
    "top25-22": {  # Citywide Technology Strategic Plan
        "topics": ["government IT strategy", "municipal technology modernization", "digital government transformation"],
        "horizon_focus": "H2",
    },
    "top25-23": {  # IT Organizational Alignment
        "topics": ["government IT organization", "public sector IT management", "technology governance municipal"],
        "horizon_focus": "H1",
    },
    "top25-24": {  # Austin FIRST EMS Mental Health
        "topics": ["mental health crisis response", "EMS mental health", "co-responder programs", "crisis intervention technology"],
        "horizon_focus": "H2",
    },
}


# ============================================================================
# Query Generator Class
# ============================================================================

class QueryGenerator:
    """
    Generates search queries for discovery system.

    Creates municipal-focused queries from:
    - Pillar definitions and focus areas
    - Top 25 Priorities with specific search topics
    - Horizon-specific modifiers for temporal targeting

    Example:
        generator = QueryGenerator()

        # Generate queries for specific pillars
        queries = generator.generate_queries(
            pillars_filter=['CH', 'MC'],
            max_queries=50
        )

        # Generate queries for all horizons
        queries = generator.generate_queries(
            horizons=['H1', 'H2', 'H3'],
            max_queries=100
        )
    """

    def __init__(self):
        self.pillars = PILLAR_DEFINITIONS
        self.priorities = TOP_25_PRIORITIES
        self.horizon_modifiers = HORIZON_MODIFIERS
        self.municipal_keywords = MUNICIPAL_KEYWORDS
        self.priority_templates = PRIORITY_SEARCH_TEMPLATES

    def generate_queries(
        self,
        pillars_filter: Optional[List[str]] = None,
        horizons: Optional[List[str]] = None,
        include_priorities: bool = True,
        max_queries: int = 100
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
                    pillar_code,
                    target_horizons
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
        self,
        pillar_code: str,
        horizons: List[str]
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
                queries.append(QueryConfig(
                    query_text=modified_query,
                    pillar_code=pillar_code,
                    horizon_target=horizon,
                    source_context="pillar"
                ))

        # Generate from search terms
        for search_term in pillar.get("search_terms", []):
            for horizon in horizons:
                modified_query = self._add_horizon_modifiers(search_term, horizon)
                queries.append(QueryConfig(
                    query_text=modified_query,
                    pillar_code=pillar_code,
                    horizon_target=horizon,
                    source_context="pillar"
                ))

        return queries

    def _generate_priority_queries(
        self,
        priority: Dict[str, str]
    ) -> List[QueryConfig]:
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

        # Get priority-specific template if available
        template = self.priority_templates.get(priority_id)

        if template:
            topics = template.get("topics", [])
            horizon_focus = template.get("horizon_focus", "H2")

            for topic in topics:
                # Generate with primary horizon focus
                modified_query = self._add_horizon_modifiers(topic, horizon_focus)
                queries.append(QueryConfig(
                    query_text=modified_query,
                    pillar_code=pillar_code,
                    priority_id=priority_id,
                    horizon_target=horizon_focus,
                    source_context="priority"
                ))

                # Also generate one query for adjacent horizon
                adjacent_horizon = "H3" if horizon_focus == "H2" else "H2"
                adjacent_query = self._add_horizon_modifiers(topic, adjacent_horizon)
                queries.append(QueryConfig(
                    query_text=adjacent_query,
                    pillar_code=pillar_code,
                    priority_id=priority_id,
                    horizon_target=adjacent_horizon,
                    source_context="priority"
                ))
        else:
            # Fallback: generate generic query from priority title
            title = priority["title"]
            for horizon in ["H2", "H3"]:  # Priorities usually focus on emerging
                query_text = f"{title} municipal government technology innovation"
                modified_query = self._add_horizon_modifiers(query_text, horizon)
                queries.append(QueryConfig(
                    query_text=modified_query,
                    pillar_code=pillar_code,
                    priority_id=priority_id,
                    horizon_target=horizon,
                    source_context="priority"
                ))

        return queries

    def _add_horizon_modifiers(
        self,
        base_query: str,
        horizon: str
    ) -> str:
        """
        Add horizon-specific modifiers to a base query.

        Args:
            base_query: Base search query
            horizon: Target horizon (H1, H2, H3)

        Returns:
            Modified query string with horizon context
        """
        horizon_config = self.horizon_modifiers.get(horizon, self.horizon_modifiers["H2"])

        # Select a modifier based on query content
        modifiers = horizon_config.get("search_modifiers", [])
        time_qualifiers = horizon_config.get("time_qualifiers", [])

        # Use first modifier and time qualifier for consistency
        modifier = modifiers[0] if modifiers else ""
        time_qual = time_qualifiers[0] if time_qualifiers else ""

        # Construct modified query
        current_year = datetime.now().year
        if horizon == "H1":
            # H1: Focus on current implementations
            return f"{base_query} {modifier} city government {current_year} {current_year + 1}"
        elif horizon == "H2":
            # H2: Focus on pilots and emerging
            return f"{base_query} {modifier} municipal {time_qual}"
        else:
            # H3: Focus on research and future
            return f"{base_query} {modifier} future city government"

    def get_pillar_info(self, pillar_code: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific pillar."""
        return self.pillars.get(pillar_code)

    def get_priority_info(self, priority_id: str) -> Optional[Dict[str, str]]:
        """Get information about a specific priority."""
        for priority in self.priorities:
            if priority["id"] == priority_id:
                return priority
        return None

    def get_priorities_for_pillar(self, pillar_code: str) -> List[Dict[str, str]]:
        """Get all priorities for a specific pillar."""
        return [p for p in self.priorities if p["pillar_code"] == pillar_code]


# ============================================================================
# Convenience Functions
# ============================================================================

def generate_discovery_queries(
    pillars: Optional[List[str]] = None,
    max_queries: int = 100
) -> List[QueryConfig]:
    """
    Convenience function to generate discovery queries.

    Args:
        pillars: Optional list of pillar codes to filter
        max_queries: Maximum number of queries

    Returns:
        List of QueryConfig objects
    """
    generator = QueryGenerator()
    return generator.generate_queries(
        pillars_filter=pillars,
        max_queries=max_queries
    )


def get_all_pillar_codes() -> List[str]:
    """Get all available pillar codes."""
    return list(PILLAR_DEFINITIONS.keys())


def get_all_priority_ids() -> List[str]:
    """Get all available priority IDs."""
    return [p["id"] for p in TOP_25_PRIORITIES]
