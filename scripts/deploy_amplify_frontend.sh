#!/usr/bin/env bash
# Connect GitHub (CodeStar) + create Amplify app for frontend/ (Next.js WEB_COMPUTE).
#
# Prerequisites:
#   1. CodeStar connection AVAILABLE (see connect_amplify_github.sh)
#   2. GITHUB_OAUTH_TOKEN — classic PAT with repo scope for swa01wk/recoup
#
# Usage:
#   export GITHUB_OAUTH_TOKEN='ghp_...'
#   export NEXT_PUBLIC_API_URL='https://vxndciwupy.us-east-1.awsapprunner.com'
#   ./scripts/deploy_amplify_frontend.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REGION="${CDK_DEFAULT_REGION:-us-east-1}"
API_URL="${NEXT_PUBLIC_API_URL:-https://vxndciwupy.us-east-1.awsapprunner.com}"
REPO="${AMPLIFY_REPOSITORY:-https://github.com/swa01wk/recoup}"
APP_NAME="${AMPLIFY_APP_NAME:-recoup-jfull}"

if [[ -z "${GITHUB_OAUTH_TOKEN:-}" ]]; then
  echo "Set GITHUB_OAUTH_TOKEN (GitHub PAT with repo access) or connect via AWS Console → Amplify → Host web app."
  exit 1
fi

BUILD_SPEC="$(cat "$ROOT/frontend/amplify.yml")"

EXISTING=$(aws amplify list-apps --region "$REGION" \
  --query "apps[?name=='${APP_NAME}'].appId | [0]" --output text 2>/dev/null || true)

if [[ -n "$EXISTING" && "$EXISTING" != "None" ]]; then
  APP_ID="$EXISTING"
  echo "Using existing Amplify app: $APP_ID"
else
  APP_ID=$(aws amplify create-app \
    --name "$APP_NAME" \
    --platform WEB_COMPUTE \
    --repository "$REPO" \
    --oauth-token "$GITHUB_OAUTH_TOKEN" \
    --environment-variables "NEXT_PUBLIC_API_URL=${API_URL}" \
    --build-spec "$BUILD_SPEC" \
    --custom-rules '[{"source":"/<*>","target":"/index.html","status":"404-200"}]' \
    --region "$REGION" \
    --query 'app.appId' --output text)
  echo "Created Amplify app: $APP_ID"
fi

BRANCH="${AMPLIFY_BRANCH:-main}"
if ! aws amplify get-branch --app-id "$APP_ID" --branch-name "$BRANCH" --region "$REGION" &>/dev/null; then
  aws amplify create-branch --app-id "$APP_ID" --branch-name "$BRANCH" --region "$REGION"
fi

aws amplify start-job --app-id "$APP_ID" --branch-name "$BRANCH" --job-type RELEASE --region "$REGION" \
  --query 'jobSummary.jobId' --output text >/dev/null

DOMAIN=$(aws amplify get-app --app-id "$APP_ID" --region "$REGION" --query 'app.defaultDomain' --output text)
FRONTEND_URL="https://${BRANCH}.${DOMAIN}"
echo ""
echo "Amplify build started. Frontend URL (when job succeeds): ${FRONTEND_URL}"
echo "Update CORS: export RECOUP_FRONTEND_URL='${FRONTEND_URL}' && ./scripts/deploy_app_hosting.sh"
