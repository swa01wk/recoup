"""
Recoup FastAPI application.

Mounts all route prefixes and configures middleware, CORS, and health checks.

Run locally:
    cd backend && uvicorn recoup.api.main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import settings
from .routes.approvals import router as approvals_router
from .routes.opportunities import router as opportunities_router
from .routes.replay import router as replay_router

app = FastAPI(
    title="Recoup — AWS Spend Recovery Agent",
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
    allow_origins=["*"],  # Phase 4: restrict to frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(opportunities_router, prefix="/api/opportunities", tags=["opportunities"])
app.include_router(approvals_router, prefix="/api/approvals", tags=["approvals"])
app.include_router(replay_router, prefix="/api/replay", tags=["replay"])


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/config", tags=["meta"])
def config_info() -> dict[str, str | bool]:
    """Return non-secret config for the frontend feature-flag panel."""
    return {
        "simulation_mode": True,
        "live_aws_enabled": settings.recoup_enable_live_aws,
        "real_submission_enabled": settings.recoup_enable_real_support_submission,
        "bedrock_model": settings.bedrock_model_id,
        "bedrock_region": settings.bedrock_region,
    }
