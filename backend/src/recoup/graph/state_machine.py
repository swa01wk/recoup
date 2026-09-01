"""
DynamoDB-backed state machine for RecoveryOpportunity.

All state transitions are atomic conditional writes with optimistic locking
(state_version). Concurrent writers race; the loser retries or surfaces an
error — the winner's write is the canonical state.

In Phase 1 / local runs, if DynamoDB is unavailable the in-memory fallback
is used automatically so unit tests don't need AWS credentials.
"""

from __future__ import annotations

import logging
from typing import Any

import boto3
from botocore.exceptions import ClientError

from ..config import settings
from ..models.opportunity import OpportunityState

log = logging.getLogger(__name__)

# DynamoDB error code for a failed ConditionExpression
_CONDITION_FAILED = "ConditionalCheckFailedException"


class StateMachineError(Exception):
    """Raised when a state transition is rejected."""


class StaleVersionError(StateMachineError):
    """Raised when the expected state_version no longer matches (optimistic lock)."""


# ---------------------------------------------------------------------------
# Valid transitions — source → set of allowed targets
# ---------------------------------------------------------------------------

TRANSITIONS: dict[OpportunityState, set[OpportunityState]] = {
    OpportunityState.DETECTED: {OpportunityState.INVESTIGATING},
    OpportunityState.INVESTIGATING: {
        OpportunityState.EVIDENCE_READY,
        OpportunityState.NEEDS_EVIDENCE,
    },
    OpportunityState.NEEDS_EVIDENCE: {OpportunityState.INVESTIGATING},
    OpportunityState.EVIDENCE_READY: {OpportunityState.ELIGIBILITY_REVIEWED},
    OpportunityState.ELIGIBILITY_REVIEWED: {
        OpportunityState.AWAITING_APPROVAL,
        OpportunityState.DENIED,
        OpportunityState.FAILED,
    },
    OpportunityState.AWAITING_APPROVAL: {
        OpportunityState.APPROVED,
        OpportunityState.DENIED,
    },
    OpportunityState.APPROVED: {OpportunityState.SUBMITTING},
    OpportunityState.SUBMITTING: {
        OpportunityState.SUBMITTED,
        OpportunityState.FAILED,
    },
    OpportunityState.SUBMITTED: {OpportunityState.MONITORING},
    OpportunityState.MONITORING: {
        OpportunityState.RECOVERED,
        OpportunityState.REJECTED,
        OpportunityState.NEEDS_FOLLOWUP,
    },
    # Terminal states — no outgoing transitions
    OpportunityState.RECOVERED: set(),
    OpportunityState.REJECTED: set(),
    OpportunityState.DENIED: set(),
    OpportunityState.FAILED: set(),
    OpportunityState.NEEDS_FOLLOWUP: set(),
}


def assert_valid_transition(
    current: OpportunityState, target: OpportunityState
) -> None:
    """Raise StateMachineError if the transition is not in the allowed set."""
    allowed = TRANSITIONS.get(current, set())
    if target not in allowed:
        raise StateMachineError(
            f"Invalid transition: {current.value} → {target.value}. "
            f"Allowed from {current.value}: {[s.value for s in allowed]}"
        )


# ---------------------------------------------------------------------------
# In-memory fallback (unit tests / local dev without DynamoDB)
# ---------------------------------------------------------------------------

_in_memory_store: dict[str, dict[str, Any]] = {}


class InMemoryStateMachine:
    """Thread-unsafe in-memory store. For unit tests only."""

    def transition(
        self,
        opportunity_id: str,
        new_state: OpportunityState,
        expected_version: int,
        extra_attrs: dict[str, Any] | None = None,
    ) -> int:
        record = _in_memory_store.get(opportunity_id)
        if record is None:
            # Auto-create on first transition
            _in_memory_store[opportunity_id] = {
                "id": opportunity_id,
                "state": OpportunityState.DETECTED.value,
                "state_version": 0,
            }
            record = _in_memory_store[opportunity_id]

        current = OpportunityState(record["state"])
        assert_valid_transition(current, new_state)

        if record["state_version"] != expected_version:
            raise StaleVersionError(
                f"Expected version {expected_version}, got {record['state_version']}"
            )

        record["state"] = new_state.value
        record["state_version"] = expected_version + 1
        if extra_attrs:
            record.update(extra_attrs)

        return record["state_version"]

    def get(self, opportunity_id: str) -> dict[str, Any] | None:
        return _in_memory_store.get(opportunity_id)

    def upsert(self, opportunity_id: str, attrs: dict[str, Any]) -> None:
        if opportunity_id not in _in_memory_store:
            _in_memory_store[opportunity_id] = {"id": opportunity_id, "state_version": 0}
        _in_memory_store[opportunity_id].update(attrs)

    def reset(self) -> None:
        _in_memory_store.clear()


