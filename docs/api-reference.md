# Recoup — API Reference

**Framework:** FastAPI 0.1.0  
**Last updated:** Sep 13, 2026  
**Base URL (production):** `https://vxndciwupy.us-east-1.awsapprunner.com`  
**Base URL (local):** `http://localhost:8000` (Docker / Playwright default; **8010** if using native `.env.example`)  
**Interactive docs:** `GET /docs` (Swagger UI) · `GET /redoc` (ReDoc) — e.g. `https://vxndciwupy.us-east-1.awsapprunner.com/docs`  
**Run locally:** `cd backend && uvicorn recoup.api.main:app --reload --port 8000`  
**Playwright tests:** J-FULL–focused suite (see `USER_JOURNEY_CHECKLIST.md`).

---

## J-FULL operator API (primary — use these)

| Step | Method | Path |
|------|--------|------|
| Reset (dev/test) | POST | `/api/test/reset` · `/api/admin/reset?clear_scan_cache=true` |
| Scan | POST | `/api/scan/demo` · `/api/scan/full` · `/api/scan/preview` |
| Promote | POST | `/api/scan/findings/promote` |
| List / detail | GET | `/api/opportunities` · `/api/opportunities/{id}` |
| HITL | POST | `/api/approvals/opportunity/{id}/approve` · `…/investigate` · `…/decline` |
| Ledger | GET | `/api/approvals/outcomes` · `/api/scan/findings/promoted` |
| Quality | GET | `/api/quality/scorecard` |
| Optional agent | POST | `/api/opportunities/{id}/run` · GET `…/trace` · GET `…/stream` |

Canonical walkthrough: [operator-journey.md](operator-journey.md).

---

## Removed HTTP routes (Sep 2026 — J-FULL cleanup)

These endpoints were **removed** from the public API. SLA replay math remains in `backend/src/recoup/adapters/replay.py` for **unit tests** and the quality scorecard engine only.

| Former prefix | Was used for |
|---------------|--------------|
| `/api/replay/*` | SLA verified replay trigger |
| `/api/ec2-demo/*` | Live EC2 stop demo |
| `/api/cloudtrail-demo/*` | Governance S7 |
| `/api/tagging-demo/*` | Governance S8 |
| `/api/cost-demo/*` | Governance S9 |

Sections below that document removed routes are **archived reference** only.

---

## Authentication (Sprint 4)

When `RECOUP_API_KEY` is set, all non-public endpoints require one of:

```
X-API-Key: <your-api-key>
Authorization: Bearer <your-api-key>
```

**Public paths** (no auth required): `/health`, `/health/ready`, `/docs`, `/redoc`, `/openapi.json`, `/api/config`

In `RECOUP_ENV=local` mode the auth check is skipped for development convenience.

**Response `401`** when key is missing or wrong:
```json
{ "error": "Unauthorized — X-API-Key or Authorization: Bearer required." }
```

---

## Meta Endpoints

### `GET /health`

Liveness probe. Used by load balancers and health monitors.

