# Recoup — Verified Replay System

**Files:**  
- Adapter: `backend/src/recoup/adapters/replay.py`  
- API Route: `backend/src/recoup/api/routes/replay.py`  
- Fixtures dir: `eval_fixtures/sla/api_gateway/canonical/`  
**Last updated:** Sep 11, 2026  
**Playwright tests:** `journey-sla-replay-full.spec.ts` (10 tests), `sla-replay.spec.ts` (4 tests) — see Journey J4 in `USER_JOURNEY_CHECKLIST.md`.  
**Status:** Phase 2 complete — real SLA scenario deterministic across 20/20 consecutive runs; P95 = 23 ms

---

## What is a Verified Replay?

A Verified Replay is a **seedable, deterministic execution** of the full Recoup agent graph using a pre-recorded synthetic incident. It:

1. Loads a canonical event payload from `eval_fixtures/` (no live AWS incident required)
2. Gates real AWS Support submission via `recoup_enable_real_support_submission=False` (default)
3. Runs the complete 11-node graph
4. Produces the same numerical result — **$0.35** — on every run
5. Finishes in P95 ≤ 60 seconds

The replay is the **primary judge demo path**. No live AWS incident needed — all AgentNode stubs are deterministic. Bedrock is bypassed (`use_strands=False`).

---

## Why Replay-First?

| Problem | Replay Solution |
|---------|----------------|
| Live AWS incidents are unpredictable | Replay is seeded from immutable `eval_fixtures/` |
| Real credit claims have consequences | `recoup_enable_real_support_submission=False` (default) prevents real submissions |
| Evaluation reproducibility | Same input → same `case_id`, always |
| Demo during judging | No AWS credentials required for the judge to verify |
| CI golden test | `pytest` verifies `potential_credit == Decimal("0.35")` on every run |

---

## Canonical Scenario

**Scenario ID:** `replay-apigateway-2026-08-sla-001`  
**Name:** API Gateway 10% SLA Credit — August 2026

```python
CANONICAL_SCENARIO = ReplayScenario(
    scenario_id="replay-apigateway-2026-08-sla-001",
    name="API Gateway 10% SLA Credit — August 2026",
    description=(
        "6 unavailable 5-minute intervals in a 31-day month "
        "(8,640 total). Monthly uptime: 99.9306%. 10% credit tier. "
        "$3.51 billed charges → $0.35 potential credit."
    ),
    event=_CANONICAL_EVENT,
    expected_credit_usd=Decimal("0.35"),
    expected_uptime_pct=Decimal("99.930556"),
    tags=["golden", "apigateway", "sla_10pct"],
)
```

### Canonical Event Payload

```json
{
  "source": "replay",
  "event_id": "replay-apigateway-2026-08-sla-001",
  "service": "apigateway",
  "region": "us-east-1",
  "start": "2026-08-01T02:00:00Z",
  "end": "2026-08-01T02:30:00Z",
  "affected_resource_ids": ["arn:aws:apigateway:us-east-1::/restapis/demo0001"],
  "raw_ref": "s3://recoup-eval-fixtures/replay/apigateway-2026-08-sla-001.json",
  "replay": true
}
```

---

## ReplayScenario Model

```python
class ReplayScenario(BaseModel):
    scenario_id: str
    name: str
    description: str
    event: dict[str, Any]           # raw event dict → parsed to IncidentSignal
    expected_credit_usd: Decimal    # asserted in golden tests
    expected_uptime_pct: Decimal    # asserted in golden tests
    tags: list[str]
```

---

## ReplayAdapter

```python
class ReplayAdapter:
    def __init__(self, fixtures_dir: Path | None = None) -> None:
        ...

    def build_state(
        self,
        scenario: ReplayScenario | None = None,
        *,
        opportunity_id: str | None = None,
    ) -> GraphState:
        ...

    def load_scenario_from_file(self, filename: str) -> ReplayScenario:
        ...
```

### `build_state()` Behavior

1. Defaults to `CANONICAL_SCENARIO` if no scenario provided
2. Generates `opportunity_id` as `f"opp-{scenario.scenario_id}"` unless overridden
3. Parses the event dict into a typed `IncidentSignal`
4. Runs with real-submission gated off (default)
5. Generates a deterministic `idempotency_key`:
   ```python
   "replay:" + sha256(scenario_id.encode()).hexdigest()[:16]
   ```
6. Returns a fully-populated `GraphState` ready to pass to `recoup_graph.run()`

---

## Running a Replay

### Via Python

```python
from recoup.adapters.replay import ReplayAdapter, CANONICAL_SCENARIO
from recoup.graph.recoup_graph import recoup_graph
from decimal import Decimal

adapter = ReplayAdapter()
state = adapter.build_state(CANONICAL_SCENARIO)
final_state = recoup_graph.run(state)

assert final_state.availability_result.potential_credit == Decimal("0.35")
assert final_state.case_id is not None
```

### Via API

```bash
# Run the canonical replay
curl -X POST http://localhost:8000/api/replay/run \
  -H "Content-Type: application/json" \
  -d '{"scenario_id": "replay-apigateway-2026-08-sla-001"}'
```

