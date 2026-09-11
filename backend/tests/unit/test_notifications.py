"""Unit tests for SNS/SQS notification helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from recoup.notifications import format_recovery_report_email, notify_sns


class TestFormatRecoveryReportEmail:
    def test_subject_includes_service_and_savings(self) -> None:
        subject, message = format_recovery_report_email(
            opportunity_id="recovery-abc",
            service="EC2",
            region="us-east-1",
            resource_id="i-123",
            savings_per_month="30.37",
            recommendation="Stop idle instance",
            severity="high",
            action="stop_demo_instance",
        )
        assert "EC2" in subject
        assert "30.37" in subject
        assert "recovery-abc" in message
        assert "i-123" in message
        assert "Stop idle instance" in message
        assert "ec2/v2/home" in message


class TestNotifySns:
    def test_skipped_when_live_aws_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from recoup.config import settings

        monkeypatch.setattr(settings, "evidence_bucket", "", raising=False)
        monkeypatch.setattr(settings, "recoup_sns_topic_arn", "", raising=False)
        monkeypatch.setattr(settings, "recovery_events_queue_url", "", raising=False)
        monkeypatch.setattr(settings, "approvals_table", "", raising=False)
        monkeypatch.setattr(settings, "recoup_sns_dry_run", False, raising=False)
        assert settings.live_aws_enabled is False

        assert notify_sns("subj", "body") is False

    def test_skipped_when_topic_arn_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from recoup.config import settings

        monkeypatch.setattr(settings, "recoup_sns_topic_arn", "", raising=False)
        monkeypatch.setattr(settings, "recoup_sns_dry_run", False, raising=False)

        assert notify_sns("subj", "body") is False

    def test_dry_run_without_topic_returns_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from recoup.config import settings

        monkeypatch.setattr(settings, "recoup_sns_topic_arn", "", raising=False)
        monkeypatch.setattr(settings, "recoup_sns_dry_run", True, raising=False)

        assert notify_sns("subj", "body") is True

    def test_dry_run_with_topic_returns_true_without_boto3(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from recoup.config import settings

        monkeypatch.setattr(
            settings, "recoup_sns_topic_arn", "arn:aws:sns:us-east-1:1:recoup-alerts", raising=False
        )
        monkeypatch.setattr(settings, "recoup_sns_dry_run", True, raising=False)

        with patch("boto3.client") as mock_client:
            assert notify_sns("subj", "body") is True
            mock_client.assert_not_called()

    def test_publish_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from recoup.config import settings

        monkeypatch.setattr(
            settings, "recoup_sns_topic_arn", "arn:aws:sns:us-east-1:1:recoup-alerts", raising=False
        )
        monkeypatch.setattr(settings, "recoup_sns_dry_run", False, raising=False)
        monkeypatch.setattr(settings, "bedrock_region", "us-east-1", raising=False)

        mock_sns = MagicMock()
        with patch("boto3.client", return_value=mock_sns):
            assert notify_sns("Recovery report", "Hello") is True
        mock_sns.publish.assert_called_once_with(
            TopicArn="arn:aws:sns:us-east-1:1:recoup-alerts",
            Subject="Recovery report",
            Message="Hello",
        )

    def test_publish_failure_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from recoup.config import settings

        monkeypatch.setattr(
            settings, "recoup_sns_topic_arn", "arn:aws:sns:us-east-1:1:recoup-alerts", raising=False
        )
        monkeypatch.setattr(settings, "recoup_sns_dry_run", False, raising=False)

        mock_sns = MagicMock()
        mock_sns.publish.side_effect = RuntimeError("access denied")
        with patch("boto3.client", return_value=mock_sns):
            assert notify_sns("subj", "body") is False


class TestHitlFlowSnsOnApprove:
    def test_approve_calls_notify_sns(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from decimal import Decimal

        from recoup.approval.flow import HITLFlow

        published: list[tuple[str, str]] = []

        def _capture(subject: str, message: str) -> bool:
            published.append((subject, message))
            return True

        monkeypatch.setattr(
            "recoup.notifications.notify_sns",
            _capture,
            raising=False,
        )

        flow = HITLFlow(opportunity_id="opp-sns-001")
        record = flow.create_request(
            principal="system",
            action="submit_support_case",
            amount=Decimal("0.35"),
            claim_hash="sha256:testhash",
            state_version=1,
        )
        flow.approve(
            approval_id=record.approval_id,
            principal="operator@example.com",
            claim_hash="sha256:testhash",
            amount=Decimal("0.35"),
            state_version=1,
        )

        assert flow.last_sns_notification_sent is True
        assert len(published) == 1
        assert "Recovery Report" in published[0][0]
