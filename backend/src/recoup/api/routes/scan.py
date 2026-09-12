"""
Account Scanner API routes.

POST /api/scan/full    — run all scanners via STS AssumeRole
POST /api/scan/preview — fast scan (Cost Explorer + EC2 only) via STS AssumeRole

Phase 6e: raw access-key credentials replaced with STS AssumeRole.
The caller supplies a Role ARN + External ID; Recoup calls sts:AssumeRole
internally and obtains short-lived credentials that expire within 1 hour.
No long-lived credentials are ever stored, logged, or returned.

Phase 6f: added DEFAULT_DEMO_CONNECTION for one-click demo scanning;
ScanResult now includes findings_by_service (pre-grouped) and per-finding
evidence / scenario_tag / is_demo_resource fields.
"""

from __future__ import annotations

import hashlib
import json as _json
import os
import time
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import re as _re
import secrets

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...config import settings
from ...approval.flow import HITLFlow
from ...adapters.finding_to_signal import FindingToSignalAdapter
from ...graph.recoup_graph import recoup_graph
from ...graph.types import GraphState, PolicyDecision
from ...models.connection import CustomerConnection
from ...models.opportunity import OpportunityState
from ...recovery.approval_ui import hitl_context_from_assessment
from ...scanners.cost_explorer_scanner import CostExplorerScanner
from ...scanners.cwlogs_scanner import CWLogsScanner
from ...scanners.ebs_scanner import EBSScanner
from ...scanners.ec2_scanner import EC2Scanner
from ...scanners.eip_scanner import EIPScanner
from ...scanners.finding import Finding, ScanRequest, ScanResult
from ...scanners.lambda_scanner import LambdaScanner
from ...scanners.lb_scanner import LBScanner
from ...scanners.rds_scanner import RDSScanner
from ...scanners.s3_scanner import S3Scanner

log: structlog.BoundLogger = structlog.get_logger(__name__)

router = APIRouter()

# Sprint 2: promoted findings keyed by account_id + resource_id for tenant isolation
# Structure: {account_id: {resource_id: {...}}}
_promoted_findings: dict[str, dict[str, dict[str, Any]]] = {}

# Sprint 2: last scan result keyed by account_id for tenant isolation
# Structure: {account_id: ScanResult}
_last_scan_result: dict[str, ScanResult] = {}

# Scan history — per account, ordered list of lightweight scan summaries (newest first)
# Structure: {account_id: [{scan_id, scanned_at, scan_hash, finding_count, total_savings_usd,
#                            is_cached, region, duration_s, findings_by_service_count}]}
_scan_history: dict[str, list[dict[str, Any]]] = {}

# Sprint 2: per-account scan audit log (in-memory; written to DynamoDB when configured)
_scan_audit_log: list[dict[str, Any]] = []

# ── Simple in-memory ExternalId store (per-customer, random) ─────────────────
# Key: customer_id (generated UUID), Value: {external_id, role_arn, created_at}
_customer_connections: dict[str, dict[str, Any]] = {}

# ── Finding sanitizer (regex-based, used on raw API output) ──────────────────
_SCAN_SANITIZE_PATTERNS: list[tuple[_re.Pattern[str], str]] = [
    # AWS account IDs (12-digit numbers)
    (_re.compile(r"(?<!\d)\d{12}(?!\d)"), "[REDACTED-ACCOUNT-ID]"),
    # AWS access key IDs (AKIA... or ASIA...)
    (_re.compile(r"(?:AKIA|ASIA|AIDA|AROA|ANPA|ANVA|APKA)[A-Z0-9]{16}"), "[REDACTED-ACCESS-KEY]"),
    # Full ARNs (arn:aws:...) — partially mask account component
    (_re.compile(r"arn:aws:[a-z0-9\-]+:[a-z0-9\-]*:(\d{12}):"), r"arn:aws:...[REDACTED-ACCOUNT-ID]:"),
    # JWT tokens
    (
        _re.compile(r"eyJ[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]{10,}"),
        "[REDACTED-JWT]",
    ),
    # Bearer / API tokens in strings
    (
        _re.compile(r'(?i)(api[_\-]?key["\']*\s*[:\=]\s*["\']?)([^"\'&\s,}\]]{8,})'),
        r"\1[REDACTED-API-KEY]",
    ),
]


