import type {
  ConfidenceScore,
  RecoveryAssessment,
  OperationalSignal,
  RiskAssessment,
  EvidenceSufficiency,
} from "@/lib/recovery-types";
import { PIPELINE_STAGE_HINTS } from "@/lib/recoup-ui-rules";

export function riskTierFromLevel(level: string | undefined): string {
  if (!level) return "YELLOW";
  const u = level.toUpperCase();
  if (u === "LOW") return "GREEN";
  if (u === "MEDIUM") return "YELLOW";
  return "RED";
}

export function riskLevelLabel(level: string | undefined): string {
  if (!level) return "Medium";
  const u = level.toUpperCase();
  if (u === "LOW") return "Low";
  if (u === "MEDIUM") return "Medium";
  if (u === "HIGH") return "High";
  if (u === "CRITICAL") return "Critical";
  return level;
}

export function discoveryConfidenceLabel(score: number | null | undefined): string {
  if (score == null) return "—";
  if (score >= 90) return "Opportunity is likely real";
  if (score >= 75) return "Strong evidence alignment";
  if (score >= 50) return "Moderate confidence";
  return "Needs more evidence";
}

export function evidenceBulletsFromAssessment(
  assessment: RecoveryAssessment | null | undefined
): { supporting: string[]; counter: string[] } {
  if (!assessment?.signals?.length) {
    return { supporting: [], counter: [] };
  }
  const byId = new Map(assessment.signals.map((s) => [s.signal_id, s]));
  const supporting = (assessment.evidence_bundle?.supporting_signal_ids ?? [])
    .map((id) => byId.get(id)?.description ?? id)
    .filter(Boolean);
  const counter = (assessment.evidence_bundle?.counter_signal_ids ?? [])
    .map((id) => byId.get(id)?.description ?? id)
    .filter(Boolean);
  if (supporting.length === 0) {
    return {
      supporting: assessment.signals
        .filter((s) => s.direction !== "contradicts")
        .slice(0, 6)
        .map((s) => s.description || s.value),
      counter,
    };
  }
  return { supporting, counter };
}

export function signalCount(assessment: RecoveryAssessment | null | undefined): number {
  return assessment?.signals?.length ?? 0;
}

export function insightSummary(assessment: RecoveryAssessment | null | undefined): string | null {
  const ins = assessment?.insights?.[0];
  if (!ins) return null;
  return ins.summary || ins.text || null;
}

export function topInsight(assessment: RecoveryAssessment | null | undefined): string | null {
  return insightSummary(assessment);
}

export function actionConfidenceForPrimary(
  assessment: RecoveryAssessment | null | undefined
): number | null {
  if (!assessment?.recommendation) return null;
  const id = assessment.recommendation.primary_action_id;
  const ac = assessment.action_confidences?.[id];
  return ac?.score ?? null;
}

export function confidenceFactorsLines(
  conf: ConfidenceScore | null | undefined
): string[] {
  if (!conf?.factors || typeof conf.factors !== "object") return [];
  const f = conf.factors as Record<string, number>;
  const lines: string[] = [];
  const pct = (v: number) => `${Math.round(v <= 1 ? v * 100 : v)}%`;
  if (f.coverage != null) lines.push(`Coverage ${pct(f.coverage)}`);
  if (f.agreement != null) lines.push(`Agreement ${pct(f.agreement)}`);
  if (f.strength != null) lines.push(`Strength ${pct(f.strength)}`);
  if (f.freshness != null) lines.push(`Freshness ${pct(f.freshness)}`);
  if (f.source_diversity != null) lines.push(`Source diversity ${pct(f.source_diversity)}`);
  if (f.contradiction_penalty != null && f.contradiction_penalty > 0) {
    lines.push(`Contradictions -${pct(f.contradiction_penalty)}`);
  }
  return lines;
}

export function sufficiencyTooltipLines(
  suff: EvidenceSufficiency | null | undefined
): string[] {
  if (!suff) return [];
  const missing =
    suff.missing_critical_signals?.length
      ? suff.missing_critical_signals.join(", ")
      : "None";
  return [
    `Expected signals: ${suff.expected_signal_count ?? "—"}`,
    `Collected: ${suff.collected_signal_count ?? "—"}`,
    `Missing critical evidence: ${missing}`,
    `Contradictions: ${suff.contradiction_count ?? 0}`,
  ];
}

export function riskTooltipLines(risk: RiskAssessment | null | undefined): string[] {
  if (!risk) return [];
  const lines = (risk.factors ?? []).map(
    (f) => `${f.label || f.name}: ${f.level || f.contribution}`
  );
  lines.push(`Risk score: ${risk.score}/100`);
  lines.push("Calculated from AWS context and policy signals.");
  return lines;
}

