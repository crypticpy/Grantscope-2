"""
Taxonomy constants and conversion utilities.

Single source of truth for pillars, stages, goals, and horizons used across
discovery, scanning, classification, export, and presentation services.

Canonical pillar codes: CH, EW, HG, HH, MC, PS
"""

from typing import Any, Dict, List, Optional, Set


# ============================================================================
# Strategic Pillars
# ============================================================================

# Pillar code to human-readable name
# These are the 6 canonical AI pillar codes from Austin's strategic framework
PILLAR_NAMES: Dict[str, str] = {
    "CH": "Community Health & Sustainability",
    "EW": "Economic & Workforce Development",
    "HG": "High-Performing Government",
    "HH": "Homelessness & Housing",
    "MC": "Mobility & Critical Infrastructure",
    "PS": "Public Safety",
}

# Valid pillar codes (set for fast membership checks)
VALID_PILLAR_CODES: Set[str] = set(PILLAR_NAMES.keys())

# Alias used by signal_agent_service and others
VALID_PILLAR_IDS: Set[str] = VALID_PILLAR_CODES

# Short descriptions for each pillar
PILLAR_DESCRIPTIONS: Dict[str, str] = {
    "CH": "Public health, parks, climate, preparedness, and animal services",
    "EW": "Economic mobility, small business support, and creative economy",
    "HG": "Fiscal integrity, technology, workforce, and community engagement",
    "HH": "Complete communities, affordable housing, and homelessness reduction",
    "MC": "Transportation, transit, utilities, and facility management",
    "PS": "Community relationships, fair delivery, and disaster preparedness",
}

# Icons for each pillar (used in presentations and exports)
PILLAR_ICONS: Dict[str, str] = {
    "CH": "\u2665",  # ♥
    "EW": "\U0001f4bc",  # briefcase emoji
    "HG": "\U0001f3db",  # classical building emoji
    "HH": "\U0001f3e0",  # house emoji
    "MC": "\U0001f697",  # car emoji
    "PS": "\U0001f6e1",  # shield emoji
}

# Pillar colors for PDF exports and frontend (matches frontend badge colors)
PILLAR_COLORS: Dict[str, Dict[str, str]] = {
    "CH": {
        "name": "Community Health & Sustainability",
        "color": "#22c55e",
        "bg": "#dcfce7",
        "icon": "\u2665",
    },
    "EW": {
        "name": "Economic & Workforce Development",
        "color": "#3b82f6",
        "bg": "#dbeafe",
        "icon": "\U0001f4bc",
    },
    "HG": {
        "name": "High-Performing Government",
        "color": "#6366f1",
        "bg": "#e0e7ff",
        "icon": "\U0001f3db",
    },
    "HH": {
        "name": "Homelessness & Housing",
        "color": "#ec4899",
        "bg": "#fce7f3",
        "icon": "\U0001f3e0",
    },
    "MC": {
        "name": "Mobility & Critical Infrastructure",
        "color": "#f59e0b",
        "bg": "#fef3c7",
        "icon": "\U0001f697",
    },
    "PS": {
        "name": "Public Safety",
        "color": "#ef4444",
        "bg": "#fee2e2",
        "icon": "\U0001f6e1",
    },
}

