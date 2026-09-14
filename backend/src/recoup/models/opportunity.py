"""Recovery opportunity — the core state machine entity."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, computed_field, field_validator


class OpportunityState(StrEnum):
    DETECTED = "DETECTED"
    INVESTIGATING = "INVESTIGATING"
    EVIDENCE_READY = "EVIDENCE_READY"
    NEEDS_EVIDENCE = "NEEDS_EVIDENCE"
    ELIGIBILITY_REVIEWED = "ELIGIBILITY_REVIEWED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    SUBMITTING = "SUBMITTING"
    SUBMITTED = "SUBMITTED"
    MONITORING = "MONITORING"
    RECOVERED = "RECOVERED"
    REJECTED = "REJECTED"
    NEEDS_FOLLOWUP = "NEEDS_FOLLOWUP"
    DENIED = "DENIED"
    DECLINED = "DECLINED"
    FAILED = "FAILED"


class RecoveryOpportunity(BaseModel):
    id: str
    type: Literal["SLA", "ANOMALY", "OPTIMIZATION"]
    account_id_masked: str = Field(description="Last 4 digits of account ID only")
    service: str
    region: str
    discovered_at: datetime
    potential_value: Decimal = Field(default=Decimal("0.00"))
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    state: OpportunityState = OpportunityState.DETECTED
    state_version: int = Field(default=0, description="Increments atomically on every state change")
    idempotency_key: str = ""
    active_claim_hash: str | None = None

    @field_validator("account_id_masked")
    @classmethod
    def mask_account_id(cls, v: str) -> str:
        """Ensure only last 4 digits are stored."""
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) >= 4:
            return f"****{digits[-4:]}"
        return v

    @field_validator("potential_value", mode="before")
    @classmethod
    def coerce_decimal(cls, v: object) -> Decimal:
        return Decimal(str(v))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def lifecycle_state(self) -> str:
        """4-bucket canonical lifecycle for display (mutually exclusive).

        DETECTED  = early investigation stages (before approval gate)
        PENDING   = awaiting human approval
        APPROVED  = approved / in remediation / being monitored
        RECOVERED = verified savings confirmed
        """
        s = self.state.upper()
        if s in {
            "DETECTED",
            "INVESTIGATING",
            "NEEDS_EVIDENCE",
            "EVIDENCE_READY",
            "ELIGIBILITY_REVIEWED",
        }:
            return "DETECTED"
        if s in {"AWAITING_APPROVAL", "NEEDS_FOLLOWUP"}:
            return "PENDING"
        if s in {"APPROVED", "SUBMITTING", "SUBMITTED"}:
            return "APPROVED"
        if s in {"MONITORING", "RECOVERED"}:
            return "RECOVERED"
        # Terminal negatives: REJECTED, FAILED, DECLINED, DENIED → map to DETECTED
        return "DETECTED"
