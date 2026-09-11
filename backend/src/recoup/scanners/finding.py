"""Data models for the Account Scanner."""

from __future__ import annotations

import hashlib
from typing import Any, Literal

from pydantic import BaseModel, Field


class Finding(BaseModel):
    service: str
    resource_id: str
    resource_type: str
    issue: str
    estimated_monthly_savings_usd: float
    recommendation: str
    severity: Literal["high", "medium", "low"]
    region: str
    # Phase 6f — per-finding evidence + demo workload metadata
    evidence: dict[str, Any] = Field(
        default_factory=dict,
        description="Service-specific telemetry evidence (CPU avg, volume type, etc.)",
    )
    scenario_tag: str | None = Field(
        default=None,
        description="RecoupScenario tag value if resource is a demo workload",
    )
    is_demo_resource: bool = Field(
        default=False,
        description="True if resource has RecoupDemo=true tag",
    )
    finding_type: str | None = Field(
        default=None,
        description="Machine-readable finding type (e.g. IDLE_INSTANCE, UNATTACHED_VOLUME)",
    )
    content_hash: str | None = Field(
        default=None,
        description=(
            "sha256 of resource_id|finding_type|savings|severity|issue — "
            "changes only when the finding itself changes. Used for idempotent upserts: "
            "if the hash matches the stored hash, the opportunity is NOT re-promoted."
        ),
    )

    def compute_content_hash(self) -> str:
        """Return sha256(resource_id|finding_type|savings_cents|severity|issue)."""
        savings_cents = round(self.estimated_monthly_savings_usd * 100)
        raw = (
            f"{self.resource_id}|{self.finding_type or ''}|"
            f"{savings_cents}|{self.severity}|{self.issue}"
        )
        return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


class ScanRequest(BaseModel):
    """
    Connection request using STS AssumeRole.

    Phase 6e: raw access keys replaced with a role ARN + External ID.
    Recoup calls ``sts:AssumeRole`` internally — no long-lived credentials
    are ever stored or transmitted.
    """

    role_arn: str = Field(
        ...,
        description="ARN of RecoupReadOnlyRole (or equivalent) to assume via STS",
    )
    external_id: str = Field(
        ...,
        description="External ID matching the role's trust policy condition",
    )
    region: str = Field(default="us-east-1", description="Primary AWS region to scan")
    regions: list[str] = Field(
        default_factory=list,
        description="Additional regions to include in the scan",
    )


class ScanResult(BaseModel):
    scanned_at: str
    account_id: str | None = None
    region: str
    findings: list[Finding]
    total_estimated_monthly_savings_usd: float
    errors: list[str]
    scan_duration_seconds: float
    # Phase 6e — STS AssumeRole provenance
    assumed_role_arn: str | None = None
    assumed_role_account_id: str | None = None
    session_name: str | None = None
    # Phase 6f — pre-grouped findings + demo metadata
    findings_by_service: dict[str, list[Finding]] = Field(
        default_factory=dict,
        description="Findings grouped by AWS service name for frontend rendering",
    )
    # Scan dedup / history fields
    scan_id: str | None = Field(
        default=None,
        description="Unique identifier for this scan run (UUID)",
    )
    scan_hash: str | None = Field(
        default=None,
        description=(
            "sha256 of all sorted finding content_hashes — "
            "unchanged when the same resources are found with the same details"
        ),
    )
    is_cached: bool = Field(
        default=False,
        description=(
            "True when a rescan produced the same findings as the previous scan. "
            "The result is the cached scan re-served to prevent duplicate opportunities."
        ),
    )
