# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GrantScope2 is an AI-powered grant discovery and strategic horizon scanning platform for the City of Austin. It automates discovery, analysis, and tracking of grant opportunities and emerging trends relevant to municipal operations, aligned with Austin's strategic framework and the CMO's Top 25 Priorities.

## Tech Stack

- **Frontend**: React 18 + TypeScript + Vite + TailwindCSS + Radix UI (shadcn/ui pattern)
- **Backend**: FastAPI (Python 3.11+) with Pydantic, 31 routers
- **Database**: PostgreSQL 16 + pgvector (self-hosted), SQLAlchemy 2.0 async with asyncpg
- **Migrations**: Alembic (78 historical SQL migrations stamped as baseline, new features use Alembic)
- **AI/ML**: Azure OpenAI (gpt-4.1, gpt-4.1-mini, text-embedding-ada-002), gpt-researcher
- **Auth**: Custom JWT auth (bcrypt + python-jose), self-hosted GoTrue for legacy compatibility
- **Search**: SearXNG (self-hosted) with Serper/Tavily fallbacks
- **Hosting**: Azure Container Apps (backend), Vercel (frontend)

## Development Commands

### Backend

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000  # API server (embeds worker by default)
python -m app.worker                                        # Standalone worker (if not embedded)
pytest                                                      # Run all tests
pytest tests/test_discovery_queue.py -v                     # Run single test file
pytest tests/test_discovery_queue.py::test_name -v          # Run single test
ruff check .                                                # Lint
```

### Frontend

```bash
cd frontend/foresight-frontend
pnpm dev                    # Dev server (port 5173) — no proxy, expects backend on VITE_API_URL
pnpm build                  # Production build
pnpm build:prod             # Production build with TypeScript check (strips source identifiers)
pnpm lint                   # ESLint
pnpm test                   # Vitest unit tests (watch mode)
pnpm test:run               # Run tests once
pnpm test:coverage          # Coverage (scoped to visualizations)
pnpm test:e2e               # Playwright E2E tests
pnpm test:e2e:headed        # E2E with browser visible
```

### Database Migrations

```bash
cd backend
alembic upgrade head        # Apply pending migrations
alembic revision --autogenerate -m "description"  # Generate new migration
alembic history             # View migration history
```

Historical SQL migrations (78 files) are applied via `infra/migrate.sh` using psql. Alembic baseline stamp (`20260217_000001`) marks the starting point — new features use Alembic exclusively.

### Docker

```bash
docker compose up -d                          # Start all 7 services
docker compose --profile app up -d            # Include web + worker containers
```

### Available CLIs

- **GitHub CLI** (`gh`) — create PRs, view issues, manage repos
- **Vercel CLI** (`vercel`) — check deployments, manage environment variables

## Architecture

### Backend Structure (`backend/app/`)

**App entry point**: `main.py` (~280 lines) uses an app factory pattern (`create_app()`). Only 2 auth endpoints are inline; everything else is delegated to routers. The lifespan manager optionally starts APScheduler and an embedded worker.

**Routers** (`app/routers/` — 31 files): Endpoints are fully split out. Key routers: `cards.py`, `discovery.py`, `workstreams.py`, `proposals.py`, `wizard.py`, `chat.py`, `analytics.py`, `dashboard.py`, `applications.py`, `budget.py`, `checklist.py`, `collaboration.py`, `attachments.py`, `exports.py`.

**Services** (~28 files at `app/` and `app/services/`): Business logic layer. Key services: `ai_service.py` (classification/scoring), `discovery_service.py` (content pipeline), `research_service.py` (gpt-researcher), `brief_service.py`, `wizard_service.py`, `proposal_service.py`, `chat_service.py`, `signal_agent_service.py`, `pattern_detection_service.py`.

**Source fetchers** (`app/source_fetchers/`): `grants_gov_fetcher.py`, `sam_gov_fetcher.py`, `rss_fetcher.py`, `news_fetcher.py`, `government_fetcher.py`, `academic_fetcher.py`, `searxng_fetcher.py`, `serper_fetcher.py`.

**Shared dependencies** (`app/deps.py`): Provides `get_db`, `get_current_user`, `openai_client`, rate limiters — all routers import from here.

**Database** (`app/database.py`): SQLAlchemy 2.0 async engine with asyncpg, connection pooling (10 + 20 overflow), `get_db()` dependency with auto-commit/rollback.

**ORM models** (`app/models/db/` — 24 files, ~55+ models): All use SQLAlchemy 2.0 `Mapped[]`/`mapped_column()` syntax. The `Card` model is the largest (~300 lines, 60+ columns) with pgvector `VECTOR(1536)` embedding. Key model files: `card.py`, `workstream.py`, `discovery.py`, `proposal.py`, `wizard_session.py`, `grant_application.py`, `chat.py`, `reference.py` (7 lookup tables).

**Worker** (`app/worker.py`): Async polling loop with exponential backoff (5s–30s). Processes: research tasks, executive briefs, discovery runs, workstream scans, RSS monitoring, scheduled discovery. Uses optimistic locking for job claims. Runs embedded in web process by default (`GRANTSCOPE_EMBED_WORKER=true`) or standalone (`python -m app.worker`).

**Scheduler** (`app/scheduler.py`): APScheduler with 9 cron/interval jobs. Enabled via `GRANTSCOPE_ENABLE_SCHEDULER=true`.

### Frontend Structure (`frontend/foresight-frontend/src/`)

**Routing** (`App.tsx`): react-router-dom v6 with `BrowserRouter`. Dashboard and Login are eagerly loaded; all other routes use `React.lazy()` + `Suspense`. Protected routes wrapped in `<ProtectedRoute>` (auth check + error boundary). Legacy `/cards/:slug` redirects to `/signals/:slug`. Grant aliases: `/opportunities` → Signals, `/programs` → Workstreams.

**API layer** (`src/lib/`): All API calls use native `fetch` — no axios, no supabase-js. Each module (`discovery-api.ts`, `workstream-api.ts`, `analytics-api.ts`, `chat-api.ts`, `wizard-api.ts`, `proposal-api.ts`, `feeds-api.ts`, etc.) follows the same pattern: import `API_BASE_URL` from config, accept token parameter, return typed promises. Chat uses SSE streaming. Wizard supports FormData uploads and blob downloads.

**State management**: No external state library. Single `AuthContext` for auth state. Everything else uses component-local `useState`/`useEffect` and custom hooks. Auth tokens stored in localStorage (`gs2_token`, `gs2_user`).

**Auth flow**: Custom JWT — `POST /api/v1/auth/login` returns `{ access_token, user }`. Token validated on mount via `GET /api/v1/auth/me`. Sign-out is client-side only (clear localStorage). `getStoredToken()` exported from `App.tsx` for API calls.

**Key pages**: `Dashboard.tsx`, `DiscoveryQueue.tsx` (largest ~70KB), `Signals.tsx`, `CardDetail.tsx`, `Workstreams.tsx`, `WorkstreamKanban.tsx`, `AskGrantScope.tsx` (AI chat), `AnalyticsV2.tsx`, `GrantWizard.tsx`, `ProposalEditor.tsx`.

**UI patterns**: shadcn/ui (Radix + Tailwind + CVA), `@dnd-kit` for kanban drag-and-drop, `@xyflow/react` for graph diagrams, `recharts` for charts, `@tanstack/react-virtual` for virtualized lists, `react-hook-form` + `zod` for forms.

**Path alias**: `@` maps to `./src` (configured in both `vite.config.ts` and `tsconfig.json`).

**Design system**: City of Austin brand colors (`brand-blue: #44499C`, `brand-green: #009F4D`), Geist font, class-based dark mode via `next-themes`.

