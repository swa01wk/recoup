"use client";

import type { SafetyCheck } from "@/lib/recovery-types";
import { SafetyChecklist } from "@/components/recoup/safety-checklist";

export function SafetyChecksCard({ checks }: { checks: SafetyCheck[] }) {
  if (!checks.length) return null;
  return (
    <div className="space-y-3">
      <h3 className="text-xs font-semibold uppercase tracking-widest text-slate-400">
        Safety Checks
      </h3>
      <SafetyChecklist checks={checks} bare />
    </div>
  );
}
