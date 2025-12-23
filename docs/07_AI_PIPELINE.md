# Foresight: AI Pipeline Specification

## Overview

The AI pipeline handles automated intelligence gathering, processing, and analysis. Two main flows:

1. **Nightly Scan** - Scheduled batch processing of sources
2. **On-Demand Research** - User-triggered deep dives

---

## Nightly Scan Pipeline

### Schedule

- **Time:** 2:00 AM CT (configurable)
- **Frequency:** Daily
- **Duration:** ~2-4 hours depending on volume

### Pipeline Stages

```
┌─────────────────────────────────────────────────────────────┐
│                    NIGHTLY PIPELINE                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. FETCH         ──►  Gather articles from all sources     │
│       │                                                     │
│       ▼                                                     │
│  2. DEDUPLICATE   ──►  Remove duplicates by URL + content   │
│       │                                                     │
│       ▼                                                     │
│  3. TRIAGE        ──►  Quick relevance check (fast/cheap)   │
│       │                                                     │
│       ▼                                                     │
│  4. PROCESS       ──►  Full analysis of relevant articles   │
│       │                                                     │
│       ▼                                                     │
│  5. MATCH         ──►  Link to existing cards or create new │
│       │                                                     │
│       ▼                                                     │
│  6. STORE         ──►  Persist to database                  │
│       │                                                     │
│       ▼                                                     │
│  7. NOTIFY        ──►  Queue digest emails                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Stage 1: Fetch

### Sources

| Source | Type | API | Rate Limit | Focus |
|--------|------|-----|------------|-------|
| NewsAPI | News | REST | 100/day (free) | General tech news |
| GDELT | News | REST | Unlimited | Global events |
| GovTech | RSS | Feed | N/A | Municipal tech |
| Route Fifty | RSS | Feed | N/A | State/local gov |
| Smart Cities Dive | RSS | Feed | N/A | Smart city tech |
| MIT Tech Review | RSS | Feed | N/A | Emerging tech |
| arXiv | API | REST | Reasonable | Research papers |
| SSRN | RSS | Feed | N/A | Policy papers |

### Fetch Implementation

```python
# app/pipeline/fetchers/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

@dataclass
class RawArticle:
    url: str
    title: str
    content: str
    published_at: Optional[datetime]
    source_name: str
    author: Optional[str]
    api_source: str  # Which fetcher found this

class BaseFetcher(ABC):
    """Base class for all source fetchers."""
    
    @abstractmethod
    async def fetch(self, since: datetime) -> List[RawArticle]:
        """Fetch articles published since given datetime."""
        pass
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        pass
```

```python
# app/pipeline/fetchers/newsapi.py

import httpx
from datetime import datetime, timedelta

class NewsAPIFetcher(BaseFetcher):
    source_name = "newsapi"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://newsapi.org/v2"
        
    async def fetch(self, since: datetime) -> List[RawArticle]:
        articles = []
        
        # Search queries targeting municipal/gov tech
        queries = [
            "municipal technology",
            "smart city",
            "government AI",
            "public sector innovation",
            "city infrastructure technology",
        ]
        
        async with httpx.AsyncClient() as client:
            for query in queries:
                response = await client.get(
                    f"{self.base_url}/everything",
                    params={
                        "q": query,
                        "from": since.isoformat(),
                        "sortBy": "publishedAt",
                        "language": "en",
                        "apiKey": self.api_key,
                    }
                )
                data = response.json()
                
                for item in data.get("articles", []):
                    articles.append(RawArticle(
                        url=item["url"],
                        title=item["title"],
                        content=item.get("content") or item.get("description", ""),
                        published_at=datetime.fromisoformat(item["publishedAt"].replace("Z", "+00:00")),
                        source_name=item["source"]["name"],
                        author=item.get("author"),
                        api_source=self.source_name,
                    ))
        
        return articles
```

```python
# app/pipeline/fetchers/rss.py

import feedparser
from datetime import datetime

class RSSFetcher(BaseFetcher):
    def __init__(self, feed_url: str, name: str):
        self.feed_url = feed_url
        self._source_name = name
        
    @property
    def source_name(self) -> str:
        return self._source_name
    
    async def fetch(self, since: datetime) -> List[RawArticle]:
        feed = feedparser.parse(self.feed_url)
        articles = []
        
        for entry in feed.entries:
            pub_date = datetime(*entry.published_parsed[:6])
            if pub_date > since:
                articles.append(RawArticle(
                    url=entry.link,
                    title=entry.title,
                    content=entry.get("summary", ""),
                    published_at=pub_date,
                    source_name=feed.feed.title,
                    author=entry.get("author"),
                    api_source=self.source_name,
                ))
        
        return articles
