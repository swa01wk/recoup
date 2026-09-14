/** Approval-card fallbacks (risk tier, action, rollback) for opportunity detail. */

export const STRANDS_NODES = new Set([
  "incident_correlation",
  "eligibility_reasoner",
  "claim_package_generator",
]);

export type IntentLabel =
  | "Abandoned"
  | "Anomalous"
  | "Policy-violating"
  | "Expected-but-inefficient"
  | "Recoverable";

export function deriveIntentLabel(
  reasons: string[] | undefined
): IntentLabel {
  const text = (reasons ?? []).join(" ").toLowerCase();
  if (/idle|abandon|orphan/.test(text)) return "Abandoned";
  if (/anomal/.test(text)) return "Anomalous";
  if (/policy/.test(text)) return "Policy-violating";
  if (/inefficient|oversized|gp2/.test(text)) return "Expected-but-inefficient";
  return "Recoverable";
}

export function intentBadgeVariant(
  intent: IntentLabel
): "warning" | "error" | "pending" | "default" {
  if (intent === "Abandoned") return "warning";
  if (intent === "Anomalous" || intent === "Policy-violating") return "error";
  if (intent === "Expected-but-inefficient") return "pending";
  return "default";
}

export function riskTierBadgeVariant(
  tier: string
): "success" | "warning" | "error" {
  const normalized = tier.toUpperCase();
  if (normalized === "GREEN") return "success";
  if (normalized === "RED") return "error";
  return "warning";
}

export function fallbackApprovalContext(
  action: string,
  amount: string
): { risk_tier: string; action_description: string; rollback_context: string } {
  const amt = amount.startsWith("$") ? amount : `$${amount}`;
  if (action === "apply_cost_recovery") {
    return {
      risk_tier: "YELLOW",
      action_description: `Record cost recovery (${amt}/mo estimated savings)`,
      rollback_context: `Scanner-estimated savings · Claim bound at promote · Review evidence before approving`,
    };
  }
  if (action === "submit_support_case") {
    return {
      risk_tier: "YELLOW",
      action_description: `Submit ${amt} SLA credit claim to AWS Support`,
      rollback_context: "Withdraw claim within 24h before submission completes",
    };
  }
  return {
    risk_tier: "YELLOW",
    action_description: `Execute recovery action: ${action.replace(/_/g, " ")} (${amt}/mo)`,
    rollback_context: `Estimated recovery: ${amt}/mo · Review opportunity details before approving`,
  };
}
