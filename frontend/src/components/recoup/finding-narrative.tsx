"use client";

interface FindingNarrativeProps {
  insight: string | null;
  whyBullets: string[];
  counterBullets: string[];
  resourceId?: string | null;
  resourceLabel?: string;
  truncateResourceId?: (id: string, max: number) => string;
}

export function FindingNarrative({
  insight,
  whyBullets,
  counterBullets,
  resourceId,
  resourceLabel = "Resource",
  truncateResourceId,
}: FindingNarrativeProps) {
  return (
    <div className="space-y-4">
      {resourceId && (
        <div>
          <span className="text-[10px] uppercase tracking-widest text-slate-500">
            {resourceLabel}
          </span>
          <p
            className="font-mono text-[11px] text-slate-500 truncate mt-0.5"
            title={resourceId}
          >
            {truncateResourceId ? truncateResourceId(resourceId, 36) : resourceId}
          </p>
        </div>
      )}

      <div>
        <span className="text-[10px] uppercase tracking-widest text-slate-500">Insight</span>
        <p className="text-sm text-slate-300 mt-1.5 leading-relaxed">
          {insight ??
            "This resource shows patterns consistent with recoverable waste while continuing to incur cost."}
        </p>
      </div>

      <div>
        <span className="text-[10px] uppercase tracking-widest text-slate-500">
          Why Recoup believes this
        </span>
        <ul className="mt-2 space-y-1.5 text-sm text-slate-300">
          {whyBullets.slice(0, 8).map((item) => (
            <li key={item} className="flex gap-2">
              <span className="text-emerald-500 shrink-0">✓</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>

      <div>
        <span className="text-[10px] uppercase tracking-widest text-amber-500/90">
          Counter-evidence
        </span>
        {counterBullets.length === 0 ? (
          <p className="text-sm text-slate-500 mt-1.5">
            No meaningful contradicting signals detected.
          </p>
        ) : (
          <ul className="mt-2 space-y-1.5 text-sm text-amber-200/90">
            {counterBullets.map((item) => (
              <li key={item} className="flex gap-2">
                <span className="shrink-0">⚠</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
