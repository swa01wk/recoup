"""Discovery and action confidence (deterministic)."""

from __future__ import annotations

from ...models.recovery import (
    ConfidenceFactorBreakdown,
    ConfidenceScore,
    EvidenceGraph,
    EvidenceGraphRelation,
    EvidenceSufficiencyLevel,
    OperationalSignal,
)
from ..catalog import RemediationCatalogEntry


def _weighted_score(factors: ConfidenceFactorBreakdown) -> int:
    raw = (
        factors.coverage * 0.25
        + factors.agreement * 0.25
        + factors.strength * 0.20
        + factors.freshness * 0.15
        + factors.source_diversity * 0.15
        + factors.dependency_certainty * 0.10
        - factors.contradiction_penalty
        - factors.missing_evidence_penalty
    )
    return max(0, min(100, int(round(raw))))


def _base_factors(
    signals: list[OperationalSignal],
    graph: EvidenceGraph,
    sufficiency: EvidenceSufficiencyLevel,
    missing_count: int,
) -> ConfidenceFactorBreakdown:
    sources = {s.source for s in signals}
    contradictions = sum(
        1 for e in graph.edges if e.relation == EvidenceGraphRelation.CONTRADICTS
    )
    supports = sum(
        1 for e in graph.edges if e.relation == EvidenceGraphRelation.SUPPORTS
    )

    coverage = min(100.0, 40.0 + len(signals) * 8.0)
    agreement = 85.0 if contradictions == 0 else max(30.0, 85.0 - contradictions * 25.0)
    strength = min(100.0, 50.0 + supports * 15.0)
    freshness = 95.0
    diversity = min(100.0, 50.0 + len(sources) * 15.0)
    dep_certainty = 70.0 if missing_count == 0 else 45.0

    contra_pen = contradictions * 5.0
    miss_pen = missing_count * 3.0
    if sufficiency == EvidenceSufficiencyLevel.INSUFFICIENT:
        miss_pen += 15.0
    elif sufficiency == EvidenceSufficiencyLevel.CONFLICTING:
        contra_pen += 10.0

    return ConfidenceFactorBreakdown(
        coverage=coverage,
        agreement=agreement,
        strength=strength,
        freshness=freshness,
        source_diversity=diversity,
        dependency_certainty=dep_certainty,
        contradiction_penalty=contra_pen,
        missing_evidence_penalty=miss_pen,
        explanation="Deterministic weighted confidence model",
    )


def compute_discovery_confidence(
    signals: list[OperationalSignal],
    graph: EvidenceGraph,
    sufficiency: EvidenceSufficiencyLevel,
    missing_count: int,
) -> ConfidenceScore:
    factors = _base_factors(signals, graph, sufficiency, missing_count)
    score = _weighted_score(factors)
    label = "high" if score >= 80 else "medium" if score >= 55 else "low"
    return ConfidenceScore(
        score=score,
        label=label,
        factors=factors,
        evidence_signal_ids=[s.signal_id for s in signals[:20]],
    )


def compute_action_confidence(
    action: RemediationCatalogEntry,
    discovery: ConfidenceScore,
    risk_score: int,
    sufficiency: EvidenceSufficiencyLevel,
) -> ConfidenceScore:
    factors = discovery.factors.model_copy(deep=True)
    penalty = 0.0
    if action.destructive:
        penalty += 25.0
        factors.explanation = "Destructive action penalty applied"
    if sufficiency != EvidenceSufficiencyLevel.SUFFICIENT:
        penalty += 12.0
    penalty += max(0, (risk_score - 50) * 0.3)

    factors.contradiction_penalty += penalty
    score = _weighted_score(factors)
    label = "high" if score >= 80 else "medium" if score >= 55 else "low"
    return ConfidenceScore(score=score, label=label, factors=factors)
