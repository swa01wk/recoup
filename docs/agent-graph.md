# Recoup — Agent Graph Reference

**File:** `backend/src/recoup/graph/`  
**Entry point:** `recoup_graph.build_recoup_graph()` → `Graph`  
**Node count:** 11 (4 Deterministic · 5 Agent · 2 Hybrid)  
**Status:** Phase 1 complete — all nodes have deterministic stubs; AgentNode stubs replaced by real Strands Agents in Phase 2

---

## Graph Overview

```
normalize_event (D)
    │
    ▼
incident_correlation (A) ──── CloudWatch · Health · CloudTrail
    │
    ▼
sla_contract_resolver (D) ──── sla_catalog/
    │
    ▼
availability_calculator (D) ──── pure Decimal math
    │
    ▼
evidence_collector (A) ──── CloudWatch · Logs · Cost · S3
    │
    ▼
evidence_sanitizer (D) ──── deterministic redaction
    │
    ▼
eligibility_reasoner (A) ──── reads evidence by ID only
    │
    ▼
risk_policy_gate (D) ──── Cedar policy
    │
    ├── REQUIRE_APPROVAL ──► await_human_approval (HITL pause)
    │                              │
    ├── ALLOW ─────────────────────┤
    │                              ▼
    └── DENY ──► terminal_denied  claim_package_generator (A)
                                   │
                                   ▼
                              submission_adapter (D)
                                   │
                                   ▼
                              case_monitor (A)
```

Legend: `(D)` = DeterministicNode · `(A)` = AgentNode · `HITL` = Human-in-the-Loop pause

---

## Node Type Reference

### `DeterministicNode`

```python
class DeterministicNode:
    name: str
    fn: Callable[[GraphState], dict[str, Any]]
    description: str
```

- Pure Python function, no LLM
- All financial arithmetic, policy evaluation, and state transitions live here
- 100% reproducible given the same inputs

### `AgentNode`

```python
class AgentNode:
    name: str
    tool_names: list[str]
    system_prompt: str
    description: str
    stub_fn: Callable[[GraphState], dict[str, Any]] | None
```

- Backed by Amazon Bedrock (Claude 3.5 Sonnet) via Strands
- Has a `stub_fn` for Phase 1 that returns deterministic typed data
- Phase 2 replaces `stub_fn` with a real `strands.Agent` call

---

## Node Specifications

### Node 1 — `normalize_event` (Deterministic)

**Purpose:** Parse a raw event payload (EventBridge, SQS, or replay seed) into a typed `IncidentSignal`. Generate an idempotency key.

| Attribute | Value |
|-----------|-------|
| Type | `DeterministicNode` |
| Tools | none |
| Input | `GraphState.signal` (pre-populated by ingestion layer or replay adapter) |
| Output | `idempotency_key: str` |
| Error | Appends to `state.errors` if `signal` is `None` |

**Idempotency key format:**
```
{event_id}:{service}:{region}
```

---

### Node 2 — `incident_correlation` (AgentNode)

**Purpose:** Correlate the incident signal against CloudWatch metrics, AWS Health events, and CloudTrail to form a working `IncidentHypothesis`.

| Attribute | Value |
|-----------|-------|
| Type | `AgentNode` |
| Tools | `get_cloudwatch_metrics`, `get_health_event`, `lookup_cloudtrail_events`, `get_cost_anomalies` |
| Input | `GraphState.signal` |
| Output | `hypothesis: IncidentHypothesis` |
| Stub behavior | Produces 6 bad intervals in 8,640 total → 99.9306% uptime, $18,400 billed, confidence=0.92 |

**System prompt (summarized):**
> You are a cloud reliability engineer analyzing an AWS incident. Correlate the signal with CloudWatch metrics, health events, and CloudTrail to form a hypothesis. Output ONLY factual observations. Never conclude financial eligibility.

**`IncidentHypothesis` fields:**
```python
service: str
region: str
incident_date: date
affected_resource_ids: list[str]
availability_intervals: list[AvailabilityInterval]
billed_charges: Decimal
confidence: float  # 0.0 – 1.0
summary: str
replay: bool
```

---

### Node 3 — `sla_contract_resolver` (Deterministic)

**Purpose:** Load the correct SLA contract from the local `sla_catalog/` directory for the service and incident date.

| Attribute | Value |
|-----------|-------|
| Type | `DeterministicNode` |
| Tools | none |
| Input | `GraphState.hypothesis` (service, region, incident_date) |
| Output | `contract: SLAContract` |
| Fatal error | `SLAContractNotFoundError` if no contract covers the incident date |

