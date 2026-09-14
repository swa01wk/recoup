# Phase 6b — Demo Realism & AWS Integration

> **Historical — internal only.** Current product: [docs index](../../../README.md) · [judge-demo.md](../../../judge-demo.md) · [STATUS.md](../STATUS.md).

> **As-built:** Governance demo APIs shipped (`/api/cloudtrail-demo`, `/api/tagging-demo`, `/api/cost-demo`). UI tiles on a single “Command Center” dashboard were **not** kept — prove via API curls or journey tests. See [docs/demo-playbook.md](../docs/demo-playbook.md).

**Timeline:** Sep 2–5, 2026  
**Status:** `[~] In Progress`  
**Depends on:** Phase 6 (Live AWS Action Proof) ✅  
**See also:** [Phase 6e](./phase-6e-iam-security-model-sts-assumerole.md) — IAM role architecture that governs how all 8 scenarios are accessed  
**See also:** [Phase 6f](./phase-6f-demo-workloads-stack-8-scenarios.md) — CDK stack deploying all 8 demo waste scenarios  
**Goal:** Close the data gaps between fixture-driven scenarios and real AWS — so every scene in the video touches real AWS services and every scenario is backed by real account data where possible.

---

## Context — Why This Phase Exists

The account (`625962218034`) is new. This creates gaps:
- No real API Gateway → no real SLA downtime data
- Cost Explorer just enabled → no historical billing data until Sep 3
- No active AWS Health incidents → no real Health event triggers
- Most resources exist but aren't yet wired into the demo flow

The strategy: **use the AWS services that ARE provisioned and have real data right now** to fill these gaps, and inject synthetic-but-real data into CloudWatch/EventBridge for the ones that don't.

---

## What Was Already Built (Sep 2, 2026)

These changes are complete and merged into the main codebase.

### S3 Evidence Writes — Scene 1
- Added `live_evidence: bool` flag to `EvidenceCollector`
- When `RECOUP_ENABLE_LIVE_AWS=true`, evidence JSONs (health event, metric series, billing, CloudTrail) land in real `recoup-evidence` S3 bucket with KMS encryption during the SLA replay
- Replay API response now returns `evidence_s3_uris` list — displayed in the Replay page UI as a green "Evidence Written to S3 — LIVE AWS" panel
- **Files changed:** `evidence/collector.py`, `graph/nodes.py`, `api/routes/replay.py`, `frontend/src/app/replay/page.tsx`, `frontend/src/lib/api.ts`

### CloudWatch Logs Audit Trail — Scene 2
- `HITLFlow.approve()`, `decline()`, and `create_request()` now write structured JSON events to CloudWatch Logs `/recoup/runtime` → stream `hitl-approvals`
- Events: `APPROVAL_REQUESTED`, `APPROVAL_GRANTED`, `APPROVAL_DECLINED`
- Fails silently — approval flow is never blocked by a CW error
- **Files changed:** `approval/flow.py`, `api/routes/approvals.py`

### DynamoDB Visibility — Scene 2
- Approval API responses now include `_aws.dynamodb_table`, `_aws.audit_log_group`, `_aws.live` fields
- Decision Inbox UI shows `● DynamoDB: recoup-approvals` and `● CloudWatch Logs: /recoup/runtime` badges in the header
- **Files changed:** `api/routes/approvals.py`, `frontend/src/app/approvals/page.tsx`

### S3 Scorecard Persistence — Scene 4
- After every quality run, scorecard JSON written to `s3://recoup-eval-fixtures/scorecards/{timestamp}.json`
- Response includes `scorecard_s3_uri` — shown as a green "Scorecard persisted to S3 — LIVE AWS" banner in the Quality Dashboard
- **Files changed:** `api/routes/quality.py`, `frontend/src/app/quality/page.tsx`

---

## Remaining Work — Prioritized

### Priority 1 — SNS Notifications (30 min) 🔴 Not Started

**AWS service:** SNS `recoup-alerts` topic  
**Email subscribed:** `swaroop.shivakumar@webknot.in`  
**Video moment:** Phone buzzes with real AWS email while you're on screen.

**When to fire:**
1. `POST /api/replay/api-gateway-sla` — "SLA credit opportunity detected ($0.35 from real billing) — approval required"
2. `POST /api/ec2-demo/execute/{id}` — "Instance i-0d3389d7f950f7d3f stopped — $7.59/month saved"

