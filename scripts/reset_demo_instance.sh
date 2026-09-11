#!/bin/bash
# reset_demo_instance.sh — Start the demo EC2 instance back to 'running' state.
#
# Usage:
#   ./scripts/reset_demo_instance.sh                  # auto-discovers instance via RecoupDemo=true tag
#   ./scripts/reset_demo_instance.sh i-0abc123def456  # explicit instance ID
#
# Prerequisites:
#   - AWS CLI configured with credentials for the demo account
#   - At least one EC2 instance tagged RecoupDemo=true in us-east-1

set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-us-east-1}"
INSTANCE_ID="${1:-}"

# ── Discover instance ID if not provided ─────────────────────────────────────
if [ -z "$INSTANCE_ID" ]; then
  echo "→ Discovering demo instance via RecoupDemo=true tag..."
  INSTANCE_ID=$(aws ec2 describe-instances \
    --region "$REGION" \
    --filters "Name=tag:RecoupDemo,Values=true" "Name=instance-state-name,Values=stopped,stopping,running" \
    --query "Reservations[0].Instances[0].InstanceId" \
    --output text 2>/dev/null || echo "")
fi

if [ -z "$INSTANCE_ID" ] || [ "$INSTANCE_ID" = "None" ]; then
  echo "❌  No demo instance found."
  echo "    Provide an instance ID as the first argument, or tag an EC2 instance with RecoupDemo=true."
  exit 1
fi

echo "→ Demo instance: $INSTANCE_ID (region: $REGION)"

# ── Check current state ──────────────────────────────────────────────────────
STATE=$(aws ec2 describe-instances \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --query "Reservations[0].Instances[0].State.Name" \
  --output text)

echo "   Current state: $STATE"

if [ "$STATE" = "running" ]; then
  echo "✓  Instance is already running — no action needed."
  exit 0
fi

if [ "$STATE" = "terminated" ]; then
  echo "❌  Instance is terminated — cannot restart a terminated instance."
  echo "    Deploy a new demo instance via: cdk deploy RecoupDemoStack"
  exit 1
fi

# ── Start instance ───────────────────────────────────────────────────────────
echo "→ Starting instance $INSTANCE_ID..."
aws ec2 start-instances --region "$REGION" --instance-ids "$INSTANCE_ID" > /dev/null

echo "→ Waiting for instance-running state (this may take ~30 s)..."
aws ec2 wait instance-running --region "$REGION" --instance-ids "$INSTANCE_ID"

FINAL=$(aws ec2 describe-instances \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --query "Reservations[0].Instances[0].State.Name" \
  --output text)

echo "✓  Instance state: $FINAL"
echo ""
echo "   Update RECOUP_DEMO_INSTANCE_ALLOWLIST in .env if the instance ID changed."
echo "   Instance is ready for the next demo run."
