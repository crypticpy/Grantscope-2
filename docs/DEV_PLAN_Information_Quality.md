# Development Plan: Information Quality, Source Credibility & User-Generated Content

**Companion to:** `PRD_Information_Quality_and_User_Generated_Content.md`
**Approach:** Dependency-ordered, AI-agent executed, complete implementation — no stubs or placeholders

---

## Dependency Graph Overview

```
Layer 0: Database Schema (all migrations)
    │
    ├──► Layer 1: Backend Core Services
    │       │
    │       ├──► Layer 2: Pipeline Hardening (fixes to existing services)
    │       │       │
    │       │       ├──► Layer 3: Backend API Endpoints
    │       │       │       │
    │       │       │       ├──► Layer 4: Frontend Components & Pages
    │       │       │       │       │
    │       │       │       │       └──► Layer 5: Integration & Polish
    │       │       │       │
    │       │       │       └──► Layer 4b: Discovery Pipeline Integration
    │       │       │
    │       │       └──► Layer 3b: SQI Calculation Engine
    │       │
    │       └──► Layer 2b: Domain Reputation Service
    │
    └──► Layer 1b: Seed Data (domain reputation tiers)
```

Each layer is fully complete before the next begins. Within a layer, independent tasks can run in parallel.

---

## Layer 0: Database Schema

**Depends on:** Nothing
**Blocked by:** Nothing — this is the foundation everything else builds on

All new tables and column additions. Each migration gets a header comment explaining purpose, what it enables, and rollback strategy.

### Task 0.1: Domain Reputation Table

**Migration:** `YYYYMMDD_domain_reputation.sql`

**Creates:**

```sql
-- domain_reputation: Stores credibility tiers and user-aggregated reputation
-- for source domains. Used by discovery pipeline triage and SQI calculation.
-- Seeded with 100+ curated domains in Task 1.5.
-- Rollback: DROP TABLE domain_reputation;

CREATE TABLE domain_reputation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain_pattern TEXT NOT NULL UNIQUE,        -- e.g., 'gartner.com', '*.gov'
    organization_name TEXT NOT NULL,             -- e.g., 'Gartner'
    category TEXT NOT NULL,                      -- e.g., 'consulting', 'government', 'academic'
    curated_tier INTEGER CHECK (curated_tier IN (1, 2, 3)),  -- NULL = untiered
    user_quality_avg NUMERIC(3,2) DEFAULT 0,    -- Aggregated from source_ratings
    user_relevance_avg NUMERIC(3,2) DEFAULT 0,  -- Aggregated from source_ratings
    user_rating_count INTEGER DEFAULT 0,
    triage_pass_rate NUMERIC(5,4) DEFAULT 0,    -- % of sources from this domain that pass triage
    triage_total_count INTEGER DEFAULT 0,        -- Total sources triaged from this domain
    triage_pass_count INTEGER DEFAULT 0,         -- Sources that passed triage
    composite_score NUMERIC(5,2) DEFAULT 0,      -- Weighted combination: 50% curated + 30% user + 20% pipeline
    texas_relevance_bonus INTEGER DEFAULT 0,     -- +10 for Texas-specific sources
    is_active BOOLEAN DEFAULT TRUE,
    notes TEXT,                                   -- Admin notes
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for lookup during triage
CREATE INDEX idx_domain_reputation_pattern ON domain_reputation (domain_pattern);
CREATE INDEX idx_domain_reputation_tier ON domain_reputation (curated_tier) WHERE curated_tier IS NOT NULL;
CREATE INDEX idx_domain_reputation_composite ON domain_reputation (composite_score DESC);
```

**RLS:** Admin full access. All authenticated users can read. Only admins can write.

**Files owned:** `supabase/migrations/YYYYMMDD_domain_reputation.sql`

---

### Task 0.2: Source Ratings Table

**Migration:** `YYYYMMDD_source_ratings.sql`

**Creates:**

```sql
-- source_ratings: Per-user quality and municipal relevance ratings on individual sources.
-- Aggregated nightly into domain_reputation. Displayed in SourcesTab alongside AI scores.
-- Rollback: DROP TABLE source_ratings;

CREATE TABLE source_ratings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    quality_rating INTEGER NOT NULL CHECK (quality_rating BETWEEN 1 AND 5),
    relevance_rating TEXT NOT NULL CHECK (relevance_rating IN ('high', 'medium', 'low', 'not_relevant')),
    comment TEXT CHECK (char_length(comment) <= 280),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (source_id, user_id)
);

CREATE INDEX idx_source_ratings_source ON source_ratings (source_id);
CREATE INDEX idx_source_ratings_user ON source_ratings (user_id);
```

**RLS:** Users can read all ratings. Users can insert/update/delete only their own.

**Files owned:** `supabase/migrations/YYYYMMDD_source_ratings.sql`

---

