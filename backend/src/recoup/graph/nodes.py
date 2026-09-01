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
import uuid
from datetime import datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
from decimal import Decimal

from ..engines.calculator import calculate_availability_and_credit
from ..engines.sla_resolver import SLAContractNotFoundError, resolve_sla_contract
from ..models.availability import AvailabilityInterval, AvailabilityResult
from ..models.claim import ClaimPackage
from ..models.eligibility import EligibilityAssessment
from ..models.evidence import EvidenceManifest, RedactionReport
from ..models.signal import IncidentSignal
from .types import (
    CaseOutcome,
    GraphState,
    IncidentHypothesis,
    PolicyDecision,
)


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

def normalize_event_fn(state: GraphState) -> dict:
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

def incident_correlation_stub(state: GraphState) -> dict:
    """
    Correlate the incident signal to form a working hypothesis.

    Stub: derives a deterministic hypothesis from the signal so Phase 1 tests
    pass without Bedrock. Phase 2 replaces this with a real Strands Agent that
    calls get_cloudwatch_metrics / get_health_event / lookup_cloudtrail_events.
    """
    signal = state.signal
    if signal is None:
        return {"errors": state.errors + ["incident_correlation: no signal in state"]}

    # Build a plausible stub hypothesis — 6 bad intervals out of 8,640 →
    # 99.9306% uptime → 10% credit tier (matches the golden test spec)
    total_intervals = 8_640  # 31-day month ÷ 5 min
    bad_intervals = 6
    now = _utcnow().replace(tzinfo=None)

    intervals: list[AvailabilityInterval] = []
    for i in range(total_intervals):
        is_bad = i < bad_intervals
        intervals.append(
            AvailabilityInterval(
                start=now.replace(hour=0, minute=0, second=0, microsecond=0),
                end=now.replace(hour=0, minute=5, second=0, microsecond=0),
                availability_pct=Decimal("0") if is_bad else Decimal("100"),
                request_count=1000,
                error_count=1000 if is_bad else 0,
                evidence_refs=[],
            )
        )

    hypothesis = IncidentHypothesis(
        service=signal.service,
        region=signal.region,
        incident_date=signal.start.date(),
        affected_resource_ids=signal.affected_resource_ids,
        availability_intervals=intervals,
        billed_charges=Decimal("18400.00"),
        confidence=0.92,
        summary=(
            f"Detected {bad_intervals} unavailable 5-minute intervals for "
            f"{signal.service} in {signal.region}. "
            f"Estimated monthly uptime: 99.9306%. Potential 10% credit tier."
        ),
        replay=signal.replay,
    )
    return {"hypothesis": hypothesis}


# ---------------------------------------------------------------------------
# Node 3 — sla_contract_resolver (Deterministic)
# ---------------------------------------------------------------------------

def sla_contract_resolver_fn(state: GraphState) -> dict:
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

def availability_calculator_fn(state: GraphState) -> dict:
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

def evidence_collector_stub(state: GraphState) -> dict:
    """
    Collect CloudWatch metrics, logs, cost records, and health events for the
    incident period and store raw evidence to S3.

    Stub: builds a minimal manifest with the required fields so downstream
    nodes have valid evidence IDs to reference.
    """
    contract = state.contract
    hypothesis = state.hypothesis

    if contract is None or hypothesis is None:
        return {"errors": state.errors + ["evidence_collector: missing contract or hypothesis"]}

    opp_id = state.opportunity_id
    items = []
    for field_name, ev_type in [
        ("request_logs", "log"),
        ("error_logs", "log"),
        ("billing_record", "billing_record"),
    ]:
        ev_id = f"ev-{hashlib.sha256(f'{opp_id}:{field_name}'.encode()).hexdigest()[:8]}"
        from ..models.evidence import EvidenceItem
        items.append(
            EvidenceItem(
                id=ev_id,
                type=ev_type,  # type: ignore[arg-type]
                source=f"stub:{field_name}",
                timestamp_range=(hypothesis.incident_date, hypothesis.incident_date),  # type: ignore[arg-type]
                storage_uri=f"s3://recoup-evidence/{opp_id}/{field_name}.json",
                sanitized_uri=None,
                hash=_sha256({"opp_id": opp_id, "field": field_name}),
                sensitivity="MEDIUM",
                status="FOUND",
            )
        )

    manifest = EvidenceManifest(
        opportunity_id=opp_id,
        items=items,
        missing_fields=[
            f for f in contract.required_claim_fields
            if f not in {"api_id", "region", "billing_cycle", "request_logs", "error_logs", "billing_record"}
        ],
        redaction_report=RedactionReport(evidence_id=opp_id),
    )
    return {"evidence_manifest": manifest}


