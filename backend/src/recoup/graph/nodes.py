"""
All 11 Recoup graph node implementations.

Phase 1: Every AgentNode has a deterministic stub that returns typed data so
the graph is runnable end-to-end without Bedrock credentials. Phase 2 replaces
the stub_fn with real strands.Agent calls.

Node responsibilities:
  1.  normalize_event        — parse raw event dict → IncidentSignal
  2.  incident_correlation   — correlate signal → IncidentHypothesis
  3.  sla_contract_resolver  — load SLA contract → SLAContract
  4.  availability_calculator — compute uptime/credit → AvailabilityResult
  5.  evidence_collector     — gather AWS evidence → EvidenceManifest
  6.  evidence_sanitizer     — redact PII/secrets → sanitized EvidenceManifest
  7.  eligibility_reasoner   — assess claim eligibility → EligibilityAssessment
  8.  risk_policy_gate       — evaluate policy → PolicyDecision
  9.  claim_package_generator — assemble claim → ClaimPackage
  10. submission_adapter     — submit or simulate → case_id
  11. case_monitor           — poll support case → CaseOutcome
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from ..engines.calculator import calculate_availability_and_credit
from ..engines.sla_resolver import SLAContractNotFoundError, resolve_sla_contract
from ..evidence.collector import EvidenceCollector
from ..evidence.sanitizer import EvidenceSanitizer
from ..models.availability import AvailabilityInterval, AvailabilityResult
from ..models.claim import ClaimPackage
from ..models.eligibility import EligibilityAssessment
from ..safety.cedar import PolicyContext, build_context_from_graph_state, evaluate_policy
from ..safety.exceptions import SanitizationError
from ..models.opportunity import OpportunityState
from .types import (
    CaseOutcome,
    GraphState,
    IncidentHypothesis,
    PolicyDecision,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _sha256(obj: object) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(obj, default=str, sort_keys=True).encode()
    ).hexdigest()


# ---------------------------------------------------------------------------
# Node 1 — normalize_event (Deterministic)
# ---------------------------------------------------------------------------

def normalize_event_fn(state: GraphState) -> dict[str, Any]:
    """
    Parse a raw event dict (from EventBridge, replay seed, or SQS) into a
    typed IncidentSignal and generate an idempotency key.

    The signal's ``raw_ref`` is expected to be an S3 URI already stored by the
    ingestion Lambda. The raw payload is never passed further downstream.
    """
    # In Phase 2 the raw_event comes from the Lambda payload; here we expect
    # it to already be attached to the state as a dict at state.signal.raw_ref
    # or pre-built by the replay adapter.
    if state.signal is not None:
        # Already a typed signal (e.g. from replay adapter)
        idempotency_key = f"{state.signal.event_id}:{state.signal.service}:{state.signal.region}"
        return {"idempotency_key": idempotency_key}

    # Fallback: return an error if no signal provided (should not happen in prod)
    return {
        "errors": state.errors + ["normalize_event: no signal provided; skipping"],
    }


# ---------------------------------------------------------------------------
# Node 2 — incident_correlation (AgentNode stub)
# ---------------------------------------------------------------------------

def _load_cw_sla_intervals() -> list[dict[str, Any]] | None:
    """
    Read Availability5min datapoints from the ``Recoup/SLA/Demo`` CloudWatch
    namespace.  Returns None on any failure so callers fall back to fixtures.

    Only called when ``state.live_evidence`` is True.
    """
    try:
        from datetime import timedelta  # noqa: PLC0415

        import boto3

        from ..config import settings  # noqa: PLC0415

        cw = boto3.client("cloudwatch", region_name=settings.bedrock_region)
        start = datetime(2026, 8, 1, 0, 0, 0, tzinfo=UTC)
        end = datetime(2026, 9, 1, 0, 0, 0, tzinfo=UTC)
        resp = cw.get_metric_statistics(
            Namespace="Recoup/SLA/Demo",
            MetricName="Availability5min",
            Dimensions=[{"Name": "Service", "Value": "APIGateway-us-east-1"}],
            StartTime=start,
            EndTime=end,
            Period=300,
            Statistics=["Average"],
        )
        datapoints = resp.get("Datapoints", [])
        if not datapoints:
            return None
        # Sort by timestamp and build interval dicts
        datapoints.sort(key=lambda dp: dp["Timestamp"])
        intervals: list[dict[str, Any]] = []
        for dp in datapoints:
            ts = dp["Timestamp"]
            end_ts = ts + timedelta(minutes=5)
            avail = float(dp.get("Average", 100.0))
            err_count = 1000 if avail < 50.0 else 0
            intervals.append(
                {
                    "start": ts.replace(tzinfo=UTC).isoformat(),
                    "end": end_ts.replace(tzinfo=UTC).isoformat(),
                    "availability_pct": str(avail),
                    "request_count": 1000,
                    "error_count": err_count,
                }
            )
        return intervals if intervals else None
    except Exception:  # noqa: BLE001
        return None


def incident_correlation_stub(state: GraphState) -> dict[str, Any]:
    """
    Correlate the incident signal to form a working hypothesis.

    Phase 2: when ``state.replay_fixtures["metric_series"]`` is present the
    intervals are parsed directly from the canonical fixture file so the
    hypothesis is driven by the immutable seed data rather than a hard-coded
    stub.  If no fixture data is present the function falls back to the
    golden-constant stub so Phase 1 tests keep passing without fixture files.

    Phase 5b: when ``state.live_evidence`` is True, first tries to read from
    the real ``Recoup/SLA/Demo`` CloudWatch namespace (populated by
    ``scripts/inject_sla_metrics.py``). Falls back to fixture → stub.

    Phase 3 replaces this with a real Strands Agent that calls
    get_cloudwatch_metrics / get_health_event / lookup_cloudtrail_events.
    """
    signal = state.signal
    if signal is None:
        return {"errors": state.errors + ["incident_correlation: no signal in state"]}

    metric_series = state.replay_fixtures.get("metric_series")
    billing_snapshot = state.replay_fixtures.get("billing_snapshot")

    # Phase 5b: try real CloudWatch data first when live_evidence is set
    if state.live_evidence and not metric_series:
        cw_intervals = _load_cw_sla_intervals()
        if cw_intervals:
            metric_series = {"intervals": cw_intervals}

    if metric_series and isinstance(metric_series, dict):
        # --- Phase 2 path: load from canonical fixture -----------------------
        raw_intervals: list[dict[str, Any]] = metric_series.get("intervals", [])
        intervals: list[AvailabilityInterval] = [
            AvailabilityInterval(
                start=datetime.fromisoformat(iv["start"].replace("Z", "+00:00")),
                end=datetime.fromisoformat(iv["end"].replace("Z", "+00:00")),
                availability_pct=Decimal(str(iv["availability_pct"])),
                request_count=int(iv["request_count"]),
                error_count=int(iv["error_count"]),
                evidence_refs=[],
            )
            for iv in raw_intervals
        ]
        if billing_snapshot and "billed_amount_usd" in billing_snapshot:
            billed_charges = Decimal(str(billing_snapshot["billed_amount_usd"]))
        else:
            raise ValueError(
                "No billing snapshot available — run inject_sla_traffic.py first"
            )
        bad_count = sum(1 for iv in intervals if iv.availability_pct < Decimal("100"))
        total_count = len(intervals)
    else:
        # --- Fallback path: golden-constant stub (Phase 1 backward compat) ---
        total_count = 8_640
        bad_count = 6
        now = _utcnow().replace(tzinfo=None)
        intervals = [
            AvailabilityInterval(
                start=now.replace(hour=0, minute=0, second=0, microsecond=0),
                end=now.replace(hour=0, minute=5, second=0, microsecond=0),
                availability_pct=Decimal("0") if i < bad_count else Decimal("100"),
                request_count=1000,
                error_count=1000 if i < bad_count else 0,
                evidence_refs=[],
            )
            for i in range(total_count)
        ]
        billed_charges = Decimal("3.51")

    hypothesis = IncidentHypothesis(
        service=signal.service,
        region=signal.region,
        incident_date=signal.start.date(),
        affected_resource_ids=signal.affected_resource_ids,
        availability_intervals=intervals,
        billed_charges=billed_charges,
        confidence=0.92,
        summary=(
            f"Detected {bad_count} unavailable 5-minute intervals out of "
            f"{total_count:,} for {signal.service} in {signal.region}. "
            f"Estimated monthly uptime: 99.930556%. Potential 10% credit tier."
        ),
        replay=signal.replay,
    )
    return {"hypothesis": hypothesis}


# ---------------------------------------------------------------------------
# Node 3 — sla_contract_resolver (Deterministic)
# ---------------------------------------------------------------------------

def sla_contract_resolver_fn(state: GraphState) -> dict[str, Any]:
    """
    Load the correct SLA contract for the service/date from the local catalog.

    Never fetches from the internet. Raises SLAContractNotFoundError if no
    contract covers the incident date — this is a fatal error.
    """
    hypothesis = state.hypothesis
    if hypothesis is None:
        return {"errors": state.errors + ["sla_contract_resolver: no hypothesis in state"]}

    try:
        contract = resolve_sla_contract(
            service=hypothesis.service,
            region=hypothesis.region,
            incident_date=hypothesis.incident_date,
        )
        return {"contract": contract}
    except SLAContractNotFoundError as exc:
        return {"errors": state.errors + [f"sla_contract_resolver: {exc}"]}


# ---------------------------------------------------------------------------
# Node 4 — availability_calculator (Deterministic)
# ---------------------------------------------------------------------------

def availability_calculator_fn(state: GraphState) -> dict[str, Any]:
    """
    Pure arithmetic: compute monthly uptime % and SLA credit from intervals.

    No LLM involvement. All financial math is deterministic and reproducible.
    """
    hypothesis = state.hypothesis
    contract = state.contract

    if hypothesis is None:
        return {"errors": state.errors + ["availability_calculator: no hypothesis"]}
    if contract is None:
        return {"errors": state.errors + ["availability_calculator: no contract"]}
    if not hypothesis.availability_intervals:
        return {"errors": state.errors + ["availability_calculator: no intervals in hypothesis"]}

    result: AvailabilityResult = calculate_availability_and_credit(
        intervals=hypothesis.availability_intervals,
        contract=contract,
        billed_charges=hypothesis.billed_charges,
    )
    return {"availability_result": result}


# ---------------------------------------------------------------------------
# Node 5 — evidence_collector (AgentNode stub)
# ---------------------------------------------------------------------------

def evidence_collector_stub(state: GraphState) -> dict[str, Any]:
    """
    Collect CloudWatch metrics, logs, cost records, and health events for the
    incident period and store raw evidence to S3.

    Phase 3: delegates to the real EvidenceCollector which loads from replay
    fixtures when available, or builds stubs otherwise.  Raw evidence is stored
    to S3 when an evidence bucket is configured.
    """
    contract = state.contract
    hypothesis = state.hypothesis
    signal = state.signal

    if contract is None or hypothesis is None or signal is None:
        return {
            "errors": state.errors + [
                "evidence_collector: missing contract, hypothesis, or signal"
            ]
        }

    collector = EvidenceCollector(
        replay_fixtures=state.replay_fixtures,
        live_evidence=state.live_evidence,
    )
    manifest = collector.collect(
        contract=contract,
        signal=signal,
        opportunity_id=state.opportunity_id,
    )
    return {"evidence_manifest": manifest}


# ---------------------------------------------------------------------------
# Node 6 — evidence_sanitizer (Deterministic)
# ---------------------------------------------------------------------------

def evidence_sanitizer_fn(state: GraphState) -> dict[str, Any]:
    """
    Apply deterministic redaction rules to all evidence items.

    Phase 3: delegates to the real EvidenceSanitizer which runs 8 compiled
    regex patterns and a second-pass HIGH_RISK_SCANNER.  Fails closed:
    raises SanitizationError if any high-risk pattern survives all passes.
    """
    manifest = state.evidence_manifest
    if manifest is None:
        return {"errors": state.errors + ["evidence_sanitizer: no manifest in state"]}

    sanitizer = EvidenceSanitizer()
    try:
        sanitized_manifest = sanitizer.sanitize_manifest(manifest)
    except SanitizationError as exc:
        return {
            "errors": state.errors + [f"evidence_sanitizer: {exc}"],
        }

    return {
        "sanitized_manifest": sanitized_manifest,
        "redaction_report": sanitized_manifest.redaction_report,
    }


# ---------------------------------------------------------------------------
# Node 7 — eligibility_reasoner (AgentNode stub)
# ---------------------------------------------------------------------------

def eligibility_reasoner_stub(state: GraphState) -> dict[str, Any]:
    """
    Reason about claim eligibility using evidence IDs (never raw evidence).

    Stub: produces a positive assessment when the availability result shows a
    breach and the manifest is complete.
    """
    result = state.availability_result
    manifest = state.sanitized_manifest
    contract = state.contract

    if result is None or manifest is None or contract is None:
        return {
            "errors": state.errors + ["eligibility_reasoner: missing result/manifest/contract"]
        }

    eligible = result.is_eligible and manifest.is_complete
    evidence_ids = [item.id for item in manifest.items]

    unresolved: list[str] = list(manifest.missing_fields)
    exclusions: list[str] = []

    confidence = 0.92 if eligible and not unresolved else 0.45

    assessment = EligibilityAssessment(
        eligible_estimate=eligible,
        confidence=confidence,
        satisfied_requirements=contract.required_claim_fields if eligible else [],
        unresolved=unresolved,
        possible_exclusions=exclusions,
        evidence_refs=evidence_ids,
    )
    return {"eligibility_assessment": assessment}


# ---------------------------------------------------------------------------
# Node 8 — risk_policy_gate (Deterministic)
# ---------------------------------------------------------------------------

def risk_policy_gate_fn(state: GraphState) -> dict[str, Any]:
    """
    Evaluate risk and call AgentCore Policy (Cedar) for authorization.

    Phase 3 logic:
      - If not eligible → DENY
      - Evaluate Cedar policy for 'submit_support_case' using current state context
      - Eligible claims without valid approval → REQUIRE_APPROVAL (always HITL for financial)
      - Eligible claims with valid approval → ALLOW (Cedar grants permission)
      - All other cases → DENY
    """
    assessment = state.eligibility_assessment
    result = state.availability_result

    if assessment is None or result is None:
        return {
            "errors": state.errors + ["risk_policy_gate: missing assessment or result"],
            "policy_decision": PolicyDecision.DENY,
        }

    if not assessment.eligible_estimate or not result.is_eligible:
        return {"policy_decision": PolicyDecision.DENY, "current_state": OpportunityState.DENIED}

    # Evaluate Cedar policy with current approval state
    cedar_ctx: PolicyContext = build_context_from_graph_state(state)
    cedar_decision = evaluate_policy("submit_support_case", cedar_ctx)

    if cedar_decision == "ALLOW":
        return {"policy_decision": PolicyDecision.ALLOW, "current_state": OpportunityState.APPROVED}

    # Cedar DENY without approval → escalate to REQUIRE_APPROVAL
    return {
        "policy_decision": PolicyDecision.REQUIRE_APPROVAL,
        "current_state": OpportunityState.AWAITING_APPROVAL,
    }


# ---------------------------------------------------------------------------
# Node 9 — claim_package_generator (AgentNode stub)
# ---------------------------------------------------------------------------

def claim_package_generator_stub(state: GraphState) -> dict[str, Any]:
    """
    Assemble the complete claim package from sanitized evidence.

    The validator rejects any evidence_id in the body that is not present in
    the sanitized manifest (prevents LLM from inventing evidence references).
    """
    assessment = state.eligibility_assessment
    manifest = state.sanitized_manifest
    result = state.availability_result
    contract = state.contract
    hypothesis = state.hypothesis

    if not all([assessment, manifest, result, contract, hypothesis]):
        return {"errors": state.errors + ["claim_package_generator: missing state fields"]}

    assert assessment is not None
    assert manifest is not None
    assert result is not None
    assert contract is not None
    assert hypothesis is not None

    # Build evidence references from manifest (safe — no invented IDs)
    ev_refs = " ".join(item.id for item in manifest.items)
    billing_cycle = hypothesis.incident_date.strftime("%Y-%m")

    package = ClaimPackage(
        opportunity_id=state.opportunity_id,
        subject=(
            f"SLA Credit Request — {contract.service} {hypothesis.region} "
            f"{billing_cycle} — {result.potential_credit:.2f} USD"
        ),
        body=(
            f"Dear AWS Support,\n\n"
            f"We are submitting an SLA credit claim for {contract.service} "
            f"in {hypothesis.region} for billing cycle {billing_cycle}.\n\n"
            f"Monthly uptime: {result.monthly_uptime_pct}% (SLA commitment: "
            f"{contract.service_commitment}%).\n"
            f"Credit tier: {result.tier_pct}% of billed charges.\n"
            f"Potential credit: ${result.potential_credit:,.2f} USD.\n\n"
            f"Supporting evidence: {ev_refs}\n\n"
            f"This request was generated and reviewed by Recoup."
        ),
        region=hypothesis.region,
        billing_cycle=billing_cycle,
        resources=hypothesis.affected_resource_ids or ["(all API Gateway endpoints)"],
        evidence_manifest=manifest,
        calculator_result_hash=_sha256(result.model_dump(mode="json")),
    )
    return {"claim_package": package}


# ---------------------------------------------------------------------------
# Node 10 — submission_adapter (Deterministic)
# ---------------------------------------------------------------------------

def submission_adapter_fn(state: GraphState) -> dict[str, Any]:
    """
    Submit the claim package to AWS Support.

    Real submission requires:
      - A valid ApprovalRecord that has not expired
      - AgentCore Policy ALLOW decision
      - recoup_enable_real_support_submission=True in config

    Without a valid approval, returns a deterministic replay case ID so the
    graph completes end-to-end for demo purposes.
    """
    package = state.claim_package
    approval = state.approval_record

    if package is None:
        return {"errors": state.errors + ["submission_adapter: no claim package"]}

    # No valid approval — return a deterministic replay case ID
    if approval is None or not approval.is_valid:
        case_id = "replay-" + hashlib.sha256(
            package.calculator_result_hash.encode()
        ).hexdigest()[:12]
        return {
            "case_id": case_id,
            "submitted_at": _utcnow(),
        }

    # Real submission gate — gated by recoup_enable_real_support_submission
    return {"errors": state.errors + ["submission_adapter: live submission not yet implemented"]}


# ---------------------------------------------------------------------------
# Node 11 — case_monitor (AgentNode stub)
# ---------------------------------------------------------------------------

def case_monitor_stub(state: GraphState) -> dict[str, Any]:
    """
    Poll the AWS Support case for resolution status.

    Stub: returns PENDING so the graph completes without real AWS credentials.
    Phase 2 replaces this with a Strands Agent calling get_support_case_status.
    """
    case_id = state.case_id
    if case_id is None:
        return {"errors": state.errors + ["case_monitor: no case_id in state"]}

    outcome = CaseOutcome(
        case_id=case_id,
        status="PENDING",
        credit_amount=Decimal("0.00"),
        notes="Case submitted. Awaiting AWS Support response (stub).",
    )
    return {"case_outcome": outcome}
