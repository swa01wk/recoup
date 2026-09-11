# Recoup IAM Role Inventory

All roles are created by CDK. Follows least-privilege; default deny on all write actions.

**Phase 6e update:** Added `RecoupReadOnlyRole` and `RecoupRemediationRole` via `RecoupIamStack`.
Role count: **6** (was 4). See [`docs/iam-architecture.md`](iam-architecture.md) for the full STS design.

---

## RecoupRuntimeRole

**Purpose:** Assumed by Amazon Bedrock AgentCore Runtime to execute the recovery agent graph.

**Trust Principal:** `bedrock.amazonaws.com`

**Permissions:**
| Permission | Resources | Reason |
|-----------|----------|--------|
| `AmazonBedrockFullAccess` (managed) | `*` | Invoke Bedrock models |
| DynamoDB read/write | `recoup-opportunities`, `recoup-approvals`, `recoup-tool-audits`, `recoup-outcome-metadata` | State machine + audit log |
| S3 read/write | `recoup-evidence-*` | Store evidence |
| S3 read | `recoup-sla-catalog-*`, `recoup-eval-fixtures-*` | Load SLA contracts + fixtures |
| KMS encrypt/decrypt | `alias/recoup-evidence` | Evidence encryption |
| CloudWatch Logs write | `/recoup/runtime` | Runtime logs |
| `sts:AssumeRole` | `RecoupReadOnlyRole` ARN | Phase 6e — analysis via STS |
| `sts:AssumeRole` | `RecoupRemediationRole` ARN | Phase 6e — remediation via STS |

**What it cannot do:**
- Call AWS Service APIs directly for analysis (must assume ReadOnlyRole)
- Call `ec2:StopInstances` directly (must assume RemediationRole)
- Call AWS Support API directly (requires `RecoupSubmissionRole` + approval)
- Write to S3 buckets outside `recoup-*` prefix

---

## RecoupGatewayExecutionRole

**Purpose:** Assumed by AgentCore Gateway to invoke Lambda tool targets and emit traces.

**Trust Principal:** `bedrock.amazonaws.com`

**Permissions:**
| Permission | Resources | Reason |
|-----------|----------|--------|
| `lambda:InvokeFunction` | `arn:aws:lambda:{region}:{account}:function:recoup-*` | Invoke tool Lambdas |
| CloudWatch Logs write | `/recoup/gateway` | Gateway logs |

**What it cannot do:**
- Read or write DynamoDB directly
- Read S3 buckets
- Invoke Lambda functions outside the `recoup-*` prefix

---

## RecoupReadConnectorRole

**Purpose:** Assumed by read-only tool Lambda functions to query AWS data sources.

**Trust Principal:** `lambda.amazonaws.com`

**Permissions:**
| Action | Reason |
|--------|--------|
| `cloudwatch:GetMetricStatistics`, `cloudwatch:GetMetricData`, `cloudwatch:DescribeAlarms` | Fetch availability metrics |
| `logs:FilterLogEvents`, `logs:GetLogEvents` | Fetch error logs for evidence |
| `health:DescribeEvents`, `health:DescribeEventDetails`, `health:DescribeAffectedEntities` | Fetch SLA incident data |
| `ce:GetCostAndUsage`, `ce:GetCostForecast`, `ce:GetAnomalies`, `ce:GetRecommendations` | Fetch billing data for credit calculation |
| `cloudtrail:LookupEvents` | Verify EC2 ownership, audit trail |
| `ec2:DescribeInstances` | Check instance tags before stop |
| `support:DescribeCases` | Monitor case status |
| `AWSLambdaBasicExecutionRole` (managed) | CloudWatch Logs write for Lambda |

**All permissions are read-only.** No `Create*`, `Put*`, `Delete*`, `Update*`, or `Stop*` actions.

---

## RecoupSubmissionRole (Phase 2+)

**Purpose:** Assumed only after `REQUIRE_APPROVAL` policy decision + human approval to submit real support cases.

