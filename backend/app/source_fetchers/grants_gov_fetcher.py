"""
Grants.gov source fetcher for federal grant opportunities.

This module fetches grant opportunities from the Grants.gov public API
(POST https://api.grants.gov/v1/api/search2). No authentication is required.
Results are filtered for relevance to City of Austin municipal operations and
converted to RawSource objects for the discovery pipeline.

Features:
- Search Grants.gov by keyword, status, and funding category
- Pagination support (API returns max 25 per page)
- Austin-relevance filtering by CFDA prefix, agency, and keywords
- Graceful error handling with retry logic
- Structured grant metadata in RawSource content field

Usage:
    from backend.app.source_fetchers.grants_gov_fetcher import (
        fetch_grants_gov_opportunities,
        fetch_and_convert_opportunities,
    )

    # Raw opportunity objects
    result = await fetch_grants_gov_opportunities(
        topics=["municipal infrastructure", "public health"],
        max_results=50,
    )

    # Pipeline-ready RawSource objects
    sources, source_type = await fetch_and_convert_opportunities(
        topics=["affordable housing"],
        max_results=25,
    )
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import aiohttp

if TYPE_CHECKING:
    from ..research_service import RawSource

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

GRANTS_GOV_API_URL = "https://api.grants.gov/v1/api/search2"

# Default timeout for HTTP requests (seconds)
DEFAULT_TIMEOUT = 30

# Grants.gov returns a maximum of 25 results per page
MAX_RESULTS_PER_PAGE = 25

# User agent consistent with other GrantScope fetchers
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 "
    "GrantScope-Research-Bot/1.0"
)

# Maximum retry attempts for failed API requests
MAX_RETRIES = 3

# Base delay between retries in seconds (doubles each attempt)
RETRY_BASE_DELAY = 1.0

# Grants.gov opportunity detail URL template
OPPORTUNITY_URL_TEMPLATE = "https://www.grants.gov/search-results-detail/{id}"

# Mapping of Grants.gov funding category codes to GrantScope grant categories.
# Grants.gov codes: https://www.grants.gov/web/grants/search-grants.html
AUSTIN_RELEVANT_CATEGORIES: Dict[str, str] = {
    "RA": "HS",  # Recovery Act -> Health & Social Services
    "AG": "EN",  # Agriculture -> Environment
    "AR": "CE",  # Arts -> Culture & Education
    "BC": "CE",  # Business & Commerce -> Culture & Education
    "CD": "HD",  # Community Development -> Housing & Development
    "CP": "EQ",  # Consumer Protection -> Equity & Engagement
    "DPR": "PS",  # Disaster Prevention & Relief -> Public Safety
    "ED": "CE",  # Education -> Culture & Education
    "ELT": "IN",  # Employment, Labor, Training -> Infrastructure
    "EN": "EN",  # Energy -> Environment
    "ENV": "EN",  # Environment -> Environment
    "FN": "TG",  # Food & Nutrition -> Technology & Government
    "HL": "HS",  # Health -> Health & Social Services
    "HO": "HD",  # Housing -> Housing & Development
    "HU": "EQ",  # Humanities -> Equity & Engagement
    "IS": "HS",  # Income Security & Social Services -> Health & Social Services
    "ISS": "HS",  # Income Security & Social Services -> Health & Social Services
    "LJL": "PS",  # Law, Justice, Legal Services -> Public Safety
    "NR": "EN",  # Natural Resources -> Environment
    "OZ": "TG",  # Opportunity Zone Benefits -> Technology & Government
    "RD": "IN",  # Regional Development -> Infrastructure
    "ST": "TG",  # Science & Technology -> Technology & Government
    "T": "IN",  # Transportation -> Infrastructure
    "ACA": "HS",  # Affordable Care Act -> Health & Social Services
    "O": "TG",  # Other -> Technology & Government
}

# CFDA number prefixes for programs relevant to municipal government.
# Format: first two digits of CFDA number -> federal agency.
RELEVANT_CFDA_PREFIXES: Dict[str, str] = {
    "14": "HUD",  # Housing and Urban Development
    "15": "DOI",  # Department of the Interior
    "16": "DOJ",  # Department of Justice
    "17": "DOL",  # Department of Labor
    "20": "DOT",  # Department of Transportation
    "66": "EPA",  # Environmental Protection Agency
    "81": "DOE",  # Department of Energy
    "84": "ED",  # Department of Education
    "93": "HHS",  # Health and Human Services
    "97": "FEMA",  # Federal Emergency Management Agency (DHS)
    "10": "USDA",  # Department of Agriculture
    "11": "DOC",  # Department of Commerce
}

# Federal agency codes that commonly fund municipal programs
RELEVANT_AGENCY_CODES: set = {
    "HUD",
    "DOT",
    "EPA",
    "FEMA",
    "DHS",
    "DOE",
    "HHS",
    "DOJ",
    "ED",
    "USDA",
    "DOC",
    "DOL",
    "DOI",
    "NSF",
    "SBA",
    # Sub-agency variations used in Grants.gov
    "HUD-CPD",
    "HUD-PIH",
    "EPA-OW",
    "EPA-OAR",
    "DOT-FTA",
    "DOT-FHWA",
    "DOT-NHTSA",
    "HHS-ACF",
    "HHS-CDC",
    "HHS-SAMHSA",
    "HHS-HRSA",
    "DOJ-OJP",
    "DOJ-COPS",
    "ED-OESE",
    "DHS-FEMA",
    "USDA-RD",
}

# Keywords that indicate an opportunity is relevant to city/municipal government
MUNICIPAL_RELEVANCE_KEYWORDS: set = {
    "municipal",
    "city",
    "local government",
    "urban",
    "community",
    "public health",
    "transportation",
    "transit",
    "infrastructure",
    "affordable housing",
    "homelessness",
    "public safety",
    "emergency management",
    "water",
    "wastewater",
    "stormwater",
    "broadband",
    "climate",
    "resilience",
    "sustainability",
    "workforce development",
    "economic development",
    "public works",
    "parks",
    "recreation",
    "library",
    "fire department",
    "police",
    "EMS",
    "911",
    "smart city",
    "civic",
    "equity",
    "accessibility",
    "brownfield",
    "energy efficiency",
    "renewable energy",
    "disaster preparedness",
    "flood",
    "hazard mitigation",
    "community development block grant",
    "CDBG",
    "metropolitan",
    "county",
    "tribe",
    "territory",
    "state and local",
    "unit of government",
}


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class GrantsGovOpportunity:
    """Structured data from a single Grants.gov API result."""

    id: str
    title: str
    agency: str
    description: str
    open_date: Optional[datetime] = None
    close_date: Optional[datetime] = None
    close_date_explanation: Optional[str] = None
    cfda_numbers: List[str] = field(default_factory=list)
    estimated_funding: Optional[int] = None
    award_floor: Optional[int] = None
    award_ceiling: Optional[int] = None
    cost_sharing: bool = False
    category: Optional[str] = None
    opportunity_category: Optional[str] = None
    funding_categories: List[str] = field(default_factory=list)
    opportunity_number: Optional[str] = None
    agency_code: Optional[str] = None
    expected_awards: Optional[int] = None
    opportunity_url: str = ""
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GrantsGovFetchResult:
    """Result of a Grants.gov fetch operation."""

    opportunities: List[GrantsGovOpportunity]
    total_results: int
    errors: List[str]


# ============================================================================
# Date Parsing
# ============================================================================


def _parse_grants_gov_date(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parse a date string from the Grants.gov API.

    Grants.gov returns dates in MM/dd/yyyy format. Some responses may
    include timestamps or use alternate separators.

    Args:
        date_str: Date string from API (e.g., "02/15/2026")

    Returns:
        datetime object or None if parsing fails
    """
    if not date_str:
        return None

    for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d", "%m/%d/%Y %H:%M:%S"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue

    logger.debug(f"Could not parse Grants.gov date: {date_str}")
    return None


