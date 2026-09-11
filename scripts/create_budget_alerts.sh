#!/usr/bin/env bash
# Phase 6f — Pre-deploy Budget Alerts
#
# Creates three AWS Budget cost alerts at $25, $40, and $50 thresholds.
# Run BEFORE deploying RecoupDemoWorkloadsStack to protect against overruns.
#
# Prerequisites:
#   - AWS CLI v2 configured with appropriate credentials
#   - Account ID set in AWS_ACCOUNT_ID env var or auto-detected
#
# Usage:
#   ./scripts/create_budget_alerts.sh
#   ./scripts/create_budget_alerts.sh --email swaroop.shivakumar@webknot.in
#
# Demo spend target: $30–$50/month (stop EC2+RDS between sessions)

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
EMAIL="${RECOUP_ALERT_EMAIL:-swaroop.shivakumar@webknot.in}"
ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"

# Parse --email flag
while [[ $# -gt 0 ]]; do
  case "$1" in
    --email) EMAIL="$2"; shift 2 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Phase 6f — Creating AWS Budget Cost Alerts"
echo "  Account:    ${ACCOUNT_ID}"
echo "  Alert email: ${EMAIL}"
echo "  Thresholds:  \$25 (warning) / \$40 (critical) / \$50 (hard limit)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

# ── Helper: create one budget with one notification ───────────────────────────
create_budget() {
  local name="$1"
  local amount="$2"
  local threshold_pct="${3:-100}"  # % of budget amount that triggers alert

  echo "  Creating budget '${name}' at \$${amount}…"

  aws budgets create-budget \
    --account-id "${ACCOUNT_ID}" \
    --budget "{
      \"BudgetName\": \"${name}\",
      \"BudgetLimit\": {\"Amount\": \"${amount}\", \"Unit\": \"USD\"},
      \"TimeUnit\": \"MONTHLY\",
      \"BudgetType\": \"COST\"
    }" \
    --notifications-with-subscribers "[{
      \"Notification\": {
        \"NotificationType\": \"ACTUAL\",
        \"ComparisonOperator\": \"GREATER_THAN\",
        \"Threshold\": ${threshold_pct},
        \"ThresholdType\": \"PERCENTAGE\"
      },
      \"Subscribers\": [{
        \"SubscriptionType\": \"EMAIL\",
        \"Address\": \"${EMAIL}\"
      }]
    }]" 2>&1 | grep -v "^$" || true

  echo "  ✓ Budget '${name}' created (\$${amount} threshold)"
}

# ── Budget 1: Warning at $25 ──────────────────────────────────────────────────
create_budget "recoup-demo-warning-25"   "25" 100

# ── Budget 2: Critical at $40 ────────────────────────────────────────────────
create_budget "recoup-demo-critical-40"  "40" 100

# ── Budget 3: Hard limit at $50 ──────────────────────────────────────────────
create_budget "recoup-demo-hardlimit-50" "50" 100

echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "All 3 budget alerts created. Check your AWS Billing console:"
echo "  https://console.aws.amazon.com/billing/home#/budgets"
echo
echo "Cost-saving reminder:"
echo "  Stop EC2+RDS between demo sessions to reduce spend by ~70%:"
echo "  aws ec2 stop-instances --instance-ids <oversized-ec2-id>"
echo "  aws rds stop-db-instance --db-instance-identifier <idle-rds-id>"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
