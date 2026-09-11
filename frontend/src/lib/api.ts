const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Opportunity {
  id: string;
  state: string;
  state_version: number;
  potential_value: string | null;
  confidence: number | null;
  service: string | null;
  region: string | null;
}

export interface TraceResult {
  opportunity_id: string;
  signal: Record<string, unknown> | null;
  hypothesis_summary: string | null;
  contract: { service: string; version: string } | null;
  availability_result: {
    monthly_uptime_pct: string;
    threshold_breached: boolean;
    tier_pct: string;
    billed_charges: string;
    potential_credit: string;
    calculation_trace: string[];
  } | null;
  eligibility: {
    eligible_estimate?: boolean;
    is_eligible?: boolean;
    confidence: number;
    reasons?: string[];
    satisfied_requirements?: string[];
    evidence_refs?: string[];
  } | null;
  policy_decision: string | null;
  case_id: string | null;
  case_outcome: Record<string, unknown> | null;
  errors: string[];
}

export interface ApprovalRecord {
  approval_id: string;
  opportunity_id: string;
  action: string;
  state: string;
  amount: string;
  claim_hash: string;
  state_version: number;
  requested_at: string;
  expires_at: string | null;
  decided_by: string | null;
  notes: string | null;
  risk_tier?: string;
  action_description?: string;
  rollback_context?: string;
}

/** Response from POST /api/opportunities/{id}/run (optional agent graph; not the removed /api/replay HTTP). */
export interface RunResult {
  opportunity_id: string;
  scenario_id: string;
  live_evidence: boolean;
  evidence_s3_uris: string[];
  evidence_bucket: string;
  monthly_uptime_pct: string | null;
  threshold_breached: boolean | null;
  tier_pct: string | null;
  billed_charges: string | null;
  potential_credit: string | null;
  calculation_trace: string[];
  policy_decision: string | null;
  case_id: string | null;
  errors: string[];
  sse_url: string;
}