# ============================================================================
# Opportunity Parsing
# ============================================================================


def _parse_opportunity(raw: Dict[str, Any]) -> GrantsGovOpportunity:
    """
    Parse a single opportunity from the Grants.gov API response.

    Args:
        raw: A single item from the oppHits array

    Returns:
        GrantsGovOpportunity with all available fields populated
    """
    opp_id = str(raw.get("id", ""))

    # Parse CFDA list
    cfda_list = raw.get("cfdaList", []) or []
    if isinstance(cfda_list, str):
        cfda_list = [c.strip() for c in cfda_list.split(",") if c.strip()]

    # Parse funding categories
    funding_cats_raw = raw.get("fundingCategories", "") or ""
    if isinstance(funding_cats_raw, str):
        funding_categories = [
            c.strip() for c in funding_cats_raw.split("|") if c.strip()
        ]
    elif isinstance(funding_cats_raw, list):
        funding_categories = funding_cats_raw
    else:
        funding_categories = []

    # Parse numeric funding fields safely
    def _safe_int(val: Any) -> Optional[int]:
        if val is None:
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            return None

    return GrantsGovOpportunity(
        id=opp_id,
        title=raw.get("title", "Untitled Opportunity"),
        agency=raw.get("agency", raw.get("agencyName", "Unknown Agency")),
        description=raw.get("description", ""),
        open_date=_parse_grants_gov_date(raw.get("openDate")),
        close_date=_parse_grants_gov_date(raw.get("closeDate")),
        close_date_explanation=raw.get("closeDateExplanation"),
        cfda_numbers=cfda_list,
        estimated_funding=_safe_int(raw.get("estimatedFunding")),
        award_floor=_safe_int(raw.get("awardFloor")),
        award_ceiling=_safe_int(raw.get("awardCeiling")),
        cost_sharing=bool(raw.get("costSharing", False)),
        category=raw.get("category"),
        opportunity_category=raw.get("opportunityCategory"),
        funding_categories=funding_categories,
        opportunity_number=raw.get("number", raw.get("opportunityNumber")),
        agency_code=raw.get("agencyCode"),
        expected_awards=_safe_int(raw.get("expectedNumberOfAwards")),
        opportunity_url=OPPORTUNITY_URL_TEMPLATE.format(id=opp_id),
        raw_data=raw,
    )


