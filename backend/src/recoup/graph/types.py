"""
Core graph abstractions for the Recoup agent pipeline.

Provides DeterministicNode, AgentNode, Graph, GraphState, and hook context types.
Designed to wrap strands-agents at runtime while keeping Phase 1 stubs dependency-free.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Literal, Union

from pydantic import BaseModel, Field

from ..models.approval import ApprovalRecord
from ..models.availability import AvailabilityInterval, AvailabilityResult
from ..models.claim import ClaimPackage
from ..models.eligibility import EligibilityAssessment
from ..models.evidence import EvidenceManifest, RedactionReport
from ..models.opportunity import OpportunityState
from ..models.signal import IncidentSignal
from ..models.sla import SLAContract


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


class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"


class ErrorDisposition(str, Enum):
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
    simulation_mode: bool = True

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
    An LLM-backed node. In Phase 1 the ``stub_fn`` is called instead of a real
    Strands Agent so the graph is runnable without Bedrock credentials.

    In Phase 2 the stub_fn is replaced by a real ``strands.Agent`` call.
    """

    def __init__(
        self,
        name: str,
        tool_names: list[str],
        system_prompt: str = "",
        description: str = "",
        stub_fn: Callable[[GraphState], dict[str, Any]] | None = None,
    ) -> None:
        self.name = name
        self.tool_names = tool_names
        self.system_prompt = system_prompt
        self.description = description
        self._stub_fn = stub_fn

    def run(self, state: GraphState) -> dict[str, Any]:
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
    targets: dict[str, Union[str, AgentNode, DeterministicNode]]


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

    def run(self, initial_state: GraphState) -> GraphState:
        """
        Execute the graph sequentially in topological order.

        Conditional edges are evaluated against the live GraphState at runtime.
        Nodes that return a dict of updates are merged into the running state.
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

            updates = node.run(state)
            if updates:
                state = state.model_copy(update=updates)

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
