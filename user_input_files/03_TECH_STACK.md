# Foresight: Tech Stack & Dependencies

## Overview

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Frontend | React + TypeScript + Vite | Modern, fast, type-safe |
| Styling | TailwindCSS | Utility-first, rapid prototyping |
| Backend | FastAPI (Python 3.11+) | Async, fast, great for AI workloads |
| Database | Supabase (PostgreSQL) | Managed, pgvector, auth included |
| Vector Search | pgvector | Built into Supabase, no extra service |
| LLM | Azure OpenAI / OpenAI | GPT-4o for analysis |
| Embeddings | text-embedding-ada-002 | Standard, cost-effective |
| Scheduling | APScheduler | Simple, in-process for pilot |
| Hosting | HuggingFace Spaces | Free tier, Docker support |

---

## Frontend Dependencies

### package.json (core)

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "@supabase/supabase-js": "^2.38.0",
    "@tanstack/react-query": "^5.8.0",
    "axios": "^1.6.0",
    "date-fns": "^2.30.0",
    "lucide-react": "^0.292.0",
    "zustand": "^4.4.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.2.0",
    "autoprefixer": "^10.4.16",
    "postcss": "^8.4.31",
    "tailwindcss": "^3.3.5",
    "typescript": "^5.2.0",
    "vite": "^5.0.0"
  }
}
```

### Key Libraries

| Package | Purpose |
|---------|---------|
| `react-router-dom` | Client-side routing |
| `@supabase/supabase-js` | Database client, auth, real-time |
| `@tanstack/react-query` | Data fetching, caching |
| `axios` | HTTP client for API calls |
| `date-fns` | Date formatting |
| `lucide-react` | Icons |
| `zustand` | Lightweight state management |

---

## Backend Dependencies

### requirements.txt

```
# Core
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-dotenv>=1.0.0

# Database
supabase>=2.0.0
asyncpg>=0.29.0

# AI/ML
openai>=1.3.0
tiktoken>=0.5.0
numpy>=1.24.0

# HTTP/Async
httpx>=0.25.0
aiohttp>=3.9.0

# Scheduling
apscheduler>=3.10.0

# Data Processing
feedparser>=6.0.0
beautifulsoup4>=4.12.0
lxml>=4.9.0

# Utilities
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.0
```

### Key Libraries

| Package | Purpose |
|---------|---------|
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
| `supabase` | Database client |
| `openai` | LLM API client |
| `tiktoken` | Token counting |
| `apscheduler` | Job scheduling |
| `feedparser` | RSS/Atom parsing |
| `beautifulsoup4` | HTML parsing |
| `httpx` | Async HTTP client |

---

## Database (Supabase)

### Required Extensions

```sql
-- Enable pgvector for embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable pg_trgm for text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

### Connection

```python
from supabase import create_client

supabase = create_client(
    supabase_url=os.environ["SUPABASE_URL"],
    supabase_key=os.environ["SUPABASE_KEY"]
)
```

---

## AI Services

### Azure OpenAI (Production)

```python
from openai import AzureOpenAI

client = AzureOpenAI(
    api_key=os.environ["AZURE_OPENAI_KEY"],
    api_version="2024-02-15-preview",
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"]
)
```

### OpenAI Direct (Pilot)

```python
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
```

### Models Used

| Task | Model | Approx Cost |
|------|-------|-------------|
| Card summarization | gpt-4o | $0.005/1K tokens |
| Implications analysis | gpt-4o | $0.005/1K tokens |
| Triage/classification | gpt-4o-mini | $0.00015/1K tokens |
| Embeddings | text-embedding-ada-002 | $0.0001/1K tokens |

---

## Environment Variables

### Backend (.env)

```
# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...
SUPABASE_SERVICE_KEY=eyJ...

# OpenAI (choose one)
OPENAI_API_KEY=sk-...

# Azure OpenAI (production)
AZURE_OPENAI_KEY=...
AZURE_OPENAI_ENDPOINT=https://xxx.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=gpt-4o

# News APIs
NEWSAPI_KEY=...
GDELT_API_KEY=...

# App Config
ENVIRONMENT=development
LOG_LEVEL=INFO
NIGHTLY_SCAN_HOUR=2
```

### Frontend (.env)

```
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
VITE_API_URL=https://xxx.hf.space/api
```

---

## Project Structure

### Backend

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry
│   ├── config.py            # Settings/env vars
│   ├── database.py          # Supabase client
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── cards.py         # Card endpoints
│   │   ├── users.py         # User endpoints
│   │   ├── workstreams.py   # Workstream endpoints
│   │   ├── analysis.py      # Implications endpoints
│   │   └── search.py        # Search endpoints
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── card.py
│   │   ├── user.py
│   │   ├── workstream.py
│   │   └── source.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ai_service.py    # LLM interactions
│   │   ├── embedding_service.py
│   │   ├── card_service.py
│   │   └── search_service.py
│   │
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── scanner.py       # Nightly scan orchestration
│   │   ├── fetchers/        # Source-specific fetchers
│   │   ├── processors.py    # Article processing
│   │   └── scheduler.py     # APScheduler setup
│   │
│   └── utils/
│       ├── __init__.py
│       └── helpers.py
│
├── tests/
├── Dockerfile
├── requirements.txt
└── pyproject.toml
```

### Frontend

```
frontend/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── index.css
│   │
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Header.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── Layout.tsx
│   │   ├── cards/
│   │   │   ├── CardPreview.tsx
│   │   │   ├── CardDetail.tsx
│   │   │   ├── CardTimeline.tsx
│   │   │   └── CardList.tsx
│   │   ├── workstreams/
│   │   ├── analysis/
│   │   └── common/
│   │
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── Discovery.tsx
│   │   ├── CardPage.tsx
│   │   ├── Workstreams.tsx
│   │   └── Settings.tsx
│   │
│   ├── hooks/
│   │   ├── useCards.ts
│   │   ├── useWorkstreams.ts
│   │   └── useAuth.ts
│   │
│   ├── services/
│   │   ├── api.ts
│   │   └── supabase.ts
│   │
│   ├── store/
│   │   └── index.ts
│   │
│   └── types/
│       └── index.ts
│
├── public/
├── index.html
├── package.json
├── tailwind.config.js
├── tsconfig.json
└── vite.config.ts
```

---

## Docker Configuration (Backend)

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app ./app

EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
```

Port 7860 is the default for HuggingFace Spaces.

---

*Document Version: 1.0*
*Last Updated: December 2024*
