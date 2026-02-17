#!/usr/bin/env bash
# =============================================================================
# GrantScope2 — Azure Deployment Orchestrator
# =============================================================================
# Deploys infrastructure (Bicep), container images (ACR), and frontend (SWA)
# for the City of Austin AI-powered grant discovery platform.
#
# Usage:
#   ./infrastructure/deploy.sh <environment> --resource-group <rg> [options]
#
# Examples:
#   ./infrastructure/deploy.sh prod -g rg-aph-cognitive-sandbox-dev-scus-01
#   ./infrastructure/deploy.sh prod -g rg-aph-cognitive-sandbox-dev-scus-01 --push
#   ./infrastructure/deploy.sh prod -g rg-aph-cognitive-sandbox-dev-scus-01 --push --skip-infra
#   ./infrastructure/deploy.sh prod -g rg-aph-cognitive-sandbox-dev-scus-01 --frontend
#   ./infrastructure/deploy.sh prod -g rg-aph-cognitive-sandbox-dev-scus-01 --push --frontend
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
readonly BASE_NAME="grantscope2"
readonly ACR_IMAGE="grantscope2-api"

# ---------------------------------------------------------------------------
# Color output helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
header()  { echo -e "\n${BOLD}========== $* ==========${NC}\n"; }

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------
usage() {
  cat <<'USAGE'
GrantScope2 Deployment Script

USAGE:
  ./infrastructure/deploy.sh <environment> --resource-group <rg> [options]

ARGUMENTS:
  <environment>       Required. One of: dev, staging, prod

OPTIONS:
  -g, --resource-group <name>   Required. Azure resource group name.
  --push                        Build and push Docker image, then update container apps.
  --skip-infra                  Skip Bicep infrastructure deployment.
  --frontend                    Build and deploy frontend to Azure Static Web App.
  --image-tag <tag>             Override image tag (default: v1.0.0-YYYYMMDD-<git-hash>).
  --postgres-password <pw>      PostgreSQL admin password (prompted interactively if
                                not provided and infrastructure deployment is enabled).
  -h, --help                    Show this help message and exit.

EXAMPLES:
  # Deploy infrastructure only
  ./infrastructure/deploy.sh prod -g rg-aph-cognitive-sandbox-dev-scus-01

  # Deploy infrastructure + build/push image + update container apps
  ./infrastructure/deploy.sh prod -g rg-aph-cognitive-sandbox-dev-scus-01 --push

  # Build and push image only (skip infrastructure)
  ./infrastructure/deploy.sh prod -g rg-aph-cognitive-sandbox-dev-scus-01 --push --skip-infra

  # Deploy frontend only
  ./infrastructure/deploy.sh prod -g rg-aph-cognitive-sandbox-dev-scus-01 --frontend --skip-infra

  # Full deployment (infra + backend + frontend)
  ./infrastructure/deploy.sh prod -g rg-aph-cognitive-sandbox-dev-scus-01 --push --frontend
USAGE
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
ENVIRONMENT=""
RESOURCE_GROUP=""
PUSH=false
SKIP_INFRA=false
FRONTEND=false
IMAGE_TAG=""
POSTGRES_PASSWORD=""

parse_args() {
  if [[ $# -eq 0 ]]; then
    usage
    exit 1
  fi

  # First positional argument is the environment
  case "${1:-}" in
    -h|--help)
      usage
      exit 0
      ;;
    dev|staging|prod)
      ENVIRONMENT="$1"
      shift
      ;;
    *)
      error "Invalid environment '${1:-}'. Must be one of: dev, staging, prod."
      echo ""
      usage
      exit 1
      ;;
  esac

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -g|--resource-group)
        RESOURCE_GROUP="${2:?'--resource-group requires a value'}"
        shift 2
        ;;
      --push)
        PUSH=true
        shift
        ;;
      --skip-infra)
        SKIP_INFRA=true
        shift
        ;;
      --frontend)
        FRONTEND=true
        shift
        ;;
      --image-tag)
        IMAGE_TAG="${2:?'--image-tag requires a value'}"
        shift 2
        ;;
      --postgres-password)
        POSTGRES_PASSWORD="${2:?'--postgres-password requires a value'}"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        error "Unknown option: $1"
        echo ""
        usage
        exit 1
        ;;
    esac
  done

  # Validate required arguments
  if [[ -z "$RESOURCE_GROUP" ]]; then
    error "Missing required option: --resource-group (-g)"
    echo ""
    usage
    exit 1
  fi
}

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
validate_prerequisites() {
  header "Validating prerequisites"

  # Must run from repo root
  if [[ ! -f "$REPO_ROOT/backend/Dockerfile" ]]; then
    error "Cannot find backend/Dockerfile. This script must be run from the repository root."
    error "Expected repo root: $REPO_ROOT"
    exit 1
  fi
  success "Repository root verified: $REPO_ROOT"

  # Check Bicep templates exist
  if [[ "$SKIP_INFRA" == false ]]; then
    if [[ ! -f "$SCRIPT_DIR/main.bicep" ]]; then
      error "Cannot find infrastructure/main.bicep. Bicep templates are missing."
      exit 1
    fi
    local param_file="$SCRIPT_DIR/parameters/${ENVIRONMENT}.bicepparam"
    if [[ ! -f "$param_file" ]]; then
      error "Cannot find parameter file: $param_file"
      error "Create infrastructure/parameters/${ENVIRONMENT}.bicepparam before deploying."
      exit 1
    fi
    success "Bicep templates and parameters found"
  fi

  # Azure CLI
  if ! command -v az &>/dev/null; then
    error "Azure CLI (az) is not installed. Install from: https://aka.ms/install-azure-cli"
    exit 1
  fi
  if ! az account show &>/dev/null; then
    error "Azure CLI is not logged in. Run 'az login' first."
    exit 1
  fi
  local account_name
  account_name=$(az account show --query name -o tsv 2>/dev/null)
  success "Azure CLI authenticated (subscription: $account_name)"

  # Resource group exists
  if ! az group show --name "$RESOURCE_GROUP" &>/dev/null; then
    error "Resource group '$RESOURCE_GROUP' does not exist or you lack access."
    exit 1
  fi
  success "Resource group '$RESOURCE_GROUP' exists"

  # Docker (only if pushing)
  if [[ "$PUSH" == true ]]; then
    if ! command -v docker &>/dev/null; then
      error "Docker is not installed. Required for --push. Install from: https://docs.docker.com/get-docker/"
      exit 1
    fi
    if ! docker info &>/dev/null; then
      error "Docker daemon is not running. Start Docker Desktop or the Docker service."
      exit 1
    fi
    success "Docker is available"
  fi

  # pnpm (only if deploying frontend)
  if [[ "$FRONTEND" == true ]]; then
    if ! command -v pnpm &>/dev/null; then
      error "pnpm is not installed. Required for --frontend. Install with: npm install -g pnpm"
      exit 1
    fi
    success "pnpm is available"

    if ! command -v npx &>/dev/null; then
      error "npx is not installed. Required for Static Web App deployment."
      exit 1
    fi
    success "npx is available"
  fi

  # Default image tag
  if [[ -z "$IMAGE_TAG" ]]; then
    local git_hash
    git_hash=$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo "unknown")
    IMAGE_TAG="v1.0.0-$(date +%Y%m%d)-${git_hash}"
  fi
  info "Image tag: $IMAGE_TAG"
  info "Environment: $ENVIRONMENT"
}

