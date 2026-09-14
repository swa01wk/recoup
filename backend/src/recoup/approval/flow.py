"""
HITL Approval Flow — manages the full lifecycle of a human approval request.

Lifecycle:
    create_request()  → PENDING  (expires_at = now + 24h)
    approve()         → APPROVED (bound to claim hash + state version + amount)
    decline()         → DECLINED
    revoke()          → REVOKED  (called if state changes after approval)
    check_expired()   → EXPIRED  (called by policy gate before submission)

Security properties:
    - Approval is cryptographically bound to ``claim_hash`` (SHA-256 of the
      ClaimPackage JSON) so a regenerated package cannot reuse an old approval.
    - ``state_version`` binding prevents stale approvals from authorising a
      submission after the opportunity state was changed.
    - ``amount`` binding prevents submitting a different credit amount than
      the one the human reviewed.
    - ``expires_at`` (24h TTL) ensures time-bounded authority.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import structlog

from ..models.approval import ApprovalRecord, ApprovalState
from .store import (
    get_pending_for_opportunity,
    save_approval,
    update_approval_state,
)

log: structlog.BoundLogger = structlog.get_logger(__name__)

AUDIT_LOG_GROUP = "/recoup/runtime"
AUDIT_LOG_STREAM = "hitl-approvals"


def _derive_approval_context(
    action: str,
    amount: Decimal,
) -> tuple[str, str, str]:
    """Return (risk_tier, action_description, rollback_context) for Decision Inbox UI."""
    amt = f"${amount:,.2f}"
    if action == "stop_demo_instance":
        return (
            "RED",
            "Stop EC2 demo instance (RecoupDemo allowlist verified)",
            f"Reversible: restart instance within 24h · Estimated recovery: {amt}/mo",
        )
    if action == "submit_support_case":
        return (
            "YELLOW",
            f"Submit {amt} SLA credit claim to AWS Support",
            "Withdraw claim within 24h before submission completes",
        )
    return (
        "YELLOW",
        f"Execute recovery action: {action.replace('_', ' ')} ({amt}/mo)",
        f"Estimated recovery: {amt}/mo · Review opportunity details before approving",
    )


def _write_cw_audit(event_type: str, payload: dict[str, object]) -> None:
    """
    Write a single audit event to CloudWatch Logs /recoup/runtime.
    Fails silently so approval actions are never blocked by a CW error.
    """
    try:
        import boto3
        import botocore.config  # noqa: PLC0415

        client = boto3.client(
            "logs",
            region_name="us-east-1",
            config=botocore.config.Config(
                connect_timeout=3,
                read_timeout=5,
                retries={"max_attempts": 0},
            ),
        )
        message = json.dumps({"event": event_type, **payload}, default=str)

        # Ensure the log stream exists
        try:
            client.create_log_stream(
                logGroupName=AUDIT_LOG_GROUP,
                logStreamName=AUDIT_LOG_STREAM,
            )
        except client.exceptions.ResourceAlreadyExistsException:
            pass

        client.put_log_events(
            logGroupName=AUDIT_LOG_GROUP,
            logStreamName=AUDIT_LOG_STREAM,
            logEvents=[{"timestamp": int(time.time() * 1000), "message": message}],
        )
        log.info("hitl_flow.cw_audit_written", audit_event=event_type)
    except Exception as exc:  # noqa: BLE001
        log.warning("hitl_flow.cw_audit_failed", audit_event=event_type, error=str(exc))


class HITLFlow:
    """
    Orchestrates the HITL approval lifecycle for one opportunity.

    Args:
        opportunity_id: Opportunity this flow belongs to.
    """

    def __init__(self, opportunity_id: str) -> None:
        self._opportunity_id = opportunity_id
        self._last_sns_notification_sent: bool = False

    @property
    def last_sns_notification_sent(self) -> bool:
        """Whether the most recent approve() successfully published SNS (or dry-run)."""
        return self._last_sns_notification_sent

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_request(
        self,
        principal: str,
        action: str,
        amount: Decimal,
        claim_hash: str,
        state_version: int,
        ttl_hours: int = 24,
        resource_id: str = "",
        risk_tier_override: str | None = None,
        action_description_override: str | None = None,
        rollback_context_override: str | None = None,
    ) -> ApprovalRecord:
        """
        Create a PENDING ApprovalRecord and persist it.

        Args:
            principal:     Who is being asked to approve (user / role).
            action:        Description of the action (e.g. 'submit_support_case').
            amount:        Dollar amount shown on the approval card.
            claim_hash:    SHA-256 of the ClaimPackage JSON.
            state_version: Current opportunity state version — bound to approval.
            ttl_hours:     Expiry window (default 24 h).
            resource_id:   Underlying AWS resource ID for cross-restart dedup.

        Returns:
            The created ApprovalRecord in PENDING state.
        """
        # Revoke any existing pending approval for this opportunity
        existing = get_pending_for_opportunity(self._opportunity_id)
        if existing is not None:
            update_approval_state(
                existing.approval_id,
                ApprovalState.REVOKED,
                decided_by="system",
                notes="Superseded by new approval request",
            )
            log.info(
                "hitl_flow.revoked_superseded",
                opportunity_id=self._opportunity_id,
                old_approval_id=existing.approval_id,
            )

        # Also revoke any other PENDING approvals for the same resource_id
        # (can occur after server restarts when opportunity IDs are regenerated)
        if resource_id:
            from .store import revoke_pending_by_resource_id  # noqa: PLC0415
            revoked_count = revoke_pending_by_resource_id(
                resource_id=resource_id,
                exclude_opportunity_id=self._opportunity_id,
                notes="Superseded by re-promotion of same resource",
            )
            if revoked_count > 0:
                log.info(
                    "hitl_flow.revoked_stale_resource_approvals",
                    resource_id=resource_id,
                    revoked_count=revoked_count,
                )

        risk_tier, action_description, rollback_context = _derive_approval_context(
            action, amount
        )
        if risk_tier_override is not None:
            risk_tier = risk_tier_override
        if action_description_override is not None:
            action_description = action_description_override
        if rollback_context_override is not None:
            rollback_context = rollback_context_override
        record = ApprovalRecord.create(
            approval_id=str(uuid.uuid4()),
            principal=principal,
            action=action,
            amount=amount,
            claim_hash=claim_hash,
            opportunity_id=self._opportunity_id,
            resource_id=resource_id,
            state_version=state_version,
            ttl_hours=ttl_hours,
            risk_tier=risk_tier,
            action_description=action_description,
            rollback_context=rollback_context,
        )
        save_approval(record)
        log.info(
            "hitl_flow.request_created",
            opportunity_id=self._opportunity_id,
            approval_id=record.approval_id,
            action=action,
            amount=str(amount),
            expires_at=record.expires_at.isoformat(),
        )
        _write_cw_audit("APPROVAL_REQUESTED", {
            "opportunity_id": self._opportunity_id,
            "approval_id": record.approval_id,
            "action": action,
            "amount": str(amount),
            "principal": principal,
            "expires_at": record.expires_at.isoformat(),
        })
        return record

    # ------------------------------------------------------------------
    # Decide
    # ------------------------------------------------------------------

    def approve(
        self,
        approval_id: str,
        principal: str,
        claim_hash: str,
        amount: Decimal,
        state_version: int,
        notes: str = "",
    ) -> ApprovalRecord:
        """
        Record human approval with full binding assertions.

        Raises:
            ValueError: If approval not found, already decided, hash mismatches,
                        amount mismatches, state version mismatches, or expired.
        """
        from ..approval.store import get_approval

        record = get_approval(approval_id)
        self._assert_actionable(record, approval_id)
        assert record is not None  # narrowing after _assert_actionable

        # Binding assertions — protect against stale/tampered approvals
        if record.claim_hash != claim_hash:
            raise ValueError(
                f"claim_hash mismatch: approval bound to {record.claim_hash!r}, "
                f"got {claim_hash!r}"
            )
        if record.amount != amount:
            raise ValueError(
                f"amount mismatch: approval bound to {record.amount}, got {amount}"
            )
        if record.state_version != state_version:
            raise ValueError(
                f"state_version mismatch: approval bound to {record.state_version}, "
                f"got {state_version}"
            )
        if record.is_expired:
            raise ValueError(
                f"Approval {approval_id!r} has expired at {record.expires_at.isoformat()}"
            )

        updated = update_approval_state(
            approval_id,
            ApprovalState.APPROVED,
            decided_by=principal,
            notes=notes,
        )
        assert updated is not None
        log.info(
            "hitl_flow.approved",
            opportunity_id=self._opportunity_id,
            approval_id=approval_id,
            principal=principal,
        )
        _write_cw_audit("APPROVAL_GRANTED", {
            "opportunity_id": self._opportunity_id,
            "approval_id": approval_id,
            "principal": principal,
            "amount": str(updated.amount),
            "approved_at": updated.timestamp.isoformat(),
        })

        # Sprint 3: outcome record before SNS so create() does not clobber sns_sent.
        try:
            from ..graph.outcome_repository import outcome_repo  # noqa: PLC0415

            existing_outcome = outcome_repo.get(self._opportunity_id)
            if existing_outcome is None:
                outcome_repo.create(
                    opportunity_id=self._opportunity_id,
                    credit_amount=updated.amount,
                    action_taken=updated.action,
                )
            outcome_repo.mark_recovered(
                opportunity_id=self._opportunity_id,
                credit_amount=updated.amount,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("hitl_flow.outcome_write_failed", error=str(exc))

        sns_sent = self._send_sns_recovery_report(updated)
        self._last_sns_notification_sent = sns_sent
        try:
            from ..graph.outcome_repository import outcome_repo  # noqa: PLC0415
            outcome_repo.record_sns_notification(self._opportunity_id, sns_sent)
        except Exception as exc:  # noqa: BLE001
            log.warning("hitl_flow.sns_record_failed", error=str(exc))

        return updated

    def _send_sns_recovery_report(self, record: ApprovalRecord) -> bool:
        """
        Send an SNS recovery report email after approval.

        Resolves opportunity metadata from _graph_states (cost recovery)
        or uses the approval record's action/amount for SLA claims.
        Fails silently — notification failure never blocks the approval.
        """
        from ..notifications import format_recovery_report_email, notify_sns

        try:
            # Try to get rich metadata from graph state
            from ..demo_session import (  # noqa: PLC0415
                DEFAULT_TEST_SESSION,
                current_demo_session_id,
            )
            from ..demo_state import graph_states  # noqa: PLC0415

            sid = current_demo_session_id.get() or DEFAULT_TEST_SESSION
            gs = graph_states(sid).get(self._opportunity_id)
            if gs and gs.signal:
                sig = gs.signal
                resource_id = (
                    sig.affected_resource_ids[0]
                    if sig.affected_resource_ids
                    else self._opportunity_id
                )
                savings = (
                    str(gs.availability_result.potential_credit)
                    if gs.availability_result
                    else str(record.amount)
                )
                service = sig.service
                region = sig.region or "us-east-1"
                recommendation = (
                    gs.eligibility_assessment.satisfied_requirements[0]
                    if (
                        gs.eligibility_assessment
                        and gs.eligibility_assessment.satisfied_requirements
                    )
                    else record.action_description or record.action
                )
            else:
                resource_id = self._opportunity_id
                savings = str(record.amount)
                service = "AWS"
                region = "us-east-1"
                recommendation = record.action_description or record.action

            subject, message = format_recovery_report_email(
                opportunity_id=self._opportunity_id,
                service=service,
                region=region,
                resource_id=resource_id,
                savings_per_month=savings,
                recommendation=recommendation,
                severity="high",
                action=record.action,
            )
            sent = notify_sns(subject=subject, message=message)
            log.info(
                "hitl_flow.sns_report_sent",
                opportunity_id=self._opportunity_id,
                sent=sent,
            )
            return sent
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "hitl_flow.sns_report_failed",
                opportunity_id=self._opportunity_id,
                error=str(exc),
            )
            return False

    def decline(
        self,
        approval_id: str,
        principal: str,
        notes: str = "",
    ) -> ApprovalRecord:
        """Record human decline."""
        record = update_approval_state(
            approval_id,
            ApprovalState.DECLINED,
            decided_by=principal,
            notes=notes,
        )
        if record is None:
            raise ValueError(f"Approval '{approval_id}' not found")
        log.info(
            "hitl_flow.declined",
            opportunity_id=self._opportunity_id,
            approval_id=approval_id,
            principal=principal,
        )
        _write_cw_audit("APPROVAL_DECLINED", {
            "opportunity_id": self._opportunity_id,
            "approval_id": approval_id,
            "principal": principal,
            "notes": notes,
        })
        return record

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_pending(self) -> ApprovalRecord | None:
        """Return the current PENDING approval for this opportunity, or None."""
        return get_pending_for_opportunity(self._opportunity_id)

    def approval_card_text(self, record: ApprovalRecord) -> str:
        """
        Render the human-readable approval card (shown in Decision Inbox).

        This mirrors the spec's approval card format exactly.
        """
        now = datetime.now(UTC)
        hours_left = (record.expires_at - now).total_seconds() / 3600
        return (
            f"ACTION: {record.action}\n"
            f"AMOUNT: ${record.amount:,.2f}\n"
            f"OPPORTUNITY: {record.opportunity_id}\n"
            f"CLAIM HASH: {record.claim_hash[:16]}...\n"
            f"STATE VERSION: {record.state_version}\n"
            f"EXPIRES: {record.expires_at.strftime('%Y-%m-%d %H:%M UTC')} "
            f"({hours_left:.1f}h remaining)\n"
            "\n"
            "⚠️  This action will create a real AWS Support case.\n"
            "    Real Support submission is currently DISABLED (Verified Replay mode).\n"
            "    Approving will trigger: simulate_support_case → REPLAY case id.\n"
            "\n"
            "[Approve]  [Decline]"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _assert_actionable(
        self,
        record: ApprovalRecord | None,
        approval_id: str,
    ) -> None:
        if record is None:
            raise ValueError(f"Approval '{approval_id}' not found")
        if record.state not in (ApprovalState.PENDING,):
            raise ValueError(
                f"Approval '{approval_id}' is already in state '{record.state}'"
            )
