# Recoup — State Machine Reference

**File:** `backend/src/recoup/graph/state_machine.py`  
**Persistence:** DynamoDB table `recoup-opportunities` (with in-memory fallback for unit tests)  
**Last updated:** Sep 11, 2026  
**Status:** Phase 1 complete — DynamoDB transitions + optimistic locking implemented  
**Playwright tests:** `journey-operator-primary.spec.ts`, `journey-decision-inbox.spec.ts`, `journey-security.spec.ts` verify all transitions and state_version binding.

---

## Overview

Every `RecoveryOpportunity` moves through a defined set of states as the agent graph executes. State transitions are:

- **Validated** — only allowed transitions are accepted (others raise `StateMachineError`)
- **Atomic** — DynamoDB conditional writes with optimistic locking (`state_version`)
- **Auditable** — every transition is logged with `opportunity_id`, old state, new state, and new version
- **Recoverable** — the in-memory fallback allows unit tests to run without AWS credentials

---

## State Diagram

```
                    ┌─────────────┐
                    │  DETECTED   │ ← initial state on opportunity creation
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │INVESTIGATING│ ← incident_correlation + evidence_collector running
                    └──────┬──────┘
              ┌────────────┴────────────┐
              │                         │
     ┌────────▼───────┐       ┌─────────▼────────┐
     │ EVIDENCE_READY │       │  NEEDS_EVIDENCE   │ ← retry loop
     └────────┬───────┘       └─────────┬─────────┘
              │                         │ (back to INVESTIGATING)
     ┌────────▼───────┐
     │ELIGIBILITY_    │ ← eligibility_reasoner + risk_policy_gate complete
     │  REVIEWED      │
     └────────┬───────┘
     ┌────────┴─────────┬──────────────┐
     │                  │              │
┌────▼──────┐      ┌────▼──┐      ┌───▼──┐
│AWAITING_  │      │DENIED │      │FAILED│
│ APPROVAL  │      └───────┘      └──────┘
└────┬──────┘  ← HITL (opportunity detail / approvals API)
     │
     ├── DECLINED ──► DENIED
     │
     ▼
  APPROVED ← human approves (UI: `/opportunities/{id}` or `POST .../approvals/opportunity/{id}/approve`)
     │
     ▼
 SUBMITTING ← submission_adapter executing
     │
     ├── FAILED
     │
     ▼
 SUBMITTED ← case_id written
     │
     ▼
 MONITORING ← case_monitor polling
     │
     ├──────────────────────┐
     │                      │                 │
  RECOVERED             REJECTED        NEEDS_FOLLOWUP
(credit granted)     (claim denied)   (needs manual review)
```

---

## All States

| State | Description |
|-------|-------------|
| `DETECTED` | Opportunity created from an EventBridge health event, cost anomaly, or replay seed |
| `INVESTIGATING` | `incident_correlation` and `evidence_collector` nodes are running |
| `EVIDENCE_READY` | All required evidence has been collected and sanitized |
| `NEEDS_EVIDENCE` | Evidence collection incomplete; retrying investigation |
| `ELIGIBILITY_REVIEWED` | `eligibility_reasoner` and `risk_policy_gate` have run |
| `AWAITING_APPROVAL` | Waiting for human approve/decline/investigate on opportunity detail |
| `APPROVED` | Human approved the action |
| `SUBMITTING` | `submission_adapter` is submitting to AWS Support |
| `SUBMITTED` | AWS Support case has been created (real or simulated) |
| `MONITORING` | `case_monitor` is polling the case for resolution |
| `RECOVERED` | AWS Support approved the credit claim |
| `REJECTED` | AWS Support rejected the credit claim |
| `NEEDS_FOLLOWUP` | Case needs manual review (e.g. request for more info) |
| `DENIED` | Cedar policy or eligibility check denied the claim |
| `FAILED` | Unrecoverable error during processing |

---

## Valid Transitions

```python
TRANSITIONS: dict[OpportunityState, set[OpportunityState]] = {
    DETECTED:             {INVESTIGATING},
    INVESTIGATING:        {EVIDENCE_READY, NEEDS_EVIDENCE},
    NEEDS_EVIDENCE:       {INVESTIGATING},
    EVIDENCE_READY:       {ELIGIBILITY_REVIEWED},
    ELIGIBILITY_REVIEWED: {AWAITING_APPROVAL, DENIED, FAILED},
    AWAITING_APPROVAL:    {APPROVED, DENIED},
    APPROVED:             {SUBMITTING},
    SUBMITTING:           {SUBMITTED, FAILED},
    SUBMITTED:            {MONITORING},
    MONITORING:           {RECOVERED, REJECTED, NEEDS_FOLLOWUP},
    # Terminal states — no outgoing transitions
    RECOVERED:            set(),
    REJECTED:             set(),
    DENIED:               set(),
    FAILED:               set(),
    NEEDS_FOLLOWUP:       set(),
}
```

