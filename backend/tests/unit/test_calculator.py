"""
Golden acceptance tests for the SLA availability and credit calculator.

Tests 1-12 directly correspond to Appendix C of the product spec.
These tests are 100% deterministic — no LLM calls, no AWS calls.
All must pass before every commit to main.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from recoup.engines.calculator import calculate_availability_and_credit
from recoup.models.availability import AvailabilityInterval
from recoup.models.sla import CreditTier, SLAContract

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

API_GW_CONTRACT = SLAContract(
    service="apigateway",
    version="2022-05-05",
    effective_from="2022-05-05",
    service_commitment=Decimal("99.95"),
    interval_minutes=5,
    claim_deadline_rule="end_of_second_billing_cycle_after_incident",
    credit_tiers=[
        CreditTier(
            min_pct=Decimal("99.00"),
            max_exclusive_pct=Decimal("99.95"),
            credit_pct=Decimal("10"),
        ),
        CreditTier(
            min_pct=Decimal("95.00"),
            max_exclusive_pct=Decimal("99.00"),
            credit_pct=Decimal("25"),
        ),
        CreditTier(
            min_pct=Decimal("0.00"),
            max_exclusive_pct=Decimal("95.00"),
            credit_pct=Decimal("100"),
        ),
    ],
    required_claim_fields=["api_id", "region", "billing_cycle", "request_logs", "billing_record"],
    source_url="https://aws.amazon.com/api-gateway/sla/",
    source_hash="sha256:test",
)

BILLED_CHARGES = Decimal("100.00")


def _make_intervals(total: int, unavailable_count: int) -> list[AvailabilityInterval]:
    """Create intervals with the first `unavailable_count` at 0% availability."""
    base = datetime(2026, 8, 1, tzinfo=UTC)
    from datetime import timedelta

    intervals = []
    for i in range(total):
        start = base + timedelta(minutes=5 * i)
        end = start + timedelta(minutes=5)
        is_down = i < unavailable_count
        intervals.append(
            AvailabilityInterval(
                start=start,
                end=end,
                availability_pct=Decimal("0.0") if is_down else Decimal("100.0"),
                request_count=0 if is_down else 1000,
                error_count=1000 if is_down else 0,
            )
        )
    return intervals


def _intervals_for_uptime(uptime_pct: Decimal, total: int = 8640) -> list[AvailabilityInterval]:
    """Create intervals yielding exactly the requested uptime percentage."""
    unavailable = int((Decimal("1") - uptime_pct / Decimal("100")) * total)
    return _make_intervals(total, unavailable)


# ---------------------------------------------------------------------------
# Appendix C — Golden acceptance tests
# ---------------------------------------------------------------------------


def test_golden_uptime_8634_of_8640() -> None:
    """Test 1: 8,640 five-minute intervals, 6 at 0% → 99.930556%"""
    intervals = _make_intervals(total=8640, unavailable_count=6)
    result = calculate_availability_and_credit(intervals, API_GW_CONTRACT, BILLED_CHARGES)
    # (8640 - 6) / 8640 * 100 = 8634/8640 * 100 = 99.930555...
    assert result.monthly_uptime_pct == Decimal("99.930556")


def test_golden_tier_10_pct_not_25() -> None:
    """Test 2: 99.9306% maps to 10% tier, NOT 25%."""
    intervals = _make_intervals(total=8640, unavailable_count=6)
    result = calculate_availability_and_credit(intervals, API_GW_CONTRACT, BILLED_CHARGES)
    assert result.tier_pct == Decimal("10")
    assert result.tier_pct != Decimal("25")


def test_golden_credit_ten_pct() -> None:
    """Test 3: $100.00 × 10% = $10.00"""
    intervals = _make_intervals(total=8640, unavailable_count=6)
    result = calculate_availability_and_credit(intervals, API_GW_CONTRACT, BILLED_CHARGES)
    assert result.potential_credit == Decimal("10.00")


def test_exactly_at_commitment_not_eligible() -> None:
    """Test 4: Exactly 99.95% is NOT breached (strict less-than boundary)."""
    # 99.95% = (total - unavailable) / total; solve for unavailable
    # unavailable = total * (1 - 99.95/100) = 8640 * 0.0005 = 4.32 → 4 unavailable
    # But 4/8640 = 99.9537% which is above 99.95. Use a different total.
    # With total=2000: unavailable=1 → 1999/2000*100 = 99.95 exactly
    intervals = _make_intervals(total=2000, unavailable_count=1)
    result = calculate_availability_and_credit(intervals, API_GW_CONTRACT, BILLED_CHARGES)
    assert result.monthly_uptime_pct == Decimal("99.950000")
    assert result.threshold_breached is False
    assert result.potential_credit == Decimal("0.00")


def test_25_pct_tier() -> None:
    """25% tier fires when uptime is between 95% and 99%."""
    # 6 unavailable out of 100 total = 94% uptime — oops, that's 100% tier
    # Use 97.5% uptime → 25% tier
    intervals = _make_intervals(total=1000, unavailable_count=25)
    result = calculate_availability_and_credit(intervals, API_GW_CONTRACT, BILLED_CHARGES)
    assert Decimal("95") <= result.monthly_uptime_pct < Decimal("99")
    assert result.tier_pct == Decimal("25")


def test_100_pct_tier() -> None:
    """100% credit tier fires when uptime < 95%."""
    intervals = _make_intervals(total=100, unavailable_count=10)
    result = calculate_availability_and_credit(intervals, API_GW_CONTRACT, BILLED_CHARGES)
    assert result.monthly_uptime_pct < Decimal("95")
    assert result.tier_pct == Decimal("100")
    assert result.potential_credit == BILLED_CHARGES


def test_above_commitment_no_credit() -> None:
    """Uptime above 99.95% yields zero credit."""
    intervals = _make_intervals(total=8640, unavailable_count=0)
    result = calculate_availability_and_credit(intervals, API_GW_CONTRACT, BILLED_CHARGES)
    assert result.threshold_breached is False
    assert result.potential_credit == Decimal("0.00")
    assert result.tier_pct == Decimal("0")


def test_calculation_trace_populated() -> None:
    """Calculation trace must contain human-readable arithmetic steps."""
    intervals = _make_intervals(total=8640, unavailable_count=6)
    result = calculate_availability_and_credit(intervals, API_GW_CONTRACT, BILLED_CHARGES)
    assert len(result.calculation_trace) >= 5
    assert any("8,640" in step for step in result.calculation_trace)
    assert any("10.00" in step or "10" in step for step in result.calculation_trace)


def test_zero_billing_charges_yields_zero_credit() -> None:
    """Zero billed charges → $0.00 credit regardless of uptime."""
    intervals = _make_intervals(total=8640, unavailable_count=6)
    result = calculate_availability_and_credit(intervals, API_GW_CONTRACT, Decimal("0.00"))
    assert result.potential_credit == Decimal("0.00")


def test_decimal_precision_no_float() -> None:
    """Credit calculation must use Decimal throughout — no floating point rounding."""
    intervals = _make_intervals(total=8640, unavailable_count=6)
    result = calculate_availability_and_credit(intervals, API_GW_CONTRACT, Decimal("100.00"))
    assert isinstance(result.potential_credit, Decimal)
    assert isinstance(result.monthly_uptime_pct, Decimal)
    assert isinstance(result.tier_pct, Decimal)


def test_empty_intervals_raises() -> None:
    """Empty interval list must raise ValueError."""
    with pytest.raises(ValueError, match="zero intervals"):
        calculate_availability_and_credit([], API_GW_CONTRACT, BILLED_CHARGES)


def test_boundary_just_below_99_95() -> None:
    """Just below 99.95% must be breached and land in 10% tier."""
    # 4 unavailable out of 8000 total = 99.95% — need slightly less uptime
    # Use uptime of 99.9499% — 1 unavailable per 1999 → 1998/1999 = 99.94997%
    intervals = _make_intervals(total=1999, unavailable_count=1)
    result = calculate_availability_and_credit(intervals, API_GW_CONTRACT, BILLED_CHARGES)
    assert result.threshold_breached is True
    assert result.tier_pct == Decimal("10")
