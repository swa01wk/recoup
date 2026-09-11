"""
Global pytest configuration.

Prevents DynamoDB, CloudWatch Logs (and other AWS services) from making live
network calls during unit tests.  All AWS operations fall back to their
in-memory stubs automatically when boto3 raises — this conftest just ensures
the raise happens immediately (< 1 ms) instead of hanging for 60+ seconds
waiting for a TCP timeout in environments without AWS access.

Tests that explicitly need live AWS behaviour should monkeypatch their own
boto3.resource / boto3.client mock or use the ``integration`` marker.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _no_live_aws(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Replace ``boto3.resource`` and ``boto3.client`` with mocks that raise
    immediately for AWS service calls, so all production code falls back to
    in-memory stubs without waiting for a TCP timeout.

    Individual tests can override this by patching at the module level
    (e.g. ``monkeypatch.setattr("boto3.resource", <custom_mock>)``).
    """
    # ── DynamoDB ──────────────────────────────────────────────────────────
    mock_ddb = MagicMock()
    mock_ddb.Table.return_value.put_item.side_effect = RuntimeError("no-dynamo-in-tests")
    mock_ddb.Table.return_value.get_item.side_effect = RuntimeError("no-dynamo-in-tests")
    mock_ddb.Table.return_value.scan.side_effect = RuntimeError("no-dynamo-in-tests")
    mock_ddb.Table.return_value.update_item.side_effect = RuntimeError("no-dynamo-in-tests")

    def _mock_resource(service: str, *args: Any, **kwargs: Any) -> Any:
        if service == "dynamodb":
            return mock_ddb
        raise RuntimeError(f"boto3.resource('{service}') blocked in unit tests")

    monkeypatch.setattr("boto3.resource", _mock_resource)

    # ── CloudWatch Logs + S3 (evidence sanitizer) ───────────────────────
    # HITLFlow._write_cw_audit calls boto3.client("logs") and catches exceptions
    # silently. The evidence sanitizer calls boto3.client("s3") to store
    # sanitized evidence — it has its own try/except for S3 errors.
    # We return failing mocks for these services to trigger the fallback paths
    # without hanging on a TCP timeout.
    def _make_failing_client() -> MagicMock:
        c = MagicMock()
        c.create_log_stream.side_effect = RuntimeError("no-aws-in-tests")
        c.put_log_events.side_effect = RuntimeError("no-aws-in-tests")
        c.put_object.side_effect = RuntimeError("no-aws-in-tests")
        c.get_object.side_effect = RuntimeError("no-aws-in-tests")
        return c

    def _mock_client(service: str, *args: Any, **kwargs: Any) -> Any:
        if service in ("logs", "cloudwatch", "s3", "sns", "sqs"):
            return _make_failing_client()
        # For other services (STS, EC2, etc.), tests must patch boto3.client
        # themselves. Raise immediately (don't hang on TCP timeout).
        raise RuntimeError(
            f"boto3.client('{service}') not mocked in unit tests — "
            "add a patch in your test or extend conftest."
        )

    monkeypatch.setattr("boto3.client", _mock_client)
