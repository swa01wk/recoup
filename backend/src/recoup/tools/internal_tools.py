"""
Internal write tools — evidence store, approval, and simulation.

These tools write to internal Recoup infrastructure (S3, DynamoDB) and
never communicate with external AWS services directly.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
from decimal import Decimal
from typing import Any

from strands import tool


# ---------------------------------------------------------------------------
# Evidence store
# ---------------------------------------------------------------------------


@tool
def store_evidence(
    opportunity_id: str,
    field_name: str,
    content_json: str,
    sensitivity: str = "MEDIUM",
) -> dict[str, Any]:
    """
    Store raw evidence to the encrypted evidence S3 bucket.

    Raw evidence is stored encrypted and never returned to the agent.
    Returns only the evidence ID, S3 URI, and SHA-256 hash.
    Allowed nodes: evidence_collector, claim_package_generator.

    Args:
        opportunity_id: The opportunity this evidence belongs to.
        field_name: Evidence field name (e.g. 'request_logs', 'billing_record').
        content_json: JSON-serialised evidence content to store.
        sensitivity: 'LOW', 'MEDIUM', or 'HIGH' — determines encryption tier.

    Returns:
        {'evidence_id', 'storage_uri', 'hash', 'stored_at'}
    """
    content_bytes = content_json.encode()
    content_hash = "sha256:" + hashlib.sha256(content_bytes).hexdigest()
    evidence_id = f"ev-{hashlib.sha256(f'{opportunity_id}:{field_name}'.encode()).hexdigest()[:8]}"
    storage_uri = f"s3://recoup-evidence/{opportunity_id}/{field_name}.json"

    # Phase 1: stub — no actual S3 write
    return {
        "evidence_id": evidence_id,
        "storage_uri": storage_uri,
        "hash": content_hash,
        "stored_at": _utcnow().isoformat(),
        "_stub": True,
    }


# ---------------------------------------------------------------------------
# Approval
# ---------------------------------------------------------------------------


@tool
def create_approval_request(
    opportunity_id: str,
    principal: str,
    action: str,
    amount_usd: str,
    claim_hash: str,
    state_version: int,
    ttl_hours: int = 24,
) -> dict[str, Any]:
    """
    Create a HITL approval request for a financial action.

    Writes a pending ApprovalRecord to DynamoDB with a TTL. The record is
    bound to the current state_version — stale approvals are automatically
    rejected by the submission_adapter.
    Allowed nodes: risk_policy_gate.

    Args:
        opportunity_id: The opportunity requiring approval.
        principal: Identity of the person/role being asked to approve.
        action: Description of the action (e.g. 'submit_sla_claim').
        amount_usd: Dollar amount to display to the approver.
        claim_hash: SHA-256 of the ClaimPackage JSON.
        state_version: Current state version — approval is bound to this.
        ttl_hours: Expiry window in hours (default 24).

    Returns:
        {'approval_id', 'state', 'expires_at', 'approval_url'}
    """
    approval_id = str(uuid.uuid4())
    expires_at = (_utcnow() + timedelta(hours=ttl_hours)).isoformat()

    # Phase 1: stub — no DynamoDB write
    return {
        "approval_id": approval_id,
        "opportunity_id": opportunity_id,
        "action": action,
        "amount_usd": amount_usd,
        "claim_hash": claim_hash,
        "state_version": state_version,
        "state": "PENDING",
        "expires_at": expires_at,
        "approval_url": f"/decisions/{opportunity_id}?approval={approval_id}",
        "_stub": True,
    }


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------


@tool
def simulate_support_case(
    opportunity_id: str,
    claim_subject: str,
    billing_cycle: str,
    potential_credit_usd: str,
    calculator_result_hash: str,
) -> dict[str, Any]:
    """
    Produce a deterministic simulated AWS Support case ID without real submission.

    The case ID is derived from the calculator result hash so every replay of
    the same scenario produces the same case ID (replay reproducibility).
    Allowed nodes: submission_adapter.

    Args:
        opportunity_id: Opportunity identifier.
        claim_subject: Claim subject line.
        billing_cycle: Billing cycle (e.g. '2026-08').
        potential_credit_usd: Credit amount string (for display).
        calculator_result_hash: SHA-256 of the AvailabilityResult JSON.

    Returns:
        {'case_id', 'simulated': True, 'submitted_at', 'subject', 'status'}
    """
    case_id = "sim-" + hashlib.sha256(calculator_result_hash.encode()).hexdigest()[:12]
    return {
        "case_id": case_id,
        "simulated": True,
        "submitted_at": _utcnow().isoformat(),
        "subject": claim_subject,
        "status": "pending-customer-action",
        "billing_cycle": billing_cycle,
        "potential_credit_usd": potential_credit_usd,
    }
