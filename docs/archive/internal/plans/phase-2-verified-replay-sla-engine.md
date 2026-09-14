# Phase 2 — Verified Replay & SLA Recovery Engine

> **Historical — internal only.** Current product: [docs index](../../../README.md) · [judge-demo.md](../../../judge-demo.md) · [STATUS.md](../STATUS.md).



**Timeline:** Day 6–9 (Target: by Sep 9, 2026)  
**Status:** `[ ] Not Started`  
**Depends on:** Phase 1 complete

---

## Objective

Build the hero demo path end-to-end. This phase implements the full canonical SLA claim workflow as a **Verified Replay** — a deterministic, immutable, seedable execution that produces the same credit result on every run and proves the complete agent workflow. Credit amount comes from real AWS billing data in billing_snapshot.json (e.g. $0.35 for demo account). The Verified Replay is the primary judge demo path.

---

## Goals

- [ ] Canonical replay seed artifacts committed to S3/repo (immutable event JSON, metric series, billing snapshot)
- [ ] `normalize_event` node correctly parses replay and live schema
- [ ] `incident_correlation` agent correctly correlates synthetic API Gateway SLA incident
- [ ] `sla_contract_resolver` loads the correct 2022-05-05 contract by incident date
- [ ] `availability_calculator` deterministically produces `99.9306%` and a positive credit from real billing data
- [ ] Full end-to-end replay executes in < 60 seconds (P95)
- [ ] Replay can be triggered via `POST /api/replay/api-gateway-sla` and monitored via SSE/WebSocket
- [ ] All golden acceptance tests pass (Appendix C from spec)
- [ ] `simulation_mode = true` is enforced throughout replay; real Support API never called
- [ ] REPLAY badge metadata attached to all replay opportunities

---

## Workstreams

### 2.1 Replay Seed Artifacts

**Location:** `eval_fixtures/sla/api_gateway/canonical/`

These are immutable, committed artifacts. Never overwrite once used in a CI run.

```
eval_fixtures/sla/api_gateway/canonical/
├── health_event.json          # Synthetic AWS Health event (same schema as real EventBridge event)
├── metric_series.json         # 8,640 five-minute intervals; 6 at 0% availability
├── billing_snapshot.json      # Real AWS billing from inject_sla_traffic.py (e.g. $3.51 for demo account)
├── cloudtrail_events.json     # Real CloudTrail events captured by inject script
├── sla_contract_ref.yaml      # Points to sla_catalog/api_gateway/2022-05-05.yaml
└── expected_output.json       # Calculator result: 99.9306%, tier=10%, credit=real amount (e.g. $0.35)
```

**Canonical `health_event.json`:**
```json
{
  "version": "0",
  "source": "aws.health",
  "detail-type": "AWS Health Event",
  "detail": {
    "service": "APIGATEWAY",
    "eventTypeCode": "AWS_APIGATEWAY_OPERATIONAL_ISSUE",
    "region": "us-east-1",
    "startTime": "2026-08-01T02:00:00Z",
    "endTime": "2026-08-01T02:30:00Z",
    "affectedResources": [
      { "entityValue": "arn:aws:apigateway:us-east-1::/restapis/demo1234" }
    ]
  },
  "_recoup_replay": true,
  "_recoup_fixture_version": "1.0.0"
}
```

**Metric series generation script:**
```python
# scripts/generate_canonical_fixtures.py
def generate_metric_series():
    """
    Generate 8,640 five-minute intervals for August 2026.
    6 intervals at 0% availability (2:00–2:30 UTC Aug 1).
    All others at 100%.
    """
    intervals = []
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    for i in range(8640):
        ts = start + timedelta(minutes=5 * i)
        is_incident = 12 <= i <= 17  # 2:00–2:30 UTC (12th–17th five-min slot)
        intervals.append({
            "start": ts.isoformat(),
            "end": (ts + timedelta(minutes=5)).isoformat(),
            "availability_pct": "0.0" if is_incident else "100.0",
            "request_count": 0 if is_incident else 1000,
            "error_count": 1000 if is_incident else 0,
        })
    return intervals
```

### 2.2 Availability & Credit Calculator

**Location:** `backend/src/recoup/engines/calculator.py`

This is the financial heart of Recoup. All arithmetic is deterministic, testable, and has no LLM involvement.

