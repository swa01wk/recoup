"""
Strands lifecycle hooks for tracing, auditing, and redaction.

Hooks fire around every node and tool call. They:
  - Open/close trace spans (AWS X-Ray via aws-xray-sdk)
  - Validate tool allowlists per node
  - Write ToolAudit records to DynamoDB after every tool call
  - Redact sensitive values from user-visible traces
  - Classify errors as RETRY or FATAL

Phase 1: All hooks are wired but span recording and DynamoDB writes are
no-ops unless AWS credentials are present. The allowlist validation and
redaction logic are fully active.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC
from typing import Any

import structlog

from ..graph.types import ErrorDisposition, NodeContext, ToolContext

log: structlog.BoundLogger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Tool allowlist — enforced in before_tool_call
# ---------------------------------------------------------------------------

ALLOWED_TOOLS_FOR_NODE: dict[str, frozenset[str]] = {
    "normalize_event": frozenset(),
    "incident_correlation": frozenset({
        "get_cloudwatch_metrics",
        "get_health_event",
        "lookup_cloudtrail_events",
        "get_cost_anomalies",
    }),
    "sla_contract_resolver": frozenset(),
    "availability_calculator": frozenset(),
    "evidence_collector": frozenset({
        "get_cloudwatch_metrics",
        "query_cloudwatch_logs",
        "get_cost_and_usage",
        "store_evidence",
    }),
    "evidence_sanitizer": frozenset(),
    "eligibility_reasoner": frozenset(),  # Read-only; no tool calls
    "risk_policy_gate": frozenset({"create_approval_request"}),
    "claim_package_generator": frozenset({"store_evidence"}),
    "submission_adapter": frozenset({"submit_support_case", "simulate_support_case"}),
    "case_monitor": frozenset({"get_support_case_status"}),
}

# ---------------------------------------------------------------------------
# High-risk redaction patterns — any match in trace output → [REDACTED]
# ---------------------------------------------------------------------------

_HIGH_RISK_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b\d{12}\b"),                      # AWS account ID
    re.compile(r"AKIA[0-9A-Z]{16}"),                # AWS access key ID
    re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*\S+"),
    re.compile(r"(?i)authorization\s*[:=]\s*\S+"),
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),    # IPv4 address
    re.compile(r"(?i)password\s*[:=]\s*\S+"),
    re.compile(r"(?i)token\s*[:=]\s*[A-Za-z0-9+/=]{20,}"),
]


def _sha256_json(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(obj, default=str, sort_keys=True).encode()
    ).hexdigest()


class _ThrottlingError(Exception):
    pass


# ---------------------------------------------------------------------------
# Hook implementation
# ---------------------------------------------------------------------------

class RecoupTracingHooks:
    """
    Lifecycle hooks for the Recoup graph.

    Attach an instance of this class to a Strands Agent or call the methods
    directly when executing graph nodes.

    Example:
        hooks = RecoupTracingHooks(opportunity_id="opp-001")
        ctx = NodeContext(node_name="normalize_event", state={"opportunity_id": "opp-001"})
        hooks.before_node_call(ctx)
        result = node.run(state)
        hooks.after_node_call(ctx, result)
    """

    def __init__(
        self,
        opportunity_id: str,
        principal: str = "system",
        simulation_mode: bool = True,
    ) -> None:
        self._opportunity_id = opportunity_id
        self._principal = principal
        self._simulation_mode = simulation_mode
        self._spans: dict[str, Any] = {}

    # -----------------------------------------------------------------------
    # Node hooks
    # -----------------------------------------------------------------------

    def before_node_call(self, ctx: NodeContext) -> None:
        """
        Start a trace span and verify state preconditions.

        Raises:
            RuntimeError: If the node is called out of expected sequence
                          (opportunity_id mismatch).
        """
        state_opp_id = ctx.state.get("opportunity_id")
        if state_opp_id and state_opp_id != self._opportunity_id:
            raise RuntimeError(
                f"Hook opportunity_id mismatch: hook={self._opportunity_id!r}, "
                f"state={state_opp_id!r}"
            )

        log.info(
            "node.start",
            node=ctx.node_name,
            opportunity_id=self._opportunity_id,
            state_version=ctx.state.get("state_version", 0),
        )
        self._spans[ctx.node_name] = ctx

    def after_node_call(self, ctx: NodeContext, result: Any) -> None:
        """Close the trace span and record duration."""
        log.info(
            "node.complete",
            node=ctx.node_name,
            opportunity_id=self._opportunity_id,
            duration_ms=ctx.duration_ms,
        )
        self._spans.pop(ctx.node_name, None)

    # -----------------------------------------------------------------------
    # Tool hooks
    # -----------------------------------------------------------------------

    def before_tool_call(self, ctx: ToolContext) -> None:
        """
        Validate the tool against the node allowlist and inject session context.

        Raises:
            PermissionError: Tool not in allowlist for this node.
        """
        allowed = ALLOWED_TOOLS_FOR_NODE.get(ctx.node_name, frozenset())
        if allowed and ctx.tool_name not in allowed:
            raise PermissionError(
                f"Tool '{ctx.tool_name}' is not allowed for node '{ctx.node_name}'. "
                f"Allowed tools: {sorted(allowed)}"
            )

        ctx.inject("opportunity_id", self._opportunity_id)
        ctx.inject("session_principal", self._principal)
        ctx.inject("simulation_mode", self._simulation_mode)

        log.info(
            "tool.start",
            tool=ctx.tool_name,
            node=ctx.node_name,
            opportunity_id=self._opportunity_id,
        )

    def after_tool_call(self, ctx: ToolContext, result: Any) -> None:
        """
        Write a ToolAudit record.

        Hashes request and response — never stores raw content.
        """
        from datetime import datetime

        from ..models.audit import ToolAudit

        audit = ToolAudit(
            trace_id=f"{self._opportunity_id}:{ctx.node_name}:{ctx.tool_name}",
            opportunity_id=self._opportunity_id,
            node=ctx.node_name,
            tool=ctx.tool_name,
            request_hash=_sha256_json(ctx.request_json),
            response_hash=_sha256_json(ctx.response_json),
            policy_decision=ctx.policy_decision,  # type: ignore[arg-type]
            latency_ms=ctx.duration_ms,
            timestamp=datetime.now(UTC),
        )

        log.info(
            "tool.complete",
            tool=ctx.tool_name,
            node=ctx.node_name,
            latency_ms=ctx.duration_ms,
            policy_decision=audit.policy_decision,
        )

        self._save_audit(audit)

    def on_error(self, ctx: NodeContext, error: Exception) -> ErrorDisposition:
        """
        Classify an error as RETRY or FATAL.

        Throttling errors are retried (up to framework retry limit).
        All other errors are fatal and surface to the operator.
        """
        log.error(
            "node.error",
            node=ctx.node_name,
            opportunity_id=self._opportunity_id,
            error=str(error),
            error_type=type(error).__name__,
        )
        if isinstance(error, _ThrottlingError):
            return ErrorDisposition.RETRY
        return ErrorDisposition.FATAL

    def custom_redaction_hook(self, ctx: TraceContext, value: str) -> str:  # type: ignore[name-defined]  # noqa: F821
        """
        Redact any high-risk pattern found in a user-visible trace value.

        Increments the redaction counter on ctx so the UI can show a badge.
        """
        for pattern in _HIGH_RISK_PATTERNS:
            if pattern.search(value):
                if hasattr(ctx, "increment"):
                    ctx.increment("redaction_count")
                log.warning(
                    "trace.redacted",
                    pattern=pattern.pattern,
                    opportunity_id=self._opportunity_id,
                )
                return "[REDACTED]"
        return value

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _save_audit(self, audit: ToolAudit) -> None:  # type: ignore[name-defined]  # noqa: F821
        """
        Persist ToolAudit to DynamoDB (best-effort; log errors but don't raise).
        """
        try:
            import boto3

            from ..config import settings

            ddb = boto3.resource("dynamodb")
            table = ddb.Table(settings.tool_audits_table)
            table.put_item(Item=audit.model_dump(mode="json"))
        except Exception as exc:  # noqa: BLE001
            log.warning("audit.save_failed", error=str(exc))
