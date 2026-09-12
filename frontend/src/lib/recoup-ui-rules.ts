/**
 * Recoup UI Rules — single source of truth for vocabulary, color semantics, and card anatomy.
 *
 * Every component that renders opportunity data MUST import from here instead of
 * hardcoding badge colors, metric formats, or label strings.
 */

// ---------------------------------------------------------------------------
// Badge color semantics (fixed — never reuse a color for a different meaning)
// ---------------------------------------------------------------------------
// Matches the Variant type in badge.tsx exactly
export type BadgeVariant =
  | "success"
  | "approved"
  | "active"
  | "pending"
  | "warning"
  | "error"
  | "outline"
  | "default";

/**
 * Fixed color-to-state mapping (never reuse a color for a different meaning).
 *
 *  success  (emerald) → RECOVERED
 *  approved (purple)  → APPROVED, authorized
 *  pending  (amber)   → PENDING, awaiting human action
 *  active   (blue)    → in-progress pipeline stages
 *  warning  (amber)   → SUBMITTING/risk-yellow
 *  error    (red)     → REJECTED, FAILED, DECLINED, DENIED
 *  default  (slate)   → DETECTED, neutral
 */
export const LIFECYCLE_BADGE_VARIANT: Record<string, BadgeVariant> = {
  DETECTED:             "default",   // Slate — neutral
  INVESTIGATING:        "active",    // Blue — in-progress
  NEEDS_EVIDENCE:       "active",
  EVIDENCE_READY:       "active",
  ELIGIBILITY_REVIEWED: "active",
  AWAITING_APPROVAL:    "pending",   // Amber — awaiting action
  NEEDS_FOLLOWUP:       "pending",
  APPROVED:             "approved",  // Purple — authorized
  SUBMITTING:           "approved",
  SUBMITTED:            "approved",
  MONITORING:           "approved",
  RECOVERED:            "success",   // Emerald — verified savings
  // Terminal negatives
  REJECTED:             "error",
  FAILED:               "error",
  DECLINED:             "error",
  DENIED:               "error",
  // 4-bucket canonical aliases
  PENDING:              "pending",
};

/** Return a badge variant for any raw opportunity state string. */
export function lifecycleBadgeVariant(state: string): BadgeVariant {
  return LIFECYCLE_BADGE_VARIANT[state.toUpperCase()] ?? "default";
}

// ---------------------------------------------------------------------------
// Severity badge variants
// ---------------------------------------------------------------------------
export function severityBadgeVariant(severity: string): BadgeVariant {
  if (severity === "high") return "error";
  if (severity === "medium") return "warning";
  return "default";
}

// ---------------------------------------------------------------------------
// Metric formatter — always include context (unit + timeframe)
// ---------------------------------------------------------------------------
export function fmtSavings(value: number | string): string {
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(n)) return "$0.00/mo";
  return `$${n.toFixed(2)}/mo`;
}

// ---------------------------------------------------------------------------
// 11-step pipeline labels (single source of truth)
// ---------------------------------------------------------------------------
export const PIPELINE_STEPS = [
  "Detect",      // 1
  "Investigate", // 2
  "Correlate",   // 3
  "Explain",     // 4
  "Prove",       // 5
  "Plan",        // 6
  "Policy",      // 7
  "Approve",     // 8
  "Remediate",   // 9
  "Verify",      // 10
  "Record",      // 11
] as const;

export type PipelineStep = (typeof PIPELINE_STEPS)[number];

/** Short contextual copy for pipeline stepper tooltips (1-based stage index). */
export const PIPELINE_STAGE_HINTS: Record<number, string> = {
  1: "Potential idle or wasteful AWS resource discovered.",
  2: "CloudWatch, CloudTrail, and resource metadata inspected.",
  3: "Independent AWS signals correlated into resource context.",
  4: "Investigator produced structured insights from evidence.",
  5: "Evidence sufficiency evaluated against expected coverage.",
  6: "Safest effective recovery action selected from allow-list.",
  7: "Recovery policy checked — human approval when required.",
  8: "Awaiting operator approve, investigate, or decline.",
  9: "Allow-listed remediation executing on approved action.",
  10: "Post-action verification and dependency checks running.",
  11: "Verified savings recorded in the recovery ledger.",
};