### Task 0.3: Cards Table Additions

**Migration:** `YYYYMMDD_cards_quality_and_origin.sql`

**Adds to `cards` table:**

```sql
-- Adds SQI fields, card origin tracking, and exploratory flag.
-- quality_score is recalculated by backend service on source changes.
-- origin tracks how the card was created for provenance display.
-- Rollback: ALTER TABLE cards DROP COLUMN quality_score, quality_breakdown, origin, is_exploratory;

ALTER TABLE cards ADD COLUMN IF NOT EXISTS quality_score INTEGER DEFAULT 0 CHECK (quality_score BETWEEN 0 AND 100);
ALTER TABLE cards ADD COLUMN IF NOT EXISTS quality_breakdown JSONB DEFAULT '{}';
ALTER TABLE cards ADD COLUMN IF NOT EXISTS origin TEXT DEFAULT 'discovery' CHECK (origin IN ('discovery', 'workstream_scan', 'user_created', 'manual'));
ALTER TABLE cards ADD COLUMN IF NOT EXISTS is_exploratory BOOLEAN DEFAULT FALSE;

CREATE INDEX idx_cards_quality_score ON cards (quality_score DESC);
CREATE INDEX idx_cards_origin ON cards (origin);
CREATE INDEX idx_cards_exploratory ON cards (is_exploratory) WHERE is_exploratory = TRUE;
```

**Files owned:** `supabase/migrations/YYYYMMDD_cards_quality_and_origin.sql`

---

### Task 0.4: Sources Table Additions

**Migration:** `YYYYMMDD_sources_quality_fields.sql`

**Adds to `sources` table:**

```sql
-- Adds peer-review flag, story cluster tracking, and domain reputation link.
-- is_peer_reviewed defaults to NULL (unknown); set by academic source fetchers.
-- story_cluster_id groups sources reporting on the same underlying event.
-- Rollback: ALTER TABLE sources DROP COLUMN is_peer_reviewed, story_cluster_id, domain_reputation_id;

ALTER TABLE sources ADD COLUMN IF NOT EXISTS is_peer_reviewed BOOLEAN;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS story_cluster_id UUID;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS domain_reputation_id UUID REFERENCES domain_reputation(id);

CREATE INDEX idx_sources_peer_reviewed ON sources (is_peer_reviewed) WHERE is_peer_reviewed IS NOT NULL;
CREATE INDEX idx_sources_story_cluster ON sources (story_cluster_id) WHERE story_cluster_id IS NOT NULL;
```

**Files owned:** `supabase/migrations/YYYYMMDD_sources_quality_fields.sql`

---

### Task 0.5: Discovery Metadata Additions

**Migration:** `YYYYMMDD_discovery_metadata_quality.sql`

**Adds to `cards` table (discovery_metadata JSONB) — no schema change needed, just documenting the new keys that will be written:**

New JSONB keys in `discovery_metadata`:

- `scores_are_defaults: boolean` — True when AI scores are parse-error fallbacks
- `content_filter_count: integer` — Sources rejected for insufficient content
- `freshness_filter_count: integer` — Sources rejected for being too old
- `story_cluster_count: integer` — Unique story clusters across sources

This task also adds a `discovery_quality_stats` JSONB field to `discovery_runs`:

```sql
ALTER TABLE discovery_runs ADD COLUMN IF NOT EXISTS quality_stats JSONB DEFAULT '{}';
```

**Files owned:** `supabase/migrations/YYYYMMDD_discovery_metadata_quality.sql`

---

## Layer 1: Backend Core Services

**Depends on:** Layer 0 (all migrations applied)

### Task 1.1: Domain Reputation Service

**New file:** `backend/app/domain_reputation_service.py`

**Responsibilities:**

- Look up domain reputation for a given URL (extract domain, match against patterns including wildcards)
- Compute composite scores from curated tier + user ratings + pipeline performance
- Handle wildcard matching (e.g., `*.gov`, `*.edu`, `*.harvard.edu`)
- Recalculate aggregated user ratings from `source_ratings` table
- Recalculate triage pass rates from `discovered_sources` table
- Apply Texas relevance bonus
- Expose methods: `get_reputation(url)`, `get_reputation_batch(urls)`, `recalculate_all()`, `get_authority_score(url)` (returns 0-100 for SQI)

**Documentation requirements:**

- Module docstring explaining the three-signal composite scoring model
- Each method gets a docstring with parameters, return type, and algorithm explanation
- Inline comments on the wildcard matching priority logic (specific domain > subdomain wildcard > TLD wildcard)
- Inline comments on the composite score formula with weight justification

**Files owned:** `backend/app/domain_reputation_service.py`

---

### Task 1.2: SQI Calculation Service

**New file:** `backend/app/quality_service.py`

**Responsibilities:**