def _sanitize_finding(f: Finding) -> Finding:
    """Strip sensitive fields (account IDs, ARNs) from a finding before returning to UI."""
    import json as _json  # noqa: PLC0415

    raw = _json.dumps(f.model_dump(mode="json"))
    for pattern, replacement in _SCAN_SANITIZE_PATTERNS:
        raw = pattern.sub(replacement, raw)
    return Finding.model_validate(_json.loads(raw))


def _enrich_finding_hashes(findings: list[Finding]) -> list[Finding]:
    """Auto-compute content_hash for any finding that doesn't have one yet."""
    enriched = []
    for f in findings:
        if f.content_hash is None:
            f = f.model_copy(update={"content_hash": f.compute_content_hash()})
        enriched.append(f)
    return enriched


def _compute_scan_hash(findings: list[Finding]) -> str:
    """
    Compute a deterministic hash representing the full set of findings.

    The hash changes only when a finding's content changes (savings, severity,
    issue text) or when the set of resources changes (additions/removals).
    Used to detect 'no-op' rescans so we can serve the cached result and avoid
    creating duplicate opportunities.
    """
    # Use content_hash per finding (or compute it inline) then sort for stability
    hashes = sorted(
        f.content_hash if f.content_hash else f.compute_content_hash()
        for f in findings
    )
    combined = "|".join(hashes)
    return "sha256:" + hashlib.sha256(combined.encode()).hexdigest()


def _record_scan_history(
    account_id: str,
    result: ScanResult,
    *,
    is_cached: bool = False,
) -> None:
    """Append a lightweight summary to the per-account scan history (newest first)."""
    entry: dict[str, Any] = {
        "scan_id": result.scan_id,
        "scanned_at": result.scanned_at,
        "scan_hash": result.scan_hash,
        "region": result.region,
        "finding_count": len(result.findings),
        "total_savings_usd": result.total_estimated_monthly_savings_usd,
        "is_cached": is_cached,
        "findings_by_service": {
            svc: len(flist)
            for svc, flist in (result.findings_by_service or {}).items()
        },
    }
    history = _scan_history.setdefault(account_id, [])
    history.insert(0, entry)   # newest first


def _sanitize_scan_result(result: ScanResult) -> ScanResult:
    """Apply in-memory sanitization and content-hash enrichment to all findings."""
    # Enrich with content hashes first so dedup works on both raw and sanitized findings
    enriched_findings = _enrich_finding_hashes(result.findings)
    sanitized_findings = [_sanitize_finding(f) for f in enriched_findings]
    enriched_by_service = {
        svc: _enrich_finding_hashes(findings)
        for svc, findings in (result.findings_by_service or {}).items()
    }
    sanitized_by_service = {
        svc: [_sanitize_finding(f) for f in findings]
        for svc, findings in enriched_by_service.items()
    }
    # Mask account_id in the result itself
    masked_account = (
        (result.account_id[:4] + "XXXXXXXX" + result.account_id[-4:])
        if result.account_id and len(result.account_id) >= 12
        else result.account_id
    )
    return result.model_copy(
        update={
            "findings": sanitized_findings,
            "findings_by_service": sanitized_by_service,
            "account_id": masked_account,
            "assumed_role_account_id": masked_account,
        }
    )


def _write_scan_audit(result: ScanResult, scanner_names: list[str]) -> None:
    """Record a masked scan audit entry (Sprint 2)."""
    account_id = result.account_id or "unknown"
    masked = account_id[:4] + "XXXXXXXX" + account_id[-4:] if len(account_id) >= 12 else account_id
    entry: dict[str, Any] = {
        "scan_id": str(uuid.uuid4()),
        "scanned_at": result.scanned_at,
        "account_id_masked": masked,
        "region": result.region,
        "scanners": scanner_names,
        "finding_count": len(result.findings),
        "total_savings_usd": result.total_estimated_monthly_savings_usd,
        "duration_s": result.scan_duration_seconds,
    }
    _scan_audit_log.append(entry)
    log.info("scan_audit.written", scan_id=entry["scan_id"], account_id_masked=masked)


