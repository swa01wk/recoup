"""Orchestrate OBSERVE → UNDERSTAND → DECIDE for optimization findings."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from ..graph.types import GraphState, IncidentHypothesis, PolicyDecision
from ..models.availability import AvailabilityResult
from ..models.eligibility import EligibilityAssessment
from ..models.opportunity import OpportunityState
from ..models.recovery import (
    InvestigationIteration,
    RecoveryAssessment,
)
from ..scanners.finding import Finding
from .catalog import catalog_for_service
from .engines.confidence import compute_action_confidence, compute_discovery_confidence
from .engines.financial import compute_financial_impact
from .engines.prioritization import compute_priority
from .engines.risk import assess_risk
from .engines.sufficiency import assess_sufficiency
from .evidence_bundle import build_evidence_bundle
from .engines.safety import run_safety_checks
from .evidence_graph import attach_recommendation_to_graph, build_evidence_graph
from .signal_direction import apply_signal_directions
from .investigator import deterministic_investigator, merge_llm_investigator_result
from .planner import build_recommendation_and_plan
from .policy import evaluate_recovery_policy
from .resource_context import build_resource_context
from .signals import investigation_probe_signals, merge_signals, signals_from_finding


def is_optimization_path(state: GraphState) -> bool:
    return bool(state.signal and state.signal.source == "optimization")


def _finding_from_state(state: GraphState) -> Finding | None:
    if state.promoted_finding is not None:
        return state.promoted_finding
    return None


def run_recovery_pipeline(
    state: GraphState,
    *,
    use_llm: bool = False,
) -> dict[str, Any]:
    """
    Run full recovery assessment for optimization path.
    Returns GraphState field updates.
    """
    finding = _finding_from_state(state)
    if finding is None:
        return {"errors": state.errors + ["recovery: no promoted_finding on state"]}

    signals = signals_from_finding(finding)
    ctx = build_resource_context(finding, signals)
    claim = finding.issue
    graph = build_evidence_graph(signals, claim)
    bundle = build_evidence_bundle(claim, signals, graph)
    sufficiency = assess_sufficiency(bundle, graph, all_signals_count=len(signals))
    signals = apply_signal_directions(signals, bundle)

    inv_base = deterministic_investigator(finding, ctx, bundle, signals)
    llm_result = None
    if use_llm and state.use_strands:
        try:
            from ..agents.strands_agents import run_recovery_investigator_agent  # noqa: PLC0415

            llm_result = run_recovery_investigator_agent(state, finding, ctx, bundle)
        except Exception:  # noqa: BLE001
            llm_result = None
    inv = merge_llm_investigator_result(inv_base, llm_result)

    discovery = compute_discovery_confidence(
        signals,
        graph,
        sufficiency.level,
        len(bundle.missing_expected),
    )

    catalog = catalog_for_service(finding.service)
    action_confidences: dict[str, Any] = {}
    primary_entry = catalog[0]
    for entry in catalog:
        risk_tmp = assess_risk(ctx, entry)
        action_confidences[entry.action_id] = compute_action_confidence(
            entry,
            discovery,
            risk_tmp.score,
            sufficiency.level,
        )

    has_counter = len(bundle.counter_signal_ids) > 0
    from .planner import _pick_primary  # noqa: PLC0415

    primary_entry = _pick_primary(finding, catalog, has_counter)
    risk = assess_risk(ctx, primary_entry)
    financial = compute_financial_impact(finding)

    rec, plan = build_recommendation_and_plan(
        finding,
        ctx,
        action_confidences,
        has_counter,
        financial.projected_monthly_recovery_usd,
    )

    graph = attach_recommendation_to_graph(graph, rec.primary_action_label)

    primary_conf = action_confidences.get(rec.primary_action_id)
    action_score = primary_conf.score if primary_conf else 50

    policy_outcome, policy_decision, policy_note = evaluate_recovery_policy(
        ctx,
        sufficiency.level,
        discovery.score,
        action_score,
        risk.level,
        primary_entry,
    )

    safety = run_safety_checks(ctx, rec, primary_entry, policy_outcome)

    assessment = RecoveryAssessment(
        pipeline_phase="UNDERSTAND",
        resource_context=ctx,
        signals=signals,
        evidence_graph=graph,
        evidence_bundle=bundle,
        insights=inv["insights"],
        evidence_sufficiency=sufficiency,
        discovery_confidence=discovery,
        action_confidences=action_confidences,
        risk_assessment=risk,
        financial_impact=financial,
        recommendation=rec,
        recovery_plan=plan,
        recovery_policy_outcome=policy_outcome,
        policy_note=policy_note,
        investigation_plan=inv.get("investigation_plan", []),
        safety_checks=safety,
    )
    priority, pexpl = compute_priority(assessment)
    assessment.priority_score = priority
    assessment.priority_explanation = pexpl

    savings = financial.projected_monthly_recovery_usd
    hypothesis = IncidentHypothesis(
        service=finding.service,
        region=finding.region,
        incident_date=state.signal.start.date() if state.signal else date.today(),
        affected_resource_ids=[finding.resource_id],
        summary=inv.get("hypothesis_summary", finding.issue),
        confidence=discovery.score / 100.0,
    )

    availability = AvailabilityResult(
        monthly_uptime_pct=Decimal("100"),
        threshold_breached=False,
        tier_pct=Decimal("0"),
        billed_charges=(savings * Decimal("12")).quantize(Decimal("0.01")),
        potential_credit=savings,
        calculation_trace=financial.calculation_trace
        + [f"Recommendation: {rec.primary_action_label}"],
    )

    eligibility = EligibilityAssessment(
        eligible_estimate=sufficiency.level.value != "INSUFFICIENT",
        confidence=discovery.score / 100.0,
        satisfied_requirements=[rec.primary_action_label],
        unresolved=bundle.missing_expected,
        possible_exclusions=(
            ["Counter-evidence under review"] if has_counter else []
        ),
        evidence_refs=[s.signal_id for s in signals[:10]],
    )

    opp_state = OpportunityState.AWAITING_APPROVAL

    return {
        "recovery_assessment": assessment,
        "hypothesis": hypothesis,
        "availability_result": availability,
        "eligibility_assessment": eligibility,
        "policy_decision": policy_decision,
        "current_state": opp_state,
    }


def enrich_assessment_investigation(state: GraphState) -> dict[str, Any]:
    """Re-run pipeline after investigate-further probes."""
    finding = _finding_from_state(state)
    if finding is None or state.recovery_assessment is None:
        return {"errors": state.errors + ["investigation: missing finding or assessment"]}

    prior = state.recovery_assessment
    probes = prior.investigation_plan[:3] or ["dependency_scan", "extended_metrics"]
    new_sigs = investigation_probe_signals(finding.resource_id, probes)
    signals = merge_signals(prior.signals, new_sigs)

    ctx = build_resource_context(finding, signals)
    claim = finding.issue
    graph = build_evidence_graph(signals, claim)
    bundle = build_evidence_bundle(claim, signals, graph)
    sufficiency = assess_sufficiency(bundle, graph, all_signals_count=len(signals))
    signals = apply_signal_directions(signals, bundle)
    inv = deterministic_investigator(finding, ctx, bundle, signals)
    discovery = compute_discovery_confidence(
        signals, graph, sufficiency.level, len(bundle.missing_expected)
    )

    catalog = catalog_for_service(finding.service)
    action_confidences = {}
    for entry in catalog:
        rt = assess_risk(ctx, entry)
        action_confidences[entry.action_id] = compute_action_confidence(
            entry, discovery, rt.score, sufficiency.level
        )

    has_counter = len(bundle.counter_signal_ids) > 0
    from .planner import _pick_primary  # noqa: PLC0415

    primary_entry = _pick_primary(finding, catalog, has_counter)
    risk = assess_risk(ctx, primary_entry)
    financial = compute_financial_impact(finding)
    rec, plan = build_recommendation_and_plan(
        finding, ctx, action_confidences, has_counter, financial.projected_monthly_recovery_usd
    )

    graph = attach_recommendation_to_graph(graph, rec.primary_action_label)

    primary_conf = action_confidences.get(rec.primary_action_id)
    policy_outcome, policy_decision, policy_note = evaluate_recovery_policy(
        ctx,
        sufficiency.level,
        discovery.score,
        primary_conf.score if primary_conf else 50,
        risk.level,
        primary_entry,
    )

    safety = run_safety_checks(ctx, rec, primary_entry, policy_outcome)

    prev_label = (
        prior.recommendation.primary_action_label if prior.recommendation else ""
    )
    rec_changed = (
        prior.recommendation.primary_action_id != rec.primary_action_id
        if prior.recommendation
        else False
    )
    reason_change = ""
    if rec_changed:
        reason_change = (
            "Extended investigation updated correlated signals and action confidence."
        )

    iteration = InvestigationIteration(
        iteration=len(prior.audit_trail) + 1,
        missing_before=list(prior.evidence_bundle.missing_expected),
        sufficiency_before=(
            prior.evidence_sufficiency.level if prior.evidence_sufficiency else None
        ),
        discovery_confidence_before=(
            prior.discovery_confidence.score if prior.discovery_confidence else None
        ),
        action_confidence_before=(
            prior.action_confidences.get(rec.primary_action_id).score
            if prior.action_confidences.get(rec.primary_action_id)
            else None
        ),
        sufficiency_after=sufficiency.level,
        discovery_confidence_after=discovery.score,
        action_confidence_after=primary_conf.score if primary_conf else None,
        notes="Investigation probes merged",
        recommendation_changed=rec_changed,
        reason_for_change=reason_change,
        previous_primary_action_label=prev_label,
        new_primary_action_label=rec.primary_action_label,
    )

    assessment = prior.model_copy(
        update={
            "signals": signals,
            "resource_context": ctx,
            "evidence_graph": graph,
            "evidence_bundle": bundle,
            "insights": inv["insights"],
            "evidence_sufficiency": sufficiency,
            "discovery_confidence": discovery,
            "action_confidences": action_confidences,
            "risk_assessment": risk,
            "recommendation": rec,
            "recovery_plan": plan,
            "recovery_policy_outcome": policy_outcome,
            "policy_note": policy_note,
            "investigation_plan": inv.get("investigation_plan", []),
            "audit_trail": prior.audit_trail + [iteration],
            "safety_checks": safety,
        }
    )
    priority, pexpl = compute_priority(assessment)
    assessment.priority_score = priority
    assessment.priority_explanation = pexpl

    opp_state = OpportunityState.AWAITING_APPROVAL
    if policy_outcome.value == "INVESTIGATE_FURTHER":
        opp_state = OpportunityState.AWAITING_APPROVAL

    return {
        "recovery_assessment": assessment,
        "policy_decision": PolicyDecision.REQUIRE_APPROVAL,
        "current_state": opp_state,
        "hypothesis": state.hypothesis.model_copy(
            update={"summary": inv.get("hypothesis_summary", finding.issue)}
        )
        if state.hypothesis
        else None,
        "investigation_iteration": iteration,
    }