# ============================================================================
# Austin Relevance Filter
# ============================================================================


def _is_austin_relevant(opp: GrantsGovOpportunity) -> bool:
    """
    Determine if a Grants.gov opportunity is relevant to City of Austin.

    Checks three signals:
    1. CFDA numbers in relevant federal program ranges
    2. Agency code from a relevant federal agency
    3. Keywords in title or description matching municipal services

    An opportunity is considered relevant if ANY of these signals match.

    Args:
        opp: Parsed opportunity

    Returns:
        True if the opportunity is likely relevant to city government
    """
    # 1. Check CFDA prefixes
    for cfda in opp.cfda_numbers:
        cfda_str = str(cfda).strip()
        prefix = cfda_str.split(".")[0] if "." in cfda_str else cfda_str[:2]
        if prefix in RELEVANT_CFDA_PREFIXES:
            return True

    # 2. Check agency code
    agency_code = (opp.agency_code or "").upper()
    if agency_code in RELEVANT_AGENCY_CODES:
        return True

    # Also check agency name for partial matches
    agency_upper = (opp.agency or "").upper()
    for relevant_code in RELEVANT_AGENCY_CODES:
        if relevant_code in agency_upper:
            return True

    # 3. Check keywords in title and description
    text_to_search = f"{opp.title} {opp.description}".lower()
    for keyword in MUNICIPAL_RELEVANCE_KEYWORDS:
        if keyword in text_to_search:
            return True

    return False


# ============================================================================
# API Interaction
# ============================================================================


