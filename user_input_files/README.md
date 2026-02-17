# GrantScope2 Design Documents

## Overview

GrantScope2 is a strategic horizon scanning system for the City of Austin. These documents define the architecture, data model, and implementation specifications.

**Target Stack:**

- Frontend: React + TypeScript + Vite + TailwindCSS
- Backend: FastAPI (Python 3.11+)
- Database: Supabase (PostgreSQL + pgvector)
- AI: Azure OpenAI / OpenAI
- Hosting: HuggingFace Spaces + Vercel/Netlify

---

## Document Index

| #   | Document                                        | Description                                               | Read When               |
| --- | ----------------------------------------------- | --------------------------------------------------------- | ----------------------- |
| 01  | [PROJECT_OVERVIEW.md](./01_PROJECT_OVERVIEW.md) | What GrantScope2 is, the problem it solves, core concepts | Start here              |
| 02  | [ARCHITECTURE.md](./02_ARCHITECTURE.md)         | System components, data flows, hosting                    | Planning infrastructure |
| 03  | [TECH_STACK.md](./03_TECH_STACK.md)             | Dependencies, project structure, Docker config            | Setting up projects     |
| 04  | [DATA_MODEL.md](./04_DATA_MODEL.md)             | Database schema, tables, indexes, RLS                     | Building database       |
| 05  | [API_SPEC.md](./05_API_SPEC.md)                 | REST API endpoints, request/response formats              | Building backend        |
| 06  | [FRONTEND_SPEC.md](./06_FRONTEND_SPEC.md)       | Pages, components, wireframes, state management           | Building frontend       |
| 07  | [AI_PIPELINE.md](./07_AI_PIPELINE.md)           | Nightly scan, processing, prompts, costs                  | Building AI features    |
| 08  | [MVP_SCOPE.md](./08_MVP_SCOPE.md)               | What's in v1 vs deferred, timeline, success criteria      | Prioritizing work       |
| 09  | [TAXONOMY.md](./09_TAXONOMY.md)                 | Complete reference for pillars, goals, stages, etc.       | Quick reference         |

---

## Quick Start for Development

### 1. Set Up Supabase

1. Create new Supabase project
2. Run schema from `04_DATA_MODEL.md`
3. Enable pgvector extension
4. Set up auth (email/password)
5. Note URL and keys

### 2. Set Up Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Fill in Supabase and OpenAI keys

# Run locally
uvicorn app.main:app --reload
```

### 3. Set Up Frontend

```bash
cd frontend
npm install

# Create .env file
cp .env.example .env
# Fill in Supabase and API URLs

# Run locally
npm run dev
```

### 4. Test Pipeline

```bash
# Trigger manual scan
curl -X POST http://localhost:8000/api/v1/admin/scan
```

---

## Development Order (Suggested)

### Phase 1: Foundation (Week 1)

1. Set up Supabase with schema
2. Scaffold FastAPI project
3. Implement auth endpoints
4. Scaffold React project
5. Implement login flow

### Phase 2: Core Data (Week 2)

1. Card CRUD endpoints
2. Source endpoints
3. Timeline endpoints
4. Search endpoint (vector)

### Phase 3: User Features (Week 3)

1. Follow/unfollow endpoints
2. Workstream endpoints
3. Notes endpoints
4. User profile endpoints

### Phase 4: Frontend (Week 3-4)

1. Layout components
2. Discovery page
3. Card detail page
4. Dashboard
5. Workstreams page

### Phase 5: Pipeline (Week 4-5)

1. Fetchers (NewsAPI, RSS)
2. Triage processor
3. Full processor
4. Card matcher
5. Scheduler

### Phase 6: Deploy & Test (Week 5-6)

1. Deploy backend to HF Spaces
2. Deploy frontend to Vercel
3. End-to-end testing
4. Bug fixes
5. Pilot user onboarding

---

## Key Decisions Made

| Decision           | Choice              | Rationale                               |
| ------------------ | ------------------- | --------------------------------------- |
| Backend language   | Python              | Best AI/ML ecosystem                    |
| Frontend framework | React (not Next.js) | Simpler, SPA sufficient                 |
| Database           | Supabase            | Managed, pgvector, auth included        |
| Vector DB          | pgvector            | Built into Supabase, no extra service   |
| Graph DB           | Deferred            | Use relational for MVP, add Neo4j later |
| Hosting            | HF Spaces           | Free tier, Docker support               |
| Auth               | Supabase Auth       | Integrated, JWT-based                   |

---

## Environment Variables Needed

### Backend

```
SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_SERVICE_KEY=
OPENAI_API_KEY=
NEWSAPI_KEY=
```

### Frontend

```
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
VITE_API_URL=
```

---

## Questions for Implementation

Before starting, confirm:

1. **OpenAI vs Azure OpenAI**: Using OpenAI direct for pilot, or need Azure from start?
2. **User provisioning**: Manual creation, or self-signup with @austintexas.gov domain?
3. **Initial sources**: Which RSS feeds specifically to include?
4. **Pilot users**: Who are the 5-10 initial users?
5. **Success metrics**: What defines "working" for pilot?

---

## Contact

Project Lead: Chris (AI Technology Lead, Austin Public Health)
