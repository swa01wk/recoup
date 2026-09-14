"""Recovery pipeline domain models — evidence, confidence, risk, plans."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class EvidenceGraphRelation(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"
    DEPENDS_ON = "depends_on"
    DERIVED_FROM = "derived_from"
    LEADS_TO = "leads_to"
    BLOCKS = "blocks"
    INCREASES_RISK = "increases_risk"
    REDUCES_RISK = "reduces_risk"


class SignalDirection(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"


class SafetyCheckStatus(StrEnum):
    PASS = "PASS"  # noqa: S105
    WARN = "WARN"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class RecoveryPlanStepPhase(StrEnum):
    PRECHECK = "precheck"
    EXECUTION = "execution"
    VERIFICATION = "verification"
    ROLLBACK = "rollback"


class EvidenceSufficiencyLevel(StrEnum):
    SUFFICIENT = "SUFFICIENT"
    PARTIAL = "PARTIAL"
    CONFLICTING = "CONFLICTING"
    INSUFFICIENT = "INSUFFICIENT"


class SavingsLifecycleStage(StrEnum):
    POTENTIAL = "POTENTIAL"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    IMPLEMENTED = "IMPLEMENTED"
    VERIFIED = "VERIFIED"


class RecoveryPolicyOutcome(StrEnum):
    AUTO_ALLOWED = "AUTO_ALLOWED"
    HITL_REQUIRED = "HITL_REQUIRED"
    BLOCKED = "BLOCKED"
    INVESTIGATE_FURTHER = "INVESTIGATE_FURTHER"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class OperationalSignal(BaseModel):
    signal_id: str
    resource_id: str
    resource_type: str = ""
    source: str
    signal_type: str
    metric_or_event: str = ""
    value: str
    unit: str = ""
    observation_window: str = ""
    observed_at: str = ""
    freshness: str = "current"
    raw_reference: str = ""
    description: str = ""
    direction: SignalDirection = SignalDirection.NEUTRAL
    strength: float = Field(default=0.5, ge=0.0, le=1.0)


class ResourceIdentity(BaseModel):
    resource_id: str
    resource_type: str = ""
    service: str = ""
    region: str = ""
    instance_type: str = ""


class ResourceEnvironment(BaseModel):
    environment: str = "unknown"
    tags: dict[str, str] = Field(default_factory=dict)
    owner: str = ""
    is_demo: bool = False
    scenario_tag: str = ""


class ResourceContext(BaseModel):
    identity: ResourceIdentity
    environment: ResourceEnvironment = Field(default_factory=ResourceEnvironment)
    cost_notes: list[str] = Field(default_factory=list)
    usage_notes: list[str] = Field(default_factory=list)
    activity_notes: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    recovery_notes: list[str] = Field(default_factory=list)


class EvidenceGraphNode(BaseModel):
    node_id: str
    kind: Literal["signal", "claim", "insight", "recommendation"] = "signal"
    label: str
    signal_id: str | None = None


class EvidenceGraphEdge(BaseModel):
    edge_id: str
    source_id: str
    target_id: str
    relation: EvidenceGraphRelation


class EvidenceGraph(BaseModel):
    nodes: list[EvidenceGraphNode] = Field(default_factory=list)
    edges: list[EvidenceGraphEdge] = Field(default_factory=list)


class EvidenceBundle(BaseModel):
    claim: str = ""
    supporting_signal_ids: list[str] = Field(default_factory=list)
    counter_signal_ids: list[str] = Field(default_factory=list)
    neutral_signal_ids: list[str] = Field(default_factory=list)
    missing_expected: list[str] = Field(default_factory=list)
    grouped: dict[str, list[str]] = Field(default_factory=dict)


class Insight(BaseModel):
    insight_id: str
    text: str
    title: str = ""
    summary: str = ""
    signal_ids: list[str] = Field(default_factory=list)
    contradicting_signal_ids: list[str] = Field(default_factory=list)
    edge_ids: list[str] = Field(default_factory=list)


class EvidenceSufficiency(BaseModel):
    level: EvidenceSufficiencyLevel
    reasons: list[str] = Field(default_factory=list)
    expected_signal_count: int = 0
    collected_signal_count: int = 0
    missing_critical_signals: list[str] = Field(default_factory=list)
    contradiction_count: int = 0


class ConfidenceFactorBreakdown(BaseModel):
    coverage: float = 0.0
    agreement: float = 0.0
    strength: float = 0.0
    freshness: float = 0.0
    source_diversity: float = 0.0
    dependency_certainty: float = 0.0
    contradiction_penalty: float = 0.0
    missing_evidence_penalty: float = 0.0
    explanation: str = ""


class ConfidenceScore(BaseModel):
    score: int = Field(ge=0, le=100)
    label: str = ""
    factors: ConfidenceFactorBreakdown = Field(default_factory=ConfidenceFactorBreakdown)
    evidence_signal_ids: list[str] = Field(default_factory=list)


class RiskFactor(BaseModel):
    name: str
    contribution: str
    label: str = ""
    level: str = ""
    signal_ids: list[str] = Field(default_factory=list)


class RiskAssessment(BaseModel):
    score: int = Field(ge=0, le=100, default=50)
    level: RiskLevel = RiskLevel.MEDIUM
    factors: list[RiskFactor] = Field(default_factory=list)
    explanation: str = ""


class FinancialImpact(BaseModel):
    current_monthly_usd: Decimal = Decimal("0.00")
    projected_monthly_recovery_usd: Decimal = Decimal("0.00")
    projected_annual_recovery_usd: Decimal = Decimal("0.00")
    lifecycle_stage: SavingsLifecycleStage = SavingsLifecycleStage.POTENTIAL
    calculation_trace: list[str] = Field(default_factory=list)


class RemediationOption(BaseModel):
    action_id: str
    label: str
    reversibility: str = "unknown"
    action_confidence: ConfidenceScore | None = None


class RecoveryRecommendation(BaseModel):
    primary_action_id: str
    primary_action_label: str
    reasoning: str = ""
    alternatives: list[RemediationOption] = Field(default_factory=list)
    rejected_alternatives: list[str] = Field(default_factory=list)
    expected_monthly_recovery_usd: Decimal = Decimal("0.00")
    reversibility: str = ""
    prerequisites: list[str] = Field(default_factory=list)


class RecoveryPlanStep(BaseModel):
    step_id: str
    title: str
    description: str = ""
    phase: RecoveryPlanStepPhase = RecoveryPlanStepPhase.EXECUTION
    status: str = "pending"


class SafetyCheck(BaseModel):
    check: str
    status: SafetyCheckStatus
    summary: str = ""


class RecoveryPlan(BaseModel):
    prerequisites: list[str] = Field(default_factory=list)
    pre_action_checks: list[str] = Field(default_factory=list)
    execution_steps: list[str] = Field(default_factory=list)
    rollback_strategy: str = ""
    verification_steps: list[str] = Field(default_factory=list)
    policy_requirements: list[str] = Field(default_factory=list)
    human_approval_required: bool = True
    structured_steps: list[RecoveryPlanStep] = Field(default_factory=list)


class InvestigationIteration(BaseModel):
    iteration: int
    trigger: str = "investigate_further"
    missing_before: list[str] = Field(default_factory=list)
    sufficiency_before: EvidenceSufficiencyLevel | None = None
    discovery_confidence_before: int | None = None
    action_confidence_before: int | None = None
    sufficiency_after: EvidenceSufficiencyLevel | None = None
    discovery_confidence_after: int | None = None
    action_confidence_after: int | None = None
    notes: str = ""
    recommendation_changed: bool = False
    reason_for_change: str = ""
    previous_primary_action_label: str = ""
    new_primary_action_label: str = ""


class WorkflowSnapshot(BaseModel):
    workflow_state: str = ""
    pipeline_stage: int = Field(default=1, ge=1, le=11)
    execution_status: str = ""


class RecoveryAssessment(BaseModel):
    pipeline_phase: str = "UNDERSTAND"
    resource_context: ResourceContext | None = None
    signals: list[OperationalSignal] = Field(default_factory=list)
    evidence_graph: EvidenceGraph = Field(default_factory=EvidenceGraph)
    evidence_bundle: EvidenceBundle = Field(default_factory=EvidenceBundle)
    insights: list[Insight] = Field(default_factory=list)
    evidence_sufficiency: EvidenceSufficiency | None = None
    discovery_confidence: ConfidenceScore | None = None
    action_confidences: dict[str, ConfidenceScore] = Field(default_factory=dict)
    risk_assessment: RiskAssessment | None = None
    financial_impact: FinancialImpact | None = None
    recommendation: RecoveryRecommendation | None = None
    recovery_plan: RecoveryPlan | None = None
    recovery_policy_outcome: RecoveryPolicyOutcome = RecoveryPolicyOutcome.HITL_REQUIRED
    policy_note: str = ""
    priority_score: int = Field(default=0, ge=0, le=100)
    priority_explanation: str = ""
    audit_trail: list[InvestigationIteration] = Field(default_factory=list)
    investigation_plan: list[str] = Field(default_factory=list)
    safety_checks: list[SafetyCheck] = Field(default_factory=list)

    def summary_for_api(self) -> dict[str, Any]:
        """Denormalized fields for list/get opportunity responses."""
        primary_action = (
            self.recommendation.primary_action_label if self.recommendation else None
        )
        action_conf = None
        if self.recommendation and self.recommendation.primary_action_id:
            ac = self.action_confidences.get(self.recommendation.primary_action_id)
            action_conf = ac.score if ac else None
        return {
            "discovery_confidence": (
                self.discovery_confidence.score if self.discovery_confidence else None
            ),
            "action_confidence": action_conf,
            "risk_level": (
                self.risk_assessment.level.value if self.risk_assessment else None
            ),
            "evidence_sufficiency": (
                self.evidence_sufficiency.level.value
                if self.evidence_sufficiency
                else None
            ),
            "priority_score": self.priority_score,
            "recommended_action": primary_action,
        }
