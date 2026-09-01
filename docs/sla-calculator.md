# Recoup — SLA Calculator Reference

**Files:**  
- Calculator: `backend/src/recoup/engines/calculator.py`  
- Resolver: `backend/src/recoup/engines/sla_resolver.py`  
- SLA Catalog: `sla_catalog/api_gateway/2022-05-05.yaml`  
**Status:** Complete — 63/63 tests pass, 0 DeprecationWarnings

---

## Overview

The SLA Calculator is a **pure deterministic Python module** with zero LLM involvement. All arithmetic uses `Decimal` with explicit rounding to eliminate floating-point drift. The golden test value (`$1,840.00`) must match exactly on every run — no tolerance margin.

---

## Availability Formula

```
monthly_uptime_pct = (total_intervals - unavailable_intervals) / total_intervals × 100

threshold_breached = monthly_uptime_pct < service_commitment

tier_pct = credit_tiers[matching tier] if threshold_breached else 0

potential_credit = billed_charges × tier_pct / 100  (if threshold_breached)
                 = $0.00                              (if not threshold_breached)
```

**Boundary condition:** The threshold is a **strict less-than**. A monthly uptime of exactly `99.95%` with a `99.95%` commitment does **not** breach the SLA.

---

## What "Unavailable" Means

An interval is considered **unavailable** when:
```python
interval.availability_pct < Decimal("100")
```

For API Gateway, this corresponds to any 5-minute window where the error rate exceeded the SLA threshold. The `availability_pct` field is populated by the `incident_correlation` node from CloudWatch `5XXError` metrics.

---

## Decimal Precision

```python
monthly_uptime_pct = (...).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
potential_credit   = (...).quantize(Decimal("0.01"),     rounding=ROUND_HALF_UP)
```

- Uptime percentage: 6 decimal places (e.g. `99.930556`)
- Credit amount: 2 decimal places (e.g. `1840.00`)
- All intermediate arithmetic uses `Decimal`, never `float`

---

## Function Signature

```python
def calculate_availability_and_credit(
    intervals: list[AvailabilityInterval],
    contract: SLAContract,
    billed_charges: Decimal,
) -> AvailabilityResult:
```

**Arguments:**
- `intervals` — All `AvailabilityInterval` objects for the billing month (not just unavailable ones)
- `contract` — The `SLAContract` loaded by the `sla_contract_resolver` node
- `billed_charges` — Total AWS charges for the affected service in the billing cycle

**Returns:** `AvailabilityResult` with uptime %, tier, credit, and a human-readable `calculation_trace`

---

## API Gateway SLA Contract (`2022-05-05`)

**File:** `sla_catalog/api_gateway/2022-05-05.yaml`

```yaml
service: apigateway
version: "2022-05-05"
effective_from: "2022-05-05"
effective_to: null              # still in effect
service_commitment: "99.95"
interval_minutes: 5
claim_deadline_rule: "end_of_second_billing_cycle_after_incident"
```

### Credit Tiers

| Uptime Range | Credit |
|-------------|--------|
| 99.00% ≤ uptime < 99.95% | **10%** of monthly billed charges |
| 95.00% ≤ uptime < 99.00% | **25%** of monthly billed charges |
| 0.00% ≤ uptime < 95.00% | **100%** of monthly billed charges |

### Required Claim Fields

```
api_id · region · billing_cycle · request_logs · error_logs · billing_record
```

### SLA Exclusions

```
customer_caused_errors · backend_lambda_failures · planned_maintenance · force_majeure
```

---

## Golden Test Specification (Appendix C)

The golden test in `tests/unit/test_calculator.py` must pass on every CI run. Any change that breaks the golden value (`$1,840.00`) fails CI.

### Canonical Scenario

| Parameter | Value |
|-----------|-------|
| Service | Amazon API Gateway |
| Region | us-east-1 |
| Billing month | August 2026 (31 days) |
| Total 5-minute intervals | 8,640 (31 × 24 × 60 ÷ 5) |
| Unavailable intervals | 6 |
| Billed charges | $18,400.00 |

### Step-by-Step Calculation

**Step 1 — Monthly uptime %**
```
(8,640 - 6) / 8,640 × 100
= 8,634 / 8,640 × 100
= 0.99930555... × 100
= 99.930556%   (quantized to 6 dp, ROUND_HALF_UP)
```

