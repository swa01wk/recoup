"use client";

import type { SafetyCheck } from "@/lib/recovery-types";
import { cn } from "@/lib/utils";

const icon: Record<string, string> = {
  PASS: "✓",
  WARN: "⚠",
  FAIL: "✕",
  UNKNOWN: "?",
};

export function SafetyChecklist({ checks }: { checks: SafetyCheck[] }) {
  if (!checks.length) return null;
  return (
    <div className="space-y-2 pt-2 border-t border-slate-700/40">
      <span className="text-[10px] uppercase tracking-widest text-slate-500">
        Safety checks
      </span>
      <ul className="space-y-1.5">
        {checks.map((c) => (
          <li
            key={c.check}
            className={cn(
              "text-xs flex gap-2",
              c.status === "PASS" && "text-emerald-400/90",
              c.status === "WARN" && "text-amber-400/90",
              c.status === "FAIL" && "text-red-400/90",
              c.status === "UNKNOWN" && "text-slate-400"
            )}
          >
            <span className="shrink-0 w-3">{icon[c.status] ?? "○"}</span>
            <span>
              {c.summary || c.check}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