# ---------------------------------------------------------------------------
# Phase 1: Infrastructure Deployment
# ---------------------------------------------------------------------------
deploy_infrastructure() {
  header "Phase 1: Infrastructure Deployment (Bicep)"

  # Prompt for PostgreSQL password if not provided
  if [[ -z "$POSTGRES_PASSWORD" ]]; then
    echo -n "Enter PostgreSQL admin password: "
    read -rs POSTGRES_PASSWORD
    echo ""
    if [[ -z "$POSTGRES_PASSWORD" ]]; then
      error "PostgreSQL admin password cannot be empty."
      exit 1
    fi
    # Confirm password
    echo -n "Confirm PostgreSQL admin password: "
    local confirm_password
    read -rs confirm_password
    echo ""
    if [[ "$POSTGRES_PASSWORD" != "$confirm_password" ]]; then
      error "Passwords do not match."
      exit 1
    fi
  fi

  info "Deploying Bicep templates to resource group: $RESOURCE_GROUP"
  info "Template: infrastructure/main.bicep"
  info "Parameters: infrastructure/parameters/${ENVIRONMENT}.bicepparam"

  local deployment_name="grantscope2-${ENVIRONMENT}-$(date +%Y%m%d%H%M%S)"

  az deployment group create \
    --name "$deployment_name" \
    --resource-group "$RESOURCE_GROUP" \
    --template-file "$SCRIPT_DIR/main.bicep" \
    --parameters "$SCRIPT_DIR/parameters/${ENVIRONMENT}.bicepparam" \
    --parameters postgresAdminPassword="$POSTGRES_PASSWORD" \
    --parameters imageTag="$IMAGE_TAG" \
    --output table

  success "Infrastructure deployment complete: $deployment_name"

  # Print deployment outputs
  info "Deployment outputs:"
  az deployment group show \
    --name "$deployment_name" \
    --resource-group "$RESOURCE_GROUP" \
    --query 'properties.outputs' \
    --output table 2>/dev/null || warn "Could not retrieve deployment outputs"

  # Assign RBAC roles for managed identities
  assign_rbac_roles "$deployment_name"
}

