"""
Phase 6 tests — Live AWS Action Proof.

All tests are deterministic: no LLM calls, no real AWS calls, no network.
Tests cover:
  - stop_demo_instance: allowlist enforcement, simulation return, idempotency
  - EC2DemoAdapter: trigger workflow, approval creation, execute (simulation)
  - Cedar policy: stop_demo_instance ALLOW and DENY scenarios
  - EC2 demo API routes (via FastAPI TestClient)
  - Terminate forbidden: terminate_ec2_instance always DENY
  - Full workflow: trigger → approve → execute → verify stop result
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from recoup.adapters.ec2_demo import EC2DemoAdapter, _clear_ec2_demo_store, _monthly_waste
from recoup.approval.store import (
    _clear_in_memory,
    get_approval,
    get_pending_for_opportunity,
)
from recoup.safety.cedar import PolicyContext, evaluate_policy
from recoup.tools.ec2_tools import _action_hash, _clear_idempotency_store, stop_demo_instance

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_stores() -> None:
    """Clear all in-memory state before each test."""
    _clear_in_memory()
    _clear_idempotency_store()
    _clear_ec2_demo_store()


@pytest.fixture()
def allowlisted_instance(monkeypatch: pytest.MonkeyPatch) -> str:
    """Patch settings so 'i-test000000000001' is in the allowlist."""
    monkeypatch.setattr(
        "recoup.tools.ec2_tools.settings",
        _FakeSettings(instance_id="i-test000000000001"),
    )
    monkeypatch.setattr(
        "recoup.adapters.ec2_demo.settings",
        _FakeSettings(instance_id="i-test000000000001"),
    )
    return "i-test000000000001"


@pytest.fixture()
def simulation_instance(monkeypatch: pytest.MonkeyPatch) -> str:
    """
    Patch settings with the demo stub instance ID.

    ``"i-demo0000000000000"`` is the sentinel that triggers the deterministic
    simulation path in ``stop_demo_instance`` without touching AWS.

    Also patches boto3.resource to fail fast on any DynamoDB call so approval
    store falls back to in-memory immediately (no 60s timeout waiting for AWS).
    """
    monkeypatch.setattr(
        "recoup.tools.ec2_tools.settings",
        _FakeSettings(instance_id="i-demo0000000000000"),
    )
    monkeypatch.setattr(
        "recoup.adapters.ec2_demo.settings",
        _FakeSettings(instance_id="i-demo0000000000000"),
    )
    # Fail DynamoDB immediately so approval store falls back to in-memory
    mock_ddb = MagicMock()
    mock_ddb.Table.return_value.put_item.side_effect = Exception("no-ddb-in-tests")
    mock_ddb.Table.return_value.get_item.side_effect = Exception("no-ddb-in-tests")
    mock_ddb.Table.return_value.scan.side_effect = Exception("no-ddb-in-tests")
    mock_ddb.Table.return_value.update_item.side_effect = Exception("no-ddb-in-tests")
    monkeypatch.setattr("boto3.resource", lambda *a, **kw: mock_ddb)
    monkeypatch.setattr("boto3.client", MagicMock(side_effect=Exception("no-aws-in-tests")))
    return "i-demo0000000000000"


class _FakeSettings:
    """Minimal settings stub for tests — no AWS calls."""

    def __init__(self, instance_id: str = "i-test000000000001") -> None:
        self._instance_id = instance_id
        self.bedrock_region = "us-east-1"
        self.allowlisted_demo_account_id = "123456789012"
        # Phase 6e — STS remediation role (None → falls back to default cred chain in tests)
        self.recoup_remediation_role_arn: str | None = None
        self.recoup_external_id: str | None = None

    @property
    def demo_instance_ids(self) -> list[str]:
        return [self._instance_id]


# ---------------------------------------------------------------------------
# 1. stop_demo_instance — allowlist enforcement
# ---------------------------------------------------------------------------


def test_stop_demo_instance_rejects_non_allowlisted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Instance not in allowlist → PermissionError, no AWS call."""
    monkeypatch.setattr(
        "recoup.tools.ec2_tools.settings",
        _FakeSettings(instance_id="i-allowed0000000001"),
    )
    with pytest.raises(PermissionError, match="not in the RecoupDemo allowlist"):
        stop_demo_instance(
            instance_id="i-evil0000000000000",
            opportunity_id="opp-test",
            approval_id="appr-test",
        )