- Calculate Source Quality Index for a card given its sources
- Compute each of the 5 SQI components:
  - **Source Authority (30%):** Uses DomainReputationService to get authority scores per source, averages them
  - **Source Diversity (20%):** Counts distinct `api_source` categories
  - **Corroboration (20%):** Counts unique story clusters (not raw source count)
  - **Recency (15%):** Age-weighted scoring based on source publication/ingestion dates
  - **Municipal Specificity (15%):** Combines AI `relevance_to_card` scores with domain type signals
- Store results in `cards.quality_score` and `cards.quality_breakdown`
- Expose methods: `calculate_sqi(card_id)`, `recalculate_all_cards()`, `get_breakdown(card_id)`

**Documentation requirements:**

- Detailed module docstring explaining the SQI methodology, why these 5 components, and the weight rationale
- Each component calculation gets its own well-documented private method
- The scoring curves (e.g., recency decay, diversity scaling) are documented with comments showing example inputs → outputs

**Depends on:** Task 1.1 (DomainReputationService)

**Files owned:** `backend/app/quality_service.py`

---

### Task 1.3: Story Clustering Service

**New file:** `backend/app/story_clustering_service.py`

**Responsibilities:**

- Given a set of sources (with embeddings), cluster them by semantic similarity
- Use cosine similarity threshold of 0.90 for same-story clustering
- Assign `story_cluster_id` to each source
- Return cluster count for SQI corroboration component
- Handle sources without embeddings gracefully (each is its own cluster)
- Expose methods: `cluster_sources(source_ids)`, `get_cluster_count(card_id)`, `cluster_new_sources(card_id, new_source_ids)`

**Documentation requirements:**

- Module docstring explaining the clustering algorithm and threshold choice
- Document the edge cases: sources without embeddings, single-source cards, cross-card clustering

**Files owned:** `backend/app/story_clustering_service.py`

---

### Task 1.4: Source Content Validator

**New file:** `backend/app/source_validator.py`

**Responsibilities:**

- Validate source content before triage: minimum 100 characters of meaningful text
- Validate source freshness by category (News/Tech: 90d, Academic: 365d, Government: 730d, RSS: 90d)
- Detect and flag academic pre-prints (arXiv domain detection, lack of DOI for journal papers)
- Parse dates in multiple formats (ISO 8601, RFC 2822, natural language like "January 15, 2025")
- Return validation result with reason codes for logging
- Expose methods: `validate_content(source)`, `validate_freshness(source, category)`, `detect_preprint(source)`, `validate_all(source, category)`

**Documentation requirements:**

- Document each validation rule, the threshold, and the reasoning behind it
- Document the date parsing strategy and fallback behavior
- Document what happens when validation fails vs. when it's inconclusive

**Files owned:** `backend/app/source_validator.py`

---

### Task 1.5: Domain Reputation Seed Data

**New file:** `supabase/migrations/YYYYMMDD_seed_domain_reputation.sql`

**Responsibilities:**

- Insert all 100+ organizations from PRD Section 10 into `domain_reputation`
- Set curated_tier, organization_name, category for each
- Set texas_relevance_bonus = 10 for Texas-specific sources
- Set initial composite_score based on curated tier alone (Tier 1 = 85, Tier 2 = 60, Tier 3 = 35)

**Documentation requirements:**

- Header comment explaining the tier definitions and source of the curated list
- Organized by category with section comments

**Depends on:** Task 0.1 (domain_reputation table exists)

**Files owned:** `supabase/migrations/YYYYMMDD_seed_domain_reputation.sql`

---

## Layer 2: Pipeline Hardening

**Depends on:** Layer 1 (core services available)

These tasks modify existing files. Each task owns specific changes within shared files. No two tasks modify the same function.

### Task 2.1: Content Validation in Discovery Pipeline

**Modifies:** `backend/app/discovery_service.py`

**Changes:**

- Import and use `SourceValidator` in the triage step
- Before calling AI triage, run `validate_content()` and `validate_freshness()` on each source
- Sources failing validation are logged with reason codes and skipped
- Add content/freshness filter counts to discovery run `quality_stats`
- Reject sources with < 100 chars content (FIX-C1)
- Reject sources exceeding age thresholds by category (FIX-H1)

**Does NOT modify:** AI triage logic, card creation logic, deduplication logic

**Files modified:** `backend/app/discovery_service.py` (triage section only)

---

### Task 2.2: Content Validation in Workstream Scan Pipeline

**Modifies:** `backend/app/workstream_scan_service.py`

**Changes:**

- Import and use `SourceValidator` (same as Task 2.1 but in the scan service)
- Apply same content minimum and freshness filtering
- Change card creation to use `review_status: 'pending_review'` instead of `'approved'` (FIX-C2)
- Add rate limiting enforcement: check scan count for workstream in last 24h before execution (FIX-H5)

**Files modified:** `backend/app/workstream_scan_service.py`

---

