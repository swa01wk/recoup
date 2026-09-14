"""Evidence sufficiency assessment."""

from __future__ import annotations

from typing import Any

from ...models.recovery import (
    EvidenceBundle,
    EvidenceGraph,
    EvidenceGraphRelation,
    EvidenceSufficiency,
    EvidenceSufficiencyLevel,
)


def assess_sufficiency(
    bundle: EvidenceBundle,
    graph: EvidenceGraph,
    *,
    all_signals_count: int = 0,
) -> EvidenceSufficiency:
    reasons: list[str] = []
    contradictions = sum(
        1 for e in graph.edges if e.relation == EvidenceGraphRelation.CONTRADICTS
    )
    supporting = len(bundle.supporting_signal_ids)
    expected = max(5, len(bundle.supporting_signal_ids) + len(bundle.missing_expected))
    collected = all_signals_count or (
        len(bundle.supporting_signal_ids)
        + len(bundle.counter_signal_ids)
        + len(bundle.neutral_signal_ids)
    )
    missing_critical = list(bundle.missing_expected)

    base_kwargs: dict[str, Any] = {
        "expected_signal_count": expected,
        "collected_signal_count": collected,
        "missing_critical_signals": missing_critical,
        "contradiction_count": contradictions,
    }

    if supporting == 0:
        return EvidenceSufficiency(
            level=EvidenceSufficiencyLevel.INSUFFICIENT,
            reasons=["No supporting signals linked to the primary claim"],
            **base_kwargs,
        )

    if contradictions >= 2:
        return EvidenceSufficiency(
            level=EvidenceSufficiencyLevel.CONFLICTING,
            reasons=["Multiple contradictory signals affect the primary claim"],
            **base_kwargs,
        )

    if contradictions == 1:
        reasons.append("Contradictory evidence requires interpretation")
        if bundle.missing_expected:
            reasons.extend(bundle.missing_expected)
        return EvidenceSufficiency(
            level=EvidenceSufficiencyLevel.PARTIAL,
            reasons=reasons,
            **base_kwargs,
        )

    if bundle.missing_expected:
        reasons.extend([f"Missing: {m}" for m in bundle.missing_expected])
        return EvidenceSufficiency(
            level=EvidenceSufficiencyLevel.PARTIAL,
            reasons=reasons,
            **base_kwargs,
        )

    return EvidenceSufficiency(
        level=EvidenceSufficiencyLevel.SUFFICIENT,
        reasons=["Required signal coverage met for this finding type"],
        **base_kwargs,
    )
