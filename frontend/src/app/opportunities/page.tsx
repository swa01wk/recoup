"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type Finding } from "@/lib/api";
import { useRecoveryData } from "@/hooks/useRecoveryData";
import { type LocalScanEntry } from "@/lib/recovery-storage";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { RecoveryLedger } from "@/components/ui/recovery-ledger";
import {
  OpportunityRow,
  OpportunityTableHeader,
  type OpportunityRowData,
} from "@/components/recoup/opportunity-row";
import { fmtSavings, formatLifecycleLabel, severityToRisk } from "@/lib/recoup-ui-rules";
import { requestRecoveryDataRefresh } from "@/lib/recovery-data-events";

function fmtDateShort(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

type FilterState = {
  service: string;
  status: string;
  risk: string;
  region: string;
  sortBy: "savings" | "service" | "status" | "priority";
};

function buildOpportunityRows(
  findings: Finding[],
  promotedMap: Map<string, string>,
  opportunityStateMap: Map<string, string>,
  opportunityMetaMap: Map<
    string,
    {
      service: string | null;
      region: string | null;
      priority_score?: number | null;
      evidence_sufficiency?: string | null;
      risk_level?: string | null;
    }
  >
): OpportunityRowData[] {
  const seen = new Set<string>();
  const rows: OpportunityRowData[] = [];

  for (const f of findings) {
    if (seen.has(f.resource_id)) continue;
    seen.add(f.resource_id);

    const opportunityId = promotedMap.get(f.resource_id);
    const state = opportunityId
      ? (opportunityStateMap.get(opportunityId) ?? "INVESTIGATING")
      : "DETECTED";
    const meta = opportunityId ? opportunityMetaMap.get(opportunityId) : null;

    rows.push({
      resourceId: f.resource_id,
      service: meta?.service ?? f.service,
      region: meta?.region ?? undefined,
      issue: f.issue,
      savings: f.estimated_monthly_savings_usd,
      severity: f.severity,
      state,
      opportunityId,
      priorityScore: meta?.priority_score ?? undefined,
      evidenceSufficiency: meta?.evidence_sufficiency ?? undefined,
      apiRiskLevel: meta?.risk_level ?? undefined,
    });
  }

  return rows;
}

function ScanHistoryPanel({
  history,
  promotedMap,
  opportunityStateMap,
  snsStatusMap,
  onStartRecovery,
  promotingId,
}: {
  history: LocalScanEntry[];
  promotedMap: Map<string, string>;
  opportunityStateMap: Map<string, string>;
  snsStatusMap: Map<string, { sent: boolean; sentAt: string | null }>;
  onStartRecovery: (f: Finding) => void;
  promotingId: string | null;
}) {
  const [expanded, setExpanded] = useState(false);

  if (history.length === 0) return null;

  return (
    <div className="rounded-xl border border-slate-800/60 bg-slate-900/10 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 text-xs text-slate-500 hover:text-slate-300 transition-colors"
      >
        <span className="flex items-center gap-2">
          Scan History
          <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] text-slate-500">
            {history.length} scan{history.length !== 1 ? "s" : ""}
          </span>
        </span>
        <span>{expanded ? "▲" : "▼"}</span>
      </button>
      {expanded && (
        <div className="border-t border-slate-800/60 divide-y divide-slate-800/40">
          {history.map((entry, idx) => (
            <div key={entry.scan_id ?? idx} className="px-4 py-3 text-xs space-y-1">
              <div className="flex items-center gap-3 flex-wrap text-slate-400">
                <span>{fmtDateShort(entry.scanned_at)}</span>
                <span className="font-mono text-emerald-400">{fmtSavings(entry.total_savings_usd)}</span>
                <span>{entry.finding_count} findings</span>
                {entry.is_cached && (
                  <span className="text-amber-500">Cached</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function OpportunitiesPage() {
  const router = useRouter();
  const {
    mergedOpportunities,
    promoted,
    findings,
    scanTotal,
    loading,
    refresh,
    isCached,
    scanHistory,
    ledgerData,
  } = useRecoveryData();

  const [promotingId, setPromotingId] = useState<string | null>(null);
  const [promoteError, setPromoteError] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterState>({
    service: "all",
    status: "all",
    risk: "all",
    region: "all",
    sortBy: "savings",
  });

  const promotedMap = useMemo(
    () => new Map(promoted.map((p) => [p.resource_id, p.opportunity_id])),
    [promoted]
  );
  const opportunityStateMap = useMemo(
    () => new Map(mergedOpportunities.map((o) => [o.id, o.state])),
    [mergedOpportunities]
  );
  const opportunityMetaMap = useMemo(
    () =>
      new Map(
        mergedOpportunities.map((o) => [
          o.id,
          {
            service: o.service,
            region: o.region,
            priority_score: o.priority_score,
            evidence_sufficiency: o.evidence_sufficiency,
            risk_level: o.risk_level,
          },
        ])
      ),
    [mergedOpportunities]
  );

  const allRows = useMemo(
    () => buildOpportunityRows(findings, promotedMap, opportunityStateMap, opportunityMetaMap),
    [findings, promotedMap, opportunityStateMap, opportunityMetaMap]
  );

  const serviceOptions = useMemo(
    () => ["all", ...Array.from(new Set(allRows.map((r) => r.service))).sort()],
    [allRows]
  );
  const regionOptions = useMemo(
    () => ["all", ...Array.from(new Set(allRows.map((r) => r.region).filter(Boolean) as string[])).sort()],
    [allRows]
  );

  const filteredRows = useMemo(() => {
    let rows = allRows.filter((r) => {
      if (filters.service !== "all" && r.service !== filters.service) return false;
      if (filters.status !== "all" && formatLifecycleLabel(r.state) !== filters.status) return false;
      if (filters.risk !== "all" && severityToRisk(r.severity) !== filters.risk) return false;
      if (filters.region !== "all" && r.region !== filters.region) return false;
      return true;
    });

    if (filters.sortBy === "priority") {
      rows = [...rows].sort(
        (a, b) => (b.priorityScore ?? 0) - (a.priorityScore ?? 0) || b.savings - a.savings
      );
    } else if (filters.sortBy === "savings") {
      rows = [...rows].sort((a, b) => b.savings - a.savings);
    } else if (filters.sortBy === "service") {
      rows = [...rows].sort((a, b) => a.service.localeCompare(b.service));
    } else {
      rows = [...rows].sort((a, b) => formatLifecycleLabel(a.state).localeCompare(formatLifecycleLabel(b.state)));
    }
    return rows;
  }, [allRows, filters]);

  const statusOptions = useMemo(
    () => ["all", ...Array.from(new Set(allRows.map((r) => formatLifecycleLabel(r.state)))).sort()],
    [allRows]
  );

  const handleStartRecovery = async (finding: Finding) => {
    setPromotingId(finding.resource_id);
    setPromoteError(null);
    try {
      const res = await api.scan.promote(finding);
      requestRecoveryDataRefresh();
      router.push(`/opportunities/${res.opportunity_id}`);
    } catch (e) {
      setPromoteError(e instanceof Error ? e.message : "Failed to start recovery");
      setPromotingId(null);
    }
  };

  const hasAnyFindings = findings.length > 0 || mergedOpportunities.length > 0 || promoted.length > 0;

  return (
    <div className="flex flex-col min-h-screen p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold text-slate-100">Opportunities</h1>
          <p className="text-sm text-slate-400 mt-1">
            Recoverable spend identified from your AWS account
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={() => void refresh()}>
            Refresh
          </Button>
          <Link href="/scan">
            <Button variant="secondary" size="sm">New Scan</Button>
          </Link>
        </div>
      </div>

      {/* Recovery Summary */}
      {(hasAnyFindings || scanTotal > 0) && (
        <div className="space-y-1">
          <RecoveryLedger data={ledgerData} compact variant="summary" />
          <p className="text-[10px] text-slate-600 px-1">
            Remaining + Pending Approval + Recovered = Potential Savings · same scope on Ledger page
          </p>
        </div>
      )}

      {/* Cached notice */}
      {isCached && (
        <div className="rounded-lg border border-amber-600/30 bg-amber-950/10 px-4 py-3 flex items-start gap-3">
          <span className="text-amber-400">⟳</span>
          <div>
            <p className="text-sm font-medium text-amber-200">Rescan complete — no new resources found</p>
            <p className="text-xs text-slate-400 mt-0.5">
              Showing cached results.{" "}
              <Link href="/scan" className="text-blue-400 underline underline-offset-2">Run a new scan</Link>
              {" "}if your infrastructure changed.
            </p>
          </div>
        </div>
      )}

      {/* Filters + Opportunity list */}
      {allRows.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-3 flex-wrap">
            <select
              value={filters.service}
              onChange={(e) => setFilters((f) => ({ ...f, service: e.target.value }))}
              className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-300 focus:border-blue-500 focus:outline-none"
            >
              {serviceOptions.map((s) => (
                <option key={s} value={s}>{s === "all" ? "All Services" : s}</option>
              ))}
            </select>
            <select
              value={filters.status}
              onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}
              className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-300 focus:border-blue-500 focus:outline-none"
            >
              {statusOptions.map((s) => (
                <option key={s} value={s}>{s === "all" ? "All Statuses" : s}</option>
              ))}
            </select>
            <select
              value={filters.risk}
              onChange={(e) => setFilters((f) => ({ ...f, risk: e.target.value }))}
              className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-300 focus:border-blue-500 focus:outline-none"
            >
              <option value="all">All Risk</option>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
              <option value="Low">Low</option>
            </select>
            {regionOptions.length > 1 && (
              <select
                value={filters.region}
                onChange={(e) => setFilters((f) => ({ ...f, region: e.target.value }))}
                className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-300 focus:border-blue-500 focus:outline-none"
              >
                {regionOptions.map((r) => (
                  <option key={r} value={r}>{r === "all" ? "All Regions" : r}</option>
                ))}
              </select>
            )}
            <select
              value={filters.sortBy}
              onChange={(e) => setFilters((f) => ({ ...f, sortBy: e.target.value as FilterState["sortBy"] }))}
              className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-300 focus:border-blue-500 focus:outline-none ml-auto"
            >
              <option value="savings">Highest Savings</option>
              <option value="service">Service</option>
              <option value="status">Status</option>
            </select>
          </div>

          <Card className="overflow-hidden">
            <OpportunityTableHeader />
            <div>
              {filteredRows.map((row) => {
                const finding = findings.find((f) => f.resource_id === row.resourceId);
                return (
                  <OpportunityRow
                    key={row.resourceId}
                    data={row}
                    loading={promotingId === row.resourceId}
                    onStartRecovery={
                      finding && !row.opportunityId
                        ? () => void handleStartRecovery(finding)
                        : undefined
                    }
                  />
                );
              })}
              {filteredRows.length === 0 && (
                <p className="text-sm text-slate-500 py-8 text-center">No opportunities match these filters.</p>
              )}
            </div>
          </Card>
        </div>
      )}

      {promoteError && (
        <div className="rounded-lg border border-red-500/30 bg-red-900/20 p-3 text-sm text-red-300">
          {promoteError}
        </div>
      )}

      {/* Scan History — secondary, collapsed */}
      <ScanHistoryPanel
        history={scanHistory}
        promotedMap={promotedMap}
        opportunityStateMap={opportunityStateMap}
        snsStatusMap={new Map()}
        onStartRecovery={(f) => void handleStartRecovery(f)}
        promotingId={promotingId}
      />

      {/* Empty state */}
      {!loading && !hasAnyFindings && scanHistory.length === 0 && (
        <Card>
          <CardContent className="py-16 text-center space-y-4">
            <p className="text-slate-400">No recoverable opportunities yet</p>
            <p className="text-xs text-slate-500">
              Scan your AWS account to discover idle resources and cost-saving actions.
            </p>
            <Link href="/scan">
              <Button variant="primary" size="md">Go to Account Scanner</Button>
            </Link>
          </CardContent>
        </Card>
      )}

      {loading && scanHistory.length === 0 && allRows.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-slate-500 text-sm">Loading opportunities…</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
