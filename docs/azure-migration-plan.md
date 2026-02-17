# GrantScope2: Azure Infrastructure Migration Plan

**Project:** GrantScope2 — AI-Powered Strategic Horizon Scanning System
**Owner:** City of Austin, Office of Innovation
**Date:** February 2026
**Status:** Draft

---

## 1. Current Architecture

```
                          Internet
                             |
                     +-------+-------+
                     |   Vercel CDN  |
                     | (React + Vite)|
                     +-------+-------+
                             |
              +--------------+--------------+
              |                             |
    +---------+---------+     +-------------+------------+
    |   Railway          |     |   Supabase               |
    |  - FastAPI (API)   |     |  - PostgreSQL + pgvector |
    |  - Background      |     |  - Auth (JWT)            |
    |    Worker           |     |  - Row-Level Security    |
    +---------+---------+     +-------------+------------+
              |                             |
    +---------+---------+                   |
    |  Self-Hosted Libs  |                  |
    |  - GPT Researcher  |                  |
    |  - trafilatura     |                  |
    +-------------------+                   |
              |                             |
    +---------+-----------------------------+
    |          Azure OpenAI (City Infra)    |
    |  - GPT-4.1 (analysis, scoring)       |
    |  - text-embedding-3-large            |
    +---------+-----------------------------+
              |
    +---------+---------+
    |  Serper.dev        |
    |  ($1/1K queries)   |
    +-------------------+
```

**Key points:**

- Railway hosts both the API server and the async background worker as separate services.
- Supabase provides PostgreSQL with pgvector for semantic search, plus JWT-based authentication.
- Azure OpenAI is already on city infrastructure -- no migration needed.
- Serper.dev is the only remaining paid external API ($1 per 1,000 queries).
- trafilatura and GPT Researcher run in-process within the worker (no external service).

---

## 2. Target Architecture

```
                          Internet
                             |
                   +---------+---------+
                   | Azure Front Door  |
                   | + WAF             |
                   +---------+---------+
                             |
              +--------------+--------------+
              |                             |
    +---------+---------+     +-------------+------------+
    | Azure Container   |     | Azure Static Web Apps    |
    | Apps Environment  |     | (React + Vite frontend)  |
    |                   |     +--------------------------+
    | - api (FastAPI)   |
    | - worker (async)  |
    +---------+---------+
              |
    +---------+-----------------------------+
    |          Azure VNet (Private)         |
    |                                       |
    |  +----------------------------------+ |
    |  | Azure DB for PostgreSQL          | |
    |  | Flexible Server + pgvector       | |
    |  +----------------------------------+ |
    |                                       |
    |  +----------------------------------+ |
    |  | Azure Blob Storage               | |
    |  | (PDF/PPTX exports, assets)       | |
    |  +----------------------------------+ |
    |                                       |
    |  +----------------------------------+ |
    |  | Azure Key Vault                  | |
    |  | (secrets, connection strings)    | |
    |  +----------------------------------+ |
    +---------------------------------------+
              |
    +---------+-----------------------------+
    |  Azure OpenAI (already provisioned)  |
    +---------------------------------------+
              |
    +---------+-----------------------------+
    |  Azure AD / Entra ID (SSO)           |
    |  - City employee authentication      |
    |  - RBAC via JWT claims               |
    +---------------------------------------+
              |
    +---------+---------+
    |  Azure App        |
    |  Insights         |
    |  (monitoring)     |
    +-------------------+
```

**Services:**

| Component         | Azure Service                           | SKU / Tier                      |
| ----------------- | --------------------------------------- | ------------------------------- |
| API Server        | Container Apps                          | Consumption (serverless)        |
| Background Worker | Container Apps                          | Consumption (serverless)        |
| Database          | Azure DB for PostgreSQL Flexible Server | Burstable B1ms (2 vCores, 4 GB) |
| Vector Search     | pgvector extension on Azure PostgreSQL  | Included                        |
| Auth / SSO        | Azure AD (Entra ID)                     | City tenant (existing)          |
| Secrets           | Azure Key Vault                         | Standard                        |
| Object Storage    | Azure Blob Storage                      | Hot tier                        |
| CDN / WAF         | Azure Front Door                        | Standard                        |
| Monitoring        | Application Insights                    | Pay-as-you-go                   |
| Frontend          | Azure Static Web Apps                   | Free or Standard                |

