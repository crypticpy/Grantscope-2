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
import ssl
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
    # Note: The Grants.gov API has a known issue where combining keyword
    # search with oppStatuses="posted" returns 0 results. As a workaround,
    # we omit the status filter when searching by keyword and filter on our
    # side after fetching results.
    payload = {
        "keyword": keyword,
        "sortBy": "openDate",
        "rows": min(rows, MAX_RESULTS_PER_PAGE),
        "offset": offset,
    }
    if not keyword:
        # Only add status filter when not searching by keyword
        payload["oppStatuses"] = "posted" if posted_only else "forecasted|posted"

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
                    # API wraps results under "data" key
                    return data.get("data", data)

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
    # Grants.gov API requires an explicit SSL context; without it, Python's
    # default aiohttp SSL handling causes the API to return empty results.
    ssl_ctx = ssl.create_default_context()
    connector = aiohttp.TCPConnector(ssl=ssl_ctx)

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
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

                hits = data.get("hitCount", data.get("hits", 0))
                if offset == 0:
                    total_api_results += hits
                opp_hits = data.get("oppHits", [])

                if not opp_hits:
                    break

                for raw_opp in opp_hits:
                    # Client-side status filtering (API keyword+status combo is broken)
                    if posted_only:
                        opp_status = (raw_opp.get("oppStatus") or "").lower()
                        if opp_status and opp_status != "posted":
                            continue

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


# ============================================================================
# Opportunity Detail + Attachment Fetching
# ============================================================================

FETCH_OPPORTUNITY_URL = "https://api.grants.gov/v1/api/fetchOpportunity"
ATTACHMENT_DOWNLOAD_URL = (
    "https://apply07.grants.gov/grantsws/rest/opportunity/att/download/{att_id}"
)


