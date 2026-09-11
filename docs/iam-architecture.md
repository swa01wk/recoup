# IAM Security Architecture

**Version:** Phase 6e | **Updated:** Sep 11, 2026

---

## Overview

Recoup uses a three-tier IAM role model that mirrors the exact access pattern a real customer deployment would use:

```
Recoup runtime
  → RecoupRuntimeRole (application execution identity)
    → STS AssumeRole  (short-lived, scoped, ExternalId-gated)
      → RecoupReadOnlyRole   (inventory / cost / telemetry reads)
      → RecoupRemediationRole (ec2:StopInstances on tagged instances only)
```

**Key invariant:** Analysis and remediation are always separate credential paths. The role that reads CloudWatch metrics and Cost Explorer data *cannot* stop an instance. The role that can stop an instance *cannot* read billing data.

---

## Role Hierarchy

### RecoupRuntimeRole

| Property | Value |
|---|---|
| **Purpose** | Application execution identity |
| **Trust principal** | `bedrock.amazonaws.com` (AgentCore Runtime) |
| **Key permissions** | DynamoDB read/write, S3 read/write (evidence/catalog), KMS, CloudWatch Logs write, `sts:AssumeRole` for ReadOnly + Remediation roles |
| **What it cannot do** | Call AWS Service APIs directly for analysis (must assume ReadOnlyRole); call `ec2:StopInstances` directly |

Added in Phase 6e: `sts:AssumeRole` for `RecoupReadOnlyRole` and `RecoupRemediationRole`.

---

### RecoupReadOnlyRole

| Property | Value |
|---|---|
| **Purpose** | Broad analysis access — inventory, cost, telemetry |
| **Trust principal** | `RecoupRuntimeRole` (same account) with `sts:ExternalId` condition |
| **CDK stack** | `RecoupIamStack` |
| **Created** | Phase 6e |

**Permission summary:**

| Sid | Services | Permitted actions |
|---|---|---|
| `EC2ReadOnly` | EC2 | `Describe*`, `GetConsoleOutput` |
| `CloudWatchReadOnly` | CloudWatch, Logs | `Get*`, `List*`, `Describe*`, `FilterLogEvents` |
| `CostReadOnly` | Cost Explorer, Cost Optimization Hub | `GetCostAndUsage`, `GetAnomalies`, `ListRecommendations`, … |
| `CloudTrailReadOnly` | CloudTrail | `LookupEvents`, `DescribeTrails` |
| `EBSRDSLambdaS3ELBReadOnly` | RDS, Lambda, S3, ELB | `Describe*`, `List*`, `GetBucket*` |
| `TaggingReadOnly` | Resource Groups Tagging API | `GetResources`, `GetTagKeys`, `GetTagValues` |
| `ComputeOptimizerReadOnly` | Compute Optimizer | `Get*InstanceRecommendations` |

**What it cannot do:** No `ec2:StopInstances`, no `s3:PutObject`, no write action on any service.

---

### RecoupRemediationRole

| Property | Value |
|---|---|
| **Purpose** | Narrowly scoped write role for approved remediation actions |
| **Trust principal** | `RecoupRuntimeRole` (same account) with `sts:ExternalId` condition |
| **CDK stack** | `RecoupIamStack` |
| **Created** | Phase 6e |

**Permission summary:**

| Sid | Effect | Action | Condition |
|---|---|---|---|
| `AllowStopDemoInstancesOnly` | Allow | `ec2:StopInstances` | `ec2:ResourceTag/RecoupDemo = true` |
| `DescribeTagsForVerification` | Allow | `ec2:DescribeTags`, `ec2:DescribeInstances` | — |
| `ExplicitlyDenyTerminate` | **Deny** | `ec2:TerminateInstances` | — (cannot be overridden) |

**What it cannot do:** Cannot read CloudWatch metrics, cannot access Cost Explorer, cannot list S3 objects. It has exactly the write permission needed and nothing more.

---

## ExternalId Design

