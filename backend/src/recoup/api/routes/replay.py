"""
Replay API routes.

POST /api/replay/run                — run the canonical SLA replay (generic)
POST /api/replay/api-gateway-sla   — trigger the canonical API Gateway replay
GET  /api/replay/scenarios          — list all available scenarios
"""

from __future__ import annotations

import hashlib
import json as _json
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ...adapters.replay import CANONICAL_SCENARIO, ReplayAdapter
from ...approval.flow import HITLFlow
from ...config import settings
from ...graph.recoup_graph import recoup_graph
from ...graph.types import PolicyDecision
from ...notifications import notify_sns, publish_opportunity_event
from .opportunities import _graph_states as _opp_graph_states

router = APIRouter()


class ReplayRunRequest(BaseModel):
    scenario_id: str = "replay-apigateway-2026-08-sla-001"
    opportunity_id: str | None = None
    # Optional custom parameters — when provided, credit is computed dynamically
    # instead of running the full canonical graph
    availability_pct: float | None = None
    request_count: int | None = None
    error_count: int | None = None
    monthly_billing_usd: float | None = None


class ReplayResponse(BaseModel):
    opportunity_id: str
    scenario_id: str
    monthly_uptime_pct: str | None
    threshold_breached: bool | None
    tier_pct: str | None
    billed_charges: str | None
    potential_credit: str | None
    calculation_trace: list[str]
    policy_decision: str | None
    case_id: str | None
    errors: list[str]
    sse_url: str


def _run_canonical(opportunity_id: str | None) -> dict[str, Any]:
    """Execute the canonical SLA replay and return a structured result dict."""
    adapter = ReplayAdapter()
    state = adapter.build_state(CANONICAL_SCENARIO, opportunity_id=opportunity_id)

    # Stamp live_evidence when S3 evidence bucket is configured.
    # NOTE: use_strands is intentionally NOT set here — canonical SLA replay must
    # stay fully deterministic (20/20 fixture-based) so the evaluation score is
    # reproducible. Strands / Bedrock is only used in the live EC2 demo path.
    if settings.evidence_bucket:
        state = state.model_copy(update={"live_evidence": True})

    final_state = recoup_graph.run(state)

    # Ensure state_version starts at 1 so approval records have a meaningful version.
    if final_state.state_version == 0:
        final_state = final_state.model_copy(update={"state_version": 1})

    # Persist so GET /api/opportunities and GET /api/opportunities/{id} can serve it
    _opp_graph_states[final_state.opportunity_id] = final_state

    # Surface approval request in the Decision Inbox when gate fires REQUIRE_APPROVAL
    if final_state.policy_decision == PolicyDecision.REQUIRE_APPROVAL:
        result_data = final_state.availability_result
        if result_data is not None:
            claim_hash = "sha256:" + hashlib.sha256(
                _json.dumps(
                    result_data.model_dump(mode="json"), default=str, sort_keys=True
                ).encode()
            ).hexdigest()
            flow = HITLFlow(opportunity_id=final_state.opportunity_id)
            flow.create_request(
                principal="recoup-agent",
                action="submit_support_case",
                amount=result_data.potential_credit,
                claim_hash=claim_hash,
                state_version=final_state.state_version,
            )

    result = final_state.availability_result

    # SNS + SQS notifications (live AWS only, fail silently)
    if result is not None and settings.recoup_sns_topic_arn:
        credit_str = str(result.potential_credit)
        notify_sns(
            subject=f"Recoup — ${ credit_str } SLA credit opportunity detected — approval required",
            message=(
                f"Recoup detected a ${credit_str} SLA credit opportunity for Amazon API Gateway "
                f"(us-east-1) for August 2026.\n\n"
                f"Opportunity ID: {final_state.opportunity_id}\n"
                f"Monthly uptime: {result.monthly_uptime_pct}%\n"
                f"Billed charges: ${result.billed_charges}\n"
                f"Credit tier: {result.tier_pct}%\n\n"
                "Human approval is required before Recoup submits the credit claim.\n"
                "Log in to the Decision Inbox to approve."
            ),
        )
        publish_opportunity_event(
            opportunity_id=final_state.opportunity_id,
            opportunity_type="SLA_CREDIT",
            potential_value_usd=credit_str,
            service="apigateway",
            region="us-east-1",
            requires_approval=True,
        )

    # Collect evidence S3 URIs written during this run (non-empty when live_evidence=True)
    evidence_s3_uris: list[str] = []
    if final_state.evidence_manifest is not None:
        evidence_s3_uris = [
            item.storage_uri
            for item in final_state.evidence_manifest.items
            if item.storage_uri and item.storage_uri.startswith("s3://")
        ]

    eligible = (
        final_state.policy_decision == PolicyDecision.REQUIRE_APPROVAL
        and result is not None
        and result.potential_credit > 0
    )
    credit_amount = str(result.potential_credit) if result else "0"

    return {
        "opportunity_id": final_state.opportunity_id,
        "scenario_id": CANONICAL_SCENARIO.scenario_id,
        "live_evidence": final_state.live_evidence,
        "evidence_s3_uris": evidence_s3_uris,
        "evidence_bucket": settings.evidence_bucket or "recoup-evidence",
        "monthly_uptime_pct": str(result.monthly_uptime_pct) if result else None,
        "threshold_breached": result.threshold_breached if result else None,
        "tier_pct": str(result.tier_pct) if result else None,
        "billed_charges": str(result.billed_charges) if result else None,
        "potential_credit": credit_amount,
        "credit_amount": credit_amount,  # Alias — tests use this field name
        "eligible": eligible,
        "calculation_trace": result.calculation_trace if result else [],
        "policy_decision": (
            final_state.policy_decision.value if final_state.policy_decision else None
        ),
        "case_id": final_state.case_id,
        "errors": final_state.errors,
        "sse_url": f"/api/opportunities/{final_state.opportunity_id}/stream",
    }


