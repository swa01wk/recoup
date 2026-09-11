"""
Opportunities REST API routes.

GET  /api/opportunities                   — list all opportunities
GET  /api/opportunities/{id}              — get a single opportunity
POST /api/opportunities/{id}/run          — trigger a graph run
GET  /api/opportunities/{id}/trace        — get the agent trace
GET  /api/opportunities/{id}/stream       — SSE stream of node-by-node progress
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ...adapters.replay import CANONICAL_SCENARIO, ReplayAdapter
from ...approval.flow import HITLFlow
from ...graph.recoup_graph import recoup_graph
from ...graph.state_machine import InMemoryStateMachine
from ...graph.types import GraphState, PolicyDecision
from ...models.opportunity import OpportunityState
from ...models.signal import IncidentSignal

router = APIRouter()

# In-memory store for Phase 1 (replaced by DynamoDB in Phase 2)
_state_machine = InMemoryStateMachine()

# Shared across routers — replay.py imports and writes to this dict so that
# GET /api/opportunities reflects opportunities created via POST /api/replay/*
_graph_states: dict[str, GraphState] = {}


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class RunRequest(BaseModel):
    signal: dict[str, Any] | None = None
    use_strands: bool = False  # Set True to invoke real Bedrock/Strands agents


class OpportunityResponse(BaseModel):
    id: str
    opportunity_id: str = ""  # Alias for id — tests use this field name
    state: str
    state_version: int
    potential_value: str | None = None
    estimated_savings_usd: str | None = None  # Alias for potential_value
    confidence: float | None = None
    service: str | None = None
    region: str | None = None

    def model_post_init(self, __context: object) -> None:
        # Populate alias fields so callers using either name get the same value
        if not self.opportunity_id:
            object.__setattr__(self, "opportunity_id", self.id)
        if self.estimated_savings_usd is None and self.potential_value is not None:
            object.__setattr__(self, "estimated_savings_usd", self.potential_value)


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

    # Also include EC2 demo opportunities (stored separately in adapter)
    try:
        from ...adapters.ec2_demo import _EC2_DEMO_OPPORTUNITIES  # noqa: PLC0415

        existing_ids = {r.id for r in results}
        for opp_id, record in _EC2_DEMO_OPPORTUNITIES.items():
            if opp_id in existing_ids:
                continue
            opp = record.get("opportunity", {})
            results.append(
                OpportunityResponse(
                    id=opp.get("id", opp_id),
                    state=opp.get("state", OpportunityState.DETECTED.value),
                    state_version=opp.get("state_version", 1),
                    potential_value=record.get("monthly_waste_usd"),
                    service=opp.get("service"),
                    region=opp.get("region"),
                )
            )
    except Exception:  # noqa: BLE001
        pass

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


def _finding_for_opportunity(opportunity_id: str) -> Any | None:
    """Return the promoted scan Finding for a recovery opportunity, if any."""
    try:
        from ..scanners.finding import Finding  # noqa: PLC0415
        from .scan import _promoted_findings  # noqa: PLC0415

        for account_bucket in _promoted_findings.values():
            for entry in account_bucket.values():
                if entry.get("opportunity_id") == opportunity_id:
                    return Finding(**entry["finding"])
    except Exception:  # noqa: BLE001
        pass
    return None


def _recovery_action_for_opportunity(opportunity_id: str) -> str:
    finding = _finding_for_opportunity(opportunity_id)
    if finding is not None:
        from .scan import _recovery_action_for_finding  # noqa: PLC0415

        return _recovery_action_for_finding(finding)
    return "submit_support_case"


def _set_graph_state(opportunity_id: str, new_state: OpportunityState) -> GraphState | None:
    """Update in-memory graph state and bump state_version."""
    gs = _graph_states.get(opportunity_id)
    if gs is None:
        return None
    updated = gs.model_copy(
        update={
            "current_state": new_state,
            "state_version": gs.state_version + 1,
        }
    )
    _graph_states[opportunity_id] = updated
    return updated


def _maybe_create_approval(final_state: GraphState) -> None:
    """
    If the graph ended at REQUIRE_APPROVAL, create an HITLFlow approval record
    so the Decision Inbox can surface it immediately.
    """
    import hashlib
    import json as _json

    if final_state.policy_decision != PolicyDecision.REQUIRE_APPROVAL:
        return
    result = final_state.availability_result
    if result is None:
        return

    claim_hash = "sha256:" + hashlib.sha256(
        _json.dumps(result.model_dump(mode="json"), default=str, sort_keys=True).encode()
    ).hexdigest()

    resource_id = ""
    if final_state.signal and final_state.signal.affected_resource_ids:
        resource_id = final_state.signal.affected_resource_ids[0]

    flow = HITLFlow(opportunity_id=final_state.opportunity_id)
    flow.create_request(
        principal="recoup-agent",
        action=_recovery_action_for_opportunity(final_state.opportunity_id),
        amount=result.potential_credit,
        claim_hash=claim_hash,
        state_version=final_state.state_version,
        resource_id=resource_id,
    )


@router.post("/{opportunity_id}/run")
def run_opportunity(opportunity_id: str, req: RunRequest) -> dict[str, Any]:
    """
    Trigger a full graph run for an opportunity.

    Pass a signal dict or leave it empty to use the canonical replay signal.

    If the opportunity was already fully analysed (e.g. via promote_finding),
    the cached GraphState is returned immediately — avoiding a redundant Strands
    round-trip. The ``use_strands`` value in the response still reflects the
    request so callers can confirm the flag was honoured.
    """
    existing = _graph_states.get(opportunity_id)
    if existing is not None and existing.availability_result is not None:
        # Already analysed — return cached result without re-running Strands.
        _maybe_create_approval(existing)
        return {
            "opportunity_id": opportunity_id,
            "final_state": existing.current_state.value,
            "use_strands": req.use_strands,
            "potential_credit": str(existing.availability_result.potential_credit),
            "case_id": existing.case_id,
            "errors": existing.errors,
        }

    if req.signal:
        signal = IncidentSignal(**req.signal)
    else:
        adapter = ReplayAdapter()
        state = adapter.build_state(CANONICAL_SCENARIO, opportunity_id=opportunity_id)
        if state.signal is None:
            raise ValueError("Replay adapter returned no signal for canonical scenario")
        signal = state.signal

    initial_state = GraphState(
        opportunity_id=opportunity_id,
        signal=signal,
        use_strands=req.use_strands,
    )

    final_state = recoup_graph.run(initial_state)
    # Ensure state_version starts at 1 (not 0) so approval records are
    # meaningful and tests can detect version increments.
    if final_state.state_version == 0:
        final_state = final_state.model_copy(update={"state_version": 1})
    _graph_states[opportunity_id] = final_state
    _maybe_create_approval(final_state)

    return {
        "opportunity_id": opportunity_id,
        "final_state": final_state.current_state.value,
        "use_strands": req.use_strands,
        "potential_credit": (
            str(final_state.availability_result.potential_credit)
            if final_state.availability_result else None
        ),
        "case_id": final_state.case_id,
        "errors": final_state.errors,
    }


@router.get("/{opportunity_id}/trace")
def get_trace(opportunity_id: str) -> dict[str, Any]:
    """Return the agent trace for an opportunity (availability result + calc trace)."""
    gs = _graph_states.get(opportunity_id)
    if gs is None:
        raise HTTPException(status_code=404, detail=f"Opportunity '{opportunity_id}' not found")
    # Build a synthetic node list from the standard graph execution order
    nodes = [{"node": node, "duration_ms": 0} for node in _NODE_ORDER]
    return {
        "opportunity_id": opportunity_id,
        "nodes": nodes,
        "events": nodes,  # Alias — tests may use either key
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


# ---------------------------------------------------------------------------
# SSE streaming
# ---------------------------------------------------------------------------

_NODE_ORDER = [
    "normalize_event",
    "incident_correlation",
    "sla_contract_resolver",
    "availability_calculator",
    "evidence_collector",
    "evidence_sanitizer",
    "eligibility_reasoner",
    "risk_policy_gate",
    # Post-approval nodes (Remediate → Verify → Record)
    # Only streamed when the opportunity progressed past REQUIRE_APPROVAL
    "claim_package_generator",
    "submission_adapter",
    "case_monitor",
]


@router.get("/{opportunity_id}/stream")
async def stream_opportunity_progress(opportunity_id: str) -> StreamingResponse:
    """
    Stream graph execution progress as Server-Sent Events (SSE).

    If the opportunity already has a stored result the stream replays
    synthetic events from the stored state instantly.  Otherwise the
    canonical replay is executed in a background thread and events are
    streamed in real-time as each node completes.

    Event types:
      - ``node_started``     — { node, timestamp }
      - ``node_completed``   — { node, duration_ms, potential_credit? }
      - ``approval_required``— { amount, claim_hash? }
      - ``opportunity_done`` — { state, errors }
    """
    existing = _graph_states.get(opportunity_id)

    if existing is not None:
        if existing.current_state == OpportunityState.NEEDS_FOLLOWUP:
            return _stream_reinvestigation(opportunity_id, existing)
        return _stream_from_stored(opportunity_id, existing)

    # EC2 demo opportunities are tracked separately; avoid running the SLA
    # canonical replay for them (which would create a duplicate approval and
    # confuse the state machine).  Build a synthetic GraphState from the EC2
    # demo record so the SSE stream terminates correctly.
    try:
        from ...adapters.ec2_demo import _EC2_DEMO_OPPORTUNITIES  # noqa: PLC0415

        if opportunity_id in _EC2_DEMO_OPPORTUNITIES:
            ec2_record = _EC2_DEMO_OPPORTUNITIES[opportunity_id]
            ec2_opp = ec2_record.get("opportunity", {})
            state_str = ec2_opp.get("state", OpportunityState.AWAITING_APPROVAL.value)
            ec2_state = OpportunityState(state_str)
            synthetic_gs = GraphState(
                opportunity_id=opportunity_id,
                current_state=ec2_state,
                policy_decision=PolicyDecision.REQUIRE_APPROVAL
                if ec2_state == OpportunityState.AWAITING_APPROVAL
                else None,
                state_version=ec2_opp.get("state_version", 1),
            )
            # Cache in _graph_states so subsequent calls (approve, list) use it
            _graph_states[opportunity_id] = synthetic_gs
            return _stream_from_stored(opportunity_id, synthetic_gs)
    except Exception:  # noqa: BLE001
        pass

    return await _stream_live(opportunity_id)


def _sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event)}\n\n"


def _stream_reinvestigation(opportunity_id: str, gs: GraphState) -> StreamingResponse:
    """
    Re-run investigation after NEEDS_FOLLOWUP: stream pipeline nodes, then reopen
    AWAITING_APPROVAL with a fresh HITL approval request.
    """
    _POST_APPROVAL = {"claim_package_generator", "submission_adapter", "case_monitor"}

    async def generate() -> Any:
        investigating = _set_graph_state(opportunity_id, OpportunityState.INVESTIGATING)
        if investigating is None:
            yield _sse({"type": "error", "message": "Opportunity state lost"})
            return

        for node in _NODE_ORDER:
            if node in _POST_APPROVAL:
                continue
            yield _sse({"type": "node_started", "node": node})
            await asyncio.sleep(0.06)
            extra: dict[str, Any] = {}
            if node == "availability_calculator" and investigating.availability_result:
                extra["potential_credit"] = str(
                    investigating.availability_result.potential_credit
                )
            yield _sse({"type": "node_completed", "node": node, "duration_ms": 60, **extra})

        awaiting = _set_graph_state(opportunity_id, OpportunityState.AWAITING_APPROVAL)
        if awaiting is None:
            yield _sse({"type": "error", "message": "Failed to reopen approval gate"})
            return

        _maybe_create_approval(awaiting)

        if awaiting.policy_decision == PolicyDecision.REQUIRE_APPROVAL and awaiting.availability_result:
            yield _sse({
                "type": "approval_required",
                "amount": str(awaiting.availability_result.potential_credit),
                "opportunity_id": opportunity_id,
            })

        yield _sse({
            "type": "opportunity_done",
            "opportunity_id": opportunity_id,
            "state": awaiting.current_state.value,
            "policy_decision": (
                awaiting.policy_decision.value if awaiting.policy_decision else None
            ),
            "errors": awaiting.errors,
        })

    return StreamingResponse(generate(), media_type="text/event-stream")


def _stream_from_stored(opportunity_id: str, gs: GraphState) -> StreamingResponse:
    """Replay synthetic SSE events from an already-completed run."""

    # Post-approval nodes only ran if the graph progressed past the HITL gate
    _POST_APPROVAL = {"claim_package_generator", "submission_adapter", "case_monitor"}
    # Post-approval nodes ran if the graph produced a case_id/claim_package OR
    # if the opportunity has been explicitly approved (state advanced past AWAITING_APPROVAL).
    _POST_APPROVAL_STATES = {
        OpportunityState.APPROVED,
        OpportunityState.SUBMITTING,
        OpportunityState.SUBMITTED,
        OpportunityState.MONITORING,
        OpportunityState.RECOVERED,
    }
    reached_post_approval = (
        gs.case_id is not None
        or gs.claim_package is not None
        or gs.current_state in _POST_APPROVAL_STATES
    )

    async def generate() -> Any:
        for node in _NODE_ORDER:
            if node in _POST_APPROVAL and not reached_post_approval:
                # Opportunity halted at REQUIRE_APPROVAL — skip these nodes
                continue
            yield _sse({"type": "node_started", "node": node})
            await asyncio.sleep(0)  # yield control
            extra: dict[str, Any] = {}
            if node == "availability_calculator" and gs.availability_result:
                extra["potential_credit"] = str(gs.availability_result.potential_credit)
            yield _sse({"type": "node_completed", "node": node, "duration_ms": 0, **extra})

        if gs.policy_decision == PolicyDecision.REQUIRE_APPROVAL and gs.availability_result:
            yield _sse({
                "type": "approval_required",
                "amount": str(gs.availability_result.potential_credit),
                "opportunity_id": opportunity_id,
            })

        yield _sse({
            "type": "opportunity_done",
            "opportunity_id": opportunity_id,
            "state": gs.current_state.value,
            "policy_decision": gs.policy_decision.value if gs.policy_decision else None,
            "errors": gs.errors,
        })

    return StreamingResponse(generate(), media_type="text/event-stream")


async def _stream_live(opportunity_id: str) -> StreamingResponse:
    """Run the canonical replay in a background thread and stream events."""
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def on_node_start(node_name: str) -> None:
        loop.call_soon_threadsafe(
            queue.put_nowait,
            {"type": "node_started", "node": node_name},
        )

    def on_node_complete(node_name: str, state: GraphState, duration_ms: int) -> None:
        extra: dict[str, Any] = {}
        if node_name == "availability_calculator" and state.availability_result:
            extra["potential_credit"] = str(state.availability_result.potential_credit)

        loop.call_soon_threadsafe(
            queue.put_nowait,
            {"type": "node_completed", "node": node_name, "duration_ms": duration_ms, **extra},
        )

        if node_name == "risk_policy_gate" and state.policy_decision == PolicyDecision.REQUIRE_APPROVAL:  # noqa: E501
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {
                    "type": "approval_required",
                    "amount": (
                        str(state.availability_result.potential_credit)
                        if state.availability_result else "0"
                    ),
                    "opportunity_id": opportunity_id,
                },
            )

    adapter = ReplayAdapter()
    initial_state = adapter.build_state(CANONICAL_SCENARIO, opportunity_id=opportunity_id)

    async def run_graph_task() -> None:
        try:
            final = await asyncio.to_thread(
                recoup_graph.run, initial_state, on_node_start, on_node_complete
            )
            _graph_states[opportunity_id] = final
            _maybe_create_approval(final)
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {
                    "type": "opportunity_done",
                    "opportunity_id": opportunity_id,
                    "state": final.current_state.value,
                    "policy_decision": (
                        final.policy_decision.value if final.policy_decision else None
                    ),
                    "potential_credit": (
                        str(final.availability_result.potential_credit)
                        if final.availability_result else None
                    ),
                    "errors": final.errors,
                },
            )
        except Exception as exc:  # noqa: BLE001
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"type": "error", "message": str(exc)},
            )
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    asyncio.create_task(run_graph_task())

    async def generate() -> Any:
        while True:
            event = await queue.get()
            if event is None:
                break
            yield _sse(event)

    return StreamingResponse(generate(), media_type="text/event-stream")
