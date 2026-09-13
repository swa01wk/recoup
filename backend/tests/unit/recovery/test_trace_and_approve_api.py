"""API-level promote → trace → approve (in-memory graph, no live AWS scan)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from recoup.adapters.finding_to_signal import FindingToSignalAdapter
from recoup.api.main import app
from recoup.api.routes import opportunities as opp_routes
from recoup.api.routes import scan as scan_routes
from recoup.graph.recoup_graph import recoup_graph
from recoup.graph.types import GraphState
from recoup.models.opportunity import OpportunityState
from recoup.scanners.finding import Finding


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def _seed_promoted_opportunity(finding: Finding) -> str:
    from recoup.demo_session import DEFAULT_TEST_SESSION, bind_session, ensure_test_session
    from recoup.demo_state import graph_states, promoted_findings

    ensure_test_session(DEFAULT_TEST_SESSION)
    bind_session(DEFAULT_TEST_SESSION)
    sid = DEFAULT_TEST_SESSION
    graph_states(sid).clear()
    promoted_findings(sid).clear()
    adapter = FindingToSignalAdapter()
    opp_id = "recovery-api-test-001"
    state = GraphState(
        opportunity_id=opp_id,
        signal=adapter.adapt(finding),
        promoted_finding=finding,
        use_strands=False,
    )
    final = recoup_graph.run(state, stop_at="risk_policy_gate")
    if final.state_version == 0:
        final = final.model_copy(update={"state_version": 1})
    graph_states(sid)[opp_id] = final
    opp_routes._maybe_create_approval(final)
    promoted_findings(sid).setdefault("demo", {})[finding.resource_id] = {
        "opportunity_id": opp_id,
        "finding": finding.model_dump(mode="json"),
    }
    return opp_id


def test_trace_includes_workflow_and_assessment(client: TestClient) -> None:
    finding = Finding(
        service="EC2",
        resource_id="i-traceapprove001",
        resource_type="AWS::EC2::Instance",
        finding_type="IDLE_INSTANCE",
        issue="Idle instance",
        estimated_monthly_savings_usd=Decimal("30.37"),
        recommendation="Stop",
        severity="high",
        region="us-east-1",
        evidence={"cpu_utilization_7d_avg": "1.80%"},
    )
    client.post("/api/test/reset")
    opp_id = _seed_promoted_opportunity(finding)

    trace = client.get(f"/api/opportunities/{opp_id}/trace").json()
    assert trace.get("recovery_assessment") is not None
    assert trace.get("workflow", {}).get("pipeline_stage") == 8
    ra = trace["recovery_assessment"]
    assert ra.get("safety_checks")
    assert ra.get("evidence_sufficiency", {}).get("expected_signal_count", 0) >= 1
    assert any(n.get("kind") == "recommendation" for n in ra.get("evidence_graph", {}).get("nodes", []))


def test_approve_succeeds_with_assessment_gate(client: TestClient) -> None:
    finding = Finding(
        service="EC2",
        resource_id="i-traceapprove002",
        resource_type="AWS::EC2::Instance",
        finding_type="IDLE_INSTANCE",
        issue="Idle instance",
        estimated_monthly_savings_usd=Decimal("30.37"),
        recommendation="Stop",
        severity="high",
        region="us-east-1",
        evidence={"cpu_utilization_7d_avg": "1.80%"},
    )
    client.post("/api/test/reset")
    opp_id = _seed_promoted_opportunity(finding)

    pending = client.get(f"/api/approvals/opportunity/{opp_id}").json()
    assert pending is not None
    res = client.post(
        f"/api/approvals/opportunity/{opp_id}/approve",
        json={
            "principal": "pytest",
            "claim_hash": pending["claim_hash"],
            "amount": pending["amount"],
            "state_version": pending["state_version"],
            "notes": "ok",
        },
    )
    assert res.status_code == 200, res.text
    opp = client.get(f"/api/opportunities/{opp_id}").json()
    assert opp["state"] in ("APPROVED", "RECOVERED", "SUBMITTING", "SUBMITTED")


def test_pending_amount_matches_financial_impact(client: TestClient) -> None:
    finding = Finding(
        service="EC2",
        resource_id="i-amount-match001",
        resource_type="AWS::EC2::Instance",
        finding_type="IDLE_INSTANCE",
        issue="Idle",
        estimated_monthly_savings_usd=Decimal("30.37"),
        recommendation="Stop",
        severity="high",
        region="us-east-1",
        evidence={"cpu_utilization_7d_avg": "1.80%"},
    )
    client.post("/api/test/reset")
    opp_id = _seed_promoted_opportunity(finding)
    pending = client.get(f"/api/approvals/opportunity/{opp_id}").json()
    trace = client.get(f"/api/opportunities/{opp_id}/trace").json()
    fin = trace["recovery_assessment"]["financial_impact"]["projected_monthly_recovery_usd"]
    assert Decimal(str(pending["amount"])) == Decimal(str(fin))
