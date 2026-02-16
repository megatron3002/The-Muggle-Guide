#!/bin/bash
# ============================================
# LocalStack initialization script
# Creates S3 bucket and Secrets Manager secret
# Runs automatically when LocalStack starts
# ============================================

set -euo pipefail

echo ">> Initializing LocalStack AWS resources..."

# ── Create S3 Bucket for Model Storage ──
awslocal s3 mb s3://bookrec-models 2>/dev/null || true
echo "✓ S3 bucket 'bookrec-models' created"

# ── Pre-create directories in S3 ──
echo "" | awslocal s3 cp - s3://bookrec-models/models/.keep 2>/dev/null || true
echo "✓ S3 models/ prefix initialized"

# ── Create Secrets Manager Secret ──
awslocal secretsmanager create-secret \
  --name "bookrec/production" \
  --description "Book recommendation system secrets" \
  --secret-string '{
    "jwt_secret_key": "localstack-dev-jwt-secret-key-change-in-production-64chars!!",
    "postgres_password": "changeme",
    "redis_password": "changeme"
  }' 2>/dev/null || \
awslocal secretsmanager update-secret \
  --secret-id "bookrec/production" \
  --secret-string '{
    "jwt_secret_key": "localstack-dev-jwt-secret-key-change-in-production-64chars!!",
    "postgres_password": "changeme",
    "redis_password": "changeme"
  }' 2>/dev/null || true
echo "✓ Secrets Manager secret 'bookrec/production' created"

# ── Verify resources ──
echo ""
echo ">> Verifying resources:"
echo "S3 Buckets:"
awslocal s3 ls
echo ""
echo "Secrets:"
awslocal secretsmanager list-secrets --query 'SecretList[].Name' --output text
echo ""
echo ">> LocalStack initialization complete!"
