import { cn } from "@/lib/utils";
import type { EvidenceSource } from "@/lib/service-presentation";

interface EvidenceSourceChipsProps {
  sources: EvidenceSource[];
  className?: string;
}

export function EvidenceSourceChips({ sources, className }: EvidenceSourceChipsProps) {
  if (sources.length === 0) return null;

  return (
    <div className={cn("space-y-1.5", className)}>
      <span className="text-[10px] uppercase tracking-widest text-slate-500">
        Evidence Sources
      </span>
      <div className="flex flex-wrap gap-1.5">
        {sources.map((source) => (
          <span
            key={source}
            className="inline-flex items-center rounded-md border border-slate-700/60 bg-slate-800/40 px-2 py-0.5 text-[11px] text-slate-400"
          >
            {source}
          </span>
        ))}
      </div>
    </div>
  );
}
