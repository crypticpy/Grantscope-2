# Foresight

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6-blue.svg)](https://www.typescriptlang.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.3-61DAFB.svg)](https://reactjs.org/)

> **AI-powered strategic horizon scanning system for the City of Austin**

Foresight automates the discovery, analysis, and tracking of emerging trends, technologies, and issues that could impact municipal operations. It aligns with Austin's strategic framework and the CMO's Top 25 Priorities.

---

## Table of Contents

- [Features](#-features)
- [Quick Start](#-quick-start)
- [Architecture](#-architecture)
- [API Reference](#-api-reference)
- [AI Pipeline](#-ai-pipeline)
- [Strategic Alignment](#-strategic-alignment)
- [Documentation](#-documentation)
- [Development](#-development)
- [License](#-license)

---

## Features

- **Card-Based Intelligence** - Atomic units of strategic information with rich metadata
- **Multi-Source Discovery** - Automated content fetching from 5 source categories:
  - RSS/Atom feeds from curated sources
  - Major news outlets (Reuters, AP, GCN)
  - Academic publications (arXiv)
  - Government sources (.gov domains)
  - Tech blogs (TechCrunch, Ars Technica)
- **AI-Powered Classification** - Automatic categorization against Austin's strategic pillars
- **Vector Search** - Semantic search across all content using embeddings
- **Multi-Factor Scoring** - Impact, relevance, velocity, novelty, opportunity, and risk
- **Workstream Management** - Custom research streams for focused analysis
- **Personalized Discovery Queue** - Cards ranked by user preferences and context
- **Advanced Search & Filtering** - Save searches, filter by scores, date ranges

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (pnpm recommended)
- Supabase account
- Azure OpenAI credentials (or OpenAI, depending on configuration)

### 1. Database Setup

```bash
# Create a Supabase project at https://supabase.com
# Run migrations from the supabase/migrations folder
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Supabase and OpenAI credentials

# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# In a separate terminal, run the background worker (required for deep research, discovery, briefs)
python -m app.worker
```

### 3. Frontend Setup

```bash
cd frontend/foresight-frontend
pnpm install

# Configure environment
cp .env.example .env
# Edit .env with your Supabase URL and anon key

# Run development server
pnpm dev
```

---

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   React + TS    │────▶│    FastAPI      │────▶│    Supabase     │
│   (Frontend)    │     │    (Backend)    │     │  (PostgreSQL)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                              │                        │
                              ▼                        ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │   OpenAI API    │     │    pgvector     │
                        │  (GPT-4, Embed) │     │ (Vector Search) │
                        └─────────────────┘     └─────────────────┘
```

### Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, TypeScript, Vite, TailwindCSS, Radix UI |
| Backend | FastAPI, Python 3.11+, Pydantic |
| Database | Supabase (PostgreSQL + pgvector) |
| AI/ML | OpenAI GPT-4, Embeddings, gpt-researcher |
| Auth | Supabase Auth (JWT) |

---

## API Reference

### Authentication
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/me` | GET | Get current user profile |
| `/api/v1/me` | PATCH | Update user profile |

### Cards
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/cards` | GET | List cards with filtering |
| `/api/v1/cards/{id}` | GET | Get card details |
| `/api/v1/cards` | POST | Create new card |
| `/api/v1/cards/search` | POST | Advanced search |

### Discovery
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/discovery/trigger` | POST | Trigger discovery run |
| `/api/v1/discovery/runs` | GET | List discovery runs |
| `/api/v1/me/discovery/queue` | GET | Get personalized queue |

### Workstreams
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/me/workstreams` | GET | List user workstreams |
| `/api/v1/me/workstreams` | POST | Create workstream |
| `/api/v1/me/workstreams/{id}/feed` | GET | Get workstream feed |

---

## AI Pipeline

### Nightly Processing (6 PM Austin Time)

1. **Content Discovery** - Fetch from NewsAPI, RSS feeds, academic sources
2. **Triage** - Filter for municipal relevance using AI
3. **Analysis** - Classification and multi-factor scoring
4. **Matching** - Vector similarity to existing cards (0.92 threshold)
5. **Storage** - Create new cards or enrich existing ones

### Scoring Metrics

| Metric | Description | Range |
|--------|-------------|-------|
| Impact | Potential municipal impact | 0-100 |
| Relevance | Austin-specific relevance | 0-100 |
| Velocity | Trending speed | 0-100 |
| Novelty | Innovation level | 0-100 |
| Opportunity | Positive potential | 0-100 |
| Risk | Potential challenges | 0-100 |

---

## Strategic Alignment

### Strategic Pillars

| Code | Pillar |
|------|--------|
| CH | Community Health |
| MC | Mobility & Connectivity |
| HS | Housing & Economic Stability |
| EC | Economic Development |
| ES | Environmental Sustainability |
| CE | Cultural & Entertainment |

### Maturity Stages

1. Concept → 2. Exploring → 3. Pilot → 4. Proof of Concept → 5. Implementing → 6. Scaling → 7. Mature → 8. Declining

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
- [Railway Worker Setup](docs/RAILWAY_WORKER_SETUP.md)

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

---

## Security

- Row Level Security (RLS) on all database tables
- JWT-based authentication via Supabase
- Environment variable protection for secrets
- CORS configuration for production domains

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Built with care for the City of Austin**
