"use client";

import { cn } from "@/lib/utils";

interface OpportunityKpiCardProps {
  label: string;
  value: string;
  sentence: string;
  className?: string;
}

export function OpportunityKpiCard({ label, value, sentence, className }: OpportunityKpiCardProps) {
  return (
    <div
      className={cn(
        "rounded-lg border border-slate-700/40 bg-slate-800/30 px-4 py-3 min-h-[88px] flex flex-col justify-center",
        className
      )}
    >
      <span className="text-[10px] font-medium uppercase tracking-widest text-slate-500">
        {label}
      </span>
      <p className="text-lg font-bold text-slate-200 mt-1">{value}</p>
      <p className="text-xs text-slate-400 mt-1 leading-snug line-clamp-3">{sentence}</p>
    </div>
  );
}
