"use client";

import { useState } from "react";
import type { RecoveryAssessment } from "@/lib/recovery-types";
import { policyGovernanceLines } from "@/lib/recovery-presentation";
import { cn } from "@/lib/utils";

export function PolicyGovernance({ assessment }: { assessment: RecoveryAssessment | null }) {
  const [open, setOpen] = useState(false);
  const lines = policyGovernanceLines(assessment);

  return (
    <div className="rounded-lg border border-slate-700/40 bg-slate-800/20">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-slate-300 hover:bg-slate-800/40"
      >
        Policy &amp; Governance
        <span className={cn("text-slate-500", open && "rotate-180")}>▼</span>
      </button>
      {open && (
        <div className="px-4 pb-4 border-t border-slate-700/40 space-y-2 text-sm text-slate-400">
          {lines.map((line) => (
            <p key={line}>{line}</p>
          ))}
        </div>
      )}
    </div>
  );
}
