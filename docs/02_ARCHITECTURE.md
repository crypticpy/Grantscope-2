# GrantScope2: System Architecture

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FORESIGHT                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   React UI   │◄──►│  FastAPI     │◄──►│  Supabase    │      │
│  │  (Frontend)  │    │  (Backend)   │    │  (Database)  │      │
│  └──────────────┘    └──────┬───────┘    └──────────────┘      │
│                             │                                   │
│                             ▼                                   │
│                      ┌──────────────┐                          │
│                      │ Azure OpenAI │                          │
│                      │   (LLM)      │                          │
│                      └──────────────┘                          │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              NIGHTLY PIPELINE (Scheduled)                 │  │
│  │  Sources ──► Fetch ──► Triage ──► Analyze ──► Store      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Frontend (React + TypeScript)

- Single-page application
- Hosted as static files (Vercel, Netlify, or HF Spaces)
- Communicates with backend via REST API
- Real-time updates via Supabase subscriptions

### 2. Backend (FastAPI + Python)

- REST API for all operations
- Authentication via Supabase JWT
- Business logic and orchestration
- AI/LLM integration layer
- Hosted on HuggingFace Spaces (Docker)

### 3. Database (Supabase)

- PostgreSQL for relational data
- pgvector extension for embeddings
- Row-level security for multi-user access
- Real-time subscriptions for live updates
- Built-in authentication

### 4. AI Layer (Azure OpenAI)

- GPT-4o for analysis and synthesis
- text-embedding-ada-002 for vector embeddings
- Configurable to swap models

### 5. Nightly Pipeline

- Scheduled job (cron or APScheduler)
- Fetches from configured sources
- Processes and creates/updates cards
- Runs independently of user requests

## Data Flow: Nightly Scan

```
1. FETCH
   ├── NewsAPI (general news)
   ├── GovTech feeds (municipal news)
   ├── arXiv (research papers)
   └── Custom RSS feeds

2. TRIAGE (per article)
   ├── Is this relevant to Austin/municipal government?
   ├── Which CSP pillars does it touch?
   └── Quick relevance score (skip if < threshold)

3. ANALYZE (relevant articles)
   ├── Extract entities and concepts
   ├── Match to existing cards OR flag as new
   ├── Generate summary
   ├── Score on 7 criteria
   └── Assign horizon and stage

4. STORE
   ├── Create/update card records
   ├── Store source with embedding
   ├── Update card embeddings
   └── Log to timeline

5. NOTIFY
   ├── Queue digest emails
   └── Flag high-priority items
```

## Data Flow: User Research Task

```
1. User submits query: "AI-powered 311 systems"

2. Backend receives request
   ├── Search existing cards (vector similarity)
   ├── If matches found: return cards
   └── If insufficient: trigger research task

3. Research task (async)
   ├── Expand search to external sources
   ├── Fetch and analyze results
   ├── Create new card(s)
   └── Notify user when complete

4. Return results as cards
```

## Data Flow: Implications Analysis

```
1. User clicks "Analyze Implications" on a card

2. Backend receives request with:
   ├── Card ID
   └── Perspective (department/pillar)

3. LLM generates first-order implications

4. User selects branches to expand

5. LLM generates second/third-order implications

6. User scores implications (likelihood, desirability)

7. Analysis saved to card record
```

## Authentication Flow

```
1. User visits app
2. Redirect to Supabase Auth (email/password or SSO)
3. Supabase returns JWT
4. Frontend stores JWT, includes in API requests
5. Backend validates JWT with Supabase
6. Row-level security enforces data access
```

## Hosting Architecture (Pilot)

```
┌─────────────────────────────────────────────────────────────┐
│                    HUGGINGFACE SPACES                       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Docker Container                                    │   │
│  │  ├── FastAPI application                            │   │
│  │  ├── APScheduler (nightly jobs)                     │   │
│  │  └── Uvicorn server                                 │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│                       SUPABASE                              │
│  ├── PostgreSQL + pgvector                                 │
│  ├── Authentication                                         │
│  ├── Real-time subscriptions                               │
│  └── Storage (if needed for file uploads)                  │
└─────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│              STATIC HOSTING (Vercel/Netlify)               │
│  └── React frontend build                                   │
└─────────────────────────────────────────────────────────────┘
```

## Future Scaling Path

When pilot proves value:

1. Move backend to Azure Container Apps
2. Add Neo4j Aura for graph relationships
3. Add Redis for caching
4. Add proper job queue (Celery + Redis)
5. Integrate with City Azure AD for auth

---

_Document Version: 1.0_
_Last Updated: December 2024_
