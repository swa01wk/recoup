"""
Unit tests for the DynamoDB-backed state machine.

Uses the in-memory fallback — no AWS credentials required.
"""

from __future__ import annotations

import pytest

from recoup.graph.state_machine import (
    InMemoryStateMachine,
    StaleVersionError,
    StateMachineError,
    assert_valid_transition,
)
from recoup.models.opportunity import OpportunityState


class TestTransitionTable:
    def test_valid_transition_detected_to_investigating(self) -> None:
        assert_valid_transition(OpportunityState.DETECTED, OpportunityState.INVESTIGATING)

    def test_invalid_transition_detected_to_recovered(self) -> None:
        with pytest.raises(StateMachineError, match="DETECTED → RECOVERED"):
            assert_valid_transition(OpportunityState.DETECTED, OpportunityState.RECOVERED)

    def test_terminal_state_has_no_outgoing(self) -> None:
        for terminal in [
            OpportunityState.RECOVERED,
            OpportunityState.REJECTED,
            OpportunityState.DENIED,
            OpportunityState.FAILED,
        ]:
            with pytest.raises(StateMachineError):
                assert_valid_transition(terminal, OpportunityState.INVESTIGATING)


class TestInMemoryStateMachine:
    def setup_method(self) -> None:
        self.sm = InMemoryStateMachine()
        self.sm.reset()

    def test_first_transition_creates_record(self) -> None:
        new_version = self.sm.transition(
            "opp-001", OpportunityState.INVESTIGATING, expected_version=0
        )
        assert new_version == 1

    def test_version_increments_on_each_transition(self) -> None:
        self.sm.transition("opp-001", OpportunityState.INVESTIGATING, expected_version=0)
        new_version = self.sm.transition(
            "opp-001", OpportunityState.EVIDENCE_READY, expected_version=1
        )
        assert new_version == 2

    def test_stale_version_raises(self) -> None:
        self.sm.transition("opp-001", OpportunityState.INVESTIGATING, expected_version=0)
        with pytest.raises(StaleVersionError):
            # Expected version 0 is now stale — the record is at version 1
            self.sm.transition("opp-001", OpportunityState.EVIDENCE_READY, expected_version=0)

    def test_invalid_transition_raises(self) -> None:
        self.sm.transition("opp-001", OpportunityState.INVESTIGATING, expected_version=0)
        with pytest.raises(StateMachineError):
            # Can't jump from INVESTIGATING to APPROVED
            self.sm.transition("opp-001", OpportunityState.APPROVED, expected_version=1)

    def test_get_returns_current_record(self) -> None:
        self.sm.transition("opp-002", OpportunityState.INVESTIGATING, expected_version=0)
        record = self.sm.get("opp-002")
        assert record is not None
        assert record["state"] == OpportunityState.INVESTIGATING.value
        assert record["state_version"] == 1

    def test_get_returns_none_for_unknown_id(self) -> None:
        assert self.sm.get("opp-nonexistent") is None

    def test_full_happy_path(self) -> None:
        """Walk through the full state machine from DETECTED to RECOVERED."""
        sm = self.sm
        transitions = [
            (OpportunityState.INVESTIGATING, 0),
            (OpportunityState.EVIDENCE_READY, 1),
            (OpportunityState.ELIGIBILITY_REVIEWED, 2),
            (OpportunityState.AWAITING_APPROVAL, 3),
            (OpportunityState.APPROVED, 4),
            (OpportunityState.SUBMITTING, 5),
            (OpportunityState.SUBMITTED, 6),
            (OpportunityState.MONITORING, 7),
            (OpportunityState.RECOVERED, 8),
        ]
        for target, version in transitions:
            sm.transition("opp-golden", target, expected_version=version)
        record = sm.get("opp-golden")
        assert record["state"] == OpportunityState.RECOVERED.value
        assert record["state_version"] == 9
