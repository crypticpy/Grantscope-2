"""
AI Service for Foresight application.

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

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds
BACKOFF_MULTIPLIER = 2.0
REQUEST_TIMEOUT = 60  # seconds


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
                    wait_time = backoff * (BACKOFF_MULTIPLIER ** attempt)
                    logger.warning(f"Rate limited on {func.__name__}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                except openai.APITimeoutError as e:
                    last_exception = e
                    wait_time = backoff * (BACKOFF_MULTIPLIER ** attempt)
                    logger.warning(f"Timeout on {func.__name__}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                except openai.APIConnectionError as e:
                    last_exception = e
                    wait_time = backoff * (BACKOFF_MULTIPLIER ** attempt)
                    logger.warning(f"Connection error on {func.__name__}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                except openai.APIStatusError as e:
                    # Don't retry on 4xx errors (except 429 which is RateLimitError)
                    if 400 <= e.status_code < 500:
                        logger.error(f"API error on {func.__name__}: {e.status_code} - {e.message}")
                        raise
                    last_exception = e
                    wait_time = backoff * (BACKOFF_MULTIPLIER ** attempt)
                    logger.warning(f"API error on {func.__name__}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
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

    # Horizon & Stage
    horizon: str
    suggested_stage: int
    triage_score: int  # 1, 3, or 5

    # Scoring (all 1.0-5.0 except likelihood which is 1.0-9.0)
    credibility: float
    novelty: float
    likelihood: float
    impact: float
    relevance: float

    # Timing
    time_to_awareness_months: int
    time_to_prepare_months: int

    # Card suggestions
    suggested_card_name: str
    is_new_concept: bool

    # Entities for graph
    entities: List[ExtractedEntity] = field(default_factory=list)

    # Reasoning (for debugging/auditing)
    reasoning: str = ""


# ============================================================================
# Prompts
# ============================================================================

TRIAGE_PROMPT = """You are a triage analyst for a municipal government horizon scanning system.

Evaluate if this article is potentially relevant to city government operations, planning, or strategic interests.

Relevant topics include:
- Technology that could affect city services
- Infrastructure innovations
- Policy changes affecting municipalities
- Climate/sustainability developments
- Public safety innovations
- Economic development trends
- Housing and transportation technology
- Government operations technology

Article Title: {title}
Article Content: {content}

Respond with JSON:
{{
  "is_relevant": true/false,
  "confidence": 0.0-1.0,
  "primary_pillar": "CH|EW|HG|HH|MC|PS|null",
  "reason": "brief explanation"
}}
"""

ANALYSIS_PROMPT = """You are a strategic foresight analyst for the City of Austin.

Analyze this article for horizon scanning purposes.

TAXONOMY REFERENCE:
Pillars:
- CH (Community Health & Sustainability): Public health, parks, climate, preparedness
- EW (Economic & Workforce Development): Economic mobility, small business, creative economy
- HG (High-Performing Government): Fiscal, technology, workforce, engagement
- HH (Homelessness & Housing): Communities, affordable housing, homelessness reduction
- MC (Mobility & Critical Infrastructure): Transportation, transit, utilities, facilities
- PS (Public Safety): Relationships, fair delivery, disaster preparedness

Goals (examples):
- CH.1: Equitable public health services
- CH.3: Natural resources & climate mitigation
- HG.2: Data & technology capabilities
- MC.1: Mobility safety
- MC.3: Sustainable transportation

STEEP Categories: S (Social), T (Technological), E (Economic), En (Environmental), P (Political)

Anchors: Equity, Affordability, Innovation, Sustainability & Resiliency, Proactive Prevention, Community Trust

Horizons:
- H1: Mainstream, already happening widely (stages 6-8)
- H2: Transitional, pilots and early adoption (stages 3-5)
- H3: Weak signals, emerging concepts (stages 1-2)

Stages (1-8):
1=Concept (academic/theoretical)
2=Emerging (startups, patents, VC interest)
3=Prototype (working demos)
4=Pilot (real-world testing)
5=Municipal Pilot (government testing)
6=Early Adoption (multiple cities implementing)
7=Mainstream (widespread adoption)
8=Mature (established, commoditized)

Triage Scores:
1=Confirms known baseline (not surprising)
3=Resolves toward known alternative (expected development)
5=Novel/game-changing (unexpected, significant implications)

Article Title: {title}
Source: {source}
Published: {published_at}
Content: {content}

