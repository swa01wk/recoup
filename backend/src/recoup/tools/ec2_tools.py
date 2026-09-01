"""
Phase 6 demo tool — stop_demo_instance.

This tool is NOT available to any node in the standard SLA recovery graph.
It is registered exclusively for the live EC2 demo path (Phase 6) and
requires all of:
  - simulation_mode == False
  - instance_id in the configured allowlist
  - Valid, unexpired ApprovalRecord
  - AgentCore Policy ALLOW (Cedar rule checks RecoupDemo tag)
"""

from __future__ import annotations

from typing import Any

from strands import tool

from ..config import settings


@tool
def stop_demo_instance(
    instance_id: str,
    opportunity_id: str,
    approval_id: str,
    reason: str = "Recoup cost-optimization demo",
) -> dict[str, Any]:
    """
    Stop a tagged EC2 demo instance after CloudTrail and CloudWatch validation.

    This is a MUTATE_RED action. It will only execute when ALL safety gates pass:
      1. instance_id is in the RecoupDemo allowlist
      2. A valid ApprovalRecord matching approval_id exists and has not expired
      3. AgentCore Policy Cedar rule authorises the action
      4. CloudWatch confirms the instance is idle (CPU < 5% for 30 min)
      5. CloudTrail confirms no blocking ownership or recent configuration changes

    In Phase 1 / simulation mode this tool always returns a stub response.

    Args:
        instance_id: EC2 instance to stop (must have tag RecoupDemo=true).
        opportunity_id: Associated opportunity for audit trail.
        approval_id: Valid approval record ID for this action.
        reason: Human-readable reason recorded in CloudTrail.

    Returns:
        {'instance_id', 'previous_state', 'current_state', 'stopped_at', 'simulated'}
    """
    allowed_ids = settings.demo_instance_ids
    if instance_id not in allowed_ids:
        raise PermissionError(
            f"Instance '{instance_id}' is not in the RecoupDemo allowlist. "
            f"Allowed: {allowed_ids}"
        )

    if not settings.recoup_enable_live_aws:
        return {
            "instance_id": instance_id,
            "previous_state": "running",
            "current_state": "stopping",
            "stopped_at": None,
            "simulated": True,
            "approval_id": approval_id,
            "_stub": True,
        }

    # Phase 6: real stop via boto3 with full safety pre-checks
    raise NotImplementedError("Live EC2 stop implemented in Phase 6")
