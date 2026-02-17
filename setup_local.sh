#!/bin/bash
# =============================================================================
# GrantScope2 — Local Development Setup
# =============================================================================
# Sets up the full self-hosted stack: PostgreSQL, PostgREST, GoTrue, SearXNG,
# and the GrantScope backend + frontend.
#
# Prerequisites:
#   - Docker Desktop installed and running
#   - Python 3.11+ installed
#   - Node.js 18+ and pnpm installed
#   - psql (PostgreSQL client) installed
#
# Usage:
#   bash setup_local.sh
# =============================================================================

set -euo pipefail

echo "GrantScope2 — Local Development Setup"
echo "============================================="

# Check if we're in the right directory
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo "ERROR: Please run this script from the project root directory"
    exit 1
fi

# ---------------------------------------------------------------------------
# Prerequisites check
# ---------------------------------------------------------------------------
echo ""
echo "Checking prerequisites..."

MISSING=""

if ! command -v docker &>/dev/null; then
    MISSING="$MISSING docker"
fi

if ! command -v python3 &>/dev/null; then
    MISSING="$MISSING python3"
fi

if ! command -v pnpm &>/dev/null; then
    MISSING="$MISSING pnpm"
fi

if ! command -v psql &>/dev/null; then
    MISSING="$MISSING psql"
fi

if [ -n "$MISSING" ]; then
    echo "ERROR: Missing required tools:$MISSING"
    echo ""
    echo "Install them:"
    echo "  docker  -> https://www.docker.com/products/docker-desktop"
    echo "  python3 -> https://www.python.org/downloads/"
    echo "  pnpm    -> npm install -g pnpm"
    echo "  psql    -> brew install libpq && brew link --force libpq (macOS)"
    exit 1
fi

echo "  docker:  $(docker --version | head -1)"
echo "  python3: $(python3 --version)"
echo "  pnpm:    $(pnpm --version)"
echo "  psql:    $(psql --version | head -1)"
echo ""

# ---------------------------------------------------------------------------
# Step 1: Generate JWT keys
# ---------------------------------------------------------------------------
echo "Step 1: Generating JWT keys..."

if [ -f "backend/.env" ] && grep -q "JWT_SECRET=" backend/.env 2>/dev/null; then
    echo "  JWT keys already configured in backend/.env — skipping"
else
    JWT_OUTPUT=$(python3 infra/generate_keys.py)
    JWT_SECRET=$(echo "$JWT_OUTPUT" | grep "^JWT_SECRET=" | cut -d= -f2)
    SERVICE_KEY=$(echo "$JWT_OUTPUT" | grep "^SUPABASE_SERVICE_KEY=" | cut -d= -f2)
    ANON_KEY=$(echo "$JWT_OUTPUT" | grep "^SUPABASE_ANON_KEY=" | cut -d= -f2)
    echo "  Generated JWT_SECRET, SUPABASE_SERVICE_KEY, SUPABASE_ANON_KEY"
fi

# ---------------------------------------------------------------------------
# Step 2: Create backend .env
# ---------------------------------------------------------------------------
echo ""
echo "Step 2: Configuring backend environment..."

if [ ! -f "backend/.env" ]; then
    cp backend/.env.example backend/.env

    # Fill in self-hosted defaults
    if [ -n "${JWT_SECRET:-}" ]; then
        # Update Supabase URL for local gateway
        sed -i.bak 's|SUPABASE_URL=.*|SUPABASE_URL=http://localhost:3000|' backend/.env
        sed -i.bak "s|SUPABASE_ANON_KEY=.*|SUPABASE_ANON_KEY=$ANON_KEY|" backend/.env
        sed -i.bak "s|SUPABASE_SERVICE_KEY=.*|SUPABASE_SERVICE_KEY=$SERVICE_KEY|" backend/.env
        # Uncomment and set JWT_SECRET
        sed -i.bak "s|# JWT_SECRET=.*|JWT_SECRET=$JWT_SECRET|" backend/.env
        rm -f backend/.env.bak
    fi

    echo "  Created backend/.env with self-hosted defaults"
    echo "  NOTE: You still need to set AZURE_OPENAI_KEY in backend/.env"
else
    echo "  backend/.env already exists — skipping"
fi

# ---------------------------------------------------------------------------
# Step 3: Create frontend .env
# ---------------------------------------------------------------------------
echo ""
echo "Step 3: Configuring frontend environment..."

if [ ! -f "frontend/foresight-frontend/.env" ]; then
    cp frontend/foresight-frontend/.env.example frontend/foresight-frontend/.env

    # Update for local gateway
    if [ -n "${ANON_KEY:-}" ]; then
        sed -i.bak "s|VITE_SUPABASE_URL=.*|VITE_SUPABASE_URL=http://localhost:3000|" frontend/foresight-frontend/.env
        sed -i.bak "s|VITE_SUPABASE_ANON_KEY=.*|VITE_SUPABASE_ANON_KEY=$ANON_KEY|" frontend/foresight-frontend/.env
        rm -f frontend/foresight-frontend/.env.bak
    fi

    echo "  Created frontend/.env with local gateway URL"
else
    echo "  frontend/.env already exists — skipping"
fi

# ---------------------------------------------------------------------------
# Step 4: Start infrastructure containers
# ---------------------------------------------------------------------------
echo ""
echo "Step 4: Starting infrastructure (PostgreSQL, PostgREST, GoTrue, SearXNG)..."

# Export JWT_SECRET for docker-compose
if [ -n "${JWT_SECRET:-}" ]; then
    export JWT_SECRET
fi

docker compose up -d
echo "  Waiting for services to be healthy..."
sleep 10

# Check health
if docker compose ps | grep -q "unhealthy"; then
    echo "  WARNING: Some services are not healthy yet. Waiting 15 more seconds..."
    sleep 15
fi

echo "  Infrastructure services started"

# ---------------------------------------------------------------------------
# Step 5: Run database migrations
# ---------------------------------------------------------------------------
echo ""
echo "Step 5: Running database migrations..."

bash infra/migrate.sh "postgres://postgres:${POSTGRES_PASSWORD:-postgres}@localhost:${POSTGRES_PORT:-5432}/grantscope"

# ---------------------------------------------------------------------------
# Step 6: Install backend dependencies
# ---------------------------------------------------------------------------
echo ""
echo "Step 6: Installing backend Python dependencies..."

cd backend
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt
cd ..

echo "  Backend dependencies installed"

# ---------------------------------------------------------------------------
# Step 7: Install frontend dependencies
# ---------------------------------------------------------------------------
echo ""
echo "Step 7: Installing frontend dependencies..."

cd frontend/foresight-frontend
pnpm install --silent
cd ../..

echo "  Frontend dependencies installed"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "============================================="
echo "Setup Complete!"
echo "============================================="
echo ""
echo "Infrastructure running:"
echo "  PostgreSQL:  localhost:5432"
echo "  API Gateway: localhost:3000 (PostgREST + GoTrue)"
echo "  SearXNG:     localhost:8888"
echo ""
echo "Next steps:"
echo "  1. Set AZURE_OPENAI_KEY in backend/.env"
echo "  2. Start backend:  cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000"
echo "  3. Start frontend: cd frontend/foresight-frontend && pnpm dev"
echo "  4. Open http://localhost:5173"
echo ""
echo "Or start everything in Docker:"
echo "  docker compose --profile app up -d"
echo ""
echo "Create a test user:"
echo "  cd backend && source venv/bin/activate && python create_test_user.py"
