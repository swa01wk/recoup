"""
Tool registry — maps tool names to metadata and callable implementations.

TOOL_REGISTRY is the single source of truth for:
  - action class (READ, READ_SENSITIVE, READ_FINANCIAL, WRITE_INTERNAL,
                  WRITE_EXTERNAL_FINANCIAL, MUTATE_RED)
  - Lambda target name (for AgentCore Gateway registration)
  - allowed nodes
  - the callable tool function

The registry is consumed by:
  - AgentCore Gateway registration scripts
  - Strands Agent instantiation (tools=list(TOOL_REGISTRY.values()))
  - The tracing hook allowlist cross-check
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .aws_tools import (
    get_cloudwatch_metrics,
    get_cost_and_usage,
    get_cost_anomalies,
    get_health_event,
    get_support_case_status,
    list_cost_optimization_recommendations,
    lookup_cloudtrail_events,
    query_cloudwatch_logs,
)
from .ec2_tools import stop_demo_instance
from .internal_tools import (
    create_approval_request,
    simulate_support_case,
    store_evidence,
)


@dataclass(frozen=True)
class ToolMeta:
    """Metadata for a single registered tool."""

    name: str
    action_class: str
    lambda_target: str
    allowed_nodes: frozenset[str]
    fn: Callable[..., Any]
    description: str = ""


TOOL_REGISTRY: dict[str, ToolMeta] = {
    "get_cloudwatch_metrics": ToolMeta(
        name="get_cloudwatch_metrics",
        action_class="READ",
        lambda_target="recoup-cw-tool",
        allowed_nodes=frozenset({"incident_correlation", "evidence_collector"}),
        fn=get_cloudwatch_metrics,
        description="Retrieve CloudWatch metric datapoints for an AWS resource",
    ),
    "query_cloudwatch_logs": ToolMeta(
        name="query_cloudwatch_logs",
        action_class="READ_SENSITIVE",
        lambda_target="recoup-cw-logs-tool",
        allowed_nodes=frozenset({"evidence_collector"}),
        fn=query_cloudwatch_logs,
        description="Run a CloudWatch Logs Insights query",
    ),
    "get_health_event": ToolMeta(
        name="get_health_event",
        action_class="READ",
        lambda_target="recoup-health-tool",
        allowed_nodes=frozenset({"incident_correlation"}),
        fn=get_health_event,
        description="Retrieve AWS Health events for a service and region",
    ),
    "get_cost_and_usage": ToolMeta(
        name="get_cost_and_usage",
        action_class="READ_FINANCIAL",
        lambda_target="recoup-cost-tool",
        allowed_nodes=frozenset({"evidence_collector"}),
        fn=get_cost_and_usage,
        description="Retrieve AWS Cost and Usage data",
    ),
    "get_cost_anomalies": ToolMeta(
        name="get_cost_anomalies",
        action_class="READ_FINANCIAL",
        lambda_target="recoup-cost-tool",
        allowed_nodes=frozenset({"incident_correlation"}),
        fn=get_cost_anomalies,
        description="Retrieve AWS Cost Anomaly Detection results",
    ),
    "list_cost_optimization_recommendations": ToolMeta(
        name="list_cost_optimization_recommendations",
        action_class="READ_FINANCIAL",
        lambda_target="recoup-cost-tool",
        allowed_nodes=frozenset({"incident_correlation"}),
        fn=list_cost_optimization_recommendations,
        description="List AWS Cost Optimization Hub recommendations",
    ),
    "lookup_cloudtrail_events": ToolMeta(
        name="lookup_cloudtrail_events",
        action_class="READ_SENSITIVE",
        lambda_target="recoup-cloudtrail-tool",
        allowed_nodes=frozenset({"incident_correlation"}),
        fn=lookup_cloudtrail_events,
        description="Look up CloudTrail API activity for a resource",
    ),
    "store_evidence": ToolMeta(
        name="store_evidence",
        action_class="WRITE_INTERNAL",
        lambda_target="recoup-evidence-tool",
        allowed_nodes=frozenset({"evidence_collector", "claim_package_generator"}),
        fn=store_evidence,
        description="Store raw evidence to the encrypted S3 evidence bucket",
    ),
    "create_approval_request": ToolMeta(
        name="create_approval_request",
        action_class="WRITE_INTERNAL",
        lambda_target="recoup-approval-tool",
        allowed_nodes=frozenset({"risk_policy_gate"}),
        fn=create_approval_request,
        description="Create a HITL approval request for a financial action",
    ),
    "submit_support_case": ToolMeta(
        name="submit_support_case",
        action_class="WRITE_EXTERNAL_FINANCIAL",
        lambda_target="recoup-support-tool",
        allowed_nodes=frozenset({"submission_adapter"}),
        fn=simulate_support_case,  # real impl wired in Phase 2
        description="Submit SLA credit claim to AWS Support (requires approval + live mode)",
    ),
    "simulate_support_case": ToolMeta(
        name="simulate_support_case",
        action_class="WRITE_INTERNAL",
        lambda_target="recoup-simulate-tool",
        allowed_nodes=frozenset({"submission_adapter"}),
        fn=simulate_support_case,
        description="Produce a deterministic simulated AWS Support case ID",
    ),
    "get_support_case_status": ToolMeta(
        name="get_support_case_status",
        action_class="READ",
        lambda_target="recoup-support-tool",
        allowed_nodes=frozenset({"case_monitor"}),
        fn=get_support_case_status,
        description="Get the current status of an AWS Support case",
    ),
    "stop_demo_instance": ToolMeta(
        name="stop_demo_instance",
        action_class="MUTATE_RED",
        lambda_target="recoup-ec2-demo-tool",
        allowed_nodes=frozenset(),  # Not in the standard graph — Phase 6 only
        fn=stop_demo_instance,
        description="Stop a tagged EC2 demo instance after all safety gates pass",
    ),
}