Attempting any transition not in this map raises:
```
StateMachineError: Invalid transition: DETECTED → SUBMITTING.
Allowed from DETECTED: ['INVESTIGATING']
```

---

## DynamoDB Optimistic Locking

Every record in `recoup-opportunities` has a `state_version` integer that increments by 1 on every transition. The conditional write uses:

```python
response = self._table.update_item(
    Key={"id": opportunity_id},
    UpdateExpression="SET #st = :new_state, state_version = state_version + :inc",
    ConditionExpression="state_version = :expected_version",
    ...
)
```

**Concurrency scenario:**
1. Thread A reads version `3`, starts transition to `EVIDENCE_READY`
2. Thread B reads version `3`, also starts transition
3. Thread A writes — succeeds, version becomes `4`
4. Thread B writes — DynamoDB rejects with `ConditionalCheckFailedException`
5. Thread B's `DynamoDBStateMachine.transition()` raises `StaleVersionError`
6. Caller catches `StaleVersionError`, re-reads the record, and retries

---

## DynamoDBStateMachine API

```python
class DynamoDBStateMachine:
    def transition(
        self,
        opportunity_id: str,
        new_state: OpportunityState,
        expected_version: int,
        extra_attrs: dict[str, Any] | None = None,
    ) -> int:
        """
        Atomically move opportunity to new_state.
        Returns the new state_version on success.
        Raises StaleVersionError on concurrent write conflict.
        Raises StateMachineError on invalid transition.
        """

    def get(self, opportunity_id: str) -> dict[str, Any] | None:
        """Return the current DynamoDB record for an opportunity."""

    def upsert(self, opportunity_id: str, attrs: dict[str, Any]) -> None:
        """Create or overwrite an opportunity record (used for initial creation)."""
```

---

## InMemoryStateMachine (Unit Test Fallback)

The `InMemoryStateMachine` uses a module-level `_in_memory_store` dict. It is:
- **Not thread-safe** (intended for unit tests only)
- **Auto-created** on first transition (no prior `upsert` needed)
- **Reset-able** via `InMemoryStateMachine().reset()` between tests

```python
class InMemoryStateMachine:
    def transition(self, opportunity_id, new_state, expected_version, extra_attrs=None) -> int
    def get(self, opportunity_id) -> dict | None
    def upsert(self, opportunity_id, attrs) -> None
    def reset(self) -> None   # clears all records
```

---

## Factory Function

```python
def get_state_machine(
    use_dynamodb: bool | None = None
) -> DynamoDBStateMachine | InMemoryStateMachine:
```

- `use_dynamodb=None` (default): auto-detects based on `settings.opportunities_table`
  - If `RECOUP_OPPORTUNITIES_TABLE` env var is set → `DynamoDBStateMachine`
  - If not set (local dev / CI) → `InMemoryStateMachine`
- `use_dynamodb=True`: forces DynamoDB
- `use_dynamodb=False`: forces in-memory

---

## Error Types

| Exception | When raised |
|-----------|-------------|
| `StateMachineError` | Transition not in `TRANSITIONS` map |
| `StaleVersionError` | DynamoDB conditional write failed (concurrent writer) |
| `ClientError` | Unexpected DynamoDB error (re-raised as-is) |

`StaleVersionError` is a subclass of `StateMachineError`.

---

## DynamoDB Table Schema

**Table:** `recoup-opportunities`

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` (PK) | String | Opportunity ID |
| `state` | String | Current `OpportunityState` value |
| `state_version` | Number | Optimistic lock counter |
| `account_id_masked` | String | Last 4 digits only (e.g. `****9012`) |
| `service` | String | AWS service identifier |
| `region` | String | AWS region |
| `discovered_at` | String | ISO-8601 timestamp |
| `potential_value` | String | Decimal as string (avoids DynamoDB float) |
| `confidence` | Number | 0.0 – 1.0 |
| `idempotency_key` | String | Prevents duplicate processing |
| `active_claim_hash` | String | SHA-256 of current ClaimPackage |

**GSIs:**

| Index | Partition Key | Sort Key | Use case |
|-------|--------------|----------|---------|
| `account-state-index` | `account_id_masked` | `state` | List opportunities by account + state |
| `state-discovered-index` | `state` | `discovered_at` | List opportunities by state + discovery time |

---

## Usage Example

```python
from recoup.graph.state_machine import get_state_machine
from recoup.models.opportunity import OpportunityState

sm = get_state_machine()

# Create initial record
sm.upsert("opp-001", {
    "state": OpportunityState.DETECTED.value,
    "state_version": 0,
    "service": "apigateway",
    "region": "us-east-1",
})

# Transition to INVESTIGATING
new_version = sm.transition(
    opportunity_id="opp-001",
    new_state=OpportunityState.INVESTIGATING,
    expected_version=0,
)
# new_version == 1

# Concurrent write protection
try:
    sm.transition("opp-001", OpportunityState.EVIDENCE_READY, expected_version=0)  # stale!
except StaleVersionError:
    current = sm.get("opp-001")
    # Re-read and retry with current["state_version"]
```