**What to build:**
- `_notify_sns(subject, message)` helper in a shared `notifications.py` module
- Call in `api/routes/replay.py` after `_run_canonical()` succeeds
- Call in `api/routes/ec2_demo.py` after successful stop execution
- Guard with `settings.recoup_enable_live_aws` flag — never fires in simulation

**Files to change:** `api/routes/replay.py`, `api/routes/ec2_demo.py`  
**New file:** `backend/src/recoup/notifications.py`  
**Env var needed:** `RECOUP_SNS_TOPIC_ARN` (add to `.env.example`)

---

### Priority 2 — SQS Opportunity Events (30 min) 🔴 Not Started

**AWS service:** SQS `recoup-recovery-events` queue  
**Video moment:** Show SQS console with the message sitting in the queue — proof the system is event-driven.

**When to publish:**
- On every new opportunity created (SLA replay + EC2 demo)

**Message format:**
```json
{
  "event_type": "OPPORTUNITY_DETECTED",
  "opportunity_id": "opp-...",
  "type": "SLA_CREDIT" | "OPTIMIZATION",
  "potential_value_usd": "0.35",
  "service": "apigateway",
  "region": "us-east-1",
  "detected_at": "2026-09-02T...",
  "requires_approval": true
}
```

**What to build:**
- `_publish_sqs(payload)` helper in `notifications.py`
- Call in `api/routes/replay.py` and `api/routes/ec2_demo.py`
- Guard with `settings.recoup_enable_live_aws`

**Env var needed:** `RECOUP_SQS_QUEUE_URL` (already exists as `recovery_events_queue_url` in config)

---

### Priority 3 — CloudTrail No-Actor Standalone Scenario (1–2h) 🔴 Not Started

**AWS service:** CloudTrail `LookupEvents`  
**Data available NOW:** All CloudTrail events for `i-0d3389d7f950f7d3f` in last 24h are `AssumeRole` with `User: None`. Root account making `DescribeMetricFilters` every 5 min. `Decrypt` events with `User: None`.  
**Video moment:** Show a real scenario card: "Cost anomaly detected — no human actor found in CloudTrail. Human review required."

**What to build:**
- `GET /api/cloudtrail-demo/check` — calls real `CloudTrail.lookup_events()`, returns attribution analysis
- New scenario card in Command Center: "CloudTrail Attribution Gap" with `actor_attributed: false`, `requires_human_review: true`
- New frontend card with red "NO HUMAN ACTOR" badge

**Backend files:** `api/routes/cloudtrail_demo.py`, `api/main.py`  
**Frontend files:** `frontend/src/app/page.tsx` (new card)

---

### Priority 4 — Missing Cost Allocation Tags Scenario (2–3h) 🔴 Not Started

**AWS service:** ResourceGroupsTaggingAPI `get_resources()`  
**Data available NOW:** EC2 `i-0d3389d7f950f7d3f` missing `cost:team`, `environment`. SQS queues, SNS topic, CloudWatch alarms — all missing `cost:team`.  
**Video moment:** Show a live scan: "6 resources found without required cost allocation tags — estimated attribution gap: $X/month"

**What to build:**
- `GET /api/tagging-demo/scan` — calls `ResourceGroupsTaggingAPI.get_resources()`, filters for missing `cost:team` / `environment` tags, returns findings
- New scenario card in Command Center: "Missing Cost Allocation Tags" with resource list
- Show resource ARNs, missing tags, affected monthly cost estimate

**Backend files:** `api/routes/tagging_demo.py`, `api/main.py`  
**Frontend files:** `frontend/src/app/page.tsx` (new card), `frontend/src/app/tagging/page.tsx`

---

### Priority 5 — CloudWatch Metric Injection for SLA Scene (2h) 🔴 Not Started

**AWS service:** CloudWatch `put_metric_data` + `get_metric_statistics`  
**Goal:** Make Scene 1 data-driven by writing the 8,640 five-minute intervals into a real CloudWatch namespace (`Recoup/SLA/Demo`), then reading them back — so the CloudWatch console shows a real chart with a real dip.

