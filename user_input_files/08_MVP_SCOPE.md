# GrantScope2: MVP Scope

## Overview

This document defines what's included in the Minimum Viable Product (MVP) versus what's deferred to future versions.

**MVP Goal:** A working system that 5-10 pilot users can use to discover, follow, and analyze emerging trends relevant to their work.

**Timeline Target:** 4-6 weeks to functional MVP

---

## What's IN the MVP

### Core Features

| Feature               | Description                              | Priority |
| --------------------- | ---------------------------------------- | -------- |
| **Card Discovery**    | Browse/search all cards with filters     | P0       |
| **Card Detail**       | View full card with metadata and sources | P0       |
| **Follow Cards**      | Add cards to personal tracking           | P0       |
| **Basic Workstreams** | Create workstreams with pillar filters   | P1       |
| **Nightly Scan**      | Automated daily source ingestion         | P0       |
| **User Auth**         | Supabase email/password login            | P0       |

### Pages

| Page             | Status | Notes                                |
| ---------------- | ------ | ------------------------------------ |
| Login            | MVP    | Supabase UI components               |
| Dashboard        | MVP    | Simplified - followed cards + recent |
| Discovery Feed   | MVP    | Full filtering                       |
| Card Detail      | MVP    | All tabs except Analysis             |
| Workstreams List | MVP    | Basic CRUD                           |
| Settings         | MVP    | Profile + notification prefs only    |

### Card Features

| Feature               | MVP | Notes                   |
| --------------------- | --- | ----------------------- |
| View card summary     | ✓   |                         |
| View classification   | ✓   | Pillars, horizon, stage |
| View scoring          | ✓   | 7 criteria display      |
| View sources          | ✓   | List with links         |
| View timeline         | ✓   | Basic event list        |
| Follow/unfollow       | ✓   |                         |
| Add notes             | ✓   | Text only               |
| Implications analysis | ✗   | v1.1                    |
| Share card            | ✗   | v1.1                    |

### AI Pipeline

| Feature                     | MVP | Notes                        |
| --------------------------- | --- | ---------------------------- |
| Nightly fetch (3-4 sources) | ✓   | NewsAPI + 2-3 RSS feeds      |
| Triage filtering            | ✓   |                              |
| Full article processing     | ✓   |                              |
| Card matching               | ✓   | Vector similarity only       |
| New card creation           | ✓   |                              |
| Timeline events             | ✓   | Basic: created, source_added |
| Stage change detection      | ✗   | v1.1                         |
| Research tasks              | ✗   | v1.2                         |

### Data Model

| Table                 | MVP | Notes        |
| --------------------- | --- | ------------ |
| users                 | ✓   |              |
| cards                 | ✓   | All fields   |
| sources               | ✓   |              |
| card_timeline         | ✓   | Basic events |
| workstreams           | ✓   |              |
| card_follows          | ✓   |              |
| card_notes            | ✓   |              |
| pillars (ref)         | ✓   |              |
| goals (ref)           | ✓   |              |
| implications_analyses | ✗   | v1.1         |
| implications          | ✗   | v1.1         |

---

## What's OUT of MVP (Deferred)

### v1.1 (4-6 weeks after MVP)

| Feature                    | Description                                 |
| -------------------------- | ------------------------------------------- |
| **Implications Analysis**  | Full implications wheel with scoring        |
| **Stage Change Detection** | AI detects when cards should advance stages |
| **Velocity Scoring**       | Calculated trending metric                  |
| **Card Sharing**           | Copy link, share to colleague               |
| **Digest Emails**          | Daily/weekly email summaries                |
| **Advanced Workstreams**   | Keyword matching, stage filters             |
| **Real-time Updates**      | Supabase subscriptions for live feed        |

### v1.2 (8-12 weeks after MVP)

| Feature                 | Description                              |
| ----------------------- | ---------------------------------------- |
| **Research Tasks**      | On-demand deep research                  |
| **Top 25 Relevance**    | Auto-flag cards matching CMO priorities  |
| **Graph Relationships** | Related cards, concept clustering        |
| **Export/Reports**      | PDF export of cards, briefing generation |
| **Team Workstreams**    | Shared workstreams across users          |
| **Admin Dashboard**     | Scan status, user stats, system health   |

### v2.0 (Future)

| Feature                 | Description                              |
| ----------------------- | ---------------------------------------- |
| **Azure AD SSO**        | City employee single sign-on             |
| **Neo4j Integration**   | Full graph database for relationships    |
| **Scenario Generation** | AI-generated future scenarios from cards |
| **API Access**          | Public API for integrations              |
| **Mobile App**          | Native iOS/Android                       |
| **Multi-tenant**        | Support for other cities                 |