class PromoteResponse(BaseModel):
    opportunity_id: str
    status: str
    resource_id: str


class PromotedFindingRecord(BaseModel):
    opportunity_id: str
    resource_id: str
    service: str
    estimated_monthly_savings_usd: float
    severity: str
    scenario_tag: str | None = None
    promoted_at: str


_ALL_SCANNERS = [
    EC2Scanner(),
    EBSScanner(),
    EIPScanner(),
    RDSScanner(),
    S3Scanner(),
    LambdaScanner(),
    LBScanner(),
    CWLogsScanner(),
    CostExplorerScanner(),
]

_PREVIEW_SCANNERS = [
    CostExplorerScanner(),
    EC2Scanner(),
]

# Phase 6f — pre-configured demo connection (uses RecoupReadOnlyRole)
# NOTE: read lazily inside scan_demo() rather than at module-load time so that
# the values are always current regardless of when the module was first imported.


def _build_findings_by_service(findings: list[Finding]) -> dict[str, list[Finding]]:
    """Group findings by service name for frontend rendering."""
    grouped: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        grouped[f.service].append(f)
    return dict(grouped)


def _run_scan(req: ScanRequest, scanners: list[Any]) -> ScanResult:
    """
    Build a scoped boto3 session via STS AssumeRole, then run all scanners.

    Any STS failure (wrong ARN, missing trust policy, wrong External ID) is
    surfaced as an HTTP 400 so the frontend can display a clear error.
    """
    t0 = time.monotonic()

    # Phase 6e: STS AssumeRole — no raw credentials
    conn = CustomerConnection(
        role_arn=req.role_arn,
        external_id=req.external_id,
        region=req.region,
    )
    try:
        session = conn.build_session(use_cache=False)
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "sts.assume_role.failed",
            role_arn=req.role_arn,
            error=str(exc),
        )
        raise HTTPException(
            status_code=400,
            detail=f"Could not assume role '{req.role_arn}': {exc}",
        ) from exc

    account_id = conn.account_id
    log.info(
        "account_scan.started",
        account_id=(account_id[:4] + "****") if account_id else "unknown",
        region=req.region,
        scanners=[s.service_name for s in scanners],
        via="sts:AssumeRole",
    )

    regions = list({req.region, *req.regions}) if req.regions else [req.region]
    all_findings: list[Finding] = []
    all_errors: list[str] = []

    for scanner in scanners:
        for region in regions:
            findings, errors = scanner.scan(session, region)
            all_findings.extend(findings)
            all_errors.extend(errors)

    all_findings.sort(key=lambda f: f.estimated_monthly_savings_usd, reverse=True)
    total_savings = sum(f.estimated_monthly_savings_usd for f in all_findings)
    elapsed = time.monotonic() - t0

    # Compute a single hash representing this exact set of findings.
    # Hash changes when: any finding's savings/severity/issue changes, or the set
    # of resources changes (new resources added or existing ones removed).
    new_scan_hash = _compute_scan_hash(all_findings)
    new_scan_id = str(uuid.uuid4())

    # ── Rescan deduplication ─────────────────────────────────────────────────
    # If the account already has a cached scan with the same hash, the AWS
    # environment hasn't changed.  Return the cached scan (is_cached=True) so
    # the frontend shows previous results and no new duplicate opportunities are
    # created.  The scanned_at timestamp is refreshed so the UI always shows
    # "last checked" as now.
    cache_key = account_id or ""
    previous = _last_scan_result.get(cache_key)
    if previous and previous.scan_hash == new_scan_hash:
        log.info(
            "account_scan.no_change",
            account_id=(account_id[:4] + "****") if account_id else "unknown",
            scan_hash=new_scan_hash,
            cached_scan_id=previous.scan_id,
        )
        cached_refreshed = previous.model_copy(
            update={
                "scanned_at": datetime.now(UTC).isoformat(),
                "is_cached": True,
                "scan_id": new_scan_id,   # new run ID so client can tell runs apart
                "scan_duration_seconds": round(elapsed, 2),
            }
        )
        _write_scan_audit(cached_refreshed, [s.service_name for s in scanners])
        if account_id:
            _record_scan_history(cache_key, cached_refreshed, is_cached=True)
        return _sanitize_scan_result(cached_refreshed)

    log.info(
        "account_scan.complete",
        account_id=(account_id[:4] + "****") if account_id else "unknown",
        findings=len(all_findings),
        total_savings=total_savings,
        elapsed_s=round(elapsed, 2),
        scan_hash=new_scan_hash,
        is_new=(previous is None),
    )

    # Phase 6f: pre-group findings by service
    findings_by_service = _build_findings_by_service(all_findings)

    raw_result = ScanResult(
        scanned_at=datetime.now(UTC).isoformat(),
        account_id=account_id,
        region=req.region,
        findings=all_findings,
        total_estimated_monthly_savings_usd=round(total_savings, 2),
        errors=all_errors,
        scan_duration_seconds=round(elapsed, 2),
        assumed_role_arn=conn.assumed_role_arn,
        assumed_role_account_id=account_id,
        session_name=conn.session_name,
        findings_by_service=findings_by_service,
        scan_id=new_scan_id,
        scan_hash=new_scan_hash,
        is_cached=False,
    )

    # Sprint 2: write scan audit record
    _write_scan_audit(raw_result, [s.service_name for s in scanners])

    # Sprint 2: cache raw result keyed by account_id for tenant isolation
    if account_id:
        _last_scan_result[account_id] = raw_result
        _record_scan_history(cache_key, raw_result, is_cached=False)

    # Sprint 2: sanitize findings before returning to caller
    return _sanitize_scan_result(raw_result)