**Trust Principal:** `lambda.amazonaws.com` with condition `aws:RequestedRegion = us-east-1`

**Permissions:**
| Action | Resources | Reason |
|--------|----------|--------|
| `support:CreateCase` | `*` | Submit SLA claim to AWS Support |
| `support:DescribeCases` | `*` | Monitor case status |

**Activation conditions:**
- `PolicyDecision == REQUIRE_APPROVAL` AND
- `ApprovalRecord.state == APPROVED` AND
- `ApprovalRecord.expires_at > now()` AND
- `ApprovalRecord.claim_hash == ClaimPackage.hash`

---

## Key IAM Principles

1. **Default deny** — no `Allow *` on sensitive actions
2. **Resource scoping** — DynamoDB/S3/Lambda ARNs scoped to `recoup-*` prefix where possible
3. **No wildcard writes** — all write actions have explicit resource conditions
4. **Separation** — read tools, write tools, and submission each have different roles
5. **Human gate** — `RecoupSubmissionRole` cannot be assumed without a valid approval token
6. **Temporary credentials via STS** — no long-lived analysis keys; `RecoupReadOnlyRole` credentials expire within 1 hour (Phase 6e)

---

## RecoupReadOnlyRole *(Phase 6e)*

**Purpose:** Broad read-only analysis access assumed via STS AssumeRole. Called by scanners and discovery tools.

**Trust Principal:** `RecoupRuntimeRole` (same account) with `sts:ExternalId` condition.

**CDK Stack:** `RecoupIamStack` (`infra/cdk/lib/stacks/iam-stack.ts`)

**What it can do:**
- `ec2:Describe*` — inventory discovery
- `cloudwatch:GetMetric*`, `logs:FilterLogEvents` — telemetry
- `ce:GetCostAndUsage`, `ce:GetAnomalies` — billing analysis
- `cloudtrail:LookupEvents` — change attribution
- `rds:Describe*`, `lambda:List*`, `s3:ListAllMyBuckets` — multi-service inventory
- `tag:GetResources` — untagged resource detection
- `compute-optimizer:Get*` — right-sizing recommendations

**What it cannot do:** No `ec2:StopInstances`, no `s3:PutObject`, no write action on any service.

---

## RecoupRemediationRole *(Phase 6e)*

**Purpose:** Narrowly scoped write role for approved remediation actions only. Never used for reads.

**Trust Principal:** `RecoupRuntimeRole` (same account) with `sts:ExternalId` condition.

**CDK Stack:** `RecoupIamStack`

**What it can do:**
- `ec2:StopInstances` — only where `ec2:ResourceTag/RecoupDemo = true`
- `ec2:DescribeTags`, `ec2:DescribeInstances` — tag verification before stop

**What it cannot do:**
- `ec2:TerminateInstances` — **explicitly denied** (cannot be overridden by any Allow)
- No read permissions (CloudWatch, Cost Explorer, etc.)

---

## ExternalId

Both `RecoupReadOnlyRole` and `RecoupRemediationRole` require an `ExternalId` condition in their trust policies.

| Property | Detail |
|---|---|
| Stored in | `RECOUP_EXTERNAL_ID` env var |
| Purpose | Prevents Confused Deputy attack — attacker cannot force AssumeRole without knowing this value |
| Rotation | Update env var → redeploy `RecoupIamStack` |
| Failure mode | Missing or wrong ExternalId → `AccessDenied` from STS → HTTP 400 in scanner API |

---

## Verification

```bash
# List all Recoup roles
aws iam list-roles --query "Roles[?starts_with(RoleName,'Recoup')].RoleName" --output table

# Inspect a specific role's trust policy
aws iam get-role --role-name RecoupRuntimeRole \
  --query 'Role.AssumeRolePolicyDocument' --output json

# List inline policies on a role
aws iam list-role-policies --role-name RecoupReadConnectorRole
```
