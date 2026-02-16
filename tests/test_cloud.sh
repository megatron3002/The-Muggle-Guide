#!/bin/bash
# ============================================
# Cloud Integration Verification Script
# Validates LocalStack S3 + Secrets Manager
# Run after: docker-compose up -d
# ============================================

set -euo pipefail

LOCALSTACK_URL="${LOCALSTACK_URL:-http://localhost:4566}"
PASS=0
FAIL=0

green() { echo -e "\033[32m✓ $1\033[0m"; }
red() { echo -e "\033[31m✗ $1\033[0m"; }

check() {
    local desc="$1"
    shift
    if "$@" > /dev/null 2>&1; then
        green "$desc"
        PASS=$((PASS + 1))
    else
        red "$desc"
        FAIL=$((FAIL + 1))
    fi
}

echo ""
echo "=========================================="
echo " Cloud Integration Tests (LocalStack)"
echo "=========================================="
echo ""

export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

# ── LocalStack Health ──
echo "── LocalStack Health ──"
check "LocalStack is running" \
    curl -sf "$LOCALSTACK_URL/_localstack/health"
echo ""

# ── S3 Tests ──
echo "── S3 Model Storage ──"
check "S3 bucket 'bookrec-models' exists" \
    aws --endpoint-url="$LOCALSTACK_URL" s3 ls s3://bookrec-models

echo "  Uploading test artifact..."
echo "test-model-data" > /tmp/test_model.pkl
check "Upload model artifact to S3" \
    aws --endpoint-url="$LOCALSTACK_URL" s3 cp /tmp/test_model.pkl s3://bookrec-models/models/test_model_latest.pkl

check "Download model artifact from S3" \
    aws --endpoint-url="$LOCALSTACK_URL" s3 cp s3://bookrec-models/models/test_model_latest.pkl /tmp/test_model_download.pkl

check "Downloaded artifact matches" \
    diff /tmp/test_model.pkl /tmp/test_model_download.pkl

check "List S3 objects" \
    aws --endpoint-url="$LOCALSTACK_URL" s3 ls s3://bookrec-models/models/

# Clean up
aws --endpoint-url="$LOCALSTACK_URL" s3 rm s3://bookrec-models/models/test_model_latest.pkl > /dev/null 2>&1
rm -f /tmp/test_model.pkl /tmp/test_model_download.pkl
echo ""

# ── Secrets Manager Tests ──
echo "── Secrets Manager ──"
SECRET_VALUE=$(aws --endpoint-url="$LOCALSTACK_URL" secretsmanager get-secret-value \
    --secret-id "bookrec/production" \
    --query 'SecretString' --output text 2>/dev/null || echo "")

if [ -n "$SECRET_VALUE" ]; then
    green "Secret 'bookrec/production' exists"
    PASS=$((PASS + 1))

    # Verify secret contains expected keys
    for key in jwt_secret_key postgres_password redis_password; do
        if echo "$SECRET_VALUE" | python3 -c "import sys,json; d=json.load(sys.stdin); assert '$key' in d" 2>/dev/null; then
            green "  Secret contains key: $key"
            PASS=$((PASS + 1))
        else
            red "  Secret missing key: $key"
            FAIL=$((FAIL + 1))
        fi
    done
else
    red "Secret 'bookrec/production' not found"
    FAIL=$((FAIL + 1))
fi
echo ""

# ── API Service Integration ──
echo "── API Service → AWS Integration ──"
API_HEALTH=$(curl -sf http://localhost/api/health 2>/dev/null || echo "")
if [ -n "$API_HEALTH" ]; then
    green "API service healthy (uses Secrets Manager for config)"
else
    echo "  (API not running — skipping live integration check)"
fi
echo ""

# Summary
echo "=========================================="
echo " Results: $PASS passed, $FAIL failed"
echo "=========================================="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