---

## MVP Technical Scope

### Backend

```
Endpoints needed:
├── POST   /auth/login (handled by Supabase)
├── GET    /me
├── PATCH  /me
├── GET    /cards
├── GET    /cards/:id
├── GET    /cards/:id/sources
├── GET    /cards/:id/timeline
├── POST   /cards/search
├── POST   /cards/:id/follow
├── DELETE /cards/:id/follow
├── GET    /cards/:id/notes
├── POST   /cards/:id/notes
├── GET    /me/following
├── GET    /me/workstreams
├── POST   /me/workstreams
├── PATCH  /me/workstreams/:id
├── DELETE /me/workstreams/:id
├── GET    /me/workstreams/:id/feed
├── GET    /taxonomy
└── POST   /admin/scan (manual trigger)
```

### Frontend

```
Pages needed:
├── /login
├── / (Dashboard)
├── /discover
├── /cards/:slug
├── /workstreams
└── /settings

Components needed:
├── Layout (Header, Sidebar)
├── CardPreview
├── CardDetail
├── CardTimeline
├── SourceList
├── FilterSidebar
├── WorkstreamForm
├── NoteForm
└── Common (Button, Input, Badge, etc.)
```

### Pipeline

```
Fetchers needed:
├── NewsAPIFetcher
├── RSSFetcher (generic)
└── (configure 2-3 RSS feeds)

Processors needed:
├── triage_article()
├── process_article()
├── match_to_card()
├── create_card()
└── add_source_to_card()
```

---

## MVP Data Seeds

### Reference Data

Pre-populate on deploy:

- 6 pillars
- 23 goals
- 6 anchors
- 8 stages
- 24 Top 25 priorities (for future use)

### Test Data (Development)

Create manually or via script:

- 3 test users
- 10-15 seed cards across pillars
- 30-50 sources linked to cards
- Sample timeline events

---

## MVP Success Criteria

| Metric                         | Target            |
| ------------------------------ | ----------------- |
| Users can log in               | ✓ Works           |
| Cards appear from nightly scan | ≥5 new cards/week |
| Users can browse/filter cards  | <2s load time     |
| Users can follow cards         | Works correctly   |
| Users can create workstreams   | Works correctly   |
| Pipeline runs without errors   | 95% success rate  |
| Pilot users provide feedback   | 5+ users engaged  |

---

## MVP Timeline

### Week 1: Foundation

- [ ] Set up Supabase project
- [ ] Create database schema
- [ ] Set up FastAPI project structure
- [ ] Basic auth flow working
- [ ] Set up React project with routing

### Week 2: Core Backend

- [ ] Card CRUD endpoints
- [ ] Search endpoint (vector)
- [ ] Follow/workstream endpoints
- [ ] Notes endpoints
- [ ] Taxonomy endpoint

### Week 3: Core Frontend

- [ ] Layout components
- [ ] Discovery page with filters
- [ ] Card detail page
- [ ] Dashboard page
- [ ] Basic styling

### Week 4: Pipeline

- [ ] NewsAPI fetcher
- [ ] RSS fetcher
- [ ] Triage processor
- [ ] Full processor
- [ ] Card matching logic
- [ ] Scheduler setup

### Week 5: Integration & Polish

- [ ] End-to-end testing
- [ ] Deploy to HF Spaces
- [ ] Frontend deployment
- [ ] Bug fixes
- [ ] Pilot user onboarding

### Week 6: Buffer

- [ ] Additional bug fixes
- [ ] User feedback incorporation
- [ ] Documentation

---

## MVP Risks & Mitigations

| Risk                          | Impact             | Mitigation                 |
| ----------------------------- | ------------------ | -------------------------- |
| NewsAPI rate limits           | Can't fetch enough | Add more RSS sources       |
| AI costs higher than expected | Budget overrun     | Add triage aggressiveness  |
| Vector search slow            | Poor UX            | Add caching, limit results |
| Card matching inaccurate      | Duplicate cards    | Lower similarity threshold |
| Users don't engage            | No feedback        | Weekly check-ins, demos    |

---

## Post-MVP Priorities

Based on user feedback, likely priorities:

1. **Implications Analysis** - Differentiator feature
2. **Email Digests** - Passive engagement
3. **Stage Change Detection** - Core value prop
4. **Research Tasks** - Power user feature

---

_Document Version: 1.0_
_Last Updated: December 2024_