**Contract resolution:**
1. Normalizes service name via `_SERVICE_DIR_ALIASES` (e.g. `"API Gateway"` → `"apigateway"`)
2. Finds the highest-versioned YAML file with `effective_date ≤ incident_date`
3. Validates `source_hash` (SHA-256 of raw YAML) to detect tampering

---

### Node 4 — `availability_calculator` (Deterministic)

**Purpose:** Pure-arithmetic calculation of monthly uptime percentage and SLA credit using `Decimal` precision.

| Attribute | Value |
|-----------|-------|
| Type | `DeterministicNode` |
| Tools | none |
| Input | `GraphState.hypothesis` (intervals, billed_charges), `GraphState.contract` |
| Output | `availability_result: AvailabilityResult` |

**Formula:**
```
monthly_uptime_pct = (total_intervals - unavailable_intervals) / total_intervals × 100
threshold_breached = monthly_uptime_pct < contract.service_commitment
credit = billed_charges × tier_pct / 100   (if threshold_breached, else $0.00)
```

See [sla-calculator.md](sla-calculator.md) for the full formula reference and golden test spec.

---

### Node 5 — `evidence_collector` (AgentNode)

**Purpose:** Gather CloudWatch metrics, application logs, and billing records for the incident period. Store all raw evidence to the encrypted S3 evidence bucket before referencing it.

| Attribute | Value |
|-----------|-------|
| Type | `AgentNode` |
| Tools | `get_cloudwatch_metrics`, `query_cloudwatch_logs`, `get_cost_and_usage`, `store_evidence` |
| Input | `GraphState.hypothesis`, `GraphState.contract` |
| Output | `evidence_manifest: EvidenceManifest` |
| Stub behavior | Creates 3 evidence items (request_logs, error_logs, billing_record) with S3 URIs |

**System prompt (summarized):**
> Collect CloudWatch metrics, logs, and billing records for the incident period. Store all raw evidence to S3 before referencing it. Return only evidence IDs — never raw evidence content.

**Critical constraint:** The agent returns evidence IDs only. Raw content is never placed in agent context.

---

### Node 6 — `evidence_sanitizer` (Deterministic)

**Purpose:** Apply deterministic redaction rules to all evidence items. Produce a `RedactionReport` and a sanitized copy of the manifest.

| Attribute | Value |
|-----------|-------|
| Type | `DeterministicNode` |
| Tools | none |
| Input | `GraphState.evidence_manifest` |
| Output | `sanitized_manifest: EvidenceManifest`, `redaction_report: RedactionReport` |

**Redaction behavior:**
- Phase 1: Copies manifest to sanitized path, records 0 redactions
- Phase 3: Applies `_HIGH_RISK_PATTERNS` (account IDs, IPs, tokens, passwords) — fails closed on any HIGH_RISK match

**Fail-closed:** If a high-risk pattern remains after redaction, a `SanitizationError` is raised and the pipeline halts.

---

### Node 7 — `eligibility_reasoner` (AgentNode)

**Purpose:** Assess whether the claim meets all contractual requirements. The agent reads evidence by ID only — it never receives raw evidence content.

| Attribute | Value |
|-----------|-------|
| Type | `AgentNode` |
| Tools | none (read-only; no tool calls) |
| Input | `GraphState.contract`, `GraphState.availability_result`, `GraphState.sanitized_manifest` |
| Output | `eligibility_assessment: EligibilityAssessment` |
| Stub behavior | Returns eligible=True when `result.is_eligible` and `manifest.is_complete`, confidence=0.92 |

**System prompt (summarized):**
> Assess contractual eligibility using SLA contract terms, availability result, and evidence manifest. Reference evidence ONLY by ID. Never make financial conclusions — only assess contractual eligibility.

---

### Node 8 — `risk_policy_gate` (Deterministic)

**Purpose:** Evaluate risk and call AgentCore Policy (Cedar) for authorization. This is the sole branching node in the graph.

| Attribute | Value |
|-----------|-------|
| Type | `DeterministicNode` |
| Tools | `create_approval_request` (called if REQUIRE_APPROVAL) |
| Input | `GraphState.eligibility_assessment`, `GraphState.availability_result` |
| Output | `policy_decision: PolicyDecision` |

**Decision rules (in order):**
```
1. If not eligible → DENY
2. If eligible AND confidence ≥ 0.8 AND credit > $0 → REQUIRE_APPROVAL
3. Otherwise → DENY
```

**All financial mutations require explicit human approval.** There is no code path that submits a real claim without a valid `ApprovalRecord`.

**Conditional edge targets:**

