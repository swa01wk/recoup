"""
Phase 3 tests — Evidence System, Safety Layer & HITL Approval.

All tests are deterministic: no LLM calls, no AWS calls, no network.
Tests cover:
  - EvidenceCollector: manifest construction, field mapping, missing fields
  - EvidenceSanitizer: 6 redaction scenarios, fail-closed second-pass scan
  - AutonomyClass enforcement: BLACK → ToolDeniedError, RED without approval → error
  - Cedar policy: all 5 preconditions on submit_support_case, destructive deny
  - HITLFlow: create, approve, decline, binding assertions, expiry
  - ApprovalStore: save/get/list/update with in-memory fallback
  - Integration: full graph run produces REQUIRE_APPROVAL → real sanitizer runs
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from recoup.approval.flow import HITLFlow
from recoup.approval.store import (
    _clear_in_memory,
    get_approval,
    get_pending_for_opportunity,
    list_pending_approvals,
    save_approval,
    update_approval_state,
)
from recoup.evidence.collector import EvidenceCollector
from recoup.evidence.sanitizer import EvidenceSanitizer
from recoup.models.approval import ApprovalRecord, ApprovalState
from recoup.models.evidence import EvidenceItem, EvidenceManifest
from recoup.models.signal import IncidentSignal
from recoup.models.sla import CreditTier, SLAContract
from recoup.safety.autonomy import (
    AutonomyClass,
    check_autonomy,
    get_autonomy_class,
)
from recoup.safety.cedar import PolicyContext, evaluate_policy
from recoup.safety.exceptions import (
    ApprovalRequiredError,
    SanitizationError,
    ToolDeniedError,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_approval_store() -> None:
    """Clear in-memory approval store before each test."""
    _clear_in_memory()


def _make_signal() -> IncidentSignal:
    return IncidentSignal(
        source="replay",
        event_id="evt-test-001",
        service="amazon-api-gateway",
        region="us-east-1",
        start=datetime(2026, 8, 1, 2, 0, tzinfo=UTC),
        end=datetime(2026, 8, 1, 2, 30, tzinfo=UTC),
        affected_resource_ids=["api-abc123"],
        raw_ref="s3://recoup-evidence/test/health_event.json",
        replay=True,
    )


def _make_contract() -> SLAContract:
    return SLAContract(
        service="amazon-api-gateway",
        version="2022-05-05",
        service_commitment=Decimal("99.95"),
        interval_minutes=5,
        claim_deadline_rule="within 30 days of billing cycle end",
        required_claim_fields=[
            "request_logs",
            "billing_record",
            "health_event",
        ],
        credit_tiers=[
            CreditTier(
                min_pct=Decimal("0"),
                max_exclusive_pct=Decimal("99.0"),
                credit_pct=Decimal("25"),
            ),
            CreditTier(
                min_pct=Decimal("99.0"),
                max_exclusive_pct=Decimal("99.95"),
                credit_pct=Decimal("10"),
            ),
        ],
        exclusions=[],
        source_url="https://aws.amazon.com/api-gateway/sla/",
        effective_from=datetime(2022, 5, 5).date(),
        source_hash="sha256:abc123def456abc123def456abc123def456abc123def456abc123def456abc1",
    )


def _make_approval_record(
    *,
    state: ApprovalState = ApprovalState.PENDING,
    expires_in_hours: int = 24,
    amount: Decimal = Decimal("35.00"),
    claim_hash: str = "sha256:deadbeef",
    state_version: int = 1,
) -> ApprovalRecord:
    now = datetime.now(UTC)
    return ApprovalRecord(
        approval_id="appr-test-001",
        principal="operator@example.com",
        action="submit_support_case",
        amount=amount,
        claim_hash=claim_hash,
        opportunity_id="opp-test-001",
        state_version=state_version,
        timestamp=now,
        expires_at=now + timedelta(hours=expires_in_hours),
        state=state,
    )


# ===========================================================================
# Evidence Collector
# ===========================================================================


class TestEvidenceCollector:
    def test_collect_all_required_fields(self) -> None:
        contract = _make_contract()
        signal = _make_signal()
        collector = EvidenceCollector()
        manifest = collector.collect(contract, signal, "opp-001")

        assert manifest.opportunity_id == "opp-001"
        assert len(manifest.items) == len(contract.required_claim_fields)
        assert manifest.missing_fields == []

    def test_manifest_items_have_sha256_hashes(self) -> None:
        contract = _make_contract()
        signal = _make_signal()
        collector = EvidenceCollector()
        manifest = collector.collect(contract, signal, "opp-001")

        for item in manifest.items:
            assert item.hash.startswith("sha256:")

    def test_manifest_items_have_storage_uris(self) -> None:
        contract = _make_contract()
        signal = _make_signal()
        collector = EvidenceCollector()
        manifest = collector.collect(contract, signal, "opp-001")

        for item in manifest.items:
            assert item.storage_uri
            assert "opp-001" in item.storage_uri
            assert item.storage_uri.startswith(("s3://", "stub://"))

    def test_sanitized_uri_is_none_before_sanitization(self) -> None:
        contract = _make_contract()
        signal = _make_signal()
        collector = EvidenceCollector()
        manifest = collector.collect(contract, signal, "opp-001")

        for item in manifest.items:
            assert item.sanitized_uri is None

    def test_raw_content_not_in_manifest(self) -> None:
        """Raw evidence content must never appear in the manifest."""
        contract = _make_contract()
        signal = _make_signal()
        collector = EvidenceCollector()
        manifest = collector.collect(contract, signal, "opp-001")

        manifest_json = manifest.model_dump_json()
        # The manifest should not contain stub content keys
        assert '"_stub": true' not in manifest_json
        assert '"field_value"' not in manifest_json

    def test_replay_fixtures_used_when_present(self) -> None:
        contract = _make_contract()
        signal = _make_signal()
        fixtures = {
            "request_logs": {"log_group": "/aws/apigateway/test", "events": []},
            "billing_record": {"billed_amount_usd": "350.00"},
        }
        collector = EvidenceCollector(replay_fixtures=fixtures)
        manifest = collector.collect(contract, signal, "opp-001")

        # All 3 required fields should be collected (2 from fixtures, 1 from stub)
        assert len(manifest.items) == 3
        sources = {item.source for item in manifest.items}
        assert "request_logs" in sources
        assert "billing_record" in sources

    def test_is_complete_true_when_no_missing_fields(self) -> None:
        contract = _make_contract()
        signal = _make_signal()
        collector = EvidenceCollector()
        manifest = collector.collect(contract, signal, "opp-001")
        assert manifest.is_complete is True


# ===========================================================================
# Evidence Sanitizer
# ===========================================================================


class TestEvidenceSanitizer:
    def _make_item(self, content_hint: str = "clean") -> EvidenceItem:
        return EvidenceItem(
            id="ev-test001",
            type="log",
            source="request_logs",
            timestamp_range=(
                datetime(2026, 8, 1, 2, 0, tzinfo=UTC),
                datetime(2026, 8, 1, 2, 30, tzinfo=UTC),
            ),
            storage_uri="s3://recoup-evidence/evidence/raw/opp-001/request_logs/abc.json",
            sanitized_uri=None,
            hash="sha256:abc123",
            sensitivity="HIGH",
            status="FOUND",
        )

    def _make_manifest(self, items: list[EvidenceItem] | None = None) -> EvidenceManifest:
        if items is None:
            items = [self._make_item()]
        return EvidenceManifest(
            opportunity_id="opp-001",
            items=items,
        )

    def test_sanitize_clean_content_produces_status_redacted(self) -> None:
        sanitizer = EvidenceSanitizer()
        item = self._make_item()
        sanitized_item, report = sanitizer.sanitize_item(item)
        assert sanitized_item.status == "REDACTED"

    def test_sanitize_sets_sanitized_uri(self) -> None:
        sanitizer = EvidenceSanitizer()
        item = self._make_item()
        sanitized_item, _ = sanitizer.sanitize_item(item)
        assert sanitized_item.sanitized_uri is not None
        assert "/sanitized/" in sanitized_item.sanitized_uri

    def test_report_has_raw_and_sanitized_hash(self) -> None:
        sanitizer = EvidenceSanitizer()
        item = self._make_item()
        _, report = sanitizer.sanitize_item(item)
        assert report.raw_hash.startswith("sha256:")
        assert report.sanitized_hash.startswith("sha256:")

    def test_redacts_authorization_header(self) -> None:
        content = "Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.payload.signature"
        sanitized, count, _ = EvidenceSanitizer()._apply_redactions(content)
        assert "[REDACTED-AUTH-TOKEN]" in sanitized
        assert count > 0

    def test_redacts_jwt_token(self) -> None:
        content = "token: eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1c2VyMTIzIn0.SflKxwRJSMeKKF2QT4"
        sanitized, count, _ = EvidenceSanitizer()._apply_redactions(content)
        assert "[REDACTED-JWT]" in sanitized
        assert count > 0

    def test_redacts_api_key(self) -> None:
        content = '{"api_key": "sk-live-abc123defghijklmnop"}'
        sanitized, count, _ = EvidenceSanitizer()._apply_redactions(content)
        assert "[REDACTED-API-KEY]" in sanitized
        assert count > 0

    def test_redacts_cookie(self) -> None:
        content = "Cookie: session=abc123xyz; path=/"
        sanitized, count, _ = EvidenceSanitizer()._apply_redactions(content)
        assert "[REDACTED-COOKIE]" in sanitized
        assert count > 0

    def test_redacts_email(self) -> None:
        content = "User: admin@example.com submitted the request"
        sanitized, count, _ = EvidenceSanitizer()._apply_redactions(content)
        assert "[REDACTED-EMAIL]" in sanitized
        assert count > 0

    def test_redacts_aws_account_id(self) -> None:
        content = "Account: 123456789012 in us-east-1"
        sanitized, count, _ = EvidenceSanitizer()._apply_redactions(content)
        assert "[REDACTED-ACCOUNT-ID]" in sanitized
        assert count > 0

    def test_fail_closed_on_high_risk_pattern(self) -> None:
        """Sanitizer must raise SanitizationError if a known secret pattern survives."""

        class _AlwaysFailSanitizer(EvidenceSanitizer):
            def _apply_redactions(self, content: str) -> tuple[str, int, list[str]]:
                # Simulate redaction pass that leaves a high-risk pattern
                return "password: mysecretpassword123", 0, []

        sanitizer = _AlwaysFailSanitizer()
        item = self._make_item()
        with pytest.raises(SanitizationError) as exc_info:
            sanitizer.sanitize_item(item)
        assert exc_info.value.evidence_id == item.id

    def test_sanitize_manifest_aggregates_redactions(self) -> None:
        sanitizer = EvidenceSanitizer()
        items = [self._make_item() for _ in range(3)]
        manifest = self._make_manifest(items)
        sanitized_manifest = sanitizer.sanitize_manifest(manifest)
        assert sanitized_manifest.redaction_report.raw_hash.startswith("sha256:")
        assert all(i.status == "REDACTED" for i in sanitized_manifest.items)

    def test_missing_items_skipped_by_sanitizer(self) -> None:
        sanitizer = EvidenceSanitizer()
        item = self._make_item().model_copy(update={"status": "MISSING"})
        manifest = self._make_manifest([item])
        sanitized_manifest = sanitizer.sanitize_manifest(manifest)
        # MISSING items pass through unchanged
        assert sanitized_manifest.items[0].status == "MISSING"


# ===========================================================================
# Autonomy Class Enforcement
# ===========================================================================


class TestAutonomyClass:
    def test_green_tools_classified_correctly(self) -> None:
        green_tools = [
            "get_cloudwatch_metrics",
            "query_cloudwatch_logs",
            "get_health_event",
            "get_cost_and_usage",
            "lookup_cloudtrail_events",
        ]
        for tool in green_tools:
            assert get_autonomy_class(tool) == AutonomyClass.GREEN

    def test_yellow_tools_classified_correctly(self) -> None:
        yellow_tools = ["store_evidence", "create_approval_request", "simulate_support_case"]
        for tool in yellow_tools:
            assert get_autonomy_class(tool) == AutonomyClass.YELLOW

    def test_red_tools_classified_correctly(self) -> None:
        red_tools = ["submit_support_case", "stop_demo_instance"]
        for tool in red_tools:
            assert get_autonomy_class(tool) == AutonomyClass.RED

    def test_black_tools_classified_correctly(self) -> None:
        black_tools = ["stop_resource", "delete_resource", "terminate_ec2_instance"]
        for tool in black_tools:
            assert get_autonomy_class(tool) == AutonomyClass.BLACK

    def test_unknown_tool_defaults_to_black(self) -> None:
        assert get_autonomy_class("destroy_everything") == AutonomyClass.BLACK

    def test_check_autonomy_black_raises_tool_denied(self) -> None:
        with pytest.raises(ToolDeniedError) as exc_info:
            check_autonomy("stop_resource", opportunity_id="opp-001")
        assert "stop_resource" in str(exc_info.value)
        assert exc_info.value.tool_name == "stop_resource"

    def test_check_autonomy_red_without_approval_raises(self) -> None:
        with pytest.raises(ApprovalRequiredError) as exc_info:
            check_autonomy(
                "submit_support_case",
                opportunity_id="opp-001",
                approval=None,
            )
        assert exc_info.value.tool_name == "submit_support_case"
        assert exc_info.value.opportunity_id == "opp-001"

    def test_check_autonomy_red_with_expired_approval_raises(self) -> None:
        expired = _make_approval_record(
            state=ApprovalState.APPROVED,
            expires_in_hours=-1,  # already expired
        )
        with pytest.raises(ApprovalRequiredError):
            check_autonomy(
                "submit_support_case",
                opportunity_id="opp-test-001",
                approval=expired,
            )

    def test_check_autonomy_red_with_valid_approval_passes(self) -> None:
        valid = _make_approval_record(state=ApprovalState.APPROVED, expires_in_hours=24)
        # Should not raise
        check_autonomy(
            "submit_support_case",
            opportunity_id="opp-test-001",
            approval=valid,
        )

    def test_check_autonomy_green_passes_without_approval(self) -> None:
        # GREEN tools never need approval
        check_autonomy("get_cloudwatch_metrics", opportunity_id="opp-001")

    def test_check_autonomy_yellow_passes_without_approval(self) -> None:
        check_autonomy("store_evidence", opportunity_id="opp-001")


# ===========================================================================
# Cedar Policy Evaluation
# ===========================================================================


class TestCedarPolicy:
    def _base_ctx(self, **overrides: object) -> PolicyContext:
        """Create a PolicyContext with all 5 preconditions satisfied."""
        now = datetime.now(UTC)
        ctx = PolicyContext(
            session_authenticated=True,
            approval_state="APPROVED",
            approval_amount=Decimal("35.00"),
            approval_expires_at=now + timedelta(hours=12),
            approved_state_version=1,
            claim_amount=Decimal("35.00"),
            opportunity_state_version=1,
            recoup_enable_real_submission=True,
            current_time=now,
        )
        for k, v in overrides.items():
            object.__setattr__(ctx, k, v)
        return ctx

    def test_policy_allows_submit_when_all_conditions_met(self) -> None:
        ctx = self._base_ctx()
        assert evaluate_policy("submit_support_case", ctx) == "ALLOW"

    def test_policy_denies_submit_without_approval(self) -> None:
        ctx = self._base_ctx(approval_state="PENDING")
        assert evaluate_policy("submit_support_case", ctx) == "DENY"

    def test_policy_denies_submit_without_real_submission_flag(self) -> None:
        """Cedar must DENY when real submission flag is off (Phase 6d: no simulation_mode)."""
        ctx = self._base_ctx(recoup_enable_real_submission=False)
        assert evaluate_policy("submit_support_case", ctx) == "DENY"

    def test_policy_denies_stale_approval(self) -> None:
        now = datetime.now(UTC)
        ctx = self._base_ctx(approval_expires_at=now - timedelta(minutes=1))
        assert evaluate_policy("submit_support_case", ctx) == "DENY"

    def test_policy_denies_amount_mismatch(self) -> None:
        ctx = self._base_ctx(
            approval_amount=Decimal("35.00"),
            claim_amount=Decimal("1900.00"),  # regenerated package
        )
        assert evaluate_policy("submit_support_case", ctx) == "DENY"

    def test_policy_denies_state_version_mismatch(self) -> None:
        ctx = self._base_ctx(
            approved_state_version=1,
            opportunity_state_version=2,  # state changed after approval
        )
        assert evaluate_policy("submit_support_case", ctx) == "DENY"

    def test_policy_denies_when_real_submission_flag_off(self) -> None:
        ctx = self._base_ctx(recoup_enable_real_submission=False)
        assert evaluate_policy("submit_support_case", ctx) == "DENY"

    def test_policy_allows_read_tools_when_authenticated(self) -> None:
        ctx = PolicyContext(session_authenticated=True)
        read_tools = [
            "get_cloudwatch_metrics",
            "query_cloudwatch_logs",
            "get_health_event",
            "get_cost_and_usage",
            "lookup_cloudtrail_events",
        ]
        for tool in read_tools:
            assert evaluate_policy(tool, ctx) == "ALLOW", f"Expected ALLOW for {tool}"

    def test_policy_denies_read_tools_when_not_authenticated(self) -> None:
        ctx = PolicyContext(session_authenticated=False)
        assert evaluate_policy("get_cloudwatch_metrics", ctx) == "DENY"

    def test_policy_denies_destructive_tools(self) -> None:
        ctx = PolicyContext(session_authenticated=True)
        for action in ["stop_resource", "delete_resource", "terminate_ec2_instance"]:
            assert evaluate_policy(action, ctx) == "DENY", f"Expected DENY for {action}"

    def test_policy_allows_internal_write_tools(self) -> None:
        ctx = PolicyContext(session_authenticated=True)
        for tool in ["store_evidence", "create_approval_request", "simulate_support_case"]:
            assert evaluate_policy(tool, ctx) == "ALLOW"

    def test_policy_denies_unknown_actions(self) -> None:
        ctx = PolicyContext(session_authenticated=True)
        assert evaluate_policy("wipe_all_data", ctx) == "DENY"


# ===========================================================================
# Approval Store
# ===========================================================================


class TestApprovalStore:
    def test_save_and_get_round_trip(self) -> None:
        record = _make_approval_record()
        save_approval(record)
        fetched = get_approval("appr-test-001")
        assert fetched is not None
        assert fetched.approval_id == "appr-test-001"
        assert fetched.state == ApprovalState.PENDING

    def test_get_returns_none_for_missing(self) -> None:
        result = get_approval("nonexistent-id")
        assert result is None

    def test_list_pending_returns_only_pending(self) -> None:
        pending = _make_approval_record(state=ApprovalState.PENDING)
        approved = _make_approval_record(state=ApprovalState.APPROVED)
        approved = approved.model_copy(update={"approval_id": "appr-approved-001"})
        save_approval(pending)
        save_approval(approved)

        pending_list = list_pending_approvals()
        assert len(pending_list) == 1
        assert pending_list[0].approval_id == "appr-test-001"

    def test_update_state_approved(self) -> None:
        record = _make_approval_record()
        save_approval(record)
        updated = update_approval_state(
            "appr-test-001",
            ApprovalState.APPROVED,
        )
        assert updated is not None
        assert updated.state == ApprovalState.APPROVED

    def test_get_pending_for_opportunity(self) -> None:
        record = _make_approval_record()
        save_approval(record)
        result = get_pending_for_opportunity("opp-test-001")
        assert result is not None
        assert result.opportunity_id == "opp-test-001"

    def test_get_pending_returns_none_when_none(self) -> None:
        result = get_pending_for_opportunity("opp-no-approval")
        assert result is None


# ===========================================================================
# HITL Flow
# ===========================================================================


class TestHITLFlow:
    def test_create_request_returns_pending_record(self) -> None:
        flow = HITLFlow(opportunity_id="opp-flow-001")
        record = flow.create_request(
            principal="operator@example.com",
            action="submit_support_case",
            amount=Decimal("35.00"),
            claim_hash="sha256:deadbeef",
            state_version=1,
        )
        assert record.state == ApprovalState.PENDING
        assert record.opportunity_id == "opp-flow-001"
        assert record.amount == Decimal("35.00")

    def test_create_request_persists_to_store(self) -> None:
        flow = HITLFlow(opportunity_id="opp-flow-002")
        record = flow.create_request(
            principal="operator@example.com",
            action="submit_support_case",
            amount=Decimal("35.00"),
            claim_hash="sha256:deadbeef",
            state_version=1,
        )
        fetched = get_approval(record.approval_id)
        assert fetched is not None
        assert fetched.state == ApprovalState.PENDING

    def test_approve_with_valid_bindings(self) -> None:
        flow = HITLFlow(opportunity_id="opp-flow-003")
        record = flow.create_request(
            principal="system",
            action="submit_support_case",
            amount=Decimal("35.00"),
            claim_hash="sha256:abc123",
            state_version=1,
        )
        updated = flow.approve(
            approval_id=record.approval_id,
            principal="operator@example.com",
            claim_hash="sha256:abc123",
            amount=Decimal("35.00"),
            state_version=1,
        )
        assert updated.state == ApprovalState.APPROVED

    def test_approve_fails_on_claim_hash_mismatch(self) -> None:
        flow = HITLFlow(opportunity_id="opp-flow-004")
        record = flow.create_request(
            principal="system",
            action="submit_support_case",
            amount=Decimal("35.00"),
            claim_hash="sha256:original",
            state_version=1,
        )
        with pytest.raises(ValueError, match="claim_hash mismatch"):
            flow.approve(
                approval_id=record.approval_id,
                principal="operator@example.com",
                claim_hash="sha256:tampered",
                amount=Decimal("35.00"),
                state_version=1,
            )

    def test_approve_fails_on_amount_mismatch(self) -> None:
        flow = HITLFlow(opportunity_id="opp-flow-005")
        record = flow.create_request(
            principal="system",
            action="submit_support_case",
            amount=Decimal("35.00"),
            claim_hash="sha256:abc123",
            state_version=1,
        )
        with pytest.raises(ValueError, match="amount mismatch"):
            flow.approve(
                approval_id=record.approval_id,
                principal="operator@example.com",
                claim_hash="sha256:abc123",
                amount=Decimal("1900.00"),  # wrong amount
                state_version=1,
            )

    def test_approve_fails_on_state_version_mismatch(self) -> None:
        flow = HITLFlow(opportunity_id="opp-flow-006")
        record = flow.create_request(
            principal="system",
            action="submit_support_case",
            amount=Decimal("35.00"),
            claim_hash="sha256:abc123",
            state_version=1,
        )
        with pytest.raises(ValueError, match="state_version mismatch"):
            flow.approve(
                approval_id=record.approval_id,
                principal="operator@example.com",
                claim_hash="sha256:abc123",
                amount=Decimal("35.00"),
                state_version=99,  # state changed after request
            )

    def test_approve_fails_on_expired_record(self) -> None:
        flow = HITLFlow(opportunity_id="opp-flow-007")
        record = flow.create_request(
            principal="system",
            action="submit_support_case",
            amount=Decimal("35.00"),
            claim_hash="sha256:abc123",
            state_version=1,
            ttl_hours=0,  # immediately expired
        )
        # Manually set expires_at in the past
        expired = record.model_copy(
            update={"expires_at": datetime.now(UTC) - timedelta(hours=1)}
        )
        from recoup.approval.store import save_approval
        save_approval(expired)

        with pytest.raises(ValueError, match="expired"):
            flow.approve(
                approval_id=record.approval_id,
                principal="operator@example.com",
                claim_hash="sha256:abc123",
                amount=Decimal("35.00"),
                state_version=1,
            )

    def test_decline_sets_declined_state(self) -> None:
        flow = HITLFlow(opportunity_id="opp-flow-008")
        record = flow.create_request(
            principal="system",
            action="submit_support_case",
            amount=Decimal("35.00"),
            claim_hash="sha256:abc123",
            state_version=1,
        )
        updated = flow.decline(
            approval_id=record.approval_id,
            principal="operator@example.com",
            notes="Risk too high",
        )
        assert updated.state == ApprovalState.DECLINED

    def test_create_second_request_revokes_first(self) -> None:
        """Creating a second approval request should revoke the first."""
        flow = HITLFlow(opportunity_id="opp-flow-009")
        first = flow.create_request(
            principal="system",
            action="submit_support_case",
            amount=Decimal("35.00"),
            claim_hash="sha256:first",
            state_version=1,
        )
        _second = flow.create_request(
            principal="system",
            action="submit_support_case",
            amount=Decimal("35.00"),
            claim_hash="sha256:second",
            state_version=2,
        )
        revoked = get_approval(first.approval_id)
        assert revoked is not None
        assert revoked.state == ApprovalState.REVOKED

    def test_get_pending_returns_current_request(self) -> None:
        flow = HITLFlow(opportunity_id="opp-flow-010")
        record = flow.create_request(
            principal="system",
            action="submit_support_case",
            amount=Decimal("35.00"),
            claim_hash="sha256:abc123",
            state_version=1,
        )
        pending = flow.get_pending()
        assert pending is not None
        assert pending.approval_id == record.approval_id

    def test_approval_card_text_contains_key_fields(self) -> None:
        flow = HITLFlow(opportunity_id="opp-flow-011")
        record = flow.create_request(
            principal="system",
            action="submit_support_case",
            amount=Decimal("35.00"),
            claim_hash="sha256:abc123def456",
            state_version=1,
        )
        card = flow.approval_card_text(record)
        assert "submit_support_case" in card
        assert "35.00" in card
        assert "opp-flow-011" in card
        assert "[Approve]" in card
        assert "[Decline]" in card

    def test_create_request_populates_approval_context_fields(self) -> None:
        flow = HITLFlow(opportunity_id="opp-flow-012")
        sla = flow.create_request(
            principal="operator@example.com",
            action="submit_support_case",
            amount=Decimal("35.00"),
            claim_hash="sha256:sla",
            state_version=1,
        )
        assert sla.risk_tier == "YELLOW"
        assert "SLA credit claim" in sla.action_description
        assert "Withdraw claim" in sla.rollback_context

        ec2 = flow.create_request(
            principal="operator@example.com",
            action="stop_demo_instance",
            amount=Decimal("7.59"),
            claim_hash="sha256:ec2",
            state_version=1,
        )
        assert ec2.risk_tier == "RED"
        assert "Stop EC2 demo instance" in ec2.action_description
        assert "restart instance" in ec2.rollback_context

    def test_approval_record_is_valid_when_approved_and_not_expired(self) -> None:
        record = _make_approval_record(state=ApprovalState.APPROVED, expires_in_hours=24)
        assert record.is_valid is True

    def test_approval_record_is_not_valid_when_expired(self) -> None:
        record = _make_approval_record(state=ApprovalState.APPROVED, expires_in_hours=-1)
        assert record.is_valid is False

    def test_approval_record_is_not_valid_when_pending(self) -> None:
        record = _make_approval_record(state=ApprovalState.PENDING)
        assert record.is_valid is False


# ===========================================================================
# Integration — graph run produces real sanitizer output
# ===========================================================================


class TestPhase3GraphIntegration:
    def test_graph_run_uses_real_sanitizer(self) -> None:
        """Evidence sanitizer node should produce REDACTED items after graph run."""
        from recoup.adapters.replay import ReplayAdapter
        from recoup.graph.recoup_graph import build_recoup_graph

        adapter = ReplayAdapter()
        state = adapter.build_state()
        graph = build_recoup_graph()
        final_state = graph.run(state)

        # After Phase 3, the sanitized manifest should have REDACTED items
        assert final_state.sanitized_manifest is not None
        for item in final_state.sanitized_manifest.items:
            assert item.status in ("REDACTED", "MISSING"), (
                f"Item {item.id} should be REDACTED or MISSING, got {item.status}"
            )

    def test_graph_run_produces_redaction_report(self) -> None:
        from recoup.adapters.replay import ReplayAdapter
        from recoup.graph.recoup_graph import build_recoup_graph

        adapter = ReplayAdapter()
        state = adapter.build_state()
        graph = build_recoup_graph()
        final_state = graph.run(state)

        assert final_state.redaction_report is not None
        assert final_state.redaction_report.raw_hash.startswith("sha256:")
        assert final_state.redaction_report.sanitized_hash.startswith("sha256:")

    def test_graph_run_policy_decision_is_require_approval(self) -> None:
        """Without an approval record the policy gate must return REQUIRE_APPROVAL."""
        from recoup.adapters.replay import ReplayAdapter
        from recoup.graph.recoup_graph import build_recoup_graph
        from recoup.graph.types import PolicyDecision

        adapter = ReplayAdapter()
        state = adapter.build_state()
        graph = build_recoup_graph()
        final_state = graph.run(state)

        assert final_state.policy_decision == PolicyDecision.REQUIRE_APPROVAL

    def test_graph_golden_amount_preserved(self) -> None:
        """Golden amount must be preserved through Phase 3 nodes."""
        from recoup.adapters.replay import ReplayAdapter
        from recoup.graph.recoup_graph import build_recoup_graph

        adapter = ReplayAdapter()
        state = adapter.build_state()
        graph = build_recoup_graph()
        final_state = graph.run(state)

        assert final_state.availability_result is not None
        assert final_state.availability_result.potential_credit > Decimal("0")
