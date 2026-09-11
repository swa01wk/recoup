import { cn } from "@/lib/utils";
import { formatRiskTier } from "@/lib/recoup-ui-rules";

interface RiskIndicatorProps {
  tier: string;
  className?: string;
}

const tierStyles: Record<string, string> = {
  Low: "text-emerald-400 bg-emerald-950/30 border-emerald-700/40",
  Medium: "text-amber-400 bg-amber-950/30 border-amber-700/40",
  High: "text-red-400 bg-red-950/30 border-red-700/40",
};

export function RiskIndicator({ tier, className }: RiskIndicatorProps) {
  const label = formatRiskTier(tier);
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium",
        tierStyles[label] ?? "text-slate-400 bg-slate-800/30 border-slate-700/40",
        className
      )}
    >
      {label}
    </span>
  );
}
