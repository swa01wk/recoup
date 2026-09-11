# Recoup — Domain Models Reference

**Location:** `backend/src/recoup/models/`  
**Framework:** Pydantic v2 (zero deprecation warnings)  
**Count:** 9 models (+ graph-internal types in `graph/types.py`)  
**Last updated:** Sep 11, 2026  
**Status:** Phase 0 + Phase 1 complete; all 9 models pass `pytest -W error::DeprecationWarning`  
**Playwright tests:** `opportunity-detail.spec.ts`, `recovery-ledger.spec.ts` verify model field shapes via API.

---

## Model Relationships

```
IncidentSignal
    │ consumed by
    ▼
IncidentHypothesis ──── AvailabilityInterval (×N)
    │                       │
    ▼                       ▼
SLAContract ──────► AvailabilityResult
    │ (credit_tiers)
    │
    ▼
EvidenceManifest ──── EvidenceItem (×N)
    │                    └── RedactionReport
    ▼
EligibilityAssessment
    │
    ▼
ApprovalRecord
    │
    ▼
ClaimPackage ──── EvidenceManifest (embedded)
    │
    ▼
RecoveryOpportunity (state machine entity)
    │
    ▼
ToolAudit (one per tool call)
```

---

## 1. `IncidentSignal`

**File:** `models/signal.py`  
**Purpose:** Normalized input from EventBridge, SQS, or the replay adapter. The raw event payload is never passed downstream — only a reference to its S3 URI.

```python
class IncidentSignal(BaseModel):
    source: Literal["aws_health", "cost_anomaly", "optimization", "replay"]
    event_id: str
    service: str
    region: str
    start: datetime
    end: datetime
    affected_resource_ids: list[str]
    raw_ref: str          # S3 URI of raw event — never the content itself
    replay: bool = False
```

**Key constraint:** `raw_ref` stores an S3 URI. The raw event JSON is never placed in agent context.

---

## 2. `SLAContract`

**File:** `models/sla.py`  
**Purpose:** Represents a human-verified AWS SLA contract loaded from `sla_catalog/`. Never fetched at claim time; tamper-detected via `source_hash`.

```python
class CreditTier(BaseModel):
    min_pct: Decimal
    max_exclusive_pct: Decimal   # exclusive upper bound
    credit_pct: Decimal          # e.g. Decimal("10") for 10%

class SLAContract(BaseModel):
    service: str                   # e.g. "apigateway"
    version: str                   # e.g. "2022-05-05"
    effective_from: date
    effective_to: date | None      # None = still in effect
    service_commitment: Decimal    # e.g. Decimal("99.95")
    interval_minutes: int          # e.g. 5 (API Gateway monitoring window)
    claim_deadline_rule: str       # human-readable rule
    credit_tiers: list[CreditTier]
    required_claim_fields: list[str]
    exclusions: list[str]
    source_url: str
    source_hash: str               # must start with "sha256:"
```

**Validation:**
- `CreditTier.min_pct < max_exclusive_pct` enforced
- `source_hash` must start with `"sha256:"` (enforced by `model_validator`)

**`resolve_tier(monthly_uptime_pct)` method:**
- Returns the `credit_pct` for the matching tier
- Tiers are evaluated from highest to lowest (reverse sort on `min_pct`)
- Returns `Decimal("0")` if uptime meets or exceeds commitment

**Current catalog:** `sla_catalog/api_gateway/2022-05-05.yaml`

```
service_commitment: 99.95%
Tier 1: uptime < 99.95%  → 10% credit
Tier 2: uptime < 99.0%   → 25% credit
Tier 3: uptime < 95.0%   → 100% credit
```

---

## 3. `AvailabilityInterval`

**File:** `models/availability.py`  
**Purpose:** A single monitoring interval (typically 5 minutes for API Gateway). The calculator aggregates a month's worth of intervals.

```python
class AvailabilityInterval(BaseModel):
    start: datetime
    end: datetime
    availability_pct: Decimal     # 0 = unavailable, 100 = fully available
    request_count: int            # ≥ 0
    error_count: int              # ≥ 0
    evidence_refs: list[str]      # S3 URIs of supporting metrics/logs
```

---

## 4. `AvailabilityResult`

**File:** `models/availability.py`  
**Purpose:** Output of the `availability_calculator` node. Contains the computed uptime %, credit tier, and a human-readable calculation trace.

