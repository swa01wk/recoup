import { cn } from "@/lib/utils";
import type { EvidenceSource } from "@/lib/service-presentation";

interface EvidenceSourceChipsProps {
  sources: EvidenceSource[];
  className?: string;
  selectedSource?: string | null;
  onSelectSource?: (source: string | null) => void;
}

export function EvidenceSourceChips({
  sources,
  className,
  selectedSource = null,
  onSelectSource,
}: EvidenceSourceChipsProps) {
  if (sources.length === 0) return null;

  return (
    <div className={cn("space-y-1.5", className)}>
      <span className="text-[10px] uppercase tracking-widest text-slate-500">
        Evidence Sources
      </span>
      <div className="flex flex-wrap gap-1.5">
        {sources.map((source) => {
          const active = selectedSource?.toLowerCase() === source.toLowerCase();
          return (
            <button
              key={source}
              type="button"
              onClick={() =>
                onSelectSource?.(active ? null : source)
              }
              className={cn(
                "inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] transition-colors",
                active
                  ? "border-blue-600/70 bg-blue-900/30 text-blue-200"
                  : "border-slate-700/60 bg-slate-800/40 text-slate-400 hover:border-slate-600"
              )}
            >
              {source}
            </button>
          );
        })}
      </div>
    </div>
  );
}