# ---------------------------------------------------------------------------
# Phase 1b: RBAC Role Assignments (post-infrastructure)
# ---------------------------------------------------------------------------
assign_rbac_roles() {
  local deployment_name="$1"

  info "Assigning RBAC roles to container app managed identities..."

  # Get principal IDs from deployment outputs
  local api_principal_id worker_principal_id acr_name kv_name
  api_principal_id=$(az deployment group show \
    --name "$deployment_name" \
    --resource-group "$RESOURCE_GROUP" \
    --query 'properties.outputs.apiPrincipalId.value' -o tsv 2>/dev/null) || true
  worker_principal_id=$(az deployment group show \
    --name "$deployment_name" \
    --resource-group "$RESOURCE_GROUP" \
    --query 'properties.outputs.workerPrincipalId.value' -o tsv 2>/dev/null) || true
  acr_name=$(az deployment group show \
    --name "$deployment_name" \
    --resource-group "$RESOURCE_GROUP" \
    --query 'properties.outputs.acrName.value' -o tsv 2>/dev/null) || true
  kv_name=$(az deployment group show \
    --name "$deployment_name" \
    --resource-group "$RESOURCE_GROUP" \
    --query 'properties.outputs.keyVaultName.value' -o tsv 2>/dev/null) || true

  if [[ -z "$api_principal_id" || -z "$worker_principal_id" ]]; then
    warn "Could not retrieve managed identity principal IDs from deployment outputs."
    warn "RBAC roles must be assigned manually. See deployment docs."
    return
  fi

  # AcrPull role for both container apps
  if [[ -n "$acr_name" ]]; then
    local acr_id
    acr_id=$(az acr show --name "$acr_name" --query id -o tsv 2>/dev/null) || true
    if [[ -n "$acr_id" ]]; then
      info "Assigning AcrPull on $acr_name..."
      az role assignment create --assignee-object-id "$api_principal_id" \
        --assignee-principal-type ServicePrincipal \
        --role "AcrPull" --scope "$acr_id" --only-show-errors 2>/dev/null || true
      az role assignment create --assignee-object-id "$worker_principal_id" \
        --assignee-principal-type ServicePrincipal \
        --role "AcrPull" --scope "$acr_id" --only-show-errors 2>/dev/null || true
      success "AcrPull assigned to API and Worker"
    fi
  fi

  # Key Vault Secrets User for both container apps
  if [[ -n "$kv_name" ]]; then
    local kv_id
    kv_id=$(az keyvault show --name "$kv_name" --query id -o tsv 2>/dev/null) || true
    if [[ -n "$kv_id" ]]; then
      info "Assigning Key Vault Secrets User on $kv_name..."
      az role assignment create --assignee-object-id "$api_principal_id" \
        --assignee-principal-type ServicePrincipal \
        --role "Key Vault Secrets User" --scope "$kv_id" --only-show-errors 2>/dev/null || true
      az role assignment create --assignee-object-id "$worker_principal_id" \
        --assignee-principal-type ServicePrincipal \
        --role "Key Vault Secrets User" --scope "$kv_id" --only-show-errors 2>/dev/null || true
      success "Key Vault Secrets User assigned to API and Worker"
    fi
  fi
}

