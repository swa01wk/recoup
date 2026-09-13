/** Mirrors backend RecoveryAssessment JSON (snake_case). */

export interface ConfidenceFactorBreakdown {
  coverage?: number;
  agreement?: number;
  strength?: number;
  freshness?: number;
  source_diversity?: number;
  dependency_certainty?: number;
  contradiction_penalty?: number;
  missing_evidence_penalty?: number;
  explanation?: string;
}

export interface ConfidenceScore {
  score: number;
  label?: string;
  factors?: ConfidenceFactorBreakdown | Record<string, number | string>;
  evidence_signal_ids?: string[];
}

export type SignalDirection = "supports" | "contradicts" | "neutral";

export interface OperationalSignal {
  signal_id: string;
  description: string;
  signal_type: string;
  metric_or_event?: string;
  value: string;
  source?: string;
  unit?: string;
  observation_window?: string;
  observed_at?: string;
  freshness?: string;
  raw_reference?: string;
  direction?: SignalDirection;
  strength?: number;
}

export interface EvidenceGraphNode {
  node_id: string;
  kind: string;
  label: string;
  signal_id?: string | null;
}

export interface EvidenceGraphEdge {
  edge_id: string;
  source_id: string;
  target_id: string;
  relation: string;
}

export interface EvidenceGraph {
  nodes: EvidenceGraphNode[];
  edges: EvidenceGraphEdge[];
}

export interface EvidenceBundle {
  claim?: string;
  supporting_signal_ids: string[];
  counter_signal_ids: string[];
  neutral_signal_ids?: string[];
  missing_expected?: string[];
  grouped?: Record<string, string[]>;
}

export interface Insight {
  insight_id: string;
  text: string;
  title?: string;
  summary?: string;
  signal_ids?: string[];
  contradicting_signal_ids?: string[];
}

export interface EvidenceSufficiency {
  level: string;
  reasons?: string[];
  expected_signal_count?: number;
  collected_signal_count?: number;
  missing_critical_signals?: string[];
  contradiction_count?: number;
}

export interface RiskFactor {
  name: string;
  contribution: string;
  label?: string;
  level?: string;
}

export interface RiskAssessment {
  score: number;
  level: string;
  explanation?: string;
  factors?: RiskFactor[];
}

export interface RemediationOption {
  action_id: string;
  label: string;
  reversibility?: string;
  action_confidence?: ConfidenceScore | null;
}

export interface RecoveryRecommendation {
  primary_action_id: string;
  primary_action_label: string;
  reasoning?: string;
  alternatives?: RemediationOption[];
  rejected_alternatives?: string[];
  expected_monthly_recovery_usd?: string;
  reversibility?: string;
  prerequisites?: string[];
}

export type RecoveryPlanStepPhase = "precheck" | "execution" | "verification" | "rollback";

export interface RecoveryPlanStep {
  step_id: string;
  title: string;
  description?: string;
  phase: RecoveryPlanStepPhase;
  status?: string;
}

export interface RecoveryPlan {
  prerequisites?: string[];
  pre_action_checks?: string[];
  execution_steps?: string[];
  rollback_strategy?: string;
  verification_steps?: string[];
  policy_requirements?: string[];
  structured_steps?: RecoveryPlanStep[];
}

export type SafetyCheckStatus = "PASS" | "WARN" | "FAIL" | "UNKNOWN";

export interface SafetyCheck {
  check: string;
  status: SafetyCheckStatus;
  summary?: string;
}

export interface FinancialImpact {
  current_monthly_usd?: string;
  projected_monthly_recovery_usd?: string;
  projected_annual_recovery_usd?: string;
  lifecycle_stage?: string;
  calculation_trace?: string[];
}

export interface WorkflowSnapshot {
  workflow_state?: string;
  pipeline_stage?: number;
  execution_status?: string;
}

export interface InvestigationDelta {
  recommendation_changed?: boolean;
  reason_for_change?: string;
  previous_assessment?: {
    recommended_action?: string | null;
    discovery_confidence?: number | null;
  };
  new_assessment?: {
    recommended_action?: string | null;
    discovery_confidence?: number | null;
  };
}

export interface RecoveryAssessment {
  pipeline_phase?: string;
  signals: OperationalSignal[];
  evidence_graph?: EvidenceGraph;
  evidence_bundle?: EvidenceBundle;
  insights?: Insight[];
  evidence_sufficiency?: EvidenceSufficiency;
  discovery_confidence?: ConfidenceScore;
  action_confidences?: Record<string, ConfidenceScore>;
  risk_assessment?: RiskAssessment;
  financial_impact?: FinancialImpact;
  recommendation?: RecoveryRecommendation;
  recovery_plan?: RecoveryPlan;
  recovery_policy_outcome?: string;
  policy_note?: string;
  priority_score?: number;
  priority_explanation?: string;
  safety_checks?: SafetyCheck[];
}
