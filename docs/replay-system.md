# Recoup — Verified Replay System

**Files:**  
- Adapter: `backend/src/recoup/adapters/replay.py`  
- API Route: `backend/src/recoup/api/routes/replay.py`  
- Fixtures dir: `eval_fixtures/`  
**Status:** Phase 1 complete — canonical $1,840 scenario runs end-to-end

---

## What is a Verified Replay?

A Verified Replay is a **seedable, deterministic execution** of the full Recoup agent graph using a pre-recorded synthetic incident. It:

1. Loads a canonical event payload from `eval_fixtures/` (no live AWS incident required)
2. Sets `simulation_mode=True` (no real AWS Support submission)
3. Runs the complete 11-node graph
4. Produces the same numerical result — **$1,840.00** — on every run
5. Finishes in P95 ≤ 60 seconds

The replay is the **primary judge demo path**. No AWS credentials, no live incident, no Bedrock model calls needed in Phase 1 (all AgentNode stubs are deterministic).

---

## Why Replay-First?

| Problem | Replay Solution |
|---------|----------------|
| Live AWS incidents are unpredictable | Replay is seeded from immutable `eval_fixtures/` |
| Real credit claims have consequences | `simulation_mode=True` prevents real submissions |
| Evaluation reproducibility | Same input → same `case_id`, always |
| Demo during judging | No AWS credentials required for the judge to verify |
| CI golden test | `pytest` verifies `potential_credit == Decimal("1840.00")` on every run |

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
        "$18,400 billed charges → $1,840.00 potential credit."
    ),
    event=_CANONICAL_EVENT,
    expected_credit_usd=Decimal("1840.00"),
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
4. Sets `simulation_mode=True`
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

assert final_state.availability_result.potential_credit == Decimal("1840.00")
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
  "simulation_mode": true,
  "monthly_uptime_pct": "99.930556",
  "threshold_breached": true,
  "tier_pct": "10",
  "billed_charges": "18400.00",
  "potential_credit": "1840.00",
  "case_id": "sim-a3f9c12b4d01",
  "errors": []
}
```

### Via Curl (full graph + trace)

```bash
# Run via opportunities endpoint (also returns a trace)
OPPORTUNITY_ID="opp-$(date +%s)"

curl -X POST http://localhost:8000/api/opportunities/$OPPORTUNITY_ID/run \
  -H "Content-Type: application/json" \
  -d '{"simulation_mode": true}'

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
| `case_id` | `"sim-" + sha256(calculator_result_hash)[:12]` — same input → same ID |
| `idempotency_key` | `"replay:" + sha256(scenario_id)[:16]` — fixed per scenario |

---

## `eval_fixtures/` Directory

The `eval_fixtures/` directory holds immutable replay seed artifacts. Files in this directory:
- Are **never modified** after creation
- Are **uploaded to S3** (`recoup-eval-fixtures-{acct}-{region}`) by `deploy.sh`
- Are **versioned** in S3 (versioning enabled on the bucket)

```
eval_fixtures/
└── replay/
    └── apigateway-2026-08-sla-001.json   (Phase 2 — not yet created)
```

Phase 1 uses the in-code `_CANONICAL_EVENT` constant. Phase 2 will persist the full event JSON to `eval_fixtures/` and load it via `ReplayAdapter.load_scenario_from_file()`.

---

## CI Verification

The `ship-gates` CI job runs:

```bash
pytest tests/unit/test_calculator.py -W error::DeprecationWarning
```

The test includes a replay assertion:

```python
def test_canonical_replay_produces_1840():
    adapter = ReplayAdapter()
    state = adapter.build_state(CANONICAL_SCENARIO)
    final_state = recoup_graph.run(state)
    assert final_state.availability_result.potential_credit == Decimal("1840.00")
    assert final_state.availability_result.monthly_uptime_pct == Decimal("99.930556")
```

This test is also enforced in the `ship-gates` job comment in STATUS.md as a blocking gate for Phase 2 completion.

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
