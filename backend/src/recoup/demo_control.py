"""Global demo epoch + reset lock (multi-instance cache coherence)."""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any

import structlog

from .config import settings
from .demo_state import clear_all_memory

log = structlog.get_logger(__name__)

GLOBAL_ID = "global"
_local_global_epoch = 0
_local_lock = threading.Lock()
_memory_global: dict[str, Any] = {
    "demo_epoch": 0,
    "reset_lock_token": "",
    "reset_lock_until": 0,
}

_LOCK_TTL_SEC = 60


def _table() -> Any | None:
    if not settings.demo_control_table:
        return None
    try:
        import boto3  # noqa: PLC0415

        ddb = boto3.resource("dynamodb", region_name=settings.bedrock_region)
        return ddb.Table(settings.demo_control_table)
    except Exception as exc:  # noqa: BLE001
        log.warning("demo_control.dynamo_unavailable", error=str(exc))
        return None


def _read_global_record() -> dict[str, Any]:
    table = _table()
    if table is None:
        with _local_lock:
            return dict(_memory_global)
    try:
        resp = table.get_item(Key={"id": GLOBAL_ID})
        item = resp.get("Item") or {}
        return {
            "demo_epoch": int(item.get("demo_epoch", 0)),
            "reset_lock_token": str(item.get("reset_lock_token", "")),
            "reset_lock_until": int(item.get("reset_lock_until", 0)),
        }
    except Exception as exc:  # noqa: BLE001
        log.warning("demo_control.read_global_failed", error=str(exc))
        with _local_lock:
            return dict(_memory_global)


def get_global_epoch() -> int:
    return int(_read_global_record().get("demo_epoch", 0))


def sync_global_epoch() -> bool:
    """If remote global epoch advanced, flush all in-memory session caches on this instance."""
    global _local_global_epoch
    remote = get_global_epoch()
    if remote <= _local_global_epoch:
        return False
    _local_global_epoch = remote
    clear_all_memory(clear_scan_cache=True)
    log.info("demo_control.global_epoch_sync", demo_epoch=remote)
    return True


def _write_global(**fields: Any) -> None:
    table = _table()
    if table is None:
        with _local_lock:
            _memory_global.update(fields)
        return
    item: dict[str, Any] = {"id": GLOBAL_ID}
    item.update(fields)
    table.put_item(Item=item)


def acquire_global_reset_lock() -> str | None:
    """Return lock token if acquired, None if another reset holds the lock."""
    now = int(time.time())
    record = _read_global_record()
    lock_until = int(record.get("reset_lock_until", 0))
    if lock_until > now and record.get("reset_lock_token"):
        return None
    token = str(uuid.uuid4())
    new_until = now + _LOCK_TTL_SEC
    table = _table()
    if table is None:
        with _local_lock:
            _memory_global["reset_lock_token"] = token
            _memory_global["reset_lock_until"] = new_until
        return token
    try:
        table.update_item(
            Key={"id": GLOBAL_ID},
            UpdateExpression=(
                "SET reset_lock_token = :t, reset_lock_until = :u, demo_epoch = "
                "if_not_exists(demo_epoch, :zero)"
            ),
            ConditionExpression=(
                "attribute_not_exists(reset_lock_until) OR reset_lock_until <= :now"
            ),
            ExpressionAttributeValues={
                ":t": token,
                ":u": new_until,
                ":now": now,
                ":zero": 0,
            },
        )
        return token
    except Exception:  # noqa: BLE001
        return None


def release_global_reset_lock(token: str) -> None:
    record = _read_global_record()
    if record.get("reset_lock_token") != token:
        return
    _write_global(reset_lock_token="", reset_lock_until=0)


def bump_global_epoch() -> int:
    global _local_global_epoch
    table = _table()
    if table is None:
        with _local_lock:
            _memory_global["demo_epoch"] = int(_memory_global.get("demo_epoch", 0)) + 1
            new_epoch = int(_memory_global["demo_epoch"])
        _local_global_epoch = new_epoch
        return new_epoch
    try:
        resp = table.update_item(
            Key={"id": GLOBAL_ID},
            UpdateExpression="ADD demo_epoch :one",
            ExpressionAttributeValues={":one": 1},
            ReturnValues="UPDATED_NEW",
        )
        new_epoch = int(resp["Attributes"]["demo_epoch"])
        _local_global_epoch = new_epoch
        return new_epoch
    except Exception as exc:  # noqa: BLE001
        log.warning("demo_control.bump_global_failed", error=str(exc))
        with _local_lock:
            _memory_global["demo_epoch"] = int(_memory_global.get("demo_epoch", 0)) + 1
            new_epoch = int(_memory_global["demo_epoch"])
        _local_global_epoch = new_epoch
        return new_epoch
