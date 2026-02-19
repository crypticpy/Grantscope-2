"""
AI Service for GrantScope2 application.

Provides:
- Embedding generation for semantic search
- Triage (cheap, fast relevance filtering)
- Full analysis (classification, scoring, entity extraction)
- Entity extraction for graph building
"""

import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from functools import wraps
import openai

# Azure OpenAI deployment names
from app.openai_provider import (
    get_chat_deployment,
    get_chat_mini_deployment,
    get_embedding_deployment,
)
from app.taxonomy import PILLAR_NAMES

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds
BACKOFF_MULTIPLIER = 2.0
REQUEST_TIMEOUT = 60  # seconds

# Summary quality configuration
SUMMARY_MIN_WORDS = 150
SUMMARY_MAX_WORDS = 300
SUMMARY_STRUCTURE_KEYWORDS = {
    "problem_statement": [
        "challenge",
        "trend",
        "opportunity",
        "issue",
        "development",
        "emerging",
        "innovation",
        "technology",
        "advancement",
    ],
    "implications": [
        "implication",
        "impact",
        "effect",
        "affect",
        "consequence",
        "result",
        "influence",
        "municipal",
        "city",
        "government",
    ],
    "strategic": [
        "consider",
        "prepare",
        "action",
        "decision",
        "strategy",
        "recommend",
        "plan",
        "implement",
        "adopt",
        "evaluate",
    ],
}


def with_retry(max_retries: int = MAX_RETRIES):
    """
    Decorator for retrying async functions with exponential backoff.

    Handles OpenAI API errors and rate limits gracefully.
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            backoff = INITIAL_BACKOFF

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except openai.RateLimitError as e:
                    last_exception = e
                    wait_time = backoff * (BACKOFF_MULTIPLIER**attempt)
                    logger.warning(
                        f"Rate limited on {func.__name__}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                except openai.APITimeoutError as e:
                    last_exception = e
                    wait_time = backoff * (BACKOFF_MULTIPLIER**attempt)
                    logger.warning(
                        f"Timeout on {func.__name__}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                except openai.APIConnectionError as e:
                    last_exception = e
                    wait_time = backoff * (BACKOFF_MULTIPLIER**attempt)
                    logger.warning(
                        f"Connection error on {func.__name__}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                except openai.APIStatusError as e:
                    # Don't retry on 4xx errors (except 429 which is RateLimitError)
                    if 400 <= e.status_code < 500:
                        logger.error(
                            f"API error on {func.__name__}: {e.status_code} - {e.message}"
                        )
                        raise
                    last_exception = e
                    wait_time = backoff * (BACKOFF_MULTIPLIER**attempt)
                    logger.warning(
                        f"API error on {func.__name__}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait_time)

            logger.error(f"All {max_retries} retries exhausted for {func.__name__}")
            raise last_exception

        return wrapper

    return decorator


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class TriageResult:
    """Result of quick relevance triage."""

    is_relevant: bool
    confidence: float
    primary_pillar: Optional[str]
    reason: str
    relevance_level: str = "medium"  # "high", "medium", or "low"


@dataclass
class ExtractedEntity:
    """Entity extracted for graph storage."""

    name: str
    entity_type: str  # technology, organization, concept, person, location
    context: str  # How it appeared in the source


@dataclass
class AnalysisResult:
    """Full analysis result for a source."""

    # Summary
    summary: str
    key_excerpts: List[str]

    # Classification
    pillars: List[str]
    goals: List[str]
    steep_categories: List[str]
    anchors: List[str]

    # Horizon & Stage (kept for backward compat)
    horizon: str
    suggested_stage: int
    triage_score: int  # 1, 3, or 5

    # Scoring (all 1.0-5.0 except likelihood which is 1.0-9.0, and velocity/risk which are 1.0-10.0)
    credibility: float
    novelty: float
    likelihood: float
    impact: float
    relevance: float
    velocity: float  # Speed of trend development (1.0-10.0)
    risk: float  # Threat/uncertainty level (1.0-10.0)

    # Timing
    time_to_awareness_months: int
    time_to_prepare_months: int

    # Card suggestions
    suggested_card_name: str
    is_new_concept: bool

    # Pipeline lifecycle
    pipeline_status: str = "discovered"

    # Entities for graph
    entities: List[ExtractedEntity] = field(default_factory=list)

    # Reasoning (for debugging/auditing)
    reasoning: str = ""

    # Flag indicating whether scores are defaults (e.g., due to AI parse failure)
    scores_are_defaults: bool = False


@dataclass
class SummaryQualityResult:
    """Result of summary quality validation."""

    is_valid: bool
    word_count: int
    word_count_valid: bool
    structure_valid: bool
    structure_scores: Dict[str, float]  # Score for each structural element
    issues: List[str]  # List of quality issues found


# ============================================================================
# Summary Quality Validation
# ============================================================================


def validate_summary_quality(summary: str) -> SummaryQualityResult:
    """
    Validate summary quality against length and structure requirements.

    Checks:
    1. Word count is between 150-300 words
    2. Summary contains indicators of the 3-part structure:
       - Problem statement (challenge/trend/opportunity)
       - Implications (effects for municipal government)
       - Strategic considerations (actions/decisions)

    Args:
        summary: The summary text to validate

    Returns:
        SummaryQualityResult with validation details
    """
    issues = []

    # Word count validation
    words = summary.split()
    word_count = len(words)
    word_count_valid = SUMMARY_MIN_WORDS <= word_count <= SUMMARY_MAX_WORDS

    if word_count < SUMMARY_MIN_WORDS:
        issues.append(
            f"Summary too short: {word_count} words (minimum: {SUMMARY_MIN_WORDS})"
        )
    elif word_count > SUMMARY_MAX_WORDS:
        issues.append(
            f"Summary too long: {word_count} words (maximum: {SUMMARY_MAX_WORDS})"
        )

    # Structure validation - check for presence of key structural elements
    summary_lower = summary.lower()
    structure_scores = {}

    for element, keywords in SUMMARY_STRUCTURE_KEYWORDS.items():
        # Count how many keywords from each category are present
        matches = sum(bool(kw in summary_lower) for kw in keywords)
        # Normalize to 0-1 score (at least 2 matches for good score)
        score = min(matches / 2.0, 1.0)
        structure_scores[element] = score

        if score < 0.5:
            issues.append(
                f"Weak {element.replace('_', ' ')}: consider adding relevant context"
            )

    # Structure is valid if all elements have at least 0.5 score
    structure_valid = all(score >= 0.5 for score in structure_scores.values())

    # Overall validity requires both word count and structure
    is_valid = word_count_valid and structure_valid

    return SummaryQualityResult(
        is_valid=is_valid,
        word_count=word_count,
        word_count_valid=word_count_valid,
        structure_valid=structure_valid,
        structure_scores=structure_scores,
        issues=issues,
    )


def get_word_count(text: str) -> int:
    """Get the word count of a text string."""
    return len(text.split())


# ============================================================================
# Prompts
# ============================================================================

TRIAGE_PROMPT = """You are a triage analyst for the City of Austin's grant discovery and management platform.

