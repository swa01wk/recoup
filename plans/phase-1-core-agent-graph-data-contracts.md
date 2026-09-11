# Phase 1 — Core Agent Graph & Data Contracts

> **Historical implementation plan.** Targets below reflect mid-build intent. **Current product & metrics:** [docs/README.md](../docs/README.md) · [STATUS.md](../STATUS.md) · [docs/judge-demo.md](../docs/judge-demo.md).



**Timeline:** Day 3–6 (Target: by Sep 6, 2026)  
**Status:** `[x] Complete — Sep 1, 2026`  
**Depends on:** Phase 0 complete

---

## Objective

Implement the Strands Graph skeleton with all nodes defined, wire data contracts and domain models, build the SLA catalog, register all tool schemas with AgentCore Gateway, and define the state machine. By the end of this phase, the agent graph can be invoked end-to-end with stubbed node implementations, passing typed data between nodes without errors.

---

## Goals

- [ ] All 11 Strands Graph nodes defined with input/output type annotations
- [ ] Domain models (`RecoveryOpportunity`, `IncidentSignal`, `SLAContract`, `AvailabilityResult`, `EvidenceItem`, `EligibilityAssessment`, `ApprovalRecord`, `ClaimPackage`, `ToolAudit`) fully typed
- [ ] SLA catalog committed with API Gateway 2022-05-05 contract and CI validation
- [ ] All tool contracts registered with AgentCore Gateway (schemas, action classes, targets)
- [ ] State machine transitions implemented in DynamoDB with atomic version increments
- [ ] Strands hooks skeleton in place (BeforeNodeCall, AfterNodeCall, BeforeToolCall, AfterToolCall, Error, Redaction)
- [ ] End-to-end graph invocation with stubs passes without schema errors
- [ ] Unit tests for all domain model validations pass

---

## Workstreams

### 1.1 Domain Models

**Location:** `backend/src/recoup/models/`

All models use Pydantic v2 for validation and serialization.

```python
# models/opportunity.py
class RecoveryOpportunity(BaseModel):
    id: str                          # UUID
    type: Literal["SLA", "ANOMALY", "OPTIMIZATION"]
    account_id_masked: str           # last 4 digits only
    service: str                     # e.g., "apigateway"
    region: str
    discovered_at: datetime
    potential_value: Decimal
    confidence: float                # 0.0–1.0
    state: OpportunityState
    simulation_mode: bool = True     # default true; require explicit false for real actions
    state_version: int = 0

# models/signal.py
class IncidentSignal(BaseModel):
    source: Literal["aws_health", "cost_anomaly", "optimization", "replay"]
    event_id: str
    service: str
    region: str
    start: datetime
    end: datetime
    affected_resource_ids: list[str]
    raw_ref: str                     # S3 URI to raw event; never the raw event itself

# models/sla.py
class CreditTier(BaseModel):
    min_pct: Decimal
    max_exclusive_pct: Decimal
    credit_pct: Decimal

class SLAContract(BaseModel):
    service: str
    version: str
    effective_from: date
    effective_to: Optional[date]
    service_commitment: Decimal       # e.g., Decimal("99.95")
    interval_minutes: int             # e.g., 5
    claim_deadline_rule: str
    credit_tiers: list[CreditTier]
    required_claim_fields: list[str]
    exclusions: list[str]
    source_url: str
    source_hash: str                  # SHA-256 of the source document

# models/availability.py
class AvailabilityInterval(BaseModel):
    start: datetime
    end: datetime
    availability_pct: Decimal
    request_count: int
    error_count: int
    evidence_refs: list[str]

class AvailabilityResult(BaseModel):
    monthly_uptime_pct: Decimal
    threshold_breached: bool
    tier_pct: Decimal
    billed_charges: Decimal
    potential_credit: Decimal
    calculation_trace: list[str]     # human-readable arithmetic steps

# models/evidence.py
class EvidenceItem(BaseModel):
    id: str
    type: Literal["metric", "log", "health_event", "billing_record", "contract"]
    source: str
    timestamp_range: tuple[datetime, datetime]
    storage_uri: str                 # S3 URI of raw evidence
    sanitized_uri: Optional[str]     # S3 URI of sanitized version
    hash: str
    sensitivity: Literal["LOW", "MEDIUM", "HIGH"]
    status: Literal["FOUND", "MISSING", "REDACTED"]

class EvidenceManifest(BaseModel):
    opportunity_id: str
    items: list[EvidenceItem]
    missing_fields: list[str]
    redaction_report: RedactionReport

# models/eligibility.py
class EligibilityAssessment(BaseModel):
    eligible_estimate: bool
    confidence: float
    satisfied_requirements: list[str]
    unresolved: list[str]
    possible_exclusions: list[str]
    evidence_refs: list[str]         # must be IDs from EvidenceManifest only

# models/approval.py
class ApprovalRecord(BaseModel):
    approval_id: str
    principal: str
    action: str
    amount: Decimal
    claim_hash: str
    opportunity_id: str
    state_version: int               # bound to exact state version
    timestamp: datetime
    expires_at: datetime
    state: Literal["PENDING", "APPROVED", "EXPIRED", "REVOKED"]

# models/claim.py
class ClaimPackage(BaseModel):
    opportunity_id: str
    subject: str
    body: str
    region: str
    billing_cycle: str
    resources: list[str]
    evidence_manifest: EvidenceManifest
    calculator_result_hash: str      # SHA-256 of AvailabilityResult JSON

# models/audit.py
class ToolAudit(BaseModel):
    trace_id: str
    opportunity_id: str
    node: str
    tool: str
    request_hash: str
    response_hash: str
    policy_decision: Literal["ALLOW", "REQUIRE_APPROVAL", "DENY"]
    latency_ms: int
    timestamp: datetime
```

