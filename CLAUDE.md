# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Foresight is an AI-powered strategic horizon scanning system for the City of Austin. It automates discovery, analysis, and tracking of emerging trends, technologies, and issues that could impact municipal operations, aligned with Austin's strategic framework and CMO's Top 25 Priorities.

## Tech Stack

- **Frontend**: React 18 + TypeScript + Vite + TailwindCSS + Radix UI
- **Backend**: FastAPI (Python 3.11+) with Pydantic
- **Database**: Supabase (PostgreSQL + pgvector for vector search)
- **AI/ML**: Azure OpenAI (GPT-4, embeddings), gpt-researcher for deep research
- **Auth**: Supabase Auth (JWT-based)

## Development Commands

### Backend

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000  # API server
python -m app.worker                                        # Background worker (required for discovery, research, briefs)
pytest                                                      # Run all tests
pytest tests/test_discovery_queue.py -v                     # Run single test file
ruff check .                                                # Lint
```

### Frontend

```bash
cd frontend/foresight-frontend
pnpm dev                    # Development server (port 5173)
pnpm build                  # Production build
pnpm lint                   # ESLint
pnpm test                   # Vitest unit tests
pnpm test:run               # Run tests once (no watch)
pnpm test:e2e               # Playwright E2E tests
pnpm test:e2e:headed        # E2E with browser visible
```

### Database

Migrations are in `supabase/migrations/`. Push to remote with:

```bash
npx supabase db push    # Pushes pending migrations to remote Supabase
```

### Available CLIs

The following CLIs are installed, authenticated, and ready to use directly:

- **Supabase CLI** (`npx supabase`) — push migrations, manage DB, run SQL
- **Vercel CLI** (`vercel`) — check deployments, manage environment variables
- **GitHub CLI** (`gh`) — create PRs, view issues, manage repos

Use these tools directly rather than asking the user to perform manual steps.

## Architecture

### Backend Structure (`backend/app/`)

- `main.py` - FastAPI app with all API endpoints (monolithic, ~210KB)
- `worker.py` - Background job processor for long-running tasks
- `ai_service.py` - AI classification, scoring, and analysis
- `discovery_service.py` - Content discovery pipeline and processing
- `research_service.py` - Deep research using gpt-researcher
- `brief_service.py` - Executive brief generation
- `export_service.py` - PDF/PPTX/CSV export functionality
- `security.py` - Rate limiting, auth, security middleware
- `openai_provider.py` - Centralized Azure OpenAI client configuration
- `models/` - Pydantic models for request/response types
- `source_fetchers/` - RSS, NewsAPI, and other content fetchers

### Frontend Structure (`frontend/foresight-frontend/src/`)

- `pages/` - Route components (Dashboard, Discover, Workstreams, etc.)
- `components/` - Reusable UI components, badges, cards
- `components/ui/` - shadcn/ui base components
- `components/kanban/` - Workstream kanban board components
- `lib/` - API clients, utilities
  - `discovery-api.ts` - Card and discovery API calls
  - `workstream-api.ts` - Workstream management
  - `analytics-api.ts` - Analytics endpoints

### Key Concepts

- **Cards**: Atomic units of strategic intelligence with metadata (pillar, stage, horizon, scores)
- **Strategic Pillars**: CH (Community Health), MC (Mobility), HS (Housing), EC (Economic), ES (Environmental), CE (Cultural)
- **Maturity Stages**: Concept → Exploring → Pilot → PoC → Implementing → Scaling → Mature → Declining
- **Multi-Factor Scoring**: Impact, Relevance, Velocity, Novelty, Opportunity, Risk (0-100 each)
- **Workstreams**: User-created research streams with kanban tracking
- **Discovery Queue**: Personalized card recommendations

## Environment Variables

### Backend (`backend/.env`)

```
SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_SERVICE_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_DEPLOYMENT=
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=
TAVILY_API_KEY=         # For gpt-researcher
FIRECRAWL_API_KEY=      # For gpt-researcher
```

### Frontend (`frontend/foresight-frontend/.env`)

```
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
VITE_API_URL=http://localhost:8000
```

## API Patterns

- All API endpoints are in `main.py` under `/api/v1/`
- User-specific endpoints use `/api/v1/me/` prefix
- Authentication via Bearer token in Authorization header
- Rate limiting on sensitive endpoints via `@rate_limit_*` decorators

## Database

- Row Level Security (RLS) enabled on all tables
- pgvector extension for semantic search (0.92 similarity threshold for card matching)
- Key tables: `cards`, `workstreams`, `discovery_runs`, `card_sources`, `user_follows`

## Worker Jobs

The worker (`app/worker.py`) handles:

- Discovery pipeline runs (content fetching, triage, classification)
- Deep research tasks (gpt-researcher integration)
- Executive brief generation
- Jobs timeout after configured duration and are marked failed

## Testing

Backend tests use pytest with async support. Frontend uses Vitest for unit tests and Playwright for E2E.

Test user credentials for local development:

- Email: `test@foresight.austintexas.gov`
- Password: `TestPassword123!`
