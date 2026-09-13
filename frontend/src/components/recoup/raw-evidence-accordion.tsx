"use client";

import { useState, useImperativeHandle, forwardRef } from "react";
import type { Finding, Opportunity, TraceResult } from "@/lib/api";
import type { OperationalSignal } from "@/lib/recovery-types";
import { cn } from "@/lib/utils";

export interface RawEvidenceAccordionHandle {
  open: () => void;
}

interface RawEvidenceAccordionProps {
  opportunityId: string;
  opportunity: Opportunity | null;
  finding: Finding | null;
  trace: TraceResult | null;
  signals: OperationalSignal[];
  onRerunInvestigation?: () => void;
  showRerun?: boolean;
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex gap-2 py-0.5">
      <span className="text-slate-500 shrink-0">{k}</span>
      <span className="text-slate-300 break-all">{v}</span>
    </div>
  );
}

export const RawEvidenceAccordion = forwardRef<RawEvidenceAccordionHandle, RawEvidenceAccordionProps>(
  function RawEvidenceAccordion(
    {
      opportunityId,
      opportunity,
      finding,
      trace,
      signals,
      onRerunInvestigation,
      showRerun,
    },
    ref
  ) {
    const [open, setOpen] = useState(false);
    useImperativeHandle(ref, () => ({ open: () => setOpen(true) }));

    const entries: { k: string; v: string }[] = [];
    entries.push({ k: "opportunity_id", v: opportunityId });
    if (opportunity?.state) entries.push({ k: "state", v: opportunity.state });
    if (opportunity?.potential_value)
      entries.push({ k: "potential_value", v: opportunity.potential_value });
    if (finding?.resource_id) entries.push({ k: "resource_id", v: finding.resource_id });
    if (finding?.finding_type) entries.push({ k: "finding_type", v: finding.finding_type });
    if (finding?.estimated_monthly_savings_usd != null) {
      entries.push({
        k: "estimated_monthly_savings_usd",
        v: String(finding.estimated_monthly_savings_usd),
      });
    }
    if (finding?.severity) entries.push({ k: "severity", v: finding.severity });
    if (finding?.region) entries.push({ k: "region", v: finding.region });
    if (finding?.scenario_tag) entries.push({ k: "scenario_tag", v: finding.scenario_tag });
    if (finding?.is_demo_resource != null) {
      entries.push({ k: "is_demo_resource", v: String(finding.is_demo_resource) });
    }
    if (finding?.evidence) {
      for (const [key, val] of Object.entries(finding.evidence)) {
        entries.push({ k: key, v: typeof val === "string" ? val : JSON.stringify(val) });
      }
    }
    if (trace?.signal) {
      for (const [key, val] of Object.entries(trace.signal)) {
        if (val != null && val !== "") {
          entries.push({ k: `signal.${key}`, v: String(val) });
        }
      }
    }
    for (const sig of signals.slice(0, 12)) {
      if (sig.raw_reference) {
        entries.push({ k: `signal.${sig.signal_id}.ref`, v: sig.raw_reference });
      }
    }

    return (
      <div
        id="raw-evidence"
        className="rounded-lg border border-slate-700/40 bg-slate-800/20 scroll-mt-24"
      >
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-slate-300 hover:bg-slate-800/40"
        >
          Raw Evidence
          <span className={cn("text-slate-500", open && "rotate-180")}>▼</span>
        </button>
        {open && (
          <div className="px-4 pb-4 border-t border-slate-700/40 font-mono text-xs space-y-0.5">
            {entries.map(({ k, v }) => (
              <Row key={`${k}-${v}`} k={k} v={v} />
            ))}
            {showRerun && onRerunInvestigation && (
              <button
                type="button"
                onClick={onRerunInvestigation}
                className="text-blue-400 hover:text-blue-300 mt-3 font-sans text-xs"
              >
                Re-run agent investigation →
              </button>
            )}
          </div>
        )}
      </div>
    );
  }
);