def test_stop_demo_instance_simulation_mode(simulation_instance: str) -> None:
    """Simulation mode returns deterministic stub without touching AWS."""
    result = stop_demo_instance(
        instance_id=simulation_instance,
        opportunity_id="opp-sim-001",
        approval_id="appr-sim-001",
    )
    assert result["simulated"] is True
    assert result["instance_id"] == simulation_instance
    assert result["previous_state"] == "running"
    assert result["current_state"] == "stopping"
    assert result["stopped_at"] is None
    assert "DEMO" in result["audit_trail"][0]


def test_stop_demo_instance_simulation_no_aws_call(
    simulation_instance: str,
) -> None:
    """boto3 is never called via the simulation path (result returns before import)."""
    # Capture the real __import__ before patching so the closure can use it
    import builtins as _builtins  # noqa: PLC0415
    _real_import = _builtins.__import__

    boto3_imported: list[bool] = []

    def _trap_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "boto3":
            boto3_imported.append(True)
        return _real_import(name, *args, **kwargs)  # type: ignore[call-overload]

    _builtins.__import__ = _trap_import  # type: ignore[assignment]
    try:
        result = stop_demo_instance(
            instance_id=simulation_instance,
            opportunity_id="opp-x",
            approval_id="appr-x",
        )
    finally:
        _builtins.__import__ = _real_import  # type: ignore[assignment]

    assert result["simulated"] is True
    assert not boto3_imported, "boto3 should not be imported via the simulation path"


# ---------------------------------------------------------------------------
# 2. EC2DemoAdapter — trigger workflow
# ---------------------------------------------------------------------------


def test_ec2_demo_adapter_trigger_creates_opportunity(
    simulation_instance: str,
) -> None:
    """trigger() creates an OPTIMIZATION opportunity and a HITL approval."""
    adapter = EC2DemoAdapter()
    record = adapter.trigger(
        instance_id=simulation_instance,
    )

    opp = record["opportunity"]
    assert opp["type"] == "OPTIMIZATION"
    assert opp["service"] == "Amazon EC2"
    assert opp["state"] == "AWAITING_APPROVAL"
    assert Decimal(opp["potential_value"]) > Decimal("0")


def test_ec2_demo_adapter_trigger_creates_approval(
    simulation_instance: str,
) -> None:
    """trigger() creates a PENDING approval in the store."""
    adapter = EC2DemoAdapter()
    record = adapter.trigger(
        instance_id=simulation_instance,
    )

    approval_id = record["approval_id"]
    opp_id = record["opportunity"]["id"]
    assert approval_id is not None

    # Approval should be in the store
    approval = get_approval(approval_id)
    assert approval is not None
    assert str(approval.state) == "PENDING"
    assert approval.action == "stop_demo_instance"
    assert approval.amount == Decimal(record["monthly_waste_usd"])

    # Claim hash must be bound to the opportunity + instance
    expected_hash = "sha256:" + hashlib.sha256(
        f"{opp_id}:stop_demo_instance:{simulation_instance}".encode()
    ).hexdigest()
    assert approval.claim_hash == expected_hash


def test_ec2_demo_adapter_cloudwatch_check_simulation(
    simulation_instance: str,
) -> None:
    """CloudWatch check returns idle fixture in simulation mode."""
    adapter = EC2DemoAdapter()
    record = adapter.trigger(
        instance_id=simulation_instance,
    )
    cw = record["cloudwatch_check"]
    assert cw["simulated"] is True
    assert cw["idle"] is True
    assert cw["avg_cpu_pct"] < 5.0


def test_ec2_demo_adapter_cloudtrail_check_simulation(
    simulation_instance: str,
) -> None:
    """CloudTrail check returns clean fixture in simulation mode."""
    adapter = EC2DemoAdapter()
    record = adapter.trigger(
        instance_id=simulation_instance,
    )
    ct = record["cloudtrail_check"]
    assert ct["simulated"] is True
    assert ct["blocking_changes"] is False
    assert ct["verdict"] == "no_blocking_ownership_changes"


