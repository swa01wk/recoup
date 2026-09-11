# Phase 0 — Foundation & Infrastructure Setup

> **Historical implementation plan.** Targets below reflect mid-build intent. **Current product & metrics:** [docs/README.md](../docs/README.md) · [STATUS.md](../STATUS.md) · [docs/judge-demo.md](../docs/judge-demo.md).



**Timeline:** Day 1–3 (Target: by Sep 3, 2026)  
**Status:** `[ ] Not Started`  
**Priority:** P0 — Everything blocks on this phase

---

## Objective

Establish a clean, competition-compliant repository, provision all AWS infrastructure via CDK, deploy the minimum viable AgentCore Runtime + Gateway, wire up CI, and configure IAM roles. This phase produces no user-visible product features but makes every subsequent phase possible.

---

## Goals

- [x] Fresh repository created within the Aug 10–Sep 14 competition window (preserve first-commit timestamp)
- [ ] Public GitHub repository with MIT/Apache-2.0 license visible from the repo root
- [ ] README stub and architecture diagram placeholder committed
- [ ] CDK/Terraform stack deploys successfully to sandbox AWS account
- [ ] AgentCore Runtime instance is reachable
- [ ] AgentCore Gateway registered with at least one stub tool
- [ ] DynamoDB tables created with correct schema
- [ ] S3 buckets (evidence, SLA catalog, eval fixtures) created with correct policies
- [ ] SQS queue for recovery events created
- [ ] EventBridge rule for `aws.health` events wired to SQS
- [ ] CloudWatch log groups and basic alarms in place
- [ ] CI pipeline running lint + unit tests on every push
- [ ] Cost alarm set (alert at $10 of spending)
- [ ] AWS Builder ID verified

---

## Workstreams

### 0.1 Repository Bootstrap

**Files to create:**

```
recoup/
├── README.md                    # stub with project description, quick-start
├── LICENSE                      # MIT or Apache-2.0 — must be visible from repo root
├── .gitignore
├── architecture/
│   └── architecture.png         # placeholder; updated in Phase 4
├── docs/
│   └── DISCLOSURE.md            # fresh-project disclosure per competition rules [R1]
├── plans/                       # this folder
├── backend/
│   ├── pyproject.toml
│   └── src/recoup/
├── frontend/
│   ├── package.json
│   └── src/
├── infra/
│   ├── cdk/
│   └── terraform/ (optional alt)
├── sla_catalog/
│   └── api_gateway/
│       └── 2022-05-05.yaml
└── .github/
    └── workflows/
        └── ci.yml
```

**Key actions:**
1. `git init` with a clear first commit dated within competition window
2. Add `DISCLOSURE.md` acknowledging this is a fresh project built during the hackathon
3. Confirm repository is **public** before submission

### 0.2 AWS Account Setup

