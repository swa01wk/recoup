"use client";

import { useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import { fmtSavings } from "@/lib/recoup-ui-rules";
import type { EvidenceGraph, OperationalSignal } from "@/lib/recovery-types";

interface EvidenceGraphColumnProps {
  graph: EvidenceGraph | undefined;
  signals: OperationalSignal[];
  selectedSource?: string | null;
  claimFallback?: string;
  recommendationFallback?: string;
  savingsMonthly?: number;
}

function shortLabel(text: string, max = 28): string {
  const t = text.trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max - 1)}…`;
}

export function EvidenceGraphColumn({
  graph,
  signals,
  claimFallback = "",
  recommendationFallback = "",
  savingsMonthly,
}: EvidenceGraphColumnProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const claimNode = graph?.nodes.find((n) => n.kind === "claim");
  const recNode = graph?.nodes.find((n) => n.kind === "recommendation");
  const signalNodes = graph?.nodes.filter((n) => n.kind === "signal") ?? [];

  const displaySignals = useMemo(() => {
    if (signalNodes.length > 0) {
      return signalNodes.map((n) => {
        const sig = signals.find((s) => s.signal_id === n.node_id || s.signal_id === n.signal_id);
        return { id: n.node_id, label: n.label, sig };
      });
    }
    return signals.map((sig) => ({
      id: sig.signal_id,
      label: sig.description || sig.value,
      sig,
    }));
  }, [signalNodes, signals]);

  const claimLabel = claimNode?.label || claimFallback || "Likely waste";
  const recLabel = recNode?.label || recommendationFallback;

  const selected = useMemo(() => {
    if (!selectedId) return null;
    const row = displaySignals.find((d) => d.id === selectedId);
    if (row?.sig) return { type: "signal" as const, sig: row.sig, label: row.label };
    if (selectedId === "claim") return { type: "claim" as const, label: claimLabel };
    if (selectedId === "rec") return { type: "rec" as const, label: recLabel };
    return null;
  }, [selectedId, displaySignals, claimLabel, recLabel]);

  if (!displaySignals.length && !claimLabel && !recLabel) return null;

  return (
    <div className="space-y-3">
      <span className="text-[10px] uppercase tracking-widest text-slate-500">Evidence graph</span>

      <div className="flex flex-col items-center gap-1 py-2 text-center">
        {displaySignals.length > 0 && (
          <>
            <div className="flex flex-wrap gap-2 justify-center w-full">
              {displaySignals.map(({ id, label, sig }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setSelectedId(id === selectedId ? null : id)}
                  className={cn(
                    "rounded border px-2 py-1.5 text-[11px] min-w-[88px] max-w-[140px] transition-colors",
                    selectedId === id
                      ? "border-blue-500/70 bg-blue-950/30 text-slate-100"
                      : "border-slate-600 bg-slate-800/50 text-slate-300 hover:border-slate-500"
                  )}
                >
                  <div className="font-medium truncate">{shortLabel(label)}</div>
                  {sig?.source && (
                    <div className="text-[10px] text-slate-500 truncate">{sig.source}</div>
                  )}
                </button>
              ))}
            </div>
            <div className="text-slate-600 text-sm">↓</div>
          </>
        )}

        <button
          type="button"
          onClick={() => setSelectedId(selectedId === "claim" ? null : "claim")}
          className={cn(
            "text-sm font-medium px-3 py-1 rounded border max-w-md",
            selectedId === "claim"
              ? "border-blue-500/70 text-slate-100 bg-blue-950/20"
              : "border-transparent text-slate-200"
          )}
        >
          {shortLabel(claimLabel, 80)}
        </button>

        {recLabel && (
          <>
            <div className="text-slate-600 text-sm">↓</div>
            <button
              type="button"
              onClick={() => setSelectedId(selectedId === "rec" ? null : "rec")}
              className={cn(
                "text-sm font-semibold px-3 py-1 rounded border max-w-md",
                selectedId === "rec"
                  ? "border-blue-500/70 text-blue-200 bg-blue-950/20"
                  : "border-transparent text-blue-300/90"
              )}
            >
              {shortLabel(recLabel, 80)}
            </button>
          </>
        )}

        {savingsMonthly != null && savingsMonthly > 0 && (
          <>
            <div className="text-slate-600 text-sm">↓</div>
            <p className="text-sm font-medium text-emerald-400/90">
              {fmtSavings(savingsMonthly)} recovery
            </p>
          </>
        )}
      </div>

      {selected?.type === "signal" && selected.sig && (
        <div className="rounded-md border border-slate-700/40 bg-slate-900/50 px-3 py-2 text-xs text-slate-300 space-y-1">
          <p className="font-semibold uppercase text-slate-400">{shortLabel(selected.label, 48)}</p>
          {selected.sig.source && (
            <p>
              <span className="text-slate-500">Source:</span> {selected.sig.source}
            </p>
          )}
          <p className="leading-relaxed">
            {selected.sig.description || selected.sig.value}
          </p>
        </div>
      )}
      {selected?.type === "claim" && (
        <div className="rounded-md border border-slate-700/40 bg-slate-900/50 px-3 py-2 text-xs text-slate-300">
          <p className="font-semibold uppercase text-slate-400 mb-1">Finding</p>
          <p>{claimLabel}</p>
        </div>
      )}
      {selected?.type === "rec" && (
        <div className="rounded-md border border-slate-700/40 bg-slate-900/50 px-3 py-2 text-xs text-slate-300">
          <p className="font-semibold uppercase text-slate-400 mb-1">Recommended action</p>
          <p>{recLabel}</p>
        </div>
      )}
    </div>
  );
}
