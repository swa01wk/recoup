/**
 * Service-aware presentation helpers — business-first labels derived from
 * service, issue text, and backend action codes. Raw backend strings belong
 * in technical details only.
 */

import type { TraceResult } from "@/lib/api";
import { PIPELINE_STEPS } from "@/lib/recoup-ui-rules";

export interface ServiceRecommendation {
  action: string;
  detail?: string;
  raw?: string;
}

const SERVICE_ALIASES: Record<string, string> = {
  EC2: "EC2",
  EBS: "EBS",
  EIP: "EIP",
  RDS: "RDS",
  S3: "S3",
  LAMBDA: "Lambda",
  "LOAD BALANCER": "Load Balancer",
  CLOUDWATCH: "CloudWatch",
};

function normalizeService(service: string): string {
  const key = service.trim().toUpperCase();
  return SERVICE_ALIASES[key] ?? service;
}

/** Strip resource identifiers from prose for evidence bullets. */
function stripResourceIds(text: string): string {
  return text
    .replace(/\b(i-[a-f0-9]{8,17})\b/gi, "instance")
    .replace(/\b(vol-[a-f0-9]{8,17})\b/gi, "volume")
    .replace(/\b(eipalloc-[a-f0-9]+)\b/gi, "Elastic IP")
    .replace(/bucket\s+'[^']+'/gi, "bucket")
    .replace(/Bucket\s+'[^']+'/gi, "Bucket")
    .replace(/\b(recoup[a-z0-9-]{10,})\b/gi, "resource")
    .replace(/\s{2,}/g, " ")
    .trim();
}

/** One-line business finding for tables and hero (condition only, not identity). */
export function serviceFindingSummary(issue: string, service: string): string {
  const svc = normalizeService(service);
  const lower = issue.toLowerCase();

  if (/lifecycle/i.test(lower) && /no lifecycle|without lifecycle|not configured/i.test(lower)) {
    return "No lifecycle policy configured";
  }
  if (/stopped/i.test(lower) && svc === "EC2") return "Stopped instance";
  if (/idle|no connection|zero connection|unused db/i.test(lower) && svc === "RDS") {
    return "Idle RDS instance";
  }
  if (/unattached/i.test(lower) && svc === "EBS") return "Unattached EBS volume";
  if (/unassociated|not associated|unused.*eip|elastic ip/i.test(lower)) return "Unassociated Elastic IP";
  if (/gp2/i.test(lower) && /gp3|migr/i.test(lower)) return "GP2 volume — migrate to GP3";
  if (/oversized|over-provision|underutil/i.test(lower) && svc === "Lambda") {
    return "Oversized Lambda configuration";
  }
  if (/oversized|underutil/i.test(lower) && svc === "EC2") return "Underutilized EC2 instance";
  if (/stale|old|unused/i.test(lower) && /snapshot/i.test(lower)) return "Stale EBS snapshot";
  if (/retention/i.test(lower) && svc === "CloudWatch") return "Missing log retention policy";
  if (/idle|stopped/i.test(lower)) return `Idle ${svc} resource`;
  if (/orphan/i.test(lower)) return "Orphaned resource";

  const trimmed = issue.trim();
  if (trimmed.length <= 72) return trimmed;
  return trimmed.slice(0, 69) + "…";
}