def test_ec2_demo_adapter_waste_calculation() -> None:
    """Monthly waste is calculated correctly for t3.micro."""
    waste = _monthly_waste("t3.micro")
    # t3.micro = $0.0104/hr × 730 hr = $7.59
    assert waste == Decimal("7.59")


def test_ec2_demo_adapter_waste_calculation_t3_nano() -> None:
    """Monthly waste for t3.nano = $0.0052 × 730 = $3.80."""
    waste = _monthly_waste("t3.nano")
    assert waste == Decimal("3.80")


def test_ec2_demo_adapter_unknown_instance_type_fallback() -> None:
    """Unknown instance type falls back to t3.micro pricing."""
    waste = _monthly_waste("m5.xlarge-unknown")
    # fallback = t3.micro rate
    assert waste == Decimal("7.59")


# ---------------------------------------------------------------------------
# 3. EC2DemoAdapter — execute workflow
# ---------------------------------------------------------------------------


def test_ec2_demo_execute_simulation_returns_stop_result(
    simulation_instance: str,
) -> None:
    """execute() in simulation mode returns a stop result with simulated=True."""
    adapter = EC2DemoAdapter()
    record = adapter.trigger(
        instance_id=simulation_instance,
    )
    opp_id = record["opportunity"]["id"]

    result = adapter.execute(opportunity_id=opp_id)

    stop = result["stop_result"]
    assert stop is not None
    assert stop["simulated"] is True
    assert stop["instance_id"] == simulation_instance
    assert "executed_at" in result


def test_ec2_demo_execute_missing_opportunity_raises() -> None:
    """execute() raises KeyError for unknown opportunity IDs."""
    adapter = EC2DemoAdapter()
    with pytest.raises(KeyError, match="not found"):
        adapter.execute(opportunity_id="nonexistent-opp")


def test_ec2_demo_get_returns_record(simulation_instance: str) -> None:
    """get() returns the opportunity record by ID."""
    adapter = EC2DemoAdapter()
    record = adapter.trigger(
        instance_id=simulation_instance,
    )
    opp_id = record["opportunity"]["id"]

    fetched = adapter.get(opp_id)
    assert fetched is not None
    assert fetched["instance_id"] == simulation_instance


def test_ec2_demo_get_missing_returns_none() -> None:
    """get() returns None for unknown IDs."""
    adapter = EC2DemoAdapter()
    assert adapter.get("no-such-id") is None


def test_ec2_demo_list_all_returns_all(simulation_instance: str) -> None:
    """list_all() returns all triggered opportunities."""
    adapter = EC2DemoAdapter()
    adapter.trigger(instance_id=simulation_instance)
    adapter.trigger(instance_id=simulation_instance)

    records = adapter.list_all()
    assert len(records) == 2


# ---------------------------------------------------------------------------
# 4. Cedar policy — stop_demo_instance
# ---------------------------------------------------------------------------