# ---------------------------------------------------------------------------
# DynamoDB-backed state machine
# ---------------------------------------------------------------------------

class DynamoDBStateMachine:
    """
    Atomic conditional writes with optimistic locking.

    Every transition increments ``state_version`` by 1. If the current version
    does not match ``expected_version`` the write is rejected with a
    ``StaleVersionError`` so the caller can re-read and retry.
    """

    def __init__(self) -> None:
        self._table_name = settings.opportunities_table
        self._ddb = boto3.resource("dynamodb", region_name=settings.bedrock_region)
        self._table = self._ddb.Table(self._table_name)

    def transition(
        self,
        opportunity_id: str,
        new_state: OpportunityState,
        expected_version: int,
        extra_attrs: dict[str, Any] | None = None,
    ) -> int:
        """
        Atomically move ``opportunity_id`` to ``new_state``.

        Returns the new ``state_version`` on success.

        Raises:
            StateMachineError: Transition not in allowed set.
            StaleVersionError: Another writer changed the record concurrently.
            ClientError: Unexpected DynamoDB error.
        """
        # Validate transition before hitting DynamoDB
        record = self.get(opportunity_id)
        current = OpportunityState(record["state"]) if record else OpportunityState.DETECTED
        assert_valid_transition(current, new_state)

        update_expr_parts = [
            "#st = :new_state",
            "state_version = state_version + :inc",
        ]
        expr_attr_names: dict[str, str] = {"#st": "state"}
        expr_attr_values: dict[str, Any] = {
            ":new_state": new_state.value,
            ":inc": 1,
            ":expected_version": expected_version,
        }

        if extra_attrs:
            for i, (k, v) in enumerate(extra_attrs.items()):
                placeholder = f":extra_{i}"
                update_expr_parts.append(f"#{k} = {placeholder}")
                expr_attr_names[f"#{k}"] = k
                expr_attr_values[placeholder] = v

        update_expr = "SET " + ", ".join(update_expr_parts)

        try:
            response = self._table.update_item(
                Key={"id": opportunity_id},
                UpdateExpression=update_expr,
                ConditionExpression="state_version = :expected_version",
                ExpressionAttributeNames=expr_attr_names,
                ExpressionAttributeValues=expr_attr_values,
                ReturnValues="UPDATED_NEW",
            )
            new_version = int(response["Attributes"]["state_version"])
            log.info(
                "state_transition",
                extra={
                    "opportunity_id": opportunity_id,
                    "old_state": current.value,
                    "new_state": new_state.value,
                    "new_version": new_version,
                },
            )
            return new_version
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code == _CONDITION_FAILED:
                raise StaleVersionError(
                    f"Concurrent write detected for opportunity '{opportunity_id}'. "
                    f"Expected version {expected_version} is stale. Re-read and retry."
                ) from exc
            raise

    def get(self, opportunity_id: str) -> dict[str, Any] | None:
        response = self._table.get_item(Key={"id": opportunity_id})
        return response.get("Item")

    def upsert(self, opportunity_id: str, attrs: dict[str, Any]) -> None:
        attrs["id"] = opportunity_id
        self._table.put_item(Item=attrs)


# ---------------------------------------------------------------------------
# Factory — returns in-memory or DynamoDB backend
# ---------------------------------------------------------------------------

def get_state_machine(use_dynamodb: bool | None = None) -> DynamoDBStateMachine | InMemoryStateMachine:
    """
    Return the appropriate state machine backend.

    ``use_dynamodb=None`` (default) auto-detects: uses DynamoDB when
    ``settings.opportunities_table`` is set and non-empty, in-memory otherwise.
    """
    if use_dynamodb is None:
        use_dynamodb = bool(settings.opportunities_table)
    if use_dynamodb:
        return DynamoDBStateMachine()
    return InMemoryStateMachine()