---

## 3. Migration Phases

### Phase 1 -- Compute Migration (Railway to Azure Container Apps)

**Goal:** Move API and worker off Railway while keeping Supabase as the database temporarily.

**Steps:**

1. **Create Dockerfiles** for the API and worker processes:
   - `Dockerfile.api` -- runs `uvicorn app.main:app`
   - `Dockerfile.worker` -- runs `python -m app.worker`
   - Both share the same image, different entrypoints.

2. **Provision Azure Container Apps Environment:**
   - Create resource group `rg-grantscope-prod`.
   - Create Container Apps Environment with VNet integration.
   - Configure environment variables and secrets from Key Vault.

3. **Deploy containers:**
   - Push images to Azure Container Registry (ACR).
   - Create two Container Apps: `grantscope-api` (ingress enabled, port 8000) and `grantscope-worker` (no ingress, internal only).
   - Configure scaling rules (min 1 replica for API, 0-1 for worker).

4. **Networking and DNS:**
   - Point custom domain to Container Apps ingress.
   - Update frontend `VITE_API_URL` to new endpoint.
   - Configure CORS for the new domain.

5. **Validate:**
   - Run health checks against the new API.
   - Trigger a discovery run to confirm the worker processes jobs.
   - Monitor for 48 hours before decommissioning Railway.

6. **Decommission Railway.**

**Duration:** 1-2 weeks.

---

### Phase 2 -- Database Migration (Supabase to Azure PostgreSQL)

**Goal:** Move PostgreSQL and pgvector data to Azure-managed PostgreSQL.

**Steps:**

1. **Provision Azure DB for PostgreSQL Flexible Server:**
   - Enable the `pgvector` extension (supported on Flexible Server).
   - Enable the `uuid-ossp` extension.
   - Configure within the VNet for private access.

2. **Migrate schema and data:**

   ```bash
   # Export from Supabase
   pg_dump --no-owner --no-acl \
     -h db.<project>.supabase.co -U postgres -d postgres \
     > grantscope_dump.sql

   # Import to Azure PostgreSQL
   psql -h <azure-host>.postgres.database.azure.com \
     -U grantscope_admin -d grantscope \
     < grantscope_dump.sql
   ```

3. **Migrate RLS policies:**
   - Supabase RLS relies on `auth.uid()`. Azure PostgreSQL does not have this.
   - **Option A (recommended):** Move authorization checks to the FastAPI application layer. The API already validates JWTs and extracts user IDs -- add query filters there.
   - **Option B:** Set `app.current_user_id` via `SET` at connection time and rewrite RLS policies to use `current_setting('app.current_user_id')`.

4. **Update connection strings:**
   - Store new connection string in Azure Key Vault.
   - Update Container Apps to reference Key Vault secret.

5. **Validate:**
   - Run the test suite against the new database.
   - Verify vector similarity search returns correct results (0.92 threshold).
   - Validate all card CRUD operations, discovery runs, and workstream queries.

6. **Decommission Supabase project.**

**Duration:** 1-2 weeks.

---

### Phase 3 -- Auth Migration (Supabase Auth to Azure AD / Entra ID)

**Goal:** Replace Supabase Auth with city SSO via Entra ID.

**Steps:**

1. **Register application in Entra ID:**
   - Create app registration in the city's Azure AD tenant.
   - Configure redirect URIs for the frontend.
   - Define API scopes (`GrantScope.Read`, `GrantScope.Write`, `GrantScope.Admin`).

