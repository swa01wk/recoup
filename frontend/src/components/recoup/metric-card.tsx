import { cn } from "@/lib/utils";

interface MetricCardProps {
  label: string;
  value: string;
  sub?: string;
  accent?: "green" | "blue" | "amber" | "purple" | "slate" | "red";
  className?: string;
  dominant?: boolean;
}

const accentStyles: Record<NonNullable<MetricCardProps["accent"]>, string> = {
  green: "text-emerald-400",
  blue: "text-blue-400",
  amber: "text-amber-400",
  purple: "text-violet-400",
  slate: "text-slate-200",
  red: "text-red-400",
};

export function MetricCard({
  label,
  value,
  sub,
  accent = "slate",
  className,
  dominant = false,
}: MetricCardProps) {
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <span className="text-[10px] font-medium uppercase tracking-widest text-slate-500">
        {label}
      </span>
      <span
        className={cn(
          "font-mono font-bold tabular-nums",
          dominant ? "text-2xl" : "text-xl",
          accentStyles[accent]
        )}
      >
        {value}
      </span>
      {sub && <span className="text-xs text-slate-500">{sub}</span>}
    </div>
  );
}
