"""
Phase 2 golden acceptance tests — Verified Replay & SLA Recovery Engine.

All tests are deterministic: no LLM calls, no AWS calls, no network.
Every test must pass before every commit to main.

Test coverage:
  - Fixture files exist and have correct structure
  - Fixture intervals: 8,640 total, exactly 6 at 0% availability
  - Fixture billing snapshot: real AWS billing amount from inject_sla_traffic.py (e.g. $3.51 for demo account)
  - ReplayAdapter loads fixture data into GraphState.replay_fixtures
  - incident_correlation uses fixture intervals (fixture-driven path)
  - Full end-to-end replay: consistent positive credit on every run (amount from real billing fixture)
  - 20 consecutive runs: identical result (determinism proof)
  - use_strands=False enforced throughout (canonical replay stays deterministic)
  - GraphState.replay_fixtures round-trip
  - Graph.run() on_node_start / on_node_complete callbacks fire
  - expected_output.json matches what the calculator produces
  - replay_run.py headless script validates cleanly (import + validate)
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from recoup.adapters.replay import CANONICAL_SCENARIO, ReplayAdapter
from recoup.graph.recoup_graph import recoup_graph
from recoup.graph.types import GraphState, PolicyDecision

REPO_ROOT = Path(__file__).parent.parent.parent.parent  # backend/tests/unit/../../.. = repo root
CANONICAL_DIR = REPO_ROOT / "eval_fixtures" / "sla" / "api_gateway" / "canonical"

# Load EXPECTED_CREDIT dynamically from the fixture so tests stay valid
# regardless of the billing amount (real AWS data from inject_sla_traffic.py)
_expected_output = json.loads((CANONICAL_DIR / "expected_output.json").read_text())
EXPECTED_CREDIT = Decimal(_expected_output["calculator_outputs"]["potential_credit"])
EXPECTED_UPTIME = Decimal("99.930556")
EXPECTED_TIER = Decimal("10")
TOTAL_INTERVALS = 8_640
UNAVAILABLE_INTERVALS = 6


# ---------------------------------------------------------------------------
# Fixture file integrity
# ---------------------------------------------------------------------------


class TestFixtureFiles:
    def test_canonical_dir_exists(self) -> None:
        assert CANONICAL_DIR.is_dir(), f"Missing: {CANONICAL_DIR}"

    @pytest.mark.parametrize("filename", [
        "health_event.json",
        "metric_series.json",
        "billing_snapshot.json",
        "cloudtrail_events.json",
        "sla_contract_ref.yaml",
        "expected_output.json",
    ])
    def test_fixture_file_exists(self, filename: str) -> None:
        assert (CANONICAL_DIR / filename).exists(), f"Missing fixture: {filename}"

    def test_health_event_has_replay_flag(self) -> None:
        data = json.loads((CANONICAL_DIR / "health_event.json").read_text())
        assert data.get("_recoup_replay") is True

    def test_health_event_service_is_apigateway(self) -> None:
        data = json.loads((CANONICAL_DIR / "health_event.json").read_text())
        assert data["detail"]["service"] == "APIGATEWAY"

    def test_health_event_region(self) -> None:
        data = json.loads((CANONICAL_DIR / "health_event.json").read_text())
        assert data["detail"]["region"] == "us-east-1"

    def test_metric_series_total_intervals(self) -> None:
        data = json.loads((CANONICAL_DIR / "metric_series.json").read_text())
        assert data["total_intervals"] == TOTAL_INTERVALS
        assert len(data["intervals"]) == TOTAL_INTERVALS

    def test_metric_series_unavailable_count(self) -> None:
        data = json.loads((CANONICAL_DIR / "metric_series.json").read_text())
        bad = [iv for iv in data["intervals"] if iv["availability_pct"] == "0.0"]
        assert len(bad) == UNAVAILABLE_INTERVALS

    def test_metric_series_all_good_intervals_are_100pct(self) -> None:
        data = json.loads((CANONICAL_DIR / "metric_series.json").read_text())
        good = [iv for iv in data["intervals"] if iv["availability_pct"] != "0.0"]
        assert all(iv["availability_pct"] == "100.0" for iv in good)

    def test_billing_snapshot_amount(self) -> None:
        data = json.loads((CANONICAL_DIR / "billing_snapshot.json").read_text())
        assert Decimal(data["billed_amount_usd"]) > Decimal("0")

    def test_billing_snapshot_service(self) -> None:
        data = json.loads((CANONICAL_DIR / "billing_snapshot.json").read_text())
        assert "apigateway" in data["service"].lower() or "ApiGateway" in data["service"]

    def test_cloudtrail_no_customer_errors(self) -> None:
        data = json.loads((CANONICAL_DIR / "cloudtrail_events.json").read_text())
        assert data.get("verdict") == "no_customer_caused_errors"
        # v1.1 fixture may include infra events (e.g. CloudFormation); verdict still excludes customer-caused errors.
        assert isinstance(data.get("events"), list)

    def test_expected_output_credit(self) -> None:
        data = json.loads((CANONICAL_DIR / "expected_output.json").read_text())
        assert Decimal(data["calculator_outputs"]["potential_credit"]) == EXPECTED_CREDIT

    def test_expected_output_uptime(self) -> None:
        data = json.loads((CANONICAL_DIR / "expected_output.json").read_text())
        assert Decimal(data["calculator_outputs"]["monthly_uptime_pct"]) == EXPECTED_UPTIME

    def test_expected_output_tier(self) -> None:
        data = json.loads((CANONICAL_DIR / "expected_output.json").read_text())
        assert Decimal(data["calculator_outputs"]["tier_pct"]) == EXPECTED_TIER

    def test_expected_output_matches_calculator(self) -> None:
        """expected_output.json must be consistent with what the calculator produces."""
        expected = json.loads((CANONICAL_DIR / "expected_output.json").read_text())
        series = json.loads((CANONICAL_DIR / "metric_series.json").read_text())
        billing = json.loads((CANONICAL_DIR / "billing_snapshot.json").read_text())

        from recoup.engines.calculator import calculate_availability_and_credit
        from recoup.engines.sla_resolver import resolve_sla_contract
        from recoup.models.availability import AvailabilityInterval

        contract = resolve_sla_contract(
            service="apigateway",
            region="us-east-1",
            incident_date=__import__("datetime").date(2026, 8, 1),
        )
        intervals = [
            AvailabilityInterval(
                start=iv["start"],
                end=iv["end"],
                availability_pct=Decimal(iv["availability_pct"]),
                request_count=iv["request_count"],
                error_count=iv["error_count"],
                evidence_refs=[],
            )
            for iv in series["intervals"]
        ]
        billed_charges = Decimal(billing["billed_amount_usd"])
        result = calculate_availability_and_credit(
            intervals=intervals,
            contract=contract,
            billed_charges=billed_charges,
        )

        outputs = expected["calculator_outputs"]
        assert result.monthly_uptime_pct == Decimal(outputs["monthly_uptime_pct"])
        assert result.potential_credit == Decimal(outputs["potential_credit"])
        assert result.tier_pct == Decimal(outputs["tier_pct"])
        assert result.threshold_breached == outputs["threshold_breached"]


# ---------------------------------------------------------------------------
# ReplayAdapter — fixture loading
# ---------------------------------------------------------------------------


class TestReplayAdapterFixtureLoading:
    def test_build_state_populates_replay_fixtures(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state(CANONICAL_SCENARIO)
        assert isinstance(state.replay_fixtures, dict)
        assert len(state.replay_fixtures) > 0

    def test_replay_fixtures_contains_metric_series(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state(CANONICAL_SCENARIO)
        assert "metric_series" in state.replay_fixtures

    def test_replay_fixtures_contains_billing_snapshot(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state(CANONICAL_SCENARIO)
        assert "billing_snapshot" in state.replay_fixtures

    def test_replay_fixtures_contains_health_event(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state(CANONICAL_SCENARIO)
        assert "health_event" in state.replay_fixtures

    def test_metric_series_fixture_has_correct_interval_count(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state(CANONICAL_SCENARIO)
        series = state.replay_fixtures["metric_series"]
        assert series["total_intervals"] == TOTAL_INTERVALS
        assert len(series["intervals"]) == TOTAL_INTERVALS

    def test_billing_fixture_has_correct_amount(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state(CANONICAL_SCENARIO)
        billing = state.replay_fixtures["billing_snapshot"]
        assert Decimal(billing["billed_amount_usd"]) > Decimal("0")

    def test_adapter_without_fixtures_dir_still_builds_state(self) -> None:
        """Adapter must work even if fixtures dir doesn't exist (e.g. CI clone)."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = ReplayAdapter(fixtures_dir=Path(tmpdir))
            state = adapter.build_state(CANONICAL_SCENARIO)
            assert state.replay_fixtures == {}  # empty but not None
            assert state.signal is not None


