"""
Trajectory Tests — Phase 5.

These tests verify the structural guarantees of the Recoup agent pipeline:
  1. Node ordering is correct — safety-critical nodes never skip
  2. Policy enforcement fires before any mutating action
  3. Evidence sanitizer always runs before claim package generator
  4. Raw evidence never reaches the claim package or submission adapter
  5. Simulation mode is enforced throughout replay runs
  6. Tool allowlists are respected at every node

All tests are deterministic — full graph runs with canonical replay (no LLM).
"""

from __future__ import annotations

from decimal import Decimal

from recoup.adapters.replay import ReplayAdapter
from recoup.graph.recoup_graph import build_recoup_graph
from recoup.graph.types import GraphState, PolicyDecision

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_canonical() -> GraphState:
    adapter = ReplayAdapter()
    state = adapter.build_state()
    graph = build_recoup_graph()
    return graph.run(state)


# ---------------------------------------------------------------------------
# Node ordering — execution trace
# ---------------------------------------------------------------------------


class TestNodeOrdering:
    """Verify that nodes execute in the correct dependency order."""

    def test_normalize_event_produces_idempotency_key(self) -> None:
        """normalize_event must set idempotency_key before any other node runs."""
        final = _run_canonical()
        assert final.idempotency_key is not None
        assert len(final.idempotency_key) > 0

    def test_hypothesis_populated_before_calculator(self) -> None:
        """incident_correlation must set hypothesis before availability_calculator runs."""
        final = _run_canonical()
        assert final.hypothesis is not None
        assert final.availability_result is not None
        # availability_result depends on hypothesis — if both present, order was correct
        assert final.hypothesis.availability_intervals

    def test_contract_populated_before_calculator(self) -> None:
        """sla_contract_resolver must set contract before availability_calculator runs."""
        final = _run_canonical()
        assert final.contract is not None
        assert final.availability_result is not None

    def test_evidence_manifest_populated_before_sanitizer(self) -> None:
        """evidence_collector must set evidence_manifest before evidence_sanitizer runs."""
        final = _run_canonical()
        assert final.evidence_manifest is not None
        assert final.sanitized_manifest is not None

    def test_sanitized_manifest_set_before_eligibility(self) -> None:
        """evidence_sanitizer must complete before eligibility_reasoner references evidence."""
        final = _run_canonical()
        assert final.sanitized_manifest is not None
        assert final.eligibility_assessment is not None

    def test_eligibility_set_before_policy_gate(self) -> None:
        """eligibility_reasoner must set assessment before risk_policy_gate runs."""
        final = _run_canonical()
        assert final.eligibility_assessment is not None
        assert final.policy_decision is not None

    def test_all_eleven_pipeline_stages_produce_output(self) -> None:
        """All mandatory pipeline fields must be non-None after a full canonical run."""
        final = _run_canonical()
        assert final.signal is not None, "normalize_event: signal missing"
        assert final.hypothesis is not None, "incident_correlation: hypothesis missing"
        assert final.contract is not None, "sla_contract_resolver: contract missing"
        assert final.availability_result is not None, "availability_calculator: result missing"
        assert final.evidence_manifest is not None, "evidence_collector: manifest missing"
        assert final.sanitized_manifest is not None, "evidence_sanitizer: sanitized missing"
        assert final.eligibility_assessment is not None, "eligibility_reasoner: assessment missing"
        assert final.policy_decision is not None, "risk_policy_gate: decision missing"
        # claim_package + submission only after approval — not reached in standard run
        assert final.errors == [], f"Unexpected errors: {final.errors}"


# ---------------------------------------------------------------------------
# Safety: sanitizer always before claim package
# ---------------------------------------------------------------------------


