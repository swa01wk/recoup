import { cn } from "@/lib/utils";

// Color semantics (fixed — never reuse a color for a different meaning):
//   success  (emerald) → RECOVERED, verified savings
//   approved (purple)  → APPROVED, authorized, in-remediation
//   pending  (amber)   → PENDING, awaiting action
//   active   (blue)    → in-progress pipeline stages
//   warning  (amber)   → SUBMITTING, risk-yellow
//   error    (red)     → REJECTED, FAILED, DECLINED, risk-red, destructive
//   default  (slate)   → DETECTED, neutral, informational
type Variant =
  | "default"
  | "mocked"
  | "live"
  | "success"
  | "approved"
  | "active"
  | "warning"
  | "error"
  | "pending"
  | "outline";

interface BadgeProps {
  children: React.ReactNode;
  variant?: Variant;
  className?: string;
}

const variantStyles: Record<Variant, string> = {
  default:  "bg-slate-700 text-slate-200 border-slate-600",
  mocked:   "bg-slate-700/60 text-slate-400 border-slate-600 font-semibold tracking-wide",
  live:     "bg-red-900/60 text-red-300 border-red-700 font-semibold tracking-wide animate-pulse",
  success:  "bg-emerald-900/60 text-emerald-300 border-emerald-700",   // RECOVERED
  approved: "bg-violet-900/60 text-violet-300 border-violet-700",      // APPROVED
  active:   "bg-blue-900/60 text-blue-300 border-blue-700",            // in-progress
  warning:  "bg-amber-900/60 text-amber-300 border-amber-700",         // risk-yellow
  error:    "bg-red-900/60 text-red-300 border-red-700",               // REJECTED/FAILED
  pending:  "bg-amber-900/40 text-amber-300 border-amber-700/60",      // PENDING
  outline:  "bg-transparent text-slate-300 border-slate-600",
};

export function Badge({ children, variant = "default", className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs uppercase",
        variantStyles[variant],
        className
      )}
    >
      {children}
    </span>
  );
}

export function MockedBadge() {
  return <Badge variant="mocked">⬡ Demo Data</Badge>;
}

export function LiveBadge() {
  return <Badge variant="live">⬡ Live AWS Action</Badge>;
}

export function STSConnectedBadge({
  accountId,
  roleArn,
}: {
  accountId?: string | null;
  roleArn?: string | null;
}) {
  const label = accountId
    ? `STS AssumeRole ✓ · Account ${accountId}`
    : "STS AssumeRole ✓";
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full bg-emerald-900/40 border border-emerald-500/30 px-3 py-1 text-xs font-medium text-emerald-300"
      title={roleArn ?? undefined}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
      {label}
    </span>
  );
}

/**
 * Phase 6f — Scenario tag badge for demo workload findings.
 * Displays the RecoupScenario tag value (e.g. "oversized-ec2").
 */
export function ScenarioBadge({ scenario }: { scenario: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-md bg-violet-900/40 border border-violet-500/30 px-2 py-0.5 text-[10px] font-medium text-violet-300 uppercase tracking-wide">
      🏷 {scenario}
    </span>
  );
}

/**
 * Phase 6f — "DEMO" badge for resources that have RecoupDemo=true.
 */
export function DemoBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-md bg-amber-900/40 border border-amber-500/30 px-2 py-0.5 text-[10px] font-semibold text-amber-300 uppercase tracking-wide">
      ⬟ Demo
    </span>
  );
}

export function OperatorBadge() {
  return (
    <Badge variant="success" className="normal-case">
      Operator
    </Badge>
  );
}