### Task 2.3: Score Clamping and Consistency

**Modifies:** `backend/app/ai_service.py`, `backend/app/discovery_service.py`, `backend/app/research_service.py`, `backend/app/workstream_scan_service.py`

**Changes:**

- In `ai_service.py`: Add score clamping to `AnalysisResult` — clamp each score to its documented range on assignment (FIX-C3)
- In `ai_service.py`: When JSON parsing of AI response fails and defaults are used, set `scores_are_defaults = True` on the result
- In `research_service.py`: Fix `velocity_score = int(analysis.velocity * 10)` instead of `int(analysis.likelihood * 11)` (FIX-C4)
- In all three pipeline services: Ensure consistent score conversion formulas (velocity _ 10, all others _ 20)
- Propagate `scores_are_defaults` flag into `cards.discovery_metadata`

**Files modified:** `backend/app/ai_service.py` (AnalysisResult class + parse methods), `backend/app/research_service.py` (score mapping), `backend/app/discovery_service.py` (score mapping), `backend/app/workstream_scan_service.py` (score mapping)

---

### Task 2.4: Pillar Code Fix

**Modifies:** `backend/app/discovery_service.py`, `backend/app/ai_service.py`

**Changes:**

- Remove all pillar mapping/conversion logic that maps HG→EC and PS→CH (FIX-H4)
- Ensure all 6 pillar codes (CH, EW, HG, HH, MC, PS) pass through natively
- Add a data correction query to fix existing cards with wrong pillar mappings (in a migration)

**Files modified:** `backend/app/discovery_service.py` (pillar handling), `backend/app/ai_service.py` (pillar output)
**New file:** `supabase/migrations/YYYYMMDD_fix_pillar_codes.sql` (data correction)

---

### Task 2.5: Story-Level Deduplication Integration

**Modifies:** `backend/app/discovery_service.py`

**Changes:**

- After sources are triaged and before card creation, run `StoryClusteringService.cluster_sources()` on the source batch
- Use cluster count (not raw source count) when evaluating whether a topic has enough corroboration for card creation
- Store `story_cluster_id` on each source when it's inserted into the `sources` table
- Log cluster count in discovery run stats

**Depends on:** Task 1.3 (StoryClusteringService)

**Files modified:** `backend/app/discovery_service.py` (dedup/card-creation section)

---

### Task 2.6: Pre-Print Detection Integration

**Modifies:** `backend/app/discovery_service.py`, `backend/app/workstream_scan_service.py`

**Changes:**

- After source fetching, run `SourceValidator.detect_preprint()` on academic sources
- Set `is_peer_reviewed` flag on sources before inserting into database
- Reduce default relevance for non-peer-reviewed sources from 0.8 to 0.6 during AI analysis

**Files modified:** `backend/app/discovery_service.py` (academic source handling), `backend/app/workstream_scan_service.py` (academic source handling)

---

### Task 2.7: Domain Reputation Integration into Triage

**Modifies:** `backend/app/discovery_service.py`, `backend/app/workstream_scan_service.py`

**Changes:**

- During triage, look up each source's domain reputation via `DomainReputationService`
- Apply confidence boost/penalty based on composite score:
  - Tier 1 (composite >= 80): +0.10 confidence
  - Tier 2 (composite >= 50): +0.05 confidence
  - Tier 3 (composite >= 30): +0.00 (neutral)
  - Untiered (composite < 30): -0.05 confidence
  - Low user ratings (composite < 15): -0.10 confidence
- Link `domain_reputation_id` to each source on insert
- Log domain reputation lookup results in discovery stats

**Depends on:** Task 1.1 (DomainReputationService), Task 1.5 (seed data)

**Files modified:** `backend/app/discovery_service.py` (triage section), `backend/app/workstream_scan_service.py` (triage section)

---

## Layer 3: Backend API Endpoints

**Depends on:** Layer 2 (pipeline hardening complete)

### Task 3.1: Source Rating API Endpoints

**Modifies:** `backend/app/main.py`

**New endpoints:**

- `POST /api/v1/sources/{source_id}/rate` — Create or update user's rating. Accepts `quality_rating` (1-5), `relevance_rating` (enum), `comment` (optional, max 280). Upserts on `(source_id, user_id)`.
- `GET /api/v1/sources/{source_id}/ratings` — Returns aggregated ratings (avg quality, relevance distribution, count) plus current user's rating if exists.
- `DELETE /api/v1/sources/{source_id}/rate` — Remove user's rating.
- `GET /api/v1/sources/{source_id}/ratings/comments` — Returns all comments for a source with author info.

**Also modifies:** The existing source list response (when fetching sources for a card) to include aggregated rating data inline.

**Pydantic models to create:**

- `SourceRatingCreate` — request body for POST
- `SourceRatingResponse` — single rating
- `SourceRatingAggregate` — aggregated stats for a source

