"""
Graph checkpoint — Sprint 3.

Persists the last completed graph node for each opportunity so the graph
can resume from the correct position after a HITL approval or process crash.

Storage: DynamoDB ``recoup-opportunities`` table with a ``last_node`` attribute,
or in-memory dict when DynamoDB is unavailable.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from ..config import settings

log: structlog.BoundLogger = structlog.get_logger(__name__)

# In-memory fallback (local / test mode)
_checkpoints: dict[str, dict[str, Any]] = {}


def save_checkpoint(opportunity_id: str, node_name: str) -> None:
    """
    Persist the last completed node for *opportunity_id*.

    Called after each graph node completes successfully.
    Fails silently — checkpoint failure never blocks graph progress.
    """
    record = {
        "opportunity_id": opportunity_id,
        "last_node": node_name,
        "checkpointed_at": datetime.now(UTC).isoformat(),
    }
    _checkpoints[opportunity_id] = record

    # Attempt to persist to DynamoDB opportunities table
    if not settings.opportunities_table:
        return

    try:
        import boto3  # noqa: PLC0415
        import botocore.config  # noqa: PLC0415

        cfg = botocore.config.Config(connect_timeout=3, read_timeout=5, retries={"max_attempts": 1})
        ddb = boto3.resource("dynamodb", region_name=settings.bedrock_region, config=cfg)
        table = ddb.Table(settings.opportunities_table)
        table.update_item(
            Key={"id": opportunity_id},
            UpdateExpression="SET last_node = :n, checkpointed_at = :t",
            ExpressionAttributeValues={
                ":n": node_name,
                ":t": record["checkpointed_at"],
            },
        )
        log.debug("checkpoint.saved", opportunity_id=opportunity_id, node=node_name)
    except Exception as exc:  # noqa: BLE001
        log.debug("checkpoint.dynamo_failed", error=str(exc))


def get_checkpoint(opportunity_id: str) -> str | None:
    """
    Return the last completed node name for *opportunity_id*, or None.

    Tries DynamoDB first; falls back to in-memory cache.
    """
    # Try DynamoDB
    if settings.opportunities_table:
        try:
            import boto3  # noqa: PLC0415
            import botocore.config  # noqa: PLC0415

            cfg = botocore.config.Config(connect_timeout=3, read_timeout=5, retries={"max_attempts": 1})
            ddb = boto3.resource("dynamodb", region_name=settings.bedrock_region, config=cfg)
            table = ddb.Table(settings.opportunities_table)
            resp = table.get_item(Key={"id": opportunity_id})
            item = resp.get("Item")
            if item and "last_node" in item:
                return str(item["last_node"])
        except Exception as exc:  # noqa: BLE001
            log.debug("checkpoint.dynamo_read_failed", error=str(exc))

    # Fall back to in-memory
    record = _checkpoints.get(opportunity_id)
    return record["last_node"] if record else None


def clear_checkpoint(opportunity_id: str) -> None:
    """Remove the checkpoint for a completed or failed opportunity."""
    _checkpoints.pop(opportunity_id, None)
