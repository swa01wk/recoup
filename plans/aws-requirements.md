# Recoup — AWS Requirements & Service Inventory

> **Historical / provisioning reference.** IAM and CDK inventory remain useful; runtime metrics and UI flows: [docs/README.md](../docs/README.md).

**Document purpose:** Complete reference for every AWS service, resource, permission, and configuration required to build, run, and demo Recoup. Use this as the single source of truth when provisioning the AWS account and when writing CDK/Terraform stacks.

**Last updated:** Sep 11, 2026  
**Rules reference:** [R2] AgentCore, [R6] AgentCore Policy, [R7] AgentCore Observability, [R8] Health/EventBridge, [R9] Support API, [R11] Cost Anomaly Detection, [R12] Cost Optimization Hub, [R13] CloudWatch  

> **Historical inventory.** Service/resource list remains valid for provisioning. **Test metrics:** [docs/README.md](../docs/README.md) (**420** backend · **279** Playwright · **28** specs).

---

## 1. AWS Account Prerequisites

| Requirement | Details | Required by |
|------------|---------|------------|
| AWS Account | Standard account; no special entitlement needed for core features | Phase 0 |
| AWS Builder ID | Must be created at builder.aws before Sep 13 | Submission |
| AWS Credits | Request before Sep 11 noon PT deadline | Phase 0 |
| AWS Region | Primary: `us-east-1` (matches canonical replay fixture) | Phase 0 |
| Cost Alarm | CloudWatch alarm at $10 estimated charges | Phase 0 |
| Support Plan | Basic (default) is sufficient for EventBridge Health events; Support API requires qualifying plan (not required for demo) | Phase 3 |

---

## 2. Amazon Bedrock AgentCore

### 2.1 AgentCore Runtime

> Hosts the Strands Graph with isolated sessions and async-friendly execution.

**Service:** Amazon Bedrock AgentCore Runtime

| Resource | Name | Configuration |
|---------|------|--------------|
| Runtime instance | `recoup-recovery-agent` | Strands graph entry point configured |
| Session isolation | Per-opportunity sessions | `session_idle_timeout_seconds: 3600` |
| Execution role | `RecoupRuntimeRole` | See IAM section |
| Log group | `/recoup/runtime` | CloudWatch |
| Model configuration | Set via `BEDROCK_MODEL_ID` env var | Never hard-coded |

