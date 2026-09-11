"""
Approvals REST API routes.

GET  /api/approvals/pending              — list all pending approval requests
POST /api/approvals/{id}/approve         — approve a pending request
POST /api/approvals/{id}/decline         — decline a pending request
GET  /api/opportunities/{id}/approval   — get pending approval for an opportunity
POST /api/opportunities/{id}/approve    — approve via opportunity context
POST /api/opportunities/{id}/decline    — decline via opportunity context
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import structlog

from ...approval.flow import AUDIT_LOG_GROUP, AUDIT_LOG_STREAM, HITLFlow
from ...approval.store import (
    get_approval,
    get_pending_for_opportunity,
    list_pending_approvals,
    purge_stale_approvals,
    update_approval_state,
)
from ...config import settings
from ...models.approval import ApprovalRecord, ApprovalState
from ...models.opportunity import OpportunityState

log: structlog.BoundLogger = structlog.get_logger(__name__)


def _transition_opportunity_state(
    opportunity_id: str,
    new_state: OpportunityState,
    expected_version: int,
) -> None:
    """
    Sprint 3: Drive the OpportunityState machine for *opportunity_id*.

    Tries DynamoDB-backed state machine first (when approvals_table is
    configured), then unconditionally updates all in-memory stores so that
    GET /api/opportunities always reflects the latest state regardless of
    which persistence backend succeeded.

    Failures are logged but never block the approval API response.
    """
    # 1. Try real state machine (DynamoDB) — only when table is configured
    if settings.approvals_table:
        try:
            from ...graph.state_machine import DynamoDBStateMachine  # noqa: PLC0415

            sm = DynamoDBStateMachine()
            sm.transition(
                opportunity_id=opportunity_id,
                new_state=new_state,
                expected_version=expected_version,
            )
            log.info(
                "state_machine.transition",
                opportunity_id=opportunity_id,
                new_state=new_state.value,
                via="dynamodb",
            )
        except Exception as exc:  # noqa: BLE001
            log.debug("state_machine.dynamo_transition_skipped", error=str(exc))

    # 2. Always update in-memory _graph_states (for promote-based opportunities)
    try:
        from .opportunities import _graph_states  # noqa: PLC0415

        if opportunity_id in _graph_states:
            gs = _graph_states[opportunity_id]
            new_version = gs.state_version + 1
            _graph_states[opportunity_id] = gs.model_copy(
                update={"current_state": new_state, "state_version": new_version}
            )
            log.info(
                "state_machine.transition",
                opportunity_id=opportunity_id,
                new_state=new_state.value,
                new_version=new_version,
                via="in_memory",
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("state_machine.transition_failed", error=str(exc))

router = APIRouter()

# ---------------------------------------------------------------------------
# Shared request/response models
# ---------------------------------------------------------------------------


class ApprovalDecision(BaseModel):
    principal: str
    notes: str = ""


class ApproveRequest(BaseModel):
    """Request body for the approve endpoint — binds to claim + amount + version."""

    principal: str
    claim_hash: str
    amount: Decimal
    state_version: int
    notes: str = ""


# ---------------------------------------------------------------------------
# Global approval list
# ---------------------------------------------------------------------------


@router.get("/pending")
def list_pending() -> list[dict[str, Any]]:
    """Return all non-expired PENDING approval requests (across all opportunities)."""
    records = list_pending_approvals()
    return [_approval_to_json(r) for r in records]


def _approval_to_json(record: ApprovalRecord) -> dict[str, Any]:
    """Serialise for the Decision Inbox UI."""
    data = record.model_dump(mode="json")
    data["requested_at"] = data.get("timestamp", data.get("requested_at"))
    return data


@router.post("/{approval_id}/approve")
def approve_by_id(approval_id: str, body: ApprovalDecision) -> dict[str, Any]:
    """
    Simple approve endpoint — no binding assertions.

    Use the opportunity-scoped ``/api/opportunities/{id}/approve`` endpoint
    for full binding validation (claim_hash + amount + state_version).
    """
    record = get_approval(approval_id)
    if record is None:
        raise HTTPException(404, f"Approval '{approval_id}' not found")
    if record.state != ApprovalState.PENDING:
        raise HTTPException(409, f"Approval is already in state '{record.state}'")
    if record.is_expired:
        raise HTTPException(409, "Approval has expired")

    updated = update_approval_state(
        approval_id,
        ApprovalState.APPROVED,
        decided_by=body.principal,
        notes=body.notes,
    )
    assert updated is not None
    return {"approval_id": approval_id, "state": str(updated.state)}


@router.post("/{approval_id}/decline")
def decline_by_id(approval_id: str, body: ApprovalDecision) -> dict[str, Any]:
    """Decline a pending HITL request."""
    record = get_approval(approval_id)
    if record is None:
        raise HTTPException(404, f"Approval '{approval_id}' not found")
    if record.state != ApprovalState.PENDING:
        raise HTTPException(409, f"Approval is already in state '{record.state}'")

    updated = update_approval_state(
        approval_id,
        ApprovalState.DECLINED,
        decided_by=body.principal,
        notes=body.notes,
    )
    assert updated is not None
    return {"approval_id": approval_id, "state": str(updated.state)}


# ---------------------------------------------------------------------------
# Opportunity-scoped approval endpoints (Decision Inbox)
# ---------------------------------------------------------------------------


@router.get("/opportunity/{opportunity_id}")
def get_opportunity_approval(
    opportunity_id: str,
) -> ApprovalRecord | None:
    """Return the PENDING approval record for an opportunity, or null if none pending."""
    record = get_pending_for_opportunity(opportunity_id)
    return record


@router.post("/opportunity/{opportunity_id}/approve")
def approve_opportunity(
    opportunity_id: str,
    body: ApproveRequest,
) -> dict[str, Any]:
    """
    Approve an opportunity claim with full binding validation.

    Validates:
    - claim_hash matches the approval record
    - amount matches exactly
    - state_version matches
    - approval has not expired
    """
    pending = get_pending_for_opportunity(opportunity_id)
    if pending is None:
        raise HTTPException(
            404, f"No pending approval found for opportunity '{opportunity_id}'"
        )

    flow = HITLFlow(opportunity_id=opportunity_id)
    try:
        updated = flow.approve(
            approval_id=pending.approval_id,
            principal=body.principal,
            claim_hash=body.claim_hash,
            amount=body.amount,
            state_version=body.state_version,
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc

    result = updated.model_dump(mode="json")
    result["_aws"] = {
        "dynamodb_table": settings.approvals_table,
        "audit_log_group": AUDIT_LOG_GROUP,
        "audit_log_stream": AUDIT_LOG_STREAM,
        "live": True,
    }
    result["sns_notification_sent"] = flow.last_sns_notification_sent

    # Sprint 3: drive state machine AWAITING_APPROVAL → APPROVED
    _transition_opportunity_state(
        opportunity_id=opportunity_id,
        new_state=OpportunityState.APPROVED,
        expected_version=body.state_version,
    )

    # For non-live-EC2 actions (SLA claims, cost optimisations), replay mode
    # executes the action immediately, so we also advance to RECOVERED so the
    # Recovery Ledger "Recovered" bucket and the "Record" pipeline step light up.
    # Live EC2 stops are recorded as RECOVERED when the execute step runs.
    if updated.action != "stop_demo_instance":
        _transition_opportunity_state(
            opportunity_id=opportunity_id,
            new_state=OpportunityState.RECOVERED,
            expected_version=body.state_version,
        )

    return result


@router.post("/opportunity/{opportunity_id}/investigate")
def investigate_opportunity(
    opportunity_id: str,
    body: ApprovalDecision,
) -> dict[str, Any]:
    """
    Mark an opportunity for further investigation (NEEDS_FOLLOWUP state).

    This is a distinct action from Decline — the opportunity remains visible
    in the Decision Inbox under an "Under Investigation" section rather than
    being dismissed.
    """
    pending = get_pending_for_opportunity(opportunity_id)
    if pending is None:
        raise HTTPException(
            404, f"No pending approval found for opportunity '{opportunity_id}'"
        )

    flow = HITLFlow(opportunity_id=opportunity_id)
    updated = flow.decline(
        approval_id=pending.approval_id,
        principal=body.principal,
        notes=f"[INVESTIGATE] {body.notes}" if body.notes else "[INVESTIGATE] Sent for further investigation",
    )

    # Sprint 3: drive state machine AWAITING_APPROVAL → NEEDS_FOLLOWUP
    _transition_opportunity_state(
        opportunity_id=opportunity_id,
        new_state=OpportunityState.NEEDS_FOLLOWUP,
        expected_version=pending.state_version,
    )

    return {
        "approval_id": updated.approval_id,
        "state": str(updated.state),  # DECLINED (the approval record state)
        "opportunity_state": "NEEDS_FOLLOWUP",
        "_aws": {
            "dynamodb_table": settings.approvals_table,
            "audit_log_group": AUDIT_LOG_GROUP,
            "audit_log_stream": AUDIT_LOG_STREAM,
            "live": True,
        },
    }


@router.post("/opportunity/{opportunity_id}/decline")
def decline_opportunity(
    opportunity_id: str,
    body: ApprovalDecision,
) -> dict[str, Any]:
    """Decline a pending opportunity approval."""
    pending = get_pending_for_opportunity(opportunity_id)
    if pending is None:
        raise HTTPException(
            404, f"No pending approval found for opportunity '{opportunity_id}'"
        )

    flow = HITLFlow(opportunity_id=opportunity_id)
    updated = flow.decline(
        approval_id=pending.approval_id,
        principal=body.principal,
        notes=body.notes,
    )

    # Sprint 3: drive state machine AWAITING_APPROVAL → DENIED
    # (approval record state remains DECLINED; opportunity state becomes DENIED)
    _transition_opportunity_state(
        opportunity_id=opportunity_id,
        new_state=OpportunityState.DENIED,
        expected_version=pending.state_version,
    )

    return {
        "approval_id": updated.approval_id,
        "state": str(updated.state),
        "_aws": {
            "dynamodb_table": settings.approvals_table,
            "audit_log_group": AUDIT_LOG_GROUP,
            "audit_log_stream": AUDIT_LOG_STREAM,
            "live": True,
        },
    }


# ---------------------------------------------------------------------------
# Outcomes — expose the outcome_repo so the ledger survives server restarts
# ---------------------------------------------------------------------------


@router.get("/outcomes")
def list_outcomes() -> list[dict[str, Any]]:
    """
    Return all outcome records from the OutcomeRepository.

    Powers the persistent "Recovered" bucket in the Recovery Ledger — unlike
    in-memory _graph_states, outcome records are written to DynamoDB (or
    in-memory fallback) and survive across server restarts.
    """
    try:
        from ...graph.outcome_repository import outcome_repo  # noqa: PLC0415
        return outcome_repo.list_all()
    except Exception as exc:  # noqa: BLE001
        log.warning("approvals.outcomes_fetch_failed", error=str(exc))
        return []


# ---------------------------------------------------------------------------
# Admin: purge stale PENDING approvals
# ---------------------------------------------------------------------------


@router.post("/purge-stale")
def purge_stale() -> dict[str, Any]:
    """
    Revoke all PENDING approvals whose opportunity_id no longer exists in the
    current server session (i.e., the opportunity was created before the last
    server restart and its in-memory GraphState has been lost).

    Safe to call at any time; approved/declined records are never touched.
    Returns the number of records revoked.
    """
    try:
        from .opportunities import _graph_states  # noqa: PLC0415
        live_ids = set(_graph_states.keys())
    except Exception:  # noqa: BLE001
        live_ids = set()

    revoked = purge_stale_approvals(live_opportunity_ids=live_ids)
    log.info("approvals.purge_stale", revoked=revoked, live_opportunities=len(live_ids))
    return {
        "revoked": revoked,
        "live_opportunities": len(live_ids),
        "message": f"Revoked {revoked} stale PENDING approval(s).",
    }
