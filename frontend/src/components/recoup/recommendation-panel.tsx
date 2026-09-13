"use client";

import { useState } from "react";
import { fmtSavings } from "@/lib/recoup-ui-rules";
import type { RecoveryAssessment } from "@/lib/recovery-types";
import { actionConfidenceAlternatives, actionConfidenceForPrimary } from "@/lib/recovery-presentation";

interface RecommendationPanelProps {
  action: string;
  detail?: string;
  assessment: RecoveryAssessment | null;
  savings: number;
}

export function RecommendationPanel({
  action,
  detail,
  assessment,
  savings,
}: RecommendationPanelProps) {
  const [reasonOpen, setReasonOpen] = useState(false);
  const actionConf = actionConfidenceForPrimary(assessment);
  const alts = actionConfidenceAlternatives(assessment, 2);
  const alt = alts.find((a) => a.label !== action && !action.includes(a.label));

  return (
    <div className="space-y-4">
      <h3 className="text-xs font-semibold uppercase tracking-widest text-slate-400">
        Recommended Action
      </h3>
      <p className="text-base font-semibold text-slate-100">{action}</p>
      {detail && (
        <p className="text-sm text-slate-400 leading-relaxed line-clamp-3">{detail}</p>
      )}
      <div className="space-y-2 text-sm">
        <p>
          <span className="text-slate-500">Expected recovery</span>
          <br />
          <span className="text-emerald-400 font-medium">{fmtSavings(savings)}</span>
        </p>
        {actionConf != null && (
          <p>
            <span className="text-slate-500">Action confidence</span>
            <br />
            <span className="text-slate-200 font-medium">{Math.round(actionConf)}%</span>
          </p>
        )}
        {alt && (
          <p className="text-xs text-slate-500">
            Alternative considered: {alt.label}
            {alt.score != null ? ` (${Math.round(alt.score)}%)` : ""}
          </p>
        )}
      </div>
      {detail && detail.length > 120 && (
        <>
          <button
            type="button"
            onClick={() => setReasonOpen((v) => !v)}
            className="text-xs text-blue-400 hover:text-blue-300"
          >
            {reasonOpen ? "Hide reasoning ↑" : "View reasoning →"}
          </button>
          {reasonOpen && (
            <p className="text-sm text-slate-400 leading-relaxed border-t border-slate-700/40 pt-2">
              {detail}
            </p>
          )}
        </>
      )}
    </div>
  );
}