// ---------------------------------------------------------------------------
// Card anatomy constants
// ---------------------------------------------------------------------------
export const CARD_ANATOMY = {
  header: "header (title + badge)",
  body:   "body (metric or list)",
  footer: "footer (primary action)",
} as const;

// ---------------------------------------------------------------------------
// Page responsibilities (one job per page)
// ---------------------------------------------------------------------------
export const PAGE_JOBS = {
  "/":           "monitor: current recovery state, pending actions, operating picture",
  "/scan":       "discover: connect AWS, scan, start recovery",
  "/approvals":  "redirect: legacy inbox URL → opportunities hub",
  "/recovery":   "audit: closed-loop financial and event history",
  "/quality":    "redirect: legacy scorecard page → opportunities (use GET /api/quality/scorecard)",
} as const;

// ---------------------------------------------------------------------------
// Information flow (enforced in every opportunity surface)
// ---------------------------------------------------------------------------
export const INFORMATION_FLOW = [
  "Finding",
  "Evidence",
  "Impact",
  "Recommendation",
  "Decision",
  "Outcome",
] as const;

// ---------------------------------------------------------------------------
// Business-first copy helpers
// ---------------------------------------------------------------------------

/** Human-readable lifecycle label (business language first). */
export function formatLifecycleLabel(state: string): string {
  const s = state.toUpperCase();
  if (s === "DETECTED") return "Detected";
  if (s === "INVESTIGATING" || s === "NEEDS_EVIDENCE") return "Investigating";
  if (s === "EVIDENCE_READY" || s === "ELIGIBILITY_REVIEWED") return "Evidence Ready";
  if (s === "NEEDS_FOLLOWUP") return "Under Investigation";
  if (s === "AWAITING_APPROVAL") return "Awaiting Approval";
  if (s === "APPROVED" || s === "SUBMITTING" || s === "SUBMITTED" || s === "MONITORING") return "Approved";
  if (s === "RECOVERED") return "Recovered";
  if (["REJECTED", "FAILED", "DECLINED", "DENIED"].includes(s)) {
    return state.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }
  return state.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Current pipeline step label for stepper subtitle. */
export function pipelineStepLabel(stageIndex: number): string {
  const idx = Math.max(1, Math.min(stageIndex, PIPELINE_STEPS.length));
  return PIPELINE_STEPS[idx - 1];
}

/** Annual savings from monthly amount. */
export function fmtYearlySavings(monthly: number): string {
  if (isNaN(monthly) || monthly <= 0) return "$0.00/yr";
  return `$${(monthly * 12).toFixed(2)}/yr`;
}

/** Dollar amount without a timeframe suffix (for composing custom labels). */
export function fmtDollarAmount(value: number): string {
  if (isNaN(value)) return "$0.00";
  return `$${value.toFixed(2)}`;
}

/** Format a verification timestamp for the recovery success state. */
export function fmtVerifiedTimestamp(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

/** @deprecated Use serviceFindingSummary from @/lib/service-presentation */
export function findingSummary(issue: string, _service?: string): string {
  const trimmed = issue.trim();
  if (trimmed.length <= 72) return trimmed;
  if (/stopped|idle|unused|orphan/i.test(trimmed)) return "Idle resource detected";
  if (/oversized|underutil/i.test(trimmed)) return "Underutilized resource detected";
  return trimmed.slice(0, 69) + "…";
}

/** Risk tier display label. */
export function formatRiskTier(tier: string): string {
  const t = tier.toUpperCase();
  if (t === "GREEN") return "Low";
  if (t === "YELLOW") return "Medium";
  if (t === "RED") return "High";
  return tier.charAt(0).toUpperCase() + tier.slice(1).toLowerCase();
}

/** Map severity to risk display. */
export function severityToRisk(severity: string): string {
  if (severity === "high") return "High";
  if (severity === "medium") return "Medium";
  return "Low";
}