### 1.2 State Machine

**States and transitions:**

```
DETECTED
  → INVESTIGATING          (on: event normalized + correlation started)

INVESTIGATING
  → EVIDENCE_READY         (on: evidence collection complete)
  → NEEDS_EVIDENCE         (on: required fields missing)

NEEDS_EVIDENCE
  → INVESTIGATING          (on: retry or partial evidence found)

EVIDENCE_READY
  → ELIGIBILITY_REVIEWED   (on: eligibility assessment complete)

ELIGIBILITY_REVIEWED
  → AWAITING_APPROVAL      (on: eligible + risk gate passes → REQUIRE_APPROVAL)
  → DENIED                 (on: risk gate → DENY)
  → FAILED                 (on: unrecoverable error)

AWAITING_APPROVAL
  → APPROVED               (on: human approves via Decision Inbox)
  → DENIED                 (on: human declines or approval expires)

APPROVED
  → SUBMITTING             (on: submission adapter called)

SUBMITTING
  → SUBMITTED              (on: case id returned — real or replay)
  → FAILED                 (on: submission error)

SUBMITTED
  → MONITORING             (on: case monitor started)

MONITORING
  → RECOVERED              (on: credit confirmed)
  → REJECTED               (on: AWS denies claim)
  → NEEDS_FOLLOWUP         (on: more info requested)
```

**DynamoDB write pattern:**
```python
# Atomic conditional write; prevents race conditions
table.update_item(
    Key={"id": opportunity_id},
    UpdateExpression="SET #state = :new_state, state_version = state_version + :inc",
    ConditionExpression="state_version = :expected_version",
    ExpressionAttributeValues={
        ":new_state": new_state,
        ":inc": 1,
        ":expected_version": current_version,
    }
)
```

### 1.3 Strands Graph Definition

**Location:** `backend/src/recoup/graph/`

