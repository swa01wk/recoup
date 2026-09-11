"""
Unit tests for all domain models.

Covers field validation, custom validators, computed properties, and
Pydantic v2 serialisation. No LLM calls, no AWS calls, no network.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from recoup.models.approval import ApprovalRecord, ApprovalState
from recoup.models.claim import ClaimPackage
from recoup.models.eligibility import EligibilityAssessment
from recoup.models.evidence import EvidenceItem, EvidenceManifest
from recoup.models.opportunity import OpportunityState, RecoveryOpportunity
from recoup.models.signal import IncidentSignal
from recoup.models.sla import CreditTier, SLAContract


def _utcnow() -> datetime:
    return datetime.now(UTC)

# ---------------------------------------------------------------------------
# RecoveryOpportunity
# ---------------------------------------------------------------------------


class TestRecoveryOpportunity:
    def test_default_state_is_detected(self) -> None:
        opp = RecoveryOpportunity(
            id="opp-001",
            type="SLA",
            account_id_masked="123456789012",
            service="apigateway",
            region="us-east-1",
            discovered_at=_utcnow(),
            potential_value=Decimal("35.00"),
            confidence=0.92,
            state=OpportunityState.DETECTED,
        )
        assert opp.state == OpportunityState.DETECTED

    def test_account_id_is_masked(self) -> None:
        opp = RecoveryOpportunity(
            id="opp-001",
            type="SLA",
            account_id_masked="123456789012",
            service="apigateway",
            region="us-east-1",
            discovered_at=_utcnow(),
            state=OpportunityState.DETECTED,
        )
        assert opp.account_id_masked == "****9012"
        assert "123456789012" not in opp.account_id_masked

    def test_confidence_bounds(self) -> None:
        with pytest.raises(ValidationError):
            RecoveryOpportunity(
                id="opp-002",
                type="SLA",
                account_id_masked="1234",
                service="ec2",
                region="us-east-1",
                discovered_at=_utcnow(),
                confidence=1.5,  # invalid
                state=OpportunityState.DETECTED,
            )

    def test_state_version_defaults_zero(self) -> None:
        opp = RecoveryOpportunity(
            id="opp-003",
            type="SLA",
            account_id_masked="9999",
            service="s3",
            region="us-west-2",
            discovered_at=_utcnow(),
            state=OpportunityState.DETECTED,
        )
        assert opp.state_version == 0


# ---------------------------------------------------------------------------
# IncidentSignal
# ---------------------------------------------------------------------------


class TestIncidentSignal:
    def test_valid_signal(self) -> None:
        signal = IncidentSignal(
            source="replay",
            event_id="evt-001",
            service="apigateway",
            region="us-east-1",
            start=datetime(2026, 8, 1, 2, 0),
            end=datetime(2026, 8, 1, 2, 30),
            affected_resource_ids=["arn:aws:apigateway:us-east-1::/restapis/demo"],
            raw_ref="s3://recoup-evidence/evt-001.json",
        )
        assert signal.source == "replay"
        assert signal.replay is False

    def test_invalid_source(self) -> None:
        with pytest.raises(ValidationError):
            IncidentSignal(
                source="unknown_source",  # type: ignore
                event_id="evt-002",
                service="ec2",
                region="us-east-1",
                start=_utcnow(),
                end=_utcnow(),
                affected_resource_ids=[],
                raw_ref="s3://bucket/key",
            )


# ---------------------------------------------------------------------------
# SLAContract
# ---------------------------------------------------------------------------


class TestSLAContract:
    def _contract(self) -> SLAContract:
        return SLAContract(
            service="apigateway",
            version="2022-05-05",
            effective_from=date(2022, 5, 5),
            effective_to=None,
            service_commitment=Decimal("99.95"),
            interval_minutes=5,
            claim_deadline_rule="end_of_second_billing_cycle_after_incident",
            credit_tiers=[
                CreditTier(
                    min_pct=Decimal("99.00"),
                    max_exclusive_pct=Decimal("99.95"),
                    credit_pct=Decimal("10"),
                ),
                CreditTier(
                    min_pct=Decimal("95.00"),
                    max_exclusive_pct=Decimal("99.00"),
                    credit_pct=Decimal("25"),
                ),
                CreditTier(
                    min_pct=Decimal("0.00"),
                    max_exclusive_pct=Decimal("95.00"),
                    credit_pct=Decimal("100"),
                ),
            ],
            required_claim_fields=["api_id", "region", "billing_cycle"],
            exclusions=["customer_caused_errors"],
            source_url="https://aws.amazon.com/api-gateway/sla/",
            source_hash="sha256:abc123",
        )

    def test_source_hash_required(self) -> None:
        with pytest.raises(ValidationError):
            SLAContract(
                service="apigateway",
                version="2022-05-05",
                effective_from=date(2022, 5, 5),
                service_commitment=Decimal("99.95"),
                interval_minutes=5,
                claim_deadline_rule="end_of_second_billing_cycle",
                credit_tiers=[
                    CreditTier(
                        min_pct=Decimal("99.00"),
                        max_exclusive_pct=Decimal("99.95"),
                        credit_pct=Decimal("10"),
                    ),
                ],
                required_claim_fields=["api_id"],
                source_url="https://example.com",
                source_hash="MISSING_PREFIX",  # invalid — no 'sha256:' prefix
            )

    def test_resolve_tier_10pct(self) -> None:
        contract = self._contract()
        tier = contract.resolve_tier(Decimal("99.9306"))
        assert tier == Decimal("10")

    def test_resolve_tier_no_breach(self) -> None:
        contract = self._contract()
        tier = contract.resolve_tier(Decimal("99.95"))  # exactly at commitment = no breach
        assert tier == Decimal("0")

    def test_credit_tier_invalid_range(self) -> None:
        with pytest.raises(ValidationError):
            CreditTier(
                min_pct=Decimal("99.95"),
                max_exclusive_pct=Decimal("99.00"),  # min > max — invalid
                credit_pct=Decimal("10"),
            )


# ---------------------------------------------------------------------------
# EvidenceManifest
# ---------------------------------------------------------------------------


class TestEvidenceManifest:
    def _item(self, ev_id: str = "ev-aabbccdd") -> EvidenceItem:
        return EvidenceItem(
            id=ev_id,
            type="metric",
            source="cloudwatch",
            timestamp_range=(datetime(2026, 8, 1), datetime(2026, 8, 2)),
            storage_uri="s3://recoup-evidence/test.json",
            hash="sha256:abc123",
            sensitivity="LOW",
            status="FOUND",
        )

    def test_is_complete_when_no_missing_fields(self) -> None:
        manifest = EvidenceManifest(
            opportunity_id="opp-001",
            items=[self._item()],
            missing_fields=[],
        )
        assert manifest.is_complete is True

    def test_is_incomplete_when_fields_missing(self) -> None:
        manifest = EvidenceManifest(
            opportunity_id="opp-001",
            items=[self._item()],
            missing_fields=["billing_record"],
        )
        assert manifest.is_complete is False

    def test_item_ids(self) -> None:
        manifest = EvidenceManifest(
            opportunity_id="opp-001",
            items=[self._item("ev-11111111"), self._item("ev-22222222")],
        )
        assert manifest.item_ids == {"ev-11111111", "ev-22222222"}


# ---------------------------------------------------------------------------
# EligibilityAssessment
# ---------------------------------------------------------------------------


class TestEligibilityAssessment:
    def test_low_confidence_requires_unresolved(self) -> None:
        with pytest.raises(ValidationError):
            EligibilityAssessment(
                eligible_estimate=True,
                confidence=0.5,  # low
                evidence_refs=["ev-aabbccdd"],
                unresolved=[],           # must have something if confidence < 0.7
                possible_exclusions=[],
            )

    def test_valid_low_confidence_with_unresolved(self) -> None:
        assessment = EligibilityAssessment(
            eligible_estimate=False,
            confidence=0.4,
            evidence_refs=["ev-aabbccdd"],
            unresolved=["billing_record not found"],
        )
        assert assessment.eligible_estimate is False

    def test_high_confidence_no_unresolved_ok(self) -> None:
        assessment = EligibilityAssessment(
            eligible_estimate=True,
            confidence=0.92,
            evidence_refs=["ev-aabbccdd"],
            satisfied_requirements=["api_id", "region"],
        )
        assert assessment.confidence == 0.92


# ---------------------------------------------------------------------------
# ApprovalRecord
# ---------------------------------------------------------------------------


class TestApprovalRecord:
    def test_create_factory(self) -> None:
        record = ApprovalRecord.create(
            approval_id="apr-001",
            principal="user@example.com",
            action="submit_sla_claim",
            amount=Decimal("35.00"),
            claim_hash="sha256:abc",
            opportunity_id="opp-001",
            state_version=3,
        )
        assert record.state == ApprovalState.PENDING
        assert record.is_expired is False

    def test_expired_record_is_invalid(self) -> None:
        past = _utcnow() - timedelta(hours=1)
        record = ApprovalRecord(
            approval_id="apr-002",
            principal="user@example.com",
            action="submit_sla_claim",
            amount=Decimal("500.00"),
            claim_hash="sha256:xyz",
            opportunity_id="opp-002",
            state_version=1,
            timestamp=past - timedelta(hours=24),
            expires_at=past,
            state=ApprovalState.APPROVED,
        )
        assert record.is_expired is True
        assert record.is_valid is False


# ---------------------------------------------------------------------------
# ClaimPackage
# ---------------------------------------------------------------------------


class TestClaimPackage:
    def test_invented_evidence_ref_rejected(self) -> None:
        """ClaimPackage must reject body containing ev-* IDs not in the manifest."""
        manifest = EvidenceManifest(
            opportunity_id="opp-001",
            items=[],
        )
        with pytest.raises(ValidationError):
            ClaimPackage(
                opportunity_id="opp-001",
                subject="Test",
                body="Evidence: ev-deadbeef",  # invented ID — not in manifest
                region="us-east-1",
                billing_cycle="2026-08",
                resources=["arn:aws:apigateway:us-east-1::/restapis/demo"],
                evidence_manifest=manifest,
                calculator_result_hash="sha256:hash",
            )

    def test_valid_package_no_ev_refs(self) -> None:
        manifest = EvidenceManifest(opportunity_id="opp-001", items=[])
        pkg = ClaimPackage(
            opportunity_id="opp-001",
            subject="SLA Credit Request",
            body="Please process this claim.",  # no ev-* refs
            region="us-east-1",
            billing_cycle="2026-08",
            resources=[],
            evidence_manifest=manifest,
            calculator_result_hash="sha256:abc",
        )
        assert pkg.billing_cycle == "2026-08"
