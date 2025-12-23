#!/bin/bash

# CORS Integration Tests for Discovery API Endpoint
# Spec: 002-fix-cors-error-in-discovery-api-endpoint
# Subtask: 3-1
#
# Usage:
#   ./cors-integration-tests.sh           # Run basic tests (no auth required)
#   ./cors-integration-tests.sh <token>   # Run all tests with auth token

set -e

BACKEND_URL="http://localhost:8000"
ORIGIN="http://localhost:5173"
ENDPOINT="/api/v1/discovery/run"
AUTH_TOKEN="${1:-}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================"
echo "CORS Integration Tests"
echo "========================================"
echo "Backend URL: $BACKEND_URL"
echo "Origin: $ORIGIN"
echo "Endpoint: $ENDPOINT"
echo ""

PASSED=0
FAILED=0

# Test function
run_test() {
    local name="$1"
    local expected_status="$2"
    local result="$3"
    local has_cors="$4"

    echo -n "Test: $name... "

    if [[ "$has_cors" == "true" ]] && [[ "$result" == "$expected_status" ]]; then
        echo -e "${GREEN}PASSED${NC} (status: $result, CORS headers present)"
        ((PASSED++))
    elif [[ "$has_cors" != "true" ]]; then
        echo -e "${RED}FAILED${NC} - Missing CORS headers"
        ((FAILED++))
    else
        echo -e "${RED}FAILED${NC} (expected: $expected_status, got: $result)"
        ((FAILED++))
    fi
}

# ============================================
# TEST 1: OPTIONS Preflight Request
# ============================================

echo ""
echo "--- Test 1: OPTIONS Preflight ---"

PREFLIGHT_RESPONSE=$(curl -s -D - -o /dev/null -X OPTIONS "$BACKEND_URL$ENDPOINT" \
    -H "Origin: $ORIGIN" \
    -H "Access-Control-Request-Method: POST" \
    -H "Access-Control-Request-Headers: Content-Type, Authorization" 2>&1)

PREFLIGHT_STATUS=$(echo "$PREFLIGHT_RESPONSE" | grep "HTTP/" | head -1 | awk '{print $2}')
PREFLIGHT_CORS=$(echo "$PREFLIGHT_RESPONSE" | grep -i "access-control-allow-origin" | grep -q "$ORIGIN" && echo "true" || echo "false")

run_test "OPTIONS Preflight returns 200" "200" "$PREFLIGHT_STATUS" "$PREFLIGHT_CORS"

# Check all CORS headers
echo "  Checking CORS headers..."
echo "$PREFLIGHT_RESPONSE" | grep -i "access-control-" | while read line; do
    echo "    $line"
done

# ============================================
# TEST 2: POST Without Auth (401)
# ============================================

echo ""
echo "--- Test 2: POST Without Auth ---"

NO_AUTH_RESPONSE=$(curl -s -D - -o /dev/null -X POST "$BACKEND_URL$ENDPOINT" \
    -H "Origin: $ORIGIN" \
    -H "Content-Type: application/json" \
    -d '{}' 2>&1)

NO_AUTH_STATUS=$(echo "$NO_AUTH_RESPONSE" | grep "HTTP/" | head -1 | awk '{print $2}')
NO_AUTH_CORS=$(echo "$NO_AUTH_RESPONSE" | grep -i "access-control-allow-origin" | grep -q "$ORIGIN" && echo "true" || echo "false")

run_test "POST without auth returns 401 with CORS" "401" "$NO_AUTH_STATUS" "$NO_AUTH_CORS"

# ============================================
# TEST 3: POST With Invalid Token (401)
# ============================================

echo ""
echo "--- Test 3: POST With Invalid Token ---"

INVALID_TOKEN_RESPONSE=$(curl -s -D - -o /dev/null -X POST "$BACKEND_URL$ENDPOINT" \
    -H "Origin: $ORIGIN" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer invalid_token_12345" \
    -d '{}' 2>&1)

INVALID_TOKEN_STATUS=$(echo "$INVALID_TOKEN_RESPONSE" | grep "HTTP/" | head -1 | awk '{print $2}')
INVALID_TOKEN_CORS=$(echo "$INVALID_TOKEN_RESPONSE" | grep -i "access-control-allow-origin" | grep -q "$ORIGIN" && echo "true" || echo "false")

run_test "POST with invalid token returns 401 with CORS" "401" "$INVALID_TOKEN_STATUS" "$INVALID_TOKEN_CORS"

# ============================================
# TEST 4: POST With Valid Auth (requires token)
# ============================================

echo ""
echo "--- Test 4: POST With Valid Auth ---"

if [ -n "$AUTH_TOKEN" ]; then
    VALID_AUTH_RESPONSE=$(curl -s -D - -X POST "$BACKEND_URL$ENDPOINT" \
        -H "Origin: $ORIGIN" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -d '{}' 2>&1)

    VALID_AUTH_STATUS=$(echo "$VALID_AUTH_RESPONSE" | grep "HTTP/" | head -1 | awk '{print $2}')
    VALID_AUTH_CORS=$(echo "$VALID_AUTH_RESPONSE" | grep -i "access-control-allow-origin" | grep -q "$ORIGIN" && echo "true" || echo "false")

    # Accept 200, 201, or 500 (500 if DB issues but should still have CORS)
    if [[ "$VALID_AUTH_STATUS" =~ ^(200|201|500)$ ]]; then
        run_test "POST with valid auth returns success with CORS" "$VALID_AUTH_STATUS" "$VALID_AUTH_STATUS" "$VALID_AUTH_CORS"
    else
        run_test "POST with valid auth returns success with CORS" "200/201/500" "$VALID_AUTH_STATUS" "$VALID_AUTH_CORS"
    fi

    # Show response body
    echo "  Response body:"
    echo "$VALID_AUTH_RESPONSE" | tail -1 | head -c 500
    echo ""
else
    echo -e "  ${YELLOW}SKIPPED${NC} - No auth token provided"
    echo "  To run: ./cors-integration-tests.sh <your-supabase-jwt-token>"
fi

# ============================================
# TEST 5: Disallowed Origin (no CORS headers)
# ============================================

echo ""
echo "--- Test 5: Disallowed Origin ---"

BAD_ORIGIN_RESPONSE=$(curl -s -D - -o /dev/null -X OPTIONS "$BACKEND_URL$ENDPOINT" \
    -H "Origin: http://evil.com" \
    -H "Access-Control-Request-Method: POST" 2>&1)

BAD_ORIGIN_CORS=$(echo "$BAD_ORIGIN_RESPONSE" | grep -i "access-control-allow-origin" | grep -q "evil.com" && echo "true" || echo "false")

if [[ "$BAD_ORIGIN_CORS" == "false" ]]; then
    echo -e "Test: Disallowed origin has no CORS headers... ${GREEN}PASSED${NC}"
    ((PASSED++))
else
    echo -e "Test: Disallowed origin has no CORS headers... ${RED}FAILED${NC}"
    ((FAILED++))
fi

# ============================================
# SUMMARY
# ============================================

echo ""
echo "========================================"
echo "Test Summary"
echo "========================================"
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed.${NC}"
    exit 1
fi