**Documentation requirements:**

- Each endpoint gets a docstring explaining purpose, auth requirements, and response shape
- Pydantic models get field descriptions

**Files modified:** `backend/app/main.py` (new endpoints section)
**New file:** `backend/app/models/source_rating.py` (Pydantic models)

---

### Task 3.2: SQI API Endpoints

**Modifies:** `backend/app/main.py`

**New endpoints:**

- `GET /api/v1/cards/{card_id}/quality` — Returns full SQI breakdown (overall score + 5 component scores + metadata)
- `POST /api/v1/cards/{card_id}/quality/recalculate` — Force SQI recalculation (admin/system use)
- `POST /api/v1/admin/quality/recalculate-all` — Batch recalculate all cards (admin only)

**Also modifies:**

- Existing card list endpoints to include `quality_score` in response
- Existing card detail endpoint to include `quality_breakdown` in response
- Card search/filter to support `quality_tier` filter and `quality_score` sort

**Pydantic models to create:**

- `QualityBreakdown` — detailed SQI response
- `QualityTierFilter` — filter enum (high/moderate/needs_verification)

**Files modified:** `backend/app/main.py` (card endpoints + new quality section)
**New file:** `backend/app/models/quality.py` (Pydantic models)

---

### Task 3.3: Domain Reputation API Endpoints

**Modifies:** `backend/app/main.py`

**New endpoints:**

- `GET /api/v1/domain-reputation` — List all domains with reputation data (paginated, filterable by tier/category)
- `GET /api/v1/domain-reputation/{id}` — Single domain detail
- `POST /api/v1/admin/domain-reputation` — Add new domain (admin)
- `PATCH /api/v1/admin/domain-reputation/{id}` — Update domain tier/category (admin)
- `DELETE /api/v1/admin/domain-reputation/{id}` — Remove domain (admin)
- `POST /api/v1/admin/domain-reputation/recalculate` — Recalculate all composite scores
- `GET /api/v1/analytics/top-domains` — Top domains leaderboard (by composite score, filterable by pillar and time)

**Pydantic models to create:**

- `DomainReputationResponse`, `DomainReputationCreate`, `DomainReputationUpdate`
- `TopDomainsResponse`

**Files modified:** `backend/app/main.py`
**New file:** `backend/app/models/domain_reputation.py` (Pydantic models)

---

### Task 3.4: Card Creation API Endpoints

**Modifies:** `backend/app/main.py`

**New endpoints:**

- `POST /api/v1/cards/create-from-topic` — Mode A: Quick card from topic phrase. Accepts `topic` string, optional `workstream_id`, optional `pillar_hints[]`. Returns created card with status of background mini-scan.
- Enhanced `POST /api/v1/cards` — Mode B: Add optional `seed_urls[]` field. When provided, system fetches and analyzes each URL, generates AI classification, and creates card with sources.

**New backend service method:** `create_card_from_topic(topic, user_id)` in a new `card_creation_service.py` that:

1. Calls AI to generate card metadata from topic
2. Creates the card with `origin: 'user_created'`
3. Kicks off a background mini-scan (reusing workstream scan logic for a single topic)
4. Returns the card immediately (sources arrive asynchronously)

**Also:** `POST /api/v1/ai/suggest-keywords` — Accepts a topic phrase, returns 5-10 municipal-relevant keyword suggestions.

**Files modified:** `backend/app/main.py`
**New files:** `backend/app/card_creation_service.py`, `backend/app/models/card_creation.py`

---

### Task 3.5: Workstream Enhancement API Changes

**Modifies:** `backend/app/main.py`

**Changes:**

- Modify `POST /api/v1/me/workstreams` to make `pillar_ids` optional (currently may be required in validation)
- Modify `POST /api/v1/me/workstreams/{id}/auto-populate` response to include `match_count` field
- When `match_count` is 0, include a `suggest_scan: true` flag in response
- Add auto-scan-on-create option: when `auto_scan: true` is passed to workstream creation, automatically queue a workstream scan after creation

**Files modified:** `backend/app/main.py` (workstream endpoints)

---

## Layer 4: Frontend Components & Pages

**Depends on:** Layer 3 (API endpoints available and tested)

### Task 4.1: SQI Badge Component

**New files:**

- `frontend/foresight-frontend/src/components/QualityBadge.tsx` — Reusable traffic-light badge. Props: `score: number`, `size: 'sm' | 'md' | 'lg'`. Shows "High Confidence" (green, 75+), "Moderate" (amber, 50-74), "Needs Verification" (red, 0-49), "No Sources" (gray, null/undefined). Includes hover tooltip with score value and source count.
- `frontend/foresight-frontend/src/components/CardDetail/panels/InformationQualityPanel.tsx` — Full SQI breakdown panel for card detail page. Shows overall score, 5 component bars with labels, plain-English tooltips, last-calculated timestamp. Each component bar is color-coded and includes a "What does this mean?" link to `/methodology#scoring`.