### Key Domain Concepts

- **Cards**: Atomic units of strategic intelligence with metadata (pillar, stage, horizon, scores)
- **Strategic Pillars**: CH (Community Health), MC (Mobility), HS (Housing), EC (Economic), ES (Environmental), CE (Cultural)
- **Maturity Stages**: Concept → Exploring → Pilot → PoC → Implementing → Scaling → Mature → Declining
- **Multi-Factor Scoring**: Impact, Relevance, Velocity, Novelty, Opportunity, Risk (0–100 each)
- **Grant Alignment Scoring**: Program Fit, Amount, Competition, Readiness, Urgency, Probability
- **Workstreams**: User-created research streams with kanban tracking
- **Discovery Queue**: Personalized card recommendations
- **Grant Wizard**: Step-by-step AI interview → application plan → proposal drafting

## Environment Variables

### Backend (`backend/.env`)

```
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/dbname
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_DEPLOYMENT=
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=
JWT_SECRET=
ENVIRONMENT=development              # Controls CORS
GRANTSCOPE_EMBED_WORKER=true         # Embed worker in web process
GRANTSCOPE_ENABLE_SCHEDULER=false    # Enable APScheduler
SEARXNG_BASE_URL=                    # Self-hosted search
SEARCH_PROVIDER=                     # searxng | serper | tavily
TAVILY_API_KEY=                      # For gpt-researcher
FIRECRAWL_API_KEY=                   # For gpt-researcher
AZURE_STORAGE_CONNECTION_STRING=     # Blob storage for attachments
```

### Frontend (`frontend/foresight-frontend/.env`)

```
VITE_API_URL=http://localhost:8000   # FastAPI backend URL
```

## API Patterns

- All endpoints under `/api/v1/`, user-specific under `/api/v1/me/`
- Auth via Bearer token in Authorization header
- Rate limiting on sensitive endpoints via `slowapi` decorators
- Chat endpoint uses SSE streaming
- Wizard supports multipart form uploads (PDF parsing)

## Database

- PostgreSQL 16 with pgvector extension for semantic search
- Vector similarity threshold: 0.92 for card deduplication
- Row Level Security (RLS) configured at database level
- `tsvector` column on cards for full-text search
- `helpers/db_utils.py` contains vector search and hybrid search SQL functions

## Testing

Backend tests use pytest with async support. Frontend uses Vitest for unit tests and Playwright for E2E.

Test user credentials for local development:

- Email: `test@grantscope.austintexas.gov`
- Password: `TestPassword123!`

## Docker Services

| Service             | Purpose                               |
| ------------------- | ------------------------------------- |
| `postgres`          | PostgreSQL 16 + pgvector              |
| `postgrest`         | Supabase-compatible REST API (legacy) |
| `gotrue`            | Auth server (legacy)                  |
| `gateway`           | nginx reverse proxy                   |
| `searxng`           | Self-hosted meta-search engine        |
| `grantscope-web`    | FastAPI server                        |
| `grantscope-worker` | Background job processor              |

Deployment uses same Docker image differentiated by `GRANTSCOPE_PROCESS_TYPE` env var (`web` or `worker`).
