"""Best-effort CloudWatch custom metrics for graph nodes and tool calls."""

from __future__ import annotations

import structlog

log: structlog.BoundLogger = structlog.get_logger(__name__)


def _put(namespace: str, metric_name: str, value: float, unit: str, dimensions: list[dict[str, str]]) -> None:
    from ..config import settings  # noqa: PLC0415

    if not settings.live_aws_enabled:
        return
    try:
        import boto3  # noqa: PLC0415

        cw = boto3.client("cloudwatch", region_name=settings.bedrock_region)
        cw.put_metric_data(
            Namespace=namespace,
            MetricData=[
                {
                    "MetricName": metric_name,
                    "Value": value,
                    "Unit": unit,
                    "Dimensions": dimensions,
                }
            ],
        )
    except Exception as exc:  # noqa: BLE001
        log.debug("cloudwatch.metric_failed", namespace=namespace, metric=metric_name, error=str(exc))


def publish_graph_node(node_name: str, duration_ms: int) -> None:
    """Publish node completion count + duration to ``Recoup/Graph``."""
    dims = [{"Name": "Node", "Value": node_name}]
    _put("Recoup/Graph", "NodeCompleted", 1.0, "Count", dims)
    _put("Recoup/Graph", "NodeDurationMs", float(max(duration_ms, 0)), "Milliseconds", dims)


def publish_tool_call(tool_name: str, node_name: str, latency_ms: int) -> None:
    """Publish tool invocation count + latency to ``Recoup/Tools``."""
    dims = [
        {"Name": "Tool", "Value": tool_name},
        {"Name": "Node", "Value": node_name},
    ]
    _put("Recoup/Tools", "ToolInvoked", 1.0, "Count", dims)
    _put("Recoup/Tools", "ToolLatencyMs", float(max(latency_ms, 0)), "Milliseconds", dims)