**What to build:**
- Script: `scripts/inject_sla_metrics.py` — writes 8,640 data points to `Recoup/SLA/Demo` namespace with metric `Availability5min`; 6 zero-availability windows at 2026-08-01T02:00–02:30Z
- Update `incident_correlation_stub` in `graph/nodes.py` to check for real CloudWatch data in `Recoup/SLA/Demo` namespace before falling back to fixtures
- Optional: create a CloudWatch Dashboard `Recoup-SLA-Demo` showing the chart

**Files:** `scripts/inject_sla_metrics.py`, `graph/nodes.py`  
**Cost:** ~$0.01 for custom metric writes (first 10 metrics/month free)

---

### Priority 6 — Cost Explorer Wire-up (1h) 🔴 Blocked until Sep 3

**AWS service:** Cost Explorer  
**Available:** ~Sep 3, 2026 (24h after enabling)  
**What to build:**
- `GET /api/cost-demo/summary` — calls real `ce.get_cost_and_usage()` for the account
- Show real AWS spend in the Command Center header (e.g., "This month: $8.39")
- Wire into quality scorecard as an additional real data point

---

### Priority 7 — EventBridge as Demo Trigger (2h) 🔴 Not Started

**AWS service:** EventBridge + SQS  
**Goal:** Make Scene 1 fully event-driven — a synthetic Health event fires into EventBridge → `RecoupHealthEventRule` routes it to SQS → backend polls SQS and auto-starts the graph.  
**Video moment:** "In production, this triggers automatically when AWS Health fires. Here I'll put a synthetic event onto EventBridge and you'll see Recoup pick it up within seconds."

**What to build:**
- Script: `scripts/fire_demo_event.py` — puts synthetic EventBridge Health event
- New backend SQS poller: polls `recoup-recovery-events` on startup, auto-triggers workflow when message arrives
- Show in the demo: run the script → switch to Command Center → watch opportunity appear automatically

---

### Priority 9 — Wire `get_cost_anomalies` with Real boto3 (1h) 🔴 Not Started

**Hackathon rules:** [R11] Cost Anomaly Detection, [R12] Cost Optimization Hub  
**Current state:** Both `get_cost_anomalies()` and `list_cost_optimization_recommendations()` in `tools/aws_tools.py` return `{"_stub": True}` with empty arrays. A judge inspecting the codebase will find no real AWS call.

**What to build:**
- Replace `get_cost_anomalies` stub with real `boto3.client("ce").get_anomalies()` call, returning `Impact` and `RootCauses` fields as required by [R11]
- Replace `list_cost_optimization_recommendations` stub with real `boto3.client("cost-optimization-hub").list_recommendations()` call for [R12]
- Both guards: only call live APIs when `settings.recoup_enable_live_aws=True`; fall back to stub otherwise (new account has no anomaly history — empty result is valid)
- Wire a Cost Anomaly Monitor via AWS console (free, 5 min) so the API has something to return

**Files:** `backend/src/recoup/tools/aws_tools.py`

---

### Priority 10 — Verify AgentCore Policy in Enforcement Mode (30 min) 🔴 Not Verified

**Hackathon rule:** [R6] AgentCore Policy — Cedar policies attached in enforcement mode; default deny  
**Current state:** Cedar policies are enforced in Python via `safety/cedar.py`. The AgentCore Gateway is registered (`recoup-tool-gateway-tpnzqdgixc`) and the Cedar policy file exists at `infra/policy/recoup-policy.cedar`, but whether it is **attached to the Gateway in enforcement mode** (not just advisory/logging) has not been verified.

**What to do:**
- Open the AgentCore console or run `aws bedrock-agentcore-control describe-gateway --gateway-id recoup-tool-gateway-tpnzqdgixc`
- Confirm the policy file is attached and mode is `ENFORCING` (not `PERMISSIVE`)
- If not attached: re-run `scripts/register_agentcore.py` with policy attachment, or attach manually via console
- Document the enforcement mode confirmation in this file

---

### Priority 8 — CloudWatch Custom Metrics + Dashboard (1h) 🔴 Not Started

**AWS service:** CloudWatch custom metrics + Dashboards  
**Goal:** Publish real CloudWatch metrics after every scenario run. Create a dashboard visible in the AWS console during Scene 4.

**Metrics to publish (namespace `Recoup`):**
- `OpportunitiesDetected` — count per run
- `CreditsRecoveredUSD` — dollar value
- `HumanApprovalsRequired` — count
- `UnsafeActionsBlocked` — count

