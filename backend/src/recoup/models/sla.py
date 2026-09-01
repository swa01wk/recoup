"""SLA contract — loaded from the human-verified local catalog; never fetched at claim time."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class CreditTier(BaseModel):
    min_pct: Decimal
    max_exclusive_pct: Decimal
    credit_pct: Decimal

    @model_validator(mode="after")
    def validate_tier_range(self) -> "CreditTier":
        if self.min_pct >= self.max_exclusive_pct:
            raise ValueError("min_pct must be less than max_exclusive_pct")
        if not (Decimal("0") <= self.credit_pct <= Decimal("100")):
            raise ValueError("credit_pct must be between 0 and 100")
        return self


class SLAContract(BaseModel):
    service: str
    version: str
    effective_from: date
    effective_to: date | None = None
    service_commitment: Decimal = Field(description="e.g. Decimal('99.95')")
    interval_minutes: int = Field(ge=1, description="Monitoring interval; typically 5 for API Gateway")
    claim_deadline_rule: str
    credit_tiers: list[CreditTier] = Field(min_length=1)
    required_claim_fields: list[str] = Field(min_length=1)
    exclusions: list[str] = Field(default_factory=list)
    source_url: str = Field(description="Official AWS SLA page URL")
    source_hash: str = Field(description="SHA-256 of the source document; must start with 'sha256:'")

    @model_validator(mode="after")
    def validate_source_hash(self) -> "SLAContract":
        if not self.source_hash.startswith("sha256:"):
            raise ValueError("source_hash must start with 'sha256:'")
        return self

    def resolve_tier(self, monthly_uptime_pct: Decimal) -> Decimal:
        """Return credit percentage for the given monthly uptime. Returns 0 if not eligible."""
        if monthly_uptime_pct >= self.service_commitment:
            return Decimal("0")
        for tier in sorted(self.credit_tiers, key=lambda t: t.min_pct, reverse=True):
            if tier.min_pct <= monthly_uptime_pct < tier.max_exclusive_pct:
                return tier.credit_pct
        return Decimal("0")
