"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/recoup/status-badge";
import { RiskIndicator } from "@/components/recoup/risk-indicator";
import { serviceIcon, truncateResourceId } from "@/components/recoup/service-icons";
import {
  OPPORTUNITY_TABLE_HEADER_CELL,
  OPPORTUNITY_TABLE_GRID,
  OPPORTUNITY_TABLE_ROW,
} from "@/components/recoup/opportunity-table-layout";
import { fmtSavings, severityToRisk } from "@/lib/recoup-ui-rules";
import { serviceFindingSummary } from "@/lib/service-presentation";
import { cn } from "@/lib/utils";

export interface OpportunityRowData {
  resourceId: string;
  service: string;
  region?: string;
  issue: string;
  savings: number;
  severity: string;
  state: string;
  opportunityId?: string;
}

interface OpportunityRowProps {
  data: OpportunityRowData;
  onStartRecovery?: () => void;
  loading?: boolean;
}

function primaryAction(data: OpportunityRowData): {
  label: string;
  variant: "primary" | "secondary";
  href?: string;
} {
  const s = data.state.toUpperCase();

  if (!data.opportunityId) {
    return { label: "Start Recovery", variant: "primary" };
  }
  if (["AWAITING_APPROVAL", "NEEDS_FOLLOWUP"].includes(s)) {
    return { label: "Review", variant: "primary", href: `/opportunities/${data.opportunityId}` };
  }
  if (["APPROVED", "SUBMITTING", "SUBMITTED", "MONITORING"].includes(s)) {
    return { label: "View Progress", variant: "secondary", href: `/opportunities/${data.opportunityId}` };
  }
  if (s === "RECOVERED") {
    return { label: "View", variant: "secondary", href: `/opportunities/${data.opportunityId}` };
  }
  return { label: "View", variant: "secondary", href: `/opportunities/${data.opportunityId}` };
}

export function OpportunityTableHeader() {
  return (
    <div className={cn(OPPORTUNITY_TABLE_GRID, "py-2.5 border-b border-slate-700/40 bg-slate-800/30")}>
      <span className={OPPORTUNITY_TABLE_HEADER_CELL}>Service</span>
      <span className={OPPORTUNITY_TABLE_HEADER_CELL}>Resource</span>
      <span className={OPPORTUNITY_TABLE_HEADER_CELL}>Finding</span>
      <span className={cn(OPPORTUNITY_TABLE_HEADER_CELL, "text-right")}>Savings</span>
      <span className={cn(OPPORTUNITY_TABLE_HEADER_CELL, "text-center")}>Risk</span>
      <span className={cn(OPPORTUNITY_TABLE_HEADER_CELL, "text-center")}>Status</span>
      <span className="sr-only">Action</span>
    </div>
  );
}

export function OpportunityRow({ data, onStartRecovery, loading }: OpportunityRowProps) {
  const action = primaryAction(data);
  const summary = serviceFindingSummary(data.issue, data.service);

  return (
    <div className={OPPORTUNITY_TABLE_ROW}>
      {/* Service */}
      <div className="hidden md:flex items-center gap-1.5 min-w-0">
        <span className="text-sm leading-none">{serviceIcon(data.service)}</span>
        <span className="text-xs font-semibold text-slate-200 truncate">{data.service}</span>
      </div>

      {/* Resource */}
      <span
        className="hidden md:block font-mono text-[11px] text-slate-500 truncate self-center"
        title={data.resourceId}
      >
        {truncateResourceId(data.resourceId, 16)}
      </span>

      {/* Finding (+ mobile service/resource stack) */}
      <div className="min-w-0 md:col-span-1 col-span-1">
        <div className="flex items-center gap-2 md:hidden mb-0.5">
          <span className="text-sm">{serviceIcon(data.service)}</span>
          <span className="text-xs font-semibold text-slate-200">{data.service}</span>
        </div>
        <p className="text-sm text-slate-200 truncate leading-snug" title={summary}>
          {summary}
        </p>
        <p className="md:hidden font-mono text-[10px] text-slate-500 truncate mt-0.5">
          {truncateResourceId(data.resourceId, 22)}
        </p>
      </div>

      {/* Savings */}
      <span
        className={cn(
          "hidden md:block font-mono text-sm font-bold tabular-nums whitespace-nowrap text-right self-center",
          data.savings > 0 ? "text-emerald-400" : "text-slate-500"
        )}
      >
        {data.savings > 0 ? fmtSavings(data.savings) : "—"}
      </span>

      {/* Risk */}
      <div className="hidden md:flex justify-center self-center">
        <RiskIndicator tier={severityToRisk(data.severity)} />
      </div>

      {/* Status */}
      <div className="hidden md:flex justify-center self-center">
        <StatusBadge state={data.state} className="text-[10px] whitespace-nowrap" />
      </div>

      {/* Action */}
      <div className="flex justify-end items-center self-center shrink-0">
        {action.href ? (
          <Link href={action.href}>
            <Button variant={action.variant} size="sm" className="whitespace-nowrap">
              {action.label}
            </Button>
          </Link>
        ) : (
          <Button
            variant={action.variant}
            size="sm"
            loading={loading}
            onClick={onStartRecovery}
            className="whitespace-nowrap"
          >
            {action.label}
          </Button>
        )}
      </div>
    </div>
  );
}
