"""Safety checks and sufficiency counts."""

from __future__ import annotations

from decimal import Decimal

from recoup.models.recovery import (
    RecoveryPolicyOutcome,
    RecoveryRecommendation,
    ResourceContext,
    ResourceEnvironment,
    ResourceIdentity,
    SafetyCheckStatus,
)
from recoup.recovery.engines.safety import has_blocking_failure, run_safety_checks
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


def test_sufficiency_includes_counts() -> None:
    finding = _idle_finding()
    signals = signals_from_finding(finding)
    graph = build_evidence_graph(signals, finding.issue)
    bundle = build_evidence_bundle(finding.issue, signals, graph)
    suff = assess_sufficiency(bundle, graph, all_signals_count=len(signals))
    assert suff.collected_signal_count == len(signals)
    assert suff.expected_signal_count >= 5
    assert suff.level.value in ("SUFFICIENT", "PARTIAL")


def test_safety_checks_no_blockers_on_idle_demo() -> None:
    ctx = ResourceContext(
        identity=ResourceIdentity(resource_id="i-x", service="EC2"),
        environment=ResourceEnvironment(is_demo=True, owner="team-a"),
    )
    rec = RecoveryRecommendation(
        primary_action_id="stop",
        primary_action_label="Stop instance",
        reversibility="reversible",
        expected_monthly_recovery_usd=Decimal("30"),
    )
    checks = run_safety_checks(ctx, rec, None, RecoveryPolicyOutcome.HITL_REQUIRED)
    assert not has_blocking_failure(checks)
    assert any(c.status == SafetyCheckStatus.PASS for c in checks)
