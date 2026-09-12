"""Materialize evidence bundle from graph and signals."""

from __future__ import annotations

from ..models.recovery import (
    EvidenceBundle,
    EvidenceGraph,
    EvidenceGraphRelation,
    OperationalSignal,
)


def build_evidence_bundle(
    claim: str,
    signals: list[OperationalSignal],
    graph: EvidenceGraph,
) -> EvidenceBundle:
    claim_id = "claim-primary"
    supporting: list[str] = []
    counter: list[str] = []
    neutral: list[str] = []

    for edge in graph.edges:
        if edge.target_id != claim_id:
            continue
        if edge.relation == EvidenceGraphRelation.SUPPORTS:
            supporting.append(edge.source_id)
        elif edge.relation == EvidenceGraphRelation.CONTRADICTS:
            counter.append(edge.source_id)
        elif edge.relation in (
            EvidenceGraphRelation.NEUTRAL,
            EvidenceGraphRelation.DERIVED_FROM,
        ):
            neutral.append(edge.source_id)

    grouped: dict[str, list[str]] = {
        "utilization": [],
        "activity": [],
        "cost": [],
        "dependencies": [],
        "ownership": [],
        "operational_context": [],
    }
    for sig in signals:
        bucket = "operational_context"
        if sig.signal_type == "utilization":
            bucket = "utilization"
        elif sig.signal_type == "activity":
            bucket = "activity"
        elif sig.signal_type == "cost":
            bucket = "cost"
        elif sig.metric_or_event in ("owner", "scenario_tag", "RecoupDemo"):
            bucket = "ownership"
        grouped[bucket].append(sig.signal_id)

    missing: list[str] = []
    if not any(s.signal_type == "activity" for s in signals):
        missing.append("CloudTrail or operational activity window")
    if not grouped["dependencies"] and "EC2" in claim:
        missing.append("Dependency attachment scan")

    return EvidenceBundle(
        claim=claim,
        supporting_signal_ids=list(dict.fromkeys(supporting)),
        counter_signal_ids=list(dict.fromkeys(counter)),
        neutral_signal_ids=list(dict.fromkeys(neutral)),
        missing_expected=missing,
        grouped=grouped,
    )