```python
# graph/recoup_graph.py
from strands import Graph, AgentNode, DeterministicNode

recoup_graph = Graph(name="recoup-recovery")

# Node 1: Normalize Event (Deterministic)
normalize_event = DeterministicNode(
    name="normalize_event",
    fn=normalize_event_fn,
    inputs=["raw_event"],
    outputs=["signal: IncidentSignal", "idempotency_key: str"],
)

# Node 2: Incident Correlation (Agent)
incident_correlation = AgentNode(
    name="incident_correlation",
    tools=["get_cloudwatch_metrics", "get_health_event", "lookup_cloudtrail_events"],
    outputs=["hypothesis: IncidentHypothesis"],
    # Agent node: produces hypothesis; never concludes financial eligibility
)

# Node 3: SLA Contract Resolver (Deterministic/Tool)
sla_contract_resolver = DeterministicNode(
    name="sla_contract_resolver",
    fn=resolve_sla_contract,
    inputs=["service", "region", "incident_date"],
    outputs=["contract: SLAContract"],
)

# Node 4: Availability & Credit Calculator (Deterministic)
availability_calculator = DeterministicNode(
    name="availability_calculator",
    fn=calculate_availability_and_credit,
    inputs=["intervals: list[AvailabilityInterval]", "contract: SLAContract", "billed_charges: Decimal"],
    outputs=["result: AvailabilityResult"],
    # No LLM involvement; pure arithmetic
)

# Node 5: Evidence Collector (Agent)
evidence_collector = AgentNode(
    name="evidence_collector",
    tools=["get_cloudwatch_metrics", "query_cloudwatch_logs", "get_cost_and_usage", "store_evidence"],
    inputs=["contract: SLAContract", "hypothesis: IncidentHypothesis"],
    outputs=["manifest: EvidenceManifest"],
)

# Node 6: Evidence Sanitizer (Deterministic)
evidence_sanitizer = DeterministicNode(
    name="evidence_sanitizer",
    fn=sanitize_evidence,
    inputs=["manifest: EvidenceManifest"],
    outputs=["sanitized_manifest: EvidenceManifest", "redaction_report: RedactionReport"],
    # Fail closed: raises SanitizationError if high-risk pattern detected after redaction
)

# Node 7: Eligibility Reasoner (Agent)
eligibility_reasoner = AgentNode(
    name="eligibility_reasoner",
    tools=[],  # Read-only; references evidence by ID only
    inputs=["contract: SLAContract", "result: AvailabilityResult", "sanitized_manifest: EvidenceManifest"],
    outputs=["assessment: EligibilityAssessment"],
)

# Node 8: Risk / Policy Gate (Deterministic + AgentCore Policy)
risk_policy_gate = DeterministicNode(
    name="risk_policy_gate",
    fn=evaluate_risk_and_policy,
    inputs=["assessment: EligibilityAssessment", "result: AvailabilityResult", "session_context"],
    outputs=["decision: PolicyDecision"],
    # Calls AgentCore Policy for Cedar evaluation
)

# Node 9: Claim Package Generator (Agent + Template)
claim_package_generator = AgentNode(
    name="claim_package_generator",
    tools=["store_evidence"],
    inputs=["assessment: EligibilityAssessment", "sanitized_manifest: EvidenceManifest"],
    outputs=["package: ClaimPackage"],
    # Validator rejects any evidence_id not in sanitized_manifest
)

# Node 10: Submission Adapter (Tool)
submission_adapter = DeterministicNode(
    name="submission_adapter",
    fn=submit_or_simulate,
    inputs=["package: ClaimPackage", "approval: ApprovalRecord"],
    outputs=["case_id: str", "submitted_at: datetime"],
    # Routes to real or replay adapter based on simulation_mode + approval + policy
)

# Node 11: Case Monitor (Agent/Tool)
case_monitor = AgentNode(
    name="case_monitor",
    tools=["get_support_case_status"],
    inputs=["case_id: str"],
    outputs=["outcome: CaseOutcome"],
)

# Graph edges
recoup_graph.add_edge(normalize_event, incident_correlation)
recoup_graph.add_edge(incident_correlation, sla_contract_resolver)
recoup_graph.add_edge(incident_correlation, availability_calculator)
recoup_graph.add_edge(sla_contract_resolver, availability_calculator)
recoup_graph.add_edge(availability_calculator, evidence_collector)
recoup_graph.add_edge(evidence_collector, evidence_sanitizer)
recoup_graph.add_edge(evidence_sanitizer, eligibility_reasoner)
recoup_graph.add_edge(eligibility_reasoner, risk_policy_gate)
recoup_graph.add_conditional_edge(
    risk_policy_gate,
    condition=lambda d: d.decision,
    targets={
        "REQUIRE_APPROVAL": "await_human_approval",    # pause; resume on approval
        "ALLOW": claim_package_generator,
        "DENY": "terminal_denied",
    }
)
recoup_graph.add_edge("await_human_approval", claim_package_generator)
recoup_graph.add_edge(claim_package_generator, submission_adapter)
recoup_graph.add_edge(submission_adapter, case_monitor)
```

### 1.4 Strands Hooks

**Location:** `backend/src/recoup/hooks/`

```python
# hooks/tracing.py
class RecoupTracingHooks:
    def before_node_call(self, ctx: NodeContext) -> None:
        # Start trace span; enforce state preconditions
        span = tracer.start_span(ctx.node_name)
        span.set_attribute("opportunity_id", ctx.state["opportunity_id"])
        span.set_attribute("state_version", ctx.state["state_version"])

    def after_node_call(self, ctx: NodeContext, result: Any) -> None:
        # Persist node result summary and duration
        span.set_attribute("status", "success")
        span.set_attribute("duration_ms", ctx.duration_ms)

    def before_tool_call(self, ctx: ToolContext) -> None:
        # Validate tool against allowlist; attach policy/session context
        assert ctx.tool_name in ALLOWED_TOOLS_FOR_NODE[ctx.node_name]
        ctx.inject("opportunity_id", ctx.state["opportunity_id"])
        ctx.inject("session_principal", ctx.session.principal)

    def after_tool_call(self, ctx: ToolContext, result: Any) -> None:
        # Record result hash, latency, evidence ids — never raw evidence
        audit = ToolAudit(
            tool=ctx.tool_name,
            request_hash=sha256(ctx.request_json),
            response_hash=sha256(ctx.response_json),
            policy_decision=ctx.policy_decision,
            latency_ms=ctx.duration_ms,
        )
        save_tool_audit(audit)

    def on_error(self, ctx: NodeContext, error: Exception) -> ErrorDisposition:
        # Classify: retryable vs fatal; preserve diagnostic trace
        if isinstance(error, ThrottlingError):
            return ErrorDisposition.RETRY
        return ErrorDisposition.FATAL

    def custom_redaction_hook(self, ctx: TraceContext, value: str) -> str:
        # Ensure no raw sensitive evidence enters user-visible trace
        if HIGH_RISK_PATTERN.search(value):
            ctx.increment("redaction_count")
            return "[REDACTED]"
        return value
```