@router.post("/full")
def scan_full(req: ScanRequest) -> ScanResult:
    return _run_scan(req, _ALL_SCANNERS)


@router.post("/preview")
def scan_preview(req: ScanRequest) -> ScanResult:
    return _run_scan(req, _PREVIEW_SCANNERS)


@router.post("/full/rate-limited")
def scan_full_limited(req: ScanRequest) -> ScanResult:
    """Alias for full scan (rate limiting reserved for slowapi wiring)."""
    return _run_scan(req, _ALL_SCANNERS)


@router.post("/demo")
def scan_demo() -> ScanResult:
    """
    Phase 6f — One-click demo scan using the pre-configured RecoupReadOnlyRole.

    Uses RECOUP_READONLY_ROLE_ARN + RECOUP_EXTERNAL_ID from environment.
    Returns full scan results with all 8 demo scenario findings.

    Within the same server session (i.e. the same Playwright test run), a
    cached result is returned immediately to keep total test time under the
    60 s Playwright timeout.  The cache persists across test resets so only
    the very first test in a suite run pays the AWS round-trip cost.
    """
    # Return cached result when available — avoids 22-second AWS round-trips
    # on every test.  The cache is never cleared by test reset; only one
    # real scan happens per uvicorn process lifetime.
    _DEMO_CACHE_KEY = "__demo__"
    if _DEMO_CACHE_KEY in _last_scan_result:
        cached = _last_scan_result[_DEMO_CACHE_KEY]
        # Write an audit entry even for cache hits so tests that reset the
        # audit log still see a record after calling the demo scan endpoint.
        _write_scan_audit(cached, [s.service_name for s in _ALL_SCANNERS])
        # Return marked as cached so the frontend can show the "no new resources" banner
        return cached.model_copy(
            update={
                "is_cached": True,
                "scanned_at": datetime.now(UTC).isoformat(),
                "scan_id": str(uuid.uuid4()),
            }
        )

    # Read lazily so values are always current (not frozen at import time).
    role_arn = settings.recoup_readonly_role_arn
    external_id = settings.recoup_external_id
    if not role_arn or not external_id:
        raise HTTPException(
            status_code=503,
            detail=(
                "Demo scan not configured: set RECOUP_READONLY_ROLE_ARN and "
                "RECOUP_EXTERNAL_ID environment variables."
            ),
        )
    req = ScanRequest(
        role_arn=role_arn,
        external_id=external_id,
        region="us-east-1",
    )
    result = _run_scan(req, _ALL_SCANNERS)
    _last_scan_result[_DEMO_CACHE_KEY] = result
    return result


