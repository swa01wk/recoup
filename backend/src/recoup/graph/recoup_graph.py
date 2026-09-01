"""
Recoup recovery graph — assembles all 11 nodes and their edges.

Import and call ``build_recoup_graph()`` to get a ready-to-run Graph instance.
The graph is validated at build time so misconfigured edges raise immediately.

Usage:
    graph = build_recoup_graph()
    initial_state = GraphState(opportunity_id="opp-001", signal=signal)
    final_state = graph.run(initial_state)
"""

from .nodes import (
    availability_calculator_fn,
    case_monitor_stub,
    claim_package_generator_stub,
    eligibility_reasoner_stub,
    evidence_collector_stub,
    evidence_sanitizer_fn,
    incident_correlation_stub,
    normalize_event_fn,
    risk_policy_gate_fn,
    sla_contract_resolver_fn,
    submission_adapter_fn,
)
from .types import (
    AgentNode,
    ConditionalEdge,
    DeterministicNode,
    Graph,
    GraphState,
    PolicyDecision,
)

# ---------------------------------------------------------------------------
# Node definitions — names match the plan exactly
# ---------------------------------------------------------------------------

normalize_event = DeterministicNode(
    name="normalize_event",
    fn=normalize_event_fn,
    description="Parse raw EventBridge/replay payload → typed IncidentSignal",
)

incident_correlation = AgentNode(
    name="incident_correlation",
    tool_names=["get_cloudwatch_metrics", "get_health_event", "lookup_cloudtrail_events"],
    system_prompt=(
        "You are a cloud reliability engineer analyzing an AWS incident. "
        "Correlate the incident signal with CloudWatch metrics, health events, "
        "and CloudTrail to form a hypothesis about availability impact. "
        "Output ONLY factual observations. Never conclude financial eligibility."
    ),
    description="Correlate signal with AWS data → IncidentHypothesis",
    stub_fn=incident_correlation_stub,
)

sla_contract_resolver = DeterministicNode(
    name="sla_contract_resolver",
    fn=sla_contract_resolver_fn,
    description="Load applicable SLA contract from local catalog → SLAContract",
)

availability_calculator = DeterministicNode(
    name="availability_calculator",
    fn=availability_calculator_fn,
    description="Pure-arithmetic monthly uptime % and credit calculation → AvailabilityResult",
)

evidence_collector = AgentNode(
    name="evidence_collector",
    tool_names=[
        "get_cloudwatch_metrics",
        "query_cloudwatch_logs",
        "get_cost_and_usage",
        "store_evidence",
    ],
    system_prompt=(
        "You are collecting evidence for an AWS SLA claim. "
        "Gather CloudWatch metrics, logs, and billing records for the incident period. "
        "Store all raw evidence to S3 before referencing it. "
        "Return only evidence IDs — never raw evidence content."
    ),
    description="Gather and store AWS evidence → EvidenceManifest",
    stub_fn=evidence_collector_stub,
)

evidence_sanitizer = DeterministicNode(
    name="evidence_sanitizer",
    fn=evidence_sanitizer_fn,
    description="Apply deterministic redaction rules → sanitized EvidenceManifest",
)

eligibility_reasoner = AgentNode(
    name="eligibility_reasoner",
    tool_names=[],  # Read-only; references evidence by ID only — no tool calls
    system_prompt=(
        "You are a cloud billing specialist assessing SLA claim eligibility. "
        "Review the SLA contract terms, availability result, and evidence manifest. "
        "Reference evidence ONLY by ID from the manifest — never invent IDs. "
        "Never make financial conclusions; only assess contractual eligibility."
    ),
    description="Assess contractual eligibility → EligibilityAssessment",
    stub_fn=eligibility_reasoner_stub,
)

risk_policy_gate = DeterministicNode(
    name="risk_policy_gate",
    fn=risk_policy_gate_fn,
    description="Cedar policy evaluation → PolicyDecision (ALLOW/REQUIRE_APPROVAL/DENY)",
)

claim_package_generator = AgentNode(
    name="claim_package_generator",
    tool_names=["store_evidence"],
    system_prompt=(
        "You are drafting an AWS SLA credit claim. "
        "Use ONLY the evidence IDs from the sanitized manifest. "
        "Do not invent new evidence IDs. "
        "Format the claim body professionally and concisely."
    ),
    description="Assemble the complete ClaimPackage from sanitized evidence",
    stub_fn=claim_package_generator_stub,
)

submission_adapter = DeterministicNode(
    name="submission_adapter",
    fn=submission_adapter_fn,
    description="Submit to AWS Support or produce simulation case_id",
)

case_monitor = AgentNode(
    name="case_monitor",
    tool_names=["get_support_case_status"],
    system_prompt=(
        "You are monitoring an AWS Support case for SLA credit resolution. "
        "Poll the case status and report the outcome."
    ),
    description="Poll support case → CaseOutcome",
    stub_fn=case_monitor_stub,
)


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def build_recoup_graph() -> Graph:
    """
    Build and validate the complete Recoup recovery graph.

    Returns a Graph that is ready to execute. Call ``graph.run(initial_state)``
    with a ``GraphState`` that has at minimum ``opportunity_id`` and ``signal``
    populated.

    Raises:
        ValueError: If any edge endpoint is not a registered node.
    """
    graph = Graph(name="recoup-recovery")

    # Register all nodes
    for node in [
        normalize_event,
        incident_correlation,
        sla_contract_resolver,
        availability_calculator,
        evidence_collector,
        evidence_sanitizer,
        eligibility_reasoner,
        risk_policy_gate,
        claim_package_generator,
        submission_adapter,
        case_monitor,
    ]:
        graph.add_node(node)

    # Linear edges
    graph.add_edge(normalize_event, incident_correlation)
    graph.add_edge(incident_correlation, sla_contract_resolver)
    graph.add_edge(sla_contract_resolver, availability_calculator)
    graph.add_edge(availability_calculator, evidence_collector)
    graph.add_edge(evidence_collector, evidence_sanitizer)
    graph.add_edge(evidence_sanitizer, eligibility_reasoner)
    graph.add_edge(eligibility_reasoner, risk_policy_gate)

    # Conditional edge after risk_policy_gate
    graph.add_conditional_edge(
        source=risk_policy_gate,
        condition=lambda s: (s.policy_decision or PolicyDecision.DENY).value,
        targets={
            PolicyDecision.REQUIRE_APPROVAL.value: "await_human_approval",
            PolicyDecision.ALLOW.value: claim_package_generator.name,
            PolicyDecision.DENY.value: "terminal_denied",
        },
    )

    # After human approval resumes (handled externally — graph re-entry)
    graph.add_edge("await_human_approval", claim_package_generator)
    graph.add_edge(claim_package_generator, submission_adapter)
    graph.add_edge(submission_adapter, case_monitor)

    graph.validate()
    return graph


# Module-level singleton — import this for the standard graph instance
recoup_graph = build_recoup_graph()