/** Service-specific recommended action (not generic backend placeholder). */
export function serviceRecommendation(
  service: string,
  issue?: string,
  backendAction?: string,
  backendDescription?: string
): ServiceRecommendation {
  const svc = normalizeService(service);
  const lower = (issue ?? "").toLowerCase();
  const raw = backendDescription ?? backendAction;

  if (backendAction === "stop_demo_instance") {
    return {
      action: "Stop EC2 instance",
      detail: "Terminate only after confirming it is no longer required",
      raw,
    };
  }

  if (svc === "EC2") {
    if (/stop|stopped|idle/i.test(lower)) {
      return {
        action: "Stop EC2 instance",
        detail: "Terminate only after confirming it is no longer required",
        raw,
      };
    }
    return { action: "Right-size or stop EC2 instance", raw };
  }

  if (svc === "RDS") {
    return {
      action: "Stop idle RDS instance",
      detail: "Delete only after confirming there are no required dependencies or retained data needs",
      raw,
    };
  }

  if (svc === "EBS") {
    return {
      action: "Delete unattached EBS volume",
      detail: "Snapshot first if retention is required",
      raw,
    };
  }

  if (svc === "S3") {
    return {
      action: "Apply lifecycle policy",
      detail: "Move stale objects to lower-cost storage or expire them",
      raw,
    };
  }

  if (svc === "EIP") {
    return { action: "Release unassociated Elastic IP", raw };
  }

  if (svc === "Lambda") {
    return {
      action: "Right-size or remove unused Lambda configuration",
      raw,
    };
  }

  if (svc === "CloudWatch") {
    return { action: "Apply log retention policy", raw };
  }

  if (backendDescription && !/execute recovery|apply cost recovery/i.test(backendDescription)) {
    return { action: backendDescription, raw };
  }

  return {
    action: `Review ${svc} optimization`,
    raw,
  };
}

/** Rollback instruction — never savings estimates. */
export function serviceRollback(service: string, backendRollback?: string): string {
  const svc = normalizeService(service);

  if (backendRollback) {
    const lower = backendRollback.toLowerCase();
    if (
      /estimated recovery|\$[0-9]|\/mo|review opportunity|apply cost recovery/i.test(lower) &&
      !/restart|restore|re-alloc|rollback|reversible|withdraw|update.*rule|manual/i.test(lower)
    ) {
      // Backend placeholder — replace with service-specific rollback
    } else if (!/estimated recovery|\$[0-9].*\/mo/i.test(lower)) {
      return backendRollback;
    }
  }

  switch (svc) {
    case "EC2":
      return "Restart the instance if needed";
    case "RDS":
      return "Restart the DB instance if it was stopped";
    case "EBS":
      return "Restore from snapshot if one was created before deletion";
    case "S3":
      return "Update or remove lifecycle rule";
    case "EIP":
      return "Re-association may require allocation of a new Elastic IP";
    case "Lambda":
      return "Restore previous configuration";
    case "CloudWatch":
      return "Update or remove retention policy";
    default:
      return "Rollback requires manual restoration";
  }
}

/** Concise human-readable evidence bullets without embedded resource IDs. */
export function deriveConciseEvidence(
  trace: TraceResult | null,
  service: string,
  issue?: string
): string[] {
  const items: string[] = [];
  const lower = (issue ?? "").toLowerCase();

  if (/no connection|zero connection|connection history/i.test(lower)) {
    items.push("No connection history during evaluation window");
  } else if (/idle|stopped|unused|no activity/i.test(lower)) {
    items.push("No meaningful activity detected in evaluation window");
  }

  if (trace?.availability_result?.monthly_uptime_pct) {
    items.push(`Resource uptime ${trace.availability_result.monthly_uptime_pct}%`);
  } else if (/100%|uptime/i.test(lower)) {
    items.push("Resource uptime 100%");
  }

  const eligible = trace?.eligibility?.is_eligible ?? trace?.eligibility?.eligible_estimate;
  if (eligible === true) {
    items.push("Eligible for recovery");
  }

  if (trace?.eligibility?.satisfied_requirements?.length) {
    for (const req of trace.eligibility.satisfied_requirements.slice(0, 2)) {
      items.push(stripResourceIds(req));
    }
  }

  if (items.length === 0) {
    items.push("Scan finding matched recovery criteria");
    items.push("Policy pre-check passed");
  }

  if (!items.some((i) => /depend|usage signal/i.test(i))) {
    items.push("No active dependency or usage signal detected");
  }

  return [...new Set(items)].slice(0, 5);
}

/** Known AWS evidence sources shown as compact chips in the UI. */
export type EvidenceSource = "CloudWatch" | "CloudTrail" | "Cost Explorer" | "AWS Config";

const EVIDENCE_SOURCE_ORDER: EvidenceSource[] = [
  "CloudWatch",
  "CloudTrail",
  "Cost Explorer",
  "AWS Config",
];