# Comprehensive pillar definitions including focus areas and search terms.
# Used by query_generator (search_terms, focus_areas) and gamma_service
# (icon, description, focus_areas) for grant discovery and presentations.
PILLAR_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "CH": {
        "name": "Community Health & Sustainability",
        "icon": "\U0001f3e5",  # hospital emoji
        "description": "Grant funding for public health, environmental sustainability, and community wellness",
        "focus_areas": [
            "federal grants public health city government",
            "EPA environmental justice grants municipal",
            "HHS community health grants local government",
            "CDC public health preparedness grants city",
            "SAMHSA behavioral health grants municipal",
            "NIH community health research grants",
            "EPA clean water grants municipality",
            "DOE energy efficiency grants local government",
            "USDA community facilities grants",
            "parks and recreation federal grants city",
        ],
        "search_terms": [
            "EPA environmental justice grant NOFO",
            "HHS community health center grants",
            "CDC preparedness funding local government",
            "SAMHSA substance abuse prevention grants",
            "FEMA hazard mitigation grants city",
            "DOE weatherization assistance program grants",
            "state health department grants Texas city",
        ],
        "keywords": [
            "public health grants",
            "environmental grants",
            "sustainability funding",
            "climate resilience grants",
            "community wellness grants",
            "parks grants",
            "clean energy grants",
        ],
        "goal_alignment": "Health equity, preventive health, and environmental resilience funding",
    },
    "EW": {
        "name": "Economic & Workforce Development",
        "icon": "\U0001f4c8",  # chart increasing emoji
        "description": "Grant funding for economic mobility, workforce training, and small business support",
        "focus_areas": [
            "EDA economic development grants city government",
            "SBA small business grants municipal",
            "DOL workforce development grants local government",
            "EDA public works grants infrastructure",
            "USDA rural development grants",
            "SBA community advantage grants",
            "DOL apprenticeship grants city",
            "EDA Build Back Better regional challenge",
            "workforce innovation opportunity act grants",
            "economic development administration grants NOFO",
        ],
        "search_terms": [
            "EDA economic development grant announcement",
            "DOL workforce innovation opportunity act funding",
            "SBA small business grant program NOFO",
            "federal workforce development grants city",
            "economic development grants local government",
            "CDBG economic development funding",
        ],
        "keywords": [
            "economic development grants",
            "workforce grants",
            "small business grants",
            "job training grants",
            "WIOA funding",
            "EDA grants",
        ],
        "goal_alignment": "Economic mobility, workforce readiness, and business support funding",
    },
    "HG": {
        "name": "High-Performing Government",
        "icon": "\U0001f3db\ufe0f",  # classical building emoji
        "description": "Grant funding for technology modernization, cybersecurity, and government operations",
        "focus_areas": [
            "federal technology modernization grants city government",
            "GSA smart government grants municipal",
            "NIST cybersecurity grants local government",
            "State and Local Cybersecurity Grant Program",
            "Technology Modernization Fund federal",
            "NSF smart and connected communities grants",
            "DHS cybersecurity grants city government",
            "digital equity grants NTIA",
            "broadband infrastructure grants municipal",
            "E-Rate program grants government",
        ],
        "search_terms": [
            "NIST cybersecurity grant NOFO city government",
            "NSF smart communities grants municipal",
            "NTIA digital equity grants local government",
            "DHS state local cybersecurity grant program",
            "federal IT modernization grants city",
            "broadband equity access deployment grants",
            "GSA technology grants government",
        ],
        "keywords": [
            "technology grants",
            "cybersecurity grants",
            "digital equity grants",
            "broadband grants",
            "IT modernization grants",
            "smart government grants",
        ],
        "goal_alignment": "Government modernization, cybersecurity, and digital equity funding",
    },
    "HH": {
        "name": "Homelessness & Housing",
        "icon": "\U0001f3e0",  # house emoji
        "description": "Grant funding for affordable housing, homelessness prevention, and community development",
        "focus_areas": [
            "HUD housing grants city government",
            "CDBG community development block grants",
            "HUD homeless assistance grants continuum of care",
            "HOME Investment Partnerships Program grants",
            "Emergency Solutions Grants ESG",
            "HUD fair housing grants",
            "Low-Income Housing Tax Credit programs",
            "HUD Section 811 supportive housing grants",
            "HUD Housing Counseling grants",
            "USDA housing preservation grants",
        ],
        "search_terms": [
            "HUD NOFO housing grants city government",
            "continuum of care homeless assistance grants",
            "CDBG entitlement grants municipal",
            "HOME program funding local government",
            "Emergency Solutions Grant NOFO",
            "HUD fair housing initiatives program",
            "affordable housing grants Texas city",
        ],
        "keywords": [
            "HUD grants",
            "housing grants",
            "CDBG funding",
            "homeless assistance grants",
            "affordable housing funding",
            "community development grants",
        ],
        "goal_alignment": "Housing affordability, homelessness reduction, and community development funding",
    },
    "MC": {
        "name": "Mobility & Critical Infrastructure",
        "icon": "\U0001f687",  # metro emoji
        "description": "Grant funding for transportation, transit, utilities, and infrastructure",
        "focus_areas": [
            "DOT transportation grants city government",
            "FEMA infrastructure grants municipal",
            "FTA transit grants local government",
            "RAISE discretionary grants transportation",
            "INFRA grants infrastructure federal",
            "Safe Streets and Roads for All grants",
            "FTA bus and bus facilities grants",
            "EPA water infrastructure grants municipal",
            "DOE grid resilience grants city",
            "FEMA building resilient infrastructure grants",
        ],
        "search_terms": [
            "DOT RAISE grant NOFO city government",
            "FTA transit capital grants municipal",
            "Safe Streets for All grant application",
            "FEMA BRIC grants local government",
            "EPA drinking water state revolving fund",
            "DOE grid resilience innovation grants",
            "federal infrastructure grants Texas city",
        ],
        "keywords": [
            "transportation grants",
            "transit grants",
            "infrastructure grants",
            "RAISE grants",
            "FEMA grants",
            "water infrastructure grants",
            "DOT grants",
        ],
        "goal_alignment": "Transportation equity, infrastructure resilience, and utility modernization funding",
    },
    "PS": {
        "name": "Public Safety",
        "icon": "\U0001f6e1\ufe0f",  # shield emoji
        "description": "Grant funding for law enforcement, fire, EMS, and emergency management",
        "focus_areas": [
            "DOJ public safety grants city government",
            "FEMA emergency management grants municipal",
            "COPS Office grants local government",
            "Byrne JAG grants justice assistance",
            "FEMA Staffing for Adequate Fire and Emergency Response",
            "FEMA Assistance to Firefighters grants",
            "DOJ Office of Violence Against Women grants",
            "BJA community violence intervention grants",
            "FEMA Homeland Security Grant Program",
            "DOJ smart policing initiative grants",
        ],
        "search_terms": [
            "DOJ COPS hiring program grant NOFO",
            "FEMA SAFER grants fire department",
            "Byrne JAG grant application local government",
            "FEMA AFG grants city fire department",
            "DOJ community violence intervention grants",
            "BJA justice assistance grants city",
            "federal public safety grants Texas city",
        ],
        "keywords": [
            "public safety grants",
            "COPS grants",
            "FEMA grants",
            "DOJ grants",
            "fire department grants",
            "emergency management grants",
            "justice assistance grants",
        ],
        "goal_alignment": "Community safety, emergency preparedness, and justice funding",
    },
}

