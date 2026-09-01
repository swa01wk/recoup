"""Human approval record — bound to claim hash, amount, and state version."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ApprovalState(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    DECLINED = "DECLINED"


class ApprovalRecord(BaseModel):
    approval_id: str
    principal: str
    action: str
    amount: Decimal
    claim_hash: str = Field(description="SHA-256 of the ClaimPackage JSON")
    opportunity_id: str
    state_version: int = Field(description="Bound to this exact state version; stale if changed")
    timestamp: datetime
    expires_at: datetime
    state: ApprovalState = ApprovalState.PENDING

    @property
    def is_valid(self) -> bool:
        return self.state == ApprovalState.APPROVED and self.expires_at > _utcnow()

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= _utcnow()

    @classmethod
    def create(
        cls,
        approval_id: str,
        principal: str,
        action: str,
        amount: Decimal,
        claim_hash: str,
        opportunity_id: str,
        state_version: int,
        ttl_hours: int = 24,
    ) -> "ApprovalRecord":
        now = _utcnow()
        return cls(
            approval_id=approval_id,
            principal=principal,
            action=action,
            amount=amount,
            claim_hash=claim_hash,
            opportunity_id=opportunity_id,
            state_version=state_version,
            timestamp=now,
            expires_at=now + timedelta(hours=ttl_hours),
            state=ApprovalState.PENDING,
        )
