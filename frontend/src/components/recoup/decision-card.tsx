"use client";

import { fmtSavings, formatRiskTier } from "@/lib/recoup-ui-rules";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

interface DecisionCardProps {
  action: string;
  why: string;
  impactMonthly: number;
  riskTier: string;
  rollback: string;
  policyNote?: string;
  loading?: boolean;
  onApprove: () => void;
  approveLabel?: string;
  onDecline: () => void;
  onInvestigate: () => void;
  message?: string | null;
}

export function DecisionCard({
  action,
  why,
  impactMonthly,
  riskTier,
  rollback,
  policyNote = "Human approval required for cost recovery actions.",
  loading = false,
  onApprove,
  onDecline,
  onInvestigate,
  message,
  approveLabel,
}: DecisionCardProps) {
  const cta =
    approveLabel ?? `Approve ${fmtSavings(impactMonthly)} Recovery`;

  return (
    <Card className="border-amber-700/40 bg-slate-900/40" data-testid="approval-required-card">
      <CardContent className="py-6 space-y-5">
        <h2 className="text-lg font-bold text-amber-200">Approval Required</h2>
        <p className="text-sm text-slate-400">
          Recoup is ready to execute the proposed recovery plan.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div className="space-y-1">
            <span className="text-[10px] font-medium uppercase tracking-widest text-slate-500">
              Action
            </span>
            <p className="font-semibold text-slate-100">{action}</p>
          </div>
          <div className="space-y-1">
            <span className="text-[10px] font-medium uppercase tracking-widest text-slate-500">
              Why
            </span>
            <p className="text-slate-300">{why}</p>
          </div>
          <div className="space-y-1">
            <span className="text-[10px] font-medium uppercase tracking-widest text-slate-500">
              Impact
            </span>
            <p className="text-emerald-400 font-medium">{fmtSavings(impactMonthly)}</p>
          </div>
          <div className="space-y-1">
            <span className="text-[10px] font-medium uppercase tracking-widest text-slate-500">
              Risk
            </span>
            <p className="text-slate-200">{formatRiskTier(riskTier)}</p>
          </div>
          <div className="space-y-1 sm:col-span-2">
            <span className="text-[10px] font-medium uppercase tracking-widest text-slate-500">
              Rollback
            </span>
            <p className="text-slate-400">{rollback}</p>
          </div>
        </div>

        <p className="text-xs text-slate-500 border-t border-slate-700/40 pt-3">
          Policy: {policyNote}
        </p>

        <div className="flex items-center gap-3 flex-wrap pt-1 justify-end">
          <Button variant="secondary" size="sm" loading={loading} onClick={onInvestigate}>
            Investigate Further
          </Button>
          <Button
            variant="ghost"
            size="sm"
            loading={loading}
            onClick={onDecline}
            className="text-red-400 hover:text-red-300 border border-red-900/40"
          >
            Decline
          </Button>
          <Button variant="success" size="md" loading={loading} onClick={onApprove}>
            {cta}
          </Button>
        </div>

        {message && (
          <p
            className={`text-xs ${
              message.startsWith("Error:")
                ? "text-red-400"
                : message.startsWith("Approved")
                  ? "text-emerald-400"
                  : "text-blue-300"
            }`}
          >
            {message}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