2. **Update backend JWT validation:**
   - Replace Supabase JWT verification with Entra ID token validation.
   - Validate tokens against `https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration`.
   - Map Entra ID `oid` claim to the application's user ID.

3. **Update frontend auth flow:**
   - Replace `@supabase/supabase-js` auth with `@azure/msal-react`.
   - Implement login/logout using MSAL redirect flow.
   - Pass Entra ID access token in `Authorization: Bearer` header.

4. **Migrate user records:**
   - Map existing Supabase `auth.users` UUIDs to Entra ID object IDs.
   - Update `user_follows`, `user_preferences`, and other user-scoped tables.
   - Run a one-time migration script to reconcile user identities.

5. **Validate:**
   - Test SSO login with city credentials.
   - Verify role-based access and JWT claims flow through correctly.
   - Confirm user-specific features (follows, discovery queue) work.

**Duration:** 2-3 weeks.

---

### Phase 4 -- Observability & Security Hardening

**Goal:** Production-grade monitoring, secrets management, and network security.

**Steps:**

1. **Application Insights:**
   - Add `opencensus-ext-azure` or `azure-monitor-opentelemetry` to the FastAPI app.
   - Configure structured logging with correlation IDs.
   - Set up dashboards for: request latency, error rates, worker job duration, AI API call costs.
   - Configure alerts for error spikes and worker failures.

2. **Azure Key Vault:**
   - Store all secrets (Azure OpenAI key, Serper API key, DB connection string).
   - Grant Container Apps managed identity access to Key Vault.
   - Remove all secrets from environment variables and `.env` files.

3. **Azure Front Door + WAF:**
   - Enable DDoS protection.
   - Configure rate limiting rules (matching current `@rate_limit_*` decorators).
   - Enable bot protection and geo-filtering if required.

4. **Private Networking:**
   - Ensure PostgreSQL is accessible only via VNet private endpoint.
   - Container Apps communicate with PostgreSQL over private link.
   - No public IP on the database.

5. **Azure Blob Storage:**
   - Create storage account for PDF/PPTX exports.
   - Update `export_service.py` to write to Blob Storage instead of local filesystem.
   - Configure SAS token generation for time-limited download links.

**Duration:** 1-2 weeks.

---

## 4. Dependencies Eliminated

| Previous Dependency            | Status              | Replacement                            | Cost       |
| ------------------------------ | ------------------- | -------------------------------------- | ---------- |
| Firecrawl (content extraction) | Eliminated          | trafilatura (self-hosted, open source) | $0         |
| Exa AI (semantic search API)   | Eliminated          | Serper + trafilatura                   | $0         |
| Tavily (research API)          | Eliminated          | Serper.dev ($1/1K queries)             | ~$1-5/mo   |
| Railway (compute)              | Migrating (Phase 1) | Azure Container Apps                   | City infra |
| Supabase PostgreSQL            | Migrating (Phase 2) | Azure DB for PostgreSQL                | City infra |
| Supabase Auth                  | Migrating (Phase 3) | Azure AD / Entra ID                    | City infra |
| NewsAPI                        | Eliminated          | Serper news search                     | Included   |

**After migration, only one external paid API remains:** Serper.dev at approximately $1-5/month.

---

## 5. Cost Comparison

### Current Pilot Costs (Monthly)

| Service                          | Cost          |
| -------------------------------- | ------------- |
| Railway (API + Worker)           | ~$5-20        |
| Supabase (Free/Pro tier)         | $0-25         |
| Azure OpenAI (city subscription) | Covered       |
| Serper.dev                       | ~$1-5         |
| **Total**                        | **~$6-50/mo** |

### Azure Deployment Costs (Monthly)

| Service                        | Estimated Cost          |
| ------------------------------ | ----------------------- |
| Container Apps (Consumption)   | ~$0-15 (scales to zero) |
| Azure DB for PostgreSQL (B1ms) | ~$25-40                 |
| Azure Blob Storage             | <$1                     |
| Application Insights           | <$5                     |
| Key Vault                      | <$1                     |
| Front Door (Standard)          | ~$35                    |
| Serper.dev                     | ~$1-5                   |
| **Total**                      | **~$67-97/mo**          |