**Integrates into:**

- `DiscoverCard.tsx` — Add QualityBadge alongside existing score badges
- `DiscoveryQueueCard.tsx` — Add QualityBadge
- `CardDetail.tsx` — Add InformationQualityPanel to Overview tab
- `KanbanCard.tsx` — Add small QualityBadge

**Documentation:** JSDoc on all props, component-level doc comment explaining the visual design rationale.

**Files owned:** `QualityBadge.tsx`, `InformationQualityPanel.tsx`
**Files modified:** `DiscoverCard.tsx`, `DiscoveryQueueCard.tsx`, `CardDetail.tsx`, `KanbanCard.tsx`

---

### Task 4.2: Source Rating UI Components

**New files:**

- `frontend/foresight-frontend/src/components/SourceRating/StarRating.tsx` — Interactive 1-5 star rating input. Optimistic UI (persists on click). Shows filled/empty stars. Handles hover preview.
- `frontend/foresight-frontend/src/components/SourceRating/RelevanceSelector.tsx` — Segmented control with 4 options (High / Medium / Low / Not Relevant). Pill-style buttons.
- `frontend/foresight-frontend/src/components/SourceRating/SourceRatingInline.tsx` — Combines StarRating + RelevanceSelector + optional comment field for inline display on each source card. Shows current user's rating pre-filled, aggregate stats alongside.
- `frontend/foresight-frontend/src/components/SourceRating/RatingAggregate.tsx` — Displays "Team Rating: 4.2/5 (3 ratings)" with divergence indicator when AI and human scores differ by >30 points.

**New API client functions:**

- Add to `frontend/foresight-frontend/src/lib/source-rating-api.ts`: `rateSource()`, `getSourceRatings()`, `deleteSourceRating()`

**Integrates into:**

- `SourcesTab.tsx` — Each source card gets SourceRatingInline below existing metadata

**Documentation:** JSDoc on all components. Comment explaining optimistic UI pattern and why it's used (reduce friction → more ratings).

**Files owned:** All `SourceRating/` components, `source-rating-api.ts`
**Files modified:** `SourcesTab.tsx`

---

### Task 4.3: Create Signal Modal

**New files:**

- `frontend/foresight-frontend/src/components/CreateSignal/CreateSignalModal.tsx` — Modal with two tabs: "Quick Create" (topic phrase input) and "Manual Create" (full form).
- `frontend/foresight-frontend/src/components/CreateSignal/QuickCreateTab.tsx` — Text input for topic phrase, optional workstream selector, "Create" button. Shows loading state while AI generates card, then success state with link to new card.
- `frontend/foresight-frontend/src/components/CreateSignal/ManualCreateTab.tsx` — Full form: name, description, pillar multi-select (with "Exploratory" option), horizon, stage, seed URLs (tag-style input accepting up to 10 URLs). Shows AI enrichment progress after submission.
- `frontend/foresight-frontend/src/components/CreateSignal/SeedUrlInput.tsx` — Tag-style input for URLs. Validates URL format. Shows count (1-10).
- `frontend/foresight-frontend/src/components/badges/ExploratoryBadge.tsx` — Distinct badge for exploratory cards (different from pillar badges).

**New API client functions:**

- Add to `frontend/foresight-frontend/src/lib/discovery-api.ts`: `createCardFromTopic()`, `createCardManual()`, `suggestKeywords()`

**Integrates into:**

- `Discover.tsx` — "Create Signal" button in page header
- `WorkstreamKanban.tsx` — "Create Signal" button in action bar

**Documentation:** Component-level docs explaining the two creation flows and when each is appropriate.

**Files owned:** All `CreateSignal/` components, `ExploratoryBadge.tsx`
**Files modified:** `Discover.tsx`, `WorkstreamKanban.tsx`, `discovery-api.ts`

---

### Task 4.4: Enhanced Workstream Form

**Modifies:** `frontend/foresight-frontend/src/components/WorkstreamForm.tsx`

**Changes:**

- Make pillar selection optional (remove any required validation)
- Add "Suggest Related Terms" button next to keywords input. Calls `POST /api/v1/ai/suggest-keywords`. Returns chips that user can click to add.
- Add "Auto-scan on create" toggle (default on when no pillars selected)
- After creation + auto-populate, if `match_count === 0`, show inline prompt: "No existing signals match this topic. Would you like to discover new content?" with "Start Discovery Scan" button
- Show scan progress inline (poll scan status endpoint)

**Modifies:** `frontend/foresight-frontend/src/pages/Workstreams.tsx` — Handle the post-creation scan flow

**Files modified:** `WorkstreamForm.tsx`, `Workstreams.tsx`

---

### Task 4.5: Methodology Page

**New files:**

