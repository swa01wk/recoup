# Recoup — Tool Registry Reference

**File:** `backend/src/recoup/tools/registry.py`  
**Total tools:** 13  
**Last updated:** Sep 11, 2026  
**Status:** All 13 tools have typed signatures and are registered in `TOOL_REGISTRY`  
**Playwright tests:** `journey-quality-gates.spec.ts` J8 verifies `unsafe_external_actions=0` (no destructive tools called).

---

## Overview

The `TOOL_REGISTRY` is the single source of truth for every tool in the system. It maps each tool name to:
- **Action class** — authorization tier that Cedar policy evaluates
- **Lambda target** — the Lambda function name for AgentCore Gateway routing
- **Allowed nodes** — the set of graph nodes that may call this tool (enforced by `RecoupTracingHooks.before_tool_call`)
- **Function** — the callable implementation decorated with `@tool` (for Strands schema generation)

```python
@dataclass(frozen=True)
class ToolMeta:
    name: str
    action_class: str
    lambda_target: str
    allowed_nodes: frozenset[str]
    fn: Callable[..., Any]
    description: str
```

---

## Action Classes

| Class | Risk Level | Description |
|-------|-----------|-------------|
| `READ` | Lowest | Public or non-sensitive AWS data (metrics, health events, support case status) |
| `READ_SENSITIVE` | Low | Data that may contain PII or secrets (logs, CloudTrail events) |
| `READ_FINANCIAL` | Medium | Billing and cost data |
| `WRITE_INTERNAL` | Medium | Writes to Recoup's own infrastructure (S3, DynamoDB) — never external |
| `WRITE_EXTERNAL_FINANCIAL` | High | External financial action (AWS Support case submission) — requires approval |
| `MUTATE_RED` | Highest | Irreversible infrastructure action (EC2 stop) — requires approval + Cedar + allowlist |

All classes except `READ` are evaluated by AgentCore Policy (Cedar). Default Cedar policy: **deny**.

---

## Complete Tool Inventory

### AWS Tools (`tools/aws_tools.py`)

#### 1. `get_cloudwatch_metrics`

| Attribute | Value |
|-----------|-------|
| Action class | `READ` |
| Lambda | `recoup-cw-tool` |
| Allowed nodes | `incident_correlation`, `evidence_collector` |

```python
def get_cloudwatch_metrics(
    namespace: str,           # e.g. "AWS/ApiGateway"
    metric_name: str,         # e.g. "5XXError"
    dimensions: list[dict],   # [{Name, Value}]
    start_time: str,          # ISO-8601
    end_time: str,            # ISO-8601
    period_seconds: int = 300,
    stat: str = "Sum",
) -> {"datapoints": [{timestamp, value, unit}], "label": str}
```

Phase 1 returns a single stub datapoint. Phase 2 calls `cloudwatch:GetMetricStatistics`.

---

#### 2. `query_cloudwatch_logs`

| Attribute | Value |
|-----------|-------|
| Action class | `READ_SENSITIVE` |
| Lambda | `recoup-cw-logs-tool` |
| Allowed nodes | `evidence_collector` |

```python
def query_cloudwatch_logs(
    log_group_name: str,
    query_string: str,     # CloudWatch Logs Insights query
    start_time: str,
    end_time: str,
    limit: int = 100,      # max 10,000
) -> {"results": list[dict], "status": "Complete"|"Running"|"Failed"}
```

**Note:** Raw log content is never returned directly. Queries must use `fields` to select specific structured fields only.

---

#### 3. `get_health_event`

| Attribute | Value |
|-----------|-------|
| Action class | `READ` |
| Lambda | `recoup-health-tool` |
| Allowed nodes | `incident_correlation` |

```python
def get_health_event(
    service: str,                   # e.g. "apigateway"
    region: str,
    event_arn: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> {"events": [{arn, service, region, startTime, endTime, statusCode}]}
```

Phase 2 calls `health:DescribeEvents` + `health:DescribeEventDetails`.

---

#### 4. `get_cost_and_usage`

| Attribute | Value |
|-----------|-------|
| Action class | `READ_FINANCIAL` |
| Lambda | `recoup-cost-tool` |
| Allowed nodes | `evidence_collector` |

