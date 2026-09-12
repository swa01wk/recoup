"""Deterministic financial impact."""

from __future__ import annotations

from decimal import Decimal

from ...models.recovery import FinancialImpact, SavingsLifecycleStage
from ...scanners.finding import Finding


def compute_financial_impact(finding: Finding) -> FinancialImpact:
    monthly = Decimal(str(finding.estimated_monthly_savings_usd)).quantize(Decimal("0.01"))
    annual = (monthly * Decimal("12")).quantize(Decimal("0.01"))
    trace = [
        f"Scanner estimated_monthly_savings_usd: ${monthly}",
        f"Annualized (×12): ${annual}",
        "Lifecycle: POTENTIAL until human approval and verification",
    ]
    return FinancialImpact(
        current_monthly_usd=monthly,
        projected_monthly_recovery_usd=monthly,
        projected_annual_recovery_usd=annual,
        lifecycle_stage=SavingsLifecycleStage.POTENTIAL,
        calculation_trace=trace,
    )