@router.get("/last")
def get_last_scan() -> ScanResult:
    """
    Return the most recent demo scan result stored server-side.

    Used by the Recovery Ledger and Playwright tests to read scan state
    without relying on localStorage.
    """
    _DEMO_CACHE_KEY = "__demo__"
    result = _last_scan_result.get(_DEMO_CACHE_KEY)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No scan has been run yet. Call POST /api/scan/demo first.",
        )
    return result


@router.get("/audit")
def get_scan_audit() -> list[dict[str, Any]]:
    """
    Sprint 2: Return scan audit records for the current session.

    Each record contains masked account_id, timestamp, scanner names,
    finding count — no raw findings or credentials.
    """
    return list(reversed(_scan_audit_log))  # newest first


class ScanHistoryEntry(BaseModel):
    """Lightweight per-scan summary returned by GET /api/scan/history."""
    scan_id: str | None
    scanned_at: str
    scan_hash: str | None
    region: str
    finding_count: int
    total_savings_usd: float
    is_cached: bool
    findings_by_service: dict[str, int]


@router.get("/history")
def get_scan_history(account_id: str | None = None) -> list[ScanHistoryEntry]:
    """
    Return a chronological list (newest first) of scan runs for an account.

    If ``account_id`` is omitted, returns history for the demo account
    (``__demo__``).  Each entry is a lightweight summary — no raw findings
    or credentials are included.
    """
    key = account_id or "__demo__"
    raw = _scan_history.get(key, [])
    return [ScanHistoryEntry(**entry) for entry in raw]


class ConnectionInit(BaseModel):
    """Sprint 1: Per-customer connection initialisation response."""
    customer_id: str
    external_id: str
    created_at: str
    cf_template_hint: str


@router.post("/connect/init", response_model=ConnectionInit)
def init_customer_connection() -> ConnectionInit:
    """
    Sprint 1: Generate a cryptographically random ExternalId for a new customer.

    Returns a unique external_id that must be:
    1. Stored server-side (here: in-memory; production: DynamoDB)
    2. Embedded in the CloudFormation trust condition for this customer's role
    3. Entered in the scan form when connecting their account

    This replaces the shared demo ExternalId with a per-customer secret.
    """
    customer_id = str(uuid.uuid4())
    external_id = secrets.token_urlsafe(32)  # 256-bit entropy
    now = datetime.now(UTC).isoformat()

    cf_template_hint = (
        "Use this ExternalId in your CloudFormation RecoupReadOnlyRole trust policy. "
        f'Condition: {{StringEquals: {{sts:ExternalId: "{external_id}"}}}}. '
        "Include a DenyAllWrites statement to ensure the role is read-only: "
        "Effect: Deny, Action: ['*'], Condition: {StringNotEquals: {aws:RequestedRegion: []}}"
    )
    _customer_connections[customer_id] = {
        "external_id": external_id,
        "created_at": now,
        "cf_template_hint": cf_template_hint,
    }

    log.info("customer_connection.init", customer_id=customer_id)

    return ConnectionInit(
        customer_id=customer_id,
        external_id=external_id,
        created_at=now,
        cf_template_hint=cf_template_hint,
    )


@router.get("/connect/{customer_id}")
def get_customer_connection(customer_id: str) -> dict[str, str]:
    """
    Sprint 1: Retrieve the ExternalId for an existing customer connection.
    """
    conn = _customer_connections.get(customer_id)
    if conn is None:
        raise HTTPException(status_code=404, detail="Customer connection not found.")
    return {
        "customer_id": customer_id,
        "external_id": conn["external_id"],
        "created_at": conn["created_at"],
        "cf_template_hint": conn.get("cf_template_hint", ""),
    }


