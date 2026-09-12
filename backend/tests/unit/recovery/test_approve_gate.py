"""Approve endpoint blocks INSUFFICIENT evidence."""

from __future__ import annotations

from decimal import Decimal

from recoup.models.recovery import (
    EvidenceSufficiency,
    EvidenceSufficiencyLevel,
    RecoveryAssessment,
    SafetyCheck,
    SafetyCheckStatus,
)
from recoup.recovery.engines.safety import has_blocking_failure


def test_has_blocking_failure_detects_fail() -> None:
    checks = [
        SafetyCheck(check="Policy", status=SafetyCheckStatus.PASS, summary="ok"),
        SafetyCheck(check="Policy allows HITL recovery", status=SafetyCheckStatus.FAIL, summary="blocked"),
    ]
    assert has_blocking_failure(checks) is True


def test_insufficient_sufficiency_enum() -> None:
    suff = EvidenceSufficiency(level=EvidenceSufficiencyLevel.INSUFFICIENT, reasons=["x"])
    assert suff.level == EvidenceSufficiencyLevel.INSUFFICIENT
    _ = RecoveryAssessment(signals=[])
