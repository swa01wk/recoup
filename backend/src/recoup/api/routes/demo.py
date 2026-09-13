"""Guest demo session API — issue token and per-session reset."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...config import settings
from ...demo_session import (
    create_session,
    reset_session,
    require_session_id,
)

router = APIRouter()


def _session_reset_allowed() -> bool:
    if settings.recoup_env != "production":
        return True
    return settings.recoup_enable_admin_reset


@router.post("/session")
def issue_demo_session() -> dict[str, str]:
    """Create a new guest demo session (browser stores session_id)."""
    return create_session()


@router.post("/session/reset")
def reset_demo_session(clear_scan_cache: bool = True) -> dict[str, str]:
    """Clear demo state for the caller's session only."""
    if not _session_reset_allowed():
        raise HTTPException(
            status_code=403,
            detail="Session reset disabled in production.",
        )
    session_id = require_session_id()
    return reset_session(session_id, clear_scan_cache=clear_scan_cache)
