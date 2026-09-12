#!/usr/bin/env bash
# Build Next.js standalone image, push to ECR, deploy UI App Runner (Plane A).
#
# Usage:
#   export CDK_DEFAULT_ACCOUNT=625962218034 CDK_DEFAULT_REGION=us-east-1
#   export NEXT_PUBLIC_API_URL='https://<RecoupAppStack AppRunnerServiceUrl output>'
#   ./scripts/deploy_ui_hosting.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REGION="${CDK_DEFAULT_REGION:-us-east-1}"
ACCOUNT="${CDK_DEFAULT_ACCOUNT:-$(aws sts get-caller-identity --query Account --output text)}"
if [[ -z "${NEXT_PUBLIC_API_URL:-}" ]]; then
  API_URL=$(aws cloudformation describe-stacks \
    --stack-name RecoupAppStack \
    --query "Stacks[0].Outputs[?OutputKey=='AppRunnerServiceUrl'].OutputValue" \
    --output text --region "$REGION" 2>/dev/null || true)
fi
API_URL="${NEXT_PUBLIC_API_URL:-${API_URL:-}}"
if [[ -z "$API_URL" || "$API_URL" == *"createAppRunnerService"* ]]; then
  echo "Set NEXT_PUBLIC_API_URL or deploy RecoupAppStack (App Runner API) first."
  exit 1
fi
echo "Building UI against API: $API_URL"
IMAGE_TAG="${RECOUP_UI_IMAGE_TAG:-latest}"

echo "━━━ Recoup UI App Runner (phase 1: ECR) ━━━"
cd "$ROOT/infra/cdk"
npm run build
export RECOUP_UI_IMAGE_TAG="$IMAGE_TAG"
npx cdk deploy RecoupUiStack --exclusively --require-approval never

REPO_URI=$(aws cloudformation describe-stacks \
  --stack-name RecoupUiStack \
  --query "Stacks[0].Outputs[?OutputKey=='UiEcrRepositoryUri'].OutputValue" \
  --output text --region "$REGION")

echo "ECR: $REPO_URI"
aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"

export DOCKER_BUILDKIT=1
docker build --platform linux/amd64 --provenance=false --sbom=false \
  --build-arg "NEXT_PUBLIC_API_URL=${API_URL}" \
  -t "recoup-ui:${IMAGE_TAG}" "$ROOT/frontend"
docker tag "recoup-ui:${IMAGE_TAG}" "${REPO_URI}:${IMAGE_TAG}"
docker push "${REPO_URI}:${IMAGE_TAG}"

echo "━━━ Phase 2: UI App Runner service ━━━"
UI_ARN=$(aws apprunner list-services --region "$REGION" \
  --query "ServiceSummaryList[?ServiceName=='recoup-ui'].ServiceArn | [0]" --output text 2>/dev/null || true)
if [[ -n "$UI_ARN" && "$UI_ARN" != "None" ]]; then
  echo "recoup-ui already exists — rolling deployment with new ECR image (no CFN recreate)."
  aws apprunner start-deployment --service-arn "$UI_ARN" --region "$REGION" >/dev/null
  UI_URL=$(aws apprunner describe-service --service-arn "$UI_ARN" --region "$REGION" \
    --query "Service.ServiceUrl" --output text)
else
  ATTEMPTS=3
  for ((i=1; i<=ATTEMPTS; i++)); do
    echo "App Runner UI create attempt ${i}/${ATTEMPTS}..."
    if npx cdk deploy RecoupUiStack --exclusively -c createUiService=true --require-approval never; then
      break
    fi
    if [[ "$i" -lt "$ATTEMPTS" ]]; then
      echo "Create failed (often transient after a delete). Waiting 90s before retry..."
      sleep 90
    else
      exit 1
    fi
  done
  UI_URL=$(aws cloudformation describe-stacks \
    --stack-name RecoupUiStack \
    --query "Stacks[0].Outputs[?OutputKey=='UiAppRunnerServiceUrl'].OutputValue" \
    --output text --region "$REGION")
fi

echo ""
echo "UI URL: ${UI_URL}"
echo "Redeploy API CORS: RECOUP_FRONTEND_URL=${UI_URL} ./scripts/deploy_app_hosting.sh"