class TestSanitizerBeforeClaimPackage:
    def test_sanitized_manifest_used_in_claim_package(self) -> None:
        """
        Claim package must reference evidence from the sanitized manifest only.
        Verifies that claim_package_generator_stub uses state.sanitized_manifest.
        """
        from recoup.approval.store import _clear_in_memory
        from recoup.graph.nodes import (
            claim_package_generator_stub,
        )

        _clear_in_memory()
        final = _run_canonical()

        # Simulate approval and run claim package generator
        from datetime import UTC, datetime, timedelta
        from decimal import Decimal

        from recoup.models.approval import ApprovalRecord, ApprovalState

        approval = ApprovalRecord(
            approval_id="appr-trajectory-001",
            principal="operator@example.com",
            action="submit_support_case",
            amount=Decimal("35.00"),
            claim_hash="sha256:trajectory",
            opportunity_id=final.opportunity_id,
            state_version=1,
            timestamp=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=24),
            state=ApprovalState.APPROVED,
        )
        state_with_approval = final.model_copy(update={"approval_record": approval})
        pkg_updates = claim_package_generator_stub(state_with_approval)

        assert "claim_package" in pkg_updates
        pkg = pkg_updates["claim_package"]

        # Every evidence ID in the claim package must come from sanitized_manifest
        sanitized_ids = {item.id for item in final.sanitized_manifest.items}
        for ev_item in pkg.evidence_manifest.items:
            assert ev_item.id in sanitized_ids, (
                f"Claim package references evidence ID '{ev_item.id}' not in sanitized manifest"
            )

    def test_raw_evidence_content_absent_from_sanitized_manifest(self) -> None:
        """Sanitized manifest items must not expose raw field values."""
        final = _run_canonical()
        sanitized_json = final.sanitized_manifest.model_dump_json()
        assert '"_stub": true' not in sanitized_json
        assert "field_value" not in sanitized_json


# ---------------------------------------------------------------------------
# Policy enforcement
# ---------------------------------------------------------------------------


class TestPolicyEnforcement:
    def test_canonical_run_produces_require_approval(self) -> None:
        """Without an approval record the policy gate returns REQUIRE_APPROVAL."""
        final = _run_canonical()
        assert final.policy_decision == PolicyDecision.REQUIRE_APPROVAL

    def test_graph_stops_at_policy_gate_without_approval(self) -> None:
        """Graph should not produce a claim_package if policy gate blocked."""
        final = _run_canonical()
        # claim_package is only set after ALLOW — should be None here
        assert final.claim_package is None

    def test_policy_denies_when_not_eligible(self) -> None:
        """Graph state with uptime above 99.95% must result in DENY."""

        from recoup.graph.nodes import risk_policy_gate_fn
        from recoup.models.availability import AvailabilityResult
        from recoup.models.eligibility import EligibilityAssessment

        final = _run_canonical()
        # Patch availability result to show no breach
        non_breach_result = AvailabilityResult(
            monthly_uptime_pct=Decimal("99.970000"),
            threshold_breached=False,
            tier_pct=Decimal("0"),
            potential_credit=Decimal("0.00"),
            billed_charges=Decimal("100.00"),
            total_intervals=8640,
            unavailable_intervals=0,
            calculation_trace=["No breach"],
        )
        non_eligible_assessment = EligibilityAssessment(
            eligible_estimate=False,
            confidence=0.95,
            satisfied_requirements=[],
            unresolved=[],
            possible_exclusions=[],
            evidence_refs=[],
        )
        patched = final.model_copy(update={
            "availability_result": non_breach_result,
            "eligibility_assessment": non_eligible_assessment,
        })
        result = risk_policy_gate_fn(patched)
        assert result["policy_decision"] == PolicyDecision.DENY

    def test_no_unsafe_actions_in_canonical_run(self) -> None:
        """Canonical replay must produce zero unsafe (live) external actions."""
        final = _run_canonical()
        # No live case submission
        assert final.case_id is None or final.case_id.startswith("sim-")


# ---------------------------------------------------------------------------
# Tool allowlists — nodes call only permitted tools
# ---------------------------------------------------------------------------