# ---------------------------------------------------------------------------
# Phase 2: Docker Build + Push + Container App Update
# ---------------------------------------------------------------------------
build_and_push() {
  header "Phase 2: Docker Build, Push, and Container App Update"

  # Get ACR details from the deployed resources
  local acr_name
  acr_name=$(az acr list --resource-group "$RESOURCE_GROUP" \
    --query "[?contains(name, '${BASE_NAME}')].name" -o tsv 2>/dev/null | head -1)

  if [[ -z "$acr_name" ]]; then
    error "Could not find Azure Container Registry in resource group '$RESOURCE_GROUP'."
    error "Deploy infrastructure first, or check that ACR name contains '${BASE_NAME}'."
    exit 1
  fi

  local acr_server
  acr_server=$(az acr show --name "$acr_name" --query loginServer -o tsv)

  info "ACR: $acr_name ($acr_server)"
  info "Image: ${acr_server}/${ACR_IMAGE}:${IMAGE_TAG}"

  # Login to ACR
  info "Logging into ACR..."
  az acr login --name "$acr_name"
  success "ACR login successful"

  # Build and push image
  info "Building Docker image (linux/amd64)..."
  docker buildx build \
    --platform linux/amd64 \
    -t "${acr_server}/${ACR_IMAGE}:${IMAGE_TAG}" \
    -t "${acr_server}/${ACR_IMAGE}:latest" \
    -f "$REPO_ROOT/backend/Dockerfile" \
    --push \
    "$REPO_ROOT"
  success "Docker image pushed: ${acr_server}/${ACR_IMAGE}:${IMAGE_TAG}"

  # Update API container app
  local api_app_name="ca-${BASE_NAME}-api-${ENVIRONMENT}"
  info "Updating container app: $api_app_name"
  az containerapp update \
    --resource-group "$RESOURCE_GROUP" \
    --name "$api_app_name" \
    --image "${acr_server}/${ACR_IMAGE}:${IMAGE_TAG}" \
    --output table
  success "API container app updated"

  # Update Worker container app
  local worker_app_name="ca-${BASE_NAME}-worker-${ENVIRONMENT}"
  info "Updating container app: $worker_app_name"
  az containerapp update \
    --resource-group "$RESOURCE_GROUP" \
    --name "$worker_app_name" \
    --image "${acr_server}/${ACR_IMAGE}:${IMAGE_TAG}" \
    --output table
  success "Worker container app updated"
}