Respond with JSON:
{{
  "summary": "2-3 sentence summary focused on municipal relevance",
  "key_excerpts": ["relevant quote 1", "relevant quote 2"],

  "pillars": ["XX", "XX"],
  "goals": ["XX.X", "XX.X"],
  "steep_categories": ["X", "X"],
  "anchors": ["anchor name"],

  "horizon": "H1|H2|H3",
  "suggested_stage": 1-8,
  "triage_score": 1|3|5,

  "credibility": 1.0-5.0,
  "novelty": 1.0-5.0,
  "likelihood": 1.0-9.0,
  "impact": 1.0-5.0,
  "relevance": 1.0-5.0,
  "time_to_awareness_months": number,
  "time_to_prepare_months": number,

  "suggested_card_name": "Concise concept name (2-5 words)",
  "is_new_concept": true/false,

  "entities": [
    {{"name": "entity name", "type": "technology|organization|concept|person|location", "context": "brief context"}}
  ],

  "reasoning": "Brief explanation of classification choices"
}}
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


# ============================================================================
# AI Service Class
# ============================================================================

class AIService:
    """Service for AI-powered analysis and classification."""

    def __init__(self, openai_client: openai.OpenAI):
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
            model="text-embedding-ada-002",
            input=truncated,
            timeout=REQUEST_TIMEOUT
        )

        return response.data[0].embedding

    @with_retry(max_retries=MAX_RETRIES)
    async def triage_source(
        self,
        title: str,
        content: str
    ) -> TriageResult:
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
            content=content[:2000]  # Limit content for cheap triage
        )

        logger.debug(f"Triaging source: {title[:50]}...")

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=200,
            timeout=REQUEST_TIMEOUT
        )

        try:
            result = json.loads(response.choices[0].message.content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse triage response: {e}")
            return TriageResult(is_relevant=False, confidence=0.0, primary_pillar=None, reason="Parse error")

        return TriageResult(
            is_relevant=result.get("is_relevant", False),
            confidence=result.get("confidence", 0.0),
            primary_pillar=result.get("primary_pillar"),
            reason=result.get("reason", "")
        )

    @with_retry(max_retries=MAX_RETRIES)
    async def analyze_source(
        self,
        title: str,
        content: str,
        source_name: str,
        published_at: str
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
            published_at=published_at
        )

        logger.info(f"Analyzing source: {title[:50]}...")

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=1500,
            timeout=REQUEST_TIMEOUT * 2  # Longer timeout for full analysis
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
                credibility=3.0,
                novelty=3.0,
                likelihood=5.0,
                impact=3.0,
                relevance=3.0,
                time_to_awareness_months=12,
                time_to_prepare_months=24,
                suggested_card_name=title[:50],
                is_new_concept=False,
                reasoning="Parse error in analysis"
            )

        # Parse entities
        entities = []
        for ent in result.get("entities", []):
            entities.append(ExtractedEntity(
                name=ent.get("name", ""),
                entity_type=ent.get("type", "concept"),
                context=ent.get("context", "")
            ))

        return AnalysisResult(
            summary=result.get("summary", ""),
            key_excerpts=result.get("key_excerpts", []),
            pillars=result.get("pillars", []),
            goals=result.get("goals", []),
            steep_categories=result.get("steep_categories", []),
            anchors=result.get("anchors", []),
            horizon=result.get("horizon", "H2"),
            suggested_stage=result.get("suggested_stage", 4),
            triage_score=result.get("triage_score", 3),
            credibility=result.get("credibility", 3.0),
            novelty=result.get("novelty", 3.0),
            likelihood=result.get("likelihood", 5.0),
            impact=result.get("impact", 3.0),
            relevance=result.get("relevance", 3.0),
            time_to_awareness_months=result.get("time_to_awareness_months", 12),
            time_to_prepare_months=result.get("time_to_prepare_months", 24),
            suggested_card_name=result.get("suggested_card_name", title[:50]),
            is_new_concept=result.get("is_new_concept", False),
            entities=entities,
            reasoning=result.get("reasoning", "")
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
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=800,
            timeout=REQUEST_TIMEOUT
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
        existing_card_summary: str
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
        prompt = f"""Determine if this article belongs to the existing card or represents a new concept.

EXISTING CARD:
Name: {existing_card_name}
Summary: {existing_card_summary}

NEW ARTICLE:
Suggested concept: {source_card_name}
Summary: {source_summary}

Is this article about the same core concept as the existing card, just with new information?
Or is it a fundamentally different concept that deserves its own card?

Respond with JSON:
{{
  "is_match": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "explanation"
}}
"""

        logger.debug(f"Checking card match: {source_card_name} vs {existing_card_name}")

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=300,
            timeout=REQUEST_TIMEOUT
        )

        try:
            return json.loads(response.choices[0].message.content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse card match response: {e}")
            return {"is_match": False, "confidence": 0.0, "reasoning": "Parse error"}
