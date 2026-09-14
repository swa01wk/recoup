"""Guest demo sessions — token issue, epoch, per-session reset."""

from __future__ import annotations

import contextvars
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any, Iterator

import structlog
from fastapi import HTTPException

from .config import settings
from .demo_control import (
    acquire_global_reset_lock,
    bump_global_epoch,
    release_global_reset_lock,
)
from .demo_state import clear_all_memory, clear_session_memory

log = structlog.get_logger(__name__)

DEMO_SESSION_HEADER = "X-Demo-Session"
# EventSource cannot set custom headers; browser SSE uses this query param instead.
DEMO_SESSION_QUERY_PARAM = "demo_session"
SESSION_PREFIX = "session#"
DEFAULT_TEST_SESSION = "__playwright__"

current_demo_session_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "demo_session_id", default=None
)

_local_sessions: dict[str, dict[str, Any]] = {}
_local_lock = threading.Lock()
_LOCK_TTL_SEC = 60
_SESSION_TTL_DAYS = 7


class DemoSessionError(HTTPException):
    """HTTP errors for demo session / epoch conflicts."""

    def __init__(self, status_code: int, code: str, detail: str) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.code = code


def _table() -> Any | None:
    if not settings.demo_control_table:
        return None
    try:
        import boto3  # noqa: PLC0415

        ddb = boto3.resource("dynamodb", region_name=settings.bedrock_region)
        return ddb.Table(settings.demo_control_table)
    except Exception as exc:  # noqa: BLE001
        log.warning("demo_session.dynamo_unavailable", error=str(exc))
        return None


def _session_key(session_id: str) -> str:
    return f"{SESSION_PREFIX}{session_id}"


def _now_epoch() -> int:
    return int(time.time())


def create_session() -> dict[str, str]:
    session_id = str(uuid.uuid4())
    expires_at = datetime.now(UTC) + timedelta(days=_SESSION_TTL_DAYS)
    expires_epoch = int(expires_at.timestamp())
    record = {
        "id": _session_key(session_id),
        "session_id": session_id,
        "session_epoch": 0,
        "expires_at_epoch": expires_epoch,
        "reset_lock_token": "",
        "reset_lock_until": 0,
    }
    table = _table()
    if table is None:
        with _local_lock:
            _local_sessions[session_id] = dict(record)
    else:
        table.put_item(Item=record)
    return {
        "session_id": session_id,
        "expires_at": expires_at.isoformat(),
    }


def _read_session_record(session_id: str) -> dict[str, Any] | None:
    table = _table()
    if table is None:
        with _local_lock:
            rec = _local_sessions.get(session_id)
            return dict(rec) if rec else None
    try:
        resp = table.get_item(Key={"id": _session_key(session_id)})
        item = resp.get("Item")
        if not item:
            return None
        return dict(item)
    except Exception as exc:  # noqa: BLE001
        log.warning("demo_session.read_failed", error=str(exc))
        return None


def validate_session_id(session_id: str) -> None:
    rec = _read_session_record(session_id)
    if rec is None:
        raise DemoSessionError(401, "invalid_session", "Unknown demo session.")
    expires = int(rec.get("expires_at_epoch", 0))
    if expires and expires < _now_epoch():
        raise DemoSessionError(401, "session_expired", "Demo session expired.")


def get_session_epoch(session_id: str) -> int:
    rec = _read_session_record(session_id)
    if rec is None:
        return 0
    return int(rec.get("session_epoch", 0))


def require_session_id() -> str:
    sid = current_demo_session_id.get()
    if not sid:
        raise DemoSessionError(
            401,
            "session_required",
            f"{DEMO_SESSION_HEADER} header required.",
        )
    validate_session_id(sid)
    return sid


def bind_session(session_id: str) -> None:
    validate_session_id(session_id)
    current_demo_session_id.set(session_id)


def ensure_test_session(session_id: str = DEFAULT_TEST_SESSION) -> str:
    """Create default session for Playwright / test reset when absent."""
    if _read_session_record(session_id) is None:
        expires_at = datetime.now(UTC) + timedelta(days=_SESSION_TTL_DAYS)
        record = {
            "id": _session_key(session_id),
            "session_id": session_id,
            "session_epoch": 0,
            "expires_at_epoch": int(expires_at.timestamp()),
            "reset_lock_token": "",
            "reset_lock_until": 0,
        }
        table = _table()
        if table is None:
            with _local_lock:
                _local_sessions[session_id] = record
        else:
            table.put_item(Item=record)
    return session_id


