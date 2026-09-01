# Recoup — Tracing Hooks Reference

**File:** `backend/src/recoup/hooks/tracing.py`  
**Class:** `RecoupTracingHooks`  
**Status:** Phase 1 complete — all 6 hook types implemented; DynamoDB writes + X-Ray spans are no-ops without credentials

---

## Overview

`RecoupTracingHooks` provides lifecycle hooks that fire around every graph node and every tool call. The hooks serve four purposes:

1. **Tracing** — Open/close X-Ray trace spans for every node and tool
2. **Allowlist enforcement** — Prevent any tool from being called by a node that isn't allowed to use it
3. **Audit logging** — Write a `ToolAudit` record to DynamoDB after every tool call (request/response as SHA-256 hashes only)
4. **Redaction** — Strip high-risk patterns (account IDs, credentials, IPs) from user-visible trace output

---

## Usage

```python
from recoup.hooks.tracing import RecoupTracingHooks
from recoup.graph.types import NodeContext, ToolContext

hooks = RecoupTracingHooks(
    opportunity_id="opp-replay-001",
    principal="ops-team",
    simulation_mode=True,
)

# Before a node runs
ctx = NodeContext(node_name="normalize_event", state=state.model_dump())
hooks.before_node_call(ctx)

# Run the node
result = node.run(state)

# After a node runs
hooks.after_node_call(ctx, result)

# Before a tool is called
tool_ctx = ToolContext(
    tool_name="get_cloudwatch_metrics",
    node_name="incident_correlation",
    state=state.model_dump(),
    request_json='{"namespace": "AWS/ApiGateway", ...}',
)
hooks.before_tool_call(tool_ctx)

# Call the tool
response = get_cloudwatch_metrics(...)

# After a tool is called
tool_ctx.response_json = json.dumps(response)
hooks.after_tool_call(tool_ctx, response)
```

---

## Hook Types

### `before_node_call(ctx: NodeContext) → None`

Fires immediately before a graph node executes.

**Validates:**
- `opportunity_id` in the state matches the hooks instance (raises `RuntimeError` on mismatch)

**Emits:**
```json
{
  "event": "node.start",
  "node": "normalize_event",
  "opportunity_id": "opp-replay-001",
  "state_version": 0
}
```

---

### `after_node_call(ctx: NodeContext, result: Any) → None`

Fires immediately after a graph node returns.

**Emits:**
```json
{
  "event": "node.complete",
  "node": "normalize_event",
  "opportunity_id": "opp-replay-001",
  "duration_ms": 12
}
```

---

### `before_tool_call(ctx: ToolContext) → None`

Fires before any tool is invoked by an AgentNode. This is the **primary security checkpoint**.

**Validates:**
- `ctx.tool_name` is in `ALLOWED_TOOLS_FOR_NODE[ctx.node_name]`
- Raises `PermissionError` if the tool is not in the allowlist

**Injects context into the tool call:**
```python
ctx.inject("opportunity_id", self._opportunity_id)
ctx.inject("session_principal", self._principal)
ctx.inject("simulation_mode", self._simulation_mode)
```

**Emits:**
```json
{
  "event": "tool.start",
  "tool": "get_cloudwatch_metrics",
  "node": "incident_correlation",
  "opportunity_id": "opp-replay-001"
}
```

---

### `after_tool_call(ctx: ToolContext, result: Any) → None`

Fires after a tool returns. Writes a `ToolAudit` record.

**Creates `ToolAudit`:**
```python
ToolAudit(
    trace_id=f"{opportunity_id}:{node}:{tool}",
    opportunity_id=opportunity_id,
    node=ctx.node_name,
    tool=ctx.tool_name,
    request_hash=sha256_json(ctx.request_json),   # hash only, never raw
    response_hash=sha256_json(ctx.response_json),  # hash only, never raw
    policy_decision=ctx.policy_decision,
    latency_ms=ctx.duration_ms,
    timestamp=utcnow(),
)
```

The `ToolAudit` is persisted to DynamoDB (`recoup-tool-audits` table). If DynamoDB is unavailable, the write failure is logged as a warning and execution continues.

**Emits:**
```json
{
  "event": "tool.complete",
  "tool": "get_cloudwatch_metrics",
  "node": "incident_correlation",
  "latency_ms": 87,
  "policy_decision": "ALLOW"
}
```

---

### `on_error(ctx: NodeContext, error: Exception) → ErrorDisposition`

Fires when a node raises an unhandled exception. Classifies the error as `RETRY` or `FATAL`.

**Classification rules:**
| Error type | Disposition |
|-----------|-------------|
| `_ThrottlingError` (Bedrock/DynamoDB throttle) | `RETRY` |
| All other exceptions | `FATAL` |

