"""
Autonomy class enforcement — every tool is classified and checked before execution.

Autonomy classes:
    GREEN  — read/analyze — automatic, no approval needed
    YELLOW — internal write — automatic + visible audit trail
    RED    — external financial action — human approval + Cedar policy required
    BLACK  — destructive infrastructure — hard-disabled in V1

The check is enforced in a deterministic pre-tool hook, NOT in a prompt.
LLM instructions cannot override this — it runs before the tool callable.
"""

from __future__ import annotations

from enum import StrEnum

from ..graph.types import ToolContext
from ..models.approval import ApprovalRecord
from .exceptions import ApprovalRequiredError, ToolDeniedError


class AutonomyClass(StrEnum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    BLACK = "BLACK"


# Single source of truth for every tool's autonomy class.
# Any tool not listed defaults to BLACK (fail-closed).
TOOL_AUTONOMY_CLASS: dict[str, AutonomyClass] = {
    # --- GREEN: read-only AWS data ---
    "get_cloudwatch_metrics": AutonomyClass.GREEN,
    "query_cloudwatch_logs": AutonomyClass.GREEN,
    "get_health_event": AutonomyClass.GREEN,
    "get_cost_and_usage": AutonomyClass.GREEN,
    "get_cost_anomalies": AutonomyClass.GREEN,
    "list_cost_optimization_recommendations": AutonomyClass.GREEN,
    "lookup_cloudtrail_events": AutonomyClass.GREEN,
    "get_support_case_status": AutonomyClass.GREEN,
    # --- YELLOW: internal write ---
    "store_evidence": AutonomyClass.YELLOW,
    "create_approval_request": AutonomyClass.YELLOW,
    "simulate_support_case": AutonomyClass.YELLOW,
    # --- RED: external financial / mutating ---
    "submit_support_case": AutonomyClass.RED,
    "stop_demo_instance": AutonomyClass.RED,
    # --- BLACK: destructive infrastructure (disabled V1) ---
    "stop_resource": AutonomyClass.BLACK,
    "delete_resource": AutonomyClass.BLACK,
    "terminate_ec2_instance": AutonomyClass.BLACK,
}


def get_autonomy_class(tool_name: str) -> AutonomyClass:
    """Return the autonomy class for a tool; defaults to BLACK for unknown tools."""
    return TOOL_AUTONOMY_CLASS.get(tool_name, AutonomyClass.BLACK)


def check_autonomy(
    tool_name: str,
    opportunity_id: str,
    approval: ApprovalRecord | None = None,
    ctx: ToolContext | None = None,
) -> None:
    """
    Assert the tool is permitted to execute given the current approval state.

    Args:
        tool_name:      Name of the tool about to be called.
        opportunity_id: Current opportunity (for error messages).
        approval:       The ApprovalRecord from GraphState (may be None).
        ctx:            Optional ToolContext for structured logging.

    Raises:
        ToolDeniedError:      BLACK-class tool or policy DENY.
        ApprovalRequiredError: RED-class tool with no valid approval.
    """
    cls = get_autonomy_class(tool_name)

    if cls == AutonomyClass.BLACK:
        raise ToolDeniedError(
            tool_name=tool_name,
            reason="Tool class is BLACK — permanently disabled in V1",
        )

    if cls == AutonomyClass.RED:
        if approval is None or not approval.is_valid:
            raise ApprovalRequiredError(
                tool_name=tool_name,
                opportunity_id=opportunity_id,
            )

    # GREEN and YELLOW pass through automatically
