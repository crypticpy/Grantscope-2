"""
SAM.gov source fetcher for federal grant and contract opportunities.

This module fetches grant and contract opportunities from the SAM.gov
Opportunities API (v2). SAM.gov is the System for Award Management,
the official U.S. government system for federal procurement and grants.

Features:
- Search SAM.gov opportunities by keyword, NAICS code, and procurement type
- Filter for grant-type opportunities (ptype "o") by default
- Austin/municipal relevance scoring
- Pagination support for large result sets
- Graceful error handling with retry logic (SAM.gov can be slow)
- Date range filtering for recent opportunities
- Converts results to RawSource format for pipeline integration

API Documentation:
    https://open.gsa.gov/api/sam-opportunities-v2/

Usage:
    from backend.app.source_fetchers.sam_gov_fetcher import (
        fetch_sam_gov_opportunities,
        fetch_and_convert_opportunities,
    )

    # Direct fetch
    result = await fetch_sam_gov_opportunities(
        topics=["municipal infrastructure", "public health"],
        max_results=50,
        include_grants=True,
    )

    # Pipeline integration
    sources, source_type = await fetch_and_convert_opportunities(
        topics=["water infrastructure", "transit"],
        max_results=30,
    )
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

# SAM.gov Opportunities API v2 endpoint
SAM_GOV_API_URL = "https://api.sam.gov/opportunities/v2/search"

# Default timeout for HTTP requests (seconds) - SAM.gov can be slow
DEFAULT_TIMEOUT = 30

# Maximum results per API page (SAM.gov allows up to 1000)
MAX_RESULTS_PER_PAGE = 100

# User agent for SAM.gov requests
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 "
    "GrantScope-Research-Bot/1.0"
)

# NAICS codes relevant to city/municipal government operations
# Grouped by functional area for clarity
RELEVANT_NAICS_CODES: List[str] = [
    # Professional, scientific, and technical services (541xxx)
    "541611",  # Administrative management consulting
    "541612",  # Human resources consulting
    "541613",  # Marketing consulting
    "541614",  # Process & logistics consulting
    "541618",  # Other management consulting
    "541620",  # Environmental consulting
    "541690",  # Other scientific/technical consulting
    "541511",  # Custom computer programming
    "541512",  # Computer systems design
    "541519",  # Other computer related services
    "541715",  # R&D in physical/engineering/life sciences
    "541720",  # R&D in social sciences/humanities
    # Heavy and civil engineering construction (237xxx)
    "237110",  # Water and sewer line construction
    "237120",  # Oil and gas pipeline construction
    "237130",  # Power and communication line construction
    "237210",  # Land subdivision
    "237310",  # Highway, street, and bridge construction
    "237990",  # Other heavy and civil engineering construction
    # Waste management and remediation (562xxx)
    "562111",  # Solid waste collection
    "562112",  # Hazardous waste collection
    "562211",  # Hazardous waste treatment and disposal
    "562212",  # Solid waste landfill
    "562910",  # Remediation services
    "562920",  # Materials recovery facilities
    # Public administration-adjacent (923xxx, 924xxx, 925xxx)
    "923110",  # Administration of education programs
    "923120",  # Administration of public health programs
    "924110",  # Administration of air and water programs
    "924120",  # Administration of conservation programs
    "925110",  # Administration of housing programs
    "925120",  # Administration of urban planning
    # Transportation and warehousing (485xxx, 488xxx)
    "485111",  # Mixed mode transit systems
    "485112",  # Commuter rail systems
    "485113",  # Bus and other motor vehicle transit
    "485119",  # Other urban transit systems
    "488111",  # Air traffic control
    "488490",  # Other support for road transportation
    # Utilities (221xxx)
    "221111",  # Hydroelectric power generation
    "221112",  # Fossil fuel electric power generation
    "221113",  # Nuclear electric power generation
    "221114",  # Solar electric power generation
    "221115",  # Wind electric power generation
    "221116",  # Geothermal electric power generation
    "221117",  # Biomass electric power generation
    "221118",  # Other electric power generation
    "221121",  # Electric bulk power transmission and control
    "221122",  # Electric power distribution
    "221210",  # Natural gas distribution
    "221310",  # Water supply and irrigation systems
    "221320",  # Sewage treatment facilities
]

# Procurement types: o=Other/Grants, p=Presolicitation, k=Combined, s=Solicitation
RELEVANT_PROCUREMENT_TYPES: List[str] = ["o", "p", "k", "s"]

# Keywords that indicate municipal/city relevance in opportunity text
MUNICIPAL_RELEVANCE_KEYWORDS: List[str] = [
    "municipal",
    "city government",
    "local government",
    "county",
    "metropolitan",
    "urban",
    "community",
    "public health",
    "public safety",
    "transportation",
    "transit",
    "infrastructure",
    "water system",
    "wastewater",
    "stormwater",
    "housing",
    "affordable housing",
    "homelessness",
    "workforce development",
    "economic development",
    "sustainability",
    "climate",
    "resilience",
    "emergency management",
    "public works",
    "parks and recreation",
    "broadband",
    "smart city",
    "civic",
    "equity",
    "environmental justice",
    "energy efficiency",
    "renewable energy",
    "law enforcement",
    "fire department",
    "EMS",
    "911",
    "cybersecurity",
    "digital services",
    "permitting",
    "code enforcement",
    "public library",
]

# Federal agencies that commonly issue grants relevant to cities
RELEVANT_AGENCIES: List[str] = [
    "DEPARTMENT OF HOUSING AND URBAN DEVELOPMENT",
    "DEPARTMENT OF TRANSPORTATION",
    "ENVIRONMENTAL PROTECTION AGENCY",
    "DEPARTMENT OF ENERGY",
    "DEPARTMENT OF HEALTH AND HUMAN SERVICES",
    "DEPARTMENT OF HOMELAND SECURITY",
    "DEPARTMENT OF JUSTICE",
    "DEPARTMENT OF COMMERCE",
    "DEPARTMENT OF LABOR",
    "DEPARTMENT OF THE INTERIOR",
    "DEPARTMENT OF EDUCATION",
    "NATIONAL SCIENCE FOUNDATION",
    "GENERAL SERVICES ADMINISTRATION",
    "FEDERAL COMMUNICATIONS COMMISSION",
    "FEDERAL EMERGENCY MANAGEMENT AGENCY",
    "SMALL BUSINESS ADMINISTRATION",
    "CORPORATION FOR NATIONAL AND COMMUNITY SERVICE",
    "NATIONAL ENDOWMENT FOR THE ARTS",
    "NATIONAL ENDOWMENT FOR THE HUMANITIES",
    "INSTITUTE OF MUSEUM AND LIBRARY SERVICES",
]

# Default number of days back to search for opportunities
DEFAULT_DAYS_BACK = 30


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class SamGovOpportunity:
    """Represents a single opportunity from SAM.gov."""

    notice_id: str
    solicitation_number: str
    title: str
    description: str
    department: str
    posted_date: Optional[datetime] = None
    response_deadline: Optional[datetime] = None
    archive_date: Optional[datetime] = None
    procurement_type: str = ""
    naics_code: str = ""
    classification_code: str = ""
    point_of_contact: Optional[Dict[str, Any]] = None
    office_address: Optional[Dict[str, Any]] = None
    award_info: Optional[Dict[str, Any]] = None
    resource_links: List[str] = field(default_factory=list)
    ui_link: str = ""
    set_aside: str = ""
    organization_type: str = ""
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def opportunity_url(self) -> str:
        """Generate the canonical SAM.gov URL for this opportunity."""
        if self.ui_link:
            return self.ui_link
        return f"https://sam.gov/opp/{self.notice_id}/view"

    @property
    def is_grant(self) -> bool:
        """Check if this opportunity is a grant (ptype 'o' = Other/Grant)."""
        return self.procurement_type.lower() == "o"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "notice_id": self.notice_id,
            "solicitation_number": self.solicitation_number,
            "title": self.title,
            "description": self.description,
            "department": self.department,
            "posted_date": (self.posted_date.isoformat() if self.posted_date else None),
            "response_deadline": (
                self.response_deadline.isoformat() if self.response_deadline else None
            ),
            "archive_date": (
                self.archive_date.isoformat() if self.archive_date else None
            ),
            "procurement_type": self.procurement_type,
            "naics_code": self.naics_code,
            "classification_code": self.classification_code,
            "point_of_contact": self.point_of_contact,
            "office_address": self.office_address,
            "award_info": self.award_info,
            "resource_links": self.resource_links,
            "ui_link": self.ui_link,
            "opportunity_url": self.opportunity_url,
            "is_grant": self.is_grant,
            "set_aside": self.set_aside,
            "organization_type": self.organization_type,
        }


@dataclass
class SamGovFetchResult:
    """Result of a SAM.gov fetch operation."""

    opportunities: List[SamGovOpportunity]
    total_results: int
    errors: List[str]

    @property
    def success_count(self) -> int:
        return len(self.opportunities)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


# ============================================================================
# Date Parsing
# ============================================================================


def _parse_sam_date(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parse a date string from SAM.gov API response.

    SAM.gov returns dates in various formats including:
    - "0101" (MMdd with no year)
    - "2024-01-15"
    - "01/15/2024"
    - "2024-01-15T00:00:00"
    - "Jan 15, 2024"

    Args:
        date_str: Date string from API response

    Returns:
        Parsed datetime or None if parsing fails
    """
    if not date_str or not isinstance(date_str, str):
        return None

    date_str = date_str.strip()
    if not date_str:
        return None

    # Try common SAM.gov date formats
    formats = [
        "%Y-%m-%dT%H:%M:%S%z",  # ISO with timezone
        "%Y-%m-%dT%H:%M:%S",  # ISO without timezone
        "%Y-%m-%d",  # ISO date only
        "%m/%d/%Y",  # US format (used in API params)
        "%m/%d/%Y %H:%M:%S",  # US format with time
        "%b %d, %Y",  # Month name short
        "%B %d, %Y",  # Month name long
        "%Y%m%d",  # Compact format
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    # Try ISO format as fallback
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        pass

    logger.debug(f"Could not parse SAM.gov date: '{date_str}'")
    return None


# ============================================================================
# API Functions
# ============================================================================


async def _search_sam_gov(
    session: aiohttp.ClientSession,
    keyword: str,
    limit: int,
    offset: int,
    api_key: str,
    ptype: Optional[str] = None,
    posted_from: Optional[str] = None,
    posted_to: Optional[str] = None,
    ncode: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute a single search against the SAM.gov Opportunities API.

    Args:
        session: aiohttp client session
        keyword: Search keyword
        limit: Number of results per page
        offset: Pagination offset
        api_key: SAM.gov API key
        ptype: Procurement type filter (o, p, k, s)
        posted_from: Start date filter (MM/dd/yyyy)
        posted_to: End date filter (MM/dd/yyyy)
        ncode: NAICS code filter

    Returns:
        Parsed JSON response dict, or empty dict on failure

    Raises:
        Does not raise; returns empty dict with logged errors
    """
    params: Dict[str, Any] = {
        "api_key": api_key,
        "keyword": keyword,
        "limit": min(limit, MAX_RESULTS_PER_PAGE),
        "offset": offset,
    }

    if ptype:
        params["ptype"] = ptype
    if posted_from:
        params["postedFrom"] = posted_from
    if posted_to:
        params["postedTo"] = posted_to
    if ncode:
        params["ncode"] = ncode

    max_retries = 3
    retry_delay = 2.0

    for attempt in range(max_retries):
        try:
            async with session.get(
                SAM_GOV_API_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data

                elif response.status == 429:
                    # Rate limited
                    wait_time = retry_delay * (2**attempt)
                    logger.warning(
                        f"SAM.gov rate limited (attempt {attempt + 1}/{max_retries}), "
                        f"waiting {wait_time:.1f}s"
                    )
                    await asyncio.sleep(wait_time)

                elif response.status == 403:
                    logger.error(
                        "SAM.gov API key invalid or unauthorized (HTTP 403). "
                        "Check SAM_GOV_API_KEY environment variable."
                    )
                    return {}

                elif response.status >= 500:
                    # Server error - retry
                    wait_time = retry_delay * (2**attempt)
                    logger.warning(
                        f"SAM.gov server error {response.status} "
                        f"(attempt {attempt + 1}/{max_retries}), waiting {wait_time:.1f}s"
                    )
                    await asyncio.sleep(wait_time)

                else:
                    body = await response.text()
                    logger.error(
                        f"SAM.gov API error: HTTP {response.status} - " f"{body[:200]}"
                    )
                    return {}

        except asyncio.TimeoutError:
            wait_time = retry_delay * (2**attempt)
            logger.warning(
                f"SAM.gov request timeout for keyword='{keyword}' "
                f"(attempt {attempt + 1}/{max_retries}), waiting {wait_time:.1f}s"
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(wait_time)

        except aiohttp.ClientError as e:
            logger.warning(
                f"SAM.gov connection error: {e} "
                f"(attempt {attempt + 1}/{max_retries})"
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)

        except Exception as e:
            logger.error(f"Unexpected error calling SAM.gov API: {e}", exc_info=True)
            return {}

    logger.error(
        f"SAM.gov API call failed after {max_retries} attempts "
        f"for keyword='{keyword}'"
    )
    return {}


# ============================================================================
# Parsing
# ============================================================================


def _parse_opportunity(raw: Dict[str, Any]) -> SamGovOpportunity:
    """
    Parse a raw opportunity dict from the SAM.gov API response.

    Args:
        raw: Single opportunity dict from the opportunitiesData array

    Returns:
        Parsed SamGovOpportunity instance
    """
    # Extract point of contact (first one if multiple)
    poc = None
    poc_list = raw.get("pointOfContact", [])
    if isinstance(poc_list, list) and poc_list:
        first_poc = poc_list[0]
        poc = {
            "name": first_poc.get("fullName", ""),
            "email": first_poc.get("email", ""),
            "phone": first_poc.get("phone", ""),
            "type": first_poc.get("type", ""),
        }

    # Extract office address
    office_addr = None
    raw_addr = raw.get("officeAddress", {})
    if isinstance(raw_addr, dict) and raw_addr:
        office_addr = {
            "city": raw_addr.get("city", ""),
            "state": raw_addr.get("state", ""),
            "zip": raw_addr.get("zipcode", raw_addr.get("zip", "")),
        }

    # Extract award info
    award = None
    raw_award = raw.get("award", {})
    if isinstance(raw_award, dict) and raw_award:
        award = {
            "amount": raw_award.get("amount", ""),
            "date": raw_award.get("date", ""),
            "awardee": (
                raw_award.get("awardee", {}).get("name", "")
                if isinstance(raw_award.get("awardee"), dict)
                else ""
            ),
        }

    # Extract resource links
    resource_links = []
    raw_links = raw.get("resourceLinks", [])
    if isinstance(raw_links, list):
        resource_links = [str(link) for link in raw_links if link]

    # Build description from available fields
    description = raw.get("description", "") or ""
    if not description:
        # Some opportunities have description in additionalInfoLink or synopsis
        description = raw.get("additionalInfoLink", "") or ""

    return SamGovOpportunity(
        notice_id=raw.get("noticeId", ""),
        solicitation_number=raw.get("solicitationNumber", "") or "",
        title=raw.get("title", "Untitled Opportunity"),
        description=description,
        department=raw.get("fullParentPathName", "") or "",
        posted_date=_parse_sam_date(raw.get("postedDate")),
        response_deadline=_parse_sam_date(raw.get("responseDeadLine")),
        archive_date=_parse_sam_date(raw.get("archiveDate")),
        procurement_type=raw.get("type", "") or "",
        naics_code=raw.get("naicsCode", "") or "",
        classification_code=raw.get("classificationCode", "") or "",
        point_of_contact=poc,
        office_address=office_addr,
        award_info=award,
        resource_links=resource_links,
        ui_link=raw.get("uiLink", "") or "",
        set_aside=raw.get("typeOfSetAside", "") or "",
        organization_type=raw.get("organizationType", "") or "",
        raw_data=raw,
    )


# ============================================================================
# Relevance Filtering
# ============================================================================


def _is_austin_relevant(opp: SamGovOpportunity) -> bool:
    """
    Determine whether a SAM.gov opportunity is relevant to the City of Austin.

    Relevance is determined by checking:
    1. Department hierarchy against known relevant federal agencies
    2. NAICS codes in relevant ranges for municipal services
    3. Keywords in title/description matching city service areas
    4. Procurement type (grants preferred)

    This is a lightweight pre-filter; the AI pipeline performs deeper analysis.

    Args:
        opp: Parsed SAM.gov opportunity

    Returns:
        True if the opportunity appears relevant to municipal government
    """
    # Check 1: Department matches a known relevant agency
    department_upper = opp.department.upper()
    for agency in RELEVANT_AGENCIES:
        if agency in department_upper:
            return True

    # Check 2: NAICS code in relevant ranges
    if opp.naics_code:
        # Check exact match
        if opp.naics_code in RELEVANT_NAICS_CODES:
            return True
        # Check 3-digit prefix match (broader industry group)
        naics_prefix = opp.naics_code[:3]
        relevant_prefixes = {code[:3] for code in RELEVANT_NAICS_CODES}
        if naics_prefix in relevant_prefixes:
            return True

    # Check 3: Keywords in title or description
    searchable_text = f"{opp.title} {opp.description}".lower()
    keyword_matches = sum(
        1 for kw in MUNICIPAL_RELEVANCE_KEYWORDS if kw in searchable_text
    )
    # Require at least 1 keyword match
    if keyword_matches >= 1:
        return True

    # Check 4: Grant-type opportunities with keyword relevance get a pass
    if opp.is_grant:
        text = f"{opp.title} {opp.description}".lower()
        if any(kw in text for kw in MUNICIPAL_RELEVANCE_KEYWORDS):
            return True

    return False


# ============================================================================
# Main Fetch Functions
# ============================================================================


async def fetch_sam_gov_opportunities(
    topics: List[str],
    max_results: int = 50,
    include_grants: bool = True,
    include_contracts: bool = False,
    days_back: int = DEFAULT_DAYS_BACK,
    filter_relevant: bool = True,
) -> SamGovFetchResult:
    """
    Fetch grant and contract opportunities from SAM.gov.

    This is the main entry point for SAM.gov opportunity discovery. It searches
    for each topic, aggregates and deduplicates results, and optionally filters
    for Austin relevance.

    Args:
        topics: List of search keywords (e.g., ["water infrastructure", "public health"])
        max_results: Maximum total opportunities to return
        include_grants: Include grant-type opportunities (ptype "o")
        include_contracts: Include contract/solicitation types (ptype "p", "k", "s")
        days_back: Number of days back to search from today
        filter_relevant: If True, apply municipal relevance filtering

    Returns:
        SamGovFetchResult with opportunities, total count, and any errors
    """
    api_key = os.getenv("SAM_GOV_API_KEY", "").strip()
    if not api_key:
        logger.warning(
            "SAM_GOV_API_KEY not set. SAM.gov fetcher will return empty results. "
            "Get a free API key at https://open.gsa.gov/api/sam-opportunities-v2/"
        )
        return SamGovFetchResult(opportunities=[], total_results=0, errors=[])

    # Build procurement type filter
    ptypes = []
    if include_grants:
        ptypes.append("o")
    if include_contracts:
        ptypes.extend(["p", "k", "s"])

    ptype_param = ",".join(ptypes) if ptypes else None

    # Build date range
    now = datetime.now(timezone.utc)
    posted_from = (now - timedelta(days=days_back)).strftime("%m/%d/%Y")
    posted_to = now.strftime("%m/%d/%Y")

    all_opportunities: List[SamGovOpportunity] = []
    seen_notice_ids: set = set()
    errors: List[str] = []
    total_results = 0

    headers = {"User-Agent": USER_AGENT}

    async with aiohttp.ClientSession(headers=headers) as session:
        for i, topic in enumerate(topics):
            if len(all_opportunities) >= max_results:
                break

            remaining = max_results - len(all_opportunities)
            page_limit = min(
                remaining * 2, MAX_RESULTS_PER_PAGE
            )  # Fetch extra for filtering

            logger.info(f"SAM.gov search: keyword='{topic}', limit={page_limit}")

            try:
                data = await _search_sam_gov(
                    session=session,
                    keyword=topic,
                    limit=page_limit,
                    offset=0,
                    api_key=api_key,
                    ptype=ptype_param,
                    posted_from=posted_from,
                    posted_to=posted_to,
                )

                if not data:
                    errors.append(f"No response for keyword '{topic}'")
                    continue

                total_records = data.get("totalRecords", 0)
                total_results += total_records
                opp_data = data.get("opportunitiesData", [])

                if not opp_data:
                    logger.info(
                        f"SAM.gov: No opportunities found for '{topic}' "
                        f"(totalRecords={total_records})"
                    )
                    continue

                logger.info(
                    f"SAM.gov: {len(opp_data)} opportunities returned for '{topic}' "
                    f"(totalRecords={total_records})"
                )

                for raw_opp in opp_data:
                    if len(all_opportunities) >= max_results:
                        break

                    try:
                        opp = _parse_opportunity(raw_opp)
                    except Exception as e:
                        logger.warning(f"Failed to parse SAM.gov opportunity: {e}")
                        errors.append(f"Parse error: {str(e)[:100]}")
                        continue

                    # Deduplicate by notice ID
                    if opp.notice_id in seen_notice_ids:
                        continue
                    seen_notice_ids.add(opp.notice_id)

                    # Apply relevance filter
                    if filter_relevant and not _is_austin_relevant(opp):
                        continue

                    all_opportunities.append(opp)

            except Exception as e:
                error_msg = f"SAM.gov fetch error for '{topic}': {str(e)[:150]}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)

            # Small delay between searches to be respectful of the API
            if i < len(topics) - 1:
                await asyncio.sleep(0.5)

    logger.info(
        f"SAM.gov fetch complete: {len(all_opportunities)} opportunities "
        f"from {len(topics)} topics ({len(errors)} errors)"
    )

    return SamGovFetchResult(
        opportunities=all_opportunities,
        total_results=total_results,
        errors=errors,
    )


# ============================================================================
# Pipeline Integration
# ============================================================================


def convert_to_raw_source(opp: SamGovOpportunity) -> Any:
    """
    Convert a SamGovOpportunity to a RawSource for the discovery pipeline.

    Uses a lazy import of RawSource from the research service to avoid
    circular dependency issues.

    Args:
        opp: Parsed SAM.gov opportunity

    Returns:
        RawSource instance compatible with the discovery/research pipeline
    """
    from ..research_service import RawSource

    # Build rich content string from opportunity data
    content_parts = [
        f"Title: {opp.title}",
        "",
        f"Department: {opp.department}" if opp.department else "",
        (
            f"Solicitation Number: {opp.solicitation_number}"
            if opp.solicitation_number
            else ""
        ),
        f"Procurement Type: {_procurement_type_label(opp.procurement_type)}",
        f"NAICS Code: {opp.naics_code}" if opp.naics_code else "",
        "",
    ]

    if opp.response_deadline:
        content_parts.append(
            f"Response Deadline: {opp.response_deadline.strftime('%B %d, %Y')}"
        )

    if opp.award_info and opp.award_info.get("amount"):
        content_parts.append(f"Award Amount: {opp.award_info['amount']}")

    content_parts.extend(
        ["", "Description:", opp.description or "(No description provided)"]
    )

    if opp.point_of_contact:
        poc = opp.point_of_contact
        poc_parts = [
            p for p in [poc.get("name"), poc.get("email"), poc.get("phone")] if p
        ]
        if poc_parts:
            content_parts.extend(["", f"Point of Contact: {', '.join(poc_parts)}"])

    content = "\n".join(part for part in content_parts if part is not None)

    # Determine published_at
    published_at = None
    if opp.posted_date:
        published_at = opp.posted_date.isoformat()

    return RawSource(
        url=opp.opportunity_url,
        title=opp.title,
        content=content.strip(),
        source_name="SAM.gov",
        relevance=0.85,  # High relevance for government grant opportunities
        published_at=published_at,
        source_type="sam_gov",
    )


def _procurement_type_label(ptype: str) -> str:
    """Map procurement type code to human-readable label."""
    labels = {
        "o": "Grant / Other",
        "p": "Presolicitation",
        "k": "Combined Synopsis/Solicitation",
        "s": "Solicitation",
        "r": "Sources Sought",
        "g": "Sale of Surplus Property",
        "i": "Intent to Bundle",
        "a": "Award Notice",
    }
    return labels.get(ptype.lower(), ptype) if ptype else "Unknown"


async def fetch_and_convert_opportunities(
    topics: List[str],
    max_results: int = 50,
    include_grants: bool = True,
    include_contracts: bool = False,
    days_back: int = DEFAULT_DAYS_BACK,
) -> Tuple[List[Any], str]:
    """
    Fetch SAM.gov opportunities and convert to RawSource format for pipeline integration.

    This is the recommended function for integrating SAM.gov data into the
    discovery pipeline. Returns a tuple of (sources, source_type) matching
    the pattern used by other fetchers.

    Args:
        topics: Search keywords for SAM.gov
        max_results: Maximum opportunities to return
        include_grants: Include grant-type opportunities
        include_contracts: Include contract/solicitation types
        days_back: Number of days back to search

    Returns:
        Tuple of (list of RawSource objects, "sam_gov" source type string)
    """
    result = await fetch_sam_gov_opportunities(
        topics=topics,
        max_results=max_results,
        include_grants=include_grants,
        include_contracts=include_contracts,
        days_back=days_back,
    )

    if result.has_errors:
        for error in result.errors:
            logger.warning(f"SAM.gov fetch error: {error}")

    sources = []
    for opp in result.opportunities:
        try:
            source = convert_to_raw_source(opp)
            sources.append(source)
        except Exception as e:
            logger.warning(
                f"Failed to convert SAM.gov opportunity '{opp.title}' "
                f"to RawSource: {e}"
            )

    logger.info(
        f"SAM.gov pipeline: {len(sources)} sources converted "
        f"from {len(result.opportunities)} opportunities"
    )

    return sources, "sam_gov"
