"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { MetricCard } from "@/components/recoup/metric-card";
import { RiskIndicator } from "@/components/recoup/risk-indicator";
import { fmtSavings, fmtYearlySavings } from "@/lib/recoup-ui-rules";

interface DecisionCardProps {
  action: string;
  why: string;
  impactMonthly: number;
  riskTier: string;
  rollback: string;
  policyNote?: string;
  loading?: boolean;
  onApprove: () => void;
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
  policyNote = "Cedar requires human approval",
  loading = false,
  onApprove,
  onDecline,
  onInvestigate,
  message,
}: DecisionCardProps) {
  return (
    <Card className="border-amber-700/50 bg-gradient-to-br from-amber-950/20 to-slate-900/40">
      <CardContent className="py-6 space-y-5">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <h2 className="text-lg font-bold text-amber-200">Approval Required</h2>
          <Badge variant="pending">Awaiting Approval</Badge>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="space-y-1">
            <span className="text-[10px] font-medium uppercase tracking-widest text-slate-500">
              Action
            </span>
            <p className="text-sm font-semibold text-slate-100">{action}</p>
          </div>
          <div className="space-y-1">
            <span className="text-[10px] font-medium uppercase tracking-widest text-slate-500">
              Why
            </span>
            <p className="text-sm text-slate-300">{why}</p>
          </div>
          <MetricCard
            label="Impact"
            value={fmtSavings(impactMonthly)}
            sub={fmtYearlySavings(impactMonthly)}
            accent="green"
            dominant
          />
          <div className="space-y-1">
            <span className="text-[10px] font-medium uppercase tracking-widest text-slate-500">
              Risk
            </span>
            <div className="pt-0.5">
              <RiskIndicator tier={riskTier} />
            </div>
          </div>
          <div className="space-y-1 sm:col-span-2">
            <span className="text-[10px] font-medium uppercase tracking-widest text-slate-500">
              Rollback
            </span>
            <p className="text-sm text-slate-400">{rollback}</p>
          </div>
        </div>

        <p className="text-xs text-slate-500 border-t border-slate-700/40 pt-3">
          Policy: {policyNote}
        </p>

        <div className="flex items-center gap-3 flex-wrap pt-1 justify-end">
          <Button variant="secondary" size="sm" loading={loading} onClick={onInvestigate}>
            Investigate Further
          </Button>
          <Button variant="ghost" size="sm" loading={loading} onClick={onDecline} className="text-red-400 hover:text-red-300 border border-red-900/40">
            Decline
          </Button>
          <Button variant="success" size="md" loading={loading} onClick={onApprove}>
            Approve Recovery
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
