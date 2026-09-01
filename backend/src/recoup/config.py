"""Application configuration — all settings from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Bedrock
    bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    bedrock_region: str = "us-east-1"

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

    # SQS
    recovery_events_queue_url: str = ""

    # EC2 Demo
    recoup_demo_instance_allowlist: str = ""
    allowlisted_demo_account_id: str = ""

    # Feature flags — default OFF; must be explicitly enabled
    recoup_enable_live_aws: bool = False
    recoup_enable_real_support_submission: bool = False

    # Cost control
    recoup_max_replay_runs_per_day: int = 100

    @property
    def demo_instance_ids(self) -> list[str]:
        return [i.strip() for i in self.recoup_demo_instance_allowlist.split(",") if i.strip()]


settings = Settings()
