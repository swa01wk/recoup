"""Evidence items, manifests, and redaction reports."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RedactionReport(BaseModel):
    evidence_id: str = ""
    redaction_count: int = 0
    raw_hash: str = ""
    sanitized_hash: str = ""
    patterns_applied: list[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    id: str
    type: Literal["metric", "log", "health_event", "billing_record", "contract"]
    source: str
    timestamp_range: tuple[datetime, datetime]
    storage_uri: str = Field(description="S3 URI of raw evidence; encrypted at rest")
    sanitized_uri: str | None = Field(default=None, description="S3 URI of sanitized version")
    hash: str = Field(description="SHA-256 of raw content; starts with 'sha256:'")
    sensitivity: Literal["LOW", "MEDIUM", "HIGH"]
    status: Literal["FOUND", "MISSING", "REDACTED"]


class EvidenceManifest(BaseModel):
    opportunity_id: str
    items: list[EvidenceItem] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    redaction_report: RedactionReport = Field(default_factory=RedactionReport)

    @property
    def is_complete(self) -> bool:
        return len(self.missing_fields) == 0

    @property
    def item_ids(self) -> set[str]:
        return {item.id for item in self.items}
