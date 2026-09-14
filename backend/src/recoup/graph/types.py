"""
Core graph abstractions for the Recoup agent pipeline.

Provides DeterministicNode, AgentNode, Graph, GraphState, and hook context types.
Designed to wrap strands-agents at runtime while keeping Phase 1 stubs dependency-free.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..models.approval import ApprovalRecord
from ..models.availability import AvailabilityInterval, AvailabilityResult
from ..models.claim import ClaimPackage
from ..models.eligibility import EligibilityAssessment
from ..models.evidence import EvidenceManifest, RedactionReport
from ..models.opportunity import OpportunityState
from ..models.recovery import RecoveryAssessment
from ..models.signal import IncidentSignal
from ..models.sla import SLAContract
from ..scanners.finding import Finding

# ---------------------------------------------------------------------------
# Domain types produced within the graph (not in models/ as they are
# internal to the pipeline and not persisted directly)
# ---------------------------------------------------------------------------


class IncidentHypothesis(BaseModel):
    """Working hypothesis produced by the incident_correlation node."""

    service: str
    region: str
    incident_date: date
    affected_resource_ids: list[str] = Field(default_factory=list)
    availability_intervals: list[AvailabilityInterval] = Field(default_factory=list)
    billed_charges: Decimal = Decimal("0.00")
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    summary: str = ""
    replay: bool = False


class CaseOutcome(BaseModel):
    """Outcome returned by the case_monitor node."""

    case_id: str
    status: Literal["PENDING", "IN_PROGRESS", "RESOLVED_APPROVED", "RESOLVED_REJECTED"] = "PENDING"
    credit_amount: Decimal = Decimal("0.00")
    notes: str = ""


class PolicyDecision(StrEnum):
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"


class ErrorDisposition(StrEnum):
    RETRY = "RETRY"
    FATAL = "FATAL"


# ---------------------------------------------------------------------------
# Mutable pipeline state — passed through every node
# ---------------------------------------------------------------------------


class GraphState(BaseModel):
    """
    Immutable-by-convention snapshot of all data accumulated in the pipeline.

    Each node receives the current GraphState and returns a *new* GraphState
    with its outputs merged in. Pydantic validation ensures type safety at
    every boundary.
    """

    model_config = {"arbitrary_types_allowed": True}

    # Identity
    opportunity_id: str
    # When True, reads real CloudWatch data and writes evidence to S3.
    # Set by the API route layer; defaults False so tests never attempt real AWS writes.
    live_evidence: bool = False
    # When True, AgentNodes call real Strands agents backed by Amazon Bedrock.
    # Never set in canonical replay (20/20 determinism preserved).
    use_strands: bool = False

    # Node outputs (populated progressively)
    signal: IncidentSignal | None = None
    idempotency_key: str = ""
    hypothesis: IncidentHypothesis | None = None
    contract: SLAContract | None = None
    availability_result: AvailabilityResult | None = None
    evidence_manifest: EvidenceManifest | None = None
    sanitized_manifest: EvidenceManifest | None = None
    redaction_report: RedactionReport | None = None
    eligibility_assessment: EligibilityAssessment | None = None
    policy_decision: PolicyDecision | None = None
    claim_package: ClaimPackage | None = None
    approval_record: ApprovalRecord | None = None
    case_id: str | None = None
    submitted_at: datetime | None = None
    case_outcome: CaseOutcome | None = None

    # Replay fixture data — loaded by ReplayAdapter; consumed by AgentNode stubs
    # Keys match fixture filenames without extension: metric_series, billing_snapshot, etc.
    replay_fixtures: dict[str, Any] = Field(default_factory=dict)

    # Cost recovery pipeline (optimization / promoted findings)
    recovery_assessment: RecoveryAssessment | None = None
    promoted_finding: Finding | None = None

    # Diagnostics
    errors: list[str] = Field(default_factory=list)
    current_state: OpportunityState = OpportunityState.DETECTED
    state_version: int = 0


# ---------------------------------------------------------------------------
# Hook context types
# ---------------------------------------------------------------------------


@dataclass
class NodeContext:
    """Passed to before/after node hooks."""

    node_name: str
    state: dict[str, Any]
    _started_at: float = field(default_factory=time.monotonic, repr=False)

    @property
    def duration_ms(self) -> int:
        return int((time.monotonic() - self._started_at) * 1000)


@dataclass
class ToolContext:
    """Passed to before/after tool hooks."""

    tool_name: str
    node_name: str
    state: dict[str, Any]
    request_json: str = ""
    response_json: str = ""
    policy_decision: str = "ALLOW"
    _started_at: float = field(default_factory=time.monotonic, repr=False)

    @property
    def duration_ms(self) -> int:
        return int((time.monotonic() - self._started_at) * 1000)

    def inject(self, key: str, value: Any) -> None:
        self.state[key] = value


# ---------------------------------------------------------------------------
# Node types
# ---------------------------------------------------------------------------


class DeterministicNode:
    """
    A pure-function node. No LLM involvement. All financial arithmetic lives here.

    The ``fn`` callable receives the current GraphState and returns a dict of
    field updates to merge into the next GraphState.
    """

    def __init__(
        self,
        name: str,
        fn: Callable[[GraphState], dict[str, Any]],
        description: str = "",
    ) -> None:
        self.name = name
        self.fn = fn
        self.description = description

    def run(self, state: GraphState) -> dict[str, Any]:
        return self.fn(state)

    def __repr__(self) -> str:
        return f"DeterministicNode(name={self.name!r})"


class AgentNode:
    """
    An LLM-backed node backed by Amazon Bedrock via the Strands SDK.

    When ``state.use_strands=True`` and a ``strands_fn`` is provided, the node
    invokes the real Strands agent.  On any failure (Bedrock unavailable, quota,
    parse error) it falls back to ``stub_fn`` so the demo never hard-fails.

    When ``state.use_strands=False`` (canonical replay, CI, tests) only
    ``stub_fn`` is called — Bedrock is never contacted.
    """

    def __init__(
        self,
        name: str,
        tool_names: list[str],
        system_prompt: str = "",
        description: str = "",
        stub_fn: Callable[[GraphState], dict[str, Any]] | None = None,
        strands_fn: Callable[[GraphState], dict[str, Any] | None] | None = None,
    ) -> None:
        self.name = name
        self.tool_names = tool_names
        self.system_prompt = system_prompt
        self.description = description
        self._stub_fn = stub_fn
        self._strands_fn = strands_fn

    _STRANDS_TIMEOUT_SECONDS: float = 15.0

    def run(self, state: GraphState) -> dict[str, Any]:
        import concurrent.futures
        import logging as _logging
        _log = _logging.getLogger(__name__)

        if state.use_strands and self._strands_fn is not None:
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self._strands_fn, state)
                    try:
                        result = future.result(timeout=self._STRANDS_TIMEOUT_SECONDS)
                        if result is not None:
                            _log.info("agentnode.strands_ok node=%s", self.name)
                            return result
                        _log.warning(
                            "agentnode.strands_returned_none node=%s — using stub", self.name
                        )
                    except concurrent.futures.TimeoutError:
                        _log.warning(
                            "agentnode.strands_timeout node=%s timeout=%.0fs — stub fallback",
                            self.name,
                            self._STRANDS_TIMEOUT_SECONDS,
                        )
                    except Exception as exc:  # noqa: BLE001
                        _log.warning(
                            "agentnode.strands_failed node=%s error=%s — using stub",
                            self.name,
                            exc,
                        )
            except Exception as exc:  # noqa: BLE001
                _log.warning(
                    "agentnode.strands_executor_failed node=%s error=%s — using stub",
                    self.name, exc,
                )

        if self._stub_fn is not None:
            return self._stub_fn(state)
        raise NotImplementedError(
            f"AgentNode '{self.name}' has no stub_fn. Wire a real Agent in Phase 2."
        )

    def __repr__(self) -> str:
        return f"AgentNode(name={self.name!r}, tools={self.tool_names!r})"


# ---------------------------------------------------------------------------
# Graph edges
# ---------------------------------------------------------------------------


@dataclass
class Edge:
    source: str
    target: str


@dataclass
class ConditionalEdge:
    source: str
    condition: Callable[[GraphState], str]
    targets: dict[str, str | AgentNode | DeterministicNode]


# ---------------------------------------------------------------------------
# Graph container
# ---------------------------------------------------------------------------

_TERMINAL_STATES = {"await_human_approval", "terminal_denied"}


class Graph:
    """
    Directed graph of DeterministicNodes and AgentNodes.

    Provides ``validate()`` to ensure all edge endpoints are resolvable at
    import time (no runtime surprises), and ``run()`` for sequential execution.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self._nodes: dict[str, DeterministicNode | AgentNode] = {}
        self._edges: list[Edge | ConditionalEdge] = []
        self._execution_order: list[str] = []

    # --- Building the graph ------------------------------------------------

    def add_node(self, node: DeterministicNode | AgentNode) -> None:
        self._nodes[node.name] = node

    def add_edge(
        self,
        source: str | DeterministicNode | AgentNode,
        target: str | DeterministicNode | AgentNode,
    ) -> None:
        src = source.name if hasattr(source, "name") else source
        tgt = target.name if hasattr(target, "name") else target
        self._edges.append(Edge(source=str(src), target=str(tgt)))

    def add_conditional_edge(
        self,
        source: str | DeterministicNode | AgentNode,
        condition: Callable[[GraphState], str],
        targets: dict[str, Any],
    ) -> None:
        src = source.name if hasattr(source, "name") else source
        self._edges.append(ConditionalEdge(source=str(src), condition=condition, targets=targets))

    # --- Validation --------------------------------------------------------

    def validate(self) -> None:
        """Assert all edge endpoints resolve to known nodes or terminal pseudo-nodes."""
        all_valid = set(self._nodes.keys()) | _TERMINAL_STATES
        for edge in self._edges:
            if edge.source not in all_valid:
                raise ValueError(
                    f"[{self.name}] Edge source '{edge.source}' is not a registered node. "
                    f"Known nodes: {sorted(all_valid)}"
                )
            if isinstance(edge, Edge) and edge.target not in all_valid:
                raise ValueError(
                    f"[{self.name}] Edge target '{edge.target}' is not a registered node."
                )
            if isinstance(edge, ConditionalEdge):
                for key, tgt in edge.targets.items():
                    tgt_name = tgt.name if hasattr(tgt, "name") else str(tgt)
                    if tgt_name not in all_valid:
                        raise ValueError(
                            f"[{self.name}] Conditional edge target '{tgt_name}' "
                            f"(key='{key}') is not a registered node."
                        )

    # --- Execution ---------------------------------------------------------

    def run(
        self,
        initial_state: GraphState,
        on_node_start: Callable[[str], None] | None = None,
        on_node_complete: Callable[[str, GraphState, int], None] | None = None,
        stop_at: str | None = None,
    ) -> GraphState:
        """
        Execute the graph sequentially in topological order.

        Conditional edges are evaluated against the live GraphState at runtime.
        Nodes that return a dict of updates are merged into the running state.

        Args:
            initial_state: Starting graph state.
            on_node_start: Optional callback fired before each node executes.
                           Receives the node name.
            on_node_complete: Optional callback fired after each node executes.
                              Receives (node_name, updated_state, duration_ms).
        """
        self.validate()

        state = initial_state
        visited: set[str] = set()
        queue: list[str] = [self._entry_node()]

        while queue:
            node_name = queue.pop(0)
            if node_name in visited or node_name in _TERMINAL_STATES:
                continue
            visited.add(node_name)

            node = self._nodes.get(node_name)
            if node is None:
                continue

            if on_node_start is not None:
                on_node_start(node_name)

            t0 = time.monotonic()
            updates = node.run(state)
            duration_ms = int((time.monotonic() - t0) * 1000)

            if updates:
                state = state.model_copy(update=updates)

            if on_node_complete is not None:
                on_node_complete(node_name, state, duration_ms)

            if stop_at and node_name == stop_at:
                break

            # Enqueue successors
            for edge in self._edges:
                if edge.source != node_name:
                    continue
                if isinstance(edge, Edge):
                    queue.append(edge.target)
                elif isinstance(edge, ConditionalEdge):
                    decision_key = edge.condition(state)
                    tgt = edge.targets.get(decision_key)
                    if tgt is not None:
                        tgt_name = tgt.name if hasattr(tgt, "name") else str(tgt)
                        queue.append(tgt_name)

        return state

    # --- Helpers -----------------------------------------------------------

    def _entry_node(self) -> str:
        """Return the node that has no incoming edges (graph entry point)."""
        targets = {
            (e.target if isinstance(e, Edge) else "")
            for e in self._edges
        }
        for name in self._nodes:
            if name not in targets:
                return name
        # Fallback: first registered node
        return next(iter(self._nodes))

    @property
    def node_names(self) -> list[str]:
        return list(self._nodes.keys())

    def __repr__(self) -> str:
        return f"Graph(name={self.name!r}, nodes={self.node_names})"
