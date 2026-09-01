#!/usr/bin/env bash
# =============================================================================
# Recoup — Infrastructure Verification Script
# Run after ./scripts/deploy.sh to confirm all AWS resources exist correctly.
# Usage: ./scripts/verify_infra.sh [--region us-east-1]
# =============================================================================
set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-us-east-1}"
for arg in "$@"; do
  case $arg in
    --region) shift; REGION="$1" ;;
  esac
done

PASS=0
FAIL=0
WARN=0

log()  { echo "$(date -u '+%H:%M:%S')  $*"; }
ok()   { echo "$(date -u '+%H:%M:%S') ✅ $*"; ((PASS++)) || true; }
fail() { echo "$(date -u '+%H:%M:%S') ❌ $*"; ((FAIL++)) || true; }
warn() { echo "$(date -u '+%H:%M:%S') ⚠️  $*"; ((WARN++)) || true; }

ACCOUNT=$(aws sts get-caller-identity --query 'Account' --output text 2>/dev/null) \
  || { echo "ERROR: AWS credentials not configured"; exit 1; }

log "Verifying Recoup infrastructure"
log "Account: $ACCOUNT | Region: $REGION"
echo ""

# ── DynamoDB ─────────────────────────────────────────────────────────────────
log "── DynamoDB tables ──"
for table in recoup-opportunities recoup-approvals recoup-tool-audits recoup-outcome-metadata; do
  status=$(aws dynamodb describe-table \
    --table-name "$table" \
    --region "$REGION" \
    --query 'Table.TableStatus' --output text 2>/dev/null || echo "NOT_FOUND")
  if [[ "$status" == "ACTIVE" ]]; then
    ok "$table — ACTIVE"
  else
    fail "$table — $status"
  fi
done

# Check GSIs on opportunities table
gsi_count=$(aws dynamodb describe-table \
  --table-name recoup-opportunities \
  --region "$REGION" \
  --query 'length(Table.GlobalSecondaryIndexes)' --output text 2>/dev/null || echo "0")
if [[ "$gsi_count" -ge 2 ]]; then
  ok "recoup-opportunities GSIs present ($gsi_count)"
else
  fail "recoup-opportunities missing GSIs (found: $gsi_count, expected: 2)"
fi

echo ""

# ── S3 Buckets ────────────────────────────────────────────────────────────────
log "── S3 buckets ──"
for bucket_suffix in evidence sla-catalog eval-fixtures; do
  bucket="recoup-${bucket_suffix}-${ACCOUNT}-${REGION}"
  if aws s3api head-bucket --bucket "$bucket" --region "$REGION" 2>/dev/null; then
    versioning=$(aws s3api get-bucket-versioning \
      --bucket "$bucket" \
      --query 'Status' --output text 2>/dev/null || echo "Disabled")
    if [[ "$versioning" == "Enabled" ]]; then
      ok "$bucket — exists, versioning Enabled"
    else
      warn "$bucket — exists but versioning: $versioning"
    fi
  else
    fail "$bucket — NOT FOUND"
  fi
done

echo ""

# ── SQS Queues ───────────────────────────────────────────────────────────────
log "── SQS queues ──"
for queue in recoup-recovery-events recoup-recovery-events-dlq; do
  url=$(aws sqs get-queue-url \
    --queue-name "$queue" \
    --region "$REGION" \
    --query 'QueueUrl' --output text 2>/dev/null || echo "NOT_FOUND")
  if [[ "$url" != "NOT_FOUND" ]]; then
    ok "$queue — exists"
  else
    fail "$queue — NOT FOUND"
  fi
done

echo ""

# ── KMS ──────────────────────────────────────────────────────────────────────
log "── KMS ──"
key_state=$(aws kms describe-key \
  --key-id "alias/recoup-evidence" \
  --region "$REGION" \
  --query 'KeyMetadata.KeyState' --output text 2>/dev/null || echo "NOT_FOUND")
if [[ "$key_state" == "Enabled" ]]; then
  ok "alias/recoup-evidence — Enabled"
else
  fail "alias/recoup-evidence — $key_state"
fi

echo ""

# ── EventBridge ──────────────────────────────────────────────────────────────
log "── EventBridge ──"
rule_state=$(aws events describe-rule \
  --name RecoupHealthEventRule \
  --region "$REGION" \
  --query 'State' --output text 2>/dev/null || echo "NOT_FOUND")
if [[ "$rule_state" == "ENABLED" ]]; then
  ok "RecoupHealthEventRule — ENABLED"
else
  fail "RecoupHealthEventRule — $rule_state"
fi

echo ""

# ── CloudWatch Log Groups ────────────────────────────────────────────────────
log "── CloudWatch log groups ──"
for lg in /recoup/runtime /recoup/gateway /recoup/api; do
  exists=$(aws logs describe-log-groups \
    --log-group-name-prefix "$lg" \
    --region "$REGION" \
    --query 'length(logGroups)' --output text 2>/dev/null || echo "0")
  if [[ "$exists" -ge 1 ]]; then
    ok "$lg — exists"
  else
    fail "$lg — NOT FOUND"
  fi
done

echo ""

# ── CloudWatch Alarms ────────────────────────────────────────────────────────
log "── CloudWatch alarms ──"
alarm_state=$(aws cloudwatch describe-alarms \
  --alarm-names RecoupEstimatedChargesAlarm \
  --region us-east-1 \
  --query 'MetricAlarms[0].StateValue' --output text 2>/dev/null || echo "NOT_FOUND")
if [[ "$alarm_state" == "OK" || "$alarm_state" == "INSUFFICIENT_DATA" ]]; then
  ok "RecoupEstimatedChargesAlarm — $alarm_state (cost alarm active)"
elif [[ "$alarm_state" == "ALARM" ]]; then
  warn "RecoupEstimatedChargesAlarm — IN ALARM (charges > \$10!)"
else
  fail "RecoupEstimatedChargesAlarm — $alarm_state"
fi

echo ""

# ── IAM Roles ────────────────────────────────────────────────────────────────
log "── IAM roles ──"
for role in RecoupRuntimeRole RecoupGatewayExecutionRole RecoupReadConnectorRole; do
  exists=$(aws iam get-role \
    --role-name "$role" \
    --query 'Role.RoleName' --output text 2>/dev/null || echo "NOT_FOUND")
  if [[ "$exists" == "$role" ]]; then
    ok "$role — exists"
  else
    fail "$role — NOT FOUND"
  fi
done

echo ""

# ── SNS ──────────────────────────────────────────────────────────────────────
log "── SNS ──"
sns_arn=$(aws sns list-topics \
  --region "$REGION" \
  --query "Topics[?contains(TopicArn,'recoup-alerts')].TopicArn | [0]" \
  --output text 2>/dev/null || echo "None")
if [[ "$sns_arn" != "None" && -n "$sns_arn" ]]; then
  ok "recoup-alerts SNS topic — $sns_arn"
else
  warn "recoup-alerts SNS topic — not found (alarm exists but no subscriber email set)"
fi

echo ""

# ── Summary ───────────────────────────────────────────────────────────────────
echo "════════════════════════════════════════════"
echo "  Verification complete"
echo "  ✅ Passed : $PASS"
echo "  ❌ Failed : $FAIL"
echo "  ⚠️  Warnings: $WARN"
echo ""
if [[ "$FAIL" -eq 0 ]]; then
  echo "  All checks passed — ready for Phase 2"
else
  echo "  Fix failures before starting Phase 2"
  echo "  Re-run: ./scripts/deploy.sh"
fi
echo "════════════════════════════════════════════"

exit "$FAIL"
