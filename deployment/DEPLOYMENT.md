# GrantScope2 Deployment Guide

Comprehensive instructions for deploying GrantScope2, the City of Austin's AI-powered strategic horizon scanning and grant discovery platform. GrantScope2 is a multi-service application composed of a React SPA frontend, a FastAPI backend (API + background worker), PostgreSQL with pgvector, Azure Blob Storage, and Azure OpenAI.

**Last Updated**: 2026-02-17

## Table of Contents

- [Prerequisites](#prerequisites)
- [Architecture Overview](#architecture-overview)
- [Choosing Your Deployment](#choosing-your-deployment)
- [Local Development (Docker Compose)](#local-development-docker-compose)
- [Azure Deployment](#azure-deployment)
- [Environment Variables](#environment-variables)
- [Health Checks & Monitoring](#health-checks--monitoring)
- [Database Migrations](#database-migrations)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before deploying, ensure you have the following installed:

| Tool          | Version | Purpose                                    |
| ------------- | ------- | ------------------------------------------ |
| **Azure CLI** | 2.60+   | Azure resource management and deployment   |
| **Docker**    | 24+     | Container builds and local development     |
| **Python**    | 3.11+   | Backend development and Alembic migrations |
| **pnpm**      | 9+      | Frontend dependency management and builds  |
| **Node.js**   | 20+     | Required by pnpm and Vite toolchain        |
| **psql**      | 16+     | Database migrations (PostgreSQL client)    |

### Platform-Specific Requirements

| Platform                   | Additional Requirements                                      |
| -------------------------- | ------------------------------------------------------------ |
| **Local (Docker Compose)** | Docker Desktop, `backend/.env` file                          |
| **Azure (Production)**     | Azure subscription, Resource Group access, ACR, Azure OpenAI |

---

## Architecture Overview

```
                          ┌─────────────────────────────────────────────────┐
                          │         Azure (South Central US)                │
                          │         rg-aph-cognitive-sandbox-dev-scus-01    │
                          │                                                 │
┌──────────────┐          │  ┌───────────────────────────────────────────┐  │
│              │  HTTPS   │  │  Container Apps Environment               │  │
│   Browser    │─────────►│  │  cae-grantscope2-prod                     │  │
│              │          │  │                                           │  │
└──────────────┘          │  │  ┌─────────────────┐  ┌────────────────┐ │  │
                          │  │  │ ca-grantscope2-  │  │ ca-grantscope2-│ │  │
┌──────────────┐          │  │  │ api-prod         │  │ worker-prod    │ │  │
│ Azure Static │  API     │  │  │                  │  │                │ │  │
│ Web Apps     │─────────►│  │  │ FastAPI          │  │ Background     │ │  │
│ (React SPA)  │  calls   │  │  │ Gunicorn+Uvicorn │  │ Worker         │ │  │
│              │          │  │  │ Port 8000        │  │ Discovery,     │ │  │
└──────────────┘          │  │  │ 4 workers        │  │ Research,      │ │  │
                          │  │  └────────┬─────────┘  │ Briefs         │ │  │
                          │  │           │             └───────┬────────┘ │  │
                          │  └───────────┼─────────────────────┼─────────┘  │
                          │              │                     │             │
                          │              ▼                     ▼             │
                          │  ┌─────────────────────────────────────────────┐│
                          │  │ psql-grantscope2-prod                       ││
                          │  │ Azure PostgreSQL Flexible Server             ││
                          │  │ PostgreSQL 16 + pgvector                     ││
                          │  │ Burstable B1ms (1 vCPU, 2 GB RAM, 32 GB)    ││
                          │  └─────────────────────────────────────────────┘│
                          │                                                 │
                          │  ┌───────────────────┐  ┌─────────────────────┐│
                          │  │ stgrantscope2prod  │  │ kv-grantscope2-prd ││
                          │  │ Azure Blob Storage │  │ Azure Key Vault    ││
                          │  │ application-       │  │ Secrets management ││
                          │  │ attachments        │  │                    ││
                          │  └───────────────────┘  └─────────────────────┘│
                          │                                                 │
                          │  ┌───────────────────┐  ┌─────────────────────┐│
                          │  │ Azure OpenAI       │  │ acrgrantscope2prod ││
                          │  │ GPT-4 + ada-002    │  │ Container Registry ││
                          │  │ (East US 2)        │  │ Docker images      ││
                          │  └───────────────────┘  └─────────────────────┘│
                          │                                                 │
                          │  ┌─────────────────────────────────────────────┐│
                          │  │ log-grantscope2-prod                        ││
                          │  │ Log Analytics Workspace                      ││
                          │  └─────────────────────────────────────────────┘│
                          └─────────────────────────────────────────────────┘

External APIs:
  ├── Tavily API    (deep research search)
  ├── Firecrawl API (web scraping for research)
  ├── Serper API    (Google Search fallback)
  └── SAM.gov API   (grant opportunity data)
```

### Resource Naming Convention

| Resource                   | Name                                   | Type                     |
| -------------------------- | -------------------------------------- | ------------------------ |
| Resource Group             | `rg-aph-cognitive-sandbox-dev-scus-01` | Shared, existing         |
| Container Apps Environment | `cae-grantscope2-prod`                 | Managed environment      |
| API Container App          | `ca-grantscope2-api-prod`              | FastAPI web server       |
| Worker Container App       | `ca-grantscope2-worker-prod`           | Background job processor |
| Container Registry         | `acrgrantscope2prod`                   | Docker image store       |
| PostgreSQL Server          | `psql-grantscope2-prod`                | Flexible Server          |
| Storage Account            | `stgrantscope2prod`                    | Blob storage             |
| Key Vault                  | `kv-grantscope2-prd`                   | Secrets management       |
| Log Analytics              | `log-grantscope2-prod`                 | Centralized logging      |
| Static Web App             | `swa-grantscope2-prod`                 | React SPA hosting        |

---

## Choosing Your Deployment

| Deployment Method      | Best For                               | Complexity | Cost                       |
| ---------------------- | -------------------------------------- | ---------- | -------------------------- |
| **Docker Compose**     | Local development, testing, demos      | Low        | Free (except Azure OpenAI) |
| **Azure (Production)** | Production, enterprise, City of Austin | Medium     | ~$150-250/mo               |

For most workflows, start with **Docker Compose locally** for development and testing, then deploy to **Azure** for production.

### Key Differences

| Feature  | Docker Compose                           | Azure Production                       |
| -------- | ---------------------------------------- | -------------------------------------- |
| Database | Local PostgreSQL 16 + pgvector           | Azure PostgreSQL Flexible Server       |
| Auth     | Self-hosted GoTrue (Supabase-compatible) | Hardcoded test user (Entra ID planned) |
| Search   | Self-hosted SearXNG (zero API cost)      | Tavily/Serper APIs (paid)              |
| Storage  | Local filesystem                         | Azure Blob Storage                     |
| Frontend | Vite dev server (port 5173)              | Azure Static Web Apps                  |
| Scaling  | Single instance                          | Container Apps autoscaling             |

---

## Local Development (Docker Compose)

The repository includes a full `docker-compose.yml` that provides a self-hosted stack mirroring the production architecture without any cloud dependencies (except Azure OpenAI).

### Services

| Service             | Image                           | Purpose                               | Port       |
| ------------------- | ------------------------------- | ------------------------------------- | ---------- |
| `postgres`          | `pgvector/pgvector:pg16`        | PostgreSQL 16 + pgvector              | 5432       |
| `postgrest`         | `postgrest/postgrest`           | Supabase-compatible REST API          | (internal) |
| `gotrue`            | `supabase/gotrue:v2.172.1`      | Supabase-compatible auth              | (internal) |
| `gateway`           | `nginx:alpine`                  | Reverse proxy (mirrors Supabase URLs) | 3000       |
| `searxng`           | `searxng/searxng`               | Self-hosted meta-search engine        | 8888       |
| `grantscope-web`    | Built from `backend/Dockerfile` | FastAPI API server                    | 8000       |
| `grantscope-worker` | Built from `backend/Dockerfile` | Background worker                     | (none)     |

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/CityOfAustin/grantscope-2.git
cd grantscope-2

# 2. Create backend environment file
cp backend/.env.example backend/.env
# Edit backend/.env — at minimum set AZURE_OPENAI_* variables

# 3. Generate JWT keys for self-hosted auth
python infra/generate_keys.py

# 4. Start infrastructure services (postgres, postgrest, gotrue, gateway, searxng)
docker compose up -d

# 5. Apply database migrations
./infra/migrate.sh

# 6. Start application services (API + Worker)
docker compose --profile app up -d

# 7. Start the frontend dev server
cd frontend/foresight-frontend
pnpm install
pnpm dev
```

After startup:

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000/api/v1/health
- **Supabase Gateway**: http://localhost:3000 (REST + Auth APIs)
- **SearXNG UI**: http://localhost:8888

### Docker Compose Profiles

```bash
# Infrastructure only (default — no --profile flag)
docker compose up -d

# Infrastructure + application (API + Worker)
docker compose --profile app up -d

# View logs
docker compose logs -f grantscope-web grantscope-worker

# Rebuild after code changes
docker compose --profile app up -d --build
```

### Building the Docker Image

The Dockerfile is located at `backend/Dockerfile` and uses the **repository root** as the build context. It produces a single image that supports both web and worker modes via the `GRANTSCOPE_PROCESS_TYPE` environment variable.

#### Image Details

| Property      | Value                                                  |
| ------------- | ------------------------------------------------------ |
| Base image    | `python:3.11-slim`                                     |
| Non-root user | `appuser` (UID 1000)                                   |
| Entrypoint    | `/app/entrypoint.sh`                                   |
| Web mode      | Gunicorn + 4 UvicornWorkers on port 8000               |
| Worker mode   | `python -m app.worker`                                 |
| Health check  | `curl -f http://localhost:${PORT:-8000}/api/v1/health` |

#### Build for Local Testing

```bash
docker build -f backend/Dockerfile -t grantscope2:local .
```

#### Build for Azure (AMD64)

Most cloud platforms run on x86_64 architecture. If building on Apple Silicon (M1/M2/M3/M4), specify the platform:

```bash
docker buildx build --platform linux/amd64 \
  -f backend/Dockerfile \
  -t grantscope2:azure .
```

---

## Azure Deployment

### Step 1: Login to Azure

```bash
az login
az account set --subscription "<your-subscription-id>"
```

Verify you have access to the shared resource group:

```bash
az group show --name rg-aph-cognitive-sandbox-dev-scus-01 --query "name" -o tsv
```

### Step 2: Deploy Infrastructure via Bicep

The repository includes Bicep templates for provisioning all Azure resources.

```bash
cd infrastructure
./deploy.sh prod
```

This creates:

- Container Apps Environment (`cae-grantscope2-prod`)
- API Container App (`ca-grantscope2-api-prod`)
- Worker Container App (`ca-grantscope2-worker-prod`)
- Azure Container Registry (`acrgrantscope2prod`)
- Azure PostgreSQL Flexible Server (`psql-grantscope2-prod`)
- Azure Storage Account (`stgrantscope2prod`)
- Azure Key Vault (`kv-grantscope2-prd`)
- Log Analytics Workspace (`log-grantscope2-prod`)
- Managed Identity for Container Apps
- Static Web App (`swa-grantscope2-prod`)

### Step 3: Build and Push Backend Image to ACR

> **CRITICAL: Always Use Versioned Tags**
>
> Azure Container Apps caches images by tag name. Using `:latest` repeatedly will NOT trigger a new deployment -- Azure will silently reuse the cached image. **Always use unique version tags** (e.g., `:v1.2.0`, `:v1.2.0-20260217`) to force Azure to pull the new image and create a new revision.

```bash
# Login to ACR
az acr login --name acrgrantscope2prod

# Set version (use git short hash + date for uniqueness)
VERSION="1.0.0-$(date +%Y%m%d%H%M%S)"

# Build for AMD64 and push to ACR
docker buildx build --platform linux/amd64 \
  -f backend/Dockerfile \
  -t acrgrantscope2prod.azurecr.io/grantscope2:v${VERSION} \
  --push .

# Also tag as latest for reference (but ALWAYS deploy with the versioned tag)
docker tag acrgrantscope2prod.azurecr.io/grantscope2:v${VERSION} \
  acrgrantscope2prod.azurecr.io/grantscope2:latest
docker push acrgrantscope2prod.azurecr.io/grantscope2:latest
```

Update both Container Apps with the new image:

```bash
# Update the API container
az containerapp update \
  --name ca-grantscope2-api-prod \
  --resource-group rg-aph-cognitive-sandbox-dev-scus-01 \
  --image acrgrantscope2prod.azurecr.io/grantscope2:v${VERSION}

# Update the Worker container
az containerapp update \
  --name ca-grantscope2-worker-prod \
  --resource-group rg-aph-cognitive-sandbox-dev-scus-01 \
  --image acrgrantscope2prod.azurecr.io/grantscope2:v${VERSION}
```

### Step 4: Build and Deploy Frontend to Azure Static Web Apps

The frontend is a React 18 + TypeScript + Vite SPA deployed to Azure Static Web Apps.

```bash
cd frontend/foresight-frontend

# Install dependencies
pnpm install

# Build for production (set API URL to the Container App FQDN)
VITE_API_URL=https://ca-grantscope2-api-prod.<region>.azurecontainerapps.io \
VITE_SUPABASE_URL=https://ca-grantscope2-api-prod.<region>.azurecontainerapps.io \
VITE_SUPABASE_ANON_KEY=your-anon-key \
  pnpm build
```

Deploy using the Azure Static Web Apps CLI or GitHub Actions:

```bash
# Option A: Deploy via SWA CLI
npx @azure/static-web-apps-cli deploy ./dist \
  --app-name swa-grantscope2-prod \
  --resource-group rg-aph-cognitive-sandbox-dev-scus-01

# Option B: Deploy via Azure CLI
az staticwebapp deploy \
  --name swa-grantscope2-prod \
  --resource-group rg-aph-cognitive-sandbox-dev-scus-01 \
  --source ./dist
```

**SPA Routing**: Configure a `staticwebapp.config.json` in the frontend build output to handle client-side routing:

```json
{
  "navigationFallback": {
    "rewrite": "/index.html",
    "exclude": ["/assets/*", "/*.ico", "/*.svg"]
  }
}
```

### Step 5: Run Database Migrations

GrantScope2 uses two migration systems during the transition period:

1. **Supabase migrations** (`supabase/migrations/*.sql`) -- legacy schema via psql
2. **Alembic migrations** (`backend/alembic/`) -- new features via SQLAlchemy

#### Apply Supabase Migrations

```bash
# Get the Azure PostgreSQL connection string from Key Vault
DB_HOST="psql-grantscope2-prod.postgres.database.azure.com"
DB_USER="gsadmin"
DB_NAME="grantscope"

# Apply all Supabase SQL migrations
./infra/migrate.sh "postgres://${DB_USER}:<password>@${DB_HOST}:5432/${DB_NAME}?sslmode=require"
```

#### Apply Alembic Migrations

```bash
cd backend

# Set the DATABASE_URL for Alembic (uses asyncpg driver)
export DATABASE_URL="postgresql+asyncpg://${DB_USER}:<password>@${DB_HOST}:5432/${DB_NAME}"

# Apply all pending migrations
alembic upgrade head

# Verify current state
alembic current
```

### Step 6: Configure Secrets in Key Vault

```bash
VAULT_NAME="kv-grantscope2-prd"

# Azure OpenAI credentials
az keyvault secret set --vault-name "$VAULT_NAME" \
  --name "azure-openai-key" \
  --value "<your-azure-openai-key>"

az keyvault secret set --vault-name "$VAULT_NAME" \
  --name "azure-openai-endpoint" \
  --value "https://aph-cognitive-sandbox-openai-eastus2.openai.azure.com"

# Database connection string
az keyvault secret set --vault-name "$VAULT_NAME" \
  --name "database-url" \
  --value "postgresql+asyncpg://gsadmin:<password>@psql-grantscope2-prod.postgres.database.azure.com:5432/grantscope"

# Azure Storage connection string
az keyvault secret set --vault-name "$VAULT_NAME" \
  --name "azure-storage-connection-string" \
  --value "<your-connection-string>"

# Supabase keys (migration period)
az keyvault secret set --vault-name "$VAULT_NAME" \
  --name "supabase-service-key" \
  --value "<your-supabase-service-key>"

# External API keys
az keyvault secret set --vault-name "$VAULT_NAME" \
  --name "tavily-api-key" \
  --value "<your-tavily-key>"

az keyvault secret set --vault-name "$VAULT_NAME" \
  --name "serper-api-key" \
  --value "<your-serper-key>"
```

When deployed with Bicep templates, Container Apps pull secrets from Key Vault and inject them as environment variables automatically via managed identity.

### Step 7: Verify Deployment

```bash
# Check API health
API_FQDN=$(az containerapp show \
  --name ca-grantscope2-api-prod \
  --resource-group rg-aph-cognitive-sandbox-dev-scus-01 \
  --query "properties.configuration.ingress.fqdn" -o tsv)

curl "https://${API_FQDN}/api/v1/health" | python -m json.tool

# Check container app status
az containerapp show \
  --name ca-grantscope2-api-prod \
  --resource-group rg-aph-cognitive-sandbox-dev-scus-01 \
  --query "{status:properties.runningStatus, fqdn:properties.configuration.ingress.fqdn}" \
  -o table

# Check worker status
az containerapp show \
  --name ca-grantscope2-worker-prod \
  --resource-group rg-aph-cognitive-sandbox-dev-scus-01 \
  --query "{status:properties.runningStatus}" \
  -o table

# Verify active revisions
az containerapp revision list \
  --name ca-grantscope2-api-prod \
  --resource-group rg-aph-cognitive-sandbox-dev-scus-01 \
  --query "[].{name:name, active:properties.active, traffic:properties.trafficWeight}" \
  -o table

# Check frontend
SWA_URL=$(az staticwebapp show \
  --name swa-grantscope2-prod \
  --resource-group rg-aph-cognitive-sandbox-dev-scus-01 \
  --query "defaultHostname" -o tsv)

echo "Frontend: https://${SWA_URL}"
curl -s -o /dev/null -w "%{http_code}" "https://${SWA_URL}"
```

---

## Environment Variables

### Backend Environment Variables

#### Required (Application Will Not Start Without These)

| Variable                             | Description                                      | Example                                                         |
| ------------------------------------ | ------------------------------------------------ | --------------------------------------------------------------- |
| `AZURE_OPENAI_ENDPOINT`              | Azure OpenAI resource endpoint                   | `https://aph-cognitive-sandbox-openai-eastus2.openai.azure.com` |
| `AZURE_OPENAI_KEY`                   | Azure OpenAI API key                             | `abc123...`                                                     |
| `AZURE_OPENAI_API_VERSION`           | API version for chat completions                 | `2024-12-01-preview`                                            |
| `AZURE_OPENAI_DEPLOYMENT_CHAT`       | Chat model deployment name                       | `gpt-4.1`                                                       |
| `AZURE_OPENAI_DEPLOYMENT_CHAT_MINI`  | Mini model deployment name                       | `gpt-4.1-mini`                                                  |
| `AZURE_OPENAI_DEPLOYMENT_EMBEDDING`  | Embedding model deployment name                  | `text-embedding-ada-002`                                        |
| `AZURE_OPENAI_EMBEDDING_API_VERSION` | API version for embeddings                       | `2023-05-15`                                                    |
| `SUPABASE_URL`                       | Supabase endpoint (cloud or self-hosted gateway) | `https://your-project.supabase.co`                              |
| `SUPABASE_SERVICE_KEY`               | Supabase service role key                        | `eyJ...`                                                        |

#### Required for Azure Production

| Variable                          | Description                            | Example                                                                                               |
| --------------------------------- | -------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `DATABASE_URL`                    | PostgreSQL connection string (asyncpg) | `postgresql+asyncpg://gsadmin:pass@psql-grantscope2-prod.postgres.database.azure.com:5432/grantscope` |
| `AZURE_STORAGE_CONNECTION_STRING` | Blob storage connection string         | `DefaultEndpointsProtocol=https;AccountName=stgrantscope2prod;...`                                    |

#### Worker-Specific

| Variable                                  | Description                              | Default                                 |
| ----------------------------------------- | ---------------------------------------- | --------------------------------------- |
| `GRANTSCOPE_PROCESS_TYPE`                 | Set to `worker` for background processor | `web`                                   |
| `GRANTSCOPE_ENABLE_SCHEDULER`             | Enable cron jobs (only on worker!)       | `false`                                 |
| `GRANTSCOPE_WORKER_POLL_INTERVAL_SECONDS` | Job polling interval                     | `5`                                     |
| `GRANTSCOPE_WORKER_HEALTH_SERVER`         | Enable health endpoint on worker         | `false` (auto-enabled if `PORT` is set) |
| `GRANTSCOPE_BRIEF_TIMEOUT_SECONDS`        | Brief generation timeout                 | `1800`                                  |
| `GRANTSCOPE_DISCOVERY_TIMEOUT_SECONDS`    | Discovery run timeout                    | `5400`                                  |

#### Search Configuration

| Variable           | Description                                           | Default                                |
| ------------------ | ----------------------------------------------------- | -------------------------------------- |
| `SEARCH_PROVIDER`  | Search backend: `auto`, `searxng`, `serper`, `tavily` | `auto`                                 |
| `SEARXNG_BASE_URL` | SearXNG instance URL                                  | `http://searxng:8080` (Docker Compose) |
| `TAVILY_API_KEY`   | Tavily API key (paid search)                          | -                                      |
| `SERPER_API_KEY`   | Serper.dev API key (Google Search)                    | -                                      |
| `SAM_GOV_API_KEY`  | SAM.gov API key (grant data)                          | -                                      |

#### Security & Networking

| Variable                | Description                                   | Default                                       |
| ----------------------- | --------------------------------------------- | --------------------------------------------- |
| `ENVIRONMENT`           | `development` or `production` (controls CORS) | `development`                                 |
| `ALLOWED_ORIGINS`       | Comma-separated CORS origins                  | `http://localhost:3000,http://localhost:5173` |
| `TRUSTED_PROXY_COUNT`   | Reverse proxies for IP extraction             | `1`                                           |
| `RATE_LIMIT_PER_MINUTE` | Rate limit per IP                             | `100`                                         |
| `MAX_REQUEST_SIZE_MB`   | Maximum request body size                     | `10`                                          |
| `PORT`                  | Server port (set by Azure Container Apps)     | `8000`                                        |

#### Optional Integrations

| Variable            | Description                       | Default           |
| ------------------- | --------------------------------- | ----------------- |
| `FIRECRAWL_API_KEY` | Firecrawl web scraping API key    | -                 |
| `GAMMA_API_KEY`     | Gamma.app presentation generation | -                 |
| `GAMMA_API_ENABLED` | Enable Gamma integration          | `true` if key set |
| `COA_LOGO_URL`      | City of Austin logo for branding  | (built-in)        |

### Frontend Environment Variables (Build-Time)

These are baked into the Vite build output and must be set before `pnpm build`:

| Variable                 | Description                         | Example                                                          |
| ------------------------ | ----------------------------------- | ---------------------------------------------------------------- |
| `VITE_SUPABASE_URL`      | Supabase endpoint for auth and data | `https://your-project.supabase.co`                               |
| `VITE_SUPABASE_ANON_KEY` | Supabase anonymous/public key       | `eyJ...`                                                         |
| `VITE_API_URL`           | Backend API base URL                | `https://ca-grantscope2-api-prod.<region>.azurecontainerapps.io` |

---

## Health Checks & Monitoring

### Health Endpoint

The backend exposes a detailed health check at:

```
GET /api/v1/health
```

Response:

```json
{
  "status": "healthy",
  "timestamp": "2026-02-17T00:00:00+00:00",
  "services": {
    "database": "connected",
    "ai": "available",
    "search": {
      "provider": "searxng",
      "available": true
    }
  },
  "capabilities": [
    "ai_analysis",
    "search:searxng",
    "rss_feeds",
    "web_crawling",
    "tavily",
    "serper",
    "grants_gov_integration"
  ],
  "degraded": null,
  "mode": "full"
}
```

A root endpoint is also available:

```
GET /
```

Returns: `{"status": "ok", "message": "GrantScope2 API is running"}`

### Docker Health Check

The container includes an automatic health check configured in the Dockerfile:

| Setting      | Value                                            |
| ------------ | ------------------------------------------------ |
| Interval     | 30 seconds                                       |
| Timeout      | 10 seconds                                       |
| Start period | 60 seconds (allows for startup and font caching) |
| Retries      | 3                                                |

Check container health locally:

```bash
docker ps                    # Shows health status column
docker inspect --format='{{.State.Health.Status}}' grantscope-web
```

### Azure Container Apps Health Probes

Azure Container Apps uses the `/api/v1/health` endpoint for:

- **Liveness probes**: Restart containers that become unresponsive
- **Readiness probes**: Route traffic only to healthy instances
- **Startup probes**: Allow sufficient time for initial startup

The worker Container App also supports health checks when `PORT` is set (Azure provides this automatically), which enables the worker's built-in health server.

### Log Analytics

Container logs are streamed to the `log-grantscope2-prod` Log Analytics Workspace.

```bash
# View API container logs
az containerapp logs show \
  --name ca-grantscope2-api-prod \
  --resource-group rg-aph-cognitive-sandbox-dev-scus-01 \
  --follow

# View worker container logs
az containerapp logs show \
  --name ca-grantscope2-worker-prod \
  --resource-group rg-aph-cognitive-sandbox-dev-scus-01 \
  --follow
```

---

## Database Migrations

GrantScope2 uses two migration systems during the transition from Supabase to direct PostgreSQL:

### 1. Supabase Migrations (Legacy Schema)

SQL files in `supabase/migrations/` are applied with the `infra/migrate.sh` script. These are idempotent and safe to re-run.

```bash
# Local development
./infra/migrate.sh

# Azure PostgreSQL
./infra/migrate.sh "postgres://gsadmin:<password>@psql-grantscope2-prod.postgres.database.azure.com:5432/grantscope?sslmode=require"
```

### 2. Alembic Migrations (New Features)

SQLAlchemy models in `backend/app/models/db/` are managed by Alembic. The configuration is in `backend/alembic.ini` and reads `DATABASE_URL` from the environment.

```bash
cd backend

# Set connection string
export DATABASE_URL="postgresql+asyncpg://gsadmin:<password>@psql-grantscope2-prod.postgres.database.azure.com:5432/grantscope"

# Apply all pending migrations
alembic upgrade head

# Check current migration state
alembic current

# View migration history
alembic history

# Create a new migration (auto-detect model changes)
alembic revision -m "add_new_table" --autogenerate

# Roll back one migration
alembic downgrade -1
```

### Migration Order

When deploying to a fresh database:

1. Run `infra/init-db.sql` (handled automatically by Docker Compose, or run manually for Azure)
2. Apply Supabase migrations: `./infra/migrate.sh <connection-string>`
3. Apply Alembic migrations: `alembic upgrade head`

### Azure PostgreSQL: Enable pgvector

The pgvector extension must be enabled on the Azure PostgreSQL Flexible Server:

```bash
# Enable the extension (requires server restart)
az postgres flexible-server parameter set \
  --resource-group rg-aph-cognitive-sandbox-dev-scus-01 \
  --server-name psql-grantscope2-prod \
  --name azure.extensions \
  --value "VECTOR"

# Restart the server
az postgres flexible-server restart \
  --resource-group rg-aph-cognitive-sandbox-dev-scus-01 \
  --name psql-grantscope2-prod

# Then connect and create the extension
psql "postgres://gsadmin:<password>@psql-grantscope2-prod.postgres.database.azure.com:5432/grantscope?sslmode=require" \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

---

## Troubleshooting

### Container Won't Start

**Symptoms**: Container exits immediately or restarts in a loop.

**Check logs**:

```bash
# Docker Compose
docker compose logs -f grantscope-web
docker compose logs -f grantscope-worker

# Azure Container Apps
az containerapp logs show \
  --name ca-grantscope2-api-prod \
  --resource-group rg-aph-cognitive-sandbox-dev-scus-01 \
  --tail 100
```

**Common causes**:

- Missing or invalid `AZURE_OPENAI_*` environment variables
- `DATABASE_URL` connection string is wrong or database is unreachable
- Port 8000 already in use (local development)
- `SUPABASE_URL` or `SUPABASE_SERVICE_KEY` not set

### Health Check Failing

**Symptoms**: Container shows "unhealthy" status or returns non-200 from health endpoint.

**Verify the endpoint**:

```bash
curl -v http://localhost:8000/api/v1/health
```

**Check if the process is running**:

```bash
docker compose exec grantscope-web ps aux
```

**Check the health response for degraded services**:

```bash
curl -s http://localhost:8000/api/v1/health | python -m json.tool
# Look at the "degraded" and "mode" fields
```

### Azure Container Apps Not Pulling New Image

**Symptoms**: Deployment "succeeds" but the app still runs old code.

**Root cause**: Using `:latest` tag repeatedly. Azure caches the image digest and won't pull a new image if the tag name hasn't changed.

**Solution**: Always use unique version tags:

```bash
VERSION="1.0.0-$(date +%Y%m%d%H%M%S)"

az containerapp update \
  --name ca-grantscope2-api-prod \
  --resource-group rg-aph-cognitive-sandbox-dev-scus-01 \
  --image acrgrantscope2prod.azurecr.io/grantscope2:v${VERSION}
```

**Verify the new revision is active**:

```bash
az containerapp revision list \
  --name ca-grantscope2-api-prod \
  --resource-group rg-aph-cognitive-sandbox-dev-scus-01 \
  --query "[].{name:name, active:properties.active, traffic:properties.trafficWeight}" \
  -o table
```

### Azure Container Apps Cannot Pull Image (Auth Error)

**Symptoms**: Container App fails to start with image pull errors.

**Verify ACR access**:

```bash
# List images in registry
az acr repository list --name acrgrantscope2prod -o table

# Check managed identity has AcrPull role
az role assignment list \
  --scope /subscriptions/<sub-id>/resourceGroups/rg-aph-cognitive-sandbox-dev-scus-01/providers/Microsoft.ContainerRegistry/registries/acrgrantscope2prod \
  --query "[].{principal:principalName, role:roleDefinitionName}" \
  -o table
```

### Build Fails on Apple Silicon

**Symptoms**: Build produces ARM64 image or fails with architecture-related errors when deployed to Azure.

**Solution**: Always use `--platform linux/amd64` when building for Azure:

```bash
docker buildx build --platform linux/amd64 \
  -f backend/Dockerfile \
  -t acrgrantscope2prod.azurecr.io/grantscope2:v${VERSION} \
  --push .
```

### Worker Not Processing Jobs

**Symptoms**: Discovery runs, research tasks, or briefs stay in "queued" status.

**Check worker logs**:

```bash
# Local
docker compose logs -f grantscope-worker

# Azure
az containerapp logs show \
  --name ca-grantscope2-worker-prod \
  --resource-group rg-aph-cognitive-sandbox-dev-scus-01 \
  --follow
```

**Verify worker environment**:

- `GRANTSCOPE_PROCESS_TYPE` must be `worker`
- Worker needs the same database and API credentials as the API container
- Worker needs search access (`TAVILY_API_KEY`, `SERPER_API_KEY`, or `SEARXNG_BASE_URL`)

### Database Connection Refused (Azure PostgreSQL)

**Symptoms**: Application logs show connection timeout or SSL errors.

**Check firewall rules**:

```bash
az postgres flexible-server firewall-rule list \
  --resource-group rg-aph-cognitive-sandbox-dev-scus-01 \
  --name psql-grantscope2-prod \
  -o table
```

**Verify SSL mode**: Azure PostgreSQL requires SSL. Ensure your connection string includes `?sslmode=require` for psql or that your asyncpg driver is configured for SSL.

**Test connectivity**:

```bash
psql "postgres://gsadmin:<password>@psql-grantscope2-prod.postgres.database.azure.com:5432/grantscope?sslmode=require" \
  -c "SELECT version();"
```

### Environment Variables Not Loading

**Symptoms**: App starts but API calls fail or features are missing.

**Verify variables are set**:

```bash
# Docker Compose
docker compose exec grantscope-web env | grep -E '(AZURE|SUPABASE|DATABASE)'

# Azure Container Apps
az containerapp show \
  --name ca-grantscope2-api-prod \
  --resource-group rg-aph-cognitive-sandbox-dev-scus-01 \
  --query "properties.template.containers[0].env[].name" -o tsv
```

**Check `.env` file format**:

- Ensure no quotes around values (Docker Compose `.env` files should not quote values)
- Ensure no trailing whitespace
- Ensure the file uses Unix line endings (LF, not CRLF)

### Blob Storage Upload Fails

**Symptoms**: File attachments fail to upload with a 403 or connection error.

**Verify**:

- `AZURE_STORAGE_CONNECTION_STRING` is set and valid
- The `application-attachments` container exists in the storage account
- File size does not exceed 25 MB (`MAX_FILE_SIZE_BYTES`)

```bash
# Check if container exists
az storage container show \
  --name application-attachments \
  --account-name stgrantscope2prod \
  --auth-mode login
```

### Getting Help

1. Check container logs first (see commands above)
2. Review `backend/.env.example` for all available configuration options
3. Test the health endpoint (`/api/v1/health`) for service-level diagnostics
4. Open an issue on GitHub with:
   - Error messages from logs
   - Your deployment method (Docker Compose vs Azure)
   - Output of `/api/v1/health` endpoint
   - Relevant environment variables (redact secrets!)
