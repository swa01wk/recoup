"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useRecoveryData } from "@/hooks/useRecoveryData";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { RecoveryLedger } from "@/components/ui/recovery-ledger";
import { AuditEventRow, AuditTableHeader, type AuditEvent } from "@/components/recoup/audit-event-row";
import {
  auditEventActor,
  auditEventKey,
  auditEventLabel,
} from "@/lib/service-presentation";

/** Dedupe opportunities by id — keeps the last entry per id. */
function dedupeOpportunities<T extends { id: string }>(opps: T[]): T[] {
  const byId = new Map<string, T>();
  for (const opp of opps) {
    if (opp.id) byId.set(opp.id, opp);
  }
  return Array.from(byId.values());
}

export default function RecoveryLedgerPage() {
  const { mergedOpportunities, promoted, ledgerData, loading, refresh } = useRecoveryData();

  const eventHistory = useMemo(() => {
    const promotedByOpp = new Map(promoted.map((p) => [p.opportunity_id, p]));
    const uniqueOpps = dedupeOpportunities(mergedOpportunities);
    const seenKeys = new Set<string>();
    const items: AuditEvent[] = [];

    for (const opp of uniqueOpps) {
      if (!opp.id) continue;

      const promo = promotedByOpp.get(opp.id);
      const service = String(opp.service ?? promo?.service ?? "Unknown");
      const state = opp.state.toUpperCase();
      // Stable timestamp — never Date.now() (would change on every render)
      const timestamp = promo?.promoted_at ?? `1970-01-01T00:00:00.000Z::${opp.id}`;

      const event: AuditEvent = {
        key: auditEventKey({
          opportunityId: opp.id,
          eventType: "lifecycle_state",
          state,
          timestamp,
          service,
        }),
        opportunityId: opp.id,
        eventType: "lifecycle_state",
        timestamp,
        service,
        event: auditEventLabel(state),
        amount:
          parseFloat(opp.potential_value ?? "0") ||
          promo?.estimated_monthly_savings_usd ||
          0,
        actor: auditEventActor(state),
        state: opp.state,
        href: `/opportunities/${opp.id}`,
      };

      if (seenKeys.has(event.key)) continue;
      seenKeys.add(event.key);
      items.push(event);
    }

    return items.sort((a, b) => {
      const tDiff = new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
      if (tDiff !== 0) return tDiff;
      return a.opportunityId.localeCompare(b.opportunityId);
    });
  }, [promoted, mergedOpportunities]);

  return (
    <div className="flex flex-col min-h-screen p-6 space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold text-slate-100">Recovery Ledger</h1>
          <p className="text-sm text-slate-400 mt-1">
            Immutable financial and audit history of all recovery events
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={() => void refresh()}>
            Refresh
          </Button>
          <Link href="/opportunities">
            <Button variant="secondary" size="sm">← Opportunities</Button>
          </Link>
        </div>
      </div>

      <RecoveryLedger data={ledgerData} variant="ledger" compact />

      <Card className="overflow-hidden">
        <CardHeader>
          <CardTitle>Audit History</CardTitle>
          <span className="text-xs text-slate-500">
            Event = what happened · Status = current lifecycle state
          </span>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <p className="text-sm text-slate-500 py-8 text-center">Loading audit history…</p>
          ) : eventHistory.length === 0 ? (
            <p className="text-sm text-slate-500 py-8 text-center">
              No events yet. Start from the Account Scanner.
            </p>
          ) : (
            <>
              <AuditTableHeader />
              <div>
                {eventHistory.map((event) => (
                  <AuditEventRow key={event.key} event={event} />
                ))}
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
