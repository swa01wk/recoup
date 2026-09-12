"""Deterministic operational risk assessment."""

from __future__ import annotations

from ...models.recovery import ResourceContext, RiskAssessment, RiskFactor, RiskLevel
from ..catalog import RemediationCatalogEntry


def assess_risk(
    ctx: ResourceContext,
    action: RemediationCatalogEntry | None,
) -> RiskAssessment:
    factors: list[RiskFactor] = []
    score = 25

    env = ctx.environment.environment
    if env in ("prod", "production"):
        score += 35
        factors.append(
            RiskFactor(
                name="environment",
                label="Environment",
                level="High",
                contribution="+35",
            )
        )
    elif env == "unknown":
        score += 15
        factors.append(
            RiskFactor(
                name="environment",
                label="Environment",
                level="Medium",
                contribution="+15",
            )
        )
    else:
        factors.append(
            RiskFactor(
                name="environment",
                label="Environment",
                level="Low",
                contribution="+0",
            )
        )

    if ctx.dependencies:
        score += 10
        factors.append(
            RiskFactor(
                name="dependencies",
                label="Dependencies",
                level="Medium",
                contribution="+10",
            )
        )
    else:
        score += 5
        factors.append(
            RiskFactor(
                name="dependencies",
                label="Dependencies",
                level="Low",
                contribution="+5",
            )
        )

    if ctx.environment.is_demo:
        score -= 15
        factors.append(
            RiskFactor(
                name="criticality",
                label="Criticality",
                level="Low",
                contribution="-15",
            )
        )

    if action and action.destructive:
        score += 20
        factors.append(
            RiskFactor(
                name="reversibility",
                label="Reversibility",
                level="High",
                contribution="+20",
            )
        )
    elif action:
        factors.append(
            RiskFactor(
                name="reversibility",
                label="Reversibility",
                level="Low",
                contribution="+0",
            )
        )

    owner = ctx.environment.owner or ctx.environment.tags.get("Owner")
    factors.append(
        RiskFactor(
            name="ownership",
            label="Ownership",
            level="Known" if owner else "Unknown",
            contribution="+0",
        )
    )

    score = max(0, min(100, score))

    if score >= 75:
        level = RiskLevel.CRITICAL
    elif score >= 55:
        level = RiskLevel.HIGH
    elif score >= 35:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.LOW

    return RiskAssessment(
        score=score,
        level=level,
        factors=factors,
        explanation=f"Risk score {score} from environment, dependencies, and action reversibility",
    )
