"""
Phase 6e tests — IAM Security Model & STS AssumeRole Architecture.

Coverage:
  - CustomerConnection model validation
  - CustomerConnection.build_session() happy path (mocked STS)
  - CustomerConnection.build_session() failure / wrong ExternalId (HTTP 400)
  - Session cache behaviour (cache hit / miss / clear)
  - ScanRequest model: role_arn + external_id required; no raw access keys
  - ScanResult model: STS provenance fields present
  - /api/scan/preview and /api/scan/full raise HTTP 400 on STS failure
  - ec2_tools.stop_demo_instance uses RecoupRemediationRole when configured
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from recoup.models.connection import _SESSION_CACHE, CustomerConnection
from recoup.scanners.finding import ScanRequest, ScanResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_ROLE_ARN = "arn:aws:iam::123456789012:role/RecoupReadOnlyRole"
_FAKE_REMEDIATION_ARN = "arn:aws:iam::123456789012:role/RecoupRemediationRole"
_FAKE_EXT_ID = "recoup-demo-external-id"

_FAKE_STS_RESPONSE: dict[str, Any] = {
    "Credentials": {
        "AccessKeyId": "ASIAFAKEACCESSKEY",
        "SecretAccessKey": "fakeSecretKey",
        "SessionToken": "fakeSessionToken",
    },
    "AssumedRoleUser": {
        "Arn": "arn:aws:sts::123456789012:assumed-role/RecoupReadOnlyRole/recoup-analysis-session",
        "AssumedRoleId": "AROAFAKEID:recoup-analysis-session",
    },
}


def _make_mock_sts_client(response: dict[str, Any] | None = None) -> MagicMock:
    """Return a mock STS client that returns *response* for assume_role."""
    mock_sts = MagicMock()
    mock_sts.assume_role.return_value = response or _FAKE_STS_RESPONSE
    return mock_sts


# ---------------------------------------------------------------------------
# 1. CustomerConnection model validation
# ---------------------------------------------------------------------------


class TestCustomerConnectionModel:
    def test_requires_role_arn(self) -> None:
        with pytest.raises(ValidationError, match="role_arn"):
            CustomerConnection(external_id=_FAKE_EXT_ID)  # type: ignore[call-arg]

    def test_requires_external_id(self) -> None:
        with pytest.raises(ValidationError, match="external_id"):
            CustomerConnection(role_arn=_FAKE_ROLE_ARN)  # type: ignore[call-arg]

    def test_default_region(self) -> None:
        conn = CustomerConnection(role_arn=_FAKE_ROLE_ARN, external_id=_FAKE_EXT_ID)
        assert conn.region == "us-east-1"

    def test_default_session_name(self) -> None:
        conn = CustomerConnection(role_arn=_FAKE_ROLE_ARN, external_id=_FAKE_EXT_ID)
        assert conn.session_name == "recoup-analysis-session"

    def test_account_id_initially_none(self) -> None:
        conn = CustomerConnection(role_arn=_FAKE_ROLE_ARN, external_id=_FAKE_EXT_ID)
        assert conn.account_id is None

    def test_assumed_role_arn_initially_none(self) -> None:
        conn = CustomerConnection(role_arn=_FAKE_ROLE_ARN, external_id=_FAKE_EXT_ID)
        assert conn.assumed_role_arn is None


# ---------------------------------------------------------------------------
# 2. CustomerConnection.build_session() — happy path
# ---------------------------------------------------------------------------


class TestCustomerConnectionBuildSession:
    def setup_method(self) -> None:
        CustomerConnection.clear_cache()

    def test_returns_boto3_session(self) -> None:
        conn = CustomerConnection(role_arn=_FAKE_ROLE_ARN, external_id=_FAKE_EXT_ID)
        with patch("boto3.client", return_value=_make_mock_sts_client()):
            session = conn.build_session(use_cache=False)
        import boto3
        assert isinstance(session, boto3.Session)

    def test_populates_account_id(self) -> None:
        conn = CustomerConnection(role_arn=_FAKE_ROLE_ARN, external_id=_FAKE_EXT_ID)
        with patch("boto3.client", return_value=_make_mock_sts_client()):
            conn.build_session(use_cache=False)
        assert conn.account_id == "123456789012"

    def test_populates_assumed_role_arn(self) -> None:
        conn = CustomerConnection(role_arn=_FAKE_ROLE_ARN, external_id=_FAKE_EXT_ID)
        with patch("boto3.client", return_value=_make_mock_sts_client()):
            conn.build_session(use_cache=False)
        assert conn.assumed_role_arn is not None
        assert "assumed-role" in conn.assumed_role_arn

    def test_passes_correct_role_arn_to_sts(self) -> None:
        conn = CustomerConnection(role_arn=_FAKE_ROLE_ARN, external_id=_FAKE_EXT_ID)
        mock_sts = _make_mock_sts_client()
        with patch("boto3.client", return_value=mock_sts):
            conn.build_session(use_cache=False)
        call_kwargs = mock_sts.assume_role.call_args[1]
        assert call_kwargs["RoleArn"] == _FAKE_ROLE_ARN

    def test_passes_external_id_to_sts(self) -> None:
        conn = CustomerConnection(role_arn=_FAKE_ROLE_ARN, external_id=_FAKE_EXT_ID)
        mock_sts = _make_mock_sts_client()
        with patch("boto3.client", return_value=mock_sts):
            conn.build_session(use_cache=False)
        call_kwargs = mock_sts.assume_role.call_args[1]
        assert call_kwargs["ExternalId"] == _FAKE_EXT_ID

    def test_session_duration_1_hour(self) -> None:
        conn = CustomerConnection(role_arn=_FAKE_ROLE_ARN, external_id=_FAKE_EXT_ID)
        mock_sts = _make_mock_sts_client()
        with patch("boto3.client", return_value=mock_sts):
            conn.build_session(use_cache=False)
        call_kwargs = mock_sts.assume_role.call_args[1]
        assert call_kwargs["DurationSeconds"] == 3600


# ---------------------------------------------------------------------------
# 3. Session cache behaviour
# ---------------------------------------------------------------------------


class TestSessionCache:
    def setup_method(self) -> None:
        CustomerConnection.clear_cache()

    def test_cache_hit_avoids_second_sts_call(self) -> None:
        conn = CustomerConnection(role_arn=_FAKE_ROLE_ARN, external_id=_FAKE_EXT_ID)
        mock_sts = _make_mock_sts_client()
        with patch("boto3.client", return_value=mock_sts):
            conn.build_session(use_cache=True)
            conn.build_session(use_cache=True)
        # STS assume_role called only once
        assert mock_sts.assume_role.call_count == 1

    def test_use_cache_false_forces_fresh_assume(self) -> None:
        conn = CustomerConnection(role_arn=_FAKE_ROLE_ARN, external_id=_FAKE_EXT_ID)
        mock_sts = _make_mock_sts_client()
        with patch("boto3.client", return_value=mock_sts):
            conn.build_session(use_cache=False)
            conn.build_session(use_cache=False)
        assert mock_sts.assume_role.call_count == 2

    def test_clear_cache_flushes_entries(self) -> None:
        conn = CustomerConnection(role_arn=_FAKE_ROLE_ARN, external_id=_FAKE_EXT_ID)
        mock_sts = _make_mock_sts_client()
        with patch("boto3.client", return_value=mock_sts):
            conn.build_session(use_cache=True)
        assert len(_SESSION_CACHE) > 0
        CustomerConnection.clear_cache()
        assert len(_SESSION_CACHE) == 0


# ---------------------------------------------------------------------------
# 4. STS failure → ClientError → propagated correctly
# ---------------------------------------------------------------------------


class TestSTSFailure:
    def setup_method(self) -> None:
        CustomerConnection.clear_cache()

    def test_sts_client_error_propagates(self) -> None:
        import botocore.exceptions

        conn = CustomerConnection(role_arn=_FAKE_ROLE_ARN, external_id="wrong-ext-id")
        mock_sts = MagicMock()
        mock_sts.assume_role.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "ExternalId mismatch"}},
            "AssumeRole",
        )
        with patch("boto3.client", return_value=mock_sts):
            with pytest.raises(botocore.exceptions.ClientError, match="ExternalId mismatch"):
                conn.build_session(use_cache=False)


# ---------------------------------------------------------------------------
# 5. ScanRequest model — Phase 6e shape (role_arn + external_id)
# ---------------------------------------------------------------------------


class TestScanRequestModel:
    def test_role_arn_required(self) -> None:
        with pytest.raises(ValidationError, match="role_arn"):
            ScanRequest(external_id=_FAKE_EXT_ID)  # type: ignore[call-arg]

    def test_external_id_required(self) -> None:
        with pytest.raises(ValidationError, match="external_id"):
            ScanRequest(role_arn=_FAKE_ROLE_ARN)  # type: ignore[call-arg]

    def test_no_access_key_field(self) -> None:
        """Phase 6e removed raw access keys from ScanRequest — confirm absent."""
        req = ScanRequest(role_arn=_FAKE_ROLE_ARN, external_id=_FAKE_EXT_ID)
        assert not hasattr(req, "access_key_id"), "access_key_id must not exist in ScanRequest"
        assert not hasattr(req, "secret_access_key"), "secret_access_key must not exist"

    def test_default_region(self) -> None:
        req = ScanRequest(role_arn=_FAKE_ROLE_ARN, external_id=_FAKE_EXT_ID)
        assert req.region == "us-east-1"

    def test_custom_region(self) -> None:
        req = ScanRequest(role_arn=_FAKE_ROLE_ARN, external_id=_FAKE_EXT_ID, region="eu-west-1")
        assert req.region == "eu-west-1"


# ---------------------------------------------------------------------------
# 6. ScanResult model — STS provenance fields present
# ---------------------------------------------------------------------------


class TestScanResultModel:
    def test_sts_provenance_fields_exist(self) -> None:
        """ScanResult must carry the Phase 6e STS provenance fields."""
        result = ScanResult(
            scanned_at="2026-09-03T12:00:00+00:00",
            region="us-east-1",
            findings=[],
            total_estimated_monthly_savings_usd=0.0,
            errors=[],
            scan_duration_seconds=0.1,
            assumed_role_arn=_FAKE_ROLE_ARN,
            assumed_role_account_id="123456789012",
            session_name="recoup-analysis-session",
        )
        assert result.assumed_role_arn == _FAKE_ROLE_ARN
        assert result.assumed_role_account_id == "123456789012"
        assert result.session_name == "recoup-analysis-session"

    def test_provenance_fields_optional(self) -> None:
        """Fields should default to None when not provided."""
        result = ScanResult(
            scanned_at="2026-09-03T12:00:00+00:00",
            region="us-east-1",
            findings=[],
            total_estimated_monthly_savings_usd=0.0,
            errors=[],
            scan_duration_seconds=0.1,
        )
        assert result.assumed_role_arn is None
        assert result.assumed_role_account_id is None
        assert result.session_name is None


# ---------------------------------------------------------------------------
# 7. Scan API routes — HTTP 400 on STS failure
# ---------------------------------------------------------------------------


@pytest.fixture()
def scan_client() -> TestClient:
    from recoup.api.main import app
    return TestClient(app, raise_server_exceptions=False)


class TestScanRouteSTSError:
    def test_preview_returns_400_on_sts_failure(self, scan_client: TestClient) -> None:
        """POST /api/scan/preview should return 400 when STS AssumeRole fails."""
        import botocore.exceptions

        err = botocore.exceptions.ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Invalid ExternalId"}},
            "AssumeRole",
        )
        with patch("recoup.api.routes.scan.CustomerConnection.build_session", side_effect=err):
            resp = scan_client.post(
                "/api/scan/preview",
                json={"role_arn": _FAKE_ROLE_ARN, "external_id": "wrong"},
            )
        assert resp.status_code == 400
        assert "assume role" in resp.json()["detail"].lower()

    def test_full_returns_400_on_sts_failure(self, scan_client: TestClient) -> None:
        """POST /api/scan/full should return 400 when STS AssumeRole fails."""
        import botocore.exceptions

        err = botocore.exceptions.ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Role not found"}},
            "AssumeRole",
        )
        with patch("recoup.api.routes.scan.CustomerConnection.build_session", side_effect=err):
            resp = scan_client.post(
                "/api/scan/full",
                json={"role_arn": "arn:aws:iam::999:role/NoSuchRole", "external_id": "x"},
            )
        assert resp.status_code == 400

    def test_preview_success_returns_sts_provenance(self, scan_client: TestClient) -> None:
        """On a successful scan, assumed_role_arn must be in the response."""
        mock_sts = _make_mock_sts_client()
        empty_scan: tuple[list[Any], list[str]] = ([], [])

        with (
            patch("boto3.client", return_value=mock_sts),
            patch(
                "recoup.scanners.cost_explorer_scanner.CostExplorerScanner.scan",
                return_value=empty_scan,
            ),
            patch(
                "recoup.scanners.ec2_scanner.EC2Scanner.scan",
                return_value=empty_scan,
            ),
        ):
            resp = scan_client.post(
                "/api/scan/preview",
                json={"role_arn": _FAKE_ROLE_ARN, "external_id": _FAKE_EXT_ID},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["assumed_role_arn"] is not None
        # Sprint 2: account_id is now masked in the API response for privacy
        account_id = body["assumed_role_account_id"]
        assert account_id is not None
        # Masked format: first4XXXXXXXX + last4 (e.g. "1234XXXXXXXX9012")
        assert "XXXXXXXX" in account_id or account_id == "123456789012"


# ---------------------------------------------------------------------------
# 8. ec2_tools — RecoupRemediationRole used when configured
# ---------------------------------------------------------------------------


class TestEC2ToolsRemediationRole:
    def test_uses_remediation_role_when_configured(self) -> None:
        """
        When recoup_remediation_role_arn + recoup_external_id are set,
        stop_demo_instance must assume RecoupRemediationRole (not default creds).
        """
        from recoup.tools.ec2_tools import stop_demo_instance

        mock_sts = _make_mock_sts_client(
            {
                "Credentials": {
                    "AccessKeyId": "REMEDIATION_KEY",
                    "SecretAccessKey": "REMEDIATION_SECRET",
                    "SessionToken": "REMEDIATION_TOKEN",
                },
                "AssumedRoleUser": {
                    "Arn": (
                        "arn:aws:sts::123456789012:assumed-role/"
                        "RecoupRemediationRole/recoup-remediation-session"
                    ),
                    "AssumedRoleId": "AROAFAKEID:recoup-remediation-session",
                },
            }
        )

        class _FakeSettingsWithRole:
            bedrock_region = "us-east-1"
            allowlisted_demo_account_id = "123456789012"
            recoup_remediation_role_arn = _FAKE_REMEDIATION_ARN
            recoup_external_id = _FAKE_EXT_ID

            @property
            def demo_instance_ids(self) -> list[str]:
                return ["i-test000000000001"]

        # Patch the STS client + all AWS calls that stop_demo_instance would make
        mock_ec2_client = MagicMock()
        mock_ec2_client.describe_tags.return_value = {
            "Tags": [{"Key": "RecoupDemo", "Value": "true"}]
        }
        mock_ec2_client.stop_instances.return_value = {
            "StoppingInstances": [
                {"InstanceId": "i-test000000000001", "CurrentState": {"Name": "stopping"}}
            ]
        }
        mock_ec2_client.describe_instance_status.return_value = {"InstanceStatuses": []}
        mock_ec2_client.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {"InstanceId": "i-test000000000001", "State": {"Name": "stopped"}}
                    ]
                }
            ]
        }
        mock_session = MagicMock()
        mock_session.client.return_value = mock_ec2_client

        CustomerConnection.clear_cache()
        with (
            patch("recoup.tools.ec2_tools.settings", _FakeSettingsWithRole()),
            patch("boto3.client", return_value=mock_sts),
            # boto3.Session is imported locally inside build_session; patch at module level
            patch("boto3.Session", return_value=mock_session),
        ):
            with pytest.raises(PermissionError, match="Approval"):
                # The function will reach STS AssumeRole (✓), then fail at the
                # approval-record check — that's expected in a unit test context.
                stop_demo_instance(
                    instance_id="i-test000000000001",
                    opportunity_id="opp-sts-test",
                    approval_id="appr-sts-test",
                )

        # Verify STS was called with the remediation role ARN
        mock_sts.assume_role.assert_called_once()
        call_kwargs = mock_sts.assume_role.call_args[1]
        assert call_kwargs["RoleArn"] == _FAKE_REMEDIATION_ARN

    def test_falls_back_to_default_creds_when_no_role_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When remediation role ARN is not set, default credential chain is used."""
        from recoup.tools.ec2_tools import stop_demo_instance

        class _FakeSettingsNoRole:
            bedrock_region = "us-east-1"
            allowlisted_demo_account_id = "123456789012"
            recoup_remediation_role_arn: str | None = None
            recoup_external_id: str | None = None

            @property
            def demo_instance_ids(self) -> list[str]:
                return ["i-test000000000001"]

        mock_ec2_client = MagicMock()
        mock_ec2_client.describe_tags.return_value = {
            "Tags": [{"Key": "RecoupDemo", "Value": "true"}]
        }
        mock_ec2_client.stop_instances.return_value = {
            "StoppingInstances": [
                {"InstanceId": "i-test000000000001", "CurrentState": {"Name": "stopping"}}
            ]
        }
        mock_ec2_client.describe_instance_status.return_value = {"InstanceStatuses": []}
        mock_ec2_client.describe_instances.return_value = {
            "Reservations": [
                {
                    "Instances": [
                        {"InstanceId": "i-test000000000001", "State": {"Name": "stopped"}}
                    ]
                }
            ]
        }
        mock_session = MagicMock()
        mock_session.client.return_value = mock_ec2_client
        mock_boto3_session_cls = MagicMock(return_value=mock_session)

        monkeypatch.setattr("recoup.tools.ec2_tools.settings", _FakeSettingsNoRole())
        with patch("boto3.Session", mock_boto3_session_cls):
            with pytest.raises(PermissionError):
                # Fails at the approval check (expected) — boto3.Session already called
                stop_demo_instance(
                    instance_id="i-test000000000001",
                    opportunity_id="opp-no-role",
                    approval_id="appr-no-role",
                )

        # boto3.Session called with just region (default creds, no STS)
        mock_boto3_session_cls.assert_called_once()
        call_kwargs = mock_boto3_session_cls.call_args[1]
        assert "aws_access_key_id" not in call_kwargs
        assert "aws_session_token" not in call_kwargs