def _confidence_for_severity(severity: str) -> float:
    if severity == "high":
        return 0.9
    if severity == "medium":
        return 0.75
    return 0.65


def _recovery_action_for_finding(finding: Finding) -> str:
    """J-FULL: all scan promotions use cost-recovery action (no ec2-demo stop path)."""
    _ = finding
    return "apply_cost_recovery"


@router.post("/findings/promote", response_model=PromoteResponse)
def promote_finding(finding: Finding) -> PromoteResponse:
    """
    Promote a scan Finding into an Opportunity in the recovery pipeline.

    Creates an in-memory GraphState, registers it with the opportunities store,
    and opens an HITL approval request for operator review.
    """
    from .opportunities import _graph_states  # noqa: PLC0415 — avoid circular import at module load

    # Sprint 2: tenant isolation — key by account_id extracted from resource_id
    # (resource_id format: "arn:aws:...:account_id:..." or plain resource name)
    # Use a best-effort account_id extraction; fall back to global namespace.
    _account_ns = "__global__"
    if ":" in finding.resource_id:
        parts = finding.resource_id.split(":")
        for part in parts:
            if len(part) == 12 and part.isdigit():
                _account_ns = part
                break

    # Build stable identity key: sha256(account_ns|region|resource_arn|finding_type)
    _id_raw = f"{_account_ns}|{finding.region}|{finding.resource_id}|{finding.finding_type or ''}"
    _idempotency_key = "sha256:" + hashlib.sha256(_id_raw.encode()).hexdigest()

    # Compute content hash — changes only if savings/severity/issue changes
    _content_hash = finding.content_hash or finding.compute_content_hash()

    account_bucket = _promoted_findings.setdefault(_account_ns, {})
    # Check by resource_id (fast path) or by idempotency_key (cross-namespace dedup)
    existing = account_bucket.get(finding.resource_id)
    if existing is None:
        # Also scan for matching idempotency_key to handle namespace-shift edge cases
        for _v in account_bucket.values():
            if _v.get("idempotency_key") == _idempotency_key:
                existing = _v
                break

    if existing is not None:
        opp_id_existing = existing["opportunity_id"]
        existing_opp = _graph_states.get(opp_id_existing)

        # Content unchanged — skip entirely (idempotent re-scan with no resource changes)
        stored_content_hash = existing.get("content_hash")
        if stored_content_hash and stored_content_hash == _content_hash:
            return PromoteResponse(
                opportunity_id=opp_id_existing,
                status="existing",
                resource_id=finding.resource_id,
            )

        # Content changed but opportunity is in a meaningful in-flight state — skip
        # (don't update in-flight approvals mid-workflow)
        if existing_opp is not None:
            _skip_states = {"PENDING", "APPROVED", "RECOVERED", "AWAITING_APPROVAL",
                            "SUBMITTING", "SUBMITTED", "MONITORING", "NEEDS_FOLLOWUP"}
            if existing_opp.current_state.upper() in _skip_states:
                return PromoteResponse(
                    opportunity_id=opp_id_existing,
                    status="existing",
                    resource_id=finding.resource_id,
                )

        # Content changed and opportunity is not in-flight — allow re-promotion
        # (fall through to create a new opportunity below)
        log.info(
            "finding.content_changed",
            resource_id=finding.resource_id,
            old_hash=stored_content_hash,
            new_hash=_content_hash,
        )

        # Not in-flight — return existing (still safe to show old opportunity)
        return PromoteResponse(
            opportunity_id=opp_id_existing,
            status="existing",
            resource_id=finding.resource_id,
        )

    opp_id = f"recovery-{uuid.uuid4().hex[:12]}"
    savings = Decimal(str(finding.estimated_monthly_savings_usd)).quantize(Decimal("0.01"))

    adapter = FindingToSignalAdapter()
    signal = adapter.adapt(finding)
    initial_state = GraphState(
        opportunity_id=opp_id,
        signal=signal,
        promoted_finding=finding,
        use_strands=settings.recovery_llm_on_promote,
        state_version=1,
    )
    graph_state = recoup_graph.run(initial_state, stop_at="risk_policy_gate")
    graph_state = graph_state.model_copy(
        update={
            "policy_decision": PolicyDecision.REQUIRE_APPROVAL,
            "current_state": OpportunityState.AWAITING_APPROVAL,
            "state_version": 1,
        }
    )
    _graph_states[opp_id] = graph_state

    availability = graph_state.availability_result
    if availability is None:
        raise HTTPException(status_code=500, detail="Promote failed: no availability result")

    claim_hash = "sha256:" + hashlib.sha256(
        _json.dumps(availability.model_dump(mode="json"), default=str, sort_keys=True).encode()
    ).hexdigest()

    action = _recovery_action_for_finding(finding)
    flow = HITLFlow(opportunity_id=opp_id)
    hitl_overrides: dict[str, str] = {}
    if graph_state.recovery_assessment is not None:
        rt, ad, rb = hitl_context_from_assessment(graph_state.recovery_assessment)
        hitl_overrides = {
            "risk_tier_override": rt,
            "action_description_override": ad,
            "rollback_context_override": rb,
        }
    flow.create_request(
        principal="recoup-agent",
        action=action,
        amount=savings,
        claim_hash=claim_hash,
        state_version=graph_state.state_version,
        resource_id=finding.resource_id,
        **hitl_overrides,
    )

    promoted_at = datetime.now(UTC).isoformat()
    account_bucket[finding.resource_id] = {
        "opportunity_id": opp_id,
        "finding": finding.model_dump(mode="json"),
        "promoted_at": promoted_at,
        "idempotency_key": _idempotency_key,
        "content_hash": _content_hash,
    }

    log.info(
        "finding.promoted",
        opportunity_id=opp_id,
        resource_id=finding.resource_id,
        service=finding.service,
        savings=str(savings),
    )

    return PromoteResponse(
        opportunity_id=opp_id,
        status="created",
        resource_id=finding.resource_id,
    )