Evaluate if this content describes a grant opportunity, funding announcement, RFP, cooperative agreement, or other funding-related content relevant to City of Austin departments.

Indicators of a relevant grant opportunity:
- Federal grants (EPA, HUD, DOT, FEMA, HHS, DOJ, DOE, USDA, NSF, etc.)
- State of Texas grants (TCEQ, TxDOT, TWDB, OOG, TEA, HHSC, GLO, etc.)
- Foundation and private grants (Bloomberg, Kresge, Knight, Ford, etc.)
- Cooperative agreements, formula grants, competitive grants
- Notices of Funding Opportunity (NOFO), Requests for Proposals (RFP)
- Grant renewals, supplemental funding, or continuation awards
- Funding forecasts or pre-announcement notices

Relevant funding areas for City of Austin:
- Health & social services, behavioral health, youth programs
- Public safety, emergency management, justice reform
- Housing, homelessness prevention, community development
- Infrastructure, transportation, water, energy
- Environment, climate resilience, sustainability, parks
- Cultural programs, libraries, arts, workforce development
- Technology modernization, cybersecurity, data & innovation
- Equity, accessibility, civic engagement, immigrant services

Article Title: {title}
Article Content: {content}

Rate the relevance level:
- "high": This is a specific grant opportunity, NOFO, or funding announcement directly relevant to one or more City of Austin departments. A grants manager would want to evaluate this immediately.
- "medium": This is funding-related content (grant tips, policy changes affecting funding, upcoming grant cycles) that could inform grant strategy. Not a specific opportunity but useful context.
- "low": Not related to grants, funding opportunities, or municipal funding strategy.

Respond with JSON:
{{
  "relevance_level": "high|medium|low",
  "is_relevant": true/false,
  "confidence": 0.0-1.0,
  "primary_pillar": "HS|PS|HD|IN|EN|CE|TG|EQ|null",
  "reason": "1-2 sentence explanation of why this is or isn't a relevant grant opportunity for the City of Austin"
}}

Grant Category Codes:
- HS: Health & Human Services (public health, behavioral health, social services, youth)
- PS: Public Safety & Emergency Management (law enforcement, fire, EMS, justice, FEMA)
- HD: Housing & Community Development (affordable housing, homelessness, planning)
- IN: Infrastructure & Transportation (roads, water, energy, facilities, telecom)
- EN: Environment & Sustainability (climate, conservation, parks, resilience)
- CE: Cultural & Economic Development (libraries, arts, education, workforce)
- TG: Technology & Government Innovation (IT, cybersecurity, data, e-government)
- EQ: Equity & Engagement (civil rights, accessibility, civic engagement)
"""

ANALYSIS_PROMPT = """You are a grant opportunity analyst for the City of Austin's grant discovery platform.

Analyze this content to extract structured grant opportunity metadata and evaluate its strategic fit for City of Austin departments.

SUMMARY STRUCTURE REQUIREMENTS:
Your summary MUST follow this grant-focused structure:
1. Opportunity: What is being funded, by whom, and for how much?
2. Eligibility & Fit: Who can apply and how does this align with Austin's needs?
3. Action Required: What should Austin's grants team do next (apply, monitor, prepare)?

The summary should be 3-5 sentences that flow naturally while covering all three elements.

GRANT CATEGORY REFERENCE:
Categories (use these as pillar codes):
- HS (Health & Human Services): Public health, behavioral health, social services, youth development
- PS (Public Safety & Emergency Management): Law enforcement, fire, EMS, emergency management, justice
- HD (Housing & Community Development): Affordable housing, homelessness, community development, planning
- IN (Infrastructure & Transportation): Roads, water, energy, facilities, telecommunications
- EN (Environment & Sustainability): Climate, conservation, parks, resilience, sustainability
- CE (Cultural & Economic Development): Libraries, museums, arts, education, workforce development
- TG (Technology & Government Innovation): IT modernization, data, cybersecurity, innovation, e-government
- EQ (Equity & Engagement): Civil rights, accessibility, language access, civic participation

KEY AUSTIN DEPARTMENTS (for eligibility and fit assessment):
- APH (Austin Public Health), APD (Austin Police), AFD (Austin Fire), EMS, HSEM (Homeland Security)
- AWU (Austin Water), ATD (Transportation), AE (Austin Energy), ARR (Resource Recovery)
- PARD (Parks & Recreation), APL (Library), EDD (Economic Development), NHCD (Housing & Planning)
- CTM (Communications & Technology), OOI (Office of Innovation), WPD (Watershed Protection)
- OEQ (Office of Equity), OII (Immigrant Integration), COS (Office of Sustainability)
- CMO (City Manager Office), DSD (Development Services), PWD (Public Works)

GRANT-SPECIFIC SCORING:

Alignment Score (0-100): How well does this grant match Austin's strategic priorities and department needs?
0-25=Poor fit, 26-50=Partial fit, 51-75=Good fit, 76-100=Excellent fit

Readiness Score (0-100): Can Austin realistically apply? Consider staff capacity, existing programs, infrastructure.
0-25=Not ready, 26-50=Would need significant preparation, 51-75=Reasonably ready, 76-100=Highly prepared

Competition Score (0-100): How competitive is this grant? Higher = less competition = better chance.
0-25=Extremely competitive (many applicants, low award rate), 26-50=Competitive, 51-75=Moderate competition, 76-100=Low competition (formula grant, few eligible applicants)

Urgency Score (0-100): How soon is the deadline?
0-25=No deadline or >6 months, 26-50=3-6 months, 51-75=30-90 days, 76-100=<30 days (urgent)

Probability Score (0-100): Overall estimated probability of successful application.
0-25=Low probability, 26-50=Below average, 51-75=Above average, 76-100=High probability

HORIZON MAPPING (for backward compatibility):
- H1 = Urgent/Active grants (deadlines < 30 days) — maps to stages 7-8
- H2 = Approaching grants (deadlines 30-90 days) — maps to stages 3-6
- H3 = Planning/forecasted grants (deadlines > 90 days or future) — maps to stages 1-2

Grant Lifecycle Stages (mapped to 1-8 for compatibility):
1-2 = Forecasted (pre-announcement, upcoming grant cycle)
3-4 = Open (recently posted, accepting applications)
5-6 = Active (applications being accepted, mid-cycle)
7-8 = Closing soon / Closed (deadline imminent or passed)

