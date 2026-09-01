"""
AWS-facing tool stubs.

Each tool:
  - Has a typed signature and docstring (used by strands for schema generation)
  - Validates inputs before making any AWS call
  - Returns structured dicts (JSON-serialisable)
  - Is decorated with @tool so strands.Agent can call it directly

Phase 1: All tools return deterministic stub responses. Phase 2 replaces
the stub bodies with real boto3 calls wrapped by the AgentCore Gateway.
"""

from __future__ import annotations

from datetime import datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
from typing import Any

from strands import tool


# ---------------------------------------------------------------------------
# CloudWatch
# ---------------------------------------------------------------------------


@tool
def get_cloudwatch_metrics(
    namespace: str,
    metric_name: str,
    dimensions: list[dict[str, str]],
    start_time: str,
    end_time: str,
    period_seconds: int = 300,
    stat: str = "Sum",
) -> dict[str, Any]:
    """
    Retrieve CloudWatch metric datapoints for an AWS resource.

    Returns metric datapoints as a list of {timestamp, value} dicts.
    Allowed nodes: incident_correlation, evidence_collector.

    Args:
        namespace: CloudWatch metric namespace (e.g. 'AWS/ApiGateway').
        metric_name: Name of the metric (e.g. '5XXError').
        dimensions: List of {Name, Value} dimension filters.
        start_time: ISO-8601 start time.
        end_time: ISO-8601 end time.
        period_seconds: Aggregation period in seconds (default 300 = 5 min).
        stat: Aggregation statistic (Sum, Average, SampleCount).

    Returns:
        {'datapoints': [{timestamp, value, unit}], 'label': metric_name}
    """
    # Phase 1 stub
    return {
        "datapoints": [
            {"timestamp": start_time, "value": 0.0, "unit": "Count"},
        ],
        "label": metric_name,
        "_stub": True,
    }


@tool
def query_cloudwatch_logs(
    log_group_name: str,
    query_string: str,
    start_time: str,
    end_time: str,
    limit: int = 100,
) -> dict[str, Any]:
    """
    Run a CloudWatch Logs Insights query and return matching log records.

    Raw log content is NEVER returned directly — only structured fields.
    Allowed nodes: evidence_collector.

    Args:
        log_group_name: CloudWatch Logs group name.
        query_string: Logs Insights query (e.g. 'fields @timestamp, @message | limit 10').
        start_time: ISO-8601 start time.
        end_time: ISO-8601 end time.
        limit: Maximum number of results (default 100, max 10 000).

    Returns:
        {'results': [list of field dicts], 'status': 'Complete'|'Running'|'Failed'}
    """
    return {
        "results": [],
        "status": "Complete",
        "_stub": True,
    }


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@tool
def get_health_event(
    service: str,
    region: str,
    event_arn: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> dict[str, Any]:
    """
    Retrieve AWS Health events for a service in a region.

    Allowed nodes: incident_correlation.

    Args:
        service: AWS service identifier (e.g. 'apigateway').
        region: AWS region (e.g. 'us-east-1').
        event_arn: Optional specific event ARN to fetch.
        start_time: ISO-8601 start time for event search window.
        end_time: ISO-8601 end time for event search window.

    Returns:
        {'events': [{arn, service, region, startTime, endTime, statusCode}]}
    """
    return {
        "events": [],
        "_stub": True,
    }


# ---------------------------------------------------------------------------
# Cost & Usage
# ---------------------------------------------------------------------------


@tool
def get_cost_and_usage(
    service: str,
    region: str,
    start_date: str,
    end_date: str,
    granularity: str = "MONTHLY",
) -> dict[str, Any]:
    """
    Retrieve AWS Cost and Usage data for a service and billing period.

    Allowed nodes: evidence_collector.

    Args:
        service: AWS service filter (e.g. 'Amazon API Gateway').
        region: AWS region to filter on.
        start_date: Billing period start (YYYY-MM-DD).
        end_date: Billing period end (YYYY-MM-DD, exclusive).
        granularity: MONTHLY or DAILY.

    Returns:
        {'results': [{start, end, total_usd}]}
    """
    return {
        "results": [
            {
                "start": start_date,
                "end": end_date,
                "total_usd": "18400.00",
                "_stub": True,
            }
        ],
    }


@tool
def get_cost_anomalies(
    service: str,
    start_date: str,
    end_date: str,
    min_impact_usd: float = 100.0,
) -> dict[str, Any]:
    """
    Retrieve AWS Cost Anomaly Detection anomalies for a service.

    Allowed nodes: incident_correlation.

    Args:
        service: AWS service to check (e.g. 'Amazon API Gateway').
        start_date: Search window start (YYYY-MM-DD).
        end_date: Search window end (YYYY-MM-DD).
        min_impact_usd: Minimum anomaly impact in USD to include.

    Returns:
        {'anomalies': [{id, service, region, start_date, end_date, impact_usd}]}
    """
    return {"anomalies": [], "_stub": True}


@tool
def list_cost_optimization_recommendations(
    service: str | None = None,
    region: str | None = None,
) -> dict[str, Any]:
    """
    List AWS Cost Optimization Hub recommendations.

    Allowed nodes: incident_correlation.

    Args:
        service: Optional service filter.
        region: Optional region filter.

    Returns:
        {'recommendations': [{id, service, region, estimated_savings_usd, action}]}
    """
    return {"recommendations": [], "_stub": True}


# ---------------------------------------------------------------------------
# CloudTrail
# ---------------------------------------------------------------------------


@tool
def lookup_cloudtrail_events(
    resource_id: str,
    start_time: str,
    end_time: str,
    event_names: list[str] | None = None,
) -> dict[str, Any]:
    """
    Look up CloudTrail API activity for a specific resource.

    Sensitive field values are excluded from the response — only event names,
    timestamps, and user identity type are returned.
    Allowed nodes: incident_correlation.

    Args:
        resource_id: The AWS resource identifier to look up.
        start_time: ISO-8601 start time.
        end_time: ISO-8601 end time.
        event_names: Optional list of API call names to filter (e.g. ['DeleteRestApi']).

    Returns:
        {'events': [{event_name, event_time, user_identity_type, request_id}]}
    """
    return {"events": [], "_stub": True}


# ---------------------------------------------------------------------------
# Support
# ---------------------------------------------------------------------------


@tool
def get_support_case_status(
    case_id: str,
) -> dict[str, Any]:
    """
    Get the current status of an AWS Support case.

    Allowed nodes: case_monitor.

    Args:
        case_id: AWS Support case identifier.

    Returns:
        {'case_id', 'status', 'subject', 'created_at', 'resolved_at', 'communications'}
    """
    return {
        "case_id": case_id,
        "status": "pending-customer-action",
        "subject": "SLA Credit Request (stub)",
        "created_at": _utcnow().isoformat(),
        "resolved_at": None,
        "communications": [],
        "_stub": True,
    }