```python
from decimal import Decimal, ROUND_HALF_UP

def calculate_monthly_uptime(
    intervals: list[AvailabilityInterval],
    contract: SLAContract,
) -> AvailabilityResult:
    """
    RFC-faithful SLA calculator.
    
    Monthly uptime % = (total_minutes - downtime_minutes) / total_minutes * 100
    where downtime = minutes in intervals below the service commitment threshold.
    
    For API Gateway: 5-minute intervals; any interval with ≥1 error is treated
    per the SLA as a "downtime" minute.
    """
    total_intervals = len(intervals)
    assert total_intervals == 8640, f"Expected 8,640 intervals for a full month, got {total_intervals}"

    unavailable_intervals = [i for i in intervals if i.availability_pct < Decimal("100")]
    unavailable_count = len(unavailable_intervals)

    # SLA formula: (total - unavailable) / total * 100
    monthly_uptime_pct = (
        Decimal(total_intervals - unavailable_count) / Decimal(total_intervals) * Decimal(100)
    ).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    # Golden test: 8640 intervals, 6 at 0% → 99.930556%
    # (8640 - 6) / 8640 * 100 = 8634/8640 * 100 = 99.9305555...%

    threshold_breached = monthly_uptime_pct < contract.service_commitment

    tier_pct = Decimal("0")
    if threshold_breached:
        for tier in sorted(contract.credit_tiers, key=lambda t: t.min_pct, reverse=True):
            if tier.min_pct <= monthly_uptime_pct < tier.max_exclusive_pct:
                tier_pct = tier.credit_pct
                break

    potential_credit = (billed_charges * tier_pct / Decimal(100)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    calculation_trace = [
        f"Total intervals: {total_intervals}",
        f"Unavailable intervals: {unavailable_count}",
        f"Monthly uptime %: ({total_intervals} - {unavailable_count}) / {total_intervals} × 100 = {monthly_uptime_pct}%",
        f"SLA commitment: {contract.service_commitment}%",
        f"Threshold breached: {threshold_breached}",
        f"Credit tier: {tier_pct}%",
        f"Billed charges: ${billed_charges}",
        f"Potential credit: ${billed_charges} × {tier_pct}% = ${potential_credit}",
    ]

    return AvailabilityResult(
        monthly_uptime_pct=monthly_uptime_pct,
        threshold_breached=threshold_breached,
        tier_pct=tier_pct,
        billed_charges=billed_charges,
        potential_credit=potential_credit,
        calculation_trace=calculation_trace,
    )
```

**Golden acceptance tests (from spec Appendix C):**

```python
# tests/unit/test_calculator.py
def test_golden_uptime_calculation():
    """Spec test 1: 8,640 intervals, 6 at 0% → 99.930555...%"""
    intervals = make_intervals(total=8640, unavailable_count=6)
    result = calculate_monthly_uptime(intervals, api_gateway_contract)
    assert result.monthly_uptime_pct == Decimal("99.930556")  # rounded to 6dp

def test_golden_tier_10_pct():
    """Spec test 2: 99.9306% → 10% tier (not 25%)"""
    result = resolve_tier(Decimal("99.9306"), api_gateway_contract)
    assert result == Decimal("10")

def test_golden_credit_real():
    """Spec test 3: real billed amount × 10% = real credit (e.g. $3.51 × 10% = $0.351)"""
    credit = calculate_credit(Decimal("3.51"), Decimal("10"))
    assert credit == Decimal("0.351")

def test_exact_commitment_not_eligible():
    """Spec test 4: 99.95% is not breached (less-than boundary)"""
    result = calculate_monthly_uptime(
        make_intervals_for_uptime(Decimal("99.95")), api_gateway_contract
    )
    assert not result.threshold_breached

def test_missing_api_id_blocks_submission():
    """Spec test 5: missing API id → NEEDS_EVIDENCE; submit unreachable"""
    ...

def test_no_requests_interval_handling():
    """Spec test for zero-request intervals"""
    ...
```

### 2.3 SLA Contract Resolver

**Location:** `backend/src/recoup/engines/sla_resolver.py`

```python
def resolve_sla_contract(
    service: str,
    region: str,
    incident_date: date,
) -> SLAContract:
    """
    Load the correct SLA contract version by service and effective date.
    Never allow agent to browse the web at claim time.
    Contract must be in the local/S3 catalog with source hash.
    """
    contracts = load_catalog(service)  # from sla_catalog/ directory
    applicable = [
        c for c in contracts
        if c.effective_from <= incident_date
        and (c.effective_to is None or c.effective_to >= incident_date)
    ]
    if not applicable:
        raise SLAContractNotFoundError(service=service, date=incident_date)
    return max(applicable, key=lambda c: c.effective_from)
```

### 2.4 Replay Adapter

