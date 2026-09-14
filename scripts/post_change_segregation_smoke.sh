#!/usr/bin/env bash
# Post-change verification (Plane D/E ops) — platform must stay healthy.
set -euo pipefail

API_URL="${RECOUP_API_URL:-https://qawwrm7kzy.us-east-1.awsapprunner.com}"
BASE="${API_URL%/}"

echo "API health: $BASE"
curl -sf "$BASE/health" | grep -q '"status":"ok"' && echo "OK /health"
curl -sf "$BASE/health/ready" >/dev/null && echo "OK /health/ready"

aws sns list-topics --query "Topics[?contains(TopicArn, 'recoup-alerts')].TopicArn" --output text | grep -q recoup-alerts \
  && echo "OK SNS recoup-alerts"

aws dynamodb list-tables --query "TableNames[?starts_with(@, 'recoup-')]" --output text | grep -q recoup \
  && echo "OK DynamoDB recoup-* tables"

echo "Segregation smoke complete."
