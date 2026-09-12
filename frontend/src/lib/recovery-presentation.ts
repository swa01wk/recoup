import type {
  ConfidenceScore,
  RecoveryAssessment,
  OperationalSignal,
  RiskAssessment,
  EvidenceSufficiency,
} from "@/lib/recovery-types";

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
