#!/usr/bin/env bash
# Post-deploy smoke checks (Plane A + B). Does not mutate demo scanner targets.
set -euo pipefail
API_URL="${1:-${RECOUP_API_URL:-}}"

if [[ -z "$API_URL" ]]; then
  API_URL=$(aws cloudformation describe-stacks --stack-name RecoupAppStack \
    --query "Stacks[0].Outputs[?OutputKey=='AppRunnerServiceUrl'].OutputValue" --output text 2>/dev/null || true)
fi

if [[ -z "$API_URL" || "$API_URL" == *"createAppRunnerService"* ]]; then
  echo "Set RECOUP_API_URL or deploy App Runner first."
  exit 1
fi

BASE="${API_URL%/}"
echo "Smoke: $BASE"

curl -sf "$BASE/health" | grep -q '"status":"ok"' && echo "OK /health"
curl -sf "$BASE/health/ready" >/dev/null && echo "OK /health/ready"
curl -sf -o /dev/null -w "%{http_code}" -X POST "$BASE/api/test/reset" | grep -q 403 && echo "OK /api/test/reset blocked in production"

echo "Demo scan (requires ReadOnly role env on App Runner):"
curl -sf -X POST "$BASE/api/scan/demo" -H 'Content-Type: application/json' | head -c 200
echo ""