**Dashboard:** `Recoup-Demo` — 4 single-value widgets + time series

---

## Relationship to Phase 6e & 6f

This phase focuses on **real AWS service integration** for the existing SLA + EC2 demo paths.

**Phase 6e** (IAM Security Model) changes *how* all AWS calls are made — through `RecoupReadOnlyRole` via STS AssumeRole rather than direct application credentials. Items in this phase that call AWS directly (SNS, SQS, CloudTrail, Cost Explorer) will use the Phase 6e `CustomerConnection` abstraction once 6e is merged.

**Phase 6f** (Demo Workloads Stack) extends coverage from the single EC2 scenario here to all **8 waste scenarios**: oversized-ec2, unattached-ebs, gp2-migration, idle-eip, idle-rds, s3-no-lifecycle, oversized-lambda, stale-snapshot. If you are implementing the Account Scanner demo flow, implement 6e and 6f first.

---

## AWS Services Coverage After All Items Complete

| AWS Service | Scene | Status |
|---|---|---|
| S3 (`recoup-evidence`) | 1 — evidence writes | ✅ Done |
| DynamoDB (`recoup-approvals`) | 2 — approval persistence | ✅ Done |
| CloudWatch Logs (`/recoup/runtime`) | 2 — audit trail | ✅ Done |
| S3 (`recoup-eval-fixtures`) | 4 — scorecard persistence | ✅ Done |
| CloudWatch (`GetMetricStatistics`) | 3 — EC2 CPU check | ✅ Done (Phase 6) |
| CloudTrail (`LookupEvents`) | 3 — ownership check | ✅ Done (Phase 6) |
| EC2 (`StopInstances`) | 3 — live action | ✅ Done (Phase 6) |
| KMS (evidence encryption) | 1 — S3 KMS writes | ✅ Done |
| SNS (`recoup-alerts`) | 1 + 3 — notifications | 🔴 Priority 1 |
| SQS (`recoup-recovery-events`) | 1 — event publishing | 🔴 Priority 2 |
| CloudTrail (standalone scenario) | new card | 🔴 Priority 3 |
| ResourceGroupsTaggingAPI | new card | 🔴 Priority 4 |
| CloudWatch custom metrics (inject) | 1 — SLA data-driven | 🔴 Priority 5 |
| Cost Explorer | header + quality | 🔴 Priority 6 (Sep 3) |
| EventBridge (as trigger) | 1 — auto-trigger | 🔴 Priority 7 |
| CloudWatch custom metrics (publish) | 4 — dashboard | 🔴 Priority 8 |
| Bedrock AgentCore (console show) | architecture scene | ✅ Already registered |

**Target: 17 real AWS services touched in the demo flow.**

---

## Video Scene Map — Updated

| Scene | What you show | Real AWS services |
|---|---|---|
| Scene 1 — SLA Replay | Trigger replay → real credit ($0.35 from actual AWS billing) → evidence in S3 → SNS email arrives → SQS message in console → CW metric chart shows dip | S3, KMS, SNS, SQS, CloudWatch, DynamoDB |
| Scene 2 — HITL Approval | Decision Inbox → approve → DynamoDB record live → CloudWatch Logs audit entry | DynamoDB, CloudWatch Logs |
| Scene 3 — EC2 Stop | Live CPU check → LIVE AWS ACTION → stop → SNS confirmation email | CloudWatch, CloudTrail, EC2, SNS |
| Scene 4 — Quality Dashboard | All gates green → scorecard in S3 → CloudWatch dashboard | S3, CloudWatch metrics |
| Scene 5 — Architecture | Show AgentCore console → EventBridge rule → SQS queue in console | AgentCore, EventBridge, SQS |

---

## Definition of Done

| Check | Criteria |
|---|---|
| SNS notifications | Real email received in inbox during test run |
| SQS publish | Message visible in SQS console after each scenario |
| CloudTrail scenario | Live `LookupEvents` call, real results, new UI card |
| Tags scenario | Live `get_resources()` call, real untagged ARNs, new UI card |
| CW metric injection | Chart visible in CloudWatch console showing the Aug 1 dip |
| Cost Explorer | Real spend figure shown in UI |
| EventBridge trigger | Synthetic event → auto opportunity in < 10s |
| CW dashboard | `Recoup-Demo` dashboard visible in AWS console |