The `ExternalId` condition prevents the [Confused Deputy problem](https://docs.aws.amazon.com/IAM/latest/UserGuide/confused-deputy.html): an attacker who knows a role ARN cannot force another AWS account's services to assume that role without also knowing the External ID.

| Property | Detail |
|---|---|
| **Value** | Stored in `RECOUP_EXTERNAL_ID` env var; set in CDK as `externalId` parameter |
| **Where it appears** | Trust policy `Condition.StringEquals.sts:ExternalId` on both ReadOnly and Remediation roles |
| **How to rotate** | Update `RECOUP_EXTERNAL_ID` + redeploy `RecoupIamStack`; any in-flight sessions with the old ID will fail to renew |
| **What happens without it** | `sts:AssumeRole` returns `AccessDenied` — scanners receive HTTP 400 |

---

## Credential Lifecycle

```
t=0     Recoup backend calls sts:AssumeRole (ExternalId required)
t=0     STS issues temporary credentials: AccessKeyId + SecretAccessKey + SessionToken
t=0     CustomerConnection caches the session for 50 minutes
t=50m   Cache evicted; next call triggers a new AssumeRole
t=60m   STS credentials expire; any in-flight call with old creds returns ExpiredToken
```

- Credentials are **never written to any database, log, or API response**
- The assumed session name is `recoup-analysis-session` (visible in CloudTrail)
- `DurationSeconds=3600` (maximum for a chained role assumption)

---

## Access Flow Diagrams

### Same-Account (Hackathon Demo)

```
┌─────────────────┐         sts:AssumeRole + ExternalId
│  Recoup backend │  ──────────────────────────────────▶  RecoupReadOnlyRole
│ (EC2 / Lambda)  │                                        (account 625962218034)
│                 │  ──────────────────────────────────▶  RecoupRemediationRole
└─────────────────┘         sts:AssumeRole + ExternalId    (account 625962218034)
```

### Future Cross-Account (Production)

```
┌──────────────────────────┐         sts:AssumeRole + ExternalId
│ Recoup control-plane     │  ──────────────────────────────────▶  RecoupReadOnlyRole
│ account (Recoup's AWS)   │                                        (customer account)
└──────────────────────────┘

Only the role ARN's account ID changes — code path is identical.
```

---

## Security Invariants

| Invariant | How enforced |
|---|---|
| Analysis role cannot stop an instance | `RecoupReadOnlyRole` has no `ec2:Stop*` permission |
| Remediation role cannot read billing data | `RecoupRemediationRole` has no `ce:*` or `cloudwatch:*` permission |
| TerminateInstances is always blocked | Explicit `Deny` in `RecoupRemediationRole` (overrides any Allow) |
| Stop requires `RecoupDemo=true` tag | IAM condition `ec2:ResourceTag/RecoupDemo = true` |
| No long-lived access keys in scanner API | Raw credential fields removed from `ScanRequest` in Phase 6e |
| External ID required | Trust policy `Condition.StringEquals.sts:ExternalId` |

---

## Verification Commands

```bash
# 1. Confirm AssumeRole succeeds with correct ExternalId
aws sts assume-role \
  --role-arn "$RECOUP_READONLY_ROLE_ARN" \
  --role-session-name test-session \
  --external-id "$RECOUP_EXTERNAL_ID"
# Expected: JSON with Credentials.AccessKeyId

# 2. Confirm AssumeRole FAILS without ExternalId
aws sts assume-role \
  --role-arn "$RECOUP_READONLY_ROLE_ARN" \
  --role-session-name test-session
# Expected: An error occurred (AccessDenied)

# 3. Confirm ReadOnly role cannot call StopInstances
CREDS=$(aws sts assume-role \
  --role-arn "$RECOUP_READONLY_ROLE_ARN" \
  --role-session-name test-stop \
  --external-id "$RECOUP_EXTERNAL_ID" \
  --query Credentials --output json)
AWS_ACCESS_KEY_ID=$(echo $CREDS | jq -r .AccessKeyId) \
AWS_SECRET_ACCESS_KEY=$(echo $CREDS | jq -r .SecretAccessKey) \
AWS_SESSION_TOKEN=$(echo $CREDS | jq -r .SessionToken) \
  aws ec2 stop-instances --instance-ids i-0d3389d7f950f7d3f
# Expected: An error occurred (UnauthorizedOperation)

# 4. Confirm scan API works end-to-end
curl -s -X POST http://localhost:8000/api/scan/preview \
  -H "Content-Type: application/json" \
  -d '{"role_arn":"'"$RECOUP_READONLY_ROLE_ARN"'","external_id":"'"$RECOUP_EXTERNAL_ID"'"}' \
  | jq '{assumed_role_arn,assumed_role_account_id,findings_count:.findings|length}'
```

---

## CDK Deployment

```bash
# Build + deploy (first time after Phase 0 deploy):
cd infra/cdk
npm run build
npx cdk deploy RecoupIamStack

# The stack outputs three values:
#   RecoupReadOnlyRoleArn   → set as RECOUP_READONLY_ROLE_ARN in .env
#   RecoupRemediationRoleArn → set as RECOUP_REMEDIATION_ROLE_ARN in .env
#   ExternalId              → set as RECOUP_EXTERNAL_ID in .env

# Tear down (removes both new roles, does not affect InfraStack):
npx cdk destroy RecoupIamStack
```

---

## Related Documentation

- [`docs/iam-roles.md`](iam-roles.md) — full role inventory with permissions
- [`docs/cross-account-onboarding.md`](cross-account-onboarding.md) — customer role setup guide
- [`docs/architecture-overview.md`](architecture-overview.md) — system architecture with STS flow
- [`infra/cdk/lib/stacks/iam-stack.ts`](../infra/cdk/lib/stacks/iam-stack.ts) — CDK source
