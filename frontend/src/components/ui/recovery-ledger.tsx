"use client";

import Link from "next/link";
import { fmt } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { toCanonicalLifecycle } from "@/lib/recovery-storage";

export interface RecoveryLedgerData {
  detected: number;      // remaining actionable (scanTotal − recovered − pending)
  totalDetected: number; // original scan total
  recovered: number;
  pending: number;
}

interface RecoveryLedgerProps {
  data: RecoveryLedgerData;
  compact?: boolean;
  /** "summary" shows "Recovery Summary" (Opportunities page); "ledger" shows full title */
  variant?: "summary" | "ledger";
  className?: string;
}

function Stage({
  label,
  value,
  colorClass,
  borderClass,
  subtitle,
  title,
}: {
  label: string;
  value: number;
  colorClass: string;
  borderClass: string;
  subtitle?: string;
  /** Native tooltip on hover — no floating overlay */
  title?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col justify-center rounded-lg border px-4 py-3 min-w-0 flex-1 min-h-[88px]",
        borderClass
      )}
      title={title}
    >
      <span className="text-[10px] uppercase tracking-widest text-slate-500 leading-tight">
        {label}
      </span>
      <span className={cn("text-xl font-bold font-mono mt-1 tabular-nums leading-none", colorClass)}>
        {fmt(value)}
        <span className="text-xs font-normal text-slate-500">/mo</span>
      </span>
      {subtitle && (
        <span className="text-[10px] text-slate-500 mt-1.5 leading-tight">{subtitle}</span>
      )}
    </div>
  );
}

function Arrow() {
  return (
    <span className="hidden lg:flex items-center justify-center text-slate-600 text-base shrink-0 self-center">
      →
    </span>
  );
}

export function RecoveryLedger({
  data,
  compact = false,
  variant = "ledger",
  className,
}: RecoveryLedgerProps) {
  const title = variant === "summary" ? "Recovery Summary" : "Recovery Ledger";

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wide">
            {title}
          </h2>
          {!compact && (
            <p className="text-xs text-slate-500 mt-0.5">
              Closed-loop spend recovery — from detection to verified savings
            </p>
          )}
        </div>
        {variant === "summary" && (
          <Link
            href="/recovery"
            className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
          >
            View ledger →
          </Link>
        )}
        {!compact && variant === "ledger" && (
          <Link
            href="/recovery"
            className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
          >
            View full ledger →
          </Link>
        )}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr] lg:items-stretch gap-2">
        <Stage
          label="Potential Savings"
          value={data.totalDetected}
          colorClass="text-slate-300"
          borderClass="border-slate-600/40 bg-slate-800/30"
          subtitle="Original recoverable value identified in the scan"
          title="Total recoverable amount from the latest scan"
        />
        <Arrow />
        <Stage
          label="Remaining"
          value={data.detected}
          colorClass="text-blue-300"
          borderClass="border-blue-700/40 bg-blue-950/30"
          subtitle="Not yet actioned"
          title="Not recovered and not awaiting approval"
        />
        <Arrow />
        <Stage
          label="Pending Approval"
          value={data.pending}
          colorClass="text-amber-300"
          borderClass="border-amber-700/40 bg-amber-950/30"
          subtitle="Awaiting human action"
          title="Amount waiting for operator approval"
        />
        <Arrow />
        <Stage
          label="Recovered"
          value={data.recovered}
          colorClass="text-emerald-300"
          borderClass="border-emerald-700/40 bg-emerald-950/30"
          subtitle="Verified savings"
          title="Savings verified after remediation"
        />
      </div>
    </div>
  );
}

// ── Service-level ledger ───────────────────────────────────────────────────
// Shows where a single opportunity sits in the 3-bucket lifecycle.

export type ServiceLifecycleBucket = "DETECTED" | "PENDING" | "RECOVERED";

const SERVICE_STAGES: Array<{
  bucket: ServiceLifecycleBucket;
  label: string;
  colorClass: string;
  activeBorder: string;
  activeBg: string;
  doneBorder: string;
  doneBg: string;
}> = [
  {
    bucket: "DETECTED",
    label: "Remaining",
    colorClass: "text-blue-300",
    activeBorder: "border-blue-500/60",
    activeBg: "bg-blue-900/30",
    doneBorder: "border-slate-600/40",
    doneBg: "bg-slate-800/20",
  },
  {
    bucket: "PENDING",
    label: "Pending Approval",
    colorClass: "text-amber-300",
    activeBorder: "border-amber-500/60",
    activeBg: "bg-amber-900/20",
    doneBorder: "border-slate-600/40",
    doneBg: "bg-slate-800/20",
  },
  {
    bucket: "RECOVERED",
    label: "Recovered",
    colorClass: "text-emerald-300",
    activeBorder: "border-emerald-500/60",
    activeBg: "bg-emerald-900/20",
    doneBorder: "border-slate-600/40",
    doneBg: "bg-slate-800/20",
  },
];