# AI pillar codes -> Database pillar IDs mapping
# All 6 canonical pillar codes pass through natively (no lossy conversion).
# The database pillars table has been updated to match the AI taxonomy.
PILLAR_CODE_MAP: Dict[str, str] = {
    "CH": "CH",  # Community Health & Sustainability
    "EW": "EW",  # Economic & Workforce Development
    "HG": "HG",  # High-Performing Government
    "HH": "HH",  # Homelessness & Housing
    "MC": "MC",  # Mobility & Critical Infrastructure
    "PS": "PS",  # Public Safety
}


def convert_pillar_id(ai_pillar: str) -> Optional[str]:
    """
    Convert AI pillar code to database pillar ID.

    All 6 canonical pillar codes (CH, EW, HG, HH, MC, PS) pass through
    natively. Unknown codes are returned as-is for forward compatibility.

    Args:
        ai_pillar: Pillar code from AI classification

    Returns:
        Database-compatible pillar ID, or None if input is empty
    """
    return PILLAR_CODE_MAP.get(ai_pillar, ai_pillar) if ai_pillar else None


# ============================================================================
# Maturity Stages  [DEPRECATED - use PIPELINE_STATUSES instead]
# ============================================================================

# DEPRECATED: Use PIPELINE_STATUSES for new code. Kept for backward compatibility.
STAGE_NUMBER_TO_ID = {
    1: "1_concept",
    2: "2_exploring",
    3: "3_pilot",
    4: "4_proof",
    5: "5_implementing",
    6: "6_scaling",
    7: "7_mature",
    8: "8_declining",
}

# DEPRECATED: Use PIPELINE_STATUSES for new code. Kept for backward compatibility.
STAGE_ID_TO_NUMBER = {v: k for k, v in STAGE_NUMBER_TO_ID.items()}

# DEPRECATED: Use PIPELINE_STATUSES[status]["label"] for display names.
STAGE_NAMES = {
    1: "Concept",
    2: "Exploring",
    3: "Pilot",
    4: "Proof of Concept",
    5: "Implementing",
    6: "Scaling",
    7: "Mature",
    8: "Declining",
}


def convert_stage_to_id(stage_number: int) -> str:
    """
    DEPRECATED: Use pipeline_status directly instead.

    Convert stage number to database stage_id.

    Args:
        stage_number: Stage number (1-8)

    Returns:
        Database stage_id string (e.g., "4_proof")
    """
    return STAGE_NUMBER_TO_ID.get(stage_number, "4_proof")


