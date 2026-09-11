"use client";

import { useEffect, useState, useRef, useCallback, startTransition } from "react";
import { use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  api,
  type TraceResult,
  type ApprovalRecord,
  type SseEvent,
  type Opportunity,
  type Finding,
} from "@/lib/api";
import { loadLastScan } from "@/lib/recovery-storage";
import { useRole } from "@/hooks/useRole";
import { fallbackApprovalContext } from "@/lib/competitive-ui";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { pipelineStageForOpportunity } from "@/lib/recovery-storage";
import {
  fmtSavings,
  fmtYearlySavings,
  formatLifecycleLabel,
} from "@/lib/recoup-ui-rules";
import {
  serviceFindingSummary,
  serviceRecommendation,
  serviceRollback,
  deriveConciseEvidence,
  deriveEvidenceSources,
  executedRecoveryActionLabel,
  approvalWhyText,
  executionStageLabel,
  canRerunInvestigation,
} from "@/lib/service-presentation";
import { EvidenceSourceChips } from "@/components/recoup/evidence-source-chips";
import { StatusBadge } from "@/components/recoup/status-badge";
import { MetricCard } from "@/components/recoup/metric-card";
import { EvidenceList } from "@/components/recoup/evidence-list";
import { RiskIndicator } from "@/components/recoup/risk-indicator";
import { ConfidenceIndicator } from "@/components/recoup/confidence-indicator";
import { LifecycleStepper } from "@/components/recoup/lifecycle-stepper";
import { DecisionCard } from "@/components/recoup/decision-card";
import { RecoveryVerifiedHero } from "@/components/recoup/recovery-verified-hero";
import { TechnicalDetails } from "@/components/recoup/technical-details";
import { serviceIcon, truncateResourceId } from "@/components/recoup/service-icons";

function nodeToPipelineStage(node: string): number {
  if (["normalize_event"].includes(node)) return 2;
  if (["incident_correlation", "sla_contract_resolver"].includes(node)) return 3;
  if (["availability_calculator", "evidence_collector", "evidence_sanitizer"].includes(node)) return 5;
  if (["eligibility_reasoner", "risk_policy_gate"].includes(node)) return 7;
  if (["claim_package_generator", "submission_adapter", "case_monitor"].includes(node)) return 8;
  return 2;
}