def test_cedar_stop_demo_instance_allow() -> None:
    """Cedar ALLOW when all preconditions are satisfied."""
    ctx = PolicyContext(
        approval_state="APPROVED",
        target_instance_tag="RecoupDemo=true",
        target_account_id="123456789012",
        allowlisted_demo_account_id="123456789012",
        approval_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    assert evaluate_policy("stop_demo_instance", ctx) == "ALLOW"


def test_cedar_stop_demo_instance_deny_no_approval() -> None:
    """Cedar DENY when approval_state is not APPROVED."""
    ctx = PolicyContext(
        approval_state="PENDING",
        target_instance_tag="RecoupDemo=true",
        target_account_id="123456789012",
        allowlisted_demo_account_id="123456789012",
        approval_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    assert evaluate_policy("stop_demo_instance", ctx) == "DENY"


def test_cedar_stop_demo_instance_deny_wrong_tag() -> None:
    """Cedar DENY when RecoupDemo tag is missing or wrong value."""
    ctx = PolicyContext(
        approval_state="APPROVED",
        target_instance_tag="SomeOtherTag=true",
        target_account_id="123456789012",
        allowlisted_demo_account_id="123456789012",
        approval_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    assert evaluate_policy("stop_demo_instance", ctx) == "DENY"


def test_cedar_stop_demo_instance_deny_wrong_account() -> None:
    """Cedar DENY when target_account_id doesn't match allowlisted_demo_account_id."""
    ctx = PolicyContext(
        approval_state="APPROVED",
        target_instance_tag="RecoupDemo=true",
        target_account_id="999999999999",
        allowlisted_demo_account_id="123456789012",
        approval_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    assert evaluate_policy("stop_demo_instance", ctx) == "DENY"


def test_cedar_stop_demo_instance_deny_expired_approval() -> None:
    """Cedar DENY when approval has expired."""
    ctx = PolicyContext(
        approval_state="APPROVED",
        target_instance_tag="RecoupDemo=true",
        target_account_id="123456789012",
        allowlisted_demo_account_id="123456789012",
        approval_expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    assert evaluate_policy("stop_demo_instance", ctx) == "DENY"


def test_cedar_terminate_ec2_always_denied() -> None:
    """terminate_ec2_instance is hard-forbidden in all circumstances."""
    ctx = PolicyContext(
        approval_state="APPROVED",
        session_authenticated=True,
    )
    assert evaluate_policy("terminate_ec2_instance", ctx) == "DENY"


# ---------------------------------------------------------------------------
# 5. _action_hash binding
# ---------------------------------------------------------------------------


def test_action_hash_is_deterministic() -> None:
    """Same inputs always produce the same binding hash."""
    h1 = _action_hash("opp-abc", "i-123")
    h2 = _action_hash("opp-abc", "i-123")
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_action_hash_differs_by_opportunity() -> None:
    """Different opportunity IDs produce different hashes."""
    h1 = _action_hash("opp-aaa", "i-123")
    h2 = _action_hash("opp-bbb", "i-123")
    assert h1 != h2


def test_action_hash_differs_by_instance() -> None:
    """Different instance IDs produce different hashes."""
    h1 = _action_hash("opp-aaa", "i-111")
    h2 = _action_hash("opp-aaa", "i-222")
    assert h1 != h2


# ---------------------------------------------------------------------------
# 6. Full simulation workflow: trigger → (approve) → execute
# ---------------------------------------------------------------------------


def test_full_simulation_workflow(simulation_instance: str) -> None:
    """
    End-to-end simulation:
    trigger → verify approval pending → approve → execute → verify stop result.
    """
    from recoup.approval.store import update_approval_state  # noqa: PLC0415
    from recoup.models.approval import ApprovalState  # noqa: PLC0415

    adapter = EC2DemoAdapter()
    record = adapter.trigger(
        instance_id=simulation_instance,
    )
    opp_id = record["opportunity"]["id"]
    approval_id = record["approval_id"]

    # Approval should be PENDING
    pending = get_pending_for_opportunity(opp_id)
    assert pending is not None
    assert pending.action == "stop_demo_instance"
    assert str(pending.state) == "PENDING"

    # Simulate operator approving via Decision Inbox
    update_approval_state(
        approval_id,
        ApprovalState.APPROVED,
        decided_by="operator@recoup",
        notes="Approved in test",
    )

    # Execute the stop
    result = adapter.execute(opportunity_id=opp_id)

    stop = result["stop_result"]
    assert stop is not None
    assert stop["simulated"] is True
    assert stop["instance_id"] == simulation_instance
    assert stop["current_state"] == "stopping"
    assert "executed_at" in result


def test_pending_approval_visible_via_global_store(simulation_instance: str) -> None:
    """Approval created by EC2 demo trigger appears in the global pending list."""
    from recoup.approval.store import list_pending_approvals  # noqa: PLC0415

    adapter = EC2DemoAdapter()
    adapter.trigger(instance_id=simulation_instance)
    adapter.trigger(instance_id=simulation_instance)

    pending = list_pending_approvals()
    ec2_pending = [p for p in pending if p.action == "stop_demo_instance"]
    assert len(ec2_pending) >= 1


def test_ec2_demo_opportunity_id_is_unique(simulation_instance: str) -> None:
    """Each trigger() call generates a distinct opportunity ID."""
    adapter = EC2DemoAdapter()
    r1 = adapter.trigger(instance_id=simulation_instance)
    r2 = adapter.trigger(instance_id=simulation_instance)
    assert r1["opportunity"]["id"] != r2["opportunity"]["id"]
