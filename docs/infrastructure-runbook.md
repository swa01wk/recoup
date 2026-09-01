# Recoup Infrastructure Runbook

**Stack:** `RecoupInfraStack` + `RecoupDemoStack`  
**Region:** us-east-1 (configurable via `CDK_DEFAULT_REGION`)  
**Deploy time:** ~8 min from clean account

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Node.js | 20+ | `nvm install 20` |
| Python | 3.12+ | `pyenv install 3.12` |
| AWS CLI | v2 | [docs.aws.amazon.com/cli](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) |
| CDK | 2.267+ | bundled in `infra/cdk` — `npm ci` |
| jq | any | `brew install jq` |

---

## First-Time Deploy

```bash
# 1. Configure AWS credentials
aws configure                    # or: export AWS_PROFILE=recoup-sandbox

# 2. Verify identity
aws sts get-caller-identity

# 3. Full deploy (runs unit tests first)
./scripts/deploy.sh

# 4. Verify all resources exist
./scripts/verify_infra.sh

# 5. Register AgentCore Harness + Gateway (new bedrock-agentcore-control API)
python scripts/register_agentcore.py

# 6. Copy IDs to .env
cat infra/agentcore-ids.json
# → add RECOUP_AGENTCORE_HARNESS_ID, RECOUP_AGENTCORE_HARNESS_ARN, and
#   RECOUP_AGENTCORE_GATEWAY_ID to .env

# NOTE: Classic Bedrock Agents (create_agent) is in maintenance mode for new
# accounts since Jul 30 2026.  register_agentcore.py now uses create_harness()
# and create_gateway() from the bedrock-agentcore-control client instead.
```

---

## Re-Deploy After Changes

```bash
# Infra changes only (skip unit tests)
./scripts/deploy.sh --skip-tests

# CDK infra only (skip demo EC2)
./scripts/deploy.sh --infra-only

# Demo EC2 only
./scripts/deploy.sh --demo-only
```

---

## Tear Down

> Only do this after the competition ends. `RETAIN` policy means you must delete manually.

```bash
# Delete S3 bucket contents first (required before bucket deletion)
aws s3 rm s3://recoup-evidence-ACCOUNT-REGION --recursive
aws s3 rm s3://recoup-sla-catalog-ACCOUNT-REGION --recursive
aws s3 rm s3://recoup-eval-fixtures-ACCOUNT-REGION --recursive

# Destroy stacks
cd infra/cdk
npx cdk destroy --all
```

---

## Resource Inventory

### DynamoDB Tables

| Table | Partition Key | Sort Key | GSIs | Purpose |
|-------|--------------|----------|------|---------|
| `recoup-opportunities` | `id` (S) | — | `account-state-index`, `state-discovered-index` | Main opportunity records |
| `recoup-approvals` | `approval_id` (S) | — | — | HITL approval records (TTL on `expires_at`) |
| `recoup-tool-audits` | `trace_id` (S) | `timestamp` (S) | — | Tool call audit log |
| `recoup-outcome-metadata` | `pk` (S) | — | — | Service/region/month outcome summaries |

### S3 Buckets

| Bucket | Encryption | Versioning | Lifecycle |
|--------|-----------|-----------|-----------|
| `recoup-evidence-{acct}-{region}` | KMS CMK | ✅ | Raw → Glacier after 90d |
| `recoup-sla-catalog-{acct}-{region}` | S3-SSE | ✅ | — |
| `recoup-eval-fixtures-{acct}-{region}` | S3-SSE | ✅ | — |

### SQS Queues

| Queue | Visibility | Retention | DLQ |
|-------|-----------|----------|-----|
| `recoup-recovery-events` | 300s | 14d | `recoup-recovery-events-dlq` |
| `recoup-recovery-events-dlq` | — | 14d | — |

### CloudWatch

| Log Group | Retention | Source |
|-----------|----------|--------|
| `/recoup/runtime` | 30 days | AgentCore Runtime |
| `/recoup/gateway` | 30 days | AgentCore Gateway |
| `/recoup/api` | 30 days | FastAPI backend |

### Alarms

| Alarm | Threshold | Action |
|-------|---------|--------|
| `RecoupEstimatedChargesAlarm` | $10 estimated charges | SNS → `recoup-alerts` |

> **Subscribe your email to the `recoup-alerts` SNS topic** after deploy:
> ```bash
> aws sns subscribe \
>   --topic-arn $(aws sns list-topics --query "Topics[?contains(TopicArn,'recoup-alerts')].TopicArn|[0]" --output text) \
>   --protocol email \
>   --notification-endpoint YOUR@EMAIL.COM
> ```

---

## Cost Estimate

| Service | Usage | Est. Cost/day |
|---------|-------|--------------|
| DynamoDB (on-demand) | Light hackathon load | < $0.10 |
| S3 (3 buckets) | < 1 GB total | < $0.05 |
| SQS | < 1k messages | < $0.01 |
| KMS | < 10k requests | < $0.03 |
| EC2 t3.micro (demo) | Stopped most of the time | < $0.01 |
| Bedrock Claude 3.5 Sonnet | Demo calls only | < $1.00 |
| **Total** | | **< $2/day** |

The $10 CloudWatch alarm gives roughly 5 days of buffer.

---

## Troubleshooting

### CDK bootstrap fails with permission error
```bash
# Add CloudFormation + IAM permissions to your deployment user/role
aws iam attach-user-policy \
  --user-name YOUR_USER \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
```

### DynamoDB table stuck in CREATING
```bash
# Wait and retry verify
sleep 30 && ./scripts/verify_infra.sh
```

### AgentCore Runtime creation fails
- Ensure Bedrock is enabled in your region (`us-east-1` recommended)
- Verify `RecoupRuntimeRole` has `AmazonBedrockFullAccess`
- Check CloudTrail for the exact IAM error

### S3 bucket name conflict
Bucket names include `{account}-{region}` — conflicts only occur if you've deployed before. Use:
```bash
aws s3 rb s3://recoup-evidence-OLD_ACCT-REGION --force
```
