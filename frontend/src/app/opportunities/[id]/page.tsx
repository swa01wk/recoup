"use client";

import { useEffect, useState, useRef, useCallback, startTransition } from "react";
import { use } from "react";
import {
  api,
  type TraceResult,
  type ApprovalRecord,
  type SseEvent,
  type Opportunity,
  type Finding,
} from "@/lib/api";
import { loadLastScan } from "@/lib/recovery-storage";
import { requestRecoveryDataRefresh } from "@/lib/recovery-data-events";
import { useRole } from "@/hooks/useRole";
import { fallbackApprovalContext } from "@/lib/competitive-ui";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { pipelineStageForOpportunity } from "@/lib/recovery-storage";
import { fmtSavings, formatLifecycleLabel } from "@/lib/recoup-ui-rules";
import {
  serviceFindingSummary,
  serviceRecommendation,
  serviceRollback,
  deriveConciseEvidence,
  executedRecoveryActionLabel,
  approvalWhyText,
  executionStageLabel,
  canRerunInvestigation,
} from "@/lib/service-presentation";
import { LifecycleStepper } from "@/components/recoup/lifecycle-stepper";
import { DecisionCard } from "@/components/recoup/decision-card";
import { RecoveryVerifiedHero } from "@/components/recoup/recovery-verified-hero";
import { SummaryMetricCards } from "@/components/recoup/summary-metric-cards";
import { EvidenceGraphColumn } from "@/components/recoup/evidence-graph-column";
import { RecommendationPanel } from "@/components/recoup/recommendation-panel";
import { RecoveryPlanCollapsible } from "@/components/recoup/recovery-plan-collapsible";
import { RecommendationUpdatedBanner } from "@/components/recoup/recommendation-updated-banner";
import { OpportunityHeader } from "@/components/recoup/opportunity-header";
import { WhatRecoupFound } from "@/components/recoup/what-recoup-found";
import { WhyRecoupBelieves } from "@/components/recoup/why-recoup-believes";
import { SafetyChecksCard } from "@/components/recoup/safety-checks-card";
import { ConfidenceDetails } from "@/components/recoup/confidence-details";
import { PolicyGovernance } from "@/components/recoup/policy-governance";
import {
  RawEvidenceAccordion,
  type RawEvidenceAccordionHandle,
} from "@/components/recoup/raw-evidence-accordion";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { RiskIndicator } from "@/components/recoup/risk-indicator";
import Link from "next/link";
import type { InvestigationDelta, RecoveryAssessment } from "@/lib/recovery-types";
import {
  actionConfidenceForPrimary,
  evidenceBulletsFromAssessment,
  insightSummary,
  monthlySavingsFromAssessment,
  policyLabelFromAssessment,
  riskTierFromLevel,
  topInsight,
} from "@/lib/recovery-presentation";

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

  const [trace, setTrace] = useState<TraceResult | null>(null);
  const [opportunity, setOpportunity] = useState<Opportunity | null>(null);
  const [approval, setApproval] = useState<ApprovalRecord | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [livePipelineStage, setLivePipelineStage] = useState<number | null>(null);
  const [approvalLoading, setApprovalLoading] = useState(false);
  const [approvalMsg, setApprovalMsg] = useState<string | null>(null);
  const [finding, setFinding] = useState<Finding | null>(null);
  const [verifiedAt, setVerifiedAt] = useState<string | null>(null);
  const [outcomeRecovered, setOutcomeRecovered] = useState(false);
  const [investigationDelta, setInvestigationDelta] = useState<InvestigationDelta | null>(null);
  const [approveOpen, setApproveOpen] = useState(false);
  const [investigateLines, setInvestigateLines] = useState<string[]>([]);
  const esRef = useRef<EventSource | null>(null);
  const rawEvidenceRef = useRef<RawEvidenceAccordionHandle>(null);

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

  const syncRecoveryLedger = useCallback(async () => {
    await loadData();
    requestRecoveryDataRefresh();
  }, [loadData]);

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
    setStreaming(true);
    setApprovalMsg(null);
    setInvestigateLines([
      "Checking longer utilization window",
      "Checking recent CloudTrail activity",
      "Revalidating dependencies",
    ]);
    setLivePipelineStage(2);

    const es = new EventSource(api.opportunities.streamUrl(id));
    esRef.current = es;

    es.onmessage = (ev: MessageEvent) => {
      const event = JSON.parse(ev.data as string) as SseEvent;
      if (event.type === "node_started") {
        requestRecoveryDataRefresh();
      }
      if ((event.type === "node_started" || event.type === "node_completed") && event.node) {
        setLivePipelineStage(nodeToPipelineStage(event.node));
      }
      if (event.type === "node_completed" && event.investigation_delta) {
        setInvestigationDelta(event.investigation_delta);
        void syncRecoveryLedger();
      }
      if (event.type === "approval_required") {
        setLivePipelineStage(8);
        void syncRecoveryLedger();
      }
      if (event.type === "opportunity_done") {
        setStreaming(false);
        setLivePipelineStage(null);
        setInvestigateLines([]);
        es.close();
        if (event.state === "AWAITING_APPROVAL") {
          setApprovalMsg(null);
        }
        void syncRecoveryLedger();
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
  }, [id, syncRecoveryLedger]);

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
      setApprovalMsg("Approved — executing recovery on this opportunity.");
      setApproveOpen(false);
      await syncRecoveryLedger();
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
      await syncRecoveryLedger();
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
      setApprovalMsg(null);
      await syncRecoveryLedger();
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
  const region = String(trace?.signal?.region ?? opportunity?.region ?? finding?.region ?? "");
  const resourceId =
    trace?.signal?.resource_id != null
      ? String(trace.signal.resource_id)
      : finding?.resource_id ?? null;
  const issueText = trace?.hypothesis_summary ?? finding?.issue ?? "";
  const savingsRaw = opportunity?.potential_value ? parseFloat(opportunity.potential_value) : 0;
  const assessment: RecoveryAssessment | null = trace?.recovery_assessment ?? null;
  const savings = monthlySavingsFromAssessment(assessment, savingsRaw);
  const executionStatus =
    trace?.workflow?.execution_status ||
    (isRemediating ? executionStageLabel(oppState) : "");
  const discoveryConf =
    assessment?.discovery_confidence?.score ??
    (opportunity?.discovery_confidence != null
      ? opportunity.discovery_confidence
      : opportunity?.confidence != null
        ? parseFloat(String(opportunity.confidence)) * 100
        : null);
  const actionConf =
    actionConfidenceForPrimary(assessment) ?? opportunity?.action_confidence ?? null;

  const fallbackCtx = approval
    ? fallbackApprovalContext(approval.action, approval.amount)
    : null;

  const recommendation =
    assessment?.recommendation?.primary_action_label
      ? {
          action: assessment.recommendation.primary_action_label,
          detail: assessment.recommendation.reasoning,
          raw: approval?.action_description,
        }
      : serviceRecommendation(
          service,
          issueText,
          approval?.action,
          approval?.action_description ?? fallbackCtx?.action_description
        );

  const rollback = serviceRollback(
    service,
    approval?.rollback_context ?? fallbackCtx?.rollback_context
  );

  const riskTier =
    approval?.risk_tier ??
    riskTierFromLevel(assessment?.risk_assessment?.level ?? opportunity?.risk_level ?? undefined) ??
    fallbackCtx?.risk_tier ??
    "YELLOW";
  const findingHeadline = serviceFindingSummary(issueText || `Idle ${service} resource`, service);
  const assessmentEvidence = evidenceBulletsFromAssessment(assessment);
  const evidence =
    assessmentEvidence.supporting.length > 0
      ? assessmentEvidence.supporting
      : deriveConciseEvidence(trace, service, issueText);
  const counterEvidence = assessmentEvidence.counter;
  const whyText = approvalWhyText(issueText);
  const execLabel = executionStageLabel(oppState);
  const lifecycleLabel = formatLifecycleLabel(oppState);
  const executedAction = executedRecoveryActionLabel(
    service,
    issueText || finding?.issue,
    approval?.action
  );
  const pendingApproval = approval?.state === "PENDING";
  const showInvestigate = canRerunInvestigation(oppState) && !pendingApproval;
  const extendedInvestigationLabel =
    oppState === "NEEDS_FOLLOWUP" ? "Run Extended Investigation" : "Re-run Investigation";

  const policyLabel = policyLabelFromAssessment(assessment);
  const headerNarrative =
    topInsight(assessment) ??
    "Recoup found no meaningful operational activity and identified a reversible recovery action.";
  const resourceLabel =
    service === "RDS" ? "DB instance" : service === "EC2" ? "Instance" : "Resource";
  const foundBody = resourceId
    ? `${resourceLabel} ${resourceId} continues to incur recurring cost despite showing no meaningful operational activity.`
    : (insightSummary(assessment) ?? issueText) ||
      "This resource shows patterns consistent with recoverable waste while continuing to incur cost.";

  const impactMonthly = approval ? parseFloat(approval.amount) || savings : savings;
  const approveCtaLabel = `Approve ${fmtSavings(impactMonthly)} Recovery`;

  const openRawEvidence = () => {
    rawEvidenceRef.current?.open();
    document.getElementById("raw-evidence")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="flex flex-col min-h-screen p-6 space-y-5 max-w-7xl mx-auto">
      {isRecovered && (
        <>
          <Link href="/opportunities" className="text-slate-500 hover:text-slate-300 text-sm">
            ← Opportunities
          </Link>
          {savings > 0 && (
            <RecoveryVerifiedHero
              amountMonthly={savings}
              service={service}
              resourceId={resourceId}
              region={region || undefined}
              executedAction={executedAction}
              verifiedAt={verifiedAt}
            />
          )}
        </>
      )}

      {!isRecovered && (
        <>
          <OpportunityHeader
            service={service}
            oppState={oppState}
            savings={savings}
            findingHeadline={findingHeadline}
            narrative={headerNarrative}
            resourceId={resourceId}
            region={region}
            findingLabel={findingHeadline}
            policyLabel={policyLabel}
            riskTier={riskTier}
            showInvestigate={showInvestigate}
            streaming={streaming}
            investigateLabel={extendedInvestigationLabel}
            onInvestigate={startStream}
          />

          <Card className="border-slate-700/40">
            <CardContent className="py-3">
              <LifecycleStepper
                activeStage={pipelineActiveStage}
                failed={isFailed}
                executionLabel={execLabel}
                lifecycleLabel={lifecycleLabel}
                assessment={assessment}
                pendingApproval={pendingApproval}
              />
              {streaming && (
                <div className="text-xs text-blue-400 mt-2 space-y-1">
                  <p className="flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse" />
                    Investigating…
                  </p>
                  <ul className="pl-4 text-slate-500 space-y-0.5">
                    {investigateLines.map((line) => (
                      <li key={line}>• {line}</li>
                    ))}
                  </ul>
                </div>
              )}
              {!streaming && executionStatus && (
                <p className="text-xs text-blue-300/90 mt-2">{executionStatus}</p>
              )}
            </CardContent>
          </Card>

          <RecommendationUpdatedBanner delta={investigationDelta} />

          <SummaryMetricCards
            assessment={assessment}
            savings={savings}
            riskTier={riskTier}
            discoveryConf={discoveryConf}
            actionConf={actionConf}
            evidenceFallbackCount={evidence.length}
            rollbackFallback={assessment?.recovery_plan?.rollback_strategy ?? rollback}
          />

          <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)] gap-4">
            <div className="space-y-4">
              <Card>
                <CardContent className="py-4 space-y-6">
                  <WhatRecoupFound
                    headline={findingHeadline}
                    body={foundBody}
                    savings={savings}
                  />
                  <WhyRecoupBelieves
                    whyBullets={evidence}
                    counterBullets={counterEvidence}
                    onViewRawEvidence={openRawEvidence}
                  />
                  <EvidenceGraphColumn
                    graph={assessment?.evidence_graph}
                    signals={assessment?.signals ?? []}
                    claimFallback={issueText}
                    recommendationFallback={recommendation.action}
                    savingsMonthly={savings}
                  />
                </CardContent>
              </Card>
            </div>

            <div className="space-y-4">
              <Card>
                <CardContent className="py-4 space-y-6">
                  <RecommendationPanel
                    action={recommendation.action}
                    detail={recommendation.detail}
                    assessment={assessment}
                    savings={savings}
                  />
                  <SafetyChecksCard checks={assessment?.safety_checks ?? []} />
                </CardContent>
              </Card>
              <Card>
                <CardContent className="py-4">
                  <RecoveryPlanCollapsible plan={assessment?.recovery_plan} variant="card" />
                </CardContent>
              </Card>
            </div>
          </div>

          {pendingApproval && approval && (
            <>
              <DecisionCard
                action={recommendation.action}
                why={topInsight(assessment) ?? whyText}
                impactMonthly={impactMonthly}
                riskTier={riskTier}
                rollback={assessment?.recovery_plan?.rollback_strategy ?? rollback}
                policyNote={assessment?.policy_note ?? policyLabel}
                loading={approvalLoading}
                approveLabel={approveCtaLabel}
                onApprove={() => setApproveOpen(true)}
                onDecline={() => void handleDecline()}
                onInvestigate={() => void handleInvestigate()}
                message={approvalMsg}
              />
              <Dialog open={approveOpen} onOpenChange={setApproveOpen}>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Approve Recovery</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-3 text-sm">
                    <p>
                      <span className="text-slate-500">Action:</span>{" "}
                      <span className="text-slate-100 font-medium">{recommendation.action}</span>
                    </p>
                    <p>
                      <span className="text-slate-500">Projected recovery:</span>{" "}
                      {fmtSavings(impactMonthly)}
                    </p>
                    <div className="flex items-center gap-2">
                      <span className="text-slate-500">Risk:</span>
                      <RiskIndicator tier={riskTier} />
                    </div>
                    {actionConf != null && (
                      <p>
                        <span className="text-slate-500">Action confidence:</span>{" "}
                        {Math.round(actionConf)}%
                      </p>
                    )}
                    <p>
                      <span className="text-slate-500">Rollback:</span>{" "}
                      {assessment?.recovery_plan?.rollback_strategy ?? rollback}
                    </p>
                  </div>
                  <DialogFooter>
                    <Button variant="secondary" size="sm" onClick={() => setApproveOpen(false)}>
                      Cancel
                    </Button>
                    <Button
                      variant="success"
                      size="md"
                      loading={approvalLoading}
                      onClick={() => void handleApprove()}
                    >
                      Approve &amp; Execute
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </>
          )}

          {oppState === "NEEDS_FOLLOWUP" && !approval && (
            <div className="rounded-lg border border-amber-700/50 bg-amber-900/10 px-4 py-3 text-sm text-amber-200 space-y-3">
              <p>
                Under investigation — run extended investigation when you are ready to approve or
                decline again.
              </p>
              <Button variant="secondary" size="sm" loading={streaming} onClick={startStream}>
                {streaming ? "Investigating…" : "Run Extended Investigation"}
              </Button>
            </div>
          )}

          {approvalMsg && !approval && oppState !== "NEEDS_FOLLOWUP" && (
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

          <ConfidenceDetails
            assessment={assessment}
            discoveryConf={discoveryConf}
            actionConf={actionConf}
          />
          <PolicyGovernance assessment={assessment} />
          <RawEvidenceAccordion
            ref={rawEvidenceRef}
            opportunityId={id}
            opportunity={opportunity}
            finding={finding}
            trace={trace}
            signals={assessment?.signals ?? []}
            showRerun={showInvestigate}
            onRerunInvestigation={startStream}
          />
        </>
      )}
    </div>
  );
}