# ---------------------------------------------------------------------------
# incident_correlation fixture-driven path
# ---------------------------------------------------------------------------


class TestIncidentCorrelationFixturePath:
    def _run_to_hypothesis(self) -> GraphState:
        adapter = ReplayAdapter()
        state = adapter.build_state(CANONICAL_SCENARIO)
        final = recoup_graph.run(state)
        return final

    def test_hypothesis_is_produced(self) -> None:
        final = self._run_to_hypothesis()
        assert final.hypothesis is not None

    def test_hypothesis_has_correct_interval_count(self) -> None:
        final = self._run_to_hypothesis()
        assert final.hypothesis is not None
        assert len(final.hypothesis.availability_intervals) == TOTAL_INTERVALS

    def test_hypothesis_has_correct_unavailable_count(self) -> None:
        final = self._run_to_hypothesis()
        assert final.hypothesis is not None
        bad = [
            iv for iv in final.hypothesis.availability_intervals
            if iv.availability_pct < Decimal("100")
        ]
        assert len(bad) == UNAVAILABLE_INTERVALS

    def test_hypothesis_billed_charges_from_fixture(self) -> None:
        final = self._run_to_hypothesis()
        assert final.hypothesis is not None
        assert final.hypothesis.billed_charges > Decimal("0")

    def test_hypothesis_replay_flag_propagated(self) -> None:
        final = self._run_to_hypothesis()
        assert final.hypothesis is not None
        assert final.hypothesis.replay is True


