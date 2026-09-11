import { cn } from "@/lib/utils";

interface EvidenceListProps {
  items: string[];
  className?: string;
  compact?: boolean;
}

export function EvidenceList({ items, className, compact = false }: EvidenceListProps) {
  if (items.length === 0) {
    return <p className="text-xs text-slate-500">No evidence collected yet</p>;
  }

  return (
    <ul className={cn("space-y-1.5", className)}>
      {items.map((item, i) => (
        <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
          <span className="text-emerald-500 shrink-0 mt-0.5">✓</span>
          <span className={compact ? "text-xs" : undefined}>{item}</span>
        </li>
      ))}
    </ul>
  );
}
