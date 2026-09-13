"use client";

import { useState } from "react";
import type { RecoveryAssessment } from "@/lib/recovery-types";
import {
  actionConfidenceForPrimary,
  actionConfidenceSupportingFactors,
  actionConfidenceUncertaintyFactors,
  discoveryConfidenceSupportingFactors,
  discoveryConfidenceUncertaintyFactors,
} from "@/lib/recovery-presentation";
import { cn } from "@/lib/utils";

function FactorSection({
  title,
  supporting,
  uncertainty,
}: {
  title: string;
  supporting: string[];
  uncertainty: string[];
}) {
  return (
    <div className="space-y-3 py-3 border-b border-slate-700/40 last:border-0">
      <p className="text-sm font-medium text-slate-200">{title}</p>
      <div>
        <p className="text-[10px] uppercase tracking-widest text-slate-500 mb-1.5">
          Supporting factors
        </p>
        {supporting.length === 0 ? (
          <p className="text-xs text-slate-500">No structured supporting factors reported.</p>
        ) : (
          <ul className="space-y-1 text-sm text-slate-300">
            {supporting.map((line) => (
              <li key={line} className="flex gap-2">
                <span className="text-emerald-500">✓</span>
                {line}
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        <p className="text-[10px] uppercase tracking-widest text-slate-500 mb-1.5">
          Remaining uncertainty
        </p>
        {uncertainty.length === 0 ? (
          <p className="text-xs text-slate-500">No structured uncertainty factors reported.</p>
        ) : (
          <ul className="space-y-1 text-sm text-slate-400">
            {uncertainty.map((line) => (
              <li key={line} className="flex gap-2">
                <span className="text-amber-500">?</span>
                {line}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export function ConfidenceDetails({
  assessment,
  discoveryConf,
  actionConf,
}: {
  assessment: RecoveryAssessment | null;
  discoveryConf: number | null;
  actionConf: number | null;
}) {
  const [open, setOpen] = useState(false);
  const ac = actionConf ?? actionConfidenceForPrimary(assessment);
  if (discoveryConf == null && ac == null) return null;

  return (
    <div className="rounded-lg border border-slate-700/40 bg-slate-800/20">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-slate-300 hover:bg-slate-800/40"
      >
        Confidence details
        <span className={cn("text-slate-500", open && "rotate-180")}>▼</span>
      </button>
      {open && (
        <div className="px-4 pb-4 border-t border-slate-700/40">
          {discoveryConf != null && (
            <FactorSection
              title={`Why ${Math.round(discoveryConf)}% discovery confidence?`}
              supporting={discoveryConfidenceSupportingFactors(assessment)}
              uncertainty={discoveryConfidenceUncertaintyFactors(assessment)}
            />
          )}
          {ac != null && (
            <FactorSection
              title={`Why ${Math.round(ac)}% action confidence?`}
              supporting={actionConfidenceSupportingFactors(assessment)}
              uncertainty={actionConfidenceUncertaintyFactors(assessment)}
            />
          )}
        </div>
      )}
    </div>
  );
}
