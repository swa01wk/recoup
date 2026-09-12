"""In-memory evidence graph from signals."""

from __future__ import annotations

import hashlib

from ..models.recovery import (
    EvidenceGraph,
    EvidenceGraphEdge,
    EvidenceGraphNode,
    EvidenceGraphRelation,
    OperationalSignal,
)


def _eid(src: str, tgt: str, rel: str) -> str:
    raw = f"{src}|{tgt}|{rel}"
    return "edge-" + hashlib.sha256(raw.encode()).hexdigest()[:10]


def build_evidence_graph(
    signals: list[OperationalSignal],
    claim: str,
) -> EvidenceGraph:
    nodes: list[EvidenceGraphNode] = []
    edges: list[EvidenceGraphEdge] = []

    for sig in signals:
        nodes.append(
            EvidenceGraphNode(
                node_id=sig.signal_id,
                kind="signal",
                label=sig.description[:120] or sig.metric_or_event,
                signal_id=sig.signal_id,
            )
        )

    claim_id = "claim-primary"
    nodes.append(
        EvidenceGraphNode(node_id=claim_id, kind="claim", label=claim[:160])
    )

    supporting: list[str] = []
    contradicting: list[str] = []

    for sig in signals:
        val_lower = sig.value.lower()
        if sig.signal_type == "utilization":
            try:
                num = float(sig.value.replace("%", "").strip())
                if num < 5.0:
                    supporting.append(sig.signal_id)
                    edges.append(
                        EvidenceGraphEdge(
                            edge_id=_eid(sig.signal_id, claim_id, "supports"),
                            source_id=sig.signal_id,
                            target_id=claim_id,
                            relation=EvidenceGraphRelation.SUPPORTS,
                        )
                    )
            except ValueError:
                pass
        if sig.signal_type in ("cost", "finding", "activity", "metadata"):
            if sig.signal_id not in supporting and sig.signal_id not in contradicting:
                supporting.append(sig.signal_id)
                edges.append(
                    EvidenceGraphEdge(
                        edge_id=_eid(sig.signal_id, claim_id, "supports"),
                        source_id=sig.signal_id,
                        target_id=claim_id,
                        relation=EvidenceGraphRelation.SUPPORTS,
                    )
                )
        if sig.metric_or_event == "periodic_workload" or "nightly" in val_lower:
            contradicting.append(sig.signal_id)
            edges.append(
                EvidenceGraphEdge(
                    edge_id=_eid(sig.signal_id, claim_id, "contradicts"),
                    source_id=sig.signal_id,
                    target_id=claim_id,
                    relation=EvidenceGraphRelation.CONTRADICTS,
                )
            )
        if sig.metric_or_event == "severity" and sig.value == "low":
            edges.append(
                EvidenceGraphEdge(
                    edge_id=_eid(sig.signal_id, claim_id, "neutral"),
                    source_id=sig.signal_id,
                    target_id=claim_id,
                    relation=EvidenceGraphRelation.NEUTRAL,
                )
            )

    if finding_type := _signal_value(signals, "finding_type"):
        if finding_type in ("IDLE_INSTANCE", "STOPPED_INSTANCE", "UNATTACHED_VOLUME"):
            for sig in signals:
                if sig.signal_type == "finding" and sig.metric_or_event == "issue":
                    edges.append(
                        EvidenceGraphEdge(
                            edge_id=_eid(sig.signal_id, claim_id, "derived"),
                            source_id=sig.signal_id,
                            target_id=claim_id,
                            relation=EvidenceGraphRelation.DERIVED_FROM,
                        )
                    )

    return EvidenceGraph(nodes=nodes, edges=edges)


def attach_recommendation_to_graph(
    graph: EvidenceGraph,
    recommendation_label: str,
) -> EvidenceGraph:
    """Add recommendation node and claim → recommendation edge for UI column view."""
    if not recommendation_label:
        return graph
    rec_id = "recommendation-primary"
    claim_id = "claim-primary"
    nodes = list(graph.nodes)
    edges = list(graph.edges)
    if not any(n.node_id == rec_id for n in nodes):
        nodes.append(
            EvidenceGraphNode(
                node_id=rec_id,
                kind="recommendation",
                label=recommendation_label[:160],
            )
        )
    if any(n.node_id == claim_id for n in nodes):
        edges.append(
            EvidenceGraphEdge(
                edge_id=_eid(claim_id, rec_id, "leads_to"),
                source_id=claim_id,
                target_id=rec_id,
                relation=EvidenceGraphRelation.LEADS_TO,
            )
        )
    return EvidenceGraph(nodes=nodes, edges=edges)


def _signal_value(signals: list[OperationalSignal], metric: str) -> str | None:
    for s in signals:
        if s.metric_or_event == metric:
            return s.value
    return None


def count_relations(graph: EvidenceGraph, relation: EvidenceGraphRelation) -> int:
    return sum(1 for e in graph.edges if e.relation == relation)
