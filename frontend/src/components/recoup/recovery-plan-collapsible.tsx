"use client";

import { useState } from "react";
import type { RecoveryPlan } from "@/lib/recovery-types";
import { cn } from "@/lib/utils";

const PHASE_LABEL: Record<string, string> = {
  precheck: "Pre-checks",
  execution: "Execution",
  verification: "Verification",
  rollback: "Rollback",
};

export function RecoveryPlanCollapsible({ plan }: { plan: RecoveryPlan | null | undefined }) {
  const [open, setOpen] = useState(false);
  if (!plan) return null;

  const structured = plan.structured_steps ?? [];
  const byPhase = structured.length
    ? structured.reduce<Record<string, typeof structured>>((acc, step) => {
        const p = step.phase;
        if (!acc[p]) acc[p] = [];
        acc[p].push(step);
        return acc;
      }, {})
    : null;

  return (
    <div className="rounded-lg border border-slate-700/40 bg-slate-800/20">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-slate-300 hover:bg-slate-800/40"
      >
        View Recovery Plan
        <span className={cn("text-slate-500 transition-transform", open && "rotate-180")}>▼</span>
      </button>
      {open && (
        <div className="px-4 pb-4 space-y-4 border-t border-slate-700/40 pt-3">
          {byPhase ? (
            Object.entries(byPhase).map(([phase, steps]) => (
              <div key={phase}>
                <h4 className="text-[10px] uppercase tracking-widest text-slate-500 mb-2">
                  {PHASE_LABEL[phase] ?? phase}
                </h4>
                <ol className="list-decimal pl-4 text-sm text-slate-400 space-y-1">
                  {steps.map((s) => (
                    <li key={s.step_id}>{s.title}</li>
                  ))}
                </ol>
              </div>
            ))
          ) : (
            <>
              {plan.pre_action_checks?.length ? (
                <Section title="Pre-checks" items={plan.pre_action_checks} />
              ) : null}
              {plan.execution_steps?.length ? (
                <Section title="Execution" items={plan.execution_steps} />
              ) : null}
              {plan.verification_steps?.length ? (
                <Section title="Verification" items={plan.verification_steps} />
              ) : null}
              {plan.rollback_strategy ? (
                <Section title="Rollback" items={[plan.rollback_strategy]} />
              ) : null}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function Section({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h4 className="text-[10px] uppercase tracking-widest text-slate-500 mb-2">{title}</h4>
      <ol className="list-decimal pl-4 text-sm text-slate-400 space-y-1">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ol>
    </div>
  );
}
