"""Admin reset gate — production requires RECOUP_ENABLE_ADMIN_RESET."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from recoup.api.main import app


def test_admin_reset_allowed_in_local() -> None:
    with patch("recoup.api.main.settings") as mock_settings:
        mock_settings.recoup_env = "local"
        mock_settings.recoup_enable_admin_reset = False
        mock_settings.recoup_api_key = ""
        client = TestClient(app)
        res = client.post("/api/admin/reset")
        assert res.status_code == 200
        assert res.json()["status"] == "reset"


def test_admin_reset_forbidden_in_production_by_default() -> None:
    with patch("recoup.api.main.settings") as mock_settings:
        mock_settings.recoup_env = "production"
        mock_settings.recoup_enable_admin_reset = False
        mock_settings.recoup_api_key = ""
        client = TestClient(app)
        res = client.post("/api/admin/reset")
        assert res.status_code == 403


def test_admin_reset_allowed_in_production_when_flag_set() -> None:
    with patch("recoup.api.main.settings") as mock_settings:
        mock_settings.recoup_env = "production"
        mock_settings.recoup_enable_admin_reset = True
        mock_settings.recoup_api_key = ""
        client = TestClient(app)
        res = client.post("/api/admin/reset")
        assert res.status_code == 200
