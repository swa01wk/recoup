"""CloudWatch custom metrics — no-op when live AWS disabled."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from recoup.config import settings
from recoup.observability.cloudwatch_metrics import publish_graph_node, publish_tool_call


def _disable_live_aws(monkeypatch) -> None:
    monkeypatch.setattr(settings, "evidence_bucket", "", raising=False)
    monkeypatch.setattr(settings, "recoup_sns_topic_arn", "", raising=False)
    monkeypatch.setattr(settings, "recovery_events_queue_url", "", raising=False)
    monkeypatch.setattr(settings, "approvals_table", "", raising=False)
    assert settings.live_aws_enabled is False


def test_metrics_noop_when_live_aws_disabled(monkeypatch) -> None:
    _disable_live_aws(monkeypatch)
    with patch("boto3.client") as mock_client:
        publish_graph_node("normalize_event", 12)
        publish_tool_call("get_cloudwatch_metrics", "incident_correlation", 5)
        mock_client.assert_not_called()


def test_publish_graph_node_when_live(monkeypatch) -> None:
    monkeypatch.setattr(settings, "evidence_bucket", "recoup-evidence-demo", raising=False)
    monkeypatch.setattr(settings, "bedrock_region", "us-east-1", raising=False)
    assert settings.live_aws_enabled is True
    cw = MagicMock()
    with patch("boto3.client", return_value=cw):
        publish_graph_node("risk_policy_gate", 42)
    assert cw.put_metric_data.call_count == 2
    namespaces = {c.kwargs["Namespace"] for c in cw.put_metric_data.call_args_list}
    assert namespaces == {"Recoup/Graph"}