async def _search_grants_gov(
    session: aiohttp.ClientSession,
    keyword: str,
    rows: int = MAX_RESULTS_PER_PAGE,
    offset: int = 0,
    posted_only: bool = True,
) -> Dict[str, Any]:
    """
    Execute a single search request against the Grants.gov API.

    Args:
        session: Active aiohttp session
        keyword: Search keyword string
        rows: Number of results per page (max 25)
        offset: Starting offset for pagination
        posted_only: If True, only return posted (open) opportunities

    Returns:
        Parsed JSON response dict, or empty dict on failure
    """
    opp_statuses = "posted" if posted_only else "forecasted|posted"

    payload = {
        "keyword": keyword,
        "oppStatuses": opp_statuses,
        "sortBy": "openDate",
        "rows": min(rows, MAX_RESULTS_PER_PAGE),
        "offset": offset,
    }

    for attempt in range(MAX_RETRIES):
        try:
            async with session.post(
                GRANTS_GOV_API_URL,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": USER_AGENT,
                },
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data

                if response.status == 429:
                    wait_time = RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(
                        f"Grants.gov rate limited, waiting {wait_time:.1f}s "
                        f"(attempt {attempt + 1}/{MAX_RETRIES})"
                    )
                    await asyncio.sleep(wait_time)
                    continue

                if response.status >= 500:
                    wait_time = RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(
                        f"Grants.gov server error {response.status}, retrying in "
                        f"{wait_time:.1f}s (attempt {attempt + 1}/{MAX_RETRIES})"
                    )
                    await asyncio.sleep(wait_time)
                    continue

                # Client error (4xx other than 429) -- do not retry
                body = await response.text()
                logger.error(f"Grants.gov API error {response.status}: {body[:200]}")
                return {}

        except asyncio.TimeoutError:
            wait_time = RETRY_BASE_DELAY * (2**attempt)
            logger.warning(
                f"Grants.gov request timeout (attempt {attempt + 1}/{MAX_RETRIES})"
            )
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(wait_time)

        except aiohttp.ClientError as exc:
            logger.warning(
                f"Grants.gov connection error: {exc} "
                f"(attempt {attempt + 1}/{MAX_RETRIES})"
            )
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_BASE_DELAY * (2**attempt))

        except Exception as exc:
            logger.error(f"Unexpected error calling Grants.gov API: {exc}")
            return {}

    logger.error(
        f"Failed to fetch from Grants.gov after {MAX_RETRIES} attempts "
        f"(keyword='{keyword}')"
    )
    return {}


# ============================================================================
# Main Entry Point
# ============================================================================


async def fetch_grants_gov_opportunities(
    topics: List[str],
    max_results: int = 50,
    posted_only: bool = True,
    filter_relevant: bool = True,
) -> GrantsGovFetchResult:
    """
    Fetch grant opportunities from Grants.gov matching the given topics.

    Searches the Grants.gov API for each topic keyword, paginates through
    results, optionally filters for Austin relevance, and deduplicates by
    opportunity ID.

    Args:
        topics: List of keyword strings to search (e.g., ["municipal infrastructure"])
        max_results: Maximum total opportunities to return across all topics
        posted_only: If True, only return currently open (posted) opportunities
        filter_relevant: If True, filter results for city/municipal relevance

    Returns:
        GrantsGovFetchResult containing opportunities, total count, and errors
    """
    all_opportunities: List[GrantsGovOpportunity] = []
    seen_ids: set = set()
    errors: List[str] = []
    total_api_results = 0

    timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for topic in topics:
            if len(all_opportunities) >= max_results:
                break

            remaining = max_results - len(all_opportunities)
            offset = 0

            while remaining > 0:
                rows = min(remaining, MAX_RESULTS_PER_PAGE)

                logger.info(
                    f"Searching Grants.gov: keyword='{topic}', "
                    f"offset={offset}, rows={rows}"
                )

                data = await _search_grants_gov(
                    session,
                    keyword=topic,
                    rows=rows,
                    offset=offset,
                    posted_only=posted_only,
                )

                if not data:
                    errors.append(f"Empty response for keyword '{topic}'")
                    break

                hits = data.get("hits", 0)
                total_api_results += hits
                opp_hits = data.get("oppHits", [])

                if not opp_hits:
                    break

                for raw_opp in opp_hits:
                    opp = _parse_opportunity(raw_opp)

                    if opp.id in seen_ids:
                        continue
                    seen_ids.add(opp.id)

                    if filter_relevant and not _is_austin_relevant(opp):
                        continue

                    all_opportunities.append(opp)
                    if len(all_opportunities) >= max_results:
                        break

                # If we got fewer results than requested, no more pages
                if len(opp_hits) < rows:
                    break

                offset += len(opp_hits)
                remaining = max_results - len(all_opportunities)

                # Small delay between pages to be respectful
                await asyncio.sleep(0.5)

    logger.info(
        f"Grants.gov fetch complete: {len(all_opportunities)} opportunities "
        f"(from {total_api_results} total API results, "
        f"{len(topics)} topic(s) searched)"
    )

    return GrantsGovFetchResult(
        opportunities=all_opportunities,
        total_results=total_api_results,
        errors=errors,
    )