```python
def get_cost_and_usage(
    service: str,               # e.g. "Amazon API Gateway"
    region: str,
    start_date: str,            # YYYY-MM-DD
    end_date: str,              # YYYY-MM-DD, exclusive
    granularity: str = "MONTHLY",
) -> {"results": [{start, end, total_usd}]}
```

Phase 1 stub returns `total_usd: "3.51"` (the canonical golden scenario value). Phase 2 calls `ce:GetCostAndUsage`.

---

#### 5. `get_cost_anomalies`

| Attribute | Value |
|-----------|-------|
| Action class | `READ_FINANCIAL` |
| Lambda | `recoup-cost-tool` |
| Allowed nodes | `incident_correlation` |

```python
def get_cost_anomalies(
    service: str,
    start_date: str,
    end_date: str,
    min_impact_usd: float = 100.0,
) -> {"anomalies": [{id, service, region, start_date, end_date, impact_usd}]}
```

Phase 2 calls `ce:GetAnomalies`.

---

#### 6. `list_cost_optimization_recommendations`

| Attribute | Value |
|-----------|-------|
| Action class | `READ_FINANCIAL` |
| Lambda | `recoup-cost-tool` |
| Allowed nodes | `incident_correlation` |

```python
def list_cost_optimization_recommendations(
    service: str | None = None,
    region: str | None = None,
) -> {"recommendations": [{id, service, region, estimated_savings_usd, action}]}
```

Phase 2 calls `ce:GetRecommendations` via Cost Optimization Hub.

---

#### 7. `lookup_cloudtrail_events`

| Attribute | Value |
|-----------|-------|
| Action class | `READ_SENSITIVE` |
| Lambda | `recoup-cloudtrail-tool` |
| Allowed nodes | `incident_correlation` |

```python
def lookup_cloudtrail_events(
    resource_id: str,
    start_time: str,
    end_time: str,
    event_names: list[str] | None = None,
) -> {"events": [{event_name, event_time, user_identity_type, request_id}]}
```

**Sensitive field exclusion:** Response omits all raw request/response parameters. Only event metadata is returned. Phase 2 calls `cloudtrail:LookupEvents`.

---

#### 8. `get_support_case_status`

| Attribute | Value |
|-----------|-------|
| Action class | `READ` |
| Lambda | `recoup-support-tool` |
| Allowed nodes | `case_monitor` |

```python
def get_support_case_status(
    case_id: str,
) -> {"case_id", "status", "subject", "created_at", "resolved_at", "communications"}
```

Phase 2 calls `support:DescribeCases`.

---

### Internal Tools (`tools/internal_tools.py`)

#### 9. `store_evidence`

| Attribute | Value |
|-----------|-------|
| Action class | `WRITE_INTERNAL` |
| Lambda | `recoup-evidence-tool` |
| Allowed nodes | `evidence_collector`, `claim_package_generator` |

```python
def store_evidence(
    opportunity_id: str,
    field_name: str,         # e.g. "request_logs", "billing_record"
    content_json: str,       # serialized evidence content
    sensitivity: str = "MEDIUM",
) -> {"evidence_id", "storage_uri", "hash", "stored_at"}
```

Raw content is stored to `s3://recoup-evidence/{opportunity_id}/{field_name}.json` (KMS encrypted). The agent only receives the `evidence_id` back — never the stored content.

---

#### 10. `create_approval_request`

| Attribute | Value |
|-----------|-------|
| Action class | `WRITE_INTERNAL` |
| Lambda | `recoup-approval-tool` |
| Allowed nodes | `risk_policy_gate` |

```python
def create_approval_request(
    opportunity_id: str,
    principal: str,
    action: str,
    amount_usd: str,
    claim_hash: str,        # SHA-256 of ClaimPackage JSON
    state_version: int,     # bound to this exact version
    ttl_hours: int = 24,
) -> {"approval_id", "state", "expires_at", "approval_url"}
```

Creates a `PENDING` `ApprovalRecord` in DynamoDB with a TTL. The `claim_hash` + `state_version` binding ensures a stale approval cannot be used if the opportunity changes.

---

#### 11. `submit_support_case`

| Attribute | Value |
|-----------|-------|
| Action class | `WRITE_EXTERNAL_FINANCIAL` |
| Lambda | `recoup-support-tool` |
| Allowed nodes | `submission_adapter` |

