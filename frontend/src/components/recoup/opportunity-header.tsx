"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/recoup/status-badge";
import { serviceIcon } from "@/components/recoup/service-icons";
import { fmtSavings, fmtYearlySavings } from "@/lib/recoup-ui-rules";
import { formatRiskTier } from "@/lib/recoup-ui-rules";

interface OpportunityHeaderProps {
  service: string;
  oppState: string;
  savings: number;
  findingHeadline: string;
  narrative: string;
  resourceId: string | null;
  region: string;
  findingLabel: string;
  policyLabel: string;
  riskTier: string;
  showInvestigate: boolean;
  streaming: boolean;
  investigateLabel: string;
  onInvestigate: () => void;
}

export function OpportunityHeader({
  service,
  oppState,
  savings,
  findingHeadline,
  narrative,
  resourceId,
  region,
  findingLabel,
  policyLabel,
  riskTier,
  showInvestigate,
  streaming,
  investigateLabel,
  onInvestigate,
}: OpportunityHeaderProps) {
  const riskLabel = formatRiskTier(riskTier);
  const showLowRiskBadge = riskLabel === "Low";

  return (
    <header className="space-y-3">
      <Link href="/opportunities" className="text-slate-500 hover:text-slate-300 text-sm inline-block">
        ← Opportunities
      </Link>
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="space-y-2 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-2xl">{serviceIcon(service)}</span>
            <h1 className="text-2xl font-bold text-slate-100">{service} Opportunity</h1>
            <StatusBadge state={oppState} />
            {showLowRiskBadge && (
              <span className="text-[10px] uppercase tracking-wide text-emerald-400/90 border border-emerald-800/50 rounded px-2 py-0.5">
                Low Risk
              </span>
            )}
          </div>
          {savings > 0 && (
            <div>
              <p className="text-2xl font-mono font-bold text-emerald-400 tabular-nums">
                {fmtSavings(savings)} recoverable
              </p>
              <p className="text-sm text-slate-500 mt-0.5">
                {fmtYearlySavings(savings)} projected recovery
              </p>
            </div>
          )}
        </div>
        {showInvestigate && (
          <Button variant="secondary" size="sm" loading={streaming} onClick={onInvestigate}>
            {streaming ? "Investigating…" : investigateLabel}
          </Button>
        )}
      </div>
      <div>
        <p className="text-base font-medium text-slate-200">{findingHeadline}</p>
        <p className="text-sm text-slate-400 mt-0.5 leading-relaxed">{narrative}</p>
      </div>
      <p className="text-xs text-slate-500 flex flex-wrap gap-x-4 gap-y-1">
        {resourceId && <span>Resource: {resourceId}</span>}
        {region && <span>Region: {region}</span>}
        <span>Finding: {findingLabel}</span>
        <span>Policy: {policyLabel}</span>
      </p>
    </header>
  );
}
