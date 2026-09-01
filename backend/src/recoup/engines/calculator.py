"""
SLA availability and credit calculator.

All arithmetic uses Decimal with explicit rounding — never float.
No LLM involvement. All golden acceptance tests must pass against this module.
"""

from decimal import ROUND_HALF_UP, Decimal

from ..models.availability import AvailabilityInterval, AvailabilityResult
from ..models.sla import SLAContract


def calculate_availability_and_credit(
    intervals: list[AvailabilityInterval],
    contract: SLAContract,
    billed_charges: Decimal,
) -> AvailabilityResult:
    """
    Calculate monthly uptime % and SLA credit from raw intervals.

    Golden test spec (Appendix C, tests 1-3):
      - 8,640 five-minute intervals, 6 at 0% availability → 99.9306%
      - 99.9306% with API Gateway contract → 10% tier
      - $18,400 × 10% → $1,840.00

    Args:
        intervals: All monitoring intervals for the billing month.
        contract: The applicable SLA contract (resolved by incident date).
        billed_charges: Affected service charges for the billing cycle.

    Returns:
        AvailabilityResult with uptime %, tier, credit, and calculation trace.
    """
    total = len(intervals)
    if total == 0:
        raise ValueError("Cannot calculate availability with zero intervals")

    # An interval is considered unavailable if availability_pct < 100.
    # For API Gateway the SLA measures error rate per 5-minute window.
    unavailable = [i for i in intervals if i.availability_pct < Decimal("100")]
    unavailable_count = len(unavailable)

    # SLA formula: (total_intervals - unavailable_intervals) / total_intervals × 100
    monthly_uptime_pct = (
        Decimal(total - unavailable_count) / Decimal(total) * Decimal("100")
    ).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    # Threshold is a strict less-than — exactly at commitment is NOT breached
    threshold_breached = monthly_uptime_pct < contract.service_commitment

    tier_pct = contract.resolve_tier(monthly_uptime_pct) if threshold_breached else Decimal("0")

    potential_credit = (
        (billed_charges * tier_pct / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if threshold_breached
        else Decimal("0.00")
    )

    trace = _build_trace(
        total=total,
        unavailable_count=unavailable_count,
        monthly_uptime_pct=monthly_uptime_pct,
        service_commitment=contract.service_commitment,
        threshold_breached=threshold_breached,
        tier_pct=tier_pct,
        billed_charges=billed_charges,
        potential_credit=potential_credit,
    )

    return AvailabilityResult(
        monthly_uptime_pct=monthly_uptime_pct,
        threshold_breached=threshold_breached,
        tier_pct=tier_pct,
        billed_charges=billed_charges,
        potential_credit=potential_credit,
        calculation_trace=trace,
    )


def _build_trace(
    total: int,
    unavailable_count: int,
    monthly_uptime_pct: Decimal,
    service_commitment: Decimal,
    threshold_breached: bool,
    tier_pct: Decimal,
    billed_charges: Decimal,
    potential_credit: Decimal,
) -> list[str]:
    lines = [
        f"Total 5-minute intervals in billing month: {total:,}",
        f"Unavailable intervals (availability < 100%): {unavailable_count}",
        f"Formula: ({total:,} − {unavailable_count}) ÷ {total:,} × 100",
        f"Monthly uptime %: {monthly_uptime_pct}%",
        f"SLA commitment: {service_commitment}%",
        f"Threshold breached: {'YES' if threshold_breached else 'NO'} "
        f"({monthly_uptime_pct}% {'<' if threshold_breached else '≥'} {service_commitment}%)",
    ]
    if threshold_breached:
        lines += [
            f"Credit tier: {tier_pct}%",
            f"Billed charges in affected billing cycle: ${billed_charges:,}",
            f"Potential credit: ${billed_charges:,} × {tier_pct}% = ${potential_credit:,}",
        ]
    else:
        lines.append("Not eligible — uptime meets or exceeds SLA commitment.")
    return lines