### 1.5 SLA Catalog

**Location:** `sla_catalog/`

```yaml
# sla_catalog/api_gateway/2022-05-05.yaml
service: apigateway
version: "2022-05-05"
effective_from: "2022-05-05"
effective_to: null
service_commitment: "99.95"
interval_minutes: 5
claim_deadline_rule: "end_of_second_billing_cycle_after_incident"
credit_tiers:
  - min_pct: "99.00"
    max_exclusive_pct: "99.95"
    credit_pct: 10
  - min_pct: "95.00"
    max_exclusive_pct: "99.00"
    credit_pct: 25
  - min_pct: "0.00"
    max_exclusive_pct: "95.00"
    credit_pct: 100
required_claim_fields:
  - api_id
  - region
  - billing_cycle
  - request_logs
  - error_logs
  - billing_record
exclusions:
  - customer_caused_errors
  - backend_lambda_failures
  - planned_maintenance
source_url: "https://aws.amazon.com/api-gateway/sla/"
source_hash: "sha256:..."       # must be populated by CI
```

**CI validation test:**
```python
def test_sla_catalog_has_source_hash():
    for contract in load_all_contracts():
        assert contract.source_hash.startswith("sha256:"), \
            f"Contract {contract.service}/{contract.version} missing source hash"
        assert contract.source_url, \
            f"Contract {contract.service}/{contract.version} missing source URL"
```

### 1.6 Tool Registry

**Location:** `backend/src/recoup/tools/`

All tools are narrow, typed, and registered via AgentCore Gateway. No raw boto3 clients exposed to agents.

| Tool | Action Class | Lambda target | Allowed nodes |
|------|-------------|--------------|---------------|
| `get_cloudwatch_metrics` | READ | `recoup-cw-tool` | incident_correlation, evidence_collector |
| `query_cloudwatch_logs` | READ_SENSITIVE | `recoup-cw-logs-tool` | evidence_collector |
| `get_health_event` | READ | `recoup-health-tool` | incident_correlation |
| `get_cost_and_usage` | READ_FINANCIAL | `recoup-cost-tool` | evidence_collector |
| `get_cost_anomalies` | READ_FINANCIAL | `recoup-cost-tool` | incident_correlation |
| `list_cost_optimization_recommendations` | READ_FINANCIAL | `recoup-cost-tool` | incident_correlation |
| `lookup_cloudtrail_events` | READ_SENSITIVE | `recoup-cloudtrail-tool` | incident_correlation |
| `store_evidence` | WRITE_INTERNAL | `recoup-evidence-tool` | evidence_collector, claim_package_generator |
| `create_approval_request` | WRITE_INTERNAL | `recoup-approval-tool` | risk_policy_gate |
| `submit_support_case` | WRITE_EXTERNAL_FINANCIAL | `recoup-support-tool` | submission_adapter |
| `simulate_support_case` | WRITE_INTERNAL | `recoup-simulate-tool` | submission_adapter |
| `stop_demo_instance` | MUTATE_RED | `recoup-ec2-demo-tool` | (Phase 6 only) |

---

## Definition of Done

| Check | Criteria |
|-------|----------|
| Domain models | All models import, instantiate, and validate without errors |
| Graph | Graph can be instantiated; all edges resolve to valid node names |
| State machine | Atomic DynamoDB transition tested with optimistic locking |
| SLA catalog | API Gateway contract loads; CI test for source_hash passes |
| Tool registry | All 10 tools registered in Gateway with schema validation |
| Hooks | Hook skeleton fires on stub node calls without errors |
| Unit tests | 100% pass; no LLM calls in unit tests |

---

## Post-Implementation Documentation

> Created in `plans/docs/` after phase completion.

- `docs/data-models.md` — Full domain model reference with field descriptions and validation rules
- `docs/strands-graph.md` — Graph topology, node responsibilities, conditional edges, and hook points
- `docs/sla-catalog.md` — How to add new SLA contracts, validation requirements, and CI checks
- `docs/tool-registry.md` — Complete tool inventory with schemas, action classes, and allowed nodes
- `docs/state-machine.md` — State transition diagram, DynamoDB write patterns, and idempotency design

---

## Risks

| Risk | Mitigation |
|------|-----------|
| Strands API changes | Pin Strands version; run integration tests on each upgrade |
| AgentCore tool registration complexity | Build a CLI helper script for tool registration |
| Model produces financial conclusions | Strict system prompt constraints; deterministic nodes own all financial math |
| State version race condition | Optimistic locking with `ConditionExpression` on every write |