| Decision | Next Node |
|---------|----------|
| `REQUIRE_APPROVAL` | `await_human_approval` (HITL pause) |
| `ALLOW` | `claim_package_generator` |
| `DENY` | `terminal_denied` (pipeline ends) |

---

### Node 9 — `claim_package_generator` (AgentNode)

**Purpose:** Assemble the complete `ClaimPackage` from the sanitized evidence manifest. Validates that all evidence IDs in the package body exist in the manifest (prevents invented references).

| Attribute | Value |
|-----------|-------|
| Type | `AgentNode` |
| Tools | `store_evidence` |
| Input | `GraphState.eligibility_assessment`, `GraphState.sanitized_manifest`, `GraphState.availability_result`, `GraphState.contract`, `GraphState.hypothesis` |
| Output | `claim_package: ClaimPackage` |

**System prompt (summarized):**
> Draft an AWS SLA credit claim. Use ONLY the evidence IDs from the sanitized manifest. Do not invent new evidence IDs. Format the claim body professionally and concisely.

---

### Node 10 — `submission_adapter` (Deterministic)

**Purpose:** Submit the `ClaimPackage` to AWS Support, or produce a simulated case ID if `simulation_mode=True`.

| Attribute | Value |
|-----------|-------|
| Type | `DeterministicNode` |
| Tools | `submit_support_case` / `simulate_support_case` |
| Input | `GraphState.claim_package`, `GraphState.approval_record`, `GraphState.simulation_mode` |
| Output | `case_id: str`, `submitted_at: datetime` |

**Submission gate:**
```python
if simulation_mode:
    case_id = "sim-" + sha256(package.calculator_result_hash)[:12]
    # No real AWS Support call
else:
    assert approval is not None and approval.is_valid
    # Real submission (Phase 2)
```

---

### Node 11 — `case_monitor` (AgentNode)

**Purpose:** Poll the AWS Support case for resolution status.

| Attribute | Value |
|-----------|-------|
| Type | `AgentNode` |
| Tools | `get_support_case_status` |
| Input | `GraphState.case_id` |
| Output | `case_outcome: CaseOutcome` |
| Stub behavior | Returns `status="PENDING"` |

---

## Special Pseudo-Nodes

| Name | Type | Description |
|------|------|-------------|
| `await_human_approval` | Terminal (external) | Graph pauses here; resumed by the HITL approval API endpoint when `ApprovalRecord.state == APPROVED` |
| `terminal_denied` | Terminal (final) | Pipeline ends; `PolicyDecision.DENY` is recorded |

---

## `GraphState` — Pipeline Data Contract

The `GraphState` is the immutable-by-convention snapshot of all accumulated data. Every node receives the full state and returns a dict of field updates to merge in.

```python
class GraphState(BaseModel):
    # Identity
    opportunity_id: str
    simulation_mode: bool = True

    # Node outputs (populated progressively)
    signal: IncidentSignal | None
    idempotency_key: str
    hypothesis: IncidentHypothesis | None
    contract: SLAContract | None
    availability_result: AvailabilityResult | None
    evidence_manifest: EvidenceManifest | None
    sanitized_manifest: EvidenceManifest | None
    redaction_report: RedactionReport | None
    eligibility_assessment: EligibilityAssessment | None
    policy_decision: PolicyDecision | None
    claim_package: ClaimPackage | None
    approval_record: ApprovalRecord | None
    case_id: str | None
    submitted_at: datetime | None
    case_outcome: CaseOutcome | None

    # Diagnostics
    errors: list[str]
    current_state: OpportunityState
    state_version: int
```

---

## Graph Validation

The `Graph.validate()` method is called at build time and at import time (via the module-level `recoup_graph = build_recoup_graph()`). It raises `ValueError` immediately if any edge endpoint references an unknown node name, providing fail-fast detection of configuration errors.

---

## Phase 2 Upgrade Path

To replace a stub with a real Strands Agent:

```python
# Phase 1 (stub):
incident_correlation = AgentNode(
    name="incident_correlation",
    tool_names=["get_cloudwatch_metrics", "get_health_event"],
    stub_fn=incident_correlation_stub,
)

# Phase 2 (real agent):
from strands import Agent
from ..tools.registry import TOOL_REGISTRY

incident_correlation = AgentNode(
    name="incident_correlation",
    tool_names=["get_cloudwatch_metrics", "get_health_event"],
    # stub_fn=None  ← remove the stub
    agent=Agent(
        tools=[TOOL_REGISTRY[t].fn for t in ["get_cloudwatch_metrics", "get_health_event"]],
        system_prompt=incident_correlation.system_prompt,
    ),
)
```