```

### Source Configuration

```python
# app/pipeline/config.py

SOURCES = [
    {
        "type": "newsapi",
        "enabled": True,
    },
    {
        "type": "rss",
        "name": "govtech",
        "url": "https://www.govtech.com/rss/",
        "enabled": True,
    },
    {
        "type": "rss", 
        "name": "route_fifty",
        "url": "https://www.route-fifty.com/rss/",
        "enabled": True,
    },
    {
        "type": "rss",
        "name": "smart_cities_dive",
        "url": "https://www.smartcitiesdive.com/feeds/news/",
        "enabled": True,
    },
    {
        "type": "rss",
        "name": "mit_tech_review",
        "url": "https://www.technologyreview.com/feed/",
        "enabled": True,
    },
]
```

---

## Stage 2: Deduplicate

Remove duplicate articles by:
1. Exact URL match
2. Content similarity (embedding cosine similarity > 0.95)

```python
# app/pipeline/processors.py

async def deduplicate(articles: List[RawArticle]) -> List[RawArticle]:
    """Remove duplicate articles."""
    seen_urls = set()
    unique = []
    
    for article in articles:
        # Normalize URL
        normalized_url = normalize_url(article.url)
        
        if normalized_url not in seen_urls:
            seen_urls.add(normalized_url)
            unique.append(article)
    
    return unique
```

---

## Stage 3: Triage

Fast, cheap relevance check using GPT-4o-mini.

**Goal:** Filter out irrelevant articles before expensive processing.

```python
# app/services/ai_service.py

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

async def triage_article(article: RawArticle) -> dict:
    """Quick relevance check for an article."""
    
    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": TRIAGE_PROMPT.format(
                title=article.title,
                content=article.content[:2000]  # Limit content
            )
        }],
        response_format={"type": "json_object"},
        max_tokens=200,
    )
    
    return json.loads(response.choices[0].message.content)
```

**Triage thresholds:**
- `is_relevant == True` AND `confidence >= 0.6` → Continue to processing
- Otherwise → Skip

---

## Stage 4: Process

Full analysis of relevant articles using GPT-4o.

### Analysis Output

```python
@dataclass
class ProcessedArticle:
    raw: RawArticle
    
    # AI-generated
    summary: str
    key_excerpts: List[str]
    entities: List[str]  # Technologies, organizations, concepts
    
    # Classification
    pillars: List[str]
    goals: List[str]
    steep_categories: List[str]
    anchors: List[str]
    
    # Scoring
    horizon: str  # H1, H2, H3
    suggested_stage: int  # 1-8
    triage_score: int  # 1, 3, 5
    
    credibility: float
    novelty: float
    likelihood: float
    impact: float
    relevance: float
    time_to_awareness_months: int
    time_to_prepare_months: int
    
    # For card matching
    suggested_card_name: str
    is_new_concept: bool
    
    # Embedding
    embedding: List[float]
```

### Processing Prompt

```python
PROCESS_PROMPT = """You are a strategic foresight analyst for the City of Austin.

Analyze this article for horizon scanning purposes.

TAXONOMY REFERENCE:
Pillars: CH (Community Health), EW (Economic), HG (High-Performing Gov), HH (Housing), MC (Mobility), PS (Public Safety)
STEEP: S (Social), T (Technological), E (Economic), E (Environmental), P (Political)
Anchors: Equity, Affordability, Innovation, Sustainability & Resiliency, Proactive Prevention, Community Trust

Horizons:
- H1: Mainstream, already happening widely
- H2: Transitional, pilots and early adoption
- H3: Weak signals, emerging concepts

Stages (1-8):
1=Concept, 2=Emerging, 3=Prototype, 4=Pilot, 5=Municipal Pilot, 6=Early Adoption, 7=Mainstream, 8=Mature

Triage Scores:
1=Confirms known baseline, 3=Resolves toward known alternative, 5=Novel/game-changing

Article Title: {title}
Source: {source}
Published: {published_at}
Content: {content}

Respond with JSON:
{{
  "summary": "2-3 sentence summary focused on municipal relevance",
  "key_excerpts": ["quote 1", "quote 2"],
  "entities": ["technology/org/concept names"],
  
  "pillars": ["XX", "XX"],
  "goals": ["XX.X"],
  "steep_categories": ["X"],
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
  
  "suggested_card_name": "Concise concept name",
  "is_new_concept": true/false,
  "reasoning": "Brief explanation of classification choices"
}}
"""
```

### Embedding Generation

```python
async def generate_embedding(text: str) -> List[float]:
    """Generate embedding for text using OpenAI."""
    
    response = await openai_client.embeddings.create(
        model="text-embedding-ada-002",
        input=text[:8000]  # Token limit
    )
    
    return response.data[0].embedding