Triage Scores (grant context):
1=Routine/recurring grant (expected annual cycle)
3=Notable opportunity (good fit, standard process)
5=Exceptional opportunity (high value, strong fit, rare or new program)

LEGACY SCORING (maintain for downstream compatibility):
Credibility (1.0-5.0): Source reliability. Federal register/grants.gov=5, state agencies=4, foundations=3, news reports=2, unverified=1
Novelty (1.0-5.0): Is this a new program? 5=Brand new program, 3=Modified existing, 1=Recurring unchanged
Likelihood (1.0-9.0): Likelihood Austin would qualify. 9=Guaranteed eligible, 5=Likely eligible, 1=Unlikely
Impact (1.0-5.0): Potential impact on Austin services. 5=Transformative, 3=Meaningful, 1=Minimal
Relevance (1.0-5.0): Direct relevance to Austin priorities. 5=Core priority, 3=Related, 1=Tangential
Velocity (1.0-10.0): How fast must Austin act? 10=Immediate action, 5=Weeks to prepare, 1=Months available
Risk (1.0-10.0): Risk of NOT pursuing. 10=Critical funding gap, 5=Missed opportunity, 1=Low stakes

Article Title: {title}
Source: {source}
Published: {published_at}
Content: {content}

Respond with JSON:
{{
  "summary": "3-5 sentence grant opportunity summary: what is being funded, who is eligible, key requirements, and strategic fit for Austin",
  "key_excerpts": ["relevant quote 1", "relevant quote 2"],

  "pillars": ["XX"],
  "goals": [],
  "steep_categories": [],
  "anchors": [],

  "grant_title": "Official grant title or program name",
  "grantor": "Funding agency or organization",
  "grant_type": "federal|state|foundation|local|other",
  "funding_amount_min": null,
  "funding_amount_max": null,
  "deadline": "YYYY-MM-DD or null",
  "cfda_number": "XX.XXX or null",
  "eligibility_summary": "Who can apply and key requirements",
  "match_requirement": "Description of matching funds requirement or null",
  "grant_lifecycle": "open|closing_soon|closed|awarded|forecasted",
  "deadline_urgency": "urgent|approaching|planning|null",

  "alignment_score": 0-100,
  "readiness_score": 0-100,
  "competition_score": 0-100,
  "urgency_score": 0-100,
  "probability_score": 0-100,

  "pipeline_status": "discovered",
  "horizon": "H1|H2|H3",
  "suggested_stage": 1-8,
  "triage_score": 1|3|5,

  "credibility": 1.0-5.0,
  "novelty": 1.0-5.0,
  "likelihood": 1.0-9.0,
  "impact": 1.0-5.0,
  "relevance": 1.0-5.0,
  "velocity": 1.0-10.0,
  "risk": 1.0-10.0,

  "suggested_card_name": "Concise grant opportunity name (2-6 words)",
  "is_new_concept": true/false,

  "entities": [
    {{"name": "entity name", "type": "organization|program|regulation", "context": "brief context"}}
  ],

  "reasoning": "Brief explanation of classification and scoring rationale"
}}
"""

DEEP_RESEARCH_REPORT_PROMPT = """You are a grant analyst creating a comprehensive grant opportunity assessment report for City of Austin decision-makers and grants management staff.

Generate an in-depth grant opportunity assessment for "{card_name}" for the City of Austin's grant discovery platform.

CURRENT CARD INFORMATION:
Summary: {current_summary}
Description: {current_description}
Pipeline Status: {pipeline_status}
Pillar: {pillar}

GPT RESEARCHER FINDINGS:
{gpt_researcher_report}

ANALYZED SOURCE INSIGHTS:
{source_insights}

EXTRACTED ENTITIES:
{entities}

{austin_context}

---

Create a COMPREHENSIVE grant opportunity assessment report with the following sections. Be specific, cite grant details, and provide actionable guidance for the grants team.

## GRANT OVERVIEW
- Official grant/program title and CFDA/ALN number (if applicable)
- Funding agency and program office
- Funding range (minimum and maximum award amounts)
- Application deadline and grant period/duration
- Grant type (competitive, formula, cooperative agreement, pass-through)
- Total program funding available
- Expected number of awards

## STRATEGIC FIT ANALYSIS
- How this grant aligns with Austin's strategic priorities
- Which City of Austin departments would benefit (be specific: APH, ATD, AWU, PARD, etc.)
- Connection to current city initiatives, programs, or capital improvement plans
- How this funding could advance equity goals and underserved communities
- Alignment with City Council priorities and City Manager directives

## ELIGIBILITY ASSESSMENT
- Eligible applicant types and whether City of Austin qualifies
- Geographic eligibility requirements
- Population or demographic requirements
- Required certifications, designations, or prior experience
- Any disqualifying factors for Austin
- Whether sub-recipients or partners are permitted/required

## BUDGET & MATCH ANALYSIS
- Funding amount range and typical award size
- Cost-sharing or matching fund requirements (percentage and type)
- Allowable and unallowable costs
- Indirect cost rate considerations
- Budget period and multi-year funding structure
- Potential sources for matching funds within Austin's budget

## COMPETITION ANALYSIS
- Historical award data (number of applicants vs. awards in prior years)
- Typical success rate for similar applications
- Known competitors (other Texas cities, peer municipalities)
- Austin's competitive advantages for this specific grant
- Austin's competitive disadvantages or gaps to address
- Whether Austin has previously applied for or received this grant

## APPLICATION REQUIREMENTS
- Key documents and certifications needed
- Narrative sections and page limits
- Required partnerships or letters of support
- Data and evidence requirements
- Environmental review or other compliance requirements
- Estimated level of effort to prepare the application (staff hours, timeline)

## RECOMMENDATIONS
(Provide a clear GO / CONDITIONAL GO / NO-GO recommendation with detailed reasoning)

For a GO or CONDITIONAL GO recommendation, include:
1. Lead department(s) and recommended project manager
2. Application timeline with key milestones
3. Internal approvals needed (City Manager, Council authorization, etc.)
4. Partners or co-applicants to engage
5. Budget and match funding strategy
6. Specific conditions that must be met (for CONDITIONAL GO)

For a NO-GO recommendation, explain:
1. Primary reasons for not pursuing
2. Whether to monitor for future cycles
3. Alternative funding sources to explore instead

## NEXT STEPS
(Numbered list of specific, time-bound actions)
- Immediate actions (this week)
- Short-term actions (next 30 days)
- Pre-submission actions (before deadline)
- Include specific staff roles, meetings to schedule, and documents to prepare

---