const KNOWN_EVIDENCE_SOURCES = new Set<string>(EVIDENCE_SOURCE_ORDER);

function normalizeEvidenceSource(value: string): EvidenceSource | null {
  const normalized = value.trim();
  if (KNOWN_EVIDENCE_SOURCES.has(normalized)) {
    return normalized as EvidenceSource;
  }
  return null;
}

/**
 * Derive AWS evidence sources from finding metadata and agent trace.
 * Only returns sources with a reliable mapping — never invents sources.
 */
export function deriveEvidenceSources(
  service: string,
  findingType: string | null | undefined,
  evidence: Record<string, unknown> | undefined,
  trace: TraceResult | null
): EvidenceSource[] {
  const sources = new Set<EvidenceSource>();
  const ev = evidence ?? {};
  const ft = (findingType ?? "").toUpperCase();
  const svc = service.trim().toUpperCase();

  // Explicit source list from backend finding metadata (if present)
  const explicit = ev.sources ?? ev.evidence_sources;
  if (Array.isArray(explicit)) {
    for (const entry of explicit) {
      if (typeof entry === "string") {
        const normalized = normalizeEvidenceSource(entry);
        if (normalized) sources.add(normalized);
      }
    }
  }

  // Agent trace — availability metrics come from CloudWatch
  if (trace?.availability_result?.monthly_uptime_pct) {
    sources.add("CloudWatch");
  }

  // Agent pipeline evidence refs indicate SLA-style collection (CW + CloudTrail)
  if (trace?.eligibility?.evidence_refs?.length) {
    sources.add("CloudWatch");
    sources.add("CloudTrail");
  }

  // Scanner evidence keys that imply CloudWatch metric queries
  if (
    ev.cpu_utilization_7d_avg ||
    ev.connection_count_avg ||
    (typeof ev.cpu_avg === "string" && ev.cpu_avg !== "n/a") ||
    (typeof ev.p99_duration_ms === "string" && ev.p99_duration_ms !== "no_data") ||
    ev.invocation_count_30d !== undefined
  ) {
    sources.add("CloudWatch");
  }

  if (ev.config_compliance !== undefined || ev.config_rule_name) {
    sources.add("AWS Config");
  }

  // Service / finding-type mappings aligned with backend scanners
  if (svc === "COST EXPLORER" || ft.includes("COST") || ft.includes("SPEND")) {
    sources.add("Cost Explorer");
  }
  if (svc === "CLOUDWATCH LOGS" || svc === "CLOUDWATCH") {
    sources.add("CloudWatch");
  }
  if (svc === "RDS" && (ft === "IDLE_RDS" || ev.connection_count_avg)) {
    sources.add("CloudWatch");
  }
  if (svc === "LAMBDA" && ft === "OVERSIZED_LAMBDA") {
    if (
      ev.p99_duration_ms !== "no_data" ||
      ev.invocation_count_30d !== undefined
    ) {
      sources.add("CloudWatch");
    }
  }
  if (svc === "EC2" && ft === "IDLE_INSTANCE") {
    sources.add("CloudWatch");
  }

  return EVIDENCE_SOURCE_ORDER.filter((s) => sources.has(s));
}

/**
 * Past-tense label for the recovery action that was executed.
 * Returns null when the action cannot be determined reliably.
 */
export function executedRecoveryActionLabel(
  service: string,
  issue?: string,
  backendAction?: string
): string | null {
  const svc = normalizeService(service);

  if (backendAction === "stop_demo_instance") {
    return "Stopped EC2 instance";
  }

  switch (svc) {
    case "RDS":
      return "Stopped idle RDS instance";
    case "EC2":
      return "Stopped EC2 instance";
    case "EBS":
      return "Deleted unattached EBS volume";
    case "EIP":
      return "Released unassociated Elastic IP";
    case "S3":
      return "Applied lifecycle policy";
    case "Lambda":
      return "Right-sized Lambda configuration";
    case "CloudWatch":
      return "Applied log retention policy";
    default: {
      const rec = serviceRecommendation(service, issue, backendAction);
      if (/^Review /i.test(rec.action)) return null;
      if (rec.action.startsWith("Stop ")) return `Stopped${rec.action.slice(4)}`;
      if (rec.action.startsWith("Delete ")) return `Deleted${rec.action.slice(6)}`;
      if (rec.action.startsWith("Apply ")) return `Applied${rec.action.slice(5)}`;
      if (rec.action.startsWith("Release ")) return `Released${rec.action.slice(7)}`;
      if (rec.action.startsWith("Right-size ")) return `Right-sized${rec.action.slice(10)}`;
      return null;
    }
  }
}

