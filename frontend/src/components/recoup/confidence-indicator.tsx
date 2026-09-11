import { cn } from "@/lib/utils";

interface ConfidenceIndicatorProps {
  value: number | null | undefined;
  className?: string;
}

export function ConfidenceIndicator({ value, className }: ConfidenceIndicatorProps) {
  const normalized = value != null && !isNaN(value) ? (value <= 1 ? value * 100 : value) : null;
  const display = normalized != null ? `${Math.round(normalized)}%` : "—";
  const level =
    normalized != null && normalized >= 80 ? "high" : normalized != null && normalized >= 50 ? "medium" : "low";

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <span className="text-[10px] font-medium uppercase tracking-widest text-slate-500">
        Confidence
      </span>
      <span
        className={cn(
          "text-sm font-semibold",
          level === "high" ? "text-emerald-400" : level === "medium" ? "text-blue-400" : "text-slate-400"
        )}
      >
        {display}
      </span>
    </div>
  );
}
