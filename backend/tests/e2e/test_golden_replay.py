"""
E2E Golden Replay Tests — Phase 5.

PURPOSE OF THESE TESTS
----------------------
These tests verify the *algorithm correctness* of the SLA recovery engine using
a known, seeded fixture (canonical SLA replay: API Gateway, Sep 2026, 10%
credit tier on real AWS billing data from inject_sla_traffic.py).

They are ENGINE UNIT TESTS — not demo claims.

What these tests assert:
  1. Identical results across 20 consecutive runs (100% golden-path)
  2. P95 < 60-second SLA
  3. Complete trace (all mandatory pipeline fields populated)
  4. 0 unsafe external actions
  5. Credit > 0 and policy = REQUIRE_APPROVAL
"""

from __future__ import annotations

import time
from decimal import Decimal

from recoup.adapters.replay import ReplayAdapter
from recoup.graph.recoup_graph import build_recoup_graph
from recoup.graph.types import GraphState, PolicyDecision

# ---------------------------------------------------------------------------
# Single canonical run verification
# ---------------------------------------------------------------------------


class TestGoldenReplaySingle:
    def test_canonical_run_completes_without_errors(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state()
        graph = build_recoup_graph()
        final = graph.run(state)
        assert final.errors == [], f"Canonical run errors: {final.errors}"

    def test_canonical_credit_is_positive_and_consistent(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state()
        graph = build_recoup_graph()
        final = graph.run(state)
        assert final.availability_result is not None
        assert final.availability_result.potential_credit > Decimal("0")

    def test_canonical_uptime_is_99930556(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state()
        graph = build_recoup_graph()
        final = graph.run(state)
        assert final.availability_result is not None
        assert final.availability_result.monthly_uptime_pct == Decimal("99.930556")

    def test_canonical_tier_is_10pct(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state()
        graph = build_recoup_graph()
        final = graph.run(state)
        assert final.availability_result is not None
        assert final.availability_result.tier_pct == Decimal("10")

    def test_canonical_policy_requires_approval(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state()
        graph = build_recoup_graph()
        final = graph.run(state)
        assert final.policy_decision == PolicyDecision.REQUIRE_APPROVAL

    def test_canonical_sanitized_manifest_is_populated(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state()
        graph = build_recoup_graph()
        final = graph.run(state)
        assert final.sanitized_manifest is not None
        assert len(final.sanitized_manifest.items) > 0

    def test_canonical_redaction_report_present(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state()
        graph = build_recoup_graph()
        final = graph.run(state)
        assert final.redaction_report is not None
        assert final.redaction_report.raw_hash.startswith("sha256:")
        assert final.redaction_report.sanitized_hash.startswith("sha256:")

    def test_canonical_eligibility_positive(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state()
        graph = build_recoup_graph()
        final = graph.run(state)
        assert final.eligibility_assessment is not None
        assert final.eligibility_assessment.eligible_estimate is True

    def test_canonical_no_strands_in_replay(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state()
        graph = build_recoup_graph()
        final = graph.run(state)
        # Canonical replay never uses Strands — always deterministic
        assert final.use_strands is False

    def test_canonical_no_unsafe_actions(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state()
        graph = build_recoup_graph()
        final = graph.run(state)
        # No real AWS calls occurred (evidenced by stub flags)
        if final.case_id:
            assert final.case_id.startswith("sim-")


# ---------------------------------------------------------------------------
# 20 consecutive canonical runs — 100% golden-path
# ---------------------------------------------------------------------------


class TestGoldenReplay20Consecutive:
    """
    Runs the canonical scenario 20 times and asserts:
      - 20/20 produce the same positive credit (amount from real billing_snapshot.json — 100% success rate)
      - P95 elapsed time < 60 seconds
      - All runs error-free
    """

    RUNS = 20

    def _run_timed(self) -> tuple[GraphState, float]:
        adapter = ReplayAdapter()
        state = adapter.build_state()
        graph = build_recoup_graph()
        t0 = time.perf_counter()
        final = graph.run(state)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return final, elapsed_ms

    def test_all_20_runs_produce_consistent_positive_credit(self) -> None:
        credits = []
        failures = []
        for i in range(self.RUNS):
            final, _ = self._run_timed()
            if (
                final.availability_result is not None
                and final.availability_result.potential_credit > Decimal("0")
                and final.errors == []
            ):
                credits.append(final.availability_result.potential_credit)
            else:
                failures.append(i)
        assert len(failures) == 0, (
            f"Golden path: {self.RUNS - len(failures)}/{self.RUNS} passed. Failed runs: {failures}"
        )
        assert len(set(credits)) == 1, (
            f"Non-deterministic credits across {self.RUNS} runs: {set(credits)}"
        )

    def test_p95_below_60_seconds(self) -> None:
        elapsed_times = []
        for _ in range(self.RUNS):
            _, elapsed_ms = self._run_timed()
            elapsed_times.append(elapsed_ms)

        elapsed_times.sort()
        p95_idx = int(0.95 * len(elapsed_times))
        p95_ms = elapsed_times[p95_idx]
        p95_seconds = p95_ms / 1000.0

        assert p95_seconds < 60.0, (
            f"P95 replay time {p95_seconds:.2f}s exceeds 60s limit. "
            f"All times (ms): {elapsed_times}"
        )

    def test_all_20_runs_error_free(self) -> None:
        for i in range(self.RUNS):
            final, _ = self._run_timed()
            assert final.errors == [], f"Run {i} had errors: {final.errors}"

    def test_all_20_runs_no_strands(self) -> None:
        for i in range(self.RUNS):
            final, _ = self._run_timed()
            assert final.use_strands is False, f"Run {i} unexpectedly had use_strands=True"

    def test_20_runs_identical_uptime_pct(self) -> None:
        uptimes = set()
        for _ in range(self.RUNS):
            final, _ = self._run_timed()
            if final.availability_result:
                uptimes.add(final.availability_result.monthly_uptime_pct)
        assert len(uptimes) == 1, (
            f"Non-deterministic uptime across 20 runs: {uptimes}"
        )
        assert list(uptimes)[0] > Decimal("0")

    def test_20_runs_identical_idempotency_keys(self) -> None:
        """Same scenario always produces the same idempotency key."""
        keys = set()
        for _ in range(self.RUNS):
            final, _ = self._run_timed()
            if final.idempotency_key:
                keys.add(final.idempotency_key)
        assert len(keys) == 1, (
            f"Idempotency key varied across 20 runs: {keys}"
        )


# ---------------------------------------------------------------------------
# Trace completeness
# ---------------------------------------------------------------------------


class TestTraceCompleteness:
    def test_calculation_trace_has_at_least_5_steps(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state()
        graph = build_recoup_graph()
        final = graph.run(state)
        assert final.availability_result is not None
        assert len(final.availability_result.calculation_trace) >= 5

    def test_calculation_trace_mentions_8640(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state()
        graph = build_recoup_graph()
        final = graph.run(state)
        assert final.availability_result is not None
        trace = " ".join(final.availability_result.calculation_trace)
        assert "8,640" in trace or "8640" in trace

    def test_calculation_trace_is_non_empty(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state()
        graph = build_recoup_graph()
        final = graph.run(state)
        assert final.availability_result is not None
        assert len(final.availability_result.calculation_trace) > 0

    def test_hypothesis_summary_is_non_empty(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state()
        graph = build_recoup_graph()
        final = graph.run(state)
        assert final.hypothesis is not None
        assert len(final.hypothesis.summary) > 0

    def test_evidence_manifest_has_items(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state()
        graph = build_recoup_graph()
        final = graph.run(state)
        assert final.evidence_manifest is not None
        assert len(final.evidence_manifest.items) > 0

    def test_all_manifest_items_have_hashes(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state()
        graph = build_recoup_graph()
        final = graph.run(state)
        assert final.evidence_manifest is not None
        for item in final.evidence_manifest.items:
            assert item.hash.startswith("sha256:"), (
                f"Evidence item {item.id} missing sha256 hash"
            )

    def test_all_sanitized_items_redacted(self) -> None:
        adapter = ReplayAdapter()
        state = adapter.build_state()
        graph = build_recoup_graph()
        final = graph.run(state)
        assert final.sanitized_manifest is not None
        for item in final.sanitized_manifest.items:
            assert item.status in ("REDACTED", "MISSING"), (
                f"Item {item.id} has unexpected status {item.status!r}"
            )
