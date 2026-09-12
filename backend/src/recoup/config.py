"""Application configuration — all settings from environment variables."""

from __future__ import annotations

import json
import logging
import pathlib

import structlog
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always resolve the project-root .env regardless of the working directory
# the server was launched from (backend/, project root, or anywhere else).
# Path: backend/src/recoup/config.py → backend/src/recoup → backend/src → backend → project root
_ROOT_ENV = pathlib.Path(__file__).parent.parent.parent.parent / ".env"

log = structlog.get_logger(__name__)


def _load_secrets_from_aws(secrets_arn: str) -> dict[str, str]:
    """
    Sprint 4 — Load sensitive config from AWS Secrets Manager.

    Fetches the secret at *secrets_arn* and returns a flat dict of
    string key→value pairs.  Falls back gracefully (returns {}) when
    boto3 is not installed, credentials are absent, or the secret does
    not exist — so local development is never broken.
    """
    try:
        import boto3  # noqa: PLC0415
        import botocore.config  # noqa: PLC0415

        cfg = botocore.config.Config(connect_timeout=3, read_timeout=5,
                                      retries={"max_attempts": 1})
        client = boto3.client("secretsmanager", config=cfg)
        response = client.get_secret_value(SecretId=secrets_arn)
        raw = response.get("SecretString") or ""
        return json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning(
            "secrets_manager.load_failed: %s — using environment variables only", exc
        )
        return {}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Load project-root .env first (absolute path — works regardless of cwd),
        # then fall back to a local .env in the working directory.
        # Environment variables always take final precedence (pydantic-settings default).
        env_file=[str(_ROOT_ENV), ".env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment — controls CORS, test-reset gate, fallback behaviour
    # Values: "local" | "staging" | "production"
    recoup_env: str = "local"

    # Frontend URL — set to https://your-app.vercel.app in production
    frontend_url: str = "http://localhost:3000"

    # Structured logging level
    recoup_log_level: str = "INFO"

    # LLM provider — controls which model backend Strands agents use.
    # Supported values: "bedrock" (default) | "openai"
    # Add new providers by registering them in strands_agents._MODEL_PROVIDERS.
    llm_provider: str = "bedrock"

    # Bedrock
    bedrock_model_id: str = "us.amazon.nova-pro-v1:0"
    bedrock_region: str = "us-east-1"

    # OpenAI (used when llm_provider="openai")
    openai_api_key: str = ""
    openai_model_id: str = "gpt-4o"

    # AgentCore
    agentcore_runtime_arn: str = ""
    agentcore_gateway_url: str = ""

    # DynamoDB
    opportunities_table: str = "recoup-opportunities"
    approvals_table: str = "recoup-approvals"
    tool_audits_table: str = "recoup-tool-audits"
    outcome_metadata_table: str = "recoup-outcome-metadata"

    # S3
    evidence_bucket: str = ""
    sla_catalog_bucket: str = ""
    eval_fixtures_bucket: str = ""
    evidence_kms_key_id: str = ""

    # SNS
    recoup_sns_topic_arn: str = ""
    # When true, notify_sns() logs the payload and returns success without calling AWS
    # (Playwright / local smoke — use real RECOUP_SNS_TOPIC_ARN for live email test)
    recoup_sns_dry_run: bool = False

    # SQS
    recovery_events_queue_url: str = ""

    # EC2 Demo
    recoup_demo_instance_allowlist: str = ""
    allowlisted_demo_account_id: str = ""

    # Phase 6e — IAM role ARNs for STS AssumeRole architecture
    # RecoupReadOnlyRole: broad read-only analysis (inventory / cost / telemetry)
    recoup_readonly_role_arn: str = ""
    # ExternalId used in the RecoupReadOnlyRole trust policy condition
    recoup_external_id: str = ""
    # RecoupRemediationRole: ec2:StopInstances on RecoupDemo=true only
    recoup_remediation_role_arn: str = ""
    # RecoupRuntimeRole: application execution identity (informational)
    recoup_runtime_role_arn: str = ""

    # Phase 6f — scanner demo tuning thresholds
    # Set stale_snapshot_days=0 to detect snapshots of any age (demo mode)
    recoup_stale_snapshot_days: int = 90
    # Set rds_lookback_days=1 to flag new RDS instances immediately (demo mode)
    recoup_rds_lookback_days: int = 7

    # Feature flags — default OFF; must be explicitly enabled
    recoup_enable_real_support_submission: bool = False
    # Sidebar "Reset Demo Data" — allowed in production only when explicitly enabled
    recoup_enable_admin_reset: bool = False

    # Recovery pipeline — LLM on promote (default off for CI/Playwright)
    recovery_llm_on_promote: bool = False
    recovery_llm_on_investigate: bool = True

    # Cost control
    recoup_max_replay_runs_per_day: int = 100

    # Sprint 4 — API key auth (optional; set to enforce in production)
    # When set, all non-public API calls must include:
    #   X-API-Key: <value>   OR   Authorization: Bearer <value>
    recoup_api_key: str = ""

    # Sprint 4 — Secrets Manager ARN (optional)
    # When set, secrets are loaded from AWS Secrets Manager at startup
    # and override any matching environment variables.
    recoup_secrets_arn: str = ""

    # Sprint 4 — Sentry DSN (optional)
    sentry_dsn: str = ""

    @property
    def demo_instance_ids(self) -> list[str]:
        return [i.strip() for i in self.recoup_demo_instance_allowlist.split(",") if i.strip()]

    @property
    def live_aws_enabled(self) -> bool:
        """True when real AWS resources are configured (inferred from settings)."""
        return bool(
            self.evidence_bucket
            or self.recoup_sns_topic_arn
            or self.recovery_events_queue_url
            or self.approvals_table
        )


def _build_settings() -> Settings:
    """
    Build Settings, optionally overlaying values from AWS Secrets Manager.
    Called once at module import time.
    """
    base = Settings()
    if base.recoup_secrets_arn:
        overrides = _load_secrets_from_aws(base.recoup_secrets_arn)
        if overrides:
            # Re-instantiate with overrides applied so pydantic validates them
            merged = base.model_dump()
            # Only override keys that are actual Setting fields
            valid_keys = set(base.model_fields.keys())
            for k, v in overrides.items():
                k_lower = k.lower()
                if k_lower in valid_keys:
                    merged[k_lower] = v
            return Settings.model_validate(merged)
    return base


settings = _build_settings()