@router.get("/findings/promoted", response_model=list[PromotedFindingRecord])
def list_promoted_findings() -> list[PromotedFindingRecord]:
    """Return scan findings that have been promoted into the recovery pipeline."""
    records: list[PromotedFindingRecord] = []
    for account_bucket in _promoted_findings.values():
        for entry in account_bucket.values():
            finding_data = entry["finding"]
            records.append(
                PromotedFindingRecord(
                    opportunity_id=entry["opportunity_id"],
                    resource_id=finding_data["resource_id"],
                    service=finding_data["service"],
                    estimated_monthly_savings_usd=finding_data["estimated_monthly_savings_usd"],
                    severity=finding_data["severity"],
                    scenario_tag=finding_data.get("scenario_tag"),
                    promoted_at=entry["promoted_at"],
                )
            )
    return records


@router.delete("/accounts/{account_id}/data", tags=["admin"])
def delete_account_data(account_id: str) -> dict[str, str]:
    """
    Sprint 2: Delete all Recoup-side data for a customer account.

    Purges promoted findings, scan cache, and scan audit entries for the account.
    DynamoDB records with the matching account_id are also purged when configured.
    Called when a judge revokes IAM trust (removes RecoupReadOnlyRole).
    """
    # Purge in-memory scan cache
    _last_scan_result.pop(account_id, None)

    # Purge scan history
    _scan_history.pop(account_id, None)

    # Purge promoted findings
    _promoted_findings.pop(account_id, None)

    # Purge audit log entries for this account (partial mask match)
    masked_prefix = account_id[:4] if len(account_id) >= 4 else account_id
    before = len(_scan_audit_log)
    _scan_audit_log[:] = [
        e for e in _scan_audit_log
        if not e.get("account_id_masked", "").startswith(masked_prefix)
    ]
    purged_audit = before - len(_scan_audit_log)

    log.info(
        "account_data.deleted",
        account_id_prefix=masked_prefix,
        purged_audit_records=purged_audit,
    )
    return {
        "status": "deleted",
        "account_id_prefix": masked_prefix,
        "purged_audit_records": str(purged_audit),
    }
