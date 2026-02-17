"""
Austin strategic context for research report enrichment.

Provides CMO Top 25 priorities, city departments, strategic pillars,
and peer city list for comparative benchmarking.
"""

from typing import List, Dict

from app.taxonomy import PILLAR_NAMES

# ---------------------------------------------------------------------------
# Strategic pillar reference (canonical source: taxonomy.py)
# ---------------------------------------------------------------------------
STRATEGIC_PILLARS = PILLAR_NAMES

# ---------------------------------------------------------------------------
# CMO Top 25 Priorities
# ---------------------------------------------------------------------------
CMO_TOP_25_PRIORITIES: List[Dict] = [
    # Homelessness & Housing (HH)
    {"id": "T1", "name": "Reduce chronic homelessness by 50%", "pillar": "HH"},
    {"id": "T2", "name": "Expand affordable housing inventory", "pillar": "HH"},
    {
        "id": "T3",
        "name": "Accelerate permanent supportive housing development",
        "pillar": "HH",
    },
    {
        "id": "T4",
        "name": "Strengthen tenant protections and anti-displacement programs",
        "pillar": "HH",
    },
    # Mobility & Critical Infrastructure (MC)
    {"id": "T5", "name": "Improve transit ridership and connectivity", "pillar": "MC"},
    {"id": "T6", "name": "Advance Vision Zero traffic safety", "pillar": "MC"},
    {
        "id": "T7",
        "name": "Expand protected bike and pedestrian infrastructure",
        "pillar": "MC",
    },
    {
        "id": "T8",
        "name": "Modernize water and wastewater infrastructure",
        "pillar": "MC",
    },
    # High-Performing Government (HG)
    {
        "id": "T9",
        "name": "Modernize city IT infrastructure and cybersecurity",
        "pillar": "HG",
    },
    {"id": "T10", "name": "Improve 311 service response times", "pillar": "HG"},
    {
        "id": "T11",
        "name": "Enhance data-driven decision making across departments",
        "pillar": "HG",
    },
    {
        "id": "T12",
        "name": "Recruit and retain a diverse city workforce",
        "pillar": "HG",
    },
    # Public Safety (PS)
    {"id": "T13", "name": "Expand mental health crisis response", "pillar": "PS"},
    {"id": "T14", "name": "Reduce gun violence in priority areas", "pillar": "PS"},
    {
        "id": "T15",
        "name": "Increase community-oriented policing capacity",
        "pillar": "PS",
    },
    {"id": "T16", "name": "Improve emergency response times citywide", "pillar": "PS"},
    # Community Health & Sustainability (CH)
    {"id": "T17", "name": "Achieve carbon neutrality by 2040", "pillar": "CH"},
    {"id": "T18", "name": "Expand parks and green infrastructure", "pillar": "CH"},
    {
        "id": "T19",
        "name": "Reduce health disparities in underserved communities",
        "pillar": "CH",
    },
    {
        "id": "T20",
        "name": "Strengthen climate resilience and disaster preparedness",
        "pillar": "CH",
    },
    {"id": "T21", "name": "Improve air and water quality monitoring", "pillar": "CH"},
    # Economic & Workforce Development (EW)
    {
        "id": "T22",
        "name": "Support small business growth and entrepreneurship",
        "pillar": "EW",
    },
    {
        "id": "T23",
        "name": "Expand workforce development and skills training programs",
        "pillar": "EW",
    },
    {
        "id": "T24",
        "name": "Attract and retain technology and innovation employers",
        "pillar": "EW",
    },
    {
        "id": "T25",
        "name": "Grow the creative economy and cultural sector",
        "pillar": "EW",
    },
]