```

---

## Stage 5: Match

Link processed articles to existing cards or create new ones.

### Matching Logic

```python
async def match_to_card(
    processed: ProcessedArticle,
    existing_cards: List[Card]
) -> Tuple[Optional[Card], bool]:
    """
    Match article to existing card or determine if new card needed.
    
    Returns: (matched_card, should_create_new)
    """
    
    # 1. Semantic search against existing cards
    similar_cards = await vector_search(
        processed.embedding,
        table="cards",
        limit=5,
        threshold=0.82
    )
    
    if not similar_cards:
        # No similar cards - likely new concept
        return None, processed.is_new_concept
    
    # 2. Check top match
    top_match = similar_cards[0]
    
    if top_match.similarity > 0.92:
        # Strong match - add as source to existing card
        return top_match.card, False
    
    elif top_match.similarity > 0.82:
        # Moderate match - use LLM to decide
        decision = await llm_match_decision(processed, top_match.card)
        if decision.is_match:
            return top_match.card, False
        else:
            return None, True
    
    else:
        # Weak match - probably new concept
        return None, processed.is_new_concept
```

### LLM Match Decision

```python
MATCH_PROMPT = """Determine if this article belongs to the existing card or represents a new concept.

EXISTING CARD:
Name: {card_name}
Summary: {card_summary}

NEW ARTICLE:
Title: {article_title}
Summary: {article_summary}
Suggested concept: {suggested_name}

Is this article about the same core concept as the existing card, just with new information?
Or is it a fundamentally different concept that deserves its own card?

Respond with JSON:
{{
  "is_match": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "explanation"
}}
"""
```

---

## Stage 6: Store

Persist results to database.

### For Matched Cards

```python
async def add_source_to_card(card_id: str, processed: ProcessedArticle):
    """Add new source to existing card."""
    
    # 1. Insert source
    source = await db.sources.insert({
        "card_id": card_id,
        "url": processed.raw.url,
        "title": processed.raw.title,
        "publication": processed.raw.source_name,
        "author": processed.raw.author,
        "published_at": processed.raw.published_at,
        "api_source": processed.raw.api_source,
        "full_text": processed.raw.content,
        "ai_summary": processed.summary,
        "key_excerpts": processed.key_excerpts,
        "relevance_to_card": processed.relevance,
        "embedding": processed.embedding,
    })
    
    # 2. Log timeline event
    await db.card_timeline.insert({
        "card_id": card_id,
        "event_type": "source_added",
        "event_description": f"New source: {processed.raw.title}",
        "triggered_by_source_id": source.id,
    })
    
    # 3. Check for stage change
    await check_stage_change(card_id, processed)
    
    # 4. Update card summary if significant
    if processed.novelty > 3.5:
        await regenerate_card_summary(card_id)
```

### For New Cards

```python
async def create_card(processed: ProcessedArticle) -> Card:
    """Create new card from processed article."""
    
    # 1. Generate card embedding (from summary)
    card_embedding = await generate_embedding(
        f"{processed.suggested_card_name} {processed.summary}"
    )
    
    # 2. Create card
    card = await db.cards.insert({
        "name": processed.suggested_card_name,
        "slug": slugify(processed.suggested_card_name),
        "summary": processed.summary,
        
        "horizon": processed.horizon,
        "stage": processed.suggested_stage,
        "triage_score": processed.triage_score,
        
        "pillars": processed.pillars,
        "goals": processed.goals,
        "steep_categories": processed.steep_categories,
        "anchors": processed.anchors,
        
        "credibility_score": processed.credibility,
        "novelty_score": processed.novelty,
        "likelihood_score": processed.likelihood,
        "impact_score": processed.impact,
        "relevance_score": processed.relevance,
        "time_to_awareness_months": processed.time_to_awareness_months,
        "time_to_prepare_months": processed.time_to_prepare_months,
        
        "embedding": card_embedding,
    })
    
    # 3. Add initial source
    await add_source_to_card(card.id, processed)
    
    # 4. Log creation
    await db.card_timeline.insert({
        "card_id": card.id,
        "event_type": "created",
        "event_description": f"Card created from {processed.raw.source_name}",
    })
    
    return card