**Step 2 — Threshold check**
```
99.930556% < 99.95%  → TRUE  (threshold breached)
```

**Step 3 — Credit tier**
```
99.00% ≤ 99.930556% < 99.95%  → 10% tier
```

**Step 4 — Credit amount**
```
$18,400.00 × 10% = $1,840.00  (quantized to 2 dp)
```

### Expected Outputs

```python
AvailabilityResult(
    monthly_uptime_pct=Decimal("99.930556"),
    threshold_breached=True,
    tier_pct=Decimal("10"),
    billed_charges=Decimal("18400.00"),
    potential_credit=Decimal("1840.00"),
    calculation_trace=[
        "Total 5-minute intervals in billing month: 8,640",
        "Unavailable intervals (availability < 100%): 6",
        "Formula: (8,640 − 6) ÷ 8,640 × 100",
        "Monthly uptime %: 99.930556%",
        "SLA commitment: 99.95%",
        "Threshold breached: YES (99.930556% < 99.95%)",
        "Credit tier: 10%",
        "Billed charges in affected billing cycle: $18,400",
        "Potential credit: $18,400 × 10% = $1,840",
    ],
)
```

---

## SLA Contract Resolver

**File:** `backend/src/recoup/engines/sla_resolver.py`

### Resolution Algorithm

```python
def resolve_sla_contract(
    service: str,
    region: str,
    incident_date: date,
) -> SLAContract:
```

1. Normalize the service name via `_SERVICE_DIR_ALIASES` (e.g. `"apigateway"` → `"api_gateway"`)
2. Load all `*.yaml` files from `sla_catalog/{service_dir}/`
3. Filter to contracts where `effective_from ≤ incident_date ≤ effective_to` (or `effective_to is None`)
4. Return the contract with the latest `effective_from` (most recent applicable version)
5. Raise `SLAContractNotFoundError` if no contract matches

### Service Directory Aliases

```python
_SERVICE_DIR_ALIASES = {
    "apigateway":           "api_gateway",
    "api-gateway":          "api_gateway",
    "lambda":               "lambda",
    "ec2":                  "ec2",
    "s3":                   "s3",
    "rds":                  "rds",
    "elasticloadbalancing": "elb",
    "elb":                  "elb",
    "cloudfront":           "cloudfront",
    "dynamodb":             "dynamodb",
    "sqs":                  "sqs",
    "sns":                  "sns",
}
```

### `source_hash` Integrity

Every SLA contract YAML includes a `source_hash` field containing the SHA-256 of the original AWS SLA document. The CI test (`test_sla_catalog.py`) verifies this field is present and starts with `"sha256:"`.

This prevents undetected tampering with contract terms that would silently change credit calculations.

---

## Calculation Trace

The `calculation_trace` list is stored in `AvailabilityResult` and displayed in the UI as a step-by-step audit trail. Example:

```
Total 5-minute intervals in billing month: 8,640
Unavailable intervals (availability < 100%): 6
Formula: (8,640 − 6) ÷ 8,640 × 100
Monthly uptime %: 99.930556%
SLA commitment: 99.95%
Threshold breached: YES (99.930556% < 99.95%)
Credit tier: 10%
Billed charges in affected billing cycle: $18,400
Potential credit: $18,400 × 10% = $1,840
```

This trace is the "show your work" output that makes the claim verifiable by a human reviewer and by the evaluation scorecard.

---

## Edge Cases

| Scenario | Behavior |
|----------|---------|
| Zero intervals | `ValueError: "Cannot calculate availability with zero intervals"` |
| All intervals available (100%) | `threshold_breached=False`, `potential_credit=Decimal("0.00")` |
| Uptime exactly at commitment (99.95%) | Not breached — strict `<` comparison |
| Uptime below lowest tier (< 0%) | Not possible — `availability_pct` is `Decimal("0")` minimum |
| Multiple applicable contract versions | Most recent `effective_from` wins |
| No contract for service | `SLAContractNotFoundError` raised (fatal in graph) |
| Service alias not found | Falls back to raw service name as directory |

---

## Running the Tests

```bash
cd backend
pytest tests/unit/test_calculator.py -v -W error::DeprecationWarning
```

The `ship-gates` CI job runs this test in isolation and fails the build if the golden value does not match exactly.