Important guidelines:
- Be SPECIFIC with grant details: amounts, dates, CFDA numbers, agency contacts
- Reference the ACTUAL grant requirements from the source materials
- Map recommendations to SPECIFIC Austin departments by abbreviation (APH, ATD, etc.)
- Make next steps ACTIONABLE with clear owners and timelines
- Note UNCERTAINTIES and information gaps that need to be resolved
- Include any relevant federal/state compliance requirements (UGG, 2 CFR 200, etc.)
- Keep the report between 2000-3000 words
- Use markdown formatting for readability
- When citing findings from the analyzed sources, reference them by their title in the text
- DO NOT include a Sources & Methodology section - this will be appended automatically
"""

ENTITY_EXTRACTION_PROMPT = """Extract key entities from this research content for building a knowledge graph.

Content: {content}

Extract:
1. Technologies/Concepts: Specific technologies, methodologies, or concepts mentioned
2. Organizations: Companies, agencies, universities, cities involved
3. People: Key individuals mentioned (researchers, executives, officials)
4. Locations: Cities, regions, countries where implementations are happening
5. Relationships: How entities relate (implements, develops, partners_with, competes_with, regulates)

Respond with JSON:
{{
  "entities": [
    {{"name": "Entity Name", "type": "technology|organization|concept|person|location", "context": "brief context"}}
  ],
  "relationships": [
    {{"source": "Entity A", "relationship": "implements|develops|partners_with|competes_with|regulates|located_in", "target": "Entity B"}}
  ]
}}
"""

SIGNAL_PROFILE_PROMPT = """You are a strategic intelligence analyst for the City of Austin's horizon scanning system.

Generate a comprehensive signal profile for the following emerging trend/signal. This profile will be the primary reference document for city officials evaluating this signal.

SIGNAL: {signal_name}
INITIAL ASSESSMENT: {signal_summary}
STRATEGIC PILLAR: {pillar_name}
PIPELINE STATUS: {pipeline_status}

SOURCE EVIDENCE ({source_count} sources):
{source_details}

Generate a profile with these sections (use markdown formatting):

## Overview
What this signal is, why it matters, and how it connects to broader trends. Provide context that helps a non-expert understand the significance. (2-3 paragraphs)

## Key Developments
Specific examples, data points, timelines, and evidence from the sources. Include names of organizations, programs, technologies, and cities involved. Be concrete — cite specific examples rather than making general statements.

## Municipal Relevance
How this signal specifically impacts city government operations, service delivery, budgets, or strategic planning. What departments or functions are most affected? Reference specific Austin strategic priorities where applicable.

## What to Watch
Key indicators that would signal acceleration or deceleration of this trend. Upcoming milestones, decision points, or events that the team should monitor. What would trigger a need for immediate action?

