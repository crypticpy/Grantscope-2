# GrantScope2 - Security Architecture Document

**Document Version:** 1.0
**Last Updated:** February 2026
**Classification:** Internal Use Only
**Prepared For:** City Security Team - Production Audit Review

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Decision: Multi-Service](#2-architecture-decision-multi-service)
3. [System Architecture Overview](#3-system-architecture-overview)
4. [Container Security Architecture](#4-container-security-architecture)
5. [Azure Cloud Architecture](#5-azure-cloud-architecture)
6. [Security Controls](#6-security-controls)
7. [Data Flow and Privacy](#7-data-flow-and-privacy)
8. [Compliance Mapping](#8-compliance-mapping)
9. [Threat Model](#9-threat-model)
10. [Security Hardening Checklist](#10-security-hardening-checklist)
11. [Appendices](#11-appendices)

---

## 1. Executive Summary

### 1.1 Application Purpose

GrantScope2 is an AI-powered grant intelligence platform for the City of Austin. It automates discovery, analysis, tracking, and application support for grant opportunities, providing strategic alignment with Austin's priorities and the CMO's Top 25 goals. Unlike its predecessor (RTASS, a client-side-only transcription tool), GrantScope2 maintains a **full server-side database** containing sensitive grant application data, proposal content, budget information, and document attachments.

### 1.2 Key Security Highlights

| Security Aspect    | Implementation                                                     |
| ------------------ | ------------------------------------------------------------------ |
| Architecture       | Multi-service (frontend, API, worker, database, blob storage)      |
| Data Storage       | Server-side PostgreSQL + Azure Blob Storage (sensitive grant data) |
| Secrets Management | Azure Key Vault with RBAC and Managed Identity                     |
| Container Runtime  | Non-root user (UID 1000), Python 3.11-slim base                    |
| AI Services        | Azure OpenAI (GPT-4.1 for analysis, embeddings for search)         |
| Database Security  | PostgreSQL with RLS, SSL required, SQLAlchemy ORM                  |
| File Storage       | Azure Blob Storage with SAS tokens, extension/MIME validation      |
| API Security       | Rate limiting (slowapi), Pydantic validation, security headers     |
| Network Security   | HTTPS only (TLS 1.2+), CORS restricted to specific origins         |
| Monitoring         | Azure Log Analytics with centralized logging                       |

### 1.3 Attack Surface Summary

```
+------------------------------------------------------------------+
|                    ATTACK SURFACE ANALYSIS                        |
+------------------------------------------------------------------+
|                                                                   |
|  EXPANDED ATTACK SURFACE (vs. RTASS):                             |
|  - PostgreSQL database with sensitive grant data                  |
|  - Azure Blob Storage with document attachments                   |
|  - Multi-service communication (API <-> Worker <-> DB)            |
|  - File upload endpoint accepting user documents                  |
|  - Background worker processing long-running tasks                |
|                                                                   |
|  MITIGATIONS:                                                     |
|  - SQLAlchemy ORM prevents SQL injection (parameterized queries)  |
|  - File uploads validated (extension, MIME type, 25MB limit)      |
|  - Rate limiting on all endpoints, stricter on sensitive ones     |
|  - Pydantic models validate all request/response data             |
|  - Non-root containers with minimal capabilities                  |
|                                                                   |
|  EXTERNAL DEPENDENCIES:                                           |
|  - Azure OpenAI API (Microsoft-managed, SOC 2 compliant)         |
|  - Azure PostgreSQL Flexible Server (Microsoft-managed)           |
|  - Azure Blob Storage (Microsoft-managed)                         |
|  - Tavily, Firecrawl APIs (for deep research, optional)          |
|  - SearXNG (self-hosted search, optional)                         |
|                                                                   |
|  ENTRY POINTS:                                                    |
|  - HTTPS endpoint (port 443 via Static Web App)                   |
|  - API endpoint (port 8000 via Container App ingress)             |
|  - Health check endpoint (/api/v1/health)                         |
|                                                                   |
+------------------------------------------------------------------+
```

---

## 2. Architecture Decision: Multi-Service

### 2.1 Why We Chose Multi-Service Over Single Container

GrantScope2 uses a **multi-service architecture** with separate frontend, API, worker, and database tiers. This is a deliberate departure from the single-container approach used by RTASS, driven by fundamental differences in application requirements.

#### Why Single Container (RTASS) No Longer Works

| Requirement Change       | RTASS                 | GrantScope2                          |
| ------------------------ | --------------------- | ------------------------------------ |
| Data Persistence         | Client-side IndexedDB | Server-side PostgreSQL               |
| Background Processing    | None                  | Long-running discovery/research jobs |
| File Storage             | None                  | Azure Blob Storage (25MB documents)  |
| AI Processing Complexity | Single API call       | Multi-step pipelines with embeddings |
| Scaling Requirements     | Uniform               | API and Worker scale independently   |
| Data Sensitivity         | User-controlled       | Server-side sensitive grant data     |

#### Security Rationale for Multi-Service

| Benefit                     | Description                                                  |
| --------------------------- | ------------------------------------------------------------ |
| Isolation of Concerns       | Database, file storage, and compute are separate blast zones |
| Independent Scaling         | API handles requests; worker handles background jobs         |
| Defense in Depth            | Multiple security boundaries between internet and data       |
| Least Privilege per Service | API has DB access; worker has DB + external API access       |
| Separate Monitoring         | Each service has independent health checks and logging       |

#### Operational Rationale

| Benefit                     | Description                                             |
| --------------------------- | ------------------------------------------------------- |
| Zero-Downtime Deployments   | Frontend deploys independently from API                 |
| Worker Resilience           | Worker restarts don't affect API availability           |
| Resource Optimization       | Worker gets more CPU for AI tasks; API gets more memory |
| Independent Troubleshooting | Isolate issues to specific service without full restart |

#### Service Responsibilities

```
+------------------------------------------------------------------+
|                  SERVICE RESPONSIBILITY MATRIX                     |
+------------------------------------------------------------------+
|                                                                   |
|  STATIC WEB APP (Frontend)                                        |
|  - React 18 + TypeScript + Vite                                   |
|  - No server-side code, no secrets                                |
|  - All data via API calls to backend                              |
|                                                                   |
|  CONTAINER APP - API (Backend)                                     |
|  - FastAPI Python 3.11                                            |
|  - Request handling, validation, auth                             |
|  - Database CRUD via SQLAlchemy ORM                                |
|  - File upload/download orchestration                              |
|  - Real-time AI interactions (chat, classification)                |
|                                                                   |
|  CONTAINER APP - Worker (Background)                               |
|  - Same image, different entrypoint mode                           |
|  - Discovery pipeline execution                                   |
|  - Deep research tasks (gpt-researcher)                            |
|  - Executive brief generation                                      |
|  - Job timeout watchdog (configurable per job type)                |
|                                                                   |
|  POSTGRESQL (Data Tier)                                            |
|  - Persistent storage for all application data                     |
|  - pgvector extension for semantic search embeddings               |
|  - Row Level Security (RLS) policies                               |
|  - SSL-encrypted connections required                              |
|                                                                   |
|  BLOB STORAGE (File Tier)                                          |
|  - Grant application document attachments                          |
|  - UUID-based blob paths (no original filenames in paths)          |
|  - Time-limited SAS URLs for secure download                       |
|                                                                   |
+------------------------------------------------------------------+
```

---

## 3. System Architecture Overview

### 3.1 High-Level Architecture

```
+=========================================================================+
|                         AZURE CLOUD BOUNDARY                            |
+=========================================================================+
|                                                                         |
|  +-------------------------------------------------------------------+  |
|  |              AZURE STATIC WEB APP (swa-grantscope2-prod)          |  |
|  |                                                                   |  |
|  |  +-------------------------------------------------------------+  |  |
|  |  |  React 18 + TypeScript + Vite + TailwindCSS                 |  |  |
|  |  |  - No server-side code or secrets                           |  |  |
|  |  |  - All API calls to Container App backend                   |  |  |
|  |  |  - Azure-managed TLS and CDN                                |  |  |
|  |  +-------------------------------------------------------------+  |  |
|  +-------------------------------------------------------------------+  |
|                              |                                          |
|                              | HTTPS (TLS 1.2+)                         |
|                              v                                          |
|  +-------------------------------------------------------------------+  |
|  |      CONTAINER APPS ENVIRONMENT (cae-grantscope2-prod)            |  |
|  |                                                                   |  |
|  |  +----------------------------+ +-----------------------------+   |  |
|  |  |  API CONTAINER APP         | |  WORKER CONTAINER APP       |   |  |
|  |  |  (ca-grantscope2-api-prod) | |  (ca-grantscope2-worker-prod)|  |  |
|  |  |                            | |                             |   |  |
|  |  |  FastAPI + Gunicorn        | |  Background job processor   |   |  |
|  |  |  4 Uvicorn workers         | |  APScheduler (nightly/weekly)|  |  |
|  |  |  0.5 vCPU, 1Gi RAM        | |  Job timeout watchdog       |   |  |
|  |  |  Port 8000                 | |                             |   |  |
|  |  |                            | |                             |   |  |
|  |  |  User: appuser (UID 1000) | |  User: appuser (UID 1000)  |   |  |
|  |  +-------------+--------------+ +----------+------------------+   |  |
|  |                |                            |                     |  |
|  +----------------|----------------------------|---------------------+  |
|                   |                            |                        |
|       +-----------+----------------------------+-----------+            |
|       |           |                            |           |            |
|       v           v                            v           v            |
|  +-----------+ +-----------+ +-------------+ +-------------------+      |
|  | POSTGRESQL| | BLOB      | | AZURE       | | EXTERNAL APIs     |      |
|  | FLEXIBLE  | | STORAGE   | | OPENAI      | |                   |      |
|  | SERVER    | |           | |             | | - Tavily (search)  |      |
|  |           | | stgrant-  | | GPT-4.1     | | - Firecrawl       |      |
|  | psql-     | | scope2    | | GPT-4.1-mini| | - SearXNG          |      |
|  | grant-    | | prod      | | Embeddings  | | - Serper           |      |
|  | scope2-   | |           | |             | | - SAM.gov          |      |
|  | prod      | | Max 25MB  | |             | |                   |      |
|  |           | | per file  | |             | |                   |      |
|  | pgvector  | | SAS URLs  | |             | |                   |      |
|  | SSL req'd | |           | |             | |                   |      |
|  +-----------+ +-----------+ +-------------+ +-------------------+      |
|                                                                         |
|  +-------------------------------------------------------------------+  |
|  |  SUPPORTING SERVICES                                              |  |
|  |                                                                   |  |
|  |  +----------------+  +----------------+  +---------------------+  |  |
|  |  |   KEY VAULT    |  |  CONTAINER     |  |   LOG ANALYTICS     |  |  |
|  |  | kv-grantscope2 |  |  REGISTRY      |  | log-grantscope2     |  |  |
|  |  | -prd           |  | acrgrantscope2 |  | -prod               |  |  |
|  |  |                |  | prod           |  |                     |  |  |
|  |  | - API Keys     |  |                |  | - App logs          |  |  |
|  |  | - DB creds     |  | - Private      |  | - Container metrics |  |  |
|  |  | - Storage keys |  | - Vuln scan    |  | - Security alerts   |  |  |
|  |  | - RBAC access  |  | - Managed ID   |  | - 30-day retention  |  |  |
|  |  +----------------+  +----------------+  +---------------------+  |  |
|  +-------------------------------------------------------------------+  |
|                                                                         |
+=========================================================================+
                                    ^
                                    | HTTPS (TLS 1.2+)
                                    |
+=========================================================================+
|                           USER BROWSER                                  |
+=========================================================================+
|                                                                         |
|  +-------------------------------------------------------------------+  |
|  |  NO CLIENT-SIDE DATA PERSISTENCE                                  |  |
|  |                                                                   |  |
|  |  - All data stored server-side in PostgreSQL                      |  |
|  |  - Documents stored in Azure Blob Storage                         |  |
|  |  - Browser holds only session state and cached API responses      |  |
|  |  - Clearing browser does NOT delete user data                     |  |
|  +-------------------------------------------------------------------+  |
|                                                                         |
+=========================================================================+
```

### 3.2 Architecture Characteristics

| Characteristic   | Description                                             |
| ---------------- | ------------------------------------------------------- |
| Pattern          | Multi-service (frontend, API, worker, data tier)        |
| API Framework    | FastAPI (Python 3.11) with Pydantic validation          |
| Frontend         | React 18 + TypeScript + Vite + TailwindCSS              |
| Runtime          | Python 3.11-slim on Debian (backend), static (frontend) |
| Containerization | Two containers from single image (~500MB)               |
| Orchestration    | Azure Container Apps (API + Worker)                     |
| Frontend Hosting | Azure Static Web Apps (CDN-backed)                      |
| Database         | Azure PostgreSQL Flexible Server (Burstable B1ms)       |
| File Storage     | Azure Blob Storage (application-attachments container)  |
| Scaling          | API: horizontal (HTTP-based); Worker: single instance   |
| Data Persistence | Server-side PostgreSQL + Blob Storage                   |

### 3.3 AI Model Configuration

| Function        | Model                      | Purpose                        |
| --------------- | -------------------------- | ------------------------------ |
| Analysis/Chat   | GPT-4.1                    | Grant analysis, classification |
| Fast Operations | GPT-4.1-mini               | Quick summaries, triage        |
| Embeddings      | text-embedding-ada-002     | Semantic search, card matching |
| Deep Research   | GPT-4.1 via gpt-researcher | Comprehensive grant research   |

---

## 4. Container Security Architecture

### 4.1 Single-Stage Build Process

```
+=====================================================================+
|                      DOCKER BUILD PROCESS                           |
+=====================================================================+
|                                                                     |
|  BASE IMAGE: python:3.11-slim (Debian-based)                        |
|  +---------------------------------------------------------------+  |
|  |                                                               |  |
|  |  1. System Dependencies (as root)                             |  |
|  |     - gcc, g++ (build deps for native extensions)             |  |
|  |     - curl (health checks)                                    |  |
|  |     - apt cache cleaned after install                         |  |
|  |                                                               |  |
|  |  2. Create Non-Root User                                      |  |
|  |     - appgroup (GID 1000)                                     |  |
|  |     - appuser (UID 1000)                                      |  |
|  |                                                               |  |
|  |  3. Python Dependencies                                       |  |
|  |     - pip install --no-cache-dir (no pip cache in image)      |  |
|  |     - requirements.txt with pinned versions                   |  |
|  |                                                               |  |
|  |  4. Application Code                                          |  |
|  |     - COPY --chown=appuser:appgroup                           |  |
|  |     - Proper file ownership from build time                   |  |
|  |                                                               |  |
|  |  5. Switch to Non-Root User                                   |  |
|  |     - USER appuser                                            |  |
|  |     - All runtime operations as UID 1000                      |  |
|  |                                                               |  |
|  |  6. Entrypoint                                                |  |
|  |     - /app/entrypoint.sh                                      |  |
|  |     - Supports web/worker via GRANTSCOPE_PROCESS_TYPE         |  |
|  |                                                               |  |
|  +---------------------------------------------------------------+  |
|                                                                     |
|  SECURITY PROPERTIES:                                               |
|  [x] Non-root user (UID 1000, GID 1000)                            |
|  [x] No pip cache in final image                                    |
|  [x] Apt cache cleaned after install                                |
|  [x] Health checks enabled (curl-based)                             |
|  [x] Proper file ownership (COPY --chown)                           |
|  [x] PYTHONDONTWRITEBYTECODE=1 (no .pyc files)                     |
|  [x] PYTHONUNBUFFERED=1 (real-time logging)                        |
|                                                                     |
+=====================================================================+
```

### 4.2 Container Security Controls

| Control                 | Implementation                   | CIS Benchmark  |
| ----------------------- | -------------------------------- | -------------- |
| Non-root User           | User: appuser (UID 1000)         | CIS Docker 4.1 |
| Minimal Base Image      | python:3.11-slim (~120MB base)   | CIS Docker 4.2 |
| No Unnecessary Packages | Only gcc, g++, curl (build deps) | CIS Docker 4.4 |
| Cache Cleanup           | apt clean + rm apt lists         | CIS Docker 4.4 |
| Proper Ownership        | COPY --chown for app files       | CIS Docker 4.8 |
| Health Checks           | HTTP /api/v1/health endpoint     | Best Practice  |
| No .pyc Files           | PYTHONDONTWRITEBYTECODE=1        | Best Practice  |
| Unbuffered Logging      | PYTHONUNBUFFERED=1               | Best Practice  |

### 4.3 Dual-Mode Entrypoint

The same container image supports two runtime modes via the `GRANTSCOPE_PROCESS_TYPE` environment variable:

```
+=====================================================================+
|                    ENTRYPOINT CONFIGURATION                         |
+=====================================================================+
|                                                                     |
|  /app/entrypoint.sh (set -euo pipefail)                             |
|                                                                     |
|  GRANTSCOPE_PROCESS_TYPE=web (default)                              |
|  +---------------------------------------------------------------+  |
|  |  gunicorn app.main:app                                        |  |
|  |    --workers 4                                                |  |
|  |    --worker-class uvicorn.workers.UvicornWorker               |  |
|  |    --bind 0.0.0.0:${PORT:-8000}                               |  |
|  |    --timeout 120                                              |  |
|  |    --graceful-timeout 30                                      |  |
|  |    --keep-alive 5                                             |  |
|  |    --access-logfile - --error-logfile -                       |  |
|  +---------------------------------------------------------------+  |
|                                                                     |
|  GRANTSCOPE_PROCESS_TYPE=worker                                     |
|  +---------------------------------------------------------------+  |
|  |  python -m app.worker                                         |  |
|  |    - Polls for queued jobs                                    |  |
|  |    - Configurable poll interval                               |  |
|  |    - Per-job timeout watchdog                                 |  |
|  |    - Optional health server for liveness probes               |  |
|  +---------------------------------------------------------------+  |
|                                                                     |
|  SECURITY PROPERTIES:                                               |
|  - exec replaces shell (PID 1 signal handling)                     |  |
|  - set -euo pipefail (fail-fast on errors)                         |  |
|  - No shell injection (variables are trusted env vars)             |  |
|                                                                     |
+=====================================================================+
```

### 4.4 Production Image Contents

```
+=====================================================================+
|                    PRODUCTION IMAGE CONTENTS                        |
+=====================================================================+
|                                                                     |
|  /app                                                               |
|  |-- app/                                                           |
|  |   |-- main.py              # FastAPI application factory         |
|  |   |-- security.py          # Rate limiting, headers, middleware  |
|  |   |-- auth.py              # Authentication (hardcoded for MVP)  |
|  |   |-- database.py          # SQLAlchemy async engine             |
|  |   |-- storage.py           # Azure Blob Storage client           |
|  |   |-- worker.py            # Background job processor            |
|  |   |-- routers/             # API endpoint modules                |
|  |   |-- models/              # Pydantic + SQLAlchemy models        |
|  |   |-- services/            # Business logic layer                |
|  |   +-- source_fetchers/     # Content discovery fetchers          |
|  |-- branding/                # City of Austin logos for exports    |
|  |-- entrypoint.sh            # Dual-mode startup script            |
|  +-- requirements.txt         # Pinned Python dependencies          |
|                                                                     |
|  User:  appuser (UID 1000, GID 1000)                                |
|  Port:  8000                                                        |
|  Entry: /app/entrypoint.sh                                          |
|                                                                     |
+=====================================================================+
|                    EXCLUDED FROM IMAGE                               |
+=====================================================================+
|                                                                     |
|  [x] Frontend code (deployed separately to Static Web App)          |
|  [x] Test files and coverage reports                                |
|  [x] Environment files (.env*)                                      |
|  [x] Git history and configuration                                  |
|  [x] IDE configuration files                                        |
|  [x] Documentation and planning files                               |
|  [x] Infrastructure-as-Code templates                               |
|  [x] pip download cache (--no-cache-dir)                            |
|                                                                     |
+=====================================================================+
```

---

## 5. Azure Cloud Architecture

### 5.1 Resource Topology

```
+=========================================================================+
|                        AZURE RESOURCE GROUP                             |
|             (rg-aph-cognitive-sandbox-dev-scus-01) [shared]             |
+=========================================================================+
|                                                                         |
|  NETWORKING & ACCESS                                                    |
|  +-------------------------------------------------------------------+  |
|  |                                                                   |  |
|  |  Internet --> [Static Web App] --> SPA served via Azure CDN      |  |
|  |                                                                   |  |
|  |  Internet --> [Container App Ingress] --> API endpoints          |  |
|  |                     |                        |                    |  |
|  |                     v                        v                    |  |
|  |              +----------+            +---------------+            |  |
|  |              |   CORS   |            | TLS 1.2+      |            |  |
|  |              | Enforced |            | Auto-managed  |            |  |
|  |              +----------+            +---------------+            |  |
|  |                                                                   |  |
|  +-------------------------------------------------------------------+  |
|                                                                         |
|  COMPUTE LAYER                                                          |
|  +-------------------------------------------------------------------+  |
|  |                                                                   |  |
|  |  Container Apps Environment: cae-grantscope2-prod                 |  |
|  |  +-------------------------------------------------------------+  |  |
|  |  |                                                             |  |  |
|  |  |  API: ca-grantscope2-api-prod                               |  |  |
|  |  |  +-------------------+                                      |  |  |
|  |  |  | 0.5 vCPU, 1Gi RAM|  GRANTSCOPE_PROCESS_TYPE=web          |  |  |
|  |  |  | Port 8000         |  Gunicorn + 4 Uvicorn workers        |  |  |
|  |  |  | External ingress  |  Rate limiting, security headers     |  |  |
|  |  |  +-------------------+                                      |  |  |
|  |  |                                                             |  |  |
|  |  |  Worker: ca-grantscope2-worker-prod                         |  |  |
|  |  |  +-------------------+                                      |  |  |
|  |  |  | 0.5 vCPU, 1Gi RAM|  GRANTSCOPE_PROCESS_TYPE=worker       |  |  |
|  |  |  | No public ingress |  Discovery, research, briefs         |  |  |
|  |  |  | Health server opt.|  Job timeouts: 900s-5400s            |  |  |
|  |  |  +-------------------+                                      |  |  |
|  |  |                                                             |  |  |
|  |  +-------------------------------------------------------------+  |  |
|  |                                                                   |  |
|  +-------------------------------------------------------------------+  |
|                                                                         |
|  STATIC HOSTING                                                         |
|  +-------------------------------------------------------------------+  |
|  |                                                                   |  |
|  |  Static Web App: swa-grantscope2-prod                             |  |
|  |  - React 18 + TypeScript + Vite build                            |  |
|  |  - Azure CDN with global edge caching                            |  |
|  |  - No server-side code execution                                  |  |
|  |  - Auto TLS certificate management                               |  |
|  |                                                                   |  |
|  +-------------------------------------------------------------------+  |
|                                                                         |
|  DATA LAYER                                                             |
|  +-------------------------------------------------------------------+  |
|  |                                                                   |  |
|  |  +--------------------+  +-------------------+                    |  |
|  |  | PostgreSQL Flex    |  | Blob Storage      |                    |  |
|  |  | psql-grantscope2-  |  | stgrantscope2prod |                    |  |
|  |  | prod               |  |                   |                    |  |
|  |  |                    |  | Container:        |                    |  |
|  |  | Burstable B1ms     |  | application-      |                    |  |
|  |  | pgvector enabled   |  | attachments       |                    |  |
|  |  | SSL required       |  |                   |                    |  |
|  |  | RLS enabled        |  | 25MB max/file     |                    |  |
|  |  +--------------------+  +-------------------+                    |  |
|  |                                                                   |  |
|  +-------------------------------------------------------------------+  |
|                                                                         |
|  SUPPORTING SERVICES                                                    |
|  +-------------------------------------------------------------------+  |
|  |                                                                   |  |
|  |  +----------------+  +----------------+  +---------------------+  |  |
|  |  |   Key Vault    |  |  Container     |  |   Log Analytics     |  |  |
|  |  | kv-grantscope2 |  |  Registry      |  | log-grantscope2     |  |  |
|  |  | -prd           |  | acrgrantscope2 |  | -prod               |  |  |
|  |  |                |  | prod           |  |                     |  |  |
|  |  | - API Keys     |  |                |  | - App logs          |  |  |
|  |  | - DB creds     |  | - Private      |  | - Container metrics |  |  |
|  |  | - Storage keys |  | - Vuln scan    |  | - Security alerts   |  |  |
|  |  | - RBAC access  |  | - Managed ID   |  | - 30-day retention  |  |  |
|  |  +----------------+  +----------------+  +---------------------+  |  |
|  |                                                                   |  |
|  +-------------------------------------------------------------------+  |
|                                                                         |
|  IDENTITY & ACCESS (NO CREDENTIALS IN CODE)                             |
|  +-------------------------------------------------------------------+  |
|  |                                                                   |  |
|  |  System-Assigned Managed Identity (Container Apps)                |  |
|  |                                                                   |  |
|  |    [Container App] ---(AcrPull)--------> [Container Registry]     |  |
|  |    [Container App] ---(SecretsUser)----> [Key Vault]              |  |
|  |    [Container App] ---(Contributor)----> [PostgreSQL]             |  |
|  |    [Container App] ---(StorageBlob)----> [Blob Storage]           |  |
|  |                                                                   |  |
|  +-------------------------------------------------------------------+  |
|                                                                         |
+=========================================================================+
```

### 5.2 Managed Identity Authentication Flow

```
+=====================================================================+
|               MANAGED IDENTITY AUTHENTICATION FLOW                  |
+=====================================================================+
|                                                                     |
|  Container App (API or Worker)                                      |
|  +---------------------+                                            |
|  |                     |    1. Request token                        |
|  |   Application Code  |--------------------------------+           |
|  |                     |                                |           |
|  |   (NO credentials   |    2. Return token             v           |
|  |    stored in code)  |<-----------------------+  +----------+     |
|  |                     |                        |  |  Azure   |     |
|  +----------+----------+                        +--+  IMDS    |     |
|             |                                      +----------+     |
|             |                                                       |
|             | 3. Present token                                      |
|             |                                                       |
|    +--------v--------+    +------------------+    +-----------+     |
|    |                 |    |                  |    |           |     |
|    |   Key Vault     |    |  Container       |    | PostgreSQL|     |
|    |                 |    |  Registry        |    |           |     |
|    |  4. Validate    |    |                  |    | 4. Validate|    |
|    |  5. Return      |    |  4. Validate     |    | 5. Return |    |
|    |     secrets     |    |  5. Return image |    |    data   |    |
|    |                 |    |                  |    |           |     |
|    +-----------------+    +------------------+    +-----------+     |
|                                                                     |
|  SECURITY BENEFIT:                                                  |
|  - No credentials in code, config, or environment                   |
|  - Azure manages credential rotation automatically                  |
|  - No credential exposure risk in container image                   |
|  - Separate identity per service (API vs Worker)                    |
|                                                                     |
+=====================================================================+
```

### 5.3 Azure Resource Security Settings

| Resource             | Security Configuration                                         |
| -------------------- | -------------------------------------------------------------- |
| Container App API    | System-assigned managed identity, HTTPS only, external ingress |
| Container App Worker | System-assigned managed identity, no public ingress            |
| Static Web App       | Azure-managed TLS, CDN distribution, no server-side code       |
| Key Vault            | RBAC authorization, soft delete, purge protection              |
| Container Registry   | Private (no anon pull), managed identity auth, vuln scanning   |
| PostgreSQL           | SSL required, Burstable B1ms, Azure AD auth supported          |
| Blob Storage         | HTTPS-only, SAS tokens for download, no anonymous access       |
| Log Analytics        | 30-day retention, data encryption at rest                      |
| Container Env        | Consumption workload profile, Log Analytics linked             |

---

## 6. Security Controls

### 6.1 Network Security Layers

```
+=====================================================================+
|                      NETWORK SECURITY LAYERS                        |
+=====================================================================+
|                                                                     |
|  LAYER 1: EDGE PROTECTION                                           |
|  +---------------------------------------------------------------+  |
|  |  - HTTPS only (HTTP requests redirected)                      |  |
|  |  - TLS 1.2+ enforced (no legacy protocols)                    |  |
|  |  - Azure infrastructure DDoS protection                       |  |
|  |  - Static Web App CDN for frontend edge caching               |  |
|  +---------------------------------------------------------------+  |
|                                                                     |
|  LAYER 2: APPLICATION SECURITY HEADERS (SecurityHeadersMiddleware)  |
|  +---------------------------------------------------------------+  |
|  |  X-Frame-Options: DENY (clickjacking protection)              |  |
|  |  X-Content-Type-Options: nosniff                              |  |
|  |  X-XSS-Protection: 1; mode=block (legacy browser support)    |  |
|  |  Referrer-Policy: strict-origin-when-cross-origin             |  |
|  |  Permissions-Policy: accelerometer=(), camera=(),             |  |
|  |    geolocation=(), gyroscope=(), magnetometer=(),             |  |
|  |    microphone=(), payment=(), usb=()                          |  |
|  |  Strict-Transport-Security: max-age=31536000;                 |  |
|  |    includeSubDomains; preload (production only)               |  |
|  |  Cache-Control: no-store, no-cache, must-revalidate, private  |  |
|  |  X-Request-ID: {uuid} (audit trail per request)               |  |
|  +---------------------------------------------------------------+  |
|                                                                     |
|  LAYER 3: CORS POLICY (Strict, Environment-Aware)                   |
|  +---------------------------------------------------------------+  |
|  |  Production:                                                  |  |
|  |    - HTTPS origins only (HTTP rejected)                       |  |
|  |    - localhost/127.0.0.1 origins rejected                     |  |
|  |    - Default: https://grantscope2.vercel.app                  |  |
|  |    - Configurable via ALLOWED_ORIGINS env var                 |  |
|  |    - Origin validation: must start with https://              |  |
|  |                                                               |  |
|  |  Development:                                                 |  |
|  |    - Allows localhost origins for testing                     |  |
|  |    - Default: http://localhost:3000,5173,5174                 |  |
|  |                                                               |  |
|  |  Allowed Methods: GET, POST, PUT, DELETE, OPTIONS             |  |
|  |  Allowed Headers: Content-Type, Authorization, X-Request-ID   |  |
|  +---------------------------------------------------------------+  |
|                                                                     |
|  LAYER 4: RATE LIMITING (slowapi + per-IP tracking)                  |
|  +---------------------------------------------------------------+  |
|  |  Global: 100 requests/minute per IP (configurable)            |  |
|  |  Sensitive endpoints: 10 requests/minute                      |  |
|  |  Auth endpoints: 5 requests/minute                            |  |
|  |  Discovery/research: 3 requests/minute                        |  |
|  |                                                               |  |
|  |  IP Extraction: Anti-spoofing via rightmost-non-trusted       |  |
|  |  X-Forwarded-For approach (configurable proxy count)          |  |
|  |  IP validation before rate limit key assignment               |  |
|  +---------------------------------------------------------------+  |
|                                                                     |
|  LAYER 5: REQUEST VALIDATION                                         |
|  +---------------------------------------------------------------+  |
|  |  - Request body size limit: 10MB (configurable)               |  |
|  |  - Content-Length header validation                            |  |
|  |  - Pydantic model validation on all endpoints                 |  |
|  |  - File upload validation (extension, MIME, size)             |  |
|  +---------------------------------------------------------------+  |
|                                                                     |
+=====================================================================+
```

### 6.2 Secrets Management

| Secret                         | Storage Location | Access Method                |
| ------------------------------ | ---------------- | ---------------------------- |
| Azure OpenAI API Key           | Azure Key Vault  | Managed Identity + secretRef |
| Azure OpenAI Endpoint          | Azure Key Vault  | Managed Identity + secretRef |
| Database Connection String     | Azure Key Vault  | Managed Identity + secretRef |
| Blob Storage Connection String | Azure Key Vault  | Managed Identity + secretRef |
| Supabase Service Key           | Azure Key Vault  | Managed Identity + secretRef |
| Tavily API Key                 | Azure Key Vault  | Managed Identity + secretRef |
| Serper API Key                 | Azure Key Vault  | Managed Identity + secretRef |
| Container Registry             | Azure (Managed)  | System-assigned identity     |

**Security Properties:**

- No secrets in source code
- No secrets in container image
- No secrets in committed environment files (.env.example has placeholders only)
- Secrets retrieved at runtime via managed identity or Container App secret references
- Automatic credential rotation support
- Key Vault with soft delete and purge protection enabled

### 6.3 Application Security

| Control              | Implementation                                                 |
| -------------------- | -------------------------------------------------------------- |
| Input Validation     | Pydantic models for all API request/response types             |
| SQL Injection Prev.  | SQLAlchemy ORM with parameterized queries (no raw SQL)         |
| Error Handling       | Sanitized responses in production (no stack traces exposed)    |
| Logging              | Structured logs to Log Analytics (no PII, no query content)    |
| File Upload Security | Extension whitelist, MIME type validation, 25MB size limit     |
| Rate Limiting        | IP-based via slowapi with anti-spoofing protection             |
| Request ID Tracking  | UUID per request for audit trail correlation                   |
| Health Checks        | Liveness probes via /api/v1/health (30s interval)              |
| Dependency Security  | pip audit, pinned versions in requirements.txt                 |
| CORS                 | Origin whitelist, environment-aware (HTTPS-only in production) |

### 6.4 Database Security

| Control               | Implementation                                             |
| --------------------- | ---------------------------------------------------------- |
| Connection Encryption | SSL required for all connections (PostgreSQL Flexible)     |
| Query Safety          | SQLAlchemy ORM (parameterized queries, no string concat)   |
| Row Level Security    | RLS policies on tables for user-scoped data access         |
| Connection Pooling    | pool_size=10, max_overflow=20, pool_pre_ping=True          |
| Connection Recycling  | pool_recycle=300 (5 min) to prevent stale connections      |
| Session Management    | Auto-commit on success, rollback on exception              |
| Access Control        | Managed Identity or dedicated DB credentials via Key Vault |

### 6.5 File Upload Security

```
+=====================================================================+
|                    FILE UPLOAD SECURITY                              |
+=====================================================================+
|                                                                     |
|  VALIDATION PIPELINE (before any file touches Blob Storage):        |
|                                                                     |
|  Step 1: Extension Whitelist                                        |
|  +---------------------------------------------------------------+  |
|  |  Allowed: pdf, docx, doc, xlsx, xls, png, jpg, jpeg, txt     |  |
|  |  All other extensions: REJECTED (HTTP 400)                    |  |
|  +---------------------------------------------------------------+  |
|                                                                     |
|  Step 2: MIME Type Validation                                       |
|  +---------------------------------------------------------------+  |
|  |  Allowed MIME types:                                          |  |
|  |  - application/pdf                                            |  |
|  |  - application/vnd.openxmlformats-officedocument.*            |  |
|  |  - application/msword, application/vnd.ms-excel               |  |
|  |  - image/png, image/jpeg                                      |  |
|  |  - text/plain                                                 |  |
|  |  Mismatched extension/MIME: REJECTED (HTTP 400)               |  |
|  +---------------------------------------------------------------+  |
|                                                                     |
|  Step 3: Size Limit                                                 |
|  +---------------------------------------------------------------+  |
|  |  Maximum: 25 MB per file                                      |  |
|  |  Oversized files: REJECTED (HTTP 413)                         |  |
|  +---------------------------------------------------------------+  |
|                                                                     |
|  Step 4: Secure Storage                                             |
|  +---------------------------------------------------------------+  |
|  |  Blob path: applications/{app_id}/{uuid8}_{safe_filename}    |  |
|  |  - UUID prefix prevents path collision                        |  |
|  |  - Slashes/backslashes stripped from filename                 |  |
|  |  - Content-Type set explicitly on blob                        |  |
|  |  - Download via time-limited SAS URLs (1-hour expiry)         |  |
|  +---------------------------------------------------------------+  |
|                                                                     |
+=====================================================================+
```

### 6.6 Container Runtime Security

```yaml
# Security configuration applied to Container Apps
security:
  user: appuser (1000:1000) # Non-root user
  healthcheck:
    endpoint: /api/v1/health
    interval: 30s
    timeout: 10s
    start_period: 60s
    retries: 3

# Worker-specific security
worker:
  no_public_ingress: true # Worker not accessible from internet
  job_timeouts: # Per-job type watchdog
    brief: 1800s # 30 minutes
    discovery: 5400s # 90 minutes
    research_update: 900s # 15 minutes
    research_deep: 2700s # 45 minutes
```

---

## 7. Data Flow and Privacy

### 7.1 Data Flow Diagram

```
+=====================================================================+
|                         DATA FLOW DIAGRAM                           |
+=====================================================================+
|                                                                     |
|  USER BROWSER                                                       |
|  +---------------------------+                                      |
|  |                           |                                      |
|  |  1. User interacts with   |                                      |
|  |     GrantScope2 SPA       |                                      |
|  |     (React frontend)      |                                      |
|  |                           |                                      |
|  |  - Browse grant opps      |                                      |
|  |  - Create applications    |                                      |
|  |  - Upload documents       |                                      |
|  |  - Chat with AI           |                                      |
|  |  - View analytics         |                                      |
|  |                           |                                      |
|  +------------+--------------+                                      |
|               |                                                     |
|               | HTTPS (TLS 1.2+)                                    |
|               | JSON API requests                                   |
|               v                                                     |
|  +---------------------------+                                      |
|  |                           |                                      |
|  |  FASTAPI APPLICATION      |                                      |
|  |  (Container App - API)    |                                      |
|  |                           |                                      |
|  |  2. Request processing:   |                                      |
|  |     - CORS validation     |                                      |
|  |     - Rate limiting       |                                      |
|  |     - Auth validation     |                                      |
|  |     - Pydantic validation |                                      |
|  |     - Business logic      |                                      |
|  |                           |                                      |
|  +-----+------+------+------+                                      |
|        |      |      |                                              |
|        |      |      +---> Azure OpenAI                              |
|        |      |            - Grant analysis/classification           |
|        |      |            - Embedding generation                    |
|        |      |            - Chat completions                        |
|        |      |            - Data NOT retained by Azure OpenAI       |
|        |      |                                                      |
|        |      +----------> Azure Blob Storage                        |
|        |                   - Document upload/download                 |
|        |                   - SAS URL generation                      |
|        |                   - 25MB max per file                        |
|        |                                                             |
|        +-----------------> Azure PostgreSQL                          |
|                            - CRUD operations via SQLAlchemy          |
|                            - Parameterized queries only              |
|                            - SSL-encrypted connections               |
|                            - Data persisted server-side              |
|                                                                     |
|  +---------------------------+                                      |
|  |                           |                                      |
|  |  BACKGROUND WORKER        |                                      |
|  |  (Container App - Worker) |                                      |
|  |                           |                                      |
|  |  3. Async job execution:  |                                      |
|  |     - Discovery pipelines |----> External search APIs             |
|  |     - Deep research       |      (Tavily, Firecrawl, SearXNG)    |
|  |     - Brief generation    |                                      |
|  |     - Results written to  |----> PostgreSQL                       |
|  |       database            |----> Azure OpenAI (analysis)          |
|  |                           |                                      |
|  +---------------------------+                                      |
|                                                                     |
+=====================================================================+
```

### 7.2 Data Classification

| Data Type              | Classification | Storage Location      | Retention       |
| ---------------------- | -------------- | --------------------- | --------------- |
| Grant opportunity data | Internal       | PostgreSQL            | Ongoing         |
| Grant applications     | Sensitive      | PostgreSQL            | Ongoing         |
| Proposal content       | Sensitive      | PostgreSQL (JSONB)    | Ongoing         |
| Budget data            | Sensitive      | PostgreSQL            | Ongoing         |
| Document attachments   | Sensitive      | Azure Blob Storage    | User-controlled |
| User profiles          | Internal       | PostgreSQL            | Ongoing         |
| AI embeddings          | Internal       | PostgreSQL (pgvector) | Ongoing         |
| Chat conversations     | Internal       | PostgreSQL            | Ongoing         |
| Card/trend data        | Internal       | PostgreSQL            | Ongoing         |
| Workstream data        | Internal       | PostgreSQL            | Ongoing         |
| API keys/secrets       | Secret         | Azure Key Vault       | Managed         |
| Application logs       | Operational    | Log Analytics         | 30 days         |

### 7.3 Critical Difference from RTASS: Server-Side Data

```
+=====================================================================+
|          DATA STORAGE: RTASS vs. GRANTSCOPE2                        |
+=====================================================================+
|                                                                     |
|  RTASS (Previous Application):                                      |
|  +---------------------------------------------------------------+  |
|  |  - ALL data stored client-side in browser IndexedDB           |  |
|  |  - Server had NO persistent storage                           |  |
|  |  - Clearing browser deleted all data                          |  |
|  |  - No server-side data breach risk                            |  |
|  |  - User fully controlled their data                           |  |
|  +---------------------------------------------------------------+  |
|                                                                     |
|  GRANTSCOPE2 (Current Application):                                 |
|  +---------------------------------------------------------------+  |
|  |  - ALL data stored SERVER-SIDE in PostgreSQL + Blob Storage   |  |
|  |  - Database contains SENSITIVE grant application data         |  |
|  |  - Proposal narratives, budget details, organization info     |  |
|  |  - Document attachments in Azure Blob Storage                 |  |
|  |  - Data persists regardless of browser state                  |  |
|  |                                                               |  |
|  |  SECURITY IMPLICATIONS:                                       |  |
|  |  - Database breach = exposure of sensitive grant data         |  |
|  |  - SQL injection prevention is CRITICAL (SQLAlchemy ORM)      |  |
|  |  - Database access controls must be enforced (RLS, SSL)       |  |
|  |  - Blob storage access must be controlled (SAS tokens)        |  |
|  |  - Backup and disaster recovery planning required             |  |
|  |  - Data retention policies needed for compliance              |  |
|  +---------------------------------------------------------------+  |
|                                                                     |
+=====================================================================+
```

### 7.4 PII and Sensitive Data Handling

Grant applications may contain Personally Identifiable Information (PII) and sensitive organizational data:

| PII/Sensitive Data Type          | Where Stored       | Protection                           |
| -------------------------------- | ------------------ | ------------------------------------ |
| Applicant names and contact info | PostgreSQL         | Database encryption at rest, RLS     |
| Organization details             | PostgreSQL         | Database encryption at rest, RLS     |
| Budget and financial data        | PostgreSQL (JSONB) | Database encryption at rest, RLS     |
| Proposal narratives              | PostgreSQL (JSONB) | Database encryption at rest, RLS     |
| Supporting documents             | Azure Blob Storage | Encryption at rest, SAS token access |
| User email addresses             | PostgreSQL         | Database encryption at rest          |

**PII Protection Measures:**

1. **Encryption at Rest**: Azure PostgreSQL and Blob Storage encrypt data at rest by default
2. **Encryption in Transit**: SSL required for all database connections; HTTPS for all API traffic
3. **Access Control**: Database credentials stored in Key Vault; SAS tokens for blob access
4. **Logging Protection**: Application logs do not contain grant content, proposal text, or PII
5. **AI Processing**: Azure OpenAI does NOT retain data after processing (SOC 2, ISO 27001)

### 7.5 Azure OpenAI Data Handling

When using Azure OpenAI (all AI processing routes through Azure-managed endpoints):

| Aspect         | Policy                               |
| -------------- | ------------------------------------ |
| Training Data  | NOT used to train or improve models  |
| Data Retention | NOT retained after processing        |
| Compliance     | SOC 2, ISO 27001, HIPAA eligible     |
| Data Residency | Processed in configured Azure region |

**What IS sent to Azure OpenAI:**

- Grant opportunity text for analysis and classification
- Proposal content for AI-assisted editing
- Card descriptions for embedding generation
- Chat messages for conversational AI responses

**What is NOT sent to Azure OpenAI:**

- Database credentials or API keys
- User authentication tokens
- Raw document files (only extracted text content)
- Application logs or system metadata

### 7.6 External API Data Flow

GrantScope2 integrates with external APIs for deep research and discovery:

| External API | Data Sent                    | Data Received               | Risk Level |
| ------------ | ---------------------------- | --------------------------- | ---------- |
| Tavily       | Search queries (topic-based) | Web content summaries       | Low        |
| Firecrawl    | URLs to crawl                | Extracted web page content  | Low        |
| SearXNG      | Search queries               | Search result URLs/snippets | Low        |
| Serper       | Search queries               | Google search results       | Low        |
| SAM.gov      | Grant opportunity queries    | Federal grant listings      | Low        |

**Mitigation:** No sensitive grant application data, PII, or user data is sent to external search APIs. Only topic-based search queries are transmitted.

---

## 8. Compliance Mapping

### 8.1 OWASP Top 10 (2021) Mapping

| OWASP Risk                     | Mitigation                                                                | Status    |
| ------------------------------ | ------------------------------------------------------------------------- | --------- |
| A01: Broken Access Control     | Hardcoded auth (MVP); Entra ID planned; RLS on database                   | Partial   |
| A02: Cryptographic Failures    | TLS 1.2+, Key Vault for secrets, PostgreSQL SSL required                  | Mitigated |
| A03: Injection                 | SQLAlchemy ORM (parameterized queries), Pydantic validation               | Mitigated |
| A04: Insecure Design           | Security headers, file upload validation, rate limiting                   | Mitigated |
| A05: Security Misconfiguration | Environment-aware CORS, Key Vault secrets, no defaults in production      | Mitigated |
| A06: Vulnerable Components     | Pinned requirements.txt, pip audit, Python 3.11-slim base                 | Mitigated |
| A07: Auth Failures             | Rate limiting on auth endpoints (5/min), Key Vault for API keys           | Partial   |
| A08: Data Integrity            | HTTPS only, Pydantic input validation, SQLAlchemy ORM                     | Mitigated |
| A09: Logging Failures          | Structured logging to Log Analytics, request ID tracking                  | Mitigated |
| A10: SSRF                      | External API calls use configured endpoints only, no user-controlled URLs | Mitigated |

**Note on A01 and A07 (Partial):** The current MVP uses hardcoded authentication for single-tester use. Production deployment requires migration to Microsoft Entra ID for proper authentication and authorization. This is the highest-priority security enhancement planned.

### 8.2 CIS Docker Benchmark Mapping

| CIS Control                         | Implementation                         | Status |
| ----------------------------------- | -------------------------------------- | ------ |
| 4.1 Create user for container       | User: appuser (UID 1000)               | Pass   |
| 4.2 Use trusted base images         | python:3.11-slim (Official Docker Hub) | Pass   |
| 4.3 Install necessary packages only | gcc, g++, curl (build deps only)       | Pass   |
| 4.4 Scan and rebuild for patches    | apt-get upgrade in Dockerfile          | Pass   |
| 4.5 Enable Content Trust            | Configurable in registry               | Note   |
| 4.8 Set filesystem ownership        | COPY --chown=appuser:appgroup          | Pass   |
| 5.3 Restrict Linux capabilities     | Container Apps managed                 | Note   |
| 5.12 Mount filesystem read-only     | Supported via orchestrator             | Note   |
| 5.25 Restrict privilege escalation  | Non-root user enforced                 | Pass   |
| 5.28 Use PIDs cgroup limit          | Container Apps managed                 | Pass   |

### 8.3 NIST Cybersecurity Framework

| Function | Category               | Implementation                                           |
| -------- | ---------------------- | -------------------------------------------------------- |
| Identify | Asset Management       | Azure resource group with tagged resources               |
| Identify | Risk Assessment        | STRIDE threat model, data classification table           |
| Protect  | Access Control         | Managed Identity, RBAC, Key Vault, rate limiting         |
| Protect  | Data Security          | TLS, PostgreSQL SSL, Blob encryption, RLS                |
| Protect  | Information Protection | File upload validation, Pydantic schemas, ORM            |
| Detect   | Continuous Monitoring  | Log Analytics, health checks, request ID tracking        |
| Detect   | Security Events        | Auth failure logging, rate limit violation logging       |
| Respond  | Response Planning      | Centralized logging for investigation, audit trail       |
| Recover  | Recovery Planning      | Database backups (Azure-managed), container redeployment |

---

## 9. Threat Model

### 9.1 STRIDE Analysis

| Threat                 | Risk   | Mitigation                                                         |
| ---------------------- | ------ | ------------------------------------------------------------------ |
| Spoofing               | Medium | Hardcoded auth (MVP); Entra ID planned; IP-based rate limiting     |
| Tampering              | Medium | TLS encryption, Pydantic validation, SQLAlchemy ORM                |
| Repudiation            | Low    | Structured logging, request ID tracking, Log Analytics             |
| Information Disclosure | High   | Key Vault, RLS, SSL, no PII in logs, SAS token expiry              |
| Denial of Service      | Medium | Rate limiting (3 tiers), Azure DDoS protection, request size limit |
| Elevation of Privilege | Low    | Non-root container, database RLS, no admin API exposed             |

### 9.2 Attack Vectors and Mitigations

```
+=====================================================================+
|                      ATTACK SURFACE ANALYSIS                        |
+=====================================================================+
|                                                                     |
|  EXTERNAL ATTACK VECTORS                                            |
|  +---------------------------------------------------------------+  |
|  |                                                               |  |
|  |  [Internet] --> [API Endpoint]                                |  |
|  |                        |                                      |  |
|  |                        +-- SQL Injection                      |  |
|  |                        |   Mitigation: SQLAlchemy ORM with    |  |
|  |                        |   parameterized queries. No raw SQL  |  |
|  |                        |   with user input anywhere in code.  |  |
|  |                        |                                      |  |
|  |                        +-- File Upload Attack                 |  |
|  |                        |   Mitigation: Extension whitelist    |  |
|  |                        |   (9 types), MIME validation, 25MB   |  |
|  |                        |   limit, UUID-based blob paths       |  |
|  |                        |                                      |  |
|  |                        +-- API Abuse / DDoS                   |  |
|  |                        |   Mitigation: 3-tier rate limiting   |  |
|  |                        |   (100/10/5/3 per min), request size |  |
|  |                        |   limit (10MB), Azure DDoS           |  |
|  |                        |                                      |  |
|  |                        +-- XSS Attack                         |  |
|  |                        |   Mitigation: Security headers,      |  |
|  |                        |   React auto-escaping, X-Content-    |  |
|  |                        |   Type-Options: nosniff              |  |
|  |                        |                                      |  |
|  |                        +-- CSRF Attack                        |  |
|  |                        |   Mitigation: CORS policy, no        |  |
|  |                        |   session cookies (token-based auth) |  |
|  |                        |                                      |  |
|  |                        +-- Auth Bypass                        |  |
|  |                        |   Mitigation: MVP uses hardcoded     |  |
|  |                        |   auth (known limitation). Entra ID  |  |
|  |                        |   planned for production.            |  |
|  |                        |                                      |  |
|  |                        +-- Path Traversal (File Upload)       |  |
|  |                            Mitigation: Filenames sanitized    |  |
|  |                            (slashes stripped), UUID prefix,   |  |
|  |                            blob path constructed server-side  |  |
|  |                                                               |  |
|  +---------------------------------------------------------------+  |
|                                                                     |
|  DATABASE ATTACK VECTORS                                            |
|  +---------------------------------------------------------------+  |
|  |                                                               |  |
|  |  [API/Worker] --> [PostgreSQL]                                |  |
|  |                        |                                      |  |
|  |                        +-- SQL Injection (Primary Risk)       |  |
|  |                        |   Mitigation: SQLAlchemy ORM         |  |
|  |                        |   exclusively. All queries use       |  |
|  |                        |   parameterized statements.          |  |
|  |                        |   No string concatenation for SQL.   |  |
|  |                        |                                      |  |
|  |                        +-- Unauthorized Data Access           |  |
|  |                        |   Mitigation: RLS policies, SSL      |  |
|  |                        |   required, Key Vault credentials    |  |
|  |                        |                                      |  |
|  |                        +-- Connection Pool Exhaustion         |  |
|  |                            Mitigation: pool_size=10,          |  |
|  |                            max_overflow=20, pool_pre_ping,    |  |
|  |                            pool_recycle=300s                  |  |
|  |                                                               |  |
|  +---------------------------------------------------------------+  |
|                                                                     |
|  INTERNAL ATTACK VECTORS                                            |
|  +---------------------------------------------------------------+  |
|  |                                                               |  |
|  |  [Container] --> [Azure Resources]                            |  |
|  |                        |                                      |  |
|  |                        +-- Credential Theft                   |  |
|  |                        |   Mitigation: Managed ID (no creds   |  |
|  |                        |   in code), Key Vault for runtime    |  |
|  |                        |                                      |  |
|  |                        +-- Container Escape                   |  |
|  |                        |   Mitigation: Non-root user, Azure   |  |
|  |                        |   Container Apps managed isolation   |  |
|  |                        |                                      |  |
|  |                        +-- Lateral Movement                   |  |
|  |                        |   Mitigation: Each service has       |  |
|  |                        |   scoped permissions; worker has no  |  |
|  |                        |   public ingress                     |  |
|  |                        |                                      |  |
|  |                        +-- Blob Storage Unauthorized Access   |  |
|  |                            Mitigation: SAS tokens with 1-hour |  |
|  |                            expiry, no anonymous access,       |  |
|  |                            connection string in Key Vault     |  |
|  |                                                               |  |
|  +---------------------------------------------------------------+  |
|                                                                     |
|  SUPPLY CHAIN ATTACK VECTORS                                        |
|  +---------------------------------------------------------------+  |
|  |                                                               |  |
|  |  [pip packages] --> [Build Process]                           |  |
|  |                           |                                   |  |
|  |                           +-- Malicious Dependency            |  |
|  |                           |   Mitigation: pip audit, pinned   |  |
|  |                           |   requirements.txt, no wildcard   |  |
|  |                           |                                   |  |
|  |                           +-- Compromised Base Image          |  |
|  |                           |   Mitigation: Official Python     |  |
|  |                           |   3.11-slim from Docker Hub       |  |
|  |                           |                                   |  |
|  |                           +-- Build Injection                 |  |
|  |                               Mitigation: GitHub Actions CI,  |  |
|  |                               ACR vulnerability scanning      |  |
|  |                                                               |  |
|  +---------------------------------------------------------------+  |
|                                                                     |
+=====================================================================+
```

### 9.3 Risk Prioritization

| Risk Area                 | Severity | Likelihood | Priority | Status                 |
| ------------------------- | -------- | ---------- | -------- | ---------------------- |
| Auth bypass (hardcoded)   | High     | High (MVP) | Critical | Entra ID planned       |
| SQL injection             | Critical | Low        | High     | Mitigated (ORM)        |
| File upload malware       | High     | Medium     | High     | Mitigated (validation) |
| Database credential leak  | Critical | Low        | High     | Mitigated (Key Vault)  |
| API abuse / scraping      | Medium   | Medium     | Medium   | Mitigated (rate limit) |
| Blob storage unauthorized | High     | Low        | Medium   | Mitigated (SAS)        |
| Supply chain compromise   | High     | Low        | Medium   | Mitigated (auditing)   |
| Container escape          | Critical | Very Low   | Low      | Mitigated (non-root)   |

---

## 10. Security Hardening Checklist

### 10.1 Pre-Deployment Checklist

| Item                                                              | Required | Status |
| ----------------------------------------------------------------- | -------- | ------ |
| pip audit shows no high/critical vulnerabilities                  | Yes      | [ ]    |
| All secrets stored in Key Vault (no env vars with real values)    | Yes      | [ ]    |
| CORS policy restricted to production frontend URL only            | Yes      | [x]    |
| Security headers middleware enabled                               | Yes      | [x]    |
| Rate limiting configured and tested                               | Yes      | [x]    |
| Container runs as non-root user (appuser, UID 1000)               | Yes      | [x]    |
| Health check endpoints configured and responding                  | Yes      | [x]    |
| PostgreSQL SSL required (reject plaintext connections)            | Yes      | [ ]    |
| Database RLS policies applied on all user-facing tables           | Yes      | [ ]    |
| Blob Storage container set to private (no anonymous access)       | Yes      | [ ]    |
| TLS certificate valid and auto-renewed (Static Web App)           | Yes      | [ ]    |
| Log Analytics workspace configured and receiving logs             | Yes      | [ ]    |
| File upload validation tested (bad extension, bad MIME, oversize) | Yes      | [x]    |
| Production CORS rejects HTTP and localhost origins                | Yes      | [x]    |
| Error responses sanitized (no stack traces in production)         | Yes      | [x]    |
| Worker container has no public ingress                            | Yes      | [ ]    |
| Request size limit configured (10MB default)                      | Yes      | [x]    |

### 10.2 Authentication Migration Checklist (Pre-Production)

| Item                                                 | Required | Status |
| ---------------------------------------------------- | -------- | ------ |
| Replace hardcoded auth with Microsoft Entra ID       | Yes      | [ ]    |
| JWT token validation on all API endpoints            | Yes      | [ ]    |
| Role-based access control (RBAC) for admin endpoints | Yes      | [ ]    |
| Token refresh mechanism implemented                  | Yes      | [ ]    |
| Session management (token expiry, revocation)        | Yes      | [ ]    |
| Auth failure logging and monitoring alerts           | Yes      | [x]    |

### 10.3 Production Configuration Recommendations

```
# Key Vault - enable purge protection
enablePurgeProtection: true

# PostgreSQL - enforce SSL
ssl_enforcement: 'Enabled'
ssl_min_version: 'TLSv1.2'

# Blob Storage - disable anonymous access
allow_blob_public_access: false

# Container Registry - Premium for security features
sku: 'Premium'

# Log Analytics - extend retention for compliance
retentionInDays: 90

# Container App (Worker) - no external ingress
ingress: null  # Worker communicates only via database
```

### 10.4 Optional Security Enhancements

| Enhancement            | Description                                                 | Priority |
| ---------------------- | ----------------------------------------------------------- | -------- |
| Microsoft Entra ID     | Replace hardcoded auth with enterprise SSO                  | Critical |
| Azure Front Door + WAF | Edge protection, DDoS mitigation, bot detection             | High     |
| Private Endpoints      | Remove public network access to PostgreSQL and Blob Storage | High     |
| VNet Integration       | Network isolation for Container Apps Environment            | Medium   |
| Azure Defender         | Threat detection for containers and databases               | Medium   |
| Egress Firewall Rules  | Restrict outbound to Azure OpenAI, search APIs only         | Medium   |
| Database Audit Logging | PostgreSQL pgaudit extension for query-level audit          | Medium   |
| Image Signing          | Container image verification via Docker Content Trust       | Low      |
| Customer-Managed Keys  | CMK for PostgreSQL and Blob Storage encryption              | Low      |

---

## 11. Appendices

### 11.1 Glossary

| Term                | Definition                                                    |
| ------------------- | ------------------------------------------------------------- |
| Container App       | Azure's serverless container hosting service                  |
| Managed Identity    | Azure AD identity for resources (no credentials needed)       |
| Static Web App      | Azure's hosting service for static frontend applications      |
| PostgreSQL Flexible | Azure-managed PostgreSQL with flexible scaling options        |
| pgvector            | PostgreSQL extension for vector similarity search             |
| Row Level Security  | PostgreSQL feature restricting row access by user/role        |
| SQLAlchemy          | Python SQL toolkit and ORM for parameterized queries          |
| Pydantic            | Python data validation library using type annotations         |
| FastAPI             | Modern Python web framework for building APIs                 |
| SAS Token           | Shared Access Signature for time-limited Azure Blob access    |
| slowapi             | Python rate limiting library for FastAPI/Starlette            |
| gpt-researcher      | Open-source AI research agent for deep web research           |
| Entra ID            | Microsoft's identity and access management service (Azure AD) |

### 11.2 File References

| File                                        | Purpose                                |
| ------------------------------------------- | -------------------------------------- |
| /backend/Dockerfile                         | Container build definition             |
| /backend/entrypoint.sh                      | Dual-mode startup script (web/worker)  |
| /backend/requirements.txt                   | Pinned Python dependencies             |
| /backend/app/main.py                        | FastAPI application factory with CORS  |
| /backend/app/security.py                    | Rate limiting, headers, error handling |
| /backend/app/auth.py                        | Authentication (hardcoded MVP)         |
| /backend/app/database.py                    | SQLAlchemy async engine configuration  |
| /backend/app/storage.py                     | Azure Blob Storage client              |
| /backend/app/services/attachment_service.py | File upload validation logic           |
| /backend/.env.example                       | Environment variable template          |

### 11.3 Contact Information

| Role                | Contact        |
| ------------------- | -------------- |
| Application Owner   | [To be filled] |
| Security Contact    | [To be filled] |
| Infrastructure Team | [To be filled] |

---

## Document Approval

| Role                | Name | Date | Signature |
| ------------------- | ---- | ---- | --------- |
| Application Owner   |      |      |           |
| Security Reviewer   |      |      |           |
| Infrastructure Lead |      |      |           |

---

_This document should be reviewed and updated with each major release or infrastructure change._