**Expected response:**
```json
{
  "opportunity_id": "opp-replay-apigateway-2026-08-sla-001",
  "scenario_id": "replay-apigateway-2026-08-sla-001",
  "monthly_uptime_pct": "99.930556",
  "threshold_breached": true,
  "tier_pct": "10",
  "billed_charges": "3.51",
  "potential_credit": "0.35",
  "case_id": "replay-a3f9c12b4d01",
  "errors": []
}
```

### Via Curl (full graph + trace)

```bash
# Run via opportunities endpoint (also returns a trace)
OPPORTUNITY_ID="opp-$(date +%s)"

curl -X POST http://localhost:8000/api/opportunities/$OPPORTUNITY_ID/run \
  -H "Content-Type: application/json" \
  -d '{}'

curl http://localhost:8000/api/opportunities/$OPPORTUNITY_ID/trace
```

---

## Determinism Guarantees

| Component | How determinism is ensured |
|-----------|---------------------------|
| `IncidentSignal` | Fixed event payload from `_CANONICAL_EVENT` constant |
| `IncidentHypothesis` | Stub always produces 6 bad intervals in 8,640 |
| `SLAContract` | Loaded from fixed YAML file (`2022-05-05.yaml`) |
| `AvailabilityResult` | Pure Decimal math — no float, no randomness |
| `EvidenceManifest` | Evidence IDs derived from SHA-256 of `{opportunity_id}:{field_name}` |
| `ClaimPackage` | Body assembled from deterministic inputs |
| `case_id` | **`submission_adapter` node:** `"replay-" + sha256(…)[:12]`. **`simulate_support_case` tool** (if invoked directly): `"sim-" + sha256(calculator_result_hash)[:12]`. Canonical replay API uses the graph path → `replay-` prefix. |
| `idempotency_key` | `"replay:" + sha256(scenario_id)[:16]` — fixed per scenario |

---

## `eval_fixtures/` Directory

The `eval_fixtures/` directory holds immutable replay seed artifacts. Files in this directory:
- Are **never modified** after creation
- Are **uploaded to S3** (`recoup-eval-fixtures-{acct}-{region}`) by `deploy.sh`
- Are **versioned** in S3 (versioning enabled on the bucket)

```
eval_fixtures/
└── sla/
    └── api_gateway/
        └── canonical/
            ├── health_event.json       — synthetic AWS Health event (full EventBridge schema)
            ├── metric_series.json      — 8,640 five-minute intervals; 6 at 0% (02:00–02:30 UTC Aug 1)
            ├── billing_snapshot.json   — August 2026 billing: $3.51 for API Gateway us-east-1
            ├── cloudtrail_events.json  — benign events; verdict: no_customer_caused_errors
            ├── sla_contract_ref.yaml   — points to sla_catalog/api_gateway/2022-05-05.yaml
            └── expected_output.json    — calculator result: 99.930556%, tier=10%, credit=$0.35
```

`ReplayAdapter._load_fixtures()` loads these files into `GraphState.replay_fixtures` at state-build time. The `incident_correlation` stub parses intervals from `metric_series.json` and billing from `billing_snapshot.json` before falling back to golden constants.

---

## CI Verification

The `ship-gates` CI job runs:

```bash
pytest tests/unit/ tests/e2e/test_golden_replay.py -W error::DeprecationWarning
python scripts/assert_ship_gates.py scorecard.json
```

The golden replay test (Phase 2 e2e suite):

```python
def test_canonical_replay_produces_real_credit():
    adapter = ReplayAdapter()
    state = adapter.build_state(CANONICAL_SCENARIO)
    final_state = recoup_graph.run(state)
    assert final_state.availability_result.potential_credit == Decimal("0.35")
    assert final_state.availability_result.monthly_uptime_pct == Decimal("99.930556")

def test_canonical_replay_20_consecutive_runs():
    # 20/20 must return identical $0.35
    results = [recoup_graph.run(adapter.build_state()) for _ in range(20)]
    assert all(r.availability_result.potential_credit == Decimal("0.35") for r in results)
```

The `assert_ship_gates.py` script enforces ship-gate metrics from the scorecard JSON (aligned with the six live gates in `/api/quality/scorecard` plus legacy threshold fields where configured).

---

## Adding New Scenarios

1. Create a `ReplayScenario` instance with the desired parameters:

```python
my_scenario = ReplayScenario(
    scenario_id="replay-s3-2026-09-sla-001",
    name="S3 25% SLA Credit — September 2026",
    description="...",
    event={
        "source": "replay",
        "event_id": "replay-s3-2026-09-sla-001",
        "service": "s3",
        "region": "us-east-1",
        "start": "2026-09-01T00:00:00Z",
        "end": "2026-09-01T06:00:00Z",
        "affected_resource_ids": ["arn:aws:s3:::my-bucket"],
        "raw_ref": "s3://recoup-eval-fixtures/replay/s3-2026-09-sla-001.json",
        "replay": True,
    },
    expected_credit_usd=Decimal("5000.00"),
    expected_uptime_pct=Decimal("97.500000"),
    tags=["s3", "sla_25pct"],
)
```

2. Persist to `eval_fixtures/replay/s3-2026-09-sla-001.json`
3. Ensure the corresponding SLA contract exists in `sla_catalog/s3/`
4. Add a golden test to `tests/unit/test_calculator.py`