GUIDELINES:
- Write 500-800 words total
- Be SPECIFIC — use names, dates, numbers, and examples from the sources
- Write for a municipal government audience — city managers, department heads, elected officials
- Avoid jargon without explanation
- Each section should have substantive content, not just headers
- If sources are thin, acknowledge gaps rather than fabricating details
- Do NOT include a sources section — that is handled separately
"""


# ============================================================================
# AI Service Class
# ============================================================================


class AIService:
    """Service for AI-powered analysis and classification."""

    def __init__(self, openai_client: openai.AsyncOpenAI):
        """
        Initialize the AI service.

        Args:
            openai_client: AsyncOpenAI client for async operations
        """
        self.client = openai_client

    @with_retry(max_retries=MAX_RETRIES)
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for text using OpenAI.

        Args:
            text: Text to embed (will be truncated to ~8000 chars)

        Returns:
            1536-dimensional embedding vector
        """
        # Truncate to stay within token limits
        truncated = text[:8000] if len(text) > 8000 else text

        logger.debug(f"Generating embedding for text ({len(truncated)} chars)")

        response = self.client.embeddings.create(
            model=get_embedding_deployment(), input=truncated, timeout=REQUEST_TIMEOUT
        )

        return response.data[0].embedding

    @with_retry(max_retries=MAX_RETRIES)
    async def triage_source(self, title: str, content: str) -> TriageResult:
        """
        Quick relevance check for a source using cheap model.

        Args:
            title: Source title
            content: Source content (will be truncated)

        Returns:
            TriageResult with relevance decision
        """
        prompt = TRIAGE_PROMPT.format(
            title=title,
            content=content[:4000],  # Increased from 2000 for better context
        )

        logger.debug(f"Triaging source: {title[:50]}...")

        response = self.client.chat.completions.create(
            model=get_chat_mini_deployment(),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=200,
            timeout=REQUEST_TIMEOUT,
        )

        try:
            result = json.loads(response.choices[0].message.content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse triage response: {e}")
            return TriageResult(
                is_relevant=False,
                confidence=0.0,
                primary_pillar=None,
                reason="Parse error",
                relevance_level="low",
            )

        return TriageResult(
            is_relevant=result.get("is_relevant", False),
            confidence=result.get("confidence", 0.0),
            primary_pillar=result.get("primary_pillar"),
            reason=result.get("reason", ""),
            relevance_level=result.get("relevance_level", "medium"),
        )

    async def generate_source_title(self, url: str, content_snippet: str) -> str:
        """
        Generate a descriptive title for a source using a cheap model.
        Useful for PDFs and sources without proper titles.

        Args:
            url: Source URL (for context)
            content_snippet: First ~1000 chars of the source content

        Returns:
            Generated title string
        """
        prompt = f"""Generate a concise, descriptive title (under 100 characters) for this document.

URL: {url}
Content excerpt:
{content_snippet[:1000]}

Respond with ONLY the title text, nothing else."""

        try:
            response = self.client.chat.completions.create(
                model=get_chat_mini_deployment(),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50,
                timeout=15,
            )
            title = response.choices[0].message.content.strip().strip('"').strip("'")
            return title[:200] if title else "Untitled"
        except Exception as e:
            logger.warning(f"Title generation failed: {e}")
            return "Untitled"

    @with_retry(max_retries=MAX_RETRIES)
    async def analyze_source(
        self, title: str, content: str, source_name: str, published_at: str
    ) -> AnalysisResult:
        """
        Full analysis of a source using powerful model.

        Args:
            title: Source title
            content: Full source content
            source_name: Publication/source name
            published_at: Publication date string

        Returns:
            AnalysisResult with full classification and scoring
        """
        prompt = ANALYSIS_PROMPT.format(
            title=title,
            content=content[:6000],  # More content for full analysis
            source=source_name,
            published_at=published_at,
        )

        logger.info(f"Analyzing source: {title[:50]}...")

        response = self.client.chat.completions.create(
            model=get_chat_deployment(),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=1500,
            timeout=REQUEST_TIMEOUT * 2,  # Longer timeout for full analysis
        )

        try:
            result = json.loads(response.choices[0].message.content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse analysis response: {e}")
            # Return default analysis on parse error
            return AnalysisResult(
                summary=f"Analysis failed for: {title}",
                key_excerpts=[],
                pillars=[],
                goals=[],
                steep_categories=[],
                anchors=[],
                horizon="H2",
                suggested_stage=4,
                triage_score=3,
                pipeline_status="discovered",
                credibility=3.0,
                novelty=3.0,
                likelihood=5.0,
                impact=3.0,
                relevance=3.0,
                velocity=5.0,
                risk=5.0,
                time_to_awareness_months=12,
                time_to_prepare_months=24,
                suggested_card_name=title[:50],
                is_new_concept=False,
                reasoning="Parse error in analysis",
                scores_are_defaults=True,
            )

        entities = [
            ExtractedEntity(
                name=ent.get("name", ""),
                entity_type=ent.get("type", "concept"),
                context=ent.get("context", ""),
            )
            for ent in result.get("entities", [])
        ]
        # Validate summary quality
        summary = result.get("summary", "")
        quality_result = validate_summary_quality(summary)

        if not quality_result.is_valid:
            logger.warning(
                f"Summary quality issues for '{title[:50]}...': "
                f"word_count={quality_result.word_count}, "
                f"issues={quality_result.issues}"
            )
        else:
            logger.debug(
                f"Summary quality validated for '{title[:50]}...': "
                f"word_count={quality_result.word_count}, "
                f"structure_scores={quality_result.structure_scores}"
            )

        # Extract raw scores and clamp to valid ranges
        raw_credibility = result.get("credibility", 3.0)
        raw_novelty = result.get("novelty", 3.0)
        raw_likelihood = result.get("likelihood", 5.0)
        raw_impact = result.get("impact", 3.0)
        raw_relevance = result.get("relevance", 3.0)
        raw_velocity = result.get("velocity", 5.0)
        raw_risk = result.get("risk", 5.0)

        # Clamp scores to their documented valid ranges
        clamped_credibility = max(1.0, min(float(raw_credibility), 5.0))
        clamped_novelty = max(1.0, min(float(raw_novelty), 5.0))
        clamped_likelihood = max(1.0, min(float(raw_likelihood), 9.0))
        clamped_impact = max(1.0, min(float(raw_impact), 5.0))
        clamped_relevance = max(1.0, min(float(raw_relevance), 5.0))
        clamped_velocity = max(1.0, min(float(raw_velocity), 10.0))
        clamped_risk = max(1.0, min(float(raw_risk), 10.0))

        # Log if any scores were clamped (indicates AI returned out-of-range values)
        if (
            clamped_credibility != float(raw_credibility)
            or clamped_novelty != float(raw_novelty)
            or clamped_likelihood != float(raw_likelihood)
            or clamped_impact != float(raw_impact)
            or clamped_relevance != float(raw_relevance)
            or clamped_velocity != float(raw_velocity)
            or clamped_risk != float(raw_risk)
        ):
            logger.warning(
                f"Scores clamped for '{title[:50]}...': "
                f"credibility={raw_credibility}->{clamped_credibility}, "
                f"novelty={raw_novelty}->{clamped_novelty}, "
                f"likelihood={raw_likelihood}->{clamped_likelihood}, "
                f"impact={raw_impact}->{clamped_impact}, "
                f"relevance={raw_relevance}->{clamped_relevance}, "
                f"velocity={raw_velocity}->{clamped_velocity}, "
                f"risk={raw_risk}->{clamped_risk}"
            )

        return AnalysisResult(
            summary=summary,
            key_excerpts=result.get("key_excerpts", []),
            pillars=result.get("pillars", []),
            goals=result.get("goals", []),
            steep_categories=result.get("steep_categories", []),
            anchors=result.get("anchors", []),
            horizon=result.get("horizon", "H2"),
            suggested_stage=result.get("suggested_stage", 4),
            triage_score=result.get("triage_score", 3),
            pipeline_status=result.get("pipeline_status", "discovered"),
            credibility=clamped_credibility,
            novelty=clamped_novelty,
            likelihood=clamped_likelihood,
            impact=clamped_impact,
            relevance=clamped_relevance,
            velocity=clamped_velocity,
            risk=clamped_risk,
            time_to_awareness_months=result.get("time_to_awareness_months", 12),
            time_to_prepare_months=result.get("time_to_prepare_months", 24),
            suggested_card_name=result.get("suggested_card_name", title[:50]),
            is_new_concept=result.get("is_new_concept", False),
            entities=entities,
            reasoning=result.get("reasoning", ""),
        )

    @with_retry(max_retries=MAX_RETRIES)
    async def extract_entities(self, content: str) -> Dict[str, Any]:
        """
        Extract entities and relationships for graph building.

        Args:
            content: Text content to analyze

        Returns:
            Dict with entities and relationships lists
        """
        prompt = ENTITY_EXTRACTION_PROMPT.format(content=content[:4000])

        logger.debug("Extracting entities from content")

        response = self.client.chat.completions.create(
            model=get_chat_mini_deployment(),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=800,
            timeout=REQUEST_TIMEOUT,
        )

        try:
            return json.loads(response.choices[0].message.content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse entity extraction response: {e}")
            return {"entities": [], "relationships": []}

    @with_retry(max_retries=MAX_RETRIES)
    async def check_card_match(
        self,
        source_summary: str,
        source_card_name: str,
        existing_card_name: str,
        existing_card_summary: str,
    ) -> Dict[str, Any]:
        """
        Determine if a source belongs to an existing card or is new.

        Args:
            source_summary: AI summary of the source
            source_card_name: Suggested card name from analysis
            existing_card_name: Name of potentially matching card
            existing_card_summary: Summary of potentially matching card

        Returns:
            Dict with is_match, confidence, reasoning
        """
        prompt = f"""You are helping a municipal horizon scanning system decide whether a newly discovered article should be ADDED to an existing card or whether it represents a TRULY NEW concept.

IMPORTANT GUIDANCE:
- PREFER adding to existing cards over creating new ones
- Only say "not a match" if the concepts are fundamentally different
- Similar concepts with different aspects/angles = SAME CARD
- Same technology/trend in different contexts = SAME CARD
- Evolution or update of existing concept = SAME CARD

EXAMPLES OF MATCHES (is_match = true):
- "AI Traffic Management" article → existing "Smart Traffic Systems" card ✓
- "Electric Bus Pilot in Portland" article → existing "Electric Public Transit" card ✓
- "5G Network Security Concerns" article → existing "5G Infrastructure" card ✓
- "Drone Delivery for Medications" article → existing "Drone Delivery Services" card ✓

EXAMPLES OF NON-MATCHES (is_match = false):
- "Quantum Computing Advances" article → existing "AI Traffic Management" card ✗
- "Urban Farming Initiative" article → existing "Electric Vehicle Charging" card ✗

EXISTING CARD:
Name: {existing_card_name}
Summary: {existing_card_summary}

NEW ARTICLE:
Suggested concept: {source_card_name}
Summary: {source_summary}

Question: Is this article about the same GENERAL TOPIC AREA as the existing card?
Even if the specific focus differs, they should be matched if they're in the same technology/trend domain.

Respond with JSON:
{{
  "is_match": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation of why they match or don't match"
}}
"""

        logger.debug(f"Checking card match: {source_card_name} vs {existing_card_name}")

        response = self.client.chat.completions.create(
            model=get_chat_mini_deployment(),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=300,
            timeout=REQUEST_TIMEOUT,
        )

        try:
            return json.loads(response.choices[0].message.content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse card match response: {e}")
            return {"is_match": False, "confidence": 0.0, "reasoning": "Parse error"}

    @with_retry(max_retries=MAX_RETRIES)
    async def enhance_card_from_research(
        self,
        current_name: str,
        current_summary: str,
        current_description: str,
        research_report: str,
        source_summaries: List[str],
    ) -> Dict[str, str]:
        """
        Generate enhanced card summary and description based on research findings.

        Args:
            current_name: Current card name
            current_summary: Current card summary
            current_description: Current card description
            research_report: Full research report from GPT Researcher
            source_summaries: List of AI summaries from analyzed sources

        Returns:
            Dict with enhanced_summary and enhanced_description
        """
        # Combine source insights
        source_insights = "\n".join([f"- {s}" for s in source_summaries[:5]])

        # Detect if the existing description is a rich structured profile
        is_structured = any(
            hdr in (current_description or "")
            for hdr in [
                "## Overview",
                "## Key Developments",
                "## Municipal Relevance",
                "## What to Watch",
            ]
        )
        desc_length = len(current_description or "")

        if is_structured and desc_length > 500:
            # Rich profile exists — integrate new findings into the existing structure
            length_guidance = (
                f"The current description is a {desc_length}-character structured profile with markdown sections. "
                f"You MUST preserve this structure and length. Update each section with new evidence from the research. "
                f"Your enhanced_description MUST be at least {desc_length} characters and use the same markdown sections."
            )
            format_guidance = (
                "Maintain the existing markdown structure (## Overview, ## Key Developments, "
                "## Municipal Relevance, ## What to Watch). Add new findings to the appropriate "
                "sections. Do NOT shorten or flatten the description into plain paragraphs."
            )
        else:
            length_guidance = (
                "Write a comprehensive description (2-3 substantial paragraphs) covering key developments, "
                "implications, and municipal relevance."
            )
            format_guidance = "Use clear prose paragraphs. Include specific names, dates, and data points."

        prompt = f"""You are enhancing a strategic discovery card based on new research findings.
The card tracks an emerging technology, trend, or innovation relevant to municipal government.

CURRENT CARD:
Name: {current_name}
Summary: {current_summary}
Description: {current_description}

NEW RESEARCH FINDINGS:
{research_report[:4000] if research_report else "No detailed report available"}

KEY SOURCE INSIGHTS:
{source_insights or "No specific source insights"}

TASK:
1. Enhance the card's summary (1-2 sentences) to incorporate the most significant new findings
2. Enhance the description:
   {length_guidance}
   {format_guidance}
   - Integrate new findings from the research — do NOT remove existing valuable content
   - Be factual, specific, and actionable — cite names, dates, numbers
   - Preserve ALL important information from the original description

CRITICAL: The enhanced_description must be AT LEAST as long as the current description.
Do NOT condense a detailed description into a shorter summary.

Respond with JSON:
{{
  "enhanced_summary": "Updated 1-2 sentence summary with key new insights",
  "enhanced_description": "Updated description integrating new research (preserve structure and length)",
  "key_updates": ["List of 2-3 most significant new findings"]
}}
"""

        logger.debug(f"Enhancing card from research: {current_name}")

        # Use higher max_tokens for structured profiles to avoid truncation
        max_tokens = 3000 if is_structured else 1500

        response = self.client.chat.completions.create(
            model=get_chat_deployment(),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=max_tokens,
            timeout=REQUEST_TIMEOUT,
        )

        try:
            return json.loads(response.choices[0].message.content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse card enhancement response: {e}")
            return {
                "enhanced_summary": current_summary,
                "enhanced_description": current_description,
                "key_updates": [],
            }

    async def generate_signal_profile(
        self,
        signal_name: str,
        signal_summary: str,
        pillar_id: str,
        horizon: str = "",
        source_analyses: List[Dict] = None,
        pipeline_status: str = "discovered",
    ) -> str:
        """
        Generate a rich signal profile from existing source analyses.
        No web search needed — synthesizes from data we already have.

        Args:
            signal_name: Name of the signal/card
            signal_summary: Brief summary from signal agent
            pillar_id: Strategic pillar code (CH, EW, HG, etc.)
            horizon: H1, H2, or H3 (kept for backward compat)
            source_analyses: List of dicts with keys: title, url, summary, key_excerpts, content
            pipeline_status: Pipeline lifecycle status (discovered, evaluating, etc.)

        Returns:
            Markdown formatted profile (500-800 words)
        """
        if source_analyses is None:
            source_analyses = []
        pillar_name = PILLAR_NAMES.get(pillar_id, pillar_id or "General")

        # Build source details for the prompt
        source_details_parts = []
        for i, src in enumerate(source_analyses[:10], 1):
            title = src.get("title", "Untitled")
            url = src.get("url", "")
            summary = src.get("summary", "")[:400]
            excerpts = src.get("key_excerpts", [])
            content = src.get("content", "")[:500]

            part = f"### Source {i}: {title}"
            if url:
                part += f"\nURL: {url}"
            if summary:
                part += f"\nSummary: {summary}"
            if excerpts:
                for ex in excerpts[:2]:
                    part += f'\nKey excerpt: "{ex[:200]}"'
            elif content:
                part += f"\nContent snippet: {content}"
            source_details_parts.append(part)

        source_details = (
            "\n\n".join(source_details_parts)
            if source_details_parts
            else "No detailed source data available."
        )

        prompt = SIGNAL_PROFILE_PROMPT.format(
            signal_name=signal_name,
            signal_summary=signal_summary or "No initial summary provided.",
            pillar_name=pillar_name,
            pipeline_status=pipeline_status or "discovered",
            source_count=len(source_analyses),
            source_details=source_details,
        )

        try:
            response = self.client.chat.completions.create(
                model=get_chat_deployment(),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                timeout=REQUEST_TIMEOUT * 2,
            )
            profile = response.choices[0].message.content.strip()
            logger.info(
                f"Generated signal profile for '{signal_name[:50]}' ({len(profile)} chars)"
            )
            return profile
        except Exception as e:
            logger.error(
                f"Signal profile generation failed for '{signal_name[:50]}': {e}"
            )
            # Return a minimal profile rather than nothing
            return f"""## Overview

{signal_summary or signal_name}

*Profile generation encountered an error. Run deep research or try again later to generate a full profile.*
"""

    async def analyze_trend_trajectory(
        self,
        signal_name: str,
        source_dates: List[str],
        source_summaries: List[str],
    ) -> str:
        """Classify the overall trend trajectory of a signal.

        Uses GPT-4o-mini to classify based on source publication patterns
        and content themes.

        Args:
            signal_name: Name of the signal/card.
            source_dates: List of ISO date strings for recent sources.
            source_summaries: List of brief summaries for recent sources.

        Returns:
            One of: accelerating, stable, emerging, declining, unknown
        """
        if not source_summaries:
            return "unknown"

        # Build a compact context for the classifier
        timeline_parts = []
        for date, summary in zip(source_dates[:15], source_summaries[:15]):
            short_date = date[:10] if date else "unknown"
            short_summary = (summary or "")[:150]
            timeline_parts.append(f"- [{short_date}] {short_summary}")

        timeline_text = "\n".join(timeline_parts) if timeline_parts else "No data"

        prompt = f"""Classify the trend trajectory for the signal "{signal_name}" based on its recent source publications.

Source timeline (newest first):
{timeline_text}

Based on the publication frequency, recency, and content themes, classify this signal's trajectory as exactly ONE of:
- **accelerating**: Rapidly increasing coverage, growing momentum, more frequent and urgent publications
- **stable**: Consistent coverage over time, no major shifts in momentum or urgency
- **emerging**: Early-stage signal with sparse but growing coverage, recently appeared
- **declining**: Decreasing coverage, fading from discussion, fewer recent publications

Respond with ONLY the single word classification (accelerating, stable, emerging, or declining). No explanation."""

        try:
            response = self.client.chat.completions.create(
                model=get_chat_mini_deployment(),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0,
                timeout=REQUEST_TIMEOUT,
            )
            result = response.choices[0].message.content.strip().lower()
            valid = {"accelerating", "stable", "emerging", "declining"}
            if result in valid:
                return result
            # Try to extract a valid value from longer responses
            for v in valid:
                if v in result:
                    return v
            logger.warning(
                f"Unexpected trend trajectory response for '{signal_name[:40]}': {result}"
            )
            return "unknown"
        except Exception as e:
            logger.warning(
                f"Trend trajectory analysis failed for '{signal_name[:40]}': {e}"
            )
            return "unknown"

    async def generate_gap_analysis(
        self,
        card_name: str,
        initial_report: str,
        source_summaries: List[str],
    ) -> List[str]:
        """Analyze a research report for gaps and generate follow-up queries.

        Identifies unanswered questions, single-source claims, and
        unexplored angles, then generates 3-5 targeted follow-up queries.

        Args:
            card_name: Name of the signal being researched.
            initial_report: The GPT Researcher report text.
            source_summaries: Brief summaries of sources found so far.

        Returns:
            List of 3-5 follow-up search queries targeting identified gaps.
        """
        sources_text = "\n".join(f"- {s[:200]}" for s in source_summaries[:10])

        prompt = f"""You are a strategic research analyst. Analyze this initial research on "{card_name}" and identify gaps.

INITIAL REPORT (excerpt):
{initial_report[:3000]}

SOURCES COVERED:
{sources_text}

Identify:
1. What questions does this research NOT answer?
2. What claims have only one supporting source?
3. What angles are unexplored (costs, risks, case studies, vendor landscape, peer city implementations)?
4. What data points are missing (timelines, budgets, outcomes)?

Generate exactly 5 follow-up search queries that would fill the most important gaps. Each query should be specific and search-engine-ready.

Respond as a JSON object:
{{"queries": ["query 1", "query 2", "query 3", "query 4", "query 5"]}}"""

        try:
            response = self.client.chat.completions.create(
                model=get_chat_mini_deployment(),
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=500,
                temperature=0.3,
                timeout=REQUEST_TIMEOUT,
            )
            result = json.loads(response.choices[0].message.content)
            queries = result.get("queries", [])
            logger.info(
                f"Gap analysis for '{card_name[:40]}': {len(queries)} follow-up queries"
            )
            return queries[:5]
        except Exception as e:
            logger.warning(f"Gap analysis failed for '{card_name[:40]}': {e}")
            return []

    async def verify_source_claims(
        self,
        source_analyses: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Cross-reference claims across sources to assess confidence.

        Groups claims by topic, checks for multi-source corroboration,
        and identifies contradictions.

        Args:
            source_analyses: List of dicts with title, summary, key_excerpts.

        Returns:
            Dict with:
              - verified_claims: List of claims supported by 2+ sources
              - single_source_claims: List of claims from only one source
              - contradictions: List of contradictory claim pairs
              - confidence_summary: Overall text summary
        """
        if not source_analyses or len(source_analyses) < 2:
            return {
                "verified_claims": [],
                "single_source_claims": [],
                "contradictions": [],
                "confidence_summary": "Insufficient sources for cross-verification.",
            }

        # Build compact source digest for the LLM
        digest_parts = []
        for i, src in enumerate(source_analyses[:12], 1):
            title = src.get("title", "Untitled")[:80]
            summary = src.get("summary", "")[:300]
            excerpts = src.get("key_excerpts", [])
            excerpt_text = "; ".join(e[:150] for e in excerpts[:2])
            digest_parts.append(
                f"[Source {i}: {title}]\n{summary}\nKey points: {excerpt_text}"
            )

        digest = "\n\n".join(digest_parts)

        prompt = f"""Analyze these research sources for cross-verification. Identify:

1. **Verified claims**: Key claims that appear in 2+ sources (higher confidence)
2. **Single-source claims**: Important claims that only one source mentions (lower confidence)
3. **Contradictions**: Places where sources disagree on facts, timelines, or conclusions

SOURCES:
{digest}

Respond as JSON:
{{
  "verified_claims": [
    {{"claim": "description", "source_count": 3, "sources": [1, 3, 5]}}
  ],
  "single_source_claims": [
    {{"claim": "description", "source_index": 2}}
  ],
  "contradictions": [
    {{"claim_a": "source 1 says X", "claim_b": "source 4 says Y", "sources": [1, 4]}}
  ],
  "confidence_summary": "2-3 sentence overall assessment"
}}"""

        try:
            response = self.client.chat.completions.create(
                model=get_chat_mini_deployment(),
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=1500,
                temperature=0,
                timeout=REQUEST_TIMEOUT * 2,
            )
            result = json.loads(response.choices[0].message.content)
            verified = result.get("verified_claims", [])
            single = result.get("single_source_claims", [])
            contradictions = result.get("contradictions", [])
            logger.info(
                f"Source verification: {len(verified)} verified, "
                f"{len(single)} single-source, "
                f"{len(contradictions)} contradictions"
            )
            return result
        except Exception as e:
            logger.warning(f"Source verification failed: {e}")
            return {
                "verified_claims": [],
                "single_source_claims": [],
                "contradictions": [],
                "confidence_summary": "Verification analysis unavailable.",
            }

    @with_retry(max_retries=MAX_RETRIES)
    async def generate_deep_research_report(
        self,
        card_name: str,
        current_summary: str,
        current_description: str,
        horizon: str,
        stage: int,
        pillar: str,
        gpt_researcher_report: str,
        source_analyses: List[Dict[str, Any]],
        entities: List[Dict[str, str]],
        pipeline_status: str = "discovered",
    ) -> str:
        """
        Generate a comprehensive strategic intelligence report for deep research.

        This creates a multi-section, executive-quality report that synthesizes
        all research findings into actionable strategic intelligence.

        Args:
            card_name: Name of the card/concept
            current_summary: Current card summary
            current_description: Current card description
            horizon: H1/H2/H3 horizon classification
            stage: Stage 1-8
            pillar: Primary pillar code
            gpt_researcher_report: Raw report from GPT Researcher
            source_analyses: List of analyzed sources with summaries
            entities: Extracted entities for context

        Returns:
            Comprehensive markdown-formatted strategic report
        """
        # Format source insights with URLs for citation
        source_insights = ""
        for i, src in enumerate(source_analyses[:10], 1):
            title = src.get("title", "Untitled")[:80]
            url = src.get("url", "")
            source_name = src.get("source_name", "")

            # Format title as clickable link if URL available
            if url:
                source_insights += f"\n{i}. **[{title}]({url})**"
            else:
                source_insights += f"\n{i}. **{title}**"

            if source_name:
                source_insights += f" *({source_name})*"
            source_insights += "\n"
            source_insights += f"   Summary: {src.get('summary', 'No summary')[:300]}\n"
            if src.get("key_excerpts"):
                source_insights += (
                    f"   Key insight: {src.get('key_excerpts', [''])[0][:200]}\n"
                )

        # Format entities
        entity_str = ""
        if entities:
            tech_entities = [e for e in entities if e.get("type") == "technology"]
            org_entities = [e for e in entities if e.get("type") == "organization"]
            loc_entities = [e for e in entities if e.get("type") == "location"]

            if tech_entities:
                entity_str += f"Technologies: {', '.join(e.get('name', '') for e in tech_entities[:8])}\n"
            if org_entities:
                entity_str += f"Organizations: {', '.join(e.get('name', '') for e in org_entities[:8])}\n"
            if loc_entities:
                entity_str += f"Locations: {', '.join(e.get('name', '') for e in loc_entities[:5])}\n"

        # Format Austin strategic context for the prompt
        try:
            from .austin_context import format_austin_context_for_prompt

            austin_context = format_austin_context_for_prompt(pillar)
        except Exception:
            austin_context = ""

        prompt = DEEP_RESEARCH_REPORT_PROMPT.format(
            card_name=card_name,
            current_summary=current_summary or "No current summary",
            current_description=current_description or "No current description",
            pipeline_status=pipeline_status or "discovered",
            pillar=pillar or "Not specified",
            gpt_researcher_report=(
                gpt_researcher_report[:8000]
                if gpt_researcher_report
                else "No GPT Researcher report available"
            ),
            source_insights=source_insights or "No additional source insights",
            entities=entity_str or "No entities extracted",
            austin_context=austin_context,
        )

        logger.info(f"Generating comprehensive deep research report for: {card_name}")

        response = self.client.chat.completions.create(
            model=get_chat_deployment(),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=16384,  # Max output for GPT-4o to ensure complete report with sources
            timeout=REQUEST_TIMEOUT * 3,  # Extended timeout for long report
        )

        report = response.choices[0].message.content

        # Build formatted sources section with clickable links
        sources_section = self._build_sources_section(source_analyses)

        # Add metadata header and append sources section
        report_with_header = f"""# Deep Research Report: {card_name}

**Generated:** {__import__('datetime').datetime.now(__import__('datetime').timezone.utc).strftime('%B %d, %Y at %I:%M %p')}
**Classification:** Pipeline Status: {pipeline_status} | {pillar}
**Sources Analyzed:** {len(source_analyses)}

---

{report}

---

{sources_section}
"""

        logger.info(
            f"Generated comprehensive report ({len(report_with_header)} chars) for: {card_name}"
        )
        return report_with_header

    def _build_sources_section(self, source_analyses: List[Dict[str, Any]]) -> str:
        """
        Build a formatted sources section with clickable links.

        Args:
            source_analyses: List of source analysis dicts with url, title, source_name

        Returns:
            Markdown-formatted sources section
        """
        if not source_analyses:
            return "## Sources Cited\n\nNo sources available."

        # Log source data for debugging
        logger.info(f"Building sources section from {len(source_analyses)} sources")
        for i, src in enumerate(source_analyses[:3]):
            logger.debug(
                f"Source {i}: title={src.get('title', 'N/A')[:50]}, url={src.get('url', 'N/A')[:50] if src.get('url') else 'None'}"
            )

        # Deduplicate sources by URL
        seen_urls = set()
        unique_sources = []
        for src in source_analyses:
            url = src.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_sources.append(src)
            elif not url:
                # Include sources without URLs but mark them
                unique_sources.append(src)

        # Build the section
        lines = ["## Sources Cited", ""]

        for i, src in enumerate(unique_sources, 1):
            title = src.get("title") or "Untitled Source"
            url = src.get("url") or ""
            source_name = src.get("source_name") or ""

            # Clean up title (remove excessive length, normalize whitespace)
            title = " ".join(str(title).split())[:100] or "Untitled Source"

            # Skip completely empty entries
            if not title and not url:
                continue

            # Format as numbered list with clickable links
            if url and url.startswith(("http://", "https://")):
                entry = f"{i}. [{title}]({url})"
            elif url:
                entry = f"{i}. {title} ({url})"
            else:
                entry = f"{i}. {title}"

            # Add source/publication name if available
            if source_name:
                entry += f" — *{source_name}*"

            lines.append(entry)

        # Add methodology note
        lines.extend(
            [
                "",
                "---",
                "",
                "**Research Methodology:** This report was generated using GPT Researcher for source discovery, "
                "supplemented by Serper web and news search, with Exa AI neural search as a fallback. "
                "Content was extracted using Firecrawl or trafilatura. Sources were filtered for relevance to municipal "
                "government applications and analyzed using AI-powered classification and summarization.",
            ]
        )

        return "\n".join(lines)
