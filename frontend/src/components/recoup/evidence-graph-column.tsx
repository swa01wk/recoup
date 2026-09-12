"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Tooltip } from "@/components/ui/tooltip";
import type { EvidenceGraph, OperationalSignal } from "@/lib/recovery-types";

interface EvidenceGraphColumnProps {
  graph: EvidenceGraph | undefined;
  signals: OperationalSignal[];
  selectedSource: string | null;
  claimFallback?: string;
  recommendationFallback?: string;
}

function signalTooltip(sig: OperationalSignal): ReactNode {
  return (
    <div className="space-y-0.5 text-left max-w-xs">
      <div>
        <span className="text-slate-500">Source:</span> {sig.source ?? "—"}
      </div>
      <div>
        <span className="text-slate-500">Metric:</span> {sig.metric_or_event || sig.signal_type}
      </div>
      <div>
        <span className="text-slate-500">Value:</span> {sig.value}
      </div>
      {sig.observation_window && (
        <div>
          <span className="text-slate-500">Window:</span> {sig.observation_window}
        </div>
      )}
      {sig.freshness && (
        <div>
          <span className="text-slate-500">Freshness:</span> {sig.freshness}
        </div>
      )}
      {sig.direction && (
        <div>
          <span className="text-slate-500">Direction:</span> {sig.direction}
        </div>
      )}
      {sig.raw_reference && (
        <div className="truncate">
          <span className="text-slate-500">Ref:</span> {sig.raw_reference}
        </div>
      )}
    </div>
  );
}

export function EvidenceGraphColumn({
  graph,
  signals,
  selectedSource,
  claimFallback = "",
  recommendationFallback = "",
}: EvidenceGraphColumnProps) {
  const nodes = graph?.nodes ?? [];
  const claimNode = nodes.find((n) => n.kind === "claim");
  const recNode = nodes.find((n) => n.kind === "recommendation");
  const signalNodes = nodes.filter((n) => n.kind === "signal");

  const displaySignals =
    signalNodes.length > 0
      ? signalNodes.map((n) => {
          const sig = signals.find((s) => s.signal_id === n.node_id);
          return { node: n, sig };
        })
      : signals.map((sig) => ({
          node: { node_id: sig.signal_id, label: sig.description || sig.value, kind: "signal" },
          sig,
        }));

  const filtered = selectedSource
    ? displaySignals.filter(
        ({ sig }) => sig?.source?.toLowerCase() === selectedSource.toLowerCase()
      )
    : displaySignals;

  const claimLabel = claimNode?.label || claimFallback;
  const recLabel = recNode?.label || recommendationFallback;

  if (!filtered.length && !claimLabel) return null;

  return (
    <div className="space-y-3">
      <span className="text-[10px] uppercase tracking-widest text-slate-500">
        Evidence graph
      </span>
      <div className="flex flex-wrap gap-2 justify-center py-2">
        {displaySignals.map(({ node, sig }, idx) => {
          if (!sig) return null;
          const dim =
            selectedSource &&
            sig.source?.toLowerCase() !== selectedSource.toLowerCase();
          const short = sig.source || node.label.slice(0, 24);
          return (
            <Tooltip key={`${node.node_id}-${idx}`} content={signalTooltip(sig)}>
              <button
                type="button"
                className={cn(
                  "rounded-md border px-2 py-1.5 text-[11px] text-left max-w-[140px] transition-opacity",
                  dim ? "opacity-30 border-slate-800" : "border-slate-600 bg-slate-800/50 text-slate-300",
                  !dim && selectedSource && sig.source?.toLowerCase() === selectedSource.toLowerCase()
                    ? "ring-1 ring-blue-500/60"
                    : ""
                )}
              >
                <div className="font-medium text-slate-200 truncate">{short}</div>
                <div className="text-slate-500 truncate">{sig.value}</div>
              </button>
            </Tooltip>
          );
        })}
      </div>
      <div className="flex justify-center text-slate-600 text-lg">↓</div>
      <p className="text-center text-sm font-medium text-slate-200 px-4">{claimLabel}</p>
      <div className="flex justify-center text-slate-600 text-lg">↓</div>
      <p className="text-center text-sm font-semibold text-blue-300/90 px-4">{recLabel}</p>
    </div>
  );
}