# ============================================================================
# Pipeline Integration
# ============================================================================


def convert_to_raw_source(opp: GrantsGovOpportunity) -> "RawSource":
    """
    Convert a GrantsGovOpportunity to a RawSource for the discovery pipeline.

    Lazily imports RawSource from research_service to avoid circular imports.
    The content field contains structured grant metadata formatted as text
    for downstream AI analysis.

    Args:
        opp: Parsed Grants.gov opportunity

    Returns:
        RawSource instance ready for the research pipeline
    """
    from ..research_service import RawSource

    # Format funding information
    funding_parts = []
    if opp.estimated_funding is not None:
        funding_parts.append(f"Estimated Total Funding: ${opp.estimated_funding:,}")
    if opp.award_floor is not None:
        funding_parts.append(f"Award Floor: ${opp.award_floor:,}")
    if opp.award_ceiling is not None:
        funding_parts.append(f"Award Ceiling: ${opp.award_ceiling:,}")
    if opp.expected_awards is not None:
        funding_parts.append(f"Expected Number of Awards: {opp.expected_awards}")
    funding_info = "\n".join(funding_parts) if funding_parts else "Not specified"

    # Format dates
    open_str = opp.open_date.strftime("%B %d, %Y") if opp.open_date else "Not specified"
    close_str = (
        opp.close_date.strftime("%B %d, %Y") if opp.close_date else "Not specified"
    )
    if opp.close_date_explanation:
        close_str += f" ({opp.close_date_explanation})"

    # Map opportunity category code to label
    opp_cat_labels = {
        "D": "Discretionary",
        "M": "Mandatory",
        "C": "Continuation",
        "E": "Earmark",
        "O": "Other",
    }
    opp_cat_label = opp_cat_labels.get(
        opp.opportunity_category or "", opp.opportunity_category or "Not specified"
    )

    # Build structured content for AI analysis
    content = f"""\
Title: {opp.title}

Agency: {opp.agency}
Opportunity Number: {opp.opportunity_number or 'N/A'}
Opportunity Category: {opp_cat_label}
CFDA Numbers: {', '.join(opp.cfda_numbers) if opp.cfda_numbers else 'N/A'}

Open Date: {open_str}
Close Date: {close_str}

Funding Information:
{funding_info}

Cost Sharing Required: {'Yes' if opp.cost_sharing else 'No'}

Description:
{opp.description or 'No description available.'}"""

    # Determine published_at from open_date
    published_at = opp.open_date.isoformat() if opp.open_date else None

    return RawSource(
        url=opp.opportunity_url,
        title=opp.title,
        content=content,
        source_name="Grants.gov",
        relevance=0.85,
        published_at=published_at,
        source_type="grants_gov",
    )


async def fetch_and_convert_opportunities(
    topics: List[str],
    max_results: int = 50,
    posted_only: bool = True,
) -> Tuple[List, str]:
    """
    Fetch opportunities from Grants.gov and convert to RawSource objects.

    This is the recommended entry point for integration with the discovery
    pipeline. Returns a tuple of (sources, source_type) matching the
    convention used by other fetchers.

    Args:
        topics: Search keyword strings
        max_results: Maximum opportunities to return
        posted_only: If True, only return posted (open) opportunities

    Returns:
        Tuple of (list of RawSource objects, "grants_gov")
    """
    result = await fetch_grants_gov_opportunities(
        topics=topics,
        max_results=max_results,
        posted_only=posted_only,
    )

    sources = [convert_to_raw_source(opp) for opp in result.opportunities]

    if result.errors:
        logger.warning(
            f"Grants.gov fetch completed with {len(result.errors)} error(s): "
            f"{'; '.join(result.errors[:3])}"
        )

    return sources, "grants_gov"
