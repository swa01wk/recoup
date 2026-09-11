"""
Cedar policy evaluation — Python simulation of the AgentCore Policy Cedar rules.

In production this delegates to the AWS Bedrock AgentCore Policy service which
evaluates the actual Cedar policies in ``infra/policy/recoup-policy.cedar``.

This module provides:
  1. A ``PolicyContext`` dataclass that mirrors the Cedar evaluation context.
  2. ``evaluate_policy(action, ctx)`` — deterministic Python simulation that
     produces identical ALLOW/DENY decisions to the real Cedar policies.
  3. Integration tests for all 5 preconditions on ``submit_support_case``.

The simulation is used in:
  - Unit tests (no AWS credentials required)
  - risk_policy_gate node (Phase 3 path; real AgentCore call in Phase 4+)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

# ---------------------------------------------------------------------------
# Policy context — mirrors Cedar evaluation context attributes
# ---------------------------------------------------------------------------


@dataclass
class PolicyContext:
    """
    All attributes available during Cedar policy evaluation.

    Attribute names match the Cedar context keys in recoup-policy.cedar.
    """

    # Session
    session_authenticated: bool = True

    # Approval
    approval_state: str = "PENDING"          # "PENDING" | "APPROVED" | "EXPIRED" | "DECLINED"
    approval_amount: Decimal = Decimal("0")
    approval_expires_at: datetime = field(
        default_factory=lambda: datetime(2099, 1, 1, tzinfo=UTC)
    )
    approved_state_version: int = 0

    # Claim
    claim_amount: Decimal = Decimal("0")
    opportunity_state_version: int = 0

    # Feature flags
    recoup_enable_real_submission: bool = False

    # EC2 demo (Phase 6)
    target_instance_tag: str = ""
    target_account_id: str = ""
    allowlisted_demo_account_id: str = ""

    # Runtime timestamp (injected at evaluation time)
    current_time: datetime = field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Cedar policy evaluation
# ---------------------------------------------------------------------------

# Read-only tools that are always permitted for authenticated sessions
_READ_ACTIONS: frozenset[str] = frozenset({
    "get_cloudwatch_metrics",
    "query_cloudwatch_logs",
    "get_health_event",
    "get_cost_and_usage",
    "get_cost_anomalies",
    "list_cost_optimization_recommendations",
    "lookup_cloudtrail_events",
    "store_evidence",
    "create_approval_request",
    "simulate_support_case",
    "get_support_case_status",
})

# Permanently forbidden destructive tools (forbid rule; overrides all permits)
_FORBIDDEN_ACTIONS: frozenset[str] = frozenset({
    "stop_resource",
    "delete_resource",
    "terminate_ec2_instance",
})


def evaluate_policy(action: str, ctx: PolicyContext) -> str:
    """
    Evaluate Cedar policies for ``action`` against ``ctx``.

    Returns:
        "ALLOW"  — action is permitted
        "DENY"   — action is denied (includes explicit forbids)

    Policy evaluation order mirrors Cedar:
      1. Forbid rules (hard deny — cannot be overridden)
      2. Permit rules (specific preconditions per action)
      3. Default deny (implicit; no matching permit → DENY)
    """
    # --- 1. Forbid rules -----------------------------------------------
    if action in _FORBIDDEN_ACTIONS:
        return "DENY"

    # --- 2. Permit rules -----------------------------------------------

    # Read-only tools: permit when session is authenticated
    if action in _READ_ACTIONS:
        return "ALLOW" if ctx.session_authenticated else "DENY"

    # submit_support_case: 5 preconditions must ALL be satisfied
    if action == "submit_support_case":
        if not _check_submit_support_case(ctx):
            return "DENY"
        return "ALLOW"

    # stop_demo_instance: approval + allowlist guard
    if action == "stop_demo_instance":
        if not _check_stop_demo_instance(ctx):
            return "DENY"
        return "ALLOW"

    # --- 3. Default deny -----------------------------------------------
    return "DENY"


def _check_submit_support_case(ctx: PolicyContext) -> bool:
    """
    All 5 Cedar preconditions for submit_support_case.

    Mirrors the Cedar permit rule exactly:
      approval_state == "APPROVED"
      approval_amount == claim_amount
      approval_expires_at > current_time
      opportunity_state_version == approved_state_version
      recoup_enable_real_submission == true
    """
    now = datetime.now(UTC)
    return (
        ctx.approval_state == "APPROVED"
        and ctx.approval_amount == ctx.claim_amount
        and ctx.approval_expires_at > now
        and ctx.opportunity_state_version == ctx.approved_state_version
        and ctx.recoup_enable_real_submission
    )


def _check_stop_demo_instance(ctx: PolicyContext) -> bool:
    """
    Cedar preconditions for stop_demo_instance.

    approval_state == "APPROVED"
    target_instance_tag == "RecoupDemo=true"
    target_account_id == allowlisted_demo_account_id
    approval_expires_at > current_time
    """
    now = datetime.now(UTC)
    return (
        ctx.approval_state == "APPROVED"
        and ctx.target_instance_tag == "RecoupDemo=true"
        and ctx.target_account_id == ctx.allowlisted_demo_account_id
        and ctx.target_account_id != ""
        and ctx.approval_expires_at > now
    )


def build_context_from_graph_state(
    state: GraphState,  # type: ignore[name-defined]  # noqa: F821
) -> PolicyContext:
    """
    Derive a PolicyContext from the current GraphState.

    Used by risk_policy_gate to evaluate Cedar policy without importing
    the graph module into the safety layer.
    """
    approval = state.approval_record
    result = state.availability_result

    approval_state = "PENDING"
    approval_amount = Decimal("0")
    approval_expires_at = datetime(2099, 1, 1, tzinfo=UTC)
    approved_state_version = 0

    if approval is not None:
        approval_state = str(approval.state)
        approval_amount = approval.amount
        approval_expires_at = approval.expires_at
        approved_state_version = approval.state_version

    claim_amount = result.potential_credit if result is not None else Decimal("0")

    from ..config import settings

    return PolicyContext(
        session_authenticated=True,
        approval_state=approval_state,
        approval_amount=approval_amount,
        approval_expires_at=approval_expires_at,
        approved_state_version=approved_state_version,
        claim_amount=claim_amount,
        opportunity_state_version=state.state_version,
        recoup_enable_real_submission=settings.recoup_enable_real_support_submission,
        current_time=datetime.now(UTC),
    )
