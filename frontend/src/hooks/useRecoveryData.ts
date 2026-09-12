"use client";

import { useCallback, useEffect, useMemo, useState, startTransition } from "react";
import {
  api,
  type ApprovalRecord,
  type Finding,
  type Opportunity,
  type PromotedFindingRecord,
} from "@/lib/api";
import { loadLastScan, loadScanHistory, type LocalScanEntry } from "@/lib/recovery-storage";
import { RECOVERY_DATA_REFRESH_EVENT } from "@/lib/recovery-data-events";
import { computeLedgerData, type RecoveryLedgerData } from "@/lib/recovery-ledger-math";

type OutcomeRecord = {
  opportunity_id?: string;
  pk?: string;
  credit_amount: string;
  outcome_state: string;
  sns_sent?: boolean;
  sns_sent_at?: string | null;
};

/** Derive opportunity_id from pk when DynamoDB records omit the field. */
function normalizeOutcomeId(outcome: OutcomeRecord): string | undefined {
  if (outcome.opportunity_id) return outcome.opportunity_id;
  const pk = outcome.pk;
  if (pk?.startsWith("outcome#")) return pk.slice("outcome#".length);
  return undefined;
}

export interface RecoveryData {
  /** All live opportunities from the backend, with outcome states merged in */
  mergedOpportunities: Opportunity[];
  /** Pending HITL approval records */
  pending: ApprovalRecord[];
  /** Promoted scan findings (resource_id → opportunity_id mapping) */
  promoted: PromotedFindingRecord[];
  /** Raw scan findings from localStorage */
  findings: Finding[];
  /** Total scan savings from the last scan */
  scanTotal: number;
  /** Pre-computed ledger bucket data (Detected / Pending / Approved / Recovered) */
  ledgerData: RecoveryLedgerData;
  /** Total monetary value of pending approvals */
  pendingAmount: number;
  /** Whether the initial load is in progress */
  loading: boolean;
  /** Error message, if any */
  error: string | null;
  /** Trigger a manual refresh */
  refresh: () => void;
  /** True if the last scan returned cached results (no new AWS resources found) */
  isCached: boolean;
  /** Unique ID of the last scan run */
  lastScanId: string | null;
  /** Timestamp of the last scan */
  lastScannedAt: string | null;
  /** Per-scan history (newest first, from localStorage) */
  scanHistory: LocalScanEntry[];
  /** Map of opportunity_id → SNS notification status */
  snsStatusMap: Map<string, { sent: boolean; sentAt: string | null }>;
}

/**
 * Shared hook that is the single source of truth for all opportunity data.
 *
 * Consumed by: Recovery Dashboard, Recovery Ledger, and any other page that
 * needs to display opportunity state. Both pages receive the exact same merged
 * dataset — eliminating Dashboard/Ledger discrepancies.
 */
export function useRecoveryData(pollIntervalMs = 10_000): RecoveryData {
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [pending, setPending] = useState<ApprovalRecord[]>([]);
  const [promoted, setPromoted] = useState<PromotedFindingRecord[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [scanTotal, setScanTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [outcomes, setOutcomes] = useState<OutcomeRecord[]>([]);
  const [isCached, setIsCached] = useState(false);
  const [lastScanId, setLastScanId] = useState<string | null>(null);
  const [lastScannedAt, setLastScannedAt] = useState<string | null>(null);
  const [scanHistory, setScanHistory] = useState<LocalScanEntry[]>([]);

  const refresh = useCallback(async () => {
    try {
      const [opps, approvals, promotedList, outcomeList] = await Promise.all([
        api.opportunities.list().catch(() => [] as Opportunity[]),
        api.approvals.listPending().catch(() => [] as ApprovalRecord[]),
        api.scan.listPromoted().catch(() => [] as PromotedFindingRecord[]),
        api.approvals.listOutcomes().catch(() => [] as OutcomeRecord[]),
      ]);

      const lastScan = loadLastScan();
      setOpportunities(opps);
      setPending(approvals);
      setPromoted(promotedList);
      setOutcomes(outcomeList);
      setFindings(lastScan?.findings ?? []);
      setScanTotal(lastScan?.total_estimated_monthly_savings_usd ?? 0);
      setIsCached(lastScan?.is_cached ?? false);
      setLastScanId(lastScan?.scan_id ?? null);
      setLastScannedAt(lastScan?.scanned_at ?? null);
      setScanHistory(loadScanHistory());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    startTransition(() => { void refresh(); });
    const id = setInterval(() => startTransition(() => void refresh()), pollIntervalMs);
    return () => clearInterval(id);
  }, [refresh, pollIntervalMs]);

  useEffect(() => {
    const onRefresh = () => {
      startTransition(() => { void refresh(); });
    };
    window.addEventListener(RECOVERY_DATA_REFRESH_EVENT, onRefresh);
    return () => window.removeEventListener(RECOVERY_DATA_REFRESH_EVENT, onRefresh);
  }, [refresh]);

  // Merge outcome records into opportunities so RECOVERED state persists
  // across server restarts (outcomes stored in DynamoDB / in-memory).
  const mergedOpportunities = useMemo(() => {
    const outcomeMap = new Map<string, string>();
    for (const outcome of outcomes) {
      const id = normalizeOutcomeId(outcome);
      if (id) outcomeMap.set(id, outcome.outcome_state);
    }

    const merged = opportunities.map((opp) => ({
      ...opp,
      state: outcomeMap.get(opp.id) === "RECOVERED" ? "RECOVERED" : opp.state,
    }));

    // Add outcome-only records (opportunities from a prior session)
    const liveIds = new Set(opportunities.map((o) => o.id));
    for (const outcome of outcomes) {
      const id = normalizeOutcomeId(outcome);
      if (!id || liveIds.has(id) || outcome.outcome_state !== "RECOVERED") continue;
      merged.push({
        id,
        state: "RECOVERED",
        state_version: 0,
        potential_value: outcome.credit_amount,
        confidence: null,
        service: null,
        region: null,
      });
    }

    // Dedupe by id — prevents double-counting when outcome and live opp overlap
    const byId = new Map<string, (typeof merged)[number]>();
    for (const opp of merged) {
      if (opp.id) byId.set(opp.id, opp);
    }
    return Array.from(byId.values());
  }, [opportunities, outcomes]);

  const ledgerData = useMemo(
    () =>
      computeLedgerData(
        scanTotal,
        mergedOpportunities,
        pending.map((r) => ({
          opportunity_id: r.opportunity_id,
          amount: r.amount,
        }))
      ),
    [scanTotal, mergedOpportunities, pending]
  );

  const pendingAmount = ledgerData.pending;

  const snsStatusMap = useMemo(() => {
    const map = new Map<string, { sent: boolean; sentAt: string | null }>();
    for (const outcome of outcomes) {
      if (outcome.sns_sent === undefined) continue;
      const id = normalizeOutcomeId(outcome);
      if (!id) continue;
      map.set(id, { sent: outcome.sns_sent ?? false, sentAt: outcome.sns_sent_at ?? null });
    }
    return map;
  }, [outcomes]);

  return {
    mergedOpportunities,
    pending,
    promoted,
    findings,
    scanTotal,
    ledgerData,
    pendingAmount,
    loading,
    error,
    refresh,
    isCached,
    lastScanId,
    lastScannedAt,
    scanHistory,
    snsStatusMap,
  };
}