def extract_stage_number(stage_id: str) -> Optional[int]:
    """
    Extract stage number from stage_id.

    Args:
        stage_id: Database stage_id (e.g., "4_proof" or "4")

    Returns:
        Stage number (1-8) or None if invalid
    """
    if not stage_id:
        return None

    # Handle both "4_proof" and "4" formats
    stage_str = stage_id.split("_")[0] if "_" in stage_id else stage_id

    try:
        return int(stage_str)
    except ValueError:
        return None


# ============================================================================
# Goals
# ============================================================================


def convert_goal_id(ai_goal: str) -> str:
    """
    Convert AI goal format to database format.

    AI returns: "CH.1", "MC.3", "HG.2"
    Database expects: "CH-01", "MC-03", "HG-02"

    Pillar codes in the goal prefix pass through natively.

    Args:
        ai_goal: Goal ID from AI classification (e.g., "CH.1")

    Returns:
        Database-compatible goal ID (e.g., "CH-01")
    """
    if not ai_goal or "." not in ai_goal:
        return ai_goal

    parts = ai_goal.split(".")
    if len(parts) != 2:
        return ai_goal

    pillar = parts[0]
    try:
        number = int(parts[1])
        # Pillar code passes through natively (no lossy conversion)
        mapped_pillar = PILLAR_CODE_MAP.get(pillar, pillar)
        return f"{mapped_pillar}-{number:02d}"
    except ValueError:
        return ai_goal


# ============================================================================
# Horizons  [DEPRECATED - use PIPELINE_STATUSES / PIPELINE_PHASES instead]
# ============================================================================

# DEPRECATED: Use PIPELINE_STATUSES for new code. Kept for backward compatibility.
HORIZON_DEFINITIONS = {
    "H1": {
        "name": "Mainstream",
        "timeframe": "0-3 years",
        "description": "Technologies and trends already in widespread adoption",
    },
    "H2": {
        "name": "Transitional",
        "timeframe": "3-7 years",
        "description": "Emerging technologies being piloted and evaluated",
    },
    "H3": {
        "name": "Transformative",
        "timeframe": "7-15+ years",
        "description": "Experimental and future-oriented concepts",
    },
}

VALID_HORIZONS = {"H1", "H2", "H3", "ALL"}

# ============================================================================
# Grant Categories (Phase 1: Grant Platform Transformation)
# ============================================================================

# 8 grant funding categories — these will replace pillars in the grant context
# but pillars remain for backward compatibility with existing classification
GRANT_CATEGORIES: Dict[str, Dict[str, str]] = {
    "HS": {
        "name": "Health & Social Services",
        "description": "Public health, behavioral health, social services, youth development",
        "color": "#22c55e",
        "icon": "heart-pulse",
    },
    "PS": {
        "name": "Public Safety",
        "description": "Law enforcement, fire, EMS, emergency management, justice",
        "color": "#ef4444",
        "icon": "shield",
    },
    "HD": {
        "name": "Housing & Development",
        "description": "Affordable housing, homelessness, community development, planning",
        "color": "#ec4899",
        "icon": "home",
    },
    "IN": {
        "name": "Infrastructure",
        "description": "Transportation, water, energy, facilities, telecommunications",
        "color": "#f59e0b",
        "icon": "building-2",
    },
    "EN": {
        "name": "Environment",
        "description": "Climate, sustainability, parks, conservation, resilience",
        "color": "#10b981",
        "icon": "leaf",
    },
    "CE": {
        "name": "Culture & Education",
        "description": "Libraries, museums, arts, education, workforce development",
        "color": "#8b5cf6",
        "icon": "graduation-cap",
    },
    "TG": {
        "name": "Technology & Government",
        "description": "IT modernization, data, cybersecurity, innovation, e-government",
        "color": "#3b82f6",
        "icon": "cpu",
    },
    "EQ": {
        "name": "Equity & Engagement",
        "description": "Civil rights, accessibility, language access, civic participation",
        "color": "#f97316",
        "icon": "users",
    },
}

VALID_GRANT_CATEGORY_CODES: Set[str] = set(GRANT_CATEGORIES.keys())

# ============================================================================
# Grant Pipeline Statuses
# ============================================================================

