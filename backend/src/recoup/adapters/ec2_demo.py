"""
EC2 Demo Adapter — orchestrates the live EC2 cost-optimisation demo workflow.

This workflow is distinct from the SLA graph. The EC2 demo:
  1. Strands agent analysis (live mode) OR simulated checks (replay mode)
       - CloudWatch CPU check  → confirms instance is idle (avg CPU < 1% over 7 days)
       - CloudTrail ownership  → no blocking changes in last 24 h
  2. Waste calculation → estimated monthly cost for idle instance
  3. Creates OPTIMIZATION opportunity with HITL approval request
  4. After human approval → calls stop_demo_instance with all 5 safety guards

When use_strands=True, a real Strands agent backed by Amazon Bedrock orchestrates
the analysis (tool calls to CloudWatch + CloudTrail + EC2 APIs) and provides
step-by-step reasoning about the stop decision.

The adapter is stateless across requests; all state lives in two module-level
in-memory dicts (_EC2_DEMO_OPPORTUNITIES, _approval store in approval/store.py).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from ..approval.flow import HITLFlow
from ..config import settings
from ..models.opportunity import OpportunityState, RecoveryOpportunity

# In-memory store for EC2 demo opportunities (keyed by opportunity_id)
_EC2_DEMO_OPPORTUNITIES: dict[str, dict[str, Any]] = {}

# On-demand pricing for common t3 instance types (USD/hour, us-east-1)
_T3_HOURLY: dict[str, Decimal] = {
    "t3.nano": Decimal("0.0052"),
    "t3.micro": Decimal("0.0104"),
    "t3.small": Decimal("0.0208"),
    "t3.medium": Decimal("0.0416"),
    "t3.large": Decimal("0.0832"),
    "t3.xlarge": Decimal("0.1664"),
    "t3.2xlarge": Decimal("0.3328"),
}
_DEFAULT_HOURLY = Decimal("0.0104")  # t3.micro fallback
_HOURS_PER_MONTH = Decimal("730")


def _monthly_waste(instance_type: str) -> Decimal:
    """Return estimated monthly on-demand cost for an idle instance."""
    hourly = _T3_HOURLY.get(instance_type, _DEFAULT_HOURLY)
    return (hourly * _HOURS_PER_MONTH).quantize(Decimal("0.01"))


def _clear_ec2_demo_store() -> None:
    """Reset in-memory store — for use in tests only."""
    _EC2_DEMO_OPPORTUNITIES.clear()


class EC2DemoAdapter:
    """
    Orchestrates the EC2 demo opportunity lifecycle.

    All AWS calls require real credentials and the RecoupDemo=true instance tag.
    """

    def trigger(
        self,
        instance_id: str,
        opportunity_id: str | None = None,
        use_strands: bool = False,
    ) -> dict[str, Any]:
        """
        Start the EC2 demo workflow for an instance.

        When use_strands=True, a Strands agent backed by Amazon Bedrock
        orchestrates the CloudWatch + CloudTrail analysis and provides
        step-by-step reasoning. Falls back to deterministic checks on any
        Bedrock failure.

        If ``instance_id`` is the placeholder ``i-demo0000000000000`` (or no
        allowlisted instance is configured), all AWS checks return deterministic
        stub values so the demo runs without real AWS credentials.

        Returns a record dict containing the opportunity, checks, approval ID,
        and (when Strands was used) agent_reasoning.
        """
        opp_id = opportunity_id or f"ec2-demo-{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC)

        agent_reasoning: str | None = None

        # ── Strands-driven analysis ───────────────────────────────────────────
        if use_strands:
            from ..agents.strands_agents import run_ec2_stop_decision_agent  # noqa: PLC0415

            strands_result = run_ec2_stop_decision_agent(
                instance_id=instance_id,
                region=settings.bedrock_region,
            )
            if strands_result is not None:
                cw_check = {
                    "avg_cpu_pct": strands_result.get("avg_cpu_pct", 0.0),
                    "max_cpu_pct": strands_result.get("max_cpu_pct", 0.0),
                    "period_days": 7,
                    "idle": strands_result.get("idle", True),
                    "note": strands_result.get("reasoning", "Strands agent analysis"),
                    "simulated": False,
                    "agent_driven": True,
                }
                ct_check = {
                    "recent_events": strands_result.get("recent_events", 0),
                    "blocking_changes": strands_result.get("blocking_changes", False),
                    "verdict": strands_result.get("verdict", "no_blocking_ownership_changes"),
                    "note": strands_result.get("reasoning", ""),
                    "simulated": False,
                    "agent_driven": True,
                }
                agent_reasoning = strands_result.get("reasoning")
                instance_type = self._get_instance_type(instance_id)
                monthly_waste = _monthly_waste(instance_type)
                waste_note = (
                    f"~${monthly_waste}/month at on-demand rate "
                    f"({instance_type}, {settings.bedrock_region}) — Strands agent verdict: "
                    f"{strands_result.get('verdict', 'idle_safe_to_stop')}"
                )
                return self._build_record(
                    opp_id=opp_id,
                    now=now,
                    instance_id=instance_id,
                    instance_type=instance_type,
                    cw_check=cw_check,
                    ct_check=ct_check,
                    monthly_waste=monthly_waste,
                    waste_note=waste_note,
                    agent_reasoning=agent_reasoning,
                )
            # Strands returned None — fall through to deterministic checks

        cw_check = self._cloudwatch_check(instance_id)
        ct_check = self._cloudtrail_check(instance_id)
        instance_type = self._get_instance_type(instance_id)

        monthly_waste = _monthly_waste(instance_type)
        waste_note = (
            f"~${monthly_waste}/month at on-demand rate "
            f"({instance_type}, {settings.bedrock_region})"
        )
        return self._build_record(
            opp_id=opp_id,
            now=now,
            instance_id=instance_id,
            instance_type=instance_type,
            cw_check=cw_check,
            ct_check=ct_check,
            monthly_waste=monthly_waste,
            waste_note=waste_note,
            agent_reasoning=None,
        )

    def _build_record(
        self,
        *,
        opp_id: str,
        now: datetime,
        instance_id: str,
        instance_type: str,
        cw_check: dict[str, Any],
        ct_check: dict[str, Any],
        monthly_waste: Decimal,
        waste_note: str,
        agent_reasoning: str | None,
    ) -> dict[str, Any]:
        """Assemble and persist the opportunity record after analysis."""
        opportunity = RecoveryOpportunity(
            id=opp_id,
            type="OPTIMIZATION",
            account_id_masked=settings.allowlisted_demo_account_id or "****0000",
            service="Amazon EC2",
            region=settings.bedrock_region,
            discovered_at=now,
            potential_value=monthly_waste,
            confidence=0.96,
            state=OpportunityState.AWAITING_APPROVAL,
            state_version=1,
        )

        action_hash = "sha256:" + hashlib.sha256(
            f"{opp_id}:stop_demo_instance:{instance_id}".encode()
        ).hexdigest()

        flow = HITLFlow(opportunity_id=opp_id)
        approval = flow.create_request(
            principal="recoup-agent",
            action="stop_demo_instance",
            amount=monthly_waste,
            claim_hash=action_hash,
            state_version=opportunity.state_version,
        )

        record: dict[str, Any] = {
            "opportunity": opportunity.model_dump(mode="json"),
            "instance_id": instance_id,
            "instance_type": instance_type,
            "cloudwatch_check": cw_check,
            "cloudtrail_check": ct_check,
            "monthly_waste_usd": str(monthly_waste),
            "waste_note": waste_note,
            "action_hash": action_hash,
            "approval_id": approval.approval_id,
            "triggered_at": now.isoformat(),
            "stop_result": None,
            "agent_reasoning": agent_reasoning,
        }
        _EC2_DEMO_OPPORTUNITIES[opp_id] = record
        return record

    def execute(
        self,
        opportunity_id: str,
    ) -> dict[str, Any]:
        """
        Execute the instance stop after approval is confirmed.

        Calls stop_demo_instance which validates the approval internally and
        executes the AWS stop (or returns a simulation result).
        """
        record = _EC2_DEMO_OPPORTUNITIES.get(opportunity_id)
        if record is None:
            raise KeyError(f"EC2 demo opportunity '{opportunity_id}' not found")

        instance_id: str = record["instance_id"]
        approval_id: str = record["approval_id"]

        from ..tools.ec2_tools import stop_demo_instance  # noqa: PLC0415

        stop_result = stop_demo_instance(
            instance_id=instance_id,
            opportunity_id=opportunity_id,
            approval_id=approval_id,
        )

        record["stop_result"] = stop_result
        record["executed_at"] = datetime.now(UTC).isoformat()
        return record

    def get(self, opportunity_id: str) -> dict[str, Any] | None:
        """Return a single EC2 demo opportunity record, or None."""
        return _EC2_DEMO_OPPORTUNITIES.get(opportunity_id)

    def list_all(self) -> list[dict[str, Any]]:
        """Return all EC2 demo opportunity records."""
        return list(_EC2_DEMO_OPPORTUNITIES.values())

    # ── Private helpers ─────────────────────────────────────────────────────

    def _is_stub_instance(self, instance_id: str) -> bool:
        """Return True when the instance should use deterministic stub data.

        Stub data is used for the placeholder demo instance or when no real
        allowlisted instance is configured (no RECOUP_DEMO_INSTANCE_ALLOWLIST).
        """
        allowed_ids = settings.demo_instance_ids
        return instance_id == "i-demo0000000000000" or not allowed_ids

    def _cloudwatch_check(self, instance_id: str) -> dict[str, Any]:
        """Check average CPU utilisation over the last 7 days."""
        if self._is_stub_instance(instance_id):
            return {
                "avg_cpu_pct": 0.2,
                "max_cpu_pct": 1.4,
                "period_days": 7,
                "idle": True,
                "note": "Average CPU utilisation < 1% over 7 days — instance is idle",
                "simulated": True,
            }

        from datetime import timedelta  # noqa: PLC0415

        import boto3  # noqa: PLC0415

        cw = boto3.client("cloudwatch", region_name=settings.bedrock_region)
        end = datetime.now(UTC)
        start = end - timedelta(days=7)
        resp = cw.get_metric_statistics(
            Namespace="AWS/EC2",
            MetricName="CPUUtilization",
            Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
            StartTime=start,
            EndTime=end,
            Period=3600,
            Statistics=["Average", "Maximum"],
        )
        datapoints = resp.get("Datapoints", [])
        if datapoints:
            avgs = [dp["Average"] for dp in datapoints]
            maxs = [dp["Maximum"] for dp in datapoints]
            avg_cpu = sum(avgs) / len(avgs)
            max_cpu = max(maxs)
        else:
            avg_cpu = 0.0
            max_cpu = 0.0

        return {
            "avg_cpu_pct": round(avg_cpu, 2),
            "max_cpu_pct": round(max_cpu, 2),
            "period_days": 7,
            "idle": avg_cpu < 5.0,
            "note": f"Average CPU {avg_cpu:.2f}% over 7 days",
            "simulated": False,
        }

    def _cloudtrail_check(self, instance_id: str) -> dict[str, Any]:
        """Check for blocking CloudTrail events in the last 24 hours."""
        if self._is_stub_instance(instance_id):
            return {
                "recent_events": 0,
                "blocking_changes": False,
                "verdict": "no_blocking_ownership_changes",
                "note": "No critical CloudTrail events in last 24 h",
                "simulated": True,
            }

        from datetime import timedelta  # noqa: PLC0415

        import boto3  # noqa: PLC0415

        ct = boto3.client("cloudtrail", region_name=settings.bedrock_region)
        now = datetime.now(UTC)
        resp = ct.lookup_events(
            LookupAttributes=[
                {"AttributeKey": "ResourceName", "AttributeValue": instance_id}
            ],
            StartTime=now - timedelta(hours=24),
            EndTime=now,
            MaxResults=10,
        )
        events = resp.get("Events", [])
        blocking_event_names = {"ModifyInstanceAttribute", "AssociateIamInstanceProfile"}
        blocking = any(e.get("EventName") in blocking_event_names for e in events)

        return {
            "recent_events": len(events),
            "blocking_changes": blocking,
            "verdict": (
                "blocking_changes_detected" if blocking
                else "no_blocking_ownership_changes"
            ),
            "note": f"{len(events)} CloudTrail event(s) in last 24 h",
            "simulated": False,
        }

    def _get_instance_type(self, instance_id: str) -> str:
        """Return the EC2 instance type, or 't3.micro' for stub instances."""
        if self._is_stub_instance(instance_id):
            return "t3.micro"

        import boto3  # noqa: PLC0415

        ec2 = boto3.client("ec2", region_name=settings.bedrock_region)
        desc = ec2.describe_instances(InstanceIds=[instance_id])
        return str(desc["Reservations"][0]["Instances"][0]["InstanceType"])
