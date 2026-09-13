"use client";

import { OpportunityKpiCard } from "@/components/recoup/opportunity-kpi-card";
import { fmtSavings, fmtYearlySavings } from "@/lib/recoup-ui-rules";
import type { RecoveryAssessment } from "@/lib/recovery-types";
import {
  actionConfidenceKpiSentence,
  discoveryConfidenceLabel,
  evidenceKpiSentence,
  riskLevelLabel,
  riskSummarySentence,
  rollbackKpiLabel,
  signalCount,
} from "@/lib/recovery-presentation";

interface SummaryMetricCardsProps {
  assessment: RecoveryAssessment | null;
  savings: number;
  riskTier: string;
  discoveryConf: number | null;
  actionConf: number | null;
  evidenceFallbackCount: number;
  rollbackFallback: string;
}

export function SummaryMetricCards({
  assessment,
  savings,
  riskTier,
  discoveryConf,
  actionConf,
  evidenceFallbackCount,
  rollbackFallback,
}: SummaryMetricCardsProps) {
  const nSignals = assessment ? signalCount(assessment) : evidenceFallbackCount;
  const riskLevel =
    assessment?.risk_assessment?.level != null
      ? riskLevelLabel(assessment.risk_assessment.level)
      : riskLevelLabel(
          riskTier === "GREEN" ? "LOW" : riskTier === "RED" ? "HIGH" : "MEDIUM"
        );
  const rollback = rollbackKpiLabel(assessment, rollbackFallback);

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      <OpportunityKpiCard
        label="Evidence"
        value={`${nSignals} signal${nSignals === 1 ? "" : "s"}`}
        sentence={evidenceKpiSentence(assessment, evidenceFallbackCount)}
      />
      <OpportunityKpiCard
        label="Impact"
        value={fmtSavings(savings)}
        sentence={`${fmtYearlySavings(savings)} projected recovery.`}
      />
      <OpportunityKpiCard
        label="Risk"
        value={riskLevel}
        sentence={riskSummarySentence(assessment, riskTier)}
      />
      <OpportunityKpiCard
        label="Discovery Confidence"
        value={discoveryConf != null ? `${Math.round(discoveryConf)}%` : "—"}
        sentence={discoveryConfidenceLabel(discoveryConf)}
      />
      <OpportunityKpiCard
        label="Action Confidence"
        value={actionConf != null ? `${Math.round(actionConf)}%` : "—"}
        sentence={actionConfidenceKpiSentence(assessment)}
      />
      <OpportunityKpiCard label="Rollback" value={rollback.value} sentence={rollback.sentence} />
    </div>
  );
}

export { riskLevelLabel };
