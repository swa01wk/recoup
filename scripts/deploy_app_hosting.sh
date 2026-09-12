#!/usr/bin/env bash
# Build production API image, push to ECR, deploy App Runner (two-phase CDK).
#
# Usage:
#   export CDK_DEFAULT_ACCOUNT=625962218034 CDK_DEFAULT_REGION=us-east-1
#   export RECOUP_EXTERNAL_ID='recoup-demo-external-id'
#   export RECOUP_FRONTEND_URL='https://your.amplifyapp.com'
#   ./scripts/deploy_app_hosting.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REGION="${CDK_DEFAULT_REGION:-us-east-1}"
ACCOUNT="${CDK_DEFAULT_ACCOUNT:-$(aws sts get-caller-identity --query Account --output text)}"
IMAGE_TAG="${RECOUP_API_IMAGE_TAG:-latest}"

echo "━━━ Recoup App Runner deploy (phase 1: ECR) ━━━"
cd "$ROOT/infra/cdk"
npm run build

export RECOUP_API_IMAGE_TAG="$IMAGE_TAG"
npx cdk deploy RecoupAppStack --exclusively --require-approval never

REPO_URI=$(aws cloudformation describe-stacks \
  --stack-name RecoupAppStack \
  --query "Stacks[0].Outputs[?OutputKey=='EcrRepositoryUri'].OutputValue" \
  --output text --region "$REGION")

echo "ECR repository: $REPO_URI"
echo "━━━ Docker build + push ━━━"
aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"

# Single-platform manifest only — App Runner can fail on OCI index + attestation manifests.
export DOCKER_BUILDKIT=1
docker build --platform linux/amd64 --provenance=false --sbom=false \
  -t "recoup-api:${IMAGE_TAG}" "$ROOT"
docker tag "recoup-api:${IMAGE_TAG}" "${REPO_URI}:${IMAGE_TAG}"
docker push "${REPO_URI}:${IMAGE_TAG}"

echo "━━━ Phase 2: App Runner service ━━━"
npx cdk deploy RecoupAppStack --exclusively -c createAppRunnerService=true --require-approval never

APP_URL=$(aws cloudformation describe-stacks \
  --stack-name RecoupAppStack \
  --query "Stacks[0].Outputs[?OutputKey=='AppRunnerServiceUrl'].OutputValue" \
  --output text --region "$REGION")

echo ""
echo "API URL: ${APP_URL}"
echo "Amplify: NEXT_PUBLIC_API_URL=${APP_URL}"
echo "Then set RECOUP_FRONTEND_URL to Amplify URL and redeploy App stack if CORS needed."
