"""
Taxonomy constants and conversion utilities.

Shared definitions for pillars, stages, goals, and horizons used across
discovery, scanning, and classification services.
"""

from typing import Optional


# ============================================================================
# Strategic Pillars
# ============================================================================

# Pillar code to human-readable name
PILLAR_NAMES = {
    "CH": "Community Health",
    "MC": "Mobility Infrastructure",
    "HS": "Housing Stability",
    "EC": "Economic Development",
    "ES": "Environmental Sustainability",
    "CE": "Cultural Entertainment",
}

# AI pillar codes -> Database pillar IDs mapping
# AI may return different codes than what's in the database
PILLAR_CODE_MAP = {
    "CH": "CH",  # Community Health -> Community Health
    "MC": "MC",  # Mobility & Connectivity -> Mobility & Connectivity
    "EW": "EC",  # Economic & Workforce -> Economic Development
    "HG": "EC",  # High-Performing Government -> Economic Development (closest match)
    "HH": "HS",  # Homelessness & Housing -> Housing & Economic Stability
    "PS": "CH",  # Public Safety -> Community Health (closest match)
    "ES": "ES",  # Environmental Sustainability -> Environmental Sustainability
    "CE": "CE",  # Cultural & Entertainment -> Cultural & Entertainment
}


def convert_pillar_id(ai_pillar: str) -> Optional[str]:
    """
    Convert AI pillar code to database pillar ID.
    
    AI may return codes that don't exist in the database.
    This function maps them to the closest valid pillar.
    
    Args:
        ai_pillar: Pillar code from AI classification
        
    Returns:
        Database-compatible pillar ID, or None if input is empty
    """
    if not ai_pillar:
        return None
    return PILLAR_CODE_MAP.get(ai_pillar, ai_pillar)


# ============================================================================
# Maturity Stages
# ============================================================================

# Stage number to database stage_id mapping
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

# Stage ID to number (reverse mapping)
STAGE_ID_TO_NUMBER = {v: k for k, v in STAGE_NUMBER_TO_ID.items()}

# Stage names for display
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
    
    Also maps pillar codes in the goal to database-compatible codes.
    
    Args:
        ai_goal: Goal ID from AI classification (e.g., "CH.1")
        
    Returns:
        Database-compatible goal ID (e.g., "CH-01")
    """
    if not ai_goal or '.' not in ai_goal:
        return ai_goal
    
    parts = ai_goal.split('.')
    if len(parts) != 2:
        return ai_goal
    
    pillar = parts[0]
    try:
        number = int(parts[1])
        # Also convert the pillar code in the goal
        mapped_pillar = PILLAR_CODE_MAP.get(pillar, pillar)
        return f"{mapped_pillar}-{number:02d}"
    except ValueError:
        return ai_goal


# ============================================================================
# Horizons
# ============================================================================

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
