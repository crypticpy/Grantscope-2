# Product Requirements Document: Information Quality, Source Credibility & User-Generated Content

**Version:** 1.1
**Date:** February 2025
**Product:** GrantScope2 — AI-Powered Strategic Horizon Scanning System
**Owner:** City of Austin Innovation Office
**Status:** Draft for Review

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Feature 1: Source Quality Index (SQI)](#3-feature-1-source-quality-index-sqi)
4. [Feature 2: User Source Ratings](#4-feature-2-user-source-ratings)
5. [Feature 3: Domain Reputation System & Feedback Loop](#5-feature-3-domain-reputation-system--feedback-loop)
6. [Feature 4: User-Generated Cards ("Create Signal")](#6-feature-4-user-generated-cards-create-signal)
7. [Feature 5: Topic-First Workstreams](#7-feature-5-topic-first-workstreams)
8. [Feature 6: Transparency & Methodology Page](#8-feature-6-transparency--methodology-page)
9. [Feature 7: Pipeline Quality Hardening](#9-feature-7-pipeline-quality-hardening)
10. [Domain Reputation Tier Reference](#10-domain-reputation-tier-reference)
11. [Architecture Audit Findings & Remediation](#11-architecture-audit-findings--remediation)
12. [Implementation Philosophy](#12-implementation-philosophy)
13. [Success Metrics](#13-success-metrics)

---

## 1. Executive Summary

Users have expressed concern about information quality: they cannot confidently explain to leadership how GrantScope2 ensures high-quality, credible data enters the platform. This PRD defines a set of features that address information quality transparency, source credibility, user feedback mechanisms, and user-generated content capabilities.

**Key deliverables:**

- A visible, explainable **Source Quality Index** on every card
- **Per-source user ratings** for quality and municipal relevance
- A **domain reputation system** that feeds user ratings back into the discovery pipeline
- **Manual card creation** for topics outside pre-baked methodology
- **Topic-first workstreams** that generate cards for brand-new areas
- A **transparency/methodology page** explaining how the system works
- **Pipeline hardening** to fix critical quality weaknesses identified in architecture audit

---

## 2. Problem Statement

### 2.1 User Concerns

City of Austin staff using GrantScope2 need to present findings to council members and the mayor. They face these challenges:

1. **Accountability gap:** Users cannot explain _how_ the AI determines information quality. When asked "How do you know this is reliable?", they have no concrete answer beyond "the AI scored it."

2. **No source feedback mechanism:** Users visit source URLs, assess quality manually, and have no way to record that assessment or influence future discovery.

3. **Rigid topic coverage:** The system only scans pre-defined strategic pillars and Top 25 priorities. When new topics arise (e.g., forensics for an upcoming council meeting), users cannot initiate research within the platform.

4. **Municipal relevance is implicit:** There is no explicit measurement of how relevant a source is to _municipal_ government specifically (vs. general technology news).

### 2.2 Technical Concerns (Architecture Audit)

An internal audit of the discovery pipeline identified 5 critical and 12 high-severity quality weaknesses, including:

- No source credibility scoring or domain validation
- RSS feeds can be poisoned (including user-submitted Hacker News)
- AI hallucination can propagate into cards with no fact-checking
- Sources without content auto-pass triage
- Workstream scan cards bypass human review entirely
- Academic pre-prints treated as more credible than news articles
- Echo chamber risk from same story across multiple outlets

Full audit findings are documented in [Section 11](#11-architecture-audit-findings--remediation).

---

## 3. Feature 1: Source Quality Index (SQI)

### 3.1 Overview

A composite quality score (0-100) displayed on every card, computed from the quality characteristics of its underlying sources. This gives users a single, explainable metric to answer "How reliable is this information?"

### 3.2 Score Components

The SQI is computed from five weighted dimensions:

| Component                 | Weight | Description                                                                                                                                                                  |
| ------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Source Authority**      | 30%    | Average domain reputation tier of sources (Tier 1 = 100, Tier 2 = 70, Tier 3 = 45, Untiered = 20)                                                                            |
| **Source Diversity**      | 20%    | Number of distinct source categories represented (RSS, News, Academic, Government, Tech). 5 categories = 100; 1 category = 20                                                |
| **Corroboration**         | 20%    | Number of independent sources confirming the topic. Clustered by semantic similarity to count unique stories, not duplicate coverage. 5+ unique stories = 100; 1 source = 20 |
| **Recency**               | 15%    | Age-weighted freshness. All sources < 30 days = 100; 30-90 days = 70; 90-180 days = 40; > 180 days = 20                                                                      |
| **Municipal Specificity** | 15%    | How directly sources discuss municipal/local government topics. Derived from AI relevance scores and domain type (government domains score higher)                           |

### 3.3 Display

- **Card listing views:** Traffic-light badge: "High Confidence" (75-100, green), "Moderate" (50-74, amber), "Needs Verification" (0-49, red)
- **Card detail page:** New "Information Quality" panel alongside existing ImpactMetricsPanel. Shows overall SQI with a breakdown chart of all 5 components. Tooltip on each component explains the calculation in plain English.
- **Hover tooltip on badge:** Shows SQI score and the number of sources

### 3.4 User Stories

**US-SQI-1:** As a strategic analyst, I want to see an information quality badge on each card in the browse view so that I can quickly identify which cards have strong evidentiary backing before presenting them to leadership.

**Acceptance Criteria:**

- Every card in the Discover page shows a quality badge (High Confidence / Moderate / Needs Verification)
- Badge color-coding is consistent: green (75+), amber (50-74), red (0-49)
- Badge is visible without expanding the card
- Cards with zero sources show "No Sources" state instead of a misleading score

**US-SQI-2:** As a department director, I want to drill into the quality score breakdown on a card detail page so that I can explain to council members exactly why we consider this information reliable.

**Acceptance Criteria:**

- Card detail page shows the 5 SQI components with individual scores and the overall weighted total
- Each component has a plain-English tooltip explaining what it measures
- The breakdown updates in real-time when new sources are added
- A timestamp shows when the SQI was last recalculated

**US-SQI-3:** As a workstream manager, I want to sort and filter cards by quality score so that I can prioritize high-confidence signals for leadership briefings.

**Acceptance Criteria:**

- Discover page supports sorting by SQI (ascending/descending)
- Discover page supports filtering by quality tier (High/Moderate/Needs Verification)
- Workstream kanban shows quality badge on each card

### 3.5 Technical Approach

- New fields on `cards` table: `quality_score INTEGER` (0-100), `quality_breakdown JSONB`
- SQI recalculated via database function triggered on source insert/update/delete
- Backend endpoint: `GET /api/v1/cards/{id}/quality` returns breakdown
- Quality score included in standard card list responses

---

## 4. Feature 2: User Source Ratings

### 4.1 Overview

A lightweight mechanism for users to rate individual sources on quality and municipal relevance, directly from the Sources tab of any card.

### 4.2 Rating Dimensions

| Dimension               | Input Type        | Scale                              | Question                                                   |
| ----------------------- | ----------------- | ---------------------------------- | ---------------------------------------------------------- |
| **Quality**             | Star rating       | 1-5 stars                          | "How reliable and accurate is this source?"                |
| **Municipal Relevance** | Segmented control | High / Medium / Low / Not Relevant | "How relevant is this to municipal government operations?" |
| **Comment**             | Optional text     | Free text, max 280 chars           | "Brief note on why"                                        |

### 4.3 Display

- **Inline on each source card** in the Sources tab: Small star rating + relevance selector below the existing source metadata
- **Community aggregate** shown alongside: "3 ratings, avg 4.2 stars, High relevance" next to the AI's `relevance_to_card` score
- **Visual comparison:** AI assessment vs. human assessment displayed side by side so users can see alignment or divergence

### 4.4 User Stories

**US-SR-1:** As an analyst, I want to rate the quality and municipal relevance of a source after I've reviewed it so that my assessment is recorded and visible to my colleagues.

**Acceptance Criteria:**

- Each source in the Sources tab shows clickable star rating (1-5) and relevance selector
- Rating persists immediately on click (optimistic UI, no submit button)
- User can update their rating at any time
- If I've already rated, my existing rating is pre-filled
- Other users' ratings are shown as an aggregate, not individually (to prevent social pressure)

**US-SR-2:** As a team lead, I want to see the aggregate quality rating from my team next to the AI's relevance score so that I can identify where human judgment diverges from AI assessment.

**Acceptance Criteria:**

- Sources tab shows both "AI Relevance: 85%" and "Team Rating: 4.2/5 (3 ratings)" for each source
- When team rating diverges significantly from AI score (>30 points on normalized scale), a visual indicator highlights the divergence
- Aggregate updates in real-time as new ratings are submitted

**US-SR-3:** As a department director, I want to leave a brief note explaining why a source is high or low quality so that my reasoning is available to colleagues reviewing the same card.

**Acceptance Criteria:**

- Optional comment field accepts up to 280 characters
- Comments are visible to all users viewing the source
- Comments are attributed to the author (name, not anonymous)
- Comment can be edited or deleted by its author

### 4.5 Technical Approach

- New table: `source_ratings` (`id`, `source_id` FK, `user_id` FK, `quality_rating` INTEGER 1-5, `relevance_rating` TEXT, `comment` TEXT, `created_at`, `updated_at`). Unique constraint on `(source_id, user_id)`.
- API endpoints: `POST /api/v1/sources/{id}/rate`, `GET /api/v1/sources/{id}/ratings`
- Source list responses include aggregated rating data
- RLS: Users can read all ratings, write/update only their own

---

## 5. Feature 3: Domain Reputation System & Feedback Loop

### 5.1 Overview

An evolving domain reputation database that combines curated authority tiers with user rating signals to influence future discovery pipeline behavior.

### 5.2 Domain Reputation Table

Each domain gets a reputation profile built from three signal types:

| Signal                   | Source                                                   | Weight |
| ------------------------ | -------------------------------------------------------- | ------ |
| **Curated Tier**         | Pre-seeded from expert-compiled list (see Section 10)    | 50%    |
| **User Ratings**         | Aggregated quality/relevance ratings from source_ratings | 30%    |
| **Pipeline Performance** | Triage pass rate, auto-approval rate per domain          | 20%    |

### 5.3 How It Feeds Back Into Discovery

1. **Triage boost/penalty:** During AI triage, sources from Tier 1 domains get a confidence boost (+0.1), while sources from domains with low user ratings get a penalty (-0.1). This shifts borderline sources above or below the 0.6 threshold.

2. **Source budget allocation:** Discovery runs allocate more of their source-per-category budget to categories and domains with higher reputation scores. If government sources consistently rate higher, the fetcher caps increase for that category.

3. **New domain learning:** When a domain appears that is not in the curated list, its initial reputation is "Untiered" (lowest weight). As users rate its sources, the domain's reputation adjusts organically.

4. **Reputation decay:** Domain reputation scores incorporate a time decay. Recent ratings weigh more heavily than older ones, so the system adapts to changes in source quality over time.

### 5.4 User Stories

**US-DR-1:** As a system administrator, I want the platform to come pre-loaded with a curated list of authoritative municipal research sources so that the AI prioritizes credible domains from day one.

**Acceptance Criteria:**

- Domain reputation table is seeded with 100+ domains across 3 tiers (see Section 10)
- Each domain entry includes: domain pattern, tier (1/2/3), organization name, category
- Tier assignments are visible in an admin view
- Admin can add, edit, or remove domain entries

**US-DR-2:** As an analyst, I want my source ratings to gradually improve the system's source selection so that domains I rate highly appear more often and domains I rate poorly appear less.

**Acceptance Criteria:**

- After 5+ ratings for a domain, the domain's aggregated user score is factored into triage
- The triage confidence adjustment is visible in discovery run reports
- The system never completely blocks a domain based on user ratings alone (minimum floor)
- Monthly report shows how user ratings have shifted domain reputations

**US-DR-3:** As a workstream manager, I want to see which domains contribute the most high-quality sources so that I can recommend those publications to colleagues for manual reading.

**Acceptance Criteria:**

- Analytics page shows a "Top Domains by Quality" leaderboard
- Leaderboard combines AI triage pass rate with average user quality rating
- Filterable by pillar and time period
- Clickable to see all sources from that domain

### 5.5 Technical Approach

- New table: `domain_reputation` (`id`, `domain_pattern` TEXT UNIQUE, `organization_name`, `category`, `curated_tier` INTEGER 1-3 NULL, `user_quality_avg` NUMERIC, `user_relevance_avg` NUMERIC, `user_rating_count` INTEGER, `triage_pass_rate` NUMERIC, `composite_score` NUMERIC 0-100, `last_updated`)
- Aggregate computation runs nightly or on-demand
- Discovery service reads domain reputation at triage stage
- Seed migration with curated domain list from Section 10

---

## 6. Feature 4: User-Generated Cards ("Create Signal")

### 6.1 Overview

A workflow allowing users to create cards for topics not covered by the existing strategic framework. Supports both quick topic-based creation (AI-assisted) and manual entry.

### 6.2 Two Creation Modes

**Mode A: Quick Card from Topic**

1. User enters a topic phrase (e.g., "forensic technology for municipal law enforcement")
2. System runs AI analysis on the topic to generate initial card metadata
3. System triggers a mini-scan (5-10 sources) to find relevant content
4. Card is created with `origin: 'user_created'` and the user as `created_by`
5. User optionally adds the card to a workstream

**Mode B: Full Manual Entry**

1. User fills a form: name, description, pillar(s) or "Exploratory", horizon, stage
2. User can paste seed URLs for initial sources
3. System enriches from provided URLs (fetch content, generate AI analysis)
4. Card is created and scored based on available information
5. Card enters the system at `review_status: 'active'` (user-created = pre-approved)

### 6.3 Exploratory Cards

Cards that don't align with existing pillars receive special handling:

- `pillars` array may be empty
- New `is_exploratory` boolean flag on cards table
- Exploratory cards are visually distinct (different badge style)
- They still participate in weekly scans for updates
- Users can later assign pillars as the topic matures

### 6.4 User Stories

**US-UC-1:** As a strategic analyst, I want to create a card for a topic that emerged in a leadership meeting so that I can begin tracking it in GrantScope2 immediately, even if it doesn't fit our current strategic pillars.

**Acceptance Criteria:**

- "Create Signal" button is accessible from the Discover page header and the Workstream page
- Quick creation requires only a topic phrase (3+ words)
- AI generates card name, summary, classification, and scores within 30 seconds
- Mini-scan starts automatically and adds sources within 2 minutes
- Card appears in the Discover page and is searchable immediately
- If no pillar fits, card is labeled "Exploratory" with a distinct visual badge

**US-UC-2:** As a department director preparing for a council meeting on forensics, I want to create a card with specific URLs I've already found so that those sources are analyzed and scored within the GrantScope2 framework.

**Acceptance Criteria:**

- Manual creation form accepts 1-10 seed URLs
- System fetches and analyzes content from each URL
- AI generates scores, classification, and summary based on the provided sources
- Card is immediately available with sources displayed in the Sources tab
- User can edit the AI-generated name and summary before saving
- SQI is calculated based on the seed sources

**US-UC-3:** As a workstream manager, I want user-created cards to be automatically monitored in weekly scans so that they stay current without manual intervention.

**Acceptance Criteria:**

- User-created cards with `status: 'active'` are included in nightly scans
- New sources discovered for user-created cards are added and surface in the Sources tab
- Score history is tracked the same as discovery-created cards
- Users receive notification (in-app) when significant new sources are found

### 6.5 Technical Approach

- New fields on `cards`: `origin TEXT` ('discovery', 'workstream_scan', 'user_created', 'manual'), `is_exploratory BOOLEAN DEFAULT FALSE`
- New endpoint: `POST /api/v1/cards/create-from-topic` (Mode A)
- Enhanced existing `POST /api/v1/cards` endpoint for Mode B with URL enrichment
- Mini-scan reuses `WorkstreamScanService` logic with a single-topic scope
- Frontend: New `CreateSignalModal` component with tabbed mode selection

---

## 7. Feature 5: Topic-First Workstreams

### 7.1 Overview

Enhanced workstream creation flow that supports brand-new topics with no existing cards. When auto-populate returns zero results, the system proactively offers to discover content.

### 7.2 Enhanced Creation Flow

```
User creates workstream with keywords
        |
        v
Auto-populate checks existing cards
        |
        +-- Found cards --> Normal flow (add to inbox)
        |
        +-- Zero/few cards found -->
                |
                v
        Prompt: "No existing signals match. Run a discovery scan?"
                |
                +-- Yes --> Trigger workstream scan immediately
                |           Show real-time progress
                |           Add discovered cards to inbox
                |
                +-- No --> Create empty workstream
                           User can trigger scan later
```

### 7.3 Keyword Suggestions

New AI-assisted keyword expansion: user types a topic phrase, and the system suggests related search terms.

Example:

- Input: "forensic technology"
- Suggestions: "digital forensics municipal", "crime lab automation", "forensic DNA technology city", "evidence management systems", "forensic science government"

### 7.4 User Stories

**US-TW-1:** As a strategic analyst exploring a new area like forensics, I want to create a workstream for a topic that has no existing cards and have the system discover relevant content for me.

**Acceptance Criteria:**

- Workstream creation form does not require pillar selection (keywords alone are sufficient)
- When auto-populate returns 0 cards, a prompt offers to "Discover content for this topic"
- If accepted, a workstream scan starts and progress is shown in real-time
- Discovered cards appear in the workstream inbox within 3-5 minutes
- The workstream is functional even with zero initial cards (empty state with scan prompt)

**US-TW-2:** As an analyst who is not sure what search terms to use, I want the system to suggest related keywords when I describe a topic so that I can build a comprehensive workstream quickly.

**Acceptance Criteria:**

- After entering 1+ keywords, a "Suggest Related Terms" button is available
- System returns 5-10 suggested keywords within 5 seconds
- Suggestions are displayed as selectable chips that can be added with a click
- Suggestions include municipal-specific variants of the topic
- User can edit or remove any suggested term before saving

**US-TW-3:** As a team lead, I want cards discovered through a topic-first workstream to be visible to the entire team so that other analysts can find and use them.

**Acceptance Criteria:**

- Cards created via workstream scans appear in the global Discover page
- Cards retain a "Discovered via [Workstream Name]" provenance indicator
- Other users can add these cards to their own workstreams
- Cards participate in the global weekly scan for updates

### 7.5 Technical Approach

- Modify `WorkstreamForm` to make pillar selection optional
- Add keyword suggestion endpoint: `POST /api/v1/ai/suggest-keywords` (uses GPT-4.1-mini)
- Modify auto-populate response to include `match_count` so frontend can offer scan
- Add auto-scan-on-create option to workstream creation flow
- Frontend: Enhanced `WorkstreamForm` with suggestion chips and scan-on-create toggle

---

## 8. Feature 6: Transparency & Methodology Page

### 8.1 Overview

A public-facing page within the app that explains how GrantScope2 discovers, verifies, and scores information. This enables users to confidently explain the system's methodology to leadership.

### 8.2 Page Sections

**Section 1: How We Find Content**

- Description of the 5 source categories (RSS, News, Academic, Government, Tech)
- Named source outlets and why they were selected
- Explanation of query generation from strategic pillars and priorities
- Source diversity goals and metrics

**Section 2: How We Verify Quality**

- AI triage process (what the AI looks for, what gets filtered out)
- Confidence thresholds and what they mean
- Domain reputation system (curated tiers, user feedback integration)
- Deduplication process (how we prevent echo chambers)
- Human review workflow (what requires manual approval)

**Section 3: How We Score**

- Explanation of each score dimension in plain English:
  - **Impact:** How big of a deal is this for the city?
  - **Relevance:** How much does this matter to Austin specifically?
  - **Velocity:** How fast is this moving?
  - **Novelty:** Have we seen this before?
  - **Risk:** How much could this hurt us if we ignore it?
  - **Maturity/Credibility:** How trustworthy and mature is the evidence?
  - **Source Quality Index:** How reliable is the underlying information?
- Score ranges, color-coding, and what High/Medium/Low means
- How scores change over time (score history tracking)

**Section 4: How Users Improve the System**

- Source ratings and how they feed back into discovery
- Card follows and dismissals as quality signals
- Domain reputation learning from user behavior
- User-generated cards and topic-first workstreams

**Section 5: Our Source Authority Tiers**

- Interactive table of all tiered domains with organization names and categories
- Explanation of tier definitions
- Last updated date

**Section 6: Limitations & Caveats**

- AI can make errors; human review is essential
- Pre-prints are not peer-reviewed
- Scores are estimates, not measurements
- System improves over time with user feedback

### 8.3 User Stories

**US-TP-1:** As a department director presenting to council, I want to access a clear methodology page so that I can explain how GrantScope2 ensures information quality when asked.

**Acceptance Criteria:**

- Methodology page is accessible from the main navigation (e.g., "How It Works" or "Methodology")
- Page is readable by non-technical users (no jargon without explanation)
- Each section has a summary at the top and expandable details
- Page loads without authentication (optionally, for sharing with external stakeholders)
- Print-friendly layout for offline use

**US-TP-2:** As an analyst new to the platform, I want to understand what each score means so that I interpret card data correctly.

**Acceptance Criteria:**

- Each score dimension has a plain-English definition, the numeric range, and a practical example
- Visual examples show what a "high" vs "low" score looks like
- Linked from score tooltips throughout the app (click "What does this mean?" -> methodology page section)

### 8.4 Technical Approach

- New frontend route: `/methodology`
- Static content page with expandable sections (Radix UI Accordion)
- Source tier table fetched from `domain_reputation` API endpoint
- No backend logic needed beyond the domain reputation API
- Consider making this page publicly accessible (no auth required)

---

## 9. Feature 7: Pipeline Quality Hardening

### 9.1 Overview

Targeted fixes for the critical and high-severity weaknesses identified in the architecture audit. These are infrastructure improvements that users won't see directly but that materially improve the data entering the platform.

### 9.2 Critical Fixes

**FIX-C1: Reject content-less sources instead of auto-passing**

_Current behavior:_ Sources with no content are auto-passed through triage with confidence 0.65.
_New behavior:_ Sources with fewer than 100 characters of content are rejected from triage. A warning is logged but they do not enter the analysis pipeline.

**Acceptance Criteria:**

- Sources with < 100 chars content are filtered before triage
- Filtered sources are logged with reason "insufficient_content"
- Discovery run reports show count of content-filtered sources
- No content-less sources appear as card sources

**FIX-C2: Require human review for workstream scan cards**

_Current behavior:_ Workstream scan cards are auto-approved with `review_status: 'approved'`.
_New behavior:_ Workstream scan cards are created with `review_status: 'pending_review'` and added to the workstream inbox. They require the user to explicitly approve (move out of inbox) or can be auto-approved if their SQI >= 75.

**Acceptance Criteria:**

- Workstream scan cards enter `pending_review` status
- Cards appear in workstream inbox with a "Needs Review" badge
- User must explicitly approve (drag to Screening column) or approve via button
- Cards with SQI >= 75 may be auto-approved (configurable threshold)
- Rejected cards are removed from the workstream

**FIX-C3: Add score range clamping**

_Current behavior:_ AI-returned scores are accepted without validation. Parse error defaults produce mid-range scores that look legitimate.
_New behavior:_ All AI scores are clamped to their documented ranges. Parse error defaults are flagged with a `scores_are_defaults: true` flag.

**Acceptance Criteria:**

- Credibility clamped to 1.0-5.0, velocity to 1.0-10.0, likelihood to 1.0-9.0, etc.
- Parse error fallback scores include `scores_are_defaults: true` in card metadata
- Cards with default scores show a "Scores Unverified" indicator in the UI
- Score conversion formulas are consistent across discovery_service, workstream_scan_service, and research_service

**FIX-C4: Fix velocity/likelihood score mapping inconsistency**

_Current behavior:_ `research_service.py` maps `velocity_score` from `likelihood * 11`, while `discovery_service.py` and `workstream_scan_service.py` use `velocity * 10`.
_New behavior:_ All pipelines use `velocity * 10` consistently.

**Acceptance Criteria:**

- All three services use `int(analysis.velocity * 10)` for velocity_score
- Existing cards with incorrect velocity scores are flagged for re-scoring
- Score history is not retroactively modified

### 9.3 High-Severity Fixes

**FIX-H1: Add source freshness filtering**

Sources older than a configurable threshold are rejected before triage:

- News/Tech: 90 days
- Academic: 365 days
- Government: 730 days (2 years)
- RSS: 90 days

**Acceptance Criteria:**

- Each source category has a configurable max age
- Sources exceeding max age are filtered before triage
- Filtered sources are counted in discovery run reports
- Date parsing handles multiple formats gracefully (ISO, RFC 2822, natural language)

**FIX-H2: Distinguish academic pre-prints from peer-reviewed publications**

Add `is_peer_reviewed` flag to source metadata. arXiv sources default to `false`. Default relevance for non-peer-reviewed academic sources reduced from 0.8 to 0.6.

**Acceptance Criteria:**

- Sources table has new `is_peer_reviewed BOOLEAN` field
- arXiv sources are marked `is_peer_reviewed: false`
- Non-peer-reviewed default relevance reduced to 0.6
- Sources tab shows "Pre-print" vs "Published" indicator for academic sources
- SQI calculation weights peer-reviewed sources higher

**FIX-H3: Add story-level deduplication**

Before creating cards from multiple sources, cluster semantically similar sources to detect when multiple outlets report the same underlying story. Count unique stories, not outlet repetitions.

**Acceptance Criteria:**

- Sources with cosine similarity >= 0.90 to each other are clustered as the same story
- Card creation uses cluster count (unique stories) not raw source count
- SQI corroboration component uses cluster count
- Cluster information is stored in source metadata for auditability

**FIX-H4: Fix pillar code mapping**

Replace lossy mappings (`"HG" -> "EC"`, `"PS" -> "CH"`) with direct support for all 6 pillar codes in the database. If the database schema doesn't support all codes, add the missing ones.

**Acceptance Criteria:**

- All 6 pillar codes (CH, EW, HG, HH, MC, PS) are supported natively
- No more pillar mapping/conversion layer
- Existing cards with mapped pillars are corrected to their intended codes

**FIX-H5: Enforce workstream scan rate limiting in code**

The docstring claims 2 scans per workstream per day, but the code doesn't enforce it.

**Acceptance Criteria:**

- WorkstreamScanService checks scan count before execution
- Returns clear error message when rate limit exceeded
- Rate limit is configurable via environment variable
- Scan history endpoint shows remaining quota

### 9.4 User Stories for Pipeline Hardening

**US-PH-1:** As a system administrator, I want content-less sources to be rejected rather than auto-approved so that cards are always backed by substantive content.

**US-PH-2:** As a strategic analyst, I want to know when card scores are AI defaults (from a parse error) rather than genuine assessments so that I can flag those cards for re-analysis.

**US-PH-3:** As a workstream manager, I want workstream-discovered cards to require my approval before becoming "active" so that I maintain quality control over my research pipeline.

---

## 10. Domain Reputation Tier Reference

### 10.1 Tier Definitions

- **Tier 1 (Highest Authority):** Primary authoritative sources — original research producers, government agencies, and organizations whose data and analysis are the foundation of municipal decision-making.
- **Tier 2 (Established Credible):** Well-respected organizations with strong track records in municipal/government research, policy, and reporting.
- **Tier 3 (Notable/Useful):** Credible organizations producing relevant content, but either more specialized, newer, or covering municipal topics as a secondary focus.
- **Untiered:** Unknown or new domains. Start with lowest credibility weight. Can be promoted through positive user ratings.

### 10.2 Tier 1: Highest Authority (~35 organizations)

**Management Consulting & Advisory:**
| Organization | Domain(s) |
|---|---|
| Gartner | gartner.com |
| Deloitte Center for Government Insights | deloitte.com |
| McKinsey & Company | mckinsey.com |

**Government Research & Advisory:**
| Organization | Domain(s) |
|---|---|
| Brookings Institution | brookings.edu |
| RAND Corporation | rand.org |
| National League of Cities (NLC) | nlc.org |
| ICMA | icma.org |
| U.S. Conference of Mayors | usmayors.org |

**Government Technology Media:**
| Organization | Domain(s) |
|---|---|
| Government Technology | govtech.com |
| Governing | governing.com |

**Academic Institutions:**
| Organization | Domain(s) |
|---|---|
| Harvard Kennedy School / Ash Center | ash.harvard.edu |
| Data-Smart City Solutions (Harvard) | datasmart.hks.harvard.edu |
| UT Austin LBJ School | lbj.utexas.edu |

**Federal/State Government:**
| Organization | Domain(s) |
|---|---|
| U.S. GAO | gao.gov |
| Congressional Research Service | crsreports.congress.gov |
| EPA | epa.gov |
| HUD | hud.gov |
| FEMA | fema.gov |
| U.S. DOT | dot.gov, fhwa.dot.gov |
| Census Bureau | census.gov |
| Texas Comptroller | comptroller.texas.gov |
| TCEQ | tceq.texas.gov |
| TxDOT | txdot.gov |

**Municipal Innovation Networks:**
| Organization | Domain(s) |
|---|---|
| Bloomberg Philanthropies | bloomberg.org, whatworkscities.bloomberg.org |
| Bloomberg Cities Network (JHU) | bloombergcities.jhu.edu |

**Professional Associations:**
| Organization | Domain(s) |
|---|---|
| GFOA | gfoa.org |
| APA | planning.org |
| NACTO | nacto.org |
| Texas Municipal League | tml.org |

**Think Tanks:**
| Organization | Domain(s) |
|---|---|
| Urban Institute | urban.org |
| Pew Research Center | pewresearch.org |
| Lincoln Institute of Land Policy | lincolninst.edu |
| Urban Land Institute | uli.org |

**International:**
| Organization | Domain(s) |
|---|---|
| OECD | oecd.org |

### 10.3 Tier 2: Established Credible (~50 organizations)

**Consulting:** Accenture, BCG, Forrester, IDC, Bain, PwC, KPMG, EY, Guidehouse

**Government Research:** NACo (naco.org), NAPA (napawash.org), NCSL (ncsl.org), NGA (nga.org), CSG (csg.org), Results for America (results4america.org)

**Gov Tech Media:** StateScoop (statescoop.com), Route Fifty (route-fifty.com), FedScoop (fedscoop.com), FCW (fcw.com), Government Executive (govexec.com), GCN (gcn.com), Smart Cities Dive (smartcitiesdive.com)

**Academic:** MIT DUSP (dusp.mit.edu), Georgetown Beeck Center (beeckcenter.georgetown.edu), ASU Center for Urban Innovation (urbaninnovation.asu.edu), UIC CUPPA (cuppa.uic.edu)

**Federal Agencies:** DOE (energy.gov), DHS/CISA (cisa.gov), NIST (nist.gov), FCC (fcc.gov), BLS (bls.gov), Texas Governor's Office (gov.texas.gov)

**Professional Associations:** APWA (apwa.org), AWWA (awwa.org), IACP (theiacp.org), NFPA (nfpa.org), NASCIO (nascio.org), CDG (centerdigitalgov.com), NRPA (nrpa.org), ASCE (asce.org), TCMA (via tml.org), TAGITM (via tml.org)

**Innovation Networks:** Code for America (codeforamerica.org), Nesta (nesta.org.uk), Smart Growth America (smartgrowthamerica.org)

**Think Tanks:** New America (newamerica.org), Volcker Alliance (volckeralliance.org), Milken Institute (milkeninstitute.org), Bipartisan Policy Center (bipartisanpolicy.org), CBPP (cbpp.org)

**International:** WEF (weforum.org), UN-Habitat (unhabitat.org), World Bank (worldbank.org)

**General:** All .gov domains not individually classified, all .edu domains not individually classified

### 10.4 Tier 3: Notable/Useful (~15 organizations)

Capgemini (capgemini.com), StateTech Magazine (statetechmagazine.com), CyberScoop (cyberscoop.com), Northeastern (cssh.northeastern.edu), Indiana O'Neill School (oneill.indiana.edu), Penn IUR (penniur.upenn.edu), CNU (cnu.org), Strong Towns (strongtowns.org), Enterprise Community Partners (enterprisecommunity.org), Tax Foundation (taxfoundation.org), Reason Foundation (reason.org), TPCA (texaspolicechiefs.org), IAFC (iafc.org), NAR (nar.realtor)

### 10.5 Domain Matching Rules

- Use suffix matching: `*.harvard.edu` catches all Harvard subdomains
- Government domains: Any `*.gov` gets automatic Tier 2 minimum
- Education domains: Any `*.edu` gets automatic Tier 3 minimum
- Texas-specific sources (tml.org, tceq.texas.gov, etc.) get a +10 relevance bonus for Austin scans
- Consulting firm marketing pages (e.g., `/services/`, `/solutions/`) score lower than research pages (e.g., `/insights/`, `/research/`)

---

## 11. Architecture Audit Findings & Remediation

### 11.1 Summary of Findings

| Severity     | Count | Addressed In                   |
| ------------ | ----- | ------------------------------ |
| **Critical** | 5     | Feature 7 (Pipeline Hardening) |
| **High**     | 12    | Features 3, 5, 7               |
| **Medium**   | 11    | Features 3, 7, future releases |
| **Low**      | 3     | Backlog                        |

### 11.2 Critical Findings

| ID  | Finding                        | Current Impact                       | Remediation                             | Feature       |
| --- | ------------------------------ | ------------------------------------ | --------------------------------------- | ------------- |
| C1  | No source credibility scoring  | All domains treated equally          | Domain Reputation System                | Feature 3     |
| C2  | RSS feeds can be poisoned      | Hacker News content enters unchecked | Content minimum + domain reputation     | Features 3, 7 |
| C3  | AI hallucination propagation   | No fact-checking on AI outputs       | Score clamping + default flagging + SQI | Features 1, 7 |
| C4  | Content-less sources auto-pass | URL-only sources bypass triage       | Reject sources < 100 chars              | Feature 7     |
| C5  | Workstream cards auto-approved | No human review for scan results     | Require review for scan-created cards   | Feature 7     |

### 11.3 High-Severity Findings

| ID  | Finding                             | Remediation                             | Feature   |
| --- | ----------------------------------- | --------------------------------------- | --------- |
| H1  | Echo chamber risk                   | Story-level clustering/dedup            | Feature 7 |
| H2  | No freshness filtering              | Age-based rejection by category         | Feature 7 |
| H3  | Pre-prints treated as peer-reviewed | Peer-review flag + relevance adjustment | Feature 7 |
| H4  | Fragile web scraping selectors      | Monitor for failures, add health checks | Backlog   |
| H5  | Triage threshold too low (0.6)      | Evaluate raising to 0.65-0.70           | Feature 7 |
| H6  | Parse error defaults undetected     | Flag scores_are_defaults in metadata    | Feature 7 |
| H7  | Pillar mapping lossy                | Support all 6 pillar codes natively     | Feature 7 |
| H8  | Score conversion inconsistent       | Standardize velocity = velocity \* 10   | Feature 7 |
| H9  | Card content overwritten            | Add versioning for AI-enhanced content  | Future    |
| H10 | GPT Researcher is a black box       | Log all GPT Researcher source URLs      | Future    |
| H11 | Workstream rate limit unenforced    | Add code-level enforcement              | Feature 7 |
| H12 | No domain diversity enforcement     | Domain caps per card/run                | Future    |

---

## 12. Implementation Philosophy

### 12.1 Approach

All features in this PRD will be implemented by AI coding agents operating autonomously. There are no human developers or fixed timelines. Work proceeds at whatever pace yields the highest quality output.

### 12.2 Guiding Principles

- **Complete implementation only.** No stubs, no placeholders, no `// TODO` comments, no mock data left behind. Every function is fully implemented, every edge case is handled, every error path has a meaningful response. If a feature isn't ready, it isn't merged.

- **Thorough documentation.** Every new module, function, class, and API endpoint gets clear docstrings and inline comments explaining _why_, not just _what_. Complex algorithms (SQI calculation, domain reputation scoring, story clustering) get dedicated doc blocks explaining the methodology. TypeScript interfaces get JSDoc comments. Database migrations get header comments explaining purpose and rollback strategy.

- **Dependency-ordered execution.** Features are built in strict dependency order: database schema first, then backend services, then API endpoints, then frontend components. No layer is built until the layer it depends on is complete and tested. See the accompanying Development Plan for the full dependency graph.

- **Delight the end user.** These are city government employees presenting to elected officials. Every UI element should feel polished, professional, and confidence-inspiring. Quality badges should be immediately legible. Rating controls should be frictionless. The methodology page should be something a director is _proud_ to show to a council member. Transitions should be smooth, loading states should be informative, and empty states should guide users toward productive actions.

- **Slow and steady.** There is no rush. Each feature should be implemented thoroughly before moving to the next. Cutting corners to move faster is explicitly discouraged. A feature that works perfectly is better than three features that mostly work.

---

## 13. Success Metrics

### Quantitative

| Metric                                                        | Baseline         | Target                            | Measurement                      |
| ------------------------------------------------------------- | ---------------- | --------------------------------- | -------------------------------- |
| % of cards with SQI >= 50                                     | N/A (new metric) | > 70%                             | Weekly calculation               |
| User source ratings per week                                  | 0                | > 50                              | source_ratings table count       |
| Domain reputation coverage (% of sources from tiered domains) | ~30% (estimated) | > 60%                             | Discovery run reports            |
| User-created cards per month                                  | 0                | > 10                              | Cards with origin='user_created' |
| Workstream scans triggered per week                           | ~5               | > 15                              | workstream_scans table           |
| Content-less sources rejected                                 | 0                | 100%                              | Discovery run filter counts      |
| Time to explain methodology to leadership                     | Unmeasured       | < 5 minutes with methodology page | User survey                      |

### Qualitative

- Users report increased confidence in presenting GrantScope2 findings to council
- Leadership accepts GrantScope2 data as credible for decision-making
- Users actively rate sources (indicating engagement with quality)
- New topics (like forensics) are successfully tracked end-to-end within the platform
- Methodology page is referenced in council presentations

---

## Appendix A: Glossary

| Term                       | Definition                                                                       |
| -------------------------- | -------------------------------------------------------------------------------- |
| **SQI**                    | Source Quality Index — composite score (0-100) measuring information reliability |
| **Card**                   | Atomic unit of strategic intelligence in GrantScope2                             |
| **Pillar**                 | Strategic category (CH, EW, HG, HH, MC, PS) aligned with Austin's framework      |
| **Triage**                 | Fast AI relevance check that filters content before full analysis                |
| **Domain Reputation**      | Credibility score assigned to a source's publishing domain                       |
| **Exploratory Card**       | User-created card that doesn't align with predefined pillars                     |
| **Topic-First Workstream** | Workstream created around a new topic with no pre-existing cards                 |
| **Story Cluster**          | Group of sources that report on the same underlying event/story                  |

## Appendix B: Related Documents

- `docs/07_AI_PIPELINE.md` — Current AI pipeline documentation
- `docs/04_DATA_MODEL.md` — Current data model specification
- `docs/09_TAXONOMY.md` — Strategic taxonomy definitions
- `docs/DEV_PLAN_Information_Quality.md` — Dependency-ordered development plan