# Full set of pipeline statuses for the grant kanban board
# Old statuses (inbox, screening, research, brief, watching, archived) remain valid
# for backward compatibility
PIPELINE_STATUSES: Dict[str, Dict[str, str]] = {
    "discovered": {
        "label": "Discovered",
        "description": "New grant opportunity identified by system",
        "color": "#3b82f6",
    },
    "evaluating": {
        "label": "Evaluating",
        "description": "Under review for fit and feasibility",
        "color": "#3b82f6",
    },
    "applying": {
        "label": "Applying",
        "description": "Actively preparing application",
        "color": "#f59e0b",
    },
    "submitted": {
        "label": "Submitted",
        "description": "Application submitted, awaiting decision",
        "color": "#8b5cf6",
    },
    "awarded": {
        "label": "Awarded",
        "description": "Grant awarded",
        "color": "#22c55e",
    },
    "active": {
        "label": "Active",
        "description": "Grant in performance period, drawing funds",
        "color": "#10b981",
    },
    "closed": {
        "label": "Closed",
        "description": "Grant completed or opportunity passed",
        "color": "#6b7280",
    },
    "declined": {
        "label": "Declined",
        "description": "Application not selected or opportunity passed",
        "color": "#ef4444",
    },
    "expired": {
        "label": "Expired",
        "description": "Deadline passed without application",
        "color": "#6b7280",
    },
}

VALID_PIPELINE_STATUSES: Set[str] = set(PIPELINE_STATUSES.keys())

# Combined set: old kanban statuses + new pipeline statuses (for validation)
ALL_WORKSTREAM_CARD_STATUSES: Set[str] = {
    # Legacy statuses (keep for backward compat)
    "inbox",
    "screening",
    "research",
    "brief",
    "watching",
    "archived",
    # New grant pipeline statuses
    "discovered",
    "evaluating",
    "applying",
    "submitted",
    "awarded",
    "active",
    "closed",
    "declined",
    "expired",
}

# Pipeline phases -- derived grouping of statuses
PIPELINE_PHASES: Dict[str, List[str]] = {
    "pipeline": ["discovered", "evaluating"],
    "pursuing": ["applying", "submitted"],
    "active": ["awarded", "active"],
    "archived": ["closed", "declined", "expired"],
}

PIPELINE_PHASE_DISPLAY: Dict[str, Dict[str, str]] = {
    "pipeline": {
        "label": "Pipeline",
        "color": "#3b82f6",
        "description": "Opportunities being tracked",
    },
    "pursuing": {
        "label": "Pursuing",
        "color": "#f59e0b",
        "description": "Actively being applied for",
    },
    "active": {
        "label": "Active",
        "color": "#22c55e",
        "description": "Funded grants in performance",
    },
    "archived": {
        "label": "Archived",
        "color": "#6b7280",
        "description": "Completed, declined, or expired",
    },
}


def get_pipeline_phase(status: str) -> str:
    """Return the pipeline phase for a given status."""
    for phase, statuses in PIPELINE_PHASES.items():
        if status in statuses:
            return phase
    return "pipeline"  # default


# ============================================================================
# Deadline Urgency Tiers
# ============================================================================

DEADLINE_TIERS: Dict[str, Dict[str, Any]] = {
    "urgent": {
        "label": "Urgent",
        "days_remaining": 14,
        "color": "#ef4444",
        "description": "Deadline within 2 weeks",
    },
    "approaching": {
        "label": "Approaching",
        "days_remaining": 45,
        "color": "#f59e0b",
        "description": "Deadline within 45 days",
    },
    "planning": {
        "label": "Planning",
        "days_remaining": None,  # > 45 days or no deadline
        "color": "#22c55e",
        "description": "Deadline > 45 days out or no deadline set",
    },
}

# ============================================================================
# Grant Types
# ============================================================================

GRANT_TYPES: Dict[str, str] = {
    "federal": "Federal Grant",
    "state": "State Grant",
    "foundation": "Foundation/Private Grant",
    "local": "Local/Regional Grant",
    "other": "Other Funding Source",
}

VALID_GRANT_TYPES: Set[str] = set(GRANT_TYPES.keys())

# ============================================================================
# Alignment Score Factors
# ============================================================================