async def fetch_opportunity_details(opportunity_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch full opportunity details from Grants.gov, including synopsis,
    attachment folders, CFDA numbers, and agency contact info.

    Uses POST https://api.grants.gov/v1/api/fetchOpportunity with
    body {"opportunityId": <int>}. No authentication required.

    Args:
        opportunity_id: Grants.gov numeric opportunity ID

    Returns:
        Full opportunity data dict, or None on failure
    """
    timeout = aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
    ssl_ctx = ssl.create_default_context()
    connector = aiohttp.TCPConnector(ssl=ssl_ctx)

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        for attempt in range(MAX_RETRIES):
            try:
                async with session.post(
                    FETCH_OPPORTUNITY_URL,
                    json={"opportunityId": int(opportunity_id)},
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": USER_AGENT,
                    },
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("errorcode") == 0:
                            detail = data.get("data", {})
                            # Check for "no record found" errors
                            errors = detail.get("errorMessages", [])
                            if errors and any(
                                "no record" in str(e).lower() for e in errors
                            ):
                                logger.info(
                                    f"No detail record for opportunity {opportunity_id}"
                                )
                                return None
                            return detail
                        logger.warning(
                            f"Grants.gov fetchOpportunity error: {data.get('msg')}"
                        )
                        return None

                    if response.status == 429:
                        wait_time = RETRY_BASE_DELAY * (2**attempt)
                        logger.warning(
                            f"Grants.gov rate limited, waiting {wait_time:.1f}s"
                        )
                        await asyncio.sleep(wait_time)
                        continue

                    if response.status >= 500:
                        wait_time = RETRY_BASE_DELAY * (2**attempt)
                        await asyncio.sleep(wait_time)
                        continue

                    logger.error(f"Grants.gov fetchOpportunity HTTP {response.status}")
                    return None

            except asyncio.TimeoutError:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_BASE_DELAY * (2**attempt))
            except aiohttp.ClientError as exc:
                logger.warning(f"Grants.gov detail connection error: {exc}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_BASE_DELAY * (2**attempt))
            except (ValueError, TypeError) as exc:
                logger.error(f"Invalid opportunity ID '{opportunity_id}': {exc}")
                return None

    logger.error(
        f"Failed to fetch opportunity details after {MAX_RETRIES} attempts "
        f"(id={opportunity_id})"
    )
    return None


def extract_nofo_attachment_urls(detail: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Extract NOFO PDF attachment download URLs from opportunity detail data.

    Looks for attachments in "Full Announcement" and "Revised Full Announcement"
    folders, which typically contain the NOFO PDF. Falls back to
    "Other Supporting Documents" if no full announcement is found.

    Args:
        detail: Raw opportunity detail dict from fetch_opportunity_details()

    Returns:
        List of dicts with keys: url, filename, mime_type, folder_type
    """
    attachments = []
    folders = detail.get("synopsisAttachmentFolders", [])

    # Priority order: Revised Full Announcement > Full Announcement > Other
    priority_order = [
        "Revised Full Announcement",
        "Full Announcement",
        "Other Supporting Documents",
    ]

    sorted_folders = sorted(
        folders,
        key=lambda f: (
            priority_order.index(f.get("folderType", ""))
            if f.get("folderType", "") in priority_order
            else 99
        ),
    )

    for folder in sorted_folders:
        folder_type = folder.get("folderType", "Unknown")
        for att in folder.get("synopsisAttachments", []):
            att_id = att.get("id")
            filename = att.get("fileName", "")
            mime_type = att.get("mimeType", "")

            if not att_id:
                continue

            # Only include PDFs and Word docs
            if mime_type not in (
                "application/pdf",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/msword",
            ):
                continue

            attachments.append(
                {
                    "url": ATTACHMENT_DOWNLOAD_URL.format(att_id=att_id),
                    "filename": filename,
                    "mime_type": mime_type,
                    "folder_type": folder_type,
                }
            )

    return attachments


def format_opportunity_detail(detail: Dict[str, Any]) -> str:
    """
    Format raw opportunity detail JSON into structured text for AI analysis.

    Extracts synopsis, eligibility, funding, agency contacts, and CFDA info
    into a comprehensive text block suitable for research pipeline ingestion.

    Args:
        detail: Raw opportunity detail dict from fetch_opportunity_details()

    Returns:
        Formatted text content string
    """
    parts = []

    title = detail.get("opportunityTitle", "Unknown Opportunity")
    opp_number = detail.get("opportunityNumber", "N/A")
    parts.append(f"# {title}")
    parts.append(f"Opportunity Number: {opp_number}")

    # Agency info
    agency = detail.get("agencyDetails", {})
    top_agency = detail.get("topAgencyDetails", {})
    if top_agency.get("agencyName"):
        parts.append(f"Agency: {top_agency['agencyName']}")
    if agency.get("agencyName") and agency["agencyName"] != top_agency.get(
        "agencyName"
    ):
        parts.append(f"Sub-Agency: {agency['agencyName']}")

    # Category
    cat = detail.get("opportunityCategory", {})
    if isinstance(cat, dict) and cat.get("description"):
        parts.append(f"Category: {cat['description']}")

    # CFDA/ALN numbers
    cfdas = detail.get("cfdas", [])
    if cfdas:
        for cfda in cfdas:
            parts.append(
                f"CFDA/ALN: {cfda.get('cfdaNumber', 'N/A')} - "
                f"{cfda.get('programTitle', '')}"
            )

    # Synopsis or Forecast description
    synopsis = detail.get("synopsis") or detail.get("forecast") or {}
    desc = synopsis.get("synopsisDesc") or synopsis.get("forecastDesc") or ""
    # Strip HTML tags
    if desc:
        import re as _re

        desc_clean = _re.sub(r"<[^>]+>", "", desc).strip()
        parts.append(f"\n## Description\n{desc_clean}")

    # Funding info
    funding_parts = []
    est_funding = synopsis.get("estimatedFunding")
    if est_funding:
        try:
            funding_parts.append(f"Estimated Total Funding: ${int(est_funding):,}")
        except (ValueError, TypeError):
            funding_parts.append(f"Estimated Total Funding: {est_funding}")
    ceiling = synopsis.get("awardCeiling")
    if ceiling and str(ceiling) != "0":
        try:
            funding_parts.append(f"Award Ceiling: ${int(ceiling):,}")
        except (ValueError, TypeError):
            pass
    floor = synopsis.get("awardFloor")
    if floor and str(floor) != "0":
        try:
            funding_parts.append(f"Award Floor: ${int(floor):,}")
        except (ValueError, TypeError):
            pass
    num_awards = synopsis.get("numberOfAwards")
    if num_awards:
        funding_parts.append(f"Expected Number of Awards: {num_awards}")
    cost_sharing = synopsis.get("costSharing")
    if cost_sharing is not None:
        funding_parts.append(
            f"Cost Sharing Required: {'Yes' if cost_sharing else 'No'}"
        )
    if funding_parts:
        parts.append("\n## Funding Information\n" + "\n".join(funding_parts))

    # Eligible applicant types
    applicant_types = synopsis.get("applicantTypes", [])
    if applicant_types:
        types_list = [
            at.get("description", "") for at in applicant_types if at.get("description")
        ]
        if types_list:
            parts.append(
                "\n## Eligible Applicant Types\n"
                + "\n".join(f"- {t}" for t in types_list)
            )

    # Funding instruments
    instruments = synopsis.get("fundingInstruments", [])
    if instruments:
        inst_list = [
            i.get("description", "") for i in instruments if i.get("description")
        ]
        if inst_list:
            parts.append(f"Funding Instrument: {', '.join(inst_list)}")

    # Key dates
    date_parts = []
    posting = synopsis.get("postingDate")
    if posting:
        date_parts.append(f"Posting Date: {posting}")
    response_date = synopsis.get("responseDateDesc") or synopsis.get(
        "estApplicationResponseDate"
    )
    if response_date:
        date_parts.append(f"Application Deadline: {response_date}")
    est_award = synopsis.get("estAwardDate")
    if est_award:
        date_parts.append(f"Estimated Award Date: {est_award}")
    est_start = synopsis.get("estProjectStartDate")
    if est_start:
        date_parts.append(f"Estimated Project Start: {est_start}")
    archive = synopsis.get("archiveDate")
    if archive:
        date_parts.append(f"Archive Date: {archive}")
    if date_parts:
        parts.append("\n## Key Dates\n" + "\n".join(date_parts))

    # Agency contact
    contact_parts = []
    contact_name = synopsis.get("agencyContactName")
    if contact_name:
        contact_parts.append(f"Contact: {contact_name}")
    contact_phone = synopsis.get("agencyContactPhone")
    if contact_phone:
        contact_parts.append(f"Phone: {contact_phone}")
    contact_email = synopsis.get("agencyContactEmail")
    if contact_email:
        contact_parts.append(f"Email: {contact_email}")
    if contact_parts:
        parts.append("\n## Agency Contact\n" + "\n".join(contact_parts))

    # Eligibility description
    elig_desc = synopsis.get("applicantEligibilityDesc")
    if elig_desc and elig_desc.strip() and elig_desc.strip() != "N/A":
        parts.append(f"\n## Eligibility Details\n{elig_desc}")

    # Modification comments
    mod_comments = detail.get("modifiedComments")
    if mod_comments and mod_comments.strip():
        parts.append(f"\n## Recent Modifications\n{mod_comments.strip()}")

    return "\n".join(parts)