```python
class AvailabilityResult(BaseModel):
    monthly_uptime_pct: Decimal    # e.g. Decimal("99.930556")
    threshold_breached: bool       # True if uptime < service_commitment
    tier_pct: Decimal              # e.g. Decimal("10")
    billed_charges: Decimal        # charges in the affected billing cycle
    potential_credit: Decimal      # e.g. Decimal("0.35")
    calculation_trace: list[str]   # human-readable arithmetic steps for UI

    @property
    def is_eligible(self) -> bool:
        return self.threshold_breached and self.potential_credit > Decimal("0")
```

**Golden test values:**
```
8,640 intervals, 6 unavailable → 99.930556% → tier 10% → $3.51 × 10% = $0.35
```

---

## 5. `EvidenceItem` + `EvidenceManifest`

**File:** `models/evidence.py`  
**Purpose:** Evidence is always stored in S3 and referenced by ID. Raw content never appears in agent context or API responses.

```python
class EvidenceItem(BaseModel):
    id: str                        # e.g. "ev-a3f92c1d"
    type: Literal["metric", "log", "health_event", "billing_record", "contract"]
    source: str                    # e.g. "cloudwatch:GetMetricStatistics"
    timestamp_range: tuple[datetime, datetime]
    storage_uri: str               # S3 URI of raw evidence (KMS encrypted)
    sanitized_uri: str | None      # S3 URI of sanitized version
    hash: str                      # SHA-256 of raw content; starts with "sha256:"
    sensitivity: Literal["LOW", "MEDIUM", "HIGH"]
    status: Literal["FOUND", "MISSING", "REDACTED"]

class RedactionReport(BaseModel):
    evidence_id: str
    redaction_count: int = 0
    raw_hash: str                  # SHA-256 of all raw hashes combined
    sanitized_hash: str            # SHA-256 of all sanitized hashes combined
    patterns_applied: list[str]    # e.g. ["account_id", "ip_address", "auth_token"]

class EvidenceManifest(BaseModel):
    opportunity_id: str
    items: list[EvidenceItem]
    missing_fields: list[str]      # required fields not yet collected
    redaction_report: RedactionReport

    @property
    def is_complete(self) -> bool:
        return len(self.missing_fields) == 0

    @property
    def item_ids(self) -> set[str]:
        return {item.id for item in self.items}
```

---

## 6. `EligibilityAssessment`

**File:** `models/eligibility.py`  
**Purpose:** Output of the `eligibility_reasoner` AgentNode. The agent can only reference evidence by ID (not by content).

```python
class EligibilityAssessment(BaseModel):
    eligible_estimate: bool
    confidence: float              # 0.0 – 1.0
    satisfied_requirements: list[str]
    unresolved: list[str]          # contract requirements not yet met
    possible_exclusions: list[str] # SLA exclusions that might apply
    evidence_refs: list[str]       # IDs from EvidenceManifest only
```

**Validation:**
- Low-confidence assessments (`confidence < 0.7`) must include at least one `unresolved` item or `possible_exclusion`. This prevents the agent from emitting a vague low-confidence assessment without explanation.

---

## 7. `ApprovalRecord`

**File:** `models/approval.py`  
**Purpose:** HITL approval record. Bound to a specific `ClaimPackage` hash, amount, and state version. Stored in DynamoDB with TTL.

```python
class ApprovalState(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    DECLINED = "DECLINED"

class ApprovalRecord(BaseModel):
    approval_id: str
    principal: str                 # who is being asked to approve
    action: str                    # human-readable action description
    amount: Decimal                # the credit amount being approved
    claim_hash: str                # SHA-256 of ClaimPackage JSON
    opportunity_id: str
    state_version: int             # bound to this exact version; stale if changed
    timestamp: datetime
    expires_at: datetime           # default TTL: 24 hours
    state: ApprovalState

    @property
    def is_valid(self) -> bool:
        return self.state == ApprovalState.APPROVED and self.expires_at > utcnow()
```

**Factory method:**
```python
record = ApprovalRecord.create(
    approval_id="appr-001",
    principal="ops-team",
    action="Submit $0.35 SLA credit claim to AWS Support",
    amount=Decimal("0.35"),
    claim_hash="sha256:...",
    opportunity_id="opp-replay-001",
    state_version=3,
    ttl_hours=24,
)
```

**Binding:** The `claim_hash` and `state_version` mean that if the opportunity changes after the approval is issued, the approval becomes stale and cannot be used.

---

## 8. `ClaimPackage`

**File:** `models/claim.py`  
**Purpose:** The complete package ready to submit to AWS Support. Validated to ensure no invented evidence IDs.

