"""
Replay adapter — seeds the graph with a deterministic, immutable scenario.

A Verified Replay is a seedable execution that:
  1. Loads a canonical event JSON from S3 or the local eval_fixtures directory
  2. Builds an IncidentSignal with ``replay=True``
  3. Runs the graph in simulation_mode=True
  4. Produces the same $1,840 result on every run (deterministic)

The replay is the primary judge demo path. It requires no live AWS incident
and no real Bedrock credentials in Phase 1.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ..graph.types import GraphState
from ..models.signal import IncidentSignal

# Canonical replay seed — matches the golden test spec (Appendix C)
_CANONICAL_EVENT: dict[str, Any] = {
    "source": "replay",
    "event_id": "replay-apigateway-2026-08-sla-001",
    "service": "apigateway",
    "region": "us-east-1",
    "start": "2026-08-01T02:00:00Z",
    "end": "2026-08-01T02:30:00Z",
    "affected_resource_ids": ["arn:aws:apigateway:us-east-1::/restapis/demo0001"],
    "raw_ref": "s3://recoup-eval-fixtures/replay/apigateway-2026-08-sla-001.json",
    "replay": True,
}


class ReplayScenario(BaseModel):
    """Definition of a single replay scenario."""

    scenario_id: str
    name: str
    description: str
    event: dict[str, Any]
    expected_credit_usd: Decimal
    expected_uptime_pct: Decimal
    tags: list[str] = []


# Canonical $1,840 scenario
CANONICAL_SCENARIO = ReplayScenario(
    scenario_id="replay-apigateway-2026-08-sla-001",
    name="API Gateway 10% SLA Credit — August 2026",
    description=(
        "6 unavailable 5-minute intervals in a 31-day month "
        "(8,640 total). Monthly uptime: 99.9306%. 10% credit tier. "
        "$18,400 billed charges → $1,840.00 potential credit."
    ),
    event=_CANONICAL_EVENT,
    expected_credit_usd=Decimal("1840.00"),
    expected_uptime_pct=Decimal("99.930556"),
    tags=["golden", "apigateway", "sla_10pct"],
)


class ReplayAdapter:
    """
    Seeds a GraphState from a replay scenario for deterministic execution.

    Usage:
        adapter = ReplayAdapter()
        state = adapter.build_state(CANONICAL_SCENARIO)
        final_state = recoup_graph.run(state)
        assert final_state.availability_result.potential_credit == Decimal("1840.00")
    """

    def __init__(self, fixtures_dir: Path | None = None) -> None:
        self._fixtures_dir = fixtures_dir or _default_fixtures_dir()

    def build_state(
        self,
        scenario: ReplayScenario | None = None,
        *,
        opportunity_id: str | None = None,
    ) -> GraphState:
        """
        Build a fully-populated initial GraphState from a replay scenario.

        Args:
            scenario: Scenario to replay. Defaults to the canonical scenario.
            opportunity_id: Override the generated opportunity ID.

        Returns:
            GraphState ready to pass to ``recoup_graph.run()``.
        """
        scenario = scenario or CANONICAL_SCENARIO
        opp_id = opportunity_id or f"opp-{scenario.scenario_id}"

        event = scenario.event
        signal = IncidentSignal(
            source=event["source"],
            event_id=event["event_id"],
            service=event["service"],
            region=event["region"],
            start=datetime.fromisoformat(event["start"].replace("Z", "+00:00")),
            end=datetime.fromisoformat(event["end"].replace("Z", "+00:00")),
            affected_resource_ids=event["affected_resource_ids"],
            raw_ref=event["raw_ref"],
            replay=event.get("replay", True),
        )

        return GraphState(
            opportunity_id=opp_id,
            simulation_mode=True,
            signal=signal,
            idempotency_key=self._idempotency_key(scenario.scenario_id),
        )

    def load_scenario_from_file(self, filename: str) -> ReplayScenario:
        """Load a scenario from a JSON file in the fixtures directory."""
        path = self._fixtures_dir / filename
        with path.open() as f:
            data = json.load(f)
        return ReplayScenario(**data)

    @staticmethod
    def _idempotency_key(scenario_id: str) -> str:
        return "replay:" + hashlib.sha256(scenario_id.encode()).hexdigest()[:16]


def _default_fixtures_dir() -> Path:
    root = Path(__file__).parent.parent.parent.parent.parent
    return root / "eval_fixtures"