```

---

## Stage 7: Notify

Queue digest emails for users.

```python
async def queue_notifications(scan_results: ScanResults):
    """Queue digest emails for users with updates."""
    
    # Get all users with notification preferences
    users = await db.users.select().where(
        preferences__digest_frequency != None
    )
    
    for user in users:
        # Get user's followed cards that have updates
        updated_cards = await get_user_updated_cards(
            user.id, 
            scan_results.processed_card_ids
        )
        
        if updated_cards:
            await queue_digest_email(user, updated_cards)
```

---

## On-Demand Research

User-triggered deep research on a topic.

### Research Task Flow

```python
async def run_research_task(task_id: str, query: str, user_id: str):
    """Execute a research task."""
    
    await update_task_status(task_id, "processing")
    
    try:
        # 1. Expand query into search terms
        search_terms = await expand_query(query)
        
        # 2. Search across all sources (not just last 24h)
        articles = []
        for term in search_terms:
            articles.extend(await search_sources(term, days_back=30))
        
        # 3. Deduplicate
        articles = await deduplicate(articles)
        
        # 4. Process all (no triage - user requested these)
        processed = []
        for article in articles[:50]:  # Limit to 50
            processed.append(await process_article(article))
        
        # 5. Cluster into concepts
        clusters = await cluster_by_concept(processed)
        
        # 6. Create cards for each cluster
        cards_created = []
        for cluster in clusters:
            card = await create_card_from_cluster(cluster)
            cards_created.append(card)
        
        # 7. Update task status
        await update_task_status(task_id, "completed", {
            "cards_created": [c.id for c in cards_created],
            "sources_processed": len(processed),
        })
        
    except Exception as e:
        await update_task_status(task_id, "failed", {"error": str(e)})
```

### Query Expansion

```python
EXPAND_PROMPT = """Generate search queries to research this topic thoroughly.

User Query: {query}

Generate 5-8 specific search queries that would help find:
- Current state of this technology/concept
- Municipal/government applications
- Recent pilots or implementations
- Key companies or organizations involved
- Challenges and limitations
- Future outlook

Respond with JSON:
{{
  "queries": ["query 1", "query 2", ...]
}}
"""
```

---

## Implications Analysis

AI-assisted implications wheel generation.

### First-Order Generation

```python
FIRST_ORDER_PROMPT = """Generate first-order implications of this emerging trend for the specified perspective.

CARD: {card_name}
Summary: {card_summary}
Stage: {stage}

PERSPECTIVE: {perspective}
Context: {perspective_detail}

Generate 3-5 direct, first-order implications. These should be:
- Direct consequences (not second-order effects)
- Specific to the perspective given
- Mix of positive and negative possibilities
- Concrete and actionable

Respond with JSON:
{{
  "implications": [
    {{
      "content": "implication text",
      "is_positive": true/false
    }}
  ]
}}
"""
```

### Expansion (Second/Third Order)

```python
EXPAND_IMPLICATION_PROMPT = """Generate second-order implications from this first-order implication.

CONTEXT:
Card: {card_name}
Perspective: {perspective}

FIRST-ORDER IMPLICATION: {parent_implication}

Generate 3-5 second-order implications. These should be:
- Consequences of the first-order implication (not the original card)
- More specific and downstream
- Mix of positive and negative
- Consider equity, budget, operational, political dimensions

Respond with JSON:
{{
  "implications": [
    {{
      "content": "implication text",
      "is_positive": true/false
    }}
  ]
}}
"""
```

---

## Cost Estimation

### Per Nightly Scan (estimated 200 articles)

| Stage | Model | Tokens | Cost |
|-------|-------|--------|------|
| Triage (200) | gpt-4o-mini | ~400K | $0.06 |
| Process (60) | gpt-4o | ~600K | $3.00 |
| Embeddings (60) | ada-002 | ~120K | $0.01 |
| Match decisions (20) | gpt-4o | ~40K | $0.20 |
| **Daily Total** | | | **~$3.30** |
| **Monthly Total** | | | **~$100** |

### Per Research Task

| Stage | Model | Tokens | Cost |
|-------|-------|--------|------|
| Query expansion | gpt-4o | ~2K | $0.01 |
| Process (50) | gpt-4o | ~500K | $2.50 |
| Clustering | gpt-4o | ~20K | $0.10 |
| **Per Task** | | | **~$2.60** |

### Per Implications Analysis

| Stage | Model | Tokens | Cost |
|-------|-------|--------|------|
| First-order (1) | gpt-4o | ~2K | $0.01 |
| Second-order (5) | gpt-4o | ~10K | $0.05 |
| Third-order (25) | gpt-4o | ~50K | $0.25 |
| **Full Analysis** | | | **~$0.31** |

---

*Document Version: 1.0*
*Last Updated: December 2024*
