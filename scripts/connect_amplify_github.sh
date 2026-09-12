#!/usr/bin/env bash
# Ensure a GitHub CodeStar connection exists for Amplify (Plane A).
set -euo pipefail
REGION="${CDK_DEFAULT_REGION:-us-east-1}"
NAME="${CODESTAR_CONNECTION_NAME:-recoup-github}"

ARN=$(aws codestar-connections list-connections --region "$REGION" \
  --query "Connections[?ConnectionName=='${NAME}'].ConnectionArn | [0]" --output text)

if [[ -z "$ARN" || "$ARN" == "None" ]]; then
  ARN=$(aws codestar-connections create-connection \
    --provider-type GitHub --connection-name "$NAME" --region "$REGION" \
    --query 'ConnectionArn' --output text)
  echo "Created connection: $ARN"
else
  echo "Connection: $ARN"
fi

STATUS=$(aws codestar-connections get-connection --connection-arn "$ARN" --region "$REGION" \
  --query 'Connection.ConnectionStatus' --output text)
echo "Status: $STATUS"

if [[ "$STATUS" != "AVAILABLE" ]]; then
  echo ""
  echo "Complete GitHub authorization in AWS Console:"
  echo "  https://${REGION}.console.aws.amazon.com/codesuite/settings/connections"
  echo "Then run ./scripts/deploy_amplify_frontend.sh with GITHUB_OAUTH_TOKEN, or connect repo in Amplify Console."
  exit 2
fi