export function actionConfidenceAlternatives(
  assessment: RecoveryAssessment | null | undefined,
  limit = 3
): { label: string; score: number }[] {
  if (!assessment?.recommendation) return [];
  const primaryId = assessment.recommendation.primary_action_id;
  const entries: { label: string; score: number }[] = [];
  for (const alt of assessment.recommendation.alternatives ?? []) {
    const sc =
      alt.action_confidence?.score ??
      assessment.action_confidences?.[alt.action_id]?.score;
    if (sc != null) entries.push({ label: alt.label, score: sc });
  }
  for (const [id, conf] of Object.entries(assessment.action_confidences ?? {})) {
    if (id === primaryId) continue;
    if (entries.some((e) => e.label === id)) continue;
    entries.push({ label: id, score: conf.score });
  }
  return entries.sort((a, b) => b.score - a.score).slice(0, limit);
}

export function monthlySavingsFromAssessment(
  assessment: RecoveryAssessment | null | undefined,
  fallback: number
): number {
  const raw = assessment?.financial_impact?.projected_monthly_recovery_usd;
  if (raw != null) {
    const n = parseFloat(String(raw));
    if (!isNaN(n)) return n;
  }
  const rec = assessment?.recommendation?.expected_monthly_recovery_usd;
  if (rec != null) {
    const n = parseFloat(String(rec));
    if (!isNaN(n)) return n;
  }
  return fallback;
}

export function groupedEvidenceLabels(
  signals: OperationalSignal[],
  ids: string[]
): string[] {
  const byId = new Map(signals.map((s) => [s.signal_id, s]));
  return ids.map((id) => byId.get(id)?.description ?? id);
}

export function supportingSignalCount(assessment: RecoveryAssessment | null | undefined): number {
  if (!assessment) return 0;
  const ids = assessment.evidence_bundle?.supporting_signal_ids ?? [];
  if (ids.length > 0) return ids.length;
  return assessment.signals.filter((s) => s.direction !== "contradicts").length;
}

export function evidenceKpiSentence(
  assessment: RecoveryAssessment | null | undefined,
  fallbackSupportingCount: number
): string {
  const n = assessment ? signalCount(assessment) : fallbackSupportingCount;
  const support = assessment ? supportingSignalCount(assessment) : fallbackSupportingCount;
  const counter = assessment?.evidence_bundle?.counter_signal_ids?.length ?? 0;
  if (n === 0) return "Evidence is still being collected.";
  if (counter === 0) {
    return `${support} signal${support === 1 ? "" : "s"} support the finding. No meaningful contradictory evidence detected.`;
  }
  return `${support} signal${support === 1 ? "" : "s"} support the finding. ${counter} contradictory signal${counter === 1 ? "" : "s"} noted.`;
}

export function riskSummarySentence(
  assessment: RecoveryAssessment | null | undefined,
  riskTier: string
): string {
  const risk = assessment?.risk_assessment;
  if (risk?.explanation?.trim()) return risk.explanation.trim();
  const factor = risk?.factors?.[0];
  if (factor?.label || factor?.name) {
    return `${factor.label || factor.name}: ${factor.level || factor.contribution || "see factors"}.`;
  }
  const tier = risk?.level ? riskLevelLabel(risk.level) : riskLevelLabel(
    riskTier === "GREEN" ? "LOW" : riskTier === "RED" ? "HIGH" : "MEDIUM"
  );
  if (tier === "Low") return "Reversible action with limited expected operational impact.";
  if (tier === "High" || tier === "Critical") return "Higher operational impact if the assessment is wrong.";
  return "Moderate operational impact if the assessment is wrong.";
}

export function actionConfidenceKpiSentence(assessment: RecoveryAssessment | null | undefined): string {
  const label = assessment?.recommendation?.primary_action_label;
  const reasoning = assessment?.recommendation?.reasoning?.trim();
  if (label && reasoning) {
    const short = reasoning.length > 120 ? `${reasoning.slice(0, 117)}…` : reasoning;
    return short;
  }
  if (label) return `${label} is currently the strongest recovery action at this evidence level.`;
  return "Recovery action confidence reflects evidence alignment and reversibility.";
}

export function rollbackKpiLabel(
  assessment: RecoveryAssessment | null | undefined,
  rollbackFallback: string
): { value: string; sentence: string } {
  const strategy = assessment?.recovery_plan?.rollback_strategy?.trim() || rollbackFallback.trim();
  const rev = assessment?.recommendation?.reversibility?.toLowerCase() ?? "";
  const available =
    rev.includes("reversible") ||
    (strategy.length > 0 && !/destructive|limited rollback|snapshot/i.test(strategy));
  if (available && strategy) {
    const short = strategy.length > 100 ? `${strategy.slice(0, 97)}…` : strategy;
    return { value: "Available", sentence: short };
  }
  if (available) return { value: "Available", sentence: "The approved action supports rollback if verification fails." };
  return { value: "Limited", sentence: strategy || "Rollback path may be limited for this action." };
}

