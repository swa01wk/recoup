"use client";

interface Edge {
  source_id: string;
  target_id: string;
  relation: string;
}

export function EvidenceGraphSummary({ edges }: { edges: Edge[] }) {
  if (!edges.length) return null;
  return (
    <div className="space-y-1.5">
      <span className="text-[10px] uppercase tracking-widest text-slate-500">
        Evidence graph
      </span>
      <ul className="text-xs text-slate-400 space-y-1 font-mono">
        {edges.slice(0, 6).map((e) => (
          <li key={`${e.source_id}-${e.relation}-${e.target_id}`}>
            signal → <span className="text-slate-300">{e.relation}</span> → claim
          </li>
        ))}
      </ul>
    </div>
  );
}