# ---------------------------------------------------------------------------
# City Departments
# ---------------------------------------------------------------------------
CITY_DEPARTMENTS: List[Dict] = [
    {"code": "ATD", "name": "Austin Transportation Department", "pillars": ["MC"]},
    {"code": "APD", "name": "Austin Police Department", "pillars": ["PS"]},
    {"code": "AFD", "name": "Austin Fire Department", "pillars": ["PS"]},
    {"code": "EMS", "name": "Austin-Travis County EMS", "pillars": ["PS", "CH"]},
    {
        "code": "CTM",
        "name": "Communications & Technology Management",
        "pillars": ["HG"],
    },
    {"code": "AE", "name": "Austin Energy", "pillars": ["CH", "MC"]},
    {"code": "AWU", "name": "Austin Water", "pillars": ["CH", "MC"]},
    {"code": "PARD", "name": "Parks and Recreation Department", "pillars": ["CH"]},
    {"code": "HSD", "name": "Housing & Planning Department", "pillars": ["HH"]},
    {"code": "EDD", "name": "Economic Development Department", "pillars": ["EW"]},
    {"code": "APH", "name": "Austin Public Health", "pillars": ["CH", "PS"]},
    {"code": "OPM", "name": "Office of Performance Management", "pillars": ["HG"]},
    {"code": "FSD", "name": "Financial Services Department", "pillars": ["HG"]},
    {"code": "HRD", "name": "Human Resources Department", "pillars": ["HG"]},
    {"code": "OOS", "name": "Office of Sustainability", "pillars": ["CH"]},
]

# ---------------------------------------------------------------------------
# Peer Cities for Benchmarking
# ---------------------------------------------------------------------------
PEER_CITIES: List[Dict] = [
    {"name": "Denver", "state": "CO", "population": 713000},
    {"name": "San Antonio", "state": "TX", "population": 1472000},
    {"name": "Portland", "state": "OR", "population": 641000},
    {"name": "Seattle", "state": "WA", "population": 749000},
    {"name": "Nashville", "state": "TN", "population": 684000},
    {"name": "Charlotte", "state": "NC", "population": 897000},
    {"name": "Columbus", "state": "OH", "population": 907000},
    {"name": "San Jose", "state": "CA", "population": 1014000},
    {"name": "Fort Worth", "state": "TX", "population": 958000},
    {"name": "Phoenix", "state": "AZ", "population": 1625000},
]


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def get_relevant_priorities(pillar_id: str) -> List[Dict]:
    """Get Top 25 priorities relevant to a specific pillar.

    Args:
        pillar_id: Strategic pillar code (e.g. "CH", "HH", "MC").

    Returns:
        List of priority dicts matching the given pillar.
    """
    return [p for p in CMO_TOP_25_PRIORITIES if p["pillar"] == pillar_id]


def get_relevant_departments(pillar_id: str) -> List[Dict]:
    """Get departments related to a specific pillar.

    Args:
        pillar_id: Strategic pillar code (e.g. "CH", "HH", "MC").

    Returns:
        List of department dicts whose pillars include the given pillar_id.
    """
    return [d for d in CITY_DEPARTMENTS if pillar_id in d["pillars"]]


def get_peer_city_names() -> List[str]:
    """Get just the city names for query building.

    Returns:
        List of peer city name strings.
    """
    return [c["name"] for c in PEER_CITIES]


def format_austin_context_for_prompt(pillar_id: str) -> str:
    """Format Austin context as text for injection into research prompts.

    Builds a compact text block with the relevant CMO priorities, responsible
    departments, and peer cities formatted for LLM consumption.

    Args:
        pillar_id: Strategic pillar code (e.g. "CH", "HH", "MC").

    Returns:
        A multi-line string suitable for embedding in a research prompt.
    """
    pillar_name = STRATEGIC_PILLARS.get(pillar_id, pillar_id)

    # Priorities
    priorities = get_relevant_priorities(pillar_id)
    if priorities:
        priority_lines = ", ".join(f"{p['id']}: {p['name']}" for p in priorities)
    else:
        priority_lines = "(none for this pillar)"

    # Departments
    departments = get_relevant_departments(pillar_id)
    if departments:
        dept_lines = ", ".join(f"{d['code']} ({d['name']})" for d in departments)
    else:
        dept_lines = "(none for this pillar)"

    # Peer cities
    peer_names = get_peer_city_names()
    peer_line = ", ".join(peer_names)

    return (
        f"AUSTIN STRATEGIC CONTEXT (Pillar: {pillar_name}):\n"
        f"Relevant CMO Priorities: {priority_lines}\n"
        f"Responsible Departments: {dept_lines}\n"
        f"Peer Cities for Comparison: {peer_line}"
    )
