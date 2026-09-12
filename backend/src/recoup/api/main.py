"""
Recoup FastAPI application.

Mounts all route prefixes and configures middleware, CORS, and health checks.

Run locally:
    cd backend && uvicorn recoup.api.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address
    _SLOWAPI_AVAILABLE = True
except ImportError:  # noqa: BLE001
    _SLOWAPI_AVAILABLE = False
    Limiter = None  # type: ignore[assignment, misc]
    RateLimitExceeded = None  # type: ignore[assignment, misc]
    _rate_limit_exceeded_handler = None  # type: ignore[assignment]

    def get_remote_address(request: "Request") -> str:  # type: ignore[misc]
        return "unknown"

# ── Sentry (optional) ────────────────────────────────────────────────────────
try:
    import sentry_sdk as _sentry_sdk
    _SENTRY_AVAILABLE = True
except ImportError:  # noqa: BLE001
    _SENTRY_AVAILABLE = False
    _sentry_sdk = None  # type: ignore[assignment]

from ..config import settings
from ..sqs_poller import start_poller, stop_poller
from .routes.approvals import router as approvals_router
from .routes.opportunities import router as opportunities_router
from .routes.quality import router as quality_router
from .routes.scan import router as scan_router


def _configure_logging() -> None:
    """Centralise structlog configuration; wire RECOUP_LOG_LEVEL."""
    log_level = getattr(logging, settings.recoup_log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
            if settings.recoup_env == "local"
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


def _configure_sentry() -> None:
    """Sprint 4 — Initialise Sentry SDK when SENTRY_DSN is configured."""
    if not settings.sentry_dsn:
        return
    if not _SENTRY_AVAILABLE:
        logging.getLogger("recoup.api").warning(
            "SENTRY_DSN is set but sentry-sdk is not installed — skipping Sentry init"
        )
        return
    _sentry_sdk.init(  # type: ignore[union-attr]
        dsn=settings.sentry_dsn,
        environment=settings.recoup_env,
        traces_sample_rate=0.1,
        # Don't send PII by default
        send_default_pii=False,
    )
    logging.getLogger("recoup.api").info("sentry.initialised")


# ── Rate limiter ─────────────────────────────────────────────────────────────
# Applied selectively to expensive endpoints (scan, replay, agent stream).
limiter = Limiter(key_func=get_remote_address) if _SLOWAPI_AVAILABLE else None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    _configure_logging()
    _configure_sentry()
    start_poller()
    yield
    stop_poller()


# ── CORS origins ─────────────────────────────────────────────────────────────
# In local/staging mode we allow localhost origins for development convenience.
# In production, only the explicit frontend URL is allowed.
_CORS_ORIGINS: list[str] = (
    ["*"]
    if settings.recoup_env == "local"
    else [
        settings.frontend_url,
        # Allow localhost for staging testing
        "http://localhost:3000",
        "http://localhost:3001",
    ]
)

app = FastAPI(
    title="Recoup — AWS Spend Recovery Agent",
    lifespan=lifespan,
    version="0.1.0",
    description=(
        "Autonomous SLA credit recovery and cost optimisation for AWS workloads. "
        "All external financial actions require human approval."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Wire slowapi rate limiter (no-op when slowapi not installed)
if _SLOWAPI_AVAILABLE and limiter is not None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]


# ── Public paths that never require authentication ────────────────────────────
_PUBLIC_PATHS: frozenset[str] = frozenset({
    "/health",
    "/health/ready",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/config",
})


# ── API-key auth middleware (Sprint 4) ───────────────────────────────────────
@app.middleware("http")
async def api_key_auth(request: Request, call_next):  # type: ignore[no-untyped-def]
    """
    Enforce API-key authentication when RECOUP_API_KEY is set in production.

    Accepted tokens (checked in order):
      1. X-API-Key: <key>   header
      2. Authorization: Bearer <key>   header

    Rules:
    - Only active when ``settings.recoup_api_key`` is non-empty.
    - Local environment (``recoup_env=local``) skips the check so that
      local development requires no credentials.
    - Public paths (/health, /docs, etc.) are always allowed through.
    """
    api_key = settings.recoup_api_key
    # Skip if no key configured or in local dev
    if not api_key or settings.recoup_env == "local":
        return await call_next(request)

    # Always allow public paths
    if request.url.path in _PUBLIC_PATHS:
        return await call_next(request)

    # OPTIONS pre-flight — never block
    if request.method == "OPTIONS":
        return await call_next(request)

    # Extract presented token
    presented: str = (
        request.headers.get("X-API-Key", "")
        or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    )

    import hmac  # noqa: PLC0415
    valid = hmac.compare_digest(presented.encode(), api_key.encode())
    if not valid:
        log = structlog.get_logger("recoup.auth")
        log.warning("auth.rejected", path=request.url.path, method=request.method)
        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized — X-API-Key or Authorization: Bearer required."},
        )

    return await call_next(request)


# ── Request-ID middleware ─────────────────────────────────────────────────────
@app.middleware("http")
async def inject_request_id(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ── Global exception handler — sanitized, no stack-trace leakage ─────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log = structlog.get_logger("recoup.api")
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    log.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error_type=type(exc).__name__,
        request_id=request_id,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "An internal error occurred.",
            "request_id": request_id,
        },
    )

app.include_router(opportunities_router, prefix="/api/opportunities", tags=["opportunities"])
app.include_router(approvals_router, prefix="/api/approvals", tags=["approvals"])
app.include_router(quality_router, prefix="/api/quality", tags=["quality"])
app.include_router(scan_router, prefix="/api/scan", tags=["scan"])


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "version": "0.1.0"}


@app.get("/health/ready", tags=["meta"])
def health_ready() -> dict[str, object]:
    """Readiness probe — checks key downstream dependencies."""
    checks: dict[str, str] = {}

    # DynamoDB reachability (non-blocking — skip when not configured)
    if settings.approvals_table:
        try:
            import boto3  # noqa: PLC0415
            ddb = boto3.client("dynamodb", region_name=settings.bedrock_region)
            ddb.describe_table(TableName=settings.approvals_table)
            checks["dynamodb"] = "ok"
        except Exception as exc:  # noqa: BLE001
            checks["dynamodb"] = f"error: {type(exc).__name__}"
    else:
        checks["dynamodb"] = "not_configured"

    all_ok = all(v in ("ok", "not_configured") for v in checks.values())
    return {"status": "ready" if all_ok else "degraded", "ready": all_ok, "checks": checks}


def _admin_reset_allowed() -> bool:
    """Gate POST /api/admin/reset — always on in non-production; opt-in in production."""
    if settings.recoup_env != "production":
        return True
    return settings.recoup_enable_admin_reset


def _do_full_reset(*, clear_scan_cache: bool = False) -> dict[str, str]:
    """Shared implementation for full in-memory state reset."""
    from .routes.opportunities import _graph_states
    from .routes.scan import _promoted_findings, _scan_audit_log, _last_scan_result, _scan_history

    _graph_states.clear()
    _promoted_findings.clear()
    _scan_audit_log.clear()
    _scan_history.clear()
    if clear_scan_cache:
        _last_scan_result.clear()

    # Clear approvals — in-memory AND DynamoDB (recoup-approvals table)
    try:
        from ..approval.store import clear_all_approvals  # noqa: PLC0415
        clear_all_approvals()
    except Exception:  # noqa: BLE001
        pass

    # Clear outcome records — in-memory AND DynamoDB (recoup-outcome-metadata table)
    # This is the source of stale "Recovered" rows that survive server restarts.
    try:
        from ..graph.outcome_repository import outcome_repo  # noqa: PLC0415
        outcome_repo.clear_all()
    except Exception:  # noqa: BLE001
        pass

    cleared = "graph_states,promoted_findings,scan_audit,scan_history,approvals_dynamo,outcomes_dynamo"
    if clear_scan_cache:
        cleared += ",scan_cache"
    return {"status": "reset", "cleared": cleared}


@app.post("/api/admin/reset", tags=["admin"])
def admin_reset(clear_scan_cache: bool = False) -> dict[str, str]:
    """
    Full in-memory state reset for demo/development use.

    Clears all opportunities, promoted findings, approvals, audit log, and outcome records.
    Optionally clears the scan result cache (pass ?clear_scan_cache=true) so the next
    scan fetches fresh data from AWS.

    Disabled in production unless RECOUP_ENABLE_ADMIN_RESET=true (hosted judge demo).
    """
    from fastapi import HTTPException as _HTTPException  # noqa: PLC0415

    if not _admin_reset_allowed():
        raise _HTTPException(status_code=403, detail="Admin reset disabled in production.")

    return _do_full_reset(clear_scan_cache=clear_scan_cache)


@app.get("/api/test/reset", tags=["meta"])
@app.post("/api/test/reset", tags=["meta"])
def test_reset() -> dict[str, str]:
    """
    Reset all in-memory state for Playwright test isolation.

    Clears _graph_states, _promoted_findings, approvals (in-memory), and scan audit/history.
    Does not clear the demo scan cache (see clear_scan_cache on admin reset).

    DISABLED in production (RECOUP_ENV=production).
    """
    from fastapi import HTTPException as _HTTPException  # noqa: PLC0415

    if settings.recoup_env == "production":
        raise _HTTPException(status_code=403, detail="Test reset disabled in production.")

    # NOTE: _last_scan_result is intentionally NOT cleared here for test isolation.
    # The demo scan hits real AWS APIs (~22 s each call); keeping the cached result
    # across test resets means only the first test pays the round-trip cost.
    return _do_full_reset(clear_scan_cache=False)


@app.get("/api/config", tags=["meta"])
def config_info() -> dict[str, str | bool]:
    """Return non-secret config for the frontend feature-flag panel."""
    return {
        "real_submission_enabled": settings.recoup_enable_real_support_submission,
        # LLM provider adapter — "bedrock" | "openai" (see LLM_PROVIDER env var)
        "llm_provider": settings.llm_provider,
        # Bedrock fields — still included when llm_provider="bedrock"
        "bedrock_model": settings.bedrock_model_id,
        "bedrock_region": settings.bedrock_region,
        # OpenAI fields — model ID is safe to expose; api_key is intentionally omitted
        "openai_model_id": settings.openai_model_id if settings.llm_provider == "openai" else "",
        "evidence_bucket_configured": bool(settings.evidence_bucket),
        "sns_notifications_enabled": bool(settings.recoup_sns_topic_arn),
        "sqs_events_enabled": bool(settings.recovery_events_queue_url),
        "admin_reset_enabled": _admin_reset_allowed(),
    }