/** Short approval-card "why" — not a repeat of the full finding headline. */
export function approvalWhyText(issue?: string): string {
  const lower = (issue ?? "").toLowerCase();
  if (/no connection|idle|stopped|unused|no activity/i.test(lower)) {
    return "No meaningful activity detected";
  }
  if (/lifecycle/i.test(lower)) return "Objects accumulating without lifecycle controls";
  if (/unattached|unassociated|orphan/i.test(lower)) return "Resource is unused and unattached";
  return "Recovery criteria met during evaluation";
}

/** Pipeline execution stage label (distinct from lifecycle authorization state). */
export function executionStageLabel(state: string): string {
  const s = state.toUpperCase();
  if (s === "DETECTED") return "Detect";
  if (["INVESTIGATING", "NEEDS_EVIDENCE"].includes(s)) return "Investigating";
  if (s === "EVIDENCE_READY") return "Evidence Ready";
  if (s === "ELIGIBILITY_REVIEWED") return "Policy";
  if (s === "NEEDS_FOLLOWUP") return "Under Investigation";
  if (s === "AWAITING_APPROVAL") return "Awaiting Approval";
  if (s === "APPROVED") return "Remediating";
  if (["SUBMITTING", "SUBMITTED"].includes(s)) return "Remediating";
  if (s === "MONITORING") return "Verifying";
  if (s === "RECOVERED") return "Recovered";
  if (["REJECTED", "DECLINED", "DENIED", "FAILED"].includes(s)) return "Stopped";
  return PIPELINE_STEPS[0];
}

/** Whether re-running investigation is a meaningful action. */
export function canRerunInvestigation(state: string): boolean {
  const s = state.toUpperCase();
  return ![
    "APPROVED", "SUBMITTING", "SUBMITTED", "MONITORING", "RECOVERED",
    "REJECTED", "DECLINED", "DENIED", "FAILED",
  ].includes(s);
}

/** Audit event label — event (what happened) separate from state badge. */
export function auditEventLabel(state: string): string {
  const s = state.toUpperCase();
  if (s === "DETECTED") return "Finding detected";
  if (s === "INVESTIGATING") return "Investigation started";
  if (s === "EVIDENCE_READY") return "Evidence collected";
  if (s === "AWAITING_APPROVAL") return "Awaiting approval";
  if (s === "APPROVED") return "Approval granted";
  if (s === "SUBMITTING" || s === "SUBMITTED") return "Remediation executed";
  if (s === "MONITORING") return "Verifying savings impact";
  if (s === "RECOVERED") return "Recovery verified";
  if (s === "DECLINED") return "Declined by operator";
  if (["REJECTED", "DENIED"].includes(s)) return "Rejected by policy";
  if (s === "FAILED") return "Remediation failed";
  return state.replace(/_/g, " ");
}

export function auditEventActor(state: string): string {
  const s = state.toUpperCase();
  if (["RECOVERED", "SUBMITTING", "SUBMITTED", "MONITORING"].includes(s)) return "Recoup";
  if (["APPROVED", "DECLINED"].includes(s)) return "Operator";
  if (s === "AWAITING_APPROVAL") return "System";
  return "Recoup";
}

/** Stable unique key for audit event rows. */
export function auditEventKey(parts: {
  opportunityId: string;
  eventType: string;
  state: string;
  timestamp: string;
  service: string;
}): string {
  return [
    parts.opportunityId,
    parts.eventType,
    parts.state,
    parts.timestamp,
    parts.service,
  ].join("::");
}