- `frontend/foresight-frontend/src/pages/Methodology.tsx` — Full methodology page with 6 expandable sections per PRD Section 8.2. Uses Radix Accordion. Professional, clean layout optimized for print. Includes a "Source Authority Tiers" section that fetches from `GET /api/v1/domain-reputation` and renders a searchable, sortable table.
- Route registration in the app router

**Design requirements:**

- Must feel authoritative and professional — this will be shown to council members
- Each section starts with a 2-3 sentence executive summary, then expandable detail
- Score definitions include visual examples (small inline bar showing what 80/100 looks like)
- Print stylesheet that hides navigation and expands all accordions
- "What does this mean?" links from score tooltips throughout the app should deep-link to specific sections (via URL hash anchors)

**Files owned:** `Methodology.tsx`
**Files modified:** Router configuration (add `/methodology` route)

---

### Task 4.6: Discover Page Enhancements

**Modifies:** `frontend/foresight-frontend/src/pages/Discover.tsx`

**Changes:**

- Add quality tier filter to existing filter bar (High Confidence / Moderate / Needs Verification / All)
- Add quality score sort option to existing sort controls
- Cards show provenance indicator when `origin` is `'user_created'` or `'workstream_scan'` (small "User Created" or "Discovered via [workstream]" label)
- "Scores Unverified" indicator on cards where `discovery_metadata.scores_are_defaults` is true
- "Pre-print" indicator on academic sources in source previews

**Files modified:** `Discover.tsx`, filter/sort components as needed

---

### Task 4.7: Kanban Board Enhancements

**Modifies:** `frontend/foresight-frontend/src/components/kanban/KanbanCard.tsx`

**Changes:**

- Add QualityBadge (small size) to each kanban card
- Add "Needs Review" badge on cards with `review_status: 'pending_review'`
- Add approval quick-action button on inbox cards with pending_review status
- Show ExploratoryBadge on exploratory cards

**Files modified:** `KanbanCard.tsx`, `CardActions.tsx`

---

## Layer 5: Integration & Polish

**Depends on:** Layer 4 (all frontend components built)

### Task 5.1: Domain Reputation Aggregation Job

**Modifies:** `backend/app/main.py` (scheduler section)

**Changes:**

- Add nightly job that runs `DomainReputationService.recalculate_all()`
- This aggregates all source_ratings by domain into `domain_reputation.user_quality_avg`, `user_relevance_avg`, `user_rating_count`
- Recalculates triage_pass_rate from `discovered_sources` data
- Recomputes composite_score using the weighted formula

**Files modified:** `backend/app/main.py` (scheduler), `backend/app/domain_reputation_service.py` (add batch recalculate method)

---

### Task 5.2: SQI Auto-Recalculation

**Modifies:** `backend/app/main.py` or `backend/app/quality_service.py`

**Changes:**

- When a source is added to a card (via discovery, research, or user creation), trigger SQI recalculation for that card
- When a source rating is submitted, trigger SQI recalculation for the parent card
- Ensure SQI is calculated for newly created cards once their initial sources arrive
- Add SQI recalculation to the nightly scan job for all active cards

**Files modified:** `backend/app/quality_service.py`, `backend/app/main.py` (source-related endpoints)

---

### Task 5.3: Score Tooltip Links to Methodology

**Modifies:** Various frontend components that display score tooltips

**Changes:**

- Add "Learn more" links in score tooltips across the app that link to the appropriate section of `/methodology`
- Impact score tooltip → `/methodology#impact`
- Quality badge tooltip → `/methodology#sqi`
- Each score dimension gets a hash anchor on the methodology page

**Files modified:** `ImpactMetricsPanel.tsx`, `QualityBadge.tsx`, `InformationQualityPanel.tsx`, score-related components

---

### Task 5.4: Analytics — Top Domains Leaderboard

**New file:** `frontend/foresight-frontend/src/components/analytics/TopDomainsLeaderboard.tsx`

**Integrates into:** Analytics page (existing)

**Shows:**

- Top 20 domains by composite score
- Each entry: domain name, organization, tier badge, avg user quality rating, triage pass rate
- Filterable by pillar, time period
- Clickable rows that expand to show recent sources from that domain

**Files owned:** `TopDomainsLeaderboard.tsx`
**Files modified:** Analytics page (add leaderboard section)

---

### Task 5.5: TypeScript Types & API Client Consolidation

**Modifies:** Frontend type files and API clients

**Changes:**

- Add all new TypeScript interfaces to appropriate type files:
  - `QualityBreakdown`, `QualityBadgeProps` to CardDetail types
  - `SourceRating`, `SourceRatingAggregate` to source types
  - `DomainReputation` to a new types file
  - `CreateSignalRequest`, `CreateSignalResponse` to discovery-api types
- Ensure all new API client functions have proper TypeScript types (no `any`)
- Add JSDoc to all new interfaces and type aliases