ALIGNMENT_SCORE_FACTORS: Dict[str, Dict[str, str]] = {
    "fit": {
        "label": "Program Fit",
        "description": "How well the grant aligns with program goals and department mission",
        "weight": "0.25",
    },
    "amount": {
        "label": "Funding Amount",
        "description": "Whether the funding range matches program budget needs",
        "weight": "0.15",
    },
    "competition": {
        "label": "Competition Level",
        "description": "Estimated competitiveness based on past awards and applicant pool",
        "weight": "0.15",
    },
    "readiness": {
        "label": "Readiness",
        "description": "Department's capacity to apply and manage the grant",
        "weight": "0.15",
    },
    "urgency": {
        "label": "Deadline Urgency",
        "description": "Time remaining before application deadline",
        "weight": "0.15",
    },
    "probability": {
        "label": "Success Probability",
        "description": "Overall estimated probability of award based on all factors",
        "weight": "0.15",
    },
}

# ============================================================================
# City of Austin Departments (reference list)
# ============================================================================

# Maps department abbreviation to full name and associated grant categories
DEPARTMENT_LIST: Dict[str, Dict[str, Any]] = {
    "APH": {"name": "Austin Public Health", "categories": ["HS"]},
    "APD": {"name": "Austin Police Department", "categories": ["PS"]},
    "AFD": {"name": "Austin Fire Department", "categories": ["PS"]},
    "EMS": {"name": "Austin-Travis County EMS", "categories": ["PS"]},
    "HSEM": {"name": "Homeland Security & Emergency Management", "categories": ["PS"]},
    "AWU": {"name": "Austin Water", "categories": ["IN", "EN"]},
    "ATD": {"name": "Austin Transportation", "categories": ["IN"]},
    "AE": {"name": "Austin Energy", "categories": ["IN", "EN"]},
    "ARR": {"name": "Austin Resource Recovery", "categories": ["EN", "IN"]},
    "PARD": {"name": "Parks & Recreation", "categories": ["EN", "CE"]},
    "APL": {"name": "Austin Public Library", "categories": ["CE"]},
    "EDD": {"name": "Economic Development", "categories": ["CE", "HD"]},
    "NHCD": {"name": "Housing & Planning", "categories": ["HD"]},
    "DSD": {"name": "Development Services", "categories": ["HD", "IN"]},
    "WPD": {"name": "Watershed Protection", "categories": ["EN"]},
    "CTM": {"name": "Communications & Technology Management", "categories": ["TG"]},
    "OOI": {"name": "Office of Innovation", "categories": ["TG"]},
    "FSD": {"name": "Financial Services", "categories": ["TG"]},
    "HRD": {"name": "Human Resources", "categories": ["TG"]},
    "LAW": {"name": "Law Department", "categories": ["TG"]},
    "CMO": {"name": "City Manager Office", "categories": ["TG", "EQ"]},
    "OPM": {"name": "Office of Performance Management", "categories": ["TG"]},
    "CCC": {"name": "Combined Communications Center (911)", "categories": ["PS", "TG"]},
    "BSD": {"name": "Building Services", "categories": ["IN"]},
    "FMD": {"name": "Fleet Mobility Services", "categories": ["IN"]},
    "PWD": {"name": "Public Works", "categories": ["IN"]},
    "AAR": {"name": "Aviation", "categories": ["IN"]},
    "OEQ": {"name": "Office of Equity", "categories": ["EQ"]},
    "OII": {"name": "Office of Immigrant Integration", "categories": ["EQ"]},
    "CRA": {"name": "Civil Rights Office", "categories": ["EQ"]},
    "ODA": {"name": "Office of Disability Affairs", "categories": ["EQ", "HS"]},
    "CPIO": {"name": "Communications & Public Information", "categories": ["TG"]},
    "COS": {"name": "Office of Sustainability", "categories": ["EN"]},
    "CC": {"name": "Austin Convention Center", "categories": ["CE"]},
    "MOS": {"name": "Municipal Court", "categories": ["PS"]},
    "ACD": {"name": "Animal Services", "categories": ["HS"]},
    "COA311": {"name": "311 / Austin 3-1-1", "categories": ["TG", "EQ"]},
    "OSPB": {"name": "Office of Small & Minority Business", "categories": ["EQ", "CE"]},
    "CPTD": {"name": "Capital Planning & Transportation", "categories": ["IN"]},
    "OCOS": {"name": "Office of the City Clerk", "categories": ["TG"]},
    "IAO": {"name": "Internal Audit Office", "categories": ["TG"]},
    "FPD": {"name": "Financial Policy Division", "categories": ["TG"]},
    "CRO": {"name": "Community Registry Office", "categories": ["EQ"]},
}

VALID_DEPARTMENT_CODES: Set[str] = set(DEPARTMENT_LIST.keys())