export interface SseEvent {
  type:
    | "node_started"
    | "node_completed"
    | "approval_required"
    | "opportunity_done"
    | "error";
  node?: string;
  duration_ms?: number;
  potential_credit?: string;
  amount?: string;
  opportunity_id?: string;
  state?: string;
  policy_decision?: string;
  errors?: string[];
  message?: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${text}`);
  }
  return res.json() as Promise<T>;
}

export interface Finding {
  service: string;
  resource_id: string;
  resource_type: string;
  issue: string;
  estimated_monthly_savings_usd: number;
  recommendation: string;
  severity: "high" | "medium" | "low";
  region: string;
  // Phase 6f — per-finding evidence + demo workload metadata
  evidence: Record<string, unknown>;
  finding_type?: string | null;
  scenario_tag?: string | null;
  is_demo_resource?: boolean;
}

// Phase 6e: raw access keys replaced with STS AssumeRole connection
export interface ScanRequest {
  role_arn: string;
  external_id: string;
  region: string;
  regions?: string[];
}

export interface PromoteResponse {
  opportunity_id: string;
  status: string;
  resource_id: string;
}

export interface PromotedFindingRecord {
  opportunity_id: string;
  resource_id: string;
  service: string;
  estimated_monthly_savings_usd: number;
  severity: string;
  scenario_tag?: string | null;
  promoted_at: string;
}

export interface RecoveryLedgerSummary {
  detected: number;
  approved: number;
  recovered: number;
  pending: number;
}

export interface ScanResult {
  scanned_at: string;
  account_id: string | null;
  region: string;
  findings: Finding[];
  total_estimated_monthly_savings_usd: number;
  errors: string[];
  scan_duration_seconds: number;
  // Phase 6e — STS AssumeRole provenance
  assumed_role_arn?: string | null;
  assumed_role_account_id?: string | null;
  session_name?: string | null;
  // Phase 6f — pre-grouped findings for multi-service display
  findings_by_service?: Record<string, Finding[]>;
  // Scan dedup / history
  scan_id?: string | null;
  scan_hash?: string | null;
  /** True when rescan produced the same findings — previous results are served */
  is_cached?: boolean;
}

export interface ScanHistoryEntry {
  scan_id: string | null;
  scanned_at: string;
  scan_hash: string | null;
  region: string;
  finding_count: number;
  total_savings_usd: number;
  is_cached: boolean;
  findings_by_service: Record<string, number>;
}

export const api = {
  opportunities: {
    list: () => request<Opportunity[]>("/api/opportunities"),
    get: (id: string) => request<Opportunity>(`/api/opportunities/${id}`),
    run: (id: string, signal?: Record<string, unknown>) =>
      request<RunResult>(`/api/opportunities/${id}/run`, {
        method: "POST",
        body: JSON.stringify({ signal }),
      }),
    trace: (id: string) => request<TraceResult>(`/api/opportunities/${id}/trace`),
    streamUrl: (id: string) => `${BASE}/api/opportunities/${id}/stream`,
  },
  approvals: {
    listPending: () => request<ApprovalRecord[]>("/api/approvals/pending"),
    forOpportunity: (id: string) =>
      request<ApprovalRecord | null>(`/api/approvals/opportunity/${id}`),
    approve: (
      id: string,
      body: {
        principal: string;
        claim_hash: string;
        amount: string;
        state_version: number;
        notes?: string;
      }
    ) =>
      request<ApprovalRecord>(`/api/approvals/opportunity/${id}/approve`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    decline: (
      id: string,
      body: { principal: string; notes?: string }
    ) =>
      request<ApprovalRecord>(`/api/approvals/opportunity/${id}/decline`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    investigate: (
      id: string,
      body: { principal: string; notes?: string }
    ) =>
      request<{ approval_id: string; state: string; opportunity_state: string }>(
        `/api/approvals/opportunity/${id}/investigate`,
        {
          method: "POST",
          body: JSON.stringify(body),
        }
      ),
    purgeStale: () =>
      request<{ revoked: number; live_opportunities: number; message: string }>(
        "/api/approvals/purge-stale",
        { method: "POST" }
      ),
    listOutcomes: () =>
      request<
        Array<{
          opportunity_id?: string;
          pk?: string;
          credit_amount: string;
          action_taken?: string;
          outcome_state: string;
          created_at?: string;
          recovered_at: string | null;
          sns_sent?: boolean;
          sns_sent_at?: string | null;
        }>
      >("/api/approvals/outcomes"),
  },
  scan: {
    full: (req: ScanRequest) =>
      request<ScanResult>("/api/scan/full", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    preview: (req: ScanRequest) =>
      request<ScanResult>("/api/scan/preview", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    demo: () =>
      request<ScanResult>("/api/scan/demo", {
        method: "POST",
      }),
    last: () => request<ScanResult>("/api/scan/last"),
    promote: (finding: Finding) =>
      request<PromoteResponse>("/api/scan/findings/promote", {
        method: "POST",
        body: JSON.stringify(finding),
      }),
    listPromoted: () =>
      request<PromotedFindingRecord[]>("/api/scan/findings/promoted"),
    audit: () => request<Record<string, unknown>[]>("/api/scan/audit"),
    history: (accountId?: string) =>
      request<ScanHistoryEntry[]>(
        `/api/scan/history${accountId ? `?account_id=${accountId}` : ""}`
      ),
    /**
     * Full demo reset — clears all opportunities, approvals, promoted findings, audit log.
     * Pass clearScanCache=true to also clear the cached scan result (next scan hits AWS).
     */
    adminReset: (clearScanCache = false) =>
      request<{ status: string; cleared: string }>(
        `/api/admin/reset${clearScanCache ? "?clear_scan_cache=true" : ""}`,
        { method: "POST" }
      ),
    // Sprint 1: per-customer ExternalId generation
    initConnection: () =>
      request<{
        customer_id: string;
        external_id: string;
        created_at: string;
        cf_template_hint: string;
      }>("/api/scan/connect/init", { method: "POST" }),
  },
};