# ---------------------------------------------------------------------------
# End-to-end golden acceptance tests
# ---------------------------------------------------------------------------


class TestEndToEndGoldenReplay:
    def _run(self, opportunity_id: str = "test-phase2-e2e") -> GraphState:
        adapter = ReplayAdapter()
        state = adapter.build_state(CANONICAL_SCENARIO, opportunity_id=opportunity_id)
        return recoup_graph.run(state)

    def test_no_errors(self) -> None:
        final = self._run()
        assert final.errors == [], f"Expected no errors, got: {final.errors}"

    def test_monthly_uptime_pct(self) -> None:
        final = self._run()
        assert final.availability_result is not None
        assert final.availability_result.monthly_uptime_pct == EXPECTED_UPTIME

    def test_threshold_breached(self) -> None:
        final = self._run()
        assert final.availability_result is not None
        assert final.availability_result.threshold_breached is True

    def test_credit_tier(self) -> None:
        final = self._run()
        assert final.availability_result is not None
        assert final.availability_result.tier_pct == EXPECTED_TIER

    def test_potential_credit_matches_fixture(self) -> None:
        """Credit matches expected_output.json (real billing from inject_sla_traffic.py)."""
        final = self._run()
        assert final.availability_result is not None
        assert final.availability_result.potential_credit == EXPECTED_CREDIT

    def test_no_strands_in_canonical_replay(self) -> None:
        """Canonical replay never invokes Strands — use_strands stays False."""
        final = self._run()
        assert final.use_strands is False

    def test_policy_decision_require_approval(self) -> None:
        """All financial actions require explicit human approval (never auto-approved)."""
        final = self._run()
        assert final.policy_decision == PolicyDecision.REQUIRE_APPROVAL

    def test_graph_pauses_at_hitl_gate(self) -> None:
        """case_id is None because the HITL gate pauses downstream nodes."""
        final = self._run()
        assert final.case_id is None
        assert final.claim_package is None

    def test_evidence_manifest_present(self) -> None:
        final = self._run()
        assert final.sanitized_manifest is not None
        assert len(final.sanitized_manifest.items) >= 3

    def test_contract_loaded(self) -> None:
        final = self._run()
        assert final.contract is not None
        assert final.contract.service == "apigateway"

    def test_calculation_trace_non_empty(self) -> None:
        final = self._run()
        assert final.availability_result is not None
        assert len(final.availability_result.calculation_trace) >= 5

    def test_eligibility_assessment_eligible(self) -> None:
        final = self._run()
        assert final.eligibility_assessment is not None
        assert final.eligibility_assessment.eligible_estimate is True