**Response `200`:**
```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

---

### `GET /health/ready`

Readiness probe — checks configured dependencies (e.g. DynamoDB when `RECOUP_APPROVALS_TABLE` is set).

**Response `200`:**
```json
{
  "status": "ready",
  "ready": true,
  "checks": {
    "dynamodb": "ok"
  }
}
```

When a check fails, `status` is `"degraded"` and `ready` is `false`.

---

### `GET /api/config`

Returns non-secret configuration values for the frontend feature-flag panel.

**Response `200`:**
```json
{
  "real_submission_enabled": false,
  "llm_provider": "bedrock",
  "bedrock_model": "us.amazon.nova-pro-v1:0",
  "bedrock_region": "us-east-1",
  "openai_model_id": "",
  "evidence_bucket_configured": true,
  "sns_notifications_enabled": false,
  "sqs_events_enabled": false
}
```

| Field | Type | Description |
|-------|------|-------------|
| `real_submission_enabled` | bool | `RECOUP_ENABLE_REAL_SUPPORT_SUBMISSION` |
| `llm_provider` | string | `"bedrock"` or `"openai"` |
| `bedrock_model` | string | Bedrock model ID |
| `bedrock_region` | string | AWS region for Bedrock/AgentCore |
| `openai_model_id` | string | Set when `llm_provider=openai` (API key never exposed) |
| `evidence_bucket_configured` | bool | S3 evidence bucket configured |
| `sns_notifications_enabled` | bool | SNS topic ARN configured |
| `sqs_events_enabled` | bool | Recovery events queue configured |

---

## Opportunities

### `GET /api/opportunities`

List all tracked recovery opportunities.

**Response `200`:** `array` of opportunity summaries

```json
[
  {
    "id": "opp-replay-apigateway-2026-08-sla-001",
    "state": "MONITORING",
    "state_version": 4,
    "potential_value": "0.35",
    "confidence": 0.92,
    "service": "apigateway",
    "region": "us-east-1",
    "discovery_confidence": 82,
    "action_confidence": 76,
    "risk_level": "LOW",
    "evidence_sufficiency": "SUFFICIENT",
    "priority_score": 71,
    "recommended_action": "Resize or stop idle instance"
  }
]
```

Scan-promoted opportunities include optional **`discovery_confidence`**, **`action_confidence`**, **`risk_level`**, **`evidence_sufficiency`**, **`priority_score`**, **`recommended_action`** when `recovery_assessment` is on the graph state.

---

### `GET /api/opportunities/{opportunity_id}`

Get a single opportunity by ID.

**Path parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `opportunity_id` | string | ✅ | Opportunity identifier |

**Response `200`:**
```json
{
  "id": "opp-replay-001",
  "state": "MONITORING",
  "state_version": 4,
  "potential_value": "0.35",
  "confidence": 0.92,
  "service": "apigateway",
  "region": "us-east-1"
}
```

**Response `404`:**
```json
{"detail": "Opportunity 'opp-xyz' not found"}
```

---

### `POST /api/opportunities/{opportunity_id}/run`

Trigger a full agent graph run for a given opportunity ID.

**Path parameters:**

| Parameter | Type | Required |
|-----------|------|----------|
| `opportunity_id` | string | ✅ |

**Request body:**
```json
{
  "signal": null
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `signal` | object \| null | `null` | `IncidentSignal` dict. If null, the canonical replay signal is used |

**Signal object (when provided):**
```json
{
  "source": "aws_health",
  "event_id": "my-event-001",
  "service": "apigateway",
  "region": "us-east-1",
  "start": "2026-08-01T02:00:00Z",
  "end": "2026-08-01T02:30:00Z",
  "affected_resource_ids": ["arn:aws:apigateway:us-east-1::/restapis/abc123"],
  "raw_ref": "s3://recoup-eval-fixtures/my-event.json",
  "replay": false
}
```

**Response `200`:**
```json
{
  "opportunity_id": "opp-test-001",
  "final_state": "MONITORING",
  "potential_credit": "0.35",
  "case_id": "replay-a3f9c12b4d01",
  "errors": []
}
```

| Field | Description |
|-------|-------------|
| `final_state` | The `OpportunityState` after graph execution |
| `potential_credit` | Credit amount in USD (string to preserve Decimal precision) |
| `case_id` | Simulated or real AWS Support case ID |
| `errors` | List of non-fatal error messages accumulated during execution |

---

### `GET /api/opportunities/{opportunity_id}/trace`

Return the complete agent trace for an opportunity.

**Response `200`:**
```json
{
  "opportunity_id": "opp-replay-001",
  "signal": {
    "source": "replay",
    "event_id": "replay-apigateway-2026-08-sla-001",
    "service": "apigateway",
    "region": "us-east-1",
    "start": "2026-08-01T02:00:00+00:00",
    "end": "2026-08-01T02:30:00+00:00",
    "affected_resource_ids": ["arn:aws:apigateway:us-east-1::/restapis/demo0001"],
    "raw_ref": "s3://recoup-eval-fixtures/replay/apigateway-2026-08-sla-001.json",
    "replay": true
  },
  "hypothesis_summary": "Detected 6 unavailable 5-minute intervals...",
  "contract": {
    "service": "apigateway",
    "version": "2022-05-05"
  },
  "availability_result": {
    "monthly_uptime_pct": "99.930556",
    "threshold_breached": true,
    "tier_pct": "10",
    "billed_charges": "3.51",
    "potential_credit": "0.35",
    "calculation_trace": [
      "Total 5-minute intervals in billing month: 8,640",
      "Unavailable intervals (availability < 100%): 6",
      "Formula: (8,640 − 6) ÷ 8,640 × 100",
      "Monthly uptime %: 99.930556%",
      "SLA commitment: 99.95%",
      "Threshold breached: YES (99.930556% < 99.95%)",
      "Credit tier: 10%",
      "Billed charges in affected billing cycle: $3.51",
      "Potential credit: $3.51 × 10% = $0.35"
    ]
  },
  "eligibility": {
    "eligible_estimate": true,
    "confidence": 0.92,
    "satisfied_requirements": ["api_id", "region", "billing_cycle", "request_logs", "error_logs", "billing_record"],
    "unresolved": [],
    "possible_exclusions": [],
    "evidence_refs": ["ev-a3f92c1d", "ev-b8e14c2a", "ev-cc92d3f1"]
  },
  "policy_decision": "REQUIRE_APPROVAL",
  "case_id": "replay-a3f9c12b4d01",
  "case_outcome": {
    "case_id": "replay-a3f9c12b4d01",
    "status": "PENDING",
    "credit_amount": "0.00",
    "notes": "Case submitted. Awaiting AWS Support response (stub)."
  },
  "errors": [],
  "recovery_assessment": {
    "pipeline_phase": "UNDERSTAND",
    "evidence_sufficiency": { "level": "SUFFICIENT", "summary": "…" },
    "discovery_confidence": { "score": 82, "label": "High" },
    "recommendation": { "primary_action_label": "…", "primary_action_id": "…" },
    "recovery_plan": { "steps": [] },
    "safety_checks": [],
    "evidence_graph": { "nodes": [], "edges": [] }
  },
  "workflow": {
    "workflow_state": "AWAITING_APPROVAL",
    "pipeline_stage": 8,
    "execution_status": ""
  }
}
```

For **scan-promoted** opportunities, `recovery_assessment` is populated at promote; SLA replay fixtures may omit it. **`GET /api/opportunities/{id}/workflow`** returns the same payload as trace (alias for detail UI).

**Response `404`:**
```json
{"detail": "Opportunity 'opp-xyz' not found"}
```

---

## Approvals (HITL)

### `GET /api/approvals/pending`

List all pending HITL approval requests.

**Response `200`:**
```json
[
  {
    "approval_id": "appr-001",
    "principal": "ops-team",
    "action": "Submit $0.35 SLA credit claim to AWS Support",
    "amount": "0.35",
    "claim_hash": "sha256:abcdef...",
    "opportunity_id": "opp-replay-001",
    "state_version": 3,
    "timestamp": "2026-08-15T10:00:00Z",
    "expires_at": "2026-08-16T10:00:00Z",
    "state": "PENDING"
  }
]
```

---

### `POST /api/approvals/{approval_id}/approve`

Approve a pending HITL request. This allows the graph to proceed past `await_human_approval`.

**Request body:**
```json
{
  "principal": "alice@example.com",
  "notes": "Verified availability data — credit is valid."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `principal` | string | ✅ | Identity of the approver |
| `notes` | string | — | Optional justification |

**Response `200`:**
```json
{
  "approval_id": "appr-001",
  "state": "APPROVED"
}
```

**Response `404`:** Approval not found  
**Response `409`:** Approval already in non-PENDING state

---

### `POST /api/approvals/{approval_id}/decline`

Decline a pending HITL request.

**Request body:** Same as approve

**Response `200`:**
```json
{
  "approval_id": "appr-001",
  "state": "DECLINED"
}
```

---

### Opportunity-scoped HITL (primary UI: `/opportunities/{id}`)

These routes drive the frontend approve flow on `/opportunities/[id]`. They validate **claim_hash**, **amount**, and **state_version** on approve.

### `GET /api/approvals/opportunity/{opportunity_id}`

Return the pending `ApprovalRecord` for an opportunity, or `null` if none.

### `POST /api/approvals/opportunity/{opportunity_id}/approve`

**Request body:**
```json
{
  "principal": "alice@example.com",
  "claim_hash": "sha256:abcdef...",
  "amount": "0.35",
  "state_version": 3,
  "notes": "Verified SLA math."
}
```

**Response `200`:** Full `ApprovalRecord` JSON plus `_aws`, `sns_notification_sent`. Opportunity state → `APPROVED` (and often `RECOVERED` for non-EC2 actions).

**Response `404`:** No pending approval  
**Response `409`:** Hash, amount, or state_version mismatch / expired; or recovery gates — evidence sufficiency **INSUFFICIENT**, blocking **safety check FAIL**, or **projected recovery amount** ≠ pending `amount`

### `POST /api/approvals/opportunity/{opportunity_id}/decline`

**Request body:** `{ "principal", "notes?" }` — marks approval `DECLINED`.

### `POST /api/approvals/opportunity/{opportunity_id}/investigate`

**Request body:** `{ "principal", "notes?" }` — approval `DECLINED` with investigate prefix; opportunity → `NEEDS_FOLLOWUP`.

### `GET /api/approvals/outcomes`

List recovery outcome records for the Recovery Ledger audit trail.

### `POST /api/approvals/purge-stale`

Remove expired pending approvals (admin/demo).

---

## Opportunities (streaming)

### `GET /api/opportunities/{opportunity_id}/stream`

Server-Sent Events (`text/event-stream`). Each message is JSON with a **`type`** field:

| `type` | Payload |
|--------|---------|
| `node_started` | `{ "type", "node", "timestamp"? }` |
| `node_completed` | `{ "type", "node", "duration_ms", ... }` |
| `approval_required` | `{ "type", "opportunity_id", ... }` |
| `opportunity_done` | `{ "type", "state", ... }` |
| `error` | `{ "type", "message" }` |

Example:
```
data: {"type": "node_started", "node": "normalize_event"}
data: {"type": "node_completed", "node": "risk_policy_gate", "duration_ms": 12, "policy_decision": "REQUIRE_APPROVAL"}
```

---

## Replay (archived — HTTP removed Sep 2026)

> **Not mounted.** Public `/api/replay/*` routes were removed in the J-FULL cleanup. SLA replay logic remains in `backend/src/recoup/adapters/replay.py` for **unit/e2e pytest** and the quality scorecard. Use `POST /api/opportunities/{id}/run` only when exercising the agent graph on an existing opportunity — not as a replacement for the old replay trigger.

The following documents the **former** contract for historical reference.

### `POST /api/replay/api-gateway-sla` _(removed)_

Trigger the canonical API Gateway SLA replay. Always produces exactly **$0.35**. Writes real evidence to S3 (`recoup-evidence` bucket, KMS-encrypted) when live AWS is enabled.

**Request body:** _(empty — no body required)_

**Response `200`:**
```json
{
  "opportunity_id": "opp-replay-apigateway-2026-08-sla-001",
  "scenario_id": "replay-apigateway-2026-08-sla-001",
  "monthly_uptime_pct": "99.930556",
  "threshold_breached": true,
  "tier_pct": "10",
  "billed_charges": "3.51",
  "potential_credit": "0.35",
  "calculation_trace": ["..."],
  "case_id": "replay-a3f9c12b4d01",
  "policy_decision": "REQUIRE_APPROVAL",
  "eligible": true,
  "credit_amount": "0.35",
  "sse_url": "/api/opportunities/opp-replay-apigateway-2026-08-sla-001/stream",
  "live_evidence": {},
  "evidence_bucket": "recoup-evidence-...",
  "evidence_s3_uris": ["s3://recoup-evidence-.../..."],
  "errors": []
}
```

Optional query: `?opportunity_id=` to reuse an existing opportunity ID.

The `evidence_s3_uris` array is populated when live AWS resources (S3 bucket, KMS key) are configured. `case_id` typically uses a `replay-` prefix from the submission adapter.

---

### `POST /api/replay/run`

Execute a Verified Replay by scenario ID. The canonical scenario always produces exactly **$0.35**.

**Request body:**
```json
{
  "scenario_id": "replay-apigateway-2026-08-sla-001",
  "opportunity_id": null
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `scenario_id` | string | canonical | Which scenario to run |
| `opportunity_id` | string \| null | auto-generated | Override the opportunity ID |

**Response `200`:**
```json
{
  "opportunity_id": "opp-replay-apigateway-2026-08-sla-001",
  "scenario_id": "replay-apigateway-2026-08-sla-001",
  "monthly_uptime_pct": "99.930556",
  "threshold_breached": true,
  "tier_pct": "10",
  "billed_charges": "3.51",
  "potential_credit": "0.35",
  "calculation_trace": [
    "Total 5-minute intervals in billing month: 8,640",
    "Unavailable intervals (availability < 100%): 6",
    "..."
  ],
  "case_id": "replay-a3f9c12b4d01",
  "errors": []
}
```

The `potential_credit` field is always `"0.35"` for the canonical scenario.

---

### `GET /api/replay/scenarios`

List all available replay scenarios.

**Response `200`:**
```json
[
  {
    "scenario_id": "replay-apigateway-2026-08-sla-001",
    "name": "API Gateway 10% SLA Credit — August 2026",
    "description": "6 unavailable 5-minute intervals in a 31-day month (8,640 total). Monthly uptime: 99.9306%. 10% credit tier. $3.51 billed charges → $0.35 potential credit.",
    "expected_credit_usd": "0.35",
    "tags": ["golden", "apigateway", "sla_10pct"]
  }
]
```

---

## Admin / test reset

### `POST /api/admin/reset`

Query: `clear_scan_cache=true|false`. Full reset of in-memory demo state (and DynamoDB approvals/outcomes when configured). **403** in production.

### `GET` / `POST /api/test/reset`

Playwright isolation reset. **403** in production.

---

## Error Format

Most client errors use FastAPI's `detail` field:

```json
{ "detail": "Human-readable error message" }
```

Unhandled **500** responses use:

```json
{
  "error": "An internal error occurred.",
  "request_id": "uuid"
}
```

| HTTP Status | Meaning |
|-------------|---------|
| `200` | Success |
| `404` | Resource not found |
| `409` | Conflict (e.g. approval already decided) |
| `422` | Validation error (invalid request body) |
| `500` | Internal server error |

---

## EC2 Demo (Phase 6)

Routes for the live AWS action demo: idle EC2 detection → HITL approval → real `StopInstances`.

### `POST /api/ec2-demo/trigger`

Start the EC2 demo workflow. Runs CloudWatch CPU check + CloudTrail ownership check, creates an OPTIMIZATION opportunity, and raises a HITL approval request with the **LIVE AWS ACTION** badge.

**Request body:**
```json
{
  "instance_id": ""
}
```

| Field | Default | Description |
|-------|---------|-------------|
| `instance_id` | First entry in `RECOUP_DEMO_INSTANCE_ALLOWLIST` | EC2 instance to evaluate. If blank, defaults to first allowlisted instance. |

**Response `200`:** Full opportunity dict including `approval_id`, `cw_cpu_pct`, `ct_verdict`, `monthly_waste_usd`.

---

### `GET /api/ec2-demo/opportunities`

List all EC2 demo opportunities (OPTIMIZATION type).

**Response `200`:** Array of opportunity dicts.

---

### `GET /api/ec2-demo/opportunity/{opportunity_id}`

Get a single EC2 demo opportunity by ID.

**Response `200`:** Full opportunity dict. **Response `404`:** Not found.

---

### `POST /api/ec2-demo/execute/{opportunity_id}`

Execute the approved `stop_demo_instance` action. Requires a valid `ApprovalRecord` in DynamoDB for the opportunity.

**Response `200`:**
```json
{
  "opportunity_id": "opp-ec2-demo-...",
  "instance_id": "i-0abc123...",
  "previous_state": "running",
  "current_state": "stopped",
  "stopped_at": "2026-09-02T10:00:00Z",
  "simulated": false
}
```

**Response `400`:** No valid approval found, or safety guard failed (allowlist, tag check, etc.).

---

## Demo Scenarios (Phase 6b)

Live-data demo endpoints used by governance flows and tests. Each endpoint attempts a real AWS call; on failure it falls back to a deterministic fixture. The `_aws.live` field indicates whether real data was returned.

---

### `GET /api/cloudtrail-demo/check`

CloudTrail attribution check — was any recent activity on the demo EC2 instance caused by a human actor?

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `instance_id` | string | `i-0d3389d7f950f7d3f` | EC2 instance to analyse |
| `hours` | int | `24` | Look-back window |

**Response `200`:**
```json
{
  "instance_id": "i-0d3389d7f950f7d3f",
  "window_hours": 24,
  "simulated": true,
  "data_source": "simulation",
  "checked_at": "2026-09-02T10:00:00+00:00",
  "total_events": 4,
  "actor_attributed": false,
  "human_events": 0,
  "actor_type_breakdown": {"AssumedRole": 3, "Root": 1},
  "requires_human_review": true,
  "finding": "No human actor found in CloudTrail events — all activity is automated (AssumedRole / AWSService). Cost anomalies in this period cannot be attributed to a specific user. Human review required.",
  "events": [...],
  "_aws": {
    "service": "CloudTrail",
    "api": "LookupEvents",
    "live": false
  }
}
```

Always attempts `cloudtrail:LookupEvents` filtered by `ResourceName=<instance_id>`; falls back to fixture if the call fails. Check `_aws.live` in the response to confirm real data.

---

### `GET /api/cost-demo/summary`

Real AWS account spend for the current billing month with per-service breakdown.

**Response `200`:**
```json
{
  "fetched_at": "2026-09-02T10:00:00+00:00",
  "simulated": true,
  "data_source": "simulation",
  "total_usd": 8.39,
  "billing_period_start": "2026-09-01",
  "billing_period_end": "2026-09-02",
  "breakdown": [
    {"service": "Amazon EC2", "cost_usd": 3.12},
    {"service": "Amazon CloudWatch", "cost_usd": 1.85},
    {"service": "AWS Key Management Service", "cost_usd": 1.0},
    {"service": "Amazon DynamoDB", "cost_usd": 0.98},
    {"service": "Amazon S3", "cost_usd": 0.88},
    {"service": "Amazon SNS", "cost_usd": 0.56}
  ],
  "_aws": {
    "service": "CostExplorer",
    "api": "GetCostAndUsage",
    "live": false
  }
}
```

Always attempts `ce:GetCostAndUsage` (monthly granularity, grouped by SERVICE); falls back to fixture if Cost Explorer has no data yet. Live data available from Sep 3, 2026 (24h after enabling Cost Explorer).

---

### `GET /api/tagging-demo/scan`

Scan all AWS resources for missing required cost allocation tags (`cost:team`, `environment`).

**Response `200`:**
```json
{
  "scanned_at": "2026-09-02T10:00:00+00:00",
  "simulated": true,
  "data_source": "simulation",
  "required_tags": ["cost:team", "environment"],
  "resources_scanned": 6,
  "resources_missing_tags": 6,
  "estimated_attribution_gap_usd_monthly": 9.04,
  "findings": [
    {
      "arn": "arn:aws:ec2:us-east-1:...:instance/i-0d3389d7f950f7d3f",
      "resource_type": "ec2",
      "present_tags": {"RecoupDemo": "true", "Name": "recoup-demo"},
      "missing_tags": ["cost:team", "environment"],
      "estimated_monthly_cost_usd": 7.59
    }
  ],
  "summary": "6 resources found without required cost allocation tags — estimated attribution gap: $9.04/month",
  "_aws": {
    "service": "ResourceGroupsTaggingAPI",
    "api": "GetResources",
    "live": false
  }
}
```

Always attempts `tagging:GetResources` with `IncludeComplianceDetails=true`; falls back to fixture if the call fails.

---

## Quality / Scorecard (Phase 5)

### `GET /api/quality/scorecard`

Run the live evaluation suite and return a scorecard. Also persists the result to S3 (`recoup-eval-fixtures/scorecards/{timestamp}.json`) when live AWS is enabled.

**Response `200`:** (abbreviated — see live response for full score breakdown strings)

```json
{
  "build": "2026.09.11-1815",
  "run_at": "2026-09-11T18:15:00+00:00",
  "golden_path_success": "5/5",
  "overall_scenario_success": "42/47",
  "evidence_recall": "2/2",
  "tool_selection_accuracy": "10/10",
  "financial_math_correctness": "5/5",
  "unsafe_external_actions": 0,
  "unsupported_claim_rate": "0/1",
  "replay_p50_seconds": 0.021,
  "replay_p95_seconds": 0.023,
  "trace_completeness": "8/8",
  "gates": [
    {"id": "golden_path_success", "pass": true, "value": 5},
    {"id": "financial_math_correctness", "pass": true, "value": 5},
    {"id": "evidence_recall", "pass": true, "value": 2},
    {"id": "tool_selection_accuracy", "pass": true, "value": 10},
    {"id": "trace_completeness", "pass": true, "value": 8},
    {"id": "unsafe_actions", "pass": true, "value": 0}
  ],
  "all_gates_pass": true,
  "scorecard_s3_uri": "s3://...",
  "scorecard_bucket": "recoup-eval-fixtures-..."
}
```

The `scorecard_s3_uri` is populated when the eval fixtures bucket is configured.

---

## Account Scanner (Phase 6e)

Scans an AWS account for cost-saving opportunities across 9 service categories. Uses **STS AssumeRole** — the caller provides a Role ARN + External ID; Recoup calls `sts:AssumeRole` internally and obtains short-lived credentials (1-hour expiry). No long-lived access keys are ever stored, logged, or returned.

---

### `POST /api/scan/demo`

Demo scan (no role required) — returns 8+ tagged findings for the hackathon account. Used by `/scan` UI.

### `GET /api/scan/last`

Last cached demo scan result (in-memory).

### `GET /api/scan/history`

Scan history entries. Optional query: `account_id`.

### `POST /api/scan/full/rate-limited`

Alias of full scan with rate limiting when `slowapi` is installed.

### `POST /api/scan/findings/promote`

Promote a scan finding to a recovery opportunity (`AWAITING_APPROVAL`).

### `GET /api/scan/findings/promoted`

List promoted findings / opportunities from scan flow.

---

### `POST /api/scan/preview`

Fast scan — runs EC2 + Cost Explorer scanners only. Completes in < 10 seconds.

**Request body:**
```json
{
  "role_arn": "arn:aws:iam::625962218034:role/RecoupReadOnlyRole",
  "external_id": "recoup-demo-external-id",
  "region": "us-east-1"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `role_arn` | string | ✅ | ARN of the analysis role to assume via STS (e.g. `RecoupReadOnlyRole`) |
| `external_id` | string | ✅ | External ID matching the trust policy condition |
| `region` | string | ❌ | AWS region to scan (default: `us-east-1`) |

**Response `200`:**
```json
{
  "scanned_at": "2026-09-03T11:00:00Z",
  "account_id": "625962218034",
  "region": "us-east-1",
  "findings": [
    {
      "service": "ec2",
      "resource_id": "i-0d3389d7f950f7d3f",
      "resource_type": "EC2 Instance",
      "issue": "CPU < 1% over 7 days — likely idle",
      "severity": "high",
      "estimated_monthly_savings_usd": 7.59,
      "recommendation": "Stop or downsize instance",
      "region": "us-east-1"
    }
  ],
  "total_estimated_monthly_savings_usd": 7.59,
  "errors": [],
  "scan_duration_seconds": 4.8,
  "assumed_role_arn": "arn:aws:sts::625962218034:assumed-role/RecoupReadOnlyRole/recoup-analysis-session",
  "assumed_role_account_id": "625962218034",
  "session_name": "recoup-analysis-session"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `findings` | array | `Finding` objects sorted by `estimated_monthly_savings_usd` descending |
| `total_estimated_monthly_savings_usd` | float | Sum of all finding savings |
| `errors` | array | Per-scanner errors (insufficient permissions, service not enabled) — non-fatal |
| `scan_duration_seconds` | float | Total scan duration in seconds |
| `assumed_role_arn` | string | Full ARN of the assumed-role session (STS provenance) |
| `assumed_role_account_id` | string | AWS account ID where the role was assumed |
| `session_name` | string | IAM session name used (`recoup-analysis-session`) |

**Error `400`:**
```json
{
  "detail": "Could not assume role 'arn:aws:iam::...': An error occurred (AccessDenied) ..."
}
```
Returned when STS AssumeRole fails — wrong ARN, missing trust policy, or incorrect External ID.

Preview/full responses may also include: `scan_id`, `scan_hash`, `is_cached`, `findings_by_service` (demo paths).

---

### `POST /api/scan/full`

Full scan — runs all 9 scanners in parallel. Completes in 15–30 seconds.

**Request body:** Same as `/api/scan/preview` (`role_arn` + `external_id` + `region`).

**Response `200`:** Same shape as preview, with findings covering all 9 services:

| Scanner | Finding Types |
|---------|--------------|
| `EC2Scanner` | `IDLE_INSTANCE` — CPU < 5% over 7 days |
| `EBSScanner` | `UNATTACHED_VOLUME` — not attached to any instance |
| `EIPScanner` | `IDLE_EIP` — Elastic IP with no association |
| `RDSScanner` | `IDLE_RDS` — CPU < 5%, connections ≈ 0 over 7 days |
| `S3Scanner` | `NO_LIFECYCLE_POLICY` — all objects in STANDARD class |
| `LambdaScanner` | `OVERSIZED_LAMBDA` — < 5 invocations in 30 days |
| `LBScanner` | `IDLE_LOAD_BALANCER` — 0 healthy targets |
| `CWLogsScanner` | `NO_RETENTION_POLICY` — log group set to Never Expire |
| `CostExplorerScanner` | `RIGHT_SIZING` — Cost Explorer recommendation available |

---

### `Finding` Object

| Field | Type | Description |
|-------|------|-------------|
| `service` | string | AWS service (`ec2`, `ebs`, `eip`, `rds`, `s3`, `lambda`, `lb`, `cwlogs`, `cost_explorer`) |
| `finding_type` | string | Finding category (see scanner table above) |
| `resource_id` | string | ARN or ID of the affected resource |
| `severity` | string | `high` / `medium` / `low` (lowercase) |
| `estimated_monthly_savings_usd` | float | Estimated monthly savings if the finding is resolved |
| `evidence` | object | Service-specific evidence fields (populated from Phase 6f) |

---

### `POST /api/scan/connect/init` (Sprint 1)

Generate a per-customer `ExternalId` for the connect wizard. Must be called once per customer before they deploy the CloudFormation role.

**Request body:** (empty)

**Response `200`:**
```json
{
  "customer_id": "a3f2e1d0-...",
  "external_id": "Xk3mP9...randombase64...",
  "cf_template_hint": "...Condition: {StringEquals: {sts:ExternalId: \"Xk3mP9...\"}} ... Sid: DenyAllWrites ..."
}
```

| Field | Description |
|-------|-------------|
| `customer_id` | UUID to reference this customer's connection |
| `external_id` | 256-bit `secrets.token_urlsafe(32)` — unique per customer, never reused |
| `cf_template_hint` | Snippet showing the trust policy condition and DenyAllWrites block to paste into CloudFormation |

---

### `GET /api/scan/connect/{customer_id}` (Sprint 1)

Retrieve a previously generated connection record.

**Response `200`:** `{ customer_id, external_id, created_at, cf_template_hint }`  
**Response `404`:** customer_id not found

---

### `GET /api/scan/audit` (Sprint 2)

Return the scan audit log for the current session. Each entry is masked — no raw account IDs or ARNs.

**Response `200`:**
```json
[
  {
    "scan_id": "scan-a1b2c3d4",
    "account_id_masked": "1234XXXXXXXX9012",
    "scanned_at": "2026-09-08T12:34:56Z",
    "scanners": ["EC2Scanner", "EBSScanner"],
    "region": "us-east-1",
    "total_savings_usd": 87.82,
    "duration_s": 4.2,
    "finding_count": 8
  }
]
```

---

### `DELETE /api/scan/accounts/{account_id}/data` (Sprint 2)

Purge all scan cache, promoted findings, and audit log entries for a customer account. Use `__demo__` for the demo account.

**Response `200`:**
```json
{
  "status": "deleted",
  "account_id_prefix": "XXXX",
  "purged_audit_records": "3"
}
```

---

## CORS

In `RECOUP_ENV=local`, CORS allows `*` for development convenience. In production, only `settings.frontend_url` is allowed. Configure via `FRONTEND_URL` env var.

---

## Running the API

```bash
# Development
cd backend
pip install -e ".[dev]"
uvicorn recoup.api.main:app --reload --port 8000

# Visit Swagger UI
open http://localhost:8000/docs

# J-FULL smoke (demo scan)
curl -s -X POST http://localhost:8000/api/scan/demo | jq '.findings | length'

# Optional: quality scorecard (includes replay P95 from pytest adapter)
curl -s http://localhost:8000/api/quality/scorecard | jq '.all_gates_pass'

# Golden SLA replay (no HTTP) — from backend/
pytest tests/e2e/test_golden_replay.py -q
```