```python
class ClaimPackage(BaseModel):
    opportunity_id: str
    subject: str
    body: str                          # the actual claim text
    region: str
    billing_cycle: str                 # e.g. "2026-08"
    resources: list[str]               # affected resource ARNs
    evidence_manifest: EvidenceManifest
    calculator_result_hash: str        # SHA-256 of AvailabilityResult JSON
```

**Critical validator (`evidence_refs_exist_in_manifest`):**
All `ev-XXXXXXXX` patterns found in `body` must correspond to IDs present in `evidence_manifest.item_ids`. Any invented evidence ID raises a `ValueError`. This is a hard safety guard against LLM hallucination of evidence references.

---

## 9. `RecoveryOpportunity`

**File:** `models/opportunity.py`  
**Purpose:** The core state machine entity persisted in DynamoDB. One record per detected incident.

```python
class OpportunityState(str, Enum):
    DETECTED = "DETECTED"
    INVESTIGATING = "INVESTIGATING"
    EVIDENCE_READY = "EVIDENCE_READY"
    NEEDS_EVIDENCE = "NEEDS_EVIDENCE"
    ELIGIBILITY_REVIEWED = "ELIGIBILITY_REVIEWED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    SUBMITTING = "SUBMITTING"
    SUBMITTED = "SUBMITTED"
    MONITORING = "MONITORING"
    RECOVERED = "RECOVERED"
    REJECTED = "REJECTED"
    NEEDS_FOLLOWUP = "NEEDS_FOLLOWUP"
    DENIED = "DENIED"
    FAILED = "FAILED"

class RecoveryOpportunity(BaseModel):
    id: str
    type: Literal["SLA", "ANOMALY", "OPTIMIZATION"]
    account_id_masked: str         # last 4 digits of account ID only
    service: str
    region: str
    discovered_at: datetime
    potential_value: Decimal
    confidence: float              # 0.0 – 1.0
    state: OpportunityState
    state_version: int             # increments atomically on every state change
    idempotency_key: str
    active_claim_hash: str | None
```

**`account_id_masked` validator:**
The 12-digit AWS account ID is always masked to only the last 4 digits before storage (e.g. `"123456789012"` → `"****9012"`).

> **Phase 6d note:** `simulation_mode` was removed from `RecoveryOpportunity`. Real AWS Support submission is now gated exclusively by `recoup_enable_real_support_submission` in config + Cedar policy ALLOW + valid `ApprovalRecord`.

---

## 10. `ToolAudit`

**File:** `models/audit.py`  
**Purpose:** Immutable record of every tool call, written by the `after_tool_call` hook. Stored in the `recoup-tool-audits` DynamoDB table.

```python
class ToolAudit(BaseModel):
    trace_id: str                  # "{opportunity_id}:{node}:{tool}"
    opportunity_id: str
    node: str
    tool: str
    request_hash: str              # SHA-256 of request JSON (never raw request)
    response_hash: str             # SHA-256 of response JSON (never raw response)
    policy_decision: Literal["ALLOW", "REQUIRE_APPROVAL", "DENY"]
    latency_ms: int
    timestamp: datetime
```

**Note:** Raw request/response content is never stored. Only SHA-256 hashes, enabling audit verification without exposing sensitive data.

---

## Graph-Internal Types (`graph/types.py`)

These types are pipeline-internal and are not persisted to DynamoDB directly.

| Type | Purpose |
|------|---------|
| `GraphState` | Immutable-by-convention snapshot of all pipeline data; passed through every node |
| `IncidentHypothesis` | Working hypothesis produced by `incident_correlation` |
| `CaseOutcome` | Outcome returned by `case_monitor` |
| `PolicyDecision` | Enum: `ALLOW`, `REQUIRE_APPROVAL`, `DENY` |
| `ErrorDisposition` | Enum: `RETRY`, `FATAL` |
| `NodeContext` | Hook context for before/after node calls |
| `ToolContext` | Hook context for before/after tool calls |
| `DeterministicNode` | Pure-function graph node |
| `AgentNode` | LLM-backed graph node (with stub support) |
| `Edge` | Directed edge between two nodes |
| `ConditionalEdge` | Branching edge evaluated against live `GraphState` |
| `Graph` | Container that validates and executes the DAG |

---

## Validation Standards

All 9 models are validated with:

```bash
pytest tests/unit/ -W error::DeprecationWarning
```

- Zero `DeprecationWarning`s tolerated
- All `datetime` fields use timezone-aware types
- No `datetime.utcnow()` — replaced with `datetime.now(timezone.utc)`
- All `Decimal` fields use explicit `Decimal(str(v))` coercion, never `float`
