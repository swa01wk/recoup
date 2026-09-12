"use client";

import { Tooltip } from "@/components/ui/tooltip";
import { MetricCard } from "@/components/recoup/metric-card";
import { ConfidenceIndicator } from "@/components/recoup/confidence-indicator";
import { RiskIndicator } from "@/components/recoup/risk-indicator";
import { fmtSavings, fmtYearlySavings } from "@/lib/recoup-ui-rules";
import type { RecoveryAssessment } from "@/lib/recovery-types";
import {
  actionConfidenceForPrimary,
  actionConfidenceAlternatives,
  confidenceFactorsLines,
  discoveryConfidenceLabel,
  riskLevelLabel,
  riskTooltipLines,
  riskTierFromLevel,
  signalCount,
  sufficiencyTooltipLines,
} from "@/lib/recovery-presentation";

interface SummaryMetricCardsProps {
  assessment: RecoveryAssessment | null;
  savings: number;
  riskTier: string;
  discoveryConf: number | null;
  actionConf: number | null;
  evidenceFallbackCount: number;
}

export function SummaryMetricCards({
  assessment,
  savings,
  riskTier,
  discoveryConf,
  actionConf,
  evidenceFallbackCount,
}: SummaryMetricCardsProps) {
  const suff = assessment?.evidence_sufficiency;
  const suffLevel = suff?.level ?? "—";
  const nSignals = assessment ? signalCount(assessment) : evidenceFallbackCount;
  const risk = assessment?.risk_assessment;
  const tier =
    riskTier ||
    riskTierFromLevel(risk?.level) ||
    "YELLOW";
  const primaryLabel = assessment?.recommendation?.primary_action_label ?? "";

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
      <Tooltip
        content={
          <div className="space-y-0.5">
            {sufficiencyTooltipLines(suff).map((line) => (
              <div key={line}>{line}</div>
            ))}
          </div>
        }
      >
        <div className="rounded-lg border border-slate-700/40 bg-slate-800/30 px-4 py-3 min-h-[88px] flex flex-col justify-center cursor-default">
          <span className="text-[10px] font-medium uppercase tracking-widest text-slate-500">
            Evidence
          </span>
          <p className="text-lg font-bold text-slate-200 mt-1">{nSignals} signals</p>
          <p className="text-xs font-medium text-emerald-400/90 mt-0.5">{suffLevel}</p>
        </div>
      </Tooltip>

      <div className="rounded-lg border border-slate-700/40 bg-slate-800/30 px-4 py-3 min-h-[88px] flex flex-col justify-center">
        <MetricCard label="Impact" value={fmtSavings(savings)} sub={fmtYearlySavings(savings)} accent="green" />
      </div>

      <Tooltip
        content={
          <div className="space-y-0.5 max-w-xs">
            {riskTooltipLines(risk).map((line) => (
              <div key={line}>{line}</div>
            ))}
          </div>
        }
      >
        <div className="rounded-lg border border-slate-700/40 bg-slate-800/30 px-4 py-3 min-h-[88px] flex flex-col justify-center cursor-default">
          <span className="text-[10px] font-medium uppercase tracking-widest text-slate-500 mb-1">
            Risk
          </span>
          <RiskIndicator tier={tier} />
          <p className="text-[10px] text-slate-500 mt-1">
            {risk?.factors?.length ?? 0} contributing factors
          </p>
          <p className="text-[10px] text-slate-500">Operational impact if wrong</p>
        </div>
      </Tooltip>

      <Tooltip
        content={
          <div className="space-y-0.5">
            <div className="font-medium text-slate-200 mb-1">
              Discovery Confidence {discoveryConf != null ? `${Math.round(discoveryConf)}%` : "—"}
            </div>
            {confidenceFactorsLines(assessment?.discovery_confidence ?? null).map((line) => (
              <div key={line}>{line}</div>
            ))}
          </div>
        }
      >
        <div className="rounded-lg border border-slate-700/40 bg-slate-800/30 px-4 py-3 min-h-[88px] flex flex-col justify-center cursor-default">
          <ConfidenceIndicator value={discoveryConf} label="Discovery Confidence" />
          <p className="text-[10px] text-slate-500 mt-1 line-clamp-2">
            {discoveryConfidenceLabel(discoveryConf)}
          </p>
        </div>
      </Tooltip>

      <Tooltip
        content={
          <div className="space-y-0.5">
            {actionConfidenceAlternatives(assessment).map((a) => (
              <div key={a.label}>
                {a.label}: {Math.round(a.score)}%
              </div>
            ))}
          </div>
        }
      >
        <div className="rounded-lg border border-slate-700/40 bg-slate-800/30 px-4 py-3 min-h-[88px] flex flex-col justify-center cursor-default">
          <ConfidenceIndicator
            value={actionConf ?? actionConfidenceForPrimary(assessment)}
            label="Action Confidence"
          />
          {primaryLabel && (
            <p className="text-[10px] text-slate-400 mt-1 truncate" title={primaryLabel}>
              {primaryLabel}
            </p>
          )}
        </div>
      </Tooltip>
    </div>
  );
}

export { riskLevelLabel };
