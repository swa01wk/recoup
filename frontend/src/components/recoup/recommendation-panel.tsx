"use client";

import { fmtSavings } from "@/lib/recoup-ui-rules";
import type { RecoveryAssessment } from "@/lib/recovery-types";
import { actionConfidenceAlternatives, actionConfidenceForPrimary } from "@/lib/recovery-presentation";
import { SafetyChecklist } from "@/components/recoup/safety-checklist";

interface RecommendationPanelProps {
  action: string;
  detail?: string;
  assessment: RecoveryAssessment | null;
  savings: number;
  rollback: string;
}

export function RecommendationPanel({
  action,
  detail,
  assessment,
  savings,
  rollback,
}: RecommendationPanelProps) {
  const actionConf = actionConfidenceForPrimary(assessment);
  const alts = actionConfidenceAlternatives(assessment, 2);
  const alt = alts.find(
    (a) => a.label !== action && !action.includes(a.label)
  );
  const whyNot =
    alt && alt.score < (actionConf ?? 0)
      ? `More destructive or lower confidence (${Math.round(alt.score)}%) at current evidence level.`
      : undefined;

  return (
    <div className="space-y-4">
      <h3 className="text-xs font-semibold uppercase tracking-widest text-slate-400">
        Recommended Action
      </h3>
      <p className="text-base font-semibold text-slate-100">{action}</p>
      {detail && <p className="text-sm text-slate-400">{detail}</p>}
      <div className="space-y-2 text-sm">
        <p>
          <span className="text-slate-500">Expected recovery:</span>{" "}
          <span className="text-emerald-400 font-medium">{fmtSavings(savings)}</span>
        </p>
        {actionConf != null && (
          <p>
            <span className="text-slate-500">Action confidence:</span>{" "}
            <span className="text-slate-200 font-medium">{Math.round(actionConf)}%</span>
          </p>
        )}
        <p className="text-slate-400 text-xs leading-relaxed">
          Stopping or scaling is preferred when reversible and evidence supports idle or waste.
        </p>
        {alt && (
          <p className="text-xs text-slate-500">
            Alternative considered: {alt.label} — {Math.round(alt.score)}% action confidence.
            {whyNot && <> Why not: {whyNot}</>}
          </p>
        )}
      </div>
      <div className="pt-2 border-t border-slate-700/40">
        <span className="text-[10px] uppercase tracking-widest text-slate-500">Rollback</span>
        <p className="text-sm text-slate-400 mt-1">{rollback}</p>
      </div>
      <SafetyChecklist checks={assessment?.safety_checks ?? []} />
    </div>
  );
}
