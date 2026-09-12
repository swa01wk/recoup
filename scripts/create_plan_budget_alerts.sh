#!/usr/bin/env bash
# Cumulative spend alerts aligned to $150 plan / $180–$200 stretch (through Oct 31).
#
# Usage:
#   ./scripts/create_plan_budget_alerts.sh
#   ./scripts/create_plan_budget_alerts.sh --email you@example.com

set -euo pipefail

EMAIL="${RECOUP_ALERT_EMAIL:-swaroop.shivakumar@webknot.in}"
ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --email) EMAIL="$2"; shift 2 ;;
    *) echo "Unknown: $1"; exit 1 ;;
  esac
done

create_budget() {
  local name="$1"
  local amount="$2"
  local desc="$3"
  aws budgets create-budget \
    --account-id "$ACCOUNT_ID" \
    --budget "{
      \"BudgetName\": \"${name}\",
      \"BudgetLimit\": {\"Amount\": \"${amount}\", \"Unit\": \"USD\"},
      \"BudgetType\": \"COST\",
      \"TimeUnit\": \"MONTHLY\",
      \"CostTypes\": {\"IncludeTax\": true, \"IncludeSubscription\": true}
    }" \
    --notifications-with-subscribers "[{
      \"Notification\": {
        \"ComparisonOperator\": \"GREATER_THAN\",
        \"Threshold\": 100,
        \"ThresholdType\": \"PERCENTAGE\",
        \"NotificationType\": \"ACTUAL\"
      },
      \"Subscribers\": [{\"SubscriptionType\": \"EMAIL\", \"Address\": \"${EMAIL}\"}]
    }]" 2>/dev/null \
    || aws budgets update-budget \
      --account-id "$ACCOUNT_ID" \
      --new-budget "{
        \"BudgetName\": \"${name}\",
        \"BudgetLimit\": {\"Amount\": \"${amount}\", \"Unit\": \"USD\"},
        \"BudgetType\": \"COST\",
        \"TimeUnit\": \"MONTHLY\",
        \"CostTypes\": {\"IncludeTax\": true, \"IncludeSubscription\": true}
      }"
  echo "Budget ${name} at \$${amount}/mo — ${desc}"
}

echo "Creating plan budgets for account ${ACCOUNT_ID} → ${EMAIL}"
create_budget "recoup-plan-warning-100" "100" "warning — review Cost Explorer"
create_budget "recoup-plan-ceiling-150" "150" "plan ceiling — freeze upgrades"
create_budget "recoup-plan-stretch-180" "180" "stretch — document approval"
