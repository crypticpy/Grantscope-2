"""
Source content validator for GrantScope discovery pipeline.

Validates source content quality, freshness, and provenance before it enters
the AI triage stage. This module acts as a fast, deterministic pre-filter that
catches obviously invalid or low-quality sources without consuming AI tokens.

Validation stages:
    1. Content validation - Ensures minimum meaningful text (>=100 chars after
       stripping HTML/whitespace). Catches empty pages, paywalls, and stubs.
    2. Freshness validation - Enforces category-specific age thresholds so the
       pipeline focuses on timely content. Government docs get longer windows
       because policy moves slowly; news gets shorter windows for relevance.
    3. Pre-print detection - Flags academic pre-prints (arXiv, bioRxiv, SSRN)
       so downstream consumers can apply appropriate caveats and weighting.

Usage:
    from app.source_validator import SourceValidator

    validator = SourceValidator()
    result = validator.validate_all(
        content="<p>Some article text...</p>",
        published_date="2025-01-15",
        category="news",
        url="https://example.com/article"
    )
    if result.is_valid:
        # Proceed to AI triage
        ...
    else:
        # Log rejection reason
        print(result.content_validation.reason_code)
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List

logger = logging.getLogger(__name__)


# ============================================================================
# Date Parsing Utilities
# ============================================================================

# Common date formats to try when python-dateutil is not available.
# Ordered from most specific to least specific to avoid ambiguous parses.
_DATE_FORMATS = [
    # ISO 8601 variants
    "%Y-%m-%dT%H:%M:%S%z",  # 2025-01-15T10:30:00+00:00
    "%Y-%m-%dT%H:%M:%SZ",  # 2025-01-15T10:30:00Z
    "%Y-%m-%dT%H:%M:%S",  # 2025-01-15T10:30:00
    "%Y-%m-%d",  # 2025-01-15
    # RFC 2822 (common in RSS feeds)
    "%a, %d %b %Y %H:%M:%S %z",  # Mon, 15 Jan 2025 10:30:00 +0000
    "%a, %d %b %Y %H:%M:%S %Z",  # Mon, 15 Jan 2025 10:30:00 GMT
    "%d %b %Y %H:%M:%S %z",  # 15 Jan 2025 10:30:00 +0000
    # Human-readable formats
    "%B %d, %Y",  # January 15, 2025
    "%b %d, %Y",  # Jan 15, 2025
    "%d %B %Y",  # 15 January 2025
    "%d %b %Y",  # 15 Jan 2025
    "%m/%d/%Y",  # 01/15/2025
    "%d/%m/%Y",  # 15/01/2025
    "%Y/%m/%d",  # 2025/01/15
]


def _parse_date(date_str: str) -> Optional[datetime]:
    """
    Parse a date string into a timezone-aware datetime.

    Attempts python-dateutil first (handles the widest variety of formats),
    then falls back to iterating through common strptime patterns.

    Args:
        date_str: Date string in any common format (ISO 8601, RFC 2822,
                  human-readable like 'January 15, 2025', etc.)

    Returns:
        Timezone-aware datetime in UTC, or None if parsing fails entirely.
    """
    if not date_str or not date_str.strip():
        return None

    date_str = date_str.strip()

    # Attempt 1: python-dateutil (most flexible parser)
    try:
        from dateutil import parser as dateutil_parser

        parsed = dateutil_parser.parse(date_str)
        # Ensure timezone-aware (assume UTC if naive)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (ImportError, ValueError, OverflowError):
        # dateutil not installed or couldn't parse; fall through
        pass

    # Attempt 2: Try common strptime formats
    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(date_str, fmt)
            # Ensure timezone-aware (assume UTC if naive)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            continue

    logger.warning("Could not parse date string: %s", date_str)
    return None


# ============================================================================
# HTML Stripping Utility
# ============================================================================

# Regex to match HTML tags (including self-closing tags and attributes)
_HTML_TAG_RE = re.compile(r"<[^>]+>")

# Regex to match HTML entities like &amp; &lt; &#39; &#x27;
_HTML_ENTITY_RE = re.compile(r"&(?:#\d+|#x[\da-fA-F]+|\w+);")

# Regex to collapse multiple whitespace characters into a single space
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_html(text: str) -> str:
    """
    Remove HTML tags and entities, then collapse whitespace.

    This is intentionally simple (regex-based) rather than using a full HTML
    parser. We only need a rough character count of meaningful text, not a
    perfectly rendered document.

    Args:
        text: Raw text that may contain HTML markup.

    Returns:
        Cleaned text with HTML removed and whitespace normalized.
    """
    text = _HTML_TAG_RE.sub(" ", text)
    text = _HTML_ENTITY_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


# ============================================================================
# Validation Result Dataclasses
# ============================================================================


@dataclass
class ValidationResult:
    """
    Result of a single validation check (content or freshness).

    Attributes:
        is_valid: Whether the content passed this validation check.
        reason_code: Machine-readable code for the validation outcome.
            - 'ok'                : Passed validation.
            - 'content_empty'     : No content provided (None or empty string).
            - 'content_too_short' : Content under 100 meaningful characters.
            - 'stale_news'        : News/tech/RSS content older than 90 days.
            - 'stale_academic'    : Academic content older than 365 days.
            - 'stale_government'  : Government content older than 730 days.
            - 'stale_default'     : Uncategorized content older than 180 days.
            - 'date_unparseable'  : Published date could not be parsed.
            - 'date_missing'      : No published date provided.
        detail: Human-readable explanation of the validation outcome.
    """

    is_valid: bool
    reason_code: str
    detail: str


@dataclass
class PrePrintResult:
    """
    Result of pre-print detection analysis.

    Pre-prints are academic papers that have not undergone formal peer review.
    They may contain preliminary findings that are later revised or retracted.
    Flagging them allows downstream consumers to add appropriate caveats.

    Attributes:
        is_preprint: Whether the source appears to be a pre-print.
        confidence: Confidence level of the detection.
            - 'high'   : URL matches a known pre-print server (arXiv, bioRxiv, etc.)
            - 'medium' : Content contains pre-print terminology.
            - 'low'    : Academic-looking URL without DOI (weaker signal).
        indicators: List of specific signals that triggered the detection.
    """

    is_preprint: bool
    confidence: str  # 'high', 'medium', 'low'
    indicators: List[str] = field(default_factory=list)


@dataclass
class FullValidationResult:
    """
    Aggregated result of all validation checks on a single source.

    The top-level `is_valid` is True only if both content and freshness
    validations pass. Pre-print detection does NOT affect validity -- it is
    informational only, so pre-prints can still enter the pipeline with
    appropriate metadata.

    Attributes:
        content_validation: Result of content length/quality check.
        freshness_validation: Result of publication date freshness check.
        preprint_result: Pre-print detection result, or None if URL was empty.
        is_valid: True only when all blocking validations passed.
    """

    content_validation: ValidationResult
    freshness_validation: ValidationResult
    preprint_result: Optional[PrePrintResult]
    is_valid: bool


# ============================================================================
# Freshness Thresholds (in days)
# ============================================================================

# Category-specific freshness thresholds. Sources older than these limits
# are considered stale for that category. Rationale:
#
# - news/tech_blog/rss (90 days): News has a short relevance window. Surfacing
#   old news misleads users about current trends.
# - academic (365 days): Research papers remain relevant longer, but anything
#   over a year old is likely already known or superseded.
# - government (730 days / 2 years): Policy documents, regulations, and
#   government reports have long implementation timelines. A 2-year window
#   accommodates the slow pace of government action.
# - default (180 days): Conservative middle ground for uncategorized sources.

FRESHNESS_THRESHOLDS: dict[str, int] = {
    "news": 90,
    "tech_blog": 90,
    "rss": 90,
    "academic": 365,
    "government": 730,
}

# Fallback threshold when category is not in the map above.
DEFAULT_FRESHNESS_DAYS = 180


# ============================================================================
# Pre-Print Detection Constants
# ============================================================================

# Known pre-print server domains. Matching any of these in a URL is a
# high-confidence indicator that the source is a pre-print.
PREPRINT_DOMAINS = [
    "arxiv.org",
    "biorxiv.org",
    "medrxiv.org",
    "ssrn.com",
    "preprints.org",
]

# Content phrases that indicate a pre-print at medium confidence.
# These appear in abstracts, disclaimers, or metadata of non-peer-reviewed work.
PREPRINT_CONTENT_PHRASES = [
    "pre-print",
    "preprint",
    "not peer-reviewed",
    "not been peer-reviewed",
    "working paper",
    "under review",
    "submitted for publication",
]

# Regex pattern matching academic-looking URLs (e.g. /abs/2301.12345, /paper/123)
# Used as a weak signal for low-confidence pre-print detection.
_ACADEMIC_URL_RE = re.compile(
    r"(/abs/|/paper/|/publication/|/abstract/|/doi/|/articles?/)",
    re.IGNORECASE,
)

# DOI pattern -- presence of a DOI suggests the paper has been formally
# published, which reduces the likelihood of it being a pre-print.
_DOI_RE = re.compile(r"10\.\d{4,}/\S+")


# ============================================================================
# Minimum Content Length
# ============================================================================

# Sources with fewer than this many characters of meaningful text (after
# stripping HTML and whitespace) are rejected. 100 characters is roughly
# 15-20 words, which is the absolute minimum to extract any useful signal.
# Shorter texts are typically paywalled stubs, error pages, or empty feeds.
MIN_CONTENT_LENGTH = 100


# ============================================================================
# SourceValidator
# ============================================================================


class SourceValidator:
    """
    Validates source content quality, freshness, and provenance.

    This is a stateless utility class with no database or network dependencies.
    All methods are synchronous and deterministic, making them fast and easy
    to test.

    Usage:
        validator = SourceValidator()
        result = validator.validate_all(content, published_date, category, url)
    """

    def validate_content(self, content: Optional[str]) -> ValidationResult:
        """
        Validate that source content meets minimum quality requirements.

        Strips HTML tags, entities, and excess whitespace, then checks that
        at least 100 characters of meaningful text remain. This catches
        empty pages, paywall stubs, placeholder content, and error pages.

        Args:
            content: Raw content text, possibly containing HTML markup.
                     None or empty string is treated as missing content.

        Returns:
            ValidationResult with reason_code:
                - 'ok'                if content has >= 100 meaningful chars
                - 'content_empty'     if content is None or empty after stripping
                - 'content_too_short' if content has < 100 meaningful chars
        """
        # Handle None or empty input
        if not content or not content.strip():
            return ValidationResult(
                is_valid=False,
                reason_code="content_empty",
                detail="No content provided. Source may be paywalled, empty, or failed to load.",
            )

        # Strip HTML and normalize whitespace
        cleaned = _strip_html(content)

        if len(cleaned) < MIN_CONTENT_LENGTH:
            return ValidationResult(
                is_valid=False,
                reason_code="content_too_short",
                detail=(
                    f"Content has only {len(cleaned)} characters after cleaning "
                    f"(minimum: {MIN_CONTENT_LENGTH}). Source may be a stub, "
                    f"paywall notice, or error page."
                ),
            )

        return ValidationResult(
            is_valid=True,
            reason_code="ok",
            detail=f"Content has {len(cleaned)} characters after cleaning.",
        )

    def validate_freshness(
        self, published_date: Optional[str], category: str
    ) -> ValidationResult:
        """
        Validate that source content is fresh enough for its category.

        Different content categories have different relevance windows:
            - News / Tech blogs / RSS:  90 days
            - Academic / Research:     365 days
            - Government:             730 days (2 years)
            - Default (uncategorized): 180 days

        Sources without a parseable date pass with a warning, since missing
        dates are common in RSS feeds and should not block triage.

        Args:
            published_date: Date string in any common format (ISO 8601,
                           RFC 2822, human-readable). None if unknown.
            category: Source category key matching SourceCategory enum values
                     (e.g. 'news', 'academic', 'government', 'tech_blog', 'rss').

        Returns:
            ValidationResult with reason_code:
                - 'ok'              if date is within freshness threshold
                - 'date_missing'    if no date was provided (passes with warning)
                - 'date_unparseable' if date string could not be parsed (passes with warning)
                - 'stale_news'      if news/tech/rss content is too old
                - 'stale_academic'  if academic content is too old
                - 'stale_government' if government content is too old
                - 'stale_default'   if uncategorized content is too old
        """
        # No date provided -- pass with advisory
        if not published_date:
            return ValidationResult(
                is_valid=True,
                reason_code="date_missing",
                detail="No published date provided. Freshness check skipped.",
            )

        parsed = _parse_date(published_date)
        if parsed is None:
            return ValidationResult(
                is_valid=True,
                reason_code="date_unparseable",
                detail=f"Could not parse date '{published_date}'. Freshness check skipped.",
            )

        # Calculate age in days
        now = datetime.now(timezone.utc)
        age_days = (now - parsed).days

        # Negative age means the date is in the future -- treat as fresh
        if age_days < 0:
            return ValidationResult(
                is_valid=True,
                reason_code="ok",
                detail=f"Published date is {abs(age_days)} days in the future. Treating as fresh.",
            )

        # Look up threshold for this category
        category_lower = category.lower().strip()
        threshold = FRESHNESS_THRESHOLDS.get(category_lower, DEFAULT_FRESHNESS_DAYS)

        if age_days > threshold:
            # Determine the specific stale reason code based on category
            stale_reason = _stale_reason_code(category_lower)
            return ValidationResult(
                is_valid=False,
                reason_code=stale_reason,
                detail=(
                    f"Source is {age_days} days old, exceeding the {threshold}-day "
                    f"threshold for '{category}' content."
                ),
            )

        return ValidationResult(
            is_valid=True,
            reason_code="ok",
            detail=f"Source is {age_days} days old (threshold: {threshold} days for '{category}').",
        )

    def detect_preprint(
        self, url: str, content: Optional[str] = None
    ) -> PrePrintResult:
        """
        Detect whether a source is an academic pre-print.

        Detection uses a tiered confidence system:
            - High confidence:   URL matches a known pre-print server
                                 (arXiv, bioRxiv, medRxiv, SSRN, preprints.org).
            - Medium confidence: Content contains pre-print terminology
                                 ('preprint', 'not peer-reviewed', 'working paper', etc.).
            - Low confidence:    URL has academic patterns (e.g. /abs/, /paper/)
                                 but no DOI, suggesting it may not be formally published.

        Pre-print status is informational only and does NOT block the source
        from entering the pipeline. It allows downstream consumers to apply
        appropriate caveats and weighting.

        Args:
            url: Source URL to analyze for pre-print server domains.
            content: Optional content text to scan for pre-print terminology.

        Returns:
            PrePrintResult with is_preprint, confidence level, and indicators.
        """
        indicators: List[str] = []
        url_lower = (url or "").lower()

        # --- High confidence: known pre-print server domains ---
        for domain in PREPRINT_DOMAINS:
            if domain in url_lower:
                indicators.append(f"URL matches known pre-print server: {domain}")
                return PrePrintResult(
                    is_preprint=True,
                    confidence="high",
                    indicators=indicators,
                )

        # --- Medium confidence: content contains pre-print terminology ---
        if content:
            content_lower = content.lower()
            indicators.extend(
                f"Content contains pre-print phrase: '{phrase}'"
                for phrase in PREPRINT_CONTENT_PHRASES
                if phrase in content_lower
            )
            if indicators:
                return PrePrintResult(
                    is_preprint=True,
                    confidence="medium",
                    indicators=indicators,
                )

        # --- Low confidence: academic-looking URL without DOI ---
        if url_lower and _ACADEMIC_URL_RE.search(url_lower):
            # Check whether URL or content contains a DOI.
            # A DOI suggests formal publication, so we do NOT flag it.
            has_doi = bool(_DOI_RE.search(url_lower))
            if not has_doi and content:
                has_doi = bool(_DOI_RE.search(content))

            if not has_doi:
                indicators.append("Academic-looking URL pattern without DOI detected")
                return PrePrintResult(
                    is_preprint=True,
                    confidence="low",
                    indicators=indicators,
                )

        # --- Not a pre-print ---
        return PrePrintResult(
            is_preprint=False,
            confidence="low",
            indicators=[],
        )

    def validate_all(
        self,
        content: Optional[str],
        published_date: Optional[str],
        category: str,
        url: str,
    ) -> FullValidationResult:
        """
        Run all validation checks on a single source.

        Executes content validation, freshness validation, and pre-print
        detection in sequence. The top-level `is_valid` is True only when
        both content and freshness validations pass. Pre-print detection
        is informational and does not affect overall validity.

        Args:
            content: Raw content text (may contain HTML). None if unavailable.
            published_date: Publication date string in any common format.
                           None if unknown.
            category: Source category key (e.g. 'news', 'academic', 'government').
            url: Source URL for pre-print detection analysis.

        Returns:
            FullValidationResult aggregating all individual check results.
        """
        content_result = self.validate_content(content)
        freshness_result = self.validate_freshness(published_date, category)

        preprint_result = self.detect_preprint(url, content) if url else None
        # Overall validity requires both content and freshness to pass.
        # Pre-print status is informational and does not block sources.
        is_valid = content_result.is_valid and freshness_result.is_valid

        if not is_valid:
            # Log rejection for observability and debugging
            reasons = []
            if not content_result.is_valid:
                reasons.append(content_result.reason_code)
            if not freshness_result.is_valid:
                reasons.append(freshness_result.reason_code)
            logger.info(
                "Source rejected by validator: url=%s reasons=%s",
                url,
                reasons,
            )

        return FullValidationResult(
            content_validation=content_result,
            freshness_validation=freshness_result,
            preprint_result=preprint_result,
            is_valid=is_valid,
        )


# ============================================================================
# Internal Helpers
# ============================================================================


def _stale_reason_code(category: str) -> str:
    """
    Map a category to its specific stale reason code.

    Args:
        category: Lowercase category string.

    Returns:
        Reason code string like 'stale_news', 'stale_academic', etc.
    """
    if category in {"news", "tech_blog", "rss"}:
        return "stale_news"
    elif category == "academic":
        return "stale_academic"
    elif category == "government":
        return "stale_government"
    else:
        return "stale_default"
