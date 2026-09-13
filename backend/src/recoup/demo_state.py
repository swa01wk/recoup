"""Session-partitioned in-memory demo state (scan graph, cache, audit)."""

from __future__ import annotations

from typing import Any

from .graph.types import GraphState
from .scanners.finding import ScanResult

# session_id -> opp_id -> GraphState
_graph_states_by_session: dict[str, dict[str, GraphState]] = {}

# session_id -> account_ns -> resource_id -> promoted record
_promoted_findings_by_session: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}

# session_id -> cache_key -> ScanResult
_last_scan_result_by_session: dict[str, dict[str, ScanResult]] = {}

# session_id -> list of audit entries
_scan_audit_log_by_session: dict[str, list[dict[str, Any]]] = {}

# session_id -> account_id -> history entries
_scan_history_by_session: dict[str, dict[str, list[dict[str, Any]]]] = {}


def graph_states(session_id: str) -> dict[str, GraphState]:
    return _graph_states_by_session.setdefault(session_id, {})


def promoted_findings(session_id: str) -> dict[str, dict[str, dict[str, Any]]]:
    return _promoted_findings_by_session.setdefault(session_id, {})


def scan_result_cache(session_id: str) -> dict[str, ScanResult]:
    return _last_scan_result_by_session.setdefault(session_id, {})


def scan_audit_log(session_id: str) -> list[dict[str, Any]]:
    return _scan_audit_log_by_session.setdefault(session_id, [])


def scan_history(session_id: str) -> dict[str, list[dict[str, Any]]]:
    return _scan_history_by_session.setdefault(session_id, {})


def clear_session_memory(session_id: str, *, clear_scan_cache: bool = True) -> None:
    _graph_states_by_session.pop(session_id, None)
    _promoted_findings_by_session.pop(session_id, None)
    _scan_audit_log_by_session.pop(session_id, None)
    _scan_history_by_session.pop(session_id, None)
    if clear_scan_cache:
        _last_scan_result_by_session.pop(session_id, None)


def clear_all_memory(*, clear_scan_cache: bool = True) -> None:
    _graph_states_by_session.clear()
    _promoted_findings_by_session.clear()
    _scan_audit_log_by_session.clear()
    _scan_history_by_session.clear()
    if clear_scan_cache:
        _last_scan_result_by_session.clear()
