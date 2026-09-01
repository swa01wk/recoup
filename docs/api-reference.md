# Recoup — API Reference

**Framework:** FastAPI 0.1.0  
**Base URL (local):** `http://localhost:8000`  
**Base URL (production):** TBD (Phase 4)  
**Interactive docs:** `GET /docs` (Swagger UI) · `GET /redoc` (ReDoc)  
**Run locally:** `cd backend && uvicorn recoup.api.main:app --reload --port 8000`

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

### `GET /api/config`

Returns non-secret configuration values for the frontend feature-flag panel.

**Response `200`:**
```json
{
  "simulation_mode": true,
  "live_aws_enabled": false,
  "real_submission_enabled": false,
  "bedrock_model": "claude-3-5-sonnet-20241022",
  "bedrock_region": "us-east-1"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `simulation_mode` | bool | Always `true` in Phase 1 |
| `live_aws_enabled` | bool | Whether live AWS data fetching is enabled |
| `real_submission_enabled` | bool | Whether real AWS Support submission is enabled |
| `bedrock_model` | string | Bedrock model ID in use |
| `bedrock_region` | string | AWS region for Bedrock/AgentCore |

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
    "simulation_mode": true,
    "potential_value": "1840.00",
    "confidence": 0.92,
    "service": "apigateway",
    "region": "us-east-1"
  }
]
```

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
  "simulation_mode": true,
  "potential_value": "1840.00",
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
  "signal": null,
  "simulation_mode": true
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `signal` | object \| null | `null` | `IncidentSignal` dict. If null, the canonical replay signal is used |
| `simulation_mode` | bool | `true` | Always `true` in Phase 1 |

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
  "potential_credit": "1840.00",
  "case_id": "sim-a3f9c12b4d01",
  "errors": [],
  "simulation_mode": true
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
    "billed_charges": "18400.00",
    "potential_credit": "1840.00",
    "calculation_trace": [
      "Total 5-minute intervals in billing month: 8,640",
      "Unavailable intervals (availability < 100%): 6",
      "Formula: (8,640 − 6) ÷ 8,640 × 100",
      "Monthly uptime %: 99.930556%",
      "SLA commitment: 99.95%",
      "Threshold breached: YES (99.930556% < 99.95%)",
      "Credit tier: 10%",
      "Billed charges in affected billing cycle: $18,400",
      "Potential credit: $18,400 × 10% = $1,840"
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
  "case_id": "sim-a3f9c12b4d01",
  "case_outcome": {
    "case_id": "sim-a3f9c12b4d01",
    "status": "PENDING",
    "credit_amount": "0.00",
    "notes": "Case submitted. Awaiting AWS Support response (stub)."
  },
  "errors": []
}
```

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
    "action": "Submit $1,840.00 SLA credit claim to AWS Support",
    "amount": "1840.00",
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

## Replay

### `POST /api/replay/run`

Execute a Verified Replay. The canonical scenario always produces exactly **$1,840.00**.

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
  "simulation_mode": true,
  "monthly_uptime_pct": "99.930556",
  "threshold_breached": true,
  "tier_pct": "10",
  "billed_charges": "18400.00",
  "potential_credit": "1840.00",
  "calculation_trace": [
    "Total 5-minute intervals in billing month: 8,640",
    "Unavailable intervals (availability < 100%): 6",
    "..."
  ],
  "case_id": "sim-a3f9c12b4d01",
  "errors": []
}
```

The `potential_credit` field is always `"1840.00"` for the canonical scenario.

---

### `GET /api/replay/scenarios`

List all available replay scenarios.

**Response `200`:**
```json
[
  {
    "scenario_id": "replay-apigateway-2026-08-sla-001",
    "name": "API Gateway 10% SLA Credit — August 2026",
    "description": "6 unavailable 5-minute intervals in a 31-day month (8,640 total). Monthly uptime: 99.9306%. 10% credit tier. $18,400 billed charges → $1,840.00 potential credit.",
    "expected_credit_usd": "1840.00",
    "tags": ["golden", "apigateway", "sla_10pct"]
  }
]
```

---

## Error Format

All errors follow FastAPI's standard detail format:

```json
{
  "detail": "Human-readable error message"
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

## CORS

In Phase 1, CORS is configured with `allow_origins=["*"]`. Phase 4 restricts this to the frontend origin.

---

## Running the API

```bash
# Development
cd backend
pip install -e ".[dev]"
uvicorn recoup.api.main:app --reload --port 8000

# Visit Swagger UI
open http://localhost:8000/docs

# Run canonical replay
curl -X POST http://localhost:8000/api/replay/run \
  -H "Content-Type: application/json" \
  -d '{"scenario_id": "replay-apigateway-2026-08-sla-001"}'
```
