"""Unit tests for recovery pipeline — signals, confidence, promote path."""

from __future__ import annotations

from decimal import Decimal

from recoup.adapters.finding_to_signal import FindingToSignalAdapter
from recoup.graph.recoup_graph import recoup_graph
from recoup.graph.types import GraphState
from recoup.models.opportunity import OpportunityState
from recoup.recovery.engines.confidence import compute_discovery_confidence
from recoup.recovery.engines.sufficiency import assess_sufficiency
from recoup.recovery.evidence_bundle import build_evidence_bundle
from recoup.recovery.evidence_graph import build_evidence_graph
from recoup.recovery.signals import signals_from_finding
from recoup.scanners.finding import Finding


def _idle_finding() -> Finding:
    return Finding(
        service="EC2",
        resource_id="i-testidle123456",
        resource_type="AWS::EC2::Instance",
        finding_type="IDLE_INSTANCE",
        issue="Instance avg CPU 1.8% over 7d — idle",
        estimated_monthly_savings_usd=93.0,
        recommendation="Stop if unused",
        severity="high",
        region="us-east-1",
        evidence={"cpu_utilization_7d_avg": "1.80%", "instance_type": "m5.large"},
    )


def test_signals_from_finding_factual_not_conclusive() -> None:
    signals = signals_from_finding(_idle_finding())
    assert any("1.80" in s.value for s in signals)
    assert not any(s.signal_type == "conclusion" for s in signals)


def test_discovery_confidence_reproducible() -> None:
    finding = _idle_finding()
    signals = signals_from_finding(finding)
    graph = build_evidence_graph(signals, finding.issue)
    bundle = build_evidence_bundle(finding.issue, signals, graph)
    suff = assess_sufficiency(bundle, graph)
    c1 = compute_discovery_confidence(signals, graph, suff.level, len(bundle.missing_expected))
    c2 = compute_discovery_confidence(signals, graph, suff.level, len(bundle.missing_expected))
    assert c1.score == c2.score
    assert 0 <= c1.score <= 100


def test_promote_graph_produces_recovery_assessment() -> None:
    finding = _idle_finding()
    adapter = FindingToSignalAdapter()
    state = GraphState(
        opportunity_id="recovery-test001",
        signal=adapter.adapt(finding),
        promoted_finding=finding,
        use_strands=False,
    )
    final = recoup_graph.run(state, stop_at="risk_policy_gate")
    assert final.recovery_assessment is not None
    assert final.recovery_assessment.discovery_confidence is not None
    assert final.availability_result is not None
    assert final.availability_result.potential_credit == Decimal("93.00")
    assert final.current_state == OpportunityState.AWAITING_APPROVAL


def test_counter_evidence_scenario() -> None:
    finding = _idle_finding()
    finding.scenario_tag = "nightly-batch"
    signals = signals_from_finding(finding)
    graph = build_evidence_graph(signals, finding.issue)
    bundle = build_evidence_bundle(finding.issue, signals, graph)
    assert len(bundle.counter_signal_ids) >= 1
