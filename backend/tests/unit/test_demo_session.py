"""Guest demo session API and partition behavior."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from recoup.api.main import app
from recoup.demo_session import DEFAULT_TEST_SESSION, DEMO_SESSION_HEADER, ensure_test_session
from recoup.demo_state import graph_states, promoted_findings


def test_create_demo_session() -> None:
    client = TestClient(app)
    res = client.post("/api/demo/session")
    assert res.status_code == 200
    body = res.json()
    assert uuid.UUID(body["session_id"])
    assert "expires_at" in body


def test_missing_session_header_rejected_in_production(monkeypatch) -> None:
    monkeypatch.setattr("recoup.api.main.settings.recoup_env", "production")
    client = TestClient(app)
    res = client.post("/api/scan/demo")
    assert res.status_code == 401
    assert res.json()["code"] == "session_required"


def test_session_isolation_for_opportunities_list() -> None:
    from recoup.graph.types import GraphState
    from recoup.models.opportunity import OpportunityState

    client = TestClient(app)
    a = client.post("/api/demo/session").json()["session_id"]
    b = client.post("/api/demo/session").json()["session_id"]
    graph_states(a)["opp-a"] = GraphState(
        opportunity_id="opp-a", state_version=1, current_state=OpportunityState.DETECTED
    )

    res_a = client.get("/api/opportunities", headers={DEMO_SESSION_HEADER: a})
    res_b = client.get("/api/opportunities", headers={DEMO_SESSION_HEADER: b})
    assert len(res_a.json()) == 1
    assert res_b.json() == []


def test_session_reset_clears_partition_only() -> None:
    client = TestClient(app)
    a = client.post("/api/demo/session").json()["session_id"]
    b = client.post("/api/demo/session").json()["session_id"]
    from recoup.graph.types import GraphState
    from recoup.models.opportunity import OpportunityState

    graph_states(a)["opp-a"] = GraphState(
        opportunity_id="opp-a", state_version=1, current_state=OpportunityState.DETECTED
    )
    graph_states(b)["opp-b"] = GraphState(
        opportunity_id="opp-b", state_version=1, current_state=OpportunityState.DETECTED
    )
    promoted_findings(a)["ns"] = {"r1": {"opportunity_id": "opp-a"}}

    reset = client.post(
        "/api/demo/session/reset",
        headers={DEMO_SESSION_HEADER: a},
    )
    assert reset.status_code == 200
    assert graph_states(a) == {}
    assert "opp-b" in graph_states(b)
    assert promoted_findings(a) == {}


def test_local_default_session_without_header() -> None:
    ensure_test_session(DEFAULT_TEST_SESSION)
    client = TestClient(app)
    res = client.get("/api/opportunities")
    assert res.status_code == 200


def test_local_demo_scan_offline_without_iam(monkeypatch) -> None:
    """Local Playwright path — demo scan works without STS AssumeRole."""
    monkeypatch.setattr("recoup.api.routes.scan.settings.recoup_env", "local")
    monkeypatch.setattr("recoup.api.routes.scan.settings.recoup_readonly_role_arn", "")
    monkeypatch.setattr("recoup.api.routes.scan.settings.recoup_external_id", "")
    client = TestClient(app)
    sid = client.post("/api/demo/session").json()["session_id"]
    res = client.post("/api/scan/demo", headers={DEMO_SESSION_HEADER: sid})
    assert res.status_code == 200
    assert len(res.json()["findings"]) >= 1
