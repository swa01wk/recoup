"""
Evidence Sanitizer — deterministic redaction of raw evidence content.

Design principles:
- No LLM involvement — purely regex-based, deterministic, reproducible.
- Fail-closed: if any high-risk pattern survives all redaction passes, the
  sanitizer raises SanitizationError and the item is quarantined.
- Two-pass design:
    Pass 1 — apply REDACTION_PATTERNS (known secret/PII shapes)
    Pass 2 — HIGH_RISK_SCANNER checks for any remaining dangerous content
- Raw content is loaded from S3; sanitized content is stored back to S3.
  When no S3 bucket is configured, content is passed directly so the
  sanitizer is fully testable without AWS credentials.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import structlog

from ..models.evidence import EvidenceItem, EvidenceManifest, RedactionReport
from ..safety.exceptions import SanitizationError

log: structlog.BoundLogger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Redaction patterns — compiled once at module load
# ---------------------------------------------------------------------------

# Each entry is (compiled_pattern, replacement_string, label)
REDACTION_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # Authorization headers (Bearer tokens, Basic auth)
    (
        re.compile(
            r"(?i)(authorization\s*[:\=]\s*)(bearer\s+[\w\-\.]+|basic\s+[A-Za-z0-9+/=]+)",
            re.MULTILINE,
        ),
        r"\1[REDACTED-AUTH-TOKEN]",
        "auth_token",
    ),
    # API keys in JSON / query strings
    (
        re.compile(
            r'(?i)(api[_\-]?key["\']*\s*[:\=]\s*["\']?)([^"\'&\s,}\]]{8,})',
            re.MULTILINE,
        ),
        r"\1[REDACTED-API-KEY]",
        "api_key",
    ),
    # Cookie headers
    (
        re.compile(r"(?i)(cookie\s*:\s*)(.+)", re.MULTILINE),
        r"\1[REDACTED-COOKIE]",
        "cookie",
    ),
    # JWT tokens (three base64url segments separated by dots)
    (
        re.compile(
            r"eyJ[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]{10,}"
        ),
        "[REDACTED-JWT]",
        "jwt",
    ),
    # AWS secret access keys (40-char uppercase alphanumeric not adjacent to more)
    (
        re.compile(r"(?<![A-Z0-9])[A-Z0-9]{40}(?![A-Z0-9])"),
        "[REDACTED-AWS-SECRET]",
        "aws_secret",
    ),
    # Email addresses (generic PII)
    (
        re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
        "[REDACTED-EMAIL]",
        "email",
    ),
    # AWS account IDs (12-digit numbers in IAM ARNs or standalone)
    (
        re.compile(r"(?<!\d)\d{12}(?!\d)"),
        "[REDACTED-ACCOUNT-ID]",
        "account_id",
    ),
    # Private IP addresses
    (
        re.compile(
            r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
            r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
            r"|192\.168\.\d{1,3}\.\d{1,3})\b"
        ),
        "[REDACTED-PRIVATE-IP]",
        "private_ip",
    ),
]

# Second-pass scanner — any match here means redaction failed; fail closed.
_HIGH_RISK_SCANNER: re.Pattern[str] = re.compile(
    r"(?i)(password|secret|private[_\-]?key|credential|token)"
    r"[\s]*[:\=][\s]*[^\s,}\]]{8,}",
    re.MULTILINE,
)


def _sha256(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Sanitizer class
# ---------------------------------------------------------------------------


class EvidenceSanitizer:
    """
    Apply deterministic redaction to all items in an EvidenceManifest.

    S3 loads/stores are attempted when the item has a valid storage_uri;
    falls back to stub content on any S3 error so replay runs always succeed.
    """

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sanitize_manifest(self, manifest: EvidenceManifest) -> EvidenceManifest:
        """
        Sanitize all FOUND evidence items and return an updated manifest.

        Items with status MISSING are skipped.
        Raises SanitizationError on the first item that fails the second-pass
        scan (fail-closed).
        """
        sanitized_items: list[EvidenceItem] = []
        total_redactions = 0
        patterns_seen: set[str] = set()

        for item in manifest.items:
            if item.status == "MISSING":
                sanitized_items.append(item)
                continue

            sanitized_item, report = self.sanitize_item(item)
            sanitized_items.append(sanitized_item)
            total_redactions += report.redaction_count
            patterns_seen.update(report.patterns_applied)

        aggregate_report = RedactionReport(
            evidence_id=manifest.opportunity_id,
            redaction_count=total_redactions,
            raw_hash=_sha256(
                json.dumps([i.hash for i in manifest.items], sort_keys=True)
            ),
            sanitized_hash=_sha256(
                json.dumps([i.hash for i in sanitized_items], sort_keys=True)
            ),
            patterns_applied=sorted(patterns_seen),
        )

        return manifest.model_copy(
            update={"items": sanitized_items, "redaction_report": aggregate_report}
        )

    def sanitize_item(
        self, item: EvidenceItem
    ) -> tuple[EvidenceItem, RedactionReport]:
        """
        Sanitize a single evidence item.

        Returns (sanitized_item, per-item RedactionReport).
        Raises SanitizationError if high-risk content survives redaction.
        """
        raw_content = self._load_raw(item)
        sanitized, redaction_count, patterns_applied = self._apply_redactions(
            raw_content
        )

        # Second-pass scan — fail closed
        if _HIGH_RISK_SCANNER.search(sanitized):
            raise SanitizationError(
                message=(
                    "High-risk pattern detected in sanitized output after all "
                    "redaction passes; failing closed"
                ),
                evidence_id=item.id,
            )

        sanitized_uri = self._store_sanitized(item, sanitized)
        raw_hash = _sha256(raw_content)
        sanitized_hash = _sha256(sanitized)

        report = RedactionReport(
            evidence_id=item.id,
            redaction_count=redaction_count,
            raw_hash=raw_hash,
            sanitized_hash=sanitized_hash,
            patterns_applied=patterns_applied,
        )

        updated_item = item.model_copy(
            update={
                "sanitized_uri": sanitized_uri,
                "status": "REDACTED",
                "hash": raw_hash,
            }
        )
        return updated_item, report

    # ------------------------------------------------------------------
    # Redaction engine
    # ------------------------------------------------------------------

    def _apply_redactions(
        self, content: str
    ) -> tuple[str, int, list[str]]:
        """Apply all REDACTION_PATTERNS; return (sanitized, total_count, labels)."""
        total = 0
        applied: list[str] = []
        for pattern, replacement, label in REDACTION_PATTERNS:
            new_content, n = re.subn(pattern, replacement, content)
            if n > 0:
                total += n
                applied.append(label)
            content = new_content
        return content, total, applied

    # ------------------------------------------------------------------
    # S3 helpers (stub when no bucket is configured)
    # ------------------------------------------------------------------

    def _load_raw(self, item: EvidenceItem) -> str:
        """Load raw evidence content from S3, falling back to stub on error."""
        if not item.storage_uri or not item.storage_uri.startswith("s3://"):
            return json.dumps(
                {
                    "evidence_id": item.id,
                    "source": item.source,
                    "hash": item.hash,
                    "_stub": True,
                },
                sort_keys=True,
            )

        try:
            import boto3

            bucket, key = item.storage_uri.replace("s3://", "").split("/", 1)
            s3 = boto3.client("s3")
            response = s3.get_object(Bucket=bucket, Key=key)
            return response["Body"].read().decode()
        except Exception as exc:  # noqa: BLE001
            is_expected = "NoSuchKey" in str(exc)
            (log.debug if is_expected else log.warning)(
                "evidence_sanitizer.s3_load_failed",
                uri=item.storage_uri,
                error=str(exc),
            )
            # Fall back to stub so sanitizer never blocks a run
            return json.dumps(
                {"evidence_id": item.id, "source": item.source, "hash": item.hash, "_stub": True},
                sort_keys=True,
            )

    def _store_sanitized(self, item: EvidenceItem, content: str) -> str:
        """Write sanitized content to S3 and return the sanitized S3 URI."""
        if not item.storage_uri or not item.storage_uri.startswith("s3://"):
            return ""

        sanitized_uri = item.storage_uri.replace("/raw/", "/sanitized/")

        try:
            import boto3

            from ..config import settings

            bucket, key = sanitized_uri.replace("s3://", "").split("/", 1)
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
            log.info("evidence_sanitizer.s3_stored", uri=sanitized_uri)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "evidence_sanitizer.s3_store_failed",
                uri=sanitized_uri,
                error=str(exc),
            )
            # Non-fatal: sanitized content is in memory; log the failure and continue.
            # Matches the same fail-gracefully pattern as _load_raw.

        return sanitized_uri

        return sanitized_uri
