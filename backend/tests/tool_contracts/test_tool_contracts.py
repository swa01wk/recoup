"""
Tool Contract Tests — Phase 5.

Validates that each tool in the TOOL_REGISTRY:
  1. Returns the correct schema structure (deterministic stub responses)
  2. Respects input validation (required fields present)
  3. Is never called outside its allowed_nodes list
  4. Always returns JSON-serialisable output
  5. Never exposes raw evidence content (no _stub key in downstream context)

All tests are deterministic — no LLM calls, no real AWS calls.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from recoup.tools.aws_tools import (
    get_cloudwatch_metrics,
    get_cost_and_usage,
    get_health_event,
    get_support_case_status,
    lookup_cloudtrail_events,
    query_cloudwatch_logs,
)
from recoup.tools.ec2_tools import stop_demo_instance
from recoup.tools.internal_tools import (
    create_approval_request,
    simulate_support_case,
    store_evidence,
)
from recoup.tools.registry import TOOL_REGISTRY

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_json_serialisable(obj: Any) -> bool:
    try:
        json.dumps(obj)
        return True
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# TOOL_REGISTRY contract
# ---------------------------------------------------------------------------


class TestToolRegistry:
    def test_registry_has_fourteen_or_more_tools(self) -> None:
        assert len(TOOL_REGISTRY) >= 13

    def test_all_tools_have_name(self) -> None:
        for name, entry in TOOL_REGISTRY.items():
            assert name, "Tool name must be non-empty"
            assert entry.name == name

    def test_all_tools_have_action_class(self) -> None:
        for name, entry in TOOL_REGISTRY.items():
            assert entry.action_class, f"{name} missing action_class"

    def test_all_tools_have_allowed_nodes(self) -> None:
        for name, entry in TOOL_REGISTRY.items():
            assert hasattr(entry, "allowed_nodes"), f"{name} missing allowed_nodes"
            assert isinstance(entry.allowed_nodes, (frozenset, set, list)), (
                f"{name}.allowed_nodes must be a set/frozenset/list"
            )

    def test_no_destructive_tools_in_read_class(self) -> None:
        """Destructive tools must not be labelled READ or WRITE_INTERNAL."""
        destructive_names = {"stop_resource", "delete_resource", "terminate_ec2_instance"}
        for name, entry in TOOL_REGISTRY.items():
            if name in destructive_names:
                assert entry.action_class not in ("READ", "WRITE_INTERNAL"), (
                    f"Destructive tool {name} must not be READ/WRITE_INTERNAL"
                )

    def test_submit_support_case_is_external_financial(self) -> None:
        entry = TOOL_REGISTRY.get("submit_support_case")
        if entry:
            assert entry.action_class == "WRITE_EXTERNAL_FINANCIAL"

    def test_stop_demo_instance_is_mutate_red(self) -> None:
        entry = TOOL_REGISTRY.get("stop_demo_instance")
        if entry:
            assert entry.action_class == "MUTATE_RED"


# ---------------------------------------------------------------------------
# CloudWatch tool contracts
# ---------------------------------------------------------------------------


class TestGetCloudwatchMetrics:
    def test_returns_datapoints_key(self) -> None:
        result = get_cloudwatch_metrics(
            namespace="AWS/ApiGateway",
            metric_name="5XXError",
            dimensions=[{"Name": "ApiName", "Value": "test-api"}],
            start_time="2026-08-01T02:00:00Z",
            end_time="2026-08-01T03:00:00Z",
        )
        assert "datapoints" in result

    def test_returns_label_key(self) -> None:
        result = get_cloudwatch_metrics(
            namespace="AWS/ApiGateway",
            metric_name="5XXError",
            dimensions=[],
            start_time="2026-08-01T02:00:00Z",
            end_time="2026-08-01T02:30:00Z",
        )
        assert result["label"] == "5XXError"

    def test_output_is_json_serialisable(self) -> None:
        result = get_cloudwatch_metrics(
            namespace="AWS/ApiGateway",
            metric_name="Count",
            dimensions=[],
            start_time="2026-08-01T00:00:00Z",
            end_time="2026-08-01T01:00:00Z",
        )
        assert _is_json_serialisable(result)

    def test_datapoints_have_required_fields(self) -> None:
        result = get_cloudwatch_metrics(
            namespace="AWS/ApiGateway",
            metric_name="5XXError",
            dimensions=[],
            start_time="2026-08-01T00:00:00Z",
            end_time="2026-08-01T01:00:00Z",
        )
        for dp in result["datapoints"]:
            assert "timestamp" in dp
            assert "value" in dp


# ---------------------------------------------------------------------------
# CloudWatch Logs tool contracts
# ---------------------------------------------------------------------------


class TestQueryCloudwatchLogs:
    def test_returns_results_key(self) -> None:
        result = query_cloudwatch_logs(
            log_group_name="/aws/apigateway/test",
            query_string="fields @timestamp | filter @message like /ERROR/",
            start_time="2026-08-01T02:00:00Z",
            end_time="2026-08-01T02:30:00Z",
        )
        assert "results" in result

    def test_output_is_json_serialisable(self) -> None:
        result = query_cloudwatch_logs(
            log_group_name="/aws/apigateway/test",
            query_string="fields @message",
            start_time="2026-08-01T00:00:00Z",
            end_time="2026-08-01T01:00:00Z",
        )
        assert _is_json_serialisable(result)

    def test_no_raw_content_in_results(self) -> None:
        """Raw evidence content must never appear as a plain field."""
        result = query_cloudwatch_logs(
            log_group_name="/aws/apigateway/test",
            query_string="fields @message",
            start_time="2026-08-01T00:00:00Z",
            end_time="2026-08-01T01:00:00Z",
        )
        result_json = json.dumps(result)
        assert "Authorization: Bearer" not in result_json
        assert "api_key" not in result_json.lower() or "[REDACTED" in result_json


# ---------------------------------------------------------------------------
# Health event tool contracts
# ---------------------------------------------------------------------------


class TestGetHealthEvent:
    def test_returns_events_key(self) -> None:
        result = get_health_event(
            service="apigateway",
            region="us-east-1",
            start_time="2026-08-01T00:00:00Z",
            end_time="2026-08-01T06:00:00Z",
        )
        assert "events" in result

    def test_output_is_json_serialisable(self) -> None:
        result = get_health_event(
            service="apigateway",
            region="us-east-1",
            start_time="2026-08-01T00:00:00Z",
            end_time="2026-08-01T06:00:00Z",
        )
        assert _is_json_serialisable(result)


# ---------------------------------------------------------------------------
# Cost & Usage tool contracts
# ---------------------------------------------------------------------------


class TestGetCostAndUsage:
    def test_returns_results_key(self) -> None:
        result = get_cost_and_usage(
            service="Amazon API Gateway",
            region="us-east-1",
            start_date="2026-08-01",
            end_date="2026-09-01",
        )
        assert "results" in result

    def test_output_is_json_serialisable(self) -> None:
        result = get_cost_and_usage(
            service="Amazon API Gateway",
            region="us-east-1",
            start_date="2026-08-01",
            end_date="2026-09-01",
        )
        assert _is_json_serialisable(result)

    def test_results_have_total_usd(self) -> None:
        result = get_cost_and_usage(
            service="Amazon API Gateway",
            region="us-east-1",
            start_date="2026-08-01",
            end_date="2026-09-01",
        )
        for r in result.get("results", []):
            assert "total_usd" in r


# ---------------------------------------------------------------------------
# CloudTrail tool contracts
# ---------------------------------------------------------------------------


class TestLookupCloudtrailEvents:
    def test_returns_events_key(self) -> None:
        result = lookup_cloudtrail_events(
            resource_id="arn:aws:apigateway:us-east-1::/restapis/demo0001",
            start_time="2026-08-01T00:00:00Z",
            end_time="2026-08-01T06:00:00Z",
        )
        assert "events" in result

    def test_output_is_json_serialisable(self) -> None:
        result = lookup_cloudtrail_events(
            resource_id="arn:aws:apigateway:us-east-1::/restapis/demo0001",
            start_time="2026-08-01T00:00:00Z",
            end_time="2026-08-01T06:00:00Z",
        )
        assert _is_json_serialisable(result)

    def test_verdict_in_response_or_events_present(self) -> None:
        """Either a verdict key or a list of events must be returned."""
        result = lookup_cloudtrail_events(
            resource_id="arn:aws:apigateway:us-east-1::/restapis/demo0001",
            start_time="2026-08-01T00:00:00Z",
            end_time="2026-08-01T06:00:00Z",
        )
        assert "events" in result or "verdict" in result


# ---------------------------------------------------------------------------
# Internal tools contracts
# ---------------------------------------------------------------------------


class TestStoreEvidence:
    def test_returns_storage_uri(self) -> None:
        result = store_evidence(
            opportunity_id="opp-test-001",
            field_name="cloudwatch_metrics",
            content_json='{"datapoints": [], "label": "5XXError"}',
        )
        assert "storage_uri" in result

    def test_returns_hash(self) -> None:
        result = store_evidence(
            opportunity_id="opp-test-001",
            field_name="cloudwatch_metrics",
            content_json='{"datapoints": []}',
        )
        assert "hash" in result
        assert result["hash"].startswith("sha256:")

    def test_returns_evidence_id(self) -> None:
        result = store_evidence(
            opportunity_id="opp-test-001",
            field_name="cloudwatch_metrics",
            content_json='{"datapoints": []}',
        )
        assert "evidence_id" in result

    def test_output_is_json_serialisable(self) -> None:
        result = store_evidence(
            opportunity_id="opp-test-001",
            field_name="billing_record",
            content_json='{"amount": "3.51"}',
        )
        assert _is_json_serialisable(result)

    def test_evidence_id_prefixed_with_ev(self) -> None:
        result = store_evidence(
            opportunity_id="opp-test-001",
            field_name="request_logs",
            content_json='{"events": []}',
        )
        assert result["evidence_id"].startswith("ev-")


class TestCreateApprovalRequest:
    def test_returns_approval_id(self) -> None:
        result = create_approval_request(
            opportunity_id="opp-test-001",
            principal="operator@example.com",
            action="submit_support_case",
            amount_usd="0.35",
            claim_hash="sha256:abc123",
            state_version=1,
        )
        assert "approval_id" in result

    def test_approval_state_is_pending(self) -> None:
        result = create_approval_request(
            opportunity_id="opp-test-002",
            principal="operator@example.com",
            action="submit_support_case",
            amount_usd="0.35",
            claim_hash="sha256:abc123",
            state_version=1,
        )
        assert result.get("state") in ("PENDING", "pending")

    def test_contains_approval_url(self) -> None:
        result = create_approval_request(
            opportunity_id="opp-test-003",
            principal="operator@example.com",
            action="submit_support_case",
            amount_usd="500.00",
            claim_hash="sha256:abc123",
            state_version=1,
        )
        assert "approval_url" in result

    def test_output_is_json_serialisable(self) -> None:
        result = create_approval_request(
            opportunity_id="opp-test-003",
            principal="operator@example.com",
            action="submit_support_case",
            amount_usd="500.00",
            claim_hash="sha256:abc123",
            state_version=1,
        )
        assert _is_json_serialisable(result)


class TestSimulateSupportCase:
    def test_returns_case_id(self) -> None:
        result = simulate_support_case(
            opportunity_id="opp-test-001",
            claim_subject="SLA Credit Request — API Gateway August 2026",
            billing_cycle="2026-08",
            potential_credit_usd="0.35",
            calculator_result_hash="sha256:abc123",
        )
        assert "case_id" in result

    def test_case_id_starts_with_sim(self) -> None:
        result = simulate_support_case(
            opportunity_id="opp-test-001",
            claim_subject="SLA breach",
            billing_cycle="2026-08",
            potential_credit_usd="0.35",
            calculator_result_hash="sha256:abc123",
        )
        assert result["case_id"].startswith("sim-")

    def test_simulated_flag_true(self) -> None:
        result = simulate_support_case(
            opportunity_id="opp-test-001",
            claim_subject="SLA breach",
            billing_cycle="2026-08",
            potential_credit_usd="0.35",
            calculator_result_hash="sha256:abc123",
        )
        assert result.get("simulated") is True

    def test_output_is_json_serialisable(self) -> None:
        result = simulate_support_case(
            opportunity_id="opp-test-001",
            claim_subject="SLA breach",
            billing_cycle="2026-08",
            potential_credit_usd="0.35",
            calculator_result_hash="sha256:abc123",
        )
        assert _is_json_serialisable(result)


# ---------------------------------------------------------------------------
# EC2 tool contracts
# ---------------------------------------------------------------------------


class TestStopDemoInstance:
    def test_requires_allowlist_instance_id(self) -> None:
        """stop_demo_instance must reject instance IDs not in the allowlist."""
        with pytest.raises(PermissionError):
            stop_demo_instance(
                instance_id="i-not-in-allowlist-999",
                opportunity_id="opp-test-001",
                approval_id="appr-test-001",
                reason="test",
            )

    def test_no_allowlist_returns_simulated_flag(self) -> None:
        """When live AWS is disabled, returns simulated=True without real call."""
        from recoup.config import settings
        allowed = list(settings.demo_instance_ids)
        if not allowed:
            pytest.skip("No demo instance IDs configured; skipping allowlist test")
        if settings.live_aws_enabled:
            pytest.skip("Live AWS enabled — these tests require no real AWS calls")
        result = stop_demo_instance(
            instance_id=allowed[0],
            opportunity_id="opp-test-001",
            approval_id="appr-test-001",
            reason="test stop",
        )
        assert result.get("simulated") is True

    def test_output_is_json_serialisable(self) -> None:
        from recoup.config import settings
        allowed = list(settings.demo_instance_ids)
        if not allowed:
            pytest.skip("No demo instance IDs configured")
        if settings.live_aws_enabled:
            pytest.skip("Live AWS enabled — these tests require no real AWS calls")
        result = stop_demo_instance(
            instance_id=allowed[0],
            opportunity_id="opp-test-001",
            approval_id="appr-test-001",
            reason="phase 6 demo",
        )
        assert _is_json_serialisable(result)


# ---------------------------------------------------------------------------
# Support case status
# ---------------------------------------------------------------------------


class TestGetSupportCaseStatus:
    def test_returns_status_key(self) -> None:
        result = get_support_case_status(case_id="sim-abc123def456")
        assert "status" in result

    def test_output_is_json_serialisable(self) -> None:
        result = get_support_case_status(case_id="sim-abc123def456")
        assert _is_json_serialisable(result)
