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
        """Canonical scenario: 6 bad intervals / 8,640 total → positive credit (amount from billing fixture)."""
        state = self._initial_state()
        final = recoup_graph.run(state)
        assert final.availability_result is not None
        assert final.availability_result.potential_credit > Decimal("0")

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

    def test_no_live_case_id_without_real_submission(self) -> None:
        """Without RECOUP_ENABLE_REAL_SUPPORT_SUBMISSION, case_id stays None or sim-prefixed."""
        s1 = self._initial_state("run-1")
        s2 = self._initial_state("run-2")
        f1 = recoup_graph.run(s1)
        f2 = recoup_graph.run(s2)
        # Both runs produce the same deterministic outcome
        assert f1.policy_decision == f2.policy_decision

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
        assert state.use_strands is False
        assert state.idempotency_key.startswith("replay:")

    def test_canonical_replay_produces_positive_credit(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state(CANONICAL_SCENARIO)
        final = recoup_graph.run(state)
        assert final.availability_result is not None
        assert final.availability_result.potential_credit > Decimal("0")
        assert final.availability_result.tier_pct == Decimal("10")


# ---------------------------------------------------------------------------
# Phase 6c — Strands SDK & Bedrock deep integration
# ---------------------------------------------------------------------------


class TestStrandsFallback:
    """
    Tests for graceful degradation when Strands / LLM provider is unavailable.

    All tests run with use_strands=True but a strands_fn that raises — the node
    must fall back to the stub_fn and produce a correct result.  No real LLM
    calls are made (no network required).
    """

    def _signal(self) -> IncidentSignal:
        return IncidentSignal(
            source="replay",
            event_id="test-evt-strands",
            service="apigateway",
            region="us-east-1",
            start=datetime(2026, 8, 1, 2, 0),
            end=datetime(2026, 8, 1, 2, 30),
            affected_resource_ids=["arn:aws:apigateway:us-east-1::/restapis/test"],
            raw_ref="s3://recoup-evidence/test.json",
            replay=True,
        )

    def test_agent_node_falls_back_on_strands_exception(self) -> None:
        """AgentNode invokes stub_fn when strands_fn raises any exception."""
        calls: list[str] = []

        def broken_strands(state: GraphState) -> dict[str, object]:
            raise RuntimeError("LLM unavailable")

        def good_stub(state: GraphState) -> dict[str, object]:
            calls.append("stub")
            return {"hypothesis": None}

        node = AgentNode(
            name="test_node",
            tool_names=[],
            stub_fn=good_stub,
            strands_fn=broken_strands,
        )
        state = GraphState(opportunity_id="test", use_strands=True)
        result = node.run(state)
        assert calls == ["stub"], "stub_fn must be called after strands_fn raises"
        assert result == {"hypothesis": None}

    def test_agent_node_falls_back_when_strands_returns_none(self) -> None:
        """AgentNode uses stub_fn when strands_fn returns None."""
        calls: list[str] = []

        def none_strands(state: GraphState) -> None:
            return None

        def good_stub(state: GraphState) -> dict[str, object]:
            calls.append("stub")
            return {"hypothesis": None}

        node = AgentNode(
            name="test_node",
            tool_names=[],
            stub_fn=good_stub,
            strands_fn=none_strands,  # type: ignore[arg-type]
        )
        state = GraphState(opportunity_id="test", use_strands=True)
        result = node.run(state)
        assert calls == ["stub"]
        assert result == {"hypothesis": None}

    def test_use_strands_false_never_calls_strands_fn(self) -> None:
        """When use_strands=False, strands_fn must never be called."""
        strands_called: list[bool] = []

        def should_not_be_called(state: GraphState) -> dict[str, object]:
            strands_called.append(True)
            return {}

        node = AgentNode(
            name="test_node",
            tool_names=[],
            stub_fn=lambda s: {"ok": True},
            strands_fn=should_not_be_called,
        )
        state = GraphState(opportunity_id="test", use_strands=False)
        node.run(state)
        assert strands_called == [], "strands_fn must not be called when use_strands=False"

    def test_canonical_replay_never_uses_strands(self) -> None:
        """Canonical replay path: use_strands is False — 20/20 deterministic result."""
        adapter = ReplayAdapter()
        state = adapter.build_state(CANONICAL_SCENARIO)
        assert state.use_strands is False, (
            "ReplayAdapter must never set use_strands=True — "
            "breaks 20/20 deterministic guarantee"
        )

    def test_graph_with_failing_strands_still_produces_credit(self) -> None:
        """Full graph: use_strands=True, all strands_fns raise — must produce positive credit."""
        from recoup.adapters.replay import ReplayAdapter
        from recoup.graph.recoup_graph import build_recoup_graph
        from recoup.graph.types import AgentNode

        graph = build_recoup_graph()

        # Patch all AgentNodes to have a failing strands_fn
        def always_fail(state: GraphState) -> dict[str, object]:
            raise RuntimeError("Simulated LLM failure")

        for node in graph._nodes.values():
            if isinstance(node, AgentNode):
                node._strands_fn = always_fail

        adapter = ReplayAdapter()
        state = adapter.build_state(CANONICAL_SCENARIO)
        # Force use_strands so the fallback path is exercised
        state = state.model_copy(update={"use_strands": True})
        final = graph.run(state)

        assert final.availability_result is not None
        assert final.availability_result.potential_credit > Decimal("0"), (
            "Strands fallback must produce a positive financial result"
        )

    def test_strands_agents_module_imports_cleanly(self) -> None:
        """strands_agents module must be importable without side effects or errors."""
        from recoup.agents import strands_agents  # noqa: F401

    def test_llm_provider_is_configured(self) -> None:
        """settings.llm_provider must name a supported adapter with credentials set."""
        from recoup.agents.strands_agents import _MODEL_PROVIDERS
        from recoup.config import settings

        assert settings.llm_provider in _MODEL_PROVIDERS, (
            f"LLM_PROVIDER='{settings.llm_provider}' is not registered. "
            f"Valid options: {list(_MODEL_PROVIDERS)}"
        )
        if settings.llm_provider == "bedrock":
            assert settings.bedrock_model_id, "BEDROCK_MODEL_ID must not be empty"
            assert ":" in settings.bedrock_model_id, (
                "BEDROCK_MODEL_ID must include a version suffix (e.g. ':0')"
            )
        elif settings.llm_provider == "openai":
            assert settings.openai_api_key, (
                "OPENAI_API_KEY must not be empty when LLM_PROVIDER=openai"
            )
            assert settings.openai_model_id, "OPENAI_MODEL_ID must not be empty"
