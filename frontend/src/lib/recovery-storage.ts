import type { Finding, ScanResult, ScanHistoryEntry } from "@/lib/api";

export const LAST_SCAN_KEY = "recoup:lastScanResult";
export const SCAN_COUNT_KEY = "recoup:lastScanFindingCount";
export const SCAN_HISTORY_KEY = "recoup:scanHistory";

/** Maximum number of scan history entries to keep in localStorage. */
const MAX_HISTORY_ENTRIES = 20;

/**
 * Rich per-scan record stored in localStorage.
 * Extends the backend ScanHistoryEntry with full findings for inline display.
 */
export interface LocalScanEntry extends ScanHistoryEntry {
  findings: Finding[];
}

export function saveLastScan(result: ScanResult): void {
  localStorage.setItem(LAST_SCAN_KEY, JSON.stringify(result));
  localStorage.setItem(SCAN_COUNT_KEY, String(result.findings.length));
  // Append to local scan history (persists across page loads)
  appendScanHistory({
    scan_id: result.scan_id ?? null,
    scanned_at: result.scanned_at,
    scan_hash: result.scan_hash ?? null,
    region: result.region,
    finding_count: result.findings.length,
    total_savings_usd: result.total_estimated_monthly_savings_usd,
    is_cached: result.is_cached ?? false,
    findings_by_service: Object.fromEntries(
      Object.entries(result.findings_by_service ?? {}).map(([svc, list]) => [svc, list.length])
    ),
    findings: result.findings,
  });
}

export function loadLastScan(): ScanResult | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(LAST_SCAN_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as ScanResult;
  } catch {
    return null;
  }
}

export function appendScanHistory(entry: LocalScanEntry): void {
  if (typeof window === "undefined") return;
  const existing = loadScanHistory();
  // Avoid duplicates with the same scan_id
  const deduped = entry.scan_id
    ? existing.filter((e) => e.scan_id !== entry.scan_id)
    : existing;
  const next = [entry, ...deduped].slice(0, MAX_HISTORY_ENTRIES);
  localStorage.setItem(SCAN_HISTORY_KEY, JSON.stringify(next));
}

export function loadScanHistory(): LocalScanEntry[] {
  if (typeof window === "undefined") return [];
  const raw = localStorage.getItem(SCAN_HISTORY_KEY);
  if (!raw) return [];
  try {
    return JSON.parse(raw) as LocalScanEntry[];
  } catch {
    return [];
  }
}

/** Clear all scan-related keys from localStorage (call after a full backend reset). */
export function clearLocalScanData(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(LAST_SCAN_KEY);
  localStorage.removeItem(SCAN_COUNT_KEY);
  localStorage.removeItem(SCAN_HISTORY_KEY);
}

/**
 * Maps an opportunity state to its 1-based stage index in the 11-step pipeline.
 *
 * 11-step pipeline (unified across all opportunity types):
 *   1 Detect → 2 Investigate → 3 Correlate → 4 Explain → 5 Prove →
 *   6 Plan → 7 Policy → 8 Approve → 9 Remediate → 10 Verify → 11 Record
 */
export function pipelineStageForOpportunity(state: string): number {
  const normalized = state.toUpperCase();
  if (normalized === "DETECTED") return 1;           // Detect
  if (normalized === "INVESTIGATING") return 2;       // Investigate
  if (normalized === "NEEDS_EVIDENCE") return 3;     // Correlate
  if (normalized === "EVIDENCE_READY") return 5;     // Prove
  if (normalized === "ELIGIBILITY_REVIEWED") return 6; // Plan
  if (normalized === "AWAITING_APPROVAL") return 8;  // Approve
  if (normalized === "NEEDS_FOLLOWUP") return 8;     // still at Approve gate
  if (normalized === "APPROVED") return 9;           // Remediate
  if (normalized === "SUBMITTING" || normalized === "SUBMITTED") return 9; // Remediate
  if (normalized === "MONITORING") return 10;        // Verify
  if (normalized === "RECOVERED") return 11;         // Record
  // Terminal negatives stay at the last gate reached
  if (normalized === "DENIED" || normalized === "REJECTED") return 8;
  if (normalized === "DECLINED" || normalized === "FAILED") return 9;
  return 1;
}

/** The 6-stage labels kept for backward compat — new code should use PIPELINE_STEPS (11 steps). */
export const COST_RECOVERY_STAGES = [
  "Detect",
  "Investigate",
  "Plan",
  "Policy",
  "Approve",
  "Record",
] as const;

/**
 * Maps an opportunity state to one of the 4 canonical lifecycle buckets.
 * These buckets are mutually exclusive — an opportunity belongs to exactly one.
 *
 * DETECTED  = early stages (investigation, evidence gathering)
 * PENDING   = awaiting human approval
 * APPROVED  = post-approval (remediating / submitting)
 * RECOVERED = verified savings confirmed
 */
export type CanonicalLifecycle = "DETECTED" | "PENDING" | "APPROVED" | "RECOVERED";

export function toCanonicalLifecycle(state: string): CanonicalLifecycle {
  const s = state.toUpperCase();
  if (["DETECTED", "INVESTIGATING", "NEEDS_EVIDENCE", "EVIDENCE_READY", "ELIGIBILITY_REVIEWED"].includes(s)) {
    return "DETECTED";
  }
  if (["AWAITING_APPROVAL", "NEEDS_FOLLOWUP"].includes(s)) {
    return "PENDING";
  }
  // APPROVED, SUBMITTING, SUBMITTED, MONITORING, RECOVERED all collapse into RECOVERED
  // (Approve is the final human action — what follows is mechanical execution)
  if (["APPROVED", "SUBMITTING", "SUBMITTED", "MONITORING", "RECOVERED"].includes(s)) {
    return "RECOVERED";
  }
  // Terminal negatives (REJECTED, FAILED, DECLINED, DENIED) → DETECTED
  return "DETECTED";
}

export function scenarioStatus(
  tag: string,
  findings: Finding[],
  promotedResourceIds: Set<string>,
  recoveredIds: Set<string>
): "detected" | "pending" | "recovered" | "idle" {
  const match = findings.find((f) => f.scenario_tag === tag);
  if (!match) return "idle";
  if (recoveredIds.has(match.resource_id)) return "recovered";
  if (promotedResourceIds.has(match.resource_id)) return "pending";
  return "detected";
}