**Note:** If the city already has enterprise agreements or reserved capacity, Container Apps, Front Door, and monitoring costs may be significantly lower or already covered. The Azure DB for PostgreSQL cost can be reduced by using reserved instances (~40% savings). Without Front Door (if behind city network), costs drop to ~$30-60/mo.

---

## 6. Prerequisites

The following must be provisioned by City of Austin IT before migration begins:

| Item                                    | Owner              | Phase   |
| --------------------------------------- | ------------------ | ------- |
| Azure subscription / resource group     | City IT            | Phase 1 |
| Azure Container Registry (ACR)          | City IT            | Phase 1 |
| Azure Container Apps Environment        | City IT / Dev Team | Phase 1 |
| Azure DB for PostgreSQL Flexible Server | City IT            | Phase 2 |
| VNet + private endpoints configuration  | City IT (Network)  | Phase 2 |
| Entra ID app registration               | City IT (Identity) | Phase 3 |
| Azure Key Vault instance                | City IT            | Phase 1 |
| Azure Blob Storage account              | City IT            | Phase 4 |
| Azure Front Door profile                | City IT (Network)  | Phase 4 |
| Application Insights workspace          | City IT            | Phase 4 |
| DNS records / custom domain delegation  | City IT (Network)  | Phase 1 |
| CI/CD pipeline (GitHub Actions to ACR)  | Dev Team           | Phase 1 |

---

## 7. Risks & Mitigations

| Risk                                                                | Impact                                                        | Likelihood | Mitigation                                                                                                                                       |
| ------------------------------------------------------------------- | ------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| pgvector behavior differences between Supabase and Azure PostgreSQL | Similarity search returns different results                   | Low        | Test with production data before cutover. Both use the same pgvector extension.                                                                  |
| RLS policy migration breaks authorization                           | Users see data they shouldn't, or can't access their own data | Medium     | Move to application-level auth checks in FastAPI. Test all endpoints with multiple user roles.                                                   |
| Entra ID token format differs from Supabase JWT                     | Auth breaks across frontend and backend                       | Medium     | Build and test the new auth flow in a staging environment before cutover. Keep Supabase Auth running in parallel during transition.              |
| Cold start latency on Container Apps (Consumption)                  | Slow first request after idle period                          | Medium     | Set minimum replica count to 1 for the API container. Worker can scale to zero since it processes async jobs.                                    |
| Database migration data loss                                        | Missing cards, broken references                              | Low        | Use `pg_dump`/`pg_restore` with checksums. Run diff validation queries post-migration. Keep Supabase running read-only for 1 week after cutover. |
| City IT provisioning delays                                         | Timeline slips                                                | High       | Submit provisioning requests early. Identify a technical contact in City IT. Have a clear list of requirements (Section 6) ready on day one.     |
| Network/firewall rules block outbound calls                         | Serper API, Azure OpenAI calls fail                           | Medium     | Document all outbound endpoints. Request firewall rules during Phase 1. Test connectivity before decommissioning Railway.                        |

---

## Timeline Summary

| Phase                | Duration      | Dependencies                                       |
| -------------------- | ------------- | -------------------------------------------------- |
| Phase 1 -- Compute   | 1-2 weeks     | Azure subscription, ACR, Container Apps, Key Vault |
| Phase 2 -- Database  | 1-2 weeks     | Azure PostgreSQL, VNet, Phase 1 complete           |
| Phase 3 -- Auth      | 2-3 weeks     | Entra ID app registration, Phase 2 complete        |
| Phase 4 -- Hardening | 1-2 weeks     | Front Door, Blob Storage, App Insights             |
| **Total**            | **5-9 weeks** |                                                    |

Phases can overlap where dependencies allow. Phase 4 tasks (Key Vault, App Insights) can begin alongside Phase 1.
