# GrantScope2

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6-blue.svg)](https://www.typescriptlang.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.3-61DAFB.svg)](https://reactjs.org/)

> **AI-powered grant discovery and strategic research platform for the City of Austin**

GrantScope2 automates the discovery, analysis, and tracking of grant opportunities and emerging trends relevant to municipal operations. It combines horizon scanning with grant-specific tooling — alignment scoring, guided application wizards, and AI-assisted proposal drafting — aligned with Austin's strategic framework and the CMO's Top 25 Priorities.

---

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [API Reference](#api-reference)
- [AI Pipeline](#ai-pipeline)
- [Strategic Alignment](#strategic-alignment)
- [Documentation](#documentation)
- [Development](#development)
- [License](#license)

---

## Features

### Grant Discovery & Application

- **Grants.gov + SAM.gov Integration** — Automated fetching of federal grant opportunities
- **Grant Alignment Scoring** — AI-scored fit across 6 factors (program fit, amount, competition, readiness, urgency, probability)
- **Guided Application Wizard** — Step-by-step AI interview that builds a grant application plan
- **AI Proposal Drafting** — Section-by-section proposal generation (executive summary, needs statement, project description, budget narrative, timeline, evaluation plan)
- **PDF Grant Document Parsing** — Upload NOFOs and grant announcements for automatic extraction

### Strategic Intelligence

- **Card-Based Intelligence** — Atomic units of strategic information with rich metadata and version-tracked descriptions
- **Multi-Source Discovery** — Automated content fetching from:
  - Grants.gov and SAM.gov (federal opportunities)
  - RSS/Atom feeds from curated sources
  - Government and academic publications
  - Web crawling via gpt-researcher
- **AI-Powered Classification** — Categorization against Austin's strategic pillars using GPT-4.1
- **Vector Search** — Semantic search across all content using pgvector embeddings
- **Multi-Factor Scoring** — Impact, relevance, velocity, novelty, opportunity, and risk (0–100 each)

### Workflow & Analysis

- **Workstream Management** — Custom research streams with kanban tracking
- **Personalized Discovery Queue** — Cards ranked by user preferences and context
- **Deep Research** — Multi-round investigations with source verification via gpt-researcher
- **Executive Briefs** — AI-generated strategic summaries
- **Cross-Signal Connections** — Automatic discovery of related trends via embedding similarity
- **Export** — PDF, PPTX, CSV, and Gamma.app presentation generation

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Azure OpenAI credentials
- Node.js 18+ with pnpm (for frontend development)

### 1. Start Infrastructure

```bash
# Clone and configure
cp backend/.env.example backend/.env
# Edit backend/.env with your Azure OpenAI credentials

# Start all services (Postgres, PostgREST, GoTrue, nginx gateway, SearXNG, API, worker)
docker compose up -d
```

This starts 7 services — see [Architecture](#architecture) for details.

### 2. Run Migrations

```bash
# Apply database migrations
./infra/migrate.sh
```

### 3. Frontend Setup

```bash
cd frontend/foresight-frontend
pnpm install

cp .env.example .env
# Edit .env — point VITE_SUPABASE_URL to the gateway and VITE_API_URL to the backend

pnpm dev
```

### Local Development (without Docker)

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Worker (separate terminal)
python -m app.worker
```

---

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   React + TS    │────▶│    FastAPI       │────▶│  PostgreSQL 16  │
│   (Vercel)      │     │ (Azure Cont.App)│     │   + pgvector    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                      │                        ▲
        │                      ▼                        │
        │               ┌─────────────────┐     ┌──────┴──────────┐
        │               │  Azure OpenAI   │     │   PostgREST     │
        │               │ GPT-4.1 / Embed │     │   + GoTrue      │
        │               └─────────────────┘     └──────┬──────────┘
        │                      │                        │
        │                      ▼                ┌───────┴─────────┐
        └─────────────────────────────────────▶│  nginx gateway  │
                                                │ (Supabase-compat)│
                                                └─────────────────┘
```

The frontend connects to **two** backends: the FastAPI server for business logic and AI, and the nginx gateway (which proxies PostgREST + GoTrue) for direct database queries and authentication. The gateway mirrors Supabase's URL structure, so the standard `supabase-js` and `supabase-py` client libraries work without modification.

### Tech Stack

| Layer             | Technology                                                       |
| ----------------- | ---------------------------------------------------------------- |
| Frontend          | React 18, TypeScript, Vite, TailwindCSS, Radix UI (shadcn/ui)    |
| Frontend Hosting  | Vercel                                                           |
| Backend           | FastAPI, Python 3.11, Gunicorn + Uvicorn workers                 |
| Background Worker | Same container, `GRANTSCOPE_PROCESS_TYPE=worker`                 |
| Database          | PostgreSQL 16 + pgvector (self-hosted)                           |
| Database REST API | PostgREST (Supabase-compatible)                                  |
| Auth              | GoTrue v2 (Supabase-compatible, self-hosted), JWT-based          |
| API Gateway       | nginx — routes `/rest/v1/*` to PostgREST, `/auth/v1/*` to GoTrue |
| AI                | Azure OpenAI (gpt-4.1, gpt-4.1-mini, text-embedding-ada-002)     |
| Deep Research     | gpt-researcher + Azure OpenAI                                    |
| Search            | SearXNG (self-hosted) with Serper / Tavily fallbacks             |
| Grant Data        | Grants.gov API, SAM.gov Opportunities API                        |
| Exports           | PDF (reportlab), PPTX (python-pptx), CSV (pandas), Gamma.app     |
| Container Hosting | Azure Container Apps                                             |

### Docker Compose Services

| Service             | Image                       | Purpose                                              |
| ------------------- | --------------------------- | ---------------------------------------------------- |
| `postgres`          | `pgvector/pgvector:pg16`    | PostgreSQL 16 with pgvector extension                |
| `postgrest`         | `postgrest/postgrest`       | REST API over PostgreSQL (Supabase-compatible)       |
| `gotrue`            | `supabase/gotrue:v2.172.1`  | Authentication server (JWT issuance, signup/login)   |
| `gateway`           | `nginx:alpine`              | Reverse proxy — unified Supabase-compatible endpoint |
| `searxng`           | `searxng/searxng`           | Self-hosted meta-search engine (zero API cost)       |
| `grantscope-web`    | Custom (backend/Dockerfile) | FastAPI API server                                   |
| `grantscope-worker` | Custom (backend/Dockerfile) | Background job processor                             |

---

## API Reference

### Authentication

| Endpoint     | Method | Description              |
| ------------ | ------ | ------------------------ |
| `/api/v1/me` | GET    | Get current user profile |
| `/api/v1/me` | PATCH  | Update user profile      |

### Cards

| Endpoint               | Method | Description                  |
| ---------------------- | ------ | ---------------------------- |
| `/api/v1/cards`        | GET    | List cards with filtering    |
| `/api/v1/cards/{id}`   | GET    | Get card details             |
| `/api/v1/cards`        | POST   | Create new card              |
| `/api/v1/cards/search` | POST   | Semantic and advanced search |

### Discovery

| Endpoint                     | Method | Description            |
| ---------------------------- | ------ | ---------------------- |
| `/api/v1/discovery/trigger`  | POST   | Trigger discovery run  |
| `/api/v1/discovery/runs`     | GET    | List discovery runs    |
| `/api/v1/me/discovery/queue` | GET    | Get personalized queue |

### Workstreams

| Endpoint                           | Method | Description           |
| ---------------------------------- | ------ | --------------------- |
| `/api/v1/me/workstreams`           | GET    | List user workstreams |
| `/api/v1/me/workstreams`           | POST   | Create workstream     |
| `/api/v1/me/workstreams/{id}/feed` | GET    | Get workstream feed   |

### Grant Wizard

| Endpoint                                 | Method | Description                         |
| ---------------------------------------- | ------ | ----------------------------------- |
| `/api/v1/wizard/sessions`                | POST   | Start a new wizard session          |
| `/api/v1/wizard/sessions/{id}/grant`     | POST   | Process grant context (text or PDF) |
| `/api/v1/wizard/sessions/{id}/interview` | POST   | Submit interview answers            |
| `/api/v1/wizard/sessions/{id}/plan`      | POST   | Synthesize application plan         |

### Proposals

| Endpoint                                             | Method | Description                    |
| ---------------------------------------------------- | ------ | ------------------------------ |
| `/api/v1/proposals`                                  | GET    | List proposals                 |
| `/api/v1/proposals`                                  | POST   | Create proposal                |
| `/api/v1/proposals/{id}/sections/{section}/generate` | POST   | AI-generate a proposal section |

---

## AI Pipeline

### Discovery Processing

1. **Content Fetching** — Pull from Grants.gov, SAM.gov, RSS feeds, government/academic sources
2. **Triage** — AI filters for municipal relevance
3. **Classification** — Categorize by strategic pillar, maturity stage, and horizon
4. **Multi-Factor Scoring** — Score across 6 dimensions using GPT-4.1
5. **Deduplication** — Vector similarity matching (0.92 threshold) to merge or enrich existing cards
6. **Storage** — Create new cards or update existing ones with version-tracked descriptions

### Grant Alignment Scoring

When a card represents a grant opportunity, alignment scoring evaluates:

| Factor      | Description                                  | Weight    |
| ----------- | -------------------------------------------- | --------- |
| Program Fit | How well the grant matches city capabilities | High      |
| Amount      | Funding amount relative to effort            | Medium    |
| Competition | Estimated competitiveness                    | Medium    |
| Readiness   | City's readiness to apply                    | High      |
| Urgency     | Deadline proximity                           | Medium    |
| Probability | Overall likelihood of award                  | Composite |

### Scoring Metrics (All Cards)

| Metric      | Description                | Range |
| ----------- | -------------------------- | ----- |
| Impact      | Potential municipal impact | 0–100 |
| Relevance   | Austin-specific relevance  | 0–100 |
| Velocity    | Trending speed             | 0–100 |
| Novelty     | Innovation level           | 0–100 |
| Opportunity | Positive potential         | 0–100 |
| Risk        | Potential challenges       | 0–100 |

---

## Strategic Alignment

### Strategic Pillars

| Code | Pillar                       |
| ---- | ---------------------------- |
| CH   | Community Health             |
| MC   | Mobility & Connectivity      |
| HS   | Housing & Economic Stability |
| EC   | Economic Development         |
| ES   | Environmental Sustainability |
| CE   | Cultural & Entertainment     |

### Grant Categories

The system maps federal opportunities to 8 categories aligned with City of Austin domains, scored against the 43 city departments that may serve as applicants.

### Maturity Stages

Concept → Exploring → Pilot → Proof of Concept → Implementing → Scaling → Mature → Declining

---

## Documentation

Detailed documentation is available in the `/docs` folder:

- [Project Overview](docs/01_PROJECT_OVERVIEW.md)
- [Architecture](docs/02_ARCHITECTURE.md)
- [Tech Stack](docs/03_TECH_STACK.md)
- [Data Model](docs/04_DATA_MODEL.md)
- [API Specification](docs/05_API_SPEC.md)
- [Frontend Specification](docs/06_FRONTEND_SPEC.md)
- [AI Pipeline](docs/07_AI_PIPELINE.md)
- [MVP Scope](docs/08_MVP_SCOPE.md)
- [Taxonomy](docs/09_TAXONOMY.md)
- [Security](docs/SECURITY.md)

---

## Development

### Running Tests

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend/foresight-frontend
pnpm test
```

### Code Quality

```bash
# Backend linting
cd backend
ruff check .

# Frontend linting
cd frontend/foresight-frontend
pnpm lint
```

### Environment Variables

See `backend/.env.example` and `frontend/foresight-frontend/.env.example` for full configuration reference. Key variables:

**Backend** — Azure OpenAI credentials, database connection (SUPABASE_URL pointing to the self-hosted gateway), SAM.gov API key, search provider config.

**Frontend** — Gateway URL (VITE_SUPABASE_URL), anon key, API URL.

---

## Security

- Row Level Security (RLS) on all database tables
- JWT-based authentication via self-hosted GoTrue
- PostgREST role-switching (`anon`, `authenticated`, `service_role`) enforces RLS
- Rate limiting on auth and sensitive endpoints
- Environment variable protection for all secrets
- CORS restricted to production domains

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Built with care for the City of Austin**
