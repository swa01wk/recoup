"""
Approval store — DynamoDB-backed persistence with in-memory fallback.

Design:
- Primary store: DynamoDB table ``recoup-approvals`` (configured via settings).
- Fallback: in-memory dict, used when AWS credentials are absent or boto3
  raises an error. The fallback is also used by the API server in replay mode
  so the full approve/decline flow is testable without AWS.
- Sprint 4: In production (RECOUP_ENV=production), in-memory fallback is
  DISABLED. DynamoDB failures raise immediately so nothing is silently lost.
- All records are serialised/deserialised via ApprovalRecord.model_dump().
- DynamoDB TTL is set on ``expires_at_epoch`` (Unix timestamp) so DynamoDB
  automatically purges expired records — no cron job needed.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import structlog

from ..models.approval import ApprovalRecord, ApprovalState

log: structlog.BoundLogger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# In-memory fallback store (shared within a process; reset between test runs)
# ---------------------------------------------------------------------------

_IN_MEMORY: dict[str, dict[str, Any]] = {}


def _clear_in_memory() -> None:
    """Reset in-memory store — for use in tests only."""
    _IN_MEMORY.clear()


# ---------------------------------------------------------------------------
# DynamoDB helpers
# ---------------------------------------------------------------------------


def _to_dynamo_item(record: ApprovalRecord) -> dict[str, Any]:
    """Serialise an ApprovalRecord to a DynamoDB-compatible dict."""
    item = record.model_dump(mode="json")
    # DynamoDB TTL attribute (must be a Unix epoch integer)
    item["expires_at_epoch"] = int(record.expires_at.timestamp())
    # Decimal fields must be Decimal for boto3
    item["amount"] = str(record.amount)
    return item


def _from_dynamo_item(item: dict[str, Any]) -> ApprovalRecord:
    """Deserialise a DynamoDB item back to an ApprovalRecord."""
    item = dict(item)
    item.pop("expires_at_epoch", None)
    # boto3 returns Decimal for numbers; convert back
    if isinstance(item.get("amount"), Decimal):
        item["amount"] = item["amount"]
    return ApprovalRecord.model_validate(item)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _is_production() -> bool:
    """Return True when running in production mode."""
    from ..config import settings  # noqa: PLC0415
    return settings.recoup_env == "production"


def save_approval(record: ApprovalRecord) -> None:
    """
    Persist an ApprovalRecord to DynamoDB or in-memory fallback.

    Always attempts DynamoDB first.
    - In production: raises on DynamoDB failure (no silent data loss).
    - Otherwise: falls back to in-memory dict.
    """
    if not _dynamo_available():
        if _is_production():
            raise RuntimeError(
                "approval_store: boto3 not available in production — "
                "cannot persist approval record"
            )
        _IN_MEMORY[record.approval_id] = record.model_dump(mode="json")
        log.debug("approval_store.saved_inmemory", approval_id=record.approval_id)
        return

    try:
        from ..config import settings  # noqa: PLC0415

        ddb = _ddb_resource()
        table = ddb.Table(settings.approvals_table)
        table.put_item(Item=_to_dynamo_item(record))
        log.info("approval_store.saved_dynamo", approval_id=record.approval_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("approval_store.dynamo_write_failed", error=str(exc))
        if _is_production():
            # Re-raise so the caller gets a 500 rather than silently dropping the record
            raise RuntimeError(
                f"approval_store: DynamoDB write failed in production: {exc}"
            ) from exc
        # Non-production: fall back to in-memory to not block the run
        _IN_MEMORY[record.approval_id] = record.model_dump(mode="json")


def get_approval(approval_id: str) -> ApprovalRecord | None:
    """
    Fetch an ApprovalRecord by its approval_id.

    Returns None if not found. Tries DynamoDB first.
    - In production: raises on DynamoDB failure.
    - Otherwise: falls back to in-memory.
    """
    if not _dynamo_available():
        if _is_production():
            raise RuntimeError("approval_store: boto3 not available in production")
        raw = _IN_MEMORY.get(approval_id)
        if raw is None:
            return None
        return ApprovalRecord.model_validate(raw)

    try:
        from ..config import settings  # noqa: PLC0415

        ddb = _ddb_resource()
        table = ddb.Table(settings.approvals_table)
        response = table.get_item(Key={"approval_id": approval_id})
        item = response.get("Item")
        if item is None:
            return None
        return _from_dynamo_item(dict(item))
    except Exception as exc:  # noqa: BLE001
        log.warning("approval_store.dynamo_read_failed", error=str(exc))
        if _is_production():
            raise RuntimeError(
                f"approval_store: DynamoDB read failed in production: {exc}"
            ) from exc
        raw = _IN_MEMORY.get(approval_id)
        return ApprovalRecord.model_validate(raw) if raw else None


def _pending_only(records: list[ApprovalRecord]) -> list[ApprovalRecord]:
    """
    Return actionable PENDING records, auto-expiring stale ones.

    Also deduplicates by resource_id: when multiple PENDING approvals share the
    same resource_id (can happen after server restarts), only the most-recently
    created one is kept; all older ones are revoked immediately.
    """
    actionable: list[ApprovalRecord] = []
    for record in records:
        if record.state != ApprovalState.PENDING:
            continue
        if record.is_expired:
            update_approval_state(record.approval_id, ApprovalState.EXPIRED)
            continue
        actionable.append(record)

    # Deduplicate by resource_id (keep newest, revoke older duplicates)
    if not any(r.resource_id for r in actionable):
        return actionable  # No resource_ids set — nothing to deduplicate

    seen_resource: dict[str, ApprovalRecord] = {}
    deduped: list[ApprovalRecord] = []
    for record in sorted(actionable, key=lambda r: r.timestamp, reverse=True):
        if not record.resource_id:
            deduped.append(record)
            continue
        if record.resource_id not in seen_resource:
            seen_resource[record.resource_id] = record
            deduped.append(record)
        else:
            # Older duplicate — revoke it
            update_approval_state(
                record.approval_id,
                ApprovalState.REVOKED,
                decided_by="system",
                notes="Duplicate: superseded by newer approval for same resource",
            )
            log.info(
                "approval_store.dedup_revoked",
                approval_id=record.approval_id,
                resource_id=record.resource_id,
            )
    return deduped


def list_pending_approvals() -> list[ApprovalRecord]:
    """Return all non-expired PENDING approval records across all opportunities."""
    if not _dynamo_available():
        if _is_production():
            raise RuntimeError("approval_store: boto3 not available in production")
        result = []
        for raw in _IN_MEMORY.values():
            if raw.get("state") == ApprovalState.PENDING:
                result.append(ApprovalRecord.model_validate(raw))
        return _pending_only(result)

    try:
        from boto3.dynamodb.conditions import Attr  # noqa: PLC0415

        from ..config import settings  # noqa: PLC0415

        ddb = _ddb_resource()
        table = ddb.Table(settings.approvals_table)
        response = table.scan(FilterExpression=Attr("state").eq(ApprovalState.PENDING))
        records = [_from_dynamo_item(dict(i)) for i in response.get("Items", [])]
        return _pending_only(records)
    except Exception as exc:  # noqa: BLE001
        log.warning("approval_store.dynamo_scan_failed", error=str(exc))
        if _is_production():
            raise RuntimeError(
                f"approval_store: DynamoDB scan failed in production: {exc}"
            ) from exc
        # Non-production: fall back to in-memory
        result = []
        for raw in _IN_MEMORY.values():
            if raw.get("state") == ApprovalState.PENDING:
                result.append(ApprovalRecord.model_validate(raw))
        return _pending_only(result)


def get_pending_for_opportunity(opportunity_id: str) -> ApprovalRecord | None:
    """Return the non-expired PENDING ApprovalRecord for an opportunity, or None."""
    if not _dynamo_available():
        if _is_production():
            raise RuntimeError("approval_store: boto3 not available in production")
        for raw in _IN_MEMORY.values():
            if (
                raw.get("opportunity_id") == opportunity_id
                and raw.get("state") == ApprovalState.PENDING
            ):
                record = ApprovalRecord.model_validate(raw)
                if record.is_expired:
                    update_approval_state(record.approval_id, ApprovalState.EXPIRED)
                    return None
                return record
        return None

    try:
        from boto3.dynamodb.conditions import Attr  # noqa: PLC0415

        from ..config import settings  # noqa: PLC0415

        ddb = _ddb_resource()
        table = ddb.Table(settings.approvals_table)
        response = table.scan(
            FilterExpression=(
                Attr("opportunity_id").eq(opportunity_id)
                & Attr("state").eq(ApprovalState.PENDING)
            )
        )
        items = response.get("Items", [])
        if not items:
            return None
        record = _from_dynamo_item(dict(items[0]))
        if record.is_expired:
            update_approval_state(record.approval_id, ApprovalState.EXPIRED)
            return None
        return record
    except Exception as exc:  # noqa: BLE001
        log.warning("approval_store.dynamo_scan_failed", error=str(exc))
        if _is_production():
            raise RuntimeError(
                f"approval_store: DynamoDB scan failed in production: {exc}"
            ) from exc
        # Non-production: fall back to in-memory
        for raw in _IN_MEMORY.values():
            if (
                raw.get("opportunity_id") == opportunity_id
                and raw.get("state") == ApprovalState.PENDING
            ):
                return ApprovalRecord.model_validate(raw)
        return None


def update_approval_state(
    approval_id: str,
    new_state: ApprovalState,
    decided_by: str = "system",
    notes: str = "",
) -> ApprovalRecord | None:
    """
    Transition an ApprovalRecord to a new state (APPROVED, DECLINED, REVOKED).

    Returns the updated record, or None if not found.
    """
    record = get_approval(approval_id)
    if record is None:
        return None

    # Check expiry before approving
    if new_state == ApprovalState.APPROVED and record.is_expired:
        new_state = ApprovalState.EXPIRED

    updated = record.model_copy(update={"state": new_state})
    save_approval(updated)
    log.info(
        "approval_store.state_updated",
        approval_id=approval_id,
        old_state=str(record.state),
        new_state=str(new_state),
        decided_by=decided_by,
    )
    return updated


# ---------------------------------------------------------------------------
# Resource-level deduplication helpers
# ---------------------------------------------------------------------------


def revoke_pending_by_resource_id(
    resource_id: str,
    exclude_opportunity_id: str = "",
    notes: str = "Superseded",
) -> int:
    """
    Revoke all PENDING approvals whose resource_id matches, except the one
    belonging to *exclude_opportunity_id*.  Returns the number revoked.

    This is called when a finding is re-promoted after a server restart, so
    that stale approval cards from previous runs are cleaned up.
    """
    if not resource_id:
        return 0

    all_pending = _list_all_pending_raw()
    revoked = 0
    for record in all_pending:
        if record.resource_id != resource_id:
            continue
        if record.opportunity_id == exclude_opportunity_id:
            continue
        update_approval_state(
            record.approval_id,
            ApprovalState.REVOKED,
            decided_by="system",
            notes=notes,
        )
        revoked += 1
    return revoked


def purge_stale_approvals(live_opportunity_ids: set[str]) -> int:
    """
    Revoke all PENDING approvals whose opportunity_id is NOT in
    *live_opportunity_ids*.  Used by the purge-stale admin endpoint to
    clean up records left over from previous server runs.

    Returns the number of approvals revoked.
    """
    all_pending = _list_all_pending_raw()
    revoked = 0
    for record in all_pending:
        if record.opportunity_id not in live_opportunity_ids:
            update_approval_state(
                record.approval_id,
                ApprovalState.REVOKED,
                decided_by="system",
                notes="Stale: opportunity no longer exists in current server session",
            )
            revoked += 1
    return revoked


def _list_all_pending_raw() -> list[ApprovalRecord]:
    """Return all raw PENDING records (no expiry filtering, no dedup) for admin ops."""
    if not _dynamo_available():
        result = []
        for raw in _IN_MEMORY.values():
            if raw.get("state") == ApprovalState.PENDING:
                result.append(ApprovalRecord.model_validate(raw))
        return result

    try:
        from boto3.dynamodb.conditions import Attr  # noqa: PLC0415
        from ..config import settings  # noqa: PLC0415

        ddb = _ddb_resource()
        table = ddb.Table(settings.approvals_table)
        response = table.scan(FilterExpression=Attr("state").eq(ApprovalState.PENDING))
        return [_from_dynamo_item(dict(i)) for i in response.get("Items", [])]
    except Exception as exc:  # noqa: BLE001
        log.warning("approval_store.raw_scan_failed", error=str(exc))
        result = []
        for raw in _IN_MEMORY.values():
            if raw.get("state") == ApprovalState.PENDING:
                result.append(ApprovalRecord.model_validate(raw))
        return result


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _dynamo_available() -> bool:
    """Return True if boto3 is importable AND the DynamoDB table name is configured.

    Skipping the check when no table is configured avoids connection-timeout
    delays in local/demo/test environments where DynamoDB is never used.
    """
    try:
        import boto3  # noqa: F401
        from ..config import settings  # noqa: PLC0415
        return bool(settings.approvals_table)
    except ImportError:
        return False


def _ddb_resource() -> Any:
    """
    Return a DynamoDB resource with a short connect timeout so tests and
    offline environments fail fast instead of hanging for 60+ seconds.
    """
    import boto3  # noqa: PLC0415
    import botocore.config

    cfg = botocore.config.Config(
        connect_timeout=3,
        read_timeout=5,
        retries={"max_attempts": 1},
    )
    return boto3.resource("dynamodb", region_name="us-east-1", config=cfg)


def clear_all_approvals() -> int:
    """
    Delete every approval record — in-memory and DynamoDB.

    Used by the admin demo reset so stale PENDING/APPROVED rows from prior
    sessions don't bleed through.  Returns the number of items deleted.
    """
    import structlog as _structlog  # noqa: PLC0415
    _log = _structlog.get_logger(__name__)

    deleted = 0
    deleted += len(_IN_MEMORY)
    _IN_MEMORY.clear()

    if _dynamo_available():
        try:
            from ..config import settings as _settings  # noqa: PLC0415
            ddb = _ddb_resource()
            table = ddb.Table(_settings.approvals_table)

            resp = table.scan(ProjectionExpression="approval_id")
            items = resp.get("Items", [])
            while "LastEvaluatedKey" in resp:
                resp = table.scan(
                    ProjectionExpression="approval_id",
                    ExclusiveStartKey=resp["LastEvaluatedKey"],
                )
                items.extend(resp.get("Items", []))

            with table.batch_writer() as batch:
                for item in items:
                    batch.delete_item(Key={"approval_id": item["approval_id"]})
            deleted += len(items)
            _log.info("approvals.clear_all", deleted=deleted)
        except Exception as exc:  # noqa: BLE001
            _log.warning("approvals.clear_all_failed", error=str(exc))

    return deleted
