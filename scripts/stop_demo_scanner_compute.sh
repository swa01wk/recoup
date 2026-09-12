#!/usr/bin/env bash
# Plane D only — stop oversized EC2 + idle RDS (RecoupDemo=true). Does not affect App Runner / DynamoDB.
set -euo pipefail
REGION="${AWS_DEFAULT_REGION:-us-east-1}"

EC2_IDS=$(aws ec2 describe-instances --region "$REGION" \
  --filters "Name=tag:RecoupScenario,Values=oversized-ec2" "Name=instance-state-name,Values=running" \
  --query "Reservations[].Instances[].InstanceId" --output text)

if [[ -n "$EC2_IDS" && "$EC2_IDS" != "None" ]]; then
  aws ec2 stop-instances --instance-ids $EC2_IDS --region "$REGION"
  echo "Stopped EC2: $EC2_IDS"
else
  echo "No running oversized-ec2 instance"
fi

RDS_ID=$(aws rds describe-db-instances --region "$REGION" \
  --query "DBInstances[?contains(DBInstanceIdentifier, 'idlerds') || contains(DBInstanceIdentifier, 'IdleRDS')].DBInstanceIdentifier | [0]" \
  --output text 2>/dev/null || echo "None")

if [[ -n "$RDS_ID" && "$RDS_ID" != "None" ]]; then
  STATUS=$(aws rds describe-db-instances --db-instance-identifier "$RDS_ID" --region "$REGION" \
    --query "DBInstances[0].DBInstanceStatus" --output text)
  if [[ "$STATUS" == "available" ]]; then
    aws rds stop-db-instance --db-instance-identifier "$RDS_ID" --region "$REGION"
    echo "Stopping RDS: $RDS_ID"
  else
    echo "RDS $RDS_ID status: $STATUS"
  fi
else
  echo "No idle RDS found"
fi
