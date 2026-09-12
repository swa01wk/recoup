import { toCanonicalLifecycle } from "./recovery-storage";

export interface RecoveryLedgerData {
  detected: number;
  totalDetected: number;
  recovered: number;
  pending: number;
}

type LedgerOpportunity = { id?: string; state: string; potential_value: string | null };
type LedgerPendingApproval = { opportunity_id?: string; amount: string };

function roundUsd(n: number): number {
  return Math.round((n + Number.EPSILON) * 100) / 100;
}

function parseUsd(raw: string | null | undefined): number {
  const n = parseFloat(raw ?? "0");
  return isNaN(n) || n <= 0 ? 0 : roundUsd(n);
}

function ledgerStatePriority(state: string): number {
  const c = toCanonicalLifecycle(state);
  if (c === "RECOVERED") return 3;
  if (c === "PENDING") return 2;
  return 1;
}

function dedupeOpportunitiesForLedger(opportunities: LedgerOpportunity[]): LedgerOpportunity[] {
  const withoutId: LedgerOpportunity[] = [];
  const byId = new Map<string, LedgerOpportunity>();

  for (const opp of opportunities) {
    if (!opp.id) {
      withoutId.push(opp);
      continue;
    }
    const prev = byId.get(opp.id);
    if (!prev || ledgerStatePriority(opp.state) >= ledgerStatePriority(prev.state)) {
      byId.set(opp.id, opp);
    }
  }

  return [...byId.values(), ...withoutId];
}

function isTerminalNegativeOpportunityState(state: string): boolean {
  return ["REJECTED", "FAILED", "DECLINED", "DENIED"].includes(state.toUpperCase());
}

/**
 * Compute Recovery Summary / Ledger buckets.
 * Remaining + Pending + Recovered = Potential Savings (per scan scope).
 */
export function computeLedgerData(
  scanTotal: number,
  opportunities: LedgerOpportunity[],
  pendingApprovals: LedgerPendingApproval[] = []
): RecoveryLedgerData {
  let recovered = 0;
  let pendingFromOpps = 0;
  const pendingOppIds = new Set<string>();
  const deduped = dedupeOpportunitiesForLedger(opportunities);
  const oppById = new Map(deduped.filter((o) => o.id).map((o) => [o.id!, o]));

  for (const opp of deduped) {
    const value = parseUsd(opp.potential_value);
    if (value <= 0) continue;

    const canonical = toCanonicalLifecycle(opp.state);

    if (canonical === "RECOVERED") {
      recovered += value;
    } else if (canonical === "PENDING") {
      pendingFromOpps += value;
      if (opp.id) pendingOppIds.add(opp.id);
    }
  }

  recovered = roundUsd(recovered);
  pendingFromOpps = roundUsd(pendingFromOpps);

  let pendingFromApprovals = 0;
  for (const row of pendingApprovals) {
    const oid = row.opportunity_id;
    if (oid && pendingOppIds.has(oid)) continue;
    const linked = oid ? oppById.get(oid) : undefined;
    if (linked) {
      if (toCanonicalLifecycle(linked.state) === "RECOVERED") continue;
      if (isTerminalNegativeOpportunityState(linked.state)) continue;
    }
    pendingFromApprovals += parseUsd(row.amount);
  }
  pendingFromApprovals = roundUsd(pendingFromApprovals);

  const pending = roundUsd(pendingFromOpps + pendingFromApprovals);
  const total = Math.max(roundUsd(scanTotal), roundUsd(recovered + pending));
  const detected = Math.max(0, roundUsd(total - recovered - pending));

  return { detected, totalDetected: total, recovered, pending };
}