**Location:** `backend/src/recoup/adapters/replay.py`

```python
class ReplayAdapter:
    """
    Intercepts every external AWS call and returns seeded fixture data instead.
    Guarantees deterministic, repeatable execution without real AWS calls.
    """

    def get_health_event(self, event_id: str) -> dict:
        return load_fixture("health_event.json")

    def get_cloudwatch_metrics(self, **kwargs) -> MetricSeries:
        return load_fixture("metric_series.json")

    def get_cost_and_usage(self, **kwargs) -> BillingRecord:
        return load_fixture("billing_snapshot.json")

    def simulate_support_case(self, package: ClaimPackage, approval: ApprovalRecord) -> str:
        """Always returns a REPLAY-* case id. Never calls real Support API."""
        return f"REPLAY-{uuid4().hex[:8].upper()}"
```

**Adapter routing:**
```python
def get_adapter(simulation_mode: bool) -> Union[LiveAdapter, ReplayAdapter]:
    if simulation_mode:
        return ReplayAdapter()
    # Live adapter only when simulation_mode=false AND env flag set AND policy allows
    if not os.getenv("RECOUP_ENABLE_LIVE_AWS"):
        raise LiveAdapterDisabledError()
    return LiveAdapter()
```

### 2.5 Replay API Endpoint

**Location:** `backend/src/recoup/api/replay.py`

```python
@router.post("/api/replay/api-gateway-sla")
async def trigger_canonical_replay(session: SessionDep) -> ReplayResponse:
    """
    Trigger the canonical API Gateway SLA replay.
    Creates a new opportunity with simulation_mode=True.
    Returns opportunity_id for polling/SSE.
    """
    idempotency_key = f"replay-canonical-{date.today().isoformat()}"
    opportunity = await create_or_fetch_opportunity(idempotency_key, simulation_mode=True)
    await enqueue_replay_event(opportunity.id, fixture="api_gateway_canonical")
    return ReplayResponse(opportunity_id=opportunity.id, sse_url=f"/api/opportunities/{opportunity.id}/stream")
```

### 2.6 Progress Streaming

Use Server-Sent Events (SSE) to push node-by-node progress to the frontend during replay:

```python
@router.get("/api/opportunities/{id}/stream")
async def stream_opportunity_progress(id: str, session: SessionDep):
    async def generate():
        async for event in subscribe_to_opportunity(id):
            yield f"data: {event.json()}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")
```

**SSE event types:**
- `node_started` — { node, timestamp }
- `node_completed` — { node, duration_ms, output_summary }
- `node_failed` — { node, error_type, retryable }
- `approval_required` — { action, amount, claim_hash, expires_at }
- `opportunity_updated` — { state, state_version }

---

## Definition of Done

| Check | Criteria |
|-------|----------|
| Seed artifacts | Committed; immutable; `_recoup_replay: true` flag present |
| Calculator | All 12 golden acceptance tests pass with deterministic `Decimal` math |
| SLA resolver | Resolves correct contract version by date; CI test for catalog integrity |
| Replay adapter | Full end-to-end replay returns `REPLAY-*` case id; never calls real Support |
| Replay API | `POST /api/replay/api-gateway-sla` triggers workflow; SSE streams progress |
| Timing | P95 replay completion time < 60 seconds in CI |
| simulation_mode | Every tool call in replay confirms `simulation_mode=true`; policy test passes |
| 20/20 consecutive | Golden replay produces identical result on 20 consecutive runs |

---

## Post-Implementation Documentation

> Created in `plans/docs/` after phase completion.

- `docs/calculator.md` — SLA availability and credit calculation methodology, formula derivation, and tier boundary logic
- `docs/sla-contract-resolver.md` — How contracts are versioned, loaded, and validated at claim time
- `docs/replay-system.md` — Replay adapter design, seed artifact structure, and how to add new replay scenarios
- `docs/replay-api.md` — API reference for replay endpoints and SSE event stream
- `docs/golden-acceptance-tests.md` — Full list of golden acceptance tests with expected inputs/outputs

---

## Risks

| Risk | Mitigation |
|------|-----------|
| Decimal rounding inconsistency | Use `Decimal` throughout; never `float`; pin rounding mode to `ROUND_HALF_UP` |
| Fixture mutation breaking 20/20 test | Treat fixture files as immutable; add CI check for file hash |
| SSE disconnection during replay | Client-side reconnect with `Last-Event-ID`; state persisted in DynamoDB |
| Replay > 60 second P95 | Profile and cache SLA contract load; warm fixtures in memory |
