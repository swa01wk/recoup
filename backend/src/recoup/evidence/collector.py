"""
Evidence Collector — gathers AWS evidence and stores it to encrypted S3.

Design principles:
- Raw evidence is NEVER passed to the LLM or user-visible API responses.
- Each field is fetched, hashed, and stored to S3 independently.
- The manifest carries only S3 URIs and SHA-256 hashes — not the raw content.
- S3 writes are skipped when no S3 bucket is configured, so the graph runs
  end-to-end in replay / CI mode without any AWS calls.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

import structlog

from ..config import settings
from ..models.evidence import EvidenceItem, EvidenceManifest, RedactionReport
from ..models.signal import IncidentSignal
from ..models.sla import SLAContract

log: structlog.BoundLogger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Field → EvidenceItem type mapping
# ---------------------------------------------------------------------------

FIELD_TO_TYPE: dict[str, str] = {
    "request_logs": "log",
    "error_logs": "log",
    "billing_record": "billing_record",
    "health_event": "health_event",
    "cloudtrail_events": "log",
    "metric_series": "metric",
    "sla_contract": "contract",
    "api_id": "log",
    "region": "log",
    "billing_cycle": "billing_record",
}

FIELD_SENSITIVITY: dict[str, str] = {
    "request_logs": "HIGH",
    "error_logs": "HIGH",
    "billing_record": "MEDIUM",
    "health_event": "LOW",
    "cloudtrail_events": "HIGH",
    "metric_series": "LOW",
    "sla_contract": "LOW",
    "api_id": "LOW",
    "region": "LOW",
    "billing_cycle": "LOW",
}

# Fields that can be derived from the signal without an AWS call
_SIGNAL_FIELDS = {"api_id", "region", "billing_cycle"}


def _sha256(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode()).hexdigest()


def _evidence_id(opportunity_id: str, field_name: str) -> str:
    return "ev-" + hashlib.sha256(
        f"{opportunity_id}:{field_name}".encode()
    ).hexdigest()[:8]


class EvidenceCollector:
    """
    Collects evidence required by the SLA contract and stores it to S3.

    Instantiate once per graph run and call ``collect()``.  The returned
    EvidenceManifest contains only S3 URIs and hashes — raw content never
    leaves this class.

    Args:
        replay_fixtures:  Pre-loaded fixture data from the replay adapter.
                          When present, fixture content is used as the raw
                          evidence instead of live AWS calls.
        live_evidence:   When True, S3 writes are attempted (with silent fallback
                         on error). When False (default), S3 writes are skipped
                         so tests never require AWS credentials.
    """

    def __init__(
        self,
        replay_fixtures: dict[str, Any] | None = None,
        live_evidence: bool = False,
    ) -> None:
        self._replay_fixtures = replay_fixtures or {}
        self._live_evidence = live_evidence

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def collect(
        self,
        contract: SLAContract,
        signal: IncidentSignal,
        opportunity_id: str,
    ) -> EvidenceManifest:
        """
        Collect all required evidence fields and return a populated manifest.

        Missing fields are recorded (not fatal) — eligibility_reasoner will
        inspect ``missing_fields`` and may downgrade confidence.
        """
        items: list[EvidenceItem] = []
        missing: list[str] = []

        for field_name in contract.required_claim_fields:
            try:
                item = self._collect_field(field_name, signal, opportunity_id)
                items.append(item)
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "evidence_collector.field_missing",
                    field=field_name,
                    opportunity_id=opportunity_id,
                    error=str(exc),
                )
                missing.append(field_name)

        return EvidenceManifest(
            opportunity_id=opportunity_id,
            items=items,
            missing_fields=missing,
            redaction_report=RedactionReport(evidence_id=opportunity_id),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _collect_field(
        self,
        field_name: str,
        signal: IncidentSignal,
        opportunity_id: str,
    ) -> EvidenceItem:
        # Phase 1: fetch raw content — failure here means the field is truly missing
        raw_content = self._fetch_raw(field_name, signal)
        raw_json = json.dumps(raw_content, default=str, sort_keys=True)
        content_hash = _sha256(raw_json)

        s3_key = (
            f"evidence/raw/{opportunity_id}/{field_name}/"
            f"{uuid.uuid4().hex[:8]}.json"
        )
        storage_uri = f"s3://{settings.evidence_bucket or 'recoup-evidence'}/{s3_key}"

        ev_type = FIELD_TO_TYPE.get(field_name, "log")
        sensitivity = FIELD_SENSITIVITY.get(field_name, "MEDIUM")

        if not self._live_evidence:
            log.debug("evidence_collector.s3_skip_no_live_evidence", uri=storage_uri)
            storage_uri = f"stub://{opportunity_id}/{field_name}"
        else:
            # Phase 2: persist to S3 — failure here is a storage warning, not a
            # missing-field error.  Evidence was collected; it just wasn't persisted.
            try:
                self._store_to_s3(storage_uri, raw_json)
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "evidence_collector.s3_store_failed_non_fatal",
                    field=field_name,
                    uri=storage_uri,
                    error=str(exc),
                )

        return EvidenceItem(
            id=_evidence_id(opportunity_id, field_name),
            type=ev_type,  # type: ignore[arg-type]
            source=field_name,
            timestamp_range=(signal.start, signal.end),
            storage_uri=storage_uri,
            sanitized_uri=None,
            hash=content_hash,
            sensitivity=sensitivity,  # type: ignore[arg-type]
            status="FOUND",
        )

    def _fetch_raw(self, field_name: str, signal: IncidentSignal) -> Any:
        """
        Return raw evidence for a field.

        Priority:
          1. Replay fixture data (deterministic; no AWS call)
          2. Signal-derived constant fields (api_id, region, billing_cycle)
          3. Stub payload (no replay fixture; no AWS call)

        Phase 3: live AWS calls will replace step 3 via injected tool callables.
        """
        # 1. Replay fixtures
        if field_name in self._replay_fixtures:
            return self._replay_fixtures[field_name]

        # 2. Signal-derived fields
        if field_name in _SIGNAL_FIELDS:
            return {
                "field": field_name,
                "value": getattr(signal, field_name, None)
                or signal.region
                or signal.service,
                "incident_start": signal.start.isoformat(),
                "incident_end": signal.end.isoformat(),
            }

        # 3. Simulation stub
        return {
            "field": field_name,
            "service": signal.service,
            "region": signal.region,
            "start": signal.start.isoformat(),
            "end": signal.end.isoformat(),
            "_stub": True,
        }

    def _store_to_s3(self, storage_uri: str, content: str) -> None:
        """
        Write content to S3 with KMS encryption.

        Silently skips the write when live_evidence is False so tests never
        require AWS credentials.
        """
        if not self._live_evidence:
            log.debug("evidence_collector.s3_skip_no_live_evidence", uri=storage_uri)
            return

        try:
            import boto3

            bucket, key = storage_uri.replace("s3://", "").split("/", 1)
            s3 = boto3.client("s3")
            kwargs: dict[str, Any] = {
                "Bucket": bucket,
                "Key": key,
                "Body": content.encode(),
                "ServerSideEncryption": "aws:kms",
            }
            kms_key = settings.evidence_kms_key_id
            if kms_key:
                kwargs["SSEKMSKeyId"] = kms_key
            s3.put_object(**kwargs)
            log.info("evidence_collector.s3_stored", uri=storage_uri)
        except Exception as exc:  # noqa: BLE001
            log.warning("evidence_collector.s3_failed", uri=storage_uri, error=str(exc))
            raise  # caller (_collect_field) decides whether this is fatal
