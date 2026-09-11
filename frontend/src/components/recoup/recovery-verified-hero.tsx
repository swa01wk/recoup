import Link from "next/link";
import { Button } from "@/components/ui/button";
import { fmtDollarAmount, fmtVerifiedTimestamp } from "@/lib/recoup-ui-rules";
import { truncateResourceId } from "@/components/recoup/service-icons";

interface RecoveryVerifiedHeroProps {
  amountMonthly: number;
  service: string;
  resourceId?: string | null;
  region?: string;
  executedAction?: string | null;
  verifiedAt?: string | null;
}

export function RecoveryVerifiedHero({
  amountMonthly,
  service,
  resourceId,
  region,
  executedAction,
  verifiedAt,
}: RecoveryVerifiedHeroProps) {
  const yearly = amountMonthly * 12;
  const contextParts = [
    service,
    resourceId ? truncateResourceId(resourceId, 28) : null,
    region || null,
  ].filter(Boolean);

  return (
    <div className="rounded-xl border border-emerald-700/50 bg-gradient-to-br from-emerald-950/30 to-slate-900/40 p-6 space-y-4">
      <div className="flex items-start gap-3">
        <div className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-emerald-900/40 border border-emerald-600/40 shrink-0">
          <span className="text-lg text-emerald-400">✓</span>
        </div>
        <div className="min-w-0 flex-1 space-y-3">
          <h2 className="text-lg font-bold text-emerald-300">Recovery Verified</h2>

          <div>
            <p className="text-2xl font-mono font-bold text-emerald-400 tabular-nums">
              {fmtDollarAmount(amountMonthly)}/mo recovered
            </p>
            <p className="text-sm font-mono text-slate-400 tabular-nums mt-0.5">
              {fmtDollarAmount(yearly)}/year
            </p>
          </div>

          {contextParts.length > 0 && (
            <p className="text-xs text-slate-500 truncate" title={contextParts.join(" · ")}>
              {contextParts.map((part, i) => (
                <span key={i}>
                  {i > 0 && <span className="text-slate-600 mx-1.5">·</span>}
                  <span className={i === 1 && resourceId ? "font-mono" : undefined}>{part}</span>
                </span>
              ))}
            </p>
          )}

          {executedAction && (
            <div>
              <p className="text-[10px] uppercase tracking-widest text-slate-500">Action completed</p>
              <p className="text-sm text-slate-200 mt-0.5">{executedAction}</p>
            </div>
          )}

          <ul className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs text-slate-300">
            <li className="flex items-center gap-2 rounded-lg border border-emerald-800/30 bg-emerald-950/20 px-3 py-2">
              <span className="text-emerald-500">✓</span> AWS action executed
            </li>
            <li className="flex items-center gap-2 rounded-lg border border-emerald-800/30 bg-emerald-950/20 px-3 py-2">
              <span className="text-emerald-500">✓</span> Resource state verified
            </li>
            <li className="flex items-center gap-2 rounded-lg border border-emerald-800/30 bg-emerald-950/20 px-3 py-2">
              <span className="text-emerald-500">✓</span> Savings recorded in Recovery Ledger
            </li>
          </ul>

          {verifiedAt && (
            <p className="text-xs text-slate-500">
              Verified {fmtVerifiedTimestamp(verifiedAt)}
            </p>
          )}

          <Link href="/recovery">
            <Button variant="secondary" size="sm">
              View Recovery Ledger
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
