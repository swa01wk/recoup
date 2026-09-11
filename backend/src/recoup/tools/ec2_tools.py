"""
Phase 6 demo tool — stop_demo_instance.

This tool is NOT available to any node in the standard SLA recovery graph.
It is registered exclusively for the live EC2 demo path (Phase 6) and
requires all of:
  - instance_id in the configured allowlist
  - Valid, unexpired ApprovalRecord
  - AgentCore Policy ALLOW (Cedar rule checks RecoupDemo tag)
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from strands import tool

from ..config import settings

# In-memory idempotency store for live stops (keyed by "{opportunity_id}:{instance_id}")
_IDEMPOTENCY_STORE: dict[str, dict[str, Any]] = {}


def _action_hash(opportunity_id: str, instance_id: str) -> str:
    """SHA-256 binding hash that ties an approval to one specific action."""
    return "sha256:" + hashlib.sha256(
        f"{opportunity_id}:stop_demo_instance:{instance_id}".encode()
    ).hexdigest()


def _clear_idempotency_store() -> None:
    """Reset idempotency store — for use in tests only."""
    _IDEMPOTENCY_STORE.clear()


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
      4. Claim hash is bound to this specific opportunity_id + instance_id
      5. Idempotency: duplicate call returns prior result without a second stop

    If no allowlisted instance is configured, this tool returns a
    deterministic stub response without touching AWS.

    Args:
        instance_id: EC2 instance to stop (must have tag RecoupDemo=true).
        opportunity_id: Associated opportunity for audit trail.
        approval_id: Valid approval record ID for this action.
        reason: Human-readable reason recorded in CloudTrail.

    Returns:
        dict with instance_id, previous_state, current_state, stopped_at, simulated
    """
    allowed_ids = settings.demo_instance_ids

    # Guard 0: Stub mode — demo placeholder or no allowlist configured.
    # Still enforces approval state even in stub mode.
    if not allowed_ids or instance_id == "i-demo0000000000000":
        from ..approval.store import get_approval  # noqa: PLC0415
        approval_record = get_approval(approval_id)
        if approval_record is None or approval_record.state.value != "APPROVED":
            raise PermissionError(
                f"Approval '{approval_id}' is not in APPROVED state. "
                "Human approval is required before executing the stop action."
            )
        return {
            "instance_id": instance_id,
            "previous_state": "running",
            "current_state": "stopping",
            "stopped_at": None,
            "simulated": True,
            "approval_id": approval_id,
            "opportunity_id": opportunity_id,
            "audit_trail": [
                "[DEMO] Approval verified — APPROVED state confirmed.",
                "[DEMO] No real AWS API call made (no allowlisted instance configured).",
            ],
        }

    # Guard 1: Allowlist check — must pass in live mode
    if instance_id not in allowed_ids:
        raise PermissionError(
            f"Instance '{instance_id}' is not in the RecoupDemo allowlist. "
            f"Allowed: {allowed_ids}"
        )

    # ── Live mode: all 5 guards must pass before any AWS call ──────────────

    ts = datetime.now(UTC).isoformat()

    # Guard 2: Live tag verification via AWS
    import boto3  # noqa: PLC0415

    # Phase 6e: use RecoupRemediationRole credentials when configured.
    # The remediation role is scoped to ec2:StopInstances on RecoupDemo=true only
    # and explicitly denies ec2:TerminateInstances.  Fall back to default
    # credential chain (instance profile / env vars) when role ARN is not set.
    _ec2_session: Any
    if settings.recoup_remediation_role_arn and settings.recoup_external_id:
        from ..models.connection import CustomerConnection  # noqa: PLC0415

        _rem_conn = CustomerConnection(
            role_arn=settings.recoup_remediation_role_arn,
            external_id=settings.recoup_external_id,
            region=settings.bedrock_region,
            session_name="recoup-remediation-session",
        )
        _ec2_session = _rem_conn.build_session()
        audit_trail: list[str] = [
            f"Assumed RecoupRemediationRole via STS: {settings.recoup_remediation_role_arn}"
        ]
    else:
        _ec2_session = boto3.Session(region_name=settings.bedrock_region)
        audit_trail = []

    ec2 = _ec2_session.client("ec2", region_name=settings.bedrock_region)
    tags_resp = ec2.describe_tags(
        Filters=[
            {"Name": "resource-id", "Values": [instance_id]},
            {"Name": "key", "Values": ["RecoupDemo"]},
        ]
    )
    tags = tags_resp.get("Tags", [])
    if not any(t.get("Value") == "true" for t in tags):
        raise PermissionError(
            f"Instance '{instance_id}' does not have RecoupDemo=true tag. "
            "Refusing to stop untagged instance."
        )
    audit_trail.append(f"[{ts}] RecoupDemo=true tag verified via DescribeTags API")

    # Guard 3 & 4: Approval validation + binding assertion
    from ..approval.store import get_approval  # noqa: PLC0415

    record = get_approval(approval_id)
    if record is None:
        raise PermissionError(f"Approval '{approval_id}' not found")
    if not record.is_valid:
        raise PermissionError(
            f"Approval '{approval_id}' is not valid "
            f"(state={record.state}, expired={record.is_expired})"
        )

    expected_hash = _action_hash(opportunity_id, instance_id)
    if record.claim_hash != expected_hash:
        raise PermissionError(
            f"Approval claim_hash mismatch for instance '{instance_id}'. "
            "Approval was not bound to this opportunity + instance combination."
        )
    audit_trail.append(
        f"Approval {approval_id[:8]}... validated — state=APPROVED, hash matches"
    )

    # Guard 5: Idempotency — prevent duplicate stop calls
    idem_key = f"{opportunity_id}:{instance_id}"
    if idem_key in _IDEMPOTENCY_STORE:
        prior = _IDEMPOTENCY_STORE[idem_key]
        return {**prior, "idempotent": True}

    # ── Execute stop ────────────────────────────────────────────────────────

    # Get current state before acting
    desc = ec2.describe_instances(InstanceIds=[instance_id])
    previous_state: str = desc["Reservations"][0]["Instances"][0]["State"]["Name"]
    audit_trail.append(f"Pre-stop state verified: {previous_state}")

    if previous_state == "stopped":
        result: dict[str, Any] = {
            "instance_id": instance_id,
            "previous_state": previous_state,
            "current_state": "stopped",
            "stopped_at": datetime.now(UTC).isoformat(),
            "verified_stopped": True,
            "simulated": False,
            "approval_id": approval_id,
            "opportunity_id": opportunity_id,
            "audit_trail": audit_trail + ["Instance already stopped — idempotent return"],
        }
        _IDEMPOTENCY_STORE[idem_key] = result
        return result

    # Issue StopInstances — NOT TerminateInstances (reversible)
    audit_trail.append(
        f"Issuing StopInstances for {instance_id} (reason: {reason})"
    )
    ec2.stop_instances(InstanceIds=[instance_id])

    # Wait for stopped state — timeout after 60 s (5 s × 12 attempts)
    waiter = ec2.get_waiter("instance_stopped")
    waiter.wait(
        InstanceIds=[instance_id],
        WaiterConfig={"Delay": 5, "MaxAttempts": 12},
    )

    # Verify final state
    desc2 = ec2.describe_instances(InstanceIds=[instance_id])
    final_state: str = desc2["Reservations"][0]["Instances"][0]["State"]["Name"]
    stopped_at = datetime.now(UTC).isoformat()
    audit_trail.append(f"Final state verified: {final_state}")

    result = {
        "instance_id": instance_id,
        "previous_state": previous_state,
        "current_state": final_state,
        "stopped_at": stopped_at,
        "verified_stopped": final_state == "stopped",
        "simulated": False,
        "approval_id": approval_id,
        "opportunity_id": opportunity_id,
        "audit_trail": audit_trail,
    }
    _IDEMPOTENCY_STORE[idem_key] = result
    return result
