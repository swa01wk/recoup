"""Opportunity priority scoring."""

from __future__ import annotations

from decimal import Decimal

from ...models.recovery import (
    EvidenceSufficiencyLevel,
    RecoveryAssessment,
)


def compute_priority(assessment: RecoveryAssessment) -> tuple[int, str]:
    fin = assessment.financial_impact
    monthly = float(fin.projected_monthly_recovery_usd if fin else Decimal("0"))
    disc = assessment.discovery_confidence.score if assessment.discovery_confidence else 50
    suff = (
        assessment.evidence_sufficiency.level
        if assessment.evidence_sufficiency
        else EvidenceSufficiencyLevel.PARTIAL
    )
    risk = assessment.risk_assessment.score if assessment.risk_assessment else 50

    suff_mult = {
        EvidenceSufficiencyLevel.SUFFICIENT: 1.0,
        EvidenceSufficiencyLevel.PARTIAL: 0.75,
        EvidenceSufficiencyLevel.CONFLICTING: 0.4,
        EvidenceSufficiencyLevel.INSUFFICIENT: 0.2,
    }[suff]

    value_component = min(40.0, monthly * 0.4)
    conf_component = disc * 0.35
    risk_adj = max(0.3, 1.0 - risk / 150.0)
    raw = (value_component + conf_component) * suff_mult * risk_adj
    score = max(0, min(100, int(round(raw))))
    explanation = (
        f"Priority {score}: savings weight + discovery confidence, "
        f"adjusted by sufficiency ({suff.value}) and risk"
    )
    return score, explanation
