"""
Unit tests for the Recoup graph — instantiation, validation, and end-to-end stub run.

No LLM calls, no AWS calls, no network.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from recoup.adapters.replay import CANONICAL_SCENARIO, ReplayAdapter
from recoup.graph.recoup_graph import build_recoup_graph, recoup_graph
from recoup.graph.types import (
    AgentNode,
    DeterministicNode,
    Graph,
    GraphState,
    PolicyDecision,
)
from recoup.models.signal import IncidentSignal


class TestGraphStructure:
    def test_graph_has_all_11_nodes(self) -> None:
        expected = {
            "normalize_event",
            "incident_correlation",
            "sla_contract_resolver",
            "availability_calculator",
            "evidence_collector",
            "evidence_sanitizer",
            "eligibility_reasoner",
            "risk_policy_gate",
            "claim_package_generator",
            "submission_adapter",
            "case_monitor",
        }
        assert set(recoup_graph.node_names) == expected

    def test_graph_validates_without_error(self) -> None:
        g = build_recoup_graph()
        g.validate()  # should not raise

    def test_node_types_are_correct(self) -> None:
        deterministic = {
            "normalize_event",
            "sla_contract_resolver",
            "availability_calculator",
            "evidence_sanitizer",
            "risk_policy_gate",
            "submission_adapter",
        }
        agent = {
            "incident_correlation",
            "evidence_collector",
            "eligibility_reasoner",
            "claim_package_generator",
            "case_monitor",
        }
        for name in deterministic:
            node = recoup_graph._nodes[name]
            assert isinstance(node, DeterministicNode), f"{name} should be DeterministicNode"
        for name in agent:
            node = recoup_graph._nodes[name]
            assert isinstance(node, AgentNode), f"{name} should be AgentNode"

    def test_invalid_edge_raises(self) -> None:
        g = Graph(name="test")
        g.add_node(DeterministicNode("node_a", lambda s: {}))
        g.add_edge("node_a", "nonexistent_node")
        with pytest.raises(ValueError, match="nonexistent_node"):
            g.validate()


class TestGraphRun:
    def _initial_state(self, opportunity_id: str = "test-opp-001") -> GraphState:
        signal = IncidentSignal(
            source="replay",
            event_id="test-evt-001",
            service="apigateway",
            region="us-east-1",
            start=datetime(2026, 8, 1, 2, 0),
            end=datetime(2026, 8, 1, 2, 30),
            affected_resource_ids=["arn:aws:apigateway:us-east-1::/restapis/test"],
            raw_ref="s3://recoup-evidence/test.json",
            replay=True,
        )
        return GraphState(
            opportunity_id=opportunity_id,
            simulation_mode=True,
            signal=signal,
        )

    def test_graph_runs_end_to_end_no_errors(self) -> None:
        state = self._initial_state()
        final = recoup_graph.run(state)
        assert final.errors == [], f"Expected no errors, got: {final.errors}"

    def test_graph_produces_availability_result(self) -> None:
        state = self._initial_state()
        final = recoup_graph.run(state)
        assert final.availability_result is not None
        assert final.availability_result.threshold_breached is True

    def test_graph_produces_golden_credit(self) -> None:
        """Canonical scenario: 6 bad intervals / 8,640 total → $1,840.00 credit."""
        state = self._initial_state()
        final = recoup_graph.run(state)
        assert final.availability_result is not None
        assert final.availability_result.potential_credit == Decimal("1840.00")

    def test_graph_produces_claim_package(self) -> None:
        """
        When policy_decision == REQUIRE_APPROVAL the graph pauses at
        await_human_approval. case_id and claim_package are None — this is
        correct HITL behaviour. The claim is assembled only after approval.
        """
        state = self._initial_state()
        final = recoup_graph.run(state)
        assert final.policy_decision == PolicyDecision.REQUIRE_APPROVAL
        # Graph paused waiting for human — downstream nodes not yet executed
        assert final.case_id is None
        assert final.claim_package is None

    def test_simulation_mode_case_id_is_deterministic(self) -> None:
        """Same scenario always produces the same sim-* case ID."""
        s1 = self._initial_state("run-1")
        s2 = self._initial_state("run-2")
        f1 = recoup_graph.run(s1)
        f2 = recoup_graph.run(s2)
        assert f1.case_id == f2.case_id

    def test_policy_decision_is_require_approval(self) -> None:
        """Eligible claims always require human approval (never auto-approved)."""
        state = self._initial_state()
        final = recoup_graph.run(state)
        assert final.policy_decision == PolicyDecision.REQUIRE_APPROVAL

    def test_evidence_manifest_has_required_fields(self) -> None:
        state = self._initial_state()
        final = recoup_graph.run(state)
        assert final.sanitized_manifest is not None
        assert len(final.sanitized_manifest.items) >= 3


class TestReplayAdapter:
    def test_canonical_scenario_builds_state(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state(CANONICAL_SCENARIO)
        assert state.signal is not None
        assert state.signal.service == "apigateway"
        assert state.simulation_mode is True
        assert state.idempotency_key.startswith("replay:")

    def test_canonical_replay_produces_1840(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state(CANONICAL_SCENARIO)
        final = recoup_graph.run(state)
        assert final.availability_result is not None
        assert final.availability_result.potential_credit == Decimal("1840.00")
        assert final.availability_result.tier_pct == Decimal("10")