def _acquire_session_reset_lock(session_id: str) -> str | None:
    now = _now_epoch()
    rec = _read_session_record(session_id)
    if rec is None:
        return None
    lock_until = int(rec.get("reset_lock_until", 0))
    if lock_until > now and rec.get("reset_lock_token"):
        return None
    token = str(uuid.uuid4())
    new_until = now + _LOCK_TTL_SEC
    table = _table()
    if table is None:
        with _local_lock:
            if session_id in _local_sessions:
                _local_sessions[session_id]["reset_lock_token"] = token
                _local_sessions[session_id]["reset_lock_until"] = new_until
                return token
        return None
    try:
        table.update_item(
            Key={"id": _session_key(session_id)},
            UpdateExpression="SET reset_lock_token = :t, reset_lock_until = :u",
            ConditionExpression=(
                "attribute_not_exists(reset_lock_until) OR reset_lock_until <= :now"
            ),
            ExpressionAttributeValues={":t": token, ":u": new_until, ":now": now},
        )
        return token
    except Exception:  # noqa: BLE001
        return None


def _release_session_reset_lock(session_id: str, token: str) -> None:
    rec = _read_session_record(session_id)
    if not rec or rec.get("reset_lock_token") != token:
        return
    table = _table()
    if table is None:
        with _local_lock:
            if session_id in _local_sessions:
                _local_sessions[session_id]["reset_lock_token"] = ""
                _local_sessions[session_id]["reset_lock_until"] = 0
        return
    try:
        table.update_item(
            Key={"id": _session_key(session_id)},
            UpdateExpression="SET reset_lock_token = :e, reset_lock_until = :z",
            ExpressionAttributeValues={":e": "", ":z": 0},
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("demo_session.release_lock_failed", error=str(exc))


def _bump_session_epoch(session_id: str) -> int:
    table = _table()
    if table is None:
        with _local_lock:
            rec = _local_sessions.setdefault(
                session_id,
                {
                    "id": _session_key(session_id),
                    "session_id": session_id,
                    "session_epoch": 0,
                },
            )
            rec["session_epoch"] = int(rec.get("session_epoch", 0)) + 1
            return int(rec["session_epoch"])
    try:
        resp = table.update_item(
            Key={"id": _session_key(session_id)},
            UpdateExpression="ADD session_epoch :one",
            ExpressionAttributeValues={":one": 1},
            ReturnValues="UPDATED_NEW",
        )
        return int(resp["Attributes"]["session_epoch"])
    except Exception as exc:  # noqa: BLE001
        log.warning("demo_session.bump_epoch_failed", error=str(exc))
        return get_session_epoch(session_id) + 1


def reset_session(session_id: str, *, clear_scan_cache: bool = True) -> dict[str, str]:
    token = _acquire_session_reset_lock(session_id)
    if token is None:
        raise DemoSessionError(
            409,
            "reset_in_progress",
            "Session reset already in progress.",
        )
    try:
        _bump_session_epoch(session_id)
        clear_session_memory(session_id, clear_scan_cache=clear_scan_cache)
        from .approval.store import clear_approvals_for_session  # noqa: PLC0415
        from .graph.outcome_repository import outcome_repo  # noqa: PLC0415

        clear_approvals_for_session(session_id)
        outcome_repo.clear_for_session(session_id)
        return {"status": "reset", "scope": "session", "session_id": session_id}
    finally:
        _release_session_reset_lock(session_id, token)


def run_global_reset(*, clear_scan_cache: bool = True) -> dict[str, str]:
    token = acquire_global_reset_lock()
    if token is None:
        raise DemoSessionError(
            409,
            "reset_in_progress",
            "Global reset already in progress.",
        )
    try:
        bump_global_epoch()
        clear_all_memory(clear_scan_cache=clear_scan_cache)
        from .approval.store import clear_all_approvals  # noqa: PLC0415
        from .graph.outcome_repository import outcome_repo  # noqa: PLC0415

        clear_all_approvals()
        outcome_repo.clear_all()
        return {"status": "reset", "scope": "global"}
    finally:
        release_global_reset_lock(token)


@contextmanager
def session_epoch_guard(session_id: str) -> Iterator[int]:
    """Capture session epoch at start; raise 409 if it changed before exit."""
    start = get_session_epoch(session_id)
    yield start
    if get_session_epoch(session_id) != start:
        raise DemoSessionError(
            409,
            "session_reset",
            "Demo was reset — refresh the page and try again.",
        )


def assert_session_epoch_unchanged(session_id: str, epoch_at_start: int) -> None:
    if get_session_epoch(session_id) != epoch_at_start:
        raise DemoSessionError(
            409,
            "session_reset",
            "Demo was reset — refresh the page and try again.",
        )
