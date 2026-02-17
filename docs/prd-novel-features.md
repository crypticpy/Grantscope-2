# Product Requirements Document: Novel Differentiating Features

**Version:** 1.0
**Date:** February 2026
**Product:** GrantScope2 -- AI-Powered Strategic Horizon Scanning System
**Owner:** City of Austin Innovation Office
**Status:** Draft for Review

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Strategic Context](#2-strategic-context)
3. [Feature 1: Cross-Signal Pattern Detection](#3-feature-1-cross-signal-pattern-detection)
4. [Feature 2: Signal Velocity & Trajectory Tracking](#4-feature-2-signal-velocity--trajectory-tracking)
5. [Feature 3: Natural Language Querying ("Ask GrantScope2")](#5-feature-3-natural-language-querying-ask-grantscope2)
6. [Feature 4: Peer City Intelligence](#6-feature-4-peer-city-intelligence)
7. [Feature 5: Proactive Email Digests](#7-feature-5-proactive-email-digests)
8. [Feature 6: Grant & Funding Matcher](#8-feature-6-grant--funding-matcher)
9. [Feature 7: Austin-Specific Impact Analysis](#9-feature-7-austin-specific-impact-analysis)
10. [Feature 8: Signal Decay Detection](#10-feature-8-signal-decay-detection)
11. [Implementation Roadmap](#11-implementation-roadmap)
12. [Success Metrics](#12-success-metrics)
13. [Risks & Mitigations](#13-risks--mitigations)

---

## 1. Executive Summary

GrantScope2 already automates signal discovery and classification. This PRD defines the next generation of features that transform GrantScope2 from a signal aggregation tool into an **intelligence platform** -- one that finds patterns humans miss, tracks how the landscape shifts over time, and answers strategic questions on demand.

These eight features collectively represent the capabilities that differentiate GrantScope2 from traditional consulting engagements (Gartner, McKinsey, Deloitte) and static trend report subscriptions. Where a $500K/year consulting engagement delivers quarterly slide decks with generic industry analysis, GrantScope2 delivers continuous, Austin-specific, cross-domain intelligence that improves with every interaction.

**Priority 1 (Build Now):** Cross-Signal Pattern Detection, Signal Velocity Tracking, Ask GrantScope2, Peer City Intelligence, Proactive Email Digests

**Priority 2 (Next Phase):** Grant & Funding Matcher, Austin-Specific Impact Analysis, Signal Decay Detection

---

## 2. Strategic Context

### 2.1 Why These Features Matter

Traditional horizon scanning suffers from three structural limitations:

1. **Siloed analysis.** Consultants analyze mobility separately from housing separately from public health. The most consequential trends emerge at the intersections.
2. **Point-in-time snapshots.** A quarterly report captures one moment. By the time it reaches a council member, the landscape has shifted.
3. **Passive consumption.** Staff receive reports but cannot interrogate the underlying data. Follow-up questions require another engagement.

GrantScope2's novel features address all three limitations by making intelligence continuous, cross-domain, and interactive.

### 2.2 Competitive Positioning

| Capability                     | Gartner/McKinsey        | Static Trend Tools | GrantScope2 (Current) | GrantScope2 (This PRD)       |
| ------------------------------ | ----------------------- | ------------------ | --------------------- | ---------------------------- |
| Signal discovery               | Manual                  | Automated          | Automated             | Automated                    |
| Cross-domain pattern detection | Rare, analyst-dependent | None               | None                  | **AI-driven, nightly**       |
| Velocity tracking              | Annual benchmarks       | None               | None                  | **Continuous, per-signal**   |
| Natural language Q&A           | Analyst on retainer     | None               | None                  | **Self-service, instant**    |
| Peer city benchmarking         | Custom research         | None               | None                  | **Automated, continuous**    |
| Austin specificity             | Custom engagement       | None               | Partial               | **Deep contextual analysis** |
| Cost                           | $300-500K/year          | $20-50K/year       | Internal              | Internal                     |

---

## 3. Feature 1: Cross-Signal Pattern Detection

### 3.1 What It Does

An AI system that analyzes all active signals across strategic pillars to identify emergent cross-domain connections that siloed analysis would miss. Rather than treating each signal in isolation, the system clusters related signals and synthesizes high-level insights about what the convergence means for Austin.

**Example insight:** "Autonomous vehicle pilots (Mobility) + aging population growth data (Community Health) + transit budget constraints (Economic) suggest an opportunity for autonomous senior shuttle programs. Denver and Portland are already piloting similar programs."

### 3.2 Why It Matters

Cross-domain pattern detection is where GrantScope2 delivers value that no consulting engagement can match at scale. A human analyst might connect two domains they personally understand, but systematically scanning all six pillars for emergent intersections requires either a large team or AI. This is GrantScope2's single most defensible differentiator.

**Versus Gartner/McKinsey:** Consulting engagements are scoped to one domain. Cross-domain insights require separate engagements, separate analysts, and manual synthesis -- if they happen at all.

### 3.3 User Stories

- As a **strategic planning director**, I want to see where trends in different pillars converge so that I can identify opportunities before they become obvious.
- As a **department head**, I want to understand how signals outside my domain might affect my programs so that I am not blindsided by second-order effects.
- As an **innovation office analyst**, I want the system to surface non-obvious connections so that I can brief leadership on emerging cross-cutting themes.
- As a **budget analyst**, I want to see where multiple trends converge on a single infrastructure need so that I can justify capital investment with multiple supporting signals.

### 3.4 Technical Approach

**Architecture: Nightly batch job via existing worker infrastructure.**

1. **Signal collection.** Query all active cards (status = active, not archived) with their current embeddings from the `cards` table.
2. **Embedding clustering.** Use HDBSCAN or k-means on the pgvector embeddings to identify clusters of semantically related signals that span multiple pillars. Only clusters containing cards from 2+ different pillars are candidates.
3. **LLM synthesis.** For each cross-pillar cluster, send the card summaries to GPT-4 with a prompt that asks: (a) What pattern or convergence do these signals represent? (b) What is the strategic implication for a mid-size US city? (c) What actions should city leadership consider?
4. **Insight storage.** Create an `insights` table to store generated insights, linked to their source cards via a junction table `insight_cards`.
5. **Deduplication.** Before storing, embed the new insight and check similarity against existing insights (threshold 0.90). Update existing insights rather than creating near-duplicates.
6. **Surfacing.** Display insights on the Dashboard in a new "AI Insights" section. Each insight card shows the synthesis, links to contributing signals, and the date generated.

**New database objects:**

```sql
CREATE TABLE insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    detail TEXT,
    pillars_involved TEXT[] NOT NULL,
    confidence FLOAT CHECK (confidence BETWEEN 0 AND 1),
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'dismissed', 'archived')),
    embedding VECTOR(1536),
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE insight_cards (
    insight_id UUID REFERENCES insights(id) ON DELETE CASCADE,
    card_id UUID REFERENCES cards(id) ON DELETE CASCADE,
    relevance_score FLOAT,
    PRIMARY KEY (insight_id, card_id)
);
```

**Worker job:** New `generate_insights` job type in `worker.py`, scheduled nightly after discovery runs complete.

### 3.5 Acceptance Criteria

- [ ] Nightly batch job runs after discovery pipeline and completes within 15 minutes for up to 500 active signals.
- [ ] Only clusters spanning 2+ pillars generate insights.
- [ ] Each insight links to 2-10 source signals with relevance scores.
- [ ] Near-duplicate insights (cosine similarity > 0.90) are merged rather than duplicated.
- [ ] Dashboard displays "AI Insights" section with the 5 most recent insights.
- [ ] Each insight shows contributing signals as clickable links.
- [ ] Users can dismiss an insight (status = dismissed), providing implicit feedback.
- [ ] Insights older than 90 days without user interaction are auto-archived.

---

## 4. Feature 2: Signal Velocity & Trajectory Tracking

### 4.1 What It Does

Tracks how each signal evolves over time and computes a trajectory indicator -- accelerating, stable, or declining. When a signal's trajectory crosses defined thresholds, the system recommends horizon reclassification (e.g., H3 to H2) and notifies relevant followers.

**Tracked metrics per signal per time period:**

- New source count (articles, reports mentioning this signal)
- Media mention velocity (rate of new mentions vs. prior period)
- Peer city adoption count (how many benchmark cities are acting on this)
- Sentiment shift (is coverage becoming more positive/negative)

### 4.2 Why It Matters

Static classification is the single biggest weakness of traditional horizon scanning. A signal classified as "Horizon 3 -- long-term" in January might accelerate to "Horizon 1 -- immediate" by June due to a federal policy change or technology breakthrough. Without velocity tracking, stale classifications create a false sense of timeline.

**Versus Gartner/McKinsey:** Consulting reports are snapshots. Between reports, signals can dramatically shift. Gartner's Hype Cycle updates annually; GrantScope2 updates continuously.

### 4.3 User Stories

- As a **strategic planner**, I want to see which signals are accelerating so that I can prioritize my attention on fast-moving trends.
- As a **department head**, I want to be notified when a signal I follow changes trajectory so that I can adjust planning timelines.
- As an **innovation analyst**, I want the system to recommend horizon reclassifications so that the signal database stays current without manual triage.
- As a **leadership briefer**, I want to show velocity data in presentations so that I can convey urgency with evidence, not opinion.

### 4.4 Technical Approach

**Architecture: Metrics computed during each discovery run, trajectory calculated weekly.**

1. **Metrics collection.** During each discovery run, count new sources per card. Store in a new `signal_metrics` table with a timestamp. Media mention velocity is derived from source count deltas. Peer city adoption is derived from Peer City Intelligence data (Feature 4).
2. **Trajectory calculation.** Weekly batch job computes trajectory for each active card:
   - Calculate 4-week rolling average of new source count.
   - Compare current period vs. prior period: >25% increase = accelerating, >25% decrease = declining, otherwise = stable.
   - Weight peer city adoption changes more heavily (a city launching a pilot is a stronger signal than three news articles).
3. **Horizon recommendation.** When a signal has been "accelerating" for 3+ consecutive periods and is currently H3 or H2, recommend an upgrade. When "declining" for 4+ periods, recommend a downgrade.
4. **Badge display.** Signal cards show a trajectory badge: "Accelerating" (up arrow), "Stable" (right arrow), "Declining" (down arrow) with color coding (green, gray, amber).
5. **Notification.** When trajectory changes, notify followers via in-app notification and include in digest emails (Feature 5).

**New database objects:**

```sql
CREATE TABLE signal_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id UUID REFERENCES cards(id) ON DELETE CASCADE,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    new_source_count INTEGER DEFAULT 0,
    mention_velocity FLOAT,
    peer_city_count INTEGER DEFAULT 0,
    sentiment_score FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(card_id, period_start)
);

-- Add to cards table
ALTER TABLE cards ADD COLUMN trajectory TEXT DEFAULT 'stable'
    CHECK (trajectory IN ('accelerating', 'stable', 'declining'));
ALTER TABLE cards ADD COLUMN trajectory_updated_at TIMESTAMPTZ;
ALTER TABLE cards ADD COLUMN horizon_recommendation TEXT;
```

### 4.5 Acceptance Criteria

- [ ] Signal metrics are recorded during every discovery run.
- [ ] Trajectory is recalculated weekly for all active signals.
- [ ] Trajectory badge is visible on signal cards in all views (Dashboard, Discover, Workstream).
- [ ] Trajectory change triggers in-app notification to signal followers.
- [ ] Horizon reclassification recommendations appear as actionable suggestions (accept/dismiss).
- [ ] Historical trajectory data is viewable as a sparkline or mini-chart on the signal detail page.
- [ ] Trajectory calculation completes within 5 minutes for up to 1,000 signals.

---

## 5. Feature 3: Natural Language Querying ("Ask GrantScope2")

### 5.1 What It Does

Allows any city employee to ask questions about trends, signals, and strategic topics in plain English and receive synthesized, sourced answers drawn from GrantScope2's signal database. This is not keyword search -- it is a RAG (Retrieval-Augmented Generation) pipeline that finds relevant signals via vector search and then uses an LLM to compose a coherent, cited answer.

**Example queries:**

- "What are other cities doing about AI in code enforcement?"
- "How might autonomous vehicles affect Austin's transit budget?"
- "What housing innovations are accelerating right now?"
- "Are there any signals related to climate resilience and infrastructure?"

### 5.2 Why It Matters

This feature transforms GrantScope2 from a system you browse into a system you converse with. It dramatically lowers the barrier to entry: a council member who would never navigate a signal dashboard can type a question and get an answer. It also captures demand signals -- questions asked reveal what leadership cares about, which can inform future discovery priorities.

**Versus Gartner/McKinsey:** Getting an answer from a consulting firm requires scheduling a call, waiting for research, and paying for analyst time. Ask GrantScope2 delivers answers in seconds, 24/7, drawing from the same continuously-updated signal database.

### 5.3 User Stories

- As a **council briefing preparer**, I want to ask a question in plain English and get a sourced answer so that I can quickly build briefing materials.
- As a **department head**, I want to ask "What should I know about [topic]?" and get a synthesis rather than a list of links so that I can make informed decisions quickly.
- As a **new user**, I want to explore GrantScope2 by asking questions so that I do not need training on the interface.
- As an **innovation analyst**, I want to see what questions other users are asking so that I can identify emerging areas of interest across departments.

### 5.4 Technical Approach

**Architecture: Real-time RAG pipeline with streaming response.**

1. **Query embedding.** Embed the user's natural language question using the same Azure OpenAI embedding model used for cards.
2. **Vector retrieval.** Search the `cards` table using pgvector cosine similarity. Retrieve the top 15 most relevant cards (similarity > 0.70).
3. **Context assembly.** For each retrieved card, include: name, summary, pillars, horizon, stage, trajectory, and top 3 sources with URLs.
4. **LLM synthesis.** Send the assembled context to GPT-4 with a system prompt instructing it to: (a) Answer the question using only the provided signals, (b) cite specific signals by name, (c) note any gaps where the signal database lacks coverage, (d) suggest follow-up questions.
5. **Streaming response.** Stream the LLM response to the frontend via SSE (Server-Sent Events) for a responsive UX.
6. **Query logging.** Store all queries, retrieved cards, and user satisfaction signals in a `queries` table for analytics and discovery tuning.

**New API endpoints:**

```
POST /api/v1/ask
  Body: { "question": "string", "pillar_filter": "string?" }
  Response: SSE stream of { "chunk": "string", "sources": Card[], "done": boolean }

GET /api/v1/ask/history
  Response: { "queries": Query[] }
```

**New database objects:**

```sql
CREATE TABLE queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),
    question TEXT NOT NULL,
    answer TEXT,
    source_card_ids UUID[],
    pillar_filter TEXT,
    satisfaction INTEGER CHECK (satisfaction BETWEEN 1 AND 5),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Frontend integration:**

- Header search bar triggers Ask GrantScope2 with a dedicated dropdown/modal for answers.
- Dedicated `/ask` page with full conversation history and suggested questions.
- Answer cards are clickable to navigate to the underlying signal.

### 5.5 Acceptance Criteria

- [ ] Users can submit natural language questions from the header search bar or the dedicated Ask page.
- [ ] Answers stream in real-time (first token within 2 seconds).
- [ ] Every factual claim in the answer cites a specific signal by name, linked to its detail page.
- [ ] The system clearly states when the signal database lacks coverage for a question.
- [ ] Users can rate answer quality (thumbs up/down or 1-5 scale).
- [ ] Query history is persisted and viewable by the user.
- [ ] The system suggests 3 follow-up questions after each answer.
- [ ] Pillar filtering is available to scope answers to a specific domain.

---

## 6. Feature 4: Peer City Intelligence

### 6.1 What It Does

Automatically monitors a curated set of 20 peer cities for relevant activity -- council agendas, press releases, pilot program announcements, RFPs, and policy changes. Signals discovered through peer city monitoring are tagged with the originating cities, enabling competitive benchmarking ("Austin is behind/ahead on [topic] relative to peer cities").

**Target peer cities (initial set):**
Denver, Seattle, Portland, Nashville, Charlotte, San Antonio, San Jose, Columbus, Fort Worth, Jacksonville, Indianapolis, San Francisco, Dallas, Phoenix, Minneapolis, Raleigh, Kansas City, Louisville, Oklahoma City, Tampa

### 6.2 Why It Matters

City leaders constantly ask: "What are other cities doing?" This question currently requires manual research or expensive consulting engagements. Automated peer city monitoring provides continuous competitive intelligence and helps Austin learn from others' successes and failures.

**Versus Gartner/McKinsey:** Peer benchmarking is a standard consulting deliverable, typically costing $50-100K per engagement and delivering a single point-in-time comparison. GrantScope2 delivers continuous benchmarking as a built-in capability.

### 6.3 User Stories

- As a **department head**, I want to know which peer cities are ahead of Austin on topics I care about so that I can learn from their experience.
- As a **council briefing preparer**, I want to cite peer city examples when recommending initiatives so that proposals have evidence of feasibility.
- As an **innovation analyst**, I want to track how quickly peer cities adopt emerging technologies so that I can calibrate Austin's horizon classifications.
- As a **city manager**, I want a competitive dashboard showing Austin's position relative to peers so that I can set strategic priorities.

### 6.4 Technical Approach

**Architecture: Extended source fetcher pipeline with city-specific feeds.**

1. **Source configuration.** For each peer city, maintain a configuration of:
   - City council agenda RSS feed URL (most cities publish these)
   - City press release / newsroom RSS feed URL
   - Serper/Tavily search queries: "[city name] + [pillar topic]" for each strategic pillar
2. **Fetcher implementation.** New `PeerCityFetcher` in `source_fetchers/` that extends the existing fetcher pattern. Runs as part of the nightly discovery pipeline. Each city's sources are fetched and processed through the standard triage/classification pipeline.
3. **City tagging.** Add a `peer_cities` array field to cards. During classification, if a source originated from a peer city feed, tag the card with that city. If multiple cities are acting on the same signal, the card accumulates city tags.
4. **Benchmarking engine.** For each active signal, compute a peer adoption score: number of peer cities with observed activity divided by total peer cities. Classify as: Leading (Austin acting, <3 peers), Keeping Pace (Austin acting, 3+ peers), Falling Behind (Austin not acting, 3+ peers), or Early Signal (no cities acting).
5. **Competitive dashboard.** New dashboard section or dedicated page showing peer adoption heatmap (cities vs. pillars) and Austin's relative position.

**New database objects:**

```sql
ALTER TABLE cards ADD COLUMN peer_cities TEXT[] DEFAULT '{}';

CREATE TABLE peer_city_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    city_name TEXT NOT NULL UNIQUE,
    state TEXT NOT NULL,
    population INTEGER,
    council_agenda_feed TEXT,
    press_release_feed TEXT,
    search_queries JSONB DEFAULT '[]',
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE peer_city_activity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    city_name TEXT NOT NULL,
    card_id UUID REFERENCES cards(id) ON DELETE CASCADE,
    activity_type TEXT CHECK (activity_type IN ('agenda_item', 'press_release', 'pilot', 'rfp', 'policy', 'other')),
    source_url TEXT,
    observed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 6.5 Acceptance Criteria

- [ ] At least 15 of 20 target peer cities have configured RSS feeds or search queries.
- [ ] Peer city sources are processed through the standard discovery pipeline nightly.
- [ ] Cards originating from peer city sources display a "Observed in: City1, City2" tag.
- [ ] Peer adoption score is computed and displayed for each active signal.
- [ ] A competitive benchmarking view shows Austin's position relative to peers, filterable by pillar.
- [ ] Peer city activity feed shows recent activity across all monitored cities.
- [ ] Users can suggest additional peer cities for monitoring.
- [ ] Peer city data feeds into Signal Velocity tracking (Feature 2) as a weighted input.

---

## 7. Feature 5: Proactive Email Digests

### 7.1 What It Does

Sends personalized, periodic email digests to users based on their workstream subscriptions and followed signals. Digests contain new signals, velocity changes, AI insights, and peer city activity relevant to each user's interests. Users configure their preferred email address (independent of login credentials), frequency, and content preferences.

### 7.2 Why It Matters

Most city employees will not log into GrantScope2 daily. Proactive delivery of relevant intelligence via email meets users where they already work. This is the difference between a tool that waits to be consulted and a system that actively informs decision-making.

**Versus Gartner/McKinsey:** Consulting firms send generic newsletters to all subscribers. GrantScope2 digests are personalized to each user's specific workstreams and followed signals -- every recipient gets a different email.

### 7.3 User Stories

- As a **busy department head**, I want a weekly digest of new signals in my areas so that I stay informed without logging in.
- As a **workstream owner**, I want to know when signals in my workstream change trajectory so that I can adjust plans proactively.
- As a **user with a non-organizational email**, I want to set a separate notification email so that digests reach my preferred inbox (since test/SSO accounts may not have real email addresses).
- As an **innovation analyst**, I want daily digests so that I can triage new signals each morning.

### 7.4 Technical Approach

**Architecture: Scheduled worker job with templated email delivery.**

1. **User preferences.** Extend the `users.preferences` JSONB field to include:
   - `digest_frequency`: "daily", "weekly", "none"
   - `digest_email`: separate email address for notifications (nullable, falls back to auth email)
   - `digest_content`: array of content types to include: ["new_signals", "velocity_changes", "insights", "peer_cities"]
2. **Digest generation.** New worker job `generate_digests` runs at configured times (daily at 7 AM CT, weekly on Monday at 7 AM CT). For each eligible user:
   - Query new signals matching user's followed pillars/workstreams since last digest.
   - Query velocity changes for followed signals.
   - Query new AI insights involving user's pillars.
   - Query peer city activity for user's topics.
3. **Template rendering.** Render digest content using an HTML email template. Include: summary stats (X new signals, Y velocity changes), top items with brief summaries, and deep links back to GrantScope2 for full details.
4. **Email delivery.** Use a transactional email service (SendGrid, Resend, or Supabase's built-in email). Queue emails through the worker to avoid rate limits.
5. **Settings UI.** New section on the Settings/Profile page for email preferences: frequency selector, custom email field, content type toggles.

**New API endpoints:**

```
GET  /api/v1/me/digest-preferences
PUT  /api/v1/me/digest-preferences
POST /api/v1/me/digest/preview    # Preview what your next digest would contain
```

### 7.5 Acceptance Criteria

- [ ] Users can set digest frequency (daily, weekly, none) on the Settings page.
- [ ] Users can set a notification email address separate from their login email.
- [ ] Users can select which content types to include in their digest.
- [ ] Daily digests are delivered by 7:30 AM CT; weekly digests by 7:30 AM CT on Mondays.
- [ ] Each digest is personalized to the user's workstreams and followed signals.
- [ ] Digests include deep links that navigate directly to the relevant signal or insight.
- [ ] Users can preview their next digest before it sends.
- [ ] Empty digests (no new content) are suppressed -- users are not emailed when there is nothing to report.
- [ ] Unsubscribe link in every email that sets frequency to "none."

---

## 8. Feature 6: Grant & Funding Matcher

**Priority: 2 -- Next Phase**

### 8.1 What It Does

Matches active signals and workstreams to available federal, state, and foundation grant opportunities. When a signal aligns with an open grant program, the system surfaces the match with grant details, deadlines, eligibility criteria, and estimated fit score.

**Example:** "The 'Smart Traffic Signal Optimization' signal matches the USDOT SMART Grant Program. Application deadline: March 15, 2027. Estimated fit: High (smart city infrastructure, population > 500K, existing ITS investment)."

### 8.2 Why It Matters

Cities leave billions in available grant funding on the table because they lack the capacity to systematically match their strategic priorities to funding opportunities. Grant matching transforms GrantScope2 from an intelligence tool into an action enabler -- not just "here is what is happening" but "here is how to fund a response."

**Versus Gartner/McKinsey:** Traditional consulting identifies trends but does not connect them to funding mechanisms. Grant matching is typically a separate, expensive service.

### 8.3 User Stories

- As a **grants coordinator**, I want to see which signals match open grants so that I can proactively pursue funding for emerging initiatives.
- As a **department head**, I want to know if a trend I am tracking has available funding so that I can move from research to action.
- As a **budget analyst**, I want a consolidated view of all grant opportunities matched to our strategic signals so that I can plan the grants pipeline.
- As a **city manager**, I want to see total potential funding available across all matched grants so that I can assess the ROI of acting on specific signals.

### 8.4 Technical Approach

1. **Grant data ingestion.** Build scrapers/API integrations for: grants.gov (federal), NSF, USDOT, EPA, HUD, and Texas state grant portals. Store in a `grants` table with fields for title, agency, deadline, amount, eligibility criteria, and a text description.
2. **Embedding and matching.** Embed grant descriptions using the same embedding model as cards. Match grants to cards using cosine similarity (threshold 0.75). Apply eligibility filters (population, geography, entity type).
3. **Fit scoring.** LLM-assisted scoring: for each grant-signal match above the similarity threshold, ask GPT-4 to assess fit on a 1-5 scale considering Austin's specific characteristics.
4. **Surfacing.** Grant matches appear on signal detail pages and in a dedicated "Funding Opportunities" view. Include deadline countdown, agency, amount range, and fit score.

### 8.5 Acceptance Criteria

- [ ] System ingests grants from at least 3 federal sources (grants.gov, USDOT, one additional).
- [ ] Grant-signal matching runs weekly and produces matches with fit scores.
- [ ] Signal detail pages show matched grants with deadlines and fit scores.
- [ ] Dedicated funding opportunities page shows all active matches, sortable by deadline, amount, and fit.
- [ ] Expired grants (past deadline) are automatically archived.
- [ ] Users can dismiss irrelevant grant matches, providing feedback to improve future matching.

---

## 9. Feature 7: Austin-Specific Impact Analysis

**Priority: 2 -- Next Phase**

### 9.1 What It Does

For each signal, auto-generates a contextual analysis specific to Austin's unique characteristics: population growth trajectory, climate profile, budget constraints, existing infrastructure, current strategic plan alignment, and demographic composition. This transforms generic signal descriptions into actionable, localized intelligence.

**Example:** "Flood-resistant infrastructure innovations: Austin experienced 14 significant flood events in the past decade. The Watershed Protection Department's current capital plan allocates $80M through 2028. This signal is directly relevant to the Williamson Creek and Onion Creek flood mitigation projects. Estimated additional investment needed: $15-25M."

### 9.2 Why It Matters

Generic trend reports are the primary complaint about consulting engagements. "Smart city trends" is not useful; "What smart city trends mean for Austin given our 3% annual population growth, 300+ days of sun, and $5.2B annual budget" is useful. Localization is the difference between information and intelligence.

**Versus Gartner/McKinsey:** Consulting firms produce templated reports and add a thin customization layer. GrantScope2 can weave Austin-specific data into every analysis because the contextual dataset is persistent and continuously updated.

### 9.3 User Stories

- As a **council briefing preparer**, I want to see how a national trend specifically affects Austin so that my briefings are locally relevant.
- As a **budget analyst**, I want to understand the financial implications of a signal for Austin's specific budget structure.
- As a **department head**, I want to know how my department's existing programs relate to a new signal so that I can identify overlap or gaps.
- As a **strategic planner**, I want signals contextualized against Austin's strategic plan so that I can assess alignment.

### 9.4 Technical Approach

1. **Austin context database.** Curate a structured dataset of Austin-specific facts: population data, budget figures, department structures, capital improvement plan, climate data, major ongoing projects, strategic plan goals. Store as a set of context documents in the database, updated quarterly.
2. **Context-aware analysis.** When a user requests impact analysis for a signal (or automatically for high-scoring signals), retrieve relevant Austin context documents and the signal's full details. Send to GPT-4 with a prompt asking for localized analysis covering: relevance to current city programs, budget implications, infrastructure readiness, demographic considerations, and strategic plan alignment.
3. **Caching.** Store generated analyses in a `signal_analyses` table linked to the card. Regenerate when the signal's summary changes significantly or when Austin context data is updated.

### 9.5 Acceptance Criteria

- [ ] Austin context database contains at least: population stats, budget summary, strategic plan goals, climate profile, and top 10 capital projects.
- [ ] Impact analysis can be triggered manually from any signal detail page.
- [ ] Auto-generated analyses reference specific Austin data points (not generic city language).
- [ ] Analyses are cached and reused until underlying data changes.
- [ ] High-scoring signals (impact > 80) automatically receive analysis without user request.

---

## 10. Feature 8: Signal Decay Detection

**Priority: 2 -- Next Phase**

### 10.1 What It Does

Identifies signals that are losing momentum -- the inverse of velocity tracking. While Feature 2 detects acceleration, Signal Decay Detection specifically focuses on identifying hype cycles that have peaked, initiatives that have stalled, and technologies that are failing to achieve adoption. This prevents the organization from investing in signals that appear promising but are actually fading.

**Example:** "Blockchain for land records: No new pilot announcements in 8 months. Funding mentions down 60% year-over-year. 2 of 3 known pilots discontinued. Recommend: Downgrade from H2 to H3, archive if no activity within 90 days."

### 10.2 Why It Matters

Knowing what to stop watching is as valuable as knowing what to start watching. Organizations waste significant resources pursuing trends that have peaked. Decay detection prevents "zombie signals" -- topics that persist in the system because no one actively removes them, consuming attention and creating noise.

**Versus Gartner/McKinsey:** The Gartner Hype Cycle tracks this at a macro level, updated annually. GrantScope2 tracks decay at the individual signal level, updated continuously, with Austin-specific context about whether the technology is actually viable for municipal use cases.

### 10.3 User Stories

- As a **workstream owner**, I want to know when a signal in my workstream is decaying so that I can reallocate attention to higher-momentum topics.
- As a **budget analyst**, I want early warning when a technology trend is losing steam so that I do not recommend investment in declining areas.
- As an **innovation analyst**, I want the system to auto-suggest archiving stale signals so that the active signal database stays clean and credible.
- As a **leadership briefer**, I want to communicate when previously hyped topics are fading so that leadership expectations are calibrated.

### 10.4 Technical Approach

1. **Decay scoring.** Extend the signal metrics infrastructure (Feature 2) with decay-specific indicators:
   - Months since last new source
   - Source count trend (rolling 3-month decline rate)
   - Peer city pilot discontinuation events
   - Sentiment shift toward negative/skeptical
   - Funding mention decline rate
2. **Decay classification.** Compute a composite decay score (0-100). Classify as: Healthy (0-25), Cooling (26-50), Decaying (51-75), Stale (76-100).
3. **Auto-recommendations.** Signals classified as "Decaying" for 2+ consecutive periods trigger an auto-recommendation to downgrade horizon. Signals classified as "Stale" for 3+ periods trigger an auto-recommendation to archive.
4. **Decay dashboard.** New section on the analytics page showing decaying signals, sorted by decay score. Include a "Zombie Signal" report of signals with no new sources for 6+ months that are still classified as H1 or H2.

### 10.5 Acceptance Criteria

- [ ] Decay score is computed for all active signals during the weekly metrics run.
- [ ] Signals are classified into decay tiers (Healthy, Cooling, Decaying, Stale).
- [ ] "Decaying" signals display a visual indicator on their cards.
- [ ] Auto-archive recommendations are generated for "Stale" signals.
- [ ] Decay dashboard shows all signals in Cooling/Decaying/Stale tiers.
- [ ] "Zombie Signal" report identifies H1/H2 signals with no activity for 6+ months.
- [ ] Users can override decay recommendations (mark as "still relevant" with justification).

---

## 11. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-4)

| Week | Feature                    | Deliverable                                                                                  |
| ---- | -------------------------- | -------------------------------------------------------------------------------------------- |
| 1-2  | Signal Velocity (F2)       | `signal_metrics` table, metrics collection in discovery pipeline, trajectory calculation job |
| 2-3  | Signal Velocity (F2)       | Trajectory badge on cards, notification on trajectory change                                 |
| 3-4  | Cross-Signal Patterns (F1) | `insights` table, nightly clustering job, LLM synthesis pipeline                             |

**Rationale:** Velocity tracking provides the data infrastructure that multiple later features depend on. Cross-signal patterns build on embeddings already in the system.

### Phase 2: User-Facing Intelligence (Weeks 5-8)

| Week | Feature              | Deliverable                                                                 |
| ---- | -------------------- | --------------------------------------------------------------------------- |
| 5-6  | Ask GrantScope2 (F3) | RAG pipeline, `/ask` endpoint with SSE streaming, header search integration |
| 6-7  | Ask GrantScope2 (F3) | Query history, satisfaction tracking, suggested follow-ups                  |
| 7-8  | Email Digests (F5)   | Preferences UI, digest generation job, email template, delivery pipeline    |

**Rationale:** Ask GrantScope2 is high visibility and immediately demonstrates value to leadership. Email digests drive recurring engagement.

### Phase 3: Competitive Intelligence (Weeks 9-12)

| Week  | Feature                     | Deliverable                                                                                 |
| ----- | --------------------------- | ------------------------------------------------------------------------------------------- |
| 9-10  | Peer City Intelligence (F4) | `PeerCityFetcher`, city configuration for 15+ cities, source integration                    |
| 10-11 | Peer City Intelligence (F4) | Peer adoption scoring, city tags on cards, competitive benchmarking view                    |
| 11-12 | Integration                 | Connect peer city data to velocity tracking, include in digests, surface in Ask GrantScope2 |

**Rationale:** Peer city intelligence has the most complex data pipeline and benefits from Velocity and Ask GrantScope2 already being in place.

### Phase 4: Next-Generation (Weeks 13-20)

| Week  | Feature                     | Deliverable                                                        |
| ----- | --------------------------- | ------------------------------------------------------------------ |
| 13-15 | Grant Matcher (F6)          | Grant data ingestion, embedding, matching pipeline, UI             |
| 16-17 | Austin Impact Analysis (F7) | Austin context database, analysis generation, caching              |
| 18-20 | Signal Decay (F8)           | Decay scoring, classification, auto-recommendations, zombie report |

---

## 12. Success Metrics

### Quantitative

| Metric                                      | Target                              | Measurement                                                      |
| ------------------------------------------- | ----------------------------------- | ---------------------------------------------------------------- |
| Cross-signal insights generated per week    | 5-15                                | Count of new `insights` records                                  |
| Insight dismissal rate                      | <40%                                | Dismissed / total insights shown                                 |
| Ask GrantScope2 queries per week            | 50+ (after 3 months)                | Count of `queries` records                                       |
| Ask GrantScope2 satisfaction score          | >3.5/5.0                            | Average rating on answers                                        |
| Digest open rate                            | >50%                                | Email analytics                                                  |
| Peer cities monitored                       | 15+                                 | Active `peer_city_config` records                                |
| Velocity-driven reclassifications per month | 5-20                                | Cards with horizon changes attributed to velocity recommendation |
| Signal decay archival rate                  | 10-20% of stale signals per quarter | Archived cards triggered by decay detection                      |

### Qualitative

- Staff cite GrantScope2 insights in council briefings and strategic planning documents.
- Department heads use peer city data to justify or de-prioritize initiatives.
- "Ask GrantScope2" becomes the default first step when someone has a strategic question.
- Leadership references velocity and trajectory data in budget discussions.

### Cost Displacement

- Target: GrantScope2 replaces or reduces the need for at least one external consulting engagement per year ($100-250K savings).
- Measurement: Track instances where GrantScope2-generated intelligence would have previously required a consulting RFP.

---

## 13. Risks & Mitigations

| Risk                                                           | Likelihood | Impact | Mitigation                                                                                                                                                                                        |
| -------------------------------------------------------------- | ---------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Cross-signal insights are low quality or obvious**           | Medium     | High   | Human review period for first 30 days; tune clustering thresholds and LLM prompts based on feedback; implement dismissal tracking to identify weak patterns                                       |
| **Peer city RSS feeds are unreliable or inconsistent**         | High       | Medium | Fall back to Serper/Tavily search for cities without stable feeds; build monitoring for feed health; start with 10 cities, expand as feed reliability is confirmed                                |
| **Ask GrantScope2 hallucinates or cites non-existent signals** | Medium     | High   | RAG pipeline strictly limits LLM context to retrieved signals; answer includes only linked, verifiable signal names; add explicit "I don't have enough data" responses for low-similarity queries |
| **Email delivery issues (spam filters, bounce rates)**         | Medium     | Medium | Use established transactional email service with proper SPF/DKIM; allow users to whitelist; provide in-app digest fallback                                                                        |
| **Grant data staleness (expired grants shown as active)**      | Medium     | Medium | Weekly grant data refresh; deadline-based auto-expiry; last-refreshed timestamp visible to users                                                                                                  |
| **LLM API costs scale with usage**                             | Medium     | Low    | Cache Ask GrantScope2 answers for similar questions (embedding similarity > 0.95); batch nightly jobs efficiently; set per-user daily query limits                                                |
| **Velocity tracking produces noisy trajectory changes**        | Medium     | Medium | Require 3+ consecutive periods before changing trajectory label; use smoothed rolling averages rather than raw deltas; allow user override                                                        |

---

## Appendix A: Glossary

- **Signal:** An atomic unit of strategic intelligence in GrantScope2, represented as a "card" in the system. Synonymous with "card" in the codebase.
- **Pillar:** One of six strategic domains: Community Health (CH), Mobility (MC), Housing (HS), Economic (EC), Environmental (ES), Cultural (CE).
- **Horizon:** Time classification for a signal. H1 = immediate (0-12 months), H2 = emerging (1-3 years), H3 = long-term (3+ years).
- **Trajectory:** The direction and rate of change for a signal's momentum: accelerating, stable, or declining.
- **Insight:** A cross-domain pattern detected by analyzing signals across multiple pillars.
- **Decay:** The measurable decline in momentum, coverage, or adoption for a signal over time.
- **RAG:** Retrieval-Augmented Generation, a technique that grounds LLM responses in retrieved data to reduce hallucination.
- **Peer adoption score:** The fraction of monitored peer cities with observed activity on a given signal.

## Appendix B: Dependencies on Existing Infrastructure

| Existing Component                              | Features That Depend On It                                                   |
| ----------------------------------------------- | ---------------------------------------------------------------------------- |
| pgvector embeddings on `cards` table            | F1 (clustering), F3 (vector retrieval), F6 (grant matching)                  |
| Discovery pipeline (`discovery_service.py`)     | F2 (metrics collection), F4 (peer city ingestion)                            |
| Worker job infrastructure (`worker.py`)         | F1 (nightly insights), F2 (weekly trajectory), F5 (digest generation)        |
| Azure OpenAI integration (`openai_provider.py`) | F1 (LLM synthesis), F3 (RAG answers), F6 (fit scoring), F7 (impact analysis) |
| User preferences JSONB field                    | F5 (digest settings)                                                         |
| Supabase Auth                                   | F3 (query attribution), F5 (email routing)                                   |
