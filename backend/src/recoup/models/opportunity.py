"""Recovery opportunity — the core state machine entity."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class OpportunityState(str, Enum):
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
    simulation_mode: bool = Field(
        default=True,
        description="Always true unless explicitly set to false; gates all real external actions",
    )
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
