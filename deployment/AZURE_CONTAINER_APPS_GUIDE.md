# Azure Container Apps Deployment Guide (GrantScope2)

This guide documents the Azure Container Apps setup for the GrantScope2 strategic horizon scanning system. It covers infrastructure provisioning, multi-service deployment, secret management, network access control, database administration, blob storage, and troubleshooting.

**Last updated:** February 2026

---

## 1. Scope + Principles

GrantScope2 is a multi-service architecture deployed to Azure Container Apps:

| Service               | Technology                                          | Purpose                                        |
| --------------------- | --------------------------------------------------- | ---------------------------------------------- |
| **API Server**        | FastAPI (Python 3.11), port 8000                    | REST API, serves `/api/v1/*` endpoints         |
| **Background Worker** | Same image, `GRANTSCOPE_PROCESS_TYPE=worker`        | Long-running jobs: discovery, research, briefs |
| **Frontend**          | React 18 + Vite + TypeScript                        | Static Web App (SWA)                           |
| **Database**          | Azure PostgreSQL Flexible Server (PG 16 + pgvector) | Primary data store                             |
| **Blob Storage**      | Azure Storage Account                               | Application attachments                        |

**Principles:**

- **Secrets in Key Vault only.** No secrets in environment variables, Bicep parameters, or git.
- **Bicep IaC for all infrastructure.** Every Azure resource is defined in `infrastructure/` and deployed via `deploy.sh`.
- **Hardcoded auth for MVP.** Entra ID authentication is planned for a future phase. The current deployment uses a single hardcoded test user for initial testing and demo.
- **Immutable image tags.** Every release uses a unique, versioned tag (e.g., `v1.2.3` or `20260217-abcdef`). Never deploy `:latest` to production.

---

## 2. Current Azure Footprint

All resources reside in the shared resource group `rg-aph-cognitive-sandbox-dev-scus-01` (South Central US).

| Resource                   | Name                         | SKU / Notes                                    |
| -------------------------- | ---------------------------- | ---------------------------------------------- |
| Container App (API)        | `ca-grantscope2-api-prod`    | 0.5 vCPU, 1Gi RAM, min 1 / max 3 replicas      |
| Container App (Worker)     | `ca-grantscope2-worker-prod` | 0.5 vCPU, 1Gi RAM, min 1 / max 1 replicas      |
| Container Apps Environment | `cae-grantscope2-prod`       | Consumption workload profile                   |
| Azure Container Registry   | `acrgrantscope2prod`         | Standard SKU (`acrgrantscope2prod.azurecr.io`) |
| Key Vault                  | `kv-grantscope2-prd`         | Standard SKU                                   |
| Log Analytics Workspace    | `log-grantscope2-prod`       | Centralized logging for both container apps    |
| PostgreSQL Flexible Server | `psql-grantscope2-prod`      | Burstable B1ms, PG 16, pgvector enabled        |
| Storage Account            | `stgrantscope2prod`          | Blob container: `application-attachments`      |
| Static Web App             | `swa-grantscope2-prod`       | React/Vite frontend                            |

### Useful Commands

Get the API container app FQDN:

```bash
az containerapp show \
  -g rg-aph-cognitive-sandbox-dev-scus-01 \
  -n ca-grantscope2-api-prod \
  --query properties.configuration.ingress.fqdn -o tsv
```

Get the worker container app status:

```bash
az containerapp show \
  -g rg-aph-cognitive-sandbox-dev-scus-01 \
  -n ca-grantscope2-worker-prod \
  --query "{state:properties.provisioningState,running:properties.runningStatus}" -o jsonc
```

Check all GrantScope2 resources in the resource group:

```bash
az resource list \
  -g rg-aph-cognitive-sandbox-dev-scus-01 \
  --query "[?contains(name, 'grantscope2') || contains(name, 'grantscope')].{name:name, type:type, location:location}" \
  -o table
```

The API container app exposes:

- **App:** `https://<API_FQDN>/`
- **Health:** `https://<API_FQDN>/api/v1/health`
- **Docs:** `https://<API_FQDN>/docs` (Swagger UI)

The worker container app exposes:

- **Health:** `https://<WORKER_FQDN>/api/v1/health` (minimal health server for liveness probes)

The frontend is served from:

- **Static Web App:** `https://swa-grantscope2-prod.<region>.azurestaticapps.net/`

---

## 3. Prerequisites

### Software

- **Python 3.11+** (for local backend development and testing)
- **Docker** (for building container images; `docker buildx` required for multi-platform builds)
- **Azure CLI** (`az`): logged in via `az login`
- **Azure CLI Bicep support:** install with `az bicep install`
- **Node.js 20+** and **pnpm** (for frontend builds)
- **Azure Static Web Apps CLI:** `npm install -g @azure/static-web-apps-cli`

### Azure Permissions

The deploying identity needs:

| Permission                        | Scope              | Purpose                         |
| --------------------------------- | ------------------ | ------------------------------- |
| **Contributor** (or higher)       | Resource group     | Deploy infrastructure via Bicep |
| **Key Vault Secrets Officer**     | Key Vault          | Set and manage secrets          |
| **AcrPush**                       | Container Registry | Push container images           |
| **Storage Blob Data Contributor** | Storage Account    | Manage blob containers          |

### Authentication (Deferred)

Entra ID authentication setup is deferred to a future phase. For the MVP, the application uses a hardcoded test user:

- **Email:** `test@grantscope.austintexas.gov`
- **Password:** `TestPassword123!`

See [Section 5: Authentication](#5-authentication-future-entra-id) for the planned Entra ID configuration.

---

## 4. Deployments (IaC + App)

### 4a. Parameter Files

Parameter files live under `infrastructure/parameters/`:

- `infrastructure/parameters/dev.bicepparam`
- `infrastructure/parameters/staging.bicepparam`
- `infrastructure/parameters/prod.bicepparam`

Key fields:

| Parameter         | Description                                     |
| ----------------- | ----------------------------------------------- |
| `baseName`        | Controls resource naming (e.g., `grantscope2`)  |
| `imageTag`        | Container image tag to deploy (e.g., `v1.0.0`)  |
| `externalIngress` | Whether the API app is publicly accessible      |
| `enableKeyVault`  | Whether to provision and wire up Key Vault      |
| `enablePostgres`  | Whether to provision PostgreSQL Flexible Server |
| `enableStorage`   | Whether to provision the Storage Account        |

### 4b. Deploy Infrastructure (Bicep)

Use the deployment wrapper script:

```bash
./infrastructure/deploy.sh prod --resource-group rg-aph-cognitive-sandbox-dev-scus-01
```

This creates or updates: ACR, Key Vault, Log Analytics, Container Apps Environment, both Container Apps (API + Worker), PostgreSQL Flexible Server, and Storage Account.

### 4c. Set Secrets in Key Vault

The container apps reference Key Vault secrets by name. Set the following secrets (values intentionally omitted):

```bash
VAULT="kv-grantscope2-prd"

# Database connection string (asyncpg format)
az keyvault secret set --vault-name $VAULT \
  --name database-url \
  --value 'postgresql+asyncpg://gsadmin:<password>@psql-grantscope2-prod.postgres.database.azure.com:5432/grantscope'

# Azure Blob Storage connection string
az keyvault secret set --vault-name $VAULT \
  --name azure-storage-connection-string \
  --value 'DefaultEndpointsProtocol=https;AccountName=stgrantscope2prod;AccountKey=<key>;EndpointSuffix=core.windows.net'

# Azure OpenAI
az keyvault secret set --vault-name $VAULT \
  --name azure-openai-api-key \
  --value '<your-azure-openai-key>'

az keyvault secret set --vault-name $VAULT \
  --name azure-openai-endpoint \
  --value 'https://aph-cognitive-sandbox-openai-eastus2.openai.azure.com'

# Supabase (used by legacy services during migration)
az keyvault secret set --vault-name $VAULT \
  --name supabase-url \
  --value 'https://<your-project>.supabase.co'

az keyvault secret set --vault-name $VAULT \
  --name supabase-service-key \
  --value '<your-supabase-service-key>'

# Search and research APIs
az keyvault secret set --vault-name $VAULT \
  --name tavily-api-key \
  --value '<your-tavily-key>'

az keyvault secret set --vault-name $VAULT \
  --name firecrawl-api-key \
  --value '<your-firecrawl-key>'
```

If you get permission errors, grant the deploying identity RBAC access on the vault:

```bash
az role assignment create \
  --assignee <your-aad-object-id-or-upn> \
  --role "Key Vault Secrets Officer" \
  --scope $(az keyvault show -g rg-aph-cognitive-sandbox-dev-scus-01 -n kv-grantscope2-prd --query id -o tsv)
```

### 4d. Build and Push Backend Image to ACR

Build a `linux/amd64` image and push it to ACR with a versioned tag:

```bash
# Login to ACR
az acr login --name acrgrantscope2prod

# Build and push (from repo root)
IMAGE_TAG="v1.0.0-$(git rev-parse --short HEAD)"
docker buildx build \
  --platform linux/amd64 \
  -t acrgrantscope2prod.azurecr.io/grantscope2-api:${IMAGE_TAG} \
  -f backend/Dockerfile \
  --push \
  .

# Update the API container app
az containerapp update \
  -g rg-aph-cognitive-sandbox-dev-scus-01 \
  -n ca-grantscope2-api-prod \
  --image acrgrantscope2prod.azurecr.io/grantscope2-api:${IMAGE_TAG}

# Update the Worker container app (same image, different process type)
az containerapp update \
  -g rg-aph-cognitive-sandbox-dev-scus-01 \
  -n ca-grantscope2-worker-prod \
  --image acrgrantscope2prod.azurecr.io/grantscope2-api:${IMAGE_TAG}
```

Alternatively, use the deployment wrapper which handles build + push + update:

```bash
./infrastructure/deploy.sh prod \
  --resource-group rg-aph-cognitive-sandbox-dev-scus-01 \
  --push
```

**Important:** Azure Container Apps may cache images by tag. Always deploy a unique tag for each release.

### 4e. Deploy Frontend to Static Web App

Build and deploy the React/Vite frontend:

```bash
cd frontend/foresight-frontend

# Install dependencies and build
pnpm install
VITE_API_URL="https://<API_FQDN>" \
VITE_SUPABASE_URL="https://<your-project>.supabase.co" \
VITE_SUPABASE_ANON_KEY="<anon-key>" \
pnpm build

# Deploy to Azure Static Web App
swa deploy dist \
  --app-name swa-grantscope2-prod \
  --env production
```

### 4f. Run Database Migrations

Run Alembic migrations against the Azure PostgreSQL instance:

```bash
cd backend

# Set the database URL (or export it)
export DATABASE_URL="postgresql+asyncpg://gsadmin:<password>@psql-grantscope2-prod.postgres.database.azure.com:5432/grantscope"

# Apply all pending migrations
alembic upgrade head

# Verify current migration state
alembic current
```

For remote execution from a container:

```bash
az containerapp exec \
  -g rg-aph-cognitive-sandbox-dev-scus-01 \
  -n ca-grantscope2-api-prod \
  --command "alembic upgrade head"
```

### 4g. Verify Deployment

```bash
RG="rg-aph-cognitive-sandbox-dev-scus-01"

# Check API revisions
az containerapp revision list -g $RG -n ca-grantscope2-api-prod -o table

# Check Worker revisions
az containerapp revision list -g $RG -n ca-grantscope2-worker-prod -o table

# Get the API FQDN
API_FQDN=$(az containerapp show -g $RG -n ca-grantscope2-api-prod \
  --query properties.configuration.ingress.fqdn -o tsv)

# Health check
curl -i "https://${API_FQDN}/api/v1/health"

# Verify the API responds
curl -s "https://${API_FQDN}/docs" | head -20
```

---

## 5. Authentication (Future: Entra ID)

### Current State (MVP)

For the MVP phase, authentication uses a hardcoded test user in the application code. There is no Azure Entra ID integration yet. The test user is:

- **Email:** `test@grantscope.austintexas.gov`
- **Password:** `TestPassword123!`

Access control during MVP relies on IP allowlisting (see [Section 6](#6-network-access-ip-allowlist)) to restrict who can reach the application.

### Planned Entra ID Setup

When Entra ID authentication is enabled, Azure Container Apps provides built-in auth endpoints under `/.auth/*`. Unauthenticated requests will be challenged, and users must be assigned to the Enterprise Application to access the app.

**Sign-in URL (once enabled):**

```text
https://<API_FQDN>/.auth/login/aad?post_login_redirect_uri=/
```

**Recommended setup: Dedicated Entra app registration**

Best practice is one Entra app registration per web app, with:

- Redirect URI: `https://<API_FQDN>/.auth/login/aad/callback`
- Identifier URI / audience: `api://<clientId>`
- A client secret stored in the Container App secret store (`microsoft-provider-authentication-secret`)

Directory permissions vary by tenant. If `az ad app create` fails with "Insufficient privileges", request directory role support or use the shared-app approach below.

**Shared-app setup (available in this environment)**

In the current environment, a shared Entra app registration exists that can be reused if directory permissions prevent creating a new app:

- **Tenant:** `5c5e19f6-a6ab-4b45-b1d0-be4608a9a67f`
- **Shared app registration (clientId):** `5bc5f790-8319-4a2c-8ffe-5fdfd2200f60`

If using the shared app:

1. Add the GrantScope2 callback URL to the shared app's redirect URIs.
2. Create a dedicated client secret for GrantScope2 usage and store it in the GrantScope2 Container App secret store.
3. On teardown, remove the GrantScope2 callback URL and delete the GrantScope2 credential from the shared app.

### Managing User Access (Add/Remove People)

Access is controlled via the **Enterprise Application** backing the Entra app registration. In this tenant, assignment is required (users/groups must be explicitly assigned).

**Initial user:** `christopher.collins@austintexas.gov`

**Preferred method:** Entra portal -> Enterprise Applications -> (app name) -> Users and groups.

**CLI (user assignment) example:**

```bash
MAIL="christopher.collins@austintexas.gov"
APP_ID="5bc5f790-8319-4a2c-8ffe-5fdfd2200f60"

USER_ID=$(az ad user list --filter "mail eq '${MAIL}'" --query "[0].id" -o tsv)
SP_ID=$(az ad sp show --id "${APP_ID}" --query id -o tsv)

# Assign user (default appRoleId is all zeros when no explicit appRoles exist)
az rest --method POST \
  --url "https://graph.microsoft.com/v1.0/users/${USER_ID}/appRoleAssignments" \
  --body "{\"principalId\":\"${USER_ID}\",\"resourceId\":\"${SP_ID}\",\"appRoleId\":\"00000000-0000-0000-0000-000000000000\"}"
```

**Remove a user assignment:**

```bash
ASSIGNMENT_ID=$(az rest --method GET \
  --url "https://graph.microsoft.com/v1.0/users/${USER_ID}/appRoleAssignments?\$filter=resourceId%20eq%20${SP_ID}" \
  --query "value[0].id" -o tsv)

az rest --method DELETE \
  --url "https://graph.microsoft.com/v1.0/users/${USER_ID}/appRoleAssignments/${ASSIGNMENT_ID}"
```

---

## 6. Network Access (IP Allowlist)

Ingress access restrictions are a network gate that applies **before** any application-level authentication:

1. Request must originate from an allowed IP/CIDR (if an allowlist is configured).
2. Then the user must authenticate (once Entra ID is enabled).

**Important:** Both container apps (API and Worker) should be configured if the worker exposes an external health endpoint. For the MVP, the primary concern is the API container app.

### List Current Allow Rules

```bash
RG="rg-aph-cognitive-sandbox-dev-scus-01"

# API container app
az containerapp ingress access-restriction list -g $RG -n ca-grantscope2-api-prod -o table

# Worker container app
az containerapp ingress access-restriction list -g $RG -n ca-grantscope2-worker-prod -o table
```

### Add a Temporary Developer IP

```bash
RG="rg-aph-cognitive-sandbox-dev-scus-01"

# Add to API container app
az containerapp ingress access-restriction set -g $RG -n ca-grantscope2-api-prod \
  --rule-name dev-chris \
  --ip-address 203.0.113.45/32 \
  --description "Chris Collins - temporary dev access" \
  --action Allow

# Mirror the same rule to the Worker (if external ingress is enabled)
az containerapp ingress access-restriction set -g $RG -n ca-grantscope2-worker-prod \
  --rule-name dev-chris \
  --ip-address 203.0.113.45/32 \
  --description "Chris Collins - temporary dev access" \
  --action Allow
```

### Remove a Rule

```bash
RG="rg-aph-cognitive-sandbox-dev-scus-01"

az containerapp ingress access-restriction remove -g $RG -n ca-grantscope2-api-prod \
  --rule-name dev-chris

az containerapp ingress access-restriction remove -g $RG -n ca-grantscope2-worker-prod \
  --rule-name dev-chris
```

### MVP Access

For the MVP, ensure that `christopher.collins@austintexas.gov`'s IP address is allowlisted on the API container app. Determine their current IP and add it:

```bash
# Ask the user for their IP, or look it up
curl -s https://ifconfig.me

# Then add the allow rule
az containerapp ingress access-restriction set \
  -g rg-aph-cognitive-sandbox-dev-scus-01 \
  -n ca-grantscope2-api-prod \
  --rule-name user-chris-collins \
  --ip-address <CHRIS_IP>/32 \
  --description "christopher.collins@austintexas.gov - MVP user" \
  --action Allow
```

---

## 7. PostgreSQL Administration

### Connection Details

- **Server:** `psql-grantscope2-prod.postgres.database.azure.com`
- **Port:** `5432`
- **Database:** `grantscope`
- **Admin user:** `gsadmin`
- **SSL:** Required (Azure enforces SSL by default)

### Connect via psql

```bash
psql "host=psql-grantscope2-prod.postgres.database.azure.com \
  port=5432 \
  dbname=grantscope \
  user=gsadmin \
  sslmode=require"
```

### Connect via Azure CLI

```bash
az postgres flexible-server connect \
  -n psql-grantscope2-prod \
  -u gsadmin \
  -d grantscope \
  --interactive
```

### Running Migrations

Migrations use Alembic and are located in `backend/alembic/`. The `alembic.ini` file reads `DATABASE_URL` from the environment (it is never hardcoded in the config file).

```bash
cd backend

export DATABASE_URL="postgresql+asyncpg://gsadmin:<password>@psql-grantscope2-prod.postgres.database.azure.com:5432/grantscope"

# Check current state
alembic current

# View migration history
alembic history

# Apply all pending migrations
alembic upgrade head

# Roll back one migration
alembic downgrade -1
```

### Enabling pgvector Extension

The pgvector extension must be enabled once on the database for vector similarity search:

```sql
-- Connect to the grantscope database, then:
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify
SELECT * FROM pg_extension WHERE extname = 'vector';
```

Via Azure CLI:

```bash
az postgres flexible-server parameter set \
  -g rg-aph-cognitive-sandbox-dev-scus-01 \
  -s psql-grantscope2-prod \
  --name azure.extensions \
  --value VECTOR
```

### Firewall Rules

Azure PostgreSQL Flexible Server uses firewall rules to control access. Add your development IP:

```bash
az postgres flexible-server firewall-rule create \
  -g rg-aph-cognitive-sandbox-dev-scus-01 \
  -n psql-grantscope2-prod \
  --rule-name dev-chris \
  --start-ip-address 203.0.113.45 \
  --end-ip-address 203.0.113.45
```

Remove when no longer needed:

```bash
az postgres flexible-server firewall-rule delete \
  -g rg-aph-cognitive-sandbox-dev-scus-01 \
  -n psql-grantscope2-prod \
  --rule-name dev-chris --yes
```

### Backup Considerations

Azure PostgreSQL Flexible Server (Burstable B1ms) includes:

- **Automated backups:** Retained for 7 days by default (configurable up to 35 days).
- **Point-in-time restore:** Available within the backup retention period.
- **Geo-redundant backup:** Not available on Burstable SKU. Consider upgrading for production workloads that require geo-redundancy.

Check backup configuration:

```bash
az postgres flexible-server show \
  -g rg-aph-cognitive-sandbox-dev-scus-01 \
  -n psql-grantscope2-prod \
  --query "{backup:backup, sku:sku}" -o jsonc
```

---

## 8. Blob Storage Administration

### Storage Account Details

- **Account:** `stgrantscope2prod`
- **Container:** `application-attachments`
- **Purpose:** Stores uploaded files (PDFs, budgets, supporting documents) associated with grant applications.

### Creating the Container

The `application-attachments` container should be created by the Bicep deployment. If it needs to be created manually:

```bash
az storage container create \
  --account-name stgrantscope2prod \
  --name application-attachments \
  --auth-mode login
```

### Checking Usage

List blobs in the container:

```bash
az storage blob list \
  --account-name stgrantscope2prod \
  --container-name application-attachments \
  --auth-mode login \
  -o table
```

Get container size and blob count:

```bash
az storage blob list \
  --account-name stgrantscope2prod \
  --container-name application-attachments \
  --auth-mode login \
  --query "[].properties.contentLength" -o tsv | awk '{sum+=$1} END {printf "Total: %.2f MB (%d blobs)\n", sum/1048576, NR}'
```

### SAS URL Generation

Generate a temporary SAS URL for a specific blob (e.g., for sharing a download link):

```bash
az storage blob generate-sas \
  --account-name stgrantscope2prod \
  --container-name application-attachments \
  --name "path/to/file.pdf" \
  --permissions r \
  --expiry $(date -u -v+1H '+%Y-%m-%dT%H:%MZ') \
  --auth-mode login \
  --as-user \
  --full-uri
```

Generate a container-level SAS (for bulk operations):

```bash
az storage container generate-sas \
  --account-name stgrantscope2prod \
  --name application-attachments \
  --permissions rl \
  --expiry $(date -u -v+1H '+%Y-%m-%dT%H:%MZ') \
  --auth-mode login \
  --as-user
```

---

## 9. Troubleshooting

### Container App Shows "Unavailable" (404)

If `https://<API_FQDN>/` returns an Azure "Unavailable" page but the revision FQDN works, repair traffic routing:

```bash
RG="rg-aph-cognitive-sandbox-dev-scus-01"
CA="ca-grantscope2-api-prod"

# Switch to multiple revision mode (enables explicit traffic routing)
az containerapp revision set-mode -g "$RG" -n "$CA" --mode multiple

# Route 100% of traffic to the latest revision
az containerapp ingress traffic set -g "$RG" -n "$CA" --revision-weight latest=100
```

Verify:

```bash
az containerapp show -g "$RG" -n "$CA" \
  --query "{state:properties.provisioningState,fqdn:properties.configuration.ingress.fqdn}" -o jsonc
```

### Database Connection Issues

**Symptom:** API logs show `connection refused` or `timeout` errors to PostgreSQL.

1. **Check firewall rules** -- the container app's outbound IPs must be allowed:

   ```bash
   # Get the container app environment's outbound IPs
   az containerapp env show \
     -g rg-aph-cognitive-sandbox-dev-scus-01 \
     -n cae-grantscope2-prod \
     --query "properties.staticIp" -o tsv

   # List current PostgreSQL firewall rules
   az postgres flexible-server firewall-rule list \
     -g rg-aph-cognitive-sandbox-dev-scus-01 \
     -n psql-grantscope2-prod -o table
   ```

2. **Check the DATABASE_URL secret** is correctly set in Key Vault:

   ```bash
   az keyvault secret show --vault-name kv-grantscope2-prd --name database-url --query value -o tsv
   ```

3. **Check PostgreSQL server status:**

   ```bash
   az postgres flexible-server show \
     -g rg-aph-cognitive-sandbox-dev-scus-01 \
     -n psql-grantscope2-prod \
     --query "{state:state, fqdn:fullyQualifiedDomainName}" -o jsonc
   ```

### Worker Not Processing Jobs

**Symptom:** Jobs remain in `queued` status and are never picked up.

1. **Check the worker is running:**

   ```bash
   az containerapp revision list \
     -g rg-aph-cognitive-sandbox-dev-scus-01 \
     -n ca-grantscope2-worker-prod -o table
   ```

2. **Check worker logs:**

   ```bash
   az containerapp logs show \
     -g rg-aph-cognitive-sandbox-dev-scus-01 \
     -n ca-grantscope2-worker-prod \
     --tail 100
   ```

3. **Verify the worker has `GRANTSCOPE_PROCESS_TYPE=worker`** set in its environment:

   ```bash
   az containerapp show \
     -g rg-aph-cognitive-sandbox-dev-scus-01 \
     -n ca-grantscope2-worker-prod \
     --query "properties.template.containers[0].env[?name=='GRANTSCOPE_PROCESS_TYPE']" -o jsonc
   ```

4. **Restart the worker revision:**

   ```bash
   REV=$(az containerapp show -g rg-aph-cognitive-sandbox-dev-scus-01 \
     -n ca-grantscope2-worker-prod --query properties.latestReadyRevisionName -o tsv)
   az containerapp revision restart \
     -g rg-aph-cognitive-sandbox-dev-scus-01 \
     -n ca-grantscope2-worker-prod --revision "$REV"
   ```

### Image Pull Failures

**Symptom:** Container app revision fails to start with image pull errors.

1. **Verify the image exists in ACR:**

   ```bash
   az acr repository show-tags --name acrgrantscope2prod --repository grantscope2-api -o table
   ```

2. **Check ACR credentials are configured on the container app:**

   ```bash
   az containerapp registry list \
     -g rg-aph-cognitive-sandbox-dev-scus-01 \
     -n ca-grantscope2-api-prod -o table
   ```

3. **Re-configure ACR access (if needed):**

   ```bash
   az containerapp registry set \
     -g rg-aph-cognitive-sandbox-dev-scus-01 \
     -n ca-grantscope2-api-prod \
     --server acrgrantscope2prod.azurecr.io \
     --identity system
   ```

### Migration Failures

**Symptom:** `alembic upgrade head` fails with errors.

1. **Check current migration state:**

   ```bash
   alembic current
   alembic history --verbose
   ```

2. **If the migration is partially applied**, you may need to manually mark it or roll back:

   ```bash
   # Roll back one step
   alembic downgrade -1

   # Or stamp a specific revision (use with caution)
   alembic stamp <revision_id>
   ```

3. **Check for schema conflicts** by connecting to the database and inspecting:

   ```bash
   psql "host=psql-grantscope2-prod.postgres.database.azure.com port=5432 dbname=grantscope user=gsadmin sslmode=require" \
     -c "SELECT * FROM alembic_version;"
   ```

### Secrets Not Taking Effect

Container Apps may require a revision restart after secret updates:

```bash
# Restart API
REV=$(az containerapp show -g rg-aph-cognitive-sandbox-dev-scus-01 \
  -n ca-grantscope2-api-prod --query properties.latestReadyRevisionName -o tsv)
az containerapp revision restart \
  -g rg-aph-cognitive-sandbox-dev-scus-01 \
  -n ca-grantscope2-api-prod --revision "$REV"

# Restart Worker
REV=$(az containerapp show -g rg-aph-cognitive-sandbox-dev-scus-01 \
  -n ca-grantscope2-worker-prod --query properties.latestReadyRevisionName -o tsv)
az containerapp revision restart \
  -g rg-aph-cognitive-sandbox-dev-scus-01 \
  -n ca-grantscope2-worker-prod --revision "$REV"
```

### Viewing Logs

Stream live logs from either container app:

```bash
# API logs (live stream)
az containerapp logs show \
  -g rg-aph-cognitive-sandbox-dev-scus-01 \
  -n ca-grantscope2-api-prod \
  --follow

# Worker logs (last 200 lines)
az containerapp logs show \
  -g rg-aph-cognitive-sandbox-dev-scus-01 \
  -n ca-grantscope2-worker-prod \
  --tail 200
```

Query Log Analytics for historical logs:

```bash
az monitor log-analytics query \
  --workspace log-grantscope2-prod \
  --analytics-query "ContainerAppConsoleLogs_CL | where ContainerAppName_s contains 'grantscope2' | order by TimeGenerated desc | take 50" \
  -o table
```

---

## 10. Cleanup

Pick the cleanup level that matches your intent.

### A) Keep Running, Remove Temporary Dev Access

1. Remove temporary IP allow rules (keep only corporate/VPN/proxy ranges):

   ```bash
   RG="rg-aph-cognitive-sandbox-dev-scus-01"

   # List current rules
   az containerapp ingress access-restriction list -g $RG -n ca-grantscope2-api-prod -o table
   az containerapp ingress access-restriction list -g $RG -n ca-grantscope2-worker-prod -o table

   # Remove temporary developer rules
   az containerapp ingress access-restriction remove -g $RG -n ca-grantscope2-api-prod --rule-name dev-chris
   az containerapp ingress access-restriction remove -g $RG -n ca-grantscope2-worker-prod --rule-name dev-chris
   ```

2. Remove individual PostgreSQL firewall rules:

   ```bash
   az postgres flexible-server firewall-rule delete \
     -g $RG -n psql-grantscope2-prod --rule-name dev-chris --yes
   ```

3. Rotate any temporary credentials or SAS tokens.

### B) Full Teardown (All GrantScope2 Resources)

If GrantScope2 is no longer needed, delete its resources. **The resource group is shared** -- delete only GrantScope2-specific resources. **Do NOT delete the resource group itself.**

Suggested order:

```bash
RG="rg-aph-cognitive-sandbox-dev-scus-01"

# 1. Container Apps (API + Worker)
az containerapp delete -g $RG -n ca-grantscope2-api-prod --yes
az containerapp delete -g $RG -n ca-grantscope2-worker-prod --yes

# 2. Container Apps Environment
az containerapp env delete -g $RG -n cae-grantscope2-prod --yes

# 3. Static Web App
az staticwebapp delete -g $RG -n swa-grantscope2-prod --yes

# 4. Container Registry
az acr delete -g $RG -n acrgrantscope2prod --yes

# 5. PostgreSQL Flexible Server (WARNING: destroys all data)
az postgres flexible-server delete -g $RG -n psql-grantscope2-prod --yes

# 6. Storage Account (WARNING: destroys all uploaded files)
az storage account delete -g $RG -n stgrantscope2prod --yes

# 7. Key Vault (soft-delete is enabled by default; can be purged later)
az keyvault delete -g $RG -n kv-grantscope2-prd

# 8. Log Analytics Workspace
az monitor log-analytics workspace delete -g $RG -n log-grantscope2-prod --yes
```

### C) Shared Entra App Cleanup (Only If GrantScope2 Used Shared App)

If you used the shared Entra app registration approach (Section 5):

1. Remove the GrantScope2 redirect URI from the shared app's redirect URIs.
2. Delete the GrantScope2 credential on the shared app (look for credentials with a display name like `grantscope2-containerapp-auth`).

**These steps can impact other apps using the same app registration.** Coordinate changes before removing shared redirect URIs or credentials.

---

## Appendix: Environment Variable Reference

The following environment variables are expected by the backend container. In production, sensitive values are sourced from Key Vault; non-sensitive values are set directly as Container App environment variables.

| Variable                            | Source                   | Description                                   |
| ----------------------------------- | ------------------------ | --------------------------------------------- |
| `ENVIRONMENT`                       | Container App env        | `production` or `development`                 |
| `GRANTSCOPE_PROCESS_TYPE`           | Container App env        | `web` (API) or `worker`                       |
| `GRANTSCOPE_ENABLE_SCHEDULER`       | Container App env        | `true` on worker only                         |
| `ALLOWED_ORIGINS`                   | Container App env        | Comma-separated CORS origins                  |
| `TRUSTED_PROXY_COUNT`               | Container App env        | `1` for Azure Container Apps                  |
| `DATABASE_URL`                      | Key Vault                | PostgreSQL connection string (asyncpg)        |
| `AZURE_STORAGE_CONNECTION_STRING`   | Key Vault                | Blob storage connection string                |
| `AZURE_OPENAI_API_KEY`              | Key Vault                | Azure OpenAI API key                          |
| `AZURE_OPENAI_ENDPOINT`             | Key Vault                | Azure OpenAI endpoint URL                     |
| `SUPABASE_URL`                      | Key Vault                | Supabase project URL (legacy)                 |
| `SUPABASE_SERVICE_KEY`              | Key Vault                | Supabase service role key (legacy)            |
| `TAVILY_API_KEY`                    | Key Vault                | Tavily search API key                         |
| `FIRECRAWL_API_KEY`                 | Key Vault                | Firecrawl API key                             |
| `AZURE_OPENAI_API_VERSION`          | Container App env        | `2024-12-01-preview`                          |
| `AZURE_OPENAI_DEPLOYMENT_CHAT`      | Container App env        | `gpt-4.1`                                     |
| `AZURE_OPENAI_DEPLOYMENT_CHAT_MINI` | Container App env        | `gpt-4.1-mini`                                |
| `AZURE_OPENAI_DEPLOYMENT_EMBEDDING` | Container App env        | `text-embedding-ada-002`                      |
| `PORT`                              | Container App env (auto) | Set by Azure Container Apps, typically `8000` |