const BUCKET_ORDER: ServiceLifecycleBucket[] = ["DETECTED", "PENDING", "RECOVERED"];

interface ServiceLedgerProps {
  /** Current lifecycle bucket this opportunity is in */
  bucket: ServiceLifecycleBucket;
  /** Dollar value of this opportunity */
  value: number;
  className?: string;
}

export function ServiceLedger({ bucket, value, className }: ServiceLedgerProps) {
  const activeBucketIdx = BUCKET_ORDER.indexOf(bucket);

  return (
    <div className={cn("space-y-2", className)}>
      <p className="text-[10px] text-slate-500 uppercase tracking-widest font-medium">
        Service Lifecycle
      </p>
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
        {SERVICE_STAGES.map((stage, i) => {
          const isActive = i === activeBucketIdx;
          const isDone = i < activeBucketIdx;

          return (
            <div key={stage.bucket} className="flex items-center gap-2 flex-1">
              <div
                className={cn(
                  "flex-1 rounded-lg border px-3 py-2.5 transition-all",
                  isActive
                    ? cn(stage.activeBorder, stage.activeBg)
                    : isDone
                    ? "border-slate-700/30 bg-slate-800/10 opacity-40"
                    : "border-slate-700/30 bg-slate-800/10 opacity-30"
                )}
              >
                <div className="flex items-center gap-1.5 mb-1">
                  {isDone ? (
                    <span className="text-[10px] text-emerald-500">✓</span>
                  ) : isActive ? (
                    <span className={cn("text-[10px]", stage.colorClass)}>●</span>
                  ) : (
                    <span className="text-[10px] text-slate-600">○</span>
                  )}
                  <span
                    className={cn(
                      "text-[10px] uppercase tracking-widest font-medium",
                      isActive ? stage.colorClass : isDone ? "text-slate-500" : "text-slate-600"
                    )}
                  >
                    {stage.label}
                  </span>
                </div>
                <p
                  className={cn(
                    "font-mono font-bold text-sm",
                    isActive ? stage.colorClass : "text-slate-600"
                  )}
                >
                  {isActive ? fmt(value) : isDone ? fmt(value) : "—"}
                  {(isActive || isDone) && (
                    <span className="text-[10px] font-normal text-slate-500">/mo</span>
                  )}
                </p>
              </div>
              {i < SERVICE_STAGES.length - 1 && (
                <span className="hidden sm:block text-slate-600 text-sm shrink-0">→</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Compute ledger bucket values from server-side state.
 *
 * The three buckets form a pipeline accounting equation:
 *   detected (remaining) + pending + recovered = total scan value
 *
 * Buckets:
 * - detected  = remaining recoverable opportunity (scanTotal − recovered − pending)
 * - Pending   = sum of AWAITING_APPROVAL opportunities
 * - Recovered = sum of RECOVERED / APPROVED opportunities
 *
 * NOTE: The ledger counts ALL opportunities returned by the API (including
 * SLA-replay ones), not just cost-recovery ("recovery-" prefix) items.
 * We round all bucket sums to 2 decimal places to prevent IEEE-754 drift.
 */
export function computeLedgerData(
  scanTotal: number,
  opportunities: Array<{ state: string; potential_value: string | null }>,
  pendingApprovalAmount: number
): RecoveryLedgerData {
  let recovered = 0;
  let pendingFromOpps = 0;

  for (const opp of opportunities) {
    const raw = parseFloat(opp.potential_value ?? "0");
    if (isNaN(raw) || raw <= 0) continue;
    const value = Math.round((raw + Number.EPSILON) * 100) / 100;

    // toCanonicalLifecycle now maps APPROVED → RECOVERED, so 3 buckets only
    const canonical = toCanonicalLifecycle(opp.state);

    if (canonical === "RECOVERED") {
      recovered += value;
    } else if (canonical === "PENDING") {
      pendingFromOpps += value;
    }
  }

  recovered = Math.round((recovered + Number.EPSILON) * 100) / 100;
  pendingFromOpps = Math.round((pendingFromOpps + Number.EPSILON) * 100) / 100;

  const pending = pendingFromOpps > 0 ? pendingFromOpps : pendingApprovalAmount;
  const total = Math.max(
    Math.round((scanTotal + Number.EPSILON) * 100) / 100,
    Math.round((recovered + pending + Number.EPSILON) * 100) / 100
  );

  // "detected" = remaining actionable opportunity (shrinks as items are recovered)
  const detected = Math.max(0, Math.round((total - recovered - pending + Number.EPSILON) * 100) / 100);

  return { detected, totalDetected: total, recovered, pending };
}
