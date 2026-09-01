"""
Opportunities REST API routes.

GET  /api/opportunities            — list all opportunities
GET  /api/opportunities/{id}       — get a single opportunity
POST /api/opportunities/{id}/run   — trigger a graph run
GET  /api/opportunities/{id}/trace — get the agent trace
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...graph.recoup_graph import recoup_graph
from ...graph.state_machine import InMemoryStateMachine, get_state_machine
from ...graph.types import GraphState
from ...models.opportunity import OpportunityState, RecoveryOpportunity
from ...models.signal import IncidentSignal

router = APIRouter()

# In-memory store for Phase 1 (replaced by DynamoDB in Phase 2)
_state_machine = InMemoryStateMachine()
_graph_states: dict[str, GraphState] = {}


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class RunRequest(BaseModel):
    signal: dict[str, Any] | None = None
    simulation_mode: bool = True


class OpportunityResponse(BaseModel):
    id: str
    state: str
    state_version: int
    simulation_mode: bool
    potential_value: str | None = None
    confidence: float | None = None
    service: str | None = None
    region: str | None = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=list[OpportunityResponse])
def list_opportunities() -> list[OpportunityResponse]:
    """Return all tracked opportunities."""
    results = []
    for opp_id, record in _state_machine.get.__self__.__dict__.get(  # type: ignore
        "_in_memory_store", {}
    ).items():
        results.append(
            OpportunityResponse(
                id=opp_id,
                state=record.get("state", OpportunityState.DETECTED.value),
                state_version=record.get("state_version", 0),
                simulation_mode=record.get("simulation_mode", True),
            )
        )
    # Fallback: enumerate from graph_states
    if not results:
        for opp_id, gs in _graph_states.items():
            results.append(
                OpportunityResponse(
                    id=opp_id,
                    state=gs.current_state.value,
                    state_version=gs.state_version,
                    simulation_mode=gs.simulation_mode,
                    potential_value=(
                        str(gs.availability_result.potential_credit)
                        if gs.availability_result else None
                    ),
                    confidence=(
                        gs.eligibility_assessment.confidence
                        if gs.eligibility_assessment else None
                    ),
                    service=gs.signal.service if gs.signal else None,
                    region=gs.signal.region if gs.signal else None,
                )
            )
    return results


@router.get("/{opportunity_id}", response_model=OpportunityResponse)
def get_opportunity(opportunity_id: str) -> OpportunityResponse:
    """Return a single opportunity by ID."""
    gs = _graph_states.get(opportunity_id)
    if gs is None:
        raise HTTPException(status_code=404, detail=f"Opportunity '{opportunity_id}' not found")
    return OpportunityResponse(
        id=opportunity_id,
        state=gs.current_state.value,
        state_version=gs.state_version,
        simulation_mode=gs.simulation_mode,
        potential_value=(
            str(gs.availability_result.potential_credit)
            if gs.availability_result else None
        ),
        confidence=(
            gs.eligibility_assessment.confidence
            if gs.eligibility_assessment else None
        ),
        service=gs.signal.service if gs.signal else None,
        region=gs.signal.region if gs.signal else None,
    )


@router.post("/{opportunity_id}/run")
def run_opportunity(opportunity_id: str, req: RunRequest) -> dict[str, Any]:
    """
    Trigger a full graph run for an opportunity.

    In Phase 1 all runs are simulation_mode=True. Pass a signal dict or leave
    it empty to use the canonical replay signal.
    """
    from ...adapters.replay import CANONICAL_SCENARIO, ReplayAdapter

    if req.signal:
        signal = IncidentSignal(**req.signal)
    else:
        adapter = ReplayAdapter()
        state = adapter.build_state(CANONICAL_SCENARIO, opportunity_id=opportunity_id)
        signal = state.signal

    initial_state = GraphState(
        opportunity_id=opportunity_id,
        simulation_mode=req.simulation_mode,
        signal=signal,
    )

    final_state = recoup_graph.run(initial_state)
    _graph_states[opportunity_id] = final_state

    return {
        "opportunity_id": opportunity_id,
        "final_state": final_state.current_state.value,
        "potential_credit": (
            str(final_state.availability_result.potential_credit)
            if final_state.availability_result else None
        ),
        "case_id": final_state.case_id,
        "errors": final_state.errors,
        "simulation_mode": final_state.simulation_mode,
    }


@router.get("/{opportunity_id}/trace")
def get_trace(opportunity_id: str) -> dict[str, Any]:
    """Return the agent trace for an opportunity (availability result + calc trace)."""
    gs = _graph_states.get(opportunity_id)
    if gs is None:
        raise HTTPException(status_code=404, detail=f"Opportunity '{opportunity_id}' not found")
    return {
        "opportunity_id": opportunity_id,
        "signal": gs.signal.model_dump(mode="json") if gs.signal else None,
        "hypothesis_summary": gs.hypothesis.summary if gs.hypothesis else None,
        "contract": (
            {"service": gs.contract.service, "version": gs.contract.version}
            if gs.contract else None
        ),
        "availability_result": (
            gs.availability_result.model_dump(mode="json") if gs.availability_result else None
        ),
        "eligibility": (
            gs.eligibility_assessment.model_dump(mode="json")
            if gs.eligibility_assessment else None
        ),
        "policy_decision": gs.policy_decision.value if gs.policy_decision else None,
        "case_id": gs.case_id,
        "case_outcome": (
            gs.case_outcome.model_dump(mode="json") if gs.case_outcome else None
        ),
        "errors": gs.errors,
    }
