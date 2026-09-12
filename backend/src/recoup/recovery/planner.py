"""Recovery recommendation and plan (deterministic + LLM hook)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from ..models.recovery import (
    RecoveryPlan,
    RecoveryPlanStep,
    RecoveryPlanStepPhase,
    RecoveryRecommendation,
    RemediationOption,
    ResourceContext,
)
from ..scanners.finding import Finding
from .catalog import RemediationCatalogEntry, catalog_for_service


def _pick_primary(
    finding: Finding,
    catalog: list[RemediationCatalogEntry],
    has_counter: bool,
) -> RemediationCatalogEntry:
    ft = (finding.finding_type or "").upper()
    if has_counter:
        for c in catalog:
            if c.action_id in ("investigate", "resize", "none"):
                return c
        return catalog[0]
    if "IDLE" in ft or "STOPPED" in ft:
        for c in catalog:
            if c.action_id == "stop":
                return c
    if "UNATTACHED" in ft:
        for c in catalog:
            if c.action_id == "delete_unattached":
                return c
    if "GP2" in (finding.issue or "").upper():
        for c in catalog:
            if c.action_id == "change_type":
                return c
    return catalog[0] if catalog else RemediationCatalogEntry("investigate", "Investigate", "reversible")


def build_recommendation_and_plan(
    finding: Finding,
    ctx: ResourceContext,
    action_confidences: dict[str, Any],
    has_counter: bool,
    monthly: Decimal,
) -> tuple[RecoveryRecommendation, RecoveryPlan]:
    catalog = catalog_for_service(finding.service)
    primary = _pick_primary(finding, catalog, has_counter)

    alts: list[RemediationOption] = []
    for entry in catalog:
        if entry.action_id == primary.action_id:
            continue
        ac = action_confidences.get(entry.action_id)
        alts.append(
            RemediationOption(
                action_id=entry.action_id,
                label=entry.label,
                reversibility=entry.reversibility,
                action_confidence=ac,
            )
        )

    reasoning = (
        f"Prefer {primary.label} as the least destructive option that achieves "
        f"projected recovery of ${monthly}/mo."
    )
    if has_counter:
        reasoning = (
            "Counter-evidence detected — conservative action preferred over destructive remediation."
        )

    rec = RecoveryRecommendation(
        primary_action_id=primary.action_id,
        primary_action_label=primary.label,
        reasoning=reasoning,
        alternatives=alts[:4],
        rejected_alternatives=[
            a.label for a in alts if a.action_confidence and a.action_confidence.score < 50
        ],
        expected_monthly_recovery_usd=monthly,
        reversibility=primary.reversibility,
        prerequisites=["Verify approval and policy gate", "Confirm resource still in scanned state"],
    )

    pre_checks = [
        "Re-run scanner snapshot or validate resource state",
        "Confirm evidence sufficiency not degraded",
        "Confirm approval remains valid",
    ]
    exec_steps = [f"Apply action: {primary.label} via allow-listed tooling"]
    verify_steps = [
        "Confirm resource state matches expected post-action state",
        "Validate billing impact in next cost cycle",
        "Confirm no rollback condition",
    ]
    rollback = (
        f"Reverse {primary.label} using AWS console or automation runbook"
        if primary.reversibility == "reversible"
        else "Restore from snapshot/backup if available before destructive change"
    )

    structured: list[RecoveryPlanStep] = []
    for i, title in enumerate(pre_checks, start=1):
        structured.append(
            RecoveryPlanStep(
                step_id=f"pre-{i}",
                title=title,
                phase=RecoveryPlanStepPhase.PRECHECK,
            )
        )
    for i, title in enumerate(exec_steps, start=1):
        structured.append(
            RecoveryPlanStep(
                step_id=f"exec-{i}",
                title=title,
                phase=RecoveryPlanStepPhase.EXECUTION,
            )
        )
    for i, title in enumerate(verify_steps, start=1):
        structured.append(
            RecoveryPlanStep(
                step_id=f"ver-{i}",
                title=title,
                phase=RecoveryPlanStepPhase.VERIFICATION,
            )
        )
    structured.append(
        RecoveryPlanStep(
            step_id=f"rb-{uuid.uuid4().hex[:6]}",
            title=rollback,
            phase=RecoveryPlanStepPhase.ROLLBACK,
        )
    )

    plan = RecoveryPlan(
        prerequisites=rec.prerequisites,
        pre_action_checks=pre_checks,
        execution_steps=exec_steps,
        rollback_strategy=rollback,
        verification_steps=verify_steps,
        policy_requirements=["Human approval unless AUTO_ALLOWED by recovery policy"],
        human_approval_required=True,
        structured_steps=structured,
    )
    return rec, plan