export function policyLabelFromAssessment(assessment: RecoveryAssessment | null | undefined): string {
  const note = assessment?.policy_note?.trim();
  if (note) return note;
  const outcome = assessment?.recovery_policy_outcome;
  if (outcome === "HITL_REQUIRED" || outcome === "AUTO_ALLOWED") {
    return outcome === "AUTO_ALLOWED"
      ? "Auto-allowed when policy gates pass"
      : "Human approval required";
  }
  if (outcome === "BLOCKED") return "Recovery blocked by policy";
  if (outcome === "INVESTIGATE_FURTHER") return "Investigate further before approval";
  return "Default human approval for cost recovery actions";
}

export function discoveryConfidenceSupportingFactors(
  assessment: RecoveryAssessment | null | undefined
): string[] {
  if (!assessment) return [];
  const signals = assessment.signals;
  const byId = new Map(signals.map((s) => [s.signal_id, s]));
  const fromIds = (assessment.discovery_confidence?.evidence_signal_ids ?? [])
    .map((id) => byId.get(id)?.description || byId.get(id)?.value)
    .filter(Boolean) as string[];
  const fromSuff = assessment.evidence_sufficiency?.reasons ?? [];
  const fromBundle = groupedEvidenceLabels(
    signals,
    assessment.evidence_bundle?.supporting_signal_ids ?? []
  );
  return [...new Set([...fromIds, ...fromSuff, ...fromBundle])].slice(0, 8);
}

export function discoveryConfidenceUncertaintyFactors(
  assessment: RecoveryAssessment | null | undefined
): string[] {
  if (!assessment) return [];
  const lines: string[] = [];
  for (const m of assessment.evidence_sufficiency?.missing_critical_signals ?? []) {
    lines.push(m);
  }
  for (const m of assessment.evidence_bundle?.missing_expected ?? []) {
    lines.push(m);
  }
  const factors = assessment.discovery_confidence?.factors as Record<string, number> | undefined;
  if (factors?.missing_evidence_penalty != null && factors.missing_evidence_penalty > 0) {
    lines.push("Some expected evidence is still missing");
  }
  for (const c of assessment.safety_checks ?? []) {
    if (c.status === "UNKNOWN" || c.status === "WARN") {
      lines.push(c.summary || c.check);
    }
  }
  return [...new Set(lines)].slice(0, 6);
}

export function actionConfidenceSupportingFactors(
  assessment: RecoveryAssessment | null | undefined
): string[] {
  if (!assessment) return [];
  const lines: string[] = [];
  const rev = assessment.recommendation?.reversibility;
  if (rev?.toLowerCase().includes("reversible")) {
    lines.push("Selected action supports rollback");
  }
  for (const c of assessment.safety_checks ?? []) {
    if (c.status === "PASS") lines.push(c.summary || c.check);
  }
  const expl = assessment.action_confidences?.[assessment.recommendation?.primary_action_id ?? ""]
    ?.factors;
  if (expl && typeof expl === "object" && "explanation" in expl) {
    const e = (expl as { explanation?: string }).explanation;
    if (e?.trim()) lines.push(e.trim());
  }
  return [...new Set(lines)].slice(0, 8);
}

export function actionConfidenceUncertaintyFactors(
  assessment: RecoveryAssessment | null | undefined
): string[] {
  if (!assessment) return [];
  const lines: string[] = [];
  for (const c of assessment.safety_checks ?? []) {
    if (c.status === "UNKNOWN" || c.status === "WARN") {
      lines.push(c.summary || c.check);
    }
  }
  return [...new Set(lines)].slice(0, 6);
}

export function policyGovernanceLines(assessment: RecoveryAssessment | null | undefined): string[] {
  const lines: string[] = [];
  lines.push(`Approval policy: ${policyLabelFromAssessment(assessment)}`);
  lines.push("Access model: Read-only discovery. No resource modification without approval.");
  const guards = assessment?.recovery_plan?.policy_requirements ?? [];
  if (guards.length) {
    lines.push(`Guardrails: ${guards.join("; ")}`);
  } else {
    lines.push("Guardrails: Recovery actions require appropriate safety and rollback checks.");
  }
  return lines;
}

export function pipelineStageExplanation(
  stage: number,
  assessment: RecoveryAssessment | null | undefined,
  pendingApproval: boolean
): string[] {
  const base = PIPELINE_STAGE_HINTS[stage];
  const lines: string[] = base ? [base] : [];
  if (stage === 3 && assessment) {
    const n = signalCount(assessment);
    if (n > 0) lines.push(`${n} independent signal${n === 1 ? "" : "s"} correlated for this resource.`);
  }
  if (stage === 5 && assessment?.evidence_sufficiency) {
    lines.push(`Evidence sufficiency: ${assessment.evidence_sufficiency.level}.`);
  }
  if (stage === 8 && pendingApproval) {
    lines.push("Operator approve, investigate further, or decline.");
  }
  return lines.slice(0, 4);
}