**Required permissions for Runtime role:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "arn:aws:bedrock:us-east-1::foundation-model/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:Query"
      ],
      "Resource": [
        "arn:aws:dynamodb:us-east-1:*:table/recoup-*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::recoup-evidence-*/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:InvokeGateway"
      ],
      "Resource": "*"
    }
  ]
}
```

### 2.2 AgentCore Gateway

> Exposes narrow MCP-compatible tools for AWS data and actions.

**Service:** Amazon Bedrock AgentCore Gateway

| Tool Name | Action Class | Target | Lambda Name |
|-----------|-------------|--------|------------|
| `get_cloudwatch_metrics` | READ | Lambda | `recoup-cw-tool` |
| `query_cloudwatch_logs` | READ_SENSITIVE | Lambda | `recoup-cw-logs-tool` |
| `get_health_event` | READ | Lambda | `recoup-health-tool` |
| `get_cost_and_usage` | READ_FINANCIAL | Lambda | `recoup-cost-tool` |
| `get_cost_anomalies` | READ_FINANCIAL | Lambda | `recoup-cost-tool` |
| `list_cost_optimization_recommendations` | READ_FINANCIAL | Lambda | `recoup-cost-tool` |
| `lookup_cloudtrail_events` | READ_SENSITIVE | Lambda | `recoup-cloudtrail-tool` |
| `store_evidence` | WRITE_INTERNAL | Lambda | `recoup-evidence-tool` |
| `create_approval_request` | WRITE_INTERNAL | Lambda | `recoup-approval-tool` |
| `submit_support_case` | WRITE_EXTERNAL_FINANCIAL | Lambda | `recoup-support-tool` |
| `simulate_support_case` | WRITE_INTERNAL | Lambda | `recoup-simulate-tool` |
| `stop_demo_instance` | MUTATE_RED | Lambda | `recoup-ec2-demo-tool` |

**Gateway execution role (`RecoupGatewayExecutionRole`):**
- Invoke registered Lambda targets
- Evaluate AgentCore Policy
- Emit logs to `/recoup/gateway`

### 2.3 AgentCore Policy

> Cedar policies govern MCP tool calls; default deny for sensitive actions.

**Service:** Amazon Bedrock AgentCore Policy

**Policy file:** `infra/policy/recoup-policy.cedar`

**Key rules:**
1. PERMIT all READ tools for authenticated runtime sessions
2. PERMIT `submit_support_case` ONLY when: `simulation_mode=false` AND `approval_state=APPROVED` AND `approval_amount=claim_amount` AND `approval_expires_at > now` AND `state_version matches`
3. PERMIT `stop_demo_instance` ONLY when: `approval=APPROVED` AND `target_tag=RecoupDemo=true` AND `target_account=allowlisted`
4. FORBID all destructive tools (terminate, delete, mutate IAM)
5. FORBID `submit_support_case` when `simulation_mode=true`

**Context fields injected by Strands hooks (BeforeToolCall):**
- `session_authenticated`
- `simulation_mode`
- `approval_state`
- `approval_amount`
- `claim_amount`
- `approval_expires_at`
- `current_time`
- `opportunity_state_version`
- `approved_state_version`
- `target_instance_tag`
- `target_account_id`
- `allowlisted_demo_account_id`
- `recoup_enable_real_submission`

### 2.4 AgentCore Observability

> Agent/runtime/tool/policy metrics, logs, and traces.

**Service:** Amazon Bedrock AgentCore Observability

**CloudWatch log groups:**
- `/recoup/runtime` — Strands Graph execution logs
- `/recoup/gateway` — Tool call logs (sanitized; no raw evidence)
- `/recoup/api` — FastAPI request/response logs

**Metrics to emit:**
- `recoup/node/duration_ms` — per node
- `recoup/tool/latency_ms` — per tool call
- `recoup/tool/policy_decision` — ALLOW/DENY counts
- `recoup/opportunity/state_transitions` — per state
- `recoup/replay/duration_ms` — end-to-end replay timing
- `recoup/evidence/redaction_count` — per evidence collection

---

## 3. Amazon Bedrock (Foundation Models)

**Service:** Amazon Bedrock (model invocation)

| Configuration | Value |
|--------------|-------|
| Model selection | Set via `BEDROCK_MODEL_ID` environment variable; never hard-coded |
| Active model | `us.amazon.nova-pro-v1:0` (Amazon Nova Pro — confirmed in `strands_agents.py` + `/api/config`) |
| Region | `us-east-1` |
| Invocation method | Via Strands `BedrockModel` → AgentCore Runtime / direct Bedrock depending on config |

**IAM:** Runtime role has `bedrock:InvokeModel` on `arn:aws:bedrock:us-east-1::foundation-model/*`

---

## 4. AWS EventBridge

**Service:** Amazon EventBridge

| Resource | Name | Configuration |
|---------|------|--------------|
| Rule | `RecoupHealthEventRule` | Source: `["aws.health"]`; all regions |
| Target | SQS queue | `recoup-recovery-events` |
| Dead letter | SQS DLQ | `recoup-recovery-events-dlq` |

**EventBridge notes:**
- All AWS customers receive Health events via EventBridge at no additional cost
- No AWS Health API entitlement required for EventBridge Health events
- For demo: inject replay event with same normalized schema through the normalizer; EventBridge not called during replay
- Both public and account-specific Health events can be matched

**Sample Health event schema (matches real `aws.health` format):**
```json
{
  "version": "0",
  "id": "event-id",
  "source": "aws.health",
  "account": "123456789012",
  "time": "2026-08-01T02:00:00Z",
  "region": "us-east-1",
  "detail-type": "AWS Health Event",
  "detail": {
    "service": "APIGATEWAY",
    "eventTypeCode": "AWS_APIGATEWAY_OPERATIONAL_ISSUE",
    "eventTypeCategory": "issue",
    "region": "us-east-1",
    "startTime": "Thu, 1 Aug 2026 02:00:00 GMT",
    "endTime": "Thu, 1 Aug 2026 02:30:00 GMT",
    "statusCode": "closed",
    "affectedEntities": [
      { "entityValue": "arn:aws:apigateway:us-east-1::/restapis/demo1234" }
    ]
  }
}
```

---

## 5. Amazon SQS

**Service:** Amazon SQS

| Queue | Name | Configuration |
|-------|------|--------------|
| Recovery events | `recoup-recovery-events` | Standard; visibility timeout 300s; DLQ after 3 failures |
| Dead letter | `recoup-recovery-events-dlq` | Standard; retention 14 days |

**Message retention:** 14 days  
**Max message size:** 256 KB  
**Consumer:** Event normalizer Lambda / FastAPI worker

---

## 6. Amazon DynamoDB

**Service:** Amazon DynamoDB

### Tables

#### `recoup-opportunities`
| Attribute | Type | Key |
|-----------|------|-----|
| `id` | String | Partition key |
| `account_id_masked` | String | |
| `service` | String | |
| `region` | String | |
| `state` | String | |
| `state_version` | Number | Used for optimistic locking |
| `discovered_at` | String (ISO) | |
| `potential_value` | String (Decimal) | |
| `confidence` | Number | |
| `simulation_mode` | Boolean | |
| `idempotency_key` | String | |

**GSIs:**
- `account-state-index`: partition=`account_id_masked`, sort=`state`
- `state-discovered-index`: partition=`state`, sort=`discovered_at`

#### `recoup-approvals`
| Attribute | Type | Key |
|-----------|------|-----|
| `approval_id` | String | Partition key |
| `opportunity_id` | String | |
| `principal` | String | |
| `action` | String | |
| `amount` | String (Decimal) | |
| `claim_hash` | String | |
| `state_version` | Number | |
| `state` | String | PENDING/APPROVED/EXPIRED/REVOKED |
| `expires_at` | Number (TTL) | DynamoDB TTL attribute |

#### `recoup-tool-audits`
| Attribute | Type | Key |
|-----------|------|-----|
| `trace_id` | String | Partition key |
| `timestamp` | String | Sort key |
| `opportunity_id` | String | |
| `node` | String | |
| `tool` | String | |
| `request_hash` | String | |
| `response_hash` | String | |
| `policy_decision` | String | |
| `latency_ms` | Number | |

#### `recoup-outcome-metadata`
| Attribute | Type | Key |
|-----------|------|-----|
| `pk` | String (service#region#month) | Partition key |
| `outcome` | String | RECOVERED/REJECTED/NEEDS_FOLLOWUP |
| `recovered_value` | String (Decimal) | |

**Capacity:** On-demand (PAY_PER_REQUEST) for all tables  
**Encryption:** AWS-managed CMK

---

## 7. Amazon S3

**Service:** Amazon S3

### Buckets

#### `recoup-evidence-{account-id}-{region}`
| Setting | Value |
|---------|-------|
| Versioning | Enabled |
| Server-side encryption | SSE-KMS with `RecoupEvidenceKey` CMK |
| Public access | Blocked (all public access blocked) |
| Lifecycle | Archive raw evidence to Glacier after 90 days |

**Prefix structure:**
```
recoup-evidence/
├── raw/{opportunity_id}/{field}/{uuid}.json     # encrypted raw evidence; never shown to users
├── sanitized/{opportunity_id}/{field}/{uuid}.json  # redacted version
└── claims/{opportunity_id}/package.json        # claim package manifest
```

#### `recoup-sla-catalog-{account-id}-{region}`
| Setting | Value |
|---------|-------|
| Versioning | Enabled |
| Encryption | SSE-S3 |
| Access | Read by `RecoupRuntimeRole`; write by CI/deploy only |

**Contents:**
```
sla_catalog/
├── api_gateway/
│   └── 2022-05-05.yaml
└── [future services]
```

#### `recoup-eval-fixtures-{account-id}-{region}`
| Setting | Value |
|---------|-------|
| Versioning | Enabled |
| Encryption | SSE-S3 |
| Access | Read by `RecoupRuntimeRole` and CI role |

**Contents:**
```
eval_fixtures/
└── sla/api_gateway/canonical/
    ├── health_event.json
    ├── metric_series.json
    ├── billing_snapshot.json
    ├── cloudtrail_events.json
    └── expected_output.json
```

---

## 8. AWS KMS

**Service:** AWS Key Management Service

| Key | Alias | Usage |
|-----|-------|-------|
| `RecoupEvidenceKey` | `alias/recoup-evidence` | Encrypt raw evidence in S3; encrypt DynamoDB at rest |

**Key policy:** Only `RecoupRuntimeRole` and KMS admin can use the key. Frontend role cannot access it.

---

## 9. Amazon CloudWatch

**Service:** Amazon CloudWatch

### Log Groups
| Log Group | Retention | Purpose |
|-----------|-----------|---------|
| `/recoup/runtime` | 30 days | Strands Graph execution + AgentCore Runtime |
| `/recoup/gateway` | 30 days | Tool call logs (sanitized) |
| `/recoup/api` | 7 days | FastAPI request/response |
| `/recoup/ec2-demo` | 7 days | EC2 demo tool audit trail |

### Metrics (CloudWatch Agent / custom metrics)
| Metric | Namespace | Dimensions |
|--------|-----------|-----------|
| `node_duration_ms` | `Recoup/Graph` | NodeName |
| `tool_latency_ms` | `Recoup/Tools` | ToolName, PolicyDecision |
| `opportunity_state_count` | `Recoup/Opportunities` | State |
| `replay_duration_ms` | `Recoup/Replay` | — |
| `evidence_redaction_count` | `Recoup/Evidence` | EvidenceType |
| `unsafe_action_attempts` | `Recoup/Safety` | ToolName |

### Alarms
| Alarm | Threshold | Action |
|-------|-----------|--------|
| `RecoupSpendAlarm` | $10 estimated charges | SNS notification |
| `RecoupUnsafeActionAlarm` | unsafe_action_attempts > 0 | SNS notification (critical) |
| `RecoupReplayLatencyAlarm` | replay_duration_ms P95 > 60000 | SNS notification |

### CloudWatch for SLA Evidence
- Use `GetMetricData` for interval-level API Gateway telemetry
- Scope to synthetic API/region/time window for demo
- One request retrieves multiple metrics/data points
- Convert to 5-minute availability intervals for calculator

---

## 10. AWS Cost Explorer

**Service:** AWS Cost Explorer

| API | V1 Use | Permission Required |
|-----|--------|-------------------|
| `GetCostAndUsage` | Get service/region charges for billing cycle | `ce:GetCostAndUsage` |
| `GetCostForecast` | Optional: show spend trend | `ce:GetCostForecast` |

**IAM on `RecoupReadConnectorRole`:**
```json
{
  "Effect": "Allow",
  "Action": [
    "ce:GetCostAndUsage",
    "ce:GetCostForecast"
  ],
  "Resource": "*"
}
```

**Note:** Cost Explorer API calls cost $0.01 per API call. Use replay fixtures for demo to avoid cost.

---

## 11. AWS Cost Anomaly Detection

**Service:** AWS Cost Anomaly Detection

| API | V1 Use | Permission |
|-----|--------|-----------|
| `GetAnomalies` | Anomaly Impact and RootCauses for trigger/enrichment | `ce:GetAnomalies` |

**Usage:** Supporting module — anomaly detection signals feed the `incident_correlation` agent node as an alternative trigger source alongside Health events.

---

## 12. AWS Cost Optimization Hub

**Service:** AWS Cost Optimization Hub

| API | V1 Use | Permission |
|-----|--------|-----------|
| `ListRecommendations` | Read action type, savings, implementation effort | `cost-optimization-hub:ListRecommendations` |

**Usage:** Recoup is NOT a replacement for Cost Optimization Hub. It consumes Cost Optimization Hub signals and performs the operational closure work. Cost Optimization Hub is an input, not the product.

---

## 13. AWS CloudTrail

**Service:** AWS CloudTrail

| API | V1 Use | Permission |
|-----|--------|-----------|
| `LookupEvents` | Find resource change actors/events; correlate suspicious spend | `cloudtrail:LookupEvents` |

**Note:** CloudTrail log data is READ_SENSITIVE — contains PII and API call detail. All CloudTrail evidence passes through the sanitization pipeline before any use.

---

## 14. AWS Health

**Service:** AWS Health (via EventBridge)

| Integration | Details |
|------------|---------|
| EventBridge | Primary V1 integration; all accounts receive Health events at no cost |
| AWS Health API | Optional; requires qualifying support plan; NOT required for demo |
| Event schema | `source: "aws.health"`, `detail-type: "AWS Health Event"` |

**Key facts:**
- All AWS customers receive Health events through EventBridge at no additional cost
- Direct AWS Health API access depends on qualifying support plans
- EventBridge is correct V1 integration — no support plan dependency
- Both public and account-specific Health events can be matched via EventBridge

---

## 15. AWS Support API

**Service:** AWS Support

| API | V1 Use | When Available |
|-----|--------|---------------|
| `CreateCase` | Submit SLA credit claim (real mode only) | Qualifying support plan required |
| `DescribeCases` | Check case status | Same |
| `AddCommunicationToCase` | Follow up on case | Same |

**Critical constraints:**
- The judge demo NEVER depends on this API
- `submit_support_case` tool is disabled by default; requires `RECOUP_ENABLE_REAL_SUPPORT_SUBMISSION=true` + qualifying account + explicit approval + policy ALLOW
- For all demos: use `simulate_support_case` → `REPLAY-*` case id
- **Do not submit a fabricated SLA claim to AWS Support** — serious compliance violation

**IAM (`RecoupSubmissionRole`):**
```json
{
  "Effect": "Allow",
  "Action": [
    "support:CreateCase",
    "support:DescribeCases",
    "support:AddCommunicationToCase"
  ],
  "Resource": "*"
}
```
This role is assumed only after human approval + policy ALLOW. Not available to the frontend.

---

## 16. Amazon EC2

**Service:** Amazon EC2 (demo only)

| Resource | Configuration |
|---------|--------------|
| Demo instance | `t3.micro`; tag `RecoupDemo=true`; tag `ManagedBy=recoup` |
| Instance ID | Stored in `RECOUP_DEMO_INSTANCE_ALLOWLIST` env var |
| Actions allowed | `StopInstances` ONLY |
| Actions forbidden | `TerminateInstances`, `RebootInstances`, `ModifyInstanceAttribute` |

**IAM (`RecoupReadConnectorRole` for EC2 reads, separate for stop):**
```json
{
  "Effect": "Allow",
  "Action": [
    "ec2:DescribeInstances",
    "ec2:DescribeTags",
    "ec2:DescribeInstanceStatus"
  ],
  "Resource": "*"
},
{
  "Effect": "Allow",
  "Action": "ec2:StopInstances",
  "Resource": "arn:aws:ec2:us-east-1:*:instance/${DEMO_INSTANCE_ID}",
  "Condition": {
    "StringEquals": {
      "aws:ResourceTag/RecoupDemo": "true"
    }
  }
}
```

**Forbidden in IAM (explicit deny):**
```json
{
  "Effect": "Deny",
  "Action": [
    "ec2:TerminateInstances",
    "ec2:ModifyInstanceAttribute"
  ],
  "Resource": "*"
}
```

---

## 17. AWS IAM — Complete Role Inventory

### RecoupRuntimeRole
- **Purpose:** Amazon Bedrock AgentCore Runtime execution
- **Trust:** `bedrock-agentcore.amazonaws.com`
- **Permissions:** Invoke Bedrock models; read/write Recoup DynamoDB tables; read/write Recoup S3 prefixes; invoke AgentCore Gateway; use KMS key for evidence bucket

### RecoupGatewayExecutionRole
- **Purpose:** AgentCore Gateway — invoke Lambda tools; evaluate AgentCore Policy
- **Trust:** `bedrock-agentcore-gateway.amazonaws.com`
- **Permissions:** Invoke registered Lambda ARNs; evaluate AgentCore Policy; emit logs to `/recoup/gateway`

### RecoupReadConnectorRole
- **Purpose:** AWS data reads for tool Lambdas
- **Trust:** Lambda
- **Permissions:** `cloudwatch:GetMetricData`, `logs:FilterLogEvents`, `ce:GetCostAndUsage`, `ce:GetAnomalies`, `cost-optimization-hub:ListRecommendations`, `cloudtrail:LookupEvents`, `ec2:DescribeInstances`, `ec2:DescribeTags`, `health:DescribeEventDetails` (if available)
- **Explicit deny:** All write actions; `ec2:TerminateInstances`; `s3:DeleteObject` on evidence bucket

### RecoupSubmissionRole
- **Purpose:** AWS Support API — assumed only after approval + policy
- **Trust:** Lambda (recoup-support-tool); assumed role, not a primary role
- **Permissions:** `support:CreateCase`, `support:DescribeCases`, `support:AddCommunicationToCase`
- **Condition:** Must be assumed with `sts:ExternalId` matching the approval ID

### RecoupFrontendRole
- **Purpose:** Frontend session authentication
- **Trust:** Cognito identity pool (or API Gateway IAM authorizer)
- **Permissions:** None directly; frontend receives only signed session tokens from FastAPI
- **Note:** Frontend never receives AWS service credentials

### RecoupCIRole
- **Purpose:** CI/CD pipeline (GitHub Actions)
- **Trust:** `github.com` OIDC
- **Permissions:** Read eval fixture S3 bucket; write scorecard to DynamoDB; CDK deploy for infra changes

---

## 18. CDK Stack Summary

**Stack:** `RecoupInfraStack`

```bash
# Deploy command
cd infra/cdk
npm install
npx cdk bootstrap --region us-east-1
npx cdk deploy RecoupInfraStack RecoupDemoStack --require-approval never
```

**Stack outputs (exported for application config):**
```
RecoupOpportunitiesTableName
RecoupApprovalsTableName
RecoupToolAuditsTableName
RecoupEvidenceBucketName
RecoupSLACatalogBucketName
RecoupEvalFixturesBucketName
RecoupEvidenceKMSKeyArn
RecoupRecoveryEventsQueueUrl
RecoupRuntimeRoleArn
RecoupGatewayExecutionRoleArn
RecoupReadConnectorRoleArn
RecoupDemoInstanceId
```

---

## 19. Estimated AWS Cost

> For a 14-day build + 30-day judging period. Set $10 alarm for early warning.

### 19.1 Infrastructure Overview (by service)

| Service | Estimated Cost | Notes |
|---------|---------------|-------|
| Bedrock AgentCore Runtime | ~$5–20 | Depends on replay count and model invocations |
| Bedrock model invocations | ~$5–15 | Nova Pro v1 / Claude 3.5 Sonnet; see model note in §21 |
| DynamoDB | ~$1 | On-demand; low volume |
| S3 | ~$1 | Evidence + fixture + scorecard storage |
| EventBridge | $0 | Health events free |
| SQS | $0 | Free tier |
| CloudWatch | ~$2 | Custom metrics + logs |
| Cost Explorer API | ~$1 | $0.01/call; use replay fixtures in demo |
| EC2 demo instance | ~$1 | t3.micro `i-0d3389d7f950f7d3f`; stop when not demoing |
| Lambda (tool functions) | ~$0 | Free tier |
| **Total estimate** | **~$15–40** | Monitor with billing alarm |

---

### 19.2 Demo-Specific Infrastructure Costs (per scenario)

#### One-Time Setup Costs

| Demo | Scenario | Resource provisioned | One-time cost | Notes |
|------|----------|---------------------|--------------|-------|
| **S1 / Part 2** | SLA Credit Recovery | API Gateway `recoup-sla-demo` (creation) | $0.00 | Free to create |
| **S1 / Part 2** | SLA Credit Recovery | 1,000,500 API Gateway calls via `inject_sla_traffic.py` | **$3.50** | $3.50/million calls |
| **S1 / Part 2** | SLA Credit Recovery | Lambda `recoup-sla-health` — 1M requests | $0.00 | Within free tier (first 1M/mo) |
| **S1 / Part 2** | SLA Credit Recovery | Lambda duration (128 MB × 50 ms × 1M = ~6,944 GB-s) | $0.00 | Within free tier (400K GB-s/mo) |
| **S1 / Part 2** | SLA Credit Recovery | CloudWatch Logs access logs (~10 MB) | $0.005 | $0.50/GB |
| **S1 / Part 2** | SLA Credit Recovery | CDK stack deploy (CloudFormation) | $0.00 | Free |
| **All demos** | Scanner workload resources | `RecoupDemoWorkloadsStack` CDK deploy | $0.00 | Free |
| | | **One-time total** | **≈ $3.51** | |

> Lambda is entirely within free tier (account `625962218034` confirmed: −$5.98 credits active). Total out-of-pocket for one-time setup: **≈ $3.51**.

---

#### Monthly Running Costs — Demo Waste Resources (Account Scanner, Part 1)

These resources exist **solely to demonstrate scan findings**. They are intentionally idle/misconfigured.

| Scan # | Resource | ID | Waste type | Reported savings | Actual monthly cost to keep live |
|--------|----------|-----|-----------|-----------------|----------------------------------|
| Scan-1 | EC2 t3.medium | `i-07057bf0f44dd8ee5` | Stopped / idle | $30.37/mo | **~$0.80/mo** (EBS storage only while stopped) |
| Scan-2 | EBS gp3 100 GiB | `vol-03227335ad49b9c4e` | Unattached volume | $10.00/mo | **$8.00/mo** ($0.08/GB/mo × 100 GiB) |
| Scan-3 | EBS gp2 50 GiB | `vol-0908db94e8019950b` | gp2 → gp3 candidate | $5.00/mo | **$5.00/mo** ($0.10/GB/mo × 50 GiB) |
| Scan-4 | Elastic IP | `eipalloc-03e6ded8240b64745` | Idle EIP | $3.65/mo | **$3.65/mo** ($0.005/hr unassociated) |
| Scan-5 | RDS db.t3.micro MySQL | `recoupdemoworkloadsstack-idlerds...` | Idle / stopped | $12.41/mo | **~$0.23/mo** (20 GiB storage only while stopped) |
| Scan-6 | S3 bucket | `recoupdemoworkloadsstack-nolifecycle...` | No lifecycle policy | $5.00/mo | **~$0.02/mo** (minimal objects) |
| Scan-7 | Lambda 1024 MB | `RecoupDemoWorkloadsStack-OversizedLambda...` | 0 invocations | $3.75/mo | **$0.00** (no invocations = no charge) |
| Scan-8 | EBS snapshot | `snap-005ea520968192a0c` | Stale snapshot (source deleted) | $0.05/GB/mo | **~$0.05/mo** (1 GiB snapshot) |
| | | | **Total waste resource cost** | | **≈ $17.75/mo** |

> **Note:** The "Reported savings" column is what Recoup surfaces to users as recoverable waste. The "Actual monthly cost" is lower because stopped EC2 and RDS don't accrue instance-hours. The scanner deliberately reports the would-be running cost to highlight the risk of restarting forgotten resources.

---

#### Monthly Running Costs — Core Demo Infrastructure

| Demo | Scenario | Resource | Monthly cost | Notes |
|------|----------|----------|-------------|-------|
| **S3 / Part 4** | Live EC2 Stop | Demo instance `i-0d3389d7f950f7d3f` (t3.micro) | **$7.59/mo** | Must be **running** before demo; stop after each run |
| **S1 / Part 2** | SLA Replay | API Gateway `recoup-sla-demo` idle | **$0.00** | No idle cost once 1M calls injected |
| **S1 / Part 2** | SLA Replay | Lambda `recoup-sla-health` idle | **$0.00** | No invocations = no charge |
| **All demos** | Backend / storage | DynamoDB tables (4×) on-demand | **~$0.50/mo** | Low volume |
| **All demos** | Evidence storage | S3 buckets (3× + demo workload) | **~$1.00/mo** | KMS-encrypted evidence accumulates |
| **All demos** | Observability | CloudWatch Logs (3 log groups, 30-day retention) | **~$1.50/mo** | `/recoup/runtime`, `/recoup/gateway`, `/recoup/api` |
| **S7 / Part 7** | CloudTrail | CloudTrail `LookupEvents` reads | **~$0.00** | Free for management events |
| **S8 / Part 8** | Tagging | Resource Groups Tagging API reads | **$0.00** | Free |
| **S9 / Part 9** | Cost Explorer | `GetCostAndUsage` (1–3 calls/day) | **~$0.30/mo** | $0.01/call; use cached responses where possible |
| | | **Core demo infrastructure total** | **≈ $10.89/mo** | |

---

#### Per-Run Incremental Costs

| Demo | Trigger | AWS calls made | Cost per run |
|------|---------|---------------|-------------|
| **S1 / Part 2** | `POST /api/replay/api-gateway-sla` | S3 `PutObject` ×4 (KMS-encrypted evidence), DynamoDB `PutItem` ×1, KMS encrypt ×4 | **~$0.000009** |
| **S2 / Part 3** | HITL approve via UI | DynamoDB `GetItem` + `PutItem`, CloudWatch `PutLogEvents` | **~$0.000002** |
| **S3 / Part 4** | `POST /api/ec2-demo/trigger` then approve + execute | EC2 `DescribeInstances` ×2, `DescribeTags` ×1, CloudWatch `GetMetricStatistics`, CloudTrail `LookupEvents`, `StopInstances` ×1 | **~$0.00001** |
| **S6 / Part 1** | `POST /api/scan/demo` | EC2 `DescribeInstances`, EBS `DescribeVolumes`, RDS `DescribeDBInstances`, Lambda `GetFunctionConfiguration` + `GetMetricStatistics`, S3 `ListBuckets`, CloudTrail `LookupEvents` | **~$0.00005** |
| **Quality / Part 6** | `POST /api/quality/scorecard` (20-run eval) | 20× replay run costs + S3 `PutObject` ×1 (scorecard) | **~$0.0002** |
| | | **Cost per full demo walkthrough (all 10 scenarios)** | **< $0.001** |

> Running the full demo suite 100 times costs less than $0.10 in incremental API charges.

---

### 19.3 Total Cost Estimate — Hackathon Period

| Period | Category | Cost |
|--------|----------|------|
| One-time setup | SLA injection (1M API Gateway calls) | $3.51 |
| Monthly (Sep 7 – Oct 8, ~30 days) | Demo waste resources (Scan-1 through Scan-8) | $17.75 |
| Monthly (Sep 7 – Oct 8, ~30 days) | Core demo infrastructure (EC2 + S3 + DynamoDB + CW) | $10.89 |
| Monthly (Sep 7 – Oct 8, ~30 days) | Bedrock model invocations (demos + development) | $5–15 |
| Monthly (Sep 7 – Oct 8, ~30 days) | AgentCore Runtime | $5–20 |
| Per-run (estimated 500 total demo + test runs) | Incremental API calls across all scenarios | < $0.50 |
| | **Total hackathon estimate** | **≈ $43–67** |

> Budget recommendation: request **$100 in AWS credits** — this provides comfortable headroom for active development, CI test runs, and judge review period through Oct 8.

---

### 19.4 Cost Containment

- **Stop demo EC2 `i-0d3389d7f950f7d3f`** between demo sessions (`./scripts/reset_demo_instance.sh` to restart)
- **Do not start `i-07057bf0f44dd8ee5` (waste EC2)** — scanner detects it correctly while stopped; starting it costs $30/mo
- **Do not start the idle RDS** — same logic; stopped = detectable at near-zero cost
- **Use replay fixtures** instead of re-calling real AWS APIs during development iteration
- **Cache Cost Explorer responses** — $0.01/call adds up; frontend caches for 1 hour
- **DynamoDB TTL** on approval records auto-deletes after 48h
- **CloudWatch log retention:** 30 days runtime/gateway, 7 days API
- **S3 Intelligent-Tiering** on evidence bucket (objects > 128 KB tiered after 30 days)
- **`RECOUP_MAX_REPLAY_RUNS_PER_DAY=100`** caps Bedrock invocations during development

---

## 20. Compliance Checklist

| Rule | Requirement | Status | Notes |
|------|------------|--------|-------|
| [R1] Fresh project | Repository created after Aug 10; first commit timestamped | ✅ | First commit `0bbe21e` |
| [R1] Public repo | GitHub repo public with license | ✅ | github.com/swa01wk/recoup, MIT |
| [R1] Judge access | Demo free and accessible through Oct 8, 2026 | 🔴 | Live URL pending (Phase 7 remaining — Vercel + Railway deploy) |
| [R2] AgentCore | Runtime + Gateway + Policy/Observability deployed | 🟡 | Runtime + Gateway registered (`recoup_recovery_agent-T9RRFljZUO`, `recoup-tool-gateway-tpnzqdgixc`). Strands agents call Bedrock via `BedrockModel` from Strands SDK. **Verify:** AgentCore Runtime is in the execution path (not just direct Bedrock). Harness + Gateway registered — confirm invocation goes through AgentCore for judge review. |
| [R6] AgentCore Policy | Cedar policies attached in enforcement mode; default deny | 🟡 | Cedar enforced in Python (`safety/cedar.py`). Claim binding tested: tampered hash/amount/version → 409 (**Playwright SEC-1/SEC-2/SEC-3 verified**). **Must verify** `recoup-policy.cedar` is attached to gateway in ENFORCING mode, not advisory. |
| [R7] AgentCore Observability | All metrics/logs routed to CloudWatch | 🟡 | CW log groups `/recoup/runtime`, `/recoup/gateway`, `/recoup/api`, `/recoup/ec2-demo` wired. `X-Request-ID` on all responses (**Playwright SEC-5/SEC-6 verified**). Custom node/tool metrics (`Recoup/Graph`, `Recoup/Tools`) — not yet publishing custom metric data points. |
| [R8] Health/EventBridge | EventBridge rule on aws.health; no support plan dependency | ✅ | Rule exists. **SQS poller live** — `sqs_poller.py` imported and `start_poller()` called in `main.py` lifespan. `sqs_events_enabled` exposed in `/api/config`. |
| [R9] Support API | Replay adapter is primary; real adapter behind feature flag | ✅ | `simulate_support_case` primary; `submit_support_case` behind `RECOUP_ENABLE_REAL_SUPPORT_SUBMISSION` flag. `real_submission_enabled` in `/api/config`. |
| [R10] Log redaction | Deterministic redaction before any log evidence leaves sanitizer | ✅ | 8 regex patterns, fail-closed, 66 Phase 3 tests. **Playwright SEC-9/SEC-10 verified**: account IDs masked as `XXXXXXXX`, no raw 12-digit IDs. Evidence sanitizer: `unsafe_actions=0`, `hallucinated_evidence=0` (quality scorecard). |
| [R11] Cost Anomaly | Anomaly module uses Impact and RootCauses fields | 🟡 | `get_cost_anomalies()` in `aws_tools.py` has **real `ce.get_anomalies()` call** (lines 204–237) with graceful fallback to `{"anomalies": [], "_stub": True, "_error": "live_call_failed"}` on error. Will return live data when CE anomalies exist in demo account. |
| [R12] Cost Opt Hub | Recommendations consumed as signals; not replicated | 🟡 | `list_cost_optimization_recommendations()` has **real `hub.list_recommendations()` call** (lines 272–289) with graceful fallback to stub on error. Will return live data when Cost Opt Hub has recommendations. |
| [R13] CloudWatch | GetMetricData for SLA evidence; proper scoping | ✅ | EC2 CPU check uses real `GetMetricStatistics`. SLA replay uses eval fixtures (deterministic 20/20). CloudWatch Logs scanner reads CW log groups. 4 log groups wired. |

---

## 21. Environment Variables

All environment variables must be set in the deployment environment. Never commit values to the repository.

```bash
# Bedrock
# ✅ Model resolved: Nova Pro confirmed in strands_agents.py (BedrockModel) and /api/config
# strands_agents.py uses settings.bedrock_model_id which defaults to us.amazon.nova-pro-v1:0
BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0
BEDROCK_REGION=us-east-1

# AgentCore
AGENTCORE_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-east-1:...
AGENTCORE_GATEWAY_URL=https://recoup-tool-gateway-tpnzqdgixc.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp

# DynamoDB
OPPORTUNITIES_TABLE=recoup-opportunities
APPROVALS_TABLE=recoup-approvals
TOOL_AUDITS_TABLE=recoup-tool-audits

# S3
EVIDENCE_BUCKET=recoup-evidence-{account}-us-east-1
SLA_CATALOG_BUCKET=recoup-sla-catalog-{account}-us-east-1
EVAL_FIXTURES_BUCKET=recoup-eval-fixtures-{account}-us-east-1
EVIDENCE_KMS_KEY_ID=arn:aws:kms:us-east-1:...:key/...

# SQS
RECOVERY_EVENTS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/...

# SNS (Phase 6b P1 — notifications on opportunity detected + EC2 stopped)
RECOUP_SNS_TOPIC_ARN=arn:aws:sns:us-east-1:625962218034:recoup-alerts

# EC2 Demo
RECOUP_DEMO_INSTANCE_ALLOWLIST=i-0d3389d7f950f7d3f
ALLOWLISTED_DEMO_ACCOUNT_ID=625962218034

# Feature flags (default false — explicit opt-in required)
RECOUP_ENABLE_LIVE_AWS=false
RECOUP_ENABLE_REAL_SUPPORT_SUBMISSION=false

# Cost control
RECOUP_MAX_REPLAY_RUNS_PER_DAY=100
```
