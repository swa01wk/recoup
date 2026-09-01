"""
Replay API routes.

POST /api/replay/run               — run the canonical $1,840 replay
GET  /api/replay/scenarios         — list all available scenarios
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ...adapters.replay import CANONICAL_SCENARIO, ReplayAdapter
from ...graph.recoup_graph import recoup_graph

router = APIRouter()


class ReplayRunRequest(BaseModel):
    scenario_id: str = "replay-apigateway-2026-08-sla-001"
    opportunity_id: str | None = None


@router.post("/run")
def run_replay(req: ReplayRunRequest) -> dict[str, Any]:
    """
    Execute a Verified Replay and return the result.

    The canonical scenario always produces exactly $1,840.00 credit.
    """
    adapter = ReplayAdapter()
    state = adapter.build_state(
        CANONICAL_SCENARIO, opportunity_id=req.opportunity_id
    )

    final_state = recoup_graph.run(state)

    result = final_state.availability_result
    return {
        "opportunity_id": final_state.opportunity_id,
        "scenario_id": CANONICAL_SCENARIO.scenario_id,
        "simulation_mode": True,
        "monthly_uptime_pct": str(result.monthly_uptime_pct) if result else None,
        "threshold_breached": result.threshold_breached if result else None,
        "tier_pct": str(result.tier_pct) if result else None,
        "billed_charges": str(result.billed_charges) if result else None,
        "potential_credit": str(result.potential_credit) if result else None,
        "calculation_trace": result.calculation_trace if result else [],
        "case_id": final_state.case_id,
        "errors": final_state.errors,
    }


@router.get("/scenarios")
def list_scenarios() -> list[dict[str, Any]]:
    """Return metadata for all available replay scenarios."""
    return [
        {
            "scenario_id": CANONICAL_SCENARIO.scenario_id,
            "name": CANONICAL_SCENARIO.name,
            "description": CANONICAL_SCENARIO.description,
            "expected_credit_usd": str(CANONICAL_SCENARIO.expected_credit_usd),
            "tags": CANONICAL_SCENARIO.tags,
        }
    ]