# ---------------------------------------------------------------------------
# 20 consecutive runs — determinism proof
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_20_consecutive_runs_same_credit(self) -> None:
        """Golden: identical credit on 20 consecutive runs without any seed."""
        adapter = ReplayAdapter()
        credit_amounts: list[Decimal] = []
        uptimes: list[Decimal] = []

        for i in range(20):
            state = adapter.build_state(CANONICAL_SCENARIO, opportunity_id=f"det-run-{i:04d}")
            final = recoup_graph.run(state)
            assert final.availability_result is not None
            credit_amounts.append(final.availability_result.potential_credit)
            uptimes.append(final.availability_result.monthly_uptime_pct)

        assert len(set(credit_amounts)) == 1, (
            f"Non-deterministic credits: {set(credit_amounts)}"
        )
        assert credit_amounts[0] > Decimal("0"), (
            f"Credit must be positive, got: {credit_amounts[0]}"
        )
        assert all(u == EXPECTED_UPTIME for u in uptimes), (
            f"Non-deterministic uptimes: {set(uptimes)}"
        )

    def test_idempotency_key_stable_across_runs(self) -> None:
        """Same scenario always produces the same idempotency key."""
        adapter = ReplayAdapter()
        keys = set()
        for _ in range(5):
            state = adapter.build_state(CANONICAL_SCENARIO)
            keys.add(state.idempotency_key)
        assert len(keys) == 1, f"Idempotency key changed between runs: {keys}"


# ---------------------------------------------------------------------------
# Graph.run() callback support
# ---------------------------------------------------------------------------


class TestGraphCallbacks:
    def test_on_node_complete_fires_for_all_nodes(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state(CANONICAL_SCENARIO, opportunity_id="cb-test-001")

        completed: list[str] = []

        def on_complete(node_name: str, _state: GraphState, _ms: int) -> None:
            completed.append(node_name)

        recoup_graph.run(state, on_node_complete=on_complete)

        expected_nodes = {
            "normalize_event",
            "incident_correlation",
            "sla_contract_resolver",
            "availability_calculator",
            "evidence_collector",
            "evidence_sanitizer",
            "eligibility_reasoner",
            "risk_policy_gate",
        }
        assert expected_nodes.issubset(set(completed)), (
            f"Missing callbacks for: {expected_nodes - set(completed)}"
        )

    def test_on_node_start_fires_for_all_nodes(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state(CANONICAL_SCENARIO, opportunity_id="cb-test-002")

        started: list[str] = []
        recoup_graph.run(state, on_node_start=lambda n: started.append(n))

        assert "normalize_event" in started
        assert "availability_calculator" in started

    def test_callback_receives_updated_state(self) -> None:
        """The state passed to on_node_complete reflects the node's output."""
        adapter = ReplayAdapter()
        state = adapter.build_state(CANONICAL_SCENARIO, opportunity_id="cb-test-003")

        credit_after_calculator: list[Decimal] = []

        def on_complete(node_name: str, s: GraphState, _ms: int) -> None:
            if node_name == "availability_calculator" and s.availability_result:
                credit_after_calculator.append(s.availability_result.potential_credit)

        recoup_graph.run(state, on_node_complete=on_complete)
        assert credit_after_calculator == [EXPECTED_CREDIT]

    def test_callback_duration_ms_is_non_negative(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state(CANONICAL_SCENARIO, opportunity_id="cb-test-004")
        durations: list[int] = []
        recoup_graph.run(state, on_node_complete=lambda n, s, ms: durations.append(ms))
        assert all(ms >= 0 for ms in durations)

    def test_no_callback_still_works(self) -> None:
        """graph.run() without callbacks must still produce the correct result."""
        adapter = ReplayAdapter()
        state = adapter.build_state(CANONICAL_SCENARIO, opportunity_id="cb-test-005")
        final = recoup_graph.run(state)
        assert final.availability_result is not None
        assert final.availability_result.potential_credit == EXPECTED_CREDIT
