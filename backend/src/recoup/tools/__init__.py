"""
Recoup tool schemas and stub implementations.

All tools are narrow, typed, and registered via AgentCore Gateway. No raw
boto3 clients are exposed to agents — every tool enforces its own guard.

Tools use the strands @tool decorator so they can be passed directly to
strands.Agent(tools=[...]) in Phase 2.
"""

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
from .registry import TOOL_REGISTRY, ToolMeta

__all__ = [
    # AWS read tools
    "get_cloudwatch_metrics",
    "query_cloudwatch_logs",
    "get_health_event",
    "get_cost_and_usage",
    "get_cost_anomalies",
    "list_cost_optimization_recommendations",
    "lookup_cloudtrail_events",
    "get_support_case_status",
    # Internal write tools
    "store_evidence",
    "create_approval_request",
    "simulate_support_case",
    # Phase 6 demo tool
    "stop_demo_instance",
    # Registry
    "TOOL_REGISTRY",
    "ToolMeta",
]
