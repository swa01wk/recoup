import { cn } from "@/lib/utils";

interface CardProps {
  children: React.ReactNode;
  className?: string;
}

export function Card({ children, className }: CardProps) {
  return (
    <div
      className={cn(
        "rounded-xl border border-slate-700/60 bg-slate-800/50 backdrop-blur-sm",
        className
      )}
    >
      {children}
    </div>
  );
}

export function CardHeader({ children, className }: CardProps) {
  return (
    <div
      className={cn(
        "flex items-center justify-between border-b border-slate-700/60 px-5 py-4",
        className
      )}
    >
      {children}
    </div>
  );
}

export function CardTitle({ children, className }: CardProps) {
  return (
    <h3 className={cn("text-sm font-semibold text-slate-200 uppercase tracking-wider", className)}>
      {children}
    </h3>
  );
}

export function CardContent({ children, className }: CardProps) {
  return <div className={cn("px-5 py-4", className)}>{children}</div>;
}

interface StatCardProps {
  label: string;
  value: string;
  sub?: string;
  accent?: "green" | "blue" | "orange" | "red" | "slate";
}

const accentStyles: Record<NonNullable<StatCardProps["accent"]>, string> = {
  green: "text-emerald-400",
  blue: "text-blue-400",
  orange: "text-orange-400",
  red: "text-red-400",
  slate: "text-slate-200",
};

export function StatCard({ label, value, sub, accent = "slate" }: StatCardProps) {
  return (
    <Card>
      <CardContent className="py-5">
        <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-1">{label}</p>
        <p className={cn("text-2xl font-bold font-mono", accentStyles[accent])}>{value}</p>
        {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
      </CardContent>
    </Card>
  );
}
