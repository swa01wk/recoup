"""Global demo epoch and reset lock."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from recoup.api.main import app
from recoup.demo_control import bump_global_epoch, get_global_epoch, sync_global_epoch
from recoup.demo_session import DEFAULT_TEST_SESSION
from recoup.demo_state import graph_states


def test_sync_global_epoch_clears_memory() -> None:
    from recoup.graph.types import GraphState
    from recoup.models.opportunity import OpportunityState

    graph_states(DEFAULT_TEST_SESSION)["z"] = GraphState(
        opportunity_id="z", state_version=1, current_state=OpportunityState.DETECTED
    )
    import recoup.demo_control as dc

    old = dc._local_global_epoch
    dc._local_global_epoch = 0
    try:
        with patch.object(dc, "get_global_epoch", return_value=5):
            sync_global_epoch()
    finally:
        dc._local_global_epoch = old
    assert graph_states(DEFAULT_TEST_SESSION) == {}


def test_global_reset_forbidden_without_flag() -> None:
    with patch("recoup.api.main.settings") as mock_settings:
        mock_settings.recoup_env = "production"
        mock_settings.recoup_enable_global_reset = False
        mock_settings.recoup_api_key = ""
        mock_settings.recoup_enable_admin_reset = True
        client = TestClient(app)
        res = client.post(
            "/api/admin/reset?scope=global",
            headers={"X-Demo-Session": DEFAULT_TEST_SESSION},
        )
        assert res.status_code == 403


def test_session_reset_does_not_bump_global_epoch() -> None:
    before = get_global_epoch()
    bump_global_epoch()
    mid = get_global_epoch()
    assert mid >= before + 1