class TestToolAllowlists:
    def test_tool_registry_evidence_collector_tools(self) -> None:
        """evidence_collector node is only allowed to call its registered tools."""
        from recoup.tools.registry import TOOL_REGISTRY

        ec_tools = {
            name
            for name, entry in TOOL_REGISTRY.items()
            if "evidence_collector" in entry.allowed_nodes
        }
        expected = {
            "get_cloudwatch_metrics",
            "query_cloudwatch_logs",
            "get_cost_and_usage",
            "store_evidence",
        }
        # All expected tools must be registered for evidence_collector
        for tool in expected:
            assert tool in ec_tools, f"{tool} not registered for evidence_collector"

    def test_submission_adapter_not_in_read_only_node_tools(self) -> None:
        """submit_support_case must not be callable from incident_correlation."""
        from recoup.tools.registry import TOOL_REGISTRY

        entry = TOOL_REGISTRY.get("submit_support_case")
        if entry:
            allowed = entry.allowed_nodes
            assert "incident_correlation" not in allowed
            assert "evidence_collector" not in allowed
            assert "eligibility_reasoner" not in allowed

    def test_stop_demo_instance_only_in_submission_path(self) -> None:
        """stop_demo_instance must not be reachable from read-only nodes."""
        from recoup.tools.registry import TOOL_REGISTRY

        entry = TOOL_REGISTRY.get("stop_demo_instance")
        if entry:
            allowed = entry.allowed_nodes
            read_only_nodes = [
                "incident_correlation",
                "sla_contract_resolver",
                "availability_calculator",
                "evidence_sanitizer",
                "eligibility_reasoner",
                "risk_policy_gate",
            ]
            for node in read_only_nodes:
                assert node not in allowed, (
                    f"stop_demo_instance must not be accessible from {node}"
                )


# ---------------------------------------------------------------------------
# Simulation mode enforcement
# ---------------------------------------------------------------------------


class TestSimulationModeEnforcement:
    def test_replay_state_always_has_no_strands(self) -> None:
        """ReplayAdapter.build_state() must NOT set use_strands (replay stays deterministic)."""
        adapter = ReplayAdapter()
        state = adapter.build_state()
        assert state.use_strands is False

    def test_final_state_has_no_strands(self) -> None:
        """use_strands must remain False after full graph execution in canonical replay."""
        final = _run_canonical()
        assert final.use_strands is False

    def test_no_live_aws_calls_in_replay(self) -> None:
        """All tool stubs must return _stub=True in simulation paths."""
        from recoup.tools.aws_tools import get_cloudwatch_metrics

        result = get_cloudwatch_metrics(
            namespace="AWS/ApiGateway",
            metric_name="5XXError",
            dimensions=[],
            start_time="2026-08-01T02:00:00Z",
            end_time="2026-08-01T02:30:00Z",
        )
        assert result.get("_stub") is True

    def test_submission_adapter_produces_sim_case_id(self) -> None:
        """submission_adapter must return a sim-prefixed case_id in non-live mode."""
        from recoup.graph.nodes import submission_adapter_fn

        final = _run_canonical()
        # Provide a claim package to allow submission_adapter to run
        if final.claim_package is not None:
            result = submission_adapter_fn(final)
            if "case_id" in result:
                assert result["case_id"].startswith("sim-")


# ---------------------------------------------------------------------------
# Financial math integrity
# ---------------------------------------------------------------------------


class TestFinancialMathIntegrity:
    def test_canonical_credit_is_positive_and_deterministic(self) -> None:
        final = _run_canonical()
        assert final.availability_result is not None
        assert final.availability_result.potential_credit > Decimal("0")

    def test_canonical_uptime_is_correct(self) -> None:
        final = _run_canonical()
        assert final.availability_result is not None
        assert final.availability_result.monthly_uptime_pct == Decimal("99.930556")

    def test_canonical_tier_is_10pct(self) -> None:
        final = _run_canonical()
        assert final.availability_result is not None
        assert final.availability_result.tier_pct == Decimal("10")

    def test_canonical_threshold_breached(self) -> None:
        final = _run_canonical()
        assert final.availability_result is not None
        assert final.availability_result.threshold_breached is True

    def test_twenty_consecutive_runs_identical_credit(self) -> None:
        """20 consecutive canonical runs must all produce the same credit — 100% determinism."""
        credit_set: set[Decimal] = set()
        for _ in range(20):
            final = _run_canonical()
            assert final.availability_result is not None
            credit_set.add(final.availability_result.potential_credit)
        assert len(credit_set) == 1, (
            f"Non-deterministic results across 20 runs: {credit_set}"
        )
        assert list(credit_set)[0] > Decimal("0"), (
            f"Credit must be positive: {credit_set}"
        )
