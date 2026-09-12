"use client";

import { cn } from "@/lib/utils";
import { PIPELINE_STEPS, PIPELINE_STAGE_HINTS, pipelineStepLabel } from "@/lib/recoup-ui-rules";
import { Tooltip } from "@/components/ui/tooltip";

interface LifecycleStepperProps {
  activeStage: number;
  stageHints?: Record<number, string>;
  failed?: boolean;
  /** When true, all pipeline stages render as completed (e.g. RECOVERED). */
  allStagesComplete?: boolean;
  /** Current pipeline execution stage (e.g. "Remediating") */
  executionLabel?: string;
  /** Lifecycle authorization state (e.g. "Approved") — shown when distinct from execution */
  lifecycleLabel?: string;
  compact?: boolean;
  className?: string;
}

export function LifecycleStepper({
  activeStage,
  stageHints = PIPELINE_STAGE_HINTS,
  failed = false,
  allStagesComplete = false,
  executionLabel,
  lifecycleLabel,
  compact = false,
  className,
}: LifecycleStepperProps) {
  const clampedStage = Math.max(1, Math.min(activeStage, PIPELINE_STEPS.length));
  const stageName = executionLabel ?? pipelineStepLabel(clampedStage);
  const displayStage = allStagesComplete ? PIPELINE_STEPS.length : clampedStage;
  const showLifecycle =
    lifecycleLabel &&
    lifecycleLabel.toLowerCase() !== stageName.toLowerCase();

  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <p className="text-xs text-slate-500 uppercase tracking-wide font-semibold">
          Step {displayStage} of {PIPELINE_STEPS.length}
          <span className="text-slate-300 font-normal normal-case ml-2">
            — {stageName}
          </span>
        </p>
        {showLifecycle && (
          <span className="text-[10px] text-slate-500 normal-case">
            Lifecycle: <span className="text-violet-300">{lifecycleLabel}</span>
          </span>
        )}
      </div>

      {compact ? (
        <div className="flex items-center gap-1 overflow-x-auto pb-1">
          {PIPELINE_STEPS.map((label, i) => {
            const stage = i + 1;
            const isDone = !failed && (allStagesComplete || stage < clampedStage);
            const isActive = !allStagesComplete && !failed && stage === clampedStage;
            const isFailed = failed && !allStagesComplete && stage === clampedStage;
            return (
              <div key={label} className="flex items-center gap-1 shrink-0">
                <div
                  className={cn(
                    "h-1.5 w-6 rounded-full transition-all",
                    isDone
                      ? "bg-emerald-600"
                      : isFailed
                      ? "bg-red-600"
                      : isActive
                      ? "bg-blue-500"
                      : "bg-slate-700"
                  )}
                  title={label}
                />
              </div>
            );
          })}
        </div>
      ) : (
        <div className="flex items-center gap-1 flex-wrap">
          {PIPELINE_STEPS.map((label, i) => {
            const stage = i + 1;
            const isDone = !failed && (allStagesComplete || stage < clampedStage);
            const isActive = !allStagesComplete && !failed && stage === clampedStage;
            const isFailed = failed && !allStagesComplete && stage === clampedStage;
            const hint = stageHints[stage];
            const pill = (
              <div
                className={cn(
                  "px-2.5 py-1 rounded-full text-[10px] font-semibold border transition-all whitespace-nowrap",
                  isDone
                    ? "border-emerald-700/60 bg-emerald-900/20 text-emerald-300"
                    : isFailed
                    ? "border-red-700/60 bg-red-900/20 text-red-300"
                    : isActive
                    ? "border-blue-600/70 bg-blue-900/20 text-blue-300"
                    : "border-slate-700/40 bg-slate-800/20 text-slate-500"
                )}
              >
                {isDone ? "✓ " : isFailed ? "✕ " : isActive ? "● " : "○ "}
                {label}
              </div>
            );
            return (
              <div key={label} className="flex items-center gap-1">
                {hint && (isDone || isActive) ? (
                  <Tooltip content={<span className="max-w-[220px] block">{hint}</span>}>
                    {pill}
                  </Tooltip>
                ) : (
                  pill
                )}
                {i < PIPELINE_STEPS.length - 1 && (
                  <span className="text-slate-600 text-[10px]">→</span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/** Business milestones only — use when a simplified progress view is needed. */
export const BUSINESS_MILESTONES = [
  "Detected",
  "Evidence Ready",
  "Awaiting Approval",
  "Approved",
  "Recovered",
] as const;

interface BusinessMilestoneStripProps {
  activeIndex: number;
  className?: string;
}

export function BusinessMilestoneStrip({ activeIndex, className }: BusinessMilestoneStripProps) {
  return (
    <div className={cn("flex items-center gap-2 flex-wrap", className)}>
      {BUSINESS_MILESTONES.map((label, i) => {
        const isDone = i < activeIndex;
        const isActive = i === activeIndex;
        return (
          <div key={label} className="flex items-center gap-2">
            <span
              className={cn(
                "text-[10px] font-medium uppercase tracking-wide",
                isDone ? "text-emerald-400" : isActive ? "text-blue-400" : "text-slate-600"
              )}
            >
              {isDone ? "✓ " : isActive ? "● " : "○ "}
              {label}
            </span>
            {i < BUSINESS_MILESTONES.length - 1 && (
              <span className="text-slate-700 text-[10px]">→</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

/** Map opportunity state to business milestone index (0–4). */
export function stateToMilestoneIndex(state: string): number {
  const s = state.toUpperCase();
  if (["RECOVERED", "MONITORING"].includes(s)) return 4;
  if (["APPROVED", "SUBMITTING", "SUBMITTED"].includes(s)) return 3;
  if (["AWAITING_APPROVAL", "NEEDS_FOLLOWUP"].includes(s)) return 2;
  if (["EVIDENCE_READY", "ELIGIBILITY_REVIEWED"].includes(s)) return 1;
  return 0;
}
