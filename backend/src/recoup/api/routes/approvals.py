"""
Approvals REST API routes.

GET  /api/approvals/pending          — list pending approval requests
POST /api/approvals/{id}/approve     — approve a pending request
POST /api/approvals/{id}/decline     — decline a pending request
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...models.approval import ApprovalRecord, ApprovalState

router = APIRouter()

# In-memory approval store (replaced by DynamoDB in Phase 3)
_approvals: dict[str, dict[str, Any]] = {}


class ApprovalDecision(BaseModel):
    principal: str
    notes: str = ""


@router.get("/pending")
def list_pending() -> list[dict[str, Any]]:
    """Return all PENDING approval requests."""
    return [
        v for v in _approvals.values()
        if v.get("state") == ApprovalState.PENDING.value
    ]


@router.post("/{approval_id}/approve")
def approve(approval_id: str, body: ApprovalDecision) -> dict[str, Any]:
    """Approve a pending HITL request."""
    record = _approvals.get(approval_id)
    if not record:
        raise HTTPException(404, f"Approval '{approval_id}' not found")
    if record["state"] != ApprovalState.PENDING.value:
        raise HTTPException(409, f"Approval is already in state '{record['state']}'")
    record["state"] = ApprovalState.APPROVED.value
    record["decided_by"] = body.principal
    record["notes"] = body.notes
    return {"approval_id": approval_id, "state": record["state"]}


@router.post("/{approval_id}/decline")
def decline(approval_id: str, body: ApprovalDecision) -> dict[str, Any]:
    """Decline a pending HITL request."""
    record = _approvals.get(approval_id)
    if not record:
        raise HTTPException(404, f"Approval '{approval_id}' not found")
    if record["state"] != ApprovalState.PENDING.value:
        raise HTTPException(409, f"Approval is already in state '{record['state']}'")
    record["state"] = ApprovalState.DECLINED.value
    record["decided_by"] = body.principal
    record["notes"] = body.notes
    return {"approval_id": approval_id, "state": record["state"]}
