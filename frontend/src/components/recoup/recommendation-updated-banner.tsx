"use client";

import type { InvestigationDelta } from "@/lib/recovery-types";

export function RecommendationUpdatedBanner({ delta }: { delta: InvestigationDelta | null }) {
  if (!delta?.recommendation_changed) return null;
  const prev = delta.previous_assessment?.recommended_action;
  const next = delta.new_assessment?.recommended_action;
  return (
    <div className="rounded-lg border border-blue-700/50 bg-blue-950/30 px-4 py-3 text-sm space-y-1">
      <p className="font-semibold text-blue-200">Recommendation updated</p>
      {prev && (
        <p className="text-slate-400">
          Previous: <span className="text-slate-300">{prev}</span>
        </p>
      )}
      {next && (
        <p className="text-slate-400">
          New: <span className="text-emerald-300">{next}</span>
        </p>
      )}
      {delta.reason_for_change && (
        <p className="text-xs text-slate-500">Reason: {delta.reason_for_change}</p>
      )}
    </div>
  );
}
