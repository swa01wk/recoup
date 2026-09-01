"""Availability intervals and credit calculation result."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class AvailabilityInterval(BaseModel):
    start: datetime
    end: datetime
    availability_pct: Decimal
    request_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    evidence_refs: list[str] = Field(default_factory=list)


class AvailabilityResult(BaseModel):
    monthly_uptime_pct: Decimal
    threshold_breached: bool
    tier_pct: Decimal
    billed_charges: Decimal
    potential_credit: Decimal
    calculation_trace: list[str] = Field(
        description="Human-readable arithmetic steps; shown in UI"
    )

    @property
    def is_eligible(self) -> bool:
        return self.threshold_breached and self.potential_credit > Decimal("0")