**Returns:** `ErrorDisposition.RETRY` or `ErrorDisposition.FATAL`

**Emits:**
```json
{
  "event": "node.error",
  "node": "evidence_collector",
  "opportunity_id": "opp-replay-001",
  "error": "ThrottlingException: Rate exceeded",
  "error_type": "_ThrottlingError"
}
```

---

### `custom_redaction_hook(ctx: TraceContext, value: str) → str`

Fires when Strands writes a value to the user-visible agent trace. Scans the value against `_HIGH_RISK_PATTERNS` and replaces any match with `"[REDACTED]"`.

**Redaction patterns:**
```python
_HIGH_RISK_PATTERNS = [
    re.compile(r"\b\d{12}\b"),                      # AWS account ID (12 digits)
    re.compile(r"AKIA[0-9A-Z]{16}"),                # AWS access key ID
    re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*\S+"),
    re.compile(r"(?i)authorization\s*[:=]\s*\S+"),
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),    # IPv4 address
    re.compile(r"(?i)password\s*[:=]\s*\S+"),
    re.compile(r"(?i)token\s*[:=]\s*[A-Za-z0-9+/=]{20,}"),
]
```

If a match is found, the hook:
1. Replaces the entire value with `"[REDACTED]"`
2. Increments `ctx.redaction_count` (for UI display)
3. Logs a `trace.redacted` warning with the pattern that matched

**Fail-closed:** Any pattern match → entire value redacted. There is no partial redaction.

---

## Tool Allowlist

```python
ALLOWED_TOOLS_FOR_NODE: dict[str, frozenset[str]] = {
    "normalize_event":         frozenset(),
    "incident_correlation":    frozenset({"get_cloudwatch_metrics", "get_health_event",
                                          "lookup_cloudtrail_events", "get_cost_anomalies"}),
    "sla_contract_resolver":   frozenset(),
    "availability_calculator": frozenset(),
    "evidence_collector":      frozenset({"get_cloudwatch_metrics", "query_cloudwatch_logs",
                                          "get_cost_and_usage", "store_evidence"}),
    "evidence_sanitizer":      frozenset(),
    "eligibility_reasoner":    frozenset(),   # no tool calls — reads evidence by ID only
    "risk_policy_gate":        frozenset({"create_approval_request"}),
    "claim_package_generator": frozenset({"store_evidence"}),
    "submission_adapter":      frozenset({"submit_support_case", "simulate_support_case"}),
    "case_monitor":            frozenset({"get_support_case_status"}),
}
```

This map is separate from but consistent with the `allowed_nodes` field in `TOOL_REGISTRY`. The redundancy is intentional: both the tool metadata and the hooks enforce the constraint independently.

---

## Hook Context Types

### `NodeContext`

```python
@dataclass
class NodeContext:
    node_name: str
    state: dict[str, Any]        # serialized GraphState snapshot
    _started_at: float           # monotonic time at creation

    @property
    def duration_ms(self) -> int:
        return int((monotonic() - _started_at) * 1000)
```

### `ToolContext`

```python
@dataclass
class ToolContext:
    tool_name: str
    node_name: str
    state: dict[str, Any]
    request_json: str = ""
    response_json: str = ""
    policy_decision: str = "ALLOW"
    _started_at: float = ...

    @property
    def duration_ms(self) -> int: ...

    def inject(self, key: str, value: Any) -> None:
        self.state[key] = value
```

---

## Structured Logging

All hooks use `structlog` for structured JSON logging. Log fields are consistent across all events:

| Field | Description |
|-------|-------------|
| `event` | Event type (e.g. `"node.start"`, `"tool.complete"`, `"trace.redacted"`) |
| `node` | Graph node name |
| `tool` | Tool name (only in tool events) |
| `opportunity_id` | Bound opportunity identifier |
| `duration_ms` | Execution time (only in `*.complete` events) |
| `policy_decision` | Cedar policy outcome (only in `tool.complete`) |
| `error` | Error message (only in `node.error`) |
| `error_type` | Exception class name (only in `node.error`) |
| `pattern` | Regex pattern that matched (only in `trace.redacted`) |

---

## Phase 1 vs Phase 2 Behavior

| Feature | Phase 1 | Phase 2 |
|---------|---------|---------|
| Allowlist enforcement | ✅ Active | ✅ Active |
| Redaction | ✅ Active | ✅ Active |
| Structured logging | ✅ Active | ✅ Active |
| X-Ray spans | No-op (no credentials) | Active (aws-xray-sdk) |
| DynamoDB audit writes | No-op → logged warning | Active → `recoup-tool-audits` |
| `on_error` classification | ✅ Active | ✅ Active |