Phase 1 backing function: `simulate_support_case` (real implementation wired in Phase 2). Requires:
- `recoup_enable_real_support_submission == True` (config flag)
- Valid, unexpired `ApprovalRecord`
- AgentCore Policy Cedar ALLOW

---

#### 12. `simulate_support_case`

| Attribute | Value |
|-----------|-------|
| Action class | `WRITE_INTERNAL` |
| Lambda | `recoup-simulate-tool` |
| Allowed nodes | `submission_adapter` |

```python
def simulate_support_case(
    opportunity_id: str,
    claim_subject: str,
    billing_cycle: str,
    potential_credit_usd: str,
    calculator_result_hash: str,   # determines the deterministic case_id
) -> {"case_id", "simulated": True, "submitted_at", "subject", "status"}
```

Produces a deterministic case ID: `"sim-" + sha256(calculator_result_hash)[:12]` when this **tool** is invoked. The graph **`submission_adapter` node** (canonical replay) uses `"replay-" + hash[:12]` instead — see [agent-graph.md](agent-graph.md).

---

### EC2 Tool (`tools/ec2_tools.py`)

#### 13. `stop_demo_instance`

| Attribute | Value |
|-----------|-------|
| Action class | `MUTATE_RED` |
| Lambda | `recoup-ec2-demo-tool` |
| Allowed nodes | _(none in standard graph — Phase 6 only)_ |

```python
def stop_demo_instance(
    instance_id: str,       # must be in RECOUP_DEMO_INSTANCE_ALLOWLIST
    opportunity_id: str,
    approval_id: str,       # must reference a valid ApprovalRecord
    reason: str = "Recoup cost-optimization demo",
) -> {"instance_id", "previous_state", "current_state", "stopped_at", "simulated"}
```

**All safety gates must pass before execution:**
1. `instance_id` in `RECOUP_DEMO_INSTANCE_ALLOWLIST` env var
2. `approval_id` references a valid, unexpired `ApprovalRecord`
3. AgentCore Policy Cedar rule confirms `RecoupDemo=true` tag
4. CloudWatch confirms CPU < 5% for 30 minutes (idle check)
5. CloudTrail confirms no recent blocking changes

Phase 1/simulation: always returns stub with `simulated: true`. Phase 6: real `ec2:StopInstances` call.

---

#### 13. `stop_demo_instance` (Phase 6 EC2 demo — outside standard graph)

`allowed_nodes` is empty — not invoked from the 11-node SLA graph. Called from `/api/ec2-demo/execute` after HITL approval.

---

## Tool Allowlist Enforcement

The `RecoupTracingHooks.before_tool_call` method enforces allowlists at runtime:

```python
def before_tool_call(self, ctx: ToolContext) -> None:
    allowed = ALLOWED_TOOLS_FOR_NODE.get(ctx.node_name, frozenset())
    if allowed and ctx.tool_name not in allowed:
        raise PermissionError(
            f"Tool '{ctx.tool_name}' is not allowed for node '{ctx.node_name}'."
        )
```

A `PermissionError` is raised before any tool executes if the calling node is not in the tool's `allowed_nodes` set. This is defense-in-depth against prompt injection or unexpected LLM behavior.

---

## Node-to-Tool Mapping (Summary)

| Node | Allowed tools |
|------|-------------|
| `normalize_event` | _(none)_ |
| `incident_correlation` | `get_cloudwatch_metrics`, `get_health_event`, `lookup_cloudtrail_events`, `get_cost_anomalies`, `list_cost_optimization_recommendations` (registry); tracing hooks may allow a subset — see `hooks/tracing.py` |
| `sla_contract_resolver` | _(none)_ |
| `availability_calculator` | _(none)_ |
| `evidence_collector` | `get_cloudwatch_metrics`, `query_cloudwatch_logs`, `get_cost_and_usage`, `store_evidence` |
| `evidence_sanitizer` | _(none)_ |
| `eligibility_reasoner` | _(none — read-only)_ |
| `risk_policy_gate` | _(none at runtime — Cedar in `nodes.py`; `create_approval_request` registered but graph node does not call it)_ |
| `claim_package_generator` | `store_evidence` |
| `submission_adapter` | _(none at runtime — produces `replay-` case IDs; registry lists submit/simulate for Gateway)_ |
| `case_monitor` | `get_support_case_status` |
