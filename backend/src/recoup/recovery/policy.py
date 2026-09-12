"""Deterministic recovery policy (separate from SLA Cedar submit path)."""

from __future__ import annotations

from ..graph.types import PolicyDecision
from ..models.recovery import (
    EvidenceSufficiencyLevel,
    RecoveryPolicyOutcome,
    ResourceContext,
    RiskLevel,
)
from .catalog import RemediationCatalogEntry


def evaluate_recovery_policy(
    ctx: ResourceContext,
    sufficiency: EvidenceSufficiencyLevel,
    discovery_score: int,
    action_confidence: int,
    risk_level: RiskLevel,
    action: RemediationCatalogEntry,
) -> tuple[RecoveryPolicyOutcome, PolicyDecision, str]:
    if sufficiency == EvidenceSufficiencyLevel.INSUFFICIENT:
        return (
            RecoveryPolicyOutcome.INVESTIGATE_FURTHER,
            PolicyDecision.REQUIRE_APPROVAL,
            "Insufficient evidence — investigate further before acting",
        )
    if sufficiency == EvidenceSufficiencyLevel.CONFLICTING:
        return (
            RecoveryPolicyOutcome.INVESTIGATE_FURTHER,
            PolicyDecision.REQUIRE_APPROVAL,
            "Conflicting evidence — additional investigation required",
        )

    if action.action_id == "terminate" and risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
        return (
            RecoveryPolicyOutcome.HITL_REQUIRED,
            PolicyDecision.REQUIRE_APPROVAL,
            "Destructive action in elevated risk context requires approval",
        )

    # AUTO_ALLOWED is recorded on assessment for explainability; J-FULL promote
    # still forces REQUIRE_APPROVAL at the HTTP layer for cost recovery.
    if (
        ctx.environment.environment in ("dev", "development", "staging")
        and not action.destructive
        and action_confidence >= 85
        and discovery_score >= 80
        and risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM)
        and sufficiency == EvidenceSufficiencyLevel.SUFFICIENT
    ):
        return (
            RecoveryPolicyOutcome.AUTO_ALLOWED,
            PolicyDecision.REQUIRE_APPROVAL,
            "Eligible for auto-safe policy; human approval still required on J-FULL path",
        )

    if ctx.environment.environment in ("prod", "production"):
        return (
            RecoveryPolicyOutcome.HITL_REQUIRED,
            PolicyDecision.REQUIRE_APPROVAL,
            "Production resources require human approval",
        )

    return (
        RecoveryPolicyOutcome.HITL_REQUIRED,
        PolicyDecision.REQUIRE_APPROVAL,
        "Default human approval for cost recovery actions",
    )
