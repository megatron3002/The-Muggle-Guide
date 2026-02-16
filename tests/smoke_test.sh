#!/bin/bash
# ============================================
# Smoke Test Script for Book Recommendation System
# Run after: docker-compose up -d
# ============================================

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost/api}"
PASS=0
FAIL=0

green() { echo -e "\033[32m✓ $1\033[0m"; }
red() { echo -e "\033[31m✗ $1\033[0m"; }

test_endpoint() {
    local desc="$1"
    local expected_code="$2"
    local method="$3"
    local url="$4"
    shift 4
    local extra_args=("$@")

    local response
    response=$(curl -s -w "\n%{http_code}" -X "$method" "$url" "${extra_args[@]}" 2>/dev/null)
    local code=$(echo "$response" | tail -1)
    local body=$(echo "$response" | sed '$d')

    if [ "$code" = "$expected_code" ]; then
        green "$desc (HTTP $code)"
        PASS=$((PASS + 1))
    else
        red "$desc — expected $expected_code, got $code"
        echo "  Response: $body"
        FAIL=$((FAIL + 1))
    fi

    echo "$body"
}

echo ""
echo "=========================================="
echo " Book Recommendation System — Smoke Tests"
echo "=========================================="
echo ""

# 1. Health Check
echo "── Health Checks ──"
test_endpoint "NGINX health" "200" GET "http://localhost/nginx-health"
echo ""
test_endpoint "API health" "200" GET "$BASE_URL/health"
echo ""
test_endpoint "API liveness" "200" GET "$BASE_URL/live"
echo ""

# 2. Register
echo "── Authentication ──"
REGISTER_BODY=$(test_endpoint "Register user" "201" POST "$BASE_URL/auth/register" \
    -H "Content-Type: application/json" \
    -d '{"email":"smoke@test.com","username":"smokeuser","password":"SmokeTest123"}')
echo ""

ACCESS_TOKEN=$(echo "$REGISTER_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || echo "")
REFRESH_TOKEN=$(echo "$REGISTER_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('refresh_token',''))" 2>/dev/null || echo "")

if [ -z "$ACCESS_TOKEN" ]; then
    # Try login instead (user might already exist)
    LOGIN_BODY=$(test_endpoint "Login user" "200" POST "$BASE_URL/auth/login" \
        -H "Content-Type: application/json" \
        -d '{"email":"smoke@test.com","password":"SmokeTest123"}')
    ACCESS_TOKEN=$(echo "$LOGIN_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || echo "")
    REFRESH_TOKEN=$(echo "$LOGIN_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('refresh_token',''))" 2>/dev/null || echo "")
fi

AUTH_HEADER="Authorization: Bearer $ACCESS_TOKEN"

# 3. Token Refresh
test_endpoint "Refresh token" "200" POST "$BASE_URL/auth/refresh" \
    -H "Content-Type: application/json" \
    -d "{\"refresh_token\":\"$REFRESH_TOKEN\"}"
echo ""

# 4. Books
echo "── Book Operations ──"
test_endpoint "List books (requires auth)" "200" GET "$BASE_URL/books" \
    -H "$AUTH_HEADER"
echo ""

# 5. RBAC Test — non-admin cannot retrain
echo "── RBAC Tests ──"
test_endpoint "Non-admin retrain (should 403)" "403" POST "$BASE_URL/admin/retrain" \
    -H "$AUTH_HEADER"
echo ""

# 6. Recommendations
echo "── Recommendations ──"
test_endpoint "Top recommendations" "200" GET "$BASE_URL/recommendations/top?n=5" \
    -H "$AUTH_HEADER" || true
echo ""
test_endpoint "Similar books" "200" GET "$BASE_URL/recommendations/similar/1?n=5" \
    -H "$AUTH_HEADER" || true
echo ""

# 7. Rate Limiting Test
echo "── Rate Limiting ──"
echo "Sending 12 rapid requests..."
for i in $(seq 1 12); do
    code=$(curl -s -o /dev/null -w "%{http_code}" -X GET "$BASE_URL/health")
    if [ "$code" = "429" ]; then
        green "Rate limit triggered at request $i (HTTP 429)"
        PASS=$((PASS + 1))
        break
    fi
    if [ "$i" = "12" ]; then
        echo "  (Rate limiting may not trigger for /health — it's excluded)"
    fi
done
echo ""

# 8. Metrics
echo "── Monitoring ──"
test_endpoint "Prometheus metrics" "200" GET "$BASE_URL/metrics"
echo ""

# Summary
echo "=========================================="
echo " Results: $PASS passed, $FAIL failed"
echo "=========================================="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
