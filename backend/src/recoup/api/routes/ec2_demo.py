"""
EC2 Demo REST API routes — Phase 6 live AWS action proof.

POST /api/ec2-demo/trigger            — start EC2 demo workflow (creates approval)
GET  /api/ec2-demo/opportunities      — list all EC2 demo opportunities
GET  /api/ec2-demo/opportunity/{id}   — get one EC2 demo opportunity
POST /api/ec2-demo/execute/{id}       — execute stop after approval is confirmed
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from ...adapters.ec2_demo import EC2DemoAdapter
from ...config import settings
from ...notifications import notify_sns, publish_action_event, publish_opportunity_event

router = APIRouter()
_adapter = EC2DemoAdapter()


class TriggerRequest(BaseModel):
    instance_id: str = ""


@router.post("/trigger")
def trigger_ec2_demo(body: TriggerRequest = Body(default=TriggerRequest())) -> dict[str, Any]:
    """
    Trigger the EC2 demo workflow.

    Creates an OPTIMIZATION opportunity, runs CloudWatch and CloudTrail checks
    (real or simulated), calculates monthly waste, and raises a HITL approval
    request visible in the Decision Inbox with the LIVE AWS ACTION badge.

    If no instance_id is provided, uses the first entry in
    RECOUP_DEMO_INSTANCE_ALLOWLIST (falls back to 'i-demo0000000000000').
    """
    instance_id = body.instance_id.strip()
    if not instance_id:
        allowed = settings.demo_instance_ids
        instance_id = allowed[0] if allowed else "i-demo0000000000000"

    use_strands = bool(settings.evidence_bucket)
    try:
        record = _adapter.trigger(
            instance_id=instance_id,
            use_strands=use_strands,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # SQS opportunity event (live AWS only, fail silently)
    publish_opportunity_event(
        opportunity_id=record["opportunity"]["id"],
        opportunity_type="OPTIMIZATION",
        potential_value_usd=record["monthly_waste_usd"],
        service="ec2",
        region=record["opportunity"].get("region", "us-east-1"),
        requires_approval=True,
        extra={"instance_id": instance_id},
    )

    return record


@router.get("/opportunities")
def list_ec2_demo_opportunities() -> list[dict[str, Any]]:
    """List all EC2 demo opportunities, with top-level id/state for easy access."""
    results = []
    for record in _adapter.list_all():
        opp = record.get("opportunity", {})
        flat = dict(record)
        flat["id"] = opp.get("id", "")
        flat["state"] = opp.get("state", "")
        results.append(flat)
    return results


@router.get("/opportunity/{opportunity_id}")
def get_ec2_demo_opportunity(opportunity_id: str) -> dict[str, Any]:
    """Return a single EC2 demo opportunity by ID, with top-level id/state."""
    record = _adapter.get(opportunity_id)
    if record is None:
        raise HTTPException(404, f"EC2 demo opportunity '{opportunity_id}' not found")
    opp = record.get("opportunity", {})
    flat = dict(record)
    flat["id"] = opp.get("id", opportunity_id)
    flat["state"] = opp.get("state", "")
    flat["action"] = "stop_demo_instance"
    return flat


@router.post("/execute/{opportunity_id}")
def execute_ec2_demo(opportunity_id: str) -> dict[str, Any]:
    """
    Execute the instance stop after approval is confirmed.

    The HITL approval created by /trigger must be in APPROVED state before
    calling this endpoint.  Calls StopInstances with full Cedar policy +
    allowlist + tag verification guards.  Returns a deterministic stub result
    when no allowlisted instance is configured.
    """
    record = _adapter.get(opportunity_id)
    if record is None:
        raise HTTPException(404, f"EC2 demo opportunity '{opportunity_id}' not found")

    try:
        result = _adapter.execute(opportunity_id=opportunity_id)
    except PermissionError as exc:
        # Approval not in APPROVED state → 409 Conflict
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # SNS + SQS notifications on successful stop (live AWS only, fail silently)
    instance_id_exec: str = result.get("instance_id", "unknown")
    monthly_waste: str = result.get("monthly_waste_usd", "0")
    notify_sns(
        subject=f"Recoup — Instance {instance_id_exec} stopped — ${monthly_waste}/month saved",
        message=(
            f"Recoup stopped EC2 instance {instance_id_exec} after human approval.\n\n"
            f"Opportunity ID: {opportunity_id}\n"
            f"Estimated monthly saving: ${monthly_waste}\n"
            f"Instance type: {result.get('instance_type', 'unknown')}\n\n"
            "The instance was idle (avg CPU < 1% over 7 days) and had no recent "
            "blocking CloudTrail events. Action approved by human operator."
        ),
    )
    publish_action_event(
        opportunity_id=opportunity_id,
        action="stop_demo_instance",
        result="stopped",
        service="ec2",
        extra={"instance_id": instance_id_exec, "monthly_waste_usd": monthly_waste},
    )

    # Add top-level fields for easy access by tests
    stop = result.get("stop_result") or {}
    return {
        **result,
        "opportunity_id": opportunity_id,
        "status": stop.get("current_state", "success"),
    }
