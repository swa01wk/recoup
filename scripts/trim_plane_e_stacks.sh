#!/usr/bin/env bash
# Destroy Plane E legacy stacks (SLA API GW + live-stop demo EC2). Does not touch Infra or hosting.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/infra/cdk"
npm run build 2>/dev/null || npm ci && npm run build

for stack in RecoupSLADemoStack RecoupDemoStack; do
  if aws cloudformation describe-stacks --stack-name "$stack" &>/dev/null; then
    echo "Destroying $stack ..."
    npx cdk destroy "$stack" --force
  else
    echo "Stack $stack not present — skip"
  fi
done

echo "Done. Plane B (Infra) and Plane D (Workloads) unchanged."
