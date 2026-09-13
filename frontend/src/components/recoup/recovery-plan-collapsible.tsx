"use client";

import { useState } from "react";
import type { RecoveryPlan } from "@/lib/recovery-types";
import { cn } from "@/lib/utils";

const PHASE_ORDER = ["precheck", "execution", "verification"] as const;
const PHASE_LABEL: Record<string, string> = {
  precheck: "Pre-checks",
  execution: "Execution",
  verification: "Verification",
  rollback: "Rollback",
};

interface RecoveryPlanCardProps {
  plan: RecoveryPlan | null | undefined;
  /** When true, show as always-visible card (right column). When false, legacy collapsible. */
  variant?: "card" | "collapsible";
}

export function RecoveryPlanCollapsible({
  plan,
  variant = "collapsible",
}: RecoveryPlanCardProps) {
  const [legacyOpen, setLegacyOpen] = useState(false);
  const [expandedStep, setExpandedStep] = useState<string | null>(null);

  if (!plan) return null;

  const structured = plan.structured_steps ?? [];
  const orderedSteps = structured.length
    ? [
        ...PHASE_ORDER.flatMap((phase) =>
          structured.filter((s) => s.phase === phase)
        ),
        ...structured.filter(
          (s) => !PHASE_ORDER.includes(s.phase as (typeof PHASE_ORDER)[number])
        ),
      ]
    : [];

  const listItems =
    orderedSteps.length > 0
      ? orderedSteps
      : [
          ...(plan.execution_steps ?? []).map((title, i) => ({
            step_id: `exec-${i}`,
            title,
            description: "",
            phase: "execution" as const,
          })),
          ...(plan.verification_steps ?? []).map((title, i) => ({
            step_id: `ver-${i}`,
            title,
            description: "",
            phase: "verification" as const,
          })),
        ];

  const body = (
    <div className="space-y-3">
      <ol className="space-y-2">
        {listItems.map((step, idx) => {
          const open = expandedStep === step.step_id;
          return (
            <li key={step.step_id} className="text-sm text-slate-300">
              <button
                type="button"
                className="text-left w-full flex gap-2 hover:text-slate-100"
                onClick={() =>
                  setExpandedStep(open ? null : step.step_id)
                }
              >
                <span className="text-slate-500 shrink-0">{idx + 1}.</span>
                <span className="font-medium">{step.title}</span>
              </button>
              {open && step.description && (
                <p className="pl-6 text-xs text-slate-500 mt-1">{step.description}</p>
              )}
            </li>
          );
        })}
      </ol>
      {plan.rollback_strategy && (
        <div className="pt-2 border-t border-slate-700/40">
          <span className="text-[10px] uppercase tracking-widest text-slate-500">Rollback</span>
          <p className="text-sm text-slate-400 mt-1">{plan.rollback_strategy}</p>
        </div>
      )}
    </div>
  );

  if (variant === "card") {
    return (
      <div className="space-y-3">
        <h3 className="text-xs font-semibold uppercase tracking-widest text-slate-400">
          Recovery Plan
        </h3>
        {body}
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-slate-700/40 bg-slate-800/20">
      <button
        type="button"
        onClick={() => setLegacyOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-slate-300 hover:bg-slate-800/40"
      >
        View Recovery Plan
        <span className={cn("text-slate-500 transition-transform", legacyOpen && "rotate-180")}>
          ▼
        </span>
      </button>
      {legacyOpen && (
        <div className="px-4 pb-4 border-t border-slate-700/40 pt-3">{body}</div>
      )}
    </div>
  );
}
