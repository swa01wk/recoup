"""Map RecoveryAssessment to HITL approval display fields."""

from __future__ import annotations

from ..models.recovery import RecoveryAssessment, RiskLevel


def hitl_context_from_assessment(assessment: RecoveryAssessment) -> tuple[str, str, str]:
    """Return (risk_tier, action_description, rollback_context) for ApprovalRecord."""
    risk_tier = "YELLOW"
    if assessment.risk_assessment:
        level = assessment.risk_assessment.level
        if level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            risk_tier = "RED"
        elif level == RiskLevel.LOW:
            risk_tier = "GREEN"

    action_description = "Execute cost recovery"
    if assessment.recommendation:
        action_description = assessment.recommendation.primary_action_label
        if assessment.recommendation.reasoning:
            action_description = f"{action_description} — {assessment.recommendation.reasoning[:120]}"

    rollback = ""
    if assessment.recovery_plan:
        rollback = assessment.recovery_plan.rollback_strategy[:240]

    return risk_tier, action_description, rollback