# ---------------------------------------------------------------------------
# Node 6 — evidence_sanitizer (Deterministic)
# ---------------------------------------------------------------------------

def evidence_sanitizer_fn(state: GraphState) -> dict:
    """
    Apply deterministic redaction rules to all evidence items.

    Fails closed: raises SanitizationError if a HIGH_RISK pattern remains
    after redaction. In Phase 1 the stub just copies the manifest and produces
    a redaction report.
    """
    manifest = state.evidence_manifest
    if manifest is None:
        return {"errors": state.errors + ["evidence_sanitizer: no manifest in state"]}

    # Build sanitized copies (Phase 1: no actual redaction, just record the step)
    from ..models.evidence import EvidenceItem
    sanitized_items = []
    for item in manifest.items:
        sanitized_uri = item.storage_uri.replace(
            "recoup-evidence/", "recoup-evidence-sanitized/"
        )
        sanitized_items.append(
            item.model_copy(update={"sanitized_uri": sanitized_uri, "status": "FOUND"})
        )

    report = RedactionReport(
        evidence_id=manifest.opportunity_id,
        redaction_count=0,
        raw_hash=_sha256([i.hash for i in manifest.items]),
        sanitized_hash=_sha256([i.hash for i in sanitized_items]),
        patterns_applied=["account_id", "ip_address", "auth_token"],
    )

    sanitized_manifest = manifest.model_copy(
        update={"items": sanitized_items, "redaction_report": report}
    )
    return {"sanitized_manifest": sanitized_manifest, "redaction_report": report}


# ---------------------------------------------------------------------------
# Node 7 — eligibility_reasoner (AgentNode stub)
# ---------------------------------------------------------------------------

def eligibility_reasoner_stub(state: GraphState) -> dict:
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

def risk_policy_gate_fn(state: GraphState) -> dict:
    """
    Evaluate risk and call AgentCore Policy (Cedar) for authorization.

    Rules:
      - If not eligible → DENY
      - If credit > $0 and confidence ≥ 0.8 → REQUIRE_APPROVAL (always HITL for financial)
      - Otherwise → DENY

    Phase 1: Cedar evaluation is stubbed; returns REQUIRE_APPROVAL for eligible
    claims so the HITL path is exercised in the graph run.
    """
    assessment = state.eligibility_assessment
    result = state.availability_result

    if assessment is None or result is None:
        return {
            "errors": state.errors + ["risk_policy_gate: missing assessment or result"],
            "policy_decision": PolicyDecision.DENY,
        }

    if not assessment.eligible_estimate or not result.is_eligible:
        return {"policy_decision": PolicyDecision.DENY}

    # All financial mutations require explicit human approval
    return {"policy_decision": PolicyDecision.REQUIRE_APPROVAL}


# ---------------------------------------------------------------------------
# Node 9 — claim_package_generator (AgentNode stub)
# ---------------------------------------------------------------------------

def claim_package_generator_stub(state: GraphState) -> dict:
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

def submission_adapter_fn(state: GraphState) -> dict:
    """
    Submit the claim package to AWS Support — or simulate if simulation_mode is True.

    Real submission requires:
      - simulation_mode == False (explicit opt-in)
      - A valid ApprovalRecord that has not expired
      - AgentCore Policy ALLOW decision

    In Phase 1 all runs are simulation_mode=True.
    """
    package = state.claim_package
    approval = state.approval_record

    if package is None:
        return {"errors": state.errors + ["submission_adapter: no claim package"]}

    if state.simulation_mode:
        # Deterministic simulated case ID for replay reproducibility
        case_id = "sim-" + hashlib.sha256(
            package.calculator_result_hash.encode()
        ).hexdigest()[:12]
        return {
            "case_id": case_id,
            "submitted_at": _utcnow(),
        }

    # Real submission gate
    if approval is None or not approval.is_valid:
        return {
            "errors": state.errors + [
                "submission_adapter: valid approval required for live submission"
            ]
        }

    # Phase 2: call real support adapter
    return {"errors": state.errors + ["submission_adapter: live submission not yet implemented"]}


# ---------------------------------------------------------------------------
# Node 11 — case_monitor (AgentNode stub)
# ---------------------------------------------------------------------------

def case_monitor_stub(state: GraphState) -> dict:
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