def _run_dynamic(
    availability_pct: float,
    monthly_billing_usd: float,
    opportunity_id: str | None = None,
) -> dict[str, Any]:
    """
    Compute SLA credit dynamically from custom availability and billing parameters.

    Uses the canonical API Gateway SLA contract tiers. Does not run the full
    graph — just applies the credit formula directly.
    """
    from decimal import Decimal  # noqa: PLC0415
    from datetime import date  # noqa: PLC0415
    from ...engines.sla_resolver import resolve_sla_contract  # noqa: PLC0415
    import uuid  # noqa: PLC0415

    contract = resolve_sla_contract("apigateway", "us-east-1", date(2026, 8, 1))
    uptime = Decimal(str(availability_pct))
    threshold_breached = uptime < contract.service_commitment
    tier_pct = contract.resolve_tier(uptime)
    billing = Decimal(str(monthly_billing_usd))
    credit = (billing * tier_pct / Decimal("100")).quantize(Decimal("0.01"))
    eligible = threshold_breached and credit > Decimal("0")
    opp_id = opportunity_id or f"replay-dynamic-{uuid.uuid4().hex[:8]}"

    return {
        "opportunity_id": opp_id,
        "scenario_id": "dynamic",
        "monthly_uptime_pct": str(uptime),
        "availability_pct": float(uptime),  # numeric alias for test compatibility
        "threshold_breached": threshold_breached,
        "tier_pct": str(tier_pct),
        "billed_charges": str(billing),
        "potential_credit": str(credit),
        "credit_amount": str(credit),
        "eligible": eligible,
        "calculation_trace": [
            f"availability_pct={availability_pct}",
            f"service_commitment={contract.service_commitment}%",
            f"threshold_breached={threshold_breached}",
            f"credit_tier={tier_pct}%",
            f"credit={credit} USD",
        ],
        "policy_decision": "REQUIRE_APPROVAL" if eligible else "DENY",
        "case_id": None,
        "errors": [],
        "sse_url": f"/api/opportunities/{opp_id}/stream",
    }


@router.post("/run")
def run_replay(req: ReplayRunRequest) -> dict[str, Any]:
    """
    Execute a Verified Replay and return the result.

    When availability_pct and monthly_billing_usd are provided, credit is
    computed dynamically from those parameters. Otherwise, the canonical
    API Gateway fixture replay is run (credit = $0.35 from billing snapshot).
    """
    if req.availability_pct is not None and req.monthly_billing_usd is not None:
        return _run_dynamic(
            availability_pct=req.availability_pct,
            monthly_billing_usd=req.monthly_billing_usd,
            opportunity_id=req.opportunity_id,
        )
    return _run_canonical(req.opportunity_id)


@router.post("/api-gateway-sla")
def trigger_canonical_replay(opportunity_id: str | None = None) -> dict[str, Any]:
    """
    Trigger the canonical API Gateway SLA Verified Replay.

    Returns the full computation result including:
    - Monthly uptime %: 99.930556% (8,634 / 8,640 five-minute intervals available)
    - Credit tier: 10% (SLA commitment 99.95% breached)
    - Potential credit: 10% of real billed charges from billing_snapshot.json ($0.35 for demo account)
    - Policy decision: REQUIRE_APPROVAL (HITL gate enforced for all financial actions)

    The ``sse_url`` in the response can be used to stream node-by-node progress
    for a subsequent run via GET /api/opportunities/{id}/stream.
    """
    return _run_canonical(opportunity_id)


@router.get("/scenarios")
def list_scenarios() -> list[dict[str, Any]]:
    """Return metadata for all available replay scenarios."""
    return [
        {
            "scenario_id": CANONICAL_SCENARIO.scenario_id,
            "name": CANONICAL_SCENARIO.name,
            "description": CANONICAL_SCENARIO.description,
            "expected_credit_usd": str(CANONICAL_SCENARIO.expected_credit_usd),
            "expected_uptime_pct": str(CANONICAL_SCENARIO.expected_uptime_pct),
            "tags": CANONICAL_SCENARIO.tags,
        }
    ]