export default function OpportunityPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { principal } = useRole();
  const router = useRouter();

  const [trace, setTrace] = useState<TraceResult | null>(null);
  const [opportunity, setOpportunity] = useState<Opportunity | null>(null);
  const [approval, setApproval] = useState<ApprovalRecord | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [streamDone, setStreamDone] = useState(false);
  const [livePipelineStage, setLivePipelineStage] = useState<number | null>(null);
  const [approvalLoading, setApprovalLoading] = useState(false);
  const [approvalMsg, setApprovalMsg] = useState<string | null>(null);
  const [finding, setFinding] = useState<Finding | null>(null);
  const [verifiedAt, setVerifiedAt] = useState<string | null>(null);
  const [outcomeRecovered, setOutcomeRecovered] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  function outcomeOpportunityId(outcome: {
    opportunity_id?: string;
    pk?: string;
  }): string | undefined {
    if (outcome.opportunity_id) return outcome.opportunity_id;
    if (outcome.pk?.startsWith("outcome#")) return outcome.pk.slice("outcome#".length);
    return undefined;
  }

  const loadData = useCallback(async () => {
    try {
      setTrace(await api.opportunities.trace(id));
    } catch { /* trace not ready */ }
    try {
      setApproval(await api.approvals.forOpportunity(id));
    } catch { /* no approval yet */ }
    try {
      setOpportunity(await api.opportunities.get(id));
    } catch { /* opportunity may not exist */ }
    try {
      const promoted = await api.scan.listPromoted();
      const promo = promoted.find((p) => p.opportunity_id === id);
      if (promo) {
        const scan = loadLastScan();
        const match = scan?.findings.find((f) => f.resource_id === promo.resource_id) ?? null;
        setFinding(match);
      } else {
        setFinding(null);
      }
    } catch {
      setFinding(null);
    }
    try {
      const outcomes = await api.approvals.listOutcomes();
      const outcome = outcomes.find((o) => outcomeOpportunityId(o) === id);
      setVerifiedAt(outcome?.recovered_at ?? null);
      setOutcomeRecovered(outcome?.outcome_state === "RECOVERED");
    } catch {
      setVerifiedAt(null);
      setOutcomeRecovered(false);
    }
  }, [id]);

  useEffect(() => {
    startTransition(() => { void loadData(); });
  }, [loadData]);

  const rawOppState = opportunity?.state?.toUpperCase() ?? "DETECTED";
  const oppState = outcomeRecovered ? "RECOVERED" : rawOppState;
  const isRemediating =
    !outcomeRecovered &&
    ["APPROVED", "SUBMITTING", "SUBMITTED", "MONITORING"].includes(rawOppState);

  useEffect(() => {
    if (!isRemediating) return;
    const pollId = setInterval(() => startTransition(() => void loadData()), 5000);
    return () => clearInterval(pollId);
  }, [isRemediating, loadData]);

  const startStream = useCallback(() => {
    esRef.current?.close();
    setStreamDone(false);
    setStreaming(true);
    setApprovalMsg(null);
    setLivePipelineStage(2);

    const es = new EventSource(api.opportunities.streamUrl(id));
    esRef.current = es;

    es.onmessage = (ev: MessageEvent) => {
      const event = JSON.parse(ev.data as string) as SseEvent;
      if ((event.type === "node_started" || event.type === "node_completed") && event.node) {
        setLivePipelineStage(nodeToPipelineStage(event.node));
      }
      if (event.type === "approval_required") {
        setLivePipelineStage(8);
        void loadData();
      }
      if (event.type === "opportunity_done") {
        setStreamDone(true);
        setStreaming(false);
        setLivePipelineStage(null);
        es.close();
        if (event.state === "AWAITING_APPROVAL") {
          setApprovalMsg(null);
        }
        void loadData();
      }
      if (event.type === "error") {
        setStreaming(false);
        setLivePipelineStage(null);
        es.close();
      }
    };

    es.onerror = () => {
      setStreaming(false);
      setLivePipelineStage(null);
      es.close();
    };
  }, [id, loadData]);

  useEffect(() => () => { esRef.current?.close(); }, []);

  const handleApprove = async () => {
    if (!approval) return;
    setApprovalLoading(true);
    try {
      await api.approvals.approve(id, {
        principal,
        claim_hash: approval.claim_hash,
        amount: approval.amount,
        state_version: approval.state_version,
        notes: "Approved via Recoup",
      });
      setApprovalMsg("Approved — redirecting to ledger…");
      await loadData();
      setTimeout(() => router.push("/recovery"), 1200);
    } catch (e) {
      setApprovalMsg(`Error: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setApprovalLoading(false);
    }
  };

  const handleDecline = async () => {
    if (!approval) return;
    setApprovalLoading(true);
    try {
      await api.approvals.decline(id, { principal, notes: "Declined" });
      setApproval(null);
      setApprovalMsg("Recovery declined.");
      await loadData();
    } catch (e) {
      setApprovalMsg(`Error: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setApprovalLoading(false);
    }
  };

  const handleInvestigate = async () => {
    if (!approval) return;
    setApprovalLoading(true);
    try {
      await api.approvals.investigate(id, { principal, notes: "Investigate Further" });
      setApproval(null);
      setApprovalMsg(
        "Marked for further investigation. Use Re-run Investigation when ready to return to approval."
      );
      await loadData();
    } catch (e) {
      setApprovalMsg(`Error: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setApprovalLoading(false);
    }
  };

  const isRecovered = oppState === "RECOVERED";
  const isFailed = ["REJECTED", "FAILED", "DECLINED", "DENIED"].includes(oppState);

  const pipelineActiveStage =
    livePipelineStage ??
    (oppState ? pipelineStageForOpportunity(oppState) : approval?.state === "PENDING" ? 8 : 1);

  const service = String(trace?.signal?.service ?? opportunity?.service ?? "AWS");
  const region = String(trace?.signal?.region ?? opportunity?.region ?? "");
  const resourceId =
    trace?.signal?.resource_id != null
      ? String(trace.signal.resource_id)
      : finding?.resource_id ?? null;
  const issueText = trace?.hypothesis_summary ?? "";
  const savings = opportunity?.potential_value ? parseFloat(opportunity.potential_value) : 0;
  const confidence = opportunity?.confidence != null ? parseFloat(String(opportunity.confidence)) : null;

  const fallbackCtx = approval
    ? fallbackApprovalContext(approval.action, approval.amount)
    : null;

  const recommendation = serviceRecommendation(
    service,
    issueText,
    approval?.action,
    approval?.action_description ?? fallbackCtx?.action_description
  );

  const rollback = serviceRollback(
    service,
    approval?.rollback_context ?? fallbackCtx?.rollback_context
  );

  const riskTier = approval?.risk_tier ?? fallbackCtx?.risk_tier ?? "YELLOW";
  const findingHeadline = serviceFindingSummary(issueText || `Idle ${service} resource`, service);
  const evidence = deriveConciseEvidence(trace, service, issueText);
  const evidenceSources = deriveEvidenceSources(
    service,
    finding?.finding_type,
    finding?.evidence,
    trace
  );
  const whyText = approvalWhyText(issueText);
  const execLabel = executionStageLabel(oppState);
  const lifecycleLabel = formatLifecycleLabel(oppState);
  const executedAction = executedRecoveryActionLabel(
    service,
    issueText || finding?.issue,
    approval?.action
  );
  const showInvestigate = canRerunInvestigation(oppState);

  return (
    <div className="flex flex-col min-h-screen p-6 space-y-5 max-w-5xl">
      <Link href="/opportunities" className="text-slate-500 hover:text-slate-300 text-sm">
        ← Opportunities
      </Link>

      {isRecovered && savings > 0 && (
        <RecoveryVerifiedHero
          amountMonthly={savings}
          service={service}
          resourceId={resourceId}
          region={region || undefined}
          executedAction={executedAction}
          verifiedAt={verifiedAt}
        />
      )}

      {/* 1. HERO SUMMARY */}
      {!isRecovered && (
        <header className="space-y-3">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="space-y-2 min-w-0">
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-2xl">{serviceIcon(service)}</span>
                <h1 className="text-2xl font-bold text-slate-100">{service} Opportunity</h1>
                <StatusBadge state={oppState} />
              </div>
              {savings > 0 && (
                <p className="text-3xl font-mono font-bold text-emerald-400 tabular-nums">
                  {fmtSavings(savings)} recoverable
                </p>
              )}
            </div>
            {showInvestigate && (
              <Button variant="secondary" size="sm" loading={streaming} onClick={startStream}>
                {streaming
                  ? "Investigating…"
                  : streamDone || oppState === "AWAITING_APPROVAL"
                  ? "Re-run Investigation"
                  : "Run Investigation"}
              </Button>
            )}
          </div>
          <div>
            <p className="text-base font-medium text-slate-200">{findingHeadline}</p>
            <p className="text-sm text-slate-400 mt-0.5">
              No meaningful activity detected in the evaluation window.
            </p>
          </div>
        </header>
      )}

      {/* 2. 11-STEP PIPELINE — hidden once recovery is verified */}
      {!isRecovered && (
        <Card className="border-slate-700/40">
          <CardContent className="py-3">
            <LifecycleStepper
              activeStage={pipelineActiveStage}
              failed={isFailed}
              executionLabel={execLabel}
              lifecycleLabel={lifecycleLabel}
            />
            {streaming && (
              <p className="text-xs text-blue-400 mt-2 flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse" />
                Live investigation in progress
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {!isRecovered && (
        <>
          {/* 3. DECISION SUMMARY — four compact metrics only */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="rounded-lg border border-slate-700/40 bg-slate-800/30 px-4 py-3 min-h-[88px] flex flex-col justify-center">
              <span className="text-[10px] font-medium uppercase tracking-widest text-slate-500">Evidence</span>
              <p className="text-lg font-bold text-slate-200 mt-1">{evidence.length} signals</p>
            </div>
            <div className="rounded-lg border border-slate-700/40 bg-slate-800/30 px-4 py-3 min-h-[88px] flex flex-col justify-center">
              <MetricCard label="Impact" value={fmtSavings(savings)} sub={fmtYearlySavings(savings)} accent="green" />
            </div>
            <div className="rounded-lg border border-slate-700/40 bg-slate-800/30 px-4 py-3 min-h-[88px] flex flex-col justify-center">
              <span className="text-[10px] font-medium uppercase tracking-widest text-slate-500 mb-1">Risk</span>
              <RiskIndicator tier={riskTier} />
            </div>
            <div className="rounded-lg border border-slate-700/40 bg-slate-800/30 px-4 py-3 min-h-[88px] flex flex-col justify-center">
              <ConfidenceIndicator value={confidence} />
            </div>
          </div>

          {/* 4. EVIDENCE + RECOMMENDATION */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <CardContent className="py-4 space-y-4">
                <h3 className="text-xs font-semibold uppercase tracking-widest text-slate-400">
                  What Recoup Found
                </h3>
                {resourceId && (
                  <div>
                    <span className="text-[10px] uppercase tracking-widest text-slate-500">
                      {service === "RDS" ? "DB instance" : service === "EC2" ? "Instance" : "Resource"}
                    </span>
                    <p className="font-mono text-[11px] text-slate-500 truncate mt-0.5" title={resourceId}>
                      {truncateResourceId(resourceId, 36)}
                    </p>
                  </div>
                )}
                <div>
                  <span className="text-[10px] uppercase tracking-widest text-slate-500">Evidence</span>
                  <div className="mt-2">
                    <EvidenceList items={evidence} />
                  </div>
                </div>
                <EvidenceSourceChips sources={evidenceSources} />
              </CardContent>
            </Card>

            <Card>
              <CardContent className="py-4 space-y-3">
                <h3 className="text-xs font-semibold uppercase tracking-widest text-slate-400">
                  Recommended Action
                </h3>
                <p className="text-base font-semibold text-slate-100">{recommendation.action}</p>
                {recommendation.detail && (
                  <p className="text-sm text-slate-400">{recommendation.detail}</p>
                )}
                <div className="pt-2 border-t border-slate-700/40">
                  <span className="text-[10px] uppercase tracking-widest text-slate-500">Rollback</span>
                  <p className="text-sm text-slate-400 mt-1">{rollback}</p>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* 6. TECHNICAL DETAILS */}
          <TechnicalDetails>
            <div className="space-y-2 font-sans text-xs">
              <p><span className="text-slate-500">Opportunity ID:</span> {id}</p>
              {resourceId && <p><span className="text-slate-500">Resource ARN/ID:</span> {resourceId}</p>}
              {region.length > 0 && <p><span className="text-slate-500">Region:</span> {region}</p>}
              {approval && <p><span className="text-slate-500">Claim hash:</span> {approval.claim_hash}</p>}
              {approval?.action && <p><span className="text-slate-500">Backend action:</span> {approval.action}</p>}
              {recommendation.raw && (
                <p><span className="text-slate-500">Raw recommendation:</span> {recommendation.raw}</p>
              )}
              {trace?.hypothesis_summary && (
                <p><span className="text-slate-500">Agent trace:</span> {trace.hypothesis_summary}</p>
              )}
              {showInvestigate && (
                <button
                  type="button"
                  onClick={startStream}
                  className="text-blue-400 hover:text-blue-300 mt-2"
                >
                  Re-run agent investigation →
                </button>
              )}
            </div>
          </TechnicalDetails>
        </>
      )}

      {/* 5. APPROVAL / CURRENT ACTION */}
      {approval && approval.state === "PENDING" && (
        <DecisionCard
          action={recommendation.action}
          why={whyText}
          impactMonthly={parseFloat(approval.amount) || savings}
          riskTier={riskTier}
          rollback={rollback}
          loading={approvalLoading}
          onApprove={() => void handleApprove()}
          onDecline={() => void handleDecline()}
          onInvestigate={() => void handleInvestigate()}
          message={approvalMsg}
        />
      )}

      {oppState === "NEEDS_FOLLOWUP" && !approval && !approvalMsg && (
        <div className="rounded-lg border border-amber-700/50 bg-amber-900/10 px-4 py-3 text-sm text-amber-200">
          Under investigation — re-run the agent investigation when you are ready to approve or decline again.
        </div>
      )}

      {approvalMsg && !approval && (
        <div
          className={`rounded-lg px-4 py-3 text-sm ${
            oppState === "DENIED"
              ? "border border-red-800/50 bg-red-900/10 text-red-300"
              : "border border-blue-700/50 bg-blue-900/10 text-blue-300"
          }`}
        >
          {approvalMsg}
        </div>
      )}
    </div>
  );
}
