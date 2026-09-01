#!/usr/bin/env bash
# =============================================================================
# Recoup — Full Deployment Script
# Usage: ./scripts/deploy.sh [--infra-only | --demo-only | --skip-tests]
# Prerequisites: AWS CLI configured, CDK bootstrapped, Node 20+, Python 3.12+
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CDK_DIR="$REPO_ROOT/infra/cdk"
BACKEND_DIR="$REPO_ROOT/backend"
AGENTCORE_CONFIG="$REPO_ROOT/infra/agentcore-config.yaml"

DEPLOY_INFRA=true
DEPLOY_DEMO=true
RUN_TESTS=true

for arg in "$@"; do
  case $arg in
    --infra-only) DEPLOY_DEMO=false ;;
    --demo-only)  DEPLOY_INFRA=false ;;
    --skip-tests) RUN_TESTS=false ;;
  esac
done

# ── Helpers ──────────────────────────────────────────────────────────────────
log()  { echo "$(date -u '+%H:%M:%S') ▸ $*"; }
fail() { echo "$(date -u '+%H:%M:%S') ✗ $*" >&2; exit 1; }
ok()   { echo "$(date -u '+%H:%M:%S') ✓ $*"; }

# ── Preflight checks ─────────────────────────────────────────────────────────
log "Checking prerequisites..."
command -v aws     >/dev/null 2>&1 || fail "aws CLI not found"
command -v node    >/dev/null 2>&1 || fail "node not found (need 20+)"
command -v python3 >/dev/null 2>&1 || fail "python3 not found (need 3.12+)"
command -v npx     >/dev/null 2>&1 || fail "npx not found"

aws sts get-caller-identity >/dev/null 2>&1 || fail "AWS credentials not configured"
ok "AWS identity: $(aws sts get-caller-identity --query 'Arn' --output text)"

ACCOUNT=$(aws sts get-caller-identity --query 'Account' --output text)
REGION=${CDK_DEFAULT_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}
log "Account: $ACCOUNT | Region: $REGION"

# ── Unit tests ───────────────────────────────────────────────────────────────
if [ "$RUN_TESTS" = true ]; then
  log "Running unit tests..."
  cd "$BACKEND_DIR"
  pip install -e ".[dev]" -q
  pytest tests/unit/ -q --tb=short
  ok "All unit tests passed"
  cd "$REPO_ROOT"
fi

# ── CDK bootstrap (idempotent) ────────────────────────────────────────────────
log "Bootstrapping CDK (idempotent)..."
cd "$CDK_DIR"
npm ci -q
npx cdk bootstrap "aws://$ACCOUNT/$REGION" --quiet
ok "CDK bootstrap complete"

# ── Deploy RecoupInfraStack ───────────────────────────────────────────────────
if [ "$DEPLOY_INFRA" = true ]; then
  log "Deploying RecoupInfraStack..."
  npx cdk deploy RecoupInfraStack \
    --require-approval never \
    --outputs-file "$REPO_ROOT/infra/cdk-outputs.json" \
    --progress events
  ok "RecoupInfraStack deployed"

  # Export stack outputs as env vars for subsequent steps
  RUNTIME_ROLE_ARN=$(jq -r '.RecoupInfraStack.RuntimeRoleArn' "$REPO_ROOT/infra/cdk-outputs.json")
  GATEWAY_ROLE_ARN=$(jq -r '.RecoupInfraStack.GatewayExecutionRoleArn' "$REPO_ROOT/infra/cdk-outputs.json")
  log "RuntimeRoleArn: $RUNTIME_ROLE_ARN"
  log "GatewayExecutionRoleArn: $GATEWAY_ROLE_ARN"
fi

# ── Deploy RecoupDemoStack ────────────────────────────────────────────────────
if [ "$DEPLOY_DEMO" = true ]; then
  log "Deploying RecoupDemoStack (demo EC2)..."
  npx cdk deploy RecoupDemoStack \
    --require-approval never \
    --outputs-file "$REPO_ROOT/infra/cdk-outputs-demo.json" \
    --progress events
  DEMO_INSTANCE_ID=$(jq -r '.RecoupDemoStack.DemoInstanceId' "$REPO_ROOT/infra/cdk-outputs-demo.json")
  ok "Demo instance: $DEMO_INSTANCE_ID — add to RECOUP_DEMO_INSTANCE_ALLOWLIST"
fi

# ── Upload SLA catalog to S3 ─────────────────────────────────────────────────
if [ "$DEPLOY_INFRA" = true ]; then
  log "Uploading SLA catalog to S3..."
  SLA_BUCKET="recoup-sla-catalog-$ACCOUNT-$REGION"
  aws s3 sync "$REPO_ROOT/sla_catalog/" "s3://$SLA_BUCKET/sla_catalog/" \
    --delete --sse aws:kms
  ok "SLA catalog uploaded to s3://$SLA_BUCKET/sla_catalog/"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════"
echo "  Recoup deployment complete"
echo "  Account : $ACCOUNT"
echo "  Region  : $REGION"
echo "  Outputs : infra/cdk-outputs.json"
echo ""
echo "  Next steps:"
echo "  1. Register AgentCore Runtime using infra/agentcore-config.yaml"
echo "  2. Set RECOUP_DEMO_INSTANCE_ALLOWLIST env var"
echo "  3. Run: python scripts/replay_run.py (Phase 2)"
echo "════════════════════════════════════════════════"