**Files modified:** Type files in `src/components/CardDetail/types.ts`, `src/lib/discovery-api.ts`, `src/lib/workstream-api.ts`
**New file:** `src/lib/source-rating-api.ts` (if not created in Task 4.2), `src/types/domain-reputation.ts`

---

## Parallel Execution Map

Tasks that can run simultaneously within each layer:

```
Layer 0: [0.1, 0.2, 0.3, 0.4, 0.5] — all independent

Layer 1: [1.1, 1.3, 1.4] in parallel
         then [1.2] (needs 1.1)
         [1.5] can run with any (needs only 0.1)

Layer 2: [2.1, 2.2] in parallel (both use SourceValidator but modify different files)
         [2.3] independent
         [2.4] independent
         [2.5] needs 1.3
         [2.6] independent
         [2.7] needs 1.1 + 1.5

Layer 3: [3.1, 3.2, 3.3, 3.4, 3.5] — all independent (different endpoint sections)

Layer 4: [4.1, 4.2, 4.3, 4.5] in parallel (different components, no shared files)
         [4.4] independent
         [4.6, 4.7] in parallel (different pages)

Layer 5: [5.1, 5.2] in parallel (different concerns)
         [5.3, 5.4, 5.5] in parallel (different files)
```

---

## File Ownership Summary

Prevents conflicts when running parallel agents.

### New Files (exclusively owned by one task)

| File                                                                    | Owner Task                   |
| ----------------------------------------------------------------------- | ---------------------------- |
| `backend/app/domain_reputation_service.py`                              | 1.1                          |
| `backend/app/quality_service.py`                                        | 1.2                          |
| `backend/app/story_clustering_service.py`                               | 1.3                          |
| `backend/app/source_validator.py`                                       | 1.4                          |
| `backend/app/card_creation_service.py`                                  | 3.4                          |
| `backend/app/models/source_rating.py`                                   | 3.1                          |
| `backend/app/models/quality.py`                                         | 3.2                          |
| `backend/app/models/domain_reputation.py`                               | 3.3                          |
| `backend/app/models/card_creation.py`                                   | 3.4                          |
| `frontend/.../components/QualityBadge.tsx`                              | 4.1                          |
| `frontend/.../components/CardDetail/panels/InformationQualityPanel.tsx` | 4.1                          |
| `frontend/.../components/SourceRating/*.tsx`                            | 4.2                          |
| `frontend/.../lib/source-rating-api.ts`                                 | 4.2                          |
| `frontend/.../components/CreateSignal/*.tsx`                            | 4.3                          |
| `frontend/.../components/badges/ExploratoryBadge.tsx`                   | 4.3                          |
| `frontend/.../pages/Methodology.tsx`                                    | 4.5                          |
| `frontend/.../components/analytics/TopDomainsLeaderboard.tsx`           | 5.4                          |
| All `supabase/migrations/YYYYMMDD_*.sql`                                | 0.1-0.5, 1.5, 2.4 (as noted) |

### Shared Files (modified by multiple tasks — MUST be sequential)

| File                                                     | Modified By (in order)                  |
| -------------------------------------------------------- | --------------------------------------- |
| `backend/app/main.py`                                    | 3.1 → 3.2 → 3.3 → 3.4 → 3.5 → 5.1 → 5.2 |
| `backend/app/discovery_service.py`                       | 2.1 → 2.4 → 2.5 → 2.6 → 2.7             |
| `backend/app/workstream_scan_service.py`                 | 2.2 → 2.6 → 2.7                         |
| `backend/app/ai_service.py`                              | 2.3 → 2.4                               |
| `backend/app/research_service.py`                        | 2.3                                     |
| `frontend/.../components/CardDetail/tabs/SourcesTab.tsx` | 4.2                                     |
| `frontend/.../components/CardDetail/CardDetail.tsx`      | 4.1                                     |
| `frontend/.../pages/Discover.tsx`                        | 4.3 → 4.6                               |
| `frontend/.../components/kanban/KanbanCard.tsx`          | 4.7                                     |
| `frontend/.../components/WorkstreamForm.tsx`             | 4.4                                     |
| `frontend/.../lib/discovery-api.ts`                      | 4.3 → 5.5                               |

---

## Documentation Checklist

Every task must complete these before marking done:

- [ ] Module/file-level docstring explaining purpose and how it fits into the system
- [ ] Every public function/method has a docstring with parameters, return type, and behavior description
- [ ] Complex algorithms have step-by-step inline comments
- [ ] TypeScript interfaces have JSDoc on every field
- [ ] Database migrations have header comments with purpose and rollback strategy
- [ ] API endpoints have docstrings describing auth requirements, request/response shapes, and error cases
- [ ] No `// TODO`, `// FIXME`, `// HACK`, or placeholder comments remain
- [ ] No stub functions, mock data, or temporary implementations remain
