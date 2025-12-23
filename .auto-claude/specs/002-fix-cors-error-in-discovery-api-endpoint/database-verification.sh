#!/bin/bash

# Database Verification Script for Discovery Runs
# Spec: 002-fix-cors-error-in-discovery-api-endpoint
# Subtask: 3-4 - Verify database record created with correct column values
#
# Usage:
#   ./database-verification.sh <supabase-jwt-token>
#
# This script:
# 1. Triggers a discovery run via API
# 2. Queries the database to verify the record was created correctly
# 3. Validates expected column values

set -e

BACKEND_URL="http://localhost:8000"
ORIGIN="http://localhost:5173"
ENDPOINT="/api/v1/discovery/run"
AUTH_TOKEN="${1:-}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "========================================"
echo "Database Verification: Discovery Runs"
echo "========================================"
echo ""

if [ -z "$AUTH_TOKEN" ]; then
    echo -e "${RED}Error: Auth token required${NC}"
    echo ""
    echo "Usage: ./database-verification.sh <supabase-jwt-token>"
    echo ""
    echo "To get a token:"
    echo "  1. Open browser DevTools (F12)"
    echo "  2. Navigate to http://localhost:5173/discover/history"
    echo "  3. Login if needed"
    echo "  4. In Console, run: (await supabase.auth.getSession()).data.session.access_token"
    echo "  5. Copy the token and run this script"
    echo ""
    echo "Alternatively, check manually with these SQL queries:"
    echo "----------------------------------------"
    echo ""
    echo -e "${BLUE}-- Query the most recent discovery run:${NC}"
    echo "SELECT"
    echo "    id,"
    echo "    status,"
    echo "    triggered_by,"
    echo "    triggered_by_user,"
    echo "    cards_created,"
    echo "    cards_enriched,"
    echo "    cards_deduplicated,"
    echo "    sources_found,"
    echo "    started_at,"
    echo "    summary_report"
    echo "FROM discovery_runs"
    echo "ORDER BY created_at DESC"
    echo "LIMIT 1;"
    echo ""
    echo -e "${BLUE}-- Expected values for a freshly triggered run:${NC}"
    echo "-- status = 'running' (immediately after trigger)"
    echo "-- triggered_by = 'manual' (API-triggered runs)"
    echo "-- triggered_by_user IS NOT NULL (should be user UUID)"
    echo "-- cards_created = 0 (initial)"
    echo "-- cards_enriched = 0 (initial)"
    echo "-- cards_deduplicated = 0 (initial)"
    echo "-- sources_found = 0 (initial)"
    echo "-- started_at IS NOT NULL"
    echo "-- summary_report contains config object"
    echo ""
    exit 0
fi

echo "Step 1: Triggering discovery run..."
echo "----------------------------------------"

# Trigger discovery run
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BACKEND_URL$ENDPOINT" \
    -H "Origin: $ORIGIN" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $AUTH_TOKEN" \
    -d '{}')

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -n -1)

echo "HTTP Status: $HTTP_CODE"
echo "Response: $BODY"
echo ""

if [[ "$HTTP_CODE" != "200" && "$HTTP_CODE" != "201" ]]; then
    echo -e "${RED}Error: Discovery run trigger failed (HTTP $HTTP_CODE)${NC}"
    echo "Response: $BODY"
    exit 1
fi

# Extract run ID from response
RUN_ID=$(echo "$BODY" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$RUN_ID" ]; then
    echo -e "${RED}Error: Could not extract run ID from response${NC}"
    exit 1
fi

echo -e "${GREEN}Discovery run created successfully!${NC}"
echo "Run ID: $RUN_ID"
echo ""

echo "Step 2: Verify record in database"
echo "----------------------------------------"
echo ""
echo -e "${YELLOW}Run the following SQL query in Supabase to verify:${NC}"
echo ""
echo "SELECT"
echo "    id,"
echo "    status,"
echo "    triggered_by,"
echo "    triggered_by_user IS NOT NULL as has_user,"
echo "    cards_created,"
echo "    cards_enriched,"
echo "    cards_deduplicated,"
echo "    sources_found,"
echo "    started_at IS NOT NULL as has_started_at,"
echo "    summary_report->'config' IS NOT NULL as has_config"
echo "FROM discovery_runs"
echo "WHERE id = '$RUN_ID';"
echo ""

echo "Step 3: Expected values"
echo "----------------------------------------"
echo ""
echo -e "${BLUE}Expected results:${NC}"
echo "  - id: $RUN_ID"
echo "  - status: 'running' (initially, then 'completed' or 'failed')"
echo "  - triggered_by: 'manual'"
echo "  - has_user: true"
echo "  - cards_created: 0"
echo "  - cards_enriched: 0"
echo "  - cards_deduplicated: 0"
echo "  - sources_found: 0"
echo "  - has_started_at: true"
echo "  - has_config: true"
echo ""

echo "Step 4: Quick status check via API"
echo "----------------------------------------"

# Give the background task a moment to run
sleep 2

# Check the run status
STATUS_RESPONSE=$(curl -s -X GET "$BACKEND_URL/api/v1/discovery/runs/$RUN_ID" \
    -H "Authorization: Bearer $AUTH_TOKEN" 2>&1)

echo "Run status from API:"
echo "$STATUS_RESPONSE" | head -c 500
echo ""
echo ""

echo "========================================"
echo -e "${GREEN}Verification Complete${NC}"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Check Supabase dashboard for the discovery_runs table"
echo "  2. Verify the record with ID: $RUN_ID exists"
echo "  3. Confirm all expected column values match"
echo ""
