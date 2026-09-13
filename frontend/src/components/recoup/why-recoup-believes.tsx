"use client";

interface WhyRecoupBelievesProps {
  whyBullets: string[];
  counterBullets: string[];
  onViewRawEvidence?: () => void;
}

export function WhyRecoupBelieves({
  whyBullets,
  counterBullets,
  onViewRawEvidence,
}: WhyRecoupBelievesProps) {
  return (
    <div className="space-y-4">
      <h3 className="text-xs font-semibold uppercase tracking-widest text-slate-400">
        Why Recoup Believes This
      </h3>
      <ul className="space-y-1.5 text-sm text-slate-300">
        {whyBullets.slice(0, 8).map((item) => (
          <li key={item} className="flex gap-2">
            <span className="text-emerald-500 shrink-0">✓</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>

      <div>
        <span className="text-[10px] uppercase tracking-widest text-amber-500/90">
          Counter-evidence
        </span>
        {counterBullets.length === 0 ? (
          <p className="text-sm text-slate-500 mt-1.5">
            No meaningful contradictory signals were detected.
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

      {onViewRawEvidence && (
        <button
          type="button"
          onClick={onViewRawEvidence}
          className="text-xs text-blue-400 hover:text-blue-300"
        >
          View raw evidence →
        </button>
      )}
    </div>
  );
}
