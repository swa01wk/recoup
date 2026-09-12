"""Deterministic pre-approval safety checks."""

from __future__ import annotations

from ...models.recovery import (
    RecoveryPolicyOutcome,
    RecoveryRecommendation,
    ResourceContext,
    SafetyCheck,
    SafetyCheckStatus,
)
from ..catalog import RemediationCatalogEntry


def run_safety_checks(
    ctx: ResourceContext,
    recommendation: RecoveryRecommendation | None,
    primary_entry: RemediationCatalogEntry | None,
    policy_outcome: RecoveryPolicyOutcome,
) -> list[SafetyCheck]:
    checks: list[SafetyCheck] = []

    deps = ctx.dependencies
    if deps:
        lb = any("load" in d.lower() or "elb" in d.lower() for d in deps)
        checks.append(
            SafetyCheck(
                check="Active dependencies",
                status=SafetyCheckStatus.WARN if lb else SafetyCheckStatus.WARN,
                summary=f"{len(deps)} dependency reference(s) detected",
            )
        )
    else:
        checks.append(
            SafetyCheck(
                check="Active dependencies",
                status=SafetyCheckStatus.PASS,
                summary="No active dependency detected",
            )
        )

    owner = ctx.environment.owner or ctx.environment.tags.get("Owner") or ctx.environment.tags.get("owner")
    if owner:
        checks.append(
            SafetyCheck(
                check="Owner identified",
                status=SafetyCheckStatus.PASS,
                summary=f"Owner: {owner}",
            )
        )
    else:
        checks.append(
            SafetyCheck(
                check="Owner identified",
                status=SafetyCheckStatus.UNKNOWN,
                summary="Ownership uncertain",
            )
        )

    rev = recommendation.reversibility if recommendation else ""
    if primary_entry and primary_entry.reversibility == "reversible":
        checks.append(
            SafetyCheck(
                check="Action is reversible",
                status=SafetyCheckStatus.PASS,
                summary="Selected action supports rollback",
            )
        )
    elif rev == "reversible":
        checks.append(
            SafetyCheck(
                check="Action is reversible",
                status=SafetyCheckStatus.PASS,
                summary="Selected action supports rollback",
            )
        )
    else:
        checks.append(
            SafetyCheck(
                check="Action is reversible",
                status=SafetyCheckStatus.WARN,
                summary="Destructive or limited rollback path",
            )
        )

    checks.append(
        SafetyCheck(
            check="Backup/recovery path",
            status=SafetyCheckStatus.UNKNOWN,
            summary="Backup status unknown — confirm before destructive actions",
        )
    )

    if policy_outcome == RecoveryPolicyOutcome.BLOCKED:
        checks.append(
            SafetyCheck(
                check="Policy allows HITL recovery",
                status=SafetyCheckStatus.FAIL,
                summary="Recovery blocked by policy",
            )
        )
    else:
        checks.append(
            SafetyCheck(
                check="Policy allows HITL recovery",
                status=SafetyCheckStatus.PASS,
                summary="Human approval path enabled",
            )
        )

    return checks


def has_blocking_failure(checks: list[SafetyCheck]) -> bool:
    return any(c.status == SafetyCheckStatus.FAIL for c in checks)