# ---------------------------------------------------------------------------
# Phase 3: Frontend Deployment
# ---------------------------------------------------------------------------
deploy_frontend() {
  header "Phase 3: Frontend Deployment (Static Web App)"

  local frontend_dir="$REPO_ROOT/frontend/foresight-frontend"

  if [[ ! -d "$frontend_dir" ]]; then
    error "Frontend directory not found: $frontend_dir"
    exit 1
  fi

  # Get API FQDN for environment variable injection
  local api_app_name="ca-${BASE_NAME}-api-${ENVIRONMENT}"
  local api_fqdn
  api_fqdn=$(az containerapp show \
    --resource-group "$RESOURCE_GROUP" \
    --name "$api_app_name" \
    --query properties.configuration.ingress.fqdn \
    -o tsv 2>/dev/null) || true

  if [[ -z "$api_fqdn" ]]; then
    warn "Could not retrieve API FQDN from container app '$api_app_name'."
    warn "Frontend will build without VITE_API_URL. Set it manually if needed."
  else
    info "API endpoint: https://${api_fqdn}"
  fi

  # Install dependencies
  info "Installing frontend dependencies..."
  (cd "$frontend_dir" && pnpm install --frozen-lockfile)
  success "Dependencies installed"

  # Build frontend with API URL
  info "Building frontend..."
  if [[ -n "$api_fqdn" ]]; then
    (cd "$frontend_dir" && VITE_API_URL="https://${api_fqdn}" pnpm build)
  else
    (cd "$frontend_dir" && pnpm build)
  fi
  success "Frontend build complete"

  # Deploy to Static Web App
  local swa_name="swa-${BASE_NAME}-${ENVIRONMENT}"
  info "Deploying to Static Web App: $swa_name"
  (cd "$frontend_dir" && npx @azure/static-web-apps-cli deploy dist \
    --app-name "$swa_name" \
    --env production)
  success "Frontend deployed to Static Web App"
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print_summary() {
  header "Deployment Summary"

  echo -e "${BOLD}Environment:${NC}    $ENVIRONMENT"
  echo -e "${BOLD}Resource Group:${NC} $RESOURCE_GROUP"
  echo -e "${BOLD}Image Tag:${NC}      $IMAGE_TAG"
  echo ""

  # Infrastructure
  if [[ "$SKIP_INFRA" == false ]]; then
    echo -e "  ${GREEN}+${NC} Infrastructure deployed (Bicep)"
  else
    echo -e "  ${YELLOW}-${NC} Infrastructure skipped"
  fi

  # Backend
  if [[ "$PUSH" == true ]]; then
    echo -e "  ${GREEN}+${NC} Docker image built and pushed"
    echo -e "  ${GREEN}+${NC} API container app updated (ca-${BASE_NAME}-api-${ENVIRONMENT})"
    echo -e "  ${GREEN}+${NC} Worker container app updated (ca-${BASE_NAME}-worker-${ENVIRONMENT})"
  else
    echo -e "  ${YELLOW}-${NC} Docker image build/push skipped"
  fi

  # Frontend
  if [[ "$FRONTEND" == true ]]; then
    echo -e "  ${GREEN}+${NC} Frontend deployed (swa-${BASE_NAME}-${ENVIRONMENT})"
  else
    echo -e "  ${YELLOW}-${NC} Frontend deployment skipped"
  fi

  echo ""

  # Print resource URLs
  info "Fetching resource URLs..."

  # API URL
  local api_fqdn
  api_fqdn=$(az containerapp show \
    --resource-group "$RESOURCE_GROUP" \
    --name "ca-${BASE_NAME}-api-${ENVIRONMENT}" \
    --query properties.configuration.ingress.fqdn \
    -o tsv 2>/dev/null) || true
  if [[ -n "$api_fqdn" ]]; then
    echo -e "  ${BOLD}API:${NC}      https://${api_fqdn}"
    echo -e "  ${BOLD}API Docs:${NC} https://${api_fqdn}/docs"
  fi

  # SWA URL
  local swa_fqdn
  swa_fqdn=$(az staticwebapp show \
    --resource-group "$RESOURCE_GROUP" \
    --name "swa-${BASE_NAME}-${ENVIRONMENT}" \
    --query defaultHostname \
    -o tsv 2>/dev/null) || true
  if [[ -n "$swa_fqdn" ]]; then
    echo -e "  ${BOLD}Frontend:${NC} https://${swa_fqdn}"
  fi

  # PostgreSQL
  local pg_fqdn
  pg_fqdn=$(az postgres flexible-server list \
    --resource-group "$RESOURCE_GROUP" \
    --query "[?contains(name, '${BASE_NAME}')].fullyQualifiedDomainName" \
    -o tsv 2>/dev/null | head -1) || true
  if [[ -n "$pg_fqdn" ]]; then
    echo -e "  ${BOLD}Postgres:${NC} ${pg_fqdn}"
  fi

  echo ""
  success "Deployment complete."
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
  parse_args "$@"
  validate_prerequisites

  # Phase 1: Infrastructure
  if [[ "$SKIP_INFRA" == false ]]; then
    deploy_infrastructure
  else
    info "Skipping infrastructure deployment (--skip-infra)"
  fi

  # Phase 2: Docker build + push
  if [[ "$PUSH" == true ]]; then
    build_and_push
  fi

  # Phase 3: Frontend
  if [[ "$FRONTEND" == true ]]; then
    deploy_frontend
  fi

  # Summary
  print_summary
}

main "$@"