**Prerequisites:**
- AWS account with sufficient permissions
- AWS Builder ID created at [builder.aws](https://builder.aws) — verify before Sep 13
- Request AWS credits before Sep 11 noon PT deadline

**IAM Roles to create:**

| Role | Purpose | Key Permissions |
|------|---------|----------------|
| `RecoupRuntimeRole` | Bedrock AgentCore Runtime | Invoke Bedrock; read/write Recoup DynamoDB/S3 prefixes; invoke Gateway |
| `RecoupGatewayExecutionRole` | AgentCore Gateway | Invoke Lambda targets; evaluate AgentCore Policy; emit logs/traces |
| `RecoupReadConnectorRole` | AWS data reads | Cost Explorer, CloudWatch, CloudTrail, resource Describe; no mutations |
| `RecoupSubmissionRole` | Support API (production only) | AWS Support API only; assumed only after approval + policy decision |
| `RecoupFrontendRole` | UI session | No direct AWS credentials; Cognito/IAM/JWT only |

**IAM Policy principles:**
- Default deny on all write actions
- Scope resource ARNs to Recoup prefixes where possible
- No `*` on sensitive actions (Support API, destructive EC2)
- All role assumptions require explicit condition keys

### 0.3 CDK Stack

**Stack: `RecoupInfraStack`**

Resources to provision:

```
DynamoDB Tables:
  recoup-opportunities      # partition: opportunity_id; GSI: account+state, state+discovered_at
  recoup-approvals          # partition: approval_id; TTL on expires_at
  recoup-tool-audits        # partition: trace_id; sort: timestamp
  recoup-outcome-metadata   # partition: service+region+month

S3 Buckets:
  recoup-evidence-{account}-{region}       # versioned; SSE-KMS; no public access
  recoup-sla-catalog-{account}-{region}   # versioned; read by runtime role
  recoup-eval-fixtures-{account}-{region} # versioned; CI read access

SQS Queues:
  recoup-recovery-events          # standard queue with DLQ
  recoup-recovery-events-dlq

EventBridge Rules:
  RecoupHealthEventRule    # source: ["aws.health"] → SQS target

CloudWatch:
  /recoup/runtime          # log group
  /recoup/gateway          # log group
  /recoup/api              # log group
  RecoupSpendAlarm         # alert at $10 estimated charges

KMS:
  RecoupEvidenceKey        # CMK for evidence bucket encryption
```

**CDK Commands:**
```bash
cd infra/cdk
npm install
npx cdk bootstrap
npx cdk deploy RecoupInfraStack
```

### 0.4 AgentCore Runtime Deployment

**Target:** Amazon Bedrock AgentCore Runtime

Steps:
1. Configure `agentcore-config.yaml` with graph entry point and session settings
2. Deploy the Strands graph stub (single no-op node) to confirm connectivity
3. Verify runtime creates isolated sessions
4. Wire CloudWatch log group `/recoup/runtime`

**Config template:**
```yaml
runtime:
  name: recoup-recovery-agent
  model_id: ${BEDROCK_MODEL_ID}   # set via environment, not hard-coded
  session_idle_timeout_seconds: 3600
  log_group: /recoup/runtime
  execution_role_arn: ${RECOUP_RUNTIME_ROLE_ARN}
```

### 0.5 AgentCore Gateway Registration

**Register stub tools (expand in Phase 1):**
- `get_cloudwatch_metrics` — READ
- `get_health_event` — READ
- `store_evidence` — WRITE_INTERNAL

Each tool registration must specify:
- Input/output schema (JSON Schema)
- Action class label (READ / WRITE_INTERNAL / WRITE_EXTERNAL_FINANCIAL / etc.)
- Lambda/API target ARN
- IAM execution role

### 0.6 CI Pipeline

**`.github/workflows/ci.yml`:**

```yaml
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -e ".[dev]"
      - run: pytest backend/tests/unit/ -v
      - run: ruff check backend/
      - run: mypy backend/src/
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: cd frontend && npm ci && npm run build
```

---

## Definition of Done

| Check | Criteria |
|-------|----------|
| Repository | Public, MIT/Apache license visible, README present, disclosure committed |
| CDK | `cdk deploy` runs without error; all resources exist in AWS console |
| AgentCore Runtime | Stub graph deploys; session can be created via API |
| AgentCore Gateway | Stub tool registered; invocation logged to CloudWatch |
| DynamoDB | Tables exist with correct key schema and GSIs |
| S3 | Buckets exist; versioning and encryption enabled |
| EventBridge | Rule exists; test health event routes to SQS |
| CI | Push to main triggers workflow; lint + unit tests pass |
| Cost alarm | Alarm exists and is in OK state |
| AWS Builder ID | Verified and accessible |

---

## Post-Implementation Documentation

> Created in `plans/docs/` after phase completion.

- `docs/infrastructure-runbook.md` — How to deploy, tear down, and redeploy the stack
- `docs/iam-roles.md` — Complete IAM role and policy inventory
- `docs/aws-resource-inventory.md` — All AWS resource ARNs with tagging conventions
- `docs/ci-guide.md` — CI pipeline documentation and how to add new test stages
- `docs/cost-management.md` — Billing alarms, budget tracking, and cost containment strategy

---

## Risks

| Risk | Mitigation |
|------|-----------|
| AgentCore Runtime availability/quota | Request access early; have a fallback to local Strands execution for dev |
| CDK bootstrap permission issues | Use `--profile` flag; ensure deployment role has sufficient permissions |
| Cost overrun | $10 CloudWatch alarm; disable unused services immediately |
| Competition window compliance | Preserve `git log` showing first commit after Aug 10 |
